#!/usr/bin/env python3
"""cert_offthread_evidence.py — THE RENDER'S OWN NUMBER REACHES THE ROW.

offthreadVideoThreads shipped at v573 as the only named lead on render, which is
61% of a 235s wall. It has been UNPROVEN ever since, and not once for a reason
that had anything to do with the lever:

  attempt 1   read the orchestrator's tee. The value is printed by
              render-full.mjs INSIDE the burst container. Empty.
  attempt 2   same reader, same container, same empty result.

Twice the instrument was pointed at the wrong process and twice "no evidence"
was indistinguishable from "no effect". The value was in `_r.stdout` the entire
time — subprocess.run captures it — and was being printed straight back out to
the container that nobody was reading.

THE CONTRACT THIS FILE DEFENDS IS A CROSS-FILE ONE, which is the part that
actually rots: render-full.mjs FORMATS the line and handler.py PARSES it, in two
languages, with nothing but this cert holding them together. A reworded log line
in the .mjs silently empties the column in the .py, and the failure mode is a
NULL that reads exactly like "the render never ran" — the PROBE COLLAPSE class,
which has already produced one false verdict here.

    python3 cert_offthread_evidence.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MJS = open(os.path.join(HERE, "src/remotion/render-full.mjs"), encoding="utf-8").read()
HND = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
NC = "\n".join(re.sub(r"#.*$", "", ln) for ln in HND.splitlines())


def main():
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if not cond and detail else ""))
        if not cond:
            fails.append(name)

    # ── 1. THE LEVER IS SET, NOT MERELY LOGGED ──────────────────────────────
    # A log line saying what we intended, beside a renderMedia call that never
    # received it, is the built-not-wired class with eleven precedents.
    check("renderMedia actually receives offthreadVideoThreads",
          re.search(r"offthreadVideoThreads:\s*Number\(", MJS) is not None,
          "the option is logged but not passed — the render uses Remotion's 2")
    # THE OVERRIDE MUST BE ON THE OPTION, not merely somewhere in the file.
    # The log line also names the env var, so a substring check passes even
    # after the renderMedia option is hardcoded — the reverting mechanism gone
    # while the cert reads green. Caught by mutation, not by review.
    check("the override is wired to the OPTION, not just mentioned",
          re.search(r"offthreadVideoThreads:\s*Number\(\s*process\.env\."
                    r"PROMPTLY_OFFTHREAD_THREADS\s*\|\|", MJS) is not None,
          "PROMPTLY_OFFTHREAD_THREADS=2 would no longer restore the default")

    # THE LOG AND THE OPTION MUST COMPUTE THE SAME EXPRESSION. Found by
    # mutation: editing only the LOG line's copy left the cert green, and that
    # is a genuine defect, not a harness artifact. The persisted column is read
    # FROM THE LOG. If the log resolves `resolvedConcurrency` while the option
    # resolves `process.env.X || resolvedConcurrency`, then setting the override
    # makes the row report 8 while the render actually used 2 — a column that is
    # confidently, silently wrong. That is worse than the NULL this whole change
    # exists to fix, because a NULL announces itself.
    _log_expr = re.search(r"offthreadVideoThreads=\$\{([^}]*)\}", MJS)
    _opt_expr = re.search(r"offthreadVideoThreads:\s*([^,]*),", MJS)
    check("the logged expression is identical to the option's",
          _log_expr is not None and _opt_expr is not None
          and " ".join(_log_expr.group(1).split()) == " ".join(_opt_expr.group(1).split()),
          f"log={_log_expr.group(1).strip() if _log_expr else None!r}\n"
          f"         opt={_opt_expr.group(1).strip() if _opt_expr else None!r}\n"
          f"         the row would report a value the render did not use")

    # ── 2. THE CROSS-FILE CONTRACT ──────────────────────────────────────────
    # Build the line the way the .mjs builds it, then run the .py's OWN regex
    # against it. This is the assertion that survives a reword: if either side
    # moves, the synthesised line stops matching and this fails.
    m = re.search(r'r"([^"]*offthreadVideoThreads[^"]*)"', NC)
    check("handler declares a parser for the line", m is not None,
          "nothing reads the value out of the captured stdout")
    if not m:
        print("\n  CERT OFFTHREAD-EVIDENCE: FAIL (no parser)")
        return 1
    pattern = m.group(1).replace("\\\\d", "\\d")

    # The literal text between the two interpolations, taken from the .mjs.
    joiner = re.search(r"concurrency=\$\{resolvedConcurrency\}`\s*\+\s*`(.*?)\$\{", MJS)
    check("the .mjs still emits concurrency= then offthreadVideoThreads=",
          joiner is not None,
          "the log line was restructured; the parser cannot be relied on")
    sep = joiner.group(1).replace("offthreadVideoThreads=", "") if joiner else " "
    synthetic = f"[render-full] composition=X frames 0-99, 3 segments, concurrency=8{sep}offthreadVideoThreads=8 (remotion default is 2)"
    hit = re.search(pattern, synthetic)
    check("handler's regex matches a line built from the .mjs template",
          hit is not None and hit.group(1) == "8" and hit.group(2) == "8",
          f"pattern {pattern!r} did not match {synthetic!r} — the two files have "
          f"DRIFTED and the column will be silently NULL")

    # A wrong-but-plausible line must NOT match, or the parser is not a parser.
    check("a line without the pair does not match",
          re.search(pattern, "[render-full] composition=X, concurrency=8") is None)

    # ── 3. IT REACHES THE ROW ───────────────────────────────────────────────
    check("the value is collected into a module holder",
          "_RENDER_OFFTHREAD.setdefault(\"offthread\", []).append(" in NC
          and "_RENDER_OFFTHREAD.setdefault(\"concurrency\", []).append(" in NC,
          "parsed and discarded")
    check("both are persisted on the job row",
          '"render_offthread_threads":' in NC and '"render_concurrency":' in NC)
    # ── AST, BECAUSE STRINGS CANNOT SEE STRUCTURE ──────────────────────────
    # Two checks here were string-based and BOTH passed under mutation: the
    # nesting test compared file offsets (dedenting a key does not move it in
    # the file) and the None test found `or None` on the OTHER field. A grep
    # cannot tell nesting from ordering, or field A from field B. The AST can.
    import ast as _ast
    _st = None
    for _n in _ast.walk(_ast.parse(HND)):
        if isinstance(_n, _ast.Dict):
            for _k, _v in zip(_n.keys, _n.values):
                if (isinstance(_k, _ast.Constant) and _k.value == "stage_timings"
                        and isinstance(_v, _ast.Dict)):
                    _st = _v
    check("a stage_timings dict literal exists", _st is not None)
    _keys = {}
    if _st is not None:
        _keys = {k.value: v for k, v in zip(_st.keys, _st.values)
                 if isinstance(k, _ast.Constant) and isinstance(k.value, str)}
    for _f in ("render_offthread_threads", "render_concurrency", "render_legs_reporting"):
        check(f"{_f} is nested INSIDE stage_timings", _f in _keys,
              "a top-level key is stripped by content-studio — the class that "
              "ate gemini_tokens, vad_coverage, _lang_bundle and source_duration")

    # PER FIELD, not "somewhere in the file".
    for _f in ("render_offthread_threads", "render_concurrency"):
        _v = _keys.get(_f)
        _ok = (isinstance(_v, _ast.BoolOp) and isinstance(_v.op, _ast.Or)
               and isinstance(_v.values[-1], _ast.Constant)
               and _v.values[-1].value is None)
        check(f"{_f} falls back to None, never [] or 0", _ok,
              "an empty list reads as 'the render reported nothing' and 0 as "
              "'threads=0' — both indistinguishable from a render that never ran")
    check("reset per job (warm containers)",
          "_RENDER_OFFTHREAD.clear()" in NC,
          "a warm container would attribute the previous job's render to this one")

    # ── 4. UNMEASURED IS NOT ZERO, AND NOT AN EMPTY LIST ────────────────────
    # `[]` would read as "the render reported nothing" and `0` as "threads=0".
    # None is the only honest value for "no leg reported", and the count beside
    # it is what makes the difference legible.
    # ── 5. THE LIST IS NOT FLATTENED TO ONE NUMBER ──────────────────────────
    # Overlay and micro legs render separately. If they ever resolve to
    # different values, that difference IS the finding.
    check("distinct values are kept, not collapsed to a scalar",
          "sorted(set(_RENDER_OFFTHREAD.get(\"offthread\")" in NC)

    print()
    if fails:
        print(f"  CERT OFFTHREAD-EVIDENCE: FAIL ({len(fails)})")
        return 1
    print("  NOTE: asserts the value REACHES THE ROW. That the lever MOVES the")
    print("  wall clock is proven by a by-route cut on real traffic against this")
    print("  column, not by this file.")
    print("  CERT OFFTHREAD-EVIDENCE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
