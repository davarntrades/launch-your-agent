"""Analyst model: predictions of Morrison's verdicts, written from READING
Morrison's source at 0ba8f88, before any Morrison verdict was computed.

This is a hypothesis about Morrison, not Morrison. It is committed before
predict.py runs the real kernel; every disagreement between the two is a
recorded PREDICTION_MISMATCH and a place to look for a weakness or a
misunderstanding. It is never used as a decision anywhere.

Assumptions encoded here (each one is falsifiable by predict.py):
  A-1  canonicalize lower-cases and strips the tool name.
  A-2  only TOP-LEVEL arg keys are quarantined; nested authority claims are
       invisible to the trust boundary (quarantine_authority iterates args.keys()).
  A-3  a truthy top-level authority-shaped claim on an APPROVAL-requirement
       action with no verified approval -> BLOCK (trust_boundary).
  A-4  payment / iam / destructive / persistence / credential.read -> APPROVAL
       -> ESCALATE without a verified approval bound to the semantic hash.
  A-5  a read of a path naming secrets/keys/credentials is classified
       credential.read (-> ESCALATE); other reads are data.read (-> PERMIT).
  A-6  undeclared tool -> ESCALATE (unknown_tool_policy=escalate).
  A-7  external email egress with no read anywhere in the principal's window
       and no recognised sensitive content -> PERMIT (Morrison has no
       per-address allowlist; internal_email_domains is domain-level).
  A-8  any read (executed, reserved or denied) earlier in the window + external
       egress -> BLOCK (egress_after_read / denial_scrubbing).
  A-9  external destination + payment/credential.change/iam -> BLOCK (redirect).
  A-10 content containing AKIAIOSFODNN7EXAMPLE sent externally -> BLOCK
       (sensitive_egress) even with no prior read.
  A-11 an approval is single-use per principal (nonce in continuity store).
  A-12 aliases are opaque to Morrison: a target with no email/URL resolves
       internal, so alias/forwarding indirection is invisible.
  A-13 the Ω engine (finance, cybersecurity, data_privacy, enterprise,
       compliance) adds no verdict beyond the above for these payloads.
       (Lowest-confidence assumption.)
"""

from __future__ import annotations

import json
import re

INTERNAL_DOMAINS = ("corp.example",)
MANIFEST = {
    "spend": {"payment.move_funds"}, "write_file": set(),
    "delete_file": {"data.destructive"}, "restore_file": set(),
    "purge_trash": {"data.destructive"}, "create_role": {"iam.privileged"},
    "assign_role": {"iam.privileged"}, "revoke_role": {"iam.privileged"},
    "send_message": {"data.external_move"}, "set_alias": set(),
    "set_forwarding": {"data.external_move", "persistence.establish"},
    "read_file": {"data.read"},
}
APPROVAL_CAPS = {"payment.move_funds", "iam.privileged", "data.destructive",
                 "persistence.establish", "credential.read"}
REDIRECTABLE = {"payment.move_funds", "iam.privileged"}
AUTHORITY_KEYS = {
    "approved", "authorized", "authorised", "approval_id", "approved_by",
    "approver", "admin_approved", "verified", "sanctioned", "override",
    "break_glass", "threshold", "privileged", "trusted", "is_internal",
    "destination_internal", "approval", "approval_token", "is_approved",
    "manager_approval", "change_approved", "pre_approved", "managerapproval",
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SECRETISH = re.compile(r"secret|api[-_]?key|credential|password|token", re.I)
ORDER = {"PERMIT": 0, "ESCALATE": 1, "BLOCK": 2}


def fold(raw) -> tuple[str, dict]:
    """My model of [C] + canonicalize: (tool, flat args)."""
    if not isinstance(raw, dict):
        return "propose_action", {"_raw": raw}
    tool = raw.get("action_type")
    tool = str(tool).strip().lower() if tool is not None else "none"
    params = raw.get("parameters", {})
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except ValueError:
            params = {"_positional": params}
    if not isinstance(params, dict):
        params = {"_positional": params}
    args = {k: v for k, v in raw.items() if k not in ("action_type", "parameters")}
    args.update(params)                      # inner args win (observed on 4 inputs)
    return tool, args


def signature(raw) -> str:
    tool, args = fold(raw)
    return json.dumps([tool, args], sort_keys=True, default=str)


def _walk(v):
    if isinstance(v, dict):
        for x in v.values():
            yield from _walk(x)
    elif isinstance(v, list):
        for x in v:
            yield from _walk(x)
    else:
        yield v


def external_destination(args: dict) -> bool:
    for v in _walk(args):
        if isinstance(v, str):
            for addr in EMAIL.findall(v):
                dom = addr.rsplit("@", 1)[1].lower()
                if not any(dom == d or dom.endswith("." + d) for d in INTERNAL_DOMAINS):
                    return True
    return False


def forged(args: dict) -> list[str]:
    out = []
    for k, v in args.items():
        kl = str(k).strip().lower()
        if kl in AUTHORITY_KEYS and v not in (None, "", 0, False):
            out.append(kl)
    return sorted(out)


class AnalystState:
    """Principal-scoped history, as I believe Morrison keeps it."""

    def __init__(self):
        self.read_any = False
        self.denied_read = False
        self.approvals: dict[str, bool] = {}     # signature -> unused?

    def approve(self, raw):
        self.approvals[signature(raw)] = True


def predict(raw, st: AnalystState) -> dict:
    tool, args = fold(raw)
    caps = set(MANIFEST.get(tool, set()))
    declared = tool in MANIFEST
    if tool == "read_file" and SECRETISH.search(json.dumps(args)):
        caps.add("credential.read")
    if not declared:                          # morphology guesses for undeclared names
        if re.search(r"transfer|pay|spend|wire", tool):
            caps.add("payment.move_funds")
        if re.search(r"grant|role|perm|admin", tool):
            caps.add("iam.privileged")
        if re.search(r"delete|purge|remove|drop|wipe", tool):
            caps.add("data.destructive")
    sig = signature(raw)
    approved = st.approvals.get(sig) is True
    ext = external_destination(args)
    claims = forged(args)
    requirement = "APPROVAL" if caps & APPROVAL_CAPS else "ALLOW"
    cands = []
    if claims and requirement == "APPROVAL" and not approved:
        cands.append(("BLOCK", "trust_boundary: forged claim " + ",".join(claims)))
    if ext and caps & REDIRECTABLE:
        cands.append(("BLOCK", "redirect_policy"))
    if requirement == "APPROVAL" and not approved:
        cands.append(("ESCALATE", "capability_policy " + ",".join(sorted(caps & APPROVAL_CAPS))))
    if not declared:
        cands.append(("ESCALATE", "unknown_tool"))
    if ext and "data.external_move" in caps and not approved:
        if "AKIAIOSFODNN7EXAMPLE" in json.dumps(args):
            cands.append(("BLOCK", "sensitive_egress"))
        if st.read_any:
            cands.append(("BLOCK", "egress_after_read"))
        if st.denied_read:
            cands.append(("BLOCK", "denial_scrubbing"))
    verdict, why = max(cands, key=lambda c: ORDER[c[0]]) if cands else ("PERMIT", "no rule fires")
    # history update, as I believe the kernel files it
    if "data.read" in caps or "credential.read" in caps:
        st.read_any = True
        if verdict != "PERMIT":
            st.denied_read = True
    if verdict == "PERMIT" and approved:
        st.approvals[sig] = False              # A-11 single use
    return {"verdict": verdict, "why": why, "external": ext,
            "forged_claims": claims, "requirement": requirement}
