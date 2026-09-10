#!/usr/bin/env python3
"""ONE REPORT from every per-video analysis.

  python3 run_craft_synthesis.py                the standard (Zac's ten)
  python3 run_craft_synthesis.py --field        the wider field, SEPARATELY
  python3 run_craft_synthesis.py --both         both, as two documents

TWO DOCUMENTS, NEVER ONE. The standard and the field are synthesised in
separate calls and land in the prefix as separate, labelled reports, because
the agent has to be able to tell which one a line came from — and because a
contradiction is resolved by the standard winning, which is impossible to do
to half of a merged document.

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


def run(fn, items, mode, tag, want_fp):
    words = sum(len(a["prose"].split()) for a in items)
    print(f"  PRICE: {len(items)} analyses, {words:,} words in, one call "
          f"=> ~${words * 1.4 / 1e6 * 1.25 + 0.03:.2f}")
    r = fn.remote(items, mode=mode)
    # THE RESULT MUST COME FROM THE CODE THAT IS ON THIS DISK. A deploy
    # followed straight by a call once ran the PREVIOUS version and refused a
    # report using a rule that had already been narrowed — a real-looking
    # refusal the shipped code would not have made.
    got = r.get("guard_fp")
    if got != want_fp:
        print(f"  *** STALE IMAGE: the container's rate guard is {got}, this "
              f"worktree's is {want_fp}. The result is NOT about the code you "
              f"have. Redeploy and re-run; nothing written.")
        return False
    print(f"  state={r['state']}  {r['detail']}  wall={r['wall_s']}s  "
          f"guard={got}")
    if r.get("preamble_stripped"):
        print(f"  (preamble removed: {r['preamble_stripped'][:70]!r})")
    for h in (r.get("rate_hits") or []):
        print(f"  *** RATE: {h}")
    if r.get("prose"):
        open(f"/tmp/craft_report_{tag}.md", "w").write(r["prose"])
        print(f"  written: /tmp/craft_report_{tag}.md")
    json.dump(r, open(f"/tmp/craft_report_{tag}.json", "w"))
    return r["state"] == "MEASURED"


def main():
    want_field = "--field" in sys.argv or "--both" in sys.argv
    want_std = "--field" not in sys.argv or "--both" in sys.argv
    ref, ref_bad = load(REF, "zac_reference")
    field, field_bad = load(FIELD, "apify_field")
    print(f"  references: {len(ref)} MEASURED"
          + (f", {len(ref_bad)} NOT: {ref_bad}" if ref_bad else ""))
    print(f"  field:      {len(field)} MEASURED"
          + (f", {len(field_bad)} NOT" if field_bad else ""))

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import craft_pass_app                                         # noqa: E402
    want_fp = craft_pass_app.guard_fp()
    print(f"  this worktree's rate guard: {want_fp}")

    fn = modal.Function.from_name("promptly-craft-pass", "synthesise")
    ok = True
    if want_std:
        if not ref:
            print("  *** no reference analyses — refusing to synthesise a "
                  "taste he did not choose")
            return 1
        print("\nTHE STANDARD — Zac's ten")
        ok &= run(fn, ref, "standard", "standard", want_fp)
    if want_field:
        if not field:
            print("  *** no field analyses")
            return 1
        print("\nTHE WIDER FIELD — other people's work, a SEPARATE document")
        ok &= run(fn, field, "field", "field", want_fp)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
