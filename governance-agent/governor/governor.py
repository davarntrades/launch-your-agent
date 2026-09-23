"""Governor: simulate a proposal on a copy of the state, then test the result
against every constraint predicate.

Pure and deterministic: same (state, proposal) -> same verdict. The input
state is never modified. No model call is involved.
"""

from .actions import TransitionError, apply
from .constraints import CONSTRAINTS, ESCALATE, WITHHOLD
from .state import clone, digest

AUTHORIZE = "AUTHORIZE"


def evaluate(state, proposal, constraints=CONSTRAINTS):
    """Return a verdict dict:

    {verdict, violated: [names], reasons: [str], simulated_state}

    Precedence: any WITHHOLD-class violation -> WITHHOLD; otherwise any
    ESCALATE-class violation -> ESCALATE; otherwise AUTHORIZE.
    """
    before_digest = digest(state)
    simulated = clone(state)
    try:
        apply(simulated, proposal)
    except TransitionError as exc:
        return {
            "verdict": WITHHOLD,
            "violated": ["transition_defined"],
            "reasons": [str(exc)],
            "simulated_state": None,
        }

    violated, reasons, classes = [], [], set()
    for name, predicate, cls in constraints:
        found = predicate(state, simulated)
        if found:
            violated.append(name)
            reasons.extend(f"{name}: {r}" for r in found)
            classes.add(cls)

    assert digest(state) == before_digest, "Governor must not modify the input state"

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
        "simulated_state": simulated,
    }
