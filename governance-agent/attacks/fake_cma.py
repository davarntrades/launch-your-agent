"""In-process stand-in for the CMA API, used to drive driver.run_live() with
scripted (including hostile) session event streams. No network.

A script is a list of ticks. Each GET /sessions/{id} advances one tick; the
following GET /sessions/{id}/events returns the cumulative events of all
ticks so far (the real endpoint returns the full history).
"""

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import driver  # noqa: E402


def good_agent():
    a = json.load(open(os.path.join(ROOT, "agent.json")))
    return dict(a, id="agent_fake", version=1, model={"id": "claude-opus-5-5"})


def good_env():
    return dict(json.load(open(os.path.join(ROOT, "environment.json"))), id="env_fake")


def tool_use(eid, tool_input, name="propose_action", etype="agent.custom_tool_use"):
    return {"id": eid, "type": etype, "name": name, "input": tool_input}


def requires_action(*ids):
    return {"status": "idle", "stop_reason": {"type": "requires_action", "event_ids": list(ids)}}


END = {"status": "idle", "stop_reason": {"type": "end_turn"}}


class FakeCMA:
    def __init__(self, ticks, agent=None, env=None, page_size=None):
        self.page_size = page_size
        self.ticks = ticks            # [(session_patch, [new events])]
        self.agent = agent or good_agent()
        self.env = env or good_env()
        self.i = -1
        self.events = []
        self.posted = []              # (path, body) of every POST
        self.session_create_body = None

    def session(self):
        base = {"id": "sesn_fake", "status": "running", "vault_ids": [], "resources": [],
                "agent": copy.deepcopy(self.agent), "outcome_evaluations": []}
        if self.i >= 0 and self.ticks:
            base.update(copy.deepcopy(self.ticks[min(self.i, len(self.ticks) - 1)][0]))
        return base

    def __call__(self, method, path, body=None):
        if method == "POST":
            self.posted.append((path, copy.deepcopy(body)))
        if method == "GET" and path.startswith("/agents/"):
            return copy.deepcopy(self.agent)
        if method == "GET" and path.startswith("/environments/"):
            return copy.deepcopy(self.env)
        if method == "POST" and path == "/sessions":
            self.session_create_body = copy.deepcopy(body)
            return self.session()
        if method == "GET" and path == "/sessions/sesn_fake":
            self.i += 1
            if self.i >= len(self.ticks) + 3:   # script exhausted: end the session instead of idling forever
                return dict(self.session(), status="terminated", stop_reason={"type": "script_exhausted"})
            if self.i < len(self.ticks):
                self.events += copy.deepcopy(self.ticks[self.i][1])
                self.ticks[self.i] = (self.ticks[self.i][0], [])  # deliver each event once
            return self.session()
        if method == "GET" and path.startswith("/sessions/sesn_fake/events"):
            if not self.page_size:
                return {"data": copy.deepcopy(self.events)}
            start = 0
            if "after_id=" in path:
                after = path.split("after_id=")[1]
                start = [e["id"] for e in self.events].index(after) + 1
            page = self.events[start:start + self.page_size]
            return {"data": copy.deepcopy(page), "has_more": start + self.page_size < len(self.events),
                    "last_id": page[-1]["id"] if page else None}
        if method == "POST" and path == "/sessions/sesn_fake/events":
            return {"data": []}
        raise AssertionError(f"unexpected call {method} {path}")


def run(fake):
    """Run driver.run_live against `fake`. Returns (pipeline or None, halted_reason or None)."""
    holder = {}
    os.environ.update(ANTHROPIC_API_KEY="fake", AGENT_ID="agent_fake", AGENT_VERSION="1", ENV_ID="env_fake")
    orig_api, orig_sleep = driver.api, driver.time.sleep
    driver.api, driver.time.sleep = fake, (lambda _s: None)
    halted = None
    try:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            driver.run_live(on_pipeline=lambda p: holder.setdefault("pipe", p))
    except SystemExit as exc:
        halted = str(exc.code)
    finally:
        driver.api, driver.time.sleep = orig_api, orig_sleep
    return holder.get("pipe"), halted
