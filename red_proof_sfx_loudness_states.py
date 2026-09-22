#!/usr/bin/env python3
"""RED proof for smoke_sfx_loudness_states.py.

Mutation 1 restores the claim I actually published — a short sound classified as
silent — and it is the reason this check exists.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_sfx_loudness_states.py")

MUTATIONS = [
    # THE RULE INVERTS: a sound too short to integrate is called MEASURABLE, so
    # its floor reading becomes a value. This is exactly what I did by hand.
    ("short_sound_called_measurable", "smoke_sfx_loudness_states.py",
     '    return "ABSENT_TOO_SHORT" if duration_ms < R128_WINDOW_MS else "MEASURABLE"',
     '    return "MEASURABLE"',
     "L2 short_population_present",
     lambda s: 'if duration_ms < R128_WINDOW_MS' in s),
    # THE WINDOW GOES TO ZERO — same defect, reached by moving the constant
    # rather than the branch. Nothing is ever too short, so nothing is ever a
    # floor, and the four come back as measured silence.
    ("integration_window_goes_to_zero", "smoke_sfx_loudness_states.py",
     "R128_WINDOW_MS = 400.0", "R128_WINDOW_MS = 0.0",
     "L2 short_population_present",
     lambda s: "R128_WINDOW_MS = 400.0" in s),
    # THE PEAK READER GOES BLIND. volumedetect prints at INFO level; a pattern
    # that stops matching returns None for every peak and L1 must catch it
    # rather than the table filling with nulls that read as quiet.
    ("peak_reader_goes_blind", "smoke_sfx_loudness_states.py",
     r'r"max_volume:\s*(-?[\d.]+) dB"', r'r"maxvolumeXX:\s*(-?[\d.]+) dB"',
     "L1 every_file_measured",
     lambda s: r'max_volume:\s*(-?[\d.]+) dB' in s),
    # THE SCOPE WIDENS BACK TO THE DIRECTORY, which is what failed on the first
    # run: fifteen files against a menu describing thirteen, and the peak range
    # claim reads false on sounds nobody can be served.
    ("scope_widens_to_the_directory", "smoke_sfx_loudness_states.py",
     'names = sorted(f for f in os.listdir(SOUNDS) if f.endswith(".mp3") and f in live)',
     'names = sorted(f for f in os.listdir(SOUNDS) if f.endswith(".mp3"))',
     "L0 corpus_nonempty",
     lambda s: 'f.endswith(".mp3") and f in live' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    p = subprocess.run(["git", "status", "--porcelain", "smoke_sfx_loudness_states.py"],
                       cwd=HERE, capture_output=True, text=True)
    return p.stdout.strip()


def main():
    base = residue()
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:])
        return 2
    print("baseline green.\n")

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-34s HARNESS FAILURE  anchor %dx in %s" % (name, n, target))
            continue
        if pre is not None and not pre(src):
            print("  %-34s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            compile(mutant, path, "exec")
        except SyntaxError as e:
            print("  %-34s HARNESS FAILURE  mutant will not parse (%s)" % (name, e))
            continue
        open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-34s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue()
        if r != base:
            print("     RESIDUE after %s: %r" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
