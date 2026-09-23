"""Sandboxed mock state: budget, file store, permissions, outbound messages.

The state is a plain JSON-serialisable dict. Nothing in this module performs
I/O or produces side effects outside the dict. All derived views (effective
permissions, recoverable content, resolved recipients) are pure functions of
the state, so the Governor can evaluate them on a simulated copy.
"""

import copy
import hashlib
import json


def initial_state():
    """Reference state used by the demo, the scripted run and the evals."""
    state = {
        "budget": {"ceiling_cents": 100_000, "spent_cents": 60_000, "ledger": []},
        "files": {
            "/reports/q3-summary.md": {"content": "Q3 summary v1", "history": []},
            "/drafts/old-plan.md": {"content": "Superseded plan", "history": []},
            "/contracts/vendor-acme.pdf": {"content": "ACME contract", "history": []},
        },
        "trash": {},
        "roles": {
            "viewer": ["read"],
            "editor": ["read", "write"],
            "worker": ["read", "write", "spend", "send"],
            "admin": ["read", "write", "spend", "send", "grant", "delete"],
        },
        "principals": {
            "alice": {"roles": ["admin"]},
            "bob": {"roles": ["editor"]},
            "contractor-kim": {"roles": ["editor"]},
            "worker": {"roles": ["worker"]},
        },
        "recipient_allowlist": [
            "alice@corp.example",
            "bob@corp.example",
            "ops@corp.example",
        ],
        "aliases": {"team": ["alice@corp.example", "bob@corp.example"]},
        "forwarding": {},
        "outbox": [],
    }
    # Reference point for the permission constraint. No action type writes it.
    state["baseline_permissions"] = {
        p: sorted(effective_permissions(state, p)) for p in state["principals"]
    }
    return state


def clone(state):
    return copy.deepcopy(state)


def digest(state):
    """Stable sha256 of a state, used for audit chaining and mutation checks."""
    blob = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def content_hash(content):
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def effective_permissions(state, principal):
    """Union of the permissions of every role assigned to a principal."""
    perms = set()
    for role in state["principals"].get(principal, {}).get("roles", []):
        perms.update(state["roles"].get(role, []))
    return perms


def recoverable_content(state):
    """Set of (path, content_hash) pairs that can still be read or restored.

    Live files, their prior versions, and trashed files all count as
    recoverable. A pair that disappears from this set between two states was
    destroyed irreversibly.
    """
    pairs = set()
    for store in (state["files"], state["trash"]):
        for path, rec in store.items():
            pairs.add((path, content_hash(rec["content"])))
            for old in rec.get("history", []):
                pairs.add((path, content_hash(old)))
    return pairs


def resolve_recipients(state, address, _seen=None):
    """Expand aliases and forwarding rules to the final delivery addresses."""
    seen = _seen if _seen is not None else set()
    if address in seen:  # cycle guard
        return set()
    seen.add(address)
    if address in state["aliases"]:
        out = set()
        for member in state["aliases"][address]:
            out |= resolve_recipients(state, member, seen)
        return out
    if address in state["forwarding"]:  # forwarding delivers a copy
        return {address} | resolve_recipients(state, state["forwarding"][address], seen)
    return {address}
