"""Proposal schema, normalisation, transition functions and write footprints.

A proposal is a JSON object:
    {"id": str, "action_type": str, "target": str, "parameters": {...}}

`normalize()` turns any input into a fresh, JSON-only proposal with exactly
the declared keys and types, or raises TransitionError. The returned object
shares no references with the caller's input.

Each transition mutates the state it is given (the Governor passes a clone).
FOOTPRINT lists the top-level state keys a transition may write; the
Governor rejects a simulated result that changed anything else.
"""

import json

from .state import resolve_recipients


class TransitionError(Exception):
    pass


# action_type -> {param: (type, required)}
PARAMS = {
    "spend": {"amount_cents": (int, True), "memo": (str, False)},
    "write_file": {"content": (str, True)},
    "delete_file": {"mode": (str, False)},
    "restore_file": {},
    "purge_trash": {},
    "create_role": {"permissions": (list, True)},
    "assign_role": {"role": (str, True)},
    "revoke_role": {"role": (str, True)},
    "send_message": {"subject": (str, True), "body": (str, True)},
    "set_alias": {"members": (list, True)},
    "set_forwarding": {"forward_to": (str, True)},
}

FOOTPRINT = {
    "spend": {"budget"},
    "write_file": {"files"},
    "delete_file": {"files", "trash"},
    "restore_file": {"files", "trash"},
    "purge_trash": {"trash"},
    "create_role": {"roles"},
    "assign_role": {"principals"},
    "revoke_role": {"principals"},
    "send_message": {"outbox"},
    "set_alias": {"aliases"},
    "set_forwarding": {"forwarding"},
}

PROPOSAL_KEYS = {"id", "action_type", "target", "parameters"}
MAX_STR = 10_000


def _check_str(value, name):
    if not isinstance(value, str) or not value or len(value) > MAX_STR:
        raise TransitionError(f"{name} must be a non-empty string of at most {MAX_STR} chars")


def normalize(raw):
    """Return a detached, schema-exact copy of a proposal or raise TransitionError."""
    try:
        proposal = json.loads(json.dumps(raw))  # JSON-only, no shared references
    except (TypeError, ValueError) as exc:
        raise TransitionError(f"proposal is not JSON-serialisable: {exc}")
    if not isinstance(proposal, dict):
        raise TransitionError("proposal must be an object")
    extra = set(proposal) - PROPOSAL_KEYS
    if extra:
        raise TransitionError(f"unexpected proposal keys {sorted(extra)}")
    action = proposal.get("action_type")
    if action not in PARAMS:
        raise TransitionError(f"unknown action_type {action!r}")
    _check_str(proposal.get("target"), "target")
    params = proposal.get("parameters", {})
    if not isinstance(params, dict):
        raise TransitionError("parameters must be an object")
    spec = PARAMS[action]
    extra = set(params) - set(spec)
    if extra:
        raise TransitionError(f"unexpected parameters {sorted(extra)} for {action}")
    for name, (typ, required) in spec.items():
        if name not in params:
            if required:
                raise TransitionError(f"missing parameter '{name}'")
            continue
        value = params[name]
        if typ is int and (isinstance(value, bool) or not isinstance(value, int)):
            raise TransitionError(f"parameter '{name}' must be an integer")
        if typ is str:
            _check_str(value, f"parameter '{name}'")
        if typ is list:
            if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
                raise TransitionError(f"parameter '{name}' must be a non-empty list of strings")
    proposal["parameters"] = params
    return proposal


def _spend(s, target, p):
    amount = p["amount_cents"]
    if amount <= 0:
        raise TransitionError("amount_cents must be > 0")
    s["budget"]["spent_cents"] += amount
    s["budget"]["ledger"].append({"payee": target, "amount_cents": amount, "memo": p.get("memo", "")})


def _write_file(s, target, p):
    rec = s["files"].get(target)
    if rec is None:
        s["files"][target] = {"content": p["content"], "history": []}
    else:
        rec["history"].append(rec["content"])
        rec["content"] = p["content"]


def _delete_file(s, target, p):
    mode = p.get("mode", "trash")
    if mode not in ("trash", "permanent"):
        raise TransitionError("mode must be 'trash' or 'permanent'")
    if target not in s["files"]:
        raise TransitionError(f"no file at {target}")
    if mode == "trash" and target in s["trash"]:
        raise TransitionError(f"trash already holds {target}")
    rec = s["files"].pop(target)
    if mode == "trash":
        s["trash"][target] = rec


def _restore_file(s, target, p):
    if target not in s["trash"]:
        raise TransitionError(f"no trashed file at {target}")
    if target in s["files"]:
        raise TransitionError(f"live file already exists at {target}")
    s["files"][target] = s["trash"].pop(target)


def _purge_trash(s, target, p):
    if target == "*":
        if not s["trash"]:
            raise TransitionError("trash is empty")
        s["trash"].clear()
    elif target in s["trash"]:
        del s["trash"][target]
    else:
        raise TransitionError(f"no trashed file at {target}")


def _create_role(s, target, p):
    if target in s["roles"]:
        raise TransitionError(f"role {target} already exists")
    s["roles"][target] = sorted(set(p["permissions"]))


def _assign_role(s, target, p):
    role = p["role"]
    if role not in s["roles"]:
        raise TransitionError(f"no role {role}")
    roles = s["principals"].setdefault(target, {"roles": []})["roles"]
    if role in roles:
        raise TransitionError(f"{target} already holds role {role}")
    roles.append(role)


def _revoke_role(s, target, p):
    roles = s["principals"].get(target, {}).get("roles", [])
    if p["role"] not in roles:
        raise TransitionError(f"{target} does not hold role {p['role']}")
    roles.remove(p["role"])


def _send_message(s, target, p):
    delivered = sorted(resolve_recipients(s, target))
    if not delivered:
        raise TransitionError(f"{target!r} resolves to no recipients")
    s["outbox"].append({"to": target, "delivered_to": delivered, "subject": p["subject"], "body": p["body"]})


def _set_alias(s, target, p):
    s["aliases"][target] = list(p["members"])


def _set_forwarding(s, target, p):
    s["forwarding"][target] = p["forward_to"]


TRANSITIONS = {
    "spend": _spend,
    "write_file": _write_file,
    "delete_file": _delete_file,
    "restore_file": _restore_file,
    "purge_trash": _purge_trash,
    "create_role": _create_role,
    "assign_role": _assign_role,
    "revoke_role": _revoke_role,
    "send_message": _send_message,
    "set_alias": _set_alias,
    "set_forwarding": _set_forwarding,
}
assert set(TRANSITIONS) == set(PARAMS) == set(FOOTPRINT)

# JSON Schema for the Worker's propose_action tool (kept in sync with PARAMS).
PROPOSAL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action_type": {"type": "string", "enum": sorted(TRANSITIONS)},
        "target": {
            "type": "string",
            "description": "payee (spend), file path (write/delete/restore/purge; '*' purges all trash), "
                           "role name (create_role), principal (assign/revoke_role), "
                           "address or alias (send_message, set_alias, set_forwarding)",
        },
        "parameters": {
            "type": "object",
            "description": "spend: {amount_cents:int, memo?}; write_file: {content}; delete_file: {mode:'trash'|'permanent'}; "
                           "create_role: {permissions:[str]}; assign_role/revoke_role: {role}; "
                           "send_message: {subject, body}; set_alias: {members:[str]}; set_forwarding: {forward_to}; "
                           "restore_file/purge_trash: {}",
        },
    },
    "required": ["action_type", "target", "parameters"],
    "additionalProperties": False,
}


def apply(state, proposal):
    """Apply a normalised proposal to `state` in place. Raises TransitionError."""
    TRANSITIONS[proposal["action_type"]](state, proposal["target"], proposal["parameters"])
