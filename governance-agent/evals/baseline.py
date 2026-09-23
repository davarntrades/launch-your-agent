"""Comparison baseline: per-proposal field rules, no state simulation.

This is NOT used for authorization. It exists only to show, in the eval
report, which cases a check that inspects the proposal alone (against the
session-start state) gets wrong.
"""

from governor.state import initial_policy, initial_state

_START = initial_state()
_POLICY = initial_policy(_START)


def evaluate(proposal):
    t, target, p = proposal["action_type"], proposal["target"], proposal.get("parameters", {})
    if t == "spend":
        remaining = _POLICY.ceiling_cents - _START["budget"]["spent_cents"]
        return "AUTHORIZE" if p.get("amount_cents", 0) <= remaining else "WITHHOLD"
    if t == "delete_file" and p.get("mode") == "permanent":
        return "ESCALATE"
    if t == "assign_role" and p.get("role") == "admin":
        return "WITHHOLD"
    if t == "send_message":
        return "AUTHORIZE" if target in _POLICY.recipient_allowlist else "WITHHOLD"
    return "AUTHORIZE"
