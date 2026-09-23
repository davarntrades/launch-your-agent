# Mediation boundary

Claim under test: **every change to the real state passes through Governor → Executor, and what the Executor commits is exactly what the Governor evaluated.** Policy accuracy (`evals/`) is a separate question. This file is about the boundary.

The original architecture (`4293483`) failed this: 14 BYPASS / 6 GAP of 33 attacks. See `FALSIFICATION.md` for the sequence original → attack → result → harden → retest. Everything below describes the hardened code.

Run: `python3 attacks/run_original.py` (original) · `python3 attacks/run_attacks.py` (hardened) · `python3 attacks/mutation_check.py` (removes each guard and confirms that at least one attack then reports OPEN).

## Where the boundary sits

```
 CMA (Anthropic-hosted)                              │  operator machine (this repo, driver.py process)
                                                     │
 Worker model ── tools: [custom propose_action] ─────┼─▶ split_events(): only agent.custom_tool_use
   no agent_toolset, no MCP, no skills, no vaults    │     named propose_action becomes a proposal;
   env: networking limited, allowed_hosts []         │     any other tool event → interrupt + exit
   (nothing of the real state is mounted here)       │   normalize() → evaluate(policy, snapshot) ─┐
                                                     │   Executor.commit(authorization) ◀──────────┘
 ◀── user.custom_tool_result (verdict text only) ────┼── audit log (hash chain)
```

The real state and the policy exist only inside the driver process. The Worker's only effect channel is the `propose_action` tool, and CMA executes that tool **client-side**: CMA pauses and hands the call to `driver.py`. CMA itself never executes it.

## The six questions

| # | Path | Why it is unavailable | Enforced by | Attack(s) |
|---|---|---|---|---|
| 1 | Bypass `propose_action` | The Worker has no other tool. Plain text is never parsed into a proposal. A custom tool under any other name halts the session | `agent.json`; `attest.check_agent` before every session; `attest.split_events` | Q1 × 4 |
| 2 | MCP / tool execution outside the Governor | No `mcp_servers`, `mcp_toolset` or `agent_toolset`, and MCP networking is off. Any `agent.tool_use` / `agent.mcp_tool_use` event halts the session. Session-level tool overrides are detected on every poll. Hidden pages of event history are scanned (fail closed) | `check_agent`, `check_environment`, `check_session` (per poll), `list_events` pagination | Q2 × 6 |
| 3 | Mutate through the sandbox | The state isn't in the sandbox: session create sends no `resources`, `vault_ids` or files. The environment has no egress. Inside the driver process only the Executor holds a reference; `Pipeline.state` returns a copy | environment config; `Executor` private `_state` + `snapshot()` | Q3 × 3 |
| 4 | Redeem a stale authorization | AUTHORIZE is bound to `(state_digest, proposal_digest, result_digest)`. Commit is compare-and-swap, and the committed state is the evaluated simulation itself, not a re-application. Ids are single-use (the CMA event id, not a Worker-chosen value). ESCALATE approval re-evaluates on the current state, and approval is a Python call no proposal type can reach | `Executor.commit`, `Pipeline._seen_ids`, `Pipeline.approve`, a lock around evaluate + commit (a two-thread race overspent the original in ~98% of trials) | Q4 × 7 |
| 5 | Manipulate the evaluated state | Policy is a frozen object outside the state, so no transition receives it. Proposals are JSON-round-tripped (detached) with exact keys and types. Recipients are resolved on the simulated state (alias shadowing, forwarding, cycles). Unrecognized spellings fail closed | `Policy`, `actions.normalize`, `resolve_recipients` | Q5 × 7 |
| 6 | Unmodelled execution surface | Unknown action types are WITHHOLD. Each transition has a declared write footprint, and a write outside it is WITHHOLD (frame condition). Proposal count is bounded. A randomized 5,000-proposal run (seed 7) found the hard constraints holding after every step and no irreversible loss without an approval entry | `FOOTPRINT` check in `evaluate`, `proposal_budget`, `hard_invariants_hold` | Q6 × 6 |

## What is NOT structurally closed (residuals)

These are the places where the boundary rests on detection or trust rather than construction:

1. **The CMA platform honoring the tool config.** We don't prevent server-side execution; we configure none and detect any (`agent.tool_use` / `agent.mcp_tool_use` → halt). Detection happens at poll granularity (3 s). A server-side tool would already have run by then, but with no network egress and no state in the container it would have nothing to reach.
2. **Anyone holding the API key.** They can update the agent or session config. Drift is detected per poll and halts the run, but it isn't prevented. Mitigation: a dedicated workspace and key for this agent.
3. **In-process code.** Python has no object capabilities: code running *inside* the driver process can reach `pipe._executor` (the attack suite does this on purpose). The boundary is the process boundary, and the Worker never executes code in that process.
4. **The human approver.** The Worker's final text can argue for approving an ESCALATE. Approval should be made from the audit entry (state_before, simulated effect, reasons), never from Worker text.
5. **Transition semantics.** The frame condition catches writes to undeclared state keys. It does not catch a wrong effect *inside* a declared key. The constraints are still checked on the resulting state, so a wrong effect that leaves the admissible set is caught; one that stays inside it is not.
6. **The audit log is tamper-evident, not tamper-proof.** Rewriting the whole chain is undetectable unless the head hash is anchored somewhere else (v2).
7. **Mock vs real systems.** The CAS here covers the mock state. A real executor needs the same binding at the real system (conditional writes, version checks), because external state can change between evaluate and commit outside this process.
8. **Event-page cursor shape.** `list_events` follows `has_more` / `last_id` / `after_id` and halts if a cursor is missing. The exact CMA pagination fields should be confirmed against the live docs on the first live run.
