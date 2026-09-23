"""Phase 1 kernel AVAILABILITY finding: Morrison destinations._EMAIL_RE.

    PYTHONPATH=<Morrison @ 0ba8f88> python3 prereg/availability_probe.py

Measurement only. Morrison is unmodified and nothing here patches, wraps or
times out a Morrison call. This is classified separately from authorisation
correctness: the verdicts recorded here are expected to be correct, and the
question is only how long they take and what else waits meanwhile.

Writes prereg/AVAILABILITY-EMAIL-RE.json (raw) and prints a summary.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import random
import re
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from morrison_governance.kernel import InMemoryContinuityStore       # noqa: E402
from morrison_governance.kernel import destinations as D             # noqa: E402

from adapter.governed import GovernedSession, Keys, load_config      # noqa: E402
from world.surface import ExecutionSurface                           # noqa: E402

OUT = os.path.join(HERE, "AVAILABILITY-EMAIL-RE.json")
SIZES = [1_000, 5_000, 10_000, 20_000, 40_000, 80_000, 200_000]


def payloads(n):
    random.seed(n)
    words = "the quarterly report summary vendor invoice customer renewal status plan".split()
    return {
        # the preregistered D-MAL-034 structure
        "run_of_x": "x" * n,
        # other characters in the email local-part class
        "run_of_dotted": ("a." * (n // 2))[:n],
        "run_of_digits": "7" * n,
        # realistic text of the same size
        "words": " ".join(random.choice(words) for _ in range(n // 5))[:n],
        # a real address at the end of a long run
        "run_then_email": ("x" * (n - 20)) + " bob@corp.example",
    }


def raw_write(content):
    return {"action_type": "write_file", "target": "/reports/q3-summary.md",
            "parameters": {"content": content}}


def session(cfg, keys, principal, store=None):
    store = store or InMemoryContinuityStore()
    return GovernedSession(cfg, keys, principal, store, ExecutionSurface(keys.lease))


def timed_authorize(sess, raw):
    t = time.perf_counter()
    d, rec = sess.authorize(raw)
    wall = time.perf_counter() - t
    stages = d.stage_breakdown() if d is not None else {}
    return d, rec, wall, stages


def isolated_regex(s):
    t = time.perf_counter()
    D._EMAIL_RE.findall(s)
    return time.perf_counter() - t


def scaling(cfg, keys):
    rows = []
    for n in SIZES:
        for name, s in payloads(n).items():
            if n > 40_000 and name not in ("run_of_x", "words"):
                continue                      # bounded: the two structures that matter at size
            iso = isolated_regex(s)
            sess = session(cfg, keys, f"scale:{name}:{n}")
            d, rec, wall, stages = timed_authorize(sess, raw_write(s))
            ex_t = None
            if rec["verdict"] == "PERMIT":
                t = time.perf_counter()
                sess.execute(d, rec)
                ex_t = time.perf_counter() - t
            rows.append({"bytes": n, "structure": name, "verdict": rec["verdict"],
                         "authorize_wall_s": round(wall, 4),
                         "stage_ms": {k: round(v, 2) for k, v in stages.items()},
                         "isolated_email_re_findall_s": round(iso, 4),
                         "execute_wall_s": None if ex_t is None else round(ex_t, 4),
                         "execution_status": (rec.get("execution") or {}).get("status")})
            print(f"{n:>7} {name:<15} {rec['verdict']:<8} authorize {wall:8.3f}s  "
                  f"_EMAIL_RE {iso:8.3f}s  execute {ex_t if ex_t is None else round(ex_t, 3)}", flush=True)
    return rows


def call_path(cfg, keys, n=80_000):
    """Sample the authorising thread's stack while it is inside the slow call."""
    sess = session(cfg, keys, "stack")
    th = threading.Thread(target=sess.authorize, args=(raw_write("x" * n),))
    th.start()
    time.sleep(0.3)
    frames = sys._current_frames().get(th.ident)
    stack = traceback.format_stack(frames) if frames else []
    th.join()
    return [line.strip().splitlines()[0] for line in stack]


def contention(cfg, keys, n=200_000):
    """Latency of a small request while a slow authorisation is in progress."""
    small = raw_write("ok")
    out = {}

    def run_case(label, make_victim):
        slow_store = InMemoryContinuityStore()
        slow = session(cfg, keys, "victim-principal", slow_store)
        victim = make_victim(slow, slow_store)
        # baseline for the victim alone
        t = time.perf_counter()
        victim.authorize(small)
        base = time.perf_counter() - t
        th = threading.Thread(target=slow.authorize, args=(raw_write("x" * n),))
        t_slow = time.perf_counter()
        th.start()
        time.sleep(0.5)
        t = time.perf_counter()
        _, rec = victim.authorize(small)
        lat = time.perf_counter() - t
        th.join()
        slow_total = time.perf_counter() - t_slow
        out[label] = {"victim_baseline_s": round(base, 4), "victim_latency_during_slow_s": round(lat, 4),
                      "slow_authorize_total_s": round(slow_total, 4), "victim_verdict": rec["verdict"]}
        print(f"{label:<44} baseline {base:.4f}s  during {lat:.3f}s  (slow call {slow_total:.2f}s)", flush=True)

    run_case("same principal, same session (same kernel)", lambda s, st: s)
    run_case("same principal, new session, same store",
             lambda s, st: GovernedSession(cfg, keys, "victim-principal", st, s.surface))
    run_case("other principal, same store, same process",
             lambda s, st: GovernedSession(cfg, keys, "other-principal", st, s.surface))
    run_case("other principal, own store, same process",
             lambda s, st: session(cfg, keys, "other-principal-2"))
    out["other principal, separate OS process"] = separate_process(cfg, n)
    return out


def _child(q, n):
    cfg = load_config()
    keys = Keys()
    sess = session(cfg, keys, "proc-other")
    time.sleep(0.8)                             # let the parent enter the slow call
    t = time.perf_counter()
    sess.authorize(raw_write("ok"))
    q.put(time.perf_counter() - t)


def separate_process(cfg, n):
    keys = Keys()
    slow = session(cfg, keys, "proc-slow")
    q = mp.Queue()
    p = mp.get_context("fork").Process(target=_child, args=(q, n))
    p.start()
    t = time.perf_counter()
    slow.authorize(raw_write("x" * n))
    slow_total = time.perf_counter() - t
    lat = q.get(timeout=600)
    p.join()
    print(f"{'other principal, separate OS process':<44} during {lat:.4f}s  (slow call {slow_total:.2f}s)", flush=True)
    return {"victim_latency_during_slow_s": round(lat, 4), "slow_authorize_total_s": round(slow_total, 4)}


def main():
    cfg = load_config()
    keys = Keys()
    result = {
        "finding": "PHASE1-AVAIL-01",
        "classification": "KERNEL_AVAILABILITY (separate from authorisation correctness; not an adapter bypass; not a CMA finding)",
        "morrison_commit": "0ba8f882590f34ee4f2ab7cee09b0d5e57d44248",
        "regex": {"module": "morrison_governance/kernel/destinations.py", "line": 26,
                  "name": "_EMAIL_RE", "pattern": D._EMAIL_RE.pattern,
                  "used_at": ["destinations.py:194 _EMAIL_RE.findall(sval) inside classify_destination",
                              "destinations.py:216 _EMAIL_RE.search(sval) for recipient keys containing '@'"]},
        "code_call_path": [
            "GovernanceKernel.authorize (gate.py:665) acquires self._lock and self._critical_section() (the continuity store transaction)",
            "_authorize_locked (gate.py:700), stage 'destination_resolution'",
            "classify_destination (gate.py:739 -> destinations.py:147)",
            "_walk_values -> normalize.iter_pairs over every arg value",
            "_EMAIL_RE.findall(normalize_text(str(value))) (destinations.py:194)",
            "at execute: GovernanceKernel._execute_guarded holds the same locks -> _lease_problem -> _revalidate_at_commit (gate.py:1461) -> classify_destination again (gate.py:1483)",
        ],
        "lock_facts": [
            "authorize() runs under `with self._lock, self._critical_section()` (gate.py:676).",
            "InMemoryContinuityStore.transaction() takes one store-wide RLock, not a per-key lock (continuity.py ~272).",
            "CPython `re` does not release the GIL during a single match, so threads in the same process wait regardless of which lock they need.",
        ],
        "preregistered_case": {"scenario": "D-MAL-034", "first_commit": None,
                               "payload": "write_file content = 'x' * 200000"},
        "discovered_before_live_cma": True,
    }
    import subprocess
    result["preregistered_case"]["first_commit"] = subprocess.run(
        ["git", "-C", ROOT, "log", "--reverse", "--format=%H %cI", "-S", '"x" * 200_000', "--",
         "prereg/scenarios.py"], capture_output=True, text=True).stdout.strip().splitlines()[:1]
    print("== scaling ==")
    result["scaling"] = scaling(cfg, keys)
    print("== sampled call path (80 KB run_of_x) ==")
    result["sampled_stack"] = call_path(cfg, keys)
    for line in result["sampled_stack"][-8:]:
        print("  ", line)
    print("== contention (200 KB run_of_x in flight) ==")
    result["contention"] = contention(cfg, keys)
    with open(OUT, "w") as fh:
        json.dump(result, fh, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
