#!/usr/bin/env python3
"""RED proof for smoke_brief_composer.py — the brief is three parts, exactly."""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_brief_composer.py")
SRC = os.path.join(HERE, "brief_composer.py")


def _env():
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


MUTATIONS = [
    # A DEFAULT CREEPS BACK. One plausible sentence at a time is exactly how
    # the density rate survived a careful removal once already.
    ("a_default_creeps_back",
     '    lines = ["The user asked for: %s" % slot, "", OPEN_LINE]',
     '    lines = ["The user asked for: %s" % slot, "", "Cut dead air and filler '
     'words.", OPEN_LINE]',
     # AIMED AT L3, NOT L1. The inserted line joins with "\n" and lands in the
     # SAME paragraph as the open line, so the paragraph count stays 3 and L1
     # is content. L3 names the defaults individually and is what sees it —
     # which is the argument for naming them rather than counting them.
     "L3 nothing_but_the_three_parts",
     lambda s: 'lines = ["The user asked for: %s" % slot, "", OPEN_LINE]' in s),
    # THE ASK LINE RETURNS — an instruction about behaviour in a brief that is
    # now only facts the agent lacks.
    ("the_ask_line_returns",
     '        lines.append(tl)',
     '        lines.append(tl)\n        lines.append("")\n'
     '        lines.append("If anything is unclear, ask — your question reaches them.")',
     "L1 exactly_three_parts",
     lambda s: "your question reaches them" not in s),
    # THE OPEN LINE STARTS RESTRICTING. "only" turns an offer into a limit and
    # reads as precision.
    ("the_open_line_restricts",
     'OPEN_LINE = ("Our project\'s graphics, caption styles and sounds are here for "\n'
     '             "you alongside your own.")',
     'OPEN_LINE = ("Use only our project\'s graphics, caption styles and sounds.")',
     "L9 brief_is_neutral_about_what_may_be_used",
     lambda s: "alongside your own" in s),
    # A FAMILY DROPS OUT OF THE OFFER. RESTRICTS and PREFERS both stay zero,
    # so only a per-family leg sees it — and the family that goes is the one
    # nobody watches.
    ("a_family_drops_out_of_the_offer",
     '''OPEN_LINE = ("Our project's graphics, caption styles and sounds are here for "''',
     '''OPEN_LINE = ("Our project's graphics and sounds are here for "''',
     "L10 every_family_is_named_in_the_open_line",
     lambda s: "caption styles and sounds are here" in s),
    # THE PLACEHOLDER RETURNS for an empty brief.
    ("placeholder_returns_for_an_empty_brief",
     '    return "an edit of this video"',
     '    return "(none given)"',
     "L12 user_slot_is_never_empty_or_a_placeholder",
     lambda s: 'return "an edit of this video"' in s),
    # THE TIER DEFAULTS TO PAID — every unconfigured caller then asserts
    # something about an account it knows nothing about.
    ("tier_defaults_to_paid",
     "def compose(user_words, tier=None):",
     'def compose(user_words, tier="paid"):',
     "L14 tier_line_only_for_a_ruled_tier",
     lambda s: "def compose(user_words, tier=None):" in s),
    # THE ACCOUNT CLAIM RETURNS — the exact words my own draft shipped.
    ("tier_line_claims_a_plan_limit",
     '    "paid": "Only generate new images, video, voiceover or music if asked.",',
     '    "paid": "This is a paid account with unlimited exports. Only generate '
     'new images, video, voiceover or music if asked.",',
     "L15 no_tier_line_claims_anything_about_an_account",
     lambda s: '"paid": "Only generate new images' in s),
    # THE CLAIMS ARE STRIPPED AND THE INSTRUCTION GOES WITH THEM.
    ("tier_line_stops_instructing",
     '    "free": "Don\'t generate new images, video, voiceover or music.",',
     '    "free": "Keep it simple.",',
     "L16 every_tier_line_still_instructs",
     lambda s: '"free": "Don\'t generate new images' in s),
]


def run():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def failed(out, phrase):
    return any(phrase in ln and "FAIL" in ln for ln in out.splitlines())


def main():
    rc, out = run()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-800:])
        return 2
    print("baseline green.\n")
    raw = io.open(SRC, encoding="utf-8").read()
    red, vacuous = 0, []
    for name, old, new, phrase, pre in MUTATIONS:
        if raw.count(old) != 1:
            print("  %-40s HARNESS FAILURE: anchor %dx" % (name, raw.count(old)))
            continue
        if not pre(raw):
            vacuous.append(name)
            print("  %-40s VACUOUS   precondition false" % name)
            continue
        io.open(SRC, "w", encoding="utf-8").write(raw.replace(old, new, 1))
        rc2, out2 = run()
        io.open(SRC, "w", encoding="utf-8").write(raw)
        ok = rc2 != 0 and failed(out2, phrase)
        red += 1 if ok else 0
        print("  %-40s %s   rc=%d leg_failed=%s"
              % (name, "RED " if ok else "NOT RED", rc2, failed(out2, phrase)))
    if io.open(SRC, encoding="utf-8").read() != raw:
        print("\nHARNESS FAILURE: residue in brief_composer.py")
        return 2
    print("\n%d/%d RED-proven%s" % (red, len(MUTATIONS),
          ("; VACUOUS: " + ", ".join(vacuous)) if vacuous else ""))
    return 0 if (MUTATIONS and red == len(MUTATIONS) and not vacuous) else 1


if __name__ == "__main__":
    sys.exit(main())
