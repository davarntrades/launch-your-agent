# morrison-cma: Morrison × Claude Managed Agents falsification campaign

The Morrison Runtime Governance kernel (`davarntrades/Morrison-Runtime-Governance` @ `0ba8f88`, unmodified) governs a CMA Worker. The experimental prototype in `../governance-agent/` is **not** used as a decision authority. Its frozen transitions and constraints serve only as the mock world and as oracle [H]. Its historical results remain prototype evidence.

| File | Role |
|---|---|
| `PREREGISTRATION.md` | Hypotheses, controls, outcome vocabulary, analysis plan |
| `TRIAL-MATRIX.md` | Live arms, counts, estimated API usage, outcome-blind scaling rule |
| `config/deployment.json` | Configuration C1: every Morrison input |
| `adapter/unwrap.py` | [C]: CMA tool input → Morrison call (one rule, no decisions) |
| `adapter/governed.py` | Operator runtime: authorise → lease → [E] |
| `world/world.py`, `world/surface.py` | Mock world, oracle [H], execution surface [E] |
| `prereg/analyst.py` | My written predictions of Morrison, made before running it |
| `prereg/scenarios.py` → `prereg/corpus.jsonl` | Deterministic corpus (2,833 scenarios) with analyst + oracle labels |
| `arms/` | Agent prompts, tool schema, model-dependent arms |
| `LOCK-A.sha256` | Hashes of everything above at preregistration commit A |

Run everything with Morrison on `PYTHONPATH` at the pinned commit.
