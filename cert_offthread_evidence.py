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

    # ── THE ARM: DECOUPLED, PER-JOB, AND SALTED ────────────────────────────
    # MEASURED before arming: offthread == concurrency on EVERY leg
    # ({2:12,4:7,8:5,16:13} across 37), so the two are perfectly collinear and no
    # cut of production traffic can separate them. The arm must PIN the extractor
    # independently of concurrency or it measures nothing.
    check("the arm pins the extractor independently of concurrency",
          'return "2" if' in NC and "_resolve_offthread_arm" in NC,
          "an arm that moves with concurrency is collinear with it and unreadable")
    # PER-JOB, NOT PER-CONTAINER. render-full.mjs reads process.env, fixed at
    # container start — arming via the secret would be a flip, and the only
    # concurrency that produces is the warm/cold mixture whose container age
    # correlates with load. Exactly the defect the stall experiment shipped with.
    check("the arm crosses as a per-invocation subprocess env",
          'env=_env' in NC and '_env["PROMPTLY_OFFTHREAD_THREADS"] = _OFFTHREAD_ARM[0]' in NC,
          "a per-container env is a flip, not a split")
    check("os.environ is NOT mutated to carry the arm",
          'os.environ["PROMPTLY_OFFTHREAD_THREADS"]' not in NC,
          "mutating the parent env leaks the arm to every later job in a warm "
          "container — one job's assignment would silently become permanent")
    # SALTED. An unsalted hash puts the SAME jobs in both experimental arms, and
    # each experiment becomes the other's confound.
    check("the split is salted apart from the stall experiment",
          '"offthread:" + str(job_id)' in NC,
          "co-assignment would make both results unreadable")
    check("dark by default behind its own flag",
          'PROMPTLY_OFFTHREAD_ARM' in NC and '!= "1"' in NC)
    check("the arm is persisted on the row",
          '"offthread_arm": _OFFTHREAD_ARM[0],' in NC,
          "cut by clock instead of by what ran")
    check("resolved once per job, beside the other resets",
          NC.count("_OFFTHREAD_ARM[0] = _resolve_offthread_arm(job_id)") == 1)

    # ── ITEM (2): THE STAGE THAT HAD NO NODE ───────────────────────────────
    # normalize_transcribe_upload was 49.5s p50 — larger than the whole
    # editorial call — and ABSENT FROM THE TIMELINE TREE. Not zero children: no
    # node. 100% invisible, so no parallelism change could be sized against it.
    check("normalize_transcribe_upload now has a timeline node",
          '_tl_add_done("normalize_transcribe_upload"' in NC,
          "without a parent the waits below are orphaned onto `job`")
    _nw = NC.count('parent="normalize_transcribe_upload"')
    check("its blocking waits are instrumented as children",
          _nw >= 5, f"only {_nw} wait span(s) — the stage stays mostly unattributed")
    check("the waits use _tl_wait, which measures the WAIT not the work",
          '_tl_wait("wait_normalize"' in NC,
          "these are pool futures; the number wanted is the long pole")

    # ── LEGSTAT: THE DECOMPOSITION OF "A CHUNK COSTS ~110s" ────────────────
    # Same cross-file contract as the offthread line, same rot risk: the .mjs
    # FORMATS it and the .py PARSES it, in two languages. Built from the .mjs
    # template and run against handler's own regex.
    check("the renderer emits a LEGSTAT line", "LEGSTAT frames=" in MJS,
          "no per-leg frames/fps — 110s stays one undecomposed number")
    _lp = re.search(r'r"(LEGSTAT[^"]*)"', NC)
    check("handler declares a LEGSTAT parser", _lp is not None)
    if _lp:
        _pat = _lp.group(1).replace("\\\\d", "\\d")
        _synth = "[render-full] LEGSTAT frames=2184 elapsed=109.60 fps=19.93 chunked=1 composition=PromptlyMicroSegments"
        _hit = re.search(_pat, _synth)
        check("handler's regex matches a line built from the .mjs template",
              _hit is not None and _hit.group(1) == "2184" and _hit.group(3) == "19.93",
              f"{_pat!r} did not match {_synth!r} — the files have DRIFTED and "
              f"the column goes silently NULL")
    # COLLECTED, not just persisted. Found by mutation: replacing the append
    # with a discard left this cert GREEN, because the persist line still
    # referenced the key it would now never contain. Asserting the write site
    # without the read site is half a check.
    check("LEGSTAT is collected into the holder, not discarded",
          '_RENDER_OFFTHREAD.setdefault("legs", []).append(' in NC,
          "parsed and thrown away — the column would be permanently None")
    check("per-leg stats are persisted",
          '"render_legs": (_RENDER_OFFTHREAD.get("legs") or None)' in NC,
          "parsed and discarded")
    check("no leg reporting persists None, never []",
          'or None)' in NC,
          "an empty list reads as 'the render rendered no frames'")

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
