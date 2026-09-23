"""Executor, audit log and the pipeline that connects them to the Governor.

    Worker proposal -> Governor.evaluate -> Executor.commit (AUTHORIZE only) -> audit

Boundary properties enforced here:
  * The Executor holds the only reference to the real state. `Pipeline.state`
    returns a copy; nothing outside the Executor can obtain a mutable handle.
  * Commit is compare-and-swap on the authorization binding: the live state
    must still match `state_digest`, and the committed state is the simulated
    state whose digest was checked. A stale or altered authorization raises
    StaleAuthorization and nothing is written.
  * Proposal ids are single-use; a replayed id is WITHHOLD.
  * Evaluate + commit run under one lock, so no other submission interleaves.
  * ESCALATE proposals wait in a queue; approve() re-evaluates against the
    current state and commits under a fresh authorization. approve() is a
    Python call for the operator; no proposal type reaches it.
"""

import hashlib
import json
import threading

from .constraints import CONSTRAINTS, ESCALATE, WITHHOLD
from .governor import AUTHORIZE, evaluate
from .state import clone, digest


class StaleAuthorization(Exception):
    pass


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
    """The only holder of, and only writer to, the real state."""

    def __init__(self, state):
        self._state = clone(state)

    def snapshot(self):
        return clone(self._state)

    def digest(self):
        return digest(self._state)

    def commit(self, authorization, proposal, simulated_state):
        if authorization is None:
            raise StaleAuthorization("no authorization")
        if digest(self._state) != authorization["state_digest"]:
            raise StaleAuthorization("live state differs from the evaluated state")
        if digest(proposal) != authorization["proposal_digest"]:
            raise StaleAuthorization("proposal differs from the evaluated proposal")
        if digest(simulated_state) != authorization["result_digest"]:
            raise StaleAuthorization("result differs from the evaluated result")
        self._state = clone(simulated_state)


class Pipeline:
    def __init__(self, state, policy, audit_path=None, constraints=CONSTRAINTS, max_proposals=500):
        self.policy = policy
        self._executor = Executor(state)
        self.audit = AuditLog(audit_path)
        self.constraints = constraints
        self.max_proposals = max_proposals
        self._pending = {}  # proposal id -> normalised proposal (ESCALATE queue)
        self._seen_ids = set()
        self._auto_id = 0
        self._lock = threading.Lock()

    @property
    def state(self):
        """A copy of the real state. Mutating it has no effect."""
        return self._executor.snapshot()

    @property
    def pending(self):
        return sorted(self._pending)

    def submit(self, raw_proposal):
        with self._lock:
            before = self._executor.snapshot()
            pid = raw_proposal.get("id") if isinstance(raw_proposal, dict) else None
            if not pid:
                self._auto_id += 1
                pid = f"p{self._auto_id:03d}"
                if isinstance(raw_proposal, dict):
                    raw_proposal = dict(raw_proposal, id=pid)
            if not isinstance(pid, str) or pid in self._seen_ids:
                result = {"verdict": WITHHOLD, "violated": ["single_use_id"],
                          "reasons": [f"proposal id {pid!r} already used or invalid"], "proposal": None}
                return self._log("proposal", raw_proposal, before, result)
            self._seen_ids.add(pid)
            if len(self._seen_ids) > self.max_proposals:
                result = {"verdict": WITHHOLD, "violated": ["proposal_budget"],
                          "reasons": [f"more than {self.max_proposals} proposals in this pipeline"], "proposal": None}
                return self._log("proposal", raw_proposal, before, result)

            result = evaluate(self.policy, before, raw_proposal, self.constraints)
            if result["verdict"] == AUTHORIZE:
                self._executor.commit(result["authorization"], result["proposal"], result["simulated_state"])
            elif result["verdict"] == ESCALATE:
                self._pending[pid] = result["proposal"]
            return self._log("proposal", result["proposal"] or raw_proposal, before, result)

    def approve(self, proposal_id, approver):
        """Release a held ESCALATE proposal with a recorded approval."""
        with self._lock:
            before = self._executor.snapshot()
            proposal = self._pending.pop(proposal_id, None)
            if proposal is None:
                result = {"verdict": WITHHOLD, "violated": ["no_pending_escalation"],
                          "reasons": [f"no pending escalation {proposal_id!r}"], "proposal": None}
                return self._log("escalation_approval", {"id": proposal_id}, before, result, approver=approver)
            result = evaluate(self.policy, before, proposal, self.constraints)
            hard = [n for n, _, c in self.constraints if c == WITHHOLD and n in result["violated"]]
            if result["verdict"] == WITHHOLD or hard:
                result = dict(result, verdict=WITHHOLD)
            else:
                result = dict(result, verdict=AUTHORIZE,
                              reasons=result["reasons"] + [f"escalation approved by {approver}"])
                self._executor.commit(result["authorization"], result["proposal"], result["simulated_state"])
            return self._log("escalation_approval", proposal, before, result, approver=approver)

    def reject(self, proposal_id, approver):
        with self._lock:
            before = self._executor.snapshot()
            proposal = self._pending.pop(proposal_id, {"id": proposal_id})
            result = {"verdict": WITHHOLD, "violated": [], "reasons": [f"escalation rejected by {approver}"]}
            return self._log("escalation_rejection", proposal, before, result, approver=approver)

    def _log(self, kind, proposal, before, result, **extra):
        after = self._executor.snapshot()
        entry = {
            "kind": kind,
            "proposal": json.loads(json.dumps(proposal, default=repr)),
            "state_before": before,
            "state_before_digest": digest(before),
            "verdict": result["verdict"],
            "violated": result["violated"],
            "reasons": result["reasons"],
            "state_after": after,
            "state_after_digest": digest(after),
            "policy_digest": digest(self.policy.as_dict()),
            **extra,
        }
        return self.audit.record(entry)
