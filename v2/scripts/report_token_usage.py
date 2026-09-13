#!/usr/bin/env python3
"""Read-only local task-tree token audit; never export conversation contents.

Only metadata headers are inspected to discover descendants. Full token events
are read only for the explicitly requested root and its descendants. The report
is a recorded-usage snapshot, not a billing estimate or complete ChatGPT history.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
          "output_tokens", "reasoning_output_tokens", "total_tokens")


def counter_sum(rows):
    result = {key:sum(row.get(key,0) for row in rows) for key in FIELDS}
    result["uncached_input_tokens"] = result["input_tokens"]-result["cached_input_tokens"]
    return result


def audit(session_roots, root_id, since=None):
    metadata = {}
    for folder in session_roots:
        for path in folder.rglob("rollout-*.jsonl"):
            try:
                with path.open() as handle:
                    event = json.loads(handle.readline())
                if event.get("type") != "session_meta":
                    continue
                meta = event["payload"]
                source = meta.get("source")
                agent = source.get("subagent",{}) if isinstance(source,dict) else {}
                spawn = agent.get("thread_spawn",{})
                metadata.setdefault(meta["id"], []).append({"path":path,"parent":meta.get("parent_thread_id") or spawn.get("parent_thread_id"),
                    "agent_path":spawn.get("agent_path"),"kind":agent.get("other") or ("agent" if spawn else "primary")})
            except (OSError,ValueError,KeyError):
                continue
    selected = {root_id}
    while True:
        more = {key for key, records in metadata.items() if any(row["parent"] in selected for row in records)}
        if more <= selected:
            break
        selected |= more
    rows = []
    for task_id in sorted(selected):
        records = metadata.get(task_id,[])
        events = {}
        for record in records:
            with record["path"].open() as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except ValueError:  # A concurrent writer may not have completed the last line.
                        continue
                    payload = event.get("payload",{})
                    if event.get("type") != "event_msg" or payload.get("type") != "token_count":
                        continue
                    info = payload.get("info") or {}
                    total = info.get("total_token_usage")
                    if total:
                        events[event["timestamp"]] = {"total":{key:int(total.get(key,0)) for key in FIELDS},
                            "last":info.get("last_token_usage") or {}}
        ordered = sorted(events.items())
        row = {"thread_id":task_id,"agent_path":records[0]["agent_path"] if records else None,
               "kind":records[0]["kind"] if records else "unknown", "usage_available":bool(ordered)}
        if ordered:
            # A resumed app session can restart its cumulative counter. Add
            # each monotone segment once; repeated notifications add zero.
            row["as_of_utc"] = ordered[-1][0]
            row["usage"] = {key:0 for key in FIELDS}
            row["usage_since"] = {key:0 for key in FIELDS}
            row["counter_resets"] = []
            previous = {key:0 for key in FIELDS}
            for stamp,event in ordered:
                total = event["total"]
                if total["total_tokens"] < previous["total_tokens"]:
                    row["counter_resets"].append({"timestamp":stamp,
                        "new_total_equals_last_request":total["total_tokens"]==event["last"].get("total_tokens")})
                    previous = {key:0 for key in FIELDS}
                increment = {key:total[key]-previous[key] for key in FIELDS}
                for key,value in increment.items():
                    row["usage"][key] += value
                    if since and stamp >= since:
                        row["usage_since"][key] += value
                previous = total
        rows.append(row)
    available = [row for row in rows if row["usage_available"]]
    total = counter_sum([row["usage"] for row in available])
    result = {"generated_at_utc":datetime.now(timezone.utc).isoformat(),"root_thread_id":root_id,
              "scope":"Explicit local Codex task and discovered descendants; not all historical ChatGPT conversations or account usage.",
              "counting":"Each thread's cumulative-counter segments, once, accounting for observed session resets. Cached input is a subset of input; reasoning output is a subset of output.",
              "billing_cost_computed":False,"complete_project_lifetime_usage_known":False,
              "all_discovered_threads_have_usage":len(available)==len(rows),
              "recorded_usage_total":total,"threads":rows,
              "limitations":["Snapshot excludes model work after the recorded event, including this response's completion.",
                 "No token event means unavailable, not zero. Guardian/system-task usage is included only if locally reported.",
                 "Original linked ChatGPT conversation usage is not exposed by these local task counters.",
                 "Cached context is repeatedly processed input, not newly authored content. This is not a price or account-limit conversion."]}
    result["recorded_usage_by_kind"] = {kind:counter_sum([row["usage"] for row in available if row["kind"]==kind])
        for kind in sorted({row["kind"] for row in available})}
    if since:
        result["since_utc"] = since
        result["recorded_usage_since"] = counter_sum([row["usage_since"] for row in available])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions",type=Path,action="append",required=True)
    parser.add_argument("--root-thread",required=True)
    parser.add_argument("--since",help="UTC ISO timestamp; subtract the last cumulative counter before this boundary")
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists: choose a new snapshot name")
    report = audit(args.sessions,args.root_thread,args.since)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({key:report[key] for key in ("generated_at_utc","recorded_usage_total","all_discovered_threads_have_usage")},indent=2))
    if args.since:
        print(json.dumps({"recorded_usage_since":report["recorded_usage_since"]},indent=2))


if __name__ == "__main__":
    main()
