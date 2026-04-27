"""
FFmpeg base-video builder for the visually-identical fast path.

Replaces the old PromptlyBase Remotion composition (which painted full
1080×1920 video frames at 30fps in JavaScript canvas — the source of the
~120s slowdown after the 66-pack landed) with a single-pass FFmpeg
filtergraph that does the same work natively:

  - Clip extraction (trim + setpts for playbackRate)
  - Simple zoom effects (SmoothPush / SnapReframe / StepZoom / StageZoom)
    expressed as per-frame `crop` expressions using the same easing math
    the Remotion components use.
  - B-roll cutaways via `overlay` with `enable=between(t,...)`
  - Outro fade via `fade` filter
  - Concat across all clips + Remotion-rendered micro-segments
  - Alpha-composite the PromptlyOverlay layer
  - Final libx264 ultrafast crf 18 encode
  - Audio mux (stream-copied from the parallel audio pipeline)

Composite-effect zooms (FocusWindow / LetterboxPush / DepthPull) and ALL
transitions (CardSwipe / FilmStrip / SceneTitle / NewspaperWipe / LightLeak
/ SlideOver / Stack / CrossfadeZoom / ShutterFlash / StepPush / ZoomThrough)
stay in Remotion via PromptlyMicroSegments — those carry multi-layer
visual identity (bokeh orbs, blur masks, custom typography, etc.) that has
no faithful FFmpeg analog.
"""

from typing import List, Dict, Optional, Tuple
import math


# ── Zoom categorization ──────────────────────────────────────────────────────

# Pure scale + origin transforms — paint identical between Chromium's
# `transform: scale()` and FFmpeg's crop+lanczos-scale to 1080×1920.
SIMPLE_ZOOM_TYPES = {"SmoothPush", "SnapReframe", "StepZoom", "StageZoom"}

# Composite-effect zooms — multi-layer overlays, blur masks, bokeh orbs, etc.
# Stay in Remotion via PromptlyMicroSegments to preserve visual identity.
COMPLEX_ZOOM_TYPES = {"FocusWindow", "LetterboxPush", "DepthPull"}

# Default scale per zoom type (matches Remotion components' fallbacks).
_DEFAULT_SCALE = {
    "SmoothPush": 1.2,
    "SnapReframe": 1.3,
    "StepZoom": 1.3,
    "StageZoom": 1.35,
    "FocusWindow": 1.8,    # bgScale default
    "LetterboxPush": 1.2,
    "DepthPull": 1.15,
}


def categorize_clip(clip_spec: dict) -> str:
    """Returns "ffmpeg" if the clip can be rendered directly in FFmpeg,
    else "remotion" if it has a composite-effect zoom that must be
    rendered in PromptlyMicroSegments."""
    zoom = clip_spec.get("zoomEffect")
    if not zoom:
        return "ffmpeg"
    ztype = zoom.get("type")
    if ztype in SIMPLE_ZOOM_TYPES:
        return "ffmpeg"
    return "remotion"


# ── Zoom easing math (ported from Remotion components) ───────────────────────
#
# Every Remotion zoom component computes a `scale` and `(originX, originY)`
# per frame and applies CSS `transform: scale(s); transformOrigin: oX% oY%`.
# We reproduce the same per-frame `(scale, originX, originY)` in Python and
# emit FFmpeg `crop` filter expressions that sample the equivalent source
# region:
#
#   crop_w = W / scale
#   crop_h = H / scale
#   crop_x = originX * W * (1 - 1/scale)
#   crop_y = originY * H * (1 - 1/scale)
#
# Followed by `scale=W:H:flags=lanczos` to scale that crop back up to the
# canvas. At lanczos quality, the resampled output is visually identical to
# Chromium's compositor-applied `transform: scale()` on the same region.

# Spring constants for SnapReframe (damping=28, mass=0.6, stiffness=260).
# Over-damped: discriminant = 28² - 4*0.6*260 = 160 > 0.
# Closed-form step response for over-damped spring:
#   x(t) = 1 - (r2*e^(r1*t) - r1*e^(r2*t)) / (r2 - r1)
# where r1, r2 are the roots of the characteristic equation
#   m*r² + c*r + k = 0 → r = (-c ± √(c²-4mk)) / 2m
_SPRING_DAMPING = 28.0
_SPRING_MASS = 0.6
_SPRING_STIFFNESS = 260.0
_SPRING_DISC = _SPRING_DAMPING ** 2 - 4 * _SPRING_MASS * _SPRING_STIFFNESS  # = 160
_SPRING_R1 = (-_SPRING_DAMPING + math.sqrt(_SPRING_DISC)) / (2 * _SPRING_MASS)  # ≈ -12.7924
_SPRING_R2 = (-_SPRING_DAMPING - math.sqrt(_SPRING_DISC)) / (2 * _SPRING_MASS)  # ≈ -33.8742
_SPRING_DENOM = _SPRING_R2 - _SPRING_R1  # ≈ -21.0818


def _normalize_events(zoom_spec: dict, clip_duration_frames: int, source_fps: float) -> List[dict]:
    """Returns a list of {esF, edF, scale, originX, originY} dicts, one per
    zoom event. Empty events list synthesizes one full-clip-duration event
    matching the Remotion full-duration mode of each component.

    NOTE: esF / edF can be NEGATIVE for events that have been shifted by the
    chunked-composite slicer (events whose start was BEFORE the chunk window
    end up with negative startMs). The FFmpeg expression engine handles
    negative comparison values correctly — `lt(n, -72)` is just False for
    non-negative n, which short-circuits the corresponding branches. Don't
    clamp these to 0 here; that would lose the event's actual timing and
    flatten its easing curve into a brand-new short ramp."""
    ztype = zoom_spec["type"]
    raw_events = zoom_spec.get("events") or []
    default_scale = _DEFAULT_SCALE.get(ztype, 1.2)

    if not raw_events:
        return [{
            "esF": 0,
            "edF": max(1, int(clip_duration_frames)),
            "scale": float(zoom_spec.get("scale", default_scale)),
            "originX": float(zoom_spec.get("originX", 0.5)),
            "originY": float(zoom_spec.get("originY", 0.5)),
        }]

    events = []
    for ev in raw_events:
        if not isinstance(ev, dict):
            continue
        try:
            start_ms = float(ev.get("startMs", 0.0))
            dur_ms = float(ev.get("durationMs", 0.0))
        except (TypeError, ValueError):
            continue
        es_f = int(round(start_ms * source_fps / 1000.0))
        ed_f = int(round((start_ms + dur_ms) * source_fps / 1000.0))
        if ed_f <= es_f:
            ed_f = es_f + 1
        events.append({
            "esF": es_f,
            "edF": ed_f,
            "scale": float(ev.get("scale", default_scale)),
            "originX": float(ev.get("originX", 0.5)),
            "originY": float(ev.get("originY", 0.5)),
        })
    events.sort(key=lambda e: e["esF"])
    return events


def _smooth_push_progress_expr(es: int, ed: int) -> str:
    """SmoothPush progress 0→1 with cubic in/hold/out, matching Remotion.

    Timeline (Remotion SmoothPush.tsx):
      - 0% .. 35%: out-cubic ramp 0 → 1
      - 35% .. 60%: hold at 1
      - 60% .. 100%: in-cubic ramp 1 → 0 (1 - in-cubic)

    NOTE: es and ed can be negative when this event has been shifted by the
    chunked-composite slicer. We wrap every numeric token in parentheses so
    FFmpeg's expression parser tokenizes `n - (-72)` as `n + 72` rather than
    relying on `--` lexing behavior.
    """
    duration = ed - es
    rd = max(1, int(round(duration * 0.35)))
    hd = max(rd + 1, int(round(duration * 0.6)))
    od = max(1, duration - hd)
    rd_end = es + rd
    hd_end = es + hd
    return (
        f"if(lt(n,({es})),0,"
        f"if(lt(n,({rd_end})),(1-pow(1-(n-({es}))/{rd},3)),"
        f"if(lt(n,({hd_end})),1,"
        f"if(lt(n,({ed})),(1-pow((n-({hd_end}))/{od},3)),0))))"
    )


def _step_zoom_progress_expr(es: int, ed: int) -> str:
    """StepZoom: hard step on at es, hard step off at ed."""
    return f"if(lt(n,({es})),0,if(lt(n,({ed})),1,0))"


def _stage_zoom_scale_expr(es: int, ed: int, target_scale: float, first_stage: float) -> str:
    """StageZoom returns SCALE (not progress) — it has two distinct scale
    targets so a single 0→1 progress doesn't capture it.

    Timeline (Remotion StageZoom.tsx):
      - 0% .. 20%: out-cubic 1 → s1
      - 20% .. 40%: hold s1
      - 40% .. 65%: out-cubic s1 → s2
      - 65% .. 80%: hold s2
      - 80% .. 100%: in-cubic s2 → 1
    """
    duration = ed - es
    p1_end = es + max(1, int(round(duration * 0.2)))
    h1_end = es + max(p1_end - es + 1, int(round(duration * 0.4)))
    p2_end = es + max(h1_end - es + 1, int(round(duration * 0.65)))
    h2_end = es + max(p2_end - es + 1, int(round(duration * 0.8)))
    end = ed

    p1d = max(1, p1_end - es)
    p2d = max(1, p2_end - h1_end)
    od = max(1, end - h2_end)
    s1 = first_stage
    s2 = target_scale
    return (
        f"if(lt(n,({es})),1,"
        f"if(lt(n,({p1_end})),1+({s1}-1)*(1-pow(1-(n-({es}))/{p1d},3)),"
        f"if(lt(n,({h1_end})),{s1},"
        f"if(lt(n,({p2_end})),{s1}+({s2}-{s1})*(1-pow(1-(n-({h1_end}))/{p2d},3)),"
        f"if(lt(n,({h2_end})),{s2},"
        f"if(lt(n,({end})),{s2}+(1-{s2})*pow((n-({h2_end}))/{od},3),1))))))"
    )


def _spring_response_expr(t_seconds_expr: str) -> str:
    """Closed-form over-damped spring step response (0 → 1).
    `t_seconds_expr` is an FFmpeg expression that evaluates to t in seconds.

    Math: x(t) = 1 - (r2*e^(r1*t) - r1*e^(r2*t)) / (r2-r1)
    Verified: x(0) = 0, x(∞) = 1, dx/dt(0) = 0.
    """
    return (
        f"(1-(({_SPRING_R2})*exp(({_SPRING_R1})*({t_seconds_expr}))"
        f"-({_SPRING_R1})*exp(({_SPRING_R2})*({t_seconds_expr})))/({_SPRING_DENOM}))"
    )


def _snap_reframe_event_scale_expr(es: int, ed: int, target_scale: float, fps: float) -> str:
    """SnapReframe per-event scale contribution.

    Remotion (SnapReframe.tsx):
      zoomIn  = spring(t1) where t1 = max(0, frame-eventStart) / fps
      zoomOut = spring(t2) where t2 = max(0, frame-eventEnd)   / fps  (else 0)
      eventScale = 1 + (TS-1) * zoomIn * (1 - zoomOut)
    Returns the eventScale expression (always ≥ 1).

    Negative es/ed values (from the chunked-composite slicer) are wrapped in
    parens so FFmpeg's expression parser tokenizes correctly.
    """
    t1_expr = f"((n-({es}))/{fps})"
    t2_expr = f"((n-({ed}))/{fps})"
    spring_in = _spring_response_expr(t1_expr)
    spring_out = f"if(lt(n,({ed})),0,{_spring_response_expr(t2_expr)})"
    return (
        f"if(lt(n,({es})),1,"
        f"(1+({target_scale}-1)*({spring_in})*(1-({spring_out}))))"
    )


def build_zoom_filter_chain(
    zoom_spec: dict,
    clip_duration_frames: int,
    source_fps: float,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
) -> str:
    """Build the `crop=...,scale=...:flags=lanczos` filter chain that applies
    the given zoom effect to a 1080×1920 source clip. Returns "" for unsupported
    zoom types (caller should categorize first via categorize_clip)."""
    ztype = zoom_spec["type"]
    if ztype not in SIMPLE_ZOOM_TYPES:
        return ""

    events = _normalize_events(zoom_spec, clip_duration_frames, source_fps)
    if not events:
        return ""

    # Build per-frame scale(n) expression. For a single event, the formula is
    # straightforward. For multiple events (rare), we chain max() across each
    # event's contribution.
    if len(events) == 1:
        ev = events[0]
        es, ed = ev["esF"], ev["edF"]
        ts = ev["scale"]
        if ztype == "SmoothPush":
            progress = _smooth_push_progress_expr(es, ed)
            scale_expr = f"(1+({ts}-1)*{progress})"
        elif ztype == "StepZoom":
            progress = _step_zoom_progress_expr(es, ed)
            scale_expr = f"(1+({ts}-1)*{progress})"
        elif ztype == "StageZoom":
            scale_expr = _stage_zoom_scale_expr(es, ed, ts, float(zoom_spec.get("firstStage", 1.15)))
        elif ztype == "SnapReframe":
            scale_expr = _snap_reframe_event_scale_expr(es, ed, ts, source_fps)
        else:
            return ""
        ox_expr = f"({ev['originX']})"
        oy_expr = f"({ev['originY']})"
    else:
        # Multi-event: stack max() of per-event scale contributions, and
        # piecewise-pick the origin from whichever event currently dominates.
        # For events that don't overlap (the typical case from Gemini), this
        # is equivalent to "use the active event's origin during its window."
        scale_terms = []
        ox_branches = []
        oy_branches = []
        for ev in events:
            es, ed = ev["esF"], ev["edF"]
            ts = ev["scale"]
            if ztype == "SmoothPush":
                progress = _smooth_push_progress_expr(es, ed)
                term = f"(1+({ts}-1)*{progress})"
            elif ztype == "StepZoom":
                progress = _step_zoom_progress_expr(es, ed)
                term = f"(1+({ts}-1)*{progress})"
            elif ztype == "StageZoom":
                term = _stage_zoom_scale_expr(es, ed, ts, float(zoom_spec.get("firstStage", 1.15)))
            elif ztype == "SnapReframe":
                term = _snap_reframe_event_scale_expr(es, ed, ts, source_fps)
            else:
                continue
            scale_terms.append(term)
            ox_branches.append((es, ed, ev["originX"]))
            oy_branches.append((es, ed, ev["originY"]))
        if not scale_terms:
            return ""
        # max(a, b) ≡ if(gt(a,b), a, b)
        scale_expr = scale_terms[0]
        for term in scale_terms[1:]:
            scale_expr = f"if(gt({scale_expr},{term}),{scale_expr},{term})"
        # Origin picks first matching event window, falls back to 0.5.
        ox_expr = "0.5"
        oy_expr = "0.5"
        for es, ed, ox in reversed(ox_branches):
            ox_expr = f"if(lt(n,({es})),{ox_expr},if(lt(n,({ed})),{ox},{ox_expr}))"
        for es, ed, oy in reversed(oy_branches):
            oy_expr = f"if(lt(n,({es})),{oy_expr},if(lt(n,({ed})),{oy},{oy_expr}))"

    crop_w = f"{canvas_w}/({scale_expr})"
    crop_h = f"{canvas_h}/({scale_expr})"
    crop_x = f"({ox_expr})*{canvas_w}*(1-1/({scale_expr}))"
    crop_y = f"({oy_expr})*{canvas_h}*(1-1/({scale_expr}))"

    return (
        f"crop=w='{crop_w}':h='{crop_h}':x='{crop_x}':y='{crop_y}',"
        f"scale={canvas_w}:{canvas_h}:flags=lanczos"
    )


# ── B-roll mapping ───────────────────────────────────────────────────────────

def build_broll_input_filter(
    broll_idx: int,
    broll: dict,
    output_input_idx: int,
    source_fps: float,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
) -> Tuple[str, str]:
    """Build the per-B-roll input filter chain. Returns (filter_string, label).

    The filter chain:
      1. Trims the B-roll source to [seekFromFrames, seekFromFrames + durationInFrames * playbackRate)
         in the broll's own frame coordinates (its source fps may differ from output).
      2. Rebases timestamps to 0 and applies playbackRate via setpts.
      3. Scales/crops to canvas dimensions (objectFit:cover semantics).
      4. Shifts presentation time forward to output start so the overlay aligns.
      5. Resamples to output fps for clean overlay alignment.
    """
    label = f"br{broll_idx}"
    seek_from_frames = int(broll.get("seekFromFrames", 0))
    dur_frames = int(broll["durationInFrames"])
    pbr = float(broll.get("playbackRate", 1.0)) or 1.0
    from_frame = int(broll["fromFrame"])
    out_start_seconds = from_frame / source_fps
    # Read enough source frames to fill the duration at the desired playback
    # rate. trim takes seconds (more reliable than frame indices when the
    # broll fps differs from source_fps).
    source_in_seconds = (dur_frames * pbr) / source_fps
    trim_start_s = seek_from_frames / max(1.0, source_fps)
    trim_end_s = trim_start_s + source_in_seconds + 0.05  # small padding for safety
    filters = [
        f"trim=start={trim_start_s:.6f}:end={trim_end_s:.6f}",
        f"setpts=(PTS-STARTPTS)/{pbr:.6f}",
        f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={canvas_w}:{canvas_h}",
        f"fps={source_fps:g}",
        f"setpts=PTS+{out_start_seconds:.6f}/TB",
    ]
    chain = f"[{output_input_idx}:v]" + ",".join(filters) + f"[{label}]"
    return chain, label


# ── Clip segment filter (FFmpeg-renderable clips) ────────────────────────────

def _build_clip_segment_with_pad(
    seg_idx: int,
    clip: dict,
    source_pad: str,
    source_fps: float,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
) -> Tuple[str, str]:
    """Build the per-clip filter chain that produces one output segment.

    `source_pad` is the input pad name (e.g. "0:v" or "src3"). Caller routes
    each clip through its own copy of the source via a `split` filter.

    Returns (filter_string, label).

    The chain:
      1. Trims source to the exact minimum frames that produce dur_frames
         output frames after the rate change (see "Why" below).
      2. Rebases PTS and applies playbackRate via setpts.
      3. Resamples to source_fps (drops/duplicates as needed for the rate).
      4. Applies zoom math (if simple zoom) via crop+scale-lanczos.
      5. Clamps output to exactly `dur_frames` and rebases PTS for clean
         concat downstream.
      6. Sets sar=1 and pix_fmt=yuv420p.

    Why `ceil((dur_frames - 1) * pbr) + 1`:
    Replacing the original `round(dur_frames * pbr)` formula. The previous
    code underflowed in 7 of 9 typical (dur_frames, pbr) combinations —
    Python's banker's rounding (round(8.5)==8) plus the fps filter's PTS-
    based resampling truncated the output by 1+ frame per sub-clip. Across
    ~47 sub-clips per video that produced multi-frame video shortage while
    audio rendered at full duration, causing A/V desync and visible glitch
    at concat boundaries.

    The new formula is the geometric minimum, no safety buffer:
      - dur_frames output frames span (dur_frames - 1) intervals of 1/fps.
      - Each output interval requires `pbr` source intervals at source_fps.
      - Source intervals needed = ceil((dur_frames - 1) * pbr).
      - Source frames needed = intervals + 1 (fencepost — N frames bound
        N-1 intervals).
    The post-fps trim then clamps to exactly dur_frames in case round-near
    in the fps filter emits one extra frame at the tail. Verified exact for
    every (dur_frames, pbr) tested.
    """
    label = f"c{seg_idx}"
    start_from = int(clip["startFromFrames"])
    dur_frames = int(clip["durationInFrames"])
    pbr = float(clip.get("playbackRate", 1.0)) or 1.0
    source_frames_needed = max(1, int(math.ceil((dur_frames - 1) * pbr)) + 1)
    end_frame = start_from + source_frames_needed

    filters = [
        f"trim=start_frame={start_from}:end_frame={end_frame}",
        f"setpts=(PTS-STARTPTS)/{pbr:.6f}",
        f"fps={source_fps:g}",
    ]

    zoom = clip.get("zoomEffect")
    if zoom and zoom.get("type") in SIMPLE_ZOOM_TYPES:
        zoom_filter = build_zoom_filter_chain(zoom, dur_frames, source_fps, canvas_w, canvas_h)
        if zoom_filter:
            filters.append(zoom_filter)

    filters.append(f"trim=end_frame={dur_frames}")
    filters.append("setpts=PTS-STARTPTS")
    filters.append("setsar=1")
    filters.append("format=yuv420p")
    chain = f"[{source_pad}]" + ",".join(filters) + f"[{label}]"
    return chain, label


# ── Top-level: full base+composite filtergraph ───────────────────────────────

def build_final_filtergraph(
    *,
    clips: List[dict],
    transitions: List[dict],
    broll: List[dict],
    micro_segments: List[dict],
    outro: str,
    total_output_frames: int,
    source_fps: float,
    source_input_idx: int = 0,
    micro_input_idx: Optional[int] = None,
    overlay_input_idx: Optional[int] = None,
    broll_input_start_idx: Optional[int] = None,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    # Chunk-aware fields. When called for a single chunk in the chunked-
    # composite path, these tell the builder where this chunk sits in the
    # global timeline so the overlay-input trim and outro fade align
    # correctly. None = legacy single-pass mode.
    chunk_global_start_frame: Optional[int] = None,
    global_total_frames: Optional[int] = None,
) -> Tuple[str, List[str]]:
    """Build the full FFmpeg filtergraph that produces the final composited
    video (pre-audio mux). Caller wraps this in an `ffmpeg -i ... -filter_complex
    "<this>" -map "[final_v]" ... output.mp4` invocation.

    Inputs (FFmpeg `-i` order, by index):
      [source_input_idx]     normalized source video (1080×1920, source_fps)
      [micro_input_idx]      Remotion PromptlyMicroSegments output (h264).
                             None if no Remotion segments are needed.
      [overlay_input_idx]    Remotion PromptlyOverlay output (ProRes 4444 alpha).
                             None if overlay is empty (no captions/MG/text — rare).
      [broll_input_start_idx] First B-roll input index; subsequent B-rolls
                             follow sequentially.

    The filtergraph:
      - Builds each timeline segment (clip or transition):
          * FFmpeg-renderable clip: trim+setpts+(zoom?)+format
          * Remotion-rendered clip or transition: trim from micro segments
      - Concats all segments in timeline order → [base]
      - Overlays B-roll cutaways at their output windows → [base_with_broll]
      - Applies outro fade if configured → [base_faded]
      - Composites alpha overlay onto the base → [final_v]

    Returns (filtergraph_string, [final_video_label]).
    """
    parts: List[str] = []
    segment_labels: List[str] = []

    transitions_by_after_idx = {int(t["afterClipIndex"]): t for t in transitions}

    # ── Pre-split inputs that are referenced multiple times ────────────────
    # FFmpeg's filter_complex requires explicit `split` filters when an input
    # pad feeds multiple downstream chains. Source feeds one chain per
    # ffmpeg-renderable clip; micro_segments.mp4 feeds one chain per
    # remotion-rendered clip + one per transition.
    n_source_uses = sum(1 for c in clips if categorize_clip(c) == "ffmpeg")
    n_micro_uses = (
        sum(1 for c in clips if categorize_clip(c) != "ffmpeg")
        + len(transitions)
    )
    source_pad_pool: List[str] = []
    if n_source_uses > 1:
        labels = [f"src{i}" for i in range(n_source_uses)]
        parts.append(
            f"[{source_input_idx}:v]split={n_source_uses}"
            + "".join(f"[{lbl}]" for lbl in labels)
        )
        source_pad_pool = list(labels)
    elif n_source_uses == 1:
        source_pad_pool = [f"{source_input_idx}:v"]
    micro_pad_pool: List[str] = []
    if micro_input_idx is not None and n_micro_uses > 1:
        labels = [f"mic{i}" for i in range(n_micro_uses)]
        parts.append(
            f"[{micro_input_idx}:v]split={n_micro_uses}"
            + "".join(f"[{lbl}]" for lbl in labels)
        )
        micro_pad_pool = list(labels)
    elif micro_input_idx is not None and n_micro_uses == 1:
        micro_pad_pool = [f"{micro_input_idx}:v"]

    def _next_source_pad() -> str:
        if not source_pad_pool:
            raise RuntimeError("Exhausted source input pads (split count miscounted)")
        return source_pad_pool.pop(0)

    def _next_micro_pad() -> str:
        if not micro_pad_pool:
            raise RuntimeError("Exhausted micro input pads (split count miscounted)")
        return micro_pad_pool.pop(0)

    # ── Per-segment filter chains ────────────────────────────────────────────
    # Output timeline = clip 0 [+ transition 0] + clip 1 [+ transition 1] + ...
    # Each transition lives BETWEEN clip i and clip i+1; clips and transitions
    # both have explicit durationInFrames.
    seg_idx = 0
    for clip_i, clip in enumerate(clips):
        clip_kind = categorize_clip(clip)
        if clip_kind == "ffmpeg":
            chain, lbl = _build_clip_segment_with_pad(
                seg_idx, clip, _next_source_pad(), source_fps, canvas_w, canvas_h,
            )
            parts.append(chain)
            segment_labels.append(lbl)
        else:
            # Remotion-rendered clip (composite-effect zoom). Trim from the
            # PromptlyMicroSegments output by frame range. The micro segments
            # are placed back-to-back in that file at their declared
            # outputStartFrame/durationInFrames.
            if micro_input_idx is None:
                raise RuntimeError(
                    f"Clip {clip_i} requires Remotion (composite zoom "
                    f"{clip.get('zoomEffect', {}).get('type')}) but no "
                    f"micro_input_idx was provided."
                )
            ms = _find_micro_segment_for_clip(micro_segments, clip_i)
            if ms is None:
                raise RuntimeError(
                    f"Clip {clip_i} categorized as remotion but no matching "
                    f"micro_segment was provided."
                )
            lbl = f"c{seg_idx}"
            sf = int(ms["outputStartFrame"])
            ef = sf + int(ms["durationInFrames"])
            parts.append(
                f"[{_next_micro_pad()}]"
                f"trim=start_frame={sf}:end_frame={ef},"
                f"setpts=PTS-STARTPTS,"
                f"fps={source_fps:g},"
                f"setsar=1,"
                f"format=yuv420p"
                f"[{lbl}]"
            )
            segment_labels.append(lbl)
        seg_idx += 1

        # Transition after this clip (if any)
        trans = transitions_by_after_idx.get(clip_i)
        if trans is not None:
            if micro_input_idx is None:
                raise RuntimeError(
                    f"Transition after clip {clip_i} ({trans.get('type')}) "
                    f"requires Remotion but no micro_input_idx was provided."
                )
            ms = _find_micro_segment_for_transition(micro_segments, clip_i)
            if ms is None:
                raise RuntimeError(
                    f"Transition after clip {clip_i} has no matching "
                    f"micro_segment."
                )
            lbl = f"c{seg_idx}"
            sf = int(ms["outputStartFrame"])
            ef = sf + int(ms["durationInFrames"])
            parts.append(
                f"[{_next_micro_pad()}]"
                f"trim=start_frame={sf}:end_frame={ef},"
                f"setpts=PTS-STARTPTS,"
                f"fps={source_fps:g},"
                f"setsar=1,"
                f"format=yuv420p"
                f"[{lbl}]"
            )
            segment_labels.append(lbl)
            seg_idx += 1

    # ── Concat all segments → [base] ─────────────────────────────────────────
    if not segment_labels:
        raise RuntimeError("build_final_filtergraph: no segments produced")
    if len(segment_labels) == 1:
        parts.append(f"[{segment_labels[0]}]null[base]")
    else:
        concat_inputs = "".join(f"[{lbl}]" for lbl in segment_labels)
        parts.append(f"{concat_inputs}concat=n={len(segment_labels)}:v=1:a=0[base]")

    # ── B-roll overlays at their output-time windows ─────────────────────────
    cur = "base"
    if broll and broll_input_start_idx is not None:
        for bi, br in enumerate(broll):
            br_input_idx = broll_input_start_idx + bi
            br_filter, br_label = build_broll_input_filter(
                bi, br, br_input_idx, source_fps, canvas_w, canvas_h,
            )
            parts.append(br_filter)
            from_frame = int(br["fromFrame"])
            dur_frames = int(br["durationInFrames"])
            t0 = from_frame / source_fps
            t1 = (from_frame + dur_frames) / source_fps
            next_label = f"base_b{bi}"
            parts.append(
                f"[{cur}][{br_label}]"
                f"overlay=x=0:y=0:format=auto:eof_action=pass:"
                f"enable='between(t,{t0:.6f},{t1:.6f})'"
                f"[{next_label}]"
            )
            cur = next_label

    # ── Outro fade ───────────────────────────────────────────────────────────
    # Single-pass mode (chunk_global_start_frame is None): fade applied to
    #   the tail of the full output.
    # Chunked mode: fade applies only to the chunk(s) containing the global
    #   fade window; fade_start is recomputed in CHUNK-LOCAL seconds.
    if outro and outro != "none":
        fade_color = "black" if outro == "fade_black" else "white"
        fade_dur_seconds = 1.0
        if chunk_global_start_frame is None:
            total_seconds = total_output_frames / source_fps
            fade_start_seconds = max(0.0, total_seconds - fade_dur_seconds)
            apply_fade = True
        else:
            assert global_total_frames is not None, (
                "global_total_frames must be set in chunked mode"
            )
            global_fade_start_frame = max(
                0, int(global_total_frames - round(fade_dur_seconds * source_fps))
            )
            chunk_end_frame = chunk_global_start_frame + total_output_frames
            # Apply only if the global fade window overlaps this chunk.
            apply_fade = chunk_end_frame > global_fade_start_frame
            if apply_fade:
                # Convert global fade start to chunk-local seconds.
                local_fade_start_frame = max(
                    0, global_fade_start_frame - chunk_global_start_frame
                )
                fade_start_seconds = local_fade_start_frame / source_fps
        if apply_fade:
            next_label = "base_faded"
            parts.append(
                f"[{cur}]fade=t=out:st={fade_start_seconds:.6f}:"
                f"d={fade_dur_seconds:.6f}:c={fade_color}[{next_label}]"
            )
            cur = next_label

    # ── Alpha overlay composite ──────────────────────────────────────────────
    # Single-pass mode: overlay.mov covers the full output, no trim needed.
    # Chunked mode: overlay.mov covers the GLOBAL output; we trim to this
    #   chunk's frame range and rebase to chunk-local PTS.
    if overlay_input_idx is not None:
        if chunk_global_start_frame is not None:
            ov_lbl = f"ov_chunk"
            sf = int(chunk_global_start_frame)
            ef = sf + int(total_output_frames)
            parts.append(
                f"[{overlay_input_idx}:v]"
                f"trim=start_frame={sf}:end_frame={ef},"
                f"setpts=PTS-STARTPTS"
                f"[{ov_lbl}]"
            )
            parts.append(
                f"[{cur}][{ov_lbl}]overlay=format=auto:shortest=0[final_v]"
            )
        else:
            parts.append(
                f"[{cur}][{overlay_input_idx}:v]overlay=format=auto:shortest=0[final_v]"
            )
    else:
        parts.append(f"[{cur}]null[final_v]")

    return ";".join(parts), ["final_v"]


def _find_micro_segment_for_clip(micro_segments: List[dict], clip_idx: int) -> Optional[dict]:
    for ms in micro_segments:
        if ms.get("type") == "zoom_clip" and int(ms.get("_clipIndex", -1)) == clip_idx:
            return ms
    return None


def _find_micro_segment_for_transition(micro_segments: List[dict], after_clip_idx: int) -> Optional[dict]:
    for ms in micro_segments:
        if (ms.get("type") == "transition"
                and int(ms.get("_afterClipIndex", -2)) == after_clip_idx):
            return ms
    return None


# ── Timeline slicing for chunked composite ───────────────────────────────────
#
# The chunked-composite path runs N parallel ffmpeg invocations, each
# producing one mp4 piece for a frame range of the output timeline. To do
# this, we take the full timeline (clips, transitions, broll, micro_segments)
# and slice each entity at the chunk boundary, producing chunk-local copies
# with adjusted timing.
#
# Frame-coordinate semantics throughout this module:
#   * GLOBAL output frame: position in the entire output video (0 to total-1)
#   * CHUNK output frame:  position in this chunk's piece (0 to chunk_size-1)
#   * CLIP-LOCAL output frame: position in a single clip's playback (after
#                              `setpts=PTS/playbackRate` rebase).
#
# Slicing keeps the timeline-order semantics intact: each chunk's sliced
# clips/transitions sum exactly to (chunk_end - chunk_start) frames, so when
# the N chunks are concatenated lossless they reconstruct the full video.

def slice_timeline_for_chunk(
    chunk_start: int,
    chunk_end: int,
    clips: List[dict],
    transitions: List[dict],
    broll: List[dict],
    micro_segments: List[dict],
    source_fps: float,
) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    """Produce a chunk-local view of the timeline visible in the GLOBAL output
    frame range [chunk_start, chunk_end). Frame counters in the returned dicts
    are CHUNK-LOCAL (0 = first frame of this chunk).

    Returns (chunk_clips, chunk_transitions, chunk_broll, chunk_micro_segments)
    suitable for passing into build_final_filtergraph as if they were a
    standalone timeline of length (chunk_end - chunk_start) frames.
    """
    chunk_clips: List[dict] = []
    chunk_transitions: List[dict] = []
    chunk_broll: List[dict] = []
    chunk_micro_segments: List[dict] = []

    transitions_by_after_idx = {int(t["afterClipIndex"]): t for t in transitions}

    cursor_global = 0
    new_clip_idx = 0
    for clip_i, clip in enumerate(clips):
        clip_global_start = cursor_global
        clip_dur = int(clip["durationInFrames"])
        clip_global_end = clip_global_start + clip_dur
        cursor_global = clip_global_end

        # Does this clip overlap the chunk window?
        if clip_global_end > chunk_start and clip_global_start < chunk_end:
            visible_global_start = max(clip_global_start, chunk_start)
            visible_global_end = min(clip_global_end, chunk_end)
            local_start = visible_global_start - clip_global_start  # offset into clip
            local_end = visible_global_end - clip_global_start
            local_duration = local_end - local_start

            playback_rate = float(clip.get("playbackRate", 1.0)) or 1.0
            sliced = dict(clip)
            sliced["startFromFrames"] = int(
                clip["startFromFrames"] + round(local_start * playback_rate)
            )
            sliced["durationInFrames"] = local_duration

            # Shift zoom events: they're in CLIP-LOCAL OUTPUT MS coords. After
            # slicing, events past `local_start` need to shift by -local_start
            # ms-equivalent so n=0 in the sliced clip still maps to the right
            # event timing.
            zoom = clip.get("zoomEffect")
            if isinstance(zoom, dict) and zoom.get("events"):
                local_start_ms = (local_start / source_fps) * 1000.0
                shifted_events = []
                for ev in zoom["events"]:
                    if not isinstance(ev, dict):
                        continue
                    try:
                        ev_start = float(ev.get("startMs", 0.0))
                        ev_dur = float(ev.get("durationMs", 0.0))
                    except (TypeError, ValueError):
                        continue
                    # Keep ALL events regardless of where they fall relative
                    # to the chunk window. Events entirely before/after the
                    # chunk produce no visible effect (the per-frame zoom
                    # expression evaluates them to 0/1 outside their range).
                    # Critically: events that started BEFORE the chunk and
                    # are still active inside it MUST keep their original
                    # duration — otherwise the easing curve gets re-fit to
                    # the visible-only span and the zoom motion no longer
                    # continues smoothly across chunk boundaries.
                    new_ev = dict(ev)
                    new_ev["startMs"] = ev_start - local_start_ms
                    new_ev["durationMs"] = ev_dur
                    shifted_events.append(new_ev)
                if shifted_events:
                    new_zoom = dict(zoom)
                    new_zoom["events"] = shifted_events
                    sliced["zoomEffect"] = new_zoom
                else:
                    sliced.pop("zoomEffect", None)

            # If this is a remotion-rendered clip, slice its micro_segment too.
            if categorize_clip(clip) == "remotion":
                ms = _find_micro_segment_for_clip(micro_segments, clip_i)
                if ms is None:
                    raise RuntimeError(
                        f"slice_timeline_for_chunk: clip {clip_i} categorized "
                        f"as remotion but no matching micro_segment found."
                    )
                # The micro_segments.mp4 file holds frames at positions
                # [outputStartFrame, outputStartFrame + durationInFrames). For
                # the visible portion of this clip, we want the corresponding
                # sub-range from the same file.
                new_ms = dict(ms)
                new_ms["outputStartFrame"] = int(ms["outputStartFrame"]) + local_start
                new_ms["durationInFrames"] = local_duration
                new_ms["_clipIndex"] = new_clip_idx
                chunk_micro_segments.append(new_ms)

            chunk_clips.append(sliced)
            current_new_clip_idx = new_clip_idx
            new_clip_idx += 1

            # Transition after this clip (only if BOTH clip and transition
            # are visible in the chunk; if the transition's tail is in another
            # chunk, slice it).
            trans = transitions_by_after_idx.get(clip_i)
            if trans is not None:
                trans_global_start = cursor_global
                trans_dur = int(trans["durationInFrames"])
                trans_global_end = trans_global_start + trans_dur
                cursor_global = trans_global_end

                if trans_global_end > chunk_start and trans_global_start < chunk_end:
                    t_visible_start = max(trans_global_start, chunk_start)
                    t_visible_end = min(trans_global_end, chunk_end)
                    t_local_start = t_visible_start - trans_global_start
                    t_local_end = t_visible_end - trans_global_start
                    t_local_duration = t_local_end - t_local_start

                    sliced_trans = dict(trans)
                    sliced_trans["durationInFrames"] = t_local_duration
                    sliced_trans["afterClipIndex"] = current_new_clip_idx

                    ms = _find_micro_segment_for_transition(micro_segments, clip_i)
                    if ms is None:
                        raise RuntimeError(
                            f"slice_timeline_for_chunk: transition after "
                            f"clip {clip_i} has no matching micro_segment."
                        )
                    new_ms = dict(ms)
                    new_ms["outputStartFrame"] = int(ms["outputStartFrame"]) + t_local_start
                    new_ms["durationInFrames"] = t_local_duration
                    new_ms["_afterClipIndex"] = current_new_clip_idx
                    chunk_micro_segments.append(new_ms)

                    chunk_transitions.append(sliced_trans)
            # else: trans falls outside chunk. Don't add. cursor already advanced.
        else:
            # Clip outside chunk — still need to advance cursor past the
            # following transition (if any) so subsequent clips' positions
            # are computed correctly.
            trans = transitions_by_after_idx.get(clip_i)
            if trans is not None:
                cursor_global += int(trans["durationInFrames"])

    # B-roll: simple frame-range overlap check, then slice.
    for br in broll:
        br_global_start = int(br["fromFrame"])
        br_dur = int(br["durationInFrames"])
        br_global_end = br_global_start + br_dur
        if br_global_end <= chunk_start or br_global_start >= chunk_end:
            continue
        v_start = max(br_global_start, chunk_start)
        v_end = min(br_global_end, chunk_end)
        local_start = v_start - br_global_start  # offset into broll's own timeline
        local_duration = v_end - v_start
        playback_rate = float(br.get("playbackRate", 1.0)) or 1.0

        sliced_br = dict(br)
        # fromFrame is OUTPUT-frame in the chunk-local timeline (0 = first
        # frame of this chunk).
        sliced_br["fromFrame"] = v_start - chunk_start
        sliced_br["durationInFrames"] = local_duration
        sliced_br["seekFromFrames"] = int(
            br["seekFromFrames"] + round(local_start * playback_rate)
        )
        chunk_broll.append(sliced_br)

    return chunk_clips, chunk_transitions, chunk_broll, chunk_micro_segments


def split_timeline_into_chunks(total_output_frames: int, n_chunks: int) -> List[Tuple[int, int]]:
    """Partition [0, total_output_frames) into n_chunks contiguous half-open
    ranges (start, end) with end - start frames each (rounded). Used by the
    chunked-composite path; trivially compatible with the existing
    _split_frames helper in handler.py but returns half-open ranges to match
    Python slice semantics."""
    if total_output_frames <= 0 or n_chunks <= 0:
        return []
    per = total_output_frames // n_chunks
    remainder = total_output_frames % n_chunks
    ranges = []
    cursor = 0
    for i in range(n_chunks):
        chunk_size = per + (1 if i < remainder else 0)
        if chunk_size == 0:
            continue
        ranges.append((cursor, cursor + chunk_size))
        cursor += chunk_size
    return ranges


# ── Public: build full micro-segments input + per-segment metadata ───────────

def build_micro_segments_input(
    clips: List[dict],
    transitions: List[dict],
    source_url: str,
    source_fps: float,
    canvas_w: int = 1080,
    canvas_h: int = 1920,
) -> Tuple[Optional[dict], List[dict]]:
    """Plan the PromptlyMicroSegments composition input.

    Returns (input_dict, segments_with_metadata):
      input_dict           — the JSON Python writes to disk for the Remotion
                             render (None if no segments are needed).
      segments_with_metadata — same segments, but each entry has internal keys
                             `_clipIndex` or `_afterClipIndex` so the FFmpeg
                             filtergraph builder can locate them by source.
    """
    segments: List[dict] = []
    cursor = 0

    transitions_by_idx = {int(t["afterClipIndex"]): t for t in transitions}

    for clip_i, clip in enumerate(clips):
        if categorize_clip(clip) == "remotion":
            dur = int(clip["durationInFrames"])
            segments.append({
                "type": "zoom_clip",
                "outputStartFrame": cursor,
                "durationInFrames": dur,
                "clip": clip,
                "_clipIndex": clip_i,
            })
            cursor += dur
        trans = transitions_by_idx.get(clip_i)
        if trans is not None:
            dur = int(trans["durationInFrames"])
            segments.append({
                "type": "transition",
                "outputStartFrame": cursor,
                "durationInFrames": dur,
                "transition": trans,
                "_afterClipIndex": clip_i,
            })
            cursor += dur

    if not segments:
        return None, []

    # Strip internal metadata from the JSON we hand to Remotion.
    public_segments = []
    for s in segments:
        ps = {
            "type": s["type"],
            "outputStartFrame": s["outputStartFrame"],
            "durationInFrames": s["durationInFrames"],
        }
        if "clip" in s:
            ps["clip"] = s["clip"]
        if "transition" in s:
            ps["transition"] = s["transition"]
        public_segments.append(ps)

    input_dict = {
        "sourceUrl": source_url,
        "fps": source_fps,
        "width": canvas_w,
        "height": canvas_h,
        "totalDurationInFrames": cursor,
        "segments": public_segments,
    }
    return input_dict, segments
