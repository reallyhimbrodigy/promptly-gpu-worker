#!/usr/bin/env python3
"""ONE RUN'S VERDICT FOR THE BATCH, as an exit code the shell reads BARE.

  0  A green: no terminal that is a cache fault, and call 1 read the ping's entry
  1  A red:   CACHE MISS within the run, or a cold write at call 1 (cross-run)
  2  STOP:    the API refused (API ERROR), or the preflight refused
Two record shapes: a JOB (three_turns + run_line) and G's PROBE (control + review — its control review is
call 1 after the ping, so a cold write there is the same cross-run fault, seen before H1 spends).
The NO-WATCH arm runs cold BY DESIGN (Zac, 2026-09-18): its cold write is named, not red; a within-run
CACHE MISS on it is still red. The line printed names the fields the code reasons about. Never read
this through a pipe (`| tee`): the pipe's status is tee's, not this one's.
"""
import json
import sys


def verdict_probe(rec):
    c, r = rec.get("control") or {}, rec.get("review") or {}
    line = "probe density=%s control: cold_write=%s api=%s false_positives=%s wall=%s | planted: named=%s api=%s wall=%s | request_mb=%s/%s" % (
        rec.get("density_fps"), c.get("cold_write"), c.get("api_status"), c.get("false_positives"), c.get("wall_s"),
        (r.get("named") or {}), r.get("api_status"), r.get("wall_s"), c.get("request_mb"), r.get("request_mb"))
    for x in (c, r):
        st = x.get("api_status")
        if (isinstance(st, int) and st >= 400) or "preflight_refused" in str(x.get("api_head") or ""):
            return 2, line
    if (c.get("cold_write") or {}).get("cold"):
        return 1, line
    return 0, line


def verdict(rec):
    if "control" in rec and "review" in rec and "three_turns" not in rec:
        return verdict_probe(rec)
    tm = rec.get("three_turns") or {}
    rl = rec.get("run_line") or {}
    t = (tm.get("terminal") or {}).get("kind")
    cw = tm.get("cold_write") or {}
    line = "terminal=%s verdict=%s api_calls=%s usd_cli=%s request_mb=%s cold_write=%s density_fps=%s" % (
        t, tm.get("verdict"), rl.get("api_calls"), rl.get("usd_cli"), rl.get("request_mb"), cw, rl.get("density_fps"))
    if t in ("API ERROR", "PREFLIGHT REFUSED"):
        return 2, line
    if t == "CACHE MISS":
        return 1, line
    if cw.get("cold") and rl.get("no_watch"):
        return 0, line + " | COLD BY DESIGN (no-watch: its own prefix, cross-run N/A)"
    if cw.get("cold"):
        return 1, line
    return 0, line


def main():
    rc, line = verdict(json.load(open(sys.argv[1], encoding="utf-8")))
    print(line)
    sys.exit(rc)


if __name__ == "__main__":
    main()
