"""Governor: normalise a proposal, simulate it on a copy of the state, check
the frame condition, then test the result against every constraint predicate.

Pure and deterministic: same (policy, state, proposal) -> same verdict. The
input state is never modified. No model call is involved.

An AUTHORIZE verdict carries an `authorization` binding:
    {state_digest, proposal_digest, result_digest}
The Executor commits only if the live state still has `state_digest`, and it
commits the simulated state itself (checked against `result_digest`), so the
state that was evaluated is exactly the state that gets written.
"""

from .actions import FOOTPRINT, TransitionError, apply, normalize
from .constraints import CONSTRAINTS, ESCALATE, WITHHOLD
from .state import clone, digest

AUTHORIZE = "AUTHORIZE"


def _withhold(name, reason, proposal=None):
    return {"verdict": WITHHOLD, "violated": [name], "reasons": [reason], "proposal": proposal,
            "simulated_state": None, "authorization": None}


def changed_keys(before, after):
    keys = set(before) | set(after)
    return {k for k in keys if before.get(k, object()) != after.get(k, object())}


def evaluate(policy, state, raw_proposal, constraints=CONSTRAINTS):
    """Return {verdict, violated, reasons, proposal, simulated_state, authorization}.

    Precedence: any WITHHOLD-class violation -> WITHHOLD; otherwise any
    ESCALATE-class violation -> ESCALATE; otherwise AUTHORIZE.
    """
    state_digest = digest(state)
    try:
        proposal = normalize(raw_proposal)
    except TransitionError as exc:
        return _withhold("proposal_schema", str(exc))

    simulated = clone(state)
    try:
        apply(simulated, proposal)
    except TransitionError as exc:
        return _withhold("transition_defined", str(exc), proposal)

    outside = changed_keys(state, simulated) - FOOTPRINT[proposal["action_type"]]
    if outside:
        return _withhold("frame_condition", f"{proposal['action_type']} changed undeclared state {sorted(outside)}",
                         proposal)

    violated, reasons, classes = [], [], set()
    for name, predicate, cls in constraints:
        found = predicate(policy, state, simulated)
        if found:
            violated.append(name)
            reasons.extend(f"{name}: {r}" for r in found)
            classes.add(cls)

    assert digest(state) == state_digest, "Governor must not modify the input state"

    if WITHHOLD in classes:
        verdict = WITHHOLD
    elif ESCALATE in classes:
        verdict = ESCALATE
    else:
        verdict = AUTHORIZE
    return {
        "verdict": verdict,
        "violated": violated,
        "reasons": reasons or ["resulting state satisfies all constraints"],
        "proposal": proposal,
        "simulated_state": simulated,
        "authorization": {
            "state_digest": state_digest,
            "proposal_digest": digest(proposal),
            "result_digest": digest(simulated),
        } if verdict != WITHHOLD else None,
    }
