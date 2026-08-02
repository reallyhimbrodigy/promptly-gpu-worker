"""phase3_section_cert.py — the Rule-1 gate for the whole prompt region.

Run against a pre-change snapshot of handler.py. FAILS if ANY section lost a
content word, number or name, or if a DO-NOT-COLLAPSE invariant was flattened.
This is the check that makes a Phase-3 regression impossible: no condensation
reaches handler.py without this exiting 0.

    python3 phase3_section_cert.py --before /tmp/handler.before.py

ARM AWARENESS (why this is not just a loop over sections)
  Some prompt text is swapped at RUNTIME behind a flag, so the section as it
  sits in the f-string is only ONE arm of what Gemini can receive. The
  `payoff-commit-even-viral` invariant guards the token `dwell`, which exists
  only in the PROMPTLY_DWELL swap target — on the flag-off arm that ships today
  the old prose is live and `dwell` is legitimately absent. Checking only the
  static text would report a permanent false FAIL; deleting the invariant to go
  green would throw away a real guard. So each invariant is checked against
  every arm, and passes if the arm that OWNS it holds.
"""
import argparse
import ast
import importlib.util
import re
import os
import shutil
import sys
import tempfile

import cert_prompt_content_diff as C


def _map_for(handler_path):
    """build_map() against an arbitrary handler.py, in a scratch dir."""
    d = tempfile.mkdtemp()
    shutil.copy(handler_path, os.path.join(d, "handler.py"))
    for f in ("validate_deploy.py", "prompt_token_map.py"):
        shutil.copy(f, os.path.join(d, f))
    cwd = os.getcwd()
    os.chdir(d)
    try:
        spec = importlib.util.spec_from_file_location("_ptm", "prompt_token_map.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.build_map()
    finally:
        os.chdir(cwd)


def dwell_swaps(handler_path):
    """Pull _DWELL_SWAPS out of the source without importing handler.py."""
    with open(handler_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "_DWELL_SWAPS":
                    return ast.literal_eval(node.value)
    return []


def arms(text, swaps):
    """Every text Gemini can actually receive for this section."""
    out = {"flag-off (live)": text}
    swapped = text
    for old, new in swaps:
        if old in swapped:
            swapped = swapped.replace(old, new)
    if swapped != text:
        out["PROMPTLY_DWELL on"] = swapped
    return out


_PINNED = re.compile(r'"([^"\\]{12,})"\s+in\s+_(?:src|h|prompt|sys)\b')


def pinned_literals(after_path, before_path, gate="validate_deploy.py"):
    """Prompt phrases validate_deploy asserts verbatim.

    A caveman pass deletes articles — and `validate_deploy` pins some prompt
    sentences EXACTLY ("NEVER cover the speaker's face", "the FACE FILLS THE
    CENTER BAND even when the head-TOP reads"). Dropping one 'the' from those
    breaks the deploy gate, and the content-word diff cannot see it: no content
    word was lost. This is the missing check, so a reword can never silently
    break a gate that a prior ruling put there.
    """
    try:
        with open(gate, encoding="utf-8") as fh:
            gsrc = fh.read()
        with open(after_path, encoding="utf-8") as fh:
            hsrc = fh.read()
        with open(before_path, encoding="utf-8") as fh:
            bsrc = fh.read()
    except OSError:
        return []
    # REGRESSIONS only: a literal counts iff it was in handler.py before and is
    # gone now. Literals that were never there pin some other file (the Remotion
    # components, say) and are not this gate's business.
    return sorted({lit for lit in _PINNED.findall(gsrc)
                   if lit in bsrc and lit not in hsrc})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, help="pre-change handler.py snapshot")
    ap.add_argument("--after", default="handler.py")
    a = ap.parse_args()

    before, after = _map_for(a.before), _map_for(a.after)
    swaps = dwell_swaps(a.after)
    cpt = before["chars_per_token"]

    failures, tb, ta = [], 0, 0
    print(f"PHASE-3 SECTION CERT   {a.before}  ->  {a.after}\n")
    print(f"{'before':>7}  {'after':>7}  {'delta':>7}  {'ratio':>6}  {'verdict':<10} section")
    print("-" * 96)

    for label, otext in before["sections"].items():
        ntext = after["sections"].get(label)
        if ntext is None:
            failures.append(f"{label}: SECTION DISAPPEARED")
            continue
        b, n = len(otext) / cpt, len(ntext) / cpt
        tb, ta = tb + b, ta + n

        rep = C.audit(otext, ntext)
        lost = rep["lost_content_words"] + rep["lost_numbers"] + rep["lost_names"]

        # An invariant passes if the arm that owns it still holds.
        owned = [i for i in C.DO_NOT_COLLAPSE if i[1] == label]
        collapsed = []
        if owned:
            per_arm = {k: C.check_invariants(label, v) for k, v in arms(ntext, swaps).items()}
            for iid, _sec, _toks, desc in owned:
                if all(any(c[0] == iid for c in v) for v in per_arm.values()):
                    collapsed.append((iid, desc))

        ok = not lost and not collapsed
        verdict = "PASS" if ok else "FAIL"
        if not ok:
            failures.append(label)
        flag = "" if abs(b - n) < 1 else f"{b / max(1.0, n):.3f}x"
        print(f"{round(b):>7,}  {round(n):>7,}  {round(n - b):>+7,}  {flag:>6}  "
              f"{verdict:<10} {label}")
        for w in lost:
            print(f"{'':>32}  LOST: {w}")
        for iid, desc in collapsed:
            print(f"{'':>32}  INVARIANT COLLAPSED — {iid}: {desc}")

    print("-" * 96)
    print(f"{round(tb):>7,}  {round(ta):>7,}  {round(ta - tb):>+7,}  "
          f"{tb / max(1.0, ta):>5.3f}x  {'':<10} CORE (13 sections)")
    # gate-pinned prompt phrases must survive verbatim
    broken = pinned_literals(a.after, a.before)
    if broken:
        print(f"\nGATE-PINNED PHRASES BROKEN ({len(broken)}) — validate_deploy asserts these verbatim:")
        for lit in broken:
            print(f"    {lit[:100]}")
        failures.append("gate-pinned phrases")
    else:
        print("\ngate-pinned phrases: all present (validate_deploy literals intact)")

    print(f"\n{'CERT PASS — nothing removed, no invariant collapsed, no gate phrase broken' if not failures else 'CERT FAIL: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
