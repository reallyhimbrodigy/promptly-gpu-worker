#!/usr/bin/env python3
"""RED proof for smoke_poster_frame_legible.py.

Mutation 1 reproduces EmojiCard's real defect on a component that is currently
ON the menu — EmojiCard itself cannot be used, because editing its body made it
STALE_BODY and dropped it off, which is the sha binding working correctly and
also the reason the proof has to aim somewhere else.
"""
import json
import os
import re
import subprocess
import sys

# A MUTATED .py RE-RUN IN A SUBPROCESS CAN BE SERVED A STALE .pyc, AND THE
# MUTANT THEN REPORTS THE PREVIOUS MUTATION'S BEHAVIOUR.
#
# Python invalidates its bytecode cache on (mtime, size). A red proof writes a
# mutant, runs it, restores, writes the next — all inside one mtime second — so
# a size collision between two mutants serves the earlier one's .pyc to the
# later one's run. MEASURED HERE: red_proof_what_landed reported 6/7 with the
# cache live and 7/7 with PYTHONDONTWRITEBYTECODE=1, and the NOT RED mutation
# was failing a leg belonging to the PRECEDING mutation.
#
# That is a false NOT RED — a mutation that does bite, reported as one that
# does not — and the same mechanism can produce a false RED, which is worse.
# The guard costs nothing: the child never writes bytecode, so there is nothing
# stale to serve.
def _child_env():
    import os as _os
    e = dict(_os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_poster_frame_legible.py")

MUTATIONS = [
    # EMOJICARD'S REAL DEFECT, on a menu component: content faded in from an
    # ease that is 0 on frame 0, so the poster is blank.
    ("content_fades_in_from_zero", "port/bodies/PlainText.jsx",
     '      <div style={{ transform: "translateY(" + rise + "px)", color: textColor,',
     '      <div style={{ transform: "translateY(" + rise + "px)", opacity: ease, color: textColor,',
     "L2 no_computed_opacity_outside_pins",
     lambda s: '<div style={{ transform: "translateY(" + rise + "px)", color: textColor,' in s),
    # THE DEFAULT GOES EMPTY, so the bail-out branch becomes the poster. This is
    # EmojiCard's other half: an error string reached BY THE DEFAULTS.
    ("registered_default_goes_empty", "measured/REGISTERED_DEFAULTS.json",
     '"default": "THIS IS THE PART THAT MATTERS"', '"default": ""',
     "L1 no_error_string_as_poster",
     lambda s: '"THIS IS THE PART THAT MATTERS"' in s),
    # A COMPONENT'S DEFAULT IS NOT RECORDED AT ALL. Silence here is how the
    # blank one got through the first time, so it must not read as a pass.
    ("default_unrecorded", "measured/REGISTERED_DEFAULTS.json",
     '"QuoteCard":', '"QuoteCardXX_REMOVED":',
     "L1 no_error_string_as_poster",
     lambda s: '"QuoteCard":' in s),
    # A PIN FOR A COMPONENT THAT NO LONGER RAMPS OPACITY is a stale argument,
    # and a stale note is read as fact by the next reader.
    ("pin_goes_stale", "smoke_poster_frame_legible.py",
     '    "DepthPull": "the haze and orbs fade in and out across the pull",',
     '    "DepthPull": "the haze and orbs fade in and out across the pull",\n'
     '    "PlainText": "PIN FOR A COMPONENT THAT DOES NOT RAMP OPACITY",',
     "L3 no_stale_opacity_pins",
     lambda s: '"DepthPull": "the haze' in s),
    # ONE OF THE THIRTEEN REACHES THE MENU WITHOUT A POSTER. The queue is only
    # safe while none of them is offered; the day one is, L4c must fire on it.
    # THE OFFERED-CHECK GOES BLIND. Editing the record cannot put a queued
    # component on the menu — the menu is DERIVED — so the rule is hoisted into
    # queued_on_menu() and mutated there. Break the intersection and a promoted
    # component with no poster stops being reported.
    ("offered_check_goes_blind", "smoke_poster_frame_legible.py",
     '    return sorted(set(queue or []) & set(menu or []))',
     '    return sorted(set(queue or []) & set())',
     "L4d queue_recorded_and_off_menu",
     lambda s: 'set(queue or []) & set(menu or [])' in s),
    # THE QUEUE GOES QUIET — emptied, so "no offered component has an unresolved
    # slot" starts reading as "no component does".
    ("queue_goes_quiet", "measured/REGISTERED_DEFAULTS.json",
     '        "CardSwipe",\n        "DipToBlack",\n        "SlideOver",',
     '        "CardSwipe",',
     "L4d queue_recorded_and_off_menu",
     lambda s: '        "CardSwipe",\n        "DipToBlack",' in s),
    # THE FALLBACK DETECTOR GOES BLIND: with the pattern broken it finds no
    # bail-out branches at all, and L1 then passes for the wrong reason.
    ("detector_goes_blind", "smoke_poster_frame_legible.py",
     'r"if \\(!\\s*[A-Za-z_.]+\\s*\\)\\s*\\{\\s*return \\((.{0,400}?)\\);\\s*\\}"',
     'r"if \\(!!!\\s*[A-Za-z_.]+\\s*\\)\\s*\\{\\s*return \\((.{0,400}?)\\);\\s*\\}"',
     "L1b detector_finds_a_known_positive",
     lambda s: 'if \\(!\\s*[A-Za-z_.]+' in s),
    # A KNOWN DEFECT LOSES ITS OWNER and becomes furniture -- the exact way a
    # red stops being read. EmojiCard is allowed to sit in the record BECAUSE
    # it is owned, dated and has a clearing condition; strip one and it is just
    # a broken component nobody is carrying.
    ("defect_loses_its_owner", "measured/REGISTERED_BODIES.json",
     '"owner": "registration path (Builder 1) \u2014 this lane cannot re-register",',
     '"_owner_removed": "",',
     "L5 registration_defects_are_quarantined",
     lambda s: '"state": "DEFECT"' in s),
    # COVERAGE SHRINKS SILENTLY: a name leaves the unprobed list without
    # anything moving into `components`, so the record quietly claims more
    # verification than was done. That is the denominator rule applied to a
    # to-do list.
    ("coverage_shrinks_silently", "measured/REGISTERED_BODIES.json",
     '\n  "CaptionMatch",', '',
     "L6 registration_coverage_is_disclosed",
     lambda s: '"CaptionMatch"' in s),
    # THE DECLARATION IS WITHDRAWN, so the real overlap becomes undeclared and
    # the leg must name it.
    #
    # THE OBVIOUS MUTATION HERE IS VACUOUS AND I WROTE IT FIRST: widening
    # KNOWN_TWO_HOME to accept everything leaves the leg passing, because
    # nothing is undeclared TODAY and a wider allow-list has nothing extra to
    # admit. It changed the file and not the verdict. Narrowing bites, because
    # StickyNotes is really in both sets — the mutation has to make the
    # population violate the rule, not make the rule looser than the population.
    ("two_home_declaration_withdrawn", "smoke_poster_frame_legible.py",
     '    KNOWN_TWO_HOME = {"StickyNotes"}',
     '    KNOWN_TWO_HOME = set()',
     "L7b two_registration_homes_are_declared",
     lambda s: 'StickyNotes' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True, env=_child_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    p = subprocess.run(["git", "status", "--porcelain", "port/bodies",
                        "measured/REGISTERED_DEFAULTS.json",
                        "smoke_poster_frame_legible.py"],
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
    exercised = 0
    unexercised = []
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-32s HARNESS FAILURE  anchor %dx in %s" % (name, n, target))
            continue
        if pre is not None and not pre(src):
            print("  %-32s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            if target.endswith(".json"):
                json.loads(mutant)
            elif target.endswith(".py"):
                compile(mutant, path, "exec")
        except (SyntaxError, ValueError) as e:
            print("  %-32s HARNESS FAILURE  mutant will not parse (%s)" % (name, e))
            continue
        open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        # UNEXERCISED IS A THIRD STATE, not a quiet NOT RED.
        #
        # The smoke stops after L0 when every body has just been edited and is
        # awaiting a picture — the sha binding working. A mutation aimed at a leg
        # that never ran cannot bite, and calling that NOT RED says the check is
        # broken when the truth is it was never asked. Folding UNDECIDABLE into
        # either neighbour is this repo's costume 5, and it would be doing it
        # inside the proof whose job is to catch exactly that.
        #
        # So: exit reflects only mutations that were EXERCISED, and the
        # unexercised count is printed loudly rather than absorbed — an empty
        # population must never be able to buy a green.
        ran = re.search(r"^\s+%s\s+(ok|FAIL)" % re.escape(phrase), mout, re.M) is not None
        if not ran:
            unexercised.append(name)
            # No restore here: the `finally` above already put the file back.
            print("  %-32s UNEXERCISED  (%s never ran — population empty)" % (name, phrase))
            continue
        ok = mrc != 0 and fired
        print("  %-32s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        exercised += 1
        if ok:
            red += 1
        r = residue()
        if r != base:
            print("     RESIDUE after %s: %r" % (name, r))
            return 2

    print("\n%d/%d RED-proven of the %d EXERCISED (%d of %d mutations could not "
          "run)" % (red, exercised, exercised, len(unexercised), len(MUTATIONS)))
    if unexercised:
        print("  UNEXERCISED — the smoke stopped before these legs, so they are "
              "UNPROVEN, not passing:")
        for n in unexercised:
            print("     %s" % n)
        print("  This clears when the edited bodies are re-photographed and the "
              "menu repopulates.")
    # A floor on the EXERCISED set: zero exercised mutations must never be green.
    ok = bool(MUTATIONS) and exercised > 0 and red == exercised
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
