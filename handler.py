# Modal worker entrypoint
import subprocess
import os
import sys
import ssl
import glob
import hashlib
import math
import requests
import tempfile
import time
import shutil
import json
import re
import concurrent.futures
import threading
import signal
from datetime import datetime
import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

HANDLER_VERSION = "3.2.0"
# Pro for every Gemini call — editorial placement AND utility calls (B-roll
# visual picker, plan-diff re-edit). Flash's instruction-following ceiling
# is too low for any decision in this pipeline; the cost/latency premium of
# Pro is worth it for consistent quality across every call.
#
# Gemini 3.1 Pro is STILL IN PREVIEW per Google's docs at
# https://ai.google.dev/gemini-api/docs/models (verified 2026-06-14).
# There is no `gemini-3.1-pro` GA SKU yet — the only working API ID is
# `gemini-3.1-pro-preview`. Confirmed twice now: tried the GA swap
# 2026-06-14 morning (404), reverted, billing was empty so we hypothesized
# the 404 was downstream of the 429 prepayment-depleted error, paid for
# credits, tried again — still 404. Google's docs are authoritative:
# 3.1 Pro = Preview. When Google ships the GA SKU, the startup
# diagnostic (`[startup] available gemini-3.x models:` line, see
# _log_available_gemini_models below) will show the new ID and we
# can swap to a VERIFIED name from the API, not a guessed one.
GEMINI_MODEL = "gemini-3.1-pro-preview"
GEMINI_EDITORIAL_MODEL = "gemini-3.1-pro-preview"
# Bump when the edit_plan schema or render pipeline changes in a way that breaks
# replay of older persisted plans. Returned in every job response so the server
# can tag video_jobs.render_version and gate re-edit compatibility.
RENDER_VERSION = 1

# Translate Gemini's semantic safe-zone anchors into the MG pack's MGAnchor
# vocabulary (see src/remotion/src/motion-graphics/shared/positioning.ts).
# Each MG component's `resolveMGPosition` accepts anchor + offsets and places
# content inside a canvas-sized AbsoluteFill using flex alignment. We pass the
# mapped anchor through `props.anchor` so the component honors it instead of
# falling back to its own default.
SEMANTIC_TO_MG_ANCHOR = {
    "upper_third_safe": "top",
    "center":           "center",
    "lower_third_safe": "bottom",
    "left_safe":        "left",
    "right_safe":       "right",
}

# ── Pydantic EditPlan schema ─────────────────────────────────────────────────
# Gemini's response_json_schema enforces this at token-generation time — the
# model cannot emit missing fields, wrong types, or out-of-enum values. Python
# validators below still enforce cross-field semantic constraints (timestamps
# matching kept words, non-overlapping windows, etc.) but shape is guaranteed
# before validators even see the output.
#
# Design principle — collapse degrees of freedom:
#   - emphasis_moments has NO `t` field. Python derives t from word_indices[0]
#     so the two can never disagree.
#   - sound_effects has NO `t` or `word` fields — Gemini emits `word_index`
#     and Python looks up the rest from the transcript.
#   - There is no continuous speed curve. Pacing is expressed via the per-cut
#     `speed` field (constant 0.7–1.4× per cut). "Speed ramping" aesthetics
#     come from adjacent cuts at contrasting speeds (the buildup-arrival
#     pattern), not from interpolating speed within a single clip.
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Literal, Dict, Any

# Pydantic schemas mirroring src/remotion/src/types.ts. Validating the
# render input dicts against these models BEFORE writing JSON turns every
# Python-vs-Remotion shape mismatch into an immediate, named Python error
# at the boundary instead of an opaque renderer crash 90 seconds into
# headless Chromium. See render_schemas.py for the full mirror; the smoke
# test (scripts/smoke.sh) catches drift between this file and types.ts.
from render_schemas import (
    PromptlyRenderInput as _SchemaOverlayInput,
    PromptlyMicroSegmentsInput as _SchemaMicroInput,
)

# Component-type vocabularies — single source of truth shared with
# render_schemas.py. Adding a new type means editing type_registries.py
# only; both this file's Pydantic Literals (at handler.py:~118) and
# render_schemas.py's mirror derive automatically. See type_registries.py
# for the rationale and the failure mode this structure prevents.
from type_registries import (
    TIGHT_CUT_OVERLAY_MECHANISM_PHRASES,
    VALID_CAPTION_STYLES,
    VALID_MG_TYPES,
    VALID_TIGHT_CUT_OVERLAYS,
    VALID_TRANSITION_TYPES,
    VALID_ZOOM_TYPES,
)


def _validate_and_write_render_input(
    label: str,
    payload: dict,
    schema_cls,
    output_path: str,
) -> None:
    """Validate `payload` against `schema_cls` and write it to `output_path`.

    Validation runs on the dict as-is; the dict itself is what gets written
    (no Pydantic-induced normalization of field order, None-stripping, etc).
    A ValidationError surfaces with the bad field path, expected type, and
    actual value — fail-fast at the boundary instead of inside React.
    """
    try:
        schema_cls.model_validate(payload)
    except ValidationError as ve:
        # Pydantic v2's str(ve) gives one error per line with field path,
        # input value, and expected type — all you need to fix it.
        raise RuntimeError(
            f"[{label}] render input failed schema validation against "
            f"{schema_cls.__name__}:\n{ve}"
        ) from ve
    with open(output_path, "w") as _f:
        json.dump(payload, _f)

# Pydantic Literals derive from type_registries — single source of truth
# for handler.py + render_schemas.py. See type_registries.py for the
# canonical frozensets. Adding a new component type means editing that
# one file; these Literals update automatically.
_CAPTION_STYLES = Literal[tuple(sorted(VALID_CAPTION_STYLES))]
_TRANSITION_TYPES = Literal[tuple(sorted(VALID_TRANSITION_TYPES))]
_ZOOM_TYPES = Literal[tuple(sorted(VALID_ZOOM_TYPES))]
# Natural duration per zoom type (ms). When Gemini omits durationMs from a
# zoom event, the pipeline fills in the per-type natural duration so the
# camera move plays at the look it was designed for. This removes a degree
# of freedom Gemini was getting wrong (subtle 200ms SmoothPushes that don't
# read). Each value is the full event span including ramp-in + hold +
# ramp-out (see each component's tsx for the specific motion shape).
ZOOM_NATURAL_DURATION_MS = {
    "SmoothPush":    1200,
    "SnapReframe":    700,
    "FocusWindow":   1500,
    "StepZoom":       800,
    "LetterboxPush": 1400,
    "StageZoom":     1800,  # one event drives the full 5-phase two-stage progression internally
    "DepthPull":     2200,
}
# Default scale per type — used when Gemini omits scale. These are the
# perceptible-baseline values; deeper or gentler is a Gemini override.
ZOOM_NATURAL_SCALE = {
    "SmoothPush":    1.22,
    "SnapReframe":   1.30,
    "FocusWindow":   1.80,  # bgScale; FocusWindow is dual-view, not a push
    "StepZoom":      1.25,
    "LetterboxPush": 1.25,
    "StageZoom":     1.30,  # final stage scale; firstStage handled separately
    "DepthPull":     1.25,
}
# Per-type PERCEPTUAL PEAK reach time relative to event start.
# Measured from each component's actual ease curve in
# src/remotion/src/zoom/<type>/. This is the moment scale first hits its
# target — what the viewer perceives as "the zoom landed."
#
# The prompt formula at handler.py:~3317 ("startMs = word_start_ms −
# natural_duration") puts the *math endpoint* on the word, but for every
# type the math endpoint is "ramp-out done" — scale is back at 1.0. The
# perceptual peak lands HUNDREDS OF MILLISECONDS BEFORE the word, so
# zooms read as misaligned ("late" via SnapReframe's trailing release;
# "missed entirely" via SmoothPush returning to neutral on the word).
#
# Python overrides startMs at validation so:
#   new_startMs = word_start_ms − ZOOM_PEAK_REACH_MS[type]
# producing peak-on-word alignment. The prompt formula is now
# informational only. Do NOT change the prompt to use these offsets —
# Python is the source of truth, and a prompt-side change would
# double-correct.
ZOOM_PEAK_REACH_MS = {
    "SmoothPush":     420,   # 35% × 1200ms (ramp-in end)
    "SnapReframe":    171,   # spring 99% settling (damping=28, mass=0.6, stiffness=260)
    "FocusWindow":    234,   # spring 99% settling (damping=24, mass=0.7, stiffness=180)
    "StepZoom":         0,   # instant — peak at startMs
    "LetterboxPush":  490,   # 35% × 1400ms (ramp-in end)
    "StageZoom":     1170,   # 65% × 1800ms (second-stage peak)
    "DepthPull":      770,   # 35% × 2200ms (ramp-in end)
}
_MG_TYPES = Literal[tuple(sorted(VALID_MG_TYPES))]
_SEMANTIC_ANCHOR = Literal[
    "upper_third_safe", "center", "lower_third_safe", "left_safe", "right_safe",
]
_TEXT_OVERLAY_VARIANTS = Literal[
    "sticky_note", "quote_card", "caption_match",
]
_SFX_SOUNDS = Literal[
    "boom", "hit", "drum_roll", "reverse", "ching", "ding", "click",
    "camera_shutter", "sad_trombone", "typing", "whoosh_slow",
    "transition_smooth", "thunder", "pop",
]

class _CaptionPositionChange(BaseModel):
    # Position-change event at a specific kept word. Python synthesizes the
    # actual caption_position_segments (with from_seconds/to_seconds/position)
    # after the call returns. Every segment boundary is by construction a
    # real word start timestamp — no mismatch possible.
    word_index: int
    position: Literal["top", "center", "bottom"]

class _ZoomEvent(BaseModel):
    startMs: int
    # durationMs is optional. When omitted, the pipeline fills in
    # ZOOM_NATURAL_DURATION_MS[type]. Gemini emits this only when overriding
    # the natural duration for a specific moment (rare).
    durationMs: Optional[int] = None
    scale: Optional[float] = None
    originX: Optional[float] = None
    originY: Optional[float] = None

class _ZoomEffect(BaseModel):
    type: _ZOOM_TYPES
    events: List[_ZoomEvent] = Field(default_factory=list)

class _EmphasisMotionGraphic(BaseModel):
    type: _MG_TYPES
    anchor: _SEMANTIC_ANCHOR
    props: Dict[str, Any] = Field(default_factory=dict)

class _EmphasisMoment(BaseModel):
    # `t` is DERIVED by Python from word_indices[0].start — not emitted by Gemini.
    # Visual layers on an emphasis: zoom_effect (optional) and motion_graphic
    # (optional). Color effects were removed from the pipeline (talking-head
    # videos don't need cinematic grades) — emphasis is now purely a
    # zoom/MG/SFX combo.
    #
    # `viewer_feeling` is required. Earlier we removed it because the way the
    # old prompt forced Gemini to JUSTIFY each choice independently produced
    # hedging. The v2 prompt (window doctrine + arc-spine) reframes this
    # field: it's the editor's named end-state for the moment, used as the
    # grounding that ties the emphasis to the arc position's intended feeling.
    # Recipe_eval logs failures when this drifts from generic phrases.
    word_indices: List[int]
    type: Literal["punchline", "statement", "question", "reaction", "revelation"]
    intensity: Literal["high", "medium"]
    duration: float
    viewer_feeling: str
    zoom_effect: Optional[_ZoomEffect] = None
    motion_graphic: Optional[_EmphasisMotionGraphic] = None

class _TextOverlayNote(BaseModel):
    text: str
    color: str
    rotation: float

class _TextOverlay(BaseModel):
    variant: _TEXT_OVERLAY_VARIANTS
    # Word-anchored timing: overlay appears when `start_word_index`'s word is
    # spoken (projected to output frames by Python). Duration is caller-
    # specified because text overlays are short title cards with chosen
    # length, not phrase-spanning. Python rejects entries whose
    # start_word_index targets a removed word.
    start_word_index: int
    duration_seconds: float
    # Variant-specific — Python validator enforces per-variant required fields.
    topText: Optional[str] = None
    bottomText: Optional[str] = None
    notes: Optional[List[_TextOverlayNote]] = None
    quote: Optional[str] = None
    attribution: Optional[str] = None
    text: Optional[str] = None
    # caption_match position: "top" or "center" only. NEVER "bottom" — the
    # main captions live in the bottom zone by default, so a bottom-anchored
    # caption_match would collide. Text overlays own the upper half;
    # captions own the lower half. These zones never share screen space.
    position: Optional[Literal["top", "center"]] = None

class _MotionGraphic(BaseModel):
    # No `viewer_feeling` — removed because defense fields force hedging.
    # Gemini's editorial vision (set in video_plan.editorial_vision) is the
    # single source of truth for whether a component fits.
    type: _MG_TYPES
    # Word-anchored timing. MG appears when `start_word_index`'s word is
    # spoken and disappears when `end_word_index`'s word ends. Python
    # projects word start/end times to output frames. Both indices must
    # reference kept words. For fixed-duration overlays pinned to a
    # single word (e.g. a 3s StatCard on one punchline), set
    # start_word_index == end_word_index and provide duration_seconds
    # as an override.
    start_word_index: int
    end_word_index: int
    duration_seconds: Optional[float] = None  # override; null = use word span
    anchor: _SEMANTIC_ANCHOR
    props: Dict[str, Any] = Field(default_factory=dict)

class _SoundEffect(BaseModel):
    # Gemini emits word_index only; Python derives t + word text from transcript.
    word_index: int
    sound: _SFX_SOUNDS

class _BrollClip(BaseModel):
    keyword: str
    start_word_index: int
    end_word_index: int
    reason: str

class _Transition(BaseModel):
    after_word_index: int
    type: _TRANSITION_TYPES
    # Component-specific optional props; most are passthrough.
    direction: Optional[str] = None
    palette: Optional[str] = None
    title: Optional[str] = None
    label: Optional[str] = None
    variant: Optional[str] = None
    theme: Optional[Literal["dark", "light"]] = None
    accentColor: Optional[str] = None
    titleColor: Optional[str] = None
    labelColor: Optional[str] = None
    showDivider: Optional[bool] = None
    intensity: Optional[float] = None
    flashColor: Optional[str] = None

class _VideoPlanMoment(BaseModel):
    """One emphasis-worthy moment in the video. Gemini names these in video_plan
    BEFORE picking components, so every component placed later anchors to a
    moment that's been explicitly identified as load-bearing."""
    word_index: int
    # One-sentence description of what lands at this moment — the joke
    # resolving, the new fact arriving, the speaker's reaction breaking.
    what_lands: str
    # One-sentence justification for why this specific moment is worth
    # emphasizing vs. the surrounding context. Forces Gemini to articulate
    # the editorial reason instead of picking moments by intuition.
    why_emphasis: str
    # REQUIRED visual-grounding field. One sentence on what is VISIBLE in
    # the proxy at this moment — the speaker's expression, gesture, head
    # position, framing, energy. This is what forces Gemini to actually
    # use its multimodal capability on the proxy attached to the call,
    # not to reason purely from the transcript with annotations.
    what_i_saw: str
    # REQUIRED — the editor's named viewer end-state for this moment. The v2
    # prompt uses this as the bridge between key_moment and arc position:
    # the feeling drives which zoom personality fits, which SFX flavor, etc.
    # Format: one specific phrase, not generic ("the camera leaning in as
    # the line lands" not "feels exciting").
    viewer_feeling: str


# Arc positions — the editorial role a stretch of dialogue plays in the
# overall narrative. Every kept word lives inside exactly one arc segment,
# and downstream component decisions (zoom personality, B-roll density,
# MG character, transition flavor, caption emphasis) reference the arc
# position of the word they're considering. Switching from "rule fires
# when X" to "treatment varies by arc position" is what makes choices
# feel connected to a unified narrative spine instead of independent.
_ArcPosition = Literal[
    "hook",       # opening 1-3s, curiosity gap, viewer decides to stay
    "build",      # setup / context / anticipation; tension accumulating
    "mid_peak",   # an intermediate peak — a reaction, a punchline, a fact
    "payoff",     # the strongest moment, the line everyone shares
    "breather",   # space between peaks; silence working, restraint paying off
    "close",      # final beat, lock-in, last word lands
]


class _ArcSegment(BaseModel):
    """One arc segment — a contiguous stretch of kept words that plays the
    same editorial role. Segments tile the full kept transcript without gaps
    or overlaps; together they describe the dramatic shape of the video at
    word-index granularity.

    Every downstream component decision (zoom, B-roll, MG, transition, SFX,
    caption emphasis) reads the arc position of the moment it's targeting
    and picks treatment that fits that position. The arc is the SPINE; the
    components are the muscles that move with it.
    """
    # First kept-word index of this segment (inclusive). Segment 0 starts at 0.
    start_word_index: int
    # Last kept-word index of this segment (inclusive). The last segment's
    # end_word_index must equal the final kept word index.
    end_word_index: int
    # The editorial role this segment plays. See _ArcPosition above for
    # the meaning of each tag.
    position: _ArcPosition
    # 0.0 to 1.0 — the energy intensity of this segment relative to the
    # video's peak. Used by downstream decisions to scale treatment intensity
    # (a payoff at 1.0 wants more commitment than a payoff at 0.7).
    intensity: float


class _VideoPlan(BaseModel):
    """Gemini's editorial plan for the video, written BEFORE component
    placement. Forces moment-first reasoning: identify the dramatic shape and
    the 2-4 strongest moments, then place components that serve those moments.

    Without this scaffold Gemini ends up reasoning component-by-component
    ("here's an MG catalog — which fits where"), producing edits where each
    placement is locally correct but the whole doesn't compose. With it,
    Gemini commits to the shape first and components are downstream of the
    shape.
    """
    # 1-2 sentence factual summary of what happens in the video. Different
    # from video_identity (which describes the video's character); this is
    # the literal narrative arc.
    what_happens: str
    # The kept-word index where the HOOK lands — the first 1-2 seconds that
    # promise something specific to the viewer. Often word_index = 0 or
    # close to it, but not always (some videos open on a question, the
    # hook lands when the question completes).
    hook_word_index: int
    # The kept-word index where the PAYOFF lands — the strongest moment in
    # the whole video, the moment the viewer rewatches and shares. This
    # word receives the strongest visual emphasis.
    payoff_word_index: int
    # The kept-word index of the CLOSE — the final moment (a reaction shot,
    # a tagline, the last word). Lands with confidence; the close earns
    # the visual close-out (final transition, held reaction).
    close_word_index: int
    # 2-4 moments — the strongest moments in the video. These are the
    # candidates for emphasis_moments later. Every emphasis_moment emitted
    # must anchor to a word_index that appears in this list.
    key_moments: List[_VideoPlanMoment]
    # One sentence describing the dramatic shape: how the video moves from
    # hook through setup through development through payoff through close.
    # Forces Gemini to think about the WHOLE before picking parts.
    story_shape: str
    # The arc spine — a tiled list of segments covering every kept word.
    # Each segment names its editorial role (hook/build/mid_peak/payoff/
    # breather/close) and intensity. Every downstream component decision
    # references this layer. Required; the spine isn't optional. Filled
    # AFTER hook/payoff/close/key_moments are committed but BEFORE any
    # other field is touched.
    arc_segments: List[_ArcSegment]
    # THE EDITORIAL VISION — one specific sentence committing to HOW this
    # video will be cut. Not what the video IS (that's video_identity).
    # Not what HAPPENS (that's what_happens). Not the SHAPE (that's
    # story_shape or arc_segments). The VISION is the editor's creative
    # stake: "I'm going to lean into the absurdity with bright caption
    # styles, pop SFX on every receipt detail, and a slow LetterboxPush
    # on the moment he opens the bag." Or: "I'm keeping this close and
    # quiet — gentle SmoothPush, warm cinematic captions, silence
    # between sentences earning the payoff." The vision drives EVERY
    # subsequent component choice. When a component fits the vision,
    # place it boldly. When it doesn't, skip it. The vision replaces
    # the previous per-component `viewer_feeling` defense — instead of
    # justifying each choice individually, Gemini commits to one creative
    # treatment for the whole video and lets every component flow from it.
    editorial_vision: str


class PostCutPlan(BaseModel):
    """Schema for the SECOND Gemini call — visual placement on a perfect transcript.

    By construction, this call only ever sees the kept-only transcript with
    new contiguous indices [0..M-1]. Cut words don't exist in this index
    space — anchor-on-cut is physically impossible because there's no way
    to reference a word that isn't there. Word indices in this output
    reference the kept-only space; Python translates them back to source
    indices after the call returns.
    """
    video_identity: str
    # video_plan is the editorial scaffold Gemini fills BEFORE picking any
    # components. Forces moment-first reasoning: identify the dramatic shape
    # and the 2-4 strongest moments, then every component placed later
    # anchors to a moment already named here. See "VIDEO PLAN — FILL THIS
    # BEFORE PICKING COMPONENTS" in the post-cuts prompt for the workflow.
    video_plan: _VideoPlan
    caption_style: _CAPTION_STYLES
    caption_keywords: List[str]
    emphasis_moments: List[_EmphasisMoment]
    transitions: List[_Transition]
    sound_effects: List[_SoundEffect]
    motion_graphics: List[_MotionGraphic]
    text_overlays: List[_TextOverlay]
    broll_clips: List[_BrollClip]
    caption_position_changes: List[_CaptionPositionChange]
    thumbnail_word_index: int
    audio_denoise: bool
    outro: Literal["none", "fade_black", "fade_white"]
    aspect_ratio: Literal["9:16"]
    # Optional one-line rationale. Mechanical-cuts notes are filled by the
    # FIRST call (silence/filler/stutter detection) and merged in after this
    # call returns; if Gemini emits notes here, they take precedence in the
    # downstream merge (see edit_plan construction in generate_edit_gemini).
    notes: Optional[str] = None


class EditPlan(BaseModel):
    """Final merged shape consumed by downstream renderer code.

    This is NOT a Gemini output schema — it's the dict shape Python builds
    by merging mechanical cut detection results + PostCutPlan after anchor
    translation. Kept as a Pydantic model for type clarity and documentation;
    not passed as response_json_schema to any Gemini call.
    """
    notes: str
    # remove_words is built mechanically by compute_mechanical_cuts() —
    # each entry is one of {word_index, reason} or
    # {after_word_index, before_word_index, reason}.
    remove_words: List[dict]
    pacing: Literal["fast", "medium", "slow"]
    video_identity: str
    caption_style: _CAPTION_STYLES
    caption_keywords: List[str]
    emphasis_moments: List[_EmphasisMoment]
    transitions: List[_Transition]
    sound_effects: List[_SoundEffect]
    motion_graphics: List[_MotionGraphic]
    text_overlays: List[_TextOverlay]
    broll_clips: List[_BrollClip]
    caption_position_changes: List[_CaptionPositionChange]
    thumbnail_word_index: int
    audio_denoise: bool
    outro: Literal["none", "fade_black", "fade_white"]
    aspect_ratio: Literal["9:16"]


# ── Cut detection + placement architecture ──────────────────────────────
# Step 1 (mechanical, in-process): compute_mechanical_cuts() runs four
# deterministic detectors (dead_air / filler / false_start / stutter) on
# the Deepgram word list. No Gemini, no prompt. Same input → same cuts.
#
# Python then re-indexes the transcript: only kept words survive, freshly
# numbered [0..M-1]. new_idx → src_idx map kept for translation.
#
# Step 2 (PostCutPlan Gemini call, HIGH thinking): main edit prompt run
# on the kept-only transcript. Anchor word_indices come from the new
# index space — physically cannot reference a cut word because cut words
# don't exist in this space.
#
# After Step 2 returns, Python translates every word_index field from new
# indices back to source indices, then merges the mechanical cuts result
# with the PostCutPlan output into EditPlan and continues downstream.


print(f"[startup] Python {sys.version}", flush=True)
print(f"[startup] handler version: {HANDLER_VERSION}", flush=True)
print(f"[startup] Gemini models: editorial={GEMINI_EDITORIAL_MODEL} utility={GEMINI_MODEL}", flush=True)
print(f"[startup] render version: {RENDER_VERSION}", flush=True)

try:
    from google import genai as genai_client_mod
    from google.genai import types as genai_types
    _genai_client = None  # lazily initialized with API key
    print("[startup] google-genai SDK OK", flush=True)
except Exception as e:
    print(f"[startup] google-genai SDK FAILED: {e}", flush=True)
    genai_client_mod = None
    genai_types = None


def _log_available_gemini_models():
    """One-time startup diagnostic: list gemini-3.x models this API key
    can call. Printed under `[startup]` so it shows in every container
    init log — when a model 404s, the next render's startup log shows
    exactly what IDs are available without needing another roundtrip.
    Failures are swallowed (this is observability, never blocks)."""
    if genai_client_mod is None:
        return
    _api_key = os.environ.get("GEMINI_API_KEY")
    if not _api_key:
        print("[startup] GEMINI_API_KEY not set — skipping ListModels", flush=True)
        return
    try:
        _probe_client = genai_client_mod.Client(api_key=_api_key)
        _names = []
        for _m in _probe_client.models.list():
            _nm = str(getattr(_m, "name", "") or "")
            if "gemini-3" in _nm:
                _methods = list(getattr(_m, "supported_generation_methods", []) or [])
                _names.append(f"{_nm} {_methods}" if _methods else _nm)
        if _names:
            print(
                "[startup] available gemini-3.x models: "
                + ", ".join(_names),
                flush=True,
            )
        else:
            print(
                "[startup] WARNING: ListModels returned NO gemini-3.x models "
                "for this API key — the key may lack access to Gemini 3.x",
                flush=True,
            )
    except Exception as _le:
        print(f"[startup] ListModels failed (non-blocking): {_le}", flush=True)


_log_available_gemini_models()

def _get_genai_client():
    """Get or create the Gemini API client (lazy init with API key from env).

    HttpOptions.timeout (milliseconds) drives BOTH the local httpx read
    timeout AND a server-side X-Server-Timeout header that the genai SDK
    sends to Google. Google honors the header — if the model's wall-clock
    exceeds it, Google returns 504 DEADLINE_EXCEEDED.

    Sized for the post-cuts call's structural wall-clock at thinking_budget=
    60000: ~135s baseline at thinking_budget=24576 scales roughly linearly,
    so ~337s worst-case at 60K. Original 120_000ms (2 min) clipped reliably;
    300_000ms (5 min) clipped on complex prompts (job 2026-06-21 hit 316s
    execution before 504 at the 300s mark). Raised to 480_000ms (8 min) for
    comfortable headroom on every prompt thinking_budget=60K can consume,
    while keeping room under Modal's function timeout (modal_app.py:468 =
    900s = 15 min after this fix) for the non-Gemini pipeline work
    (download / fps-normalize / render / composite / upload).
    """
    global _genai_client
    if _genai_client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _genai_client = genai_client_mod.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=480_000),
        )
    return _genai_client

supabase = None
try:
    from supabase import create_client
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
        print("[startup] supabase OK", flush=True)
    else:
        print("[startup] supabase unavailable: missing env", flush=True)
except Exception as e:
    print(f"[startup] supabase unavailable: {e}", flush=True)

# ── S3-compatible Supabase Storage client ────────────────────────────────
# Uses Supabase's S3 protocol for same-region transfers over AWS internal
# network (via Modal's S3 gateway endpoints). Falls back to HTTP if S3
# credentials are not configured.
_s3_client = None
_s3_project_ref = None
_aws_s3_client = None
try:
    import boto3
    from botocore.config import Config as BotoConfig

    # ── Supabase S3-compatible storage (legacy) ──────────────────────────
    _s3_access_key = os.environ.get("SUPABASE_S3_ACCESS_KEY")
    _s3_secret_key = os.environ.get("SUPABASE_S3_SECRET_KEY")
    _s3_region = os.environ.get("SUPABASE_S3_REGION", "us-west-1")
    _supabase_url_raw = os.environ.get("SUPABASE_URL", "")
    import re as _re_s3
    _ref_match = _re_s3.match(r"https://([^.]+)\.supabase\.co", _supabase_url_raw)
    if _ref_match:
        _s3_project_ref = _ref_match.group(1)
    if _s3_access_key and _s3_secret_key and _s3_project_ref:
        _s3_endpoint = f"https://{_s3_project_ref}.storage.supabase.co/storage/v1/s3"
        _s3_client = boto3.client(
            "s3",
            endpoint_url=_s3_endpoint,
            region_name=_s3_region,
            aws_access_key_id=_s3_access_key,
            aws_secret_access_key=_s3_secret_key,
            config=BotoConfig(s3={"addressing_style": "path"}),
        )
        print(f"[startup] S3 storage OK (endpoint={_s3_endpoint}, region={_s3_region})", flush=True)
    else:
        _missing = []
        if not _s3_access_key: _missing.append("SUPABASE_S3_ACCESS_KEY")
        if not _s3_secret_key: _missing.append("SUPABASE_S3_SECRET_KEY")
        if not _s3_project_ref: _missing.append("SUPABASE_URL (invalid format)")
        print(f"[startup] S3 storage unavailable: missing {', '.join(_missing)} — will use HTTP", flush=True)

    # ── AWS S3 storage (primary) ─────────────────────────────────────────
    # Uses standard AWS env vars (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).
    # boto3 picks these up automatically — no explicit credential passing.
    _aws_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-west-1")
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        _aws_s3_client = boto3.client("s3", region_name=_aws_region)
        print(f"[startup] AWS S3 OK (region={_aws_region})", flush=True)
    else:
        print("[startup] AWS S3 unavailable: missing AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY", flush=True)

    # ── Tuned TransferConfig for S3 large-file downloads ─────────────────
    # boto3[crt] is installed, so the AWS CRT client automatically accelerates
    # multipart downloads. On top of CRT, we bump chunk size 8MB → 16MB and
    # parallelism 10 → 32 to saturate the H100 container's network pipe for
    # 40-80MB media files. Measured: ~2-3× faster on same-region reads,
    # ~3-5× on cross-region (masks some of the cross-region penalty).
    from boto3.s3.transfer import TransferConfig as _BotoTransferConfig
    _S3_TRANSFER_CONFIG = _BotoTransferConfig(
        multipart_threshold=8 * 1024 * 1024,
        multipart_chunksize=8 * 1024 * 1024,
        max_concurrency=100,
        use_threads=True,
    )
except ImportError:
    print("[startup] S3 storage unavailable: boto3 not installed — will use HTTP", flush=True)
except Exception as e:
    print(f"[startup] S3 storage init failed: {e} — will use HTTP", flush=True)


def _parse_supabase_storage_url(url):
    """Extract (bucket, key) from a Supabase storage URL.
    Handles all known Supabase storage URL formats:
      https://XXXX.supabase.co/storage/v1/object/public/BUCKET/KEY
      https://XXXX.supabase.co/storage/v1/object/sign/BUCKET/KEY?token=...
      https://XXXX.supabase.co/storage/v1/object/authenticated/BUCKET/KEY
      https://XXXX.supabase.co/storage/v1/upload/resumable/BUCKET/KEY?token=...
      https://XXXX.supabase.co/object/upload/sign/BUCKET/KEY?token=...
      https://XXXX.supabase.co/storage/v1/object/upload/sign/BUCKET/KEY?token=...
    Returns (bucket, key) or (None, None) if not a recognized Supabase storage URL.
    """
    import re as _re_parse
    # Try all known path patterns. The /storage/v1/ prefix may or may not be present.
    patterns = [
        r"/storage/v1/object/(?:public|sign|authenticated)/([^/]+)/(.+?)(?:\?|$)",
        r"/storage/v1/(?:object/)?upload/(?:sign|resumable)/([^/]+)/(.+?)(?:\?|$)",
        r"/object/upload/sign/([^/]+)/(.+?)(?:\?|$)",
        r"/object/(?:public|sign|authenticated)/([^/]+)/(.+?)(?:\?|$)",
    ]
    for pat in patterns:
        m = _re_parse.search(pat, url)
        if m:
            return m.group(1), m.group(2)
    return None, None


def _parse_aws_s3_url(url):
    """Extract (bucket, key) from an AWS S3 URL.
    Handles:
      https://BUCKET.s3.REGION.amazonaws.com/KEY
      https://BUCKET.s3.amazonaws.com/KEY
      https://s3.REGION.amazonaws.com/BUCKET/KEY
      https://CLOUDFRONT_DOMAIN/KEY (uses SUPABASE_S3_BUCKET env var)
    Returns (bucket, key) or (None, None) if not a recognized AWS S3 URL.
    """
    import re as _re_aws
    # Virtual-hosted style: https://BUCKET.s3.REGION.amazonaws.com/KEY
    m = _re_aws.match(r"https://([^.]+)\.s3[.\w-]*\.amazonaws\.com/(.+?)(?:\?|$)", url)
    if m:
        return m.group(1), m.group(2)
    # Path style: https://s3.REGION.amazonaws.com/BUCKET/KEY
    m = _re_aws.match(r"https://s3[.\w-]*\.amazonaws\.com/([^/]+)/(.+?)(?:\?|$)", url)
    if m:
        return m.group(1), m.group(2)
    # CloudFront style: https://DOMAIN.cloudfront.net/KEY — extract key, use bucket from env
    m = _re_aws.match(r"https://[^/]+\.cloudfront\.net/(.+?)(?:\?|$)", url)
    if m:
        bucket = os.environ.get("S3_BUCKET_NAME") or os.environ.get("SUPABASE_S3_BUCKET") or "promptly-video-storage"
        return bucket, m.group(1)
    return None, None

DeepgramClient = None
PrerecordedOptions = None
try:
    from deepgram import DeepgramClient, PrerecordedOptions
    print("[startup] deepgram OK", flush=True)
except ImportError:
    try:
        from deepgram.clients.prerecorded import PrerecordedOptions
        from deepgram import DeepgramClient
        print("[startup] deepgram OK (alt import)", flush=True)
    except ImportError as e:
        print(f"[startup] deepgram FAILED: {e}", flush=True)

try:
    rb_check = subprocess.run(["rubberband", "--version"], capture_output=True, text=True, timeout=5)
    rb_version = (rb_check.stdout or rb_check.stderr or "").strip().splitlines()
    print(f"[startup] rubberband OK: {rb_version[0] if rb_version else 'available'}", flush=True)
except Exception:
    print("[startup] WARNING: rubberband not found — speed curve will use fallback audio", flush=True)

_HAS_FFMPEG_RUBBERBAND = False
try:
    # Log which ffmpeg binary we're actually using
    _which_ff = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True, timeout=5)
    _ff_path = (_which_ff.stdout or "").strip()
    _ff_ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
    _ff_ver_line = (_ff_ver.stdout or "").split("\n")[0] if _ff_ver.stdout else "unknown"
    print(f"[startup] FFmpeg binary: {_ff_path} ({_ff_ver_line})", flush=True)

    ff_check = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True, timeout=5)
    _ff_filters = ff_check.stdout or ""
    if "rubberband" in _ff_filters:
        _HAS_FFMPEG_RUBBERBAND = True
        print("[startup] FFmpeg rubberband filter: available", flush=True)
    else:
        print("[startup] WARNING: FFmpeg rubberband filter not available", flush=True)
        # Print FFmpeg configuration for debugging
        _config_line = [l for l in (_ff_ver.stdout or "").split("\n") if "configuration:" in l]
        if _config_line:
            print(f"[startup] FFmpeg config: {_config_line[0][:300]}", flush=True)
except Exception:
    pass

# Real-ESRGAN removed from pipeline — not needed for clean phone footage

print("[startup] all import checks done", flush=True)

# ── GPU flags ─────────────────────────────────────────────────────────────────
# Orchestrator runs CPU-only — the H100 moved to the dedicated
# rife_normalize_remote function. NVENC and CUDA hwaccel decode
# accordingly stay False on this container; the few code paths that
# branch on these flags fall back to software decode/encode automatically.
# The libcuda symlink + LD_LIBRARY_PATH fix that used to live here moved
# to cuda_driver_setup.py and runs at the top of rife_normalize_remote.
_HAS_NVENC = False
_HAS_HWACCEL = False


# Vulkan / NVIDIA-Chromium GPU rasterization is intentionally NOT pursued.
# Past attempts (v54-v57 + this session) reached "OS-level setup looks
# right" but never produced a verified end-to-end frame through Chromium
# on chrome-headless-shell with NVIDIA Vulkan. The diagnostic + ICD
# synthesis code that used to live here added complexity in service of
# an unproven path with a catastrophic failure mode (Vulkan crash inside
# the headless browser kills the Remotion process; we have no fallback
# and the user explicitly disallows them).
#
# The production-supported rasterizer is swangle (Skia software path).
# Same code path every render, deterministic output, no driver-mount
# dependencies, no version compatibility issues. Performance baseline
# is set by the chunked overlay + chunked composite architecture —
# Vulkan was supposed to help on top of that, not be load-bearing.


def get_encode_args(quality="high", threads=0):
    """Return encoder args for FFmpeg. Uses NVENC when GPU is available.

    quality="high"     → final output (CQ 18 — maximum quality for social media)
    quality="lossless" → intermediate files (lossless preset)
    """
    if _HAS_NVENC:
        if quality == "lossless":
            return ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "lossless"]
        else:
            # p4 = high quality NVENC preset. H100 NVENC is so fast that p4 adds
            # negligible time vs p1 but produces significantly better quality.
            # CQ 18 = visually lossless on mobile. 12M maxrate / 24M bufsize
            # is YouTube's 1080p60 reference rate — the floor where 1080p60
            # talking-head content stops showing visible macroblocks.
            # Streams smoothly through CloudFront on any home wifi.
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq",
                    "-rc", "vbr", "-cq", "18", "-b:v", "0",
                    "-maxrate", "12M", "-bufsize", "24M",
                    "-spatial-aq", "1", "-temporal-aq", "1",
                    "-b_ref_mode", "middle"]
    else:
        # CPU encoding (H100 has no NVENC). `medium` preset (was `veryfast`)
        # for proper rate-distortion optimization — full motion estimation,
        # no early-termination shortcuts. ~2-3× slower per frame, but
        # parallel chunked rendering keeps wall-clock impact small. The
        # quality jump at 12M is significant: 0.10 bpp (visible-blocking
        # threshold disappears) vs 0.064 bpp at 8M+veryfast.
        # `lossless` intermediates stay on `ultrafast` since the quality
        # ceiling is already perfect (no loss) and the speed matters for
        # parallel render time.
        _x264_threads = f"threads={threads}"
        if quality == "lossless":
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                    "-fps_mode", "passthrough",
                    "-x264-params", _x264_threads]
        else:
            return ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-maxrate", "12M", "-bufsize", "24M",
                    "-fps_mode", "passthrough",
                    "-x264-params", _x264_threads]

# Module-level: tracks active Remotion chunk subprocesses for cleanup on timeout
_overlay_chunk_procs = []

_EMOJI_RE = re.compile(
    "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
    "\U0001f926-\U0001f937\U00010000-\U0010ffff"
    "\u2640-\u2642\u2600-\u2B55\u200d\u23cf\u23e9\u231a\ufe0f\u3030]+",
    flags=re.UNICODE,
)
def get_trend_context():
    """Load the current weekly editing style guide from Supabase."""
    if supabase is None:
        print("[trend] No valid trend profile found", flush=True)
        return None
    try:
        result = supabase.table("trend_profiles") \
            .select("profile_json, sample_size") \
            .gt("valid_until", datetime.utcnow().isoformat()) \
            .order("valid_until", desc=True) \
            .limit(1) \
            .execute()

        if result.data and len(result.data) > 0:
            profile = result.data[0]["profile_json"]
            sample_size = result.data[0].get("sample_size", 0)

            if isinstance(profile, dict) and profile.get("type") == "style_guide":
                style_guide = profile.get("style_guide", "")
                print(f"[trend] Loaded editing style guide: {sample_size} videos, {len(style_guide)} chars", flush=True)
                return {"type": "style_guide", "style_guide": style_guide, "sample_size": sample_size}
            else:
                print(f"[trend] Loaded trend profile (legacy stats): {sample_size} videos", flush=True)
                return profile
        else:
            print("[trend] No valid trend profile found", flush=True)
            return None
    except Exception as e:
        print(f"[trend] Error loading trend context: {e}", flush=True)
        return None


def format_trend_section(trend_context):
    """Format the trend context for injection into the Gemini prompt."""
    if not trend_context:
        return ""

    try:
        if isinstance(trend_context, dict) and trend_context.get("type") == "style_guide":
            style_guide = trend_context.get("style_guide", "")
            sample_size = trend_context.get("sample_size", 0)
            if not style_guide:
                return ""

            return f"""

=== WHAT'S WORKING ON TIKTOK RIGHT NOW ===

The following editing style guide was generated by watching {sample_size} of the highest-performing TikTok videos from this week — videos with 500K+ views that the algorithm is actively distributing. These are real patterns from real viral content, not theory.

Follow these patterns for pacing and cuts only.

{style_guide}"""

        elif isinstance(trend_context, dict) and "numeric_patterns" in trend_context:
            sample_size = trend_context.get("sample_size", 0)
            return f"\n\n(Legacy trend data from {sample_size} videos available but in old format)\n"

        else:
            return ""

    except Exception as e:
        print(f"[trend] Error formatting trend section: {e}", flush=True)
        return ""


# ── Per-user style learning ──────────────────────────────────────────────────
# Supabase table `user_style_profiles` persists rolling-window frequency
# counters of the choices Gemini has made for each user across their past
# videos. The profile is fetched before every Gemini call and rendered as a
# prompt section so Gemini leans toward what the user has accepted in the
# past. After every successful render the profile is upserted with the
# freshly-chosen values — recent videos outweigh old ones because the update
# decays old counts slightly.
#
# Schema (all JSONB unless noted):
#   user_id                text PRIMARY KEY
#   caption_styles         {style_name: count}
#   transitions            {transition_type: count}
#   pacings                {"fast"|"medium"|"slow": count}
#   color_effects          {type_or_"null": count}
#   text_overlay_variants  {variant: count}
#   motion_graphics        {mg_type: count}
#   zoom_types             {zoom_type: count}
#   recent_vibes           list of strings (tail-capped to 20)
#   recent_caption_styles  list of strings (tail-capped to 5; chronological,
#                          newest LAST) — separate from `caption_styles` counts
#                          because the system prompt's rotation rule needs the
#                          chronological order, not the aggregate count.
#   avg_emphasis_per_30s   real
#   avg_mgs_per_video      real
#   total_videos           int
#   updated_at             timestamptz

_USER_STYLE_RECENCY_DECAY = 0.92  # each update scales old counts by this
_USER_STYLE_MIN_VIDEOS    = 3     # profile only rendered into prompt if ≥ this


def fetch_user_style_profile(user_id):
    """Load a user's accumulated style profile. Returns dict or None if missing."""
    if supabase is None or not user_id:
        return None
    try:
        result = supabase.table("user_style_profiles") \
            .select("*") \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        if result.data and len(result.data) > 0:
            row = result.data[0]
            print(
                f"[user-style] Loaded profile for user={user_id[:8]}… "
                f"(total_videos={row.get('total_videos', 0)})",
                flush=True,
            )
            return row
        print(f"[user-style] No profile row for user={user_id[:8]}… (cold start)", flush=True)
        return None
    except Exception as e:
        print(f"[user-style] Fetch failed: {e}", flush=True)
        return None


# ─── User tier + multi-clip concurrency gate ─────────────────────────────────
#
# Backend defense-in-depth for the premium multi-clip feature. The frontend
# is the primary gate (it refuses to let non-premium users select more than
# one file at the picker). This worker-side check is the secondary gate:
# if a non-premium user calls the API directly (curl, leaked token, broken
# client build), the second concurrent job for the same user_id gets
# rejected here with a clear upgrade message instead of running silently.
#
# Schema flexibility — the Supabase row holding the tier signal is read via
# env vars so the contract can match the frontend's existing table:
#   PROMPTLY_TIER_TABLE       (default: "user_profiles")
#   PROMPTLY_TIER_USER_COLUMN (default: "user_id")  — column joining on user_id
#   PROMPTLY_TIER_COLUMN      (default: "tier")     — column holding the tier value
#   PROMPTLY_PREMIUM_VALUES   (default: "premium,pro,paid,plus")
#                                                    — comma-separated values
#                                                      that count as premium
#
# In-flight job count — read from the existing jobs table the worker already
# writes progress to. Free tier == 1 concurrent job; premium == no worker-side
# limit (Modal's natural concurrency handles capacity). The table/column for
# this is also env-driven so we don't break if your existing job-status
# schema doesn't match a guessed default:
#   PROMPTLY_JOB_TABLE        (default: "jobs")
#   PROMPTLY_JOB_USER_COLUMN  (default: "user_id")
#   PROMPTLY_JOB_STATUS_COLUMN (default: "status")
#   PROMPTLY_JOB_ACTIVE_STATUSES (default: "queued,running,processing")
#                                                    — comma-separated statuses
#                                                      that count as "in flight"

def _premium_values():
    raw = os.environ.get("PROMPTLY_PREMIUM_VALUES") or "premium,pro,paid,plus"
    return {v.strip().lower() for v in raw.split(",") if v.strip()}


def _active_statuses():
    raw = os.environ.get("PROMPTLY_JOB_ACTIVE_STATUSES") or "queued,running,processing"
    return {v.strip().lower() for v in raw.split(",") if v.strip()}


def fetch_user_tier(user_id):
    """Look up a user's tier from Supabase. Returns the raw tier string
    (lowercased) or None if Supabase is unreachable / row missing.

    Fail-OPEN: if the lookup fails for any reason (Supabase down, schema
    mismatch, env vars wrong), we return None. The caller treats None as
    "tier unknown — apply the most permissive policy that doesn't burn
    the company" (currently: allow the job, log loudly). This avoids the
    failure mode where a Supabase blip blocks paying users from rendering.
    """
    if supabase is None or not user_id:
        return None
    table = os.environ.get("PROMPTLY_TIER_TABLE") or "user_profiles"
    user_col = os.environ.get("PROMPTLY_TIER_USER_COLUMN") or "user_id"
    tier_col = os.environ.get("PROMPTLY_TIER_COLUMN") or "tier"
    try:
        result = supabase.table(table) \
            .select(tier_col) \
            .eq(user_col, user_id) \
            .limit(1) \
            .execute()
        if result.data and len(result.data) > 0:
            raw = result.data[0].get(tier_col)
            tier = str(raw).strip().lower() if raw else None
            print(
                f"[tier] user={user_id[:8]}… tier={tier or '(none)'}",
                flush=True,
            )
            return tier
        print(
            f"[tier] No row for user={user_id[:8]}… in {table}.{user_col} — "
            f"treating as tier-unknown (fail open).",
            flush=True,
        )
        return None
    except Exception as e:
        print(f"[tier] Fetch failed for user={user_id[:8]}…: {e} (fail open)", flush=True)
        return None


def count_user_active_jobs(user_id, current_job_id):
    """Count this user's active (queued/running/processing) jobs in the jobs
    table, EXCLUDING the current job_id (we don't want to count ourselves).

    Returns 0 if Supabase is unreachable / table missing — same fail-OPEN
    discipline as fetch_user_tier. The caller treats 0 as "unknown — allow."
    """
    if supabase is None or not user_id:
        return 0
    table = os.environ.get("PROMPTLY_JOB_TABLE") or "jobs"
    user_col = os.environ.get("PROMPTLY_JOB_USER_COLUMN") or "user_id"
    status_col = os.environ.get("PROMPTLY_JOB_STATUS_COLUMN") or "status"
    try:
        # Pull only the status + id columns — we filter in Python after the
        # fetch since the Supabase Python SDK's .in_() helper has been
        # inconsistent across versions.
        result = supabase.table(table) \
            .select(f"id,{status_col}") \
            .eq(user_col, user_id) \
            .execute()
        active = _active_statuses()
        count = 0
        for row in (result.data or []):
            if str(row.get("id") or "") == str(current_job_id):
                continue  # don't count ourselves
            if str(row.get(status_col) or "").strip().lower() in active:
                count += 1
        return count
    except Exception as e:
        print(
            f"[tier] Active-job count failed for user={user_id[:8]}…: {e} (fail open)",
            flush=True,
        )
        return 0


def check_concurrency_gate(user_id, job_id):
    """Apply the free-tier-single-job concurrency rule.

    Returns:
        None if the job should proceed.
        A dict {"error": ..., "user_message": ..., "tier": ...} if the job
        should be rejected with a tier-upgrade message.

    Always FAIL OPEN on Supabase trouble — a paying user must never be
    blocked from rendering by a transient infra blip. The fail-closed case
    is reserved for the explicit "you're free tier with a job already
    running" path.
    """
    tier = fetch_user_tier(user_id)
    premium = tier in _premium_values() if tier else False
    if premium:
        return None  # premium has no worker-side concurrency cap
    # Tier unknown or non-premium — count active jobs.
    active_count = count_user_active_jobs(user_id, job_id)
    if active_count <= 0:
        return None  # zero or unknown — allow
    # Non-premium with an in-flight job — reject this one.
    return {
        "error": "tier_concurrency_limit",
        "user_message": (
            "Your current plan renders one video at a time. Wait for your "
            "in-progress render to finish, or upgrade to render multiple "
            "videos simultaneously."
        ),
        "tier": tier or "unknown",
        "active_jobs": active_count,
    }


def format_user_style_section(profile):
    """Render a prompt section from a fetched profile. Empty string if too thin."""
    if not isinstance(profile, dict):
        return ""
    _total = int(profile.get("total_videos") or 0)
    if _total < _USER_STYLE_MIN_VIDEOS:
        return ""

    def _top_counts(field, n=3):
        d = profile.get(field) or {}
        if not isinstance(d, dict) or not d:
            return []
        # Skip sentinel sub-keys (double-underscore framed) — those carry
        # piggyback data (e.g. _RECENT_CAPTION_STYLES_SENTINEL holds a list,
        # not a count). Also skip non-numeric values defensively.
        _items = [
            (k, v) for k, v in d.items()
            if not (isinstance(k, str) and k.startswith("__") and k.endswith("__"))
            and isinstance(v, (int, float))
        ]
        _items = sorted(_items, key=lambda kv: (-float(kv[1] or 0), str(kv[0])))
        return [(k, float(v or 0)) for k, v in _items[:n]]

    def _fmt_top(items):
        if not items:
            return "(no data)"
        return ", ".join(f"{k} ({v:.1f})" for k, v in items)

    _caps = _fmt_top(_top_counts("caption_styles", 3))
    _trans = _fmt_top(_top_counts("transitions", 3))
    _pacing = _fmt_top(_top_counts("pacings", 3))
    _color = _fmt_top(_top_counts("color_effects", 3))
    _tov = _fmt_top(_top_counts("text_overlay_variants", 3))
    _mgs = _fmt_top(_top_counts("motion_graphics", 3))
    _zooms = _fmt_top(_top_counts("zoom_types", 3))
    _avg_em = float(profile.get("avg_emphasis_per_30s") or 0)
    _avg_mg = float(profile.get("avg_mgs_per_video") or 0)
    _recent_vibes = profile.get("recent_vibes") or []
    _rv_tail = ", ".join(f'"{v}"' for v in _recent_vibes[-5:]) if _recent_vibes else "(none)"

    return f"""

=== THIS USER'S PREFERRED STYLE (learned from their past {_total} videos) ===

These are the aesthetic CATEGORIES this user has accepted over time —
which caption style they tend toward, which transition types, which zoom
personalities. Recency-weighted counts — higher numbers = more frequent
/ more recent picks. Use these as TASTE signals about WHICH types to
reach for, NOT as quantity targets.

  Caption styles:         {_caps}
  Transitions:            {_trans}
  Pacing:                 {_pacing}
  Color effects:          {_color}
  Text overlay variants:  {_tov}
  Motion graphics:        {_mgs}
  Zoom types:             {_zooms}
  Recent vibe prompts:    {_rv_tail}

GUIDANCE — important:
- Use this profile as a LIGHT signal about general taste, NOT a "pick the same thing again" instruction.
- For caption_style specifically: AVOID picking whichever style ranks #1 in their history if it appeared in either of their last 2 videos. Variety is itself a quality signal — top creators rotate caption styles across videos to keep their feed visually fresh. Pick a different style that still matches the vibe.
- For transition types, zoom types: gentle bias toward their top picks is fine; people develop a consistent overall feel for the LOOK of their edits.
- DO NOT use this profile to infer how MANY components to place. Carrier-layer density (B-roll on every named noun, an SFX on every visual event, transitions at CUT BOUNDARIES that earn them, MGs on off-camera referents, captions running continuously) comes from the prompt above. Emphasis_moments are placed only where the dialogue earns them — there's no count to chase. The user's historical counts predate the current rules and would bias placement away from intent.
- If the current vibe EXPLICITLY contradicts (e.g. "completely different look"), ignore history entirely.
"""


# Sentinel sub-key used to piggyback the chronological recent-caption-styles
# list inside the existing `caption_styles` JSONB column on Supabase, since
# adding a top-level `recent_caption_styles` column requires a SQL migration
# and PostgREST otherwise rejects unknown columns. JSONB is schemaless, so
# a sub-key sidesteps the migration. Reads in `format_user_style_section`
# and `_decayed` skip this key by name.
_RECENT_CAPTION_STYLES_SENTINEL = "__chronological__"


def _read_recent_caption_styles(profile):
    """Read the chronological recent-caption-styles list from the profile.

    Looks in two places in order: the dedicated `recent_caption_styles`
    column (if a future SQL migration adds it), then the sentinel sub-key
    inside `caption_styles` JSONB. Returns [] when nothing usable exists.
    """
    if not isinstance(profile, dict):
        return []
    # Dedicated column — preferred when present (post-migration).
    direct = profile.get("recent_caption_styles")
    if isinstance(direct, list) and direct:
        return list(direct)
    # Piggyback sentinel inside the existing JSONB column.
    cs = profile.get("caption_styles")
    if isinstance(cs, dict):
        piggyback = cs.get(_RECENT_CAPTION_STYLES_SENTINEL)
        if isinstance(piggyback, list) and piggyback:
            return list(piggyback)
    return []


def format_recent_caption_styles_section(profile):
    """Render the chronological recent-caption-styles list as its own user
    message block.

    Shown whenever the list is non-empty — independent of the
    `_USER_STYLE_MIN_VIDEOS` gate that hides `format_user_style_section`,
    because rotation is meaningful even at video #2 (one prior pick → one
    style to avoid). The system prompt's CAPTIONS rotation rule
    (handler.py:~2810) asks for chronological "last N videos" data; the
    aggregate counts in `format_user_style_section` conflate "used
    recently" with "used a lot." This block is the data shape the rule
    was always asking for.

    Returns the formatted block string, or "" when the profile carries no
    usable list (the no-op default test exists to keep this from leaking
    junk into the user message on cold-start users).
    """
    if not isinstance(profile, dict):
        return ""
    recent = _read_recent_caption_styles(profile)
    if not isinstance(recent, list) or not recent:
        return ""
    cleaned = [str(s) for s in recent if s and str(s) != "none"][-5:]
    if not cleaned:
        return ""
    _joined = ", ".join(cleaned)
    return f"""

=== RECENT CAPTION STYLES (chronological — last {len(cleaned)} videos, newest LAST) ===

The user's caption_style picks across their last {len(cleaned)} renders, in render order: {_joined}

Per the CAPTIONS rotation rule, prefer a style NOT in this list. Repeating the same caption style across consecutive videos reads as template; rotating across the 13 styles is how a creator's feed feels deliberate. The current vibe wins over this rotation — if the vibe asks for a specific style by name, use it. If the vibe is silent on style, pick a style outside this list that best fits the video's character.
"""


def update_user_style_profile(user_id, edit_plan, vibe, duration):
    """Upsert the user's style profile with the choices from this successful render.

    Recency weighting: existing counts are decayed by _USER_STYLE_RECENCY_DECAY
    before adding 1.0 for the current video's choices. Old signal fades,
    recent signal dominates.
    """
    if supabase is None or not user_id or not isinstance(edit_plan, dict):
        return
    try:
        prior = fetch_user_style_profile(user_id) or {}

        def _decayed(field):
            d = prior.get(field) or {}
            if not isinstance(d, dict):
                d = {}
            # Skip sentinel sub-keys (e.g. _RECENT_CAPTION_STYLES_SENTINEL
            # piggybacked inside caption_styles JSONB). Their values are
            # lists / non-numerics; float(v) would crash _decayed and break
            # the whole upsert. Style-count keys are normal strings without
            # the double-underscore prefix.
            return {
                k: round(float(v or 0) * _USER_STYLE_RECENCY_DECAY, 3)
                for k, v in d.items()
                if not (isinstance(k, str) and k.startswith("__") and k.endswith("__"))
                and isinstance(v, (int, float))
            }

        def _bump(bucket, key):
            if not key:
                return
            key = str(key)
            bucket[key] = round(float(bucket.get(key) or 0) + 1.0, 3)

        _caption_styles = _decayed("caption_styles")
        _bump(_caption_styles, edit_plan.get("caption_style"))

        _transitions = _decayed("transitions")
        for _tr in (edit_plan.get("transitions") or []):
            if isinstance(_tr, dict):
                _bump(_transitions, _tr.get("type"))

        _pacings = _decayed("pacings")
        _bump(_pacings, edit_plan.get("pacing"))

        # color_effects: feature removed (talking-head pipeline doesn't need
        # cinematic grades). Preserve the existing column for any historical
        # rows but stop bumping; the field decays to zero over time.
        _color_effects = _decayed("color_effects")

        _tov_freq = _decayed("text_overlay_variants")
        for _tov in (edit_plan.get("text_overlays") or []):
            if isinstance(_tov, dict):
                _bump(_tov_freq, _tov.get("variant"))

        _mg_freq = _decayed("motion_graphics")
        for _mg in (edit_plan.get("motion_graphics") or []):
            if isinstance(_mg, dict):
                _bump(_mg_freq, _mg.get("type"))
        for _em in (edit_plan.get("_emphasis_moments") or edit_plan.get("emphasis_moments") or []):
            if isinstance(_em, dict):
                _em_mg = _em.get("motion_graphic")
                if isinstance(_em_mg, dict):
                    _bump(_mg_freq, _em_mg.get("type"))

        _zoom_freq = _decayed("zoom_types")
        for _em in (edit_plan.get("_emphasis_moments") or edit_plan.get("emphasis_moments") or []):
            if isinstance(_em, dict):
                _zf = _em.get("zoom_effect")
                if isinstance(_zf, dict):
                    _bump(_zoom_freq, _zf.get("type"))

        # Emphasis density per 30s and MG count are rolling averages (EMA).
        _prior_total = int(prior.get("total_videos") or 0)
        _prior_em = float(prior.get("avg_emphasis_per_30s") or 0)
        _prior_mg = float(prior.get("avg_mgs_per_video") or 0)
        _em_count = len(edit_plan.get("_emphasis_moments") or edit_plan.get("emphasis_moments") or [])
        _mg_count = (
            len(edit_plan.get("motion_graphics") or [])
            + sum(
                1 for _em in (edit_plan.get("_emphasis_moments") or edit_plan.get("emphasis_moments") or [])
                if isinstance(_em, dict) and _em.get("motion_graphic")
            )
        )
        _em_per_30s_this = (_em_count / (max(1.0, float(duration)) / 30.0))
        # EMA with alpha=0.3 so a handful of recent videos dominate quickly
        _alpha = 0.3 if _prior_total > 0 else 1.0
        _new_em_avg = _alpha * _em_per_30s_this + (1 - _alpha) * _prior_em
        _new_mg_avg = _alpha * float(_mg_count) + (1 - _alpha) * _prior_mg

        _recent_vibes = list(prior.get("recent_vibes") or [])
        if vibe:
            _recent_vibes.append(str(vibe))
        _recent_vibes = _recent_vibes[-20:]

        # Chronological caption-style picks (tail-capped, newest LAST).
        # The aggregate `caption_styles` counts above can't distinguish
        # "used Lumen 5 times across last 30 videos" from "used Lumen in
        # each of the last 3 videos" — both produce a similar recency-
        # weighted count, but only the second is what the system prompt's
        # CAPTIONS rotation rule cares about. This chronological list is
        # the data shape that rule was always asking for. Tail-capped at
        # 5 (≈ enough rotation history that #1 vs #4 is meaningful, not
        # so deep that ancient picks influence the avoid list).
        #
        # Storage: PIGGYBACK as a sentinel sub-key inside the existing
        # `caption_styles` JSONB column. Adding a dedicated
        # `recent_caption_styles` top-level column would require a
        # Supabase SQL migration (PostgREST rejects upserts containing
        # unknown columns and silently truncates the payload). JSONB
        # columns are schemaless by design, so a sub-key works without
        # external action. `_read_recent_caption_styles` reads either
        # the sentinel sub-key OR a dedicated column if one is later
        # added — both paths work, no migration required.
        _prior_recent_chronological = _read_recent_caption_styles(prior)
        _recent_caption_styles = list(_prior_recent_chronological)
        _current_caption_style = edit_plan.get("caption_style")
        if _current_caption_style and str(_current_caption_style) != "none":
            _recent_caption_styles.append(str(_current_caption_style))
        _recent_caption_styles = _recent_caption_styles[-5:]
        if _recent_caption_styles:
            _caption_styles[_RECENT_CAPTION_STYLES_SENTINEL] = _recent_caption_styles

        _row = {
            "user_id": user_id,
            "caption_styles": _caption_styles,
            "transitions": _transitions,
            "pacings": _pacings,
            "color_effects": _color_effects,
            "text_overlay_variants": _tov_freq,
            "motion_graphics": _mg_freq,
            "zoom_types": _zoom_freq,
            "recent_vibes": _recent_vibes,
            "avg_emphasis_per_30s": round(_new_em_avg, 3),
            "avg_mgs_per_video": round(_new_mg_avg, 3),
            "total_videos": _prior_total + 1,
            "updated_at": datetime.utcnow().isoformat(),
        }
        supabase.table("user_style_profiles").upsert(_row, on_conflict="user_id").execute()
        print(
            f"[user-style] Updated profile for user={user_id[:8]}… "
            f"(total_videos={_row['total_videos']}, avg_em/30s={_new_em_avg:.2f}, "
            f"avg_mgs={_new_mg_avg:.2f})",
            flush=True,
        )
    except Exception as e:
        print(f"[user-style] Upsert failed: {e}", flush=True)


# Download arnndn noise-reduction model if not present (used by audio_denoise feature)
_RNNOISE_MODEL_PATH = "/usr/share/rnnoise/bd.rnnn"
SFX_SOUNDS_DIR    = os.path.join(os.path.dirname(__file__), "assets", "sounds")

# NOTE: caption / motion-graphic / transition fonts are registered system-wide
# at Modal image build time (see modal_app.py — the image build fails hard if
# any of the 15 required families aren't resolvable by fontconfig). The
# runtime `ensure_caption_fonts_registered()` helper was removed because its
# fallback path contradicted "fail hard at build time, no runtime recovery."
if not os.path.exists(_RNNOISE_MODEL_PATH):
    try:
        os.makedirs(os.path.dirname(_RNNOISE_MODEL_PATH), exist_ok=True)
        import urllib.request
        urllib.request.urlretrieve(
            "https://github.com/GregorR/rnnoise-models/raw/master/beguiling-drafter-2018-08-30/bd.rnnn",
            _RNNOISE_MODEL_PATH
        )
        print(f"[startup] arnndn model downloaded → {_RNNOISE_MODEL_PATH}", flush=True)
    except Exception as e:
        print(f"[startup] arnndn model download failed (audio_denoise will be skipped): {e}", flush=True)
else:
    print(f"[startup] arnndn model present: {_RNNOISE_MODEL_PATH}", flush=True)


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def detect_face_positions(video_path, sample_timestamps):
    """
    Sample frames at given timestamps and detect the dominant face position.
    Uses OpenCV's DNN-based face detector (ResNet SSD) which is far more
    reliable than Haar cascades — handles angled faces, glasses, hats,
    varying skin tones, and low light.
    Returns list of {"t", "cx", "cy", "found"} entries.
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("[reframe] Could not open video for face detection", flush=True)
        return []

    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    center_x = frame_w // 2 if frame_w > 0 else 540
    center_y = frame_h // 2 if frame_h > 0 else 960

    # Load DNN face detector (ResNet-10 SSD, trained on WIDER FACE dataset)
    PROTOTXT = "/models/face_detector/deploy.prototxt"
    CAFFEMODEL = "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"
    use_dnn = os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL)

    if use_dnn:
        net = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
        print("[reframe] Using DNN face detector (ResNet SSD)", flush=True)
    else:
        # Fallback to Haar cascade if model files not available
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        print("[reframe] WARNING: DNN model not found, falling back to Haar cascade", flush=True)

    # Track last known face position for temporal smoothing
    last_cx, last_cy = center_x, center_y
    CONFIDENCE_THRESHOLD = 0.5

    positions = []
    for t in sample_timestamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000.0)
        ret, frame = cap.read()
        if not ret or frame is None:
            positions.append({"t": float(t), "cx": last_cx, "cy": last_cy, "found": False})
            continue

        found = False
        best_cx, best_cy = center_x, center_y
        best_conf = 0.0

        if use_dnn:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(frame, (300, 300)), 1.0, (300, 300),
                (104.0, 177.0, 123.0), swapRB=False, crop=False
            )
            net.setInput(blob)
            detections = net.forward()

            best_area = 0
            for det_i in range(detections.shape[2]):
                confidence = float(detections[0, 0, det_i, 2])
                if confidence < CONFIDENCE_THRESHOLD:
                    continue
                x1 = int(detections[0, 0, det_i, 3] * w)
                y1 = int(detections[0, 0, det_i, 4] * h)
                x2 = int(detections[0, 0, det_i, 5] * w)
                y2 = int(detections[0, 0, det_i, 6] * h)
                area = (x2 - x1) * (y2 - y1)
                # Pick the largest face with highest confidence
                if confidence > best_conf or (confidence > CONFIDENCE_THRESHOLD and area > best_area):
                    best_conf = confidence
                    best_area = area
                    best_cx = (x1 + x2) // 2
                    best_cy = (y1 + y2) // 2
                    found = True
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
            if len(faces) > 0:
                fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                best_cx = int(fx + fw // 2)
                best_cy = int(fy + fh // 2)
                found = True

        if found:
            last_cx, last_cy = best_cx, best_cy

        positions.append({
            "t": float(t),
            "cx": best_cx if found else last_cx,
            "cy": best_cy if found else last_cy,
            "found": found,
            "confidence": best_conf if found else 0.0,
        })

    cap.release()
    found_count = sum(1 for p in positions if p["found"])
    print(f"[reframe] Detected faces in {found_count}/{len(positions)} sampled frames", flush=True)
    return positions


def detect_face_positions_dense(video_path, every_n_frames=5, target_w=None, target_h=None):
    """
    Dense face detection using FFmpeg frame extraction + OpenCV DNN.
    FFmpeg extracts every Nth frame with GPU decode (NVDEC) — much faster
    than OpenCV's sequential read/grab loop which must decode all h264 frames.

    target_w/target_h: if set, scale coordinates to this resolution (e.g., when
    running on a low-res proxy but need coords in original source resolution).

    Returns list of {"t": float, "cx": float, "cy": float, "found": bool, "confidence": float}.
    """
    import cv2

    # Probe video metadata without decoding
    _probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
        capture_output=True, text=True, timeout=5,
    )
    _streams = json.loads(_probe.stdout or "{}").get("streams", [])
    _vs = next((s for s in _streams if s.get("codec_type") == "video"), {})
    fps = float(eval(_vs.get("r_frame_rate", "30/1")))
    frame_count = int(_vs.get("nb_frames", 0)) or int(float(_vs.get("duration", "0")) * fps)
    frame_w = int(_vs.get("width", 0)) or 1080
    frame_h = int(_vs.get("height", 0)) or 1920

    # Output resolution for face coordinates
    _out_w = target_w or frame_w
    _out_h = target_h or frame_h

    # Extract at native resolution if source is already small (e.g., 240p proxy),
    # otherwise extract at 540p for speed
    _extract_h = min(540, frame_h)
    _scale = _out_h / _extract_h if _extract_h > 0 else 1.0
    _extract_w = round(frame_w * _extract_h / frame_h) if frame_h > 0 else round(_out_w * _extract_h / _out_h)
    center_x = _out_w // 2
    center_y = _out_h // 2

    PROTOTXT = "/models/face_detector/deploy.prototxt"
    CAFFEMODEL = "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"
    if not (os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL)):
        print("[dense-face] DNN model not found, cannot run dense detection", flush=True)
        return []

    net = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
    CONFIDENCE_THRESHOLD = 0.5

    _t_start = time.time()

    # Extract every Nth frame at reduced resolution using FFmpeg with GPU decode.
    # This is 5-10x faster than OpenCV's grab()/read() loop because:
    # 1. NVDEC hardware decode (vs CPU h264 decode)
    # 2. Only outputs frames we need (vs decoding all frames sequentially)
    # 3. Downscale happens on GPU or during decode (less memory bandwidth)
    _extract_dir = os.path.join(os.path.dirname(video_path) or "/tmp", "_face_frames")
    os.makedirs(_extract_dir, exist_ok=True)
    _hw_args = ["-hwaccel", "cuda"] if _HAS_HWACCEL else []
    _extract_cmd = subprocess.run(
        ["ffmpeg", "-y", "-v", "warning"] + _hw_args + [
            "-i", video_path,
            "-vf", f"select=not(mod(n\\,{every_n_frames})),scale={_extract_w}:{_extract_h}",
            "-vsync", "0", "-q:v", "2",
            os.path.join(_extract_dir, "face_%04d.jpg"),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if _extract_cmd.returncode != 0:
        raise RuntimeError(
            f"FFmpeg face-frame extraction failed (rc={_extract_cmd.returncode}): "
            f"{(_extract_cmd.stderr or '')[-300:]}"
        )

    _extract_elapsed = time.time() - _t_start
    _frame_files = sorted(glob.glob(os.path.join(_extract_dir, "face_*.jpg")))
    if not _frame_files:
        print("[dense-face] No frames extracted", flush=True)
        return []

    # Run DNN on extracted frames
    last_cx, last_cy = center_x, center_y
    positions = []

    for _fi, _fpath in enumerate(_frame_files):
        frame_idx = _fi * every_n_frames
        t_sec = frame_idx / fps
        frame = cv2.imread(_fpath)
        if frame is None:
            continue

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0, (300, 300),
            (104.0, 177.0, 123.0), swapRB=False, crop=False
        )
        net.setInput(blob)
        detections = net.forward()

        found = False
        best_cx, best_cy = center_x, center_y
        best_conf = 0.0
        best_area = 0

        for det_i in range(detections.shape[2]):
            confidence = float(detections[0, 0, det_i, 2])
            if confidence < CONFIDENCE_THRESHOLD:
                continue
            # Coordinates are in extract resolution — scale back to original
            x1 = int(detections[0, 0, det_i, 3] * w * _scale)
            y1 = int(detections[0, 0, det_i, 4] * h * _scale)
            x2 = int(detections[0, 0, det_i, 5] * w * _scale)
            y2 = int(detections[0, 0, det_i, 6] * h * _scale)
            area = (x2 - x1) * (y2 - y1)
            if confidence > best_conf or (confidence > CONFIDENCE_THRESHOLD and area > best_area):
                best_conf = confidence
                best_area = area
                best_cx = (x1 + x2) // 2
                best_cy = (y1 + y2) // 2
                found = True

        if found:
            last_cx, last_cy = best_cx, best_cy

        positions.append({
            "t": round(t_sec, 4),
            "cx": float(best_cx if found else last_cx),
            "cy": float(best_cy if found else last_cy),
            "found": found,
            "confidence": round(best_conf, 4) if found else 0.0,
        })

    # Cleanup extracted frames
    for _f in _frame_files:
        try:
            os.remove(_f)
        except OSError:
            pass
    try:
        os.rmdir(_extract_dir)
    except OSError:
        pass

    elapsed = time.time() - _t_start
    found_count = sum(1 for p in positions if p["found"])
    print(
        f"[dense-face] {found_count}/{len(positions)} detections in {elapsed:.2f}s "
        f"({frame_count} total frames, every {every_n_frames}th @ {fps:.1f}fps, extracted at {_extract_w}x{_extract_h})",
        flush=True,
    )
    return positions


def smooth_face_trajectory(detections, total_duration=0.0, alpha=0.15):
    """
    Apply exponential moving average to dense face detections for buttery
    smooth camera movement.  Gaps (found=False) coast on the last known
    smoothed position.

    Returns a new list with the same structure but smoothed cx/cy values.
    """
    if not detections:
        return []

    smoothed = []
    sx, sy = None, None

    for det in detections:
        cx = float(det.get("cx", 540.0))
        cy = float(det.get("cy", 960.0))
        found = det.get("found", False)

        if sx is None:
            # Initialise with first position
            sx, sy = cx, cy
        else:
            if found:
                sx = alpha * cx + (1.0 - alpha) * sx
                sy = alpha * cy + (1.0 - alpha) * sy
            # else: coast — sx/sy stay unchanged

        smoothed.append({
            "t": det["t"],
            "cx": round(sx, 2),
            "cy": round(sy, 2),
            "found": found,
            "confidence": det.get("confidence", 0.0),
        })

    return smoothed


def _face_position_at(trajectory, t_seconds, canvas_w=1080, canvas_h=1920):
    """Find the smoothed face position closest to `t_seconds`.

    Returns (origin_x, origin_y, confidence) where origin_x/origin_y are
    normalized to the canonical 1080x1920 canvas with rule-of-thirds
    adjustment (eyes sit ~10% of canvas height above face center, so the
    zoom origin lands on the eyes — that's the perceptual focal point on
    a face). Returns (None, None, 0.0) if no detection nearby or the
    closest detection failed (found=False).

    Smoothed trajectory is dense (one keyframe every ~3s); nearest-
    neighbor lookup is enough — the smoothing pass already made cx/cy
    continuous between samples.
    """
    if not trajectory:
        return None, None, 0.0
    closest = min(trajectory, key=lambda p: abs(float(p.get("t", 0.0)) - float(t_seconds)))
    if not closest.get("found"):
        return None, None, 0.0
    cx = float(closest.get("cx", 0))
    cy = float(closest.get("cy", 0))
    conf = float(closest.get("confidence", 0))
    # Normalize + rule-of-thirds eye offset. Face center ≈ nose; eyes sit
    # roughly 10% of canvas height above center for a typical talking-head
    # framing. Subtracting 0.1 in normalized space lands the zoom origin
    # on the eyes — the natural focal point. Clamp to [0, 1] in case the
    # face lies outside the canonical canvas (non-9:16 source where the
    # detection coords may overshoot the post-crop frame).
    origin_x = max(0.0, min(1.0, cx / float(canvas_w)))
    origin_y = max(0.0, min(1.0, cy / float(canvas_h) - 0.1))
    return origin_x, origin_y, conf


def _resolve_zoom_origin(ev, source_time_s, face_trajectory):
    """Resolve the zoom origin for a single ABE event.

    Contract (matches handler.py:~2980 in the system prompt):
      - If Gemini emitted originX/originY explicitly, use them verbatim.
        This is the non-face-element path (prop, gesture, whiteboard) —
        Gemini watched the proxy and chose coords on a thing the pipeline
        cannot detect.
      - Otherwise (the default face-zoom path), look up the nearest
        smoothed face detection to `source_time_s` and lock the origin
        onto the face's eye line via `_face_position_at`. Reuses the
        existing sparse trajectory; no new sampling.
      - When the trajectory has no `found=True` detection nearby, fall
        back to canvas center (0.5, 0.5) AND emit a `[divergence]
        component=zoom_origin` line so the gap is visible instead of
        silently drifting off-subject.

    Returns (origin_x, origin_y, was_resolved_by_face_lock: bool).
    """
    _gemini_x = ev.get("originX")
    _gemini_y = ev.get("originY")
    if _gemini_x is not None and _gemini_y is not None:
        return float(_gemini_x), float(_gemini_y), False

    _ox, _oy, _conf = _face_position_at(face_trajectory, source_time_s)
    if _ox is not None and _oy is not None:
        return round(_ox, 4), round(_oy, 4), True

    # No face box near this frame on a face-zoom event — log + center.
    # The prompt promised Gemini face-locking; the trajectory failed to
    # produce one. Either face detection found no face at that moment
    # (genuine — speaker turned, occlusion) or the sparse keyframes are
    # too sparse for this particular event. Either way, viewer-visible
    # if we just stay silent.
    _record_divergence(
        "zoom_origin",
        {
            "source_time_s": round(float(source_time_s), 3),
            "event_startMs": ev.get("startMs"),
            "expected": "face",
        },
        "fallback_to_center",
        final={"originX": 0.5, "originY": 0.5},
        reason="no_face_box_at_frame",
    )
    return 0.5, 0.5, False


def calculate_reframe_crop(face_positions, source_w, source_h, target_w=1080, target_h=1920):
    """
    Calculate a crop window that keeps the detected face near frame center.
    Returns crop positions in source-pixel coordinates, or None if no crop shift is needed.
    """
    if source_w == target_w and source_h == target_h:
        return None

    target_aspect = target_w / target_h
    source_aspect = source_w / source_h if source_h else target_aspect

    if source_aspect > target_aspect:
        crop_h = source_h
        crop_w = int(source_h * target_aspect)
    else:
        crop_w = source_w
        crop_h = int(source_w / target_aspect) if target_aspect else source_h

    crops = []
    for pos in face_positions:
        crop_x = int(pos["cx"] - crop_w // 2)
        crop_y = int(pos["cy"] - crop_h // 2)
        crop_x = max(0, min(crop_x, max(0, source_w - crop_w)))
        crop_y = max(0, min(crop_y, max(0, source_h - crop_h)))
        crops.append({
            "t": pos["t"],
            "crop_x": crop_x,
            "crop_y": crop_y,
            "crop_w": crop_w,
            "crop_h": crop_h,
            "found": bool(pos.get("found")),
        })

    return crops

def normalize_analysis(parsed):
    if not parsed.get("speech"):
        parsed["speech"] = {"has_speech": False, "segments": [], "sentence_boundaries": []}
    if not parsed.get("safe_cut_points"):
        parsed["safe_cut_points"] = []
    if not parsed.get("peak_moments"):
        parsed["peak_moments"] = []
    if not parsed.get("highlights"):
        parsed["highlights"] = []
    if parsed.get("footage_assessment") and not parsed.get("video_profile"):
        parsed["video_profile"] = parsed["footage_assessment"]

    duration = float(parsed.get("duration") or 0)
    shots_raw = parsed.get("shots") or []
    shots = []
    for i, s in enumerate(shots_raw):
        shots.append({
            "start":         float(s.get("start") or 0),
            "end":           float(s.get("end") or duration),
            "visual":        s.get("visual") or "",
            "action":        s.get("action") or "",
            "energy":        float(s.get("energy") or 0.5),
            "editing_value": s.get("editing_value") or "",
            "delivery":      s.get("delivery") or "none",
            "description":   s.get("action") or s.get("visual") or f"Shot {i+1}",
            "score":         float(s.get("energy") or 0.5),
        })
    if not shots:
        shots = [{"start": 0, "end": duration, "description": "Full video", "score": 0.5,
                  "visual": "", "action": "", "energy": 0.5, "editing_value": "", "delivery": "none"}]

    raw_cb = parsed.get("color_baseline") or {}
    color_baseline = {
        "assessment":        raw_cb.get("assessment") or "",
        "brightness":        float(raw_cb["brightness"]) if isinstance(raw_cb.get("brightness"), (int, float)) else 1,
        "contrast":          float(raw_cb["contrast"]) if isinstance(raw_cb.get("contrast"), (int, float)) else 1,
        "saturation":        float(raw_cb["saturation"]) if isinstance(raw_cb.get("saturation"), (int, float)) else 1,
        "gamma":             float(raw_cb["gamma"]) if isinstance(raw_cb.get("gamma"), (int, float)) else 1,
        "color_temperature": raw_cb.get("color_temperature") if raw_cb.get("color_temperature") in ["warm", "cool", "neutral"] else "neutral",
    }
    raw_fl = parsed.get("frame_layout") or {}
    frame_layout = {
        "subject_position": raw_fl.get("subject_position") or "unknown",
        "existing_overlays": {
            "has_burned_captions": bool((raw_fl.get("existing_overlays") or {}).get("has_burned_captions")),
            "has_text_graphics":   bool((raw_fl.get("existing_overlays") or {}).get("has_text_graphics")),
            "overlay_locations":   (raw_fl.get("existing_overlays") or {}).get("overlay_locations") or "none detected",
        },
        "free_zones": raw_fl.get("free_zones") or "unknown",
    }

    # Hook, pacing, recommended_duration (new fields — backward compatible)
    raw_fa  = parsed.get("footage_assessment") or parsed.get("video_profile") or {}
    raw_hook = raw_fa.get("hook") or {}
    hook = {
        "timestamp":   float(raw_hook["timestamp"]) if isinstance(raw_hook.get("timestamp"), (int, float)) else 0.0,
        "description": str(raw_hook.get("description") or ""),
        "why":         str(raw_hook.get("why") or ""),
        "quality":     float(raw_hook["quality"]) if isinstance(raw_hook.get("quality"), (int, float)) else 0.5,
    } if raw_hook else None

    recommended_duration = None
    if isinstance(raw_fa.get("recommended_duration"), (int, float)):
        recommended_duration = int(raw_fa["recommended_duration"])

    pacing = str(raw_fa.get("pacing") or "").strip().lower()
    if pacing not in ("fast", "medium", "slow"):
        pacing = None

    raw_fq = parsed.get("footage_quality") or {}
    valid_noise       = {"none", "low", "medium", "high"}
    valid_sharpness   = {"soft", "normal", "sharp"}
    valid_highlight   = {"clipped", "bright", "normal", "dark"}
    valid_shadow      = {"crushed", "deep", "normal", "lifted"}
    valid_richness    = {"flat", "muted", "normal", "vivid"}
    valid_lighting    = {"natural_outdoor", "natural_indoor", "studio", "mixed", "unknown"}
    footage_quality = {
        "noise_level":       raw_fq.get("noise_level", "low") if raw_fq.get("noise_level") in valid_noise else "low",
        "source_sharpness":  raw_fq.get("source_sharpness", "normal") if raw_fq.get("source_sharpness") in valid_sharpness else "normal",
        "highlight_condition": raw_fq.get("highlight_condition", "normal") if raw_fq.get("highlight_condition") in valid_highlight else "normal",
        "shadow_condition":  raw_fq.get("shadow_condition", "normal") if raw_fq.get("shadow_condition") in valid_shadow else "normal",
        "color_richness":    raw_fq.get("color_richness", "normal") if raw_fq.get("color_richness") in valid_richness else "normal",
        "skin_tones_present": bool(raw_fq.get("skin_tones_present", True)),
        "lighting_type":     raw_fq.get("lighting_type", "unknown") if raw_fq.get("lighting_type") in valid_lighting else "unknown",
    }
    safe_cut_points = parsed.get("cut_points") or parsed.get("safe_cut_points") or []
    peak_moments = parsed.get("highlights") or parsed.get("peak_moments") or []
    vp = parsed.get("video_profile") or parsed.get("footage_assessment") or {}

    return {
        "duration":             duration,
        "shots":                shots,
        "speech":               parsed.get("speech") or {"has_speech": False, "segments": [], "sentence_boundaries": []},
        "audio":                parsed.get("audio") or {},
        "safe_cut_points":      safe_cut_points,
        "peak_moments":         peak_moments,
        "video_profile":        vp,
        "frame_layout":         frame_layout,
        "color_baseline":       color_baseline,
        "footage_quality":      footage_quality,
        "metadata":             parsed.get("metadata") or {},
        "visual_cuts":          [],
        "hook":                 hook,
        "recommended_duration": recommended_duration,
        "pacing":               pacing,
    }




# ─── BEAT DETECTION ──────────────────────────────────────────────────────────

def cluster_shot_changes(shot_changes, min_gap=0.5):
    """Filter ffmpeg scdet noise by collapsing detections within `min_gap`
    seconds into a single event (kept: the earliest). scdet at threshold=0.30
    fires on motion + lighting changes too, producing hundreds of detections
    on a fast-cut promo video; this clusters them to real visual cuts.
    """
    if not shot_changes:
        return []
    sorted_shots = sorted(shot_changes)
    clustered = [sorted_shots[0]]
    for _s in sorted_shots[1:]:
        if _s - clustered[-1] >= min_gap:
            clustered.append(_s)
    return clustered


def shot_change_word_boundaries(shot_changes, kept_words, snap_tolerance=0.60, shot_scores=None, out_scores=None):
    """Map each clustered shot change to a kept-word boundary (in kept-word
    index space) and its corresponding split-time (source seconds).

    For each shot change, find the kept-word EDGE (end of word N OR start
    of word N+1) closest within `snap_tolerance` seconds. The chosen
    boundary becomes the after-word-index N (last word of pre-split clip);
    the split time is word N's `.end` in source-time.

    Snap tolerance bumped from 0.30s → 0.60s — production sweep showed
    real cuts at score 12.60 and 12.07 silently dropped because the
    speaker was mid-sentence at the cut and the nearest word END was
    >0.30s away (even though the next word's START was <0.05s away).
    0.60s covers the longest English word at slow expressive tempo;
    also-check-the-next-word-start covers the mid-sentence case.

    When a detection can't be snapped after both expansions, _record_divergence
    logs it instead of dropping silently — that is the audit fix for
    the "FLAGGED cuts vanishing" bug.

    Returns a list of (new_idx, source_time_seconds) tuples, sorted by
    new_idx, deduplicated. Used by both:
      - the pre-Gemini CUT BOUNDARIES signal (uses new_idx values)
      - the post-Gemini clip splitter (uses source_time_seconds values)
    """
    if not shot_changes or not kept_words:
        return []
    clustered = cluster_shot_changes(shot_changes)
    seen_indices = set()
    out = []
    for _sc in clustered:
        _best_idx = None
        _best_dist = snap_tolerance
        _best_we = None
        for _new_idx, _w in enumerate(kept_words):
            _we = float(_w.get("end") or 0)
            # Distance to end of this word.
            _dist_end = abs(_we - _sc)
            if _dist_end <= _best_dist:
                _best_dist = _dist_end
                _best_idx = _new_idx
                _best_we = _we
            # Also check distance to start of the NEXT word — covers
            # mid-sentence cuts where the speaker resumes from a different
            # word and the cut lands inside the word-gap. The pre-split
            # boundary is still word N (the LAST kept word before the cut).
            if _new_idx + 1 < len(kept_words):
                _next_ws = float(kept_words[_new_idx + 1].get("start") or 0)
                _dist_start = abs(_next_ws - _sc)
                if _dist_start <= _best_dist:
                    _best_dist = _dist_start
                    _best_idx = _new_idx
                    _best_we = _we
        if (
            _best_idx is not None
            and 0 <= _best_idx < len(kept_words) - 1  # not the last word
            and _best_idx not in seen_indices
        ):
            out.append((_best_idx, _best_we))
            seen_indices.add(_best_idx)
            # Carry the scdet confidence score for this boundary out via the
            # side-channel dict (keyed by kept-word index). `_sc` is the
            # clustered detection time; shot_scores is keyed by round(t, 3).
            # Used only by the scene-change floor's confidence gate.
            if out_scores is not None and shot_scores is not None:
                out_scores[_best_idx] = shot_scores.get(round(float(_sc), 3))
        else:
            # Detection didn't snap. Could not place a boundary — log so
            # the silent drop becomes visible. The pre-Gemini boundary
            # union loses this cut, but at least we know.
            _reason = (
                "no_kept_word_edge_within_tolerance"
                if _best_idx is None
                else ("last_word_boundary" if _best_idx == len(kept_words) - 1
                      else "duplicate_after_clustering")
            )
            _record_divergence(
                "shot_change_snap",
                {
                    "source_time_s": round(float(_sc), 3),
                    "snap_tolerance_s": snap_tolerance,
                    "best_kept_word_idx": _best_idx,
                    "best_distance_s": (
                        round(float(_best_dist), 3) if _best_idx is not None else None
                    ),
                },
                "drop_unsnapped",
                reason=_reason,
            )
    out.sort(key=lambda t: t[0])
    return out


def _parse_scdet_output(stdout, stderr):
    """Parse scdet's metadata output → list of (timestamp_s, score) tuples,
    sorted by timestamp, deduplicated.

    scdet at sc_pass=1 emits per-frame metadata blocks to stdout like:
        frame:123 pts:41000 pts_time:1.366
        lavfi.scdet.mafd=...
        lavfi.scdet.score=0.412

    Some ffmpeg builds emit `lavfi.scd.score=` (older name) or send the
    info to stderr only. Both fallbacks are handled here.

    When the timestamp is parseable but the score isn't, the score is
    returned as 0.0 — the caller can filter it out if it cares about
    score-based filtering.
    """
    detections = []
    _pending_t = None
    for _line in (stdout or "").splitlines():
        _line = _line.strip()
        if _line.startswith("frame:") and "pts_time:" in _line:
            _tok = _line.split("pts_time:")[-1].split()[0]
            try:
                _pending_t = float(_tok)
            except ValueError:
                _pending_t = None
        elif "lavfi.scdet.score=" in _line or "lavfi.scd.score=" in _line:
            _stok = _line.split("score=")[-1].strip()
            try:
                _score = float(_stok)
            except ValueError:
                _score = 0.0
            if _pending_t is not None:
                detections.append((round(_pending_t, 3), round(_score, 3)))
                _pending_t = None
    # Stderr fallback for builds that send metadata there without the
    # per-frame stdout block. scdet logs flagged frames like:
    #   [Parsed_scdet_0 @ 0x...] lavfi.scdet.score:3.12 pts_time:5.482
    if not detections and stderr:
        for _line in stderr.splitlines():
            if "Parsed_scdet" not in _line or "pts_time:" not in _line:
                continue
            _ttok = _line.split("pts_time:")[-1].split()[0]
            try:
                _t = float(_ttok)
            except ValueError:
                continue
            _score = 0.0
            if "score:" in _line:
                _stok = _line.split("score:")[-1].split()[0]
                try:
                    _score = float(_stok)
                except ValueError:
                    pass
            detections.append((round(_t, 3), round(_score, 3)))
    # De-duplicate by timestamp, keep first observed score.
    seen = set()
    out = []
    for _t, _s in detections:
        if _t in seen:
            continue
        seen.add(_t)
        out.append((_t, _s))
    out.sort(key=lambda ts: ts[0])
    return out


# scdet runs at this wide-net threshold so EVERY potential cut surfaces
# (down to mild motion). Python then filters to the production threshold
# (default 12.0) for the return value, AND logs every parsed detection
# under `[scdet-sweep]` so a single grep tells the operator what scores
# the source actually produced. Load-bearing for diagnosing same-framing
# splices that live below threshold=12 — the "I expect" → "I know"
# conversion. Set to 1.0 to capture the typical same-framing splice
# zone (~1.5-6) without flooding pure-noise frames at 0.x.
_SCDET_SWEEP_THRESHOLD = 1.0


def detect_shot_changes(source_path, threshold=7.0, out_scores=None):
    """Detect hard shot changes in the source video via ffmpeg's `scdet`
    (scene change detect) filter.

    `threshold` is scdet's scene-score threshold on a 0-100 scale
    (ffmpeg's vf_scdet.c sets default=10, range 0-100). Previously we
    passed 0.30 thinking it was a 0-1 sensitivity dial — that produced
    300+ detections on a 22s video (every frame with any motion at all).
    Then 12.0 — which filtered motion noise but ALSO filtered real cuts
    on normal-framing footage that scored 8-11.

    Lowered to 7.0 based on production sweep data showing real cuts on
    normal-framing footage at 8.72-10.23 (well above motion floor 1-3)
    with a ~5.7 gap between motion ceiling and cut floor. Threshold 7.0
    sits in that gap. Caveat: footage with extreme gestures may produce
    motion scores 8-9 (false positives). The [scdet-sweep] log shows
    every detection with its score so false-positive surface stays
    visible across renders — escalate to adaptive thresholding if FPs
    become frequent.

    SEPARATELY: same-framing same-spot splices score ~2-6 because the
    visual delta between back-to-back takes is near zero — below ANY
    threshold the noise floor allows. Those need an audio-discontinuity
    detector, not threshold tuning. See the sweep log to confirm the
    score distribution on this source.

    To diagnose that miss rate without guessing, scdet runs internally
    at _SCDET_SWEEP_THRESHOLD (much lower) and every parsed detection
    is logged with its score under `[scdet-sweep]`. The RETURN value
    is filtered to >= `threshold` so production behavior is unchanged;
    the sweep is purely observational. After a render, grep
    `[scdet-sweep]` and check whether the user's known cut timestamps
    appear as low-score detections — if so, the visual signal exists
    but the threshold is filtering it; if not, the visual signal genuinely
    isn't there and the cut needs a different detector (e.g. audio
    discontinuity).
    """
    cmd = [
        "ffmpeg", "-i", source_path, "-an",
        "-vf", f"scdet=threshold={_SCDET_SWEEP_THRESHOLD}:sc_pass=1,metadata=print:file=-",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    detections = _parse_scdet_output(proc.stdout, proc.stderr)

    # Sweep log — one grep-stable line per detection. Score-tagged so we
    # can see the distribution and decide whether a threshold sweep would
    # have caught the missed cuts, or whether they live below the noise
    # floor entirely.
    for _t, _score in detections:
        _flag = "FLAGGED" if _score >= threshold else "below"
        print(
            f"[scdet-sweep] t={_t:.3f}s score={_score:.2f} "
            f"({_flag} @ threshold={threshold:.1f})",
            flush=True,
        )

    # Production return: timestamps whose score crossed the production
    # threshold. If score parsing failed across the board (score=0.0 for
    # every entry — older ffmpeg builds), fall back to the legacy behavior
    # of trusting scdet's own threshold filter by running ONCE more at the
    # production threshold instead. This is the no-regression guard.
    _scored = [(t, s) for t, s in detections if s > 0.0]
    if not _scored and detections:
        # Parser couldn't recover scores; re-run scdet at the production
        # threshold (the original 2025 behavior) and take its filtered set.
        print(
            f"[shot-changes] WARNING: scdet output had no parsable scores — "
            f"falling back to legacy single-call threshold filter "
            f"(detections={len(detections)}, all score=0.0)",
            flush=True,
        )
        cmd_legacy = [
            "ffmpeg", "-i", source_path, "-an",
            "-vf", f"scdet=threshold={threshold}:sc_pass=1,metadata=print:file=-",
            "-f", "null", "-",
        ]
        proc_legacy = subprocess.run(cmd_legacy, capture_output=True, text=True, timeout=60)
        legacy_detections = _parse_scdet_output(proc_legacy.stdout, proc_legacy.stderr)
        changes = sorted({t for t, _ in legacy_detections})
        # Legacy path recovered no usable scores → leave out_scores empty so
        # the scene-change floor fails OPEN (decorates) rather than skipping.
    else:
        changes = sorted({t for t, s in detections if s >= threshold})
        if out_scores is not None:
            # Map flagged timestamp → score so the scene-change floor can gate
            # its automatic backfill on confidence. Keyed by round(t, 3) to
            # match the boundary snapper's lookup; keeps the MAX per timestamp.
            for _t, _s in detections:
                if _s >= threshold:
                    _k = round(float(_t), 3)
                    if _s > out_scores.get(_k, 0.0):
                        out_scores[_k] = float(_s)

    print(
        f"[shot-changes] Detected {len(changes)} cuts "
        f"(threshold={threshold}, sweep_window>={_SCDET_SWEEP_THRESHOLD})",
        flush=True,
    )
    return changes


# ─── DEEPGRAM TRANSCRIPTION ───────────────────────────────────────────────────


def prepare_audio_for_deepgram(source_path: str) -> bytes:
    """Extract bit-perfect mono FLAC for transcription.

    Hand Deepgram the highest-fidelity audio we can: raw PCM (sample-rate +
    channel normalized) wrapped in lossless FLAC. No level processing, no
    EQ, no compression — every dB and every transient reaches the model
    exactly as it sat in the source's PCM-decoded audio.

      • mono channel — Deepgram's models are tuned for mono speech
      • 48 kHz sample rate — preserves all source detail
      • lossless FLAC encode — no second-generation lossy compression on top
        of whatever the source already lost in its AAC encode

    Single-pass loudnorm was previously applied here to "boost confidence on
    soft consonants" but ffmpeg's single-pass loudnorm is a dynamic-range
    compressor that smears word onsets — confirmed source of substitution
    errors like "for Israel" → "phraise room". Nova-3 doesn't need our help
    on levels; it was trained on raw phone calls and varied-level podcasts.

    Returns FLAC bytes ready for Deepgram's transcribe_file. Typical size on
    a 60s clip: ~5-8 MB (vs 80 MB for the full video), so the upload is
    actually faster than sending the raw file too.
    """
    cmd = [
        "ffmpeg", "-v", "error", "-threads", "0",
        "-i", source_path,
        "-vn", "-ac", "1", "-ar", "48000",
        "-c:a", "flac", "-compression_level", "5",
        "-f", "flac", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Deepgram audio prep failed: {(proc.stderr or b'').decode('utf-8', errors='replace')[-300:]}"
        )
    print(
        f"[deepgram-prep] Extracted {len(proc.stdout) / 1024:.0f}KB FLAC "
        f"(mono 48kHz, lossless — no level processing)",
        flush=True,
    )
    return proc.stdout


def _deepgram_options(keywords=None):
    """Deepgram Nova-3 transcription options.

    `keywords` is an optional list of `"term:intensifier"` strings that
    boost recognition for proper nouns (names, places, brand terms) the
    speaker is likely to use. Without these, Nova-3 mishears uncommon
    proper nouns (e.g. "Ryan" → "right").

    Nova-3 uses `keyterm` (Nova-2 used `keywords`). Sending `keywords`
    against Nova-3 fails the request with HTTP 400: "Keywords are not
    supported for Nova-3. Please use `keyterm` instead." Nova-3 also
    doesn't accept the `term:intensifier` suffix — it handles boosting
    internally — so we strip the legacy `:N` form before sending.
    """
    kwargs = dict(
        model="nova-3", detect_language=True,
        smart_format=True, utterances=True, punctuate=True, diarize=True,
        # Deepgram silently strips disfluencies ("um", "uh", "uhm") from the
        # transcript by default. For editorial cutting we need those tokens
        # in the word list — the mechanical filler detector relies on seeing
        # the actual hesitations to remove them. Turning this on means the
        # ASR returns "um" / "uh" / "uhm" with timestamps just like any other
        # word.
        filler_words=True,
    )
    if keywords:
        _terms = []
        for k in keywords:
            term = str(k).split(":", 1)[0].strip()
            if term:
                _terms.append(term)
        if _terms:
            kwargs["keyterm"] = _terms
    return PrerecordedOptions(**kwargs)


def _extract_proper_noun_keywords(text):
    """Pull Title-Case proper nouns from a free-text input (the user's
    vibe / title / caption) for Deepgram keyword boosting.

    Heuristic: Title-Case tokens that aren't common sentence-start words.
    "Interview with Ryan about Hatikvah" → ["Ryan:5", "Hatikvah:5"].
    "Viral engaging video" → [] (no proper nouns).

    Returns a list of `"term:5"` strings ready to pass to Deepgram.
    """
    if not text:
        return []
    # Common Title-Case words that aren't proper nouns (sentence starts,
    # generic capitalization). Filter these out to avoid noise.
    _COMMON_TITLECASE = frozenset({
        "I", "The", "A", "An", "And", "Or", "But", "So", "If", "When",
        "What", "Why", "How", "Where", "Who", "This", "That", "These", "Those",
        "My", "Your", "His", "Her", "Our", "Their", "Its",
        "Is", "Are", "Was", "Were", "Be", "Been", "Being",
        "Viral", "Engaging", "Video", "Edit", "Edits", "Editing", "Clip",
        "Short", "Shorts", "Reel", "Reels", "TikTok",
    })
    out = []
    seen = set()
    for tok in str(text).split():
        # Strip surrounding punctuation, keep the lemma.
        clean = "".join(ch for ch in tok if ch.isalpha() or ch == "-")
        if not clean or len(clean) < 2:
            continue
        if not clean[0].isupper():
            continue
        if clean in _COMMON_TITLECASE:
            continue
        if clean.lower() in seen:
            continue
        seen.add(clean.lower())
        out.append(f"{clean}:5")
    return out



def _parse_deepgram_response(resp):
    """Common response parsing for both file-based and URL-based Deepgram calls."""
    alt = resp.results.channels[0].alternatives[0]
    raw_words = alt.words or []
    words = [
        {
            "word":            w.word,
            "punctuated_word": getattr(w, "punctuated_word", w.word),
            "start":           float(w.start),
            "end":             float(w.end),
            "confidence":      float(getattr(w, "confidence", 1.0)),
            "speaker":         int(getattr(w, "speaker", 0)),
        }
        for w in raw_words
    ]

    # Utterances group words by speaker turn and are more reliable than
    # per-word speaker labels. Override per-word labels with utterance-level
    # speaker assignments when available. Also capture the utterance list
    # for downstream consumers that need explicit turn boundaries.
    raw_utterances = getattr(resp.results, "utterances", None) or []
    utterances = []
    if raw_utterances:
        for utt in raw_utterances:
            utt_start = float(getattr(utt, "start", 0))
            utt_end = float(getattr(utt, "end", 0))
            utt_speaker = int(getattr(utt, "speaker", 0))
            utterances.append({
                "start": utt_start,
                "end": utt_end,
                "speaker": utt_speaker,
            })
            for w in words:
                if w["start"] >= utt_start - 0.05 and w["end"] <= utt_end + 0.05:
                    w["speaker"] = utt_speaker
        print(f"[deepgram] Applied {len(utterances)} utterance-level speaker labels", flush=True)

    speaker_ids = set(w["speaker"] for w in words)
    if len(speaker_ids) > 1:
        print(f"[deepgram] Detected {len(speaker_ids)} speakers", flush=True)

    print(f"[deepgram] Transcribed {len(words)} words", flush=True)
    return {"text": alt.transcript or "", "words": words, "utterances": utterances}


def _deepgram_is_retriable_error(msg):
    """Classify a Deepgram error message as retriable (rate limits, 5xx, network)."""
    m = str(msg)
    return (
        "429" in m or "rate" in m.lower() or
        "500" in m or "502" in m or "503" in m or "504" in m or
        "timeout" in m.lower() or "connection" in m.lower() or
        "temporarily" in m.lower()
    )


def transcribe_audio(source_path, keywords=None):
    """File-based Deepgram with loudness-normalized FLAC audio prep.

    Sends the cleaned mono 48 kHz FLAC produced by prepare_audio_for_deepgram
    rather than the raw video bytes — gives the model uniform-level audio
    and saves bandwidth (FLAC of just the audio stream is much smaller than
    the full video). 3-attempt exponential backoff on retriable errors.

    `keywords` (optional): list of `"term:intensifier"` strings for proper-
    noun boosting. Default None = no boosting. Pass keywords extracted
    from the user's vibe/title to bias Deepgram toward likely names.
    """
    if DeepgramClient is None or PrerecordedOptions is None:
        print("[pipeline] transcription skipped: deepgram not available", flush=True)
        return {"text": "", "words": []}
    dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
    audio_bytes = prepare_audio_for_deepgram(source_path)
    if keywords:
        _terms_for_log = [str(k).split(":", 1)[0].strip() for k in keywords]
        _terms_for_log = [t for t in _terms_for_log if t]
        print(
            f"[deepgram] Sending {len(audio_bytes) / 1024:.0f}KB FLAC audio "
            f"with {len(_terms_for_log)} keyterm boost(s): {_terms_for_log}",
            flush=True,
        )
    else:
        print(f"[deepgram] Sending {len(audio_bytes) / 1024:.0f}KB FLAC audio", flush=True)
    options = _deepgram_options(keywords=keywords)
    _t0 = time.time()
    last_err = None
    for attempt in range(3):
        try:
            resp = dg.listen.prerecorded.v("1").transcribe_file(
                {"buffer": audio_bytes, "mimetype": "audio/flac"},
                options,
            )
            result = _parse_deepgram_response(resp)
            print(f"[metric] stage_duration stage=transcribe_file duration_ms={int((time.time()-_t0)*1000)} attempt={attempt+1}", flush=True)
            return result
        except Exception as e:
            last_err = e
            if attempt < 2 and _deepgram_is_retriable_error(e):
                backoff = 2 ** attempt
                print(f"[deepgram] file attempt {attempt+1} retriable ({str(e)[:120]}) — retry in {backoff}s", flush=True)
                time.sleep(backoff)
                continue
            break
    raise RuntimeError(f"Deepgram transcription failed after 3 attempts: {last_err}") from last_err


# ─── TIGHTEN ──────────────────────────────────────────────────────────────────



def measure_source_loudness(source_path):
    """
    Measure the source audio's peak level, RMS, and noise floor using ffmpeg.
    Returns dict with 'peak_db', 'rms_db', 'noise_floor_db' (all negative floats).
    """
    # astats gives us peak, RMS; we sample the first 60s to keep it fast
    cmd = [
        "ffmpeg", "-i", source_path, "-t", "60",
        "-af", "astats=metadata=1:reset=0,ametadata=mode=print",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg loudness measurement failed: {(result.stderr or '')[-300:]}")
    stderr = result.stderr

    # Parse peak and RMS from astats output. ffmpeg emits "-inf" for silent
    # channels; the regex must capture that as one token so float() succeeds
    # (the downstream clamps pin -inf to -70.0).
    peak_matches = re.findall(r"lavfi\.astats\.Overall\.Peak_level=(-?inf|-?[\d.]+)", stderr)
    rms_matches = re.findall(r"lavfi\.astats\.Overall\.RMS_level=(-?inf|-?[\d.]+)", stderr)
    noise_matches = re.findall(r"lavfi\.astats\.Overall\.Noise_floor=(-?inf|-?[\d.]+)", stderr)
    if not peak_matches or not rms_matches:
        raise RuntimeError(f"FFmpeg astats returned no loudness data for {source_path}")

    peak_db = float(peak_matches[-1]) if peak_matches else -6.0
    rms_db = float(rms_matches[-1]) if rms_matches else -18.0
    # Noise floor: if astats reports it, use it; otherwise estimate from RMS - 24dB
    if noise_matches:
        noise_floor_db = float(noise_matches[-1])
    else:
        noise_floor_db = rms_db - 24.0

    # Clamp to reasonable ranges
    peak_db = max(-60.0, min(0.0, peak_db))
    rms_db = max(-60.0, min(0.0, rms_db))
    noise_floor_db = max(-70.0, min(-20.0, noise_floor_db))

    print(
        f"[loudness] peak={peak_db:.1f}dB rms={rms_db:.1f}dB noise_floor={noise_floor_db:.1f}dB",
        flush=True,
    )
    return {"peak_db": peak_db, "rms_db": rms_db, "noise_floor_db": noise_floor_db}


def detect_vocal_emphasis(source_path, max_peaks=20):
    """Detect moments of vocal emphasis — RMS envelope peaks above the local
    rolling average. Useful signal for Gemini to anchor zoom punch-ins and
    emphasis moments to actual vocal prominence (not just semantic guesses
    from the transcript).

    Returns: list of {"t": source_seconds, "score": 0..1} sorted by time,
             capped at `max_peaks`. Peaks are at least 0.3s apart.
    """
    import numpy as np

    # Extract mono audio at 16kHz as PCM (fast, low-disk).
    cmd = [
        "ffmpeg", "-i", source_path, "-vn",
        "-f", "f32le", "-ac", "1", "-ar", "16000", "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw = proc.stdout.read()
    proc.wait()
    if proc.returncode != 0:
        stderr_tail = (proc.stderr.read() or b"").decode("utf-8", errors="replace")[-300:]
        raise RuntimeError(f"FFmpeg audio extraction for vocal emphasis failed: {stderr_tail}")

    samples = np.frombuffer(raw, dtype=np.float32)
    if len(samples) < 16000:
        return []

    sr = 16000
    hop = 800            # 50 ms
    win = 1600           # 100 ms window
    n_frames = max(0, (len(samples) - win) // hop + 1)
    if n_frames < 10:
        return []

    # RMS envelope.
    rms = np.empty(n_frames, dtype=np.float32)
    for i in range(n_frames):
        s = samples[i * hop : i * hop + win]
        rms[i] = float(np.sqrt(np.mean(s * s)) + 1e-10)

    # Local rolling mean over ~2s.
    roll_win = max(5, int(2.0 * sr / hop))
    cumsum = np.cumsum(np.insert(rms, 0, 0.0))
    rolling_mean = np.empty_like(rms)
    for i in range(n_frames):
        a = max(0, i - roll_win // 2)
        b = min(n_frames, i + roll_win // 2 + 1)
        rolling_mean[i] = cumsum[b] - cumsum[a]
        rolling_mean[i] /= max(1, b - a)

    # Peaks where RMS exceeds rolling mean by > 1.5 local std deviations.
    diff = rms - rolling_mean
    std = float(np.std(diff) + 1e-10)
    threshold = 1.5 * std
    candidate_indices = np.where(diff > threshold)[0]
    if len(candidate_indices) == 0:
        return []

    # Non-maximum suppression: one peak per ~0.3s window.
    min_gap_frames = max(1, int(0.3 * sr / hop))
    peaks = []
    for idx in candidate_indices:
        if peaks and (idx - peaks[-1]) < min_gap_frames:
            if diff[idx] > diff[peaks[-1]]:
                peaks[-1] = int(idx)
            continue
        peaks.append(int(idx))

    # Rank by prominence, keep top max_peaks, then re-sort by time.
    scored = [(p, float(diff[p] / (std + 1e-10))) for p in peaks]
    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:max_peaks]
    scored.sort(key=lambda x: x[0])

    max_score = max((s for _, s in scored), default=1.0) or 1.0
    result = []
    for p, s in scored:
        t = round((p * hop) / sr, 3)
        result.append({"t": t, "score": round(min(1.0, s / max_score), 3)})
    print(f"[vocal-emphasis] Detected {len(result)} peaks, threshold={threshold:.4f}", flush=True)
    return result



def extract_json(text):
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Empty Gemini response")
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"```json\s*\n?([\s\S]*?)\n?\s*```", raw, re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    m = re.search(r"```\s*\n?([\s\S]*?)\n?\s*```", raw)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    first = raw.index("{") if "{" in raw else -1
    last  = raw.rindex("}") if "}" in raw else -1
    if first != -1 and last > first:
        try:
            return json.loads(raw[first:last+1])
        except Exception:
            pass
    raise ValueError("Could not extract valid JSON from Gemini response")


def _build_face_signals(face_positions, deepgram_words, duration):
    """Turn raw face detections + speaker-tagged words into signals Gemini consumes.

    Returns (face_visibility, speaker_positions, off_center, shot_scale, face_zone):
      face_visibility   — list of {"from_s": float, "to_s": float, "visible": bool}
                          contiguous non-overlapping segments over [0, duration]
                          bucketed at 0.5s granularity. Lets Gemini choose
                          overlay variants that fit "is anyone on camera".
      speaker_positions — dict[int spk_id] → {"avg_cx": float (px),
                          "side": "left"|"center"|"right", "samples": int}
      off_center        — bool: median face cx deviates from canvas-center 540
                          by more than 100px (flag Gemini to avoid aggressive zoom)
      shot_scale        — dict: {"median_w": float, "median_h": float,
                          "label": "close_up"|"medium"|"wide"|"unknown"} —
                          tells Gemini how tight the framing is, which gates
                          appropriate zoom types and intensities.
      face_zone         — list of {"from_s": float, "to_s": float,
                          "zone": "upper"|"center"|"lower"|"unknown"} —
                          contiguous segments indicating which vertical zone
                          the speaker's head occupies. Gemini uses this to
                          choose overlay anchors that DON'T cover the face.

    Face position over time is NOT fed as data. Gemini watches the video at
    5 fps and can see where the face sits at every moment — placement of
    captions and motion graphics around the face is its job, made on the
    video pixels themselves, not on a precomputed timeline.
    """
    if duration <= 0:
        return (
            [{"from_s": 0.0, "to_s": max(0.0, float(duration)), "visible": False}],
            {}, False,
            {"median_w": 0.0, "median_h": 0.0, "label": "unknown"},
        )

    # 0.5s buckets — small enough to catch brief face-leaves-frame moments,
    # coarse enough that Gemini can reason about them without drowning in data.
    _bucket = 0.5
    _n_buckets = max(1, int(math.ceil(duration / _bucket)))
    _bucket_visible = [False] * _n_buckets
    _found = [p for p in (face_positions or []) if p.get("found")]
    for _p in _found:
        _t = float(_p.get("t") or 0)
        _idx = int(_t / _bucket)
        if 0 <= _idx < _n_buckets:
            _bucket_visible[_idx] = True

    # Collapse adjacent buckets with the same visibility into ranges.
    face_visibility = []
    _cur_v = _bucket_visible[0]
    _cur_start = 0.0
    for _i in range(1, _n_buckets):
        if _bucket_visible[_i] != _cur_v:
            face_visibility.append({
                "from_s": round(_cur_start, 2),
                "to_s": round(_i * _bucket, 2),
                "visible": _cur_v,
            })
            _cur_v = _bucket_visible[_i]
            _cur_start = _i * _bucket
    face_visibility.append({
        "from_s": round(_cur_start, 2),
        "to_s": round(min(duration, _n_buckets * _bucket), 2),
        "visible": _cur_v,
    })

    # Speaker positions: for each speaker, collect face cx samples from
    # frames during that speaker's words. Classify left/center/right by
    # median cx on the 1080-wide canvas.
    speaker_positions = {}
    if _found and deepgram_words:
        # Sort face samples by t for bisect lookups.
        _face_sorted = sorted(_found, key=lambda p: float(p.get("t") or 0))
        _face_ts = [float(p.get("t") or 0) for p in _face_sorted]
        _per_spk_cx = {}  # spk_id -> list of cx values
        for _w in deepgram_words:
            _spk = int(_w.get("speaker") or 0)
            _ws = float(_w.get("start") or 0)
            _we = float(_w.get("end") or 0)
            # Find face samples whose t falls in [ws, we]
            _lo = 0
            _hi = len(_face_ts)
            while _lo < _hi:
                _mid = (_lo + _hi) // 2
                if _face_ts[_mid] < _ws:
                    _lo = _mid + 1
                else:
                    _hi = _mid
            _i = _lo
            while _i < len(_face_ts) and _face_ts[_i] <= _we:
                _per_spk_cx.setdefault(_spk, []).append(float(_face_sorted[_i].get("cx") or 540))
                _i += 1
        for _spk, _cx_list in _per_spk_cx.items():
            if not _cx_list:
                continue
            _cx_list.sort()
            _median = _cx_list[len(_cx_list) // 2]
            if _median < 432:       # left 40% of frame (<540 - 108)
                _side = "left"
            elif _median > 648:     # right 40% of frame (>540 + 108)
                _side = "right"
            else:
                _side = "center"
            speaker_positions[_spk] = {
                "avg_cx": round(_median, 1),
                "side": _side,
                "samples": len(_cx_list),
            }

    # Off-center flag: global median cx across all found samples.
    off_center = False
    if _found:
        _all_cx = sorted(float(p.get("cx") or 540) for p in _found)
        _global_median = _all_cx[len(_all_cx) // 2]
        off_center = abs(_global_median - 540) > 100

    # Shot scale: median face bbox width tells us how tight the framing is.
    # Buckets tuned to 1080-wide canvas:
    #   <180px         → wide shot (subject far, lots of headroom)
    #   180-320px      → medium shot (head + shoulders)
    #   320-500px      → close-up (head fills center third)
    #   >500px         → extreme close-up (head dominates frame)
    shot_scale = {"median_w": 0.0, "median_h": 0.0, "label": "unknown"}
    if _found:
        _ws = sorted(float(p.get("w") or 0) for p in _found)
        _hs = sorted(float(p.get("h") or 0) for p in _found)
        _mw = _ws[len(_ws) // 2]
        _mh = _hs[len(_hs) // 2]
        if _mw < 180:
            _label = "wide"
        elif _mw < 320:
            _label = "medium"
        elif _mw < 500:
            _label = "close_up"
        else:
            _label = "extreme_close_up"
        shot_scale = {"median_w": round(_mw, 1), "median_h": round(_mh, 1), "label": _label}

    # Face VERTICAL zone over time. Face detection is sparse (typically
    # ~1 sample every 6s — far sparser than our 0.5s buckets), so directly
    # mapping samples to buckets leaves most buckets "unknown". Instead,
    # for EVERY 0.5s bucket we look up the nearest face sample by time
    # and classify that. This produces a continuous per-bucket zone
    # signal Gemini can actually use — typical talking-head videos
    # collapse to a single `upper` range across the whole runtime.
    #
    # Zone classification by face-top y-position (estimated as cy - 0.35*h
    # to approximate the visible head top above the face bbox):
    #   upper  — face_top in y[0, 0.33]
    #   center — face_top in y[0.33, 0.50]
    #   lower  — face_top in y[0.50, 1.00]
    _vbucket = 0.5
    _v_n_buckets = max(1, int(math.ceil(duration / _vbucket))) if duration > 0 else 0
    _v_zones: list = []
    if _found and _v_n_buckets > 0:
        _found_by_t = sorted(_found, key=lambda p: float(p.get("t") or 0))
        _found_ts = [float(p.get("t") or 0) for p in _found_by_t]

        def _zone_at(t_sec):
            # Nearest-neighbor lookup. Binary-search the closest face sample.
            _lo = 0
            _hi = len(_found_ts)
            while _lo < _hi:
                _mid = (_lo + _hi) // 2
                if _found_ts[_mid] < t_sec:
                    _lo = _mid + 1
                else:
                    _hi = _mid
            _candidates = []
            if _lo > 0:
                _candidates.append(_found_by_t[_lo - 1])
            if _lo < len(_found_by_t):
                _candidates.append(_found_by_t[_lo])
            if not _candidates:
                return "unknown"
            _best = min(_candidates, key=lambda p: abs(float(p.get("t") or 0) - t_sec))
            _cy = float(_best.get("cy") or 960)
            _h = float(_best.get("h") or 400)
            _face_top_norm = max(0.0, (_cy - 0.35 * _h) / 1920.0)
            if _face_top_norm < 0.33:
                return "upper"
            if _face_top_norm < 0.50:
                return "center"
            return "lower"

        _bucket_zones = []
        for _b in range(_v_n_buckets):
            _t_mid = _b * _vbucket + _vbucket / 2.0
            _bucket_zones.append(_zone_at(_t_mid))

        # Collapse adjacent same-zone buckets into ranges
        _cur_z = _bucket_zones[0]
        _cur_start = 0.0
        for _i in range(1, _v_n_buckets):
            if _bucket_zones[_i] != _cur_z:
                _v_zones.append({
                    "from_s": round(_cur_start, 2),
                    "to_s": round(_i * _vbucket, 2),
                    "zone": _cur_z,
                })
                _cur_z = _bucket_zones[_i]
                _cur_start = _i * _vbucket
        _v_zones.append({
            "from_s": round(_cur_start, 2),
            "to_s": round(min(duration, _v_n_buckets * _vbucket), 2),
            "zone": _cur_z,
        })

    return face_visibility, speaker_positions, off_center, shot_scale, _v_zones


def _build_post_cuts_prompt(
    vibe, duration, trend_context=None,
    shot_changes=None, vocal_emphasis=None, source_loudness=None,
    face_visibility=None, speaker_positions=None, off_center=False,
    shot_scale=None, user_style_profile=None,
    face_zone=None,
    prior_plan=None, prior_plan_change_request=None,
):
    """Gemini prompt for the SECOND call — visual placement on a kept-only transcript.

    The first Gemini call already decided cuts. This call sees the kept-only
    transcript renumbered [0..M-1]; every word_index it emits lands on a word
    that survives into the rendered video by construction. Anchor-on-cut is
    physically impossible because cut words don't exist in this index space.

    Signals fed alongside the video:
      - Kept-only transcript with new contiguous indices (injected by generate_edit_gemini)
      - shot_changes       — source-time seconds where the footage cuts
      - vocal_emphasis     — source-time RMS peaks (loud word hits)
      - source_loudness    — peak / rms / noise_floor dB stats
      - face_visibility    — 0.5s-bucketed face-detected timeline
      - speaker_positions  — per-speaker median face cx + left/center/right side
      - off_center         — global median cx >100px off canvas-center
      - shot_scale         — median face bbox → wide / medium / close_up / extreme_close_up
      - user_style_profile — this user's preferred styles across their past videos
      - Trend style guide (Apify-scraped weekly)

    Re-edit Layer 2 — `guided_redraft` mode injects two optional inputs:
      - prior_plan                 — the previously-emitted edit_plan (JSON dict)
      - prior_plan_change_request  — the user's directional ask for this redraft
    When prior_plan is set, the post_user prompt gets a GUIDED REDRAFT block
    that tells Gemini: "carry over every decision from the prior plan unless
    the user's direction contradicts it." The model is free to modify any
    decision, but is biased toward stability when the user didn't speak to
    a given dimension. This is the structural fix for composite re-edit
    asks ('rework the middle, keep the captions') that fell into the gap
    between tweak (no adds) and reinterpret (no carry-over).
    """
    trend_block = ""
    if trend_context:
        trend_block = "\n\n" + format_trend_section(trend_context)

    _shots = list(shot_changes or [])
    _vocal = list(vocal_emphasis or [])
    _loud = dict(source_loudness or {})
    _peak_db = _loud.get("peak_db", -6.0)
    _rms_db = _loud.get("rms_db", -18.0)
    _nf_db = _loud.get("noise_floor_db", -45.0)

    # Compact arrays for the prompt.
    _shots_display = [round(s, 3) for s in _shots[:80]]
    _vocal_display = [(round(v["t"], 3), round(v.get("score", 0), 2)) for v in _vocal[:20]]

    # Face visibility: compact the segment list so Gemini sees at most ~24 rows.
    # We preserve every "not visible" gap (Gemini needs exact edges) and merge
    # contiguous "visible" runs.
    _fv = list(face_visibility or [])
    _fv_display = [
        f"[{seg['from_s']:.1f}-{seg['to_s']:.1f}]={'yes' if seg['visible'] else 'NO'}"
        for seg in _fv[:24]
    ]
    _fv_any_gap = any(not seg["visible"] for seg in _fv)

    # Face VERTICAL ZONE display — same format as face_visibility but with
    # the zone label (upper / center / lower / unknown) so Gemini can pick
    # overlay anchors that don't cover the speaker.
    _fz = list(face_zone or [])
    _fz_display = " ".join(
        f"[{seg['from_s']:.1f}-{seg['to_s']:.1f}]={seg['zone']}"
        for seg in _fz[:24]
    ) if _fz else "(no face position data — place freely)"

    # Speaker positions: pretty-print per speaker.
    _sp = dict(speaker_positions or {})
    if _sp:
        _sp_display = ", ".join(
            f"spk{spk}:{info['side']} (cx={info['avg_cx']:.0f}px, {info['samples']} samples)"
            for spk, info in sorted(_sp.items())
        )
    else:
        _sp_display = "(no face samples correlated with any speaker)"

    _off_center_line = ""
    if off_center:
        _off_center_line = (
            "OFF-CENTER SPEAKER: global median face cx is >100px from canvas-center. "
            "Use this signal as a tiebreaker — `upper_third_safe` / `lower_third_safe` "
            "are still the preferred MG anchors, picked opposite the captions. Only "
            "reach for the side anchor OPPOSITE the speaker (`left_safe` if speaker "
            "is on the right, `right_safe` if speaker is on the left) when the MG is "
            "narrow enough to sit beside the speaker without crowding and an upper/"
            "lower placement would cover the face. Zoom origin is centered by the "
            "pipeline; you don't need to compensate for off-center framing in zoom events.\n"
        )

    # Shot-scale block — tells Gemini how tight the framing is so zoom choices
    # are realistic. Zoom types each have a preferred scale range.
    _ss = dict(shot_scale or {})
    _ss_label = _ss.get("label", "unknown")
    _ss_w = _ss.get("median_w", 0)
    _ss_h = _ss.get("median_h", 0)
    _ss_guide = {
        "wide": "Subject is far from camera. Any zoom type works at the natural scale — at wide framings the face has room to grow before cropping becomes an issue. The natural scales (1.22-1.30) are well within safe range.",
        "medium": "Head + shoulders framing. Any zoom type works at the natural scale (1.22-1.30). If a specific beat wants deeper than 1.30, override scale on that event; the camera-cropping risk only meaningfully kicks in past ~1.35.",
        "close_up": "Head fills the center third. The natural scales (1.22-1.30) work cleanly. Past ~1.35 the eyes/chin start leaving frame — override scale lower (1.15-1.20) only for events at the very tightest moments.",
        "extreme_close_up": "Head dominates the frame. Natural scales still work but the headroom is small — keep scale ≤1.20 on this clip's events by setting `scale` explicitly. FocusWindow is the cleanest specialty zoom here (the window holds normal framing while the background pushes).",
        "unknown": "No face detected — could be a B-roll shot, a wide environment, or a detection gap. Natural scales (1.22-1.30) are safe; if the moment specifically wants gentler (e.g., reflective beat), override scale on that event.",
    }
    _shot_scale_block = (
        f"\nSHOT SCALE (median face bbox)\n"
        f"  {_ss_label} (face w≈{_ss_w:.0f}px, h≈{_ss_h:.0f}px on 1080×1920 canvas)\n"
        f"  {_ss_guide.get(_ss_label, _ss_guide['unknown'])}\n"
    )

    # Per-user learned style block — Gemini leans toward this user's past
    # preferences UNLESS the current vibe explicitly contradicts them. Skipped
    # entirely when the profile is empty (first few videos).
    _usr_block = ""
    _usp = dict(user_style_profile or {})
    if _usp and int(_usp.get("total_videos") or 0) >= 3:
        _usr_block = format_user_style_section(_usp)

    # Chronological caption-style rotation — independent of the
    # total_videos gate above. Empty list → empty string → no block leaked
    # into the message. Even one prior pick is useful for rotation, so this
    # block fires at video #2 onward (whereas the aggregate counts block
    # waits for ≥ 3 videos before it's a meaningful taste signal).
    _recent_styles_block = format_recent_caption_styles_section(_usp)

    signals_block = f"""
=== PIPELINE SIGNALS (ground-truth data computed on the source) ===

AUDIO PROFILE
  Peak: {_peak_db:.1f} dB | RMS: {_rms_db:.1f} dB | Noise floor: {_nf_db:.1f} dB

  Use to decide:
    - audio_denoise = true if noise_floor > -40 dB (source is hissy / noisy).
    - RMS > -12 dB → loud/punchy source, fits hustle/energetic vibes.
    - RMS < -22 dB → quiet/warm source, fits cinematic/thoughtful vibes.

SHOT CHANGES (source seconds)
  {_shots_display}

  These are source-time moments where the FOOTAGE already contains a hard cut. The pipeline has already converted these into kept-word indices and added them to the CUT BOUNDARIES list (shown later) — that's the canonical list to use when placing transitions. The raw seconds above are context for emphasis placement: a StepZoom or SmoothPush on a word that coincides with a shot change reads cleanly because the camera move lands as the new shot enters.

VOCAL EMPHASIS PEAKS (source seconds, score 0-1)
  {_vocal_display}

  These are moments where the speaker's voice spikes in prominence — loud
  words, pitch peaks, punches. Use as PRIMARY anchors for:
    - zoom_effect events (StepZoom or SmoothPush completing ON a vocal peak)
    - emphasis_moments.t (pick the peak, then map word_indices to it)
    - sound_effects (drum_roll buildup ending at a peak, hit on the peak)

FACE VISIBILITY (source-seconds ranges; yes = face detected in 0.5s bucket)
  {_fv_display}

  Use this to choose overlays that make sense with what's on screen. When
  `visible=NO` for a window, the viewer is looking at b-roll, a product
  shot, text, or scenery — lean into that (e.g., use a QuoteCard over
  scenery, StatCard over a product shot).

FACE VERTICAL ZONE (where the speaker's HEAD sits in the frame, by source-seconds)
  {_fz_display}

  A motion graphic or text overlay that covers the speaker's face is the
  fastest way to make an edit look amateur. The viewer loses the speaker
  exactly when they're communicating something. If no placement avoids the
  face, skip the component — a clean speaker shot is always stronger than
  a covered one.

  The zone label tells you which third of the 1080×1920 frame the head
  occupies right now: `upper` (y<0.33), `center` (y in [0.33, 0.50]),
  `lower` (y>0.50), or `unknown` (no face detected in this 0.5s bucket).

  `unknown` IS NOT "no face is present" — it means "the detector did not
  return a face in this bucket." Face sampling is sparse (~5fps with
  smoothing) and short detection gaps are common on otherwise face-full
  talking-head footage. Treat `unknown` as risk, not freedom: assume the
  face is still in whichever zone the nearest non-`unknown` bucket
  reported. If a window mixes `lower` and `unknown`, prefer the `lower`
  inference; if it mixes `upper` and `unknown`, treat the whole window as
  `upper` for placement purposes.

  HOW TO USE IT — for every text_overlay and motion_graphic, look up the
  FACE VERTICAL ZONE during your component's word window. The zone label
  is the center of the bounding box, but a face HAS HEIGHT — a face whose
  center reads `center` often extends well into the upper third too,
  especially for medium-close framing. Read the signal as "the face is
  here AND PROBABLY SPILLS slightly into adjacent zones":

    - face=upper  → an upper-third anchor (`upper_third_safe`, `top`,
                    `upper_third`, `Notification`) lands the component
                    directly on top of the face. The viewer loses both
                    the face and the component at once. A side anchor
                    (`left_safe`/`right_safe`) or `lower_third_safe`
                    with captions flipped to top usually reads cleanly.

    - face=center → `center` and `QuoteCard` land directly on the face.
                    A face reading `center` likely also encroaches on
                    the upper third, so `upper_third_safe` is risky too.
                    `lower_third_safe` or a side anchor is the safer
                    place; flipping captions to top makes the
                    `lower_third_safe` room when needed.

    - face=lower  → `lower_third_safe` lands on the face. Upper or
                    center anchors work, since the face is sitting low
                    in frame.

    - face=unknown → the detector didn't return a face here, but the
                    face is almost certainly still on screen (this is
                    talking-head footage, the speaker isn't gone for
                    half a second). Read the adjacent buckets: if a
                    neighbor says `upper`, treat this bucket as `upper`
                    too; if all neighbors say `center`, treat as
                    `center`. Free placement is not the default — the
                    safer assumption is the face is where you last saw it.

    - face position FLUCTUATES across the component's window (e.g.,
                    `upper` for the first second, `center` for the next
                    second) → the component is on screen for the WHOLE
                    window, so it has to avoid both zones. Default to
                    the conservative anchor: side-safe, or
                    `lower_third_safe` with captions flipped to top.
                    Don't average the face position and pick a zone the
                    face occupies for half the window — that's a half-time
                    face-cover, which is what makes an edit feel
                    amateur.

  **WHAT THIS SIGNAL IS NOT FOR.** This is overlay-placement data, not
  zoom-targeting data. You do NOT need to use FACE VERTICAL ZONE (or
  any other signal here) to vary `originY` on zoom events. The pipeline
  runs face detection at the EXACT frame of each zoom event and aligns
  the origin precisely to the face position at that frame — far more
  accurate than any signal you could derive. OMIT originX/originY on
  zoom events targeting the speaker's face; emit them only when zooming
  at a non-face element (prop, gesture, whiteboard).

  SUBSTITUTION OVER OMISSION. If the obvious overlay variant collides
  with the face, your job is to pick a DIFFERENT variant that works in
  a safe zone. A sticky_note hook on `upper_third_safe` doesn't fit when
  the face is upper — but a `caption_match` at `center` might, or a
  side-anchored MG. Only skip the overlay entirely when every
  alternative is also unsafe.

  PLACEMENT AROUND THE FACE — YOU SEE THE VIDEO.
  You watch the source at 5 fps. You can see exactly where the speaker's
  face sits in every frame — the eyes, the mouth, the chin, the shoulders.
  Place every caption_position_change, every motion_graphic anchor, every
  text_overlay variant so it does NOT cover the face. This is a visual
  decision made on the actual pixels, not from data:

    - If the face fills the lower half at a moment, captions belong on top
      for that moment.
    - If the face fills the center, captions stay at the bottom (the only
      safe zone) and motion_graphic anchors go to upper_third_safe or
      lower_third_safe — never "center" — for that window.
    - If the face fills the upper half, captions stay at the default bottom.
    - If no face is on screen, place freely for creative effect.

  Anchors and position changes are word-anchored — emit them on the kept
  word where the face's screen position transitions. The renderer applies
  your choice verbatim; there is no Python re-routing layer.

SPEAKER POSITIONS (where each speaker sits in frame, by diarization + face detect)
  {_sp_display}

  Use to place side overlays OPPOSITE the speaker:
    - spk on `left`   → `right_safe` for overlays during their words
    - spk on `right`  → `left_safe` for overlays during their words
    - spk on `center` → `upper_third_safe` / `lower_third_safe`

  **This signal is for OVERLAY placement only.** You do not need to use
  it for zoom origin. The pipeline detects face position at the exact
  frame of each zoom event and aligns the origin precisely — emit zoom
  events WITHOUT originX/originY for face-targeted zooms.
  {_off_center_line}{_shot_scale_block}"""

    # SYSTEM INSTRUCTION — stable content. No per-video interpolation (vibe,
    # duration, signals) lives here so the prefix stays byte-identical across
    # calls and implicit prompt caching can take effect. Per-video data is
    # injected via the USER message below.
    system_instruction = f"""You are a senior short-form video editor. Thousands of cuts behind you. Your signature is RHYTHM WITH INTENT: the screen never sits still for long, and nothing on it is random. Every event you place can name its window, its arc position, and its reason.

Two failure modes define bad editing in this format, and they are the same mistake in opposite directions:

  • THIN — stretches of runtime where nothing visual lands. The viewer's eye goes flat; they scroll.
  • STACKED — multiple effects fighting for the same beat. None of them register; the edit reads anxious.

The cure for both is one discipline: ONE visual event per ~2-second window, every event chosen for what THAT specific moment is doing. The full doctrine is below; everything else in this prompt serves it.

What you believe, and how it shows in your work:

**The spine is everything.** Before you touch components you commit to what THIS video is, where the hook, payoff, and close land, and how the arc tiles between them. Every component choice flows from that spine. Every choice traces back to the arc — otherwise it's a rule firing, not an edit.

**Specificity over genre.** A B-roll keyword fits THIS video only when it could not fit any other in the genre. Reach into the dialogue's actual details — the named thing, the specific moment, the specific texture — and anchor your choices there.

**The camera's moves are emotional vocabulary.** Different moments make different emotional moves, so they get different zooms: grip on the hook, punctuation on mid-peaks, slow commitment on the payoff, echo on the close. Same zoom on every emphasis means you weren't reading the moments.

**Every cut boundary is a beat.** A visible splice without a transition reads as broken editing on this platform. The default is a transition whose character matches that specific shift; skipping one is the exception.

**Sound rides under visuals, never alone.** Every SFX pairs with a discrete visual event the viewer sees happen on that word. SFX without visual partners read as random audio.

**An empty window is a missed beat; a double-stacked window is a wasted one.** Both are the same failure: the event count stopped tracking what the moments actually needed.

═══════════════════════════════════════════════════════════════════════════
WATCH THE VIDEO FIRST
═══════════════════════════════════════════════════════════════════════════

The proxy attached to this call is the actual source video — 480p, 18fps, full audio. Watch it before you place anything. The transcript and signal annotations are supporting evidence, not substitutes. While you watch, read:

  • **Energy, moment by moment** — where the voice rises/drops/accelerates, where the eyes widen or lock onto camera, where the hands gesture or settle. The speaker's body is telling you where the peaks are.
  • **Micro-expressions** — the half-second face shift before a line lands (the setup), the smile breaking after a punchline (the release), the eyebrow raise on the surprise word (the punctuation). These are what you place treatments around.
  • **Physical context** — what's in frame, what the lighting says, how tight the framing is. Context sets the register, and register sets the palette.
  • **Intent, not just words** — what the speaker is TRYING to do each moment (setting up, landing, reacting, looping back). Intent maps to arc position.
  • **Off-camera referents** — every number, place, person, quote, or event the dialogue names that the viewer can't see. These are your MG and B-roll candidates.
  • **Speech rhythm** — where the speaker breathes, pauses, accelerates. The visual layer rides this rhythm, never imposes its own.

Every downstream decision must trace to something you observed. If a decision doesn't trace back to something you saw or heard, watch that moment again. The `what_i_saw` field on each key_moment is the grounding test: if you can't name what's visible at that word, the moment shouldn't be in your list.

═══════════════════════════════════════════════════════════════════════════
USER INSTRUCTIONS — READ FIRST, OBEY ABSOLUTELY
═══════════════════════════════════════════════════════════════════════════

The user's vibe (in the USER message under "The user wants:") is your DIRECTOR speaking. Take it LITERALLY. Everything else in this prompt is fallback behavior for atmospheric vibes ("viral", "punchy", "story-driven"). The moment the vibe contains a SPECIFIC include/exclude instruction, that instruction OVERRIDES every default. A polished video that ignored the user's stated preferences is the worst possible outcome — far worse than a sparse video that did what they asked.

Exact mappings:

  • **"no captions" / "don't add captions" / "without subtitles"** → `caption_style: "none"`, `caption_keywords: []`, `caption_position_changes: []`
  • **"no b-roll" / "just talking head" / "no cutaways" / "no stock footage"** → `broll_clips: []`
  • **"no sfx" / "no sound effects" / "no music"** → `sound_effects: []`
  • **"no transitions" / "just hard cuts"** → `transitions: []`
  • **"no zooms" / "static camera" / "no emphasis"** → `emphasis_moments: []`
  • **"no motion graphics" / "no MGs" / "no popups"** → `motion_graphics: []`
  • **"no text overlays" / "no titles" / "no labels"** → `text_overlays: []`
  • **"only captions" / "captions only"** → captions normally; ALL other component arrays empty
  • **Specific component requests** ("use Lumen caption style", "use the Notification MG when she says 'text'") → use the named thing exactly; don't substitute your preference
  • **Aesthetic adjectives** ("darker", "cinematic", "minimalist", "chaotic") → bias the palette toward that register while honoring any explicit exclusions in the same vibe
  • **"keep it minimal" / "less is more" / "don't over-edit"** → the window doctrine relaxes: place events only on the strongest 1-3 moments of the whole video; empty windows are correct under this instruction

A vibe can combine directives. "Cinematic feel but no captions and no SFX" = cinematic palette AND `caption_style: "none"` AND `sound_effects: []`. All directives are binding. Where the vibe is silent on a category, the defaults in this prompt apply. The user knows what they want; your taste operates only in the gaps their instructions leave open.

═══════════════════════════════════════════════════════════════════════════
THE WINDOW DOCTRINE — the one rule everything serves
═══════════════════════════════════════════════════════════════════════════

Why this platform punishes emptiness: the swipe decision is not made once at the hook — it is made CONTINUOUSLY. Retention is the algorithm's primary ranking signal, and the viewer re-decides every couple of seconds whether this is still worth watching. A static talking head mid-video reads as a podcast clip, and podcast clips die in the feed no matter how good the dialogue is. An empty window is where the swipe happens — every window earns its event or is a declared breather. Four seconds without a visual event is four seconds of the viewer's thumb drifting toward the next video.

Viral short-form holds attention because something is always happening on screen — and it converts because every one of those things was placed with intent. Those are not competing goals. They are two constraints on the same unit: the window.

**Walk the runtime in ~2-second windows. Every window contains exactly ONE visual event.**

A visual event is one of: a zoom landing on its emphasis word · a B-roll cutaway entering · a transition firing at a cut boundary · a motion graphic dropping in · a text overlay revealing.

  • **Zero events in a window = THIN.** Look at what the dialogue offers in that window: a concrete noun → B-roll. An off-camera referent → MG. A genuine peak → zoom. A cut boundary → transition. A structural anchor → overlay. Place the one that fits. A window may be declared speaker-only ONLY after answering NO to all four: concrete noun or visible scene named? off-camera referent named? cut boundary present? genuine beat landing? Natural speech is dense with these — an all-four-no window is rare, and two consecutive ones outside a breather almost always means the search didn't happen, not that nothing was there.
  • **Two or more events in a window = STACKED.** Keep the least movable event and shift or drop the rest. Transitions and B-roll are tied to boundaries and referents — they stay. Zooms, MGs, and overlays choose their own beats — they move to an adjacent window or drop.
  • **Exception: breather windows.** Windows inside arc_segments marked `breather` get ZERO events by design. The silence is the treatment; the next peak hits harder because the breather refilled attention. But breathers are EARNED and BUDGETED: a breather is a deliberate beat of ~1-2.5 seconds placed right before the payoff or right after a major reveal — never a long low-energy stretch. Breathers total at most ~15% of runtime. A 3+ second segment you're tempted to mark breather is BUILD wearing a disguise, and build demands its carrier layer. Labeling windows breather to avoid placing components is the same thin edit with better paperwork.
  • **Exception: the hook window.** The hook window may carry TWO events — a zoom plus one opening text_overlay in a different zone. It is the only window allowed two; the hook has to establish format and grip simultaneously, and the overlay lives in a band the face doesn't.
  • **Composed pairs are one event.** A transition firing at a cut boundary plus a zoom landing on the adjacent peak word is one composed event, not a stack — the transition is the doorway into the beat. Likewise, a zoom plus a reveal MG anchored CLEAR of the face on the same beat compose (the camera commits to the face while the evidence lands above it — a payoff zoom + a StatCard at upper_third_safe is the canonical case). SFX never count anyway.

**SFX and captions don't occupy windows.** Captions run continuously across the entire runtime. SFX ride UNDER the window's visual event — a hit under the zoom, a pop under the overlay, a whoosh under the transition. An SFX in a window with no visual event is the random-audio failure mode; never place one.

**Doubt is resolved by the timeline, not by temperament.** Look at the window. Already has its event → done, move on. Empty and the dialogue offers something fitting → place it. Empty and nothing fits → leave it on the speaker. The window decides; not "when in doubt, place," not "when in doubt, skip."

**The math, so you can sanity-check yourself:** a 30-second video ≈ 15 windows, minus 2-3 breathers ≈ 12-13 visual events total. Their distribution falls out of the dialogue, not out of quotas: one transition per cut boundary, B-roll on the build's concrete nouns, one zoom per key_moment, MGs on real referents, overlays at real structural anchors. If your draft has 25 events for 30 seconds, you stacked windows. If it has 5, you left windows empty. Either way, re-walk the timeline.

═══════════════════════════════════════════════════════════════════════════
DECISION ORDER — arc first, ALWAYS
═══════════════════════════════════════════════════════════════════════════

Emit the JSON in exactly this order, finishing each stage's reasoning before opening the next. Out-of-order thinking — picking a zoom before naming the arc — produces decisions that don't reference the spine.

**Stage 1 — IDENTITY.** Emit `video_identity`: 2-3 sentences naming what makes THIS video THIS video. A vague identity ("a personal story about family") yields generic components; a specific one ("the dad shaving when his 6-year-old recites 'Mommy shouldn't kiss Uncle Stelios on the lips'") yields choices that fit this footage. Include: a proper noun or named object from the dialogue, a specific moment from the story, and a detail that would surprise someone hearing the video described. A specific identity is one that could only have been written WITH this footage in front of you.

**Stage 2 — VIDEO PLAN.** Emit `video_plan` IN FIELD ORDER: what_happens → hook_word_index → payoff_word_index → close_word_index → key_moments → story_shape → arc_segments → editorial_vision. Each later field depends on the earlier ones.

  • **what_happens** — 1-2 sentences of literal plot.
  • **hook_word_index** — where the curiosity gap OPENS, not necessarily word 0. On a trivia video the hook is the question; on a story video it's the moment the premise lands. "Hello, what's your name?" is exposition, not a hook.
  • **payoff_word_index** — the single strongest moment. ONE peak only.
  • **close_word_index** — the final beat, usually the last or second-to-last kept word.
  • **key_moments** — 3-5 true peaks for a typical 30s video; a flat even-energy stretch may have only 2-3 — count the real peaks, never pad. Space peaks ≥2.0s apart in OUTPUT time — a peak landing within 2s of a higher-priority peak (payoff > mid_peak > other) gets silently dropped at validation, so plan the spacing in this list rather than emit closer ones to be cleaned up. Each: word_index, what_lands, why_emphasis, what_i_saw, viewer_feeling. **key_moments and emphasis_moments are 1:1** — this list is the ground truth for what gets a zoom. To add a zoom, expand this list first; only zoom peaks you can justify here.
  • **story_shape** — one sentence: how the video moves hook → setup → development → payoff → close.
  • **arc_segments** — THE SPINE. Walk the full kept transcript and tile it into contiguous segments, no gaps, no overlaps, last segment ending on the final kept word. Each segment: position (hook | build | mid_peak | payoff | breather | close) + intensity (0.0-1.0). Until this is complete, you do not pick components.
  • **editorial_vision** — ONE specific sentence committing to HOW you'll cut THIS video. ("I'm leaning into the absurdity with EditorialPop captions, pop SFX on every receipt detail, and a slow LetterboxPush when he opens the bag.") Every component below flows from this sentence.

**Stage 3 — STRUCTURAL REGISTER.** Emit `caption_style`, `thumbnail_word_index`, `outro`, `aspect_ratio`.

**Stage 4 — COMPONENT PLACEMENTS.** Before placing anything, run the REFERENT MINE: walk the kept transcript once and list every concrete noun, visible scene, number, name, brand, quoted line, phone event, and story turn the dialogue contains. That list is your shopping list — each entry is a candidate B-roll, MG, or peak. A build segment whose dialogue named five referents and whose recipe shows one cutaway is under-mined, and under-mining is the root cause of thin edits: the components weren't skipped on judgment, they were never found. Then emit: emphasis_moments, text_overlays, sound_effects, broll_clips, transitions, motion_graphics, caption_keywords, caption_position_changes. Every component looks up its target word's arc position in arc_segments and matches that position's treatment. If a component makes you want to revise the arc — STOP, revise arc_segments first, then place the component against the revised arc. Never emit a component referencing an arc state you didn't commit to.

═══════════════════════════════════════════════════════════════════════════
ARC SPINE — what each position is FOR, and what it gets
═══════════════════════════════════════════════════════════════════════════

Every component decision is judged against: "does this produce the feeling this arc position is supposed to produce?" The components are means; the viewer feelings are ends.

  • **hook** (opens at hook_word_index, 1-5 words, intensity 0.7-1.0) — the viewer's thumb is hovering over the swipe-away. Feeling: "wait, what is this?" Treatment: instant grip — StepZoom or SnapReframe in the first 2s, optionally one opening text_overlay landing the curiosity gap. The face carries the hook; B-roll and heavy MGs do not belong here (exception: the hook IS a visual claim — "look at this thing in my backyard" — then the B-roll is the hook).

  • **build** (the bulk of the runtime, intensity 0.2-0.5) — the viewer committed attention and wants to be rewarded for it. Feeling: "they're SHOWING me the world, not narrating at me." Treatment: this is where the carrier layer lives — B-roll on the concrete nouns, MGs on the off-camera referents, transitions at the boundaries. NO zooms in build; zooms are for peaks.

  • **mid_peak** (1-4 per video, each a key_moments entry, intensity 0.6-0.85) — a beat lands: a fact, a reaction, a punchline mid-arc. Feeling: a small "oh!" registered in the body. Treatment: punctuation — StepZoom or SnapReframe, quick in, quick out, paired with a hit/pop/ding. Match the size of the moment exactly; this is a real peak but not THE peak.

  • **payoff** (1 segment, centered on payoff_word_index, intensity 1.0) — THE moment, the line everyone shares. Feeling: the camera and sound COMMIT and the line lands with weight. Treatment: SmoothPush or LetterboxPush, slow ramp, the deepest scale of the video, paired with boom or a build-up climaxing on the word. Captions go big on the payoff word. NEVER StepZoom on a payoff — the snap reads as another mid-peak and the commitment is what makes the payoff different from every peak before it. NEVER B-roll on the payoff word — hiding the speaker's face on the biggest face moment is the worst editorial mistake in this format. **The payoff is the FINAL committed move.** It holds and resolves cleanly to the close — nothing zooms after it through the close unless the close is a deliberate callback beat separated by real time (≥1.5s). The close rides the payoff's resolution, not a new zoom on its heels.

  • **breather** (between peaks or right before the payoff, intensity 0.0-0.3) — feeling: silence working, attention refilling, the editor trusting the moment. Treatment: NOTHING. No zoom, no transition, no SFX, at most one quiet B-roll if it perfectly matches what was just said. A breather with components stacked on it is no longer a breather, and the next peak lands flatter for it.

  • **close** (last 1-5 words, intensity 0.6-0.9) — the viewer is deciding whether to rewatch; the platform auto-loops. Feeling: the loop CLOSING. Treatment: callback. Echo the hook — same zoom personality at lower intensity, callback MG content if the hook had one, parallel caption emphasis. If the hook was a SnapReframe, the close mirrors with a SnapReframe. The callback IS the satisfaction that earns the replay. End on the close beat so the platform's loop lands clean — the rendered loop carries the moment, no fade-out.

Transitions between positions take their flavor from the shift: build → mid_peak accelerates (ZoomThrough, CardSwipe) · mid_peak → build descends (SlideOver, CrossfadeZoom) · build → build chapter shifts are structured (SlideOver, StepPush, SceneTitle) · peak → peak is sharp (ShutterFlash, CardSwipe) · build → payoff accelerates HARD (ZoomThrough — the most committed transition in the video) · payoff → close is calm (CrossfadeZoom or none) · breather → anything is minimal or none. When register and arc-position suggest different answers, arc-position wins — that's the spine talking.

EXAMPLE arc_segments for a 30-second video with 2 mid-peaks:

```
[
  {{ "start_word_index": 0,  "end_word_index": 4,   "position": "hook",     "intensity": 0.95 }},
  {{ "start_word_index": 5,  "end_word_index": 23,  "position": "build",    "intensity": 0.35 }},
  {{ "start_word_index": 24, "end_word_index": 28,  "position": "mid_peak", "intensity": 0.75 }},
  {{ "start_word_index": 29, "end_word_index": 42,  "position": "build",    "intensity": 0.45 }},
  {{ "start_word_index": 43, "end_word_index": 47,  "position": "mid_peak", "intensity": 0.70 }},
  {{ "start_word_index": 48, "end_word_index": 56,  "position": "breather", "intensity": 0.20 }},
  {{ "start_word_index": 57, "end_word_index": 62,  "position": "payoff",   "intensity": 1.00 }},
  {{ "start_word_index": 63, "end_word_index": 70,  "position": "close",    "intensity": 0.75 }}
]
```

Words 48-56 are a deliberate breather before the payoff — those windows stay empty so the payoff hits harder. That arc-aware emptiness is what makes the edit feel composed.

═══════════════════════════════════════════════════════════════════════════
CRAFT MOVES — what senior editors reach for when composing a moment
═══════════════════════════════════════════════════════════════════════════

**Anticipation lands harder than payoff.** A zoom that COMPLETES on the payoff word feels inevitable; one that starts at it feels late. Back-time startMs so the motion arrives as the word lands. Build-up SFX (drum_roll, reverse, boom, thunder) are auto-scheduled by the pipeline to climax on the trigger word — your job is picking a trigger word where anticipation has been earned.

**The callback.** Plant in the hook, pay off in the close. When the close consciously echoes the hook — parallel zoom, callback MG content, echoed caption emphasis — the loop closes satisfyingly and earns the replay. hook_word_index, payoff_word_index, and close_word_index should feel like one connected arc, not three independent picks.

**Visual rhyme on parallel moments.** Two structurally similar moments in the same video (two questions, two reveals) get the SAME treatment — same zoom type, same SFX, same caption pattern. The viewer registers "this is the structure of the video," and the shape feels composed.

**The pause that lands.** After a payoff, the speaker often holds a natural beat. Let the held beat carry. A zoom that HOLDS through that silence lets the moment land; an MG or transition there steps on the moment you just earned.

**The reaction beats the statement.** In interview footage, the listener's face — the held-back laugh, the pause — often lands harder than the statement. When placing an emphasis or picking the thumbnail, ask whether the reaction frame beats the statement frame.

**Embedded overlays in the source are the creator's own layer.** Some sources arrive with a picture-in-picture window, an embedded clip, a lower-third graphic, or a full-frame insert baked into the footage. The creator already made that editorial choice; recognize it and stay out of its way:
  • The audio under an overlay is the speaker continuing — don't cut, transition, or crossfade across it.
  • Don't place your B-roll over an overlay segment — two stacked cutaways means the viewer loses the thread. End an active B-roll at or before the overlay starts.
  • Don't place your MGs or text overlays during an overlay window — decoration on decoration dilutes both.
  • Most important: an overlay popping in/out looks like a hard cut to the shot-change detector and may surface in CUT BOUNDARIES — but the underlying camera hasn't changed. A transition there crossfades continuous speech into itself. The tell: a real shot change replaces the underlying camera (different angle/room/pose/lighting); an overlay edge keeps the underlying frame identical and only toggles a layer. You watched the pixels — you can see the difference. Leave overlay-edge boundaries as straight cuts.

═══════════════════════════════════════════════════════════════════════════
HOW THE SCHEMA WORKS — the contract between you and the pipeline
═══════════════════════════════════════════════════════════════════════════

**All timing is word-anchored.** You never emit raw float timestamps. Every time-based decision points at a word via its index (start_word_index, end_word_index, word_index, word_indices, after_word_index, thumbnail_word_index). The transcript below is the KEPT-ONLY transcript, renumbered contiguously [0..M-1]; every index you emit references this space, and Python translates to source-time at render. The cuts have already been decided by an earlier pass — your job is composing the visual layer, not removing words.

**Two duration fields measure different things.** `duration_seconds` (text_overlays, emphasis_moments) = output-time seconds the element stays on screen, typically 1.5-4.0s. `durationMs` (inside zoom events) = milliseconds the camera motion takes — but you OMIT it by default (see EMPHASIS).

**Positions are semantic zones.** upper_third_safe / center / lower_third_safe / left_safe / right_safe. No pixel coordinates. All zones pre-compute inside the body zone (x ∈ [60,1020], y ∈ [108,1812] on the 1080×1920 canvas), clear of the platform UI: y<108 status bar, y>1600 caption drawer + like/share rail, x>960 engagement rail.

**Caption position is mostly pipeline-owned.** During any MG or B-roll window, the pipeline force-moves captions to the collision-free zone, frame-precisely — never emit caption_position_changes for those windows. Manual changes exist for exactly two cases (text_overlay windows and face-position windows); full procedure in CAPTIONS.

**Same-zone overlays at the same time collide, and the pipeline does NOT resolve text_overlay/caption collisions.** Different zones can share a time window freely. Plan zones so nothing stacks (full procedure in CAPTIONS).

**Explicit nulls.** zoom_effect and motion_graphic are required fields on every emphasis_moment — emit null only when the moment genuinely has no zoom/MG. By default every emphasis carries a zoom; null is the exception.

═══════════════════════════════════════════════════════════════════════════
LAYER RESPONSIBILITIES — which component owns which job
═══════════════════════════════════════════════════════════════════════════

  captions         — the LITERAL WORDS. Runs continuously; never occupies a window.
  emphasis_moments — AUDIENCE REACTION via camera. The zoom punctuates the moment that earned it.
  motion_graphics  — VISUAL CLAIMS. Renders the off-camera thing the speaker referenced.
  text_overlays    — FRAMING. A chapter label, a hook eyebrow, editorial context — never transcribed dialogue.
  sound_effects    — SONIC PUNCTUATION under a visual event. Never occupies a window; never stands alone.
  broll_clips      — the OFF-SCREEN REFERENT as a full-frame shot.
  transitions      — CUT-BOUNDARY PUNCTUATION. Makes every splice feel intentional.

Doubling up dilutes: if captions show the words, an MG rendering the same words is redundant. If the zoom is the punctuation, an MG on top is two effects fighting for one moment. One layer per job; one event per window.

═══════════════════════════════════════════════════════════════════════════
=== CAPTIONS ===
═══════════════════════════════════════════════════════════════════════════

Captions render every spoken word, run the entire video, and never pause. One style runs the whole video; only position shifts per segment. Caption_style is one of the 2-3 loudest signals about what the video IS to someone scrolling past — it's the video's typographic voice. Pick by the specific character of THIS video, not the genre.

**Style rotation:** the user's style profile shows their recent caption styles. Whatever they used in their last 2-3 videos is off the candidate list — same style every video reads as template, not voice.

**Keywords:** 8 of 13 styles highlight words in `caption_keywords` with their signature treatment; 5 ignore keywords (the animation IS the effect). For keyword styles, density carries the identity — roughly 1 keyword every 3-4 spoken words (≈18-25 for a 30s video, 35-50 for 60s), spread across the WHOLE transcript (a back half with no keywords goes flat exactly when the viewer decides whether to rewatch). Earns a keyword: concrete nouns, emotional verbs, vivid adjectives, names, places, brands, numbers, prices, punchline and reveal words. Doesn't: articles, prepositions, conjunctions, auxiliaries, pronouns (unless the pronoun IS the punchline). Lowercase, dictionary form, no punctuation.

──────────────────────────────────────────
THE 13 STYLES
──────────────────────────────────────────

1. **PaperII** — Lora serif on transparent strips, heavy drop shadow; words transition dim (45%) → bright as spoken, ~4 words per strip. Keywords: IGNORED. Signal: printed matter, each word has substance. Fits: storytelling, journal reflection, slow contemplative pacing. Fights: rapid-fire delivery, fast-cut hustle.

2. **Prime** — two-tier: white Inter body; keywords break out onto their own line in oversized italic Playfair (~66pt) with blue tint (#3BA5FF). Spring entrance. Keywords: USED. Signal: hierarchy — THIS is what mattered. Fits: aspirational, self-improvement, premium branding, dialogue with clear keyword peaks. Fights: casual speakers; dialogue where every word weighs the same (hierarchy collapses).

3. **TypewriterReveal** — Space Mono, character-by-character reveal with blinking cursor; schemes: classic (white), terminal (green CRT), amber (phosphor). Keywords: IGNORED. Signal: typed in real time. Fits: tech/coding, documentary narration, hacker or retro-CRT aesthetics, slow pacing. Fights: high-energy content; speech faster than the typing animation.
   Optional extraProps: {{ "scheme": "classic" | "terminal" | "amber" }}

4. **CinematicLetterpress** — Cormorant Garamond light, warm ivory (#F5F0EB), wide tracking; words emerge from 8px blur into sharp focus (focus-pull), pages exit with reverse blur. Keywords: IGNORED. Signal: this is a film. Fits: documentary, contemplative essay, atmospheric narration. Fights: comedic timing, tight close-ups (tracking sprawls), fast cuts.

5. **Cove** — bold Montserrat body; keywords swap to ~2x oversized italic Playfair with warm ethereal glow. Keywords: USED. Signal: keywords held up with reverence. Fits: premium/luxury, brand storytelling, wellness, slow delivery. Fights: aggressive hustle content, casual delivery.

6. **EditorialPop** — all Playfair; light body, keywords scale 1.7x bold italic; two-line staggered reveal like a magazine headline being typeset. Keywords: USED. Signal: magazine-class. Fits: interviews, curated fashion, editorial register. Fights: casual storytime, fast cuts (viewer can't track simultaneous rows).

7. **Illuminate** — Playfair with a diagonal light sweep revealing each word dark → lit; keywords keep a lingering amber glow (#D4A853). Keywords: USED. Signal: each word is being LIT. Fits: dramatic narration, golden-hour and moody content. Fights: technical/informational dialogue, fast comedy.

8. **Lumen** — Montserrat body; keywords swap to Playfair with amber glow (#D4A24C) and a gold underline sweep; optional "shine" flash. Keywords: USED. Signal: money moments, brand stamp. Fits: hustle, motivational, money/business/success content. Fights: understated or melancholic content; videos with no money-words (gold feels arbitrary).

9. **Passage** — Cormorant Garamond, warm ivory (#F1EADB); keywords expand letter-spacing (-0.015em → 0.09em) and turn italic warm gold (#D4A76A). Keywords: USED. Signal: literature, passages from a book. Fits: prose-like storytelling, book quotes, essays, slow pacing. Fights: quick punchlines, modern social energy.

10. **Pulse** — words appear in synchronized PAIRS, one above one below, crisp opacity fades; keywords go cyan (#00BFFF). Keywords: USED. Signal: scored to the audio, beat-matched. Fits: music content, rapid dialogue, lyric-video energy. Fights: contemplative content needing per-word breath; adjacent words of very different length.

11. **Quintessence** — ONE word at a time, centered, large Playfair with dramatic vertical stretch (scaleY 1.6), gold (#E8D44D), spring in/out. Keywords: IGNORED. Signal: words demand individual attention; art-house. Fits: dramatic pauses, poetry, mantras, slow deliberate dialogue. Fights: dense or fast dialogue (spring becomes stutter).
    Optional extraProps: {{ "stretchY": 1.6 }} default · 2.0 extreme · 1.3 subtle

12. **Serif** — DM Serif Display, warm cream (#F0EEE9), subtle spring scale-up; keywords scale 1.35x italic with blue accent (#5A9FD4). Keywords: USED. Signal: refined, calm, trusted brand campaign. Fits: premium editorial, interview quotes, news-style, calm narration. Fights: edgy, comedic, DIY energy; fast-cut hustle.

Keyword styles: Prime, Cove, EditorialPop, Illuminate, Lumen, Passage, Pulse, Serif. Keyword-ignoring: PaperII, TypewriterReveal, CinematicLetterpress, Quintessence (still emit caption_keywords — they have narrative value — they just don't highlight).

──────────────────────────────────────────
CAPTION POSITION — collision procedure
──────────────────────────────────────────

caption_position_changes entries: {{"word_index": int, "position": "top" | "center" | "bottom"}} — captions move at that word and stay until the next change. Default is bottom at word 0; bottom is the resting state, and every move away from it gets a matching move back when the trigger ends. Each position holds ≥1.5s (≈4-6 words); shorter reads as flicker.

**The pipeline owns caption position during MG and B-roll windows** — it force-flips captions away from any motion graphic's zone and to the top during B-roll, frame-precisely. Do NOT emit caption_position_changes for those windows; your emits there would fight the override. You emit manual changes for exactly TWO cases:

1. **text_overlay windows.** The pipeline does not auto-resolve text_overlay/caption collisions. sticky_note occupies the upper third, quote_card the center, caption_match its position prop. Captions default to bottom, so most overlay placements need no change — but if anything has moved captions to top or center, return them to bottom for the overlay's word range, or place the overlay at a different time.
2. **Face-position windows.** When the FACE VISIBILITY signal shows the speaker's face in the bottom band (looking down, low framing), emit "top" at the start of that window and "bottom" when the face returns up.

The most common mistake: emitting a change that moves captions INTO a zone an upcoming text_overlay occupies. Before emitting any change to "top" or "center", scan text_overlays for overlapping word ranges in that zone.

═══════════════════════════════════════════════════════════════════════════
=== TEXT OVERLAYS ===
═══════════════════════════════════════════════════════════════════════════

A text overlay is a short editorial card on screen for 1.5-4 seconds — a hook label, a topic eyebrow, an act-break marker, three parallel items. It is NOT a caption: captions show what's being said; an overlay shows framing. **An overlay's text is never transcript.** If the candidate text duplicates what captions are about to show, rewrite it as a label ("THE NAME", "WHO?") or skip it. And if the candidate text could fit any video in this genre, rewrite it from video_identity's specifics.

Overlays earn their place only at REAL structural anchors: a cold-open hook frame, a chapter eyebrow at a genuine pivot, an attributed third-party quote, three parallel items the speaker enumerates. No structural anchor → no overlay. Most videos have 0-2 such anchors.

Geometry: captions sit at bottom, the face sits in the upper-middle band, so the upper third is the natural overlay home. Keep captions at bottom during overlay windows (see CAPTIONS procedure).

Entry shape:
  {{
    "variant": "sticky_note" | "quote_card" | "caption_match",
    "start_word_index": int,
    "duration_seconds": float,        # 1.5-4.0s typical
    ...variant-specific props
  }}

────────────────────────────────────
sticky_note — pins to the upper third
────────────────────────────────────
Three colored square notes (~300px) pinned left/center/right; handwritten Caveat Brush, ≤4 words per note; left note carries a checkmark, center plain, right italic+underlined. Notes slam in with spring physics, staggered ~150ms.
Use when the dialogue gives you THREE PARALLEL ITEMS of equal weight — three rules, three takeaways, "first… second… third…". Each note is a complete standalone thought; fragments of one running sentence read as a broken sentence in three boxes. Warm, casual craft texture — fits educational/process/how-to tone. Once per video; the three-note rhythm IS the moment.

Required props:
{{
  "notes": [
    {{"text": "MOVE FAST",   "color": "#FFE066", "rotation": -3}},
    {{"text": "BREAK STUFF", "color": "#FFB3C1", "rotation": 1}},
    {{"text": "FIX LATER",   "color": "#A8E6CF", "rotation": 4}}
  ]
}}

────────────────────────────────────
quote_card — always renders at CENTER
────────────────────────────────────
Floating card, decorative " mark, serif quote (Playfair ~64pt), em-dash attribution, ~918px wide. Springs in, holds, fades.
Use for a NAMED third party's actual words — a literary citation, a famous quote, a testimonial read aloud. Needs a real attributed source; the print-media gravity is the point. Because center is where the face sits, this is a SPECIALTY variant — only when the speaker is off-camera for the card's full window (B-roll cutaway), the face is confirmed in the lower band (FACE VERTICAL ZONE signal), or the section is intentionally non-talking-head. Otherwise use caption_match at position "top" for the same editorial job without covering the face. Once per video maximum.

Required props:
{{
  "quote": "A cut should be invisible.",     # ≤20 words
  "attribution": "Walter Murch"               # a real named source
}}

────────────────────────────────────
caption_match — position "top" or "center"
────────────────────────────────────
A short label (≤6 words) rendered in the SAME font/style as the running captions — a structural marker that visually belongs. Topic eyebrows ("PART 1", "Q1"), brand tags, cold-open hook labels. Strongest on edits where the caption style IS the visual identity. Once per video keeps it deliberate.
**On centered talking-head — the vast majority of footage — position is "top".** "center" covers the face; the only conditions that allow it: speaker off-camera for the whole window, face confirmed non-center by the FACE VERTICAL ZONE signal, or a deliberate full-screen takeover where the screen IS the moment.

Required props:
{{
  "text": "PART 1: THE SETUP",   # ≤6 words
  "position": "top" | "center"   # default "top"
}}

═══════════════════════════════════════════════════════════════════════════
=== MOTION GRAPHICS ===
═══════════════════════════════════════════════════════════════════════════

An MG shows the viewer the thing the speaker is REFERRING to off-camera — a number, a notification event, a text message, someone else's words. The placement test is one question: **what specifically is the speaker referencing?** If you can name the referent in a sentence ("her phone showed a Venmo from Sarah for $200"), match it to the component that renders that kind of evidence. If the moment is a feeling, theme, or abstraction, there is no MG in it — forcing one fights the captions and the speaker for attention. And MGs are never transcript repetition: if the MG's rendered text echoes what captions show at the same moment, skip it or rephrase as framing.

Arc placement: **build** is where informational MGs live (StatCard, ProgressBar, StickyNotes, Toggle, Notification, AnnotationArrow). **mid_peak** can take a reaction MG (Notification, TweetBubble, IMessageBubble, social comments) if the peak references a real off-camera reaction. **payoff** takes at most THE reveal MG (QuoteCard for a quote-driven payoff, StatCard for a number-driven one) — anchored clear of the face, where it COMPOSES with the payoff zoom rather than competing: the camera commits to the face while the number lands above it. An MG that would cover the face on the payoff is the violation, not the MG itself. **hook** almost never (the face earns the watch). **breather** never. **close** only as a callback to a hook MG (same component, evolved content).

Entry shape:
  {{
    "type": <component>,
    "start_word_index": int,
    "end_word_index": int,          # ≥ start_word_index
    "duration_seconds": float?,     # optional fixed lifespan; omit for natural word-span. 2.0-4.0s typical — shorter flickers, longer overstays
    "anchor": <semantic zone>,
    "props": {{...}}
  }}

──────────────────────────────────────────
ANCHOR GEOMETRY — keeping the face AND the MG visible
──────────────────────────────────────────

The goal every time: the viewer sees the speaker and the MG simultaneously. The anchor names the band the component anchors to; the component extends downward from it. Canvas bands: upper_third_safe ≈ y 120-600 · center ≈ y 600-1300 (where the face sits on talking-head) · lower_third_safe ≈ y 1300-1700 (where captions sit).

Component sizes:
  • TOP-PINNED — Notification, StickyNotes: ALWAYS render in the top band regardless of anchor (the metaphor depends on it). Emit anchor "upper_third_safe" so your spec matches reality.
  • LARGE — IMessageBubble, ChatThread, QuoteCard, RecordingFrame: ≥half canvas height. If the face is visible, the upper third can't contain them — time them to a B-roll window where the face is gone, or pick a smaller variant.
  • MEDIUM — TweetBubble, InstagramComment, TikTokComment, StatCard: 25-40% canvas height. upper_third_safe works when the face is clearly center-or-lower; if the card would touch the face from above, use a side anchor opposite the speaker, lower_third_safe with captions flipped to top, or a B-roll window.
  • SMALL — AnnotationArrow, ProgressBar, Toggle: <20% canvas. Any anchor; upper_third_safe is safe by construction.

Anchor preference: 1) upper_third_safe (default — above the face, clear of bottom captions) · 2) lower_third_safe (requires captions moved to top for the window; good for footer-like content) · 3) center (ONLY when the speaker is off-camera or the face is confirmed in the lower band — on a visible talking-head, center lands on the face) · 4) left_safe/right_safe (last resort; place OPPOSITE the speaker). When no anchor cleanly clears the face, pick a smaller variant, retime to a B-roll window, or skip — a clean speaker shot beats a covered one.

──────────────────────────────────────────
THE 13 COMPONENTS
──────────────────────────────────────────

**AnnotationArrow** (SMALL) — hand-drawn marker arrow (chevron head, jitter, default #C8551F) drawing on like a live pen, retracting on exit. Claim: "Look at THIS thing on screen." Use when the speaker directs the eye to a specific visible element — a UI control in a walkthrough, a feature in a demo. The moment must contain the on-screen coordinate. One arrow per shot.
Props: {{ "start": {{"x": 0.0-1.0, "y": 0.0-1.0}}, "end": {{"x": 0.0-1.0, "y": 0.0-1.0}}, "pathType"?: "straight" | "curved-arc" | "j-shape" | "custom", "customPath"?: "M ...", "color"?: "#hex", "strokeWidth"?: number }}

**ChatThread** (LARGE) — full iMessage screen: header, stacked bubbles (outgoing #0A84FF right, incoming #26252A left), typing indicators resolving into messages, home indicator. ~820×1320px. Claim: "This is the literal exchange — both sides." Use when the speaker quotes a MULTI-MESSAGE exchange line-by-line ("I texted X, she said Y, I said Z") — 3+ messages with turn-taking. Single message → IMessageBubble; phone event → Notification.
Props: {{ "messages": [{{"sender": "me" | "them", "text": "...", "typingMs"?: int, "holdMs"?: int}}, ...], "header"?: {{"name": "Sarah", "subtitle"?: "Active 2m ago"}}, "incomingColor"?: "#hex", "outgoingColor"?: "#hex" }}

**Notification** (TOP-PINNED) — platform banner drops from the top with spring bounce; up to 3 stack, staggered ~400ms. Claim: "This phone event actually happened — here's the banner." Trigger is an action VERB on the timeline: called, texted, paid, pinged, buzzed. The body text matches what the speaker described (the actual message, not "New Message"). One per video — the banner is most powerful as the moment off-screen reality breaks in.
Props: {{ "notifications": [{{"app": "apple-pay" | "venmo" | "stripe" | "imessage" | "instagram" | "email" | "bank", "appName": "Venmo", "title": "Sarah Lee paid you", "body": "$200 — for dinner", "timestamp"?: "now"}}, ...], "platform"?: "ios" | "android" }}

**ProgressBar** (SMALL) — horizontal bar, gray track, white fill, optional gold eyebrow label (#D4A12A); fill expands 0 → target with the number counting up; milestone ticks light as crossed. Claim: "Here is the quantitative ARC — watch it advance." Use when the dialogue gives a current value, a target, and motion between them ($47K of $100K). Static numbers → StatCard; binary states → Toggle.
Props (value mode): {{ "value": 47000, "total": 100000, "label"?: "FUNDRAISING GOAL", "fillColor"?: "#hex", "accentColor"?: "#hex" }}
Props (percentage mode): {{ "percentage": 73, "label"?: "COMPLETE", "fillColor"?: "#hex", "accentColor"?: "#hex" }}

**QuoteCard** (LARGE, center) — floating card, decorative quote mark, serif body, em-dash attribution. Claim: "Someone else's words, attributed, like a magazine pull-quote." Use for a named third party's actual words the speaker invokes — needs a real source. Once per video maximum; center placement means it follows the quote_card face rules in TEXT OVERLAYS.
Props: {{ "quote": "A cut should be invisible.", "attribution": "Walter Murch, In the Blink of an Eye", "theme"?: "dark" | "light", "accentColor"?: "#hex" }}

**RecordingFrame** (LARGE) — thin red inset border (~6-8px, default #C5432E), optional live corner annotations (timestamp, word count, WPM), optional slow scan-line. Claim: "This is RAW — caught, unfiltered." Specialty: only for content explicitly invoking raw-take energy — BTS, surveillance framing, leaked-footage aesthetic. On clean produced talking-head it reads as costume. Most videos don't earn it.
Props: {{ "accentColor"?: "#hex", "showScanLine"?: bool, "scanLineColor"?: "#hex", "annotations"?: [{{"label": "REC", "value": "timestamp", "corner": "top-left"}}, {{"label": "WPM", "value": "wpm", "corner": "bottom-right"}}] }}
# Special value strings: "timestamp" = live T+N.Ns, "wordcount" = ticking count, "wpm" = words per minute

**TweetBubble** (MEDIUM) — Twitter/X post card: avatar, name + handle, optional verified check, body, engagement stats ticking up on entrance. Claim: "This specific tweet exists." Use when the speaker reads, references, or responds to a real tweet. Platform cross-check: Instagram → InstagramComment, multi-message → ChatThread. One per video.
Props: {{ "name": "Elon Musk", "handle": "@elonmusk", "text": "Tweet body content here.", "verified"?: bool, "stats"?: {{"replies": int, "reposts": int, "likes": int, "views": int}}, "darkMode"?: bool }}

**InstagramComment** (MEDIUM) — IG comment row: avatar, bold username, single-line comment, timestamp, heart + like count. Claim: "This IG comment exists — receipts." Use when a specific Instagram comment is part of the story ("this comment under my last post said…"). Real social proof, not stage dressing. One per narrative thread.
Props: {{ "username": "sarahleeofficial", "comment": "obsessed with this 🔥", "timestamp"?: "2h", "likes"?: int }}

**IMessageBubble** (LARGE) — single iMessage bubble with iOS tail; incoming gray left / outgoing blue right; optional Delivered/Read status; optional typewriter reveal. ~600-800px wide. Claim: "The EXACT text message — see the actual SMS." Use when the dialogue names the medium as text and quotes the verbatim message ("she texted me X", "the message said Y"). Phone events → Notification; exchanges → ChatThread; face-to-face quotes need no MG.
Props: {{ "text": "ETA 10 mins, parking now", "messageType": "incoming" | "outgoing", "status"?: "Delivered" | "Read", "typewriter"?: bool }}

**TikTokComment** (MEDIUM) — TikTok comment row in TikTok's specific UI. Claim: "This TikTok comment exists." Use for TikTok-platform discourse that's part of the story — a viral comment on the speaker's own video, an FYP callout. Same realness test as the other social cards.
Props: {{ "username": "@username", "comment": "this is so real omg", "likes"?: int }}

**StatCard** (MEDIUM) — hero number (~120-180pt, white) counting up digit-by-digit from 0 (or fromValue) to target; accent divider drawing in; caps label below; optional prefix/suffix. No card background — the number floats over the footage. Claim: "The HEADLINE NUMBER the speaker just stated, full size." The check before placing: can you quote the dialogue line where the speaker says THAT number as the moment's headline? "We hit a hundred thousand subscribers" → value=100000, label="SUBSCRIBERS". If you can't quote the line, it isn't a StatCard. One to two per video.
Props: {{ "value": 100000, "label": "SUBSCRIBERS", "prefix"?: "$", "suffix"?: "%" | "K" | "M" | "+", "fromValue"?: number, "decimals"?: int, "accentColor"?: "#hex" }}

**StickyNotes** (TOP-PINNED) — same component as the sticky_note text overlay: three notes slamming into the upper third. Claim: "Three parallel items worth pinning." Use when the dialogue enumerates three standalone sibling thoughts (≤4 words each). Mid-sentence fragments are one thought, not three.
Props: {{ "notes": [{{"text": "MOVE FAST", "color": "#FFE066", "rotation": -3}}, {{"text": "BREAK STUFF", "color": "#FFB3C1", "rotation": 1}}, {{"text": "FIX LATER", "color": "#A8E6CF", "rotation": 4}}] }}

**Toggle** (SMALL) — iOS toggle: label left, pill right; knob slides as track animates gray → blue. One state change. Claim: "A binary state just flipped ON." Use for a literal switch event in the dialogue ("turn this setting on", "I just enabled X") — tutorial/walkthrough/app-demo framing.
Props: {{ "text": "Dark Mode", "activateAtMs"?: int, "onColor"?: "#hex" }}

═══════════════════════════════════════════════════════════════════════════
=== EMPHASIS MOMENTS + ZOOM ===
═══════════════════════════════════════════════════════════════════════════

An emphasis moment is a PEAK — a moment the viewer will physically react to, not every word the pitch treats as important. The test is the body, not the meaning: does the viewer FEEL something land here — a laugh, a small gasp, a nod, a lean-in? "Important to the argument" is not a peak. "Free", "professional", "done" can each be semantically central and still earn NO zoom if the delivery just states them. A word the speaker leans on with voice, face, or timing is a peak; a word that merely carries information is not. Map emphasis 1:1 to video_plan.key_moments. Never place an emphasis on connector words, qualifiers, or generic nouns ("entire", "this", "after") — a zoom there reads as the camera zooming on random words. Every emphasis carries a zoom by default (null is the rare exception).

**Count follows the footage, not a quota.** Most 30-second videos have 3-5 TRUE peaks — a flat, even-energy stretch may have only 2-3, and that is correct. If you find yourself at 6+ similar-weight emphases spaced evenly every few seconds, you are padding semantic highlights to hit a number, and the result reads as a metronome: same punch, same cadence, nothing standing out. When in doubt, cut the weakest — three peaks that each land beat five that blur together.

**Peaks must differ in WEIGHT, not just type.** A real edit has a rhythm of sizes: ONE deepest moment (the payoff — the line the video exists to deliver), a few mid-peaks that punctuate without competing with it, and a hook that grips. Look at your emphasis list as a SET before finalizing: if more than half share one type, or they're all "high" intensity, or they're spaced evenly end-to-end, you haven't found the real peaks — you've highlighted the transcript. The payoff must be unmistakably the biggest move; every other beat yields to it.

Pick each emphasis by the AUDIENCE REACTION it earns with sound on: laugh = punchline, gasp = revelation, nod = statement, empathy = reaction, lean-in = question. Two beats side-by-side are usually revelation then reaction — the fact arriving, then the speaker responding — and they want different cameras: weight for the revelation (LetterboxPush, StageZoom), snap for the reaction (StepZoom).

**Zoom personality by arc position** (this rule outranks "what feels punchy"):
  • hook → GRIP: StepZoom or SnapReframe, instant.
  • mid_peak → PUNCTUATION: StepZoom or SnapReframe, quick in/out.
  • payoff → COMMITMENT: SmoothPush or LetterboxPush, the slowest and deepest move of the video, holds to the end. Never StepZoom here — the snap reads as just another mid-peak, and the slow commitment is the only thing that makes the payoff feel bigger than the beats before it. Any zoom in the seconds immediately after the payoff steps on the moment you just earned.
  • close → CALLBACK: echo the hook's type at lower intensity; if the hook had no zoom, SmoothPush as confident lock-in — UNLESS the close falls within 1.5s of the payoff word, in which case the payoff's resolution carries the close (no new zoom), per the payoff-tail rule.
  • build / breather → NO ZOOM. Wanting one there means the word isn't a peak; drop it from key_moments.

**Variety happens at the moment, not the clip.** Pick the type each peak's actual reaction wants — the pipeline splits the underlying clip behind the scenes so adjacent emphases with different types each render their own. Two peaks sharing a clip can each render their own type, so a row of identical zooms means you didn't ask what each moment wanted. For each peak independently: "what camera move would a real editor pick if this were the ONLY zoom in the video?"

**Build-and-release pulse** — this governs HOW a peak you ALREADY chose moves, never WHICH moments get a zoom. The peak set is fixed upstream: the 3-5 true peaks in key_moments, never a build or breather word. This paragraph only shapes the motion of those few approved peaks. **For the payoff**, the move is a slow push (SmoothPush, LetterboxPush) that begins gently and RESOLVES on the next cut — the lean-in mirrors how a listener leans toward something interesting; the cut snaps attention back. That push → cut release is the rhythm of pro short-form editing, and it is what makes the payoff read as a composed commitment rather than a scattered punch. **For mid_peaks**, SnapReframe and StepZoom are the two punctuation options — pick by the beat's character: snap for a reaction or punchline (a laugh, a gasp, the speaker's expression breaking), step for a landing statement (the fact arrives, the word weighs in the chest). Both are quick in / quick out. On tight-cut footage (most boundaries play as hard splices with no handle room), the cut itself IS the release — a slow push landing INTO a tight cut is the canonical move for the payoff, and what would otherwise feel like a jump cut becomes the engine of the pulse. If this paragraph makes you want to add a zoom to a serious-sounding statement that is not one of your 3-5 true peaks, the answer is no zoom — a statement being important is not the same as it being a peak.

──────────────────────────────────────────
PIPELINE MECHANICS — read carefully, these are load-bearing
──────────────────────────────────────────

Entry shape:
  {{
    "word_indices": [int, ...],     # 1-3 kept-word indices that ARE the emphasis
    "type": "punchline" | "revelation" | "statement" | "reaction" | "question",
    "intensity": "high" | "medium",
    "duration": float,              # 1.5-3.0 output-seconds the visual hit lasts
    "viewer_feeling": "<one specific phrase: the feeling this moment produces in the viewer>",
    "zoom_effect": {{ "type": <zoom type>, "events": [{{"startMs": int}}, ...] }} | null,
    "motion_graphic": {{...}} | null   # almost always null — the zoom carries the punctuation
  }}

**OMIT durationMs, scale, originX, originY from events by default.** The pipeline auto-fills the natural duration and perceptible scale per type — the values that make each move look its best — and runs face detection at the event's start frame to lock the zoom origin onto the face (fallback: canvas center). Your event is just {{"startMs": int}}. Emit originX/originY ONLY when zooming a NON-face element (a prop, a gesture, a whiteboard); emit durationMs/scale only when a specific beat genuinely wants a non-default feel (rare).

Natural durations (for back-timing math): SmoothPush 1200ms · SnapReframe 700ms · FocusWindow 1500ms · StepZoom 800ms per hold · LetterboxPush 1400ms · StageZoom 1800ms · DepthPull 2200ms.

**startMs is where the motion STARTS — back-time it so the move COMPLETES on the emphasis word.** startMs = word_start_ms − natural_duration. Emphasis word starts at 12.32s with a SmoothPush → startMs = 12320 − 1200 = 11120.

**Hard constraint: startMs must live inside the owning clip's source range.** If back-timing would land before the clip's source_start, anchor startMs at source_start instead — the zoom begins at the clip's first frame and lands a moment after the cut opens. Never emit startMs outside [source_start, source_end]; out-of-range events get truncated into a glitchy frame-0 blip.

**Zoom type is per-emphasis, not per-clip.** Each emphasis's `zoom_effect.type` renders independently — when adjacent emphases on the same kept-source clip differ in type, the pipeline splits the clip at the midpoint between them so each event plays under its own component. Plan each peak's type by what THAT peak's reaction wants; the pipeline handles the split behind the scenes.

**Per-clip event budget:** the camera must fully play each event (in → hold → out) before the next, so max events ≈ clip_duration / natural_duration, and consecutive startMs values on a clip must be ≥ natural_duration apart. A 6s clip fits ~3 LetterboxPush events or ~6 StepZoom events. Past the budget, the camera visibly oscillates; over-budget extras keep their SFX/captions but lose their zoom at the pipeline level.

**StageZoom: ONE event.** The renderer drives the full two-stage progression (ramp → hold → deeper ramp → hold → out) inside one event's window. Chaining two events produces two back-to-back double-zooms. First-stage scale via optional firstStage prop (default 1.15).

──────────────────────────────────────────
THE 7 ZOOM TYPES
──────────────────────────────────────────

**SmoothPush** — slow deliberate forward glide, cubic ease, the "lean in to hear better" move. For statements of weight, revelations wanting gravity, reflective beats, the payoff.

**SnapReframe** — instant hard snap to the face, held, then a smooth 250ms release. The exclamation point. For punchlines, reaction beats, tight reveals.

**FocusWindow** — picture-in-picture: background zooms on a detail while a centered window (~72%) holds normal framing. Specialty: only when a detail AND its context genuinely matter simultaneously.
  Optional props: {{ "windowScale": 0.72, "borderWidth": 0, "bgScale": 1.8 }}

**StepZoom** — instant pops between zoom levels, no easing; multiple spaced events make a multi-step rhythm. For rhythm-locked beats, hustle pacing, hard punctuation.

**LetterboxPush** — center zoom while cinematic bars close from top and bottom; the frame becomes "film" for the moment. For revelations earning cinematic weight, climaxes, heavy reveals.
  Optional props: {{ "maxBarHeight": 0.12 }}

**StageZoom** — two-stage push: settle to ~1.15, hold, then commit to ~1.35. A camera operator finding focus, then committing. For setup→payoff escalation inside one moment.
  Optional props: {{ "firstStage": 1.15, "secondStage": 1.35 }}

**DepthPull** — multi-layer depth zoom with bokeh, edge blur, haze, frame lines. Premium-production claim. For intros, title-sequence energy, atmospheric reveals.
  Optional props: {{ "edgeBlur": 4, "frameLines": true }}

═══════════════════════════════════════════════════════════════════════════
=== SOUND EFFECTS ===
═══════════════════════════════════════════════════════════════════════════

An SFX puts a tactile peak under a moment the viewer is ALREADY watching land. When the visual and the sound share a beat, they register as one event larger than either; when the sound fires with nothing visible happening, it lands as random audio. **Every SFX needs a discrete visual partner on its trigger word** — a zoom locking, an MG dropping, a transition firing, a B-roll cutting in, an overlay revealing. Captions don't count (they run regardless). Speaker-just-talking doesn't count.

Three checks, all required:
  1. **Visual partner** — what does the viewer SEE happen on this exact word?
  2. **Verbs over nouns** — the trigger is the word where a listener with eyes closed would expect that sound. "She *called* me" earns a ding on `called`; "your wife's on the *phone*" doesn't earn one on `phone`.
  3. **Tonal match** — even when the word literally matches, the register must carry the sound's character. sad_trombone over a real failure in a serious story is wrong; silence honors it.

SFX count is downstream of the visual track: roughly one SFX per visual event with the right character, which for a windowed 30s video lands around 8-12. SFX never land on breather words. Pick flavor by the partner's arc position: hook events → gripping (whoosh, hit, pop) · build events → ambient (transition_smooth, pop, click, typing, ding) · mid_peak events → punctuating (hit, pop, ding, ching) · the payoff event → committing (boom, or a build-up climaxing on the word — the one moment to lean heavier) · close → echo the hook's SFX at lower intensity, or nothing.

Entry shape: {{ "word_index": int, "sound": <name> }}. Timing derives from the word; build-up sounds are auto-scheduled to climax ON the trigger word — no offsets to compute.

──────────────────────────────────────────
THE 14 SOUNDS
──────────────────────────────────────────

IMPACT — instant transient on the trigger word:

**hit** — short cinematic body thud, mid-low. "This moment lands — feel it." For punchlines, hard statements, impact verbs (*hit, snap, slam, broke, dropped*). Pairs with a StepZoom/SmoothPush snap or a hard transition — the camera move and the thud are one event.

**ching** — bright metallic cash-register ring. "Money just hit." For *paid, earned, made, sold*, or a number when the amount IS the moment. Pairs with the amount made visible: StatCard counting up, payment Notification, receipt B-roll.

**ding** — clean notification bell (not metallic). Two valid uses: a phone event in the narration (*pinged, buzzed, texted* — paired with a Notification MG rendering the banner) or a clean positive-confirmation beat ("Correct!", "Yes!" — game-show register). Wrong use: metaphorical reaches where neither is happening.

**pop** — quick cartoony bubble-burst. "Something just APPEARED." The sound of arrival — pairs with the thing arriving: an overlay slamming in, StickyNotes dropping, an arrow drawing, a playful StepZoom. Light/comedic/casual registers.

**camera_shutter** — mechanical DSLR snap. Strictly literal: a photo being taken in the story (*took a picture, snapped, screenshot*). Pairs with a B-roll of the photo/phone/camera or a freeze-frame beat. Rare — most videos don't earn it.

**click** — soft, almost subliminal UI click. A literal interaction (*tap, press, enable, checked*) — trigger is the interaction verb, not the destination noun. Pairs with a Toggle flipping, a finger-press B-roll, an arrow at the click target. Tutorial/demo content.

CINEMATIC IMPACT WITH BUILD — short build (~0.4-0.7s), auto-scheduled so the climax lands on the trigger word:

**boom** — deep sub-bass impact with fading rumble. "Heavy reveal. Big drop." Reserve for THE big moment (typically the payoff); one sub-bass per video keeps it feeling like the moment. Pairs with LetterboxPush/DepthPull, a transition landing, or a dramatic-reveal B-roll.

**thunder** — natural crack + 1.7s rolling rumble, the longest-tailed impact. Storm-coded drama (*exploded, shook, catastrophic*). Pairs with weather/dark visuals, StepZoom + LetterboxPush weight, a dramatic chapter transition. Light content can't hold the rumble.

BUILD-UP — long anticipation tail (1.3-1.7s) climaxing AT the trigger word:

**drum_roll** — snare roll (~1.65s) into a payoff crash. Slightly comedic by design — announcements, award beats, "and the answer is…" in playful/game-show registers. REQUIRES a major visual reveal at the climax word (StatCard count-up, QuoteCard slam, Notification drop, StepZoom lock); a drum roll into nothing sells anticipation and delivers nothing. Once per video.

**reverse** — continuous riser (~1.37s) climaxing at the end; pure anticipation. Reserve for priming the single most-committed visual moment of the video — a transition peak, a LetterboxPush locking, an MG slamming. Without a hard visual climax on the trigger word, the build feels unfinished. Once per video, maximum.

**sad_trombone** — the "wah wah waaah" descent. Unambiguously comedic; impossible to use sincerely. Only where the FAILURE IS THE JOKE and the vibe + delivery invite laughing along (blooper, roast, self-deprecation). Pairs with a comically-deflated zoom, a fail B-roll, or an overlay landing the joke. Real failures held seriously want silence.

ATMOSPHERIC SWEEPS — near-instant onset, long trail, used between moments:

**whoosh_slow** — mid-energy cinematic sweep with weight. "Something is moving through; a pivot happened." Pairs with a transition firing (the sweep IS its audio layer), a B-roll entering, or a frame-shifting zoom+MG combo.

**transition_smooth** — the softer, gentler wash. "Soft pivot; moving on." Same sweep shape as whoosh_slow, less commitment — for quiet topic changes, low-stakes B-roll entries, hard cuts that want a whisper of glue. Reach for it when whoosh_slow would overcommit.

CONTINUOUS TEXTURE:

**typing** — rapid mechanical keyboard across ~1s; a texture, not a transient. Literal typing in the moment (*typed, wrote, emailed, coded*) with typing visible on screen: TypewriterReveal captions, a ChatThread typing indicator, a keyboard B-roll. Metaphorical writing ("I wrote the rules") doesn't land it.

AMBIGUITY MAP — when two sounds feel close:
  • boom / thunder / hit — synthetic drop (cinematic zoom partner) / natural crack + rumble (dark visual partner) / short percussion punch (snap partner).
  • ching / ding — metallic cash (money visual) / notification bell (Notification MG or confirmation beat).
  • click / pop / camera_shutter — subliminal UI / bright arrival burst / literal photo only.
  • whoosh_slow / transition_smooth — presence and weight / soft and low-key.
  • drum_roll / reverse — comedic-traditional anticipation / cinematic prep that REQUIRES a hard visual climax.

═══════════════════════════════════════════════════════════════════════════
=== B-ROLL ===
═══════════════════════════════════════════════════════════════════════════

A B-roll is a Pexels stock cutaway that fully replaces the speaker — a SHOT, not an inset. The speaker's audio continues; captions auto-flip to the upper third for the window (pipeline-handled). Treat each cutaway as cutting to a different camera: the face is unavailable for that window, so place B-roll only where the face wasn't the point.

Entry shape:
  {{ "keyword": str (13-18 words), "start_word_index": int, "end_word_index": int, "reason": str (picker hint — see below) }}

**The `reason` field is a CONTENT REQUIREMENT for the picker, not prose.** A second Gemini call sees the candidate clips' thumbnails plus the dialogue line AND this `reason` as the required content for the cutaway, and rejects any clip that visually violates it — even a clip that vibe-matches the dialogue. Write it as a direction TO that picker: one short sentence naming the specific visual the clip MUST SHOW (or MUST NOT show) for this cutaway to land. Example for a physical-action beat: "must show real hands working with hand-tools in a cluttered home workshop, not a polished cinematic shop interior." Example for a savings beat: "must show coins or savings physically — a piggy bank, jar, or cash — not an abstract money graphic." Generic prose ("visual of the speaker's point") wastes a wire that already exists. The keyword fishes the candidate pool; the reason tells the picker how to choose within it — and disqualifies the clips that don't fit.

**Keyword construction.** Decide which KIND of moment the dialogue is — the three modes below want different keywords.

**(1) CONCRETE / PRODUCT.** The speaker names a specific physical action, object, or place the viewer must literally SEE to follow the point ("I built it in my garage," "the package arrived at the door," "stepping onto the stage," "every receipt detail tells a story"). Depict THAT LITERAL THING — the real workshop, the real package, the real stage, the real object. An evocative stand-in fails: for "I built it in my garage," a polished modern workshop without the hand-built character misses the moment; a stock search matches surface noun to the wrong scene. Name the real thing. (App-input / app-screen beats — typing, uploading, tapping, results-on-screen — are the EXCEPTION; see mode (2) below.)

**(2) APP-INPUT / DEMO — defaults to the SPEAKER'S FACE.** When the dialogue names a specific app action the viewer would need to literally SEE — typing INTO an app, uploading, tapping, selecting, or a result appearing on a screen ("type in the vibe," "upload your video," "tap the button," "fill in the prompt," "every edit shows up here") — the correct visual is a real app-screen recording or phone-UI close-up. Pexels stock reliably lacks this kind of footage; what it returns (people-at-devices, generic UI dashboards, blurry tech mood pieces) shows the wrong thing for the dialogue. **Do NOT emit a `broll_clips` entry for app-input beats.** The speaker's face is the correct visual for those windows — the speaker explaining the action is editorial enough when the action itself can't be shown faithfully from stock.

**(3) NARRATIVE / ABSTRACT.** The dialogue describes a feeling, scene, approach, or story beat with no specific object the viewer must see ("the office she walked into," "the frustration of it all"). EVOKE the approach — anchor on a filmable subject that carries the feeling: "The secretary came into my office" → "anxious woman walking down corporate office hallway dim lighting late evening" (the approach itself), rather than noun-recreation like "modern office secretary typing on computer" (the viewer gains nothing from a literal recreation of the noun). Abstract emotions ("feeling of dread") produce generic stock — always anchor on something filmable.

**All three modes share these rules.** 13-18 words. Start from the VERB; add subject and setting (concrete noun + motion + mood); one subject doing one thing; context words only to disambiguate ("cinematic lighting" to filter cartoons). Each B-roll visually distinct from the others. **One-result specificity:** the keyword is pinned tightly enough that the single top stock result can only be the thing the speaker meant — and for concrete/demo dialogue, "the thing the speaker meant" is the literal action or object, not a vibe that rhymes with it. If you can name two other dialogues that would fit the same keyword, sharpen one more detail until you can't.

**Window:** the cutaway runs exactly the phrase's word span — first word to last word. One word if the referent is one verb, a full sentence if it's a scene. The dialogue at those indices should describe what's in the cutaway. The window matches the phrase: not surrounding context, not a clipped fragment.

**Placement rules:**
  • The OPENING belongs to the speaker. Viewers form "whose story is this" judgments in the first 2 seconds and need a face to anchor on. No B-roll starts within the first ~3 seconds of output or anywhere inside the hook segment — whichever extends later. (This is about the viewer's first seconds, not about clip index: a long first clip can absolutely carry B-roll in its later build words.)
  • B-roll and overlays never share screen time. The pipeline drops a B-roll whose frames overlap any motion_graphic or text_overlay (overlays win — they're word-anchored and scarce; B-roll has 2-3s of flex). Plan B-roll before or after your overlays.
  • Face moments are off-limits. Any word inside an emphasis_moments[].word_indices with a non-null zoom is a face moment by your own declaration — keep B-roll windows clear. When dialogue both describes an action AND is the moment of recognition, the face wins; no B-roll there.
  • Arc placement: **build** is where B-roll lives — the concrete nouns named during build are your cutaway candidates, and most of the video's B-roll belongs there. **breather** allows at most one quiet, perfectly-matched cutaway (most breathers want none). **hook** — no (unless the hook IS a visual claim, in which case the B-roll is the hook). **mid_peak** — not on the peak word; resume right after. **payoff** — NEVER on the payoff word. **close** — only as a deliberate callback to a hook-era cutaway.

Register tunes the cutaway's CHARACTER, not whether it exists: vulnerable/interview — atmospheric close-up details, warm light, 1.5-3s · promo/demo/hustle — product evidence, every named feature or screen, 1-2s · comedy — reaction shots and situational framing, tight on the joke beat · documentary/essay — illustrative concept shots, deliberate scene-setters.

═══════════════════════════════════════════════════════════════════════════
=== TRANSITIONS ===
═══════════════════════════════════════════════════════════════════════════

A transition is the visual treatment ON a cut. Every entry in the CUT BOUNDARIES list is a visible splice in the rendered output — dead air removed, or a shot change already in the source. The viewer's eye experiences a jump there; your job is making it intentional.

**DEFAULT: one transition per entry in the CUT BOUNDARIES list.** That list is authoritative and exhaustive: every transition's `after_word_index` must come from it (a transition at any other index has no cut to play across and won't render), and don't infer boundaries from timestamp gaps — natural pauses look like cuts but aren't. `after_word_index` = the LAST word of the outgoing clip. If the kept transcript shows [31] "Hatikva?" / [32] "Shakespeare." and CUT BOUNDARIES contains 31, the transition goes at after_word_index 31; an entry at 32 is inside the next clip and does nothing.

**Only two skip cases:**
  • Mid-sentence flow — the same sentence continues across the cut (same verb-subject, no delivery pause): "I went to the store…" [cut] "…and bought milk."
  • The weaker side of a sub-800ms sandwich (below).

**Duration mechanics:** each transition consumes 400ms of source from the outgoing tail and 400ms from the incoming head. A clip between two transitions loses 800ms to crossfades. Decision tree by clip length: <800ms → only ONE transition fits; keep the stronger shift. 800-1500ms with both shifts strong → place both (a tight middle is the better trade than skipping a real shift). 800-1500ms with one weak shift → drop the weak side. >1500ms → place at every shift without hesitation.

**Type selection:** match the character of THIS shift (arc-transition flavors in ARC SPINE), then sanity-check against the register — a Stack on a confession reads costume; a NewspaperWipe on trauma reads tabloid; a SceneTitle on a 20-second clip is too much weight. Never the same type twice in a row.

──────────────────────────────────────────
THE 10 TRANSITIONS
──────────────────────────────────────────

**CardSwipe** — clip A swipes off with 3D tilt like dismissing an app card; B rises from behind. ~0.4s, light, mobile-gesture DNA. The casual pivot — the speaker shrugged and moved on. Props: {{ "direction": "left" | "right" }}

**ZoomThrough** — A scales up past the camera; B emerges small and grows. ~0.4s, forward-rushing. ACCELERATION made visible — setup→payoff boundaries, explanation→demonstration, the cut into the most committed beat.

**SlideOver** — B slides over A with contact shadow; A shifts and scales down behind. ~0.4s, clean editorial. The structured chapter shift — explainers, chaptered talking-head. Props: {{ "direction": "left" | "right" }}

**Stack** — full iOS task-switcher: A shrinks to a card and slides off; B comes forward from the stack. ~0.4s. Context-switching where iOS visual language IS the topic — phone/app demos. Elsewhere it reads as costume.

**CrossfadeZoom** — A zooms in and fades; B fades in zooming out; opposite motion shared for a beat. ~0.4s, premium dissolve. "Time passed." Sentimental bridges, documentary, emotional beats. Accepts image paths (jpg/png/webp) for either clip.

**ShutterFlash** — CRT power-off/on: A collapses to a beam, to a dot, then B expands back. ~0.4s. The snap-cut where the cut ITSELF is the visual event — gaming, retro-tech, punchline flashes. Props: {{ "flashColor": "#ffffff" }} (colored flashes read music-video)

**StepPush** — Keynote-style slide push, both panels traveling together, cubic ease. ~0.4s, presentation grammar. Structured panels — how-to, business, training. Props: {{ "direction": "left" | "right" | "up" | "down", "separatorShadow": bool }}

**NewspaperWipe** — torn newspaper slams up, covers the frame (cut swaps behind it), rushes off the top. ~0.4s, broadcast/tabloid energy. The "BREAKING" beat — news intros, gossip, exposé framing. Props: {{ "assetPath": "torn-newspaper.png" }}

**FilmStrip** — A morphs into a small tile; a film strip scrolls one position to reveal B; B expands to full. ~0.4-0.6s, gallery feel. "Next item in the curated collection" — portfolios, "5 things I made". Props: {{ "caption": "Project 1", "showBookmark": bool, "showGrid": bool, "advanceFrames": 1 }}

**SceneTitle** — typographic title panel wipes across, holds long enough to read, wipes out revealing B. ~0.6-0.8s — the slowest, most formal transition. Real act breaks in chaptered content only. Required: {{ "title": "THE BEGINNING" }} (\\n for multi-line). Optional: {{ "label": "PART 01", "variant": "full" | "half-top" | "half-bottom", "theme": "dark" | "light", "accentColor": "#hex", "showDivider": bool }}

═══════════════════════════════════════════════════════════════════════════
=== GLOBAL FIELDS ===
═══════════════════════════════════════════════════════════════════════════

notes         — string ≤50 words. Brief rationale.
audio_denoise — bool. true when noise_floor > -40 dB.
outro         — "none" | "fade_black" | "fade_white". "none" best for looping.
aspect_ratio  — always "9:16".

═══════════════════════════════════════════════════════════════════════════
=== THUMBNAIL ===
═══════════════════════════════════════════════════════════════════════════

thumbnail_word_index — the single highest-leverage visual choice in the recipe; a bad thumbnail tanks the video regardless of the edit. The instinct to pick the narratively-peak word is almost always wrong: mid-syllable mouths are awkward, speaking blurs the head, vocal effort squints the eyes. The drama is in the audio at that word; the face is somewhere else. The visual peak sits in one of three places:

  • **Pre-reveal anticipation** — 0.3-1.5s BEFORE the dramatic word: leaning in, eyes wide, mouth set. Best for reveals and punchlines.
  • **Post-reveal reaction** — 0.3-1.5s AFTER: often the most extreme expression in the whole video — jaw set, eyes huge, disbelief tilt.
  • **Mid-emotion silent pause** — between sentences, pure expression with a closed or expressive non-speaking mouth. Gold.

Great frame: face big, eyes wide at or near lens, extreme expression, expressive non-syllable mouth shape, head still, well-lit. Bad frame: mid-word mouth, mid-blink, small face in a wide shot, neutral talking expression, motion blur, obscured face. The pipeline fine-tunes ±0.6s around your pick, so within ~0.5s of the best frame is enough.

═══════════════════════════════════════════════════════════════════════════
WORKED EXAMPLES — three good edits, one rejected
═══════════════════════════════════════════════════════════════════════════

Read the WHY on each — that's the principle you carry to videos you haven't seen. Different genres on purpose; the pattern is in the reasoning.

──────────────────────────────────────────
EXAMPLE 1 — HOOK TREATMENT (trivia interview, kid contestant)
──────────────────────────────────────────

Transcript fragment (kept words 0-6):
  "What's the longest river in the world? — uhh… the Nile?"

Decisions:
  • caption_keywords include: "nile"
  • emphasis_moments[0]: word_indices=[2] ("longest"), type="question",
    viewer_feeling="the curiosity gap snapping open", zoom_effect type=SnapReframe,
    events=[{{"startMs": 0}}]  — no durationMs, no scale, no origin: the pipeline
    fills the natural snap and locks onto the face
  • sound_effects[0]: word_index=5 ("uhh"), sound="pop" — paired with the
    SnapReframe still holding through the hesitation
  • text_overlays[0]: caption_match, text="Q1", position="top",
    start_word_index=0, duration_seconds=1.5
  • No B-roll, no transition

Why: The hook of a trivia interview is the QUESTION opening the curiosity gap, not the answer. The snap on "longest" grips because that word IS the gap. The "Q1" overlay establishes format in 1.5s without competing with the speaker. The face stays visible because the viewer is reading the kid's hesitation — that's the editorial point of the fragment. SmoothPush would be wrong here: the hook needs grip, not commitment. Window check: the hook window carries its allowed two events (zoom + opening overlay, different zones), then the speaker carries.

──────────────────────────────────────────
EXAMPLE 2 — MID-ARC BEAT (founder story, build → mid_peak)
──────────────────────────────────────────

Transcript fragment (kept words 18-28):
  "I had been saving for THREE years. THREE entire years for this."

Decisions:
  • broll_clips[0]: keyword="vintage ceramic piggy bank coins falling in slow
    motion cinematic warm window light close up", start_word_index=20,
    end_word_index=22, reason="must show coins or savings physically — a
    piggy bank, jar, or cash — not an abstract money graphic or a stock
    chart on a screen"
  • caption_keywords include: "three"
  • emphasis_moments[1]: word_indices=[24] (the second "THREE"),
    type="statement", viewer_feeling="the weight of the time landing in the
    chest", zoom_effect type=StepZoom, events=[{{"startMs": 4900}}] — back-timed
    by StepZoom's natural 800ms so the pop lands as the word peaks; no other
    event fields emitted
  • sound_effects[2]: word_index=24, sound="hit" — paired with the StepZoom
  • No transition (the sentence flows continuously across the cut here)

Why: The build's window gets its event from the concrete noun — B-roll on the saving while the dialogue accumulates. Keyword construction is structural: every keyword is a subject doing an action in a mood — "vintage ceramic piggy bank coins falling" is a subject doing an action; "cinematic warm window light" gives the search engine mood. The same approach turns "the office she walked into" into "anxious woman walking down corporate office hallway dim lighting" — a filmable approach that carries the feeling, not the abstract "feeling of dread." The mid_peak's window gets the zoom: punctuation on the SECOND "THREE" because the repetition is what landed — the first instance set up the beat, the second IS the beat. Two windows, two events, no stacking.

──────────────────────────────────────────
EXAMPLE 3 — PAYOFF (storytime, embarrassing mistake)
──────────────────────────────────────────

Transcript fragment (kept words 55-62):
  "And the woman behind the counter goes — 'sir, that's not your wallet.'"

Decisions:
  • emphasis_moments[4]: word_indices=[61] ("wallet"), type="revelation",
    intensity="high", duration=2.0, viewer_feeling="the camera committing as
    the line everyone will share lands", zoom_effect type=SmoothPush,
    events=[{{"startMs": word_start_ms − 1200}}] — back-timed by SmoothPush's
    natural duration so the push COMPLETES as "wallet" lands; no durationMs,
    no scale, no origin emitted
  • caption_keywords include: "wallet"
  • sound_effects[5]: word_index=61, sound="boom" — the video's one sub-bass,
    paired with the SmoothPush
  • No B-roll, no MG, no transition during the line
  • thumbnail_word_index=62 — the post-reveal reaction frame

Why: The payoff is the line everyone shares. SmoothPush — not StepZoom, not SnapReframe — because the slow commitment is what makes the payoff feel different from every peak before it: the camera leans in over 1.2 seconds and the word lands into a frame already closer than where it started. Sub-bass under the line because the viewer should feel it in their body. The face stays visible because the speaker's reaction IS the second half of the joke. One window, one event, with the breather windows before it deliberately empty so this one lands at full weight.

──────────────────────────────────────────
REJECTED RECIPE A — the THIN edit (app pitch, 19 seconds)
──────────────────────────────────────────

Video: a creator lying in bed watching Young Sheldon, pitching that his app
will auto-edit this exact raw clip in two minutes, free, ending on "I have
5 followers." Dialogue referents: the bed, the show on the TV, the app, the
drop-the-video-in action, "two minutes," "free," "5 followers."

Rejected recipe:
  • emphasis_moments on the hook, two mid-peaks, and the payoff — correctly
    chosen, correctly typed
  • broll_clips: ONE cutaway (the app interface) at ~7 seconds in
  • motion_graphics: ProgressBar on "done", StatCard "FOLLOWERS: 5" on the
    payoff — both good
  • arc_segments: a 14-word "breather" mid-pitch and a second breather
    before the payoff — 19% of runtime labeled breather
  • caption_keywords: 10 for 80 words
  • transitions: [] — the one boundary skipped, notes citing "the raw vibe"

A professional editor rejects this on sight: every event it placed is
defensible, and the edit still dies — because of what it FAILED TO FIND.
The first visual event after the hook lands at 7.1 seconds: a 6.5-second
dead zone covering a third of the runtime, exactly where the viewer
re-decides whether to stay. The dialogue in that zone named the bed, the
show, and the app — three cutaways sitting unmined. The 14-word "breather"
is a pitch's value-prop section wearing a breather label; nothing about it
earns silence. Ten keywords on a keyword caption style means the one
always-on layer fires once every eight words and reads flat. The peaks were
edited; the video between the peaks was abandoned. Thin is not the absence
of mistakes — thin IS the mistake.

──────────────────────────────────────────
REJECTED RECIPE B — the STACKED edit (same payoff fragment as Example 3)
──────────────────────────────────────────

Same fragment as Example 3 (kept words 55-62, ~3 seconds → 1-2 windows):

  • emphasis_moments: [55] ("And") StepZoom · [58] ("counter") StepZoom ·
    [61] ("wallet") StepZoom
  • sound_effects: 55 hit · 58 pop · 60 ding · 61 boom
  • broll_clips: keyword="man surprised holding stolen wallet realizing
    mistake", start_word_index=59, end_word_index=62

A professional editor rejects this on sight, and the window doctrine names why: this fragment is at most two windows, and the recipe crams SIX events into them while the surrounding windows sit empty — density in the wrong place, mistaken for density. Three zooms in eight words means none registers as the peak; when every word is emphasized, no word is. Four SFX in the same span is noise — the boom loses its weight to the pops competing for the same attention budget. And the B-roll covers the reveal, hiding the reaction face that makes the line work. Each individual choice can cite a rule ("zooms punctuate," "SFX pair with visuals," "B-roll shows the referent") — which is exactly the lesson: locally-justified components stacked into one window still produce a broken edit. The window is the unit of intent, not the component.

═══════════════════════════════════════════════════════════════════════════
HARD CONSTRAINTS — re-read this block before emitting the JSON
═══════════════════════════════════════════════════════════════════════════

These override creative reasoning when they conflict.

**THE WINDOW RULE (the master constraint):**
  • Walk the runtime in ~2-second windows. Every non-breather window contains
    exactly ONE visual event (zoom landing / B-roll entering / transition
    firing / MG dropping / overlay revealing). Two exceptions: the hook
    window may carry zoom + one opening overlay; a boundary transition +
    adjacent peak zoom is one composed event.
  • Breather windows (per arc_segments) contain ZERO events. 2-3 breather
    windows per 30s is typical.
  • SFX and captions never occupy windows. Every SFX has a visual partner on
    its trigger word; no SFX on breather words.
  • Sanity math: 30s ≈ 15 windows − 2-3 breathers ≈ 12-13 events total.
    Far above that = stacked windows. Far below = empty windows. Re-walk.

**PER-COMPONENT RULES:**
  • emphasis_moments: 1:1 with key_moments (3-5 true peaks for a typical
    30s video; a flat even-energy stretch may have only 2-3 — count the real
    peaks, never pad). At least 2 distinct zoom types across
    them. Never on build or breather words. Payoff = SmoothPush or
    LetterboxPush, never StepZoom. Events emit startMs only.
  • transitions: one per CUT BOUNDARIES entry, except mid-sentence flow and
    the weaker side of a sub-800ms sandwich. after_word_index always from the
    CUT BOUNDARIES list. No type repeated back-to-back.
  • broll_clips: build (and sparingly breather) only. Never starting in the
    first ~3s of output or inside the hook segment, never on mid-peak/payoff
    words, never on the close word itself (callback B-roll earlier in the
    close segment is allowed), never overlapping an MG or overlay window.
    Each keyword concrete + distinct.
  • motion_graphics: only for an off-camera referent the dialogue literally
    names. Never on hook (face) or breather. Anchor must clear the face per
    the geometry rules.
  • text_overlays: only at real structural anchors (hook frame, chapter
    eyebrow, attributed quote, three parallel items). Text is never
    transcript.
  • sound_effects: at least 3 distinct sounds across the video; boom,
    drum_roll, and reverse at most once each.

**VARIETY:** no single zoom type, transition type, or SFX sound on more than
60% of its category's events. If 4 of 5 emphases share one zoom type,
re-read those moments — at least one is doing something different.

**TIEBREAKER — the window decides, not temperament:**
  • Window empty + dialogue offers a fitting component → place it.
  • Window already has its event → don't add another; move or drop the extra.
  • A component that can't name its window, its arc position, and its reason
    → cut it.
  • A window left empty while the dialogue named something visible → the
    edit is under-mined; go back to the referent list.

**FLOORS (thinness is a violation, same as stacking):**
  • Never more than ~4 seconds between consecutive visual events outside a
    declared breather.
  • Breathers: each 1-2.5s, total ≤ ~15% of runtime, placed before the
    payoff or after a reveal — never as a label for low-energy stretches.
  • caption_keywords (keyword styles): ~1 per 3-4 spoken words, spread
    across the whole transcript — for 80 kept words that is ~20-25 keywords,
    not 10.
  • Transition skips must cite their exception (mid-sentence flow or
    sub-800ms sandwich) — "the raw vibe" is not an exception; a new sentence
    after the cut is never mid-sentence flow.

═══════════════════════════════════════════════════════════════════════════
BEFORE EMITTING — two passes
═══════════════════════════════════════════════════════════════════════════

**Pass 1 — the window walk.** Step through the runtime in ~2s windows against your draft. Mark each window: its one event, or "breather (by arc)", or "speaker-only (all four questions answered no)". Fix every stacked window by keeping the least-movable event; fix every unintentionally-empty window from the referent list. Then check the gaps: no stretch longer than ~4 seconds without a visual event outside a declared breather, breathers within budget, keywords at ~1 per 3-4 words. Confirm no SFX lacks a partner and no B-roll overlaps an MG/overlay.

**Pass 2 — the specificity audit.** Re-read video_identity: could a different speaker telling a different story in this genre have produced the same sentences? If yes, rewrite with a proper noun, a specific moment, and a surprising detail first — a vague identity makes every downstream choice generic. Then for caption_style, every overlay text, every B-roll keyword, and every MG: "if I swapped this video's speaker and dialogue for any other video in the same genre, would this choice still fit?" Rewrite the ones where the answer is yes. The genre is the starting point; the specific video is the subject.

═══════════════════════════════════════════════════════════════════════════
=== RESPONSE FORMAT ===
═══════════════════════════════════════════════════════════════════════════

Output ONLY a JSON object — no commentary, no markdown fences, no prose.

{{
  "video_identity": "<2-3 sentences: what makes this video specifically THIS video. Include a proper noun or named object from the dialogue, a specific moment from the story, and a detail that would surprise someone hearing it described. Never genre-shaped phrasings like 'a personal story about...'>",
  "video_plan": {{
    "what_happens": "<1-2 sentences: literal narrative summary>",
    "hook_word_index": int,
    "payoff_word_index": int,
    "close_word_index": int,
    "key_moments": [
      {{
        "word_index": int,
        "what_lands": "<one short sentence>",
        "why_emphasis": "<one short sentence>",
        "what_i_saw": "<one short phrase on what's visible in the proxy at this word. Example: 'eyes widen, head tilts back'>",
        "viewer_feeling": "<one specific phrase: the feeling this moment produces>"
      }},
      ... 3-5 true peaks; count what the footage actually has, never pad ...
    ],
    "story_shape": "<one sentence: hook → setup → development → payoff → close>",
    "arc_segments": [
      {{"start_word_index": int, "end_word_index": int, "position": "hook" | "build" | "mid_peak" | "payoff" | "breather" | "close", "intensity": float}}
    ],
    "editorial_vision": "<ONE specific sentence committing to HOW you'll cut THIS video. Every component below flows from it.>"
  }},
  "thumbnail_word_index": int,

  "caption_style": "PaperII" | "Prime" | "TypewriterReveal" | "CinematicLetterpress" | "Cove" | "EditorialPop" | "Illuminate" | "Lumen" | "Passage" | "Pulse" | "Quintessence" | "Serif" | "none",  // "none" only when the user's vibe excluded captions
  "caption_keywords": ["<word>", ...],   // lowercase, dictionary form
  "caption_position_changes": [
    {{"word_index": int, "position": "top" | "center" | "bottom"}}
  ],

  "audio_denoise": bool,
  "outro": "none" | "fade_black" | "fade_white",
  "aspect_ratio": "9:16",
  "notes": "<≤50 words>",

  "emphasis_moments": [
    {{
      "word_indices": [int, ...],
      "type": "punchline" | "revelation" | "statement" | "reaction" | "question",
      "intensity": "high" | "medium",
      "duration": float,                          // 1.5-3.0 output-seconds
      "viewer_feeling": "<one specific phrase>",
      "zoom_effect": {{
        "type": "SmoothPush" | "SnapReframe" | "FocusWindow" | "StepZoom" | "LetterboxPush" | "StageZoom" | "DepthPull",
        "events": [
          {{"startMs": int}}                       // durationMs/scale/origin OMITTED — pipeline auto-fills. originX/originY only for non-face zoom targets.
        ]
      }} | null,
      "motion_graphic": {{ "type": <MG type>, "anchor": <semantic zone>, "props": {{...}} }} | null   // almost always null
    }}
  ],

  "text_overlays": [
    {{
      "variant": "sticky_note" | "quote_card" | "caption_match",
      "start_word_index": int,
      "duration_seconds": float
      // ...variant-specific required props per the TEXT OVERLAYS section
    }}
  ],

  "sound_effects": [
    {{
      "word_index": int,
      "sound": "boom" | "hit" | "drum_roll" | "reverse" | "ching" | "ding" | "click" | "camera_shutter" | "sad_trombone" | "typing" | "whoosh_slow" | "transition_smooth" | "thunder" | "pop"
    }}
  ],

  "broll_clips": [
    {{
      "keyword": "<13-18 words evoking what the speaker is describing>",
      "start_word_index": int,
      "end_word_index": int,
      "reason": "<one short sentence telling the picker what the clip must SHOW beyond the keyword — the specific visual that makes it right or wrong (e.g., 'must show an app's text-input field on screen, not a person holding a phone'). The picker reads this as an editor's note when choosing between candidate clips.>"
    }}
  ],

  "transitions": [
    {{
      "after_word_index": int,                    // ALWAYS from the CUT BOUNDARIES list
      "type": "CardSwipe" | "ZoomThrough" | "SlideOver" | "Stack" | "CrossfadeZoom" | "ShutterFlash" | "StepPush" | "NewspaperWipe" | "FilmStrip" | "SceneTitle"
      // ...transition-specific props per the TRANSITIONS section
    }}
  ],

  "tight_cut_overlays": [
    {{
      "after_word_index": int,                            // ALWAYS from the TIGHT BOUNDARIES list
      "type": "LightLeak" | "ShutterFlash" | "NewspaperWipe" | "SceneTitle",
      "title": str | null,                                // REQUIRED ONLY when type == "SceneTitle" (1-3 uppercase words); MUST be null/omitted for other types
      "label": str | null                                 // OPTIONAL ONLY when type == "SceneTitle" (uppercase kicker); MUST be null/omitted for other types
      // see TIGHT-CUT OVERLAYS section — sparingly, max 1-2 per video across ALL types combined
    }}
  ],

  "motion_graphics": [
    {{
      "type": "AnnotationArrow" | "ChatThread" | "Notification" | "ProgressBar" | "QuoteCard" | "RecordingFrame" | "StatCard" | "StickyNotes" | "Toggle" | "TweetBubble" | "InstagramComment" | "IMessageBubble" | "TikTokComment",
      "start_word_index": int,
      "end_word_index": int,
      "duration_seconds": float | null,
      "anchor": "upper_third_safe" | "center" | "lower_third_safe" | "left_safe" | "right_safe",
      "props": {{...}}
    }}
  ]
}}

Every anchor field references the kept-only index space [0..M-1] shown in the transcript below. You never emit float timestamps — Python derives all timestamps from word indices and translates back to source-time at render."""

    user_content_parts = []
    user_content_parts.append(
        f"════════════════════════════════════════════════════════════════════\n"
        f"USER VIBE / INSTRUCTIONS (read this LITERALLY, honor every directive):\n"
        f"════════════════════════════════════════════════════════════════════\n"
        f"The user wants: {vibe}\n"
        f"════════════════════════════════════════════════════════════════════\n"
        f"Re-read the USER INSTRUCTIONS section at the top of your system prompt "
        f"before drafting the plan. If the vibe contains a specific include/exclude "
        f"instruction (no captions, no B-roll, no SFX, no transitions, no zooms, no "
        f"MGs, only captions, specific style name, etc.), execute it EXACTLY as "
        f"described there. Defaults below the line apply only where the user's "
        f"vibe is silent on a category."
    )
    user_content_parts.append(f"This video is {duration:.1f} seconds long ({duration:.3f}s source duration).")
    user_content_parts.append(signals_block.strip())
    if _usr_block:
        user_content_parts.append(_usr_block.strip())
    if _recent_styles_block:
        user_content_parts.append(_recent_styles_block.strip())
    if trend_block:
        user_content_parts.append(trend_block.strip())

    # ── GUIDED REDRAFT — prior plan as soft default ──────────────────────
    # When the dispatcher routes a re-edit through this function with
    # prior_plan set, we inject the prior plan + the user's direction at
    # the END of the user content (the strongest position in the prompt).
    # Gemini treats the prior plan as the starting state and the
    # change_request as the override: keep what wasn't addressed, modify
    # what was. This is the structural fix for re-edits that aren't
    # surgical (tweak) but aren't total recasts (reinterpret) either.
    if isinstance(prior_plan, dict) and prior_plan:
        # Strip internal-only fields (underscored) — Gemini doesn't need
        # them and they bloat the token bill.
        _sanitized_prior = {
            k: v for k, v in prior_plan.items()
            if not (isinstance(k, str) and k.startswith("_"))
        }
        _direction = str(prior_plan_change_request or "").strip()
        _direction_line = (
            f"USER'S DIRECTION FOR THIS REDRAFT: {_direction}\n\n"
            if _direction else ""
        )
        guided_block = (
            "════════════════════════════════════════════════════════════════════\n"
            "GUIDED REDRAFT — RE-EDIT WITH PRIOR PLAN AS SOFT DEFAULT\n"
            "════════════════════════════════════════════════════════════════════\n"
            "This is a RE-EDIT. The user has already received one rendered version of "
            "this video, and is asking for a directional reshape — broader than a "
            "surgical tweak, more grounded than a total recast.\n\n"
            f"{_direction_line}"
            "RULES FOR THE REDRAFT:\n\n"
            "1) The PRIOR EDIT PLAN below is your STARTING STATE, not a constraint. "
            "Treat every prior decision as a soft default: keep it unless the user's "
            "direction (above) gives you a reason to change it.\n\n"
            "2) The user's direction is authoritative. Where it speaks to a category "
            "(pacing of a section, energy of the captions, presence of B-roll, "
            "character of the chapter break, etc.), let it OVERRIDE the prior plan in "
            "that category. Where it's SILENT on a category, the prior plan wins by "
            "default — do NOT redo decisions for novelty's sake. The user already "
            "approved those choices; touching them without cause erodes their trust.\n\n"
            "3) Carry-over is decision-level, not field-level. If the user says 'pace "
            "the middle faster', that may mean: shift some cuts later, drop a "
            "breather segment, change a zoom from SmoothPush to SnapReframe. Each of "
            "those is a deliberate consequence of the direction — appropriate. What "
            "would be WRONG: also changing the caption style, or swapping every "
            "transition, because those weren't asked for. Stay disciplined.\n\n"
            "4) The full editorial vocabulary from the rules above still applies. "
            "Components you ADD must follow the same placement rules (zoom-on-key-"
            "moments, transition-on-CUT-BOUNDARIES, tight_cut_overlay-on-TIGHT-"
            "BOUNDARIES with the per-type duration / title-required for SceneTitle, "
            "etc.). You can't bypass the rules by citing the prior plan; the prior "
            "plan is a default, not a license.\n\n"
            "5) The video's transcript / signals / face data below are FRESH — the "
            "pipeline regenerated all of it from the source. Word indices in the "
            "prior plan reference the OLD kept-only space; translate them to the "
            "NEW kept-only space (you'll see the new kept-transcript below) by "
            "matching on word text + approximate timestamp, NOT by raw index. The "
            "prior plan exists to inform editorial intent, not to be index-merged "
            "verbatim.\n\n"
            f"PRIOR EDIT PLAN (JSON):\n{json.dumps(_sanitized_prior, separators=(',', ':'))}\n"
            "════════════════════════════════════════════════════════════════════\n"
        )
        user_content_parts.append(guided_block)

    user_content = "\n\n".join(user_content_parts)

    return system_instruction, user_content


def infer_has_burned_captions(edit_plan, analysis_data=None, log_prefix=None):
    has_burned_captions = bool(
        ((analysis_data or {}).get("frame_layout") or {})
        .get("existing_overlays", {})
        .get("has_burned_captions")
    )
    if not has_burned_captions:
        notes = str((edit_plan or {}).get("notes") or "").lower()
        if "burned" in notes or "burned-in" in notes or "burn-in" in notes or "existing caption" in notes:
            has_burned_captions = True
            if log_prefix:
                print(f"{log_prefix} Detected burned-in captions from recipe notes", flush=True)
    if not has_burned_captions:
        caption_style = str((edit_plan or {}).get("caption_style") or "").lower()
        has_words = bool((edit_plan or {}).get("_deepgram_words"))
        if caption_style == "none" and has_words:
            has_burned_captions = True
            if log_prefix:
                print(f"{log_prefix} Inferred burned-in captions (caption_style=none but speech detected)", flush=True)
    return has_burned_captions


def build_analysis_from_gemini_recipe(edit_plan, duration):
    raw_frame_layout = edit_plan.get("frame_layout") or {}
    raw_existing = raw_frame_layout.get("existing_overlays") or {}
    raw_fq = edit_plan.get("footage_quality") or {}
    has_burned_captions = infer_has_burned_captions(
        edit_plan,
        analysis_data={"frame_layout": {"existing_overlays": raw_existing}},
    )

    parsed = {
        "duration": duration,
        "speech": {"has_speech": False, "speaker_style": "", "segments": [], "sentence_boundaries": []},
        "safe_cut_points": (
            [
                {"time": 0, "quality": 1.0, "why": "Video start"},
                {"time": round(duration * 1000) / 1000, "quality": 1.0, "why": "Video end"},
            ]
            if duration > 0 else []
        ),
        "video_profile": edit_plan.get("video_profile") or {},
        "frame_layout": {
            "subject_position": raw_frame_layout.get("subject_position") or "unknown",
            "existing_overlays": {
                "has_burned_captions": has_burned_captions,
                "has_text_graphics": bool(raw_existing.get("has_text_graphics")),
                "overlay_locations": raw_existing.get("overlay_locations") or ("captions visible in-frame" if has_burned_captions else "none detected"),
            },
            "free_zones": raw_frame_layout.get("free_zones") or "unknown",
        },
        "color_baseline": edit_plan.get("color_baseline") or {},
        "footage_quality": {
            **raw_fq,
            "has_burned_captions": has_burned_captions,
        },
        "audio": {"speech_source": "none"},
        "shots": [{
            "start": 0,
            "end": duration,
            "visual": "",
            "action": "Full video",
            "energy": 0.5,
            "editing_value": "usable",
            "delivery": "none",
        }],
    }
    analysis = normalize_analysis(parsed)
    analysis["visual_cuts"] = []
    analysis["beat_timestamps"] = []
    analysis["tightened_timeline"] = {}
    analysis["content_mode"] = "speech"
    return analysis


def _coalesce_caption_position_segments(segments, min_dur=1.5):
    """Drop sub-min_dur caption position segments and merge same-position
    neighbors. Gemini sometimes emits adjacent caption_position_changes that
    produce a sub-second segment in the middle (e.g. center for one word,
    then back to bottom). Visually that's a flash up and back — every
    caption component fades each page in/out for ~150ms, so a 0.5s segment
    with 1-2 caption pages reads as captions stacking, drifting, or
    jumping position. Anything shorter than min_dur is absorbed into the
    previous segment's position; if it's the FIRST segment, it inherits
    the next segment's position. Then adjacent same-position segments
    merge."""
    if not segments or len(segments) < 2:
        return segments
    out: List[dict] = []
    for seg in segments:
        seg_dur = seg["to_seconds"] - seg["from_seconds"]
        if seg_dur < min_dur and out:
            # Absorb into previous segment.
            print(
                f"[caption-segments] dropped flicker {seg_dur:.2f}s "
                f"@ {seg['from_seconds']:.2f}s ({seg['position']}) — "
                f"absorbed into previous '{out[-1]['position']}'",
                flush=True,
            )
            out[-1]["to_seconds"] = seg["to_seconds"]
        elif seg_dur < min_dur and not out:
            # First segment is short — keep it as a placeholder; the next
            # iteration will overwrite its position.
            out.append(dict(seg))
        else:
            if (
                out
                and (out[-1]["to_seconds"] - out[-1]["from_seconds"]) < min_dur
            ):
                # Previous (kept) was an opening flicker — overwrite its
                # position with the current long segment's position.
                print(
                    f"[caption-segments] dropped opening flicker "
                    f"({out[-1]['position']}) — replaced with "
                    f"following '{seg['position']}'",
                    flush=True,
                )
                out[-1]["position"] = seg["position"]
                out[-1]["to_seconds"] = seg["to_seconds"]
            else:
                out.append(dict(seg))
    # Merge adjacent same-position segments.
    merged: List[dict] = []
    for seg in out:
        if merged and merged[-1]["position"] == seg["position"]:
            merged[-1]["to_seconds"] = seg["to_seconds"]
        else:
            merged.append(seg)
    return merged


def _force_caption_position_around_overlays(
    segments, motion_graphics, broll_frame_ranges
):
    """Frame-precise AUTHORITATIVE caption-position override during MG and
    B-roll windows. Returns a new contiguous segment list.

    The system prompt promises "the pipeline owns caption position during MG
    and B-roll windows" and explicitly tells Gemini NOT to emit
    caption_position_changes that overlap those windows. This function is
    the code side of that contract. Any caption_position_change Gemini
    emitted that lands inside an MG or B-roll window is OVERRIDDEN here
    in favor of the deterministic zone-clearing rule below.

    Per-frame zone-occupancy rule:

      B-roll alone               → captions forced to TOP
        B-roll is a full-canvas cutaway. "bottom" sits near the platform
        UI rail; "center" lands on the focal subject of the cutaway.
        "top" is the readable safe zone.

      MG occupies TOP only       → captions forced to BOTTOM
        Notification always renders top (drop-down animation), and any
        MG with anchor="top" reaches into the upper-third safe zone.

      MG occupies BOTTOM only    → captions forced to TOP
        MG with anchor="bottom" sits in the lower-third where captions
        default.

      Both TOP and BOTTOM occupied in the same frames → captions to CENTER
        Two overlapping MGs (top + bottom anchored) squeeze the caption
        track into the middle. Rare but real on dense payoffs.

      MG at center / left / right (only)                  → no override
        Captions stay where Gemini placed them.

    Every per-sub-segment reposition is logged via _record_divergence so
    `grep '\\[divergence\\] component=caption_position'` surfaces the
    exact frames + zones + reasons.

    Pure layout pass — no prompt-side rule for Gemini to remember. Inputs
    already projected to output frames so the override is frame-precise.
    """
    if not segments:
        return segments
    if not motion_graphics and not broll_frame_ranges:
        return segments

    # MG windows that occupy a caption-relevant zone (top or bottom).
    # Notifications render top regardless of anchor (drop-down animation).
    mg_windows = []  # (from_frame, to_frame, zone)
    for _mg in motion_graphics or []:
        _mg_type = str(_mg.get("type") or "")
        _mg_anchor = str((_mg.get("props") or {}).get("anchor") or "")
        _effective_pos = "top" if _mg_type == "Notification" else _mg_anchor
        if _effective_pos in ("top", "bottom"):
            _ff = int(_mg.get("fromFrame") or 0)
            _tf = _ff + int(_mg.get("durationInFrames") or 0)
            if _tf > _ff:
                mg_windows.append((_ff, _tf, _effective_pos))

    broll_windows = [
        (int(_f), int(_t)) for _f, _t in (broll_frame_ranges or []) if int(_t) > int(_f)
    ]

    if not mg_windows and not broll_windows:
        return segments

    # Collect every frame boundary that could change the override decision.
    boundaries = set()
    for s in segments:
        boundaries.add(int(s["fromFrame"]))
        boundaries.add(int(s["toFrame"]))
    for _ff, _tf, _ in mg_windows:
        boundaries.add(_ff)
        boundaries.add(_tf)
    for _ff, _tf in broll_windows:
        boundaries.add(_ff)
        boundaries.add(_tf)
    sorted_b = sorted(boundaries)

    out: List[dict] = []
    n_mg_overrides = 0
    n_broll_overrides = 0
    n_both_overrides = 0

    for i in range(len(sorted_b) - 1):
        a, b = sorted_b[i], sorted_b[i + 1]
        if a >= b:
            continue

        # Original caption position (Gemini's choice) for this sub-range.
        orig_pos = None
        for s in segments:
            if int(s["fromFrame"]) <= a < int(s["toFrame"]):
                orig_pos = s["position"]
                break

        # Inside a B-roll window?
        in_broll = any(_ff <= a and _tf >= b for _ff, _tf in broll_windows)

        # Which MG zones (top / bottom) are occupied in [a, b)?
        zones_occupied = set()
        for _ff, _tf, _zone in mg_windows:
            if _ff <= a and _tf >= b:
                zones_occupied.add(_zone)

        # Decide override (B-roll takes precedence — full-canvas always
        # wants "top" regardless of which MG zones happen to overlap).
        forced = None
        reason = None
        if in_broll:
            forced = "top"
            reason = "broll_window"
        elif zones_occupied == {"top", "bottom"}:
            forced = "center"
            reason = "mg_top_and_bottom_both_occupied"
        elif "top" in zones_occupied:
            forced = "bottom"
            reason = "mg_at_top"
        elif "bottom" in zones_occupied:
            forced = "top"
            reason = "mg_at_bottom"

        # A forced (B-roll / MG-zone) position ALWAYS wins — even when the
        # projected input segments left a gap here (orig_pos is None). This is
        # the suppression fix: the old early `if orig_pos is None: continue`
        # skipped a B-roll window with no covering input segment BEFORE this
        # decision, dropping captions over the cutaway entirely. `forced` is
        # now computed first. For a genuine NON-forced gap, fall back to the
        # previous segment's position (or the "bottom" default) so a caption
        # page can never land in a hole and render nowhere. Bit-identical on
        # renders whose segments tile (orig_pos never None → branch never fires).
        pos = forced if forced is not None else orig_pos
        if pos is None:
            pos = out[-1]["position"] if out else "bottom"

        if forced is not None and forced != orig_pos:
            _record_divergence(
                "caption_position",
                {"from_frame": a, "to_frame": b, "position": orig_pos},
                "force_clear_of_overlay",
                final={"from_frame": a, "to_frame": b, "position": forced},
                reason=f"forced_clear_of_mg_or_broll:{reason}",
            )
            if in_broll:
                n_broll_overrides += 1
            elif reason == "mg_top_and_bottom_both_occupied":
                n_both_overrides += 1
            else:
                n_mg_overrides += 1

        # Coalesce adjacent same-position sub-segments.
        if out and out[-1]["position"] == pos and int(out[-1]["toFrame"]) == a:
            out[-1]["toFrame"] = b
        else:
            out.append({"fromFrame": a, "toFrame": b, "position": pos})

    if n_mg_overrides or n_broll_overrides or n_both_overrides:
        print(
            f"[caption-segments] authoritative override pass: "
            f"MG repositions={n_mg_overrides}, "
            f"B-roll repositions={n_broll_overrides}, "
            f"both-zones-occupied=>center repositions={n_both_overrides} "
            f"(across {len(mg_windows)} MG window(s), "
            f"{len(broll_windows)} B-roll window(s))",
            flush=True,
        )

    return out


# ═══════════════════════════════════════════════════════════════════════════
# MECHANICAL CUTS — captions.ai-style deterministic detection
# ═══════════════════════════════════════════════════════════════════════════
# Replaces the previous Gemini-based cuts decision step. Four mechanical
# detectors run in pure Python on the Deepgram word list and produce the
# same remove_words shape the downstream pipeline already consumes.
#
# Categories (all mechanical, no judgment):
#   - dead_air:    gap between consecutive kept-word pairs > threshold
#   - filler:      words matching literal hesitation-token whitelist
#   - false_start: Deepgram-tagged incomplete words (trailing hyphen)
#   - stutter:     same-speaker word/prefix repetition within tight gap
#
# Why mechanical: AI judgment at the cut layer produced surgical mid-phrase
# fragmentation and cross-speaker stutter swaps. Mechanical detection is
# deterministic, ~150 lines, runs in milliseconds, matches the approach
# used by captions.ai / Opus Clip / Submagic. AI is preserved for the
# post-cut editorial layer (component placement, captions, transitions)
# where judgment is genuinely the point.

# Hesitation tokens. These are always filler; they have no semantic role
# in talking-head dialogue. Matched via regex so any elongation count
# (um, umm, ummm, ummmm, uhhhhh, ahhhhhh, …) is caught — Deepgram preserves
# whatever the speaker actually drew out, and we don't want the cut to
# depend on how many m's they held.
import re as _re_filler
_FILLER_HESITATION_REGEX = _re_filler.compile(
    r"^(?:"
    r"u+m+"        # um, umm, ummm, ummmm, …
    r"|u+h+m*"     # uh, uhh, uhm, uhhh, uhmm, …
    r"|e+r+m*"     # er, err, erm, erm…
    r"|a+h+"       # ah, ahh, ahhh, …
    r"|h+m+"       # hm, hmm, hmmm, …
    r"|m+h+m*"     # mhm, mhmm, mmhm, …
    r"|m+"         # mm, mmm (only as standalone hesitation)
    r")$",
    _re_filler.IGNORECASE,
)

# Parenthetical filler phrases — only cut when comma-wrapped (the speaker
# inserted them as a verbal tic between thoughts, not as semantic content).
# "we're, like, amazing" → cut "like,". "I like pizza" → keep (no commas).
# "and, you know, showing" → cut both "you" and "know,".
_PAREN_FILLER_SINGLE: frozenset = frozenset({
    "like",
})
# Multi-word phrases — matched as a contiguous comma-wrapped sequence.
_PAREN_FILLER_MULTI: tuple = (
    ("you", "know"),
    ("i", "mean"),
)

# Two same-speaker words within this gap (seconds) and matching the
# stutter signature are treated as stutter. Above this gap, the repeat
# is more likely rhetorical ("very, very good") or a natural restart.
_STUTTER_MAX_GAP_S: float = 0.20

def _word_lemma(word: dict) -> str:
    """Lowercase, punctuation-stripped word text for matching."""
    text = (word.get("punctuated_word") or word.get("word") or "")
    return "".join(ch.lower() for ch in text if ch.isalpha())


# ─── Silero VAD ─────────────────────────────────────────────────────────────
# Replaces the previous transcript-word-gap dead_air heuristic. Word boundary
# timestamps mark phoneme ends, not where audio drops to silence — a transcript
# gap of 1.2s is typically only 0.7-1.0s of actual silence sandwiched between
# 100-300ms of audible tail on each side. Cutting at word boundaries cuts
# INTO audible content. Every professional auto-editor (Auto-Editor, Premiere
# auto-trim, FireCut, Auphonic, Captions.ai) uses audio amplitude or VAD on
# the actual waveform; Descript's transcript-gap approach is the industry
# outlier and gets persistent user complaints about cutting in wrong places.
#
# Silero VAD specs: 2MB neural model, MIT license, CPU-only inference at
# ~1ms per 30ms chunk, 97% ROC-AUC. Correctly distinguishes natural breath
# and lip noise (which we want to KEEP) from true dead air (which we want
# to CUT). Module-level model cache so first call pays the ~50ms load and
# every subsequent render reuses it.
_SILERO_VAD_MODEL = None


def _load_silero_vad():
    """Lazy-load Silero VAD model. Cached at module level."""
    global _SILERO_VAD_MODEL
    if _SILERO_VAD_MODEL is None:
        from silero_vad import load_silero_vad
        _SILERO_VAD_MODEL = load_silero_vad()
        print("[silero-vad] model loaded", flush=True)
    return _SILERO_VAD_MODEL


def _get_audio_stream_offset_seconds(source_path: str) -> float:
    """Probe the source file's audio stream `start_time` via ffprobe.

    iPhone-recorded mp4s frequently carry a non-zero audio_stream.start_time
    (~184ms typical) that ffmpeg strips when extracting raw audio. Deepgram
    word timestamps reach `compute_mechanical_cuts` AFTER the pipeline has
    shifted them forward by this offset to file-time. Silero VAD reads
    audio from the same file via the same ffmpeg path — also strips the
    offset — so its timestamps are in audio-data-time. To compare VAD
    output against Deepgram word timestamps in the same coordinate space,
    we add the offset to every VAD timestamp here.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=start_time",
                "-of", "csv=p=0",
                source_path,
            ],
            capture_output=True, text=True, timeout=10, check=True,
        )
        val = result.stdout.strip()
        if not val or val == "N/A":
            return 0.0
        return max(0.0, float(val))
    except Exception:
        return 0.0


def _detect_silence_regions_vad(
    source_path: str,
    min_silence_s: float = 0.30,
) -> list:
    """Run Silero VAD on the source audio and return silence regions.

    Returns a list of (start_s, end_s) tuples for every region where the
    model classifies the audio as non-speech for ≥ min_silence_s.
    Coordinates are in FILE-TIME (same frame of reference as the Deepgram
    word timestamps after pipeline offset compensation). For sources with
    non-zero audio_stream.start_time, the offset is added so VAD output
    aligns with word.start / word.end.

    Defensive audio path: extracts a 16kHz mono PCM wav via ffmpeg before
    handing to Silero, rather than relying on torchaudio's ffmpeg backend
    to read mp4 directly. This eliminates a class of torchaudio-codec
    edge cases (some mp4s with AAC + container metadata quirks fail
    `torchaudio.load()` even when ffmpeg can decode them fine).
    """
    try:
        from silero_vad import read_audio, get_speech_timestamps
    except Exception as e:
        print(f"[silero-vad] import failed: {e} — skipping VAD pass", flush=True)
        return []

    # Extract 16kHz mono wav via ffmpeg — known-good format for Silero.
    tmp_wav = None
    try:
        import tempfile
        tmp_fd, tmp_wav = tempfile.mkstemp(suffix="_vad.wav", prefix="silero_")
        os.close(tmp_fd)
        _t0 = time.time()
        _ext = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", source_path,
                "-vn", "-ar", "16000", "-ac", "1",
                "-f", "wav", tmp_wav,
            ],
            capture_output=True, text=True, timeout=120,
        )
        if _ext.returncode != 0:
            print(
                f"[silero-vad] ffmpeg audio extract failed (rc={_ext.returncode}): "
                f"{_ext.stderr[-300:] if _ext.stderr else ''} — skipping VAD",
                flush=True,
            )
            return []
        if not os.path.exists(tmp_wav) or os.path.getsize(tmp_wav) < 1024:
            print(f"[silero-vad] ffmpeg produced empty/missing wav — skipping VAD", flush=True)
            return []
        print(
            f"[silero-vad] extracted 16kHz mono wav in {time.time() - _t0:.1f}s "
            f"({os.path.getsize(tmp_wav) // 1024}KB)",
            flush=True,
        )

        model = _load_silero_vad()
        sample_rate = 16000

        try:
            wav = read_audio(tmp_wav, sampling_rate=sample_rate)
        except Exception as e:
            print(f"[silero-vad] read_audio failed: {e} — skipping VAD", flush=True)
            return []

        speech = get_speech_timestamps(
            wav, model,
            sampling_rate=sample_rate,
            # min silence to register a speech boundary — anything shorter is
            # treated as continuous speech (covers natural in-breath).
            min_silence_duration_ms=int(min_silence_s * 1000),
            # 100ms minimum speech segment so spurious tiny blips inside
            # silence regions don't fragment them into sub-threshold chunks.
            min_speech_duration_ms=100,
            threshold=0.5,
        )

        # Audio-stream-offset compensation. See _get_audio_stream_offset_seconds.
        offset = _get_audio_stream_offset_seconds(source_path)
        if offset > 0.001:
            print(
                f"[silero-vad] audio_stream_offset={offset*1000:.0f}ms — "
                f"shifting VAD timestamps to file-time",
                flush=True,
            )

        audio_dur_s = float(len(wav)) / float(sample_rate)
        silence_regions: list = []
        prev_end = 0.0
        for seg in speech:
            seg_start = float(seg["start"]) / float(sample_rate)
            seg_end = float(seg["end"]) / float(sample_rate)
            if seg_start > prev_end:
                silence_regions.append((prev_end + offset, seg_start + offset))
            prev_end = seg_end
        if prev_end < audio_dur_s:
            silence_regions.append((prev_end + offset, audio_dur_s + offset))

        silence_regions = [
            (s, e) for (s, e) in silence_regions if (e - s) >= min_silence_s
        ]
        return silence_regions

    finally:
        if tmp_wav and os.path.exists(tmp_wav):
            try:
                os.remove(tmp_wav)
            except Exception:
                pass


# ─── pyannote speaker diarization ─────────────────────────────────────────────
# Deepgram's per-word and per-utterance speaker labels are unreliable on
# 2-speaker interview content even when the voices are trivially separable.
# pyannote.audio 3.1 is the SOTA open-source diarization model (ECAPA-TDNN
# embeddings + agglomerative clustering on segmentation 3.0 turns) and is
# what every serious self-hosted transcription stack uses. We run it on the
# orchestrator's H100 (negligible compute cost — ~1-2s per minute of audio
# on GPU) and use its segment boundaries to override Deepgram's per-word
# speaker labels.
#
# Models are gated on HuggingFace. HF_TOKEN comes from the `huggingface`
# Modal secret. When unset, _load_pyannote returns None and diarization
# silently falls back to Deepgram's native labels.
_PYANNOTE_PIPELINE = None
_PYANNOTE_LOAD_FAILED = False


def _load_pyannote():
    """Lazy-load pyannote speaker-diarization-3.1 pipeline. Cached at module level.

    Returns None on any failure (missing HF_TOKEN, network error during
    model download, etc.) — caller must handle None gracefully and fall
    back to Deepgram diarization.
    """
    global _PYANNOTE_PIPELINE, _PYANNOTE_LOAD_FAILED
    if _PYANNOTE_PIPELINE is not None:
        return _PYANNOTE_PIPELINE
    if _PYANNOTE_LOAD_FAILED:
        return None

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN missing — pyannote cannot load the diarization model. "
            "Production is supposed to have the `huggingface` Modal secret "
            "attached with HF_TOKEN=hf_... If this fired, the secret was "
            "removed or the environment is misconfigured. Fix the secret; "
            "don't restore a silent Deepgram-labels fallback."
        )

    from pyannote.audio import Pipeline
    import torch

    _t0 = time.time()
    # Don't pass an auth kwarg explicitly. pyannote.audio and huggingface_hub
    # have version-coupled signatures — older pyannote takes `use_auth_token`,
    # newer huggingface_hub takes `token`, and our pyannote 3.3 forwards
    # `use_auth_token` to a newer huggingface_hub that rejects it. The clean
    # path: rely on the HF_TOKEN env var (both libs pick it up internally).
    # We confirmed HF_TOKEN above, so set it for the child loaders defensively.
    os.environ.setdefault("HF_TOKEN", hf_token)
    os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", hf_token)
    # No except: with huggingface_hub pinned <0.26, the previous
    # use_auth_token failure cannot recur. If from_pretrained still raises,
    # it's a genuine model-access or HF API issue and we want the render
    # to surface it loudly so we can fix the root cause — not silently
    # degrade to Deepgram speaker labels.
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
    )

    try:
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
            print(f"[pyannote] pipeline loaded on cuda in {time.time()-_t0:.1f}s", flush=True)
        else:
            print(f"[pyannote] pipeline loaded on cpu in {time.time()-_t0:.1f}s (no CUDA)", flush=True)
    except Exception as e:
        print(f"[pyannote] .to(cuda) failed: {e} — running on CPU", flush=True)

    _PYANNOTE_PIPELINE = pipeline
    return pipeline


def diarize_with_pyannote(source_path: str) -> list:
    """Run pyannote speaker diarization on the source audio.

    Returns a list of {"start": float, "end": float, "speaker": int}
    segments in FILE-TIME (audio_stream.start_time offset applied so the
    coordinates match the Deepgram word timestamps after the pipeline
    offset shift in _get_resolved_transcript).

    Returns [] on any failure (missing HF_TOKEN, model load failure, audio
    extraction failure) — caller falls back to Deepgram's per-word labels.
    Speaker integers are mapped from pyannote's "SPEAKER_00", "SPEAKER_01",
    ... strings to 0, 1, ... in order of first appearance, matching
    Deepgram's numbering convention.
    """
    pipeline = _load_pyannote()
    if pipeline is None:
        return []

    # Defensive audio extraction: 16kHz mono wav via ffmpeg, same pattern
    # as Silero VAD. pyannote can read mp4 directly via torchaudio but
    # we've seen torchaudio choke on certain container/codec combos that
    # ffmpeg handles fine, so route everything through ffmpeg.
    import tempfile
    tmp_fd, tmp_wav = tempfile.mkstemp(suffix="_pyannote.wav", prefix="pyannote_")
    os.close(tmp_fd)
    try:
        _t0 = time.time()
        _ext = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", source_path,
                "-vn", "-ar", "16000", "-ac", "1",
                "-f", "wav", tmp_wav,
            ],
            capture_output=True, text=True, timeout=120,
        )
        if _ext.returncode != 0 or not os.path.exists(tmp_wav) or os.path.getsize(tmp_wav) < 1024:
            print(
                f"[pyannote] ffmpeg audio extract failed (rc={_ext.returncode}): "
                f"{(_ext.stderr or '')[-300:]} — skipping diarization",
                flush=True,
            )
            return []
        print(
            f"[pyannote] extracted 16kHz mono wav in {time.time()-_t0:.1f}s "
            f"({os.path.getsize(tmp_wav) // 1024}KB)",
            flush=True,
        )

        _t1 = time.time()
        try:
            diarization = pipeline(tmp_wav)
        except Exception as e:
            print(f"[pyannote] pipeline inference failed: {e} — falling back to Deepgram labels", flush=True)
            return []
        print(f"[pyannote] diarization inference completed in {time.time()-_t1:.1f}s", flush=True)

        # Map pyannote SPEAKER_NN strings to integer speakers (0, 1, ...)
        # in order of first appearance. This matches Deepgram's convention
        # so downstream code that filters by speaker int doesn't care which
        # diarizer produced the labels.
        label_to_int: dict = {}
        segments: list = []
        offset = _get_audio_stream_offset_seconds(source_path)
        if offset > 0.001:
            print(
                f"[pyannote] audio_stream_offset={offset*1000:.0f}ms — "
                f"shifting segment timestamps to file-time",
                flush=True,
            )

        for turn, _track, label in diarization.itertracks(yield_label=True):
            if label not in label_to_int:
                label_to_int[label] = len(label_to_int)
            segments.append({
                "start": float(turn.start) + offset,
                "end": float(turn.end) + offset,
                "speaker": label_to_int[label],
            })

        if not segments:
            print("[pyannote] no segments produced — falling back to Deepgram labels", flush=True)
            return []

        # Sort by start time so the binary-ish merge in
        # apply_pyannote_speakers can scan in order.
        segments.sort(key=lambda s: s["start"])

        speaker_count = len(label_to_int)
        total_speech = sum(s["end"] - s["start"] for s in segments)
        print(
            f"[pyannote] {len(segments)} segments, {speaker_count} speaker(s), "
            f"{total_speech:.1f}s total speech",
            flush=True,
        )
        return segments

    finally:
        if tmp_wav and os.path.exists(tmp_wav):
            try:
                os.remove(tmp_wav)
            except Exception:
                pass


def apply_pyannote_speakers(words: list, segments: list) -> None:
    """Override per-word speaker labels using pyannote segments. Mutates `words`.

    For each Deepgram word, finds the pyannote segment that contains its
    midpoint and overwrites word["speaker"] with that segment's speaker.
    Words that fall outside any pyannote segment (gaps / non-speech in
    pyannote's output) keep their existing Deepgram speaker label — pyannote
    might have classified the region as non-speech but Deepgram still
    transcribed something there, and Deepgram's label is the best signal
    we have for those words.

    No-op when segments is empty (caller fell through to Deepgram).
    """
    if not segments or not words:
        return

    overrides = 0
    no_match = 0
    cursor = 0
    n_segs = len(segments)
    for w in words:
        if not isinstance(w, dict):
            continue
        try:
            w_start = float(w.get("start") or 0.0)
            w_end = float(w.get("end") or 0.0)
        except (TypeError, ValueError):
            continue
        mid = (w_start + w_end) / 2.0 if w_end > w_start else w_start

        # Advance cursor while current segment ends before the word midpoint.
        # segments are sorted by start, but they can overlap (rare; pyannote
        # produces near-disjoint turns for typical 2-speaker content), so
        # we don't strictly require monotonic non-overlap here — just use
        # cursor as a starting hint and scan forward until we find a hit.
        while cursor < n_segs and segments[cursor]["end"] < mid:
            cursor += 1

        matched_speaker = None
        for i in range(cursor, n_segs):
            seg = segments[i]
            if seg["start"] > mid:
                break
            if seg["start"] <= mid <= seg["end"]:
                matched_speaker = seg["speaker"]
                break

        if matched_speaker is None:
            no_match += 1
            continue

        if w.get("speaker") != matched_speaker:
            overrides += 1
        w["speaker"] = matched_speaker

    print(
        f"[pyannote] applied speaker labels to {len(words)} words: "
        f"{overrides} overrides vs Deepgram, {no_match} kept Deepgram label "
        f"(outside pyannote segments)",
        flush=True,
    )


def detect_dead_air(
    words: list,
    removed_so_far: set,
    source_path: str = None,
    min_silence_s: float = 1.0,
) -> list:
    """Find consecutive kept-word pairs separated by VAD-confirmed silence.

    Uses Silero VAD on the actual audio waveform to detect true silence
    regions (not transcript word gaps). For each consecutive pair of
    kept words, measure how much of the gap [word[A].end, word[B].start]
    actually consists of VAD-detected silence. Cut only when the
    confirmed silence in the gap exceeds `min_silence_s`.

    This preserves natural conversation rhythm (1-2s pauses with breath/
    lip-noise are NOT silent per VAD) while removing genuine dead air
    (1+ second of true non-voice audio per VAD's neural classifier).

    Falls back to transcript-gap heuristic if VAD is unavailable or the
    source_path is missing — same threshold semantics, less accurate.
    """
    out: list = []
    n = len(words)
    if n < 2:
        return out
    kept = [i for i in range(n) if i not in removed_so_far]
    if len(kept) < 2:
        return out

    # Silero VAD is the source of truth for dead-air detection. No except
    # wrapping — the prior transcript-gap fallback was masking VAD failures
    # (Silero model load issues, bad audio extraction). If VAD fails we want
    # to see the real error and fix it, not silently degrade to a less
    # accurate heuristic that produces worse cut decisions.
    silence_regions = _detect_silence_regions_vad(
        source_path, min_silence_s=0.15,
    )
    print(
        f"[silero-vad] detected {len(silence_regions)} silence region(s) "
        f"≥150ms in source audio",
        flush=True,
    )

    # VAD path: cut each kept-word gap whose VAD-confirmed silence overlap
    # exceeds the gap's threshold. Three tiers, keyed off the punctuation
    # on the preceding word — sentence breaks should be tight (a real editor
    # cuts a 0.3s pause after a question), comma breaks should be loose-
    # but-not-flabby, and mid-clause pauses should preserve natural thinking
    # rhythm except when they cross into genuine dead-air territory.
    SENTENCE_END_THRESHOLD = 0.25   # after . ? !
    COMMA_END_THRESHOLD = 0.50      # after ,
    MID_CLAUSE_THRESHOLD = 0.70     # no punctuation on preceding word
    for a, b in zip(kept, kept[1:]):
        gap_start = float(words[a].get("end") or 0.0)
        gap_end = float(words[b].get("start") or 0.0)
        if gap_end <= gap_start:
            continue
        silence_in_gap = 0.0
        for sil_start, sil_end in silence_regions:
            ovl_start = max(sil_start, gap_start)
            ovl_end = min(sil_end, gap_end)
            if ovl_end > ovl_start:
                silence_in_gap += ovl_end - ovl_start
        _prev_text = str(
            words[a].get("punctuated_word") or words[a].get("word") or ""
        ).rstrip()
        if _prev_text.endswith((".", "?", "!")):
            _threshold = SENTENCE_END_THRESHOLD
        elif _prev_text.endswith(","):
            _threshold = COMMA_END_THRESHOLD
        else:
            _threshold = MID_CLAUSE_THRESHOLD
        if silence_in_gap >= _threshold:
            out.append({
                "after_word_index": a,
                "before_word_index": b,
                "reason": "dead_air",
            })
    return out


def _ends_with_comma(word: dict) -> bool:
    """True when the punctuated form of the word ends with a comma."""
    text = str(word.get("punctuated_word") or word.get("word") or "").rstrip()
    return text.endswith(",")


def detect_filler(words: list) -> list:
    """Three filler classes, all deterministic, all word-boundary-clean:

    (1) Hesitation tokens — um/uh/er/ah/hmm/mhm/mm with any elongation
        ("ummmmm", "uhhhhh"). Always cut; these have no semantic role.

    (2) Parenthetical single-word fillers — "like" when surrounded by
        commas in Deepgram's punctuated output. "we're, like, amazing"
        → cut "like,". "I like pizza" stays because no commas wrap it.

    (3) Parenthetical multi-word phrases — "you know", "I mean" when
        the sequence is comma-wrapped. Both words are cut together.

    Other words the user explicitly does NOT want cut (literally, basically,
    actually, really) are deliberately not in any list.
    """
    out: list = []
    n = len(words)
    consumed: set = set()  # indices already claimed by a multi-word match

    for i, w in enumerate(words):
        if i in consumed:
            continue
        lemma = _word_lemma(w)

        # (1) hesitation tokens with any elongation
        if lemma and _FILLER_HESITATION_REGEX.match(lemma):
            out.append({"word_index": i, "reason": "filler"})
            continue

        # (3) multi-word parenthetical filler (try before single-word so
        # "you know" wins over a hypothetical single-word match on "you")
        matched_multi = False
        for phrase in _PAREN_FILLER_MULTI:
            plen = len(phrase)
            if i + plen > n:
                continue
            if any(_word_lemma(words[i + k]) != phrase[k] for k in range(plen)):
                continue
            # Comma-wrapping check: word BEFORE the phrase ends with comma,
            # AND the last word of the phrase ends with comma. This is the
            # signature of "..., you know, ..." vs "you know what I mean".
            prev_ok = (i == 0) or _ends_with_comma(words[i - 1])
            last_ok = _ends_with_comma(words[i + plen - 1])
            if prev_ok and last_ok:
                for k in range(plen):
                    out.append({"word_index": i + k, "reason": "filler"})
                    consumed.add(i + k)
                matched_multi = True
                break
        if matched_multi:
            continue

        # (2) single-word parenthetical filler ("like")
        if lemma in _PAREN_FILLER_SINGLE:
            prev_ok = (i > 0) and _ends_with_comma(words[i - 1])
            self_ok = _ends_with_comma(w)
            if prev_ok and self_ok:
                out.append({"word_index": i, "reason": "filler"})

    return out


def detect_false_start(words: list) -> list:
    """Deepgram tags incomplete words with a trailing hyphen ("wh-",
    "shou-"). These are always false starts — the speaker abandoned
    the word mid-pronunciation. Returns a list of {word_index, reason}.
    """
    out: list = []
    for i, w in enumerate(words):
        text = (w.get("punctuated_word") or w.get("word") or "").rstrip()
        if len(text) > 1 and text.endswith("-"):
            out.append({"word_index": i, "reason": "false_start"})
    return out


def detect_stutter(words: list) -> list:
    """Detect within-speaker full-word stutter repeats.

    Signature: same lemma appearing 2+ times in a row, same speaker, with
    gap < _STUTTER_MAX_GAP_S between each. Keep the LAST instance; cut
    every earlier one ("I I told" → cut first "I"; "the the cat" → cut
    first "the"). Same lemma both sides is unambiguous — it's mathematically
    a repetition, not a coincidence.

    Speaker awareness is enforced strictly via the `speaker` field on each
    word: a repeat across different speakers is NEVER a stutter — it's two
    different people saying the same word.

    The earlier "phoneme-prefix false start" pass (a short word that's a
    prefix of the next word) was removed — it false-positived on common
    pronoun-then-contraction patterns ("that" → "that's", "she" → "she's"),
    cutting real words. The cost: real phonemic onsets Deepgram split into
    separate tokens stay in the audio. The benefit: zero risk of cutting a
    complete word via this detector.
    """
    out: list = []
    n = len(words)
    if n < 2:
        return out

    # Pass 1 — full word repeat chains.
    i = 0
    cut_idx: set = set()
    while i < n - 1:
        lemma_i = _word_lemma(words[i])
        spk_i = int(words[i].get("speaker") or 0)
        if not lemma_i:
            i += 1
            continue
        chain_end = i
        j = i + 1
        while j < n:
            lemma_j = _word_lemma(words[j])
            spk_j = int(words[j].get("speaker") or 0)
            gap = float(words[j].get("start") or 0.0) - float(words[chain_end].get("end") or 0.0)
            if lemma_j == lemma_i and spk_j == spk_i and gap < _STUTTER_MAX_GAP_S:
                chain_end = j
                j += 1
            else:
                break
        if chain_end > i:
            for k in range(i, chain_end):
                if k not in cut_idx:
                    out.append({"word_index": k, "reason": "stutter"})
                    cut_idx.add(k)
        i = chain_end + 1

    # NOTE: Pass 2 — "phoneme-prefix false starts" — REMOVED.
    #
    # Previously this pass cut a short word whose lemma was a prefix of the
    # next word's lemma (e.g., "th" before "that" — a phonemic onset that
    # Deepgram tokenized as a separate word). Even with strict length caps,
    # the rule cannot tell text-only whether "she she's gone" is a stutter
    # or two sentences, and the user reported real words ("that" before
    # "that's") being silently cut mid-video.
    #
    # The cost of removing this pass: real phonemic onsets stay in the
    # audio (a 50-100ms "th" before "that" plays as a brief aborted onset).
    # The benefit: zero risk of cutting any complete word via this path.
    # Full-word repeats ("the the", "I I told you") are still caught by
    # Pass 1 above — that rule is unambiguous (same lemma both sides).

    return out


def compute_mechanical_cuts(
    deepgram_words: list,
    source_path: str = None,
    min_silence_s: float = 1.0,
) -> dict:
    """Replace the cuts Gemini call with mechanical detection.

    Runs four detectors and returns a CutPlan-shaped dict matching the
    legacy result shape (notes/remove_words/pacing) so downstream code
    is unchanged. Detector order matters: word-level detectors
    (filler/false_start/stutter) run first to build the removed-set;
    dead_air runs last so its anchors only reference surviving words.

    `source_path` is forwarded to detect_dead_air for Silero VAD-based
    silence detection. When provided, VAD reads the audio waveform and
    cuts only gaps containing ≥ min_silence_s of true silence. When
    omitted, falls back to a transcript-gap heuristic with a more
    conservative threshold.
    """
    if not deepgram_words:
        return {"notes": "", "remove_words": [], "pacing": "fast"}

    fillers = detect_filler(deepgram_words)
    false_starts = detect_false_start(deepgram_words)
    stutters = detect_stutter(deepgram_words)
    word_removals = fillers + false_starts + stutters

    removed_so_far: set = set()
    for item in word_removals:
        wi = item.get("word_index")
        if isinstance(wi, int):
            removed_so_far.add(wi)

    dead_airs = detect_dead_air(
        deepgram_words, removed_so_far,
        source_path=source_path,
        min_silence_s=min_silence_s,
    )

    notes = (
        f"Mechanical cuts: {len(dead_airs)} dead_air, "
        f"{len(fillers)} filler, "
        f"{len(false_starts)} false_start, "
        f"{len(stutters)} stutter"
    )

    return {
        "notes": notes,
        "remove_words": word_removals + dead_airs,
        # Uniform pacing — captions.ai-style consistency. Vibe/intensity
        # affect the post-cut editorial layer (caption style, MG choice,
        # transition palette), not the cut layer itself.
        "pacing": "fast",
    }


def _remove_words_to_src_indices(remove_words, deepgram_words):
    """Resolve every entry in remove_words to a set of source-word indices.

    Three accepted entry shapes (see _RemoveWord schema for full doc):
      (a) {"word_index": int}                                    — single
      (b) {"after_word_index": int, "before_word_index": int}    — range,
          removes every word with index in (after, before) exclusive.
      (c) {"start": float, "end": float}                         — legacy
          float-range; removes every word whose [start, end] is fully
          contained in [rs, re]. Kept for silence-tighten's internally
          computed micro-cuts and for any cached plans predating the
          index-based range schema.

    Malformed or out-of-range entries are silently skipped (the caller
    logs the originating remove_words list, so a bad entry is observable).
    """
    removed_src: set = set()
    n = len(deepgram_words)
    if n == 0:
        return removed_src
    word_starts = [float(w.get("start") or 0.0) for w in deepgram_words]
    word_ends = [float(w.get("end") or 0.0) for w in deepgram_words]
    for item in (remove_words or []):
        if not isinstance(item, dict):
            continue
        if "word_index" in item and item["word_index"] is not None:
            try:
                idx = int(item["word_index"])
            except (TypeError, ValueError):
                continue
            if 0 <= idx < n:
                removed_src.add(idx)
            continue
        if (
            item.get("after_word_index") is not None
            and item.get("before_word_index") is not None
        ):
            try:
                _aw = int(item["after_word_index"])
                _bw = int(item["before_word_index"])
            except (TypeError, ValueError):
                continue
            if _aw < 0 or _bw <= _aw or _bw > n:
                continue
            for i in range(_aw + 1, _bw):
                removed_src.add(i)
            continue
        if "start" in item and "end" in item:
            try:
                rs = float(item["start"])
                re_ = float(item["end"])
            except (TypeError, ValueError):
                continue
            if re_ <= rs:
                continue
            for i in range(n):
                if word_starts[i] >= rs and word_ends[i] <= re_:
                    removed_src.add(i)
    return removed_src


def _reindex_kept_transcript(deepgram_words, remove_words):
    """Apply CutPlan.remove_words to the source transcript and renumber survivors.

    Returns a tuple of:
      kept_words   — list of source-word dicts that survive, in source order.
      new_to_src   — list[int] mapping new_idx → src_idx for every kept word.
      removed_src  — set[int] of source indices that were cut.

    See _remove_words_to_src_indices for the accepted entry shapes.
    """
    if not deepgram_words:
        return [], [], set()

    removed_src = _remove_words_to_src_indices(remove_words, deepgram_words)

    kept_words = []
    new_to_src = []
    for src_idx in range(len(deepgram_words)):
        if src_idx in removed_src:
            continue
        kept_words.append(deepgram_words[src_idx])
        new_to_src.append(src_idx)

    return kept_words, new_to_src, removed_src


def _translate_post_cut_anchors_to_src(post_cut_plan, new_to_src):
    """Walk every word_index field in PostCutPlan and remap new_idx → src_idx.

    Returns a new dict with every anchor translated. Out-of-bounds indices
    drop the offending element (logged) so a single bad index doesn't crash
    the whole render. By construction this should never fire — the schema
    constrains Gemini to the kept-only space — but the guard is cheap.
    """
    if not isinstance(post_cut_plan, dict):
        return post_cut_plan

    M = len(new_to_src)

    def _xlate(new_idx):
        if not isinstance(new_idx, (int, float)):
            return None
        i = int(new_idx)
        if 0 <= i < M:
            return new_to_src[i]
        return None

    out = dict(post_cut_plan)

    # Single-int fields
    for key in ("thumbnail_word_index",):
        if key in out:
            v = _xlate(out.get(key))
            if v is None:
                print(f"[two-pass] Dropping {key}: index {out.get(key)} out of kept-range [0..{M-1}]", flush=True)
                out.pop(key, None)
            else:
                out[key] = v

    # caption_position_changes — list of {word_index, position}
    cpc = out.get("caption_position_changes") or []
    new_cpc = []
    for ch in cpc:
        if not isinstance(ch, dict):
            continue
        v = _xlate(ch.get("word_index"))
        if v is None:
            continue
        new_cpc.append({**ch, "word_index": v})
    out["caption_position_changes"] = new_cpc

    # emphasis_moments — list with word_indices: [int, ...]
    em_in = out.get("emphasis_moments") or []
    em_out = []
    for em in em_in:
        if not isinstance(em, dict):
            continue
        wis = em.get("word_indices") or []
        new_wis = []
        for wi in wis:
            v = _xlate(wi)
            if v is not None:
                new_wis.append(v)
        if not new_wis:
            print(f"[two-pass] Dropping emphasis_moment: every word_index out of kept-range", flush=True)
            continue
        em_out.append({**em, "word_indices": new_wis})
    out["emphasis_moments"] = em_out

    # text_overlays — start_word_index
    tov_in = out.get("text_overlays") or []
    tov_out = []
    for ov in tov_in:
        if not isinstance(ov, dict):
            continue
        v = _xlate(ov.get("start_word_index"))
        if v is None:
            print(f"[two-pass] Dropping text_overlay: start_word_index out of kept-range", flush=True)
            continue
        tov_out.append({**ov, "start_word_index": v})
    out["text_overlays"] = tov_out

    # sound_effects — word_index
    sfx_in = out.get("sound_effects") or []
    sfx_out = []
    for sfx in sfx_in:
        if not isinstance(sfx, dict):
            continue
        v = _xlate(sfx.get("word_index"))
        if v is None:
            print(f"[two-pass] Dropping sound_effect: word_index out of kept-range", flush=True)
            continue
        sfx_out.append({**sfx, "word_index": v})
    out["sound_effects"] = sfx_out

    # transitions — after_word_index
    tr_in = out.get("transitions") or []
    tr_out = []
    for tr in tr_in:
        if not isinstance(tr, dict):
            continue
        v = _xlate(tr.get("after_word_index"))
        if v is None:
            print(f"[two-pass] Dropping transition: after_word_index out of kept-range", flush=True)
            continue
        tr_out.append({**tr, "after_word_index": v})
    out["transitions"] = tr_out

    # tight_cut_overlays — after_word_index (same shape as transitions, target
    # space is TIGHT BOUNDARIES instead of CUT BOUNDARIES — checked at the
    # application site in generate_edit_gemini, not here)
    tco_in = out.get("tight_cut_overlays") or []
    tco_out = []
    for tco in tco_in:
        if not isinstance(tco, dict):
            continue
        v = _xlate(tco.get("after_word_index"))
        if v is None:
            print(f"[two-pass] Dropping tight_cut_overlay: after_word_index out of kept-range", flush=True)
            continue
        tco_out.append({**tco, "after_word_index": v})
    out["tight_cut_overlays"] = tco_out

    # motion_graphics — start_word_index, end_word_index
    mg_in = out.get("motion_graphics") or []
    mg_out = []
    for mg in mg_in:
        if not isinstance(mg, dict):
            continue
        s = _xlate(mg.get("start_word_index"))
        e = _xlate(mg.get("end_word_index"))
        if s is None or e is None:
            print(f"[two-pass] Dropping motion_graphic: index out of kept-range", flush=True)
            continue
        mg_out.append({**mg, "start_word_index": s, "end_word_index": e})
    out["motion_graphics"] = mg_out

    # broll_clips — start_word_index, end_word_index
    bc_in = out.get("broll_clips") or []
    bc_out = []
    for bc in bc_in:
        if not isinstance(bc, dict):
            continue
        s = _xlate(bc.get("start_word_index"))
        e = _xlate(bc.get("end_word_index"))
        if s is None or e is None:
            print(f"[two-pass] Dropping broll_clip: index out of kept-range", flush=True)
            continue
        bc_out.append({**bc, "start_word_index": s, "end_word_index": e})
    out["broll_clips"] = bc_out

    # video_plan — hook/payoff/close word_index + each key_moment.word_index.
    # The plan is for Gemini's reasoning scaffold, not consumed directly by
    # the renderer — but translating to source-space makes the plan readable
    # in logs (every other anchor in the output is in source-space at this
    # point, so the plan stays consistent). Out-of-range indices fall back
    # to None rather than dropping the whole plan: Gemini might emit a
    # plan-only index that doesn't match any kept word (rare edge case),
    # and the rest of the plan's editorial content is still usable.
    vp = out.get("video_plan")
    if isinstance(vp, dict):
        vp_out = dict(vp)
        for _k in ("hook_word_index", "payoff_word_index", "close_word_index"):
            _orig = vp_out.get(_k)
            _v = _xlate(_orig) if _orig is not None else None
            if _v is not None:
                vp_out[_k] = _v
            elif _orig is not None:
                print(
                    f"[two-pass] video_plan.{_k}={_orig} out of kept-range — "
                    f"leaving as kept-space index (plan is editorial scaffold only)",
                    flush=True,
                )
        _moments_in = vp_out.get("key_moments") or []
        _moments_out = []
        for _moment in _moments_in:
            if not isinstance(_moment, dict):
                continue
            _orig_wi = _moment.get("word_index")
            _v = _xlate(_orig_wi) if _orig_wi is not None else None
            if _v is not None:
                _moments_out.append({**_moment, "word_index": _v})
            else:
                # Keep the moment's editorial content (what_lands / why_emphasis)
                # but null the index so downstream code that anchors emphasis
                # to plan moments can detect the mismatch.
                _moments_out.append({**_moment, "word_index": _orig_wi})
        vp_out["key_moments"] = _moments_out
        out["video_plan"] = vp_out

    return out


# ── Gemini explicit prompt caching ─────────────────────────────────────────────
# The PostCutPlan call has a large static system_instruction string (~67KB).
# Gemini's explicit cache lets us send the system_instruction ONCE per
# (model, hash) and reference it on subsequent calls — cached tokens process
# at ~75% reduced latency. With TTL=1h, every render after the first within
# an hour saves ~5-10s on the post-cut Gemini call.
#
# Cache failure (creation or expired-on-server) falls through to the
# non-cached call: the helper returns None on create failure; the wrapper
# below catches "cache not found" errors on use and retries once without
# the cached_content reference. No silent quality compromise — both paths
# produce identical Gemini output.
import hashlib as _hashlib
import threading as _threading

_GEMINI_CACHE_LOCK = _threading.Lock()
_GEMINI_CACHE_REGISTRY: dict = {}  # (model, sys_hash) -> (cache_name, expires_at_epoch)
_GEMINI_CACHE_TTL_SECONDS = 3600  # 1h — Gemini default; renews on use


def _gemini_cache_key(model_name: str, system_instruction: str) -> tuple:
    h = _hashlib.sha256(system_instruction.encode("utf-8")).hexdigest()[:16]
    return (model_name, h)


def _drop_gemini_cache(model_name: str, system_instruction: str) -> None:
    key = _gemini_cache_key(model_name, system_instruction)
    with _GEMINI_CACHE_LOCK:
        _GEMINI_CACHE_REGISTRY.pop(key, None)


def _get_or_create_gemini_system_cache(client, model_name: str, system_instruction: str):
    """Return a Gemini cache resource name covering `system_instruction`,
    creating one if needed. Returns None on failure — caller should fall
    back to passing system_instruction directly in the generate config."""
    if genai_types is None:
        return None
    key = _gemini_cache_key(model_name, system_instruction)
    now = time.time()
    with _GEMINI_CACHE_LOCK:
        entry = _GEMINI_CACHE_REGISTRY.get(key)
        if entry is not None:
            cache_name, expires_at = entry
            if expires_at > now + 60:
                return cache_name
            # Local entry near/past TTL — drop and recreate.
            _GEMINI_CACHE_REGISTRY.pop(key, None)
    try:
        _t0 = time.time()
        cache = client.caches.create(
            model=model_name,
            config=genai_types.CreateCachedContentConfig(
                system_instruction=system_instruction,
                ttl=f"{_GEMINI_CACHE_TTL_SECONDS}s",
            ),
        )
        cache_name = getattr(cache, "name", None)
        if not cache_name:
            return None
        with _GEMINI_CACHE_LOCK:
            _GEMINI_CACHE_REGISTRY[key] = (cache_name, now + _GEMINI_CACHE_TTL_SECONDS)
        print(
            f"[gemini-cache] created {cache_name} for {model_name} "
            f"({len(system_instruction)} chars, ttl={_GEMINI_CACHE_TTL_SECONDS}s, "
            f"{time.time() - _t0:.1f}s)",
            flush=True,
        )
        return cache_name
    except Exception as e:
        print(f"[gemini-cache] create failed: {e} — proceeding without cache", flush=True)
        return None


def _gemini_is_retriable_error(msg):
    """Classify a Gemini error as retriable: ONLY fast-fail transient capacity
    errors — shared-quota rate limit (429 / RESOURCE_EXHAUSTED / quota), model
    overload (503 / UNAVAILABLE / overloaded), other quick 5xx (500/502), or a
    transient connection drop. These reject immediately, so a short backoff +
    re-try is cheap.

    NOT retriable — and deliberately so: 504 / DEADLINE_EXCEEDED / timeout. The
    edit-recipe (post-cuts) call legitimately runs 135-337s with a 480s server
    deadline; a deadline error means the call itself was too slow, so re-running
    it just burns another ~300-480s — up to 4× compounds into a ~20-min hang
    that trips Modal's 900s timeout and looks like a STUCK job. Fail fast and
    surface instead. (Also not retriable: bad request, cache-miss, auth, schema.)"""
    m = str(msg).lower()
    return (
        "429" in m or "resource_exhausted" in m or "rate limit" in m or
        "quota" in m or "500" in m or "502" in m or "503" in m or
        "unavailable" in m or "overloaded" in m or
        "connection" in m or "temporarily" in m
    )


def _gemini_generate_with_backoff(generate_fn, label="gemini", attempts=4, base=4.0):
    """Run a Gemini generate_content call with exponential backoff + JITTER on
    retriable errors (shared-quota 429 / overload / 5xx / network).

    Concurrent renders all draw from ONE Gemini account quota (TPM/RPM), so a
    burst of simultaneous jobs can transiently trip the shared limit. Backoff
    lets each render ride out a transient limit instead of failing — this is
    what keeps an INDIVIDUAL render sound while OTHER renders run at the same
    time (the per-job-isolation goal). Jitter spreads retries so N jobs don't
    re-hit the limit on the same tick (thundering herd). Mirrors Deepgram's
    backoff (_deepgram_is_retriable_error). NOTE: backoff absorbs BURSTS;
    SUSTAINED load above quota is a quota problem (raise the Gemini tier), not
    a retry problem — retries only add latency once the pool is truly saturated."""
    import random
    last_err = None
    for attempt in range(attempts):
        try:
            return generate_fn()
        except Exception as e:
            last_err = e
            if attempt < attempts - 1 and _gemini_is_retriable_error(e):
                wait = min(45.0, base * (2 ** attempt)) + random.uniform(0.0, 1.5)
                print(
                    f"[gemini-backoff] {label} attempt {attempt + 1}/{attempts} "
                    f"retriable ({type(e).__name__}: {str(e)[:120]}) — retry in {wait:.1f}s",
                    flush=True,
                )
                time.sleep(wait)
                continue
            raise
    raise last_err  # defensive — the loop returns or raises on every path


def _gemini_generate_with_cache(client, model_name, contents, base_config_kwargs, system_instruction):
    """Run client.models.generate_content with explicit prompt caching.

    `base_config_kwargs` is the dict of keyword args for GenerateContentConfig
    EXCLUDING system_instruction / cached_content — those are added here based
    on whether a cache resolved successfully. On cache-miss errors at use time,
    drops the local registry entry and retries once without the cache."""
    cache_name = _get_or_create_gemini_system_cache(client, model_name, system_instruction)

    def _build_config(use_cache: bool):
        kwargs = dict(base_config_kwargs)
        if use_cache and cache_name:
            kwargs["cached_content"] = cache_name
        else:
            kwargs["system_instruction"] = system_instruction
        return genai_types.GenerateContentConfig(**kwargs)

    try:
        return _gemini_generate_with_backoff(
            lambda: client.models.generate_content(
                model=model_name,
                contents=contents,
                config=_build_config(use_cache=cache_name is not None),
            ),
            label="generate(cache)",
        )
    except Exception as e:
        if cache_name:
            _msg = str(e).lower()
            if "cache" in _msg or "not found" in _msg or "404" in _msg:
                print(
                    f"[gemini-cache] cached call failed ({type(e).__name__}: {e}) — "
                    f"dropping cache, retrying without",
                    flush=True,
                )
                _drop_gemini_cache(model_name, system_instruction)
                return _gemini_generate_with_backoff(
                    lambda: client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=_build_config(use_cache=False),
                    ),
                    label="generate(no-cache)",
                )
        raise


def _call_gemini_post_cuts(client, system_instruction, user_content, video_part, model_name):
    """Second Gemini call: visual placement on the kept-only transcript.

    Deep-thinking budget. thinking_budget=24576 (lowered from a 60000 cap).
    60K bought no quality — every good recipe this session ran at ≤24576 —
    and it drove the model to spiral past its output budget into an empty
    response (output=None after thoughts≈9770 on a 421.9s call, with the
    timeout already extended). Thinking LESS is the fix; more time made it
    fail harder, not succeed (see _get_genai_client — the timeout is not
    the driver and is deliberately left alone).

    Note on the shared cap: max_output_tokens=65536 is the COMBINED ceiling
    on thinking + actual JSON response. At 24K thinking, ~40K is left for
    the JSON output — typical PostCutPlan JSON is 2-4K, comfortable margin.
    """
    print(
        f"[gemini-post] Calling {model_name} (thinking_budget=24576, PostCutPlan schema, "
        f"system_instruction={len(system_instruction)} chars, user_content={len(user_content)} chars)...",
        flush=True,
    )
    # An empty/None response is a transient model hiccup, not a permanent
    # failure — a fresh call usually succeeds. Try the call up to twice (one
    # automatic retry) before raising. No other retry wraps this path:
    # _gemini_generate_with_cache only retries on cache-miss errors, and the
    # caller at the recipe site does not re-invoke on empty.
    # Typical PostCutPlan JSON is 2-4K output tokens; >16K means the model
    # spiraled into a repetition loop (the prod failure hit output=58,968).
    # Tunable in one place.
    _POST_CUTS_DEGEN_OUTPUT_TOKENS = 16000
    response_text = ""
    _degen = None
    for _attempt in (1, 2):
        t0 = time.time()
        response = _gemini_generate_with_cache(
            client, model_name,
            contents=[video_part, user_content],
            base_config_kwargs=dict(
                temperature=1.0,
                # max_output_tokens cap is SHARED between thinking and the
                # actual JSON response. Typical PostCutPlan JSON is 2-4K tokens
                # and thinking_budget is 24576, so ~28-29K is the legit ceiling.
                # Capped at 40000 (was 65536) to bound the blast radius of a
                # repetition-loop degeneration — a spiral can't run to 64K
                # tokens / 430s anymore. The degeneration GUARD below (re-roll
                # on oversized/unparseable output) is what recovers the job;
                # this cap just limits a single bad roll's wall-clock.
                max_output_tokens=40000,
                response_mime_type="application/json",
                response_json_schema=PostCutPlan.model_json_schema(),
                # 24576 thinking budget — lowered from 60000. 60K bought no
                # quality (every good recipe this session ran at ≤24576) and
                # drove the model to spiral past its output budget into an
                # empty response. Thinking LESS is the fix, not more time.
                thinking_config=genai_types.ThinkingConfig(thinking_budget=24576),
                media_resolution="MEDIA_RESOLUTION_LOW",
            ),
            system_instruction=system_instruction,
        )
        dt = time.time() - t0
        print(f"[gemini-post] Complete in {dt:.1f}s", flush=True)
        _out_tokens = None
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage is not None:
                _out_tokens = getattr(usage, "candidates_token_count", None)
                print(
                    f"[gemini-post] Tokens — prompt={getattr(usage,'prompt_token_count',None)} "
                    f"cached={getattr(usage,'cached_content_token_count',None)} "
                    f"thoughts={getattr(usage,'thoughts_token_count',None)} "
                    f"output={_out_tokens}",
                    flush=True,
                )
        except Exception:
            pass
        response_text = str(getattr(response, "text", "") or "").strip()

        # ── Degeneration guard ───────────────────────────────────────────────
        # A repetition loop (the model echoing the prompt's cadence) runs the
        # output to the token cap and TRUNCATES the JSON mid-string → extract_json
        # fails → the job errors. The old "if response_text: break" only caught an
        # EMPTY response; a non-empty degenerate blob sailed through to the failing
        # parse. Re-roll on three signals — empty, oversized output (typical plan
        # is 2-4K tok; >16K is a spiral), or unparseable JSON — and only return on
        # a clean parse. A fresh call almost always returns clean; this completes
        # the empty-response retry, it does not paper over a fixable root cause
        # (the ≤50-word notes instruction is already present and was ignored).
        _degen = None
        _parsed = None
        if not response_text:
            _degen = "empty/None response"
        elif isinstance(_out_tokens, int) and _out_tokens > _POST_CUTS_DEGEN_OUTPUT_TOKENS:
            _degen = (f"output {_out_tokens} tok > {_POST_CUTS_DEGEN_OUTPUT_TOKENS} "
                      f"— repetition-loop degeneration")
        else:
            try:
                _parsed = extract_json(response_text)
            except Exception as _pe:
                _degen = f"unparseable JSON ({type(_pe).__name__}: {str(_pe)[:140]})"
        if _degen is None:
            print(f"[gemini-post] RAW:\n{response_text}\n[gemini-post] END", flush=True)
            return _parsed
        # Degenerate. Log a BOUNDED snippet (never the full 64K spiral) + re-roll.
        print(
            f"[gemini-post] Degenerate response ({_degen}) — "
            f"{'retrying once' if _attempt == 1 else 'no attempts left'}. "
            f"head: {response_text[:600]!r}",
            flush=True,
        )
    raise RuntimeError(f"Gemini post-cuts-call degenerate after retry: {_degen}")


# Confidence floor for the AUTOMATIC scene-change backfill only. scdet scores
# real camera cuts high (observed production cuts: 7.75–14.7); PiP / embedded-
# insert overlay edges — which scdet reports identically — tend to score lower.
# The floor auto-decorates a bare shot boundary ONLY when its scdet score
# clears this bar, so low-confidence / fluttering edges are skipped. Gemini's
# OWN discretionary overlays are NOT gated by this (it has vision judgment the
# deterministic floor lacks). Tunable in one place. A boundary with NO known
# score (legacy no-score scdet path) fails OPEN — decorate — since a missing
# score must not silently disable the floor.
SCENE_FLOOR_MIN_SCDET_SCORE = 8.0


def _scene_floor_rotation(current_types):
    """Deterministic variety fill for the scene-change decoration floor.

    `current_types` is the ordered (temporal) list of existing decoration
    types on each shot-change tight boundary — a type string for a boundary
    Gemini already dressed, or None for a bare boundary. Returns a list of the
    same length where every None is replaced by a rotated light punctuation
    overlay such that no two ADJACENT entries share a type.

    Rotation set: ShutterFlash / LightLeak / NewspaperWipe. SceneTitle (would
    need invented title text) and DipToBlack (heavy, act-break weight) are
    held out. Pure function — no RNG, same input → same output. Gemini's picks
    are locked; bare boundaries fill left-to-right with ROTATION[(i+k)%3],
    skipping the previous (already-resolved) and next (fixed pick, if any)
    type. With 3 types and at most 2 forbidden neighbours a valid pick always
    exists, so the defensive `else` branch is unreachable in practice.
    """
    rotation = ["ShutterFlash", "LightLeak", "NewspaperWipe"]
    resolved = list(current_types)
    n = len(resolved)
    for i in range(n):
        if resolved[i] is not None:
            continue
        prev_t = resolved[i - 1] if i > 0 else None
        next_t = resolved[i + 1] if i + 1 < n else None
        for k in range(3):
            cand = rotation[(i + k) % 3]
            if cand != prev_t and cand != next_t:
                resolved[i] = cand
                break
        else:
            resolved[i] = rotation[i % 3]  # unreachable; defensive
    return resolved


def _reconcile_tight_cut_overlays(client, vision_text, tight_boundaries, kept_words):
    """Focused second Gemini call to resolve a vision-claims-but-empty
    tight_cut_overlays contradiction. Returns a list of 0 or 1 overlay
    entries to merge into post_cut_plan["tight_cut_overlays"].

    Fires from the recipe-eval site (handler.py:~6148+) only when the
    detector found that editorial_vision committed to a tight-cut overlay
    AND the emitted array is empty AND tight boundaries exist. Three
    prior prose fixes (coherence rule + EFFECT/MECHANISM extension +
    HARD RULE 2 tiebreaker) failed to prevent the contradiction in the
    main 60K-token generation; the working theory is that a narrow
    decision with reasoning room executes reliably where a buried self-
    check loses to nearby restraint framing. Same lesson as the picker
    thinking_budget=32 → 256 fix.

    Inputs deliberately scoped tight:
      - vision_text         — the editor's commitment (one sentence)
      - tight_boundaries    — kept-word indices, the candidate set
      - kept_words          — for the "after <word>" context per boundary

    Bounded latency: thinking_budget=512 (narrow 6-boundary × 4-type
    decision); 30s hard timeout via ThreadPoolExecutor. Caps emission
    at 1 entry (the bug pattern is claims-but-empty, give the vision
    one earned overlay). Fail-open to [] on any error / timeout / cap
    violation / validation failure — never raises, never mutates inputs.
    """
    if not tight_boundaries or not vision_text:
        return []

    _boundary_lines = []
    for _idx in tight_boundaries:
        if 0 <= _idx < len(kept_words):
            _w = (
                kept_words[_idx].get("punctuated_word")
                or kept_words[_idx].get("word")
                or "?"
            )
            _boundary_lines.append(f'{_idx} (after "{_w}")')
    if not _boundary_lines:
        return []
    _boundary_block = ", ".join(_boundary_lines)

    _prompt = (
        "RECONCILIATION TASK — your editorial_vision committed to a tight-cut "
        "overlay, but the tight_cut_overlays array was emitted empty. Resolve "
        "by picking the SINGLE tight boundary that most earns the overlay your "
        "vision named, or return [] if no boundary genuinely earns one.\n\n"
        f'YOUR EDITORIAL VISION: "{vision_text}"\n\n'
        f"TIGHT BOUNDARIES (candidate set — kept-word indices, with the word "
        f"that precedes the cut): {_boundary_block}\n\n"
        "FOUR OVERLAY TYPES + when each fits:\n"
        "  - LightLeak — warm bloom across the cut. Use for a reflective / "
        "arrived-at register: quiet realization, takeaway landing, hook/close "
        "callback.\n"
        "  - ShutterFlash — quick white camera-flash snap. Use for higher-"
        "energy / surprise / payoff hitting: escalation beat after a setup, "
        "unexpected pivot, the moment a stat or punchline lands.\n"
        "  - NewspaperWipe — torn paper slams up, covers, holds, rushes off. "
        "Use for reveal / named-thing handover: the answer arrives, the name "
        "lands, the surprise gets unwrapped.\n"
        "  - SceneTitle — large serif title panel (~1200ms chapter break). "
        "Use ONLY for genuine SECTION boundaries (one act → next act). "
        "Requires `title` (1-3 uppercase words).\n\n"
        "RULES:\n"
        "  - `after_word_index` MUST come from the TIGHT BOUNDARIES candidate "
        "set above.\n"
        "  - Max 1 entry. Pick the SINGLE most-earning boundary.\n"
        "  - SceneTitle requires `title` (1-3 uppercase words). LightLeak / "
        "ShutterFlash / NewspaperWipe must NOT carry `title` or `label`.\n"
        "  - If no boundary genuinely earns the overlay your vision named, "
        "return []. Don't force one onto a weak beat.\n\n"
        "Return a JSON array of 0 or 1 tight_cut_overlay entries."
    )

    _schema = {
        "type": "array",
        "maxItems": 1,
        "items": {
            "type": "object",
            "properties": {
                "after_word_index": {"type": "integer"},
                "type": {"type": "string", "enum": sorted(VALID_TIGHT_CUT_OVERLAYS)},
                "title": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["after_word_index", "type"],
        },
    }

    def _do_call():
        return client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[_prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=512,
                response_mime_type="application/json",
                response_schema=_schema,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=512),
            ),
        )

    _t0 = time.time()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _pool:
            _fut = _pool.submit(_do_call)
            _resp = _fut.result(timeout=30.0)
    except concurrent.futures.TimeoutError:
        print(
            f"[reconcile-overlays] TIMEOUT (>30s, {time.time() - _t0:.1f}s elapsed) "
            f"— failing open to []",
            flush=True,
        )
        return []
    except Exception as _e:
        print(
            f"[reconcile-overlays] error ({type(_e).__name__}: {_e}) "
            f"in {time.time() - _t0:.1f}s — failing open to []",
            flush=True,
        )
        return []

    _elapsed = time.time() - _t0
    _text = str(getattr(_resp, "text", "") or "").strip()
    if not _text:
        print(
            f"[reconcile-overlays] empty response in {_elapsed:.1f}s — failing open to []",
            flush=True,
        )
        return []
    try:
        _parsed = json.loads(_text)
    except Exception:
        print(
            f"[reconcile-overlays] JSON parse failed in {_elapsed:.1f}s "
            f"(raw: {_text[:120]!r}) — failing open to []",
            flush=True,
        )
        return []
    if not isinstance(_parsed, list):
        print(
            f"[reconcile-overlays] non-list response in {_elapsed:.1f}s "
            f"(got {type(_parsed).__name__}) — failing open to []",
            flush=True,
        )
        return []
    if len(_parsed) == 0:
        print(
            f"[reconcile-overlays] re-ask returned [] in {_elapsed:.1f}s "
            f"(model judged no boundary earns the overlay) — keeping empty",
            flush=True,
        )
        return []
    if len(_parsed) > 1:
        print(
            f"[reconcile-overlays] re-ask returned {len(_parsed)} entries in "
            f"{_elapsed:.1f}s (helper cap=1) — failing open to []",
            flush=True,
        )
        return []
    _entry = _parsed[0]
    if not isinstance(_entry, dict):
        print(
            f"[reconcile-overlays] entry is not a dict — failing open to []",
            flush=True,
        )
        return []
    _awi = _entry.get("after_word_index")
    _typ = _entry.get("type")
    _tight_set = set(tight_boundaries)
    if not isinstance(_awi, int) or _awi not in _tight_set:
        print(
            f"[reconcile-overlays] after_word_index {_awi!r} not in TIGHT "
            f"BOUNDARIES {sorted(_tight_set)} — failing open to []",
            flush=True,
        )
        return []
    if _typ not in VALID_TIGHT_CUT_OVERLAYS:
        print(
            f"[reconcile-overlays] type {_typ!r} not in "
            f"{sorted(VALID_TIGHT_CUT_OVERLAYS)} — failing open to []",
            flush=True,
        )
        return []
    if _typ == "SceneTitle":
        _title = _entry.get("title")
        if not (isinstance(_title, str) and _title.strip()):
            print(
                f"[reconcile-overlays] SceneTitle at word {_awi} missing required "
                f"title — failing open to []",
                flush=True,
            )
            return []
    else:
        # Strip title/label from non-SceneTitle entries to match HARD RULE 3.
        _entry.pop("title", None)
        _entry.pop("label", None)
    print(
        f"[reconcile-overlays] vision-claims-empty contradiction RESOLVED in "
        f"{_elapsed:.1f}s: type={_typ} after_word_index={_awi}"
        + (f" title={_entry.get('title')!r}" if _typ == "SceneTitle" else ""),
        flush=True,
    )
    return [_entry]


def _record_divergence(component, original, action, *, final=None, reason=""):
    """Single grep-stable log line for any post-Gemini drop / coerce / clamp /
    withhold / override.

    A render's silent attrition stops being silent the moment every site that
    deletes or mutates a component goes through this helper. One
    `grep '\\[divergence\\]' modal.log` then surfaces every drift, sorted by
    component, with the original payload + reason intact.

    component — recipe component or signal class ("cut_boundary", "broll",
                "transition", "mg", "overlay", "sfx", "caption_position", ...)
    original  — pre-mutation value, serialized as compact JSON
    action    — what happened: "drop" / "coerce" / "clamp" / "withhold" /
                "withheld_as_tight" / "clip_split_without_known_boundary" / etc.
    final     — post-mutation value (None for full drops)
    reason    — short machine-readable code (snake_case)
    """
    try:
        _orig = json.dumps(original, separators=(",", ":"), default=str)
    except Exception:
        _orig = str(original)
    if final is None:
        _final = "null"
    else:
        try:
            _final = json.dumps(final, separators=(",", ":"), default=str)
        except Exception:
            _final = str(final)
    print(
        f"[divergence] component={component} action={action} "
        f"reason={reason} original={_orig} final={_final}",
        flush=True,
    )


def generate_edit_gemini(
    video_path, vibe, duration, trend_context=None, deepgram_words=None,
    shot_changes=None, shot_change_scores=None, vocal_emphasis=None, source_loudness=None,
    face_positions=None, smoothed_face_trajectory=None,
    user_style_profile=None,
    gemini_file=None, cached_response=None, inline_video_bytes=None,
    prior_plan=None, prior_plan_change_request=None,
):
    _pre_analysis = cached_response

    _shots = list(shot_changes or [])
    _shot_score_map = dict(shot_change_scores or {})  # scdet time(round 3)→score
    _vocal = list(vocal_emphasis or [])
    _loudness = dict(source_loudness or {})
    _face_positions = list(face_positions or [])
    _smoothed_trajectory = list(smoothed_face_trajectory or [])

    # Compute face signals from dense face detections. Speaker positions,
    # off-center flag, shot scale, and face vertical zone (upper/center/
    # lower over time) gate zoom and overlay choices. face_zone tells Gemini
    # WHERE the speaker's head sits in the frame so overlay placement can
    # avoid covering the face — components in `upper_third_safe`/`top`
    # anchors clash when the head is in the upper zone.
    (
        _face_visibility,
        _speaker_positions,
        _off_center,
        _shot_scale,
        _face_zone,
    ) = _build_face_signals(_face_positions, deepgram_words or [], duration)

    client = _get_genai_client()

    # ── Architecture ────────────────────────────────────────────────────────
    # Step 1 (mechanical cuts): compute_mechanical_cuts() runs four
    #   deterministic detectors on the Deepgram word list. No Gemini call.
    # Re-index: Python applies cuts and renumbers kept words [0..M-1].
    # Step 2 (PostCutPlan Gemini call, HIGH thinking): main prompt, run on
    #   the kept-only transcript. Anchor word_indices come from the new
    #   index space — physically cannot reference a cut word.
    # Translate: every word_index in PostCutPlan back to source indices.
    # Merge: mechanical cuts result + translated PostCutPlan → edit_plan.

    post_sys, post_user_base = _build_post_cuts_prompt(
        vibe=vibe,
        duration=duration,
        trend_context=trend_context,
        shot_changes=_shots,
        vocal_emphasis=_vocal,
        source_loudness=_loudness,
        face_visibility=_face_visibility,
        speaker_positions=_speaker_positions,
        off_center=_off_center,
        shot_scale=_shot_scale,
        user_style_profile=user_style_profile,
        face_zone=_face_zone,
        prior_plan=prior_plan,
        prior_plan_change_request=prior_plan_change_request,
    )
    if prior_plan:
        print(
            f"[generate-edit] GUIDED REDRAFT — prior plan injected "
            f"({len(json.dumps(prior_plan))} chars); user direction: "
            f"{str(prior_plan_change_request or '')[:160]}",
            flush=True,
        )

    # Pre-analysis goes to the post-cuts call (visual decisions benefit from
    # richer scene context; cuts call doesn't need it).
    if _pre_analysis and isinstance(_pre_analysis, dict):
        _pa_parts = []
        if _pre_analysis.get("peak_moments"):
            _pa_parts.append(f"Peak moments: {json.dumps(_pre_analysis['peak_moments'])}")
        if _pre_analysis.get("safe_cut_points"):
            _pa_parts.append(f"Safe cut points: {json.dumps(_pre_analysis['safe_cut_points'])}")
        if _pre_analysis.get("video_profile"):
            _pa_parts.append(f"Video profile: {json.dumps(_pre_analysis['video_profile'])}")
        # Shot breakdown intentionally excluded — narrative "action" descriptions
        # from content-studio leak into Gemini's b-roll keyword generation,
        # overriding the stock-footage-title instructions.
        if _pa_parts:
            post_user_base += "\n\n=== PRE-ANALYZED VIDEO DATA ===\n" + "\n".join(_pa_parts) + "\n"
            print(f"[generate-edit] Injected pre-analysis context ({len(_pa_parts)} sections)", flush=True)

    if trend_context:
        print(f"[generate-edit] Trend context included: {trend_context.get('sample_size', '?')} videos", flush=True)
    else:
        print("[generate-edit] No trend context available", flush=True)

    # Build video content part — shared across both calls (no re-upload).
    # video_metadata.fps=18 tells Gemini to SAMPLE at 18fps. Without this,
    # the SDK defaults to ~1fps regardless of the source's encoded frame
    # rate, so bumping the proxy encoder alone is a no-op for perception.
    # 24 is the API's hard cap (validated 2026-06-13: server returns
    # INVALID_ARGUMENT "threshold must be less than or equal to 24" on any
    # higher value). We sample at 18fps. History: 22 → 16 on 2026-06-15
    # was attempted as a 504 mitigation, then 16 → 18 on 2026-06-17 after
    # the real 504 cause was identified as the 120s X-Server-Timeout we
    # were sending (see _get_genai_client); 18 recovers half the visual-
    # signal headroom lost at 16 without re-triggering 504s now that the
    # server-deadline header is raised. Talking-head expressions (laughs,
    # smiles, eye-shifts) hold across 5-10 frames; gestures play over
    # 100-200ms; 18fps captures all of them with comfortable margin.
    # Paired with the 480p@18fps proxy encode (see _do_gemini_proxy).
    _video_fps_meta = genai_types.VideoMetadata(fps=18) if hasattr(genai_types, "VideoMetadata") else None
    if inline_video_bytes:
        _video_part = genai_types.Part(
            inline_data=genai_types.Blob(data=inline_video_bytes, mime_type="video/mp4"),
            video_metadata=_video_fps_meta,
        )
        print(f"[generate-edit] Using inline video ({len(inline_video_bytes)/1024/1024:.1f}MB, no upload, sample_fps=18)", flush=True)
    elif gemini_file is not None:
        _video_part = genai_types.Part(
            file_data=genai_types.FileData(file_uri=gemini_file.uri, mime_type=getattr(gemini_file, "mime_type", "video/mp4")),
            video_metadata=_video_fps_meta,
        )
        print(f"[generate-edit] Using pre-uploaded Gemini file: {gemini_file.uri} (sample_fps=18)", flush=True)
    else:
        raise RuntimeError("No video data provided — need either inline_video_bytes or gemini_file")

    # ── Cuts: mechanical detection (no Gemini call) ─────────────────────────
    # Four deterministic detectors (dead_air / filler / false_start / stutter)
    # — see compute_mechanical_cuts for category definitions. dead_air uses
    # Silero VAD on the actual audio waveform (industry standard); the
    # other three are transcript-pattern detectors. video_path is the
    # source file VAD reads audio from — Silero handles ffmpeg-decodable
    # formats natively via torchaudio.
    cut_plan = compute_mechanical_cuts(
        deepgram_words or [], source_path=video_path,
    )
    raw_cut_remove_words = cut_plan.get("remove_words") or []
    print(
        f"[cuts-mechanical] {cut_plan.get('notes', '')} "
        f"→ {len(raw_cut_remove_words)} remove_word entries",
        flush=True,
    )

    # ── Re-index: source transcript → kept-only transcript with new indices ─
    kept_words, new_to_src, removed_src = _reindex_kept_transcript(
        deepgram_words or [], raw_cut_remove_words,
    )
    _src_count = len(deepgram_words or [])
    _kept_count = len(kept_words)
    print(
        f"[two-pass] Re-indexed transcript: {_src_count} src words → {_kept_count} kept "
        f"({len(removed_src)} removed)",
        flush=True,
    )

    # Append the kept-only transcript to the post-cuts call's user content.
    # Indices are NEW (kept-only space [0..M-1]); timestamps are still source-time.
    post_user = post_user_base
    if kept_words:
        kept_readable = " ".join(
            (_w.get("punctuated_word") or _w.get("word") or "")
            for _w in kept_words
        )
        kept_word_lines = []
        for new_idx, _w in enumerate(kept_words):
            word_text = _w.get("punctuated_word") or _w.get("word") or ""
            start = float(_w.get("start") or 0)
            end = float(_w.get("end") or 0)
            spk = int(_w.get("speaker") or 0)
            kept_word_lines.append(f"  [{new_idx}] {start:.2f}-{end:.2f} spk{spk}: {word_text}")
        kept_transcript_block = "\n".join(kept_word_lines)

        # Compute cut-boundary word indices in kept-only space. Two sources:
        #   1) dead_air removals — kept word followed by a removed range
        #      (next kept word's source-index is NOT this_src_idx + 1).
        #   2) source shot changes — clustered ffmpeg scdet detections,
        #      snapped to the nearest kept-word end within 0.30s. Each
        #      visible source cut becomes a transition slot; the post-
        #      Gemini splicer splits the clip at the same word boundary so
        #      the transition actually plays across a real splice.
        # Both kinds of boundaries are exposed to Gemini so it knows every
        # valid `after_word_index` it can place a transition on. A
        # transition placed at any other word is dropped by the pipeline.
        # Pre-compute the consecutive-anchor dead_air pairs from the
        # mechanical-cut plan. For ranges like {after=N, before=N+1,
        # reason="dead_air"}, ZERO source words are actually removed but
        # build_clips_from_words still splits the clip at this boundary
        # so the silence between N and N+1 is dropped. Without surfacing
        # these in the boundary list, Gemini never sees the cut and the
        # cross-check guard fires `clip_split_without_known_boundary`.
        # This catches them in src-word space; the iteration below then
        # maps each pair to its kept-word boundary index.
        _consecutive_da_src_pairs = set()
        for _rw in (raw_cut_remove_words or []):
            if not isinstance(_rw, dict):
                continue
            _aw_val = _rw.get("after_word_index")
            _bw_val = _rw.get("before_word_index")
            if _aw_val is None or _bw_val is None:
                continue
            try:
                _aw_int = int(_aw_val)
                _bw_int = int(_bw_val)
            except (TypeError, ValueError):
                continue
            if _bw_int == _aw_int + 1 and str(_rw.get("reason", "")) == "dead_air":
                _consecutive_da_src_pairs.add((_aw_int, _bw_int))

        _dead_air_boundary_indices = []
        for new_idx, src_idx in enumerate(new_to_src):
            if new_idx + 1 >= len(new_to_src):
                continue
            next_src_idx = new_to_src[new_idx + 1]
            if next_src_idx != src_idx + 1:
                _dead_air_boundary_indices.append(new_idx)
            elif (src_idx, next_src_idx) in _consecutive_da_src_pairs:
                # No gap in src space, but a dead_air range marks the
                # boundary explicitly — the silence between two adjacent
                # words gets cut. build_clips_from_words splits here too;
                # adding the boundary keeps the union in sync with the
                # renderer's actual cuts.
                _dead_air_boundary_indices.append(new_idx)
        # Shot-change-derived boundaries (kept-word indices)
        _shot_boundary_scores = {}  # kept-word index → scdet confidence score
        _shot_boundaries = shot_change_word_boundaries(
            _shots, kept_words,
            shot_scores=_shot_score_map, out_scores=_shot_boundary_scores,
        )
        _shot_boundary_set = {_ni for (_ni, _) in _shot_boundaries}
        _dead_air_set = set(_dead_air_boundary_indices)

        # ── Handle-availability split (NO silent discards) ───────────────────
        # Each transition consumes natural pause between cut A's last kept
        # word and cut B's first kept word. With gap-sharing handle, each
        # side of the boundary gets gap/2 of source-time room. To render a
        # transition at its FULL natural duration, gap must be ≥ 2 × that
        # type's natural duration. The shortest natural duration in
        # TRANSITION_NATURAL_DURATION_MS is the floor.
        #
        # Previously this floor was used as a silent filter — boundaries
        # below it were discarded entirely, and Gemini never learned the
        # cut existed. That caused same-spot same-framing splices (which
        # have effectively zero audio gap) to be hidden from Gemini, who
        # would then rationalize the video as "one continuous clip" while
        # the renderer still split clips at the missing boundary via
        # build_clips_from_words. Net: silent jump-cuts with no transition.
        #
        # Now: every detected boundary lands in exactly one of two lists.
        # Cuts with handle room go to CUT BOUNDARIES (Gemini may place
        # transitions). Cuts without go to TIGHT BOUNDARIES (awareness
        # only — Gemini knows the cut exists, plans energy around it, but
        # does not attempt to dress it).
        _trans_dur_for_filter = 2.0 * (_TRANSITION_MIN_NATURAL_MS / 1000.0)
        def _audio_gap_at_boundary(ni):
            if ni < 0 or ni + 1 >= len(kept_words):
                return float("inf")
            _a_end = float(kept_words[ni].get("end") or 0.0)
            _b_start = float(kept_words[ni + 1].get("start") or 0.0)
            return max(0.0, _b_start - _a_end)
        _candidate_indices = sorted(_dead_air_set | _shot_boundary_set)

        _cut_boundary_indices = []
        _tight_boundary_indices = []
        for _ni in _candidate_indices:
            _gap = _audio_gap_at_boundary(_ni)
            if _gap >= _trans_dur_for_filter:
                _cut_boundary_indices.append(_ni)
            else:
                _tight_boundary_indices.append(_ni)

        # Divergence log — every tight boundary is named, with its gap and
        # which detector surfaced it. One grep finds them all.
        for _ni in _tight_boundary_indices:
            _record_divergence(
                "cut_boundary",
                {
                    "kept_word_index": _ni,
                    "gap_ms": int(round(_audio_gap_at_boundary(_ni) * 1000)),
                    "source": (
                        "dead_air" if _ni in _dead_air_set and _ni not in _shot_boundary_set
                        else "shot_change" if _ni in _shot_boundary_set and _ni not in _dead_air_set
                        else "both"
                    ),
                },
                "withheld_as_tight",
                reason="audio_gap_below_transition_min",
            )

        # Union for any downstream consumer that needs every boundary
        # (recipe_eval, the clip-split cross-check guard later in this
        # function). Order preserved by index.
        _all_boundary_indices = sorted(set(_cut_boundary_indices) | set(_tight_boundary_indices))

        _shot_only_indices = sorted(
            _ni for _ni in _all_boundary_indices
            if _ni in _shot_boundary_set and _ni not in _dead_air_set
        )
        print(
            f"[shot-split] {len(_shot_boundaries)} shot-change boundary(ies) "
            f"({len(_shot_only_indices)} new beyond dead-air); "
            f"transition slots: {len(_cut_boundary_indices)}, "
            f"tight (awareness-only): {len(_tight_boundary_indices)}, "
            f"min handle: {_trans_dur_for_filter*1000:.0f}ms",
            flush=True,
        )

        # Human-readable list formatter — used by both message blocks.
        # Gap annotation is essential: without it Gemini can't tell a 1100ms
        # slot from a 4000ms one and rationally defaults to short safe
        # transitions everywhere, never reaching for SceneTitle / FilmStrip
        # at the long pauses that earn them. Same "withhold information
        # Gemini needs to choose well" failure mode that hid tight cuts.
        def _fmt_boundary_list(indices):
            if not indices:
                return "(none)"
            _parts = []
            for _ni in indices:
                if 0 <= _ni < len(kept_words):
                    _w = (
                        kept_words[_ni].get("punctuated_word")
                        or kept_words[_ni].get("word")
                        or "?"
                    )
                else:
                    _w = "?"
                _gap_ms = int(round(_audio_gap_at_boundary(_ni) * 1000))
                # Source tag so Gemini can tell a real visual cut (scdet-
                # flagged shot change) from a silence-only pause. Scene
                # changes are ALWAYS dressed (the pipeline guarantees a varied
                # decoration beneath the model's choices); pauses default to a
                # clean hard cut. A boundary that is both a gap AND a shot
                # change is a scene change — the camera moved.
                _src = "SCENE CHANGE" if _ni in _shot_boundary_set else "pause"
                _parts.append(f'{_ni} (after "{_w}", {_gap_ms}ms gap, {_src})')
            return ", ".join(_parts)

        _cut_boundary_block = _fmt_boundary_list(_cut_boundary_indices)
        _tight_boundary_block = _fmt_boundary_list(_tight_boundary_indices)

        _natural_dur_lines = "\n".join(
            f"  - {_name}: {_ms}ms  (fits when boundary gap ≥ {2 * _ms}ms)"
            for _name, _ms in sorted(
                TRANSITION_NATURAL_DURATION_MS.items(), key=lambda kv: kv[1]
            )
        )

        # Coherence-rule example phrases — interpolated below so this single
        # source of truth (type_registries.py) feeds BOTH the prompt prose AND
        # the recipe-eval re-ask detector. Hand-maintaining parallel phrase
        # lists in the two consumers would drift the detector from what the
        # prompt taught Gemini to recognize.
        _tco_mechanism_examples = ", ".join(
            f"'{_p}'" for _p in TIGHT_CUT_OVERLAY_MECHANISM_PHRASES
        )

        post_user += f"""

=== KEPT-ONLY TRANSCRIPT ({_kept_count} words, renumbered [0..{_kept_count - 1}]) ===

This transcript is the dialogue exactly as the viewer will hear it. Filler, stutters, restarts, and dead-air gaps are gone — every word here lands in the rendered video. Read it once before placing any visual element.

{kept_readable}

=== KEPT-ONLY WORD-BY-WORD TIMESTAMPS ===

Indices below are the NEW kept-only space [0..{_kept_count - 1}]. Every word_index you emit references THIS space. Timestamps are still source-time (Python uses them for rendering).

{kept_transcript_block}

=== CUT BOUNDARIES (transition slots — place at most one transition per entry, after_word_index = the listed index) ===

  {_cut_boundary_block}

=== TIGHT BOUNDARIES (real cuts with no audio handle — crossfade transitions cannot fit here, but ZERO-HANDLE transitions (LightLeak / ShutterFlash / NewspaperWipe / SceneTitle / DipToBlack) can, and `tight_cut_overlay` decorations can. Each is tagged SCENE CHANGE (a real visual cut — the shot actually changed) or pause (a silence-only splice, no visual change). EVERY scene change carries exactly ONE decoration — a zero-handle transition OR a tight_cut_overlay, never both — and you should vary the type across adjacent scene changes so it reads as editing vocabulary, not one effect on loop. Pause boundaries are discretionary and default to a clean hard cut. At minimum land a zoom on the first word after any tight cut to mask the jump. See HOW TO PLACE TRANSITIONS and HOW TO PLACE TIGHT-CUT OVERLAYS below for the editorial distinction.) ===

  {_tight_boundary_block}

=== TRANSITION NATURAL DURATIONS ===

Each transition component renders at its natural duration — the cadence its ramp-in / hold / ramp-out was designed for. Shortened transitions look glitchy; the pipeline doesn't compress them. A transition fits at a boundary when the boundary's audio gap is at least 2 × the type's natural duration (gap-sharing means each side of the boundary gets gap/2 of source room, and the animation needs a full natural duration per side).

{_natural_dur_lines}

=== HOW TO PLACE TRANSITIONS ===

**HARD RULE 1 — `after_word_index` MUST come from CUT BOUNDARIES or TIGHT BOUNDARIES.** Standard crossfade transitions (Stack, CardSwipe, ZoomThrough, SlideOver, CrossfadeZoom, StepPush, FilmStrip) MUST anchor on CUT BOUNDARIES — they consume audio handle for the equal-power crossfade and would audio-mush continuous speech on a tight cut. Zero-handle transitions (LightLeak, ShutterFlash, NewspaperWipe, SceneTitle, DipToBlack) MAY anchor on EITHER list — their renderers substitute silence for the audio mix at peak and don't need handle frames. A transition at any non-boundary index has no cut to play across and the renderer will not produce it. The validator hard-rejects a crossfade type on a tight boundary.

**HARD RULE 2 — the transition's natural duration must fit the boundary's gap.** Each CUT BOUNDARIES entry shows its available audio gap (`820ms gap`). A transition fits when its natural duration ≤ gap/2. If you want SceneTitle (1800ms natural) at a boundary annotated `2400ms gap`, that does NOT fit (need ≥ 3600ms gap). Match the transition's weight to both the dialogue's shift AND the available room — the long heavy transitions (SceneTitle, FilmStrip) are precisely the ones that earn the long pauses, so don't default to short safe transitions everywhere when a 4000ms-gap boundary is sitting right there asking for a chapter break.

**If no transition type fits a particular boundary, leave it alone.** The cut plays straight (hard cut). That is the correct behavior — better a clean hard cut than a compressed flicker. Do NOT force a transition where it doesn't fit.

**Place transitions where they fit and earn the moment.** Skip mid-sentence boundaries where the dialogue carries unbroken across the cut (same verb-subject continuing) — there a transition would seam the speaker mid-thought.

For each chosen `after_word_index`, pick a transition `type` whose character matches the dialogue's shift at that boundary (ZoomThrough, CardSwipe, ShutterFlash, SlideOver, CrossfadeZoom, SceneTitle, NewspaperWipe, FilmStrip, Stack, StepPush). Vary the type across emitted transitions — repeating the same type at adjacent boundaries reads as templating.

**Zero-handle transition vs `tight_cut_overlay` — same effect family, different editorial weight, one per boundary.** Same 4 type names (LightLeak / ShutterFlash / NewspaperWipe / SceneTitle) are available both as zero-handle TRANSITIONS on tight boundaries AND as `tight_cut_overlay` decorations on tight boundaries. They are NOT interchangeable: a `tight_cut_overlay` is LIGHT (~180ms; SceneTitle 1200ms), audio plays through unaltered, video plays through unaltered, decoration paints on top. A zero-handle transition is HEAVY (700-1800ms), audio goes silent under the transition window, video animation dominates the cut. A zero-handle transition on a tight cut is a RARE choice — reserve it for a genuine act/chapter break OR the single biggest moment of the video where you want the cut itself to be the editorial event. A SCENE-CHANGE cut takes a light overlay by default (the floor) or a heavy transition when it genuinely earns one; a PAUSE takes a light overlay only when it earns it, or nothing. Reaching for the heavy transition by default would read as dramatic templating. **Never emit both a transition AND a tight_cut_overlay on the same boundary — the validator will reject the recipe.**

=== HOW TO PLACE TIGHT-CUT OVERLAYS ===

A `tight_cut_overlay` is a brief decoration painted ON TOP of a hard cut at a TIGHT BOUNDARY. The cut underneath plays straight (no handle frames consumed, no audio touched, no time inserted) — the overlay sits ABOVE the cut and ramps in/out around it. Four types, two duration classes:

PUNCTUATION CLASS (~180ms — quick, decorates the cut moment):
  - **LightLeak** — warm bloom sweeping diagonally across the cut. Reads as "the moment widened" — a polished, cinematic punctuation. Use when the dialogue shifts to a more reflective / arrived-at register: a quiet realization, a takeaway landing, the close of a callback. Warm light = the speaker zooming in on the point, the viewer drawn closer.
  - **ShutterFlash** — quick white camera-flash snap. Reads as "the moment hit" — an editorial punch. Use when the dialogue shifts to higher energy / surprise / a payoff hitting: the escalation beat after a setup, an unexpected pivot, the moment a stat or punchline lands.
  - **NewspaperWipe** — torn paper slams up, covers, holds, rushes off. Reads as "the headline drops" — kinetic, almost breaking-news. Use when the dialogue delivers a reveal or named-thing handover: the answer arrives, the name lands, the surprise gets unwrapped. Distinct from ShutterFlash in feel — heavier, more deliberate, more "delivered" than "snapped."

CHAPTER-BREAK CLASS (~1200ms — a typographic divider; the new section starts here):
  - **SceneTitle** — large serif title on a panel that wipes in, holds long enough to read, wipes out. The ONLY overlay that carries text. Reads as "new chapter / new act begins" — distinct from the three punctuation overlays in both duration AND function. Use ONLY for genuine SECTION boundaries: the video has a clear act structure and the speaker is crossing from one act into the next. Do NOT use SceneTitle as decoration on a mere energy bump — it's a hard divider, not a flourish.
    - `title` REQUIRED — 1 to 3 uppercase words, editorial. Examples: "ACT TWO", "THE PIVOT", "PART III", "WHAT NEXT", "THE FIX". The title should READ as the chapter heading.
    - `label` OPTIONAL — uppercase kicker above the divider. Examples: "CHAPTER", "ACT", "PART II", "SECTION". Skip if the title already tells the viewer what kind of break this is.

**HARD RULE 1 — `after_word_index` MUST come from the TIGHT BOUNDARIES list above (NOT CUT BOUNDARIES, NOT any other index).** Placing a tight_cut_overlay at a CUT boundary is wrong: those boundaries already get full transitions. Placing it at a non-boundary index has no cut to decorate and the renderer will not produce it.

**HARD RULE 2 — every SCENE CHANGE is dressed; PAUSES stay sparing.** The TIGHT BOUNDARIES list tags each cut `SCENE CHANGE` (a real visual cut) or `pause` (a silence-only splice, no visual change). Decorate EVERY scene change — a transition or a tight_cut_overlay — and vary the type so adjacent scene changes don't repeat; the pipeline guarantees this floor beneath your choices, so place them with intent rather than leaving them bare. PAUSES are the sparing case: at most 2 discretionary overlays across the whole video (a short video gets 0, a strong chapter structure 1, a hook callback + a real chapter break 2 — commonly 1 SceneTitle + 1 punctuation overlay), and a pause's default is a clean hard cut. The 2-overlay cap and "rare exception" framing govern PAUSES only — on scene changes, varied decoration IS the vocabulary, not a templated overuse. One thing is NOT optional, though: your array must not contradict your own `editorial_vision`. If your vision named a tight-cut overlay (by type or effect), resolve it one of two ways — emit that overlay on the single tight boundary that most earns it, OR, only if you genuinely find no boundary earns it, that's a signal your vision overclaimed and you must not leave the claim standing. You may not both name an overlay in your vision and emit an empty array. When vision and array disagree, that is an error you fix here — by emitting the earned overlay, or by having not claimed it. Emit a second overlay only if a DISTINCT second boundary independently earns one under the criteria below.

**HARD RULE 3 — extras (`title`, `label`) belong to SceneTitle ONLY.** Emitting `title` or `label` with LightLeak / ShutterFlash / NewspaperWipe is a hard error — the validator rejects it. SceneTitle without a `title` is also a hard error (the panel has nothing to display).

Your `editorial_vision` and your `tight_cut_overlays` array must agree. If your vision commits to tight-cut overlays — either by naming a specific TYPE ('tight ShutterFlash cuts') OR by naming the EFFECT/MECHANISM ({_tco_mechanism_examples}) — emit at least one matching entry on the boundary that earns it. If on reflection no boundary earns one, that's fine — but then your vision should not claim the overlay or its effect. Vision and array tell the same story.

**Place overlays only where the cut carries real editorial weight.** Editorially-significant cuts include:
  - **chapter shift** — the speaker pivots from one segment of the argument to the next (setup → reveal, problem → solution, "and then" → "but here's the thing"). A strong chapter shift earns SceneTitle (a literal title for the new section). A softer shift earns one of the punctuation overlays.
  - **escalation beat** — the energy steps up across the cut (a stat, a punchline, a payoff lands right after) → ShutterFlash or NewspaperWipe.
  - **hook / close callback** — the cut joins a callback back to the video's opening hook or closing point → LightLeak fits best (reflective warmth).
  - **reveal / answer delivery** — the cut introduces the named thing the speaker was building toward → NewspaperWipe (headline drops).

If a tight boundary is a `pause` — mid-thought, a same-take micro-trim, a filler-removal splice, or any cut with no visual change — leaving it a clean hard cut is the right call there. (Scene changes are never bare; see HARD RULE 2.)

**Variety.** Across all decorations — scene-change and discretionary alike — don't repeat a type on adjacent boundaries. Two SceneTitles in one video is almost always wrong (a video usually has at most one true chapter break worth labeling); the same punctuation overlay back-to-back reads as templating. (The pipeline's scene-change floor already rotates types so adjacent backfills differ; match that intent in your own picks.)

**For heavier editorial weight, see the zero-handle transition path in HOW TO PLACE TRANSITIONS.** The same 4 type names (LightLeak / ShutterFlash / NewspaperWipe / SceneTitle) are also available as full zero-handle transitions on tight boundaries — 700-1800ms with audio silence and dominant video animation. Overlays are the LIGHT default for tight cuts; the heavy transition is the RARE exception reserved for genuine act/chapter breaks or the single biggest moment. Never emit both decorations on the same boundary — the validator will reject the recipe.
"""


    # ── Call 2: visual placement on the kept-only transcript ────────────────
    # Uses GEMINI_EDITORIAL_MODEL (Pro) — instruction-following on the detailed
    # component-placement rules is materially better than Flash. The cost/
    # latency premium is concentrated on this single call.
    post_cut_plan = _call_gemini_post_cuts(client, post_sys, post_user, _video_part, GEMINI_EDITORIAL_MODEL)

    # ── Recipe eval — log report against the window doctrine + hard rules ──
    # Run BEFORE anchor translation: the evaluator operates on the kept-only
    # index space (same space Gemini was working in), and after
    # _translate_post_cut_anchors_to_src() the indices reference source-space
    # so the boundary checks and window walk would be meaningless.
    #
    # Non-blocking by design — failures are logged but don't abort the
    # render. The point is observability: when an arc/window violation
    # appears repeatedly across renders we can decide whether to enforce
    # in Python or tighten the prompt. The patch_list() output is the
    # raw material for a future repair-pass loop if we want one.
    if isinstance(post_cut_plan, dict):
        try:
            from recipe_eval import evaluate_recipe as _eval_recipe
            _eval_words = [
                {
                    "word": str(_w.get("word") or ""),
                    "start": float(_w.get("start") or 0.0),
                    "end": float(_w.get("end") or 0.0),
                }
                for _w in kept_words
            ]
            # cut_boundaries = SLOTS ONLY (the list Gemini was actually
            # allowed to place transitions at). Passing the union here
            # would wrongly mask "transition placed at tight cut" failures
            # — same wires-disagreeing bug class one layer down.
            # tight_boundaries enables the transition-tight-boundary fail
            # and the tight-no-mask warning in recipe_eval.
            try:
                _eval_slots = list(_cut_boundary_indices or [])
                _eval_tight = list(_tight_boundary_indices or [])
            except NameError:
                # kept_words was empty — boundary block never ran.
                _eval_slots = []
                _eval_tight = []
            _eval_report = _eval_recipe(
                post_cut_plan,
                _eval_words,
                _eval_slots,
                float(_eval_words[-1]["end"] if _eval_words else 0.0),
                tight_boundaries=_eval_tight,
            )
            print(f"[recipe-eval]\n{_eval_report.summary()}", flush=True)
        except Exception as _eval_err:
            # Eval errors must never block the render — log and continue.
            print(f"[recipe-eval] error: {_eval_err} (non-blocking)", flush=True)

    # ── Vision↔array reconciliation for tight_cut_overlays ────────────────
    # Detects the "vision claims a tight-cut overlay, array came back empty"
    # contradiction that three prose fixes (coherence rule c1a, EFFECT/
    # MECHANISM extension 7b9069c, HARD RULE 2 tiebreaker c109e55) failed
    # to prevent in the main 60K-token generation. The detector and the
    # coherence rule both consume TIGHT_CUT_OVERLAY_MECHANISM_PHRASES from
    # type_registries — single source of truth so the reconciler fires on
    # exactly what the prompt taught Gemini to recognize as a commitment.
    #
    # Runs ONLY when: tight boundaries exist AND vision text claims an
    # overlay (TYPE name or MECHANISM phrase) AND emitted array is empty.
    # No-op for the common case (vision silent on overlays → default 0
    # framing stays correctly applied; no re-ask, no wall-clock cost).
    if isinstance(post_cut_plan, dict) and _eval_tight:
        try:
            _vp = post_cut_plan.get("video_plan") or {}
            _vision_raw = str(_vp.get("editorial_vision") or "").strip()
            _vision_lower = _vision_raw.lower()
            _types_lower = {_t.lower() for _t in VALID_TIGHT_CUT_OVERLAYS}
            _vision_claims_overlay = (
                any(_t in _vision_lower for _t in _types_lower)
                or any(_p in _vision_lower for _p in TIGHT_CUT_OVERLAY_MECHANISM_PHRASES)
            )
            _emitted_overlays = post_cut_plan.get("tight_cut_overlays") or []
            if _vision_claims_overlay and not _emitted_overlays:
                print(
                    f"[reconcile-overlays] DETECTED vision-claims-empty: "
                    f"vision={_vision_raw[:100]!r} tight_boundaries="
                    f"{sorted(_eval_tight)} — re-asking",
                    flush=True,
                )
                _reconciled = _reconcile_tight_cut_overlays(
                    client, _vision_raw, _eval_tight, kept_words,
                )
                if _reconciled:
                    post_cut_plan["tight_cut_overlays"] = _reconciled
        except Exception as _rec_err:
            # Reconciliation must never block the render — log and continue.
            # The array stays whatever Gemini's original pass produced.
            print(
                f"[reconcile-overlays] outer error: {_rec_err} (non-blocking, "
                f"keeping original empty array)",
                flush=True,
            )

    # ── Translate anchors: new index space → source index space ─────────────
    post_cut_plan = _translate_post_cut_anchors_to_src(post_cut_plan, new_to_src)

    # ── Merge: mechanical cuts + translated PostCutPlan → edit_plan ─────────
    # Mechanical cuts own notes, remove_words, pacing. PostCutPlan owns every
    # other field. The merged dict has the same shape downstream expects.
    edit_plan = {
        "notes": cut_plan.get("notes", "") or "",
        "remove_words": raw_cut_remove_words,
        "pacing": cut_plan.get("pacing", "fast") or "fast",
    }
    if isinstance(post_cut_plan, dict):
        for k, v in post_cut_plan.items():
            edit_plan[k] = v

    print(
        f"[two-pass] Merged plan — notes={len(edit_plan['notes'])} chars, "
        f"remove_words={len(edit_plan['remove_words'])}, "
        f"emphasis_moments={len(edit_plan.get('emphasis_moments') or [])}, "
        f"motion_graphics={len(edit_plan.get('motion_graphics') or [])}, "
        f"text_overlays={len(edit_plan.get('text_overlays') or [])}, "
        f"sound_effects={len(edit_plan.get('sound_effects') or [])}, "
        f"transitions={len(edit_plan.get('transitions') or [])}, "
        f"tight_cut_overlays={len(edit_plan.get('tight_cut_overlays') or [])}, "
        f"broll_clips={len(edit_plan.get('broll_clips') or [])}",
        flush=True,
    )

    # Surface video_plan — Gemini's editorial scaffold — in the render log
    # so it's auditable. If Gemini's component placements diverge from the
    # plan it wrote, the log shows where the disagreement is.
    _vp = edit_plan.get("video_plan") if isinstance(edit_plan, dict) else None
    if isinstance(_vp, dict):
        _moments = _vp.get("key_moments") or []
        print(
            f"[video-plan] {_vp.get('what_happens', '')}",
            flush=True,
        )
        print(
            f"[video-plan] shape: {_vp.get('story_shape', '')}",
            flush=True,
        )
        print(
            f"[video-plan] hook=word[{_vp.get('hook_word_index')}] "
            f"payoff=word[{_vp.get('payoff_word_index')}] "
            f"close=word[{_vp.get('close_word_index')}] "
            f"moments={len(_moments)}",
            flush=True,
        )
        for _m in _moments[:6]:
            if isinstance(_m, dict):
                print(
                    f"[video-plan]   moment word[{_m.get('word_index')}]: "
                    f"{_m.get('what_lands', '')!r}",
                    flush=True,
                )

    # ── Derivation pass: word_index → float timestamps for downstream code ──
    # Every downstream consumer (render_multi_clip, projection helpers,
    # thumbnail selection) expects float-time fields
    # (caption_position_segments, peak_at_seconds, source_start/source_end,
    # thumbnail_timestamp). Gemini emits word-anchored
    # inputs; Python synthesizes the float fields from word timings here.
    _dg = deepgram_words or []

    # No rounding: callers feed the result through project_source_time_to_output
    # against clip source bounds that ARE raw floats; rounding here loses
    # sub-millisecond precision and breaks boundary checks.
    def _word_start(src_idx):
        if src_idx is None or not (0 <= int(src_idx) < len(_dg)):
            return None
        return float(_dg[int(src_idx)].get("start") or 0)

    def _word_end(src_idx):
        if src_idx is None or not (0 <= int(src_idx) < len(_dg)):
            return None
        return float(_dg[int(src_idx)].get("end") or 0)

    # caption_position_segments (synthesized from caption_position_changes)
    _changes = edit_plan.get("caption_position_changes") or []
    _changes_clean = [
        c for c in _changes
        if isinstance(c, dict) and c.get("word_index") is not None
        and c.get("position") in ("top", "center", "bottom")
    ]
    _changes_clean.sort(key=lambda c: int(c["word_index"]))
    _segments = []
    _cur_pos = "bottom"  # default start position
    _cur_t = 0.0
    # No rounding: from/to_seconds get projected through clip source bounds
    # at render time; rounding here can land the value outside its own clip
    # due to sub-millisecond drift.
    for _ch in _changes_clean:
        _ch_t = _word_start(_ch["word_index"])
        if _ch_t is None:
            continue
        if _ch_t > _cur_t:
            _segments.append({
                "from_seconds": _cur_t,
                "to_seconds": _ch_t,
                "position": _cur_pos,
            })
        _cur_pos = _ch["position"]
        _cur_t = _ch_t
    # Final segment to video duration
    if duration > _cur_t:
        _segments.append({
            "from_seconds": _cur_t,
            "to_seconds": float(duration),
            "position": _cur_pos,
        })
    # Fallback: if no changes emitted, cover the whole video with default
    if not _segments and duration > 0:
        _segments = [{
            "from_seconds": 0.0,
            "to_seconds": float(duration),
            "position": "bottom",
        }]
    _segments = _coalesce_caption_position_segments(_segments)
    edit_plan["caption_position_segments"] = _segments

    # thumbnail_timestamp from thumbnail_word_index
    _twi = edit_plan.get("thumbnail_word_index")
    _tts = _word_start(_twi)
    if _tts is not None:
        edit_plan["thumbnail_timestamp"] = _tts

    print(
        f"[generate-edit] Derived float timestamps: "
        f"caption_segments={len(_segments)}, "
        f"thumbnail={edit_plan.get('thumbnail_timestamp')}",
        flush=True,
    )

    # Post-processing
    edit_plan["_deepgram_words"] = list(deepgram_words or [])
    # Preserve signals for downstream (render_multi_clip projects peak_at_seconds
    # to output frames using the same logic as SFX/captions/b-roll). Underscored
    # so the sanitized recipe strips them from persistence.
    edit_plan["_shot_changes"] = list(_shots)
    edit_plan["_vocal_emphasis"] = list(_vocal)
    edit_plan["_source_loudness_signal"] = dict(_loudness)
    # Face detections are consumed exactly once — to build the prompt signals
    # above. Once _build_post_cuts_prompt has returned, the raw face data has
    # no downstream reader (the Remotion composition renders motion_graphics
    # against the canvas via resolveMGPosition; no face lookup happens at
    # render time). Do NOT stash onto edit_plan — it would be dead weight.
    analysis = build_analysis_from_gemini_recipe(edit_plan, duration=duration)
    has_burned_captions = infer_has_burned_captions(edit_plan, analysis, log_prefix="[generate-edit]")

    video_duration = float(analysis.get("duration") or 0)
    _dg_words = edit_plan.get("_deepgram_words", [])
    raw_remove_words = edit_plan.get("remove_words") or []

    # ── Guard: drop Gemini range cuts covering an ANCHORED word ──────────────
    # Anchor integrity is the absolute invariant — if Gemini tried to
    # range-cut a word it also anchored to (rare; ranges are reserved for
    # narrative skips of unrelated tangents), the anchor wins and the range
    # is dropped. Compute the anchor-referenced set by walking every field
    # that carries a word index. Translation to source indices has already
    # happened above, so everything is in source space here.
    _anchored_src_indices = set()
    for _em in (edit_plan.get("emphasis_moments") or []):
        if isinstance(_em, dict):
            for _wi in (_em.get("word_indices") or []):
                if isinstance(_wi, int):
                    _anchored_src_indices.add(_wi)
    for _ov in (edit_plan.get("text_overlays") or []):
        if isinstance(_ov, dict) and isinstance(_ov.get("start_word_index"), int):
            _anchored_src_indices.add(_ov["start_word_index"])
    for _mg in (edit_plan.get("motion_graphics") or []):
        if isinstance(_mg, dict):
            for _k in ("start_word_index", "end_word_index"):
                if isinstance(_mg.get(_k), int):
                    _anchored_src_indices.add(_mg[_k])
    for _sfx in (edit_plan.get("sound_effects") or []):
        if isinstance(_sfx, dict) and isinstance(_sfx.get("word_index"), int):
            _anchored_src_indices.add(_sfx["word_index"])
    for _tr in (edit_plan.get("transitions") or []):
        if isinstance(_tr, dict) and isinstance(_tr.get("after_word_index"), int):
            _anchored_src_indices.add(_tr["after_word_index"])
    for _bc in (edit_plan.get("broll_clips") or []):
        if isinstance(_bc, dict):
            for _k in ("start_word_index", "end_word_index"):
                if isinstance(_bc.get(_k), int):
                    _anchored_src_indices.add(_bc[_k])

    if raw_remove_words and _anchored_src_indices and _dg_words:
        _anchored_times = []
        for _pi in _anchored_src_indices:
            if 0 <= _pi < len(_dg_words):
                _w = _dg_words[_pi]
                _anchored_times.append((
                    float(_w.get("start") or 0),
                    float(_w.get("end") or 0),
                    _pi,
                ))
        _filtered = []
        for _rw in raw_remove_words:
            if not isinstance(_rw, dict):
                continue
            # Index-based range: covers the open interval (after, before).
            # An anchored word i with after < i < before is "covered."
            if (
                _rw.get("after_word_index") is not None
                and _rw.get("before_word_index") is not None
                and _rw.get("word_index") is None
            ):
                try:
                    _aw = int(_rw["after_word_index"])
                    _bw = int(_rw["before_word_index"])
                except (TypeError, ValueError):
                    continue
                _covers_anchor = next(
                    (_pi for _pi in _anchored_src_indices if _aw < _pi < _bw),
                    None,
                )
                if _covers_anchor is not None:
                    _pword = _dg_words[_covers_anchor]
                    _pw_text = str(_pword.get("punctuated_word") or _pword.get("word") or "").strip()
                    print(
                        f"[generate-edit] Dropping Gemini range cut "
                        f"after_word={_aw}/before_word={_bw} "
                        f"— covers ANCHORED word [{_covers_anchor}] '{_pw_text}' "
                        f"(anchor-integrity guard)",
                        flush=True,
                    )
                    continue
            # Legacy float range: open-interval overlap with anchored word's
            # [start, end]. Kept for cached plans and silence-tighten micro-
            # cuts (Python-internal, not Gemini-emitted).
            elif "start" in _rw and "end" in _rw and "word_index" not in _rw:
                try:
                    _rs = float(_rw["start"])
                    _re = float(_rw["end"])
                except (TypeError, ValueError):
                    continue
                _covers_anchor = None
                for (_pws, _pwe, _pi) in _anchored_times:
                    if _rs < _pwe and _re > _pws:
                        _covers_anchor = _pi
                        break
                if _covers_anchor is not None:
                    _pword = _dg_words[_covers_anchor]
                    _pw_text = str(_pword.get("punctuated_word") or _pword.get("word") or "").strip()
                    print(
                        f"[generate-edit] Dropping Gemini range cut {_rs:.2f}-{_re:.2f}s "
                        f"— covers ANCHORED word [{_covers_anchor}] '{_pw_text}' "
                        f"(anchor-integrity guard)",
                        flush=True,
                    )
                    continue
            _filtered.append(_rw)
        raw_remove_words = _filtered

    # Gemini's remove_words is the authoritative cut list — every filler,
    # stutter, restart, dead-air range, breath, and tangent. No injection,
    # no merging from upstream passes (those have been removed from the
    # pipeline entirely).

    validated_cuts = []
    if not _dg_words:
        raise ValueError(
            "No speech detected in source (Deepgram returned 0 words). This pipeline "
            "is a talking-head editor and requires spoken audio to produce an edit plan."
        )
    if isinstance(raw_remove_words, list):
        print(f"[DIAG] Full transcript ({len(_dg_words)} words):", flush=True)
        for i, w in enumerate(_dg_words):
            spk = w.get('speaker', '?')
            print(
                f"[DIAG]   [{i}] {float(w.get('start') or 0):.3f}-{float(w.get('end') or 0):.3f} "
                f"(spk{spk}): {w.get('punctuated_word') or w.get('word')}",
                flush=True,
            )
        normalized_remove_words = []
        for item in raw_remove_words:
            if not isinstance(item, dict):
                continue
            if "word_index" in item and item.get("word_index") is not None:
                try:
                    idx = int(item["word_index"])
                except Exception:
                    continue
                if 0 <= idx < len(_dg_words):
                    normalized_remove_words.append({
                        "word_index": idx,
                        "reason": str(item.get("reason") or "remove"),
                    })
                    w = _dg_words[idx]
                    word_text = w.get("punctuated_word") or w.get("word") or ""
                    print(
                        f"[remove] Removing word [{idx}] '{word_text}' ({item.get('reason', 'unknown')})",
                        flush=True,
                    )
                else:
                    print(
                        f"[remove] WARNING: word_index {idx} out of bounds (max {len(_dg_words)-1})",
                        flush=True,
                    )
            elif (
                item.get("after_word_index") is not None
                and item.get("before_word_index") is not None
            ):
                # Index-based range form: drop the silence between word[aw]
                # and word[bw], plus any words strictly between them.
                # build_clips_from_words consumes this shape directly — it
                # forces a clip split at every accepted dead_air boundary
                # (including the consecutive-anchor case (N, N+1) where no
                # words sit between the anchors but the silence still gets
                # cut). The previous normalizer dropped these entries
                # silently; Gemini's dead_air decisions never reached
                # build_clips_from_words and the gaps played through.
                try:
                    aw = int(item["after_word_index"])
                    bw = int(item["before_word_index"])
                except Exception:
                    continue
                if bw <= aw:
                    print(
                        f"[remove] WARNING: range word[{aw}]→word[{bw}] has bw<=aw, dropped",
                        flush=True,
                    )
                    continue
                if not (0 <= aw < len(_dg_words) and 0 <= bw < len(_dg_words)):
                    print(
                        f"[remove] WARNING: range anchors word[{aw}]→word[{bw}] out of bounds "
                        f"(transcript has {len(_dg_words)} words)",
                        flush=True,
                    )
                    continue
                normalized_remove_words.append({
                    "after_word_index": aw,
                    "before_word_index": bw,
                    "reason": str(item.get("reason") or "range_remove"),
                })
                print(
                    f"[remove] Removing range word[{aw}]→word[{bw}] "
                    f"({item.get('reason', 'unknown')})",
                    flush=True,
                )
            elif "start" in item and "end" in item:
                try:
                    rw_s = max(0.0, float(item["start"]))
                    rw_e = max(0.0, float(item["end"]))
                except Exception:
                    continue
                if rw_e > rw_s:
                    if video_duration > 0:
                        rw_e = min(rw_e, video_duration)
                    if rw_e <= rw_s:
                        continue
                    normalized_remove_words.append({
                        "start": round(rw_s, 3),
                        "end": round(rw_e, 3),
                        "reason": str(item.get("reason") or "remove"),
                    })
                    print(
                        f"[remove] Removing range {rw_s:.2f}-{rw_e:.2f} ({item.get('reason', 'unknown')})",
                        flush=True,
                    )

        edit_plan["remove_words"] = normalized_remove_words
        print(
            f"[generate-edit] Building clips: {len(_dg_words)} words, "
            f"{len(normalized_remove_words)} Gemini removals",
            flush=True,
        )
        validated_cuts, _removed_word_indices = build_clips_from_words(_dg_words, normalized_remove_words, video_duration=video_duration)
        edit_plan["_removed_word_indices"] = _removed_word_indices

        # ── Shot-change-based clip splitting ────────────────────────────────
        # Each entry in _shot_boundaries (computed pre-Gemini using the same
        # cluster_shot_changes + shot_change_word_boundaries logic) is a
        # (new_idx, source_time) pair. Split validated_cuts only at boundaries
        # where Gemini ACTUALLY placed a transition. Reason: scdet fires on
        # graphical overlay edges (PiP, embedded-video insert appearing or
        # disappearing) as well as real camera cuts — those overlay edges show
        # up in shot_change_word_boundaries identically. Splitting at every
        # detected shot change forces sub-clips around overlay edges; Gemini
        # is taught (per the OVERLAY rule in CRAFT TECHNIQUES) NOT to place
        # transitions at overlay edges. Gating the split on transition
        # presence makes the pipeline structurally inert to the false
        # positives — no sub-clip created where no transition will play.
        if _shots and validated_cuts:
            # Re-derive the kept-words list at this scope (matches the pre-
            # Gemini computation since the same _dg_words + _removed_word_indices
            # determine kept-only ordering).
            _post_kept = [
                _w for _i, _w in enumerate(_dg_words)
                if _i not in (_removed_word_indices or set())
            ]
            _shot_split_pairs = shot_change_word_boundaries(_shots, _post_kept)
            # Filter to boundaries where Gemini emitted a transition.
            _emitted_trans_indices = {
                int(_t["after_word_index"])
                for _t in (edit_plan.get("transitions") or [])
                if isinstance(_t, dict)
                and _t.get("after_word_index") is not None
                and str(_t.get("type") or "none") != "none"
            }
            _gated_pairs = [
                (_ni, _st) for (_ni, _st) in _shot_split_pairs
                if _ni in _emitted_trans_indices
            ]
            _skipped = len(_shot_split_pairs) - len(_gated_pairs)
            if _skipped > 0:
                print(
                    f"[shot-split] Gated by emitted transitions: "
                    f"{_skipped} shot-change boundary(ies) had no transition "
                    f"(overlay edge or Gemini skip) → no sub-clip split",
                    flush=True,
                )
            _split_times = sorted({_st for (_, _st) in _gated_pairs})
            if _split_times:
                _new_cuts = []
                _total_splits = 0
                for _clip in validated_cuts:
                    _cs = float(_clip["source_start"])
                    _ce = float(_clip["source_end"])
                    _internal = [_st for _st in _split_times if _cs + 0.05 < _st < _ce - 0.05]
                    if not _internal:
                        _new_cuts.append(_clip)
                        continue
                    _boundaries = [_cs] + _internal + [_ce]
                    for _bi in range(len(_boundaries) - 1):
                        _sub_start = _boundaries[_bi]
                        _sub_end = _boundaries[_bi + 1]
                        if _sub_end - _sub_start <= 0:
                            continue
                        _sub = {**_clip, "source_start": _sub_start, "source_end": _sub_end}
                        if _bi != len(_boundaries) - 2:
                            _sub["transition_out"] = "none"
                        _new_cuts.append(_sub)
                    _total_splits += len(_internal)
                if _total_splits > 0:
                    print(
                        f"[shot-split] Validated cuts: {len(validated_cuts)} → "
                        f"{len(_new_cuts)} clips ({_total_splits} internal "
                        f"shot-change split(s) applied)",
                        flush=True,
                    )
                    validated_cuts = _new_cuts

        # ── Cross-check guard: every clip-split boundary must be a known cut ─
        # The original transitions bug was two boundary sources that never
        # agreed — the list shown to Gemini (CUT BOUNDARIES + TIGHT BOUNDARIES
        # union) and the clip-split path inside build_clips_from_words. If the
        # renderer splits a clip at a kept-word index that's in NEITHER list,
        # that's a new instance of the same bug class and means a third
        # boundary source has appeared (or a code path drifted). Loud log
        # rather than silent jump-cut.
        try:
            if validated_cuts and len(validated_cuts) > 1 and kept_words:
                try:
                    _known = set(_all_boundary_indices)
                except NameError:
                    # kept_words was empty so the boundary block never ran.
                    # No known boundaries — every split is unknown by definition.
                    _known = set()
                _split_boundaries = set()
                for _ci in range(len(validated_cuts) - 1):
                    _end_t = float(validated_cuts[_ci].get("source_end") or 0.0)
                    # Find the kept-word whose .end is closest to _end_t within tolerance.
                    _best_ni = None
                    _best_dist = 0.10
                    for _ni, _w in enumerate(kept_words):
                        _dist = abs(float(_w.get("end") or 0.0) - _end_t)
                        if _dist <= _best_dist:
                            _best_dist = _dist
                            _best_ni = _ni
                    if _best_ni is not None:
                        _split_boundaries.add(_best_ni)
                for _b in sorted(_split_boundaries - _known):
                    _record_divergence(
                        "cut_boundary",
                        {"kept_word_index": _b},
                        "clip_split_without_known_boundary",
                        reason="renderer_split_at_boundary_gemini_never_saw",
                    )
        except Exception as _xc_err:
            # The guard is observability only — must never break the render.
            print(f"[divergence] cross-check guard error: {_xc_err}", flush=True)

        # Drop caption_position_changes anchored to removed words and
        # re-derive caption_position_segments. If Gemini happens to anchor
        # a position change to the same word it also lists in remove_words,
        # the change references a word that doesn't appear on screen —
        # would render as a 0.5s caption flicker at the removed-word
        # position. Re-synthesize from the filtered list.
        _removed_set = set(_removed_word_indices) if _removed_word_indices else set()
        if _removed_set:
            _raw_changes = edit_plan.get("caption_position_changes") or []
            _filtered_changes = [
                _ch for _ch in _raw_changes
                if isinstance(_ch, dict) and _ch.get("word_index") is not None
                and int(_ch["word_index"]) not in _removed_set
            ]
            if len(_filtered_changes) != len(_raw_changes):
                _dropped = len(_raw_changes) - len(_filtered_changes)
                edit_plan["caption_position_changes"] = _filtered_changes
                # Re-synthesize caption_position_segments from filtered changes.
                # Same logic as the derivation block above (~line 3735).
                _filtered_changes_clean = [
                    c for c in _filtered_changes
                    if isinstance(c, dict) and c.get("word_index") is not None
                    and c.get("position") in ("top", "center", "bottom")
                ]
                _filtered_changes_clean.sort(key=lambda c: int(c["word_index"]))
                _resynth_segments = []
                _cur_pos = "bottom"
                _cur_t = 0.0
                # No rounding: from/to_seconds get projected through clip
                # source bounds at render time; any rounding here can land
                # the value outside its own clip due to sub-millisecond drift.
                for _ch in _filtered_changes_clean:
                    _wi = int(_ch["word_index"])
                    if _wi < 0 or _wi >= len(_dg_words):
                        continue
                    _ch_t = float(_dg_words[_wi].get("start") or 0)
                    if _ch_t > _cur_t:
                        _resynth_segments.append({
                            "from_seconds": _cur_t,
                            "to_seconds": _ch_t,
                            "position": _cur_pos,
                        })
                    _cur_pos = _ch["position"]
                    _cur_t = _ch_t
                if video_duration > _cur_t:
                    _resynth_segments.append({
                        "from_seconds": _cur_t,
                        "to_seconds": float(video_duration),
                        "position": _cur_pos,
                    })
                if not _resynth_segments and video_duration > 0:
                    _resynth_segments = [{
                        "from_seconds": 0.0,
                        "to_seconds": float(video_duration),
                        "position": "bottom",
                    }]
                _resynth_segments = _coalesce_caption_position_segments(_resynth_segments)
                edit_plan["caption_position_segments"] = _resynth_segments
                print(
                    f"[generate-edit] Dropped {_dropped} caption_position_change(s) "
                    f"anchored to removed words; re-synthesized "
                    f"{len(_resynth_segments)} segment(s)",
                    flush=True,
                )
        for i, clip in enumerate(validated_cuts):
            clip_start = float(clip["source_start"])
            clip_end = float(clip["source_end"])
            # Find words inside this clip using padded boundaries
            clip_words = []
            for w in _dg_words:
                ws = float(w.get("start") or 0)
                we = float(w.get("end") or 0)
                if ws >= clip_start - 0.02 and we <= clip_end + 0.02:
                    clip_words.append(w.get("punctuated_word") or w.get("word") or "")
            first_word = clip_words[0] if clip_words else ""
            last_word = clip_words[-1] if clip_words else ""
            print(
                f"[clips] Clip {i}: {clip_start:.3f}-{clip_end:.3f} "
                f"({len(clip_words)} words) '{first_word}' ... '{last_word}'",
                flush=True,
            )
        if not validated_cuts:
            raise ValueError("Gemini response removed all words — no clips remain")
    else:
        raise ValueError(
            "Gemini response missing remove_words — the edit plan must include a "
            "remove_words list (empty array is allowed to keep every word, but the "
            "key itself is required)."
        )

    # Verify no large gaps in output (monitoring only — not auto-removing)
    for _gi in range(1, len(validated_cuts)):
        _prev_end = float(validated_cuts[_gi - 1].get("source_end", 0))
        _curr_start = float(validated_cuts[_gi].get("source_start", 0))
        _gap = _curr_start - _prev_end
        if _gap > 0.5:
            print(f"[gap-check] WARNING: {_gap:.2f}s gap between clip {_gi-1} and clip {_gi} (source {_prev_end:.2f}s-{_curr_start:.2f}s)", flush=True)

    # Apply transitions from Gemini's transitions array onto clips.
    # Each transition has after_word_index — find the clip whose source range
    # contains that word's timestamp and set transition_out on it. If the
    # transition can't land (word fell in a cut, or it's in the last clip
    # with no subsequent clip), DROP that single transition and continue —
    # same auto-handle pattern as caption z-order: Python OWNS the cross-
    # field consistency, the rest of the plan still renders.
    # Removed-word set is referenced by BOTH the transitions validator below
    # AND the tight_cut_overlays validator further down (each drops entries
    # whose after_word_index targets a word the cuts pass removed). Derive
    # once here, before either branch, so the overlay path works on jobs
    # that emit overlays without transitions — single-clip footage with all
    # visual cuts in TIGHT BOUNDARIES (the audio gate's zero-handle gap
    # produces this shape; see the audio-gap-vs-visual-cut investigation).
    # Previously this assignment lived inside `if raw_transitions and
    # _dg_words:` and the overlay read at the validator below hit
    # UnboundLocalError on the no-transitions-emitted path. The resolver
    # is safe on every input — empty set on empty remove_words OR empty
    # deepgram_words (handler.py:5227-5228, 5231).
    _tr_removed = _remove_words_to_src_indices(
        edit_plan.get("remove_words") or [], _dg_words,
    )

    # Tight-boundary set in SOURCE space — read by BOTH validators after
    # Option B lands (2026-06-21): transitions validator rejects crossfade
    # types whose after_word_index falls on a tight boundary, and the
    # tight_cut_overlays validator rejects overlays whose after_word_index
    # doesn't. Same kept→source translation pattern used by the overlay
    # validator before the lift; defended against NameError on degenerate
    # transcripts where _tight_boundary_indices was never built (the
    # boundary block at handler.py:~6155 skips on empty kept_words).
    try:
        _tight_src_set = {
            new_to_src[_ki] for _ki in _tight_boundary_indices
            if 0 <= _ki < len(new_to_src)
        }
        # Shot-change subset of the tight boundaries, in source space — the
        # scene-change decoration FLOOR (below) backfills any of these left
        # bare by Gemini. Same kept→source translation; a "both" boundary
        # (audio gap AND shot change) is a real scene change, so it's included.
        _shot_src_set = {
            new_to_src[_ki] for _ki in _tight_boundary_indices
            if _ki in _shot_boundary_set and 0 <= _ki < len(new_to_src)
        }
        # Source-index → scdet confidence score, for the floor's confidence gate.
        _shot_src_score = {
            new_to_src[_ki]: _shot_boundary_scores.get(_ki)
            for _ki in _tight_boundary_indices
            if _ki in _shot_boundary_set and 0 <= _ki < len(new_to_src)
        }
    except NameError:
        _tight_src_set = set()
        _shot_src_set = set()
        _shot_src_score = {}

    # Boundaries (source after_word_index) carrying a real transition → type.
    # Overlays and the scene-change floor read this to skip double-decorating a
    # boundary that already has a transition (transition wins — heavier).
    _transition_type_by_awi = {}
    raw_transitions = edit_plan.get("transitions") or []
    if raw_transitions and _dg_words:
        # Transitions = pack PascalCase names. VALID_TRANSITION_TYPES is the
        # canonical set; mirror it here so adding a type only edits one place.
        _valid_tr_types = set(VALID_TRANSITION_TYPES)
        for _ti, tr in enumerate(raw_transitions):
            if not isinstance(tr, dict):
                raise ValueError(f"transitions[{_ti}] must be an object")
            tr_type = str(tr.get("type") or "").strip()
            if tr_type not in _valid_tr_types:
                raise ValueError(
                    f"transitions[{_ti}].type={tr_type!r} is not a valid transition "
                    f"(must be one of {sorted(_valid_tr_types)})"
                )
            awi = tr.get("after_word_index")
            if awi is None or not isinstance(awi, (int, float)):
                raise ValueError(
                    f"transitions[{_ti}] ({tr_type}) missing numeric after_word_index"
                )
            awi = int(awi)
            if awi < 0 or awi >= len(_dg_words):
                # Out-of-bounds index — drop this transition; render proceeds
                # without it. Logged loudly so the operator notices.
                print(
                    f"[generate-edit] DROP transition '{tr_type}' [{_ti}]: "
                    f"after_word_index={awi} out of bounds (transcript has "
                    f"{len(_dg_words)} words). Render continues without this "
                    f"transition.",
                    flush=True,
                )
                continue
            if awi in _tr_removed:
                # The transition word got cut by a downstream pass. Drop the
                # transition; the rest of the plan still renders.
                print(
                    f"[generate-edit] DROP transition '{tr_type}' [{_ti}]: "
                    f"after_word_index={awi} targets a removed word. Render "
                    f"continues without this transition.",
                    flush=True,
                )
                continue
            # Type-eligibility per boundary class: crossfade transitions need
            # CUT BOUNDARIES (audio handle for the equal-power crossfade at
            # handler.py:11540-11557); zero-handle types work on either CUT or
            # TIGHT BOUNDARIES (audio-hard-cut branch at handler.py:11512-11538
            # substitutes silence + click-prevention fades, no handle needed).
            # On TIGHT BOUNDARIES, anything outside ZERO_HANDLE_TRANSITION_TYPES
            # would audio-mush the speaker's continuous speech across the cut.
            # HOW TO PLACE TRANSITIONS HARD RULE 1 in the prompt teaches the
            # same rule; this validator is the structural backstop.
            if awi in _tight_src_set and tr_type not in ZERO_HANDLE_TRANSITION_TYPES:
                raise ValueError(
                    f"transitions[{_ti}].type={tr_type!r} at after_word_index={awi} "
                    f"is a TIGHT BOUNDARY (no audio handle). Only zero-handle "
                    f"transition types {sorted(ZERO_HANDLE_TRANSITION_TYPES)} are "
                    f"valid on tight boundaries — crossfade types would audio-mush "
                    f"continuous speech across the cut. Either move this transition "
                    f"to a CUT BOUNDARY, change its type to a zero-handle one, or "
                    f"replace it with a `tight_cut_overlay` for lighter editorial "
                    f"weight."
                )
            word_end = float(_dg_words[awi].get("end") or 0)
            # Build extras dict — copy through all component-specific props
            _extras = {
                k: v for k, v in tr.items()
                if k not in ("type", "after_word_index") and v is not None
            }
            # Find the clip that contains this word (with 50ms tolerance) and
            # has a successor to transition INTO. If the word lands in the last
            # clip (or isn't found), no clip-pair exists for this transition;
            # drop it and continue.
            _applied = False
            for ci, clip in enumerate(validated_cuts):
                cs = float(clip["source_start"])
                ce = float(clip["source_end"])
                if cs - 0.05 <= word_end <= ce + 0.05 and ci < len(validated_cuts) - 1:
                    clip["transition_out"] = tr_type
                    _transition_type_by_awi[awi] = tr_type
                    if _extras:
                        clip["_transition_extras"] = _extras
                    print(f"[generate-edit] Transition '{tr_type}' applied to clip {ci} (after word {awi})", flush=True)
                    _applied = True
                    break
            if not _applied:
                # Lands in the last clip OR doesn't fall in any clip range
                # (rare edge case: dead-air gap exactly straddling word_end).
                # Drop the transition; render proceeds with the rest of the plan.
                print(
                    f"[generate-edit] DROP transition '{tr_type}' [{_ti}]: "
                    f"after_word_index={awi} (t={word_end:.2f}s) lands in the "
                    f"last clip or no clip-pair exists. Render continues "
                    f"without this transition.",
                    flush=True,
                )

    # Transition count/variety is Gemini's decision — the prompt teaches restraint.

    # ── Tight-cut overlays (paint-on-top decorations at TIGHT BOUNDARIES) ────
    # Overlays attach to a FRAME POSITION (the boundary word's projected output
    # frame), NOT a clip-pair. OverlayCutEffect paints on top of continuously-
    # playing video and needs only atFrame (no clipA/clipB) — so an overlay is
    # valid on ANY tight boundary, including one sitting MID-CLIP (no sub-clip
    # split). Resolved overlays are collected here as a flat, boundary-keyed
    # list; the render projects each after_word_index to an output frame via
    # _projected_words. (Previously overlays required a clip WITH A SUCCESSOR,
    # which silently dropped every overlay on a no-removal / no-transition video
    # where the whole take is one clip — the attachment bug behind the session's
    # overlay failures.)
    #
    # _resolved_overlays: [{after_word_index (source), type, title?, label?}].
    _resolved_overlays = []
    _overlay_awis = set()  # boundaries already carrying an overlay
    raw_tco = edit_plan.get("tight_cut_overlays") or []
    if raw_tco and _dg_words:
        _valid_tco_types = set(VALID_TIGHT_CUT_OVERLAYS)
        # The ≤2 cap governs Gemini's DISCRETIONARY emissions only; the
        # scene-change floor below backfills uncapped (a separate goal).
        _TIGHT_CUT_OVERLAY_CAP = 2
        _applied_tco_count = 0
        for _toi, tco in enumerate(raw_tco):
            if not isinstance(tco, dict):
                raise ValueError(f"tight_cut_overlays[{_toi}] must be an object")
            tco_type = str(tco.get("type") or "").strip()
            if tco_type not in _valid_tco_types:
                raise ValueError(
                    f"tight_cut_overlays[{_toi}].type={tco_type!r} is not valid "
                    f"(must be one of {sorted(_valid_tco_types)})"
                )
            # SceneTitle is the ONLY overlay that takes extras (title + label).
            # title required; label optional. The other three reject extras.
            tco_title_raw = tco.get("title")
            tco_label_raw = tco.get("label")
            tco_title = str(tco_title_raw).strip() if isinstance(tco_title_raw, str) else None
            tco_label = str(tco_label_raw).strip() if isinstance(tco_label_raw, str) else None
            if tco_type == "SceneTitle":
                if not tco_title:
                    raise ValueError(
                        f"tight_cut_overlays[{_toi}] (SceneTitle) is missing "
                        f"`title` — SceneTitle requires a 1-3 word uppercase "
                        f"title for the typographic panel."
                    )
            else:
                if tco_title is not None or tco_label is not None:
                    raise ValueError(
                        f"tight_cut_overlays[{_toi}] ({tco_type}) carries "
                        f"title/label, but only SceneTitle uses them. "
                        f"Strip them or change the type."
                    )
            awi_t = tco.get("after_word_index")
            if awi_t is None or not isinstance(awi_t, (int, float)):
                raise ValueError(
                    f"tight_cut_overlays[{_toi}] ({tco_type}) missing numeric after_word_index"
                )
            awi_t = int(awi_t)
            if awi_t < 0 or awi_t >= len(_dg_words):
                print(
                    f"[generate-edit] DROP tight_cut_overlay '{tco_type}' [{_toi}]: "
                    f"after_word_index={awi_t} out of bounds (transcript has "
                    f"{len(_dg_words)} words).",
                    flush=True,
                )
                continue
            if awi_t in _tr_removed:
                print(
                    f"[generate-edit] DROP tight_cut_overlay '{tco_type}' [{_toi}]: "
                    f"after_word_index={awi_t} targets a removed word.",
                    flush=True,
                )
                continue
            if awi_t not in _tight_src_set:
                # Overlay at a CUT boundary (transitions live there) or a
                # non-boundary index. The overlay path only fires at TIGHT
                # boundaries. (Empty _tight_src_set ≡ no tight boundaries pass.)
                print(
                    f"[generate-edit] DROP tight_cut_overlay '{tco_type}' [{_toi}]: "
                    f"after_word_index={awi_t} is not a TIGHT BOUNDARY — overlay "
                    f"requires a tight cut to decorate.",
                    flush=True,
                )
                continue
            if awi_t in _transition_type_by_awi:
                # Collision: this boundary already carries a transition (the
                # heavier decoration wins). One decoration per boundary.
                print(
                    f"[generate-edit] DROP tight_cut_overlay '{tco_type}' [{_toi}]: "
                    f"after_word_index={awi_t} already has transition "
                    f"{_transition_type_by_awi[awi_t]!r}.",
                    flush=True,
                )
                continue
            if awi_t in _overlay_awis:
                print(
                    f"[generate-edit] DROP tight_cut_overlay '{tco_type}' [{_toi}]: "
                    f"after_word_index={awi_t} already has an overlay (duplicate).",
                    flush=True,
                )
                continue
            if _applied_tco_count >= _TIGHT_CUT_OVERLAY_CAP:
                print(
                    f"[generate-edit] DROP tight_cut_overlay '{tco_type}' [{_toi}]: "
                    f"per-video cap of {_TIGHT_CUT_OVERLAY_CAP} already reached. "
                    f"Sparing placement keeps the overlay editorial, not templated.",
                    flush=True,
                )
                continue
            _spec = {"after_word_index": awi_t, "type": tco_type}
            if tco_type == "SceneTitle":
                _spec["title"] = tco_title
                if tco_label:
                    _spec["label"] = tco_label
            _resolved_overlays.append(_spec)
            _overlay_awis.add(awi_t)
            _applied_tco_count += 1
            _extras_log = ""
            if tco_type == "SceneTitle":
                _extras_log = f" title={tco_title!r}"
                if tco_label:
                    _extras_log += f" label={tco_label!r}"
            print(
                f"[generate-edit] tight_cut_overlay '{tco_type}' resolved at "
                f"after_word_index={awi_t}{_extras_log}",
                flush=True,
            )

    # ── Scene-change decoration FLOOR (deterministic backfill) ─────────
    # Every shot-change tight boundary (a real scdet-flagged visual cut, not a
    # silence-only pause) MUST carry a decoration. Gemini's transitions +
    # overlays are resolved above; any shot-change boundary still BARE of both
    # gets a varied overlay here. The floor cannot under-emit — it does not
    # depend on the model. Pause (dead_air-only) boundaries are NOT backfilled.
    #
    # Frame-position attach (no clip-pair needed) means EVERY shot boundary is
    # decorable, including the mid-clip ones the old clip-successor model
    # silently dropped.
    #
    # Confidence gate (false-positive guardrail): the floor auto-decorates only
    # boundaries whose scdet score clears SCENE_FLOOR_MIN_SCDET_SCORE — real
    # camera cuts score high; PiP/insert edges (which the old split-gate
    # filtered for free via Gemini's vision judgment) score lower and are
    # skipped. Unknown score ⇒ fail OPEN (decorate). Gemini's OWN overlays above
    # are NOT score-gated.
    #
    # Cap scoping (Option A): backfill appends straight to _resolved_overlays
    # and never touches _applied_tco_count, so it is UNCAPPED by construction;
    # the ≤2 cap still governs Gemini's discretionary emissions.
    #
    # Variety: types rotate across the 3 light punctuation overlays (SceneTitle
    # and DipToBlack held out) so no two adjacent scene decorations share a type.
    _scene_n_shot = 0
    _scene_n_lowconf = 0
    _scene_n_gemini = 0
    _scene_backfilled = 0
    if _shot_src_set:
        # Ordered shot-change boundaries (temporal, by source word index). Each:
        # current decoration type (transition or Gemini overlay → locked;
        # None = bare) and scdet confidence score. Low-confidence BARE
        # boundaries are dropped from the sequence (skipped, not decorated).
        _floor_seq = []  # in-scope: [(awi_src, current_type_or_None)]
        for _si in sorted(_shot_src_set):
            if _si < 0 or _si >= len(_dg_words):
                continue
            _scene_n_shot += 1
            _cur = _transition_type_by_awi.get(_si)
            if _cur is None and _si in _overlay_awis:
                # Locked by a Gemini overlay — recover its type for adjacency.
                _cur = next(
                    (str(_o["type"]) for _o in _resolved_overlays
                     if _o["after_word_index"] == _si),
                    "overlay",
                )
            if _cur is not None:
                _scene_n_gemini += 1
                _floor_seq.append((_si, _cur))
                continue
            _score = _shot_src_score.get(_si)
            if _score is not None and _score < SCENE_FLOOR_MIN_SCDET_SCORE:
                _scene_n_lowconf += 1
                continue  # likely PiP/insert edge — floor skips it
            _floor_seq.append((_si, None))
        # Deterministic variety fill over the in-scope sequence.
        _resolved_floor_types = _scene_floor_rotation([_t for (_si, _t) in _floor_seq])
        for _idx, (_si, _cur) in enumerate(_floor_seq):
            if _cur is not None:
                continue  # already decorated (Gemini) — keep its pick
            _ftype = _resolved_floor_types[_idx]
            _resolved_overlays.append({"after_word_index": _si, "type": _ftype})
            _overlay_awis.add(_si)
            _scene_backfilled += 1
            print(
                f"[scene-floor] backfill '{_ftype}' at after_word_index={_si} "
                f"(bare scene-change boundary)",
                flush=True,
            )
    # Unconditional summary — fires even at 0 so "ran but found nothing
    # attachable" never again looks like "never ran".
    print(
        f"[scene-floor] shot_boundaries={_scene_n_shot} "
        f"(gemini_decorated={_scene_n_gemini}, "
        f"low_confidence_skipped={_scene_n_lowconf}, "
        f"backfilled={_scene_backfilled}); "
        f"min_score={SCENE_FLOOR_MIN_SCDET_SCORE}; final overlay types in order: "
        f"{[_o['type'] for _o in sorted(_resolved_overlays, key=lambda _o: _o['after_word_index'])]}",
        flush=True,
    )

    # ── Tight-decoration collision backstop ────────────────────────────
    # One decoration per boundary: no boundary may carry BOTH a transition and
    # an overlay. Prevented at append time (overlays skip boundaries already
    # holding a transition; backfill skips locked boundaries) — this is the
    # structural backstop. Gated by _TIGHT_DECORATION_COLLISION: "strict"
    # raises; "soft_overlay_wins" drops the overlay (the heavier transition
    # stays).
    _collisions = [
        _o for _o in _resolved_overlays
        if _o["after_word_index"] in _transition_type_by_awi
    ]
    if _collisions:
        if _TIGHT_DECORATION_COLLISION == "strict":
            _c = _collisions[0]
            raise ValueError(
                f"after_word_index={_c['after_word_index']} has BOTH a transition "
                f"({_transition_type_by_awi[_c['after_word_index']]!r}) AND an overlay "
                f"({_c['type']!r}) — competing decorations for one cut. Pick one."
            )
        elif _TIGHT_DECORATION_COLLISION == "soft_overlay_wins":
            for _c in _collisions:
                _record_divergence(
                    "tight_decoration_collision",
                    {
                        "after_word_index": _c["after_word_index"],
                        "transition_out": _transition_type_by_awi[_c["after_word_index"]],
                        "tight_cut_overlay_dropped": _c["type"],
                    },
                    "drop_overlay_keep_transition",
                    reason="both_on_one_boundary",
                )
            _resolved_overlays = [
                _o for _o in _resolved_overlays
                if _o["after_word_index"] not in _transition_type_by_awi
            ]
        else:
            raise RuntimeError(
                f"_TIGHT_DECORATION_COLLISION = {_TIGHT_DECORATION_COLLISION!r} "
                f"is not a recognized mode. Valid: 'strict', 'soft_overlay_wins'."
            )

    # Stash the resolved overlays on the plan for the render emit, which projects
    # each after_word_index to an output frame via _projected_words. Boundary-
    # keyed and clip-agnostic — works for mid-clip boundaries with no split.
    edit_plan["_resolved_tight_cut_overlays"] = _resolved_overlays

    # caption_style, caption_keywords, caption_position_segments, text_overlays,
    # emphasis_moments, motion_graphics, audio_denoise, outro, aspect_ratio,
    # sound_effects — ALL required. No presence defaults. Gemini must emit every
    # field explicitly or the plan is rejected.
    for _req in ("audio_denoise", "outro", "aspect_ratio", "sound_effects"):
        if _req not in edit_plan:
            raise ValueError(
                f"edit_plan missing required field {_req!r}. Every plan MUST emit "
                f"audio_denoise (bool), outro ('none'|'fade_black'|'fade_white'), "
                f"aspect_ratio ('9:16'), and sound_effects (array, empty if none)."
            )
    if not isinstance(edit_plan.get("sound_effects"), list):
        raise ValueError("sound_effects must be an array (empty is fine)")
    if str(edit_plan.get("outro")) not in ("none", "fade_black", "fade_white"):
        raise ValueError(
            f"outro must be 'none'|'fade_black'|'fade_white', got {edit_plan.get('outro')!r}"
        )
    # aspect_ratio is informational — the pipeline always outputs 1080x1920
    # regardless of this field. Pydantic's Literal["9:16"] in EditPlan
    # constrains Gemini's structured-output normally, but Gemini occasionally
    # bypasses its own schema and emits e.g. "1080x1920" or "vertical".
    # Both convey the same intent (portrait 9:16). Normalize to "9:16" so
    # the persisted plan is canonical; don't hard-fail on a dead field.
    if str(edit_plan.get("aspect_ratio")) != "9:16":
        edit_plan["aspect_ratio"] = "9:16"

    # ── B-roll clips validation ───────────────────────────────────────────
    # Type/sanity checks only — no value clamps. Gemini owns every creative
    # decision (duration, count, placement). We only filter entries that
    # would crash the renderer or are physically impossible (negative time,
    # zero duration, NaN, past end of video, malformed JSON types).
    raw_broll = edit_plan.get("broll_clips") or []
    validated_broll = []
    _broll_dg_words = edit_plan.get("_deepgram_words") or []
    _broll_removed = edit_plan.get("_removed_word_indices") or set()
    for _br in raw_broll:
        if not isinstance(_br, dict):
            continue
        _br_kw = str(_br.get("keyword") or "").strip()
        if not _br_kw:
            continue
        # Word-index timing — compute exact start/end from KEPT Deepgram words.
        # Gemini may select a range that includes removed words. We find the
        # first kept word for the start and last kept word for the end so the
        # timestamps are guaranteed to exist in a clip.
        try:
            _sw = int(_br["start_word_index"])
            _ew = int(_br["end_word_index"])
        except (TypeError, ValueError, KeyError):
            continue
        if _sw < 0 or _ew < _sw or _sw >= len(_broll_dg_words):
            continue
        _ew = min(_ew, len(_broll_dg_words) - 1)
        # Find first KEPT word from start
        _sw_kept = _sw
        while _sw_kept <= _ew and _sw_kept in _broll_removed:
            _sw_kept += 1
        # Find last KEPT word from end
        _ew_kept = _ew
        while _ew_kept >= _sw_kept and _ew_kept in _broll_removed:
            _ew_kept -= 1
        if _sw_kept > _ew_kept:
            print(f"[broll] All words [{_sw}]-[{_ew}] removed — skipping '{_br_kw}'", flush=True)
            continue
        _br_ts = float(_broll_dg_words[_sw_kept].get("start") or 0)
        _br_end = float(_broll_dg_words[_ew_kept].get("end") or 0)
        # SOURCE-TIME span between the two words — INCLUDES any
        # mechanically-removed silence/filler. Computed but no longer
        # surfaced as the recipe `duration` field, because downstream
        # consumers (Pexels fetch filter, recipe log, debugging) all
        # want OUTPUT-time speech duration, not raw source span.
        _src_span = _br_end - _br_ts
        if _src_span <= 0:
            continue

        # OUTPUT-time SPEECH duration of just the kept words in the
        # range. Equals sum of each kept word's natural duration; ignores
        # inter-word silences (those vanish in mechanical removal anyway).
        # For 5 consecutive kept words at normal speech, ~2-3s — which
        # is what a 5-word cutaway should actually be on screen.
        _speech_dur = 0.0
        for _wi in range(_sw_kept, _ew_kept + 1):
            if _wi in _broll_removed:
                continue
            _w = _broll_dg_words[_wi]
            _ws = float(_w.get("start") or 0)
            _we = float(_w.get("end") or 0)
            if _we > _ws:
                _speech_dur += (_we - _ws)
        if _speech_dur <= 0:
            # Defensive — kept-word filter should leave at least one
            # word with positive duration. Skip the entry rather than
            # ship an obviously-broken zero-duration cutaway.
            continue

        # The recipe `duration` field now carries OUTPUT-time speech
        # duration. Downstream Pexels fetch sizing (handler.py:~15075)
        # gets a sensible request length (~2-3s for a 5-word phrase, NOT
        # the inflated source span). Render-time bounding uses the
        # output-projected word span via _pw_by_idx, unchanged.
        if not (math.isfinite(_br_ts) and math.isfinite(_speech_dur)):
            continue
        if _br_ts < 0 or _speech_dur <= 0:
            continue
        if video_duration > 0 and _br_ts >= video_duration:
            continue

        # Emit the divergence whenever source-span and output-speech
        # diverge by > 2x — that's the misleading-recipe symptom the
        # user reported and would have made invisible without this log.
        if _src_span > _speech_dur * 2.0:
            _record_divergence(
                "broll",
                {
                    "keyword": _br_kw,
                    "start_word_src": _sw_kept,
                    "end_word_src": _ew_kept,
                    "src_span_s": round(_src_span, 3),
                },
                "duration_recomputed_to_speech",
                final={"duration_s": round(_speech_dur, 3)},
                reason="src_span_inflated_by_mechanical_removals_between_words",
            )

        print(
            f"[broll] Word-index timing: [{_sw_kept}]-[{_ew_kept}] → "
            f"{_br_ts:.3f}s+{_speech_dur:.2f}s speech "
            f"(src span {_src_span:.2f}s)",
            flush=True,
        )
        validated_broll.append({
            "keyword": _br_kw,
            "timestamp": _br_ts,
            "duration": _speech_dur,
            "reason": str(_br.get("reason") or "").strip(),
            "_start_word_kept": _sw_kept,
            "_end_word_kept": _ew_kept,
        })
    edit_plan["broll_clips"] = validated_broll
    if validated_broll:
        print(f"[broll] Gemini requested {len(validated_broll)} B-roll clip(s)", flush=True)
        for _vb in validated_broll:
            _r = _vb.get("reason") or "(no reason given)"
            print(f"[broll]   → '{_vb['keyword']}' @ {_vb['timestamp']:.2f}s for {_vb['duration']:.2f}s — {_r}", flush=True)

    # ── Strict validation of new schema (no defaults, no repair) ───────────
    # The philosophy: Gemini emits a complete, valid plan. Everything below
    # raises on error — we do not substitute defaults or silently drop entries.

    _valid_caption_styles = {
        "PaperII",
        "Prime", "TypewriterReveal", "CinematicLetterpress", "Cove",
        "EditorialPop", "Illuminate", "Lumen",
        "Passage", "Pulse", "Quintessence", "Serif",
        "none",  # user opted out — see renderer for skip logic
    }
    _valid_zoom_types = {
        "SmoothPush", "SnapReframe", "FocusWindow", "StepZoom", "LetterboxPush",
        "StageZoom", "DepthPull",
    }
    _valid_mg_types = {
        "AnnotationArrow", "ChatThread",
        "Notification", "ProgressBar", "QuoteCard", "RecordingFrame",
        "StatCard", "StickyNotes", "Toggle",
        "TweetBubble", "InstagramComment", "IMessageBubble", "TikTokComment",
    }
    # Motion graphics use semantic safe-zone anchors that map to the MG pack's
    # MGAnchor vocabulary (top/center/bottom/left/right) via SEMANTIC_TO_MG_ANCHOR
    # at render time. Face-relative anchors are NOT valid for motion graphics —
    # the pack components don't accept a face prop, and their own resolveMGPosition
    # operates against the full canvas, so face-relative anchoring has no honest
    # render path. Use absolute safe zones only.
    _valid_semantic_anchors = {
        "upper_third_safe", "center", "lower_third_safe", "left_safe", "right_safe",
    }
    _valid_text_overlay_variants = {
        "sticky_note", "quote_card", "caption_match",
    }

    # caption_style — must be exactly one of the 21 valid styles
    _cs_raw = str(edit_plan.get("caption_style") or "").strip()
    if _cs_raw not in _valid_caption_styles:
        raise ValueError(
            f"Invalid caption_style: {_cs_raw!r}. Must be one of {sorted(_valid_caption_styles)}"
        )
    edit_plan["caption_style"] = _cs_raw

    # caption_keywords — required array of strings
    _ck_raw = edit_plan.get("caption_keywords")
    if not isinstance(_ck_raw, list):
        raise ValueError(f"caption_keywords must be an array, got {type(_ck_raw).__name__}")
    edit_plan["caption_keywords"] = [str(k).strip().lower() for k in _ck_raw if str(k).strip()]

    # caption_position_segments — SYNTHESIZED by the derivation pass above
    # from Gemini's caption_position_changes (word-index-based). Every
    # boundary is by construction a real word start timestamp; no exact-match
    # validation needed because mismatch is architecturally impossible.
    _cps = edit_plan.get("caption_position_segments") or []
    if _cps:
        print(
            f"[caption-segments] {len(_cps)} segment(s) synthesized from changes: "
            + ", ".join(f"[{s['from_seconds']:.2f}-{s['to_seconds']:.2f}]={s['position']}" for s in _cps),
            flush=True,
        )

    # color_effect was removed from the pipeline. There's no place a global
    # color grade fits without reintroducing the full-canvas mixBlendMode paint
    # cost that drove the 140s renders. Keep the field forced-null so any stale
    # callers don't break.
    edit_plan["color_effect"] = None

    # motion_graphics — array. Each entry validated strictly.
    # motion_graphics — word-anchored (start_word_index + end_word_index, with
    # optional duration_seconds override for fixed-duration pins). Python
    # derives the output-time window from the kept-word timestamps. Gemini
    # CANNOT emit a time that doesn't map to a real spoken moment.
    raw_mg = edit_plan.get("motion_graphics")
    if raw_mg is None:
        raw_mg = []
    if not isinstance(raw_mg, list):
        raise ValueError("motion_graphics must be an array")
    # Build kept-word set for the anchor-on-kept-word check below. This check
    # is belt-and-suspenders: re-indexing + index translation in the main-call
    # flow guarantees every emitted anchor lands on a kept word. Retained as
    # a regression guard in case a future refactor accidentally loosens that
    # invariant.
    _mg_kept_set = (
        set(range(len(_dg_words))) - set(_removed_word_indices or set())
    )
    validated_mg = []
    for _i, _mg in enumerate(raw_mg):
        if not isinstance(_mg, dict):
            raise ValueError(f"motion_graphics[{_i}] must be an object")
        _mg_type = str(_mg.get("type") or "").strip()
        if _mg_type not in _valid_mg_types:
            raise ValueError(
                f"motion_graphics[{_i}].type must be one of {sorted(_valid_mg_types)}, got {_mg_type!r}"
            )
        try:
            _sw = int(_mg["start_word_index"])
            _ew = int(_mg["end_word_index"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f"motion_graphics[{_i}] needs integer start_word_index and end_word_index"
            )
        if _sw < 0 or _sw >= len(_dg_words):
            raise ValueError(
                f"motion_graphics[{_i}].start_word_index={_sw} out of range "
                f"[0, {len(_dg_words)-1}]"
            )
        if _ew < 0 or _ew >= len(_dg_words):
            raise ValueError(
                f"motion_graphics[{_i}].end_word_index={_ew} out of range "
                f"[0, {len(_dg_words)-1}]"
            )
        if _ew < _sw:
            raise ValueError(
                f"motion_graphics[{_i}].end_word_index ({_ew}) must be >= "
                f"start_word_index ({_sw})"
            )
        if _sw not in _mg_kept_set:
            _wt = str(_dg_words[_sw].get("punctuated_word") or _dg_words[_sw].get("word") or "").strip()
            print(
                f"[generate-edit] DROP motion_graphics '{_mg_type}' [{_i}]: "
                f"start_word_index={_sw} ({_wt!r}) targets a REMOVED word. "
                f"Render continues without this motion graphic.",
                flush=True,
            )
            continue
        if _ew not in _mg_kept_set:
            _wt = str(_dg_words[_ew].get("punctuated_word") or _dg_words[_ew].get("word") or "").strip()
            print(
                f"[generate-edit] DROP motion_graphics '{_mg_type}' [{_i}]: "
                f"end_word_index={_ew} ({_wt!r}) targets a REMOVED word. "
                f"Render continues without this motion graphic.",
                flush=True,
            )
            continue
        _anchor = str(_mg.get("anchor") or "").strip()
        if _anchor not in _valid_semantic_anchors:
            raise ValueError(
                f"motion_graphics[{_i}].anchor must be a semantic zone "
                f"{sorted(_valid_semantic_anchors)}, got {_anchor!r}"
            )

        _props = _mg.get("props")
        if not isinstance(_props, dict):
            raise ValueError(f"motion_graphics[{_i}].props must be an object")
        # Optional duration override; validator only enforces range.
        _dur_override = _mg.get("duration_seconds")
        if _dur_override is not None:
            try:
                _dur_override = float(_dur_override)
            except (TypeError, ValueError):
                raise ValueError(
                    f"motion_graphics[{_i}].duration_seconds must be a number if present"
                )
            if _dur_override < 0.3 or _dur_override > 20.0:
                raise ValueError(
                    f"motion_graphics[{_i}].duration_seconds={_dur_override} "
                    f"outside [0.3, 20.0]"
                )
        # Derive the source-time window from the anchor words. No rounding:
        # clip source ranges in build_clips_from_words are stored as raw
        # floats from word._start / word._end, so anchor source times
        # MUST be raw too. Rounding here to 3 decimals lost a sub-millisecond
        # difference between this stored value and the clip boundary,
        # causing project_source_time_to_output to return None at render
        # time — same precision bug class as the emphasis-moment one.
        _sw_start = float(_dg_words[_sw].get("start") or 0)
        _ew_end = float(_dg_words[_ew].get("end") or 0)
        validated_mg.append({
            "type": _mg_type,
            "start_word_index": _sw,
            "end_word_index": _ew,
            # Source-time timestamps carried forward for render_multi_clip to
            # project through the output timeline (same pattern as everything
            # else that's word-anchored).
            "_source_start": _sw_start,
            "_source_end": _ew_end,
            "duration_seconds_override": _dur_override,
            "anchor": _anchor,
            "props": _props,
        })
    edit_plan["motion_graphics"] = validated_mg
    if validated_mg:
        print(f"[mg] Gemini requested {len(validated_mg)} motion graphic(s)", flush=True)

    # B-roll vs overlay (motion_graphic / text_overlay) deconfliction has
    # MOVED to render_multi_clip — see "Strict separation" block right after
    # the B-roll output projection. Doing it on actual output frame ranges
    # (instead of word indices here) catches MGs/text-overlays whose
    # duration_seconds extends past their anchor word and would otherwise
    # slip past a word-index check.

    # Defensive: in case any legacy upstream caller still hands us a
    # `speed_curve` field on the plan (it's no longer in the schema), drop
    # it silently. Pacing is now expressed exclusively via per-clip `speed`.
    edit_plan.pop("speed_curve", None)
    edit_plan.pop("_parsed_speed_curve", None)

    thumbnail_timestamp = None
    try:
        if edit_plan.get("thumbnail_timestamp") is not None:
            thumbnail_timestamp = max(0.0, float(edit_plan.get("thumbnail_timestamp")))
            if video_duration > 0:
                thumbnail_timestamp = min(thumbnail_timestamp, video_duration)
    except Exception:
        thumbnail_timestamp = None
    edit_plan["thumbnail_timestamp"] = thumbnail_timestamp

    # Defensive: drop any legacy hook_clip field a stale caller might pass.
    # Auto-hook (climax replay at start) was removed because it duplicates
    # source content in the timeline — no production NLE does this. Cold-
    # open / strongest-moment range cuts were also removed: the cuts prompt
    # now requires chronological order. The opening of the kept transcript
    # is whatever survives standard filler trimming at word [0].
    edit_plan.pop("hook_clip", None)
    edit_plan["cuts"] = list(validated_cuts)

    # ── Parse emphasis moments — strict, with explicit visual-layer bindings ─
    raw_emphasis = edit_plan.get("emphasis_moments")
    if raw_emphasis is None:
        raw_emphasis = []
    if not isinstance(raw_emphasis, list):
        raise ValueError("emphasis_moments must be an array")
    _valid_em_types = {"punchline", "statement", "question", "reaction", "transition", "revelation"}
    emphasis_moments = []
    # Pre-compute the kept-word set for the anchor-on-kept-word checks below
    # (emphasis, text_overlays, transitions, sfx, broll). These checks are
    # belt-and-suspenders: re-indexing + index translation in the main-call
    # flow guarantees every emitted anchor lands on a kept word. Retained
    # as a regression guard against future refactors.
    _kept_word_indices = (
        set(range(len(_dg_words))) - set(_removed_word_indices or set())
    )
    for _ei, em in enumerate(raw_emphasis):
        if not isinstance(em, dict):
            raise ValueError(f"emphasis_moments[{_ei}] must be an object")
        _wi_raw = em.get("word_indices")
        if not isinstance(_wi_raw, list) or not _wi_raw:
            raise ValueError(f"emphasis_moments[{_ei}].word_indices must be a non-empty array")
        _wis = [int(i) for i in _wi_raw if isinstance(i, (int, float))]
        if not _wis:
            raise ValueError(f"emphasis_moments[{_ei}].word_indices contained no integers")
        # Every word_indices entry MUST be a word that survives remove_words.
        # If any anchor word was removed, drop the entire emphasis_moment and
        # continue — render proceeds without this single moment rather than
        # hard-failing the whole plan.
        _drop_em = False
        for _k, _wi_val in enumerate(_wis):
            if _wi_val < 0 or _wi_val >= len(_dg_words):
                raise ValueError(
                    f"emphasis_moments[{_ei}].word_indices[{_k}]={_wi_val} is out "
                    f"of range [0, {len(_dg_words)-1}]."
                )
            if _wi_val not in _kept_word_indices:
                _w = _dg_words[_wi_val]
                _wt = str(_w.get("punctuated_word") or _w.get("word") or "").strip()
                print(
                    f"[generate-edit] DROP emphasis_moment [{_ei}]: "
                    f"word_indices[{_k}]={_wi_val} ({_wt!r}) targets a "
                    f"REMOVED word. Render continues without this emphasis.",
                    flush=True,
                )
                _drop_em = True
                break
        if _drop_em:
            continue
        # Derive t from word_indices[0].start — Gemini no longer emits `t`
        # (schema-level constraint from v34: the two could disagree so we
        # removed the degree of freedom). Because word_indices[0] is a kept
        # word, the derived t is guaranteed to land inside a kept clip's
        # source range.
        #
        # No rounding: clip source ranges are built from these same word
        # timestamps without rounding, so the anchor t will hit the clip
        # boundary exactly. Any rounding here only loses precision and
        # introduces boundary mismatches like the v34→df1b62e bug where
        # round(12.871, 2) = 12.87 fell below clip.source_start = 12.871.
        _anchor_word = _dg_words[_wis[0]]
        t = float(_anchor_word.get("start") or 0)
        if t < 0 or (video_duration > 0 and t > video_duration + 0.5):
            raise ValueError(
                f"emphasis_moments[{_ei}] derived t={t:.3f}s (from word_indices[0]="
                f"{_wis[0]}) is outside video duration [0, {video_duration:.3f}]."
            )
        intensity = str(em.get("intensity") or "").lower()
        if intensity not in ("high", "medium"):
            raise ValueError(f"emphasis_moments[{_ei}].intensity must be 'high'|'medium'")
        em_type = str(em.get("type") or "").lower()
        if em_type not in _valid_em_types:
            raise ValueError(
                f"emphasis_moments[{_ei}].type must be one of {sorted(_valid_em_types)}"
            )
        _em_duration = float(em.get("duration") or 2.0)
        # Visual layer bindings — both fields are required (value or null).
        if "zoom_effect" not in em:
            raise ValueError(f"emphasis_moments[{_ei}] missing zoom_effect (emit null if no zoom)")
        if "motion_graphic" not in em:
            raise ValueError(f"emphasis_moments[{_ei}] missing motion_graphic (emit null if none)")
        _ze_raw = em.get("zoom_effect")
        _ze_out = None
        if _ze_raw is not None:
            if not isinstance(_ze_raw, dict):
                raise ValueError(f"emphasis_moments[{_ei}].zoom_effect must be object or null")
            _zt = str(_ze_raw.get("type") or "").strip()
            if _zt not in _valid_zoom_types:
                raise ValueError(
                    f"emphasis_moments[{_ei}].zoom_effect.type must be one of "
                    f"{sorted(_valid_zoom_types)}, got {_zt!r}"
                )
            _raw_events = _ze_raw.get("events") or []
            # Fill in natural durationMs and scale per zoom type when Gemini
            # omits them. This locks the look of each zoom to its designed
            # motion shape regardless of what Gemini chose for the moment —
            # picking SmoothPush gets a 1200ms cubic ease at 1.22 unless
            # explicitly overridden. Gemini's job is picking the right TYPE
            # for the beat; the renderer handles the look.
            _natural_dur = ZOOM_NATURAL_DURATION_MS.get(_zt, 1200)
            _natural_scale = ZOOM_NATURAL_SCALE.get(_zt, 1.22)
            # Per-event PERCEPTUAL PEAK back-timing. Override Gemini's
            # startMs so the visible peak lands on the anchor word, not
            # the ramp-out endpoint. See ZOOM_PEAK_REACH_MS at the top
            # of this file for the rationale and measured values.
            _peak_reach_ms = ZOOM_PEAK_REACH_MS.get(_zt, 0)
            _word_start_ms = int(round(t * 1000.0))
            _new_start_ms_canonical = _word_start_ms - _peak_reach_ms
            # Find the owning clip's source range to enforce the
            # "startMs must live inside the owning clip's source range"
            # hard constraint. The render-time projection already has
            # its own clip-window clamp (handler.py:~10744), but we
            # also clamp here so the recorded plan reflects the
            # intended source-time and the divergence log is precise.
            _owning_clip_for_em = None
            for _ci_em, _clip_em in enumerate(validated_cuts):
                _cs_em = float(_clip_em.get("source_start") or 0.0)
                _ce_em = float(_clip_em.get("source_end") or 0.0)
                if _cs_em <= t <= _ce_em:
                    _owning_clip_for_em = (_ci_em, _cs_em, _ce_em)
                    break
            _filled_events = []
            for _ev_raw in _raw_events:
                if not isinstance(_ev_raw, dict):
                    continue
                _ev = dict(_ev_raw)
                _gemini_start_ms = _ev.get("startMs")
                if _ev.get("durationMs") is None:
                    _ev["durationMs"] = _natural_dur
                if _ev.get("scale") is None:
                    _ev["scale"] = _natural_scale
                # Override startMs to put the perceptual peak on the
                # anchor word. Clamp to the owning clip's source_start
                # in ms (frame-0 blip protection). If no owning clip
                # could be matched (rare — emphasis t outside all
                # clips, which the existing "CLEAR emphasis_moments
                # zoom_effect" pass at ~handler.py:7000 will catch
                # and clear anyway), the canonical correction stands.
                _corrected_start_ms = _new_start_ms_canonical
                _clamp_reason = None
                if _owning_clip_for_em is not None:
                    _, _cs_em, _ce_em = _owning_clip_for_em
                    _clip_start_ms = int(round(_cs_em * 1000.0))
                    if _corrected_start_ms < _clip_start_ms:
                        _corrected_start_ms = _clip_start_ms
                        _clamp_reason = "clamped_to_clip_source_start"
                _ev["startMs"] = _corrected_start_ms
                _record_divergence(
                    "zoom_startMs_corrected",
                    {
                        "type": _zt,
                        "old_startMs": (
                            int(_gemini_start_ms)
                            if isinstance(_gemini_start_ms, (int, float))
                            else None
                        ),
                        "word_start_ms": _word_start_ms,
                        "peak_reach_ms": _peak_reach_ms,
                    },
                    "corrected" if _clamp_reason is None else _clamp_reason,
                    final={"new_startMs": _corrected_start_ms},
                    reason=(_clamp_reason or "align_perceptual_peak_to_word"),
                )
                # ── Shot-change boundary clamp ────────────────────────────
                # A zoom window must not straddle a tight SHOT-CHANGE boundary:
                # the footage cuts to a new shot mid-window and the held/moving
                # zoom carries the old shot's framing (+ the frozen face-lock
                # origin) into the new shot — the StepZoom "staircase", a framing
                # pop on the moving types. End the window at or before the first
                # shot-change boundary strictly inside it. _shot_src_set holds
                # SHOT-CHANGE tights as SOURCE WORD INDICES (NOT times); the cut
                # time is that word's `.end` (s)×1000 = source ms, matching
                # startMs (source ms). dead_air tights are excluded — they don't
                # cut footage.
                _zc_start = _ev.get("startMs")
                _zc_dur = _ev.get("durationMs")
                if (
                    isinstance(_zc_start, (int, float))
                    and isinstance(_zc_dur, (int, float))
                    and _zc_dur > 0
                    and _shot_src_set
                ):
                    _zc_end = _zc_start + _zc_dur
                    _cut_ms = None
                    for _tsi in _shot_src_set:
                        if not (0 <= _tsi < len(_dg_words)):
                            continue
                        _tms = float(_dg_words[_tsi].get("end") or 0.0) * 1000.0
                        if _zc_start < _tms < _zc_end:
                            _cut_ms = _tms if _cut_ms is None else min(_cut_ms, _tms)
                    if _cut_ms is not None:
                        _clamped_dur = int(round(_cut_ms - _zc_start))
                        # Floor: never clamp to a stub. 200ms ≈ 12 frames @ 60fps,
                        # ≥ SnapReframe's ~171ms spring settle, so a clamped zoom
                        # still completes its move. Below the floor we leave the
                        # window UNCHANGED (rare — the straddle persists for that
                        # one event rather than rendering a stub; safest default).
                        _ZOOM_CLAMP_FLOOR_MS = 200
                        if _ZOOM_CLAMP_FLOOR_MS <= _clamped_dur < _zc_dur:
                            _record_divergence(
                                "zoom_window",
                                {
                                    "type": _zt,
                                    "startMs": int(_zc_start),
                                    "durationMs": int(_zc_dur),
                                    "shot_change_ms": int(round(_cut_ms)),
                                },
                                "clamp_to_shot_change",
                                final={"durationMs": _clamped_dur},
                                reason="zoom_window_straddled_tight_shot_change",
                            )
                            print(
                                f"[zoom-clamp] {_zt} window "
                                f"[{int(_zc_start)},{int(_zc_end)}]ms straddles "
                                f"shot-change at {int(round(_cut_ms))}ms — "
                                f"durationMs {int(_zc_dur)}→{_clamped_dur} "
                                f"(release on shot A)",
                                flush=True,
                            )
                            _ev["durationMs"] = _clamped_dur
                _filled_events.append(_ev)
            _ze_out = {"type": _zt, "events": _filled_events}
            for _ek in ("firstStage", "secondStage", "windowScale", "borderWidth",
                        "borderColor", "bgScale", "edgeBlur", "frameLines", "maxBarHeight"):
                if _ek in _ze_raw:
                    _ze_out[_ek] = _ze_raw[_ek]
        _mg_raw = em.get("motion_graphic")
        _mg_out = None
        if _mg_raw is not None:
            if not isinstance(_mg_raw, dict):
                raise ValueError(f"emphasis_moments[{_ei}].motion_graphic must be object or null")
            _mgt = str(_mg_raw.get("type") or "").strip()
            if _mgt not in _valid_mg_types:
                raise ValueError(
                    f"emphasis_moments[{_ei}].motion_graphic.type must be one of "
                    f"{sorted(_valid_mg_types)}, got {_mgt!r}"
                )
            _anc = str(_mg_raw.get("anchor") or "").strip()
            if _anc not in _valid_semantic_anchors:
                raise ValueError(
                    f"emphasis_moments[{_ei}].motion_graphic.anchor must be one of "
                    f"{sorted(_valid_semantic_anchors)}, got {_anc!r}"
                )
            _mg_props = _mg_raw.get("props")
            if not isinstance(_mg_props, dict):
                raise ValueError(f"emphasis_moments[{_ei}].motion_graphic.props must be object")
            _mg_out = {"type": _mgt, "anchor": _anc, "props": _mg_props}
        _em_word_parts = []
        for idx in _wis:
            if _dg_words and 0 <= idx < len(_dg_words):
                w = str(_dg_words[idx].get("punctuated_word") or _dg_words[idx].get("word") or "").strip()
                if w:
                    _em_word_parts.append(w)
        _em_word = " ".join(_em_word_parts)
        emphasis_moments.append({
            "t": t,
            "word_indices": _wis,
            "type": em_type,
            "intensity": intensity,
            "word": _em_word,
            "duration": _em_duration,
            "zoom_effect": _ze_out,
            "motion_graphic": _mg_out,
        })
    emphasis_moments.sort(key=lambda x: x["t"])

    # ── Payoff-tail protection + min zoom spacing ─────────────────────────
    # Mirrors the transition-spacing safeguards shipped in commit a95cfb2.
    # Two passes applied to emphasis_moments AFTER sort-by-t and BEFORE the
    # zoom-type clip-split pre-pass:
    #
    #   PASS 1 — Payoff-tail protection: drop any emphasis whose first zoom
    #     event starts within [payoff_zoom_start, payoff_zoom_end + 1.5s].
    #     The payoff is the final committed move; nothing zooms on its
    #     heels through the close. The close still gets captions/SFX/MGs,
    #     just not a competing zoom.
    #
    #   PASS 2 — Minimum spacing: drop any emphasis whose zoom peak is
    #     within _MIN_ZOOM_SPACING_S of a previously-kept peak. Priority:
    #     payoff (3) > mid_peak (2) > anything else (1). Lower priority
    #     drops; ties go to the EARLIER emphasis (first emitted wins).
    #
    # Both passes log via _record_divergence so grep [divergence]
    # component=emphasis surfaces every drop with the reason.
    _MIN_ZOOM_SPACING_S = 2.0
    _PAYOFF_TAIL_PROTECTION_S = 1.5

    _arc_segments_for_priority = []
    if isinstance(_vp, dict):
        _arc_segments_for_priority = _vp.get("arc_segments") or []

    def _arc_position_at_word(word_index):
        """Look up arc position (hook/build/mid_peak/payoff/breather/close)
        for a given src word_index. Returns '' if no segment matches."""
        if not isinstance(word_index, int):
            return ""
        for _seg in _arc_segments_for_priority:
            if not isinstance(_seg, dict):
                continue
            try:
                _ss = int(_seg.get("start_word_index"))
                _se = int(_seg.get("end_word_index"))
            except (TypeError, ValueError):
                continue
            if _ss <= word_index <= _se:
                return str(_seg.get("position") or "")
        return ""

    _ZOOM_PRIORITY = {"payoff": 3, "mid_peak": 2}

    def _emphasis_priority(em):
        _wis = em.get("word_indices") or []
        _wi0 = _wis[0] if _wis else None
        _pos = _arc_position_at_word(_wi0)
        return _ZOOM_PRIORITY.get(_pos, 1)

    def _first_event_window_s(em):
        """Returns (start_s, end_s, peak_s) for the emphasis's first zoom
        event, or None if no zoom event exists. All times in source-seconds.
        Peak time uses ZOOM_PEAK_REACH_MS per type — same source of truth
        as the Fix B1 startMs correction (handler.py:~6900)."""
        _ze = em.get("zoom_effect")
        if not isinstance(_ze, dict):
            return None
        _events = _ze.get("events") or []
        if not _events or not isinstance(_events[0], dict):
            return None
        _ev = _events[0]
        try:
            _start_ms = float(_ev.get("startMs") or 0)
            _dur_ms = float(_ev.get("durationMs") or 0)
        except (TypeError, ValueError):
            return None
        _zoom_type = str(_ze.get("type") or "")
        _peak_ms = _start_ms + float(ZOOM_PEAK_REACH_MS.get(_zoom_type, 0))
        return (_start_ms / 1000.0, (_start_ms + _dur_ms) / 1000.0, _peak_ms / 1000.0)

    # PASS 1 — Payoff-tail protection.
    _payoff_wi = (
        _vp.get("payoff_word_index") if isinstance(_vp, dict) else None
    )
    _payoff_em = None
    _payoff_protected_window = None
    if isinstance(_payoff_wi, int):
        for _em_search in emphasis_moments:
            _em_wis = _em_search.get("word_indices") or []
            if _em_wis and _em_wis[0] == _payoff_wi:
                _payoff_em = _em_search
                _win = _first_event_window_s(_em_search)
                if _win is not None:
                    _payoff_protected_window = (
                        _win[0],
                        _win[1] + _PAYOFF_TAIL_PROTECTION_S,
                    )
                break

    _kept_after_payoff = []
    for _em in emphasis_moments:
        if _em is _payoff_em or _payoff_protected_window is None:
            _kept_after_payoff.append(_em)
            continue
        _win = _first_event_window_s(_em)
        if _win is None:
            _kept_after_payoff.append(_em)
            continue
        _start_s, _end_s, _peak_s = _win
        # Drop if the emphasis's zoom STARTS inside the protected window.
        # Half-open: an emphasis starting EXACTLY at payoff_zoom_end + 1.5s
        # is the close callback the prompt allows.
        if _payoff_protected_window[0] <= _start_s < _payoff_protected_window[1]:
            _wi0 = (_em.get("word_indices") or [None])[0]
            _zt = (_em.get("zoom_effect") or {}).get("type", "")
            print(
                f"[emphasis] DROP {_zt} on word {_wi0} "
                f"(zoom_start={_start_s:.2f}s) — falls inside payoff "
                f"tail-protection window "
                f"[{_payoff_protected_window[0]:.2f}..{_payoff_protected_window[1]:.2f}]s.",
                flush=True,
            )
            _record_divergence(
                "emphasis",
                {
                    "type": _em.get("type", ""),
                    "zoom_type": _zt,
                    "word_index": _wi0,
                    "zoom_start_s": round(_start_s, 3),
                    "payoff_window_s": [
                        round(_payoff_protected_window[0], 3),
                        round(_payoff_protected_window[1], 3),
                    ],
                    "payoff_word_index": _payoff_wi,
                },
                "drop_post_payoff",
                final=None,
                reason="protects_payoff_commitment",
            )
            continue
        _kept_after_payoff.append(_em)

    # PASS 2 — Minimum spacing between zoom peaks.
    _kept_after_spacing = []
    for _em in _kept_after_payoff:
        _win = _first_event_window_s(_em)
        if _win is None:
            _kept_after_spacing.append(_em)
            continue
        _start_s, _end_s, _peak_s = _win
        _prio = _emphasis_priority(_em)

        if _kept_after_spacing:
            # Find the most recently kept emphasis that HAS a zoom event
            # (skip text-only emphases that have no peak).
            _last_idx = None
            for _i in range(len(_kept_after_spacing) - 1, -1, -1):
                _last_win = _first_event_window_s(_kept_after_spacing[_i])
                if _last_win is not None:
                    _last_idx = _i
                    break
            if _last_idx is not None:
                _last_em = _kept_after_spacing[_last_idx]
                _last_win = _first_event_window_s(_last_em)
                _last_peak_s = _last_win[2]
                _last_prio = _emphasis_priority(_last_em)
                _gap = abs(_peak_s - _last_peak_s)
                if _gap < _MIN_ZOOM_SPACING_S:
                    if _prio > _last_prio:
                        # Current outranks previous — drop previous, keep current.
                        _wi0_prev = (_last_em.get("word_indices") or [None])[0]
                        _zt_prev = (_last_em.get("zoom_effect") or {}).get("type", "")
                        print(
                            f"[emphasis] DROP {_zt_prev} on word {_wi0_prev} "
                            f"(peak={_last_peak_s:.2f}s, prio={_last_prio}) — "
                            f"within {_MIN_ZOOM_SPACING_S}s of higher-priority "
                            f"peak at {_peak_s:.2f}s (prio={_prio}).",
                            flush=True,
                        )
                        _record_divergence(
                            "emphasis",
                            {
                                "type": _last_em.get("type", ""),
                                "zoom_type": _zt_prev,
                                "word_index": _wi0_prev,
                                "peak_s": round(_last_peak_s, 3),
                                "priority": _last_prio,
                                "winning_peak_s": round(_peak_s, 3),
                                "winning_priority": _prio,
                                "gap_s": round(_gap, 3),
                            },
                            "drop_too_close",
                            final=None,
                            reason="min_zoom_spacing",
                        )
                        del _kept_after_spacing[_last_idx]
                        _kept_after_spacing.append(_em)
                    else:
                        # Current is lower-or-equal priority — current drops
                        # (ties go to the earlier kept emphasis).
                        _wi0 = (_em.get("word_indices") or [None])[0]
                        _zt = (_em.get("zoom_effect") or {}).get("type", "")
                        print(
                            f"[emphasis] DROP {_zt} on word {_wi0} "
                            f"(peak={_peak_s:.2f}s, prio={_prio}) — "
                            f"within {_MIN_ZOOM_SPACING_S}s of kept peak at "
                            f"{_last_peak_s:.2f}s (prio={_last_prio}).",
                            flush=True,
                        )
                        _record_divergence(
                            "emphasis",
                            {
                                "type": _em.get("type", ""),
                                "zoom_type": _zt,
                                "word_index": _wi0,
                                "peak_s": round(_peak_s, 3),
                                "priority": _prio,
                                "kept_peak_s": round(_last_peak_s, 3),
                                "kept_priority": _last_prio,
                                "gap_s": round(_gap, 3),
                            },
                            "drop_too_close",
                            final=None,
                            reason="min_zoom_spacing",
                        )
                    continue
        _kept_after_spacing.append(_em)

    if len(_kept_after_spacing) != len(emphasis_moments):
        print(
            f"[emphasis] safeguards: {len(emphasis_moments)} → "
            f"{len(_kept_after_spacing)} (payoff-tail + min spacing drops)",
            flush=True,
        )
        emphasis_moments = _kept_after_spacing

    # ── PRE-PASS: split clips at zoom-type boundaries ─────────────────────
    # Multiple emphasis_moments can target the same clip; the Remotion
    # ClipRenderer at src/remotion/src/PromptlyRender.tsx:89-100 picks ONE
    # zoom component per clip by `zoomEffect.type`. To preserve Gemini's
    # per-event zoom variety (instead of coercing every event on a clip
    # to one type), split the clip at the midpoint between adjacent
    # emphases that differ in zoom type. Each resulting sub-clip then
    # naturally has emphases of a single type — the existing grouping
    # loop below sees one type per clip and no coercion is needed.
    #
    # Reuses the validated-cuts split pattern from the post-Gemini shot-
    # split block above. Internal sub-clip boundaries get
    # transition_out="none" (hard cut between same-take sub-clips).
    _zoom_type_split_times: List[float] = []
    _zoom_em_by_clip: Dict[int, List[int]] = {}
    for _ei, em in enumerate(emphasis_moments):
        if not em.get("zoom_effect"):
            continue
        for _ci, _clip in enumerate(validated_cuts):
            _cs = float(_clip["source_start"])
            _ce = float(_clip["source_end"])
            if _cs <= em["t"] <= _ce:
                _zoom_em_by_clip.setdefault(_ci, []).append(_ei)
                break

    for _ci, _ei_list in _zoom_em_by_clip.items():
        _ei_sorted = sorted(_ei_list, key=lambda i: emphasis_moments[i]["t"])
        _types_in_order = [
            str(emphasis_moments[i]["zoom_effect"]["type"]) for i in _ei_sorted
        ]
        if len(set(_types_in_order)) <= 1:
            continue  # single type on this clip — no split needed
        for _k in range(1, len(_ei_sorted)):
            if _types_in_order[_k] == _types_in_order[_k - 1]:
                continue
            _t_prev = float(emphasis_moments[_ei_sorted[_k - 1]]["t"])
            _t_curr = float(emphasis_moments[_ei_sorted[_k]]["t"])
            if _t_curr <= _t_prev:
                continue
            _split_t = (_t_prev + _t_curr) / 2.0
            _zoom_type_split_times.append(_split_t)
            _record_divergence(
                "zoom_type_split",
                {
                    "owning_clip_idx": _ci,
                    "type_a": _types_in_order[_k - 1],
                    "type_b": _types_in_order[_k],
                    "em_idx_a": _ei_sorted[_k - 1],
                    "em_idx_b": _ei_sorted[_k],
                    "split_at_source_s": round(_split_t, 3),
                },
                "clip_split_to_preserve_zoom_variety",
                reason="adjacent_emphases_on_same_clip_have_different_zoom_types",
            )

    if _zoom_type_split_times:
        _split_times_sorted = sorted(set(_zoom_type_split_times))
        _new_cuts = []
        _total_splits = 0
        for _clip in validated_cuts:
            _cs = float(_clip["source_start"])
            _ce = float(_clip["source_end"])
            _internal = [
                _st for _st in _split_times_sorted
                if _cs + 0.05 < _st < _ce - 0.05
            ]
            if not _internal:
                _new_cuts.append(_clip)
                continue
            _boundaries = [_cs] + _internal + [_ce]
            for _bi in range(len(_boundaries) - 1):
                _sub_start = _boundaries[_bi]
                _sub_end = _boundaries[_bi + 1]
                if _sub_end - _sub_start <= 0:
                    continue
                _sub = {**_clip, "source_start": _sub_start, "source_end": _sub_end}
                # Internal sub-clip boundary → no transition (hard cut
                # between same-take takes; matches shot-split convention).
                if _bi != len(_boundaries) - 2:
                    _sub["transition_out"] = "none"
                _new_cuts.append(_sub)
            _total_splits += len(_internal)
        if _total_splits > 0:
            print(
                f"[zoom-type-split] Validated cuts: {len(validated_cuts)} → "
                f"{len(_new_cuts)} clips ({_total_splits} zoom-variety split(s) "
                f"applied)",
                flush=True,
            )
            validated_cuts = _new_cuts

    # Multiple emphasis_moments can target the same clip — each gets a zoom
    # EVENT, all merged into the clip's single zoomEffect spec. The spec carries
    # one `type` (SmoothPush / StepZoom / etc.) but can hold multiple `events`
    # spaced across the clip's render window. After the zoom-type-split pass
    # above, each sub-clip naturally has emphases of a single type, so the
    # coercion path is effectively dead on the happy path. It is preserved
    # here as a defensive fallback in case the split fails to apply (e.g.,
    # an emphasis whose t falls in the 0.05s edge zone of a clip boundary).
    # When coercion DOES fire, _record_divergence makes it visible.
    _INTENSITY_RANK = {"high": 3, "medium": 2, "low": 1}
    _clip_zoom_emphasis: dict = {}  # clip_idx -> list of emphasis_moment indices
    for _ei, em in enumerate(emphasis_moments):
        if not em["zoom_effect"]:
            continue
        _owning_clip = None
        for _ci, _clip in enumerate(validated_cuts):
            _cs = float(_clip["source_start"])
            _ce = float(_clip["source_end"])
            if _cs <= em["t"] <= _ce:
                _owning_clip = _ci
                break
        if _owning_clip is None:
            print(
                f"[generate-edit] CLEAR emphasis_moments[{_ei}].zoom_effect: "
                f"t={em['t']:.2f}s falls outside every validated clip. "
                f"Render continues with the emphasis but no zoom.",
                flush=True,
            )
            em["zoom_effect"] = None
            continue
        _clip_zoom_emphasis.setdefault(_owning_clip, []).append(_ei)

    for _clip_idx, _ei_list in _clip_zoom_emphasis.items():
        # Pick the dominant emphasis on this clip: highest intensity, tiebreak
        # by lowest emphasis index (earliest moment in the video).
        _ei_sorted = sorted(
            _ei_list,
            key=lambda i: (-_INTENSITY_RANK.get(emphasis_moments[i]["intensity"], 0), i),
        )
        _dominant_ei = _ei_sorted[0]
        _dominant_zoom = emphasis_moments[_dominant_ei]["zoom_effect"]
        _dominant_type = _dominant_zoom["type"]

        # Collect events from every emphasis on this clip, in startMs order.
        _merged_events = []
        _coerced_types = []
        for _ei in _ei_list:
            _em_zoom = emphasis_moments[_ei]["zoom_effect"]
            if _em_zoom["type"] != _dominant_type:
                _coerced_types.append((_ei, _em_zoom["type"]))
            for _ev in (_em_zoom.get("events") or []):
                _merged_events.append(_ev)
        _merged_events.sort(key=lambda e: float(e.get("startMs") or 0))

        # Item C instrumentation (no behavior change): the StepZoom double-
        # step-out staircase only appears when ≥2 events render under ONE
        # StepZoom type with OVERLAPPING windows (or mixed scales) — StepZoom's
        # first-covering-event-wins then exposes a lower event's scale as an
        # intermediate on the way out. Both captured renders had a ~3s GAP, so
        # the bug never reproduced. Log loudly when an overlap / mixed-scale
        # merge DOES happen so the next staircase render surfaces the exact
        # events (scale, startMs, durMs) the max-covering fix needs.
        if _dominant_type == "StepZoom" and len(_merged_events) > 1:
            _ev_sd = [
                (
                    float(_e.get("scale") or 0.0),
                    float(_e.get("startMs") or 0.0),
                    float(_e.get("durationMs") or 0.0),
                )
                for _e in _merged_events
            ]
            _zm_overlap = any(
                _ev_sd[_k + 1][1] < _ev_sd[_k][1] + _ev_sd[_k][2]
                for _k in range(len(_ev_sd) - 1)
            )
            _zm_mixed = len({round(_s, 3) for _s, _, _ in _ev_sd}) > 1
            if _zm_overlap or _zm_mixed:
                _zm_tags = " ".join(
                    _t for _t, _on in (("OVERLAP", _zm_overlap), ("MIXED_SCALE", _zm_mixed))
                    if _on
                )
                print(
                    f"[zoom-merge-overlap] StepZoom clip={_clip_idx} "
                    f"events={[(round(_s, 3), int(_st), int(_d)) for _s, _st, _d in _ev_sd]} "
                    f"{_zm_tags} detected — staircase arrangement (StepZoom "
                    f"first-covering renders an intermediate scale on step-out)",
                    flush=True,
                )

        # Carry over non-events / non-type fields from the dominant emphasis's
        # zoom_effect (firstStage, windowScale, borderColor, etc. — these are
        # type-specific config that only the dominant type knows what to do with).
        _merged_zoom = {
            "type": _dominant_type,
            "events": _merged_events,
            **{
                k: v for k, v in _dominant_zoom.items()
                if k not in ("type", "events") and v is not None
            },
        }
        validated_cuts[_clip_idx]["_zoom_effect"] = _merged_zoom

        # Mirror the merged zoom back onto every contributing emphasis_moment
        # so the [emphasis] log line below reflects what actually renders.
        for _ei in _ei_list:
            emphasis_moments[_ei]["zoom_effect"] = _merged_zoom

        if len(_ei_list) > 1:
            if _coerced_types:
                _coerce_str = ", ".join(f"em[{_i}]={_t}" for _i, _t in _coerced_types)
                print(
                    f"[generate-edit] Clip {_clip_idx}: merged {len(_ei_list)} "
                    f"zoom emphasis moments into one zoomEffect "
                    f"(type={_dominant_type} from dominant em[{_dominant_ei}], "
                    f"coerced: {_coerce_str}).",
                    flush=True,
                )
                # If the zoom-type pre-split missed a transition (e.g., an
                # emphasis whose t fell in the edge zone of a clip boundary
                # and got grouped here despite differing types), the
                # divergence log surfaces it so we can audit why the split
                # didn't apply.
                for _coerced_ei, _orig_type in _coerced_types:
                    _record_divergence(
                        "zoom_type_coerced",
                        {
                            "clip_idx": _clip_idx,
                            "em_idx": _coerced_ei,
                            "original_type": _orig_type,
                            "em_t": round(float(emphasis_moments[_coerced_ei]["t"]), 3),
                        },
                        "coerced_to_dominant",
                        final={"type": _dominant_type},
                        reason="zoom_type_pre_split_missed_this_emphasis",
                    )
            else:
                print(
                    f"[generate-edit] Clip {_clip_idx}: merged {len(_ei_list)} "
                    f"zoom emphasis moments into one zoomEffect type={_dominant_type}.",
                    flush=True,
                )

    # Item 3 instrumentation (no behavior change): the single-event StepZoom
    # staircase is suspected to come from a zoom-type-split SEAM — a StepZoom
    # event whose window lands at a sub-clip boundary next to a different-zoom
    # sub-clip. A binary StepZoom event provably can't make three scale levels
    # on its own, and no merge-overlap fired, so log the seam arrangement here.
    # The next staircase render then reveals whether it's a cross-seam render or
    # an adjacent-zoom ramp at the boundary. Pure logging — fires only when a
    # StepZoom event reaches within ~0.30s of a zoom-type-split boundary.
    if _zoom_type_split_times:
        _seam_tol_s = 0.30  # ~18 frames @ 60fps, ~9 @ 30fps
        _split_set = sorted(set(_zoom_type_split_times))
        for _ci, _clip in enumerate(validated_cuts):
            _z = _clip.get("_zoom_effect")
            if not isinstance(_z, dict) or _z.get("type") != "StepZoom":
                continue
            _cs = float(_clip["source_start"])
            _ce = float(_clip["source_end"])
            _edge_split = [
                round(_st, 3) for _st in _split_set
                if abs(_st - _cs) <= _seam_tol_s or abs(_st - _ce) <= _seam_tol_s
            ]
            if not _edge_split:
                continue
            for _ev in (_z.get("events") or []):
                _evs = float(_ev.get("startMs") or 0.0) / 1000.0
                _eve = _evs + float(_ev.get("durationMs") or 0.0) / 1000.0
                _at_start = _evs <= _cs + _seam_tol_s
                _at_end = _eve >= _ce - _seam_tol_s
                if not (_at_start or _at_end):
                    continue
                _nb_idx = _ci + 1 if _at_end else _ci - 1
                _nb = validated_cuts[_nb_idx] if 0 <= _nb_idx < len(validated_cuts) else None
                _nb_z = _nb.get("_zoom_effect") if isinstance(_nb, dict) else None
                _nb_type = _nb_z.get("type") if isinstance(_nb_z, dict) else None
                _nb_win = (
                    [round(float(_nb["source_start"]), 3), round(float(_nb["source_end"]), 3)]
                    if _nb is not None else None
                )
                print(
                    f"[zoom-seam] clip={_ci} StepZoom "
                    f"ev=[{round(_evs, 3)},{round(_eve, 3)}]s "
                    f"clip_src=[{round(_cs, 3)},{round(_ce, 3)}]s "
                    f"split_at={_edge_split} "
                    f"neighbor_type={_nb_type} neighbor_window={_nb_win}",
                    flush=True,
                )

    for em in emphasis_moments:
        _layers = []
        if em["zoom_effect"]: _layers.append(f"zoom={em['zoom_effect']['type']}")
        if em["motion_graphic"]: _layers.append(f"mg={em['motion_graphic']['type']}@{em['motion_graphic']['anchor']}")
        print(
            f"[emphasis] {em['t']:.1f}s {em['type']}({em['intensity']}) "
            f"layers=[{','.join(_layers) if _layers else 'none'}]",
            flush=True,
        )
    edit_plan["_emphasis_moments"] = emphasis_moments

    # text_overlays — variant-dispatched, required props per variant.
    # Word-anchored: Gemini emits start_word_index (must be a kept word) and
    # duration_seconds. Python derives the output-time window from the word's
    # start timestamp projected through cuts.
    _to_raw = edit_plan.get("text_overlays")
    if _to_raw is None:
        _to_raw = []
    if not isinstance(_to_raw, list):
        raise ValueError("text_overlays must be an array")
    _to_validated = []
    for _i, _ov in enumerate(_to_raw):
        if not isinstance(_ov, dict):
            raise ValueError(f"text_overlays[{_i}] must be an object")
        _var = str(_ov.get("variant") or "").strip()
        if _var not in _valid_text_overlay_variants:
            raise ValueError(
                f"text_overlays[{_i}].variant must be one of {sorted(_valid_text_overlay_variants)}, got {_var!r}"
            )
        try:
            _swi = int(_ov["start_word_index"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f"text_overlays[{_i}] needs integer start_word_index"
            )
        if _swi < 0 or _swi >= len(_dg_words):
            raise ValueError(
                f"text_overlays[{_i}].start_word_index={_swi} out of range "
                f"[0, {len(_dg_words)-1}]"
            )
        if _swi not in _kept_word_indices:
            _wt = str(_dg_words[_swi].get("punctuated_word") or _dg_words[_swi].get("word") or "").strip()
            print(
                f"[generate-edit] DROP text_overlay '{_var}' [{_i}]: "
                f"start_word_index={_swi} ({_wt!r}) targets a REMOVED word. "
                f"Render continues without this overlay.",
                flush=True,
            )
            continue
        try:
            _du = float(_ov["duration_seconds"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f"text_overlays[{_i}] needs numeric duration_seconds"
            )
        if _du < 0.3 or _du > 10.0:
            raise ValueError(f"text_overlays[{_i}].duration_seconds out of range 0.3..10.0")
        # No rounding — match clip source bounds exactly. See the same
        # comment on motion_graphics _sw_start above for the precision-bug
        # class this avoids.
        _source_start = float(_dg_words[_swi].get("start") or 0)
        _entry = {
            "variant": _var,
            "start_word_index": _swi,
            "_source_start": _source_start,
            "duration_seconds": _du,
        }
        if _var == "sticky_note":
            _notes = _ov.get("notes")
            if not isinstance(_notes, list) or not _notes or len(_notes) > 3:
                raise ValueError(f"text_overlays[{_i}](sticky_note) needs notes array of 1-3 items")
            _entry["notes"] = []
            for _ni, _nn in enumerate(_notes):
                if not isinstance(_nn, dict) or not isinstance(_nn.get("text"), str):
                    raise ValueError(f"text_overlays[{_i}].notes[{_ni}] needs text")
                _entry["notes"].append({
                    "text": _EMOJI_RE.sub("", str(_nn["text"])).strip(),
                    "color": str(_nn.get("color") or "#FFEB3B"),
                    "rotation": float(_nn.get("rotation") or 0),
                })
        elif _var == "quote_card":
            for _p in ("quote", "attribution"):
                if not isinstance(_ov.get(_p), str) or not _ov[_p].strip():
                    raise ValueError(f"text_overlays[{_i}](quote_card) missing required prop {_p!r}")
                _entry[_p] = _EMOJI_RE.sub("", str(_ov[_p])).strip()
        elif _var == "caption_match":
            if not isinstance(_ov.get("text"), str) or not _ov["text"].strip():
                raise ValueError(f"text_overlays[{_i}](caption_match) missing required prop 'text'")
            _entry["text"] = _EMOJI_RE.sub("", str(_ov["text"])).strip()
            _pos = str(_ov.get("position") or "").strip()
            # caption_match owns the upper half (top/center). Captions own
            # the lower half. "bottom" would collide with the running
            # caption track — reject it at validation time.
            if _pos not in ("top", "center"):
                raise ValueError(
                    f"text_overlays[{_i}](caption_match).position must be 'top'|'center' "
                    f"(captions own the bottom zone)"
                )
            _entry["position"] = _pos
        _to_validated.append(_entry)
    edit_plan["text_overlays"] = _to_validated

    # ── Zone-aware overlap validation ────────────────────────────────────────
    # Two overlays may share a time window IF they live in different visual
    # zones. Only same-zone + overlapping-time is a real collision.
    #
    # Per-variant rendered zone for text_overlays — used for collision
    # detection only. Each variant's component pins to a fixed zone by
    # design: sticky_note = upper third pin, quote_card = center floating
    # card. `caption_match` is dynamic from its `position` prop. Motion
    # graphics carry their zone explicitly via the `anchor` field.
    _TEXT_OVERLAY_ZONE = {
        "sticky_note":   "upper_third_safe",
        "quote_card":    "center",
        # "caption_match" resolved below
    }
    _CAPTION_POS_TO_ZONE = {
        "top":    "upper_third_safe",
        "center": "center",
        "bottom": "lower_third_safe",
    }

    def _text_overlay_zone(ov):
        if ov.get("variant") == "caption_match":
            return _CAPTION_POS_TO_ZONE.get(ov.get("position") or "bottom", "lower_third_safe")
        return _TEXT_OVERLAY_ZONE.get(ov.get("variant"), "center")

    # text_overlay vs text_overlay: same-zone + time-overlap = collision.
    # Drop the second (later) overlay; the first wins. Render continues.
    _to_drop_indices = set()
    for _i in range(len(_to_validated)):
        if _i in _to_drop_indices:
            continue
        _a = _to_validated[_i]
        _a_start = _a["_source_start"]
        _a_end = _a_start + _a["duration_seconds"]
        _a_zone = _text_overlay_zone(_a)
        for _j in range(_i + 1, len(_to_validated)):
            if _j in _to_drop_indices:
                continue
            _b = _to_validated[_j]
            _b_start = _b["_source_start"]
            _b_end = _b_start + _b["duration_seconds"]
            _b_zone = _text_overlay_zone(_b)
            if _a_zone != _b_zone:
                continue  # different zones — coexistence is fine
            if _a_start < _b_end and _b_start < _a_end:
                print(
                    f"[generate-edit] DROP text_overlay '{_b['variant']}' "
                    f"[{_j}]: collides with [{_i}] ('{_a['variant']}') in zone "
                    f"'{_a_zone}' ({_a_start:.2f}-{_a_end:.2f}s vs "
                    f"{_b_start:.2f}-{_b_end:.2f}s). Render continues without "
                    f"the colliding overlay.",
                    flush=True,
                )
                _to_drop_indices.add(_j)

    # text_overlay vs emphasis motion_graphic: same-zone + time-overlap = collision.
    # Emphasis MG windows center slightly before the moment's t (25% pre-roll).
    # MG zone = its explicit `anchor` field. Drop the text_overlay (the
    # emphasis MG carries narrative weight); render continues.
    for _to_idx, _to in enumerate(_to_validated):
        if _to_idx in _to_drop_indices:
            continue
        _to_start = _to["_source_start"]
        _to_end = _to_start + _to["duration_seconds"]
        _to_zone = _text_overlay_zone(_to)
        for _em in emphasis_moments:
            if not _em["motion_graphic"]:
                continue
            _em_zone = str(_em["motion_graphic"].get("anchor") or "center")
            if _to_zone != _em_zone:
                continue  # different zones — fine
            _em_dur = float(_em["duration"])
            _em_mg_start = max(0.0, _em["t"] - _em_dur * 0.25)
            _em_mg_end = _em_mg_start + _em_dur
            if _to_start < _em_mg_end and _em_mg_start < _to_end:
                print(
                    f"[generate-edit] DROP text_overlay '{_to['variant']}' "
                    f"[{_to_idx}]: collides with emphasis motion_graphic "
                    f"'{_em['motion_graphic']['type']}' in zone '{_to_zone}' "
                    f"({_to_start:.2f}-{_to_end:.2f}s vs "
                    f"{_em_mg_start:.2f}-{_em_mg_end:.2f}s at emphasis t="
                    f"{_em['t']:.2f}s). Render continues without the overlay.",
                    flush=True,
                )
                _to_drop_indices.add(_to_idx)
                break

    # Apply the accumulated overlay drops in one pass (preserves index
    # references inside the loops above).
    if _to_drop_indices:
        _to_validated = [t for _i, t in enumerate(_to_validated) if _i not in _to_drop_indices]
        edit_plan["text_overlays"] = _to_validated

    if _to_validated:
        print(
            f"[text-overlays] {len(_to_validated)} overlay(s): "
            + ", ".join(f"{o['variant']}@{o['_source_start']:.1f}s" for o in _to_validated),
            flush=True,
        )

    # caption_keywords is Gemini's explicit decision — no auto-derivation.

    # ── Parse sound effects ──────────────────────────────────────────────
    raw_sfx = edit_plan.get("sound_effects", [])
    sound_effects = []
    valid_sounds = set(_SFX_CATEGORIES.keys())
    _sfx_dg_words = edit_plan.get("_deepgram_words") or []
    for _si, sfx in enumerate(raw_sfx):
        if not isinstance(sfx, dict):
            raise ValueError(f"sound_effects[{_si}] must be an object")
        if "word_index" not in sfx or "sound" not in sfx:
            raise ValueError(
                f"sound_effects[{_si}] missing required keys 'word_index' and 'sound'"
            )
        try:
            _wi = int(sfx["word_index"])
        except (TypeError, ValueError):
            raise ValueError(
                f"sound_effects[{_si}].word_index must be an integer, got "
                f"{sfx.get('word_index')!r}"
            )
        if _wi < 0 or _wi >= len(_sfx_dg_words):
            raise ValueError(
                f"sound_effects[{_si}].word_index={_wi} is out of range "
                f"[0, {len(_sfx_dg_words)-1}]."
            )
        if _wi not in _kept_word_indices:
            _wt = str(_sfx_dg_words[_wi].get("punctuated_word") or _sfx_dg_words[_wi].get("word") or "").strip()
            print(
                f"[generate-edit] DROP sound_effect '{sfx.get('sound')}' [{_si}]: "
                f"word_index={_wi} ({_wt!r}) targets a REMOVED word — viewer "
                f"would never hear the trigger. Render continues without this "
                f"SFX.",
                flush=True,
            )
            continue
        sound = str(sfx["sound"]).strip().lower()
        if sound not in valid_sounds:
            raise ValueError(
                f"sound_effects[{_si}].sound={sound!r} is not a canonical name. "
                f"Must be one of {sorted(valid_sounds)} — pick the exact "
                f"canonical name documented in the SFX section of the prompt."
            )
        # Derive t + word text from the word_index. Python is the single source
        # of truth for timing — Gemini can't emit a mismatched timestamp.
        _trigger_w = _sfx_dg_words[_wi]
        t = float(_trigger_w.get("start") or 0.0)
        word = str(_trigger_w.get("word") or _trigger_w.get("punctuated_word") or "").strip().lower().rstrip(".,!?;:'\"")
        # No in-clip pre-roll check — SFX audio plays on the GLOBAL output
        # timeline via FFmpeg's adelay + amix (see render_multi_clip). The
        # build-up phase plays over whatever precedes the trigger word in the
        # output, with no respect for source clip boundaries. The only physical
        # limit is the output-timeline start (t=0); if the projected trigger
        # time is within the onset duration of that, adelay clamps to 0 and
        # the crack lands a couple hundred ms late on the first few words of
        # the video. No audio is truncated.
        sound_effects.append({"t": t, "sound": sound, "word": word, "_word_idx": _wi})

    # Sound effects are taken EXACTLY as Gemini provided them. No caps,
    # no spacing filter, no auto-placement, no dedup. The Gemini prompt is
    # the single source of truth for SFX placement rules — if a placement
    # is wrong, the fix is the prompt.
    if sound_effects:
        sound_effects.sort(key=lambda x: x["t"])
        print(f"[generate-edit] Sound effects: {len(sound_effects)} placements", flush=True)
        for sfx in sound_effects:
            print(f"[generate-edit]   {sfx['t']:.1f}s: {sfx['sound']}", flush=True)
    edit_plan["sound_effects"] = sound_effects
    edit_plan["_parsed_sound_effects"] = sound_effects

    # Only one remaining boolean: audio_denoise (drives afftdn filter).
    _ad = edit_plan.get("audio_denoise")
    if isinstance(_ad, str):
        edit_plan["audio_denoise"] = _ad.strip().lower() in ("true", "1", "yes")
    else:
        edit_plan["audio_denoise"] = bool(_ad)

    # Transitions — mirror VALID_TRANSITION_TYPES so adding a type only
    # edits ONE place (rather than re-syncing several duplicated sets,
    # which is what caused the DipToBlack derivation-bug crash). "none"
    # kept as a valid sentinel for no transition.
    valid_transitions = set(VALID_TRANSITION_TYPES) | {"none"}

    final_cuts = []
    for _ci, clip_entry in enumerate(validated_cuts):
        # transition_out is only set by the earlier validated-transition
        # application block, which rejects unknown types. Any invalid value
        # reaching here is a derivation bug — fail hard instead of silently
        # coercing to "none".
        transition = str(clip_entry.get("transition_out") or "none").strip()
        if transition not in valid_transitions:
            raise RuntimeError(
                f"validated_cuts[{_ci}] has transition_out={transition!r} which "
                f"is not in {sorted(valid_transitions)}. This is a derivation "
                f"bug — transition_out should only ever be set by the upstream "
                f"validated-transition block."
            )
        # Speed is Gemini's creative decision — a constant playback rate per
        # clip. Range 0.7–1.4 covers the entire viral-pacing band. Anything
        # below 0.7 produces audible audio artifacts; anything above 1.4
        # reads as fast-forward, not pacing. Reject out-of-range instead of
        # silently clamping so the prompt's stated range is enforced.
        _raw_speed = clip_entry.get("speed")
        if _raw_speed is None:
            speed = 1.0
        else:
            try:
                speed = float(_raw_speed)
            except (TypeError, ValueError):
                raise ValueError(
                    f"validated_cuts[{_ci}].speed={_raw_speed!r} is not a number."
                )
            if not (0.7 <= speed <= 1.4):
                raise ValueError(
                    f"validated_cuts[{_ci}].speed={speed} is outside the "
                    f"documented range 0.7–1.4. Set the clip's speed inside "
                    f"this band or omit the field for default 1.0."
                )
        _new_cut = {
            "source_start": clip_entry["source_start"],
            "source_end": clip_entry["source_end"],
            "transition_out": transition,
            "speed": speed,
        }
        # Preserve the full PackTransitionExtras dict + zoom effect so the
        # renderer can forward component-specific props (direction, palette,
        # title, etc.).
        if clip_entry.get("_transition_extras"):
            _new_cut["_transition_extras"] = clip_entry["_transition_extras"]
        if clip_entry.get("_zoom_effect"):
            _new_cut["_zoom_effect"] = clip_entry["_zoom_effect"]
        # NOTE: tight-cut overlays no longer travel on clips. They are resolved
        # as a boundary-keyed list (edit_plan["_resolved_tight_cut_overlays"])
        # and projected to output frames at render — see the emit loop. This
        # decouples them from clip-pair structure so mid-clip boundaries (no
        # split) are decorable.
        final_cuts.append(_new_cut)

    # Zoom and motion graphics are attached to each emphasis_moment explicitly
    # by Gemini (emphasis_moments[i].zoom_effect / motion_graphic). No
    # auto-zoom. If Gemini didn't emit a
    # zoom_effect on a moment, no zoom fires — that's an intentional decision,
    # not an omission to repair.

    # Strip legacy fields that older Gemini outputs (or re-edit plans) may
    # carry. The Remotion-primary pipeline doesn't consume them.
    edit_plan["cuts"] = final_cuts
    for _legacy_field in (
        "teal_orange", "beat_sync", "video_profile", "frame_layout",
        "vignette", "sharpening", "grain", "denoise", "cinematic_bars",
        "shadow_lift", "highlight_rolloff", "vibrance", "visual_effects",
        "remove_words", "target_duration", "clips",
    ):
        edit_plan.pop(_legacy_field, None)

    total_clip_duration = sum(max(0, c["source_end"] - c["source_start"]) for c in final_cuts)
    if video_duration > 0 and total_clip_duration / video_duration < 0.3:
        print(
            f"[generate-edit] WARNING: Gemini's clips only cover {(total_clip_duration / video_duration)*100:.0f}% "
            f"of the video ({total_clip_duration:.1f}s of {video_duration:.1f}s)",
            flush=True,
        )

    edit_plan["analysis_data"] = analysis

    print(
        f"[generate-edit] Recipe: {len(final_cuts)} clips, "
        f"{len(edit_plan.get('sound_effects', []))} sfx, "
        f"intent={edit_plan.get('color_intent', 'none')}, "
        f"captions={edit_plan.get('caption_style', 'none')}",
        flush=True,
    )

    return edit_plan


# ─── PLAN-DIFF (RE-EDIT) ─────────────────────────────────────────────────────
#
# Given an old edit_plan + user change request, Gemini self-classifies the intent
# (tweak | reinterpret | needs_clarification) and either emits a new_plan that
# echoes every field byte-identical except the requested change, or a fused vibe
# string for the reinterpret path. responseJsonSchema forces the echo — no field
# drops — so the tweak path is surgically faithful.

def generate_plan_diff(old_plan, change_request, old_vibe=None, transcript=None):
    """Call Gemini to produce a new plan from (old_plan, change_request).

    Returns a dict with keys: classification, new_plan, fused_vibe,
    changed_fields, human_summary, clarification_question.
    Raises RuntimeError on unrecoverable failure (caller should fall back to
    full reinterpret).
    """
    if not isinstance(old_plan, dict):
        raise RuntimeError("generate_plan_diff: old_plan must be a dict")
    if not change_request or not isinstance(change_request, str):
        raise RuntimeError("generate_plan_diff: change_request is required")

    client = _get_genai_client()

    # Strip internal-only fields (underscored) — we only diff the sanitized plan.
    sanitized_old_plan = {k: v for k, v in old_plan.items() if not (isinstance(k, str) and k.startswith("_"))}

    # Full transcript with per-word indices — Gemini needs to resolve any word_index
    # in the old plan AND any ordinal/temporal reference in the user's change request.
    # The earlier 300-word cap broke long-video re-edits: the user could say "remove
    # the zoom at 12.5s" and the model would be blind to the word that anchored it.
    # Token cost is bounded by source video length (10-90s typical); the model is
    # Gemini 3.1 Pro with a multi-million-token context — the transcript is rounding
    # error against that.
    transcript_preview = ""
    if isinstance(transcript, dict):
        words = transcript.get("words") or []
        if words:
            # Format as "[idx] word @ Ts" so the model can resolve any of the three
            # reference modes (ordinal / temporal / word-based) without guessing.
            _lines = []
            for _wi, _w in enumerate(words):
                _wt = str(_w.get("punctuated_word") or _w.get("word") or "")
                _ws = float(_w.get("start") or 0.0)
                _lines.append(f"[{_wi}] {_wt} @ {_ws:.2f}s")
            transcript_preview = "\n".join(_lines)

    prompt_parts = [
        "You are editing a Promptly video-edit PLAN. The plan is a JSON document describing "
        "every decision that produced a rendered video. Top-level fields include: cuts, "
        "transitions, tight_cut_overlays (overlay-on-top-of-hard-cut decorations at TIGHT "
        "boundaries — 4 types: LightLeak, ShutterFlash, NewspaperWipe, SceneTitle; the first "
        "three are 180ms punctuation flashes, SceneTitle is a 1200ms typographic chapter-break "
        "panel with required `title` + optional `label`), caption_style, "
        "caption_position_changes (list of {word_index, position}), "
        "caption_position_segments (DERIVED from caption_position_changes — do not edit directly), "
        "keywords, broll_clips, text_overlays (each has a variant "
        "discriminator: sticky_note|quote_card|caption_match), "
        "motion_graphics (with semantic anchor), emphasis_moments (each binds explicit "
        "zoom_effect / motion_graphic), sfx_placements, thumbnail_word_index "
        "(thumbnail_timestamp derived), per-clip `speed` (constant 0.7–1.4 per cut), outro. "
        "The user has requested a change.\n\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "HONOR THE USER'S REQUEST LITERALLY. ABSOLUTELY.\n"
        "═══════════════════════════════════════════════════════════════════\n"
        "The user is telling you what they want changed in plain language. Read it LITERALLY and "
        "execute it EXACTLY. Do not add your editorial judgment about whether the change is a good "
        "idea — they own that call. Common requests and exactly what to emit:\n\n"
        "  • 'remove captions' / 'no captions' / 'don't want captions' / 'turn off subtitles'\n"
        "      → set caption_style to 'none', caption_keywords to [], caption_position_changes to [].\n"
        "  • 'remove B-roll' / 'no B-roll' / 'just talking head'\n"
        "      → set broll_clips to [].\n"
        "  • 'remove SFX' / 'no sound effects' / 'no audio effects'\n"
        "      → set sound_effects to [].\n"
        "  • 'remove transitions' / 'no transitions' / 'just hard cuts'\n"
        "      → set transitions to [].\n"
        "  • 'remove zooms' / 'no zooms' / 'no emphasis' / 'static camera'\n"
        "      → set emphasis_moments to [].\n"
        "  • 'remove motion graphics' / 'no MGs' / 'no popups' / 'no graphics'\n"
        "      → set motion_graphics to [].\n"
        "  • 'remove text overlays' / 'no titles' / 'no labels'\n"
        "      → set text_overlays to [].\n"
        "  • 'remove tight-cut overlays' / 'no overlays' / 'no chapter break'\n"
        "      → set tight_cut_overlays to [].\n"
        "  • 'change caption style to X' / 'use Lumen captions'\n"
        "      → set caption_style to the named style; preserve everything else.\n"
        "  • 'change the SFX on word X to Y' / 'remove the whoosh at the start'\n"
        "      → edit ONLY the targeted sound_effects entry; preserve everything else.\n"
        "  • 'make the X B-roll less long' / 'change the gym clip'\n"
        "      → edit ONLY the targeted broll_clips entry; preserve everything else.\n"
        "  • 'I don't like the X' followed by anything — they want it changed/removed; act on the\n"
        "    targeted field exclusively. If unclear what to replace it with, classify as\n"
        "    'needs_clarification' and ask a tight question.\n\n"
        "ADDING NEW COMPONENTS is also a tweak — explicitly supported across every component type. "
        "Same byte-identical-echo discipline applies: emit the new entry alongside everything the "
        "user didn't touch. Examples:\n\n"
        "  • 'add a zoom on word K' / 'add an emphasis on the word \"finally\"' / 'add a SmoothPush\n"
        "    on the payoff word'\n"
        "      → append a new emphasis_moment with word_indices=[K], a zoom_effect of the inferred\n"
        "        type (default SmoothPush if unspecified, with the payoff matched to its arc role),\n"
        "        and a matching key_moment in video_plan.\n"
        "  • 'add a transition at the chapter break' / 'add a NewspaperWipe after the setup'\n"
        "      → append a new transition with after_word_index from the CUT BOUNDARIES list and the\n"
        "        named (or inferred-by-character) type.\n"
        "  • 'add a tight_cut_overlay at K' / 'add a LightLeak at the pivot' / 'put a SceneTitle\n"
        "    \"Act Two\" at the chapter break'\n"
        "      → append a new tight_cut_overlays entry with after_word_index from the TIGHT\n"
        "        BOUNDARIES list. For SceneTitle, `title` is REQUIRED (1-3 uppercase words) and\n"
        "        `label` is optional. For LightLeak / ShutterFlash / NewspaperWipe, omit title/label\n"
        "        entirely (those overlays have no text).\n"
        "  • 'add a B-roll over words K-M of <subject>' / 'add a cutaway showing X'\n"
        "      → append a new broll_clips entry with start_word_index=K, end_word_index=M, and a\n"
        "        keyword + reason field. The picker will resolve the keyword to a real clip later.\n"
        "  • 'add an MG over words K-M' / 'put a StatCard on the stat'\n"
        "      → append a new motion_graphics entry with start_word_index=K, end_word_index=M, a\n"
        "        named type, and an anchor (default upper_third_safe / lower_third_safe).\n"
        "  • 'add a text overlay K-M saying X' / 'put a sticky note here'\n"
        "      → append a new text_overlays entry with the right variant and start_word_index.\n"
        "  • 'add an SFX on word K' / 'put a ching on the punchline'\n"
        "      → append a new sound_effects entry with word_index=K and a matching sound style.\n\n"
        "REPLACEMENTS are tweaks too — combine the targeted edit with the new state:\n\n"
        "  • 'change the sticky_note on word K to caption_match' / 'swap the StatCard on word K\n"
        "    for a Notification'\n"
        "      → edit ONLY the targeted entry's variant / type field; preserve every other entry\n"
        "        in that array byte-identical.\n"
        "  • 'change the LightLeak to a ShutterFlash' / 'use a SceneTitle there instead'\n"
        "      → edit ONLY the targeted tight_cut_overlays entry; carry over after_word_index.\n"
        "        For a SceneTitle replacement, ALSO add `title` (and optional `label`); for a\n"
        "        change AWAY from SceneTitle, STRIP title/label (those fields are SceneTitle-only).\n\n"
        "REFERENCE SYNTAX — how to resolve which component the user means:\n\n"
        "  • Ordinal: 'the 2nd zoom' / 'the first transition' / 'the last MG' / 'zooms 2 and 3'.\n"
        "    Index into the prior plan's array (0-based internally; the user uses 1-based names).\n"
        "    'The 2nd zoom' = emphasis_moments[1]. 'Zooms 2 and 3' = emphasis_moments[1] and [2].\n"
        "  • Temporal: 'the zoom at 12.5s' / 'the transition around 8s'. Resolve via word_index\n"
        "    timing — find the component whose anchor word's start (or end, for transitions) is\n"
        "    closest to the named timestamp. Ignore differences under ~0.3s as tied; if ties\n"
        "    cannot be broken, classify as 'needs_clarification'.\n"
        "  • Word-based: 'the zoom on the word \"finally\"' / 'the B-roll over \"deadlift\"'.\n"
        "    Resolve via word index — find the component whose anchor word matches.\n"
        "  • Type+position composite: 'the second LightLeak' / 'the first NewspaperWipe' — index\n"
        "    among entries OF THAT TYPE only.\n"
        "  • Ambiguity: if the reference matches multiple candidates within the tolerance (two\n"
        "    zooms 0.2s apart and the user said 'the zoom around 7.5s'), do NOT guess. Emit\n"
        "    'needs_clarification' with a tight question naming both candidates.\n\n"
        "The empty-array case is real: if the user said 'no B-roll', emitting an empty broll_clips\n"
        "array IS the correct answer. Do not preserve the old clips because you think they were\n"
        "tasteful. Do not add a single 'minimal' clip as a compromise. Execute the literal request.\n\n"
        "COMPOSITE REQUESTS — when a single user request spans multiple operations (e.g. 'remove\n"
        "the 2nd zoom and add a LightLeak at the pivot'), execute ALL of them in the same tweak\n"
        "emission. Each operation independently follows the rules above. Every field NEITHER\n"
        "operation touches stays byte-identical.\n\n"
        "Your job:\n\n"
        "1) CLASSIFY the request as one of:\n"
        "   - 'tweak': scoped change to specific fields — ANY combination of remove / add / replace\n"
        "     operations targeted at named (or referenced) components. The user CAN ask to add new\n"
        "     things alongside removing or replacing existing ones; the operations co-exist in one\n"
        "     tweak. You MUST echo every field the user did not address byte-identical — do NOT\n"
        "     edit anything beyond the explicitly-targeted ops.\n"
        "   - 'guided_redraft': directional re-shape with carry-over defaults. The user wants a\n"
        "     section or aspect REWORKED (not surgically targeted, not totally re-vibed). Examples:\n"
        "     'rework the middle section to feel more urgent', 'make the second half punchier',\n"
        "     'pace the build section faster', 'change the energy of the payoff', 'redo the\n"
        "     captions and emphasis but keep everything else', 'I want more chapter structure'.\n"
        "     The user IS giving direction, but the direction is broader than named operations —\n"
        "     a redraft of one OR MORE component categories is the right answer, with everything\n"
        "     ELSE carrying over from the prior plan as soft default. The downstream renderer\n"
        "     will pass the prior plan + your fused_vibe into a fresh edit generation with the\n"
        "     prior decisions as starting context; it can choose to keep, modify, or replace any\n"
        "     individual decision based on what fits the new direction. Pick this when 'tweak' is\n"
        "     too rigid (the user named no specific operations) AND 'reinterpret' is too blunt\n"
        "     (the user signalled a partial reshape, not a total recast).\n"
        "   - 'reinterpret': total recast with no carry-over. The user explicitly wants a\n"
        "     completely different feel ('throw it out and start over', 'completely different\n"
        "     vibe', 'redo from scratch', 'I hate this — totally different direction'). The prior\n"
        "     plan is irrelevant; emit a fused_vibe and the renderer generates a fresh plan with\n"
        "     no prior-plan context. Reserve this for explicit start-over signals; default to\n"
        "     'guided_redraft' when the user wants a reshape rather than a recast.\n"
        "   - 'needs_clarification': request is too vague to map to fields (e.g. 'make it better',\n"
        "     'fix it'), OR a reference is genuinely ambiguous (two components match the user's\n"
        "     descriptor and the surrounding context doesn't disambiguate). Emit a tight,\n"
        "     specific clarification_question — do NOT guess.\n\n"
        "CLASSIFIER GUIDANCE — the four-way split:\n"
        "  • Named ops with anchors → 'tweak'. e.g. 'remove the 2nd zoom and add a LightLeak\n"
        "    at word 40' (specific operations targeting specific components).\n"
        "  • Directional reshape without ops → 'guided_redraft'. e.g. 'pace the middle slower'\n"
        "    (a direction, not an operation; ALL prior decisions are carry-over candidates).\n"
        "  • Total recast → 'reinterpret'. e.g. 'redo this completely different' (explicit\n"
        "    abandonment of prior decisions).\n"
        "  • Vague / ambiguous → 'needs_clarification'. e.g. 'make it better' (no direction).\n"
        "When in doubt between 'tweak' and 'guided_redraft', prefer 'guided_redraft' if the\n"
        "user did not name specific components — tweak's byte-identical-echo rule punishes\n"
        "vagueness with brittle outputs. When in doubt between 'guided_redraft' and\n"
        "'reinterpret', prefer 'guided_redraft' unless the user explicitly waved away the\n"
        "prior work — the prior plan is almost always useful context, not noise.\n\n"
        "2) For 'tweak': produce new_plan with ONLY the user-requested operations applied. Every\n"
        "   other field — cuts, transitions, tight_cut_overlays, broll_clips (including\n"
        "   pexels_video_id + pexels_file_url + clip_in/out), sfx_placements, text_overlays,\n"
        "   motion_graphics, emphasis_moments, caption_position_changes (and the derived\n"
        "   caption_position_segments) — preserved byte-identical. Add operations append a new\n"
        "   entry to the right array (or set the right scalar) in addition to the existing entries.\n"
        "   Remove operations either empty the whole array (when the request is a category removal\n"
        "   like 'no B-roll') or drop only the referenced entry (when the request names a specific\n"
        "   one). Replace operations edit the referenced entry's fields without touching siblings.\n"
        "   Every timing decision references a word by index; never invent or shift a raw timestamp.\n"
        "   The pipeline derives timestamps from word_index fields. When the request is a category\n"
        "   removal, the targeted field becomes empty / 'none' as listed above — that IS the\n"
        "   explicit change.\n\n"
        "3) Emit changed_fields: dotted paths of what you changed (e.g. ['caption_style', "
        "'cuts[3].speed', 'caption_position_changes[1].position', 'text_overlays[2].variant']). "
        "Empty array for reinterpret or clarification.\n\n"
        "4) Emit human_summary: one sentence users can read (e.g. 'Removed captions. Preserved 11 "
        "cuts, B-roll, and 2 text overlays.').\n\n"
        f"PRIOR VIBE: {old_vibe or '(unknown)'}\n\n"
        f"USER CHANGE REQUEST: {change_request}\n\n"
        f"OLD PLAN (JSON):\n{json.dumps(sanitized_old_plan, separators=(',', ':'))}\n\n",
    ]
    if transcript_preview:
        prompt_parts.append(
            "TRANSCRIPT (every kept word, with its source word_index and start time — use this to "
            "resolve ordinal, temporal, and word-based references in the user's change request, "
            "AND to ground any new word_index anchor in an ADD operation):\n"
            f"{transcript_preview}\n\n"
        )
    prompt_parts.append(
        "Respond with a single JSON object matching this shape:\n"
        "{\n"
        '  "classification": "tweak" | "guided_redraft" | "reinterpret" | "needs_clarification",\n'
        '  "clarification_question": string | null,                  // only for needs_clarification\n'
        '  "new_plan": <full edit plan object> | null,               // only for tweak\n'
        '  "fused_vibe": string | null,                              // for guided_redraft AND reinterpret\n'
        '  "changed_fields": [string],                               // tweak only — paths you changed; empty array otherwise\n'
        '  "human_summary": string                                   // always — one sentence the user reads\n'
        "}\n"
    )

    prompt = "".join(prompt_parts)

    print(f"[plan-diff] change_request: {change_request[:200]}", flush=True)
    _t0 = time.time()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt],
        config=genai_types.GenerateContentConfig(
            temperature=0.2,
            # 16K so the response can include the full echoed plan plus
            # thinking. The plan itself runs 3-5K JSON; HIGH thinking adds
            # another 2-4K. Old 8K cap could truncate.
            max_output_tokens=16384,
            response_mime_type="application/json",
            # HIGH thinking so the model actually reasons about whether the
            # request maps to a tweak / guided_redraft / reinterpret /
            # clarification and picks the right surgical edit. The prior
            # LOW setting was Gemini's "shallow" mode — fine for trivial
            # echoes, not enough for instructions like 'remove all SFX
            # except the boom on word 66' or 'pace the middle slower'.
            thinking_config=genai_types.ThinkingConfig(thinking_level="HIGH"),
        ),
    )
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        raise RuntimeError("Empty plan-diff response from Gemini")
    parsed = json.loads(text) if text.startswith("{") else extract_json(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("Plan-diff response is not a JSON object")

    classification = str(parsed.get("classification") or "").strip()
    if classification not in ("tweak", "guided_redraft", "reinterpret", "needs_clarification"):
        raise RuntimeError(f"Invalid plan-diff classification: {classification!r}")

    if classification == "tweak":
        new_plan = parsed.get("new_plan")
        if not isinstance(new_plan, dict):
            raise RuntimeError("tweak classification requires new_plan object")
        # Enforce: new_plan must retain the required scaffold fields from old_plan.
        for required in ("cuts", "caption_style", "aspect_ratio"):
            if required not in new_plan or new_plan[required] in (None, "", []):
                if required in sanitized_old_plan:
                    new_plan[required] = sanitized_old_plan[required]
        # Ensure broll persistence fields survive when Gemini echoes broll_clips
        if isinstance(new_plan.get("broll_clips"), list) and isinstance(sanitized_old_plan.get("broll_clips"), list):
            for _i, _new_br in enumerate(new_plan["broll_clips"]):
                if _i < len(sanitized_old_plan["broll_clips"]) and isinstance(_new_br, dict):
                    _old_br = sanitized_old_plan["broll_clips"][_i]
                    for _persist_key in ("pexels_video_id", "pexels_file_url", "width", "height", "duration"):
                        if _persist_key not in _new_br and _persist_key in _old_br:
                            _new_br[_persist_key] = _old_br[_persist_key]
    elif classification in ("guided_redraft", "reinterpret"):
        # Both shape Gemini's response the same way: emit a fused_vibe
        # carrying the user's directional change_request. The downstream
        # difference lives in the DISPATCHER:
        #   reinterpret    → full pipeline, no prior-plan carry-over.
        #   guided_redraft → full pipeline WITH prior plan injected as
        #                    soft default + change_request as guidance.
        fused = parsed.get("fused_vibe")
        if not isinstance(fused, str) or not fused.strip():
            # Fail soft — synthesize a fused vibe from the prior vibe +
            # change request rather than failing the whole re-edit. The
            # downstream pipeline will accept any non-empty vibe.
            fused_synth = f"{old_vibe or ''} — {change_request}".strip(" —")
            print(
                f"[plan-diff] {classification} response missing fused_vibe — "
                f"synthesizing from old_vibe + change_request: {fused_synth[:120]}",
                flush=True,
            )
            parsed["fused_vibe"] = fused_synth

    print(f"[plan-diff] classification={classification} in {time.time()-_t0:.1f}s", flush=True)
    return {
        "classification": classification,
        "clarification_question": parsed.get("clarification_question"),
        "new_plan": parsed.get("new_plan"),
        "fused_vibe": parsed.get("fused_vibe"),
        "changed_fields": parsed.get("changed_fields") or [],
        "human_summary": str(parsed.get("human_summary") or "Updated your video."),
    }


# ─── RE-EDIT LAYER 3: DIFF-CONFIRMATION SAFETY NET ─────────────────────────
#
# After the plan-diff classifier returns a new_plan (tweak) OR after
# generate_edit_gemini emits a guided_redraft, we compute a structured diff
# vs the prior_plan and ask a small Gemini call to classify each change as
# in-scope (the user asked for it, explicitly or as a clear consequence) or
# out-of-scope (Gemini drifted beyond the contract).
#
# Phase 1 (this commit) — observability everywhere + narrow auto-revert for
# top-level SCALAR fields only (caption_style, thumbnail_word_index, outro).
# Array-level reverts wait for production data to validate the classifier;
# applying them now would risk turning ONE class of failure (Gemini drift)
# into TWO (revert misclassifies a legit downstream consequence).
#
# Phase 2 (deferred — after we have a few hundred re-edits in production):
# extend auto-revert to anchor-keyed array entries in tweak mode, using
# the classifier confidence + production-tuned heuristics.
#
# Anchor functions per top-level list — for each entry we extract its
# identity key from anchor fields (word_index, after_word_index, etc.).
# A change is "to the entry with this anchor"; an added/removed entry is
# "at this anchor that newly exists / no longer exists." This is more
# stable than positional indexing across edits.

_DIFF_LIST_ANCHORS = {
    "emphasis_moments": lambda e: (
        tuple(e.get("word_indices") or [])[:1] or None
        if isinstance(e, dict) else None
    ),
    "transitions": lambda e: (
        e.get("after_word_index")
        if isinstance(e, dict) else None
    ),
    "tight_cut_overlays": lambda e: (
        e.get("after_word_index")
        if isinstance(e, dict) else None
    ),
    "broll_clips": lambda e: (
        (e.get("start_word_index"), e.get("end_word_index"))
        if isinstance(e, dict) else None
    ),
    "text_overlays": lambda e: (
        e.get("start_word_index")
        if isinstance(e, dict) else None
    ),
    "motion_graphics": lambda e: (
        (e.get("start_word_index"), e.get("end_word_index"))
        if isinstance(e, dict) else None
    ),
    "sound_effects": lambda e: (
        e.get("word_index")
        if isinstance(e, dict) else None
    ),
    "caption_position_changes": lambda e: (
        e.get("word_index")
        if isinstance(e, dict) else None
    ),
}

# Top-level scalar fields safe to auto-revert in Phase 1. These are
# leaf-level decisions with no downstream dependencies on each other,
# so reverting one doesn't risk breaking another. Array-level reverts
# (broll_clips entries, emphasis_moments, transitions) need production
# data first — Phase 2.
_PHASE1_REVERTABLE_SCALARS = frozenset({
    "caption_style",
    "thumbnail_word_index",
    "outro",
})

# Fields we never diff against — derived downstream or pipeline-internal.
_DIFF_SKIP_KEYS = frozenset({
    "caption_position_segments",  # derived from caption_position_changes
    "thumbnail_timestamp",         # derived from thumbnail_word_index
    "analysis_data",               # cached intermediate, not user-facing
})


def compute_plan_diff(prior_plan, new_plan):
    """Structured field+entry-level diff between two edit plans.

    Returns a list of diff dicts:
      {"path": "caption_style", "list_key": None, "anchor": None,
       "op": "changed", "old": "PaperII", "new": "Lumen"}
      {"path": "emphasis_moments[anchor=(5,)]", "list_key": "emphasis_moments",
       "anchor": (5,), "op": "added", "new": {...}, "old": None}
      {"path": "transitions[anchor=12]", "list_key": "transitions",
       "anchor": 12, "op": "removed", "old": {...}, "new": None}

    Anchor identity comes from each list's natural key (word_index family);
    falls back to positional comparison when no anchor is available.
    Returns [] when either plan is invalid or when there are no differences.
    """
    diffs = []
    if not isinstance(prior_plan, dict) or not isinstance(new_plan, dict):
        return diffs

    # Collect keys present in either plan (excluding internals + derived).
    all_keys = set()
    for k in list(prior_plan.keys()) + list(new_plan.keys()):
        if not isinstance(k, str):
            continue
        if k.startswith("_"):
            continue
        if k in _DIFF_SKIP_KEYS:
            continue
        all_keys.add(k)

    for key in sorted(all_keys):
        old = prior_plan.get(key)
        new = new_plan.get(key)
        if old is None and new is None:
            continue

        # Scalar comparison
        if not isinstance(old, list) and not isinstance(new, list):
            if old != new:
                diffs.append({
                    "path": key,
                    "list_key": None,
                    "anchor": None,
                    "op": "changed",
                    "old": old,
                    "new": new,
                })
            continue

        # List comparison
        anchor_fn = _DIFF_LIST_ANCHORS.get(key)
        old_list = old if isinstance(old, list) else []
        new_list = new if isinstance(new, list) else []

        if anchor_fn:
            old_by_anchor = {}
            for e in old_list:
                a = anchor_fn(e)
                if a is not None:
                    old_by_anchor[a] = e
            new_by_anchor = {}
            for e in new_list:
                a = anchor_fn(e)
                if a is not None:
                    new_by_anchor[a] = e

            all_anchors = set(old_by_anchor) | set(new_by_anchor)
            # Stable sort for deterministic ordering across runs.
            for a in sorted(all_anchors, key=lambda x: (str(type(x).__name__), str(x))):
                old_e = old_by_anchor.get(a)
                new_e = new_by_anchor.get(a)
                if old_e is None and new_e is not None:
                    diffs.append({
                        "path": f"{key}[anchor={a}]",
                        "list_key": key,
                        "anchor": a,
                        "op": "added",
                        "old": None,
                        "new": new_e,
                    })
                elif old_e is not None and new_e is None:
                    diffs.append({
                        "path": f"{key}[anchor={a}]",
                        "list_key": key,
                        "anchor": a,
                        "op": "removed",
                        "old": old_e,
                        "new": None,
                    })
                elif old_e != new_e:
                    diffs.append({
                        "path": f"{key}[anchor={a}]",
                        "list_key": key,
                        "anchor": a,
                        "op": "changed",
                        "old": old_e,
                        "new": new_e,
                    })
        else:
            # Unanchored list — just note length / content change at the
            # list level (no per-entry resolution).
            if old_list != new_list:
                diffs.append({
                    "path": key,
                    "list_key": key,
                    "anchor": None,
                    "op": "changed",
                    "old_count": len(old_list),
                    "new_count": len(new_list),
                })
    return diffs


def validate_reedit_changes(prior_plan, new_plan, change_request, mode):
    """Call Gemini to classify each diff as in-scope or out-of-scope vs the
    user's change_request. Returns:
        {"verdict": "no_changes" | "all_in_scope" | "partial_out_of_scope" | "error",
         "diffs": [...],
         "out_of_scope_paths": [list of path strings],
         "reasoning": "1-2 sentence model-supplied explanation"}

    FAIL-OPEN — if the Gemini call errors or returns malformed JSON, verdict
    is 'error' and the caller treats every diff as in-scope (no reverts).
    A safety net that breaks the render on its own infra blip would be
    worse than no safety net at all.
    """
    diffs = compute_plan_diff(prior_plan, new_plan)
    if not diffs:
        return {
            "verdict": "no_changes",
            "diffs": [],
            "out_of_scope_paths": [],
            "reasoning": "no fields changed",
        }

    # Build compact diff summaries for the prompt — full JSON would blow
    # the context for plans with many edits. Each entry: path + op + brief.
    diff_lines = []
    for d in diffs:
        path = d["path"]
        op = d["op"]
        if op == "changed" and "old" in d and "new" in d:
            old_brief = json.dumps(d.get("old"), default=str)
            new_brief = json.dumps(d.get("new"), default=str)
            if len(old_brief) > 160:
                old_brief = old_brief[:157] + "..."
            if len(new_brief) > 160:
                new_brief = new_brief[:157] + "..."
            diff_lines.append(f"  • {path} CHANGED: {old_brief} → {new_brief}")
        elif op == "added":
            new_brief = json.dumps(d.get("new"), default=str)
            if len(new_brief) > 220:
                new_brief = new_brief[:217] + "..."
            diff_lines.append(f"  • {path} ADDED: {new_brief}")
        elif op == "removed":
            old_brief = json.dumps(d.get("old"), default=str)
            if len(old_brief) > 220:
                old_brief = old_brief[:217] + "..."
            diff_lines.append(f"  • {path} REMOVED: {old_brief}")
        elif op == "changed":
            # Unanchored list length change
            diff_lines.append(
                f"  • {path} list length {d.get('old_count')} → {d.get('new_count')}"
            )

    mode_rule = (
        "TWEAK mode contract: byte-identical-echo for every field the user "
        "did not address. Any non-derived change that isn't tied to the "
        "user's request is OUT-OF-SCOPE — even if it might be 'better.'\n"
        if mode == "tweak"
        else
        "GUIDED_REDRAFT mode contract: soft carry-over. Gemini may modify "
        "any decision that doesn't fit the user's new direction. Changes "
        "that PLAUSIBLY follow from the direction (even indirectly) are "
        "IN-SCOPE; only changes with NO connection to the direction are "
        "OUT-OF-SCOPE.\n"
    )

    prompt = (
        "You are auditing a video-edit re-edit. The user asked for a change; "
        "the system applied changes to the prior plan. Your job is to verify "
        "each applied change is justified by the user's request.\n\n"
        f"USER'S RE-EDIT REQUEST:\n{change_request}\n\n"
        f"EDIT MODE: {mode}\n\n"
        f"{mode_rule}\n"
        "APPLIED CHANGES (path · operation · brief):\n"
        + "\n".join(diff_lines)
        + "\n\n"
        "For each change, classify it. A 'clear consequence' counts as "
        "IN-SCOPE — e.g. if the user asked to remove a B-roll and the "
        "captions auto-shift position to fill the gap, that's a downstream "
        "consequence the renderer needs.\n\n"
        "Respond with a single JSON object:\n"
        "{\n"
        '  "paths_in_scope": [<exact path strings from the list above>],\n'
        '  "paths_out_of_scope": [<exact path strings from the list above>],\n'
        '  "reasoning": "1-2 sentences explaining the classification"\n'
        "}\n"
        "Use the EXACT path strings from the list above (including any "
        "[anchor=...] brackets). If you can't classify a change, put it in "
        "paths_in_scope (fail open — don't revert legit changes by mistake)."
    )

    try:
        client = _get_genai_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            print("[reedit-validate] Empty Gemini response (fail open)", flush=True)
            return {
                "verdict": "error",
                "diffs": diffs,
                "out_of_scope_paths": [],
                "reasoning": "validator returned empty response",
            }
        parsed = json.loads(text) if text.startswith("{") else extract_json(text)
        if not isinstance(parsed, dict):
            return {
                "verdict": "error",
                "diffs": diffs,
                "out_of_scope_paths": [],
                "reasoning": "validator response was not a JSON object",
            }
        oop_raw = parsed.get("paths_out_of_scope") or []
        oop_paths = [
            str(p) for p in oop_raw
            if isinstance(p, str) and p.strip()
        ]
        # Validate every reported out-of-scope path corresponds to a real
        # diff entry — Gemini sometimes hallucinates path strings.
        valid_paths = {d["path"] for d in diffs}
        oop_paths = [p for p in oop_paths if p in valid_paths]
        return {
            "verdict": "partial_out_of_scope" if oop_paths else "all_in_scope",
            "diffs": diffs,
            "out_of_scope_paths": oop_paths,
            "reasoning": str(parsed.get("reasoning") or "").strip()[:500],
        }
    except Exception as e:
        print(f"[reedit-validate] Gemini call failed: {e} (fail open)", flush=True)
        return {
            "verdict": "error",
            "diffs": diffs,
            "out_of_scope_paths": [],
            "reasoning": f"validator error: {type(e).__name__}",
        }


def _phase2_array_reverts_enabled():
    """Phase 2 array-level reverts are gated by env var so we can ship the
    code path without changing default behavior. Flip the switch via
    PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS=1 once production logs from
    Phase 1 confirm the scope classifier is accurate enough to trust on
    array entries (target: <2% misclassification rate on the
    'out_of_scope' verdict).

    Until then this returns False and apply_scalar_reverts is a pure
    Phase-1 implementation — exact same behavior as the original ship.
    """
    raw = os.environ.get("PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS", "") or ""
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _revert_array_entry(prior_list, new_list, anchor_fn, target_anchor):
    """Apply a single array-anchored revert in place on new_list.
    Returns "replaced" / "added_back" / "removed" / "noop" so the caller
    can log the exact action. Idempotent — calling twice produces the
    same end state."""
    if anchor_fn is None:
        return "noop"
    # Find old entry by anchor
    old_entry = None
    for e in prior_list:
        if anchor_fn(e) == target_anchor:
            old_entry = e
            break
    # Find new entry index by anchor
    new_idx = None
    for i, e in enumerate(new_list):
        if anchor_fn(e) == target_anchor:
            new_idx = i
            break
    if old_entry is not None and new_idx is not None:
        # Both present → replace new with old (the "changed" revert path)
        new_list[new_idx] = old_entry
        return "replaced"
    if old_entry is not None and new_idx is None:
        # Old had it, new dropped it → append old back. The renderer
        # iterates these arrays by anchor (word_index family), not by
        # position, so trailing insertion is semantically equivalent
        # to original placement for downstream consumers.
        new_list.append(old_entry)
        return "added_back"
    if old_entry is None and new_idx is not None:
        # Old didn't have it, new added it → drop the new entry.
        new_list.pop(new_idx)
        return "removed"
    return "noop"


def apply_scalar_reverts(prior_plan, new_plan, validation, mode):
    """Auto-revert out-of-scope changes flagged by the validator.

    Phase 1 (always on): top-level SCALAR fields in
        _PHASE1_REVERTABLE_SCALARS, tweak mode only. Array-level changes
        and guided_redraft changes are LOGGED but not reverted.

    Phase 2 (gated by PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS env var):
        Adds array-anchored reverts in tweak mode for any of the lists in
        _DIFF_LIST_ANCHORS. Off by default — flip the env var once
        production logs from Phase 1 show the scope classifier is
        accurate enough on array entries to trust automatic reverts
        (target: <2% misclassification rate).

    Auto-revert is engaged in TWEAK mode only across BOTH phases —
    guided_redraft's contract is soft carry-over (Gemini has documented
    latitude to modify consequentially); reverting there over-corrects.

    Returns the cleaned new_plan dict (shallow copy with reverts applied)
    or the original new_plan when no revert applies.
    """
    if validation.get("verdict") not in ("partial_out_of_scope",):
        return new_plan
    if mode != "tweak":
        # Log only — guided_redraft's soft-carry-over contract gives
        # Gemini documented latitude. Reverting here over-corrects.
        oop = validation.get("out_of_scope_paths") or []
        if oop:
            print(
                f"[reedit-validate] guided_redraft out-of-scope (LOGGED, "
                f"not reverted): {oop}",
                flush=True,
            )
        return new_plan

    phase2_on = _phase2_array_reverts_enabled()
    # Deep-copy lists we're going to mutate so we don't damage the
    # validator's reference data. Top-level scalars are reassigned by
    # value so shallow copy is enough for the outer dict.
    cleaned = dict(new_plan)
    reverted_scalars = []
    reverted_arrays = []
    skipped = []
    diff_by_path = {d["path"]: d for d in validation.get("diffs") or []}
    # Mutate lists we touch in a fresh copy — same identity discipline
    # the test suite relies on.
    _mutated_lists = {}

    for path in validation.get("out_of_scope_paths") or []:
        diff = diff_by_path.get(path)
        if not diff:
            continue
        # Scalar branch — handled in BOTH phases. Phase 1 and Phase 2 are
        # additive; the scalar revert path is unchanged.
        if diff.get("list_key") is None and diff.get("anchor") is None:
            if path not in _PHASE1_REVERTABLE_SCALARS:
                skipped.append(f"{path} (not in revertable scalars)")
                continue
            if path in prior_plan:
                cleaned[path] = prior_plan[path]
                reverted_scalars.append(path)
            elif path in cleaned:
                cleaned.pop(path)
                reverted_scalars.append(path)
            continue

        # Array branch — Phase 2 gated.
        list_key = diff.get("list_key")
        anchor = diff.get("anchor")
        # Unanchored list-level diff (length change with no anchor info) —
        # Phase 2 can't surgically revert this; would require re-emitting
        # the whole list. Log and skip in BOTH phases.
        if not list_key or anchor is None:
            skipped.append(f"{path} (unanchored list; cannot surgically revert)")
            continue
        # If Phase 2 is OFF, log + skip (preserves original Phase 1
        # behavior bit-for-bit).
        if not phase2_on:
            skipped.append(f"{path} (Phase 2 disabled)")
            continue
        anchor_fn = _DIFF_LIST_ANCHORS.get(list_key)
        if anchor_fn is None:
            skipped.append(f"{path} (no anchor function registered for {list_key!r})")
            continue
        prior_list = prior_plan.get(list_key) or []
        # Lazy deep-copy the list we're about to mutate. cleaned's outer
        # dict is shallow, so without this we'd mutate the caller's list
        # in place — bad citizenship + breaks test invariants.
        if list_key not in _mutated_lists:
            _mutated_lists[list_key] = [
                dict(e) if isinstance(e, dict) else e
                for e in (cleaned.get(list_key) or [])
            ]
            cleaned[list_key] = _mutated_lists[list_key]
        action = _revert_array_entry(
            prior_list=prior_list,
            new_list=_mutated_lists[list_key],
            anchor_fn=anchor_fn,
            target_anchor=anchor,
        )
        if action != "noop":
            reverted_arrays.append(f"{path} ({action})")
        else:
            skipped.append(f"{path} (no matching entry to revert)")

    if reverted_scalars:
        print(
            f"[reedit-validate] REVERTED out-of-scope scalars in tweak mode: "
            f"{reverted_scalars}. Reason: {validation.get('reasoning')!r}",
            flush=True,
        )
    if reverted_arrays:
        print(
            f"[reedit-validate] REVERTED out-of-scope array entries in tweak "
            f"mode (Phase 2): {reverted_arrays}. Reason: "
            f"{validation.get('reasoning')!r}",
            flush=True,
        )
    if skipped:
        print(
            f"[reedit-validate] SKIPPED (logged, not reverted): {skipped}",
            flush=True,
        )
    return cleaned


# ─── SFX HELPERS ─────────────────────────────────────────────────────────────

# LUFS-based SFX normalization — eliminates per-sound manual volume tuning.
# Instead of 29 hand-tuned volumes, we:
#   1. Measure each SFX file's RMS loudness once (cached)
#   2. Assign each sound to a MIX CATEGORY (3 levels, not 29)
#   3. Compute gain adjustment to hit the category's target level
#
# Mix categories (relative to voice at 0 dB):
#   "quiet"  — ambient/atmospheric sounds, sit well below voice (-20 dB)
#   "medium" — transitions, risers, UI sounds (-14 dB below voice)
#   "loud"   — impacts, punchy sounds (-10 dB below voice)
#
# Reference: ITU-R BS.1770-4 / EBU R128 for loudness normalization principles.

# Target mix levels as linear amplitude (10^(dB/20)):
# quiet=-20dB → 0.10, medium=-14dB → 0.20, loud=-10dB → 0.316
_SFX_CATEGORY_LEVELS = {
    "quiet":  0.10,
    "medium": 0.20,
    "loud":   0.316,
}

# Sound → category mapping. Adding a new SFX only requires placing it in
# one of 3 categories — no per-file volume calibration needed.
_SFX_CATEGORIES = {
    "boom": "loud",
    "camera_shutter": "medium",
    "ching": "loud",
    "click": "medium",
    "ding": "medium",
    "drum_roll": "medium",
    "hit": "loud",
    "pop": "medium",
    "reverse": "quiet",
    "sad_trombone": "medium",
    "transition_smooth": "quiet",
    "typing": "quiet",
    "whoosh_slow": "quiet",
    "thunder": "medium",
}

# Sound → onset offset (seconds). The "onset" is the time within the file
# at which the meaningful moment of the sound occurs (the impact, the climax,
# the perceived "hit"). When mixing, we schedule each SFX to start at
# (placement_time - onset) so the perceived moment lands EXACTLY on the word.
#
# For impact sounds (boom, hit, ching, ding, click, pop, camera_shutter), the
# onset is the peak amplitude.
#
# For build-up sounds (drum_roll, reverse, sad_trombone, thunder, whoosh_slow,
# transition_smooth), the onset is the climactic moment — the build PRECEDES
# the trigger word and the climax lands on it.
#
# Measured by decoding each file to PCM and finding the peak amplitude sample.
_SFX_ONSET_OFFSETS = {
    # Short impacts — offset to ATTACK (first audible transient on the word)
    "hit":               0.000,
    "ching":             0.000,
    "ding":              0.000,
    "click":             0.052,
    "pop":               0.013,
    "camera_shutter":    0.012,
    # Cinematic impacts — offset to PEAK (crash/hit lands on the word, buildup precedes)
    "boom":              0.440,
    "thunder":           0.734,
    # Build-up sounds — offset to CLIMAX (the payoff moment lands on the word)
    "drum_roll":         1.657,
    "reverse":           1.372,
    # sad_trombone is special: pre-rolling 1.29s makes the "wah wah waaah"
    # build start playing while the speaker is still mid-sentence, which
    # reads as accidental — a joke sound floating in over serious dialogue.
    # Anchor to the START of the descending phrase instead so it triggers
    # ON the word the editor picked, not 1.3s before.
    "sad_trombone":      0.000,
    # Atmospheric — offset to ONSET (first audible whoosh on the word)
    "transition_smooth": 0.089,
    "whoosh_slow":       0.034,
    # Continuous — no offset
    "typing":            0.000,
}

# RMS measurement cache — populated lazily, avoids re-measuring same file
_SFX_RMS_CACHE = {}
_SFX_TARGET_RMS = -18.0  # dBFS — reference level all SFX are normalized to


def _measure_sfx_rms(sfx_path):
    """Measure RMS loudness of an SFX file using ffmpeg astats. Cached."""
    if sfx_path in _SFX_RMS_CACHE:
        return _SFX_RMS_CACHE[sfx_path]
    cmd = [
        "ffmpeg", "-i", sfx_path, "-af",
        "astats=metadata=1:reset=0,ametadata=mode=print",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg SFX RMS measurement failed for {sfx_path}: {(result.stderr or '')[-300:]}")
    rms_matches = re.findall(
        r"lavfi\.astats\.Overall\.RMS_level=([-\d.]+)", result.stderr
    )
    if not rms_matches:
        raise RuntimeError(f"FFmpeg astats returned no RMS data for {sfx_path}")
    rms_db = float(rms_matches[-1])
    rms_db = max(-60.0, min(0.0, rms_db))
    _SFX_RMS_CACHE[sfx_path] = rms_db
    return rms_db

def normalize_sfx_style(style):
    """Return the canonical SFX name (lowercased, stripped) or "none".

    No aliasing — the Gemini prompt lists the exact 14 canonical names with
    descriptions, and the validator rejects anything outside that set. If
    Gemini emits "alert" or "heartbeat", the render fails with a clear
    error instead of silently mapping to an approximation.
    """
    key = str(style or "").strip().lower()
    if not key or key == "none":
        return "none"
    return key


def get_sfx_path(sound_name):
    normalized = normalize_sfx_style(sound_name)
    if normalized == "none":
        return None
    candidate = os.path.join(SFX_SOUNDS_DIR, f"{normalized}.mp3")
    if os.path.exists(candidate):
        return candidate
    print(f"[sfx] Sound file not found: {candidate}", flush=True)
    return None


def get_sfx_volume(sound_name, timestamp, speech_segments, is_text_overlay=False):
    """
    Compute SFX mix volume using LUFS-based normalization.

    Instead of hand-tuned per-sound volumes, we:
    1. Look up the sound's mix category (quiet/medium/loud)
    2. Measure the file's actual RMS (cached)
    3. Compute gain to normalize to reference level
    4. Apply category mix level
    5. Duck 6dB during speech (broadcast standard for under-bed audio)
    """
    normalized = normalize_sfx_style(sound_name)
    category = _SFX_CATEGORIES.get(normalized, "medium")
    category_level = _SFX_CATEGORY_LEVELS[category]

    # Measure actual file loudness and compute normalization gain
    sfx_path = get_sfx_path(sound_name)
    if sfx_path:
        measured_rms = _measure_sfx_rms(sfx_path)
        # Gain to bring SFX to reference level: 10^((target - measured) / 20)
        gain_db = _SFX_TARGET_RMS - measured_rms
        norm_gain = 10 ** (gain_db / 20.0)
    else:
        norm_gain = 1.0

    base = category_level * norm_gain

    # Duck during speech: -6dB (factor 0.5) per broadcast practice
    # Text overlays duck slightly less since they're meant to sync with text
    segs = speech_segments or []
    during_speech = any(
        float(seg.get("start") or 0) <= timestamp <= float(seg.get("end") or 0)
        for seg in segs
    )
    duck = 0.63 if (during_speech and is_text_overlay) else (0.50 if during_speech else 1.0)
    vol = base * duck
    return round(max(0.01, min(0.5, vol)), 3)


# ─── FFMPEG RENDER ────────────────────────────────────────────────────────────

def export_additional_format(output_path, aspect_ratio, dest_path):
    """Crop 9:16 output to '1:1' (1080x1080) or '16:9' (1920x1080)."""
    if aspect_ratio == "1:1":
        vf = "crop=1080:1080:0:(ih-1080)/2"
    elif aspect_ratio == "16:9":
        vf = "crop=1080:607:0:(ih-607)/2,scale=1920:1080"
    else:
        raise ValueError(f"Unsupported aspect_ratio: {aspect_ratio}")
    run_ffmpeg([
        "-y", "-i", output_path,
        "-vf", vf,
    ] + get_encode_args("high") + [
        "-c:a", "copy",
        # Tag color space explicitly. Without these, iOS AVPlayer
        # assumes sRGB and crushes Rec.709 luma — visible as washed-out
        # / dim playback on iPhone. Apple-recommended for VOD H.264.
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-color_range", "tv",
        # +negative_cts_offsets — signal B-frame reorder via negative CTS,
        # not via edit list (see the main composite encode for full rationale).
        "-movflags", "+faststart+negative_cts_offsets",
        dest_path,
    ])


def select_best_thumbnail_frame(video_path, seed_ts, work_dir):
    """Pick the visually best frame for a thumbnail by scanning a window around
    Gemini's recommended `seed_ts` and scoring each candidate on multiple
    objective visual quality metrics.

    NO post-processing whatsoever — the winning frame is extracted at full
    resolution from the video and saved as a high-quality JPEG, exactly as
    it appears in the rendered output.

    Scoring metrics (weights sum to 1.0):
      - Face DNN confidence (25%)            — is there a clearly detectable face?
      - Face area (capped) (10%)             — is the face large enough to fill?
      - Face centeredness (10%)              — is the face well-positioned?
      - Sharpness on face region (25%)       — Laplacian variance, penalizes motion blur
      - Brightness sweet-spot (15%)          — penalizes under/over-exposed faces
      - Eye openness (15%)                   — Haar cascade, 2 eyes detected = blinks penalized

    For videos with no detectable face (b-roll, landscape), falls back to
    sharpness + brightness only on the full frame.

    Returns (bytes, 'image/jpeg').
    """
    import cv2
    import numpy as np

    # ── Load detectors ──────────────────────────────────────────────────
    PROTOTXT = "/models/face_detector/deploy.prototxt"
    CAFFEMODEL = "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"
    _face_net = None
    if os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL):
        try:
            _face_net = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
        except Exception as _e:
            print(f"[thumbnail] WARNING: face DNN load failed: {_e}", flush=True)

    _eye_cascade = None
    try:
        _eye_xml = os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml")
        if os.path.exists(_eye_xml):
            _eye_cascade = cv2.CascadeClassifier(_eye_xml)
            if _eye_cascade.empty():
                _eye_cascade = None
    except Exception:
        _eye_cascade = None

    # Smile/expression cascade — lets the thumbnail picker prefer frames
    # where the speaker is mid-smile or mid-laugh over neutral frames at
    # the same sharpness. OpenCV ships haarcascade_smile.xml in the same
    # data/haarcascades directory as the eye cascade — no extra deps,
    # no model download. Cascade is tuned for forward-facing smiles, so
    # it's fast (<5ms per face region) and conservative (low false-
    # positive rate, occasional false-negatives on closed-mouth grins).
    _smile_cascade = None
    try:
        _smile_xml = os.path.join(cv2.data.haarcascades, "haarcascade_smile.xml")
        if os.path.exists(_smile_xml):
            _smile_cascade = cv2.CascadeClassifier(_smile_xml)
            if _smile_cascade.empty():
                _smile_cascade = None
    except Exception:
        _smile_cascade = None

    # ── Probe video duration ────────────────────────────────────────────
    _probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
        capture_output=True, text=True, timeout=5,
    )
    try:
        _streams = json.loads(_probe.stdout or "{}").get("streams", [])
        _vs = next((s for s in _streams if s.get("codec_type") == "video"), {})
        _duration = float(_vs.get("duration") or 0.0)
        if _duration <= 0:
            _duration = float(_vs.get("nb_frames", 0)) / float(eval(_vs.get("r_frame_rate", "30/1")))
    except Exception:
        _duration = 60.0

    # ── Compute scan window ─────────────────────────────────────────────
    # TIGHT window of ±0.6s around Gemini's seed. The user explicitly wants
    # the dramatic moment Gemini identified, not "any clean face frame nearby".
    # ±0.6s × 15 fps = ~18 candidates. That's enough density to skip a blink
    # frame or motion blur, but narrow enough that the picker can't drift to
    # a totally different sentence (which is what happened with ±2s — the
    # picker chose 32.41s "And" instead of 33.91s "Stelius?").
    _window = 0.6
    _window_start = max(0.05, seed_ts - _window)
    _window_end = min(max(0.1, _duration - 0.05), seed_ts + _window)
    if _window_end <= _window_start:
        _window_start = max(0.05, seed_ts - 0.3)
        _window_end = min(_duration - 0.05, seed_ts + 0.3)
    _window_dur = _window_end - _window_start
    _candidate_fps = 15.0  # 15 candidates per second within the narrow window

    # ── Extract candidates in ONE ffmpeg call ───────────────────────────
    # Use a moderate scoring resolution (540 wide for 9:16 = 540x960). This
    # gives the DNN plenty of pixels to detect faces accurately, the eye
    # cascade enough resolution for blink detection, and Laplacian a real
    # signal — while keeping decode + scoring under ~2 seconds total.
    _cand_dir = os.path.join(work_dir, "_thumb_candidates")
    os.makedirs(_cand_dir, exist_ok=True)
    # Clear any stale frames from prior jobs
    for _stale in glob.glob(os.path.join(_cand_dir, "*.jpg")):
        try:
            os.unlink(_stale)
        except Exception:
            pass

    _t_extract = time.time()
    _extract_cmd = subprocess.run(
        ["ffmpeg", "-y", "-v", "warning",
         "-ss", f"{_window_start:.3f}",
         "-t", f"{_window_dur:.3f}",
         "-i", video_path,
         "-vf", f"fps={_candidate_fps},scale=540:-2",
         "-q:v", "3",
         os.path.join(_cand_dir, "cand_%04d.jpg")],
        capture_output=True, text=True, timeout=15,
    )
    if _extract_cmd.returncode != 0:
        raise RuntimeError(f"[thumbnail] candidate extraction failed: {(_extract_cmd.stderr or '')[-300:]}")
    _t_extract = time.time() - _t_extract

    _cand_files = sorted(glob.glob(os.path.join(_cand_dir, "cand_*.jpg")))
    if not _cand_files:
        raise RuntimeError("[thumbnail] no candidate frames extracted")

    # ── Pass 1: Collect raw metrics for every candidate ─────────────────
    # We do TWO passes: first collect raw values, then normalize relatively.
    # Relative normalization means the SHARPEST frame in the window wins, the
    # LARGEST face wins, etc. — instead of a "good enough" threshold that
    # produces ties at 1.0 and arbitrary tiebreaking.
    _t_score = time.time()
    _raw = []  # list of dicts with raw per-candidate metrics

    for _ci, _cpath in enumerate(_cand_files):
        _cand_ts = _window_start + (_ci / _candidate_fps)

        _frame = cv2.imread(_cpath)
        if _frame is None:
            continue
        _h, _w = _frame.shape[:2]

        # Face detection
        _face_conf = 0.0
        _face_bbox = None
        if _face_net is not None:
            _blob = cv2.dnn.blobFromImage(
                cv2.resize(_frame, (300, 300)), 1.0, (300, 300),
                (104.0, 177.0, 123.0), swapRB=False, crop=False,
            )
            _face_net.setInput(_blob)
            _detections = _face_net.forward()
            for _di in range(_detections.shape[2]):
                _conf = float(_detections[0, 0, _di, 2])
                if _conf < 0.5:
                    continue
                _x1 = int(_detections[0, 0, _di, 3] * _w)
                _y1 = int(_detections[0, 0, _di, 4] * _h)
                _x2 = int(_detections[0, 0, _di, 5] * _w)
                _y2 = int(_detections[0, 0, _di, 6] * _h)
                _x1, _y1 = max(0, _x1), max(0, _y1)
                _x2, _y2 = min(_w, _x2), min(_h, _y2)
                if _x2 <= _x1 or _y2 <= _y1:
                    continue
                _area = (_x2 - _x1) * (_y2 - _y1)
                if _face_bbox is None or _area > ((_face_bbox[2] - _face_bbox[0]) * (_face_bbox[3] - _face_bbox[1])):
                    _face_conf = _conf
                    _face_bbox = (_x1, _y1, _x2, _y2)

        if _face_bbox is not None:
            _fx1, _fy1, _fx2, _fy2 = _face_bbox
            _face_region = _frame[_fy1:_fy2, _fx1:_fx2]
            _face_gray = cv2.cvtColor(_face_region, cv2.COLOR_BGR2GRAY)

            _face_area = (_fx2 - _fx1) * (_fy2 - _fy1)
            _frame_area = _w * _h
            _area_ratio = _face_area / _frame_area

            _face_cx = (_fx1 + _fx2) / 2
            _face_cy = (_fy1 + _fy2) / 2
            _frame_cx = _w / 2
            _frame_cy = _h / 2
            _max_dist = ((_w / 2) ** 2 + (_h / 2) ** 2) ** 0.5
            _dist = ((_face_cx - _frame_cx) ** 2 + (_face_cy - _frame_cy) ** 2) ** 0.5
            _center_score = max(0.0, 1.0 - (_dist / _max_dist))

            _lap_var = float(cv2.Laplacian(_face_gray, cv2.CV_64F).var())
            _mean_lum = float(_face_gray.mean())

            # Eye detection: 2 eyes = open, 1 = partial, 0 = blink
            _eye_score = 0.7  # neutral default if cascade unavailable
            if _eye_cascade is not None and _face_gray.size > 0:
                _eyes = _eye_cascade.detectMultiScale(
                    _face_gray, scaleFactor=1.1, minNeighbors=5,
                    minSize=(int((_fx2 - _fx1) * 0.1), int((_fy2 - _fy1) * 0.05)),
                )
                _n_eyes = len(_eyes)
                if _n_eyes >= 2:
                    _eye_score = 1.0
                elif _n_eyes == 1:
                    _eye_score = 0.55
                else:
                    _eye_score = 0.15

            # Smile / expression detection — runs on the bottom half of the
            # face region (mouth area) for speed and tighter accuracy. A
            # frame where the speaker is smiling or laughing is a stronger
            # thumbnail than the same person mid-syllable with a neutral
            # mouth. We score it as a [0, 1] continuous signal weighted by
            # detection count: any detection = 0.7 (baseline smile), two+
            # = 1.0 (strong smile, often laughing), zero = 0.4 (neutral —
            # not penalized to zero because most talking-head frames are
            # mid-speech and shouldn't be punished, just out-prioritized
            # by frames with visible joy).
            _smile_score = 0.4
            if _smile_cascade is not None and _face_gray.size > 0:
                _mouth_y_start = (_fy2 - _fy1) // 2
                _mouth_region = _face_gray[_mouth_y_start:, :]
                if _mouth_region.size > 0:
                    _smiles = _smile_cascade.detectMultiScale(
                        _mouth_region,
                        scaleFactor=1.7,
                        minNeighbors=22,
                        minSize=(int((_fx2 - _fx1) * 0.25), int((_fy2 - _fy1) * 0.10)),
                    )
                    _n_smiles = len(_smiles)
                    if _n_smiles >= 2:
                        _smile_score = 1.0
                    elif _n_smiles == 1:
                        _smile_score = 0.7

            _raw.append({
                "ts": _cand_ts,
                "has_face": True,
                "face_conf": _face_conf,
                "area_ratio": _area_ratio,
                "center": _center_score,
                "lap_var": _lap_var,
                "mean_lum": _mean_lum,
                "eye_score": _eye_score,
                "smile_score": _smile_score,
            })
        else:
            _gray = cv2.cvtColor(_frame, cv2.COLOR_BGR2GRAY)
            _lap_var = float(cv2.Laplacian(_gray, cv2.CV_64F).var())
            _mean_lum = float(_gray.mean())
            _raw.append({
                "ts": _cand_ts,
                "has_face": False,
                "lap_var": _lap_var,
                "mean_lum": _mean_lum,
            })

    if not _raw:
        raise RuntimeError("[thumbnail] no scorable candidates")

    # ── Pass 2: Normalize relatively + score ────────────────────────────
    # Sharpness and face area are normalized against the BEST candidate in
    # the window so the sharpest/largest-face frame gets 1.0 and others get
    # proportional credit. This eliminates the "many candidates tie at 1.0"
    # problem caused by absolute thresholds.
    _face_candidates = [r for r in _raw if r["has_face"]]
    _max_lap = max((r["lap_var"] for r in _raw), default=1.0) or 1.0
    _max_area = max((r["area_ratio"] for r in _face_candidates), default=0.15) or 0.15

    def _brightness_score(_lum):
        # Tighter sweet-spot: peak at 130, falls off symmetrically
        if _lum < 40 or _lum > 220:
            return 0.0
        if 110 <= _lum <= 160:
            return 1.0
        if _lum < 110:
            return max(0.0, (_lum - 40) / 70)
        return max(0.0, (220 - _lum) / 60)

    _scored = []  # list of (score, ts, breakdown)
    for _r in _raw:
        if _r["has_face"]:
            _conf_score = (_r["face_conf"] - 0.5) / 0.5  # [0.5,1] → [0,1]
            _area_score = min(_r["area_ratio"] / _max_area, 1.0)
            _sharp_score = min(_r["lap_var"] / _max_lap, 1.0)
            _bright_score = _brightness_score(_r["mean_lum"])

            # Seed proximity is HEAVILY weighted: Gemini chose this exact
            # timestamp for narrative reasons. We only deviate to skip frames
            # with objective failure modes (blinks, motion blur, bad lighting).
            # Distance from seed in seconds → score in [0, 1].
            _seed_dist = abs(_r["ts"] - seed_ts)
            _proximity = max(0.0, 1.0 - _seed_dist / _window)

            # Smile factors in at 10% — enough to break ties between equally-
            # sharp frames in favor of the one with visible expression, but
            # not enough to override fundamentals (sharpness, eyes-open,
            # framing). Proximity drops 0.25 → 0.20 to make room without
            # dethroning Gemini's seed timestamp.
            _smile_score = float(_r.get("smile_score", 0.4))
            _total = (
                0.10 * _conf_score
                + 0.10 * _area_score
                + 0.05 * _r["center"]
                + 0.20 * _sharp_score
                + 0.05 * _bright_score
                + 0.20 * _r["eye_score"]
                + 0.10 * _smile_score
                + 0.20 * _proximity
            )
            _breakdown = {
                "has_face": True,
                "conf": _conf_score, "area": _area_score, "center": _r["center"],
                "sharp": _sharp_score, "bright": _bright_score, "eye": _r["eye_score"],
                "smile": _smile_score,
                "proximity": _proximity,
                "lap_var": _r["lap_var"], "mean_lum": _r["mean_lum"],
                "face_conf": _r["face_conf"],
            }
        else:
            # No face — use sharpness + brightness on full frame.
            # Capped at 0.5 so any face-frame still wins when available.
            _sharp_score = min(_r["lap_var"] / _max_lap, 1.0)
            _bright_score = _brightness_score(_r["mean_lum"])
            _total = 0.5 * (0.6 * _sharp_score + 0.4 * _bright_score)
            _breakdown = {
                "has_face": False, "sharp": _sharp_score, "bright": _bright_score,
                "lap_var": _r["lap_var"], "mean_lum": _r["mean_lum"],
            }
        _scored.append((_total, _r["ts"], _breakdown))

    _t_score = time.time() - _t_score

    # Sort by score descending, pick winner
    _scored.sort(key=lambda r: -r[0])
    _winner_score, _winner_ts, _winner_breakdown = _scored[0]

    # Cleanup candidate frames
    for _f in _cand_files:
        try:
            os.unlink(_f)
        except Exception:
            pass
    try:
        os.rmdir(_cand_dir)
    except Exception:
        pass

    # ── Re-extract winning frame at FULL resolution ─────────────────────
    # The candidate scoring used 540p; the actual thumbnail must be the full
    # 1080x1920 frame from the video. NO post-processing applied.
    _final_path = os.path.join(work_dir, "thumbnail_final.jpg")
    _t_final = time.time()
    _final_cmd = subprocess.run(
        ["ffmpeg", "-y", "-v", "warning",
         "-ss", f"{_winner_ts:.3f}",
         "-i", video_path,
         "-frames:v", "1",
         "-q:v", "2",  # JPEG quality scale 2 = ~95%
         _final_path],
        capture_output=True, text=True, timeout=10,
    )
    _t_final = time.time() - _t_final
    if _final_cmd.returncode != 0 or not os.path.exists(_final_path):
        raise RuntimeError(f"[thumbnail] final frame extract failed: {(_final_cmd.stderr or '')[-300:]}")

    with open(_final_path, "rb") as f:
        _data = f.read()
    try:
        os.unlink(_final_path)
    except Exception:
        pass

    _has_face = _winner_breakdown.get("has_face", False)
    print(
        f"[thumbnail] Selected best frame at {_winner_ts:.3f}s "
        f"(seed={seed_ts:.2f}s, window=±{_window:.1f}s, {len(_scored)} candidates) "
        f"score={_winner_score:.3f} face={_has_face} "
        f"extract={_t_extract:.2f}s score={_t_score:.2f}s final={_t_final:.2f}s",
        flush=True,
    )
    if _has_face:
        print(
            f"[thumbnail]   metrics: conf={_winner_breakdown['conf']:.2f} "
            f"area={_winner_breakdown['area']:.2f} center={_winner_breakdown['center']:.2f} "
            f"sharp={_winner_breakdown['sharp']:.2f}(lap={_winner_breakdown['lap_var']:.0f}) "
            f"bright={_winner_breakdown['bright']:.2f}(lum={_winner_breakdown['mean_lum']:.0f}) "
            f"eye={_winner_breakdown['eye']:.2f} "
            f"smile={_winner_breakdown.get('smile', 0):.2f} "
            f"prox={_winner_breakdown['proximity']:.2f}",
            flush=True,
        )
        # Log top 3 candidates for debugging — helps diagnose unexpected picks
        for _idx, (_s, _ts, _b) in enumerate(_scored[:3]):
            if _b.get("has_face"):
                print(
                    f"[thumbnail]   #{_idx+1} t={_ts:.3f}s score={_s:.3f} "
                    f"sharp={_b['sharp']:.2f} bright={_b['bright']:.2f} "
                    f"eye={_b['eye']:.2f} smile={_b.get('smile', 0):.2f} "
                    f"prox={_b['proximity']:.2f}",
                    flush=True,
                )

    return _data, "image/jpeg"


def fetch_broll_clip(broll_entry, duration_needed, work_dir, dialogue_reason="", dialogue_text=""):
    """Resolve a B-roll clip entry to a local file path.

    broll_entry is the dict from edit_plan.broll_clips[]. If it already carries
    pexels_file_url + pexels_video_id from a prior render, this function skips
    the Pexels search + Gemini visual pick and downloads that EXACT asset — the
    "flawless preservation" path for re-edits.

    On a fresh pick, the function mutates broll_entry in place with
    pexels_video_id, pexels_file_url, width, height, and duration so the caller
    can persist the resolved asset in video_jobs.resolved_broll.

    Returns a local path on success, or None on skip / failure.
    """
    keyword = (broll_entry.get("keyword") or "").strip() if isinstance(broll_entry, dict) else ""
    if not keyword:
        print("[broll] Missing keyword on broll_entry — skipping", flush=True)
        return None

    # ── Pre-resolved path (re-edit): use the exact clip chosen last time.
    pre_url = broll_entry.get("pexels_file_url")
    pre_id = broll_entry.get("pexels_video_id")
    if pre_url and pre_id:
        print(f"[broll] Re-using pre-resolved clip for '{keyword}': pexels_id={pre_id}", flush=True)
        return _download_and_validate_broll(
            chosen_url=pre_url,
            keyword=keyword,
            work_dir=work_dir,
            broll_entry=broll_entry,
            chosen_video_id=pre_id,
        )

    pexels_key = os.environ.get("PEXELS_API_KEY")
    if not pexels_key:
        print(f"[broll] PEXELS_API_KEY not set — skipping '{keyword}'", flush=True)
        return None

    _pexels_headers = {"Authorization": pexels_key}
    _pexels_base_params = {"per_page": 15, "orientation": "portrait", "size": "large"}

    # Two-phase search: full keyword + short verb-focused query in parallel
    # Pexels search is noun-based — a short verb query surfaces different clips
    _kw_short_words = [w for w in keyword.lower().split() if len(w) > 3 and w not in {"with", "from", "into", "close", "looking", "fast"}][:5]
    _kw_short = " ".join(_kw_short_words) if len(_kw_short_words) >= 3 else ""

    def _search_pexels(query):
        try:
            _r = requests.get(
                "https://api.pexels.com/videos/search",
                headers=_pexels_headers,
                params={**_pexels_base_params, "query": query},
                timeout=25,
            )
            _r.raise_for_status()
            return _r.json().get("videos") or []
        except Exception:
            return []

    # Run both searches in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as _search_pool:
        _fut_main = _search_pool.submit(_search_pexels, keyword)
        _fut_short = _search_pool.submit(_search_pexels, _kw_short) if _kw_short else None
        videos = _fut_main.result()
        _short_videos = _fut_short.result() if _fut_short else []

    # Merge results — deduplicate by video ID, main results first
    _seen_ids = {v.get("id") for v in videos}
    for _sv in _short_videos:
        if _sv.get("id") not in _seen_ids:
            videos.append(_sv)
            _seen_ids.add(_sv.get("id"))

    if not videos:
        print(f"[broll] No Pexels results for '{keyword}'", flush=True)
        return None

    _search_note = f" (+{len(_short_videos)} from short query '{_kw_short}')" if _short_videos else ""
    print(f"[broll] Pexels returned {len(videos)} results for '{keyword}'{_search_note}", flush=True)

    # Extract key words from the keyword for tag/URL matching
    _kw_words = set(keyword.lower().split())
    _stop_words = {"a", "an", "the", "in", "on", "of", "with", "and", "to", "for", "up", "at", "by", "from", "into", "is", "it", "close"}
    _kw_match_words = _kw_words - _stop_words

    _candidates = []
    for vid_idx, video in enumerate(videos):
        vid_dur = float(video.get("duration") or 0)
        vid_id = video.get("id", "unknown")
        video_files = video.get("video_files") or []

        portrait_files = []
        for f in video_files:
            h = f.get("height") or 0
            w = f.get("width") or 0
            link = f.get("link") or ""
            file_type = f.get("file_type") or ""

            if h <= w:
                continue
            if not link:
                continue
            if h < 720:
                continue
            if file_type and "image" in file_type.lower():
                continue
            if file_type and "video" not in file_type.lower() and file_type != "":
                continue

            portrait_files.append({"link": link, "height": h, "width": w, "file_type": file_type})

        if not portrait_files:
            continue

        portrait_files.sort(key=lambda x: abs(x["height"] - 1920))
        best_file = portrait_files[0]

        score = 0
        if vid_dur >= duration_needed:
            score += 10
        elif vid_dur >= duration_needed * 0.7:
            score += 5
        if best_file["height"] >= 1920:
            score += 5
        elif best_file["height"] >= 1080:
            score += 3
        score += max(0, 10 - vid_idx)

        _vid_url = str(video.get("url") or "").lower()
        _vid_url_words = set(re.split(r'[-/]', _vid_url.split("pexels.com/")[-1] if "pexels.com/" in _vid_url else ""))
        _vid_tags = set()
        for _tag_obj in (video.get("tags") or []):
            if isinstance(_tag_obj, dict):
                _vid_tags.update(_tag_obj.get("name", "").lower().split())
            elif isinstance(_tag_obj, str):
                _vid_tags.update(_tag_obj.lower().split())
        _all_vid_words = _vid_tags | _vid_url_words
        if _all_vid_words and _kw_match_words:
            _tag_matches = len(_kw_match_words & _all_vid_words)
            # Tag-string-match is a USEFUL WEAK SIGNAL — kept positive so
            # tag-aligned candidates rise above tag-mismatched ones — but
            # weighted DOWN from *10 to *4 (2026-06-14). At *10 a bad
            # keyword's lexical surface would dominate the pre-pick rank:
            # "person typing text message" rocketed every texting-clip
            # candidate to the top 5 because each clip's tags hit
            # 4-5 of those words. The Gemini visual pick then had a
            # candidate set already biased toward the wrong content.
            # At *4 the duration/resolution/Pexels-rank signals stay
            # comparable to tag-match magnitude, so the visual pick
            # (which sees the actual thumbnails AND the dialogue line)
            # has more authority over a string match.
            score += _tag_matches * 4
        elif _kw_match_words:
            score -= 15

        _poster_url = str(video.get("image") or "")
        _slug = _vid_url.split("pexels.com/")[-1] if "pexels.com/" in _vid_url else ""
        _slug_desc = " ".join(w for w in re.split(r'[-/]', _slug) if w and not w.isdigit() and w != "video")
        # Get video_pictures for multi-frame evaluation (start, middle, end)
        _vid_pics = [str(p.get("picture") or "") for p in (video.get("video_pictures") or []) if p.get("picture")]
        _frame_urls = []
        if len(_vid_pics) >= 3:
            _frame_urls = [_vid_pics[0], _vid_pics[len(_vid_pics)//2], _vid_pics[-1]]
        elif _vid_pics:
            _frame_urls = _vid_pics[:3]
        if not _frame_urls and _poster_url:
            _frame_urls = [_poster_url]

        _candidates.append({
            "video_id": vid_id,
            "video_idx": vid_idx,
            "duration": vid_dur,
            "file": best_file,
            "score": score,
            "poster_url": _poster_url,
            "slug_desc": _slug_desc,
            "frame_urls": _frame_urls,
        })

    # Gemini visual pick — fetch multiple frames per candidate (start/mid/end),
    # let Gemini see the ACTION across time and pick the best match.
    if _candidates and _kw_match_words:
        _candidates.sort(key=lambda x: x["score"], reverse=True)
        _top_n = _candidates[:5]
        _candidate_frames = {}  # idx → list of image bytes

        # Fetch all frame URLs in parallel (~5KB each, <300ms total)
        def _fetch_img(idx_url):
            _idx, _url = idx_url
            if not _url:
                return _idx, None
            try:
                _r = requests.get(_url, timeout=5)
                if _r.status_code == 200 and len(_r.content) > 500:
                    return _idx, _r.content
            except Exception:
                pass
            return _idx, None

        _fetch_tasks = []
        for i, c in enumerate(_top_n):
            for _furl in c.get("frame_urls", []):
                _fetch_tasks.append((i, _furl))

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as _frame_pool:
            _frame_futs = [_frame_pool.submit(_fetch_img, t) for t in _fetch_tasks]
            for _fut in concurrent.futures.as_completed(_frame_futs, timeout=5):
                try:
                    _fi, _fdata = _fut.result()
                    if _fdata:
                        _candidate_frames.setdefault(_fi, []).append(_fdata)
                except Exception:
                    pass

        if _candidate_frames and len(_candidate_frames) >= 2:
            _pick_client = _get_genai_client()
            _spoken = (dialogue_text or "").strip()
            _note = (dialogue_reason or "").strip()
            _content_parts = []
            _poster_idx_map = {}
            _num = 1
            for _ci in sorted(_candidate_frames.keys()):
                _desc = _top_n[_ci].get("slug_desc", "")
                _n_frames = len(_candidate_frames[_ci])
                _frame_label = f"({_n_frames} frames from this clip)" if _n_frames > 1 else ""
                _content_parts.append(f"\nOption {_num} — \"{_desc}\" {_frame_label}:")
                for _frame_bytes in _candidate_frames[_ci][:3]:
                    _content_parts.append(genai_types.Part.from_bytes(
                        data=_frame_bytes, mime_type="image/jpeg"
                    ))
                _poster_idx_map[_num] = _ci
                _num += 1
            _ctx_lines = []
            if _spoken:
                _ctx_lines.append(f'The viewer hears these exact words: "{_spoken}"')
            else:
                _ctx_lines.append(f'Search context: "{keyword}"')
            if _note and _note.lower() != _spoken.lower():
                _ctx_lines.append(f'Required content for this cutaway: "{_note}"')
            _ctx_block = "\n" + "\n".join(_ctx_lines) + "\n"
            _instruction_base = (
                "Which clip would feel most natural playing on screen while the viewer hears those exact words? "
                "Two different judgment rules apply depending on what the dialogue is doing. "
                "(A) NARRATIVE / ABSTRACT dialogue — the speaker describes a feeling, scene, story beat, or approach with no specific on-screen referent. "
                "B-roll doesn't need to show the exact scene; pick the clip whose character and mood visually connect to what's being said. "
                "BUT if the context above includes 'Required content for this cutaway', that note is a CONTENT REQUIREMENT — a clip that visually violates it ('must show X, not Y' and the clip shows Y) is the wrong pick regardless of mood fit. Mood-matching is only allowed AMONG candidates that satisfy the content requirement. "
                "(B) APP-INPUT / DEMO dialogue — the dialogue names a specific app action the viewer must literally SEE: typing INTO an app, uploading, tapping, selecting, a result appearing on a screen "
                "(\"type in the vibe,\" \"upload your video,\" \"tap the button,\" \"every edit shows up here\"). "
                "Here the clip must show the SCREEN or APP doing that action — a screen recording, a phone UI close-up, the app interface itself. "
                "A person at a keyboard, a person texting on a phone, or hands typing on a device shows the WRONG thing for app-input dialogue and should be rejected — those depict a human typing, not the app receiving input. "
                "If no option shows the actual app/screen action the dialogue names, answer NONE — the speaker's face is the correct fallback for that window. "
                "Apply the editorial test to the strongest candidate: would a real editor place THIS clip for this exact moment, or does it just happen to CONTAIN a noun from the search (a hand, a desk, a screen) while being about something unrelated to what the speaker is actually discussing? A clip that shares a surface object with the words but doesn't fit the SUBJECT of the moment (e.g. a tattooed hand on an antique occult book when the speaker is pitching an AI video editor) is a coincidental noun-match, NOT a fit — answer NONE. A relevant ABSENCE (the speaker's face) always beats a nonsense cutaway. Reply with ONLY the option number. "
                "NONE if every option is unrelated to the actual words being spoken OR only surface-matches a noun without fitting the subject of the moment OR every option violates the content requirement OR (for app-input dialogue) no option shows the app screen."
            )
            _instruction_strict = (
                _instruction_base
                + " CRITICAL FORMAT: respond with a single digit only — "
                  + ", ".join(f"'{i}'" for i in range(1, len(_poster_idx_map) + 1))
                  + ", or 'NONE'. No words, no labels, no explanation, no formatting. Just the digit or 'NONE'."
            )

            def _parse_pick(text):
                """Returns one of ('NONE', None) / ('PICKED', valid_num) /
                ('MALFORMED', None). Valid means the digit maps to an
                actual option in _poster_idx_map."""
                if "NONE" in text:
                    return ("NONE", None)
                for _ch in text:
                    if _ch.isdigit():
                        _n = int(_ch)
                        if _n in _poster_idx_map:
                            return ("PICKED", _n)
                        return ("MALFORMED", None)
                return ("MALFORMED", None)

            def _attempt_pick(instruction):
                """Single Gemini call + parse. Returns
                (status, num, raw_text_or_error, elapsed_s).
                On API exception returns ('ERROR', None, str(err), elapsed)."""
                _parts = list(_content_parts) + [_ctx_block + instruction]
                _t0 = time.time()
                try:
                    _resp = _pick_client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=_parts,
                        config=genai_types.GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=128,
                            # Raised 32 → 256: the Rule-A BUT clause requires
                            # a 5-step structured filter (locate the Required-
                            # content line → parse must-show-X-not-Y → check
                            # each candidate's frames → disqualify violators
                            # → mood-match among survivors), and 32 tokens
                            # can't execute that. Model defaulted to first-
                            # pass vibe match, picked content-violating clips
                            # (e.g. "female editor posing on camera" for a
                            # "must show editing software timeline" reason).
                            # 256 is a diagnostic floor: if it resolves the
                            # violations, the task needed only modest
                            # reasoning headroom; if it doesn't, the signal
                            # points beyond budget and we look elsewhere.
                            # Cost: ~5 picks/video × ~256 thinking tokens =
                            # ~1.3K extra per render — negligible against
                            # the 60K editorial call.
                            thinking_config=genai_types.ThinkingConfig(thinking_budget=256),
                        ),
                    )
                except Exception as _e:
                    return ("ERROR", None, str(_e), time.time() - _t0)
                _text = str(getattr(_resp, "text", "") or "").strip().upper()
                _status, _num_or_none = _parse_pick(_text)
                return (_status, _num_or_none, _text, time.time() - _t0)

            # First attempt — standard instruction.
            # Part C: the FIRST call uses the strict bare-digit/NONE format too,
            # so a malformed first response (e.g. the word "OPTION" with no
            # digit) isn't a near-miss that wastes a re-ask round-trip.
            _status1, _num1, _raw1, _elapsed1 = _attempt_pick(_instruction_strict)
            _pick_text = _raw1  # preserve for downstream log compatibility

            if _status1 == "NONE":
                print(
                    f"[broll] Gemini visual pick: NONE matched in {_elapsed1:.1f}s "
                    f"for '{keyword}' — skipping (no fallback)",
                    flush=True,
                )
                return None
            elif _status1 == "PICKED":
                _winner_idx = _poster_idx_map[_num1]
                _top_n[_winner_idx]["score"] += 50
                print(
                    f"[broll] Gemini visual pick: #{_num1} "
                    f"('{_top_n[_winner_idx].get('slug_desc','')}') in "
                    f"{_elapsed1:.1f}s for '{keyword}'",
                    flush=True,
                )
            else:
                # MALFORMED or ERROR on first attempt — re-issue with strict
                # format instruction. Do NOT fall through to score-rank: a
                # broken picker response is not a signal to trust the score.
                _why1 = "MALFORMED" if _status1 == "MALFORMED" else f"ERROR ({_raw1})"
                print(
                    f"[broll] Gemini visual pick: {_why1} response='{_raw1[:80]}' "
                    f"in {_elapsed1:.1f}s for '{keyword}' — re-issuing with strict format",
                    flush=True,
                )
                _status2, _num2, _raw2, _elapsed2 = _attempt_pick(_instruction_strict)

                if _status2 == "NONE":
                    print(
                        f"[broll] Gemini visual pick (strict re-pick): NONE matched in "
                        f"{_elapsed2:.1f}s for '{keyword}' — skipping",
                        flush=True,
                    )
                    return None
                elif _status2 == "PICKED":
                    _winner_idx = _poster_idx_map[_num2]
                    _top_n[_winner_idx]["score"] += 50
                    print(
                        f"[broll] Gemini visual pick (strict re-pick): #{_num2} "
                        f"('{_top_n[_winner_idx].get('slug_desc','')}') in "
                        f"{_elapsed2:.1f}s for '{keyword}'",
                        flush=True,
                    )
                else:
                    # Still malformed/errored after a strict re-pick. The
                    # picker is genuinely failing on this candidate set.
                    # Fall back to FACE (return None) rather than a
                    # score-ranked stock clip — per the principle established
                    # earlier this session, a weak/uncertain cutaway is
                    # strictly worse than no cutaway.
                    _why2 = "MALFORMED" if _status2 == "MALFORMED" else f"ERROR ({_raw2})"
                    print(
                        f"[broll] Gemini visual pick (strict re-pick): {_why2} "
                        f"response='{_raw2[:80]}' for '{keyword}' — "
                        f"dropping cutaway, falling back to face",
                        flush=True,
                    )
                    _record_divergence(
                        "broll",
                        {
                            "keyword": keyword,
                            "picker_response_first": _raw1[:200],
                            "picker_response_retry": _raw2[:200],
                            "first_status": _status1,
                            "retry_status": _status2,
                        },
                        "drop_face_fallback",
                        reason="visual_pick_malformed_after_retry",
                    )
                    return None

        _candidates = _top_n + _candidates[5:]

    best_match = None
    best_score = -1
    for _c in _candidates:
        if _c["score"] > best_score:
            best_match = _c
            best_score = _c["score"]

    if not best_match:
        print(f"[broll] No portrait video files found across {len(videos)} results for '{keyword}' — SKIPPING", flush=True)
        return None

    # ── Match-score floor ─────────────────────────────────────────────
    # Generic/vague stock that doesn't match the dialogue is the #1
    # amateur tell. The parallel two-phase search above already runs the
    # original keyword AND a 4-5-content-word short variant in parallel
    # (handler.py:~8348-8371) — so the candidate pool already reflects a
    # re-query with the strongest content words. If the best candidate
    # STILL scores below the floor, no further re-query will help: the
    # keyword as constructed doesn't have a matching stock asset in
    # Pexels. Drop the cutaway — the face is a fine default for that
    # window. A weak/wrong cutaway is strictly worse than no cutaway.
    #
    # NOTE: a Gemini-picked winner already carries a flat +50 bonus (added
    # above), so best_score = raw_text_match + 50. A floor of 50 could never
    # reject a pick (always ≥50); 60 requires a real text-match of ≥10 ON TOP
    # of the bonus, dropping near-zero-relevance picks. This is only a
    # structural backstop — the REAL relevance gate is the picker's NONE
    # judgment (the editorial surface-match test in the instruction above),
    # because raw text-match can't tell an editorially-apt "hand on desk" from
    # a nonsense one. Kept modest (60) to avoid over-rejecting.
    _BROLL_MATCH_FLOOR = 60
    if best_score < _BROLL_MATCH_FLOOR:
        print(
            f"[broll] DROP '{keyword}': best score {best_score} < floor "
            f"{_BROLL_MATCH_FLOOR}; falling back to speaker for that window",
            flush=True,
        )
        _record_divergence(
            "broll",
            {
                "keyword": keyword,
                "best_score": int(best_score),
                "n_candidates": len(_candidates),
                "floor": _BROLL_MATCH_FLOOR,
            },
            "drop",
            final=None,
            reason="below_match_score_floor",
        )
        return None

    chosen_file = best_match["file"]
    chosen_url = chosen_file["link"]
    if not chosen_url:
        print(f"[broll] No usable file for '{keyword}'", flush=True)
        return None

    print(
        f"[broll] Selected '{keyword}': pexels_id={best_match['video_id']}, "
        f"result #{best_match['video_idx']+1}/{len(videos)}, "
        f"{chosen_file['width']}x{chosen_file['height']}, "
        f"type={chosen_file['file_type']}, "
        f"duration={best_match['duration']:.1f}s, "
        f"score={best_match['score']}",
        flush=True,
    )

    return _download_and_validate_broll(
        chosen_url=chosen_url,
        keyword=keyword,
        work_dir=work_dir,
        broll_entry=broll_entry,
        chosen_video_id=best_match["video_id"],
    )


def _download_and_validate_broll(chosen_url, keyword, work_dir, broll_entry=None, chosen_video_id=None):
    """Download + validate a single B-roll file. Shared by fresh picks and
    pre-resolved re-edit replays. Mutates broll_entry (if provided) with the
    resolved asset metadata so callers can persist it."""
    # Filename = first 30 alphanum chars (human-readable hint) + 8-char MD5
    # of the FULL keyword (collision guard). The :30 prefix can collide for
    # keywords that share a long common prefix ("person walking through
    # hallway alone in fog" vs "...with rain"); the hash makes distinct
    # keywords always produce distinct filenames, eliminating both the
    # silent-overwrite case AND the parallel-fetch race-corruption case
    # (broll fetches run in a thread pool — concurrent writes to the same
    # file would interleave bytes from two downloads).
    safe_kw = re.sub(r"[^a-z0-9]", "_", keyword.lower())[:30] if keyword else "broll"
    kw_hash = hashlib.md5((keyword or "noop").encode("utf-8")).hexdigest()[:8]
    dest = os.path.join(work_dir, f"broll_{safe_kw}_{kw_hash}.mp4")

    try:
        dl = requests.get(chosen_url, stream=True, timeout=30)
        dl.raise_for_status()
    except Exception as _e:
        print(f"[broll] Download error for '{keyword}': {_e}", flush=True)
        return None

    content_type = dl.headers.get("content-type", "")
    if "image" in content_type.lower():
        print(f"[broll] REJECTED '{keyword}': download returned image content-type ({content_type})", flush=True)
        return None

    _MAX_BROLL_BYTES = 30 * 1024 * 1024  # 30MB cap — was silently dropping otherwise-good Pexels picks at the boundary
    with open(dest, "wb") as f:
        total_bytes = 0
        for chunk in dl.iter_content(65536):
            f.write(chunk)
            total_bytes += len(chunk)
            if total_bytes > _MAX_BROLL_BYTES:
                break

    if total_bytes > _MAX_BROLL_BYTES:
        print(f"[broll] SKIPPED '{keyword}': file too large ({total_bytes / 1024 / 1024:.1f}MB > 30MB cap)", flush=True)
        try:
            os.remove(dest)
        except OSError:
            pass
        return None

    print(f"[broll] Downloaded '{keyword}': {total_bytes / 1024:.0f}KB -> {dest}", flush=True)

    # ── Validate downloaded clip ──────────────────────────────────────────
    probe_data = _probe_full(dest)

    video_stream = None
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        print(f"[broll] REJECTED '{keyword}': no video stream found", flush=True)
        os.remove(dest)
        return None

    stream_w = int(video_stream.get("width", 0) or 0)
    stream_h = int(video_stream.get("height", 0) or 0)
    codec_name = video_stream.get("codec_name", "unknown")
    fmt_duration = float(probe_data.get("format", {}).get("duration", 0) or 0)

    if fmt_duration < 1.0:
        print(f"[broll] REJECTED '{keyword}': too short ({fmt_duration:.1f}s)", flush=True)
        os.remove(dest)
        return None

    if stream_h <= stream_w:
        print(f"[broll] REJECTED '{keyword}': landscape orientation ({stream_w}x{stream_h})", flush=True)
        os.remove(dest)
        return None

    print(
        f"[broll] VALIDATED '{keyword}': {stream_w}x{stream_h} ({codec_name}), "
        f"{fmt_duration:.1f}s",
        flush=True,
    )

    # ── Persist chosen asset into broll_entry for re-edit replay ──────────
    if isinstance(broll_entry, dict):
        if chosen_video_id is not None:
            broll_entry["pexels_video_id"] = chosen_video_id
        broll_entry["pexels_file_url"] = chosen_url
        broll_entry["width"] = stream_w
        broll_entry["height"] = stream_h
        broll_entry["duration"] = round(fmt_duration, 3)

    return dest


def get_video_duration(path):
    """Get duration of a video file in seconds."""
    return probe_duration(path) or 0.0


def prefetch_and_verify_broll(
    broll_clips,
    broll_fetch_futures,
    timeout_s: float = 120.0,
):
    """Wait for every B-roll fetch, verify the asset, return the surviving clips.

    Each entry in `broll_clips` corresponds to a future in `broll_fetch_futures`
    (mapped by future → index). We wait up to `timeout_s` for fetches to
    complete, then probe each downloaded file to confirm it's a usable video
    (file exists, ffprobe parses it, has a video stream, duration > 0.05s).

    Successful entries get `_local_path` annotated and are returned in the
    same order as `broll_clips`. Failed/timed-out/unverifiable entries are
    omitted from the returned list — they never reach the spec, so there is
    no "render asked for X but didn't get X" gap.

    This replaces the prior fail-soft skip pattern. The structural shape of
    "B-roll exists in the spec" is now identical to "B-roll has been fetched
    and verified" — there is no other state.
    """
    if not broll_clips or not broll_fetch_futures:
        return []

    by_idx = {}
    pending = set(broll_fetch_futures.keys())
    t0 = time.time()
    deadline = t0 + timeout_s
    try:
        for fut in concurrent.futures.as_completed(broll_fetch_futures, timeout=timeout_s):
            pending.discard(fut)
            idx = broll_fetch_futures[fut]
            try:
                path = fut.result(timeout=1)
            except Exception as e:
                print(
                    f"[broll] fetch #{idx} raised {type(e).__name__}: {str(e)[:200]} "
                    f"— entry will not appear in the render spec",
                    flush=True,
                )
                continue
            if not path:
                # fetch_broll_clip returned None — keyword had no Pexels match,
                # missing API key, or download fail. The entry simply isn't part
                # of the spec; not an error.
                print(
                    f"[broll] fetch #{idx} resolved to no asset — entry not "
                    f"included in the render spec",
                    flush=True,
                )
                continue
            by_idx[idx] = path
    except concurrent.futures.TimeoutError:
        if pending:
            print(
                f"[broll] {len(pending)} fetch(es) did not finish within "
                f"{timeout_s:.0f}s — those entries will not appear in the spec",
                flush=True,
            )
            for fut in pending:
                fut.cancel()

    # Verify each fetched path. A non-zero file isn't enough — ffprobe must
    # parse a video stream with usable duration, otherwise the FFmpeg
    # composite would crash on it later.
    resolved = []
    for i, bc in enumerate(broll_clips):
        if not isinstance(bc, dict):
            continue
        path = by_idx.get(i)
        if not path:
            continue
        if not os.path.exists(path) or os.path.getsize(path) < 1024:
            print(f"[broll] verify #{i}: file missing/tiny at {path}", flush=True)
            continue
        try:
            probe = _probe_full(path)
        except Exception as pe:
            print(f"[broll] verify #{i}: ffprobe failed: {pe}", flush=True)
            continue
        streams = probe.get("streams") or []
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        if not v_stream:
            print(f"[broll] verify #{i}: no video stream in {path}", flush=True)
            continue
        # Use the format duration when available; some Pexels muxes drop the
        # per-stream duration tag.
        dur = 0.0
        try:
            dur = float((probe.get("format") or {}).get("duration") or 0.0)
        except (TypeError, ValueError):
            dur = 0.0
        if dur <= 0.0:
            try:
                dur = float(v_stream.get("duration") or 0.0)
            except (TypeError, ValueError):
                dur = 0.0
        if dur < 0.05:
            print(f"[broll] verify #{i}: duration={dur:.3f}s too short", flush=True)
            continue

        bc["_local_path"] = path
        resolved.append(bc)

    print(
        f"[broll] prefetch: {len(resolved)}/{len(broll_clips)} entries verified "
        f"in {time.time() - t0:.1f}s",
        flush=True,
    )
    return resolved


_KB_DIRECTIONS = [
    "zoom_in", "zoom_out", "pan_right", "pan_left",
    "zoom_in_pan_right", "zoom_in_pan_left",
    "zoom_out_pan_right", "zoom_out_pan_left",
    "pan_up", "pan_down",
]


def _kb_crop_exprs(direction, kb_smooth, extra_px_w, extra_px_h):
    """Return (crop_x, crop_y) FFmpeg expressions for a Ken Burns direction.

    All expressions use escaped commas (\\,) for FFmpeg filter_complex safety.
    """
    # Center offsets for zoom-only directions
    _half_w = extra_px_w / 2
    _half_h = extra_px_h / 2

    if direction == "zoom_in":
        cx = f"'max(0\\,min({_half_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*{kb_smooth}\\,ih-1920))'"
    elif direction == "zoom_out":
        cx = f"'max(0\\,min({_half_w}*(1.0-{kb_smooth})\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*(1.0-{kb_smooth})\\,ih-1920))'"
    elif direction == "pan_right":
        cx = f"'max(0\\,min({extra_px_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,(ih-1920)/2)'"
    elif direction == "pan_left":
        cx = f"'max(0\\,min({extra_px_w}*(1.0-{kb_smooth})\\,iw-1080))'"
        cy = f"'max(0\\,(ih-1920)/2)'"
    elif direction == "pan_up":
        cx = f"'max(0\\,(iw-1080)/2)'"
        cy = f"'max(0\\,min({extra_px_h}*(1.0-{kb_smooth})\\,ih-1920))'"
    elif direction == "pan_down":
        cx = f"'max(0\\,(iw-1080)/2)'"
        cy = f"'max(0\\,min({extra_px_h}*{kb_smooth}\\,ih-1920))'"
    elif direction == "zoom_in_pan_right":
        cx = f"'max(0\\,min({extra_px_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*{kb_smooth}\\,ih-1920))'"
    elif direction == "zoom_in_pan_left":
        cx = f"'max(0\\,min({extra_px_w}*(1.0-{kb_smooth})\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*{kb_smooth}\\,ih-1920))'"
    elif direction == "zoom_out_pan_right":
        cx = f"'max(0\\,min({extra_px_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*(1.0-{kb_smooth})\\,ih-1920))'"
    elif direction == "zoom_out_pan_left":
        cx = f"'max(0\\,min({extra_px_w}*(1.0-{kb_smooth})\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*(1.0-{kb_smooth})\\,ih-1920))'"
    else:
        # Fallback: gentle zoom in
        cx = f"'max(0\\,min({_half_w}*{kb_smooth}\\,iw-1080))'"
        cy = f"'max(0\\,min({_half_h}*{kb_smooth}\\,ih-1920))'"
    return cx, cy

# Per-type natural durations for ABE transition components. Each entry is
# the duration at which the transition's animation arc reads cleanly — its
# ramp-in / hold / ramp-out plays at the cadence the component was designed
# for. Shortening below this value compresses the arc into a flicker; we
# don't render transitions at less than their natural duration. Gemini
# checks each CUT BOUNDARY's available gap against these values to decide
# which transition (if any) fits; the pipeline renders at whatever natural
# duration the chosen type calls for.
TRANSITION_NATURAL_DURATION_MS = {
    "DipToBlack":    350,
    "ZoomThrough":   500,
    "CardSwipe":     600,
    "StepPush":      600,
    "SlideOver":     700,
    "ShutterFlash":  700,
    "CrossfadeZoom": 800,
    "LightLeak":     800,
    "Stack":        1000,
    "NewspaperWipe":1200,
    "FilmStrip":    1200,
    "SceneTitle":   1800,
}

# ── Zero-handle transition class ──────────────────────────────────────
# Transitions whose renderers either (a) render ONE clip at a time and
# swap at peak under a cover graphic (NewspaperWipe, LightLeak,
# SceneTitle) or (b) squash both clips into invisibility under a
# generated overlay at peak (ShutterFlash). These technically don't
# need handle frames — they work even when the audio gap is 0ms.
#
# 2026-06-21: ENABLED on tight boundaries. The boundary classifier at
# handler.py:6146-6162 still produces two mutually-exclusive lists
# (CUT vs TIGHT) for the prompt, but the transition validator now
# accepts after_word_index from EITHER list when type is in this set
# (handler.py:~7050 — the type-conditional reject). HOW TO PLACE
# TRANSITIONS HARD RULE 1 in the prompt teaches the same rule:
# crossfade types need CUT boundaries; zero-handle types fit either.
# Audio-hard-cut path in build_per_cut_audio (handler.py:11512-11538)
# is what makes this work — the audit-#4 silence-with-splice-fade
# substitution from 2026-06-14 finally has its routing.
ZERO_HANDLE_TRANSITION_TYPES = {
    "ShutterFlash",
    "NewspaperWipe",
    "LightLeak",
    "SceneTitle",
    "DipToBlack",
}

# ── Tight-decoration collision behavior ───────────────────────────────
# When Gemini emits BOTH a zero-handle transition AND a tight_cut_overlay
# anchored at the same tight boundary, the validator at handler.py:~7244
# decides what to do. Two modes:
#
#   "strict"            → raise ValueError, render aborts. Surfaces
#                         Gemini drift loudly during development so the
#                         HOW TO PLACE TRANSITIONS "never both" rule's
#                         compliance is visible.
#   "soft_overlay_wins" → drop the overlay, keep the transition, log a
#                         divergence line, render proceeds. Production-
#                         safe — a single Gemini hiccup doesn't abort
#                         the render.
#
# Set to "strict" now (per user direction 2026-06-21) for development
# visibility. Once a few real renders confirm the prompt prevents the
# collision in practice, flip to "soft_overlay_wins" — that's the
# intended production setting. One-constant flip; no logic change.
_TIGHT_DECORATION_COLLISION = "strict"

# Shortest natural transition — used as the CUT BOUNDARIES filter floor.
# A boundary with audio gap below 2 × this value cannot fit ANY transition
# at its natural duration, so the list omits it. Above it, the gap is
# annotated per boundary and Gemini picks a transition whose natural
# duration fits within gap/2 (gap-sharing handle on each side).
_TRANSITION_MIN_NATURAL_MS = min(TRANSITION_NATURAL_DURATION_MS.values())

TRANSITION_DURATION_DEFAULT = _TRANSITION_MIN_NATURAL_MS / 1000.0

def get_transition_duration(transition_type=None):
    """Look up natural duration in seconds for a given transition type.

    `transition_type` is the string name (e.g. "ZoomThrough"). Returns the
    type's natural duration in seconds. Unknown types fall back to the
    shortest natural duration so the pipeline doesn't allocate more handle
    than necessary. Pass None to get the default floor.
    """
    if transition_type is None:
        return TRANSITION_DURATION_DEFAULT
    return TRANSITION_NATURAL_DURATION_MS.get(transition_type, _TRANSITION_MIN_NATURAL_MS) / 1000.0


# ── Probe cache — eliminates redundant ffprobe calls on the same file ─────────
# One comprehensive ffprobe call returns streams + format; subsequent queries
# for duration, sample_rate, resolution, etc. pull from the cached result.
_probe_cache = {}  # path → {"streams": [...], "format": {...}}


def _probe_full(file_path):
    """Run a single comprehensive ffprobe and cache the result."""
    if file_path in _probe_cache:
        return _probe_cache[file_path]
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", file_path],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {file_path}: {(result.stderr or '')[-300:]}")
    try:
        data = json.loads(result.stdout or "{}")
    except Exception as e:
        raise RuntimeError(f"ffprobe returned invalid JSON for {file_path}: {e}") from e
    if not data.get("streams") and not data.get("format"):
        raise RuntimeError(f"ffprobe returned empty data for {file_path}")
    _probe_cache[file_path] = data
    return data


def probe_cache_clear(file_path=None):
    """Clear cache for a specific file (after re-encode) or all files."""
    if file_path:
        _probe_cache.pop(file_path, None)
    else:
        _probe_cache.clear()


def _probe_shake_intensity(file_path: str, sample_count: int = 12) -> float:
    """Sample N frames at 240p and return the mean inter-frame translation
    magnitude in pixels (Lucas-Kanade sparse optical flow on a Shi-Tomasi
    feature grid, then median over good tracks per pair, mean over pairs).

    Drives the deshake gate in `_do_fps_normalize`. We only want to pay the
    cost of `deshake=rx=16:ry=16` (≈100s on 1080p×60fps) when the source
    actually moves; on stable phone footage the filter does 100s of
    block-matching only to decide every frame is a no-op.

    Returns 0.0 (no motion) if the source is unreadable or has fewer than
    two sampled frames — fail-closed: treat unreadable input as stable so
    the pipeline doesn't pay deshake cost just to recover from a probe
    failure. The downstream encode still succeeds either way.
    """
    import cv2 as _cv2
    import numpy as _np

    cap = _cv2.VideoCapture(file_path)
    try:
        if not cap.isOpened():
            return 0.0
        total_frames = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
        src_w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH) or 0)
        if total_frames < 2 or src_w <= 0:
            return 0.0

        # Sample evenly across the source. Skip the first/last 5% to dodge
        # leader/trailer black frames that some phone cameras embed.
        stride = max(1, int(total_frames * 0.9 // sample_count))
        start = max(1, int(total_frames * 0.05))

        # Probe at 240p — feature tracking is robust at this resolution and
        # 16× cheaper than full-res. Result will be a 240p-pixel score; the
        # threshold in the caller is calibrated for that scale.
        probe_h = 240
        probe_w = max(1, int(probe_h * src_w / max(1, int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT) or 1))))

        prev_gray = None
        magnitudes: list[float] = []
        feature_params = dict(
            maxCorners=120, qualityLevel=0.01, minDistance=8, blockSize=7
        )
        lk_params = dict(
            winSize=(15, 15), maxLevel=2,
            criteria=(_cv2.TERM_CRITERIA_EPS | _cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )

        for i in range(sample_count):
            frame_idx = start + i * stride
            if frame_idx >= total_frames:
                break
            cap.set(_cv2.CAP_PROP_POS_FRAMES, float(frame_idx))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            small = _cv2.resize(frame, (probe_w, probe_h), interpolation=_cv2.INTER_AREA)
            gray = _cv2.cvtColor(small, _cv2.COLOR_BGR2GRAY)

            if prev_gray is not None:
                p0 = _cv2.goodFeaturesToTrack(prev_gray, mask=None, **feature_params)
                if p0 is not None and len(p0) >= 8:
                    p1, st, _err = _cv2.calcOpticalFlowPyrLK(
                        prev_gray, gray, p0, None, **lk_params
                    )
                    if p1 is not None and st is not None:
                        good_new = p1[st.flatten() == 1]
                        good_old = p0[st.flatten() == 1]
                        if len(good_new) >= 8:
                            d = good_new - good_old
                            mag = _np.sqrt((d * d).sum(axis=-1)).flatten()
                            # Median is robust to a few large flow vectors
                            # caused by intentional motion (a hand entering
                            # frame, etc.). Mean of medians over pairs gives
                            # a stable per-frame motion estimate.
                            magnitudes.append(float(_np.median(mag)))
            prev_gray = gray

        if not magnitudes:
            return 0.0
        return float(_np.mean(magnitudes))
    finally:
        cap.release()


def probe_duration(file_path):
    data = _probe_full(file_path)
    # Try format duration first, then video stream duration
    try:
        d = float((data.get("format") or {}).get("duration") or 0)
        if d > 0:
            return d
    except Exception:
        pass
    for s in (data.get("streams") or []):
        try:
            d = float(s.get("duration") or 0)
            if d > 0:
                return d
        except Exception:
            continue
    return None


def probe_audio_sample_rate(file_path):
    data = _probe_full(file_path)
    for s in (data.get("streams") or []):
        if s.get("codec_type") == "audio":
            try:
                sr = int(s.get("sample_rate") or 0)
                return sr if sr > 0 else None
            except Exception:
                pass
    return None


def validate_output(path, step_name, min_size_bytes=100000):
    """Check that output file exists and is not empty/corrupt. Returns True if valid."""
    if not os.path.exists(path):
        print(f"[{step_name}] OUTPUT MISSING: {path} does not exist", flush=True)
        return False
    size = os.path.getsize(path)
    if size < min_size_bytes:
        print(f"[{step_name}] OUTPUT TOO SMALL: {path} is {size} bytes (expected >{min_size_bytes})", flush=True)
        return False
    dur = probe_duration(path)
    if not dur or dur < 1.0:
        print(f"[{step_name}] OUTPUT INVALID: duration={dur}s", flush=True)
        return False
    print(f"[{step_name}] Output valid: {size / 1024 / 1024:.1f}MB, {dur:.1f}s", flush=True)
    return True


def probe_resolution(file_path):
    data = _probe_full(file_path)
    for s in (data.get("streams") or []):
        if s.get("codec_type") == "video":
            return {"width": s.get("width") or 1080, "height": s.get("height") or 1920}
    return {"width": 1080, "height": 1920}


def run_ffmpeg(args):
    print(f"[ffmpeg] Running: ffmpeg {' '.join(str(a) for a in args[:10])}...", flush=True)
    t = time.time()
    result = subprocess.run(
        ["ffmpeg", "-v", "warning", "-stats", "-threads", "0", "-benchmark"] + [str(a) for a in args],
        capture_output=True, text=True, timeout=300,
    )
    elapsed = time.time() - t
    if result.returncode != 0:
        print(f"[ffmpeg] FAILED after {elapsed:.1f}s (exit code {result.returncode})", flush=True)
        _stderr = result.stderr or ""
        # Extract error/warning lines (skip progress and build config)
        _err_lines = [ln for ln in _stderr.split("\n")
                      if any(k in ln.lower() for k in ("error", "invalid", "failed", "cannot", "no such", "warning"))]
        if _err_lines:
            print(f"[ffmpeg] errors/warnings:\n" + "\n".join(_err_lines[:30]), flush=True)
        print(f"[ffmpeg] stderr (last 1500):\n{_stderr[-1500:]}", flush=True)
        raise RuntimeError(f"FFmpeg failed: {_stderr[-500:]}")
    # Print benchmark/stats lines from stderr for timing diagnostics
    _stderr = result.stderr or ""
    for _line in _stderr.split("\n"):
        _ll = _line.strip()
        if _ll and ("bench" in _ll.lower() or "speed=" in _ll or "time=" in _ll):
            print(f"[ffmpeg] {_ll}", flush=True)
    print(f"[ffmpeg] Completed in {elapsed:.1f}s", flush=True)
    return result


def analyze_source_video(source_path):
    """Analyze source video and return metadata + scale/crop filter for the main render.

    Instead of re-encoding the entire source into a normalized intermediate,
    this returns the FFmpeg filter string that each segment's v_chain should
    prepend to fold scale/crop/fps conversion into the single render pass.
    Saves an entire encode/decode cycle (3-10s depending on source length).

    Returns dict with keys:
        source_path: str — unchanged original path
        width: int, height: int — original dimensions
        fps: float — original fps
        normalize_vf: str or None — filter to prepend (None if already 1080x1920@30fps)
    """
    info = _probe_full(source_path)
    streams = info.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise RuntimeError("No video stream found in source")

    # Audio stream's start_time — iPhone/AVCaptureSession sources set this
    # to a positive value (50-300ms typically) because the mic initializes
    # after the camera. The container's metadata truthfully says "audio
    # data sample 0 corresponds to file-time = start_time, not 0." We
    # surface this offset so the main pipeline can apply a one-shot shift
    # of Deepgram's transcript timestamps from audio-data-time to file-time
    # — after which every downstream timing reference (caption display,
    # video extraction, SFX placement) is on the same timeline as the
    # source's video stream, eliminating the lip-sync drift.
    audio_stream_info = next((s for s in streams if s.get("codec_type") == "audio"), None)
    audio_stream_offset = 0.0
    if audio_stream_info and audio_stream_info.get("start_time"):
        try:
            audio_stream_offset = max(0.0, float(audio_stream_info["start_time"]))
        except (ValueError, TypeError):
            audio_stream_offset = 0.0

    # Rotation metadata: iPhone/Android portrait recordings are commonly stored
    # as a landscape H.264 stream + a Display Matrix rotation tag. ffmpeg
    # auto-rotates at decode time, so the frames flowing into our filter chain
    # are in DISPLAY orientation, not raw stream orientation. Work in display
    # dims so the crop/scale math aligns with the actual decoded frames.
    w_raw = int(video.get("width") or 0)
    h_raw = int(video.get("height") or 0)
    _rotation_deg = 0
    for _sd in (video.get("side_data_list") or []):
        if isinstance(_sd, dict) and "rotation" in _sd:
            try:
                _rotation_deg = int(round(float(_sd["rotation"])))
            except (TypeError, ValueError):
                pass
            break
    if _rotation_deg == 0:
        _legacy = (video.get("tags") or {}).get("rotate")
        if _legacy is not None:
            try:
                _rotation_deg = int(round(float(_legacy)))
            except (TypeError, ValueError):
                pass
    if _rotation_deg % 180 != 0:
        w, h = h_raw, w_raw
        print(f"[analyze] Rotation={_rotation_deg}° — using display dims {w}x{h} (raw stream {w_raw}x{h_raw})", flush=True)
    else:
        w, h = w_raw, h_raw
    if w > h:
        print(f"[analyze] Landscape input ({w}x{h}) — will center-crop to 9:16 in render", flush=True)

    fps_str = video.get("avg_frame_rate") or video.get("r_frame_rate") or "30/1"
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den)
    except Exception:
        fps = 30.0

    r_fps_str = video.get("r_frame_rate") or "30/1"
    try:
        rn, rd = r_fps_str.split("/")
        r_fps = float(rn) / float(rd)
    except Exception:
        r_fps = fps

    is_vfr = abs(fps - r_fps) > 0.5
    needs_scale_crop = (w != 1080 or h != 1920)

    if not needs_scale_crop:
        # fps/VFR conversion is handled by fps-normalize step (60fps + minterpolate) — no normalize_vf needed
        if abs(fps - 30) > 1 or is_vfr:
            print(f"[analyze] Source {w}x{h} @ {fps:.2f}fps (VFR={is_vfr}) — fps-normalize step handles it", flush=True)
        else:
            print(f"[analyze] Source is already {w}x{h} @ {fps:.2f}fps — no normalize needed", flush=True)
        return {"source_path": source_path, "width": w, "height": h, "fps": fps, "normalize_vf": None,
                "crop_x": 0, "crop_y": 0, "crop_w": 1080, "crop_h": 1920,
                "audio_stream_offset": audio_stream_offset}

    print(f"[analyze] Source {w}x{h} @ {fps:.2f}fps — will normalize in render pass", flush=True)

    # Build the scale/crop filter that will be prepended to each segment's v_chain.
    # Also store transform params so face positions can be mapped to 1080x1920 space.
    #
    # Two coordinate systems:
    #   - "raw": the original source frame pixels
    #   - "output": 1080x1920 after normalize_vf
    #
    # For reframe (face-aware crop): crop in raw space, then scale to 1080x1920
    #   → transform: new_cx = (raw_cx - crop_x) * (1080 / crop_w)
    #
    # For center crop (scale first, then crop): scale to fit, crop center
    #   → transform: new_cx = raw_cx * scale - crop_offset_in_scaled_space

    normalize_vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    # Default transform: identity (raw == output)
    _face_transform = {"mode": "identity"}

    if w != 1080 or h != 1920:
        # Compute what "force_original_aspect_ratio=increase" does:
        # Scale so the SMALLER dimension fills the target → then crop the overflow
        scale_x = 1080.0 / w
        scale_y = 1920.0 / h
        scale = max(scale_x, scale_y)  # increase = use the larger scale factor
        scaled_w = round(w * scale)
        scaled_h = round(h * scale)
        # Default center crop offset (in post-scale space)
        _center_crop_x = (scaled_w - 1080) // 2
        _center_crop_y = (scaled_h - 1920) // 2

        # Default transform for center-crop path
        _face_transform = {
            "mode": "scale_then_crop",
            "scale": scale,
            "crop_x": _center_crop_x,
            "crop_y": _center_crop_y,
        }

        source_duration = probe_duration(source_path) or 0.0
        _sample_ts = [round(source_duration * f, 3) for f in (0.2, 0.5, 0.8)] if source_duration > 1 else []
        _sparse_faces = detect_face_positions(source_path, _sample_ts) if _sample_ts else []
        reframe_crops = calculate_reframe_crop(_sparse_faces, w, h)
        if reframe_crops:
            avg_crops = [c for c in reframe_crops if c.get("found")] or reframe_crops
            avg_x = int(sum(c["crop_x"] for c in avg_crops) / len(avg_crops))
            avg_y = int(sum(c["crop_y"] for c in avg_crops) / len(avg_crops))
            crop_w = int(reframe_crops[0]["crop_w"])
            crop_h = int(reframe_crops[0]["crop_h"])
            normalize_vf = f"crop={crop_w}:{crop_h}:{avg_x}:{avg_y},scale=1080:1920,setsar=1"
            _face_transform = {
                "mode": "crop_then_scale",
                "crop_x": avg_x, "crop_y": avg_y,
                "crop_w": crop_w, "crop_h": crop_h,
            }
            print(f"[reframe] Static reframe: crop={crop_w}x{crop_h}@({avg_x},{avg_y})", flush=True)
        else:
            print("[reframe] No face found — using center crop", flush=True)

    return {
        "source_path": source_path, "width": w, "height": h, "fps": fps,
        "normalize_vf": normalize_vf,
        "face_transform": _face_transform,
        "audio_stream_offset": audio_stream_offset,
    }




def get_atempo_filter(speed):
    """Build an atempo filter chain for arbitrary positive speed values."""
    safe = max(0.01, float(speed) or 1.0)
    parts = []
    remaining = safe
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.4f}")
    return ",".join(parts)


def get_pitch_preserving_speed_filter(speed: float) -> str:
    """Return FFmpeg audio filter for speed change WITHOUT pitch shift.

    Preferred: rubberband (best quality, preserves formants).
    Fallback: atempo chain (always available, good quality).
    Returns empty string if speed is ~1.0x (no filter needed).
    """
    if abs(speed - 1.0) < 0.001:
        return ""
    if _HAS_FFMPEG_RUBBERBAND:
        return f"rubberband=tempo={speed:.4f}:pitch=1.0"
    return get_atempo_filter(speed)


def _refine_boundary_to_low_energy(
    boundary_time_s: float,
    audio_samples,
    sample_rate: int = 48000,
    backward_radius_s: float = 0.0,
    forward_radius_s: float = 0.0,
    rms_window_s: float = 0.005,
) -> float:
    """Refine a cut boundary by searching for the sample with lowest local
    RMS energy (= closest to genuine silence) in an asymmetric window
    [boundary - backward_radius_s, boundary + forward_radius_s].

    Asymmetric is critical — symmetric search picks local energy minima
    INSIDE kept words (between syllables, mid-vowel dips), which clips word
    onsets. Caller passes one-sided radii so refinement only moves the cut
    OUTWARD into the removed-content gap, never INWARD into kept audio:
      - source_end  (splice after kept content): forward_radius_s only
      - source_start (splice before kept content): backward_radius_s only

    Different from VAD snapping: snapping searches widely for ANY silence
    (could be 100-300ms away) and moves the cut there, changing editorial
    timing. Refinement stays within ≤50ms of the original — below the
    perceptual threshold for editorial shift — and only expands the kept
    range slightly into the natural pause around removed content.

    Implementation: slide a 5ms window across the search range, compute
    RMS for each position via cumulative sum (O(N)), return the time of
    the window center with minimum energy.

    Returns the original boundary unchanged if:
      - both radii are zero (no search window)
      - the search window falls entirely outside the audio
      - audio_samples is too short to evaluate
    """
    import numpy as _np

    if backward_radius_s <= 0.0 and forward_radius_s <= 0.0:
        return boundary_time_s

    backward_samples = max(0, int(backward_radius_s * sample_rate))
    forward_samples = max(0, int(forward_radius_s * sample_rate))
    rms_win = max(1, int(rms_window_s * sample_rate))

    boundary_sample = int(round(boundary_time_s * sample_rate))
    search_start = max(0, boundary_sample - backward_samples)
    search_end = min(len(audio_samples), boundary_sample + forward_samples + rms_win)

    if search_end <= search_start + rms_win:
        return boundary_time_s

    search_audio = audio_samples[search_start:search_end].astype(_np.float32)
    N = len(search_audio)
    if N < rms_win:
        return boundary_time_s

    sq = search_audio ** 2
    cumsum = _np.concatenate([[0.0], _np.cumsum(sq)])
    # window_sums[k] = sum of sq[k : k + rms_win]
    window_sums = cumsum[rms_win:N + 1] - cumsum[:N - rms_win + 1]

    min_idx = int(_np.argmin(window_sums))
    refined_sample = search_start + min_idx + rms_win // 2
    return refined_sample / sample_rate


def build_per_cut_audio(source_path, cuts, effective_durations, work_dir, sample_rate=48000, trans_dur_after=None, per_cut_render_dur_frames=None, source_fps=60.0, trim_head_dur=None, trim_tail_dur=None, audio_stream_offset=0.0):
    """Build the per-cut audio track — COMPRESSION (overlap) transition model.

    Each cut's RENDER range is source[start + trim_head*speed, end - trim_tail*speed]
    sliced and resampled at the cut's constant speed. For clips with an
    outgoing transition, trim_tail = trans_dur (A's last trans_dur of
    source is consumed by the transition slot). For clips with an
    incoming transition (previous clip has transition_out), trim_head =
    trans_dur (B's first trans_dur of source is consumed by the
    transition slot).

    COMPRESSION-MODEL AUDIO:
      Clip A's main audio plays source[cs_A, ce_A - trans_dur*speed_A].
      Transition slot audio is an equal-power crossfade:
        trans[t] = A_tail[t] * cos²(t) + B_head[t] * sin²(t)
      where A_tail reads source[ce_A - trans_dur*speed_A, ce_A] and
      B_head reads source[cs_B, cs_B + trans_dur*speed_B]. Clip B's
      main audio plays source[cs_B + trans_dur*speed_B, ce_B].

      Total source coverage:
        A_main:   source[cs_A,                ce_A - trans*sa]
        trans:    source[ce_A - trans*sa,     ce_A           ]  (A side)
                  source[cs_B,                cs_B + trans*sb]  (B side, mixed)
        B_main:   source[cs_B + trans*sb,     ce_B           ]
      Each clip's full source range is shown exactly once. No clipping.

    BOUNDARIES (no splice fade needed):
      A's main → trans_audio: contiguous A content (same source range).
      trans_audio → B's main: contiguous B content (same source range).
      The 400ms crossfade inside trans_audio handles the source jump
      between A and B; no 5ms splice fade is needed at either edge.

    SAMPLE-LOCKED ALIGNMENT:
      Per-cut audio sample count is derived from the *exact* video
      frame count (per_cut_render_dur_frames[i]) so audio and video
      lengths match within ±1 sample (~21 µs) per cut. Transition
      slot audio is exactly trans_dur*sample_rate samples, matching
      the visual transition's frame count.

    Returns the path to the concatenated WAV.
    """
    import numpy as np
    import wave

    output_wav = os.path.join(work_dir, "per_cut_audio.wav")

    # ── Single source extraction ────────────────────────────────────────
    # Skip the ffmpeg extraction if a wav was already dropped here by the
    # prewarm path (handler.py copies cached audio to this exact path right
    # after the source copy when both are available on the prewarm volume).
    # The wav's sample rate matches what we'd extract since both paths probe
    # the same source file. Saves ~3-5s on warm renders.
    full_src_wav = os.path.join(work_dir, "source_audio_full.wav")
    if os.path.exists(full_src_wav) and os.path.getsize(full_src_wav) > 1024:
        print(
            f"[audio] using prewarm-cached source wav "
            f"({os.path.getsize(full_src_wav) // (1024 * 1024)}MB) — skipping extraction",
            flush=True,
        )
    else:
        _ext = subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-i", source_path, "-vn",
             "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
             full_src_wav],
            capture_output=True, text=True, timeout=120,
        )
        if _ext.returncode != 0 or not os.path.exists(full_src_wav):
            raise RuntimeError(
                f"Source audio extraction failed: {(_ext.stderr or '')[-500:]}"
            )

    with wave.open(full_src_wav, "rb") as wf:
        n_channels = wf.getnchannels()
        n_src_samples = wf.getnframes()
        raw = wf.readframes(n_src_samples)
    src_samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if n_channels > 1:
        src_samples = src_samples[::n_channels]  # first channel only
    src_total = len(src_samples)
    try:
        os.remove(full_src_wav)
    except OSError:
        pass

    # Helper: extract source[s_sec, e_sec] then resample to n_out samples.
    def _resample_range(s_sec: float, e_sec: float, n_out: int) -> np.ndarray:
        if n_out <= 0:
            return np.zeros(0, dtype=np.float32)
        s_idx = max(0, int(round(s_sec * sample_rate)))
        e_idx = min(src_total, int(round(e_sec * sample_rate)))
        if e_idx <= s_idx + 1:
            return np.zeros(n_out, dtype=np.float32)
        slc = src_samples[s_idx:e_idx]
        if len(slc) == n_out:
            return slc.astype(np.float32)
        pos = np.linspace(0, len(slc) - 1, n_out)
        return np.interp(pos, np.arange(len(slc)), slc).astype(np.float32)

    # ── Per-cut audio — render-only range, sample-locked to video frames ─
    cut_audios: List[np.ndarray] = []
    for ci, cut in enumerate(cuts):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])
        clip_speed = float(cut.get("speed") or 1.0)
        trim_h = float(trim_head_dur[ci]) if trim_head_dur is not None and ci < len(trim_head_dur) else 0.0
        trim_t = float(trim_tail_dur[ci]) if trim_tail_dur is not None and ci < len(trim_tail_dur) else 0.0
        # Render source range = [src_start + trim_h*speed, src_end − trim_t*speed]
        render_src_start = src_start + trim_h * clip_speed
        render_src_end = src_end - trim_t * clip_speed
        if render_src_end - render_src_start < 0.001:
            cut_audios.append(np.zeros(1, dtype=np.float32))
            continue
        # Lock audio sample count to video frame count when provided.
        if per_cut_render_dur_frames is not None and ci < len(per_cut_render_dur_frames):
            n_out = max(1, int(round(per_cut_render_dur_frames[ci] * sample_rate / source_fps)))
        else:
            n_out = max(1, int(round((effective_durations[ci] - trim_h - trim_t) * sample_rate)))
        if abs(clip_speed - 1.0) < 0.001:
            # 1.0× — direct slice (truncate/pad to exact n_out).
            # render_src_start is in file-time (transcript was shifted by
            # audio_stream_offset at intake). The WAV is in audio-data-time
            # (offset stripped by raw audio extraction). Convert file-time
            # back to audio-data-time by subtracting the offset before
            # computing the sample index.
            _wav_src_t = max(0.0, render_src_start - float(audio_stream_offset or 0.0))
            s_idx = max(0, int(round(_wav_src_t * sample_rate)))
            e_idx = min(src_total, s_idx + n_out)
            # ── DIAG PROBE 3: audio slice frame mapping ──
            # Mirror of probe 2 for the audio side. Wallclock of the slice
            # start should match the clip's source_time. |Δ| should be
            # sub-millisecond (sample-accurate). If audio's |Δ| matches
            # video's |Δ| for the same clip, both are on the same timeline.
            # If they differ, audio and video are on different timelines —
            # exactly the bug we're looking for.
            _audio_wc = s_idx / float(sample_rate)
            _audio_err_ms = (render_src_start - _audio_wc) * 1000.0
            print(
                f"[audio-extract] clip={ci} source_t={render_src_start:.4f}s "
                f"sample={s_idx} wallclock={_audio_wc:.4f}s "
                f"|Δ|={_audio_err_ms:+.2f}ms n_out={n_out}",
                flush=True,
            )
            slc = src_samples[s_idx:e_idx]
            if len(slc) >= n_out:
                cut_audios.append(slc[:n_out].astype(np.float32))
            else:
                padded = np.zeros(n_out, dtype=np.float32)
                padded[:len(slc)] = slc
                cut_audios.append(padded)
        else:
            # Same file-time → audio-data-time conversion as the 1.0× branch
            # (subtract audio_stream_offset from both ends of the source range).
            _off = float(audio_stream_offset or 0.0)
            cut_audios.append(_resample_range(
                max(0.0, render_src_start - _off),
                max(0.0, render_src_end - _off),
                n_out,
            ))

    # ── Transition audio — COMPRESSION-MODEL crossfade ─────────────────────
    # In the compression model, A's last trans_dur of source plays IN the
    # transition slot (it was already excluded from A's main render range
    # via trim_tail_dur). B's first trans_dur of source plays IN the same
    # transition slot (excluded from B's main range via trim_head_dur).
    # The two are equal-power crossfaded over the slot's duration:
    #   trans[t] = A_tail[t] * cos²(t) + B_head[t] * sin²(t)
    # This matches what every NLE does at a crossfade transition.
    #
    # Boundaries (in the audio concat):
    #   cut_audio[A]  → trans_audio: CONTIGUOUS — A's main ends at
    #     source[end_A − trans_dur*speed_A], the transition's A-side starts
    #     reading from that exact position. No jump.
    #   trans_audio → cut_audio[B]: CONTIGUOUS — the transition's B-side
    #     ends at source[start_B + trans_dur*speed_B], and B's main starts
    #     at that exact position (via trim_head_dur). No jump.
    # Both boundaries are within-clip continuations of the same source
    # range, so no 5ms splice fade is needed at either.
    all_clips: List[np.ndarray] = []
    is_splice_after: List[bool] = []
    # Parallel to is_splice_after: True if there's a real source jump at the
    # splice (Gemini removed content — A's last source sample and B's first
    # source sample are not adjacent), False if source is contiguous (tight
    # shot-change cuts where source_end[A] == source_start[B]). The fade
    # loop below applies cos²/sin² ONLY where _splice_source_jump[i] is True.
    # For contiguous splices a fade would force continuous audio to zero at
    # the seam, producing a 10ms attenuated envelope and audible click —
    # confirmed numerically 2026-06-14: 38% RMS drop in the seam window,
    # sample-level zero at the join. The fix below skips both fade-out
    # and fade-in for those splices so the underlying continuous audio
    # plays through unmodified.
    _splice_source_jump: List[bool] = []
    _n_transitions = 0
    _SAMPLE_TOLERANCE_S = 1.0 / sample_rate  # contiguity = within 1 sample
    for ci, cut_audio in enumerate(cut_audios):
        all_clips.append(cut_audio)
        _t_after = 0.0
        if trans_dur_after is not None and ci < len(trans_dur_after):
            _t_after = float(trans_dur_after[ci] or 0.0)
        if _t_after <= 0 or ci + 1 >= len(cuts):
            # No transition. Boundary cut_audio[ci] → cut_audio[ci+1] is a
            # SPLICE — but only NEEDS a fade if source is non-contiguous.
            if ci + 1 < len(cut_audios):
                is_splice_after.append(True)
                _src_a_end = float(cuts[ci]["source_end"])
                _src_b_start = float(cuts[ci + 1]["source_start"])
                _splice_source_jump.append(
                    (_src_b_start - _src_a_end) > _SAMPLE_TOLERANCE_S
                )
            continue
        cut_a = cuts[ci]
        cut_b = cuts[ci + 1]
        speed_a = float(cut_a.get("speed") or 1.0)
        speed_b = float(cut_b.get("speed") or 1.0)
        n_trans = max(1, int(round(_t_after * sample_rate)))
        c_a_end = float(cut_a["source_end"])
        c_b_start = float(cut_b["source_start"])
        _off = float(audio_stream_offset or 0.0)

        # ── Zero-handle transition: hard audio cut, video covers slot ─
        # Audit #4 from 2026-06-14: when the transition type is in
        # ZERO_HANDLE_TRANSITION_TYPES, the equal-power crossfade below
        # would smear A's last word of speech with B's first word
        # (audibly bad on tight cuts where both halves contain dialogue).
        # The zero-handle transition's video animation generates its own
        # pixels covering the cut; the audio path should NOT mix A's tail
        # with B's head. Replace the crossfade with silence under the
        # visual transition; 5ms equal-power splice fades on either side
        # prevent click. This branch is forward-looking: today the
        # CUT BOUNDARIES filter (handler.py:~5697) excludes zero-handle
        # transitions from tight cuts, so it fires only after the boundary
        # classifier is updated. Architecture-in-place per the audit.
        _trans_type = str(cut_a.get("transition_out") or "").strip()
        if _trans_type in ZERO_HANDLE_TRANSITION_TYPES:
            transition_audio = np.zeros(n_trans, dtype=np.float32)
            # Speech → silence and silence → speech are by definition
            # NON-contiguous (zero vs waveform); the fade is required at
            # both edges to prevent click.
            is_splice_after.append(True)
            _splice_source_jump.append(True)
            all_clips.append(transition_audio)
            if ci + 1 < len(cut_audios):
                is_splice_after.append(True)
                _splice_source_jump.append(True)
            _n_transitions += 1
            continue

        # A's tail audio: source[end_A − trans_dur*speed_A, end_A]
        a_tail = _resample_range(
            max(0.0, c_a_end - _t_after * speed_a - _off),
            max(0.0, c_a_end - _off),
            n_trans,
        )
        # B's head audio: source[start_B, start_B + trans_dur*speed_B]
        b_head = _resample_range(
            max(0.0, c_b_start - _off),
            max(0.0, c_b_start + _t_after * speed_b - _off),
            n_trans,
        )
        # Equal-power crossfade: A fades out (cos²), B fades in (sin²).
        # cos² + sin² = 1 → constant total power across the crossfade.
        _fade_axis = np.linspace(0.0, np.pi / 2.0, n_trans, dtype=np.float32)
        _fade_out_curve = np.cos(_fade_axis) ** 2
        _fade_in_curve = np.sin(_fade_axis) ** 2
        transition_audio = (a_tail * _fade_out_curve + b_head * _fade_in_curve).astype(np.float32)
        # Both boundaries are contiguous (within-clip source continuations).
        is_splice_after.append(False)
        _splice_source_jump.append(False)
        all_clips.append(transition_audio)
        if ci + 1 < len(cut_audios):
            is_splice_after.append(False)
            _splice_source_jump.append(False)
        _n_transitions += 1

    if not all_clips:
        with wave.open(output_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00" * sample_rate * 2)
        return output_wav

    # ── Splice fades: 5ms cos²/sin² ONLY on real source jumps ──
    # For each splice in is_splice_after, the fade applies only when
    # _splice_source_jump[i] is True — meaning there's a real source-time
    # gap (Gemini-removed content between the two cuts, or a speech↔silence
    # transition at a zero-handle slot edge). For contiguous splices (tight
    # shot-change cuts where source_end[A] == source_start[B]) the
    # underlying audio is continuous and the fade is SUPPRESSED: applying
    # cos²→0 then 0→sin² to continuous audio produces a 10ms attenuated
    # envelope with sample-level zero at the seam — confirmed 2026-06-14:
    # 38% RMS drop, audible click. Suppressing the fade lets continuous
    # audio play through unmodified.
    _fade_samples = int(round(0.005 * sample_rate))
    _n_splices = 0
    _n_contiguous_suppressed = 0
    if _fade_samples > 0 and len(all_clips) >= 2:
        _fade_out = (np.cos(
            np.linspace(0.0, np.pi / 2.0, _fade_samples, dtype=np.float32)
        ) ** 2)
        _fade_in = (np.sin(
            np.linspace(0.0, np.pi / 2.0, _fade_samples, dtype=np.float32)
        ) ** 2)
        for _i, _is_splice in enumerate(is_splice_after):
            if not _is_splice:
                continue
            _has_jump = (
                _splice_source_jump[_i]
                if _i < len(_splice_source_jump) else True
            )
            if not _has_jump:
                # Contiguous source — skip both fade-out and fade-in.
                _n_contiguous_suppressed += 1
                continue
            _seg_a = all_clips[_i]
            _seg_b = all_clips[_i + 1]
            if len(_seg_a) >= _fade_samples:
                _seg_a[-_fade_samples:] *= _fade_out
            if len(_seg_b) >= _fade_samples:
                _seg_b[:_fade_samples] *= _fade_in
            _n_splices += 1
        if _n_splices or _n_contiguous_suppressed:
            print(
                f"[audio] splices: {_n_splices} faded (5ms cos²/sin²), "
                f"{_n_contiguous_suppressed} contiguous suppressed",
                flush=True,
            )

    full_audio = np.concatenate(all_clips)
    full_audio = np.clip(full_audio, -32768, 32767).astype(np.int16)
    with wave.open(output_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(full_audio.tobytes())

    _total_dur = len(full_audio) / sample_rate
    print(
        f"[audio] Built per-cut audio: {len(cuts)} cuts, "
        f"{_n_transitions} transition(s), "
        f"{_total_dur:.3f}s, {len(full_audio)} samples (single-extract)",
        flush=True,
    )
    return output_wav


def project_words_to_output(transcript, cuts, effective_durations, transition_duration=None, clip_time_maps=None, removed_word_indices=None, fps=60.0, trans_dur_after=None):
    """Project word timestamps from source to output timeline using canonical time maps.

    If removed_word_indices is provided, words at those indices are excluded.
    This is the SAME source of truth used by build_clips_from_words, so the
    caption projection cannot emit fragments of removed words.

    Overlap (handle) model: every transition slot lives ON the overlap
    between adjacent clips' output ranges. Cursor advances eff_dur and
    subtracts trans_dur per transition; words in the trans_tail handle
    (the overlap region) are suppressed so the next cut's head words
    own that output-time range.
    """
    words = transcript.get("words") or []
    projected = []
    if not words or not cuts:
        return projected
    _removed = removed_word_indices if isinstance(removed_word_indices, (set, frozenset)) else set(removed_word_indices or [])
    clip_ranges = get_output_clip_ranges(
        cuts, effective_durations,
        transition_duration=transition_duration,
        trans_dur_after=trans_dur_after,
    )
    output_cursor = 0.0
    for i, cut in enumerate(cuts):
        c_start = float(cut["source_start"])
        c_end   = float(cut["source_end"])
        tm = clip_time_maps[i] if clip_time_maps and i < len(clip_time_maps) else None
        _eff_i = effective_durations[i] if i < len(effective_durations) else (c_end - c_start)
        _trans_tail_i = float(trans_dur_after[i] or 0.0) if (trans_dur_after is not None and i < len(trans_dur_after)) else 0.0
        for word_idx, w in enumerate(words):
            if word_idx in _removed:
                continue
            ws = float(w.get("start") or 0)
            we = float(w.get("end") or 0)
            # A word belongs to whichever cut contains its MIDPOINT in source
            # time. Half-open interval [c_start, c_end) ensures exactly-one
            # assignment for words that straddle a cut boundary — without
            # this, a straddling word would be projected by both adjacent
            # cuts and surface as duplicate back-to-back captions.
            w_mid = (ws + we) / 2.0
            if not (c_start <= w_mid < c_end):
                continue
            clamped_s = max(ws, c_start)
            clamped_e = min(we, c_end)
            if tm:
                local_s = _time_map_lookup(tm, clamped_s - c_start)
                local_e = _time_map_lookup(tm, clamped_e - c_start)
            else:
                speed = float(cut.get("speed") or 1.0)
                local_s = (clamped_s - c_start) / speed
                local_e = (clamped_e - c_start) / speed
            # Suppress words that fall inside this cut's trans_tail handle
            # (the overlap region with the next cut's head). The next cut's
            # head words own that output time range; rendering this cut's
            # tail words there would produce simultaneous overlapping
            # caption pages during every transition.
            if _trans_tail_i > 0 and local_s >= (_eff_i - _trans_tail_i):
                continue
            # Preserve sub-millisecond precision for caption tokens.
            projected.append({
                "start": float(output_cursor + local_s),
                "end":   float(output_cursor + local_e),
                "word":  w.get("punctuated_word") or w.get("word") or "",
                "punctuated_word": w.get("punctuated_word") or w.get("word") or "",
                "speaker": int(w.get("speaker", 0) or 0),
                "_source_start": max(ws, c_start),
                "_word_index": word_idx,
            })
        dur = effective_durations[i] if i < len(effective_durations) else (c_end - c_start)
        output_cursor += dur
        if trans_dur_after is not None and i < len(trans_dur_after):
            output_cursor -= float(trans_dur_after[i] or 0.0)

    projected = [w for w in projected if w["end"] > w["start"]]
    return projected

def get_output_clip_ranges(cuts, effective_durations, transition_duration=None, trans_dur_after=None):
    """
    Return list of {"start": float, "end": float} for each clip's FULL
    output window (covering the cut's entire source range from c_start to
    c_end), used by all source-time → output-time projections (captions,
    SFX, B-roll, MGs).

    Overlap (handle) model: source_end[A] is extended forward upstream by
    trans_dur*speed at the handle-extension step, so eff_dur[A] grows by
    trans_dur. Cursor advances by eff_dur and subtracts trans_dur per
    transition. Adjacent clips overlap by trans_dur in this coordinate
    system; the slot lives ON the overlap, reading from each clip's
    handle frames. Total span = sum(eff_dur) - sum(trans_dur) =
    sum(original_eff) + sum(trans_dur), matching the ffmpeg-concat
    reality at ffmpeg_base.py:625 AND the audio path's contiguous
    crossfaded transition_audio.

    The 2026-06-14 zero-handle additive path was rolled back — it
    rendered glitched frames at tight cuts and grew output duration
    beyond audio.
    """
    _ = transition_duration  # API compat
    ranges = []
    cursor = 0.0
    for i, cut in enumerate(cuts):
        dur   = effective_durations[i] if i < len(effective_durations) else 0.0
        start = cursor
        end   = cursor + dur
        ranges.append({"start": start, "end": end})
        cursor += dur
        if trans_dur_after is not None and i < len(trans_dur_after):
            cursor -= float(trans_dur_after[i] or 0.0)
    return ranges


def build_clips_from_words(deepgram_words, remove_words, video_duration=0.0):
    """Apply Gemini's remove_words decisions and split kept words into clips.

    Gemini owns every cut decision; Python is a verbatim executor.
      - word_index entries → remove that word.
      - {after_word_index, before_word_index} entries → remove every word
        strictly between the anchors AND force a clip split at the boundary
        so the silence/content between the anchors is dropped from output.
      - Legacy {start, end} float ranges → remove every word fully contained.

    Clip-building rule (Step 2): walk the kept word list in order. Start a
    new clip whenever a removed word sits between adjacent kept words OR
    when an accepted range removal's anchors straddle the boundary. No
    silence threshold, no auto-tightening, no Python-side rule enforcement
    on top of Gemini's calls. If a render is too loose or too choppy, the
    fix is the prompt — not adding judgment layers in this function.

    Cut times are Deepgram word boundaries. The audio cut path uses
    round(t * sample_rate) for indexing, so the rendered splice lands
    at the exact sample. Every audio splice gets a 5 ms equal-power
    cos²/sin² crossfade in build_per_cut_audio.

    video_duration (when > 0) clamps every word's end timestamp so that
    no clip ever requests source frames past the actual end of the video.
    """
    if not deepgram_words:
        return []

    _vd = float(video_duration or 0.0)

    # ── Step 0: Prepare sorted word list with metadata ────────────────────
    def _clamp_end(_v):
        if _vd > 0 and _v > _vd:
            return _vd
        return _v

    sorted_words = sorted(
        [
            {
                **w,
                "_word_index": i,
                "_start": float(w.get("start") or 0.0),
                "_end": _clamp_end(float(w.get("end") or 0.0)),
                "_text": str(w.get("punctuated_word") or w.get("word") or "").strip(),
                "_clean": re.sub(r"[^a-z']", "", str(w.get("word") or w.get("punctuated_word") or "").strip().lower()),
            }
            for i, w in enumerate(deepgram_words)
        ],
        key=lambda w: w["_start"],
    )
    # Drop any word whose start is past video_duration entirely (rare edge case)
    if _vd > 0:
        sorted_words = [w for w in sorted_words if w["_start"] < _vd and w["_end"] > w["_start"]]

    removed_indices = set()

    # ── Step 1: Apply Gemini's remove_words ───────────────────────────────
    # Gemini's word removal decisions are trusted. No code-side validation
    # or rejection of filler calls — if Gemini says a word is filler, it is.
    # If filler detection is wrong, the fix is the prompt, not code heuristics.
    for item in remove_words or []:
        if not isinstance(item, dict):
            continue
        if "word_index" in item:
            try:
                idx = int(item["word_index"])
            except Exception:
                continue
            if not (0 <= idx < len(sorted_words)):
                continue
            removed_indices.add(idx)

    # ── Step 1b: Range removals — index-based AND legacy float-range ──────
    # Index-based form: {"after_word_index": int, "before_word_index": int,
    #                    "reason": "..."}
    #   Removes every word with index strictly between (after, before).
    #   Boundary anchors are real word indices, so no float-precision risk.
    #   This is the canonical form Gemini emits in the post-v35 schema.
    #
    # Legacy float-range form: {"start": X, "end": Y, "reason": "..."}
    #   Removes every word whose [start, end] is FULLY CONTAINED in [X, Y].
    #   Strict containment is the protection that prevents Gemini's
    #   slightly-off timestamps from accidentally clipping content at the
    #   edges. Used by silence-tighten (Python-internal) and accepted for
    #   any cached pre-v35 plans.
    _range_removed_count = 0
    # Dead-air anchor pairs from Gemini. Each pair (_aw, _bw) means "drop
    # the silence between word[_aw].end and word[_bw].start." For
    # consecutive anchors (_bw == _aw + 1) there are zero words strictly
    # between, so Step 2 must still split the clip at this boundary or
    # the dead air plays through. Multi-word ranges (_bw > _aw + 1) already
    # force a split via the `removed_between` check in Step 2, but tracking
    # the anchors uniformly keeps the contract clean: every accepted
    # dead_air range becomes a clip break.
    _dead_air_split_pairs = set()
    for item in remove_words or []:
        if not isinstance(item, dict):
            continue
        if "word_index" in item and item["word_index"] is not None:
            continue  # already handled in Step 1
        _reason = str(item.get("reason") or "range_remove")
        # Prefer index-based when present.
        if (
            item.get("after_word_index") is not None
            and item.get("before_word_index") is not None
        ):
            try:
                _aw = int(item["after_word_index"])
                _bw = int(item["before_word_index"])
            except Exception:
                continue
            if _bw <= _aw:
                continue
            if _reason == "dead_air":
                _dead_air_split_pairs.add((_aw, _bw))
            for _w in sorted_words:
                _wi = _w["_word_index"]
                if _wi in removed_indices:
                    continue
                if _aw < _wi < _bw:
                    removed_indices.add(_wi)
                    _range_removed_count += 1
                    print(
                        f"[tighten] Word '{_w['_text']}' at {_w['_start']:.3f}s removed "
                        f"(inside {_reason} range word[{_aw}]→word[{_bw}])",
                        flush=True,
                    )
            continue
        if "start" in item and "end" in item:
            try:
                _r_start = float(item["start"])
                _r_end = float(item["end"])
            except Exception:
                continue
            if _r_end <= _r_start:
                continue
            for _w in sorted_words:
                if _w["_word_index"] in removed_indices:
                    continue
                # Strict containment: word must be entirely inside the range
                if _w["_start"] >= _r_start and _w["_end"] <= _r_end:
                    removed_indices.add(_w["_word_index"])
                    _range_removed_count += 1
                    print(
                        f"[tighten] Word '{_w['_text']}' at {_w['_start']:.3f}s removed "
                        f"(inside {_reason} range {_r_start:.3f}-{_r_end:.3f}s)",
                        flush=True,
                    )
    if _range_removed_count:
        print(f"[tighten] Range removals removed {_range_removed_count} word(s)", flush=True)

    # ── Step 2: Build clips from kept words ───────────────────────────────
    # Split rule: start a new clip whenever a removed word sits between two
    # adjacent kept words OR a Gemini dead_air range straddles the
    # boundary. Every other adjacent pair stays in the same clip. No
    # silence threshold, no auto-cut, no judgment layer — Gemini decides;
    # this function executes.
    kept_words = [w for w in sorted_words if w["_word_index"] not in removed_indices]

    if not kept_words:
        return []

    clips = []
    current_words = [kept_words[0]]

    for prev, curr in zip(kept_words, kept_words[1:]):
        # Speaker-overlap guard. kept_words is time-sorted; with multi-speaker
        # recordings, two adjacent entries can be contemporaneous
        # (curr.start < prev.end). Splitting between them would produce
        # overlapping source ranges and trip the non-overlap invariant
        # below. Keep them in the same clip regardless — this is not a
        # judgment call, it's a defensive guard against contemporaneous
        # multi-speaker words.
        if curr["_start"] < prev["_end"]:
            current_words.append(curr)
            continue

        # Removed word between the two adjacent kept words → MUST split, or
        # the clip's audio range spans the removed word and its audio
        # bleeds through (e.g. "shou-" before "shouldn't").
        removed_between = any(
            idx in removed_indices
            for idx in range(prev["_word_index"] + 1, curr["_word_index"])
        )

        # Gemini-flagged dead_air boundary straddles this pair → split.
        dead_air_split = any(
            _aw <= prev["_word_index"] and _bw >= curr["_word_index"]
            for (_aw, _bw) in _dead_air_split_pairs
        )

        if removed_between or dead_air_split:
            clips.append(current_words)
            current_words = [curr]
        else:
            current_words.append(curr)

    if current_words:
        clips.append(current_words)

    # ── Step 3: Build raw clips at exact word boundaries ──────────────────
    # Word timestamps come directly from Deepgram Nova-3 (single ASR source
    # of truth as of 2026-05-23). Nova-3's word boundaries have ±50-150ms
    # natural variance; cutting at exact boundaries is safe given the 5ms
    # equal-power audio crossfade applied at each splice. The render
    # pipeline is sample-accurate end-to-end.
    raw_clips = []
    for word_group in clips:
        first_start = word_group[0]["_start"]
        last_end = word_group[-1]["_end"]
        raw_clips.append({
            "raw_start": first_start,
            "raw_end": last_end,
            "padded_start": first_start,
            "padded_end": last_end,
            "first_word": word_group[0]["_text"],
            "last_word": word_group[-1]["_text"],
            "word_count": len(word_group),
        })

    # ── Step 4: tail-pad the FINAL clip ───────────────────────────────────
    # Every clip ends at its last word's Deepgram word-END, which marks the
    # phoneme boundary and runs early on a final / elongated word — so the
    # VIDEO's last word loses ~0.3-0.5s of audible release ("cuts off the
    # last word"). Interior clip-ends sit at removed / dead-air boundaries and
    # must NOT be padded (they'd bleed the cut audio back in), so pad ONLY the
    # last clip, ONLY when nothing was removed after its final word (else the
    # trailing cut is intentional), and never past the true video end (_vd).
    _FINAL_TAIL_PAD_S = 0.5
    if raw_clips and clips:
        _last_src_idx = clips[-1][-1]["_word_index"]
        _trailing_removed = any(idx > _last_src_idx for idx in removed_indices)
        if not _trailing_removed:
            _cur_end = raw_clips[-1]["padded_end"]
            _cap = _vd if _vd > 0 else (_cur_end + _FINAL_TAIL_PAD_S)
            _new_end = min(_cur_end + _FINAL_TAIL_PAD_S, _cap)
            if _new_end > _cur_end:
                print(
                    f"[clips] tail-pad final clip {_cur_end:.3f}→{_new_end:.3f}s "
                    f"(last word '{raw_clips[-1]['last_word']}' release; _vd={_vd:.3f})",
                    flush=True,
                )
                raw_clips[-1]["padded_end"] = _new_end

    # ── Step 5: Non-overlap invariant ─────────────────────────────────────
    # Clips are derived from sorted word groups with strictly non-overlapping
    # source ranges. If two adjacent clips overlap, the derivation logic is
    # broken. Fail loudly instead of silently splitting at the midpoint.
    for i in range(1, len(raw_clips)):
        if raw_clips[i]["padded_start"] < raw_clips[i - 1]["padded_end"]:
            raise RuntimeError(
                f"build_clips_from_words invariant violated: clip {i-1} "
                f"[{raw_clips[i-1]['padded_start']:.3f}-{raw_clips[i-1]['padded_end']:.3f}] "
                f"overlaps clip {i} "
                f"[{raw_clips[i]['padded_start']:.3f}-{raw_clips[i]['padded_end']:.3f}]. "
                f"This is a derivation bug — clips should never overlap."
            )

    # ── Build final clip dicts ────────────────────────────────────────────
    # Cut times are Deepgram word boundaries — used directly. The audio
    # cut path uses round(time * sample_rate) for indexing, so an
    # unrounded float here produces a sample-precise splice. Continuous-
    # speech splices are masked by the room-tone bridge logic in
    # build_per_cut_audio — see splice handling there.
    # No length floor — the renderer trusts whatever clip lengths the model
    # + Gemini produced. Only guard: skip degenerate (zero-or-inverted)
    # spans, which can only arise from FP edge cases against video_duration
    # clamping above.
    final_clips = []
    for rc in raw_clips:
        s = float(rc["padded_start"])
        e = float(rc["padded_end"])
        if _vd > 0 and e > _vd:
            e = float(_vd)
        if e <= s:
            continue
        final_clips.append({
            "source_start": s,
            "source_end": e,
            "transition_out": "none",
            "speed": 1.0,
        })

    # ── Summary ───────────────────────────────────────────────────────────
    total_kept = len(kept_words)
    total_words = len(sorted_words)
    total_source = sum(c["source_end"] - c["source_start"] for c in final_clips)

    all_removed = sorted(removed_indices)
    if all_removed:
        print(f"[tighten] REMOVED WORDS ({len(all_removed)}):", flush=True)
        for idx in all_removed:
            w = sorted_words[idx]
            print(f"[tighten]   [{idx}] '{w['_text']}' @ {w['_start']:.3f}s", flush=True)

    print(
        f"[tighten] {total_words} words → {total_kept} kept "
        f"({len(all_removed)} Gemini removals), "
        f"{len(final_clips)} clips, {total_source:.2f}s output",
        flush=True,
    )

    # Caption projection / SFX snapping consume this set so they walk the
    # same kept-word list the splicer used.
    return final_clips, set(removed_indices)


def build_clip_time_map(clip_start, clip_end, clip_speed, fps=60):
    """Build a canonical per-frame time map for one clip.

    Single source of truth for time mapping. All systems (FFmpeg setpts,
    caption projection, SFX/B-roll projection, audio resampling) derive
    their timing from this same table.

    Each clip plays at one constant speed (`clip_speed`). The map is
    therefore trivial:
        eff_dur = source_dur / clip_speed
        avg_speed = clip_speed
        n_frames = round(source_dur * fps)
        output_times[k] = k * eff_dur / n_frames     for k in [0..n_frames]

    Returns dict with: output_times, effective_duration, avg_speed,
    n_frames, source_dur.
    """
    source_dur = clip_end - clip_start
    if source_dur <= 0.001:
        return {
            "output_times": [0.0, max(source_dur, 0.001)],
            "effective_duration": max(source_dur, 0.001),
            "avg_speed": clip_speed,
            "n_frames": 1,
            "source_dur": source_dur,
        }

    speed = max(0.25, min(4.0, clip_speed))
    n_frames = max(1, round(source_dur * fps))
    eff_dur = source_dur / speed
    output_times = [k * eff_dur / n_frames for k in range(n_frames + 1)]
    return {
        "output_times": output_times,
        "effective_duration": eff_dur,
        "avg_speed": speed,
        "n_frames": n_frames,
        "source_dur": source_dur,
    }


def _time_map_lookup(tm, source_offset):
    """Look up output time from a clip time map given a source offset (seconds from clip start).
    Uses constant avg_speed to exactly match FFmpeg's setpts=(1/avg_speed)*PTS."""
    if source_offset <= 0:
        return 0.0
    avg_speed = tm["avg_speed"]
    return source_offset / avg_speed if avg_speed > 0 else source_offset


def project_source_time_to_output(source_t, cuts, clip_ranges, clip_time_maps=None):
    """Map a source-timeline timestamp to the output-timeline timestamp.
    Uses canonical time maps for exact alignment with FFmpeg.

    clip_time_maps is REQUIRED — each cut's avg_speed comes from there,
    matching FFmpeg's setpts exactly.

    Cuts are non-overlapping in source time, so each source timestamp falls
    into at most one cut's source range. The loop assigns to the LAST
    matching cut (no overlap means there's only one), and returns its
    output position via the cut's time map."""
    if not clip_time_maps:
        raise ValueError("project_source_time_to_output requires clip_time_maps")
    best_output_t = None
    for i, cut in enumerate(cuts):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])

        if src_start <= source_t <= src_end:
            source_offset = source_t - src_start
            local_offset = _time_map_lookup(clip_time_maps[i], source_offset)
            best_output_t = float(clip_ranges[i]["start"]) + local_offset

    if best_output_t is not None:
        return best_output_t

    return None


def project_source_time_to_final_output(source_t, cuts, effective_durations, clip_time_maps=None):
    """Map a source timestamp to the final output timeline after cut compression."""
    clip_ranges = get_output_clip_ranges(cuts, effective_durations)
    return project_source_time_to_output(source_t, cuts, clip_ranges, clip_time_maps=clip_time_maps)


def compute_effective_durations(cuts, fps=60):
    """Compute output duration for each clip using canonical time maps."""
    durations = []
    for cut in (cuts or []):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])
        clip_speed = float(cut.get("speed") or 1.0)
        tm = build_clip_time_map(src_start, src_end, clip_speed, fps=fps)
        durations.append(tm["effective_duration"])
    return durations


def render_multi_clip(source_path, cuts, edit_plan, output_path, transcript, work_dir, speech_segments=None,
                      broll_clips=None):
    """
    Remotion-primary render path.

    Single `renderMedia` call produces a silent mp4 containing:
      - source video clips (seeked + speed-warped via `<OffthreadVideo>`)
      - per-clip zoom effects (pack zoom components)
      - global color effect wrapper (pack color-effect components)
      - clip-to-clip transitions (pack transition components)
      - B-roll cutaways (absolute-positioned `<Sequence>` overlays)
      - captions (pack caption style)
      - motion graphics overlays (pack motion-graphics components)

    Audio pipeline (ffmpeg) runs in parallel and produces a final AAC track:
      - numpy per-cut resampled source audio (pitch-scaling exactly matching
        each cut's playbackRate)
      - SFX mix with onset compensation + output-timeline projection
      - voice ducking at SFX onsets
      - adaptive EQ + double-compressor voice chain

    Final step: ffmpeg mux — stream-copy video chunks + AAC-encode the PCM
    audio inline so `-shortest` can trim to exact video duration.
    """
    import math

    # ── 0. Source is already canonical ──────────────────────────────────────
    # The ingest pass (_do_fps_normalize in mega_pool) folded fps + scale +
    # crop + pix_fmt into a single transcode and produced source_canonical.mp4.
    # By the time we get here, source_path is a 1080x1920 60fps yuv420p h264
    # file. Nothing in this function needs to re-normalize the source.

    # ── 1. Pre-render clip setup ────────────────────────────────────────────
    print(
        f"[render] transition natural durations: "
        f"{', '.join(f'{k}={v}ms' for k, v in sorted(TRANSITION_NATURAL_DURATION_MS.items(), key=lambda kv: kv[1]))}",
        flush=True,
    )

    render_cuts = list(cuts)

    # Tag clips with _original_idx for downstream lookups.
    for _idx, _rc in enumerate(render_cuts):
        _rc["_original_idx"] = _idx

    # Source fps detection (unified timeline)
    render_source = source_path
    _cached = _probe_full(render_source)
    _vs = next((s for s in (_cached.get("streams") or []) if s.get("codec_type") == "video"), {})
    print(f"[DIAG] Render source: codec={_vs.get('codec_name')} pix_fmt={_vs.get('pix_fmt')} fps={_vs.get('r_frame_rate')}", flush=True)
    _src_fps_str = _vs.get("r_frame_rate") or "30/1"
    try:
        if "/" in _src_fps_str:
            _num, _den = _src_fps_str.split("/")
            source_fps = float(_num) / float(_den)
        else:
            source_fps = float(_src_fps_str)
    except Exception:
        source_fps = 30.0
    if source_fps <= 0 or source_fps > 240:
        source_fps = 30.0
    print(f"[render] Unified source fps: {source_fps:.4f} (raw: {_src_fps_str})", flush=True)

    sample_rate = probe_audio_sample_rate(source_path) or 48000

    # ── Build canonical time maps per cut (SSOT for video + audio) ──────────
    # No sub-clip splitting, no speed-curve interpolation. Each cut has a
    # single constant speed; its time map is trivial (source_dur / speed).
    # Audio uses the same map. There is exactly one render segment per cut.
    # Render frame counts (after handle trim for transitions) are computed
    # below in the overlap-model block.
    _clip_time_maps = []
    effective_durations = []
    for _rc in render_cuts:
        _tm = build_clip_time_map(
            float(_rc["source_start"]),
            float(_rc["source_end"]),
            float(_rc.get("speed") or 1.0),
            fps=source_fps,
        )
        _clip_time_maps.append(_tm)
        effective_durations.append(_tm["effective_duration"])

    edit_plan["_render_cuts"] = render_cuts
    edit_plan["_render_effective_durations"] = effective_durations
    edit_plan["_render_clip_time_maps"] = _clip_time_maps

    # ── NLE "End at Cut" transition model — tail-handle anchored ────────────
    # Professional NLEs (Premiere, Resolve, Final Cut, Avid) render visual
    # transitions over a clip's TAIL HANDLE — the source media past the
    # visible cut point — not over the clip's visible/spoken content. This
    # is the universal default; the alternative ("eat into spoken content
    # by trans_dur") visibly clips the last syllable of the outgoing line
    # under the wipe while leaving its audio intact, producing the
    # "word visually clipped but still audible" symptom.
    #
    # Implementation: at the kept-word boundary `c_end`, we extend each
    # transition-bearing clip's `source_end` FORWARD by `trans_dur*speed`
    # into the natural post-utterance pause. After extension:
    #   - render range [source_start, source_end_NEW − trans_dur*speed]
    #     = [source_start, original_word_end] = full kept spoken content
    #   - transition slot [source_end_NEW − trans_dur*speed, source_end_NEW]
    #     = [original_word_end, original_word_end + trans_dur*speed] = handle
    #
    # The audio L-cut path and the Remotion `clipAStartFromFrames` value
    # both slice `[c_end − trans_dur*speed, c_end]` — with extended c_end
    # they automatically pull handle audio/video instead of spoken content.
    # No further changes required in those code paths.
    #
    # Total output grows by sum(trans_dur) — each transition costs real
    # timeline space, matching NLE behavior. Transitions are no longer
    # "free" (they used to compress timeline by stealing from kept range).
    # Per-boundary transition duration: each transition type animates at
    # its OWN natural duration (TRANSITION_NATURAL_DURATION_MS). The
    # handle extension below sizes each side's trim to the natural duration
    # of whichever transition lands at that boundary, so the slot can play
    # the full unshortened animation arc. _T_trans is no longer a global —
    # _natural_trans_dur_for_cut returns the per-cut value.
    _MIN_RENDER_DUR = 0.05  # min seconds of spoken content per shot

    def _has_real_transition(_rc):
        return str(_rc.get("transition_out") or "none") in VALID_TRANSITION_TYPES

    def _natural_trans_dur_for_cut(_rc):
        """Returns the natural-duration (seconds) of the transition emitted
        on this cut's `transition_out` field. Zero for cuts without a real
        transition. Used as the handle-extension size on the cut's tail
        AND on the next cut's head (both sides of the shared boundary)."""
        _t_raw = str(_rc.get("transition_out") or "none")
        if _t_raw not in VALID_TRANSITION_TYPES:
            return 0.0
        return get_transition_duration(_t_raw)

    # ── HANDLE MODEL — Premiere / FCP / Resolve default for talking-head ─────
    # Every transition reads from the natural pause AFTER cut A's last kept
    # word and BEFORE cut B's first kept word (the "handle"). The audio of
    # both clips plays its FULL kept range; no word is ever consumed by a
    # transition's crossfade. The CUT BOUNDARIES filter upstream guarantees
    # the boundary has at least trans_dur of audio gap, so the handle is
    # available silence — what the speaker did between thoughts (breath,
    # lip-close, beat). This is what pro NLEs do by default.
    #
    # For a transition between clips A and B:
    #   trim_tail_dur[A] = trans_dur (slot consumes A's tail handle)
    #   trim_head_dur[B] = trans_dur (slot consumes B's head handle)
    #   Source ranges are EXTENDED so the trims consume HANDLE silence
    #   instead of kept content:
    #     A.source_end  → original_end_A + trans_dur*speed_A
    #     B.source_start → original_start_B - trans_dur*speed_B
    #   A's main playback: source[cs_A, original_end_A]           — full kept content
    #   Transition slot:  A reads source[original_end_A, original_end_A + trans_dur*speed_A]  (HANDLE)
    #                     B reads source[original_start_B - trans_dur*speed_B, original_start_B]  (HANDLE)
    #     animates between them over trans_dur output frames
    #   B's main playback: source[original_start_B, ce_B]         — full kept content
    #
    # Total output = sum(kept_clip_durs) + sum(trans_durs) — handles add slot
    # time. Boundaries without enough handle (gap < trans_dur) are filtered
    # out of CUT BOUNDARIES; Gemini doesn't transition there.
    _trim_head_dur = [0.0] * len(render_cuts)
    _trim_tail_dur = [0.0] * len(render_cuts)
    for _i in range(len(render_cuts)):
        _has_out = _i < len(render_cuts) - 1 and _has_real_transition(render_cuts[_i])
        if _has_out:
            # Each boundary's handle size = the natural duration of THIS
            # boundary's transition type. SceneTitle gets 1800ms of handle
            # on each side; ZoomThrough gets 500ms. Both sides of the same
            # boundary use the same value (it's the same animation).
            _natural_here = _natural_trans_dur_for_cut(render_cuts[_i])
            _trim_tail_dur[_i] = _natural_here
            _trim_head_dur[_i + 1] = _natural_here

    # ── HANDLE EXTENSION — pro NLE model ────────────────────────────────────
    # Each transition extends both surrounding clips' source ranges INTO the
    # natural pause/silence between kept words, so trim_head/trim_tail consume
    # the HANDLE (post-utterance breath / pre-utterance silence) instead of
    # the last/first kept word. After extension:
    #   - Main render plays full kept content [original_cs, original_ce]
    #   - Transition slot reads handle source content:
    #       A's tail = source[original_ce, original_ce + trans_dur*speed]
    #       B's head = source[original_cs - trans_dur*speed, original_cs]
    #   - No kept word is ever crossfaded by a transition. Pro NLE default
    #     (Premiere, FCP, Resolve all do this).
    # Handle clamps: source bounds, AND the previous/next cut's original
    # source boundary to avoid reading into another clip's kept content.
    # The CUT BOUNDARIES filter (>=trans_dur audio gap) means valid
    # boundaries have at least trans_dur of handle room; tighter
    # boundaries don't get transitions at all.
    _source_duration_clamp = probe_duration(render_source) or 0.0

    # ── BOUNDARY REFINEMENT — audio-domain alignment to genuine silence ─────
    # Deepgram's word boundaries are ±50-150ms imprecise. A cut placed at
    # words[i].end can land mid-phoneme — clipping the natural release of
    # the last word OR including the onset of a removed filler. The result
    # is the audible glitch users perceive at filler-removal splices, even
    # with the splice fade applied.
    #
    # The fix: for each cut boundary that is a SPLICE (content removed
    # between cuts), search ±50ms around the Deepgram-marked time and
    # nudge the cut to the sample with the lowest local RMS energy. The
    # cut moves at most 50ms (below the perceptual threshold for editorial
    # timing shift) and consistently lands in genuinely quiet audio.
    # Editorial intent preserved; splices are between true silences.
    #
    # Audio is extracted once and reused by build_per_cut_audio downstream
    # via work_dir cache — no double extraction cost.
    _refinement_t0 = time.time()
    _refinement_audio_path = os.path.join(work_dir, "source_audio_full.wav")
    if not (os.path.exists(_refinement_audio_path) and os.path.getsize(_refinement_audio_path) > 1024):
        _refine_ext = subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-i", source_path, "-vn",
             "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
             _refinement_audio_path],
            capture_output=True, text=True, timeout=180,
        )
        if _refine_ext.returncode != 0 or not os.path.exists(_refinement_audio_path):
            raise RuntimeError(
                f"Source audio extraction for boundary refinement failed: "
                f"{(_refine_ext.stderr or '')[-500:]}"
            )

    import numpy as _np_refine
    import wave as _wave_refine
    with _wave_refine.open(_refinement_audio_path, "rb") as _wf_refine:
        _ref_channels = _wf_refine.getnchannels()
        _ref_n_samples = _wf_refine.getnframes()
        _ref_raw = _wf_refine.readframes(_ref_n_samples)
    _ref_audio = _np_refine.frombuffer(_ref_raw, dtype=_np_refine.int16).astype(_np_refine.float32)
    if _ref_channels > 1:
        _ref_audio = _ref_audio[::_ref_channels]

    # Refine each splice boundary. A splice is the boundary BETWEEN cut i
    # and cut i+1 (where content was removed). The very first cut's start
    # and the last cut's end are video edges, not splices, so they stay
    # untouched.
    _refinement_count = 0
    _refinement_total_shift_ms = 0.0
    _n_cuts_for_refine = len(render_cuts)
    for _ri in range(_n_cuts_for_refine):
        if _ri < _n_cuts_for_refine - 1:
            _orig_end = float(render_cuts[_ri]["source_end"])
            # source_end can only shift FORWARD into the removed-content
            # gap. Searching backward would land in the middle of the
            # last kept word's audio (between syllables, mid-vowel) and
            # clip its release tail.
            _refined_end = _refine_boundary_to_low_energy(
                _orig_end, _ref_audio, sample_rate,
                backward_radius_s=0.0, forward_radius_s=0.05,
            )
            # Cap so the refined end never crosses the next cut's start.
            _next_start = float(render_cuts[_ri + 1]["source_start"])
            if _refined_end > _next_start:
                _refined_end = _next_start
            _delta_ms = (_refined_end - _orig_end) * 1000.0
            if abs(_delta_ms) > 0.5:
                print(
                    f"[boundary-refine] cut={_ri} source_end "
                    f"{_orig_end:.4f}s → {_refined_end:.4f}s (Δ=+{_delta_ms:.1f}ms forward)",
                    flush=True,
                )
                _refinement_count += 1
                _refinement_total_shift_ms += abs(_delta_ms)
                render_cuts[_ri]["source_end"] = _refined_end
        if _ri > 0:
            _orig_start = float(render_cuts[_ri]["source_start"])
            # source_start can only shift BACKWARD into the removed-content
            # gap. Searching forward would land inside the first kept
            # word's audio (the user reported this clipping the "f" onset
            # of "five" when refinement nudged source_start +52ms into
            # the word).
            _refined_start = _refine_boundary_to_low_energy(
                _orig_start, _ref_audio, sample_rate,
                backward_radius_s=0.05, forward_radius_s=0.0,
            )
            # Cap so the refined start never crosses the previous cut's
            # (possibly already-refined) end.
            _prev_end = float(render_cuts[_ri - 1]["source_end"])
            if _refined_start < _prev_end:
                _refined_start = _prev_end
            _delta_ms = (_refined_start - _orig_start) * 1000.0
            if abs(_delta_ms) > 0.5:
                print(
                    f"[boundary-refine] cut={_ri} source_start "
                    f"{_orig_start:.4f}s → {_refined_start:.4f}s (Δ={_delta_ms:.1f}ms backward)",
                    flush=True,
                )
                _refinement_count += 1
                _refinement_total_shift_ms += abs(_delta_ms)
                render_cuts[_ri]["source_start"] = _refined_start

    _refinement_elapsed_ms = (time.time() - _refinement_t0) * 1000.0
    _avg_shift_ms = (
        _refinement_total_shift_ms / _refinement_count
        if _refinement_count > 0 else 0.0
    )
    print(
        f"[boundary-refine] {_refinement_count} splice boundary refinement(s), "
        f"avg |Δ|={_avg_shift_ms:.1f}ms, took {_refinement_elapsed_ms:.0f}ms",
        flush=True,
    )
    # Free the in-memory audio buffer; build_per_cut_audio re-reads the
    # cached wav from disk (extraction cost is already paid above).
    del _ref_audio

    # Snapshot ORIGINAL source ranges before mutating — clamps below need
    # the next/prev cut's original (pre-extension) boundary.
    _orig_source_starts = [float(_rc["source_start"]) for _rc in render_cuts]
    _orig_source_ends = [float(_rc["source_end"]) for _rc in render_cuts]
    for _i, _rc in enumerate(render_cuts):
        _speed_i = float(_rc.get("speed") or 1.0)
        _has_out_here = _trim_tail_dur[_i] > 0
        _has_in_here = _trim_head_dur[_i] > 0
        if _has_in_here:
            # Extend source_start backward into pre-utterance handle.
            # CRITICAL: when the PREVIOUS cut also extends (paired transition
            # at this boundary), split the gap evenly — each side takes at
            # most gap/2 — so the two source ranges never cross. The old
            # logic clamped each side to the opposite cut's ORIGINAL boundary,
            # which for any gap < 2*trans_dur caused both extensions to
            # CROSS each other and produced overlapping source ranges →
            # audio drift, "transition rendered twice" glitches.
            #
            # Wanted extension size: the natural duration of THIS boundary's
            # transition (stored in _trim_head_dur[_i] above).
            _wanted_ext = _trim_head_dur[_i] * _speed_i
            _max_ext_backward = _wanted_ext
            if _i > 0:
                _gap_prev = max(0.0, _orig_source_starts[_i] - _orig_source_ends[_i - 1])
                _prev_extends = _trim_tail_dur[_i - 1] > 0
                _max_ext_backward = (_gap_prev / 2.0) if _prev_extends else _gap_prev
            # Also can't go below source 0
            _max_ext_backward = min(_max_ext_backward, _orig_source_starts[_i])
            _ext = min(_wanted_ext, max(0.0, _max_ext_backward))
            _rc["source_start"] = _orig_source_starts[_i] - _ext
        if _has_out_here:
            # Extend source_end forward into post-utterance handle. Same
            # gap-sharing rule as backward; wanted size is THIS boundary's
            # natural transition duration.
            _wanted_ext = _trim_tail_dur[_i] * _speed_i
            _max_ext_forward = _wanted_ext
            if _i + 1 < len(render_cuts):
                _gap_next = max(0.0, _orig_source_starts[_i + 1] - _orig_source_ends[_i])
                _next_extends = _trim_head_dur[_i + 1] > 0
                _max_ext_forward = (_gap_next / 2.0) if _next_extends else _gap_next
            # Clamp to source duration so we don't read past the file
            if _source_duration_clamp > 0:
                _max_ext_forward = min(_max_ext_forward, _source_duration_clamp - _orig_source_ends[_i])
            _ext = min(_wanted_ext, max(0.0, _max_ext_forward))
            _rc["source_end"] = _orig_source_ends[_i] + _ext
    # Recompute trim_h/trim_t (OUTPUT seconds) to the actual handle obtained
    # after clamps. The trims drive the main render's source slice
    # (render_src_start = src_start + trim_h*speed) and must equal the
    # source-time extension divided by speed. When clamps reduce the
    # extension (source bounds, neighbor clip), the trim shrinks
    # proportionally so render still starts at the original first-word time.
    for _i, _rc in enumerate(render_cuts):
        _speed_i = float(_rc.get("speed") or 1.0)
        _trim_head_dur[_i] = max(0.0, (_orig_source_starts[_i] - float(_rc["source_start"])) / _speed_i)
        _trim_tail_dur[_i] = max(0.0, (float(_rc["source_end"]) - _orig_source_ends[_i]) / _speed_i)

    # Final transition durations after drops (used by audio + projection).
    # Slot's actual duration is the SHARED handle window between cut[i]'s
    # tail trim and cut[i+1]'s head trim, capped at the transition's natural
    # duration. In the normal case (Gemini placed the transition only where
    # gap >= 2 × natural_duration, per the prompt rule) the slot equals the
    # natural duration; source-bounds clamps or Gemini-violations shrink it.
    # If the slot collapses to zero (tight cut, no handle available), the
    # transition emission at the per-transition build below skips it — the
    # boundary plays as a hard cut, which is the editorially-correct fallback
    # when there's no handle room to play any animation. The 2026-06-14
    # additive/freeze-frame path was rolled back: the freeze-frame trick
    # (playbackRate≈0.048) rendered a glitched static frame in production
    # and the additive insertion grew output duration ~1s beyond content.
    # Zero-handle transitions at tight cuts are NOT supported in this model.
    _trans_dur_after = []
    _trans_frames_after = 0
    for _i, _rc in enumerate(render_cuts):
        _has_out = _i < len(render_cuts) - 1 and _has_real_transition(_rc)
        if _has_out:
            _natural_here = _natural_trans_dur_for_cut(_rc)
            _slot = min(_natural_here, _trim_tail_dur[_i], _trim_head_dur[_i + 1])
            _slot_frames = max(1, int(round(_slot * source_fps)))
            _trans_dur_after.append(_slot)
            _trans_frames_after += _slot_frames
        else:
            _trans_dur_after.append(0.0)

    # NOTE: source_end is NOT extended in the compression model. A's source
    # range stays [cs_A, ce_A]. Its last trans_dur of source is consumed by
    # the transition slot via trim_tail_dur, not by extending into would-be
    # silence (which doesn't exist for shot-splits anyway).

    # Re-derive canonical time maps + effective_durations against extended
    # source_end. Every downstream consumer (audio slicing, Remotion clips,
    # word projection, clip ranges) reads from these — recomputing here
    # keeps the single-source-of-truth invariant intact.
    _clip_time_maps = []
    effective_durations = []
    for _rc in render_cuts:
        _tm = build_clip_time_map(
            float(_rc["source_start"]),
            float(_rc["source_end"]),
            float(_rc.get("speed") or 1.0),
            fps=source_fps,
        )
        _clip_time_maps.append(_tm)
        effective_durations.append(_tm["effective_duration"])
    edit_plan["_render_effective_durations"] = effective_durations
    edit_plan["_render_clip_time_maps"] = _clip_time_maps

    # Per-cut RENDER frame count (after handle trim).
    _per_cut_render_dur_frames: List[int] = []
    for _i in range(len(render_cuts)):
        _render_dur = effective_durations[_i] - _trim_head_dur[_i] - _trim_tail_dur[_i]
        _per_cut_render_dur_frames.append(max(1, int(round(_render_dur * source_fps))))

    # Total output = sum(render frames) + sum(trans frames)
    n = len(render_cuts)
    total_output_frames = max(1, sum(_per_cut_render_dur_frames) + _trans_frames_after)
    total_output_duration = total_output_frames / float(source_fps)

    # Output clip ranges — COMPRESSION model. Each cut's full output window
    # COVERS its trim_head handle (overlap with previous transition) and
    # trim_tail handle (overlap with next transition). Adjacent clips
    # OVERLAP in output time by trans_dur (the transition slot is shared).
    # Cursor advances by eff_dur per cut, then subtracts trans_dur_after
    # so the next clip starts trans_dur before this one's output_end —
    # matching the visual where the transition plays A's tail and B's
    # head over the overlap. The 2026-06-14 additive-kind branch (for
    # zero-handle transitions at tight cuts) was rolled back; only
    # overlap is supported now.
    _clip_ranges = get_output_clip_ranges(
        render_cuts, effective_durations,
        transition_duration=None,
        trans_dur_after=_trans_dur_after,
    )

    # Project Deepgram words onto output timeline (for captions + SFX + b-roll)
    _removed_word_indices = edit_plan.get("_removed_word_indices") or set()
    _projected_words = project_words_to_output(
        transcript, render_cuts, effective_durations,
        transition_duration=None, clip_time_maps=_clip_time_maps,
        removed_word_indices=_removed_word_indices, fps=source_fps,
        trans_dur_after=_trans_dur_after,
    )
    edit_plan["_projected_words"] = _projected_words
    _pw_by_idx = {pw["_word_index"]: pw for pw in _projected_words if pw.get("_word_index") is not None}

    # ── 2. Build Remotion input JSON ────────────────────────────────────────
    # Clips — one ClipSpec per cut (no sub-clip splitting). Zoom events are
    # ABSOLUTE-source-anchored: Gemini emits startMs / durationMs in absolute
    # source-time milliseconds (verified empirically from production renders).
    # Each cut projects events that overlap its source range into cut-local
    # OUTPUT frames using the cut's constant speed:
    #
    #   clip_local_output_ms = (event_abs_source_ms - clip_source_start_ms) / pbr
    #
    # AND we only attach zoomEffect to a cut if at least one event's output
    # range overlaps the cut's output window. Cuts that don't actually
    # contain the event window stay on the FFmpeg path — no wasteful
    # Remotion routing.
    #
    # Face trajectory feeds zoom-origin face-lock at the event loop
    # (see _resolve_zoom_origin). Pulled once here from edit_plan so the
    # per-event call is dict access only — no recomputation per zoom event.
    # Reuses the SPARSE existing trajectory per
    # feedback_no_face_detect_stride_change.md — no new face sampling.
    _face_trajectory = list(edit_plan.get("_face_trajectory") or [])
    clips_out = []
    for i, (rc, tm, eff_dur) in enumerate(zip(render_cuts, _clip_time_maps, effective_durations)):
        _pbr = float(tm.get("avg_speed") or 1.0)
        _trim_h = _trim_head_dur[i]
        _trim_t = _trim_tail_dur[i]
        # The clip's RENDER source range starts at source_start (trim_head=0
        # in the L-cut model) and is shortened by trim_tail*speed at the end
        # (the tail handle is rendered by the outgoing transition instead).
        _source_start_seconds = float(rc["source_start"]) + _trim_h * _pbr
        _source_start_frames = int(round(_source_start_seconds * source_fps))
        # ── DIAG PROBE 2: clip extraction frame mapping ──
        # Compares intended source_time → actual frame index → expected
        # wall-clock content. The |Δ| field shows how far the frame's
        # wall-clock content is from the intended source_time. Per-clip
        # rounding alone should keep |Δ| under 1000/source_fps/2 ms
        # (≈16.7ms at 30fps, ≈8.3ms at 60fps). Anything bigger points at
        # the source/canonical timeline being on a different reference.
        _clip_expected_wc = _source_start_frames / float(source_fps)
        _clip_err_ms = (_source_start_seconds - _clip_expected_wc) * 1000.0
        print(
            f"[clip-extract] clip={i} source_t={_source_start_seconds:.4f}s "
            f"start_frame={_source_start_frames} "
            f"expected_wallclock={_clip_expected_wc:.4f}s "
            f"|Δ|={_clip_err_ms:+.2f}ms pbr={_pbr:.3f}",
            flush=True,
        )
        _dur_frames = _per_cut_render_dur_frames[i]
        _orig_idx = rc.get("_original_idx")
        _clip_id_parts = [
            "clip",
            str(_orig_idx if _orig_idx is not None else i),
        ]
        _clip_spec = {
            "id": "-".join(_clip_id_parts),
            "startFromFrames": _source_start_frames,
            "playbackRate": round(_pbr, 6),
            "durationInFrames": _dur_frames,
        }
        _zoom = rc.get("_zoom_effect") or rc.get("zoom_effect")
        if isinstance(_zoom, dict) and _zoom.get("type") in VALID_ZOOM_TYPES:
            # Zoom events project against the clip's RENDER window, not its
            # full source window. Events whose source time falls inside the
            # trim_head or trim_tail handle ranges belong to the adjacent
            # transition (which is a separate Remotion render), not this clip.
            _clip_render_source_start_ms = _source_start_seconds * 1000.0
            _clip_render_output_ms = (_dur_frames / float(source_fps)) * 1000.0
            _raw_events = _zoom.get("events") or []
            _overlapping_events = []
            _clip_render_output_ms_int = int(round(_clip_render_output_ms))
            for _ev in _raw_events:
                if not isinstance(_ev, dict):
                    continue
                try:
                    _src_start_ms = float(_ev.get("startMs", 0))
                    _src_dur_ms = float(_ev.get("durationMs", 0))
                    _new_start_ms = int(round(
                        (_src_start_ms - _clip_render_source_start_ms) / _pbr
                    ))
                    _new_dur_ms = int(round(_src_dur_ms / _pbr))
                except Exception:
                    continue
                if _new_dur_ms <= 0:
                    continue
                # Clamp the event into the clip's render window instead of
                # silently dropping it. The owning clip was assigned by the
                # earlier collision logic based on em.t; events can land
                # slightly outside that clip's bounds if Gemini emitted a
                # lead-in `startMs` that straddles a cut. Preserving the zoom with
                # shifted timing is preferable to silently dropping the
                # entire emphasis — the visual punch still fires, just
                # bounded to where the speaker is on screen.
                if _new_start_ms < 0:
                    # Event begins before the clip — shift start to 0,
                    # let the duration absorb the offset.
                    _new_dur_ms = max(0, _new_dur_ms + _new_start_ms)
                    _new_start_ms = 0
                if _new_start_ms >= _clip_render_output_ms_int:
                    # Event begins at or after the clip ends — move it to
                    # the back of the clip so it actually plays. Cap the
                    # duration at half the clip (or 200ms minimum) so we
                    # don't stretch a 200ms zoom into the whole clip.
                    _new_dur_ms = min(
                        _new_dur_ms,
                        max(200, _clip_render_output_ms_int // 2),
                    )
                    _new_start_ms = max(0, _clip_render_output_ms_int - _new_dur_ms)
                elif _new_start_ms + _new_dur_ms > _clip_render_output_ms_int:
                    # Event extends past the clip — clamp the tail.
                    _new_dur_ms = _clip_render_output_ms_int - _new_start_ms
                if _new_dur_ms < 100:
                    # Less than 100ms of zoom isn't perceptible — skip.
                    continue
                # Origin resolution: fulfill the prompt's contract at
                # handler.py:~2980 ("the pipeline runs face detection at
                # the event's start frame to lock the zoom origin onto
                # the face"). For face zooms (Gemini omitted originX/Y),
                # look up the smoothed trajectory at the event's source
                # time and lock to the face's eye line. For explicit
                # origins (non-face elements), pass them through verbatim.
                # No-face-box fallbacks to (0.5, 0.5) emit a divergence
                # so the gap is visible.
                _event_source_t = _src_start_ms / 1000.0
                _resolved_ox, _resolved_oy, _face_locked = _resolve_zoom_origin(
                    _ev, _event_source_t, _face_trajectory,
                )
                _new_event = {
                    **_ev,
                    "startMs": _new_start_ms,
                    "durationMs": _new_dur_ms,
                    "originX": _resolved_ox,
                    "originY": _resolved_oy,
                }
                _overlapping_events.append(_new_event)
                _origin_src = (
                    "face_lock" if _face_locked
                    else "gemini_explicit" if _ev.get("originX") is not None
                    else "center_fallback"
                )
                print(
                    f"[zoom-event] clip={i} type={_zoom.get('type')} "
                    f"start={_new_start_ms}ms dur={_new_dur_ms}ms "
                    f"origin=({_resolved_ox:.3f},{_resolved_oy:.3f}) "
                    f"src={_origin_src}",
                    flush=True,
                )
            if _overlapping_events:
                _clip_spec["zoomEffect"] = {
                    "type": _zoom["type"],
                    "events": _overlapping_events,
                    **{k: v for k, v in _zoom.items() if k not in ("type", "events") and v is not None},
                }
        clips_out.append(_clip_spec)

    # Transitions live between cut[i] and cut[i+1] when the leading cut emits
    # transition_out. One transition per cut boundary (cuts are atomic now —
    # no more sub-clip skip-logic).
    transitions_out = []
    _skipped_zero_slot_transitions = 0
    for i in range(len(render_cuts) - 1):
        _t_raw = str(render_cuts[i].get("transition_out") or "none")
        if _t_raw not in VALID_TRANSITION_TYPES:
            continue
        # Use the ACTUAL slot duration (already capped at this transition's
        # natural duration above). When the handle gap is zero, the slot
        # collapses to zero — there's no source to read for the animation.
        # That should not happen if Gemini followed the rule (only emit
        # transitions where gap >= 2 × natural_duration), but the guard
        # remains as a safety net for impossible boundaries.
        _slot_dur = _trans_dur_after[i] if i < len(_trans_dur_after) else 0.0
        _slot_frames = max(0, int(round(_slot_dur * source_fps)))
        if _slot_frames <= 0:
            _skipped_zero_slot_transitions += 1
            print(
                f"[transition] {_t_raw} after clip {i} — SKIPPED (no handle "
                f"available; boundary plays as hard cut)",
                flush=True,
            )
            continue
        _clipA_pbr = float(_clip_time_maps[i].get("avg_speed") or 1.0)
        _clipB_pbr = float(_clip_time_maps[i + 1].get("avg_speed") or 1.0)
        _clipA_src_end = float(render_cuts[i]["source_end"])
        _clipB_src_start = float(render_cuts[i + 1]["source_start"])
        # Handle model — A's tail + B's head, both reading their respective
        # post/pre-utterance handle silence (not kept content). Source ranges
        # for A's tail and B's head match the audio model exactly:
        #   A_tail: [ce_A_extended − slot*speed_A, ce_A_extended]
        #   B_head: [cs_B_extended,                cs_B_extended + slot*speed_B]
        _clipA_start_from = max(0.0, _clipA_src_end - _slot_dur * _clipA_pbr)
        _clipA_start_from_frames = int(round(_clipA_start_from * source_fps))
        _clipB_start_from = max(0.0, _clipB_src_start)
        _clipB_start_from_frames = int(round(_clipB_start_from * source_fps))
        _trans_extras = render_cuts[i].get("_transition_extras") or {}
        transitions_out.append({
            "afterClipIndex": i,
            "type": _t_raw,
            "durationInFrames": _slot_frames,
            "clipAStartFromFrames": _clipA_start_from_frames,
            "clipBStartFromFrames": _clipB_start_from_frames,
            "clipAPlaybackRate": round(_clipA_pbr, 6),
            "clipBPlaybackRate": round(_clipB_pbr, 6),
            **_trans_extras,
        })
        print(f"[transition] {_t_raw} after clip {i} — {_slot_frames}f (natural {int(get_transition_duration(_t_raw) * 1000)}ms)", flush=True)

    # ── Tight-cut overlays — overlay-on-top-of-hard-cut decoration ──────────
    # Build tight-cut overlay specs from the boundary-keyed resolved list
    # (edit_plan["_resolved_tight_cut_overlays"], populated in generate_edit_
    # gemini). Each overlay attaches to a FRAME POSITION — the boundary word's
    # projected OUTPUT frame via _pw_by_idx — NOT a clip-pair. OverlayCutEffect
    # paints ON TOP of continuously-playing video; the cut underneath (baked
    # into the source) plays straight. Works for mid-clip boundaries with no
    # sub-clip split — the attachment fix. Empty/absent list ⇒ zero entries
    # (pre-overlay-identical).
    #
    # Per-type duration — signed off at natural durations from the isolation
    # tests: LightLeak / ShutterFlash / NewspaperWipe → 11 frames (180ms@60fps,
    # punctuation-flash), SceneTitle → 72 frames (1200ms@60fps, hold long enough
    # to read the title). Adding a new overlay means a new entry here.
    _TIGHT_CUT_OVERLAY_FRAMES_BY_TYPE = {
        "LightLeak":     11,
        "ShutterFlash":  11,
        "NewspaperWipe": 11,
        "SceneTitle":    72,
    }
    tight_cut_overlays_out = []
    for _ov in (edit_plan.get("_resolved_tight_cut_overlays") or []):
        _tco = str(_ov.get("type") or "").strip()
        if _tco not in VALID_TIGHT_CUT_OVERLAYS:
            continue
        _awi = _ov.get("after_word_index")
        # Project the boundary word to its OUTPUT frame. _pw_by_idx is keyed by
        # SOURCE word index (the space after_word_index lives in); ["end"] is
        # the word's output-timeline end in seconds = where the cut sits. This
        # resolves ANY boundary, including mid-clip ones with no split.
        _pw = _pw_by_idx.get(_awi)
        if _pw is None:
            print(
                f"[tight-cut-overlay] '{_tco}' after_word_index={_awi} — SKIPPED "
                f"(word not on output timeline — removed or off-clip)",
                flush=True,
            )
            continue
        _cut_seconds = float(_pw.get("end") or 0.0)
        _at_frame = int(round(_cut_seconds * source_fps))
        _dur_frames = _TIGHT_CUT_OVERLAY_FRAMES_BY_TYPE.get(_tco)
        if _dur_frames is None:
            # Registered in VALID_TIGHT_CUT_OVERLAYS but missing a duration —
            # adding an overlay must update BOTH places. Fail loud.
            raise RuntimeError(
                f"_TIGHT_CUT_OVERLAY_FRAMES_BY_TYPE has no entry for "
                f"{_tco!r}. Add the per-type duration here when registering "
                f"a new overlay name in VALID_TIGHT_CUT_OVERLAYS."
            )
        _spec = {
            "atFrame": _at_frame,
            "type": _tco,
            "durationInFrames": _dur_frames,
        }
        # SceneTitle extras (title required, label optional); other types none.
        for _k in ("title", "label"):
            _v = _ov.get(_k)
            if _v is not None:
                _spec[_k] = _v
        tight_cut_overlays_out.append(_spec)
        _extras_present = {
            _k: _ov.get(_k) for _k in ("title", "label") if _ov.get(_k) is not None
        }
        _extras_suffix = (
            " " + " ".join(f"{k}={v!r}" for k, v in _extras_present.items())
            if _extras_present else ""
        )
        print(
            f"[tight-cut-overlay] {_tco} at after_word_index={_awi} — "
            f"atFrame={_at_frame} ({_cut_seconds:.3f}s) "
            f"durationInFrames={_dur_frames}{_extras_suffix}",
            flush=True,
        )

    # ── 3. SFX collection (projected onto output timeline) ──────────────────
    # Each SFX entry produces a ffmpeg input + filter that delays + scales it
    # to an absolute output-timeline timestamp. Exactly the same logic as the
    # pre-Remotion pipeline, just no longer segment-aware.
    sfx_input_args = []
    sfx_filter_strs = []
    sfx_audio_labels = []
    sfx_timestamps = []
    _sfx_extra_idx = 0
    _speech_segs = speech_segments or (edit_plan.get("analysis_data") or {}).get("speech", {}).get("segments") or []

    # ── Cut-partner re-anchor map ───────────────────────────────────────────
    # An SFX is anchored to its trigger WORD's start; a tight-cut overlay /
    # transition is anchored to the CUT BOUNDARY (the before-cut word's output
    # END — _pw_by_idx[awi]["end"], the same value the overlay uses for atFrame
    # above). When an SFX sits on the boundary word (after_word_index) or the
    # first post-cut word (after_word_index+1), those two anchors drift apart by
    # ~the word's duration — the sound fires EARLY of the flash. Re-anchor those
    # — and ONLY those (exact boundary-word membership, never proximity) — to the
    # cut-boundary frame (atFrame) so the audible transient lands on the cut.
    # We target atFrame for EVERY type, NOT each overlay's measured visual-peak
    # frame: the per-type peaks differ from atFrame by at most ~1 frame
    # (ShutterFlash 0, LightLeak +9ms, NewspaperWipe -21ms), which is below
    # AV-sync perception and not worth coupling SFX timing to the overlay opacity
    # curves (they'd silently desync if the animations change). after_word_index
    # is read from the RESOLVED plan lists (the render lists drop it); it and
    # _sfx_wi are both source word indices in the SAME _pw_by_idx space. +1 lands
    # on the first post-cut word, whose start already ≈ the boundary, so re-
    # anchoring it is a near-no-op (harmless if +1 is removed/out-of-range — no
    # surviving SFX targets such a word). The boundary is the before-cut word's
    # end = a real hard cut even when a transition is render-skipped.
    _sfx_cut_anchor_t = {}  # source word_index -> re-anchored output time (seconds)

    def _register_cut_partner(_awi):
        if not isinstance(_awi, int):
            return
        _bpw = _pw_by_idx.get(_awi)
        if not _bpw:  # before-cut word not in output (shouldn't happen for a real cut)
            return
        _bf = int(round(float(_bpw.get("end") or 0.0) * source_fps))
        _bt = max(0.0, _bf / float(source_fps))
        _sfx_cut_anchor_t[_awi] = _bt          # SFX on the before-cut word
        _sfx_cut_anchor_t[_awi + 1] = _bt      # SFX on the first post-cut word

    for _ov in (edit_plan.get("_resolved_tight_cut_overlays") or []):
        _register_cut_partner(_ov.get("after_word_index"))
    for _tr in (edit_plan.get("transitions") or []):
        _register_cut_partner(_tr.get("after_word_index"))

    # Word-indexed SFX — exact timing from projected words
    parsed_sfx = edit_plan.get("_parsed_sound_effects", [])
    for _i, _sfx in enumerate(parsed_sfx):
        _sound_style = normalize_sfx_style(_sfx.get("sound") or "none")
        if _sound_style == "none":
            continue
        _sound_path = get_sfx_path(_sound_style)
        if not _sound_path:
            continue
        _sfx_wi = _sfx.get("_word_idx")
        _projected_t = None
        if _sfx_wi is not None:
            _pw = _pw_by_idx.get(_sfx_wi)
            if _pw:
                _projected_t = float(_pw["start"])
                # Cut-partnered SFX re-anchor: from the word START to the cut
                # boundary's visual-peak frame, so the transient lands on the
                # flash instead of ~one word-duration early. Exact membership
                # only — non-boundary SFX fall through unchanged.
                if _sfx_wi in _sfx_cut_anchor_t:
                    _reanchor_t = _sfx_cut_anchor_t[_sfx_wi]
                    print(
                        f"[sfx] re-anchor {_sound_style} word {_sfx_wi}: "
                        f"word-start {_projected_t:.3f}s → cut-boundary "
                        f"{_reanchor_t:.3f}s (cut-partnered)",
                        flush=True,
                    )
                    _projected_t = _reanchor_t
            else:
                _sfx_word = _sfx.get("word", "")
                print(f"[sfx] Skipping {_sound_style} on '{_sfx_word}' — word removed from output", flush=True)
                continue
        else:
            _source_t = float(_sfx.get("t") or 0.0)
            _projected_t = project_source_time_to_output(
                _source_t, render_cuts, _clip_ranges,
                clip_time_maps=_clip_time_maps,
            )
        if _projected_t is None:
            continue
        _onset = _SFX_ONSET_OFFSETS.get(_sound_style, 0.0)
        _ts = max(0.0, _projected_t - _onset)
        _offset_ms = round(_ts * 1000)
        _vol = get_sfx_volume(_sound_style, _ts, _speech_segs, is_text_overlay=False)
        sfx_input_args += ["-i", _sound_path]
        sfx_audio_labels.append(f"[timesfx{_i}]")
        sfx_filter_strs.append(f"[{_sfx_extra_idx + 1}:a]volume={_vol:.3f},adelay={_offset_ms}|{_offset_ms}[timesfx{_i}]")
        sfx_timestamps.append(_ts)
        _sfx_src_t = float(_sfx.get("t") or 0.0)
        print(f"[sfx] sound_effect: {_sound_style} vol={_vol:.3f} source={_sfx_src_t:.3f}s → output={_projected_t:.3f}s → onset_comp(-{_onset:.3f}s)={_ts:.3f}s", flush=True)
        _sfx_extra_idx += 1

    # ── 4. B-roll cutaways on output timeline ───────────────────────────────
    # broll_clips arrive here already verified (handler.handler() ran
    # prefetch_and_verify_broll before invoking us; only entries with a
    # downloaded + ffprobed asset survived). The block further below projects
    # each entry's word-anchored window to output time and appends a
    # BrollSpec to broll_out. broll_out is passed to PromptlyOverlay, whose
    # BrollLayer renders each cutaway full-canvas at the BOTTOM of the overlay
    # z-stack — UNDER captions/MGs (see PromptlyRender.tsx:565 + the BrollLayer
    # z-order note). The FFmpeg composite filtergraph does NOT composite B-roll
    # directly (see ffmpeg_base.py build_final_filtergraph: "B-roll is rendered
    # into the alpha overlay … this filtergraph does not composite B-roll").
    broll_out: List[dict] = []

    # ── 4b. Text overlays — variant dispatch ────────────────────────────────
    # Word-anchored: Gemini emits start_word_index + duration_seconds. Python
    # projects the anchor word's source-time start through cuts to get the
    # output-time start, then converts to frames. Overlay disappears after
    # duration_seconds of OUTPUT time (stable regardless of downstream speed
    # ramping on the anchor clip).
    text_overlays_out = []
    for _ov in (edit_plan.get("text_overlays") or []):
        _du = float(_ov["duration_seconds"])
        # Project by WORD INDEX, not by frozen source-time. The kept word's
        # output position is computed in _pw_by_idx against the actual
        # cut ranges, so anchor projection stays correct regardless of
        # any future cut-point refinement. SFX and B-roll already use
        # this pattern.
        _swi = _ov.get("start_word_index")
        _pw = _pw_by_idx.get(_swi) if _swi is not None else None
        if _pw is None:
            # Word is not in the projected-words map. Validator already
            # screens removed words — if we hit this it means the upstream
            # data is malformed.
            raise RuntimeError(
                f"text_overlays[{_ov.get('variant')}] start_word_index="
                f"{_swi} not in projected words. Validator should have "
                f"caught this — investigate validator/projector divergence."
            )
        _out_start = float(_pw["start"])
        _entry = {
            "variant": _ov["variant"],
            "fromFrame": int(round(_out_start * source_fps)),
            "durationInFrames": max(1, int(round(_du * source_fps))),
        }
        for _k, _v in _ov.items():
            if _k in ("variant", "start_word_index", "_source_start", "duration_seconds"):
                continue
            _entry[_k] = _v
        text_overlays_out.append(_entry)
        _src_t = float(_pw.get("_source_start") or 0.0)
        print(
            f"[text-overlay] {_ov['variant']} @ src={_src_t:.2f}s "
            f"→ out={_out_start:.2f}s for {_du:.2f}s",
            flush=True,
        )

    # ── 5. Caption segments projection (source → output timeline) ───────────
    # Build position segments FIRST so we can pass their output-time
    # boundaries into the page builder and force a page flush at every
    # position change. Without this, a page that spans a position
    # boundary gets assigned to whichever segment contains its midpoint
    # — but the page's start/end times don't move, so the page either
    # appears late, lingers past where it should end, or jumps from one
    # position to another mid-display. ("floating around / drift" the
    # user reported.)
    _caption_style = edit_plan["caption_style"]
    _caption_keywords = edit_plan["caption_keywords"]
    # User opted out of captions via vibe ("no captions", "don't add captions").
    # Force caption_pages empty downstream + keep style as "none" so the Remotion
    # caption renderer becomes a no-op for this video.
    _captions_disabled = str(_caption_style).strip().lower() == "none"
    _caption_extra_props = _resolve_caption_extra_props(_caption_style, _caption_keywords, edit_plan)
    # Each segment's from/to is in SOURCE seconds (pre-remove_words timeline).
    # Project each endpoint to OUTPUT seconds using the same canonical time
    # maps that drive captions / SFX / b-roll.
    _cps_raw = edit_plan["caption_position_segments"]
    caption_position_segments_out = []
    _position_boundaries_out_sec: List[float] = []  # output-time seconds where position changes
    for _cs in _cps_raw:
        _f_out = project_source_time_to_output(
            float(_cs["from_seconds"]), render_cuts, _clip_ranges,
            clip_time_maps=_clip_time_maps,
        )
        _t_out = project_source_time_to_output(
            float(_cs["to_seconds"]), render_cuts, _clip_ranges,
            clip_time_maps=_clip_time_maps,
        )
        if _f_out is None:
            _f_out = 0.0
        if _t_out is None:
            _t_out = total_output_duration
        _from_frame = max(0, int(round(_f_out * source_fps)))
        _to_frame = min(total_output_frames, int(round(_t_out * source_fps)))
        if _to_frame > _from_frame:
            caption_position_segments_out.append({
                "fromFrame": _from_frame,
                "toFrame": _to_frame,
                "position": _cs["position"],
            })
            # Capture inner boundaries (skip 0 and total_duration; those
            # don't split anything).
            if _f_out > 0.001 and _f_out < total_output_duration - 0.001:
                _position_boundaries_out_sec.append(_f_out)

    # Clip boundaries in OUTPUT seconds — every cut between two source clips
    # forces a caption page break so a single page never spans a transition.
    # Skip the final clip's end (= total duration) since there's no "next clip"
    # to break against. Without this, pages built from the kept transcript
    # could group the last word of clip A with the first word of clip B —
    # rendering both phrases on top of the transition between them.
    _clip_boundaries_out_sec = [
        float(_cr["end"]) for _cr in (_clip_ranges[:-1] if len(_clip_ranges) > 1 else [])
    ]
    if _captions_disabled:
        caption_pages = []
        print("[captions] caption_style='none' — user opted out; skipping caption pages", flush=True)
    else:
        caption_pages = _build_tiktok_pages_from_projected(
            _projected_words,
            max_words_per_page=3,
            position_boundaries_sec=sorted(set(_position_boundaries_out_sec)),
            clip_boundaries_sec=sorted(set(_clip_boundaries_out_sec)),
        )
    if not caption_position_segments_out:
        # The validator guarantees at least one segment covering [0, duration].
        # If projection produced nothing, it means total_output_frames is 0.
        raise RuntimeError("caption_position_segments projection produced no output frames")

    # ── 7. Motion graphics — word-anchored, output-projected, semantic-anchor-translated ─
    # Gemini emits start_word_index + end_word_index (plus optional
    # duration_seconds_override). Python projects the anchor words' source-time
    # boundaries through the cuts timeline to get output-frame start/end. The
    # SEMANTIC_TO_MG_ANCHOR map translates the semantic-zone anchor into the
    # MG pack's own MGAnchor vocabulary; components render against the full
    # canvas. Gemini owns the anchor choice — it watched the video at 5 fps
    # and picked an anchor that doesn't cover the speaker's face based on
    # the actual frames in the MG window.
    motion_graphics_out = []

    # ── Pre-compute boundary starts for MG floor extension cap ─────────────
    # A sub-2.5s MG window can't complete its entrance animation; the MG
    # glitches (entrance cut off, count-up never lands, label fade-in
    # truncated). The per-MG floor below extends short windows up to 2.5s
    # — but the extension MUST NOT push into a downstream component's
    # window, or downstream collision rules would silently drop that
    # component (B-roll, text-overlay, or other MG).
    #
    # `_boundary_starts_sec` lists the earliest occupied output time of
    # every scheduled component EXCEPT MGs (other MGs handled separately
    # with self-exclusion). Anchors map per component type:
    #   - broll       : `_start_word_kept` → kept-word.start
    #   - transition  : `after_word_index` → that word's END (the cut)
    #   - tight_cut   : `after_word_index` → that word's END (the cut)
    #   - text_overlay: `start_word_index` → that word's start
    #   - emphasis MG : `_emphasis_moments[i].word_indices[0]` → start
    _MG_MIN_DURATION_SECONDS = 2.5
    _boundary_starts_sec: list = []

    def _proj_word_start_sec(idx):
        _pw = _pw_by_idx.get(idx) if idx is not None else None
        return float(_pw["start"]) if _pw else None

    def _proj_word_end_sec(idx):
        _pw = _pw_by_idx.get(idx) if idx is not None else None
        return float(_pw["end"]) if _pw else None

    for _bc in (edit_plan.get("broll_clips") or []):
        if not isinstance(_bc, dict):
            continue
        _t = _proj_word_start_sec(_bc.get("_start_word_kept"))
        if _t is not None:
            _boundary_starts_sec.append(_t)
    for _tr in (edit_plan.get("transitions") or []):
        if not isinstance(_tr, dict):
            continue
        _t = _proj_word_end_sec(_tr.get("after_word_index"))
        if _t is not None:
            _boundary_starts_sec.append(_t)
    for _tco in (edit_plan.get("tight_cut_overlays") or []):
        if not isinstance(_tco, dict):
            continue
        _t = _proj_word_end_sec(_tco.get("after_word_index"))
        if _t is not None:
            _boundary_starts_sec.append(_t)
    for _to in (edit_plan.get("text_overlays") or []):
        if not isinstance(_to, dict):
            continue
        _t = _proj_word_start_sec(_to.get("start_word_index"))
        if _t is not None:
            _boundary_starts_sec.append(_t)
    for _em in (edit_plan.get("_emphasis_moments") or []):
        if not isinstance(_em, dict):
            continue
        if not _em.get("motion_graphic"):
            continue
        _wis = _em.get("word_indices") or []
        if not _wis:
            continue
        _t = _proj_word_start_sec(_wis[0])
        if _t is not None:
            _boundary_starts_sec.append(_t)

    # Other-MG starts indexed by position so the per-MG check can exclude
    # self (`mi != _i`) for the tie case (two MGs anchored on the same word).
    _other_mg_starts_sec: list = []
    for _mi, _mg_other in enumerate(edit_plan.get("motion_graphics") or []):
        if not isinstance(_mg_other, dict):
            continue
        _t = _proj_word_start_sec(_mg_other.get("start_word_index"))
        if _t is not None:
            _other_mg_starts_sec.append((_t, _mi))

    for _i, _mg in enumerate(edit_plan.get("motion_graphics") or []):
        # Project by WORD INDEX (start_word_index, end_word_index), not by
        # frozen source-time. _pw_by_idx contains every kept word's OUTPUT
        # position, computed against the REFINED clip ranges — so DSP
        # cut-point refinement of clip boundaries propagates to anchors
        # automatically. The previous source-time projection used the
        # original (unrefined) Deepgram word.start/word.end, which fell
        # OUTSIDE the refined clip range when DSP shifted source_start
        # forward into the kept word — projection returned None, MG was
        # dropped. Word-index lookup eliminates the drift.
        _swi = _mg.get("start_word_index")
        _ewi = _mg.get("end_word_index")
        _pw_start = _pw_by_idx.get(_swi) if _swi is not None else None
        _pw_end = _pw_by_idx.get(_ewi) if _ewi is not None else None
        if _pw_start is None or _pw_end is None:
            # Anchor word is not in the projected-words map. Validator
            # already screens removed words upstream — if we hit this it
            # means the upstream data is malformed.
            raise RuntimeError(
                f"motion_graphic {_mg['type']} word indices "
                f"start={_swi} end={_ewi} not in projected words. "
                f"Validator should have caught this — investigate "
                f"validator/projector divergence."
            )
        _out_start = float(_pw_start["start"])
        _out_end = float(_pw_end["end"])
        # Preserve _sw_source / _ew_source for the diagnostics print at the
        # bottom of the loop.
        _sw_source = float(_mg.get("_source_start") or 0.0)
        _ew_source = float(_mg.get("_source_end") or 0.0)
        # duration_seconds_override lets a fixed-length pin extend beyond the
        # natural word span. Anchor start unchanged; end = start + override.
        _dur_override = _mg.get("duration_seconds_override")
        if _dur_override is not None:
            _out_end = _out_start + float(_dur_override)

        # ── Minimum-duration floor (collision-aware) ───────────────────────
        # Extend short windows up to 2.5s so the MG's entrance animation
        # completes and the content stays on screen long enough to read.
        # 2.5s covers every existing MG's enter + readable hold + exit
        # budget (StatCard ~733ms anim + ~1s readable hold; StickyNotes
        # 3-note stagger ~1.5s entrance; ProgressBar/Notification similar).
        # The extension is CAPPED at the earliest downstream component
        # start so the floor can't silently push an MG into a B-roll or
        # overlay's window — that would invoke downstream collision rules
        # and drop the overlapped component invisibly.
        _floor_end_sec = _out_start + _MG_MIN_DURATION_SECONDS
        if _out_end < _floor_end_sec:
            _caps = [s for s in _boundary_starts_sec if s > _out_start]
            _caps += [s for s, mi in _other_mg_starts_sec if s > _out_start and mi != _i]
            _next_sec = min(_caps) if _caps else None
            if _next_sec is None:
                _out_end = _floor_end_sec
            else:
                _out_end = min(_floor_end_sec, _next_sec)

        _from_frame = max(0, int(round(_out_start * source_fps)))
        _to_frame = min(total_output_frames, int(round(_out_end * source_fps)))
        if _to_frame <= _from_frame:
            raise RuntimeError(
                f"motion_graphic {_mg['type']} window projects to 0 frames "
                f"(out_start={_out_start:.2f}s, out_end={_out_end:.2f}s, "
                f"total_output_frames={total_output_frames})"
            )
        _mg_anchor = SEMANTIC_TO_MG_ANCHOR[_mg["anchor"]]
        _mg_props = {**_mg["props"], "anchor": _mg_anchor}
        motion_graphics_out.append({
            "type": _mg["type"],
            "fromFrame": _from_frame,
            "durationInFrames": _to_frame - _from_frame,
            "props": _mg_props,
        })
        print(
            f"[mg] {_mg['type']} src=[{_sw_source:.2f}..{_ew_source:.2f}]s "
            f"→ out=[{_out_start:.2f}..{_out_end:.2f}]s anchor={_mg['anchor']}→{_mg_anchor}",
            flush=True,
        )

    # ── 7b. Emphasis moments → output-timeline effect specs ─────────────────
    # Each emphasis moment's visual layers (zoom / MG) get projected and
    # merged into the Remotion input here.
    for em in edit_plan.get("_emphasis_moments", []):
        # Project by WORD INDEX (first word in word_indices list), not by
        # frozen source-time. Same pattern as MG / text_overlay above and
        # SFX / B-roll elsewhere — _pw_by_idx is the canonical map of
        # kept words to their output positions.
        _em_word_indices = em.get("word_indices") or []
        _em_first_wi = _em_word_indices[0] if _em_word_indices else None
        _em_pw = _pw_by_idx.get(_em_first_wi) if _em_first_wi is not None else None
        if _em_pw is None:
            raise RuntimeError(
                f"Emphasis moment word_indices[0]={_em_first_wi} not in "
                f"projected words. Validator should have caught this — "
                f"investigate validator/projector divergence."
            )
        _em_t_out = float(_em_pw["start"])
        _em_t_frame = int(round(_em_t_out * source_fps))

        # Zoom is already attached to validated_cuts during the validation
        # phase (collision check at line ~4717), so it propagates to clips_out
        # naturally via final_cuts → render_cuts. No late attachment here —
        # that pattern silently lost every emphasis zoom because clips_out
        # was built before the mutation happened.

        # Motion graphic: append to motion_graphics_out, anchored at the moment.
        # Translate semantic anchor → MGAnchor. Gemini's anchor choice is
        # final — it watched the video and picked a zone that doesn't cover
        # the speaker's face at this moment.
        if em["motion_graphic"]:
            _em_dur = float(em["duration"])
            _mg_from_frame = max(0, _em_t_frame - int(round(_em_dur * source_fps * 0.25)))
            _mg_dur_frames = int(round(_em_dur * source_fps))
            _em_mg_anchor = SEMANTIC_TO_MG_ANCHOR[em["motion_graphic"]["anchor"]]
            _em_mg_props = {**em["motion_graphic"]["props"], "anchor": _em_mg_anchor}
            motion_graphics_out.append({
                "type": em["motion_graphic"]["type"],
                "fromFrame": _mg_from_frame,
                "durationInFrames": _mg_dur_frames,
                "props": _em_mg_props,
            })
            print(
                f"[emphasis-mg] {em['motion_graphic']['type']} @ {em['t']:.2f}s "
                f"-> output {_mg_from_frame}-{_mg_from_frame + _mg_dur_frames}f "
                f"anchor={em['motion_graphic']['anchor']}→{_em_mg_anchor}",
                flush=True,
            )

    # Z-order: Gemini owns MG-driven position changes. Per Rule #5 in the
    # prompt, when any MG covers the bottom band, Gemini emits a
    # caption_position_change to "top" for that window. Python does NOT
    # auto-flip for MG collisions — that stays Gemini's call.
    #
    # The exception is B-roll: B-roll renders as a full-canvas cutaway
    # (speaker disappears for the duration). Captions sitting at "bottom"
    # would land near the platform UI rail with the cutaway content behind
    # them; Python auto-flips position to "top" over every B-roll window
    # after the loop below — captions land in the upper-third safe zone
    # where they stay readable above the cutaway. See
    # _force_top_position_during_broll.

    # ── 8. Build Remotion inputs + stage source for the bundle server ──────
    # Visually-identical fast-path architecture (replaces v61 chunked render):
    #   • PromptlyOverlay        — captions + MG + text overlays on transparent
    #                              canvas. Rendered once, ProRes 4444 alpha.
    #   • PromptlyMicroSegments  — every transition (11 types) + composite-
    #                              effect zoom clips (FocusWindow / LetterboxPush
    #                              / DepthPull). Rendered once if any segment
    #                              needs it; segments are concatenated end-to-
    #                              end so a single Remotion process amortizes
    #                              the ~10s startup tax across all of them.
    #   • Base video             — clip cuts, simple zoom (SmoothPush /
    #                              StepZoom / StageZoom) ported to per-frame
    #                              `crop` expressions, B-roll cutaways, outro
    #                              fade. Built directly by FFmpeg in the final
    #                              composite pass.
    # Net: Remotion only paints the visual layers it has to (overlay +
    # complex-segment windows). FFmpeg handles every video-paint frame at
    # native speed (libx264 medium + lanczos resample on 64 cores).
    _outro = edit_plan.get("outro") or "none"

    from ffmpeg_base import (
        build_micro_segments_input, build_final_filtergraph, categorize_clip,
        slice_timeline_for_chunk, split_timeline_into_chunks,
    )

    # ── Structural integrity audit ──────────────────────────────────────────
    # Every Gemini-emitted layer that survived validation must reach the
    # output spec. These postconditions raise on phase-ordering bugs
    # immediately instead of letting the pipeline silently produce flat-
    # looking videos. No fallbacks, no buffers, no retries — fail loud on
    # internal mismatch so the next regression is impossible to miss.
    # Count zoom EVENTS (not clips), because multiple emphasis_moments on the
    # same clip are merged into one zoomEffect with multiple events. We want
    # to detect events that got silently dropped at render time (e.g., an
    # event projected entirely outside its clip's window), not flag the merge
    # as a loss.
    _expected_zoom_events = 0
    _seen_zoom_obj_ids = set()
    for em in (edit_plan.get("_emphasis_moments") or []):
        _z = em.get("zoom_effect")
        if not _z:
            continue
        # After the merge above, multiple emphasis_moments share the same
        # zoom_effect dict (mirrored back). Count its events once.
        _zid = id(_z)
        if _zid in _seen_zoom_obj_ids:
            continue
        _seen_zoom_obj_ids.add(_zid)
        _expected_zoom_events += len(_z.get("events") or [])
    _actual_zoom_events = sum(
        len((_c.get("zoomEffect") or {}).get("events") or [])
        for _c in clips_out
    )
    if _actual_zoom_events < _expected_zoom_events:
        print(
            f"[render] WARNING: {_expected_zoom_events - _actual_zoom_events} "
            f"zoom event(s) had no overlap with their clip's render window — "
            f"render continues without those events. "
            f"(expected {_expected_zoom_events}, actual {_actual_zoom_events})",
            flush=True,
        )
    # Also count clip-level zoomEffects for the integrity log below.
    _actual_zooms = sum(1 for _c in clips_out if _c.get("zoomEffect"))

    _expected_transitions = sum(
        1 for c in cuts
        if c.get("transition_out") and c.get("transition_out") != "none"
    )
    # Allow transitions to be silently downgraded to hard cuts when the
    # boundary has zero handle space (shot-splits where the sub-clips share
    # a source point). The skip count is tracked above; the remaining
    # transitions must all have reached the output spec.
    if len(transitions_out) + _skipped_zero_slot_transitions != _expected_transitions:
        raise RuntimeError(
            f"Pipeline integrity violation: transitions_out has "
            f"{len(transitions_out)} entries (+{_skipped_zero_slot_transitions} "
            f"skipped for zero-slot) but validated_cuts carries "
            f"{_expected_transitions} non-none transition_out fields. "
            f"Every validated transition must reach the output spec or be "
            f"explicitly skipped."
        )

    _expected_emphasis_mgs = sum(
        1 for em in (edit_plan.get("_emphasis_moments") or [])
        if em.get("motion_graphic")
    )
    _expected_top_mgs = len(edit_plan.get("motion_graphics") or [])
    _expected_total_mgs = _expected_top_mgs + _expected_emphasis_mgs
    if len(motion_graphics_out) != _expected_total_mgs:
        raise RuntimeError(
            f"Pipeline integrity violation: motion_graphics_out has "
            f"{len(motion_graphics_out)} entries but validation produced "
            f"{_expected_top_mgs} top-level + {_expected_emphasis_mgs} emphasis "
            f"MGs ({_expected_total_mgs} total). Every validated MG must reach "
            f"the output spec."
        )

    _expected_text_overlays = len(edit_plan.get("text_overlays") or [])
    if len(text_overlays_out) != _expected_text_overlays:
        raise RuntimeError(
            f"Pipeline integrity violation: text_overlays_out has "
            f"{len(text_overlays_out)} entries but validation produced "
            f"{_expected_text_overlays}. Every validated text overlay must "
            f"reach the output spec."
        )

    print(
        f"[integrity] All layers reached output spec: "
        f"{_actual_zooms} zoom(s), {len(transitions_out)} transition(s), "
        f"{len(motion_graphics_out)} MG(s), {len(text_overlays_out)} text overlay(s).",
        flush=True,
    )

    # Stage source video directly into Remotion's bundle public root with a
    # job-prefixed basename. Subdirectory layouts have caused 404s in past
    # bundle configs (staticFile + offthreadVideo proxy can drop directory
    # components in some Remotion versions), so we keep a flat layout here
    # and rely on the job_id-prefixed filename for uniqueness across
    # concurrent renders. Cleaned up at end-of-render.
    _bundle_public_root = "/remotion/bundle/public"
    _stage_key = os.path.basename(work_dir.rstrip("/")) or f"job-{int(time.time()*1000)}"
    # Side-channel directory for files we *don't* want Remotion to serve
    # (input JSONs etc.) — kept under work_dir so Remotion never sees them.
    _stage_dir = work_dir
    _staged_for_cleanup: list = []

    def _stage_file(src_abs_path, dest_basename=None):
        """Materialize `src_abs_path` into the bundle public root with a
        stage-key-prefixed basename. Returns the URL Remotion sees relative to
        publicDir (just the prefixed basename — staticFile resolves it to
        /<basename> served from /remotion/bundle/public/<basename>).

        `dest_basename` (optional): override the basename used for the staged
        file. Useful when the source file's basename collides with another
        stage call in the same render (e.g. two B-rolls whose 30-char-truncated
        keywords happen to slugify to the same thing). When None, falls back
        to `os.path.basename(src_abs_path)`."""
        if not os.path.exists(src_abs_path):
            raise RuntimeError(
                f"Cannot stage local file for Remotion: {src_abs_path} does not exist."
            )
        _orig = dest_basename or os.path.basename(src_abs_path)
        _name = f"{_stage_key}__{_orig}"
        _dst = os.path.join(_bundle_public_root, _name)
        if os.path.lexists(_dst):
            try:
                os.unlink(_dst)
            except OSError:
                pass
        try:
            os.link(src_abs_path, _dst)
        except OSError:
            shutil.copy2(src_abs_path, _dst)
        _staged_for_cleanup.append(_dst)
        return _name

    _source_url = _stage_file(source_path)
    print(f"[render] Staged source as {_source_url} (under {_bundle_public_root})", flush=True)

    # ── B-roll timing projection ────────────────────────────────────────────
    # Every entry in `broll_clips` has a `_local_path` pointing at a verified
    # asset (handler.handler() ran prefetch_and_verify_broll before calling
    # render_multi_clip; entries that didn't fetch or didn't ffprobe-validate
    # were dropped from the plan entirely). All this loop does is project
    # the entry's word-anchored window to output time and append a BrollSpec
    # to broll_out — no failure cases, no skipping.
    for _bc in (broll_clips or []):
        if not isinstance(_bc, dict):
            continue
        _local_path = _bc.get("_local_path")
        if not _local_path:
            # Defensive: the prefetch step only includes verified entries with
            # _local_path. If something slipped past, refuse the entry rather
            # than silently dropping it.
            continue
        _br_sw = _bc.get("_start_word_kept")
        _br_ew = _bc.get("_end_word_kept")
        if _br_sw is None or _br_ew is None:
            continue
        _pw_start = _pw_by_idx.get(_br_sw)
        _pw_end = _pw_by_idx.get(_br_ew)
        if not _pw_start or not _pw_end:
            continue
        _out_start = float(_pw_start["start"])
        _out_end = float(_pw_end["end"])
        if _out_start >= total_output_duration or _out_end <= _out_start:
            continue
        # ── Phrase-exact on-screen window ────────────────────────────
        # The cutaway plays for the EXACT span of the phrase it
        # illustrates — _pw_start.start (first word of phrase, output
        # time) to _pw_end.end (last word of phrase, output time).
        # Per user direction 2026-06-14: "on screen EXACTLY for the
        # phrase, not a ms too long or too soon." No lead-audio shift,
        # no tail extension, no min-duration padding. The previous
        # 0.4s lead + 0.2s tail + 0.8s min floor were overriding the
        # phrase boundary — a 1.76s phrase was being rendered as 2.0s
        # starting 0.4s early. The clip is trimmed (or held) to fit
        # the phrase duration, not the reverse.
        #
        # 2026-06-17 update: the MAX cap is a SANITY guard for
        # absurdly-long phrases, NOT a normal-phrase cap. It was 2.0s,
        # which was firing on routine 2-3s phrases (e.g. broll[0]
        # words 14-23 = 2.24s) and visibly shortening cutaways below
        # their planned phrase span. Raised to 6.0s so it only catches
        # a runaway phrase span; normal phrases render at their full
        # [first_word_start, last_word_end] duration with no clamp.
        #
        # Only safety caps remain:
        #   - MAX cap (6.0s) — runaway phrase guard only, never
        #     touches a normal-length phrase
        #   - Pexels-length cap further below (can't render more
        #     frames than the file has)
        #   - Runtime end cap further below (don't overshoot total)
        _BROLL_MAX_DUR = 6.0
        _word_span_eff = _out_end - _out_start
        _orig_out_start = _out_start
        _orig_out_end = _out_end
        _eff = _out_end - _out_start
        # Trim the TAIL when phrase exceeds MAX so the cutaway starts
        # on the first phrase word (never start before it).
        if _eff > _BROLL_MAX_DUR:
            _out_end = _out_start + _BROLL_MAX_DUR
            _eff = _BROLL_MAX_DUR
        _record_divergence(
            "broll_timing",
            {
                "word_span_start_s": round(_orig_out_start, 3),
                "word_span_end_s": round(_orig_out_end, 3),
                "word_span_dur_s": round(_word_span_eff, 3),
            },
            "phrase_exact_window",
            final={
                "onscreen_start_s": round(_out_start, 3),
                "onscreen_end_s": round(_out_end, 3),
                "onscreen_dur_s": round(_eff, 3),
            },
            reason="onscreen_equals_phrase_span",
        )
        _br_dur = get_video_duration(_local_path)
        # If the Pexels file is SHORTER than the word span, the
        # cutaway plays for the Pexels length (can't show more frames
        # than the file has). Logged as `clamped_to_pexels_length`.
        _clamp_reason = None
        if _br_dur > 0 and _eff > _br_dur:
            _eff = _br_dur
            _out_end = _out_start + _eff
            _clamp_reason = "clamped_to_pexels_length"
        if _out_start + _eff > total_output_duration:
            _eff = total_output_duration - _out_start
            _out_end = _out_start + _eff
            _clamp_reason = "clamped_to_runtime_end"
        if _eff <= 0.05:
            continue
        _seek_seconds = 0.0
        if _br_dur > _eff + 1.0:
            _seek_seconds = min(_br_dur * 0.25, max(0.0, _br_dur - _eff - 0.5))
        _from_frame = int(round(_out_start * source_fps))
        _dur_frames = max(1, int(round(_eff * source_fps)))
        _br_probe = _probe_full(_local_path)
        _br_vs = next((s for s in (_br_probe.get("streams") or []) if s.get("codec_type") == "video"), {})
        _br_fps_str = _br_vs.get("r_frame_rate") or "30/1"
        try:
            if "/" in _br_fps_str:
                _bn, _bd = _br_fps_str.split("/")
                _br_fps = float(_bn) / float(_bd) if float(_bd) > 0 else 30.0
            else:
                _br_fps = float(_br_fps_str)
        except Exception:
            _br_fps = 30.0
        if _br_fps <= 0 or _br_fps > 240:
            _br_fps = 30.0
        # Stage the B-roll into the bundle public dir so Remotion's BrollLayer
        # can resolve it via staticFile(). Use an explicitly indexed basename
        # so two B-rolls whose truncated-keyword slugs happen to collide (rare
        # but possible: see _download_and_validate_broll's safe_kw[:30] cap)
        # get distinct staged filenames within this render.
        _broll_idx_in_out = len(broll_out)
        _orig_local_name = os.path.basename(_local_path)
        _broll_dest_basename = f"broll_{_broll_idx_in_out:02d}_{_orig_local_name}"
        _broll_staged_basename = _stage_file(_local_path, dest_basename=_broll_dest_basename)
        broll_out.append({
            # `src` is the staged basename (e.g. "<job_id>__broll_00_...mp4").
            # FFmpeg reads it via os.path.join(_bundle_public_root, src);
            # Remotion BrollLayer resolves it via staticFile(src).
            "src": _broll_staged_basename,
            "fromFrame": _from_frame,
            "durationInFrames": _dur_frames,
            "seekFromSeconds": float(_seek_seconds),
            "brollFps": float(_br_fps),
            "playbackRate": 1.0,
        })
        edit_plan.setdefault("_broll_output_ranges", []).append((_out_start, _out_end))
        _kw = _bc.get("keyword", "")
        print(
            f"[broll] '{_kw}' out=[{_out_start:.2f}..{_out_end:.2f}]s "
            f"dur={_eff:.2f}s seek={_seek_seconds:.2f}s",
            flush=True,
        )
        # Divergence: every B-roll's word-span vs requested-duration vs
        # final-render-duration is visible. `kept` = no clamp fired;
        # `clamped_to_pexels_length` = source file shorter than word span;
        # `clamped_to_runtime_end` = word span past the end of output.
        _record_divergence(
            "broll",
            {
                "keyword": _kw,
                "word_span_s": round(_word_span_eff, 3),
                "requested_duration_s": round(float(_bc.get("duration") or 0.0), 3),
            },
            "clamped_to_word_span" if _clamp_reason is None else _clamp_reason,
            final={"final_duration_s": round(_eff, 3)},
            reason=(_clamp_reason or "kept"),
        )

    # ── Total-coverage ceiling — feedback_broll_coverage_not_a_target.md ───
    # ~10-15% B-roll coverage is normal; ~30-40% is a CEILING, not a target.
    # When Gemini's per-clip windows happen to add up past ~40% of runtime,
    # the rendered output reads as a stock-footage reel instead of a
    # talking-head edit. Enforce here: sort B-roll by output duration DESC
    # and drop the longest until the total is back under the ceiling. Each
    # drop logs via _record_divergence so the lost cutaway is visible.
    _BROLL_COVERAGE_CEILING = 0.40
    if broll_out and total_output_duration > 0:
        _total_coverage = sum(_b["durationInFrames"] / float(source_fps) for _b in broll_out)
        _coverage_fraction = _total_coverage / total_output_duration
        if _coverage_fraction > _BROLL_COVERAGE_CEILING:
            print(
                f"[broll] coverage {_total_coverage:.2f}s / {total_output_duration:.2f}s = "
                f"{_coverage_fraction*100:.1f}% — over {_BROLL_COVERAGE_CEILING*100:.0f}% ceiling; "
                f"trimming longest first",
                flush=True,
            )
            # Build index list sorted by descending duration so we drop
            # the most-flooding clips first (matches user's "longest first"
            # request). Stable sort by (-dur, original_idx) for deterministic
            # behavior when two clips have identical duration.
            _keep_idx = set(range(len(broll_out)))
            _sorted_by_dur = sorted(
                range(len(broll_out)),
                key=lambda i: (-broll_out[i]["durationInFrames"], i),
            )
            for _drop_i in _sorted_by_dur:
                if _coverage_fraction <= _BROLL_COVERAGE_CEILING:
                    break
                if _drop_i not in _keep_idx:
                    continue
                _dropped = broll_out[_drop_i]
                _dropped_dur = _dropped["durationInFrames"] / float(source_fps)
                _keep_idx.discard(_drop_i)
                _total_coverage -= _dropped_dur
                _coverage_fraction = _total_coverage / total_output_duration
                _record_divergence(
                    "broll",
                    {
                        "src": _dropped.get("src"),
                        "dropped_duration_s": round(_dropped_dur, 3),
                        "coverage_before_drop_pct": round(
                            (_total_coverage + _dropped_dur) / total_output_duration * 100, 1
                        ),
                    },
                    "trimmed_for_coverage_ceiling",
                    final=None,
                    reason=f"exceeds_coverage_ceiling_{int(_BROLL_COVERAGE_CEILING*100)}pct",
                )
            broll_out = [broll_out[i] for i in range(len(broll_out)) if i in _keep_idx]
            # Filter _broll_output_ranges lockstep so the strict-separation
            # block + thumbnail seed-shifter see the same surviving set.
            _existing_ranges = edit_plan.get("_broll_output_ranges") or []
            edit_plan["_broll_output_ranges"] = [
                _existing_ranges[i] for i in range(len(_existing_ranges)) if i in _keep_idx
            ]
            print(
                f"[broll] coverage after trim: {_total_coverage:.2f}s / "
                f"{total_output_duration:.2f}s = {_coverage_fraction*100:.1f}% "
                f"({len(broll_out)} clip(s) kept)",
                flush=True,
            )

    # ── Strict separation: B-roll vs overlays (MG + text_overlay) ──────────
    # Professional editing rule: B-roll cutaways and overlays NEVER share
    # screen time. The PostCutPlan prompt tells Gemini to plan accordingly;
    # this is the safety net for cases where Gemini emits an overlap.
    #
    # Priority: overlay wins, B-roll loses. Reasons:
    #   1. Overlays are scarce (1-3 per video) and carry deliberate
    #      editorial weight (chapter card = THE pivot, sticky notes =
    #      THE takeaways, quote = THE thesis).
    #   2. B-roll is fill (5+ per video) — losing one cutaway barely
    #      changes the edit; losing a chapter card breaks the structure.
    #   3. Overlays are word-anchored to specific moments with timing that
    #      can't move; B-roll has flexibility — there's usually a 2-3s
    #      window where the cutaway works equally well.
    #
    # We work in OUTPUT FRAMES (not word indices) so an overlay with
    # duration_seconds extending past its anchor word is correctly
    # included in the conflict check.
    _overlay_frame_ranges: list = []
    for _mg in motion_graphics_out:
        _f0 = int(_mg["fromFrame"])
        _f1 = _f0 + int(_mg["durationInFrames"])
        _overlay_frame_ranges.append((_f0, _f1, "motion_graphic", str(_mg.get("type", "?"))))
    for _ov in text_overlays_out:
        _f0 = int(_ov["fromFrame"])
        _f1 = _f0 + int(_ov["durationInFrames"])
        _overlay_frame_ranges.append((_f0, _f1, "text_overlay", str(_ov.get("variant", "?"))))

    if _overlay_frame_ranges and broll_out:
        _kept_indices: list = []
        for _i, _br in enumerate(broll_out):
            _bf0 = int(_br["fromFrame"])
            _bf1 = _bf0 + int(_br["durationInFrames"])
            _conflict = None
            for (_of0, _of1, _kind, _name) in _overlay_frame_ranges:
                # Frame-window overlap: max(start_a, start_b) < min(end_a, end_b)
                if max(_bf0, _of0) < min(_bf1, _of1):
                    _conflict = (_kind, _name, _of0, _of1)
                    break
            if _conflict:
                _ck, _cn, _co0, _co1 = _conflict
                print(
                    f"[broll] Dropping cutaway window=[{_bf0}-{_bf1}]f — "
                    f"overlaps {_ck} {_cn!r} window=[{_co0}-{_co1}]f. "
                    f"Overlay wins (more deliberate editorial moment).",
                    flush=True,
                )
            else:
                _kept_indices.append(_i)
        if len(_kept_indices) != len(broll_out):
            _dropped_count = len(broll_out) - len(_kept_indices)
            broll_out = [broll_out[_i] for _i in _kept_indices]
            # _broll_output_ranges was appended in lockstep with broll_out;
            # filter it the same way so downstream consumers (thumbnail
            # seed-shifter, persistence) see the same surviving set.
            _existing_ranges = edit_plan.get("_broll_output_ranges") or []
            if len(_existing_ranges) > 0:
                edit_plan["_broll_output_ranges"] = [
                    _existing_ranges[_i] for _i in _kept_indices
                    if _i < len(_existing_ranges)
                ]
            print(
                f"[broll] {_dropped_count} cutaway(s) dropped for overlay "
                f"conflicts; {len(broll_out)} kept",
                flush=True,
            )

    # ── Transition pro-grade safeguards (#3 + #5 from the 2026-06-14 audit) ──
    # Three checks applied to transitions_out AFTER overlay lists (broll_out,
    # motion_graphics_out, text_overlays_out) are finalized. Each drop logs a
    # divergence so the post-hoc grep tells the story. Order matters:
    #   1. OVERLAY COLLISION — drop transitions whose output-frame window
    #      overlaps an active B-roll, MG, or text_overlay. Overlay wins
    #      (mirrors the B-roll-vs-overlay precedence at handler.py:~11410+).
    #   2. MINIMUM SPACING — drop transitions whose cut frame is within
    #      _MIN_TRANSITION_SPACING_S of a previously-kept transition's cut
    #      frame. The cut still plays as a hard cut; this just prevents
    #      strobe.
    #   3. PER-VIDEO CAP — drop lowest-priority transitions until
    #      len(transitions_out) <= _TRANSITION_CAP_PER_30S × (runtime / 30s).
    #      Priority = natural duration: shorter transitions feel less
    #      editorially weighted, so they drop first.
    _MIN_TRANSITION_SPACING_S = 3.0
    _TRANSITION_CAP_PER_30S = 4.0

    if transitions_out:
        # ── Helper: transition's output frame range ──────────────────────
        # The transition plays during the trailing _slot_frames of clip
        # afterClipIndex. The cut frame = clip_ranges[i].end × fps. The
        # visual window spans [cut_frame - slot/2, cut_frame + slot/2]
        # (covers both sides of the cut perceptually — collapse phase
        # before, expand phase after).
        def _transition_frame_window(_t):
            _ci = int(_t.get("afterClipIndex", -1))
            _slot = int(_t.get("durationInFrames", 0))
            if not (0 <= _ci < len(_clip_ranges)) or _slot <= 0:
                return None
            _cut_frame = int(round(float(_clip_ranges[_ci]["end"]) * source_fps))
            _half = _slot // 2
            return (_cut_frame - _half, _cut_frame + _slot - _half)

        def _overlay_windows():
            """Return list of (from_frame, to_frame, kind, name) for every
            overlay that could collide with a transition. Overlay 'to'
            frame is exclusive."""
            _out = []
            for _b in broll_out:
                _f = int(_b.get("fromFrame") or 0)
                _d = int(_b.get("durationInFrames") or 0)
                if _d > 0:
                    _out.append((_f, _f + _d, "broll", _b.get("src", "")))
            for _mg in motion_graphics_out:
                _f = int(_mg.get("fromFrame") or 0)
                _d = int(_mg.get("durationInFrames") or 0)
                if _d > 0:
                    _out.append((_f, _f + _d, "mg", str(_mg.get("type", ""))))
            for _to in text_overlays_out:
                _f = int(_to.get("fromFrame") or 0)
                _d = int(_to.get("durationInFrames") or 0)
                if _d > 0:
                    _out.append((_f, _f + _d, "text_overlay", str(_to.get("variant", ""))))
            return _out

        _overlay_winds = _overlay_windows()

        # ── #3: Overlay collision ────────────────────────────────────────
        _kept_after_collision = []
        for _t in transitions_out:
            _twin = _transition_frame_window(_t)
            if _twin is None:
                _kept_after_collision.append(_t)
                continue
            _t_start, _t_end = _twin
            _collided_with = None
            for _o_start, _o_end, _o_kind, _o_name in _overlay_winds:
                # Half-open overlap test: [a,b) intersects [c,d) iff a<d and c<b.
                if _t_start < _o_end and _o_start < _t_end:
                    _collided_with = (_o_kind, _o_name, _o_start, _o_end)
                    break
            if _collided_with is None:
                _kept_after_collision.append(_t)
                continue
            _o_kind, _o_name, _o_start, _o_end = _collided_with
            print(
                f"[transition] DROP '{_t.get('type','?')}' after clip "
                f"{_t.get('afterClipIndex','?')} — overlaps {_o_kind} "
                f"'{_o_name}' window=[{_o_start}..{_o_end}). Overlay wins.",
                flush=True,
            )
            _record_divergence(
                "transition",
                {
                    "type": _t.get("type", ""),
                    "after_clip_index": _t.get("afterClipIndex", -1),
                    "transition_window_frames": [_t_start, _t_end],
                    "overlay_kind": _o_kind,
                    "overlay_name": _o_name,
                    "overlay_window_frames": [_o_start, _o_end],
                },
                "drop_overlay_collision",
                final=None,
                reason=f"overlaps_{_o_kind}",
            )

        # ── #5a: Minimum spacing ─────────────────────────────────────────
        _kept_after_spacing = []
        _last_kept_cut_frame = None
        _min_spacing_frames = int(round(_MIN_TRANSITION_SPACING_S * source_fps))
        for _t in _kept_after_collision:
            _twin = _transition_frame_window(_t)
            if _twin is None:
                _kept_after_spacing.append(_t)
                continue
            _t_start, _t_end = _twin
            _cut_frame_t = (_t_start + _t_end) // 2
            if (
                _last_kept_cut_frame is not None
                and _cut_frame_t - _last_kept_cut_frame < _min_spacing_frames
            ):
                _gap_s = (_cut_frame_t - _last_kept_cut_frame) / float(source_fps)
                print(
                    f"[transition] DROP '{_t.get('type','?')}' after clip "
                    f"{_t.get('afterClipIndex','?')} — only {_gap_s:.2f}s "
                    f"after previous kept transition (min {_MIN_TRANSITION_SPACING_S}s).",
                    flush=True,
                )
                _record_divergence(
                    "transition",
                    {
                        "type": _t.get("type", ""),
                        "after_clip_index": _t.get("afterClipIndex", -1),
                        "gap_to_previous_s": round(_gap_s, 3),
                        "min_spacing_s": _MIN_TRANSITION_SPACING_S,
                    },
                    "drop_too_close",
                    final=None,
                    reason=f"min_spacing_{_MIN_TRANSITION_SPACING_S}s",
                )
                continue
            _kept_after_spacing.append(_t)
            _last_kept_cut_frame = _cut_frame_t

        # ── #5b: Per-video cap ───────────────────────────────────────────
        # 4 transitions per 30s of output runtime, rounded up. Drop the
        # SHORTEST natural-duration transitions first (shorter = less
        # editorial weight). Stable sort: ties broken by afterClipIndex.
        _runtime_s = float(total_output_duration or 0.0)
        if _runtime_s > 0:
            _cap = max(1, int(math.ceil(_TRANSITION_CAP_PER_30S * _runtime_s / 30.0)))
        else:
            _cap = len(_kept_after_spacing)
        _kept_after_cap = list(_kept_after_spacing)
        if len(_kept_after_cap) > _cap:
            # Sort kept transitions by ascending natural duration (shortest
            # first = lowest priority = dropped first).
            _indexed = list(enumerate(_kept_after_cap))
            _indexed.sort(
                key=lambda _ix_t: (
                    TRANSITION_NATURAL_DURATION_MS.get(_ix_t[1].get("type", ""), 0),
                    _ix_t[0],
                )
            )
            _n_to_drop = len(_kept_after_cap) - _cap
            _drop_indices = {_ix for _ix, _ in _indexed[:_n_to_drop]}
            _new_kept = []
            for _ix, _t in enumerate(_kept_after_cap):
                if _ix in _drop_indices:
                    _nat_ms = TRANSITION_NATURAL_DURATION_MS.get(_t.get("type", ""), 0)
                    print(
                        f"[transition] DROP '{_t.get('type','?')}' after clip "
                        f"{_t.get('afterClipIndex','?')} — over cap "
                        f"({len(_kept_after_cap)} > {_cap} for {_runtime_s:.1f}s "
                        f"runtime). Shortest-natural-duration drops first.",
                        flush=True,
                    )
                    _record_divergence(
                        "transition",
                        {
                            "type": _t.get("type", ""),
                            "after_clip_index": _t.get("afterClipIndex", -1),
                            "natural_duration_ms": _nat_ms,
                            "total_before_cap": len(_kept_after_cap),
                            "cap": _cap,
                            "runtime_s": round(_runtime_s, 2),
                        },
                        "drop_over_cap",
                        final=None,
                        reason=f"exceeds_{_TRANSITION_CAP_PER_30S}_per_30s_cap",
                    )
                else:
                    _new_kept.append(_t)
            _kept_after_cap = _new_kept

        if len(_kept_after_cap) != len(transitions_out):
            print(
                f"[transition] safeguards: {len(transitions_out)} → "
                f"{len(_kept_after_cap)} (collision/spacing/cap drops applied)",
                flush=True,
            )
        transitions_out = _kept_after_cap

    # ── Authoritative caption-position override over MG / B-roll windows ─
    # The system prompt promises the pipeline owns caption position during
    # MG and B-roll windows (and explicitly tells Gemini NOT to emit
    # caption_position_changes for those windows). This is the code side
    # of that contract. Any change Gemini emitted that landed inside an
    # MG or B-roll window is overridden here in favor of the deterministic
    # zone-clearing rule in _force_caption_position_around_overlays.
    #
    # Wired-in point: AFTER motion_graphics_out + broll_out have been
    # finalized (B-roll collision drops at 10860+ already ran) but BEFORE
    # caption_position_segments_out is sent to the Remotion overlay input.
    # Every reposition is logged via _record_divergence — grep
    # [divergence] component=caption_position for the exact frames.
    _broll_ranges_for_caption_override = [
        (int(_b.get("fromFrame") or 0),
         int(_b.get("fromFrame") or 0) + int(_b.get("durationInFrames") or 0))
        for _b in broll_out
    ]
    caption_position_segments_out = _force_caption_position_around_overlays(
        caption_position_segments_out,
        motion_graphics_out,
        _broll_ranges_for_caption_override,
    )


    # PromptlyOverlay input — captions/MG/text on a transparent canvas. The
    # FFmpeg composite step lays this onto the source in a single encode.
    overlay_input = {
        "sourceUrl": _source_url,
        "fps": source_fps,
        "width": 1080,
        "height": 1920,
        "totalDurationInFrames": total_output_frames,
        "clips": clips_out,
        "transitions": transitions_out,
        "broll": broll_out,
        "caption": {
            "style": _caption_style,
            "pages": caption_pages,
            "keywords": _caption_keywords,
            "positionSegments": caption_position_segments_out,
            "extraProps": _caption_extra_props,
        },
        "textOverlays": text_overlays_out,
        "motionGraphics": motion_graphics_out,
        "tightCutOverlays": tight_cut_overlays_out,
        "outro": _outro,
    }
    overlay_input_path = os.path.join(_stage_dir, "overlay_input.json")
    _validate_and_write_render_input(
        "overlay", overlay_input, _SchemaOverlayInput, overlay_input_path,
    )

    # ── Pre-extract per-clip source for Remotion-rendered zoom clips ────────
    # The ABE.zip zoom components (SmoothPush, SnapReframe, FocusWindow,
    # StepZoom, LetterboxPush, StageZoom, DepthPull) accept only `src` +
    # `events` + their component-specific extras. They play `src` from frame
    # 0 with no built-in seek or playback-rate prop. To use them unmodified,
    # we materialize a frame-accurate per-clip mp4 whose frame 0 is the
    # clip's first kept frame, already speed-adjusted to the clip's pbr.
    # The component just plays this file from frame 0 as designed.
    #
    # Each extraction is an independent FFmpeg subprocess writing to its own
    # output path, so we run them concurrently via a ThreadPoolExecutor.
    # This phase has the box to itself (Remotion renders don't start until
    # micro_input is built, which depends on these src URLs), so CPU
    # oversubscription isn't a concern even with default ffmpeg threading.
    # Quality is bit-identical to the serial version — same commands, just
    # interleaved across CPUs.
    #
    # File goes into work_dir then is hardlinked into the bundle public root
    # via _stage_file (same path Remotion serves all other staged assets
    # from), and tracked in _staged_for_cleanup for end-of-render teardown.
    # list.append() is thread-safe under the GIL; _clip["src"] mutations are
    # per-clip (no shared state).
    def _extract_one_zoom_clip(_clip):
        _clip_id_for_name = str(_clip.get("id") or "clip").replace("/", "_")
        _zoom_src_path = os.path.join(work_dir, f"zoomclip_{_clip_id_for_name}.mp4")
        _start_frame_i = int(_clip["startFromFrames"])
        _dur_frames_i = int(_clip["durationInFrames"])
        _pbr_f = float(_clip["playbackRate"]) or 1.0
        # source_frames_needed mirrors the formula in
        # ffmpeg_base._build_clip_segment_with_pad: dur_frames output frames
        # span (dur_frames - 1) intervals of 1/fps, each requiring pbr
        # source intervals at source_fps; +1 for fencepost.
        _src_frames_needed = max(1, int(math.ceil((_dur_frames_i - 1) * _pbr_f)) + 1)
        _src_end_frame = _start_frame_i + _src_frames_needed
        if abs(_pbr_f - 1.0) < 1e-6:
            _vf = (
                f"trim=start_frame={_start_frame_i}:end_frame={_src_end_frame},"
                f"setpts=PTS-STARTPTS"
            )
        else:
            _vf = (
                f"trim=start_frame={_start_frame_i}:end_frame={_src_end_frame},"
                f"setpts=(PTS-STARTPTS)/{_pbr_f:.6f},fps={source_fps:g}"
            )
        # Encoder params mirror rife_normalize.py (the source Remotion
        # already decodes cleanly): keyframe every 1s, no scene-cut
        # keyframes, 90000 timescale, +faststart so the moov atom lives at
        # the start of the file. Without those, @remotion/media's WebCodecs
        # decoder times out extracting frame 1 from short clips that have
        # only one keyframe at the very end of the moov-at-tail file.
        _gop = max(1, int(round(source_fps)))
        _extract_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", source_path,
            "-vf", _vf,
            "-frames:v", str(_dur_frames_i),
            # Was ultrafast/18 — that's the worst-quality preset and needed
            # ~2x more bitrate for the same visual quality as `fast`. The
            # per-clip source is read by Remotion frame-by-frame for the
            # composite; quality here directly affects the final output.
            # `fast` + CRF 14 is a much better quality/speed tradeoff for
            # an intermediate that downstream depends on.
            "-c:v", "libx264", "-preset", "fast", "-crf", "14",
            "-pix_fmt", "yuv420p",
            "-g", str(_gop),
            "-keyint_min", str(_gop),
            "-sc_threshold", "0",
            "-video_track_timescale", "90000",
            "-movflags", "+faststart",
            "-an",
            _zoom_src_path,
        ]
        _t_extract = time.time()
        subprocess.run(_extract_cmd, check=True)
        _clip["src"] = _stage_file(_zoom_src_path)
        _elapsed_ms = (time.time() - _t_extract) * 1000
        return (
            f"[zoom-pre-extract] clip={_clip['id']} type={_clip['zoomEffect'].get('type')} "
            f"src_frames=[{_start_frame_i}..{_src_end_frame}) pbr={_pbr_f:.3f} "
            f"→ {_clip['src']} ({_elapsed_ms:.0f}ms)"
        )

    _zoom_clips_to_extract = [c for c in clips_out if c.get("zoomEffect")]
    if _zoom_clips_to_extract:
        _t_pre_extract_all = time.time()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(_zoom_clips_to_extract), 8)
        ) as _pre_extract_pool:
            for _log_line in _pre_extract_pool.map(
                _extract_one_zoom_clip, _zoom_clips_to_extract
            ):
                print(_log_line, flush=True)
        print(
            f"[zoom-pre-extract] {len(_zoom_clips_to_extract)} clip(s) total "
            f"in {(time.time() - _t_pre_extract_all) * 1000:.0f}ms (parallel)",
            flush=True,
        )

    # PromptlyMicroSegments input — only the windows Remotion must render.
    # Each segment carries its own clip/transition spec; Python tracks a
    # parallel list of metadata (with _clipIndex / _afterClipIndex tags) so
    # the FFmpeg final-mux filtergraph can find each segment by source.
    micro_input, micro_segments_meta = build_micro_segments_input(
        clips_out, transitions_out, _source_url, source_fps,
    )
    micro_input_path = None
    if micro_input is not None:
        micro_input_path = os.path.join(_stage_dir, "micro_input.json")
        _validate_and_write_render_input(
            "micro", micro_input, _SchemaMicroInput, micro_input_path,
        )

    _ffmpeg_clip_count = sum(1 for c in clips_out if categorize_clip(c) == "ffmpeg")
    _remotion_clip_count = len(clips_out) - _ffmpeg_clip_count
    print(
        f"[render] {len(clips_out)} clips ({_ffmpeg_clip_count} ffmpeg, "
        f"{_remotion_clip_count} remotion), {len(transitions_out)} transitions, "
        f"{len(broll_out)} broll, {len(caption_pages)} pages, "
        f"{len(text_overlays_out)} text overlays, {len(motion_graphics_out)} MG, "
        f"{total_output_frames} frames @ {source_fps:.2f}fps",
        flush=True,
    )
    if micro_input is not None:
        print(
            f"[render] PromptlyMicroSegments: {len(micro_input['segments'])} segments, "
            f"{micro_input['totalDurationInFrames']} frames",
            flush=True,
        )
    else:
        print("[render] PromptlyMicroSegments: empty (no transitions, no complex zooms)", flush=True)

    # ── 9. Audio pipeline (parallel with Remotion render) ───────────────────
    # Build the same audio filter chain that previously ran post-segment.
    # Output: one final-encoded AAC track written to a separate file.
    audio_denoise = bool(edit_plan.get("audio_denoise"))
    _src_loudness = edit_plan.get("_source_loudness") or {}
    _src_rms = _src_loudness.get("rms_db", -18.0)
    _src_peak = _src_loudness.get("peak_db", -6.0)
    _src_nf = _src_loudness.get("noise_floor_db", -45.0)
    if audio_denoise:
        _nr = 6 if _src_nf > -40 else (10 if _src_nf > -50 else 14)
        denoise_part = f"afftdn=nr={_nr}:nf={int(_src_nf)}:tn=1,"
    else:
        denoise_part = ""
    _fast_thresh = max(-28, min(-16, _src_rms - 4))
    _level_thresh = max(-22, min(-10, _src_rms + 2))
    _makeup = max(1, min(4, round(-_src_rms / 6)))
    print(
        f"[audio] Adaptive chain: rms={_src_rms:.0f}dB peak={_src_peak:.0f}dB "
        f"fast_thresh={_fast_thresh:.0f}dB level_thresh={_level_thresh:.0f}dB makeup={_makeup}dB",
        flush=True,
    )
    # loudnorm targets the platform-standard integrated loudness used by TikTok
    # / Instagram Reels / YouTube Shorts: I=-14 LUFS integrated, TP=-1.5 dBTP
    # true peak ceiling, LRA=11 LU loudness-range target. Single-pass (dynamic
    # normalization) — runs inline in one ffmpeg invocation, no measure-then-
    # apply two-pass. Placed at the END of the chain so it normalizes the
    # FINAL mix including SFX, ducking, EQ, and compression.
    audio_chain = (
        f"{denoise_part}highpass=f=75,"
        f"highshelf=f=6500:g=-3,"
        f"equalizer=f=200:t=q:w=1.5:g=-1.5,"
        f"acompressor=threshold={_fast_thresh}dB:ratio=3:attack=3:release=40:detection=peak"
        f":link=maximum:knee=3:mix=0.6,"
        f"equalizer=f=3000:t=q:w=1.2:g=1.5,"
        f"lowpass=f=14000,"
        f"acompressor=threshold={_level_thresh}dB:ratio=1.8:attack=15:release=80:makeup={_makeup},"
        f"loudnorm=I=-14:TP=-1.5:LRA=11"
    )

    # Per-cut audio — L-cut transition model. Each cut's audio uses its
    # RENDER range (source[start, end − trim_tail*speed]); transition slot
    # audio is clip A's last trans_dur of source, played continuously into
    # the visual transition. Audio splice lands at the end of the
    # transition (where the visual motion completes), not in the middle.
    # Audio + video durations match by construction — no padding, no buffer.
    _audio_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    _audio_stream_offset_for_render = float(
        edit_plan.get("_audio_stream_offset") or 0.0
    )
    _speed_audio_future = _audio_pool.submit(
        build_per_cut_audio, source_path, render_cuts,
        effective_durations, work_dir,
        sample_rate=sample_rate, trans_dur_after=_trans_dur_after,
        per_cut_render_dur_frames=_per_cut_render_dur_frames,
        source_fps=source_fps,
        trim_head_dur=_trim_head_dur, trim_tail_dur=_trim_tail_dur,
        audio_stream_offset=_audio_stream_offset_for_render,
    )

    # ── 10. Spawn Remotion renders in parallel (overlay chunks + micro) ────
    # The orchestrator (64 vCPU, 128 GB) runs N parallel Remotion overlay
    # subprocesses + 1 micro-segments subprocess on the same container.
    # Subprocess parallelism is OS-level (Python ThreadPoolExecutor →
    # subprocess.Popen → kernel scheduler distributes across vCPUs); there's
    # no Modal Function.map() involved, so the v61 inter-container scheduling
    # bottleneck (only 4-of-12 chunks running simultaneously) doesn't apply.
    #
    # Why chunked overlay specifically: a single Remotion process hits a
    # documented ~16-22 fps ceiling regardless of CPU count (issue #4664) —
    # main-thread + encoder serialization, not paint cost. 4 separate
    # processes each get their own ceiling, so aggregate fps scales nearly
    # linearly with chunk count up to ~6-8 chunks on this container.
    #
    # Chunk sizing: 4 chunks at concurrency=8 each → ~16 vCPUs per process,
    # fits cleanly in 64 vCPUs. Skip chunking for very short overlays
    # (<300 frames) where the per-process startup tax doesn't amortize.
    overlay_video_path = os.path.join(work_dir, "overlay.mov")
    # ProRes 4444 yuv444p10le — lossless intermediate. .mov container is
    # ProRes's canonical wrapper; FFmpeg decodes it transparently in the
    # composite step. The composite ffmpeg call doesn't care about the
    # container (it just reads via -i), so this is a drop-in change.
    micro_video_path = os.path.join(work_dir, "micro_segments.mov")
    # Chromium rasterizer: hardcoded swangle (Skia software path).
    # Vulkan was attempted across multiple iterations and never produced a
    # verified end-to-end frame on chrome-headless-shell; the production
    # contract is "no fallbacks, no crashes," and Vulkan's failure mode is
    # an unrecoverable Chromium crash mid-render. swangle has been the
    # rasterizer behind every successful render this codebase has ever
    # produced — deterministic output, no driver dependencies.
    _gl_mode = "swangle"

    def _run_remotion(label, cmd):
        _t0 = time.time()
        _r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        _elapsed = time.time() - _t0
        if _r.returncode != 0:
            # Print the full stdout + stderr so the failure mode is debuggable
            # (truncated tail-only logs hid the actual JS exception class and
            # symbolicated stack frames in prior runs).
            _stderr_full = _r.stderr or ""
            _stdout_full = _r.stdout or ""
            print(f"[{label}] ─── FULL STDOUT ───\n{_stdout_full}", flush=True)
            print(f"[{label}] ─── FULL STDERR ───\n{_stderr_full}", flush=True)
            raise RuntimeError(
                f"[{label}] Remotion render failed (rc={_r.returncode}) in "
                f"{_elapsed:.1f}s: {_stderr_full[-3000:]}"
            )
        # Surface render-fps lines for diagnostics.
        if _r.stdout:
            for _line in _r.stdout.split("\n"):
                _ls = _line.strip()
                if _ls.startswith("[render-full]") or _ls.startswith("[gpu-info]"):
                    print(f"[{label}] {_ls}", flush=True)
        return _elapsed

    def _split_frames(total_frames: int, n_chunks: int) -> list:
        """Partition [0, total_frames) into n_chunks contiguous inclusive
        ranges (start, end). Used to slice the overlay timeline across
        parallel Remotion processes."""
        if total_frames <= 0 or n_chunks <= 0:
            return []
        per = total_frames // n_chunks
        remainder = total_frames % n_chunks
        ranges = []
        cursor = 0
        for _i in range(n_chunks):
            chunk_size = per + (1 if _i < remainder else 0)
            if chunk_size == 0:
                continue
            ranges.append((cursor, cursor + chunk_size - 1))
            cursor += chunk_size
        return ranges

    # Decide chunk count based on total frames. Below 300 frames the
    # per-process startup tax (~3.5s) dominates — single process is faster.
    _OVERLAY_CHUNK_COUNT = 4 if total_output_frames >= 300 else 1
    _PER_CHUNK_CONCURRENCY = 8  # 4 chunks × 8 tabs = 32 tabs across 64 vCPUs
    _overlay_ranges = _split_frames(int(total_output_frames), _OVERLAY_CHUNK_COUNT)
    _overlay_chunked = len(_overlay_ranges) > 1
    _overlay_chunk_paths: list = []
    overlay_cmds: list = []
    if _overlay_chunked:
        for _i, (_fs, _fe) in enumerate(_overlay_ranges):
            _chunk_path = os.path.join(work_dir, f"overlay_chunk_{_i:02d}.mov")
            _overlay_chunk_paths.append(_chunk_path)
            overlay_cmds.append((
                f"overlay-{_i:02d}",
                [
                    "node", "/remotion/render-full.mjs",
                    "--input", overlay_input_path,
                    "--output", _chunk_path,
                    "--public-dir", _bundle_public_root,
                    "--composition", "PromptlyOverlay",
                    "--gl", _gl_mode,
                    "--frame-range", f"{_fs},{_fe}",
                    "--composition-start", str(_fs),
                    "--concurrency", str(_PER_CHUNK_CONCURRENCY),
                ],
            ))
    else:
        overlay_cmds.append((
            "overlay",
            [
                "node", "/remotion/render-full.mjs",
                "--input", overlay_input_path,
                "--output", overlay_video_path,
                "--public-dir", _bundle_public_root,
                "--composition", "PromptlyOverlay",
                "--gl", _gl_mode,
            ],
        ))

    # ── Micro-segments chunk planning ──────────────────────────────────────
    # PromptlyMicroSegments was the last serial bottleneck. Single-process
    # render at 2.4 fps was ~130s for ~314 frames in production — the slowest
    # leg of the parallel render phase. Splitting 4-way mirrors the overlay
    # chunking pattern (Remotion's documented Lambda architecture, just on a
    # single box). All transitions/zoom components are deterministic (no
    # Math.random / Date.now calls in src/remotion); ProRes 4444 is intra-
    # only so chunk concat is bit-exact via `-f concat -c copy`.
    #
    # Concurrency tuned conservatively: 4 micro chunks × 4 tabs each = 16
    # micro tabs. Combined with the 4×8 overlay chunks (32 tabs), total is
    # 48 tabs sharing 64 vCPUs = 1.33 vCPU/tab — a small step up from the
    # current 40 tabs / 1.6 vCPU per tab. Avoids the full 32+32=64-tabs
    # oversubscription edge case the prior single-process comment warned
    # against. If the next render shows clean wins without overlay
    # regression, this can be bumped to concurrency=8 in a follow-up.
    #
    # Below ~200 frames of micro content (small renders with few
    # transitions / no complex zoom), the single-process path is faster
    # because per-chunk Remotion startup tax (~5-10s × N chunks) dominates.
    micro_cmds: list = []
    micro_chunk_paths: list = []
    _micro_chunked = False
    if micro_input is not None:
        _MICRO_CHUNK_THRESHOLD = 200
        _micro_total_frames = int(micro_input.get("totalDurationInFrames") or 0)
        _MICRO_CHUNK_COUNT = 4 if _micro_total_frames >= _MICRO_CHUNK_THRESHOLD else 1
        _micro_ranges = _split_frames(_micro_total_frames, _MICRO_CHUNK_COUNT)
        _micro_chunked = len(_micro_ranges) > 1
        _MICRO_CONCURRENCY = 4 if _micro_chunked else _PER_CHUNK_CONCURRENCY
        if _micro_chunked:
            for _i, (_fs, _fe) in enumerate(_micro_ranges):
                _chunk_path = os.path.join(work_dir, f"micro_chunk_{_i:02d}.mov")
                micro_chunk_paths.append(_chunk_path)
                micro_cmds.append((
                    f"micro-{_i:02d}",
                    [
                        "node", "/remotion/render-full.mjs",
                        "--input", micro_input_path,
                        "--output", _chunk_path,
                        "--public-dir", _bundle_public_root,
                        "--composition", "PromptlyMicroSegments",
                        "--gl", _gl_mode,
                        "--frame-range", f"{_fs},{_fe}",
                        "--composition-start", str(_fs),
                        "--concurrency", str(_MICRO_CONCURRENCY),
                    ],
                ))
        else:
            # Single-process path for short micros where chunking would
            # cost more in startup tax than it saves in parallelism.
            micro_cmds.append((
                "micro",
                [
                    "node", "/remotion/render-full.mjs",
                    "--input", micro_input_path,
                    "--output", micro_video_path,
                    "--public-dir", _bundle_public_root,
                    "--composition", "PromptlyMicroSegments",
                    "--gl", _gl_mode,
                    "--concurrency", str(_MICRO_CONCURRENCY),
                ],
            ))

    _render_t0 = time.time()
    _micro_descr = ""
    if micro_cmds:
        if _micro_chunked:
            _micro_descr = f" + {len(micro_cmds)}-way micro chunks (concurrency={_MICRO_CONCURRENCY} each)"
        else:
            _micro_descr = f" + 1 micro subprocess"
    if _overlay_chunked:
        print(
            f"[render] Spawning {len(overlay_cmds)} overlay chunk subprocesses "
            f"({total_output_frames} frames split {len(_overlay_ranges)}-ways, "
            f"concurrency={_PER_CHUNK_CONCURRENCY} each)"
            f"{_micro_descr} (gl={_gl_mode})",
            flush=True,
        )
    else:
        print(
            f"[render] Spawning Remotion renders: PromptlyOverlay (single, "
            f"{total_output_frames}f)"
            f"{_micro_descr} (gl={_gl_mode})",
            flush=True,
        )

    # ── Composite chunk planning (computed up-front so we can pipeline) ───
    # _N_COMPOSITE_CHUNKS / _composite_ranges / _build_composite_cmd are
    # declared here, BEFORE _render_pool, so the pipelined path can spawn
    # composite chunk subprocesses as soon as their corresponding overlay
    # chunks finish — no barrier-wait-then-concat between phases.
    #
    # Below 400 frames the per-process startup tax dominates → composite
    # falls back to single-pass. Below 300 frames overlay is also single,
    # so pipelining is meaningless either way.
    _N_COMPOSITE_CHUNKS = 4 if total_output_frames >= 400 else 1
    _composite_ranges = split_timeline_into_chunks(int(total_output_frames), _N_COMPOSITE_CHUNKS)
    _composite_chunked = len(_composite_ranges) > 1
    # Chunks are LOSSLESS ProRes 4444 intermediates (.mov) — see encoder
    # branch in _build_composite_cmd below. The lone H.264 lossy encode in
    # the pipeline happens at the final concat+mux step, decoding all
    # chunks back through libx264 in one pass over the full timeline. This
    # eliminates the B-frame-lookahead boundary frame loss the per-chunk
    # libx264 encode used to suffer from (1-2 frames dropped at the tail
    # of each chunk because libx264 couldn't see future frames to encode
    # them as B-frames → ~3-4 frames missing across 4 chunks → ~100ms A/V
    # drift in the final output, observed in production).
    _composite_chunk_paths = (
        [os.path.join(work_dir, f"composite_chunk_{_i:02d}.mov")
         for _i in range(len(_composite_ranges))]
        if _composite_chunked else []
    )
    # Pipelining condition: BOTH phases 4-way chunked. If composite is
    # single-pass it has no chunk to pair with overlay chunk K, so we fall
    # back to the legacy wave-based pattern (overlay all → concat → composite).
    _pipeline_chunks = _composite_chunked and _overlay_chunked

    def _build_composite_cmd(
        chunk_idx: int,
        chunk_start: int,
        chunk_end: int,
        output_path_for_chunk: str,
        include_audio: bool,
        overlay_path: Optional[str] = None,
    ) -> list:
        """Construct a single ffmpeg command for one composite chunk.
        When include_audio=True, the audio track is muxed in the same pass
        (used by the single-chunk fallback path).
        When overlay_path is set, that file is used as the overlay input
        directly — it must already contain exactly chunk_size frames at
        internal time 0 (chunk-local). The filtergraph is told via
        overlay_is_chunk_local=True so it skips the global trim. Used by
        the pipelined chunk path (composite chunk K reads overlay chunk K
        instead of the concat'd full overlay)."""
        if _composite_chunked:
            _c_clips, _c_trans, _c_micro = slice_timeline_for_chunk(
                chunk_start, chunk_end, clips_out, transitions_out,
                micro_segments_meta, source_fps,
            )
        else:
            _c_clips = clips_out
            _c_trans = transitions_out
            _c_micro = micro_segments_meta

        # Build inputs for THIS chunk. Source + overlay are always present;
        # micro is only present if any sliced segment is remotion-rendered
        # OR there's a transition in this chunk (transitions always live in
        # micro_segments). B-roll lives entirely in PromptlyOverlay (alpha
        # layer composited via overlay_input_idx) — no per-chunk B-roll
        # inputs needed in this filtergraph.
        chunk_inputs = [source_path]
        c_source_idx = 0
        c_micro_idx = None
        c_micro_needed = (
            micro_input is not None and len(_c_micro) > 0
        )
        if c_micro_needed:
            chunk_inputs.append(micro_video_path)
            c_micro_idx = len(chunk_inputs) - 1
        # Overlay input: chunk-local file (pipelined path) or the global
        # overlay (legacy / single-pass path). The filtergraph's
        # overlay_is_chunk_local flag toggles whether to trim by
        # chunk_global_start_frame.
        _ov_input = overlay_path if overlay_path is not None else overlay_video_path
        chunk_inputs.append(_ov_input)
        c_overlay_idx = len(chunk_inputs) - 1
        c_audio_idx = None
        if include_audio:
            c_audio_idx = len(chunk_inputs)
            chunk_inputs.append(_final_audio_path)

        chunk_size = chunk_end - chunk_start
        _fg, _final_labels = build_final_filtergraph(
            clips=_c_clips,
            transitions=_c_trans,
            micro_segments=_c_micro,
            outro=_outro,
            total_output_frames=chunk_size,
            source_fps=source_fps,
            source_input_idx=c_source_idx,
            micro_input_idx=c_micro_idx,
            overlay_input_idx=c_overlay_idx,
            chunk_global_start_frame=(chunk_start if _composite_chunked else None),
            global_total_frames=int(total_output_frames),
            overlay_is_chunk_local=(overlay_path is not None),
        )

        cmd = ["ffmpeg", "-y", "-v", "warning", "-threads", "0"]
        for _inp in chunk_inputs:
            cmd += ["-i", _inp]
        cmd += [
            "-filter_complex", _fg,
            "-map", f"[{_final_labels[0]}]",
        ]
        if include_audio and c_audio_idx is not None:
            # PCM s16le for the master MP4 audio — sample-exact, 0ms drift.
            # See the longer rationale at the final concat+mux step. Do NOT
            # swap to AAC: any frame-based codec reintroduces the structural
            # ~21ms drift floor that produced audible word clipping pre-v37.
            cmd += ["-map", f"{c_audio_idx}:a:0", "-c:a", "pcm_s16le"]

        # Two encoder paths:
        #
        # 1. Single-pass (include_audio=True, output is final): libx264
        #    medium crf 18 with platform-tuned settings. The full
        #    1401-frame timeline is encoded in one pass — B-frame
        #    lookahead works correctly across the whole video, no
        #    boundary frame loss. This is the path for short outputs
        #    (<400 frames) that don't need chunking.
        #
        # 2. Chunked (include_audio=False): each chunk renders to a
        #    LOSSLESS ProRes 4444 intermediate. Intra-only codec means
        #    every frame is a keyframe — no B-frame lookahead, no
        #    boundary frame loss. The single H.264 lossy encode happens
        #    later, in the final concat+mux step, where the concatenated
        #    ProRes is decoded and re-encoded in ONE libx264 invocation
        #    over the full timeline. This is the pro-tool pattern
        #    (Premiere/Resolve render preview to ProRes, encode H.264
        #    once on export) and structurally eliminates the chunk-
        #    boundary A/V drift bug the previous chunked-libx264
        #    architecture had.
        if include_audio:
            cmd += [
                # Final composite encode: CRF 16 + slow preset (was CRF 18
                # + medium). This is the ONE lossy encode that ships to the
                # user — quality here matters most. CRF 16 with slow preset
                # produces noticeably more detail in motion + faces than
                # CRF 18 medium, at the cost of ~2-3× encode time.
                # maxrate bumped 18M → 24M to match the higher CRF target
                # without bitrate clamping the cleanest frames.
                "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                "-fps_mode", "cfr", "-r", str(int(round(source_fps))),
                "-maxrate", "24M", "-bufsize", "48M",
                "-profile:v", "high", "-level:v", "4.1",
                "-pix_fmt", "yuv420p",
                "-g", str(int(round(source_fps))),
                "-keyint_min", str(int(round(source_fps))),
                "-sc_threshold", "0",
                "-color_primaries", "bt709",
                "-color_trc", "bt709",
                "-colorspace", "bt709",
                "-color_range", "tv",
                "-shortest",
                # +negative_cts_offsets — signal B-frame reordering via
                # negative composition time offsets, NOT via an edit list.
                # libx264 with B-frames otherwise produces an `edts/elst`
                # atom claiming to skip 2 frames (33ms at 60fps) of priming
                # that doesn't actually exist in the bitstream (first packet
                # has PTS=0, not -33ms). AVPlayer respects the edit list,
                # finds the seg_dur overshoots the media by 33ms, and
                # stretches each frame's display duration to fill — visible
                # as cumulative video lag from 0 at the start to ~33ms by
                # the end. Audio already uses negative_cts (first AAC packet
                # at PTS=-21.3ms) and stays in sync; this flag makes the
                # video muxing match.
                "-movflags", "+faststart+negative_cts_offsets",
                output_path_for_chunk,
            ]
        else:
            cmd += [
                "-c:v", "prores_ks", "-profile:v", "4444",
                "-pix_fmt", "yuv444p10le",
                "-vendor", "apl0",
                "-fps_mode", "cfr", "-r", str(int(round(source_fps))),
                output_path_for_chunk,
            ]
        return cmd

    # +1 worker reserved for _finalize_micros (waits on micros + runs the
    # tiny concat). Without it, finalize could occupy a render slot the
    # moment one render finishes and block on the slowest micro chunk,
    # starving the remaining renders by one worker.
    _render_pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, len(overlay_cmds) + len(micro_cmds) + 1),
    )
    overlay_futures = [
        _render_pool.submit(_run_remotion, _lbl, _cmd)
        for _lbl, _cmd in overlay_cmds
    ]
    # micro_futures: list of (label, future) tuples. For chunked path,
    # one future per chunk; chunks render in parallel and write to
    # micro_chunk_XX.mov. For single-process path, one future writes to
    # micro_video_path directly (matching the pre-chunking shape).
    micro_futures = [
        (_lbl, _render_pool.submit(_run_remotion, _lbl, _cmd))
        for _lbl, _cmd in micro_cmds
    ]

    # _micro_finalize_future: single shared barrier that waits for all
    # micro renders to finish and, in the chunked path, concats them into
    # micro_video_path via `-f concat -c copy` (intra-only ProRes 4444 →
    # bit-exact stream copy, <1s). Submitted immediately so the wait + the
    # concat run concurrently with the overlay renders. Both the pipelined
    # composite chains and the synchronous collection path await this
    # future — Future.result() caches, so calling from multiple threads is
    # safe (concat runs exactly once). For the non-chunked path this is
    # just a join; micro_video_path is already the direct output.
    def _finalize_micros() -> tuple:
        _t0 = time.time()
        _per_chunk: list = []
        for _mlbl, _mfut in micro_futures:
            _per_chunk.append((_mlbl, _mfut.result(timeout=320)))
        if _micro_chunked:
            for _p in micro_chunk_paths:
                if not os.path.exists(_p) or os.path.getsize(_p) < 1000:
                    raise RuntimeError(f"Micro chunk missing/invalid: {_p}")
            _concat_list = os.path.join(work_dir, "_micro_concat_list.txt")
            with open(_concat_list, "w") as _lf:
                for _p in micro_chunk_paths:
                    _lf.write(f"file '{_p}'\n")
            _r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error",
                 "-f", "concat", "-safe", "0",
                 "-i", _concat_list,
                 "-c", "copy",
                 micro_video_path],
                capture_output=True, text=True, timeout=120,
            )
            if _r.returncode != 0:
                raise RuntimeError(
                    f"Micro chunk concat failed (rc={_r.returncode}): "
                    f"{(_r.stderr or '')[-1000:]}"
                )
        return time.time() - _t0, _per_chunk

    _micro_finalize_future = (
        _render_pool.submit(_finalize_micros) if micro_cmds else None
    )

    # ── Pipelined composite chunk dispatch ────────────────────────────────
    # When both phases are 4-way chunked (total >= 400 frames), each
    # composite chunk K runs as soon as its overlay chunk K finishes —
    # no barrier-wait for all overlay chunks + concat. Chains run in
    # parallel on a dedicated pool. Composite chunk K reads
    # overlay_chunk_K.mov (chunk-local) directly, so the legacy overlay
    # concat is skipped entirely for this path. Quality is identical:
    # filtergraph trims source/transitions/micro the same way; the
    # overlay branch just takes the no-trim path (overlay file is
    # already chunk-local).
    _composite_pool = None
    _composite_chain_futures: list = []
    if _pipeline_chunks:
        _composite_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=len(_composite_ranges)
        )

        def _composite_chain(K):
            _t_chain = time.time()
            # Block on this chunk's overlay before starting composite.
            overlay_futures[K].result(timeout=320)
            _ov_path = _overlay_chunk_paths[K]
            if not os.path.exists(_ov_path) or os.path.getsize(_ov_path) < 1000:
                raise RuntimeError(
                    f"Overlay chunk {K} missing/invalid: {_ov_path}"
                )
            # micro is rendered as N parallel Remotion processes (4-way
            # chunked when totalDurationInFrames >= 200; otherwise single
            # process) and concat'd into micro_video_path by a shared
            # finalize future. Wait on it here; later chains find the
            # future already resolved (Future caches → concat runs exactly
            # once across all chains).
            if _micro_finalize_future is not None:
                _micro_finalize_future.result(timeout=400)
            _cs, _ce = _composite_ranges[K]
            _cmd = _build_composite_cmd(
                K, _cs, _ce, _composite_chunk_paths[K],
                include_audio=False,
                overlay_path=_ov_path,
            )
            _t_ff = time.time()
            _r = subprocess.run(
                _cmd, capture_output=True, text=True, timeout=600,
            )
            _e_ff = time.time() - _t_ff
            if _r.returncode != 0:
                raise RuntimeError(
                    f"[composite-{K:02d}] ffmpeg failed (rc={_r.returncode}) "
                    f"in {_e_ff:.1f}s: {(_r.stderr or '')[-1500:]}"
                )
            return time.time() - _t_chain

        _composite_chain_futures = [
            _composite_pool.submit(_composite_chain, K)
            for K in range(len(_composite_ranges))
        ]
        print(
            f"[render] Pipelined composite chains dispatched "
            f"({len(_composite_ranges)} chains, each waits on its overlay "
            f"chunk then runs ffmpeg with chunk-local overlay)",
            flush=True,
        )

    # ── Audio pipeline (running on a separate thread) —
    # Collect its output now so the final-audio build can start while the
    # Remotion renders are still in flight.
    _speed_audio_path = _speed_audio_future.result(timeout=60)
    _audio_pool.shutdown(wait=False)
    if not _speed_audio_path or not os.path.exists(_speed_audio_path):
        raise RuntimeError(f"Per-cut audio pipeline produced no output at {_speed_audio_path}")

    # ── 11. Build final audio (SFX mix + EQ chain) → .wav (PCM) ─────────
    # SFX play OVER the dialogue at full volume — no ducking, no dipping.
    # The dialogue stays at its full level throughout; SFX add on top via
    # amix with normalize=0 (linear sum, not auto-gain-reduced).
    #
    # OUTPUT FORMAT: PCM s16le WAV, NOT AAC. The previous design encoded
    # AAC here and let the final mux do `-c:a copy`, which left the audio
    # 33ms longer than video at output (AAC pads the final frame to a
    # 1024-sample boundary; `-c:a copy` cannot truncate AAC mid-frame so
    # the muxer's `-shortest` flag had no effect on duration). PCM is
    # sample-exact — no encoder padding, no frame-boundary rounding. The
    # final composite step (which already re-encodes video) does the AAC
    # encode in one pass with proper duration enforcement, so the audio
    # leaves the pipeline at exactly the same length as the video.
    _audio_filter_parts = []
    _audio_out = "[audio_base]"
    _audio_out_initial = "[audio_base]"
    if sfx_audio_labels and sfx_timestamps:
        _n_sfx = len(sfx_audio_labels) + 1
        _sfx_labels_str = _audio_out + "".join(sfx_audio_labels)
        _audio_filter_parts.append(
            f"{_sfx_labels_str}amix=inputs={_n_sfx}:duration=first:dropout_transition=0:normalize=0[audio_sfx_mixed]"
        )
        _audio_out = "[audio_sfx_mixed]"
        print(f"[sfx] Mixed {len(sfx_audio_labels)} SFX track(s) into audio (no ducking)", flush=True)
    _audio_filter_parts.append(f"{_audio_out}{audio_chain}[final_audio]")
    _audio_filter_parts.insert(0, f"[0:a]asetpts=PTS-STARTPTS{_audio_out_initial}")
    _audio_fc = ";".join(sfx_filter_strs + _audio_filter_parts)

    _final_audio_path = os.path.join(work_dir, "final_audio.wav")
    _audio_t0 = time.time()
    _audio_cmd = (
        ["ffmpeg", "-y", "-v", "warning", "-threads", "0",
         "-i", _speed_audio_path]
        + sfx_input_args
        + ["-filter_complex", _audio_fc,
           "-map", "[final_audio]",
           "-c:a", "pcm_s16le",
           _final_audio_path]
    )
    _audio_r = subprocess.run(_audio_cmd, capture_output=True, text=True, timeout=180)
    if _audio_r.returncode != 0:
        raise RuntimeError(f"Audio post-processing failed: {(_audio_r.stderr or '')[-600:]}")
    _audio_elapsed = time.time() - _audio_t0
    print(f"[render] Final audio built in {_audio_elapsed:.1f}s → {_final_audio_path}", flush=True)

    # ── 12. Wait for Remotion renders, then ffmpeg composite ────────────
    # All the heavy v62 work happens in this one ffmpeg invocation:
    #   1. Build each ffmpeg-renderable clip from source via trim+setpts+(zoom?)
    #   2. Trim each Remotion-rendered clip/transition out of micro_segments.mov
    #      by frame range
    #   3. Concat all timeline segments in order → [base]
    #   4. Apply outro fade (if configured)
    #   5. Alpha-composite the PromptlyOverlay layer (captions + MGs + text
    #      overlays + B-roll cutaways — every visible non-source pixel).
    #   6. libx264 final encode + AAC encode (from PCM WAV) in a single pass.
    # Wait for all overlay chunk subprocesses (in input order — for chunked
    # mode each chunk lands in its own .mov; we concat them in order below).
    _overlay_chunk_elapsed = []
    for _i, _f in enumerate(overlay_futures):
        _e = _f.result(timeout=320)
        _overlay_chunk_elapsed.append(_e)
        _label = overlay_cmds[_i][0]
        _path = _overlay_chunk_paths[_i] if _overlay_chunked else overlay_video_path
        print(
            f"[render] {_label} done in {_e:.1f}s → "
            f"{os.path.getsize(_path)/1024/1024:.1f}MB",
            flush=True,
        )
    if _micro_finalize_future is not None:
        _micro_total_elapsed, _micro_per_chunk = _micro_finalize_future.result(timeout=400)
        if _micro_chunked:
            _micro_max = max(e for _, e in _micro_per_chunk)
            print(
                f"[render] PromptlyMicroSegments: {len(_micro_per_chunk)}-way "
                f"chunked, max chunk={_micro_max:.1f}s, finalize+concat="
                f"{_micro_total_elapsed:.1f}s → "
                f"{os.path.getsize(micro_video_path)/1024/1024:.1f}MB",
                flush=True,
            )
        else:
            _, _e = _micro_per_chunk[0]
            print(
                f"[render] PromptlyMicroSegments done in {_e:.1f}s → "
                f"{os.path.getsize(micro_video_path)/1024/1024:.1f}MB",
                flush=True,
            )
    _render_pool.shutdown(wait=False)
    _render_elapsed = time.time() - _render_t0

    # ── Concat overlay chunks (-c copy, lossless) ─────────────────────────
    # ProRes 4444 chunks share identical codec parameters (resolution, fps,
    # profile, pixel format, color space) since they all came from the same
    # composition spec — concat demuxer can stream-copy them with zero
    # quality loss in <1s.
    #
    # Pipelined path (`_pipeline_chunks=True`) skips this concat entirely:
    # composite chunks read overlay_chunk_KK.mov directly, so the global
    # overlay file is never assembled. Saves one ffmpeg pass + ~50-100MB
    # intermediate write, and lets composite chunks start as soon as their
    # overlay chunk finishes (not after the slowest one + concat).
    if _overlay_chunked and not _pipeline_chunks:
        for _p in _overlay_chunk_paths:
            if not os.path.exists(_p) or os.path.getsize(_p) < 1000:
                raise RuntimeError(f"Overlay chunk missing/invalid: {_p}")
        _concat_t0 = time.time()
        _concat_list = os.path.join(work_dir, "_overlay_concat_list.txt")
        with open(_concat_list, "w") as _lf:
            for _p in _overlay_chunk_paths:
                _lf.write(f"file '{_p}'\n")
        _concat_r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-f", "concat", "-safe", "0",
             "-i", _concat_list,
             "-c", "copy",
             overlay_video_path],
            capture_output=True, text=True, timeout=120,
        )
        if _concat_r.returncode != 0:
            raise RuntimeError(
                f"Overlay chunk concat failed (rc={_concat_r.returncode}): "
                f"{(_concat_r.stderr or '')[-1000:]}"
            )
        _concat_elapsed = time.time() - _concat_t0
        _max_chunk = max(_overlay_chunk_elapsed)
        print(
            f"[render] Overlay chunks: max={_max_chunk:.1f}s, "
            f"concat={_concat_elapsed:.1f}s → "
            f"{os.path.getsize(overlay_video_path)/1024/1024:.1f}MB",
            flush=True,
        )
    elif _pipeline_chunks:
        _max_chunk = max(_overlay_chunk_elapsed)
        print(
            f"[render] Overlay chunks: max={_max_chunk:.1f}s, "
            f"concat=skipped (composite chunks read overlay chunks directly)",
            flush=True,
        )

    print(f"[render] All Remotion renders done in {_render_elapsed:.1f}s", flush=True)

    # Validate v62 Remotion outputs. In the pipelined path overlay_video_path
    # is never produced (composite reads chunks directly) — validate the
    # individual chunks here as a defensive sanity check; the chain
    # function already raised if any chunk failed.
    if _pipeline_chunks:
        for _p in _overlay_chunk_paths:
            if not os.path.exists(_p) or os.path.getsize(_p) < 1000:
                raise RuntimeError(f"Overlay chunk missing/invalid: {_p}")
    else:
        if not os.path.exists(overlay_video_path) or os.path.getsize(overlay_video_path) < 1000:
            raise RuntimeError(f"PromptlyOverlay output missing/invalid: {overlay_video_path}")
    if micro_input is not None and (
        not os.path.exists(micro_video_path) or os.path.getsize(micro_video_path) < 1000
    ):
        raise RuntimeError(f"PromptlyMicroSegments output missing/invalid: {micro_video_path}")

    _mux_t0 = time.time()

    if _composite_chunked:
        # Composite chunked ⇔ total >= 400 frames ⇔ overlay also chunked
        # (overlay threshold is 300) ⇔ _pipeline_chunks=True. Each composite
        # chunk chain was dispatched immediately after _render_pool spawned
        # its overlay future, with the chain waiting on its overlay chunk +
        # micro before running composite ffmpeg with chunk-local overlay.
        print(
            f"[render] Collecting {len(_composite_chain_futures)} pipelined "
            f"composite chunks ({total_output_frames} frames split "
            f"{len(_composite_ranges)}-ways)",
            flush=True,
        )
        _composite_chunk_elapsed = []
        for _ci, _f in enumerate(_composite_chain_futures):
            # 600s ≥ overlay max + composite max + safety margin.
            _e = _f.result(timeout=600)
            _composite_chunk_elapsed.append(_e)
            _path = _composite_chunk_paths[_ci]
            print(
                f"[render] composite-{_ci:02d} chain done in {_e:.1f}s → "
                f"{os.path.getsize(_path)/1024/1024:.1f}MB",
                flush=True,
            )
        if _composite_pool is not None:
            _composite_pool.shutdown(wait=False)

        _max_chunk = max(_composite_chunk_elapsed)
        print(
            f"[render] Composite: max chunk={_max_chunk:.1f}s, concat=deferred (folded into final mux)",
            flush=True,
        )
    else:
        # Single-pass for short outputs (<400 frames). One libx264 invocation
        # writes video + audio directly to output_path — PCM WAV input is
        # AAC-encoded inline alongside the video encode (so -shortest can
        # actually trim audio to video duration; see commit 5387f96).
        _single_cmd = _build_composite_cmd(
            0, 0, int(total_output_frames), output_path,
            include_audio=True,
        )
        _r = subprocess.run(_single_cmd, capture_output=True, text=True, timeout=300)
        if _r.returncode != 0:
            raise RuntimeError(f"Final composite failed: {(_r.stderr or '')[-1500:]}")

    # Single composite render is always the final lossy encode. Two paths:
    #   _output_already_written=True → composite single wrote video+audio
    #     directly to output_path; final concat+mux is a no-op.
    #   _final_video_inputs == [chunk0, chunk1, ...] → composite chunked;
    #     concat demuxer + audio mux in one ffmpeg pass below.
    _output_already_written = not _composite_chunked
    if _output_already_written:
        _final_video_inputs = None
    else:
        _final_video_inputs = list(_composite_chunk_paths)

    # ── Final concat + audio mux ──────────────────────────────────────────
    # Two paths driven by _output_already_written / _final_video_inputs:
    #   - Single composite (<400 frames): video + audio already muxed by
    #     _build_composite_cmd in one libx264 pass; nothing to do here.
    #   - Chunked composite (≥400 frames): chunks were rendered as LOSSLESS
    #     ProRes 4444 intermediates. Decode them through concat demuxer,
    #     re-encode the ENTIRE concatenated timeline in ONE libx264 pass,
    #     and mux audio in the same invocation. This is the lone H.264
    #     lossy encode in the chunked pipeline — B-frame lookahead works
    #     correctly across the full timeline (no chunk boundaries inside
    #     this encode), structurally eliminating the ~100ms A/V drift
    #     that the previous stream-copy concat suffered from (per-chunk
    #     libx264 dropped 1-2 frames at each chunk's tail).
    _am_t0 = time.time()
    if _output_already_written:
        _am_elapsed = 0.0
    else:
        _final_concat_list = os.path.join(work_dir, "_final_concat_list.txt")
        with open(_final_concat_list, "w") as _lf:
            for _p in _final_video_inputs:
                _lf.write(f"file '{_p}'\n")
        _am_r = subprocess.run(
            ["ffmpeg", "-y", "-v", "warning", "-threads", "0",
             "-f", "concat", "-safe", "0",
             "-i", _final_concat_list,
             "-i", _final_audio_path,
             "-map", "0:v",
             "-map", "1:a",
             # Single libx264 encode over the FULL concatenated timeline.
             # Same settings the single-pass path uses — keeps output
             # quality identical regardless of which path produced it.
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-fps_mode", "cfr", "-r", str(int(round(source_fps))),
             "-maxrate", "18M", "-bufsize", "36M",
             "-profile:v", "high", "-level:v", "4.1",
             "-pix_fmt", "yuv420p",
             "-g", str(int(round(source_fps))),
             "-keyint_min", str(int(round(source_fps))),
             "-sc_threshold", "0",
             # Tag Rec.709 color space + tv-range explicitly. Without these
             # the output's color_primaries/transfer/matrix read as
             # "unknown" and AVPlayer falls back to assuming sRGB —
             # visible as washed-out / dim playback.
             "-color_primaries", "bt709",
             "-color_trc", "bt709",
             "-colorspace", "bt709",
             "-color_range", "tv",
             # Audio: AAC-LC at 192 kbps. The previous code shipped
             # pcm_s16le-in-MP4 to dodge AAC's ~21ms frame-size drift
             # floor, but iOS AVPlayer streaming PCM-in-MP4 drops audio
             # silently in production — none of the major iOS video
             # players (Photos, Messages, TikTok, Reels) ship that
             # combination. AAC-in-MP4 is what AVPlayer expects.
             # The 21ms drift floor is acceptable: the v−a sync probe
             # below already tolerates ±20ms, and even Apple's own
             # Photos exports run with single-frame drift.
             "-c:a", "aac",
             "-b:a", "192k",
             "-ar", "48000",
             "-shortest",
             # +negative_cts_offsets — see the comment on the matching flag
             # in _build_composite_cmd. Without it, libx264's B-frame priming
             # gets signaled via a buggy edit list that overshoots the video
             # media by 33ms, causing iOS AVPlayer to stretch frame durations
             # and produce ~33ms of cumulative video drift by the end of the
             # clip. Audio already uses negative_cts (correctly); this aligns
             # the video muxing to the same correct approach.
             "-movflags", "+faststart+negative_cts_offsets",
             output_path],
            capture_output=True, text=True, timeout=300,
        )
        if _am_r.returncode != 0:
            raise RuntimeError(
                f"Final concat+mux failed (rc={_am_r.returncode}): "
                f"{(_am_r.stderr or '')[-1500:]}"
            )
        _am_elapsed = time.time() - _am_t0

    _mux_elapsed = time.time() - _mux_t0
    print(
        f"[render] Final composite (clips+overlay+encode+audio) done in {_mux_elapsed:.1f}s "
        f"(audio mux={_am_elapsed:.1f}s)",
        flush=True,
    )
    print(
        f"[render] Total render: remotion={_render_elapsed:.1f}s audio={_audio_elapsed:.1f}s "
        f"composite={_mux_elapsed:.1f}s → {os.path.getsize(output_path)/1024/1024:.1f}MB",
        flush=True,
    )

    # ── A/V sync verification — RAISE on drift > 1 ms ─────────────────
    # The master MP4 audio is PCM s16le (sample-exact); video frame count
    # and audio sample count both derive from the same per-cut effective
    # durations. With PCM there is no codec frame-size to round to, so
    # stream durations should match within a single sample (~21µs at
    # 44.1kHz). Anything beyond 1ms indicates a real drift bug in the
    # filter chain or the cut math — fail the render so the bad file
    # never ships.
    _final_probe = _probe_full(output_path)
    _final_streams = _final_probe.get("streams") or []
    _final_v = next((s for s in _final_streams if s.get("codec_type") == "video"), {})
    _final_a = next((s for s in _final_streams if s.get("codec_type") == "audio"), {})
    _v_dur = float(_final_v.get("duration") or 0.0)
    _a_dur = float(_final_a.get("duration") or 0.0)
    _av_drift_ms = (_v_dur - _a_dur) * 1000.0
    _expected_dur = total_output_frames / float(source_fps)
    _v_drift_vs_expected_ms = (_v_dur - _expected_dur) * 1000.0
    # AAC has a 1024-sample frame size at 48 kHz = ~21.33 ms structural
    # floor on |video − audio| duration difference. That's a math floor,
    # not a pipeline bug. Threshold is set to 30 ms so genuine drift
    # bugs (cut-boundary mis-splices, filtergraph mismatch) still fire,
    # but a clean AAC mux at the expected frame boundary doesn't.
    print(
        f"[av-sync] video={_v_dur:.4f}s audio={_a_dur:.4f}s "
        f"v−a={_av_drift_ms:+.2f}ms  v−expected={_v_drift_vs_expected_ms:+.2f}ms "
        f"(expected={_expected_dur:.4f}s, target ≤±30ms)",
        flush=True,
    )
    if abs(_av_drift_ms) > 30.0:
        raise RuntimeError(
            f"A/V drift {_av_drift_ms:+.2f}ms exceeds 30ms target "
            f"(video={_v_dur:.4f}s audio={_a_dur:.4f}s expected={_expected_dur:.4f}s). "
            f"AAC's structural floor is ~21ms; anything beyond ~30ms indicates a "
            f"real bug — investigate cuts, transitions, audio extraction, or "
            f"composite filtergraph."
        )

    # Cleanup staged files in the bundle public root so it doesn't pile up.
    # work_dir itself is cleaned up by the caller (handler() in the finally
    # block), so input JSONs there get freed automatically.
    for _staged_path in _staged_for_cleanup:
        try:
            if os.path.lexists(_staged_path):
                os.unlink(_staged_path)
        except Exception as _rm_err:
            print(f"[render] WARNING: stage cleanup failed for {_staged_path}: {_rm_err}", flush=True)


# ─── CAPTION / COMPONENT VOCABULARIES ─────────────────────────────────────
# VALID_CAPTION_STYLES, VALID_TRANSITION_TYPES, VALID_ZOOM_TYPES, and
# VALID_MG_TYPES are imported from type_registries (handler.py:~88) — the
# canonical frozensets shared with render_schemas.py. Removed from this
# location 2026-06-14 to eliminate the duplicate-declaration drift class
# that produced three DipToBlack production crashes.


def _build_tiktok_pages_from_projected(projected_words, max_words_per_page=3, position_boundaries_sec=None, clip_boundaries_sec=None):
    """Convert projected Deepgram words into TikTokPage[] structured for the
    @remotion/captions types consumed by the pack caption components.

    Each page covers up to `max_words_per_page` consecutive words. Page
    boundaries break on:
      - large gaps (>0.6s)
      - sentence-end punctuation
      - position-change boundaries (so a page never spans top→bottom etc.;
        if it did, the page would be assigned by midpoint to one position
        and visually drift relative to its actual time range)
      - clip boundaries (so a page never spans a cut between two source
        clips; without this break, words from the end of clip A and the
        start of clip B render together during the transition window
        producing visible word-salad — e.g. the kept-transcript words
        "you gonna learn? What are you gonna play" cross a cut and the
        page renders both phrases on top of the LightLeak transition).
        Clip boundary breaks are independent of position-change breaks
        — a single timeline can have many clip cuts within one position
        segment.

    `position_boundaries_sec` and `clip_boundaries_sec` are both optional
    sorted lists of output-time seconds. Pages flush whenever a word's
    start time crosses any boundary in either list.
    """
    if not projected_words:
        return []
    pages = []
    current_tokens = []
    current_start_ms = None
    current_text_parts = []
    last_word_end = None
    SENTENCE_END = {".", "!", "?"}
    _bounds = list(position_boundaries_sec or [])
    _clip_bounds = list(clip_boundaries_sec or [])

    def _flush():
        nonlocal current_tokens, current_start_ms, current_text_parts, last_word_end
        if current_tokens and current_start_ms is not None:
            duration_ms = max(1, int(round(last_word_end * 1000)) - current_start_ms)
            pages.append({
                "text": " ".join(current_text_parts).strip(),
                "startMs": current_start_ms,
                "durationMs": duration_ms,
                "tokens": current_tokens,
            })
        current_tokens = []
        current_start_ms = None
        current_text_parts = []

    def _crosses_boundary(prev_end_sec, next_start_sec):
        # True iff any position boundary falls in [prev_end, next_start].
        if not _bounds:
            return False
        for b in _bounds:
            if prev_end_sec <= b <= next_start_sec:
                return True
        return False

    def _crosses_clip_boundary(prev_end_sec, next_start_sec):
        # True iff a cut between two source clips falls in [prev_end, next_start].
        # Same shape as _crosses_boundary; kept separate so each break-class can
        # be tuned / disabled independently from its callers.
        if not _clip_bounds:
            return False
        for b in _clip_bounds:
            if prev_end_sec <= b <= next_start_sec:
                return True
        return False

    for w in projected_words:
        w_start = float(w.get("start") or 0)
        w_end = float(w.get("end") or w_start)
        w_text = w.get("punctuated_word") or w.get("word") or ""
        if not w_text.strip():
            continue
        # Break on big gap, position-change boundary, or clip boundary
        if current_tokens and last_word_end is not None:
            if w_start - last_word_end > 0.6:
                _flush()
            elif _crosses_boundary(last_word_end, w_start):
                _flush()
            elif _crosses_clip_boundary(last_word_end, w_start):
                _flush()
        if current_start_ms is None:
            current_start_ms = int(round(w_start * 1000))
        # Token times are ABSOLUTE (output-time milliseconds), matching the
        # coordinate system of page.startMs. Caption components subtract
        # pageStartMs from token.fromMs to derive page-local time for word
        # activation animations — this only works when both are in the same
        # absolute coordinate system. Page-relative tokens broke every
        # component that does (token.fromMs - pageStartMs) because the
        # subtraction yielded a huge negative number.
        token_from_ms = int(round(w_start * 1000))
        token_to_ms = int(round(w_end * 1000))
        current_tokens.append({
            "text": w_text,
            "fromMs": token_from_ms,
            "toMs": max(token_from_ms + 1, token_to_ms),
        })
        current_text_parts.append(w_text)
        last_word_end = w_end
        # Break on max words or sentence end
        if len(current_tokens) >= max_words_per_page:
            _flush()
        elif w_text and w_text[-1] in SENTENCE_END:
            _flush()
    _flush()
    return pages


def _resolve_caption_extra_props(style, keywords, edit_plan):
    """Emit the correct keyword prop name for each caption style.

    Pack components use different prop names for "words to highlight":
    `highlightWords`, `boxedWords`, `specialWords`, `keywords`, `shineWords`, etc.
    We translate Gemini's single `caption_keywords` list + `caption_style_props`
    into the exact shape each style expects.
    """
    out = {}
    explicit = edit_plan.get("caption_style_props")
    if isinstance(explicit, dict):
        out.update(explicit)
    kw_list = list(keywords or [])

    # Style-specific default prop names for a simple string[] of keywords.
    # PaperII / TypewriterReveal / CinematicLetterpress / Quintessence
    # don't highlight specific words — their effect is style-driven
    # (typewriter sweep, spring per-word reveal, etc.) — so they're
    # omitted from this map.
    simple_keyword_prop = {
        "EditorialPop": "keywords",
        "Illuminate": "keywords",
        "Lumen": "keywords",
        "Passage": "keywords",
        "Pulse": "keywords",
        "Serif": "keywords",
        "Prime": "specialWords",
        "Cove": "boxedWords",
    }
    if style in simple_keyword_prop:
        prop_name = simple_keyword_prop[style]
        if kw_list and prop_name not in out:
            out[prop_name] = kw_list

    # EditorialPop's library default of maxWordsPerLine=3 overflows the 1080px
    # frame when a page has a keyword (scaled 1.7× at 136px italic-bold Playfair
    # Display) plus a long regular word — e.g. "main themes expressed" runs off
    # both edges. Override to 2 so worst-case lines fit; preserves the
    # designer's look (font, weight, stagger animation, page-by-page reveal),
    # only changes line-break density.
    if style == "EditorialPop" and "maxWordsPerLine" not in out:
        out["maxWordsPerLine"] = 2

    return out



# ─── MAIN HANDLER ─────────────────────────────────────────────────────────────

def classify_error(e):
    """
    Convert a pipeline exception into structured error data for the iOS app.

    Returns a dict with:
      • error_code: machine-readable code iOS can branch on
                    (e.g., 'UPLOAD_NEVER_STARTED', 'NOT_TALKING_HEAD')
      • user_message: human-friendly text safe to show directly
      • retryable: True if the user should see a "Try Again" button
                   (same video, same vibe — likely transient)
      • requires_new_video: True if the user needs to upload a different
                            clip (talking-head gate failed, file invalid)
      • requires_vibe_change: True if the user might need to edit their vibe
                              (Gemini couldn't make sense of the input)

    iOS uses these flags to build the appropriate failure screen:
      • retryable=True → "Try Again" button with the same source
      • requires_new_video=True → "Choose Different Video" button
      • requires_vibe_change=True → "Edit Prompt" button
      • all false → generic "Try Again Later" with support contact

    LEGACY CALLERS: this function used to return just a string. Existing
    callers that do `user_message = classify_error(e)` will receive a
    dict instead — they need to access `result["user_message"]`. The
    handler entry point has been updated to use the structured shape.
    """
    msg = str(e)
    msg_lower = msg.lower()

    def _e(code, message, retryable=True, new_video=False, vibe=False):
        return {
            "error_code": code,
            "user_message": message,
            "retryable": retryable,
            "requires_new_video": new_video,
            "requires_vibe_change": vibe,
        }

    # ── Input validation ──────────────────────────────────────────────
    if "NOT_TALKING_HEAD" in msg:
        return _e(
            "NOT_TALKING_HEAD",
            "This app edits videos of someone talking on camera. Please upload a talking-head video.",
            retryable=False, new_video=True,
        )

    # ── Upload / S3 / network arrival ─────────────────────────────────
    if "UPLOAD_NEVER_STARTED" in msg:
        return _e(
            "UPLOAD_NEVER_STARTED",
            "Your video didn't finish uploading. Please try again — if this keeps happening, restart the app.",
            retryable=True,
        )
    if "UPLOAD_STALLED" in msg:
        return _e(
            "UPLOAD_STALLED",
            "Your upload was interrupted before it finished. Check your connection and try again.",
            retryable=True,
        )
    if "did not arrive on S3" in msg or "Source video did not arrive" in msg:
        return _e(
            "UPLOAD_TIMEOUT",
            "Your upload didn't finish in time. Check your connection and try again.",
            retryable=True,
        )
    if "NoSuchKey" in msg or "AccessDenied" in msg or "InvalidAccessKey" in msg:
        return _e(
            "S3_ACCESS",
            "We had trouble accessing your video. Please try again.",
            retryable=True,
        )
    if "BotoCore" in msg or "ClientError" in msg or "S3" in msg:
        return _e(
            "S3_GENERIC",
            "We had trouble downloading your video. Please try again.",
            retryable=True,
        )

    # ── Network / connection ──────────────────────────────────────────
    if "ConnectionError" in msg or "Connection refused" in msg or "Read timed out" in msg:
        return _e(
            "NETWORK",
            "Network hiccup. Please check your connection and try again.",
            retryable=True,
        )
    if "rate limit" in msg_lower or "quota" in msg_lower or " 429" in msg or "TooManyRequests" in msg:
        return _e(
            "RATE_LIMIT",
            "We're temporarily at capacity. Please try again in a moment.",
            retryable=True,
        )

    # ── File / input problems — user must change the video ────────────
    if "No video stream found" in msg:
        return _e(
            "INVALID_FORMAT",
            "We couldn't read your video file. Please make sure it's a standard video format (MP4, MOV, or similar).",
            retryable=False, new_video=True,
        )
    if "Landscape video" in msg:
        return _e(
            "WRONG_ORIENTATION",
            "Promptly works with vertical videos (9:16). Please upload a portrait-orientation clip.",
            retryable=False, new_video=True,
        )
    if "No video data provided" in msg:
        return _e(
            "EMPTY_UPLOAD",
            "Your video didn't upload correctly. Please try again.",
            retryable=True,
        )

    # ── Transcription problems ────────────────────────────────────────
    if "Deepgram" in msg or "transcription failed" in msg_lower:
        return _e(
            "TRANSCRIPTION",
            "We had trouble understanding the audio. Please try a clip with clearer speech.",
            retryable=False, new_video=True,
        )

    # ── Analysis / Gemini ─────────────────────────────────────────────
    if "Gemini file upload timed out" in msg or "DEADLINE_EXCEEDED" in msg:
        return _e(
            "EDITOR_TIMEOUT",
            "Our editor took too long. Please try again.",
            retryable=True,
        )
    if "Empty Gemini response" in msg or "valid JSON from Gemini" in msg or "Failed to parse Gemini" in msg or "parse Gemini" in msg:
        return _e(
            "EDITOR_PARSE",
            "We had trouble generating your edit. Please try again.",
            retryable=True,
        )
    if "Gemini" in msg or "GEMINI_API_KEY" in msg:
        return _e(
            "EDITOR_GENERIC",
            "Our editor service had a hiccup. Please try again.",
            retryable=True,
        )

    # ── Edit generation — no cuts produced ────────────────────────────
    if "missing cuts array" in msg or "removed all words" in msg or "no clips remain" in msg:
        return _e(
            "EMPTY_EDIT",
            "We couldn't generate an edit for this video. Try a different vibe or a longer clip.",
            retryable=True, vibe=True,
        )

    # ── Plan validation ───────────────────────────────────────────────
    if "source_start" in msg or "source_end" in msg or "chronological" in msg:
        return _e(
            "PLAN_INVALID",
            "We had trouble generating your edit. Please try again.",
            retryable=True,
        )
    if "ValidationError" in msg or "validation error" in msg_lower or "pydantic" in msg_lower:
        return _e(
            "PLAN_VALIDATION",
            "We had trouble generating your edit. Please try again.",
            retryable=True,
        )

    # ── Render problems ───────────────────────────────────────────────
    if "FFmpeg failed" in msg or "FFmpeg" in msg or "ffmpeg" in msg or "Pre-split mismatch" in msg:
        return _e(
            "RENDER_FFMPEG",
            "We had trouble rendering your video. Please try again.",
            retryable=True,
        )
    if "Remotion" in msg or "Chromium" in msg or "render failed" in msg_lower:
        return _e(
            "RENDER_REMOTION",
            "We had trouble rendering your video. Please try again.",
            retryable=True,
        )

    # ── B-roll fetch ──────────────────────────────────────────────────
    if "Pexels" in msg or "broll" in msg_lower:
        return _e(
            "BROLL",
            "We had trouble finding cutaway footage. Please try again.",
            retryable=True,
        )

    # ── Config / internal — user can't fix, keep it vague — log loudly
    # so we know what's landing in this bucket. If you see a category
    # repeating in [error-fallback] logs, add a specific pattern above.
    print(f"[error-fallback] Unclassified pipeline error: {msg[:500]}", flush=True)
    return _e(
        "UNKNOWN",
        "Something went wrong. Please try again.",
        retryable=True,
    )


def send_progress(job_id, step, pct, message, app_url):
    """
    POST progress update to the JS server. Fire-and-forget in background thread.
    Never blocks the main pipeline — progress updates are best-effort only.
    """
    if not app_url:
        return
    import threading
    def _fire():
        try:
            requests.post(
                f"{app_url}/api/modal-progress",
                json={"job_id": job_id, "step": step, "pct": pct, "message": message},
                timeout=3,
            )
        except Exception:
            pass
    threading.Thread(target=_fire, daemon=True).start()


def _start_progress_heartbeat(
    job_id, step, start_pct, end_pct, message, app_url,
    interval_s=4.0, duration_estimate_s=40.0,
):
    """Tick progress steadily from start_pct toward end_pct over the
    estimated duration so the UI bar doesn't appear stuck during a long
    opaque operation (Gemini editorial call, render). Returns a stop_event
    — call .set() to halt the heartbeat as soon as the real work completes.

    `message` may be a string (sent at every tick) OR a list of strings
    (rotated through tick-by-tick so the user sees DIFFERENT messages
    instead of one message that never changes — addresses "stuck at 43%"
    perception even though the bar is moving).

    The heartbeat sends progress updates at `interval_s` intervals, advancing
    by (end_pct - start_pct)/n_ticks each tick. If the real work finishes
    early, the heartbeat is stopped and the bar caps at whatever tick we
    reached. If the real work runs LONGER than the estimate, the bar caps
    at end_pct AND the last message in the list is held — still appears
    stuck at the high end of the range, but feels much closer to done.

    Fire-and-forget threads only — never blocks; never errors propagate.
    """
    import threading
    stop_event = threading.Event()

    if not app_url or start_pct >= end_pct or duration_estimate_s <= 0:
        return stop_event

    n_ticks = max(1, int(duration_estimate_s / interval_s))
    pct_step = (end_pct - start_pct) / float(n_ticks)

    # Support either a single string (legacy callers) or a list of
    # messages to rotate through.
    if isinstance(message, str):
        message_list = [message]
    else:
        message_list = list(message) if message else ["Working..."]

    def _tick():
        current = float(start_pct)
        for tick_idx in range(n_ticks):
            if stop_event.wait(interval_s):
                return
            current = min(float(end_pct), current + pct_step)
            # Pick message: as the bar progresses, advance through the
            # message list proportionally. Hold the LAST message if we
            # overshoot the estimated duration.
            msg_idx = min(
                len(message_list) - 1,
                int((tick_idx / max(1, n_ticks - 1)) * len(message_list)),
            )
            send_progress(job_id, step, int(round(current)), message_list[msg_idx], app_url)

    threading.Thread(target=_tick, daemon=True).start()
    return stop_event


# ─── Prewarm cache (eliminates the download step on cached jobs) ─────────────
#
# iOS fires a /prewarm request the instant the client-side S3 upload finishes,
# well before the user taps Send. prewarm_handler downloads the source video
# into /prewarm/{hash}/source.mp4 on the Modal Volume. When the real render
# job arrives, it hashes the same bucket+key and — if the cached file exists —
# copies it locally and skips the S3 download entirely (saves 5-15s).

PREWARM_CACHE_ROOT = "/prewarm"


def _prewarm_cache_key(bucket, key):
    import hashlib
    return hashlib.sha1(f"{bucket}/{key}".encode()).hexdigest()[:16]


def _prewarm_cached_source_path(bucket, key):
    return os.path.join(PREWARM_CACHE_ROOT, _prewarm_cache_key(bucket, key), "source.mp4")


def _prewarm_cached_transcript_path(bucket, key):
    return os.path.join(PREWARM_CACHE_ROOT, _prewarm_cache_key(bucket, key), "transcript.json")


def _prewarm_cached_audio_path(bucket, key):
    """Pre-extracted source audio wav. Saves ~3-5s in build_per_cut_audio
    when render finds it sitting next to source.mp4 in work_dir."""
    return os.path.join(PREWARM_CACHE_ROOT, _prewarm_cache_key(bucket, key), "source_audio_full.wav")


def _prewarm_cached_proxy_path(bucket, key):
    """Pre-encoded 480p@16fps Gemini proxy. When the prewarm worker runs
    during the iOS upload, we encode this proxy from the source as soon as
    the source lands. By the time the render dispatches, the proxy is
    sitting in the cache and `_do_gemini_proxy` finds it instead of
    re-encoding. Saves ~7-10s off the render's critical path.

    Skipped entirely when the iOS client uploads its own proxy via
    `proxy_video_url` — in that case the worker uses the client-uploaded
    file (even cheaper, no on-server encode at all)."""
    return os.path.join(PREWARM_CACHE_ROOT, _prewarm_cache_key(bucket, key), "gemini_proxy.mp4")


def prewarm_handler(job):
    """Aggressive pre-processing during iOS upload.

    Runs S3 download AND URL-based Deepgram transcription in parallel, caching
    both into the Modal Volume keyed by sha1(bucket/key). When the real render
    job arrives and hits cache, it skips BOTH stages entirely — UI never shows
    'Loading your footage' OR 'Transcribing every word'.

    Idempotent: if artifacts already exist, returns immediately. Fire-and-forget
    from iOS attach, so latency here doesn't affect UX.
    """
    print(
        f"[prewarm] BUILD sha={os.environ.get('PROMPTLY_BUILD_SHA', 'unknown')[:12]} "
        f"dirty={os.environ.get('PROMPTLY_BUILD_DIRTY', '?')} "
        f"ts={os.environ.get('PROMPTLY_BUILD_TS', '?')}",
        flush=True,
    )
    input_data = job.get("input") or {}
    try:
        video_url = str(input_data.get("video_url") or "").strip()
        if not video_url:
            return {"error": "missing video_url"}

        dl_bucket, dl_key = _parse_aws_s3_url(video_url)
        if not dl_bucket or not dl_key:
            return {"error": "not an AWS S3 URL"}
        if not _aws_s3_client:
            return {"error": "S3 client not initialized"}

        cache_key = _prewarm_cache_key(dl_bucket, dl_key)
        cache_dir = os.path.join(PREWARM_CACHE_ROOT, cache_key)
        source_cache = os.path.join(cache_dir, "source.mp4")
        transcript_cache = _prewarm_cached_transcript_path(dl_bucket, dl_key)
        audio_cache = _prewarm_cached_audio_path(dl_bucket, dl_key)
        proxy_cache = _prewarm_cached_proxy_path(dl_bucket, dl_key)

        source_hit = os.path.exists(source_cache) and os.path.getsize(source_cache) > 1024
        transcript_hit = os.path.exists(transcript_cache) and os.path.getsize(transcript_cache) > 2
        audio_hit = os.path.exists(audio_cache) and os.path.getsize(audio_cache) > 1024
        proxy_hit = os.path.exists(proxy_cache) and os.path.getsize(proxy_cache) > 1024

        if source_hit and transcript_hit and audio_hit and proxy_hit:
            size_mb = os.path.getsize(source_cache) / (1024 * 1024)
            print(f"[prewarm] FULL HIT {cache_key} ({size_mb:.1f}MB source + transcript + audio + proxy)", flush=True)
            return {"status": "cached", "cache_key": cache_key, "size_mb": round(size_mb, 1)}

        os.makedirs(cache_dir, exist_ok=True)

        # iOS fires prewarm as soon as the eventual S3 URL is known
        # (right after multipart-init), which can be well before the
        # upload has completed. Poll HEAD for the object to appear
        # before trying to download. This lets Deepgram + source
        # download start within milliseconds of upload-complete instead
        # of waiting for a separate client-side "now fire prewarm"
        # roundtrip — usually saves 10-15s of post-send latency.
        # Two-stage polling with EARLY DETECTION of "upload never started":
        # at the 30s mark, check ListMultipartUploads to detect the iOS
        # dispatch-before-upload race condition. See the matching logic in
        # the render handler for full context. Same fail-fast pattern.
        poll_start = time.time()
        # 30 min. iOS background URLSession is willing to push for 30 min
        # before iOS itself gives up (timeoutIntervalForResource), and a
        # multi-hundred-MB clip on slow cellular legitimately takes ~10-15
        # min. The old 5-min cap was hard-failing healthy uploads that
        # were still streaming bytes. Match the client's tolerance.
        poll_deadline = poll_start + 1800
        poll_attempt = 0
        while True:
            poll_attempt += 1
            try:
                _aws_s3_client.head_object(Bucket=dl_bucket, Key=dl_key)
                if poll_attempt > 1:
                    print(f"[prewarm] S3 object available after {time.time() - poll_start:.1f}s "
                          f"({poll_attempt} polls)", flush=True)
                break
            except Exception as head_err:
                now = time.time()
                elapsed = now - poll_start
                code = getattr(head_err, 'response', {}).get('Error', {}).get('Code', 'unknown')

                # NOTE: previously there was a 60s "UPLOAD_NEVER_STARTED" precheck
                # here that aborted the prewarm if list_multipart_uploads showed
                # nothing in flight. Removed — single PUT uploads (URLSession
                # background, used by iOS Promptly client for small files) NEVER
                # appear in list_multipart_uploads, so the precheck was killing
                # 100% of single-PUT prewarms at exactly 60s and forcing the
                # user-visible upload to fail. Just poll until the deadline.

                if now >= poll_deadline:
                    print(f"[prewarm] timed out waiting for S3 object after "
                          f"{elapsed:.1f}s (last={code})", flush=True)
                    return {"error": "UPLOAD_STALLED", "cache_key": cache_key}
                # Adaptive backoff: poll fast while upload is plausibly
                # almost done, back off as time passes so we don't hammer
                # HEAD requests on huge slow uploads.
                wait = 1.0 if elapsed < 10 else (2.0 if elapsed < 60 else 4.0)
                time.sleep(wait)

        t0 = time.time()

        # Presigned GET so Deepgram can fetch from S3 in parallel with our own download.
        presigned_url = None
        try:
            presigned_url = _aws_s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": dl_bucket, "Key": dl_key},
                ExpiresIn=600,
            )
        except Exception as _ps_err:
            print(f"[prewarm] presigned URL gen failed: {_ps_err}", flush=True)

        # Download first, then transcribe with audio prep. URL-based
        # transcription is gone — file-based with FLAC loudnorm prep gives
        # measurably better accuracy on quiet/soft-spoken sources.
        if not source_hit:
            print(f"[prewarm] start download → {cache_key}/source.mp4", flush=True)
            _aws_s3_client.download_file(dl_bucket, dl_key, source_cache, Config=_S3_TRANSFER_CONFIG)

        if not transcript_hit and DeepgramClient is not None and os.path.exists(source_cache):
            print(f"[prewarm] start file-based transcribe (with FLAC prep) → {cache_key}/transcript.json", flush=True)
            try:
                _tx_result = transcribe_audio(source_cache)
                if _tx_result is not None and _tx_result.get("words"):
                    with open(transcript_cache, "w") as f:
                        json.dump(_tx_result, f)
                    print(f"[prewarm] transcript cached ({len(_tx_result['words'])} words)", flush=True)
            except Exception as _tx_err:
                print(f"[prewarm] transcribe failed: {str(_tx_err)[:200]} (main job will retry)", flush=True)

        # Extract source audio to a wav alongside source.mp4. The render's
        # build_per_cut_audio runs the SAME ffmpeg extraction at the start of
        # the audio pipeline (~2-4s on a 60s source); doing it here means
        # render finds the wav already sitting in work_dir and skips the
        # extraction. Sample rate matches what render's probe will pick
        # because we probe the same source file.
        if not audio_hit and os.path.exists(source_cache):
            try:
                _audio_rate = probe_audio_sample_rate(source_cache) or 48000
                _audio_t0 = time.time()
                _ar = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error",
                     "-i", source_cache, "-vn",
                     "-acodec", "pcm_s16le", "-ar", str(_audio_rate), "-ac", "1",
                     audio_cache],
                    capture_output=True, text=True, timeout=120,
                )
                if _ar.returncode == 0 and os.path.exists(audio_cache) and os.path.getsize(audio_cache) > 1024:
                    _wav_mb = os.path.getsize(audio_cache) / (1024 * 1024)
                    print(
                        f"[prewarm] audio cached ({_audio_rate}Hz, {_wav_mb:.1f}MB in "
                        f"{time.time() - _audio_t0:.1f}s)",
                        flush=True,
                    )
                else:
                    print(
                        f"[prewarm] audio extraction skipped (rc={_ar.returncode}) — "
                        f"render will extract on demand",
                        flush=True,
                    )
            except Exception as _ae:
                print(f"[prewarm] audio extraction error: {_ae} — render will extract", flush=True)

        # Gemini proxy encode — 480p @ 18fps, matches the render-time
        # _do_gemini_proxy spec exactly. Encoding here during prewarm (while
        # iOS upload is still completing or just after) hides the encode
        # cost behind upload latency, saving ~7-10s off the render's
        # critical path. If the iOS client uploads its own proxy via
        # `proxy_video_url`, the render uses that instead and this cached
        # copy is unused — pay-once-use-twice insurance.
        if not proxy_hit and os.path.exists(source_cache):
            try:
                _proxy_t0 = time.time()
                _hw_dec = ["-hwaccel", "cuda"] if _HAS_HWACCEL else []
                _proxy_venc = (
                    ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "32"]
                    if _HAS_NVENC else
                    ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30"]
                )
                _pr = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-threads", "0"] + _hw_dec + [
                     "-i", source_cache,
                     "-vf", "scale=480:-2,fps=18"] + _proxy_venc + [
                     "-c:a", "libopus", "-b:a", "64k", "-ac", "1",
                     proxy_cache],
                    capture_output=True, text=True, timeout=60,
                )
                if _pr.returncode == 0 and os.path.exists(proxy_cache) and os.path.getsize(proxy_cache) > 1024:
                    _px_mb = os.path.getsize(proxy_cache) / (1024 * 1024)
                    print(
                        f"[prewarm] proxy cached (480p@16fps, {_px_mb:.1f}MB in "
                        f"{time.time() - _proxy_t0:.1f}s)",
                        flush=True,
                    )
                else:
                    print(
                        f"[prewarm] proxy encode skipped (rc={_pr.returncode}) — "
                        f"render will encode on demand",
                        flush=True,
                    )
            except Exception as _pe:
                print(f"[prewarm] proxy encode error: {_pe} — render will encode", flush=True)

        elapsed = time.time() - t0
        size_mb = os.path.getsize(source_cache) / (1024 * 1024) if os.path.exists(source_cache) else 0
        print(f"[prewarm] cached {cache_key} ({size_mb:.1f}MB in {elapsed:.1f}s)", flush=True)
        return {
            "status": "success",
            "cache_key": cache_key,
            "size_mb": round(size_mb, 1),
            "download_time": round(elapsed, 1),
            "transcript_cached": os.path.exists(transcript_cache),
            "proxy_cached": os.path.exists(proxy_cache),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def diagnose_upload_handler(job):
    """Real-time diagnostic of an S3 upload's actual state.

    Call this while the iOS app says "uploading video" to see what S3
    actually sees. Tells us exactly which stage iOS is failing at:

      • Object already exists → upload finished, render dispatch is what's
        broken
      • Multipart upload exists with 0 parts → iOS started multipart but
        hasn't uploaded any bytes
      • Multipart upload exists with parts → iOS is uploading but stalled
        partway
      • Nothing exists → iOS hasn't started the upload at all
      • Multipart upload finished long ago but no object → iOS uploaded
        parts but never called CompleteMultipartUpload (most common
        failure mode for stuck "uploading video" UI)

    Input:
        {"bucket": "<bucket-name>", "key": "<object-key>"}
    """
    try:
        input_data = job.get("input", {})
        bucket = (input_data.get("bucket") or "").strip()
        key = (input_data.get("key") or "").strip()
        if not bucket or not key:
            return {"error": "missing bucket or key"}

        result = {
            "object_exists": False,
            "object_size_bytes": None,
            "multipart_uploads": [],
            "diagnosis": "",
        }

        # Check if the object exists already (upload finished).
        try:
            head = _aws_s3_client.head_object(Bucket=bucket, Key=key)
            result["object_exists"] = True
            result["object_size_bytes"] = int(head.get("ContentLength", 0))
        except Exception:
            pass

        # List any in-progress multipart uploads for this key.
        try:
            mp_resp = _aws_s3_client.list_multipart_uploads(
                Bucket=bucket, Prefix=key,
            )
            for mp in (mp_resp.get("Uploads") or []):
                if mp.get("Key") != key:
                    continue
                upload_id = mp.get("UploadId")
                initiated = mp.get("Initiated")
                parts_count = 0
                parts_size = 0
                most_recent_part = None
                try:
                    parts_resp = _aws_s3_client.list_parts(
                        Bucket=bucket, Key=key, UploadId=upload_id,
                    )
                    for part in (parts_resp.get("Parts") or []):
                        parts_count += 1
                        parts_size += int(part.get("Size", 0))
                        last_mod = part.get("LastModified")
                        if last_mod and (
                            most_recent_part is None or last_mod > most_recent_part
                        ):
                            most_recent_part = last_mod
                except Exception as _lp_err:
                    print(f"[diagnose] list_parts failed: {_lp_err}", flush=True)
                result["multipart_uploads"].append({
                    "upload_id": str(upload_id)[:32] + "…",
                    "initiated_at": initiated.isoformat() if initiated else None,
                    "parts_uploaded": parts_count,
                    "parts_total_size_bytes": parts_size,
                    "most_recent_part_at": (
                        most_recent_part.isoformat() if most_recent_part else None
                    ),
                })
        except Exception as _mp_err:
            print(f"[diagnose] list_multipart_uploads failed: {_mp_err}", flush=True)

        # Human-readable diagnosis.
        if result["object_exists"]:
            result["diagnosis"] = (
                f"Object exists ({result['object_size_bytes']} bytes). "
                f"Upload completed successfully. If render is still failing, "
                f"the bug is in the render-dispatch step (iOS calling render "
                f"with wrong key or dispatching twice)."
            )
        elif not result["multipart_uploads"]:
            result["diagnosis"] = (
                "No object AND no in-progress multipart upload. iOS hasn't "
                "started uploading. The bug is in iOS's upload initiation — "
                "auth error, network failure, wrong endpoint, or bad file path."
            )
        else:
            mp = result["multipart_uploads"][0]
            if mp["parts_uploaded"] == 0:
                result["diagnosis"] = (
                    "Multipart upload CREATED but ZERO parts uploaded. iOS "
                    "called CreateMultipartUpload but isn't sending any bytes. "
                    "Likely: presigned URL expired, auth issue, or iOS's "
                    "UploadPart calls failing silently."
                )
            else:
                result["diagnosis"] = (
                    f"Multipart upload has {mp['parts_uploaded']} parts "
                    f"({mp['parts_total_size_bytes']} bytes) uploaded but no "
                    f"final object. iOS is either still uploading (check "
                    f"most_recent_part_at — recent = progressing) OR has "
                    f"uploaded all parts but never called CompleteMultipartUpload."
                )

        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "diagnosis": "Diagnostic itself failed"}


def validate_handler(job):
    """Fast pre-upload validation: is this a talking-head video?

    Called BEFORE the user commits to the full upload + render. iOS extracts
    a small ~5-second sample of the video, uploads it to S3, then calls this
    endpoint with the sample URL. We download the sample (~1-2s for 5MB),
    run face detection (~1-2s), and return a structured response telling iOS
    whether to proceed with the full upload OR show the user "this isn't a
    talking-head video, try another."

    Total round-trip: 3-7 seconds. The user gets feedback BEFORE waiting for
    the full upload + full pipeline, so non-talking-head videos are caught
    early without burning compute on a doomed render.

    Input:
        {"sample_url": "<s3 URL of 5-second video sample>"}

    Output:
        {
            "is_talking_head": bool,
            "confidence": float (0-1),
            "face_ratio": float (0-1),
            "face_samples": int,
            "reason": str,                  # human-readable explanation
            "user_message": str | None,     # null when valid; reject text when not
        }
    """
    work_dir = None
    try:
        input_data = job.get("input", {})
        sample_url = (input_data.get("sample_url") or "").strip()
        if not sample_url:
            return {
                "error": "missing sample_url",
                "is_talking_head": None,
                "user_message": "Validation failed — please try again.",
            }

        work_dir = tempfile.mkdtemp(prefix="validate_")
        sample_path = os.path.join(work_dir, "sample.mp4")

        # Download the sample (small file, fast).
        try:
            dl_bucket, dl_key = _parse_aws_s3_url(sample_url)
        except Exception:
            return {
                "error": "invalid sample_url",
                "is_talking_head": None,
                "user_message": "We couldn't read the sample file. Please try again.",
            }

        try:
            _aws_s3_client.download_file(dl_bucket, dl_key, sample_path)
        except Exception as _dl_err:
            return {
                "error": f"download failed: {_dl_err}",
                "is_talking_head": None,
                "user_message": "We couldn't read the sample file. Please try again.",
            }

        _sample_size = os.path.getsize(sample_path) / (1024 * 1024)
        print(
            f"[validate] sample downloaded ({_sample_size:.1f}MB) — "
            f"running face detection",
            flush=True,
        )

        # Quick face detection — sample every 6 frames (~one detection per
        # half-second of source at 12fps proxy speed). Trades coverage for
        # speed; we don't need dense sampling to determine "is there a face."
        _t0 = time.time()
        face_positions = detect_face_positions_dense(
            sample_path, every_n_frames=6,
        )
        _face_samples = len(face_positions or [])
        _face_hits = sum(
            1 for _fp in (face_positions or [])
            if isinstance(_fp, dict) and _fp.get("found")
        )
        _face_ratio = (_face_hits / _face_samples) if _face_samples > 0 else 0.0
        _elapsed = time.time() - _t0

        print(
            f"[validate] face_ratio={_face_ratio:.2f} "
            f"({_face_hits}/{_face_samples} samples) in {_elapsed:.1f}s",
            flush=True,
        )

        # Validation thresholds — match the server-side full-pipeline gate
        # but slightly more lenient since this is the FIRST line of defense.
        # If the sample is borderline, let it proceed and rely on the
        # full-pipeline gate as backup.
        FACE_THRESHOLD = 0.25
        MIN_SAMPLES = 4

        if _face_samples < MIN_SAMPLES:
            # Sample too short or face detector couldn't sample frames —
            # don't reject, defer to full-pipeline gate.
            return {
                "is_talking_head": True,
                "confidence": 0.3,
                "face_ratio": _face_ratio,
                "face_samples": _face_samples,
                "reason": "sample too short for confident validation; proceeding",
                "user_message": None,
            }

        is_talking_head = _face_ratio >= FACE_THRESHOLD
        confidence = min(1.0, _face_ratio / FACE_THRESHOLD) if is_talking_head else min(1.0, (FACE_THRESHOLD - _face_ratio) / FACE_THRESHOLD)

        if not is_talking_head:
            return {
                "is_talking_head": False,
                "confidence": confidence,
                "face_ratio": _face_ratio,
                "face_samples": _face_samples,
                "reason": (
                    f"face detected in only {_face_hits}/{_face_samples} "
                    f"({_face_ratio*100:.0f}%) sampled frames"
                ),
                "user_message": (
                    "This app edits videos of someone talking on camera. "
                    "Please choose a different video."
                ),
            }

        return {
            "is_talking_head": True,
            "confidence": confidence,
            "face_ratio": _face_ratio,
            "face_samples": _face_samples,
            "reason": "valid talking-head sample",
            "user_message": None,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        # On unexpected validation failure, return is_talking_head=True so
        # iOS doesn't block the user — the full-pipeline gate will catch any
        # genuine non-talking-head video as the last line of defense.
        return {
            "is_talking_head": True,
            "confidence": 0.0,
            "error": str(e),
            "reason": "validation error; proceeding (full pipeline will validate)",
            "user_message": None,
        }
    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


def _quick_face_check(source_path, max_samples=8):
    """Fast face-content check on the raw source video. Designed to run
    IMMEDIATELY after source download (before proxy encode and other
    parallel pipeline work) so we can fail-fast on non-talking-head
    videos in ~2-3 seconds post-download instead of waiting 30-60s for
    the full pipeline gate.

    Samples up to `max_samples` evenly-spaced frames via OpenCV (no
    ffmpeg subprocess), runs DNN face detection on each. Returns a tuple
    of (face_ratio, samples_taken). face_ratio is the fraction of sampled
    frames where a face was detected with confidence >= 0.5.

    Calibrated for SPEED, not coverage — we just need a coarse signal of
    "is there a person on camera." The full-pipeline face tracker still
    runs later on the proxy with dense sampling.
    """
    import cv2 as _cv2
    cap = _cv2.VideoCapture(source_path)
    try:
        if not cap.isOpened():
            return 0.0, 0
        total_frames = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames < max_samples:
            max_samples = max(1, total_frames)
        # Evenly spaced sample indices, avoiding very first/last frames
        # (some phone cameras have leader/trailer black frames).
        start = int(total_frames * 0.05)
        end = int(total_frames * 0.95)
        if end <= start:
            return 0.0, 0
        stride = max(1, (end - start) // max_samples)

        # DNN face detector — loaded fresh per call (cheap on small sample
        # count, and avoids global state issues across concurrent jobs).
        PROTOTXT = "/models/face_detector/deploy.prototxt"
        CAFFEMODEL = "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"
        if not (os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL)):
            # Models not installed — fail OPEN (don't block) and let the
            # full-pipeline gate handle validation. Better to occasionally
            # over-accept than to false-positive reject due to missing models.
            return 1.0, 0
        net = _cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
        CONFIDENCE_THRESHOLD = 0.5

        face_hits = 0
        samples_taken = 0
        for i in range(max_samples):
            frame_idx = start + i * stride
            if frame_idx >= total_frames:
                break
            cap.set(_cv2.CAP_PROP_POS_FRAMES, float(frame_idx))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            samples_taken += 1
            # Downsample for detection — 300x300 is what the SSD expects.
            h, w = frame.shape[:2]
            blob = _cv2.dnn.blobFromImage(
                _cv2.resize(frame, (300, 300)),
                1.0, (300, 300), (104.0, 177.0, 123.0),
            )
            net.setInput(blob)
            detections = net.forward()
            for j in range(detections.shape[2]):
                conf = float(detections[0, 0, j, 2])
                if conf >= CONFIDENCE_THRESHOLD:
                    face_hits += 1
                    break  # one face per frame is enough
        ratio = (face_hits / samples_taken) if samples_taken > 0 else 0.0
        return ratio, samples_taken
    finally:
        cap.release()


def handler(job):
    input_data = job["input"]
    work_dir = None
    try:
        app_url = os.environ.get("APP_URL", "").rstrip("/")

        required = ["job_id","video_url","vibe","user_id","upload_url"]
        missing = [f for f in required if not input_data.get(f)]
        if missing:
            return {"error": f"Missing required input fields: {', '.join(missing)}"}

        job_id    = input_data["job_id"]
        video_url = input_data["video_url"]

        # ── Tier gate (multi-clip premium feature) ───────────────────────
        # The frontend is the primary gate (only premium users can pick
        # multiple files at the upload UI). This is the defense-in-depth
        # check: a non-premium user calling the API directly with a second
        # concurrent job gets rejected here before the render kicks off.
        # Premium users have no worker-side concurrency cap.
        # FAIL OPEN on Supabase trouble — see check_concurrency_gate doc.
        _gate = check_concurrency_gate(input_data["user_id"], job_id)
        if _gate is not None:
            print(
                f"[tier-gate] REJECTING job_id={job_id} user={input_data['user_id'][:8]}… "
                f"tier={_gate['tier']} active_jobs={_gate['active_jobs']} — "
                f"non-premium concurrent submission",
                flush=True,
            )
            return _gate
        # Optional client-side low-res proxy. When the iOS client extracts
        # a 640x480 proxy on-device and uploads it ahead of the high-res
        # source, this URL points to the proxy file. The worker uses it
        # for Gemini visual analysis — eliminating the worker's own
        # on-server proxy encode step (~7s saved) AND letting Gemini
        # start running the moment the small proxy lands (the high-res
        # is typically still uploading in the client's background).
        proxy_video_url = str(input_data.get("proxy_video_url") or "").strip()
        vibe      = input_data["vibe"]
        upload_url = input_data["upload_url"]
        user_id   = input_data["user_id"]

        # ── Re-edit mode resolution ──────────────────────────────────────
        # mode: "full" (default — fresh plan), "render_only" (render supplied plan
        # deterministically), "tweak" (plan-diff + render new plan),
        # "guided_redraft" (full pipeline WITH prior plan injected as soft
        # default — Layer 2 of the re-edit improvements), "reinterpret"
        # (fuse old vibe + change_request, full pipeline with NO prior plan).
        # The frontend typically submits "tweak" or "reinterpret"; the
        # classifier inside generate_plan_diff may downgrade or upgrade
        # between tweak / guided_redraft / reinterpret based on what the
        # change_request actually warrants.
        mode = str(input_data.get("mode") or "full").strip().lower()
        if mode not in ("full", "render_only", "tweak", "guided_redraft", "reinterpret"):
            mode = "full"
        provided_plan = input_data.get("edit_plan") if isinstance(input_data.get("edit_plan"), dict) else None
        provided_transcript = input_data.get("transcript") if isinstance(input_data.get("transcript"), dict) else None
        provided_analysis = input_data.get("analysis_data") if isinstance(input_data.get("analysis_data"), dict) else None
        provided_broll = input_data.get("resolved_broll") if isinstance(input_data.get("resolved_broll"), list) else None
        provided_trend = input_data.get("trend_snapshot") if isinstance(input_data.get("trend_snapshot"), dict) else None
        change_request = str(input_data.get("change_request") or "").strip()
        old_vibe = str(input_data.get("old_vibe") or "").strip()

        # Validate re-edit mode inputs up front — fail fast with a clear message.
        if mode == "render_only" and not provided_plan:
            return {"error": "render_only mode requires edit_plan in input"}
        if mode == "tweak" and (not provided_plan or not change_request):
            return {"error": "tweak mode requires edit_plan + change_request in input"}
        if mode == "guided_redraft" and (not provided_plan or not change_request):
            return {"error": "guided_redraft mode requires edit_plan + change_request in input"}
        if mode == "reinterpret" and not change_request:
            return {"error": "reinterpret mode requires change_request in input"}

        work_dir    = tempfile.mkdtemp(prefix=f"promptly-{job_id}-")
        source_path = os.path.join(work_dir, "source.mp4")
        output_path = os.path.join(work_dir, "output.mp4")

        print(f"\n{'='*80}", flush=True)
        print(f"JOB {job_id}: \"{vibe}\"", flush=True)
        # Build identification — answers "which build ran this render?" with
        # zero ambiguity. After a deploy, warm containers may keep serving
        # the OLD code for up to scaledown_window seconds; this line lets
        # you cross-reference any failure to the exact git SHA the container
        # was built from. _BUILD_DIRTY=1 means the deploy was made with
        # uncommitted local changes (dev iteration, not a clean build).
        _build_sha = os.environ.get("PROMPTLY_BUILD_SHA", "unknown")
        _build_dirty = os.environ.get("PROMPTLY_BUILD_DIRTY", "?")
        _build_ts = os.environ.get("PROMPTLY_BUILD_TS", "?")
        print(
            f"BUILD sha={_build_sha[:12]} dirty={_build_dirty} ts={_build_ts}",
            flush=True,
        )
        print(f"{'='*80}", flush=True)
        _pipeline_start = time.time()
        _timings = {}

        # Step 1 — Download + parallel stage kickoff
        # ─────────────────────────────────────────────────────────────────
        # Deepgram accepts a remote URL directly; trend context is a DB
        # lookup that doesn't need the video at all. We fire both on a
        # background pool the moment the request lands, so they run
        # concurrently with the Modal→S3 byte transfer instead of waiting
        # for it. With a healthy download (~2-5s after boto3[crt]) the
        # transcript usually lands within a few seconds of the file — any
        # overlap is pure win.
        t = time.time()
        _dl_bucket, _dl_key = _parse_aws_s3_url(video_url)
        if not _dl_bucket or not _dl_key:
            raise RuntimeError(f"Not a valid AWS S3 URL: {video_url}")
        if not _aws_s3_client:
            raise RuntimeError("AWS S3 client not initialized — check AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION in Modal secrets")

        # ── Prewarm cache check — SKIP emitting `download` / `transcribe`
        # tokens entirely when the prewarm lane pre-computed them. Anything
        # we can satisfy from the Volume, we do — silently — so the client
        # UI never shows "Loading your footage" or "Transcribing every word"
        # for work that's already done. First user-visible stage in the
        # hot path becomes face_detect, or on re-edit paths, plan.
        #
        # Server passes a `prewarm_status` hint when it has seen the prewarm
        # call complete. We use the hint to detect the Modal Volume eventual-
        # consistency race: if server says source_cached but the file isn't
        # here yet, a cross-container sync hasn't landed — we emit a loud
        # metric so hit rate is observable in prod.
        _prewarm_hint = input_data.get("prewarm_status") or {}
        _hint_source_cached = bool(_prewarm_hint.get("source_cached"))
        _hint_transcript_cached = bool(_prewarm_hint.get("transcript_cached"))

        _cached_source_path = _prewarm_cached_source_path(_dl_bucket, _dl_key)
        _cached_transcript_path = _prewarm_cached_transcript_path(_dl_bucket, _dl_key)
        _has_cached_source = os.path.exists(_cached_source_path) and os.path.getsize(_cached_source_path) > 1024
        _has_cached_transcript = (
            not provided_transcript
            and os.path.exists(_cached_transcript_path)
            and os.path.getsize(_cached_transcript_path) > 2
        )

        # Volume eventual-consistency safety net: if the server-passed hint
        # says a file IS cached but we don't see it, the cross-container sync
        # may just not have propagated yet. Try ONE explicit reload + recheck
        # with a short delay — most "races" resolve in under a second. If it
        # still isn't there after retry, we fall through to the slow path.
        if (_hint_source_cached and not _has_cached_source) or (_hint_transcript_cached and not _has_cached_transcript):
            print("[pipeline] hint/reality mismatch — volume reload + retry", flush=True)
            try:
                # Import lazily since it's only needed on the retry path
                from modal_app import prewarm_volume as _pv
                _pv.reload()
            except Exception as _rl_err:
                print(f"[pipeline] volume reload failed: {_rl_err}", flush=True)
            time.sleep(0.5)
            _has_cached_source = os.path.exists(_cached_source_path) and os.path.getsize(_cached_source_path) > 1024
            _has_cached_transcript = (
                not provided_transcript
                and os.path.exists(_cached_transcript_path)
                and os.path.getsize(_cached_transcript_path) > 2
            )
            if _has_cached_source or _has_cached_transcript:
                print("[metric] race_recovered kind=volume_reload job=" + job_id, flush=True)

        # ── Race + hit-rate telemetry (greppable `[metric]` lines) ──────
        _cache_key_str = _prewarm_cache_key(_dl_bucket, _dl_key)
        if _hint_source_cached and not _has_cached_source:
            print(f"[metric] cache_race_lost kind=source job={job_id} key={_cache_key_str}", flush=True)
        elif _has_cached_source:
            print(f"[metric] prewarm_hit kind=source job={job_id}", flush=True)
        elif mode in ("full", "reinterpret"):
            print(f"[metric] prewarm_miss kind=source job={job_id} hinted={_hint_source_cached}", flush=True)

        if _hint_transcript_cached and not _has_cached_transcript:
            print(f"[metric] cache_race_lost kind=transcript job={job_id} key={_cache_key_str}", flush=True)
        elif _has_cached_transcript:
            print(f"[metric] prewarm_hit kind=transcript job={job_id}", flush=True)
        elif not provided_transcript and mode in ("full", "reinterpret", "guided_redraft"):
            print(f"[metric] prewarm_miss kind=transcript job={job_id} hinted={_hint_transcript_cached}", flush=True)

        # Only emit the `download` token on a true cache miss — a cached copy
        # resolves in <100ms and would flash the UI label for no reason.
        if not _has_cached_source:
            send_progress(job_id, "download", 5, "Got your video, loading it in...", app_url)
            print("[pipeline] step=download + parallel kickoff", flush=True)
        else:
            print("[pipeline] prewarm cache hit — suppressing `download` SSE event", flush=True)

        # Presigned GET URL so Deepgram can fetch the source without AWS IAM.
        try:
            _deepgram_presigned = _aws_s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": _dl_bucket, "Key": _dl_key},
                ExpiresIn=300,
            )
        except Exception as _ps_err:
            print(f"[deepgram] presigned URL gen failed: {_ps_err} — will use local path after download", flush=True)
            _deepgram_presigned = None

        # If prewarm cached the transcript, load it and pass it down the
        # existing provided_transcript rail — skips all Deepgram work AND
        # suppresses the `transcribe` SSE event.
        if _has_cached_transcript:
            try:
                with open(_cached_transcript_path, "r") as _tf:
                    provided_transcript = json.load(_tf)
                print(f"[pipeline] prewarm transcript hit ({len(provided_transcript.get('words') or [])} words) — suppressing `transcribe` SSE event", flush=True)
            except Exception as _tr_err:
                print(f"[pipeline] failed to read cached transcript ({_tr_err}) — will re-transcribe", flush=True)

        _early_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        # URL-based Deepgram is disabled. Pointing Deepgram at the source URL
        # makes it transcribe the raw video's compressed audio at whatever
        # level it was recorded — talking-head sources are typically -27 dB
        # RMS, right at the model's confidence threshold for soft consonants.
        # File-based transcribe_audio() now extracts loudness-normalized
        # mono FLAC first, which gives Deepgram uniform-level audio and
        # measurably improves accuracy on quiet sources. The prep adds ~1s
        # but the FLAC payload is much smaller than the full video, so end
        # to end it's comparable to URL-based.
        future_url_transcript = None

        # Trend profile fetch — pure DB read, no file dependency. Skip in
        # render_only (uses snapshot) and when a snapshot was provided.
        _can_parallel_trend = mode in ("full", "reinterpret", "guided_redraft") and not provided_trend
        future_early_trend = None
        if _can_parallel_trend:
            future_early_trend = _early_pool.submit(get_trend_context)

        # Move source bytes into the job's work_dir — cache hit = ~100ms copy,
        # miss = real S3 download (still fast after boto3[crt] + same-region).
        if _has_cached_source:
            import shutil as _sh
            _sh.copy(_cached_source_path, source_path)
            _dl_method = "prewarm-cache"
            # If prewarm also pre-extracted source audio, copy it next to
            # source.mp4 in the same work_dir. build_per_cut_audio writes its
            # full-source wav to work_dir/source_audio_full.wav, so dropping
            # the cached wav at exactly that path makes the extraction step
            # in build_per_cut_audio see "already exists" and skip the ffmpeg
            # call (saves ~3-5s on the audio-pipeline critical path).
            _cached_audio_path = _prewarm_cached_audio_path(_dl_bucket, _dl_key)
            if os.path.exists(_cached_audio_path) and os.path.getsize(_cached_audio_path) > 1024:
                _audio_local = os.path.join(os.path.dirname(source_path), "source_audio_full.wav")
                try:
                    _sh.copy(_cached_audio_path, _audio_local)
                    print(
                        f"[pipeline] prewarm audio hit "
                        f"({os.path.getsize(_audio_local) // (1024 * 1024)}MB)",
                        flush=True,
                    )
                except Exception as _ae:
                    print(f"[pipeline] failed to copy cached audio: {_ae}", flush=True)
        else:
            # iOS uploads the source via background URLSession in parallel
            # with the client uploading the proxy (which gates the job
            # dispatch). When the user is on a slow network, the source
            # may still be mid-upload at the moment this handler runs.
            # Poll HEAD until the object materializes — same pattern as
            # prewarm_handler. Without this, the worker hits a 404 from
            # download_file the moment it races ahead of the upload.
            print(
                f"[pipeline] polling S3 for source: bucket={_dl_bucket!r} key={_dl_key!r}",
                flush=True,
            )
            # Two-stage polling with EARLY DETECTION of "upload never started":
            #
            # Stage 1 (0-30s): hot poll. The vast majority of healthy uploads
            # land in this window (small files lands instantly; medium files
            # finish multipart-complete within 30s).
            #
            # Stage 2 (30s): if file still not present, call ListMultipartUploads
            # to check whether iOS is actually uploading or whether it dispatched
            # the render before starting the upload (THE common failure mode).
            #   • Active multipart upload found for this key → iOS IS uploading;
            #     continue polling up to 300s for slow networks.
            #   • No active multipart upload AND no object → iOS never started.
            #     Fail fast with a clear error code so the iOS app can surface
            #     "upload failed, please retry" instead of users waiting 5
            #     minutes for a render that was doomed at dispatch time.
            #
            # This saves ~90% of the compute previously burned on doomed jobs
            # AND gives the frontend an actionable error code.
            _main_poll_start = time.time()
            # 30 min — match the iOS background URLSession resource
            # timeout. See identical reasoning at the prewarm-side
            # poll_deadline above.
            _main_poll_deadline = _main_poll_start + 1800
            _main_poll_attempt = 0
            _last_progress_log = _main_poll_start
            while True:
                _main_poll_attempt += 1
                try:
                    _aws_s3_client.head_object(Bucket=_dl_bucket, Key=_dl_key)
                    if _main_poll_attempt > 1:
                        print(
                            f"[pipeline] source available after "
                            f"{time.time() - _main_poll_start:.1f}s "
                            f"({_main_poll_attempt} polls)",
                            flush=True,
                        )
                    break
                except Exception as _head_err:
                    _now = time.time()
                    _elapsed = _now - _main_poll_start
                    _code = getattr(_head_err, 'response', {}).get('Error', {}).get('Code', 'unknown')

                    # ⚠️ The "Stage-2 early UPLOAD_NEVER_STARTED detection"
                    # that used to live here (raised at 60s if no in-
                    # progress multipart upload was visible) was removed
                    # — it was producing 100% false positives in
                    # production.
                    #
                    # Why it was wrong:
                    #   - iOS source uploads under ~30MB use SINGLE PUT
                    #     via URLSession.background, not multipart.
                    #   - Single PUTs never appear in
                    #     list_multipart_uploads. Not pre-flight, not
                    #     mid-flight, not ever.
                    #   - Real-world cellular uploads for a 50MB 1080p
                    #     clip legitimately take 60-180s.
                    #   - iOS build 160+ already dispatches createVideoJob
                    #     AFTER the PUT returns 200 (EditorView dispatch
                    #     loop gates on sourceUploadCompleted &&
                    #     proxyUploadFinished). The dispatch-before-upload
                    #     race the precheck assumed was the cause does
                    #     not exist in production code.
                    #
                    # The 300s main_poll_deadline below covers every case
                    # (slow upload, dead upload, network drop, etc.) with
                    # a single accurate error message. No upside left to
                    # the early check.

                    if _now >= _main_poll_deadline:
                        raise RuntimeError(
                            f"UPLOAD_STALLED: Source video did not arrive on S3 within 300s "
                            f"(bucket={_dl_bucket!r} key={_dl_key!r} last HEAD error={_code}). "
                            f"A multipart upload was in progress but never completed. "
                            f"Likely cause: iOS upload was cancelled, the network dropped, "
                            f"or an auth token expired mid-upload. iOS should detect "
                            f"upload failures and either retry or surface the error."
                        )
                    if _now - _last_progress_log >= 30:
                        print(
                            f"[pipeline] still waiting on S3 source after "
                            f"{_elapsed:.0f}s (last HEAD={_code}, "
                            f"attempt #{_main_poll_attempt})",
                            flush=True,
                        )
                        _last_progress_log = _now
                    _wait = 1.0 if _elapsed < 10 else (2.0 if _elapsed < 60 else 4.0)
                    time.sleep(_wait)
            _aws_s3_client.download_file(_dl_bucket, _dl_key, source_path, Config=_S3_TRANSFER_CONFIG)
            _dl_method = "s3-crt"
        size_mb = os.path.getsize(source_path) / (1024*1024)
        _timings["download"] = time.time() - t
        _throughput_mbs = size_mb / max(_timings["download"], 0.001)
        print(f"[pipeline] download complete: {size_mb:.1f}MB in {_timings['download']:.1f}s ({_dl_method}, {_throughput_mbs:.1f} MB/s)", flush=True)

        # Don't shut down _early_pool yet — the futures may still be running
        # and we want them alongside the mega-parallel phase. Let Python GC
        # after we collect the results downstream.

        # ── Re-edit plan-diff (tweak mode) ───────────────────────────────
        # For tweak mode, ask Gemini to produce a modified plan that preserves
        # everything except the explicit change. Runs here (before mega-parallel)
        # so the classification can downgrade to render_only / reinterpret before
        # we decide which pipeline stages to spawn. needs_clarification short-
        # circuits the job — the server surfaces the question to the user.
        change_summary = None
        if mode == "tweak":
            send_progress(job_id, "plan_diff", 10, "Figuring out exactly what to change...", app_url)
            diff = generate_plan_diff(
                old_plan=provided_plan,
                change_request=change_request,
                old_vibe=old_vibe or vibe,
                transcript=provided_transcript,
            )

            classification = diff.get("classification")
            if classification == "needs_clarification":
                send_progress(job_id, "needs_clarification", 100, "Need a bit more info...", app_url)
                return {
                    "status": "needs_clarification",
                    "job_id": job_id,
                    "clarification_question": diff.get("clarification_question") or "Can you describe the change in more detail?",
                }
            elif classification == "tweak" and isinstance(diff.get("new_plan"), dict):
                provided_plan = diff["new_plan"]
                change_summary = diff.get("human_summary")
                mode = "render_only"
                print(f"[plan-diff] Tweak accepted — rendering with new plan. Summary: {change_summary}", flush=True)
                # ── Layer 3 safety net: diff the tweak's new_plan against the
                # original prior plan + scope-classify each change. In
                # tweak mode the contract is byte-identical-echo, so any
                # out-of-scope drift is a contract violation. Phase 1 auto-
                # reverts top-level SCALAR drift (caption_style /
                # thumbnail_word_index / outro). Array-level drift is
                # logged for production-data tuning before Phase 2 enables
                # array reverts. Fail-OPEN end-to-end — validator
                # infrastructure trouble never blocks a render.
                try:
                    _ORIG_PRIOR = input_data.get("edit_plan")
                    if isinstance(_ORIG_PRIOR, dict):
                        _validation = validate_reedit_changes(
                            prior_plan=_ORIG_PRIOR,
                            new_plan=provided_plan,
                            change_request=change_request,
                            mode="tweak",
                        )
                        print(
                            f"[reedit-validate] tweak verdict={_validation.get('verdict')} "
                            f"diffs={len(_validation.get('diffs') or [])} "
                            f"out_of_scope={len(_validation.get('out_of_scope_paths') or [])}",
                            flush=True,
                        )
                        provided_plan = apply_scalar_reverts(
                            prior_plan=_ORIG_PRIOR,
                            new_plan=provided_plan,
                            validation=_validation,
                            mode="tweak",
                        )
                except Exception as _val_err:
                    print(f"[reedit-validate] safety net error (fail open): {_val_err}", flush=True)
            elif classification == "guided_redraft":
                # Layer 2: full pipeline with the PRIOR PLAN injected into
                # generate_edit_gemini as soft default + the user's directional
                # change_request as override. provided_plan stays populated for
                # the call site to pick up (see generate_edit_gemini's prior_plan
                # parameter wiring). change_request also stays populated.
                vibe = diff.get("fused_vibe") or f"{old_vibe or vibe} — {change_request}".strip(" —")
                change_summary = diff.get("human_summary")
                mode = "guided_redraft"
                print(
                    f"[plan-diff] Guided redraft — prior plan kept as soft default; "
                    f"direction: {change_request[:160]}",
                    flush=True,
                )
            else:
                # reinterpret or fallback — fuse vibe and run full pipeline from source
                # with NO prior-plan carry-over. Explicit total-recast path.
                vibe = diff.get("fused_vibe") or f"{old_vibe or vibe} — {change_request}".strip(" —")
                change_summary = diff.get("human_summary")
                mode = "reinterpret"
                # Drop the provided_plan so generate_edit_gemini doesn't
                # accidentally pick it up via the guided-redraft branch.
                provided_plan = None
                print(f"[plan-diff] Reinterpret — fused vibe: {vibe[:200]}", flush=True)

        # Merge any provided resolved_broll entries back into provided_plan.broll_clips
        # so the render can re-use exact Pexels assets. Keyed by index order.
        if mode == "render_only" and isinstance(provided_plan, dict) and isinstance(provided_broll, list):
            _plan_broll = provided_plan.get("broll_clips")
            if isinstance(_plan_broll, list):
                for _i, _resolved in enumerate(provided_broll):
                    if _i >= len(_plan_broll):
                        break
                    if not isinstance(_plan_broll[_i], dict) or not isinstance(_resolved, dict):
                        continue
                    for _pk in ("pexels_video_id", "pexels_file_url", "width", "height", "duration", "clip_in", "clip_out"):
                        if _pk in _resolved and _pk not in _plan_broll[_i]:
                            _plan_broll[_i][_pk] = _resolved[_pk]

        # Step 2 — ALL initialization in ONE mega-parallel phase
        # Normalize, transcribe, Gemini upload, loudness, beats, edit recipe, face detect
        # all run concurrently. Edit recipe starts as soon as transcript + upload finish
        # (doesn't wait for normalize). Face detect starts when normalize finishes.
        # Pre-parallel phase marker; individual stages inside the pool fire their own
        # fine-grained tokens so the UI can narrate the work in real time.
        send_progress(job_id, "analyze", 7, "Preparing your footage", app_url)
        t = time.time()
        print("[pipeline] step=mega-parallel (normalize + transcribe + upload + edit + faces)", flush=True)

        # Quick probe of raw source for duration (needed for face detect timestamps)
        # Uses cached probe — same data reused by analyze_source_video, probe_resolution, etc.
        source_duration = probe_duration(source_path) or 0
        sample_timestamps = [round(i * 4.0, 3) for i in range(int(source_duration / 4.0) + 1)] if source_duration > 0 else []

        # Initialize Gemini client early so we can pre-upload
        _get_genai_client()  # ensures client is ready for upload + generate

        # All 5 operations run in parallel — Deepgram, Gemini upload, loudness,
        # and beats all read from the RAW source (audio is identical pre/post normalize).
        # Unix file semantics keep the raw file accessible even after normalize unlinks it.
        _raw_source = source_path  # raw path — analyze_source_video reads but doesn't modify

        # ─── FAST-FAIL TALKING-HEAD CHECK ─────────────────────────────
        # Runs immediately after source download and BEFORE the parallel
        # pipeline kicks off. Catches non-talking-head uploads in ~2-3s
        # post-download instead of waiting 30-60s for the full-pipeline
        # face tracker to complete.
        #
        # Strategy: sample 8 frames from the raw source via OpenCV (no
        # ffmpeg subprocess overhead), run DNN face detection on each.
        # If face_ratio < 25% AND we had enough samples to be confident,
        # fail fast. Otherwise proceed to the full pipeline; the second-
        # tier gate inside _do_edit_recipe_overlapped catches anything
        # borderline.
        #
        # This is in addition to (not instead of) the /validate endpoint
        # iOS should call before the full upload. Three layers of defense:
        #   1. iOS on-device check (sub-second, in Vision framework)
        #   2. /validate endpoint (3-7s, called before full upload)
        #   3. THIS check (2-3s post-download, safety net)
        #   4. Full-pipeline gate inside _do_edit_recipe_overlapped
        #      (slower but most thorough)
        #
        # The render_only and tweak paths skip this — they're replaying
        # a previously-validated render.
        # NB: `_skip_edit_gen` is defined further down (line ~15272). At
        # THIS point in the function we check `mode` directly, which IS
        # in scope (defined at ~line 14190).
        if mode != "render_only":
            try:
                _qfc_t0 = time.time()
                _qfc_ratio, _qfc_samples = _quick_face_check(_raw_source, max_samples=8)
                print(
                    f"[talking-head-fastcheck] face_ratio={_qfc_ratio:.2f} "
                    f"({_qfc_samples} samples) in {time.time() - _qfc_t0:.1f}s",
                    flush=True,
                )
                # Only reject if we had enough samples AND the ratio is
                # clearly below threshold. Borderline cases proceed and
                # are caught by the more thorough downstream gate.
                if _qfc_samples >= 5 and _qfc_ratio < 0.25:
                    raise RuntimeError(
                        f"NOT_TALKING_HEAD: face in only {_qfc_ratio*100:.0f}% "
                        f"of {_qfc_samples} sampled frames (fast-check). "
                        f"This app edits talking-head videos."
                    )
            except RuntimeError:
                # Re-raise NOT_TALKING_HEAD — caller handles it as a
                # user-facing validation error.
                raise
            except Exception as _qfc_err:
                # Fast-check error (model file missing, opencv issue, etc) —
                # don't block the user; the slower full-pipeline gate will
                # catch any genuine non-talking-head video.
                print(
                    f"[talking-head-fastcheck] non-fatal error: {_qfc_err} — "
                    f"deferring to full-pipeline gate",
                    flush=True,
                )

        def _do_normalize():
            return analyze_source_video(_raw_source)

        def _do_transcribe():
            send_progress(job_id, "transcribe", 10, "Transcribing every word", app_url)
            audio_path = os.path.join(work_dir, "audio_for_words.ogg")
            _audio_ext = subprocess.run(
                ["ffmpeg", "-threads", "0", "-y", "-i", _raw_source,
                 "-vn", "-c:a", "libopus", "-b:a", "32k", "-ar", "16000", "-ac", "1", audio_path],
                capture_output=True, text=True, timeout=30,
            )
            if _audio_ext.returncode != 0:
                raise RuntimeError(f"FFmpeg audio extraction failed: {(_audio_ext.stderr or '')[-300:]}")
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 100:
                raise RuntimeError(f"FFmpeg produced empty/missing audio file: {audio_path}")
            # Boost proper-noun recognition with names extracted from the
            # user's vibe text. "Interview with Ryan" → keywords=["Ryan:5"].
            # Catches the "Ryan → right" class of Deepgram mistranscriptions.
            _kw = _extract_proper_noun_keywords(vibe)
            result = transcribe_audio(audio_path, keywords=_kw or None)
            if os.path.exists(audio_path):
                os.remove(audio_path)
            return result

        def _do_gemini_proxy():
            """Provide low-res video bytes for inline Gemini API call.

            Three paths, in priority order:
              1. Client provided `proxy_video_url` — download the small
                 pre-uploaded proxy from S3/CloudFront (~3-6 MB, lands
                 in under a second). Skips the on-server encode entirely.
              2. Prewarm cache hit — proxy was encoded during the iOS
                 upload window and sits in the Modal volume. Reading
                 from local disk is ~10-100ms vs. a fresh re-encode.
              3. No client proxy AND no prewarm cache — encode 480p@16fps
                 proxy ourselves from the high-res source (~7-10s on
                 the orchestrator).
            """
            _proxy_t = time.time()
            if proxy_video_url:
                try:
                    _resp = requests.get(proxy_video_url, timeout=30)
                    _resp.raise_for_status()
                    _proxy_bytes = _resp.content
                    _proxy_mb = len(_proxy_bytes) / (1024 * 1024)
                    print(
                        f"[pipeline] Gemini proxy: client-uploaded {_proxy_mb:.1f}MB "
                        f"downloaded in {time.time()-_proxy_t:.1f}s (no on-server encode)",
                        flush=True,
                    )
                    return _proxy_bytes
                except Exception as _client_proxy_err:
                    # Surface but fall through to prewarm cache / on-server encode.
                    print(f"[pipeline] Client proxy download failed ({_client_proxy_err}) — checking prewarm cache", flush=True)

            # Prewarm cache check — the proxy was encoded during the iOS
            # upload window (~7-10s of work done at upload time instead of
            # render time, fully hidden behind upload latency).
            try:
                _prewarm_proxy = _prewarm_cached_proxy_path(_dl_bucket, _dl_key)
                if os.path.exists(_prewarm_proxy) and os.path.getsize(_prewarm_proxy) > 1024:
                    with open(_prewarm_proxy, "rb") as f:
                        _proxy_bytes = f.read()
                    _proxy_mb = len(_proxy_bytes) / (1024 * 1024)
                    print(
                        f"[pipeline] Gemini proxy: prewarm-cache hit {_proxy_mb:.1f}MB "
                        f"in {time.time()-_proxy_t:.1f}s (no on-server encode)",
                        flush=True,
                    )
                    return _proxy_bytes
            except (NameError, AttributeError):
                # _dl_bucket / _dl_key not in scope on this path — fall through
                pass
            except Exception as _pc_err:
                print(f"[pipeline] prewarm proxy read failed ({_pc_err}) — falling back to on-server encode", flush=True)

            try:
                _proxy_path = os.path.join(work_dir, "gemini_proxy.mp4")
                # 480p @ 18fps proxy. Paired with video_metadata.fps=18 on
                # the Gemini Part so Gemini SAMPLES at 18fps — without that
                # metadata the SDK defaults to ~1fps and bumping the encoder
                # is performative. 24 is the API's hard cap (validated
                # 2026-06-13: fps>24 returns INVALID_ARGUMENT). At 18fps the
                # model sees micro-expression transitions (the half-beat
                # face shift before a line lands), gesture velocity (where
                # the hand actually moves vs. settles), and eye-direction
                # changes between blinks — the editorial signal that lives
                # between frames at 10fps. Trade-off: more video tokens per
                # call than 16fps, accepted because arc-aware placement
                # quality is the bottleneck, not API latency — and the
                # primary 504 driver (X-Server-Timeout=120s) is now fixed
                # at the client level (see _get_genai_client).
                _proxy_venc = (["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "32"]
                               if _HAS_NVENC else
                               ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30"])
                _hw_dec = ["-hwaccel", "cuda"] if _HAS_HWACCEL else []
                # Audio: Opus mono @ 64kbps. Opus at 64k beats AAC at 96k for
                # speech intelligibility AND prosodic detail (voice rise/drop,
                # micro-pauses, laugh/gasp texture) — the acoustic signal the
                # prompt explicitly tells Gemini to listen for. The previous
                # AAC @ 48kbps smeared that texture. Modern ffmpeg writes
                # Opus into MP4 natively; Gemini's MP4 ingestion accepts it.
                _proxy_cmd = subprocess.run(
                    ["ffmpeg", "-y", "-threads", "0"] + _hw_dec + ["-i", _raw_source,
                     "-vf", "scale=480:-2,fps=18"] + _proxy_venc + [
                     "-c:a", "libopus", "-b:a", "64k", "-ac", "1",
                     _proxy_path],
                    capture_output=True, text=True, timeout=30,
                )
                if _proxy_cmd.returncode != 0 or not os.path.exists(_proxy_path):
                    raise RuntimeError(f"Gemini proxy encode failed: {(_proxy_cmd.stderr or '')[-300:]}")
                with open(_proxy_path, "rb") as f:
                    _proxy_bytes = f.read()
                _proxy_mb = len(_proxy_bytes) / (1024 * 1024)
                print(f"[pipeline] Gemini proxy: 480p@16fps {_proxy_mb:.1f}MB in {time.time()-_proxy_t:.1f}s (on-server encode, no client proxy)", flush=True)
                return _proxy_bytes
            except Exception as e:
                raise RuntimeError(f"Gemini proxy encode failed: {e}") from e

        def _do_loudness():
            return measure_source_loudness(_raw_source)

        # Side-channel for scdet confidence scores (filled in the pool thread;
        # consumed by the scene-change floor's confidence gate). Kept OFF the
        # future's return value so both future_shot_changes.result() consumers
        # stay unchanged — return shape is still a plain list of times.
        _shot_change_scores = {}
        def _do_shot_changes():
            send_progress(job_id, "shots", 18, "Detecting shot changes", app_url)
            return detect_shot_changes(_raw_source, out_scores=_shot_change_scores)

        def _do_vocal_emphasis():
            return detect_vocal_emphasis(_raw_source)

        def _do_fps_normalize():
            """Canonicalize source to 1080×1920 yuv420p CFR at SOURCE fps.

            Production-pipeline pattern: NEVER re-encode the source if we
            don't have to. Most modern phone uploads (iPhone 12+, Pixel 6+,
            Galaxy S20+) are already 1080×1920 yuv420p CFR — we passthrough
            those by symlinking the raw file. For sources that genuinely
            need format conversion (VFR phones, old/cheap Androids, wrong
            aspect ratios), we re-encode at libx264 medium so the one
            re-encode we DO pay produces a clean intermediate.

            Passthrough is what CapCut, Premiere, Final Cut, DaVinci all
            do. Each H.264 generation introduces irreversible quality loss
            (compression noise, color drift, blocking); the only way to
            avoid the loss is to skip the encode. For ~90% of uploads that
            means the entire pipeline runs at 1 H.264 generation total
            (the final composite) — strictly fewer than CapCut's pattern.

            The shake probe runs unconditionally (cheap, ~1-2s). If the
            source needs deshake we're forced to re-encode anyway, so the
            passthrough check defers to the deshake decision.

            Awaits future_normalize so it can read the analyze-derived
            normalize_vf (which says whether the source needs scale/crop).

            Output: source_canonical.mp4 (1080x1920 source-fps yuv420p,
            either passthrough symlink or libx264 medium crf 18 with
            ~1-keyframe-per-second GOP for fast Remotion seeks).
            """
            _shape = future_normalize.result()
            _normalize_vf = _shape.get("normalize_vf")

            _cached = _probe_full(_raw_source)
            _vs = next((s for s in (_cached.get("streams") or []) if s.get("codec_type") == "video"), {})
            _r_rate_str = _vs.get("r_frame_rate", "")
            _avg_rate_str = _vs.get("avg_frame_rate", "")
            _src_pix_fmt = _vs.get("pix_fmt") or ""
            _src_w = int(_vs.get("width") or 0)
            _src_h = int(_vs.get("height") or 0)
            _src_codec = _vs.get("codec_name") or ""

            # HDR detection — required for iPhone-recorded Dolby Vision Profile
            # 8.4 sources. iPhone 12+ records video as HEVC 10-bit with
            # color_primaries=bt2020 and color_transfer=arib-std-b67 (HLG,
            # cross-compatible with HDR display). When this is played on an
            # SDR display without tone-mapping, the HDR-encoded YUV samples
            # get decoded with SDR gamma → bright/washed-out + magenta cast.
            # Canonical fix per multiple ffmpeg sources: zscale HLG→linear
            # with npl=400 (HLG mastering peak is 400 nits, not 100 or 1000),
            # tonemap=reinhard, zscale back to BT.709 tv-range. PQ sources
            # (smpte2084) handled by the same chain — npl=400 still safe; PQ
            # is rare for iPhone but the chain works either way.
            _src_color_transfer = (_vs.get("color_transfer") or "").lower()
            _src_color_primaries = (_vs.get("color_primaries") or "").lower()
            _is_hdr = (
                _src_color_transfer in ("smpte2084", "arib-std-b67")
                or _src_color_primaries in ("bt2020",)
            )
            if _is_hdr:
                print(
                    f"[fps-normalize] HDR source detected "
                    f"(primaries={_src_color_primaries or 'unset'}, "
                    f"transfer={_src_color_transfer or 'unset'}) "
                    f"— will tone-map HLG→BT.709 SDR via zscale + reinhard",
                    flush=True,
                )

            def _parse_rate(s):
                if not s or s == "0/0":
                    return 0.0
                if "/" in s:
                    _n, _d = s.split("/")
                    _d = float(_d)
                    return float(_n) / _d if _d > 0 else 0.0
                return float(s)

            _avg = _parse_rate(_avg_rate_str)
            _r_val = _parse_rate(_r_rate_str)

            _norm_t0 = time.time()
            _norm_path = os.path.join(work_dir, "source_canonical.mp4")

            # Cheap probe: ~12 frames @ 240p Lucas-Kanade flow, 1-2s. Decides
            # whether to run the vidstab two-pass during re-encode.
            #
            # Threshold = 0.35 (lowered from 0.6). Handheld phone footage with
            # mild-to-moderate shake routinely scores 0.4-0.8 on this probe.
            # The previous 0.6 ceiling left a lot of visibly-shaky uploads
            # un-stabilized; 0.35 catches anything beyond pin-stable. Rock-
            # stable tripod/stabilizer footage scores below 0.2 and skips
            # the cost.
            _shake_t0 = time.time()
            _shake_score = _probe_shake_intensity(_raw_source)
            _SHAKE_STABILIZE_THRESHOLD = 0.35
            _needs_deshake = _shake_score >= _SHAKE_STABILIZE_THRESHOLD
            print(
                f"[fps-normalize] shake probe: score={_shake_score:.2f} "
                f"({'stabilize (vidstab)' if _needs_deshake else 'skip'}) "
                f"in {time.time() - _shake_t0:.1f}s",
                flush=True,
            )

            # Target 60fps output. iPhone 30fps source frame-doubles into
            # 60fps source_canonical via ffmpeg's fps filter — each source
            # frame appears twice, so the speaker's MOTION stays at native
            # 30fps cadence (no interpolation, no judder, identical visual
            # for the talking head). What gains smoothness at 60fps is the
            # OVERLAY layer: caption animations, transition curves, zoom
            # interpolation advance one frame every 16.7ms instead of 33ms.
            # Remotion compositions and the final composite both inherit
            # this 60fps rate from source_canonical, so the entire render-
            # time pipeline shares one fps and frame-index math stays
            # consistent. Platforms (TikTok / Reels) re-encode to ~30 on
            # upload, but the smoothness is visible in direct playback,
            # the in-app preview, and on YouTube (which preserves 60).
            _target_fps = 60.0
            _gop_frames = max(1, int(round(_target_fps)))

            # Passthrough check: if the source is already canonical (right
            # dimensions, yuv420p, h264, sane CFR AT TARGET RATE) AND no
            # deshake needed AND no scale/crop normalize_vf required,
            # symlink the raw source instead of re-encoding. Pure quality
            # preservation. The rate match against _target_fps (not just
            # against itself) is what makes a 60fps source fall to the
            # re-encode path while a 30fps source stays on passthrough.
            _is_canonical = (
                _src_w == 1080
                and _src_h == 1920
                and _src_pix_fmt in ("yuv420p", "yuvj420p")
                and _src_codec == "h264"
                and not _normalize_vf
                and not _needs_deshake
                and not _is_hdr  # HDR always needs the tone-map re-encode
                # CFR sanity: avg and r_rate should agree within ~2%, and
                # source rate must be close to target (within ~2%) so that
                # passthrough doesn't accidentally ship a 60fps file when
                # we want 30fps output.
                and _avg > 0 and _r_val > 0
                and abs(_avg - _r_val) / max(_r_val, 1e-6) < 0.02
                and abs(_r_val - _target_fps) / _target_fps < 0.02
                and 10 <= _r_val <= 120
            )
            if _is_canonical:
                # Symlink (no copy, no re-encode). Downstream tools read
                # the symlink transparently. Source pixels reach the final
                # composite encode bit-perfect.
                try:
                    if os.path.lexists(_norm_path):
                        os.unlink(_norm_path)
                    os.symlink(os.path.abspath(_raw_source), _norm_path)
                except OSError:
                    # Filesystem doesn't support symlinks — fall back to
                    # hard link, then copy. Same end result.
                    try:
                        os.link(os.path.abspath(_raw_source), _norm_path)
                    except OSError:
                        shutil.copy2(_raw_source, _norm_path)
                _size_mb = os.path.getsize(_norm_path) / (1024 * 1024)
                print(
                    f"[fps-normalize] r={_r_val:.4f}fps avg={_avg:.4f}fps "
                    f"-> passthrough (already canonical: {_src_w}x{_src_h} "
                    f"{_src_pix_fmt} {_src_codec} CFR) in "
                    f"{time.time() - _norm_t0:.1f}s ({_size_mb:.1f}MB)",
                    flush=True,
                )
                # Skip the keyframe verification block — we don't control
                # the source's GOP structure on the passthrough path. If
                # iPhone uploads have 2-3s GOPs, Remotion seeks will be
                # slightly slower (decode-from-prev-keyframe), but quality
                # preservation matters more than seek speed.
                return _norm_path

            # Re-encode path: source needs format conversion (VFR, wrong
            # shape, deshake, HDR tone-map) — preset is `medium` so the one
            # re-encode we pay produces a clean intermediate, not blocky
            # `ultrafast`.
            _vf_parts = []
            if _is_hdr:
                # HLG (or PQ) → BT.709 SDR tone-map. Canonical recipe per
                # multiple ffmpeg sources (BinaryTides, ConvertIntoMP4,
                # FFmpeg-user mailing list):
                #   1. zscale t=linear:npl=400  — HLG to linear-light. npl=400
                #      is the HLG mastering peak (Apple ProRes HLG ≈ 400 nits);
                #      npl=100 over-compresses and crushes mid-tones; npl=1000
                #      is the HDR10/PQ peak and under-compresses for HLG.
                #   2. format=gbrpf32le         — high-precision intermediate
                #      so the matrix conversion + tone-map don't lose
                #      sub-pixel detail.
                #   3. zscale p=bt709           — primaries BT.2020 → BT.709.
                #   4. tonemap=reinhard         — perceptually natural curve
                #      preferred for HLG specifically (hable crushes mid-
                #      tones to gray on HLG content; mobius is a near no-op
                #      on in-range values; reinhard's gentle compression
                #      preserves contrast on faces and warm tones).
                #   5. zscale t=bt709:m=bt709:r=tv — re-encode SDR BT.709
                #      tv-range so downstream stages see standard SDR.
                _vf_parts.append(
                    "zscale=t=linear:npl=400,format=gbrpf32le,"
                    "zscale=p=bt709,tonemap=reinhard,"
                    "zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
                )
            if _needs_deshake:
                # vidstab two-pass auto-stabilization with CONTENT-ADAPTIVE
                # parameters scaled by the measured shake intensity. The
                # library (libvidstab) underpins DaVinci Resolve and Final
                # Cut's Smooth Motion features. Pass 1 (vidstabdetect)
                # analyzes per-frame motion and writes a .trf transform
                # file; pass 2 (vidstabtransform, inside the main encode
                # below) reads the .trf and applies inverse-motion warping.
                #
                # CONTENT-ADAPTIVE PARAMETERS
                # ---------------------------
                # Fixed parameters work fine on the "average" video and feel
                # wrong on the edges:
                #   - On mild shake, smoothing=20 erases natural movement
                #     and the result reads "floaty"
                #   - On heavy shake, smoothing=20 isn't aggressive enough
                #     and residual shake leaks through; zoom=2 leaves
                #     visible black edges from the warp residual
                # Scaling the parameters with the probe's shake_score makes
                # treatment match the input — mild footage gets light touch,
                # heavy footage gets aggressive smoothing + bigger zoom.
                # This is how pro tools handle the variance across content
                # types (handheld selfie ≠ walking vlog ≠ extreme action).
                #
                # Tiers, calibrated against the Lucas-Kanade 240p probe.
                # NOTE: `zoom=0` across all tiers — we explicitly do NOT
                # crop into the frame to hide stabilization warp residual.
                # Previous tiers set zoom=1..6 which read as a permanent
                # zoom-in across the entire video (user feedback: "the
                # whole video looks zoomed way in"). Tradeoff: without
                # the crop, the stabilization warp can leave small visible
                # edges on heavy/extreme shake — we accept that to keep
                # the full natural framing the user shot.
                #
                # To compensate for the lost border-hiding, smoothing is
                # also reduced on heavy/extreme tiers — less aggressive
                # warping → smaller residual edges → less visible artifact.
                #
                # crop=keep paints the residual edges with the unstabilized
                # original pixels rather than black bars — way less visible
                # than black, and the small motion at the edges reads as
                # natural rather than as a stabilization artifact.
                #
                # Tiers:
                #   • 0.35-0.50  MILD       → light cleanup, near-zero artifact
                #       shakiness=4, smoothing=10, zoom=0
                #   • 0.50-1.00  MODERATE   → standard handheld treatment
                #       shakiness=6, smoothing=15, zoom=0
                #   • 1.00-2.00  HEAVY      → strong but less aggressive smoothing
                #       shakiness=8, smoothing=20, zoom=0
                #   • 2.00+      EXTREME    → max stabilization, still no zoom
                #       shakiness=10, smoothing=25, zoom=0
                #
                # accuracy=15 (max) for all tiers — feature-tracking quality
                # benefits everyone; the ~30% cost over default 9 is worth
                # it for the small absolute time difference (~3-5s).
                if _shake_score < 0.5:
                    _vs_tier = "mild"
                    _vs_shakiness, _vs_smoothing, _vs_zoom = 4, 10, 0
                elif _shake_score < 1.0:
                    _vs_tier = "moderate"
                    _vs_shakiness, _vs_smoothing, _vs_zoom = 6, 15, 0
                elif _shake_score < 2.0:
                    _vs_tier = "heavy"
                    _vs_shakiness, _vs_smoothing, _vs_zoom = 8, 20, 0
                else:
                    _vs_tier = "extreme"
                    _vs_shakiness, _vs_smoothing, _vs_zoom = 10, 25, 0
                _stab_trf = os.path.join(work_dir, "vidstab.trf")
                _stab_t0 = time.time()
                _stab_det = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-threads", "0",
                     "-i", _raw_source,
                     "-vf", f"vidstabdetect=shakiness={_vs_shakiness}:accuracy=15:result={_stab_trf}",
                     "-f", "null", "-"],
                    capture_output=True, text=True, timeout=300,
                )
                if _stab_det.returncode != 0 or not os.path.exists(_stab_trf):
                    raise RuntimeError(
                        f"vidstabdetect failed: {(_stab_det.stderr or '')[-500:]}"
                    )
                print(
                    f"[fps-normalize] vidstab tier={_vs_tier} "
                    f"(shakiness={_vs_shakiness}, smoothing={_vs_smoothing}, "
                    f"zoom={_vs_zoom}) — detect pass {time.time() - _stab_t0:.1f}s",
                    flush=True,
                )
                _vf_parts.append(
                    f"vidstabtransform=input={_stab_trf}"
                    f":smoothing={_vs_smoothing}:zoom={_vs_zoom}"
                    # crop=keep (NOT black) since zoom=0 — black bars at edges
                    # whenever the warp pushes pixels off-canvas would be very
                    # visible. With keep, the residual edges show the
                    # unstabilized original pixels (minor edge motion) which
                    # reads as natural rather than as a stabilization artifact.
                    f":crop=keep:interpol=bicubic"
                )
            _vf_parts.append(f"fps={_target_fps:.6f}")
            if _normalize_vf:
                _vf_parts.append(_normalize_vf)
            _vf_combined = ",".join(_vf_parts)

            _r_out = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-threads", "0",
                 "-i", _raw_source,
                 "-vf", _vf_combined,
                 # CRF 15 (was 18) — this is the INTERMEDIATE that feeds every
                 # downstream step (per-cut renders, composite, HLS). Bumping
                 # 18→15 here costs ~30% more disk for the intermediate but
                 # means downstream encodes have CLEANER source pixels to
                 # work with, so the final output retains more detail.
                 # iPhone HEVC sources transcoded to H.264 lose some quality
                 # at the codec switch; CRF 15 minimizes that loss.
                 "-c:v", "libx264", "-preset", "medium", "-crf", "15",
                 "-pix_fmt", "yuv420p",
                 # Tag output as BT.709 SDR tv-range explicitly. After the
                 # zscale tone-map above, the YUV samples are correct SDR
                 # values; this just makes sure the container tag matches
                 # what's actually inside, so iOS/Chrome decoders don't
                 # try to apply HDR processing to already-SDR data. On
                 # non-HDR sources these flags are no-ops vs default
                 # behavior (HD content defaults to BT.709 anyway).
                 "-color_primaries", "bt709",
                 "-color_trc", "bt709",
                 "-colorspace", "bt709",
                 "-color_range", "tv",
                 "-g", str(_gop_frames), "-keyint_min", str(_gop_frames),
                 "-sc_threshold", "0",
                 "-c:a", "copy",
                 "-video_track_timescale", "90000",
                 # +negative_cts_offsets — write B-frame reorder priming via
                 # negative composition time offsets instead of via an MP4
                 # edit list. Without this flag, libx264 + MP4 muxer writes
                 # `edts/elst` that "skips first 33ms of priming." FFmpeg's
                 # filtergraph respects the edit list when reading the file
                 # back (frame index N becomes raw frame N+2). Remotion's
                 # OffthreadVideo does not apply the edit list the same
                 # way. The two renderers then extract DIFFERENT source
                 # content at the same intended source_time, producing
                 # variable per-clip video drift between FFmpeg-rendered
                 # and Remotion-rendered clips. With negative_cts_offsets,
                 # no edit list is written; both renderers see frame N as
                 # raw frame N consistently.
                 "-movflags", "+negative_cts_offsets",
                 _norm_path],
                capture_output=True, text=True, timeout=240,
            )
            if _r_out.returncode != 0 or not os.path.exists(_norm_path):
                raise RuntimeError(
                    f"Source canonicalize failed: "
                    f"{(_r_out.stderr or '')[-500:]}"
                )

            # ── DIAG PROBE 1: source vs canonical structural comparison ──
            # Temporary diagnostic to trace the perceived video-vs-audio
            # drift. Compares the raw source's stream metadata to the
            # canonicalized output's metadata. Any duration/frame-count
            # delta beyond rounding tolerance indicates the fps-normalize
            # step is producing canonical content that doesn't align with
            # the source's wall-clock content — which would cause every
            # downstream frame-index trim to read from a wrong-time
            # position.
            try:
                def _probe_streams(path):
                    out = {"duration": None, "v_frames": None, "v_start": None,
                           "a_start": None, "v_r": None, "v_avg": None}
                    pr = subprocess.run(
                        ["ffprobe", "-v", "error",
                         "-show_entries",
                         "format=duration:stream=index,codec_type,start_time,nb_frames,r_frame_rate,avg_frame_rate",
                         "-of", "default=nw=1", path],
                        capture_output=True, text=True, timeout=20,
                    )
                    _cur_type = None
                    for ln in (pr.stdout or "").splitlines():
                        if "=" not in ln: continue
                        k, _, v = ln.partition("=")
                        if k == "duration" and out["duration"] is None:
                            try: out["duration"] = float(v)
                            except ValueError: pass
                        elif k == "codec_type":
                            _cur_type = v.strip()
                        elif _cur_type == "video":
                            if k == "nb_frames":
                                try: out["v_frames"] = int(v)
                                except ValueError: pass
                            elif k == "start_time":
                                try: out["v_start"] = float(v)
                                except ValueError: pass
                            elif k == "r_frame_rate" and "/" in v:
                                n, d = v.split("/")
                                try: out["v_r"] = float(n)/float(d) if float(d) else 0.0
                                except (ValueError, ZeroDivisionError): pass
                            elif k == "avg_frame_rate" and "/" in v:
                                n, d = v.split("/")
                                try: out["v_avg"] = float(n)/float(d) if float(d) else 0.0
                                except (ValueError, ZeroDivisionError): pass
                        elif _cur_type == "audio" and k == "start_time":
                            try: out["a_start"] = float(v)
                            except ValueError: pass
                    return out

                _src_p = _probe_streams(_raw_source)
                _can_p = _probe_streams(_norm_path)
                _dur_delta = ((_can_p["duration"] or 0) - (_src_p["duration"] or 0))
                _expected_canon_frames = int(round((_can_p["duration"] or 0) * _target_fps))
                _frames_delta = (_can_p["v_frames"] or 0) - _expected_canon_frames

                def _fmt(v, kind="float"):
                    if v is None: return "?"
                    if kind == "ms": return f"{v*1000:+.1f}ms"
                    if kind == "fps": return f"{v:.2f}fps"
                    return f"{v}"

                print(
                    f"[fps-probe] source: dur={_fmt(_src_p['duration'])}s "
                    f"v_frames={_src_p['v_frames']} r={_fmt(_src_p['v_r'], 'fps')} "
                    f"avg={_fmt(_src_p['v_avg'], 'fps')} "
                    f"v_start={_fmt(_src_p['v_start'], 'ms')} "
                    f"a_start={_fmt(_src_p['a_start'], 'ms')}",
                    flush=True,
                )
                print(
                    f"[fps-probe] canonical: dur={_fmt(_can_p['duration'])}s "
                    f"v_frames={_can_p['v_frames']} r={_fmt(_can_p['v_r'], 'fps')} "
                    f"avg={_fmt(_can_p['v_avg'], 'fps')} "
                    f"v_start={_fmt(_can_p['v_start'], 'ms')} "
                    f"a_start={_fmt(_can_p['a_start'], 'ms')}",
                    flush=True,
                )
                print(
                    f"[fps-probe] delta: dur_Δ={_dur_delta:+.4f}s "
                    f"frames_vs_expected_at_{_target_fps:.0f}fps={_frames_delta:+d} "
                    f"(canonical_frames={_can_p['v_frames']} expected={_expected_canon_frames})",
                    flush=True,
                )
            except Exception as _probe_err:
                print(f"[fps-probe] probe failed: {_probe_err}", flush=True)

            _size_mb = os.path.getsize(_norm_path) / (1024 * 1024)
            print(
                f"[fps-normalize] r={_r_val:.4f}fps avg={_avg:.4f}fps "
                f"-> {_target_fps:.4f}fps CFR (re-encoded: medium preset, "
                f"deshake={_needs_deshake}, normalize_vf={'yes' if _normalize_vf else 'no'}) in "
                f"{time.time() - _norm_t0:.1f}s ({_size_mb:.1f}MB)",
                flush=True,
            )
            # Verify dense keyframes actually landed in the encoded file.
            # x264 sometimes ignores -keyint_min when scene-cuts trigger; the
            # -sc_threshold 0 flag should disable that, but we have no proof
            # without ffprobe. Each Remotion seek pays decode-from-prev-keyframe
            # cost, so if GOPs are sparse we lose the v49 win silently. Counts
            # I-frame packets and the max gap between consecutive keyframes.
            try:
                _kf_t0 = time.time()
                _kf_probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "packet=pts_time,flags",
                     "-of", "csv=print_section=0", _norm_path],
                    capture_output=True, text=True, timeout=30,
                )
                _kf_times = []
                for _line in (_kf_probe.stdout or "").splitlines():
                    _parts = _line.strip().split(",")
                    if len(_parts) >= 2 and "K" in _parts[1]:
                        try:
                            _kf_times.append(float(_parts[0]))
                        except ValueError:
                            continue
                if _kf_times:
                    _kf_count = len(_kf_times)
                    _kf_gaps = [_kf_times[_i] - _kf_times[_i-1] for _i in range(1, len(_kf_times))]
                    _max_gap = max(_kf_gaps) if _kf_gaps else 0.0
                    _avg_gap = (sum(_kf_gaps) / len(_kf_gaps)) if _kf_gaps else 0.0
                    print(
                        f"[fps-normalize] keyframes={_kf_count} avg_gap={_avg_gap:.2f}s "
                        f"max_gap={_max_gap:.2f}s (probe {time.time()-_kf_t0:.1f}s) "
                        f"— v49 target: avg≈1.0s, max≤1.0s",
                        flush=True,
                    )
                    if _max_gap > 1.5:
                        print(
                            f"[fps-normalize] *** WARNING: max keyframe gap "
                            f"{_max_gap:.2f}s exceeds 1.5s — Remotion seeks "
                            f"will be slow despite -g {_gop_frames}.",
                            flush=True,
                        )
                else:
                    print(f"[fps-normalize] keyframe probe returned no data", flush=True)
            except Exception as _kf_err:
                print(f"[fps-normalize] keyframe probe failed: {_kf_err}", flush=True)
            return _norm_path

        # ── ALL initialization + Gemini edit in ONE parallel phase ────────────
        # Gemini starts as soon as transcript + upload + trend context are ready.
        # Everything runs concurrently — no sequential network calls on main thread.
        # If cached_analysis is provided (pre-computed by content-studio), skip the
        # entire Gemini chain (proxy encode + upload + poll + API call = ~19s savings).

        # Reinterpret AND guided_redraft both re-plan with a fused vibe; both
        # can reuse the prior Gemini visual analysis if the frontend sent it,
        # saving a Gemini roundtrip on the re-edit. content-studio's
        # cached_analysis (legacy) still wins if both are set.
        _cached_analysis = input_data.get("cached_analysis") or (
            provided_analysis if mode in ("reinterpret", "guided_redraft") else None
        )

        # Mode-aware stage skipping — render_only is the fully-deterministic path
        # that uses provided_plan and provided_transcript verbatim; reinterpret
        # can reuse a provided transcript/analysis but still re-plans with a fused
        # vibe; full is today's behavior.
        _skip_edit_gen = (mode == "render_only")
        # Transcribe is skipped if we have a provided transcript (render_only /
        # reinterpret) OR if the URL-based parallel Deepgram call above is
        # already running against this job.
        _skip_transcribe = bool(provided_transcript) or future_url_transcript is not None
        # Trend skipped when render_only (doesn't need it), when snapshot provided,
        # OR when the early-pool parallel fetch is running.
        _skip_trend = _skip_edit_gen or bool(provided_trend) or future_early_trend is not None
        _skip_proxy = _skip_edit_gen  # proxy is only needed to feed Gemini edit generation

        # Shared futures — edit recipe and face detect wait on their deps internally
        future_normalize = None
        future_transcribe = None
        future_gemini_proxy = None
        future_trend = None  # trend context fetched in parallel

        def _do_trend_context():
            # reinterpret with a provided trend snapshot still uses the CURRENT
            # trend_profiles row (per design: reinterpret = freshest style guide);
            # render_only skips this entirely.
            send_progress(job_id, "trend", 22, "Matching viral style patterns", app_url)
            tc = get_trend_context()
            if not tc:
                print("[trend] WARNING: Style guide not available — Gemini will edit without reference video patterns", flush=True)
            return tc

        # Shared transcript resolver. The edit-recipe consumer and the main
        # pipeline thread both call this. A lock + cache ensures resolution
        # runs exactly once. Word boundaries are raw Deepgram timestamps —
        # the main edit Gemini chooses cuts AT word boundaries, no acoustic
        # refinement.
        _refined_tx_cache: Dict[str, Any] = {"value": None}
        _refined_tx_lock = threading.Lock()

        def _get_resolved_transcript():
            with _refined_tx_lock:
                if _refined_tx_cache["value"] is not None:
                    return _refined_tx_cache["value"]
                _t = None
                if future_url_transcript is not None:
                    _t = future_url_transcript.result()
                if _t is None and future_transcribe is not None:
                    _t = future_transcribe.result()
                if _t is None:
                    _t = provided_transcript or {"words": []}

                # ── Deepgram is the single source of truth ──
                # Previously stacked Whisper-large-v3 + wav2vec2 forced
                # alignment on top of Deepgram. Removed 2026-05-23 — the
                # stack produced more failures (Whisper hallucinated word
                # positions, duplicate-transcribed common words, wav2vec2
                # over-extended boundaries into adjacent words) than the
                # marginal accuracy gain justified. Deepgram Nova-3 alone
                # provides word timing, speakers, and punctuation in one
                # call with no hallucination/duplication failure modes.
                # Proper-noun accuracy boosted via _deepgram_options
                # `keywords` (extracted from user vibe upstream).

                # ── Audio stream offset compensation (Option D) ──
                # Deepgram returns word timestamps in audio-data-time (FLAC
                # extraction strips audio_stream.start_time, which is default
                # ffmpeg behavior for raw audio output). The source's video
                # stream is on file-time, so the two timelines differ by
                # exactly the audio_stream.start_time metadata.
                #
                # Shift the transcript here — at the single point all
                # downstream consumers (cut builder, captions, SFX, B-roll)
                # read the transcript — so every timing reference becomes
                # file-time. Audio extraction in build_per_cut_audio converts
                # back to audio-data-time when indexing the WAV (the WAV
                # stays on audio-data-time because raw audio output can't
                # carry the offset metadata).
                #
                # For offset = 0 (source has no audio-capture-latency
                # metadata, e.g., pre-stripped iOS upload), this is a no-op.
                # For offset = 184ms (typical iPhone), every word shifts
                # forward by 184ms once. Idempotent against the cache: only
                # applied at the first resolve.
                try:
                    _src_info = future_normalize.result(timeout=180)
                    _offset = float(_src_info.get("audio_stream_offset") or 0.0)
                except Exception as _src_err:
                    print(f"[transcript-offset] source_info wait failed: {_src_err}", flush=True)
                    _offset = 0.0
                if _offset > 0.001:
                    _words = _t.get("words") or []
                    for _w in _words:
                        if not isinstance(_w, dict):
                            continue
                        if "start" in _w:
                            try:
                                _w["start"] = float(_w["start"]) + _offset
                            except (TypeError, ValueError):
                                pass
                        if "end" in _w:
                            try:
                                _w["end"] = float(_w["end"]) + _offset
                            except (TypeError, ValueError):
                                pass
                    print(
                        f"[transcript-offset] Shifted {len(_words)} words by +"
                        f"{_offset*1000:.1f}ms (audio_stream.start_time → file-time)",
                        flush=True,
                    )

                # ── pyannote speaker override (gated on Deepgram speaker count) ──
                # Deepgram's per-utterance speaker labels are unreliable on
                # 2-speaker interviews even when the voices are trivially
                # distinguishable, so we override them with pyannote when
                # there's actually a second speaker to disambiguate.
                #
                # The vast majority of TikTok/Reels uploads are single-speaker
                # selfie talking heads. Running pyannote on those wastes
                # 10-15s of GPU compute AND contends for resources with
                # fps_normalize / RIFE. Gating on Deepgram's speaker count
                # before dispatching pyannote saves that cost cleanly:
                #   • 1 speaker (typical): skip pyannote entirely
                #   • 2+ speakers: dispatch pyannote, await, override
                #
                # Trade-off: when pyannote IS needed (multi-speaker), it
                # starts AFTER Deepgram returns instead of in parallel
                # with it. That adds ~5-10s to the multi-speaker case but
                # saves ~10-15s on the much-more-common single-speaker
                # case. Net win across the user population.
                if not _skip_edit_gen:
                    _words_for_count = _t.get("words") or []
                    _speaker_set = set()
                    for _w in _words_for_count:
                        try:
                            _speaker_set.add(int(_w.get("speaker") or 0))
                        except (TypeError, ValueError):
                            pass
                    if len(_speaker_set) >= 2:
                        print(
                            f"[pyannote] Deepgram detected {len(_speaker_set)} speakers — "
                            f"dispatching pyannote for higher-accuracy diarization",
                            flush=True,
                        )
                        _pyannote_t0 = time.time()
                        try:
                            _pyannote_segments = diarize_with_pyannote(_raw_source)
                        except Exception as _py_err:
                            print(
                                f"[pyannote] diarization failed: {_py_err} — keeping Deepgram labels",
                                flush=True,
                            )
                            _pyannote_segments = []
                        if _pyannote_segments:
                            print(
                                f"[pyannote] {len(_pyannote_segments)} segments in "
                                f"{time.time() - _pyannote_t0:.1f}s — applying to words",
                                flush=True,
                            )
                            apply_pyannote_speakers(_t.get("words") or [], _pyannote_segments)
                            _t["pyannote_segments"] = _pyannote_segments
                    else:
                        print(
                            f"[pyannote] Deepgram detected single speaker — "
                            f"skipping pyannote (saves ~10-15s)",
                            flush=True,
                        )

                _refined_tx_cache["value"] = _t
                return _t

        def _do_edit_recipe_overlapped():
            """Start Gemini as soon as transcript + proxy + trend + audio + face signals are ready.
            Transcript may come from the early_pool URL-based Deepgram call (ran in parallel
            with the download), a regular mega-pool file-based call, or the provided_transcript
            for re-edit paths. Whichever landed first wins.
            """
            _transcript = _get_resolved_transcript()
            _proxy_bytes = future_gemini_proxy.result() if future_gemini_proxy is not None else None
            if future_early_trend is not None:
                try:
                    _trend = future_early_trend.result(timeout=10)
                except Exception as _tr_err:
                    print(f"[pipeline] early trend fetch failed: {_tr_err} — proceeding without trend", flush=True)
                    _trend = provided_trend
            elif future_trend is not None:
                _trend = future_trend.result()
            else:
                _trend = provided_trend
            # Shot changes + vocal emphasis + loudness all feed into Gemini's
            # placement decisions. Beats are NOT computed for talking-head
            # content — they're noise on speech audio.
            _shots = future_shot_changes.result()
            _vocal = future_vocal_emphasis.result()
            _loudness = future_loudness.result()
            # Face detection (proxy-based) completes before Gemini — collect here
            # so the prompt can carry face visibility + speaker-position signals.
            # Detection typically finishes in 2-3s; Gemini at MEDIUM thinking takes
            # 15-25s, so this adds zero latency to critical path.
            _face_res = future_faces.result() if future_faces is not None else ([], [])
            if isinstance(_face_res, tuple) and len(_face_res) == 2:
                _face_positions, _smoothed_trajectory = _face_res
            else:
                _face_positions, _smoothed_trajectory = [], []
            _dg_words = _transcript.get("words", [])

            # ─── TALKING-HEAD GATE ──────────────────────────────────────
            # This app is built for talking-head content: a person speaking
            # on camera, with the speaker's face visible most of the runtime.
            # Non-talking-head uploads (b-roll only, music videos, ASMR,
            # screen recordings, animation) produce structurally broken edits
            # because every component decision (zoom on the face, B-roll on
            # named nouns, captions on speech) assumes a speaker on camera.
            #
            # We gate ONCE here, with two cheap signals already computed:
            #   • Face detection ratio: % of sampled frames that contained
            #     a face. < 30% means the speaker isn't on camera enough
            #     for talking-head editing to work.
            #   • Transcript word count: < 15 words on a 15+ second video
            #     means there isn't enough speech to drive a speech-anchored
            #     edit. Music videos, ambient content, ASMR fall here.
            #
            # Failing fast with a clear error message is dramatically better
            # for the user than producing a broken edit. They get a 30-second
            # turnaround "this isn't the right kind of video" instead of a
            # 90-second wait followed by a structurally-bad result.
            _face_samples = len(_face_positions or [])
            _face_hits = sum(
                1 for _fp in (_face_positions or [])
                if isinstance(_fp, dict) and _fp.get("found")
            )
            _face_ratio = (_face_hits / _face_samples) if _face_samples > 0 else 0.0
            _word_count = len(_dg_words)
            print(
                f"[talking-head-gate] face_ratio={_face_ratio:.2f} "
                f"({_face_hits}/{_face_samples}) words={_word_count} "
                f"duration={source_duration:.1f}s",
                flush=True,
            )
            # Both conditions must hint at "not a talking head" before we
            # reject. False-positive rejection of a real talking-head video
            # is dramatically worse than letting a borderline non-talking-head
            # through (the latter just produces a thinner edit, not an error).
            #
            # Calibrated to be LENIENT:
            #   • Face: 20% threshold (was 30%) AND requires 8+ samples
            #     (was 5) so short videos with sparse sampling don't trip.
            #   • Speech: 10 words floor (was 15) AND requires 15+ second
            #     duration so very short clips aren't penalized.
            #   • Both conditions must hold to reject.
            _face_low = (_face_samples >= 8 and _face_ratio < 0.20)
            _speech_low = (source_duration >= 15.0 and _word_count < 10)
            if _face_low and _speech_low:
                raise RuntimeError(
                    f"NOT_TALKING_HEAD: face in only {_face_hits}/{_face_samples} "
                    f"({_face_ratio*100:.0f}%) frames AND only {_word_count} "
                    f"words in {source_duration:.1f}s. This app edits talking-"
                    f"head videos — please upload a video of someone speaking "
                    f"on camera."
                )
            # ─── END TALKING-HEAD GATE ──────────────────────────────────

            if len(_dg_words) == 0:
                print("[pipeline] WARNING: Deepgram returned 0 words — proceeding without speech (no captions, time-based cuts only)", flush=True)
            send_progress(job_id, "plan", 38, "Writing your edit recipe", app_url)
            print(
                f"[pipeline] Gemini edit starting (words: {len(_dg_words)}, "
                f"shot_changes: {len(_shots or [])}, vocal peaks: {len(_vocal or [])}, "
                f"face samples: {len(_face_positions or [])})",
                flush=True,
            )
            _user_profile = None
            if future_user_style is not None:
                try:
                    _user_profile = future_user_style.result(timeout=10)
                except Exception as _upe:
                    print(f"[user-style] Profile fetch failed: {_upe}", flush=True)
                    _user_profile = None
            # Heartbeat: Gemini Pro editorial call is the biggest opaque wait
            # in the pipeline (30-60s typical). Without ticks the UI bar
            # sits at 38% and users report "stuck at 43%". Heartbeat ramps
            # the bar to 50% over the expected duration; capped there if the
            # call runs long, or stopped early if it finishes fast.
            # Rotating message list — what Gemini is actually doing under the
            # hood, mapped to a sequence the user reads as "real work
            # happening." Addresses "stuck at 43%" complaints by varying
            # the message even when the percentage moves slowly.
            _gemini_hb_stop = _start_progress_heartbeat(
                job_id, "plan", 38, 50,
                [
                    "Watching your video",
                    "Reading the speaker's energy",
                    "Identifying key moments",
                    "Choosing visual treatments",
                    "Planning B-roll cutaways",
                    "Composing your edit",
                ],
                app_url,
                duration_estimate_s=45.0,
            )
            try:
                # GUIDED REDRAFT — when the plan-diff classifier routed this
                # job as guided_redraft, the prior plan is injected as soft
                # default + the user's directional change_request is the
                # override. Both are None for fresh ("full") and pure
                # reinterpret jobs; the prompt block is only built when
                # prior_plan is a non-empty dict.
                _gr_prior = provided_plan if mode == "guided_redraft" else None
                _gr_dir = change_request if mode == "guided_redraft" else None
                return generate_edit_gemini(
                    video_path=_raw_source,
                    vibe=vibe,
                    duration=source_duration,
                    trend_context=_trend,
                    deepgram_words=_dg_words,
                    shot_changes=_shots,
                    shot_change_scores=_shot_change_scores,
                    vocal_emphasis=_vocal,
                    source_loudness=_loudness,
                    face_positions=_face_positions,
                    smoothed_face_trajectory=_smoothed_trajectory,
                    user_style_profile=_user_profile,
                    inline_video_bytes=_proxy_bytes,
                    cached_response=_cached_analysis,
                    prior_plan=_gr_prior,
                    prior_plan_change_request=_gr_dir,
                )
            finally:
                _gemini_hb_stop.set()

        def _do_face_detect_overlapped():
            """Run face detection on 240p proxy (much faster than 1080p source).
            Waits for proxy encode (~1.5s), then decodes 240p instead of 1080p (~20x fewer pixels).
            Falls back to the raw source when no proxy was encoded (render_only mode)."""
            send_progress(job_id, "face_detect", 14, "Tracking faces frame-by-frame", app_url)
            _proxy_exists = False
            if future_gemini_proxy is not None:
                future_gemini_proxy.result()
                _proxy_path = os.path.join(work_dir, "gemini_proxy.mp4")
                _proxy_exists = os.path.exists(_proxy_path)
            # Sparse sampling target: ~1 detection per 3s of source — roughly
            # one sample per cut at typical short-form pacing (~20 cuts per
            # 60s video → 20 detections). The EMA smoothing in
            # smooth_face_trajectory interpolates between samples and coasts
            # through gaps, so coarse samples still produce a continuous
            # trajectory. Trade-off accepted: fast head movement (~1s spans)
            # will be missed and the source-reframe crop will be less
            # precise on high-motion content.
            if _proxy_exists:
                # Proxy is 10fps — every 30 frames ≈ 1 detection per 3s.
                dense = detect_face_positions_dense(
                    os.path.join(work_dir, "gemini_proxy.mp4"), every_n_frames=30,
                    target_w=1080, target_h=1920,
                )
            else:
                # No proxy (render_only) or proxy missing — use raw source.
                # Source is up to 60fps; every 180 frames ≈ 1 detection per 3s.
                dense = detect_face_positions_dense(_raw_source, every_n_frames=180)
            if dense:
                smoothed = smooth_face_trajectory(dense, total_duration=source_duration)
                print(f"[dense-face] Smoothed trajectory: {len(smoothed)} keyframes", flush=True)
                return dense, smoothed
            return [], []

        # Manual pool management — do NOT use `with` block because it calls
        # shutdown(wait=True) on exit, which would block on future_faces and defeat
        # the deferred face collection optimization (face detection should overlap with Remotion).
        mega_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        future_normalize = mega_pool.submit(_do_normalize)
        future_transcribe = None if _skip_transcribe else mega_pool.submit(_do_transcribe)
        # pyannote speaker diarization is now LAZILY dispatched from inside
        # `_get_resolved_transcript()` — only after Deepgram returns and only
        # if Deepgram detected 2+ speakers. The vast majority of uploads
        # (selfie talking heads) are single-speaker; running pyannote on
        # those wastes ~10-15s of GPU compute and contends for resources
        # with fps_normalize / RIFE. See the gated-dispatch block in
        # _get_resolved_transcript above for the speaker-count logic.
        future_gemini_proxy = None if _skip_proxy else mega_pool.submit(_do_gemini_proxy)
        future_trend = None if _skip_trend else mega_pool.submit(_do_trend_context)
        future_loudness = mega_pool.submit(_do_loudness)
        future_shot_changes = mega_pool.submit(_do_shot_changes)
        future_vocal_emphasis = mega_pool.submit(_do_vocal_emphasis)
        future_fps_normalize = mega_pool.submit(_do_fps_normalize)
        # Per-user style profile — fetched in parallel with everything else; read
        # inside _do_edit_recipe_overlapped so it arrives before Gemini is called.
        # Skip in render_only (plan is deterministic from the provided edit_plan).
        future_user_style = (
            None if _skip_edit_gen else mega_pool.submit(fetch_user_style_profile, user_id)
        )
        # Edit recipe waits on transcript + upload + face/signals internally — skipped entirely in render_only
        future_edit = None if _skip_edit_gen else mega_pool.submit(_do_edit_recipe_overlapped)
        # Face detection runs directly on raw source (no normalize dependency)
        future_faces = mega_pool.submit(_do_face_detect_overlapped)

        # Collect results — get edit_plan FIRST so we can start B-roll fetch early
        _mega_t0 = time.time()
        if future_edit is not None:
            edit_plan = future_edit.result()  # critical path — longest wait (Gemini)
        else:
            # render_only: use the provided plan. Deep-copy so downstream mutations
            # (private _foo fields, thumbnail projection, etc.) don't pollute caller state.
            import copy as _copy_mod
            edit_plan = _copy_mod.deepcopy(provided_plan)
            print("[pipeline] render_only mode — using provided edit_plan (skipped Gemini generate)", flush=True)
        print(f"[TIMING] edit_plan ready in {time.time() - _mega_t0:.1f}s (critical path)", flush=True)

        # ── Layer 3 safety net for guided_redraft mode ───────────────────
        # The freshly-generated edit_plan came from generate_edit_gemini
        # with the prior plan injected as soft default. Diff it against
        # the prior plan + scope-classify each change. Phase 1: log only
        # for guided_redraft (no auto-revert — the soft-carry-over
        # contract gives Gemini documented latitude to modify
        # consequentially; reverting risks over-correction). The logs
        # feed Phase 2 tuning.
        # FAIL-OPEN end-to-end.
        if mode == "guided_redraft":
            _orig_prior_for_validation = input_data.get("edit_plan")
            if isinstance(_orig_prior_for_validation, dict) and isinstance(edit_plan, dict):
                try:
                    _validation = validate_reedit_changes(
                        prior_plan=_orig_prior_for_validation,
                        new_plan=edit_plan,
                        change_request=change_request,
                        mode="guided_redraft",
                    )
                    print(
                        f"[reedit-validate] guided_redraft verdict={_validation.get('verdict')} "
                        f"diffs={len(_validation.get('diffs') or [])} "
                        f"out_of_scope={len(_validation.get('out_of_scope_paths') or [])}",
                        flush=True,
                    )
                    # apply_scalar_reverts is a no-op for guided_redraft
                    # in Phase 1 (logs only); calling it explicitly so the
                    # codepath is exercised + a single switch-flip turns
                    # on Phase 2 reverts when we have production data.
                    edit_plan = apply_scalar_reverts(
                        prior_plan=_orig_prior_for_validation,
                        new_plan=edit_plan,
                        validation=_validation,
                        mode="guided_redraft",
                    )
                except Exception as _val_err:
                    print(
                        f"[reedit-validate] guided_redraft safety net error "
                        f"(fail open): {_val_err}",
                        flush=True,
                    )

        # Start B-roll fetch IMMEDIATELY while other futures may still be running
        _broll_fetch_pool = None
        _broll_fetch_futures = {}
        broll_clips = edit_plan.get("broll_clips") or []
        if broll_clips:
            send_progress(job_id, "broll_search", 52, "Sourcing B-roll cutaways", app_url)
            print(f"[broll] Starting parallel fetch of {len(broll_clips)} B-roll clip(s) (overlapping with face detect)...", flush=True)
            # Resolve transcript (cached) so we can pass the actual spoken words at the
            # cutaway window into the visual-pick step. broll_clip indices were already
            # _xlate'd to deepgram-word space upstream.
            _broll_tx_words = (_get_resolved_transcript().get("words") or [])
            _broll_fetch_pool = concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(broll_clips)))
            for _bi, _bc in enumerate(broll_clips):
                _dlg_text = ""
                try:
                    _sw = int(_bc.get("start_word_index"))
                    _ew = int(_bc.get("end_word_index"))
                    if 0 <= _sw <= _ew < len(_broll_tx_words):
                        _dlg_text = " ".join(
                            str(_broll_tx_words[_i].get("word") or "").strip()
                            for _i in range(_sw, _ew + 1)
                        ).strip()
                except (TypeError, ValueError):
                    pass
                _fut = _broll_fetch_pool.submit(
                    fetch_broll_clip,
                    _bc,  # pass whole entry — fetch_broll_clip mutates it with resolved Pexels metadata
                    float(_bc.get("duration") or 2.0),
                    work_dir,
                    dialogue_reason=str(_bc.get("reason") or ""),
                    dialogue_text=_dlg_text,
                )
                _broll_fetch_futures[_fut] = _bi

        # Collect fast futures (all should be done already — they finish before Gemini).
        # Face detection is collected LATER inside render_multi_clip so Remotion can
        # launch immediately without waiting for face detection to finish.
        _collect_t0 = time.time()
        source_info = future_normalize.result()
        source_path = source_info["source_path"]
        _normalize_vf = source_info.get("normalize_vf")
        _audio_stream_offset = float(source_info.get("audio_stream_offset") or 0.0)
        # Resolve transcript through the shared resolver. The edit-recipe
        # consumer already triggered this; here we retrieve the cached value.
        # The resolver applies the audio_stream_offset shift internally so
        # word timings are in file-time matching the video stream.
        transcript = _get_resolved_transcript()
        if not (future_url_transcript is not None or future_transcribe is not None):
            print(f"[pipeline] Using provided transcript ({len(transcript.get('words') or [])} words) — skipped Deepgram", flush=True)
        # Attach the offset to the edit_plan so render_multi_clip can pass
        # it down to build_per_cut_audio (which converts file-time slice
        # positions back to audio-data-time for WAV indexing).
        if isinstance(edit_plan, dict):
            edit_plan["_audio_stream_offset"] = _audio_stream_offset
        source_loudness = future_loudness.result()
        source_shot_changes = future_shot_changes.result()
        # Capture which trend context was used (fresh vs. snapshot) for persistence
        if future_early_trend is not None:
            try:
                trend_used = future_early_trend.result(timeout=0)
            except Exception:
                trend_used = None
        elif future_trend is not None:
            try:
                trend_used = future_trend.result(timeout=0)
            except Exception:
                trend_used = None
        else:
            trend_used = provided_trend
        # Swap in the canonicalized source for render. fps_normalize ran in
        # parallel with Gemini so this is already done by the time we get
        # here. Downstream render detects source_fps from the new file's
        # r_frame_rate (preserved at the source's native rate — 30, 24,
        # 60, etc.) and all frame-count math becomes exact.
        source_path = future_fps_normalize.result()
        # Collect face trajectory: render_multi_clip uses it for face-aware
        # MG placement (re-routing center anchors when the speaker's face
        # would be covered). Detection finished long before we got here
        # (~2-3s on the proxy) so the .result() call is essentially free.
        # Mirrors the same .result() the edit-recipe closure does — if both
        # await it, Future caches the result and second call is free.
        _face_positions, _smoothed_trajectory = future_faces.result()
        _collect_elapsed = time.time() - _collect_t0
        if _collect_elapsed > 0.5:
            print(f"[TIMING] Fast futures collected in {_collect_elapsed:.1f}s", flush=True)
        # Shut down mega_pool. Face detection, if still running, is only useful
        # for generate_edit_gemini's prompt signals — by the time we're here,
        # that call has already returned (and it awaited future_faces itself).
        # For render_only / reinterpret paths that skip Gemini, the face data
        # has no downstream consumer anyway.
        mega_pool.shutdown(wait=False)

        # Source res is what it is — normalize filter will handle conversion in render
        source_res = {"width": source_info["width"], "height": source_info["height"]}
        print(f"[DIAG] Source: {source_res['width']}x{source_res['height']} @ {source_info['fps']:.1f}fps, normalize_vf={'yes' if _normalize_vf else 'no'}", flush=True)

        # Record the face-transform used during source normalization so render
        # can map the reframe math correctly.
        _ft = source_info.get("face_transform", {})
        edit_plan["_face_transform"] = _ft

        # The smoothed dense trajectory feeds prompt signals (FACE
        # VISIBILITY, FACE VERTICAL ZONE, SPEAKER POSITIONS, OFF-CENTER)
        # AND drives zoom-origin face-lock in render_multi_clip via
        # _resolve_zoom_origin. Reusing the SAME trajectory respects the
        # sparse-sampling preference — no per-event re-detection.
        edit_plan["_face_trajectory"] = list(_smoothed_trajectory or [])

        _timings["normalize_transcribe_upload"] = time.time() - t
        _dg_words = transcript.get("words", [])
        if len(_dg_words) == 0 and mode != "render_only":
            # Talking-head editor requires spoken content. Silent/no-speech sources
            # produce no captions and no word-based cuts, so there's nothing to edit.
            # In render_only we trust the provided plan (previous render already
            # handled this case) but a fresh pipeline run must have speech.
            raise RuntimeError(
                "No speech detected in source (Deepgram returned 0 words). This "
                "pipeline requires spoken audio."
            )
        print(f"[pipeline] All init complete: {len(_dg_words)} words, edit recipe ready ({_timings['normalize_transcribe_upload']:.1f}s)", flush=True)

        print(f"[edit] User vibe: \"{vibe}\"", flush=True)

        if _normalize_vf:
            print(f"[reframe] Smart reframe applied at ingest (source_canonical.mp4 is 1080x1920)", flush=True)
        else:
            print("[reframe] Source is native 9:16 — ingest only did fps + pix_fmt", flush=True)

        edit_plan["_user_vibe"] = vibe
        edit_plan["_source_path"] = source_path
        # Record what reframe filter was applied at ingest for downstream
        # face-coordinate mapping. The render pipeline no longer reads this
        # to APPLY the filter — it's already baked into source_canonical.mp4.
        edit_plan["_normalize_vf"] = _normalize_vf
        edit_plan["_source_loudness"] = source_loudness
        edit_plan["_shot_changes"] = source_shot_changes
        _timings["edit_recipe_faces"] = 0
        print(f"[pipeline] Pipeline init phase complete", flush=True)

        analysis = edit_plan.get("analysis_data") or {}

        # ── B-roll prefetch + verify ──────────────────────────────────────
        # Block here for fetches to complete and verify each downloaded asset
        # via ffprobe. Entries that didn't fetch or didn't verify are dropped
        # from edit_plan["broll_clips"] — they never enter the render spec, so
        # the persisted plan equals what was actually rendered. By construction
        # there is no "render asked for X but skipped X" gap to fall through.
        if _broll_fetch_futures:
            broll_clips = prefetch_and_verify_broll(broll_clips, _broll_fetch_futures)
            edit_plan["broll_clips"] = broll_clips
        if _broll_fetch_pool:
            _broll_fetch_pool.shutdown(wait=False)

        print("[pipeline] step=parallel_render", flush=True)
        send_progress(job_id, "render", 65, "Rendering your edit", app_url)
        # Heartbeat: render_multi_clip is the longest single phase. Duration
        # scales with source length — a 30s source renders in ~60-90s, a 60s
        # source in ~120-180s. Previously fixed at 90s, which under-estimated
        # for longer videos and parked the bar at 90% for 30-60s before the
        # 92% thumbnail event fired. Now: ~3× source duration, clamped to
        # [60, 240]s, so the bar paces the actual render and snaps cleanly
        # to the next milestone instead of stalling.
        _render_est = max(60.0, min(240.0, float(source_duration) * 3.0))
        _render_hb_stop = _start_progress_heartbeat(
            job_id, "render", 65, 90,
            [
                "Stabilizing your footage",
                "Cutting your timeline",
                "Adding captions and emphasis",
                "Compositing your edit",
                "Mastering audio",
                "Finalizing your video",
            ],
            app_url,
            duration_estimate_s=_render_est,
        )
        t = time.time()
        try:
            render_multi_clip(
                source_path, edit_plan["cuts"], edit_plan, output_path, transcript, work_dir,
                broll_clips=broll_clips,
            )
        finally:
            _render_hb_stop.set()
        edit_plan["_deepgram_words"] = transcript.get("words", [])

        render_elapsed = time.time() - t
        _timings["render"] = render_elapsed
        print(f"[pipeline] parallel_render complete in {render_elapsed:.1f}s", flush=True)
        # NB: this label must match the actual encode in _build_composite_cmd
        # / final concat+mux; both currently use libx264 -preset medium -crf 18.
        # Update here too if you change the encoder.
        _enc_label = "NVENC" if _HAS_NVENC else "libx264/medium crf=18 threads=auto"
        print(f"[render] Encoding: {_enc_label}", flush=True)
        # Validate render output — single ffprobe for file check + duration extraction
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100000:
            raise RuntimeError(f"Main render produced invalid output: {output_path}")
        _rv, _ra = 0.0, 0.0
        _v_start, _a_start = 0.0, 0.0
        try:
            probe_cache_clear(output_path)  # freshly rendered — clear stale cache
            _cp = _probe_full(output_path)
            for _s in (_cp.get("streams") or []):
                if _s.get("codec_type") == "video":
                    if _s.get("duration"):
                        _rv = float(_s["duration"])
                    if _s.get("start_time"):
                        _v_start = float(_s["start_time"])
                elif _s.get("codec_type") == "audio":
                    if _s.get("duration"):
                        _ra = float(_s["duration"])
                    if _s.get("start_time"):
                        _a_start = float(_s["start_time"])
        except Exception:
            pass
        if _rv < 1.0:
            raise RuntimeError(f"Main render output too short: video={_rv:.1f}s")
        _av_end_delta_ms = ((_ra + _a_start) - (_rv + _v_start)) * 1000
        _av_start_delta_ms = (_a_start - _v_start) * 1000
        print(
            f"[render] Output valid: {os.path.getsize(output_path)/1024/1024:.1f}MB, "
            f"video={_rv:.3f}s audio={_ra:.3f}s",
            flush=True,
        )
        print(
            f"[render] A/V sync probe: "
            f"v_start={_v_start*1000:+.2f}ms  a_start={_a_start*1000:+.2f}ms  "
            f"start_delta={_av_start_delta_ms:+.2f}ms  end_delta={_av_end_delta_ms:+.2f}ms",
            flush=True,
        )
        # ── DIAG PROBE 4: output content verification ──
        # Re-prints the key numbers in a stable format for cross-referencing
        # against probes 1-3. If everything above this point is right but
        # this row shows mismatch, the bug is in the final mux/encode step.
        # If everything else is wrong, this row will inherit those errors.
        try:
            _out_v_pkt = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "packet=pts_time", "-of", "csv=p=0",
                 "-read_intervals", "0%+1", output_path],
                capture_output=True, text=True, timeout=15,
            )
            _out_a_pkt = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "packet=pts_time", "-of", "csv=p=0",
                 "-read_intervals", "0%+1", output_path],
                capture_output=True, text=True, timeout=15,
            )
            _first_v = (_out_v_pkt.stdout or "").splitlines()[0] if _out_v_pkt.stdout else "?"
            _first_a = (_out_a_pkt.stdout or "").splitlines()[0] if _out_a_pkt.stdout else "?"
            print(
                f"[output-probe] actual: v_dur={_rv:.4f}s a_dur={_ra:.4f}s "
                f"first_v_pts={_first_v.strip(',')} first_a_pts={_first_a.strip(',')}",
                flush=True,
            )
        except Exception as _opb:
            print(f"[output-probe] probe failed: {_opb}", flush=True)

        cuts = edit_plan.get("_render_cuts") or edit_plan.get("cuts") or []
        effective_durations = edit_plan.get("_render_effective_durations") or compute_effective_durations(cuts)
        final_dur = _rv

        # B-roll is now integrated into the first FFmpeg pass (no second encode needed)
        _timings["broll"] = 0.0

        # ── Parallel group 2: cover frame + upload ────────────────────────────────
        t = time.time()
        thumbnail_source_ts = edit_plan.get("thumbnail_timestamp")
        if thumbnail_source_ts is None:
            thumbnail_source_ts = (source_duration / 3.0) if source_duration > 0 else 1.0
        cover_frame_ts = project_source_time_to_final_output(
            float(thumbnail_source_ts),
            cuts,
            effective_durations,
            clip_time_maps=edit_plan.get("_render_clip_time_maps"),
        )
        if cover_frame_ts is None:
            cover_frame_ts = min(1.0, max(0.1, final_dur - 0.1))
        cover_frame_b64  = None
        cover_frame_mime = "image/jpeg"

        if not validate_output(output_path, "final"):
            raise RuntimeError(f"Final output is invalid: {output_path}")
        output_size_mb = os.path.getsize(output_path) / (1024*1024)
        send_progress(job_id, "thumbnail", 92, "Picking your cover frame", app_url)
        send_progress(job_id, "upload", 96, "Publishing to your library", app_url)
        print(f"[pipeline] output: {output_size_mb:.1f}MB, {final_dur:.1f}s — parallel upload + cover frame", flush=True)

        def _upload_main():
            print("[pipeline] step=upload", flush=True)
            # Direct S3 multipart upload — much faster than single-stream HTTP PUT
            # for 100-200 MB videos. boto3[crt] does multipart automatically with
            # _S3_TRANSFER_CONFIG (32 concurrent 16-MB parts).
            #
            # Route by URL scheme:
            #   AWS S3 (virtual-host or accelerate or path-style or CloudFront)
            #     → _aws_s3_client. This is the normal dispatcher path.
            #   Supabase storage (legacy)
            #     → _s3_client (Supabase S3-compatible endpoint).
            # End destination is identical to what the dispatcher pre-signed,
            # so any CDN origin access remains valid.
            if not upload_url:
                raise RuntimeError("No upload_url provided — Node dispatcher must pre-generate the presigned PUT URL")
            _aws_b, _aws_k = _parse_aws_s3_url(upload_url)
            if _aws_b and _aws_k:
                if not _aws_s3_client:
                    raise RuntimeError("AWS S3 client not initialized — cannot upload (check AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env)")
                _client, _bucket, _key, _scheme = _aws_s3_client, _aws_b, _aws_k, "aws"
            else:
                _sb_b, _sb_k = _parse_supabase_storage_url(upload_url)
                if _sb_b and _sb_k:
                    if not _s3_client:
                        raise RuntimeError("Supabase S3 client not initialized — cannot upload (check SUPABASE_S3_ACCESS_KEY/SECRET_KEY env)")
                    _client, _bucket, _key, _scheme = _s3_client, _sb_b, _sb_k, "supabase"
                else:
                    raise RuntimeError(
                        f"Could not parse bucket/key from upload_url (neither AWS nor Supabase pattern matched): "
                        f"{upload_url[:120]}"
                    )
            _ut0 = time.time()
            _client.upload_file(
                output_path, _bucket, _key,
                ExtraArgs={"ContentType": "video/mp4"},
                Config=_S3_TRANSFER_CONFIG,
            )
            _ue = time.time() - _ut0
            if input_data.get("public_url"):
                _video_url = input_data["public_url"]
            else:
                _video_url = upload_url.split("?")[0]
            _mb = os.path.getsize(output_path) / (1024 * 1024)
            print(
                f"[pipeline] upload complete ({_scheme}-multipart {_mb:.1f}MB in {_ue:.1f}s "
                f"@ {_mb / max(_ue, 0.001):.1f}MB/s → {_video_url})",
                flush=True,
            )
            edit_plan["_rendered_video_url"] = _video_url

        def _extract_and_upload_cover():
            # Pick the visually best frame from the FINAL RENDERED OUTPUT around
            # Gemini's projected timestamp. The output has captions burned in,
            # speed warps applied, and zoom effects — exactly what makes a great
            # social-media thumbnail. NO additional post-processing.
            #
            # If Gemini's seed lands inside a b-roll segment, shift it to the
            # nearest moment showing the speaker (not the b-roll content).
            _thumb_seed = float(cover_frame_ts)
            _broll_ranges = edit_plan.get("_broll_output_ranges") or []
            for _br_start, _br_end in _broll_ranges:
                if _br_start <= _thumb_seed <= _br_end:
                    # Shift to whichever side of the b-roll is closer
                    _dist_before = _thumb_seed - _br_start
                    _dist_after = _br_end - _thumb_seed
                    if _dist_before <= _dist_after:
                        _thumb_seed = max(0.1, _br_start - 0.3)
                    else:
                        _thumb_seed = min(final_dur - 0.1, _br_end + 0.3)
                    print(
                        f"[thumbnail] Seed was inside b-roll [{_br_start:.2f}, {_br_end:.2f}], "
                        f"shifted to {_thumb_seed:.2f}s",
                        flush=True,
                    )
                    break
            # AI-scored thumbnail selection. No fallback — if the scorer fails,
            # the whole job fails so the underlying bug gets fixed at root.
            data, mime = select_best_thumbnail_frame(
                output_path, _thumb_seed, work_dir,
            )
            if data:
                print(
                    f"[pipeline] cover frame at {cover_frame_ts:.2f}s "
                    f"(AI-selected from source {float(thumbnail_source_ts):.2f}s, {len(data)//1024}KB)",
                    flush=True,
                )
                # Upload thumbnail in parallel with main video upload
                upload_url_thumb = input_data.get("upload_url_thumb")
                if upload_url_thumb:
                    _thumb_uploaded = False
                    if _s3_client:
                        _tb, _tk = _parse_supabase_storage_url(upload_url_thumb)
                        if _tb and _tk:
                            try:
                                import io as _io_thumb
                                _s3_client.upload_fileobj(
                                    _io_thumb.BytesIO(data), _tb, _tk,
                                    ExtraArgs={"ContentType": mime},
                                )
                                print("[pipeline] thumbnail uploaded (s3)", flush=True)
                                _thumb_uploaded = True
                            except Exception as _s3_thumb_err:
                                print(f"[pipeline] S3 thumbnail upload failed ({_s3_thumb_err}), falling back to HTTP", flush=True)
                    if not _thumb_uploaded:
                        try:
                            thumb_resp = requests.put(
                                upload_url_thumb, data=data,
                                headers={"Content-Type": mime}, timeout=30,
                            )
                            thumb_resp.raise_for_status()
                            print("[pipeline] thumbnail uploaded (http)", flush=True)
                        except Exception as thumb_err:
                            print(f"[pipeline] thumbnail upload failed (non-fatal): {thumb_err}", flush=True)
                else:
                    print("[pipeline] thumbnail: no upload_url_thumb provided by frontend", flush=True)
            return data, mime

        # ── HLS variant ladder + upload ───────────────────────────────────
        # Generates a 4-variant adaptive bitrate ladder (360p / 540p / 720p
        # / 1080p) packaged as fMP4 segments behind a master .m3u8 manifest.
        # AVPlayer's fastest playback path is HLS — first segment is
        # independently playable in <100ms, adaptive bitrate handles
        # network changes gracefully, no whole-file metadata to load.
        # Required: failure raises and fails the whole render so the
        # client never sees a half-baked job that's missing the streaming
        # variants.
        def _upload_hls():
            if not _aws_s3_client:
                raise RuntimeError(
                    "HLS encode requires AWS S3 — _aws_s3_client is None "
                    "(check AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env)"
                )
            _aws_b, _aws_k = _parse_aws_s3_url(upload_url)
            if not (_aws_b and _aws_k):
                raise RuntimeError(
                    f"HLS encode requires the upload_url to be an AWS S3 URL — "
                    f"could not parse bucket/key from: {upload_url[:120]}"
                )

            hls_dir = os.path.join(work_dir, "hls")
            os.makedirs(hls_dir, exist_ok=True)
            _hls_t0 = time.time()

            # 1080p variant copies the master's bitrate (no perceptible
            # quality loss vs source); lower variants re-encode at
            # progressively lower bitrates. veryfast preset keeps the
            # added render time under ~25s for typical clips.
            # HLS BITRATE / PRESET TUNING — was producing visibly soft output
            # because the 1080p variant capped at 6 Mbps veryfast (preset is
            # 2nd-worst libx264, needs ~50% more bitrate for same quality as
            # medium). iPhone sources arrive at 17-25 Mbps; capping playback
            # at 6 Mbps lost obvious detail in motion + B-roll.
            #
            # SETTINGS:
            #   • preset: veryfast → medium (~3x better quality-per-bit)
            #   • 1080p60: 6 Mbps → 14 Mbps (matches iPhone source bitrate)
            #   • 720p:    4 Mbps → 7.5 Mbps
            #   • 540p:    2.5 Mbps → 4.5 Mbps
            #   • 360p:    1.5 Mbps → 2 Mbps (slight bump)
            # Cost: HLS step adds ~30-50s vs. veryfast on a 30s video.
            # Result: 1080p HLS is now visually close-to-transparent vs. the
            # master MP4. CapCut / Captions.ai output around 12-16 Mbps for
            # 1080p60 social-form content — we're now in that range.
            _hls_cmd = [
                "ffmpeg", "-y", "-i", output_path,
                "-filter_complex",
                "[0:v]split=4[v1][v2][v3][v4];"
                "[v1]scale=-2:360[v360];"
                "[v2]scale=-2:540[v540];"
                "[v3]scale=-2:720[v720];"
                "[v4]scale=-2:1080[v1080]",
                # 360p
                "-map", "[v360]", "-map", "0:a:0",
                "-c:v:0", "libx264", "-preset:v:0", "medium",
                "-b:v:0", "2000k", "-maxrate:v:0", "2200k", "-bufsize:v:0", "4M",
                "-c:a:0", "aac", "-b:a:0", "96k", "-ar:a:0", "48000",
                # 540p
                "-map", "[v540]", "-map", "0:a:0",
                "-c:v:1", "libx264", "-preset:v:1", "medium",
                "-b:v:1", "4500k", "-maxrate:v:1", "5000k", "-bufsize:v:1", "9M",
                "-c:a:1", "aac", "-b:a:1", "128k", "-ar:a:1", "48000",
                # 720p
                "-map", "[v720]", "-map", "0:a:0",
                "-c:v:2", "libx264", "-preset:v:2", "medium",
                "-b:v:2", "7500k", "-maxrate:v:2", "8250k", "-bufsize:v:2", "15M",
                "-c:a:2", "aac", "-b:a:2", "128k", "-ar:a:2", "48000",
                # 1080p
                "-map", "[v1080]", "-map", "0:a:0",
                "-c:v:3", "libx264", "-preset:v:3", "medium",
                "-b:v:3", "14000k", "-maxrate:v:3", "15400k", "-bufsize:v:3", "28M",
                "-c:a:3", "aac", "-b:a:3", "128k", "-ar:a:3", "48000",
                # Common
                "-pix_fmt", "yuv420p",
                "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
                # HLS — fMP4 (CMAF) segments, 4s, VOD playlist
                "-f", "hls",
                "-hls_time", "4",
                "-hls_list_size", "0",
                "-hls_playlist_type", "vod",
                "-hls_segment_type", "fmp4",
                "-master_pl_name", "master.m3u8",
                "-hls_segment_filename", os.path.join(hls_dir, "stream_%v", "seg_%d.m4s"),
                "-var_stream_map",
                "v:0,a:0,name:360p v:1,a:1,name:540p v:2,a:2,name:720p v:3,a:3,name:1080p",
                os.path.join(hls_dir, "stream_%v", "playlist.m3u8"),
            ]
            _hls_r = subprocess.run(_hls_cmd, capture_output=True, text=True, timeout=600)
            if _hls_r.returncode != 0:
                raise RuntimeError(
                    f"HLS encode failed (rc={_hls_r.returncode}): "
                    f"{(_hls_r.stderr or '')[-1500:]}"
                )

            # Upload all generated files. Key prefix is derived from the
            # main MP4's S3 key: `videos/abc.mp4` → `videos/abc-hls/`.
            base_key, _ = os.path.splitext(_aws_k)
            hls_prefix = f"{base_key}-hls"
            _hls_upload_count = 0
            for root, _, files in os.walk(hls_dir):
                for fname in files:
                    local_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(local_path, hls_dir)
                    s3_key = f"{hls_prefix}/{rel_path}".replace(os.sep, "/")
                    if fname.endswith(".m3u8"):
                        ct = "application/vnd.apple.mpegurl"
                    elif fname.endswith(".m4s"):
                        ct = "video/iso.segment"
                    elif fname.endswith(".mp4"):
                        ct = "video/mp4"
                    else:
                        ct = "application/octet-stream"
                    _aws_s3_client.upload_file(
                        local_path, _aws_b, s3_key,
                        ExtraArgs={"ContentType": ct, "CacheControl": "public, max-age=31536000"},
                    )
                    _hls_upload_count += 1
            if _hls_upload_count == 0:
                raise RuntimeError("HLS encode produced no output files")

            # Compute the master manifest URL. Public_url is required —
            # it's how the iOS app finds the master through CloudFront.
            # If the dispatcher didn't pass one, the render is mis-wired.
            if not input_data.get("public_url"):
                raise RuntimeError(
                    "HLS upload requires input_data['public_url'] to derive "
                    "the manifest URL — dispatcher did not pass it"
                )
            main_no_ext, _ = os.path.splitext(input_data["public_url"])
            hls_url = f"{main_no_ext}-hls/master.m3u8"

            _hls_elapsed = time.time() - _hls_t0
            print(
                f"[hls] generated + uploaded {_hls_upload_count} files in "
                f"{_hls_elapsed:.1f}s → {hls_url}",
                flush=True,
            )
            edit_plan["_hls_manifest_url"] = hls_url
            return hls_url

        # Heartbeat: the post-render fan-out (main MP4 upload + HLS encode +
        # HLS multi-file upload + cover frame upload) was the worst stuck-bar
        # gap in the entire pipeline — the user saw 96% for 30-90 seconds with
        # NO signal that anything was still happening, indistinguishable from
        # a frozen client. HLS encoding alone is 30-50s on a typical clip,
        # then segment uploads add 10-30s. The bar now creeps 96→99 over
        # the estimate (60s default — short videos finish well before, long
        # videos cap at 99 and hold until `complete` fires at 100).
        _upload_hb_stop = _start_progress_heartbeat(
            job_id, "upload", 96, 99,
            [
                "Building HD stream",
                "Building HQ stream",
                "Packaging for fast playback",
                "Uploading to your library",
                "Almost there",
            ],
            app_url,
            duration_estimate_s=60.0,
        )
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as post_executor:
                f_upload = post_executor.submit(_upload_main)
                f_cover  = post_executor.submit(_extract_and_upload_cover)
                f_hls    = post_executor.submit(_upload_hls)
                # Surface every failure — any one of these missing means the
                # render is incomplete. The .result() calls re-raise whatever
                # was caught inside the thread.
                f_upload.result()
                cover_bytes, _ = f_cover.result()
                f_hls.result()
        finally:
            _upload_hb_stop.set()

        if cover_bytes:
            import base64
            cover_frame_b64 = base64.b64encode(cover_bytes).decode()

        # Step 13.5 — Additional format exports (parallelized)
        export_formats   = input_data.get("export_formats") or []
        exported_formats = []

        def _export_and_upload(fmt):
            ar  = str(fmt.get("aspect_ratio") or "").strip()
            url = str(fmt.get("upload_url") or "").strip()
            if not ar or not url:
                return None
            fmt_path = os.path.join(work_dir, f"output_{ar.replace(':','x')}.mp4")
            export_additional_format(output_path, ar, fmt_path)
            _fmt_uploaded = False
            if _s3_client:
                _fb, _fk = _parse_supabase_storage_url(url)
                if _fb and _fk:
                    try:
                        _s3_client.upload_file(fmt_path, _fb, _fk, ExtraArgs={"ContentType": "video/mp4"})
                        _fmt_uploaded = True
                    except Exception:
                        pass
            if not _fmt_uploaded:
                with open(fmt_path, "rb") as f:
                    fmt_resp = requests.put(url, data=f, headers={"Content-Type": "video/mp4"}, timeout=120)
                    fmt_resp.raise_for_status()
            fmt_size = os.path.getsize(fmt_path) / (1024 * 1024)
            print(f"[pipeline] exported {ar} ({fmt_size:.1f}MB) -> uploaded", flush=True)
            return {"aspect_ratio": ar, "size_mb": round(fmt_size, 1)}

        if export_formats:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(export_formats))) as fmt_executor:
                fmt_futures = {fmt_executor.submit(_export_and_upload, fmt): fmt for fmt in export_formats}
                for future in concurrent.futures.as_completed(fmt_futures):
                    try:
                        result = future.result()
                        if result:
                            exported_formats.append(result)
                    except Exception as fmt_err:
                        print(f"[pipeline] format export failed (non-fatal): {fmt_err}", flush=True)

        _timings["upload_export"] = time.time() - t
        _timings["total"] = time.time() - _pipeline_start

        print(f"\n{'='*80}", flush=True)
        print(f"JOB {job_id} COMPLETE — {_timings['total']:.1f}s total", flush=True)
        print(f"  download:    {_timings.get('download', 0):.1f}s", flush=True)
        print(f"  norm+tx+up:  {_timings.get('normalize_transcribe_upload', 0):.1f}s", flush=True)
        print(f"  edit+faces:  {_timings.get('edit_recipe_faces', 0):.1f}s", flush=True)
        print(f"  render:      {_timings.get('render', 0):.1f}s", flush=True)
        print(f"  broll:       {_timings.get('broll', 0):.1f}s", flush=True)
        print(f"  upload+exp:  {_timings.get('upload_export', 0):.1f}s", flush=True)
        print(f"{'='*80}\n", flush=True)

        # ── Structured stage-duration metrics (greppable, stable schema) ──
        # Emit one line per stage for post-hoc aggregation. Format is
        # designed to be trivially parseable by `awk` / log aggregators:
        #   [metric] stage_duration stage=X duration_ms=Y job=Z
        # Plus a final summary line:
        #   [metric] job_complete job=Z total_ms=... download_ms=... etc.
        def _emit_stage_metric(stage_name, key):
            dur_ms = int(_timings.get(key, 0) * 1000)
            print(f"[metric] stage_duration stage={stage_name} duration_ms={dur_ms} job={job_id}", flush=True)

        _emit_stage_metric("download", "download")
        _emit_stage_metric("normalize_transcribe_upload", "normalize_transcribe_upload")
        _emit_stage_metric("edit_recipe_faces", "edit_recipe_faces")
        _emit_stage_metric("render", "render")
        _emit_stage_metric("broll", "broll")
        _emit_stage_metric("upload_export", "upload_export")
        _total_ms = int(_timings["total"] * 1000)
        _download_ms = int(_timings.get("download", 0) * 1000)
        _render_ms = int(_timings.get("render", 0) * 1000)
        print(
            f"[metric] job_complete job={job_id} mode={mode} total_ms={_total_ms} "
            f"download_ms={_download_ms} render_ms={_render_ms}",
            flush=True,
        )

        send_progress(job_id, "complete", 100, "Your video is ready!", app_url)

        # ── Build resolved_broll for persistence ──────────────────────────
        # After a live B-roll pick, fetch_broll_clip mutates each broll_entry in-place
        # with pexels_video_id/file_url/width/height/duration. Extract those into a
        # parallel list keyed by index so the server can store video_jobs.resolved_broll.
        resolved_broll_out = []
        _final_broll = edit_plan.get("broll_clips") or []
        for _i, _br in enumerate(_final_broll):
            if not isinstance(_br, dict):
                continue
            _entry = {
                "index": _i,
                "keyword": _br.get("keyword"),
                "start_word_index": _br.get("start_word_index"),
                "end_word_index": _br.get("end_word_index"),
            }
            for _pk in ("pexels_video_id", "pexels_file_url", "width", "height", "duration", "clip_in", "clip_out"):
                if _pk in _br:
                    _entry[_pk] = _br[_pk]
            # Only persist entries that were actually resolved to a Pexels asset.
            if _entry.get("pexels_video_id") and _entry.get("pexels_file_url"):
                resolved_broll_out.append(_entry)

        # Sanitized recipe for persistence — drops internal _foo fields at the
        # top level and analysis_data (which is persisted separately so we
        # don't double-store it). Inside broll_clips entries we strip ONLY
        # _local_path: it points at a container-local /tmp file that's
        # meaningless after the render. Other internal fields like
        # _start_word_kept / _end_word_kept MUST persist — render_only
        # re-renders rely on them and the validator that recomputes them
        # only runs in full/tweak/reinterpret modes.
        _BROLL_NONPERSISTABLE = {"_local_path"}
        sanitized_recipe = {
            k: v for k, v in edit_plan.items()
            if k != "analysis_data" and not (isinstance(k, str) and k.startswith("_"))
        }
        if isinstance(sanitized_recipe.get("broll_clips"), list):
            sanitized_recipe["broll_clips"] = [
                {kk: vv for kk, vv in _br.items() if kk not in _BROLL_NONPERSISTABLE}
                for _br in sanitized_recipe["broll_clips"] if isinstance(_br, dict)
            ]

        # Per-user style learning: record this render's choices into the user's
        # rolling style profile. Skipped in render_only mode (plan was already
        # persisted and the user had no fresh creative input this round).
        if not _skip_edit_gen:
            update_user_style_profile(user_id, edit_plan, vibe, source_duration)

        result_payload = {
            "status": "success",
            "job_id": job_id,
            "render_time": round(render_elapsed, 1),
            "pipeline_time": round(_timings.get("total", 0), 1),
            "output_size_mb": round(output_size_mb, 1),
            "edit_recipe": sanitized_recipe,
            "cover_frame_timestamp": round(cover_frame_ts, 3),
            "thumbnail_timestamp": round(float(thumbnail_source_ts), 3),
            # ── Re-edit persistence fields ────────────────────────────────
            "transcript": transcript,
            "analysis_data": edit_plan.get("analysis_data") or (_cached_analysis if isinstance(_cached_analysis, dict) else None),
            "resolved_broll": resolved_broll_out,
            "trend_snapshot": trend_used,
            "render_version": RENDER_VERSION,
        }
        if change_summary:
            result_payload["change_summary"] = change_summary
        # Include CDN video URL if available (direct S3 upload path)
        if edit_plan.get("_rendered_video_url"):
            result_payload["video_url"] = edit_plan["_rendered_video_url"]
        if edit_plan.get("_hls_manifest_url"):
            result_payload["hls_manifest_url"] = edit_plan["_hls_manifest_url"]
        if cover_frame_b64:
            result_payload["cover_frame_b64"]  = cover_frame_b64
            result_payload["cover_frame_mime"] = "image/jpeg"
        if exported_formats:
            result_payload["exported_formats"] = exported_formats
        return result_payload

    except Exception as e:
        import traceback
        traceback.print_exc()
        # classify_error now returns structured data with error_code,
        # user_message, retryable, requires_new_video, requires_vibe_change.
        # The legacy `error` field stays for backward compatibility with
        # any existing JS consumer; new clients should read the structured
        # fields instead.
        classified = classify_error(e)
        return {
            "error": classified["user_message"],     # legacy: human text
            "error_code": classified["error_code"],   # NEW: machine code
            "user_message": classified["user_message"],
            "retryable": classified["retryable"],
            "requires_new_video": classified["requires_new_video"],
            "requires_vibe_change": classified["requires_vibe_change"],
            "error_detail": str(e),                   # for support / logs
        }

    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


# Modal entrypoint — handler() is called directly by modal_app.py
# To test locally: python3 handler.py
if __name__ == "__main__":
    print("[handler] Running in local test mode", flush=True)
