#!/usr/bin/env python3
"""Write a run's exported mp4 from RESULTS[run_id-mp4] (fetched to <out>.json) to <out>.

  batch_mp4.py <out.mp4> [record.json]

DELIVERY (Zac, 2026-09-19): a verified export is COPIED to the Promptly Reports folder, named by run,
and the report gives that path — never a /tmp path. Set DELIVER_DIR (the window and batch scripts set it
to a dated subfolder). The copy happens ONLY after the two checks below pass, and the delivered file is
re-hashed after writing, so a truncated or half-written copy is caught rather than handed over.

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

DELIVER_DIR = os.environ.get("DELIVER_DIR", "")


def copy_is_sound(dst, sha):
    """-> True when the file written at `dst` hashes to `sha`. PURE, and a FUNCTION so a check can DRIVE
    it: inline, the comparison could only be grepped, and a grep reads the same under `if False:` — the
    mutation that disabled it passed for exactly that reason (2026-09-19)."""
    try:
        return hashlib.sha256(open(dst, "rb").read()).hexdigest() == sha
    except Exception:                                             # noqa: BLE001
        return False


def refuse(out, why):
    """Remove whatever sits at the target — in the work dir AND in the delivery folder — and say why.
    A refusal that leaves the old file behind is how a stale export reaches a report."""
    for p in (out, os.path.join(DELIVER_DIR, os.path.basename(out)) if DELIVER_DIR else out):
        if os.path.exists(p):
            os.remove(p)
            why += " (removed the stale file at %s)" % p
    print("MP4 %s ABSENT — %s" % (out, why))
    sys.exit(0)


def main():
    out = sys.argv[1]
    # BY CONVENTION WHEN NOT PASSED: this batch writes the record beside the mp4 (/tmp/batch/motion.mp4
    # <- motion.json), so the callers written before this argument existed are checked too.
    _conv = (out[:-4] if out.endswith(".mp4") else out) + ".json"
    rec_path = sys.argv[2] if len(sys.argv) > 2 else (_conv if os.path.exists(_conv) and _conv != out + ".json" else "")
    rec = {}
    if rec_path:
        try:
            rec = json.load(open(rec_path, encoding="utf-8"))
        except Exception as e:                                    # noqa: BLE001
            refuse(out, "the record %s could not be read (%s)" % (rec_path, str(e)[:60]))
        ex = rec.get("export") or {}
        if ex.get("state") != "MEASURED":
            refuse(out, "the record says export %s: %s" % (ex.get("state"), str(ex.get("why"))[:90]))
    try:
        d = json.load(open(out + ".json", encoding="utf-8"))
        data = base64.b64decode(d["b64"])
    except Exception as e:                                        # noqa: BLE001
        refuse(out, "no fetched bytes at %s.json (%s)" % (out, str(e)[:60]))
    sha = hashlib.sha256(data).hexdigest()
    want = ((rec.get("export") or {}).get("sha256") or "")
    if want and sha != want:
        refuse(out, "the fetched bytes hash %s and this run exported %s — these are not this run's bytes"
               % (sha[:12], want[:12]))
    open(out, "wb").write(data)
    line = "MP4 %s %d bytes sha %s%s" % (out, len(data), sha[:12],
                                        "  (matches the record's export)" if want else "  (NO RECORD GIVEN: provenance unchecked)")
    if DELIVER_DIR:
        # NEVER FROM THE TMP FILE: the same verified bytes are written again, then read back and re-hashed.
        try:
            os.makedirs(DELIVER_DIR, exist_ok=True)
            dst = os.path.join(DELIVER_DIR, os.path.basename(out))
            with open(dst, "wb") as fh:
                fh.write(data)
            if not copy_is_sound(dst, sha):
                os.remove(dst)
                line += "\n  DELIVERY FAILED: the copy at %s does not hash to %s — removed" % (dst, sha[:12])
            else:
                line += "\n  DELIVERED %s (re-hashed after writing: matches)" % dst
        except Exception as e:                                    # noqa: BLE001
            line += "\n  DELIVERY FAILED: %s" % str(e)[:120]
    print(line)


if __name__ == "__main__":
    main()
