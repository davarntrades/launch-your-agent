"""Constraint predicates that define the admissible set.

Each constraint is a pure function (policy, before, after) -> list of
violation reasons (empty list = satisfied). `after` is the simulated state;
`policy` is the frozen Policy, which no transition can reach. Each
constraint carries the verdict class it produces when violated:

    WITHHOLD  - the resulting state is outside the admissible set
    ESCALATE  - the resulting state is admissible only with a recorded approval
"""

from .state import effective_permissions, recoverable_content

WITHHOLD = "WITHHOLD"
ESCALATE = "ESCALATE"


def spend_ceiling(policy, before, after):
    spent = after["budget"]["spent_cents"]
    if spent > policy.ceiling_cents:
        return [f"spent {spent} > ceiling {policy.ceiling_cents} cents"]
    return []


def no_irreversible_delete(policy, before, after):
    lost = recoverable_content(before) - recoverable_content(after)
    return [f"{path} (content {h}) is no longer recoverable" for path, h in sorted(lost)]


def no_permission_widening(policy, before, after):
    reasons = []
    for principal in sorted(after["principals"]):
        base = policy.baseline_permissions.get(principal, frozenset())
        extra = effective_permissions(after, principal) - base
        if extra:
            reasons.append(f"{principal} gains {sorted(extra)} beyond baseline {sorted(base)}")
    return reasons


def recipient_allowlist(policy, before, after):
    reasons = []
    for i, msg in enumerate(after["outbox"]):
        unlisted = sorted(set(msg["delivered_to"]) - policy.recipient_allowlist)
        if unlisted:
            reasons.append(f"outbox[{i}] to {msg['to']!r} delivers to unlisted {unlisted}")
    return reasons


# Evaluation order is fixed; it determines which violation is reported first.
CONSTRAINTS = [
    ("spend_ceiling", spend_ceiling, WITHHOLD),
    ("no_permission_widening", no_permission_widening, WITHHOLD),
    ("recipient_allowlist", recipient_allowlist, WITHHOLD),
    ("no_irreversible_delete", no_irreversible_delete, ESCALATE),
]


def hard_invariants_hold(policy, state):
    """True if `state` satisfies every WITHHOLD-class constraint on its own."""
    return all(not fn(policy, state, state) for _, fn, cls in CONSTRAINTS if cls == WITHHOLD)
