#!/usr/bin/env python3
"""ONE RUN'S VERDICT FOR THE BATCH, as an exit code the shell reads BARE.

  0  A green: no terminal that is a cache fault, and call 1 read the ping's entry
  1  A red:   CACHE MISS within the run, or a cold write at call 1 (cross-run)
  2  STOP:    the API refused (API ERROR), or the preflight refused
The line printed names the fields the code reasons about. Never read this
through a pipe (`| tee`): the pipe's status is tee's, not this one's.
"""
import json
import sys


def verdict(rec):
    tm = rec.get("three_turns") or {}
    rl = rec.get("run_line") or {}
    t = (tm.get("terminal") or {}).get("kind")
    cw = tm.get("cold_write") or {}
    line = "terminal=%s verdict=%s api_calls=%s usd_cli=%s request_mb=%s cold_write=%s" % (
        t, tm.get("verdict"), rl.get("api_calls"), rl.get("usd_cli"), rl.get("request_mb"), cw)
    if t in ("API ERROR", "PREFLIGHT REFUSED"):
        return 2, line
    if t == "CACHE MISS" or cw.get("cold"):
        return 1, line
    return 0, line


def main():
    rc, line = verdict(json.load(open(sys.argv[1], encoding="utf-8")))
    print(line)
    sys.exit(rc)


if __name__ == "__main__":
    main()
