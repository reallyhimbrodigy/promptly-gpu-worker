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
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
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
        ok = mrc != 0 and fired
        print("  %-32s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
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
