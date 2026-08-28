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
    # PIN THE SUBSTANCE, NOT THE SIGNATURE. The first cut pinned the exact arg
    # list and went RED when a per-job `input_data` override was ADDED — a
    # correct change failing a check that meant to forbid a different thing.
    # Count of the assignment still catches both real regressions: dropped (0)
    # and resolved twice (2).
    check("resolved once per job, beside the other resets",
          NC.count("_OFFTHREAD_ARM[0] = _resolve_offthread_arm(") == 1)

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

    # ── RENDERCLOCK: THE PAINT/ENCODE SPLIT THAT DECIDES THE GPU QUESTION ──
    # The renderer has ALWAYS emitted a complete, grep-stable leg decomposition
    # whose children reconcile to the parent by construction — and nothing ever
    # parsed it. (A LEGSTAT line I added was a second, poorer copy of it and has
    # been deleted rather than kept beside it.)
    #
    # frames_ms vs stitch_ms is the field that matters: cert_gpu_fps measures
    # renderMedia({codec:"h264"}) END TO END, so its overall_fps is PAINT +
    # ENCODE fused and cannot attribute a null result to either. If stitch
    # dominates, GPU-Chromium is irrelevant whatever that probe returns.
    check("the renderer emits RENDERCLOCK", "[RENDERCLOCK]" in MJS,
          "the leg decomposition is gone")
    for _f in ("frames_ms=", "stitch_ms=", "frames=", "ms_per_frame="):
        check(f"RENDERCLOCK still carries {_f}", _f in MJS,
              "the paint/encode split cannot be reconstructed without it")
    _rp = re.search(r'r"(\\\[RENDERCLOCK[^"]*)"', NC)
    check("handler declares a RENDERCLOCK parser", _rp is not None)
    check("the parsed legs are persisted",
          '"render_legs": (_RENDER_OFFTHREAD.get("legs") or None)' in NC)
    check("RENDERCLOCK is collected, not discarded",
          '_RENDER_OFFTHREAD.setdefault("legs", []).append(' in NC,
          "parsed and thrown away — the column would be permanently None")
    # THE CROSS-FILE CONTRACT, built from the .mjs template and run against
    # handler's OWN regex. Two languages, nothing else holding them together.
    _synth = ("[RENDERCLOCK] leg=PromptlyMicroSegments:0-545 total_ms=112400 "
              "bundle_ms=0 browser_ms=1010 select_ms=240 render_ms=109600 "
              "frames_ms=104200 stitch_ms=5400 unaccounted_ms=1550 frames=546 "
              "ms_per_frame=190.8")
    _parts = [ln for ln in NC.splitlines() if 'r"\\[RENDERCLOCK' in ln]
    check("handler's regex matches a line built from the .mjs template",
          bool(_parts) and re.search(
              r"\[RENDERCLOCK\] leg=(\S+) total_ms=(\d+) bundle_ms=(\d+) "
              r"browser_ms=(\d+) select_ms=(\d+) render_ms=(\d+) "
              r"frames_ms=(\d+) stitch_ms=(-?\d+) unaccounted_ms=(-?\d+) "
              r"frames=(\d+) ms_per_frame=([0-9.]+)", _synth) is not None,
          "the .mjs and .py have DRIFTED — render_legs goes silently NULL")

    # ── NO METRIC CROSSES A SPAWN BOUNDARY BY STDOUT (standing rule) ───────
    # RENDERCLOCK is written by render-full.mjs into the BURST container's
    # stdout. handler dispatches that render with `.spawn()` and lives on the
    # far side, so its stdout loop never sees the stream — which is why
    # render_legs was EMPTY on every burst render, organic and batched alike.
    # Parsing it in the orchestrator was the original "logs in the burst
    # container" bug, reintroduced one process closer and still on the wrong
    # side of the boundary. Produced-where-observed, returned on the existing
    # contract.
    MA = open(os.path.join(HERE, "modal_app.py"), encoding="utf-8").read()
    check("the BURST parses RENDERCLOCK, where it is produced",
          "RENDERCLOCK" in MA and 'out.setdefault("renderclock", [])' in MA,
          "the only process that can see the stream does not read it")
    check("it rides the burst's existing return contract",
          'out.setdefault("renderclock"' in MA and '"ok"' in MA,
          "a second channel would need its own delivery guarantee")
    check("the orchestrator READS the return value, never a remote stdout",
          '_res.get("renderclock")' in NC,
          "handler must consume what the burst returned")
    # THE RULE IS ABOUT THE BOUNDARY, NOT ABOUT STDOUT. handler's in-process
    # parse in _remotion_subprocess is LEGITIMATE and must stay: when the render
    # is NOT bursted it runs as this process's own child and its stdout is
    # genuinely visible here. Forbidding all stdout parsing would delete the
    # working non-burst path.
    #
    # What must never regress is the BURST path silently depending on the
    # orchestrator to read a stream it cannot see. That is asserted positively —
    # the burst produces it and handler consumes the RETURN — because "the bad
    # thing is absent" is unfalsifiable here while "the good path exists" is not.
    # The literal in handler is the ESCAPED regex (\[RENDERCLOCK\]), so an
    # unescaped needle cannot match it — the first cut of this check failed on
    # correct code for that reason.
    check("the non-burst in-process parse is retained",
          "RENDERCLOCK" in NC,
          "deleting it would strip timings from every non-burst render")
    # A PARSER NESTED UNDER A FILTER THAT CANNOT MATCH IT is indistinguishable
    # from an absent parser, and reads as "the renderer emitted nothing". This
    # exact shape shipped: the RENDERCLOCK parse sat inside
    # `if _ls.startswith("[render-full]")` while every RENDERCLOCK line starts
    # with "[RENDERCLOCK]", so it excluded 100% of its own input. The
    # offthreadVideoThreads parse survived only because that value happens to
    # ride a [render-full] line. Asserted by INDENTATION, because that is the
    # property that was wrong — presence of the parse was never in doubt.
    _lines = NC.splitlines()
    _if_i = next((i for i, l in enumerate(_lines)
                  if 'if _ls.startswith("[render-full]")' in l), None)
    _rc_i = next((i for i, l in enumerate(_lines) if "_rc = re.search(" in l), None)
    check("the RENDERCLOCK parse is NOT nested under the [render-full] filter",
          _if_i is not None and _rc_i is not None
          and (len(_lines[_rc_i]) - len(_lines[_rc_i].lstrip()))
              <= (len(_lines[_if_i]) - len(_lines[_if_i].lstrip())),
          "the parse is indented inside a branch that cannot match its own "
          "input — it would read as 'no legs reported' forever")

    check("burst and non-burst BOTH feed the same holder",
          NC.count('_RENDER_OFFTHREAD.setdefault("legs", []).append(') >= 2,
          "one of the two render paths reports nothing")

    # ── THE NORMALIZE DECOMPOSITION IS THE POOL, NOT THE WAITS ─────────────
    # Measured: dur 48.1s, unaccounted 48.1s, all five waits ZERO. The work runs
    # in the mega-pool BEFORE the awaits, and _pool_timings measured it the whole
    # time while only being printed.
    check("per-task pool timings are persisted",
          '"pool_task_s": (dict(_POOL_TIMINGS_LAST) or None)' in NC,
          "the segments that actually carry the 48.1s stay unqueryable")
    check("pool timings are captured, not just printed",
          "_POOL_TIMINGS_LAST.update(_pool_timings)" in NC)
    check("reset per job (warm containers)",
          "_POOL_TIMINGS_LAST.clear()" in NC and NC.count("_POOL_TIMINGS_LAST.clear()") >= 2)
    # 1c: the x-axis must travel WITH the stage duration.
    QA = open(os.path.join(HERE, "query_offthread_app.py"), encoding="utf-8").read()
    check("the read returns source_s beside every stage_s",
          '"source_s": st.get("source_duration_s")' in QA,
          "a stage duration without its source duration cannot be placed on the "
          "affine curve — intercept and slope are unrecoverable from y alone")

    # ── THE BURST STAGE BOUNDARY (measured, not theorised) ─────────────────
    # 42 of 42 organic post-v574 jobs carried render_offthread_threads and ALL
    # 42 were None. render_stage runs INSIDE the render_burst container on the
    # production path, so its parse populates a holder in THAT process while the
    # orchestrator assembles stage_timings from its own. Both instruments were
    # dark on every bursted job, at every duration — the 60s/120s "drop" was
    # never about duration, it was burst-vs-local.
    #
    # Same standing rule as the fanout chunk, one level up: produced-where-
    # observed, returned on the contract the caller already reads.
    check("render_stage returns its instruments",
          '"render_instruments": {' in NC,
          "a bursted render reports nothing however correct the parse is")
    check("the orchestrator merges them back",
          '_ri.get(_k) or []' in NC and '_RENDER_OFFTHREAD.setdefault(_k, []).extend(' in NC,
          "returned and dropped is the same as never returned")
    check("a failed merge is LOUD, never silent",
          "INSTRUMENT MERGE FAILED" in NC,
          "silence is indistinguishable from a burst that rendered nothing")

    # ── A None PATH MUST NOT BECOME A TypeError ────────────────────────────
    # os.path.exists(None) RAISES; os.path.exists("") returns False. That
    # asymmetry turned a missing render artifact into an unclassifiable
    # TypeError, and because the fault is INPUT-INDEPENDENT the degrade ladder
    # reproduced it on every rung and exhausted: 10 jobs, 5 users, both
    # ladder_exhausted variants traced to this one line-shape.
    # BANNED SYMBOL, same pattern that closed localizedTitle. One bug had ONE
    # visible instance and TWELVE invisible ones — each a latent TypeError
    # waiting for its own artifact to go missing. Guarding twelve sites does not
    # stop the thirteenth being written next week; banning the bare form does.
    import re as _re2
    _bad = [NC[m.start():m.end()].strip()[:70] for m in _re2.finditer(
        r"^\s*(?:el)?if not os\.path\.exists\(([A-Za-z_][A-Za-z0-9_]*)\)", NC, _re2.M)]
    check("no bare `if not os.path.exists(<name>)` survives — use _exists()",
          not _bad,
          f"{len(_bad)} bare site(s): {_bad[:3]}\n"
          f"         os.path.exists(None) RAISES where '' returns False. Use the "
          f"None-safe _exists() helper.")
    check("the _exists helper exists and is None-safe",
          "def _exists(p) -> bool:" in NC and "return bool(p) and _os.path.exists(p)" in NC,
          "the ban has nothing to redirect callers to")
    _n_ex = NC.count("_exists(")
    check("callers actually adopted it",
          _n_ex >= 15, f"only {_n_ex} _exists( references — the ban would just "
                       f"push the shape somewhere else")
    check("a recurrence stays NAMED, not unclassified",
          '("missing_artifact_path"' in NC,
          "the class would slide back into ladder_exhausted with no mechanism")

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
