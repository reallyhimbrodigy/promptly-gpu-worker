#!/usr/bin/env python3
"""ONE REPORT from every per-video analysis.

  python3 run_craft_synthesis.py                references only
  python3 run_craft_synthesis.py --with-field   references + the wider field

WHAT IT REFUSES. The report is bound for the cached prefix — written once,
read on every render, forever. So the pass FAILS rather than returns if the
report instructs with a RATE ("~7.5 per 25s" is the one that survived a
careful removal last time by wearing prose), or if a field corpus was read and
never named as distinct from the standard.
"""
import glob
import json
import os
import sys

import modal

REF = "/tmp/craft_out"
FIELD = "/tmp/craft_out_field"


def load(d, want_weight):
    got, bad = [], []
    for f in sorted(glob.glob(f"{d}/*.json")):
        try:
            r = json.load(open(f))
        except Exception as e:                                    # noqa: BLE001
            bad.append((os.path.basename(f), f"unreadable: {e}"))
            continue
        if r.get("state") != "MEASURED" or not r.get("prose"):
            bad.append((os.path.basename(f), r.get("state")))
            continue
        got.append({"label": r.get("label") or os.path.basename(f),
                    "weight": want_weight, "prose": r["prose"]})
    return got, bad


def main():
    ref, ref_bad = load(REF, "zac_reference")
    field, field_bad = load(FIELD, "apify_field") if "--with-field" in sys.argv \
        else ([], [])
    print(f"  references: {len(ref)} MEASURED"
          + (f", {len(ref_bad)} NOT: {ref_bad}" if ref_bad else ""))
    print(f"  field:      {len(field)} MEASURED"
          + (f", {len(field_bad)} NOT" if field_bad else ""))
    if not ref:
        print("  *** no reference analyses — refusing to synthesise a taste "
              "he did not choose")
        return 1
    words = sum(len(a["prose"].split()) for a in ref + field)
    print(f"PRICE STATED: {words:,} words in, one Gemini 2.5 Pro call. "
          f"~${words * 1.4 / 1e6 * 1.25 + 0.03:.2f}.")

    fn = modal.Function.from_name("promptly-craft-pass", "synthesise")
    r = fn.remote(ref + field)
    print(f"\n  state={r['state']}  {r['detail']}  wall={r['wall_s']}s")
    for h in (r.get("rate_hits") or []):
        print(f"  *** RATE: {h}")
    tag = "ref_field" if field else "ref"
    p = f"/tmp/craft_report_{tag}.md"
    if r.get("prose"):
        open(p, "w").write(r["prose"])
        print(f"  written: {p}")
    json.dump(r, open(f"/tmp/craft_report_{tag}.json", "w"))
    return 0 if r["state"] == "MEASURED" else 1


if __name__ == "__main__":
    sys.exit(main())
