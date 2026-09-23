"""Adapter [C]: CMA `propose_action` input -> Morrison call.

The whole adapter is one rule, chosen so that the adapter makes no
representation decisions of its own:

    raw = the `input` object of an agent.custom_tool_use event, as parsed JSON
    call = {"tool": raw["action_type"], "args": raw["parameters"],
            **every other top-level key of raw (including "target")}

Morrison's own `canonicalize` then folds the extra top-level keys into `args`
and resolves any collision by its own rule. The adapter:

  * never drops, renames, coerces, validates or reorders a field;
  * never strips authority-shaped claims, at any depth;
  * never refuses. A raw input it cannot map (not a JSON object) is still
    handed to Morrison in the most literal form available, and whatever
    Morrison does with it is the result.

Anything that looks like input validation belongs to Morrison (decision) or to
the execution surface [E] (defined transitions), never here.
"""

from __future__ import annotations

import copy

_MISSING = object()


def unwrap(raw) -> tuple[dict, dict]:
    """Return (call, meta). `meta` records how the raw input was shaped."""
    meta = {"raw_type": type(raw).__name__}
    if not isinstance(raw, dict):
        meta["shape"] = "non_object"
        return {"tool": "propose_action", "args": {"_raw": copy.deepcopy(raw)}}, meta
    raw = copy.deepcopy(raw)
    tool = raw.pop("action_type", _MISSING)
    args = raw.pop("parameters", _MISSING)
    meta["shape"] = "object"
    meta["action_type_present"] = tool is not _MISSING
    meta["parameters_present"] = args is not _MISSING
    meta["parameters_type"] = type(args).__name__ if args is not _MISSING else None
    meta["extra_top_level_keys"] = sorted(k for k in raw if k != "target")
    call = {"tool": None if tool is _MISSING else tool,
            "args": {} if args is _MISSING else args}
    call.update(raw)                         # "target" and any extra keys
    return call, meta
