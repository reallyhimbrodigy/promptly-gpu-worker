#!/usr/bin/env python3
"""A sound's loudness is a STATE, and it is re-derived from the file every run.

WHY THIS IS A DERIVATION AND NOT A TABLE, which is the whole point.

The four-short-sounds finding now exists in two places: my
measured/SFX_INVENTORY_2026-09-21.md, and `sfx_chatcut_assets.json` in Builder
1's lane, which recorded it CORRECTLY days earlier — the same four names, the
same peaks, stated as ABSENT_TOO_SHORT with the EBU R128 integration gate as the
reason.

I then published "camera-flash is MEASURED SILENT at -70.0 LUFS" and he passed
it to Zac without checking it against his own record. Two failures, not one, and
his is the worse half: I read an instrument's floor as a value; he had the
correct STATE written down and did not read it. A record nobody consults is not
a record, and the entire argument for writing states instead of numbers is that
the next reader gets the state. He was the next reader.

SO THE FIX IS NOT A THIRD COPY, AND NOT A CHECK THAT TWO COPIES AGREE.
lane_contract.py exists because "a check that two copies agree is a worse answer
than not having two copies". Applied here: this asserts nothing about either
lane's file. It MEASURES THE MP3s and derives the states, so neither record can
drift and no reader has to pick which one to trust.

THE PROPERTY, in one line: below the integration window there is no integrated
reading, so the state is ABSENT_TOO_SHORT and a number there is a floor wearing
a measurement's clothes.

  EBU R128 integrates over ~400ms. Four of the thirteen are 151-254ms and read
  -70.0 LUFS on ChatCut's own asset card while peaking between -5.4 and -0.7 dB.

AND THE EXPOSURE IS ON THEIR SURFACE, NOT OURS. ChatCut prints that -70.0 on the
card their agent reads. 4 of 13 is 31% of the sound library legible as silent to
anything that selects, sorts, gains or ducks by that column. We cannot fix their
field; what we can do is never restate it as silence, and say so where the
column is read.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lane_contract as lc                                     # noqa: E402
SOUNDS = "/Users/zaclibman/promptly-gpu-worker/hype-harness/src/assets/sounds"
RECORD = os.path.join(HERE, "measured", "SFX_LOUDNESS_STATES.json")

# EBU R128's integration window. A programme shorter than this has no integrated
# loudness — the gate never opens and the meter reports its floor.
R128_WINDOW_MS = 400.0
FLOOR_LUFS = -70.0

FAILS = []


def leg(name, ok, got):
    print("  %-40s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def measure(path):
    """-> (duration_ms, peak_dB) or (None, None). Three states, never a value
    invented from a failure.

    volumedetect prints at INFO level, so this must NOT run with -v error —
    that exact mistake returned null for both readings once in this repo and the
    block still reported MEASURED.
    """
    try:
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=60)
        dur = float((d.stdout or "").strip()) * 1000.0
    except Exception:                                          # noqa: BLE001
        return None, None
    try:
        v = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                            "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=120)
        m = re.search(r"max_volume:\s*(-?[\d.]+) dB", (v.stderr or "") + (v.stdout or ""))
        return dur, (float(m.group(1)) if m else None)
    except Exception:                                          # noqa: BLE001
        return dur, None


def state_for(duration_ms):
    """The only rule in this file."""
    if duration_ms is None:
        return "FAILED"
    return "ABSENT_TOO_SHORT" if duration_ms < R128_WINDOW_MS else "MEASURABLE"


def main():
    if not os.path.isdir(SOUNDS):
        print("HARNESS FAILURE: no sound corpus at %s — this check measures "
              "files and cannot run without them" % SOUNDS)
        return 2
    # SCOPED TO THE LIVE LIBRARY, NOT THE DIRECTORY, and L4 is what forced it.
    # The directory holds FIFTEEN mp3s; the library holds THIRTEEN.
    # awkward-moment and imposter are on disk and not in the live set, and
    # measuring them dragged the reported peak range to -8.3 dB while the menu
    # — which describes the thirteen — says -5.4. The leg failed on a corpus
    # wider than the claim it was checking, which is the population lesson
    # arriving in my own new check on its first run.
    live = set(lc.live_set()["by_family"]["sfx"])
    names = sorted(f for f in os.listdir(SOUNDS) if f.endswith(".mp3") and f in live)
    extra = sorted(f for f in os.listdir(SOUNDS)
                   if f.endswith(".mp3") and f not in live)

    # A CHECK OVER AN EMPTY POPULATION ASSERTS NOTHING.
    leg("L0 corpus_nonempty", len(names) == 13,
        "%d live sound(s) measured; %d on disk and NOT in the library, excluded: %s"
        % (len(names), len(extra), [e.replace(".mp3", "") for e in extra]))
    if not names:
        return 1

    rows, failed = {}, []
    for n in names:
        dur, peak = measure(os.path.join(SOUNDS, n))
        st = state_for(dur)
        if st == "FAILED" or peak is None:
            failed.append(n)
        rows[n] = {"duration_ms": (None if dur is None else round(dur)),
                   "peak_db": peak, "integrated_state": st}

    # L1 EVERY FILE MEASURED. A file that could not be read is FAILED and must
    # not be silently absent from the table.
    leg("L1 every_file_measured", not failed, "unreadable: %s" % (failed or "none"))

    short = sorted(k for k, v in rows.items() if v["integrated_state"] == "ABSENT_TOO_SHORT")
    # L2 THE SHORT POPULATION IS NON-EMPTY, or the rule below asserts nothing.
    # Four are expected; the leg holds the count so a corpus change is visible.
    leg("L2 short_population_present", len(short) >= 4,
        "%d under %.0fms: %s" % (len(short), R128_WINDOW_MS,
                                 [s.replace(".mp3", "") for s in short]))

    # L3 NOT ONE OF THEM IS QUIET. This is the claim I got wrong, asserted
    # against the file rather than against anybody's note: a sound too short to
    # integrate is not thereby silent, and every one of these peaks loud.
    quiet = sorted(k for k in short if (rows[k]["peak_db"] or -99) < -20.0)
    leg("L3 short_sounds_are_not_quiet", not quiet,
        "peaks %s" % {k.replace(".mp3", ""): rows[k]["peak_db"] for k in short})

    # L4 THE STYLEGUIDE CLAIM IS TRUE. The menu their agent reads says every
    # sound is audible with a peak range; if that range stops covering the
    # corpus the menu has become a stale note in front of the agent.
    peaks = [v["peak_db"] for v in rows.values() if v["peak_db"] is not None]
    lo, hi = (min(peaks), max(peaks)) if peaks else (None, None)
    leg("L4 styleguide_peak_range_holds",
        peaks and lo >= -5.5 and hi <= 0.0,
        "measured range %.1f..%.1f dB; menu says -5.4..0.0" % (lo, hi) if peaks else "no peaks")

    # The record is an OUTPUT, not an input. Nothing above reads it.
    out = {"_what": "Derived every run from the mp3s in hype-harness by "
                    "smoke_sfx_loudness_states.py. An OUTPUT, never an input — "
                    "no leg above reads this file, so it cannot go stale and be "
                    "believed.",
           "_rule": "EBU R128 integrates over ~%.0fms. Below that there is no "
                    "integrated reading and the meter reports its floor "
                    "(%.1f LUFS). The state is ABSENT_TOO_SHORT; a number there "
                    "is a floor wearing a measurement's clothes."
                    % (R128_WINDOW_MS, FLOOR_LUFS),
           "_prior_record": "sfx_chatcut_assets.json in Builder 1's lane recorded "
                            "these four correctly, with these peaks, days earlier. "
                            "It was not consulted before a wrong number was "
                            "published. That is why this derives rather than "
                            "compares — two records needing an agreement check is "
                            "the defect, not the cure.",
           "_scope": "The THIRTEEN in lane_contract.live_set()['by_family']['sfx']. "
                     "Fifteen mp3s sit in the directory; awkward-moment and "
                     "imposter are not in the live set and are excluded, because "
                     "the menu's peak-range claim is about the thirteen and "
                     "measuring the wider set makes the claim read false.",
           "sounds": rows}
    json.dump(out, open(RECORD, "w"), indent=2, ensure_ascii=False)
    open(RECORD, "a").write("\n")

    print("%d/%d legs ok" % (5 - len(FAILS), 5))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
