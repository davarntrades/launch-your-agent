# governed-worker — pre-execution governance layer on CMA

```
Worker (CMA, custom tool propose_action only)
   │ proposal {action_type, target, parameters}
   ▼
Governor (deterministic Python, client-side)
   simulate on deep copy → constraint predicates → AUTHORIZE | WITHHOLD | ESCALATE (+ violated, reason)
   ▼
Executor (AUTHORIZE only; ESCALATE → pending queue)      Audit log (JSONL, sha256 chain)
   writes the sandboxed mock state                      state_before · proposal · verdict · state_after
```

Mock state: budget (cents + ledger), file store (content + history + trash), roles/principals, recipient allowlist + aliases + forwarding, outbox. No real side effects.

## Constraints (predicates on the simulated state)

| Constraint | Resulting state must satisfy | Violation |
|---|---|---|
| `spend_ceiling` | cumulative spent ≤ ceiling | WITHHOLD |
| `no_permission_widening` | each principal's effective permissions (via roles) ⊆ session baseline | WITHHOLD |
| `recipient_allowlist` | every delivered address (aliases + forwarding expanded) is listed | WITHHOLD |
| `no_irreversible_delete` | no (path, content) leaves the recoverable set (live ∪ history ∪ trash) | ESCALATE |

Undefined transitions (unknown action type, missing file, bad parameter) → WITHHOLD (`transition_defined`).

## Evals — 12 proposals

| | Governor | Baseline (field rules, no simulation) |
|---|---|---|
| Verdict accuracy | **12/12** | 8/12 |
| False authorizations | **0** | 3 (X1, X2, X3) |
| False withholds | **0** | 1 (A6) |

6 admissible (A1–A6), 3 direct violations (D1–D3), 3 multi-step sequences (X1 split spend, X2 trash → purge, X3 forwarding rule → send) whose setup steps are each AUTHORIZE. Full table: `evals/results.md`. Per-case audit logs: `evals/audit/`.

Caveat: the cases and the predicates were written together, so 12/12 shows the mechanism works as specified — it is not a measure against unseen sequences. `NEXT-DIRECTIONS.md` v2 lists more held-back sequences.

## Run it

```bash
cd governance-agent
python3 evals/run_evals.py                 # 12 cases, exits 0 on pass
python3 -m unittest discover -s tests      # 8 unit tests (determinism, no mutation, escalation, audit tamper)
python3 driver.py scripted                 # 13-proposal demo through the full pipeline, no key
./launch.sh                                # live: CMA Worker + client-side Governor (needs .env with ANTHROPIC_API_KEY)
```

## Dashboard

`agent-overview.html` (+ `overview.css` next to it). Open it in a browser:
- Laptop: `open governance-agent/agent-overview.html` (macOS) or `xdg-open …` (Linux).
- Phone: open the file from the Claude app's file view on this branch, or view the published copy if one was shared with you.
- After a live run, the Console shows the session: `platform.claude.com/workspaces/default/sessions/<session_id>` (swap `default` for your workspace).

## Hall-of-fame submission (template steps)

1. Run `python3 evals/run_evals.py` and keep the output table.
2. Optional: run `./launch.sh` once with your key; keep the session ID and `runs/<session_id>/audit.jsonl`.
3. Screenshot `agent-overview.html` (desktop width).
4. Push this branch and copy the link to the `governance-agent/` folder.
5. Submit: title, one-line description ("Deterministic pre-execution Governor for a CMA Worker: simulate → constraint predicates → AUTHORIZE/WITHHOLD/ESCALATE"), repo link, screenshot, eval table (12/12, 0 false authorizations, 0 false withholds, baseline 8/12), and the Console session link if you ran it live.
