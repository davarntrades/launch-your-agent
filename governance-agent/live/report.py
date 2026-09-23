"""Write LIVE.md from live/results-live.json, keeping three categories apart:
(1) existing mock evidence, (2) live Anthropic evidence, (3) unverified claims about Anthropic internals."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

UNVERIFIED = [
    "CMA never executes a tool that is absent from the agent/session tool configuration (we observe events; we cannot inspect the server).",
    "The event history returned by the API is complete, i.e. every tool execution in the sandbox produces an event (detection depends on this).",
    "Custom tools are never executed server-side; CMA only relays the call and waits (observed as blocking in L5, not proven for all cases).",
    "Environment networking 'limited' with no hosts holds for every egress path, not only the curl tested in L4 (DNS, other protocols, package mirrors).",
    "Agent versions are immutable once created, so an attested (id, version) cannot change underneath a running session.",
    "Only holders of an API key for this workspace can change agent, environment or session configuration.",
    "Outcome grading runs without tools that could touch operator state.",
]


def main():
    live = json.load(open(os.path.join(HERE, "results-live.json")))
    meta, probes = live["meta"], live["probes"]
    mock_h = json.load(open(os.path.join(ROOT, "attacks", "results.json")))
    mock_o = json.load(open(os.path.join(ROOT, "attacks", "results-original.json")))["results"]
    icon = {"PASS": "✅ PASS", "GAP": "🟡 GAP", "BYPASS": "❌ BYPASS", "OBSERVED": "🔎 OBSERVED",
            "NOT RUN": "⏸ NOT RUN", "ERROR": "⚠️ ERROR"}
    c = {k: sum(p["outcome"] == k for p in probes) for k in icon}

    L = ["# Live campaign — Claude Managed Agents", "",
         f"Commit `{meta['commit_sha']}` · workflow run `{meta['workflow_run_id']}` (attempt {meta['workflow_run_attempt']}) · "
         f"{meta['repository']} · finished {meta['finished_utc']}",
         f"Architecture frozen at 38db1a4 (governor/, driver.py, agent.json, environment.json, launch.sh unchanged): "
         f"**{meta['architecture_frozen_at_38db1a4']}**", "",
         "## 1 · Existing mock evidence (fake CMA API, no network) — unchanged by this campaign", "",
         f"- Original architecture 4293483: {sum(r['outcome']=='PASS' for r in mock_o)} PASS · "
         f"{sum(r['outcome']=='GAP' for r in mock_o)} GAP · {sum(r['outcome']=='BYPASS' for r in mock_o)} BYPASS (FALSIFICATION.md)",
         f"- Hardened 38db1a4: {sum(r['blocked'] for r in mock_h)}/{len(mock_h)} blocked (attacks/results.md)",
         "- These results say nothing about live platform behaviour.", "",
         "## 2 · Live Anthropic evidence", "",
         " · ".join(f"{icon[k]} {v}" for k, v in c.items() if v), "",
         "| Probe | Expected | Actual | Result | Identifiers |", "|---|---|---|---|---|"]
    for p in probes:
        ids = "; ".join(f"{k}={v}" for k, v in p["ids"].items() if v not in (None, [], ""))
        L.append(f"| **{p['id']}** {p['name']} | {p['expected']} | {str(p['actual']).replace('|', '/')} | "
                 f"{icon.get(p['outcome'], p['outcome'])} | {ids.replace('|', '/')} |")
    L += ["", "### Evidence per probe", ""]
    for p in probes:
        L.append(f"<details><summary>{p['id']} — {icon.get(p['outcome'], p['outcome'])}</summary>\n\n```json\n"
                 + json.dumps(p["evidence"], indent=2)[:6000] + "\n```\n</details>\n")
    L += ["Full event histories, session objects and the governed run's audit log: `live/evidence/`. "
          "Every API call with status and request-id: `live/results-live.json` → `api_calls`.", "",
          "## 3 · Claims about Anthropic internals that remain unverified", "",
          "These are not established by any probe above; the boundary depends on them.", ""]
    L += [f"{i}. {u}" for i, u in enumerate(UNVERIFIED, 1)]
    with open(os.path.join(ROOT, "LIVE.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
