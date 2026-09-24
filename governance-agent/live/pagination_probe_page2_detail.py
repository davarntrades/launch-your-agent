"""Fetch the FULL, untrimmed content of the 9 events on page 2 of session
sesn_01KxSMqHSa28y7quCNRtC6uA (the events invisible to driver.list_events,
established in read-back run 2, job 107433654876).

Two GET calls only (page 1 to get next_page, then page 2 itself). No new
propose_action calls. Prints raw content so the missing
agent.custom_tool_use / user.custom_tool_result pair can be inspected
directly: the tool_result's content is exactly the Governor's own
serialized verdict (driver.tool_result()'s output), so reading it
establishes directly whether the Governor mediated this specific proposal,
independent of any event-reader.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import campaign  # noqa: E402
import driver  # noqa: E402

SESSION_ID = os.environ.get("SESSION_ID", "sesn_01KxSMqHSa28y7quCNRtC6uA")


def main() -> None:
    driver.load_env(os.path.join(ROOT, ".env"))
    driver.load_env(os.path.join(ROOT, "IDS.env"))
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY missing")

    st1, d1, rid1 = campaign.http("GET", f"/sessions/{SESSION_ID}/events?limit=1000")
    print("page 1:", st1, rid1, "data_count", len(d1.get("data", [])), "next_page present:", bool(d1.get("next_page")))
    if not campaign.ok(st1) or not d1.get("next_page"):
        sys.exit(f"cannot reach page 2: status={st1} next_page={d1.get('next_page')!r}")

    next_page = d1["next_page"]
    import urllib.parse
    st2, d2, rid2 = campaign.http(
        "GET", f"/sessions/{SESSION_ID}/events?limit=1000&page={urllib.parse.quote(next_page)}")
    print("\npage 2:", st2, rid2, "data_count", len(d2.get("data", [])))
    if not campaign.ok(st2):
        sys.exit(f"page 2 fetch failed: {st2} {json.dumps(campaign.trim(d2, 800))}")

    print("\n--- full raw content of every page-2 event ---")
    for e in d2.get("data", []):
        print(json.dumps(e, indent=2, default=str))
        print("---")

    print("\n--- specifically, the propose_action / tool_result pair (if present) ---")
    for e in d2.get("data", []):
        if e.get("type") in ("agent.custom_tool_use", "user.custom_tool_result"):
            print(f"\n### {e.get('type')} id={e.get('id')} ###")
            print(json.dumps(e, indent=2, default=str))

    print("\n--- p1 vs p2 id overlap check (must be zero for a clean, non-duplicating page boundary) ---")
    p1_ids = {e.get("id") for e in d1.get("data", [])}
    p2_ids = {e.get("id") for e in d2.get("data", [])}
    print(json.dumps({"p1_count": len(p1_ids), "p2_count": len(p2_ids),
                      "overlap_count": len(p1_ids & p2_ids), "overlap_ids": sorted(p1_ids & p2_ids)}))


if __name__ == "__main__":
    main()
