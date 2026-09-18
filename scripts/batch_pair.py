#!/usr/bin/env python3
"""The with-watch and no-watch outputs: proven to differ (Rule 3) before anyone watches them."""
import hashlib, json, os
a, b = "/tmp/batch/th0.mp4", "/tmp/batch/nowatch.mp4"
if os.path.exists(a) and os.path.exists(b):
    ha, hb = (hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (a, b))
    print("PAIR DIFFERS: %s (sha %s vs %s; %d / %d bytes) — with-watch %s, no-watch %s" % ("YES" if ha != hb else "NO — IDENTICAL BYTES", ha[:12], hb[:12], os.path.getsize(a), os.path.getsize(b), a, b))
else:
    print("PAIR: one or both outputs ABSENT (with-watch %s, no-watch %s)" % (os.path.exists(a), os.path.exists(b)))
