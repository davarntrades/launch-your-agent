"""python3 -m unittest discover -s tests   (from governance-agent/)"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governor import AUTHORIZE, ESCALATE, WITHHOLD, Pipeline, evaluate, initial_state, verify_chain  # noqa: E402
from governor.state import digest  # noqa: E402


class GovernorTests(unittest.TestCase):
    def test_evaluate_does_not_modify_state(self):
        s = initial_state()
        d = digest(s)
        evaluate(s, {"action_type": "spend", "target": "x", "parameters": {"amount_cents": 1}})
        self.assertEqual(digest(s), d)

    def test_same_input_same_verdict(self):
        p = {"action_type": "delete_file", "target": "/drafts/old-plan.md", "parameters": {"mode": "permanent"}}
        a, b = evaluate(initial_state(), p), evaluate(initial_state(), p)
        self.assertEqual((a["verdict"], a["reasons"]), (b["verdict"], b["reasons"]))

    def test_unknown_action_withheld(self):
        r = evaluate(initial_state(), {"action_type": "add_allowlist", "target": "x@y", "parameters": {}})
        self.assertEqual(r["verdict"], WITHHOLD)
        self.assertEqual(r["violated"], ["transition_defined"])

    def test_withhold_leaves_real_state_unchanged(self):
        pipe = Pipeline(initial_state())
        d = digest(pipe.state)
        e = pipe.submit({"action_type": "assign_role", "target": "worker", "parameters": {"role": "admin"}})
        self.assertEqual(e["verdict"], WITHHOLD)
        self.assertEqual(digest(pipe.state), d)

    def test_role_composition_widening(self):
        pipe = Pipeline(initial_state())
        e1 = pipe.submit({"action_type": "create_role", "target": "helpers", "parameters": {"permissions": ["grant"]}})
        e2 = pipe.submit({"action_type": "assign_role", "target": "bob", "parameters": {"role": "helpers"}})
        self.assertEqual((e1["verdict"], e2["verdict"]), (AUTHORIZE, WITHHOLD))

    def test_escalation_queue_and_approval(self):
        pipe = Pipeline(initial_state())
        e = pipe.submit({"id": "d1", "action_type": "delete_file", "target": "/drafts/old-plan.md",
                         "parameters": {"mode": "permanent"}})
        self.assertEqual(e["verdict"], ESCALATE)
        self.assertIn("/drafts/old-plan.md", pipe.state["files"])
        self.assertIn("d1", pipe.pending)
        a = pipe.approve("d1", approver="alice")
        self.assertEqual(a["verdict"], AUTHORIZE)
        self.assertNotIn("/drafts/old-plan.md", pipe.state["files"])
        self.assertTrue(verify_chain(pipe.audit.entries))

    def test_approval_rechecks_current_state(self):
        pipe = Pipeline(initial_state())
        pipe.submit({"id": "d1", "action_type": "delete_file", "target": "/drafts/old-plan.md",
                     "parameters": {"mode": "permanent"}})
        pipe.submit({"action_type": "delete_file", "target": "/drafts/old-plan.md", "parameters": {"mode": "trash"}})
        a = pipe.approve("d1", approver="alice")  # file already moved: transition undefined now
        self.assertEqual(a["verdict"], WITHHOLD)

    def test_audit_tamper_detected(self):
        pipe = Pipeline(initial_state())
        pipe.submit({"action_type": "spend", "target": "x", "parameters": {"amount_cents": 1}})
        pipe.submit({"action_type": "spend", "target": "x", "parameters": {"amount_cents": 2}})
        pipe.audit.entries[0]["verdict"] = WITHHOLD
        self.assertFalse(verify_chain(pipe.audit.entries))


if __name__ == "__main__":
    unittest.main()
