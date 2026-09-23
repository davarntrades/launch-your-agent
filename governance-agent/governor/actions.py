"""Proposal schema and transition functions.

A proposal is a dict:
    {"id": str, "action_type": str, "target": str, "parameters": {...}}

Each transition takes a state and a proposal and mutates *that* state in
place. Callers pass a clone when simulating. A transition that is undefined
for the given state (missing file, unknown role, bad parameter) raises
TransitionError; the Governor maps that to WITHHOLD.
"""

from .state import resolve_recipients


class TransitionError(Exception):
    pass


def _require(params, key, typ):
    if key not in params:
        raise TransitionError(f"missing parameter '{key}'")
    if not isinstance(params[key], typ) or isinstance(params[key], bool) and typ is int:
        raise TransitionError(f"parameter '{key}' must be {typ.__name__}")
    return params[key]


def _spend(s, target, p):
    amount = _require(p, "amount_cents", int)
    if amount <= 0:
        raise TransitionError("amount_cents must be > 0")
    s["budget"]["spent_cents"] += amount
    s["budget"]["ledger"].append({"payee": target, "amount_cents": amount, "memo": p.get("memo", "")})


def _write_file(s, target, p):
    content = _require(p, "content", str)
    rec = s["files"].get(target)
    if rec is None:
        s["files"][target] = {"content": content, "history": []}
    else:
        rec["history"].append(rec["content"])
        rec["content"] = content


def _delete_file(s, target, p):
    mode = p.get("mode", "trash")
    if target not in s["files"]:
        raise TransitionError(f"no file at {target}")
    rec = s["files"].pop(target)
    if mode == "trash":
        s["trash"][target] = rec
    elif mode != "permanent":
        raise TransitionError("mode must be 'trash' or 'permanent'")


def _restore_file(s, target, p):
    if target not in s["trash"]:
        raise TransitionError(f"no trashed file at {target}")
    if target in s["files"]:
        raise TransitionError(f"live file already exists at {target}")
    s["files"][target] = s["trash"].pop(target)


def _purge_trash(s, target, p):
    if target == "*":
        s["trash"].clear()
    elif target in s["trash"]:
        del s["trash"][target]
    else:
        raise TransitionError(f"no trashed file at {target}")


def _create_role(s, target, p):
    perms = _require(p, "permissions", list)
    if target in s["roles"]:
        raise TransitionError(f"role {target} already exists")
    s["roles"][target] = sorted({str(x) for x in perms})


def _assign_role(s, target, p):
    role = _require(p, "role", str)
    if role not in s["roles"]:
        raise TransitionError(f"no role {role}")
    roles = s["principals"].setdefault(target, {"roles": []})["roles"]
    if role not in roles:
        roles.append(role)


def _revoke_role(s, target, p):
    role = _require(p, "role", str)
    roles = s["principals"].get(target, {}).get("roles", [])
    if role not in roles:
        raise TransitionError(f"{target} does not hold role {role}")
    roles.remove(role)


def _send_message(s, target, p):
    subject = _require(p, "subject", str)
    body = _require(p, "body", str)
    s["outbox"].append({
        "to": target,
        "delivered_to": sorted(resolve_recipients(s, target)),
        "subject": subject,
        "body": body,
    })


def _set_alias(s, target, p):
    members = _require(p, "members", list)
    s["aliases"][target] = [str(m) for m in members]


def _set_forwarding(s, target, p):
    s["forwarding"][target] = _require(p, "forward_to", str)


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

# JSON Schema for the Worker's propose_action tool (kept in sync with TRANSITIONS).
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
}


def apply(state, proposal):
    """Apply a proposal to `state` in place. Raises TransitionError."""
    if not isinstance(proposal, dict):
        raise TransitionError("proposal must be an object")
    fn = TRANSITIONS.get(proposal.get("action_type"))
    if fn is None:
        raise TransitionError(f"unknown action_type {proposal.get('action_type')!r}")
    target = proposal.get("target")
    params = proposal.get("parameters", {})
    if not isinstance(target, str) or not target:
        raise TransitionError("target must be a non-empty string")
    if not isinstance(params, dict):
        raise TransitionError("parameters must be an object")
    fn(state, target, params)
