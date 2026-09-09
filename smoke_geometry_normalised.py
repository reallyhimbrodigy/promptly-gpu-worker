#!/usr/bin/env python3
"""The delivered file is 1080x1920 whatever the source was.

THE DEFECT. build_cut trimmed and concatenated and never normalised geometry, so
the delivered video was whatever resolution the source happened to be. Round 42 —
the FIRST round on real footage — delivered `motion` at 540x960 and `car_short`
at 720x1272 against a 1080x1920 contract. The gate check `(w, h) != (1080, 1920)`
had existed the whole time and had never once had a source that could fail it,
because every synthetic fixture was ALREADY 1080x1920. A user uploading sub-HD
got sub-HD back.

TWO LEGS, because there are two ways to ship this broken:

  the DERIVATION — run the real function on the real dimensions of all five
  corpus sources. A pure function is testable by RUNNING it, which beats any
  assertion about its text.

  the WIRING — build_cut must actually call it, and the normalised stage must be
  what [outv] resolves to. Checked on the AST: a scale= string sitting anywhere
  in the file proves nothing (that is the standing law here), and neither does a
  call whose result is dropped on the floor.

  python3 smoke_geometry_normalised.py     exit 0 = normalised and wired
"""
import ast
import os
import sys

import agentic_editor_app as app

HERE = os.path.dirname(os.path.abspath(__file__))

# The real dimensions of the five real sources, plus the conforming case.
CASES = [
    ("talking_head",     1080, 1920, "none"),
    ("motion",            540,  960, "scale"),
    ("car_short",         720, 1272, "scale"),
    ("screen_recording", 3826, 2160, "reframe_crop"),
    ("car_mid",          2160, 3840, "scale"),
]


def main():
    fails = []

    def check(label, ok, detail=""):
        print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
        if not ok:
            fails.append(label)

    if not hasattr(app, "geometry_normalise_filter"):
        print("  [FAIL] geometry_normalise_filter does not exist — the "
              "normalisation is inline or absent, and no test can reach it.")
        return 1
    g = app.geometry_normalise_filter

    print("DERIVATION — the five real sources:")
    for name, w, h, want_mode in CASES:
        filt, mode, loss = g(w, h)
        check(f"{name:17} {w}x{h} -> {mode}", mode == want_mode,
              f"expected {want_mode}" if mode != want_mode
              else (f"crop_loss {loss:.1%}" if loss else "no loss"))
        # A conforming source must emit NO filter, so it is not re-encoded
        # through a no-op scale; every other source must emit one.
        check(f"{name:17} emits {'no' if want_mode == 'none' else 'a'} filter",
              (filt == "") if want_mode == "none" else bool(filt))

    print("\n  a source that cannot be measured is 'unknown', never silently 0:")
    for bad in ((0, 0), (None, 1920), ("x", "y")):
        filt, mode, loss = g(*bad)
        check(f"g{bad} -> {mode}", mode == "unknown" and filt == "" and loss is None)

    # The output must be EXACTLY the contract, and cover-not-pad means the crop
    # is what makes it exact. Assert the emitted filter states both.
    filt, _, _ = g(3826, 2160)
    check("the filter scales to cover AND crops to exactly 1080:1920",
          "force_original_aspect_ratio=increase" in filt
          and "crop=1080:1920" in filt and "setsar=1" in filt, filt)

    print("\nWIRING — build_cut must call it and [outv] must come from it:")
    tree = ast.parse(open(os.path.join(HERE, "agentic_editor_app.py"),
                          encoding="utf-8").read())
    bc = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "build_cut"), None)
    check("build_cut exists", bc is not None)
    if bc is None:
        return 1
    calls = [n for n in ast.walk(bc) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "geometry_normalise_filter"]
    check("build_cut CALLS geometry_normalise_filter", len(calls) == 1,
          f"{len(calls)} call(s)")
    # Its result must be BOUND, not dropped — a call whose value goes nowhere
    # changes nothing, which is the "is it called vs is it choosing" trap.
    bound = [n for n in ast.walk(bc) if isinstance(n, ast.Assign)
             and any(isinstance(v, ast.Call)
                     and getattr(v.func, "id", "") == "geometry_normalise_filter"
                     for v in ast.walk(n))]
    check("its result is BOUND, not discarded", len(bound) == 1)
    # And the normalised stage must produce [outv]: the concat output is renamed
    # to an intermediate whenever a filter exists, so downstream is unchanged.
    strs = [n.value for n in ast.walk(bc)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    joined = " ".join(strs) + " " + " ".join(
        v.value for n in ast.walk(bc) if isinstance(n, ast.JoinedStr)
        for v in n.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    check("a normalised stage produces [outv]", "[outv]" in joined and "[cv]" in joined)

    print()
    if fails:
        print(f"{len(fails)} failure(s)")
        return 1
    print("delivered geometry is normalised, and build_cut is the thing doing it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
