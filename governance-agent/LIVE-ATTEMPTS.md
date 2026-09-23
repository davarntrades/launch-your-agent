# Live campaign attempts: Claude Managed Agents

**No live Anthropic evidence exists yet.** No run has contacted the Anthropic API with the repository secret.

## Attempt 1: GitHub Actions run 35884883546

| Field | Value |
|---|---|
| Workflow | `.github/workflows/live-cma.yml` (`live-cma-campaign`), push-triggered |
| Run | https://github.com/davarntrades/launch-your-agent/actions/runs/35884883546 (run #1, attempt 1) |
| Job | 107262382745 |
| Commit | `60426dd695a0099845f34980a6eff1dee582b204` |
| Started | 2026-09-23T15:53:38Z; conclusion `failure` after about 11 s |
| Architecture frozen at 38db1a4 | Yes: `git diff --stat 38db1a4 HEAD -- governor driver.py agent.json environment.json launch.sh` was empty |
| Anthropic calls made | **None** |
| Anthropic identifiers | None (no request, session, agent or environment was created) |

**What happened.** The step `python3 live/campaign.py pre` ran with `ANTHROPIC_API_KEY` set to an empty value (the log shows `ANTHROPIC_API_KEY:` with nothing after it) and exited with `ANTHROPIC_API_KEY not set`. The governed path (`./launch.sh`) and probes L1–L9 did not run. The evidence-commit step had nothing to commit. An artifact `live-evidence-35884883546` (artifact 10762526945) holds only the frozen-architecture files.

**Cause (not yet confirmed).** GitHub Actions had no secret named exactly `ANTHROPIC_API_KEY` available to this workflow. Likely causes: the secret is stored as a Codespaces or Dependabot secret, as an Environment secret (the job declares no `environment:`), under a different name, or on another repository.

**Frozen-architecture sha256 recorded by the run:**

```
3e22f43f11c6f0a4be4e42ba2864b169837c39111d06a9f9687805be0f1f8aea  governor/__init__.py
306c5c2be81dd1a0d817976e9445555f4605f3923910339f931224f01ef3179a  governor/actions.py
52f5d28f1632ca76e33ce4a07766a72591af0ab9ff41e0c5f8a0ff489d51fcd3  governor/attest.py
d4045abe13c3e08c7c4470ac6dc6f7b1bcdc8523f80487c56ef2f26af66eac8c  governor/constraints.py
ec7bbb1ce5eb3eedc252f36eb78e393587b3c28327ed42fb2fa0e05c769b8df6  governor/governor.py
5fa8003bbece25e46032298cc645b865f19a19f97f5c4688069d4a648ec40083  governor/pipeline.py
1c2eb7308d716448070358ecaf94c3c2d58b2db1dced34df3838ad916334a3a3  governor/state.py
8e507a69e95921336b27f7dd3406b721b04341f743a60afd9b6e21986573edf7  driver.py
ceb181e6099a2c842faf5de08734bb4f50fc1aaa0d19d85829c72dfc9082f7ec  agent.json
257364f059229adc32510bef813f9986f88f8b2458bc575434eaa9ba489e2bf5  environment.json
fe7735684af93de7478b53b08215fd74ab1026e77ec7bbbf41f3725a48d3f551  launch.sh
```

## Campaign code checks before the attempt (not live evidence)

`live/campaign.py` was dry-run from this dev container against the real API with a deliberately **invalid** key, in a scratch copy outside the repo. Every call returned `401 authentication_error` as expected (e.g. request-id `req_011CfLe6ogmv7vTGpsqSiQGG`). The dry run found two classification bugs in the campaign code: an HTTP 401 was reported as GAP (L2) and as OBSERVED (L9). Both were fixed to report ERROR before commit `60426dd`. This exercised only the campaign's error handling. It says nothing about platform behavior.

## To resume

1. Add `ANTHROPIC_API_KEY` under GitHub → Settings → Secrets and variables → **Actions → Repository secrets**. If it has to stay an Environment secret, add `environment: <name>` to the job.
2. Re-run the workflow on the same commit (Actions → run 35884883546 → Re-run), or push a change to `governance-agent/live/TRIGGER`.
3. The run commits `governance-agent/live/results-live.json`, `live/evidence/` and `LIVE.md` back to the branch. Record the results before changing anything.
