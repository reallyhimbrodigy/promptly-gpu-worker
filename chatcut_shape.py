"""Print the SHAPE of a finished run: where the turns actually went.

Aggregates only. The full call list is large and the first reader truncated it
mid-string at 12000 chars, which then failed to parse — a reader that mangles
its own output is the same class as the run it is measuring.
"""
import collections
import json

import modal

app = modal.App("chatcut-shape")
RESULTS = modal.Dict.from_name("chatcut-results", create_if_missing=True)


@app.local_entrypoint()
def main(run_id: str = ""):
    d = RESULTS.get(run_id)
    if d is None:
        print(f"{run_id}: ABSENT"); return
    s = d["shape"]
    print("WALL %.1fs   agent %.1fs   rc=%s" % (d["wall_s"], d["marks"]["agent"], d["rc"]))
    print("assistant turns    %d" % s["assistant_turns"])
    print("tool calls         %d" % s["tool_calls"])
    print("turns with NO tool %d" % s["turns_with_no_tool"])
    print("tool errors        %d" % s["tool_errors"])
    print("identical repeats  %d" % s["identical_repeats"])
    tot = sum(s["buckets"].values()) or 1
    print("\nBUCKETS:")
    for k, v in sorted(s["buckets"].items(), key=lambda x: -x[1]):
        print("  %-8s %4d  %5.1f%%" % (k, v, 100 * v / tot))
    loc = collections.Counter(c["tool"] for c in s["calls"]
                              if not c["tool"].startswith("mcp__"))
    mcp = collections.Counter(c["tool"].split("__")[-1] for c in s["calls"]
                              if c["tool"].startswith("mcp__"))
    print("\nLOCAL tools (%d):" % sum(loc.values()))
    for n, c in loc.most_common():
        print("  %4d  %s" % (c, n))
    print("\nCHATCUT tools (%d):" % sum(mcp.values()))
    for n, c in mcp.most_common():
        print("  %4d  %s" % (c, n))
    errs = [c for c in s["calls"] if c["err"]]
    if errs:
        print("\nERRORED CALLS:")
        for c in errs:
            print("  turn %-4d %-28s %s" % (c["turn"], c["tool"].split("__")[-1],
                                            c["in"][:70]))
