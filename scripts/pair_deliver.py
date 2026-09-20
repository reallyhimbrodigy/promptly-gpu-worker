#!/usr/bin/env python3
"""Pull the zoom pair's record and deliver it — ONLY if the verdict earned it.

WHY DELIVERY IS A SEPARATE, REFUSING STEP. Rule 3 is not "compare, then send"; it
is "send only what has been proven to differ, for the right reason". The run's own
gate already withholds, but the thing that actually reaches Zac's Desktop is this
script, so the refusal lives here too rather than being inherited by assumption.

FIVE VERDICTS, ONE OF WHICH DELIVERS:
  DIFFER      the control is pixel-identical and the span differs -> WRITE
  CONFOUNDED  the control differs; the pair is not evidence       -> REFUSE
  IDENTICAL   the two zooms rendered the same picture             -> REFUSE
  ABSENT      a side produced no frames                           -> REFUSE
  FAILED      a sheet could not be read                           -> REFUSE
"""
import base64
import hashlib
import json
import os
import sys

DELIVER_DIR = "/Users/zaclibman/Desktop/Promptly Reports"


def main():
    import modal
    rec = modal.Dict.from_name("chatcut-results", create_if_missing=True).get("zoom-pair")
    if not rec:
        print("ABSENT: no zoom-pair record — nothing was run, or the run died before writing")
        return 1
    d = rec.get("differ") or {}
    ctrl = d.get("control") or {}
    prof = d.get("profile") or {}
    print("run state   : %s  (%ss wall, project %s)"
          % (rec.get("state"), rec.get("wall_s"), str(rec.get("project"))[:8]))
    print("verdict     : %s" % d.get("state"))
    print("why         : %s" % d.get("why"))
    if ctrl:
        print("control     : %s — %d sheet(s) outside the zoom, %s differing"
              % (ctrl.get("state"), ctrl.get("n") or 0, ctrl.get("differing")))
        print("control prof: %s" % (ctrl.get("profile") or []))
    if prof:
        print("span profile: %s" % (prof.get("profile") or []))
    for arm in ("theirs", "ours"):
        a = (rec.get("arms") or {}).get(arm) or {}
        print("%-12s: %s placed=%s removed=%s frames=%s"
              % (arm, a.get("state"), a.get("placed"), a.get("removed"),
                 (a.get("frames") or {}).get("n")))

    if d.get("state") != "DIFFER":
        print("\nREFUSED: the pair is %s, so nothing is delivered. A pair that is not "
              "evidence costs a round of his time to look at." % d.get("state"))
        return 2

    sb = rec.get("side_by_side") or {}
    if not sb.get("b64"):
        print("\nREFUSED: the verdict is DIFFER but no side-by-side image was composed (%s)"
              % sb.get("why"))
        return 3
    os.makedirs(DELIVER_DIR, exist_ok=True)
    data = base64.b64decode(sb["b64"])
    path = os.path.join(DELIVER_DIR, "zoom_pair_SmoothPush_vs_slow-push.jpg")
    with open(path, "wb") as fh:
        fh.write(data)
    # RE-HASHED AFTER THE WRITE, the same rule as the decoder and the batch: the
    # bytes that landed are what is claimed, not the bytes that were intended.
    on_disk = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if on_disk != hashlib.sha256(data).hexdigest():
        print("\nFAILED: the delivered copy does not hash to the record's bytes")
        return 4
    print("\nDELIVERED   : %s" % path)
    print("bytes/sha256: %d / %s" % (len(data), on_disk[:16]))
    for line in rec.get("labels") or []:
        print("  %s" % line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
