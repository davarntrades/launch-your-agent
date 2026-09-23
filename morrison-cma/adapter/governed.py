"""Operator-side runtime: [C] unwrap -> Morrison authorize -> lease -> [E].

Morrison (GovernanceKernel) is the only decision authority. This module only
builds Morrison's inputs from config/deployment.json and carries its outputs:

  * PERMIT   -> kernel.mint_lease -> kernel.execute(decision, executor) where
                the executor hands the lease and the exact authorised action to
                [E]. [E] verifies the lease independently.
  * ESCALATE -> nothing executes. Scripted operator approvals (if the scenario
                has one) are issued with Morrison's own `issue_approval`.
  * BLOCK    -> nothing executes.
  * an exception from Morrison -> GOVERNANCE_EXCEPTION. Never counted as BLOCK.

Every outcome is returned as a plain record; nothing here interprets it.
"""

from __future__ import annotations

import json
import os
import secrets
import traceback
import uuid

from morrison_governance import GovernanceLayer, OmegaDomain
from morrison_governance.kernel import (
    GovernanceKernel, InMemoryContinuityStore, Principal, SecurityContext,
    issue_approval,
)

from morrison_governance.kernel.canonical import canonicalize

from .unwrap import unwrap

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.normpath(os.path.join(HERE, "..", "config", "deployment.json"))


def load_config(path: str = CONFIG) -> dict:
    with open(path) as fh:
        return json.load(fh)


class Keys:
    """Per-campaign secrets. Held by the operator process only."""

    def __init__(self):
        self.approval = secrets.token_bytes(32)
        self.lease = secrets.token_bytes(32)
        self.evidence = secrets.token_bytes(32)


def build_layer(cfg: dict) -> GovernanceLayer:
    g = cfg["governance_layer"]
    return GovernanceLayer(
        domains=[OmegaDomain(d) for d in g["domains"]], log_all=g["log_all"],
        internal_email_domains=tuple(g["internal_email_domains"]),
        internal_url_hosts=tuple(g["internal_url_hosts"]))


def build_context(cfg: dict, keys: Keys, principal_id: str, store=None,
                  approvals: tuple = ()) -> SecurityContext:
    s = cfg["security_context"]
    p = s["principal"]
    return SecurityContext(
        principal=Principal(id=principal_id, tenant=p["tenant"],
                            roles=frozenset(p["roles"]),
                            granted_capabilities=frozenset(p["granted_capabilities"])),
        approvals=tuple(approvals),
        trusted_facts=dict(s["trusted_facts"]),
        signing_key=keys.approval,
        trusted_issuers=frozenset(s["trusted_issuers"]),
        internal_url_hosts=tuple(s["internal_url_hosts"]),
        internal_email_domains=tuple(s["internal_email_domains"]),
        internal_cidrs=tuple(s["internal_cidrs"]),
        unknown_tool_policy=s["unknown_tool_policy"],
        tool_manifest={k: list(v) for k, v in s["tool_manifest"].items()},
        policy_values=dict(s["policy_values"]),
        continuity_store=store if store is not None else InMemoryContinuityStore(),
        continuity_window_s=s["continuity_window_s"],
        lease_signing_key=keys.lease,
        max_outstanding_reservations=s["max_outstanding_reservations"],
        continuity_policy=s["continuity_policy"],
        trust_private_networks=s["trust_private_networks"],
    )


class GovernedSession:
    """One CMA session's worth of governance for one principal."""

    def __init__(self, cfg: dict, keys: Keys, principal_id: str, store,
                 surface, session_id: str | None = None, layer=None):
        self.cfg, self.keys, self.surface = cfg, keys, surface
        self.principal_id, self.store = principal_id, store
        self.layer = layer or build_layer(cfg)
        self.approvals: list = []
        self.session_id = session_id or uuid.uuid4().hex
        self.kernel = self._new_kernel()

    def _new_kernel(self) -> GovernanceKernel:
        ctx = build_context(self.cfg, self.keys, self.principal_id, self.store,
                            tuple(self.approvals))
        return GovernanceKernel(self.layer, ctx, evidence_key=self.keys.evidence,
                                session_id=self.session_id,
                                decision_ttl_s=self.cfg["decision_ttl_s"])

    # operator actions -----------------------------------------------------
    def operator_approve(self, raw_proposal, nonce: str | None = None) -> dict:
        """Issue a Morrison ApprovalArtifact for exactly this proposal.

        Approvals live in SecurityContext, which Morrison reads at authorise
        time; the context is rebuilt with the new approval appended. The
        kernel's session id and store are unchanged, so history carries over.
        """
        # harness v0.1 (H-1): approve the CANONICAL call, which is what
        # GovernanceKernel.authorize hashes; issue_approval does not
        # canonicalise its input itself.
        call = canonicalize(unwrap(raw_proposal)[0])
        art = issue_approval(call, issuer="operator", key=self.keys.approval,
                             nonce=nonce or uuid.uuid4().hex)
        self.approvals.append(art)
        chain = self.kernel.chain
        self.kernel = self._new_kernel()
        self.kernel.chain = chain              # one evidence chain per session
        return {"approved_semantic_hash": art.action_hash, "nonce": art.nonce}

    # the governed path ----------------------------------------------------
    def authorize(self, raw) -> tuple[object, dict]:
        call, meta = unwrap(raw)
        rec = {"raw": raw, "call": call, "unwrap": meta}
        try:
            d = self.kernel.authorize(call)
        except Exception as exc:                          # noqa: BLE001
            rec.update(verdict="GOVERNANCE_EXCEPTION",
                       exception=f"{type(exc).__name__}: {exc}",
                       traceback=traceback.format_exc(limit=4))
            return None, rec
        rec.update(verdict=d.verdict, layer=d.layer, rule=d.rule, reason=d.reason,
                   capabilities=sorted(d.capabilities), requirement=d.requirement,
                   forged_claims=list(d.forged_claims), tool_family=d.tool_family,
                   action_hash=d.action_hash, semantic_hash=d.semantic_hash,
                   decision_id=d.decision_id,
                   evidence_hash=d.evidence.record_hash if d.evidence else None)
        return d, rec

    def execute(self, d, rec: dict) -> dict:
        """Execute a PERMIT through Morrison and [E]. Fills rec['execution']."""
        if d is None or rec.get("verdict") != "PERMIT":
            rec["execution"] = {"status": "NOT_EXECUTED"}
            return rec
        try:
            lease = self.kernel.mint_lease(d, ttl_s=self.cfg["lease_ttl_s"])
        except Exception as exc:                          # noqa: BLE001
            rec["execution"] = {"status": "LEASE_MINT_EXCEPTION",
                                "reason": f"{type(exc).__name__}: {exc}"}
            return rec
        token = lease.encode()
        surface_rec = {}

        def executor(target):
            surface_rec.update(self.surface.submit(token, target))
            if surface_rec.get("status") != "APPLIED":
                raise RuntimeError(f"[E] {surface_rec.get('status')}: {surface_rec.get('reason')}")
            return surface_rec.get("observation")

        try:
            ok, out = self.kernel.execute(d, executor)
        except Exception as exc:                          # noqa: BLE001
            rec["execution"] = {"status": "EXECUTE_EXCEPTION",
                                "reason": f"{type(exc).__name__}: {exc}"}
            return rec
        rec["lease_token"] = token
        rec["execution"] = {"kernel_ok": ok, "kernel_out": out if not ok else None,
                            "surface": surface_rec or None,
                            "status": ("EXECUTED" if ok else
                                       "SURFACE_" + surface_rec.get("status", "NOT_REACHED")
                                       if surface_rec else "KERNEL_REFUSED")}
        return rec
