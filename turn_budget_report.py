#!/usr/bin/env python3
"""Print the three-way split of a run's wall, and say what it cannot attribute."""
import json
import sys

MODEL = ("WAITING", "TTFT", "GENERATING", "MODEL_ROUNDTRIP")
TOOL = ("TOOL_LOCAL", "TOOL_MCP")


def main(path):
    d = json.load(open(path, encoding="utf-8"))
    b = d.get("turn_budget") or {}
    if b.get("state") == "FAILED":
        print("TURN BUDGET: FAILED —", b.get("why"))
        return 1
    if not b:
        print("TURN BUDGET: ABSENT — this run predates the clock")
        return 1
    wall = b["wall_s"]
    buckets = b.get("buckets_s") or {}
    model = sum(v for k, v in buckets.items() if k in MODEL)
    tool = sum(v for k, v in buckets.items() if k in TOOL)
    neither = b["neither_s"]
    print("=" * 62)
    print("WHERE %.1f SECONDS GO   [%s]" % (wall, b.get("mode")))
    print("=" * 62)
    # The three Zac asked for, then the parts that make up the first.
    for lab, v in (("MODEL (producing / waiting on tokens)", model),
                   ("TOOL CALLS in flight", tool),
                   ("NEITHER", neither)):
        print("  %-38s %7.1fs  %5.1f%%" % (lab, v, 100.0 * v / wall))
    print("  " + "-" * 58)
    for k in ("WAITING", "TTFT", "GENERATING", "MODEL_ROUNDTRIP",
              "TOOL_LOCAL", "TOOL_MCP"):
        if k in buckets:
            print("      %-34s %7.1fs  %5.1f%%"
                  % (k, buckets[k], 100.0 * buckets[k] / wall))
    print()
    print("  CPU state       : %s" % b.get("cpu_state"))
    print("  CPU mean/p90    : %s / %s cores"
          % (b.get("cpu_mean_cores"), b.get("cpu_p90_cores")))
    print("  quota           : %s  cores=%s   os.cpu_count=%s (HOST, not ours)"
          % (b.get("quota_state"), b.get("quota_cores"), b.get("os_cpu_count")))
    print("  THROTTLED       : %ss  (%s%% of wall)"
          % (b.get("throttled_total_s"), b.get("throttled_share")))
    print("  gaps > 0.5s     : %s" % b.get("gaps_over_0s5"))
    gd = b.get("gap_detail") or []
    if gd:
        print("  the ten longest unattributed gaps (start, end, mean cores, throttled s):")
        for row in sorted(gd, key=lambda r: -(r[1] - r[0]))[:10]:
            print("      %8.2f -> %8.2f  (%5.1fs)  cpu=%s  thr=%s"
                  % (row[0], row[1], row[1] - row[0], row[2],
                     row[3] if len(row) > 3 else "?"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/clocked_full.json"))
