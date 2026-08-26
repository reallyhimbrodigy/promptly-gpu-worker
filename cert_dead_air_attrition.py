#!/usr/bin/env python3
"""cert_dead_air_attrition.py — ONE NUMBER WAS DOING TWO JOBS.

`preserved_silences: []` is the SCHEMA DEFAULT. Alone it cannot distinguish

    the model was asked about N spans and chose to cut them all   (working)
    the model was never asked                                     (inert)

and those point at opposite fixes. detect_dead_air once LOCATED 116 silences
and RETURNED 0 — the model was never asked — and nothing recorded the gap, so
v561's Arabic fix ("an ASR's punctuation habits must not gate a language route")
was UNCONFIRMABLE on real traffic regardless of volume. Measured 2026-08-25:
completion rate 100% pre and 100% post, which is the wrong instrument entirely,
because a passthrough completes.

Three numbers instead of one:

    located   cleared the SILENCE bar, before any linguistic gate
    offered   survived every gate and reached the model
    preserved the model chose to keep

    located > offered   -> a GATE is eating spans          (the Arabic defect)
    offered > 0, preserved == 0 -> the model is deciding   (working as designed)

    python3 cert_dead_air_attrition.py
"""
import ast
import os
import re
import sys

os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
NC = "\n".join(re.sub(r"#.*$", "", ln) for ln in SRC.splitlines())


def enclosing(src, needle):
    ln = src[:src.index(needle)].count("\n") + 1
    best = None
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= ln <= (n.end_lineno or 0):
            if best is None or n.lineno > best.lineno:
                best = n
    return best


def main():
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if not cond and detail else ""))
        if not cond:
            fails.append(name)

    import handler as H

    check("both holders exist", hasattr(H, "_DEAD_AIR_LOCATED") and hasattr(H, "_DEAD_AIR_OFFERED"))

    # LOCATED is counted BEFORE the linguistic gate, or it cannot expose a gate
    # eating spans — which is the entire point.
    i_loc = NC.index("_DEAD_AIR_LOCATED[0] += 1")
    i_gate = NC.index("_sentence_final_word(words[a])")
    check("located is counted BEFORE the linguistic gate", i_loc < i_gate,
          "counted after the gate, so located == offered always and the gap is invisible")

    # ...and AFTER the silence bar, or it counts every gap in the transcript.
    i_sil = NC.index("if silence_in_gap < _WITHIN_CLIP_TRIM_TRIGGER_S:")
    check("located is counted AFTER the silence bar", i_sil < i_loc,
          "would count every word gap, not silences")

    check("offered is set from the list the prompt iterates",
          "_DEAD_AIR_OFFERED[0] = len(_located_silences)" in NC,
          "a separately-derived number can drift from what was shown")

    # SCOPE. The persist site is in handler(); _located_silences lives in
    # generate_edit_gemini. Reading it directly would NameError into a fail-safe.
    fn = enclosing(SRC, '"dead_air_spans_offered"')
    check("the persist site uses the holder, not the out-of-scope local",
          '"dead_air_spans_offered": _DEAD_AIR_OFFERED[0]' in NC,
          f"persist is in {fn.name}(); _located_silences is not in scope there")

    check("both fields are persisted", '"dead_air_spans_located"' in NC and '"dead_air_spans_offered"' in NC)

    # NESTED, not top-level: content-studio strips top-level keys and that
    # already ate gemini_tokens, vad_coverage, _lang_bundle and source_duration.
    i_tl = NC.index('"timeline": _tl_report()')
    i_da = NC.index('"dead_air_spans_located"')
    check("nested beside timeline, not top-level", abs(i_da - i_tl) < 2000,
          "a top-level key is stripped before any reader sees it")

    # RESET PER JOB, or one job's attrition is attributed to the next.
    check("both reset per job at handler entry",
          "_DEAD_AIR_LOCATED[0] = 0" in NC and "_DEAD_AIR_OFFERED[0] = 0" in NC)
    i_reset = NC.index("_DEAD_AIR_LOCATED[0] = 0")
    check("the reset sits beside the component-ledger reset",
          abs(i_reset - NC.index("_component_ledger_reset()", i_reset - 900)) < 900)

    print()
    if fails:
        print(f"  CERT DEAD-AIR-ATTRITION: FAIL ({len(fails)})")
        return 1
    print("  NOTE: asserts the WRITE. That located>offered actually EXPOSES a gate")
    print("  is proven by an Arabic job on real traffic, not by this file.")
    print("  CERT DEAD-AIR-ATTRITION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
