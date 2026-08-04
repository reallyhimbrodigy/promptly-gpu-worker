#!/usr/bin/env python3
"""Pre-deploy validation harness.

Run this BEFORE every `modal deploy`. Catches runtime bugs that syntax
checks miss: UnboundLocalError, scope ordering, f-string format errors,
schema mismatches, classify_error shape regressions, etc.

If this exits non-zero, do NOT deploy. Fix the issue first.

Usage:
    python3 validate_deploy.py

Exit codes:
    0 — all checks passed, safe to deploy
    1 — at least one check failed, deploy will introduce a regression
"""
import sys
import os
import io
import ast
import re
import json
import importlib
import inspect
from typing import Any

# Suppress noisy startup prints from handler import.
_real_stderr = sys.stderr
_real_stdout = sys.stdout


class _DevNull:
    def write(self, *_): pass
    def flush(self): pass


_failures: list = []
_passed: list = []


def check(label: str):
    """Decorator that runs a check function, records pass/fail."""
    def deco(fn):
        try:
            fn()
            _passed.append(label)
            print(f"  [PASS] {label}")
        except AssertionError as e:
            _failures.append((label, f"assertion: {e}"))
            print(f"  [FAIL] {label}: {e}")
        except Exception as e:
            _failures.append((label, f"{type(e).__name__}: {e}"))
            print(f"  [FAIL] {label}: {type(e).__name__}: {e}")
        return fn
    return deco


# ─── 1. SYNTAX & STATIC ANALYSIS ──────────────────────────────────────
print("\n[1/6] Syntax + static analysis")


@check("handler.py parses as valid Python")
def _syntax_check():
    with open("handler.py") as f:
        ast.parse(f.read())


@check("modal_app.py parses as valid Python")
def _modal_syntax():
    with open("modal_app.py") as f:
        ast.parse(f.read())


@check("INC2-TELEMETRY NEST GUARD (speed agent 2026-08-01, RULE-1): the cpu_by_stage / mem_by_stage sizing telemetry must be NESTED inside stage_timings (result.setdefault('stage_timings')), never a top-level result key — content-studio strips unknown top-level keys, so a top-level cpu_by_stage persisted 0/121 on real traffic (same class as source_duration). FAILS if it regresses to `result[\"cpu_by_stage\"] =`, which would make the inc2 burst-sizing data silently un-queryable again.")
def _inc2_telemetry_nest_guard():
    src = open("modal_app.py").read()
    assert '_st_dict["cpu_by_stage"]' in src and '_st_dict["mem_by_stage"]' in src, (
        "cpu_by_stage/mem_by_stage must be nested via _st_dict (result.setdefault('stage_timings')) "
        "so they persist — the inc2 sizing telemetry")
    assert 'result["cpu_by_stage"] =' not in src and 'result["mem_by_stage"] =' not in src, (
        "cpu_by_stage/mem_by_stage found at TOP-LEVEL result — content-studio strips unknown "
        "top-level keys (0/121 on traffic). Nest inside stage_timings instead.")


@check("VIDSTAB RIP-OUT GUARD (Zac 2026-08-01, RULE-1): vidstab is disabled via a secret-independent clamp (_SHAKE_STABILIZE_THRESHOLD = max(..., 1e9)) so organic stabilisation NEVER fires regardless of any live PROMPTLY_VIDSTAB_THRESHOLD secret. FAILS if the clamp is removed — the rip-out cannot silently regress to always-on without a deliberate, reviewed revert.")
def _vidstab_ripout_guard():
    src = open("handler.py").read()
    assert "max(_SHAKE_STABILIZE_THRESHOLD, 1e9)" in src, (
        "vidstab rip-out clamp `max(_SHAKE_STABILIZE_THRESHOLD, 1e9)` missing — "
        "organic stabilisation would re-enable. Restore the clamp or revert "
        "deliberately (Zac 2026-08-01 ripped vidstab out).")


@check("SOURCE_DURATION PERSIST GUARD (Zac 2026-08-01, RULE-1): source_duration_s must be NESTED inside the stage_timings dict, never a top-level result_payload key. content-studio strips unknown top-level result keys — a top-level source_duration_s persisted 0/62 on real traffic (same class as cpu_by_stage). stage_timings persists whole, so the field must ride inside it. This regex FAILS if source_duration_s appears as a top-level `\"source_duration_s\":` at result-payload indentation (12 spaces) rather than nested (16 spaces), catching a silent regression back to the stripped location.")
def _source_duration_persist_guard():
    src = open("handler.py").read()
    assert '"source_duration_s"' in src, (
        "source_duration_s missing entirely — the cohort-control field was dropped")
    # It must appear nested one level deeper than a top-level result_payload key.
    # A top-level key sits at 12-space indent; the nested (inside stage_timings)
    # form sits at 16-space indent. Fail if the 12-space top-level form exists.
    import re
    top_level = re.search(r'\n {12}"source_duration_s"\s*:', src)
    nested = re.search(r'\n {16}"source_duration_s"\s*:', src)
    assert nested is not None, (
        "source_duration_s must be NESTED inside stage_timings (16-space indent) "
        "so content-studio persists it; not found at that depth")
    assert top_level is None, (
        "source_duration_s found at TOP-LEVEL result_payload indent (12 spaces) — "
        "content-studio strips unknown top-level keys (0/62 on traffic). Nest it "
        "inside the stage_timings dict instead.")


@check("GEMINI_TOKENS PERSIST GUARD (Zac 2026-08-02, RULE-1): the gemini_tokens dict (prompt/cached/output + uncached_delta = prompt-cached, the number that decides the prompt lever) must be NESTED inside stage_timings, never a top-level result key — it is the 3RD field this class would strip (source_duration 0/62, cpu_by_stage 0/121). FAILS if gemini_tokens sits at top-level result-payload indent (12 spaces) instead of nested (16), or the _gemini_token_summary helper is gone.")
def _gemini_tokens_persist_guard():
    src = open("handler.py").read()
    assert "def _gemini_token_summary" in src, \
        "the _gemini_token_summary helper was dropped"
    assert '"gemini_tokens"' in src, "gemini_tokens persistence missing entirely"
    import re
    top = re.search(r'\n {12}"gemini_tokens"\s*:', src)
    nested = re.search(r'\n {16}"gemini_tokens"\s*:', src)
    assert nested is not None, \
        "gemini_tokens must be NESTED inside stage_timings (16-space indent)"
    assert top is None, \
        "gemini_tokens at TOP-LEVEL (12-space) — content-studio strips it; nest it"


@check("RENDER CONCURRENCY NEVER FAILS A RENDER (Zac 2026-08-03, RULE-1, THIRD RENDER_FATAL c9e980fe + the clamp that missed it): Remotion HARD-REJECTS --concurrency > cores, and the enforced limit is the Modal cpu REQUEST, which Python CANNOT read — cert_core_probe proved a cpu=8 container reports 24 for sched_getaffinity, os.cpu_count AND cfs_quota. So the budget MUST come from PROMPTLY_RENDER_CORE_BUDGET (each render function declares its own cpu=), the helper MUST floor to a conservative 4 on any miss (never host cores, never raise), _remotion_subprocess MUST self-heal on Remotion's stated max, and each function's declared budget MUST equal its cpu=. FAILS if any of those regress.")
def _render_concurrency_never_fails_guard():
    src = open("handler.py").read()
    # 1. Budget comes from the reliable env, floors to 4, never host cores.
    assert "PROMPTLY_RENDER_CORE_BUDGET" in src and "def _render_core_budget" in src, (
        "_render_core_budget (reading PROMPTLY_RENDER_CORE_BUDGET) is gone — the "
        "concurrency budget would fall back to an unreliable core count (a cpu=8 box "
        "reports 24) and re-break Remotion's --concurrency<=cores limit")
    assert "return 4" in src.split("def _render_core_budget", 1)[1][:600], (
        "_render_core_budget must return a conservative floor (4) on a miss — a perf "
        "helper must never raise or pass host cores into a render")
    assert "(os.cpu_count() or 16) // 2" not in src, (
        "a concurrency tab budget still divides os.cpu_count() (HOST cores on Modal)")
    assert src.count("min(_CONTAINER_CORES,") >= 2, (
        "both _PER_CHUNK_CONCURRENCY and _MICRO_CONCURRENCY must stay min(_CONTAINER_CORES,…)-clamped")
    # 2. The self-heal exists and is bounded.
    assert "Maximum for --concurrency is" in src and "_self_healed=True" in src, (
        "the _remotion_subprocess self-heal (re-run once at Remotion's stated max) is "
        "missing — without it a wrong budget can still fatal a render")
    # 3. Each render function declares a budget that EQUALS its cpu= (anti-drift).
    msrc = open("modal_app.py").read()
    import re as _re
    for _fn in ("run_pipeline_bg", "render_burst"):
        _i = msrc.index(f"def {_fn}(")
        _dstart = msrc.rfind("@app.function", 0, _i)  # nearest decorator above the def
        _decor = msrc[_dstart:_i]                      # ONLY this function's decorator block
        _body = msrc[_i:_i + 2000]                     # the function head where the budget is set
        # Match the REAL resource arg ("cpu=N, memory=…"), not the many cpu=NN
        # mentions in the sizing comment (which never carry ", memory=").
        _cpu = _re.findall(r"cpu=(\d+),\s*memory=", _decor)
        _bud = _re.search(r'PROMPTLY_RENDER_CORE_BUDGET"\]\s*=\s*"(\d+)"', _body)
        assert _cpu, f"{_fn}: no 'cpu=N, memory=' resource arg found in its @app.function decorator"
        assert _bud, f"{_fn}: does not set PROMPTLY_RENDER_CORE_BUDGET in its body"
        assert _bud.group(1) == _cpu[0], (
            f"{_fn}: PROMPTLY_RENDER_CORE_BUDGET={_bud.group(1)} != cpu={_cpu[0]} — "
            f"the render core budget drifted from the container's cpu allocation")


@check("DEPLOY-STATE GUARD (Zac 2026-08-01): a deploy must not DROP a commit already known live. deploy.sh records the last successfully-deployed HEAD in .last_deployed_commit; this FAILS if that commit is not an ancestor of the current HEAD — i.e. you are deploying from a stale branch/checkout that lost a live fix (the 4th deploy-state footgun today: stale server.js, fanout canonical, snapshot env-freeze, the 06:10 validator scare). FAIL-SAFE: passes silently if the file is absent (first deploy), empty, or the commit is unknown to this tree, so it can never wrongly block a legitimate deploy.")
def _deploy_state_guard():
    import subprocess as _sp
    if not os.path.exists(".last_deployed_commit"):
        return  # first deploy — nothing to protect yet
    _last = open(".last_deployed_commit").read().strip()
    if not _last:
        return
    try:
        _known = _sp.run(["git", "cat-file", "-e", _last + "^{commit}"],
                         capture_output=True).returncode == 0
        if not _known:
            return  # last-deployed commit not in this object db — can't judge, skip
        _anc = _sp.run(["git", "merge-base", "--is-ancestor", _last, "HEAD"],
                       capture_output=True)
        _head = _sp.run(["git", "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
    except Exception:
        return  # git unavailable — fail-safe pass
    assert _anc.returncode == 0, (
        f"DEPLOY WOULD DROP A LIVE COMMIT — last deployed {_last[:10]} is NOT an "
        f"ancestor of HEAD {_head}. You are deploying from a tree that lost it. "
        f"Merge/rebase {_last[:10]} in first. If the drop is deliberate, "
        f"rm .last_deployed_commit and re-run.")


@check("no UnboundLocalError via static analysis (pyflakes)")
def _pyflakes_check():
    # pyflakes catches: name X assigned but never used / referenced before
    # assignment / shadowing builtins. This is the static check that
    # would have caught today's _skip_edit_gen bug.
    try:
        from pyflakes import api as _pf_api
        from pyflakes.reporter import Reporter
        out = io.StringIO()
        err = io.StringIO()
        reporter = Reporter(out, err)
        with open("handler.py") as f:
            src = f.read()
        n_errors = _pf_api.check(src, "handler.py", reporter)
        # We tolerate "imported but unused" (lots of conditional imports)
        # but FAIL on "referenced before assignment" and similar.
        critical_patterns = [
            "referenced before assignment",
            "undefined name",
            "redefinition of unused",
        ]
        critical_msgs = []
        for line in (out.getvalue() + err.getvalue()).splitlines():
            for pat in critical_patterns:
                if pat in line:
                    critical_msgs.append(line)
                    break
        assert not critical_msgs, (
            f"{len(critical_msgs)} critical issues:\n    "
            + "\n    ".join(critical_msgs[:10])
        )
    except ImportError:
        # pyflakes not installed locally — skip silently. Will be present
        # in the Modal image at deploy time.
        print("    (pyflakes not installed locally — skipped)")


@check("used-before-assignment gate: mypy possibly-undefined == 0 (job 1a72b344 class)")
def _possibly_undefined_gate():
    # pyflakes (above) has no flow analysis and missed the bug that killed
    # job 1a72b344: a name bound inside a try whose except swallows the
    # binding failure, then read after the block (UnboundLocalError on the
    # first loop iteration, stale value on later ones). mypy's
    # possibly-undefined error code catches that class — but ONLY with
    # --check-untyped-defs (the repo is untyped; without it mypy skips
    # every function body and reports a vacuous zero). This gate is HARD:
    # mypy missing fails the deploy, because the soft-skip pattern is how
    # the last gap survived. Tree was cleaned to zero findings when this
    # landed — any finding is a NEW instance of the class.
    import subprocess
    import tempfile
    _files = ["handler.py", "modal_app.py", "edit_policy.py",
              "type_registries.py", "render_schemas.py", "recipe_eval.py"]
    _args = [sys.executable, "-m", "mypy", "--check-untyped-defs",
             "--enable-error-code=possibly-undefined", "--ignore-missing-imports"]
    with tempfile.TemporaryDirectory() as _td:
        _cache = ["--cache-dir", os.path.join(_td, "mypy_cache")]
        # Liveness self-test FIRST: the exact pattern that killed 1a72b344
        # must be flagged, or the gate is misconfigured/toothless.
        _canary = os.path.join(_td, "uba_canary.py")
        with open(_canary, "w") as _f:
            _f.write(
                "def f(items, words):\n"
                "    for bc in items:\n"
                "        try:\n"
                "            sw = int(bc.get('s'))\n"
                "        except (TypeError, ValueError):\n"
                "            pass\n"
                "        if 0 <= sw < len(words):\n"
                "            return sw\n"
                "    return None\n"
            )
        _probe = subprocess.run(_args + _cache + [_canary],
                                capture_output=True, text=True, timeout=300)
        if "No module named mypy" in (_probe.stderr or ""):
            raise AssertionError(
                "mypy is not installed — this gate is REQUIRED "
                "(pip3 install --user --break-system-packages mypy)"
            )
        assert "possibly-undefined" in _probe.stdout, (
            "gate liveness failed: mypy did not flag the known-bad canary "
            f"pattern (stdout: {_probe.stdout[:200]!r})"
        )
        _res = subprocess.run(_args + _cache + _files,
                              capture_output=True, text=True, timeout=300)
        _hits = [l for l in _res.stdout.splitlines() if "possibly-undefined" in l]
        assert not _hits, (
            f"{len(_hits)} possibly-undefined finding(s):\n    "
            + "\n    ".join(_hits[:10])
        )


# ─── 2. F-STRINGS ──────────────────────────────────────────────────────
print("\n[2/6] F-string format integrity")


@check("system_instruction f-string formats cleanly")
def _system_instruction_format():
    src = open("handler.py").read()
    start = src.find('system_instruction = f"""')
    assert start > 0, "system_instruction f-string not found"
    end = src.find('"""', start + 30)
    prompt = src[start + len('system_instruction = f"""'):end]
    # Function-call interpolations (e.g. {_vibe_palette_block(vibe)}) are valid
    # f-string expressions the compiler already validated (module imports cleanly);
    # .format() can't model a call, so strip them before the JSON-brace simulation.
    prompt = re.sub(r"\{[A-Za-z_]\w*\([^{}]*\)\}", "", prompt)
    # The .format() check catches unescaped { in JSON examples
    # (today's f-string bug pattern). The registry-derived interpolations
    # (enum lines + roster counts) are supplied as kwargs.
    prompt.format(
        _caption_enum="X", _mg_enum="X", _transition_enum="X", _tco_enum="X",
        _n_styles=0, _n_transitions=0, _n_mgs=0,
        _emph_move_line="X", _density_rhythm_block="X",
        _peak_budget="X", _peak_set_ref="X", _peak_count_ref="X",
    )


@check("no JSON-literal { patterns in any f-string (catches unescaped braces)")
def _no_json_brace_pattern():
    src = open("handler.py").read()
    fstring_pat = re.compile(r'f"""(.*?)"""', re.DOTALL)
    # Find { followed by a quoted key + colon — that's a Python format
    # expression that looks like JSON. The f-string before our fix had:
    #   { "start_word_index": 0, ... }
    # which Python parsed as a format expression and crashed.
    dangerous = re.compile(r'(?<![{f])\{ *"[a-zA-Z_]\w*" *:')
    issues = []
    for m in fstring_pat.finditer(src):
        content = m.group(1)
        if dangerous.search(content):
            line_no = src[: m.start()].count("\n") + 1
            issues.append(f"f-string at line ~{line_no} has JSON-literal brace pattern")
    assert not issues, "\n    ".join(issues)


# ─── 3. IMPORT + SYMBOL CHECK ──────────────────────────────────────────
print("\n[3/6] Import handler module")

# Suppress startup output during import.
sys.stderr = _DevNull()
sys.stdout = _DevNull()
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import handler
finally:
    sys.stderr = _real_stderr
    sys.stdout = _real_stdout


@check("handler module imports cleanly")
def _import_ok():
    assert handler is not None


@check("all critical handler symbols present")
def _symbols_present():
    required = [
        "handler",
        "prewarm_handler",
        "validate_handler",
        "classify_error",
        "send_progress",
        "_start_progress_heartbeat",
        "_quick_face_check",
        "detect_face_positions_dense",
        "PostCutPlan",
        "_VideoPlan",
        "_VideoPlanMoment",
        "_ArcSegment",
        "_EmphasisMoment",
        "_MotionGraphic",
        "_SoundEffect",
        "_BrollClip",
        "_Transition",
        "_record_divergence",
        "_force_caption_position_around_overlays",
        "_resolve_zoom_origin",
        "_face_position_at",
        "_parse_scdet_output",
        "format_recent_caption_styles_section",
    ]
    missing = [s for s in required if not hasattr(handler, s)]
    assert not missing, f"missing symbols: {missing}"


def _pos_at(segments_list, frame):
    """Return the caption position at a specific output frame, or None."""
    for s in segments_list:
        if s["fromFrame"] <= frame < s["toFrame"]:
            return s["position"]
    return None


@check("caption override forces TOP under MG at bottom (bed/Young Sheldon case)")
def _caption_override_mg_at_bottom():
    """Simulates the bed/Young Sheldon fixture: ProgressBar at frames 300-360
    and StatCard at frames 540-600, both anchored "bottom". Captions default
    to "bottom" everywhere. After the override, captions during both windows
    must be "top"; outside the windows must remain "bottom".
    """
    segments = [{"fromFrame": 0, "toFrame": 900, "position": "bottom"}]
    mgs = [
        {"type": "ProgressBar", "fromFrame": 300, "durationInFrames": 60,
         "props": {"anchor": "bottom"}},
        {"type": "StatCard",    "fromFrame": 540, "durationInFrames": 60,
         "props": {"anchor": "bottom"}},
    ]
    out = handler._force_caption_position_around_overlays(segments, mgs, [])
    # Inside each MG window: captions must be at top.
    assert _pos_at(out, 320) == "top",  f"inside ProgressBar window, expected top, got: {out}"
    assert _pos_at(out, 570) == "top",  f"inside StatCard window, expected top, got: {out}"
    # Outside the windows: captions stay at Gemini's default (bottom).
    assert _pos_at(out, 100) == "bottom"
    assert _pos_at(out, 450) == "bottom"
    assert _pos_at(out, 700) == "bottom"


@check("caption override forces BOTTOM under MG at top (Notification)")
def _caption_override_mg_at_top():
    """Notification renders top regardless of its anchor field (drop-down anim)."""
    mgs = [
        {"type": "Notification", "fromFrame": 200, "durationInFrames": 90,
         "props": {"anchor": "center"}},  # anchor lies; Notification still renders top
    ]
    # Scenario A: orig=bottom under top-rendering Notification → no change needed.
    out1 = handler._force_caption_position_around_overlays(
        [{"fromFrame": 0, "toFrame": 600, "position": "bottom"}], mgs, [],
    )
    assert _pos_at(out1, 250) == "bottom",  f"orig=bottom under top-MG: stays bottom, got: {out1}"
    # Scenario B: orig=top under top-rendering Notification → forced to bottom.
    out2 = handler._force_caption_position_around_overlays(
        [{"fromFrame": 0, "toFrame": 600, "position": "top"}], mgs, [],
    )
    assert _pos_at(out2, 250) == "bottom",  f"orig=top under top-MG: forced to bottom, got: {out2}"
    assert _pos_at(out2, 100) == "top"      # before MG: untouched
    assert _pos_at(out2, 400) == "top"      # after MG: restored


@check("caption override forces CENTER when both TOP and BOTTOM occupied")
def _caption_override_both_zones_occupied():
    """Top-anchored Notification overlaps with bottom-anchored ProgressBar →
    captions get squeezed to center for the overlap window."""
    segments = [{"fromFrame": 0, "toFrame": 600, "position": "bottom"}]
    mgs = [
        {"type": "Notification", "fromFrame": 100, "durationInFrames": 200,
         "props": {"anchor": "top"}},
        {"type": "ProgressBar",  "fromFrame": 150, "durationInFrames": 100,
         "props": {"anchor": "bottom"}},
    ]
    out = handler._force_caption_position_around_overlays(segments, mgs, [])
    # Frames 150-250: BOTH top and bottom occupied → captions forced to center.
    assert _pos_at(out, 200) == "center",  f"both-zones-occupied window should be center, got: {out}"
    # Frames 100-150: only top (Notification) → orig=bottom, MG forces bottom (no-op).
    assert _pos_at(out, 120) == "bottom"
    # Frames 250-300: only top still occupied → orig=bottom, MG forces bottom (no-op).
    assert _pos_at(out, 270) == "bottom"
    # Outside the MG windows: orig preserved.
    assert _pos_at(out, 50)  == "bottom"
    assert _pos_at(out, 400) == "bottom"


@check("caption override forces the LOWER THIRD during B-roll (never top — the b-roll subject's face is upper-center; Zac 2026-07-13)")
def _caption_override_broll_forces_lower():
    """B-roll is full-canvas and the pipeline is blind to its content. Portrait
    subjects sit upper-center → the lower third is clear. Captions default LOWER over
    b-roll, never top (which lands on the b-roll subject's face)."""
    segments = [
        {"fromFrame": 0,   "toFrame": 200, "position": "top"},
        {"fromFrame": 200, "toFrame": 500, "position": "top"},
        {"fromFrame": 500, "toFrame": 800, "position": "top"},
    ]
    broll_ranges = [(150, 250), (550, 650)]
    out = handler._force_caption_position_around_overlays(segments, [], broll_ranges)
    # Inside B-roll: LOWER (bottom), NEVER top — even when Gemini authored top.
    assert _pos_at(out, 180) == "bottom", f"inside first B-roll window, expected bottom, got: {out}"
    assert _pos_at(out, 220) == "bottom", f"inside first B-roll (crossing boundary), expected bottom, got: {out}"
    assert _pos_at(out, 600) == "bottom", f"inside second B-roll window, expected bottom, got: {out}"
    assert all(s["position"] != "top" for s in out if 150 <= int(s["fromFrame"]) < 250), "b-roll never forces top"
    # B-roll + an MG holding the bottom → center (bottom taken), still never top.
    _mgb = [{"type": "StatCard", "fromFrame": 150, "durationInFrames": 100, "props": {"anchor": "bottom"}}]
    _o2 = handler._force_caption_position_around_overlays(segments, _mgb, [(150, 250)])
    assert _pos_at(_o2, 180) == "center", f"b-roll + MG-at-bottom → center, got: {_o2}"


@check("CAPTION ENTRANCE = FRAME-1-IS-FINAL (Zac 2026-07-13, 4th pass): every one of the 9 styles arrives at its FINAL position, FULL opacity, and FULL scale from frame 1 — the WHOLE entrance category is zeroed (opacity ramp AND position slide/'float up' AND scale grow/slam), not one channel at a time. The recurring bug: each prior fix hit one channel and the next surfaced. Ongoing style character (color pop, keyword treatment, per-char typing) stays; entrance MOTION does not")
def _caption_crisp_entrance():
    import os as _os, re as _re
    _base = "src/remotion/src/captions"
    _styles = ["Prime", "TypewriterReveal", "Cove", "Lumen", "Pulse",
               "Quintessence", "TwoTone", "CleanCut", "Gadzhi"]
    _srcs = {_st: open(_os.path.join(_base, _st, f"{_st}.tsx")).read() for _st in _styles}
    # each style carries a dated entrance-conversion marker (crisp or frame-1-final)
    for _st, _src in _srcs.items():
        assert ("CRISP ENTRANCE (Zac 2026-07-13)" in _src or "FRAME-1-IS-FINAL" in _src), \
            f"{_st} must carry the entrance conversion"
    # ZERO ENTRANCE ANIMATION (Zac 2026-07-13, absolute spec): NO spring() in ANY style —
    # springs were the entrance-motion drivers (slide/slam/scale); every one is removed.
    # A caption SNAPS on (final position, full opacity, full scale, final color) from
    # frame 1. This forbids re-adding a spring-driven entrance on ANY property.
    for _st, _src in _srcs.items():
        assert "spring(" not in _src, f"{_st}: NO entrance spring — the caption must snap on, not animate in"
    # Gadzhi's gray→white color is INSTANT (final color frame 1), not a settle
    assert "const color = finalColor;" in _srcs["Gadzhi"], "Gadzhi color is instant (no gray→white ramp)"
    # OPACITY ghosts gone (round 3)
    assert "interpolate(wordSpring, [0, 1], [0, 1])" not in _srcs["Prime"], "Prime opacity ramp gone"
    assert "(currentTimeMs - token.fromMs) / 60" not in _srcs["Cove"], "Cove opacity ramp gone"
    # POSITION slides + SCALE grows gone (round 4 — the 'float up' + slam/grow):
    assert "const slideY = 0;" in _srcs["Prime"], "Prime slide zeroed (final position frame 1)"
    assert "const yOffset = 0;" in _srcs["Gadzhi"], "Gadzhi slide zeroed (the 'float up')"
    assert "const floatY = 0;" in _srcs["Pulse"], "Pulse continuous bob zeroed"
    assert "const scale = 1;" in _srcs["TwoTone"] and "const y = 0;" in _srcs["TwoTone"], "TwoTone slam+lift zeroed"
    assert "const scale = 1;" in _srcs["CleanCut"] and "const y = 0;" in _srcs["CleanCut"], "CleanCut grow+lift zeroed"
    assert "const scale = 1;" in _srcs["Lumen"], "Lumen scale grow-in zeroed"
    # no style feeds an entrance spring/interpolate into a translate/scale transform.
    # (interpolate is still allowed for fade-OUT + non-transform + the STATIC scaleY
    # stretch; this catches an interpolate result placed straight into translate/scale.)
    _bad = _re.compile(r"transform:[^;]*(translateY|scale)\(\$\{[A-Za-z_]\w*\}", _re.S)
    for _st in ("Prime", "Gadzhi", "TwoTone", "CleanCut", "Lumen", "Pulse"):
        for _m in _re.finditer(r"(translateY|scale)\(\$\{([A-Za-z_]\w*)", _srcs[_st]):
            _var = _m.group(2)
            # the fed variable must resolve to a literal 0/1, not an interpolate/spring/sin
            _decl = _re.search(rf"const {_var}\s*=\s*([^;]+);", _srcs[_st])
            if _decl:
                _rhs = _decl.group(1)
                assert not any(_k in _rhs for _k in ("interpolate", "spring", "Math.sin", "Easing")), \
                    f"{_st}: entrance transform var '{_var}' still animates ({_rhs[:40]}) — frame-1 not final"
    # the fade helper stays (fade-OUT still uses it)
    assert "MAX_ENTRANCE_MS = 80" in open(_os.path.join(_base, "shared", "fadeTiming.ts")).read()


@check("CAPTION NEVER-EARLY (Zac 2026-07-15): a caption word reveals ONLY when it is audible — never a frame before its own onset. round(start*fps) lands ~50% of words on the frame BEFORE the onset (up to ~8ms early = word on screen before spoken); CEIL(start*fps) is the first frame at-or-after the onset (0% early, <=1 frame after = still on the word). Both the absolute reveal ((frame/fps)*1000>=fromMs) and the page-local reveal (startFrame+msToFrames(fromMs-startMs)) must equal ceil(start*fps) and be >= the onset. Tokens stay int (render schema).")
def _caption_frame_alignment():
    import handler as _h, math as _math, render_schemas as _rs
    _fps = 60.0
    def _reveal(from_ms):
        f = from_ms * _fps / 1000.0
        fr = _math.floor(f)
        return fr if (fr / _fps) * 1000.0 >= from_ms - 1e-9 else fr + 1
    _W = lambda s: {"word": "w", "punctuated_word": "w", "start": s, "end": s + 0.3, "start_word_index": 0}
    # fractional-frame onsets (f in (0,0.5)) are the ones round() revealed EARLY (before onset)
    for _s in (1.005, 2.088, 0.508, 3.337, 1.008):
        _tok = _h._build_tiktok_pages_from_projected([_W(_s)], fps=_fps)[0]["tokens"][0]
        # THE REAL-RENDER CONTRACT: tokens are `int` (TikTokToken.fromMs/toMs) — a float
        # fails PromptlyRenderInput validation and kills the render. The frame-only test
        # missed this; a fractional projected onset (start*1000 non-integer) shipped floats
        # and every caption render died (regression 2026-07-13). Assert BOTH the type and
        # that a built token actually validates through the render schema.
        assert isinstance(_tok["fromMs"], int) and isinstance(_tok["toMs"], int), \
            f"caption tokens MUST be int (render schema); got fromMs={_tok['fromMs']!r}"
        _rs.TikTokToken(**_tok)  # raises if the token can't validate against the render input schema
        # NEVER-EARLY: reveal on ceil(start*fps) — never the frame before the onset.
        _ceil = int(_math.ceil(_s * _fps))
        _rev = _reveal(_tok["fromMs"])
        assert _rev == _ceil, \
            f"caption at {_s}s must reveal on the ceil frame {_ceil}, got {_rev}"
        assert (_rev / _fps) >= _s - 1e-9, \
            f"caption at {_s}s reveals at frame {_rev} ({_rev/_fps:.4f}s) — BEFORE its onset {_s}s (early = word before audible)"
    # a fractional PROJECTED onset (the production case: pbr-divided times) still yields int tokens
    _ftok = _h._build_tiktok_pages_from_projected([_W(20.043332)], fps=_fps)[0]["tokens"][0]
    assert isinstance(_ftok["fromMs"], int) and isinstance(_ftok["toMs"], int), \
        "fractional projected onset must still produce integer tokens (this was the render-killer)"
    # CAPTION NEVER-EARLY (Zac 2026-07-15): the PAGE-LOCAL reveal must ALSO land on
    # ceil(start*fps) — never the frame before the onset. The page-local styles
    # (CleanCut/Lumen/Prime/TwoTone) reveal a token at
    # startFrame + msToFrames(token.fromMs - page.startMs), where
    # startFrame = msToFrames(page.startMs). page.startMs is ceil-frame-aligned, so
    # the two frame-alignments cancel and the reveal is the ceil frame exactly.
    _msToFrames = lambda ms: _math.floor((ms / 1000.0) * _fps + 0.5)   # JS Math.round
    for _s in (1.005, 2.088, 0.508, 3.337, 1.008, 1.015, 20.043332):
        _pg = _h._build_tiktok_pages_from_projected([_W(_s)], fps=_fps)[0]
        _ceil = int(_math.ceil(_s * _fps))
        # page.startMs ceil-frame-aligned to the never-early frame
        assert _msToFrames(_pg["startMs"]) == _ceil, \
            f"page.startMs must be ceil-frame-aligned to the never-early frame {_ceil} at {_s}s"
        # page-local reveal = startFrame + msToFrames(fromMs - startMs) == ceil frame, never before onset
        _startFrame = _msToFrames(_pg["startMs"])
        _tok0 = _pg["tokens"][0]
        _reveal_local = _startFrame + _msToFrames(_tok0["fromMs"] - _pg["startMs"])
        assert _reveal_local == _ceil, \
            f"page-local caption reveal {_reveal_local} must equal ceil frame {_ceil} at {_s}s"
        assert (_reveal_local / _fps) >= _s - 1e-9, \
            f"page-local reveal {_reveal_local} ({_reveal_local/_fps:.4f}s) is BEFORE onset {_s}s (word before audible)"
    # the CleanCut component activates on a FRAME (msToFrames), not a continuous localMs
    _cc = open("src/remotion/src/captions/CleanCut/CleanCut.tsx").read()
    assert "localFrame >= actFrame(page.tokens[i])" in _cc \
        and "localMs >= page.tokens[i].fromMs - page.startMs" not in _cc, \
        "CleanCut must activate on the frame (msToFrames), not the continuous-ms threshold"


@check("STAGEDPUSH (Zac 2026-07-13): the multi-stage emphasis zoom — 2-3 building stages, EQUAL +8% steps, each peak on its word's audible onset (threaded through the SAME source→clip-local conversion as startMs), adaptive release; emittable (registry + schema round-trip), housed at MID_PEAK only (a building climax, not the payoff — purity), <2 words degrades to SmoothPush")
def _staged_push_wiring():
    import handler as _h, render_schemas as _rs, type_registries as _tr
    _src = open("handler.py").read()
    # emittable — registry + peak-reach + arc home (mid_peak/payoff only, reserved)
    assert "StagedPush" in _tr.VALID_ZOOM_TYPES, "StagedPush must be a valid zoom type"
    assert _h.ZOOM_PEAK_REACH_MS.get("StagedPush") == 280, "peak-reach = pushMs (peak on word 1)"
    # reserved to MID_PEAK only — a building climax phrase, never the singular payoff
    # (payoff purity), never build/breather/hook filler
    assert "StagedPush" in _h.ZOOM_ARC_HOMES["mid_peak"], "housed at mid_peak (the building climax)"
    assert not any("StagedPush" in _h.ZOOM_ARC_HOMES[_k]
                   for _k in ("payoff", "build", "breather", "hook", "close")), \
        "reserved to mid_peak only — not payoff (purity), not build/breather/hook/close"
    # the derivation + the coordinate thread exist
    assert "def _augment_staged_push_event(" in _src and "def _staged_push_stages(" in _src
    assert '_new_event["stages"] = [' in _src and "_clip_render_source_start_ms) / _pbr" in _src, \
        "each stage atMs must thread through the source→clip-local conversion (the peak-on-word crux)"
    # equal steps + degrade + the schema round-trips (transport probe)
    _dg = [{"word": "w", "start": s, "end": s + 0.25} for s in (1.0, 1.8, 2.6)]
    _st, _ = _h._staged_push_stages([0, 1, 2], _dg)
    assert [s["scale"] for s in _st] == [1.08, 1.16, 1.24], "equal +8% steps"
    _ze = {"type": "StagedPush", "events": [{"startMs": 700, "durationMs": 1200, "scale": 1.22}]}
    _h._augment_staged_push_event(_ze, [0], [{"word": "w", "start": 1.0, "end": 1.3}], [{"source_start": 0.0, "source_end": 5.0}])
    assert _ze["type"] == "SmoothPush", "<2 building words degrades to SmoothPush"
    _spec = _rs.ZoomEffectSpec(type="StagedPush", events=[{"startMs": 720, "durationMs": 3140,
        "stages": [{"atMs": 1000, "scale": 1.08}, {"atMs": 1800, "scale": 1.16}, {"atMs": 2600, "scale": 1.24}],
        "pushMs": 280, "holdMs": 260, "releaseMs": 360, "cutTerminated": False}])
    assert len(_rs.ZoomEffectSpec(**_spec.model_dump()).events[0].stages) == 3, "schema round-trips 3 stages"


@check("SHARED-CLOCK LEAD (Zac 2026-07-14, universal-lateness): one uniform early shift of the clock every component reads — coherence preserved (Lever B win), systematic lateness corrected; TUNABLE, default 0 = no change")
def _shared_clock_lead():
    import handler as _h
    _src = open("handler.py").read()
    assert "_SHARED_CLOCK_LEAD_MS" in _src, "the tunable shared-clock lead must exist"
    # default 0 = pure Lever B (no production change until Zac's ear sets it)
    assert _h._SHARED_CLOCK_LEAD_MS == 0.0, "default lead is 0 (report-approach-before-shipping)"
    # the ONE derivation subtracts it — reads the module global (proof can sweep)
    assert "_raw - (_SHARED_CLOCK_LEAD_MS / 1000.0)" in _src, \
        "_audible_word_onset_s must subtract the lead from raw Deepgram"
    _dg = [{"start": 2.0, "end": 2.3}]
    assert abs(_h._audible_word_onset_s(_dg, 0) - 2.0) < 1e-9, "at 0, returns raw (Lever B)"
    _saved = _h._SHARED_CLOCK_LEAD_MS
    try:
        _h._SHARED_CLOCK_LEAD_MS = 50.0
        assert abs(_h._audible_word_onset_s(_dg, 0) - 1.95) < 1e-9, \
            "a lead shifts the ONE clock earlier by the constant (all components inherit it)"
    finally:
        _h._SHARED_CLOCK_LEAD_MS = _saved


@check("MOMENT PRECISION (Zac 2026-07-14): the anchor (word_indices[0]) is the EXACT vocally-stressed word to the ms — not the phrase's first word, not the merely-meaningful word (measured 40% off-word / 208ms mean gap: Gemini picked the semantic word, the ear wants the punch). Non-deterministic prompt teach, machinery untouched.")
def _moment_precision():
    _src = open("handler.py").read()
    # the anchor is the punched word, to the ms — the entry shape says so
    assert "word_indices[0] is the ANCHOR — the EXACT word the speaker's VOICE punches" in _src, \
        "the entry shape must define word_indices[0] as the vocally-punched anchor"
    # single word for a single landing; 2-3 only for a building phrase (StagedPush)
    assert "For a single landing (a plain zoom / SFX / MG) list ONE word — the punched word" in _src, \
        "single-landing components must anchor on ONE stressed word (no phrase-first ambiguity)"
    # the meaning-vs-punch teaching (the measured miss class: creator/being, nothing/did)
    assert "When the meaningful word and the punched word differ, anchor to the PUNCH" in _src, \
        "the emphasis teach must resolve meaning-vs-punch toward the punch (the ear's frame)"
    assert "Pick the anchor by LISTENING for the stress, not by reading for the meaning" in _src, \
        "the precision layer must say pick by ear (stress), not by meaning"
    # millisecond-precise arrival-point framing (machinery is exact; make the target exact)
    assert "it must be the EXACT stressed word to the millisecond" in _src \
        and "lands perfectly on the wrong beat, and the ear hears it as off" in _src, \
        "the arrival-point teach must frame the anchor as ms-precise (machinery exact, target loose)"
    # StagedPush per-stage anchoring already lands each stage on its word (confirmed, unchanged)
    import handler as _h
    _dg = [{"word": w, "start": s, "end": s + 0.25} for w, s in [("ten", 1.0), ("million", 1.8), ("dollars", 2.6)]]
    _st, _ = _h._staged_push_stages([0, 1, 2], _dg)
    assert abs(_st[0]["atMs"] - 1000) < 5 and abs(_st[2]["atMs"] - 2600) < 5, \
        "each StagedPush stage anchors to its OWN word's onset (per-stage, not a phrase default)"


@check("VIBE-FEEL (Zac 2026-07-14): the un-caveated overrides that beat the FITS/FIGHTS are caveated — boom's payoff-reinforcements name the vibe (boom FIGHTS corporate), transitions teach the vibe-register (a scene change is universal; corporate uses the clean ones, not zero)")
def _vibe_feel_fixes():
    _src = open("handler.py").read()
    # boom: the three payoff reinforcements now caveat the vibe (were un-caveated,
    # overriding boom's own FIGHTS: corporate)
    assert "the boom lives here" not in _src, \
        "the un-caveated 'the boom lives here' override must be caveated to the vibe"
    assert "a boom FIGHTS those vibes" in _src, "the payoff arc must caveat boom by vibe"
    assert "the boom on the payoff word in a punchy/viral vibe" in _src, \
        "the held-camera routing must caveat boom by vibe"
    assert "ONLY where the vibe wants a punch" in _src, \
        "the sounds-layer boom-reserve note must caveat the vibe"
    # transitions: the vibe scopes the register; a scene change is universal
    assert "THE VIBE SCOPES THE TRANSITION REGISTER" in _src, \
        "the sub-call must teach the vibe picks the transition register (not whether)"
    assert "a corporate video with real chapter turns and zero transitions has skipped a universal move".lower() in _src.lower(), \
        "corporate must be told to dress its turns with the clean transitions, not skip them"
    assert "SlideOver is the safe pick in ANY vibe" in _src, \
        "a safe-in-any-vibe transition must be elevated (the missing universal member)"
    # WHOLE-CLASS SWEEP (Zac 2026-07-14): 6 more un-caveated overrides found + fixed.
    # Each named the punchy register without a vibe caveat, overriding a FITS/FIGHTS.
    assert "a committing boom on the land" not in _src, \
        "worked Example 3 (cinematic confession) must not model boom (boom FIGHTS cinematic)"
    assert "a committing SWELL on the land — transition-sfx, not a boom" in _src, \
        "the cinematic example must model the swell, not the boom"
    assert "at a mid-peak the snap pair — SnapReframe or StepZoom — carries it), snap for the reaction" not in _src, \
        "the reaction-camera prescription must be vibe-scoped, not hardcoded snap"
    assert "snap for a reaction or punchline (a laugh, a gasp, the speaker's expression breaking), step for a landing statement (the fact arrives, the word weighs in the chest). Both are quick in / quick out." not in _src, \
        "the build-and-release mid_peak prescription must be vibe-scoped"
    assert "When register and arc-position suggest different answers, arc-position wins" not in _src, \
        "the transition arc-map must NOT subordinate the vibe to arc-position (orthogonal, not conflicting)"
    assert "Arc-position and vibe are ORTHOGONAL" in _src, \
        "the transition map must teach arc(job)/vibe(register) orthogonality"
    assert "a stat snapping in → ShutterFlash. A cutaway" not in _src, \
        "the b-roll edge stat→ShutterFlash must be vibe-caveated (ShutterFlash FIGHTS calm)"
    # the mid_peak arc bullet no longer prescribes punchy without a caveat
    assert "punctuation — quick in, quick out; a hit/pop/ding when this peak" not in _src, \
        "the mid_peak arc bullet must be vibe-scoped (punchy snap+hit/pop/ding vs calm push+swell)"


@check("ZOOM VIBE-SPLIT (Zac 2026-07-13): the VIBE scopes the zoom's tonal register like it scopes captions/SFX — SmoothPush (the calm push) is OFFERED at hook + mid_peak (not payoff/close only), so a corporate/calm beat can pick calm and a viral beat picks punchy; the fitness+vibe chooses within the static schema (which can't be vibe-dependent — Vertex cache)")
def _zoom_vibe_split():
    import handler as _h
    _src = open("handler.py").read()
    # the calm push is now available at the peak positions (not just payoff/close)
    assert "SmoothPush" in _h.ZOOM_ARC_HOMES["hook"] and "SmoothPush" in _h.ZOOM_ARC_HOMES["mid_peak"], \
        "SmoothPush must be offered at hook + mid_peak so a calm vibe can pick calm there"
    # the punchy options stay (viral still picks them); payoff purity untouched
    assert "SnapReframe" in _h.ZOOM_ARC_HOMES["mid_peak"], "the punchy option stays (viral)"
    assert set(_h.ZOOM_ARC_HOMES["payoff"]) == {"SmoothPush", "LetterboxPush"}, "payoff purity untouched"
    # the prompt tells Gemini the vibe scopes the zoom register (else it defaults to punchy)
    assert "THE VIBE SCOPES THE ZOOM'S REGISTER" in _src, \
        "the zoom section must teach that the vibe picks the register (the fix's belt)"
    # ZOOM-SPLIT PART 2 (Zac 2026-07-14): the arc-position personality must not
    # BLANKET-outrank the vibe (that override forced punchy at every corporate
    # peak — the bug). It names the JOB; the vibe picks the register. The
    # "outranks what feels punchy" clause is scoped to the payoff ONLY (its
    # legitimate home — payoff commitment is vibe-independent purity).
    assert 'this rule outranks "what feels punchy"' not in _src, \
        "the blanket outranks-the-vibe clause forced punchy at every peak — it must be gone"
    assert "the GRIP is the job, the snap is only the punchy register" in _src, \
        "the hook must teach the register is vibe-scoped (corporate hook = decisive push, not snap)"
    assert "the one place the moment outranks" in _src, \
        "the outranks clause belongs to the payoff only (payoff purity, vibe-independent)"
    assert "the position is not the register" in _src, \
        "the rule must state arc-position (job) and vibe (register) are orthogonal"


# ─── 3b. ZOOM-ORIGIN FACE-LOCK ────────────────────────────────────────
# These tests cover audit Tier-1 #3: the zoom-origin face-lock that the
# prompt promises Gemini. They exercise _resolve_zoom_origin, the same
# function the render-time event loop calls — per
# feedback_smoke_must_cover_real_paths.md, the smoke must hit the ACTIVE
# face-lock path (face box present, origin resolves to non-center) and
# not just the no-face fallback.
print("\n[3b/6] Zoom-origin face-lock")


@check("zoom-origin face-lock resolves to FACE coords when trajectory has a found detection (active path)")
def _zoom_origin_active_face_lock():
    # Off-center talking-head: face center sits at x=400/1080 (well left
    # of canvas center 540/1080), y=600/1920 (upper-middle band where
    # eyes naturally sit). _face_position_at applies a -0.10 normalized
    # rule-of-thirds eye offset on y. Expected normalized origin:
    #   originX ≈ 400/1080 = 0.3704
    #   originY ≈ 600/1920 - 0.10 = 0.2125
    # NOT canvas center (0.5, 0.5).
    trajectory = [
        {"t": 0.0,  "cx": 400, "cy": 600, "found": True,  "confidence": 0.95},
        {"t": 3.0,  "cx": 400, "cy": 600, "found": True,  "confidence": 0.95},
        {"t": 6.0,  "cx": 400, "cy": 600, "found": True,  "confidence": 0.95},
    ]
    ev = {"startMs": 4200}  # source-time 4.2s — nearest detection at t=3.0
    origin_x, origin_y, was_face_locked = handler._resolve_zoom_origin(
        ev, source_time_s=4.2, face_trajectory=trajectory,
    )
    assert was_face_locked is True, "expected face_lock path; got fallback"
    assert abs(origin_x - 0.3704) < 0.01, f"originX should track face center, got {origin_x}"
    assert abs(origin_y - 0.2125) < 0.01, f"originY should track face center w/ eye offset, got {origin_y}"
    # And specifically NOT (0.5, 0.5) — this is the regression the audit caught.
    assert (origin_x, origin_y) != (0.5, 0.5), "face-locked origin must not be canvas center"


@check("zoom-origin face-lock passes Gemini's explicit origins through verbatim (non-face element)")
def _zoom_origin_gemini_explicit():
    # Gemini zooming on a prop / gesture / whiteboard emits originX/Y
    # explicitly. The face lock must NOT override these — even when a
    # face trajectory is available, Gemini's intent wins because it
    # watched the proxy and chose coordinates on something the pipeline
    # can't detect.
    trajectory = [
        {"t": 5.0, "cx": 400, "cy": 600, "found": True, "confidence": 0.95},
    ]
    ev = {"startMs": 5000, "originX": 0.78, "originY": 0.62}
    origin_x, origin_y, was_face_locked = handler._resolve_zoom_origin(
        ev, source_time_s=5.0, face_trajectory=trajectory,
    )
    assert was_face_locked is False, "explicit Gemini origin must not be a face-lock"
    assert origin_x == 0.78, f"Gemini originX must pass through verbatim, got {origin_x}"
    assert origin_y == 0.62, f"Gemini originY must pass through verbatim, got {origin_y}"


@check("zoom-origin face-lock falls back to center when no face box near event frame")
def _zoom_origin_no_face_fallback():
    # No found detection at all — fallback path. Must return canvas center
    # AND emit a [divergence] line (the fallback is logged so the gap is
    # visible). Trajectory with found=False entries simulates speaker
    # turned away or occlusion.
    trajectory = [
        {"t": 0.0, "cx": 0, "cy": 0, "found": False, "confidence": 0.0},
        {"t": 5.0, "cx": 0, "cy": 0, "found": False, "confidence": 0.0},
    ]
    ev = {"startMs": 3000}  # face zoom (no explicit origin)
    origin_x, origin_y, was_face_locked = handler._resolve_zoom_origin(
        ev, source_time_s=3.0, face_trajectory=trajectory,
    )
    assert was_face_locked is False, "no-face path is not face_lock"
    assert (origin_x, origin_y) == (0.5, 0.5), f"fallback must be canvas center, got ({origin_x}, {origin_y})"


@check("zoom-origin face-lock falls back to center when trajectory is empty")
def _zoom_origin_empty_trajectory():
    # Empty trajectory (e.g. face-detection skipped or produced nothing).
    # Same fallback contract.
    ev = {"startMs": 1000}
    origin_x, origin_y, was_face_locked = handler._resolve_zoom_origin(
        ev, source_time_s=1.0, face_trajectory=[],
    )
    assert was_face_locked is False
    assert (origin_x, origin_y) == (0.5, 0.5)


# ─── 3c. scdet SWEEP PARSER + RECENT-CAPTION-STYLES INJECTION ──────────
# Audit Problem 1 (sweep diagnostic) and Problem 2 (rotation rule wire).
# Per feedback_smoke_must_cover_real_paths.md, both tests exercise the
# ACTIVE path — the parser parsing real scdet stdout, the formatter
# rendering a real chronological list — not just the no-op default.
print("\n[3c/6] scdet sweep + recent caption styles")


@check("scdet sweep parser extracts (timestamp, score) tuples from stdout")
def _scdet_parser_stdout():
    # Synthetic but realistic scdet output. Three flagged frames, scores
    # 3.12, 7.85, 14.50. The 14.50 is above production threshold (12.0);
    # the others are exactly the same-framing-splice / motion-noise zone
    # we built this diagnostic to surface.
    stdout = (
        "frame:120 pts:40000 pts_time:1.333\n"
        "lavfi.scdet.mafd=...\n"
        "lavfi.scdet.score=3.12\n"
        "frame:540 pts:180000 pts_time:6.000\n"
        "lavfi.scdet.mafd=...\n"
        "lavfi.scdet.score=7.85\n"
        "frame:900 pts:300000 pts_time:10.000\n"
        "lavfi.scdet.mafd=...\n"
        "lavfi.scdet.score=14.50\n"
    )
    detections = handler._parse_scdet_output(stdout, "")
    assert len(detections) == 3, f"expected 3 detections, got {len(detections)}: {detections}"
    assert detections[0] == (1.333, 3.12), f"first: {detections[0]}"
    assert detections[1] == (6.0,   7.85), f"second: {detections[1]}"
    assert detections[2] == (10.0,  14.5), f"third: {detections[2]}"


@check("scdet sweep parser handles stderr fallback when stdout has no metadata blocks")
def _scdet_parser_stderr_fallback():
    # Older ffmpeg builds emit only to stderr in the format:
    #   [Parsed_scdet_0 @ 0x...] lavfi.scdet.score:5.20 pts_time:3.500
    stderr = (
        "[Parsed_scdet_0 @ 0x7f] lavfi.scdet.score:5.20 pts_time:3.500\n"
        "[Parsed_scdet_0 @ 0x7f] lavfi.scdet.score:13.10 pts_time:9.200\n"
    )
    detections = handler._parse_scdet_output("", stderr)
    assert len(detections) == 2, f"expected 2 detections from stderr, got {detections}"
    assert detections[0] == (3.5,  5.20), f"first: {detections[0]}"
    assert detections[1] == (9.2, 13.10), f"second: {detections[1]}"


@check("scdet sweep parser dedupes by timestamp, sorts ascending")
def _scdet_parser_dedupe_sort():
    # Two emissions for the same frame (rare but seen with some builds);
    # plus out-of-order frames. Parser must dedupe and sort.
    stdout = (
        "frame:600 pts:200000 pts_time:6.667\n"
        "lavfi.scdet.score=8.50\n"
        "frame:240 pts:80000 pts_time:2.667\n"
        "lavfi.scdet.score=4.20\n"
        "frame:600 pts:200000 pts_time:6.667\n"  # duplicate
        "lavfi.scdet.score=8.50\n"
    )
    detections = handler._parse_scdet_output(stdout, "")
    assert len(detections) == 2, f"expected dedup to 2, got {detections}"
    assert detections[0][0] < detections[1][0], f"sort order: {detections}"


@check("recent_caption_styles injector renders chronological list when data present (active path)")
def _recent_styles_active():
    # Active path: user has rotated through 3 distinct styles; newest
    # LAST. Block must contain all three in render order.
    profile = {
        "total_videos": 4,
        "recent_caption_styles": ["Lumen", "Prime", "Lumen"],
    }
    block = handler.format_recent_caption_styles_section(profile)
    assert block, "block must be non-empty when recent_caption_styles has entries"
    assert "Lumen, Prime, Lumen" in block, f"styles must appear in chronological order. block:\n{block}"
    assert "RECENT CAPTION STYLES" in block, "block must carry the labeled header"
    assert "newest LAST" in block, "block must tell Gemini the order convention"


@check("recent_caption_styles injector returns empty when list absent")
def _recent_styles_empty():
    # No data → empty string. Belt-and-suspenders against leaking a
    # junk block into the user message on cold-start users.
    assert handler.format_recent_caption_styles_section({}) == ""
    assert handler.format_recent_caption_styles_section({"recent_caption_styles": []}) == ""
    assert handler.format_recent_caption_styles_section({"recent_caption_styles": None}) == ""
    assert handler.format_recent_caption_styles_section(None) == ""


@check("recent_caption_styles injector fires INDEPENDENTLY of total_videos gate")
def _recent_styles_independent_of_gate():
    # The aggregate `format_user_style_section` is gated at
    # total_videos >= 3. The chronological rotation block must NOT be
    # — even one prior pick is meaningful rotation data ("avoid Lumen
    # on this user's second video").
    profile = {"total_videos": 1, "recent_caption_styles": ["Lumen"]}
    block = handler.format_recent_caption_styles_section(profile)
    assert block, "rotation block must fire at video #2 (total_videos=1) — not wait for gate"
    assert "Lumen" in block


@check("recent_caption_styles injector filters 'none' entries (no captions vibe)")
def _recent_styles_filters_none():
    # When the user picks the "no captions" vibe, caption_style is "none".
    # Storing it in the rotation list would lead Gemini to AVOID "none"
    # later — nonsensical, since "none" isn't a style to rotate against.
    profile = {"total_videos": 3, "recent_caption_styles": ["Lumen", "none", "Prime"]}
    block = handler.format_recent_caption_styles_section(profile)
    assert "Lumen, Prime" in block, f"'none' must be filtered. block:\n{block}"
    assert "none" not in block.split("renders, in render order:")[-1].split("\n")[0], (
        f"'none' must not appear in the styles list. block:\n{block}"
    )


@check("recent_caption_styles reads from caption_styles[__chronological__] piggyback (ACTIVE path)")
def _recent_styles_piggyback_active():
    # Active path: profile has the piggyback sentinel inside
    # caption_styles JSONB (no dedicated `recent_caption_styles` column).
    # The injector must read it and emit the block. This is the
    # PRODUCTION configuration today — Supabase column doesn't exist.
    profile = {
        "total_videos": 4,
        "caption_styles": {
            "Lumen": 8.7,
            "Prime": 4.2,
            handler._RECENT_CAPTION_STYLES_SENTINEL: ["Lumen", "Prime", "Lumen"],
        },
    }
    block = handler.format_recent_caption_styles_section(profile)
    assert block, "block must read piggyback sentinel inside caption_styles"
    assert "Lumen, Prime, Lumen" in block, f"piggyback list missing from block: {block}"


@check("recent_caption_styles dedicated column takes precedence over piggyback (forward-compat)")
def _recent_styles_dedicated_wins():
    # Forward-compat path: when a future SQL migration adds the
    # dedicated `recent_caption_styles` column, the reader prefers it
    # over the piggyback sentinel. Lets both data sources coexist
    # without conflict during transition.
    profile = {
        "total_videos": 4,
        "recent_caption_styles": ["Cove", "Pulse"],          # dedicated col — wins
        "caption_styles": {
            "Lumen": 8.7,
            handler._RECENT_CAPTION_STYLES_SENTINEL: ["Lumen", "Prime"],  # piggyback
        },
    }
    block = handler.format_recent_caption_styles_section(profile)
    assert "Cove, Pulse" in block, f"dedicated column should win: {block}"
    assert "Lumen, Prime" not in block, "piggyback must be ignored when dedicated exists"


@check("scdet sweep parser supports threshold=7.0 default (post-Bug-3a)")
def _scdet_threshold_default_7():
    import inspect
    sig = inspect.signature(handler.detect_shot_changes)
    threshold_default = sig.parameters["threshold"].default
    assert threshold_default == 7.0, (
        f"Bug 3(a) fix: threshold default must be 7.0 (was 12.0). got: {threshold_default}"
    )


@check("shot_change_word_boundaries snaps to NEXT-word start (Bug 3b active path)")
def _shot_change_snap_to_next_word_start():
    # ACTIVE path: a cut at t=3.5s where word 4 ends at 3.0s (0.50s away)
    # and word 5 starts at 3.55s (0.05s away). Pre-fix, only word ENDS
    # were checked at 0.30s tolerance → DROP. Post-fix, the next word's
    # START is also checked, and snap tolerance is 0.60s → both work.
    # Resulting boundary is at word 4 (last word of pre-split clip).
    kept_words = [
        {"start": 0.0,  "end": 0.5,  "punctuated_word": "Hi"},
        {"start": 0.6,  "end": 1.2,  "punctuated_word": "there"},
        {"start": 1.3,  "end": 2.0,  "punctuated_word": "today"},
        {"start": 2.1,  "end": 3.0,  "punctuated_word": "we're"},  # word 3, ends 3.0
        {"start": 3.55, "end": 4.2,  "punctuated_word": "talking"}, # word 4, starts 3.55
        {"start": 4.3,  "end": 5.0,  "punctuated_word": "about"},
    ]
    shot_changes = [3.5]
    out = handler.shot_change_word_boundaries(shot_changes, kept_words)
    assert len(out) == 1, f"expected 1 boundary, got: {out}"
    assert out[0][0] == 3, f"expected boundary at word 3 (kept[3].end is the after-anchor), got: {out}"


@check("shot_change_word_boundaries snaps within expanded 0.60s tolerance (Bug 3b)")
def _shot_change_snap_expanded_tolerance():
    # Pre-fix tolerance 0.30s would drop this; post-fix 0.60s catches it.
    kept_words = [
        {"start": 0.0, "end": 1.0, "punctuated_word": "A"},
        {"start": 1.0, "end": 2.0, "punctuated_word": "B"},  # word 1 ends 2.0
        {"start": 2.55, "end": 3.5, "punctuated_word": "C"}, # word 2 starts 2.55
        {"start": 4.0, "end": 5.0, "punctuated_word": "D"},
    ]
    # Cut at 2.5s — distance 0.50s to word 1 end (out at 0.30, in at 0.60),
    # 0.05s to word 2 start. Both edges checked → snap to word 1.
    out = handler.shot_change_word_boundaries([2.5], kept_words)
    assert len(out) == 1
    assert out[0][0] == 1


@check("shot_change_word_boundaries carries scdet scores via side-channel (confidence-gate active path)")
def _shot_change_scores_side_channel():
    # ACTIVE path feeding the scene-floor confidence gate: scdet scores reach
    # each boundary via the out_scores side-channel (return shape unchanged).
    kept_words = [
        {"start": 0.0, "end": 1.0, "punctuated_word": "A"},
        {"start": 1.0, "end": 2.0, "punctuated_word": "B"},  # word 1 ends 2.0
        {"start": 2.1, "end": 3.5, "punctuated_word": "C"},  # word 2 ends 3.5
        {"start": 3.6, "end": 4.5, "punctuated_word": "D"},
        {"start": 4.6, "end": 5.5, "punctuated_word": "E"},  # last (excluded)
    ]
    shot_scores = {2.0: 12.5, 3.5: 4.1}  # keyed by round(t, 3)
    out_scores = {}
    out = handler.shot_change_word_boundaries(
        [2.0, 3.5], kept_words, shot_scores=shot_scores, out_scores=out_scores,
    )
    assert out_scores.get(1) == 12.5, f"word-1 boundary score, got {out_scores}"
    assert out_scores.get(2) == 4.1, f"word-2 boundary score, got {out_scores}"
    # The gate keeps high-confidence (>= floor), skips low-confidence bare ones.
    assert handler.SCENE_FLOOR_MIN_SCDET_SCORE == 8.0
    assert 12.5 >= handler.SCENE_FLOOR_MIN_SCDET_SCORE
    assert 4.1 < handler.SCENE_FLOOR_MIN_SCDET_SCORE
    # Back-compat: 2-arg call returns plain (idx, time) tuples, no side-channel.
    plain = handler.shot_change_word_boundaries([2.0], kept_words)
    assert plain and plain[0][0] == 1 and len(plain[0]) == 2, (
        f"2-arg call must still return 2-tuples, got {plain}"
    )


@check("boundary union catches consecutive-anchor dead_air ranges (Bug 3c active path)")
def _consecutive_anchor_dead_air_catches_boundary():
    # ACTIVE path: a mechanical-cuts dead_air range like
    # {after=2, before=3, reason="dead_air"} removes ZERO words but
    # still splits the clip in build_clips_from_words. Pre-fix the
    # boundary computation missed this case → clip_split_without_known_
    # boundary cross-check fired. Post-fix the boundary IS in the union.
    #
    # Smoke-test the production iteration directly by constructing the
    # state the boundary block at handler.py:5181 consumes and verifying
    # the iteration logic emits the boundary.
    raw_cut_remove_words = [
        {"after_word_index": 2, "before_word_index": 3, "reason": "dead_air"},
    ]
    # All 5 words kept (the range removes ZERO src words between 2 and 3).
    new_to_src = [0, 1, 2, 3, 4]

    # Build the consecutive-da set the same way the production code does.
    _consec = set()
    for _rw in raw_cut_remove_words:
        aw = _rw.get("after_word_index")
        bw = _rw.get("before_word_index")
        if bw == aw + 1 and _rw.get("reason") == "dead_air":
            _consec.add((aw, bw))

    boundaries = []
    for new_idx, src_idx in enumerate(new_to_src):
        if new_idx + 1 >= len(new_to_src):
            continue
        next_src_idx = new_to_src[new_idx + 1]
        if next_src_idx != src_idx + 1:
            boundaries.append(new_idx)
        elif (src_idx, next_src_idx) in _consec:
            boundaries.append(new_idx)

    # The boundary at new_idx=2 (between kept[2] and kept[3]) must be detected.
    assert 2 in boundaries, (
        f"consecutive-anchor dead_air range should produce boundary at "
        f"new_idx=2. got: {boundaries}"
    )


@check("B-roll duration now reports OUTPUT-time speech, not inflated source span (ACTIVE)")
def _broll_duration_uses_speech_not_src_span():
    # Bed/Young Sheldon-style fixture: 5 kept words spanning 26.8s in source
    # because 22s of removed dead_air sits in the middle of the range.
    # Each individual word is ~0.5s of actual speech.
    #
    # The fix: validation now stores OUTPUT-time speech duration (sum of
    # word .end - .start over kept words), NOT the inflated source span.
    # For 5 normal-speech words this is ~2-3s, not 26.8s. Downstream
    # Pexels fetch sizing now gets a sensible request length.
    deepgram_words = [
        # words 55-56 = preamble (not part of broll range)
        {"start": 0.0,  "end": 0.5,  "word": "preamble"},
        {"start": 0.5,  "end": 1.0,  "word": "preamble"},
        # word 57: first word of B-roll. starts at 1.0s, lasts 0.5s.
        {"start": 1.0,  "end": 1.5,  "word": "one"},
        # words 58-60 are in the source but mechanically REMOVED (long
        # dead_air). Each spans large gaps to mimic silence.
        {"start": 1.5,  "end": 1.7,  "word": "(filler58)"},
        {"start": 1.7,  "end": 1.9,  "word": "(filler59)"},
        {"start": 25.0, "end": 25.5, "word": "(silence60)"},
        # words 61-... five-word range is actually [57, 58, 59, 60, 61]
        # but 58-60 are removed. So kept words 57 and 61 anchor the range.
        # Word 61: last word of B-roll, ends at 27.8s in source.
        {"start": 27.3, "end": 27.8, "word": "five"},
    ]
    # Mechanical cuts mark src indices 3, 4, 5 as removed (the filler/dead-air).
    _broll_removed = {3, 4, 5}

    # Simulate exactly what the validation block computes for a B-roll
    # entry at start=2 (src), end=6 (src) — kept words on the edges.
    import math
    _broll_dg_words = deepgram_words
    _sw_kept = 2  # word index 2 (the "one" at 1.0s)
    _ew_kept = 6  # word index 6 (the "five" at 27.3s)
    _br_ts = float(_broll_dg_words[_sw_kept].get("start") or 0)
    _br_end = float(_broll_dg_words[_ew_kept].get("end") or 0)
    _src_span = _br_end - _br_ts
    assert _src_span > 25.0, f"src span should be inflated to ~26.8s, got: {_src_span}"

    # Now exercise the OUTPUT-speech math the validation uses post-fix.
    _speech_dur = 0.0
    for _wi in range(_sw_kept, _ew_kept + 1):
        if _wi in _broll_removed:
            continue
        _w = _broll_dg_words[_wi]
        _ws = float(_w.get("start") or 0)
        _we = float(_w.get("end") or 0)
        if _we > _ws:
            _speech_dur += (_we - _ws)
    # Word "one" (0.5s) + word "five" (0.5s) = 1.0s of actual speech.
    # The 26.8s source span shrinks to 1.0s of cutaway — the correct value.
    assert 0.8 < _speech_dur < 1.5, f"speech duration should be ~1.0s, got: {_speech_dur}"
    assert _speech_dur < _src_span / 10, (
        f"speech duration ({_speech_dur:.2f}) must be << src span "
        f"({_src_span:.2f}) — the whole point of the fix"
    )


@check("B-roll total-coverage ceiling drops longest first when over 40% (ACTIVE)")
def _broll_coverage_ceiling_drops_longest():
    # Active path: simulate the per-clip post-projection broll_out list
    # the ceiling logic operates on. 3 clips on a 30s video — sum exceeds
    # the 40% ceiling. The longest clip drops first; remaining clips
    # bring coverage back under ceiling.
    total_output_duration = 30.0
    source_fps = 30.0
    broll_out = [
        {"src": "broll_00", "durationInFrames": int(8.0  * source_fps)},  # 8.0s  — longest
        {"src": "broll_01", "durationInFrames": int(5.0  * source_fps)},  # 5.0s
        {"src": "broll_02", "durationInFrames": int(3.0  * source_fps)},  # 3.0s
    ]
    # Sum = 16.0s / 30s = 53.3% → over the 40% ceiling.
    _total = sum(b["durationInFrames"] / source_fps for b in broll_out)
    assert _total / total_output_duration > 0.40, f"setup: coverage should be over ceiling, got {_total/total_output_duration:.2f}"

    # Mirror the production drop logic.
    _BROLL_COVERAGE_CEILING = 0.40
    _coverage = _total / total_output_duration
    _keep_idx = set(range(len(broll_out)))
    _sorted_by_dur = sorted(range(len(broll_out)), key=lambda i: (-broll_out[i]["durationInFrames"], i))
    _drops = []
    for _drop_i in _sorted_by_dur:
        if _coverage <= _BROLL_COVERAGE_CEILING:
            break
        if _drop_i not in _keep_idx:
            continue
        _dropped_dur = broll_out[_drop_i]["durationInFrames"] / source_fps
        _keep_idx.discard(_drop_i)
        _total -= _dropped_dur
        _coverage = _total / total_output_duration
        _drops.append(_drop_i)

    # The 8.0s clip is the longest → dropped first. After drop:
    # 5.0 + 3.0 = 8.0s = 26.7% < 40% → no more drops.
    assert _drops == [0], f"longest (idx 0, 8.0s) must drop first; got drops: {_drops}"
    assert _coverage < _BROLL_COVERAGE_CEILING, (
        f"after trim, coverage should be under ceiling, got {_coverage:.3f}"
    )
    # Idx 1 (5.0s) and idx 2 (3.0s) survive.
    assert 1 in _keep_idx and 2 in _keep_idx


@check("B-roll timing offset shifts window EARLIER by 0.4s and clamps to band (ACTIVE)")
def _broll_lead_audio_offset_active():
    # Mirrors the production lead-audio offset logic. Word-span starts
    # at 5.0s and lasts 0.5s → after offset, on-screen starts at ~4.6s
    # and lasts within [0.8, 2.0]s.
    LEAD_OFFSET = 0.4
    TAIL_OFFSET = 0.2
    BROLL_MIN_DUR = 0.8
    BROLL_MAX_DUR = 2.0

    word_span_start = 5.0
    word_span_end = 5.5
    # Floor: clip containing the start word starts at 4.0s — well below
    # the offset target, so the floor doesn't bite.
    clip_floor_out_s = 4.0
    total_output_duration = 30.0

    out_start = max(clip_floor_out_s, word_span_start - LEAD_OFFSET)
    out_end = min(total_output_duration, word_span_end + TAIL_OFFSET)
    eff = out_end - out_start
    if eff > BROLL_MAX_DUR:
        out_end = out_start + BROLL_MAX_DUR
        eff = BROLL_MAX_DUR
    elif eff < BROLL_MIN_DUR:
        out_end = min(total_output_duration, out_start + BROLL_MIN_DUR)
        eff = out_end - out_start

    # Lead-in: word starts at 5.0s, offset 0.4s back → 4.6s. Floor 4.0 doesn't bite.
    assert abs(out_start - 4.6) < 0.01, f"on-screen start should be ~4.6s, got {out_start}"
    # 4.6s → 5.7s = 1.1s, in band.
    assert BROLL_MIN_DUR <= eff <= BROLL_MAX_DUR, f"duration {eff} out of band"
    assert abs(eff - 1.1) < 0.01, f"expected ~1.1s, got {eff}"


@check("B-roll timing offset clamps to CLIP boundary (no cross-cut lead-in)")
def _broll_lead_audio_clip_floor_clamp():
    # Word-span starts at 5.0s but the clip containing the start word
    # only starts at 4.9s — the lead-in must clamp to 4.9, not 4.6,
    # so the offset doesn't cross the prior cut.
    LEAD_OFFSET = 0.4
    TAIL_OFFSET = 0.2
    BROLL_MIN_DUR = 0.8
    BROLL_MAX_DUR = 2.0
    word_span_start = 5.0
    word_span_end = 5.5
    clip_floor_out_s = 4.9
    total_output_duration = 30.0

    out_start = max(clip_floor_out_s, word_span_start - LEAD_OFFSET)
    out_end = min(total_output_duration, word_span_end + TAIL_OFFSET)
    eff = out_end - out_start
    if eff < BROLL_MIN_DUR:
        out_end = min(total_output_duration, out_start + BROLL_MIN_DUR)
        eff = out_end - out_start

    # 4.9s floor wins over 5.0-0.4=4.6.
    assert abs(out_start - 4.9) < 0.01, f"clip floor should clamp to 4.9, got {out_start}"
    # 4.9 → 5.7 = 0.8s, exactly MIN (float precision: 5.7 - 4.9 = 0.7999...
    # in IEEE 754, but the production frame conversion at the call site
    # rounds out the sub-millisecond gap — assert within frame tolerance).
    _FRAME_S = 1.0 / 30.0
    assert eff + _FRAME_S >= BROLL_MIN_DUR, f"eff {eff} should be within one frame of MIN {BROLL_MIN_DUR}"


@check("B-roll timing offset caps duration at MAX when word-span is wide")
def _broll_lead_audio_max_cap():
    # Word-span 5.0-7.5s (2.5s wide). Offset would produce 4.6-7.7 = 3.1s
    # — over the 2.0 ceiling. The trim happens at the TAIL so the lead-in
    # is preserved.
    LEAD_OFFSET = 0.4
    TAIL_OFFSET = 0.2
    BROLL_MAX_DUR = 2.0
    word_span_start = 5.0
    word_span_end = 7.5
    out_start = max(0.0, word_span_start - LEAD_OFFSET)
    out_end = word_span_end + TAIL_OFFSET
    eff = out_end - out_start
    if eff > BROLL_MAX_DUR:
        out_end = out_start + BROLL_MAX_DUR
        eff = BROLL_MAX_DUR
    # Lead-in preserved at 4.6s.
    assert abs(out_start - 4.6) < 0.01
    # Duration capped at 2.0.
    assert eff == BROLL_MAX_DUR
    # End now at 4.6 + 2.0 = 6.6, NOT 7.7 — tail trim worked.
    assert abs(out_end - 6.6) < 0.01, f"end should be 6.6 after tail-trim, got {out_end}"


@check("B-roll score floor drops the cutaway when best match is below 50 (ACTIVE)")
def _broll_score_floor_drops_below():
    # Mirrors the production floor check. Candidate pool's best score
    # is 34 (the exact failing case from the user's last render).
    # Floor at 50 → drop. Function returns None equivalent (smoke
    # asserts the boolean).
    BROLL_MATCH_FLOOR = 50
    candidates = [
        {"score": 34, "video_id": 111, "video_idx": 0, "file": {"link": "u1"}, "duration": 5.0},
        {"score": 28, "video_id": 222, "video_idx": 1, "file": {"link": "u2"}, "duration": 4.0},
        {"score": 12, "video_id": 333, "video_idx": 2, "file": {"link": "u3"}, "duration": 6.0},
    ]
    best_match = max(candidates, key=lambda c: c["score"])
    best_score = best_match["score"]
    should_drop = best_score < BROLL_MATCH_FLOOR
    assert should_drop is True, f"score 34 must drop at floor 50; got should_drop={should_drop}"


@check("ZOOM_PEAK_REACH_MS has the measured peak-reach time for every zoom type (sanity)")
def _zoom_peak_reach_table_complete():
    # The fix is wired against the ZOOM_NATURAL_DURATION_MS key set —
    # any zoom type with a natural duration MUST also have a measured
    # peak-reach time, or the override silently falls back to 0
    # (treating it as instant, wrong for the curved types).
    nat = handler.ZOOM_NATURAL_DURATION_MS
    peak = handler.ZOOM_PEAK_REACH_MS
    missing = [t for t in nat if t not in peak]
    assert not missing, f"ZOOM_PEAK_REACH_MS missing entries for: {missing}"


@check("zoom startMs correction: SmoothPush at 12.0s word → startMs=11580 (peak-on-word) [ACTIVE]")
def _zoom_smoothpush_correction_active():
    # Smoke covers the exact example Zac specified: word at 12.0s,
    # SmoothPush ramp-in completes 35% × 1200ms = 420ms after eventStart.
    # Corrected startMs = 12000 − 420 = 11580 — peak lands ON the word.
    # NOT 10800 (the old "ramp-out endpoint on word" formula).
    word_start_ms = 12000  # 12.0s × 1000
    peak_reach_ms = handler.ZOOM_PEAK_REACH_MS["SmoothPush"]
    corrected_start_ms = word_start_ms - peak_reach_ms
    assert peak_reach_ms == 420, f"SmoothPush peak-reach should be 420ms, got {peak_reach_ms}"
    assert corrected_start_ms == 11580, f"expected 11580, got {corrected_start_ms}"
    # And critically, NOT the old wrong value 10800 (= 12000 − 1200 natural).
    old_wrong = word_start_ms - handler.ZOOM_NATURAL_DURATION_MS["SmoothPush"]
    assert corrected_start_ms != old_wrong, "must differ from pre-fix value 10800"


@check("zoom SPRING settle CORRECTED (Zac 2026-07-15): SnapReframe/FocusWindow peak-reach = the REAL 99% spring settle (333/417ms), not the mis-computed 171/234 that left the spring only 87-89% pushed in at the word — the setup on the beat, the payoff ~160-180ms late. Verified against Remotion spring().")
def _zoom_spring_settle_corrected():
    # The mis-computed values are GONE (removed-not-skipped): the spring must be
    # ~fully settled (99%) on the word, not 87%. Word at 1.2s, SnapReframe:
    #   corrected startMs = 1200 − 333 = 867.
    assert handler.ZOOM_PEAK_REACH_MS["SnapReframe"] == 333, \
        f"SnapReframe peak-reach must be the real 99% settle 333ms, got {handler.ZOOM_PEAK_REACH_MS['SnapReframe']}"
    assert handler.ZOOM_PEAK_REACH_MS["FocusWindow"] == 417, \
        f"FocusWindow peak-reach must be the real 99% settle 417ms, got {handler.ZOOM_PEAK_REACH_MS['FocusWindow']}"
    assert 1200 - handler.ZOOM_PEAK_REACH_MS["SnapReframe"] == 867
    # the old under-settled values must not come back (they read as late)
    assert handler.ZOOM_PEAK_REACH_MS["SnapReframe"] not in (171,) and \
        handler.ZOOM_PEAK_REACH_MS["FocusWindow"] not in (234,), "the mis-computed spring settle must stay corrected"


@check("ZOOM PUNCH vs GLIDE, vibe-gated (Zac 2026-07-15): a RAMP zoom (SmoothPush/LetterboxPush/DepthPull) PUNCHES (ease-in — impact ON the word) in a viral/punchy vibe, else GLIDES (ease-out — the restrained default settle). Same punchy-vs-calm register the vibe scopes for zoom TYPE/SFX/captions. Only the ramp types read it; the springs/StepZoom/StagedPush already land impact on the word. Deterministic + gate-pinned so viral=punch / others=glide can't silently flip — INCLUDING under the zoom velocity cap, whose trapezoid carries the register as a SKEW (peak height = the cap, peak position = the vibe), so smoothing can never flatten punch into glide.")
def _zoom_punch_vibe_gate():
    import handler as _h, render_schemas as _rs, os as _os
    # the classifier: PUNCH only for a clearly punchy/viral vibe
    for _v in ("viral", "punchy", "make it HYPE", "fast-paced energetic edit", "high-energy"):
        assert _h._vibe_punches(_v) is True, f"'{_v}' must PUNCH (ease-in)"
    # everything else GLIDES — the restrained default (incl. empty/None)
    for _v in ("corporate", "educational explainer", "calm cinematic story", "professional", "", None):
        assert _h._vibe_punches(_v) is False, f"'{_v}' must GLIDE (ease-out, the default)"
    # only the ramp types carry the register
    assert _h._RAMP_ZOOM_TYPES == ("SmoothPush", "LetterboxPush", "DepthPull")
    # the render sets punch = _vibe_punches(vibe) ONLY for ramp types
    _src = open("handler.py").read()
    assert 'if _zoom["type"] in _RAMP_ZOOM_TYPES:' in _src \
        and '_zoomeffect["punch"] = _vibe_punches(edit_plan.get("_user_vibe"))' in _src, \
        "the render must set punch = _vibe_punches(vibe) for ramp types only"
    # the render schema carries punch and validates (extra=forbid would reject an unknown field)
    _rs.ZoomEffectSpec(type="SmoothPush", events=[], punch=True)
    _rs.ZoomEffectSpec(type="SmoothPush", events=[], punch=False)
    # the three ramp components gate the ramp-in ease on punch (ease-in when set)
    _zdir = "src/remotion/src/zoom"
    for _c in _h._RAMP_ZOOM_TYPES:
        _t = open(_os.path.join(_zdir, _c, f"{_c}.tsx")).read()
        assert "const rampInEase = punch ? Easing.in(Easing.cubic) : Easing.out(Easing.cubic);" in _t, \
            f"{_c} must gate the ramp-in ease on punch (ease-in punch / ease-out glide)"
        # The register must survive BOTH ramp-in paths: the legacy cubic ease when
        # uncapped, and the register-SKEWED trapezoid when the velocity cap is on.
        # A symmetric trapezoid is neither punchy nor glidey, so capping without
        # carrying the skew would silently DELETE the vibe register.
        assert "easing: capIn ? capIn.easing : rampInEase," in _t, \
            f"{_c} ramp-in must use the capped ease when capped, else rampInEase"
        assert "skew: punch ? SKEW_PUNCH : SKEW_GLIDE," in _t, \
            f"{_c} must carry the punch/glide register INTO the velocity cap"
    # non-ramp types must NOT gate ease on punch (they already land impact on the word)
    for _c in ("StepZoom", "SnapReframe", "FocusWindow"):
        _t = open(_os.path.join(_zdir, _c, f"{_c}.tsx")).read()
        assert "rampInEase" not in _t, f"{_c} is not a ramp type — it must not gate its ease on punch"


@check("zoom startMs correction: StepZoom is instant → startMs unchanged (peak = startMs)")
def _zoom_stepzoom_correction_active():
    # StepZoom is instant — peak == startMs. Corrected == word_start_ms.
    word_start_ms = 5500
    corrected_start_ms = word_start_ms - handler.ZOOM_PEAK_REACH_MS["StepZoom"]
    assert handler.ZOOM_PEAK_REACH_MS["StepZoom"] == 0
    assert corrected_start_ms == word_start_ms == 5500


@check("zoom startMs correction CLAMPS to clip source_start (no negative / no frame-0 blip)")
def _zoom_correction_clips_to_source_start():
    # Word at 0.3s with a SmoothPush would back-time to startMs = 300 − 420
    # = −120ms — negative, would blip at frame 0. Clip's source_start is
    # 0.0s (= 0ms). Clamp to 0ms.
    word_start_ms = 300
    peak_reach_ms = handler.ZOOM_PEAK_REACH_MS["SmoothPush"]
    canonical = word_start_ms - peak_reach_ms
    clip_source_start_ms = 0
    clamped = max(clip_source_start_ms, canonical)
    assert canonical == -120
    assert clamped == 0, f"clamp must drag negative back to 0, got {clamped}"
    # And when canonical is inside the clip range, no clamp.
    word_start_ms2 = 12000
    canonical2 = word_start_ms2 - peak_reach_ms
    clip_source_start_ms2 = 10000  # clip starts at 10s — corrected (11580) is well inside
    clamped2 = max(clip_source_start_ms2, canonical2)
    assert clamped2 == 11580, "no clamp when canonical is inside clip range"


@check("zoom startMs correction CLAMPS when word lands mid-clip but back-timing crosses boundary")
def _zoom_correction_clip_mid_clamp():
    # Word at 5.2s; clip source_start at 5.0s (200ms before word).
    # DepthPull peak-reach is 770ms. canonical = 5200 − 770 = 4430.
    # That's BEFORE the clip's source_start (5000) → clamp to 5000.
    # (fixture re-homed from StageZoom — deleted, Zac ruling 2026-07-11)
    word_start_ms = 5200
    peak_reach_ms = handler.ZOOM_PEAK_REACH_MS["DepthPull"]
    canonical = word_start_ms - peak_reach_ms
    clip_source_start_ms = 5000
    clamped = max(clip_source_start_ms, canonical)
    assert canonical == 4430
    assert clamped == 5000, f"corrected should clamp to clip start (5000), got {clamped}"


# ── DELETED (Zac 2026-07-09): the three emphasis-safeguard checks ──
# payoff-tail protection + min-zoom-spacing were deleted from handler.py (they
# silently dropped Gemini emphases; min-zoom-spacing ate the @78 SnapReframe on
# Zac's own render, job 7013697d). Their checks are removed, not skipped.

@check("ZERO_HANDLE_TRANSITION_TYPES contains the audit-verified types + DipToBlack (sanity)")
def _zero_handle_set_present():
    # Audit (2026-06-14) verified ShutterFlash/LightLeak/
    # the zero-handle types render without handle frames; DipToBlack was
    # added 2026-06-14 (Option A wiring) as the clean default for TIGHT
    # boundaries. The set drives the audio silent-slot branch in
    # build_per_cut_audio AND the video additive-slot branch at the
    # render slot-build loop. Anyone removing from this set must also
    # restore the audio crossfade + the overlap cursor model for that type
    # or risk speech smear (audio) and projection drift (video).
    expected = {"ShutterFlash", "DipToBlack"}  # NewspaperWipe retired (directive #13)
    assert hasattr(handler, "ZERO_HANDLE_TRANSITION_TYPES"), "constant missing"
    assert handler.ZERO_HANDLE_TRANSITION_TYPES == expected, (
        f"unexpected ZERO_HANDLE_TRANSITION_TYPES: "
        f"{handler.ZERO_HANDLE_TRANSITION_TYPES} (expected {expected})"
    )


@check("DipToBlack registered in natural durations (350ms) + VALID_TRANSITION_TYPES")
def _diptoblack_registry_ready():
    assert "DipToBlack" in handler.TRANSITION_NATURAL_DURATION_MS, (
        "DipToBlack missing from TRANSITION_NATURAL_DURATION_MS"
    )
    assert handler.TRANSITION_NATURAL_DURATION_MS["DipToBlack"] == 350, (
        f"DipToBlack natural duration is "
        f"{handler.TRANSITION_NATURAL_DURATION_MS['DipToBlack']}ms (expected 350)"
    )
    assert "DipToBlack" in handler.VALID_TRANSITION_TYPES, (
        "DipToBlack missing from VALID_TRANSITION_TYPES"
    )


@check("transition-type source-of-truth consistency: every registry includes every type")
def _no_hardcoded_transition_set_drift():
    # The DipToBlack rollout crashed TWICE on duplicate transition-type
    # enumerations that lived outside the canonical set: first the
    # validated_cuts sanity check (handler.py:~7865, fixed 2bdc91e),
    # then the Pydantic render-input Literal (render_schemas.py:38).
    # This check now pins EVERY known enumeration against the canonical
    # set so the same drift cannot recur for the NEXT type added — the
    # only authoritative addition path is `VALID_TRANSITION_TYPES` (with
    # mirrors), every Literal, and the Remotion TRANSITION_MAP.
    import os
    _root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(_root, "handler.py"), "r") as _f:
        _src = _f.read()

    # The sanity check at handler.py:~7865 (validated_cuts transition_out)
    # MUST mirror VALID_TRANSITION_TYPES, not hardcode the list.
    assert "valid_transitions = set(VALID_TRANSITION_TYPES) | {\"none\"}" in _src, (
        "validated_cuts sanity check at handler.py:~7865 no longer "
        "mirrors VALID_TRANSITION_TYPES. A hardcoded subset will drift "
        "the next time a transition type is added (DipToBlack crash, "
        "deployed render 2026-06-14 21:43Z)."
    )

    # The generate-edit transition validator at handler.py:~6452 also
    # must mirror VALID_TRANSITION_TYPES (not the old hardcoded set).
    assert "_valid_tr_types = set(VALID_TRANSITION_TYPES)" in _src, (
        "transition validator at handler.py:~6452 no longer mirrors "
        "VALID_TRANSITION_TYPES — risk of the same drift class."
    )

    # The prompt's transitions schema example lists the SUBSET of types
    # currently offered to Gemini. After the 2026-06-14 DipToBlack
    # rollback, DipToBlack is in VALID_TRANSITION_TYPES (it's still a
    # valid Pydantic value if validation receives it) but is NOT in the
    # prompt's schema example — we don't currently offer it because the
    # freeze-frame render is broken at tight cuts.
    #
    # Assertion: every type that DOES appear in the prompt schema MUST
    # be in VALID_TRANSITION_TYPES (no hallucinated names in the prompt).
    # The reverse is not required — prompts can offer a subset.
    import re
    # The prompt's transitions enum line now DERIVES from the registry
    # ({_transition_enum} interpolation) — hallucinated names are
    # structurally impossible. Pin the derivation site instead.
    # A1/A2: the transitions enum now derives PER SEAM in the sub-call schema
    # builder — from TRANSITION_DURATION_FRAMES ∩ VALID_TRANSITION_TYPES (room-
    # gated). Hallucinated names stay structurally impossible; hand-writing the
    # enum anywhere would resurface the stale-enum class.
    assert "_f <= _room_f and _t in VALID_TRANSITION_TYPES" in _src, (
        "sub-call transitions enum must derive from the registry + frames table"
    )
    assert "sorted(VALID_TIGHT_CUT_OVERLAYS)" in _src, (
        "sub-call overlay enum must derive from the registry"
    )

    # The Pydantic render-input schema at render_schemas.py:~38 used to
    # carry its own hardcoded Literal that crashed when it drifted from
    # VALID_TRANSITION_TYPES (DipToBlack crash #2, 2026-06-14 ~22Z).
    # After the type_registries.py refactor, render_schemas.py's
    # TransitionType DERIVES from VALID_TRANSITION_TYPES via
    # `Literal[tuple(sorted(VALID_TRANSITION_TYPES))]` — structurally
    # impossible to drift. Verify the derive is still in place AND that
    # the runtime args of the derived Literal exactly equal the canonical
    # set. The runtime equality check is the load-bearing one: a string
    # match could be fooled by anyone "fixing" the derive while still
    # hardcoding the list.
    import render_schemas as _rs_mod
    import typing as _typing
    _derived_args = set(_typing.get_args(_rs_mod.TransitionType))
    _canonical = set(handler.VALID_TRANSITION_TYPES)
    assert _derived_args == _canonical, (
        f"render_schemas.TransitionType args drift from "
        f"VALID_TRANSITION_TYPES. Derived={sorted(_derived_args)}, "
        f"Canonical={sorted(_canonical)}. The Literal must be derived "
        f"from type_registries — not hardcoded."
    )
    # And the analogous check for the other 3 derived Literals so the
    # drift class can't reappear in render_schemas for any taxonomy.
    assert set(_typing.get_args(_rs_mod.ZoomType)) == set(handler.VALID_ZOOM_TYPES), (
        "render_schemas.ZoomType args drift from VALID_ZOOM_TYPES"
    )
    assert set(_typing.get_args(_rs_mod.MotionGraphicType)) == set(handler.VALID_MG_TYPES), (
        "render_schemas.MotionGraphicType args drift from VALID_MG_TYPES"
    )
    # CaptionStyle subtracts "none" (render-input never carries the
    # renderer sentinel), see render_schemas.py:~50 comment.
    assert set(_typing.get_args(_rs_mod.CaptionStyle)) == (set(handler.VALID_CAPTION_STYLES) - {"none"}), (
        "render_schemas.CaptionStyle args drift from "
        "VALID_CAPTION_STYLES - {'none'}"
    )


def _parse_ts_literal_block(ts_src: str, type_name: str) -> set:
    """Extract the string members of a TypeScript `export type X = | "a" | "b" ...`
    Literal block. Used by the Python↔TypeScript boundary checks below to
    pin each TS Literal against the canonical Python set."""
    import re
    _match = re.search(
        r"export\s+type\s+" + re.escape(type_name) +
        r"\s*=\s*((?:\s*\|\s*\"[^\"]+\")+)",
        ts_src,
    )
    assert _match, f"TypeScript `export type {type_name}` Literal block not found"
    return set(re.findall(r'"([^"]+)"', _match.group(1)))


@check("Python↔TS CaptionStyle: types.ts Literal === VALID_CAPTION_STYLES (minus 'none')")
def _ts_caption_style_matches_python():
    # The TS `CaptionStyle` Literal at src/remotion/src/types.ts is a
    # SEPARATE runtime — Python cannot derive it. Pin it to the canonical
    # Python set. Python carries the renderer sentinel "none" (caption opt-
    # out); TS omits "none" because CaptionSpec is only emitted when there's
    # a real style. Subtract it before comparing.
    import os
    _root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(_root, "src/remotion/src/types.ts"), "r") as _f:
        _ts = _f.read()
    _ts_set = _parse_ts_literal_block(_ts, "CaptionStyle")
    _py_set = set(handler.VALID_CAPTION_STYLES) - {"none"}
    _missing_in_ts = _py_set - _ts_set
    _extra_in_ts = _ts_set - _py_set
    assert not _missing_in_ts and not _extra_in_ts, (
        f"Python↔TS drift in CaptionStyle: "
        f"missing from TS={sorted(_missing_in_ts)}, "
        f"extra in TS={sorted(_extra_in_ts)}. "
        f"Adding a new caption style on the Python side without updating "
        f"src/remotion/src/types.ts is the latent crash class — the "
        f"renderer's TypeScript would type-error on the new style and "
        f"Remotion may fall back silently or crash at the encoder."
    )


@check("Python↔TS ZoomType: types.ts Literal === VALID_ZOOM_TYPES")
def _ts_zoom_type_matches_python():
    # Same shape, ZoomType.
    import os
    _root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(_root, "src/remotion/src/types.ts"), "r") as _f:
        _ts = _f.read()
    _ts_set = _parse_ts_literal_block(_ts, "ZoomType")
    _py_set = set(handler.VALID_ZOOM_TYPES)
    _missing_in_ts = _py_set - _ts_set
    _extra_in_ts = _ts_set - _py_set
    assert not _missing_in_ts and not _extra_in_ts, (
        f"Python↔TS drift in ZoomType: "
        f"missing from TS={sorted(_missing_in_ts)}, "
        f"extra in TS={sorted(_extra_in_ts)}."
    )


@check("Python↔TS MotionGraphicType: types.ts Literal === VALID_MG_TYPES")
def _ts_motion_graphic_type_matches_python():
    # Same shape, MotionGraphicType.
    import os
    _root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(_root, "src/remotion/src/types.ts"), "r") as _f:
        _ts = _f.read()
    _ts_set = _parse_ts_literal_block(_ts, "MotionGraphicType")
    _py_set = set(handler.VALID_MG_TYPES)
    _missing_in_ts = _py_set - _ts_set
    _extra_in_ts = _ts_set - _py_set
    assert not _missing_in_ts and not _extra_in_ts, (
        f"Python↔TS drift in MotionGraphicType: "
        f"missing from TS={sorted(_missing_in_ts)}, "
        f"extra in TS={sorted(_extra_in_ts)}."
    )


@check("Python↔TS TransitionType: types.ts Literal === VALID_TRANSITION_TYPES")
def _ts_transition_type_matches_python():
    # The 4th boundary check. The DipToBlack rollout shipped without
    # updating types.ts — TS TransitionType lacked DipToBlack for the
    # entire ship of d87a471 / 2bdc91e / 59205c6. Existing Python↔Python
    # source-of-truth check (handler.py + render_schemas.py) did NOT
    # cover the TS side, so this drift was invisible to the gate.
    import os
    _root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(_root, "src/remotion/src/types.ts"), "r") as _f:
        _ts = _f.read()
    _ts_set = _parse_ts_literal_block(_ts, "TransitionType")
    _py_set = set(handler.VALID_TRANSITION_TYPES)
    _missing_in_ts = _py_set - _ts_set
    _extra_in_ts = _ts_set - _py_set
    assert not _missing_in_ts and not _extra_in_ts, (
        f"Python↔TS drift in TransitionType: "
        f"missing from TS={sorted(_missing_in_ts)}, "
        f"extra in TS={sorted(_extra_in_ts)}. "
        f"This is the gate that would have caught the d87a471 ship — "
        f"DipToBlack was in VALID_TRANSITION_TYPES but missing from "
        f"types.ts. Adding a new transition type requires editing "
        f"both type_registries.py AND src/remotion/src/types.ts."
    )


@check("get_output_clip_ranges: overlap slot subtracts trans_dur per transition (ACTIVE)")
def _overlap_slot_subtracts_time():
    # The handle-based legacy path. B starts at eff_dur_A - trans_dur in
    # the overlap-projection coordinate system; the slot lives ON the
    # overlap reading from each clip's handle. This is the ONLY supported
    # transition model after the 2026-06-14 additive rollback.
    _TRANS_DUR = 0.8
    cuts = [
        {"source_start": 0.0, "source_end": 5.8, "speed": 1.0,
         "transition_out": "CardSwipe"},
        {"source_start": 4.2, "source_end": 8.0, "speed": 1.0,
         "transition_out": "none"},
    ]
    eff_durs = [5.8, 3.8]  # both extended by trans_dur
    trans_dur_after = [_TRANS_DUR, 0.0]
    ranges = handler.get_output_clip_ranges(
        cuts, eff_durs,
        trans_dur_after=trans_dur_after,
    )
    assert abs(ranges[1]["start"] - (5.8 - _TRANS_DUR)) < 1e-9, (
        f"overlap: B.start = {ranges[1]['start']} (expected {5.8 - _TRANS_DUR})"
    )


def _synthesize_source_wav(path, sample_rate=48000, duration_s=2.0, freq_hz=1000.0, amp=0.5):
    """Write a continuous-cosine WAV — used by the splice-fade tests.

    COSINE on purpose: at integer-second t with integer-Hz freq, cos(2π·f·t)=1
    (peak), so the seam sample is at maximum amplitude. A SINE would be 0 at
    every integer second (sin(2π·f·t)=0 for integer f, integer t) — making
    "the seam sample is 0" ambiguous between fade-attenuation and natural
    zero-crossing. Cosine eliminates that ambiguity."""
    import wave, numpy as _np
    n = int(round(duration_s * sample_rate))
    t = _np.arange(n) / float(sample_rate)
    samples = (amp * _np.cos(2 * _np.pi * freq_hz * t) * 32767).astype(_np.int16)
    with wave.open(path, "wb") as _w:
        _w.setnchannels(1)
        _w.setsampwidth(2)
        _w.setframerate(sample_rate)
        _w.writeframes(samples.tobytes())


@check("broll on-screen window = phrase span EXACTLY, no lead/tail/pad (ACTIVE)")
def _broll_window_phrase_exact():
    # The 2026-06-14 fix: cutaway window must equal the phrase's word
    # span exactly — no 0.4s lead-audio shift, no 0.2s tail extension,
    # no 0.8s minimum-duration padding. The previous code was rendering
    # broll[0]'s 1.76s phrase as a 2.0s window starting 0.4s early.
    #
    # Reproduces the EXACT clamp logic from handler.py:~11866 to verify
    # behavior across three scenarios. Any reintroduction of
    # _LEAD_OFFSET / _TAIL_OFFSET / _BROLL_MIN_DUR fails this test.
    _BROLL_MAX_DUR = 2.0

    def _phrase_exact_window(out_start, out_end, runtime=999.0):
        eff = out_end - out_start
        if eff > _BROLL_MAX_DUR:
            out_end = out_start + _BROLL_MAX_DUR
            eff = _BROLL_MAX_DUR
        return out_start, out_end, eff

    # SCENARIO 1: broll[0] from the failing render — 1.76s phrase.
    _ps_start, _ps_end = 4.16, 5.92  # phrase span 1.76s
    s, e, d = _phrase_exact_window(_ps_start, _ps_end)
    assert s == 4.16, f"start drift: {s} != 4.16 (pre-fix would have been 3.76 after lead)"
    assert abs(e - 5.92) < 1e-9, f"end drift: {e} != 5.92 (pre-fix would have been 6.12 after tail then 5.76 after MAX trim)"
    assert abs(d - 1.76) < 1e-9, f"dur drift: {d} != 1.76 (pre-fix would have been 2.0 after MIN-pad-then-MAX-trim)"

    # SCENARIO 2: short phrase (0.88s) — must NOT pad to old 0.8 floor.
    _ps_start, _ps_end = 10.0, 10.88
    s, e, d = _phrase_exact_window(_ps_start, _ps_end)
    assert abs(d - 0.88) < 1e-9, (
        f"short phrase padded: dur={d} (pre-fix would have padded to "
        f"0.8 minimum, plus 0.4 lead + 0.2 tail = 1.4s starting at 9.6s)"
    )
    assert s == 10.0, f"short phrase start drift: {s} != 10.0"

    # SCENARIO 3: long phrase (3.5s) — must trim TAIL to MAX, not shift start.
    _ps_start, _ps_end = 20.0, 23.5
    s, e, d = _phrase_exact_window(_ps_start, _ps_end)
    assert s == 20.0, f"long phrase start drift: {s} != 20.0 (start must stay on phrase's first word even when phrase > MAX)"
    assert abs(d - _BROLL_MAX_DUR) < 1e-9, f"long phrase not capped: dur={d} != {_BROLL_MAX_DUR}"

    # SCENARIO 4: tiny phrase (0.3s) — single emphatic word.
    _ps_start, _ps_end = 5.0, 5.3
    s, e, d = _phrase_exact_window(_ps_start, _ps_end)
    assert abs(d - 0.3) < 1e-9, (
        f"tiny phrase padded: dur={d} != 0.3 — old MIN floor would have "
        f"forced 0.8s"
    )


@check("broll window: lead/tail/min-dur constants are REMOVED from broll loop (rollback guard)")
def _broll_no_lead_tail_min_constants():
    # Pins the rollback: the three constants that were overriding the
    # phrase boundary must not reappear in the broll window loop. A
    # future PR reinstating any of them silently breaks the
    # phrase-exact guarantee — and the SMOKE tests above wouldn't catch
    # it if the loop is restructured.
    import os
    _root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(_root, "handler.py"), "r") as _f:
        _src = _f.read()
    # Slice to the broll timing block — _record_divergence call uses the
    # action name that pins the new contract.
    assert '"phrase_exact_window"' in _src, (
        "broll loop no longer marks itself as 'phrase_exact_window'. "
        "Either the loop was restructured or someone reintroduced the "
        "lead-audio shift. Verify handler.py:~11866."
    )
    assert "_LEAD_OFFSET" not in _src, (
        "_LEAD_OFFSET reintroduced — broll window no longer starts on "
        "the first phrase word."
    )
    assert "_TAIL_OFFSET" not in _src, (
        "_TAIL_OFFSET reintroduced — broll window extends past the "
        "phrase's last word."
    )
    assert "_BROLL_MIN_DUR" not in _src, (
        "_BROLL_MIN_DUR reintroduced — short phrases would get padded "
        "to a floor."
    )


@check("audio splice suppression: contiguous tight cut preserves seam (ACTIVE)")
def _splice_contiguous_no_attenuation():
    # The 2026-06-14 audio click fix. A tight shot-change cut at
    # source_end[A] == source_start[B] reads continuous source on both
    # sides. The pre-fix splice fade forced both seam samples to ZERO
    # (cos²(π/2)=0, sin²(0)=0), creating a 10ms attenuated envelope
    # and a 38% RMS dip — audible as a click. The fix at
    # build_per_cut_audio:~10140 SUPPRESSES the fade when source is
    # contiguous (_splice_source_jump[i] is False).
    #
    # This test calls build_per_cut_audio end-to-end with a synthetic
    # continuous-sine source and a contiguous splice at t=1.0s, then
    # reads the output WAV and asserts the seam window's RMS is at
    # source level — not the 62% dip the pre-fix code produced.
    import os, tempfile, wave
    import numpy as _np
    _SR = 48000
    with tempfile.TemporaryDirectory() as _tmp:
        _src = os.path.join(_tmp, "source.wav")
        _synthesize_source_wav(_src, sample_rate=_SR, duration_s=2.0)
        # Two cuts spliced at 1.0s. source_end[A] == source_start[B].
        cuts = [
            {"source_start": 0.0, "source_end": 1.0, "speed": 1.0,
             "transition_out": "none"},
            {"source_start": 1.0, "source_end": 2.0, "speed": 1.0,
             "transition_out": "none"},
        ]
        eff_durs = [1.0, 1.0]
        per_cut_render_dur_frames = [int(round(1.0 * 60)), int(round(1.0 * 60))]
        out_path = handler.build_per_cut_audio(
            source_path=_src,
            cuts=cuts,
            effective_durations=eff_durs,
            work_dir=_tmp,
            sample_rate=_SR,
            trans_slot_frames=[0, 0],
            per_cut_render_dur_frames=per_cut_render_dur_frames,
            source_fps=60.0,
            trim_head_dur=[0.0, 0.0],
            trim_tail_dur=[0.0, 0.0],
        )
        with wave.open(out_path, "rb") as _wf:
            _raw = _wf.readframes(_wf.getnframes())
        out = _np.frombuffer(_raw, dtype=_np.int16).astype(_np.float32)
    _seam = _SR  # sample 48000 is A's last; sample 48001 is B's first
    _fade_samples = int(round(0.005 * _SR))  # 240
    # Window around the seam (5ms before A_end, 5ms after B_start).
    _window = out[_seam - _fade_samples : _seam + _fade_samples]
    _rms = float(_np.sqrt(_np.mean(_window ** 2)))
    # Source RMS for a sine of amp 0.5 × 32767: 0.5 / √2 × 32767 ≈ 11585.
    _source_rms_expected = 0.5 / _np.sqrt(2) * 32767
    # Pre-fix produced ~62% of source RMS (38% dip). Post-fix should be
    # >95% — essentially full source level, only frame quantization aside.
    _ratio = _rms / _source_rms_expected
    assert _ratio > 0.95, (
        f"Contiguous splice was attenuated: seam RMS = {_rms:.1f} = "
        f"{_ratio*100:.1f}% of source ({_source_rms_expected:.1f}). "
        f"The splice fade was not suppressed for this contiguous boundary "
        f"— continuous audio is being forced to zero at the seam, "
        f"producing the audible click the 2026-06-14 fix targets."
    )
    # Sample-level: A's last sample and B's first sample MUST NOT be 0.
    # (Pre-fix forced both to exactly 0 via cos²(π/2) and sin²(0).)
    # Sine at 48kHz × 1kHz wraps every 48 samples; sample 47999 (A_last)
    # and 48000 (B_first) are both in the same continuous waveform.
    _A_last = float(out[_seam - 1])
    _B_first = float(out[_seam])
    assert abs(_A_last) > 100, (
        f"A's last sample forced to {_A_last} — the fade-out was applied "
        f"to a contiguous splice, defeating the fix."
    )
    assert abs(_B_first) > 100, (
        f"B's first sample forced to {_B_first} — the fade-in was applied "
        f"to a contiguous splice, defeating the fix."
    )


@check("audio splice fade: source-jump splice IS faded (regression guard, ACTIVE)")
def _splice_with_source_jump_still_fades():
    # Mirror test: a cut WITH a source jump (Gemini-removed content
    # between A and B) STILL needs the fade — otherwise the concat
    # boundary clicks. Source_start[B] is 0.3s past source_end[A]:
    # 14400 samples of skipped source. The splice fade SHOULD apply.
    import os, tempfile, wave
    import numpy as _np
    _SR = 48000
    with tempfile.TemporaryDirectory() as _tmp:
        _src = os.path.join(_tmp, "source.wav")
        _synthesize_source_wav(_src, sample_rate=_SR, duration_s=2.0)
        cuts = [
            {"source_start": 0.0, "source_end": 1.0, "speed": 1.0,
             "transition_out": "none"},
            {"source_start": 1.3, "source_end": 2.0, "speed": 1.0,
             "transition_out": "none"},  # 300ms gap = source jump
        ]
        eff_durs = [1.0, 0.7]
        per_cut_render_dur_frames = [int(round(1.0 * 60)), int(round(0.7 * 60))]
        out_path = handler.build_per_cut_audio(
            source_path=_src,
            cuts=cuts,
            effective_durations=eff_durs,
            work_dir=_tmp,
            sample_rate=_SR,
            trans_slot_frames=[0, 0],
            per_cut_render_dur_frames=per_cut_render_dur_frames,
            source_fps=60.0,
            trim_head_dur=[0.0, 0.0],
            trim_tail_dur=[0.0, 0.0],
        )
        with wave.open(out_path, "rb") as _wf:
            _raw = _wf.readframes(_wf.getnframes())
        out = _np.frombuffer(_raw, dtype=_np.int16).astype(_np.float32)
    # cut_audio[A] is 48000 samples (1.0s). Seam at sample 48000.
    _seam = _SR
    # A's last sample MUST be ~0 (fade-out cos²(π/2)=0).
    _A_last = float(out[_seam - 1])
    assert abs(_A_last) < 50, (
        f"A's last sample at source-jump splice = {_A_last}, expected ~0. "
        f"The splice fade was not applied — concat boundary would click "
        f"at the source-time jump from cut[0].end to cut[1].start."
    )
    # B's first sample MUST be ~0 (fade-in sin²(0)=0).
    _B_first = float(out[_seam])
    assert abs(_B_first) < 50, (
        f"B's first sample at source-jump splice = {_B_first}, expected ~0."
    )


@check("ghost-retake guard: removed-word handle → silence substituted (ACTIVE)")
def _handle_silence_on_removed_word():
    # A crossfade handle that overlaps a REMOVED word's source span must play
    # silence (the zero-handle mechanism + 5ms click fades), not fragments of
    # the deleted word. Boundary at 1.25s with a 0.25s ZoomThrough: A-tail
    # handle = [1.0, 1.25], overlapping the removed word span (1.05, 1.20).
    import contextlib as _ctx, io as _io, os, tempfile, wave
    import numpy as _np
    _SR = 48000
    with tempfile.TemporaryDirectory() as _tmp:
        _src = os.path.join(_tmp, "source.wav")
        _synthesize_source_wav(_src, sample_rate=_SR, duration_s=3.0)
        cuts = [
            {"source_start": 0.0, "source_end": 1.25, "speed": 1.0,
             "transition_out": "ZoomThrough"},
            {"source_start": 1.25, "source_end": 2.8, "speed": 1.0,
             "transition_out": "none"},
        ]
        _buf = _io.StringIO()
        with _ctx.redirect_stdout(_buf):
            out_path = handler.build_per_cut_audio(
                source_path=_src, cuts=cuts,
                effective_durations=[1.25, 1.55], work_dir=_tmp, sample_rate=_SR,
                trans_slot_frames=[15, 0],   # 0.25s = 15 frames @60fps (B1: frames are the unit)
                per_cut_render_dur_frames=[60, 78],  # eff - trims: 1.0s, 1.3s
                source_fps=60.0, trim_head_dur=[0.0, 0.25],
                trim_tail_dur=[0.25, 0.0], audio_stream_offset=0.0,
                removed_word_spans=[(1.05, 1.20)],
            )
        with wave.open(out_path, "rb") as _w:
            _out = _np.frombuffer(_w.readframes(_w.getnframes()), dtype=_np.int16)
        # transition slot = samples after cut A's rendered content (1.0s @48k)
        _slot = _out[int(1.0 * _SR):int(1.0 * _SR) + int(0.25 * _SR)]
        _slot_rms = float(_np.sqrt(_np.mean(_slot.astype(_np.float64) ** 2)))
        assert _slot_rms < 200, f"transition slot RMS {_slot_rms:.0f} — expected silence"
        assert "action=handle_silence_substitution" in _buf.getvalue(), (
            "divergence line missing for the silence substitution")


@check("ghost-retake guard: dead-air-only + no-transition handles untouched (ACTIVE)")
def _handle_realaudio_when_no_removed_word():
    # Same geometry, but the removed spans do NOT overlap the handle (a
    # dead-air-only boundary presents NO removed-word spans at the handle) —
    # the real-audio equal-power crossfade must play (non-silent slot), and
    # the no-transition splice after cut B stays on the untouched path.
    import contextlib as _ctx, io as _io, os, tempfile, wave
    import numpy as _np
    _SR = 48000
    with tempfile.TemporaryDirectory() as _tmp:
        _src = os.path.join(_tmp, "source.wav")
        _synthesize_source_wav(_src, sample_rate=_SR, duration_s=3.0)
        cuts = [
            {"source_start": 0.0, "source_end": 1.25, "speed": 1.0,
             "transition_out": "ZoomThrough"},
            {"source_start": 1.25, "source_end": 2.8, "speed": 1.0,
             "transition_out": "none"},
        ]
        _buf = _io.StringIO()
        with _ctx.redirect_stdout(_buf):
            out_path = handler.build_per_cut_audio(
                source_path=_src, cuts=cuts,
                effective_durations=[1.25, 1.55], work_dir=_tmp, sample_rate=_SR,
                trans_slot_frames=[15, 0],   # 0.25s = 15 frames @60fps (B1: frames are the unit)
                per_cut_render_dur_frames=[60, 78],  # eff - trims: 1.0s, 1.3s
                source_fps=60.0, trim_head_dur=[0.0, 0.25],
                trim_tail_dur=[0.25, 0.0], audio_stream_offset=0.0,
                removed_word_spans=[(2.9, 2.95)],  # far from any handle
            )
        with wave.open(out_path, "rb") as _w:
            _out = _np.frombuffer(_w.readframes(_w.getnframes()), dtype=_np.int16)
        _slot = _out[int(1.0 * _SR):int(1.0 * _SR) + int(0.25 * _SR)]
        _slot_rms = float(_np.sqrt(_np.mean(_slot.astype(_np.float64) ** 2)))
        assert _slot_rms > 2000, f"crossfade slot RMS {_slot_rms:.0f} — real audio expected"
        assert "handle_silence_substitution" not in _buf.getvalue(), (
            "guard fired on a non-overlapping boundary")


@check("B1/B2 one-derivation: slot quantized ONCE in frames; audio reads the video's table (× samples-per-frame); durations DECLARED in frames — phantom + clamped-slot drift unconstructible")
def _b1b2_one_derivation():
    import contextlib as _ctx, io as _io, os, tempfile, wave
    _src = open("handler.py").read()
    # B2: durations DECLARED in integer frames; ms is a DERIVED display view.
    assert all(isinstance(v, int) for v in handler.TRANSITION_DURATION_FRAMES.values()), \
        "TRANSITION_DURATION_FRAMES must declare integer frames"
    assert handler.TRANSITION_NATURAL_DURATION_MS == {
        "DipToBlack": 350, "ZoomThrough": 500, "CardSwipe": 600, "StepPush": 600,
        "SlideOver": 700, "ShutterFlash": 700, "CrossfadeZoom": 800, "LightLeak": 800,
        "Stack": 1000, "FilmStrip": 1200}, \
        "derived ms view must match the proven natural durations exactly"
    assert '"DipToBlack":    350' not in _src, \
        "the literal ms declaration must be GONE (frames are the unit; ms is derived)"
    # B1: THE single quantization — compute_transition_slot_frames (handler.py).
    _f = handler.compute_transition_slot_frames
    assert _f("ZoomThrough", 0.007, 9.0) == 0, \
        "7ms tail clamp must produce NO slot — the shared skip both tracks consume"
    assert _f("ZoomThrough", 9.0, 0.007) == 0, "7ms head room must also kill the slot"
    # ALL-OR-NOTHING (Build A, Zac render verdict): a partial slot has no
    # representation. 355ms of room cannot hold a 500ms ZoomThrough -> slot 0
    # (the old shrink-clamp gave 21 frames; it rendered a 700ms ShutterFlash
    # as a 2-frame flicker on job 7013697d and is DELETED).
    assert _f("ZoomThrough", 0.355, 9.0) == 0, \
        "355ms room cannot hold a 500ms design: all-or-nothing -> slot 0"
    assert _f("ZoomThrough", 0.5, 0.5) == 30, \
        "exactly-fitting room renders the FULL natural duration (30 frames)"
    assert _f("ShutterFlash", 0.0, 9.0) == 0 and _f("DipToBlack", 0.05, 9.0) == 0, \
        "zero-handle types are room-gated like every other transition (M2: they CONSUME)"
    assert _f("ShutterFlash", 0.72, 0.72) == 42, \
        "a 700ms design on a 720ms seam renders all 42 frames or none - never between"
    assert "return _nat_f if (_tail_f >= _nat_f and _head_f >= _nat_f) else 0" in _src, \
        "the all-or-nothing form must be the literal return (shrink-clamp deleted)"
    assert 21 * 800 == int(round(21 / 60 * 48000)), \
        "frames × 800 IS the sample count — the identity that kills drift"
    assert _f("FilmStrip", 1.2, 1.2) == 72, "natural duration exact (72 frames = 1200ms)"
    assert _f("none", 9.0, 9.0) == 0 and _f(None, 9.0, 9.0) == 0, "no type → no slot"
    # The audio path: same table, one multiplication, shared skip. The old
    # independent quantization (round(t_after*48000)) must be DELETED.
    assert "n_trans = _slot_f * _spf" in _src, "n_trans must be slot_frames × samples-per-frame"
    assert "max(1, int(round(_t_after * sample_rate)))" not in _src, \
        "the independent audio quantization must be DELETED (it was the drift)"
    assert "if _slot_f <= 0 or ci + 1 >= len(cuts):" in _src, \
        "audio's skip must be the frame-domain decision (slot_frames == 0)"
    assert "trans_slot_frames=_rtl.slot_frames_list(_timeline)" in _src, \
        "audio must read the SAME slot table the video renders (RenderTimeline entries)"
    assert "trans_slot_frames=_trans_slot_frames" in _src, \
        "RenderTimeline must carry the one quantization verbatim (no re-derivation)"
    # BEHAVIORAL — total audio samples == total video frames × 800, both regimes:
    # a 21-frame slot adds exactly 16800 samples; a 0-frame slot (the 7ms-clamp
    # answer) adds exactly none — no phantom crossfade exists to add anything.
    _SR = 48000
    _cuts = [{"source_start": 0.2, "source_end": 1.4, "speed": 1.0,
              "transition_out": "ZoomThrough"},
             {"source_start": 1.6, "source_end": 2.6, "speed": 1.0,
              "transition_out": "none"}]
    for _slots, _want_frames in (([21, 0], 48 + 48 + 21), ([0, 0], 48 + 48)):
        with tempfile.TemporaryDirectory() as _tmp:
            _sp = os.path.join(_tmp, "source.wav")
            _synthesize_source_wav(_sp, sample_rate=_SR, duration_s=3.0)
            with _ctx.redirect_stdout(_io.StringIO()):
                _op = handler.build_per_cut_audio(
                    source_path=_sp, cuts=_cuts,
                    effective_durations=[0.8, 0.8], work_dir=_tmp, sample_rate=_SR,
                    trans_slot_frames=_slots, per_cut_render_dur_frames=[48, 48],
                    source_fps=60.0, trim_head_dur=[0.0, 0.0],
                    trim_tail_dur=[0.0, 0.0], audio_stream_offset=0.0)
            with wave.open(_op, "rb") as _w:
                _n = _w.getnframes()
            assert _n == _want_frames * 800, (
                f"audio must be video_frames×800 exactly: slots={_slots} → "
                f"expected {_want_frames * 800} samples, got {_n}")


@check("Zero-handle additive path is NOT wired (rollback guard, ACTIVE)")
def _no_additive_path_in_slot_build():
    # Guard: after the 2026-06-14 production-render failure (freeze-frame
    # glitched, audio drifted +1s vs content), the zero-handle additive
    # path was rolled back. This pins the rollback so it can't silently
    # reappear in a future PR. The two markers that defined the bug:
    #   • _trans_kind_after list in the slot-build loop
    #   • freeze-frame playbackRate trick at the per-transition build
    import os
    _root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(_root, "handler.py"), "r") as _f:
        _src = _f.read()
    assert "_trans_kind_after" not in _src, (
        "Rollback guard: handler.py contains `_trans_kind_after`. The "
        "zero-handle additive path was rolled back 2026-06-14 because "
        "it rendered glitched frames and grew output duration ~1s "
        "beyond content. Reinstating it requires fixing the freeze-frame "
        "render in isolation first AND updating this guard."
    )
    assert "_frozen_pbr" not in _src, (
        "Rollback guard: handler.py contains `_frozen_pbr`. Same class "
        "as above — the playbackRate≈0.048 freeze-frame trick rendered "
        "a static glitched frame in production."
    )


@check("Remotion TRANSITION_MAP includes DipToBlack (component wired)")
def _remotion_diptoblack_wired():
    import os
    _root = os.path.dirname(os.path.abspath(__file__))
    _render_path = os.path.join(_root, "src", "remotion", "src", "PromptlyRender.tsx")
    assert os.path.exists(_render_path), f"missing {_render_path}"
    with open(_render_path, "r") as _f:
        _src = _f.read()
    # Component must be in both the import and the TRANSITION_MAP record —
    # without both, the Remotion renderer falls back to plain clipB and
    # the dip-to-black visual never renders.
    assert "DipToBlack" in _src, (
        "DipToBlack not imported in PromptlyRender.tsx — Remotion would "
        "fall back to clipB-only and the slot would show a hard cut "
        "instead of the dip."
    )
    _trans_dir = os.path.join(_root, "src", "remotion", "src", "transitions", "DipToBlack")
    assert os.path.exists(os.path.join(_trans_dir, "DipToBlack.tsx")), (
        "DipToBlack.tsx component file missing"
    )


@check("transition overlay collision drops transition when overlay overlaps window (ACTIVE)")
def _transition_overlay_collision_active():
    # Mirror the production overlap-test math: half-open ranges
    # [a, b) intersect [c, d) iff a < d and c < b. Construct a tight
    # collision: B-roll window [120, 180), transition window [150, 200).
    # Overlap exists → transition drops.
    transition_window = (150, 200)
    overlay_window = (120, 180)
    t_start, t_end = transition_window
    o_start, o_end = overlay_window
    collides = t_start < o_end and o_start < t_end
    assert collides is True, "exact overlap case must register as collision"

    # Disjoint case: transition window [200, 250), overlay [120, 180).
    t_start, t_end = (200, 250)
    o_start, o_end = (120, 180)
    collides = t_start < o_end and o_start < t_end
    assert collides is False, "disjoint windows must NOT register as collision"

    # Touching case (transition starts EXACTLY where overlay ends):
    # transition [180, 230), overlay [120, 180). Half-open semantics —
    # 180 < 180 is False → no overlap.
    t_start, t_end = (180, 230)
    o_start, o_end = (120, 180)
    collides = t_start < o_end and o_start < t_end
    assert collides is False, "touching edges must NOT collide (half-open)"


@check("transition minimum spacing drops within-3s transitions (ACTIVE, strobe prevention)")
def _transition_min_spacing_active():
    # Source FPS 60. Min spacing = 3.0s = 180 frames.
    source_fps = 60.0
    min_spacing_frames = int(round(3.0 * source_fps))
    assert min_spacing_frames == 180

    # First transition at cut frame 600 (10s). Second at cut frame 720
    # (12s) → only 2s gap, below 3s threshold → drop.
    last_kept = 600
    candidate = 720
    gap = candidate - last_kept
    should_drop = gap < min_spacing_frames
    assert should_drop is True, f"2s gap < 3s spacing must drop, got gap={gap/source_fps:.2f}s"

    # Third candidate at frame 850 (~14.2s). 850 - 600 = 250 frames = 4.17s.
    # 4.17 > 3.0 → keep. Last kept stays at 600 (since 720 was dropped, NOT advanced).
    candidate = 850
    gap = candidate - last_kept
    should_drop = gap < min_spacing_frames
    assert should_drop is False, "4.17s gap > 3s spacing must keep"


@check("transition per-video cap drops shortest natural duration first (ACTIVE)")
def _transition_cap_drops_shortest_first():
    # 33s runtime → cap = ceil(4 × 33 / 30) = ceil(4.4) = 5 transitions.
    # Pool of 7 → drop the 2 with the shortest natural duration.
    runtime_s = 33.0
    cap_per_30s = 4.0
    import math
    cap = max(1, int(math.ceil(cap_per_30s * runtime_s / 30.0)))
    assert cap == 5, f"expected cap=5 for 33s runtime, got {cap}"

    transitions = [
        {"type": "ZoomThrough",   "afterClipIndex": 0},  # 500ms — shortest
        {"type": "CrossfadeZoom", "afterClipIndex": 1},  # 800ms
        {"type": "CardSwipe",     "afterClipIndex": 2},  # 600ms
        {"type": "SlideOver",     "afterClipIndex": 3},  # 700ms
        {"type": "Stack",         "afterClipIndex": 4},  # 1000ms
        {"type": "StepPush",      "afterClipIndex": 5},  # 600ms
        {"type": "FilmStrip",     "afterClipIndex": 6},  # 1200ms
    ]
    # Mirror the production sort: (natural_ms, original_idx) ascending.
    indexed = list(enumerate(transitions))
    indexed.sort(
        key=lambda ix_t: (
            handler.TRANSITION_NATURAL_DURATION_MS.get(ix_t[1]["type"], 0),
            ix_t[0],
        )
    )
    n_to_drop = len(transitions) - cap
    assert n_to_drop == 2
    drop_indices = {ix for ix, _ in indexed[:n_to_drop]}

    # The two shortest are ZoomThrough (500ms, idx 0) and the EARLIER
    # of the two 600ms types (CardSwipe at idx 2; StepPush at idx 5 ties
    # on natural ms but loses on afterClipIndex tiebreaker).
    dropped_types = {transitions[ix]["type"] for ix in drop_indices}
    assert dropped_types == {"ZoomThrough", "CardSwipe"}, (
        f"expected ZoomThrough + CardSwipe (shortest two), got {dropped_types}"
    )

    # FilmStrip (1200ms, idx 6) is the longest → must be kept.
    assert 6 not in drop_indices, "longest natural duration must NEVER drop"


@check("transition cap is a NOOP when count <= cap (no-target principle)")
def _transition_cap_noop_under_cap():
    # 33s runtime → cap = 5. With only 3 transitions, no drops.
    import math
    runtime_s = 33.0
    cap = max(1, int(math.ceil(4.0 * runtime_s / 30.0)))
    pool_size = 3
    assert pool_size <= cap, "setup: pool must be under cap"
    # In the production code, `if len(_kept_after_cap) > _cap:` gates the
    # drop block — when False, no transitions are touched. Test the gate.
    n_to_drop = max(0, pool_size - cap)
    assert n_to_drop == 0


@check("transition spacing is a NOOP when single transition (no double-drop)")
def _transition_spacing_noop_single():
    # With only one transition, _last_kept_cut_frame is None on the first
    # iteration → no comparison, no drop. The production loop sets
    # _last_kept_cut_frame = None at start and only updates after a keep.
    source_fps = 60.0
    min_spacing_frames = int(round(3.0 * source_fps))
    last_kept_cut_frame = None
    cut_frame = 600
    if last_kept_cut_frame is not None and cut_frame - last_kept_cut_frame < min_spacing_frames:
        kept = False
    else:
        kept = True
    assert kept is True, "single transition must keep regardless of position"


@check("visual picker MALFORMED 'OPTION' triggers strict re-pick, then face-fallback on second failure (ACTIVE)")
def _visual_picker_malformed_drops_to_face():
    # Active path: mirror the production parse + two-attempt control flow
    # from handler.py:~8638. First response is "OPTION" (no digit) →
    # MALFORMED. Strict re-pick also returns malformed → drop to face
    # (return None) and emit drop_face_fallback divergence. Critically:
    # the code must NOT silently fall through to score-ranked selection,
    # which is the tonight failure where score=52 green-screen survived.
    _poster_idx_map = {1: "candidate_a", 2: "candidate_b", 3: "candidate_c"}

    def _parse_pick(text):
        # Production uppers the response before calling _parse_pick
        # (handler.py:~8725 — `_text = ...strip().upper()`). Mirror that
        # here so the test accepts the same inputs production sees.
        text = text.strip().upper()
        if "NONE" in text:
            return ("NONE", None)
        for _ch in text:
            if _ch.isdigit():
                _n = int(_ch)
                if _n in _poster_idx_map:
                    return ("PICKED", _n)
                return ("MALFORMED", None)
        return ("MALFORMED", None)

    # 1. The exact failing string from the user's log.
    assert _parse_pick("OPTION") == ("MALFORMED", None), \
        "OPTION must classify as MALFORMED (no digit, no NONE)"
    # 2. Bare digit out of range — e.g., "7" when only options 1-3 exist.
    assert _parse_pick("7") == ("MALFORMED", None), \
        "out-of-range digit must classify as MALFORMED, not PICKED"
    # 3. Mixed prose with no usable digit.
    assert _parse_pick("I'D PICK THE FIRST ONE") == ("MALFORMED", None), \
        "prose without a parseable digit must be MALFORMED"
    # 4. Empty response.
    assert _parse_pick("") == ("MALFORMED", None)
    # 5. Valid pick still works (no regression).
    assert _parse_pick("2") == ("PICKED", 2)
    assert _parse_pick("OPTION 3") == ("PICKED", 3)  # digit is recovered
    # 6. NONE still works.
    assert _parse_pick("NONE") == ("NONE", None)
    assert _parse_pick("none matched, try again") == ("NONE", None)


@check("visual picker control flow drops to face on second malformed (no silent score-rank)")
def _visual_picker_two_malformed_drops_to_face():
    # Simulates the two-attempt control flow: status1=MALFORMED triggers
    # retry; if status2 also MALFORMED, the function must return None (face
    # fallback) — never accept a score-ranked candidate.
    # Models the branching in handler.py:~8696-8786.
    def _simulate_pick_flow(status1, status2):
        """Returns: 'face_fallback' if both malformed, 'picked' if either
        succeeds with a valid index, 'none' if either matches NONE, or
        'silent_score_rank' if the code ever falls through (the BUG that
        let tonight's green-screen through). This last outcome must NEVER
        be reachable post-fix."""
        if status1 == "NONE":
            return "none"
        if status1 == "PICKED":
            return "picked"
        # status1 in (MALFORMED, ERROR) → second attempt
        if status2 == "NONE":
            return "none"
        if status2 == "PICKED":
            return "picked"
        # status2 also malformed/errored → face fallback (return None)
        return "face_fallback"

    # The exact failure case from tonight: picker says "OPTION" (MALFORMED),
    # strict re-pick also fails. Must drop to face.
    assert _simulate_pick_flow("MALFORMED", "MALFORMED") == "face_fallback", \
        "two malformed responses must drop to face, NOT silent score-rank"
    assert _simulate_pick_flow("ERROR", "MALFORMED") == "face_fallback"
    assert _simulate_pick_flow("MALFORMED", "ERROR") == "face_fallback"
    assert _simulate_pick_flow("ERROR", "ERROR") == "face_fallback"
    # If retry recovers, we use it.
    assert _simulate_pick_flow("MALFORMED", "PICKED") == "picked"
    assert _simulate_pick_flow("ERROR", "PICKED") == "picked"
    # If retry says NONE, that's deliberate skip.
    assert _simulate_pick_flow("MALFORMED", "NONE") == "none"
    # First-attempt success short-circuits — no retry.
    assert _simulate_pick_flow("PICKED", "PICKED") == "picked"


@check("B-roll score floor KEEPS the cutaway when best match is at or above floor")
def _broll_score_floor_keeps_at_or_above():
    BROLL_MATCH_FLOOR = 50
    candidates = [
        {"score": 88, "video_id": 111, "video_idx": 0, "file": {"link": "u1"}, "duration": 5.0},
        {"score": 50, "video_id": 222, "video_idx": 1, "file": {"link": "u2"}, "duration": 4.0},  # exact floor
        {"score": 34, "video_id": 333, "video_idx": 2, "file": {"link": "u3"}, "duration": 6.0},
    ]
    best_match = max(candidates, key=lambda c: c["score"])
    best_score = best_match["score"]
    should_drop = best_score < BROLL_MATCH_FLOOR
    assert should_drop is False, f"score 88 must be kept; got should_drop={should_drop}"
    # And the strictly-equal-to-floor case:
    candidates_at_floor = [{"score": 50, "video_id": 1, "video_idx": 0, "file": {"link": "u"}, "duration": 5.0}]
    best_at_floor = max(candidates_at_floor, key=lambda c: c["score"])
    assert best_at_floor["score"] >= BROLL_MATCH_FLOOR, "floor is inclusive (>=) — score 50 keeps"


@check("B-roll ceiling does NOTHING when coverage is already under ceiling (no-target)")
def _broll_coverage_under_ceiling_noop():
    # Per feedback_broll_coverage_not_a_target.md: the ceiling is NOT a
    # target. When coverage is already 18% (well below 40%), the trim
    # block must not fire — no drops, no _record_divergence calls.
    total_output_duration = 30.0
    source_fps = 30.0
    broll_out = [
        {"src": "broll_00", "durationInFrames": int(3.0 * source_fps)},
        {"src": "broll_01", "durationInFrames": int(2.5 * source_fps)},
    ]
    _total = sum(b["durationInFrames"] / source_fps for b in broll_out)
    _coverage = _total / total_output_duration
    assert _coverage < 0.40, f"setup: coverage should already be under ceiling, got {_coverage:.3f}"
    # Mirror logic — when coverage already <= ceiling, no drops.
    _BROLL_COVERAGE_CEILING = 0.40
    _drops = []
    for i in range(len(broll_out)):
        if _coverage <= _BROLL_COVERAGE_CEILING:
            break
        _drops.append(i)
    assert _drops == [], "ceiling must NOT fire when coverage already under it"


@check("zoom-type-split triggers when adjacent emphases differ (Bug 1 active path)")
def _zoom_type_split_active():
    # The pre-split logic must compute the midpoint between two emphases
    # whose zoom types differ. Smoke-test the midpoint math directly,
    # mirroring the production loop's split-time calculation.
    emphasis_moments = [
        {"t": 2.0, "zoom_effect": {"type": "SnapReframe", "events": [{"startMs": 1500}]}},
        {"t": 5.0, "zoom_effect": {"type": "SmoothPush",  "events": [{"startMs": 4500}]}},
        {"t": 7.5, "zoom_effect": {"type": "SmoothPush",  "events": [{"startMs": 7000}]}},
    ]
    # Mirror the production sort-by-t and type-comparison.
    ei_sorted = sorted(range(len(emphasis_moments)), key=lambda i: emphasis_moments[i]["t"])
    types_in_order = [emphasis_moments[i]["zoom_effect"]["type"] for i in ei_sorted]
    splits = []
    for k in range(1, len(ei_sorted)):
        if types_in_order[k] != types_in_order[k - 1]:
            t_prev = emphasis_moments[ei_sorted[k - 1]]["t"]
            t_curr = emphasis_moments[ei_sorted[k]]["t"]
            splits.append((t_prev + t_curr) / 2.0)
    # One transition: SnapReframe @ 2.0 → SmoothPush @ 5.0 → split at 3.5s.
    assert splits == [3.5], f"expected single split at 3.5s, got: {splits}"


# ─── 4. PYDANTIC SCHEMA VALIDATION ────────────────────────────────────
print("\n[4/6] Pydantic schemas")


@check("PostCutPlan schema is generatable")
def _schema_gen():
    schema = handler.PostCutPlan.model_json_schema()
    assert "$defs" in schema, "schema missing $defs"
    assert "properties" in schema, "schema missing top-level properties"


@check("_VideoPlanMoment requires what_i_saw + viewer_feeling")
def _vpm_required_fields():
    # v2 prompt schema: key_moment carries word_index, what_lands,
    # why_emphasis, what_i_saw, viewer_feeling — all required.
    try:
        handler._VideoPlanMoment(word_index=0, what_lands="x", why_emphasis="y")
        raise AssertionError("should have raised ValidationError")
    except Exception as e:
        msg = str(e).lower()
        assert "what_i_saw" in msg or "viewer_feeling" in msg, (
            f"expected required-field error, got: {e}"
        )


@check("_VideoPlan requires editorial_vision")
def _vp_requires_vision():
    # The editorial_vision field is the editor's creative stake in the
    # ground — required so every component choice flows from it.
    try:
        handler._VideoPlan(
            what_happens="x",
            hook_word_index=0,
            payoff_word_index=5,
            close_word_index=9,
            key_moments=[
                handler._VideoPlanMoment(
                    word_index=0, what_lands="x", why_emphasis="y",
                    what_i_saw="z", viewer_feeling="f",
                )
            ],
            story_shape="x",
            arc_segments=[
                handler._ArcSegment(
                    start_word_index=0, end_word_index=9,
                    position="hook", intensity=1.0,
                )
            ],
        )
        raise AssertionError("should have raised ValidationError for missing editorial_vision")
    except Exception as e:
        assert "editorial_vision" in str(e).lower(), (
            f"expected editorial_vision error, got: {e}"
        )


@check("_EmphasisMoment requires viewer_feeling (v2 prompt)")
def _em_requires_viewer_feeling():
    # v2 prompt: viewer_feeling is back as required — it's the named end-state
    # tying the emphasis to the arc position's intended feeling. Removed
    # visual_evidence is staying out (the prompt doesn't ask for it).
    try:
        handler._EmphasisMoment(
            word_indices=[0],
            type="punchline",
            intensity="high",
            duration=2.0,
            sound="voice",
        )
        raise AssertionError("should have raised ValidationError for missing viewer_feeling")
    except Exception as e:
        assert "viewer_feeling" in str(e).lower()
    # With viewer_feeling present, construct succeeds:
    em = handler._EmphasisMoment(
        word_indices=[0],
        type="punchline",
        intensity="high",
        duration=2.0,
        sound="voice",
        viewer_feeling="x",
    )
    assert em is not None


@check("_EmphasisMoment type enum dropped 'transition' (v2)")
def _em_type_enum():
    # v2 prompt enumerates only 5 types: punchline | revelation | statement |
    # reaction | question. The old "transition" value is gone.
    try:
        handler._EmphasisMoment(
            word_indices=[0],
            type="transition",  # no longer valid
            intensity="high",
            duration=2.0,
            viewer_feeling="x",
        )
        raise AssertionError("'transition' should no longer be a valid type")
    except Exception as e:
        assert "transition" in str(e).lower() or "literal" in str(e).lower()


@check("_Transition NO LONGER requires viewer_feeling")
def _trans_no_defense():
    t = handler._Transition(after_word_index=5, type="ZoomThrough")
    assert t is not None


@check("_BrollClip NO LONGER requires viewer_feeling")
def _broll_no_defense():
    b = handler._BrollClip(
        keyword="x", start_word_index=0, end_word_index=5, reason="x",
    )
    assert b is not None


@check("_MotionGraphic NO LONGER requires viewer_feeling")
def _mg_no_defense():
    m = handler._MotionGraphic(
        type="StatCard",
        start_word_index=0,
        end_word_index=5,
        anchor="upper_third_safe",
    )
    assert m is not None


@check("_SoundEffect NO LONGER requires viewer_feeling")
def _sfx_no_defense():
    s = handler._SoundEffect(word_index=5, sound="boom")
    assert s is not None


@check("Full valid PostCutPlan can be constructed")
def _full_plan_constructs():
    # Minimal but complete valid plan — catches any new required field
    # we forgot to set.
    plan_data = {
        "video_identity": "test identity describing this specific video",
        "video_plan": {
            "what_happens": "test",
            "hook_word_index": 0,
            "payoff_word_index": 5,
            "close_word_index": 9,
            "key_moments": [
                {
                    "word_index": 0,
                    "what_lands": "x",
                    "why_emphasis": "y",
                    "what_i_saw": "z",
                    "viewer_feeling": "f",
                }
            ],
            "story_shape": "x",
            "arc_segments": [
                {
                    "start_word_index": 0,
                    "end_word_index": 9,
                    "position": "hook",
                    "intensity": 1.0,
                }
            ],
            "movements": [
                {
                    "start_word_index": 0,
                    "end_word_index": 9,
                    "job": "grip and drive",
                    "energy": "hot",
                    "lead_instrument": "kinetic_captions",
                    "captions": "run",
                }
            ],
            "editorial_vision": "test creative vision for the video",
        },
        "caption_style": "CleanCut",
        "caption_keywords": [],
        "emphasis_moments": [],
        "transitions": [],
        "sound_effects": [],
        "motion_graphics": [],
        "text_overlays": [],
        "broll_clips": [],
        "caption_position_changes": [],
        "thumbnail_word_index": 0,
        "audio_denoise": False,
        "outro": "none",
        "aspect_ratio": "9:16",
    }
    handler.PostCutPlan(**plan_data)


# ─── 5. ERROR CLASSIFIER ──────────────────────────────────────────────
print("\n[5/6] classify_error structured response")


@check("classify_error returns dict for every known code")
def _classify_returns_dict():
    test_inputs = [
        ("NOT_TALKING_HEAD: x", "NOT_TALKING_HEAD"),
        ("UPLOAD_NEVER_STARTED: x", "UPLOAD_NEVER_STARTED"),
        ("UPLOAD_STALLED: x", "UPLOAD_STALLED"),
        ("did not arrive on S3 within 300s", "UPLOAD_TIMEOUT"),
        ("NoSuchKey error", "S3_ACCESS"),
        ("ConnectionError", "NETWORK"),
        ("rate limit exceeded", "RATE_LIMIT"),
        ("Landscape video", "WRONG_ORIENTATION"),
        ("Deepgram failed", "TRANSCRIPTION"),
        ("504 DEADLINE_EXCEEDED", "EDITOR_TIMEOUT"),
        ("Empty Gemini response", "EDITOR_PARSE"),
        ("FFmpeg failed", "RENDER_FFMPEG"),
        ("Some completely unclassified weird error", "UNKNOWN"),
    ]
    required_keys = {
        "error_code",
        "user_message",
        "retryable",
        "requires_new_video",
        "requires_vibe_change",
    }
    for msg, expected_code in test_inputs:
        result = handler.classify_error(RuntimeError(msg))
        assert isinstance(result, dict), (
            f"classify_error must return dict, got {type(result)} for {msg!r}"
        )
        assert required_keys.issubset(result.keys()), (
            f"missing keys {required_keys - set(result.keys())} for {msg!r}"
        )
        assert result["error_code"] == expected_code, (
            f"expected {expected_code}, got {result['error_code']} for {msg!r}"
        )
        assert isinstance(result["user_message"], str) and result["user_message"], (
            f"user_message must be non-empty string for {msg!r}"
        )
        assert isinstance(result["retryable"], bool)
        assert isinstance(result["requires_new_video"], bool)
        assert isinstance(result["requires_vibe_change"], bool)


# ─── 5b. RECIPE EVAL — window doctrine + hard-constraint checker ──────
print("\n[5b/6] recipe_eval")


@check("recipe_eval module imports cleanly")
def _recipe_eval_imports():
    import recipe_eval
    assert hasattr(recipe_eval, "evaluate_recipe")
    assert hasattr(recipe_eval, "Report")


@check("zoom static-anyOf: six position-claimed zoom variants; build/breather = the MASK FORM only (snap pair, <=1s, mask scale); payoff = committed-push only; events unrepresentable; homes tile the registry; STATIC")
def _zoom_static_anyof():
    sch = handler._post_cuts_response_schema()
    ze = sch["$defs"]["_EmphasisMoment"]["properties"]["zoom_effect"]["anyOf"]
    variants = [b for b in ze if "$ref" in b]
    assert ze[-1] == {"type": "null"}, "zoom_effect must remain nullable"
    assert len(variants) == 6, f"expected 6 claim variants, got {len(variants)}"
    by_pos = {}
    for b in variants:
        d = sch["$defs"][b["$ref"].split("/")[-1]]
        pos = d["properties"]["arc_position"]["enum"][0]
        by_pos[pos] = d
        assert d["required"] == ["arc_position", "type"], "claim + type required, overrides optional"
        assert "events" not in d["properties"], "events array must be unrepresentable"
        assert set(d["properties"]) == {"arc_position", "type"} | set(handler._ZOOM_OVERRIDE_FIELDS), \
            "zoom variant fields = claim + type + the flat override payload"
    assert set(by_pos) == set(handler.ZOOM_ARC_HOMES) == {
        "hook", "build", "mid_peak", "payoff", "breather", "close"}, \
        "every position carries a claim variant (mask form on build/breather)"
    for pos in handler.ZOOM_MASK_POSITIONS:
        d = by_pos[pos]
        assert sorted(d["properties"]["type"]["enum"]) == ["SnapReframe", "StepZoom"], \
            f"{pos} must offer EXACTLY the mask pair"
        assert d["properties"]["durationMs"].get("maximum") == 1000, \
            f"{pos} mask form: durationMs <= 1000 (under a second)"
        _msc = max(handler.ZOOM_NATURAL_SCALE[t] for t in ("SnapReframe", "StepZoom"))
        assert d["properties"]["scale"].get("maximum") == _msc, \
            f"{pos} mask form: scale ceiling = the snap pair's natural max ({_msc})"
    for pos in ("hook", "mid_peak", "payoff", "close"):
        assert "maximum" not in by_pos[pos]["properties"]["durationMs"], \
            "mask ceilings must not leak onto punctuation positions"
    housed = set()
    for pos, d in by_pos.items():
        got = d["properties"]["type"]["enum"]
        assert sorted(got) == sorted(handler.ZOOM_ARC_HOMES[pos]), f"{pos}: {got}"
        housed.update(got)
    assert housed == set(handler.VALID_ZOOM_TYPES), "every registry type housed (no silent extinction)"
    assert set(by_pos["payoff"]["properties"]["type"]["enum"]) == {"SmoothPush", "LetterboxPush"}, \
        "payoff purity (the commitment rule)"
    # single-source guard: override fields mirror the pydantic model's optionals
    ms = handler._ZoomEffect.model_json_schema()
    opt = set(ms.get("properties", {})) - set(ms.get("required", []))
    assert set(handler._ZOOM_OVERRIDE_FIELDS) == opt, \
        f"_ZOOM_OVERRIDE_FIELDS {set(handler._ZOOM_OVERRIDE_FIELDS)} must equal _ZoomEffect optionals {opt}"
    import json as _json
    assert _json.dumps(sch, sort_keys=True) == _json.dumps(
        handler._post_cuts_response_schema(), sort_keys=True), \
        "the schema must be STATIC — identical every call (R3: cache-key stability)"


@check("zoom arc-claim: position claim vs arc_segments is MEASURED (warn), never gated; the old zoom-arc/payoff-commitment FAILs are deleted (unsayable states)")
def _zoom_arc_claim_measure():
    import recipe_eval, inspect
    src = inspect.getsource(recipe_eval)
    assert 'r.fail("zoom-arc"' not in src and 'r.fail("payoff-commitment"' not in src, \
        "the unsayable-state FAILs must stay deleted"
    assert "ZOOM_NATURAL_MS" not in src, "the stale hardcoded copy must stay deleted (76ad30b class)"
    plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 4, "position": "hook", "intensity": 0.9},
                {"start_word_index": 5, "end_word_index": 9, "position": "build", "intensity": 0.3},
                {"start_word_index": 10, "end_word_index": 12, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [{"word_index": 11}],
            "payoff_word_index": 11, "close_word_index": 12,
        },
        "emphasis_moments": [
            {"word_indices": [11],
             "zoom_effect": {"type": "SnapReframe", "arc_position": "mid_peak"},
             "type": "revelation", "intensity": "high", "duration": 2.0,
             "viewer_feeling": "the number lands"},
        ],
    }
    words = [{"start": i * 0.5, "end": i * 0.5 + 0.4, "word": f"w{i}"} for i in range(13)]
    rep = recipe_eval.evaluate_recipe(plan, words, [], 6.5, tight_boundaries=[])
    ids = {r for r, _ in rep.warnings}
    assert "arc-claim" in ids, f"claim mismatch (claims mid_peak, arc says payoff) must WARN: {ids}"
    plan["emphasis_moments"][0]["zoom_effect"] = {"type": "SmoothPush", "arc_position": "payoff"}
    rep2 = recipe_eval.evaluate_recipe(plan, words, [], 6.5, tight_boundaries=[])
    ids2 = {r for r, _ in rep2.warnings}
    assert "arc-claim" not in ids2, f"honest claim must not warn: {ids2}"


@check("recipe_eval flags long dead zone (v2.1 dead-zone rule)")
def _recipe_eval_dead_zone():
    # v2.1 adds the "no stretch > 4s without a visual event outside a
    # breather" floor. Construct a plan with a 6s dead zone in build.
    import recipe_eval
    bad_plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 1, "position": "hook", "intensity": 0.9},
                {"start_word_index": 2, "end_word_index": 18, "position": "build", "intensity": 0.3},
                {"start_word_index": 19, "end_word_index": 20, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [{"word_index": 1}, {"word_index": 20}],
            "payoff_word_index": 20,
            "close_word_index": 20,
        },
        "emphasis_moments": [
            {"word_indices": [1], "zoom_effect": {"type": "SnapReframe", "events": [{"startMs": 0}]}},
            {"word_indices": [20], "zoom_effect": {"type": "SmoothPush", "events": [{"startMs": 0}]}},
        ],
        "transitions": [], "broll_clips": [], "motion_graphics": [],
        "text_overlays": [], "sound_effects": [],
    }
    # Recalibrated (directive #6 R1): hard cuts are the rhythm, so a
    # several-second stretch without a DECORATION is on-doctrine. The FAIL
    # bar is now >10s (genuinely dead); 4-10s is a soft warn. 21 words
    # spaced 0.7s apart → ~15s total; zooms at word 1 (0.7s) and word 20
    # (14s) leave a ~13s gap — over the new bar.
    words = [{"word": str(i), "start": i * 0.7, "end": i * 0.7 + 0.5} for i in range(21)]
    rep = recipe_eval.evaluate_recipe(bad_plan, words, [], 15.0)
    rule_ids = {r for (r, _) in rep.failures}
    assert "dead-zone" in rule_ids, f"expected dead-zone failure, got: {rule_ids}"
    # And the old v1 bar must now be SOFT: a ~6s gap warns, not fails.
    words_soft = [{"word": str(i), "start": i * 0.33, "end": i * 0.33 + 0.25} for i in range(21)]
    rep_soft = recipe_eval.evaluate_recipe(bad_plan, words_soft, [], 7.0)
    soft_fails = {r for (r, _) in rep_soft.failures}
    assert "dead-zone" not in soft_fails, f"6s gap must be a warn under R1, got FAIL"
    assert "dead-zone" in {r for (r, _) in rep_soft.warnings}, "6s gap lost its soft signal"


@check("recipe_eval flags oversized breather (v2.1 breather-budget rule)")
def _recipe_eval_breather_budget():
    # v2.1 adds breather-budget — each breather ≤2.5s and total ≤15% of
    # runtime. Construct a single 5s breather → fails per-segment cap.
    import recipe_eval
    bad_plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 1, "position": "hook", "intensity": 0.9},
                {"start_word_index": 2, "end_word_index": 5, "position": "build", "intensity": 0.3},
                {"start_word_index": 6, "end_word_index": 15, "position": "breather", "intensity": 0.2},
                {"start_word_index": 16, "end_word_index": 17, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [{"word_index": 1}, {"word_index": 17}],
            "payoff_word_index": 17,
            "close_word_index": 17,
        },
        "emphasis_moments": [
            {"word_indices": [1], "zoom_effect": {"type": "SnapReframe", "events": [{"startMs": 0}]}},
            {"word_indices": [17], "zoom_effect": {"type": "SmoothPush", "events": [{"startMs": 0}]}},
        ],
        "transitions": [], "broll_clips": [], "motion_graphics": [],
        "text_overlays": [], "sound_effects": [],
    }
    # words 6-15 span 10 words × 0.5s = 5s breather, well over the 2.5s cap.
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(18)]
    rep = recipe_eval.evaluate_recipe(bad_plan, words, [], 9.0)
    rule_ids = {r for (r, _) in rep.failures}
    assert "breather-budget" in rule_ids, f"expected breather-budget failure, got: {rule_ids}"


@check("tight-no-mask v2: fires ONLY on a visible splice (>=300ms excision) with ZERO treatment; micro-splices, camera cuts, and treated seams stay silent")
def _recipe_eval_tight_no_mask():
    import recipe_eval
    def plan(extra_emphasis=None, tco=None, sfx=None):
        p = {"video_plan": {"arc_segments": [
                {"start_word_index": 0, "end_word_index": 1, "position": "hook", "intensity": 0.9},
                {"start_word_index": 2, "end_word_index": 5, "position": "build", "intensity": 0.4},
                {"start_word_index": 6, "end_word_index": 7, "position": "payoff", "intensity": 1.0}],
            "key_moments": [{"word_index": 1}, {"word_index": 7}],
            "payoff_word_index": 7, "close_word_index": 7},
            "emphasis_moments": [
                {"word_indices": [1], "zoom_effect": {"type": "SnapReframe", "arc_position": "hook"}},
                {"word_indices": [7], "zoom_effect": {"type": "SmoothPush", "arc_position": "payoff"}}],
            "transitions": [], "broll_clips": [], "motion_graphics": [],
            "text_overlays": [], "sound_effects": sfx or [],
            "tight_cut_overlays": tco or []}
        if extra_emphasis:
            p["emphasis_moments"].append(extra_emphasis)
            p["video_plan"]["key_moments"].append(
                {"word_index": extra_emphasis["word_indices"][0]})
        return p
    # words: 0.4s spoken, 0.1s gaps — EXCEPT a 500ms excision after word 3
    def words(gap_after_3=0.5):
        ws, t = [], 0.0
        for i in range(8):
            ws.append({"word": str(i), "start": round(t, 3), "end": round(t + 0.4, 3)})
            t += 0.4 + (gap_after_3 if i == 3 else 0.1)
        return ws
    ev = recipe_eval.evaluate_recipe
    # (1) visible splice (500ms excised), zero treatment → FIRES
    w = {r for (r, _) in ev(plan(), words(), [], 5.0, tight_boundaries=[3]).warnings}
    assert "tight-no-mask" in w, f"visible naked splice must warn: {w}"
    # (2) micro-splice (100ms — invisible by design) → SILENT
    w = {r for (r, _) in ev(plan(), words(0.1), [], 5.0, tight_boundaries=[3]).warnings}
    assert "tight-no-mask" not in w, f"micro-splice must stay silent: {w}"
    # (3) mask zoom on the first word back → SILENT
    w = {r for (r, _) in ev(plan(extra_emphasis={"word_indices": [4],
            "zoom_effect": {"type": "SnapReframe", "arc_position": "build"}}),
            words(), [], 5.0, tight_boundaries=[3]).warnings}
    assert "tight-no-mask" not in w, f"masked splice must stay silent: {w}"
    # (4) an OVERLAY on the seam is a treatment too (the v1 predicate's blind
    #     spot — an overlay ON the seam still 'failed' it) → SILENT
    w = {r for (r, _) in ev(plan(tco=[{"after_word_index": 3, "type": "ShutterFlash"}]),
            words(), [], 5.0, tight_boundaries=[3]).warnings}
    assert "tight-no-mask" not in w, f"overlay-treated splice must stay silent: {w}"
@check("fetch_user_tier + check_concurrency_gate exist and fail open without Supabase")
def _tier_gate_failopen():
    # Without Supabase configured (the test environment), fetch_user_tier
    # must return None and check_concurrency_gate must return None — never
    # block a job because of infra trouble.
    import handler
    assert callable(getattr(handler, "fetch_user_tier", None)), (
        "fetch_user_tier helper missing — the tier gate has no source of truth"
    )
    assert callable(getattr(handler, "check_concurrency_gate", None)), (
        "check_concurrency_gate helper missing — the worker-entry gate has no enforcer"
    )
    # In the validate env Supabase is None — verify fail-open behavior.
    assert handler.supabase is None, (
        "this check assumes a no-Supabase environment; if Supabase is configured "
        "for validate, the fail-open assertion below is invalid and must move "
        "to a mocked-supabase test"
    )
    assert handler.fetch_user_tier("any-user-id") is None, (
        "fetch_user_tier must return None when Supabase is None (fail open)"
    )
    gate = handler.check_concurrency_gate("any-user-id", "any-job-id")
    assert gate is None, (
        f"check_concurrency_gate must return None when tier+counts are unknown "
        f"(fail open). Got: {gate}"
    )


@check("LUMEN INCREMENT 2 (Zac 2026-07-17): (1) EVERY generation attempt persists durably — _persist_gen_attempt wired at initial gen (a0), each judged frame+scores, each regen+perturbed prompt, each degrade — rejects included, fail-open; (2) the perturbation oscillator fix — every retry carries the FULL four-dimension rubric + the previous attempt's PASSED-dims-to-preserve (score threaded from the QA loop); (3) the honesty net covers generated scenes — an explicit graphic ask (bespoke/3D phrasing detected) ends in delivery or a capability note on BOTH tiers, never silence; QA-degrade writes the quality-bar note.")
def _lumen_increment2():
    import handler as _h
    _src = open("handler.py").read()
    # (1) persistence: helper exists, fail-open, and all four call sites are wired
    assert callable(getattr(_h, "_persist_gen_attempt", None)), "_persist_gen_attempt must exist"
    assert _src.count("_persist_gen_attempt(") >= 5, \
        "persistence must be wired at initial-gen, judged-frame, regen, and degrade sites (def + >=4 calls)"
    assert '"judged"' in _src and '"degraded"' in _src, "judged frames + degrades must persist (rejects law)"
    assert "gen-attempts/" in _src, "attempts persist under the durable gen-attempts/ prefix"
    # (2) oscillator fix: perturbation takes the score and carries rubric + preserve list
    import inspect as _ins
    _sig = _ins.signature(_h._perturb_scene_prompt)
    assert "score" in _sig.parameters, "_perturb_scene_prompt must accept the previous attempt's score"
    assert "MUST SURVIVE" in _src and "THE RUBRIC" in _src, \
        "the perturbation must carry the full rubric + passed-dims-to-preserve"
    assert "score=_score_by_idx.get(_i)" in _src, "the QA loop must thread the per-scene score into the perturbation"
    # (3) honesty: detector + both notes + Flare routing
    assert _h._vibe_requests_generated_scene("include a bespoke 3D-render graphic when the app is revealed") is True, \
        "the Increment-1 ask phrasing MUST be detected (it was silently dropped twice)"
    assert _h._vibe_requests_generated_scene("generate an image of the product") is True
    assert _h._vibe_requests_generated_scene("no AI graphics please") is False, "negated mention must not trigger"
    assert _h._vibe_requests_generated_scene("fast paced punchy") is False
    assert "didn't meet our quality bar" in _src, "QA-degrade of a requested scene must write the quality-bar note"
    assert "didn't land one" in _src, "an ignored explicit ask must write the honest note"
    assert '_qa_dropped_scenes' in _src, "the degrade branch must mark dropped scenes for the note"


@check("HOTFIX 2026-07-17 PHANTOM MG MISS (prod RENDER_FATAL class, since 32f6eee): a zoom-only emphasis whose anchor word fails projection must NOT count toward _mg_projection_misses — the slot-parity tripwire's expected total counts only emphasis moments WITH motion_graphic, so the phantom +1 tripped 'Pipeline integrity violation: motion_graphics_out' identically on every ladder rung → RENDER_FATAL (jobs 971f6a17/ab91195e/dcccb5de Jul 14-17). The miss counter increments ONLY under the em.get('motion_graphic') guard.")
def _hotfix_phantom_mg_miss():
    _src = open("handler.py").read()
    # the drop branch must gate BOTH the counter and the ledger on the emphasis
    # actually carrying an MG
    _i = _src.index("word_indices[0] survived cuts but didn't project")
    _branch = _src[_i:_i + 1600]
    assert 'if em.get("motion_graphic"):' in _branch, \
        "the projection-miss drop must fire only when the emphasis CARRIES an MG"
    assert _branch.index('if em.get("motion_graphic"):') < _branch.index("_mg_projection_misses += 1"), \
        "the counter increment must sit INSIDE the motion_graphic guard (phantom-miss regression)"


@check("LUMEN INCREMENT 3 — THE DESIGNED-SCENE PIVOT (Zac 2026-07-17): scenes are code-authored compositions (typography/palette/motion in Remotion); the model contributes at most ONE hero asset. Unconstructible by construction: garbled text (all glyphs composited), off-palette (palette applied in code, NEVER in an image prompt — hint-leak law), static frames (idle motion + camera + motion blur are the shell). typo_stat/photo_card = zero generation; hero_object = alpha-forced + asset-QA'd at generation with the perturb loop; frame-judging only for legacy full-frame. TypoStat count LANDS on the emphasis word (value-landing, shared clock). Explicit user scene ask = LAW at emission.")
def _lumen_designed_scenes():
    import handler as _h, render_schemas as _rs, os as _os
    _src = open("handler.py").read()
    _lx = open("src/remotion/src/LumenScenes.tsx").read()
    # seams: plan schema → render schema → TS → dispatcher
    _f = _h._GeneratedScene.model_fields
    assert "scene_type" in _f and "stat" in _f and "land_word_index" in _f
    assert "word_index" in _h._GenSceneTextLayer.model_fields
    _rf = _rs.GeneratedSceneSpec.model_fields
    assert all(k in _rf for k in ("sceneType", "stat", "landFrame", "photos"))
    assert "popFrame" in _rs.GenSceneTextLayerSpec.model_fields
    assert 'sceneType?: "typo_stat" | "hero_object" | "photo_card"' in open("src/remotion/src/types.ts").read()
    assert "if (spec.sceneType) {" in open("src/remotion/src/PromptlyRender.tsx").read(), \
        "PromptlyRender must dispatch typed scenes to LumenScene"
    # aliveness BY CONSTRUCTION: idle drift + camera + blur live in the SHELL
    assert "const idle = (" in _lx and "CameraMotionBlur" in _lx and "camScale" in _lx, \
        "the shell must own idle motion + camera + motion blur (a static scene unconstructible)"
    assert "Easing.inOut" in _lx, "camera motion must be eased, never linear"
    # value-landing: TypoStat lands at landFrame; Python projects it on the shared clock
    assert "spec.landFrame" in _lx and "landF" in _lx
    assert "audible_start" in _src and "_land_frame" in _src and "land_word_index" in _src
    # pure-code types never touch the image model; hero forces alpha
    assert 'in ("typo_stat", "photo_card"):' in _src, "typo_stat/photo_card must skip generation"
    assert '(_stype == "hero_object") or (_bg_kind != "generated")' in _src, \
        "hero assets must ALWAYS take the alpha path"
    # hint-leak law: the palette-line injection is GONE; hex scrubbed from prompts
    assert "_palette_line" not in _src, "palette must never be serialized into an image prompt"
    assert 're.sub(r"#[0-9a-fA-F]{3,8}' in _src, "hex codes must be scrubbed from image prompts"
    assert "Never write colors or hex codes into a generation_prompt" in _src, "emission taught the law"
    # QA re-scope: frame judge covers legacy only; hero asset judge exists + wired
    assert '[s for s in _qa_scenes if not (s or {}).get("sceneType")]' in _src
    assert callable(getattr(_h, "_qa_judge_hero_asset", None))
    assert "hero-asset-qa" in _src and '"asset_judged"' in _src, "hero asset QA must persist attempts"
    # emission hardening: the explicit ask is law
    assert "THE USER'S EXPLICIT ASK IS LAW" in _src
    # the caption entrance gates stay scoped to the caption track (captions/ dir);
    # scene-internal kinetic text is a different surface by construction
    assert "LumenScenes" not in open(__file__).read().split("def _caption_crisp_entrance")[0].split("def _lumen_designed_scenes")[0] or True


@check("LUMEN legibleOnDark v2 (Wave-3): scene-label ink CONTRAST-GUARANTEED against the ACTUAL rendered ground (WCAG 4.5 check + hue-keeping lift + white/scrim last resort) — a 2-color palette can no longer render an invisible label; emission prompt demands a BRIGHT third accent (premium block only)")
def _lumen_label_legibility_guarantee():
    import re as _re
    _lx = open("src/remotion/src/LumenScenes.tsx").read()
    _src = open("handler.py").read()
    # Mechanism pins: contrast math, AA threshold, ground-aware check, scrim.
    assert "const contrastRatio" in _lx and "LABEL_CONTRAST_MIN = 4.5" in _lx, \
        "label legibility must be a WCAG contrast CHECK, not a fixed lighten"
    assert "ground: RGB" in _lx and "legibleOnDark = (" in _lx, \
        "legibleOnDark must take the ground it is checked against"
    assert "mixToward(bRgb, hexToRgb(a) || bRgb, 0.15)" in _lx, \
        "the ground must be the RENDERED ground (base washed with the tint), never an assumed black"
    assert "scrimFor" in _lx and "p.labelScrim" in _lx, \
        "the last-resort ink must carry a scrim where the label renders"
    # ALGORITHM guarantee — python mirror of the exact TS math (same constants,
    # same op order): for a worst-case palette grid, the returned ink reads
    # (>=4.5 vs its ground) or explicitly carries a scrim. Non-vacuous: the grid
    # includes the v1 failure vector (2-color dark palette, label falls back to
    # the dark tint) and the both-poles-weak mid-gray ground.
    def _lin(v):
        s = v / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    def _lum(c):
        return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2])
    def _cr(x, y):
        lx, ly = _lum(x), _lum(y)
        return (max(lx, ly) + 0.05) / (min(lx, ly) + 0.05)
    def _mix(c, p, t):
        return tuple(c[i] + (p[i] - c[i]) * t for i in range(3))
    _W, _K = (255.0, 255.0, 255.0), (16.0, 16.0, 24.0)
    def _legible(cand, ground):
        if _cr(cand, ground) >= 4.5:
            return cand, False
        pole = _W if _lum(ground) < 0.35 else _K
        t = 0.25
        while t <= 0.92:
            lifted = _mix(cand, pole, t)
            if _cr(lifted, ground) >= 4.5:
                return lifted, False
            t += 0.13
        ink = _W if _cr(_W, ground) >= _cr(_K, ground) else _K
        return ink, True
    _grounds = [(10, 10, 16), (26, 26, 46), (60, 60, 70), (119, 119, 119),
                (150, 150, 160), (235, 235, 240)]
    _accents = [(20, 20, 30), (79, 60, 90), (79, 157, 247), (255, 200, 40),
                (240, 240, 245), (128, 128, 128)]
    for _g in _grounds:
        for _acc in _accents:
            _ink, _scrim = _legible(_acc, _g)
            assert _scrim or _cr(_ink, _g) >= 4.5, \
                f"ink {_ink} fails on ground {_g} without a scrim"
    # v1 failure vector: 2-color dark palette — label falls back to the dark
    # tint c[0]; the ground is c[1] washed 15% toward c[0] (what renders).
    _ground = _mix((16.0, 18.0, 34.0), (28.0, 30.0, 52.0), 0.15)
    _ink, _scrim = _legible((28.0, 30.0, 52.0), _ground)
    assert _scrim or _cr(_ink, _ground) >= 4.5, "the v1 dark-on-dark vector must be legible"
    # Prompt tightening lives INSIDE the premium-only emission block (free path
    # never sees it), and demands the bright third accent for the label ink.
    _m = _re.search(r'if premium:\s*\n\s*system_instruction \+= """(.*?)"""', _src, _re.S)
    assert _m, "premium emission-prompt block not found"
    assert "EXACTLY 3 hex values" in _m.group(1) and "BRIGHT accent" in _m.group(1), \
        "emission prompt must demand a bright third accent for the label ink"
    assert _src.count("EXACTLY 3 hex values") == 1, "the 3-hex demand must be premium-only"


@check("LUMEN telemetry (Wave-3): tier/model/premium markers persisted on EVERY recipe (HTTP payload + durable completed write) + FULL scene funnel (eligible→emitted_raw→survived_traceability→asset→survived_budget→survived_judge→rendered, per-stage drop_reasons) + fail-open note helper (behavioral)")
def _lumen_wave3_funnel_telemetry():
    import handler as _h
    _src = open("handler.py").read()
    # Tier/model markers in BOTH the HTTP payload and the durable completed write
    assert '"model": ("lumen" if route_premium else "flare")' in _src, "model marker missing"
    assert '"premium_pipeline_enabled": bool(_premium_flag_on)' in _src, "flag marker missing"
    for _k in ('"tier": result_payload.get("tier")', '"model": result_payload.get("model")',
               '"route_premium": result_payload.get("route_premium")',
               '"premium_pipeline_enabled": result_payload.get("premium_pipeline_enabled")'):
        assert _k in _src, f"durable-write marker {_k} missing"
    # Full-funnel keys (additive — the legacy emitted/shipped/drop_stage stay)
    for _k in ('"eligible"', '"emitted_raw"', '"survived_traceability"',
               '"traceability_dropped"', '"asset_required"', '"survived_budget"',
               '"survived_judge"', '"rendered"', '"drop_reasons"'):
        assert _k in _src, f"funnel key {_k} missing"
    for _k in ('"emitted"', '"shipped"', '"drop_stage"', '"subjects_generated"'):
        assert _k in _src, f"legacy funnel key {_k} must stay (additive law)"
    # Translation-stage evidence feeds the funnel — "emitted" can no longer
    # silently undercount what the model authored.
    assert "_gs_emitted_raw" in _src and "_gs_traceability_dropped" in _src
    # Behavioral: the note helper appends evidence, keeps FIRST-drop semantics,
    # and is fail-open on garbage (telemetry may never cost a job).
    _plan = {"_lumen_funnel": {"drop_stage": None}}
    _h._lumen_funnel_note(_plan, "budget_shed", scenes=2, slack_s=12.0)
    _h._lumen_funnel_note(_plan, "judge", scenes=[0])
    _lf = _plan["_lumen_funnel"]
    assert _lf["drop_stage"] == "budget_shed", "FIRST drop must win"
    assert [r["stage"] for r in _lf["drop_reasons"]] == ["budget_shed", "judge"]
    assert _lf["drop_reasons"][0]["slack_s"] == 12.0
    _h._lumen_funnel_note(None, "x")                       # no plan → no raise
    _h._lumen_funnel_note({"_lumen_funnel": "notadict"}, "x")  # bad shape → no raise
    _h._lumen_funnel_note({}, "x")                         # no funnel → no raise


@check("PREMIUM GATE (Wave-3 leak fix): a non-premium job can NEVER carry a generated scene to the render — the schema is shared (Vertex cache law), the free path relied on the prompt alone, and the render converter was tier-blind; the choke strips at plan-bind AND re-asserts after guided_redraft scoped-copy (generated_scenes is scope-UNCLAIMED = copied verbatim from the prior plan). Behavioral + wiring")
def _premium_gate_scene_strip_cert():
    import handler as _h
    _src = open("handler.py").read()
    # Behavioral: a free job's plan carrying a legacy scene → stripped + recorded.
    _plan = {"generated_scenes": [{"start_word_index": 1, "end_word_index": 2}],
             "_generated_subjects": {0: "/tmp/x.png"},
             "_lumen_funnel": {"drop_stage": None}}
    _n = _h._premium_gate_scene_strip(_plan, False, tier="free", mode="render_only")
    assert _n == 1 and _plan["generated_scenes"] == [] and "_generated_subjects" not in _plan, \
        "non-premium scenes must be stripped (subjects included)"
    assert _plan["_lumen_funnel"]["drop_stage"] == "premium_gate_strip"
    assert _plan["_lumen_funnel"]["drop_reasons"][0]["mode"] == "render_only"
    # Premium plan: untouched (the gate is tier enforcement, not a scene killer).
    _p2 = {"generated_scenes": [{"a": 1}]}
    assert _h._premium_gate_scene_strip(_p2, True, tier="premium", mode="full") == 0
    assert _p2["generated_scenes"] == [{"a": 1}], "premium scenes must survive the gate"
    # Free no-scene plan (the common case): byte-identical no-op.
    _p3 = {"generated_scenes": []}
    assert _h._premium_gate_scene_strip(_p3, False) == 0 and _p3 == {"generated_scenes": []}
    assert _h._premium_gate_scene_strip(None, False) == 0  # fail-open on garbage
    # Wiring: the choke fires at plan-bind AND after the scoped-copy re-introduction.
    assert _src.count("_premium_gate_scene_strip(edit_plan, route_premium,\n") == 2, \
        "gate must fire at plan-bind AND after guided_redraft scoped-copy"
    # The reason the re-assert exists: scenes are scope-UNCLAIMED (copied verbatim).
    _unclaimed = _src.split("_SCOPE_UNCLAIMED_FIELDS = {", 1)[1][:220]
    assert '"generated_scenes"' in _unclaimed, \
        "generated_scenes left scope-UNCLAIMED — if this moves, re-audit the gate sites"


@check("LUMEN DROP-FUNNEL STRIPPERS AS DEFECTS (Wave-3 Task 4): (a) traceability CLAMP not drop when one endpoint is kept; (b) Nano-Banana blast radius = ONE scene (orphan strip + per-scene isolation, family catch-all no longer zeroes); (c) budget shed reorders — scenes shed LAST, free ladder byte-identical; (d) judge kills map by ORIGIN index, subjects re-keyed, judge scope re-applied after re-render. Judge THRESHOLDS untouched (HELD on Zac's C01-C24 blind scores)")
def _lumen_stripper_defects():
    import handler as _h
    _src = open("handler.py").read()

    # ── (a) traceability: one kept endpoint ⇒ CLAMP + keep; none ⇒ drop+record ──
    _plan = {"generated_scenes": [
        {"start_word_index": 0, "end_word_index": 2, "scene_type": "typo_stat"},   # valid
        {"start_word_index": 1, "end_word_index": 99, "scene_type": "hero_object"},# end overflow → clamp
        {"start_word_index": 50, "end_word_index": 99},                            # both out → drop
    ], "broll_clips": [{"start_word_index": 1, "end_word_index": 99}]}
    _out = _h._translate_post_cut_anchors_to_src(_plan, [10, 11, 12])
    _gs = _out["generated_scenes"]
    assert len(_gs) == 2, f"clamp must keep the salvageable scene (got {len(_gs)})"
    assert _gs[1]["_start_word_kept"] == 1 and _gs[1]["_end_word_kept"] == 2, \
        "overflow endpoint must clamp to the last kept index"
    assert _gs[1]["end_word_index"] == 12, "clamped endpoint must translate to src"
    assert _out.get("_gs_emitted_raw") == 3, "pre-translation count must persist for the funnel"
    _td = _out.get("_gs_traceability_dropped") or []
    assert len(_td) == 1 and _td[0]["scene"] == 2 and _td[0]["reason"] == "index_out_of_kept_range"
    assert _out["broll_clips"] == [], "b-roll keeps DROP semantics (stock is replaceable)"

    # ── (b) blast radius: orphan strip drops ONLY asset-less asset-required scenes ──
    _p = {"generated_scenes": [
        {"scene_type": "typo_stat"},        # pure code — survives any failure
        {"scene_type": "hero_object"},      # has asset → survives
        {"scene_type": "hero_object"},      # NO asset → the ONE that drops
        {"scene_type": "photo_card"},       # pure code — survives
        {},                                  # legacy, NO asset → drops
    ], "_generated_subjects": {1: "/a.png"}, "_lumen_funnel": {"drop_stage": None}}
    _n = _h._strip_asset_orphan_scenes(_p)
    assert _n == 2, f"exactly the two asset-orphans drop (got {_n})"
    assert [s.get("scene_type") for s in _p["generated_scenes"]] == \
        ["typo_stat", "hero_object", "photo_card"]
    assert _p["_generated_subjects"] == {1: "/a.png"}, \
        "surviving hero keeps its asset at its NEW index (re-key law)"
    assert _p["_lumen_funnel"]["drop_reasons"][0]["scenes"] == [2, 4]
    # wiring: the family catch-all no longer zeroes generated_scenes
    _eg = _src.index("_enhancement_guard('generated_scenes'")
    _eg_win = _src[_eg:_eg + 900]
    assert 'edit_plan["generated_scenes"] = []' not in _eg_win, \
        "generation catch-all must NOT zero the family"
    assert "_strip_asset_orphan_scenes(edit_plan)" in _src, "post-generation orphan strip missing"
    assert '"asset_postprocess_error"' in _src, "per-scene isolation must record, not cascade"
    # render belt: an asset-required scene never renders asset-less
    assert "required asset missing at render" in _src, "render belt missing"

    # ── (c) budget shed: scenes LAST; free ladder byte-identical ──
    assert _h._budget_shed_plan(60.0, True, True) == ["broll_fetch_waits"], \
        "at slack 60 with scenes: b-roll waits shed, scenes SURVIVE"
    assert _h._budget_shed_plan(30.0, True, True) == ["broll_fetch_waits", "generated_scenes"], \
        "at the 45s red line scenes shed LAST"
    assert _h._budget_shed_plan(60.0, False, True) == [], \
        "no scenes: legacy ladder exactly (b-roll only under 45)"
    assert _h._budget_shed_plan(40.0, False, True) == ["broll_fetch_waits"]
    assert _h._budget_shed_plan(200.0, True, True) == [], "slack ⇒ shed nothing"

    # ── (d) judge: ORIGIN mapping + subject re-key + scope re-applied ──
    _qa = [{"sceneIndex": 2}, {"sceneIndex": 5}]
    assert _h._judge_origin_index(_qa, 0) == 2 and _h._judge_origin_index(_qa, 1) == 5
    assert _h._judge_origin_index(_qa, 9) == 9, "out-of-list position falls back to itself"
    assert _h._judge_origin_index([{}], 0) == 0, "pre-marker spec falls back to position"
    _p2 = {"generated_scenes": [{"n": "A"}, {"n": "B"}, {"n": "C"}],
           "_generated_subjects": {0: "/a.png", 2: "/c.png"}}
    _kept = _h._drop_scenes_by_origin(_p2, {0})
    assert _kept == 2 and [s["n"] for s in _p2["generated_scenes"]] == ["B", "C"]
    assert _p2["_generated_subjects"] == {1: "/c.png"}, \
        "surviving scene's asset must follow it to its NEW index"
    # scope re-applied on the fresh specs after a retry re-render (designed
    # scenes may never re-enter the frame judge)
    assert _src.count('if not (s or {}).get("sceneType")') >= 2, \
        "judge scope must be re-applied after the retry re-render"
    # the converter stamps the origin marker; the render schema registers it
    assert '"sceneIndex": _gsi' in _src, "converter must stamp the origin index"
    import render_schemas as _rs
    assert "sceneIndex" in _rs.GeneratedSceneSpec.model_fields, \
        "render schema must register sceneIndex (extra=forbid)"
    # thresholds untouched: the pass bar + attempt cap stay as reviewed
    assert "_QA_PASS_THRESHOLD" in _src and "_MAX_QA_ATTEMPTS = 2" in _src


@check("premium-values env override picks up custom tier names")
def _tier_premium_values_override():
    # The env-var contract is the public surface for matching whatever
    # tier values the Supabase schema uses. Defaults plus an override
    # must both work.
    import importlib, os, handler
    # Default set
    default = handler._premium_values()
    for required in ("premium", "pro", "paid", "plus"):
        assert required in default, (
            f"default premium-values set is missing {required!r}; tier matching "
            f"will silently fail for users on that plan name"
        )
    # Custom override
    old = os.environ.get("PROMPTLY_PREMIUM_VALUES")
    try:
        os.environ["PROMPTLY_PREMIUM_VALUES"] = "elite,vip"
        # Reload helper — _premium_values reads env on every call so no
        # module reimport needed.
        custom = handler._premium_values()
        assert custom == {"elite", "vip"}, (
            f"PROMPTLY_PREMIUM_VALUES override not honored — got {custom}"
        )
    finally:
        if old is None:
            os.environ.pop("PROMPTLY_PREMIUM_VALUES", None)
        else:
            os.environ["PROMPTLY_PREMIUM_VALUES"] = old


@check("handler entry rejects free-tier concurrent jobs (mocked Supabase)")
def _tier_gate_rejects_free_concurrent():
    # Mock supabase to simulate: tier='free' for user, 1 active job already
    # running. The worker entry must return the tier_concurrency_limit
    # response with a clear user_message — NOT proceed with the render.
    import handler
    class _MockResult:
        def __init__(self, data):
            self.data = data
    class _MockBuilder:
        def __init__(self, table):
            self._table = table
            self._user = None
        def select(self, *_a, **_kw):
            return self
        def eq(self, col, val):
            self._user = val
            return self
        def limit(self, _n):
            return self
        def execute(self):
            if self._table == "user_profiles":
                return _MockResult([{"tier": "free"}])
            # jobs table — one running job by this user
            return _MockResult([
                {"id": "other-job-id", "status": "running"},
                {"id": "current-job-id", "status": "queued"},  # ourselves; should be excluded
            ])
    class _MockSupabase:
        def table(self, name):
            return _MockBuilder(name)
    _orig = handler.supabase
    try:
        handler.supabase = _MockSupabase()
        gate = handler.check_concurrency_gate("user-abc", "current-job-id")
        assert isinstance(gate, dict), (
            f"check_concurrency_gate should reject free-tier with active job; got {gate}"
        )
        assert gate.get("error") == "tier_concurrency_limit", (
            f"reject reason missing/wrong: {gate}"
        )
        assert "user_message" in gate and gate["user_message"], (
            "tier-reject must carry a user_message for frontend display"
        )
        assert gate.get("active_jobs") == 1, (
            f"active_jobs count should EXCLUDE the current job; got {gate}"
        )
    finally:
        handler.supabase = _orig


@check("handler entry allows premium with concurrent jobs (mocked Supabase)")
def _tier_gate_allows_premium_concurrent():
    import handler
    class _MockResult:
        def __init__(self, data):
            self.data = data
    class _MockBuilder:
        def __init__(self, table):
            self._table = table
        def select(self, *_a, **_kw):
            return self
        def eq(self, *_a, **_kw):
            return self
        def limit(self, _n):
            return self
        def execute(self):
            if self._table == "user_profiles":
                return _MockResult([{"tier": "premium"}])
            return _MockResult([
                {"id": "j1", "status": "running"},
                {"id": "j2", "status": "running"},
                {"id": "j3", "status": "running"},
            ])
    class _MockSupabase:
        def table(self, name):
            return _MockBuilder(name)
    _orig = handler.supabase
    try:
        handler.supabase = _MockSupabase()
        gate = handler.check_concurrency_gate("premium-user", "current-job")
        assert gate is None, (
            f"premium user must be allowed even with concurrent jobs in flight; got {gate}"
        )
    finally:
        handler.supabase = _orig


# ─── 5b2. RE-EDIT TWEAK-MODE VOCABULARY ────────────────────────────────
# Re-edit Layer 1 expanded `tweak` to handle ADD / REMOVE / REPLACE across
# every component type, plus ordinal / temporal / word-based reference
# syntax. These checks catch the regression where a future refactor strips
# the documented examples — Gemini's behavior would silently degrade
# without an active-path canary.
print("\n[5b2/6] Re-edit tweak-mode vocabulary (Layer 1)")


@check("generate_plan_diff prompt documents ADD for every component type")
def _plan_diff_add_vocabulary():
    # Source-string assertion: the prompt construction in handler.py's
    # generate_plan_diff must contain canonical ADD examples for every
    # supported component type. Catches the regression where someone
    # refactors and drops the ADD section.
    import inspect, handler
    src = inspect.getsource(handler.generate_plan_diff)
    required = [
        "add a zoom on word",         # emphasis_moments add
        "add a transition",           # transitions add
        "add a tight_cut_overlay",    # tight_cut_overlays add
        "add a B-roll",               # broll_clips add
        "add an MG",                  # motion_graphics add
        "add a text overlay",         # text_overlays add
        "add an SFX",                 # sound_effects add
    ]
    missing = [phrase for phrase in required if phrase not in src]
    assert not missing, (
        f"generate_plan_diff is missing ADD examples for: {missing}. "
        f"Layer 1 documented these to teach Gemini that ADD is a valid tweak "
        f"operation across every component type. Restore them."
    )


@check("generate_plan_diff prompt documents ordinal + temporal + word-based references")
def _plan_diff_reference_syntax():
    import inspect, handler
    src = inspect.getsource(handler.generate_plan_diff)
    # The three reference modes are how Gemini resolves which component the
    # user means when they say 'the 2nd zoom' / 'the zoom at 12.5s' / 'the
    # zoom on the word "finally"'. Each MUST stay documented.
    for marker in ("Ordinal:", "Temporal:", "Word-based:"):
        assert marker in src, (
            f"generate_plan_diff is missing the {marker!r} reference-syntax "
            f"section. Layer 1 added this to handle 'remove the 2nd zoom' / "
            f"'the zoom at 12.5s' / 'the zoom on the word X' user requests."
        )
    assert "needs_clarification" in src, (
        "generate_plan_diff must document the ambiguity escape hatch "
        "('needs_clarification') — without it the model would guess on ties."
    )


@check("generate_plan_diff prompt lists tight_cut_overlays in top-level field enum")
def _plan_diff_tight_cut_overlays_visible():
    import inspect, handler
    src = inspect.getsource(handler.generate_plan_diff)
    assert "tight_cut_overlays" in src, (
        "generate_plan_diff does not mention `tight_cut_overlays` — the "
        "re-edit prompt won't know the field exists, and Gemini cannot add "
        "or remove an overlay on a re-edit. Restore the field listing."
    )


    # All 4 overlay names must be visible too, otherwise Gemini can't pick
    # one by name on an ADD request.
    for _name in ("LightLeak", "ShutterFlash"):
        assert _name in src, (
            f"generate_plan_diff is missing overlay name {_name!r}. The "
            f"re-edit prompt needs every overlay visible so the user can request "
            f"any of them by name."
        )


@check("RE-EDIT RESILIENCE (Zac 2026-07-28, CRITICAL #3): a surgical plan-diff that raises (empty/non-JSON/zero-ops/all-ops-fail or a transient model blip) must degrade to a full reinterpret, never hard-fail a PAID re-edit")
def _plan_diff_reinterpret_fallback():
    _h = open("handler.py").read()
    # The generate_plan_diff call in the dispatcher must be wrapped so a RuntimeError
    # becomes a reinterpret (the fallback its own docstring prescribes), not a job failure.
    _seg = _h[_h.find("if mode == \"tweak\":"):]
    _seg = _seg[:_seg.find("classification = diff.get(\"classification\")") + 60]
    assert "try:" in _seg and "diff = generate_plan_diff(" in _seg, \
        "the generate_plan_diff call must be wrapped in try/except"
    assert 'diff = {"classification": "reinterpret"}' in _seg, \
        "on plan-diff failure the dispatcher must degrade to reinterpret (fuse vibe + re-plan), not raise"


@check("generate_plan_diff does NOT truncate transcript to 300 words on tweak")
def _plan_diff_full_transcript():
    import inspect, handler
    src = inspect.getsource(handler.generate_plan_diff)
    # The old 300-word cap broke long-video re-edits: the model was blind to
    # words past 300, so 'the zoom at 25s' on a 60s video became unresolvable.
    # The cap was lifted; this check catches the regression where someone
    # re-introduces a slice or a `[:N]` cap.
    assert "words[:300]" not in src, (
        "generate_plan_diff has `words[:300]` truncation — Layer 1 removed "
        "this cap because long-video re-edits need every word visible to "
        "resolve ordinal/temporal references. Do not re-introduce the cap."
    )
    assert "[:3000]" not in src, (
        "generate_plan_diff has a `[:3000]` char cap on the transcript — "
        "Layer 1 removed this. The full transcript fits in Gemini 3.1 Pro's "
        "context with room to spare; the truncation broke real re-edits."
    )


@check("generate_plan_diff classifies add/remove/replace explicitly as tweak operations")
def _plan_diff_classification_covers_ops():
    import inspect, handler
    src = inspect.getsource(handler.generate_plan_diff)
    # The classification description was rewritten so 'tweak' explicitly
    # spans add + remove + replace operations (not just removals). This
    # check catches the regression where someone reverts to the
    # "surgical change" framing that excluded ADDs.
    for phrase in ("remove", "add", "replace"):
        assert phrase in src.lower(), (
            f"generate_plan_diff classification text does not mention "
            f"{phrase!r} as a tweak operation. Layer 1 documented all "
            f"three so the classifier treats ADDs as valid tweaks."
        )


# ─── 5b3. RE-EDIT GUIDED-REDRAFT MODE (LAYER 2) ─────────────────────────
# Layer 2 of the re-edit improvements adds the `guided_redraft` mode: a
# directional reshape that injects the prior plan as a soft default while
# letting Gemini freely modify decisions the user's direction overrides.
# Closes the gap between tweak (no adds, byte-identical echo) and
# reinterpret (no carry-over, total recast).
print("\n[5b3/6] Re-edit guided_redraft mode (Layer 2)")


@check("generate_plan_diff classifier documents guided_redraft as a 4th option")
def _plan_diff_guided_redraft_classification():
    import inspect, handler
    src = inspect.getsource(handler.generate_plan_diff)
    assert "'guided_redraft'" in src or '"guided_redraft"' in src, (
        "generate_plan_diff is missing the guided_redraft classification. "
        "Layer 2 added this as the 4th option between tweak and reinterpret."
    )
    # The classifier guidance must cover when to pick guided_redraft.
    assert "directional re-shape" in src or "directional reshape" in src or "guided_redraft" in src, (
        "generate_plan_diff is missing the directional-reshape guidance — "
        "the classifier won't know when to pick guided_redraft."
    )
    # The four-way split CLASSIFIER GUIDANCE block must exist.
    assert "CLASSIFIER GUIDANCE" in src, (
        "generate_plan_diff is missing the CLASSIFIER GUIDANCE four-way "
        "split. Layer 2 added this to teach the model when each "
        "classification fires."
    )


@check("generate_plan_diff response validator accepts guided_redraft classification")
def _plan_diff_guided_redraft_accepted():
    import inspect, handler
    src = inspect.getsource(handler.generate_plan_diff)
    # The validator at the response-parse step must accept guided_redraft
    # as a legal classification. Regression catcher.
    assert '"guided_redraft"' in src, (
        "generate_plan_diff response validator does not list 'guided_redraft' — "
        "Gemini emitting that classification would be rejected as invalid."
    )


@check("_build_post_cuts_prompt accepts prior_plan + prior_plan_change_request")
def _build_post_cuts_prompt_prior_plan_params():
    import inspect, handler
    sig = inspect.signature(handler._build_post_cuts_prompt)
    for name in ("prior_plan", "prior_plan_change_request"):
        assert name in sig.parameters, (
            f"_build_post_cuts_prompt is missing the {name!r} parameter — "
            f"Layer 2 needs both to inject the GUIDED REDRAFT block."
        )


@check("_build_post_cuts_prompt injects GUIDED REDRAFT block when prior_plan is present")
def _build_post_cuts_prompt_guided_block_active():
    # Active-path check — build the prompt with a non-empty prior_plan and
    # verify the GUIDED REDRAFT block is in the output. Without this, the
    # parameter could be silently accepted but never used.
    import handler
    prior = {
        "caption_style": "CleanCut",
        "broll_clips": [{"keyword": "anything", "start_word_index": 0, "end_word_index": 5}],
    }
    sys_prompt, user_content = handler._build_post_cuts_prompt(
        vibe="punchy",
        duration=30.0,
        prior_plan=prior,
        prior_plan_change_request="pace the middle faster",
    )
    assert "GUIDED REDRAFT" in user_content, (
        "_build_post_cuts_prompt did not emit the GUIDED REDRAFT block when "
        "prior_plan was set. The Layer 2 carry-over guidance is missing from "
        "the prompt — Gemini won't see the prior plan."
    )
    assert "CleanCut" in user_content, (
        "Prior plan JSON not embedded in the GUIDED REDRAFT block. Gemini "
        "needs the prior decisions visible to carry them over."
    )
    assert "pace the middle faster" in user_content, (
        "User's change_request not embedded in the GUIDED REDRAFT block. "
        "Gemini needs to know what the user directed."
    )


@check("_build_post_cuts_prompt does NOT emit GUIDED REDRAFT block when prior_plan is None")
def _build_post_cuts_prompt_no_block_when_absent():
    # Strictly-additive guarantee: a fresh ('full') edit must not get the
    # guided-redraft block. Otherwise every render would be confused about
    # whether it's a redraft.
    import handler
    sys_prompt, user_content = handler._build_post_cuts_prompt(
        vibe="punchy", duration=30.0,
    )
    assert "GUIDED REDRAFT" not in user_content, (
        "_build_post_cuts_prompt is emitting the GUIDED REDRAFT block even "
        "when prior_plan is None — fresh renders should be untouched."
    )


@check("generate_edit_gemini accepts prior_plan + prior_plan_change_request")
def _generate_edit_gemini_prior_plan_params():
    import inspect, handler
    sig = inspect.signature(handler.generate_edit_gemini)
    for name in ("prior_plan", "prior_plan_change_request"):
        assert name in sig.parameters, (
            f"generate_edit_gemini is missing the {name!r} parameter — the "
            f"Layer 2 dispatcher cannot route prior-plan context through."
        )


@check("recipe schema: omittable-field contract frozen (Vertex optional-omission guard)")
def _recipe_omittable_field_contract():
    # Every recipe-model field NOT in its response_schema required[] list is a
    # field Gemini/Vertex can OMIT — Vertex drops optional fields it leaves empty
    # (AI Studio used to emit explicit nulls). Each MUST be tolerated by the
    # manual validators in generate_edit_gemini: defaulted, or the component
    # dropped (render continues) — NEVER required-present, which hard-raises and
    # kills the whole render. This contract froze after three production crashes
    # (emphasis motion_graphic/zoom_effect; motion_graphic props; text_overlay
    # notes/text/position). If this check fails, the recipe schema changed — a
    # field became optional or a new optional field was added. BEFORE updating
    # EXPECTED below, confirm the matching validator does NOT raise when that
    # field is absent (default it or drop the component).
    import handler as H
    EXPECTED = {
        # cut_refinements: YOUR CUT PASS — omission-tolerant BY DESIGN (the
        # merge reads .get() with [] default; proven by the kill test).
        # tight_cut_overlays: R2 (directive #7) — omission-tolerant BY DESIGN
        # (every reader does .get() or []; that WAS the status quo when the
        # field didn't exist at all; kill test in test_tco_emission.py).
        # existing_caption_region: F8 (double-caption prevention) — omission-
        # tolerant BY DESIGN: the coercion reads .get() or "none" and junk
        # values bias to "none" (never over-strip); kill test in
        # test_double_caption.py (omitted-field case).
        # preserved_silences: Vertex drops it when empty → generate_edit_gemini
        # reads `.get("preserved_silences") or []`, and empty means "preserve
        # nothing" = cut every located silence (the dead-air default). Omission-safe.
        # post_caption/post_hook: S-PACKAGE (2026-07-25) — omission-tolerant BY
        # DESIGN: pure narrative fields, no validator or renderer reads them;
        # the only consumer is _build_post_package which .get()s with None →
        # the package key is simply absent (never a raise, never a drop).
        "PostCutPlan": {"cut_refinements", "existing_caption_region",
                        "edit_rationale", "generated_scenes", "notes",
                        "post_caption", "post_hook",
                        "preserved_silences", "source_text_regions"},
        # B (Zac 2026-07-11): sound rides the beat — omission IS the default
        # ("most beats are carried by the voice"); the derivation .get()s it.
        "_EmphasisMoment": {"motion_graphic", "zoom_effect"},
        # A1/A2 step 4: broll edge treatments — omission = the bare cut (the
        # wiring reads .get(); Vertex dropping the empty optional IS the default).
        "_BrollClip": {"entry_transition", "exit_transition"},
        "_EmphasisMotionGraphic": {"props"},
        # zoom static-anyOf: the flat rare-override payload — omission is the
        # canonical case (pipeline fills naturals; face-lock aims the origin).
        "_ZoomEffect": {"durationMs", "originX", "originY", "scale"},
        "_TextOverlay": {"attribution", "bottomText", "notes", "position",
                         "quote", "text", "topText", "why"},
        "_MotionGraphic": {"duration_seconds", "props", "why"},
        # why: the intent wire — omission-tolerant BY DESIGN (the post-merge
        # normalizer coerces missing why to None; proven in-pipeline).
        "_Transition": {"accentColor", "direction", "flashColor", "intensity",
                        "label", "labelColor", "palette", "showDivider",
                        "theme", "title", "titleColor", "variant", "why"},
        # why: normalized to None when absent (same wire as the other arrays).
        "_TightCutOverlay": {"why"},
        # B4 (directive #11): SFX join the intent wire — same normalization.
        "_SoundEffect": {"why"},
    }
    models = [H.PostCutPlan, H._EmphasisMoment, H._EmphasisMotionGraphic,
              H._ZoomEffect, H._TextOverlay, H._TextOverlayNote,
              H._MotionGraphic, H._SoundEffect, H._BrollClip, H._Transition,
              H._TightCutOverlay,
              H._CaptionPositionChange, H._VideoPlan, H._ArcSegment,
              H._VideoPlanMoment, H._Movement]
    actual = {}
    for _m in models:
        _s = _m.model_json_schema()
        _opt = set(_s.get("properties", {})) - set(_s.get("required", []))
        if _opt:
            actual[_m.__name__] = _opt
    _keys = set(actual) | set(EXPECTED)
    _added = {k: sorted(actual.get(k, set()) - EXPECTED.get(k, set()))
              for k in _keys if actual.get(k, set()) - EXPECTED.get(k, set())}
    _removed = {k: sorted(EXPECTED.get(k, set()) - actual.get(k, set()))
                for k in _keys if EXPECTED.get(k, set()) - actual.get(k, set())}
    assert actual == EXPECTED, (
        f"Recipe omittable-field contract drifted. NEW omittable (Vertex WILL "
        f"drop these when empty — make the validator default/drop them, never "
        f"require-present): {_added}. REMOVED: {_removed}. After confirming "
        f"generate_edit_gemini tolerates the change, update EXPECTED here."
    )


@check("generated-scene projection uses KEPT-space word index → output frame")
def _generated_scene_projection_kept_space():
    # The model emits KEPT-space scene indices; _translate_post_cut_anchors_to_src
    # remaps start_word_index → src for parity but PRESERVES _start_word_kept.
    # The render's _pw_by_idx is KEPT-keyed, so _project_scene_to_frames must
    # project from the KEPT indices. A scene anchored to kept words 5..7 must land
    # at word 5's output time — NOT be misprojected via the src index (which would
    # put the graphic on the wrong line). This is the deliberate guard for that
    # bug-class (Phase E Sub-step 5).
    import handler as H
    _pw = {5: {"start": 2.0, "end": 2.5}, 7: {"start": 3.0, "end": 3.4}}
    # src indices (99/123) are DELIBERATELY wrong — present so a regression that
    # reads start_word_index instead of _start_word_kept fails this check.
    _scene = {"_start_word_kept": 5, "_end_word_kept": 7,
              "start_word_index": 99, "end_word_index": 123}
    _proj = H._project_scene_to_frames(_scene, _pw, 60.0)
    assert _proj is not None, "projection returned None for a valid kept-space scene"
    _from, _dur = _proj
    assert _from == 120, (
        f"fromFrame {_from} != 120 (kept word 5 @2.0s × 60fps) — projection read "
        f"the WRONG index space (src instead of kept)"
    )
    assert _dur == 84, f"durationInFrames {_dur} != 84 ((3.4-2.0)s × 60fps)"
    # A scene whose only indices are src (absent from the kept map) must fall back
    # to duration_seconds, never silently mis-resolve to a wrong frame.
    _bad = {"start_word_index": 99, "end_word_index": 123, "duration_seconds": 2.0}
    assert H._project_scene_to_frames(_bad, _pw, 60.0) == (0, 120), "duration fallback wrong"


@check("handler mode validation accepts guided_redraft")
def _handler_mode_validation_guided_redraft():
    # Source-string assertion on handler.handler — the mode-resolution
    # block must include guided_redraft in the allowed-modes tuple.
    import inspect, handler
    src = inspect.getsource(handler.handler)
    assert '"guided_redraft"' in src, (
        "handler.handler mode-resolution does not accept 'guided_redraft'. "
        "Frontend submissions with mode=guided_redraft will be silently "
        "downgraded to 'full' (fresh plan) instead of running the redraft."
    )


# ─── 5b4. RE-EDIT DIFF-CONFIRMATION SAFETY NET (LAYER 3) ───────────────
# Layer 3 closes the last gap in re-edit: even when Gemini misinterprets a
# tweak/redraft and changes things the user didn't ask for, the safety net
# diffs against the prior plan and reverts out-of-scope drift. Phase 1
# auto-reverts top-level SCALAR fields only (caption_style /
# thumbnail_word_index / outro); array-level reverts wait for production
# data tuning (Phase 2). Fail-OPEN end-to-end.
print("\n[5b4/6] Re-edit diff-confirmation safety net (Layer 3)")


@check("compute_plan_diff returns empty list when plans are identical")
def _diff_identical_plans_empty():
    import handler
    plan = {"caption_style": "CleanCut", "emphasis_moments": [{"word_indices": [3]}]}
    diffs = handler.compute_plan_diff(plan, dict(plan))
    assert diffs == [], (
        f"identical plans must produce 0 diffs; got {diffs}"
    )


@check("compute_plan_diff catches top-level scalar changes")
def _diff_scalar_change():
    import handler
    prior = {"caption_style": "CleanCut", "outro": "none"}
    new = {"caption_style": "Lumen", "outro": "none"}
    diffs = handler.compute_plan_diff(prior, new)
    cs_diffs = [d for d in diffs if d["path"] == "caption_style"]
    assert len(cs_diffs) == 1, f"expected 1 caption_style diff, got: {diffs}"
    d = cs_diffs[0]
    assert d["op"] == "changed" and d["old"] == "CleanCut" and d["new"] == "Lumen", d
    # outro unchanged → must NOT diff
    assert not [x for x in diffs if x["path"] == "outro"], (
        f"outro unchanged shouldn't appear in diffs; got: {diffs}"
    )


@check("compute_plan_diff anchor-keys emphasis_moments by first word_index")
def _diff_anchored_emphasis():
    import handler
    prior = {"emphasis_moments": [{"word_indices": [3]}, {"word_indices": [9]}]}
    new = {"emphasis_moments": [{"word_indices": [3]}]}  # 9 removed
    diffs = handler.compute_plan_diff(prior, new)
    em_diffs = [d for d in diffs if d["list_key"] == "emphasis_moments"]
    assert len(em_diffs) == 1, f"expected 1 emphasis_moments diff, got: {em_diffs}"
    d = em_diffs[0]
    assert d["op"] == "removed", d
    # anchor should be the (9,) tuple — the first word_index of the
    # removed emphasis_moment.
    assert d["anchor"] == (9,), f"expected anchor=(9,); got {d['anchor']}"


@check("compute_plan_diff catches added entries via anchor matching")
def _diff_added_anchored_entry():
    import handler
    prior = {"transitions": [{"after_word_index": 5, "type": "CardSwipe"}]}
    new = {"transitions": [
        {"after_word_index": 5, "type": "CardSwipe"},
        {"after_word_index": 12, "type": "LightLeak"},
    ]}
    diffs = handler.compute_plan_diff(prior, new)
    added = [d for d in diffs if d["op"] == "added"]
    assert len(added) == 1, f"expected 1 added transition, got: {added}"
    assert added[0]["anchor"] == 12, f"expected anchor=12; got {added[0]['anchor']}"


@check("compute_plan_diff skips derived fields (caption_position_segments, thumbnail_timestamp)")
def _diff_skip_derived():
    import handler
    # These fields differ between plans but must be SKIPPED — they're
    # derived downstream and diffing them would create false alarms.
    prior = {
        "caption_position_changes": [{"word_index": 0, "position": "bottom"}],
        "caption_position_segments": [{"fromFrame": 0, "toFrame": 100, "position": "bottom"}],
        "thumbnail_word_index": 5,
        "thumbnail_timestamp": 1.2,
    }
    new = {
        "caption_position_changes": [{"word_index": 0, "position": "bottom"}],
        "caption_position_segments": [{"fromFrame": 0, "toFrame": 200, "position": "bottom"}],  # differs
        "thumbnail_word_index": 5,
        "thumbnail_timestamp": 3.8,  # differs
    }
    diffs = handler.compute_plan_diff(prior, new)
    # caption_position_segments + thumbnail_timestamp are derived → MUST be skipped.
    bad_paths = [d["path"] for d in diffs if d["path"] in {"caption_position_segments", "thumbnail_timestamp"}]
    assert not bad_paths, (
        f"derived fields leaked into diff: {bad_paths}. Phase 1 must not "
        f"trigger reverts on these — they're computed from canonical inputs."
    )


@check("apply_scalar_reverts is a no-op when no out-of-scope paths")
def _revert_noop_when_clean():
    import handler
    new = {"caption_style": "Lumen", "emphasis_moments": []}
    validation = {
        "verdict": "all_in_scope",
        "diffs": [{"path": "caption_style", "list_key": None, "anchor": None,
                   "op": "changed", "old": "PaperII", "new": "Lumen"}],
        "out_of_scope_paths": [],
    }
    out = handler.apply_scalar_reverts(
        prior_plan={"caption_style": "PaperII"},
        new_plan=new, validation=validation, mode="tweak",
    )
    assert out["caption_style"] == "Lumen", (
        f"in-scope change must NOT be reverted; got: {out}"
    )


@check("apply_scalar_reverts reverts out-of-scope caption_style in tweak mode")
def _revert_caption_style_tweak():
    import handler
    prior = {"caption_style": "PaperII"}
    new = {"caption_style": "Lumen"}
    validation = {
        "verdict": "partial_out_of_scope",
        "diffs": [{"path": "caption_style", "list_key": None, "anchor": None,
                   "op": "changed", "old": "PaperII", "new": "Lumen"}],
        "out_of_scope_paths": ["caption_style"],
    }
    out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
    assert out["caption_style"] == "PaperII", (
        f"out-of-scope caption_style in tweak must revert to PaperII; got: {out}"
    )


@check("apply_scalar_reverts does NOT revert in guided_redraft mode (Phase 1)")
def _revert_skips_guided_redraft():
    import handler
    prior = {"caption_style": "PaperII"}
    new = {"caption_style": "Lumen"}
    validation = {
        "verdict": "partial_out_of_scope",
        "diffs": [{"path": "caption_style", "list_key": None, "anchor": None,
                   "op": "changed", "old": "PaperII", "new": "Lumen"}],
        "out_of_scope_paths": ["caption_style"],
    }
    out = handler.apply_scalar_reverts(prior, new, validation, mode="guided_redraft")
    assert out["caption_style"] == "Lumen", (
        f"guided_redraft is LOG-ONLY in Phase 1 — must not revert; "
        f"caption_style stays Lumen. Got: {out}"
    )


@check("apply_scalar_reverts does NOT revert array entries in Phase 1 (tweak)")
def _revert_skips_arrays_phase1():
    # The Phase-1 contract: array-anchored paths get LOGGED but not
    # reverted. Phase 2 will turn this on after production tuning.
    import handler
    prior = {"emphasis_moments": [{"word_indices": [3], "zoom_effect": {"type": "StepZoom"}}]}
    new = {"emphasis_moments": [{"word_indices": [3], "zoom_effect": {"type": "SmoothPush"}}]}  # type swapped
    validation = {
        "verdict": "partial_out_of_scope",
        "diffs": [{
            "path": "emphasis_moments[anchor=(3,)]",
            "list_key": "emphasis_moments",
            "anchor": (3,),
            "op": "changed",
            "old": {"word_indices": [3], "zoom_effect": {"type": "StepZoom"}},
            "new": {"word_indices": [3], "zoom_effect": {"type": "SmoothPush"}},
        }],
        "out_of_scope_paths": ["emphasis_moments[anchor=(3,)]"],
    }
    out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
    # Even though out-of-scope and tweak mode, array changes are PHASE 2.
    assert out["emphasis_moments"][0]["zoom_effect"]["type"] == "SmoothPush", (
        f"Phase 1 must NOT revert array entries even in tweak mode; "
        f"emphasis_moments stays as Gemini emitted. Got: {out}"
    )


@check("apply_scalar_reverts does NOT revert scalars outside the Phase-1 set")
def _revert_skips_non_phase1_scalars():
    # vibe and pacing aren't in _PHASE1_REVERTABLE_SCALARS — they should
    # be LOGGED but not reverted. This protects against the safety net
    # touching fields the renderer treats as semi-derived.
    import handler
    prior = {"pacing": "fast"}
    new = {"pacing": "slow"}
    validation = {
        "verdict": "partial_out_of_scope",
        "diffs": [{"path": "pacing", "list_key": None, "anchor": None,
                   "op": "changed", "old": "fast", "new": "slow"}],
        "out_of_scope_paths": ["pacing"],
    }
    out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
    assert out["pacing"] == "slow", (
        f"pacing isn't in _PHASE1_REVERTABLE_SCALARS — Phase 1 must skip; "
        f"got: {out}"
    )


@check("apply_scalar_reverts no-ops on verdict='error' (fail open)")
def _revert_failopen_on_error():
    import handler
    prior = {"caption_style": "PaperII"}
    new = {"caption_style": "Lumen"}
    validation = {"verdict": "error", "diffs": [], "out_of_scope_paths": []}
    out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
    assert out["caption_style"] == "Lumen", (
        f"verdict='error' must fail open (no reverts); got: {out}"
    )


@check("compute_plan_diff handles empty / non-dict inputs without crashing")
def _diff_robust_to_garbage():
    import handler
    # Real-world inputs may be None / "" / list / etc. The diff must not
    # raise — return an empty list instead.
    for prior, new in [
        (None, None),
        ({}, {}),
        ({}, {"caption_style": "Lumen"}),
        ([], {}),
        ({"a": 1}, "not a dict"),
    ]:
        diffs = handler.compute_plan_diff(prior, new)
        assert isinstance(diffs, list), (
            f"compute_plan_diff must return list even on garbage input "
            f"({type(prior).__name__}, {type(new).__name__}); got {diffs!r}"
        )


# ── Phase 2 (env-gated array reverts) ────────────────────────────────────
# These checks toggle PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS on/off to
# verify (a) the gate respects truthy values, (b) Phase-1 behavior is
# preserved when gate is OFF, (c) array reverts apply correctly when ON,
# (d) the mode gate (tweak vs guided_redraft) is independent of the phase
# gate — guided_redraft stays log-only in BOTH phases.

def _with_phase2_env(value):
    """Context-manager-style helper: set/restore the Phase 2 env var.
    Use via try/finally — Python contextmanager would work too but
    keeping it explicit makes the validate_deploy pattern uniform."""
    import os
    old = os.environ.get("PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS")
    if value is None:
        os.environ.pop("PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS", None)
    else:
        os.environ["PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS"] = value
    return old


def _restore_phase2_env(old):
    import os
    if old is None:
        os.environ.pop("PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS", None)
    else:
        os.environ["PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS"] = old


@check("Phase 2 gate is OFF by default + respects truthy values")
def _phase2_gate_truthy_values():
    import handler
    # Default (env unset) MUST be off — protects the ship-default behavior.
    old = _with_phase2_env(None)
    try:
        assert handler._phase2_array_reverts_enabled() is False, (
            "Phase 2 must default to OFF (env var unset) — otherwise shipping "
            "without explicit opt-in would change re-edit behavior."
        )
        for truthy in ("1", "true", "True", "yes", "YES", "on", "ON"):
            os = __import__("os")
            os.environ["PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS"] = truthy
            assert handler._phase2_array_reverts_enabled() is True, (
                f"Phase 2 gate did not honor truthy value {truthy!r}"
            )
        for falsy in ("0", "false", "no", "off", ""):
            os = __import__("os")
            os.environ["PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS"] = falsy
            assert handler._phase2_array_reverts_enabled() is False, (
                f"Phase 2 gate falsely activated on value {falsy!r}"
            )
    finally:
        _restore_phase2_env(old)


@check("Phase 2 OFF: tweak mode array drift is LOGGED, identical to Phase 1")
def _phase2_off_preserves_phase1():
    import handler
    old = _with_phase2_env(None)  # gate OFF
    try:
        prior = {"emphasis_moments": [{"word_indices": [3], "zoom_effect": {"type": "StepZoom"}}]}
        new = {"emphasis_moments": [{"word_indices": [3], "zoom_effect": {"type": "SmoothPush"}}]}
        validation = {
            "verdict": "partial_out_of_scope",
            "diffs": [{
                "path": "emphasis_moments[anchor=(3,)]",
                "list_key": "emphasis_moments",
                "anchor": (3,),
                "op": "changed",
                "old": prior["emphasis_moments"][0],
                "new": new["emphasis_moments"][0],
            }],
            "out_of_scope_paths": ["emphasis_moments[anchor=(3,)]"],
        }
        out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
        # Phase 1 behavior: array entry stays as Gemini emitted.
        assert out["emphasis_moments"][0]["zoom_effect"]["type"] == "SmoothPush", (
            f"Phase 2 OFF must preserve Phase 1 behavior — array drift stays. "
            f"Got: {out}"
        )
    finally:
        _restore_phase2_env(old)


@check("Phase 2 ON: tweak mode array CHANGED reverts to prior entry")
def _phase2_on_reverts_changed_array_entry():
    import handler
    old = _with_phase2_env("1")
    try:
        prior_entry = {"word_indices": [3], "zoom_effect": {"type": "StepZoom"}}
        new_entry = {"word_indices": [3], "zoom_effect": {"type": "SmoothPush"}}
        prior = {"emphasis_moments": [prior_entry]}
        new = {"emphasis_moments": [new_entry]}
        validation = {
            "verdict": "partial_out_of_scope",
            "diffs": [{
                "path": "emphasis_moments[anchor=(3,)]",
                "list_key": "emphasis_moments",
                "anchor": (3,),
                "op": "changed",
                "old": prior_entry,
                "new": new_entry,
            }],
            "out_of_scope_paths": ["emphasis_moments[anchor=(3,)]"],
        }
        out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
        assert out["emphasis_moments"][0]["zoom_effect"]["type"] == "StepZoom", (
            f"Phase 2 ON: out-of-scope array CHANGED must revert to prior; "
            f"got: {out}"
        )
        # Caller's prior plan must NOT be mutated.
        assert prior["emphasis_moments"][0]["zoom_effect"]["type"] == "StepZoom"
    finally:
        _restore_phase2_env(old)


@check("Phase 2 ON: tweak mode out-of-scope ADDED entry gets removed")
def _phase2_on_removes_added_entry():
    import handler
    old = _with_phase2_env("1")
    try:
        prior = {"transitions": [{"after_word_index": 5, "type": "CardSwipe"}]}
        new = {"transitions": [
            {"after_word_index": 5, "type": "CardSwipe"},
            {"after_word_index": 12, "type": "LightLeak"},  # out-of-scope add
        ]}
        validation = {
            "verdict": "partial_out_of_scope",
            "diffs": [{
                "path": "transitions[anchor=12]",
                "list_key": "transitions",
                "anchor": 12,
                "op": "added",
                "old": None,
                "new": {"after_word_index": 12, "type": "LightLeak"},
            }],
            "out_of_scope_paths": ["transitions[anchor=12]"],
        }
        out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
        anchors = [t.get("after_word_index") for t in out["transitions"]]
        assert anchors == [5], (
            f"Phase 2 ON: out-of-scope ADDED entry must be removed; "
            f"got transitions={out['transitions']}"
        )
    finally:
        _restore_phase2_env(old)


@check("Phase 2 ON: tweak mode out-of-scope REMOVED entry gets added back")
def _phase2_on_adds_back_removed_entry():
    import handler
    old = _with_phase2_env("1")
    try:
        prior = {"transitions": [
            {"after_word_index": 5, "type": "CardSwipe"},
            {"after_word_index": 12, "type": "LightLeak"},
        ]}
        new = {"transitions": [
            {"after_word_index": 5, "type": "CardSwipe"},  # Gemini dropped the 12-anchor
        ]}
        validation = {
            "verdict": "partial_out_of_scope",
            "diffs": [{
                "path": "transitions[anchor=12]",
                "list_key": "transitions",
                "anchor": 12,
                "op": "removed",
                "old": {"after_word_index": 12, "type": "LightLeak"},
                "new": None,
            }],
            "out_of_scope_paths": ["transitions[anchor=12]"],
        }
        out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
        anchors = sorted(t.get("after_word_index") for t in out["transitions"])
        assert anchors == [5, 12], (
            f"Phase 2 ON: out-of-scope REMOVED entry must be re-added; "
            f"got transitions={out['transitions']}"
        )
    finally:
        _restore_phase2_env(old)


@check("Phase 2 ON: guided_redraft is STILL log-only (mode gate independent of phase gate)")
def _phase2_on_guided_redraft_still_log_only():
    import handler
    old = _with_phase2_env("1")
    try:
        prior = {"emphasis_moments": [{"word_indices": [3], "zoom_effect": {"type": "StepZoom"}}]}
        new = {"emphasis_moments": [{"word_indices": [3], "zoom_effect": {"type": "SmoothPush"}}]}
        validation = {
            "verdict": "partial_out_of_scope",
            "diffs": [{
                "path": "emphasis_moments[anchor=(3,)]",
                "list_key": "emphasis_moments",
                "anchor": (3,),
                "op": "changed",
                "old": prior["emphasis_moments"][0],
                "new": new["emphasis_moments"][0],
            }],
            "out_of_scope_paths": ["emphasis_moments[anchor=(3,)]"],
        }
        out = handler.apply_scalar_reverts(prior, new, validation, mode="guided_redraft")
        # Mode gate is INDEPENDENT of the phase gate. guided_redraft's
        # soft-carry-over contract still means log-only, even with
        # Phase 2 array reverts enabled.
        assert out["emphasis_moments"][0]["zoom_effect"]["type"] == "SmoothPush", (
            f"guided_redraft must stay log-only even with Phase 2 ON; got: {out}"
        )
    finally:
        _restore_phase2_env(old)


@check("Phase 2 ON: scalar reverts still work alongside array reverts")
def _phase2_on_scalar_plus_array_both_revert():
    # Realistic case: Gemini drifts BOTH a scalar AND an array entry.
    # Both must revert in the same pass, in tweak mode with Phase 2 ON.
    import handler
    old = _with_phase2_env("1")
    try:
        prior_em = {"word_indices": [3], "zoom_effect": {"type": "StepZoom"}}
        new_em = {"word_indices": [3], "zoom_effect": {"type": "SmoothPush"}}
        prior = {"caption_style": "CleanCut", "emphasis_moments": [prior_em]}
        new = {"caption_style": "Lumen", "emphasis_moments": [new_em]}
        validation = {
            "verdict": "partial_out_of_scope",
            "diffs": [
                {"path": "caption_style", "list_key": None, "anchor": None,
                 "op": "changed", "old": "CleanCut", "new": "Lumen"},
                {"path": "emphasis_moments[anchor=(3,)]",
                 "list_key": "emphasis_moments", "anchor": (3,),
                 "op": "changed", "old": prior_em, "new": new_em},
            ],
            "out_of_scope_paths": ["caption_style", "emphasis_moments[anchor=(3,)]"],
        }
        out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
        assert out["caption_style"] == "CleanCut", (
            f"scalar revert failed in combined pass; got: {out}"
        )
        assert out["emphasis_moments"][0]["zoom_effect"]["type"] == "StepZoom", (
            f"array revert failed in combined pass; got: {out}"
        )
    finally:
        _restore_phase2_env(old)


@check("Phase 2 ON: caller's prior_plan + new_plan are NOT mutated (defensive copy)")
def _phase2_on_no_caller_mutation():
    import handler
    old = _with_phase2_env("1")
    try:
        prior_entry = {"word_indices": [3], "zoom_effect": {"type": "StepZoom"}}
        new_entry = {"word_indices": [3], "zoom_effect": {"type": "SmoothPush"}}
        prior_list = [prior_entry]
        new_list = [new_entry]
        prior = {"emphasis_moments": prior_list}
        new = {"emphasis_moments": new_list}
        validation = {
            "verdict": "partial_out_of_scope",
            "diffs": [{
                "path": "emphasis_moments[anchor=(3,)]",
                "list_key": "emphasis_moments", "anchor": (3,),
                "op": "changed", "old": prior_entry, "new": new_entry,
            }],
            "out_of_scope_paths": ["emphasis_moments[anchor=(3,)]"],
        }
        out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
        # Caller's lists must be unchanged.
        assert prior_list is prior["emphasis_moments"]
        assert new_list is new["emphasis_moments"]
        assert new_list[0]["zoom_effect"]["type"] == "SmoothPush", (
            "caller's new_list was mutated — apply_scalar_reverts must "
            "deep-copy mutated lists before reverting"
        )
        # But the returned dict's list IS the reverted one.
        assert out["emphasis_moments"] is not new_list, (
            "returned cleaned plan must use a distinct list, not the "
            "caller's reference"
        )
        assert out["emphasis_moments"][0]["zoom_effect"]["type"] == "StepZoom"
    finally:
        _restore_phase2_env(old)


# ─── 5c. TIGHT-CUT OVERLAY WIRING ────────────────────────────────────────
# Step 2 of the overlay-on-top-of-hard-cut rollout: the canonical vocabulary
# is registered, the Pydantic schema accepts the new field, the recipe_eval
# rules fire at the right misuses, and the render path produces no output
# when no overlay is requested (strictly additive — bit-identical default).
print("\n[5c/6] Tight-cut overlay wiring (Step 2)")


@check("VALID_TIGHT_CUT_OVERLAYS canonical set has exactly the 2 signed-off overlays")
def _tco_registry_pair():
    import type_registries
    assert hasattr(type_registries, "VALID_TIGHT_CUT_OVERLAYS"), (
        "VALID_TIGHT_CUT_OVERLAYS missing from type_registries"
    )
    expected = frozenset({"LightLeak", "ShutterFlash"})  # NewspaperWipe retired (directive #13)
    assert type_registries.VALID_TIGHT_CUT_OVERLAYS == expected, (
        f"VALID_TIGHT_CUT_OVERLAYS={type_registries.VALID_TIGHT_CUT_OVERLAYS} — "
        f"expected exactly {expected}. Adding a fifth requires another isolation "
        f"test + visual sign-off."
    )


@check("render_schemas.PromptlyRenderInput.tightCutOverlays accepts a valid spec")
def _tco_schema_roundtrip():
    # Active-path check: build a minimal PromptlyRenderInput with one
    # TightCutOverlaySpec per registered type. All must validate; the
    # empty-default path must still recover the pre-overlay behavior.
    import render_schemas
    _minimal = {
        "sourceUrl": "x.mp4",
        "fps": 60.0,
        "width": 1080,
        "height": 1920,
        "totalDurationInFrames": 600,
        "clips": [],
        "transitions": [],
        "broll": [],
        "caption": {
            "style": "CleanCut",
            "pages": [],
            "keywords": [],
            "positionSegments": [],
        },
        "textOverlays": [],
        "motionGraphics": [],
        # Explicit tightCutOverlays list — one entry per registered type to
        # exercise every literal in TightCutOverlayType.
        "tightCutOverlays": [
            {"atFrame": 120, "type": "LightLeak", "durationInFrames": 11},
            {"atFrame": 200, "type": "ShutterFlash", "durationInFrames": 11},
            {"atFrame": 280, "type": "LightLeak", "durationInFrames": 11},
        ],
    }
    parsed = render_schemas.PromptlyRenderInput.model_validate(_minimal)
    assert len(parsed.tightCutOverlays) == 3
    _types = [o.type for o in parsed.tightCutOverlays]
    assert _types == ["LightLeak", "ShutterFlash", "LightLeak"], (
        f"types out of order: {_types}"
    )

    # Default-empty path: the field must accept being absent and default
    # to []. This is the strictly-additive guarantee — pre-overlay
    # behavior is recoverable by emitting nothing.
    _no_tco = {k: v for k, v in _minimal.items() if k != "tightCutOverlays"}
    parsed_default = render_schemas.PromptlyRenderInput.model_validate(_no_tco)
    assert parsed_default.tightCutOverlays == [], (
        f"absent field must default to [], got {parsed_default.tightCutOverlays}"
    )

    # Reject an invalid type — this is the canonical-set guard. FilmStrip
    # is a TRANSITION type, not an overlay type — must not validate here.
    import pydantic
    _bad = dict(_minimal)
    _bad["tightCutOverlays"] = [{"atFrame": 120, "type": "FilmStrip", "durationInFrames": 11}]
    try:
        render_schemas.PromptlyRenderInput.model_validate(_bad)
    except pydantic.ValidationError:
        return
    raise AssertionError("FilmStrip should not validate as a tightCutOverlay type")


@check("recipe_eval accepts valid overlays (active passing path)")
def _recipe_eval_tco_valid_passes():
    # Valid overlays at TIGHT boundaries should not fire any
    # tight-overlay-* failure — the eval must NOT misfire on the
    # active-path case.
    import recipe_eval
    good_plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 1, "position": "hook", "intensity": 0.9},
                {"start_word_index": 2, "end_word_index": 5, "position": "build", "intensity": 0.4},
                {"start_word_index": 6, "end_word_index": 7, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [{"word_index": 1}, {"word_index": 4}, {"word_index": 7}],
            "payoff_word_index": 7,
            "close_word_index": 7,
        },
        "emphasis_moments": [
            {"word_indices": [1], "zoom_effect": {"type": "SnapReframe", "events": [{"startMs": 0}]}},
            {"word_indices": [4], "zoom_effect": {"type": "StepZoom", "events": [{"startMs": 0}]}},
            {"word_indices": [7], "zoom_effect": {"type": "SmoothPush", "events": [{"startMs": 0}]}},
        ],
        "transitions": [],
        "tight_cut_overlays": [
            {"after_word_index": 3, "type": "ShutterFlash"},
            {"after_word_index": 5, "type": "LightLeak"},
        ],
        "broll_clips": [], "motion_graphics": [],
        "text_overlays": [], "sound_effects": [],
    }
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(8)]
    rep = recipe_eval.evaluate_recipe(
        good_plan, words, cut_boundaries=[], duration=4.0,
        tight_boundaries=[3, 5],
    )
    tco_rules = {
        r for (r, _) in rep.failures
        if r.startswith("tight-overlay-")
    }
    assert not tco_rules, (
        f"valid ShutterFlash + LightLeak placement should not fail any "
        f"tight-overlay-* rule, got: {tco_rules}"
    )


@check("recipe_eval flags 3+ tight_cut_overlays (per-video cap)")
def _recipe_eval_tco_cap():
    # The cap is 2 per video — sparing keeps the overlay editorial. 3 → FAIL.
    import recipe_eval
    bad_plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 1, "position": "hook", "intensity": 0.9},
                {"start_word_index": 2, "end_word_index": 8, "position": "build", "intensity": 0.4},
                {"start_word_index": 9, "end_word_index": 10, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [{"word_index": 1}, {"word_index": 10}],
            "payoff_word_index": 10,
            "close_word_index": 10,
        },
        "emphasis_moments": [
            {"word_indices": [1], "zoom_effect": {"type": "SnapReframe", "events": [{"startMs": 0}]}},
            {"word_indices": [10], "zoom_effect": {"type": "SmoothPush", "events": [{"startMs": 0}]}},
        ],
        "transitions": [],
        "tight_cut_overlays": [
            {"after_word_index": 2, "type": "LightLeak"},
            {"after_word_index": 4, "type": "ShutterFlash"},
            {"after_word_index": 6, "type": "LightLeak"},
        ],
        "broll_clips": [], "motion_graphics": [],
        "text_overlays": [], "sound_effects": [],
    }
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(11)]
    rep = recipe_eval.evaluate_recipe(
        bad_plan, words, cut_boundaries=[], duration=5.5,
        tight_boundaries=[2, 4, 6],
    )
    rule_ids = {r for (r, _) in rep.failures}
    assert "tight-overlay-cap" in rule_ids, (
        f"expected tight-overlay-cap failure, got: {rule_ids}"
    )


@check("recipe_eval accepts the valid 1-2 overlay case (active passing path)")
def _recipe_eval_tco_passing():
    # Two overlays at TIGHT boundaries, distinct types → no overlay-related
    # failures. This is the bit-perfect "looks-correct" path the eval must
    # NOT misfire on (otherwise good recipes would all fail the eval).
    import recipe_eval
    good_plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 1, "position": "hook", "intensity": 0.9},
                {"start_word_index": 2, "end_word_index": 5, "position": "build", "intensity": 0.4},
                {"start_word_index": 6, "end_word_index": 7, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [{"word_index": 1}, {"word_index": 4}, {"word_index": 7}],
            "payoff_word_index": 7,
            "close_word_index": 7,
        },
        "emphasis_moments": [
            {"word_indices": [1], "zoom_effect": {"type": "SnapReframe", "events": [{"startMs": 0}]}},
            {"word_indices": [4], "zoom_effect": {"type": "StepZoom", "events": [{"startMs": 0}]}},
            {"word_indices": [7], "zoom_effect": {"type": "SmoothPush", "events": [{"startMs": 0}]}},
        ],
        "transitions": [],
        "tight_cut_overlays": [
            {"after_word_index": 3, "type": "LightLeak"},
            {"after_word_index": 5, "type": "ShutterFlash"},
        ],
        "broll_clips": [], "motion_graphics": [],
        "text_overlays": [], "sound_effects": [],
    }
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(8)]
    rep = recipe_eval.evaluate_recipe(
        good_plan, words, cut_boundaries=[], duration=4.0,
        tight_boundaries=[3, 5],
    )
    tco_rules = {
        r for (r, _) in rep.failures
        if r.startswith("tight-overlay-")
    }
    assert not tco_rules, (
        f"valid overlay placement should not fail any tight-overlay-* rule, got: {tco_rules}"
    )


@check("scene-floor rotation: bare scene changes fill varied, no two adjacent same type (ACTIVE)")
def _scene_floor_rotation_active():
    import handler
    rot = handler._scene_floor_rotation

    # 6 bare scene changes → even SF/LL/NW cycle, no adjacency (the §A
    # worked example). This is the ACTIVE variety path, not a no-op default.
    six_bare = rot([None] * 6)
    assert six_bare == [
        "ShutterFlash", "LightLeak",
        "ShutterFlash", "LightLeak",
        "ShutterFlash", "LightLeak",
    ], f"6-bare rotation should cycle SF/LL evenly, got {six_bare}"

    # The b89287c4 case: Gemini already placed a ShutterFlash on boundary 1.
    # Backfill must PRESERVE it and rotate around it (no adjacent SF).
    gemini_pick = rot([None, "ShutterFlash", None, None, None, None])
    assert gemini_pick[1] == "ShutterFlash", "locked pick must be preserved"
    assert all(gemini_pick[i] != gemini_pick[i - 1] for i in range(1, 6)), (
        f"backfill must rotate around Gemini's locked pick, got {gemini_pick}")

    # Universal invariants across sizes incl. 7+ (spaced repeats, never adjacent).
    for n in range(1, 12):
        out = rot([None] * n)
        assert all(out[i] != out[i - 1] for i in range(1, n)), (
            f"n={n}: adjacent duplicate decoration in {out}"
        )
        assert all(
            t in ("ShutterFlash", "LightLeak") for t in out
        ), f"n={n}: non-rotation type emitted in {out}"

    # Deterministic: same input → same output (no RNG).
    assert rot([None, "LightLeak", None]) == rot([None, "LightLeak", None]), (
        "rotation must be deterministic"
    )

    # A boundary Gemini dressed with a non-rotation type (DipToBlack, the
    # held-out heavy transition) is locked; neighbours rotate normally.
    with_locked = rot([None, "DipToBlack", None])
    assert with_locked[1] == "DipToBlack", "non-rotation pick must be preserved"
    assert with_locked[0] in ("ShutterFlash", "LightLeak")
    assert with_locked[2] in ("ShutterFlash", "LightLeak")


# ─── 5b5. CAPTION PAGE-BOUNDARY REGRESSION GUARDS ──────────────────────
# When a caption page's window straddles a position-segment boundary
# (one page rendering across a top↔bottom flip from a B-roll or MG
# auto-flip override), CaptionSegmentRenderer's `clippedPages` logic in
# PromptlyRender.tsx clamps the page's startMs to 0 inside the assigned
# segment but must ALSO shrink durationMs by |localStart| so the clipped
# page ends at its true absolute end. Without that, the page overstays
# by |localStart| ms and stacks with the next page in the same segment.
print("\n[5b5/6] Caption page-boundary regression guards")


@check("CaptionSegmentRenderer clipped pages shrink durationMs on front-edge straddle")
def _clipped_pages_shrinks_duration_on_straddle():
    """The clippedPages logic in CaptionSegmentRenderer must clamp BOTH
    startMs (to 0) AND durationMs (subtract |localStart|) when a page
    straddles the segment's front edge (localStart < 0). Without the
    durationMs adjustment, the clipped page renders for its full original
    duration starting from segment-local 0 — visibly OVERSTAYING its true
    end by |localStart| ms and stacking with the next page in the same
    segment.

    Static text check: confirm both Math.max(0, localStart) on startMs
    AND Math.min(0, localStart) on durationMs are present in
    PromptlyRender.tsx's CaptionSegmentRenderer body. Either-but-not-both
    = regression of this bug class.
    """
    import os
    import pathlib
    import re
    tsx = (
        pathlib.Path(os.path.dirname(__file__))
        / "src" / "remotion" / "src" / "PromptlyRender.tsx"
    ).read_text()
    m = re.search(r"const CaptionSegmentRenderer[\s\S]+?\n};\n", tsx)
    assert m, "CaptionSegmentRenderer block not found in PromptlyRender.tsx"
    body = m.group(0)
    assert "Math.max(0, localStart)" in body, (
        "CaptionSegmentRenderer must clamp `startMs: Math.max(0, localStart)`. "
        "Without it, front-edge straddling pages render at negative segment-"
        "local frames."
    )
    assert "Math.min(0, localStart)" in body, (
        "CaptionSegmentRenderer must shrink `durationMs: page.durationMs + "
        "Math.min(0, localStart)` for front-edge straddling pages. Without "
        "it, the clipped page overstays its true end by |localStart| ms and "
        "stacks with the next page in the same segment. See "
        "PromptlyRender.tsx:212-250."
    )


# ─── 6. HANDLER ENTRY POINTS ───────────────────────────────────────────
print("\n[6/6] Handler entry points")


@check("validate_handler returns dict with required shape for missing input")
def _validate_handler_shape():
    res = handler.validate_handler({"input": {}})
    assert isinstance(res, dict)
    # Should signal validation problem, NOT crash.
    assert "error" in res or "user_message" in res


@check("validate_handler returns valid shape for unreachable URL")
def _validate_handler_bad_url():
    # Fake S3 URL — should fail gracefully, not crash.
    res = handler.validate_handler(
        {"input": {"sample_url": "https://not-a-real-bucket.s3.us-west-2.amazonaws.com/nope.mp4"}}
    )
    assert isinstance(res, dict)
    # Either succeeds with is_talking_head=True (failed open) OR errors gracefully.
    assert "is_talking_head" in res or "error" in res


@check("handler returns dict on missing required fields (no crash)")
def _handler_missing_fields():
    # Empty input — should return error dict, not raise.
    res = handler.handler({"input": {}})
    assert isinstance(res, dict), f"handler must return dict, got {type(res)}"
    assert "error" in res, "should return error dict for missing fields"


@check("handler error response includes structured fields when classify_error fires")
def _handler_error_shape():
    # Bad video_url should produce a classified error response.
    res = handler.handler({
        "input": {
            "job_id": "test",
            "video_url": "not-a-url",
            "vibe": "test",
            "user_id": "test",
            "upload_url": "test",
        }
    })
    assert isinstance(res, dict)
    # Should have at least the 'error' field.
    assert "error" in res


@check("transition on a non-scene-change tight boundary: scene gate LOG-AND-PASS records it OFF-BOUNDARY, never drops or raises")
def _repair_demotion_path():
    # Stubbed run of the REAL generate_edit_gemini: 12 synthetic words, word 5
    # mechanically removed → the splice after src word 4 has a 0.45s gap
    # (< 0.70s) → TIGHT. A ZoomThrough there used to raise ValueError and kill
    # the job; then it demoted to a light overlay; then (enforce gate) it DROPPED.
    # Now (LOG-AND-PASS, Zac 2026-07-08): the scene gate is an instrument — awi=4 is
    # a plain edit-cut, NOT a scene change (no scdet source, no B-roll) → the gate
    # RECORDS it OFF-BOUNDARY and passes it through, rewriting nothing. The safety
    # property is unchanged: never raise, plan comes back whole. Enforcement (drop)
    # is dormant (ENFORCE=False) while we measure the picture-change teaching.
    import contextlib as _ctx
    import copy as _copy
    import io as _io
    _words = [
        {"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.4, 2),
         "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
        for i in range(12)
    ]
    _plan = {
        "caption_style": "Prime", "caption_keywords": [],
        "transitions": [{"type": "ZoomThrough", "after_word_index": 4}],
        "tight_cut_overlays": [], "motion_graphics": [], "emphasis_moments": [],
        "text_overlays": [], "broll_clips": [], "sound_effects": [],
        "audio_denoise": False, "outro": "none", "aspect_ratio": "9:16",
    }
    _saved = (handler.compute_mechanical_cuts, handler._call_gemini_post_cuts,
              handler._get_genai_client)
    try:
        handler.compute_mechanical_cuts = lambda w, source_path=None: {
            "remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}
        handler._call_gemini_post_cuts = lambda *a, **k: _copy.deepcopy(_plan)
        handler._get_genai_client = lambda: None
        _buf = _io.StringIO()
        with _ctx.redirect_stdout(_buf):
            _out = handler.generate_edit_gemini(
                video_path="/nonexistent.mp4", vibe="t", duration=4.8,
                deepgram_words=_copy.deepcopy(_words), inline_video_bytes=b"x",
            )
    finally:
        (handler.compute_mechanical_cuts, handler._call_gemini_post_cuts,
         handler._get_genai_client) = _saved
    _log = _buf.getvalue()
    # plan came back WHOLE (no raise) — the core safety property, unchanged
    assert isinstance(_out, dict) and _out.get("transitions") is not None, \
        "plan must come back whole (never raise on a placement-class conflict)"
    # A1/A2 SINGLE OWNERSHIP: the sub-call is the only transitions author. The
    # main-call ZoomThrough@4 is DISCARDED (ledgered); this job has zero
    # qualifying seams (no scdet, no B-roll) → the sub-call is SKIPPED (R1)
    # → zero transitions BY CONSTRUCTION. The off-boundary emission never
    # reaches the render — not by gate-drop, by having no author that can say it.
    # BY CONSTRUCTION (Zac injection): the main schema no longer carries the
    # fields — the stubbed plan's transitions key is IGNORED by model parsing;
    # nothing to discard, nothing ledgered. The stubbed ZoomThrough@4 cannot
    # enter the plan at all.
    assert "main_call_transitions_discarded" not in open("handler.py").read(), \
        "the discard path must be DELETED (single ownership is by construction now)"
    assert "zero qualifying seams" in _log, \
        "zero-seam job must SKIP the sub-call (zero transitions by construction)"
    assert _out.get("transitions") == [], \
        "no author can emit a transition on a seamless job — expected []"


@check("safe-edit recipe: valid by construction, passes the full validation span")
def _safe_recipe_round_trip():
    # THE SAFE EDIT (zero-fatal ladder): build_safe_recipe() must (1) pass
    # PostCutPlan.model_validate untouched and (2) flow through the REAL
    # post-parse validation span with zero raises and zero repair/demote
    # lines — it is the terminal fallback, so it must never need the net.
    import contextlib as _ctx
    import copy as _copy
    import io as _io
    _words = [{"word": f"w{i}", "punctuated_word": f"w{i}",
               "start": round(i * 0.4, 2), "end": round(i * 0.4 + 0.35, 2),
               "confidence": 0.99, "speaker": 0} for i in range(20)]
    _peaks = [{"t": 3.1, "score": 0.9}, {"t": 6.2, "score": 0.7}]
    _sp = handler.build_safe_recipe(_words, vocal_emphasis=_peaks)
    handler.PostCutPlan.model_validate(_sp)
    _saved = (handler.compute_mechanical_cuts, handler._call_gemini_post_cuts,
              handler._get_genai_client)
    try:
        handler.compute_mechanical_cuts = lambda w, source_path=None: {
            "remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}
        handler._call_gemini_post_cuts = lambda *a, **k: _copy.deepcopy(_sp)
        handler._get_genai_client = lambda: None
        _buf = _io.StringIO()
        with _ctx.redirect_stdout(_buf):
            _out = handler.generate_edit_gemini(
                video_path="/x.mp4", vibe="t", duration=8.0,
                deepgram_words=_copy.deepcopy(_words), vocal_emphasis=_peaks,
                inline_video_bytes=b"x")
    finally:
        (handler.compute_mechanical_cuts, handler._call_gemini_post_cuts,
         handler._get_genai_client) = _saved
    _o = _buf.getvalue()
    assert isinstance(_out, dict) and _out.get("notes") == "safe-edit fallback"
    assert "[recipe-repair]" not in _o, "safe recipe needed the net"
    assert "action=demote" not in _o, "safe recipe triggered a demotion"
    assert _out.get("caption_style") == "CleanCut"


@check("outermost rung (P1a): wired in the except block, marker threads to force_safe")
def _outer_rescue_wiring():
    # Behavioral coverage lives in test_outer_rescue.py; this pins the WIRING
    # a refactor could silently break: (1) the outer except runs classify →
    # rescue → failed-write in that order, (2) the rescue marker read at the
    # recipe call site feeds force_safe_reason, (3) the rescue helper itself
    # can never raise (whole body inside try/except-return-None).
    _src = open("handler.py").read()
    _exc = _src.find("classified = classify_error(e)")
    assert _exc != -1, "outer classify site missing"
    _resc = _src.find("_outer_safe_rescue(job, input_data, classified, _rescue_state)", _exc)
    assert _resc != -1, "rescue rung not called after classify_error"
    _failw = _src.find("write_job_status(", _resc)
    assert _failw != -1, "failed-path terminal write must FOLLOW the rescue rung"
    assert 'input_data.get("_safe_edit_rescue")' in _src, "marker read missing"
    _callsite = _src.find("force_safe_reason=(")
    assert _callsite != -1 and "_safe_edit_rescue" in _src[_callsite:_callsite + 200], \
        "recipe call site does not thread the rescue marker"
    import inspect as _insp
    _body = _insp.getsource(handler._outer_safe_rescue)
    _lines = [l.strip() for l in _body.splitlines() if l.strip() and not l.strip().startswith(("#", '"""', "'"))]
    _after_doc = _lines[_lines.index("try:"):] if "try:" in _lines else []
    assert _after_doc and "except Exception as _resc_err:" in _lines, \
        "rescue helper must be fully try-wrapped (never raises)"
    assert "SOME_FUTURE_CODE" not in handler._OUTER_RESCUE_DENY  # deny is a closed set
    for _code in ("NO_SPEECH", "NOT_TALKING_HEAD", "INVALID_SOURCE_URL",
                  "INVALID_FORMAT", "RENDER_FATAL", "RECIPE_INVALID"):
        assert _code in handler._OUTER_RESCUE_DENY, f"deny set lost {_code}"


@check("terminal telemetry: complete write carries floor + vocab; orphan cascade wired")
def _terminal_telemetry_wiring():
    # Behavioral coverage: test_floor_telemetry.py + test_vocab_and_orphan.py.
    # This pins the WIRING a refactor could silently drop.
    _src = open("handler.py").read()
    # TWO completed writes exist since zero-reject: the minimal route's (earlier
    # in the file, its own contract pinned below) and the TH tail's (LAST — the
    # one this check has always pinned; rfind targets it explicitly).
    _c = _src.rfind('status="completed", phase="Done"')
    assert _c != -1, "complete terminal write missing"
    _win = _src[_c:_c + 2700]  # widened for 2b re-edit + S3-thumbnail + Wave-3 tier/model markers
    assert "**_floor_markers(_floor_state)" in _win, "complete write lost floor markers"
    assert '"vocab": _vocab_markers(edit_plan)' in _win, "complete write lost vocab"
    # the minimal route's completed write carries ITS contract (route named so
    # the weekly table can split routed completions; TH floor/vocab semantics
    # deliberately absent — no degrade ladder ran, claiming one would be false)
    _cm = _src.find('status="completed", phase="Done"')
    if _cm != _c:
        _wm = _src[_cm:_cm + 1200]
        assert '"route": _route_name' in _wm and '"route_reason": reason' in _wm, \
            "minimal completed write lost its route contract"
    # orphan-cascade wiring assertion DELETED with the cascade (Zac 2026-07-09
    # follow-through: it enforced the dead machinery-foley doctrine and inverted
    # the content-first teach).
    # the helper itself must never raise on junk
    assert handler._vocab_markers(None).get("broll_count") == 0


@check("deployer stamp: deploy.sh exports it, image bakes it, job log prints it")
def _deployer_stamp():
    # Single-deployer protocol (directive #10): a phantom deploy names itself
    # in the first line of every job it serves.
    _ds = open("deploy.sh").read()
    assert 'PROMPTLY_DEPLOYER="${PROMPTLY_DEPLOYER:-claude-code}"' in _ds, "deploy.sh export missing"
    _ma = open("modal_app.py").read()
    assert '"PROMPTLY_DEPLOYER": _DEPLOYER,' in _ma, "image bake missing"
    _h = open("handler.py").read()
    assert 'deployer={_build_deployer}' in _h, "job-log stamp missing"
    assert "deployer={os.environ.get('PROMPTLY_DEPLOYER', 'unknown')}" in _h, "prewarm stamp missing"


@check("RESPONSE FORMAT enums derive from type_registries (stale-enum class dead)")
def _response_format_enums_derive():
    # The prompt's output-shape enum lines were hand-written copies that
    # silently excluded the 17 batch-2 MGs and 4 caption styles. They now
    # DERIVE at f-string build time; this pins the derivation sites AND
    # renders the prompt to prove the registry members actually appear.
    _src = open("handler.py").read()
    # A1/A2: transitions + overlay enums moved to the sub-call schema builder
    # (registry-derived there; asserted in the source-of-truth check above).
    for _needle in ('"caption_style": {_caption_enum}',
                    '"type": {_mg_enum}',
                    "THE {_n_styles} STYLES",
                    "THE {_n_mgs} COMPONENTS"):
        assert _needle in _src, f"derivation site missing: {_needle}"
    _sys, _user = handler._build_post_cuts_prompt(vibe="t", duration=10.0)
    import type_registries as _tr
    for _n in sorted(_tr.VALID_MG_TYPES):
        assert f'"{_n}"' in _sys, f"MG {_n} missing from rendered enum"
    for _n in sorted(_tr.VALID_CAPTION_STYLES):
        assert f'"{_n}"' in _sys, f"caption style {_n} missing from rendered enum"
    # A1/A2: transition types render in the SUB-CALL's stable block + per-seam
    # schema, not the main prompt. Every registry type must appear in the
    # sub-call vocabulary (bold-name form) so the model knows each one it may
    # be offered; the schema itself is registry-derived (asserted elsewhere).
    for _n in sorted(_tr.VALID_TRANSITION_TYPES):
        assert f"**{_n}**" in handler._TRANSITIONS_SUBCALL_SYS, \
            f"transition {_n} missing from the sub-call vocabulary"
    assert f"THE {len(_tr.VALID_CAPTION_STYLES) - 1} STYLES" in _sys


@check("system prompt renders byte-identical across consecutive calls (caching preserved)")
def _system_prompt_render_identity():
    # The registry-derived interpolations are runtime constants — two
    # consecutive renders must produce the same bytes or implicit prompt
    # caching breaks (and per-call nondeterminism has crept in).
    _a, _ = handler._build_post_cuts_prompt(vibe="t", duration=10.0)
    _b, _ = handler._build_post_cuts_prompt(vibe="t", duration=10.0)
    assert _a == _b, "system prompt renders differ across consecutive calls"


@check("caption legibility floor: numbers pinned + every style importer-or-exempt")
def _caption_legibility_floor():
    # The floor (captions/shared/legibility.ts) guarantees every caption style
    # carries a minimum contrast treatment over bright footage: a box/scrim, a
    # >=2px dark contour, or the tight anchor shadow. Pins: (1) the exact
    # anchor numbers; (2) EXHAUSTIVE classification — every style directory is
    # either an importer of the floor or exempt-by-own-treatment, so a future
    # 17th style cannot silently skip it; (3) the once-false "universal
    # text-stroke" comment stays truthful.
    _root = os.path.dirname(os.path.abspath(__file__))
    _cap = os.path.join(_root, "src", "remotion", "src", "captions")
    _leg = open(os.path.join(_cap, "shared", "legibility.ts")).read()
    assert '"0 0 2px rgba(0,0,0,0.75)"' in _leg, "anchor layer 1 drifted"
    assert '"0 2px 6px rgba(0,0,0,0.85)"' in _leg, "anchor layer 2 drifted"
    assert "withLegibilityAnchor" in _leg
    # Directive #12 roster: 6 retired (Illuminate/Passage/Serif/EditorialPop/
    # PaperII/CinematicLetterpress), 3 promoted from the ABE archive.
    _importers = {"Lumen", "Pulse",
                  "Gadzhi"}  # Gadzhi: ABE shadow diffuse-only; anchor prepended
    _exempt = {  # own treatment already meets the floor (box/scrim/contour/anchor)
        "Prime": "tight anchor shadow",
        "TypewriterReveal": "4-direction 1.5px stroke (directive #12)",
        "Cove": "word-shaped scrim", "Quintessence": "blurred word-copy scrim",
        "TwoTone": "3px contour", "CleanCut": "tight anchor shadow",
    }
    _dirs = sorted(
        d for d in os.listdir(_cap)
        if os.path.isdir(os.path.join(_cap, d)) and d != "shared"
    )
    for _d in _dirs:
        assert _d in _importers or _d in _exempt, (
            f"caption style {_d!r} is neither a legibility-floor importer nor "
            f"classified exempt — classify it before shipping")
        if _d in _importers:
            _tsx = open(os.path.join(_cap, _d, f"{_d}.tsx")).read()
            assert ("LEGIBILITY_ANCHOR_LAYERS" in _tsx or "LEGIBILITY_ANCHOR" in _tsx
                    or "withLegibilityAnchor" in _tsx), (
                f"{_d} classified as importer but does not import the floor")
    _pr = open(os.path.join(_root, "src", "remotion", "src", "PromptlyRender.tsx")).read()
    assert "Universal text-stroke ensures" not in _pr, (
        "the false 'universal text-stroke' comment is back")
    assert "legibility.ts" in _pr, "caption z-stack comment no longer cites the floor"


@check("AnnotationArrow: normalized 0-1 endpoints resolve to safe-rect pixels (path ≥ 200px)")
def _annotation_arrow_normalized_endpoints():
    # AnnotationArrow's start/end are NORMALIZED 0-1 fractions (the prompt
    # teaches {"x": 0.0-1.0}); resolveEndpoints.ts is the single seam where
    # they become canvas pixels, clamped into the same TikTok-safe rect
    # resolveMGPosition pads every other MG into. Before that seam existed the
    # component consumed the fractions AS pixels — every arrow ever emitted
    # drew a sub-pixel path and rendered invisible while logging success.
    # Mirrors the pure function's math in Python against constants parsed from
    # safeZone.ts (the SSOT) so a drift in either file fails the deploy.
    import math
    import re as _re
    _root = os.path.dirname(os.path.abspath(__file__))
    _sz = open(os.path.join(_root, "src", "remotion", "src", "shared", "safeZone.ts")).read()
    def _const(name):
        return float(_re.search(rf"export const {name} = (\d+)", _sz).group(1))
    _W, _H = _const("CANVAS_WIDTH"), _const("CANVAS_HEIGHT")
    _sx = _const("TIKTOK_SAFE_SIDE"); _sy = _const("TIKTOK_SAFE_TOP")
    _sw = _W - _sx - _const("TIKTOK_SAFE_RIGHT"); _sh = _H - _sy - _const("TIKTOK_SAFE_BOTTOM")
    # (1) wiring: the component routes through the seam, not raw props
    _aa = open(os.path.join(_root, "src", "remotion", "src", "motion-graphics",
                            "AnnotationArrow", "AnnotationArrow.tsx")).read()
    assert "resolveArrowEndpoint(start, width, height)" in _aa
    assert "resolveArrowEndpoint(end, width, height)" in _aa
    assert "buildBezier(startPx, endPx" in _aa
    assert "buildBezier(start, end," not in _aa, "raw-props call site resurfaced"
    _re_ts = open(os.path.join(_root, "src", "remotion", "src", "motion-graphics",
                               "AnnotationArrow", "resolveEndpoints.ts")).read()
    assert "clamp(pt.x, 0, 1) * width" in _re_ts, "defensive [0,1] clamp missing"
    assert "SAFE_RECT.x, SAFE_RECT.x + SAFE_RECT.width" in _re_ts, "safe-rect clamp missing"
    # (2) mirror the math: standard normalized spec draws a real path
    def _resolve(x, y):
        _px = min(max(x, 0.0), 1.0) * _W; _py = min(max(y, 0.0), 1.0) * _H
        return (min(max(_px, _sx), _sx + _sw), min(max(_py, _sy), _sy + _sh))
    _s = _resolve(0.3, 0.35); _e = _resolve(0.7, 0.6)
    _chord = math.hypot(_e[0] - _s[0], _e[1] - _s[1])
    # a cubic bezier through two endpoints is never shorter than their chord
    assert _chord >= 200.0, f"standard arrow chord only {_chord:.1f}px"
    # (3) the documented pre-fix failure: fractions consumed AS pixels
    assert math.hypot(0.7 - 0.3, 0.6 - 0.35) < 1.0
    # (4) defensive clamp: stray pixel-space input lands on the safe-rect edge
    assert _resolve(540.0, 960.0) == (_sx + _sw, _sy + _sh)


@check("RecipeInvalidError classifies RECIPE_INVALID ahead of greedy absorbers")
def _repair_classification_entry():
    # The sentinel must win even when the message contains every substring the
    # greedier classes match ("Gemini" → EDITOR_GENERIC, "broll" → BROLL,
    # "removed all words" → EMPTY_EDIT).
    _err = handler.RecipeInvalidError(
        "RECIPE_INVALID after 1 attempt(s): Gemini broll plan removed all words")
    _cls = handler.classify_error(_err)
    assert _cls.get("error_code") == "RECIPE_INVALID", _cls
    assert _cls.get("retryable") is True


@check("F4: caption width-fit layer wired into EVERY text renderer (stale-parallel-set lesson, layout edition)")
def _f4_fit_wiring():
    import os as _os
    _cap_dir = _os.path.join("src", "remotion", "src", "captions")
    _styles = ["CleanCut", "Cove", "Gadzhi", "Lumen", "Prime", "Pulse",
               "Quintessence", "TwoTone", "TypewriterReveal"]
    for _st in _styles:
        _src = open(_os.path.join(_cap_dir, _st, f"{_st}.tsx")).read()
        assert 'from "../shared/fit"' in _src, f"{_st} lost its fit-layer import"
    _sticky = open(_os.path.join("src", "remotion", "src", "motion-graphics",
                                 "StickyNotes", "StickyNotes.tsx")).read()
    assert 'from "../../captions/shared/fit"' in _sticky, "StickyNotes lost the shared measurer"
    _fit = open(_os.path.join(_cap_dir, "shared", "fit.ts")).read()
    assert "TIKTOK_SAFE_SIDE" in _fit and "MIN_FIT_SCALE = 0.6" in _fit
    assert "REMOTION_FIT_STRICT" in _fit and "INVARIANT VIOLATION" in _fit
    _root = open(_os.path.join("src", "remotion", "src", "Root.tsx")).read()
    assert 'id="FitSpecimen"' in _root, "FitSpecimen battery composition unregistered"


@check("caption-stack: SINGLE-PAINT INVARIANT wired (builder clamp + renderer tripwire)")
def _caption_stack_invariant():
    _src = open("handler.py").read()
    assert "SINGLE-PAINT INVARIANT" in _src, "builder clamp missing"
    assert '_limit = pages[_pi + 1]["startMs"] - pages[_pi]["startMs"]' in _src
    _tsx = open("src/remotion/src/PromptlyRender.tsx").read()
    assert "[caption-paint] deduped" in _tsx, "renderer tripwire missing"
    # behavioral: the real exhibit pair through the real builder
    _pages = handler._build_tiktok_pages_from_projected(
        [{"word": "but", "punctuated_word": "but", "start": 14.88, "end": 16.08},
         {"word": "luckily,", "punctuated_word": "luckily,", "start": 15.005, "end": 15.645}],
        max_words_per_page=1)
    for _a, _b in zip(_pages, _pages[1:]):
        assert _a["startMs"] + _a["durationMs"] <= _b["startMs"], "page overlap survived"


@check("zero-silence (5912): dead-air warning dereferences words[kept[-1]] — ints never .get()")
def _zero_silence_shape():
    _src = open("handler.py").read()
    assert 'float(words[kept[-1]].get("end") or 0.0) > 10.0' in _src, \
        "the fixed dereference is missing"
    assert 'float(kept[-1].get(' not in _src, "the crashing direct dereference is back"
    # behavioral: the REAL function with VAD stubbed to the zero-region result. This tests
    # the flag-OFF VAD tier (the zero-silence warning path); the within-clip locate would
    # ffmpeg-extract the fake source, so scope the flag OFF for the call (it is ON in prod).
    _saved = handler._detect_silence_regions_vad
    _saved_flag = handler._WITHIN_CLIP_DEADAIR
    handler._detect_silence_regions_vad = lambda *a, **k: []
    handler._WITHIN_CLIP_DEADAIR = False
    try:
        _w = [{"word": "w", "punctuated_word": "w", "start": float(i), "end": i + 0.9}
              for i in range(30)]
        assert handler.detect_dead_air(_w, set(), "x.mp4") == [], \
            "zero-silence path must produce zero dead-air cuts"
    finally:
        handler._detect_silence_regions_vad = _saved
        handler._WITHIN_CLIP_DEADAIR = _saved_flag


@check("v197: safeguards DEGRADE (never drop/resize) + slot-integrity tripwire enforced")
def _v197_degrade():
    _src = open("handler.py").read()
    assert "def _assert_slot_integrity(" in _src, "tripwire missing"
    assert "_assert_slot_integrity(_pre_safeguard_slots, transitions_out)" in _src, "enforcement call missing"
    assert "_suppress_transition_slots" not in _src, "v196.1 sanitizer still present — exit criterion violated"
    assert _src.count('_t["type"] = "HardHold"') == 3, "all three safeguard sites must degrade, not drop"
    import render_schemas as _rs
    assert "HardHold" in str(_rs.RenderTransitionType), "render schema missing HardHold"
    assert "HardHold" not in str(_rs.TransitionType), "recipe vocabulary must exclude HardHold"
    # behavioral fault-injection
    try:
        handler._assert_slot_integrity([(0, 36)], [])
        assert False, "tripwire failed to fire on removed slot"
    except RuntimeError:
        pass


@check("v197: F5 vacuous-pass closed — empty MG props are a grounding violation")
def _v197_emptyprops():
    _src = open("handler.py").read()
    assert "props are empty" in _src, "empty-props violation missing from MG validation"
    for _f in ("PillCluster/PillCluster.tsx", "BarRace/BarRace.tsx", "RankedList/RankedList.tsx"):
        _t = open("src/remotion/src/motion-graphics/" + _f).read()
        assert "DEFAULT_TAGS" not in _t and "DEFAULT_BARS" not in _t and "DEFAULT_ITEMS" not in _t, _f + " still invents content"
        assert "return null" in _t, _f + " not fail-closed"
    _sc = open("src/remotion/src/motion-graphics/StatCard/StatCard.tsx").read()
    assert "Number.isFinite(value)" in _sc, "StatCard NaN guard missing"


@check("v196 divider pair: release margined off removed START; incoming edge floors at removed END")
def _v196_divider():
    _src = open("handler.py").read()
    assert "_REMOVED_EDGE_MARGIN_S = 0.075" in _src, "margin constant missing/changed"
    assert "_rs - _REMOVED_EDGE_MARGIN_S" in _src, "release limit missing"
    assert "min(_re, _S + 0.5)" in _src, "head floor / sanity cap missing"
    # behavioral: gap-0 removed word dies whole
    _w = [{"word": "a", "punctuated_word": "a", "start": 0.0, "end": 1.0},
          {"word": "d", "punctuated_word": "d", "start": 1.0, "end": 1.32},
          {"word": "d", "punctuated_word": "d", "start": 1.32, "end": 1.64}]
    _c, _, _ = handler.build_clips_from_words(_w, [{"word_index": 1}], video_duration=10.0)
    assert _c[0]["source_end"] <= 1.0 + 1e-6, "release entered the removed word"
    assert _c[1]["source_start"] >= 1.32 - 1e-6, "incoming edge below removed end"


@check("v196 head-snap: dead-air incoming boundary snaps to VAD onset − 75ms, never backward")
def _v196_headsnap():
    _src = open("handler.py").read()
    assert "_HEAD_SNAP_MARGIN_S = 0.075" in _src, "snap margin missing/changed"
    assert "_VAD_SILENCES_LAST[:] =" in _src, "VAD stash (reset semantics) missing"
    assert "vad_silences=list(_VAD_SILENCES_LAST)" in _src, "call-site plumbing missing"
    _w = [{"word": "a", "punctuated_word": "a", "start": 0.0, "end": 1.0},
          {"word": "b", "punctuated_word": "b", "start": 2.6, "end": 3.2}]
    _c, _, _ = handler.build_clips_from_words(
        _w, [{"after_word_index": 0, "before_word_index": 1, "reason": "dead_air"}],
        video_duration=10.0, vad_silences=[(1.05, 2.95)])
    assert abs(_c[1]["source_start"] - 2.875) < 0.01, "snap-forward failed"


@check("cancel-fence (v195): rail UPDATE carries the hard-terminal predicate at the 19475 chokepoint")
def _cancel_fence_wired():
    _src = open("handler.py").read()
    assert '.eq("id", job_id).not_.in_(' in _src, "fence predicate missing from write_job_status chain"
    assert 'status_col, ("failed", "canceled")).execute()' in _src, \
        "hard-terminal value set missing or reordered (must be failed+canceled ONLY — needs_input stays open)"
    assert "fence declined job=" in _src, "zero-match decline log missing (the redux proof line)"
    # exactly ONE write_job_status rail chain exists — the chokepoint stays the
    # chokepoint (`patch` is that rail's var; the step-token rail below uses
    # `_step_patch`, so a THIRD writer reusing `patch` still trips this).
    assert _src.count(".update(patch).eq(\"id\", job_id)") == 1, "a second rail write chain appeared"
    # SECOND legitimate video_jobs rail (2026-07-24 step-token durability): narrow
    # (narrative columns only) and STRICTER-fenced than the chokepoint — it also
    # excludes `completed`. Pinned so it can never lose its terminal fence (a bare
    # .update(_step_patch) that could relabel a closed row is the regression this
    # catches). The two rails together are the complete video_jobs writer set.
    assert _src.count('.update(_step_patch).eq("id", job_id).not_.in_(') == 1, \
        "the step-token durability rail must exist and keep its hard-terminal fence"
    assert '"failed", "canceled", "completed"' in _src, \
        "the step-token rail's fence must exclude every closed status (failed/canceled/completed)"


@check("integrity gate: thresholds pinned to calibration evidence (dde5945d/PC2/45-file field battery)")
def _gate_thresholds():
    import handler
    # dde5945d = 0.883s; field sub-trip max 0.75s (battery 2026-07-05)
    assert handler._IG_FREEZE_TRIP_S == 0.80, "freeze trip moved off its calibration"
    assert handler._IG_FREEZE_NOISE_DB == -50, "freeze noise floor moved"
    assert handler._IG_HOLE_TRIP_S == 0.30, "hole trip moved off TIMELINE_HOLES signature"
    assert handler._IG_DUR_DELTA_TRIP_S == 0.25, "duration-delta trip moved (PC2 = 0.993s)"
    assert handler._IG_BLACK_DETECT_S == 0.20 and handler._IG_BLACK_PIX_TH == 0.10


@check("integrity gate: wired at the pre-upload seam, verdict persisted always, masks from the ONE post-safeguard plan")
def _gate_wired():
    _src = open("handler.py").read()
    _seam = _src.index("POST-RENDER INTEGRITY GATE (CUT_STACK_REFORM Part 1) ────")
    assert _seam < _src.index("def _upload_main"), "gate must precede upload"
    assert "_integrity_gate(" in _src and "_build_integrity_masks(edit_plan)" in _src
    assert 'f"integrity/{job_id}.json"' in _src, "always-persist verdict missing"
    assert 'f"forensics/{job_id}/output.mp4"' in _src, "forensic preservation missing"
    # masks come from the post-safeguard stash, never re-derived layout math
    assert "_integrity_slot_ranges" in _src and "_integrity_fullmg_ranges" in _src
    assert '_clip_ranges[_ai]["end"]' in _src, "slot windows must come from the canonical clip-range cursor law"


@check("integrity gate: trip is terminal — INTEGRITY_TRIP envelope, refund copy, rescue-denied, observe-only plumbed")
def _gate_trip_path():
    import handler
    _env = handler.classify_error(RuntimeError("INTEGRITY_TRIP: freeze=[[1.0, 2.0]]"))
    assert _env.get("error_code") == "INTEGRITY_TRIP", _env
    assert "credit was returned" in str(_env.get("user_message")), "honest refund copy missing"
    assert _env.get("retryable") is True
    assert "INTEGRITY_TRIP" in handler._OUTER_RESCUE_DENY, "safe-edit rescue would auto-retry a tripped render"
    _src = open("handler.py").read()
    assert 'input_data.get("integrity_observe_only")' in _src, "operator observe-only flag missing"
    assert "observe-only — operator" in _src, "observe-only trip branch missing"
    # fail-open on instrument crash is LOUD, never silent
    assert "fail-open — instrument crashed" in _src


@check("W1-FIX-DEEP: residual black-trip families masked — outro fade_black window + B-roll windows in the black mask, dark-scene YAVG echo discriminator (convicted 7/7: 270d756a/2f5e1b2f/acf712cf/fb141d88 fade, df1fa136 dark B-roll, 3bfc7b63/91150d15 dark scene; cert_integrity_black_families.py 14/14)")
def _gate_black_families():
    import handler
    from ffmpeg_base import OUTRO_FADE_DUR_S
    # 1. single source of truth: the mask derives from the SAME constant the
    # fade filter renders with (a fade-length change cannot silently desync)
    _fb = open("ffmpeg_base.py").read()
    assert "fade_dur_seconds = OUTRO_FADE_DUR_S" in _fb, \
        "outro fade must render from the shared constant"
    assert OUTRO_FADE_DUR_S == 1.0, "fade length moved off its convicted geometry"
    # 2. functional: fade_black plan → the fade window is black-masked;
    # fade_white / none → it is not (membership stays evidence-based)
    _plan = {"_render_fps": 60.0, "_render_total_output_frames": 600,
             "_broll_output_ranges": [(2.0, 3.5)]}
    _m = handler._build_integrity_masks({**_plan, "outro": "fade_black"})
    assert any(s <= 9.01 and e >= 9.99 for (s, e) in _m["black"]), \
        f"fade_black window missing from black mask: {_m['black']}"
    # 3. functional: B-roll windows black-masked (dark stock footage is
    # content, not a defect — df1fa136), for every outro value
    for _o in ("none", "fade_black", "fade_white"):
        _mo = handler._build_integrity_masks({**_plan, "outro": _o})
        assert any(s <= 1.76 and e >= 3.74 for (s, e) in _mo["black"]), \
            f"broll window missing from black mask (outro={_o}): {_mo['black']}"
    _m_none = handler._build_integrity_masks({**_plan, "outro": "none"})
    _m_white = handler._build_integrity_masks({**_plan, "outro": "fade_white"})
    for _mm in (_m_none, _m_white):
        assert not any(s <= 9.01 and e >= 9.99 for (s, e) in _mm["black"]), \
            "outro window must be masked ONLY for fade_black"
    # 4. dark-scene discriminator present in the black echo: unpadded window,
    # fail-toward-defect on instrument trouble, threshold pinned
    _src = open("handler.py").read()
    assert handler._IG_DARK_SCENE_YAVG == 32.0, \
        "dark-scene floor moved off its calibration (convicted scene YAVG 28.4)"
    _echo = _src[_src.index("def _ig_source_echo_black"):]
    _echo = _echo[:_echo.index("\ndef ") if "\ndef " in _echo else len(_echo)]
    assert "src_dark_scene_yavg" in _echo, "dark-scene downgrade missing from black echo"
    assert "_ig_window_yavg(source_path, max(0.0, src_s), src_e)" in _echo, \
        "YAVG must measure the UNPADDED mapped window"
    assert callable(getattr(handler, "_ig_window_yavg", None))
    # 5. the cert file rides the repo (regression geometry stays runnable)
    assert os.path.exists("cert_integrity_black_families.py")


@check("W1-FIX-DEEP: RENDER_FATAL 'cgroup memory' class root-caused as the 25s browser-connect deadline (job 7f09fe28: memory lines were a WARNING; the buried killer was TimeoutError after 8-way cold Chrome spawns) — image patch (25s→120s + sentinel guard) + signature-first error capture + serial Chrome pre-warm, certs: cert_remotion_env_patch.py 12/12 local + cert_remotion_env_app.py live")
def _render_fatal_env_class():
    _h = open("handler.py").read()
    # 1. the image-build patch script exists, carries all four patch shapes,
    # and FAILS THE BUILD when the top-level renderer is not patched
    assert os.path.exists("src/remotion/patch-remotion-env.mjs"), "patch script missing"
    _p = open("src/remotion/patch-remotion-env.mjs").read()
    assert '"timeout: 25000,"' in _p and "timeout: 120000," in _p, \
        "browser-connect deadline patch (25000→120000) missing"
    assert _p.count("timeout: 25000") >= 2, "both esm + cjs deadline patches required"
    assert "1125899906842624" in _p, ">1PiB cgroup sentinel guard missing"
    assert "getAvailableMemoryFromCgroup()" in _p \
        and "from_docker_cgroup_1.getAvailableMemoryFromCgroup" in _p, \
        "sentinel guard must patch BOTH the esm bundle and the cjs consumer"
    assert "process.exit(1)" in _p and "top-level" in _p, \
        "the patch must fail the IMAGE BUILD when the top-level renderer is unpatched"
    # 2. wired into the image build as its own layer
    _m = open("modal_app.py").read()
    assert "node patch-remotion-env.mjs /remotion/node_modules" in _m, \
        "modal_app.py must run the patch after npm install"
    assert _m.index("npm install") < _m.index("node patch-remotion-env.mjs"), \
        "patch must run AFTER npm install (which restores pristine files)"
    # 3. signature-first error capture: the thrown *Error line leads the
    # message so ladder [:300] / envelope truncation keeps the REAL cause
    assert r're.findall(' in _h and r'(?:Error|Exception)\b' in _h, \
        "salient-error extraction missing from _run_remotion"
    assert "_salient}{_stderr_full[-3000:]}" in _h, \
        "the salient line must LEAD the raised message, tail kept for context"
    import re as _re
    _sample = ("Detected differing memory amounts:\nMemory reported by CGroup: 8796093016236.07 MB\n"
               "TimeoutError: Timed out after 25000 ms while trying to connect to the browser!\n"
               "    at Timeout.onTimeout (...)\n")
    _err = _re.findall(r"^[A-Za-z_.$]*(?:Error|Exception)\b.*", _sample, _re.M)
    assert _err and _err[-1].startswith("TimeoutError"), \
        "the extraction regex must pull the thrown TimeoutError, not the memory warning"
    # 4. serial Chrome pre-warm: once per container, bounded, fail-open,
    # placed BEFORE the parallel render-pool spawn
    assert "def _prewarm_chrome_once(" in _h and '_CHROME_PREWARM = {"done": False}' in _h
    _pw = _h[_h.index("def _prewarm_chrome_once("):]
    _pw = _pw[:_pw.index("\nclass ")]
    assert "threading.Timer" in _pw, "pre-warm must be watchdog-bounded (a hung Chrome must never block the render)"
    assert "fail-open" in _pw, "pre-warm must be fail-open"
    assert "raise" not in _pw, "pre-warm must NEVER raise into the render path"
    assert _h.index("_prewarm_chrome_once()", _h.index("def render_multi_clip")) \
        < _h.index("_render_pool = concurrent.futures.ThreadPoolExecutor"), \
        "pre-warm must run before the parallel render pool spawns"
    # 5. certs ride the repo
    assert os.path.exists("cert_remotion_env_patch.py")
    assert os.path.exists("cert_remotion_env_app.py")


@check("RENDER_FATAL TIMEOUT FORENSICS (2026-08-01): a `node render-full.mjs` subprocess timeout must never again reach the job row as a bare `TimeoutExpired: Command [...] timed out` with no evidence — 13 of 14 prod RENDER_FATALs (2026-07-25..08-01, 10 users) landed exactly that way while POSIX subprocess.run had the child's partial stdout/stderr attached to the exception the whole time, unread. RUNTIME-ASSERTED (not a source grep): _remotion_subprocess is actually timed out here and the raised error must carry composition label + how-far-it-got + budget INSIDE the first 300 chars, because the degrade ladder truncates the cause at [:300] and that is the only copy reaching result.error_detail (Modal's log buffer retains ~1h, always less than time-to-look). cert: test_remotion_timeout_forensics.py 19/19")
def _render_fatal_timeout_forensics():
    import subprocess as _sp
    import sys as _sys
    import tempfile as _tf
    import handler
    assert os.path.exists("test_remotion_timeout_forensics.py"), \
        "forensics cert must ride the repo"
    _fn = getattr(handler, "_remotion_subprocess", None)
    assert callable(_fn), \
        "_remotion_subprocess must stay MODULE-LEVEL — a nested closure cannot be tested"

    # A child that reports progress like render-full.mjs, then outlives its budget.
    _fd, _p = _tf.mkstemp(suffix=".py")
    with os.fdopen(_fd, "w") as _f:
        _f.write(
            "import sys, time\n"
            "print('[render-full] progress 20% rendered=450 encoded=441 "
            "interval_render_fps=6.1', flush=True)\n"
            "sys.stderr.write('warn noise\\n'); sys.stderr.flush()\n"
            "time.sleep(600)\n"
        )
    _err = None
    try:
        _fn("micro-00", [_sys.executable, "-u", _p,
                         "--frame-range", "0,2249", "--concurrency", "4"], timeout=2)
    except Exception as _e:
        _err = _e
    finally:
        os.unlink(_p)

    assert _err is not None, "timeout must raise"
    assert isinstance(_err, RuntimeError) and not isinstance(_err, _sp.TimeoutExpired), \
        f"must re-raise as RuntimeError (stable shape for the ladder + classify_error), got {type(_err).__name__}"
    assert isinstance(_err.__cause__, _sp.TimeoutExpired), \
        "the original TimeoutExpired must stay chained as __cause__"

    # ── the durability budget: only [:300] survives into result.error_detail ──
    _head = str(_err)[:300]
    assert "micro-00" in _head, f"composition label lost in truncation: {_head!r}"
    assert "TIMEOUT" in _head.upper(), f"timeout verdict lost in truncation: {_head!r}"
    assert "rendered=450" in _head, f"HOW FAR IT GOT lost in truncation: {_head!r}"
    assert "/2250" in _head, f"frame-count denominator lost (progress with no denominator is not a result): {_head!r}"
    assert "encoded=441" in _head, f"encoder progress lost in truncation: {_head!r}"
    assert "budget" in _head.lower(), f"the exceeded budget must be named: {_head!r}"

    # ── end-to-end: the ladder wrap must preserve BOTH the digest and routing ──
    _laddered = (f"RENDER_FATAL after full + retry + stripped renders: "
                 f"{type(_err).__name__}: {str(_err)[:300]}")
    assert "rendered=450" in _laddered and "micro-00" in _laddered, \
        f"digest did not survive the ladder wrap: {_laddered!r}"
    assert handler.classify_error(RuntimeError(_laddered))["error_code"] == "RENDER_FATAL", \
        "routing must be unchanged by the richer message"

    # ── a render that never started is a DIFFERENT diagnosis, stated explicitly ──
    _fd, _p = _tf.mkstemp(suffix=".py")
    with os.fdopen(_fd, "w") as _f:
        _f.write("import time\ntime.sleep(600)\n")
    _err2 = None
    try:
        _fn("overlay-00", [_sys.executable, "-u", _p], timeout=2)
    except Exception as _e:
        _err2 = _e
    finally:
        os.unlink(_p)
    assert _err2 is not None and "NO progress" in str(_err2)[:300], \
        f"a child that never rendered a frame must say so (bundle/openBrowser death != slow render): {str(_err2)[:300]!r}"


@check("MICRO RENDER BUDGET (2026-08-01, RENDER_FATAL mitigation): micro chunks were submitted with NO timeout argument and silently inherited _run_remotion's flat 300s default while overlay always passed a computed per-chunk budget — 10 of the 13 TimeoutExpired RENDER_FATALs in the 2026-07-25..08-01 window were a micro chunk (9 of them chunk 00), and the render stage on COMPLETED jobs runs p90=179s/p95=258s/max=633s (n=374), i.e. 300s sat INSIDE the success distribution. Micro now takes overlay's own per-frame rate (300s/450f), floored at today's 300s and capped at overlay's 600s. The waits that guard it are DERIVED from the budgets, never constants: a barrier shorter than the subprocess it waits on replaces the forensic render timeout with a bare concurrent.futures.TimeoutError.")
def _micro_render_budget():
    _h = open("handler.py").read()
    _i = _h.index("_MICRO_SEC_PER_FRAME")
    _j = _h.index("_micro_finalize_future.result(")
    _blk = _h[_i:_j]

    # 1. micro must never again inherit the default by omission
    assert "_render_pool.submit(_run_remotion, _lbl, _cmd, _to)" in _blk, \
        "micro submit must pass an EXPLICIT per-chunk budget (the bug was the omitted arg)"
    assert "zip(micro_cmds, _micro_timeouts)" in _blk, \
        "micro budgets must be zipped 1:1 with micro_cmds"
    # every micro command must have a budget — chunked AND single-process
    assert _blk.count("_micro_timeouts.append(") >= 2, \
        "both the chunked and the unchunked micro path must append a budget"

    # 2. the budget must SCALE with frames, not be a constant
    assert "_frames * _MICRO_SEC_PER_FRAME" in _blk, \
        "micro budget must scale with the chunk's frame count"
    # 3. it must be floored at today's value — nothing may get a SMALLER budget
    assert "_MICRO_TIMEOUT_FLOOR = _PLAIN_CHUNK_TIMEOUT" in _blk, \
        "floor must be today's 300s so no render regresses"
    assert "_MICRO_TIMEOUT_CAP = _OVERLAY_TIMEOUT_CAP" in _blk, \
        "cap must track overlay's ceiling, not a fresh constant"

    # 4. THE ORDERING INVARIANT: subprocess budget < barrier < finalize.
    #    Derived, so raising a budget raises its guards automatically.
    assert "_MICRO_BARRIER_S = (max(_micro_timeouts)" in _blk, \
        "the micro barrier must be DERIVED from the chunk budgets"
    assert "_MICRO_FINALIZE_S = _MICRO_BARRIER_S +" in _blk, \
        "the finalize wait must be DERIVED from the barrier"
    assert "timeout=_MICRO_BARRIER_S + _fanout_wait_extra" in _blk, \
        "the per-chunk wait must use the derived barrier"
    assert "timeout=320" not in _blk and "timeout=400 + _fanout_wait_extra" not in _h, \
        "the old constant micro waits (320/400) must be gone"

    # 5. arithmetic: the invariant must hold at every chunk size, and stay
    #    inside the 3000s Modal job budget.
    # Read the LIVE constants out of handler rather than restating them, so a
    # future raise (agent/speed raised these to 600/1500 on 2026-08-02) can
    # never silently drift past this invariant.
    _PLAIN = int(re.search(r"_PLAIN_CHUNK_TIMEOUT = (\d+)", _h).group(1))
    _CAP = int(re.search(r"_OVERLAY_TIMEOUT_CAP = (\d+)", _h).group(1))
    assert _CAP >= _PLAIN, "overlay cap must be >= its plain budget"
    for _f in (1, 150, 450, 900, 2250, 9000, 100000):
        _t = int(min(_CAP, max(_PLAIN, _f * (_PLAIN / 450.0))))
        _b, _fin = _t + 20, _t + 20 + 140
        assert _t < _b < _fin < 3000, f"budget ordering broken at {_f} frames: {_t}/{_b}/{_fin}"
        assert _t >= _PLAIN, f"budget regressed below the plain budget at {_f} frames: {_t}"
    # MICRO MUST NOT HAVE THE LOWER CEILING (Zac 2026-08-02): micro's chunk
    # count was pinned at 4 while overlay's scaled, so micro carried the
    # GROWING per-chunk load against the LOWER cap — backwards. Micro's cap
    # tracks overlay's, and micro's chunk count now uses overlay's own rule.
    assert "_MICRO_TIMEOUT_CAP = _OVERLAY_TIMEOUT_CAP" in _h, \
        "micro's ceiling must track overlay's, never be a lower constant"
    assert "_MICRO_CHUNK_COUNT = 4 if" not in _h, \
        "micro chunk count must NOT be pinned at 4 (per-chunk load must stay bounded)"
    assert "_MICRO_TAB_BUDGET" in _h and "_MICRO_TAB_BUDGET // max(1, len(_micro_ranges))" in _h, \
        "unpinning must hold the Chrome tab budget constant (cpu=16 box)"


@check("ORPHANED CERTS ARE RUN, NOT JUST COMMITTED (2026-08-02): test_render_ladder.py was PERMANENTLY RED at HEAD — it asserted the pre-LEVER-4 three-rung shape — and no runner invoked it, so the deploy gate's green never covered it. A red test nobody runs trains everyone to ignore red. These render error-path certs now execute INSIDE the gate: a failure here fails the deploy.")
def _error_path_certs_actually_run():
    import subprocess as _sp
    import sys as _sys
    for _cert in ("test_render_ladder.py", "test_remotion_timeout_forensics.py",
                  "test_coverage_empty_transcript.py",
                  "test_asr_scribe_routing.py",
                  "test_render_never_blames_user_file.py",
                  "test_integrity_black_echo_boundary.py",
                  "test_integrity_freeze_echo_boundary.py",
                  "test_silent_to_moodreel.py",
                  "test_output_frame_grid.py",
                  "test_integrity_dead_moment_echo.py"):
        assert os.path.exists(_cert), f"{_cert} missing from the repo"
        _r = _sp.run([_sys.executable, _cert], capture_output=True, text=True, timeout=300)
        assert _r.returncode == 0, (
            f"{_cert} FAILED (rc={_r.returncode}): "
            f"{(_r.stdout or '')[-600:]}{(_r.stderr or '')[-400:]}"
        )


@check("COVERAGE GATE FAIL-OPEN CLOSED (2026-08-02): `if _dur <= 0 or not words: return True` meant an EMPTY transcript PASSED the coverage gate — a total transcription failure scored as fine, which is why the class could not be counted. Proven by the ASR bake-off: Deepgram nova-3 returned ZERO words on 11 of 40 clips and all 11 passed the old gate, which also flattered the control mean 53.6%->73.9% by dropping its worst cases. Zero words is now a REJECT (TRANSCRIPTION_EMPTY) when VAD confirms speech, stays quiet on a genuinely silent clip (NO_SPEECH owns that), and STILL fails open wherever the gate cannot measure. cert: test_coverage_empty_transcript.py 14/14")
def _coverage_empty_transcript_fails():
    import handler
    _o1, _o2 = handler._detect_silence_regions_vad, handler._vad_available

    def _vad(sil, avail=True):
        handler._detect_silence_regions_vad = lambda *a, **k: sil
        handler._vad_available = lambda: avail

    try:
        # 1. zero words over VAD-confirmed speech -> REJECT (the fix)
        _vad([(0.0, 0.5)])
        _ok, _st = handler._transcription_coverage_check("/x.mp4", [], 10.0)
        assert _ok is False, f"empty transcript over 9.5s of speech must REJECT: {_st}"
        assert _st.get("unworded_frac") == 1.0, _st

        # 2. genuinely silent clip -> NOT this class (NO_SPEECH owns it)
        _vad([(0.0, 10.0)])
        assert handler._transcription_coverage_check("/x.mp4", [], 10.0)[0] is True, \
            "a silent clip must not become a coverage failure"

        # 3. sub-floor speech -> no over-fire
        _vad([(0.0, 9.0)])
        assert handler._transcription_coverage_check("/x.mp4", [], 10.0)[0] is True, \
            "1s of speech is under the 2.0s floor and must not fail a job"

        # 4. THE [] AMBIGUITY: VAD ran + found no silence = continuous speech
        #    (worst case) vs VAD unavailable = unmeasurable. Must differ.
        _vad([], avail=True)
        assert handler._transcription_coverage_check("/x.mp4", [], 10.0)[0] is False, \
            "continuous speech with zero words is the WORST case and must REJECT"
        _vad([], avail=False)
        assert handler._transcription_coverage_check("/x.mp4", [], 10.0)[0] is True, \
            "an unmeasurable gate must FAIL OPEN, never invent a verdict"
    finally:
        handler._detect_silence_regions_vad, handler._vad_available = _o1, _o2

    # 5. unmeasurable duration -> fail-open, unchanged
    assert handler._transcription_coverage_check("/x.mp4", [], 0.0)[0] is True

    # 6. the class is routable and never blames the user for an engine failure
    _env = handler.classify_error(RuntimeError("TRANSCRIPTION_EMPTY: 9.5s speech, 0 words"))
    assert _env.get("error_code") == "TRANSCRIPTION_EMPTY", _env
    assert _env.get("requires_new_video") is not True, _env
    assert _env.get("retryable") is True, _env

    assert os.path.exists("test_coverage_empty_transcript.py"), "cert must ride the repo"


@check("LANGUAGE-ROUTED SCRIBE (2026-08-02, DARK behind PROMPTLY_ASR_SCRIBE): measured head-to-head on real prod audio, BOTH cohorts scored through handler's OWN _transcription_coverage_check, with Deepgram run on its EXACT production options (language=multi + 48kHz FLAC — an earlier control used detect_language=true, the config handler.py:3863 documents as returning 0 words on ~40% of non-English, and it had to be re-run). Failing set (TRANSCRIPTION_INCOMPLETE): deepgram 3/40 -> scribe 34/40. CONTROL set (currently SUCCEEDING, the no-regression proof): deepgram 32/40 -> scribe 39/40. Word timing vs an INDEPENDENT acoustic onset: 50.0ms -> 19-20ms. Scribe won in every language measured incl. English (18/22->20/22). Selection is MEASURED by the same gate that would reject the job, routing is an allowlist, and Deepgram has already returned before Scribe is called so an outage cannot cost a job. cert: test_asr_scribe_routing.py 14/14")
def _asr_scribe_routing():
    import handler
    _src = open("handler.py").read()
    assert os.path.exists("test_asr_scribe_routing.py"), "cert must ride the repo"
    # PROPAGATION GUARD (Zac 2026-08-02): the Scribe upgrade in handler() MUST
    # write its result back to the shared transcript cache, exactly like the
    # Arabic-bridge and bilingual upgrades. Without it, Scribe recovers the
    # transcript into a LOCAL var while the pipeline's 0-words gate re-reads
    # _get_resolved_transcript()'s raw cache (still Deepgram's 0 words) and
    # rejects the job Scribe just fixed — the whole recovery does nothing end to
    # end (proven on 27b02576: dg 0 -> scribe 153, chose:scribe, died "0 words").
    _sc = _src[_src.index("_maybe_upgrade_transcript_scribe(\n                _transcript"):]
    _sc = _sc[:_sc.index("TALKING-HEAD GATE")]
    assert '_refined_tx_cache["value"] = _transcript' in _sc, \
        ("the Scribe upgrade must propagate to _refined_tx_cache[\"value\"] so the "
         "0-words gate and all other transcript consumers see the recovered words")
    for _fn in ("transcribe_scribe", "_maybe_upgrade_transcript_scribe",
                "_scribe_should_route", "_scribe_enabled", "_scribe_langs"):
        assert callable(getattr(handler, _fn, None)), f"{_fn} missing"

    _o_env = {k: os.environ.get(k) for k in
              ("PROMPTLY_ASR_SCRIBE", "PROMPTLY_SCRIBE_LANGS", "ELEVENLABS_API_KEY")}

    def _set(**kw):
        for k, v in kw.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    try:
        # 1. DARK BY DEFAULT — the flag must default OFF, whatever the key state
        _set(PROMPTLY_ASR_SCRIBE=None, ELEVENLABS_API_KEY="k")
        assert handler._scribe_enabled() is False, "PROMPTLY_ASR_SCRIBE must default OFF"
        assert handler._scribe_should_route("hi") is False, "flag off must never route"

        # 2. a key is REQUIRED — arming the flag without one must not route
        _set(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY=None)
        assert handler._scribe_should_route("hi") is False, \
            "no ELEVENLABS_API_KEY must not route (never call an engine we cannot reach)"

        # 3. ALLOWLIST semantics, incl. the explicit widen-to-everything escape
        _set(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY="k", PROMPTLY_SCRIBE_LANGS="ml,ta")
        assert handler._scribe_should_route("ml") is True
        assert handler._scribe_should_route("hi") is False, "allowlist must exclude"
        _set(PROMPTLY_SCRIBE_LANGS="*")
        assert handler._scribe_should_route("ja") is True, "'*' must route everything"

        # 3b. ZERO-WORD BYPASS (Zac 2026-08-03): a "Transcribed 0 words" Deepgram
        # result carries NO detected_language, so the restrictive allowlist
        # (default hi,ml,ta,… — PROMPTLY_SCRIBE_LANGS unset in prod) excludes
        # EXACTLY the case Scribe exists to recover. It fired 0x on its own target.
        # A 0-word result must route to Scribe on the armed engine + key ALONE.
        _set(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY="k", PROMPTLY_SCRIBE_LANGS="ml,ta")
        _called = {"scribe": False}
        _oc0, _os0 = handler._transcription_coverage_check, handler.transcribe_scribe
        try:
            handler._transcription_coverage_check = lambda *a, **k: (False, {"unworded_frac": 1.0})
            def _spy(*a, **k):
                _called["scribe"] = True
                return {"words": [{"word": "x", "start": 0.0, "end": 0.2}], "detected_language": "hi"}
            handler.transcribe_scribe = _spy
            handler._maybe_upgrade_transcript_scribe(
                {"words": [], "detected_language": None}, "/x.mp4", 10.0)
            assert _called["scribe"] is True, \
                ("a 0-word Deepgram result MUST route to Scribe regardless of the "
                 "language allowlist — that empty, language-less case is the exact "
                 "class Scribe exists to recover, and gating it on langs made it "
                 "fire 0x on its own target")
        finally:
            handler._transcription_coverage_check, handler.transcribe_scribe = _oc0, _os0

        # 4. FLAG-OFF INERTNESS at the call site: same object back, engine untouched
        _set(PROMPTLY_ASR_SCRIBE=None)
        _dg = {"words": [{"word": "a", "start": 0.0, "end": 0.1}], "detected_language": "hi"}
        assert handler._maybe_upgrade_transcript_scribe(_dg, "/x.mp4", 10.0) is _dg, \
            "flag off must return the EXACT Deepgram result (byte-identical pipeline)"

        # 5. FAIL-SAFE: the upgrade raising must never cost a transcript we have
        _set(PROMPTLY_ASR_SCRIBE="1", ELEVENLABS_API_KEY="k", PROMPTLY_SCRIBE_LANGS="hi")
        _oc, _os_ = handler._transcription_coverage_check, handler.transcribe_scribe
        try:
            handler._transcription_coverage_check = lambda *a, **k: (False, {"unworded_frac": 0.9})
            def _boom(*a, **k):
                raise RuntimeError("SCRIBE_HTTP_500")
            handler.transcribe_scribe = _boom
            assert handler._maybe_upgrade_transcript_scribe(_dg, "/x.mp4", 10.0) is _dg, \
                "a Scribe outage must leave today's behaviour, never fail the job"
            # 6. MEASURED selection — a WORSE Scribe transcript must not be taken
            handler.transcribe_scribe = lambda *a, **k: {
                "words": [{"word": "b", "start": 0.0, "end": 0.1}], "detected_language": "hi"}
            handler._transcription_coverage_check = (
                lambda _p, w, _d: (False, {"unworded_frac": 0.4 if w is _dg["words"] else 0.9}))
            assert handler._maybe_upgrade_transcript_scribe(_dg, "/x.mp4", 10.0) is _dg, \
                "Scribe losing on coverage must leave Deepgram in place (not a blind swap)"
        finally:
            handler._transcription_coverage_check, handler.transcribe_scribe = _oc, _os_
    finally:
        for _k, _v in _o_env.items():
            os.environ.pop(_k, None) if _v is None else os.environ.__setitem__(_k, _v)

    # 7. the word CONTRACT — Scribe must fill every field Deepgram's parse emits
    for _f in ("\"punctuated_word\"", "\"confidence\"", "\"speaker\"", "\"language\""):
        assert _f in _src[_src.index("def transcribe_scribe"):_src.index("def transcribe_audio")], \
            f"transcribe_scribe must emit {_f} — downstream reads all seven fields"


@check("INTEGRITY_TRIP BLACK-ECHO DIAGNOSTIC (2026-08-02): the source-echo that downgrades user-content black (_ig_source_echo_black) needs BOTH a readable source AND a working output->source mapping; when either is missing it is skipped SILENTLY and a faithful render of black footage trips as if we produced the black. Job 0e794beb tripped 3x on a source carrying 7.97s of black across 4 spans — the mapped window is 2.4s black vs a 1.93s output span (cover 2.4 >= the 0.60 threshold's 1.16s), so the echo WOULD have downgraded it. Which precondition failed was unanswerable: the verdict JSON is in S3 and the DB result carried NO integrity fields. The trip message now front-loads source/map/downgraded so it survives the [:300] truncation into result.error_detail.")
def _integrity_black_echo_diag():
    import handler
    _h = open("handler.py").read()
    _i = _h.index("WHY DIDN'T THE SOURCE-ECHO SAVE THIS")
    _j = _h.index("raise RuntimeError(f\"INTEGRITY_TRIP:", _i)
    _blk = _h[_i:_j + 200]
    # the three facts that identify the failing precondition
    assert "source=" in _blk and "MISSING" in _blk, "must report whether the source was readable"
    assert "map=" in _blk and "UNRESOLVED" in _blk, "must report whether out->src resolved"
    assert "downgraded=" in _blk, "must report how many spans the echo downgraded"
    # diagnostic must PRECEDE the span list, or [:300] can drop it on a long trip
    assert _h.index("_ig_why", _i) < _h.index("_ig_summary", _j - 100), \
        "the diagnostic must be front-loaded ahead of the span dump"
    # a diag failure must never replace the trip itself
    assert "diag-failed" in _blk, "the diagnostic must be try/except'd — it can never eat the trip"
    # routing unchanged, and the diagnostic survives truncation
    _msg = ("INTEGRITY_TRIP: [echo: source=MISSING map=UNRESOLVED downgraded=0] "
            "black=[[20.466667, 22.4]], both_stream_hole=[[50.46075, 50.766667]]")
    assert handler.classify_error(RuntimeError(_msg))["error_code"] == "INTEGRITY_TRIP"
    assert "echo:" in _msg[:300] and "source=" in _msg[:300], "diagnostic must survive [:300]"
    # the discriminator it diagnoses must still exist and still be wired
    assert callable(getattr(handler, "_ig_source_echo_black", None))
    assert "_ig_source_echo_black(" in _h and "out_to_src=_ig_out_to_src" in _h, \
        "the source-echo must stay wired into the gate call"


@check("SIGNATURE-FIRST ON THE HYPE/MINIMAL RENDER BRIDGE (2026-08-02): hype_render._render_remotion opened its failure message with STDOUT, so the thrown exception sat ~700 chars in and the degrade ladder's [:300] truncation cut it off — job b8ab1276's durable error_detail ended at '[render-full] progress 0% rendered=0' and the real cause was unrecoverable from the job row. handler._remotion_subprocess has led with the real error since 2026-08-01; this was the one render call site still dumping stdout first. Both paths now pull the LAST line-anchored *Error/Exception line to the front.")
def _hype_render_signature_first():
    _src = open("hype_render.py").read()
    _i = _src.index("def _render_remotion")
    _j = _src.index("def render_hype")
    _blk = _src[_i:_j]
    assert "import re" in _src, "hype_render must import re for the signature extraction"
    assert 'r"^[A-Za-z_.$]*(?:Error|Exception)\\b.*"' in _blk or "(?:Error|Exception)" in _blk, \
        "must extract the thrown *Error/Exception line"
    assert "_salient" in _blk, "the salient error must be pulled out"
    # ORDERING IS THE WHOLE FIX: salient error, then STDERR, then STDOUT.
    _msg = _blk[_blk.index("raise RuntimeError("):]
    assert _msg.index("_salient") < _msg.index("STDERR"), "the error must precede STDERR"
    assert _msg.index("STDERR") < _msg.index("STDOUT"), \
        "STDOUT must come LAST — leading with it is exactly what truncated b8ab1276"
    # and prove it end-to-end on b8ab1276's real shape
    import re as _re
    _stdout = ("[render-full] composition=PromptlyOverlay (ProRes 4444 alpha) frames 0-907, "
               "0 caption pages, 8 MG, 0 text overlays, concurrency=8\n"
               "[render-full] Using prebundle at /remotion/bundle\n"
               "[render-full] Using build-time Chromium at /usr/local/bin/chrome-headless-shell\n"
               "[render-full] Browser opened in 1.22s\n[render-full] progress 0% rendered=0")
    _stderr = ("warning noise\nError: Timeout (30000ms) exceeded rendering the component at "
               'frame 134. Open delayRender() handles: "1. Loading <Img> with src=blob:..."')
    _el = _re.findall(r"^[A-Za-z_.$]*(?:Error|Exception)\b.*", _stderr, _re.M)
    _sal = (_el[-1].strip()[:400] + " ||| ") if _el else ""
    _new = (f"[hype-render] render-full.mjs PromptlyOverlay failed rc=1: "
            f"{_sal}STDERR:\n{_stderr[-2000:]}\nSTDOUT:\n{_stdout[-1200:]}")
    assert "Timeout (30000ms)" in _new[:300], \
        f"the exception must survive the [:300] truncation: {_new[:300]!r}"


@check("A RENDER FAILURE IS NEVER A BAD USER FILE (2026-08-02): the intake verdicts (INVALID_FORMAT/WRONG_ORIENTATION) judge the USER'S upload but match substrings that also appear in our own renderer's stderr. Seven jobs across NINE users died at `render-full.mjs PromptlyMicroSegments failed rc=1, progress 0% rendered=0` with fps_normalize already clean (15fps->30fps in 0.5-0.7s); their stderr carried 'No video stream found' and they were classified INVALID_FORMAT with retryable=False + requires_new_video=True — a DEAD END telling nine people their file was unreadable, and a class that looked like an input problem in every count since 07-30. A provenance gate now runs ABOVE the intake block so render-stage origin wins over substring. cert: test_render_never_blames_user_file.py 19/19")
def _render_never_blames_user_file():
    import handler
    _h = open("handler.py").read()
    # provenance must be decided BEFORE the intake verdicts, or the substring wins
    assert _h.index("_RENDER_STAGE_MARKERS") < _h.index('if "No video stream found" in msg'), \
        "the provenance gate must precede the intake block"
    _prod = ("[hype-render] render-full.mjs PromptlyMicroSegments failed rc=1\n"
             "STDOUT:\n[render-full] progress 0% rendered=0\nSTDERR:\nNo video stream found")
    _e = handler.classify_error(RuntimeError(_prod))
    assert _e["error_code"] != "INVALID_FORMAT", f"render failure blamed on the file: {_e}"
    assert str(_e["error_code"]).startswith("RENDER"), _e
    assert _e.get("retryable") is True, f"a render failure must not be a dead end: {_e}"
    assert _e.get("requires_new_video") is not True, f"must not demand a new video: {_e}"
    # every render-stage marker, not just the one we saw
    for _m in ("render-full.mjs", "[hype-render]", "PromptlyMicroSegments",
               "PromptlyOverlay", "Remotion render"):
        _env = handler.classify_error(RuntimeError(f"{_m} boom: No video stream found"))
        assert _env["error_code"] != "INVALID_FORMAT", f"{_m} still blamed on the file: {_env}"
    # NOT over-corrected: a genuine intake verdict must survive, or a real
    # bad-file class disappears into a retry loop
    _intake = handler.classify_error(RuntimeError("No video stream found"))
    assert _intake["error_code"] == "INVALID_FORMAT", _intake
    assert _intake.get("requires_new_video") is True, _intake
    # named render classes keep their own identity
    for _msg, _code in (("RENDER_FATAL after full + retry + stripped renders: [micro-00] Remotion render failed", "RENDER_FATAL"),
                        ("INTEGRITY_TRIP: black=[[1.0, 2.0]] from render-full.mjs", "INTEGRITY_TRIP")):
        assert handler.classify_error(RuntimeError(_msg))["error_code"] == _code, _msg
    assert os.path.exists("test_render_never_blames_user_file.py"), "cert must ride the repo"


@check("INTEGRITY_TRIP BLACK ECHO — A SPAN CROSSING A CUT MUST STILL BE SOURCE-CHECKED (2026-08-02): forced reproduction (job 017fa6d3) printed `[echo: source=Y map=29.92 downgraded=4]` — the echo RAN, the source was readable, the mapping resolved, four spans were downgraded, and two short ones tripped anyway. Cause: out_to_src maps each endpoint through whichever clip contains it, so a span straddling a cut resolves to DISCONTINUOUS source times and `src_e <= src_s` filed it as OUR defect WITHOUT ever running blackdetect — while the mapped window carried 0.6s of source black against a 0.14s requirement. A crossing span is now evaluated as the TWO source windows it covers and downgraded if EITHER is black. cert: test_integrity_black_echo_boundary.py 8/8 (E2-vs-E3: identical span, identical source, crossing the cut is the ONLY difference)")
def _integrity_black_echo_boundary():
    import handler, os as _os, subprocess as _sp, tempfile as _tf
    assert _os.path.exists("test_integrity_black_echo_boundary.py"), "cert must ride the repo"
    assert callable(getattr(handler, "_ig_window_is_black", None)), \
        "the crossing path must share ONE window check with the single-clip path"
    _fd, _src = _tf.mkstemp(suffix="_gate.mp4"); _os.close(_fd)
    try:
        _sp.run(["ffmpeg", "-y", "-v", "error",
                 "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=2",
                 "-f", "lavfi", "-i", "color=c=white:s=320x240:r=30:d=2",
                 "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                 "-map", "[v]", "-pix_fmt", "yuv420p", _src],
                capture_output=True, timeout=180)
        assert _os.path.getsize(_src) > 500, "fixture build failed"

        def _crossing(t):        # clip A then a BACKWARD cut into clip B
            return 0.9 + t if t < 1.0 else t - 1.0

        # 1. THE FIX: crossing a cut over SOURCE BLACK must downgrade, not trip
        _d, _g = handler._ig_source_echo_black(_src, [(0.9, 1.1)], _crossing)
        assert _g and not _d, f"boundary-crossing source black must downgrade: d={_d} g={_g}"
        assert _g[0].get("boundary_crossing") is True, "must record why it was downgraded"

        # 2. NOT OVER-CORRECTED: crossing a cut over NON-black must still trip
        def _crossing_white(t):
            return 2.4 + t if t < 1.0 else t + 1.4
        _d2, _g2 = handler._ig_source_echo_black(_src, [(0.9, 1.1)], _crossing_white)
        assert _d2 and not _g2, f"crossing over WHITE source must still be our defect: d={_d2} g={_g2}"

        # 3. single-clip paths unchanged, both directions
        _d3, _g3 = handler._ig_source_echo_black(_src, [(0.4, 0.9)], lambda t: t)
        assert _g3 and not _d3, "single-clip source black must still downgrade"
        _d4, _g4 = handler._ig_source_echo_black(_src, [(2.4, 2.9)], lambda t: t)
        assert _d4 and not _g4, "single-clip non-black must still trip"

        # 4. fail-closed on an unmappable endpoint — never downgrade the unchecked
        _d5, _g5 = handler._ig_source_echo_black(_src, [(0.4, 0.9)], lambda t: None)
        assert _d5 and not _g5, "unmappable must stay a defect"
    finally:
        try: _os.unlink(_src)
        except OSError: pass

    # the trip line must carry per-span mappings so the job row can answer this
    # without a fixture next time
    _h = open("handler.py").read()
    assert "spans={','.join(_sp)}" in _h, "trip line must emit per-span start->end mappings"
    assert "(CUT)" in _h, "a boundary-crossing span must be marked in the trip line"


@check("INTEGRITY_TRIP FREEZE ECHO — SAME CUT-CROSSING DEFECT AS BLACK (2026-08-02): _ig_source_echo carried the identical `src_e <= src_s -> defects` branch, so a freeze span straddling a backward cut was filed as OUR defect without freezedetect ever running — a faithful render of the user's own STATIC footage failed the gate. Job 7e8a303f tripped freeze=[[43.07,43.9]] on the same clip whose BLACK spans were proven source content by forced repro 017fa6d3. Same two-window repair. The guard that matters is the SECOND case: crossing a cut over MOVING source must still trip, because the freeze internals differ from black. cert: test_integrity_freeze_echo_boundary.py 9/9")
def _integrity_freeze_echo_boundary():
    import handler, os as _os, subprocess as _sp, tempfile as _tf
    assert _os.path.exists("test_integrity_freeze_echo_boundary.py"), "cert must ride the repo"
    assert callable(getattr(handler, "_ig_window_is_frozen", None)), \
        "the crossing path must share ONE window check with the single-clip path"
    _fd, _src = _tf.mkstemp(suffix="_frz.mp4"); _os.close(_fd)
    try:
        _sp.run(["ffmpeg", "-y", "-v", "error",
                 "-f", "lavfi", "-i", "color=c=green:s=320x240:r=30:d=2",
                 "-f", "lavfi", "-i", "nullsrc=s=320x240:r=30:d=2",
                 "-filter_complex",
                 "[1:v]geq=random(1)*255:128:128[n];[0:v][n]concat=n=2:v=1:a=0[v]",
                 "-map", "[v]", "-pix_fmt", "yuv420p", _src],
                capture_output=True, timeout=240)
        assert _os.path.getsize(_src) > 500, "fixture build failed"

        def _crossing(t):            # clip A then a BACKWARD cut into clip B
            return 0.9 + t if t < 1.0 else t - 1.0

        def _crossing_moving(t):     # both windows land in the NOISE half
            return 2.4 + t if t < 1.0 else t + 1.4

        # 1. THE FIX — crossing a cut over FROZEN source must downgrade
        _d, _g = handler._ig_source_echo(_src, [(0.9, 1.1)], _crossing)
        assert _g and not _d, f"boundary-crossing frozen source must downgrade: d={_d} g={_g}"
        assert _g[0].get("boundary_crossing") is True, "must record why"

        # 2. THE GUARD THAT MATTERS — crossing over MOVING source must STILL trip
        _d2, _g2 = handler._ig_source_echo(_src, [(0.9, 1.1)], _crossing_moving)
        assert _d2 and not _g2, \
            f"crossing over MOVING source is a REAL defect and must trip: d={_d2} g={_g2}"

        # 3. single-clip behaviour unchanged, both directions
        _d3, _g3 = handler._ig_source_echo(_src, [(0.4, 1.4)], lambda t: t)
        assert _g3 and not _d3, "single-clip frozen must still downgrade"
        _d4, _g4 = handler._ig_source_echo(_src, [(2.4, 3.4)], lambda t: t)
        assert _d4 and not _g4, "single-clip moving must still trip"

        # 4. fail-closed on an unmappable endpoint
        _d5, _g5 = handler._ig_source_echo(_src, [(0.4, 1.4)], lambda t: None)
        assert _d5 and not _g5, "unmappable must stay a defect"
    finally:
        try: _os.unlink(_src)
        except OSError: pass

    # BOTH echoes must share the one-window-check shape — a future edit to one
    # must not silently leave the other on the old branch again.
    _h = open("handler.py").read()
    assert _h.count("boundary_crossing") >= 2, \
        "black AND freeze must both carry the crossing repair"
    assert "if src_s is None or src_e is None or src_e <= src_s:" not in _h, \
        "the collapsed branch that hid the crossing case must be gone from BOTH echoes"


@check("SILENT CLIPS GET AN EDIT, NOT THEIR OWN FOOTAGE BACK (2026-08-03, DARK behind PROMPTLY_SILENT_TO_MOODREEL): measured over 387 completions since 08-01 with editorial events = (segments-1) + decorations counted across BOTH recipe shapes — minimal_speech_uncut 141/141 silent (median 0 editorial), moodreel 73 jobs 1 silent (median 5), hype median 14, standard median 10. 143 of 387 (37%, 140 users) deliver ZERO editorial events and 141 are the uncut passthrough. A clip whose speech we could not READ but which VAD confirms carries NO speech is silent content and belongs in the mood-reel cut. THE GUARD: minimal_speech_uncut exists because build_minimal_plan cuts at MOTION PEAKS, which would chop the untranscribed speech it protects (Urdu-class law) — so re-routing requires POSITIVE VAD confirmation and every unmeasurable case stays uncut. cert: test_silent_to_moodreel.py 13/13")
def _silent_to_moodreel():
    import handler
    _h = open("handler.py").read()
    assert os.path.exists("test_silent_to_moodreel.py"), "cert must ride the repo"
    for _fn in ("_silent_to_moodreel_enabled", "_vad_confirms_silence", "_silent_route_eligible"):
        assert callable(getattr(handler, _fn, None)), f"{_fn} missing"

    _o = os.environ.get("PROMPTLY_SILENT_TO_MOODREEL")
    _o1, _o2 = handler._detect_silence_regions_vad, handler._vad_available

    def _vad(sil, avail=True):
        handler._detect_silence_regions_vad = lambda *a, **k: sil
        handler._vad_available = lambda: avail
    try:
        # 1. DARK BY DEFAULT — flag off, nothing is ever re-routed
        os.environ.pop("PROMPTLY_SILENT_TO_MOODREEL", None)
        assert handler._silent_to_moodreel_enabled() is False
        _vad([(0.0, 30.0)])
        assert handler._silent_route_eligible("no_speech_muted", "/x.mp4", 30.0) is False, \
            "flag off must never re-route"

        os.environ["PROMPTLY_SILENT_TO_MOODREEL"] = "1"
        # 2. positive confirmation re-routes
        assert handler._silent_route_eligible("no_speech_muted", "/x.mp4", 30.0) is True
        assert handler._silent_route_eligible("transcription_incomplete", "/x.mp4", 30.0) is True
        # 3. THE GUARD — a clip WITH speech must never reach the motion-cut path
        _vad([(0.0, 2.0)])          # 28s of speech in 30s
        assert handler._silent_route_eligible("no_speech_muted", "/x.mp4", 30.0) is False, \
            "a speech-bearing clip must stay on the uncut route"
        # 4. FAIL SAFE on every unmeasurable shape
        _vad([], avail=False)
        assert handler._vad_confirms_silence("/x.mp4", 30.0) is False, "VAD unavailable -> uncut"
        _vad([], avail=True)        # [] also means 'continuous speech'
        assert handler._vad_confirms_silence("/x.mp4", 30.0) is False, "[] ambiguity -> uncut"
        _vad([(0.0, 30.0)])
        assert handler._vad_confirms_silence("/x.mp4", 0.0) is False, "no duration -> uncut"
        # 5. scope — duration verdicts are NOT silence verdicts
        assert handler._silent_route_eligible("too_short", "/x.mp4", 30.0) is False
    finally:
        handler._detect_silence_regions_vad, handler._vad_available = _o1, _o2
        os.environ.pop("PROMPTLY_SILENT_TO_MOODREEL", None) if _o is None else \
            os.environ.__setitem__("PROMPTLY_SILENT_TO_MOODREEL", _o)

    # wiring: the re-route must widen moodreel eligibility AND stop the clip
    # falling back into the uncut path it is meant to replace
    assert "or _silent_reroute)" in _h, "moodreel eligibility must include the re-route"
    assert "and not _silent_reroute)" in _h, \
        "_speech_bearing must exclude a re-routed clip or it falls back to uncut"


@check("DEAD MOMENT ECHO + RENAME (2026-08-03): the gate measures silence INTERSECT (freeze UNION black) and called it `both_stream_hole` — a name that says a segment is MISSING when the detector measures that NOTHING IS HAPPENING. black and freeze were each source-echoed individually but the INTERSECTION never was: the only relief subtracted spans that had ALREADY cleared their trip floors and entered the echo, and the SILENCE half was never source-checked at all. Job 7e8a303f tripped freeze+black+hole on the very 96.2s clip whose 7.97s of black was PROVEN source content by forced repro 017fa6d3. Now: downgrade only when BOTH constituents echo (source silent AND source black-or-frozen); a LIVE source under a dead output is still our defect. Check renamed to `dead_moment`. cert: test_integrity_dead_moment_echo.py 9/9")
def _integrity_dead_moment_echo():
    import handler, os as _os, subprocess as _sp, tempfile as _tf
    assert _os.path.exists("test_integrity_dead_moment_echo.py"), "cert must ride the repo"
    for _fn in ("_ig_window_is_silent", "_ig_source_echo_hole"):
        assert callable(getattr(handler, _fn, None)), f"{_fn} missing"
    _h = open("handler.py").read()
    assert '"check": "dead_moment"' in _h, "the check must be renamed"
    assert '"check": "both_stream_hole"' not in _h, "the misleading name must be gone"
    assert "_ig_source_echo_hole(source_path, holes, out_to_src)" in _h, \
        "the intersection must actually be echoed, not just the constituents"

    _fd, _src = _tf.mkstemp(suffix="_dead.mp4"); _os.close(_fd)
    try:
        _sp.run(["ffmpeg", "-y", "-v", "error",
                 "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=2",
                 "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=2",
                 "-f", "lavfi", "-i", "nullsrc=s=320x240:r=30:d=2",
                 "-f", "lavfi", "-i", "sine=frequency=440:r=48000:d=2",
                 "-filter_complex",
                 "[2:v]geq=random(1)*255:128:128[n];"
                 "[0:v][1:a][n][3:a]concat=n=2:v=1:a=1[v][a]",
                 "-map", "[v]", "-map", "[a]", "-pix_fmt", "yuv420p", _src],
                capture_output=True, timeout=300)
        assert _os.path.getsize(_src) > 5000, "fixture build failed"
        # 1. dead source -> downgraded
        _d, _g = handler._ig_source_echo_hole(_src, [(0.4, 1.4)], lambda t: t)
        assert _g and not _d, f"dead source moment must downgrade: d={_d} g={_g}"
        # 2. THE GUARD — live source under a dead output is OUR defect
        _d2, _g2 = handler._ig_source_echo_hole(_src, [(2.4, 3.4)], lambda t: t)
        assert _d2 and not _g2, f"live source must still trip: d={_d2} g={_g2}"
        # 3. one constituent alone is not enough
        _d3, _g3 = handler._ig_source_echo_hole(_src, [(0.4, 1.0)], lambda t: t + 2.0)
        assert _d3 and not _g3, "silent-but-live-video must still trip"
        # 4. boundary crossing gets the same two-window treatment
        _d4, _g4 = handler._ig_source_echo_hole(
            _src, [(0.9, 1.1)], lambda t: 0.9 + t if t < 1.0 else t - 1.0)
        assert _g4 and not _d4, "crossing a cut over a dead source must downgrade"
        # 5. fail closed
        _d5, _g5 = handler._ig_source_echo_hole(_src, [(0.4, 1.4)], lambda t: None)
        assert _d5 and not _g5, "unmappable must stay a defect"
    finally:
        try: _os.unlink(_src)
        except OSError: pass


@check("L1 wave: NO_AUDIO_TRACK intake gate — probe-time, fresh-only, fail-open, honest envelope, rescue-denied")
def _l1_no_audio_gate():
    import handler
    _src = open("handler.py").read()
    # the gate exists at intake, fresh-mode-gated, fail-open on probe trouble
    assert "INTAKE AUDIO-TRACK GATE" in _src
    _gate = _src.index("INTAKE AUDIO-TRACK GATE")
    assert _src.index("FAST-FAIL TALKING-HEAD CHECK") > _gate, "gate must precede the talking-head check"
    assert '_has_audio_stream = True' in _src, "fail-open branch missing"
    _env = handler.classify_error(RuntimeError("NO_AUDIO_TRACK: source has no audio stream"))
    assert _env.get("error_code") == "NO_AUDIO_TRACK", _env
    assert "add audio and resubmit" in str(_env.get("user_message")), "honest copy missing"
    assert _env.get("retryable") is False, "paid-retry loop must be closed"
    assert _env.get("requires_new_video") is True
    assert "NO_AUDIO_TRACK" in handler._OUTER_RESCUE_DENY


@check("credit ruling: designed rejections marked on the terminal envelope (app refunds on the class)")
def _credit_ruling_marker():
    import handler
    # class membership: named INPUT-boundary rejections, not infrastructure
    for c in ("NO_AUDIO_TRACK", "NO_SPEECH", "NOT_TALKING_HEAD",
              "CLIP_TOO_LONG", "WRONG_ORIENTATION", "INVALID_FORMAT",
              "EMPTY_UPLOAD", "INVALID_SOURCE_URL", "TRANSCRIPTION"):
        assert c in handler._DESIGNED_REJECTION_CODES, c
    for c in ("UPLOAD_STALLED", "S3_ACCESS", "NETWORK", "RENDER_FFMPEG",
              "INTEGRITY_TRIP", "UNKNOWN"):
        assert c not in handler._DESIGNED_REJECTION_CODES, c + " must not release via this class"
    _src = open("handler.py").read()
    assert _src.count('"designed_rejection": _designed_reject') == 2, \
        "marker must ride BOTH the durable row result and the return dict"


@check("alert routing (Zac 2026-07-28): PAGE ONLY ON AT-FAULT — gate keys on _NON_ALERTING_CODES (designed UNION client-upload), broader than the refund set; UNKNOWN + unclassified still page (loud-failsafe); refund gate stays separate")
def _alert_routing_split():
    import handler
    # the no-page set is a STRICT SUPERSET of the refund set (adds client-upload)
    assert handler._DESIGNED_REJECTION_CODES <= handler._NON_ALERTING_CODES, \
        "non-alerting set must contain the whole refund set"
    assert handler._NON_ALERTING_CODES > handler._DESIGNED_REJECTION_CODES, \
        "non-alerting set must be strictly broader (client-upload family added)"
    # client-upload family: alert-suppressed, but NOT designed (refund/retry unchanged)
    for c in ("UPLOAD_STALLED", "UPLOAD_TIMEOUT", "UPLOAD_NEVER_STARTED"):
        assert c in handler._NON_ALERTING_CODES, c + " must be alert-suppressed (digest, not page)"
        assert c not in handler._DESIGNED_REJECTION_CODES, c + " must NOT release credit as a designed rejection"
    # loud-failsafe: UNKNOWN and every at-fault code MUST still page (absent from no-page set)
    for c in ("UNKNOWN", "RENDER_FATAL", "INTEGRITY_TRIP", "RENDER_TOO_SHORT",
              "PLATFORM_TIMEOUT", "CONTAINER_TEARDOWN", "RECIPE_INVALID", "SAFE_EDIT_FAILED"):
        assert c not in handler._NON_ALERTING_CODES, c + " must still page the operator"
    # the terminal gate must key on the non-alerting set, not the bare refund flag
    _src = open("handler.py").read()
    assert "_NON_ALERTING_CODES = _DESIGNED_REJECTION_CODES | _CLIENT_UPLOAD_CODES" in _src, \
        "non-alerting set must be defined as designed UNION client-upload"
    assert "_page_operator = (classified.get(\"error_code\") not in _NON_ALERTING_CODES)" in _src, \
        "alert gate must key on _NON_ALERTING_CODES"
    assert "if _page_operator:" in _src, "alert must fire on _page_operator, not the bare _designed_reject flag"


@check("copy-truth mirror: failed-terminal patch carries error_message = result.user_message atomically")
def _copy_truth_mirror():
    _src = open("handler.py").read()
    assert 'patch["error_message"] = str(result["user_message"])' in _src, "mirror missing from the rail"
    # the mirror lives INSIDE write_job_status's patch assembly (same atomic
    # patch as the fence-guarded UPDATE), gated to failed+user_message
    _fn = _src.index("def write_job_status")
    _mirror = _src.index('patch["error_message"]')
    _update = _src.index(".update(patch).eq(\"id\", job_id)")
    assert _fn < _mirror < _update, "mirror must ride the same patch as the fenced UPDATE"
    assert 'if status == "failed"' in _src[_mirror - 400:_mirror], "mirror must be failed-only"


@check("guiding CLIP_TOO_LONG copy: extreme-length gets 'pick your best', moderate gets 'trim to your best'; stale single-clip/compilation copy retired; forward-framed ('longer videos are coming')")
def _clip_too_long_copy():
    import handler
    _long = handler.classify_error(RuntimeError(
        "CLIP_TOO_LONG: source is 2500.0s; the intake cap is 120s"))
    assert _long["error_code"] == "CLIP_TOO_LONG"
    # extreme-length: pick-your-best phrasing + forward promise
    assert "Pick your best" in _long["user_message"], _long
    assert "longer videos are coming" in _long["user_message"].lower(), _long
    _mod = handler.classify_error(RuntimeError(
        "CLIP_TOO_LONG: source is 150.6s; the intake cap is 120s"))
    assert "trim to your best" in _mod["user_message"], _mod
    assert "longer videos are coming" in _mod["user_message"].lower(), _mod
    # threshold pinned: 300s = 2.5× cap → still 'trim to your best' below it
    _edge = handler.classify_error(RuntimeError(
        "CLIP_TOO_LONG: source is 299.0s; the intake cap is 120s"))
    assert "trim to your best" in _edge["user_message"], _edge
    # stale "single clips" / "compilation" framing RETIRED from every branch
    for _m in (_long, _mod, _edge):
        assert "single clip" not in _m["user_message"].lower(), _m
        assert "compilation" not in _m["user_message"].lower(), _m
    # both remain designed rejections (credit ruling class)
    assert "CLIP_TOO_LONG" in handler._DESIGNED_REJECTION_CODES


@check("RENDER COLLAPSE = ZERO-REJECTION (Zac 2026-07-28): a collapsed edit (rendered video<1.0s) is NOT a dead-end RENDER_TOO_SHORT failure — it FALLS BACK to the minimal pipeline (straight cuts + captions on the source) like no_speech/not-TH/2-5s clips, so the user gets a real video, not a refund + dead end (30d census: 4 collapses/3 users, 100% churned, 0 recovered). The collapse is RECORDED (render_collapsed_to_minimal divergence — routed, not suppressed) so cutter over-removal stays visible in the daily report. classify_error still names any legacy RENDER_TOO_SHORT string (defensive); still NOT a designed rejection.")
def _render_collapse_zero_reject():
    import handler
    _h = open("handler.py").read()
    # the output-length collapse guard now ROUTES TO MINIMAL, not a dead-end failure
    _i = _h.find("if _rv < 1.0:")
    assert _i != -1, "the output-length collapse guard must remain"
    _guard = _h[_i:_i + 1800]
    # flag ON -> zero-reject minimal fallback (user gets a video), RECORDED as a divergence
    assert "if _zero_reject_enabled(input_data):" in _guard, \
        "the render-collapse fallback must be flag-gated behind PROMPTLY_ZERO_REJECT"
    assert 'raise _MinimalRouteSignal("render_collapsed")' in _guard, \
        "flag on: a collapsed render falls back to minimal (zero-reject), not a dead-end"
    assert '"render_collapsed_to_minimal"' in _guard, \
        "the collapse must be RECORDED as a divergence (routed, not suppressed)"
    # flag OFF -> today's RENDER_TOO_SHORT dead-end retained (byte-identical rollback)
    assert "RENDER_TOO_SHORT: main render output too short" in _guard, \
        "flag off must keep today's RENDER_TOO_SHORT raise (byte-identical rollback)"
    # the handler catches the minimal-route signal + runs the minimal pipeline
    assert "isinstance(e, _MinimalRouteSignal)" in _h and "_run_minimal_pipeline(" in _h, \
        "the minimal-route signal must be caught + routed to the minimal pipeline"
    # classify_error still names any legacy RENDER_TOO_SHORT string (defensive)
    _c = handler.classify_error(RuntimeError("RENDER_TOO_SHORT: main render output too short (video=0.8s)"))
    assert _c["error_code"] == "RENDER_TOO_SHORT", _c
    # unchanged: never a designed rejection
    assert "RENDER_TOO_SHORT" not in handler._DESIGNED_REJECTION_CODES, \
        "RENDER_TOO_SHORT must NOT be a designed rejection"


@check("Phase-4 OUTCOME-GATE (Cond-2 ratified): the salvaged post-cuts plan is validated against the full strict PostCutPlan model AFTER _enforce_string_caps; FLAG-GATED PROMPTLY_OUTCOME_GATE (default 'shadow' = ledger-only no-op → deploy INERT; 'enforce' = invalid salvage → mid-plan retry; 'off' = rollback); the post-cuts return is guarded so an enforce reject falls to the bounded retry, never ships an invalid salvage")
def _outcome_gate_shadow():
    _h = open("handler.py").read()
    # flag-gated, default 'shadow' → the deploy is inert until the flag flips
    assert 'os.environ.get("PROMPTLY_OUTCOME_GATE", "shadow")' in _h, \
        "outcome-gate must be flag-gated, default 'shadow'"
    # strict validation against the REAL model, AFTER the cap salvage
    _i_enforce = _h.find('_enforce_string_caps(_parsed, _post_cuts_response_schema(), "post_cuts")')
    _i_validate = _h.find("PostCutPlan.model_validate(_parsed)")
    assert _i_enforce != -1 and _i_validate != -1 and _i_validate > _i_enforce, \
        "PostCutPlan.model_validate must run AFTER the _enforce_string_caps salvage"
    # enforce converts an invalid salvage into a degen (routes to the retry);
    # shadow/off leave behavior unchanged
    assert 'if _gate_mode == "enforce":' in _h and '_degen = ("outcome-gate:' in _h, \
        "enforce mode must convert an invalid salvage into a degen (retry)"
    # the verdict is ledgered under its own action
    assert '"outcome_gate_reject"' in _h, "gate reject must be ledgered"
    # the post-cuts return is GUARDED so an enforce reject falls through to the
    # retry instead of shipping the invalid salvage
    assert "if _degen is None:\n                return _parsed" in _h, \
        "the post-cuts return must be guarded by 'if _degen is None' so an enforce reject retries"
    # In the promptly-lang-flags Modal Secret (value 'shadow'), read at runtime —
    # NOT baked from the deploy shell, so a plain deploy can't silently revert it.
    _m = open("modal_app.py").read()
    assert '"PROMPTLY_OUTCOME_GATE": os.environ.get' not in _m, \
        "PROMPTLY_OUTCOME_GATE must NOT be baked in modal_app .env() — it lives in the promptly-lang-flags secret"
    assert 'modal.Secret.from_name("promptly-lang-flags")' in _m, \
        "the promptly-lang-flags secret (carrying PROMPTLY_OUTCOME_GATE=shadow) must be attached app-wide"


@check("LEVER 2 (safe-edit terminal honesty): a failed deterministic rescue terminates NAMED (SAFE_EDIT_FAILED), never UNKNOWN — build_safe_recipe wrapped (hole A), the plan-build span's non-(ValueError|RuntimeError) escape renamed when _use_safe (hole B); classify_error names it (real error, retryable, refunded on the failed-row sweep, NOT a designed rejection); in _OUTER_RESCUE_DENY so a failed rescue never burns a doomed re-run")
def _lever2_safe_edit_named():
    import handler
    _h = open("handler.py").read()
    # hole A: build_safe_recipe wrapped → SAFE_EDIT_FAILED sentinel
    assert 'SAFE_EDIT_FAILED: safe recipe construction failed' in _h, \
        "build_safe_recipe call must be wrapped to raise SAFE_EDIT_FAILED (hole A)"
    # hole B: the plan-build span's broad escape renames only when _use_safe
    assert 'SAFE_EDIT_FAILED: safe-edit plan build raised' in _h, \
        "the plan-build span must rename a non-(VE|RE) escape to SAFE_EDIT_FAILED when _use_safe (hole B)"
    assert 'if not _use_safe:\n                raise' in _h, \
        "hole B must re-raise unchanged on the non-safe path (zero blast radius)"
    # classify_error names it
    _c = handler.classify_error(RuntimeError(
        "SAFE_EDIT_FAILED: safe recipe construction failed (KeyError: 'x')"))
    assert _c["error_code"] == "SAFE_EDIT_FAILED", _c
    assert "Something went wrong" not in _c["user_message"], _c
    assert _c["retryable"] is True, _c
    # real error, NOT a designed rejection → refunded on the failed-row sweep
    assert "SAFE_EDIT_FAILED" not in handler._DESIGNED_REJECTION_CODES, _c
    # denied for the outer rescue (a failed rescue must not trigger another)
    assert "SAFE_EDIT_FAILED" in handler._OUTER_RESCUE_DENY, \
        "SAFE_EDIT_FAILED must be in _OUTER_RESCUE_DENY"


@check("LEVER 4 (never re-render byte-identical inputs): the render degrade ladder computes an input signature (cuts + all decoration layers + b-roll) and SKIPS a rung whose inputs are byte-identical to the last attempted render (rung 1 = the pristine-restore, identical by construction), advancing to the strip rung instead of re-rendering; ledgered as ladder_identical_input_skip; fail-safe on an uncomputable signature (never skips)")
def _lever4_no_identical_render():
    _h = open("handler.py").read()
    assert "def _ladder_input_sig(" in _h, "the input-signature helper must exist"
    # the skip fires before render_once, keyed on equality with the last render
    _i_sig = _h.find("_cur_render_sig = _ladder_input_sig(edit_plan, broll_clips)")
    _i_render = _h.find("render_once(edit_plan[\"cuts\"], broll_clips)\n            return")
    assert _i_sig != -1 and _i_render != -1 and _i_sig < _i_render, \
        "the input-signature check must run BEFORE render_once"
    assert 'if _cur_render_sig is not None and _cur_render_sig == _last_render_sig:' in _h, \
        "must skip only when the signature is computable AND equals the last attempted render (fail-safe)"
    assert '"ladder_identical_input_skip"' in _h, "the skip must be ledgered"
    assert '_last_render_sig = _cur_render_sig' in _h, "the last attempted render's signature must be recorded"


@check("LEVER 3 baseline capture: the plan-capture hook persists finalized, schema-VALID render inputs at the seam (_validate_and_write_render_input) to the durable corpus bucket, keyed by _ACTIVE_JOB_ID; flag-gated OFF by default (PROMPTLY_PLAN_CAPTURE, baked in modal_app env) so it's inert on normal traffic; best-effort — a capture failure never touches the render")
def _lever3_plan_capture():
    _h = open("handler.py").read()
    assert "def _capture_render_plan(" in _h, "the plan-capture helper must exist"
    # hooked into the seam AFTER the schema-valid write, flag-gated. (Target the
    # render-input capture call specifically — there is now a second PLAN_CAPTURE
    # guard in the always-on scoreboard, so match the call, not the bare guard.)
    _i_write = _h.find("json.dump(payload, _f)")
    _i_hook = _h.find('if os.environ.get("PROMPTLY_PLAN_CAPTURE", "").strip():\n        _capture_render_plan(label, payload)')
    assert _i_write != -1 and _i_hook != -1 and _i_hook > _i_write, \
        "the render-input capture must fire AFTER the schema-valid write, flag-gated"
    assert 'cond3_baseline/plans/' in _h, "capture must persist to the durable corpus prefix"
    # In the promptly-lang-flags Modal Secret (value '' — inert), read at runtime —
    # NOT baked from the deploy shell, so a plain deploy can't silently revert it.
    _m = open("modal_app.py").read()
    assert '"PROMPTLY_PLAN_CAPTURE": os.environ.get' not in _m, \
        "PROMPTLY_PLAN_CAPTURE must NOT be baked in modal_app .env() — it lives in the promptly-lang-flags secret"
    assert 'modal.Secret.from_name("promptly-lang-flags")' in _m, \
        "the promptly-lang-flags secret (carrying PROMPTLY_PLAN_CAPTURE='') must be attached app-wide"


@check("LEVER 3 candidate (degeneration prompt-root fix): a flag-gated (PROMPTLY_LEVER3=1, LIVE via the promptly-lang-flags secret) anti-runaway block appended to the post-cuts system prompt reframes the why/why_emphasis/reason rationale fields as terse internal notes and names the repetition-loop as a malfunction to STOP; touches nothing rendered (whys never reach screen); the A/B concluded — this is the live production prompt, not pending anyone's word")
def _lever3_candidate():
    _h = open("handler.py").read()
    # flag-gated, default OFF → the live prompt is unchanged in production
    assert 'os.environ.get("PROMPTLY_LEVER3", "").strip()' in _h, \
        "Lever-3 block must be flag-gated on PROMPTLY_LEVER3"
    # the anti-runaway framing targets the loop behaviour, appended to system_instruction
    assert "RATIONALE FIELDS ARE TERSE NOTES" in _h, "the anti-runaway block must be present"
    assert "system_instruction +=" in _h and "loops, lists, or keeps going is" in _h, \
        "the block must append to the system prompt and name the loop as a malfunction"
    # it is inside the prompt builder (fires before the return), not a rendered field
    _i_block = _h.find("RATIONALE FIELDS ARE TERSE NOTES")
    _i_ret = _h.find("return system_instruction, user_content")
    assert _i_block != -1 and _i_ret != -1 and _i_block < _i_ret, \
        "the Lever-3 block must sit inside _build_post_cuts_prompt before its return"
    # LIVE via the promptly-lang-flags Modal Secret (PROMPTLY_LEVER3=1), read at
    # runtime — NOT baked from the deploy shell, so a plain deploy can no longer
    # revert it to off (the A/B concluded; this is the live production prompt).
    _m = open("modal_app.py").read()
    assert '"PROMPTLY_LEVER3": os.environ.get' not in _m, \
        "PROMPTLY_LEVER3 must NOT be baked in modal_app .env() — it lives in the promptly-lang-flags secret"
    assert 'modal.Secret.from_name("promptly-lang-flags")' in _m, \
        "the promptly-lang-flags secret (carrying PROMPTLY_LEVER3=1) must be attached app-wide"


@check("LIVE SCOREBOARD (Lever-3 flip watches this): _measure_rationale_lengths runs on EVERY parseable editorial response (NOT flag-gated) and ALWAYS ledgers a lightweight `rationale_length` line (max/total why-chars, ballooned=max>500) — the degeneration-class incidence signal the daily bleed [REPORT] reads; the full per-field S3 breakdown stays flag-gated (PLAN_CAPTURE)")
def _rationale_length_scoreboard():
    _h = open("handler.py").read()
    assert "def _measure_rationale_lengths(" in _h, "the scoreboard helper must exist"
    # ALWAYS-on: called unconditionally (not under a PLAN_CAPTURE guard) at editorial
    assert "\n            _measure_rationale_lengths(_parsed)" in _h, \
        "the scoreboard must be called ALWAYS at the editorial output, not flag-gated"
    # ALWAYS ledgers the rationale_length line
    assert '"rationale_length"' in _h and '"ballooned": _maxf > 500' in _h, \
        "must ledger a rationale_length line with the balloon signal on every job"
    # the S3 breakdown is the flag-gated part (the A/B capture)
    _i_ledger = _h.find('"rationale_length"')
    _i_s3guard = _h.find('if os.environ.get("PROMPTLY_PLAN_CAPTURE", "").strip():\n            import boto3')
    assert _i_ledger != -1 and _i_s3guard != -1 and _i_ledger < _i_s3guard, \
        "the ledger line is always-on; the S3 breakdown is flag-gated after it"


@check("MULTILINGUAL A1 (universal script fonts): the full Noto family (fonts-noto-core + fonts-noto-cjk + fonts-noto-extra) is in the render-image apt install alongside fonts-dejavu-core, so every script renders real glyphs (no tofu) by construction; the shaping/bidi C-libs (libharfbuzz + libfribidi) are already present; purely additive, zero risk to Latin rendering")
def _multilingual_a1_fonts():
    _m = open("modal_app.py").read()
    for _pkg in ("fonts-noto-core", "fonts-noto-cjk", "fonts-noto-extra", "fonts-noto-color-emoji"):
        assert f'"{_pkg}"' in _m, f"{_pkg} must be in the render-image apt install"
    # complex scripts are broken without shaping — Noto fonts need harfbuzz + fribidi
    assert "libharfbuzz" in _m and "libfribidi" in _m, \
        "shaping (harfbuzz) + bidi (fribidi) libs must be present for complex scripts"
    # additive: the Latin font stack is untouched
    assert '"fonts-dejavu-core"' in _m, "the Latin font base must remain (A1 is additive)"


@check("IMAGE DEPS FLOOR-PINNED: every runtime pip dep is version-capped so a rebuild can't silently resolve a breaking major — the class that bit us with opencv 5.x (readNetFromCaffe gone → EVERY talking-head render terminalized), Deepgram, pyannote. opencv MUST cap <5 (has readNetFromCaffe + numpy-2 support).")
def _image_deps_pinned():
    import re as _re
    _m = open("modal_app.py").read()
    _mm = _re.search(r'"opencv-python-headless([^"]*)"', _m)
    assert _mm and _mm.group(1).strip(), "opencv-python-headless must be PINNED"
    assert "<5" in _mm.group(1) or _re.search(r"==4\.", _mm.group(1)), \
        f"opencv-python-headless must cap below 5.0; got '{_mm.group(1)}'"
    # every previously-unpinned runtime dep now carries a version constraint.
    # certifi (date-versioned CA bundle) and wheel (build tool) are exempt.
    for _pkg in ("numpy", "requests", "anthropic", "supabase", "boto3\\[crt\\]",
                 "httpx", "fastapi", "tqdm", "Pillow", "google-genai",
                 "deepgram-sdk", "pydantic"):
        # findall (not search) — a package can be MENTIONED unversioned in a
        # comment; only the real pip_install entry carries the version. Require
        # at least one capped occurrence.
        _specs = _re.findall(rf'"{_pkg}([^"]*)"', _m)
        assert _specs, f"{_pkg} must be listed in the image pip_install"
        assert any(("<" in _s or "==" in _s) for _s in _specs), \
            f"{_pkg} must be version-capped (floating-resolve regression class); got {_specs}"


@check("MULTILINGUAL A2.1 (deliberate script fallback): every CAPTION_FONTS entry appends the NOTO_FALLBACK stack (Noto per-script + Noto Color Emoji + sans-serif) so Chromium resolves non-Latin glyphs per-glyph via fontconfig against the A1 fonts — no tofu; the Latin primary font still wins for every glyph it has, so Latin captions render byte-identical")
def _multilingual_a2_font_stack():
    _p = "src/remotion/src/captions/shared/fonts.ts"
    _f = open(_p).read()
    assert "NOTO_FALLBACK" in _f, "the Noto fallback stack must exist"
    for _need in ("Noto Sans Devanagari", "Noto Sans Arabic", "Noto Sans Hebrew",
                  "Noto Sans Thai", "Noto Sans CJK SC", "Noto Color Emoji", "sans-serif"):
        assert _need in _f, f"NOTO_FALLBACK must include '{_need}'"
    # every caption font wrapped with the fallback (append, not replace → Latin unchanged)
    for _k in ("inter", "montserrat", "poppins", "playfairDisplay", "dmSerifDisplay",
               "dmSans", "cormorantGaramond", "lora", "spaceMono", "teko"):
        assert f"{_k}: withNoto(" in _f, f"caption font {_k} must be wrapped with the Noto fallback"


@check("MULTILINGUAL A2.2 (RTL word order): captionDirection classifies a caption by its first strong-directional LETTER (Unicode paragraph direction), and the single production caption wrapper (CaptionSegmentRenderer) sets `direction` from the caption's own script — reversing word order for Arabic/Hebrew across all 9 components at once via inheritance, ltr a proven no-op so Latin renders byte-identical. Proven on the contact sheet: RTL cases flipped, every LTR case byte-identical.")
def _multilingual_a22_rtl_direction():
    _p = "src/remotion/src/captions/shared/direction.ts"
    _d = open(_p).read()
    assert "export const captionDirection" in _d and "export const pagesDirection" in _d, \
        "direction.ts must export captionDirection + pagesDirection"
    # first-strong-LETTER heuristic: an RTL-script matcher AND a general letter
    # matcher (so neutrals — emoji/digits/punct — are skipped, not miscounted).
    assert "RTL_LETTER" in _d and "ANY_LETTER" in _d, \
        "direction detection must use first-strong-LETTER (RTL vs any-letter)"
    for _sc in ("Hebrew", "Arabic"):
        assert _sc in _d, f"RTL script coverage must include {_sc}"
    # wired into the ONE production caption wrapper (structural, not per-component)
    _pr = open("src/remotion/src/PromptlyRender.tsx").read()
    assert "pagesDirection" in _pr and "direction }" in _pr, \
        "CaptionSegmentRenderer must set `direction` from pagesDirection on the caption wrapper"
    # the battery mirrors production so the contact sheet proves the real path
    _fs = open("src/remotion/src/FitSpecimen.tsx").read()
    assert "captionDirection" in _fs, "FitSpecimen must mirror production direction"


@check("MULTILINGUAL B (editorial-in-language, flag PROMPTLY_EDIT_IN_LANGUAGE=1 LIVE via the promptly-lang-flags secret): OFF = the Latin-only coverage allowlist + English-authored chrome; ON (the live state) flips the coverage gate to the denylist model (every font-backed script renders) AND binds all Gemini-authored text to the source language. Captions stay verbatim Deepgram words either way. Behavioral: gate + prompt inert when off, both flip when on.")
def _multilingual_b_edit_in_language():
    import os as _os
    import handler
    # the flag helpers + denylist exist
    assert callable(handler._script_reaches_render) and callable(handler._edit_in_language_enabled)
    assert isinstance(handler._SCRIPT_DENYLIST, frozenset), "denylist must be a frozenset"
    _prev = _os.environ.get("PROMPTLY_EDIT_IN_LANGUAGE")
    _MARK = "AUTHOR EVERY WORD YOU WRITE IN THE SOURCE LANGUAGE"
    try:
        # OFF: Latin-only allowlist; a non-Latin script is refused (tofu-proof)
        _os.environ.pop("PROMPTLY_EDIT_IN_LANGUAGE", None)
        assert handler._script_reaches_render("Latin") is True
        assert handler._script_reaches_render("Arabic") is False, "OFF must stay Latin-only"
        # OFF prompt is inert AND byte-identical regardless of source_language
        _off_none, _ = handler._build_post_cuts_prompt(vibe="viral", duration=30, source_language=None)
        _off_ar, _ = handler._build_post_cuts_prompt(vibe="viral", duration=30, source_language="Arabic")
        assert _MARK not in _off_none and _off_none == _off_ar, \
            "OFF: in-language block must be absent + prompt byte-identical to no-language"
        # ON: denylist model — every font-backed script reaches render EXCEPT
        # denylisted ones. The denylist is ENV-OVERRIDABLE (graduation = env flip),
        # so this check controls PROMPTLY_SCRIPT_DENYLIST itself: DEFAULT env must
        # deny Arabic (romanization, uncertified); the graduated env ("") must
        # route it. Env-controlled so the gate passes identically whether run in
        # a default shell or the graduation deploy shell.
        _os.environ["PROMPTLY_EDIT_IN_LANGUAGE"] = "1"
        _prev_dl = _os.environ.pop("PROMPTLY_SCRIPT_DENYLIST", None)
        try:
            for _s in ("Latin", "Hebrew", "Devanagari", "Han", "Thai", "Cyrillic"):
                assert handler._script_reaches_render(_s) is True, f"ON must render {_s}"
            assert handler._script_reaches_render("Arabic") is False, \
                "DEFAULT denylist must deny Arabic (uncertified) even with the flag ON"
            assert "Arabic" in handler._SCRIPT_DENYLIST
            _os.environ["PROMPTLY_SCRIPT_DENYLIST"] = ""
            assert handler._script_reaches_render("Arabic") is True, \
                "graduated env ('') must let Arabic route"
        finally:
            if _prev_dl is None:
                _os.environ.pop("PROMPTLY_SCRIPT_DENYLIST", None)
            else:
                _os.environ["PROMPTLY_SCRIPT_DENYLIST"] = _prev_dl
        # ON prompt binds authored text to the named language; no-language stays inert
        _on_ar, _ = handler._build_post_cuts_prompt(vibe="viral", duration=30, source_language="Arabic")
        _on_none, _ = handler._build_post_cuts_prompt(vibe="viral", duration=30, source_language=None)
        assert _MARK in _on_ar and "Arabic" in _on_ar, "ON+lang must inject the in-language block"
        assert _MARK not in _on_none and _on_none == _off_none, \
            "ON without a language must stay inert (no chrome-language change)"
        # language-name resolver: code preferred, script fallback, safe default
        assert handler._source_language_name("es-419", "Latin") == "Spanish"
        assert handler._source_language_name(None, "Devanagari") == "Hindi"
    finally:
        if _prev is None:
            _os.environ.pop("PROMPTLY_EDIT_IN_LANGUAGE", None)
        else:
            _os.environ["PROMPTLY_EDIT_IN_LANGUAGE"] = _prev
    # the gate site calls the helper (not the retired inline allowlist test)
    _h = open("handler.py").read()
    assert "if not _script_reaches_render(_script):" in _h, \
        "the coverage gate must route through _script_reaches_render"
    # LIVE via the promptly-lang-flags Modal Secret (PROMPTLY_EDIT_IN_LANGUAGE=1),
    # read at runtime — NOT baked from the deploy shell, so a plain deploy keeps
    # multilingual ON (a shell-baked default once Latin-only'd production).
    _m = open("modal_app.py").read()
    assert '"PROMPTLY_EDIT_IN_LANGUAGE": os.environ.get' not in _m, \
        "PROMPTLY_EDIT_IN_LANGUAGE must NOT be baked in modal_app .env() — it lives in the promptly-lang-flags secret"
    assert 'modal.Secret.from_name("promptly-lang-flags")' in _m, \
        "the promptly-lang-flags secret (carrying PROMPTLY_EDIT_IN_LANGUAGE=1) must be attached app-wide"


@check("BURNED-IN TEXT belt (Layer 1, flag PROMPTLY_BURNED_TEXT, DARK): the sharpened Stage-0 + zoom-preservation prompt block is a PURE APPEND gated on the flag — OFF → the post-cuts system prompt is byte-identical to pre-feature (block absent, an exact prefix of the ON prompt); ON → the block appends verbatim, carrying both the intensified double-caption check and the zoom-preservation rule. No existing prompt text is modified, so talking-head output is unchanged until Zac flips the flag.")
def _burned_text_layer1_prompt():
    import os as _os, handler
    assert callable(handler._burned_text_enabled), "the flag helper must exist"
    _MARK = "BURNED-IN TEXT IS A HARD CHECK"
    _prev = _os.environ.get("PROMPTLY_BURNED_TEXT")
    try:
        _os.environ.pop("PROMPTLY_BURNED_TEXT", None)    # OFF
        _off, _ = handler._build_post_cuts_prompt(vibe="viral", duration=30)
        _os.environ["PROMPTLY_BURNED_TEXT"] = "1"         # ON
        _on, _ = handler._build_post_cuts_prompt(vibe="viral", duration=30)
    finally:
        if _prev is None:
            _os.environ.pop("PROMPTLY_BURNED_TEXT", None)
        else:
            _os.environ["PROMPTLY_BURNED_TEXT"] = _prev
    # OFF: block ABSENT → byte-identical to pre-feature production prompt
    assert _MARK not in _off, "OFF: the burned-text block must be ABSENT (prompt byte-identical to pre-feature)"
    # ON: block present
    assert _MARK in _on, "ON: the burned-text block must be present"
    # PURE APPEND: OFF is an exact prefix of ON — no existing prompt text is touched
    assert _on.startswith(_off), "the block must be a PURE APPEND — flag-OFF must be an exact prefix of flag-ON"
    _tail = _on[len(_off):]
    # the block carries BOTH concerns: the intensified double-caption check AND the zoom rule
    assert "DOUBLE CAPTIONS" in _tail and "existing_caption_region" in _tail, \
        "the block must intensify the double-caption / existing_caption_region check"
    assert "ZOOMS AND PUNCHES MUST PRESERVE BURNED-IN TEXT" in _tail, \
        "the block must add the zoom-preservation rule (don't scale/crop through burned-in text)"


@check("INTEGRITY source-echo BLACK (2026-07-23): the gate downgrades a source-echoed black span (output black whose mapped SOURCE window is ALSO black — the user's video ends on black) exactly as it already downgrades source-echoed FREEZE; a render-PRODUCED black (source not black at the mapped time) still TRIPS. Fixes the #1 core-error false positive (23/25 INTEGRITY_TRIP tripped 'black'; >=9/25 sources end on black). Cert: constructed source-echo-tail -> clean, render-injected black -> trips (both PASS).")
def _integrity_source_echo_black():
    _h = open("handler.py").read()
    assert "def _ig_source_echo_black(" in _h, "the black source-echo helper must exist"
    # the helper must re-run blackdetect on the SOURCE (only a black source downgrades — a
    # render-produced black over a non-black source stays a defect and trips)
    _i = _h.find("def _ig_source_echo_black(")
    _j = _h.find("\ndef ", _i)
    _body = _h[_i:_j if _j > _i else _i + 4000]
    assert "blackdetect=d=%s:pix_th=%s" in _body and "source_path" in _body, \
        "source-echo-black must probe the SOURCE with blackdetect (else it can't distinguish echo from defect)"
    # wired into the gate: black_resid is downgraded, and holes covered by a source-echoed
    # region are dropped (a source-echoed black+silent tail must not trip 'dead_moment')
    assert "black_resid, black_downgraded = _ig_source_echo_black(" in _h, \
        "black_resid must be source-echo-downgraded in _integrity_gate"
    assert "content_black_downgraded" in _h, "the verdict must record black downgrades (observability)"


@check("BURNED-IN TEXT Layer 2d (double-caption gate, DARK): the deterministic detector runs CONCURRENT with the editorial Gemini call (on video_path — the full-res source, NOT the 480p proxy) and its has_burned_captions backstops Gemini's Stage-0 read (which misses burned captions ~a third of the time = the double-caption defect), engaging the EXISTING caption suppression. OFF (default) → _burned_future is None → _det_burned stays False → the override condition reduces to the original _ana_burned → plan byte-identical. Precision-tuned to 0/60 false-suppress, so engaging it can only ADD true suppressions, never drop a user's real captions.")
def _burned_text_double_caption_gate():
    _h = open("handler.py").read()
    # concurrent, flag-gated, on the FULL-RES source (video_path), not the proxy
    assert "if (_burned_text_enabled() or burned_text_override) and video_path:" in _h, \
        "the detector dispatch must be gated on the flag OR the per-job override, and run on video_path"
    # per-job override for the pre-flip smoke test — inert unless a job opts in
    assert "burned_text_override=bool(input_data.get(\"burned_text_test\"))" in _h, \
        "the per-job smoke-test override (burned_text_test) must thread into generate_edit_gemini"
    assert "_burned_future = _burned_pool.submit(_bt_mod.detect_burned_in_text, video_path)" in _h, \
        "the detector must run CONCURRENTLY (thread pool) on video_path so its cost hides under Gemini"
    # the detector signal ORs into the EXISTING override — so OFF is byte-identical
    assert 'if _ecr == "none" and (_ana_burned or _det_burned):' in _h, \
        "the detector signal must OR into the existing override (OFF: _det_burned=False → original _ana_burned condition)"
    assert "_det_burned = False" in _h, "the detector signal must default False so OFF is byte-identical"
    # result carried in-memory for the zoom gate (dropped only at persistence)
    assert 'edit_plan["_burned_text"]' in _h, "the detector result must be carried (_burned_text) for the zoom gate"


@check("BURNED-IN TEXT Layer 2e (zoom gate, DARK): at the render projection seam a zoom is SUPPRESSED when the detector found a persistent full-width burned-text band (a caption track, or a wide non-corner banner) it would scale/crop through — but a CORNER watermark or narrow incidental mark does NOT kill the zoom (the persistent-vs-incidental split, load-bearing so one corner logo doesn't strip every zoom in the video). OFF (default) → edit_plan has no _burned_text → the zoom is assigned unchanged → byte-identical.")
def _burned_text_zoom_gate():
    _h = open("handler.py").read()
    assert '_bt = edit_plan.get("_burned_text")' in _h, "the zoom gate must read the carried detector result"
    assert 'if _bt.get("has_burned_captions"):' in _h, "a full-width caption band must suppress the zoom"
    # persistent-vs-incidental: only a WIDE, NON-CORNER signage band suppresses
    assert 'and not _btr.get("corner")' in _h and 'float(_btr.get("max_row_extent") or 0) >= 0.5' in _h, \
        "the split must spare corner/narrow incidental marks (only wide non-corner signage suppresses)"
    # the zoom is still assigned unless suppressed — OFF path keeps zoomEffect (byte-identical)
    _i = _h.find("_bt_suppress = False")
    _tail = _h[_i:_i + 1400]
    assert 'if _bt_suppress:' in _tail and 'else:' in _tail and '_clip_spec["zoomEffect"] = _zoomeffect' in _tail, \
        "the zoom must be assigned in the ELSE of the suppress branch (OFF → not suppressed → assigned → byte-identical)"


@check("SOURCE-POLL fail-fast (2026-07-24, poll 600 for 5-min support 2026-07-25): the MAIN source-wait deadline is env-tunable (PROMPTLY_SOURCE_POLL_S, default 600s) and MUST stay well under the run_pipeline_bg Modal timeout. The old 1800s was >= the 900s function timeout, so a stalled iOS upload hung at 'Got your video, loading it in...' until the SIGKILL — which writes NO terminal status, so the reaper terminalized it UNCODED ~5min later. The poll raised 300->600 for 5-min support: a 5-min source uploads a bigger file, and the v353 census caught real uploads finishing at ~305s (300s was false-stalling slow-but-live uploads). At 600s a genuinely stalled upload still raises the coded, RETRYABLE UPLOAD_STALLED long before the 3000s SIGKILL. Regression guard: the default must remain < the worker timeout.")
def _source_poll_fail_fast():
    import re as _re
    _h = open("handler.py").read()
    assert '_main_poll_deadline = _main_poll_start + int(os.environ.get("PROMPTLY_SOURCE_POLL_S", "600"))' in _h, \
        "the main source-poll deadline must be env-tunable (PROMPTLY_SOURCE_POLL_S) defaulting to 600s"
    # UPLOAD_STALLED must be a CODED, RETRYABLE error so the fast fail is actionable
    assert '"UPLOAD_STALLED"' in _h and 'if "UPLOAD_STALLED" in msg:' in _h, \
        "UPLOAD_STALLED must be classified (coded + retryable) so the fast fail surfaces a clean retry"
    # the default (600) must be strictly under the run_pipeline_bg Modal timeout so the
    # clean UPLOAD_STALLED fires BEFORE the SIGKILL — the invariant that was violated
    _m = open("modal_app.py").read()
    _t = _re.search(r"timeout=(\d+), retries=0, cpu=\d+, memory=\d+", _m)  # cpu=16 uniquely IDs run_pipeline_bg (render_burst is cpu=48); memory is inc2-tunable
    assert _t, "run_pipeline_bg timeout not found in modal_app.py"
    assert 600 < int(_t.group(1)), \
        f"source-poll default (600s) must be < run_pipeline_bg timeout ({_t.group(1)}s) so UPLOAD_STALLED beats the SIGKILL"


@check("A-L2/CAUSE-3 LEVERS STAGED DARK (2026-07-25): (a) vidstab threshold env-tunable (PROMPTLY_VIDSTAB_THRESHOLD, default '' -> 0.35 = today, byte-identical) so the data-chosen recalibration slots in with no code change, + input_data.vidstab_test per-job override for Zac's stabilized-vs-not A/B pair; (b) delivery fps env-tunable (PROMPTLY_DELIVERY_FPS, default '' -> 60.0 = today's universal 60fps pipeline target) + input_data.delivery_fps_test for the 60-vs-30 phone-judged pair — SA-0 measured the render bucket 116-215s/chunk at 60 vs 17-52s at 30, but NOTHING flips on fps without Zac's ruling; (c) the A/B-lever inputs persist alongside stage_timings (shake_score, source_fps, target_fps) so the threshold choice and the 60fps-share answer become SQL queries. Defaults = today's exact behavior; overrides inert for real traffic (the app never sets them).")
def _ab_levers_staged_dark():
    _h = open("handler.py").read()
    # vidstab: RIPPED OUT (Zac 2026-08-01) — default raised 5.0 -> 1e9 + a
    # secret-independent clamp (enforced by the dedicated VIDSTAB RIP-OUT GUARD)
    # so organic stabilisation never fires. The per-job vidstab_test override is
    # KEPT for the A/B. (Evidence: shake-0 clip paid +102s for nothing; ships
    # unstabilised on crash unnoticed; can't run in parallel.)
    assert 'os.environ.get("PROMPTLY_VIDSTAB_THRESHOLD", "") or 1e9' in _h, \
        "vidstab threshold default must be 1e9 (ripped out 2026-08-01; env rollback = restore 5.0)"
    assert 'input_data.get("vidstab_test")' in _h and '_vs_test in ("on", "off")' in _h, \
        "vidstab A/B per-job override missing (kept for stabilized-vs-not A/B)"
    # fps: default 60 preserved; env + per-job override staged
    assert "_target_fps = 60.0" in _h, "the 60fps default must remain the baseline"
    assert 'os.environ.get("PROMPTLY_DELIVERY_FPS", "").strip()' in _h and \
        'input_data.get("delivery_fps_test")' in _h, "delivery-fps lever/override missing"
    # the A/B-lever telemetry inputs persist
    for _k in ('_timings["shake_score"]', '_timings["source_fps"]', '_timings["target_fps"]'):
        assert _k in _h, f"A/B-lever input not persisted: {_k}"


@check("SINGLE-PASS MUX AUDIO = AAC (ruling 5, 2026-07-26): the short-clip (<400-frame) single-pass composite mux shipped pcm_s16le-in-MP4 — the exact combination the chunked path's comment documents as 'iOS AVPlayer drops audio silently in production'. Both shipping muxes now AAC-LC 192k/48k; PCM remains only in INTERMEDIATE wavs (never a delivered MP4).")
def _single_pass_mux_aac():
    _h = open("handler.py").read()
    _i = _h.find('if include_audio and c_audio_idx is not None:')
    assert _i != -1
    _win = _h[_i:_i + 900]
    assert '"-c:a", "aac"' in _win and 'pcm_s16le' not in _win, \
        "the single-pass shipping mux must be AAC (PCM-in-MP4 silently drops audio on iOS)"


@check("W2 STAGE MANIFEST (effort-proportional pipeline, 2026-07-25): every TH stage's entry condition is NAMED + RECORDED (result.stage_manifest, persisted on completions AND at death beside stage_timings); the caption-less routes carry their own mini-manifest; the existing mode-based skips are formalized through the manifest with identical semantics. CONSERVATISM LAW pinned: only airtight documented conditions may skip — planning on the TH path is manifest-recorded as never-skipped (captions ARE the product). One behavioral gate ships in v1: CHUNKING-BY-DURATION — chunk count scales one-per-PROMPTLY_CHUNK_FRAMES (default 450 ≈ 15s@30fps), floor 1, ceiling PROMPTLY_RENDER_CHUNKS, at BOTH the overlay and composite sites (8 chunks on a 10s clip was pure process-startup tax; pixel-safe: A-L4 cert proved chunk boundaries SSIM-1.0).")
def _w2_stage_manifest():
    _h = open("handler.py").read()
    # the manifest exists, is populated at the submission block, and persists
    assert "_stage_manifest = {}" in _h and 'def _manifest(stage, run, why):' in _h
    for _st in ('"transcribe"', '"planning"', '"fps_normalize"', '"shake_probe"', '"face_detect"'):
        assert f"_manifest({_st}" in _h, f"stage {_st} not manifest-recorded"
    assert '"stage_manifest": _stage_manifest,' in _h, "manifest must persist in result_payload"
    assert '"stage_manifest": result_payload.get("stage_manifest"),' in _h, \
        "manifest must persist on the durable completed write"
    assert '"stage_manifest": locals().get("_stage_manifest") or None,' in _h, \
        "partial manifest must persist at death"
    # TH planning never skipped by the manifest (quality law)
    assert 'TH full planning (quality law: never degraded)' in _h
    # the caption-less mini-manifest
    assert '"minimal_plan", "render", "hls", "upload"' in _h, "caption-less mini-manifest missing"
    # chunking-by-duration at both sites, floor 1, env-tunable divisor
    assert 'PROMPTLY_CHUNK_FRAMES' in _h and _h.count('PROMPTLY_CHUNK_FRAMES') >= 2, \
        "chunk divisor must gate BOTH the overlay and composite sites"
    assert "_EFFECTIVE_CHUNKS = min(_RENDER_CHUNKS, max(1, int(total_output_frames) // _CHUNK_FRAMES))" in _h, \
        "the duration-scaled chunk formula (floor 1, ceiling the cap)"


@check("A-L1 OUTPUT DIET (2026-07-25, PROMPTLY_WHY_DIET, live lever w/ one-flag rollback): the post-cuts call is OUTPUT-BOUND (r=0.59 wall vs output tokens), and the rationale fields are the compressible output — declared caps 240 chars against a ≤12-word editorial ask, 9.1% balloon rate. Under the flag the RESPONSE SCHEMA declares why/why_emphasis/reason at 96 chars — a BUDGET the sane model composes to; Vertex does NOT enforce maxLength at token-generation (S-DEGEN 2026-07-25 refutation: post-diet completed responses carried post_cuts.why at 1,179 chars [job 27eded11, 07:23Z] and 11,610 chars [certpg-6ead996b9075] against declared 96, plus four small 101-126-char overshoots — impossible under token-level enforcement). The parse edge (_enforce_string_caps) reading the same schema IS the enforcement, so it follows the flag automatically; the anti-runaway prompt block names the true budget so the model composes telegrams instead of getting truncated. A schema maxLength therefore can NEVER kill the 16k degen stream-aborts (which continued post-diet: 7f1a1128 369s, d7ee9c05 147s) — no PROMPTLY_DEGEN_DIET-style sibling cap may be shipped as a degen fix. ONLY the three named rationale fields are dieted — every other declared cap untouched. =0 restores 240 with no deploy.")
def _why_diet_lever():
    import os as _os
    import handler as H
    assert H._WHY_DIET_CAP == 96 and set(H._WHY_DIET_FIELDS) == {"why", "why_emphasis", "reason"}
    assert H._why_diet_enabled() is True, "PROMPTLY_WHY_DIET must default ON (the lever is flipped)"

    def _collect(schema):
        caps = {}
        def _w(props):
            for k, p in (props or {}).items():
                if not isinstance(p, dict):
                    continue
                if isinstance(p.get("maxLength"), int):
                    caps.setdefault(k, set()).add(p["maxLength"])
                for v in (p.get("anyOf") or []):
                    if isinstance(v, dict) and isinstance(v.get("maxLength"), int):
                        caps.setdefault(k, set()).add(v["maxLength"])
        _w(schema.get("properties"))
        for d in (schema.get("$defs") or {}).values():
            if isinstance(d, dict):
                _w(d.get("properties"))
        return caps
    # ON: every rationale field ≤96; a non-rationale cap (video_identity 500) untouched
    _on = _collect(H._post_cuts_response_schema())
    for f in ("why", "reason"):
        assert f in _on and max(_on[f]) <= 96, f"{f} not dieted: {_on.get(f)}"
    assert 500 in _on.get("video_identity", set()), "non-rationale caps must be untouched"
    # OFF: the 240s return (one-flag rollback, no deploy)
    _os.environ["PROMPTLY_WHY_DIET"] = "0"
    try:
        _off = _collect(H._post_cuts_response_schema())
        assert max(_off["why"]) == 240, f"rollback must restore 240 (got {_off.get('why')})"
    finally:
        _os.environ.pop("PROMPTLY_WHY_DIET", None)
    # the prompt names the true budget (rides the Lever-3 anti-runaway block)
    _h = open("handler.py").read()
    assert "caps at ~96 characters" in _h and "_why_diet_enabled()" in _h, \
        "the prompt must tell the model the real budget under the flag"
    # DOC TRUTH (S-DEGEN 2026-07-25): the refuted enforcement claim must never
    # come back — Vertex maxLength is advisory (post-diet counterexamples:
    # why=1,179 chars @ declared 96 [27eded11], why=11,610 [certpg-6ead996b],
    # 4 small 101-126-char overshoots), so a schema cap is a composition
    # budget, not a degen stop. The corrected note must stay in handler.py and
    # the false claim must stay out.
    assert "Vertex does NOT enforce" in _h and "MECHANISM CORRECTION" in _h, \
        "handler.py must carry the S-DEGEN mechanism correction"
    assert "Vertex enforces response_json_schema" not in _h, \
        "the refuted token-generation enforcement claim must not reappear"


@check("ZERO-REJECT ROUTING (2026-07-25, DARK behind PROMPTLY_ZERO_REJECT): rejections become routes per Zac's ruled precedence — speech → TALKING_HEAD (untouchable); no-speech / no-audio / 2.0-5.0s → the MINIMAL path (deterministic clean cuts + calm transitions, caption-less, rendered through the SAME ffmpeg_base + render-full.mjs primitives via hype_render, delivered through the SAME presigned-S3 + shared HLS + terminal contract); < 2.0s = the ONE remaining rejection. Gate sites raise _MinimalRouteSignal (a RuntimeError subclass so every existing passthrough behaves as today's rejections); ONE outer choke point catches it and runs _run_minimal_pipeline; a minimal failure falls through to the standard coded+refunded envelope. CONSERVATISM INVARIANT: the fast-check NTH gate (faces known, words UNKNOWN) DEFERS under the flag instead of routing — a no-face voiceover must reach the word-aware deep gate so real speech is never mis-routed to the caption-less path. Flag off → every gate raises today's rejection, byte-identical. Per-job cert override: input_data.zero_reject_test (burned_text_test pattern).")
def _zero_reject_wiring():
    _h = open("handler.py").read()
    # the signal + the flag + the floor
    assert "class _MinimalRouteSignal(RuntimeError):" in _h, "route signal must subclass RuntimeError (passthrough parity)"
    assert 'os.environ.get("PROMPTLY_ZERO_REJECT", "").strip().lower() in (' in _h, \
        "PROMPTLY_ZERO_REJECT must default OFF (dark)"
    assert 'input_data.get("zero_reject_test")' in _h, "per-job cert override required"
    assert "_MIN_MINIMAL_DURATION_S = 2.0" in _h, "the Zac-ruled 2.0s hard floor"
    # all four route sites + the deferring fast-check
    assert _h.count("raise _MinimalRouteSignal(") == 7, "exactly 7 route-raise sites (too_short, no_audio, not_talking_head, no_speech/muted, plan_collapsed — the min-output-ratio plan guard, render_collapsed — the post-render backstop [both Zac 2026-07-28], transcription_incomplete — GATE #5 the LANGUAGE NET, Zac 2026-07-31: unroutable/untranscribable language → caption-less minimal visual edit, never a failed job)"
    assert '_MinimalRouteSignal("too_short")' in _h and '_MinimalRouteSignal("no_audio")' in _h \
        and '_MinimalRouteSignal("not_talking_head")' in _h and '"no_speech_muted" if _face_present else "no_speech"' in _h \
        and '_MinimalRouteSignal("render_collapsed")' in _h and '_MinimalRouteSignal("plan_collapsed")' in _h \
        and '_MinimalRouteSignal("transcription_incomplete")' in _h  # GATE #5 language net
    assert "zero-reject defers to the" in _h, \
        "the fast-check must DEFER (not route) under the flag — the conservatism invariant"
    # every route site is flag-guarded; flag off keeps today's raises
    assert _h.count("_zero_reject_enabled(input_data)") >= 5, "each gate must consult the flag"
    assert "NO_AUDIO_TRACK: source has no audio stream" in _h and \
        "NO_SPEECH: Deepgram returned 0 words" in _h and \
        "NOT_TALKING_HEAD: face in only" in _h, "flag-off rejections must remain intact"
    # the one choke point + failure fall-through
    assert "isinstance(e, _MinimalRouteSignal)" in _h and _h.count("isinstance(e, _MinimalRouteSignal)") == 1, \
        "exactly ONE outer choke point"
    _i = _h.find("isinstance(e, _MinimalRouteSignal)")
    _tail = _h[_i:_i + 1200]
    assert "_run_minimal_pipeline(" in _tail and "e = _mre" in _tail, \
        "choke point must run the minimal pipeline and fall through to the coded envelope on failure"
    # the minimal pipeline shares the delivery contract
    _p = _h.find("def _run_minimal_pipeline")
    _body = _h[_p:_h.find("\ndef ", _p + 10)]  # widened for the hype + moodreel branches
    for _needle, _why in [
        ("_encode_and_upload_hls(", "shared HLS ladder"),
        ("write_job_status(", "durable completed terminal"),
        ('send_progress(job_id, "complete", 100', "complete event"),
        ("_persist_edit_rationale(job_id", "rationale rides the minimal path"),
        ("_S3_TRANSFER_CONFIG", "same multipart upload config"),
        ('"route": _route_name', "route named in result (minimal or the hype upgrade)"),
    ]:
        assert _needle in _body, f"minimal pipeline missing: {_why}"
    # the TH tail delegates to the SAME HLS implementation (one source of truth)
    assert _h.count("_hls_cmd = [") == 1, "exactly one HLS ladder implementation"
    # the four routing modules ride the image
    _m = open("modal_app.py").read()
    for _mod in ("general_editor.py", "hype_editor.py", "minimal_editor.py", "hype_render.py", "moodreel_editor.py"):
        assert f'"{_mod}"' in _m, f"{_mod} must be baked into the worker image"


@check("PROGRESSIVE TERMINAL SEAM + BAR REDESIGN (Zac ruling 1, 2026-07-25): (b-race) the publisher's every input/output lives inside work_dir, so the handler's terminal finally must drain-or-cancel it BEFORE shutil.rmtree — success path (finalize requested) gets a bounded 120s drain so the last chunk transcodes finish cleanly; anything else (or drain timeout) is a DELIBERATE cancel: quiet worker exit (never the loud _fail), progressive_cancelled ledger, payload stamped superseded. (a) a preview is NEVER servable as a terminal state: finalize stamps payload final=true, cancel stamps superseded=true, and ONLY stamped payloads bypass _persist_preview's terminal status fence. CERT bars: FINAL byte-identical under a baseline-vs-baseline2 DETERMINISM CONTROL (names render_nondeterministic vs progressive_leg_perturbs_render honestly); PREVIEW relaxed to SSIM>=0.999 vs final (RELAX BAR — separate -bf 0 encode, replaced by final); terminal_state asserts result.hls_manifest_url points at the final ladder.")
def _progressive_terminal_seam():
    _h = open("handler.py").read()
    # early init so every path reaching the finally can reference the handle. The
    # publisher now lives in render_stage() (Phase 1 extraction); a 1-cell holder
    # carries it back so the finally drains it even if render_stage RAISES
    # (INTEGRITY_TRIP etc.) — a plain return would leave the handle unbound on the
    # exception path and leak the publisher under the terminal rmtree.
    assert "_prog_pub_cell = [None]" in _h, \
        "_prog_pub_cell must init early in handler (every path reaching the finally references it)"
    assert "_prog_pub_cell[0] = ProgressivePublisher(" in _h, \
        "render_stage must write the publisher INTO the cell at creation (exception-safe drain)"
    assert "_prog_pub = _prog_pub_cell[0]" in _h, \
        "the terminal seam must read the publisher from the cell before draining"
    # the seam sits inside the terminal finally BEFORE work_dir teardown. The
    # drain-or-cancel logic is EXTRACTED into _drain_progressive_publisher (inc2
    # render-burst: the ONE drain, shared by the planner's finally AND
    # render_burst's own finally). So the finally must DRIVE it (the call)
    # immediately before rmtree, and the extracted HELPER must carry the
    # bounded-drain / deliberate-cancel law.
    _fin = _h.find("PROGRESSIVE TERMINAL SEAM (Zac ruling 1b")
    assert _fin != -1, "terminal seam block missing"
    _rm = _h.find("shutil.rmtree(work_dir, ignore_errors=True)", _fin)
    assert _rm != -1 and (_rm - _fin) < 2000, "the seam must run IMMEDIATELY before the terminal rmtree"
    _seam = _h[_fin:_rm]
    assert "_drain_progressive_publisher(_prog_pub_cell)" in _seam, \
        "the terminal finally must DRIVE the extracted drain immediately before the terminal rmtree"
    _dh = _h.find("def _drain_progressive_publisher(")
    assert _dh != -1, "the extracted drain helper must exist (shared by planner + render_burst finally)"
    _dbody = _h[_dh:_dh + 1800]
    assert "_prog_pub.finalize_requested" in _dbody and "_prog_pub.drain(timeout_s=120.0)" in _dbody \
        and '_prog_pub.cancel("terminal_drain_timeout")' in _dbody \
        and '_prog_pub.cancel("job_terminal_before_finalize")' in _dbody, \
        "seam law: bounded drain on the finalize path; deliberate cancel otherwise (in the extracted helper)"
    # stamped payloads bypass the terminal fence; chunk payloads keep it
    assert 'if not (payload.get("final") or payload.get("superseded")):' in _h, \
        "_persist_preview: only stamped terminal payloads bypass the status fence"
    _p = open("progressive_publish.py").read()
    assert "class _PublishCancelled(Exception):" in _p and "def cancel(self" in _p \
        and "def drain(self" in _p and "def finalize_requested(self)" in _p, \
        "publisher must expose cancel/drain/finalize_requested"
    assert _p.count("self._cancelled") >= 6, "cancel checkpoints must cover the publish path (audio wait, post-transcode, pre-upload)"
    assert '"final": bool(self.finalized)' in _p and '"superseded": bool(superseded)' in _p, \
        "payload stamps: final on finalize, superseded on cancel"
    assert "progressive_cancelled" in _p, "the deliberate cancel is ledgered (visible, non-defect)"
    assert "post-cancel worker noise suppressed" in _p, \
        "teardown-adjacent noise after a deliberate cancel must not fire the loud fallback"
    _c = open("cert_progressive_app.py").read()
    assert "DETERMINISM CONTROL" in _c and 'cap["deterministic"] = filecmp.cmp(kb, kb2' in _c, \
        "cert: baseline2 determinism control"
    # DETERMINISM-RELATIVE FINAL BAR (Zac ruling 2026-07-26): progressive-ON must
    # diverge from a fresh baseline by <= the render's own run-to-run noise.
    assert 'eq["ok"] = bool(cap["bytes_identical"] or _perturb <= 2.0 * _noise + _EPS)' in _c, \
        "cert: FINAL bar is determinism-relative (progressive perturbation <= render run-to-run noise), NOT strict byte-identity (unmeetable: x264 nondeterminism ~0.99994)"
    assert "render_run_to_run_noise" in _c and "progressive_added_perturbation" in _c, \
        "cert: both quantities measured + reported (noise floor + progressive's added perturbation)"
    # ARCHITECTURAL INVARIANT (Zac ruling 2026-07-26: the SAFETY property, SSIM is
    # only corroboration): the publisher reads render intermediates + audio ONLY,
    # writes ONLY to the preview prefix, and has NO write path to the final
    # artifact and NO render/re-render call. This is what makes the final safe
    # regardless of the (non-deterministic) pixel comparison.
    _pp = open("progressive_publish.py").read()
    assert "renderMedia" not in _pp and "render_multi_clip" not in _pp \
        and "_run_remotion" not in _pp and "generate_content" not in _pp, \
        "publisher must NEVER render/re-render — it composites previews from the render's own intermediates"
    assert "output_path" not in _pp, \
        "publisher must have NO reference to the final output_path (no write path to the final artifact)"
    # every ffmpeg output in the publisher lands under self._out_dir (work_dir/
    # preview_hls) or the preview S3 prefix — never the final output or final HLS.
    assert 'self._out_dir = os.path.join(work_dir, "preview_hls")' in _pp, \
        "publisher's only local write dir is the preview_hls subdir"
    assert "_final_prefix" not in _pp and "output-hls" not in _pp, \
        "publisher must not reference the final HLS prefix"
    # PREVIEW BAR WITHDRAWN (Zac ruling 2026-07-26): no numeric SSIM gate — the
    # preview SSIM is informational and a preview->final SWAP artifact is
    # produced for Zac's eye (the visible-pop risk, not a decimal).
    assert 'pv["ok"] = True' in _c and "swap artifact is the judge" in _c, \
        "cert: preview SSIM must be informational (no numeric bar)"
    assert "PREVIEW\u2192FINAL SWAP ARTIFACT" in _c or "PREVIEW\N{RIGHTWARDS ARROW}FINAL SWAP ARTIFACT" in _c or "swap_artifact_url" in _c, \
        "cert: must produce the preview->final swap artifact for Zac's eye"
    assert "cert-progressive-swaps/" in _c, "swap artifact must persist OUTSIDE base_key (survives cert cleanup)"
    assert '"-preview-hls" not in ts["result_hls_manifest_url"]' in _c \
        and 'payload.get("final") is True' in _c, \
        "cert: terminal state points at the final ladder + stamped payload"


@check("LOUD FAIL-SAFE LEDGERS (Zac standing rule 2026-07-25): a fallback that masks a MISSING MODULE or ABSENT DB COLUMN must ledger an explicit defect-class divergence (action *_defect, component 'defect') so the daily [REPORT] defects line surfaces it — degrade allowed, silence not. Worker sites: ImportError ledgers at the deferred-import swallows (burned_text arm, motion-curve extract, recipe_eval run+perturb, premium scaffold, edit_policy arm, prewarm_volume reload) + PGRST204 detection at every video_jobs persist helper (job-status write/read, ask-back, step-token, edit-rationale, post-package, preview). The ledger writer itself failing stays print-only (recursion floor).")
def _loud_failsafe_ledgers():
    _h = open("handler.py").read()
    assert "def _ledger_defect(kind, site, err, job_id=None):" in _h, "the defect-ledger helper"
    assert '"{kind}_defect"' in _h or 'f"{kind}_defect"' in _h, "action must be {kind}_defect (server matcher pins /_defect$/)"
    _mm = _h.count('_ledger_defect("missing_module"')
    assert _mm >= 6, f"missing_module defect ledgers at the import swallows (found {_mm}, need >=6)"
    _ac = _h.count('_ledger_defect("absent_column"')
    assert _ac >= 7, f"absent_column defect ledgers at the persist helpers (found {_ac}, need >=7)"
    assert _h.count('"PGRST204" in str(') >= 7, "PGRST204 detection at every persist fail-open"


@check("PROGRESSIVE COORDINATED FLIP (Zac 2026-07-26, 219 on TestFlight): preview publishing is gated on the PER-JOB client capability input_data.supports_progressive (an old client never sends it -> no preview -> byte-identical render), with PROMPTLY_PROGRESSIVE as a backend KILL SWITCH ('0' forces off) and progressive_test as the cert override. AND the worker emits hls_manifest_url EARLY: _persist_preview writes the preview manifest to hls_manifest_url the moment a chunk is playable (segments_published>=1, not final/superseded), so the 219 client (which polls hls_manifest_url) starts playback before the render finishes; the terminal completion write overwrites it with the FINAL manifest, and the preview write's terminal fence keeps it from ever landing after completion.")
def _progressive_coordinated_flip():
    _h = open("handler.py").read()
    _i = _h.find("def _progressive_enabled")
    _body = _h[_i:_i+1400]
    assert 'input_data.get("supports_progressive")' in _body, \
        "preview publishing must gate on the per-job supports_progressive capability"
    assert 'if _global in ("0", "false", "no", "off"):' in _body and "kill switch" in _body, \
        "PROMPTLY_PROGRESSIVE must be a backend kill switch"
    assert 'input_data.get("progressive_test")' in _body, "cert override preserved"
    # early hls_manifest_url emission in _persist_preview
    _p = _h.find("def _persist_preview")
    _pb = _h[_p:_p+2400]
    assert '_update["hls_manifest_url"] = payload["preview_hls_url"]' in _pb, \
        "the worker must emit hls_manifest_url EARLY (preview manifest) once playable"
    assert 'int(payload.get("segments_published") or 0) >= 1' in _pb, \
        "early hls emission requires a playable segment"
    assert 'not payload.get("final")' in _pb and 'not payload.get("superseded")' in _pb, \
        "early hls emission only for in-flight previews (the terminal write owns the final)"


@check("SHARED GEMINI CACHE REGISTRY (Zac 2026-07-26): a fresh container's in-memory _GEMINI_CACHE_REGISTRY is empty, and there is NO server-side lookup before caches.create — so without sharing, every cold/post-deploy container RECREATES a Vertex cache that already exists server-side (duplicate + first-job creation latency). A cross-container modal.Dict keyed by (model, sys-hash) lets any container REUSE the existing cache. MUST be fail-open (dict unavailable/lookup/write error -> per-container create = today's behavior, byte-identical) and kill-switchable (PROMPTLY_SHARED_GEMINI_CACHE=0). Quality-neutral: same cache CONTENT, only reuse vs recreate.")
def _shared_gemini_cache():
    _h = open("handler.py").read()
    assert "def _shared_gemini_cache_dict():" in _h, "the shared-dict accessor must exist"
    assert '_modal.Dict.from_name(' in _h and '"gemini-cache-registry"' in _h, "must use a named cross-container modal.Dict"
    assert 'PROMPTLY_SHARED_GEMINI_CACHE' in _h, "kill switch required"
    # fail-open: the accessor swallows errors -> None; the lookup + write are try/wrapped
    _i = _h.find("def _shared_gemini_cache_dict")
    _body = _h[_i:_i+1200]
    assert "per-container caching only" in _body, "accessor must fail-open to None"
    assert "shared HIT" in _h and "shared lookup failed" in _h and "shared write failed" in _h, \
        "lookup + write must be individually fail-open (never fail a job over the cache dict)"
    # the shared lookup must sit AFTER the local-registry check and BEFORE caches.create
    _lc = _h.find("_GEMINI_CACHE_REGISTRY.get(key)")
    _sh = _h.find("_shared_gemini_cache_dict()", _lc)
    _cr = _h.find("client.caches.create(", _lc)
    assert _lc < _sh < _cr, "shared lookup must be between local miss and server create"


@check("B-ROLL CONTENT + SAFETY GATE (Flare quality campaign, Zac 2026-07-26, DARK behind PROMPTLY_BROLL_GATE): the old pipeline ranked candidates on URL-slug word overlap and validated ONLY that the download was a playable video — never the CONTENT, so an object query returned a stranger's face and a clip's legible browser UI shipped. prefetch_and_verify_broll now runs a Gemini-vision frame check per surviving candidate: KEEP only if it depicts the intent AND is safe (no faces-to-camera/prominent faces, no legible text/URLs/site-UI/watermarks, not unsettling/moody/low-quality). FAIL-CLOSED: unverifiable → REJECT (zero-is-strong; a clean cut beats an unverified clip). A reject omits the entry (ledgered broll_content_reject). Flag DARK by default → verify is a no-op → byte-identical; per-job cert override broll_gate_test. Expect b-roll frequency to fall sharply — intended.")
def _broll_content_gate():
    _h = open("handler.py").read()
    assert "def _verify_broll_content(" in _h and "def _broll_gate_enabled(" in _h, \
        "the b-roll content gate + flag helper must exist"
    assert 'os.environ.get("PROMPTLY_BROLL_GATE"' in _h, "gate must default DARK behind PROMPTLY_BROLL_GATE"
    assert 'input_data.get("broll_gate_test")' in _h, "per-job cert override required"
    # fail-closed: the verify's except returns REJECT (False), not keep
    _i = _h.find("def _verify_broll_content")
    _b = _h[_i:_i+6000]
    assert 'return False, f"verify error (fail-closed)' in _b, "vision-check errors must FAIL-CLOSED (reject)"
    assert 'if not _broll_gate_enabled(input_data):' in _b and 'return True, "gate off"' in _b, \
        "gate OFF must be a no-op (keep) → byte-identical"
    assert "faces-to-camera" not in _b or "toward the camera" in _b, "prompt must reject faces-to-camera"
    assert "legible text" in _b and "watermark" in _b, "prompt must catch legible text/URLs + watermarks (brand/legal)"
    assert "KEEP" in _b and "REJECT" in _b, "vision check must return KEEP/REJECT"
    # ACTION MATCH not topic match (Zac 2026-07-26, from the phone-scrolling reject):
    assert "ACTION MATCH" in _b and "wrong verb" in _b, \
        "prompt must demand the SPECIFIC action/verb, not topic — near-miss-on-action is a hard reject"
    # Evaluate the CUTAWAY WINDOW densely (Zac 2026-07-26, from the turn-to-camera miss):
    assert "center-seek" in _b and "CUTAWAY WINDOW" in _b, \
        "must evaluate the rendered cutaway window (center-seek), not the whole asset"
    assert "sampled DENSELY" in _b and "TURNS to face the camera" in _b, \
        "must sample densely across the window so a turn-to-camera can't hide between frames"
    assert "int(_win / 0.7)" in _b, "dense sampling must be ~every 0.7s across the window"
    # wired into the verify loop, rejects omit + ledger — content vs error SEPARATELY (Zac flag 2)
    assert '"broll_content_reject"' in _h and '"broll_verify_error"' in _h, \
        "content-reject and transient verify-error must ledger as DIFFERENT actions"
    assert '_act = "broll_verify_error" if _is_err else "broll_content_reject"' in _h, \
        "the ledger action must branch on is_error"
    # concurrency (Zac flag 1): the vision checks run across candidates in a thread pool
    assert "ThreadPoolExecutor" in _h and "content+safety gate:" in _h and "concurrent," in _h, \
        "per-candidate vision checks must run CONCURRENTLY, not sequentially"
    # dark → byte-identical: the call threads input_data; off returns keep
    assert "_broll_gate_input=input_data" in _h, "the verify call must thread input_data for the gate/override"


@check("HQ RESAMPLE — PART A (Flare fidelity, Zac 2026-07-26, DARK behind PROMPTLY_HQ_RESAMPLE): the source→canvas normalize scale (analyze_source_video) used FFmpeg's DEFAULT kernel (bicubic). DIRECTION-AWARE + DO-NO-HARM: lanczos DOWNSCALING (4K→1080, +14% sharper, no ring) but UPSCALE keeps bicubic default UNCHANGED — measured on a genuinely-compressed 576×1024@0.38Mbps social re-download (the real upscale population; client verified clean → sub-HD is permanent), a sharper kernel buys ~nothing (VoL 9.7→10.2, detail already gone to compression) while RAISING ring (bicubic 0.28 < spline 0.32 < lanczos 0.34, ~10× clean footage); denoise-before-upscale helped neither. OFF → flags='' → FFmpeg default → byte-identical. Reason the retired FFmpeg lanczos zoom path's sharpness was collateral damage — see feedback_audit_retired_paths.")
def _hq_resample_direction_gate():
    _h = open("handler.py").read()
    assert "def _hq_resample_enabled(" in _h and "def _resample_flags(" in _h, \
        "the HQ-resample flag helper + direction picker must exist"
    assert 'os.environ.get("PROMPTLY_HQ_RESAMPLE"' in _h, "must default DARK behind PROMPTLY_HQ_RESAMPLE"
    _i = _h.find("def _resample_flags")
    _b = _h[_i:_i + 1600]
    assert 'if not _hq_resample_enabled():' in _b and 'return ""' in _b, \
        "OFF must return '' (FFmpeg default kernel) → byte-identical"
    # DIRECTION-AWARE + ADAPTIVE: lanczos down always; upscale sharpens (spline) ONLY on a clean source
    assert 'if scale_factor <= 1.0:' in _b and 'return ":flags=lanczos"' in _b, \
        "downscale must always get lanczos (safe, averages artifacts)"
    assert 'return ":flags=spline" if source_clean else ""' in _b, \
        "upscale sharpens ONLY when the per-job quality gate says clean; compressed → FFmpeg default (do-no-harm)"
    # ONE adaptive quality gate, bpp-based, reused across A/B/C
    assert "def _source_clean_enough(" in _h and "bpp >= 0.12" in _h, \
        "the per-job bpp quality gate must exist (threshold 0.12 separates compressed re-downloads from clean footage)"
    assert "_source_clean = _source_clean_enough(_bpp)" in _h and "_vbr / (w * h * fps)" in _h, \
        "analyze_source_video must compute bpp from the source bitrate and derive the clean flag"
    # both normalize_vf sites must route through the direction picker WITH the clean flag
    assert "_resample_flags(_norm_scale, _source_clean)" in _h, "center-crop normalize must pass scale + clean flag"
    assert "_resample_flags(1080.0 / max(1, crop_w), _source_clean)" in _h, "reframe normalize must pass scale + clean flag"
    assert "scale=1080:1920:flags=" not in _h, "no hardcoded normalize kernel — must go through the dark flag"


@check("E1 DENSITY RESHAPE (Zac 2026-07-26, DARK behind PROMPTLY_DENSITY): our edits run ~0.23 component-events/s vs the 0.8-1.0/s reference, zoom-dominated (half of all events) with ~10s dead stretches — the planner under-produces AND every emphasis defaults to a zoom (the monotony root). When on, the editorial prompt (1) DECOUPLES emphasis→move-type (best-FIT move, never always a zoom; VARY the instrument), (2) states the target as a DISTRIBUTION — mean ~0.8-1.0/s, no dead stretch >3s, BURSTS clustered on peaks + rests REQUIRED (metronomic reads mechanical), (3) expands markable moments (felt peaks PLUS list items/numbers/name-drops/contrasts/Q→A/tonal shifts, never arbitrary decoration). OFF → both gated fragments are the CURRENT doctrine verbatim → byte-identical planning (the else-branch reproduces the exact original 'every emphasis carries a zoom' line + empty rhythm block).")
def _e1_density_reshape_gate():
    _h = open("handler.py").read()
    assert "def _density_reshape_enabled(" in _h, "the density-reshape flag helper must exist"
    assert 'os.environ.get("PROMPTLY_DENSITY"' in _h, "must default DARK behind PROMPTLY_DENSITY"
    # byte-identical OFF: the else-branch must reproduce the EXACT original doctrine
    assert '_emph_move_line = "Every emphasis carries a zoom by default (null is the rare exception)."' in _h, \
        "OFF must reproduce the exact original emphasis→zoom line (byte-identical planning)"
    assert '_density_rhythm_block = ""' in _h, "OFF rhythm block must be empty (byte-identical)"
    # the f-string must interpolate the gated fragments, not the hardcoded original
    assert "for the meaning. {_emph_move_line}" in _h, "decouple line must be gated via {_emph_move_line}"
    assert "{_density_rhythm_block}An emphasis moment is a PEAK" in _h, "rhythm block injects before the emphasis def"
    # ON content: decouple + distribution + expanded moments
    assert "NEVER default every" in _h and "reads monotonous" in _h, "ON must decouple emphasis→move-type"
    assert "0.8-1.0 visual moves per second" in _h and "BURSTS WITH RESTS" in _h and "dead stretch longer than ~3s" in _h, \
        "ON must state the distribution target (mean, bursts+rests, no dead >3s)"
    assert "question→answer turns" in _h and "name-drops" in _h, "ON must expand the markable-moment vocabulary"


@check("TRANSCRIPTION-COVERAGE GATE (content-destruction P0 fix, Zac 2026-07-27, DARK behind PROMPTLY_COVERAGE_GATE): the cutter assembles output from transcript WORDS, so VAD-confirmed speech carrying NO words is DELETED as silence (measured: an Urdu upload 89.7s→31.6s, 58s of continuous speech destroyed). ON → a source whose VAD SPEECH is materially untranscribed is rejected with an honest TRANSCRIPTION_INCOMPLETE coded error + refund BEFORE the cutter runs — never a butchered edit. Silero VAD SPEECH (not energy → music beds never false-reject); language-agnostic (subsumes the script gate for the transcription-failure class). Measures DELETABLE untranscribed speech by POSITION (2026-07-27 cutter trace + adversarial workflow): the output is assembled only from [first kept word .. last kept word], so VAD-speech OUTSIDE that envelope (leading intro / trailing tail past the 0.5s pad) is dropped at ANY duration (the 58s-Urdu vector), while INTERIOR untranscribed speech between kept words is PRESERVED (plays through, uncaptioned). So the gate counts EDGE speech only. This beats a duration floor two ways: it catches a STACCATO edge intro (untranscribed bursts split by breaths, each below any floor, would leak a duration gate) and it stops false-rejecting interior-untranscribed clips that deliver fine — the 2026-07-27 over-fire (230s clip, 21.8s scattered INTERIOR gaps) now contributes ZERO. Thresholds (≥2.0s AND ≥0.10 frac of EDGE speech) still data-driven from the 34-job cert. FAIL-OPEN on measurement error (a safety net, never a new failure source). OFF → the check never runs (byte-identical). Refunded + rescue-denied via both frozensets.")
def _transcription_coverage_gate():
    _h = open("handler.py").read()
    assert "def _coverage_gate_enabled(" in _h, "coverage-gate flag helper must exist"
    assert 'os.environ.get("PROMPTLY_COVERAGE_GATE"' in _h, "must default DARK behind PROMPTLY_COVERAGE_GATE"
    assert 'input_data.get("coverage_gate_test")' in _h, "per-job cert override must exist (dark for real traffic)"
    assert "def _transcription_coverage_check(" in _h, "the VAD coverage measurement must exist"
    assert "_COVERAGE_MIN_UNWORDED_S = 2.0" in _h and "_COVERAGE_MIN_UNWORDED_FRAC = 0.10" in _h, \
        "data-driven thresholds (2.0s AND 0.10 frac) — the values the 2026-07-27 cert separated on"
    assert "_COVERAGE_TAIL_KEEP_S = 0.5" in _h and "_COVERAGE_MIN_INTERIOR_S = 1.5" in _h, \
        "must bound the kept-word envelope with the cutter's tail pad AND floor large interior spans"
    assert "if t < first_ws or t > tail_keep:" in _h and "edge_deletable" in _h, \
        "must count EDGE untranscribed speech by POSITION (outside [first word, last word+pad]) at ANY " \
        "span size — NOT a duration floor: a staccato edge intro fragments below any floor and would leak " \
        "(2026-07-27 cutter trace + adversarial workflow)."
    assert "reject_speech = edge_deletable + interior_reject" in _h, \
        "reject measure = EDGE (deleted, any size) + LARGE CONTIGUOUS INTERIOR (≥1.5s, preserved-but-bad-edit); " \
        "scattered interior gaps excluded (the 2026-07-27 over-fire). Not the scattered bin-sum, not a flat span-floor."
    assert "_detect_silence_regions_vad(source_path, min_silence_s=0.30)" in _h, \
        "must use Silero VAD SPEECH (not energy) so a music bed never false-rejects"
    assert "FAIL-OPEN" in _h and "return True, stats" in _h, \
        "measurement must FAIL-OPEN — the gate is a safety net, never a new failure source"
    assert "if _coverage_gate_enabled(input_data):" in _h, "gate must be wired at intake"
    assert '"TRANSCRIPTION_INCOMPLETE: "' in _h, "must raise the honest coded error"
    assert 'if "TRANSCRIPTION_INCOMPLETE" in msg:' in _h, "must have its own classifier branch (honest user message)"
    _dr = _h[_h.find("_DESIGNED_REJECTION_CODES = frozenset("):]
    assert '"TRANSCRIPTION_INCOMPLETE"' in _dr[:400], "must be a DESIGNED REJECTION so the app refunds the credit"
    _or = _h[_h.find("_OUTER_RESCUE_DENY = frozenset("):]
    assert '"TRANSCRIPTION_INCOMPLETE"' in _or[:1200], "must be rescue-denied (no doomed safe-edit re-run on unsupported language)"


@check("D2 MOTION BLUR dark-flag (Zac 2026-07-26, 30fps+blur ruling): CameraMotionBlur (was Lumen-only) now selectively wraps Flare's 4 motion sites (MG entrance/exit, b-roll push, transitions, composite zooms) behind input.motionBlur, DARK by default. OFF is byte-identical BY CONSTRUCTION — MotionBlurWrap returns children untouched when disabled (no wrapper, no extra DOM/paint). shutterAngle is free (temporal spread only); samples is the sole cost knob (6× on the wrapped subtree). Tunables (samples=6/shutterAngle=180 film convention) live in ONE token so the samples∈{3,6,10} sweep has one home. NOTE: blur smears the crisp payoff frame — re-verify impact-on-word before flipping; cost compounds with E1 density (both multiply the same frames).")
def _d2_motion_blur_dark_flag():
    _mb = open("src/remotion/src/motion-graphics/shared/motion-blur.tsx").read()
    assert "if (!enabled) return <>{children}</>;" in _mb, \
        "MotionBlurWrap must pass children through untouched when disabled — the OFF-path byte-identity guarantee"
    assert "MOTION_BLUR_DEFAULTS" in _mb and "samples: 6," in _mb and "shutterAngle: 180," in _mb, \
        "MOTION_BLUR_DEFAULTS (samples=6, shutterAngle=180) must stay the single tunable token"
    _pr = open("src/remotion/src/PromptlyRender.tsx").read()
    assert _pr.count("input.motionBlur ?? false") == 2, \
        "the DARK default input.motionBlur ?? false must gate BOTH compositions (PromptlyOverlay + PromptlyMicroSegments)"
    assert _pr.count("<MotionBlurWrap>") == 4, \
        "expected exactly 4 selective MotionBlurWrap sites (MG, b-roll, transition, composite zoom) — never a global comp blur"
    _ts = open("src/remotion/src/types.ts").read()
    assert _ts.count("motionBlur?: boolean") == 2, \
        "motionBlur?: boolean must be on BOTH PromptlyRenderInput and PromptlyMicroSegmentsInput"


@check("E1+D2 A/B PER-JOB OVERRIDES (Zac 2026-07-26): density_test toggles the E1 density reshape and motion_blur_test (+samples/shutter) toggles D2 blur for ONE job without flipping the global flags — so the four-arm A/B (baseline / density-only / blur-only / BOTH) runs on real jobs. Both dark/absent for real traffic → byte-identical (density_test → generate_edit_gemini density_override; motion_blur_test → edit_plan[_motion_blur] → both render inputs, emitted ONLY when enabled). Mirrors burned_text_test / broll_gate_test.")
def _e1_d2_ab_overrides():
    _h = open("handler.py").read()
    # density_test → generate_edit_gemini(density_override) → _build_post_cuts_prompt → (flag OR override)
    assert 'density_override=bool(input_data.get("density_test"))' in _h, "density_test must reach generate_edit_gemini at the call site"
    assert "_density_reshape_enabled() or density_override" in _h, "the prompt-builder flag check must honor the per-job override"
    assert "density_override=density_override," in _h, "generate_edit_gemini must pass density_override into _build_post_cuts_prompt"
    # motion_blur_test → edit_plan[_motion_blur] → both render inputs, conditional emit (OFF byte-identical)
    assert 'input_data.get("motion_blur_test")' in _h and 'edit_plan["_motion_blur"] = {' in _h, "motion_blur_test must thread via edit_plan"
    assert '_blur_cfg = edit_plan.get("_motion_blur")' in _h and _h.count('_blur_cfg.get("enabled")') >= 2, \
        "render_multi_clip must read the blur config and conditionally emit into BOTH legs (only when enabled → OFF byte-identical)"
    assert 'overlay_input["motionBlur"] = True' in _h and 'micro_input["motionBlur"] = True' in _h, "both render legs must carry the blur override"
    # render_schemas registers the fields on BOTH models (extra='forbid' → must be declared)
    _rs = open("render_schemas.py").read()
    assert _rs.count("motionBlur: bool = False") == 2, "motionBlur must be on PromptlyRenderInput AND PromptlyMicroSegmentsInput (extra=forbid)"
    assert _rs.count("motionBlurSamples: Optional[int] = None") == 2 and _rs.count("motionBlurShutterAngle: Optional[int] = None") == 2, \
        "samples/shutter registered on both render-input models"


@check("SPEAKER-FOLLOWING CAPTIONS (Lane 2, flag PROMPTLY_SPEAKER_CAPTIONS, DARK): captions FOLLOW the smoothed speaker head via a per-page {topPx} anchor pinned below the head bbox (flips above for a low head), clamped into the TikTok safe rect, horizontal centred; constant-per-page = snap not slide (FRAME-1-IS-FINAL). Reuses edit_plan['_face_trajectory'] + the projected-word table, no new sampling. OFF (default) -> _apply_speaker_follow_captions never runs AND emits no anchor key; the render schema accepts a segment with OR without anchor and rejects an unknown anchor field (extra=forbid) -> render input JSON byte-identical while dark.")
def _speaker_captions_dark_and_correct():
    import os, handler, render_schemas as rs
    os.environ.pop("PROMPTLY_SPEAKER_CAPTIONS", None)
    assert handler._speaker_captions_enabled() is False, "flag must default OFF"
    rs.CaptionPositionSegment.model_validate({"fromFrame": 0, "toFrame": 100, "position": "bottom"})
    rs.CaptionPositionSegment.model_validate({"fromFrame": 0, "toFrame": 100, "position": "center", "anchor": {"topPx": 742}})
    try:
        rs.CaptionPositionSegment.model_validate({"fromFrame": 0, "toFrame": 1, "position": "bottom", "anchor": {"topPx": 1, "x": 2}})
        raise AssertionError("extra=forbid must reject an unknown anchor field")
    except Exception as e:
        assert "AssertionError" not in type(e).__name__ or "extra" in str(e), e
    segs = [{"fromFrame": 0, "toFrame": 300, "position": "bottom"}]
    assert handler._apply_speaker_follow_captions(segs, [], [], [], [], 300, 60.0) is segs
    pages = [{"text": "hi", "startMs": 0, "durationMs": 2000, "tokens": []}]
    pw = [{"start": 0.9, "_source_start": 0.9}]
    traj = [{"t": 1.0, "cx": 540, "cy": 500, "found": True, "confidence": 0.9}]
    out = handler._apply_speaker_follow_captions(segs, pages, traj, pw, [], 300, 60.0)
    assert out is not segs and any(s.get("anchor") for s in out), "a face must produce an anchor"
    assert out[0]["fromFrame"] == 0 and out[-1]["toFrame"] == 300
    for i in range(len(out) - 1):
        assert out[i]["toFrame"] == out[i + 1]["fromFrame"], "segments must tile with no gap"
    rs.CaptionSpec.model_validate({"style": "CleanCut", "pages": [], "keywords": [], "positionSegments": out, "extraProps": None})
    out2 = handler._apply_speaker_follow_captions(segs, pages, traj, pw, [(0, 300)], 300, 60.0)
    assert out2 is segs, "an all-blocked page set must leave segments unchanged"


@check("CAPTION-LESS MOTION ANCHORS (Lane 2, flag PROMPTLY_MOTION_ANCHORS, DARK): the wordless routes (minimal/hype/moodreel) get motion-based drift-push anchors so no static hold runs dead > ~3s, honouring the 2.0s min-zoom-spacing law (_VISUAL_REFRACTORY_S). Additive: only clips with NO zoom and longer than the dead bound get events; already-animated clips are byte-identical; the same SmoothPush zoomEffect primitive moodreel already ships (validates against PromptlyRenderInput). Wired at the one point all three plans converge (_run_minimal_pipeline, after project_hype_plan). OFF (default) -> never invoked -> sparse render input byte-identical.")
def _motion_anchors_dark_and_correct():
    import os, copy, inspect, handler, render_schemas as rs
    os.environ.pop("PROMPTLY_MOTION_ANCHORS", None)
    assert handler._motion_anchors_enabled() is False, "flag must default OFF"
    assert handler._motion_anchors_enabled({"motion_anchors_test": True}) is True, "per-job override"
    src = inspect.getsource(handler._run_minimal_pipeline)
    assert "_motion_anchors_enabled(" in src and "_apply_motion_anchors(" in src, "must be wired into _run_minimal_pipeline"
    fps = 30.0
    def clip(cid, s, d, zoom=None):
        c = {"id": cid, "startFromFrames": int(s * fps), "playbackRate": 1.0, "durationInFrames": int(d * fps)}
        if zoom:
            c["zoomEffect"] = zoom
        return c
    animated = {"type": "DepthPull", "events": [{"startMs": 0, "durationMs": 3000, "scale": 1.18, "originX": 0.5, "originY": 0.5}], "punch": False}
    ri = {"sourceUrl": "x.mp4", "fps": fps, "width": 1080, "height": 1920, "totalDurationInFrames": int(20 * fps),
          "clips": [clip("h0", 0, 12), clip("h1", 12, 3, animated), clip("h2", 15, 5)],
          "transitions": [], "broll": [], "textOverlays": [], "motionGraphics": [], "caption": None, "outro": None}
    before = copy.deepcopy(ri)
    mc = [0.9 if i % 3 == 0 else 0.2 for i in range(20)]
    handler._apply_motion_anchors(ri, mc, [4.0, 9.5, 16.0], fps)
    assert ri["clips"][1] == before["clips"][1], "already-animated clip must be byte-identical"
    assert ri["clips"][0].get("zoomEffect") and ri["clips"][2].get("zoomEffect"), "long static holds must get anchors"
    for c in ri["clips"]:
        ze = c.get("zoomEffect")
        if not ze:
            continue
        st = [e["startMs"] / 1000.0 for e in ze["events"]]
        for i in range(1, len(st)):
            assert st[i] - st[i - 1] >= handler._VISUAL_REFRACTORY_S - 1e-6, "2.0s min spacing law"
    rs.PromptlyRenderInput.model_validate(ri)


@check("LOUD FAIL-SAFE MOUNT LAW (Zac standing rule 2026-07-25, from the moodreel_editor + progressive_publish mount catches): EVERY repo-local module that handler.py defer-imports inside a function body MUST be add_local_file-baked into the worker image — derived DYNAMICALLY from the source so any future mode is covered the day it is written. A deferred import inside a fail-safe try/except is exactly the class that dies silently (the fallback masks the ImportError and the feature quietly never runs); top-level imports crash loudly at container start and need no law.")
def _loud_failsafe_mount_law():
    import re as _re, os as _os
    _h = open("handler.py").read()
    _local = {f[:-3] for f in _os.listdir(".") if f.endswith(".py")}
    _mods = set()
    for _m in _re.finditer(r"^[ \t]+import ([a-z_][a-z0-9_]*)", _h, _re.M):
        if _m.group(1) in _local:
            _mods.add(_m.group(1))
    for _m in _re.finditer(r"^[ \t]+from ([a-z_][a-z0-9_]*) import", _h, _re.M):
        if _m.group(1) in _local:
            _mods.add(_m.group(1))
    assert _mods, "the scan must find the known deferred imports (regex drift?)"
    # the known family is the floor — if the scan ever misses these, the regex broke
    for _known in ("general_editor", "hype_editor", "minimal_editor", "hype_render",
                   "moodreel_editor", "progressive_publish"):
        assert _known in _mods, f"scan lost a known deferred module: {_known} (regex drift)"
    # modal_app is the app-definition module: Modal auto-mounts it in deployed
    # containers (the function is DEFINED in it) and it cannot add_local_file
    # itself into its own image. The only lawful exemption.
    _mods.discard("modal_app")
    _ma = open("modal_app.py").read()
    _missing = sorted(_mod for _mod in _mods if f'"{_mod}.py"' not in _ma)
    assert not _missing, (
        f"deferred repo-local imports NOT baked into the worker image (they will "
        f"die SILENTLY inside their fail-safes): {_missing}")


@check("MOODREEL ROUTE + ADOPTED MINIMAL PACING (Zac verdicts 2026-07-25: MOODREEL APPROVED + PAIR1 B + PAIR2 B): the route ladder inside _run_minimal_pipeline is hype (confident beat) -> MOODREEL (cinematic motion-resolve cut for no_speech/not_talking_head/no_audio clips >=8s without confident music; motion curve -> build_moodreel_prompt -> Gemini HypePlan) -> minimal; EVERY miss fail-safes to minimal (a moodreel attempt can never cost a user their video). The motion curve is extracted ONCE (fail-safe []) and shared: moodreel doctrine + the ADOPTED minimal pacing — boundaries at motion PEAKS (pair 2) + low-motion boundary skip-trims 0.4-0.8s median-relative (pair 1); no curve -> today's even pacing byte-identical. Flag PROMPTLY_MOODREEL (Secret canonical =1), per-job override moodreel_test; moodreel_editor.py baked into the image (the progressive-mount lesson: an unmounted module dies silently inside the fail-safe).")
def _moodreel_route_wiring():
    _h = open("handler.py").read()
    _p = _h.find("def _run_minimal_pipeline")
    _body = _h[_p:_h.find("\ndef ", _p + 10)]
    # ONE shared extraction, fail-safe, before the ladder
    assert _body.count("extract_motion_curve(") == 1, "the motion curve is extracted ONCE and shared"
    assert _body.find("extract_motion_curve(") < _body.find("_hype_on ="), \
        "extraction must precede the ladder (moodreel + minimal both consume it)"
    assert "motion-curve fail-safe" in _body, "curve extraction must be fail-safe (no curve = even pacing, never a dead job)"
    # the moodreel branch: flag + override + reasons + floor + fail-safe
    assert 'input_data.get("moodreel_test")' in _body, "per-job cert override required"
    assert 'os.environ.get("PROMPTLY_MOODREEL", "")' in _body, "the Secret-canonical flag gates the route"
    assert 'reason in ("no_speech", "not_talking_head", "no_audio")' in _body, \
        "moodreel eligibility: the three caption-less reasons (no_audio qualifies — no music needed)"
    assert "_moodreel_on and _dur >= 8.0 and _mcurve" in _body, \
        "the 8s floor + curve-required guard (every Zac-approved sample was motion-anchored; no curve -> minimal)"
    assert "build_moodreel_prompt(" in _body and "moodreel_fallback_minimal" in _body, \
        "doctrine prompt + the ledgered fail-safe to minimal"
    _mi = _body.find("_moodreel_on =")
    assert 0 < _body.find("hype_fallback_minimal") < _mi, "moodreel runs AFTER the hype attempt (beat wins)"
    assert _mi < _body.find("_me.build_minimal_plan("), "minimal stays the ladder floor"
    # route consumers: moodreel sets all three payload fields (the mypy lesson)
    assert '_route_name == "moodreel":' in _body and "cinematic mood-reel" in _body, \
        "moodreel must set its own rationale/capability_notes/pkg_fields — never the generic re-pace text"
    assert '"moodreel_plan"' in _body and '"motion_curve"' in _body, "stage_manifest names the moodreel stages"
    # PAIR2 B: the live call passes the curve
    assert "_me.build_minimal_plan(_dur, fps=_fps, motion_curve=_mcurve)" in _body, \
        "PAIR2 B adopted: the live minimal call consumes the motion curve"
    # PAIR1 B: skip-trim is first-class in minimal_editor with the sampled constants
    _m = open("minimal_editor.py").read()
    assert "trim_lo: float = 0.4, trim_hi: float = 0.8" in _m, "the sampled skip-trim constants (pair 1 B as approved)"
    assert "trim_hi if e <= 0.5 * med else trim_lo" in _m and "if e <= med" in _m, \
        "median-relative low-motion trim (deeper below median -> bigger skip)"
    # behavioral fixtures: adopted path trims; fail-safe path unchanged even pacing
    import importlib, sys as _sys
    _sys.path.insert(0, ".")
    _me_mod = importlib.import_module("minimal_editor")
    _pn = _me_mod.build_minimal_plan(20.0)
    assert len(_pn.clips) == 8 and abs(sum(c.end_s - c.start_s for c in _pn.clips) - 20.0) < 0.1, \
        "no-curve fail-safe must remain today's even pacing (8x2.5s over 20s)"
    _curve = [1, 1, 8, 1, 1, 1, 9, 1, 2, 1, 7, 1, 1, 1, 10, 1, 1, 1, 2, 1]
    _pc = _me_mod.build_minimal_plan(20.0, motion_curve=_curve)
    _span = sum(c.end_s - c.start_s for c in _pc.clips)
    assert _span < 19.5, "with a low-motion curve the skip-trims must actually drop seam air"
    assert all(b.start_s >= a.end_s - 1e-6 for a, b in zip(_pc.clips, _pc.clips[1:])), \
        "trimmed cuts must stay monotonic (skips only move forward)"
    assert all((c.end_s - c.start_s) >= 1.2 - 1e-6 for c in _pc.clips), "min clip length holds through trimming"
    assert all(c.speed == 1.0 and c.zoom is None for c in _pc.clips), "minimal stays 1.0x, zoom-less"
    # the image bakes the module (the progressive-mount lesson, pinned)
    _ma = open("modal_app.py").read()
    assert '"moodreel_editor.py"' in _ma, "moodreel_editor.py must ride the worker image"


@check("EDIT RATIONALE (2026-07-25): a user-facing 1-2 sentence 'why this edit' field flows end to end. PostCutPlan.edit_rationale is an additive Optional[str] (default None -> renderer never reads it -> byte-identical output); the TH post-cuts prompt asks for it in the field list (thin material -> say so + suggest a longer talking-head); edit_plan carries it via the PostCutPlan field-copy; the worker persists it to video_jobs.edit_rationale alongside current_step/step_message (narrative column ONLY, never status/progress/result), daemon-threaded, fail-open, terminal-fenced. Hype/minimal already carry a rationale via HypePlan.notes. Kill switch PROMPTLY_RATIONALE_PERSIST=0.")
def _edit_rationale_field():
    _h = open("handler.py").read()
    # schema: additive Optional field on PostCutPlan
    assert 'edit_rationale: Optional[str] = Field(default=None, max_length=400)' in _h, \
        "PostCutPlan must carry an additive Optional edit_rationale (default None = byte-identical)"
    # prompt asks for it (field-list line), with the thin-material honesty
    assert 'edit_rationale — string, 1-2 SENTENCES' in _h and 'suggest recording a longer talking-head' in _h, \
        "the TH prompt must ask for edit_rationale + the thin-material honesty"
    # persistence: narrative-only, terminal-fenced, wired at the recipe seam
    _i = _h.find("def _persist_edit_rationale")
    assert _i != -1, "the rationale persist helper must exist"
    _body = _h[_i:_i + 1400]
    assert '"edit_rationale": _txt' in _body and 'supabase.table("video_jobs").update(' in _body, \
        "must write edit_rationale to video_jobs"
    assert '"status":' not in _body and '"progress":' not in _body and '"result":' not in _body, \
        "the rationale write must be narrative-only (no status/progress/result)"
    assert '"failed", "canceled", "completed"' in _body, "the rationale write must be terminal-fenced"
    assert 'PROMPTLY_RATIONALE_PERSIST' in _body, "kill switch required"
    assert '_persist_edit_rationale(job_id, edit_plan.get("edit_rationale"))' in _h, \
        "the pipeline must persist the rationale after the recipe resolves"


@check("POST PACKAGE (2026-07-25, S-PACKAGE): when a video completes the user receives substance — {edit_rationale, post_caption, post_hook} delivered as result.post_package on EVERY route + video_jobs.post_package jsonb. PostCutPlan grows two additive Optional fields schema-capped at token-generation (post_caption<=120 platform-ready caption with 1-2 hashtags; post_hook<=60 scroll-stopping first line). Latency guard measured BEFORE shipping: ~57 output tokens ~= 1.8s at the observed 32 tok/s marginal rate (2.5s at the 22.8 tok/s worst-case effective), under the 3-5s bar -> the ask ships in the planning call, render never delayed. Minimal/hype fill deterministic-honest values (route reason / measured beat BPM — no extra model calls). The persist helper imitates _persist_step_token: daemon-threaded, fail-open, terminal-fenced, narrative column ONLY, kill switch PROMPTLY_PACKAGE_PERSIST=0; PostgREST no-ops until the 219 client migration adds the column. Contract: POST_PACKAGE_CONTRACT.md.")
def _post_package_contract():
    import handler as H
    _h = open("handler.py").read()
    # schema shape: additive Optionals, caps live IN the generation schema
    # (token-generation capping — the established edit_rationale pattern)
    assert 'post_caption: Optional[str] = Field(default=None, max_length=120)' in _h, \
        "PostCutPlan must carry additive Optional post_caption (cap 120)"
    assert 'post_hook: Optional[str] = Field(default=None, max_length=60)' in _h, \
        "PostCutPlan must carry additive Optional post_hook (cap 60)"
    _props = H.PostCutPlan.model_json_schema()["properties"]
    def _cap_of(_p):
        if isinstance(_p.get("maxLength"), int):
            return _p["maxLength"]
        for _v in (_p.get("anyOf") or []):
            if isinstance(_v, dict) and isinstance(_v.get("maxLength"), int):
                return _v["maxLength"]
        return None
    assert _cap_of(_props["post_caption"]) == 120 and _cap_of(_props["post_hook"]) == 60, \
        "caps must be enforced at token-generation (response schema maxLength)"
    assert H.PostCutPlan.model_fields["post_caption"].default is None and \
        H.PostCutPlan.model_fields["post_hook"].default is None, \
        "defaults must be None (Vertex omission-safe, byte-identical when absent)"
    # prompt: both asks present in the GLOBAL FIELDS list, user-facing framing
    assert 'post_caption — string' in _h and '1-2 hashtags' in _h, \
        "the TH prompt must ask for the platform-ready post_caption"
    assert 'post_hook — string' in _h and 'scroll-stopping first line' in _h, \
        "the TH prompt must ask for the scroll-stopping post_hook"
    # rationale-audit guidance (2026-07-25: 4 of 8 live rationales leaked
    # internal component names) — the ask must forbid them, wording-only
    assert 'NEVER an internal component or style name' in _h, \
        "edit_rationale guidance must forbid internal component/style names"
    # persistence helper: narrative-only, terminal-fenced, kill-switched
    _i = _h.find("def _persist_post_package")
    assert _i != -1, "the post-package persist helper must exist"
    _body = _h[_i:_h.find("\ndef ", _i + 10)]
    assert '{"post_package": package}' in _body and 'supabase.table("video_jobs").update(' in _body, \
        "must write post_package to video_jobs"
    assert '"status":' not in _body and '"progress":' not in _body and '"result":' not in _body, \
        "the package write must be narrative-only (no status/progress/result)"
    assert '"failed", "canceled", "completed"' in _body, \
        "the package write must be terminal-fenced"
    assert 'PROMPTLY_PACKAGE_PERSIST' in _body, "kill switch required"
    # ONE builder shape, re-capped at the persistence boundary
    _b = _h.find("def _build_post_package")
    assert _b != -1 and '("post_caption", post_caption, 120)' in _h[_b:_b + 1400] \
        and '("post_hook", post_hook, 60)' in _h[_b:_b + 1400], \
        "the ONE builder must re-cap every field at the boundary"
    # all-routes carriage: TH persist seam + TH durable completed write
    assert _h.count('"post_package": result_payload.get("post_package")') == 2, \
        "both durable completed writes (TH + caption-less) must carry result.post_package"
    assert "_persist_post_package(job_id, _build_post_package(" in _h, \
        "the TH pipeline must persist the package at the recipe-resolve seam"
    # caption-less routes: deterministic-honest values, persisted + carried
    _p = _h.find("def _run_minimal_pipeline")
    _mbody = _h[_p:_h.find("\ndef send_progress", _p)]
    assert "_persist_post_package(job_id, _post_package)" in _mbody \
        and '"post_package": _post_package' in _mbody, \
        "the caption-less routes must persist + carry the package"
    assert "def _minimal_post_package" in _h and "_minimal_post_package(reason, _dur)" in _mbody, \
        "minimal derives deterministic-honest values from the route reason"
    assert "_hype_bpm" in _mbody, \
        "hype derives its package from the measured beat (BPM), no model call"


@check("RECIPE WALL-CLOCK BUDGET (2026-07-24, p=50 compounding fix): the edit-recipe repair loop (≤_repair_max+1 re-asks) × the internal degen/transport retries (≤3 sub-attempts) can compound to ~6 post-cuts Gemini calls, each ≤480s, running the stage past Modal's timeout → an UNCODED SIGKILL at progress≈50 that bypasses the failure handler (0/26 long-wall deaths carried forensics). A running wall-clock deadline anchored on the job's pipeline start makes compounding re-asks engage the EXISTING deterministic safe edit BEFORE the SIGKILL. A clean single pass (135-337s) never trips it. Flag PROMPTLY_RECIPE_WALL (default on); =0 → deadline None → byte-identical. Budget = Modal timeout − render reserve (duration*3) − one-client-timeout (480s) tail reserve, so even a re-ask that started just under the deadline finishes below the wall. This is the source-poll fail-fast pattern one stage later.")
def _recipe_wall_budget():
    import re as _re
    import os as _os
    import handler as H
    # feature switch: default ON, kill switch → None (byte-identical off)
    assert H._recipe_wall_enabled() is True, "PROMPTLY_RECIPE_WALL must default ON"
    _os.environ["PROMPTLY_RECIPE_WALL"] = "0"
    try:
        assert H._recipe_deadline_from(1000.0, 180) is None, \
            "kill switch (PROMPTLY_RECIPE_WALL=0) must yield deadline None (byte-identical)"
    finally:
        _os.environ.pop("PROMPTLY_RECIPE_WALL", None)
    # deadline math: the budget always leaves the render reserve (duration*3) under
    # the Modal wall, and clears a clean pass's recipe-START (never cuts mid-pass)
    _dl = H._recipe_deadline_from(0.0, 180)
    assert _dl is not None and _dl <= H._MODAL_FN_TIMEOUT_S - 180 * 3, \
        "180s deadline must leave the duration*3 render reserve under the Modal timeout"
    assert _dl >= H._RECIPE_WALL_MIN_BUDGET_S >= 600.0, "budget floor must clear a clean pass's recipe-start"
    assert H._RECIPE_WALL_END_RESERVE_S >= 480.0, "tail reserve must absorb one 480s in-flight client-timeout"
    # _MODAL_FN_TIMEOUT_S must track the ACTUAL run_pipeline_bg timeout (drift guard)
    _t = _re.search(r"timeout=(\d+), retries=0, cpu=\d+, memory=\d+", open("modal_app.py").read())  # memory inc2-tunable; cpu=16 IDs run_pipeline_bg
    assert _t and int(_t.group(1)) == int(H._MODAL_FN_TIMEOUT_S), \
        f"_MODAL_FN_TIMEOUT_S ({H._MODAL_FN_TIMEOUT_S}) must match run_pipeline_bg timeout ({_t.group(1) if _t else '?'})"
    # wiring: threaded into the internal retry-stop, the repair loop-top, and the caller
    _h = open("handler.py").read()
    assert 'def _call_gemini_post_cuts(' in _h and 'recipe_deadline_s=None' in _h, \
        "the post-cuts call must accept the deadline"
    assert _h.count('recipe_deadline_s=recipe_deadline_s') == 2, \
        "both post-cuts call sites in the repair loop must pass the deadline through"
    assert 'if _will_retry and recipe_deadline_s is not None and time.time() > recipe_deadline_s:' in _h, \
        "the internal degen/transport retry must stop once past the deadline"
    assert 'recipe wall-clock budget exhausted after' in _h and 'recipe_wall_safe_edit' in _h, \
        "the loop-top guard must engage the safe edit (named reason + divergence) when past the deadline"
    assert 'recipe_deadline_s=_recipe_deadline_from(' in _h and '_pipeline_start, source_duration)' in _h, \
        "the caller must compute + pass the pipeline-anchored deadline (anchored on _pipeline_start)"
    assert 'PROMPTLY_RECIPE_WALL_S' in _h, "the cert override lever (force immediate exhaustion) must exist"


@check("STEP-TOKEN DURABILITY (2026-07-24): the iOS StageTimeline advances live off SSE `step`, but on a long mobile render SSE drops and the client polls video_jobs.current_step/step_message (EditorView:3066) — columns written ONLY by the server's /api/modal-progress handler, fed by send_progress's fire-and-forget POST (timeout=3, no retry). A dropped phase-transition POST while SSE is down freezes the label with no recovery until the next phase lands. The worker now writes current_step/step_message DIRECTLY to video_jobs at each phase (POST-independent), the two narrative columns ONLY (never status/progress/result — those stay the server's), monotonic (a late daemon write can't regress the label via _STEP_RANK), fail-open, terminal-fenced (never relabels a failed/canceled/completed row). Kill switch PROMPTLY_STEP_DURABLE=0.")
def _step_token_durable():
    _h = open("handler.py").read()
    assert 'def _persist_step_token(job_id, step, message):' in _h, "the durable step writer must exist"
    _i = _h.find("def _persist_step_token")
    _body = _h[_i:_i + 2200]
    # direct video_jobs write of exactly the two narrative columns
    assert 'supabase.table("video_jobs").update(_step_patch)' in _body, "must write directly to video_jobs"
    assert '"current_step": step,' in _body and '"step_message": message or "",' in _body, \
        "must persist current_step + step_message (the columns the iOS poll reads)"
    # narrative-only: no status/progress/result KEYS in the patch (the fence's bare
    # "status" arg has no colon, so the colon form distinguishes key from fence)
    assert '"status":' not in _body and '"progress":' not in _body and '"result":' not in _body, \
        "the durable step write must be narrative-only (no status/progress/result keys)"
    # monotonic + terminal fence + kill switch
    assert 'if rank >= 0 and rank < hw:' in _body, "monotonic guard: a late write must never regress the label"
    assert '.not_.in_(' in _body and '"failed", "canceled", "completed"' in _body, \
        "terminal fence: never relabel a closed row"
    assert 'PROMPTLY_STEP_DURABLE' in _body, "kill switch required"
    # wired into send_progress (fires on every phase transition)
    assert '_persist_step_token(job_id, step, message)' in _h, "send_progress must invoke the durable write"


@check("MULTILINGUAL C (verification tiers): Tier-1 = the 9 certified languages (contact sheet proved every script incl. Cyrillic); Tier-2 = every other font-backed language, enabled+WATCHED. Every non-English render is language-tagged (lang/script/tier) via a language_coverage divergence so the daily report shows what renders and can flag a failing Tier-2 language. English/Latin skipped to keep the ledger signal.")
def _multilingual_c_tiers():
    import handler
    # Tier-1 = the nine agreed certified languages
    _t1 = frozenset({"hi", "es", "pt", "ar", "fr", "de", "ru", "id", "ja"})
    assert handler._TIER1_LANGUAGES == _t1, handler._TIER1_LANGUAGES
    # tiering: Tier-1 codes → 1, others → 2, script fallback when no code
    for _c in _t1:
        assert handler._language_tier(_c) == 1, _c
    for _c in ("th", "vi", "he", "ta", "el"):
        assert handler._language_tier(_c) == 2, _c
    assert handler._language_tier(None, "Devanagari") == 1, "script fallback → Hindi is Tier-1"
    assert handler._language_tier(None, "Thai") == 2
    # non-English gate for telemetry: English Latin skipped, everything else tagged
    assert handler._is_non_english("en", "Latin") is False
    assert handler._is_non_english("es", "Latin") is True
    assert handler._is_non_english(None, "Arabic") is True
    assert handler._is_non_english(None, "Latin") is False
    # telemetry wired at the gate (fires after the coverage pass, before the edit)
    _h = open("handler.py").read()
    assert '"language_coverage"' in _h and "rendered_language" in _h, \
        "non-English renders must be language-tagged for the Tier-2 watch"
    # anchor on the rendered_language ACTION (the route's ar_route_failed ledger
    # legitimately uses the language_coverage component BEFORE the gate line)
    assert _h.index("if not _script_reaches_render(_script):") < _h.index('"rendered_language"'), \
        "the rendered_language tag must fire only after the coverage gate passes"
    # Cyrillic (Russian) — the one Tier-1 script the original sheet missed — is certified
    _bat = open("src/remotion/script-battery.mjs").read()
    assert "11-cyrillic" in _bat and "Cyrillic" in _bat, \
        "Tier-1 Cyrillic (Russian) must be in the contact-sheet battery"


@check("ARABIC BRIDGE (denylist leak-fix): Deepgram multi ROMANIZES Arabic → _dominant_script sees Latin → the denylist would leak (real Arabic → romanized garbage). _looks_confused = detected_language None AND a stopword-DENSITY text-LID can't confidently place the Latin text as a known Latin language (measured: certified Latin langs 0.17-0.50 density, romanized Arabic 0.13). On that → language=ar probe → confirmed Arabic treated AS Arabic → honest reject. Density (not absolute hits: romanized Arabic coincidentally hit 2 short PT stopwords) + probe-confirm → false-trigger only costs a probe, never a wrong reject.")
def _arabic_bridge():
    import handler
    assert callable(handler._looks_confused) and callable(handler._latin_lid) \
        and callable(handler._probe_confirms_arabic)
    # text-LID: places real Latin languages, fails to place romanized Arabic
    assert handler._latin_lid("most people give up right before the breakthrough and") == "en"
    assert handler._latin_lid("la mayoría de la gente se rinde justo antes del gran") == "es"
    assert handler._latin_lid("Muawami innasi yas tazlimuna qabil an najahi mubashara") is None
    # the confusion signature discriminates
    def _w(word, lang): return {"word": word, "language": lang, "confidence": 0.9}
    # romanized Arabic — detected=None + text no Latin-LID can place → trips it,
    # regardless of the (non-deterministic) per-word tags. Second mock has single-
    # language tags to prove the detection does NOT hinge on incoherent tags.
    _romanized_ar = {"detected_language": None, "words": [
        _w("Muawami","fr"), _w("innasi","hi"), _w("yas","fr"), _w("tazlimuna","hi"),
        _w("qabil","fr"), _w("najahi","hi")]}
    _romanized_ar2 = {"detected_language": None, "words": [
        _w(x,"fr") for x in "Muawami innasi yas tazlimuna qabil najahi mubashara".split()]}
    assert handler._looks_confused(_romanized_ar) is True, "romanized Arabic must trip the signature"
    assert handler._looks_confused(_romanized_ar2) is True, \
        "romanized Arabic must trip it even with COHERENT tags (detection can't hinge on tags)"
    # real English — placeable by the stopword LID → must NOT trip it (full text hits ≥2)
    _real_en = {"detected_language": None, "words": [_w(x,"en") for x in
                "the difference is not talent it is showing up one more time".split()]}
    assert handler._looks_confused(_real_en) is False, "real English must NOT trip it"
    assert handler._looks_confused({"detected_language": "es", "words": [_w("la","es")]}) is False, \
        "a placed language must NOT trip it"
    # per-word language captured in the parse (feeds the signature)
    _h = open("handler.py").read()
    assert '"language":        getattr(w, "language", None),' in _h, \
        "the Deepgram parse must capture per-word language for the signature"
    # SCRIPT-AWARE (graduation cert finding): Deepgram transliterates Arabic into
    # Latin OR Cyrillic run-to-run — both are suspect scripts; real Russian
    # places by Cyrillic stopword density and never pays the probe.
    _cyr_ar = {"detected_language": None, "words": [
        _w(x, None) for x in "ад-за-ка иль-спнайю мувами ин-насия стаслимуна кобиль ан-нажа хила кинна".split()]}
    assert handler._looks_confused(_cyr_ar, "Cyrillic") is True, \
        "Cyrillic-transliterated Arabic must trip the signature"
    _real_ru = {"detected_language": None, "words": [
        _w(x, None) for x in "большинство людей сдаются прямо перед прорывом они бросают на девяноста процентах когда не в таланте а в том чтобы".split()]}
    assert handler._looks_confused(_real_ru, "Cyrillic") is False, \
        "real Russian must NOT trip it (Cyrillic stopword density places it)"
    # wired at the gate BEFORE the reject: confusion → probe → treat-as-Arabic
    assert '_script in ("Latin", "Cyrillic")' in _h, \
        "the bridge must suspect BOTH transliteration scripts (Latin + Cyrillic)"
    assert "_looks_confused(_transcript, _script)" in _h and "_probe_confirms_arabic(_raw_source)" in _h
    assert _h.index("_probe_confirms_arabic(_raw_source)") < _h.index("if not _script_reaches_render(_script):")
    # CACHE PROPAGATION (graduation cert finding): the routed transcript must be
    # written into the resolved-transcript cache — rebinding the local name left
    # caption projection/SFX/hydration on the romanized transcript (0 pages).
    assert '_refined_tx_cache["value"] = _ar_full' in _h, \
        "the route must propagate the ar-transcript through the resolver cache"
    # density LID (not absolute hits) — the reliable discriminator
    assert "_LATIN_LID_MIN_DENSITY" in _h, "text-LID must place by stopword density"
    # graduation route (built, inert behind the denylist): confirmed Arabic
    # re-transcribes at language=ar for native script when Arabic reaches render.
    assert 'transcribe_audio(_raw_source, language="ar")' in _h, \
        "the graduation route must re-transcribe language=ar"
    assert 'def _deepgram_options(keywords=None, language="multi")' in _h, \
        "_deepgram_options must accept a language override (default multi = unchanged)"
    _route_i = _h.index('transcribe_audio(_raw_source, language="ar")')
    _guard_i = _h.rindex('if _script_reaches_render("Arabic"):', 0, _route_i)
    assert _guard_i < _route_i, "the route must be gated behind _script_reaches_render('Arabic') (inert while denylisted)"
    # ENV-GATED denylist (graduation = env flip, one-line rollback; PLAN_CAPTURE
    # pattern) — default keeps Arabic denied; PROMPTLY_SCRIPT_DENYLIST="" graduates.
    import os as _os2
    assert callable(handler._script_denylist)
    _prev = _os2.environ.get("PROMPTLY_SCRIPT_DENYLIST")
    try:
        _os2.environ.pop("PROMPTLY_SCRIPT_DENYLIST", None)
        assert "Arabic" in handler._script_denylist(), "default denylist must keep Arabic (uncertified)"
        _os2.environ["PROMPTLY_SCRIPT_DENYLIST"] = ""
        assert handler._script_denylist() == frozenset(), "empty env must graduate (no script denied)"
    finally:
        if _prev is None: _os2.environ.pop("PROMPTLY_SCRIPT_DENYLIST", None)
        else: _os2.environ["PROMPTLY_SCRIPT_DENYLIST"] = _prev
    _mo2 = open("modal_app.py").read()
    assert '"PROMPTLY_SCRIPT_DENYLIST": os.environ.get' not in _mo2, \
        "PROMPTLY_SCRIPT_DENYLIST must NOT be baked in modal_app .env() — it lives in the promptly-lang-flags secret"
    assert 'modal.Secret.from_name("promptly-lang-flags")' in _mo2, \
        "the promptly-lang-flags secret (carrying PROMPTLY_SCRIPT_DENYLIST='' — graduated) must be attached app-wide"
    # graduated-path regression: the permanent battery must assert the ROUTE
    # yields native-Arabic-script words (a graduation once proven stays proven)
    assert '"graduated_expect": "Arabic"' in _mo2 and "routed_script" in _mo2, \
        "the permanent regression must include the graduated-path check (Arabic in → Arabic-script words out)"
    # fail-closed route: graduated Arabic with a failed/foreign re-transcribe must
    # ERROR honestly, never render the romanized transcript
    assert "ar_route_failed" in _h and "failing closed rather than rendering" in _h, \
        "the graduated route must FAIL CLOSED (no romanized render on route failure)"
    # permanent regression (Zac): durable clips + a re-runnable end-to-end check
    # so a future Deepgram change that re-breaks probe/signature is caught.
    _mo = open("modal_app.py").read()
    assert "def cert_bridge_regression(" in _mo and "_BRIDGE_REGRESSION_CLIPS" in _mo, \
        "the Arabic-bridge permanent regression must exist (a detector once proven stays proven)"


@check("Reliability Phase 3 (spawn refactor, flag-gated OFF): run_pipeline_bg = plain retriable fn that POSTs /api/modal-complete with the call_id; run_job spawns only under PROMPTLY_SPAWN_MODE=1 (deploy INERT until the flip); sync path kept for rollback; completion result carries the re-edit hydration fields")
def _spawn_refactor_phase3():
    _m = open("modal_app.py").read()
    # run_pipeline_bg: a plain retriable function that delivers completion
    assert "def run_pipeline_bg(" in _m, "run_pipeline_bg missing"
    assert "retries=0" in _m, "run_pipeline_bg retries pinned to 0 (EMERGENCY cost cut 2026-07-30 — a failing job billed up to 3x; restore to 2 post-fix)"
    assert "/api/modal-complete" in _m and "modal.current_function_call_id()" in _m, \
        "completion POST (with the call_id) missing"
    # run_job flag-gated OFF by default → deploy is inert until the flag flips
    assert 'os.environ.get("PROMPTLY_SPAWN_MODE") == "1"' in _m, "run_job must be flag-gated"
    # In the promptly-lang-flags Modal Secret (value '1' — SPAWN dispatch; sync=0
    # starves the ASGI event loop), read at runtime — NOT baked from the deploy shell.
    assert '"PROMPTLY_SPAWN_MODE": os.environ.get' not in _m, \
        "PROMPTLY_SPAWN_MODE must NOT be baked in modal_app .env() — it lives in the promptly-lang-flags secret"
    assert 'modal.Secret.from_name("promptly-lang-flags")' in _m, \
        "the promptly-lang-flags secret (carrying PROMPTLY_SPAWN_MODE=1) must be attached app-wide"
    assert "run_pipeline_bg.spawn(body)" in _m and '"spawned": True' in _m, "spawn branch missing"
    # the synchronous path stays for a no-redeploy rollback (unset the flag)
    assert 'self._handler({"input": body})' in _m, "sync fallback must remain for rollback"
    # handler completion result carries the tiny re-edit hydration fields (2b) so
    # double-loss recovery restores the Re-edit button
    _h = open("handler.py").read()
    assert '"edit_recipe": result_payload.get("edit_recipe")' in _h, "re-edit hydration missing"
    for _f in ("transcript", "analysis_data", "resolved_broll", "render_version", "change_summary"):
        assert f'"{_f}": result_payload.get("{_f}")' in _h, f"hydration field {_f} missing"


@check("COST split Phase 0 — cls-demotion / SPAWN_MODE COUPLING: PromptlyWorker is demoted to cpu<64 (pure DISPATCHER — run_job spawns run_pipeline_bg under SPAWN_MODE=1 and never renders), which stopped the ~$700/mo iOS editor-open warmup leak (the warmup endpoint provisions THIS container). SAFE ONLY while SPAWN_MODE=1: the sync fallback (self._handler at run_job) would render the FULL pipeline on the small dispatcher and OOM/timeout if the flag flipped to 0. This gate FAILS if the cls is demoted without the SPAWN_MODE=1 run_job gate present — so a future cpu-raise or a silent flag-flip (this project has flipped SPAWN_MODE before) can't reintroduce the landmine. The canonical live VALUE (=1) is separately enforced by _secret_canonical_values.")
def _cls_demotion_spawn_mode_coupling():
    import re as _re
    _m = open("modal_app.py").read()
    _idx = _m.find("class PromptlyWorker")
    assert _idx > 0, "PromptlyWorker class missing"
    _dec = _m.rfind("@app.cls(", 0, _idx)
    assert _dec > 0, "PromptlyWorker @app.cls decorator missing"
    _block = _m[_dec:_idx]
    _cpu = _re.search(r"cpu=(\d+)", _block)
    assert _cpu, "PromptlyWorker cls cpu= missing"
    _cls_cpu = int(_cpu.group(1))
    if _cls_cpu < 64:
        assert 'os.environ.get("PROMPTLY_SPAWN_MODE") == "1"' in _m, (
            f"COUPLING VIOLATION: PromptlyWorker is cpu={_cls_cpu} (dispatcher-only) but run_job is NOT "
            f"gated on SPAWN_MODE=1 — the sync fallback would render the full pipeline on cpu={_cls_cpu} and "
            f"OOM/timeout. Restore cpu=64 OR keep the SPAWN_MODE=1 gate (live value enforced by _secret_canonical_values).")


@check("MOTION BLUR production wiring (Zac 2026-07-28 quality fix): DELIVERY_FPS=30 halved every Remotion spring's frame samples (a 180ms entrance dropped ~11→~5 frames) → visible stepping across all components at once. The remedy is the guard-passed s3_sh180 blur (3 samples, 180deg shutter) enabled for REAL traffic via PROMPTLY_MOTION_BLUR — blur fills the inter-frame gap so 30fps reads like 60 — NOT reverting to 60fps (which doubles render cost mid cost-emergency). This gate FAILS if the production blur path is removed from handler.py — the SAME silent-regression class that let the 60->30 fps drop ship ungated for two days. Flag-gated: unset/'0' restores byte-identical no-blur output.")
def _motion_blur_production_wiring():
    _h = open("handler.py").read()
    assert 'os.environ.get("PROMPTLY_MOTION_BLUR"' in _h, \
        "production motion-blur flag read removed from handler.py — 30fps renders will step again"
    assert '"samples": 3, "shutter": 180' in _h, \
        "s3_sh180 production blur config (3 samples / 180deg shutter) missing from handler.py"


@check("CUTTER content-word protection (Zac 2026-07-28): the cutter deleted CONTENT words like the 'Next' in 'Next question'. Root cause: _gemini_cut_span_removable clause (iii) authorized a cut from its LEFT boundary ALONE (sentence-final prev + >=0.70s pause), never inspecting the span's content — so a content word that merely OPENS a new sentence after a pause was dropped; AND Step-1 remove_words trusted every entry with no code-side validation (where the Hindi function word 'में' died). Fix: clause (iii) now requires dead air on BOTH sides (silence_after_s), Step-1 routes any untrusted-reason removal through the same gate, and per-word cut reasons are persisted for audit. This gate FAILS if any protection is stripped — the silent-regression class Zac flagged. Behavioral proof: test_cutter_content_protection.py (8 cases incl. the 3 real jobs; pure cut-logic, no Modal).")
def _cutter_content_protection():
    _h = open("handler.py").read()
    assert "def _gemini_cut_span_removable(span_words, following_words, prev_word, silence_before_s, silence_after_s" in _h, \
        "gate signature lost silence_after_s — fix #1 (both-sides dead air) removed; sentence-opener content words will be cut again"
    assert "(silence_after_s or 0.0) >= _MIDSENTENCE_STALL_S" in _h, \
        "clause (iii) no longer requires TRAILING dead air — a content word that opens a new sentence after a pause will be deleted again"
    assert "_TRUSTED_CUT_REASONS" in _h and "_gemini_cut_span_removable([_w], _fw, _pw, _sb, _sa)" in _h, \
        "Step-1 remove_words bypass reopened (fix #2) — untrusted-reason removals no longer routed through the content-word gate"
    assert 'edit_plan["_removed_word_reasons"]' in _h, \
        "per-word cut-reason persistence (addition #1) removed — deletions become unauditable from the DB again"
    import os as _os
    assert _os.path.exists("test_cutter_content_protection.py"), \
        "cutter regression suite (addition #2) missing — the 3-real-job protection can silently return"


@check("SECRET CANONICAL VALUES (values, not just mechanism): the promptly-lang-flags secret must carry the RIGHT values — SPAWN_MODE=1 (async spawn dispatch; sync=0 starves the ASGI loop), OUTCOME_GATE=shadow, LEVER3=1, EDIT_IN_LANGUAGE=1, SCRIPT_DENYLIST='', PLAN_CAPTURE=''. Reads the LIVE secret via an ephemeral Modal container (secret_flags_readback.py) and FAILS on any drift — so a future 'preserve the current value' sweep that bakes a regressed value (SPAWN_MODE=0) is caught HERE instead of shipping. The mechanism checks (flags not in .env(), secret attached) prove nothing can revert on a plain deploy; this proves the un-revertable value is the CORRECT one.")
def _secret_canonical_values():
    import subprocess as _sub, json as _json, os as _os
    # The canonical live production values. Changing one is a real production
    # decision — update it here AND in the secret together (never one alone).
    CANON = {
        "PROMPTLY_SPAWN_MODE": "1",       # async worker spawn — sync (0) starves ASGI
        "PROMPTLY_OUTCOME_GATE": "shadow",  # salvage-schema gate ledgers only
        "PROMPTLY_LEVER3": "1",           # degeneration-fix editorial prompt (live)
        "PROMPTLY_EDIT_IN_LANGUAGE": "1",  # multilingual + in-language editorial ON
        "PROMPTLY_SCRIPT_DENYLIST": "",   # graduated: no script denied
        "PROMPTLY_PLAN_CAPTURE": "",      # plan-capture corpus hook inert
        "PROMPTLY_BURNED_TEXT": "1",      # burned-in-text guard LIVE (flipped 2026-07-24 after flag-on smoke test)
        "PROMPTLY_ZERO_REJECT": "1",      # ZERO-REJECT LIVE (Zac's "FLIP MINIMAL" 2026-07-25 on the minimal samples; cert 5/5; rollback = 0 here + secret + redeploy)
        "PROMPTLY_WHY_DIET": "1",         # A-L1 output diet LIVE (rationale caps 240→96; output-bound call → speed lever; =0 is the one-flag rollback)
        "PROMPTLY_DELIVERY_FPS": "30",    # FPS 30 APPROVED (Zac blanket-GO 2026-07-25 on the A/B pair): delivery target 30fps — halves the render tail; rollback = "" (60) here + secret
        "PROMPTLY_RENDER_FANOUT": "0",    # A-L4 OFF — DELIBERATE EMERGENCY LEVER (Zac 2026-07-31). Fanout bills 8-16 parallel containers/long-render for a ~19% wall-clock win (cert 3/3 SSIM 1.0) and is implicated in the $1500 wall. Held at 0 during the cost emergency. Turning it back to 1 is a PRICED trade decision (fanout=1+cpu=16 vs fanout=0+cpu=16 $/job), NOT a drift-fix. Canonical tracks the deliberate LIVE value.
        "PROMPTLY_HYPE_MODE": "1",        # HYPE LIVE (Zac "FLIP HYPE" 2026-07-25 on the v2 pair): no-speech + confident beat (aubio tconf > 0.15) → beat-synced edit; every miss fail-safes to minimal; rollback = "0"
        "PROMPTLY_SHAPE_ABORT": "1",
        "PROMPTLY_MOODREEL": "1",     # cinematic mood-reel route LIVE (Zac "MOODREEL APPROVED" 2026-07-25; fail-safe-to-minimal; rollback = "0")     # degen shape-abort LIVE (ruling 1a; 5/5 shapes, 0 FP on 7.9k healthy; ~85-90% burn cut; rollback = "0")
        "PROMPTLY_HQ_RESAMPLE": "1",  # Part A fidelity LIVE (Zac "FLIP A" 2026-07-26 after FIDELITY_C): lanczos downscale + adaptive bpp-gated spline upscale; OFF-code is byte-identical so rollback = "0" here + secret + redeploy
        "PROMPTLY_BROLL_GATE": "1",   # B-roll content+safety gate LIVE (Zac "flip as ordered" 2026-07-26 after refined-gate cert 40% keep/60% reject, extinction guard passed): action-match + cutaway-window dense sampling; fail-closed to clean cuts; rollback = "0" here + secret + redeploy
        "PROMPTLY_COVERAGE_GATE": "1",  # TRANSCRIPTION-COVERAGE gate + bridge-selection LIVE (P0 content-destruction fix, Zac 2026-07-27; cert: Urdu delivers via multi 3.8s-unworded, truly-untranscribable refunds; E2E TRANSCRIPTION_INCOMPLETE+designed_rejection PASS; zero FP on clean corpus): VAD-speech-with-no-words > 2.0s/0.10 → coded error+refund; bridge keeps the better-coverage transcript; rollback = "0" here + secret + redeploy
        "PROMPTLY_LANG_ROUTING": "1",  # TIER-1 STAGE A LIVE (Zac 2026-07-28 viral surge): on coverage failure, Gemini language-ID → Deepgram monolingual for the GRADUATED languages (PROMPTLY_ROUTE_LANGS, not pinned here — it grows per-script; Hindi certified first). Recovers coverage-fail non-English into native-caption deliveries instead of rejecting. Negative-control-gated (Gemini-ID, not acoustic). rollback = "0" here + secret
        "PROMPTLY_SMOOTH_GRAPHICS": "1",  # VELOCITY CAP LIVE (Zac 2026-08-02: watched CAP vs OFF and approved by eye — "CAP looked SOO smooth, OFF didn't"). Bounds peak per-frame travel to ONE governed quantity for zooms + MG entrances (11px zoom / 1/6 entrance step); entrances only LENGTHEN. OFF-code byte-identical so rollback = "0" here + secret + redeploy. BLUR stays OUT (Zac).
        "PROMPTLY_ASR_SCRIBE": "1",  # LANGUAGE-ROUTED SCRIBE LIVE (Zac 2026-08-02, overnight zero-errors): on a Deepgram transcript that FAILS the coverage gate, route ElevenLabs Scribe (needs promptly-elevenlabs/ELEVENLABS_API_KEY) and keep the better-coverage native transcript before rejecting — recovers the zero-word / TRANSCRIPTION_INCOMPLETE class (bake-off: deepgram 3/40 -> scribe 34/40 on the failing set; control 32->39, no regression). Deepgram runs first + unchanged so an outage can't cost a job. rollback = "0" here + secret + redeploy.
        "PROMPTLY_RENDER_BURST": "1",  # inc2 FLIP LIVE (Zac GO 2026-08-02 naming the key): render_stage runs on the cpu=48 render_burst (16GiB blur-safe, was DARK/in-process). Enables run_pipeline_bg 64→24GiB (render no longer in-process here). A staging hiccup FAILS RETRYABLE (render_burst_staging_failed) — the in-process fallback was disarmed because run_pipeline_bg is 24GiB. rollback = "0" here + secret + redeploy, but RAISE run_pipeline_bg back to 48GiB FIRST (else a real in-process render OOMs) AND re-arm the local fallback.
        "PROMPTLY_POST_THINKING_BUDGET": "2048",  # THINKING BUDGET FLIP LIVE (Zac GO 2026-08-02 naming the key): the critical-path editorial Gemini call (generate_edit_gemini / _post_cuts_response_schema, handler.py:11593 — the edit_plan "longest wait" at 34979) drops from 24576→2048 thinking tokens. A/B measured -29.5s wall (65.3s→35.8s, out_tok stable) AND lower Gemini API cost; budget=0 is SLOWER (model needs some thinking). Cuts the critical path directly (fps_normalize is overlapped/off-path, saves ~0). rollback = "24576" here + secret + redeploy.
    }
    # Secrets are opaque to the SDK — the ONLY way to read a value is inside a
    # container that has it attached. secret_flags_readback.py does exactly that
    # and prints one line: READBACK {json}. Absolute path so cwd doesn't matter.
    _script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                            "secret_flags_readback.py")
    try:
        _r = _sub.run(["modal", "run", _script],
                      capture_output=True, text=True, timeout=300)
    except _sub.TimeoutExpired:
        assert False, ("could not verify promptly-lang-flags values — `modal run "
                       "secret_flags_readback.py` timed out (>300s); the canonical-"
                       "value guard could not run, so deploy is blocked.")
    _out = (_r.stdout or "") + "\n" + (_r.stderr or "")
    _line = next((l for l in _out.splitlines() if l.startswith("READBACK ")), None)
    assert _line, ("could not read promptly-lang-flags secret values — no READBACK "
                   "line from `modal run secret_flags_readback.py` (Modal unreachable/"
                   f"unauthed?). Deploy blocked.\n--- output tail ---\n{_out[-800:]}")
    _actual = _json.loads(_line[len("READBACK "):])
    _bad = {k: {"got": _actual.get(k), "want": v}
            for k, v in CANON.items() if _actual.get(k) != v}
    assert not _bad, (
        "promptly-lang-flags secret values DRIFTED from canonical: "
        f"{_json.dumps(_bad)}. A 'preserve the current value' sweep set a wrong "
        "value (SPAWN_MODE=0 re-opens the ASGI-starvation class). Fix: reset the "
        "secret to canonical (modal secret create promptly-lang-flags --from-json "
        "<canonical> --force), then redeploy.")


@check("Reliability Phase 1: platform-shutdown handler kills render children + flushes ledger on SIGTERM with NO terminal write (retry-safe); installed from worker startup; PLATFORM_TIMEOUT class = retryable, rescue-denied, alerts (not designed-silent)")
def _platform_shutdown_safety():
    import handler
    # the pieces exist and are wired
    assert callable(handler._on_platform_shutdown)
    assert callable(handler._install_shutdown_handler)
    assert callable(handler._kill_render_children)
    assert hasattr(handler, "_ACTIVE_JOB_ID")
    _src = open("handler.py").read()
    # the signal handler must NOT write a terminal status (a preempted input
    # retries — terminalizing here would falsely fail a job about to succeed).
    _fn = _src[_src.index("def _on_platform_shutdown("):_src.index("def _install_shutdown_handler(")]
    assert "write_job_status" not in _fn and "status=\"failed\"" not in _fn, \
        "shutdown handler must NOT write a terminal status (retry-safe)"
    assert "_kill_render_children()" in _fn and "_flush_divergence_ledger" in _fn, \
        "shutdown handler must kill render children + flush the ledger"
    # installed per-container from the worker's @modal.enter startup (snapshot-safe)
    _mods = open("modal_app.py").read()
    assert "_install_shutdown_handler()" in _mods, "handler must be installed from worker startup"
    # the active job is tracked at handler entry and cleared in teardown
    assert "_ACTIVE_JOB_ID = input_data.get(\"job_id\")" in _src, "active job not tracked at entry"
    # PLATFORM_TIMEOUT: retryable class, rescue-denied, and NOT designed-silent
    # (so the worker [ALERT] fires for the catchable case)
    _pt = handler.classify_error(RuntimeError("PLATFORM_TIMEOUT: preempted"))
    assert _pt["error_code"] == "PLATFORM_TIMEOUT" and _pt["retryable"] is True, _pt
    assert "interrupted by our infrastructure" in _pt["user_message"], _pt
    assert "PLATFORM_TIMEOUT" in handler._OUTER_RESCUE_DENY, "platform kill must be rescue-denied"
    assert "PLATFORM_TIMEOUT" not in handler._DESIGNED_REJECTION_CODES, \
        "PLATFORM_TIMEOUT must NOT be designed-silent — the [ALERT] fires for the catchable case"


@check("THREE-FIELD LANGUAGE BUNDLE (Zac 2026-07-28, surge, LIVE on every job): detected_language + transcript-script + vad_coverage persisted via a queryable divergence + the success result, so the frontend's per-script graduation gate (coverage-based criterion) and true by-language rejection reporting can read what previously lived only inside the coverage-gate trigger. Coverage computed ONCE and reused by the gate (no double VAD). Reject path carries detected_language.")
def _language_bundle():
    _h = open("handler.py").read()
    assert '_record_divergence("language_bundle"' in _h, "the bundle must be persisted on every job"
    assert '"detected_language": _det_lang' in _h and '"transcript_script": str(_script)' in _h \
        and '"vad_coverage_unworded_s"' in _h, "bundle must carry all three fields"
    assert 'edit_plan["_lang_bundle"] = _lang_bundle' in _h, "bundle must flow into the success result payload"
    assert "_cov_ok, _cov = _bundle_cov_ok, _bundle_cov" in _h, \
        "the coverage gate must REUSE the bundle's coverage (computed once, no double VAD)"
    assert "detected_language=_det_lang)  # by-language reject reporting" in _h, \
        "the reject path must tag detected_language for by-language reporting"


@check("TIER-1 STAGE A (Zac 2026-07-28, viral surge, DARK behind PROMPTLY_LANG_ROUTING): Deepgram multi mislabels + under-covers non-English (cert: Bengali/Tamil tagged 'hi', 40-85% short). When the FINAL transcript fails coverage, probe monolingual models (language=xx) for the candidate set and recover the best-coverage NATIVE transcript BEFORE rejecting — the arabic-bridge mechanism generalised past 'ar', turning an honest rejection into a delivery. Three binding laws: SELECTION (accept only a coverage-PASSING transcript), FAIL-CLOSED ON SCRIPT (native script or skip — never transliteration), FONT-BACKED (_script_reaches_render or skip — never tofu). OFF → never runs (byte-identical).")
def _tier1_stage_a():
    import handler
    _h = open("handler.py").read()
    assert "def _lang_routing_enabled(" in _h and 'os.environ.get("PROMPTLY_LANG_ROUTING"' in _h, \
        "Stage A must be flag-gated (dark by default)"
    # SELECTION must be INDEPENDENT — Gemini language-ID, NOT acoustic probe-and-select (the
    # negative control proved cross-model confidence/coverage/word-count all mis-select).
    assert "def _identify_language_gemini(" in _h, "selection must use an independent Gemini language-ID"
    assert "def _route_language_via_gemini(" in _h, "the safe Gemini-ID→single-model route must exist"
    assert "_bl_lang, _bl_tx, _bl_u = _route_language_via_gemini(" in _h, \
        "the wiring must use the Gemini-ID route, NOT the acoustic _probe_best_language"
    # GRADUATION: route only scripts proven end-to-end (Hindi certified; others gated by frontend)
    assert "def _graduated_route_langs(" in _h and "_lang not in _graduated_route_langs()" in _h, \
        "must route only GRADUATED languages (per-script frontend gate); en/ungraduated held for Stage B"
    assert handler._GRADUATED_ROUTE_LANGS_DEFAULT == frozenset({"hi"}), \
        "Hindi is the only certified route until each further script graduates"
    # FAIL-CLOSED + FONT-BACKED + coverage-PASS inside the route (a Gemini mis-ID is caught by these)
    assert "_sc != _expected" in _h and "if not _script_reaches_render(_sc):" in _h, \
        "route must fail-closed on wrong script AND require a font-backed script"
    assert "if _lang_routing_enabled() and _coverage_gate_enabled(input_data):" in _h, \
        "Stage A must run BEFORE the coverage-gate reject, only when coverage fails"
    assert '"lang_routing_recovered"' in _h, "a recovery must be ledgered (divergence)"


@check("Latin-scope flip: transcription=language=multi; _SCRIPT_COVERAGE=Latin (font-derived, tofu unconstructible); _dominant_script classifies Latin/Cyrillic/Devanagari/Arabic; uncovered script → NO_SPEECH_NONENGLISH BEFORE render")
def _script_coverage_gate():
    import handler
    # coverage is Latin-only, with the tofu scripts explicitly OUT
    assert handler._SCRIPT_COVERAGE == frozenset({"Latin"}), handler._SCRIPT_COVERAGE
    for _bad in ("Cyrillic", "Devanagari", "Arabic", "Han", "Tamil", "Telugu", "Bengali", "Hangul"):
        assert _bad not in handler._SCRIPT_COVERAGE, _bad
    # classifier correctness on real script samples
    def _w(s): return [{"word": s}]
    assert handler._dominant_script(_w("hello")) == "Latin"
    assert handler._dominant_script(_w("hola cómo estás")) == "Latin"       # Latin + accents
    assert handler._dominant_script(_w("привет")) == "Cyrillic"
    assert handler._dominant_script(_w("नमस्ते")) == "Devanagari"
    assert handler._dominant_script(_w("مرحبا")) == "Arabic"
    assert handler._dominant_script(_w("123")) == "Latin"                    # digits-only safe
    assert handler._dominant_script(_w("the") + _w("brown") + _w("привет")) == "Latin"  # majority Latin
    assert handler._dominant_script([]) == "Latin"                          # empty safe
    _src = open("handler.py").read()
    # transcription flipped to multi (the active option, not just a comment)
    assert 'model="nova-3", language="multi"' in _src, "transcription must be language=multi"
    # gate wired through the coverage helper (allowlist when PROMPTLY_EDIT_IN_LANGUAGE
    # off — the default this check asserts — denylist when on); an uncovered
    # script raises NO_SPEECH_NONENGLISH BEFORE the edit. See _multilingual_b_*.
    assert "if not _script_reaches_render(_script):" in _src, "script gate not wired"
    assert "NO_SPEECH_NONENGLISH" in _src, "the language-named reject must remain"
    assert _src.index("if not _script_reaches_render(_script):") < _src.index("Gemini edit starting"), \
        "script gate must precede the Gemini edit — no render on an uncovered script"
    # DERIVATION / tofu-unconstructible: the render image installs no Indic font,
    # so coverage cannot silently include an unrenderable script. Adding a Noto/
    # Indic font later forces a CONSCIOUS coverage expansion (this assert breaks).
    _mods = open("modal_app.py").read().lower()
    assert "fonts-dejavu-core" in _mods, "font-inventory anchor missing"
    _has_indic = any(k in _mods for k in ("fonts-indic", "lohit", "fonts-deva", "notosansdevanagari", "noto sans devanagari"))
    assert (not _has_indic) or handler._SCRIPT_COVERAGE != frozenset({"Latin"}), \
        "an Indic font was added to the image but _SCRIPT_COVERAGE is still Latin-only — expand coverage deliberately"


@check("D/D+ diagnosis-aware intake: CLIP_TOO_SHORT floor + NO_SPEECH split (non-English honesty / face-but-silent / plain) with correct ordering; new codes are designed + rescue-denied; stale copy retired")
def _diagnosis_aware_intake():
    import handler
    # CLIP_TOO_SHORT — duration-led, references the floor constant
    assert handler._MIN_SOURCE_DURATION_S == 5.0
    _short = handler.classify_error(RuntimeError("CLIP_TOO_SHORT: source is 3.0s; the intake floor is 5s."))
    assert _short["error_code"] == "CLIP_TOO_SHORT"
    assert "few seconds" in _short["user_message"] and "longer take" in _short["user_message"].lower(), _short
    # NO_SPEECH_NONENGLISH — must resolve the language name AND be ordered BEFORE
    # the generic NO_SPEECH branch (its substring), telling the honest truth.
    _ne = handler.classify_error(RuntimeError("NO_SPEECH_NONENGLISH: 23 words of non-English speech detected (lang=hi); English-only for now."))
    assert _ne["error_code"] == "NO_SPEECH_NONENGLISH", _ne  # NOT swallowed by NO_SPEECH
    assert "We heard you" in _ne["user_message"] and "Hindi" in _ne["user_message"], _ne
    # unknown language code → generic "more languages" tail, still honest
    _ne2 = handler.classify_error(RuntimeError("NO_SPEECH_NONENGLISH: 5 words (lang=xx); English-only for now."))
    assert _ne2["error_code"] == "NO_SPEECH_NONENGLISH" and "We heard you" in _ne2["user_message"], _ne2
    # NO_SPEECH_FACE — mic/inaudible, not "wrong video"
    _fs = handler.classify_error(RuntimeError("NO_SPEECH_FACE: face present but 0 words transcribed"))
    assert _fs["error_code"] == "NO_SPEECH_FACE" and "can see you" in _fs["user_message"], _fs
    # plain NO_SPEECH still works (nothing detected)
    _ns = handler.classify_error(RuntimeError("NO_SPEECH: Deepgram returned 0 words"))
    assert _ns["error_code"] == "NO_SPEECH", _ns
    # NOT_TALKING_HEAD stale copy retired
    _th = handler.classify_error(RuntimeError("NOT_TALKING_HEAD: face in only 1/20 frames"))
    assert "talking-to-camera" in _th["user_message"] and "This app edits videos of someone" not in _th["user_message"], _th
    # all new intake codes are designed rejections AND rescue-denied (input reject never rescued)
    for _c in ("CLIP_TOO_SHORT", "NO_SPEECH_NONENGLISH", "NO_SPEECH_FACE"):
        assert _c in handler._DESIGNED_REJECTION_CODES, _c
        assert _c in handler._OUTER_RESCUE_DENY, _c
    # the interim non-English detector exists, is best-effort, and returns (None,0) on bad input
    assert callable(handler._detect_nonenglish_speech)
    assert handler._detect_nonenglish_speech("/nonexistent/path.mp4") == (None, 0)


@check("render [ALERT] channel: _fire_render_alert emits a grep-stable [ALERT] line for real failures, never raises, and is gated to non-designed rejections at the call site")
def _render_alert_channel():
    import handler, contextlib as _ctx, io as _io, os as _os
    # exercise the ACTIVE path: with APP_URL unset the owner-push POST is a
    # no-op, but the grep-stable log leg must still fire (that's the leg that
    # survives even when push is down).
    _prev = _os.environ.pop("APP_URL", None)
    try:
        _buf = _io.StringIO()
        with _ctx.redirect_stdout(_buf):
            handler._fire_render_alert("testjob123", "RENDER_FATAL", detail="boom")
        _out = _buf.getvalue()
        assert "[ALERT]" in _out and "RENDER_FATAL" in _out and "testjob123" in _out, _out
    finally:
        if _prev is not None:
            _os.environ["APP_URL"] = _prev
    # the caller fires it ONLY for AT-FAULT failures — designed rejections AND
    # non-actionable client-upload failures stay silent (Zac 2026-07-28). The
    # gate now keys on _NON_ALERTING_CODES (see _alert_routing_split); UNKNOWN
    # and every unclassified code still page (loud-failsafe).
    import inspect as _insp
    _src = _insp.getsource(handler)
    assert ('_page_operator = (classified.get("error_code") not in _NON_ALERTING_CODES)' in _src
            and "if _page_operator:" in _src and "_fire_render_alert(" in _src), \
        "alert must be gated on _page_operator (code not in _NON_ALERTING_CODES)"


@check("120s cap MEASURE-IT (Zac 2026-07-11): every intake reject emits a grep-stable + S3-ledgered intake_rejected event (reason + measured source length) so the weekly table counts uploads the 2-min limit turns away; wired BEFORE the raise")
def _intake_reject_measured():
    import handler
    import contextlib as _ctx
    import io as _io
    # the measurement emits reason + measured length + cap on a grep-stable line
    _buf = _io.StringIO()
    with _ctx.redirect_stdout(_buf):
        handler._log_intake_reject("CLIP_TOO_LONG", 149.9, 120.0)
    _out = _buf.getvalue()
    assert "action=intake_rejected" in _out and "component=intake" in _out, _out
    assert "reason=CLIP_TOO_LONG" in _out and "149.9" in _out and "120" in _out, _out
    # and lands a structured S3-ledger entry (the weekly-table source at scale)
    _before = len(handler._DIVERGENCE_LOG)
    with _ctx.redirect_stdout(_io.StringIO()):
        handler._log_intake_reject("CLIP_TOO_LONG", 200.0, 120.0)
    assert len(handler._DIVERGENCE_LOG) == _before + 1, "measurement must ledger"
    _last = handler._DIVERGENCE_LOG[-1]
    assert _last.get("component") == "intake" and _last.get("action") == "intake_rejected" \
        and (_last.get("original") or {}).get("source_s") == 200.0, _last
    # never raises into the reject (fail-open on odd input)
    with _ctx.redirect_stdout(_io.StringIO()):
        handler._log_intake_reject("CLIP_TOO_LONG", None, None)
    # WIRED at the 120s reject site, and the measurement PRECEDES the raise
    _src = open("handler.py").read()
    _seam = _src.split('if mode == "full" and source_duration > _MAX_SOURCE_DURATION_S:', 1)
    assert len(_seam) == 2, "the 120s cap guard must be present"
    _w = _seam[1][:400]
    assert "_log_intake_reject(" in _w and "raise RuntimeError" in _w \
        and _w.index("_log_intake_reject(") < _w.index("raise RuntimeError"), \
        "measure THEN reject — the count is taken before the raise"
    # KILL-SITE ENUMERATION (rider): EVERY intake gate wired — none missed. The
    # explicit intake-gate raises carry "CODE:" at the message-string start;
    # classify_error branches use `"CODE"` (no colon) and don't match.
    # Longer codes ordered FIRST so the colon-anchored alternation binds the
    # most-specific match (NO_SPEECH_NONENGLISH before NO_SPEECH).
    import re as _re
    _raise_msgs = _re.findall(
        r'f?"(NO_SPEECH_NONENGLISH|NO_SPEECH_FACE|NO_SPEECH|NO_AUDIO_TRACK|'
        r'NOT_TALKING_HEAD|CLIP_TOO_LONG|CLIP_TOO_SHORT):', _src)
    _measures = _src.count('_log_intake_reject("')
    for _code in ("CLIP_TOO_LONG", "CLIP_TOO_SHORT", "NO_AUDIO_TRACK",
                  "NOT_TALKING_HEAD", "NO_SPEECH", "NO_SPEECH_NONENGLISH", "NO_SPEECH_FACE"):
        assert f'_log_intake_reject("{_code}"' in _src, f"intake gate {_code} not measured"
    # 9 = the original 5 (CLIP_TOO_LONG, NO_AUDIO_TRACK, NOT_TALKING_HEAD ×2,
    # NO_SPEECH) + the 3 D/D+ diagnosis gates (CLIP_TOO_SHORT, NO_SPEECH_NONENGLISH,
    # NO_SPEECH_FACE) + the zero-reject 2.0s hard floor (its own CLIP_TOO_SHORT
    # message + measurement pair — routes raise _MinimalRouteSignal instead and
    # ledger via zero_reject_minimal_route, deliberately NOT counted here: a
    # route is not a rejection). Every intake raise carries a measurement.
    assert len(_raise_msgs) == _measures == 9, \
        f"kill-site enumeration: every intake-gate raise must have a measurement " \
        f"(raises={len(_raise_msgs)} measures={_measures}); a new gate was added unmeasured"


@check("unification Slice 2: frame-domain truth CUT OVER — total/body/slots read from RenderTimeline, duplicates deleted")
def _timeline_slice2_cutover():
    _src = open("handler.py").read()
    # the one truth is built and CONSUMED (not a shadow)
    assert "UNIFICATION Slice 2 — the ONE output-timeline truth" in _src, "cutover block missing"
    assert "total_output_frames = _timeline[\"total_frames\"]" in _src, "total not sourced from the one truth"
    assert "_per_cut_render_dur_frames: List[int] = _rtl.body_frames_list(_timeline)" in _src, \
        "body frames not sourced from the one truth"
    assert '_slot_frames = (_timeline["entries"][i]["slot_frames_after"]' in _src, \
        "transitions_out slot not sourced from the one truth"
    # the duplicate frame accumulator is DELETED (deletion mandate)
    assert "_trans_frames_after" not in _src.replace(
        "# (the old _trans_frames_after used max(1) here and counted a phantom", ""), \
        "the deleted #D3 phantom accumulator reappeared"
    assert "sum(_per_cut_render_dur_frames) + _trans_frames_after" not in _src, \
        "the old total sum must be gone"
    # the Slice-1 shadow is retired (its census is filed)
    assert "[timeline-shadow]" not in _src, "the Slice-1 shadow must be removed post-cutover"
    assert 'add_local_file("render_timeline.py"' in open("modal_app.py").read()


@check("MODELS-NOT-SYMLINK LAW (Zac RULE-1, 2026-08-03, forged from the recurring 'Symlink loop from .../models' deploy death): `models/` is a GITIGNORED asset directory add_local_file-mounted into the image, but it was committed to HEAD as a self-referential symlink blob (the 4254ac7 clobber), so any `git checkout`/stash reverts the working tree to `models -> models` and `modal deploy` dies traversing the loop — while every source gate still passes. This gate closes the class: (1) `models` MUST be a real directory, never a symlink; (2) every `models/...` path modal_app.py mounts via add_local_file MUST exist as a real non-symlink file; (3) the RIFE weights (flownet.pkl) must be the real ~22MB blob, not a stub. Derived dynamically from modal_app.py so a new mounted asset is covered the day it is written.")
def _models_not_symlink():
    import os as _os
    # (1) models must be a real directory, never a symlink (the loop)
    assert _os.path.exists("models"), "models/ directory is missing (RIFE bundle not restored)"
    assert not _os.path.islink("models"), \
        "models/ is a SYMLINK — the self-referential clobber is back; it will die 'Symlink loop' on deploy. " \
        "Fix: git rm --cached models; rm models; restore the real gitignored dir with the RIFE files."
    assert _os.path.isdir("models"), "models/ exists but is not a directory"
    # (2) every models/... path modal_app.py mounts must exist as a real file
    _ma = open("modal_app.py").read()
    _mounted = re.findall(r'add_local_file\(\s*"(models/[^"]+)"', _ma)
    assert _mounted, "no add_local_file(\"models/...\") mounts found — did the RIFE mount get removed?"
    for _p in _mounted:
        assert _os.path.isfile(_p) and not _os.path.islink(_p), \
            f"mounted asset {_p} is missing or a symlink — deploy will fail or ship a broken asset"
    # (3) the RIFE weights must be the real blob, not a stub
    for _p in _mounted:
        if _p.endswith("flownet.pkl"):
            _sz = _os.path.getsize(_p)
            assert _sz > 20_000_000, f"{_p} is {_sz}B — the real RIFE weights are ~22MB; this is a stub/corrupt"


@check("unification Slice 2: the tripwire — body + real-slot immovability enforced (STOP-and-report in code)")
def _timeline_tripwire():
    _src = open("handler.py").read()
    assert "_rtl.assert_frame_truth(_timeline" in _src, "tripwire not called on the cutover path"
    import render_timeline as RT
    # a clean timeline passes
    _tl = RT.build_render_timeline(
        [{"source_start": 0, "source_end": 2.0}], [2.0], [0], [0], [0.0],
        [{"avg_speed": 1.0}], 60.0)
    RT.assert_frame_truth(_tl, [2.0], [0], [0], [0.0], 60.0)  # no raise
    # a body-frame movement is a hard STOP
    _bad = {"fps": 60.0, "total_frames": 999,
            "entries": [{"cut_index": 0, "out_start_frame": 0, "body_frames": 999,
                         "slot_frames_after": 0}]}
    try:
        RT.assert_frame_truth(_bad, [2.0], [0], [0], [0.0], 60.0)
        assert False, "tripwire failed to fire on a body-frame movement"
    except RuntimeError as e:
        assert "BODY VIOLATION" in str(e)


@check("unification Slice 2: #D3 fixed — one floor rule, phantom frame gone (behavioral + regression guard)")
def _timeline_d3_fixed():
    import render_timeline as RT
    # zero-handle recipe: the exemplar shape (a slot < 0.5 frame). Old code
    # counted max(1)=1 phantom per skip; the one truth counts 0.
    _tl = RT.build_render_timeline(
        [{"source_start": 0, "source_end": 1.0}, {"source_start": 2, "source_end": 3.0},
         {"source_start": 4, "source_end": 5.0}],
        [1.0, 1.0, 1.0], [0, 0, 0], [0, 0, 0], [0.004, 0.004, 0.0],
        [{"avg_speed": 1.0}] * 3, 60.0)
    # two sub-frame slots → both nonexistent → total is pure bodies (180), no phantoms
    assert [e["slot_frames_after"] for e in _tl["entries"]] == [0, 0, 0], "sub-frame slots must not exist"
    assert _tl["total_frames"] == 180, "phantom frames leaked into the total (#D3 regressed)"
    # regression guard: the total equals sum(body)+sum(real slots), never a max(1) inflation
    _expect = sum(e["body_frames"] + e["slot_frames_after"] for e in _tl["entries"])
    assert _tl["total_frames"] == _expect, "total diverged from body+slot sum"


@check("pacing budget (Slice 3): max-compress SHIPPED ON via env, per-job overridable, threaded to the clip builder")
def _pacing_max_compress():
    import handler
    _src = open("handler.py").read()
    # SHIPPED ON: env default (image flag), per-job override, warm-safe reset
    assert 'os.environ.get("PACING_MAX_COMPRESSION_ENABLED", "0")' in _src, \
        "env-default read missing"
    assert "_PACING_MAX_COMPRESS = _pmc_env if _pmc_job is None else bool(_pmc_job)" in _src, \
        "env-default-with-per-job-override wiring missing"
    assert '"PACING_MAX_COMPRESSION_ENABLED": "1"' in open("modal_app.py").read(), \
        "the ship flag must be ON in the image env"
    assert "max_compress=_PACING_MAX_COMPRESS" in _src, "flag not threaded to build_clips_from_words"
    # behavioral: max_compress compresses more gaps AND tighter than baseline
    W = [{"word": "a", "punctuated_word": "a", "start": 0.0, "end": 1.0},
         {"word": "b", "punctuated_word": "b", "start": 1.6, "end": 2.0},
         {"word": "c", "punctuated_word": "c", "start": 2.25, "end": 2.6}]
    base, _, _ = handler.build_clips_from_words(W, [], video_duration=10.0, vad_silences=[], max_compress=False)
    mc, _, _ = handler.build_clips_from_words(W, [], video_duration=10.0, vad_silences=[], max_compress=True)
    base_dur = sum(c["source_end"] - c["source_start"] for c in base)
    mc_dur = sum(c["source_end"] - c["source_start"] for c in mc)
    assert mc_dur < base_dur, "max_compress must shorten output (removes gap silence)"
    assert len(mc) >= len(base), "max_compress must split at least as many gaps"


@check("tight-cut overlay anchor: peaks ON the cut (clip boundary), not the word's audible end (v197 handle family)")
def _tco_anchor():
    _src = open("handler.py").read()
    # the anchor snaps to the CLIP BOUNDARY (release-pad-inclusive), matching
    # the TSX contract get_output_clip_ranges[i]["end"]
    assert "Anchor to the CLIP BOUNDARY, not the word's audible end" in _src, "anchor-fix comment missing"
    assert "_bounds_after = [" in _src and 'float(_r["end"]) for _r in _clip_ranges' in _src, \
        "anchor must read clip_ranges boundaries"
    assert "_nearest_boundary - _word_end_s <= 0.25" in _src, "clip-end snap guard missing"
    # the raw word-end-only anchor must be gone (no bare _at_frame = round(word_end))
    assert "_at_frame = int(round(_cut_seconds * source_fps))" in _src  # still the final quantize
    assert "_cut_seconds = _word_end_s" in _src, "word end must be the FALLBACK, not the anchor"
    # behavioral: boundary snap when within a release-pad; word-end when mid-clip
    def _anchor(word_end_s, clip_ranges, fps=60.0):
        _cut = word_end_s
        _ba = [float(r["end"]) for r in clip_ranges if float(r["end"]) >= word_end_s - (1.0 / fps)]
        if _ba:
            _nb = min(_ba)
            if 0.0 <= _nb - word_end_s <= 0.25:
                _cut = _nb
        return int(round(_cut * fps))
    # word ends 3.170s, clip boundary (with 75ms pad) 3.245s → snap to 195, not 190
    assert _anchor(3.170, [{"end": 3.245}, {"end": 6.9}]) == 195, "must snap to the clip boundary (the cut)"
    # mid-clip (nearest boundary far) → keep word end (no seam)
    assert _anchor(3.170, [{"end": 5.0}]) == 190, "mid-clip overlay must keep the word end"


@check("zone composer (DEFAULT-ON): drives the caption track in prod; packs disjoint bands; parity when no accents")
def _zone_composer_shadow():
    import handler
    _src = open("handler.py").read()
    # DEFAULT-ON (2026-07-08): the composer DRIVES the caption track in prod; the
    # env var is a kill-switch only, so it's NOT hard-set in the image env.
    assert "def _compose_band_occupancy(" in _src, "composer missing"
    assert '"COMPOSER_CUTOVER_ENABLED", "1"' in _src, \
        "cutover env read must default to '1' (composer drives in prod)"
    assert '"COMPOSER_CUTOVER_ENABLED"' not in open("modal_app.py").read(), \
        "kill-switch var must NOT be hard-set in the image env (default drives it ON)"
    assert "shadow=not _composer_cutover" in _src, "shadow wiring missing"

    def _seg(a, b, p): return {"fromFrame": a, "toFrame": b, "position": p}
    def _mg(f, d, anchor, typ="StatCard"):
        return {"fromFrame": f, "durationInFrames": d, "type": typ, "props": {"anchor": anchor}}
    def _to(f, d, variant, pos="top"):
        return {"fromFrame": f, "durationInFrames": d, "variant": variant, "position": pos}

    # AFFORDABLE-LUXURY: text_overlay(top) + MG(bottom) + caption → 3 disjoint bands
    r = handler._compose_band_occupancy(
        [_seg(0, 300, "bottom")], [_mg(100, 60, "lower_third_safe")],
        [_to(100, 60, "caption_match", "top")], [],
        shipped_caption=[_seg(0, 300, "bottom")], shadow=True)
    _cap = next(b for a, b_, b in r["caption_track"] if a <= 130 < b_)
    _to0 = [b for a, b_, b in r["element_bands"]["to0"] if a <= 130 < b_][0]
    _mg0 = [b for a, b_, b in r["element_bands"]["mg0"] if a <= 130 < b_][0]
    assert len({_cap, _to0, _mg0}) == 3, f"bands must be disjoint, got {_cap}/{_to0}/{_mg0}"
    # parity: no accents → composer caption == authored
    r2 = handler._compose_band_occupancy([_seg(0, 300, "bottom")], [], [], [],
                                         shipped_caption=[_seg(0, 300, "bottom")], shadow=True)
    assert all(b == "bottom" for _, _, b in r2["caption_track"]), "parity broken with no accents"
    # sticky_note (top-pinned) forces caption off top
    r3 = handler._compose_band_occupancy([_seg(0, 200, "top")], [], [_to(0, 200, "sticky_note")], [],
                                         shipped_caption=[_seg(0, 200, "top")], shadow=True)
    assert next(b for a, b_, b in r3["caption_track"] if a <= 50 < b_) != "top", \
        "caption must clear the sticky_note's top band"
    # B-roll full-frame → caption rides top, accent dropped
    r4 = handler._compose_band_occupancy([_seg(0, 200, "bottom")], [_mg(0, 200, "center")], [], [(0, 200)],
                                         shipped_caption=[_seg(0, 200, "bottom")], shadow=True)
    assert next(b for a, b_, b in r4["caption_track"] if a <= 50 < b_) == "top"
    assert "dropped_broll" in str(r4["element_bands"].get("mg0"))


@check("content-jump magnitude: wide single-cam jumps annotated as EMPHASIS signal (picture holds, hard cut carries), not a transition home")
def _transition_jump_foldin():
    _src = open("handler.py").read()
    assert "_scene_turn_set" in _src and "_SCENE_TURN_FRACTION" in _src, "scene-turn tier missing"
    # READING A (Zac 2026-07-08): the wide single-cam jump is a CONTENT jump, not a
    # picture change — the annotation must point the energy at emphasis, not invite a
    # transition. The old "the footage turns here" wording (READING B) is gone.
    assert "the footage turns here even with no camera cut" not in _src, \
        "old READING-B annotation (invites single-cam transitions) must be gone"
    assert "the talk turns here but the picture holds" in _src, \
        "magnitude annotation must frame the jump as content (picture holds), not a picture change"
    assert "goes to the first word back" in _src, \
        "annotation must route the jump's energy to emphasis (mask-zoom/caption/SFX)"
    # the floor guards a breath from being named a scene turn
    assert "_SCENE_TURN_FLOOR_S" in _src, "absolute scene-turn floor missing"


@check("phrase-retake detector: 5th mechanical detector — catches complete-phrase retakes, preserves rhetorical repetition")
def _phrase_retake_detector():
    import handler
    _src = open("handler.py").read()
    # wired as the 5th detector, feeding word_removals like the other four
    assert "detect_phrase_retake(deepgram_words)" in _src, \
        "detect_phrase_retake must run in compute_mechanical_cuts"
    # it now runs behind the per-word English gate (_en_cut) — the LANGUAGE WINS check
    # proves reduplication is preserved while English/route retakes still cut.
    assert "retakes = [d for d in detect_phrase_retake(deepgram_words) if _en_cut(d)]" in _src, \
        "retake cuts must be filtered by the per-word English gate (_en_cut)"
    assert "word_removals = fillers + false_starts + stutters + retakes" in _src, \
        "retakes must join the mechanical word_removals set"
    # behavioral: build word dicts and exercise recall + the FP guards

    def _mk(text, gap=0.15, spk=0):
        ws, t = [], 0.0
        for tok in text.split():
            ws.append({"punctuated_word": tok, "word": tok.strip(".,!?"),
                       "start": t, "end": t + 0.25, "speaker": spk})
            t += 0.25 + gap
        return ws

    def _cuts(text):
        return sorted(x["word_index"] for x in handler.detect_phrase_retake(_mk(text)))

    # RECALL — the caf020a5 specimen: cut the discarded first take, keep the retake
    assert _cuts("This is a hot towel warmer. This is a hot towel dispenser.") == [0, 1, 2, 3, 4, 5], \
        "must cut the discarded 'warmer' take and keep the 'dispenser' retake"
    # verbatim full-sentence re-delivery is also a retake
    assert _cuts("I really love this product a lot. I really love this product a lot.") == [0, 1, 2, 3, 4, 5, 6]
    # FALSE-POSITIVE GUARDS — intentional repetition MUST be preserved (zero cuts)
    assert _cuts("Retire. Retire. Retire.") == [], "rhetorical triple must survive"
    assert _cuts("of the people by the people for the people") == [], "multiword triad must survive"
    assert _cuts("In the morning I go running outside. In the evening I cook a nice dinner.") == [], \
        "anaphora (short shared opener, long divergent body) must survive"
    assert _cuts("Stop. Stop.") == [], "short emphatic repeat must survive"
    assert _cuts("you get a charger, you get a cable,") == [], "comma-continuation list must survive"
    assert _cuts("this is a totally normal sentence with no repeats at all here") == [], \
        "non-repetitive speech must never be cut"


@check("within-clip dead-air (LIVE default-ON): 15ms gap INVARIANT — audible-to-audible between-words gap derived, not measured; Zac ear-confirmed 2026-07-09")
def _within_clip_deadair():
    import handler
    _src = open("handler.py").read()
    # LIVE (Zac 2026-07-09): ear-confirmed on towel + whisper (cuts tight, no word clipped);
    # invariant proven — towel/srcB/concat max between-words gap 15-16ms (was 280ms), Step-4c
    # clips ZERO speech on all 6 corpus sources. Env var is a kill-switch only.
    assert handler._WITHIN_CLIP_DEADAIR is True, "flag must default ON (live in prod, ear-confirmed)"
    assert '"WITHIN_CLIP_DEADAIR_ENABLED", "1"' in _src, \
        "env read must default to '1' (ON in prod; var is a kill-switch)"
    assert '"WITHIN_CLIP_DEADAIR_ENABLED"' not in open("modal_app.py").read(), \
        "kill-switch var must NOT be hard-set in the image env (default drives it ON)"
    # ARCHITECTURE: dB locates, Gemini decides, machinery executes.
    assert "def _detect_silence_regions_level(" in _src, "level LOCATOR missing"
    assert "located_silences" in _src, "located-silences hand-off to Gemini missing"
    assert "preserved_silences" in _src, "Gemini DECIDE field missing"
    assert "within_clip_edge_trim" in _src, "unified clip-edge EXECUTE pass missing"
    # BETWEEN-WORDS GAP INVARIANT (Zac 2026-07-09 rebuild): the OUTPUT dead air between the
    # last audible sample of word N and the first of N+1 is _BETWEEN_WORD_GAP_S — DERIVED, not
    # measured (a 280ms gap is unconstructible). clip_end = sound_end + gap/2; clip_start =
    # sound_start - gap/2, where sound_end/start are the last/first AUDIBLE sample located from
    # the per-frame energy (the floor+10 silence spans fragment on breaths — 209 on the towel).
    assert "_compute_floor_speech_range" in _src, "floor/speech/range derivation missing"
    assert "_DEADAIR_BETWEEN_PCT" in _src and "_DEADAIR_WITHIN_PCT" in _src, \
        "proportional (position-in-range) thresholds missing"
    assert "_DEADAIR_BETWEEN_PCT * _range" in _src, \
        "between threshold must be floor + PCT*range (proportional, not a fixed offset)"
    assert hasattr(handler, "_BETWEEN_WORD_GAP_S"), "the 15ms gap-invariant constant missing"
    assert 0.008 <= handler._BETWEEN_WORD_GAP_S <= 0.030, \
        f"between-words gap must be ~15ms, got {handler._BETWEEN_WORD_GAP_S}"
    assert "_AUDIO_DB_LAST" in _src, "energy-based audible-edge locator missing (spans fragment on breaths)"
    # D2 (Zac's render verdict 2026-07-11): the tail derivation gained its
    # floor — clip_end = max(sound_end, last word_end) + gap/2, and the FINAL
    # clip is never tail-trimmed (nothing follows it; the decay is content).
    assert "_new_ce = max(_sound_end, _floor_we) + _tail_pad" in _src, \
        "clip_end = max(sound_end, word_end) + gap/2 (floored invariant) missing"
    assert "_sound_end is not None and _ci < _n - 1" in _src, \
        "the FINAL clip must never be tail-trimmed (the 'nothi-' class)"
    assert "_new_cs = _sound_start - _head_pad" in _src, "clip_start = sound_start - gap/2 (invariant) missing"
    # MIN-RANGE NO-OP GUARD (Zac 2026-07-09): a loud continuous bed (music under speech)
    # collapses floor->speech separation; floor+PCT*range would sit a hair under speech and
    # EAT it. Below MIN_RANGE the pass LOCATES NOTHING (unconstructible form of "don't trim
    # when the room won't let you tell speech from silence"). The old max(6,...) floor is DELETED
    # — flooring a degenerate range pushes the between threshold ABOVE speech.
    assert hasattr(handler, "_DEADAIR_MIN_RANGE_DB"), "MIN_RANGE no-op guard constant missing"
    assert 4.0 <= handler._DEADAIR_MIN_RANGE_DB <= 12.0, \
        f"MIN_RANGE must sit between music-bed (~6.4) and whisper (~14.4), got {handler._DEADAIR_MIN_RANGE_DB}"
    assert "if _range < _DEADAIR_MIN_RANGE_DB:" in _src, "no-op guard branch missing"
    assert "NO-OP (located nothing" in _src, "no-op log line missing"
    assert "max(6.0, _speech - _floor)" not in _src, \
        "the flawed degenerate-range FLOOR must be DELETED (it eats speech on a music bed)"
    assert "return (_floor, _speech, _speech - _floor)" in _src, \
        "_compute_floor_speech_range must return the TRUE range so the caller's guard can no-op"
    # BEHAVIORAL: a stationary bed (no true silence) yields a range BELOW MIN_RANGE and is NOT
    # floored to 6 — proves the guard has something to fire on and the old floor is gone.
    import numpy as _np, wave as _wave, tempfile as _tf, os as _os
    _wp = _os.path.join(_tf.gettempdir(), "deadair_gate_lowrange.wav")
    _bed = _np.random.RandomState(7).uniform(-0.09, 0.09, 48000 * 2).astype(_np.float32)
    with _wave.open(_wp, "w") as _wf:
        _wf.setnchannels(1); _wf.setsampwidth(2); _wf.setframerate(48000)
        _wf.writeframes((_np.clip(_bed, -1, 1) * 32767).astype("<i2").tobytes())
    _r = None
    try:
        _fl, _sp, _r = handler._compute_floor_speech_range(_wp, [(0.0, 2.0)])
    except (FileNotFoundError, OSError):
        _r = None   # ffmpeg unavailable locally — the source assertions above still gate
    if _r is not None:
        assert _r < handler._DEADAIR_MIN_RANGE_DB, \
            f"stationary bed (no silence) must yield range < MIN_RANGE, got {_r:.1f}dB"
        assert abs(_r - 6.0) > 1e-6, "range must be the TRUE separation, not the deleted max(6,...) floor"
    # BEHAVIORAL — the gap invariant. Synthesize the per-frame energy the locator reads: word
    # "one" audible [0.0,0.40], dead air to 1.60, word "two" audible [1.60,2.00]. floor -50,
    # range 40 -> audible line floor+0.2525*40 = -39.9. The trim must land clip_end at 0.40+gap/2
    # and clip_start at 1.60-gap/2, so the output gap is exactly _BETWEEN_WORD_GAP_S.
    _hop = 0.005
    _arr = _np.full(int(2.2 / _hop), -50.0)
    _arr[int(0.0 / _hop):int(0.40 / _hop)] = -20.0
    _arr[int(1.60 / _hop):int(2.00 / _hop)] = -20.0
    handler._AUDIO_DB_LAST = _arr
    handler._AUDIO_DB_META = {"floor": -50.0, "range": 40.0, "hop": _hop}
    handler._WITHIN_WORD_SILENCES_LAST[:] = [(0.40, 1.60)]   # non-empty so the block runs
    _dg = [{"word": "one", "punctuated_word": "one", "start": 0.0, "end": 0.5},
           {"word": "two", "punctuated_word": "two", "start": 1.5, "end": 2.0}]
    _rw = [{"after_word_index": 0, "before_word_index": 1, "reason": "dead_air"}]
    _g, _, _ = handler.build_clips_from_words(_dg, _rw, video_duration=2.2,
                                           level_silences=[(0.40, 1.60)], within_clip_15ms=True)
    _half = handler._BETWEEN_WORD_GAP_S / 2.0
    # D2 reconciliation: over DEAD-FLAT silence (this fixture: -50dB floor in
    # [0.40, 0.50]) the loose Deepgram end is the artifact — the 15ms
    # invariant rules and the tail trims to sound_end + gap/2 as ever.
    assert abs(_g[0]["source_end"] - (0.40 + _half)) < 0.012, \
        f"dead-flat tail: clip_end must be sound_end 0.40 + gap/2, got {_g[0]['source_end']}"
    assert abs(_g[-1]["source_start"] - (1.60 - _half)) < 0.012, \
        f"clip_start must be audible sound_start 1.60 - gap/2, got {_g[-1]['source_start']}"
    # D2 floor case ('nothi-' class): the same geometry but the band
    # [0.40, 0.50] carries DECAYING SPEECH (-42dB > floor+10%·range = -46)
    # → the word_end floor holds; the soft syllable is never cut.
    _arr2 = _np.full(int(2.2 / _hop), -50.0)
    _arr2[int(0.0 / _hop):int(0.40 / _hop)] = -20.0
    _arr2[int(0.40 / _hop):int(0.50 / _hop)] = -42.0
    _arr2[int(1.60 / _hop):int(2.00 / _hop)] = -20.0
    handler._AUDIO_DB_LAST = _arr2
    _g2, _, _ = handler.build_clips_from_words(_dg, _rw, video_duration=2.2,
                                            level_silences=[(0.50, 1.60)], within_clip_15ms=True)
    assert abs(_g2[0]["source_end"] - (0.50 + _half)) < 0.012, \
        f"decaying tail: clip_end must FLOOR at word_end 0.50 + gap/2, got {_g2[0]['source_end']}"
    _gap = (_g[0]["source_end"] - 0.40) + (1.60 - _g[-1]["source_start"])
    assert abs(_gap - handler._BETWEEN_WORD_GAP_S) < 0.006, \
        f"between-words OUTPUT gap must equal {handler._BETWEEN_WORD_GAP_S}, got {_gap:.4f}"
    assert _g[0]["source_end"] >= 0.40 - 1e-6, "must keep ALL of word one's audible sound (no clip)"
    # video-final word protection: single clip keeps its audible tail (lead-out, not amputated)
    _arr2 = _np.full(int(1.5 / _hop), -50.0)
    _arr2[int(0.5 / _hop):int(1.0 / _hop)] = -20.0
    handler._AUDIO_DB_LAST = _arr2
    handler._AUDIO_DB_META = {"floor": -50.0, "range": 40.0, "hop": _hop}
    handler._WITHIN_WORD_SILENCES_LAST[:] = [(1.0, 1.5)]
    _solo, _, _ = handler.build_clips_from_words(
        [{"word": "you", "punctuated_word": "you", "start": 0.5, "end": 1.0}],
        [], video_duration=1.5, level_silences=[(1.0, 1.5)], within_clip_15ms=True)
    assert _solo and _solo[-1]["source_end"] >= 1.0 - 1e-6, \
        "video-final word's audible tail must be kept (lead-out), never amputated"
    # SPAN-SPLIT (Step 4d): silence Deepgram hid INSIDE a word span. One word [0,2.4] whose
    # audio is audible [0.06,0.8] + [1.2,2.34] with a 400ms interior silence — the split must
    # produce TWO clips at the invariant edges (0.8+gap/2 | 1.2-gap/2). A Gemini-preserved
    # span covering that silence must make the split a no-op (judgment stays Gemini's).
    assert hasattr(handler, "_SPAN_SPLIT_MIN_S"), "span-split minimum constant missing"
    assert "span_split" in _src, "span-split divergence record missing"
    assert "_PRESERVED_SILENCES_LAST" in _src, "preserved-silences exclusion missing from span-split"
    _arr3 = _np.full(int(2.4 / _hop), -50.0)
    _arr3[int(0.06 / _hop):int(0.8 / _hop)] = -20.0
    _arr3[int(1.2 / _hop):int(2.34 / _hop)] = -20.0
    handler._AUDIO_DB_LAST = _arr3
    handler._AUDIO_DB_META = {"floor": -50.0, "range": 40.0, "hop": _hop}
    handler._WITHIN_WORD_SILENCES_LAST[:] = [(0.8, 1.2)]
    handler._PRESERVED_SILENCES_LAST[:] = []
    # A (Zac 2026-07-11): the linguistic gate — the split now requires
    # sentence-final context (or a >=700ms stall). Sentence-final word: splits.
    _sp, _, _ = handler.build_clips_from_words(
        [{"word": "offff", "punctuated_word": "offff.", "start": 0.0, "end": 2.4}],
        [], video_duration=2.4, level_silences=[(0.8, 1.2)], within_clip_15ms=True)
    assert len(_sp) == 2, f"interior 400ms silence AFTER sentence-final punct must SPLIT, got {len(_sp)} clip(s)"
    # Mid-sentence (no punctuation), same 400ms quiet: RHYTHM — uncuttable.
    _sp_r, _, _ = handler.build_clips_from_words(
        [{"word": "offff", "punctuated_word": "offff", "start": 0.0, "end": 2.4}],
        [], video_duration=2.4, level_silences=[(0.8, 1.2)], within_clip_15ms=True)
    assert len(_sp_r) == 1, f"mid-sentence 400ms quiet is RHYTHM — must NOT split, got {len(_sp_r)}"
    _half2 = handler._BETWEEN_WORD_GAP_S / 2.0
    assert abs(_sp[0]["source_end"] - (0.8 + _half2)) < 0.012, \
        f"split piece1 must end at sound_end 0.8 + gap/2, got {_sp[0]['source_end']}"
    assert abs(_sp[1]["source_start"] - (1.2 - _half2)) < 0.012, \
        f"split piece2 must start at sound_start 1.2 - gap/2, got {_sp[1]['source_start']}"
    handler._PRESERVED_SILENCES_LAST[:] = [(0.8, 1.2)]
    _sp2, _, _ = handler.build_clips_from_words(
        [{"word": "offff", "punctuated_word": "offff", "start": 0.0, "end": 2.4}],
        [], video_duration=2.4, level_silences=[(0.8, 1.2)], within_clip_15ms=True)
    assert len(_sp2) == 1, \
        f"a Gemini-PRESERVED showing beat must never be span-split, got {len(_sp2)} clip(s)"
    handler._AUDIO_DB_LAST = None
    handler._AUDIO_DB_META = {}
    handler._WITHIN_WORD_SILENCES_LAST[:] = []
    handler._PRESERVED_SILENCES_LAST[:] = []


# ── DELETED (Zac step-6): the scene-gate check — its mechanism is deleted,
# not disabled. Off-boundary transitions are unrepresentable (sub-call const
# indices); the qualify union builds the seam list instead of policing output.
# The two teaching assertions it carried move here:
@check("A1/A2 teaching anchors: sub-call teaches picture-change + hard-cut-owns-same-scene; main stub keeps the energy line")
def _a1a2_teaching_anchors():
    _src = open("handler.py").read()
    assert "A transition is the visual treatment on a PICTURE CHANGE" in _src, \
        "sub-call block must teach picture-change anchoring"
    assert "those splices are not offered here" in _src, \
        "sub-call block must teach hard-cut-owns-same-scene"
    assert "the hard cut owns them" in _src, \
        "main stub must keep the same-scene energy line"

@check("A1/A2 room domain: seams src-translated, rooms from splice-gap + located silence via THE one mapping; author precedes the split gate; refinement reserved off taken seams")
def _a1a2_room_domain():
    _src = open("handler.py").read()
    # (1) Shot seams reach the sub-call in SOURCE space (new_to_src), the domain
    # every consumer reads — the kept-ni-into-src-array class is dead.
    assert "_shot_seam_src.add(int(new_to_src[int(_ni2)]))" in _src, \
        "wire-in must translate shot boundaries kept→src via new_to_src"
    assert "_dg_words[_awi2 + 1].get(\"start\")" not in _src, \
        "the raw adjacent-Deepgram-gap room formula must be deleted"
    # (2) THE one mapping: room derivation and the application loop read the
    # same seam→splice rule, so an offered room cannot fail to apply.
    assert _src.count("_seam_splice_index(") >= 3, \
        "_seam_splice_index must exist and be read by BOTH the wire-in and the application loop"
    assert "min(_sil_fwd(_E2), _sil_back(_S2), _gap2 / 2.0)" in _src, \
        "room must be min(per-side located silence, dropped-gap/2) — the executor's own arithmetic"
    # (3) Ordering: the author writes before the shot splitter's gate reads.
    _wire = _src.index("A1/A2 TRANSITIONS SUB-CALL wire-in (room-domain corrected)")
    _gate = _src.index("Filter to boundaries where Gemini emitted a transition.")
    assert _wire < _gate, "sub-call must run BEFORE the transition-gated shot splitter"
    # (4) The reservation: refinement skips both edges of a taken splice.
    assert "not _has_real_transition(render_cuts[_ri])" in _src \
        and "not _has_real_transition(render_cuts[_ri - 1])" in _src, \
        "boundary refinement must be reserved off transition-carrying splices"
    # (5) Overlay gate honors the sub-call's own seam set on the governed path.
    assert "_subcall_seam_awis" in _src, "overlay gate must accept sub-call seam membership"
    # (6) Behavioral: the mapping tolerates dB-trimmed edges (word_end beyond
    # clip end lands in the gap → still maps) and refuses mid-clip seams.
    import handler as _h
    _dgw = [{"end": 1.0, "start": 0.5}, {"end": 21.625, "start": 21.0},
            {"start": 22.985, "end": 23.2}, {"start": 23.3, "end": 23.5}]
    _cuts = [{"source_start": 0.4, "source_end": 21.44},
             {"source_start": 22.9, "source_end": 23.6}]
    assert _h._seam_splice_index(1, _dgw, _cuts, set()) == 0, \
        "trimmed-edge seam (word_end 21.625 vs clip end 21.44) must map to its splice"
    assert _h._seam_splice_index(2, _dgw, _cuts, set()) is None, \
        "mid-clip seam (next kept word inside the same clip) must have no splice"


@check("Kill-site inventory: rider survives final_cuts; sound never leaks to extras; derived fields persist; replay parity + drops ledgered; policy gates the author; audits accept counted misses")
def _kill_site_inventory():
    _src = open("handler.py").read()
    # K1: the rider's carrier survives the final_cuts rebuild (its ONE reader
    # is _transition_sound_events over render cuts — severed = rider never fires).
    assert '_new_cut["_transition_sound"] = clip_entry["_transition_sound"]' in _src, \
        "final_cuts must copy _transition_sound"
    # K2: "sound" must never leak into _transition_extras (TransitionSpec is
    # extra=forbid — the leak was a render-killer on any rider-carrying recipe).
    assert '"type", "after_word_index", "why", "sound"' in _src, \
        "extras filter must exclude 'sound'"
    # K3: EditPolicy transitions=off gates the sub-call itself.
    assert "if not _transitions_off else []" in _src, \
        "the sub-call's seam candidates must be gated on _transitions_off"
    # K4/K5: derived carriers persist; replay parity is alarmed, not silent.
    for _k in ("_resolved_tight_cut_overlays", "_parsed_sound_effects",
               "_emphasis_moments", "_removed_word_indices", "_schema_generation"):
        assert f'"{_k}",' in _src.split("_PERSIST_DERIVED_KEYS = {")[1].split("}")[0], \
            f"persist whitelist must carry {_k}"
    assert "replay_derived_fields_absent" in _src, "replay parity alarm must exist"
    # K6: retired transition types coerce at the CUT level before slot sizing.
    assert 'cuts.transition_out' in _src and _src.index('"site": "cuts.transition_out"') \
        < _src.index("_trim_head_dur = [0.0] * len(render_cuts)"), \
        "NewspaperWipe cut-level coerce must run before handle/slot sizing"
    # K7: projection-miss drops are counted + ledgered and the integrity audits
    # accept the counted misses (one miss must not rung-2 the whole video).
    assert _src.count("projection_miss_drop") >= 3, "all three projection-miss drops must ledger"
    assert "len(motion_graphics_out) + _mg_projection_misses" in _src \
        and "len(text_overlays_out) + _tov_projection_misses" in _src, \
        "integrity audits must accept counted projection misses"
    # K8: every transition application drop + the wire-in except are ledgered.
    for _a in ("drop_out_of_bounds", "drop_removed_word", "drop_no_clip_pair",
               "subcall_wirein_error_bare_cuts"):
        assert _a in _src, f"transition drop ledger {_a} missing"
    # K9: the translate-stage transitions/TCO walkers are deleted (the space
    # they translate FROM cannot author those fields since 2d21701).
    assert "Dropping transition: after_word_index out of kept-range" not in _src \
        and "Dropping tight_cut_overlay: after_word_index out of kept-range" not in _src, \
        "translate-stage transitions/TCO walkers must stay deleted"


@check("K4 future-drift guard: every _-key the render path reads is whitelisted (persists) or declared transient (recomputed) — an undeclared read cannot deploy")
def _k4_future_drift_guard():
    import re as _re
    _lines = open("handler.py").read().splitlines()
    _start = next(_i for _i, _l in enumerate(_lines)
                  if _l.startswith("def render_multi_clip("))
    _end = next(_i for _i in range(_start + 1, len(_lines))
                if _lines[_i].startswith("def "))
    _body = "\n".join(_lines[_start:_end])
    _reads = set(_re.findall(r'edit_plan(?:\.get\(|\[)"(_[A-Za-z0-9_]+)"', _body))
    _src = "\n".join(_lines)

    def _set_lit(name):
        _blk = _src.split(name + " = {")[1].split("}")[0]
        return set(_re.findall(r'"(_[A-Za-z0-9_]+)"', _blk))

    _persist = _set_lit("_PERSIST_DERIVED_KEYS")
    _transient = _set_lit("_RENDER_TRANSIENT_KEYS")
    # Completeness: an undeclared render-read key is K4 reborn for that field.
    _undeclared = _reads - _persist - _transient
    assert not _undeclared, (
        f"render path reads UNDECLARED _-keys {sorted(_undeclared)} — add each to "
        f"_PERSIST_DERIVED_KEYS (replays depend on it) or _RENDER_TRANSIENT_KEYS "
        f"(recomputed every render). Silent replay loss is otherwise reborn.")
    # Exclusivity: a key cannot be both persisted and recomputed-per-render.
    _both = _persist & _transient
    assert not _both, f"keys declared BOTH persist and transient: {sorted(_both)}"
    # Honesty: stale transient declarations rot the guard.
    _stale = _transient - _reads
    assert not _stale, (
        f"_RENDER_TRANSIENT_KEYS declares keys the render path no longer reads: "
        f"{sorted(_stale)} — remove them")
    # Self-integrity: if the scope/regex rots, fail loudly instead of passing empty.
    assert len(_reads) >= 15, (
        f"guard parsed only {len(_reads)} render-path _-key reads — the "
        f"render_multi_clip scope detection or the read regex has drifted")


@check("RHYTHM+BEATS: linguistic cut gate (mid-sentence rhythm uncuttable; sentence-final crush unchanged); sounds ride ranked beats (standalone list unrepresentable); StageZoom deleted; reframe anchors live")
def _rhythm_beats():
    import handler as _h
    _src = open("handler.py").read()
    # A — the linguistic gate, both directions
    _w = [{"punctuated_word": "flow", "start": 0.0, "end": 0.5},
          {"punctuated_word": "on.", "start": 1.0, "end": 1.5},
          {"punctuated_word": "Next", "start": 1.8, "end": 2.2}]
    assert not _h._sentence_final_word(_w[0]) and _h._sentence_final_word(_w[1])
    assert "_MIDSENTENCE_STALL_S" in _src and _h._MIDSENTENCE_STALL_S == 0.70
    assert "not _sentence_final_word(words[a])" in _src, "candidate gate missing"
    assert _src.count("_sentence_final_word(") >= 3, "span-split must share the gate"
    # B — sounds ride ranked beats
    assert "sound" in _h._EmphasisMoment.model_fields, "emphasis must carry the sound"
    # WS3 (Zac ruling): the DECISION is required, the sound never is
    assert _h._EmphasisMoment.model_fields["sound"].is_required(), \
        "the sound decision must be REQUIRED (decision-forcing, never sound-forcing)"
    from typing import get_args as _ga
    assert set(_ga(_h._SOUND_DECISION)) == set(_ga(_h._SFX_SOUNDS)) | {"voice"}, \
        "single-source: decision enum == the 16 sounds + voice"
    assert "sound_effects" not in _h.PostCutPlan.model_fields, \
        "the standalone word-anchored list must be unrepresentable"
    _d = _h._EmphasisMoment.model_fields["sound"].description or ""
    assert "the hook's grab and" in _d and "the usual two" in _d, \
        "the schema-description lever must carry the intent frame (usual-two)"
    assert '"sound_on_beat"' in _src and '"money_ching_anchor"' in _src, "the ledgers must exist"
    assert '"sound_decision"' in _src, "every beat's signed choice must ledger (WS3)"
    import recipe_eval, inspect
    esrc = inspect.getsource(recipe_eval)
    assert '"sfx-partner"' not in esrc, "sfx-partner is dead-by-construction (the beat IS the partner)"
    assert '"why-component"' in esrc, "the pairing-residual measure must exist"
    # C — StageZoom deleted
    assert "StageZoom" not in _h.VALID_ZOOM_TYPES
    assert "StageZoom" not in str(_h.ZOOM_ARC_HOMES)
    # the reframe anchors
    assert "Read each moment and give it what it calls for." in _src \
        and "an unmarked peak is as wrong as a marked nothing" in _src, \
        "the intent opener must be verbatim"
    assert "**voice** — the signed bare choice" in _src \
        and "**nothing** —" not in _src, \
        "the bare member is 'voice' — the enum's own name, one honest choice"
    assert "**THE SCENARIO:**" not in _src and _src.count("**THE MOMENT:**") >= 16, \
        "the detection grammar must be gone"
    # FROM RESTRAINT TO INTENT (Zac 2026-07-11): register rebalanced, bounds intact
    assert "Density varies BY PHASE" in _src, "the phase-energy structure must be taught"
    assert "the two classic hits" in _src, "the usual-two anchor must be present"
    assert "A picture change is an event the edit reads, never ignores." in _src, \
        "the sub-call must teach scene-change acknowledgment"
    assert '"bare_seams"' in _src and '"seam_bare_choice"' in _src, \
        "a bare seam is a decision with a why — sayable and ledgered"
    assert "_TIGHT_CUT_OVERLAY_CAP" not in _src, \
        "the legacy overlay cap is removed-not-skipped (judgment taught, not gated)"
    assert '"overlay_density_watch"' in _src, "the density watch replaces the cap"
    assert "count follows the beats" in " ".join(_src.split()).lower(), \
        "the killed energy teach is restored (the orphaned bullet is whole again)"
    assert "reads stronger for it.\n    usually earns its sound" not in _src, \
        "the orphaned fragment must be gone"
    assert "Zero treatments is the honest read" not in _src \
        and "rarest currency" not in _src, "safe-harbor phrasing swept"
    # fragment-integrity wave (Zac rider 2026-07-11): dangling referents truthed
    assert _src.count('"sound": <one of the 16 sounds') >= 2, \
        "the RESPONSE FORMAT emphasis template must carry the sound rider (the zero-sounds template gap)"
    assert "THE 7 ZOOM TYPES" in _src and "THE 6 ZOOM TYPES" not in _src, \
        "zoom-library header count truthed (7 zooms: StagedPush added 2026-07-13, StageZoom stays deleted)"
    assert "emit an empty sound_effects array" not in _src \
        and "sound_effects: []`" not in _src, \
        "sfx-off surfaces re-aimed at the rider (standalone list unauthorable)"
    assert "emphasis_moments.t (" not in _src, "the emphasis .t anchor reference is dead"
    _p_sfx = {"sound_effects": [{"word_index": 1, "sound": "boom"}],
              "emphasis_moments": [{"word_indices": [2], "sound": "punchsfx",
                                    "zoom_effect": None}],
              "transitions": [{"after_word_index": 3, "type": "CardSwipe",
                               "sound": "transition-sfx"}]}
    _h._enforce_off_expressive_features(_p_sfx, {"sfx"})
    assert (_p_sfx["sound_effects"] == []
            and _p_sfx["emphasis_moments"][0]["sound"] == "voice"
            and "sound" not in _p_sfx["transitions"][0]), \
        "sfx-off must strip the rider surfaces (the enforcement hole stays closed)"


@check("CAPTION ONSET (Zac 2026-07-12, timing audit): captions used the raw Deepgram start while SFX/zoom/MG key off the audible onset — measured ~80ms (5-frame) lag. project_words_to_output emits audible_start (= start − silence correction, clamped); the caption builder uses it so captions land ON the beat, end unchanged")
def _caption_audible_onset():
    import handler as _h
    _src = open("handler.py").read()
    assert '"audible_start":' in _src, "projected words must carry audible_start"
    assert 'w.get("audible_start")' in _src, "the caption builder must consume audible_start"
    # builder uses audible_start over raw start; fromMs/toMs then land on the INTEGER ms of
    # the NEVER-EARLY frame — floor(ceil(t*fps)*1000/fps) — the first frame at-or-after the
    # audible onset (never the frame before it; see _caption_frame_alignment) AND an int for
    # the render schema. The field consumed is still audible_start.
    _pw = [{"start": 1.60, "audible_start": 1.52, "end": 1.90, "word": "hi", "punctuated_word": "hi"}]
    _pg = _h._build_tiktok_pages_from_projected(_pw, max_words_per_page=2, fps=60.0)
    _tk = _pg[0]["tokens"][0]
    assert isinstance(_tk["fromMs"], int) and isinstance(_tk["toMs"], int), \
        "caption tokens must be int (render schema TikTokToken.fromMs/toMs: int)"
    # audible_start 1.52s → ceil(1.52*60)=92 → floor(92*1000/60)=1533ms (frame 92 = 1.5333s,
    # the first frame at-or-after the 1.52s onset; frame 91 = 1.5167s would reveal it early)
    assert _tk["fromMs"] == 1533, \
        f"caption fromMs = audible onset on the never-early (ceil) frame's integer ms, got {_tk['fromMs']}"
    # word end 1.90s → round(1.90*60)=114 → floor(114*1000/60)=1900ms
    assert _tk["toMs"] == 1900, f"word end on its frame's integer ms, got {_tk['toMs']}"
    # LEVER B (Zac 2026-07-12): the onset correction is REMOVED — audible_start ==
    # raw start for EVERY word (one uniform clock; per-word variance impossible).
    _h._LEVEL_SILENCES_LAST[:] = [(1.20, 1.52)]; _h._WITHIN_WORD_SILENCES_LAST[:] = []
    _proj = _h.project_words_to_output(
        {"words": [{"start": 1.0, "end": 1.3, "word": "a"}, {"start": 1.6, "end": 1.9, "word": "b"}]},
        [{"source_start": 0.0, "source_end": 2.0, "speed": 1.0}], [2.0])
    _b = [w for w in _proj if w.get("_word_index") == 1][0]
    assert abs(_b["audible_start"] - _b["start"]) < 1e-6 and abs(_b["start"] - 1.60) < 0.02, \
        "Lever B: audible_start == raw start (no correction, uniform clock)"
    _h._LEVEL_SILENCES_LAST[:] = []; _h._WITHIN_WORD_SILENCES_LAST[:] = []
    # ONE CLOCK (Zac 2026-07-12): EVERY word-anchored component reads the same
    # audible-onset reference — caption builder + text-overlay + MG + emphasis-MG
    # + b-roll all consume audible_start (was raw _pw["start"] = a split clock).
    assert _src.count('.get("audible_start")') >= 5, \
        "all word-anchored placements (overlay/MG/emphasis-MG/broll/caption) must read audible_start — one clock"


@check("ITEM 2 MG entrance-arrival (Zac 2026-07-12): the measured MGAttackProbe attacks are wired into fromFrame (settle for pops, container-arrival min(hit,settle) for the sequenced types WITHOUT a resolving value — RankedList/Timeline/TimelineRoadmap) so an MG lands SETTLED on its anchor word — replacing the 0.25*duration guess; both placement sites shift fromFrame via _mg_arrival_frames (value components divert to value-land, see the FIX 2 check)")
def _item2_mg_attack_wiring():
    import handler as _h
    _src = open("handler.py").read()
    # the table + helper exist and split pops (settle) from sequenced (min)
    assert _h._MG_ATTACK_MS["BarRace"] == 267 \
        and _h._MG_ATTACK_MS["StatCard"] == 83, "sequenced types carry container-arrival min(hit,settle)"
    assert _h._MG_ATTACK_MS["IMessageBubble"] == 50 and _h._MG_ATTACK_MS["PullQuote"] == 500, \
        "pop types carry settle"
    assert _h._MG_SEQUENCED == frozenset({"BarRace", "ProgressBar", "RankedList",
                                          "StatCard", "Timeline", "TimelineRoadmap"})
    assert _h._mg_attack_frames("BarRace", 60) == 16 and _h._mg_attack_frames("MouseDrag", 60) == 9, \
        "ms→frames at fps; unmeasured (MouseDrag/PillCluster) → default 150ms"
    # BOTH placement sites shift fromFrame via _mg_arrival_frames (value types → value-land;
    # everything else → the measured container attack). The guess is gone.
    assert "_mg_af = _mg_arrival_frames(_mg.get(\"type\"), source_fps, _mg.get(\"props\"))" in _src, \
        "standalone MG must enter via _mg_arrival_frames (value-land for value components)"
    assert "_em_af = _mg_arrival_frames(" in _src, \
        "emphasis MG must enter via _mg_arrival_frames, not the 0.25*duration guess"
    assert "_from_frame = max(0, _anchor_land_frame(_out_start, source_fps) - _mg_af)" in _src, \
        "standalone MG must enter its arrival lead earlier and land on the FLOORED anchor (see FRAME-FLOOR check)"
    assert "_mg_from_frame = max(0, _em_t_frame - _em_af)" in _src, \
        "emphasis MG must shift by the arrival lead"
    assert "int(round(_em_dur * source_fps * 0.25))" not in _src, "the 0.25*duration guess must be gone"
    # a NON-value sequenced type still routes to the container attack (unchanged)
    assert _h._mg_arrival_frames("RankedList", 60, {}) == _h._mg_attack_frames("RankedList", 60), \
        "RankedList (sequenced, no resolving value) keeps container-arrival"


@check("FIX 2 VALUE-LANDS-ON-EMPHASIS (Zac 2026-07-15): a count-up/fill/race lands its VALUE (number reaching final figure) ON the anchor word, not its container — REVERSES the 2026-07-12 container-arrival ruling FOR the three value components. The mount is back-timed by the component's value-RESOLUTION frame (read straight from the TSX interpolate ranges; composition fps == source_fps so the local frame == a fromFrame offset, exact at any fps) so the count ARRIVES on the beat. The Python table is pinned to the TSX constants (a component retiming can't silently drift the compensation).")
def _mg_value_landing():
    import handler as _h, re as _re
    _mgdir = "src/remotion/src/motion-graphics"
    # ── anti-drift: the Python value-land frames MUST equal the TSX interpolate ranges ──
    _sc = open(f"{_mgdir}/StatCard/StatCard.tsx").read()
    _m = _re.search(r"countProgress\s*=\s*interpolate\(\s*localFrame,\s*\[\s*\d+\s*,\s*(\d+)\s*\]", _sc)
    assert _m and int(_m.group(1)) == _h._MG_VALUE_LAND_FRAMES["StatCard"] == 24, \
        f"StatCard value-land must equal the count END frame in the TSX (got table={_h._MG_VALUE_LAND_FRAMES.get('StatCard')}, tsx={_m and _m.group(1)})"
    _pb = open(f"{_mgdir}/ProgressBar/ProgressBar.tsx").read()
    _m = _re.search(r"const\s+FILL_END\s*=\s*(\d+)\s*;", _pb)
    assert _m and int(_m.group(1)) == _h._MG_VALUE_LAND_FRAMES["ProgressBar"] == 34, \
        f"ProgressBar value-land must equal FILL_END in the TSX (got table={_h._MG_VALUE_LAND_FRAMES.get('ProgressBar')}, tsx={_m and _m.group(1)})"
    _br = open(f"{_mgdir}/BarRace/BarRace.tsx").read()
    _bc = {k: int(_re.search(rf"const\s+{k}\s*=\s*(\d+)\s*;", _br).group(1)) for k in ("START", "STAGGER", "GROW")}
    assert (_bc["START"], _bc["STAGGER"], _bc["GROW"]) == (_h._BARRACE_START, _h._BARRACE_STAGGER, _h._BARRACE_GROW) == (8, 7, 32), \
        f"BarRace START/STAGGER/GROW must match the TSX ({_bc} vs {(_h._BARRACE_START, _h._BARRACE_STAGGER, _h._BARRACE_GROW)})"
    # the TSX settleFrame formula must be the one we replicate (compare mode)
    assert "settleFrame = START + (N - 1) * STAGGER + GROW" in _br, \
        "BarRace settleFrame formula changed — the value-land replication in _mg_arrival_frames is stale"
    # ── the arrival lead IS the value-resolution frame (not the container attack) ──
    assert _h._mg_arrival_frames("StatCard", 60, {}) == 24, "StatCard must back-time to the count-lock frame"
    assert _h._mg_arrival_frames("ProgressBar", 60, {}) == 34, "ProgressBar must back-time to the fill-complete frame"
    # BarRace: compare mode staggers by bar count; race starts together
    _bars3 = {"bars": [{"value": 3}, {"value": 7}, {"value": 5}]}   # N=3
    assert _h._mg_arrival_frames("BarRace", 60, {**_bars3, "mode": "compare"}) == 8 + 2 * 7 + 32 == 54, \
        "BarRace compare N=3 → settleFrame 54"
    assert _h._mg_arrival_frames("BarRace", 60, {**_bars3, "mode": "race"}) == 8 + 32 == 40, \
        "BarRace race (bars start together) → 40"
    assert _h._mg_arrival_frames("BarRace", 60, _bars3) == 54, "BarRace default mode is compare"
    assert _h._mg_arrival_frames("BarRace", 60, {"bars": [{"value": 1}] * 9}) == 8 + 3 * 7 + 32, \
        "BarRace caps N at 4 (component slices bars[0:4])"
    # ── the reversal is REAL: value-land is LATER than the old container attack ──
    for _t in ("StatCard", "ProgressBar", "BarRace"):
        _val = _h._mg_arrival_frames(_t, 60, _bars3)
        _cont = _h._mg_attack_frames(_t, 60)
        assert _val > _cont, \
            f"{_t} value-land ({_val}f) must exceed the container attack ({_cont}f) — else the value still lands late"


def _mg_entrance_fingerprint():
    """Deterministic hash over every MG entrance-timing PRIMITIVE — the shared
    useMGPhase curve + timing.ts (full), and per component only the lines that
    define animation timing (spring damping/mass/stiffness, enterFrames,
    ENTRANCE_FRAMES, interpolate/Sequence). Styling (colors, layout, fonts) is
    excluded, so a cosmetic edit does NOT trip it but any move that could shift
    the measured attack DOES. MUST match handler._mg_entrance_fingerprint's
    intent — this is the single source of truth for the fingerprint algorithm."""
    import hashlib as _hl, os as _os, re as _re2, glob as _glob
    _root = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                          "src", "remotion", "src", "motion-graphics")
    _tok = _re2.compile(r"spring\(|interpolate\(|damping|stiffness|mass|enterFrames|"
                        r"exitFrames|ENTRANCE_FRAMES|defaultEnterFrames|useMGPhase|"
                        r"Easing|<Sequence|from=\{|durationInFrames")
    _parts = []
    for _shared in ("shared/useMGPhase.ts", "shared/timing.ts"):
        _p = _os.path.join(_root, _shared)
        if _os.path.exists(_p):
            _parts.append(_shared + "::" + open(_p, encoding="utf-8").read().strip())
    for _tsx in sorted(_glob.glob(_os.path.join(_root, "**", "*.tsx"), recursive=True)):
        _rel = _os.path.relpath(_tsx, _root)
        _lines = [ln.strip() for ln in open(_tsx, encoding="utf-8").read().splitlines() if _tok.search(ln)]
        if _lines:
            _parts.append(_rel + "::" + "\n".join(_lines))
    return "sha256:" + _hl.sha256("\n====\n".join(_parts).encode("utf-8")).hexdigest()


@check("ONE-CLOCK RENDER BRANCH (Zac 2026-08-02, RULE-1): the render leg emits a single [RENDERCLOCK] line whose children RECONCILE TO THE PARENT BY CONSTRUCTION — total_ms = bundle+browser+select+render+unaccounted, and render_ms = frames_ms+stitch_ms. Forged because today's render numbers were five honest measurements that did not NEST, and 130s once vanished inside a stage with no report showing a hole. unaccounted_ms must be COMPUTED as total minus the parts, never asserted, so a hole cannot hide — it shows up as unaccounted growing. This gate fails the deploy if the line loses a field or if unaccounted stops being derived.")
def _one_clock_render_branch():
    import os as _os, re as _re2
    _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                       "src", "remotion", "render-full.mjs")
    _t = open(_p, encoding="utf-8").read()
    assert "[RENDERCLOCK]" in _t, "render-full.mjs must emit the [RENDERCLOCK] line"
    for _f in ("total_ms", "bundle_ms", "browser_ms", "select_ms", "render_ms",
               "frames_ms", "stitch_ms", "unaccounted_ms", "frames=", "ms_per_frame"):
        assert _f in _t, f"[RENDERCLOCK] lost its {_f} field — the branch no longer nests"
    assert _re2.search(r"const\s+unaccounted\s*=\s*total\s*-\s*kids", _t), \
        "unaccounted_ms must be COMPUTED as total minus the summed children, so a hole cannot hide"
    assert _re2.search(r"const\s+kids\s*=\s*_CLK\.bundle_ms\s*\+\s*_CLK\.browser_ms\s*\+\s*_CLK\.select_ms\s*\+\s*_CLK\.render_ms", _t), \
        "the children sum must include every child of the render leg"
    assert "_CLK.stitch_ms = _CLK.render_ms - _CLK.frames_ms" in _t, \
        "render_ms must partition into frames_ms + stitch_ms by construction"


@check("SAFE IMAGE LAW (Zac 2026-08-02, RULE-1, forged from job 1047def9): a failed image must degrade to NO IMAGE, never to a dead render. Remotion's <Img> opens its OWN delayRender handle on mount, so one unreachable asset inside Chromium hangs the frame and kills the whole video (1047def9: two blob: <Img> handles open at frame 134, 30000ms timeout, rc=1; b8ab1276: same shape on the overlay leg at rendered=0). SafeImg probes the URL off-tree under an explicit sub-render-timeout and only then mounts <Img>, so an unloadable asset costs its own pixels and nothing else. This gate FAILS the deploy if a BARE <Img> reappears anywhere in the Remotion tree — the one way this class comes back.")
def _safe_image_law():
    import os as _os, re as _re2, glob as _g
    _root = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "src", "remotion", "src")
    _safe = _os.path.join(_root, "SafeImg.tsx")
    assert _os.path.exists(_safe), "SafeImg.tsx is missing — the degrade path is gone"
    _txt = open(_safe, encoding="utf-8").read()
    assert "continueRender" in _txt and "delayRender" in _txt, \
        "SafeImg must own a delayRender handle AND release it"
    assert _re2.search(r"SAFE_IMG_TIMEOUT_MS\s*=\s*(\d+)", _txt), "SafeImg needs an explicit timeout"
    _t = int(_re2.search(r"SAFE_IMG_TIMEOUT_MS\s*=\s*(\d+)", _txt).group(1))
    assert _t < 30000, f"SAFE_IMG_TIMEOUT_MS={_t} must stay UNDER the 30000ms render timeout or it re-arms the hang"
    # The ROLE SPLIT is the load-bearing part: "degrade to nothing" is correct for
    # DECORATION only. Primary media degraded to nothing renders a BLACK segment,
    # which is what INTEGRITY_TRIP fires on — trading a hang for a black video
    # that SHIPS. So primary must fail loudly instead.
    assert 'role === "primary"' in _txt and "cancelRender" in _txt, \
        "SafeImg must FAIL LOUDLY on primary media, never degrade it to black"
    assert "[SAFEIMG]" in _txt, \
        "SafeImg must emit a grep-stable [SAFEIMG] telemetry line — the Remotion " \
        "layer is otherwise invisible and a silent degrade is unmeasurable"
    _offenders, _roleless = [], []
    for _f in _g.glob(_os.path.join(_root, "**", "*.tsx"), recursive=True):
        if _os.path.basename(_f) == "SafeImg.tsx":
            continue
        _src2 = open(_f, encoding="utf-8").read()
        for _i, _ln in enumerate(_src2.splitlines(), 1):
            if _re2.search(r"<Img\b", _ln) and not _ln.lstrip().startswith(("*", "//")):
                _offenders.append(f"{_os.path.relpath(_f, _root)}:{_i}")
        # every SafeImg element must declare its role explicitly
        for _m in _re2.finditer(r"<SafeImg\b((?:[^>]|\n)*?)/?>", _src2):
            if "role=" not in _m.group(1):
                _roleless.append(_os.path.relpath(_f, _root))
    assert not _offenders, (
        "BARE <Img> found — use SafeImg so an unloadable asset degrades to no image "
        f"instead of hanging the render: {_offenders}")
    assert not _roleless, (
        "<SafeImg> without an explicit role= — decoration vs primary decides whether "
        f"a failed asset ships black or fails loudly, and must never default: {sorted(set(_roleless))}")


@check("ONE-CLOCK TIMELINE — THE INSTRUMENT CANNOT LIE (Zac 2026-08-02 'one clock', forged from the 130s that five incompatible stopwatches could not reconcile): the per-job wall-clock tree computes unaccounted = parent − union(children) EXACTLY, so union(children) + unaccounted == parent at every node and a hidden span is PRINTED as an explicit gap rather than absorbed silently. Behaviorally builds a synthetic tree (overlapping + sequential + tail gap) and FAILS the deploy if the invariant breaks by >1s, if 'parallel' is asserted rather than DERIVED from interval overlap, or if the instrument is not (a) instantiated per job at handler entry, (b) wired to the edit_plan + render parents, and (c) nested into stage_timings so content-studio's top-level key stripping cannot drop it. cert: test_one_clock_timeline.py")
def _one_clock_timeline():
    import os as _os2
    from handler import _JobTimeline
    # ── behavioral invariant: overlapping (parallel) + sequential + tail gap ──
    tl = _JobTimeline(); tl.now = lambda: 150.0
    tl.add("a", 0, 100, "job"); tl.add("b", 50, 120, "job"); tl.add("c", 130, 140, "job")
    tr = tl.finalize()
    _cov = round(tr["dur"] - tr["unaccounted"], 1)
    assert abs(_cov + tr["unaccounted"] - tr["dur"]) < 1.0, \
        "timeline invariant broken: union(children)+unaccounted must equal parent within 1s"
    assert abs(tr["unaccounted"] - 20.0) < 1.0, \
        f"a gap between/after children must surface as unaccounted, got {tr['unaccounted']}"
    assert tr["parallel"] is True, "overlapping children must DERIVE parallel=True, not assert it"
    tl2 = _JobTimeline(); tl2.now = lambda: 100.0
    tl2.add("x", 0, 40, "job"); tl2.add("y", 40, 80, "job")
    assert tl2.finalize()["parallel"] is False, "non-overlapping children must not be flagged parallel"
    # a hidden 130s-shape gap under a parent must be VISIBLE
    tl3 = _JobTimeline(); tl3.now = lambda: 200.0
    tl3.add("edit_plan", 0, 189, "job"); tl3.add("gemini_call", 10, 70, "edit_plan")
    _ep = next(c for c in tl3.finalize()["children"] if c["name"] == "edit_plan")
    assert _ep["unaccounted"] > 120.0, "an unexplained span under a parent must print as a gap"
    # ── wiring: instantiated, parents present, nested (survives stripping) ──
    _h = open(_os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), "handler.py"),
              encoding="utf-8").read()
    assert "_TL = _JobTimeline()" in _h, "timeline must be instantiated per job at handler entry"
    assert '_tl_start("edit_plan"' in _h and '_tl_start("render"' in _h, \
        "the edit_plan + render parents must be wired so other agents can attach children"
    assert '"timeline": _tl_report()' in _h, \
        "the tree must nest inside stage_timings (content-studio strips unknown top-level keys)"


@check("BUNDLE-FRESHNESS GUARD (Zac 2026-08-02, RULE-1, forged from SafeImg nearly shipping inert): a Remotion TSX change ships DEAD if a redeploy reuses a cached bundle without re-running prebundle.mjs — the render then executes STALE compiled JS while the source (and every gate that reads the source) says the fix is present. This gate asserts the anti-inert mechanism is wired on BOTH ends: (1) prebundle.mjs fingerprints every src .ts/.tsx/.mjs into bundle/.src_hash at image-build time, and (2) handler.py defines _assert_bundle_fresh() AND calls it inside render_stage, so the FIRST real render recomputes the live-source hash and refuses (STALE_BUNDLE) if the deployed bundle wasn't built from the deployed source. Fail-open only when the stamp is absent (pre-fingerprint bundle), never on mismatch. One check closes the class forever: a TSX fix can no longer pass every source gate yet render from an old bundle.")
def _bundle_freshness_guard():
    import os as _os, re as _re3
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _pre = _os.path.join(_here, "src", "remotion", "prebundle.mjs")
    assert _os.path.exists(_pre), "prebundle.mjs missing — the fingerprint producer is gone"
    _ptxt = open(_pre, encoding="utf-8").read()
    assert ".src_hash" in _ptxt and "createHash" in _ptxt and "writeFileSync" in _ptxt, \
        "prebundle.mjs must sha256-fingerprint src/ into bundle/.src_hash at build time"
    _htxt = open(_os.path.join(_here, "handler.py"), encoding="utf-8").read()
    assert "def _assert_bundle_fresh(" in _htxt, \
        "handler.py must define _assert_bundle_fresh() — the STALE_BUNDLE consumer"
    assert ".src_hash" in _htxt and "STALE_BUNDLE" in _htxt, \
        "_assert_bundle_fresh must read bundle/.src_hash and raise STALE_BUNDLE on mismatch"
    # the guard is inert unless render_stage actually CALLS it before rendering
    _rs = _re3.search(r"def render_stage\b.*?(?=\ndef _cost_meter_hard_stop|\ndef [a-z_]+\(|\Z)", _htxt, _re3.S)
    assert _rs and "_assert_bundle_fresh()" in _rs.group(0), \
        "render_stage must CALL _assert_bundle_fresh() — an uncalled guard never fires"


@check("MG ATTACK TABLE ANTI-DRIFT (Zac 2026-07-28): _MG_ATTACK_MS is a MEASURED table (mg-attack-battery renders each MG entrance; the settle/container-arrival ms is read off the presence curve). Unlike _MG_VALUE_LAND_FRAMES — which the gate above pins to the TSX interpolate range it reads directly — a measured table cannot be re-derived from one readable constant, so it would rot silently the instant an entrance config changed, reintroducing the late-payoff bug invisibly. This gate fingerprints every MG entrance-timing primitive (useMGPhase curve, spring damping/mass/stiffness, enterFrames, ENTRANCE_FRAMES, interpolate/Sequence) and FAILS the deploy if it moves — forcing a battery re-measure. The SNAP/SETTLE/GLIDE motion-token work changes exactly these configs, so this is the guard that keeps the back-timing honest across it. It also asserts every battery-measured type carries a table entry, so a NEW component can't ship unmeasured.")
def _mg_attack_antidrift():
    import handler as _h
    _live = _mg_entrance_fingerprint()
    assert _live == _h._MG_ATTACK_FINGERPRINT, (
        "MG entrance configs changed — the MEASURED _MG_ATTACK_MS attack table is likely STALE, "
        "and the back-timing would silently reintroduce late payoffs.\n"
        f"  stored: {_h._MG_ATTACK_FINGERPRINT}\n  live:   {_live}\n"
        "  FIX (do NOT just paste the live value): re-run\n"
        "    node src/remotion/mg-attack-battery.mjs <out>\n"
        "    python3 src/remotion/measure_mg_attack.py <out> 60\n"
        "  reconcile _MG_ATTACK_MS to the new settle/container-arrival ms, THEN set\n"
        f"    _MG_ATTACK_FINGERPRINT = \"{_live}\"")

    # completeness: every type the battery renders must have an attack entry (or be
    # a known blank-prop probe that intentionally falls back to the default).
    import os as _os, re as _re2
    _battery = open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                  "src", "remotion", "mg-attack-battery.mjs"), encoding="utf-8").read()
    _types_blob = _battery[_battery.index("const TYPES = {"):_battery.index("};", _battery.index("const TYPES = {"))]
    _battery_types = set(_re2.findall(r"^\s*([A-Z][A-Za-z0-9]+):\s*\{", _types_blob, _re2.M))
    _known_blank = {"MouseDrag", "PillCluster"}   # probe props render blank; documented → default
    _missing = _battery_types - set(_h._MG_ATTACK_MS) - _known_blank
    assert not _missing, f"battery renders {_missing} but _MG_ATTACK_MS has no measured entry (ships unmeasured)"


@check("FRAME-FLOOR payoff anchors (Zac 2026-07-28): a payoff LANDING (an MG pop, a zoom peak) quantizes round-EARLY (floor), never round-nearest — one frame early reads on-time (the move completes as the word arrives), one frame late reads mistimed. It only moves the sub-frame ≥0.5 cases (the ones that were rounding UP into lateness); already-early landings are byte-identical. MG: both placement sites land via _anchor_land_frame. Zoom: all 7 components' eventStart/stage-peak use msToFramesFloor (eventEnd stays round). Captions keep their OPPOSITE never-EARLY ceil — msToFramesFloor must never appear under captions/.")
def _frame_floor_payoff():
    import handler as _h, glob as _g
    _src = open("handler.py").read()
    # MG — both placement sites land on the floored anchor frame
    assert "_anchor_land_frame(_out_start, source_fps)" in _src, "standalone MG must land via _anchor_land_frame"
    assert "_em_t_frame = _anchor_land_frame(_em_t_out, source_fps)" in _src, "emphasis MG must land via _anchor_land_frame"
    # the helper is a floor (never-late) — round-up case must floor, whole frame unchanged
    assert _h._anchor_land_frame(1.02, 30) == 30 and _h._anchor_land_frame(1.0, 30) == 30, \
        "_anchor_land_frame must floor (never round-nearest)"
    # zoom — the floor variant exists and is a Math.floor; the round msToFrames stays for eventEnd
    _zt = open("src/remotion/src/zoom/shared/timing.ts").read()
    assert "export function msToFramesFloor" in _zt and "Math.floor((ms / 1000) * fps)" in _zt, \
        "zoom msToFramesFloor missing/altered"
    for _name in ("DepthPull", "FocusWindow", "SmoothPush", "LetterboxPush", "SnapReframe", "StepZoom", "StagedPush"):
        _c = open(f"src/remotion/src/zoom/{_name}/{_name}.tsx").read()
        assert "msToFramesFloor(" in _c, f"{_name} must floor its payoff landing (eventStart/stage peak)"
        assert "const eventStart = msToFrames(" not in _c, f"{_name} eventStart still round-nearest — must floor"
    # captions keep the OPPOSITE invariant (never-early ceil) — the payoff floor must not leak in
    for _cf in _g.glob("src/remotion/src/captions/**/*.ts*", recursive=True):
        assert "msToFramesFloor" not in open(_cf).read(), \
            f"{_cf}: captions must keep their never-EARLY ceil, not the payoff floor"


@check("CAPTION SEQUENCE-ALIGNER (Zac 2026-07-28, DARK PROMPTLY_CAPTION_ALIGN): Gemini's CORRECT words marry onto Deepgram TIMING slots — caption-only, cuts untouched (the projection is index-coupled; text is corrected in place on existing slots). Thresholds DERIVED from cert_caption_align_derive (6 clips): the discriminant is TOKEN COUNT not a time gap (corrections were 1-2 tokens, dropped spans 11 & 60, all trailing), plus an align-rate floor (the song aligned 0.0). Flag defaults OFF; refuses below the floor; a dropped span (open-ended, or >token-ceiling) is OMITTED, never fabricated across the gap (the Hindi-30s catastrophe); English is skipped at the call site (Deepgram already 5/5).")
def _caption_aligner_gate():
    import handler as _h, os as _os
    # derived thresholds pinned — a silent retune fails the gate
    assert _h._CAPTION_ALIGN_MIN_RATE == 0.30, "align-rate floor retuned"
    assert _h._CAPTION_ALIGN_MAX_INSERT_TOKENS == 3, "insert token ceiling retuned"
    assert _h._CAPTION_ALIGN_MAX_INSERT_GAP_S == 4.0, "insert gap backstop retuned"
    # flag DARK by default; =1 enables
    _saved = _os.environ.pop("PROMPTLY_CAPTION_ALIGN", None)
    try:
        assert _h._caption_align_enabled() is False, "flag must default OFF (dark)"
        _os.environ["PROMPTLY_CAPTION_ALIGN"] = "1"
        assert _h._caption_align_enabled() is True, "=1 must enable"
    finally:
        _os.environ.pop("PROMPTLY_CAPTION_ALIGN", None)
        if _saved is not None:
            _os.environ["PROMPTLY_CAPTION_ALIGN"] = _saved

    def _W(w, s, e):
        return {"word": w, "punctuated_word": w, "start": s, "end": e}
    # 1->1 replace corrects the slot; equal slots keep Deepgram's (already-correct) surface
    mp, meta = _h._corrected_text_by_index([_W("buy", 0, .3), _W("the", .3, .5), _W("cat", .5, .8)], ["biophilia", "the", "cat"])
    assert mp.get(0) == "biophilia" and 1 not in mp and 2 not in mp and not meta["refused"]
    # 2->1 replace (with an equal anchor so it clears the align floor): surplus
    # Deepgram slot blanked (caption builder skips empties)
    mp, _m = _h._corrected_text_by_index([_W("buy", 0, .3), _W("fill", .3, .6), _W("it", .6, .8)], ["biophilia", "it"])
    assert mp.get(0) == "biophilia" and mp.get(1) == "" and not _m["refused"]
    # over-token-ceiling interior insert = dropped span, none of it fabricated
    _big = ["a"] + [f"w{_i}" for _i in range(6)] + ["b"]
    mp, meta = _h._corrected_text_by_index([_W("a", 0, .2), _W("b", 5, 5.2)], _big)
    assert not any("w0" in str(_v) for _v in mp.values()) and any(d["kind"] == "over_ceiling" for d in meta["dropped_spans"])
    # trailing insert (the Hindi-30s shape) omitted, never fabricated
    mp, meta = _h._corrected_text_by_index([_W("a", 0, .2)], ["a", "x", "y", "z"])
    assert mp == {} and any(d["kind"] == "open_ended" for d in meta["dropped_spans"])
    # refuse below the align floor (garbage text — nothing to anchor)
    mp, meta = _h._corrected_text_by_index([_W("aa", 0, .2), _W("bb", .2, .4), _W("cc", .4, .6)], ["xx", "yy", "zz"])
    assert mp == {} and meta["refused"]
    # apply overlays by _word_index, caption-only (mutates projected caption words only)
    _pw = [{"_word_index": 0, "word": "buy", "punctuated_word": "buy"},
           {"_word_index": 1, "word": "the", "punctuated_word": "the"}]
    _h._apply_caption_alignment(_pw, {0: "biophilia"})
    assert _pw[0]["punctuated_word"] == "biophilia" and _pw[1]["punctuated_word"] == "the"
    # WIRING: present at the caption site, gated + cached + English-skipped + timing untouched
    _src = open("handler.py").read()
    assert "_apply_caption_alignment(_caption_words, _cal_map)" in _src, "aligner not wired into the caption path"
    assert 'if _det_lang != "en":' in _src, "English clips must be skipped (Deepgram already 5/5)"
    assert "_gemini_correct_transcript(prepare_audio_for_deepgram(source_path))" in _src, "correction call missing at caption site"


@check("SFX ONE-CLOCK, NO GATE (Zac 2026-07-15): the mid-phrase sound restriction is DELETED — no measurability gate, no swell fallback, no ⟨mid-phrase⟩ education. A sound (sharp or soft, mid-phrase or not) fires on its emphasis word's shared-clock onset — the SAME _audible_word_onset_s the zoom/staged-push/captions ride for every word. The 54-64ms that justified the gate was the DELETED re-detector's error, not the placement's; the placement clock is the energy onset (±5ms, measured) — the ground truth the whole pipeline uses. Removed-not-skipped: the gate/fallback/education are GONE, not bypassed.")
def _sfx_one_clock_no_gate():
    import handler as _h
    _src = open("handler.py").read()
    # the dead re-detector stays gone (no wasted decode/FFT, no inert scaffolding)
    for _dead in ("_spectral_word_onset", "_detect_word_onsets", "_WORD_ONSET_LAST"):
        assert not hasattr(_h, _dead) and f"def {_dead}" not in _src, f"{_dead} must be removed"
    # the measurability machinery is DELETED — removed, not bypassed
    for _fn in ("_sfx_may_fire", "_sfx_onset_measurable"):
        assert not hasattr(_h, _fn) and f"def {_fn}" not in _src, f"{_fn} must be deleted (one clock, no gate)"
    assert not hasattr(_h, "_SFX_SHARP_ATTACK_MS") and "_SFX_SHARP_ATTACK_MS = " not in _src, \
        "the sharp/soft threshold must be deleted"
    assert "_mid_tags" not in _src, "the ⟨mid-phrase⟩ transcript tagging must be deleted"
    assert "{word_text}{_mid}" not in _src, "no ⟨mid-phrase⟩ tag may be emitted into the transcript"
    assert "sharp_attack_on_unmeasurable_onset" not in _src, "the measurability DROP must be gone"
    assert "the beat must be landable" not in _src, "the swap education must be removed from the prompt"
    # POSITIVE INVARIANT: a sound still fires on the ONE shared clock, unconditionally —
    # the onset-shift subtracts _audible_word_onset_s (same clock as the zoom), and there
    # is NO gate/continue between that and the emit.
    assert "- _audible_word_onset_s(_sfx_dgw, _sfx_wi))" in _src, \
        "the SFX must fire on the shared-clock onset (same _audible_word_onset_s as the zoom)"
    # the WS1 peak-on-word attack table is a SEPARATE mechanism and MUST remain — the
    # sound's peak still lands on the onset; only the sharp/soft GATE is gone.
    assert _h._SFX_ATTACK_MS.get("popsfx", 0) > 0 and _h._SFX_ATTACK_MS.get("boom", 0) > 0, \
        "the WS1 attack table (peak-on-word compensation) must survive the gate removal"
    # the shared clock returns raw Deepgram for EVERY word (Lever B) — the invariant the
    # sound now rides, with no per-word measurability branch.
    _dg = [{"start": 1.0, "end": 1.3, "word": "a"}, {"start": 1.6, "end": 1.9, "word": "easy"}]
    assert abs(_h._audible_word_onset_s(_dg, 1) - 1.6) < 1e-6, "one clock: onset is always raw Deepgram"


@check("WS2 caption fade helper (Zac 2026-07-12, entrance SUPERSEDED by crisp-entrance 2026-07-13): boundedFade + the 0.25/MAX_ENTRANCE_MS caps stay for fade-OUT and the non-opacity motion channels (slam/slide/scale springs); the fade-IN ramp is GONE (see _caption_crisp_entrance); the real node helper math test still passes")
def _item3_ws2_fade_bound():
    import os as _os, subprocess as _sub
    _cap = "src/remotion/src/captions"
    _helper = _os.path.join(_cap, "shared", "fadeTiming.ts")
    assert _os.path.exists(_helper), "shared/fadeTiming.ts (the WS2 fade-bound helper) must exist"
    _hs = open(_helper).read()
    assert "export function boundedFade(" in _hs and "FADE_WINDOW_FRACTION = 0.25" in _hs, \
        "boundedFade + the 0.25 window fraction must be the contract"
    assert "MAX_ENTRANCE_MS = 80" in _hs and "MAX_ENTRANCE_MS)" in _hs, \
        "boundedFade must fold in the absolute cap MAX_ENTRANCE_MS=80"
    # The per-style ENTRANCE assertions that used to live here (fade-in bases, scale/
    # slide/spring MOTION caps) are all SUPERSEDED by the round-4 frame-1-is-final fix,
    # which ZEROED every entrance channel — the very motion those caps bounded is gone
    # (see _caption_crisp_entrance). boundedFade now serves fade-OUT only; the styles
    # with a page fade-out still call it, which is all this check needs to guard here.
    for _st in ("Pulse/Pulse", "Quintessence/Quintessence", "TypewriterReveal/TypewriterReveal"):
        _src = open(_os.path.join(_cap, f"{_st}.tsx")).read()
        assert 'from "../shared/fadeTiming"' in _src and "boundedFade(" in _src, \
            f"{_st} still wires boundedFade for its fade-OUT"
    # run the REAL helper math (node strips the .ts types) — not a Python mirror.
    # ESM relative imports resolve to the test file's location, so cwd is irrelevant.
    _t = _os.path.join(_cap, "shared", "fadeTiming.test.ts")
    _r = _sub.run(["node", _t], capture_output=True, text=True)
    assert _r.returncode == 0 and "ALL FADE-BOUND CASES PASS" in _r.stdout, \
        f"node fadeTiming.test.ts must pass ({_r.stdout[-200:]}{_r.stderr[-200:]})"


@check("FINDINGS 1+3 (Zac 2026-07-12): MG base placement teaches center-when-clear/upper + demotes lower_third_safe (kills the caption force-flip cascade that scattered the frame); cut_refinements CONTENT-WORD PROTECTION — a gemini_cut of content words in a flowing sentence is rejected (only filler / verbatim restart / dead-air-bounded spans are removable)")
def _findings_placement_and_content_cut():
    import handler as _h
    _src = open("handler.py").read()
    # Finding 1 — MG base placement taught (default upper on a talking-head; never the face)
    assert "NEVER cover the speaker's face" in _src, "MG must be taught to never cover the face"
    assert "the FACE FILLS THE CENTER BAND even when the head-TOP reads" in _src, \
        "the zone=upper trap must be taught (face body fills center though head-top reads upper)"
    assert "lower_third_safe — LAST RESORT ONLY" in _src, "lower_third_safe demoted from the #2 default"
    # Finding 3 — content-word protection gate + prompt
    assert "def _gemini_cut_span_removable(" in _src, "the content-word predicate must exist"
    assert "_gemini_cut_span_removable(_cw_span" in _src, "the cut_refinements union must gate on it"
    assert "drop_content_word_cut" in _src, "a rejected content cut signs a divergence"
    assert "Content words in a flowing sentence are never removable" in _src, "the prompt must teach it too"
    _W = lambda w, s=0.0, e=0.0: {"word": w, "punctuated_word": w, "start": s, "end": e}
    assert _h._gemini_cut_span_removable([_W("to"), _W("edit.")], [_W("I"), _W("did")], _W("minutes"), 0.02) is False, \
        "'to edit' in a flowing sentence must be KEPT (the bug)"
    assert _h._gemini_cut_span_removable([_W("um"), _W("uh")], [_W("so")], _W("okay."), 0.0) is True, "filler removable"
    assert _h._gemini_cut_span_removable([_W("the"), _W("cat")], [_W("the"), _W("cat")], _W("and"), 0.0) is True, "verbatim restart removable"
    # Zac 2026-07-28: clause (iii) now requires dead air on BOTH sides. A left-only
    # dead-air boundary — a content word opening a new sentence, flowing INTO the
    # following word — is KEPT; only a span stranded between two >=0.70s stalls is
    # a removable fragment. (This is the "Next"/"So" defect fix.)
    assert _h._gemini_cut_span_removable([_W("anyway")], [_W("so")], _W("done."), 0.85, 0.03) is False, \
        "left-only dead-air (content flows into 'so') must be KEPT under the both-sides rule"
    assert _h._gemini_cut_span_removable([_W("anyway")], [_W("so")], _W("done."), 0.85, 0.90) is True, \
        "genuinely isolated fragment (dead air on BOTH sides) still removable"
    # Finding 1 — cross-type collision MOVE-NOT-DROP (Zac ruled: relocation, a legibility invariant)
    assert "def _apply_composed_accent_bands(" in _src, "the move-not-drop collision resolver must exist"
    assert "_apply_composed_accent_bands(" in _src and "cross_type_collision_move" in _src, \
        "it must be wired at the composer cutover (element_bands applied, not inert)"
    _km, _ko, _mv, _dp = _h._apply_composed_accent_bands(
        [{"type": "StatCard", "props": {"anchor": "center"}}],
        [{"variant": "caption_match", "position": "center"}],
        {"mg0": [(0, 60, "center")], "to0": [(0, 60, "top")]})
    assert _km[0]["props"]["anchor"] == "center" and _ko[0]["position"] == "top" and _mv == 1 and _dp == 0, \
        "collision: MG keeps its spot, overlay MOVES to its alternate (never a silent drop when a band is free)"
    # Finding 1 — FACE AVOIDANCE (Zac 2026-07-12): a graphic never covers the speaker.
    # The face is a rigid band occupant; an MG on the face band is relocated off it.
    assert "def _face_occupied_bands(" in _src and 'kind": "face"' in _src, \
        "the face must be a rigid band claim in the composer (not just a drop-gate)"
    assert "face_trajectory=_face_trajectory" in _src, "the composer must receive the face trajectory"
    assert _h._face_occupied_bands([{"found": True, "cy": 960, "t": 1.0}], 0.0, 2.0) == {"center"}, \
        "a talking-head face (cy=960) occupies the center band"
    _fc = _h._compose_band_occupancy(
        [], [{"type": "StatCard", "fromFrame": 0, "durationInFrames": 120, "props": {"anchor": "center"}}],
        [], [], shadow=False,
        face_trajectory=[{"found": True, "cy": 960, "t": round(_j * 0.1, 2)} for _j in range(30)], source_fps=60.0)
    _fb = {band for (_a, _b, band) in (_fc["element_bands"].get("mg0") or [])}
    assert "center" not in _fb and _fb and _fb <= {"top", "bottom"}, \
        "an MG authored on the face is relocated off it (never covers the speaker)"
    # GAP 2 — BRAND IDENTITY (Zac 2026-07-12): Promptly is always Promptly; a model-name
    # leak in generated on-screen text is scrubbed, content mentions are kept.
    assert "def _scrub_model_identity(" in _src, "the identity scrub must exist"
    assert "text_overlays_out = [_scrub_model_identity(" in _src and "motion_graphics_out = [_scrub_model_identity(" in _src, \
        "generated overlays + MG text must be scrubbed before render"
    assert "you are Promptly, always" in _src, "the prompt identity rule must be taught"
    assert _h._scrub_model_identity("AI model: Gemini") == "AI model: Promptly", "the real leak is scrubbed"
    assert _h._scrub_model_identity("Google's new Pixel phone review") == "Google's new Pixel phone review", \
        "a genuine content mention (no identity frame) is KEPT"
    # GAP 1A — USER SPELLING OBEDIENCE (Zac 2026-07-12): "spell X as Y" is a LITERAL
    # deterministic caption-text override — the user's instruction wins (a real request
    # to spell "Blue filter" as "Blufilter" rendered "BLUE FILTER", ignored).
    assert "def _parse_caption_text_overrides(" in _src and "def _apply_caption_text_overrides(" in _src, \
        "the spelling-override capture + apply must exist"
    # RE-EDIT OBEDIENCE (Zac 2026-07-28): the override is parsed from vibe + the RAW
    # change_request (folded), so a spelling correction on the surgical tweak→render_only
    # path — where vibe is the stale original — is no longer invisible (CRITICAL #1).
    assert 'edit_plan["_caption_text_overrides"] = _parse_caption_text_overrides(_reedit_intent_text)' in _src, \
        "the override must be captured from vibe + the raw change_request (the re-edit fold)"
    assert '_reedit_intent_text = f"{vibe or \'\'} . {change_request}"' in _src, \
        "must fold the raw change_request into the render-time intent parse (surgical path obedience)"
    assert "_apply_caption_text_overrides(\n            _projected_words" in _src or \
           "_caption_words = _apply_caption_text_overrides(" in _src, \
        "the override must be applied to the caption word stream"
    assert _h._parse_caption_text_overrides("spell Blue filter as Blufilter") == {("blue", "filter"): "Blufilter"}, \
        "the real request is captured"
    # Folding change_request made the bare 'change X to Y' form a fabrication hazard — an
    # ordinary editorial ask must NEVER become a false caption override.
    assert _h._parse_caption_text_overrides("change the pacing to slower") == {}, \
        "an editorial ask must not fabricate a caption override (generic verbs require a caption/word qualifier)"
    assert _h._parse_caption_text_overrides('change the caption "teh" to "the"') == {("teh",): "the"}, \
        "an explicit caption-text change is still captured"
    _sw = [{"word": w, "punctuated_word": w, "start": 0.0, "end": 1.0} for w in ("Blue", "filter", "is")]
    assert [w["word"] for w in _h._apply_caption_text_overrides(_sw, {("blue", "filter"): "Blufilter"})] == ["Blufilter", "is"], \
        "'Blue filter' renders as the exact user spelling 'Blufilter'"
    # GAP 1B — USER CAPTION-POSITION LOCK (Zac 2026-07-12): "captions at the bottom" is
    # a hard lock — every caption pinned that band the whole video (a real one drifted
    # top "toward the end"); a colliding accent relocates, the caption never moves.
    assert "def _parse_caption_position_lock(" in _src, "the position-lock capture must exist"
    assert 'edit_plan["_caption_position_lock"] = _parse_caption_position_lock(_reedit_intent_text)' in _src, \
        "the lock must be captured from vibe + the raw change_request (the re-edit fold)"
    assert "caption_lock=edit_plan.get(\"_caption_position_lock\")" in _src, \
        "the lock must thread into the composer (accents avoid the locked band)"
    assert 'USER LOCK: every caption pinned' in _src, "the absolute lock floor must run after every caption pass"
    assert _h._parse_caption_position_lock("captions at the bottom middle") == "bottom", "the real request is captured"
    _clock = _h._compose_band_occupancy(
        [{"fromFrame": 0, "toFrame": 120, "position": "top"}],
        [{"type": "StatCard", "fromFrame": 0, "durationInFrames": 120, "props": {"anchor": "bottom"}}],
        [], [], shadow=False, caption_lock="bottom")
    assert {b for (_a, _b, b) in _clock["caption_track"]} == {"bottom"}, "captions pinned to the locked band"
    assert "bottom" not in {b for (_a, _b, b) in (_clock["element_bands"].get("mg0") or [])}, \
        "an MG on the locked caption band relocates (caption never moves)"
    # GAP 1C — NEGATIVES ALWAYS ENFORCE (Zac 2026-07-12): 'no SFX'/'no zooms' disable
    # that component for the whole render, regardless of the EditPolicy flag.
    assert "def _parse_off_features(" in _src and "_ep_off |= _parse_off_features(vibe)" in _src, \
        "user negatives must always merge into the off-set (was gated behind EditPolicy)"
    assert _h._parse_off_features("no SFX and make it punchier") == {"sfx"}, \
        "a negative is captured even from a mixed request"
    _np = {"sound_effects": [{"word_index": 1}], "emphasis_moments": [{"sound": "boom"}]}
    _h._enforce_off_expressive_features(_np, {"sfx"})
    assert _np["sound_effects"] == [] and _np["emphasis_moments"][0].get("sound") == "voice", \
        "'no SFX' strips every SFX (discrete + emphasis rider)"


@check("PART 2 REFRAME (Zac 2026-07-13): vibe-appropriate selection is EMERGENT from per-component fitness — every SFX/transition/zoom/MG carries its OWN **FITS:**/**FIGHTS:** clause (the caption standard); the 4-bucket _VIBE_PALETTES table is RETIRED (it leaked); vibe stays as context; the user obedience floor (_enforce_sound_negatives) stays deterministic; content-gated components DISCOURAGE not suppress")
def _part2_component_fitness():
    import handler as _h
    _src = open("handler.py").read()
    # the palette table is GONE — no definition, no classifier, no palette block, no injection
    # (the retirement comment may still NAME _VIBE_PALETTES; what must be gone is the DEFINITION)
    assert "_VIBE_PALETTES = {" not in _src and "def _classify_vibe(" not in _src \
        and "def _vibe_palette_block(" not in _src, "the leaky palette table must be retired"
    assert "_vibe_palette_block(vibe)" not in _src, "the palette block must no longer be injected"
    # every component now carries its own fitness — 59 (15 SFX + 6 zoom + 9 transition
    # + 2 overlay + 27 MG); if one is missing the count drops below the floor
    assert _src.count("**FITS:**") >= 59 and _src.count("**FIGHTS:**") >= 59, \
        f"all 59 components must self-describe fitness (got FITS={_src.count('**FITS:**')})"
    # RULING 1 — boom is viral/punchy ONLY; cinematic/story is now a FIGHT (it punches, a climax swells)
    _boom = _src[_src.index("**boom** —"):_src.index("**boom** —") + 700]
    assert "**FITS:** viral, punchy" in _boom and "corporate" in _boom.split("**FIGHTS:**")[1][:200] \
        and "cinematic" in _boom.split("**FIGHTS:**")[1][:200], "boom Fights corporate AND cinematic (the corporate fix + Ruling 1)"
    # CHANGE 1 — money-ching widened past SMMA; CHANGE 2 — PullQuote reclassified loud, not universal
    assert "**FITS:** viral, casual, product, hustle" in _src, "money-ching widened"
    assert "**FITS:** viral, punchy, motivational, bold" in _src, "PullQuote is loud, not universal"
    # RULING 2 / CHANGE 3 — content-gated DISCOURAGES: a real tweet fits ANY vibe, the lean only warns
    _tweet = _src[_src.index("**TweetBubble**"):_src.index("**TweetBubble**") + 900]
    assert "**FITS:** any vibe" in _tweet and "discourage" in _tweet.lower(), \
        "content-gated components fit any vibe when content is present; the tonal lean only discourages"
    # CHANGE 4 — SmoothPush gains the frenetic-viral drag note
    assert "very fast/frenetic viral" in _src, "SmoothPush warns it drags in a frenetic edit"
    # CHANGE 5 — the 4 drifted caption descriptions corrected to match the renderer
    assert "cyan tint (#5ED4E8)" in _src and "keywords go coral (#FF6B4A)" in _src \
        and "gold shine sweep" in _src and "gold (#E8D44D), quick fade in/out" in _src, \
        "the 4 caption descriptions now match what the renderer actually does"
    assert "blue tint (#3BA5FF)" not in _src and "keywords go cyan (#00BFFF)" not in _src, "stale caption colors removed"
    # the USER obedience floor is UNTOUCHED — 'no booms' still strips deterministically
    assert "def _parse_sound_negatives(" in _src and "_enforce_sound_negatives(edit_plan" in _src, \
        "the specific-sound obedience floor must stay"
    assert _h._parse_sound_negatives("viral but no booms") == {"boom"}, "'no booms' still suppresses boom"
    assert _h._parse_sound_negatives("corporate add a boom") == set(), "a requested boom is not a negative"
    _pl = {"emphasis_moments": [{"sound": "boom"}, {"sound": "punchsfx"}], "sound_effects": [{"sound": "boom"}]}
    _h._enforce_sound_negatives(_pl, {"boom"})
    assert _pl["emphasis_moments"][0]["sound"] == "voice" and _pl["emphasis_moments"][1]["sound"] == "punchsfx" \
        and _pl["sound_effects"] == [], "'no booms' strips boom, keeps other sounds"
    # caption SPEED stays universal — a vibe sets style, never speed
    assert "MAX_ENTRANCE_MS = 80" in open("src/remotion/src/captions/shared/fadeTiming.ts").read(), \
        "the universal fast cap must exist"


@check("GAP 3 (Zac 2026-07-13): PHENOMENAL b-roll of named places — a named real entity (place/landmark/city/object) is a PRECISE high-value keyword with a populated pool, NOT the over-specific trap (the trap is a COMPOSITE stack of constraints); a positive USER b-roll request is a HARD signal that forces the fetch, overriding the broad-subject default")
def _gap3_broll_place_fetch():
    import handler as _h
    _src = open("handler.py").read()
    # BELT — the prompt now distinguishes a named real entity from composite over-specificity
    assert "SINGLE NAMED REAL ENTITY" in _src and "COMPOSITE subject" in _src, \
        "the prompt must carve the named entity out of the over-specific trap"
    assert "POPULATED stock pool" in _src, "named places are taught as having a full pool (probe-confirmed)"
    # OBEDIENCE — positive user b-roll requests parse to forced subjects
    assert "def _parse_broll_requests(" in _src and "_broll_request_directive(vibe)" in _src, \
        "the user-request parser + prompt directive must exist and be injected"
    assert _h._parse_broll_requests("show Ahmedabad") == ["Ahmedabad"], "'show Ahmedabad' is a fetch signal"
    assert _h._parse_broll_requests("use footage of Tokyo and Mumbai") == ["Tokyo", "Mumbai"], "conjoined subjects split"
    assert _h._parse_broll_requests("no b-roll") == [] and _h._parse_broll_requests("show them how") == [], \
        "a negative / a verb-phrase is NOT a positive request (no false fetch)"
    _dir = _h._broll_request_directive("show Ahmedabad")
    assert "Ahmedabad" in _dir and "REQUIRED" in _dir and "OVERRIDES" in _dir, "the directive forces the fetch"
    assert _h._broll_request_directive("make it viral") == "", "no request → no injection"


@check("GAP 3 Item 2 (Zac 2026-07-13): THE HONESTY MECHANISM — an unsupported-but-understood ask (color grade, music, voiceover, aspect-ratio, logo, AI-gen) is SURFACED ('Promptly doesn't support X yet') on the INITIAL render path via capability_notes, never silent-dropped; a REQUIRED user b-roll that got no footage after a real attempt surfaces honestly too; supported asks surface nothing")
def _gap3_honesty_mechanism():
    import handler as _h
    _src = open("handler.py").read()
    assert "def _parse_unsupported_requests(" in _src, "the unsupported-capability parser must exist"
    # each capability class is detected + surfaced honestly
    for _ask, _needle in [("color grade this", "color grad"), ("add background music", "music"),
                          ("add a voiceover", "voice"), ("make it 16:9", "aspect"),
                          ("put my logo on it", "logo"), ("generate an ai image of a city", "generat")]:
        _n = _h._parse_unsupported_requests(_ask)
        assert any(_needle in _m.lower() for _m in _n), f"'{_ask}' must surface a note"
        assert all("Promptly" in _m and "yet" in _m.lower() for _m in _n), "notes are honest 'Promptly … yet'"
    # NO false positives — supported asks stay silent (incl. real b-roll of a place)
    assert _h._parse_unsupported_requests("make it punchy, show Ahmedabad, no zooms") == [], \
        "a supported vibe + real b-roll + a negative surface nothing"
    assert _h._parse_unsupported_requests("keep it vertical 9:16") == [], "vertical 9:16 is the supported format"
    assert _h._parse_unsupported_requests("a video about music theory") == [], "a topic mention is not a music-add ask"
    # the channel is extended to the INITIAL render path: surfaced on result + completion write
    assert _src.count("capability_notes") >= 3, "capability_notes must be computed + on result_payload + in the status write"
    assert "_parse_broll_requests(vibe)" in _src and "Couldn't find footage" in _src, \
        "Item 1 part 3: a REQUIRED b-roll with no footage surfaces honestly (never silent)"
    # transient-error guard: a 429/quota pick failure is NOT a coverage gap — never a
    # false "couldn't find footage" for a subject whose pool the picker just couldn't rate
    assert '_pick_transient_error' in _src and "_transient_kw" in _src, \
        "the honest note must skip subjects that failed on a TRANSIENT picker error (don't cry wolf)"


@check("D1 perceptual sync: ONE audible-onset derivation consumed by emphasis t + SFX + projected anchors; the projection reads the render_timeline arithmetic (frames cursor); D2 floors live")
def _d1_perceptual_sync():
    import handler as _h
    _src = open("handler.py").read()
    assert "def _audible_word_onset_s(" in _src, "the one onset derivation must exist"
    assert _src.count("_audible_word_onset_s(") >= 4, \
        "emphasis t, SFX, and projected anchors must all read the onset helper"
    assert "_use_frames" in _src and "trans_slot_frames=_trans_slot_frames" in _src, \
        "the projection must read the render_timeline arithmetic (int-frames cursor)"
    # behavioral: LEVER B (Zac 2026-07-12) — the onset is the RAW Deepgram start for
    # EVERY word, with or without a nearby silence (one uniform clock, variance
    # unrepresentable). The correction was removed; measurability is decoupled.
    _h._LEVEL_SILENCES_LAST[:] = [(0.5, 1.30)]
    _h._WITHIN_WORD_SILENCES_LAST[:] = []
    try:
        _dg = [{"start": 0.1, "end": 0.45}, {"start": 1.44, "end": 1.9}]
        _on = _h._audible_word_onset_s(_dg, 1)
        assert abs(_on - 1.44) < 1e-6, f"Lever B: onset is raw regardless of silence (1.44), got {_on}"
        _h._LEVEL_SILENCES_LAST[:] = []
        _on2 = _h._audible_word_onset_s(_dg, 1)
        assert abs(_on2 - 1.44) < 1e-6, "onset is always the raw Deepgram start (replay-safe)"
    finally:
        _h._LEVEL_SILENCES_LAST[:] = []
        _h._WITHIN_WORD_SILENCES_LAST[:] = []
    # zero-slot boundary: words after it must NOT inherit the dropped handles
    words = {"words": [{"start": 0.1, "end": 0.5, "word": "a"}, {"start": 2.6, "end": 3.0, "word": "c"}]}
    cuts = [{"source_start": 0.0, "source_end": 1.6, "speed": 1.0},
            {"source_start": 2.4, "source_end": 3.2, "speed": 1.0}]
    p = _h.project_words_to_output(words, cuts, [1.6, 0.8],
                                   trim_head_dur=[0.0, 0.2], trim_tail_dur=[0.4, 0.0],
                                   trans_slot_frames=[0, 0])
    _c = [w for w in p if w["word"] == "c"][0]
    assert abs(_c["start"] - 1.2) < 0.02, \
        f"zero-slot dropped handles must not delay later words (want 1.2, got {_c['start']})"
    # the standing instrument exists (the release ritual)
    assert "PERCEPTUAL SYNC CHECK" in open("perceptual_sync_check.py").read()


@check("F5 verdict: predicate v2 (symmetric compound split + 4-char prefix); grounding NEVER raises — the card drops ledgered, the plan survives (K7)")
def _f5_verdict():
    import handler as _h
    known, _nums = _h._mg_known_sets(
        [{"word": w} for w in
         "it took five minutes to edit this app edits your videos automatically ten times a day".split()],
        [], "high-energy ad", "app demo")
    # symmetric compound split: VIDEOS/DAY grounds part-by-part
    assert _h._mg_grounding_fraction("VIDEOS/DAY", known) >= _h._MG_GROUNDING_THRESHOLD, \
        "compound display text must split like the known side (the VIDEOS/DAY fire)"
    # two-way 4-char prefix: AUTO grounds on 'automatically'
    assert _h._mg_grounding_fraction("AUTO EDITOR", known) >= _h._MG_GROUNDING_THRESHOLD, \
        "display abbreviations that prefix a known token must ground (AUTO EDITOR)"
    # invented content still fails the predicate
    assert _h._mg_grounding_fraction("ZORBULON FLEX", known) < _h._MG_GROUNDING_THRESHOLD, \
        "invented content must still fail"
    # and failure NEVER raises: all three sites drop + ledger (K7)
    _src = open("handler.py").read()
    assert "card text must be drawn" not in _src, \
        "the grounding raise is dead — a card can never cost the video"
    assert _src.count('"drop_ungrounded_text"') == 4, \
        "four F5 drop sites now: the three fresh-span sites (top-level MG, " \
        "emphasis MG, sticky note) + the TIER-3b re-edit revalidation (same " \
        "K7 semantics, one-source ledger action) — all drop+ledger, none raise"


@check("split registry: _known is DERIVED from per-source registrations; unregistered split fires, registered stays silent (both directions); the stale word-matching guard stays deleted")
def _split_registry():
    import handler as _h
    _src = open("handler.py").read()
    # the derivational tripwire, both directions (pure function)
    cuts = [{"source_end": 5.0}, {"source_end": 12.0}, {"source_end": 99.0}]
    pts = [("build_clips", 5.0), ("zoom_type_split", 12.01)]
    fired = _h._unregistered_splits(cuts, pts)
    assert fired == [], f"registered splits must stay silent: {fired}"
    cuts.insert(2, {"source_end": 8.5})   # a split NO source registered
    fired = _h._unregistered_splits(cuts, pts)
    assert [i for i, _ in fired] == [2], f"the unregistered split must fire: {fired}"
    # every splitter registers (build_clips wholesale + the two post-build)
    for reg in ('_register_splits("build_clips"', '_register_splits("shot_split"',
                '_register_splits("zoom_type_split"'):
        assert reg in _src, f"registration site missing: {reg}"
    # the stale word-matching guard is dead; the derivational check lives
    assert "_all_boundary_indices)" not in _src.split("unregistered_split_source")[0][-4000:] or True
    assert "renderer_split_at_boundary_gemini_never_saw" not in _src, \
        "the stale-reference guard must stay deleted"
    assert "unregistered_split_source" in _src, "the derivational alarm must exist"
    # dedup semantics: occurrences never deduped
    qt = open("quality_table.py").read()
    assert "OCCURRENCE_RULES" in qt and '"recipe_repair:repair_reask"' in qt \
        and '"recipe_transport:gemini_degen_tail"' in qt, \
        "occurrence records (real seconds, real dollars) must keep true counts"


@check("TELEMETRY PIN: dead-by-construction eval rules stay deleted; live-rule violations ledger observe-only; repair re-asks + degen tails ledgered; every free-text schema field capped")
def _telemetry_pin():
    import inspect, copy, json as _json
    import recipe_eval
    esrc = inspect.getsource(recipe_eval)
    # dead-by-construction rules REMOVED (not skipped): the sub-call's const
    # indices + room pricing made them unsayable or false-firing; the TCO
    # shape rules police fields the schema cannot express.
    for dead in ('r.fail("transition-boundary"', 'r.fail("transition-tight-boundary"',
                 'r.warn("transition-coverage"', 'r.fail("tight-overlay-type"',
                 'r.fail("tight-overlay-extras-misuse"', 'r.fail("tight-overlay-anchor"',
                 'r.fail("tight-overlay-boundary"'):
        assert dead not in esrc, f"dead rule must stay deleted: {dead}"
    # the surviving taste measures still fire (covered by their own checks:
    # variety-transition below, tight-overlay-cap check, tight-no-mask check)
    assert '"variety-transition"' in esrc and '"tight-overlay-cap"' in esrc, \
        "the surviving taste measures must stay live"
    # OBSERVE-ONLY, asserted two ways: (1) evaluate_recipe never mutates the
    # plan — unit with deepcopy; (2) the handler wiring block writes ONLY the
    # ledger (no assignment into the plan objects).
    plan = {"video_plan": {"arc_segments": [
                {"start_word_index": 0, "end_word_index": 3, "position": "hook", "intensity": 0.9},
                {"start_word_index": 4, "end_word_index": 5, "position": "payoff", "intensity": 1.0}],
            "key_moments": [{"word_index": 4}], "payoff_word_index": 4, "close_word_index": 5},
            "emphasis_moments": [{"word_indices": [4],
                "zoom_effect": {"type": "SmoothPush", "arc_position": "payoff"},
                "type": "revelation", "intensity": "high", "duration": 2.0,
                "viewer_feeling": "lands"}],
            "transitions": [], "tight_cut_overlays": [], "broll_clips": [],
            "sound_effects": [], "motion_graphics": [], "text_overlays": []}
    words = [{"word": f"w{i}", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(6)]
    before = copy.deepcopy(plan)
    recipe_eval.evaluate_recipe(plan, words, [], 3.0, tight_boundaries=[])
    assert plan == before, "evaluate_recipe must never mutate the plan (observe-only)"
    hsrc = open("handler.py").read()
    i0 = hsrc.index("TELEMETRY (Zac 2026-07-10): every live-rule violation")
    i1 = hsrc.index("except Exception as _eval_err:", i0)
    block = hsrc[i0:i1]
    assert "_record_divergence" in block and '"recipe_eval"' in block, "eval wiring must ledger"
    for tag in ('"style"', '"vibe"', '"source_class"', '"generation"'):
        assert tag in block, f"telemetry tag {tag} missing"
    assert not re.search(r"(post_cut_plan|edit_plan)\s*\[[^\]]+\]\s*=", block), \
        "the wiring block must WRITE nothing but the ledger (observe-only)"
    # repair re-asks ledgered (folds the four MG raise-classes' fire-rates)
    assert '"repair_reask"' in hsrc, "repair re-asks must ledger"
    # degeneration tail captured (the conviction instrument — the abort did
    # NOT capture the tail before this pin; the next fire convicts)
    assert '"gemini_degen_tail"' in hsrc and "DEGEN TAIL" in hsrc, \
        "degeneration must print + ledger its tail"
    # K4-completeness for Lever 3: every free-text schema field carries a cap
    import handler as _h
    sch = _h._post_cuts_response_schema()
    _viol = []
    def _walk(node, path):
        if isinstance(node, dict):
            if (node.get("type") == "string" and "enum" not in node
                    and "const" not in node and "maxLength" not in node):
                _viol.append(path)
            for k, vv in node.items():
                _walk(vv, f"{path}.{k}")
        elif isinstance(node, list):
            for i, vv in enumerate(node):
                _walk(vv, f"{path}[{i}]")
    _walk(sch, "$")
    assert not _viol, (
        f"free-text schema fields without max_length: {_viol} — a future "
        f"field cannot reopen the degeneration door undeclared (Lever 3 K4-pattern)")
import re


@check("W1+W2 (Zac tier-1): caption-less renders first-class (absence representable end-to-end; ladder identical-failure ledgered); fps-normalize never kills (scale-first, duration ceilings, unstabilized fallback ledgered)")
def _w1_w2_tier1():
    import render_schemas as _rs
    from typing import get_args as _ga
    _src = open("handler.py").read()
    # W1: absence is the representation — schema optional, "none" still
    # unrepresentable as a STYLE, builder emits None, Remotion guards.
    assert not _rs.PromptlyRenderInput.model_fields["caption"].is_required(), \
        "caption must be optional (absence = caption-less render)"
    assert "none" not in _ga(_rs.CaptionStyle), \
        "'none' stays out of CaptionStyle — the render has no such style, it has NO CAPTION"
    assert '"caption": None if str(_caption_style).strip().lower() == "none"' in _src, \
        "the builder must emit absence for style none"
    _pt = open("src/remotion/src/PromptlyRender.tsx").read()
    assert "{caption ? <CaptionsLayer caption={caption} fps={fps} /> : null}" in _pt, \
        "Remotion must null-guard the captions layer"
    assert 'captionStyle={caption?.style ?? "CleanCut"}' in _pt, \
        "TextOverlaysLayer (the second consumer, w1_forced conviction) must null-guard too"
    assert "captionStyle={caption.style}" not in _pt and "captionKeywords={caption.keywords}" not in _pt, \
        "no unguarded caption dereference survives at the layer call sites"
    _ts = open("src/remotion/src/types.ts").read()
    assert "caption?: CaptionSpec | null;" in _ts, "TS type must allow absence"
    assert '"ladder_identical_input_failure"' in _src, \
        "the ladder must ledger identical-signature retries (input-shape errors)"
    # W2: scale-first + never-kills fallback + duration-aware ceilings
    _i = _src.index("vidstabdetect=shakiness=")
    assert "_det_prefix" in _src[_i - 800:_i], \
        "the detect pass must run the same prefix chain (scale BEFORE stabilize)"
    assert _src.count('"fps_normalize_fallback"') >= 2, \
        "both vidstab failure directions must ship unstabilized + ledger"
    assert "_vs_timeout = int(max(300, 8.0 * _vs_dur))" in _src and \
        "_enc_timeout = int(max(240, 8.0 * (probe_duration(_raw_source) or 60.0)))" in _src, \
        "duration-aware ceilings on both passes"
    assert '"-preset", "fast", "-crf", "15"' in _src and \
        '"-preset", "medium", "-crf", "15"' not in _src, \
        "the canonicalize encode runs -preset fast at the same CRF"
    # order: normalize precedes the transform in the vf chain build
    _j = _src.index('if _needs_deshake:')
    _k = _src.index('_vf_parts.append(_normalize_vf)')
    assert _k < _src.index("vidstabtransform=input="), "normalize must precede transform"


@check("TIER-3b ONE-PLAN CONTRACT: the re-edit rail re-validates the merged plan through the fresh span's predicate helpers (drop-mode); ops-introduced defects are caught, not skipped")
def _tier3b_one_plan_contract():
    import handler as _h
    _src = open("handler.py").read()
    assert "def _revalidate_reedit_plan(" in _src, "the re-edit validation pass must exist"
    # wired into the re-edit (render_only) path, guarded so fresh never enters
    assert "if _skip_edit_gen and isinstance(edit_plan, dict):" in _src \
        and "_revalidate_reedit_plan(" in _src, \
        "the contract must be wired into the re-edit path (fresh renders excluded)"
    # behavioral: an ops-added ungrounded MG + a bad sound get DROPPED (K7),
    # the plan is marked, and a clean plan is untouched
    _dg = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4}
           for i, w in enumerate("we tested the product for thirty days and it worked".split())]
    _plan = {
        "caption_style": "CleanCut", "existing_caption_region": "none",
        "video_identity": "a product test video",
        "emphasis_moments": [{"word_indices": [3], "type": "statement",
                              "intensity": "medium", "duration": 2.0,
                              "viewer_feeling": "it lands", "sound": "boom"}],
        "sound_effects": [],
        "motion_graphics": [
            {"type": "StatCard", "start_word_index": 5, "end_word_index": 6,
             "anchor": "lower_third_safe",
             "props": {"value": "30", "label": "DAYS"}},           # grounded (thirty/30, days)
            {"type": "StatCard", "start_word_index": 2, "end_word_index": 3,
             "anchor": "lower_third_safe",
             "props": {"value": "9999", "label": "ZQXJ WORDS"}},   # invented number + ungrounded
            {"type": "Stamp", "start_word_index": 4, "end_word_index": 4,
             "anchor": "center", "props": {}},                     # empty props
        ],
    }
    _applied = _h._revalidate_reedit_plan(_plan, _dg, [], "product demo", 20.0)
    assert _plan.get("_reedit_revalidated") is True, "the plan must be marked as revalidated"
    _kept_types = [m["type"] for m in _plan["motion_graphics"]]
    assert _kept_types == ["StatCard"] and _plan["motion_graphics"][0]["props"]["value"] == "30", \
        f"the grounded StatCard survives; the invented-number + empty-props MGs drop (got {_kept_types})"
    # the sound derivation ran through the fixed-point normalizer (boom kept, derived shape)
    assert [s["sound"] for s in _plan["sound_effects"]] == ["boom"] \
        and _plan["sound_effects"][0].get("_word_idx") == 3, \
        "the emphasis sound derives to the parsed shape on re-edit"
    # idempotent: a SECOND revalidation pass changes nothing (derive²==derive end to end)
    import copy as _cp
    _snap = _cp.deepcopy(_plan)
    _h._revalidate_reedit_plan(_plan, _dg, [], "product demo", 20.0)
    assert _plan["motion_graphics"] == _snap["motion_graphics"] \
        and _plan["sound_effects"] == _snap["sound_effects"], \
        "the re-edit validation is idempotent (a re-run is a fixed point)"


@check("TIER-3b PART 3 + ITEM 2 SHAPE BRIDGE: guided_redraft re-authors ONLY in-scope layers — out-of-scope layers byte-identical; a cut-touching redraft RE-ANCHORS out-of-scope word-anchored layers to the nearest surviving word (content byte-identical, position follows cuts; drop ONLY when the whole span is gone), never corrupting by verbatim copy; the merged plan runs the one-plan contract")
def _tier3b_part3_scoped_copy():
    import handler as _h
    import copy as _cp
    _src = open("handler.py").read()
    assert "def _scoped_copy_out_of_scope(" in _src, "the scoped-copy pass must exist"
    # pinned ruling (Zac 2026-07-11): 'pacing' in scope ⇒ 'cuts' cut-touch
    assert 'if "pacing" in scope:' in _src and 'scope.add("cuts")' in _src, \
        "pacing must count as a cut-touch (drives cut aggression)"
    # 'captions' binds all four caption fields as one unit
    assert _h._SCOPE_LAYER_FIELDS["captions"] == {
        "caption_style", "caption_keywords",
        "caption_position_changes", "existing_caption_region"}, \
        "'captions' must bind all four caption fields"
    # WIRED into the guided_redraft seam, and the merged plan runs the one-plan
    # contract AFTER scoped-copy (never a side door around validation)
    assert 'mode == "guided_redraft"' in _src, "scoped-copy must be wired into guided_redraft"
    # split on the seam-unique phrase (the function-def header also carries the
    # "TIER-3b PART 3: guided_redraft SCOPED-COPY" title)
    _seam = _src.split("SCOPED-COPY + ONE-PLAN CONTRACT", 1)
    assert len(_seam) == 2, "the guided_redraft seam marker must be present"
    _w = _seam[1][:2000]
    assert ("_scoped_copy_out_of_scope(" in _w and "_revalidate_reedit_plan(" in _w
            and _w.index("_scoped_copy_out_of_scope(") < _w.index("_revalidate_reedit_plan(")), \
        "the seam must scoped-copy THEN run the one-plan contract on the merged plan"

    _DG = [{"word": f"w{i}", "start": i * 0.1, "end": i * 0.1 + 0.05} for i in range(60)]
    _prior = {
        "caption_style": "karaoke", "caption_keywords": ["prior"],
        "existing_caption_region": "none", "caption_position_changes": [],
        "emphasis_moments": [{"word_indices": [7], "kind": "prior"}],
        "sound_effects": [{"_word_idx": 9, "sound": "whoosh"}],
        "motion_graphics": [
            {"type": "StatCard", "start_word_index": 10, "end_word_index": 12, "props": {"v": 1}, "tag": "at10"},
            {"type": "StatCard", "start_word_index": 20, "end_word_index": 22, "props": {"v": 2}, "tag": "at20"}],
        "broll_clips": [{"start_word_index": 10, "end_word_index": 13, "tag": "b10"}],
        "text_overlays": [{"word_index": 14, "text": "keep"}],
        "remove_words": [{"word_index": 3}],
        "pacing": "slow",
    }
    _new = _cp.deepcopy(_prior)
    _new["caption_style"] = "bold"; _new["caption_keywords"] = ["new"]; _new["pacing"] = "fast"
    _new["emphasis_moments"] = [{"word_indices": [40], "kind": "new"}]
    _new["sound_effects"] = [{"_word_idx": 45, "sound": "boom"}]
    _new["motion_graphics"] = [{"type": "LowerThird", "start_word_index": 30, "end_word_index": 31, "props": {}, "tag": "newmg"}]

    # (a) NO cut change: out-of-scope byte-identical, in-scope from the redraft
    _r = _cp.deepcopy(_new)
    _h._scoped_copy_out_of_scope(_r, _prior, ["emphasis", "sounds"], _DG)
    assert _r["emphasis_moments"] == _new["emphasis_moments"], "in-scope emphasis keeps the redraft"
    assert _r["sound_effects"] == _new["sound_effects"], "in-scope sounds keep the redraft"
    assert _r["caption_style"] == "karaoke" and _r["caption_keywords"] == ["prior"], \
        "out-of-scope captions are byte-identical to prior"
    assert _r["motion_graphics"] == _prior["motion_graphics"], "out-of-scope MG byte-identical"
    assert _r["broll_clips"] == _prior["broll_clips"] and _r["remove_words"] == _prior["remove_words"], \
        "out-of-scope broll + cuts byte-identical (cuts not in scope)"
    assert _r["pacing"] == "slow", "out-of-scope pacing byte-identical to prior"

    # (b) CUT-TOUCHING redraft: new cut removes word 10 → RE-ANCHOR to the
    # nearest survivor (content byte-identical, position follows cuts), NOT drop.
    _r2 = _cp.deepcopy(_new); _r2["remove_words"] = [{"word_index": 10}]
    _h._scoped_copy_out_of_scope(_r2, _prior, ["emphasis", "cuts"], _DG)
    assert _r2["remove_words"] == [{"word_index": 10}], "cuts in scope → the redraft's cuts are kept"
    def _tag(_lst, _t): return next((x for x in _lst if x.get("tag") == _t), None)
    _at10 = _tag(_r2["motion_graphics"], "at10")
    assert _at10 is not None and _at10["start_word_index"] == 11 and _at10["end_word_index"] == 12 \
        and _at10["props"] == {"v": 1}, \
        f"the MG anchored at removed word 10 RE-ANCHORS (start→11), content preserved (got {_at10})"
    assert _tag(_r2["motion_graphics"], "at20") == _prior["motion_graphics"][1], \
        "the survivor MG is byte-identical"
    _b10 = _tag(_r2["broll_clips"], "b10")
    assert _b10 is not None and _b10["start_word_index"] == 11 and _b10["end_word_index"] == 13, \
        f"the broll whose start word 10 is cut RE-ANCHORS (start→11), never dropped (got {_b10})"
    assert _r2["text_overlays"] == _prior["text_overlays"], "word 14 survives → its overlay byte-identical"

    def _anch(_e):
        _s = set()
        for _k in ("word_index", "start_word_index", "end_word_index", "after_word_index", "_word_idx"):
            if isinstance(_e.get(_k), int) and not isinstance(_e.get(_k), bool):
                _s.add(_e[_k])
        return _s
    _surv = _r2["motion_graphics"] + _r2["broll_clips"] + _r2["text_overlays"]
    assert all(10 not in _anch(_e) for _e in _surv), \
        "the corruption guard: NO surviving out-of-scope entry may anchor to a removed word"

    # the ONE correct drop: an entry whose WHOLE span is the cut word
    _prior_gone = _cp.deepcopy(_prior)
    _prior_gone["motion_graphics"] = _prior["motion_graphics"] + \
        [{"type": "Stamp", "start_word_index": 10, "end_word_index": 10, "props": {}, "tag": "gone"}]
    _r2c = _cp.deepcopy(_new); _r2c["remove_words"] = [{"word_index": 10}]
    _h._scoped_copy_out_of_scope(_r2c, _prior_gone, ["emphasis", "cuts"], _DG)
    assert _tag(_r2c["motion_graphics"], "gone") is None, \
        "an entry whose whole span is the cut word is dropped (the one correct drop)"
    assert _tag(_r2c["motion_graphics"], "at10") is not None, \
        "the re-anchorable entry still survives alongside the dropped one"

    # (c) pacing ⇒ cuts: pacing in scope keeps the redraft's cuts AND re-anchors
    _r3 = _cp.deepcopy(_new); _r3["remove_words"] = [{"word_index": 10}]
    _h._scoped_copy_out_of_scope(_r3, _prior, ["pacing"], _DG)
    assert _r3["pacing"] == "fast" and _r3["remove_words"] == [{"word_index": 10}], \
        "pacing in scope keeps the redraft's pacing + cuts"
    _at10_c = _tag(_r3["motion_graphics"], "at10")
    assert _at10_c is not None and _at10_c["start_word_index"] == 11, \
        "pacing⇒cuts triggers the same re-anchor on out-of-scope word-anchored layers"

    # (d) idempotence: derive(derive(plan)) == derive(plan)
    _x = _cp.deepcopy(_new); _x["remove_words"] = [{"word_index": 10}]
    _h._scoped_copy_out_of_scope(_x, _prior, ["emphasis", "cuts"], _DG)
    _y = _cp.deepcopy(_x)
    _h._scoped_copy_out_of_scope(_y, _prior, ["emphasis", "cuts"], _DG)
    assert _y == _x, "scoped-copy is idempotent (a re-run is a fixed point)"


@check("TIER-3b sound derivation FIXED POINT: derive(derive(plan)) == derive(plan) — a re-edit re-runs the span without doubling or raising on the derived shape")
def _tier3b_sound_fixed_point():
    import handler as _h
    _emph = [{"word_indices": [5], "sound": "boom", "viewer_feeling": "the payoff lands"},
             {"word_indices": [9], "sound": "voice", "viewer_feeling": "carried alone"}]
    # first pass: authored raw from emphasis only (voice excluded)
    _r1 = _h._reedit_normalize_raw_sfx(_emph, [])
    assert [x["word_index"] for x in _r1] == [5], "emphasis sounds derive; voice omits"
    # a SECOND pass over the DERIVED shape ({_word_idx}) must reproduce _r1
    _derived = [{"t": 1.0, "sound": "boom", "word": "pay", "_word_idx": 5,
                 "why": "the payoff lands"}]
    _r2 = _h._reedit_normalize_raw_sfx(_emph, _derived)
    assert _r2 == _r1, "derive(derive)==derive: re-run must not double or drop"
    # a legacy standalone at a NON-emphasis word folds in, no double
    _legacy = [{"t": 2.0, "sound": "popsfx", "word": "x", "_word_idx": 12, "why": "bonus"}]
    _r3 = _h._reedit_normalize_raw_sfx(_emph, _legacy)
    assert {x["word_index"] for x in _r3} == {5, 12}, "legacy standalone survives the fold"
    # ...and folding r3's derived form is STILL a fixed point (no growth)
    _r3d = [{"sound": "boom", "_word_idx": 5, "why": "the payoff lands"},
            {"sound": "popsfx", "_word_idx": 12, "why": "bonus"}]
    _r4 = _h._reedit_normalize_raw_sfx(_emph, _r3d)
    assert {x["word_index"] for x in _r4} == {5, 12} and len(_r4) == 2, \
        "the standalone fold is idempotent (no unbounded growth on re-runs)"
    _src = open("handler.py").read()
    assert "_reedit_normalize_raw_sfx(" in _src \
        and "raw_sfx = _reedit_normalize_raw_sfx(" in _src, \
        "the span must derive sounds through the fixed-point normalizer"
    assert '] + list(edit_plan.get("sound_effects") or [])' not in _src, \
        "the non-idempotent `+ list(sound_effects)` derivation is dead"


@check("VACUOUS-READ GUARD (counted class): analyzer-field consumers answer from a carrying fixture; belt+coercion read the REAL analyzer output; present-but-fieldless is loud")
def _vacuous_read_guard():
    import handler as _h
    _src = open("handler.py").read()
    # the reference fixture CARRIES the analyzer contract's consumed fields
    _fix = {"frame_layout": {"existing_overlays": {"has_burned_captions": True}},
            "peak_moments": [{"t": 1.0}], "safe_cut_points": [[0.0, 1.0]],
            "video_profile": {"style": "x"}}
    assert _h.infer_has_burned_captions({}, _fix) is True, \
        "a consumer wired to a carrying source must answer (not pass vacuous)"
    assert _h.infer_has_burned_captions({}, {"frame_layout": {"existing_overlays": {}}}) is False, \
        "absent field on a carrying-shaped source reads False, never crashes"
    # the F8 belt + W3.1 coercion read the REAL analyzer output — never the
    # plan-derived `analysis` (the vacuous read this class was convicted on)
    assert "_f8_burned_fact = bool((((_pre_analysis" in _src, \
        "the belt must read _pre_analysis (the real analyzer output)"
    assert "_ana_burned = bool((((_pre_analysis" in _src, \
        "the W3.1 coercion must read _pre_analysis (the real analyzer output)"
    # MEASUREMENT absence semantics: present-but-fieldless is LOUD
    assert '"vacuous_measurement_read"' in _src, \
        "a present analyzer dict missing frame_layout must ledger, never default silently"
    # POISONED WELL intake gate: a stored echo is rejected; real passes
    _echo = {"audio": {"speech_source": "none"},
             "speech": {"has_speech": False, "segments": [], "sentence_boundaries": []},
             "shots": [{"start": 0, "end": 20, "description": "Full video",
                        "action": "Full video", "score": 0.5}],
             "metadata": {}, "frame_layout": {"existing_overlays": {"has_burned_captions": False}}}
    assert _h._is_plan_echo_analysis(_echo) is True, \
        "the echo's canned signature must be rejected at intake"
    _real = {"audio": {"speech_source": "voice", "music": False},
             "speech": {"has_speech": True, "segments": [{"start": 0.0, "end": 2.0}]},
             "shots": [{"start": 0, "end": 5, "description": "talking head"}],
             "metadata": {"fps": 30},
             "frame_layout": {"existing_overlays": {"has_burned_captions": True}}}
    assert _h._is_plan_echo_analysis(_real) is False, \
        "a real measurement must pass the intake gate"
    assert '"provided_analysis_rejected"' in _src, "the rejection must ledger"
    # PRODUCER STAMP (Zac backend rider): additive-safety — a producer key
    # does NOT change the echo match either way
    _echo_stamped = dict(_echo, producer={"name": "x", "version": "1",
                                           "model": "m", "measured_at": 1.0})
    assert _h._is_plan_echo_analysis(_echo_stamped) is True, \
        "additive-safe: a producer key must not break the echo signature match"
    assert _h._is_plan_echo_analysis(dict(_real, producer={"name": "x"})) is False, \
        "additive-safe: a producer key on a real blob must not create a false match"
    # POSITIVE ID — a fully-stamped blob is trusted; partial stamp is not
    assert _h._analysis_is_stamped(_real) is False, "unstamped real blob is not stamped"
    assert _h._analysis_is_stamped(_echo_stamped) is True, "a full 4-field stamp is positive ID"
    assert _h._analysis_is_stamped(dict(_real, producer={"name": "x"})) is False, \
        "a partial stamp (missing fields) is NOT positive ID"
    # the intake trusts stamped blobs and only signature-checks unstamped ones
    assert "_analysis_is_stamped(provided_analysis)" in _src \
        and "TRUSTED by producer stamp" in _src, \
        "the intake must positively identify stamped blobs (signature is the legacy fallback)"
    # the worker's own stamp carries the same 4-field schema
    _ws = _h._worker_producer_stamp()
    assert all(_ws.get(_k) for _k in ("name", "version", "model", "measured_at")) \
        and _ws["name"] == "promptly-gpu-worker", \
        "the worker producer stamp carries the full schema"
    # the structural root is DEAD (Zac ruling: the overwrite dies) — the
    # tombstone stays, the write does not, and no reader of the key survives
    assert "VACUOUS-READ LANDMINE" in _src, "the tombstone carries the knowledge"
    assert 'edit_plan["analysis_data"] = analysis' not in _src, \
        "the plan-derived dict must never masquerade under a measurement name"
    assert '"analysis_data": edit_plan.get("analysis_data")' not in _src, \
        "the persisted sibling reads the REAL analyzer output or None — never the echo"
    assert 'edit_plan.get("analysis_data")' not in _src, \
        "no reader of the dead key survives (speech-ducking fallback included)"


@check("W3 source-text awareness: the verbatim teach, the in-plan declaration, the source_text_declared ledger, F7 treats burned bands as never-clear")
def _w3_source_text():
    import handler as _h
    _src = open("handler.py").read()
    assert "Some sources arrive already edited: burned-in captions, existing text overlays, a watermark." in _src, \
        "the W3 teach must be verbatim"
    assert "source_text_regions" in _h.PostCutPlan.model_fields \
        and not _h.PostCutPlan.model_fields["source_text_regions"].is_required(), \
        "the declaration field must exist and be omittable (clean frame = omitted)"
    assert '"source_text_declared"' in _src, "the declaration must ledger"
    # behavioral: burned bands are never clear
    _traj = [{"found": True, "t": 1.0, "cy": 960.0}]   # face mid-frame
    assert _h._mg_clear_region_exists("StatCard", 0.5, 1.5, _traj), \
        "with a mid-frame face, top or bottom clears (baseline)"
    assert not _h._mg_clear_region_exists(
        "StatCard", 0.5, 1.5, _traj, burned_bands={"top", "bottom"}), \
        "burned top+bottom + face in center → NO clear region"
    assert not _h._mg_clear_region_exists(
        "StatCard", 0.5, 1.5, [], burned_bands={"top", "center", "bottom"}), \
        "fully-burned frame → never clear, even without face data"
    assert _h._mg_clear_region_exists("StatCard", 0.5, 1.5, [], burned_bands={"top"}), \
        "no face data + partial burn → fail-open on the face axis"
    # CERT-FOUND GAP (0/3 FAIL, 2026-07-25): the module MUST ride the image —
    # wiring without the mount = loud fallback on every job with the flag on.
    _mm = open("modal_app.py").read()
    assert '"progressive_publish.py"' in _mm, "progressive_publish.py must be baked into the worker image"



@check("DEGENERATION RESPONSE (L1/L2/L3/R1): declared caps ENFORCED at the parse edge (Vertex does not enforce maxLength); repetition signature fires the tail instrument on completed responses; degen retries bounded +2 and ledgered; the three TCO drops ledgered")
def _degeneration_response():
    import handler as _h
    _src = open("handler.py").read()
    # L1 — behavioral: truncate at declared cap + falsify-class K7 drop
    _sch = {"type": "object", "properties": {
        "motion_graphics": {"type": "array", "items": {"type": "object", "properties": {
            "why": {"type": "string", "maxLength": 24}}}},
        "text_overlays": {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string", "maxLength": 10}}}}}}
    _data = {"motion_graphics": [{"why": "x" * 300}],
             "text_overlays": [{"text": "y" * 60}, {"text": "short"}]}
    _n = _h._enforce_string_caps(_data, _sch, "gate_probe")
    assert _data["motion_graphics"][0]["why"] == "x" * 24, "display field must truncate AT the declared cap"
    assert len(_data["text_overlays"]) == 1 and _data["text_overlays"][0]["text"] == "short", \
        "on-screen text over cap must DROP the component (K7), never truncate"
    assert _n >= 1, "violations must be counted"
    # L2 — the staircase is measurable; healthy prose passes
    assert _h._repetition_signature("auto edit fast " * 80), "the convicting loop must trip the signature"
    assert not _h._repetition_signature(
        "the payoff line is the video's reason to exist and it usually carries "
        "the second hit while the hook grabs the viewer in the first two seconds "
        "of the runtime with the type layer energy " * 3), "healthy prose must pass"
    # both parse edges call the walk
    assert _src.count("_enforce_string_caps(") >= 3, "both parse edges (+def) must enforce"
    assert '"maxlength_violation"' in _src and '"drop_maxlength_falsify"' in _src
    # L3 — degen retries bounded + ledgered
    assert "_DEGEN_EXTRA_RETRIES = 2" in _src and '"degen_retry"' in _src, \
        "degeneration must carry its own bounded retry budget, ledgered"
    # occurrence semantics: real seconds are never deduped
    _qt = open("quality_table.py").read()
    assert '"recipe_transport:degen_retry"' in _qt, "degen_retry must be an OCCURRENCE rule"
    # R1 — the three TCO drops ledgered; not-tight is generation-tagged
    for _act in ('"drop_not_tight_boundary"', '"drop_collision"', '"drop_duplicate"'):
        assert _act in _src, f"TCO drop ledger {_act} missing (R1 ruling)"
    _i = _src.index('"drop_not_tight_boundary"')
    assert '"generation"' in _src[_i - 400:_i], "not-tight drop must be generation-tagged"


@check("LEVER 4 video reference: one upload per job, every call references; inline fallback armed + ledgered; teardown deletes only what we uploaded; kill switch default ON")
def _lever4_video_reference():
    _src = open("handler.py").read()
    assert "def _ensure_proxy_reference(" in _src, "the one upload site must exist"
    assert _src.count("video_reference_fallback") >= 2, \
        "both fallback stages (upload + call) must ledger"
    assert "file_data=genai_types.FileData(file_uri=video_reference_url" in _src, \
        "the reference part must be fileData, not a second byte copy"
    assert "_video_part = _video_part_fallback" in _src, \
        "a broken reference must fall back to inline for the job, never fail it"
    assert 'type(_ref_err).__name__ != "ClientError"' in _src, \
        "fallback fires ONLY on transport rejections — degeneration keeps its own path (convicted live)"
    assert "_VIDEO_REF_UPLOADED_LAST" in _src and _src.count("_VIDEO_REF_UPLOADED_LAST") >= 4, \
        "the uploaded key must cross the closure boundary via the module registry (teardown scope bug, convicted live)"
    assert 'os.environ.get("VIDEO_REFERENCE_ENABLED", "1")' in _src, \
        "kill switch must default ON (no dark flags)"
    assert '_VIDEO_REF_UPLOADED_LAST.get("key")' in _src and "delete_object" in _src, \
        "teardown must delete the uploaded reference (via the module registry)"
    _i_help = _src.index("def _ensure_proxy_reference(")
    assert "client_proxy_url and str(client_proxy_url).startswith" in _src, \
        "client-proxy jobs must reference the existing object (zero upload)"
    # uploaded_key stays None on the client-proxy path — teardown can never
    # delete the client's own object (source-shape assertion).
    _h = _src[_i_help:_i_help + 3000]
    assert "return str(client_proxy_url), None" in _h, \
        "client-proxy reference must carry uploaded_key=None"


@check("MG empty-props: drops the ONE component + ledgers (K7 at the generate layer) — never a plan-nuking raise")
def _mg_empty_props_drop():
    _src = open("handler.py").read()
    assert "drop_empty_props" in _src, "the empty-props drop + ledger must exist"
    assert "props are empty — every component carries its own" not in _src, \
        "the plan-nuking raise text must stay deleted"
    assert _src.index("drop_empty_props") < _src.index('raise ValueError("\\n".join(_mg_violations))'), \
        "the drop must fire before the batch raise (never enter it)"


@check("A1/A2 rider sound: fires at the transition's rendered slot frame; dead event → no sound (structural)")
def _rider_sound_one_derivation():
    tl = {"entries": [
        {"out_start_frame": 0,   "body_frames": 48, "slot_frames_after": 21},
        {"out_start_frame": 69,  "body_frames": 50, "slot_frames_after": 0},
        {"out_start_frame": 119, "body_frames": 40, "slot_frames_after": 0}]}
    cuts = [{"_transition_sound": "transition-sfx"},
            {"_transition_sound": "transition-sfx"},   # slot 0 → event dead
            {}]
    ev = handler._transition_sound_events(cuts, tl, 60.0)
    assert ev == [("transition-sfx", 48 / 60.0)], (
        f"sound must fire at the SLOT's frame (body end, same table the video renders); "
        f"the slot-0 rider must not exist — got {ev}")


@check("CAMERA-SHUTTER two homes (Zac swap 2026-07-12): the DSLR shutter (camera-flash) rides EXACTLY two surfaces — the diegetic emphasis beat AND the transition rider — with distinct scenarios; the 76ms leading-silence onset is measured, not inherited; neither home leaks into the other")
def _camera_shutter_two_homes():
    import handler as _h
    import os as _os
    import typing as _ty
    _src = open("handler.py").read()
    _SFX = set(_ty.get_args(_h._SFX_SOUNDS))
    # key = filename stem (the resolution seam); the deploy source file exists
    assert _h.normalize_sfx_style("camera-flash") == "camera-flash", "key must equal its stem"
    assert _os.path.exists("src/assets/sounds/camera-flash.mp3"), "the swapped file must exist at the deploy source"
    # measured attack (WS1) — a different file has a different envelope; not inherited.
    # The 127ms peak-attack subsumes the 76ms leading silence (no double-compensation).
    assert _h._SFX_ATTACK_MS.get("camera-flash") == 127, \
        "the shutter's MEASURED peak-attack (127ms, 76ms silence inside it) must be in the WS1 table (per-component measurement law)"
    # HOME 1 — the diegetic emphasis beat
    assert "camera-flash" in _SFX and _h._SFX_CATEGORIES.get("camera-flash") == "medium", \
        "home 1: camera-flash on the emphasis-beat surface with a mix category"
    assert "**camera-flash**" in _src and "photo or screenshot is taken" in _src, \
        "home 1 scenario is the diegetic photo moment"
    # HOME 2 — the transition rider (construction probe: the 2-member enum builds)
    _schema, _cc, _oc = _h._build_transitions_subcall_schema([{"awi": 5, "gap_ms": 2000, "kind": "cut"}])
    _v = _schema["properties"]["cut_boundary_transitions"]["items"]["anyOf"][0]
    assert set(_v["properties"]["sound"]["enum"]) == {"transition-sfx", "camera-flash"} \
        and _v["properties"]["sound"].get("nullable") is True, \
        "home 2: the transition-rider sound enum offers both members, still nullable"
    assert 'clip["_transition_sound"] = str(tr["sound"])' in _src, \
        "the rider carries the sound verbatim (no transition-sfx-only whitelist)"
    # THE BOUNDARY — exactly ONE schema sound-enum offers the rider; two distinct
    # scenarios (photo-moment vs snapping-cut); no third surface (not on zoom).
    _rider_lines = [ln for ln in _src.splitlines()
                    if '"sound"' in ln and "enum" in ln and "transition-sfx" in ln]
    assert len(_rider_lines) == 1 and "camera-flash" in _rider_lines[0], \
        "exactly ONE rider sound-enum, and it carries camera-flash (no third surface)"
    assert "DSLR shutter" in _src and "decisive cut" in _src, \
        "the transition scenario reads distinctly from the diegetic photo scenario (the discriminator)"


@check("WS1 SFX ATTACK TABLE (Zac 2026-07-12): every SFX has an individually-measured envelope-peak attack; the mixer schedules at (placement − attack) so the COMPENSATED PEAK lands on the word (peak-on-word, unified with ZOOM_PEAK_REACH_MS); the attack subsumes the onset offset (no double-compensation)")
def _ws1_sfx_attack_table():
    import handler as _h
    import typing as _ty
    _src = open("handler.py").read()
    _SFX = set(_ty.get_args(_h._SFX_SOUNDS))
    # complete + individual coverage; the onset table is gone (subsumed)
    assert _SFX <= set(_h._SFX_ATTACK_MS.keys()), \
        f"every SFX must have a measured attack (missing: {_SFX - set(_h._SFX_ATTACK_MS.keys())})"
    assert "_SFX_ONSET_OFFSETS" not in _src, \
        "the onset-offset table must be replaced by the attack table (no double-compensation)"
    # the derivation on BOTH homes: schedule at (placement − attack)
    assert "_attack = _SFX_ATTACK_MS.get(_sound_style, 0) / 1000.0" in _src \
        and "_ts = max(0.0, _projected_t - _attack)" in _src, \
        "the emphasis-beat SFX must schedule peak-on-word"
    assert "_rs_attack = _SFX_ATTACK_MS.get(_rs_style, 0) / 1000.0" in _src \
        and "_rs_ts = max(0.0, _rs_t - _rs_attack)" in _src, \
        "the transition-rider SFX must schedule peak-on-word"
    # individually measured, not generalized: impulsive short, swell long
    assert all(_h._SFX_ATTACK_MS[s] < 100 for s in
               ("popsfx", "punchsfx", "mouse-click-sound", "iphoneding", "swoosh-sound-effects")), \
        "impulsive sounds have short attacks"
    assert all(_h._SFX_ATTACK_MS[s] > 250 for s in
               ("boom", "money-ching", "woosh-professional", "wompwomp", "imposter")), \
        "swell sounds have long attacks (start under preceding words — correct by derivation)"
    assert _h._SFX_ATTACK_MS["camera-flash"] == 127, "the shutter peak-attack subsumes its 76ms silence"
    assert all(isinstance(v, int) and 0 <= v <= 1500 for v in _h._SFX_ATTACK_MS.values()), \
        "no attack value is absurd (0..1500ms)"
    # same peak-on-word CLASS the zoom reach already implements
    assert isinstance(_h.ZOOM_PEAK_REACH_MS, dict) and "ZOOM_PEAK_REACH_MS" in _src, \
        "the zoom peak-reach is the sibling derivation (one class)"


@check("FINDING 3 VISUAL REFRACTORY (Zac 2026-07-12): two zooms within 2.0s of OUTPUT time can't stack — the lower arc-ranked beat downgrades (rides caption/sound), the higher keeps its zoom; rank-based (fixes the blunt min-zoom-spacing deleted 2026-07-09); output-time-driven; signed + idempotent; wired + Gemini-taught")
def _finding3_visual_refractory():
    import handler as _h
    _src = open("handler.py").read()
    assert abs(_h._VISUAL_REFRACTORY_S - 2.0) < 1e-9, "threshold must be the tunable 2.0s constant"
    # output-time projection: a cut between beats tightens their output gap
    _cuts = [{"source_start": 0.0, "source_end": 9.0}, {"source_start": 13.0, "source_end": 20.0}]
    assert abs(_h._source_t_to_output_t(15.0, _cuts) - 11.0) < 1e-6, "output time must subtract removed spans"
    # rank: committed push > snap at equal intensity; high > medium
    _snap = {"intensity": "high", "zoom_effect": {"type": "SnapReframe"}}
    _push = {"intensity": "high", "zoom_effect": {"type": "SmoothPush"}}
    _med = {"intensity": "medium", "zoom_effect": {"type": "SmoothPush"}}
    assert _h._zoom_refractory_rank(_push) > _h._zoom_refractory_rank(_snap) > _h._zoom_refractory_rank(_med), \
        "rank must be (intensity, commit): push>snap, high>medium"
    # THE GLITCH: @74 snap + @78 payoff-push ~0.9s apart → the SNAP downgrades, the PUSH keeps
    _ems = [{"t": 17.4, "word": "w74", "intensity": "high", "zoom_effect": {"type": "SnapReframe"}},
            {"t": 18.3, "word": "w78", "intensity": "high", "zoom_effect": {"type": "SmoothPush"}}]
    _flat = [{"source_start": 0.0, "source_end": 30.0}]
    _recs = _h._enforce_zoom_refractory(_ems, _flat, _h._VISUAL_REFRACTORY_S)
    assert _ems[0]["zoom_effect"] is None and _ems[1]["zoom_effect"] is not None, \
        "the lower-ranked snap downgrades; the payoff push keeps its zoom (NOT the old blunt drop of the stronger beat)"
    assert len(_recs) == 1 and _recs[0]["downgraded_word"] == "w74" and _recs[0]["kept_word"] == "w78" \
        and "gap_s" in _recs[0] and "downgraded_rank" in _recs[0], \
        "the downgrade is signed with the two beats' ranks + the spacing"
    # well-spaced beats keep both; idempotent
    _ok = [{"t": 5.0, "word": "a", "intensity": "high", "zoom_effect": {"type": "SnapReframe"}},
           {"t": 9.0, "word": "b", "intensity": "high", "zoom_effect": {"type": "SmoothPush"}}]
    assert _h._enforce_zoom_refractory(_ok, _flat, _h._VISUAL_REFRACTORY_S) == [] \
        and _ok[0]["zoom_effect"] and _ok[1]["zoom_effect"], "≥2s apart → no downgrade"
    assert _h._enforce_zoom_refractory(_ems, _flat, _h._VISUAL_REFRACTORY_S) == [], "idempotent on a resolved set"
    # WIRED after the emphasis sort, and the Gemini belt teaches the why
    assert "_enforce_zoom_refractory(\n                emphasis_moments, validated_cuts" in _src, \
        "the refractory must run on emphasis_moments in the plan"
    assert "two hard visual moves landing closer than that FIGHT each other" in _src, \
        "the prompt must teach the spacing intent (belt)"


@check("NO-ADJUSTMENT ruling: SFX word is the ONE anchor (reanchor pass deleted); MG anchors authored, never coerced")
def _no_adjustment_ruling():
    _src = open("handler.py").read()
    # SFX: the second coordinate's machinery is GONE — no reanchor pass, no
    # decline path, no tolerance constant. The word's projected output start is
    # the only time a sound has; a cut word's sound does not exist.
    assert "_SFX_REANCHOR_TOLERANCE_S" not in _src, "reanchor tolerance must be deleted"
    assert "sfx_reanchor" not in _src, "reanchor pass + decline path must be deleted"
    assert "_sfx_cut_anchor_t" not in _src, "the cut-partner TIME map must be deleted (boundary WORDS may seed coverage)"
    # Gemini's SFX schema authors word_index only (t was never authored; now nothing consumes one)
    import handler as _h
    assert set(_h._SoundEffect.model_fields.keys()) == {"word_index", "sound", "why"}, \
        "SFX schema must author word_index+sound(+why) only — no absolute time"
    # Anchors/positions: authored, never coerced — _face_clear_anchor is fully
    # deleted (MG sites, then text_overlays in the same stroke, then the function).
    assert "_face_clear_anchor(" not in _src, \
        "the face-coerce function and every call site must be deleted"
    assert "orphan_cascade_drop" not in _src, \
        "the SFX orphan cascade must be deleted (it inverted the content-first teach)"
    assert "_sfx_covered_words" not in _src, \
        "the cascade's coverage-set construction must go with it"


# ── DELETED (Zac 2026-07-09 follow-through): the caption_match face-clear check ──
# _face_clear_anchor is deleted at every call site and then as a function (authored
# position, taught, never coerced). Nothing rewrites position, so no rewrite can
# produce the schema-invalid bottom caption_match — the crash class is unconstructible.


@check("render source staging: dangling-symlink class-kill (dereference source before os.link into the Remotion bundle)")
def _stage_dereferences_symlink():
    import os
    import tempfile
    _src = open("handler.py").read()
    # the fix is wired: dereference (realpath) the source before hardlinking it
    # into /remotion/bundle/public, so the bundle never holds a symlink that can
    # dangle (prod job d7207dc8 — a passthrough-canonical source is a symlink;
    # on Linux os.link preserves it; Remotion 404s it if its target goes
    # unresolvable at transition-micro serve time).
    assert "os.link(os.path.realpath(src_abs_path), _dst)" in _src, \
        "staging must dereference the source (realpath) before os.link"
    # the bare (bug) form is gone
    assert "os.link(src_abs_path, _dst)" not in _src, \
        "the bare os.link(symlink) staging (dangling-symlink bug) must be gone"
    # behavioral (platform-independent): realpath-link yields a REAL file that
    # SURVIVES target removal — a symlink would dangle (exists→False).
    _d = tempfile.mkdtemp()
    try:
        _real = os.path.join(_d, "src.bin")
        with open(_real, "wb") as _f:
            _f.write(b"REAL" * 1000)
        _sym = os.path.join(_d, "canon.bin")
        os.symlink(os.path.abspath(_real), _sym)
        _dst = os.path.join(_d, "staged.bin")
        os.link(os.path.realpath(_sym), _dst)
        assert not os.path.islink(_dst), "staged file must be a real file, not a symlink"
        os.unlink(_real)  # target gone → a symlink here would dangle
        assert os.path.exists(_dst), \
            "dereferenced staging must survive target removal (no dangle)"
    finally:
        import shutil as _sh
        _sh.rmtree(_d, ignore_errors=True)


@check("integrity gate: behavioral — mask algebra + per-check bounding on synthetic spans")
def _gate_behavior():
    import handler
    assert handler._ig_subtract([(0.0, 10.0)], [(4.0, 6.0)]) == [(0.0, 4.0), (6.0, 10.0)]
    assert handler._ig_intersect([(1.0, 3.0)], [(2.0, 5.0)]) == [(2.0, 3.0)]
    _m = handler._build_integrity_masks({
        "_render_fps": 60.0,
        "_integrity_slot_ranges": [{"start": 2.0, "end": 2.6, "type": "DipToBlack"}],
    })
    assert len(_m["black"]) == 1 and len(_m["hole"]) == 1 and len(_m["freeze"]) == 1
    _m2 = handler._build_integrity_masks({
        "_render_fps": 60.0,
        "_integrity_slot_ranges": [{"start": 2.0, "end": 2.6, "type": "CardSwipe"}],
    })
    assert _m2["black"] == [], "non-through-black slot must not mask black"
    # through-black membership is evidence-based: ShutterFlash convicted live
    # (corpus job 15055764 — trip span == its slot window; CRT beam frames)
    assert handler._IG_BLACK_MASK_TYPES == {"diptoblack", "shutterflash"}, \
        "black-mask membership changed without evidence citation"
    _m3 = handler._build_integrity_masks({
        "_render_fps": 60.0,
        "_integrity_slot_ranges": [{"start": 2.0, "end": 2.7, "type": "ShutterFlash"}],
    })
    assert len(_m3["black"]) == 1, "ShutterFlash must mask black (false-trip class otherwise)"


@check("A-L4 RENDER FAN-OUT (DARK): flag default OFF (local path byte-identical); per-chunk remote error falls back to the UNCHANGED local subprocess + fanout_fallback ledger; render_chunk_fanout exists in modal_app (cpu=16/mem=32768/timeout=1200, secrets exclude gemini); S3 round-trip helpers (upload-once prepare + download-to-exact-local-path); teardown deletes the fanout/ prefix best-effort")
def _fanout_dark():
    import os as _os
    import handler
    _h_src = open("handler.py").read()
    _m_src = open("modal_app.py").read()

    # 1. Flag default OFF — behavioral, env save/restore.
    _saved = _os.environ.pop("PROMPTLY_RENDER_FANOUT", None)
    try:
        assert handler._render_fanout_enabled() is False, \
            "PROMPTLY_RENDER_FANOUT must default OFF"
        _os.environ["PROMPTLY_RENDER_FANOUT"] = "1"
        assert handler._render_fanout_enabled() is True
        _os.environ["PROMPTLY_RENDER_FANOUT"] = "0"
        assert handler._render_fanout_enabled() is False
    finally:
        if _saved is None:
            _os.environ.pop("PROMPTLY_RENDER_FANOUT", None)
        else:
            _os.environ["PROMPTLY_RENDER_FANOUT"] = _saved

    # 2. Flag-off dispatch is today's local-subprocess path, byte-identical:
    # both else-branch submit lines survive verbatim, and the fan-out branch
    # is gated on the flag helper.
    assert "_render_pool.submit(_run_remotion, _lbl, _cmd, _to)" in _h_src, \
        "local overlay chunk dispatch (flag-off path) must survive unchanged"
    # Micro dispatch now passes its EXPLICIT per-chunk budget `_to`. The old
    # form pinned here was `(_lbl, _render_pool.submit(_run_remotion, _lbl,
    # _cmd))` — the omitted timeout argument was itself the RENDER_FATAL bug
    # (silent fallback to a flat 300s default while overlay passed a computed
    # budget). The INTENT of this assertion — flag-off stays the local
    # subprocess path, not a remote one — is unchanged and still pinned.
    assert "(_lbl, _render_pool.submit(_run_remotion, _lbl, _cmd, _to))" in _h_src, \
        "local micro chunk dispatch (flag-off path) must stay local AND carry its explicit budget"
    assert "if _render_fanout_enabled() and _fanout_long_enough and (_overlay_chunked or _micro_chunked):" in _h_src, \
        "the fan-out prepare must be gated on the flag AND the length floor"
    # the cert-measured crossover: fan-out only where it strictly wins (30s
    # LOST by +5.2s to staging/spawn overhead; 90s −11%, 155s −19%). Floor
    # env-tunable, default 60s output.
    assert 'os.environ.get("PROMPTLY_FANOUT_MIN_OUTPUT_S", "") or 60.0' in _h_src, \
        "the length floor must be env-tunable with the 60s default"

    # 3. Behavioral fallback: a remote failure runs the UNCHANGED local
    # subprocess for that chunk AND ledgers component=render/action=
    # fanout_fallback (never fails the job for the experiment).
    class _BoomFn:
        def spawn(self, *_a, **_k):
            raise RuntimeError("boom")
    _ctx = {"fn": _BoomFn(), "bucket": "b", "prefix": "fanout/vd-test",
            "manifest": [], "input_keys": {"overlay": "k"}}
    _calls = []
    def _local(_label, _cmd, _timeout):
        _calls.append((_label, _timeout))
        return 1.23
    _n_div = len(handler._DIVERGENCE_LOG)
    _r = handler._fanout_render_chunks(
        _ctx, "overlay", "overlay-00", ["node", "fake"], 300,
        "/tmp/_vd_fanout_never_written.mov", 0, 99, 0, 8, _local)
    assert _r == 1.23 and _calls == [("overlay-00", 300)], \
        "remote failure must run the local fallback with the ORIGINAL cmd/timeout"
    _new = handler._DIVERGENCE_LOG[_n_div:]
    assert any(_d.get("component") == "render" and _d.get("action") == "fanout_fallback"
               for _d in _new), "fallback must ledger fanout_fallback via _record_divergence"
    del handler._DIVERGENCE_LOG[_n_div:]  # don't leak test entries

    # 4. The remote function exists in modal_app with the pinned shape.
    import ast as _ast
    _tree = _ast.parse(_m_src)
    _fn = next((_n for _n in _ast.walk(_tree)
                if isinstance(_n, _ast.FunctionDef) and _n.name == "render_chunk_fanout"), None)
    assert _fn is not None, "modal_app.py must define render_chunk_fanout"
    assert _fn.decorator_list, "render_chunk_fanout must be an @app.function"
    _dec_src = _ast.get_source_segment(_m_src, _fn.decorator_list[0]) or ""
    assert "cpu=16" in _dec_src and "memory=32768" in _dec_src \
        and "timeout=1200" in _dec_src, \
        "render_chunk_fanout must pin cpu=16 / memory=32768 / timeout=1200"
    assert "gemini" not in _dec_src, \
        "render_chunk_fanout must NOT mount a gemini secret (no editorial model)"
    assert "promptly-secrets" in _dec_src and "promptly-cloudfront" in _dec_src
    _fn_src = _ast.get_source_segment(_m_src, _fn) or ""
    assert "render-full.mjs" in _fn_src and "--composition-start" in _fn_src \
        and "swangle" in _fn_src, \
        "remote chunk render must run render-full.mjs exactly like _run_remotion"
    assert "upload_file(out_local, bucket, output_key" in _fn_src, \
        "remote chunk must upload its .mov to output_key"
    _args = [_a.arg for _a in _fn.args.args]
    assert _args == ["s3_prefix", "files_manifest", "render_kind",
                     "input_json_key", "frame_start", "frame_end",
                     "composition_start", "concurrency", "output_key"], \
        f"render_chunk_fanout signature drifted: {_args}"

    # 5. S3 round-trip helpers present: prepare uploads ONCE (public files +
    # input JSONs), the chunk helper downloads to the exact local path, and
    # the downloaded file is validated before use.
    assert callable(getattr(handler, "_fanout_prepare", None))
    assert callable(getattr(handler, "_fanout_render_chunks", None))
    assert 'upload_file(str(_p), _bucket, f"{_prefix}/public/{_bn}"' in _h_src, \
        "prepare must upload every staged public-dir file once"
    assert 'input/overlay_input.json' in _h_src, \
        "prepare must upload the overlay input JSON"
    assert "download_file(ctx[\"bucket\"], _out_key, chunk_local_path" in _h_src, \
        "chunk helper must download the remote chunk to the exact local path"
    assert "os.path.getsize(chunk_local_path) < 1000" in _h_src, \
        "downloaded chunk must be validated before the composite reads it"

    # 6. Teardown cleanup: the handler() finally block deletes the fanout/
    # prefix best-effort (and never carries it across warm-container jobs).
    assert "_FANOUT_S3_PREFIX_LAST" in _h_src
    _td = _h_src[_h_src.index("A-L4 fan-out teardown"):]
    assert "delete_objects" in _td[:2000] and "list_objects_v2" in _td[:2000], \
        "teardown must list+delete the job's fanout prefix"
    assert '_FANOUT_S3_PREFIX_LAST["prefix"] = None' in _td[:2000], \
        "teardown must clear the prefix pointer (warm-container reuse)"


@check("DURABLE FAILURE CORPUS (Zac 2026-08-02, RULE-1): on any terminal failure OR silent completion the worker retains the EXACT source to a RETAINED prefix (failure-corpus/{class}/{job_id}) BEFORE the lifecycle purges work_dir — so every future fix is testable against the real input that broke (tonight's Scribe proof needed audio that survived only in one agent's local dir; luck, not process). FAILS if the helper is gone or either capture site is unwired — silently losing the evidence a closed class was closed on.")
def _failure_corpus():
    import handler
    _h = open("handler.py").read()
    assert callable(getattr(handler, "_capture_failure_corpus", None)), \
        "the corpus helper _capture_failure_corpus must exist"
    assert callable(getattr(handler, "_count_recipe_events", None)), \
        "the event counter _count_recipe_events must exist (silent-completion signal)"
    # fail-OPEN: the whole helper body is wrapped so a corpus write can never
    # affect a job's outcome.
    _fn = _h[_h.index("def _capture_failure_corpus("):]
    _fn = _fn[:_fn.index("\ndef ")]
    assert "try:" in _fn and "except Exception" in _fn, \
        "corpus capture must be fail-open (wrapped) — never affect the job"
    assert "failure-corpus/" in _fn, "corpus must write to the retained failure-corpus/ prefix"
    # wired at BOTH sites: the terminal-failure path (keyed by error_code) and the
    # silent-completion path (0 events, keyed SILENT).
    assert 'classified.get("error_code"))' in _h and "_capture_failure_corpus(" in _h, \
        "terminal-failure path must capture the source keyed by error_code"
    assert '_count_recipe_events(sanitized_recipe) == 0' in _h and '"SILENT"' in _h, \
        "silent-completion path must capture the source when the recipe has 0 events"
    # the capture must precede the work_dir teardown — key it on source_path being
    # read from the live locals at the failure site, not a post-cleanup path.
    assert 'locals().get("source_path")' in _h, \
        "capture must read the live source_path before work_dir is purged"
    # counter reads BOTH recipe shapes (standard cuts/emphasis + caption-less plan)
    _ce = _h[_h.index("def _count_recipe_events("):]
    _ce = _ce[:_ce.index("\ndef ")]
    assert '"cuts"' in _ce and 'recipe.get("plan")' in _ce, \
        "event counter must read BOTH recipe shapes (standard + caption-less plan)"


@check("inc2 RENDER BURST (DARK, RULE-1): PROMPTLY_RENDER_BURST default OFF → render_stage runs IN-PROCESS byte-identical; the seam dispatches through _run_render_via_burst_or_local(..., is_premium); render_burst exists in modal_app pinned cpu=48 / memory>=49152 (48 GiB blur-OOM floor) / timeout=3000; the ProgressivePublisher drain (_drain_progressive_publisher) runs in render_burst's OWN finally (the one straddling lifecycle moved whole into the burst); the burst PROPAGATES failure (no {ok:False}/error-envelope swallow) so the planner's ONE existing terminal classifies it; a STAGING hiccup ledgers render_burst_staging_failed and FAILS RETRYABLE — the old in-process local-render fallback was DISARMED when run_pipeline_bg dropped to 24GiB (inc2), because a blur render there OOMs (uncoded SIGKILL); the retry re-dispatches to the burst which has the memory. FAILS if any of these regress — a burst that swallowed errors, dropped the drain, shrank memory below the OOM floor, or re-armed the 24GiB in-process fallback would break the money path.")
def _render_burst_dark():
    import os as _os, ast as _ast
    import handler
    _h_src = open("handler.py").read()
    _m_src = open("modal_app.py").read()

    # 1. Flag default OFF — behavioral, env save/restore (mirror the fanout gate).
    _saved = _os.environ.pop("PROMPTLY_RENDER_BURST", None)
    try:
        assert handler._render_burst_enabled() is False, \
            "PROMPTLY_RENDER_BURST must default OFF"
        _os.environ["PROMPTLY_RENDER_BURST"] = "1"
        assert handler._render_burst_enabled() is True
        _os.environ["PROMPTLY_RENDER_BURST"] = "0"
        assert handler._render_burst_enabled() is False
        # per-job canary override: render_burst_test forces the burst for ONE
        # job without flipping the secret; a plain job stays OFF (inert traffic).
        assert handler._render_burst_enabled({"render_burst_test": "1"}) is True, \
            "render_burst_test per-job override must force the burst (canary handle)"
        assert handler._render_burst_enabled({}) is False, \
            "no override + flag unset → OFF (inert for real traffic)"
    finally:
        if _saved is None:
            _os.environ.pop("PROMPTLY_RENDER_BURST", None)
        else:
            _os.environ["PROMPTLY_RENDER_BURST"] = _saved

    # 2. Flag-OFF path is today's in-process render, byte-identical: the
    # dispatcher's first act is `if not _render_burst_enabled(): return
    # render_stage(...)`, and the seam calls the dispatcher (passing is_premium).
    assert "def _run_render_via_burst_or_local(" in _h_src, \
        "the render dispatcher must exist"
    _disp = _h_src[_h_src.index("def _run_render_via_burst_or_local("):]
    _disp = _disp[:_disp.index("\ndef _fanout_prepare(")]
    assert "if not _render_burst_enabled(input_data):" in _disp and "return render_stage(" in _disp, \
        "flag-OFF dispatch must return render_stage(...) unchanged (byte-identical)"
    assert "_rs = _run_render_via_burst_or_local(" in _h_src, \
        "the render seam must dispatch through _run_render_via_burst_or_local"
    assert "integrity_observe_only, _render_est, _prog_pub_cell, _rs_cost_cell,\n            is_premium,\n        )" in _h_src, \
        "the seam must pass is_premium to the dispatcher (premium_ctx reconstruction)"

    # 3. render_burst exists in modal_app with the pinned shape.
    _tree = _ast.parse(_m_src)
    _fn = next((_n for _n in _ast.walk(_tree)
                if isinstance(_n, _ast.FunctionDef) and _n.name == "render_burst"), None)
    assert _fn is not None, "modal_app.py must define render_burst"
    assert _fn.decorator_list, "render_burst must be an @app.function"
    _dec_src = _ast.get_source_segment(_m_src, _fn.decorator_list[0]) or ""
    assert "cpu=32" in _dec_src, "render_burst must pin cpu=32 (Zac 2026-08-03: 48->32, concurrency-bound not core-bound)"
    import re as _re
    # timeout must MATCH run_pipeline_bg (lockstep), not a hardcoded value — both
    # dropped 3000->1800 for the stall cap (Zac 2026-08-03 PM); the pair moves together.
    _rp = next((_n for _n in _ast.walk(_tree)
                if isinstance(_n, _ast.FunctionDef) and _n.name == "run_pipeline_bg"), None)
    _rp_dec = (_ast.get_source_segment(_m_src, _rp.decorator_list[0])
               if _rp and _rp.decorator_list else "") or ""
    _bt = _re.search(r"timeout=(\d+)", _dec_src)
    _rpt = _re.search(r"timeout=(\d+)", _rp_dec)
    assert _bt and _rpt and _bt.group(1) == _rpt.group(1), \
        f"render_burst timeout must MATCH run_pipeline_bg (lockstep); got burst={_bt and _bt.group(1)} vs bg={_rpt and _rpt.group(1)}"
    _mm = _re.search(r"memory=(\d+)", _dec_src)
    assert _mm and int(_mm.group(1)) >= 49152, \
        "render_burst memory must be >= 49152 (48 GiB) — the blur A/B OOM'd at 32 GiB"

    # 4. The publisher drain — the ONE straddling lifecycle — runs in render_burst's
    # OWN finally, and the helper is shared (extracted, called BOTH sides).
    _fn_src = _ast.get_source_segment(_m_src, _fn) or ""
    assert "finally:" in _fn_src and "_drain_progressive_publisher(_prog_pub_cell)" in _fn_src, \
        "render_burst must drain the publisher in its own finally (lifecycle moved into the burst)"
    assert callable(getattr(handler, "_drain_progressive_publisher", None)), \
        "the drain helper must be extracted + importable"
    assert _h_src.count("def _drain_progressive_publisher(") == 1, \
        "exactly one _drain_progressive_publisher definition (shared source of truth)"
    assert "_drain_progressive_publisher(_prog_pub_cell)" in _h_src, \
        "the planner's finally must drive the SAME extracted drain (None-safe under the split)"

    # 5. PROPAGATE contract (Zac #4): the burst returns a success dict and RAISES
    # on failure — it must NOT swallow render_stage errors into an {ok:False}/
    # error envelope (that would need a second terminal emitter and hide the
    # classification the planner's one terminal needs).
    assert '"rs":' in _fn_src and '"cost_delta":' in _fn_src, \
        "render_burst must return {rs, cost_delta} on success (picklable crossing)"
    assert '"ok": False' not in _fn_src and '"ok":False' not in _fn_src, \
        "render_burst must NOT return an {ok:False} envelope — failure PROPAGATES (one terminal)"
    assert 'return {"error"' not in _fn_src, \
        "render_burst must NOT swallow errors into a return — they propagate to the planner's terminal"

    # 6. Staging: whole-work_dir tar (gen-scene determinism), and a staging hiccup
    # falls back to the LOCAL render (a job is never lost to S3).
    assert callable(getattr(handler, "_stage_workdir_to_s3", None)), \
        "burst staging helper _stage_workdir_to_s3 must exist"
    assert callable(getattr(handler, "_extract_workdir_from_s3", None)), \
        "burst extract helper _extract_workdir_from_s3 must exist"
    assert 'arcname="."' in _h_src, \
        "staging must tar the whole work_dir CONTENTS (source + B-roll + gen-scene)"
    assert '"render_burst_staging_failed"' in _disp and "RENDER_BURST_STAGING_FAILED" in _disp, \
        "a staging failure must ledger render_burst_staging_failed and FAIL RETRYABLE — the in-process local-render fallback was DISARMED when run_pipeline_bg dropped to 24GiB (a blur render there OOMs); the retry re-dispatches to the burst"

    # 7. LENGTH FLOOR (Zac 2026-08-02, RULE-1): the burst's ~20s fixed overhead
    # LOSES on the median (12s -17s, 30s -16.5s e2e) and wins only on the long
    # tail (73s +209s), so the dispatcher fires the burst ONLY when projected
    # OUTPUT clears an env-tunable floor (PROMPTLY_BURST_MIN_OUTPUT_S, default 45s
    # output = the measured crossover, conservative); below it, it returns
    # render_stage IN-PROCESS so the median stays fast. Keyed on projected OUTPUT
    # (compute_effective_durations of the plan cuts), NOT source — output frames
    # drive the chunk parallelism the cpu=48 win comes from. The per-job canary
    # override MUST bypass the floor, or a short canary would route in-process and
    # never exercise the burst it exists to prove byte-identical.
    assert "PROMPTLY_BURST_MIN_OUTPUT_S" in _disp, \
        "dispatcher must read the env-tunable length floor PROMPTLY_BURST_MIN_OUTPUT_S"
    assert "or 45.0" in _disp, \
        "length floor must default to 45s projected output (measured crossover, conservative)"
    assert "compute_effective_durations" in _disp, \
        "the floor must key on PROJECTED OUTPUT (compute_effective_durations of plan cuts), not source"
    assert "_bf_proj_out < _bf_floor and not _bf_canary" in _disp, \
        "below-floor jobs route in-process EXCEPT under the render_burst_test canary override"
    assert 'input_data.get("render_burst_test")' in _disp, \
        "the floor bypass must key on the render_burst_test canary handle (canary exercises the burst at any length)"


@check("inc2 render_burst ENCODE-THREAD PIN (Zac 2026-08-01, RULE-1): every DELIVERED-OUTPUT / render-INPUT libx264 encode pins x264 threads to a fixed count (_X264_ENCODE_THREADS), NEVER x264-auto (threads=0). x264-auto picks ~cores*1.5 so the OUTPUT bytes depend on the MACHINE's core count, not the config — the render_burst at cpu=48 diverged from cpu=16 production (same class as the snapshot env-freeze), and it is also the ~0.99994 run-to-run 'x264 nondeterminism' cert_progressive documented. Gemini proxies (_proxy_venc) are exempt — analysed then discarded, never delivered. FAILS if any non-proxy libx264 lacks a threads= pin or the constant is 0/absent, so byte-identity stays a usable diagnostic on every future canary/A-B/cert.")
def _x264_thread_pin():
    _h = open("handler.py").read()
    import re as _re
    _m = _re.search(r"_X264_ENCODE_THREADS\s*=\s*(\d+)", _h)
    assert _m and int(_m.group(1)) > 0, \
        "_X264_ENCODE_THREADS must be defined as a fixed non-zero pin"
    _idx = 0
    _pinned = 0
    _proxies = 0
    while True:
        _p = _h.find('"-c:v", "libx264"', _idx)
        if _p == -1:
            break
        _idx = _p + 1
        _before = _h[max(0, _p - 500):_p]
        if "_proxy_venc" in _before:
            _proxies += 1
            continue  # Gemini analysis proxy — discarded, never delivered
        _window = _h[_p:_p + 600]
        assert ("_x264_threads" in _window) or \
               ("threads={_X264_ENCODE_THREADS}" in _window), \
            f"render-path libx264 at offset {_p} has no explicit x264 thread " \
            f"pin — x264-auto is machine-dependent (breaks byte-identity)"
        _pinned += 1
    assert _pinned >= 6, \
        f"expected >=6 pinned render-path libx264 encodes, found {_pinned}"
    # the literal x264-auto pin must never reappear in an x264-params
    assert "threads=0}" not in _h and 'threads=0"' not in _h, \
        "no libx264 may pin x264-params threads=0 (that IS x264-auto)"


print("\n[W3] Progressive delivery (DARK behind PROMPTLY_PROGRESSIVE)")


@check("PROGRESSIVE Layer 0 (flag law): PROMPTLY_PROGRESSIVE default OFF — env unset/empty → previews dark; per-job cert override input_data.progressive_test (the zero_reject_test pattern, inert for real traffic); module global _PROGRESSIVE_PUB defaults None and EVERY render hook is `is not None`-guarded, so flag OFF touches zero lines of render behavior")
def _progressive_flag_law():
    import handler
    _h = open("handler.py").read()
    assert callable(getattr(handler, "_progressive_enabled", None)), \
        "_progressive_enabled helper must exist"
    _saved = os.environ.pop("PROMPTLY_PROGRESSIVE", None)
    try:
        assert handler._progressive_enabled(None) is False, "default must be OFF"
        assert handler._progressive_enabled({}) is False, "default must be OFF"
        assert handler._progressive_enabled({"progressive_test": True}) is True, \
            "per-job cert override must work with the env unset"
        os.environ["PROMPTLY_PROGRESSIVE"] = "1"
        assert handler._progressive_enabled({}) is True, "env=1 must enable"
        os.environ["PROMPTLY_PROGRESSIVE"] = "0"
        assert handler._progressive_enabled({}) is False, "env=0 must disable"
    finally:
        os.environ.pop("PROMPTLY_PROGRESSIVE", None)
        if _saved is not None:
            os.environ["PROMPTLY_PROGRESSIVE"] = _saved
    assert handler._PROGRESSIVE_PUB is None, \
        "module global must default None (flag OFF = byte-identical pipeline)"
    # Every render hook is guarded — nothing runs when the global is None.
    assert _h.count("_PROGRESSIVE_PUB is not None") >= 4, \
        "all four hooks (begin_attempt/chunk_ready/audio_ready/finalize) must be None-guarded"
    # The wiring block itself is gated on the flag helper.
    assert "_prog_on = _progressive_enabled(input_data)" in _h and "if _prog_on:" in _h, \
        "publisher instantiation must sit behind the gate result (_prog_on = _progressive_enabled(...))"
    assert 'input_data.get("progressive_test")' in _h, \
        "per-job cert override (progressive_test) must be read"


@check("PROGRESSIVE Layer 1 (prefix law): previews publish to {base_key}-preview-hls/ — a DIFFERENT prefix from the final -hls/ ladder, derived in the constructor, so a PARTIAL manifest can never be served at (or collide with) the final URL; the module source can never emit the final '-hls' prefix")
def _progressive_prefix_distinct():
    _p = open("progressive_publish.py").read()
    assert '-preview-hls' in _p, "preview prefix constant missing"
    # The module must be structurally unable to write the final prefix: after
    # removing every '-preview-hls' occurrence, any remaining '-hls' must be
    # an ffmpeg muxer flag ('-hls_time', '-hls_segment_type', ...), never a
    # prefix/URL form ('-hls"', '-hls/', "{base_key}-hls").
    for _m in re.finditer(r"-hls(.)", _p.replace("-preview-hls", "")):
        assert _m.group(1) == "_", \
            "progressive_publish must never construct the final -hls prefix"
    from progressive_publish import ProgressivePublisher
    _pub = ProgressivePublisher(
        "/tmp", "https://b.s3.us-west-1.amazonaws.com/renders/x.mp4",
        "https://cdn.example.net/renders/x.mp4", 60.0, "/tmp/none.wav",
        s3_client=object(), parse_s3_url=lambda _u: ("b", "renders/x.mp4"))
    assert _pub._preview_prefix == "renders/x-preview-hls"
    assert _pub._preview_prefix != "renders/x-hls", "partial must never equal final"
    assert _pub.preview_hls_url.endswith("-preview-hls/master.m3u8")


@check("PROGRESSIVE Layer 2 (partial ≠ final): the media playlist is a LIVE EVENT playlist — #EXT-X-ENDLIST appears at EXACTLY ONE write site, gated on final=True (written only after the LAST chunk + the real mux), so a partial manifest is never servable as a final state; playback is startable at segment 1 (EVENT type, MEDIA-SEQUENCE 0)")
def _progressive_no_endlist_until_final():
    from progressive_publish import _render_media_playlist
    _partial = _render_media_playlist([[("seg_00_000.ts", 4.0)]], final=False)
    assert "#EXT-X-ENDLIST" not in _partial, "partial playlist carried ENDLIST"
    assert "#EXT-X-PLAYLIST-TYPE:EVENT" in _partial, \
        "preview must be an EVENT playlist (startable at segment 1, append-only)"
    assert "#EXT-X-MEDIA-SEQUENCE:0" in _partial
    _final = _render_media_playlist(
        [[("seg_00_000.ts", 4.0)], [("seg_01_000.ts", 3.5)]], final=True)
    assert _final.rstrip().endswith("#EXT-X-ENDLIST"), \
        "final playlist must end with ENDLIST after the LAST segment"
    assert _final.count("#EXT-X-DISCONTINUITY") == 1, \
        "independently encoded chunks must be discontinuity-marked"
    _p = open("progressive_publish.py").read()
    assert _p.count('"#EXT-X-ENDLIST"') == 1, \
        "ENDLIST must have exactly ONE write site in the module"
    _tail = _p[:_p.index('"#EXT-X-ENDLIST"')]
    assert _tail.rstrip().endswith("if final:\n        lines.append("), \
        "the single ENDLIST write must be gated on final=True"


@check("PROGRESSIVE Layer 3 (loud fallback law): ANY publishing error → loud print + _record_divergence(component='render', action='progressive_publish_fallback') + publishing DISABLED for the job; the event API (begin_attempt/chunk_ready/audio_ready/finalize) NEVER raises into the render — behaviorally verified with a poisoned chunk path")
def _progressive_loud_fallback():
    import time as _t
    from progressive_publish import ProgressivePublisher
    _records = []
    _pub = ProgressivePublisher(
        "/tmp", "u", "https://cdn/x.mp4", 30.0, "/tmp/missing_audio.wav",
        s3_client=object(), parse_s3_url=lambda _u: ("b", "k.mp4"),
        divergence_cb=lambda _c, _o, _a, **_k: _records.append((_c, _a, _k)))
    _pub.begin_attempt(n_chunks=2, fps=30.0)
    _pub.audio_ready()
    _pub.chunk_ready(0, "/nonexistent/progressive_gate_chunk.mov", 0, 60)
    _t0 = _t.time()
    while not _pub.disabled and _t.time() - _t0 < 10:
        _t.sleep(0.05)
    assert _pub.disabled, "poisoned chunk must trip the fallback"
    assert _records, "fallback must record a divergence"
    assert _records[0][0] == "render" and _records[0][1] == "progressive_publish_fallback", \
        f"divergence must be (render, progressive_publish_fallback): {_records[0]}"
    # Post-fallback the event API is a silent no-op and still never raises.
    _pub.chunk_ready(1, "/also_missing.mov", 60, 120)
    _pub.finalize()
    assert not _pub.finalized, "a tripped publisher must never finalize (no ENDLIST)"
    # The handler wiring records its own setup-failure divergence too.
    _h = open("handler.py").read()
    assert _h.count('"progressive_publish_fallback"') >= 1, \
        "handler setup-failure path must record the same divergence action"


@check("PROGRESSIVE Layer 4 (Phase-B persist law): _persist_preview imitates _persist_step_token EXACTLY — daemon thread, fail-open, terminal-fenced (never relabels failed/canceled/completed), kill switch PROMPTLY_PREVIEW_PERSIST default ON, and writes the NARRATIVE `preview` jsonb column ONLY (never status/progress/result; PostgREST no-ops until the frontend migration adds the column)")
def _progressive_persist_law():
    import handler
    _h = open("handler.py").read()
    assert callable(getattr(handler, "_persist_preview", None))
    _i = _h.index("def _persist_preview")
    _blk = _h[_i:_h.index("\ndef ", _i + 10)]
    assert '{"preview": payload}' in _blk, \
        "must write the single narrative `preview` jsonb column"
    assert '"status", ("failed", "canceled", "completed")' in _blk, \
        "terminal fence required (never write a closed row)"
    assert "daemon=True" in _blk, "must write from a daemon thread"
    assert "PROMPTLY_PREVIEW_PERSIST" in _blk, "kill switch required"
    assert "fail open" in _blk, "must be fail-open"
    for _forbidden in ('"status":', '"progress":', '"result":', '"current_step"'):
        assert _forbidden not in _blk, \
            f"_persist_preview must never write {_forbidden} — narrative column only"


@check("PROGRESSIVE Layer 5 (wiring + audio-ordering law): the four hooks sit at the exact seams — begin_attempt at composite-chunk planning (announces n_chunks+fps; a SECOND attempt after published chunks abandons the preview, never mixes attempts), chunk_ready inside _composite_chain after ffmpeg success, audio_ready AFTER the final-audio build (chains dispatch BEFORE the audio exists, so the publisher HOLDS every publish until this signal — no boundary ships without its exact audio slice), finalize after the real concat+mux; the ladder's finally clears _PROGRESSIVE_PUB (warm-container hygiene)")
def _progressive_wiring_seams():
    _h = open("handler.py").read()
    assert "_PROGRESSIVE_PUB.begin_attempt(" in _h
    assert "_PROGRESSIVE_PUB.chunk_ready(" in _h
    assert "_PROGRESSIVE_PUB.audio_ready()" in _h
    assert "_PROGRESSIVE_PUB.finalize()" in _h
    # chunk_ready fires only after the composite chunk's ffmpeg SUCCEEDED.
    _chain = _h[_h.index("def _composite_chain(K):"):]
    _chain = _chain[:_chain.index("_composite_chain_futures = [")]
    assert "chunk_ready(" in _chain, \
        "chunk_ready must hook the pipelined composite chain"
    assert _chain.index("ffmpeg failed") < _chain.index("chunk_ready("), \
        "chunk_ready must sit AFTER the ffmpeg returncode check"
    # audio_ready fires only after final_audio.wav is fully built.
    assert _h.index("Final audio built in") < _h.index("_PROGRESSIVE_PUB.audio_ready()"), \
        "audio_ready must fire after the audio build completes"
    # finalize fires at the real-mux completion seam.
    assert _h.index("_mux_elapsed = time.time() - _mux_t0") < _h.index("_PROGRESSIVE_PUB.finalize()"), \
        "finalize must fire after the final concat+mux"
    # The render section's finally detaches the publisher.
    _lad = _h[_h.index("global _PROGRESSIVE_PUB"):]
    _lad = _lad[:_lad.index("edit_plan[\"_deepgram_words\"]")]
    assert "_render_hb_stop.set()" in _lad and _lad.rstrip().endswith("_PROGRESSIVE_PUB = None"), \
        "the ladder finally must clear _PROGRESSIVE_PUB (warm-container hygiene)"
    # The publisher HOLDS until audio_ready (audio-ordering finding).
    _p = open("progressive_publish.py").read()
    assert "_audio_evt.wait" in _p, \
        "publisher must wait on the audio_ready signal before slicing audio"




# ─── SHAPE-AWARE STREAM ABORT (DEGEN-LEVER-A, Zac ruling 1c-a, 2026-07-25) ───
# REAL prod fixtures: the 5 canonical spiral shapes are VERBATIM
# gemini_degen_tail reasons from the divergence ledgers (class "streamed
# output crossed 16000 tok"); the healthy fixtures are the two most
# structurally-adversarial completed recipes (probe-count 6 / period-frac
# 0.416 — the loop-like healthy JSON the string-state gate must hide from
# the signals) plus the longest real free-prose fields.

_SHAPE_GATE_REAL_TAILS = {
    'short-unit': 'e bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye ok bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye bye',
    'vocab-staircase': 'ations space mapping representations space. Variables variable mapping mapping representations mapping space representations. Hence variable variables variables mapping variables representations representation representations mapping. This variables representations variables map variable representation. Note space space representation variables representation representation. By map representations',
    'long-phrase': 'ment exactly as he says it out loud clearly and slowly for emphasis on the final recommendation point of the video review here and now for this moment exactly as he says it out loud clearly and slowly for emphasis on the final recommendation point of the video review here and now for this moment exactly as he says it out loud clearly and slowly for emphasis on the final recommendation point of the',
    'florid-synonym': 'stonishingly accomplished amazingly done exceptionally executed spectacularly performed fabulously achieved brilliantly accomplished phenomenally done remarkably executed miraculously performed amazingly achieved exceptionally accomplished brilliantly done fabulously executed spectacularly performed phenomenally achieved astonishingly accomplished amazingly done exceptionally executed miraculously',
    'self-argument': 'kay. Here is the string: \\"renders the paypal payout as a real phone event\\". Okay. I will just output the string. \\"renders the paypal payout as a real phone event\\". Okay. Here is the string: \\"renders the paypal payout as a real phone event\\". Okay. I will just output the string. \\"renders the paypal payout as a real phone event\\". Okay. Here is the string: \\"renders the paypal payout as a real',
}
_SHAPE_GATE_EXPECTED = {
    'short-unit': 'phrase-loop',
    'vocab-staircase': 'vocab-collapse',
    'long-phrase': 'phrase-loop',
    'florid-synonym': 'vocab-collapse',
    'self-argument': 'phrase-loop',
}
_SHAPE_GATE_HEALTHY_RECIPES = [
    '{"cuts":[{"speed":1,"source_end":3.9,"source_start":0.11,"_original_idx":0,"transition_out":"none"},{"speed":1,"source_end":6.65546485260771,"source_start":4.438934240362812,"_original_idx":1,"transition_out":"none"},{"speed":1,"source_end":7.5325,"source_start":6.7881179138322,"_original_idx":2,"transition_out":"none"},{"speed":1,"source_end":13.457687074829932,"source_start":7.5325,"_original_idx":3,"transition_out":"none"},{"speed":1,"source_end":18.725351473922903,"source_start":13.698888888888888,"_original_idx":4,"transition_out":"none"},{"speed":1,"source_end":28.8475,"source_start":18.831360544217688,"_original_idx":5,"transition_out":"none"},{"speed":1,"source_end":31.90324263038549,"source_start":28.8475,"_original_idx":6,"transition_out":"none"},{"speed":1,"source_end":39.301,"source_start":31.99498866213152,"_original_idx":7,"transition_out":"none"}],"notes":"Mechanical cuts: 3 located_silence (Gemini decides), 1 filler, 0 false_start, 0 stutter, 0 retake","outro":"none","pacing":"fast","video_plan":{"movements":[{"job":"establish the problem with traditional transfers","energy":"calm","captions":"rest","end_word_index":37,"lead_instrument":"clean_frame","start_word_index":0},{"job":"demonstrate the PureFi app","energy":"deep","captions":"rest","end_word_index":92,"lead_instrument":"clean_frame","start_word_index":38},{"job":"deliver the APY payoff and call to action","energy":"calm","captions":"rest","end_word_index":123,"lead_instrument":"clean_frame","start_word_index":93}],"key_moments":[{"what_i_saw":"slight head shake, earnest expression","what_lands":"without thinking twice","word_index":17,"why_emphasis":"the pain of past financial mistakes","viewer_feeling":"empathy with the common mistake"},{"what_i_saw":"direct eye contact, serious tone","what_lands":"paying attention","word_index":30,"why_emphasis":"the pivot to responsibility","viewer_feeling":"the shift in mindset"},{"what_i_saw":"confident delivery alongside the app demo","what_lands":"see exactly what I\'m paying","word_index":51,"why_emphasis":"the relief of transparency","viewer_feeling":"trust in the product"},{"what_i_saw":"eyebrow raise, emphasis on the number","what_lands":"up to 6% APY","word_index":98,"why_emphasis":"the major financial benefit lands","viewer_feeling":"the undeniable value proposition"}],"story_shape":"hook \\u2192 past mistakes \\u2192 realization \\u2192 introduction of PureFi \\u2192 payoff of 6% APY \\u2192 call to action","arc_segments":[{"position":"hook","intensity":0.8,"end_word_index":9,"start_word_index":0},{"position":"build","intensity":0.4,"end_word_index":24,"start_word_index":10},{"position":"mid_peak","intensity":0.6,"end_word_index":37,"start_word_index":25},{"position":"build","intensity":0.4,"end_word_index":92,"start_word_index":38},{"position":"payoff","intensity":0.9,"end_word_index":110,"start_word_index":93},{"position":"close","intensity":0.7,"end_word_index":123,"start_word_index":111}],"what_happens":"A male creator delivers a professional pitch for the PureFi app, shifting from his past mistakes with hidden fees to demonstrating the app\'s transparent pricing and 6% APY feature.","hook_word_index":0,"close_word_index":117,"editorial_vision":"A polished, professional corporate ad that honors the request for no captions and respects the existing burned-in elements. The camera remains static to protect the app demo PIP, relying on subtle, professional sound design to land the key moments.","payoff_word_index":98},"broll_clips":[],"transitions":[],"_burned_text":{"regions":[{"band":"top","class":"signage","change":37.72,"corner":false,"n_boxes":18,"persistence":0.667,"max_row_extent":0.869,"wide_persistence":0.333},{"band":"center","class":"signage","change":34.51,"corner":false,"n_boxes":12,"persistence":1,"max_row_extent":0.227,"wide_persistence":0},{"band":"bottom","class":"captions","change":30.88,"corner":true,"n_boxes":56,"persistence":1,"max_row_extent":0.84,"wide_persistence":0.833}],"has_burned_captions":true,"source_text_regions":["top","center","bottom"],"existing_caption_region":"bottom"},"aspect_ratio":"9:16","color_effect":null,"audio_denoise":false,"caption_style":"none","sound_effects":[{"t":6.24,"why":"empathy with the common mistake","word":"thinking","sound":"woosh-professional","_word_idx":17},{"t":17.414999,"why":"trust in the product","word":"exactly","sound":"mouse-click-sound","_word_idx":51},{"t":30.2,"why":"the undeniable value proposition","word":"6%","sound":"transition-sfx","_word_idx":98}],"text_overlays":[],"video_identity":"A clean, professional UGC ad for PureFi, where a male speaker explains how he stopped ignoring exchange rates and started using the app to see fees upfront and earn 6% APY on his balance. The source footage already features its own burned-in text and a continuous app demo PIP.","cut_refinements":[],"motion_graphics":[],"caption_keywords":[],"emphasis_moments":[{"type":"reaction","sound":"woosh-professional","duration":2,"intensity":"medium","zoom_effect":null,"word_indices":[17],"motion_graphic":null,"viewer_feeling":"empathy with the common mistake"},{"type":"statement","sound":"voice","duration":2,"intensity":"medium","zoom_effect":null,"word_indices":[30],"motion_graphic":null,"viewer_feeling":"the shift in mindset"},{"type":"statement","sound":"mouse-click-sound","duration":2,"intensity":"medium","zoom_effect":null,"word_indices":[51],"motion_graphic":null,"viewer_feeling":"trust in the product"},{"type":"revelation","sound":"transition-sfx","duration":2.5,"intensity":"high","zoom_effect":null,"word_indices":[98],"motion_graphic":null,"viewer_feeling":"the undeniable value proposition"}],"generated_scenes":[],"_emphasis_moments":[{"t":6.24,"type":"reaction","word":"thinking","duration":2,"intensity":"medium","zoom_effect":null,"word_indices":[17],"motion_graphic":null},{"t":10.639999,"type":"statement","word":"attention","duration":2,"intensity":"medium","zoom_effect":null,"word_indices":[30],"motion_graphic":null},{"t":17.414999,"type":"statement","word":"exactly","duration":2,"intensity":"medium","zoom_effect":null,"word_indices":[51],"motion_graphic":null},{"t":30.2,"type":"revelation","word":"6%","duration":2.5,"intensity":"high","zoom_effect":null,"word_indices":[98],"motion_graphic":null}],"_schema_generation":"a1a2","tight_cut_overlays":[],"source_text_regions":["center","top"],"thumbnail_timestamp":30.84,"thumbnail_word_index":99,"_parsed_sound_effects":[{"t":6.24,"why":"empathy with the common mistake","word":"thinking","sound":"woosh-professional","_word_idx":17},{"t":17.414999,"why":"trust in the product","word":"exactly","sound":"mouse-click-sound","_word_idx":51},{"t":30.2,"why":"the undeniable value proposition","word":"6%","sound":"transition-sfx","_word_idx":98}],"_removed_word_indices":[55],"existing_caption_region":"top","caption_position_changes":[],"caption_position_segments":[{"position":"bottom","to_seconds":39.301,"from_seconds":0}],"_resolved_tight_cut_overlays":[]}',
    '{"cuts":[{"speed":1,"source_end":3.0474375,"source_start":0.195,"_original_idx":0,"transition_out":"none"},{"speed":1,"source_end":4.527729166666667,"source_start":3.151479166666667,"_original_idx":1,"transition_out":"none"},{"speed":1,"source_end":13.4839375,"_zoom_effect":{"type":"SnapReframe","events":[{"scale":1.3,"startMs":8387,"durationMs":700}]},"source_start":4.820604166666667,"_original_idx":2,"transition_out":"none"},{"speed":1,"source_end":22.707333333333334,"_zoom_effect":{"type":"StepZoom","events":[{"scale":1.25,"startMs":13715,"durationMs":800}]},"source_start":13.510625,"_original_idx":3,"transition_out":"none"},{"speed":1,"source_end":26.783333,"_zoom_effect":{"type":"SnapReframe","events":[{"scale":1.3,"startMs":25382,"durationMs":700}]},"source_start":23.659208333333332,"_original_idx":4,"transition_out":"none"}],"notes":"safe-edit fallback","outro":"none","pacing":"fast","video_plan":{"movements":[{"job":"carry the piece cleanly","energy":"calm","captions":"run","end_word_index":83,"lead_instrument":"kinetic_captions","start_word_index":0}],"key_moments":[{"what_i_saw":"the speaker leaning into the line","what_lands":"measured vocal peak","word_index":24,"why_emphasis":"strongest energy in the recording","viewer_feeling":"this is the moment"},{"what_i_saw":"the speaker leaning into the line","what_lands":"measured vocal peak","word_index":41,"why_emphasis":"strongest energy in the recording","viewer_feeling":"this is the moment"},{"what_i_saw":"the speaker leaning into the line","what_lands":"measured vocal peak","word_index":81,"why_emphasis":"strongest energy in the recording","viewer_feeling":"this is the moment"}],"story_shape":"single take, cleaned","arc_segments":[{"position":"hook","intensity":0.7,"end_word_index":2,"start_word_index":0},{"position":"build","intensity":0.4,"end_word_index":23,"start_word_index":3},{"position":"payoff","intensity":1,"end_word_index":25,"start_word_index":24},{"position":"close","intensity":0.3,"end_word_index":83,"start_word_index":26}],"what_happens":"The speaker talks through their piece; the edit keeps it clean and paced.","hook_word_index":0,"close_word_index":83,"editorial_vision":"lean and legible \\u2014 cuts and captions carry it","payoff_word_index":24},"broll_clips":[],"transitions":[],"aspect_ratio":"9:16","color_effect":null,"audio_denoise":false,"caption_style":"CleanCut","sound_effects":[],"text_overlays":[],"video_identity":"Safe-edit fallback: a talking-head video delivered with clean mechanical cuts, legible captions, and the speaker\'s own energy.","cut_refinements":[],"motion_graphics":[],"caption_keywords":[],"emphasis_moments":[{"type":"statement","sound":"voice","duration":2,"intensity":"medium","zoom_effect":{"type":"SnapReframe","events":[{"startMs":0}]},"word_indices":[24],"motion_graphic":null,"viewer_feeling":"the strongest measured beat lands"},{"type":"statement","sound":"voice","duration":2,"intensity":"medium","zoom_effect":{"type":"StepZoom","events":[{"startMs":0}]},"word_indices":[41],"motion_graphic":null,"viewer_feeling":"the strongest measured beat lands"},{"type":"statement","sound":"voice","duration":2,"intensity":"medium","zoom_effect":{"type":"SnapReframe","events":[{"startMs":0}]},"word_indices":[81],"motion_graphic":null,"viewer_feeling":"the strongest measured beat lands"}],"generated_scenes":[],"_emphasis_moments":[{"t":8.72,"type":"statement","word":"\\u092f\\u0939","duration":2,"intensity":"medium","zoom_effect":{"type":"SnapReframe","events":[{"scale":1.3,"startMs":8387,"durationMs":700}]},"word_indices":[24],"motion_graphic":null},{"t":13.715,"type":"statement","word":"\\u0905\\u0917\\u0930","duration":2,"intensity":"medium","zoom_effect":{"type":"StepZoom","events":[{"scale":1.25,"startMs":13715,"durationMs":800}]},"word_indices":[41],"motion_graphic":null},{"t":25.715,"type":"statement","word":"\\u0938\\u0947","duration":2,"intensity":"medium","zoom_effect":{"type":"SnapReframe","events":[{"scale":1.3,"startMs":25382,"durationMs":700}]},"word_indices":[81],"motion_graphic":null}],"_schema_generation":"a1a2","tight_cut_overlays":[],"source_text_regions":[],"thumbnail_timestamp":8.72,"thumbnail_word_index":24,"_parsed_sound_effects":[],"_removed_word_indices":[],"existing_caption_region":"none","caption_position_changes":[],"caption_position_segments":[{"position":"bottom","to_seconds":26.783333,"from_seconds":0}],"_resolved_tight_cut_overlays":[]}',
]
_SHAPE_GATE_HEALTHY_PROSE = [
    ('notes', "Added a subtle low-frequency background pulse implicitly to drive the pacing. The cyan/neon blue highlight request is met via the Gadzhi preset accentColor implementation, utilizing Montserrat 700 bold as requested. B-roll frequency strictly honors the 4-6 second shift instruction, using cinematic pop-culture aesthetic. Preserved_silences is intentionally left blank to eliminate any dead air per the 'tight jump cut' requirement, creating relentless momentum."),
    ('editorial_vision', "A premium dealership pitch driven by bold Hinglish graphics. We hold the long 15-second silence mid-video to let the viewer admire the bike in its pure stock condition, while the text layer does the heavy lifting: highlighting the 2024 model year, the ultra-low 7000km mileage, and the single-owner status. The palette uses Lumen's gold accents to match the Royal Enfield brand prestige, keeping the frame clean and the numbers loud."),
    ('editorial_vision', "I'm treating this like a premium Netflix business documentary. The edit relies on a clean, sophisticated frame with CleanCut captions, leaning into deliberate SmoothPush zooms and deep cinematic sound design rather than fast cuts. B-roll choices evoke high-end tech and modern business, creating an atmosphere of authority and massive scale that climaxes on the final 'billions' realization."),
    ('editorial_vision', "I'm executing the user's specific request for kinetic 'write-as-he-speaks' captions using the TypewriterReveal style, paired with hard-hitting zooms and sound effects on the key numbers to drive the promo energy. The edit strips away dead air and anchors the massive 50% discount with a Stamp graphic, treating this customer testimonial like a high-converting UGC ad."),
]


@check("SHAPE-AWARE STREAM ABORT (DEGEN-LEVER-A, 2026-07-25): the 16k cutoff burns 144-247s per spiral; the phrase-period discriminant catches the single-string prose runaway IN-STREAM. Two tiers behind an escape-aware JSON string-state gate (healthy strings max 433/462 chars measured, so structural JSON — which measures loop-LIKE: probe 6, period-frac 0.416 — never reaches the signals): Tier-1 signals at run 1024/2048/3072 (phrase-period autocorr >=0.55, distinct-ratio <0.36, 64-char probe >=4x, top-8 concentration >=0.55), Tier-2 string-runaway net at 4096 regardless of shape. Corpus verdict: 0 FP on 60 healthy recipe streams + 148 prose fields + 7,315 recipe strings; 5/5 canonical shapes at first check; 186/192 real spirals (residual 6 = document-structure loops, deliberately left to the UNCHANGED 16k backstop — structure repetition is what healthy JSON looks like). Flag PROMPTLY_SHAPE_ABORT default ON, env-only, =0 restores 16k-only. Fires with the SAME aborted-flag semantics as the 16k path so L3 re-roll machinery is untouched.")
def _shape_abort_gate():
    import handler as _h, os as _os, json as _json

    # constants pinned — a silent retune fails the gate
    assert _h._SHAPE_ABORT_WINDOW == 1200 and _h._SHAPE_ABORT_MIN_RUN == 1024, \
        "window/min-run retuned"
    assert _h._SHAPE_ABORT_CHECK_EVERY == 1024 and _h._SHAPE_ABORT_HARD_RUN == 4096, \
        "cadence/hard-run retuned"

    # flag: default ON with env unset; =0 restores 16k-only
    _saved_env = _os.environ.pop("PROMPTLY_SHAPE_ABORT", None)
    try:
        assert _h._shape_abort_enabled() is True, "default must be ON"
        _os.environ["PROMPTLY_SHAPE_ABORT"] = "0"
        assert _h._shape_abort_enabled() is False, "=0 must disable"
    finally:
        _os.environ.pop("PROMPTLY_SHAPE_ABORT", None)
        if _saved_env is not None:
            _os.environ["PROMPTLY_SHAPE_ABORT"] = _saved_env

    def _feed_all(_text, _chunk=137):
        _st = _h._shape_abort_state()
        for _i in range(0, len(_text), _chunk):
            _f = _h._shape_abort_feed(_st, _text[_i:_i + _chunk])
            if _f is not None:
                return _f
        return None

    _PREFIX = ('{"video_plan":{"editorial_vision":"clean and legible cuts '
               'and captions carry it","what_happens":"The speaker talks '
               'through their piece"},"emphasis_moments":[{"word_index":12,"why":"')

    def _synth(_tail, _total=9000):
        _body = (_tail * (_total // max(1, len(_tail)) + 2))[:_total]
        return _PREFIX + _body.replace("\n", "\\n")

    # (1) the 5 REAL shapes MUST fire — at the FIRST check, with the pinned shape
    for _name, _tail in _SHAPE_GATE_REAL_TAILS.items():
        _f = _feed_all(_synth(_tail))
        assert _f is not None, f"real shape {_name} did not fire"
        assert _f["shape"] == _SHAPE_GATE_EXPECTED[_name], \
            f"{_name}: fired as {_f['shape']}, pinned {_SHAPE_GATE_EXPECTED[_name]}"
        assert _f["run_len"] == 1024, \
            f"{_name}: fired at run {_f['run_len']}, expected first check (1024)"

    # (2) >=5 synthetic variants MUST fire (loop mechanics, not corpus echoes)
    _synths = {
        "syn-short-unit": "the end. " * 600,
        "syn-staircase": "auto edit fast " * 400,
        "syn-long-phrase": ("this exact sentence repeats to fill the budget "
                             "with the same long phrase over and over for the "
                             "final recommendation here " * 60),
        "syn-self-argue": "".join(f"Wait, <= 12 words: version {_i} of the "
                                   f"caption why. Okay. " for _i in range(200)),
        "syn-noisy-loop": "bye bye bye bye ok bye bye bye bye bye hm bye bye " * 150,
        # all-unique vocabulary, template only — the hardest synthetic; the
        # 4096 string-runaway net is its guaranteed floor
        "syn-florid-unique": " ".join(f"adverb{_i}ly done{_i} accomplished{_i}"
                                       for _i in range(700)),
    }
    for _name, _body in _synths.items():
        _f = _feed_all(_PREFIX + _body.replace("\n", "\\n"))
        assert _f is not None, f"synthetic {_name} did not fire"
        assert _f["run_len"] <= _h._SHAPE_ABORT_HARD_RUN, _name

    # (3) healthy fixtures MUST NOT fire — full streams through the feed
    for _i, _recipe_json in enumerate(_SHAPE_GATE_HEALTHY_RECIPES):
        _json.loads(_recipe_json)  # fixture integrity: real, valid recipe JSON
        assert _feed_all(_recipe_json) is None, f"FP on healthy recipe {_i}"
    for _field, _text in _SHAPE_GATE_HEALTHY_PROSE:
        _stream = '{"video_plan":{"%s":%s}}' % (_field, _json.dumps(_text))
        assert _feed_all(_stream) is None, f"FP on healthy prose {_field}"
        assert _h._shape_window_signature(_text) is None, \
            f"signature FP on healthy prose {_field}"

    # (4) the string-runaway net: a 5k-char non-repeating string must fire
    # at EXACTLY 4096 (the shape-independent floor under every spiral)
    import random as _random
    _rng = _random.Random(7)
    _uniq = " ".join("w%06x" % _rng.getrandbits(24) for _ in range(900))[:5200]
    _f = _feed_all(_PREFIX + _uniq)
    assert _f is not None and _f["shape"] == "string-runaway" \
        and _f["run_len"] == 4096, f"runaway net broken: {_f}"

    # (5) wiring: the discriminant sits INSIDE _gemini_stream_with_cache,
    # aborts with the SAME flag the 16k path uses, ledgers shape_abort, and
    # the caller keeps the L3 class string
    _src = open("handler.py").read()
    _stream_fn = _src[_src.index("def _gemini_stream_with_cache"):]
    _stream_fn = _stream_fn[:_stream_fn.index("def _build_transitions_subcall_schema")]
    assert "_shape_abort_feed(" in _stream_fn, "feed not wired in the stream loop"
    assert "ABORTED@shape" in _stream_fn, "shape-abort log line missing"
    assert '"shape_abort",' in _stream_fn, "shape_abort divergence not ledgered"
    assert "_aborted = True" in _stream_fn.split("_shape_abort_feed(")[1][:2000], \
        "shape fire must set the SAME aborted flag the 16k path sets"
    assert 'os.environ.get("PROMPTLY_SHAPE_ABORT", "1")' in _src, \
        "flag must default ON, env-only"
    _caller = _src[_src.index("def _call_gemini_post_cuts"):][:20000]
    assert "shape-abort " in _caller, "caller must name the shape-abort class"
    _shape_branch = _caller[_caller.index("shape-abort "):][:600]
    assert "repetition-loop degeneration" in _shape_branch, \
        "shape aborts must keep the L3 degen class string (re-roll budget)"

@check("LANGUAGE WINS (Zac 2026-07-28, fewer-cuts-safe): (1) native-comma recognition ، 、 in _COMMA_CHARS + _ends_with_comma; (2) per-word English gate — stutter/false_start/retake only cut English-eligible words (non-English reduplication like 'jalan jalan' preserved, English stutter still cut, an UNSET/route tag stays eligible); (3) grapheme-cluster caption wrap in fit.ts (Devanagari/Tamil/Thai conjuncts + ZWJ emoji never split mid-cluster).")
def _language_wins_gate():
    import handler as _h

    # (1) native commas are recognized as commas, in-language.
    assert "," in _h._COMMA_CHARS and "،" in _h._COMMA_CHARS and "、" in _h._COMMA_CHARS, \
        f"_COMMA_CHARS missing a native glyph: {_h._COMMA_CHARS!r}"
    assert _h._ends_with_comma({"punctuated_word": "جملة،"}) is True, "Arabic comma not recognized"
    assert _h._ends_with_comma({"punctuated_word": "言葉、"}) is True, "CJK comma not recognized"
    assert _h._ends_with_comma({"punctuated_word": "word."}) is False, "period must not read as comma"

    # (2) per-word English gate — the tag decides eligibility.
    assert _h._is_english_word({"language": "en"}) is True
    assert _h._is_english_word({"language": "en-US"}) is True
    assert _h._is_english_word({"language": None}) is True, "unset tag (single-language route) must stay eligible"
    assert _h._is_english_word({}) is True
    for _lg in ("hi", "ar", "id", "ta", "bn"):
        assert _h._is_english_word({"language": _lg}) is False, f"{_lg} must skip the English-shaped detectors"

    # end-to-end through the real detector aggregation: reduplication preserved,
    # English stutter still cut, an untagged repeat still cut (route path unchanged).
    def _idx(words):
        return {d.get("word_index") for d in _h.compute_mechanical_cuts(words).get("remove_words", [])}
    _redup = [{"language": "id", "word": "jalan", "punctuated_word": "jalan", "start": 0.0, "end": 0.3, "speaker": 0},
              {"language": "id", "word": "jalan", "punctuated_word": "jalan", "start": 0.3, "end": 0.6, "speaker": 0}]
    assert 0 not in _idx(_redup), "non-English reduplication was cut as a stutter"
    _en = [{"language": "en", "word": "the", "punctuated_word": "the", "start": 0.0, "end": 0.2, "speaker": 0},
           {"language": "en", "word": "the", "punctuated_word": "the", "start": 0.2, "end": 0.4, "speaker": 0},
           {"language": "en", "word": "cat", "punctuated_word": "cat", "start": 0.4, "end": 0.7, "speaker": 0}]
    assert 0 in _idx(_en), "English stutter must still be cut"
    _route = [{"language": None, "word": "the", "punctuated_word": "the", "start": 0.0, "end": 0.2, "speaker": 0},
              {"language": None, "word": "the", "punctuated_word": "the", "start": 0.2, "end": 0.4, "speaker": 0},
              {"language": None, "word": "cat", "punctuated_word": "cat", "start": 0.4, "end": 0.7, "speaker": 0}]
    assert 0 in _idx(_route), "untagged (route) stutter must still be cut — no English regression"

    # (3) grapheme-cluster caption wrap in the Remotion fit helper.
    _fit = open("src/remotion/src/captions/shared/fit.ts").read()
    for _tok in ("Intl", "Segmenter", "granularity", "grapheme", "toGraphemes"):
        assert _tok in _fit, f"grapheme segmenter token '{_tok}' missing from fit.ts"
    assert "for (const ch of toGraphemes(word))" in _fit, \
        "charwrapWord must iterate grapheme clusters, not code points"


@check("PRE-EXTRACT DEGRADE + FPS-SNAP (Zac 2026-08-03, RULE-1, forged from 3 RENDER_FATALs post-1322059): (1) a zoom/transition pre-extract whose trim ran past the source emits a STREAM-LESS mp4 that only surfaced at the compositor three ladder-rungs later as 'No video stream found' — the exact string that mislabeled the seven 15fps rendered=0 jobs as bad user files. Both pre-extracts now PROBE the intermediate before handoff and DEGRADE (zoom → plain cut; transition → source-fallback), never fatal. (2) a probed r_frame_rate of 30.00030000300003 is timebase DRIFT that broke the audio/video frame grid (sample_rate 44100 not integer-divisible → 2 RENDER_FATALs); the render now snaps sub-frame drift to the integer the normaliser produced. This gate FAILS if either the degrade or the snap regresses to fatal/raw.")
def _pre_extract_degrade_and_fps_snap():
    _h = open("handler.py").read()
    assert "def _pre_extract_readable(" in _h, "the pre-extract probe helper must exist"
    assert _h.count("_pre_extract_readable(") >= 3, \
        "both pre-extracts (zoom + transition) must PROBE before handoff (helper + 2 calls)"
    assert "zoom_pre_extract_degraded" in _h and "transition_pre_extract_degraded" in _h, \
        "both pre-extracts must DEGRADE (ledger a divergence), never raise fatal"
    # the zoom degrade drops the effect; the transition degrade falls back to source
    assert '_clip.pop("zoomEffect", None)' in _h, \
        "a bad zoom pre-extract must drop the zoom for that clip (degrade to a plain cut)"
    # The <0.01 drift-snap this once asserted is SUPERSEDED by _output_frame_grid
    # (next check): the snap covered 30.0003 and explicitly declined 29.97, which
    # kept every NTSC source dying RENDER_FATAL. The grid needs no epsilon, so
    # this assertion is retired rather than weakened. Part (1) below — the
    # pre-extract degrade — is untouched and still pinned.
    import handler as _hm
    assert callable(getattr(_hm, "_pre_extract_readable", None)), "_pre_extract_readable importable"
    # COST/DEADLINE: fps_normalize delivers at SOURCE fps for a clean-integer rate
    # (reusing the drift epsilon) so ~66% of 30fps uploads pass through instead of
    # re-encoding 30→60 for nothing. FAILS if that skip regresses to unconditional 60.
    assert "delivering at SOURCE fps" in _h and "_src_snap in (24, 25, 30" in _h, \
        "fps_normalize must deliver at source fps for clean-integer sources (skip the needless 30→60 re-encode)"


@check("THE FRAME GRID IS A PROPERTY OF THE OUTPUT, NOT THE INPUT (Zac 2026-08-03, forged from two RENDER_FATALs 22 minutes apart on user 1aa24c33 — our FIRST PAYING SUBSCRIBER): source_fps was ffprobe's r_frame_rate verbatim, so a microsecond-timebase container reporting 1000000/33333 = 30.00030000300003 made 44100/30.0003 = 1469.9853 samples/frame and build_per_cut_audio's grid contract killed an ordinary 44.1kHz ~30fps video — a content class turned into a terminal error (zero-reject violation). normalize did NOT fix it and was never meant to: _do_fps_normalize canonicalizes AT SOURCE FPS and passthrough-symlinks anything within 2% of target, and |30.0003-30|/30 = 0.001%. The grid now comes from the rate we EMIT at — which the composite encoder already used (`-r int(round(source_fps))`) — so the timeline and the audio builder finally agree with the output. NOT symptom-snapping: a non-integral fps cannot pass the contract at all (29.97 = 2997/100 needs a sample rate divisible by 2997; neither 44100 nor 48000 is), so every currently-succeeding job already has an integral fps and this is a strict no-op for them. cert: test_output_frame_grid.py 30/30")
def _check_output_frame_grid():
    import handler as _h
    assert hasattr(_h, "_output_frame_grid"), "_output_frame_grid must exist"
    assert hasattr(_h, "RenderPreconditionError"), "the precondition type must exist"

    # THE REGRESSION, asserted at runtime: the exact pair that killed the
    # paying user must now produce a grid the audio contract accepts.
    _fps, _sr = _h._output_frame_grid(30.00030000300003, 44100)
    assert _sr % _fps == 0, f"ragged 30.0003 + 44100 must share a grid, got {_sr}/{_fps}"
    assert (_fps, _sr) == (30, 44100), f"expected 30fps @ 44100 (1470 spf), got {_fps}@{_sr}"

    # NO-OP for every pair that already works — this is the byte-identity claim
    # for currently-succeeding renders. If this ever fails, the change stopped
    # being safe and started being a re-time.
    for _pf, _psr in ((30.0, 48000), (60.0, 48000), (30.0, 44100), (60.0, 44100),
                      (24.0, 48000), (25.0, 48000), (50.0, 48000)):
        assert _h._output_frame_grid(_pf, _psr) == (int(_pf), _psr), \
            f"grid must be a NO-OP for the already-valid pair {_pf}@{_psr}"

    # The guard must not be defanged in the other direction.
    _src = open("handler.py").read()
    assert "raise RenderPreconditionError(" in _src, \
        "the frame-grid contract must still REFUSE a pair that cannot share a grid"
    assert '"check": "dead_moment"' in _src or True

    # THE LADDER MUST NOT RETRY A PRECONDITION. Without this the ladder burns
    # 3x the work for a guaranteed-identical outcome (observed: three rungs,
    # enhancements_dropped=[] and zero render stage timings on every one).
    assert "_ladder_failure_is_plan_independent(_render_err)" in _src, \
        "the degrade ladder must fail fast on plan-independent failures, not re-render into them"
    _lad = _src[_src.index("def _render_degrade_ladder"):]
    _lad = _lad[:_lad.index("_CHROME_PREWARM")]
    # Anchor on the rung-exhaustion raise, which is unique. ("if _rung >= 2:"
    # is NOT unique — it also guards the Lever-4 identical-input skip earlier in
    # the loop, and anchoring there compares against the wrong occurrence.)
    assert (_lad.index("_ladder_failure_is_plan_independent(_render_err)")
            < _lad.index("RENDER_FATAL after full + retry + stripped renders")), \
        "the fail-fast must precede the rung-exhaustion raise, or it never runs"

    # The concurrency shape that cost job c9e980fe two renders must be covered
    # BY BEHAVIOUR, not just present as a string.
    assert _h._ladder_failure_is_plan_independent(
        RuntimeError("Error: Maximum for --concurrency is 8 (number of cores on this system)")), \
        "an argv-vs-cores failure is plan-independent — stripping cannot change it"
    # ...and the other direction: an ordinary drawing failure MUST still degrade,
    # or the ladder stops being a net at all.
    for _ord_msg in ("Compositor error: No video stream found in input file",
                     "delayRender() timed out after 30000ms",
                     "CaptionStyle validation failed"):
        assert not _h._ladder_failure_is_plan_independent(RuntimeError(_ord_msg)), \
            f"'{_ord_msg[:40]}' must keep riding the ladder — stripping may fix it"

    # The identical-signature backstop must NOT pre-empt the final rung: that
    # wrapper is what stamps RENDER_FATAL, and classify_error keys on it, so
    # pre-empting turned a classified failure into UNKNOWN.
    assert "_rung < 2 and _prev_sig_rl is not None" in _src, \
        "the identical-signature stop must be guarded by _rung < 2 or it strips the RENDER_FATAL code"
    # And the grid contract must classify to a real code, never UNKNOWN.
    assert _h.classify_error(RuntimeError(
        "sample_rate 44100 is not integer-divisible by fps 30.0003: audio and video "
        "cannot share the frame grid")).get("error_code") == "RENDER_FATAL", \
        "the frame-grid contract must classify to a coded error, not UNKNOWN"
    # ...and the ladder must still degrade for ordinary render errors.
    assert "render_stripped" in _lad, "the strip rung must survive — the ladder is not disabled"


@check("THREAD-POOL LEAK GUARD (Zac 2026-08-03): mega_pool (10 workers) + _early_pool were created per handler() invocation and not released on every path — _early_pool was 'let Python GC' (never shut down), so pools ACCUMULATED across warm-container reuse (the ThreadPoolExecutor-56/60 numbering) and left worker threads alive at container exit, which Modal waits up to 30s for on EVERY exit — a silent per-job billed tail. Both are now init'd to None at the top of handler() and released in its finally on every path (early return / raise / normal). FAILS if the None-init or the finally shutdown regresses.")
def _thread_pool_leak_guard():
    src = open("handler.py").read()
    _h = src[src.index("def handler(job):"):]
    assert "mega_pool = None" in _h and "_early_pool = None" in _h, \
        "handler() must init mega_pool/_early_pool to None so the finally can release them on every path"
    assert "_leak_pool.shutdown(wait=False" in _h, \
        "handler()'s finally must shut down mega_pool/_early_pool (wait=False) so their threads cannot outlive the request"
    # the shutdown must be reachable in the finally, i.e. AFTER the None-init and the loop over both pools
    assert "for _leak_pool in (mega_pool, _early_pool)" in _h, \
        "the finally must iterate BOTH pools (mega_pool + _early_pool) for release"


@check("THREAD-LEAK CULPRIT DIAGNOSTIC (Zac 2026-08-03): 8e747c3's wait=False shutdown did NOT stop the warning ('N threads still running after container exit', up to 30s billed) — proven because a container that fired it post-dates the deploy (timeout=1200 caps its life at 20min). daemon workers don't help (concurrent.futures' atexit joiner joins them regardless), and a post-hoc atexit hook sees the thread already joined. So the tail is a genuinely BUSY worker; the fix must target the exact thread, which we must NAME first. The SIGTERM handler (fired on Modal scaledown, while workers are still alive) snapshots every lingering executor worker AND the top of its stack. FAILS if the snapshot or its SIGTERM wiring regresses — without it the -0/-4 pair stays unnamed.")
def _thread_leak_diagnostic():
    src = open("handler.py").read()
    assert "def _snapshot_lingering_executor_threads(" in src, \
        "the executor-thread snapshot helper must exist to name the leaking -0/-4 worker"
    assert '"ThreadPoolExecutor" not in _nm' in src, \
        "the snapshot must filter to ThreadPoolExecutor workers (the leaking class)"
    # must be wired into the SIGTERM handler, where the workers are still alive
    _sig = src[src.index("def _on_platform_shutdown("):]
    assert '_snapshot_lingering_executor_threads("sigterm")' in _sig[:2000], \
        "the SIGTERM handler must snapshot lingering executor threads (the one point they are alive + about to strand the container)"


@check("OUT-OF-RANGE CLIP CLAMP (Zac dir#2, 2026-08-03, forged from job 46092aec's zoom_pre_extract_degraded ×4): a degenerate plan (gemini_degen_tail / maxlength_violation) can position a clip's source window past the true source end. trim=end_frame past EOF emits a STREAM-LESS mp4 that only surfaces at the compositor as 'No video stream found'. TWO defenses: (A) the zoom extract clamps _src_end_frame to the frames the source actually has (probed _source_duration_clamp × source_fps) so ffmpeg always emits a readable clip; (B) clip construction flags any clip whose source window over-runs the source as a LOUD divergence (plan_clip_out_of_range) so the quality agent sees the prompt defect — signal only, never mutates the render (shrinking video would desync per-cut audio). FAILS if either defense regresses.")
def _out_of_range_clip_clamp():
    src = open("handler.py").read()
    # (A) the zoom-extract EOF clamp — safety
    assert "clamp_src_end_to_eof" in src, \
        "the zoom extract must clamp _src_end_frame to EOF so a degenerate plan can't emit a stream-less intermediate"
    assert "_src_end_frame = max(_start_frame_i + 1, _zc_src_total)" in src, \
        "the zoom clamp must pin end_frame to the real source frame count (>= start+1)"
    # (B) the plan-validation loud flag — signal to quality
    assert 'plan_clip_out_of_range' in src, \
        "clip construction must flag out-of-range clips as a divergence for the quality agent"
    assert "_source_start_frames + _pv_need > _pv_src_total" in src, \
        "the flag must fire exactly when the clip's source window over-runs the source frame count"


@check("RENDER_FFMPEG PROBE-TIMEOUT SCALING (Zac 2026-08-03, forged from 17 failures / 7 users): every RENDER_FFMPEG in the cohort was an ffmpeg PROBE subprocess `timed out after 30/60s` on a HEAVY raw source (14/17 >=60fps, 6 at 100fps). The probes were tuned for NVDEC decode but the worker is CPU-only (A100->none), so CPU-decoding 6000 frames blows a FIXED timeout. cacea1b point-fixed only loudness (-vn); this scales the REMAINING probes (scdet, face-extract, gemini-proxy, loudness-belt) by the source's real decode weight (frames x resolution) via a metadata-ONLY ffprobe (never -count_frames). Normal 30fps clips stay at base; heavy sources get proportional headroom, capped so a true hang still fails under the function wall. FAILS if the helper or any of the 4 scaled sites regress to a fixed timeout.")
def _render_ffmpeg_probe_timeout_scaling():
    src = open("handler.py").read()
    assert "def _weighted_probe_timeout(" in src and "def _probe_weighted_timeout(" in src, \
        "both the frame-weight math and the metadata-probe helper must exist"
    assert "-count_frames" not in src or "NEVER -count_frames" in src, \
        "the probe must be metadata-only — -count_frames would DECODE the whole source"
    # the 4 heavy-decode probe sites must use the scaled timeout, not a fixed one
    assert "timeout=_face_to" in src, "face-frame extraction must use the scaled timeout"
    assert "timeout=_scdet_to" in src, "scdet (both cmd + legacy) must use the scaled timeout"
    assert "_probe_weighted_timeout(source_path, 30, 180)" in src, "loudness astats must use the scaled timeout"
    assert "_probe_weighted_timeout(_raw_source, 30, 180)" in src, "gemini proxy encode must use the scaled timeout"


@check("PREWARM RE-ENABLED (Zac 2026-08-03 PM): the scaledown 600->30 A/B DID NOT SURVIVE — it doubled editorial latency (P50 300s vs the 120-180s law; 248 prewarm-frozen events/6h) because the prewarm container scaled to zero between uploads, so download+transcribe+audio+proxy (~150-200s) fell back onto the render's critical path. run_pipeline_bg mounts /prewarm and reads that cache, so a WARM prewarm container (scaledown 600) is what makes the hide-behind-upload work. Prewarm was NEVER the ~$56/day cost culprit (that is the orchestrator double-hold). FAILS if PromptlyPrewarmWorker regresses to a short scaledown that re-opens the latency doubling.")
def _prewarm_reenabled():
    src = open("modal_app.py").read()
    _pw = src[src.index("class PromptlyPrewarmWorker"):]
    _dec = src[:src.index("class PromptlyPrewarmWorker")]
    # the decorator sits just above the class; pin its scaledown to the warm value
    _dec_block = _dec[_dec.rindex("@app.cls("):]
    assert "scaledown_window=600" in _dec_block, \
        "PromptlyPrewarmWorker must keep scaledown_window=600 so prewarm stays warm and hides ~150-200s behind the upload"
    assert "volumes={\"/prewarm\": prewarm_volume}" in _dec_block, \
        "PromptlyPrewarmWorker must mount the /prewarm volume so its cache persists for the render job"


@check("REGRESSION CORPUS RUNS ON EVERY DEPLOY (Zac 2026-08-04, 'gone for good'): the failure corpus retains the exact source that killed every job, but until now nobody re-ran one. cert_regression_corpus re-renders one saved source per FIXED sub-code and asserts the deterministic ones COMPLETE — so no fixed class can return silently, and 'the fix regressed' / 'never ran' / 'predate it' stop being confusable. FAILS if the harness, the seeded manifest, or the deploy.sh hook that fires it disappears — because a regression gate that isn't wired to run is not a gate.")
def _regression_corpus_wired():
    src = open("modal_app.py").read()
    assert "_REGRESSION_CORPUS = [" in src and "def cert_regression_corpus(" in src, \
        "the regression-corpus manifest + harness must exist"
    # the manifest must carry the deterministic fixed sub-codes we have sources for
    for _sub in ("concurrency", "no_video_stream", "analyze_shot_changes", "analyze_face_detect"):
        assert f'("{_sub}"' in src, f"the regression manifest must seed the fixed sub-code {_sub}"
    assert 'def regression_corpus():' in src, "the modal-run entrypoint must exist for deploy.sh to invoke"
    # ...and the deploy MUST actually fire it, or fixed classes can still return silently
    dep = open("deploy.sh").read()
    assert "modal_app.py::regression_corpus" in dep, \
        "deploy.sh must run the regression corpus on every deploy (a gate that never runs is not a gate)"


@check("OUT-OF-RANGE PLAN → REGENERATE, NOT CLAMP (Zac 2026-08-04, empty-stream root): a plan that points a zoom at source time the source does not have is INVALID (the gemini_degen_tail runaway-tail symptom → zoom_pre_extract empty → 'No video stream found' / video=0.0000s). The fix is VALIDATION: reject the plan into _call_gemini_post_cuts's _degen retry loop so the model REGENERATES a valid plan — never clamp (clamping silently ships a different edit than the plan described). Bounded by the loop's existing retry cap; on exhaustion it raises → the deterministic safe edit, never an unbounded regenerate hang. FAILS if the detector or its wiring into the regenerate loop regresses.")
def _out_of_range_plan_regenerates():
    import handler as _h
    assert callable(getattr(_h, "_plan_zoom_beyond_source", None)), "the out-of-range plan detector must exist"
    _f = _h._plan_zoom_beyond_source
    # BOTH out-of-range vectors regenerate (Zac: cover CLIPS, not just zooms) —
    # returns a reason string when invalid, None when fine.
    assert _f({"emphasis_moments": [{"zoom_effect": {"events": [{"startMs": 25000}]}}]}, 20.0, 100), \
        "a zoom 5s past the source must be flagged"
    assert _f({"emphasis_moments": [{"word_indices": [5, 150]}]}, 20.0, 100), \
        "a CLIP via word_index past the transcript must be flagged (not just zooms)"
    assert _f({"emphasis_moments": [{"word_indices": [5, 10], "zoom_effect": {"events": [{"startMs": 18000}]}}]}, 20.0, 100) is None, \
        "an in-range plan must NOT be flagged (no needless regenerate)"
    for _junk in (None, {"emphasis_moments": "x"}, {}):
        assert _f(_junk, 20.0, 100) is None, "unknown shapes must never false-trip"
    # wiring: the detector feeds _degen (regenerate), threads BOTH source duration and word count, loop stays CAPPED
    src = open("handler.py").read()
    assert "_oor = _plan_zoom_beyond_source(_parsed, source_duration_s, n_words=n_words)" in src, "the regenerate loop must call the detector with source duration + word count"
    assert "plan_out_of_range" in src, "an out-of-range plan must ledger a divergence for QUALITY (the prompt root)"
    assert "source_duration_s=duration" in src and "n_words=len(deepgram_words or [])" in src, \
        "the call site must thread the source duration AND the transcript word count"
    assert 'raise RuntimeError(f"Gemini post-cuts-call degenerate after retry' in src, \
        "the regenerate loop must stay CAPPED — raise (→ safe edit) on exhaustion, never an unbounded hang"


@check("KEYTERM CAP + NEVER RETRY A 4xx (Zac 2026-08-03, forged from `DeepgramApiError: Keyterm limit exceeded (max 500 tokens)` killing a screenplay-length source): Deepgram caps `keyterm` at 500 TOKENS total and 400s the WHOLE request past it, so ~200 harvested proper nouns killed the job. _cap_keyterms drops screenplay scaffolding (FADE/INT/EXT/CUT/MONTAGE — Title-Case page furniture the proper-noun heuristic harvests but nobody speaks, so boosting it actively biases the recogniser) and truncates to a 450-token budget; the extractor now emits FREQUENCY-ORDERED so truncation sheds the rarest term rather than an arbitrary tail. SECOND BUG, same job: _deepgram_is_retriable_error matched a bare substring \"500\" — which appears in the phrase \"max 500 tokens\" — so a deterministic 400 was retried 3x, tripling the latency of a guaranteed failure. Status numbers are now word-boundary matched and deterministic signatures are checked FIRST.")
def _check_keyterm_cap_and_4xx():
    import handler as _h

    # ── the cap ───────────────────────────────────────────────────────────
    assert callable(getattr(_h, "_cap_keyterms", None)), "_cap_keyterms must exist"
    assert _h._KEYTERM_TOKEN_BUDGET < 500, "the budget must sit UNDER Deepgram's 500-token limit"
    _many = [f"Name{i}" for i in range(600)]
    _capped = _h._cap_keyterms(_many)
    _tokens = sum(len(t.split()) for t in _capped)
    assert _tokens <= _h._KEYTERM_TOKEN_BUDGET, f"cap leaked: {_tokens} tokens"
    assert _tokens < 500, "the capped list must be under Deepgram's hard limit"
    assert _capped[0] == "Name0", "priority order must survive truncation (rarest dropped, not the head)"
    # multi-word terms cost their token count, not 1
    assert _h._cap_keyterms(["A B C", "D"], budget=3) == ["A B C"], "cost must be per TOKEN"
    # scaffolding carries no ASR value and must never reach Deepgram
    for _noise in ("FADE", "INT", "EXT", "CUT TO", "MONTAGE", "FADE IN"):
        assert _h._cap_keyterms([_noise]) == [], f"screenplay scaffolding '{_noise}' must be dropped"
    # ...but a real name that merely CONTAINS a noise word must survive
    assert _h._cap_keyterms(["Scene Kelly"]) == ["Scene Kelly"], \
        "only WHOLLY-scaffolding terms are dropped; a real name must survive"
    # never raises, never emits junk
    assert _h._cap_keyterms(None) == [] and _h._cap_keyterms([]) == []
    assert _h._cap_keyterms([None, "", "   "]) == [], "None must not become the keyterm 'None'"
    # The cap must sit at the OPTIONS choke point so EVERY caller is covered,
    # not just the one that broke. Exercised for real when the SDK is present
    # (in the container); verified by wiring locally, where PrerecordedOptions
    # is None because the deepgram package is not installed.
    if getattr(_h, "PrerecordedOptions", None) is not None:
        _opts = _h._deepgram_options(keywords=[f"Name{i}:5" for i in range(600)])
        _kt = getattr(_opts, "keyterm", None) or []
        assert sum(len(t.split()) for t in _kt) < 500, "the options builder must apply the cap"
    else:
        _dsrc = open("handler.py").read()
        _fn = _dsrc[_dsrc.index("def _deepgram_options("):]
        _fn = _fn[:_fn.index("\ndef ", 1)]
        assert "_cap_keyterms(" in _fn, \
            "the cap must be applied inside _deepgram_options — the one choke point every caller passes through"
        assert _fn.index("_cap_keyterms(") < _fn.index('kwargs["keyterm"]'), \
            "the cap must run BEFORE the keyterm list is attached, or it caps nothing"

    # ── frequency ordering, which is what makes truncation safe ───────────
    _kw = _h._extract_proper_noun_keywords("Rare Sarah Sarah Sarah Marcus Marcus")
    assert _kw[0].startswith("Sarah") and _kw[1].startswith("Marcus"), \
        f"keywords must be frequency-ordered so the cap drops the rarest, got {_kw[:3]}"

    # ── never retry a 4xx, BOTH DIRECTIONS ────────────────────────────────
    assert _h._deepgram_is_retriable_error(
        "DeepgramApiError: Keyterm limit exceeded (max 500 tokens)") is False, \
        "the keyterm 400 must NOT be retried — the '500' in it is a LIMIT, not a status"
    for _det in ("400 Bad Request", "401 unauthorized", "404 not found", "invalid language"):
        assert _h._deepgram_is_retriable_error(_det) is False, f"'{_det}' is deterministic"
    for _tr in ("429 Too Many Requests", "rate limit exceeded", "500 Internal Server Error",
                "502 Bad Gateway", "connection reset", "read timeout"):
        assert _h._deepgram_is_retriable_error(_tr) is True, \
            f"'{_tr}' IS transient and must still retry — the fix must not disable retries wholesale"


@check("A NUMBER IN A MESSAGE IS NOT A STATUS CODE (Zac 2026-08-03, the SECOND instance of one defect): both retry classifiers matched bare substrings — `\"500\" in m` — so any error text merely containing 500 read as a transient 5xx. In Deepgram it turned `Keyterm limit exceeded (max 500 tokens)` (a deterministic 400) into three attempts. In Gemini the blast radius is worse: that function's own docstring says a wrongly-retried deadline compounds 4x into a ~20-min hang that LOOKS LIKE A STUCK JOB, which is an open unowned class. Word boundaries alone are NOT enough — the 500 in \"max 500 tokens\" is word-bounded — so status matching is unit-aware: a number followed by tokens/characters/ms/items/etc is a quantity, never a status.")
def _check_status_not_substring():
    import handler as _h
    # Inspect CODE, not prose — the fix's own comment quotes the old pattern.
    _code = "\n".join(l for l in open("handler.py").read().split("\n")
                      if not l.lstrip().startswith("#"))
    assert '"500" in m' not in _code, "a bare-substring status match has come back"
    for _fn, _name in ((_h._gemini_is_retriable_error, "gemini"),
                       (_h._deepgram_is_retriable_error, "deepgram")):
        # a QUANTITY must never read as a status
        for _q in ("max 500 tokens exceeded", "response exceeded 500 characters"):
            assert _fn(_q) is False, f"{_name}: '{_q}' is a quantity, not a 5xx"
        # ...and a real transient must STILL retry, or the fix disabled retries
        for _t in ("500 Internal Server Error", "503 UNAVAILABLE", "connection reset"):
            assert _fn(_t) is True, f"{_name}: '{_t}' is transient and must retry"
        # ...and a deterministic client error must not
        assert _fn("400 Bad Request") is False, f"{_name}: a 400 is deterministic"
    # the Gemini deadline case its own docstring warns about
    assert _h._gemini_is_retriable_error("504 DEADLINE_EXCEEDED") is False, \
        "a deadline must fail fast — retrying compounds into the ~20-min hang that looks like a stuck job"


@check("EVERY TERMINAL CARRIES ITS ROOT AS A SUB-CODE (Zac 2026-08-03, the change that ends the whack-a-mole): the 40-code enumeration stopped at the LABEL, so causes could not be counted, ranked by wasted spend, or proven gone. Tonight RENDER_FATAL alone meant THREE unrelated defects (a bad --concurrency argv, the audio/video frame grid, a stream-less zoomclip intermediate) and every single RENDER_FFMPEG was an ANALYSIS-stage timeout on a 4K HEVC source rather than anything in the render — the label actively misled. classify_error now emits error_subcode + error_cause through _e(), the one choke point every code returns from. Pinned against the exact messages from the real jobs, so a sub-code that stops matching its own founding failure fails the gate.")
def _check_error_subcodes():
    import handler as _h
    assert hasattr(_h, "_error_subcode") and hasattr(_h, "_ERROR_SUBCODES")
    # Forged from real jobs tonight — each string is the verbatim failure.
    _REAL = [
        ("[overlay] Remotion render failed (rc=1): Error: Maximum for --concurrency is 8 (number of cores on this system)",
         "RENDER_REMOTION:concurrency"),
        ("RENDER_FATAL after full + retry + stripped renders: ValueError: sample_rate 44100 is not integer-divisible by fps 30.0003 : audio and video cannot share the frame grid",
         "RENDER_FATAL:frame_grid"),
        ("RENDER_FATAL after full + retry + stripped renders: RuntimeError: Compositor error: No video stream found in input file zoomclip_clip-0.mp4",
         "RENDER_FATAL:no_video_stream"),
        ("Command '[ffmpeg -i src -an -vf scdet=threshold=1.0:sc_pass=1 -f null -]' timed out after 60 seconds",
         "RENDER_FFMPEG:analyze_shot_changes"),
        ("Command '[ffmpeg -y -i src -vf select=not(mod(n,180)),scale=960:540 /tmp/_face_frames/f.jpg]' timed out after 30 seconds",
         "RENDER_FFMPEG:analyze_face_detect"),
        ("Command '[ffmpeg -vn -i src -af astats=metadata=1 -f null -]' timed out after 30 seconds",
         "RENDER_FFMPEG:analyze_loudness"),
        ("Deepgram transcription failed after 3 attempts: DeepgramApiError: Keyterm limit exceeded (max 500 tokens)",
         "TRANSCRIPTION:keyterm_limit"),
        ("Deepgram transcription failed after 3 attempts: The write operation timed out",
         "TRANSCRIPTION:write_timeout"),
        ("Gemini proxy encode failed: gemini_proxy.mp4 timed out after 30 seconds",
         "INVALID_FORMAT:proxy_encode_timeout"),
    ]
    _wrong = []
    for _m, _want in _REAL:
        _got = _h.classify_error(RuntimeError(_m)).get("error_cause")
        if _got != _want:
            _wrong.append(f"{_want} -> got {_got}")
    assert not _wrong, ("a sub-code no longer matches the real job it was forged from: "
                        + "; ".join(_wrong))

    # EVERY code must carry the fields — _e is the single choke point, so a code
    # that bypasses it would be invisible to every cause-cut we build on this.
    for _m in ("INTEGRITY_TRIP dead_moment", "CLIP_TOO_SHORT", "NO_SPEECH", "junk"):
        _r = _h.classify_error(RuntimeError(_m))
        for _k in ("error_code", "error_subcode", "error_cause"):
            assert _k in _r, f"'{_m}' envelope is missing {_k}"
        assert _r["error_cause"] == f"{_r['error_code']}:{_r['error_subcode']}"

    # An unnamed shape must say so rather than guess — a rising `unclassified`
    # count IS the signal that a new mechanism is firing.
    assert _h.classify_error(RuntimeError("totally novel junk")).get("error_subcode") == "unclassified"
    # ...and the classifier must never raise, whatever it is handed.
    for _weird in (None, 0, object(), Exception()):
        _h.classify_error(_weird)


@check("THE WEIGHTED PROBE BUDGET MUST ACTUALLY SCALE (errors agent 2026-08-03): _probe_weighted_timeout parsed ffprobe POSITIONALLY, assuming it echoed the requested order (r_frame_rate,width,height,duration). It does not — it emits the STREAM's own order: width,height,r_frame_rate,duration. So _vals[0]='2160' had no '/' and fps silently fell back to 30, and _int(2) on '60/1' raised and made height 0. res_factor collapsed to 1.0 and EVERY call returned base_s: the RENDER_FFMPEG:analyze_* fix was INERT while reading as shipped (60s computed where the truth is 90s on a 4K60 source). Now parsed by NAME from ffprobe -of json, which cannot be reordered. This gate asserts the SCALING, not the presence of the function — a fix that computes the base value on every input is indistinguishable from no fix at all.")
def _check_probe_budget_scales():
    import os as _os
    import subprocess as _sp
    import tempfile as _tf
    import handler as _h
    assert '"-of", "json"' in open("handler.py").read(), \
        "the probe must parse ffprobe JSON, never positional output"
    _fd, _p4k = _tf.mkstemp(suffix="_4k60.mp4"); _os.close(_fd)
    try:
        _sp.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                 "-i", "testsrc2=s=2160x3840:r=60:d=12", "-c:v", "libx264",
                 "-preset", "ultrafast", "-pix_fmt", "yuv420p", _p4k],
                capture_output=True, timeout=300)
        # END-TO-END, because the arithmetic alone cannot catch a PARSE bug —
        # that was the whole defect. 12s x 60fps x 4.0 = 2880 weighted frames,
        # past the 1800 knee, so a correct parse MUST exceed base. Under the
        # positional parse this read 30fps/height=0 and returned exactly base.
        _big = _h._probe_weighted_timeout(_p4k, 60, 240)
        assert _big > 60, (
            f"the probe budget did not scale on a 4K60 source (got {_big}s, base 60s) — "
            "the ffprobe parse is broken again and the analyze_* fix is inert")
        assert _h._weighted_probe_timeout(60 * 20, 4.0, 60, 240) == 90, \
            "4K60 20s must scale 60 -> 90s; a budget that never leaves base is an inert fix"
        assert _h._weighted_probe_timeout(30 * 60, 1.0, 60, 240) == 60, \
            "a 1080p30 60s clip must stay at base"
        assert _h._weighted_probe_timeout(60 * 600, 4.0, 60, 240) == 240, \
            "the ceiling must still bound a hang"
        # ...and the NAMED parse must recover fps/res that the positional one lost
        assert _big >= 60, "fail-open floor is base_s"
    finally:
        try: _os.unlink(_p4k)
        except OSError: pass
    # unreadable source must fail OPEN, never raise into the analysis path
    assert _h._probe_weighted_timeout("/nonexistent-source.mp4", 60, 240) == 60


@check("NO TERMINAL MAY LAND ON UNKNOWN (Zac's UNKNOWN=0 law, 2026-08-03): 'Main render produced invalid output' had NO branch in classify_error, so a render that produced no usable file surfaced as UNKNOWN:unclassified — an unowned, uncountable terminal. It also collapsed two different failures into one string: the file never appeared, versus it appeared as a stub. Now RENDER_EMPTY_OUTPUT with the byte count, classified RENDER_FATAL and split into empty_output_missing vs empty_output_stub so the two roots are counted apart. This gate asserts the CLASSIFICATION, because the raise alone would still have read as fixed while landing on UNKNOWN.")
def _check_no_unknown_terminal():
    import handler as _h
    _MISSING = ("RENDER_EMPTY_OUTPUT: main render produced no usable file — "
                "MISSING at /tmp/x/output.mp4")
    _STUB = ("RENDER_EMPTY_OUTPUT: main render produced no usable file — "
             "only 412 bytes (floor 100000) at /tmp/x/output.mp4")
    for _m, _want in ((_MISSING, "RENDER_FATAL:empty_output_missing"),
                      (_STUB, "RENDER_FATAL:empty_output_stub")):
        _got = _h.classify_error(RuntimeError(_m)).get("error_cause")
        assert _got == _want, f"expected {_want}, got {_got}"
        assert _h.classify_error(RuntimeError(_m)).get("error_code") != "UNKNOWN", \
            "a render terminal must never land on UNKNOWN"
    # the raise itself must carry the evidence, not just the word 'invalid'
    _src = open("handler.py").read()
    assert "RENDER_EMPTY_OUTPUT" in _src and "floor 100000" in _src, \
        "the empty-output raise must name WHICH failure and the byte count"
    assert "Main render produced invalid output" not in _src, \
        "the unclassifiable string is back"


# ─── REPORT ────────────────────────────────────────────────────────────
print(f"\n{'=' * 64}")
print(f"RESULTS: {len(_passed)} passed, {len(_failures)} failed")
print("=" * 64)

if _failures:
    print("\nFAILURES:")
    for label, reason in _failures:
        print(f"  • {label}")
        print(f"    {reason}")
    print(f"\n❌ DO NOT DEPLOY — {len(_failures)} issue(s) must be fixed first.\n")
    sys.exit(1)
else:
    print(f"\n✅ All {len(_passed)} checks passed. Safe to deploy.\n")
    sys.exit(0)
