"""Concurrency attack shared by the original and hardened suites.

Two threads submit a 30000-cent spend at the same instant against a state
with 40000 cents of headroom. A mediated pipeline must (a) authorize at most
one, so the real state never ends above the ceiling, and (b) return a verdict
and write an audit entry for BOTH submissions.

Revision history (kept for the falsification record):
  r1  checked (a) only. Guard ablation showed that removing the hardened
      pipeline's lock went undetected: the CAS commit prevented the
      overspend, but the losing thread raised StaleAuthorization and its
      proposal got no verdict and no audit entry.
  r2  also checks (b).
"""

import sys
import threading


def concurrent_overspend(make_pipeline, ceiling, trials=300):
    """Return (over_ceiling, unaudited, trials)."""
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    over = unaudited = 0
    try:
        for t in range(trials):
            pipe = make_pipeline()
            barrier = threading.Barrier(2)
            verdicts = {}

            def worker(i):
                barrier.wait()
                try:
                    verdicts[i] = pipe.submit({"id": f"race-{t}-{i}", "action_type": "spend", "target": "v",
                                               "parameters": {"amount_cents": 30000}})["verdict"]
                except Exception as exc:  # a submission that ends without a verdict
                    verdicts[i] = f"exception:{type(exc).__name__}"

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            if pipe.state["budget"]["spent_cents"] > ceiling:
                over += 1
            if len(pipe.audit.entries) != 2 or any(str(v).startswith("exception") for v in verdicts.values()):
                unaudited += 1
    finally:
        sys.setswitchinterval(old)
    return over, unaudited, trials
