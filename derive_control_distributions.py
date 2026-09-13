#!/usr/bin/env python3
"""The reference distribution for every CONTROL the components expose.

WHY THIS IS A FILE AND NOT A RULE. Zac's standing instruction: when the output
is wrong in a way the references are right about, the first question is what the
annotator was never asked — not what rule to add. The annotator now reports
`where`, `size`, `case`, `hold_s`, `colour` and `over_subject` on every
placement, so the answer to "how big, what case, where" is a MEASUREMENT with a
denominator, not a preference.

WHAT IT IS FOR. Round 70 placed, across five fixtures: one distinct component,
ZERO expressible positions (18 of 20 placements carry no position field at all),
and 18 of 20 in ALL CAPS. The corpus says case is lower 31% / upper 30% /
mixed 30% / title 9%. The repetition is not taste — there was no field.

EVERY NUMBER CARRIES ITS DENOMINATOR AND ITS VIDEO COUNT, because a share over
an unstated base is the thing this repo keeps being burned by. `answered` is how
many placements answered that field at all; a field answered by 40% of
placements is reported as such rather than silently normalised.

CUT BY FAMILY, because "text" and "card" and "cutaway" are different questions
and a blended distribution over all three is not a product number.
"""
import collections
import json
import os
import sys

ARMS = ("/tmp/refcorpus_pf", "/tmp/refcorpus_pf_listen")
FIELDS = ("where", "size", "case", "colour", "over_subject", "hold_s")

# FAMILY MEMBERSHIP BY WHAT THE ANNOTATOR CALLED IT, not by our family names.
# The corpus vocabulary is OPEN — that was the whole point of the re-read — so
# the join is on substrings of the annotator's own words.
FAMILIES = {
    "text": ("text", "caption", "typography", "title", "headline", "word",
             "subtitle", "label", "lower third", "kinetic"),
    "card": ("counter", "stat", "number", "card", "figure", "tally", "metric",
             "count-up", "count up", "price", "$"),
    "cutaway": ("cutaway", "cut-away", "cut away", "b-roll", "broll", "insert"),
}


def rows(dirs=ARMS):
    """Every annotated placement, flattened, with its video. State, not guess."""
    out, missing = [], []
    for d in dirs:
        if not os.path.isdir(d):
            missing.append(d)
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json") or fn.startswith(
                    ("manifest", "clusters", "vocabulary", "rates")):
                continue
            try:
                r = json.load(open(os.path.join(d, fn), encoding="utf-8"))
            except Exception:                                     # noqa: BLE001
                continue
            if r.get("state") != "MEASURED":
                continue
            vid = (r.get("video") or r.get("label") or fn).replace(".mp4.json", "")
            for b in (r.get("record") or {}).get("beats") or []:
                for t in (b.get("treatment") or []):
                    if isinstance(t, dict) and t.get("name"):
                        out.append({"video": vid, **t})
    return out, missing


def family_of(r):
    _s = (str(r.get("name") or "") + " " + str(r.get("what_it_does") or "")).lower()
    return [f for f, keys in FAMILIES.items() if any(k in _s for k in keys)]


def distribution(rs, field):
    """{value: {n, videos, share}} plus the denominator. ANSWERED, not total."""
    c, v = collections.Counter(), collections.defaultdict(set)
    for r in rs:
        k = str(r.get(field) or "").strip().lower()
        if not k:
            continue
        c[k] += 1
        v[k].add(r["video"])
    total = sum(c.values())
    return {
        "answered": total,
        "of_placements": len(rs),
        "videos": len({r["video"] for r in rs}),
        "values": {k: {"n": n, "videos": len(v[k]),
                       "share": round(n / total, 3) if total else None}
                   for k, n in c.most_common()},
    }


def main():
    rs, missing = rows()
    if not rs:
        print("ABSENT: no annotated records under %s — the distributions cannot "
              "be derived, which is not the same as them being empty" % (ARMS,))
        return 2
    out = {"state": "MEASURED", "placements": len(rs),
           "videos": len({r["video"] for r in rs}),
           "arms_missing": missing, "all": {}, "by_family": {}}
    for f in FIELDS:
        out["all"][f] = distribution(rs, f)
    for fam in FAMILIES:
        sub = [r for r in rs if fam in family_of(r)]
        out["by_family"][fam] = {"placements": len(sub),
                                 "videos": len({r["video"] for r in sub})}
        for f in FIELDS:
            out["by_family"][fam][f] = distribution(sub, f)
    json.dump(out, open("control_distributions.json", "w"), indent=1)

    print("CONTROL DISTRIBUTIONS — %d placements, %d videos%s\n"
          % (out["placements"], out["videos"],
             ("   (arms missing: %s)" % missing) if missing else ""))
    for fam in ("text", "card", "cutaway"):
        d = out["by_family"][fam]
        print("  %s — %d placements, %d videos" % (fam.upper(), d["placements"],
                                                   d["videos"]))
        for f in ("case", "size", "where"):
            dd = d[f]
            if not dd["answered"]:
                print("     %-6s ABSENT — no placement answered it" % f)
                continue
            top = list(dd["values"].items())[:4]
            print("     %-6s (%d of %d answered)  " % (f, dd["answered"],
                                                       dd["of_placements"])
                  + "  ".join("%s %d%%" % (k, round(100 * x["share"]))
                              for k, x in top))
        print()
    print("written: control_distributions.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
