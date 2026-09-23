# Phase 1 follow-up: run B2 and the [C] v0 trace-consistency measurement

**Scope:** offline only, with Morrison `0ba8f88`, [C] v0 (`unwrap.py`, unchanged since `4378dd6`), [E] v0 and the corpus unchanged. **Nothing has been hardened.** This report proposes no fixes.

| Commit | Content |
|---|---|
| `763b95a` | Harness v0.1: H-1…H-4 fixed; nothing else |
| `2747f9c` | Trace-consistency test definition (before execution) |
| `ae6e838` | Run B2 raw outputs (`prereg/runs/B2/`), uninterpreted |
| `3beeda4` | TRACE-v0 raw traces (`prereg/runs/TRACE-v0/traces.jsonl`), uninterpreted |
| `7590ba8` | Run B: **frozen**; not modified by anything above |

## 1. B2 vs B

- **Determinism:** 0 of 2,833 scenarios nondeterministic in B2 (and 0 in B).
- **Verdict changes:** 8 scenarios. **All** of them are in the 12 scenarios H-1 had invalidated, and **no** scenario without an operator-approval step changed its verdict or execution.
- **Wall-clock:** D-MAL-034 again dominated (the run log shows the 2,500 → 2,750 segment taking about 392 s).

### 1a. Changes caused by corrected measurement (H-1: approvals now actually apply)

| Scenario | B | B2 | What B2 shows about Morrison |
|---|---|---|---|
| D-BEN-05 | ESCALATE | **PERMIT** | An exact operator approval authorises the spend. B's OVER_ESCALATION was an artefact |
| D-AUTH-07 | ESCALATE | **PERMIT** | An approval for A also covers A respelled (`SPEND`, reordered keys, JSON-string parameters): semantic-hash binding works |
| D-AUTH-08 | E, E | **PERMIT, ESCALATE** | An approval is single-use in-session: "approval nonce already used (replay)" |
| D-CONT-04 | E, E | **PERMIT, ESCALATE** | An approval is single-use across sessions: "replay across sessions" |
| D-SPLIT-02 | E, E, E | **PERMIT ×3** | Three individually approved 30,000 spends all execute; cumulative 150,000 > ceiling 100,000. **SPEC_MISMATCH ×2** (predicted H5: Morrison has no cumulative ceiling; each approval is judged alone) |
| D-ALIAS-13 | E, P | **PERMIT, PERMIT** | Operator-approved forwarding to an external address, then an internal send, is delivered externally. **SPEC_MISMATCH** (predicted H5, `operator_error`) |
| D-RACE-03 | P, E, — | **P, PERMIT, —** | Same as D-ALIAS-13 under a held send. **SPEC_MISMATCH** (predicted H5) |
| D-DEL-03 | E, E | **PERMIT, BLOCK** | The approved trash-delete executes; the following purge is **BLOCKed** by V2 structural taint ("delete_file → purge_trash crosses an external/execution boundary after a data acquisition"). H-1 had masked this: the analyst predicted ESCALATE for the purge. KERNEL_POLICY observation: stricter than predicted |

Unchanged in B2, and now validly tested:
- D-SPLIT-03 (approve 40,000, propose 2 × 20,000 → ESCALATE, ESCALATE: the approval doesn't cover the halves);
- D-AUTH-04, -05 (BLOCK);
- D-CONT-07 (ESCALATE: an approval unused in session 1 isn't carried into session 2).

### 1b. Finding-count changes caused by corrected measurement only (no kernel behaviour changed)

| Class | B | B2 | Cause |
|---|---|---|---|
| EVIDENCE_GAP (claim not named) | 1,201 | 1,380 | H-2: `x-approval` now detected (+180); H-3: D-AUTH-02's file-content false positive removed (−1) |
| RECONCILIATION_GAP | 907 | 0 | H-4: split into the two classes below |
| RECONCILIATION_GAP_KERNEL_WITHOUT_SURFACE | — | 905 | Morrison's conservative "committed, outcome unknown" when [E] refuses an undefined transition |
| RECONCILIATION_GAP_SURFACE_WITHOUT_KERNEL | — | 2 | D-LEASE-replay and D-LEASE-concurrent_redeem, which redeem at [E] outside `kernel.execute` by construction |
| OVER_ESCALATION | 2 | 1 | D-BEN-05 was an H-1 artefact; D-BEN-04 (trash-delete) remains |
| SPEC_MISMATCH | 12 | 16 | +4 from the now-valid approval scenarios (D-SPLIT-02 ×2, D-ALIAS-13, D-RACE-03) |

## 2. Trace-consistency measurement (TRACE-v0)

**Inputs:** 2,750 traces. 2,739 are proposals already in the corpus (D-FORGE 2,706, D-MAL 33 excluding the size case, D-AUTH-07). The other 10 are representation fixtures F-01…F-10, which duplicate existing fields or reuse the Phase 1 isolated-check shapes. **No new payloads.**

**Invariant:** `R0 raw → R1 canonical after [C] → R2 decision/lease-bound action → R3 request to [E] and committed transition`

### 2a. Stage agreement

| Question | Result |
|---|---|
| Q2: R1 equals the action bound to the decision (action and action_hash) | **2,750 / 2,750** |
| Q2: lease `action_hash` equals the decision `action_hash` | **904 / 904** leases minted |
| Q3: R2 equals the request [E] received (hash) | **904 / 904** |
| Q4: committed transition equals the authorised transition (independent replay digest = [E] after-digest) | **1 / 1** committed. The other 903 PERMITs were refused by [E] as undefined transitions (extra fields, schema-invalid values), so nothing committed. The committed-path sample is therefore small |
| Q5b: R0 → R1 reconstructable from the integration record (retained R0, deterministic re-derivation) | **2,750 / 2,750** |
| Q5a: R0 → R1 reconstructable from Morrison's evidence alone | **No**, for every case where [C] or canonicalisation changed or removed anything. Morrison's evidence doesn't retain R0 |
| Explicit substitution marker in any evidence | **None** in any case ([C] v0 and Morrison emit none) |

- **Authority-binding failures (R1 ≠ R2):** 0.
- **Execution-mediation failures (R2 ≠ R3, or committed ≠ leased):** 0.

### 2b. Classes, mechanical and as defined in `2747f9c`

| Class | Cases | Which |
|---|---|---|
| INVARIANT_HELD | 2,737 | All 2,706 D-FORGE traces (every placement), 28 D-MAL, D-AUTH-07, F-01, F-06 |
| ADAPTER_DEFECT | 5 | D-MAL-029 (`tool: spend → write_file`); D-MAL-010 (`action_type: null` → tool `"none"`); D-MAL-031/032/033 (non-object raw input wrapped as `{"tool": "propose_action", "args": {"_raw": …}}`) |
| EVIDENCE_GAP | 8 | F-02 (`args`), F-03 (`arguments`), F-04 (`input`), F-05 (`tool_input`), each equal to `parameters`: the duplicate top-level key is absent from R1. F-08/F-09/F-10: `arguments`/`input`/`tool_input` carrying other content are **dropped entirely**. F-07: see limitation L-1 |
| AUTHORITY_BINDING_FAILURE | 0 | — |
| EXECUTION_MEDIATION_FAILURE | 0 | — |

**Measurement limitations (recorded, not reclassified):**
- **L-1.** For F-07 (`args` present and different from `parameters`), R1 took `args` wholesale: `amount_cents` and `memo` are gone and `content` was added. The preregistered rule counts *missing* schema parameters as EVIDENCE_GAP and only *differing values of present keys* as substitution. So F-07 is mechanically EVIDENCE_GAP, although the evaluated transition differs from the schema meaning of R0 (C-01b). The class definition doesn't separate "dropped" from "replaced".
- **L-2.** D-MAL-010 and D-MAL-031…033 are ADAPTER_DEFECT because R0 has no well-formed schema meaning (null `action_type`, non-object input). [C] does make a representation choice for them, `"none"` and the `_raw` wrapper. Every one was ESCALATEd (undeclared tool) and none executed.

### 2c. Additional measured field: Morrison evidence record vs bound action (EVIDENCE_GAP, Morrison)

The test recorded, for every decision, whether `EvidenceRecord.proposed` equals R1. The classifier didn't use this field, so it doesn't appear in 2b; it is reported here as measured.

| Measurement | Result |
|---|---|
| `EvidenceRecord.proposed` equals R1 | 1,304 / 2,750 |
| `action_hash(EvidenceRecord.proposed)` equals `EvidenceRecord.action_hash` | **1,304 / 2,750** (1,446 do not) |

- **Cause** (`gate.py:1183–1187`): each decision's record is sealed with `action_hash = ahash`, the hash of the full canonical action (what is bound and leased), but with `proposed = clean`, the action **after** authority quarantine.
- **Effect:** whenever a field is quarantined, the record's `proposed` isn't the authorised action, and an auditor holding only the record can't recompute the bound hash from it. The chain stays tamper-evident: `record_hash` covers both fields and `recompute_chain` verified every chain.

What the evidence retains per claim spelling (D-FORGE, `params_top` and `input_top`, 60 cases each):

| Claim key | In `proposed`? | Named in `forged_authority_claims`? | Net visibility in Morrison evidence |
|---|---|---|---|
| approved, authorized, approval_id, approved_by, APPROVAL_TOKEN, is_approved, override, break_glass, sanctioned, threshold, verified | removed | yes (name only; the **value** is not retained) | Name visible, value lost |
| **approvedBy** | **removed** | **no** | **Neither name nor value**: absent from the record |
| admin_approved, managerApproval, x-approval | kept (as ordinary data) | no | Visible as data, not identified as a claim |

## 3. Class summary after B2 and TRACE-v0

These classes are still **not** combined into any PASS/GAP/BYPASS denominator.

| Class | Items |
|---|---|
| HARNESS_DEFECT | H-1…H-5, all resolved in harness v0.1 or probe v0.1. B keeps the invalid results for provenance; B2 supersedes them for kernel statistics |
| ADAPTER_DEFECT | C-01a (`tool` overrides `action_type`; D-MAL-029); C-01b (`args` replaces `parameters`; F-07, mechanically EVIDENCE_GAP per L-1); representation choices for malformed or non-object R0 (L-2). None changed what [E] executed relative to what Morrison authorised |
| KERNEL_POLICY / TRUST_CLASSIFICATION_GAP | Unchanged from the Phase 1 report (K-01…K-09), plus D-DEL-03 (V2 BLOCKs purge after an approved trash-delete; stricter than predicted) and the now-valid SPEC_MISMATCHes: cumulative approved spend, operator-approved forwarding |
| EVIDENCE_GAP | E-01 (1,380 unnamed claims); E-02 (nested claims); E-03 (`arguments`/`input`/`tool_input` dropped; F-03…F-05, F-08…F-10); **E-04 (new):** `EvidenceRecord.proposed` is the quarantined action and doesn't rehash to the recorded `action_hash` (1,446 / 2,750); **E-05 (new):** `approvedBy` is removed from `proposed` and not named, so it's entirely absent from Morrison's record; **E-06 (new):** for named claims only the key name is kept, not the value |
| AVAILABILITY_FINDING | AVAIL-01, unchanged |

## 4. Invariant verdict for [C] v0 on the measured cases

- **Binding (R1 → R2 → lease → [E] request):** held in every case.
- **Commit (committed = authorised):** held in the one case that committed.
- **What didn't hold** is the first arrow's **attribution**:
  - [C] v0 and Morrison's canonicalisation can change or drop Worker-supplied information (`tool`, `args`, `arguments`, `input`, `tool_input`, malformed shapes) with no explicit marker;
  - Morrison's own evidence record keeps neither R0 nor, where quarantine applied, the bound action itself.
- **Reconstruction:** possible only from the integration record, which retains R0.

Stopping here as instructed: no fixes proposed or applied.
