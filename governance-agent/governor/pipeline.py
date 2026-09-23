"""Executor, audit log and the pipeline that connects them to the Governor.

    Worker proposal -> Governor.evaluate -> Executor (AUTHORIZE only) -> audit

ESCALATE proposals are held in a pending queue. `approve()` re-evaluates a
held proposal against the *current* state; if the only remaining violations
are ESCALATE-class, the recorded approval releases it to the Executor.
"""

import hashlib
import json

from .actions import apply
from .constraints import CONSTRAINTS, ESCALATE, WITHHOLD
from .governor import AUTHORIZE, evaluate
from .state import clone, digest


class AuditLog:
    """Append-only, hash-chained record of every proposal."""

    def __init__(self, path=None):
        self.path = path
        self.entries = []
        self._prev = "0" * 64
        if path:
            open(path, "w").close()

    def record(self, entry):
        entry = dict(entry, seq=len(self.entries), prev_hash=self._prev)
        blob = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        entry["entry_hash"] = hashlib.sha256(blob.encode()).hexdigest()
        self._prev = entry["entry_hash"]
        self.entries.append(entry)
        if self.path:
            with open(self.path, "a") as fh:
                fh.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry


def verify_chain(entries):
    prev = "0" * 64
    for e in entries:
        body = {k: v for k, v in e.items() if k != "entry_hash"}
        if body["prev_hash"] != prev:
            return False
        blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(blob.encode()).hexdigest() != e["entry_hash"]:
            return False
        prev = e["entry_hash"]
    return True


class Executor:
    """The only component that writes to the real state."""

    def __init__(self, state):
        self.state = state

    def execute(self, proposal):
        apply(self.state, proposal)


class Pipeline:
    def __init__(self, state, audit_path=None, constraints=CONSTRAINTS):
        self.executor = Executor(state)
        self.audit = AuditLog(audit_path)
        self.constraints = constraints
        self.pending = {}  # proposal id -> proposal (ESCALATE queue)
        self._auto_id = 0

    @property
    def state(self):
        return self.executor.state

    def _id(self, proposal):
        if not proposal.get("id"):
            self._auto_id += 1
            proposal = dict(proposal, id=f"p{self._auto_id:03d}")
        return proposal

    def submit(self, proposal):
        proposal = self._id(proposal)
        before = clone(self.state)
        result = evaluate(before, proposal, self.constraints)
        if result["verdict"] == AUTHORIZE:
            self.executor.execute(proposal)
        elif result["verdict"] == ESCALATE:
            self.pending[proposal["id"]] = proposal
        return self._log("proposal", proposal, before, result)

    def approve(self, proposal_id, approver):
        """Release a held ESCALATE proposal with a recorded approval."""
        proposal = self.pending.pop(proposal_id)
        before = clone(self.state)
        result = evaluate(before, proposal, self.constraints)
        hard = [n for n, _, c in self.constraints if c == WITHHOLD and n in result["violated"]]
        if result["verdict"] == WITHHOLD or hard:
            result = dict(result, verdict=WITHHOLD)
        else:
            result = dict(result, verdict=AUTHORIZE,
                          reasons=result["reasons"] + [f"escalation approved by {approver}"])
            self.executor.execute(proposal)
        return self._log("escalation_approval", proposal, before, result, approver=approver)

    def reject(self, proposal_id, approver):
        proposal = self.pending.pop(proposal_id)
        before = clone(self.state)
        result = {"verdict": WITHHOLD, "violated": [], "reasons": [f"escalation rejected by {approver}"],
                  "simulated_state": None}
        return self._log("escalation_rejection", proposal, before, result, approver=approver)

    def _log(self, kind, proposal, before, result, **extra):
        entry = {
            "kind": kind,
            "proposal": proposal,
            "state_before": before,
            "state_before_digest": digest(before),
            "verdict": result["verdict"],
            "violated": result["violated"],
            "reasons": result["reasons"],
            "state_after": clone(self.state),
            "state_after_digest": digest(self.state),
            **extra,
        }
        return self.audit.record(entry)
