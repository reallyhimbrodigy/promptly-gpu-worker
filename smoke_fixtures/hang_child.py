#!/usr/bin/env python3
"""Three child shapes the harness must survive. argv[1] picks one.

IN THE TREE, NOT IN /tmp. A fixture a proof depends on lives next to the proof:
a /tmp fixture clears on reboot and the proof then reports `anchor 0x` forever
while every other leg reads green.
"""
import json
import sys
import time

mode = sys.argv[1]
if mode == "silent":
    # reads, prints once, then goes quiet forever. The deadline must fire with
    # no further output to trigger it.
    sys.stdin.readline()
    sys.stdout.write(json.dumps({"type": "x"}) + "\n")
    sys.stdout.flush()
    time.sleep(600)
elif mode == "writes_first":
    # writes past the 64K pipe buffer BEFORE reading stdin. A parent doing a
    # synchronous multi-megabyte stdin write deadlocks against this, with
    # neither drain nor watchdog started.
    for i in range(300):
        sys.stdout.write(json.dumps({"type": "x", "n": i, "pad": "z" * 650})
                         + "\n")
    sys.stdout.flush()
    sys.stdin.read()
elif mode == "normal":
    # what the real stream-json CLI does: read ONE line, then work.
    line = sys.stdin.readline()
    sys.stdout.write(json.dumps({"type": "result", "got": len(line)}) + "\n")
    sys.stdout.flush()
