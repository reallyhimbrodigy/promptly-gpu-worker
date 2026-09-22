#!/usr/bin/env python3
"""RED proof for smoke_dispatch_classifier.py.

`order_inverted` is the defect L1 caught for real on its first run, promoted to
a mutation: test GENERATIVE before UNSAFE and an unsafe ask that is also
generative comes back PRICED. Pricing it is offering to do it.
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
SMOKE = os.path.join(HERE, "smoke_dispatch_classifier.py")
WATCHED = ["dispatch_classifier.py", "smoke_dispatch_classifier.py"]

MUTATIONS = [
    # THE ORDER INVERTS. An unsafe-and-generative ask reaches the quote.
    ("generative_tested_before_unsafe", "dispatch_classifier.py",
     "    u = _hit(_UNSAFE, t)", "    u = None if _hit(_GENERATIVE, t) else _hit(_UNSAFE, t)",
     "L1 unsafe_beats_generative_and_is_never_quoted",
     lambda s: "u = _hit(_UNSAFE, t)" in s),
    # UNSAFE STARTS DISPATCHING. The refusal becomes a label on a job that runs.
    ("unsafe_dispatches_anyway", "dispatch_classifier.py",
     '        return {"state": "UNSAFE", "reason": u[1], "may_dispatch": False,',
     '        return {"state": "UNSAFE", "reason": u[1], "may_dispatch": True,',
     "L2 unsafe_refuses_free_of_charge_and_is_counted",
     lambda s: '"state": "UNSAFE"' in s),
    # UNSAFE CARRIES A CHARGE. "no render, no charge" is the standing rule and
    # a non-zero quote here is the charge arriving by another name.
    ("unsafe_carries_a_quote", "dispatch_classifier.py",
     '                "credits_quoted": 0, "counter": "dispatch_refused_unsafe",',
     '                "credits_quoted": 20, "counter": "dispatch_refused_unsafe",',
     "L2 unsafe_refuses_free_of_charge_and_is_counted",
     lambda s: '"dispatch_refused_unsafe"' in s),
    # GENERATIVE IS ATTEMPTED INSTEAD OF QUOTED — "negotiated not attempted",
    # reversed.
    ("generative_dispatches", "dispatch_classifier.py",
     '        return {"state": "GENERATIVE", "reason": g[1], "may_dispatch": False,',
     '        return {"state": "GENERATIVE", "reason": g[1], "may_dispatch": True,',
     "L3 generative_quotes_20_and_never_dispatches",
     lambda s: '"state": "GENERATIVE"' in s),
    # THE WALL STOPS BEING TIER-SPLIT, so a Pro subscriber is shown a paywall
    # for a feature they already have.
    ("paywall_shown_to_everyone", "dispatch_classifier.py",
     '        paywalled = tier not in ("pro", "max")', "        paywalled = True",
     "L3b free_sees_the_wall_and_pro_does_not",
     lambda s: 'tier not in ("pro", "max")' in s),
    # THE NEGOTIATION BECOMES A BARE REFUSAL — no alternative named.
    ("out_of_scope_stops_negotiating", "dispatch_classifier.py",
     '                "message": o[3], "classifier_version": CLASSIFIER_VERSION}',
     '                "message": "No.", "classifier_version": CLASSIFIER_VERSION}',
     "L4 out_of_scope_negotiates_with_an_alternative",
     lambda s: '"message": o[3]' in s),
    # A RULE LOSES ITS LAW, so the category is me deciding what may be asked.
    ("out_of_scope_rule_loses_its_law", "dispatch_classifier.py",
     '"music", "no music",', '"music", "",',
     "L6 every_out_of_scope_rule_cites_a_law",
     lambda s: '"no music"' in s),
    # THE CLASSIFIER CONVICTS ORDINARY WORK — the direction that costs a user
    # their edit, and the one every over-broad rule in this repo has taken.
    ("ordinary_work_convicted", "dispatch_classifier.py",
     r'    (r"\btext[- ]to[- ](?:video|speech)\b", "text-to-video or text-to-speech"),',
     r'    (r"\b(?:cut|caption|zoom|trim)\w*\b", "text-to-video or text-to-speech"),',
     "L7 ordinary_briefs_are_never_convicted",
     lambda s: 'text[- ]to[- ](?:video|speech)' in s),
    # A FABRICATION GETS A PRICE AGAIN. The worst class: not a miss, an OFFER.
    # Removing the generate/create arm sends "generate a video of the CEO
    # endorsing us" back into GENERATIVE and it comes out quoted at 20 credits.
    ("fabrication_reaches_a_quote_again", "dispatch_classifier.py",
     r'     r"|\b(?:generate|create|make)\b[^.]{0,40}\b(?:endors\w*|praising|recommend\w*)\b",',
     r'     r"|\bZZ_NEVER_MATCHES_ZZ\b",',
     "L8 fabrication_corpus_catch_rate",
     lambda s: 'praising|recommend' in s),
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
            print("  %-34s HARNESS FAILURE  anchor %dx" % (name, n))
            continue
        if pre is not None and not pre(src):
            print("  %-34s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            compile(mutant, path, "exec")
        except SyntaxError as e:
            print("  %-34s HARNESS FAILURE  will not parse (%s)" % (name, e))
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
        r = residue(base)
        if r:
            print("     RESIDUE after %s: %s" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
