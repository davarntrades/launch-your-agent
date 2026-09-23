"""Check that the attack suite detects a removed guard.

    python3 attacks/mutation_check.py

Each mutation disables one boundary guard, re-runs the attack suite in a
subprocess and expects at least one attack to report OPEN. A mutation that
leaves every attack blocked means the suite does not cover that guard.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MUTATIONS = {
    "no frame condition": "import governor.governor as g; g.FOOTPRINT = {k: {'budget','files','trash','roles','principals','aliases','forwarding','outbox'} for k in g.FOOTPRINT}",
    "commit skips state digest": "import governor.pipeline as p, governor.state as s\n"
                                 "def commit(self, a, pr, st): self._state = s.clone(st)\n"
                                 "p.Executor.commit = commit",
    "ids reusable": "import governor.pipeline as p; p.Pipeline._seen_ids = property(lambda self: set(), lambda self, v: None)",
    "any custom tool accepted": "import governor.attest as a, driver\n"
                                "orig = a.split_events\n"
                                "def split(evs): return [(e['id'], e.get('input', {})) for e in evs if e.get('type') == 'agent.custom_tool_use'], []\n"
                                "driver.split_events = split",
    "no attestation": "import driver; driver.check_agent = lambda a: []; driver.check_environment = lambda e: []",
    "first event page only": "import driver; driver.list_events = lambda sid: driver.api('GET', f'/sessions/{sid}/events').get('data', [])",
    "state handle leaks": "import governor.pipeline as p; p.Executor.snapshot = lambda self: self._state",
    "extra proposal keys allowed": "import governor.actions as a; a.PROPOSAL_KEYS |= {'verdict','state','authorization'}",
    "policy mutable": "import governor.state as s\n"
                      "class P(dict):\n"
                      "  def __init__(self, c, r, b): super().__init__(); self.ceiling_cents=c; self.recipient_allowlist=set(r); self.baseline_permissions={k:frozenset(v) for k,v in b.items()}\n"
                      "  def as_dict(self): return {'c': self.ceiling_cents, 'r': sorted(self.recipient_allowlist)}\n"
                      "s.Policy = P",
}

RUNNER = """
import sys, runpy
sys.path.insert(0, {root!r}); sys.path.insert(0, {here!r})
{patch}
sys.argv = ['run_attacks.py']
runpy.run_path({script!r}, run_name='__main__')
"""


def main():
    undetected = []
    for name, patch in MUTATIONS.items():
        code = RUNNER.format(root=ROOT, here=HERE, patch=patch, script=os.path.join(HERE, "run_attacks.py"))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env=env)
        opened = [line.split("|")[2].strip() for line in out.stdout.splitlines() if "❌ OPEN" in line]
        status = f"detected by {len(opened)} attack(s): {opened[0]}" if opened else "NOT DETECTED"
        if not opened:
            undetected.append(name)
        print(f"- {name}: {status}")
    # results.json/md were overwritten by the mutated runs; restore the clean report
    subprocess.run([sys.executable, os.path.join(HERE, "run_attacks.py")], cwd=ROOT, capture_output=True)
    sys.exit(1 if undetected else 0)


if __name__ == "__main__":
    main()
