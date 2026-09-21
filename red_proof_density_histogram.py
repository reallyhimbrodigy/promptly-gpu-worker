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
def it(t, f0=0, f1=0, s0=0, s1=0):
    d = {"itemType": t}
    if f1:
        d["timelineRange"] = {"fromFrame": f0, "toFrame": f1}
        d["sourceRange"] = {"start": s0, "end": s1}
    return d
# 50.0s at 30fps = 1500 frames, stated the way a real record states it
p = rec("ok.json", {"export": {"state": "MEASURED"}, "timeline_sample": {"items": [
    it("video", 0, 1500, 0, 50_000_000), it("video"),
    it("caption"), it("motion-graphic"), it("audio"), it("effect")]}})
r = D.run_rates(p)
leg("an exported timeline is MEASURED", r["state"], "MEASURED")
leg("  ...two cuts over 50s is 1.0 per 25s", r["per_25s"]["cut"], 1.0)
leg("  ...and a motion-graphic counts as a card", r["counts"]["card"], 1)

# 3. ZERO IS A MEASUREMENT WHEN THE TIMELINE WAS READ. This is the other half.
p = rec("nozoom.json", {"export": {"state": "MEASURED"}, "timeline_sample": {
        "items": [it("video", 0, 750, 0, 25_000_000)]}})
r = D.run_rates(p)
leg("a family with no items on a READ timeline is 0.0 and MEASURED",
    (r["state"], r["per_25s"]["zoom"]), ("MEASURED", 0.0))

# 4. NO DURATION MEANS NO NORMALISATION. Not a divide, not a zero.
p = rec("nodur.json", {"export": {"state": "MEASURED"}, "timeline_sample": {
        "items": [{"itemType": "video"}]}})
leg("items with no frame/source ranges are ABSENT — fps is never defaulted",
    D.run_rates(p)["state"], "ABSENT")

# 4b. TWO RATES IN ONE TIMELINE IS FAILED, not an average. A divisor that is two
#     numbers is not a divisor, and averaging would publish a duration nothing has.
p = rec("mixedfps.json", {"export": {"state": "MEASURED"}, "timeline_sample": {"items": [
        it("video", 0, 750, 0, 25_000_000), it("video", 750, 1500, 0, 12_500_000)]}})
leg("items implying two frame rates are FAILED, never averaged",
    D.run_rates(p)["state"], "FAILED")

# 4c. THE DERIVATION MATCHES THE REAL RECORD. 2032 frames over 72.571429s is 28fps,
#     which is th_kolkata_en's real rate and not the 30 a default would supply.
_real = "/tmp/kolkata1.json"
if os.path.isfile(_real):
    _items = json.load(open(_real))["timeline_sample"]["items"]
    _secs, _why = D._duration_s(_items)
    leg("the real record's duration derives to its fixture's 72.571s",
        (_secs is not None and abs(_secs - 72.571) < 0.01), True)

# 5. AN UNREADABLE RECORD IS FAILED, distinct from a missing one.
p = os.path.join(tmp, "broken.json"); open(p, "w").write("{not json")
leg("an unreadable record is FAILED", D.run_rates(p)["state"], "FAILED")
leg("a missing record is ABSENT", D.run_rates(os.path.join(tmp, "nope.json"))["state"], "ABSENT")

# 6. THE COMPARISON REFUSES rather than comparing against a half-read side.
c = D.compare(os.path.join(tmp, "withheld.json"))
leg("a comparison with an ABSENT run is ABSENT, not a table of zeros", c["state"], "ABSENT")

# 7. THE ONE PUBLISHED TABLE IS THE ONLY REFERENCE. There is no second
#    derivation to disagree with it.
ref = D.reference_rates()
leg("the published reference table is MEASURED", ref["state"], "MEASURED")
leg("  ...carries one denominator", ref["wall_s"], 426.093)
leg("  ...and a family a pass never named is null, never 0.0",
    (ref["passes"]["A"]["per_25s"]["sfx"], ref["passes"]["B"]["per_25s"]["zoom"]), (None, None))

# 11. THE REFUSAL TELL, AGAINST THE THREE REAL RECORDS Builder 1 supplied.
#     kolkata-9 is the trap: it EXPORTED cleanly with four cuts and zero
#     graphics, and it carries no unsatisfied refusal at the end — so a check
#     keyed on final state passes it as editorial restraint while its card rate
#     of 0.00 is measuring a shape refusal that bounced a whole call.
_R = "/tmp/agentic-records/kolkata-%d.json"
if os.path.isfile(_R % 9):
    r9 = D.refusal_suspect(_R % 9)
    leg("kolkata-9 is flagged despite a clean final state", r9["suspect"], True)
    leg("  ...and it is the vanished adds that flag it, not a final-state tell",
        "adds dropped" in r9["why"], True)
    leg("  ...7 then 4, which is the three graphics that went unnamed",
        r9["adds_per_write_call"], [7, 4])
    # the final-state tells alone would NOT have caught it
    leg("  ...and its final state carries no refusal at all",
        any(k in r9["why"] for k in ("unbuilt", "gate:")), False)
    for _n in (10, 11):
        leg("kolkata-%d is flagged" % _n, D.refusal_suspect(_R % _n)["suspect"], True)
    # THE RULE THAT NEEDS A FIELD THE RECORD LACKS IS ABSENT, NOT APPROXIMATED.
    leg("the per-turn fault-class rule is ABSENT with its reason",
        D.refusal_suspect(_R % 11)["unanswered_classes"]["state"], "ABSENT")

# 12. A CLEAN RUN IS NOT FLAGGED. Without this the tell is a rubber stamp.
p = rec("clean.json", {"export": {"state": "MEASURED"},
                       "shape": {"calls": [{"in": json.dumps({"adds": [1, 2]})},
                                           {"in": json.dumps({"adds": [1, 2, 3]})}]},
                       "withheld": {}, "gate_findings": []})
leg("a run with non-decreasing adds and no faults is NOT flagged",
    D.refusal_suspect(p)["suspect"], False)

print("\n%s" % ("all legs green" if not fail else "%d LEG(S) FAILED" % fail))
sys.exit(1 if fail else 0)
