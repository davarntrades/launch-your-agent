"""Client-side loop: Worker proposals -> Governor -> Executor -> audit log.

    python3 driver.py scripted [proposals.json]   # no network, no key
    python3 driver.py live                        # CMA session (needs .env + IDS.env from launch.sh)

In live mode the Worker is a Claude Managed Agent whose only tool is the
custom tool `propose_action`. Each call idles the session with
`requires_action`; this loop runs the Governor on the proposal, lets the
Executor apply it only on AUTHORIZE, writes the audit entry, and returns the
verdict as `user.custom_tool_result`. The Governor never runs inside the
model's sandbox, so the Worker has no path to the real state except through it.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from governor import Pipeline, initial_state  # noqa: E402

BASE = "https://api.anthropic.com/v1"


def state_summary(state):
    return {
        "budget": {k: state["budget"][k] for k in ("ceiling_cents", "spent_cents")},
        "files": sorted(state["files"]),
        "trash": sorted(state["trash"]),
        "roles_by_principal": {p: v["roles"] for p, v in state["principals"].items()},
        "outbox_count": len(state["outbox"]),
    }


def tool_result(entry):
    return json.dumps({
        "id": entry["proposal"]["id"],
        "verdict": entry["verdict"],
        "violated": entry["violated"],
        "reasons": entry["reasons"],
        "state_summary": state_summary(entry["state_after"]),
    })


def print_entry(entry):
    p = entry["proposal"]
    extra = f"  [{', '.join(entry['violated'])}]" if entry["violated"] else ""
    print(f"{p['id']:>10}  {entry['verdict']:<9} {p['action_type']:<14} {p['target']}{extra}")


# ── scripted mode ───────────────────────────────────────────────────────
def run_scripted(path):
    with open(path) as fh:
        proposals = json.load(fh)
    os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
    pipe = Pipeline(initial_state(), audit_path=os.path.join(HERE, "runs", "scripted-audit.jsonl"))
    for p in proposals:
        print_entry(pipe.submit(p))
    print(f"\npending escalations: {sorted(pipe.pending)}")
    print(f"audit log: runs/scripted-audit.jsonl ({len(pipe.audit.entries)} entries)")


# ── live mode (CMA) ─────────────────────────────────────────────────────
def load_env(path):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


def api(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "managed-agents-2026-04-01",
            "content-type": "application/json",
        })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.JSONDecoder(strict=False).decode(resp.read().decode())
    except urllib.error.HTTPError as exc:
        sys.exit(f"{method} {path} -> {exc.code}: {exc.read().decode()[:500]}")


def run_live():
    load_env(os.path.join(HERE, ".env"))
    load_env(os.path.join(HERE, "IDS.env"))
    for k in ("ANTHROPIC_API_KEY", "AGENT_ID", "AGENT_VERSION", "ENV_ID"):
        if not os.environ.get(k):
            sys.exit(f"{k} missing — run ./launch.sh first")

    state = initial_state()
    task = open(os.path.join(HERE, "first_prompt.txt")).read()
    task += "\n\nCurrent mock state:\n" + json.dumps(state_summary(state), indent=2)
    rubric = open(os.path.join(HERE, "outcome.md")).read()

    session = api("POST", "/sessions", {
        "agent": {"type": "agent", "id": os.environ["AGENT_ID"], "version": int(os.environ["AGENT_VERSION"])},
        "environment_id": os.environ["ENV_ID"],
        "title": "governed run",
        "initial_events": [{"type": "user.define_outcome", "description": task,
                            "rubric": {"type": "text", "content": rubric}, "max_iterations": 3}],
    })
    sid = session["id"]
    run_dir = os.path.join(HERE, "runs", sid)
    os.makedirs(run_dir, exist_ok=True)
    pipe = Pipeline(state, audit_path=os.path.join(run_dir, "audit.jsonl"))
    print(f"session {sid}\nconsole https://platform.claude.com/workspaces/default/sessions/{sid}\n")

    answered = set()
    while True:
        s = api("GET", f"/sessions/{sid}")
        status, stop = s.get("status"), (s.get("stop_reason") or {})
        if status == "idle" and not stop:  # stop_reason is carried on the session.status_idle event
            idles = api("GET", f"/sessions/{sid}/events?types[]=session.status_idle").get("data", [])
            stop = (idles[-1].get("stop_reason") or {}) if idles else {}
        if status == "idle" and stop.get("type") == "requires_action":
            events = api("GET", f"/sessions/{sid}/events?types[]=agent.custom_tool_use").get("data", [])
            requested_ids = set(stop.get("event_ids") or [e["id"] for e in events])
            results = []
            for ev in events:
                if ev["id"] in requested_ids and ev["id"] not in answered:
                    proposal = dict(ev.get("input", {}), id=ev["id"])
                    entry = pipe.submit(proposal)
                    print_entry(entry)
                    results.append({"type": "user.custom_tool_result", "custom_tool_use_id": ev["id"],
                                    "content": [{"type": "text", "text": tool_result(entry)}]})
                    answered.add(ev["id"])
            if results:
                api("POST", f"/sessions/{sid}/events", {"events": results})
        elif status == "idle" or status == "terminated":
            break
        time.sleep(3)

    evals = s.get("outcome_evaluations", [])
    with open(os.path.join(run_dir, "session.json"), "w") as fh:
        json.dump({"session_id": sid, "status": status, "stop_reason": stop, "outcome_evaluations": evals,
                   "usage": s.get("usage"), "pending_escalations": sorted(pipe.pending)}, fh, indent=2)
    print(f"\nstatus {status} · outcome {[e.get('result') for e in evals]}")
    print(f"pending escalations: {sorted(pipe.pending)}\naudit log: runs/{sid}/audit.jsonl")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "scripted"
    if mode == "live":
        run_live()
    else:
        run_scripted(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "evals", "scripted_run.json"))
