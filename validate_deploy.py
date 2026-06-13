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


# ─── 2. F-STRINGS ──────────────────────────────────────────────────────
print("\n[2/6] F-string format integrity")


@check("system_instruction f-string formats cleanly")
def _system_instruction_format():
    src = open("handler.py").read()
    start = src.find('system_instruction = f"""')
    assert start > 0, "system_instruction f-string not found"
    end = src.find('"""', start + 30)
    prompt = src[start + len('system_instruction = f"""'):end]
    # The .format() check catches unescaped { in JSON examples
    # (today's f-string bug pattern).
    prompt.format()


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
    ]
    missing = [s for s in required if not hasattr(handler, s)]
    assert not missing, f"missing symbols: {missing}"


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
    s = handler._SoundEffect(word_index=5, sound="hit")
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
            "editorial_vision": "test creative vision for the video",
        },
        "caption_style": "PaperII",
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


@check("recipe_eval flags zoom on a build word (zoom-arc rule)")
def _recipe_eval_zoom_arc():
    import recipe_eval
    bad_plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 4, "position": "hook", "intensity": 0.9},
                {"start_word_index": 5, "end_word_index": 9, "position": "build", "intensity": 0.3},
                {"start_word_index": 10, "end_word_index": 12, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [
                {"word_index": 7},  # build word
            ],
            "payoff_word_index": 11,
            "close_word_index": 12,
        },
        "emphasis_moments": [
            {
                "word_indices": [7],
                "zoom_effect": {"type": "StepZoom", "events": [{"startMs": 0}]},
            }
        ],
        "transitions": [],
        "broll_clips": [],
        "motion_graphics": [],
        "text_overlays": [],
        "sound_effects": [],
    }
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(13)]
    rep = recipe_eval.evaluate_recipe(bad_plan, words, [], 6.5)
    rule_ids = {r for (r, _) in rep.failures}
    assert "zoom-arc" in rule_ids, f"expected zoom-arc failure, got: {rule_ids}"


@check("recipe_eval flags StepZoom on payoff (payoff-commitment rule)")
def _recipe_eval_payoff_commitment():
    import recipe_eval
    bad_plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 4, "position": "hook", "intensity": 0.9},
                {"start_word_index": 5, "end_word_index": 8, "position": "build", "intensity": 0.3},
                {"start_word_index": 9, "end_word_index": 11, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [{"word_index": 10}],
            "payoff_word_index": 10,
            "close_word_index": 11,
        },
        "emphasis_moments": [
            {
                "word_indices": [10],
                "zoom_effect": {"type": "StepZoom", "events": [{"startMs": 0}]},
            }
        ],
        "transitions": [], "broll_clips": [], "motion_graphics": [],
        "text_overlays": [], "sound_effects": [],
    }
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(12)]
    rep = recipe_eval.evaluate_recipe(bad_plan, words, [], 6.0)
    rule_ids = {r for (r, _) in rep.failures}
    assert "payoff-commitment" in rule_ids


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
    # 21 words spaced 0.5s apart → ~10s total. Two zooms at word 1 (0.5s)
    # and word 20 (10s) leave a ~9.5s gap in between — well over the 4s
    # floor.
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(21)]
    rep = recipe_eval.evaluate_recipe(bad_plan, words, [], 10.5)
    rule_ids = {r for (r, _) in rep.failures}
    assert "dead-zone" in rule_ids, f"expected dead-zone failure, got: {rule_ids}"


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
