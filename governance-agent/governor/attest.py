"""Attestation of the Worker's CMA configuration and its event stream.

The Governor mediates only what reaches it. These checks establish that the
Worker has no other effect channel:

  check_agent(agent)        tools == [custom propose_action] with the exact
                            schema; no agent_toolset / mcp_toolset; no
                            mcp_servers, skills or multiagent.
  check_environment(env)    networking limited, no hosts, no MCP, no package
                            managers.
  check_session(session)    no vaults, no resources; embedded agent config
                            (if returned) passes check_agent.
  split_events(events)      partitions agent events into mediated proposals
                            and anything that ran outside the Governor.

Each check returns a list of problems; an empty list means the check passed.
"""

from .actions import PROPOSAL_INPUT_SCHEMA

TOOL_NAME = "propose_action"
UNMEDIATED_EVENT_TYPES = ("agent.tool_use", "agent.mcp_tool_use", "agent.tool_result", "agent.mcp_tool_result")


def _schema_core(schema):
    """The parts of the schema that define the proposal surface (server-added
    annotations such as descriptions are ignored; normalize() re-checks inputs anyway)."""
    props = schema.get("properties") or {}
    return (sorted(props), sorted((props.get("action_type") or {}).get("enum") or []),
            sorted(schema.get("required") or []))


def check_agent(agent):
    problems = []
    tools = agent.get("tools") or []
    if len(tools) != 1:
        problems.append(f"expected exactly 1 tool, found {len(tools)}: {[t.get('type') for t in tools]}")
    for t in tools:
        if t.get("type") != "custom":
            problems.append(f"server-executed tool type {t.get('type')!r} present")
        elif t.get("name") != TOOL_NAME:
            problems.append(f"unexpected custom tool {t.get('name')!r}")
        elif _schema_core(t.get("input_schema") or {}) != _schema_core(PROPOSAL_INPUT_SCHEMA):
            problems.append("propose_action input_schema differs from governor.actions.PROPOSAL_INPUT_SCHEMA")
    for field in ("mcp_servers", "skills"):
        if agent.get(field):
            problems.append(f"{field} must be empty, found {agent.get(field)!r}")
    if agent.get("multiagent"):
        problems.append("multiagent must be absent")
    return problems


def check_environment(env):
    cfg = env.get("config", env)
    net = cfg.get("networking") or {}
    problems = []
    if net.get("type") != "limited":
        problems.append(f"networking must be limited, found {net.get('type')!r}")
    if net.get("allowed_hosts"):
        problems.append(f"allowed_hosts must be empty, found {net.get('allowed_hosts')}")
    for flag in ("allow_mcp_servers", "allow_package_managers"):
        if net.get(flag):
            problems.append(f"{flag} must be false")
    return problems


def check_session(session):
    problems = []
    if session.get("vault_ids"):
        problems.append(f"vault_ids must be empty, found {session['vault_ids']}")
    if session.get("resources"):
        problems.append(f"resources must be empty, found {len(session['resources'])}")
    agent = session.get("agent")
    if isinstance(agent, dict) and "tools" in agent:
        problems += [f"session agent: {p}" for p in check_agent(agent)]
    return problems


def split_events(events):
    """Return (proposals, violations).

    proposals   [(event_id, input)] for agent.custom_tool_use named propose_action
    violations  descriptions of any tool activity that did not go through it
    Text in agent.message events is never parsed into a proposal.
    """
    proposals, violations = [], []
    for ev in events:
        et = ev.get("type")
        if et == "agent.custom_tool_use":
            if ev.get("name") == TOOL_NAME:
                proposals.append((ev["id"], ev.get("input", {})))
            else:
                violations.append(f"custom tool {ev.get('name')!r} ({ev.get('id')}) is not propose_action")
        elif et in UNMEDIATED_EVENT_TYPES:
            violations.append(f"{et} {ev.get('name')!r} ({ev.get('id')}) ran outside the Governor")
    return proposals, violations
