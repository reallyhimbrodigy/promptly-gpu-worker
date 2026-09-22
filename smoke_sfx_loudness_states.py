#!/usr/bin/env python3
"""A sound's loudness is a STATE, and it is re-derived from the file every run.

WHY THIS IS A DERIVATION AND NOT A TABLE, which is the whole point.

The four-short-sounds finding now exists in two places: my
measured/SFX_INVENTORY_2026-09-21.md, and `sfx_chatcut_assets.json` in Builder
1's lane, which recorded it CORRECTLY days earlier -- the same four names, the
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

  EBU R128 integrates over ~400ms. Four of the thirteen are 151-255ms and read
  -70.0 LUFS on ChatCut's own asset card while peaking between -5.4 and -0.7 dB.

AND THE EXPOSURE IS ON THEIR SURFACE, NOT OURS. ChatCut prints that -70.0 on the
card their agent reads. 4 of 13 is 31% of the sound library legible as silent to
anything that selects, sorts, gains or ducks by that column. We cannot fix their
field; what we can do is never restate it as silence, and say so where the
column is read.

-- THREE THINGS BUILDER 1 FOUND READING THIS COLD, none found by me ------------

1. L3 CARRIED A FALSY ZERO AND IT INVERTED THE LEG ON THE LOUDEST POSSIBLE
   INPUT. `(rows[k]["peak_db"] or -99) < -20.0` -- and 0.0 IS FALSY IN PYTHON,
   so a sound peaking at exactly 0.0 dBFS evaluated to -99 and was reported
   QUIET by the leg whose entire claim is "not one of them is quiet". punchsfx
   already peaks at exactly 0.0 in this corpus; it is 594ms so it sat outside
   `short` and the defect was latent, waiting for the first sub-400ms sound
   normalised to full scale -- which is what a short transient usually is.

   THE SAME `or` IDIOM, ON THE SAME DAY, IN THE SAME FAMILY I published the
   wrong number about. `or 0` on a value that might not exist is already a
   standing prohibition in this repo; nobody had written down that the
   prohibition covers `or <sentinel>` on a value that can legitimately BE zero.
   The reading is now three-state: LOUD / QUIET / UNREADABLE, and UNREADABLE
   fails rather than passing as "not quiet".

2. L4 WAS CALLED styleguide_peak_range_holds AND NEVER READ THE STYLEGUIDE.
   It compared the corpus against two float literals typed in this file, which
   duplicated the menu's sentence -- so editing the menu to say -3.0 left the
   menu WRONG and the check GREEN. That is exactly what my own `_prior_record`
   note argues against, one level up: two records needing an agreement check is
   the defect, not the cure.

   It was worse than two records in the repo. The sentence lives ONLY on
   ChatCut's servers, so the literal mirrored a remote string nobody could read
   offline. The styleGuide is now saved verbatim with provenance and THE BOUNDS
   ARE PARSED OUT OF IT. No number is typed in this check, and the question I
   asked him -- "is -5.5 fitted to today's thirteen" -- dissolves rather than
   being answered.

3. AND A LITERAL ONLY CATCHES A MENU THAT IS TOO NARROW. If the quietest sound
   leaves the library and the real range becomes -2.0..-1.0, `lo >= -5.5` still
   passes while the menu advertises -5.4..0.0 -- a claim WIDER than the truth,
   in front of their agent, which is the stale-note failure L4 says it exists to
   prevent. Both directions are asserted now: stated == measured, to the one
   decimal the sentence quotes.

THE GAP THIS DOES NOT CLOSE, said rather than papered over: whether ChatCut's
LIVE styleGuide still equals measured/MENU_STYLEGUIDE.txt is a NETWORK read and
is not what this gate proves. This proves the text we publish is TRUE OF THE
CORPUS. The provenance sidecar carries the id and the read date so the drift
window is visible instead of assumed.
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
MENU = os.path.join(HERE, "measured", "MENU_STYLEGUIDE.txt")

# EBU R128's integration window. A programme shorter than this has no integrated
# loudness -- the gate never opens and the meter reports its floor.
R128_WINDOW_MS = 400.0
FLOOR_LUFS = -70.0
# A sound is QUIET below this. Not a menu bound -- the menu's bounds are PARSED.
QUIET_DB = -20.0
# The menu quotes one decimal, so "the same number" means within half of one.
ROUNDING_DB = 0.05

FAILS = []
NLEGS = 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-40s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def measure(path):
    """-> (duration_ms, peak_dB) or (None, None). Three states, never a value
    invented from a failure.

    volumedetect prints at INFO level, so this must NOT run with -v error --
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


def loudness_class(peak_db):
    """THREE STATES, because two of them used to be one.

    `(peak or -99) < -20` folded UNREADABLE and FULL SCALE into QUIET: None and
    0.0 are both falsy, so the loudest possible sound and an unreadable one came
    out the same side. Read the absence explicitly; never let a legitimate zero
    take a sentinel's place.
    """
    if peak_db is None:
        return "UNREADABLE"
    return "QUIET" if peak_db < QUIET_DB else "LOUD"


def stated_range(text, verb):
    """Pull a claimed peak range out of the MENU's own prose.

    Two sentences state a range and they use different verbs -- the corpus claim
    says "peaks between", the short-sound note says "peaking between" -- so the
    verb is the selector and neither pattern can silently match the other's
    sentence. Returns None when absent, which the caller must fail on rather
    than default.
    """
    m = re.search(verb + r"\s+(-?[\d.]+) dB and (-?[\d.]+) dB", text)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def menu_sound_names(text):
    """The sound names the MENU lists, scoped to the SOUNDS block.

    Scoped rather than pattern-matched over the whole document: the motion
    graphics are written in the same "name -- description" shape, and a check
    that read them as sounds would compare two populations and call the
    disagreement a finding.
    """
    lo = text.find("SOUNDS.")
    hi = text.find("A NOTE ON THE LOUDNESS COLUMN")
    if lo < 0 or hi < 0 or hi <= lo:
        return None
    block = text[lo:hi]
    return sorted(m.group(1) for m in
                  re.finditer(r"^(\S+) — ", block, re.M))


def main():
    if not os.path.isdir(SOUNDS):
        print("HARNESS FAILURE: no sound corpus at %s -- this check measures "
              "files and cannot run without them" % SOUNDS)
        return 2
    if not os.path.isfile(MENU):
        print("HARNESS FAILURE: no menu text at %s -- the bounds are PARSED "
              "from it and there is no literal to fall back to, by design" % MENU)
        return 2
    menu = open(MENU, encoding="utf-8").read()

    # SCOPED TO THE LIVE LIBRARY, NOT THE DIRECTORY, and L4 is what forced it.
    # The directory holds FIFTEEN mp3s; the library holds THIRTEEN.
    # awkward-moment and imposter are on disk and not in the live set, and
    # measuring them dragged the reported peak range to -8.3 dB while the menu
    # -- which describes the thirteen -- says -5.4. The leg failed on a corpus
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
                   "peak_db": peak, "integrated_state": st,
                   "loudness": loudness_class(peak)}

    # L1 EVERY FILE MEASURED. A file that could not be read is FAILED and must
    # not be silently absent from the table.
    leg("L1 every_file_measured", not failed, "unreadable: %s" % (failed or "none"))

    short = sorted(k for k, v in rows.items() if v["integrated_state"] == "ABSENT_TOO_SHORT")
    # L2 THE SHORT POPULATION IS NON-EMPTY, or the rule below asserts nothing.
    # Four are expected; the leg holds the count so a corpus change is visible.
    leg("L2 short_population_present", len(short) >= 4,
        "%d under %.0fms: %s" % (len(short), R128_WINDOW_MS,
                                 [s.replace(".mp3", "") for s in short]))

    # L3 NOT ONE OF THEM IS QUIET -- and an unreadable peak is not an answer.
    # This is the claim I got wrong, asserted against the file rather than
    # against anybody's note. It is also where the falsy zero lived: a full-scale
    # 0.0 dB sound read as -99 and came out QUIET, inverting the leg on the
    # loudest input it can be given.
    bad = sorted(k for k in short if rows[k]["loudness"] != "LOUD")
    leg("L3 short_sounds_are_not_quiet", not bad,
        "%s | offenders: %s"
        % ({k.replace(".mp3", ""): (rows[k]["peak_db"], rows[k]["loudness"])
            for k in short}, [b.replace(".mp3", "") for b in bad] or "none"))

    # L3b THE ZERO IS ASSERTED ON A FIXTURE, BECAUSE THE CORPUS CANNOT PROVE IT.
    # L3 above cannot fire on the falsy-zero defect today: the four short sounds
    # peak -0.8/-4.5/-5.4/-0.7 and none is 0.0, so restoring `(peak or -99)`
    # changes no verdict and the mutation proving the fix would be VACUOUS -- the
    # defect is real, latent, and invisible to the only population L3 examines.
    # So the property is driven directly over loudness_class.
    #
    # 0.0 AND -0.2 ARE SAMPLED, NOT INVENTED: punchsfx and transition-sfx peak
    # at exactly 0.0 in this corpus and shockingsfx at -0.2. Fixtures are
    # sampled from production, not invented -- that is a standing law, and it is
    # what makes "a short transient normalised to full scale" a real case
    # waiting to happen rather than a hypothetical.
    fixture = {0.0: "LOUD", -0.2: "LOUD", -5.4: "LOUD",
               -25.0: "QUIET", None: "UNREADABLE"}
    got = {k: loudness_class(k) for k in fixture}
    leg("L3b zero_is_a_value_not_a_sentinel", got == fixture,
        "%s | want %s" % (got, fixture))

    # L4 THE MENU'S CORPUS CLAIM IS TRUE, PARSED FROM THE MENU. No literal: the
    # bounds come out of the styleGuide their agent reads. Asserted in BOTH
    # directions, because a range wider than the truth is as stale a note as one
    # that is too narrow, and only the narrow half used to be caught.
    peaks = [v["peak_db"] for v in rows.values() if v["peak_db"] is not None]
    lo, hi = (min(peaks), max(peaks)) if peaks else (None, None)
    claim = stated_range(menu, "peaks between")
    ok4 = bool(peaks) and claim is not None \
        and abs(claim[0] - lo) <= ROUNDING_DB and abs(claim[1] - hi) <= ROUNDING_DB
    leg("L4 menu_corpus_range_is_exact", ok4,
        "menu says %s; measured %s"
        % (claim, None if not peaks else (round(lo, 1), round(hi, 1))))

    # L5 AND THE MENU'S SHORT-SOUND NOTE IS TRUE THE SAME WAY. It states its own
    # range -- the one that proves they are not silent -- and it is the sentence
    # a reader of the -70.0 column actually lands on, so it is the one that must
    # not drift.
    speaks = [rows[k]["peak_db"] for k in short if rows[k]["peak_db"] is not None]
    slo, shi = (min(speaks), max(speaks)) if speaks else (None, None)
    sclaim = stated_range(menu, "peaking between")
    ok5 = bool(speaks) and sclaim is not None \
        and abs(sclaim[0] - slo) <= ROUNDING_DB and abs(sclaim[1] - shi) <= ROUNDING_DB
    leg("L5 menu_short_note_range_is_exact", ok5,
        "note says %s; measured %s"
        % (sclaim, None if not speaks else (round(slo, 1), round(shi, 1))))

    # L6 THE MENU LISTS EXACTLY THE SOUNDS THAT EXIST. A menu naming a sound
    # that is not there sends their agent at an asset it cannot place; a menu
    # missing one hides a capability, and "a capability the agent cannot NAME is
    # indistinguishable from one it declined".
    listed = menu_sound_names(menu)
    stems = sorted(n.replace(".mp3", "") for n in names)
    leg("L6 menu_lists_exactly_the_live_sounds",
        listed is not None and listed == stems,
        "menu %s | live %d | menu-only %s | live-only %s"
        % ("UNPARSEABLE" if listed is None else len(listed), len(stems),
           sorted(set(listed or []) - set(stems)),
           sorted(set(stems) - set(listed or []))))

    # L7 THE MENU'S FOUR STATED DURATIONS ARE TRUE. These are the last numbers
    # in the menu that were not derived, and they are the EVIDENCE for the whole
    # note: "shorter than 400ms" is what makes -70.0 unmeasurable rather than
    # silent. A duration hand-edited to 435ms would make the note contradict
    # itself in front of their agent while every other leg stayed green.
    # 2ms of slack, because the menu's figures were written with int() and these
    # with round() -- that is the only disagreement between them and it is not
    # drift.
    stated_ms = {m.group(1): int(m.group(2))
                 for m in re.finditer(r"(camera-flash|popsfx|swoosh|mouse-click)"
                                      r" (\d+)ms", menu)}
    want_ms = {"camera-flash": "camera-flash.mp3", "popsfx": "popsfx.mp3",
               "swoosh": "swoosh-sound-effects.mp3",
               "mouse-click": "mouse-click-sound.mp3"}
    drift = {k: (v, rows[want_ms[k]]["duration_ms"]) for k, v in stated_ms.items()
             if want_ms[k] in rows
             and abs(v - (rows[want_ms[k]]["duration_ms"] or 0)) > 2}
    leg("L7 menu_short_durations_are_true",
        len(stated_ms) == 4 and not drift
        and all(v < R128_WINDOW_MS for v in stated_ms.values()),
        "stated %s | drift(>2ms) %s" % (stated_ms, drift or "none"))

    # The record is an OUTPUT, not an input. Nothing above reads it.
    out = {"_what": "Derived every run from the mp3s in hype-harness by "
                    "smoke_sfx_loudness_states.py. An OUTPUT, never an input -- "
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
                            "compares -- two records needing an agreement check is "
                            "the defect, not the cure.",
           "_scope": "The THIRTEEN in lane_contract.live_set()['by_family']['sfx']. "
                     "Fifteen mp3s sit in the directory; awkward-moment and "
                     "imposter are not in the live set and are excluded, because "
                     "the menu's peak-range claim is about the thirteen and "
                     "measuring the wider set makes the claim read false.",
           # THE DENOMINATOR, because this record was committed once with FIFTEEN
           # sounds in it -- a red-proof mutant's output, left behind because the
           # proof restored the file it MUTATES and not the file the smoke WRITES.
           # A reader cannot see a wrong population in prose; they can see a count.
           "_n_sounds": len(rows),
           "_n_live_in_contract": len(live),
           "_n_excluded_on_disk": len(extra),
           "sounds": rows}
    json.dump(out, open(RECORD, "w"), indent=2, ensure_ascii=False)
    open(RECORD, "a").write("\n")

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
