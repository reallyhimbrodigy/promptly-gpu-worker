#!/usr/bin/env python3
"""Write a run's exported mp4 from RESULTS[run_id-mp4] (fetched to <out>.json) to <out>."""
import base64, json, os, sys
out = sys.argv[1]
try:
    d = json.load(open(out + ".json")); open(out, "wb").write(base64.b64decode(d["b64"]))
    print("MP4 %s %d bytes sha %s" % (out, d.get("bytes"), (d.get("sha256") or "")[:12]))
except Exception as e:
    print("MP4 %s ABSENT (%s)" % (out, str(e)[:80]))
