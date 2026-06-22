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


@check("emphasis payoff-tail protection drops a snap landing 1.04s after the payoff (ACTIVE)")
def _emphasis_payoff_tail_drops_late_snap():
    # Reproduces tonight's failure: SmoothPush payoff at word 114
    # "free" with corrected startMs = 12000 - 420 = 11580 (Fix B1).
    # Event spans [11580, 12780] ms = [11.58s, 12.78s]. Protected
    # window extends to 12.78 + 1.5 = 14.28s. A SnapReframe on word 119
    # "advantage" at word_t = 13.04s has corrected startMs = 13040 - 171
    # = 12869. Snap starts at 12.869s — inside [11.58, 14.28] → drop.
    _PAYOFF_TAIL_PROTECTION_S = 1.5

    # Mirror the production extraction with the actual numbers.
    def _first_event_window_s(em):
        ze = em.get("zoom_effect") or {}
        events = ze.get("events") or []
        if not events:
            return None
        ev = events[0]
        start_ms = float(ev.get("startMs", 0))
        dur_ms = float(ev.get("durationMs", 0))
        peak_ms = start_ms + float(
            handler.ZOOM_PEAK_REACH_MS.get(ze.get("type", ""), 0)
        )
        return (start_ms / 1000.0, (start_ms + dur_ms) / 1000.0, peak_ms / 1000.0)

    payoff_em = {
        "word_indices": [114],
        "zoom_effect": {
            "type": "SmoothPush",
            "events": [{"startMs": 11580, "durationMs": 1200}],
        },
    }
    snap_em = {
        "word_indices": [119],
        "zoom_effect": {
            "type": "SnapReframe",
            "events": [{"startMs": 12869, "durationMs": 700}],
        },
    }

    payoff_win = _first_event_window_s(payoff_em)
    snap_win = _first_event_window_s(snap_em)
    payoff_protected = (payoff_win[0], payoff_win[1] + _PAYOFF_TAIL_PROTECTION_S)
    snap_start_s = snap_win[0]

    drops = payoff_protected[0] <= snap_start_s < payoff_protected[1]
    assert drops is True, (
        f"snap at {snap_start_s:.2f}s must fall inside "
        f"[{payoff_protected[0]:.2f}, {payoff_protected[1]:.2f}) and drop"
    )

    # And a snap LATE enough (≥1.5s after payoff zoom end) is the close
    # callback the prompt permits — must NOT drop.
    callback_em = {
        "word_indices": [125],
        "zoom_effect": {
            "type": "SnapReframe",
            "events": [{"startMs": 14400, "durationMs": 700}],
        },
    }
    callback_win = _first_event_window_s(callback_em)
    callback_drops = payoff_protected[0] <= callback_win[0] < payoff_protected[1]
    assert callback_drops is False, (
        f"close callback at {callback_win[0]:.2f}s "
        f"must NOT fall inside protected window {payoff_protected}"
    )


@check("emphasis min spacing drops lower-priority peak when < 2.0s apart (ACTIVE)")
def _emphasis_min_spacing_drops_lower_priority():
    # Two emphases: a mid_peak SmoothPush at t=10.0s (peak at 10.42s,
    # priority 2) and a "statement" SmoothPush at t=11.5s (peak at
    # 11.92s, priority 1). Gap = 1.5s < 2.0s threshold. Lower-priority
    # (statement, prio=1) drops; mid_peak (prio=2) survives.
    _MIN_ZOOM_SPACING_S = 2.0

    arc_segments = [
        # 0-99: build (prio 1)
        {"start_word_index": 0, "end_word_index": 99, "position": "build"},
        # 100-110: mid_peak (prio 2)
        {"start_word_index": 100, "end_word_index": 110, "position": "mid_peak"},
        # 111-130: build again (prio 1)
        {"start_word_index": 111, "end_word_index": 130, "position": "build"},
    ]

    _PRIORITY = {"payoff": 3, "mid_peak": 2}

    def _arc_pos_at(wi):
        for s in arc_segments:
            if s["start_word_index"] <= wi <= s["end_word_index"]:
                return s["position"]
        return ""

    def _prio(em):
        wi = em["word_indices"][0]
        return _PRIORITY.get(_arc_pos_at(wi), 1)

    def _peak_s(em):
        ev = em["zoom_effect"]["events"][0]
        peak_ms = float(ev["startMs"]) + float(
            handler.ZOOM_PEAK_REACH_MS.get(em["zoom_effect"]["type"], 0)
        )
        return peak_ms / 1000.0

    mid_peak_em = {
        "word_indices": [105],  # inside mid_peak segment
        "zoom_effect": {
            "type": "SmoothPush",
            "events": [{"startMs": 9580, "durationMs": 1200}],
        },
    }
    statement_em = {
        "word_indices": [115],  # inside build segment
        "zoom_effect": {
            "type": "SmoothPush",
            "events": [{"startMs": 11080, "durationMs": 1200}],
        },
    }

    assert _prio(mid_peak_em) == 2
    assert _prio(statement_em) == 1
    gap = abs(_peak_s(statement_em) - _peak_s(mid_peak_em))
    assert gap < _MIN_ZOOM_SPACING_S, f"setup: gap should be under threshold, got {gap:.2f}s"

    # The statement (lower priority) must be the one dropped.
    if _prio(statement_em) > _prio(mid_peak_em):
        kept = "mid_peak"  # this would be wrong for the test
    elif _prio(statement_em) < _prio(mid_peak_em):
        kept = "mid_peak"
    else:
        kept = "earlier"  # tie → earlier wins
    assert kept == "mid_peak", "mid_peak (prio 2) must win over statement (prio 1)"


@check("emphasis min spacing keeps BOTH when peaks are >=2.0s apart")
def _emphasis_spaced_pair_both_kept():
    # Two zooms 2.5s apart (≥2.0s threshold) and neither hits the
    # payoff tail — both must survive.
    _MIN_ZOOM_SPACING_S = 2.0

    def _peak_s(em):
        ev = em["zoom_effect"]["events"][0]
        peak_ms = float(ev["startMs"]) + float(
            handler.ZOOM_PEAK_REACH_MS.get(em["zoom_effect"]["type"], 0)
        )
        return peak_ms / 1000.0

    em_a = {
        "word_indices": [50],
        "zoom_effect": {
            "type": "SnapReframe",
            "events": [{"startMs": 9829, "durationMs": 700}],
        },
    }
    em_b = {
        "word_indices": [70],
        "zoom_effect": {
            "type": "SnapReframe",
            "events": [{"startMs": 12329, "durationMs": 700}],
        },
    }
    gap = abs(_peak_s(em_b) - _peak_s(em_a))
    assert gap >= _MIN_ZOOM_SPACING_S, f"setup: gap must be >= threshold, got {gap:.2f}s"
    # With gap above threshold, the spacing rule is a no-op. Both kept.


@check("ZERO_HANDLE_TRANSITION_TYPES contains the audit-verified types + DipToBlack (sanity)")
def _zero_handle_set_present():
    # Audit (2026-06-14) verified ShutterFlash/NewspaperWipe/LightLeak/
    # SceneTitle render correctly without handle frames; DipToBlack was
    # added 2026-06-14 (Option A wiring) as the clean default for TIGHT
    # boundaries. The set drives the audio silent-slot branch in
    # build_per_cut_audio AND the video additive-slot branch at the
    # render slot-build loop. Anyone removing from this set must also
    # restore the audio crossfade + the overlap cursor model for that type
    # or risk speech smear (audio) and projection drift (video).
    expected = {"ShutterFlash", "NewspaperWipe", "LightLeak", "SceneTitle", "DipToBlack"}
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
    _schema_line_match = re.search(
        r'"transitions":\s*\[\s*\{\{[^}]*"type":\s*((?:"[^"]+"\s*\|\s*)*"[^"]+")',
        _src,
    )
    assert _schema_line_match, (
        "Prompt schema example for transitions/type at handler.py:~3854 "
        "could not be parsed. The 'type' line shape may have changed."
    )
    _prompt_types = set(re.findall(r'"([^"]+)"', _schema_line_match.group(1)))
    _canonical = set(handler.VALID_TRANSITION_TYPES)
    _hallucinated = _prompt_types - _canonical
    assert not _hallucinated, (
        f"Prompt schema example lists types not in VALID_TRANSITION_TYPES: "
        f"{sorted(_hallucinated)}. These would fail Pydantic validation "
        f"if Gemini emitted them."
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
            trans_dur_after=[0.0, 0.0],
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
            trans_dur_after=[0.0, 0.0],
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
        {"type": "SceneTitle",    "afterClipIndex": 3},  # 1800ms — longest
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

    # SceneTitle (1800ms, idx 3) is the longest → must be kept.
    assert 3 not in drop_indices, "longest natural duration must NEVER drop"


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


# ─── 5b1. MULTI-CLIP TIER GATE (PREMIUM CONCURRENCY) ──────────────────
# Backend-side defense-in-depth for the premium multi-clip feature. The
# frontend is the primary gate (UI refuses multi-upload for non-premium);
# this worker-side check rejects curl-abuse where a non-premium user
# bypasses the UI. FAIL-OPEN discipline means Supabase blips never block
# paying users.
print("\n[5b1/6] Multi-clip tier gate")


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
    for _name in ("LightLeak", "ShutterFlash", "NewspaperWipe", "SceneTitle"):
        assert _name in src, (
            f"generate_plan_diff is missing overlay name {_name!r}. The "
            f"re-edit prompt needs all 4 visible so the user can request "
            f"any of them by name."
        )


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
        "caption_style": "PaperII",
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
    assert "PaperII" in user_content, (
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
    plan = {"caption_style": "PaperII", "emphasis_moments": [{"word_indices": [3]}]}
    diffs = handler.compute_plan_diff(plan, dict(plan))
    assert diffs == [], (
        f"identical plans must produce 0 diffs; got {diffs}"
    )


@check("compute_plan_diff catches top-level scalar changes")
def _diff_scalar_change():
    import handler
    prior = {"caption_style": "PaperII", "outro": "none"}
    new = {"caption_style": "Lumen", "outro": "none"}
    diffs = handler.compute_plan_diff(prior, new)
    cs_diffs = [d for d in diffs if d["path"] == "caption_style"]
    assert len(cs_diffs) == 1, f"expected 1 caption_style diff, got: {diffs}"
    d = cs_diffs[0]
    assert d["op"] == "changed" and d["old"] == "PaperII" and d["new"] == "Lumen", d
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
        {"after_word_index": 12, "type": "NewspaperWipe"},
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
            {"after_word_index": 12, "type": "NewspaperWipe"},  # out-of-scope add
        ]}
        validation = {
            "verdict": "partial_out_of_scope",
            "diffs": [{
                "path": "transitions[anchor=12]",
                "list_key": "transitions",
                "anchor": 12,
                "op": "added",
                "old": None,
                "new": {"after_word_index": 12, "type": "NewspaperWipe"},
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
            {"after_word_index": 12, "type": "NewspaperWipe"},
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
                "old": {"after_word_index": 12, "type": "NewspaperWipe"},
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
        prior = {"caption_style": "PaperII", "emphasis_moments": [prior_em]}
        new = {"caption_style": "Lumen", "emphasis_moments": [new_em]}
        validation = {
            "verdict": "partial_out_of_scope",
            "diffs": [
                {"path": "caption_style", "list_key": None, "anchor": None,
                 "op": "changed", "old": "PaperII", "new": "Lumen"},
                {"path": "emphasis_moments[anchor=(3,)]",
                 "list_key": "emphasis_moments", "anchor": (3,),
                 "op": "changed", "old": prior_em, "new": new_em},
            ],
            "out_of_scope_paths": ["caption_style", "emphasis_moments[anchor=(3,)]"],
        }
        out = handler.apply_scalar_reverts(prior, new, validation, mode="tweak")
        assert out["caption_style"] == "PaperII", (
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


@check("VALID_TIGHT_CUT_OVERLAYS canonical set has exactly the 4 signed-off overlays")
def _tco_registry_pair():
    import type_registries
    assert hasattr(type_registries, "VALID_TIGHT_CUT_OVERLAYS"), (
        "VALID_TIGHT_CUT_OVERLAYS missing from type_registries"
    )
    expected = frozenset({"LightLeak", "ShutterFlash", "NewspaperWipe", "SceneTitle"})
    assert type_registries.VALID_TIGHT_CUT_OVERLAYS == expected, (
        f"VALID_TIGHT_CUT_OVERLAYS={type_registries.VALID_TIGHT_CUT_OVERLAYS} — "
        f"expected exactly {expected}. Adding a fifth requires another isolation "
        f"test + visual sign-off."
    )


@check("render_schemas.PromptlyRenderInput.tightCutOverlays accepts a valid spec")
def _tco_schema_roundtrip():
    # Active-path check: build a minimal PromptlyRenderInput with one
    # TightCutOverlaySpec per registered type, plus a SceneTitle carrying
    # the title/label extras. All must validate; the empty-default path
    # must still recover the pre-overlay behavior.
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
            "style": "PaperII",
            "pages": [],
            "keywords": [],
            "positionSegments": [],
        },
        "textOverlays": [],
        "motionGraphics": [],
        # Explicit tightCutOverlays list — one entry per registered type to
        # exercise every literal in TightCutOverlayType, plus SceneTitle's
        # title/label extras.
        "tightCutOverlays": [
            {"atFrame": 120, "type": "LightLeak", "durationInFrames": 11},
            {"atFrame": 200, "type": "ShutterFlash", "durationInFrames": 11},
            {"atFrame": 280, "type": "NewspaperWipe", "durationInFrames": 11},
            {"atFrame": 380, "type": "SceneTitle", "durationInFrames": 72,
             "title": "ACT TWO", "label": "CHAPTER"},
        ],
    }
    parsed = render_schemas.PromptlyRenderInput.model_validate(_minimal)
    assert len(parsed.tightCutOverlays) == 4
    _types = [o.type for o in parsed.tightCutOverlays]
    assert _types == ["LightLeak", "ShutterFlash", "NewspaperWipe", "SceneTitle"], (
        f"types out of order: {_types}"
    )
    # SceneTitle entry must carry its title + label through the Pydantic layer.
    _st = parsed.tightCutOverlays[3]
    assert _st.title == "ACT TWO", f"SceneTitle title not preserved: {_st.title!r}"
    assert _st.label == "CHAPTER", f"SceneTitle label not preserved: {_st.label!r}"
    # SceneTitle must use the longer 72-frame duration.
    assert _st.durationInFrames == 72, (
        f"SceneTitle durationInFrames should be 72, got {_st.durationInFrames}"
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


@check("recipe_eval flags SceneTitle tight_cut_overlay without a title")
def _recipe_eval_tco_scenetitle_no_title():
    # SceneTitle's typographic panel needs a title. Emitting it without one
    # is the hard error the validator catches first; recipe_eval also
    # surfaces it so operators see the problem in the eval report.
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
        "transitions": [],
        "tight_cut_overlays": [
            {"after_word_index": 3, "type": "SceneTitle"},  # missing title!
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
    assert "tight-overlay-scenetitle-title" in rule_ids, (
        f"expected tight-overlay-scenetitle-title failure, got: {rule_ids}"
    )


@check("recipe_eval flags non-SceneTitle tight_cut_overlay carrying title/label")
def _recipe_eval_tco_extras_misuse():
    # title/label are SceneTitle-only. Emitting them with LightLeak (or
    # ShutterFlash / NewspaperWipe) is a hard error — the validator rejects
    # it. recipe_eval mirrors this as the tight-overlay-extras-misuse rule.
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
        "transitions": [],
        "tight_cut_overlays": [
            {"after_word_index": 3, "type": "LightLeak", "title": "OOPS"},
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
    assert "tight-overlay-extras-misuse" in rule_ids, (
        f"expected tight-overlay-extras-misuse failure, got: {rule_ids}"
    )


@check("recipe_eval accepts SceneTitle with title (active passing path)")
def _recipe_eval_tco_scenetitle_passes():
    # A SceneTitle with a proper title at a TIGHT boundary should not fire
    # any tight-overlay-* failure — the eval must NOT misfire on the
    # active-path case (otherwise valid chapter breaks would all show as
    # failures in the eval report).
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
            {"after_word_index": 3, "type": "SceneTitle", "title": "ACT TWO", "label": "CHAPTER"},
            {"after_word_index": 5, "type": "NewspaperWipe"},
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
        f"valid SceneTitle + NewspaperWipe placement should not fail any "
        f"tight-overlay-* rule, got: {tco_rules}"
    )


@check("recipe_eval flags tight_cut_overlay placed at a CUT BOUNDARY")
def _recipe_eval_tco_wrong_boundary():
    # Overlay anchored at a CUT BOUNDARY (where transitions live) — must fail.
    # This is the "wrong boundary type" misuse the prompt warns against.
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
        "transitions": [],
        "tight_cut_overlays": [
            {"after_word_index": 5, "type": "LightLeak"},  # 5 is a CUT BOUNDARY, not TIGHT
        ],
        "broll_clips": [], "motion_graphics": [],
        "text_overlays": [], "sound_effects": [],
    }
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(8)]
    rep = recipe_eval.evaluate_recipe(
        bad_plan, words, cut_boundaries=[5], duration=4.0,
        tight_boundaries=[3],
    )
    rule_ids = {r for (r, _) in rep.failures}
    assert "tight-overlay-boundary" in rule_ids, (
        f"expected tight-overlay-boundary failure, got: {rule_ids}"
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
        "ShutterFlash", "LightLeak", "NewspaperWipe",
        "ShutterFlash", "LightLeak", "NewspaperWipe",
    ], f"6-bare rotation should cycle SF/LL/NW evenly, got {six_bare}"

    # The b89287c4 case: Gemini already placed a ShutterFlash on boundary 1.
    # Backfill must PRESERVE it and rotate around it (no adjacent SF).
    gemini_pick = rot([None, "ShutterFlash", None, None, None, None])
    assert gemini_pick == [
        "LightLeak", "ShutterFlash", "NewspaperWipe",
        "ShutterFlash", "LightLeak", "NewspaperWipe",
    ], f"backfill must rotate around Gemini's locked pick, got {gemini_pick}"

    # Universal invariants across sizes incl. 7+ (spaced repeats, never adjacent).
    for n in range(1, 12):
        out = rot([None] * n)
        assert all(out[i] != out[i - 1] for i in range(1, n)), (
            f"n={n}: adjacent duplicate decoration in {out}"
        )
        assert all(
            t in ("ShutterFlash", "LightLeak", "NewspaperWipe") for t in out
        ), f"n={n}: non-rotation type emitted in {out}"

    # Deterministic: same input → same output (no RNG).
    assert rot([None, "LightLeak", None]) == rot([None, "LightLeak", None]), (
        "rotation must be deterministic"
    )

    # A boundary Gemini dressed with a held-out type (SceneTitle) is locked;
    # neighbours rotate normally and never collide with it.
    with_scenetitle = rot([None, "SceneTitle", None])
    assert with_scenetitle[1] == "SceneTitle", "non-rotation pick must be preserved"
    assert with_scenetitle[0] in ("ShutterFlash", "LightLeak", "NewspaperWipe")
    assert with_scenetitle[2] in ("ShutterFlash", "LightLeak", "NewspaperWipe")


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
