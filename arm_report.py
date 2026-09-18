#!/usr/bin/env python3
"""One arm of the subtraction experiment, read off its record. -> the numbers.

  python3 arm_report.py /tmp/armA.json /tmp/armB.json

Prints, per arm: what stopped it (first batch / ceiling / deadline / ran out),
thinking seconds, output tokens, assistant events to the first batch, cache
read/write, and the dollar figure. States are named — an arm that was stopped
by the ceiling rather than by its first batch is not a measurement of the
question, and the report says so instead of printing a number beside a good
one.
"""
import json
import sys


def arm(path):
    d = json.load(open(path))
    tb = d.get("turn_budget") or {}
    tm = d.get("turn_machine") or {}
    ex = tm.get("experiment") or {}
    gb = tb.get("generating_by_block_s") or {}
    ot = tb.get("output_tokens") or {}
    # THE CLI'S OWN BILL WHEN PRESENT (result event); else the deduped sums.
    _ru = tb.get("result_usage") or {}
    _src = "result event" if _ru else ("deduped sums" if ot.get("api_calls") else "EVENT SUMS (over-counted by block multiplicity)")
    cr = _ru.get("cache_read_input_tokens") if _ru else (ot.get("cache_read_sum") or 0)
    cw = _ru.get("cache_creation_input_tokens") if _ru else (ot.get("cache_write_sum") or 0)
    print("  usage source: %s | api_calls=%s" % (_src, ot.get("api_calls", "ABSENT")))
    for c in (tb.get("usage_by_call") or []):
        print("    call %-2s %-28s read=%-8s write=%-8s out=%s" % (c["n"], ",".join(c["tools"])[:28], c["read"], c["write"], c["out"]))
    out = (tb.get("output_tokens_final") or {}).get("sum") or 0
    stopped_by = (ex.get("stopped") and "first batch"
                  or (tm.get("ceiling") not in (None, "NOT REACHED") and "CEILING")
                  or (tb.get("kill_reason") or ("deadline" if tb.get("killed") else "ran to end")))
    valid = stopped_by == "first batch"
    return {
        "arm": "no-watch" if ex.get("no_watch") else "watch",
        "stopped_by": stopped_by,
        "VALID_MEASUREMENT": valid,
        "thinking_s": round(gb.get("thinking") or 0, 1),
        "generating_s": round((tb.get("buckets_s") or {}).get("GENERATING") or 0, 1),
        "output_tokens": out,
        "assistant_events": tm.get("assistant_events_seen"),
        "batch_events": tm.get("batch_events"),
        "cache_read": cr, "cache_write": cw,
        "anthropic_usd": round((cr * 0.10 * 3 + cw * 2.0 * 3 + out * 15) / 1e6, 3),
        "wall_s": d.get("wall_s"),
        "reasoning": str(d.get("shape", {}).get("reasoning_state"))[:60],
        # THE FIRST RESULT'S OWN VERDICT. An arm stopped on an errored
        # edit_item measured thinking-to-a-refusal, not thinking-to-a-
        # placement; the two are reported as different measurements.
        "first_batch_is_error": ((ex.get("batch_results") or [{}])[0]
                                 .get("is_error") if ex.get("batch_results")
                                 else "NO RESULT"),
        "kill_reason": ex.get("kill_reason") or tb.get("kill_reason"),
        "confounds": len(ex.get("confounds") or []),
    }


if __name__ == "__main__":
    rows = [arm(p) for p in sys.argv[1:]]
    keys = ["arm", "stopped_by", "VALID_MEASUREMENT", "thinking_s", "generating_s",
            "output_tokens", "assistant_events", "batch_events", "cache_read",
            "cache_write", "anthropic_usd", "wall_s", "first_batch_is_error",
            "kill_reason", "confounds"]
    for k in keys:
        print("  %-18s " % k + "   ".join("%-22s" % str(r.get(k)) for r in rows))
    if len(rows) == 2 and all(r["VALID_MEASUREMENT"] for r in rows):
        a, b = rows
        print("\n  thinking delta   : %.1fs -> %.1fs  (%.0f%% of the watch arm's)"
              % (a["thinking_s"], b["thinking_s"],
                 100.0 * b["thinking_s"] / max(a["thinking_s"], 0.1)))
    elif len(rows) == 2:
        print("\n  NOT COMPARABLE: an arm was stopped by something other than its "
              "first batch — the number beside it is not the measurement asked for")
