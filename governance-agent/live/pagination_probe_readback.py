"""Read-back follow-up to pagination_probe.py, for one already-run live
session (`sesn_01KxSMqHSa28y7quCNRtC6uA`, GH Actions run 35932071669).

That run's own ground-truth reader FAILED (its single `limit=5000` request
did not succeed, and the code did not retry with a smaller limit) — its
result "A_prototype_misses_events: False" is an ARTEFACT of an empty
ground truth, not a real finding. That failure is preserved as-is in the
original run's evidence; it is not edited or hidden here.

This script does not re-drive the session (111 real proposals were
already answered live and cost real API spend; re-answering is
unnecessary and wasteful). It only re-reads the session's already-settled
event history via two readers:

  - driver.list_events(sid) — the FROZEN prototype reader, imported and
    called verbatim, exactly as in pagination_probe.py.
  - a FIXED ground-truth reader (new code here, not part of the frozen
    prototype) that retries a ladder of `limit` values instead of giving
    up after one failed attempt, then attempts the same next_page cursor
    discovery as before.

Everything is printed to stdout so it lands in the GitHub Actions job
log directly — the artifact-storage host used by the earlier run's
upload is blocked by this environment's own egress policy (403 from the
proxy, confirmed via /root/.ccr/README.md as an organizational denial,
not something to route around), so this script avoids depending on
artifact download at all.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import campaign  # noqa: E402
import driver  # noqa: E402  frozen prototype, imported unmodified
import pagination_probe as PP  # noqa: E402  reuse verify_frozen, compare, EXECUTION_RELEVANT_TYPES

SESSION_ID = os.environ.get("SESSION_ID", "sesn_01KxSMqHSa28y7quCNRtC6uA")
LIMIT_LADDER = (5000, 2000, 1000, 500, 250, 100, 50, 20, None)

# The 111 propose_action event ids this session actually answered, taken
# verbatim from the original run's job log (run 35932071669), in order.
# Used only as an independent cross-check that both readers see the same
# set the driver itself is known to have processed live.
KNOWN_ANSWERED_FROM_ORIGINAL_LOG_TAIL = [
    "sevt_017ZBqjCyxUDYtPCxVgpUJwc", "sevt_01QyXTxtLqThFuZgM5KKcFPC", "sevt_01WWvVrPia7GAdNf8z5qXpVh",
    "sevt_016yf8c7oAezEkA4JsPnZKFL", "sevt_019YGPG4MzTg3W1vrFXXhzbi", "sevt_01PvD1Ls1XUMCBdbhYo6VM4V",
    "sevt_017NGDdgmbC68ZvfDyEk6P5s", "sevt_01VsaQssueHJ4nDyKMHJDhaH", "sevt_0151MtZLMymrr1yoSG5GGggq",
    "sevt_01NjfKhSTEyNGM3o9fx9zE6F", "sevt_015rCs8XxzRrRiz7UKkfLsr8", "sevt_01PADYZJkLHHP67eo1ZupwSQ",
    "sevt_01DmD6xYMX22erVwHRL7yf31", "sevt_01ANgtbgFm3r2ytL8gXKjkcq", "sevt_01WaH2D9GDnqdAfxZnqd54Cs",
    "sevt_01XhWga3VGiBEBWQhrS4eCXf", "sevt_015rntTPodupfqZGdSE6q8dh", "sevt_01VYzN2fT8uzjhYVMcvAEV6s",
    "sevt_01J6nD8H9vKezJPcU1BgShwB", "sevt_01LY9uFTYccxyq85U6QUwx4t", "sevt_014HV2d3hJxV3YoWDMiLvbD4",
    "sevt_016wPUxYbSRUEraDn5CWRneP", "sevt_01PB3fGiNY3Ucysto2SrmAiT", "sevt_01GFW82vQM6JSp9opyoxAaBS",
    "sevt_01NduLqmUUdXThXKxEGEwggM", "sevt_01WgyUuWQyooWtmThATYGd6P", "sevt_01PQraVmK33gyKrEN823DSMi",
    "sevt_01MyAHH3cKesggT6bfGUqv1d", "sevt_01FGM6ehNPPLSFGmsH8L8fDm", "sevt_011SP4th2mjKULRhwzZVvBTk",
    "sevt_01EQK86Vs5eZNLjgXMuofjBv", "sevt_01XzzydEnkyXk8e4kxe5aMHa", "sevt_01AeJbfGFieqVbVHNMEtr9np",
    "sevt_018aWkbwBqVSJNDQjkue6L4P", "sevt_014EjtNxvCcKQAbh2aHkxbAm", "sevt_01J8Z3QVuzKyWUEbQHuW4NgZ",
    "sevt_014psJxdRD85KexWnx1maDSX", "sevt_01HgoDz6Kmc5gJoou9q3uHHa", "sevt_0149vDYCrvg1f3CMXYegrmic",
    "sevt_01VT8UdS86XB5cbYcwNoxzoX", "sevt_01SFJWYJyLkMXCccaCPKCo5J", "sevt_01KYUgaa5rR4bQxWoZPcwnS1",
    "sevt_01APBzb1yCNcK8FhcE8rs3aF", "sevt_01KUxCT74qV1W7Tk6iPpD1M6", "sevt_01MyE4CVk71i3PXcZ91c8GM9",
    "sevt_017j7tPXfrA3wpyGjuKQvrm4", "sevt_01JaZWyXuaMcwzRH7JEPxmWm", "sevt_01NDSNr8Gh8KwenGXXX3mR4e",
    "sevt_01ChtVUZ2rHPJP7b5ogkM9hh", "sevt_01Wthoh35CfG4jfg7sdSnKLT", "sevt_01VdiaMLsUdxdjc5nwyw7bJ4",
    "sevt_017mJZAwSHLLeLfNiAh99kGr", "sevt_01BC32iePMJQCRzXQYAMT7tn", "sevt_01PdaRo4fKAGvRgQYan3qZtv",
    "sevt_01SyGoMLmW6ggLbg5B9GXFA6", "sevt_01AAUjonSPMTtmhqCWB97LLo", "sevt_01QdVq2hTNvA7UqFEaduujft",
    "sevt_01YWJz1S9LxwgrESNyYXmZyg", "sevt_01WbFYaN8vyZt5pfprD5Lsk6", "sevt_01NfSn8mZMHJ4V6GAGqEH7BS",
    "sevt_01LSQmvDjjHARnsmMrtXWEny", "sevt_01AfiSmR7haMjEheZw8ogeoj", "sevt_01JPArCAwKvQ3Ps6EhPF2y2B",
    "sevt_01BN3uFXh8DYE7RHMRKZe74y", "sevt_01XU4Pr5JFJzQUXyf4PLYuxL", "sevt_01WCx11nFez5hQAcYFqWGPX3",
    "sevt_01ARAHqjw3S5tTBjR6oDLoLu", "sevt_017wbxzfY7Hn7xCGokKexbPZ", "sevt_01A6mWDJa8hV7PJM7SoQ2kpX",
    "sevt_01YU7BVwSc6NFR1jBU1nVy7q", "sevt_01Pr5nR9TgNnbTJVkr5y6jRn", "sevt_014sW7JrubGPcSzK3BUbwG9y",
    "sevt_012dBH7QtAs2LRhR4HxgFefz", "sevt_01Dyk1e3RivJPXWHardxmkFR", "sevt_01CTdb7ZSBpfMUhXsP82Es4C",
    "sevt_01ViMVqmdBfm9gTCq8xHKj6j", "sevt_01SUDr7NPYmPJdXRRK34rtmr", "sevt_01N2U3XnBLUjSBiqVr7PhJKT",
    "sevt_01SPXcp9oXLQNQ3is2dtkpuz", "sevt_01SjKVbqR4MiidX273D2jAaK", "sevt_01KKW7zqLPWZNqVbaZ52R4Kf",
    "sevt_012ndPxhVrcKZu9LDjxuBoHK", "sevt_015A9Ucqcuh6SSGo4LrXEzcv", "sevt_01QM7oKNMLTN7myYxoQgDByL",
    "sevt_01CoN4dbicaBc2eqmZfAuW4Y", "sevt_014HUZCjeQeYide11YoqQerG", "sevt_01N5raReAp9voXPjDSUB3BS6",
    "sevt_01WjDpbb7C5bF2zUAbY1c8z9", "sevt_01NLZCBs56HZdqpLhdKsVrV1", "sevt_01KVBeY3CPbr7DRAUss8YckQ",
    "sevt_01DTqEdV4S8RZ6TDJrByB71T", "sevt_01BPEnbMtyPDAsk8kXLYx6xn", "sevt_01Ad1SGg94eDY6LTAoz8QWF2",
    "sevt_01DQVqQHrXuTkY8tZSyza6p5", "sevt_01GvEzKqdsU3zLSQfJDW99Sm", "sevt_015jV3QWbd3KcbFy1xvu8iHE",
    "sevt_01LV5DLMWxPsisgmhnSP9LPS", "sevt_01KMcbCJbMcZ4ebhwKbrkPZQ", "sevt_01TFEoFuLaS5xBpPQ8pFRw2S",
    "sevt_01PFqNbKFVeQj2QVxKtcwmvr", "sevt_01QMdBMMJWjhz1NKgJo2cwkb", "sevt_01SM3BHGKZMiimjrJuXQSu2n",
]
# Run 1 of this read-back (job 107433353640) established from the live
# error bodies that the server's valid query parameters for this endpoint
# are exactly: created_at[gt], created_at[gte], created_at[lt],
# created_at[lte], limit, order, page, types[]. "page" is tried first
# because it is the only candidate that is actually a valid parameter name
# per that error message; the others are kept only to record their
# rejection again for completeness. Continuation calls now use limit=1000
# (the server's documented max), not the previous run's hardcoded 5000,
# which masked whether "page" would have worked by failing the limit
# check before the parameter name was ever evaluated.
CURSOR_PARAM_CANDIDATES = ("page",) + tuple(
    n for n in PP.CURSOR_PARAM_CANDIDATES if n != "page")
CONTINUATION_LIMIT = 1000


def ground_truth_events_v2(sid: str) -> dict:
    """Like pagination_probe.ground_truth_events, but retries a limit ladder
    on the first call instead of giving up after one failed attempt."""
    pages: list = []
    by_id: dict = {}

    def record(attempt, status, rid, body):
        keys = sorted(body) if isinstance(body, dict) else None
        data = body.get("data") if isinstance(body, dict) else None
        pages.append({
            "attempt": attempt, "status": status, "request_id": rid, "response_keys": keys,
            "data_count": len(data) if isinstance(data, list) else None,
            "response_body_if_not_ok": None if campaign.ok(status) else campaign.trim(body, 800),
            "has_more_field": body.get("has_more") if isinstance(body, dict) else None,
            "next_page_field": body.get("next_page") if isinstance(body, dict) else None,
        })

    first_ok = False
    next_page = None
    for lim in LIMIT_LADDER:
        path = f"/sessions/{sid}/events" + (f"?limit={lim}" if lim else "")
        st, d, rid = campaign.http("GET", path)
        record(f"first page, limit={lim}", st, rid, d)
        if campaign.ok(st) and isinstance(d, dict):
            for e in d.get("data", []):
                by_id[e.get("id")] = e
            next_page = d.get("next_page")
            first_ok = True
            break
    if not first_ok:
        return {"method": "FAILED: every limit in the ladder failed", "pages": pages, "events": []}

    if not next_page:
        method = "single page (next_page falsy)"
    else:
        method = None
        remaining = next_page
        hops = 0
        while remaining and hops < 40:
            hops += 1
            found_this_hop = False
            for name in CURSOR_PARAM_CANDIDATES:
                val = remaining if isinstance(remaining, str) else json.dumps(remaining)
                path = f"/sessions/{sid}/events?limit={CONTINUATION_LIMIT}&{name}={urllib.parse.quote(val)}"
                st, d, rid = campaign.http("GET", path)
                record(f"hop{hops} candidate={name}", st, rid, d)
                if campaign.ok(st) and isinstance(d, dict):
                    new_ids = [e.get("id") for e in d.get("data", []) if e.get("id") not in by_id]
                    if new_ids:
                        for e in d.get("data", []):
                            by_id[e.get("id")] = e
                        remaining = d.get("next_page")
                        method = method or name
                        found_this_hop = True
                        break
            if not found_this_hop:
                method = method or "INCOMPLETE: no candidate continuation param advanced past next_page"
                remaining = None
        if remaining:
            method = (method or "") + " (stopped: hop cap reached, next_page still truthy)"

    ordered = sorted(by_id.values(), key=lambda e: (e.get("created_at") or "", str(e.get("id") or "")))
    return {"method": method or "single page, no continuation needed", "pages": pages, "events": ordered}


def main() -> None:
    problems = PP.verify_frozen()
    print("frozen check:", "OK" if not problems else problems)

    driver.load_env(os.path.join(ROOT, ".env"))
    driver.load_env(os.path.join(ROOT, "IDS.env"))
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY missing")

    print(f"\n=== read-back for session {SESSION_ID} (no new proposals submitted) ===\n")

    prototype = PP.safe_prototype_read(SESSION_ID)
    print("--- prototype reader: driver.list_events(sid), unmodified ---")
    print(json.dumps({"count": prototype["count"], "error": prototype["error"]}, indent=2))

    ground_truth = ground_truth_events_v2(SESSION_ID)
    print("\n--- ground truth reader v2 (fixed: limit ladder) ---")
    print("method:", ground_truth["method"])
    print("event count:", len(ground_truth["events"]))
    print("\nfull page log (every HTTP call this reader made):")
    print(json.dumps(ground_truth["pages"], indent=2, default=str))

    comparison = PP.compare(ground_truth["events"], prototype["ids"])
    print("\n--- comparison ---")
    print(json.dumps(comparison, indent=2, default=str))

    proto_ids = set(prototype["ids"] or [])
    gt_ids = {e.get("id") for e in ground_truth["events"]}
    known = set(KNOWN_ANSWERED_FROM_ORIGINAL_LOG_TAIL)
    print("\n--- cross-check against the 111 proposal ids answered live (from the original job log) ---")
    print(json.dumps({
        "known_answered_count": len(known),
        "known_answered_in_prototype_reader": len(known & proto_ids),
        "known_answered_missing_from_prototype_reader": sorted(known - proto_ids),
        "known_answered_in_ground_truth": len(known & gt_ids),
        "known_answered_missing_from_ground_truth": sorted(known - gt_ids),
    }, indent=2))

    # every event type present in ground truth, with counts, plus the type
    # distribution restricted to what the prototype reader actually returned
    from collections import Counter
    gt_types = Counter(e.get("type") for e in ground_truth["events"])
    proto_type_events = [e for e in ground_truth["events"] if e.get("id") in proto_ids]
    proto_types = Counter(e.get("type") for e in proto_type_events)
    print("\n--- event type distribution ---")
    print("ground_truth:", dict(gt_types))
    print("prototype (restricted to ids it returned, types taken from ground truth):", dict(proto_types))

    print("\n--- classification ---")
    print(json.dumps({
        "A_prototype_misses_events": comparison["A_prototype_misses_events"],
        "B_which_events_summary": f"{comparison['missing_count']} missing of {comparison['ground_truth_count']} ground truth",
        "first_missing_event": comparison["first_missing_event"],
        "C_execution_relevant_missing_count": len(comparison["execution_relevant_missing"]),
        "note": "this is a read-back of the ALREADY-COMPLETED live session from run 35932071669; "
                "no new propose_action calls were made in this process.",
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
