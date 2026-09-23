#!/usr/bin/env python3
"""The thirteen sounds land at one level, under one ceiling, with their tails.

THE STATISTIC ZAC NAMED DOES NOT EXIST AT THESE DURATIONS. Short-term LUFS is a
3-SECOND window; only two of the thirteen files are that long, and ebur128
reported -120.7 — its floor, meaning no short-term window was ever filled — for
the other eleven. Targeting it would have been normalising against a number the
instrument never produced, which is the same shape as the integrated reading
that has no block: the floor value IS the tell.

MOMENTARY (400 ms) IS THE VALID STATISTIC, and it is valid only because the
four sub-400ms files were already tail-padded to 500 ms — that padding, ruled
for a different reason, is what makes one momentary block available at all.

PURE GAIN, NO LIMITER ANYWHERE. Every delivered file is the original scaled by
one constant, so every transient and every tail sample is intact. "Keep the
transient start" forbids the alternative, and it is why five files stop short
of -14: their true peak reaches the ceiling first, and closing the last few dB
would mean squashing exactly the attack that was to be preserved.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = os.path.join(HERE, "measured", "SFX_LEVELS.json")
DELIVERED = os.path.join(HERE, "measured", "sfx_levelled")
TARGET_M, TP_CEIL = -14.0, -1.0
FAILS, NLEGS = [], 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    rows = json.load(open(LEVELS, encoding="utf-8"))

    # L0 ALL THIRTEEN, AND THE FILES EXIST. A levels record describing files
    # that are not on disk is a record of an intention.
    on_disk = sorted(f for f in os.listdir(DELIVERED) if f.endswith(".mp3"))
    missing = [r["file"] for r in rows if r["file"] not in on_disk]
    leg("L0 thirteen_levelled_files_on_disk",
        len(rows) == 13 and len(on_disk) == 13 and not missing,
        "%d rows, %d files, missing=%s" % (len(rows), len(on_disk), missing or "none"))

    # L1 NOTHING BREACHES THE TRUE-PEAK CEILING. Two files were ABOVE 0 dBTP
    # before this ran (punchsfx +1.5, transition-sfx +0.6) — already clipping.
    over = [(r["name"], r["TP_after"]) for r in rows if r["TP_after"] > TP_CEIL]
    leg("L1 no_file_over_the_true_peak_ceiling", not over,
        "%d of %d over %.1f dBTP: %s" % (len(over), len(rows), TP_CEIL, over or "none"))

    # L2 EVERY FILE IS AT THE TARGET OR HELD OFF IT BY THE CEILING — never
    # short for an unexplained reason. The two states are what makes a quiet
    # file readable as a decision rather than as a miss.
    unexplained = [(r["name"], r["M_after"], r["bound_by"]) for r in rows
                   if abs(r["M_after"] - TARGET_M) > 0.2 and r["bound_by"] != "TRUE PEAK"]
    leg("L2 every_file_is_at_target_or_peak_bound", not unexplained,
        "%d unexplained: %s" % (len(unexplained), unexplained or "none"))

    # L3 THE LOUDNESS-BOUND FILES ARE AT ONE LEVEL. The whole point: a spread
    # here is the thing a listener hears between two sounds in one edit.
    ld = [r["M_after"] for r in rows if r["bound_by"] == "loudness"]
    leg("L3 loudness_bound_files_share_one_level",
        bool(ld) and (max(ld) - min(ld)) <= 0.2,
        "%d file(s), spread %.2f dB" % (len(ld), (max(ld) - min(ld)) if ld else 0))

    # L4 NO TAIL WAS TRIMMED AND NO HEAD WAS CUT. Pure gain must not change a
    # duration; a changed one means something resampled or trimmed.
    moved = [(r["name"], r["dur_before"], r["dur_after"]) for r in rows
             if abs(r["dur_before"] - r["dur_after"]) >= 0.03]
    leg("L4 tails_and_durations_preserved", not moved,
        "%d changed: %s" % (len(moved), moved or "none"))

    # L5 THE PADDING THAT MAKES THE MEASUREMENT POSSIBLE IS STILL THERE. A
    # momentary block is 400 ms; a file shorter than that has no valid reading
    # at all, so the >=500 ms floor is load-bearing for the instrument, not
    # only for their agent's silence detection.
    short = [(r["name"], r["dur_after"]) for r in rows if r["dur_after"] < 0.40]
    leg("L5 no_file_below_one_momentary_block", not short,
        "%d under 400ms: %s" % (len(short), short or "none"))

    # L6 EVERY FILE IS NAMED BY ITS CURRENT MENU LINE. The line IS the name;
    # the set shipped carrying v1 lines while the menu had moved to v2.1.
    lines = json.load(open(os.path.join(HERE, "measured", "MENU_LINES.json"),
                           encoding="utf-8"))["sounds"]
    want = {l + ".mp3" for l in lines}
    wrong = sorted(set(on_disk) - want)
    leg("L6 filenames_are_the_current_menu_lines", not wrong,
        "%d not a current line: %s" % (len(wrong), wrong or "none"))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
