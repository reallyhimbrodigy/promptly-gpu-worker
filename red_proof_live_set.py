#!/usr/bin/env python3
"""RED proof for smoke_live_set.py — a check that has never failed is not a check.

Every mutation carries the PHRASE its target leg prints. A non-zero exit is not
enough: the seventh way a mutation misleads is a RED that is not about the
property (a crash, a parse error), and both look exactly like a pass of the
proof. `rc=1 phrase=False` is that signature and it is reported NOT RED.

Backups are IN MEMORY (a backup must not survive the run that made it) and the
tree is checked for residue after every mutation.
"""
import os
import re
import subprocess
import sys
import tokenize
import io

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "lane_contract.py")
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


# (name, old, new, leg-phrase, precondition-over-unmutated-source or None)
MUTATIONS = [
    ("floor_empty_map",
     "if not isinstance(comps, dict) or not comps:",
     "if not isinstance(comps, dict):",
     "L6 empty_is_FAILED",
     lambda s: "or not comps" in s),
    ("two_home_rule",
     "if fams and len(blocking) == len(fams):",
     "if fams and len(blocking) > 0:",
     "L5b two_home_kept",
     lambda s: "len(blocking) == len(fams)" in s),
    ("absent_becomes_failed",
     '        return {"state": ABSENT, "why": "%s carries no _library',
     '        return {"state": FAILED, "why": "%s carries no _library',
     "L7 no_ruling_is_ABSENT",
     lambda s: '"state": ABSENT' in s),
    ("renderable_loses_a_family",
     '    "caption style": "a style is a property of a caption item, not a registered component",',
     '',
     "L3 renderable_is_26",
     lambda s: '"caption style"' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    p = subprocess.run(["git", "status", "--porcelain", "lane_contract.py"],
                       cwd=HERE, capture_output=True, text=True)
    return p.stdout.strip()


def main():
    base_residue = residue()
    src = open(TARGET, encoding="utf-8").read()

    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1500:])
        return 2
    print("baseline green.\n")

    red = 0
    for name, old, new, phrase, pre in MUTATIONS:
        n = src.count(old)
        if n != 1:
            print("  %-28s HARNESS FAILURE  anchor %dx" % (name, n)); continue
        if pre is not None and not pre(src):
            print("  %-28s HARNESS FAILURE  VACUOUS precondition" % name); continue
        at = src.index(old)
        if any(a <= at and at + len(old) <= b for a, b in _prose_spans(src)):
            print("  %-28s HARNESS FAILURE  match lands in prose" % name); continue
        try:
            compile(src.replace(old, new, 1), TARGET, "exec")
        except SyntaxError as e:
            print("  %-28s HARNESS FAILURE  mutant will not parse (%s)" % (name, e)); continue
        open(TARGET, "w", encoding="utf-8").write(src.replace(old, new, 1))
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
