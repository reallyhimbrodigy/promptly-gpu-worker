#!/usr/bin/env python3
"""The run line reports what landed, and says UNMEASURED rather than guessing.

DRIVEN AGAINST RUN ONE, whose surfaces are captured in
measured/RUN_ONE_SURFACES.json from the live project rather than written for
this test. Run two is then a re-run of a proven reader instead of a build under
time pressure.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import what_landed as wl                                       # noqa: E402
import judge_v2 as jv                                          # noqa: E402

FAILS = []
NLEGS = 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    S = json.load(open(os.path.join(HERE, "measured", "RUN_ONE_SURFACES.json"),
                       encoding="utf-8"))
    T = wl.build(S)
    R = T["rows"]

    leg("L0 versions_are_stated",
        bool(wl.READER_VERSION.strip()) and bool(jv.JUDGE_VERSION.strip()),
        "reader v%s judge v%s" % (wl.READER_VERSION, jv.JUDGE_VERSION))

    # L1 RUN ONE READS BACK. The integration leg — 24 cards, one cut, nothing else.
    leg("L1 run_one_table_matches_the_surfaces",
        R["captions"]["count"] == 24 and R["cuts"]["count"] == 1
        and R["transitions"]["count"] == 0 and R["graphics"]["count"] == 0,
        "captions=%s cuts=%s transitions=%s graphics=%s"
        % (R["captions"]["count"], R["cuts"]["count"],
           R["transitions"]["count"], R["graphics"]["count"]))

    # L2 NOT_READ IS NEVER RENDERED AS 0. An unread surface and an empty one are
    # the same number and different facts.
    partial = wl.build({k: v for k, v in S.items() if k != "transitions_inspected"})
    txt = wl.render(partial)
    leg("L2 unread_surface_never_prints_as_zero",
        partial["rows"]["transitions"]["state"] == "NOT_READ"
        and partial["rows"]["transitions"]["count"] is None
        and "NOT READ" in txt and "transitions  0" not in txt,
        "state=%s count=%s" % (partial["rows"]["transitions"]["state"],
                               partial["rows"]["transitions"]["count"]))

    # L3 TRANSITIONS DEDUPE BY ID. They are listed once per ENDPOINT, so the
    # same transition appears twice and counting rows doubles it.
    doubled = [{"id": "t1"}, {"id": "t1"}, {"id": "t2"}, {"id": "t2"}]
    leg("L3 transitions_dedupe_by_id",
        len(wl.dedupe_transitions(doubled)) == 2,
        "4 endpoint rows -> %d transition(s)" % len(wl.dedupe_transitions(doubled)))

    # L4 CUTS CARRY BOTH UNITS. Source removed and timeline frames are different
    # numbers — run one removed 20ms of source and the timeline lost a whole
    # 33.3ms frame — and either alone invites the other to be inferred.
    leg("L4 cuts_report_source_and_timeline",
        R["cuts"]["source_removed_ms"] == 20.0
        and R["cuts"]["timeline_frames"] == 608 and R["cuts"]["frame_ms"] == 33.3,
        "%sms source removed; %s frames; frame=%sms"
        % (R["cuts"]["source_removed_ms"], R["cuts"]["timeline_frames"],
           R["cuts"]["frame_ms"]))

    # L5 NO MEASUREMENT -> UNMEASURED, NEVER DROPPED. The rule that matters:
    # scoring dead air by assuming there was dead air convicts a correct edit on
    # a source with no silence in it.
    s = jv.score(["cut dead air and fillers"], T, silence_spans=None)
    leg("L5 dead_air_without_a_measurement_is_UNMEASURED",
        s[0]["verdict"] == "UNMEASURED",
        "verdict=%s" % s[0]["verdict"])

    # L6 A REMAINING SPAN >= 400ms IS DROPPED, and the span is in the evidence.
    s = jv.score(["cut dead air and fillers"], T,
                 silence_spans=S["export"]["silence_all_spans"])
    leg("L6 remaining_silence_is_DROPPED_with_its_span",
        s[0]["verdict"] == "DROPPED" and "0.424" in s[0]["evidence"],
        s[0]["evidence"][:74])

    # L7 THE THRESHOLD IS REAL. Sub-400ms gaps are words, not dead air; run
    # one's other three spans are 0.28-0.35s and must not convict.
    sub = [sp for sp in S["export"]["silence_all_spans"] if sp[2] * 1000 < 400]
    s = jv.score(["cut dead air and fillers"], T, silence_spans=sub)
    leg("L7 sub_threshold_gaps_are_not_dead_air",
        len(sub) == 3 and s[0]["verdict"] == "HONORED",
        "%d span(s) under 400ms -> %s" % (len(sub), s[0]["verdict"]))

    # L8 A NEGOTIATED ASK IS NOT A DROPPED ONE. The classifier answered it
    # before the box; scoring it as dropped blames the editor for a refusal.
    s = jv.score(["music"], T, silence_spans=[], negotiated=["music"])
    leg("L8 negotiated_is_not_dropped", s[0]["verdict"] == "NEGOTIATED",
        "verdict=%s" % s[0]["verdict"])

    # L9 AN ASK WITH NO ROW IS UNMEASURED. Zooms are item properties, not a row;
    # reporting them DROPPED would be the reader's gap blamed on the edit.
    s = jv.score(["zooms"], T, silence_spans=[])
    leg("L9 ask_with_no_row_is_UNMEASURED", s[0]["verdict"] == "UNMEASURED",
        "verdict=%s" % s[0]["verdict"])

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
