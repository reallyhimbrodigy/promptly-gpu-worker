#!/usr/bin/env python3
"""RED proof: the standard must stay in the prefix, and absence must stay spoken."""
import os, shutil, subprocess, sys
APP="agentic_editor_app.py"; BAK="/tmp/_rtk.py"
shutil.copy(APP,BAK); env=dict(os.environ,PYTHONPATH=".")
def run():
    r=subprocess.run([sys.executable,"smoke_ruling_time_knowledge.py"],
                     capture_output=True,text=True,env=env)
    return r.returncode, r.stdout+r.stderr
def _prose_spans(src):
    """(start, end) char ranges of every string literal and comment.

    THE THIRD WAY A MUTATION STOPS MUTATING, found 2026-09-09. Leg 7 anchored on
    `.strip() != "1"`. My rewrite of prefix_material_enabled removed that
    predicate — and REPLACED IT WITH A DOCSTRING SENTENCE QUOTING IT, to record
    the defect. The anchor still matched EXACTLY ONCE, the count guard passed,
    the mutation applied to PROSE, and the smoke went green: NOT RED, with
    nothing wrong in the code. Documenting a defect silently re-targeted the
    mutation that hunts it.

        anchor 0x                -> a refactor moved it     (count guard)
        anchor lands in prose    -> a comment now owns it    (THIS)
        operand is empty         -> the edit is a no-op      (precondition)

    MY FIRST VERSION OF THIS GUARD WAS WRONG AND REFUSED 7 OF 8 LEGS. It blanked
    the CONTENTS of every string, so any anchor legitimately containing a
    literal — `if _v in _FLAG_FALSE:\n        return True` is fine, but
    `str(_raw).strip() == ""` is not — stopped matching the blanked text and was
    reported as prose. Almost every anchor contains a literal. The question is
    not whether the anchor has quotes in it; it is WHERE THE MATCH LANDS.
    """
    import io, tokenize
    _starts, _acc = [], 0
    for _l in src.split("\n"):
        _starts.append(_acc)
        _acc += len(_l) + 1
    spans = []
    try:
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if t.type in (tokenize.STRING, tokenize.COMMENT):
                spans.append((_starts[t.start[0] - 1] + t.start[1],
                              _starts[t.end[0] - 1] + t.end[1]))
    except (tokenize.TokenError, IndentationError):
        return []             # cannot tokenise: never refuse on a guess
    return spans


def _match_is_prose(src, old):
    """True when the ONLY occurrence of `old` sits wholly inside one string or
    comment — i.e. the mutation would edit prose and prove nothing."""
    i = src.find(old)
    if i < 0:
        return False
    j = i + len(old)
    return any(a <= i and j <= b for a, b in _prose_spans(src))


def mut(old,new,label,expect):
    src=open(APP,encoding="utf-8").read()
    if src.count(old)!=1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
    if _match_is_prose(src, old):
        print(f"  HARNESS FAILURE [{label}] anchor matches ONLY inside a string "
              f"or comment — the mutation would edit prose and prove nothing")
        return False
    open(APP,"w",encoding="utf-8").write(src.replace(old,new,1))
    rc,out=run(); shutil.copy(BAK,APP)
    ok=rc!=0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok: print(f"      expected {expect!r}")
    return ok
rc,out=run(); print(f"BASELINE exit={rc}"); assert rc==0,out
r=[]

# 1. The standard stops reaching the prefix — read_knowledge again.
r.append(mut('                + "\\n\\n" + ruling_time_knowledge())',
             '                )',
             "the standard stops being injected into the system block",
             "ruling_time_knowledge is CALLED into the system block"))

# 2. A CATALOGUE is added — 9,168 tokens of lookup material on every run.
r.append(mut('_RULING_TIME_DOCS = ("02_intent_standard.md",',
             '_RULING_TIME_DOCS = ("05_motion_graphics.md", "02_intent_standard.md",',
             "a catalogue is pulled into the prefix",
             "05_motion_graphics.md stays on disk"))

# 3. A MISSING document shrinks the block silently instead of saying so.
r.append(mut('        _head += ("\\n  (MISSING and not read: %s — the standard below is "',
             '        _head += ("" if True else "\\n  (MISSING and not read: %s — the standard below is "',
             "a missing document is no longer named",
             "a missing document is NAMED, not silently dropped"))

# 4. Total failure returns an empty block rather than saying UNAVAILABLE.
r.append(mut('        return ("EDITORIAL STANDARD: UNAVAILABLE — none of %s could be read. You "',
             '        return ("" if True else "EDITORIAL STANDARD: UNAVAILABLE — none of %s could be read. You "',
             "a total failure returns silence",
             "a total failure says UNAVAILABLE, never an empty string"))

# 5. The intent standard is dropped — the one document that IS the standard.
r.append(mut('_RULING_TIME_DOCS = ("02_intent_standard.md",\n',
             '_RULING_TIME_DOCS = (\n',
             "the intent standard is dropped from the set",
             "02_intent_standard.md is included"))

# 6. THE SWITCH DEFAULTS TO OFF — an unset flag ships a darker prefix, which is
#    the nine-dark-features class this repo has paid for repeatedly.
# RE-ANCHORED 2026-09-09. The old anchor was the one-line silent-fold predicate
#    `... .strip() != "1"`. Rewriting prefix_material_enabled to RAISE on an
#    unreadable value orphaned this mutation the same hour, and the guard
#    reported `anchor 0x` instead of counting it RED — which is the whole reason
#    the guard exists. A CORRECT FIX BLINDED THE MUTATION WRITTEN TO PROTECT IT,
#    for the second time in two days (Builder-1's `_rejected.append(_why6)` was
#    the first). Now anchored on the DEFAULT BRANCH — control flow, not one
#    spelling of one predicate — which survives a rewrite of the reader around
#    it.
r.append(mut('''    if _raw is None or str(_raw).strip() == "":
        return True''',
             '''    if _raw is None or str(_raw).strip() == "":
        return False''',
             "the switch defaults to OFF instead of ON",
             "unset means ON"))
# 7. A truthy-looking value removes it, so '0' or 'false' silently strips the
#    prefix — the classic flag-parsing defect. RE-ANCHORED on the FALSE branch
#    rather than on the predicate's spelling, for the reason in _code_only.
r.append(mut("""    if _v in _FLAG_FALSE:
        return True""", """    if _v in _FLAG_FALSE:
        return False""",
             "any non-empty value removes the material",
             "only the literal '1' disables it"))
# 8. A removal stops declaring itself and reads as a missing document.
r.append(mut('        return ("EDITORIAL STANDARD: REMOVED for this run "',
             '        return ("EDITORIAL STANDARD: UNAVAILABLE — none of it could be read. "\n                "" if False else "x" if False else "EDITORIAL STANDARD: REMOVED_ for this run "',
             "a deliberate removal reads as a missing document",
             "a removal SAYS it is deliberate"))
rc,out=run(); print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
sys.exit(0 if all(r) and rc==0 else 1)
