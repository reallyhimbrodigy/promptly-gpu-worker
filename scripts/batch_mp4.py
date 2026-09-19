#!/usr/bin/env python3
"""Write a run's exported mp4 from RESULTS[run_id-mp4] (fetched to <out>.json) to <out>.

  batch_mp4.py <out.mp4> [record.json]

REFUSES RATHER THAN HANDS OVER A STALE FILE (2026-09-18). The low arm's fetch for a run id
with no entry left the PREVIOUS batch's fetched json sitting at the path, and this decoded it:
28,366,484 bytes, sha 785a2cd1b15a, written 23:58 and byte-identical to a file from 14:09 —
while that run's own export state was WITHHELD after a RUN TIMEOUT. A missing entry and a real
export were indistinguishable because nothing checked WHOSE bytes these were.

Two checks, each naming what it read:
  1. the record's export state must be MEASURED — a WITHHELD or REFUSED export has no mp4, and
     any file at the path is somebody else's;
  2. the decoded bytes must hash to the record's own export.sha256.
The record is found by convention when it is not passed (<out>.mp4 -> <out>.json), so a caller
that predates this argument is still checked; only a missing record leaves provenance unchecked,
and the line says so. On any refusal the stale file at <out> is REMOVED, so a later reader cannot
find it either.
"""
import base64
import hashlib
import json
import os
import sys

out = sys.argv[1]
# BY CONVENTION WHEN NOT PASSED: this batch writes the record beside the mp4 (/tmp/batch/motion.mp4
# <- motion.json), so the callers written before this argument existed are checked too.
_conv = (out[:-4] if out.endswith(".mp4") else out) + ".json"
rec_path = sys.argv[2] if len(sys.argv) > 2 else (_conv if os.path.exists(_conv) and _conv != out + ".json" else "")


def refuse(why):
    for p in (out,):
        if os.path.exists(p):
            os.remove(p)
            why += " (removed the stale file at %s)" % p
    print("MP4 %s ABSENT — %s" % (out, why))
    sys.exit(0)


rec = {}
if rec_path:
    try:
        rec = json.load(open(rec_path, encoding="utf-8"))
    except Exception as e:                                        # noqa: BLE001
        refuse("the record %s could not be read (%s)" % (rec_path, str(e)[:60]))
    ex = rec.get("export") or {}
    if ex.get("state") != "MEASURED":
        refuse("the record says export %s: %s" % (ex.get("state"), str(ex.get("why"))[:90]))
try:
    d = json.load(open(out + ".json", encoding="utf-8"))
    data = base64.b64decode(d["b64"])
except Exception as e:                                            # noqa: BLE001
    refuse("no fetched bytes at %s.json (%s)" % (out, str(e)[:60]))
sha = hashlib.sha256(data).hexdigest()
want = ((rec.get("export") or {}).get("sha256") or "")
if want and sha != want:
    refuse("the fetched bytes hash %s and this run exported %s — these are not this run's bytes" % (sha[:12], want[:12]))
open(out, "wb").write(data)
print("MP4 %s %d bytes sha %s%s" % (out, len(data), sha[:12], "  (matches the record's export)" if want else "  (NO RECORD GIVEN: provenance unchecked)"))
