"""Run the attack suite against the ORIGINAL architecture, unmodified.

    python3 attacks/run_original.py        # from governance-agent/

Extracts governance-agent/ at commit ORIGINAL_COMMIT with `git archive` into
a temp dir, runs attacks/original_suite.py in a separate interpreter with
GOV_ROOT pointing at that tree, and writes attacks/results-original.{json,md}
including the commit and a sha256 of every extracted source file.
"""

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile

ORIGINAL_COMMIT = "4293483dbcb14c2a9b89335c93b4e12de8914a59"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=HERE, text=True).strip()


def main():
    blob = subprocess.check_output(["git", "archive", "--format=tar", ORIGINAL_COMMIT, "governance-agent"], cwd=REPO)
    with tempfile.TemporaryDirectory() as tmp:
        tarfile.open(fileobj=io.BytesIO(blob)).extractall(tmp)
        root = os.path.join(tmp, "governance-agent")
        provenance = {}
        for dirpath, _, files in os.walk(root):
            for f in sorted(files):
                if f.endswith((".py", ".json")) and "/evals/audit" not in dirpath:
                    path = os.path.join(dirpath, f)
                    provenance[os.path.relpath(path, root)] = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
        env = dict(os.environ, GOV_ROOT=root, PYTHONDONTWRITEBYTECODE="1")
        out = subprocess.run([sys.executable, os.path.join(HERE, "original_suite.py")], cwd=root,
                             capture_output=True, text=True, env=env)
        if out.returncode != 0:
            sys.exit(f"original suite crashed:\n{out.stderr[-3000:]}")
        rows = json.loads(out.stdout.strip().splitlines()[-1])

    with open(os.path.join(HERE, "results-original.json"), "w") as fh:
        json.dump({"commit": ORIGINAL_COMMIT, "source_sha256": provenance, "results": rows}, fh, indent=2)
    counts = {k: sum(r["outcome"] == k for r in rows) for k in ("PASS", "GAP", "BYPASS")}
    icon = {"PASS": "✅ PASS", "GAP": "🟡 GAP", "BYPASS": "❌ BYPASS"}
    lines = [f"Architecture under test: commit `{ORIGINAL_COMMIT[:7]}` (original, unmodified).", "",
             "| Group | Attack | Outcome | Reachable by | Evidence |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['group']} | {r['attack']} | {icon[r['outcome']]} | {r['scope']} | {r['evidence'].replace('|', '/')} |")
    lines.append(f"\n**{counts['PASS']} PASS · {counts['GAP']} GAP · {counts['BYPASS']} BYPASS** (of {len(rows)})")
    report = "\n".join(lines)
    with open(os.path.join(HERE, "results-original.md"), "w") as fh:
        fh.write("# Attack results — ORIGINAL architecture\n\n" + report + "\n")
    print(report)


if __name__ == "__main__":
    main()
