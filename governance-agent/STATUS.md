# Status: governed-worker (experimental prototype)

> **Scope.** This is an experimental prototype built in one session to explore pre-execution mediation for a Claude Managed Agents Worker. It is **not** the Morrison Runtime Governance kernel, does not represent it, and does not replace it. Integrating it with that published kernel is a separate, future step.

## Four things kept separate

| # | What | Result | Where |
|---|---|---|---|
| 1 | **Original architecture**, commit `4293483` (attacked after the fact, unmodified, via `git archive`) | **13 PASS · 6 GAP · 14 BYPASS** of 33 attacks (7 BYPASS reachable by the Worker) | `FALSIFICATION.md`, `attacks/results-original.{md,json}` |
| 2 | **Hardened prototype**, commit `38db1a4` (frozen since) | **33/33 attacks blocked** against a fake CMA API (no network); guard ablation 12/12 detected; policy evals 12/12 | `attacks/results.md`, `attacks/mutation-results.md`, `evals/results.md`, `BOUNDARY.md` |
| 3 | **Attempted live run**, GitHub Actions run `35884883546` | Stopped before contacting Anthropic: `ANTHROPIC_API_KEY` was empty in the workflow. **No live evidence.** | `LIVE-ATTEMPTS.md` |
| 4 | **Unverified live-platform assumptions** | Not established by anything above | Listed below |

Process note: the hardening in `38db1a4` was written before the original was attacked. `FALSIFICATION.md` records this as a process error, along with the corrected sequence.

## Unverified live-platform assumptions

1. CMA never executes a tool absent from the agent/session tool configuration.
2. The event history is complete: every sandbox tool execution produces an event.
3. Custom tools are never executed server-side; CMA only relays the call and waits.
4. `networking: limited` with no hosts blocks every egress path.
5. Agent versions are immutable once created.
6. Only API-key holders for the workspace can change agent, environment or session config.
7. Outcome grading runs without tools that could touch operator state.
8. Real event-type names (`agent.custom_tool_use`, `agent.tool_use`, `agent.mcp_tool_use`) and pagination fields (`has_more`, `last_id`, `after_id`) match what the driver assumes. So far these are assumed from docs and exercised only against a fake API.

Live probes L1–L9 in `live/campaign.py` are written to test assumptions 2, 3, 4 and 8, plus attestation on real response shapes. They have not run.
