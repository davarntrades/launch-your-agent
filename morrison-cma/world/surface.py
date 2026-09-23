"""Execution surface [E].

Holds the only mutable reference to the mock world. Applies a transition only
if the request carries a Morrison `ExecutionLease` that Morrison's own
`LeaseVerifier` accepts for exactly this request. [E] makes no policy decision:
it either redeems a valid lease for a defined transition or refuses.

v0 binds the ACTION, not the WORLD: there is no world-state compare-and-swap.
A lease minted when an alias was internal still executes after the alias was
changed. That exposure (TOCTOU) is deliberately left in v0 so the campaign can
measure it (family D-RACE); see PREREGISTRATION.md.

Offline predictions instantiate this class in-process. The live campaign runs
it as a separate process (surface_server.py, Phase 2) so that the verifier is
not in the process being governed.
"""

from __future__ import annotations

import copy
import threading

from morrison_governance.kernel.mediation import LeaseVerifier

from . import world as W


class ExecutionSurface:
    def __init__(self, lease_key: bytes, state: dict | None = None):
        self._verifier = LeaseVerifier(key=lease_key)
        self._state = copy.deepcopy(state if state is not None else W.initial_world())
        self._lock = threading.Lock()
        self.log: list[dict] = []

    # read-only views ------------------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._state)

    # the only write path --------------------------------------------------
    def submit(self, token: str, request: dict, now: float | None = None) -> dict:
        with self._lock:
            ok, why = self._verifier.verify(token, request=request, now=now)
            if not ok:
                rec = {"status": "LEASE_REFUSED", "reason": why}
                self.log.append(rec)
                return rec
            before = copy.deepcopy(self._state)
            try:
                obs = W.apply(self._state, W.proposal_from_canonical(request))
            except W.Undefined as exc:
                rec = {"status": "UNDEFINED_TRANSITION", "reason": str(exc)}
                self.log.append(rec)
                return rec
            rec = {"status": "APPLIED", "observation": obs,
                   "before_digest": W.digest(before),
                   "after_digest": W.digest(self._state)}
            self.log.append(rec)
            return rec

    # test-only mutation of the world outside any lease (D-RACE setup) ---------
    def _out_of_band(self, fn) -> None:
        with self._lock:
            fn(self._state)
