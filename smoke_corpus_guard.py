#!/usr/bin/env python3
"""RED-prove every leg of corpus_guard, then prove the real v3 plan passes.

A check that has never failed is not yet a check. Each leg below is driven by a
plan that SHOULD be refused, and the smoke fails if the guard accepts it.

Leg 3 is not synthetic. ab-sources/reliability-fixtures-v3/music-fb4aa93b.mp4 is
a real object, byte-identical to car_short-fb4aa93b.mp4 and absent from the v3
manifest. It is exactly what a person would produce by wiring v3 to v1's five
fixture names, and it is the case the filename cannot catch.

  python3 smoke_corpus_guard.py     exit 0 = all legs behaved
"""
import os
import sys
import tempfile

import corpus_guard as cg

V3 = "ab-sources/reliability-fixtures-v3"
V1 = "ab-sources/reliability-fixtures-v1"

TH = f"{V3}/talking_head-f4195ca9.mp4"
MO = f"{V3}/motion-31fa2646.mp4"
CAR = f"{V3}/car_short-fb4aa93b.mp4"
STRAY = f"{V3}/music-fb4aa93b.mp4"          # real, unmanifested, dup of CAR


def _plan(rows):
    fd, p = tempfile.mkstemp(suffix=".tsv")
    with os.fdopen(fd, "w") as fh:
        for name, key in rows:
            fh.write(f"{name}\t{key}\tbrief\tclaude-haiku-4-5\n")
    return p


def main():
    fails = []

    def leg(label, rows, declared, want_ok):
        p = _plan(rows)
        try:
            ok, lines = cg.check(p, declared)
        finally:
            os.unlink(p)
        state = "ACCEPTED" if ok else "REFUSED"
        if ok != want_ok:
            fails.append(f"{label}: guard {state}, expected "
                         f"{'ACCEPT' if want_ok else 'REFUSE'}")
            print(f"  [FAIL] {label:34} {state}")
        else:
            why = "" if ok else f" — {lines[0][:66]}"
            print(f"  [ ok ] {label:34} {state}{why}")
        return ok

    print("RED legs — each of these MUST be refused:")
    leg("spans two corpora",
        [("talking_head", TH), ("music", f"{V1}/music-a4543f09.mp4")], V3, False)
    leg("wrong corpus (rounds 35-41)",
        [("talking_head", f"{V1}/talking_head-eeb40bc7.mp4")], V3, False)
    leg("REAL stray key, not in manifest",
        [("talking_head", TH), ("music", STRAY)], V3, False)
    leg("two fixtures, one video",
        [("car_short", CAR), ("also_car", CAR)], V3, False)
    leg("corpus with no manifest",
        [("x", "ab-sources/no-such-corpus-xyz/x.mp4")],
        "ab-sources/no-such-corpus-xyz", False)
    leg("empty plan", [], V3, False)

    print("\nGREEN leg — the real v3 plan MUST be accepted:")
    leg("v3, three manifested fixtures",
        [("talking_head", TH), ("motion", MO), ("car_short", CAR)], V3, True)

    # The stray and the manifested car clip must really be the same bytes, or
    # leg 3 is testing something other than what it claims.
    import boto3
    s3 = boto3.client("s3")
    et = {}
    for k in (CAR, STRAY):
        try:
            et[k] = s3.head_object(Bucket=os.environ.get("S3_BUCKET_NAME")
                                   or "promptly-video-storage", Key=k)["ETag"]
        except Exception as exc:
            et[k] = f"MISSING ({exc.__class__.__name__})"
    print(f"\n  premise: car_short ETag {et[CAR]}")
    print(f"           stray     ETag {et[STRAY]}")
    if et[CAR] != et[STRAY]:
        fails.append("leg 3's premise is gone: the stray is no longer a "
                     "byte-identical duplicate (or was deleted). Re-point the leg.")
        print("  [FAIL] premise")
    else:
        print("  [ ok ] premise — the stray is a real byte-identical duplicate")

    print()
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return 1
    print("all legs behaved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
