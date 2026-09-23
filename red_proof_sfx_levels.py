#!/usr/bin/env python3
"""RED proof for smoke_sfx_levels.py — mutations aimed at the LEVELS RECORD.

The population is thirteen measured files, so every mutation corrupts a row the
way a bad render would and asserts the shipped check refuses it. Loosening a
threshold the population already satisfies would change bytes and no verdict —
the eighth way a mutation stops mutating, and it has cost four proofs today.
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_sfx_levels.py")
LEVELS = os.path.join(HERE, "measured", "SFX_LEVELS.json")
DELIVERED = os.path.join(HERE, "measured", "sfx_levelled")


def _env():
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def _clip(d):
    d[0]["TP_after"] = -0.4
    return d


def _quiet_unexplained(d):
    r = next(x for x in d if x["bound_by"] == "loudness")
    r["M_after"] = -19.5
    return r and d


def _spread(d):
    ld = [x for x in d if x["bound_by"] == "loudness"]
    ld[0]["M_after"] = -12.5
    ld[0]["bound_by"] = "loudness"
    return d


def _trimmed(d):
    d[0]["dur_after"] = round(d[0]["dur_before"] - 0.25, 3)
    return d


def _unpadded(d):
    r = next(x for x in d if x["dur_after"] <= 0.51)
    r["dur_after"] = 0.235
    return d


def _one_missing(d):
    return d[:-1]


MUT = [
    ("a_file_breaches_the_peak_ceiling", _clip,
     "L1 no_file_over_the_true_peak_ceiling",
     lambda d: all(x["TP_after"] <= -1.0 for x in d)),
    ("a_file_is_quiet_for_no_stated_reason", _quiet_unexplained,
     "L2 every_file_is_at_target_or_peak_bound",
     lambda d: any(x["bound_by"] == "loudness" for x in d)),
    ("the_levelled_files_drift_apart", _spread,
     "L3 loudness_bound_files_share_one_level",
     lambda d: len([x for x in d if x["bound_by"] == "loudness"]) >= 2),
    ("a_tail_is_trimmed", _trimmed,
     "L4 tails_and_durations_preserved",
     lambda d: abs(d[0]["dur_before"] - d[0]["dur_after"]) < 0.03),
    ("a_short_file_loses_its_padding", _unpadded,
     "L5 no_file_below_one_momentary_block",
     lambda d: all(x["dur_after"] >= 0.40 for x in d)),
    ("a_file_vanishes_from_the_record", _one_missing,
     "L0 thirteen_levelled_files_on_disk",
     lambda d: len(d) == 13),
]


def run():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def failed(out, phrase):
    return any(phrase in ln and "FAIL" in ln for ln in out.splitlines())


def rename_mutation():
    """The stale-line defect, where it actually lives: on disk.

    My first version rewrote the `file` field in the record instead, which made
    L0 fire — the record named a file that was not there — and L6 never spoke.
    rc=1 with leg_failed=False is the signature of a red that is not about the
    property, and it is the reason every mutation here carries the phrase its
    target leg prints rather than just an exit code.
    """
    import glob
    cur = glob.glob(os.path.join(DELIVERED, "boom - *.mp3"))
    if len(cur) != 1:
        return None, "expected exactly one boom file, found %d" % len(cur)
    stale = os.path.join(DELIVERED, "boom - deep low impact for a heavy landing.mp3")
    os.rename(cur[0], stale)
    return (cur[0], stale), None


def main():
    rc, out = run()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-800:])
        return 2
    print("baseline green.\n")
    raw = io.open(LEVELS, encoding="utf-8").read()
    red, vacuous = 0, []
    for name, apply_, phrase, pre in MUT:
        d = json.loads(raw)
        if not pre(d):
            vacuous.append(name)
            print("  %-42s VACUOUS   precondition false before the edit" % name)
            continue
        io.open(LEVELS, "w", encoding="utf-8").write(
            json.dumps(apply_(json.loads(raw)), indent=1))
        rc2, out2 = run()
        io.open(LEVELS, "w", encoding="utf-8").write(raw)
        ok = rc2 != 0 and failed(out2, phrase)
        red += 1 if ok else 0
        print("  %-42s %s   rc=%d leg_failed=%s"
              % (name, "RED " if ok else "NOT RED", rc2, failed(out2, phrase)))
    # THE ON-DISK MUTATION, run after the record ones so a failure here cannot
    # leave a renamed file behind a half-restored record.
    moved, why = rename_mutation()
    if moved is None:
        print("  %-42s HARNESS FAILURE: %s" % ("a_filename_keeps_the_old_menu_line", why))
    else:
        rc2, out2 = run()
        os.rename(moved[1], moved[0])
        ok = rc2 != 0 and failed(out2, "L6 filenames_are_the_current_menu_lines")
        red += 1 if ok else 0
        MUT.append(("a_filename_keeps_the_old_menu_line", None, None, None))
        print("  %-42s %s   rc=%d leg_failed=%s"
              % ("a_filename_keeps_the_old_menu_line", "RED " if ok else "NOT RED",
                 rc2, failed(out2, "L6 filenames_are_the_current_menu_lines")))

    if io.open(LEVELS, encoding="utf-8").read() != raw:
        print("\nHARNESS FAILURE: residue left in the levels record")
        return 2
    print("\n%d/%d RED-proven%s" % (red, len(MUT),
          ("; VACUOUS: " + ", ".join(vacuous)) if vacuous else ""))
    return 0 if (MUT and red == len(MUT) and not vacuous) else 1


if __name__ == "__main__":
    sys.exit(main())
