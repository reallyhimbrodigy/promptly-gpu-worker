#!/usr/bin/env python3
"""One reference video through the craft pass — the shape check before spending."""
import os, sys, json, modal
EX = os.path.expanduser("~/Desktop/EXAMPLES")
# The SHORTEST reference video: cheapest possible shape check, and 25.45s with
# 5 cuts is still a real edit rather than a fragment.
NAME = "v09044g40000cm9oa7nog65s2crhkf00.mp4"
p = os.path.join(EX, NAME)
b = open(p, "rb").read()
print(f"  {NAME}  {len(b)/1e6:.1f}MB")
fn = modal.Function.from_name("promptly-craft-pass", "analyse")
r = fn.remote(b, NAME, "zac_reference")
print(f"  state={r['state']}  {r['detail']}  wall={r['wall_s']}s\n")
print("=" * 78)
print(r.get("prose") or "(no prose)")
print("=" * 78)
open("/tmp/craft_one.json", "w").write(json.dumps(r))
