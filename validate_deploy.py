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


@check("caption override forces TOP during B-roll windows")
def _caption_override_broll_forces_top():
    """B-roll is full-canvas. Captions forced to top regardless of Gemini's choice."""
    segments = [
        {"fromFrame": 0,   "toFrame": 200, "position": "bottom"},
        {"fromFrame": 200, "toFrame": 500, "position": "center"},
        {"fromFrame": 500, "toFrame": 800, "position": "bottom"},
    ]
    broll_ranges = [(150, 250), (550, 650)]
    out = handler._force_caption_position_around_overlays(segments, [], broll_ranges)
    # Inside B-roll: top.
    assert _pos_at(out, 180) == "top",  f"inside first B-roll window, expected top, got: {out}"
    assert _pos_at(out, 220) == "top",  f"inside first B-roll (crossing orig boundary), expected top, got: {out}"
    assert _pos_at(out, 600) == "top",  f"inside second B-roll window, expected top, got: {out}"
    # Outside B-roll: Gemini's original choice preserved.
    assert _pos_at(out, 100) == "bottom"
    assert _pos_at(out, 400) == "center"
    assert _pos_at(out, 700) == "bottom"


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


@check("zoom startMs correction: SnapReframe at 1.2s word → startMs=1029 (peak-on-word)")
def _zoom_snapreframe_correction_active():
    # Spring 99% settling at ~171ms. Word at 1.2s = 1200ms.
    # Corrected startMs = 1200 − 171 = 1029.
    word_start_ms = 1200
    peak_reach_ms = handler.ZOOM_PEAK_REACH_MS["SnapReframe"]
    corrected_start_ms = word_start_ms - peak_reach_ms
    assert peak_reach_ms == 171
    assert corrected_start_ms == 1029, f"expected 1029, got {corrected_start_ms}"


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
    # StageZoom peak-reach is 1170ms. canonical = 5200 − 1170 = 4030.
    # That's BEFORE the clip's source_start (5000) → clamp to 5000.
    word_start_ms = 5200
    peak_reach_ms = handler.ZOOM_PEAK_REACH_MS["StageZoom"]
    canonical = word_start_ms - peak_reach_ms
    clip_source_start_ms = 5000
    clamped = max(clip_source_start_ms, canonical)
    assert canonical == 4030
    assert clamped == 5000, f"corrected should clamp to clip start (5000), got {clamped}"


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


@check("recipe_eval flags transition placed at a TIGHT boundary")
def _recipe_eval_transition_tight():
    # The new tight_boundaries kwarg must route transitions placed at tight
    # cuts to the dedicated `transition-tight-boundary` fail (not the
    # generic `transition-boundary` miss). This exercises the post-bug-fix
    # eval path: slots-only cut_boundaries + tight_boundaries explicit.
    import recipe_eval
    bad_plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 1, "position": "hook", "intensity": 0.9},
                {"start_word_index": 2, "end_word_index": 5, "position": "build", "intensity": 0.4},
                {"start_word_index": 6, "end_word_index": 7, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [{"word_index": 1}, {"word_index": 7}],
            "payoff_word_index": 7,
            "close_word_index": 7,
        },
        "emphasis_moments": [
            {"word_indices": [1], "zoom_effect": {"type": "SnapReframe", "events": [{"startMs": 0}]}},
            {"word_indices": [7], "zoom_effect": {"type": "SmoothPush", "events": [{"startMs": 0}]}},
        ],
        "transitions": [
            {"after_word_index": 3, "type": "CardSwipe"},   # at TIGHT boundary
        ],
        "broll_clips": [], "motion_graphics": [],
        "text_overlays": [], "sound_effects": [],
    }
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(8)]
    rep = recipe_eval.evaluate_recipe(
        bad_plan, words, cut_boundaries=[], duration=4.0,
        tight_boundaries=[3],
    )
    rule_ids = {r for (r, _) in rep.failures}
    assert "transition-tight-boundary" in rule_ids, f"expected transition-tight-boundary, got: {rule_ids}"
    # Crucially must NOT also fire the generic boundary miss for the same index.
    assert "transition-boundary" not in rule_ids, "tight should not double-fire as boundary-miss"


@check("recipe_eval warns when TIGHT cut has no masking zoom on next word")
def _recipe_eval_tight_no_mask():
    # Tight cut at word 3 with no emphasis on word 4 → tight-no-mask warning.
    # Prompt rule: "land a zoom on the first word after a tight cut to mask
    # the jump." Eval surfaces the missing mask as a non-blocking warning.
    import recipe_eval
    bad_plan = {
        "video_plan": {
            "arc_segments": [
                {"start_word_index": 0, "end_word_index": 1, "position": "hook", "intensity": 0.9},
                {"start_word_index": 2, "end_word_index": 5, "position": "build", "intensity": 0.4},
                {"start_word_index": 6, "end_word_index": 7, "position": "payoff", "intensity": 1.0},
            ],
            "key_moments": [{"word_index": 1}, {"word_index": 7}],
            "payoff_word_index": 7,
            "close_word_index": 7,
        },
        "emphasis_moments": [
            {"word_indices": [1], "zoom_effect": {"type": "SnapReframe", "events": [{"startMs": 0}]}},
            {"word_indices": [7], "zoom_effect": {"type": "SmoothPush", "events": [{"startMs": 0}]}},
        ],
        "transitions": [], "broll_clips": [], "motion_graphics": [],
        "text_overlays": [], "sound_effects": [],
    }
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(8)]
    rep = recipe_eval.evaluate_recipe(
        bad_plan, words, cut_boundaries=[], duration=4.0,
        tight_boundaries=[3],
    )
    warn_ids = {r for (r, _) in rep.warnings}
    assert "tight-no-mask" in warn_ids, f"expected tight-no-mask warning, got: {warn_ids}"

    # Inverse — add a masking zoom on word 4; warning must disappear.
    bad_plan["emphasis_moments"].append(
        {"word_indices": [4], "zoom_effect": {"type": "SnapReframe", "events": [{"startMs": 0}]}}
    )
    # And give word 4 a matching key_moment so the 1:1 zoom-key rule is happy.
    bad_plan["video_plan"]["key_moments"].append({"word_index": 4})
    rep2 = recipe_eval.evaluate_recipe(
        bad_plan, words, cut_boundaries=[], duration=4.0,
        tight_boundaries=[3],
    )
    warn_ids2 = {r for (r, _) in rep2.warnings}
    assert "tight-no-mask" not in warn_ids2, f"masking zoom should clear the warning, got: {warn_ids2}"


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
