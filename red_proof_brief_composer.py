#!/usr/bin/env python3
"""RED proof for smoke_brief_composer.py.

`only_becomes_a_ban` is the defect that already happened, restored: a matcher
treating `only` as a limit on the BRIEF. Measured on the corpus, four of the
five `only` sentences limit a CATEGORY inside the brief, so that mutation is a
terminal fault on a CORRECT run four times out of five.
"""
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
SMOKE = os.path.join(HERE, "smoke_brief_composer.py")
WATCHED = ["brief_composer.py", "smoke_brief_composer.py"]

MUTATIONS = [
    # THE TWO ZAC NAMED, BY NAME. Both were in my own first draft, which is
    # why they are mutations and not a style note: "This is a paid account —
    # you won't hit a plan limit" shipped in the version I sent B1.
    ("tier_line_claims_a_plan_limit", "brief_composer.py",
     '    "paid": ("Only generate new images, video, voiceover or music if the user "\n'
     '             "asked for it."),',
     '    "paid": ("This is a paid account — you won\'t hit a plan limit. Only "\n'
     '             "generate images, video, voiceover or music if the user asked."),',
     "L15 no_tier_line_claims_anything_about_an_account",
     lambda s: '"Only generate new images, video, voiceover or music if the user "' in s),
    ("tier_line_claims_unlimited_exports", "brief_composer.py",
     '    "free": "Don\'t generate new images, video, voiceover or music.",',
     '    "free": "You have unlimited exports. Don\'t generate new images, video, '
     'voiceover or music.",',
     "L15 no_tier_line_claims_anything_about_an_account",
     lambda s: '"free": "Don\'t generate new images, video, voiceover or music.",' in s),
    # AND THE OTHER DIRECTION: the claims are stripped and the INSTRUCTION goes
    # with them, leaving a line that asserts nothing and tells the agent
    # nothing — worse than the claim it replaced.
    ("tier_line_stops_instructing", "brief_composer.py",
     '    "free": "Don\'t generate new images, video, voiceover or music.",',
     '    "free": "Keep it simple.",',
     "L16 every_tier_line_still_instructs",
     lambda s: '"free": "Don\'t generate new images, video, voiceover or music.",' in s),
    # THE TIER DEFAULTS TO PAID — every unconfigured caller then asserts a
    # billing fact about an account it knows nothing about.
    ("tier_defaults_to_paid", "brief_composer.py",
     "def compose(vibe, user_brief, tier=None):",
     'def compose(vibe, user_brief, tier="paid"):',
     "L14 tier_line_only_for_a_ruled_tier",
     lambda s: "def compose(vibe, user_brief, tier=None):" in s),
    # THE LINE OVERCLAIMS. "Unlimited" is the specific word B1 named as the one
    # THE CREDIT GUARD IS DROPPED, leaving "this is a paid account" alone —
    # ZAC'S NAMED MUTANT: the placeholder comes back. It is the shape the
    # composer actually shipped with — a vibe-only submission wrote
    # "(none given)" into the brief slot — and it reads as a user who asked for
    # nothing, which is a request the agent is free to invent.
    ("placeholder_returns_for_a_vibe_only_brief", "brief_composer.py",
     '        return "a %s edit" % v',
     '        return "(none given)"',
     "L12 user_slot_is_never_empty_or_a_placeholder",
     lambda s: 'return "a %s edit" % v' in s),
    # AND THE EMPTY SLOT — the same defect with no word to grep for.
    ("user_slot_goes_empty", "brief_composer.py",
     '    return "an edit of this video"',
     '    return ""',
     "L12 user_slot_is_never_empty_or_a_placeholder",
     lambda s: 'return "an edit of this video"' in s),
    # THE MUTANT ZAC NAMED. It forbids nothing, passes any check looking for the
    # word "only", and reads as helpful guidance in review — and a run under it
    # never touches their library. A preference is the restriction that does not
    # announce itself, which is why PREFERS is its own class rather than folded
    # into NEUTRAL.
    # ZAC'S NAMED MUTANT, RE-AIMED AT THE SENTENCE THAT ACTUALLY RENDERS.
    # My first version edited DEFAULTS' graphics row, whose sentence is None and
    # which compose() ignores for that key — it always renders
    # placeable_sentence() instead. Real bytes changed and no verdict could:
    # the wrong-population vacuity, and it announced itself as rc=1 with
    # phrase=False, going red on a leg that was not the one under test.
    ("a_preference_creeps_in", "brief_composer.py",
     '    return "Add %s and %s where they fit." % (", ".join(live[:-1]), live[-1])',
     '    return "Add %s and %s where they fit — prefer the project\'s own." % (", ".join(live[:-1]), live[-1])',
     "L9 brief_is_neutral_about_what_may_be_used",
     lambda s: 'where they fit." % (", ".join(live[:-1])' in s),
    # AND A FAMILY GOES QUIET. Dropping captions from the neutrality sentence
    # leaves RESTRICTS and PREFERS both at zero, so only a per-family leg sees
    # it — the family that loses its neutrality is the one nobody watches go.
    ("a_family_drops_out_of_the_neutrality_sentence", "brief_composer.py",
     '     "The project\'s components, caption styles and sounds and your own are all "',
     '     "The project\'s components and sounds and your own are all "',
     "L10 every_family_is_named_in_the_opening_sentence",
     lambda s: "components, caption styles and sounds and your own" in s),
    # THE SOUND POOL RESTRICTION, RESTORED — exactly the sentence that shipped
    # until Zac ruled it out. It is the mutation most likely to reappear by
    # accident, because "from the project's registered sounds" reads as
    # precision rather than as a narrowing of the menu.
    ("sound_pool_restriction_returns", "brief_composer.py",
     '    ("sfx",         "sound effects", None),',
     '    ("sfx",         "sound effects", "Use the project\'s registered sounds only."),',
     "L9 brief_is_neutral_about_what_may_be_used",
     lambda s: '("sfx",         "sound effects", None),' in s),
    # THE SECOND SPELLING, RESTORED. Two different sentences said the same
    # thing, so a proof that only restores one leaves the other untested — and
    # a needle aimed at either phrasing would have missed the other.
    ("only_clause_reabsorbs_sounds", "brief_composer.py",
     '     "The project\'s components, caption styles and sounds and your own are all "',
     '     "Use only the project\'s components, caption styles and sounds. Nothing else "',
     "L9 brief_is_neutral_about_what_may_be_used",
     lambda s: "and your own are all " in s),
    # THE ONLY-IS-A-BAN DEFECT, restored. Adding `only` to the negation set is
    # the single most plausible "improvement" anyone would make here.
    ("only_becomes_a_ban", "brief_composer.py",
     'NEGATION = r"(?:no|not|don\'t|do not|never|without|skip|avoid|leave out|omit)"',
     'NEGATION = r"(?:no|not|don\'t|do not|never|without|skip|avoid|leave out|omit|only)"',
     "L5 category_scoped_only_bans_nothing",
     lambda s: '|omit)"' in s),
    # THE CONDITION GUARD GOES, so "use zooms only when they add emphasis" bans
    # zooms — the family the sentence PERMITS.
    ("conditional_guard_removed", "brief_composer.py",
     'CONDITIONAL = re.compile(r"\\bonly (?:when|if|where)\\b", re.I)',
     'CONDITIONAL = re.compile(r"\\bZZ_NEVER_MATCHES_ZZ\\b", re.I)',
     "L3 only_when_is_a_condition_not_a_ban",
     lambda s: 'only (?:when|if|where)' in s),
    # THE DENSITY GUARD GOES: "do not cut EVERY breath" becomes a family ban,
    # reversing a brief whose previous line asks for cuts.
    ("quantified_guard_removed", "brief_composer.py",
     r'QUANTIFIED = re.compile(r"\b(?:every|all|too many|so many|constant(?:ly)?)\b", re.I)',
     r'QUANTIFIED = re.compile(r"\bZZ_NEVER_MATCHES_ZZ\b", re.I)',
     "L4b quantified_guard_is_actually_reached",
     lambda s: 'too many|so many' in s),
    # THE BINDING WIDENS from 24 characters to a whole sentence, so a negation
    # anywhere near a family name suppresses it — co-occurrence read as intent.
    ("negation_binding_widens", "brief_composer.py",
     'near = re.search(NEGATION + r"[^.;!?]{0,24}?(?:" + words + r")", s, re.I)',
     'near = re.search(NEGATION + r"[^.;!?]{0,400}?(?:" + words + r")", s, re.I)',
     "L4c negation_does_not_reach_across_a_sentence",
     lambda s: '{0,24}?' in s),
    # A DEFAULT VANISHES from the list — the population floor is what notices.
    # RE-AIMED. zooms no longer prints a sentence of its own — it renders inside
    # the shared placeable bullet — so the mutation drops it from PLACEABLE.
    # Orphaned by my own refactor and caught by the anchor guard, which is
    # exactly the case that guard exists for.
    ("default_vanishes", "brief_composer.py",
     'PLACEABLE = [("graphics", "motion graphics"), ("zooms", "zooms"),',
     'PLACEABLE = [("graphics", "motion graphics"),',
     "L1 every_default_reaches_the_instruction",
     lambda s: '("zooms", "zooms")' in s),
    # IT STARTS TELLING THEIR AGENT NOT TO ASK.
    ("forbids_questions", "brief_composer.py",
     'lines.append("If anything is unclear or needs a decision only the user can "\n'
     '                 "make, ask — your question reaches them.")',
     'lines.append("Do not ask questions; make the call yourself.")',
     "L6 never_forbids_questions",
     lambda s: 'ask — your question reaches them.' in s),
    # PRECEDENCE STOPS BEING STATED, so the defaults and the user's words sit
    # side by side with nothing saying which wins — the robust half removed,
    # leaving only the matcher I do not trust on its own.
    ("precedence_dropped", "brief_composer.py",
     '    lines.append("Do exactly that. Where they didn\'t say, use these defaults:")',
     '    lines.append("Use these defaults:")',
     "L7 brief_verbatim_and_precedence_stated",
     lambda s: "Do exactly that. Where they didn't say" in s),
    # A SUPPRESSION GOES SILENT: the default is dropped and nothing records why.
    ("suppression_goes_silent", "brief_composer.py",
     '        "evidence": {k: e for k, (s, e) in states.items() if e},',
     '        "evidence": {},',
     "L8 suppression_carries_its_evidence",
     lambda s: 'for k, (s, e) in states.items() if e' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True, env=_child_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def snapshot(paths):
    return {q: open(os.path.join(HERE, q), "rb").read() for q in paths}


def residue(base):
    return sorted(q for q, b in base.items()
                  if open(os.path.join(HERE, q), "rb").read() != b)


def main():
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:])
        return 2
    print("baseline green.\n")
    base = snapshot(WATCHED)

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-28s HARNESS FAILURE  anchor %dx" % (name, n))
            continue
        if pre is not None and not pre(src):
            print("  %-28s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            compile(mutant, path, "exec")
        except SyntaxError as e:
            print("  %-28s HARNESS FAILURE  will not parse (%s)" % (name, e))
            continue
        open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-28s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue(base)
        if r:
            print("     RESIDUE after %s: %s" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
