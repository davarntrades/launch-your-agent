# Next directions — governed-worker

Reason classes: **(i)** not possible on CMA · **(ii)** needs a credential not on hand · **(iii)** possible, scheduled for a later version.

## v1 — live run
- **Launch the Worker on CMA** — (ii) no `ANTHROPIC_API_KEY` in this session. How: put the key in `governance-agent/.env` (`ANTHROPIC_API_KEY=...`, chmod 600), run `./launch.sh`. It picks the newest Opus model, creates the environment + agent, and runs `driver.py live`. Audit log lands in `runs/<session_id>/audit.jsonl`.
- **Approval command for the ESCALATE queue** — (iii). How: persist `Pipeline.pending` to `runs/<id>/pending.json`; add `driver.py approve <proposal_id> --by <name>` that calls `Pipeline.approve()` (already implemented and tested: re-evaluates against the current state before applying).
- **Grade the live run** — read `outcome_evaluations[]` and compare the Worker's report against `audit.jsonl` (the log is the ground truth; the report is graded against it).

## v2 — policy hardening
- **Constraints as versioned data** — (iii). Load ceilings, allowlist and baseline from `policy.json` with a hash recorded in every audit entry.
- **Velocity limits** — (iii). Add `spend_window` predicate (e.g. max N cents per rolling window) using the ledger in state.
- **Explicit pre-state admissibility check** — (iii). Refuse to start a run if `initial_state()` itself violates a predicate.
- **More adversarial sequences** — (iii). Role composition (already a unit test), alias rewrite (in the scripted run), restore-overwrite loops, cyclic forwarding. Add them to `evals/cases.json` as held-back cases.

## v3 — real systems
- **Swap the mock for real endpoints** — (ii) needs connector credentials. How: the Executor calls the real API; the Governor keeps evaluating on a state snapshot fetched before each proposal. Any real endpoint without a dry-run/snapshot stays behind ESCALATE.

## Always
- Re-run `python3 evals/run_evals.py` (must exit 0) and `python3 -m unittest discover -s tests` before changing any predicate or promoting a new agent version.
