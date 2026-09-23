"""Constraint predicates that define the admissible set.

Each constraint is a pure function (before, after) -> list of violation
reasons (empty list = satisfied). `after` is the simulated state. Each
constraint carries the verdict class it produces when violated:

    WITHHOLD  - the resulting state is outside the admissible set
    ESCALATE  - the resulting state is admissible only with a recorded approval
"""

from .state import effective_permissions, recoverable_content

WITHHOLD = "WITHHOLD"
ESCALATE = "ESCALATE"


def spend_ceiling(before, after):
    b = after["budget"]
    if b["spent_cents"] > b["ceiling_cents"]:
        return [f"spent {b['spent_cents']} > ceiling {b['ceiling_cents']} cents"]
    return []


def no_irreversible_delete(before, after):
    lost = recoverable_content(before) - recoverable_content(after)
    return [f"{path} (content {h}) is no longer recoverable" for path, h in sorted(lost)]


def no_permission_widening(before, after):
    baseline = after["baseline_permissions"]
    reasons = []
    for principal in sorted(after["principals"]):
        extra = effective_permissions(after, principal) - set(baseline.get(principal, []))
        if extra:
            reasons.append(f"{principal} gains {sorted(extra)} beyond baseline {baseline.get(principal, [])}")
    return reasons


def recipient_allowlist(before, after):
    allowed = set(after["recipient_allowlist"])
    reasons = []
    for i, msg in enumerate(after["outbox"]):
        unlisted = sorted(set(msg["delivered_to"]) - allowed)
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
