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
    # THE SOUND POOL RESTRICTION, RESTORED — exactly the sentence that shipped
    # until Zac ruled it out. It is the mutation most likely to reappear by
    # accident, because "from the project's registered sounds" reads as
    # precision rather than as a narrowing of the menu.
    ("sound_pool_restriction_returns", "brief_composer.py",
     '     "Place sound effects where the moment wants one — the project\'s sounds or "\n'
     '     "your own library."),',
     '     "Place sound effects from the project\'s registered sounds."),',
     "L9 sounds_not_restricted_to_the_project_pool",
     lambda s: "the project's sounds or " in s),
    # THE SECOND SPELLING, RESTORED. Two different sentences said the same
    # thing, so a proof that only restores one leaves the other untested — and
    # a needle aimed at either phrasing would have missed the other.
    ("only_clause_reabsorbs_sounds", "brief_composer.py",
     '     "Use only the components and caption styles already registered in this "',
     '     "Use only the components, sounds and caption styles registered in this "',
     "L9 sounds_not_restricted_to_the_project_pool",
     lambda s: "components and caption styles already registered" in s),
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
    ("default_vanishes", "brief_composer.py",
     '    ("zooms",       "zooms",\n     "Zoom on moments of emphasis."),\n', "",
     "L1 every_default_reaches_the_instruction",
     lambda s: '"Zoom on moments of emphasis."' in s),
    # IT STARTS TELLING THEIR AGENT NOT TO ASK.
    ("forbids_questions", "brief_composer.py",
     'lines.append("If something in the brief is unclear or you need a decision "\n'
     '                 "only the user can make, ask — the question is relayed to them.")',
     'lines.append("Do not ask questions; make the call yourself.")',
     "L6 never_forbids_questions",
     lambda s: 'the question is relayed to them' in s),
    # PRECEDENCE STOPS BEING STATED, so the defaults and the user's words sit
    # side by side with nothing saying which wins — the robust half removed,
    # leaving only the matcher I do not trust on its own.
    ("precedence_dropped", "brief_composer.py",
     '    lines.append("THE USER\'S BRIEF, which wins wherever it disagrees with anything "\n                 "above:")',
     '    lines.append("THE USER\'S BRIEF:")',
     "L7 brief_verbatim_and_precedence_stated",
     lambda s: 'wins wherever it disagrees' in s),
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
