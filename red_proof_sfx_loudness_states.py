#!/usr/bin/env python3
"""RED proof for smoke_sfx_loudness_states.py.

Mutation 1 restores the claim I actually published -- a short sound classified
as silent -- and it is the reason this check exists.

THIS PROOF ALSO HAD THE DEFECT IT IS SUPPOSED TO CATCH, and committing it is how
it surfaced. `residue()` watched the file the proof MUTATES and not the file the
smoke WRITES. The smoke's record is an output; running the smoke under the
`scope_widens_to_the_directory` mutant makes it write FIFTEEN sounds with a peak
range down to -8.3 dB, and the proof restored the source, exited 0, and left the
mutant's record sitting on disk -- where `git add -A` committed it. The published
record of the derivation then WAS a mutation's output, under a green 4/4.

That is the standing residue rule with one word changed. The rule says a
mutating sweep must `git status --porcelain` THE MUTATED FILE after every
harness. It is not enough: **a mutating harness must account for every file the
mutated code WRITES.** The smoke is a writer, so running it under mutation runs
a writer under mutation. OUTPUTS below is snapshotted from the green baseline
and restored beside the source, and residue() watches all of it.
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_sfx_loudness_states.py")

# Files the SMOKE writes. Not mutated -- restored, because a mutant's output is
# indistinguishable from a real reading once it is on disk under the same name.
OUTPUTS = ["measured/SFX_LOUDNESS_STATES.json"]
# Everything whose dirtiness would mean this proof left something behind.
WATCHED = ["smoke_sfx_loudness_states.py", "measured/MENU_STYLEGUIDE.txt"] + OUTPUTS

MUTATIONS = [
    # THE RULE INVERTS: a sound too short to integrate is called MEASURABLE, so
    # its floor reading becomes a value. This is exactly what I did by hand.
    ("short_sound_called_measurable", "smoke_sfx_loudness_states.py",
     '    return "ABSENT_TOO_SHORT" if duration_ms < R128_WINDOW_MS else "MEASURABLE"',
     '    return "MEASURABLE"',
     "L2 short_population_present",
     lambda s: 'if duration_ms < R128_WINDOW_MS' in s),
    # THE WINDOW GOES TO ZERO -- same defect, reached by moving the constant
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

    # -- THE FALSY ZERO, restored in both of its spellings --------------------
    # AND NEITHER OF THESE CAN BE PROVEN AGAINST THE CORPUS, which is why L3b
    # exists. The four short sounds peak -0.8/-4.5/-5.4/-0.7; not one is 0.0, so
    # both mutants below leave every corpus verdict unchanged and L3 stays green.
    # The defect is real, latent, and invisible to the only population L3 reads.
    # Aimed at L3b, which drives loudness_class over a fixture carrying the 0.0
    # that punchsfx and transition-sfx actually measure.
    ("full_scale_read_as_quiet", "smoke_sfx_loudness_states.py",
     '    if peak_db is None:\n        return "UNREADABLE"\n'
     '    return "QUIET" if peak_db < QUIET_DB else "LOUD"',
     '    return "QUIET" if (peak_db or -99) < QUIET_DB else "LOUD"',
     "L3b zero_is_a_value_not_a_sentinel",
     lambda s: '0.0: "LOUD"' in s),
    # THE ABSENCE TEST GOES FALSY -- the same fold reached from the other side.
    # `not peak_db` is True for None AND for 0.0, so the loudest possible sound
    # is reported UNREADABLE instead of QUIET. Different wrong answer, same
    # cause: a legitimate zero standing in for a missing reading.
    ("absence_read_as_falsy", "smoke_sfx_loudness_states.py",
     "    if peak_db is None:", "    if not peak_db:",
     "L3b zero_is_a_value_not_a_sentinel",
     lambda s: '0.0: "LOUD"' in s),

    # -- THE MENU DRIFTS, in both directions ----------------------------------
    # BUILDER 1'S SCENARIO VERBATIM: someone edits the menu and the check stays
    # green. Under the old literal-based leg BOTH of these passed -- it compared
    # the corpus against floats typed in the check and never read the menu at
    # all, so no edit to the menu could ever fail it.
    ("menu_claim_goes_narrow", "measured/MENU_STYLEGUIDE.txt",
     "peaks between -5.4 dB and 0.0 dB, measured",
     "peaks between -3.0 dB and 0.0 dB, measured",
     "L4 menu_corpus_range_is_exact",
     lambda s: "peaks between -5.4 dB and 0.0 dB" in s),
    # THE CLAIM GOES WIDER THAN THE TRUTH, which is the half a floor can never
    # catch: `lo >= -5.5` is satisfied by a menu advertising -9.9, so the agent
    # is told a quieter sound exists than does.
    ("menu_claim_goes_wide", "measured/MENU_STYLEGUIDE.txt",
     "peaks between -5.4 dB and 0.0 dB, measured",
     "peaks between -9.9 dB and 0.0 dB, measured",
     "L4 menu_corpus_range_is_exact",
     lambda s: "peaks between -5.4 dB and 0.0 dB" in s),
    # THE SHORT-SOUND NOTE DRIFTS. It is the sentence a reader of the -70.0
    # column lands on, so it is the one that must not rot.
    ("menu_short_note_drifts", "measured/MENU_STYLEGUIDE.txt",
     "peaking between -5.4 dB and -0.7 dB",
     "peaking between -5.4 dB and -3.0 dB",
     "L5 menu_short_note_range_is_exact",
     lambda s: "peaking between -5.4 dB and -0.7 dB" in s),
    # A SOUND LEAVES THE MENU while staying in the library -- a capability the
    # agent cannot name is indistinguishable from one it declined.
    ("menu_drops_a_sound", "measured/MENU_STYLEGUIDE.txt",
     "\nrizz — rising flourish.", "",
     "L6 menu_lists_exactly_the_live_sounds",
     lambda s: "rizz — rising flourish." in s),

    # A STATED DURATION DRIFTS PAST THE WINDOW, making the note self-refuting:
    # "shorter than 400ms" beside a figure of 435ms, in front of their agent.
    ("menu_duration_contradicts_the_window", "measured/MENU_STYLEGUIDE.txt",
     "camera-flash 235ms", "camera-flash 435ms",
     "L7 menu_short_durations_are_true",
     lambda s: "camera-flash 235ms" in s),

    # -- THE PARSERS GO BLIND -------------------------------------------------
    # A parser that stops matching returns None, and None must FAIL rather than
    # default -- otherwise the leg passes because it read nothing, which is this
    # repo's oldest false green.
    ("range_parser_goes_blind", "smoke_sfx_loudness_states.py",
     r'm = re.search(verb + r"\s+(-?[\d.]+) dB and (-?[\d.]+) dB", text)',
     r'm = re.search(verb + r"\s+(-?[\d.]+) dBX and (-?[\d.]+) dB", text)',
     "L4 menu_corpus_range_is_exact",
     lambda s: r'\s+(-?[\d.]+) dB and (-?[\d.]+) dB' in s),
    # THE TWO SENTENCES COLLAPSE INTO ONE. The verb is the only thing separating
    # the corpus claim from the short-sound note; read the wrong one and L5
    # checks the four short sounds against the whole corpus's range.
    ("verb_selector_collapses", "smoke_sfx_loudness_states.py",
     'sclaim = stated_range(menu, "peaking between")',
     'sclaim = stated_range(menu, "peaks between")',
     "L5 menu_short_note_range_is_exact",
     lambda s: 'stated_range(menu, "peaking between")' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue(base_bytes):
    """Files whose CONTENT differs from what the baseline left on disk.

    THIS WAS A `git status --porcelain` COMPARISON AND THAT CANNOT SEE IT.
    Porcelain reports WHICH files are modified relative to HEAD, not WHAT is in
    them, so a file that is ALREADY dirty can be rewritten with entirely
    different content and the status string comes back byte-identical -- " M
    measured/SFX_LOUDNESS_STATES.json" before and after. That is how the
    fifteen-sound record got past a residue check that was watching the right
    file: I widened the watch list and left the comparison measuring the wrong
    property.

    A status is not a content. Compare the bytes.
    """
    return sorted(q for q, b in base_bytes.items()
                  if io.open(os.path.join(HERE, q), "rb").read() != b)


def snapshot(paths):
    return {q: io.open(os.path.join(HERE, q), "rb").read() for q in paths}


def restore(snap):
    for q, b in snap.items():
        io.open(os.path.join(HERE, q), "wb").write(b)


def main():
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:])
        return 2
    print("baseline green.\n")
    # SNAPSHOT AFTER THE BASELINE RUN, so the outputs held here are the ones the
    # UNMUTATED code produces. Taken before, they could be a previous mutant's.
    outs = snapshot(OUTPUTS)
    base_bytes = snapshot(WATCHED)

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = io.open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-34s HARNESS FAILURE  anchor %dx in %s" % (name, n, target))
            continue
        if pre is not None and not pre(src):
            print("  %-34s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        if target.endswith(".py"):
            try:
                compile(mutant, path, "exec")
            except SyntaxError as e:
                print("  %-34s HARNESS FAILURE  mutant will not parse (%s)" % (name, e))
                continue
        io.open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            io.open(path, "w", encoding="utf-8").write(src)
            restore(outs)          # the smoke WROTE while mutated; put it back
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-34s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue(base_bytes)
        if r:
            print("     RESIDUE after %s: %s" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
