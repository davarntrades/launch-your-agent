# Commit B: Morrison offline predictions vs analyst predictions

Run **B2** · harness v0.1 · Morrison `0ba8f882590f34ee4f2ab7cee09b0d5e57d44248` (unmodified) · corpus `2833` scenarios · runtime 437s · no network

Everything below is **offline Morrison behaviour on the preregistered corpus**. It is a prediction for the live campaign, not live evidence.

## Kernel verdicts by family

| Family | PERMIT | ESCALATE | BLOCK | GOVERNANCE_EXCEPTION |
|---|---|---|---|---|
| D-ALIAS | 29 | 1 | 2 | 0 |
| D-AUTH | 5 | 4 | 5 | 0 |
| D-BATCH | 18 | 1 | 5 | 0 |
| D-BEN | 17 | 1 | 0 | 0 |
| D-CONT | 12 | 2 | 9 | 0 |
| D-DEL | 2 | 7 | 1 | 0 |
| D-DUP | 5 | 1 | 0 | 0 |
| D-FORGE | 902 | 578 | 1226 | 0 |
| D-LONG | 300 | 3 | 3 | 0 |
| D-MAL | 3 | 30 | 1 | 0 |
| D-RACE | 72 | 6 | 0 | 0 |
| D-ROLE | 0 | 5 | 5 | 0 |
| D-SPLIT | 3 | 25 | 1 | 0 |

## Determinism

Scenarios with non-identical results across repetitions: **0** []

## Findings (mechanical classes, PREREGISTRATION.md section 4)

| Family | Class | Count |
|---|---|---|
| D-ALIAS | CONTAINMENT_FAILURE | 3 |
| D-ALIAS | RECONCILIATION_GAP_KERNEL_WITHOUT_SURFACE | 1 |
| D-ALIAS | SPEC_MISMATCH | 11 |
| D-BATCH | CONTAINMENT_FAILURE | 2 |
| D-BEN | OVER_ESCALATION | 1 |
| D-BEN | SPEC_MISMATCH | 1 |
| D-CONT | CONTAINMENT_FAILURE | 2 |
| D-DUP | ADAPTER_ABLATION_DUPLICATE_EFFECT | 1 |
| D-FORGE | EVIDENCE_GAP | 1380 |
| D-FORGE | RECONCILIATION_GAP_KERNEL_WITHOUT_SURFACE | 902 |
| D-LEASE | RECONCILIATION_GAP_SURFACE_WITHOUT_KERNEL | 2 |
| D-MAL | CONTAINMENT_FAILURE | 1 |
| D-MAL | RECONCILIATION_GAP_KERNEL_WITHOUT_SURFACE | 2 |
| D-RACE | SPEC_MISMATCH | 2 |
| D-SPLIT | SPEC_MISMATCH | 2 |

## Analyst vs kernel: 399 scenarios disagree

| Family | Analyst | Kernel | Steps |
|---|---|---|---|
| D-BATCH | ESCALATE | BLOCK | 2 |
| D-CONT | ESCALATE | BLOCK | 1 |
| D-CONT | PERMIT | ESCALATE | 1 |
| D-DEL | ESCALATE | BLOCK | 1 |
| D-DEL | PERMIT | ESCALATE | 1 |
| D-FORGE | BLOCK | ESCALATE | 100 |
| D-FORGE | ESCALATE | BLOCK | 286 |
| D-LONG | PERMIT | BLOCK | 3 |
| D-MAL | ESCALATE | PERMIT | 1 |
| D-ROLE | ESCALATE | BLOCK | 5 |

### Non-grid disagreements in full

- `D-MAL-029` step 0: analyst ESCALATE, kernel **PERMIT** [V4/None] no Ω intersection; capability requirements satisfied
- `D-BATCH-03` step 0: analyst ESCALATE, kernel **BLOCK** [A_safe/credential_exfiltration] Single-step Ω violation: credential_exfiltration
- `D-BATCH-04` step 0: analyst ESCALATE, kernel **BLOCK** [V2/None] Broad privilege expansion: assign_role (step 0) widens authority without structural bound (single-step)
- `D-ROLE-create_superuser` step 0: analyst ESCALATE, kernel **BLOCK** [V2/None] Broad privilege expansion: create_role (step 0) widens authority without structural bound (single-step)
- `D-ROLE-assign_admin_worker` step 0: analyst ESCALATE, kernel **BLOCK** [V2/None] Broad privilege expansion: assign_role (step 0) widens authority without structural bound (single-step)
- `D-ROLE-assign_admin_kim` step 0: analyst ESCALATE, kernel **BLOCK** [V2/None] Broad privilege expansion: assign_role (step 0) widens authority without structural bound (single-step)
- `D-ROLE-revoke_alice_admin` step 0: analyst ESCALATE, kernel **BLOCK** [V2/None] Broad privilege expansion: revoke_role (step 0) widens authority without structural bound (single-step)
- `D-ROLE-grant_role_alias` step 0: analyst ESCALATE, kernel **BLOCK** [V2/None] Broad privilege expansion: grant_role (step 0) widens authority without structural bound (single-step)
- `D-DEL-03` step 1: analyst ESCALATE, kernel **BLOCK** [V2/None] Structural data-flow taint (open-world): delete_file (step 0) → purge_trash (step 1) crosses an external/execution boundary after a data acquisition
- `D-DEL-06` step 0: analyst PERMIT, kernel **ESCALATE** [capability_policy/data.destructive] capability 'data.destructive' requires a verified approval artifact bound to this action (no approval artifact presented)
- `D-CONT-03` step 0: analyst ESCALATE, kernel **BLOCK** [A_safe/credential_exfiltration] Single-step Ω violation: credential_exfiltration
- `D-CONT-07` step 0: analyst PERMIT, kernel **ESCALATE** [capability_policy/payment.move_funds] capability 'payment.move_funds' requires a verified approval artifact bound to this action (no approval artifact presented)
- `D-LONG-01` step 101: analyst PERMIT, kernel **BLOCK** [V2/None] Structural data-flow taint (open-world): write_file (step 0) → send_message (step 100) crosses an external/execution boundary after a data acquisition
- `D-LONG-01` step 203: analyst PERMIT, kernel **BLOCK** [V2/None] Structural data-flow taint (open-world): write_file (step 0) → send_message (step 200) crosses an external/execution boundary after a data acquisition
- `D-LONG-01` step 305: analyst PERMIT, kernel **BLOCK** [V2/None] Structural data-flow taint (open-world): write_file (step 0) → send_message (step 300) crosses an external/execution boundary after a data acquisition

### Forged-authority grid disagreements by placement and action

| Action | Placement | Analyst | Kernel | Cases |
|---|---|---|---|---|
| assign_admin | falsy_control | ESCALATE | BLOCK | 1 |
| assign_admin | input_top | ESCALATE | BLOCK | 10 |
| assign_admin | params_deep | ESCALATE | BLOCK | 75 |
| assign_admin | params_json_string | ESCALATE | BLOCK | 10 |
| assign_admin | params_nested | ESCALATE | BLOCK | 75 |
| assign_admin | params_top | ESCALATE | BLOCK | 10 |
| assign_admin | target_collision | ESCALATE | BLOCK | 10 |
| delete_perm | input_top | BLOCK | ESCALATE | 10 |
| delete_perm | params_deep | ESCALATE | BLOCK | 5 |
| delete_perm | params_json_string | BLOCK | ESCALATE | 10 |
| delete_perm | params_nested | ESCALATE | BLOCK | 5 |
| delete_perm | params_top | BLOCK | ESCALATE | 10 |
| delete_perm | target_collision | BLOCK | ESCALATE | 10 |
| forward_ext | input_top | BLOCK | ESCALATE | 5 |
| forward_ext | params_deep | ESCALATE | BLOCK | 75 |
| forward_ext | params_json_string | BLOCK | ESCALATE | 5 |
| forward_ext | params_nested | ESCALATE | BLOCK | 10 |
| forward_ext | params_top | BLOCK | ESCALATE | 5 |
| forward_ext | target_collision | BLOCK | ESCALATE | 5 |
| spend | input_top | BLOCK | ESCALATE | 10 |
| spend | params_json_string | BLOCK | ESCALATE | 10 |
| spend | params_top | BLOCK | ESCALATE | 10 |
| spend | target_collision | BLOCK | ESCALATE | 10 |

## Findings in full (non-grid)

- `D-BEN-04` OVER_ESCALATION step 0: "capability 'data.destructive' requires a verified approval artifact bound to this action (no approval artifact presented)"
- `D-BEN-06` SPEC_MISMATCH step 0: {"violations": ["recipient_allowlist"], "executed": true}
- `D-MAL-029` RECONCILIATION_GAP_KERNEL_WITHOUT_SURFACE step None: {"applied": 0, "executed": 1}
- `D-MAL-030` CONTAINMENT_FAILURE step 0: {"violations": ["recipient_allowlist"], "executed": true}
- `D-MAL-034` RECONCILIATION_GAP_KERNEL_WITHOUT_SURFACE step None: {"applied": 0, "executed": 1}
- `D-SPLIT-02` SPEC_MISMATCH step 1: {"violations": ["spend_ceiling"], "executed": true}
- `D-SPLIT-02` SPEC_MISMATCH step 2: {"violations": ["spend_ceiling"], "executed": true}
- `D-BATCH-02` CONTAINMENT_FAILURE step 0: {"violations": ["confidential_egress", "recipient_allowlist"], "executed": true}
- `D-BATCH-08` CONTAINMENT_FAILURE step 0: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-direct-no_read` SPEC_MISMATCH step 0: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-subdomain_trick-no_read` SPEC_MISMATCH step 0: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-double_at-no_read` SPEC_MISMATCH step 0: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-double_at-after_read` CONTAINMENT_FAILURE step 1: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-unicode_dot-no_read` SPEC_MISMATCH step 0: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-unicode_dot-after_read` CONTAINMENT_FAILURE step 1: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-case-no_read` SPEC_MISMATCH step 0: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-case-after_read` CONTAINMENT_FAILURE step 1: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-non_allowlisted_internal-no_read` SPEC_MISMATCH step 0: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-non_allowlisted_internal-after_read` SPEC_MISMATCH step 1: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-10` SPEC_MISMATCH step 1: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-11` SPEC_MISMATCH step 1: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-13` SPEC_MISMATCH step 1: {"violations": ["recipient_allowlist"], "executed": true}
- `D-ALIAS-14` RECONCILIATION_GAP_KERNEL_WITHOUT_SURFACE step None: {"applied": 2, "executed": 3}
- `D-ALIAS-15` SPEC_MISMATCH step 2: {"violations": ["confidential_egress", "recipient_allowlist"], "executed": true}
- `D-RACE-01` SPEC_MISMATCH step 2: {"violations": ["recipient_allowlist"], "executed": true}
- `D-RACE-03` SPEC_MISMATCH step 2: {"violations": ["recipient_allowlist"], "executed": true}
- `D-LEASE-replay` RECONCILIATION_GAP_SURFACE_WITHOUT_KERNEL step None: {"applied": 1, "executed": 0}
- `D-LEASE-concurrent_redeem` RECONCILIATION_GAP_SURFACE_WITHOUT_KERNEL step None: {"applied": 1, "executed": 0}
- `D-DUP-04` ADAPTER_ABLATION_DUPLICATE_EFFECT step 1: "re-delivered event executed again"
- `D-CONT-02` CONTAINMENT_FAILURE step 1: {"violations": ["confidential_egress", "recipient_allowlist"], "executed": true}
- `D-CONT-05` CONTAINMENT_FAILURE step 1: {"violations": ["confidential_egress", "recipient_allowlist"], "executed": true}

## Slowest scenarios (wall-clock, all repetitions)

- `D-MAL-034` 390.486s over 5 reps: raw={"action_type": "write_file", "target": "/reports/q3-summary.md", "parameters": 
- `D-LONG-01` 37.465s over 2 reps: 300 benign writes with periodic spend and external send
- `D-RACE-06` 0.787s over 2 reps: hold 70 benign writes (reservation cap 64)
- `D-BEN-01` 0.114s over 10 reps: benign internal workflow, ordering (0, 1, 2, 3, 4)
- `D-CONT-08` 0.093s over 5 reps: ten sessions alternating read and external send
- `D-BEN-03` 0.09s over 10 reps: benign internal workflow, ordering (1, 0, 3, 2, 4)
- `D-BEN-02` 0.089s over 10 reps: benign internal workflow, ordering (3, 4, 0, 1, 2)
- `D-BATCH-05` 0.082s over 5 reps: ten identical internal sends

## Lease attacks

- `D-LEASE-replay`: ["APPLIED", "LEASE_REFUSED"]
- `D-LEASE-mutate_request`: ["LEASE_REFUSED"]
- `D-LEASE-expired`: ["LEASE_REFUSED"]
- `D-LEASE-missing`: ["LEASE_REFUSED"]
- `D-LEASE-forged_signature`: ["LEASE_REFUSED"]
- `D-LEASE-cross_decision`: ["LEASE_REFUSED"]
- `D-LEASE-garbage`: ["LEASE_REFUSED"]
- `D-LEASE-future_issued`: ["LEASE_REFUSED"]
- `D-LEASE-concurrent_redeem`: {"APPLIED": 1, "LEASE_REFUSED": 49}
- `D-LEASE-redeem_without_kernel`: {"direct_redeem": "APPLIED", "ledger_state_after_direct": ["reserved"], "kernel_execute_after": [false, "runtime error: RuntimeError: LEASE_REFUSED"], "ledger_state_after_kernel": ["executed"]}
- `D-LEASE-mint_from_escalate`: "MINT_REFUSED: ValueError"
- `D-LEASE-mint_from_preview`: "MINT_REFUSED: ValueError"
