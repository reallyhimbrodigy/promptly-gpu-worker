#!/usr/bin/env python3
"""RED proof for density_histogram: ABSENT is not zero, and zero is not ABSENT.

The whole point of this instrument is the distinction a rate cannot carry on its
own. A family with no placements reads 0.0 ONLY if the timeline was read; a
withheld export has no rate at all. Both look like "nothing happened" in a table
of numbers, and one of them is a measurement that never occurred.
"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import density_histogram as D

fail = 0
def leg(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print("  %s %s  ::  got %r, want %r" % ("ok  " if ok else "FAIL", name, got, want))

tmp = tempfile.mkdtemp(prefix="b2-dens-")
def rec(path, obj):
    p = os.path.join(tmp, path)
    json.dump(obj, open(p, "w"))
    return p

# 1. A WITHHELD EXPORT HAS NO RATE. Not a rate of nothing.
p = rec("withheld.json", {"export": {"state": "WITHHELD", "why": "terminal"}})
leg("a withheld export is ABSENT, never zeros", D.run_rates(p)["state"], "ABSENT")

# 2. AN EXPORTED TIMELINE WITH ITEMS IS MEASURED, and the families map.
p = rec("ok.json", {"export": {"state": "OK"}, "timeline_sample": {"end_s": 50.0, "items": [
    {"itemType": "video"}, {"itemType": "video"},
    {"itemType": "caption"}, {"itemType": "motion-graphic"},
    {"itemType": "audio"}, {"itemType": "effect"}]}})
r = D.run_rates(p)
leg("an exported timeline is MEASURED", r["state"], "MEASURED")
leg("  ...two cuts over 50s is 1.0 per 25s", r["per_25s"]["cut"], 1.0)
leg("  ...and a motion-graphic counts as a card", r["counts"]["card"], 1)

# 3. ZERO IS A MEASUREMENT WHEN THE TIMELINE WAS READ. This is the other half.
p = rec("nozoom.json", {"export": {"state": "OK"}, "timeline_sample": {"end_s": 25.0,
        "items": [{"itemType": "video"}]}})
r = D.run_rates(p)
leg("a family with no items on a READ timeline is 0.0 and MEASURED",
    (r["state"], r["per_25s"]["zoom"]), ("MEASURED", 0.0))

# 4. NO DURATION MEANS NO NORMALISATION. Not a divide, not a zero.
p = rec("nodur.json", {"export": {"state": "OK"}, "timeline_sample": {"items": []}})
leg("a timeline with no duration is ABSENT", D.run_rates(p)["state"], "ABSENT")

# 5. AN UNREADABLE RECORD IS FAILED, distinct from a missing one.
p = os.path.join(tmp, "broken.json"); open(p, "w").write("{not json")
leg("an unreadable record is FAILED", D.run_rates(p)["state"], "FAILED")
leg("a missing record is ABSENT", D.run_rates(os.path.join(tmp, "nope.json"))["state"], "ABSENT")

# 6. THE COMPARISON REFUSES rather than comparing against a half-read side.
c = D.compare(os.path.join(tmp, "withheld.json"))
leg("a comparison with an ABSENT run is ABSENT, not a table of zeros", c["state"], "ABSENT")

# 7. THE REFERENCE REPORTS ITS OWN COVERAGE and never folds an unknown term in.
ref = D.reference_rates()
leg("the reference is MEASURED", ref["state"], "MEASURED")
leg("  ...and names the terms it could not map", bool(ref["unmapped"]), True)
leg("  ...with coverage under 100, stated rather than implied", ref["coverage"] < 100.0, True)

# 8. A REFERENCE WITH NO BEATS IS ABSENT, not a table of zeros.
p = rec("emptyref.json", {"beats": [], "distinct_videos": 0})
leg("a reference with no beats is ABSENT", D.reference_rates(p)["state"], "ABSENT")

print("\n%s" % ("all legs green" if not fail else "%d LEG(S) FAILED" % fail))
sys.exit(1 if fail else 0)
