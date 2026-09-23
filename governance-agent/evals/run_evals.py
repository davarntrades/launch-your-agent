"""Run the 12 governance eval cases.

    python3 evals/run_evals.py            # from governance-agent/

Writes evals/results.json, evals/results.md and one audit log per case in
evals/audit/. Exit code 0 only if every verdict matches and there are no
false authorizations.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import baseline  # noqa: E402
from governor import AUTHORIZE, Pipeline, initial_policy, initial_state, verify_chain  # noqa: E402


def run_case(case, audit_dir=None):
    path = os.path.join(audit_dir, f"{case['id']}.jsonl") if audit_dir else None
    pipe = Pipeline(initial_state(), initial_policy(), audit_path=path)
    setup_verdicts = []
    for i, step in enumerate(case["setup"]):
        e = pipe.submit(dict(step, id=f"{case['id']}-s{i + 1}"))
        setup_verdicts.append(e["verdict"])
    e = pipe.submit(dict(case["proposal"], id=f"{case['id']}-target"))
    return {
        "id": case["id"],
        "group": case["group"],
        "label": case["label"],
        "setup_verdicts": setup_verdicts,
        "expected": case["expected"]["verdict"],
        "expected_violated": case["expected"]["violated"],
        "verdict": e["verdict"],
        "violated": e["violated"],
        "reasons": e["reasons"],
        "baseline_verdict": baseline.evaluate(case["proposal"]),
        "chain_ok": verify_chain(pipe.audit.entries),
        "final_state_digest": e["state_after_digest"],
    }


def score(rows, key):
    correct = sum(r[key] == r["expected"] for r in rows)
    false_auth = [r["id"] for r in rows if r["expected"] != AUTHORIZE and r[key] == AUTHORIZE]
    false_hold = [r["id"] for r in rows if r["expected"] == AUTHORIZE and r[key] != AUTHORIZE]
    return {
        "accuracy": f"{correct}/{len(rows)}",
        "accuracy_pct": round(100 * correct / len(rows), 1),
        "false_authorizations": false_auth,
        "false_withholds": false_hold,
    }


def main():
    with open(os.path.join(HERE, "cases.json")) as fh:
        cases = json.load(fh)["cases"]
    audit_dir = os.path.join(HERE, "audit")
    os.makedirs(audit_dir, exist_ok=True)

    rows = [run_case(c, audit_dir) for c in cases]
    rerun = [run_case(c) for c in cases]
    deterministic = all(
        (a["verdict"], a["violated"], a["final_state_digest"]) == (b["verdict"], b["violated"], b["final_state_digest"])
        for a, b in zip(rows, rerun)
    )
    setup_ok = all(v == AUTHORIZE for r in rows for v in r["setup_verdicts"])
    constraint_ok = [r["id"] for r in rows if r["violated"] != r["expected_violated"]]

    summary = {
        "governor": score(rows, "verdict"),
        "baseline_no_simulation": score(rows, "baseline_verdict"),
        "violated_constraint_mismatches": constraint_ok,
        "adversarial_setup_steps_all_authorized": setup_ok,
        "deterministic_across_two_runs": deterministic,
        "audit_chains_valid": all(r["chain_ok"] for r in rows),
    }
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump({"summary": summary, "cases": rows}, fh, indent=2)

    lines = [
        "| Case | Group | Expected | Governor | Violated constraint | Baseline (no simulation) |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        ok = "✅" if r["verdict"] == r["expected"] else "❌"
        bok = "✅" if r["baseline_verdict"] == r["expected"] else "❌"
        lines.append(f"| {r['id']} | {r['group']} | {r['expected']} | {ok} {r['verdict']} | "
                     f"{', '.join(r['violated']) or '—'} | {bok} {r['baseline_verdict']} |")
    g, b = summary["governor"], summary["baseline_no_simulation"]
    lines += [
        "",
        "| Metric | Governor | Baseline |",
        "|---|---|---|",
        f"| Verdict accuracy | {g['accuracy']} | {b['accuracy']} |",
        f"| False authorizations | {len(g['false_authorizations'])} {g['false_authorizations'] or ''} | "
        f"{len(b['false_authorizations'])} {b['false_authorizations'] or ''} |",
        f"| False withholds | {len(g['false_withholds'])} {g['false_withholds'] or ''} | "
        f"{len(b['false_withholds'])} {b['false_withholds'] or ''} |",
        "",
        f"Setup steps of adversarial sequences all AUTHORIZE: {setup_ok} · "
        f"deterministic across two runs: {deterministic} · audit chains valid: {summary['audit_chains_valid']}",
    ]
    report = "\n".join(lines)
    with open(os.path.join(HERE, "results.md"), "w") as fh:
        fh.write("# Governance eval results\n\n" + report + "\n")
    print(report)

    passed = (g["accuracy_pct"] == 100.0 and not g["false_authorizations"] and not constraint_ok
              and setup_ok and deterministic and summary["audit_chains_valid"])
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
