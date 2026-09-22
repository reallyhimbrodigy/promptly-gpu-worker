#!/usr/bin/env python3
"""RED proof for smoke_live_set.py — a check that has never failed is not a check.

Every mutation carries the PHRASE its target leg prints. A non-zero exit is not
enough: the seventh way a mutation misleads is a RED that is not about the
property (a crash, a parse error), and both look exactly like a pass of the
proof. `rc=1 phrase=False` is that signature and it is reported NOT RED.

Backups are IN MEMORY (a backup must not survive the run that made it) and the
tree is checked for residue after every mutation.
"""
import json
import os
import re
import subprocess
import sys
import tokenize
import io

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
SMOKE = os.path.join(HERE, "smoke_live_set.py")


def _prose_spans(src):
    spans = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.STRING, tokenize.COMMENT):
                spans.append((tok.start, tok.end))
    except Exception:                                          # noqa: BLE001
        pass
    lines = src.splitlines(True)
    offs, run = [], 0
    for ln in lines:
        offs.append(run); run += len(ln)
    out = []
    for (sr, sc), (er, ec) in spans:
        try:
            out.append((offs[sr - 1] + sc, offs[er - 1] + ec))
        except IndexError:
            pass
    return out


# (name, TARGET-FILE, old, new, leg-phrase, precondition over unmutated source)
#
# The target file is per-mutation because the defects live in two places: the
# RULE lives in lane_contract.py, and the RULING — which components are in scope
# — lives in library_73.json. A proof that could only mutate the rule would be
# blind to the ruling silently losing a component, which is exactly what
# happened to Reticle.
MUTATIONS = [
    ("floor_empty_map", "lane_contract.py",
     "if not isinstance(comps, dict) or not comps:",
     "if not isinstance(comps, dict):",
     "L6 empty_is_FAILED",
     lambda s: "or not comps" in s),
    ("two_home_rule", "lane_contract.py",
     "if fams and len(blocking) == len(fams):",
     "if fams and len(blocking) > 0:",
     "L5b two_home_kept",
     lambda s: "len(blocking) == len(fams)" in s),
    ("absent_becomes_failed", "lane_contract.py",
     '        return {"state": ABSENT, "why": "%s carries no _library',
     '        return {"state": FAILED, "why": "%s carries no _library',
     "L7 no_ruling_is_ABSENT",
     lambda s: '"state": ABSENT' in s),
    ("renderable_loses_a_family", "lane_contract.py",
     '    "caption style": "a style is a property of a caption item, not a registered component",',
     '',
     "L3 renderable_is_27",
     # THE PHRASE WAS STALE ONCE, ON PURPOSE KEPT AS THE RECORD: this mutation
     # named "L3 renderable_is_26" after the leg was renamed to _is_27, and the
     # proof reported NOT RED with rc=1 — a red that was not about the property.
     # A bare exit code would have counted it. That is the whole argument for
     # asserting the leg's own words.
     lambda s: '"caption style"' in s),
    # L9: the menu stops asking for a picture. Every renderable component is
    # offered, 18 of them never photographed — the menu advertising what the
    # kitchen may refuse.
    ("menu_ignores_the_picture", "lane_contract.py",
     'menu = sorted(n for n in renderable if draws.get(n) == "DRAWS")',
     'menu = sorted(n for n in renderable if draws.get(n) != "__never__")',
     "L9 menu_is_frame_proven_only",
     lambda s: 'draws.get(n) == "DRAWS"' in s),
    # L10: a sha is promoted into a verdict. This is the defect Zac named —
    # "a file with a hash is a file, not evidence" — written as code.
    # THE FILE_ONLY MUTATION IS RETIRED WITH ITS LEG. Its target population
    # went empty when today's looking gave every in-scope FILE_ONLY row a real
    # verdict, so the mutation changed bytes and could not change a result —
    # vacuous, and correct to pass. Removed rather than left counting.
    # THE BODIES GO UNREADABLE — the container case Builder 1 actually hit.
    # Every sha reads None, every recorded still mismatches, and before the fix
    # `menu` came back [] with state MEASURED beside 27 renderable. The leg must
    # see a STATE, not a clean zero.
    # RE-AIMED. This first mutated the bodies PATH and named L17, and came back
    # rc=1 phrase=False: L17 asserts that a STATE is reported, and the fix
    # reports ABSENT correctly even with the path broken — so the mutation
    # proved the fix worked rather than proving the leg guards it. The property
    # that needs guarding is the None, and L19 drives it in process.
    ("absent_returns_an_empty_menu_again", "lane_contract.py",
     '        draws, menu, awaiting = None, None, None',
     '        draws, menu, awaiting = draws, [], []',
     "L19 unreadable_bodies_return_None_not_empty",
     lambda s: 'draws, menu, awaiting = None, None, None' in s),
    # THE PHOTOGRAPHER GETS GATED ON THE MENU AGAIN — the deadlock restored.
    ("to_photograph_becomes_the_menu", "lane_contract.py",
     '    to_photograph = sorted(renderable)',
     '    to_photograph = sorted(n for n in renderable if draws.get(n) == "DRAWS")',
     "L18 stale_body_is_photographable",
     lambda s: 'to_photograph = sorted(renderable)' in s),
    # L13: BYTES_ONLY collapses into DRAWS — a file that got bigger promoted
    # into a picture somebody looked at. This is the exact inference Builder 1
    # caught himself making, written as code.
    ("bytes_only_becomes_draws", "lane_contract.py",
     '            draws[name] = "BYTES_ONLY"',
     '            draws[name] = "DRAWS"',
     "L13 bytes_only_named_not_on_menu",
     lambda s: '"BYTES_ONLY"' in s),
    # L14/L15: a body is EDITED after its still was taken. This is the real
    # regression — the picture still looks perfect, and nothing but the sha
    # notices. Mutating the BODY (not the record) is the honest shape: it is
    # what actually happens when someone improves a component.
    # RE-AIMED 2026-09-21, second time, and by the same cause both times: my own
    # edit rewrote the line it targeted. Generalising the sha check from DRAWS
    # to EVERY looked-at state moved the binding into its own branch, and the
    # anchor guard said `anchor 0x` instead of passing. A mutation is aimed at a
    # line; a line is the most movable thing in a file.
    ("sha_binding_removed", "lane_contract.py",
     '        elif (row.get("body_sha256_16")\n'
     '              and row["body_sha256_16"] != _body_sha(name)):',
     '        elif False:',
     "L15 drifted_body_refuses_DRAWS",
     lambda s: 'row["body_sha256_16"] != _body_sha(name)' in s),
    # L12: the RULING regresses — Reticle is dropped from scope again on the
    # retracted blank. The rule is untouched and perfectly correct; the library
    # simply loses a component, and only a mutation of the ruling can show it.
    ("reticle_dropped_from_scope", "library_73.json",
     '    "Reticle": {',
     '    "ReticleXX_REMOVED": {',
     "L12 reticle_stays_in_scope",
     lambda s: '"Reticle": {' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True, env=_child_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    """Porcelain over the mutated sources, PLUS the smoke's own temp fixtures.

    smoke_live_set writes three untracked fixtures INTO THE TREE --
    _smoke_live_set_twohome.json, _empty.json, _noscope.json -- and removes them
    in `finally`. A SIGKILL between the write and the remove leaves them on
    disk, where `git add -A` commits them; in-memory restore does not survive a
    kill and no relocation reaches it, so only a tree check does. They were
    outside this watch list, which is the same defect that let a mutant's
    fifteen-sound record reach a commit from the sfx proof.

    TWO LIMITS, both measured rather than assumed, because the first version of
    this note claimed the watch was sufficient and it is not:

    1. Porcelain cannot tell one dirty content from another. A file ALREADY
       dirty at baseline can be rewritten entirely and the status string is
       byte-identical, so the guard sees nothing. That is exactly how a mutant's
       fifteen-sound record reached a commit from the sfx proof, and it is why
       red_proof_sfx_loudness_states compares BYTES instead. It is sufficient
       here only because these paths are committed and clean at baseline.
    2. A smoke that leaks on EVERY run, baseline included, makes its own leak
       the accepted baseline -- `base` is captured after the baseline run, so a
       consistent leak is invisible to any residue check built this way.
       VERIFIED: with the smoke's `finally: os.remove` removed, this proof
       exits 0. Catching that is a TREE check's job at commit time, not a
       residue check's inside a proof, and saying so beats widening this one
       until it claims something it cannot do.

    What it DOES catch, verified: a stray fixture already on disk when the
    proof starts -- exit 2.
    """
    p = subprocess.run(["git", "status", "--porcelain", "--",
                        "lane_contract.py", "library_73.json", "port/bodies",
                        "_smoke_live_set_twohome.json",
                        "_smoke_live_set_empty.json",
                        "_smoke_live_set_noscope.json"],
                       cwd=HERE, capture_output=True, text=True)
    return p.stdout.strip()


def main():
    base_residue = residue()

    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1500:])
        return 2
    print("baseline green.\n")

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        TARGET = os.path.join(HERE, target)
        src = open(TARGET, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-28s HARNESS FAILURE  anchor %dx" % (name, n)); continue
        if pre is not None and not pre(src):
            print("  %-28s HARNESS FAILURE  VACUOUS precondition" % name); continue
        at = src.index(old)
        if any(a <= at and at + len(old) <= b for a, b in _prose_spans(src)):
            print("  %-28s HARNESS FAILURE  match lands in prose" % name); continue
        mutant = src.replace(old, new, 1)
        # A MUTANT THAT WILL NOT PARSE NEVER RAN AT ALL, and its red is about the
        # parser rather than the property. Both file kinds get checked, each by
        # its own parser — a JSON ruling can be broken exactly as easily.
        # PARSE THE MUTANT WITH THE RIGHT PARSER, OR NOT AT ALL. Compiling a
        # .jsx body as Python reports "will not parse" for every mutation of it,
        # which is a HARNESS failure dressed as a refusal — and it fired here on
        # the first run. There is no JS parser in this harness, and none is
        # needed: the smoke only HASHES a body, it never executes one. So the
        # guard applies where it can mean something and says where it cannot.
        try:
            if target.endswith(".json"):
                json.loads(mutant)
            elif target.endswith(".py"):
                compile(mutant, TARGET, "exec")
            elif not mutant.strip():
                raise ValueError("mutant is empty")
        except (SyntaxError, ValueError) as e:
            print("  %-28s HARNESS FAILURE  mutant will not parse (%s)" % (name, e)); continue
        open(TARGET, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(TARGET, "w", encoding="utf-8").write(src)
        # the leg line is "  <name padded> FAIL   <detail>"
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-28s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue()
        if r != base_residue:
            print("     RESIDUE after %s: %r" % (name, r)); return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
