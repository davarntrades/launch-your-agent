"""PHASE1-AVAIL-01 contention measurement, v0.1 (corrects harness defect H-5).

v0 started the victim's timer only when the measuring thread next obtained
the GIL, which CPython's `re` holds for an entire `findall`. v0.1 measures
every victim from its PLANNED issue time, records how late its thread actually
woke, and runs cross-process cases with a shared FileContinuityStore.

    PYTHONPATH=<Morrison @ 0ba8f88> python3 prereg/availability_contention_v01.py

Measurement only; Morrison unmodified. Writes prereg/AVAILABILITY-CONTENTION-v0.1.json.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from morrison_governance.kernel import FileContinuityStore, InMemoryContinuityStore  # noqa: E402

from adapter.governed import GovernedSession, Keys, load_config   # noqa: E402
from world.surface import ExecutionSurface                        # noqa: E402

OUT = os.path.join(HERE, "AVAILABILITY-CONTENTION-v0.1.json")
N = 200_000                     # the preregistered D-MAL-034 size
ISSUE_AFTER = 1.0               # victim is issued this long after the slow call starts


def write(content):
    return {"action_type": "write_file", "target": "/reports/q3-summary.md",
            "parameters": {"content": content}}


def sess(cfg, keys, principal, store):
    return GovernedSession(cfg, keys, principal, store, ExecutionSurface(keys.lease))


def thread_case(label, cfg, keys, make):
    store = InMemoryContinuityStore()
    slow = sess(cfg, keys, "slow-principal", store)
    victim = make(cfg, keys, slow, store)
    victim.authorize(write("warm"))                         # warm-up / baseline
    t = time.time(); victim.authorize(write("ok")); base = time.time() - t
    box = {}

    def victim_thread(t_plan):
        now = time.time()
        box["late_wake_s"] = now - t_plan
        _, rec = victim.authorize(write("ok"))
        box["done"] = time.time()
        box["verdict"] = rec["verdict"]

    t0 = time.time()
    s = threading.Thread(target=slow.authorize, args=(write("x" * N),))
    s.start()
    t_plan = t0 + ISSUE_AFTER
    v = threading.Timer(ISSUE_AFTER, victim_thread, args=(t_plan,))
    v.start()
    s.join(); t_slow_done = time.time()
    v.join()
    row = {"case": label, "victim_baseline_s": round(base, 4),
           "victim_issued_at_s": ISSUE_AFTER,
           "victim_thread_woke_late_by_s": round(box["late_wake_s"], 3),
           "victim_latency_from_planned_issue_s": round(box["done"] - t_plan, 3),
           "slow_authorize_s": round(t_slow_done - t0, 3),
           "victim_finished_before_slow_call": box["done"] < t_slow_done,
           "victim_verdict": box["verdict"]}
    print(json.dumps(row), flush=True)
    return row


def _proc(role, principal, store_path, t0, q):
    cfg = load_config()
    keys = Keys()
    store = FileContinuityStore(store_path) if store_path else InMemoryContinuityStore()
    s = sess(cfg, keys, principal, store)
    s.authorize(write("warm"))
    if role == "slow":
        while time.time() < t0:
            time.sleep(0.001)
        s.authorize(write("x" * N))
        q.put(("slow", time.time() - t0))
    else:
        t_plan = t0 + ISSUE_AFTER
        while time.time() < t_plan:
            time.sleep(0.001)
        _, rec = s.authorize(write("ok"))
        q.put(("victim", time.time() - t_plan, rec["verdict"]))


def process_case(label, victim_principal, shared_file):
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "continuity.jsonl") if shared_file else None
        t0 = time.time() + 2.0
        a = ctx.Process(target=_proc, args=("slow", "slow-principal", path, t0, q))
        b = ctx.Process(target=_proc, args=("victim", victim_principal, path, t0, q))
        a.start(); b.start()
        got = {}
        for _ in range(2):
            m = q.get(timeout=900)
            got[m[0]] = m
        a.join(); b.join()
    row = {"case": label, "victim_issued_at_s": ISSUE_AFTER,
           "victim_latency_from_planned_issue_s": round(got["victim"][1], 3),
           "slow_authorize_s": round(got["slow"][1], 3),
           "victim_verdict": got["victim"][2],
           "store": "shared FileContinuityStore" if shared_file else "own InMemoryContinuityStore"}
    print(json.dumps(row), flush=True)
    return row


def main():
    cfg = load_config()
    keys = Keys()
    rows = [
        thread_case("thread: same principal, same kernel", cfg, keys, lambda c, k, s, st: s),
        thread_case("thread: same principal, new session, same in-memory store", cfg, keys,
                    lambda c, k, s, st: GovernedSession(c, k, "slow-principal", st, s.surface)),
        thread_case("thread: other principal, same in-memory store", cfg, keys,
                    lambda c, k, s, st: GovernedSession(c, k, "other-principal", st, s.surface)),
        thread_case("thread: other principal, own in-memory store", cfg, keys,
                    lambda c, k, s, st: sess(c, k, "other-principal", InMemoryContinuityStore())),
        process_case("process: other principal, own store", "other-principal", shared_file=False),
        process_case("process: same principal, shared FileContinuityStore", "slow-principal", shared_file=True),
        process_case("process: other principal, shared FileContinuityStore", "other-principal", shared_file=True),
    ]
    out = {"finding": "PHASE1-AVAIL-01", "probe_version": "contention v0.1 (corrects H-5)",
           "payload": f"write_file content = 'x' * {N}", "cpu_count": os.cpu_count(),
           "python": sys.version.split()[0], "rows": rows}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
