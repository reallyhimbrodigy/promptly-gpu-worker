# Modal worker entrypoint
import subprocess
import os
import sys
import ssl
import glob
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

HANDLER_VERSION = "3.1.0"
GEMINI_MODEL = "gemini-3-flash-preview"
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
#   - speed_curve is a nullable list (null == "no speed ramping") instead of
#     a list-or-string union, which simplifies the schema Gemini sees.
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

_CAPTION_STYLES = Literal[
    "HormoziPopIn", "GlitchHighlight", "EmojiPop", "NegativeFlash", "PaperII",
    "Prime", "Prism", "TypewriterReveal", "CinematicLetterpress", "Cove",
    "Dimidium", "EditorialPop", "Gadzhi", "Illuminate", "Lumen",
    "MagazineCutout", "Passage", "Pulse", "Quintessence", "Serif", "StaggerWave",
]
_COLOR_EFFECTS = Literal[
    "CinematicGrade", "BleachBypass", "VintageFilm", "DreamHaze", "ChromaSplit",
    "VignettePulse", "InvertStrike", "CineMono", "GoldenHour", "FilmGrain",
    "Portra", "NeoNoir",
]
_TRANSITION_TYPES = Literal[
    "CardSwipe", "ZoomThrough", "SlideOver", "Stack", "CrossfadeZoom",
    "ShutterFlash", "LightLeak", "StepPush", "NewspaperWipe", "FilmStrip",
    "SceneTitle",
]
_ZOOM_TYPES = Literal[
    "SmoothPush", "SnapReframe", "FocusWindow", "StepZoom", "LetterboxPush",
    "StageZoom", "DepthPull",
]
_MG_TYPES = Literal[
    "LowerThird", "AnnotationArrow", "BRollFrame", "ChartReveal", "ChatThread",
    "ComparisonSplit", "Notification", "ProgressBar", "QuoteCard", "RecordingFrame",
    "StatCard", "StickyNotes", "Toggle", "TornPaper",
    "TweetBubble", "InstagramComment", "IMessageBubble", "TikTokComment",
]
_SEMANTIC_ANCHOR = Literal[
    "upper_third_safe", "center", "lower_third_safe", "left_safe", "right_safe",
]
_TEXT_OVERLAY_VARIANTS = Literal[
    "torn_paper", "sticky_note", "quote_card", "lower_third", "caption_match",
]
_SFX_SOUNDS = Literal[
    "boom", "hit", "drum_roll", "reverse", "ching", "ding", "click",
    "camera_shutter", "sad_trombone", "typing", "whoosh_slow",
    "transition_smooth", "thunder", "pop",
]

class _HookClip(BaseModel):
    source_start: float
    source_end: float

class _CaptionPositionSegment(BaseModel):
    from_seconds: float
    to_seconds: float
    position: Literal["top", "center", "bottom"]

class _ColorPulse(BaseModel):
    peak_at_seconds: float
    attackFrames: int = 3
    holdFrames: int = 4
    releaseFrames: int = 12
    intensity: float = 1.0

class _ColorEffectTiming(BaseModel):
    mode: Literal["persistent", "pulsed"]
    fadeInFrames: Optional[int] = None
    pulses: Optional[List[_ColorPulse]] = None

class _ColorEffect(BaseModel):
    type: _COLOR_EFFECTS
    intensity: float
    timing: _ColorEffectTiming

class _ZoomEvent(BaseModel):
    startMs: int
    durationMs: int
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
    word_indices: List[int]
    type: Literal["punchline", "statement", "question", "reaction", "transition", "revelation"]
    intensity: Literal["high", "medium"]
    duration: float
    zoom_effect: Optional[_ZoomEffect] = None
    color_pulse: bool
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
    name: Optional[str] = None
    title: Optional[str] = None
    accentColor: Optional[str] = None
    theme: Optional[Literal["dark", "light"]] = None
    text: Optional[str] = None
    position: Optional[Literal["top", "center", "bottom"]] = None

class _MotionGraphic(BaseModel):
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

class _SpeedCurveKeypoint(BaseModel):
    t: float
    speed: float

class _RemoveWord(BaseModel):
    # Either a word_index (surgical single-word removal) or a start/end range
    # (continuous span like dead_air). Python validates which set is present.
    word_index: Optional[int] = None
    start: Optional[float] = None
    end: Optional[float] = None
    reason: str

class EditPlan(BaseModel):
    """Structural contract for Gemini's edit-plan output.

    Passed to generate_content as response_json_schema so invalid outputs
    are rejected at decode time. Cross-field semantic constraints (e.g.
    word_indices must reference kept words) still live in Python validators.
    """
    notes: str
    hook_clip: Optional[_HookClip] = None
    thumbnail_timestamp: float
    caption_style: _CAPTION_STYLES
    caption_keywords: List[str]
    caption_position_segments: List[_CaptionPositionSegment]
    color_effect: Optional[_ColorEffect] = None
    audio_denoise: bool
    outro: Literal["none", "fade_black", "fade_white"]
    aspect_ratio: Literal["9:16"]
    pacing: Literal["fast", "medium", "slow"]
    # null == no speed ramping. List == keypoints.
    speed_curve: Optional[List[_SpeedCurveKeypoint]] = None
    emphasis_moments: List[_EmphasisMoment]
    text_overlays: List[_TextOverlay]
    sound_effects: List[_SoundEffect]
    broll_clips: List[_BrollClip]
    transitions: List[_Transition]
    motion_graphics: List[_MotionGraphic]
    remove_words: List[_RemoveWord]


# ── Content Analysis schema (separate pre-pass Gemini call) ──────────────────
# A dedicated analysis call classifies every word before the main edit call.
# Its output drives dynamic Literal enums on the main EditPlan schema:
#   - `remove_words.word_index` enum = CUTTABLE_INDICES (analysis-cuttable)
#   - Every anchor field enum = PROTECTED_INDICES (analysis-safe)
# PROTECTED ∩ CUTTABLE = ∅ by construction, so a main-call anchor physically
# cannot reference a word Gemini later chose to cut.
_ANALYSIS_CLASS = Literal[
    "content",             # substantive content word. Protected (cannot be cut, can anchor).
    "cuttable_filler",     # context-dependent filler (literally, basically, actually, just, like).
    "cuttable_restart",    # part of a phrasal restart ("I said — I said who is he?").
    "cuttable_redundant",  # narratively redundant (word repeats a concept already stated).
    "narrative_peak",      # emphasis candidate / anchor peak. Protected.
]

class _WordAnalysis(BaseModel):
    source_index: int
    classification: _ANALYSIS_CLASS

class ContentAnalysis(BaseModel):
    """Per-word classification for the pre-edit analysis call.

    Exactly one entry per kept Deepgram word (after mechanical pre-pass).
    Narrative peaks and content words become anchor-eligible (PROTECTED);
    cuttable_* entries become cut-eligible (CUTTABLE). The two sets are
    disjoint, making anchor-on-cut collisions structurally impossible in
    the main edit call's schema.
    """
    word_analyses: List[_WordAnalysis]
    tonal_register: Literal[
        "serious", "educational", "motivational",
        "comedic", "dramatic", "casual",
    ]


# ── Mechanical pre-pass (deterministic, no Gemini) ───────────────────────────
_MECHANICAL_FILLERS = {
    "um", "uh", "er", "ah", "hmm", "uhh", "umm", "erm",
    "mhm", "hm", "mm", "mmm", "huh",
}
_STUTTER_SKIP_WORDS = {"the", "a", "an", "that", "to"}
_MECH_DEAD_AIR_THRESHOLD_S = 0.3


def mechanical_cut_pass(deepgram_words):
    """Deterministic cut detection — runs before any LLM call.

    Returns a dict with:
      - `word_cuts`: set of source word indices to cut (fillers, stutters, false starts)
      - `range_cuts`: list of (start_s, end_s) ranges to cut (dead air, non-speech)
      - `reasons`: parallel dict of word_index → reason string

    Handles the 90% of cuts that don't need video context: filler tokens,
    adjacent duplicate words, trailing-dash false starts, dead-air gaps > 0.3s.
    """
    _words = list(deepgram_words or [])
    word_cuts = set()
    reasons = {}
    range_cuts = []

    for idx, w in enumerate(_words):
        word_text = str(w.get("punctuated_word") or w.get("word") or "").strip()
        if not word_text:
            continue
        word_norm = re.sub(r"[^\w']", "", word_text).lower()

        # Filler tokens (exact match)
        if word_norm in _MECHANICAL_FILLERS:
            word_cuts.add(idx)
            reasons[idx] = "filler"
            continue

        # False start (trailing dash on punctuated_word)
        if word_text.rstrip().endswith("-"):
            word_cuts.add(idx)
            reasons[idx] = "false_start"
            continue

        # Adjacent duplicate stutter ("I I", "the the") — remove the first.
        # Skip very common short words where legitimate repetition happens
        # (e.g., "I I think" vs "that that is why").
        if idx + 1 < len(_words):
            next_text = str(_words[idx + 1].get("punctuated_word") or _words[idx + 1].get("word") or "").strip()
            next_norm = re.sub(r"[^\w']", "", next_text).lower()
            if (
                word_norm
                and word_norm == next_norm
                and word_norm not in _STUTTER_SKIP_WORDS
                and len(word_norm) >= 2
            ):
                word_cuts.add(idx)
                reasons[idx] = "stutter"
                continue

    # Dead-air detection (gaps between consecutive word boundaries)
    for i in range(len(_words) - 1):
        end_s = float(_words[i].get("end") or 0)
        next_start_s = float(_words[i + 1].get("start") or 0)
        gap = next_start_s - end_s
        if gap >= _MECH_DEAD_AIR_THRESHOLD_S:
            # Keep a small cushion either side so we don't clip speech
            # (Deepgram rounds; leave 0.04s).
            range_cuts.append((round(end_s + 0.04, 3), round(next_start_s - 0.04, 3)))

    return {
        "word_cuts": word_cuts,
        "range_cuts": range_cuts,
        "reasons": reasons,
    }


def build_constrained_edit_plan_schema(protected_indices, cuttable_indices):
    """Build a JSON schema for the main edit call with disjoint index enums.

    Starts from EditPlan.model_json_schema() and injects `enum` constraints
    on every field that references a word index:
      - `_RemoveWord.word_index` → enum = cuttable_indices
      - `_EmphasisMoment.word_indices[*]` → enum = protected_indices
      - `_TextOverlay.start_word_index` → enum = protected_indices
      - `_MotionGraphic.{start,end}_word_index` → enum = protected_indices
      - `_SoundEffect.word_index` → enum = protected_indices
      - `_Transition.after_word_index` → enum = protected_indices
      - `_BrollClip.{start,end}_word_index` → enum = protected_indices

    By making PROTECTED ∩ CUTTABLE = ∅ in the classification pass, the
    decoder is structurally incapable of emitting a JSON where an anchor
    field and a remove_words entry reference the same word index.
    """
    import copy as _copy_mod
    schema = _copy_mod.deepcopy(EditPlan.model_json_schema())
    defs = schema.get("$defs") or schema.get("definitions") or {}

    _prot = sorted(int(i) for i in (protected_indices or ()))
    _cut = sorted(int(i) for i in (cuttable_indices or ()))

    def _apply_enum(field_schema, indices):
        if not indices:
            # Empty enum — JSON Schema requires at least one value. Emit a
            # sentinel -1 that Gemini will simply never choose (no valid
            # index; field goes empty or omitted).
            indices = [-1]
        field_schema["type"] = "integer"
        field_schema["enum"] = list(indices)
        # Drop minimum/maximum/format that Pydantic may have emitted — enum
        # is the complete constraint.
        for k in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "format"):
            field_schema.pop(k, None)

    def _constrain(def_name, field_name, indices, list_item=False):
        if def_name not in defs:
            return
        props = defs[def_name].get("properties") or {}
        if field_name not in props:
            return
        field = props[field_name]
        if list_item:
            items = field.get("items")
            if isinstance(items, dict):
                _apply_enum(items, indices)
            return
        # anyOf wrapping (Optional types) — find the int branch
        if "anyOf" in field:
            for branch in field["anyOf"]:
                if isinstance(branch, dict) and branch.get("type") == "integer":
                    _apply_enum(branch, indices)
                    return
        _apply_enum(field, indices)

    # remove_words.word_index → CUTTABLE
    _constrain("_RemoveWord", "word_index", _cut)

    # All anchor fields → PROTECTED
    _constrain("_EmphasisMoment", "word_indices", _prot, list_item=True)
    _constrain("_TextOverlay", "start_word_index", _prot)
    _constrain("_MotionGraphic", "start_word_index", _prot)
    _constrain("_MotionGraphic", "end_word_index", _prot)
    _constrain("_SoundEffect", "word_index", _prot)
    _constrain("_Transition", "after_word_index", _prot)
    _constrain("_BrollClip", "start_word_index", _prot)
    _constrain("_BrollClip", "end_word_index", _prot)

    return schema

print(f"[startup] Python {sys.version}", flush=True)
print(f"[startup] handler version: {HANDLER_VERSION}", flush=True)
print(f"[startup] Gemini model: {GEMINI_MODEL}", flush=True)
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

def _get_genai_client():
    """Get or create the Gemini API client (lazy init with API key from env)."""
    global _genai_client
    if _genai_client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _genai_client = genai_client_mod.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=120_000),
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
        multipart_chunksize=16 * 1024 * 1024,
        max_concurrency=32,
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

# ── GPU / NVENC detection ─────────────────────────────────────────────────────
_HAS_NVENC = False
_HAS_HWACCEL = False  # NVDEC hardware decoding
try:
    # Print GPU info for diagnostics
    _smi = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=5,
    )
    if _smi.returncode == 0:
        print(f"[startup] GPU: {_smi.stdout.strip()}", flush=True)
    else:
        print(f"[startup] nvidia-smi failed: {_smi.stderr.strip()[:200]}", flush=True)

    # Remove CUDA stub/compat libraries that intercept dlopen before Modal's real drivers
    # The CUDA 12.6 base image ships libcuda.so.560.x in /usr/local/cuda — must be removed
    # so FFmpeg picks up the real Modal-mounted driver (580.x) from /usr/local/nvidia/
    for _stub_dir in ["/usr/local/cuda/lib64/stubs", "/usr/local/cuda/targets/x86_64-linux/lib/stubs",
                      "/usr/local/cuda/compat"]:
        if os.path.isdir(_stub_dir):
            for _sf in os.listdir(_stub_dir):
                if "encode" in _sf.lower() or "cuda.so" in _sf.lower():
                    try:
                        os.remove(os.path.join(_stub_dir, _sf))
                    except Exception:
                        pass
    # Also remove compat libcuda from the main CUDA lib dir
    for _cuda_dir in ["/usr/local/cuda/lib64", "/usr/local/cuda/targets/x86_64-linux/lib"]:
        if os.path.isdir(_cuda_dir):
            for _sf in os.listdir(_cuda_dir):
                if _sf.startswith("libcuda.so"):
                    try:
                        os.remove(os.path.join(_cuda_dir, _sf))
                    except Exception:
                        pass

    # Modal mounts NVIDIA drivers at runtime — real driver is in /usr/local/nvidia/
    # CRITICAL: NVIDIA dirs must come FIRST so the real driver (580.x) is found before any stale libs
    _nvidia_lib_dirs = []
    for _search_dir in ["/usr/local/nvidia/lib", "/usr/local/nvidia/lib64",
                        "/usr/lib/x86_64-linux-gnu", "/usr/lib64", "/usr/local/cuda/lib64"]:
        if os.path.isdir(_search_dir):
            _nvidia_lib_dirs.append(_search_dir)
    if _nvidia_lib_dirs:
        _existing_ldpath = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = ":".join(_nvidia_lib_dirs) + (":" + _existing_ldpath if _existing_ldpath else "")
        print(f"[startup] LD_LIBRARY_PATH: {os.environ['LD_LIBRARY_PATH'][:200]}", flush=True)

    # Create soname symlinks for NVIDIA libs (Modal mounts versioned .so but not symlinks)
    for _lib_dir in _nvidia_lib_dirs:
        try:
            for _f in os.listdir(_lib_dir):
                if _f.startswith("libnvidia-") and ".so." in _f and not _f.endswith(".so.1"):
                    _base = _f.split(".so.")[0]
                    _target = os.path.join(_lib_dir, _f)
                    for _suf in [".so.1", ".so"]:
                        _sym = os.path.join(_lib_dir, f"{_base}{_suf}")
                        if not os.path.exists(_sym):
                            try:
                                os.symlink(_target, _sym)
                            except Exception:
                                pass
                if _f.startswith("libcuda.so.") and not _f.endswith(".so.1"):
                    _target = os.path.join(_lib_dir, _f)
                    for _sym_name in ["libcuda.so.1", "libcuda.so"]:
                        _sym = os.path.join(_lib_dir, _sym_name)
                        if not os.path.exists(_sym):
                            try:
                                os.symlink(_target, _sym)
                            except Exception:
                                pass
        except Exception:
            pass
    subprocess.run(["ldconfig"], capture_output=True, timeout=5)

    # L40S has NVENC (8th gen Ada) — detect and enable automatically.
    # H100/A100 do NOT have NVENC (encode ASIC physically absent).
    _nvenc_check = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True, text=True, timeout=5,
    )
    if "h264_nvenc" in (_nvenc_check.stdout or ""):
        import tempfile as _tmpmod
        _nvenc_tmp = os.path.join(_tmpmod.gettempdir(), "_nvenc_test.mp4")
        _gpu_test = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:s=1920x1080:d=0.1:r=30",
             "-c:v", "h264_nvenc", "-preset", "p1", _nvenc_tmp],
            capture_output=True, text=True, timeout=10,
            env={**os.environ},
        )
        try:
            os.remove(_nvenc_tmp)
        except Exception:
            pass
        if _gpu_test.returncode == 0:
            _HAS_NVENC = True
            print("[startup] NVENC GPU encoder: AVAILABLE", flush=True)
        else:
            print(f"[startup] NVENC not available (H100/A100 lack encode ASIC) — using CPU encoder", flush=True)
    else:
        print("[startup] NVENC not in FFmpeg build — using CPU encoder", flush=True)

    # Test NVDEC hardware decoding (works on almost all NVIDIA GPUs even if NVENC fails)
    _hwaccel_test = subprocess.run(
        ["ffmpeg", "-y", "-hwaccel", "cuda", "-f", "lavfi", "-i", "color=black:s=64x64:d=0.1",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=10,
    )
    if _hwaccel_test.returncode == 0:
        _HAS_HWACCEL = True
        print("[startup] CUDA hwaccel decode: AVAILABLE", flush=True)
    else:
        print("[startup] CUDA hwaccel decode: not available", flush=True)
except Exception as _e:
    print(f"[startup] GPU check failed: {_e} — using CPU", flush=True)


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
            # CQ 18 = visually lossless on mobile. Higher bitrate ceiling (15M)
            # ensures complex scenes (fast motion, particle effects) don't starve.
            # H100 NVENC encodes 1080p @ 500+ fps — encoding is never the bottleneck.
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq",
                    "-rc", "vbr", "-cq", "18", "-b:v", "0",
                    "-maxrate", "15M", "-bufsize", "30M",
                    "-spatial-aq", "1", "-temporal-aq", "1",
                    "-b_ref_mode", "middle"]
    else:
        # H100 has no NVENC hardware — CPU encoding is the only option.
        # threads=0 lets x264 auto-detect (use all cores). Pass an explicit
        # value when running many ffmpeg processes in parallel — otherwise
        # each process tries to claim every core, producing massive
        # context-switch contention (60 processes × 80 threads each =
        # 4800 threads competing for 80 cores, render time blows up).
        # -fps_mode passthrough: honor filter graph PTS exactly. Without
        # this, libx264 forces CFR by duplicating/dropping frames to fit
        # the output frame rate, which re-introduces the quantization
        # drift the speed-warped setpts was supposed to eliminate.
        _x264_threads = f"threads={threads}"
        if quality == "lossless":
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                    "-fps_mode", "passthrough",
                    "-x264-params", _x264_threads]
        else:
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                    "-maxrate", "15M", "-bufsize", "30M",
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

Follow these patterns for speed ramping, pacing, and cuts only.

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
        _items = sorted(d.items(), key=lambda kv: (-float(kv[1] or 0), str(kv[0])))
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

These are the aesthetic patterns this user has accepted over time. Recency-
weighted counts — higher numbers = more frequent / more recent picks.

  Caption styles:         {_caps}
  Transitions:            {_trans}
  Pacing:                 {_pacing}
  Color effects:          {_color}
  Text overlay variants:  {_tov}
  Motion graphics:        {_mgs}
  Zoom types:             {_zooms}
  Avg emphasis per 30s:   {_avg_em:.1f}
  Avg MGs per video:      {_avg_mg:.1f}
  Recent vibe prompts:    {_rv_tail}

GUIDANCE:
- Lean toward the user's top picks when the current vibe is compatible.
- If the current vibe EXPLICITLY contradicts (e.g. "completely different look"),
  ignore history and follow the vibe.
- When two choices are equally defensible, pick the one the user has picked
  before — it's the signal that their aesthetic has converged.
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
            return {k: round(float(v or 0) * _USER_STYLE_RECENCY_DECAY, 3) for k, v in d.items()}

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

        _color_effects = _decayed("color_effects")
        _ce = edit_plan.get("color_effect")
        _bump(_color_effects, (_ce.get("type") if isinstance(_ce, dict) else "null"))

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
        print(f"[dense-face] FFmpeg extraction failed, falling back to OpenCV: {_extract_cmd.stderr[-200:]}", flush=True)
        # Fallback: use basic OpenCV approach
        return _detect_face_positions_dense_fallback(video_path, every_n_frames)

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


def _detect_face_positions_dense_fallback(video_path, every_n_frames=5):
    """Fallback face detection using OpenCV sequential read (slower, no FFmpeg)."""
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1080)
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1920)
    center_x, center_y = frame_w // 2, frame_h // 2
    net = cv2.dnn.readNetFromCaffe(
        "/models/face_detector/deploy.prototxt",
        "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel",
    )
    last_cx, last_cy = center_x, center_y
    positions = []
    frame_idx = 0
    while True:
        if frame_idx % every_n_frames == 0:
            ret, frame = cap.read()
            if not ret:
                break
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0), swapRB=False, crop=False)
            net.setInput(blob)
            detections = net.forward()
            found, best_cx, best_cy, best_conf, best_area = False, center_x, center_y, 0.0, 0
            for di in range(detections.shape[2]):
                conf = float(detections[0, 0, di, 2])
                if conf < 0.5:
                    continue
                x1, y1, x2, y2 = int(detections[0,0,di,3]*w), int(detections[0,0,di,4]*h), int(detections[0,0,di,5]*w), int(detections[0,0,di,6]*h)
                area = (x2-x1)*(y2-y1)
                if conf > best_conf or area > best_area:
                    best_conf, best_area, best_cx, best_cy, found = conf, area, (x1+x2)//2, (y1+y2)//2, True
            if found:
                last_cx, last_cy = best_cx, best_cy
            positions.append({"t": round(frame_idx/fps, 4), "cx": float(best_cx if found else last_cx), "cy": float(best_cy if found else last_cy), "found": found, "confidence": round(best_conf, 4) if found else 0.0})
        else:
            if not cap.grab():
                break
        frame_idx += 1
    cap.release()
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

def detect_shot_changes(source_path, threshold=0.30):
    """Detect hard shot changes in the source video via ffmpeg's `scdet`
    (scene change detect) filter.

    `threshold` is the normalized scene score threshold (0.0 - 1.0).
    scdet emits a metadata entry for every frame whose scene_score exceeds
    the threshold. We parse stderr for `lavfi.scene_score` + `pts_time`
    pairs and return the source-time timestamps of detected cuts.
    """
    cmd = [
        "ffmpeg", "-i", source_path, "-an",
        "-vf", f"scdet=threshold={threshold}:sc_pass=1,metadata=print:file=-",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    # scdet + metadata=print:file=- writes metadata lines to stdout.
    # Each detection produces blocks like:
    #   frame:123 pts:41000 pts_time:1.366
    #   lavfi.scdet.mafd=...
    #   lavfi.scdet.score=0.412
    changes = []
    _pending_t = None
    for _line in (proc.stdout or "").splitlines():
        _line = _line.strip()
        if _line.startswith("frame:") and "pts_time:" in _line:
            _tok = _line.split("pts_time:")[-1].split()[0]
            try:
                _pending_t = float(_tok)
            except ValueError:
                _pending_t = None
        elif "lavfi.scd.score" in _line or "lavfi.scdet.score" in _line:
            if _pending_t is not None:
                changes.append(round(_pending_t, 3))
                _pending_t = None
    # Some ffmpeg builds emit score=... on its own metadata line without a
    # prior frame: header — in that case, fall back to parsing pts_time from
    # stderr (scdet also logs every flagged frame to stderr with [Parsed_scdet_0]).
    if not changes and proc.stderr:
        for _line in proc.stderr.splitlines():
            if "Parsed_scdet" in _line and "pts_time:" in _line:
                _tok = _line.split("pts_time:")[-1].split()[0]
                try:
                    changes.append(round(float(_tok), 3))
                except ValueError:
                    continue
    # De-duplicate and sort.
    changes = sorted(set(changes))
    print(f"[shot-changes] Detected {len(changes)} cuts (threshold={threshold})", flush=True)
    return changes


# ─── DEEPGRAM TRANSCRIPTION ───────────────────────────────────────────────────


def _deepgram_options():
    return PrerecordedOptions(
        model="nova-3", detect_language=True,
        smart_format=True, utterances=True, punctuate=True, diarize=True,
    )


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
    # speaker assignments when available.
    raw_utterances = getattr(resp.results, "utterances", None) or []
    if raw_utterances:
        utt_count = 0
        for utt in raw_utterances:
            utt_start = float(getattr(utt, "start", 0))
            utt_end = float(getattr(utt, "end", 0))
            utt_speaker = int(getattr(utt, "speaker", 0))
            for w in words:
                if w["start"] >= utt_start - 0.05 and w["end"] <= utt_end + 0.05:
                    w["speaker"] = utt_speaker
            utt_count += 1
        print(f"[deepgram] Applied {utt_count} utterance-level speaker labels", flush=True)

    speaker_ids = set(w["speaker"] for w in words)
    if len(speaker_ids) > 1:
        print(f"[deepgram] Detected {len(speaker_ids)} speakers", flush=True)
    print(f"[deepgram] Transcribed {len(words)} words", flush=True)
    return {"text": alt.transcript or "", "words": words}


def _deepgram_is_retriable_error(msg):
    """Classify a Deepgram error message as retriable (rate limits, 5xx, network)."""
    m = str(msg)
    return (
        "429" in m or "rate" in m.lower() or
        "500" in m or "502" in m or "503" in m or "504" in m or
        "timeout" in m.lower() or "connection" in m.lower() or
        "temporarily" in m.lower()
    )


def transcribe_audio_url(video_url):
    """
    URL-based Deepgram transcription. Deepgram's servers fetch the media
    directly — runs in parallel with the Modal worker's own S3 download,
    so the transcript is ready (or close to it) the moment the file
    lands locally. Saves 3-6s of serial work vs transcribe_audio.

    3-attempt exponential backoff (1s/2s/4s) on rate limits + 5xx + network.
    Returns None on final failure; caller falls back to file-based Deepgram.
    """
    if DeepgramClient is None or PrerecordedOptions is None:
        print("[pipeline] transcription skipped: deepgram not available", flush=True)
        return {"text": "", "words": []}
    dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
    print(f"[deepgram] URL-based transcribe against {video_url[:80]}...", flush=True)
    _t0 = time.time()
    for attempt in range(3):
        try:
            resp = dg.listen.prerecorded.v("1").transcribe_url({"url": video_url}, _deepgram_options())
            result = _parse_deepgram_response(resp)
            print(f"[metric] stage_duration stage=transcribe_url duration_ms={int((time.time()-_t0)*1000)} attempt={attempt+1}", flush=True)
            return result
        except Exception as e:
            if attempt < 2 and _deepgram_is_retriable_error(e):
                backoff = 2 ** attempt
                print(f"[deepgram] URL attempt {attempt+1} retriable ({str(e)[:120]}) — retry in {backoff}s", flush=True)
                time.sleep(backoff)
                continue
            print(f"[deepgram] URL transcription failed (attempt {attempt+1}): {str(e)[:200]} — falling back", flush=True)
            return None
    return None


def transcribe_audio(source_path):
    """File-based Deepgram. Fallback when URL-based path fails. Same 3-attempt
    backoff (1s/2s/4s) on retriable errors so rate-limit spikes don't crash
    the pipeline."""
    if DeepgramClient is None or PrerecordedOptions is None:
        print("[pipeline] transcription skipped: deepgram not available", flush=True)
        return {"text": "", "words": []}
    dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
    with open(source_path, "rb") as f:
        audio_bytes = f.read()
    print(f"[deepgram] Sending {len(audio_bytes) / 1024:.0f}KB audio", flush=True)
    options = _deepgram_options()
    _t0 = time.time()
    last_err = None
    for attempt in range(3):
        try:
            resp = dg.listen.prerecorded.v("1").transcribe_file({"buffer": audio_bytes}, options)
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

ALWAYS_FILLER = {"um","uh","uhh","uhm","umm","erm","er","hmm","hm","mm","mmm","mhm","ah","ahh","huh"}
CONTEXT_FILLER = {"like","right","so","basically","literally","actually","honestly","obviously","just","really"}
MULTI_WORD_FILLER = [["you","know"],["i","mean"],["kind","of"],["sort","of"]]


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

    # Parse peak and RMS from astats output
    peak_matches = re.findall(r"lavfi\.astats\.Overall\.Peak_level=([-\d.]+)", stderr)
    rms_matches = re.findall(r"lavfi\.astats\.Overall\.RMS_level=([-\d.]+)", stderr)
    noise_matches = re.findall(r"lavfi\.astats\.Overall\.Noise_floor=([-\d.]+)", stderr)
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

    Returns (face_visibility, speaker_positions, off_center, shot_scale):
      face_visibility  — list of {"from_s": float, "to_s": float, "visible": bool}
                         contiguous non-overlapping segments over [0, duration]
                         bucketed at 0.5s granularity.
      speaker_positions — dict[int spk_id] → {"avg_cx": float (px),
                         "side": "left"|"center"|"right", "samples": int}
      off_center       — bool: median face cx deviates from canvas-center 540
                         by more than 100px (flag Gemini to avoid aggressive zoom)
      shot_scale       — dict: {"median_w": float, "median_h": float,
                         "label": "close_up"|"medium"|"wide"|"unknown"} —
                         tells Gemini how tight the framing is, which gates
                         appropriate zoom types and intensities.
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

    return face_visibility, speaker_positions, off_center, shot_scale


def build_gemini_edit_prompt(
    vibe, duration, trend_context=None,
    shot_changes=None, vocal_emphasis=None, source_loudness=None,
    face_visibility=None, speaker_positions=None, off_center=False,
    shot_scale=None, user_style_profile=None,
):
    """
    Gemini prompt for the Remotion-primary pipeline.

    Philosophy: every visual decision is Gemini's. The renderer is a pure
    executor — it does not clamp, buffer, repair, mutate, or substitute
    defaults. If Gemini emits something invalid, the render fails — the
    prompt is the single point of intelligence.

    Signals fed alongside the video:
      - Deepgram word timestamps with speaker IDs (injected by generate_edit_gemini)
      - shot_changes       — source-time seconds where the footage cuts
      - vocal_emphasis     — source-time RMS peaks (loud word hits)
      - source_loudness    — peak / rms / noise_floor dB stats
      - face_visibility    — 0.5s-bucketed face-detected timeline
      - speaker_positions  — per-speaker median face cx + left/center/right side
      - off_center         — global median cx >100px off canvas-center
      - shot_scale         — median face bbox → wide / medium / close_up / extreme_close_up
      - user_style_profile — this user's preferred styles across their past videos
      - Trend style guide (Apify-scraped weekly)
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
            "Aggressive zoom (>1.25x) will crop the speaker out. Prefer SmoothPush/StepZoom "
            "at 1.10–1.18x, or no zoom. Favor `left_safe`/`right_safe` overlays on the side "
            "OPPOSITE the speaker's median position.\n"
        )

    # Shot-scale block — tells Gemini how tight the framing is so zoom choices
    # are realistic. Zoom types each have a preferred scale range.
    _ss = dict(shot_scale or {})
    _ss_label = _ss.get("label", "unknown")
    _ss_w = _ss.get("median_w", 0)
    _ss_h = _ss.get("median_h", 0)
    _ss_guide = {
        "wide": "Subject is far from camera. SnapReframe will look absurd — the face doesn't fill enough of the frame to justify a hard snap. Prefer SmoothPush, StepZoom at 1.08–1.15x, or DepthPull for atmosphere. Avoid zoom entirely if the framing is already telling the story.",
        "medium": "Head + shoulders framing. SnapReframe and StepZoom work well at 1.12–1.20x. Avoid pushes above 1.25x — the face becomes too tight.",
        "close_up": "Head fills the center third. SnapReframe shines here at 1.10–1.18x. StageZoom / FocusWindow are on the table. Keep scale ≤1.20x — any tighter and eyes/chin leave frame.",
        "extreme_close_up": "Head dominates the frame. Almost any zoom beyond 1.10x crops facial features out. Prefer subtle StepZoom at 1.05–1.10x, or skip zoom entirely.",
        "unknown": "No face detected — shot-scale can't be inferred. Use conservative zooms (≤1.15x) or none.",
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

  These are the exact moments where the FOOTAGE already cuts. Use them:
    - Place `transitions` ON or within 0.2s of a shot change — that's where
      the viewer's eye expects a visual boundary.
    - `SceneTitle` transitions go at shot changes that mark a topic shift.
    - Emphasis moments often coincide with shot changes (reveals land
      visually when the shot cuts at the same time).

VOCAL EMPHASIS PEAKS (source seconds, score 0-1)
  {_vocal_display}

  These are moments where the speaker's voice spikes in prominence — loud
  words, pitch peaks, punches. Use as PRIMARY anchors for:
    - zoom_effect events (SnapReframe lands ON a vocal peak)
    - emphasis_moments.t (pick the peak, then map word_indices to it)
    - color pulse peak_at_seconds (hit at the vocal prominence)

FACE VISIBILITY (source-seconds ranges; yes = face detected in 0.5s bucket)
  {_fv_display}

  Use this to choose overlays that make sense with what's on screen. When
  `visible=NO` for a window, the viewer is looking at b-roll, a product
  shot, text, or scenery — lean into that (e.g., use TornPaper/QuoteCard
  over scenery, ChartReveal/StatCard over a product shot).

SPEAKER POSITIONS (where each speaker sits in frame, by diarization + face detect)
  {_sp_display}

  Use to place side overlays OPPOSITE the speaker:
    - spk on `left`   → `right_safe` for overlays during their words
    - spk on `right`  → `left_safe` for overlays during their words
    - spk on `center` → `upper_third_safe` / `lower_third_safe`
  For `lower_third` text overlays (speaker-attribution), emit ONE per distinct
  speaker at their first on-camera appearance — the diarization IDs are stable.
  {_off_center_line}{_shot_scale_block}"""

    # SYSTEM INSTRUCTION — stable content. No per-video interpolation (vibe,
    # duration, signals) lives here so the prefix stays byte-identical across
    # calls and implicit prompt caching can take effect. Per-video data is
    # injected via the USER message below.
    system_instruction = f"""You are a professional short-form video editor working on a 1080x1920 (9:16) vertical video for TikTok, Instagram Reels, and YouTube Shorts. You watch the full video at 5 frames per second — you see every shot, every face, every gesture, every on-screen element. You hear every word.

Your job: produce an edit plan that looks professionally crafted — every cut, every caption move, every zoom, every motion graphic has a narrative reason. Not random. Not accidental. Intentional.

=== CONTRACT ===

The pipeline enforces these rules with strict validators. Output that violates any rule is rejected.

1. POSITIONS ARE SEMANTIC ZONES. Use the named zones from the vocabulary (`upper_third_safe`, `center`, `lower_third_safe`, `left_safe`, `right_safe`). Pixel coordinates are not accepted.
2. TIMES ARE SOURCE SECONDS. Every timestamp you emit references the source video's timeline — match values directly from the injected transcript, shot_changes, and vocal_emphasis arrays. Frame numbers are not accepted.
3. EVERY TEXT OVERLAY HAS A VARIANT + ITS REQUIRED PROPS. The `variant` field chooses which visual treatment; each variant has a specific set of required props documented in the TEXT OVERLAYS section.
4. CAPTIONS COVER THE FULL DURATION. `caption_position_segments` spans the entire source duration (stated in the user message) with no gaps or overlaps. First segment starts at 0.0, last ends at the source duration. Every interior boundary lands on a real word boundary from the injected transcript (rounded to 2 decimals — copy the exact value).
5. Z-ORDER YIELDS TO MOTION GRAPHICS. When a motion_graphic occupies the lower half of the frame across window [t1, t2], set `caption_position_segments` to `top` across that same window. Captions and MGs do not share vertical space.
6. COLOR EFFECT MODE CONSISTENCY:
   - `InvertStrike` requires `timing.mode = "pulsed"` with at least one pulse.
   - If any `emphasis_moment.color_pulse = true`, `color_effect` is non-null and `timing.mode = "pulsed"`.
7. NON-OVERLAP WINDOWS:
   - Text overlays do not overlap each other in time.
   - Text overlays do not overlap any emphasis_moment's motion_graphic window.
   - High-intensity emphasis moments are spaced ≥2.5s apart.
8. ONE ZOOM PER KEPT-SOURCE CLIP. At most one emphasis_moment carries a zoom_effect within any single kept-source clip (the source range between your removed-words boundaries). When you want multiple zoom beats close together, stack their events onto a single emphasis_moment's `zoom_effect.events` array.
9. MOTION GRAPHIC ANCHORS ARE ABSOLUTE ZONES. Every `motion_graphics[i].anchor` and `emphasis_moments[i].motion_graphic.anchor` is one of the 5 absolute zones — MGs don't follow the speaker's face.
10. ANCHORS ARE KEPT WORDS — STRUCTURALLY ENFORCED. Every index you emit in any anchor field (`emphasis_moments[i].word_indices`, `sound_effects[i].word_index`, `text_overlays[i].start_word_index`, `motion_graphics[i].start_word_index` / `end_word_index`, `broll_clips[i].start_word_index` / `end_word_index`, `transitions[i].after_word_index`) is schema-constrained to the kept-word enum. The pipeline derives timestamps from these word anchors — there's no free-form `t` for you to emit.
11. EXPLICIT NULLS. If an emphasis moment has no zoom, emit `"zoom_effect": null` — no downstream defaults fill gaps.

=== SAFE ZONES (1080x1920 canvas) ===

Body zone (all visible elements live here):
  x ∈ [60, 1020]   y ∈ [108, 1812]

Platform UI overlays you must AVOID:
  y < 108              — top status / camera notch area
  y > 1600             — bottom caption drawer, like/share rail
  x > 960              — right engagement rail (like, comment, share, bookmark)

All semantic zones below pre-compute to inside the body zone. Use them and you are safe by construction.

=== SEMANTIC ZONE VOCABULARY (motion_graphics anchors) ===

The five absolute zones (per Rule #9). Pick based on what's already on screen and where the speaker sits.

  "upper_third_safe" — top band, above the speaker. Use for: title cards, hook text, stats appearing above the subject.
  "center"           — dead center. Use for: dramatic emphasis, full-screen moments, reveals.
  "lower_third_safe" — lower-third band, just above the TikTok/IG UI rail. Use for: LowerThird name/title cards, tweet bubbles that frame at the bottom.
  "left_safe"        — left edge, vertically centered. Use when the speaker is on the RIGHT half of the frame (put the overlay OPPOSITE the speaker).
  "right_safe"       — right edge, vertically centered. Use when the speaker is on the LEFT half of the frame.

DECISION — which anchor:
- Speaker on camera-left → `right_safe` for overlays (see SPEAKER POSITIONS signal).
- Speaker on camera-right → `left_safe` for overlays.
- Speaker centered or off-camera → `upper_third_safe` / `lower_third_safe` / `center`.
- LowerThird (speaker-attribution MG or text_overlay) → always `lower_third_safe`.
- Notification stacks / top title cards → `upper_third_safe`.

=== CAPTIONS — WORD-BY-WORD RUNNING SUBTITLES ===

ONE style for the whole video. POSITION can change per segment.

caption_style — pick EXACTLY ONE from 21 styles:

 1. "HormoziPopIn"         — Bold uppercase words spring-pop one at a time. Highlight words scale up with custom colors. Thick black stroke.
                              Best for: Motivational clips, business advice, podcast highlights.
 2. "GlitchHighlight"      — Montserrat body with highlighted words that explode into RGB chromatic aberration. Scanlines, slice displacement, flicker, then glow.
                              Best for: Tech, gaming, edgy reels, cyberpunk aesthetic.
 3. "EmojiPop"             — Words appear with automatic Lottie emoji animations. Active word gets color highlight. 48 built-in emoji mappings.
                              Best for: Fun/casual content, storytelling, social media clips.
 4. "NegativeFlash"        — Playfair Display serif. Keywords trigger a negative/inverted color flash with warm tint and glow, then settle into a distinctive color.
                              Best for: Bold statements, dramatic reveals, cinematic reels.
 5. "PaperII"              — Lora serif. Words transition from dim to bright as spoken. Strip-based stacking, heavy shadow.
                              Best for: Storytelling, narrative, poetry, journal-style.
 6. "Prime"                — Two-tier system: Inter body, special words break out into oversized italic Playfair Display on their own line.
                              Best for: Aspirational content, premium branding, lifestyle.
 7. "Prism"                — Playfair Display with keywords that dramatically scale up. Solo keywords on a line get 2.2x. Shares the NegativeFlash color system.
                              Best for: Quote highlights, single-word emphasis, editorial.
 8. "TypewriterReveal"     — Character-by-character typewriter in Space Mono. Blinking cursor. Three schemes: classic, terminal, amber.
                              Best for: Tech/coding, thoughtful narration, documentary.
 9. "CinematicLetterpress" — Words emerge from blur into focus — cinematic "focus pull." Cormorant Garamond, light weight, wide letter-spacing.
                              Best for: Documentary, film-style intros, art house.
10. "Cove"                 — Bold Montserrat base, special words switch to oversized italic Playfair Display with warm ethereal glow. ~2x scale contrast.
                              Best for: Premium/luxury, brand storytelling, wellness.
11. "Dimidium"             — Heavy Montserrat, thick black stroke (14px), staggered left-aligned lines. Subtle floating sine-wave animation.
                              Best for: Street style, urban, bold statements, hip-hop.
12. "EditorialPop"         — All Playfair Display — keywords scale to 1.7x bold italic, body stays light. Two-line staggered reveal.
                              Best for: Magazine-style, fashion, interview quotes.
13. "Gadzhi"               — Montserrat uppercase, words slide up with cubic ease-out. Gray to final color transition. Keywords land in gold.
                              Best for: Business/hustle, agency reels, SMMA aesthetic.
14. "Illuminate"           — Playfair Display with diagonal light sweep. Keywords keep a warm lingering glow. Cinematic spotlight.
                              Best for: Cinematic narration, atmospheric storytelling.
15. "Lumen"                — Montserrat body, keywords switch to Playfair with amber glow and gold underline sweep. Shine words get brightness flash.
                              Best for: Warm inspirational, golden-hour aesthetics.
16. "MagazineCutout"       — Individually cut-out paper pieces with cream background, random rotation, size variation. Collage aesthetic.
                              Best for: Creative/art, collage, DIY/craft, zine-style.
17. "Passage"              — Cormorant Garamond serif. Keywords expand letter-spacing on reveal and switch to italic warm gold.
                              Best for: Literary content, book quotes, long-form storytelling.
18. "Pulse"                — Two-slot paired display — words appear in pairs that fade in together. Keywords get cyan accent.
                              Best for: Music, rhythmic narration, fast dialogue, lyric videos.
19. "Quintessence"         — Single word at a time, centered, Playfair Display with dramatic vertical stretch (scaleY). Gold text, spring entrance.
                              Best for: Single-word emphasis, dramatic pauses, poetry.
20. "Serif"                — DM Serif Display body with keywords that scale up (1.35x) in italic with blue accent.
                              Best for: Premium editorial, interview quotes, brand messaging.
21. "StaggerWave"          — Montserrat uppercase, staggered spring entrance with sine-wave float. Active word lights up yellow.
                              Best for: Dynamic content, workout/fitness, energetic reels.

DECISION MATRIX — caption_style by content:
  business, hustle, agency, motivational         → HormoziPopIn or Gadzhi
  interview, podcast, thoughtful, calm           → Serif or Cove
  gaming, tech, cyberpunk, glitch                → GlitchHighlight or TypewriterReveal
  cinematic, documentary, dramatic               → CinematicLetterpress or NegativeFlash
  aesthetic, lifestyle, travel, minimal          → Cove or Passage
  creative, artistic, collage, music             → MagazineCutout or EmojiPop
  luxury, fashion, premium                       → Prime or Passage
  editorial, magazine, interview quote           → EditorialPop or Prism
  storytelling, narrative, POV                   → PaperII or Cove
  workout, fitness, energetic                    → StaggerWave or HormoziPopIn
  music, rhythmic, lyric-driven                  → Pulse or Prism
  unsure                                          → HormoziPopIn

caption_keywords — REQUIRED. 2-6 short words that matter narratively (punchline nouns, reveal names, emotional verbs). Lowercase, no punctuation.

caption_position_segments — REQUIRED. Array covering the full source duration (stated in the user message) with no gaps or overlaps.
  Format: [{{"from_seconds": float, "to_seconds": float, "position": "top" | "center" | "bottom"}}, ...]

  Baseline: one segment at "bottom" covering the whole duration.
  MOVE captions when:
    - A motion_graphic occupies the bottom half for some window → captions go "top" for that window.
    - The speaker is looking down / mouth is in the lower third of the frame → captions go "top".
    - B-roll cutaway covers the bottom with busy imagery → captions go "top".
    - Single-word dramatic moment (Quintessence-style) where caption needs center-stage → "center" briefly.
  Speaker changes alone don't require caption moves — face position does.
  Segment boundaries must fall on word boundaries from the transcript.

=== TEXT OVERLAYS — BRIEF TITLE CARDS ===

Short framing text that appears 1-3 times per video (hook, chapter, quote, speaker attribution). NOT running captions. Each has a `variant` that picks a distinct visual treatment.

text_overlays — REQUIRED ARRAY (can be empty).

Each entry:
  {{
    "variant": "torn_paper" | "sticky_note" | "quote_card" | "lower_third" | "caption_match",
    "start_word_index": int,       # Deepgram word whose START the overlay appears on. Schema-constrained to kept words.
    "duration_seconds": float,     # on-screen lifespan, 1.5 - 4.0s typical
    ...variant-specific REQUIRED props
  }}

The overlay appears precisely when `start_word_index`'s word begins speaking (the pipeline projects the word's start time through the output cuts) and stays visible for `duration_seconds`. No free-form timestamp to get wrong.

Variants and their REQUIRED props:

1. "torn_paper"  — Two torn paper strips slam from opposite sides. Confession/framing/hook aesthetic.
   REQUIRED: "topText" (str <=5 words UPPERCASE), "bottomText" (str <=5 words UPPERCASE)
   Use for: POV hooks ("MY 6YO" / "EXPOSED MY WIFE"), "BEFORE" / "AFTER".

2. "sticky_note" — 1-3 animated sticky notes with handwritten-style text.
   REQUIRED: "notes" (array of {{"text": str, "color": "#hex", "rotation": float}} — 1 to 3 items)
   Use for: key takeaways, tip bullets, educational moments.

3. "quote_card" — Floating card with quote + em-dash attribution. Serif, premium.
   REQUIRED: "quote" (str <=20 words), "attribution" (str)
   Use for: testimonials, pull-quotes, book references.

4. "lower_third" — Broadcast name + title card. Anchored at the lower third.
   REQUIRED: "name" (str), "title" (str — role/location)
   Use for: speaker attribution, podcast guests, location tags. EMIT ONE whenever a new speaker appears.

5. "caption_match" — Renders in the same style as the main captions. Mono-brand aesthetic.
   REQUIRED: "text" (str <=6 words), "position" ("top" | "center" | "bottom")
   Use ONLY for Hormozi/hustle/mono-brand vibes where matching the caption IS the brand. Otherwise pick torn_paper / sticky_note / quote_card / lower_third.

DECISION MATRIX — text overlay variant by content:
  POV, confession, narrative, story hook        → "torn_paper"
  educational, tip, how-to, tutorial            → "sticky_note"
  interview guest intro, name + role            → "lower_third" (emit ONE per distinct speaker)
  testimonial, pull-quote, book/article quote   → "quote_card"
  motivational/hustle/Hormozi mono-brand        → "caption_match"

0-2 overlays per video. More is noise (except lower_thirds for multi-speaker intros — one per speaker is fine).

=== EMPHASIS MOMENTS — VISUAL HITS ===

Emphasis moments are the 2-5 beats in the video that HIT HARDEST. Each composes up to three visual layers, every layer explicit.

emphasis_moments — ARRAY of 2-5 items. High-intensity moments must be ≥2.5s apart.

Each entry:
  {{
    "word_indices": [int, ...],          # 1-3 Deepgram word indices that ARE the emphasis. Every index must target a word you are KEEPING — a word you also emit in remove_words cannot be emphasized. The pipeline derives the emphasis timestamp from word_indices[0].start; you do not emit a separate `t` field.
    "type": "punchline" | "revelation" | "statement" | "reaction" | "question",
    "intensity": "high" | "medium",
    "duration": float,                   # output-seconds the visual hit lasts, 1.5 - 3.0

    # ── Visual layers — each field REQUIRED (value or null) ──
    "zoom_effect": {{"type": zoom_type, "events": [...]}} | null,
    "color_pulse": bool,                 # when true, color_effect (pulsed mode) fires a pulse aligned to this moment
    "motion_graphic": {{"type": mg_type, "anchor": zone, "props": {{...}}}} | null
  }}

For each emphasis moment, deliberately choose each layer:

A. zoom_effect — does this moment need a zoom?

   1. "SmoothPush"    — Slow, deliberate forward zoom with refined easing. Starts imperceptibly, accelerates, decelerates to stop.
                         Best for: Drawing attention, emphasis moments, B-roll enhancement.
   2. "SnapReframe"   — Fast, precise zoom with critically-damped spring. No bounce, no overshoot.
                         Best for: Beat-synced reframes, reaction shots.
   3. "FocusWindow"   — Background shows zoomed detail, smaller rectangle shows normal framing. Picture-in-picture context.
                         Best for: Revealing context around a detail, before/after in same frame.
   4. "StepZoom"      — Instant jump cuts between zoom levels. No easing. Clean editorial reframes on the beat.
                         Best for: Music videos, fast-paced edits, beat-matched.
   5. "LetterboxPush" — Zoomed-in view pushes from center with cinematic letterbox bars. Aspect ratio narrows with depth.
                         Best for: Cinematic emphasis, dramatic reveals.
   6. "StageZoom"     — Two-stage zoom: first push settles, holds, then second deeper push. Like finding focus then committing.
                         Best for: Two-beat emphasis, building tension.
   7. "DepthPull"     — Multi-layer cinematic depth. Background zooms slowly with floating bokeh, edge blur, haze, and frame lines.
                         Best for: Premium intros, title sequences, high-production moments.

   Events are CLIP-relative (startMs from the clip's start). A single event tied to this moment's position within its clip is the common pattern.
   For the `scale` value, use the SHOT SCALE block above as your single source of truth — it's tuned to the actual framing of THIS video. The scale ranges there supersede any general-purpose defaults. Too-tight zoom on an already-close face crops out eyes/chin.
   originY ≈ 0.4 for talking heads (faces sit in the upper half).

B. color_pulse — should the global color effect fire a pulse at this moment?
   Only set true if color_effect is non-null AND its timing.mode is "pulsed". Otherwise false.
   If true, the pulse's peakFrame automatically aligns to THIS moment's t.

C. motion_graphic — should a text/graphic overlay land on this moment?
   Pick from the motion graphic vocabulary below. Reserve for the 1-2 PAYOFF moments. Too many = clutter.
   motion_graphic windows must NOT overlap with any text_overlay window.

=== COLOR EFFECT — OPTIONAL GLOBAL GRADE ===

Wraps the entire video. Set null for most videos (phone footage grades poorly).

color_effect — object or null.

Structure:
  {{
    "type": <grade>,
    "intensity": 0.4 - 1.0,
    "timing": {{"mode": "persistent", "fadeInFrames": 15}}
      OR {{"mode": "pulsed", "pulses": [{{"peak_at_seconds": float, "attackFrames": 3, "holdFrames": 4, "releaseFrames": 12, "intensity": 1.0}}]}}
  }}

12 grades:

 1. "CinematicGrade" — Teal-and-orange Hollywood grade. Cool shadows, warm highlights, subtle contrast boost.
                        Best for: Cinematic footage, interviews, narrative B-roll.
 2. "BleachBypass"   — Silver retention look. Desaturated, contrasty, soft silver sheen via soft-light composite.
                        Best for: Thriller, prestige documentary, cold editorial.
 3. "VintageFilm"    — Warm highlights, green-cast shadows, halation glow, optional procedural grain.
                        Best for: Nostalgic montages, retro, wedding/lifestyle.
 4. "DreamHaze"      — Lifted blacks, soft highlight bloom, pastel desaturation. Nostalgic diffusion.
                        Best for: Dreamy montages, music videos, lifestyle/travel.
 5. "ChromaSplit"    — RGB channel split via SVG filters. Optional slow angle drift.
                        Best for: Glitch accents, analog aesthetics, beat-synced hits. Recommended with "pulsed" timing.
 6. "VignettePulse"  — Two-layer vignette: constant base + pulsed darker layer that "closes in" at peak.
                        Best for: Beat-synced emphasis, dramatic framing. Use with "pulsed" timing.
 7. "InvertStrike"   — Color-inverts footage on beat via CSS invert(). Optional contrast punch.
                        Best for: Beat drops, editorial punch, music video accents. REQUIRES "pulsed" timing.
 8. "CineMono"       — Cinematic B&W with channel-mixed grayscale. Custom R/G/B luma weights. Optional grain.
                        Best for: Prestige documentary, dramatic B&W, portraits.
 9. "GoldenHour"     — Warm amber cast, cream highlights, magenta shadow hints. Everything glows.
                        Best for: Interviews, lifestyle B-roll, golden-hour simulation.
10. "FilmGrain"      — Authentic film grain with emulsion damage. Two grain layers, dust specks, hairline scratches. Deterministic per frame.
                        Best for: Film print authenticity, documentary texture.
11. "Portra"         — Kodak Portra 400 emulation. Low contrast, lifted shadows, creamy skin tones, muted greens.
                        Best for: Portraits, editorial photography feel, subtle grading.
12. "NeoNoir"        — Fincher-style neo-noir. Heavy desaturation, crushed blacks, cold greenish-cyan midtones.
                        Best for: Thriller, moody narratives, dark editorial.

Pulsed mode:
  Each pulse has `peak_at_seconds` — a SOURCE-time timestamp (pick from vocal_emphasis peaks or shot_changes). The renderer projects to output frames.
  If any emphasis_moment.color_pulse = true, you MUST ALSO set color_effect.timing.mode = "pulsed" (additional pulses fire automatically at those moments).

GUIDELINES:
  Most videos → color_effect = null.
  Only pick a grade if it genuinely fits the vibe AND the footage is flattering enough to carry it.
  InvertStrike / ChromaSplit / VignettePulse use "pulsed".

=== MOTION GRAPHICS — REINFORCE CONTENT ===

0-5 per video. Each REINFORCES a moment, doesn't replace it.

motion_graphics — ARRAY.

Each entry is WORD-ANCHORED — Gemini picks the kept words the MG stretches across, and the pipeline derives the on-screen window from those word timestamps projected through the output cuts.

  {{
    "type": <mg_type>,
    "start_word_index": int,       # Deepgram word the MG appears on (word's start = MG's on-screen start). Schema-constrained to kept words.
    "end_word_index": int,         # Deepgram word the MG disappears after. Must be >= start_word_index. Schema-constrained to kept words.
    "duration_seconds": float?,    # OPTIONAL override. When present, MG stays on screen for this duration (from start_word.start) regardless of end_word. Use for fixed-length pins (e.g. a 3s StatCard on one punchline word — set start_word_index==end_word_index and duration_seconds=3.0). Null = natural word-span.
    "anchor": <semantic_zone>,
    "props": {{...}}                 # component-specific
  }}

Types, descriptions, use cases, and REQUIRED props (in the schema below, keys ending in `?` are optional):

 1. "LowerThird"         — Broadcast name + title card with accent edge and optional avatar. Dark or light theme.
                            Best for: Interviews, speaker identification, podcast clips.
                            Props: {{"name": str, "title": str, "accentColor"?: "#hex", "theme"?: "dark"|"light"}}

 2. "AnnotationArrow"    — Hand-drawn SVG arrow animated along bezier path. Straight, curved-arc, j-shape, or custom SVG.
                            Best for: Callouts, UI annotations, "look here" moments.
                            Props: {{"start": {{"x": 0-1, "y": 0-1}}, "end": {{"x": 0-1, "y": 0-1}}, "pathType"?: "straight"|"curved-arc"|"j-shape"|"custom", "color"?: "#hex"}}

 3. "BRollFrame"         — Framed media insert. Clean, white-border, or polaroid variant. Multiple sources stack with rotation.
                            Best for: B-roll inserts, photo reveals, product shots.
                            Props: {{"src": URL or [URL,...], "mediaType"?: "image"|"video", "aspectRatio"?: "16:9"|"4:5"|"1:1"|"9:16", "variant"?: "clean"|"white-border"|"polaroid", "caption"?: str}}

 4. "ChartReveal"        — Animated bar or line chart building from zero. Optional peak callout with spring physics.
                            Best for: Revenue/growth stats, data storytelling.
                            Props: {{"chartType": "bar"|"line", "data": [{{"label": str, "value": float}}, ...], "title"?: str, "prefix"?: str, "suffix"?: str, "accentColor"?: "#hex"}}

 5. "ChatThread"         — iMessage-style conversation with typing indicators, sequential delivery, status bar.
                            Best for: Text recreations, testimonials, DM screenshots.
                            Props: {{"messages": [{{"sender": "me"|"them", "text": str, "typingMs"?: int, "holdMs"?: int}}, ...], "header"?: {{"name": str, "subtitle"?: str}}}}

 6. "ComparisonSplit"    — Full-screen split: image, video, color, text, or stat counter per side.
                            Best for: Before/after, A/B comparisons, stat vs stat.
                            Props: {{"sides": [ContentA, ContentB], "labels": [str, str], "orientation"?: "vertical"|"horizontal", "accentColor"?: "#hex", "theme"?: "dark"|"light"}}
                            ContentX: {{"type": "text"|"stat"|"image"|"video"|"color", "value": str|number}}

 7. "Notification"       — iOS/Android notification stack. 1–3 banners drop in with platform styling. 7 built-in app icons.
                            Best for: Income proof, social proof, notification montages.
                            Props: {{"notifications": [{{"app": "apple-pay"|"venmo"|"stripe"|"imessage"|"instagram"|"email"|"bank", "appName": str, "title": str, "body": str, "timestamp"?: str}}, ...], "platform"?: "ios"|"android"}}

 8. "ProgressBar"        — Animated progress bar with count-up. Optional milestones.
                            Best for: Goal tracking, fundraising, skill bars.
                            Props: EITHER {{"value": number, "total": number, "label"?: str, "fillColor"?: "#hex", "accentColor"?: "#hex"}}  OR  {{"percentage": 0-100, "label"?: str, "fillColor"?: "#hex", "accentColor"?: "#hex"}}

 9. "QuoteCard"          — Floating card with decorative quotation mark, serif text, em-dash attribution. Spring entrance.
                            Best for: Testimonials, pull quotes, book excerpts.
                            Props: {{"quote": str, "attribution": str, "theme"?: "dark"|"light", "accentColor"?: "#hex"}}

10. "RecordingFrame"     — Full-screen recording overlay with inset border, scan line, corner annotations (timestamp, WPM).
                            Best for: Behind-the-scenes, raw/unfiltered, documentary.
                            Props: {{"accentColor"?: "#hex", "showScanLine"?: bool}}

    — SpeechBubble variants (4) — Platform-specific social bubbles. Best for: Social proof, testimonials, comment highlights.

11. "TweetBubble"        — Twitter/X post with verified badge and engagement stats.
                            Props: {{"name": str, "handle": str, "text": str, "verified"?: bool, "stats"?: {{"replies": int, "reposts": int, "likes": int, "views": int}}, "darkMode"?: bool}}
12. "InstagramComment"   — Instagram comment with avatar and like count.
                            Props: {{"username": str, "comment": str, "timestamp"?: str, "likes"?: int}}
13. "IMessageBubble"     — iMessage bubble with typewriter mode.
                            Props: {{"text": str, "messageType": "incoming"|"outgoing", "status"?: "Delivered"|"Read", "typewriter"?: bool}}
14. "TikTokComment"      — TikTok comment with likes.
                            Props: {{"username": str, "comment": str, "likes"?: int}}

15. "StatCard"           — Animated count-up number with label and accent divider. Prefix/suffix formatting.
                            Best for: Revenue stats, subscriber counts, KPIs.
                            Props: {{"value": number, "label": str, "prefix"?: str, "suffix"?: str, "fromValue"?: number, "decimals"?: int, "accentColor"?: "#hex"}}

16. "StickyNotes"        — 1–3 sticky notes slam on with spring physics. Color, rotation, handwritten text (Caveat Brush).
                            Best for: Key takeaways, tip lists, educational content.
                            Props: {{"notes": [{{"text": str, "color": "#hex", "rotation": float}}, ...]}} (1-3 notes)

17. "Toggle"             — iOS-style toggle that flips on at configurable time. Label text.
                            Best for: Feature toggles, on/off reveals, settings demos.
                            Props: {{"text": str, "activateAtMs"?: int, "onColor"?: "#hex"}}

18. "TornPaper"          — Two torn paper strips slam from opposite sides with stop-motion impact. Shadow blocks for depth.
                            Best for: Bold statements, key points, "vs" comparisons.
                            Props: {{"topText": str (<=5 words), "bottomText": str (<=5 words)}}

GUIDELINES:
  Anchor semantically, not by pixels.
  Duration 2.0 - 4.0s.
  Conflict check: if a motion_graphic sits at "lower_third_safe" during a window, your caption_position_segments MUST set captions to "top" across that window. This is your responsibility; the renderer will NOT auto-flip.
  Non-overlap: no motion_graphic window may overlap any text_overlay window.

=== WORD EDITING ===

remove_words — ARRAY. All word-level cleanup (fillers, stutters, false starts, dead air, contextual filler, phrasal restarts, narrative redundancy) has ALREADY been applied by the upstream mechanical + content-analysis pre-pass. The transcript you see is the post-pre-pass transcript; pre-cut words appear with `[PRE-CUT:reason]` tags and cannot be anchored.

Your `remove_words` field is almost always EMPTY. Only emit an entry if you decide an entire narrative section should be skipped (e.g. a tangent unrelated to the video's vibe). Range-based entries only:

  {{"start": float, "end": float, "reason": "section_skip"}}

Preferred alternative: use `speed_curve` to accelerate low-value sections instead of cutting them. Hard cuts of content inside a clause are jarring; a 1.3–1.5× speed ramp preserves continuity while pacing through filler content.

=== HOOK ===

First thing before the rest. MUST be the climax/punchline/shock. Never the setup.

hook_clip — object or null. {{"source_start": float, "source_end": float}}.
  Duration 1.0 - 3.0s. First word lands within 0.3s. null is valid when the video opens with an already-compelling first 2s.

=== SFX — SOUND EFFECTS ===

Sound effects reinforce content beats. Use them liberally WHEN they genuinely add meaning to a moment, but silence > wrong sound. Emit as many as make sense — there's no hard cap. Each entry: {{"word_index": int, "sound": <name>}} — you pick the Deepgram word that triggers the SFX and the pipeline derives the exact timing. The schema enum constrains word_index to kept words only; you cannot pick a pre-cut word.

Every sound must literally FIT the moment. The description and Best-for below tell you what each sound sounds like and when to reach for it. Tonal context beats vocabulary matching — if the surrounding content doesn't fit the sound's character, skip it even when a trigger word matches.

14 sounds, grouped by acoustic behavior:

IMPACT SOUNDS — instant transient. `t` is exactly the moment the hit should land.

 1. "hit"            — Short, punchy cinematic impact like a body hit or fist strike in a trailer. Mid-low-frequency thud, fast attack, very short tail. Not as deep as boom, not as hissy as pop.
                        Best for: punchlines, emphasis moments, hard statements, "and that's when everything changed" beats.
                        Triggers on: *hit, punch, bam, boom, snap, slam, crash, broke, dropped*.
 2. "ching"          — Bright metallic cash-register / slot-machine chime. The classic "cha-ching" money sound. High-frequency ring with a short metallic decay.
                        Best for: money wins, revenue reveals, success-money crossover, "$$$" moments, jackpot beats.
                        Triggers on: *money, cash, paid, earned, dollar, jackpot, profit, million, K, revenue*.
 3. "ding"           — Clean single-tone notification bell. iMessage-style — bright mid-high with a clean decay, NOT metallic like ching.
                        Best for: notification events ONLY — on-screen notifications, incoming messages/alerts, phone notification reveals, "you've got mail" beats. Pair naturally with the Notification motion-graphic.
                        Triggers on: *notification, alert, message, text, email, ping, notified*.
                        Skip for: correct answers, lightbulb ideas, general "yes" acknowledgments, level-ups, positive-check moments — the Notification MG pairing makes those contexts feel mismatched. Reach for `pop` or silence instead.
 4. "pop"            — Quick cartoony bubble-burst. Bright, playful, mid-energy transient.
                        Best for: item appearances, playful reveals, text-pops, sticker/emoji reveals, lighthearted visual punctuation.
                        Triggers on: *pop, appeared, suddenly, out of nowhere, surprise*, any lighthearted reveal word.
 5. "camera_shutter" — Mechanical DSLR shutter snap. Short dual-click with a slight metallic ring.
                        Best for: ONLY when an actual photo/picture is being taken on-screen, or the dialogue LITERALLY references taking a photo/screenshot. Rare — most videos should not use this at all.
                        Triggers on (literal sense only): *took a picture, photo, snap a pic, selfie, screenshot, say cheese*.
                        Skip for: metaphorical "capture the moment", "freeze frame", still-moment visuals without an actual camera reference, or generic punctuation. When unsure, pick silence.
 6. "click"          — Very soft, quiet UI button click. Low-energy tap, almost subliminal. Punctuates without intruding.
                        Best for: UI interactions, toggle moments, checkbox confirmations, micro-beats where you want rhythm but can't have loudness.
                        Triggers on: *click, tap, press, select, enable, tick, checked*.

CINEMATIC IMPACT + BUILD — these sounds have a short build (0.4–0.7s) before the peak. The renderer automatically schedules the file to START before the trigger word so the climax lands ON the word. You just pick the trigger word.

 7. "boom"           — Deep cinematic sub-bass impact. Short build (~0.4s) into a massive low-end whoom, then a fading rumble. The sound used for beat drops and heavy reveals.
                        Best for: heavy reveals, bass drops, dramatic punchlines, transition landings after an anticipation build.
                        Triggers on: *boom, drop, reveal, changed everything, here's the thing, then this happened*.
 8. "thunder"        — Natural thunder crack with a rolling rumble tail. Crack lands ~0.73s in, 1.7s of rumble trailing off.
                        Best for: dramatic proclamations, ominous statements, thriller/dark content, weather references, "storm is coming" moments.
                        Triggers on: *thunder, storm, exploded, shook, rocked, hit me, catastrophic, disaster*.

BUILD-UP SOUNDS — long builds (1.3–1.7s) climaxing at the end. The renderer schedules the file early so the climax lands on the trigger word, which means the build plays DURING the preceding audio. CRITICAL: the trigger word must have enough kept-clip time BEFORE it (at least the build duration) or the build gets truncated and the effect is lost.

 9. "drum_roll"      — Classic military/circus snare drum roll building for ~1.65s into a payoff crash at the end. Iconic tension-before-reveal sound. Traditional/comedic anticipation — works standalone in talking-head content.
                        Best for: big announcements, anticipation before a reveal, "and the answer is...", award moments, payoff setups.
                        Triggers on: *winner, revealed, the answer, finally, ta-da, drumroll, introducing*.
                        Needs ≥1.65s of kept-clip time before the trigger word.
10. "reverse"        — Reverse riser. Builds continuously in volume and pitch for ~1.37s, climaxing at the very end. Engineered as a cinematic "suck-toward-the-moment" effect — the entire sound IS anticipation.
                        Best for: priming a MAJOR visual event. ALWAYS pair with something visually impactful landing on the trigger word — a hard cut to a new scene, a zoom effect landing (SnapReframe / StepZoom / LetterboxPush), a color pulse hit (InvertStrike / VignettePulse), a TornPaper or motion-graphic slam, or a transition peak. The 1.37s rise plays across the preceding clip audio and releases into the visual beat.
                        Skip when there's no paired visual payoff — generic "wait for it" dialogue, punctuating sentences with no visual event attached, building up to a normal talking-head cut with nothing extra happening, or back-to-back triggers. Without a visual climax landing on the trigger word, this sound feels anticlimactic.
                        Needs ≥1.37s of kept-clip time before the trigger word.
11. "sad_trombone"   — The iconic "wah wah waaah" four-note descending trombone. 1.3s descending phrase climaxing on the final low note. Unambiguously comedic — every listener recognizes this as the "you failed" joke sound. There is no way to use this sincerely; it IS the joke.
                        Best for: ONLY when the content is EXPLICITLY comedic and the "failure" is being played for laughs. Trivial mishaps, obvious mock-failures, game-show-style setups, bloopers, intentional self-own jokes.
                        Required tonal gate — verify BOTH before emitting:
                          (a) User's vibe is comedic, playful, ironic, or self-deprecating (e.g. "funny", "comedy", "blooper", "joke", "fail compilation", "roast"). If the vibe is motivational, educational, interview, storytelling, lifestyle, business, or any serious register — DO NOT USE.
                          (b) Dialogue at the trigger moment is clearly comedic — the speaker is making light of the moment intentionally, not processing something real.
                        Skip for: real failures, breakups, deaths, job losses, business collapses, mental-health struggles, motivational / overcoming-adversity content, interviews / podcasts / storytelling where a guest shares a vulnerable moment, and any reflective / emotional / vulnerable content. Trigger words alone never justify this sound — "failed" in a serious context calls for silence. Context trumps vocabulary. When in doubt, skip.
                        Needs ≥1.29s of kept-clip time before the trigger word.

ATMOSPHERIC SWEEPS — airy sweeps used BETWEEN beats rather than ON impact words. Near-instant onset, long trail.

12. "whoosh_slow"        — Mid-energy cinematic airy sweep with presence and weight. More dramatic than transition_smooth.
                            Best for: dramatic entrances, reveal sweeps, camera-move-simulation moments, "and then..." narrative pivots. The more cinematic of the two sweeps.
                            Triggers on: *enter, arrived, appeared, suddenly, meanwhile, next, then, shift*.
13. "transition_smooth"  — Softer, gentler airy wash. Lower-energy atmospheric sweep, less presence than whoosh_slow.
                            Best for: scene-change transitions, soft pivots, topic shifts where whoosh_slow would be too punchy. The subtler sweep.
                            Triggers on: *transition, shift, meanwhile, moving on, next, and then, speaking of, on that note*.

CONTINUOUS TEXTURE

14. "typing"             — Keyboard typing sequence. Rapid mechanical key clicks across ~1s, not a single transient.
                            Best for: typing scenes, text-reveal moments, code/writing/email reveals, anything where typed text appears on screen. Pair naturally with a TypewriterReveal caption style.
                            Triggers on: *typed, wrote, emailed, messaged, coded, typing*.

AMBIGUITY CALLOUTS — the confusing pairs Gemini MUST distinguish:

 - boom vs thunder vs hit:           boom = deep synthetic drop (music beats, reveals). thunder = natural rolling crack with trailing rumble (drama, weather, thriller). hit = short sharp punch with no build (punchlines, emphasis).
 - ching vs ding:                    ching = metallic cash sound (money/wins only). ding = clean notification bell (phone/app notification events ONLY — never generic "yes/correct" moments).
 - click vs pop vs camera_shutter:   click = soft UI tap, nearly subliminal (buttons, toggles). pop = bright cartoony burst (playful reveals, text pops). camera_shutter = DSLR snap reserved for LITERAL photo moments only.
 - whoosh_slow vs transition_smooth: whoosh_slow has more presence and drama (dramatic entrances, cinematic moves). transition_smooth is softer and gentler (mundane topic pivots).
 - reverse vs drum_roll:             both build up. drum_roll = traditional/comedic anticipation, works standalone. reverse = cinematic visual-impact prep — REQUIRES a paired visual beat at the climax, otherwise it sounds unfinished.

RULE OF THUMB: pick a sound only when it adds meaning. A punchline without SFX is still a punchline; a punchline with the WRONG SFX becomes a problem. No generic punctuation. When unsure, skip.

=== B-ROLL ===

Pexels cutaways that play over dialogue.

broll_clips — ARRAY. {{"keyword": str (13-18 words), "start_word_index": int, "end_word_index": int, "reason": str}}

Rules: 3+ seconds of face between clips. Stay on the speaker during emotional beats, punchlines, hook.

=== TRANSITIONS ===

90%+ of cuts are hard cuts. Transitions EARN their place — ideally ON a shot change.

transitions — ARRAY. {{"after_word_index": int, "type": <name>, ...component props}}

11 transitions — pick the one whose visual character fits the edit:

 1. "CardSwipe"      — Clip A swipes off with 3D tilt like dismissing a card. Clip B rises from behind.
                        Best for: App-style UIs, mobile-first edits.
                        Optional: `direction` ("left" | "right", default "left").
 2. "ZoomThrough"    — Clip A scales up past the camera, clip B emerges from behind and grows to fill.
                        Best for: Energetic forward motion, "diving in" transitions.
 3. "SlideOver"      — Clip B slides over clip A with contact shadow. Clip A shifts and scales down.
                        Best for: Clean editorial cuts, presentations.
                        Optional: `direction` ("left" | "right", default "left").
 4. "Stack"          — iOS task-switcher. Dark wallpaper, stacked cards. Clip A shrinks to card and slides off.
                        Best for: Phone UI, app showcases, tech content.
 5. "CrossfadeZoom"  — Clip A zooms in + fades, clip B fades in + zooms out. Premium cross-dissolve with motion.
                        Best for: Cinematic dissolves, photo slideshows.
 6. "ShutterFlash"   — CRT power-off to power-on. Vertical collapse to bright dot, then reverse.
                        Best for: Retro tech, channel-switching, dramatic hard cuts.
                        Optional: `flashColor` (default "#ffffff").
 7. "LightLeak"      — Warm glow sweeps across frame. Three layered radial gradients with screen/soft-light blend. Hard cut hidden at peak.
                        Best for: Warm cinematic, golden hour, dreamy bridges.
                        Optional: `palette` ("warm"|"gold"|"cool"|"magenta", default "warm"); `direction` ("tl-br"|"tr-bl"|"left-right"|"top-down", default "tl-br"); `intensity` (default 1.0).
 8. "StepPush"       — Keynote-style slide push. Both panels travel together.
                        Best for: Presentations, corporate, clean editorial.
                        Optional: `direction` ("left"|"right"|"up"|"down", default "left"); `separatorShadow` (bool, default true).
 9. "NewspaperWipe"  — Torn newspaper slams up, covers frame, holds, rushes off. Staccato keyframes.
                        Best for: News-style intros, editorial punch cuts.
10. "FilmStrip"      — Device-frame film-reel. Clip A morphs into tile, strip scrolls, clip B expands back.
                        Best for: Gallery reveals, portfolio showcases.
                        Optional: `caption` (str); `showBookmark` (bool, default false); `showGrid` (bool, default true).
11. "SceneTitle"     — Chapter-break. Typographic title panel wipes across, holds, wipes out. Inter + DM Serif Display.
                        Best for: Chapter breaks, act titles, documentary headers.
                        REQUIRED: `title` (str). Optional: `label` (str, small uppercase); `variant` ("full"|"half-top"|"half-bottom", default "full"); `theme` ("dark"|"light", default "dark"); `accentColor` (default "#C8551F").

  Never repeat the same transition more than twice across the video.
  Place ON or near a shot_changes entry — that's where the viewer's eye expects a visual boundary.
  SceneTitle: 0-2 per video maximum (genuine chapter breaks only).

=== SPEED CURVE ===

Only when vibe mentions "speed ramp" or "CapCut style". Else: "none".

speed_curve — ARRAY of {{"t": float, "speed": float 0.67-1.4}} or "none".

=== GLOBAL FIELDS ===

notes              — string <=50 words. Brief rationale.
thumbnail_timestamp — SOURCE-seconds. Pre-reveal anticipation or post-reveal reaction, NOT the punchline word (mid-syllable mouths are ugly).
audio_denoise      — bool. true when noise_floor > -40 dB.
outro              — "none" | "fade_black" | "fade_white". "none" best for looping.
aspect_ratio       — always "9:16".
pacing             — "fast" | "medium" | "slow".

=== RESPONSE FORMAT ===

Output ONLY a JSON object — no commentary, no markdown fences, no prose.

{{
  "notes": "<=50 words>",
  "hook_clip": {{"source_start": float, "source_end": float}} | null,
  "thumbnail_timestamp": float,
  "caption_style": "<one of 21>",
  "caption_keywords": ["<word>", "<word>", ...],
  "caption_position_segments": [
    {{"from_seconds": 0.0, "to_seconds": float, "position": "top" | "center" | "bottom"}},
    ...
  ],
  "color_effect": {{"type": "<grade>", "intensity": float, "timing": {{...}}}} | null,
  "audio_denoise": bool,
  "outro": "none" | "fade_black" | "fade_white",
  "aspect_ratio": "9:16",
  "pacing": "fast" | "medium" | "slow",
  "speed_curve": [...] | null,
  "emphasis_moments": [
    {{
      "word_indices": [int, ...],
      "type": "...",
      "intensity": "high" | "medium",
      "duration": float,
      "zoom_effect": {{...}} | null,
      "color_pulse": bool,
      "motion_graphic": {{...}} | null
    }}
  ],
  "text_overlays": [
    {{"variant": "...", "start_word_index": int, "duration_seconds": float, ...variant props}}
  ],
  "sound_effects": [
    {{"word_index": int, "sound": "<name>"}}
  ],
  "broll_clips": [
    {{"keyword": "<13-18 words>", "start_word_index": int, "end_word_index": int, "reason": "<quote>"}}
  ],
  "transitions": [
    {{"after_word_index": int, "type": "<name>", ...transition props}}
  ],
  "motion_graphics": [
    {{"type": "<name>", "start_word_index": int, "end_word_index": int, "duration_seconds": float|null, "anchor": "<zone>", "props": {{...}}}}
  ],
  "remove_words": [
    {{"start": float, "end": float, "reason": "section_skip"}}
  ]
}}

=== BEFORE YOU EMIT — INTERNAL VERIFICATION ===

Work through these checks against the plan you are about to emit. This is self-verification — do not externalize it in your output.

1. Caption segments cover the full duration. `caption_position_segments[0].from_seconds == 0.0`. `caption_position_segments[-1].to_seconds` equals the source duration given in the user message. Every `to_seconds` equals the next segment's `from_seconds`. Every interior boundary matches a real word-boundary timestamp from the transcript you were given.
2. Non-overlap in time. No two `text_overlays` windows (start_word.start, start_word.start + duration_seconds) overlap. No `text_overlays` window overlaps any `motion_graphics` window or any `emphasis_moments[i].motion_graphic` window. High-intensity emphasis moments are ≥2.5s apart.
3. One zoom per kept-source clip. Within each contiguous source range between removed-word boundaries, at most one `emphasis_moments[i].zoom_effect` is non-null. Multiple beats close together stack their events onto a single emphasis_moment's `zoom_effect.events` array.
4. Z-order yield. For every window a motion_graphic sits in the lower half (`lower_third_safe` or `center`-ish), `caption_position_segments` is `top` across that window.
5. Color consistency. If any `emphasis_moments[i].color_pulse == true`, `color_effect` is non-null and `color_effect.timing.mode == "pulsed"`. `InvertStrike` requires `timing.mode == "pulsed"` with at least one pulse.
6. MG anchors are absolute zones. Every `motion_graphics[i].anchor` and every `emphasis_moments[i].motion_graphic.anchor` is one of the 5 absolute zones (`upper_third_safe`, `center`, `lower_third_safe`, `left_safe`, `right_safe`).
7. Explicit nulls. Every emphasis_moment has explicit `zoom_effect` (value or null), `color_pulse` (bool), and `motion_graphic` (value or null) fields — no omissions.
8. Build-up SFX headroom. For every `drum_roll`, `reverse`, or `sad_trombone`, the trigger word has at least the required build duration of kept-clip time before it (drum_roll ≥1.65s, reverse ≥1.37s, sad_trombone ≥1.29s).
9. sad_trombone tonal gate. If `sad_trombone` appears, the tonal_register is "comedic" AND the surrounding dialogue is being played for laughs. Otherwise remove it.

Note: word-anchor validity (anchors reference kept words) is structurally enforced by the schema enum — the decoder literally cannot emit an anchor that would target a cut word. You don't need to verify it.

If any check fails, revise the plan before emitting JSON. The validators reject violations — fixing them here is cheaper than re-generating."""

    user_content_parts = []
    user_content_parts.append(f"The user wants: {vibe}")
    user_content_parts.append(f"This video is {duration:.1f} seconds long ({duration:.3f}s source duration).")
    user_content_parts.append(signals_block.strip())
    if _usr_block:
        user_content_parts.append(_usr_block.strip())
    if trend_block:
        user_content_parts.append(trend_block.strip())
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


def run_content_analysis(deepgram_words, inline_video_bytes, mechanical_cuts):
    """Pre-pass Gemini call that classifies every word with full video context.

    Runs in parallel with face detection + other signal computation. Its output
    drives the main edit call's dynamic schema enums so that anchor fields and
    remove_words.word_index reference disjoint index spaces.

    Returns a dict:
      {
        "word_cuts": set[int]   # analysis-decided cuts (context-aware)
        "cuttable": set[int]    # analysis-cuttable words not yet cut
        "protected": set[int]   # anchor-eligible words (content + narrative peaks)
        "peaks": set[int]       # narrative peak subset of protected
        "tonal_register": str   # overall video tone (serious/comedic/...)
      }

    Gemini 3 Flash at LOW thinking is the right choice here: the task is narrow
    (per-word classification with bounded output), video understanding is the
    whole value, and there's no creative/composition reasoning to do.
    """
    _words = list(deepgram_words or [])
    if not _words or not inline_video_bytes:
        # No words → no classification possible. Default: everything the
        # mechanical pass already caught is cut; nothing else is cuttable;
        # everything else is protected.
        _mech_cuts = set(mechanical_cuts.get("word_cuts", set()))
        _protected = set(range(len(_words))) - _mech_cuts
        return {
            "word_cuts": set(),
            "cuttable": set(),
            "protected": _protected,
            "peaks": set(),
            "tonal_register": "casual",
        }

    client = _get_genai_client()
    _video_part = genai_types.Part.from_bytes(
        data=inline_video_bytes, mime_type="video/mp4",
    )

    # Build transcript representation for the analysis call. Include the
    # mechanical-cut flag per word so Gemini sees the deterministic pre-pass
    # decisions and doesn't re-classify those words.
    _mech_cuts = set(mechanical_cuts.get("word_cuts", set()))
    _mech_reasons = dict(mechanical_cuts.get("reasons", {}))
    lines = []
    for i, w in enumerate(_words):
        word_text = str(w.get("punctuated_word") or w.get("word") or "").strip()
        start = float(w.get("start") or 0)
        end = float(w.get("end") or 0)
        spk = int(w.get("speaker") or 0)
        if i in _mech_cuts:
            lines.append(
                f"  [{i}] {start:.2f}-{end:.2f} spk{spk}: {word_text}  "
                f"[MECHANICAL-CUT:{_mech_reasons.get(i, '?')}]"
            )
        else:
            lines.append(f"  [{i}] {start:.2f}-{end:.2f} spk{spk}: {word_text}")
    transcript_lines = "\n".join(lines)

    system_instruction = """You are a classification system for a short-form video editor. Your ONLY job is to classify every word in the transcript into exactly one of five buckets based on the full video and dialogue context. You do not make creative decisions — you only judge what each word is.

CLASSIFICATION VOCABULARY:

1. "content" — a substantive word that should stay in the video and cannot be cut. Nouns, verbs with semantic weight, numbers, named entities, descriptive adjectives, words that carry the meaning of the sentence. This is the default for words you're not sure about. When in doubt, pick content.

2. "cuttable_filler" — context-dependent filler. Words that look substantive in isolation but function as hedges, discourse markers, or filler in this specific context. Examples: "literally" in "I literally just walked in" (emphasis filler, no semantic value), "basically" as a hedge, "just" in "I just want to say", "like" as a discourse marker, "actually" as a hedge, "right?" at end of statement, "you know", "I mean" as restart. You must verify this word is NOT the emphasis target in its sentence (if it's where the speaker's voice peaks, it's a narrative_peak, not filler).

3. "cuttable_restart" — part of a phrasal restart that the speaker corrected. Example: "I said — I said who is he?" the first "I said" is a restart. Or: "The thing is — well the thing about it is..." the first clause is a restart. Cut the incomplete version, keep the complete one.

4. "cuttable_redundant" — narratively redundant. The word (or its phrase) repeats a concept the speaker just stated with no added value. Example: "bikini bottom is calling, calling again" — the second "calling" is redundant.

5. "narrative_peak" — a genuine emphasis target. The word where the speaker's voice peaks, the punchline noun, the reveal, the reaction word, the emotional climax. Only a few words per video qualify. These are the anchor targets for MGs, emphasis moments, and SFX.

RULES:

- Every word in the transcript gets exactly one classification (via source_index).
- Words already flagged [MECHANICAL-CUT] MUST be classified as "cuttable_filler" — they are already cut by the mechanical pre-pass; your classification is just bookkeeping.
- Do NOT add new cuts liberally. When in doubt, default to "content". Over-cutting ruins the edit.
- narrative_peak is RARE. Maybe 2–8 per video. It is the specific word the speaker hits hardest, where a visual effect belongs.
- Your output is a flat list of {source_index, classification}, one per Deepgram word index. Missing indices default to content but emit all of them.

TONAL REGISTER:

Also output the overall tonal_register of the video — serious, educational, motivational, comedic, dramatic, or casual. This drives downstream SFX gating (e.g., sad_trombone requires comedic register).

Your classification is authoritative — the downstream editor builds a schema where:
  - words you classify as cuttable_* are the ONLY words it can cut
  - words you classify as content + narrative_peak are the ONLY words it can anchor overlays to

So be accurate: a true emphasis word misclassified as filler means the editor can't highlight it. A content word misclassified as cuttable means it may get removed. The whole point of this pass is to let the editor anchor precisely."""

    user_content = f"""TRANSCRIPT (word-by-word with source indices; MECHANICAL-CUT tags indicate words already cut by the deterministic pre-pass):

{transcript_lines}

Classify each word. Return the word_analyses array with one entry per source_index (0..{len(_words) - 1}), plus the tonal_register."""

    t0 = time.time()
    print(
        f"[content-analysis] Calling Gemini model={GEMINI_MODEL} (thinking=LOW, {len(_words)} words)...",
        flush=True,
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[_video_part, user_content],
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=1.0,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_json_schema=ContentAnalysis.model_json_schema(),
            thinking_config=genai_types.ThinkingConfig(thinking_level="LOW"),
            media_resolution="MEDIA_RESOLUTION_LOW",
        ),
    )
    elapsed = time.time() - t0
    print(f"[content-analysis] Gemini complete in {elapsed:.1f}s", flush=True)

    response_text = str(getattr(response, "text", "") or "").strip()
    if not response_text:
        raise RuntimeError("Empty content-analysis response")
    parsed = extract_json(response_text)

    # Parse word_analyses into the partitioned sets.
    word_cuts = set()         # analysis-decided cuts (ADD to mechanical)
    cuttable = set()          # analysis-cuttable, NOT yet cut (Gemini may choose)
    protected = set()         # anchor-eligible
    peaks = set()             # narrative peak subset of protected

    _seen = set()
    for entry in (parsed.get("word_analyses") or []):
        try:
            idx = int(entry.get("source_index"))
            cls = str(entry.get("classification") or "content")
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(_words) or idx in _seen:
            continue
        _seen.add(idx)
        if idx in _mech_cuts:
            # Mechanical cuts stay cut regardless of what analysis says.
            continue
        if cls in ("cuttable_filler", "cuttable_restart", "cuttable_redundant"):
            # Content-aware cuts: ADD to the hard-cut set (these words are
            # cut before the main call even sees the transcript). Main call
            # cannot anchor to them because they're not in its index space.
            word_cuts.add(idx)
        elif cls == "narrative_peak":
            protected.add(idx)
            peaks.add(idx)
        else:
            # "content" — default. Protected.
            protected.add(idx)

    # Default any unclassified surviving words to content/protected so the
    # main call has full latitude over words the analysis didn't cover.
    for idx in range(len(_words)):
        if idx in _mech_cuts or idx in word_cuts:
            continue
        if idx not in protected:
            protected.add(idx)

    # No CUTTABLE set for the main edit call — all cuts are applied by
    # mechanical+analysis BEFORE the main call sees the transcript. The main
    # call's remove_words is used only for narrative range-level section
    # skips (covered via speed_curve pacing instead per current prompt).
    # This means the main-call `remove_words.word_index` enum is empty —
    # collision is structurally impossible because there are no cuttable
    # indices left to collide with.
    tonal = str(parsed.get("tonal_register") or "casual")
    print(
        f"[content-analysis] classified: {len(word_cuts)} analysis-cuts, "
        f"{len(protected)} protected ({len(peaks)} peaks), tone={tonal} ({elapsed:.1f}s)",
        flush=True,
    )
    return {
        "word_cuts": word_cuts,
        "cuttable": cuttable,
        "protected": protected,
        "peaks": peaks,
        "tonal_register": tonal,
    }


def generate_edit_gemini(
    video_path, vibe, duration, trend_context=None, deepgram_words=None,
    shot_changes=None, vocal_emphasis=None, source_loudness=None,
    face_positions=None, smoothed_face_trajectory=None,
    user_style_profile=None,
    gemini_file=None, cached_response=None, inline_video_bytes=None,
    content_analysis=None, mechanical_cuts=None,
):
    _pre_analysis = cached_response

    _shots = list(shot_changes or [])
    _vocal = list(vocal_emphasis or [])
    _loudness = dict(source_loudness or {})
    _face_positions = list(face_positions or [])
    _smoothed_trajectory = list(smoothed_face_trajectory or [])

    # ── Classification-driven disjoint index spaces ──────────────────────────
    # `mechanical_cuts` = deterministic pre-pass (fillers, stutters, etc.)
    # `content_analysis` = Gemini Flash LOW-thinking classification that runs
    # before this call to identify context-dependent cuts and narrative peaks.
    #
    # ALL cuts (mechanical + analysis) are applied to the transcript BEFORE
    # this call builds its prompt. Main-call `remove_words` is reserved for
    # narrative decisions at the range level (still schema-enforced to the
    # small set of surviving cuttable indices — typically empty since all
    # word-level cuts are upstream).
    _mech = dict(mechanical_cuts or {})
    _anal = dict(content_analysis or {})
    _mech_word_cuts = set(_mech.get("word_cuts") or set())
    _mech_range_cuts = list(_mech.get("range_cuts") or [])
    _mech_reasons = dict(_mech.get("reasons") or {})
    _anal_word_cuts = set(_anal.get("word_cuts") or set())
    # PROTECTED = words from analysis classified as content or narrative_peak.
    # These are the ONLY indices valid in any anchor field of the main call.
    _protected = set(_anal.get("protected") or set())
    _peaks = set(_anal.get("peaks") or set())
    _tonal_register = str(_anal.get("tonal_register") or "casual")
    # Hard-cut word indices = mechanical ∪ analysis. These words are stripped
    # from the transcript shown to the main call below.
    _all_cut_indices = _mech_word_cuts | _anal_word_cuts
    if _all_cut_indices:
        print(
            f"[generate-edit] Pre-cuts applied: {len(_mech_word_cuts)} mechanical + "
            f"{len(_anal_word_cuts)} analysis = {len(_all_cut_indices)} total word cuts. "
            f"{len(_protected)} protected ({len(_peaks)} peaks). tone={_tonal_register}",
            flush=True,
        )

    # Compute face-visibility timeline + per-speaker position signals + shot
    # scale from the dense face detections. These become ground-truth signals
    # in the prompt: Gemini uses `face_visibility` to decide overlay placement
    # during face-absent moments, `speaker_positions` to choose overlay sides
    # opposite the speaker, `off_center` to avoid aggressive zoom, and
    # `shot_scale` to pick zoom type (SnapReframe only works on tight faces).
    _face_visibility, _speaker_positions, _off_center, _shot_scale = _build_face_signals(
        _face_positions, deepgram_words or [], duration,
    )

    client = _get_genai_client()
    system_instruction, user_content = build_gemini_edit_prompt(
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
    )

    # Append Deepgram word timestamps to the USER content. Transcript is
    # per-video, so it stays out of system_instruction (which must remain
    # byte-stable across calls for implicit caching).
    if deepgram_words:
        readable_words = []
        for idx, w in enumerate(deepgram_words):
            if idx in _all_cut_indices:
                continue
            readable_words.append(w.get("punctuated_word") or w.get("word") or "")
        readable_transcript = " ".join(readable_words)

        word_lines = []
        peaks_lines = []
        for idx, w in enumerate(deepgram_words):
            word_text = w.get("punctuated_word") or w.get("word") or ""
            start = float(w.get("start") or 0)
            end = float(w.get("end") or 0)
            spk = int(w.get("speaker") or 0)
            if idx in _all_cut_indices:
                # Cut by mechanical or analysis pre-pass — not valid anchor target.
                _reason = _mech_reasons.get(idx, "context" if idx in _anal_word_cuts else "mechanical")
                word_lines.append(
                    f"  [{idx}] {start:.2f}-{end:.2f} spk{spk}: {word_text}  "
                    f"[PRE-CUT:{_reason} — NOT AVAILABLE for anchors]"
                )
                continue
            tag = ""
            if idx in _peaks:
                tag = "  [NARRATIVE-PEAK]"
                peaks_lines.append(f"    [{idx}] {start:.2f}s: {word_text}")
            word_lines.append(f"  [{idx}] {start:.2f}-{end:.2f} spk{spk}: {word_text}{tag}")

        transcript_block = "\n".join(word_lines)
        peaks_block = "\n".join(peaks_lines) if peaks_lines else "  (no narrative peaks identified)"
        # First KEPT word's start timestamp (used to hint the first-clip cut)
        _first_kept_start = 0.0
        for idx, w in enumerate(deepgram_words):
            if idx not in _all_cut_indices:
                _first_kept_start = float(w.get("start") or 0)
                break
        user_content += f"""

=== TONAL REGISTER (from pre-analysis) ===

This video's overall tone: {_tonal_register}.
Let this guide caption_style, color_effect, and SFX selection. Never pick an SFX that clashes with the tonal register (e.g., sad_trombone ONLY if comedic).

=== FULL TRANSCRIPT (pre-cut words removed) ===

Read this first to understand the full story before making any editing decisions. Identify the narrative structure — what is setup, what is the buildup, and where are the punchlines or reveals.

{readable_transcript}

=== WORD-BY-WORD TIMESTAMPS ===

The following is the complete word-by-word transcript with millisecond-accurate timestamps. Words tagged [PRE-CUT:*] have already been removed by the pre-pass (mechanical + context-aware analysis) — they are NOT valid anchor targets and you must not reference them in any anchor field (the schema enforces this). Words tagged [NARRATIVE-PEAK] are classified as emphasis candidates — these are your strongest anchor targets.

{transcript_block}

=== NARRATIVE PEAKS (prioritize these for emphasis, MGs, SFX, transitions) ===

{peaks_block}

RULES FOR USING THESE TIMESTAMPS:
- word_index refers to the numbered list above. Use those exact indices in anchor fields (start_word_index, end_word_index, word_indices, word_index, after_word_index).
- The schema enforces that every anchor index is a kept (non-pre-cut) word — it is structurally impossible to anchor to a pre-cut word.
- Your source_start and source_end values MUST land in the gaps BETWEEN words, not inside a word.
- A gap is the time between one word's end timestamp and the next word's start timestamp.
- NEVER place a source_start or source_end between a word's start and end timestamps — that cuts the word in half.
- The first kept word starts at {_first_kept_start:.2f}s. For talking-head videos, set your first clip's source_start to {_first_kept_start:.2f} so the video starts on the first kept word with zero dead air.
- If the video has intentional visual content before the first word (action, scenery, product shots), start source_start at 0.0 to preserve that content.

REMOVE_WORDS GUIDANCE:
- All mechanical fillers, stutters, false starts, dead air, and context-dependent filler/redundancy have already been cut by the pre-pass and analysis. Your remove_words field is almost always EMPTY.
- Only emit a remove_words entry if you identify a narrative section that needs to go (e.g., an unrelated tangent) — and prefer speed_curve acceleration for pacing instead.
"""
        print(
            f"[generate-edit] Injected {len(deepgram_words)} Deepgram word timestamps "
            f"({len(_all_cut_indices)} pre-cut, {len(_peaks)} peaks) into prompt",
            flush=True,
        )

    # Inject pre-analysis from content-studio if available (richer visual context)
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
            user_content += "\n\n=== PRE-ANALYZED VIDEO DATA ===\n" + "\n".join(_pa_parts) + "\n"
            print(f"[generate-edit] Injected pre-analysis context ({len(_pa_parts)} sections)", flush=True)

    if trend_context:
        print(f"[generate-edit] Trend context included: {trend_context.get('sample_size', '?')} videos", flush=True)
    else:
        print("[generate-edit] No trend context available", flush=True)

    # Build video content part — inline bytes (fast, no upload/poll) or file reference (legacy)
    if inline_video_bytes:
        _video_part = genai_types.Part.from_bytes(data=inline_video_bytes, mime_type="video/mp4")
        print(f"[generate-edit] Using inline video ({len(inline_video_bytes)/1024/1024:.1f}MB, no upload)", flush=True)
    elif gemini_file is not None:
        _video_part = gemini_file
        print(f"[generate-edit] Using pre-uploaded Gemini file: {gemini_file.uri}", flush=True)
    else:
        raise RuntimeError("No video data provided — need either inline_video_bytes or gemini_file")

    # Build a schema with dynamic enums constraining word-index fields:
    #   - `remove_words.word_index` → CUTTABLE (typically empty — all cuts are
    #     upstream). If empty, the decoder never emits this variant; Gemini
    #     uses the range variant for any residual narrative skips.
    #   - Every anchor field → PROTECTED (content + narrative_peak only)
    # This makes anchor-on-cut structurally impossible in the main call.
    _cuttable_for_main_call = set()  # all word-level cuts happen upstream
    _constrained_schema = build_constrained_edit_plan_schema(
        protected_indices=_protected,
        cuttable_indices=_cuttable_for_main_call,
    )

    print(
        f"[generate-edit] Calling Gemini model={GEMINI_MODEL} (thinking=MEDIUM, structured output, temp=1.0, "
        f"system_instruction={len(system_instruction)} chars, user_content={len(user_content)} chars, "
        f"protected_enum={len(_protected)} indices)...",
        flush=True,
    )
    t = time.time()
    # response_json_schema with dynamic enums constrains word indices at
    # token-generation time — the model literally cannot emit an integer
    # outside the PROTECTED set for anchor fields, and an anchor-on-cut
    # failure is physically impossible in the output shape.
    #
    # temperature=1.0 is Google's explicit recommendation for Gemini 3 — values
    # below 1.0 "may lead to unexpected behavior, such as looping or degraded
    # performance." (per ai.google.dev/gemini-api/docs/text-generation)
    #
    # system_instruction + stable prefix enables implicit prompt caching — the
    # system block is byte-identical across calls; per-video data lives in
    # user_content, so Gemini re-reads only the deltas (video + transcript +
    # signals).
    #
    # thinking_level=MEDIUM is the working baseline. The schema + validators
    # + word-anchored overlays make HIGH thinking unnecessary — structural
    # correctness is enforced at decode time, not reasoned about.
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[_video_part, user_content],
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=1.0,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_json_schema=_constrained_schema,
            thinking_config=genai_types.ThinkingConfig(thinking_level="MEDIUM"),
            media_resolution="MEDIA_RESOLUTION_LOW",
        ),
    )
    print(f"[generate-edit] Gemini complete in {time.time()-t:.1f}s", flush=True)
    try:
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            prompt_tokens = getattr(usage, "prompt_token_count", None)
            cached_tokens = getattr(usage, "cached_content_token_count", None)
            thoughts_tokens = getattr(usage, "thoughts_token_count", None)
            output_tokens = getattr(usage, "candidates_token_count", None)
            total_tokens = getattr(usage, "total_token_count", None)
            print(
                f"[generate-edit] Tokens — prompt={prompt_tokens} cached={cached_tokens} "
                f"thoughts={thoughts_tokens} output={output_tokens} total={total_tokens}",
                flush=True,
            )
    except Exception as _e:
        print(f"[generate-edit] usage_metadata read failed: {_e}", flush=True)

    response_text = str(getattr(response, "text", "") or "").strip()
    try:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
            print(f"[generate-edit] Gemini finish_reason={finish_reason}", flush=True)
            fr_str = str(finish_reason).upper()
            if "MAX" in fr_str:
                print("[generate-edit] WARNING: Gemini response TRUNCATED — increase max_output_tokens", flush=True)
            elif "SAFETY" in fr_str:
                print("[generate-edit] WARNING: Gemini response blocked by safety filter", flush=True)
    except Exception:
        pass
    if "```json" not in response_text and "{" not in response_text:
        print(
            f"[generate-edit] ERROR: No JSON found in response. Response length: {len(response_text)} chars",
            flush=True,
        )
        print(f"[generate-edit] Response tail: ...{response_text[-200:]}", flush=True)
    if not response_text:
        raise RuntimeError("Empty Gemini response")

    print(f"[generate-edit] RAW RESPONSE:\n{response_text}\n[generate-edit] END RESPONSE", flush=True)

    edit_plan = extract_json(response_text)

    # Post-processing
    edit_plan["_deepgram_words"] = list(deepgram_words or [])
    # Preserve signals for downstream (render_multi_clip projects peak_at_seconds
    # to output frames using the same logic as SFX/captions/b-roll). Underscored
    # so the sanitized recipe strips them from persistence.
    edit_plan["_shot_changes"] = list(_shots)
    edit_plan["_vocal_emphasis"] = list(_vocal)
    edit_plan["_source_loudness_signal"] = dict(_loudness)
    # Face detections are consumed exactly once — to build the prompt signals
    # above. Once build_gemini_edit_prompt has returned, the raw face data has
    # no downstream reader (the Remotion composition renders motion_graphics
    # against the canvas via resolveMGPosition; no face lookup happens at
    # render time). Do NOT stash onto edit_plan — it would be dead weight.
    analysis = build_analysis_from_gemini_recipe(edit_plan, duration=duration)
    has_burned_captions = infer_has_burned_captions(edit_plan, analysis, log_prefix="[generate-edit]")

    video_duration = float(analysis.get("duration") or 0)
    _dg_words = edit_plan.get("_deepgram_words", [])
    raw_remove_words = edit_plan.get("remove_words") or []

    # ── Guard: drop Gemini range cuts covering PROTECTED words ───────────────
    # The analysis-pass classification is authoritative. If Gemini tries to
    # range-cut a word the analysis classified as PROTECTED (content or
    # narrative peak), honor the classification and drop the range — anchors
    # rely on PROTECTED words surviving to output.
    if raw_remove_words and _protected and _dg_words:
        _protected_times = []
        for _pi in _protected:
            if 0 <= _pi < len(_dg_words):
                _w = _dg_words[_pi]
                _protected_times.append((
                    float(_w.get("start") or 0),
                    float(_w.get("end") or 0),
                    _pi,
                ))
        _filtered = []
        for _rw in raw_remove_words:
            if not isinstance(_rw, dict):
                continue
            if "start" in _rw and "end" in _rw and "word_index" not in _rw:
                try:
                    _rs = float(_rw["start"])
                    _re = float(_rw["end"])
                except (TypeError, ValueError):
                    continue
                _covers_protected = None
                for (_pws, _pwe, _pi) in _protected_times:
                    if _rs < _pwe and _re > _pws:
                        _covers_protected = _pi
                        break
                if _covers_protected is not None:
                    _pword = _dg_words[_covers_protected]
                    _pw_text = str(_pword.get("punctuated_word") or _pword.get("word") or "").strip()
                    print(
                        f"[generate-edit] Dropping Gemini range cut {_rs:.2f}-{_re:.2f}s "
                        f"— covers PROTECTED word [{_covers_protected}] '{_pw_text}' "
                        f"(classification-authoritative guard)",
                        flush=True,
                    )
                    continue
            _filtered.append(_rw)
        raw_remove_words = _filtered

    # ── Merge mechanical + analysis cuts into remove_words ───────────────────
    # Gemini's main call can't cut word-level (its CUTTABLE enum is empty by
    # design). All word-level cuts came from the two upstream passes and need
    # to be applied to the actual render via remove_words.
    _pre_cut_injections = []
    for idx in sorted(_mech_word_cuts):
        _pre_cut_injections.append({
            "word_index": idx,
            "reason": _mech_reasons.get(idx) or "mechanical",
        })
    for idx in sorted(_anal_word_cuts):
        _pre_cut_injections.append({
            "word_index": idx,
            "reason": "contextual",
        })
    for (rs, re_) in _mech_range_cuts:
        _pre_cut_injections.append({"start": rs, "end": re_, "reason": "dead_air"})
    if _pre_cut_injections:
        raw_remove_words = list(raw_remove_words) + _pre_cut_injections
        edit_plan["remove_words"] = raw_remove_words
        print(
            f"[generate-edit] Merged pre-pass cuts into remove_words: "
            f"{len(_mech_word_cuts)} mechanical words, {len(_anal_word_cuts)} analysis words, "
            f"{len(_mech_range_cuts)} dead-air ranges",
            flush=True,
        )

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
            if "word_index" in item:
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
        # Adapt tightening threshold to speech rate AND pacing.
        # Lower gap = more aggressive silence removal = tighter jump cuts.
        # Captions app aggressively removes ALL dead air — we match that.
        _pacing = str(edit_plan.get("pacing") or "fast").lower()
        if _pacing == "fast":
            _speech_gap = 0.06  # ultra-tight — gaps become noticeable at 0.75x slow-mo
        elif _pacing == "medium":
            _speech_gap = 0.10
        else:
            _speech_gap = 0.13  # slow pacing — more breathing room
        if len(_dg_words) >= 5:
            _first_t = float(_dg_words[0].get("start", 0))
            _last_t = float(_dg_words[-1].get("end", 0))
            _speech_dur = _last_t - _first_t
            if _speech_dur > 0:
                _wpm = len(_dg_words) / (_speech_dur / 60.0)
                if _wpm > 180:
                    _speech_gap += 0.05  # very fast talker — widen slightly to preserve phrasing
                elif _wpm > 150:
                    _speech_gap += 0.03  # fast talker
                elif _wpm < 100:
                    _speech_gap = max(0.08, _speech_gap - 0.03)  # slow talker — even tighter
                print(f"[tighten] Speech rate: {_wpm:.0f} wpm, pacing={_pacing} → gap threshold: {_speech_gap*1000:.0f}ms", flush=True)
        print(
            f"[generate-edit] Building clips: {len(_dg_words)} words, "
            f"{len(normalized_remove_words)} Gemini removals + deterministic tightening",
            flush=True,
        )
        validated_cuts, _removed_word_indices = build_clips_from_words(_dg_words, normalized_remove_words, max_silence_gap=_speech_gap, video_duration=video_duration)
        edit_plan["_removed_word_indices"] = _removed_word_indices
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
    # contains that word's timestamp and set transition_out on it. Fail hard on
    # any invalid reference: no silent skips, no rewires to nearby kept words.
    raw_transitions = edit_plan.get("transitions") or []
    if raw_transitions and _dg_words:
        # Transitions = pack PascalCase names (CardSwipe, ShutterFlash, …).
        _valid_tr_types = {
            "CardSwipe", "ZoomThrough", "SlideOver", "Stack", "CrossfadeZoom",
            "ShutterFlash", "LightLeak", "StepPush", "NewspaperWipe", "FilmStrip",
            "SceneTitle",
        }
        # Build set of removed word indices so we can reject transitions that
        # target removed words (Gemini must pick kept words).
        _tr_removed = set()
        for rw in (edit_plan.get("remove_words") or []):
            if "word_index" in rw:
                _tr_removed.add(int(rw["word_index"]))
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
                raise ValueError(
                    f"transitions[{_ti}] ({tr_type}) after_word_index={awi} is out of "
                    f"bounds (transcript has {len(_dg_words)} words)"
                )
            if awi in _tr_removed:
                raise ValueError(
                    f"transitions[{_ti}] ({tr_type}) after_word_index={awi} targets a "
                    f"REMOVED word. Move this transition to a word index that was kept "
                    f"(not listed in remove_words)."
                )
            word_end = float(_dg_words[awi].get("end") or 0)
            # Build extras dict — copy through all component-specific props
            _extras = {
                k: v for k, v in tr.items()
                if k not in ("type", "after_word_index") and v is not None
            }
            # Find the clip that contains this word (with 50ms tolerance). Fail
            # if no clip does — that means the transition target word ended up
            # outside every kept clip (physically impossible if awi is kept).
            _applied = False
            for ci, clip in enumerate(validated_cuts):
                cs = float(clip["source_start"])
                ce = float(clip["source_end"])
                if cs - 0.05 <= word_end <= ce + 0.05 and ci < len(validated_cuts) - 1:
                    clip["transition_out"] = tr_type
                    if _extras:
                        clip["_transition_extras"] = _extras
                    print(f"[generate-edit] Transition '{tr_type}' applied to clip {ci} (after word {awi})", flush=True)
                    _applied = True
                    break
            if not _applied:
                raise ValueError(
                    f"transitions[{_ti}] ({tr_type}) after_word_index={awi} "
                    f"(t={word_end:.3f}s) does not land in any kept clip, or lands in "
                    f"the LAST clip (there is no subsequent clip to transition to). "
                    f"Pick a word that ends inside clips[0..N-2]."
                )

    # Transition count/variety is Gemini's decision — the prompt teaches restraint.

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
    if str(edit_plan.get("aspect_ratio")) != "9:16":
        raise ValueError(
            f"aspect_ratio must be '9:16' (only supported output format), got "
            f"{edit_plan.get('aspect_ratio')!r}"
        )

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
        _br_dur = _br_end - _br_ts
        if _br_dur <= 0:
            continue
        print(f"[broll] Word-index timing: [{_sw_kept}]-[{_ew_kept}] → {_br_ts:.3f}s-{_br_end:.3f}s ({_br_dur:.2f}s)", flush=True)
        if not (math.isfinite(_br_ts) and math.isfinite(_br_dur)):
            continue
        if _br_ts < 0 or _br_dur <= 0:
            continue
        if video_duration > 0 and _br_ts >= video_duration:
            continue
        validated_broll.append({
            "keyword": _br_kw,
            "timestamp": _br_ts,
            "duration": _br_dur,
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
        "HormoziPopIn", "GlitchHighlight", "EmojiPop", "NegativeFlash", "PaperII",
        "Prime", "Prism", "TypewriterReveal", "CinematicLetterpress", "Cove",
        "Dimidium", "EditorialPop", "Gadzhi", "Illuminate", "Lumen",
        "MagazineCutout", "Passage", "Pulse", "Quintessence", "Serif", "StaggerWave",
    }
    _valid_color_types = {
        "CinematicGrade", "BleachBypass", "VintageFilm", "DreamHaze", "ChromaSplit",
        "VignettePulse", "InvertStrike", "CineMono", "GoldenHour", "FilmGrain",
        "Portra", "NeoNoir",
    }
    _valid_zoom_types = {
        "SmoothPush", "SnapReframe", "FocusWindow", "StepZoom", "LetterboxPush",
        "StageZoom", "DepthPull",
    }
    _valid_mg_types = {
        "LowerThird", "AnnotationArrow", "BRollFrame", "ChartReveal", "ChatThread",
        "ComparisonSplit", "Notification", "ProgressBar", "QuoteCard", "RecordingFrame",
        "StatCard", "StickyNotes", "Toggle", "TornPaper",
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
        "torn_paper", "sticky_note", "quote_card", "lower_third", "caption_match",
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

    # caption_position_segments — covers [0, duration], no gaps/overlaps,
    # boundaries on word boundaries (±100ms tolerance for float rounding).
    _cps_raw = edit_plan.get("caption_position_segments")
    if not isinstance(_cps_raw, list) or not _cps_raw:
        raise ValueError("caption_position_segments must be a non-empty array")
    _word_boundary_times = set()
    for _w in _dg_words:
        _word_boundary_times.add(round(float(_w.get("start") or 0), 2))
        _word_boundary_times.add(round(float(_w.get("end") or 0), 2))
    _word_boundary_times.add(0.0)
    _word_boundary_times.add(round(float(video_duration), 2))
    _validated_cps = []
    for _i, _seg in enumerate(_cps_raw):
        if not isinstance(_seg, dict):
            raise ValueError(f"caption_position_segments[{_i}] must be an object")
        try:
            _fs = float(_seg["from_seconds"])
            _ts = float(_seg["to_seconds"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f"caption_position_segments[{_i}] needs numeric from_seconds and to_seconds"
            )
        _pos = str(_seg.get("position") or "").strip()
        if _pos not in ("top", "center", "bottom"):
            raise ValueError(
                f"caption_position_segments[{_i}].position must be 'top'|'center'|'bottom', got {_pos!r}"
            )
        if _ts <= _fs:
            raise ValueError(f"caption_position_segments[{_i}] has to_seconds <= from_seconds")
        _validated_cps.append({"from_seconds": _fs, "to_seconds": _ts, "position": _pos})
    _validated_cps.sort(key=lambda x: x["from_seconds"])
    if abs(_validated_cps[0]["from_seconds"] - 0.0) > 0.05:
        raise ValueError(
            f"caption_position_segments must start at 0.0, got {_validated_cps[0]['from_seconds']}"
        )
    if abs(_validated_cps[-1]["to_seconds"] - float(video_duration)) > 0.25:
        raise ValueError(
            f"caption_position_segments must end at {video_duration}, got {_validated_cps[-1]['to_seconds']}"
        )
    for _i in range(1, len(_validated_cps)):
        _prev_end = _validated_cps[_i - 1]["to_seconds"]
        _curr_start = _validated_cps[_i]["from_seconds"]
        if abs(_curr_start - _prev_end) > 0.05:
            raise ValueError(
                f"caption_position_segments have a gap/overlap between segment {_i-1} "
                f"(ends {_prev_end}) and segment {_i} (starts {_curr_start})"
            )
    # Boundaries MUST coincide with a real word boundary — mid-word flips cause
    # visual glitches. Gemini sees every word's start/end in the transcript and
    # must pick one of those exact times (rounded to 2 decimals, same rounding
    # as `_word_boundary_times`). No tolerance window, no silent snap — the
    # boundary is either on a word or it isn't.
    for _i in range(1, len(_validated_cps)):
        _b = round(float(_validated_cps[_i]["from_seconds"]), 2)
        if _b not in _word_boundary_times:
            _nearest = min(_word_boundary_times, key=lambda w: abs(w - _b))
            raise ValueError(
                f"caption_position_segments[{_i}].from_seconds={_b}s is not a real "
                f"word boundary (nearest valid boundary is {_nearest:.2f}s, gap "
                f"{abs(_nearest-_b):.3f}s). Every segment boundary must match one of "
                f"the start/end timestamps from the word list, rounded to 2 decimals."
            )
        # Ensure the adjacent segment's to_seconds matches exactly — no drift.
        _validated_cps[_i]["from_seconds"] = _b
        _validated_cps[_i - 1]["to_seconds"] = _b
    edit_plan["caption_position_segments"] = _validated_cps
    print(
        f"[caption-segments] {len(_validated_cps)} segment(s): "
        + ", ".join(f"[{s['from_seconds']:.2f}-{s['to_seconds']:.2f}]={s['position']}" for s in _validated_cps),
        flush=True,
    )

    # color_effect — object or null. Pulses use source-time `peak_at_seconds`.
    _ce_raw = edit_plan.get("color_effect")
    if _ce_raw is None:
        edit_plan["color_effect"] = None
    elif isinstance(_ce_raw, dict):
        _ct = str(_ce_raw.get("type") or "").strip()
        if _ct not in _valid_color_types:
            raise ValueError(f"color_effect.type must be one of {sorted(_valid_color_types)}, got {_ct!r}")
        _ce_out = {"type": _ct}
        try:
            _ce_out["intensity"] = max(0.0, min(1.5, float(_ce_raw.get("intensity"))))
        except (TypeError, ValueError):
            raise ValueError("color_effect.intensity must be a number in [0.0, 1.5]")
        _timing = _ce_raw.get("timing")
        if not isinstance(_timing, dict):
            raise ValueError("color_effect.timing must be an object")
        _mode = str(_timing.get("mode") or "").strip()
        if _mode not in ("persistent", "pulsed"):
            raise ValueError(f"color_effect.timing.mode must be 'persistent'|'pulsed', got {_mode!r}")
        # InvertStrike can only render as pulsed.
        if _ct == "InvertStrike" and _mode != "pulsed":
            raise ValueError(
                "color_effect.type 'InvertStrike' REQUIRES timing.mode='pulsed' with at least one pulse"
            )
        if _mode == "persistent":
            _ce_out["timing"] = {"mode": "persistent"}
            if "fadeInFrames" in _timing:
                _ce_out["timing"]["fadeInFrames"] = int(_timing["fadeInFrames"])
        else:
            _pulses = _timing.get("pulses")
            if not isinstance(_pulses, list) or not _pulses:
                raise ValueError("color_effect.timing.pulses must be a non-empty array for pulsed mode")
            _out_pulses = []
            for _pi, _p in enumerate(_pulses):
                if not isinstance(_p, dict):
                    raise ValueError(f"color_effect.timing.pulses[{_pi}] must be an object")
                try:
                    _peak_s = float(_p["peak_at_seconds"])
                except (KeyError, TypeError, ValueError):
                    raise ValueError(
                        f"color_effect.timing.pulses[{_pi}].peak_at_seconds must be a float (source seconds)"
                    )
                if _peak_s < 0 or (video_duration > 0 and _peak_s > video_duration):
                    raise ValueError(
                        f"color_effect.timing.pulses[{_pi}].peak_at_seconds ({_peak_s}) "
                        f"outside source [0, {video_duration}]"
                    )
                _out_pulses.append({
                    "peak_at_seconds": _peak_s,
                    "attackFrames": int(_p.get("attackFrames") or 3),
                    "holdFrames": int(_p.get("holdFrames") or 4),
                    "releaseFrames": int(_p.get("releaseFrames") or 12),
                    "intensity": float(_p.get("intensity", 1.0)),
                })
            _ce_out["timing"] = {"mode": "pulsed", "pulses": _out_pulses}
        # Pass through component-specific extras verbatim.
        for _ek in ("grain", "grainStrength", "sunWash", "palette", "offset", "angle", "drift",
                    "baseDarkness", "baseInnerPct", "color", "punch", "redWeight", "greenWeight",
                    "blueWeight", "contrastBoost", "grainScale", "grainOctaves", "flicker",
                    "monochrome", "grainStep", "dustDensity", "scratchDensity"):
            if _ek in _ce_raw:
                _ce_out[_ek] = _ce_raw[_ek]
        edit_plan["color_effect"] = _ce_out
    else:
        raise ValueError(f"color_effect must be an object or null, got {type(_ce_raw).__name__}")

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
    # Build kept-word set once if emphasis validator hasn't yet (MG validator
    # runs before emphasis). This mirrors the same constraint: only kept words
    # anchor overlays.
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
            raise ValueError(
                f"motion_graphics[{_i}].start_word_index={_sw} ({_wt!r}) targets "
                f"a REMOVED word. Anchor to a kept word."
            )
        if _ew not in _mg_kept_set:
            _wt = str(_dg_words[_ew].get("punctuated_word") or _dg_words[_ew].get("word") or "").strip()
            raise ValueError(
                f"motion_graphics[{_i}].end_word_index={_ew} ({_wt!r}) targets "
                f"a REMOVED word. Anchor to a kept word."
            )
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
        # Derive the source-time window from the anchor words.
        _sw_start = round(float(_dg_words[_sw].get("start") or 0), 3)
        _ew_end = round(float(_dg_words[_ew].get("end") or 0), 3)
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

    raw_curve = edit_plan.get("speed_curve", "none")
    if raw_curve == "none" or raw_curve is None:
        speed_curve = None
    elif not isinstance(raw_curve, list):
        raise ValueError(
            f"speed_curve must be 'none' or an array of keypoints, got "
            f"{type(raw_curve).__name__}"
        )
    else:
        # Strict: every keypoint must have numeric t + speed in [0.25, 2.0].
        # No silent coercion; no dropping malformed entries.
        speed_curve = []
        for _kpi, kp in enumerate(raw_curve):
            if not isinstance(kp, dict):
                raise ValueError(f"speed_curve[{_kpi}] must be an object")
            if "t" not in kp or ("speed" not in kp and "s" not in kp):
                raise ValueError(
                    f"speed_curve[{_kpi}] missing required keys 't' and 'speed'"
                )
            try:
                t = float(kp["t"])
                s = float(kp.get("speed") if "speed" in kp else kp.get("s"))
            except (TypeError, ValueError):
                raise ValueError(
                    f"speed_curve[{_kpi}] t/speed must be numbers"
                )
            if t < 0:
                raise ValueError(
                    f"speed_curve[{_kpi}].t={t} must be >= 0"
                )
            if not (0.25 <= s <= 2.0):
                raise ValueError(
                    f"speed_curve[{_kpi}].speed={s} is outside the supported "
                    f"range 0.25-2.0. Adjust the keypoint or drop it."
                )
            speed_curve.append({"t": t, "speed": s})
        if len(speed_curve) == 0:
            speed_curve = None
        elif len(speed_curve) == 1:
            raise ValueError(
                "speed_curve must have at least 2 keypoints to define a ramp "
                "(got 1). Either add a second keypoint or use 'none'."
            )
        else:
            speed_curve.sort(key=lambda x: x["t"])

            # Gemini already has word-level timestamps at 3-decimal
            # precision and places keypoints directly on them. Any
            # rounding error is ≤1 frame (33ms) — imperceptible in a
            # speed ramp. The old snapping code corrected this tiny
            # error but caused a catastrophic bug: when a snap-back
            # keypoint fell in a dead-air gap (removed silence between
            # clips), it got pulled onto its partner's timestamp and
            # the ramp pair collapsed into a single keypoint. The
            # densifier then saw a long gap and filled it with a
            # gradual 10-second drift instead of a sharp snap. Gemini
            # is the expert — trust its timestamps exactly.

        if speed_curve and len(speed_curve) >= 2:
            # MIN_RAMP_SECS spreading was removed. It existed to prevent
            # jarring abrupt speed changes under hold-and-snap semantics
            # (where a 0.7→1.3 jump over 0.3s was an instant snap). With
            # linear interpolation, the same keypoints become a smooth
            # 0.3s glide which sounds fine. The spreading was also moving
            # keypoints away from word boundaries, defeating the snap-to-
            # word fix.

            # Densify with linear interpolation. BUDGETED allocation: a
            # global cap of 50 intermediate keypoints distributed across
            # ramps proportional to each ramp's speed delta. This bounds
            # total sub-clip count regardless of how many keypoints
            # Gemini sends, making render time predictable. Steeper ramps
            # get more sub-steps where smoothness matters most.
            _gemini_kp_count = len(speed_curve)
            speed_curve = densify_speed_curve(speed_curve, max_intermediates=150, min_step=0.08)
            if len(speed_curve) > _gemini_kp_count:
                print(
                    f"[speed-curve] Densified {_gemini_kp_count} Gemini keypoints → "
                    f"{len(speed_curve)} interpolated keypoints (smooth ramping)",
                    flush=True,
                )

            speeds = [kp["speed"] for kp in speed_curve]
            print(
                f"[generate-edit] Speed curve: {len(speed_curve)} keypoints, range "
                f"{min(speeds):.2f}x - {max(speeds):.2f}x",
                flush=True,
            )
    edit_plan["_parsed_speed_curve"] = speed_curve

    thumbnail_timestamp = None
    try:
        if edit_plan.get("thumbnail_timestamp") is not None:
            thumbnail_timestamp = max(0.0, float(edit_plan.get("thumbnail_timestamp")))
            if video_duration > 0:
                thumbnail_timestamp = min(thumbnail_timestamp, video_duration)
    except Exception:
        thumbnail_timestamp = None
    edit_plan["thumbnail_timestamp"] = thumbnail_timestamp

    hook_clip = None
    raw_hook = edit_plan.get("hook_clip")
    if isinstance(raw_hook, dict):
        try:
            hook_start = max(0.0, float(raw_hook.get("source_start")))
            hook_end = max(0.0, float(raw_hook.get("source_end")))
            if video_duration > 0:
                hook_end = min(hook_end, video_duration)
            hook_dur = hook_end - hook_start
            if 0.5 <= hook_dur <= 5.0:
                hook_clip = {
                    "source_start": round(hook_start, 3),
                    "source_end": round(hook_end, 3),
                }
            else:
                print(f"[generate-edit] Hook clip duration {hook_dur:.2f}s out of range — skipping", flush=True)
        except Exception:
            hook_clip = None
    if hook_clip:
        _hs = float(hook_clip["source_start"])
        _he = float(hook_clip["source_end"])
        print(f"[hook] Hook timestamps: {_hs:.2f}-{_he:.2f} ({_he - _hs:.2f}s)", flush=True)
    edit_plan["hook_clip"] = hook_clip
    edit_plan["cuts"] = list(validated_cuts)

    # ── Parse emphasis moments — strict, with explicit visual-layer bindings ─
    raw_emphasis = edit_plan.get("emphasis_moments")
    if raw_emphasis is None:
        raw_emphasis = []
    if not isinstance(raw_emphasis, list):
        raise ValueError("emphasis_moments must be an array")
    _valid_em_types = {"punchline", "statement", "question", "reaction", "transition", "revelation"}
    emphasis_moments = []
    # Pre-compute the kept-word set so each emphasis can verify its word_indices
    # survive remove_words. _removed_word_indices is populated upstream by
    # build_clips_from_words and covers both word_index removals and words
    # whose timestamps fell inside a start/end range removal.
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
        for _k, _wi_val in enumerate(_wis):
            if _wi_val < 0 or _wi_val >= len(_dg_words):
                raise ValueError(
                    f"emphasis_moments[{_ei}].word_indices[{_k}]={_wi_val} is out "
                    f"of range [0, {len(_dg_words)-1}]."
                )
            if _wi_val not in _kept_word_indices:
                _w = _dg_words[_wi_val]
                _wt = str(_w.get("punctuated_word") or _w.get("word") or "").strip()
                raise ValueError(
                    f"emphasis_moments[{_ei}].word_indices[{_k}]={_wi_val} "
                    f"({_wt!r}) targets a word that was REMOVED via remove_words. "
                    f"Emphasize only words that survive your removal list."
                )
        # Derive t from word_indices[0].start — Gemini no longer emits `t`
        # (schema-level constraint from v34: the two could disagree so we
        # removed the degree of freedom). Because word_indices[0] is a kept
        # word, the derived t is guaranteed to land inside a kept clip.
        _anchor_word = _dg_words[_wis[0]]
        t = round(float(_anchor_word.get("start") or 0), 2)
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
        # Visual layer bindings — ALL THREE fields are required (value or null).
        if "zoom_effect" not in em:
            raise ValueError(f"emphasis_moments[{_ei}] missing zoom_effect (emit null if no zoom)")
        if "color_pulse" not in em:
            raise ValueError(f"emphasis_moments[{_ei}] missing color_pulse (emit false if none)")
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
            _ze_out = {"type": _zt, "events": _ze_raw.get("events") or []}
            for _ek in ("firstStage", "secondStage", "windowScale", "borderWidth",
                        "borderColor", "bgScale", "edgeBlur", "frameLines", "maxBarHeight"):
                if _ek in _ze_raw:
                    _ze_out[_ek] = _ze_raw[_ek]
        _cp = em.get("color_pulse")
        if not isinstance(_cp, bool):
            raise ValueError(
                f"emphasis_moments[{_ei}].color_pulse must be a boolean, got {_cp!r}"
            )
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
            "color_pulse": _cp,
            "motion_graphic": _mg_out,
        })
    emphasis_moments.sort(key=lambda x: x["t"])

    # Cross-consistency: if any emphasis has color_pulse=true, color_effect
    # must be non-null AND pulsed. We check here after color_effect validation
    # has already run.
    _any_em_pulse = any(em["color_pulse"] for em in emphasis_moments)
    _ce_final = edit_plan.get("color_effect")
    if _any_em_pulse:
        if not _ce_final:
            raise ValueError(
                "One or more emphasis_moments.color_pulse=true but color_effect is null. "
                "Either set all color_pulse to false, or emit a pulsed color_effect."
            )
        if _ce_final.get("timing", {}).get("mode") != "pulsed":
            raise ValueError(
                "One or more emphasis_moments.color_pulse=true but color_effect.timing.mode "
                "is not 'pulsed'. Change timing.mode to 'pulsed' or set all color_pulse to false."
            )

    # High-intensity emphasis pacing: no two within 2.5s of each other.
    _high = [em for em in emphasis_moments if em["intensity"] == "high"]
    for _i in range(1, len(_high)):
        _gap = _high[_i]["t"] - _high[_i - 1]["t"]
        if _gap < 2.5:
            raise ValueError(
                f"High-intensity emphasis moments at {_high[_i-1]['t']:.2f}s and "
                f"{_high[_i]['t']:.2f}s are {_gap:.2f}s apart (minimum 2.5s)."
            )

    # Zoom collision: each clip (source_start..source_end) can host at most ONE
    # emphasis_moment with a zoom_effect. Two emphasis moments in the same clip
    # with competing zoom_effect specs would silently overwrite one another at
    # render time (the per-clip wrapper holds a single zoom component). Fail
    # here so Gemini sees the error and either consolidates them or drops one.
    _clip_zoom_owner = {}
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
            raise ValueError(
                f"emphasis_moments[{_ei}].t={em['t']:.2f}s with zoom_effect falls "
                f"OUTSIDE every validated clip — t lands in a cut/removed segment. "
                f"Move t inside a clip's source range or drop this emphasis."
            )
        if _owning_clip in _clip_zoom_owner:
            _prev = _clip_zoom_owner[_owning_clip]
            raise ValueError(
                f"emphasis_moments[{_ei}] and [{_prev}] both place zoom_effect on clip "
                f"{_owning_clip} ({validated_cuts[_owning_clip]['source_start']:.2f}-"
                f"{validated_cuts[_owning_clip]['source_end']:.2f}s). Only one zoom can "
                f"run per clip — merge their events into a single zoom_effect on the "
                f"first emphasis, or drop one of the zooms."
            )
        _clip_zoom_owner[_owning_clip] = _ei

    for em in emphasis_moments:
        _layers = []
        if em["zoom_effect"]: _layers.append(f"zoom={em['zoom_effect']['type']}")
        if em["color_pulse"]: _layers.append("pulse")
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
            raise ValueError(
                f"text_overlays[{_i}].start_word_index={_swi} ({_wt!r}) targets "
                f"a REMOVED word. Anchor to a kept word or drop this overlay."
            )
        try:
            _du = float(_ov["duration_seconds"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f"text_overlays[{_i}] needs numeric duration_seconds"
            )
        if _du < 0.3 or _du > 10.0:
            raise ValueError(f"text_overlays[{_i}].duration_seconds out of range 0.3..10.0")
        _source_start = round(float(_dg_words[_swi].get("start") or 0), 3)
        _entry = {
            "variant": _var,
            "start_word_index": _swi,
            "_source_start": _source_start,
            "duration_seconds": _du,
        }
        if _var == "torn_paper":
            for _p in ("topText", "bottomText"):
                if not isinstance(_ov.get(_p), str) or not _ov[_p].strip():
                    raise ValueError(f"text_overlays[{_i}](torn_paper) missing required prop {_p!r}")
                _entry[_p] = _EMOJI_RE.sub("", str(_ov[_p])).strip()
        elif _var == "sticky_note":
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
        elif _var == "lower_third":
            for _p in ("name", "title"):
                if not isinstance(_ov.get(_p), str) or not _ov[_p].strip():
                    raise ValueError(f"text_overlays[{_i}](lower_third) missing required prop {_p!r}")
                _entry[_p] = _EMOJI_RE.sub("", str(_ov[_p])).strip()
        elif _var == "caption_match":
            if not isinstance(_ov.get("text"), str) or not _ov["text"].strip():
                raise ValueError(f"text_overlays[{_i}](caption_match) missing required prop 'text'")
            _entry["text"] = _EMOJI_RE.sub("", str(_ov["text"])).strip()
            _pos = str(_ov.get("position") or "").strip()
            if _pos not in ("top", "center", "bottom"):
                raise ValueError(
                    f"text_overlays[{_i}](caption_match).position must be 'top'|'center'|'bottom'"
                )
            _entry["position"] = _pos
        _to_validated.append(_entry)
    edit_plan["text_overlays"] = _to_validated

    # Non-overlap: no two text_overlays may overlap in source time (since both
    # overlays are anchored to source-time word starts + duration_seconds).
    for _i in range(len(_to_validated)):
        _a = _to_validated[_i]
        _a_start = _a["_source_start"]
        _a_end = _a_start + _a["duration_seconds"]
        for _j in range(_i + 1, len(_to_validated)):
            _b = _to_validated[_j]
            _b_start = _b["_source_start"]
            _b_end = _b_start + _b["duration_seconds"]
            if _a_start < _b_end and _b_start < _a_end:
                raise ValueError(
                    f"text_overlays overlap: #{_i} ({_a['variant']} "
                    f"{_a_start:.2f}-{_a_end:.2f}s) collides with #{_j} "
                    f"({_b['variant']} {_b_start:.2f}-{_b_end:.2f}s)"
                )

    # Non-overlap: text_overlays must not overlap any emphasis motion_graphic
    # window. Emphasis MG windows are centered slightly before the moment's t
    # (mirrors the render-time placement: 25% pre-roll, 75% post-roll).
    for _to in _to_validated:
        _to_start = _to["_source_start"]
        _to_end = _to_start + _to["duration_seconds"]
        for _em in emphasis_moments:
            if not _em["motion_graphic"]:
                continue
            _em_dur = float(_em["duration"])
            _em_mg_start = max(0.0, _em["t"] - _em_dur * 0.25)
            _em_mg_end = _em_mg_start + _em_dur
            if _to_start < _em_mg_end and _em_mg_start < _to_end:
                raise ValueError(
                    f"text_overlay ({_to['variant']} {_to_start:.2f}-{_to_end:.2f}s) overlaps "
                    f"emphasis motion_graphic ({_em['motion_graphic']['type']} "
                    f"{_em_mg_start:.2f}-{_em_mg_end:.2f}s at emphasis t={_em['t']:.2f}s)"
                )

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
    # Build-up sounds require this much kept-clip time BEFORE the trigger
    # word or the build gets truncated at render and the effect is lost.
    # Values mirror _SFX_ONSET_OFFSETS for the 5 build-bearing sounds.
    _SFX_MIN_PRE_TRIGGER = {
        "boom":         0.440,
        "thunder":      0.734,
        "drum_roll":    1.657,
        "reverse":      1.372,
        "sad_trombone": 1.290,
    }
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
            raise ValueError(
                f"sound_effects[{_si}].word_index={_wi} ({_wt!r}) targets a word "
                f"that was REMOVED via remove_words. Pick a kept word or drop "
                f"this SFX — the viewer never hears the trigger otherwise."
            )
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
        # Build-duration check: the trigger word must have enough kept-clip time
        # BEFORE it to accommodate the sound's build. Fails hard if the build
        # would get truncated at render.
        if sound in _SFX_MIN_PRE_TRIGGER:
            _needed = _SFX_MIN_PRE_TRIGGER[sound]
            _clip_start = None
            for _cc in validated_cuts:
                _cs = float(_cc["source_start"])
                _ce = float(_cc["source_end"])
                if _cs <= t <= _ce:
                    _clip_start = _cs
                    break
            if _clip_start is None:
                raise ValueError(
                    f"sound_effects[{_si}] ({sound}) trigger word {word!r} at "
                    f"t={t:.2f}s is not inside any kept clip."
                )
            _pre_trigger = t - _clip_start
            if _pre_trigger < _needed:
                raise ValueError(
                    f"sound_effects[{_si}] ({sound}) needs {_needed:.2f}s of "
                    f"kept-clip time BEFORE the trigger word, but word_index="
                    f"{_wi} ({word!r}) has only {_pre_trigger:.2f}s of clip "
                    f"before it (clip starts at {_clip_start:.2f}s, word starts "
                    f"at {t:.2f}s). Move this SFX to a trigger word that's "
                    f"later in its clip, or pick an instant-onset sound "
                    f"(hit/ching/ding/pop/click/camera_shutter/typing)."
                )
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

    # Transitions — one of the 11 pack transitions (PascalCase). "none" kept
    # as a valid sentinel for no transition.
    valid_transitions = {
        "none",
        "CardSwipe", "ZoomThrough", "SlideOver", "Stack", "CrossfadeZoom",
        "ShutterFlash", "LightLeak", "StepPush", "NewspaperWipe", "FilmStrip",
        "SceneTitle",
    }

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
        # Speed is Gemini's creative decision. Reject out-of-range instead of
        # silently clamping; this forces Gemini to emit a value inside the
        # documented range rather than sending something unrealistic.
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
            if not (0.25 <= speed <= 4.0):
                raise ValueError(
                    f"validated_cuts[{_ci}].speed={speed} is outside the "
                    f"documented range 0.25-4.0. Adjust the speed_curve keypoint "
                    f"that produced this value or remove the keypoint."
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
        final_cuts.append(_new_cut)

    # Zoom and color pulses are attached to each emphasis_moment explicitly by
    # Gemini (emphasis_moments[i].zoom_effect / color_pulse / motion_graphic).
    # No auto-SnapReframe, no auto-SmoothPush on hook. If Gemini didn't emit a
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

    # Compact transcript preview so the diff model can resolve word_index references
    # without being overwhelmed. Cap at ~3K chars; plan-diff doesn't need the full
    # transcript, just enough to ground timing-ish language in the change_request.
    transcript_preview = ""
    if isinstance(transcript, dict):
        words = transcript.get("words") or []
        if words:
            preview_words = [str(w.get("punctuated_word") or w.get("word") or "") for w in words[:300]]
            transcript_preview = " ".join(preview_words)[:3000]

    prompt_parts = [
        "You are editing a Promptly video-edit PLAN. The plan is a JSON document describing "
        "every decision that produced a rendered video. Top-level fields include: cuts, "
        "transitions, caption_style, caption_position_segments (list of {fromSec,toSec,position}), "
        "keywords, broll_clips, color_effect (with timing.pulses[].peak_at_seconds), "
        "text_overlays (each has a variant discriminator: torn_paper|sticky_note|quote_card|"
        "lower_third|caption_match), motion_graphics (with semantic anchor), emphasis_moments "
        "(each binds explicit zoom_effect / color_pulse / motion_graphic), sfx_placements, "
        "outro. The user has requested a change. Your job:\n\n"
        "1) CLASSIFY the request as one of:\n"
        "   - 'tweak': surgical change to specific fields (e.g. 'smaller captions', 'remove clip 3', "
        "'different caption style', 'remove the whoosh SFX on word X', 'move captions to top for "
        "the intro'). You MUST echo every other field byte-identical. Do NOT edit anything the user "
        "didn't explicitly ask to change.\n"
        "   - 'reinterpret': holistic re-direction (e.g. 'way more chaotic', 'darker vibe', "
        "'completely different feel'). Emit a fused_vibe string that combines the prior vibe with "
        "the new direction.\n"
        "   - 'needs_clarification': request is too vague to map to fields (e.g. 'make it better'). "
        "Emit a clear clarification_question — do NOT guess.\n\n"
        "2) For 'tweak': produce new_plan with ONLY the explicitly-requested changes. Preserve "
        "cuts, transitions, broll_clips (including pexels_video_id + pexels_file_url + "
        "clip_in/out), color_effect, sfx_placements, text_overlays, motion_graphics, "
        "emphasis_moments, caption_position_segments — everything else — unchanged. When you "
        "edit an emphasis_moment's color_pulse, you MUST keep the corresponding "
        "color_effect.timing.pulses[].peak_at_seconds consistent (the renderer validates "
        "cross-references and will fail hard on mismatch).\n\n"
        "3) Emit changed_fields: dotted paths of what you changed (e.g. ['caption_style', "
        "'cuts[3].speed', 'caption_position_segments[1].position', 'text_overlays[2].variant', "
        "'emphasis_moments[0].color_pulse']). Empty array for reinterpret or clarification.\n\n"
        "4) Emit human_summary: one sentence users can read (e.g. 'Changed caption style to "
        "minimal. Preserved 11 cuts, B-roll, color grade, and 2 text overlays.').\n\n"
        f"PRIOR VIBE: {old_vibe or '(unknown)'}\n\n"
        f"USER CHANGE REQUEST: {change_request}\n\n"
        f"OLD PLAN (JSON):\n{json.dumps(sanitized_old_plan, separators=(',', ':'))}\n\n",
    ]
    if transcript_preview:
        prompt_parts.append(f"TRANSCRIPT PREVIEW (first 300 words for word_index grounding):\n{transcript_preview}\n\n")
    prompt_parts.append(
        "Respond with a single JSON object matching this shape:\n"
        "{\n"
        '  "classification": "tweak" | "reinterpret" | "needs_clarification",\n'
        '  "clarification_question": string | null,\n'
        '  "new_plan": <full edit plan object> | null,\n'
        '  "fused_vibe": string | null,\n'
        '  "changed_fields": [string],\n'
        '  "human_summary": string\n'
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
            max_output_tokens=8192,
            response_mime_type="application/json",
            thinking_config=genai_types.ThinkingConfig(thinking_level="LOW"),
        ),
    )
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        raise RuntimeError("Empty plan-diff response from Gemini")
    parsed = json.loads(text) if text.startswith("{") else extract_json(text)
    if not isinstance(parsed, dict):
        raise RuntimeError("Plan-diff response is not a JSON object")

    classification = str(parsed.get("classification") or "").strip()
    if classification not in ("tweak", "reinterpret", "needs_clarification"):
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

    print(f"[plan-diff] classification={classification} in {time.time()-_t0:.1f}s", flush=True)
    return {
        "classification": classification,
        "clarification_question": parsed.get("clarification_question"),
        "new_plan": parsed.get("new_plan"),
        "fused_vibe": parsed.get("fused_vibe"),
        "changed_fields": parsed.get("changed_fields") or [],
        "human_summary": str(parsed.get("human_summary") or "Updated your video."),
    }


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
    "sad_trombone":      1.290,
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
        "-movflags", "+faststart",
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

            _raw.append({
                "ts": _cand_ts,
                "has_face": True,
                "face_conf": _face_conf,
                "area_ratio": _area_ratio,
                "center": _center_score,
                "lap_var": _lap_var,
                "mean_lum": _mean_lum,
                "eye_score": _eye_score,
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

            _total = (
                0.10 * _conf_score
                + 0.10 * _area_score
                + 0.05 * _r["center"]
                + 0.20 * _sharp_score
                + 0.10 * _bright_score
                + 0.20 * _r["eye_score"]
                + 0.25 * _proximity
            )
            _breakdown = {
                "has_face": True,
                "conf": _conf_score, "area": _area_score, "center": _r["center"],
                "sharp": _sharp_score, "bright": _bright_score, "eye": _r["eye_score"],
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
            f"prox={_winner_breakdown['proximity']:.2f}",
            flush=True,
        )
        # Log top 3 candidates for debugging — helps diagnose unexpected picks
        for _idx, (_s, _ts, _b) in enumerate(_scored[:3]):
            if _b.get("has_face"):
                print(
                    f"[thumbnail]   #{_idx+1} t={_ts:.3f}s score={_s:.3f} "
                    f"sharp={_b['sharp']:.2f} bright={_b['bright']:.2f} "
                    f"eye={_b['eye']:.2f} prox={_b['proximity']:.2f}",
                    flush=True,
                )

    return _data, "image/jpeg"


def fetch_broll_clip(broll_entry, duration_needed, work_dir, dialogue_reason=""):
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
            score += _tag_matches * 10
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
            try:
                _pick_client = _get_genai_client()
                _dialogue_ctx = dialogue_reason or keyword
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
                _content_parts.append(
                    f'\nThe viewer hears: "{_dialogue_ctx}"\n'
                    f'Which clip would feel most natural playing on screen while the viewer hears those words? '
                    f'B-roll doesn\'t need to show the exact scene — it just needs to visually connect to what the speaker is describing. '
                    f'Pick the strongest match. Reply with ONLY the option number. '
                    f'NONE only if every option is completely unrelated to the words.'
                )

                _pick_t0 = time.time()
                _pick_resp = _pick_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=_content_parts,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=128,
                        thinking_config=genai_types.ThinkingConfig(thinking_budget=32),
                    ),
                )
                _pick_elapsed = time.time() - _pick_t0
                _pick_text = str(getattr(_pick_resp, "text", "") or "").strip().upper()

                if "NONE" in _pick_text:
                    print(f"[broll] Gemini visual pick: NONE matched in {_pick_elapsed:.1f}s for '{keyword}' — skipping (no fallback)", flush=True)
                    return None
                else:
                    _pick_num = None
                    for _ch in _pick_text:
                        if _ch.isdigit():
                            _pick_num = int(_ch)
                            break
                    if _pick_num and _pick_num in _poster_idx_map:
                        _winner_idx = _poster_idx_map[_pick_num]
                        _top_n[_winner_idx]["score"] += 50
                        print(f"[broll] Gemini visual pick: #{_pick_num} ('{_top_n[_winner_idx].get('slug_desc','')}') in {_pick_elapsed:.1f}s for '{keyword}'", flush=True)
                    else:
                        print(f"[broll] Gemini visual pick: response='{_pick_text}' in {_pick_elapsed:.1f}s for '{keyword}'", flush=True)
            except Exception as _pick_err:
                print(f"[broll] Gemini visual pick error: {_pick_err}", flush=True)

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
    safe_kw = re.sub(r"[^a-z0-9]", "_", keyword.lower())[:30] if keyword else "broll"
    dest = os.path.join(work_dir, f"broll_{safe_kw}.mp4")

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

    _MAX_BROLL_BYTES = 25 * 1024 * 1024  # 25MB cap — prevents 100MB+ 4K downloads
    with open(dest, "wb") as f:
        total_bytes = 0
        for chunk in dl.iter_content(65536):
            f.write(chunk)
            total_bytes += len(chunk)
            if total_bytes > _MAX_BROLL_BYTES:
                break

    if total_bytes > _MAX_BROLL_BYTES:
        print(f"[broll] SKIPPED '{keyword}': file too large ({total_bytes / 1024 / 1024:.1f}MB > 25MB cap)", flush=True)
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

TRANSITION_DURATION_DEFAULT = 0.3

def get_transition_duration(pacing=None):
    """Adaptive transition duration based on video pacing.
    Fast pacing = snappy transitions (0.2s), slow = smoother (0.4s)."""
    if pacing == "fast":
        return 0.2
    elif pacing == "slow":
        return 0.4
    return TRANSITION_DURATION_DEFAULT


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

    w = int(video.get("width") or 0)
    h = int(video.get("height") or 0)
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
        # fps/VFR conversion is handled by fps=30 filter in render v_chain — no normalize_vf needed
        if abs(fps - 30) > 1 or is_vfr:
            print(f"[analyze] Source {w}x{h} @ {fps:.2f}fps (VFR={is_vfr}) — fps=30 filter handles it", flush=True)
        else:
            print(f"[analyze] Source is already {w}x{h} @ {fps:.2f}fps — no normalize needed", flush=True)
        return {"source_path": source_path, "width": w, "height": h, "fps": fps, "normalize_vf": None,
                "crop_x": 0, "crop_y": 0, "crop_w": 1080, "crop_h": 1920}

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


def densify_speed_curve(speed_curve, max_intermediates=50, min_step=0.10):
    """Insert linearly-interpolated intermediate keypoints between Gemini's
    keypoints so the speed curve becomes a perceptually smooth ramp instead
    of discrete jumps.

    BUDGETED proportional allocation: a global cap of max_intermediates
    intermediate keypoints is distributed across all the ramps in
    proportion to each ramp's speed delta. Steeper ramps get more sub-steps
    (where smoothness matters most), gentler ramps get fewer. Hold sections
    get zero. This guarantees the total sub-clip count is bounded
    independently of how many keypoints Gemini sends, so render time is
    predictable.

    With a budget of 50 across typical 6-9 keypoint Gemini curves, the
    max per-step speed delta lands around 0.05 — at or just under the
    human tempo discrimination threshold. Steep ramps where smoothness
    matters most get the densest allocation; gentle ramps barely need any.

    min_step (100ms) clamps the minimum sub-clip duration so the splitter's
    micro-clip merger doesn't drop sub-clips smaller than 3 frames.

    Returns a new list with the original keypoints plus inserted intermediates.
    """
    if not speed_curve or len(speed_curve) < 2:
        return list(speed_curve or [])

    # First pass: compute each ramp's speed_delta and gap so we can
    # allocate the intermediate budget proportionally.
    ramps = []
    total_delta = 0.0
    for i in range(len(speed_curve) - 1):
        t_a = float(speed_curve[i]["t"])
        s_a = float(speed_curve[i]["speed"])
        t_b = float(speed_curve[i + 1]["t"])
        s_b = float(speed_curve[i + 1]["speed"])
        gap = t_b - t_a
        speed_delta = abs(s_b - s_a)
        is_hold = speed_delta < 0.01
        ramps.append({
            "i": i, "t_a": t_a, "s_a": s_a, "t_b": t_b, "s_b": s_b,
            "gap": gap, "delta": speed_delta, "is_hold": is_hold,
            "n_steps": 1,  # default: no intermediates (just the endpoint)
        })
        if not is_hold:
            total_delta += speed_delta

    # Second pass: allocate budget proportional to each ramp's delta.
    # Each ramp's n_steps is the number of equal sub-slices it gets
    # divided into (so n_steps - 1 intermediate keypoints inserted).
    if total_delta > 0:
        for r in ramps:
            if r["is_hold"]:
                continue
            # Ramp's share of the budget, proportional to its speed delta
            share = (r["delta"] / total_delta) * max_intermediates
            # n_steps = share + 1 (since we add (n_steps - 1) intermediates)
            n_steps = max(12, round(share) + 1)
            # Clamp by min_step so we don't create micro-clips smaller than min_step
            n_steps_time = max(12, int(r["gap"] / min_step))
            r["n_steps"] = min(n_steps, n_steps_time)

    # Third pass: emit the densified curve using smoothstep (ease-in-out)
    # interpolation. Linear interpolation has instant acceleration at ramp
    # boundaries which sounds/looks abrupt. Smoothstep (3t²-2t³) eases in
    # and out so the speed change is gentle at both ends of every ramp.
    densified = [dict(speed_curve[0])]
    for r in ramps:
        n_steps = r["n_steps"]
        if n_steps >= 2:
            for k in range(1, n_steps):
                frac = k / n_steps
                # Smoothstep: 3t² - 2t³ (ease-in-out)
                smooth_frac = frac * frac * (3.0 - 2.0 * frac)
                t_new = r["t_a"] + frac * r["gap"]  # time stays linear
                s_new = r["s_a"] + (r["s_b"] - r["s_a"]) * smooth_frac
                densified.append({"t": round(t_new, 3), "speed": round(s_new, 4)})
        densified.append(dict(speed_curve[r["i"] + 1]))

    return densified


def get_speed_for_timestamp(t, speed_curve):
    """Return the speed in effect at time t.

    Speed keypoints are HOLD-and-snap: a keypoint at time T with speed S
    means "from T onward, play at speed S, until the next keypoint takes
    effect." This matches the Gemini prompt's stated intent ("place each
    keypoint at the MOMENT the speed should change") and the user's
    mental model of speed ramping.

    Previously this function smoothstep-interpolated between adjacent
    keypoints, which produced speed values in the MIDDLE of a ramp that
    averaged toward 1.0 — meaning a clip whose start time fell between
    two keypoints would play at near-normal speed regardless of what
    Gemini set on either side.
    """
    if not speed_curve or speed_curve == "none":
        return 1.0
    if not isinstance(speed_curve, list) or len(speed_curve) == 0:
        return 1.0
    if t < float(speed_curve[0]["t"]):
        return float(speed_curve[0]["speed"])
    # Walk forward and return the speed of the most recent keypoint at or
    # before t. Keypoints are sorted by time at parse time.
    current = float(speed_curve[0]["speed"])
    for kp in speed_curve:
        if float(kp["t"]) <= t:
            current = float(kp["speed"])
        else:
            break
    return current


def get_speed_linear_interp(t, speed_curve):
    """Linearly interpolated speed at time t.

    Matches np.interp semantics used by the audio path: speed glides
    continuously between keypoints instead of holding-and-snapping. Used
    in time-map construction so video's avg_speed (log-mean of endpoints)
    and audio's per-sample speed agree on the speed profile across every
    sub-clip — including first/last sub-clips whose boundaries fall
    between densified keypoints rather than on them.
    """
    if not speed_curve or speed_curve == "none":
        return 1.0
    if not isinstance(speed_curve, list) or len(speed_curve) == 0:
        return 1.0
    t0 = float(speed_curve[0]["t"])
    if t <= t0:
        return float(speed_curve[0]["speed"])
    for i in range(1, len(speed_curve)):
        ti = float(speed_curve[i]["t"])
        if t <= ti:
            ti_prev = float(speed_curve[i - 1]["t"])
            span = ti - ti_prev
            if span < 1e-12:
                return float(speed_curve[i]["speed"])
            si_prev = float(speed_curve[i - 1]["speed"])
            si = float(speed_curve[i]["speed"])
            frac = (t - ti_prev) / span
            return si_prev + frac * (si - si_prev)
    return float(speed_curve[-1]["speed"])


def build_speed_curved_audio(source_path, cuts, speed_curve, effective_durations, work_dir, sample_rate=48000):
    """Build speed-curved audio for the entire output as one continuous operation.

    Instead of per-segment asetrate (80+ independent resamplers with boundary
    clicks), this processes each narrative clip's audio through numpy interpolation.
    Pitch shifts proportionally to speed (same effect as asetrate) but with zero
    boundary artifacts within speed ramps.

    Returns path to the processed WAV file.
    """
    import numpy as np

    output_wav = os.path.join(work_dir, "speed_curved_audio.wav")
    all_clips = []

    for ci, cut in enumerate(cuts):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])
        src_dur = src_end - src_start
        eff_dur = effective_durations[ci]
        # Speed is pre-validated to [0.25, 4.0] at plan time — no defensive clamp.
        clip_speed = float(cut.get("speed") or 1.0)

        if src_dur < 0.001:
            continue

        # Extract this clip's raw audio from source
        clip_wav = os.path.join(work_dir, f"clip_audio_{ci:03d}.wav")
        _ext = subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-ss", f"{src_start:.3f}", "-t", f"{src_dur:.3f}",
             "-i", source_path, "-vn",
             "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
             clip_wav],
            capture_output=True, text=True, timeout=15,
        )
        if _ext.returncode != 0 or not os.path.exists(clip_wav):
            # Fallback: silence for this clip
            n_out = max(1, round(eff_dur * sample_rate))
            all_clips.append(np.zeros(n_out, dtype=np.float32))
            continue

        # Read PCM samples
        import wave
        with wave.open(clip_wav, "rb") as wf:
            n_channels = wf.getnchannels()
            n_src_samples = wf.getnframes()
            raw = wf.readframes(n_src_samples)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        if n_channels > 1:
            samples = samples[::n_channels]  # take first channel
        n_src = len(samples)

        if n_src < 2:
            n_out = max(1, round(eff_dur * sample_rate))
            all_clips.append(np.zeros(n_out, dtype=np.float32))
            continue

        # Get speed at each source sample position using the speed curve.
        # Speed is hold-and-snap from the densified curve (matching video behavior).
        has_curve = (speed_curve and speed_curve != "none" and isinstance(speed_curve, list))
        n_out = max(1, round(eff_dur * sample_rate))

        if not has_curve:
            # No speed curve — simple uniform resampling at clip_speed
            if abs(clip_speed - 1.0) < 0.001:
                # 1.0x speed — just truncate/pad to exact length
                if n_src >= n_out:
                    all_clips.append(samples[:n_out])
                else:
                    padded = np.zeros(n_out, dtype=np.float32)
                    padded[:n_src] = samples
                    all_clips.append(padded)
            else:
                src_positions = np.linspace(0, n_src - 1, n_out)
                all_clips.append(np.interp(src_positions, np.arange(n_src), samples))
        else:
            # Variable speed — compute source position for each output sample
            # by integrating 1/speed(t) across the source timeline.
            src_sample_times = np.arange(n_src) / sample_rate
            abs_times = src_sample_times + src_start

            # Linearly interpolate speed between keypoints so pitch glides
            # smoothly instead of stepping at every keypoint boundary. Video's
            # avg_speed uses the log-mean of the same endpoint speeds, so
            # per-sub-clip audio/video durations match exactly (∫1/speed dt
            # equals source_dur / log_mean by construction). Clamp product
            # to [0.25, 4.0] to match video's speed range.
            kp_times = np.array([float(kp["t"]) for kp in speed_curve], dtype=np.float64)
            kp_speeds = np.array(
                [max(0.25, min(2.0, float(kp["speed"]))) for kp in speed_curve],
                dtype=np.float64,
            )
            curve_speeds = np.interp(abs_times, kp_times, kp_speeds)
            speeds = np.clip(clip_speed * curve_speeds, 0.25, 4.0)

            # Compute cumulative output time for each source sample
            dt = 1.0 / sample_rate
            cum_output = np.cumsum(dt / speeds)
            cum_output = np.insert(cum_output, 0, 0.0)  # prepend 0 for sample 0

            # Output sample grid at uniform spacing
            output_grid = np.linspace(0, eff_dur, n_out)

            # Map output time → source sample position (inverse lookup).
            # Use n_src+1 to include the final cumulative value (avoids
            # extrapolation clamping on the last few output samples).
            src_positions = np.interp(output_grid, cum_output[:n_src + 1], np.arange(n_src + 1, dtype=np.float64))
            src_positions = np.clip(src_positions, 0, n_src - 1)

            # Interpolate source audio at computed positions
            all_clips.append(np.interp(src_positions, np.arange(n_src), samples))

        # Clean up clip wav
        try:
            os.remove(clip_wav)
        except OSError:
            pass

    if not all_clips:
        # No clips — produce silence
        import wave
        with wave.open(output_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00" * sample_rate * 2)
        return output_wav

    # Apply 5ms fade at narrative clip boundaries (12 boundaries total — content cuts)
    _fade_samples = int(0.005 * sample_rate)  # 240 samples at 48kHz
    for clip_audio in all_clips:
        n = len(clip_audio)
        if n > _fade_samples * 2:
            fade_in = np.linspace(0.0, 1.0, _fade_samples)
            fade_out = np.linspace(1.0, 0.0, _fade_samples)
            clip_audio[:_fade_samples] *= fade_in
            clip_audio[-_fade_samples:] *= fade_out

    # Concatenate all clips
    full_audio = np.concatenate(all_clips)

    # Write as 16-bit PCM WAV
    full_audio = np.clip(full_audio, -32768, 32767).astype(np.int16)
    import wave
    with wave.open(output_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(full_audio.tobytes())

    _total_dur = len(full_audio) / sample_rate
    print(f"[audio-speed] Built speed-curved audio: {len(cuts)} clips, {_total_dur:.2f}s, {len(full_audio)} samples", flush=True)
    return output_wav


def project_words_to_output(transcript, cuts, effective_durations, speed_curve=None, transition_duration=None, clip_time_maps=None, removed_word_indices=None, fps=30.0):
    """Project word timestamps from source to output timeline using canonical time maps.

    If removed_word_indices is provided, words at those indices are excluded.
    This is the SAME source of truth used by build_clips_from_words, so the
    caption projection cannot emit fragments of removed words.
    """
    words = transcript.get("words") or []
    projected = []
    if not words or not cuts:
        return projected
    _removed = removed_word_indices if isinstance(removed_word_indices, (set, frozenset)) else set(removed_word_indices or [])
    clip_ranges = get_output_clip_ranges(cuts, effective_durations, transition_duration=transition_duration)
    output_cursor = 0.0
    for i, cut in enumerate(cuts):
        c_start = float(cut["source_start"])
        c_end   = float(cut["source_end"])
        tm = clip_time_maps[i] if clip_time_maps and i < len(clip_time_maps) else None
        for word_idx, w in enumerate(words):
            if word_idx in _removed:
                continue
            ws = float(w.get("start") or 0)
            we = float(w.get("end") or 0)
            if we <= c_start or ws >= c_end:
                continue
            clamped_s = max(ws, c_start)
            clamped_e = min(we, c_end)
            if tm:
                local_s = _time_map_lookup(tm, clamped_s - c_start)
                local_e = _time_map_lookup(tm, clamped_e - c_start)
            else:
                # Speed pre-validated to [0.25, 4.0] upstream.
                speed = float(cut.get("speed") or 1.0)
                local_s = (clamped_s - c_start) / speed
                local_e = (clamped_e - c_start) / speed
            projected.append({
                "start": round((output_cursor + local_s)*1000)/1000,
                "end":   round((output_cursor + local_e)*1000)/1000,
                "word":  w.get("punctuated_word") or w.get("word") or "",
                "punctuated_word": w.get("punctuated_word") or w.get("word") or "",
                "speaker": int(w.get("speaker", 0) or 0),
                "_source_start": max(ws, c_start),
                "_word_index": word_idx,
            })
        dur = effective_durations[i] if i < len(effective_durations) else (c_end - c_start)
        # Raw float accumulation — matches _seg_starts (line 6049) which also
        # uses raw addition. Frame-snapping was removed because it accumulated
        # ~200ms drift over 80+ segments, causing b-roll overlays to appear early.
        output_cursor += dur

    projected = [w for w in projected if w["end"] > w["start"]]
    return projected

def get_output_clip_ranges(cuts, effective_durations, transition_duration=None):
    """
    Return list of {"start": float, "end": float} for each clip's position
    in the output timeline.

    The actual ffmpeg pipeline concatenates segments with `-f concat -c copy`
    (stream copy), which does NOT cross-fade. Transitions are decomposed into
    per-segment fade-in/fade-out *within* each segment — they consume time
    inside the segment but the segment's total playback duration is unchanged.
    Therefore the cursor must advance by the FULL effective duration with no
    overlap subtraction. Subtracting overlap was the bug that caused captions
    and SFX to drift earlier by (n_transitions × transition_duration).

    The transition_duration parameter is kept for API compatibility but is
    intentionally unused.
    """
    _ = transition_duration  # intentionally unused — see docstring
    ranges = []
    cursor = 0.0
    for i, cut in enumerate(cuts):
        dur   = effective_durations[i] if i < len(effective_durations) else 0.0
        start = cursor
        end   = cursor + dur
        ranges.append({"start": start, "end": end})
        cursor = end
    return ranges


FILLER_WORDS = {"uh", "um", "uh,", "um,", "hmm", "hmm,", "uhh", "umm", "er", "ah"}


def _is_stutter(current_word, next_word):
    """Detect clear false-start patterns that should be removed."""
    if not next_word:
        return False

    curr = str(current_word or "").strip().lower().rstrip(".,!?;:'\"")
    nxt = str(next_word or "").strip().lower().rstrip(".,!?;:'\"")

    if not curr or not nxt:
        return False

    # Exact repetition: "I I", "the the"
    if curr == nxt:
        return True

    # Prefix/false start: "shou" before "shouldn't", "wh" before "what"
    if len(curr) >= 2 and nxt.startswith(curr) and len(nxt) > len(curr):
        return True

    # Contraction false start: "do" before "don't"
    if curr + "n't" == nxt or curr + "nt" == nxt:
        return True

    # Hyphenated/truncated word (Deepgram sometimes returns "wh-" or "th-")
    if curr.endswith("-") and len(curr) >= 2:
        return True

    return False


def build_clips_from_words(deepgram_words, remove_words, max_silence_gap=0.15, video_duration=0.0):
    """
    Deterministic, CapCut-quality clip builder.

    Pipeline:
      1. Apply Gemini's remove_words (word indices + time ranges)
      2. Deterministic filler removal (ALWAYS_FILLER, CONTEXT_FILLER, MULTI_WORD_FILLER)
      3. Stutter/repeat detection and removal
      4. Build clips from kept words, collapsing dead air
      5. Add audio padding so cuts never clip consonants
      6. Merge micro-clips (< 120ms) into neighbors
      7. Fix overlaps between adjacent clips
      8. Final safety: expand any boundary that lands mid-word

    video_duration (when > 0) clamps every word's end timestamp so that
    no clip ever requests source frames past the actual end of the video.
    Without this, ffmpeg silently produces a shorter segment than predicted
    when the last word's Deepgram-reported end exceeds the actual video
    length, causing a downstream timeline mismatch.
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

    # ── Step 1b: Time-range removals (section_skip / dead_air / non_speech_gap) ──
    # Gemini can also send {"start": X, "end": Y, "reason": "..."} entries.
    # Originally these were silently ignored (only word_index removed words),
    # but the prompt advertises section_skip and Gemini relies on it.
    #
    # SAFETY: only remove words whose ENTIRE acoustic span [start, end] is
    # FULLY CONTAINED inside the requested range. A word that partially
    # overlaps the boundary is kept. This is the protection that the original
    # silent-ignore was trying to provide — Gemini's slightly-off timestamps
    # cannot accidentally clip content at the edges.
    _range_removed_count = 0
    for item in remove_words or []:
        if not isinstance(item, dict):
            continue
        if "word_index" in item:
            continue  # already handled in Step 1
        if "start" not in item or "end" not in item:
            continue
        try:
            _r_start = float(item["start"])
            _r_end = float(item["end"])
        except Exception:
            continue
        if _r_end <= _r_start:
            continue
        _reason = str(item.get("reason") or "range_remove")
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

    gemini_removed = set(removed_indices)

    # ── Step 2: Deterministic filler word removal ─────────────────────────
    # Build a list of non-Gemini-removed words for context-aware filler detection
    remaining = [w for w in sorted_words if w["_word_index"] not in removed_indices]

    for idx_in_remaining, w in enumerate(remaining):
        clean = w["_clean"]

        # Always-filler: remove unconditionally — these are never content words
        # ("um", "uh", "er", "ah", "hmm", etc.)
        # Context-dependent fillers ("like", "so", "basically", "you know") are
        # left to Gemini which understands sentence meaning and can decide whether
        # the word is filler or actual content.
        if clean in ALWAYS_FILLER:
            removed_indices.add(w["_word_index"])
            print(
                f"[tighten] Filler '{w['_text']}' at {w['_start']:.3f}s removed (always-filler)",
                flush=True,
            )
            continue

    # ── Step 3: Stutter/repeat detection ──────────────────────────────────
    # Re-build remaining list after filler removal
    remaining = [w for w in sorted_words if w["_word_index"] not in removed_indices]

    for idx_in_remaining, w in enumerate(remaining):
        if w["_word_index"] in removed_indices:
            continue
        next_w = remaining[idx_in_remaining + 1] if idx_in_remaining + 1 < len(remaining) else None
        if next_w and _is_stutter(w["_clean"], next_w["_clean"]):
            # Different speakers repeating the same word is conversation, not a stutter.
            w_speaker = w.get("speaker", w.get("_speaker"))
            next_speaker = next_w.get("speaker", next_w.get("_speaker"))
            if w_speaker is not None and next_speaker is not None and w_speaker != next_speaker:
                print(
                    f"[tighten] Skipping cross-speaker repeat '{w['_text']}' (speaker {w_speaker}) → "
                    f"'{next_w['_text']}' (speaker {next_speaker})",
                    flush=True,
                )
                continue
            removed_indices.add(w["_word_index"])
            print(
                f"[tighten] Stutter '{w['_text']}' before '{next_w['_text']}' at {w['_start']:.3f}s removed",
                flush=True,
            )

    # ── Step 3b: Phrasal restart detection (N-gram lookahead) ─────────────
    # Catches 2- and 3-word phrasal restarts where the speaker abandons a
    # phrase mid-thought and restarts it. Example:
    #   [141] who  [142] is  [143] I  [144] said  [145] who  [146] is  [147] he?
    # "who is" at 141-142 was abandoned and restarted at 145-146.
    #
    # CRITICAL DISCRIMINATOR: a true restart abandons the first phrase mid-
    # thought. A parallel structure ("what are you gonna do? what are you
    # gonna learn?") COMPLETES the first sentence with sentence-ending
    # punctuation (?, ., !) before the next begins. We reject any match
    # where any word in the gap between the first and second occurrence has
    # sentence-ending punctuation — that signals the first sentence finished.
    #
    # Constraints (tight to avoid false positives):
    #   - phrase length 2 or 3 words
    #   - lookahead window: next 3 word positions only
    #   - time gap between phrases: ≤1.5s
    #   - same speaker
    #   - NO sentence-ending punctuation in the gap words
    _SENTENCE_END_RE = re.compile(r"[.!?]\s*$")
    remaining = [w for w in sorted_words if w["_word_index"] not in removed_indices]
    _restart_removed = set()
    for idx_in_remaining, w in enumerate(remaining):
        if w["_word_index"] in _restart_removed:
            continue
        for phrase_len in (4, 3, 2):  # try longest first to avoid orphan words
            if idx_in_remaining + phrase_len > len(remaining):
                continue
            phrase_words = remaining[idx_in_remaining : idx_in_remaining + phrase_len]
            if any(pw["_word_index"] in _restart_removed for pw in phrase_words):
                continue
            phrase_text = tuple(pw["_clean"] for pw in phrase_words)
            if not all(phrase_text):
                continue
            # If the LAST word of the candidate phrase already has sentence-
            # ending punctuation, the phrase is a complete thought — not an
            # abandoned restart. Skip.
            _last_phrase_punct = str(phrase_words[-1].get("punctuated_word") or phrase_words[-1].get("_text") or "")
            if _SENTENCE_END_RE.search(_last_phrase_punct):
                continue
            phrase_speaker = phrase_words[0].get("speaker", phrase_words[0].get("_speaker"))
            _matched = False
            # TIGHT lookahead: only check the next 3 positions, not 5
            for scan_idx in range(idx_in_remaining + phrase_len, min(idx_in_remaining + phrase_len + 3, len(remaining))):
                if scan_idx + phrase_len > len(remaining):
                    break
                cand_words = remaining[scan_idx : scan_idx + phrase_len]
                if any(cw["_word_index"] in _restart_removed for cw in cand_words):
                    continue
                cand_text = tuple(cw["_clean"] for cw in cand_words)
                if cand_text != phrase_text:
                    continue
                cand_speaker = cand_words[0].get("speaker", cand_words[0].get("_speaker"))
                if phrase_speaker is not None and cand_speaker is not None and phrase_speaker != cand_speaker:
                    continue
                # TIGHT time gap: ≤1.5s (true restarts are quick)
                _time_gap = cand_words[0]["_start"] - phrase_words[-1]["_end"]
                if _time_gap > 1.5 or _time_gap < 0:
                    continue
                # CRITICAL: reject if any word in the gap has sentence-ending
                # punctuation. That means the first sentence completed and
                # this is parallel structure, not a restart.
                _gap_words = remaining[idx_in_remaining + phrase_len : scan_idx]
                _sentence_completed = False
                for _gw in _gap_words:
                    _gw_punct = str(_gw.get("punctuated_word") or _gw.get("_text") or "")
                    if _SENTENCE_END_RE.search(_gw_punct):
                        _sentence_completed = True
                        break
                if _sentence_completed:
                    continue
                # Validated restart — remove the FIRST occurrence (false start)
                for pw in phrase_words:
                    _restart_removed.add(pw["_word_index"])
                # Also remove orphan fillers in the gap between false start and
                # restart. Example: "calling me, like, calling me" — once the
                # first "calling me" is removed, "like" becomes an orphan
                # discourse marker dangling between "started" and "calling me".
                # Its grammatical role was to bridge the false start to its
                # restart; with the false start gone, it serves no purpose.
                # We do NOT apply the pause-bracket validator here because the
                # word is provably orphaned by structural evidence (between a
                # confirmed false start and its restart). Meaningful conjunctions
                # like "but", "and", "however" are not in either filler set,
                # so they're kept.
                for _gw in _gap_words:
                    _gw_clean = _gw["_clean"]
                    if _gw_clean in ALWAYS_FILLER or _gw_clean in CONTEXT_FILLER:
                        _restart_removed.add(_gw["_word_index"])
                        print(
                            f"[tighten] Orphan filler '{_gw['_text']}' at "
                            f"{_gw['_start']:.3f}s removed "
                            f"(gap between false start and restart)",
                            flush=True,
                        )
                print(
                    f"[tighten] Phrasal restart '{' '.join(phrase_text)}' at "
                    f"{phrase_words[0]['_start']:.3f}s removed "
                    f"(repeats at {cand_words[0]['_start']:.3f}s, gap={_time_gap*1000:.0f}ms)",
                    flush=True,
                )
                _matched = True
                break
            if _matched:
                break  # don't also try shorter phrase length at this position
    removed_indices |= _restart_removed

    deterministic_removed = removed_indices - gemini_removed

    # ── Step 4: Build clips from kept words ───────────────────────────────
    kept_words = [w for w in sorted_words if w["_word_index"] not in removed_indices]

    if not kept_words:
        return []

    # The split threshold: if the gap between two kept words exceeds this,
    # we create a new clip. This collapses dead air while preserving natural
    # sentence rhythm.
    NATURAL_PAUSE = max_silence_gap  # 150ms — preserves natural breath pauses, splits on real dead air

    clips = []
    current_words = [kept_words[0]]

    for prev, curr in zip(kept_words, kept_words[1:]):
        gap = curr["_start"] - prev["_end"]

        # If any removed word exists between these two kept words, we MUST
        # split here. Otherwise the clip's audio range spans the removed
        # word and its audio bleeds through (e.g. "shou-" before "shouldn't").
        # This also fixes captions: the removed word's timestamps fall
        # outside all clips, so project_words_to_output naturally skips it.
        removed_between = any(
            idx in removed_indices
            for idx in range(prev["_word_index"] + 1, curr["_word_index"])
        )

        if gap > NATURAL_PAUSE or removed_between:
            clips.append(current_words)
            current_words = [curr]
        else:
            current_words.append(curr)

    if current_words:
        clips.append(current_words)

    # ── Step 5: Build raw clips at exact word boundaries ──────────────────
    # No padding. Cuts land at Deepgram's word.start and word.end exactly.
    # The render pipeline (PCM-audio segments + AAC-once final encode) is
    # sample-accurate, so the boundary in the rendered video matches the
    # boundary we ask for here. Previously we added 15ms / 60ms padding to
    # mask AAC priming-delay artifacts (~21ms per segment) that bled into
    # boundaries when AAC segments were stream-copy concatenated. With PCM
    # intermediates that mechanism no longer exists, so the padding is gone.
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

    # ── Step 6: Reject micro-clips ────────────────────────────────────────
    # Any clip shorter than 120ms is too small to be a standalone segment —
    # it would be unplayable. This is a symptom of a removal pattern that
    # orphans a tiny word island between two removal ranges. Fail hard so
    # Gemini fixes the removal pattern at its root rather than us silently
    # merging the orphan into a neighbor.
    MIN_CLIP_DURATION = 0.120
    for _ci, clip in enumerate(raw_clips):
        dur = clip["padded_end"] - clip["padded_start"]
        if dur < MIN_CLIP_DURATION:
            raise ValueError(
                f"build_clips_from_words produced a micro-clip ({dur*1000:.0f}ms, "
                f"words[{clip['first_word']!r}..{clip['last_word']!r}], "
                f"t={clip['padded_start']:.3f}s-{clip['padded_end']:.3f}s). Your "
                f"remove_words pattern orphans a tiny kept segment between two "
                f"removal ranges. Extend or consolidate the surrounding removals "
                f"so the kept segment is at least {MIN_CLIP_DURATION*1000:.0f}ms."
            )

    # ── Step 7: Non-overlap invariant ─────────────────────────────────────
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
    final_clips = []
    for rc in raw_clips:
        s = round(rc["padded_start"] * 1000) / 1000
        e = round(rc["padded_end"] * 1000) / 1000
        # Final clamp: padding may have pushed end past video_duration
        if _vd > 0 and e > _vd:
            e = round(_vd * 1000) / 1000
        if e - s < 0.05:
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
    total_gemini = len(gemini_removed)
    total_det = len(deterministic_removed)
    total_source = sum(c["source_end"] - c["source_start"] for c in final_clips)

    # Log every removed word so we can audit exactly what was cut
    all_removed = sorted(removed_indices)
    if all_removed:
        print(f"[tighten] REMOVED WORDS ({len(all_removed)}):", flush=True)
        for idx in all_removed:
            w = sorted_words[idx]
            source = "gemini" if idx in gemini_removed else "deterministic"
            print(f"[tighten]   [{idx}] '{w['_text']}' @ {w['_start']:.3f}s ({source})", flush=True)

    print(
        f"[tighten] {total_words} words → {total_kept} kept, "
        f"{total_gemini} Gemini removals + {total_det} deterministic removals, "
        f"{len(final_clips)} clips, {total_source:.2f}s output",
        flush=True,
    )

    # Return clips AND the set of removed word indices so downstream consumers
    # (caption projection, SFX word-snapping) can use the SAME source of truth
    # as the cut builder. Without this, the caption projection iterates the
    # full Deepgram transcript and emits fragments of removed words.
    return final_clips, set(removed_indices)


def build_clip_time_map(clip_start, clip_end, clip_speed, speed_curve, fps=30):
    """Build a canonical per-frame time map for one clip.

    This is the SINGLE SOURCE OF TRUTH for the time mapping. All systems
    (FFmpeg setpts, caption projection, SFX/B-roll projection) derive their
    timing from this same table, eliminating drift between systems.

    Uses trapezoidal integration at 1 sample per frame for sub-frame accuracy.

    Returns dict with:
        output_times: list of output times (seconds) at each source frame boundary [0..n_frames]
        effective_duration: total output duration (= output_times[-1])
        avg_speed: average speed (for audio, which must be constant)
        n_frames: number of source frames
        source_dur: source duration in seconds
    """
    source_dur = clip_end - clip_start
    if source_dur <= 0.001:
        return {"output_times": [0.0, max(source_dur, 0.001)], "effective_duration": max(source_dur, 0.001),
                "avg_speed": clip_speed, "n_frames": 1, "source_dur": source_dur}

    has_curve = (speed_curve and speed_curve != "none" and isinstance(speed_curve, list))
    n_frames = max(1, round(source_dur * fps))

    # Logarithmic mean of the sub-clip's start and end speeds (linearly
    # interpolated from the densified curve). This is the unique constant
    # speed whose reciprocal integrates to the same output duration as the
    # audio's linearly-sliding speed — i.e. video setpts=(1/log_mean)*PTS
    # and audio ∫1/speed(t) dt produce identical per-sub-clip durations.
    # Degenerate case (s_start == s_end) collapses to that shared value.
    if has_curve:
        s_start = max(0.25, min(2.0, get_speed_linear_interp(clip_start, speed_curve)))
        s_end = max(0.25, min(2.0, get_speed_linear_interp(clip_end, speed_curve)))
        if abs(s_end - s_start) < 1e-9:
            curve_speed = s_start
        else:
            curve_speed = (s_end - s_start) / math.log(s_end / s_start)
    else:
        curve_speed = 1.0
    speed = max(0.25, min(4.0, clip_speed * curve_speed))

    # Effective duration equals source_dur / speed — this matches exactly what
    # FFmpeg emits for a segment rendered with `-ss X -t source_dur -i source`
    # plus `setpts=(1/speed)*PTS`. FFmpeg reads source_dur seconds of source
    # (a continuous time window, not frame-quantized) and setpts scales the
    # output timeline by 1/speed. Stream duration = source_dur / speed.
    # Using n_frames / (fps * speed) instead introduced up to ±16ms per
    # segment of drift between our prediction and FFmpeg's actual output,
    # because round(source_dur * fps) is unstable at half-frame boundaries.
    eff_dur = source_dur / speed

    # output_times span [0, eff_dur] uniformly across n_frames+1 boundaries.
    output_times = [k * eff_dur / n_frames for k in range(n_frames + 1)]

    return {
        "output_times": output_times,
        "effective_duration": eff_dur,
        "avg_speed": speed,
        "n_frames": n_frames,
        "source_dur": source_dur,
    }


def split_clips_at_speed_keypoints(cuts, speed_curve):
    """Split clips at speed curve keypoints so each sub-clip has near-constant speed.

    This is the root fix for audio/video sync: when each sub-clip has <5% speed variation,
    constant-average audio matches the video perfectly. The parallel architecture is preserved.

    Returns expanded list of cuts with sub-clips replacing originals.
    """
    if not speed_curve or speed_curve == "none" or not isinstance(speed_curve, list):
        return list(cuts)

    # Split at every keypoint in the speed curve. The speed curve has
    # already been densified at parse time (densify_speed_curve) — Gemini's
    # original keypoints + linearly-interpolated intermediates at ~250ms
    # intervals — so this loop produces enough sub-clips for smooth ramping.
    all_split_times = sorted(set(float(kp["t"]) for kp in speed_curve))
    expanded = []

    for cut in cuts:
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])

        # Find split points that fall strictly inside this clip
        interior = [t for t in all_split_times if src_start + 0.05 < t < src_end - 0.05]

        if not interior:
            expanded.append(dict(cut))
            continue

        boundaries = [src_start] + interior + [src_end]

        for si in range(len(boundaries) - 1):
            sub_start = boundaries[si]
            sub_end = boundaries[si + 1]

            if sub_end - sub_start < 0.001:
                continue  # skip zero-length clips (floating point edge case)

            sub_cut = dict(cut)
            sub_cut["source_start"] = round(sub_start, 3)
            sub_cut["source_end"] = round(sub_end, 3)

            # Only last sub-clip keeps transition_out
            if si < len(boundaries) - 2:
                sub_cut["transition_out"] = "none"

            expanded.append(sub_cut)

    if expanded:
        n_split = len(expanded) - len(cuts)
        if n_split > 0:
            print(f"[speed-split] Split {len(cuts)} clips into {len(expanded)} sub-clips ({len(all_split_times)} split points)", flush=True)

    return expanded


def _time_map_lookup(tm, source_offset):
    """Look up output time from a clip time map given a source offset (seconds from clip start).
    Uses constant avg_speed to exactly match FFmpeg's setpts=(1/avg_speed)*PTS."""
    if source_offset <= 0:
        return 0.0
    avg_speed = tm["avg_speed"]
    return source_offset / avg_speed if avg_speed > 0 else source_offset


def build_setpts_from_time_map(tm, log=False):
    """Generate constant-speed FFmpeg setpts expression from a canonical time map.

    Uses the integrated average speed from the time map. After splitting clips at
    speed keypoints, each sub-clip has near-constant speed, so the constant average
    is accurate. Audio uses the same avg_speed, guaranteeing perfect sync.

    Returns (setpts_value, effective_dur, avg_speed).
    """
    eff_dur = tm["effective_duration"]
    avg_speed = tm["avg_speed"]
    n_frames = tm["n_frames"]

    if n_frames <= 1:
        return None, eff_dur, avg_speed

    # Skip setpts if speed is ~1.0
    if abs(avg_speed - 1.0) < 0.005:
        return None, eff_dur, avg_speed

    # Full float precision (10 decimals) so the audio asetrate and the
    # video setpts agree on the playback rate to sub-microsecond accuracy.
    # Previously :.4f rounded both values independently in opposite
    # directions, producing different effective playback rates that drifted
    # by ~1-10ms per minute of segment.
    setpts_val = f"{1.0/avg_speed:.10f}*PTS"
    if log:
        print(f"[speed] Setpts: avg={avg_speed:.3f}x, eff={eff_dur:.3f}s", flush=True)

    return setpts_val, eff_dur, avg_speed


def project_source_time_to_output(source_t, cuts, clip_ranges, speed_curve=None, clip_time_maps=None):
    """Map a source-timeline timestamp to the output-timeline timestamp.
    Uses canonical time maps for exact alignment with FFmpeg.

    clip_time_maps is REQUIRED — it contains the combined clip_speed *
    curve_speed used by FFmpeg's setpts. Without it, the projection
    would use cut["speed"] (always 1.0 when speed_curve is active),
    ignoring the speed curve entirely and placing b-roll/SFX late.

    When a hook clip duplicates a source range at the start of the timeline,
    multiple cuts can contain the same source timestamp. We prefer the LAST
    (narrative) match so that b-roll, SFX, and emphasis moments land at the
    correct narrative position rather than the hook preview position."""
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


def project_source_time_to_final_output(source_t, cuts, effective_durations, speed_curve=None, clip_time_maps=None):
    """Map a source timestamp to the final output timeline after cut compression."""
    clip_ranges = get_output_clip_ranges(cuts, effective_durations)
    return project_source_time_to_output(source_t, cuts, clip_ranges, speed_curve, clip_time_maps=clip_time_maps)


def build_variable_speed_setpts(clip_start, clip_end, clip_speed, speed_curve, log=False, fps=30):
    """Build speed expression from canonical time map. Wrapper for backward compatibility."""
    tm = build_clip_time_map(clip_start, clip_end, clip_speed, speed_curve, fps=fps)
    setpts_val, eff_dur, avg_speed = build_setpts_from_time_map(tm, log=log)
    return setpts_val, eff_dur, avg_speed


def compute_effective_durations(cuts, speed_curve=None, fps=30):
    """Compute output duration for each clip using canonical time maps."""
    durations = []
    for cut in (cuts or []):
        src_start = float(cut["source_start"])
        src_end = float(cut["source_end"])
        # Speed pre-validated to [0.25, 4.0] upstream.
        clip_speed = float(cut.get("speed") or 1.0)
        tm = build_clip_time_map(src_start, src_end, clip_speed, speed_curve, fps=fps)
        durations.append(tm["effective_duration"])
    return durations


def render_multi_clip(source_path, cuts, edit_plan, output_path, transcript, work_dir, speech_segments=None,
                      broll_clips=None, broll_fetch_futures=None):
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
      - numpy speed-curve-resampled source audio (pitch-scaling exactly matching
        video playbackRate)
      - SFX mix with onset compensation + output-timeline projection
      - voice ducking at SFX onsets
      - adaptive EQ + double-compressor voice chain

    Final step: ffmpeg mux — stream-copy video + AAC audio into output_path.
    """
    import math

    # ── 0. Source normalization — guarantee 1080x1920 9:16 input to Remotion ─
    # `normalize_vf` comes from analyze_source_video. It encodes a scale+crop
    # that reframes landscape/mismatched sources to 1080x1920 with an optional
    # face-centered crop (computed from sparse face detection). Remotion
    # cannot do this correction (CSS transforms can crop but not with the
    # same ffmpeg-quality lanczos scale), so we apply it in one pre-pass
    # before handing the source to Remotion. When the source is already
    # 1080x1920 this is a no-op and we skip the pass.
    _normalize_vf = edit_plan.get("_normalize_vf")
    if _normalize_vf:
        _norm_t0 = time.time()
        _normalized_path = os.path.join(work_dir, "source_ready.mp4")
        _norm_cmd = [
            "ffmpeg", "-y", "-v", "error", "-threads", "0",
            "-i", source_path,
            "-vf", _normalize_vf,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-video_track_timescale", "90000",
            _normalized_path,
        ]
        _norm_r = subprocess.run(_norm_cmd, capture_output=True, text=True, timeout=300)
        if _norm_r.returncode != 0:
            raise RuntimeError(
                f"Source normalization to 1080x1920 failed: {(_norm_r.stderr or '')[-500:]}"
            )
        if not os.path.exists(_normalized_path) or os.path.getsize(_normalized_path) < 10000:
            raise RuntimeError(f"Source normalization produced invalid output: {_normalized_path}")
        print(
            f"[source-norm] Applied {_normalize_vf[:60]}{'...' if len(_normalize_vf) > 60 else ''} "
            f"in {time.time() - _norm_t0:.1f}s → source_ready.mp4 "
            f"({os.path.getsize(_normalized_path)/1024/1024:.1f}MB)",
            flush=True,
        )
        source_path = _normalized_path
    else:
        print("[source-norm] Source is already 1080x1920 — no normalization needed", flush=True)

    # ── 1. Pre-render clip setup ────────────────────────────────────────────
    speed_curve = edit_plan.get("_parsed_speed_curve")
    TRANSITION_DURATION = get_transition_duration(edit_plan.get("pacing"))
    print(f"[render] transition_duration={TRANSITION_DURATION:.2f}s (pacing={edit_plan.get('pacing')})", flush=True)

    render_cuts = list(cuts)

    # Hook clip — prefix the timeline with the Gemini-selected hook source
    # range, subset from the narrative clips it overlaps. No auto-zoom is
    # applied here; if Gemini wants a zoom on the hook it emits one via
    # emphasis_moments (whose source timestamps fall in the hook window).
    hook_clip = edit_plan.get("hook_clip")
    if isinstance(hook_clip, dict):
        _hook_start = float(hook_clip.get("source_start") or 0.0)
        _hook_end = float(hook_clip.get("source_end") or 0.0)
        _hook_clips = []
        for _nc in render_cuts:
            _nc_start = float(_nc["source_start"])
            _nc_end = float(_nc["source_end"])
            _overlap_start = max(_nc_start, _hook_start)
            _overlap_end = min(_nc_end, _hook_end)
            if _overlap_end - _overlap_start > 0.05:
                _hc = dict(_nc)
                _hc["source_start"] = _overlap_start
                _hc["source_end"] = _overlap_end
                _hc["transition_out"] = "none"
                _hc["_is_hook"] = True
                _hook_clips.append(_hc)
        if not _hook_clips:
            raise RuntimeError(
                f"Hook clip {_hook_start:.3f}-{_hook_end:.3f} does not overlap any "
                f"narrative clip. Gemini must pick a hook inside kept content."
            )
        _hook_dur = sum(float(h["source_end"]) - float(h["source_start"]) for h in _hook_clips)
        print(f"[hook] Built hook from {len(_hook_clips)} narrative clip(s) covering {_hook_dur:.2f}s", flush=True)
        render_cuts = _hook_clips + render_cuts

    # Tag clips with _original_idx (hook = -1, content = 0..N)
    _content_idx = 0
    for _rc in render_cuts:
        if _rc.get("_is_hook"):
            _rc["_original_idx"] = -1
        else:
            _rc["_original_idx"] = _content_idx
            _content_idx += 1

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

    # Shift speed ramps that span removed-content gaps into preceding clip tails
    if speed_curve and isinstance(speed_curve, list) and len(speed_curve) >= 2 and len(render_cuts) >= 2:
        _ramps_shifted = 0
        for _bi in range(1, len(render_cuts)):
            _prev_start = float(render_cuts[_bi - 1]["source_start"])
            _prev_end = float(render_cuts[_bi - 1]["source_end"])
            _curr_start = float(render_cuts[_bi]["source_start"])
            _gap = _curr_start - _prev_end
            if _gap < 0.05:
                continue
            _speed_at_prev_end = get_speed_for_timestamp(_prev_end, speed_curve)
            _speed_at_curr_start = get_speed_for_timestamp(_curr_start, speed_curve)
            _delta = _speed_at_curr_start - _speed_at_prev_end
            if _delta >= -0.03:
                continue
            _prev_dur = _prev_end - _prev_start
            _ramp_dur = min(0.4, _prev_dur * 0.3)
            if _ramp_dur < 0.08:
                continue
            _ramp_start = round(_prev_end - _ramp_dur, 3)
            _target_speed = _speed_at_curr_start
            speed_curve = [kp for kp in speed_curve
                           if not (_ramp_start < float(kp["t"]) <= _prev_end)]
            _n_steps = 8
            for _si in range(_n_steps + 1):
                _frac = _si / _n_steps
                _smooth = _frac * _frac * (3.0 - 2.0 * _frac)
                _t = _ramp_start + _frac * _ramp_dur
                _s = _speed_at_prev_end + (_target_speed - _speed_at_prev_end) * _smooth
                speed_curve.append({"t": round(_t, 3), "speed": round(_s, 4)})
            _ramps_shifted += 1
        if _ramps_shifted > 0:
            speed_curve.sort(key=lambda x: float(x["t"]))
            print(f"[speed-curve] Shifted {_ramps_shifted} ramp(s) into preceding clip tails ({len(speed_curve)} keypoints)", flush=True)
    edit_plan["_parsed_speed_curve"] = speed_curve

    # Snapshot pre-split cuts (audio pipeline uses these for full clip resampling)
    _presplit_cuts = list(render_cuts)
    _presplit_effective_durations = compute_effective_durations(_presplit_cuts, speed_curve, fps=source_fps)
    edit_plan["_presplit_cuts"] = _presplit_cuts
    edit_plan["_presplit_eff_durs"] = _presplit_effective_durations

    # Split at speed curve keypoints → constant-speed sub-clips
    render_cuts = split_clips_at_speed_keypoints(render_cuts, speed_curve)

    # Build canonical time maps per sub-clip (SSOT for video + audio)
    _clip_time_maps = []
    effective_durations = []
    for _rc in render_cuts:
        _tm = build_clip_time_map(
            float(_rc["source_start"]),
            float(_rc["source_end"]),
            float(_rc.get("speed") or 1.0),
            speed_curve,
            fps=source_fps,
        )
        _clip_time_maps.append(_tm)
        effective_durations.append(_tm["effective_duration"])

    edit_plan["_render_cuts"] = render_cuts
    edit_plan["_render_effective_durations"] = effective_durations
    edit_plan["_render_clip_time_maps"] = _clip_time_maps

    n = len(render_cuts)
    total_output_duration = sum(effective_durations)
    total_output_frames = max(1, int(round(total_output_duration * source_fps)))

    # Output clip ranges (start, end in output seconds) — used for SFX + b-roll + text overlay timing
    _clip_ranges = get_output_clip_ranges(render_cuts, effective_durations, transition_duration=None)

    # Project Deepgram words onto output timeline (for captions + SFX + b-roll)
    _removed_word_indices = edit_plan.get("_removed_word_indices") or set()
    _projected_words = project_words_to_output(
        transcript, render_cuts, effective_durations, speed_curve,
        transition_duration=None, clip_time_maps=_clip_time_maps,
        removed_word_indices=_removed_word_indices, fps=source_fps,
    )
    edit_plan["_projected_words"] = _projected_words
    _pw_by_idx = {pw["_word_index"]: pw for pw in _projected_words if pw.get("_word_index") is not None}

    # ── 2. Build Remotion input JSON ────────────────────────────────────────
    # Clips — one ClipSpec per sub-clip. Zoom effects are attached to EVERY
    # sub-clip of a parent, with event `startMs` offset by how far into the
    # parent the sub-clip sits. This keeps the zoom animation continuous
    # across speed-curve splits (sub-clip 1 picks up the animation partway
    # through, matching where sub-clip 0 left off).
    clips_out = []
    prev_original_idx = None
    _parent_output_offset_ms = 0.0
    for i, (rc, tm, eff_dur) in enumerate(zip(render_cuts, _clip_time_maps, effective_durations)):
        _source_start_frames = int(round(float(rc["source_start"]) * source_fps))
        _pbr = float(tm.get("avg_speed") or 1.0)
        _dur_frames = max(1, int(round(eff_dur * source_fps)))
        _orig_idx = rc.get("_original_idx")
        _is_first_subclip = _orig_idx != prev_original_idx
        if _is_first_subclip:
            _parent_output_offset_ms = 0.0
        _clip_id_parts = [
            "hook" if rc.get("_is_hook") else "clip",
            str(_orig_idx if _orig_idx is not None else i),
            f"s{i}",
        ]
        _clip_spec = {
            "id": "-".join(_clip_id_parts),
            "startFromFrames": _source_start_frames,
            "playbackRate": round(_pbr, 6),
            "durationInFrames": _dur_frames,
        }
        _zoom = rc.get("_zoom_effect") or rc.get("zoom_effect")
        if isinstance(_zoom, dict) and _zoom.get("type") in VALID_ZOOM_TYPES:
            # Offset each event's startMs by the sub-clip's position inside
            # the parent clip. Zoom component sees time relative to parent,
            # so the animation flows seamlessly across sub-clip boundaries.
            _offset_ms = int(round(_parent_output_offset_ms))
            _raw_events = _zoom.get("events") or []
            _adjusted_events = []
            for _ev in _raw_events:
                if not isinstance(_ev, dict):
                    continue
                try:
                    _new_start_ms = int(round(float(_ev.get("startMs", 0)))) - _offset_ms
                    _new_dur_ms = int(round(float(_ev.get("durationMs", 0))))
                except Exception:
                    continue
                _new_ev = {**_ev, "startMs": _new_start_ms, "durationMs": _new_dur_ms}
                _adjusted_events.append(_new_ev)
            _clip_spec["zoomEffect"] = {
                "type": _zoom["type"],
                "events": _adjusted_events,
                **{k: v for k, v in _zoom.items() if k not in ("type", "events") and v is not None},
            }
        clips_out.append(_clip_spec)
        _parent_output_offset_ms += eff_dur * 1000.0
        prev_original_idx = _orig_idx

    # Transitions on ORIGINAL clip boundaries (not between sub-clips of same parent)
    transitions_out = []
    _T_trans = TRANSITION_DURATION
    _T_trans_frames = max(1, int(round(_T_trans * source_fps)))
    for i in range(len(render_cuts) - 1):
        if render_cuts[i].get("_original_idx") == render_cuts[i + 1].get("_original_idx"):
            continue
        _t_raw = str(render_cuts[i].get("transition_out") or "none")
        if _t_raw not in VALID_TRANSITION_TYPES:
            continue
        _clipA_pbr = float(_clip_time_maps[i].get("avg_speed") or 1.0)
        _clipB_pbr = float(_clip_time_maps[i + 1].get("avg_speed") or 1.0)
        _clipA_src_end = float(render_cuts[i]["source_end"])
        _clipA_start_from = max(0.0, _clipA_src_end - _T_trans * _clipA_pbr)
        _clipA_start_from_frames = int(round(_clipA_start_from * source_fps))
        _clipB_src_start = float(render_cuts[i + 1]["source_start"])
        _clipB_start_from_frames = int(round(_clipB_src_start * source_fps))
        _trans_extras = render_cuts[i].get("_transition_extras") or {}
        transitions_out.append({
            "afterClipIndex": i,
            "type": _t_raw,
            "durationInFrames": _T_trans_frames,
            "clipAStartFromFrames": _clipA_start_from_frames,
            "clipBStartFromFrames": _clipB_start_from_frames,
            "clipAPlaybackRate": round(_clipA_pbr, 6),
            "clipBPlaybackRate": round(_clipB_pbr, 6),
            **_trans_extras,
        })
        print(f"[transition] {_t_raw} after clip {i} (orig {render_cuts[i].get('_original_idx')}) — {_T_trans_frames}f", flush=True)

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
            else:
                _sfx_word = _sfx.get("word", "")
                print(f"[sfx] Skipping {_sound_style} on '{_sfx_word}' — word removed from output", flush=True)
                continue
        else:
            _source_t = float(_sfx.get("t") or 0.0)
            _projected_t = project_source_time_to_output(
                _source_t, render_cuts, _clip_ranges, speed_curve,
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
    # B-roll fetches run in parallel with the main pipeline. Each fetch must
    # either return a local file path OR return None (no Pexels match). A
    # raised exception fails the whole render — we do not silently skip.
    broll_out = []
    if broll_fetch_futures:
        _broll_files = {}
        for _fut in concurrent.futures.as_completed(broll_fetch_futures, timeout=30):
            _idx = broll_fetch_futures[_fut]
            _path = _fut.result(timeout=1)
            if _path:
                _broll_files[_idx] = _path

        if _broll_files and broll_clips:
            for _bi, _bc in enumerate(broll_clips):
                if _bi not in _broll_files:
                    continue
                _local_path = _broll_files[_bi]
                _br_sw = _bc.get("_start_word_kept")
                _br_ew = _bc.get("_end_word_kept")
                if _br_sw is None or _br_ew is None:
                    print(f"[broll] '{_bc.get('keyword')}' missing kept word indices — skipping", flush=True)
                    continue
                _pw_start = _pw_by_idx.get(_br_sw)
                _pw_end = _pw_by_idx.get(_br_ew)
                if not _pw_start or not _pw_end:
                    print(f"[broll] '{_bc.get('keyword')}' projected words missing — skipping", flush=True)
                    continue
                _out_start = float(_pw_start["start"])
                _out_end = float(_pw_end["end"])
                if _out_start >= total_output_duration or _out_end <= _out_start:
                    continue
                _eff = _out_end - _out_start
                _br_dur = get_video_duration(_local_path)
                if _br_dur > 0 and _eff > _br_dur:
                    _eff = _br_dur
                    _out_end = _out_start + _eff
                if _out_start + _eff > total_output_duration:
                    _eff = total_output_duration - _out_start
                    _out_end = _out_start + _eff
                if _eff <= 0.05:
                    continue
                _seek_seconds = 0.0
                if _br_dur > _eff + 1.0:
                    _seek_seconds = min(_br_dur * 0.25, max(0.0, _br_dur - _eff - 0.5))
                _from_frame = int(round(_out_start * source_fps))
                _dur_frames = max(1, int(round(_eff * source_fps)))
                # Probe the B-roll's actual fps for frame-accurate seek→frame.
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
                _seek_from_frames = int(round(_seek_seconds * _br_fps))
                broll_out.append({
                    "src": _local_path,
                    "fromFrame": _from_frame,
                    "durationInFrames": _dur_frames,
                    "seekFromFrames": _seek_from_frames,
                    "playbackRate": 1.0,
                })
                edit_plan.setdefault("_broll_output_ranges", []).append((_out_start, _out_end))
                _kw = _bc.get("keyword", "")
                print(f"[broll] '{_kw}' out=[{_out_start:.2f}..{_out_end:.2f}]s dur={_eff:.2f}s seek={_seek_seconds:.2f}s", flush=True)

    # ── 4b. Text overlays — variant dispatch ────────────────────────────────
    # Word-anchored: Gemini emits start_word_index + duration_seconds. Python
    # projects the anchor word's source-time start through cuts to get the
    # output-time start, then converts to frames. Overlay disappears after
    # duration_seconds of OUTPUT time (stable regardless of downstream speed
    # ramping on the anchor clip).
    text_overlays_out = []
    for _ov in (edit_plan.get("text_overlays") or []):
        _du = float(_ov["duration_seconds"])
        _source_start = float(_ov["_source_start"])
        _out_start = project_source_time_to_output(
            _source_start, render_cuts, _clip_ranges, speed_curve,
            clip_time_maps=_clip_time_maps,
        )
        if _out_start is None:
            raise RuntimeError(
                f"text_overlays[{_ov.get('variant')}] anchor word (source "
                f"t={_source_start:.2f}s) projected to None — anchor word was "
                f"removed after validation, which should be impossible."
            )
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
        print(
            f"[text-overlay] {_ov['variant']} @ src={_source_start:.2f}s "
            f"→ out={_out_start:.2f}s for {_du:.2f}s",
            flush=True,
        )

    # ── 5. Caption segments projection (source → output timeline) ───────────
    caption_pages = _build_tiktok_pages_from_projected(_projected_words, max_words_per_page=3)
    _caption_style = edit_plan["caption_style"]
    _caption_keywords = edit_plan["caption_keywords"]
    _caption_extra_props = _resolve_caption_extra_props(_caption_style, _caption_keywords, edit_plan)
    # Each segment's from/to is in SOURCE seconds (pre-remove_words timeline).
    # Project each endpoint to OUTPUT frames using the same canonical time maps
    # that drive captions / SFX / b-roll.
    _cps_raw = edit_plan["caption_position_segments"]
    caption_position_segments_out = []
    for _cs in _cps_raw:
        _f_out = project_source_time_to_output(
            float(_cs["from_seconds"]), render_cuts, _clip_ranges, speed_curve,
            clip_time_maps=_clip_time_maps,
        )
        _t_out = project_source_time_to_output(
            float(_cs["to_seconds"]), render_cuts, _clip_ranges, speed_curve,
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
    if not caption_position_segments_out:
        # The validator guarantees at least one segment covering [0, duration].
        # If projection produced nothing, it means total_output_frames is 0.
        raise RuntimeError("caption_position_segments projection produced no output frames")

    # ── 6. Color effect (global) — resolve peak_at_seconds → peakFrame ──────
    _color_raw = edit_plan.get("color_effect")
    color_out = None
    if isinstance(_color_raw, dict):
        color_out = {
            "type": _color_raw["type"],
            "intensity": float(_color_raw["intensity"]),
        }
        _timing = _color_raw["timing"]
        if _timing["mode"] == "persistent":
            color_out["timing"] = {"mode": "persistent"}
            if "fadeInFrames" in _timing:
                color_out["timing"]["fadeInFrames"] = int(_timing["fadeInFrames"])
        else:
            # pulsed — resolve each peak_at_seconds (source time) to an output frame.
            _resolved_pulses = []
            for _p in _timing["pulses"]:
                _peak_s = float(_p["peak_at_seconds"])
                _out_t = project_source_time_to_output(
                    _peak_s, render_cuts, _clip_ranges, speed_curve,
                    clip_time_maps=_clip_time_maps,
                )
                if _out_t is None:
                    raise RuntimeError(
                        f"color_effect pulse peak_at_seconds={_peak_s}s was removed from "
                        f"the output timeline — Gemini referenced a time in a cut segment."
                    )
                _resolved_pulses.append({
                    "peakFrame": int(round(_out_t * source_fps)),
                    "attackFrames": _p["attackFrames"],
                    "holdFrames": _p["holdFrames"],
                    "releaseFrames": _p["releaseFrames"],
                    "intensity": _p["intensity"],
                })
            color_out["timing"] = {"mode": "pulsed", "pulses": _resolved_pulses}
        # Component extras pass through.
        _extras = {k: v for k, v in _color_raw.items() if k not in ("type", "intensity", "timing")}
        if _extras:
            color_out["extraProps"] = _extras

    # ── 7. Motion graphics — word-anchored, output-projected, semantic-anchor-translated ─
    # Gemini emits start_word_index + end_word_index (plus optional
    # duration_seconds_override). Python projects the anchor words' source-time
    # boundaries through the cuts timeline to get output-frame start/end. The
    # SEMANTIC_TO_MG_ANCHOR map translates the safe-zone anchor into the MG
    # pack's own MGAnchor vocabulary; components render against the full canvas.
    motion_graphics_out = []
    for _mg in (edit_plan.get("motion_graphics") or []):
        _sw_source = float(_mg["_source_start"])
        _ew_source = float(_mg["_source_end"])
        _out_start = project_source_time_to_output(
            _sw_source, render_cuts, _clip_ranges, speed_curve,
            clip_time_maps=_clip_time_maps,
        )
        _out_end = project_source_time_to_output(
            _ew_source, render_cuts, _clip_ranges, speed_curve,
            clip_time_maps=_clip_time_maps,
        )
        if _out_start is None or _out_end is None:
            raise RuntimeError(
                f"motion_graphic {_mg['type']} anchor words projected to None "
                f"(source {_sw_source:.2f}-{_ew_source:.2f}s) — anchor word "
                f"was removed after validation."
            )
        # duration_seconds_override lets a fixed-length pin extend beyond the
        # natural word span. Anchor start unchanged; end = start + override.
        _dur_override = _mg.get("duration_seconds_override")
        if _dur_override is not None:
            _out_end = _out_start + float(_dur_override)
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
    # Each emphasis moment's explicit visual layers (zoom / color_pulse / MG)
    # get projected and merged into the Remotion input here. No mutation of
    # color_effect.timing — if emphasis has color_pulse=true, the validator
    # already enforced that color_effect.timing.mode is "pulsed".
    for em in edit_plan.get("_emphasis_moments", []):
        _em_t_out = project_source_time_to_output(
            float(em["t"]), render_cuts, _clip_ranges, speed_curve,
            clip_time_maps=_clip_time_maps,
        )
        if _em_t_out is None:
            raise RuntimeError(
                f"Emphasis moment at source {em['t']}s was removed from the output "
                f"timeline — Gemini flagged a moment in a cut segment."
            )
        _em_t_frame = int(round(_em_t_out * source_fps))

        # Zoom on the clip containing this moment (moment is in source time).
        if em["zoom_effect"]:
            for _rc in render_cuts:
                if float(_rc["source_start"]) <= em["t"] <= float(_rc["source_end"]):
                    _rc["_zoom_effect"] = em["zoom_effect"]
                    break

        # Color pulse: append at the emphasis moment's own t. Validator has
        # already guaranteed color_effect.timing.mode == "pulsed" when any
        # emphasis has color_pulse=true.
        if em["color_pulse"]:
            _pulse_entry = {
                "peakFrame": _em_t_frame,
                "attackFrames": 3,
                "holdFrames": 4,
                "releaseFrames": 12,
                "intensity": 1.0,
            }
            color_out["timing"]["pulses"].append(_pulse_entry)

        # Motion graphic: append to motion_graphics_out, anchored at the moment.
        # Translate semantic anchor → MGAnchor just like the top-level loop.
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

    # ── 7c. Z-order validator — captions must stay OUT of any bottom-anchored
    # motion_graphic's window. Gemini is told this in Rule #5, but the rule
    # requires the plan to synchronize output-time MG windows with source-time
    # caption segments. By the time we reach here, both lists have been
    # projected to output-frame space, so we can verify the contract directly.
    # No silent fix — if Gemini got this wrong the plan is invalid.
    _BOTTOM_MG_ANCHORS = {"bottom", "bottom-left", "bottom-right"}
    for _mg_out in motion_graphics_out:
        _mg_props_anchor = str((_mg_out.get("props") or {}).get("anchor") or "")
        if _mg_props_anchor not in _BOTTOM_MG_ANCHORS:
            continue
        _mg_from = int(_mg_out["fromFrame"])
        _mg_to = _mg_from + int(_mg_out["durationInFrames"])
        for _cs_out in caption_position_segments_out:
            if _cs_out["toFrame"] <= _mg_from or _cs_out["fromFrame"] >= _mg_to:
                continue
            if _cs_out["position"] != "top":
                raise RuntimeError(
                    f"Z-order violation: motion_graphic {_mg_out['type']!r} with "
                    f"anchor={_mg_props_anchor!r} occupies the bottom half during output "
                    f"frames [{_mg_from}-{_mg_to}] ({_mg_from/source_fps:.2f}s-"
                    f"{_mg_to/source_fps:.2f}s), but caption_position_segment "
                    f"[{_cs_out['fromFrame']}-{_cs_out['toFrame']}] has "
                    f"position={_cs_out['position']!r} — it must be 'top' to avoid "
                    f"caption/MG overlap. Gemini violated Rule #5: the plan should "
                    f"have placed captions at 'top' across this window."
                )

    # ── 8. Assemble Remotion input + write JSON ─────────────────────────────
    # Face trajectory no longer piped into Remotion — the motion-graphics pack
    # components position themselves via resolveMGPosition against the canvas,
    # and no other composition layer consumes face data at render time.
    _outro = edit_plan.get("outro") or "none"

    # Remotion serves local files via its bundle server, which resolves every
    # request against `publicDir` (set to `work_dir` by render-full.mjs). We
    # emit BASENAMES for every local-file URL so the browser asks the server
    # for e.g. `/source_30fps.mp4` and the server finds it in work_dir. If we
    # kept absolute /tmp paths, the server would try `/remotion/bundle/tmp/...`
    # and 404. Verify every referenced file is actually inside work_dir.
    _source_src = os.path.basename(source_path)
    if os.path.dirname(source_path) != work_dir:
        raise RuntimeError(
            f"source_path ({source_path}) is not inside work_dir ({work_dir}); "
            f"Remotion's publicDir server cannot serve it. Move the source into "
            f"work_dir before calling render_multi_clip."
        )
    for _br in broll_out:
        _full = _br["src"]
        if os.path.dirname(_full) != work_dir:
            raise RuntimeError(
                f"broll src ({_full}) is not inside work_dir ({work_dir}); "
                f"Remotion's publicDir server cannot serve it."
            )
        _br["src"] = os.path.basename(_full)

    remotion_input = {
        "sourceUrl": _source_src,
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
        "outro": _outro,
    }
    if color_out:
        remotion_input["colorEffect"] = color_out

    remotion_input_json = os.path.join(work_dir, "promptly_render_input.json")
    with open(remotion_input_json, "w") as _f:
        json.dump(remotion_input, _f)
    print(
        f"[render] Remotion input: {len(clips_out)} clips, {len(transitions_out)} transitions, "
        f"{len(broll_out)} broll, {len(caption_pages)} pages, {len(text_overlays_out)} text_overlays, "
        f"{len(motion_graphics_out)} MG, {total_output_frames} frames @ {source_fps:.2f}fps",
        flush=True,
    )

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

    # Speed-curved audio — numpy-resampled pitch-scaling, mirrors video's
    # playbackRate on a per-sub-clip basis.
    _speed_audio_future = None
    _audio_pool = None
    _has_speed_curve = (speed_curve and speed_curve != "none" and isinstance(speed_curve, list))
    if _has_speed_curve:
        _audio_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        _subclip_bounds_src = sorted(set(
            [round(float(rc["source_start"]), 3) for rc in render_cuts] +
            [round(float(rc["source_end"]), 3) for rc in render_cuts]
        ))
        _aware_speed_curve = [
            {"t": _t, "speed": get_speed_linear_interp(_t, speed_curve)}
            for _t in _subclip_bounds_src
        ]
        _speed_audio_future = _audio_pool.submit(
            build_speed_curved_audio, source_path, _presplit_cuts,
            _aware_speed_curve, _presplit_effective_durations,
            work_dir, sample_rate=sample_rate,
        )

    # ── 10. Launch Remotion render (blocking; audio future runs in parallel) ─
    silent_video_path = os.path.join(work_dir, "silent_video.mp4")
    _gl_mode = "angle-egl" if _HAS_HWACCEL else "swiftshader"
    _remotion_concurrency = max(4, min(int((os.cpu_count() or 32) // 2), 32))
    _render_cmd = [
        "node", "/remotion/render-full.mjs",
        "--input", remotion_input_json,
        "--output", silent_video_path,
        "--public-dir", work_dir,
        "--concurrency", str(_remotion_concurrency),
        "--gl", _gl_mode,
    ]
    _render_t0 = time.time()
    print(f"[render] Launching Remotion render ({_remotion_concurrency} concurrent, gl={_gl_mode})...", flush=True)
    _render_r = subprocess.run(_render_cmd, capture_output=True, text=True, timeout=900)
    _render_elapsed = time.time() - _render_t0
    if _render_r.returncode != 0:
        raise RuntimeError(
            f"Remotion render failed (rc={_render_r.returncode}): "
            f"{(_render_r.stderr or '')[-2000:]}"
        )
    # Echo Remotion's stdout for observability
    if _render_r.stdout:
        for _line in _render_r.stdout.split("\n")[-40:]:
            if _line.strip():
                print(f"[remotion] {_line}", flush=True)
    if not os.path.exists(silent_video_path) or os.path.getsize(silent_video_path) < 10000:
        raise RuntimeError(f"Remotion produced invalid output: {silent_video_path}")
    print(f"[render] Remotion video done in {_render_elapsed:.1f}s ({os.path.getsize(silent_video_path)/1024/1024:.1f}MB silent mp4)", flush=True)

    # Collect speed-curved audio (fails fast — no fallback to plain audio
    # because speed ramps would desync).
    if _speed_audio_future:
        _speed_audio_path = _speed_audio_future.result(timeout=60)
        if _audio_pool:
            _audio_pool.shutdown(wait=False)
        if not _speed_audio_path or not os.path.exists(_speed_audio_path):
            raise RuntimeError(f"Speed-curved audio pipeline produced no output at {_speed_audio_path}")
    else:
        # No speed curve — extract plain source audio once.
        _speed_audio_path = os.path.join(work_dir, "plain_audio.wav")
        _plain = subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-i", source_path, "-vn",
             "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", "1",
             _speed_audio_path],
            capture_output=True, text=True, timeout=60,
        )
        if _plain.returncode != 0:
            raise RuntimeError(f"Plain audio extraction failed: {(_plain.stderr or '')[-500:]}")

    # ── 11. Build final audio (SFX mix + ducking + EQ chain) → .m4a ─────────
    _audio_filter_parts = []
    _audio_out = "[audio_base]"
    _audio_out_initial = "[audio_base]"
    if sfx_audio_labels and sfx_timestamps:
        _duck_parts = []
        for _dt in sorted(set(sfx_timestamps)):
            _dip_start = max(0, _dt - 0.05)
            _dip_end = _dt + 0.25
            _duck_parts.append(
                f"if(between(t,{_dip_start:.3f},{_dip_end:.3f}),"
                f"0.45+0.55*max(0,min(abs(t-{_dt:.3f})/0.15,1)),"
                f"1)"
            )
        if _duck_parts:
            _duck_expr = "*".join(_duck_parts[:20])
            _audio_filter_parts.append(f"{_audio_out}volume='{_duck_expr}':eval=frame[audio_ducked]")
            _audio_out = "[audio_ducked]"
            print(f"[sfx] Audio ducking: {len(_duck_parts)} dip point(s)", flush=True)
        _n_sfx = len(sfx_audio_labels) + 1
        _sfx_labels_str = _audio_out + "".join(sfx_audio_labels)
        _audio_filter_parts.append(
            f"{_sfx_labels_str}amix=inputs={_n_sfx}:duration=first:dropout_transition=0:normalize=0[audio_sfx_mixed]"
        )
        _audio_out = "[audio_sfx_mixed]"
        print(f"[sfx] Mixed {len(sfx_audio_labels)} SFX track(s) into audio", flush=True)
    _audio_filter_parts.append(f"{_audio_out}{audio_chain}[final_audio]")
    _audio_filter_parts.insert(0, f"[0:a]asetpts=PTS-STARTPTS{_audio_out_initial}")
    _audio_fc = ";".join(sfx_filter_strs + _audio_filter_parts)

    _final_audio_path = os.path.join(work_dir, "final_audio.m4a")
    _audio_t0 = time.time()
    _audio_cmd = (
        ["ffmpeg", "-y", "-v", "warning", "-threads", "0",
         "-i", _speed_audio_path]
        + sfx_input_args
        + ["-filter_complex", _audio_fc,
           "-map", "[final_audio]",
           "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart",
           _final_audio_path]
    )
    _audio_r = subprocess.run(_audio_cmd, capture_output=True, text=True, timeout=180)
    if _audio_r.returncode != 0:
        raise RuntimeError(f"Audio post-processing failed: {(_audio_r.stderr or '')[-600:]}")
    _audio_elapsed = time.time() - _audio_t0
    print(f"[render] Final audio built in {_audio_elapsed:.1f}s → {_final_audio_path}", flush=True)

    # ── 12. Mux silent video + final audio → output.mp4 (no video re-encode) ─
    _mux_t0 = time.time()
    _mux_cmd = [
        "ffmpeg", "-y", "-v", "warning",
        "-i", silent_video_path,
        "-i", _final_audio_path,
        "-map", "0:v:0", "-c:v", "copy",
        "-map", "1:a:0", "-c:a", "copy",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]
    _mux_r = subprocess.run(_mux_cmd, capture_output=True, text=True, timeout=120)
    if _mux_r.returncode != 0:
        raise RuntimeError(f"Final mux failed: {(_mux_r.stderr or '')[-500:]}")
    _mux_elapsed = time.time() - _mux_t0
    print(f"[render] Mux done in {_mux_elapsed:.1f}s", flush=True)
    print(
        f"[render] Total render: remotion={_render_elapsed:.1f}s audio={_audio_elapsed:.1f}s "
        f"mux={_mux_elapsed:.1f}s → {os.path.getsize(output_path)/1024/1024:.1f}MB",
        flush=True,
    )


# ─── CAPTION / COMPONENT VOCABULARIES (enforced at validation + render time) ───

VALID_CAPTION_STYLES = {
    "HormoziPopIn", "GlitchHighlight", "EmojiPop", "NegativeFlash", "PaperII",
    "Prime", "Prism", "TypewriterReveal", "CinematicLetterpress", "Cove",
    "Dimidium", "EditorialPop", "Gadzhi", "Illuminate", "Lumen",
    "MagazineCutout", "Passage", "Pulse", "Quintessence", "Serif", "StaggerWave",
}

VALID_COLOR_TYPES = {
    "CinematicGrade", "BleachBypass", "VintageFilm", "DreamHaze", "ChromaSplit",
    "VignettePulse", "InvertStrike", "CineMono", "GoldenHour", "FilmGrain",
    "Portra", "NeoNoir",
}

VALID_TRANSITION_TYPES = {
    "CardSwipe", "ZoomThrough", "SlideOver", "Stack", "CrossfadeZoom",
    "ShutterFlash", "LightLeak", "StepPush", "NewspaperWipe", "FilmStrip",
    "SceneTitle",
}

VALID_ZOOM_TYPES = {
    "SmoothPush", "SnapReframe", "FocusWindow", "StepZoom", "LetterboxPush",
    "StageZoom", "DepthPull",
}

VALID_MG_TYPES = {
    "LowerThird", "AnnotationArrow", "BRollFrame", "ChartReveal", "ChatThread",
    "ComparisonSplit", "Notification", "ProgressBar", "QuoteCard", "RecordingFrame",
    "StatCard", "StickyNotes", "Toggle", "TornPaper",
    "TweetBubble", "InstagramComment", "IMessageBubble", "TikTokComment",
}


def _build_tiktok_pages_from_projected(projected_words, max_words_per_page=3):
    """Convert projected Deepgram words into TikTokPage[] structured for the
    @remotion/captions types consumed by the pack caption components.

    Each page covers up to `max_words_per_page` consecutive words. Page
    boundaries also break on large gaps (>0.6s) or sentence-end punctuation.
    """
    if not projected_words:
        return []
    pages = []
    current_tokens = []
    current_start_ms = None
    current_text_parts = []
    last_word_end = None
    SENTENCE_END = {".", "!", "?"}

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

    for w in projected_words:
        w_start = float(w.get("start") or 0)
        w_end = float(w.get("end") or w_start)
        w_text = w.get("punctuated_word") or w.get("word") or ""
        if not w_text.strip():
            continue
        # Break on big gap
        if current_tokens and last_word_end is not None:
            if w_start - last_word_end > 0.6:
                _flush()
        if current_start_ms is None:
            current_start_ms = int(round(w_start * 1000))
        # Token times are page-relative (fromMs is relative to page start)
        token_from_ms = int(round(w_start * 1000)) - current_start_ms
        token_to_ms = int(round(w_end * 1000)) - current_start_ms
        current_tokens.append({
            "text": w_text,
            "fromMs": max(0, token_from_ms),
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
    simple_keyword_prop = {
        "EditorialPop": "keywords",
        "Gadzhi": "keywords",
        "Illuminate": "keywords",
        "Lumen": "keywords",
        "Passage": "keywords",
        "Pulse": "keywords",
        "Serif": "keywords",
        "Dimidium": "highlightWords",
        "Prime": "specialWords",
        "Cove": "boxedWords",
    }
    # Styles that expect {text, color?} entries — we emit default color per style
    rich_keyword_styles = {
        "HormoziPopIn": ("highlightWords", "#F5C518"),
        "GlitchHighlight": ("highlightWords", None),
    }

    if style in simple_keyword_prop:
        prop_name = simple_keyword_prop[style]
        if kw_list and prop_name not in out:
            out[prop_name] = kw_list
    elif style in rich_keyword_styles:
        prop_name, default_color = rich_keyword_styles[style]
        if kw_list and prop_name not in out:
            if default_color:
                out[prop_name] = [{"text": w, "color": default_color} for w in kw_list]
            else:
                out[prop_name] = [{"text": w} for w in kw_list]
    return out



# ─── MAIN HANDLER ─────────────────────────────────────────────────────────────

def classify_error(e):
    """
    Convert a pipeline exception into a user-facing message.
    Returns a string safe to display directly to the user.
    """
    msg = str(e)

    # File / input problems — user can fix these
    if "No video stream found" in msg:
        return "We couldn't read your video file. Please make sure it's a standard video format (MP4, MOV, or similar)."
    if "Landscape video" in msg:
        return "Promptly works with vertical videos (9:16). Please upload a portrait-orientation clip."

    # Edit generation — no cuts produced
    if "missing cuts array" in msg:
        return "We couldn't generate an edit for this video. Try a different vibe or a longer clip."

    # Analysis problems
    if "Gemini file upload timed out" in msg:
        return "Your video took too long to upload for analysis. Please try again."
    if "Failed to parse Gemini" in msg or "parse Gemini" in msg:
        return "We had trouble analyzing your video. Please try again."

    # Edit recipe problems
    if "Empty Gemini response" in msg or "valid JSON from Gemini" in msg:
        return "We had trouble generating your edit. Please try again."
    if "source_start" in msg or "source_end" in msg or "chronological" in msg:
        return "We had trouble generating your edit. Please try again."

    # Render problems
    if "FFmpeg failed" in msg or "Pre-split mismatch" in msg:
        return "We had trouble rendering your video. Please try again."

    # Config / internal — user can't fix, keep it vague
    return "Something went wrong. Please try again."


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


def prewarm_handler(job):
    """Aggressive pre-processing during iOS upload.

    Runs S3 download AND URL-based Deepgram transcription in parallel, caching
    both into the Modal Volume keyed by sha1(bucket/key). When the real render
    job arrives and hits cache, it skips BOTH stages entirely — UI never shows
    'Loading your footage' OR 'Transcribing every word'.

    Idempotent: if artifacts already exist, returns immediately. Fire-and-forget
    from iOS attach, so latency here doesn't affect UX.
    """
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
        transcript_cache = os.path.join(cache_dir, "transcript.json")

        source_hit = os.path.exists(source_cache) and os.path.getsize(source_cache) > 1024
        transcript_hit = os.path.exists(transcript_cache) and os.path.getsize(transcript_cache) > 2

        if source_hit and transcript_hit:
            size_mb = os.path.getsize(source_cache) / (1024 * 1024)
            print(f"[prewarm] FULL HIT {cache_key} ({size_mb:.1f}MB source + transcript)", flush=True)
            return {"status": "cached", "cache_key": cache_key, "size_mb": round(size_mb, 1)}

        os.makedirs(cache_dir, exist_ok=True)
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

        # Download + transcribe in parallel.
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        fut_dl = None
        fut_tx = None
        if not source_hit:
            print(f"[prewarm] start download → {cache_key}/source.mp4", flush=True)
            fut_dl = pool.submit(
                lambda: _aws_s3_client.download_file(dl_bucket, dl_key, source_cache, Config=_S3_TRANSFER_CONFIG)
            )
        if not transcript_hit and presigned_url and DeepgramClient is not None:
            print(f"[prewarm] start URL-based transcribe → {cache_key}/transcript.json", flush=True)
            fut_tx = pool.submit(transcribe_audio_url, presigned_url)

        if fut_dl is not None:
            fut_dl.result()
        if fut_tx is not None:
            _tx_result = fut_tx.result()
            if _tx_result is not None:
                with open(transcript_cache, "w") as f:
                    json.dump(_tx_result, f)
                print(f"[prewarm] transcript cached ({len(_tx_result.get('words') or [])} words)", flush=True)
            else:
                print("[prewarm] transcribe returned None (fallback will handle in main job)", flush=True)

        pool.shutdown(wait=False)

        elapsed = time.time() - t0
        size_mb = os.path.getsize(source_cache) / (1024 * 1024) if os.path.exists(source_cache) else 0
        print(f"[prewarm] cached {cache_key} ({size_mb:.1f}MB in {elapsed:.1f}s)", flush=True)
        return {
            "status": "success",
            "cache_key": cache_key,
            "size_mb": round(size_mb, 1),
            "download_time": round(elapsed, 1),
            "transcript_cached": os.path.exists(transcript_cache),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


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
        vibe      = input_data["vibe"]
        upload_url = input_data["upload_url"]
        user_id   = input_data["user_id"]

        # ── Re-edit mode resolution ──────────────────────────────────────
        # mode: "full" (default — fresh plan), "render_only" (render supplied plan
        # deterministically), "tweak" (plan-diff + render new plan), "reinterpret"
        # (fuse old vibe + change_request, full pipeline with cached intermediates).
        mode = str(input_data.get("mode") or "full").strip().lower()
        if mode not in ("full", "render_only", "tweak", "reinterpret"):
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
        if mode == "reinterpret" and not change_request:
            return {"error": "reinterpret mode requires change_request in input"}

        work_dir    = tempfile.mkdtemp(prefix=f"promptly-{job_id}-")
        source_path = os.path.join(work_dir, "source.mp4")
        output_path = os.path.join(work_dir, "output.mp4")

        print(f"\n{'='*80}", flush=True)
        print(f"JOB {job_id}: \"{vibe}\"", flush=True)
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
        elif not provided_transcript and mode in ("full", "reinterpret"):
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
        # Only run URL-based Deepgram when we actually need a transcript and
        # don't already have one from prewarm cache or re-edit input.
        _can_url_transcribe = (
            mode not in ("render_only", "tweak")
            and not provided_transcript
            and _deepgram_presigned is not None
            and DeepgramClient is not None
        )
        future_url_transcript = None
        if _can_url_transcribe:
            print("[pipeline] kicking off Deepgram URL-based transcribe in parallel with download", flush=True)
            future_url_transcript = _early_pool.submit(transcribe_audio_url, _deepgram_presigned)

        # Trend profile fetch — pure DB read, no file dependency. Skip in
        # render_only (uses snapshot) and when a snapshot was provided.
        _can_parallel_trend = mode in ("full", "reinterpret") and not provided_trend
        future_early_trend = None
        if _can_parallel_trend:
            future_early_trend = _early_pool.submit(get_trend_context)

        # Move source bytes into the job's work_dir — cache hit = ~100ms copy,
        # miss = real S3 download (still fast after boto3[crt] + same-region).
        if _has_cached_source:
            import shutil as _sh
            _sh.copy(_cached_source_path, source_path)
            _dl_method = "prewarm-cache"
        else:
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
            else:
                # reinterpret or fallback — fuse vibe and run full pipeline from source
                vibe = diff.get("fused_vibe") or f"{old_vibe or vibe} — {change_request}".strip(" —")
                change_summary = diff.get("human_summary")
                mode = "reinterpret"
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
            result = transcribe_audio(audio_path)
            if os.path.exists(audio_path):
                os.remove(audio_path)
            return result

        def _do_gemini_proxy():
            """Encode 240p proxy and return bytes for inline Gemini API call.
            Skips the file upload + poll cycle (~6s) by sending bytes directly."""
            try:
                _proxy_t = time.time()
                _proxy_path = os.path.join(work_dir, "gemini_proxy.mp4")
                _proxy_venc = (["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "35"]
                               if _HAS_NVENC else
                               ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "32"])
                _hw_dec = ["-hwaccel", "cuda"] if _HAS_HWACCEL else []
                _proxy_cmd = subprocess.run(
                    ["ffmpeg", "-y", "-threads", "0"] + _hw_dec + ["-i", _raw_source,
                     "-vf", "scale=240:-2,fps=5"] + _proxy_venc + [
                     "-c:a", "aac", "-b:a", "32k", "-ac", "1",
                     _proxy_path],
                    capture_output=True, text=True, timeout=30,
                )
                if _proxy_cmd.returncode != 0 or not os.path.exists(_proxy_path):
                    raise RuntimeError(f"Gemini proxy encode failed: {(_proxy_cmd.stderr or '')[-300:]}")
                with open(_proxy_path, "rb") as f:
                    _proxy_bytes = f.read()
                _proxy_mb = len(_proxy_bytes) / (1024 * 1024)
                print(f"[pipeline] Gemini proxy: 240p@10fps {_proxy_mb:.1f}MB in {time.time()-_proxy_t:.1f}s (inline, no upload)", flush=True)
                return _proxy_bytes
            except Exception as e:
                raise RuntimeError(f"Gemini proxy encode failed: {e}") from e

        def _do_loudness():
            return measure_source_loudness(_raw_source)

        def _do_shot_changes():
            send_progress(job_id, "shots", 18, "Detecting shot changes", app_url)
            return detect_shot_changes(_raw_source)

        def _do_vocal_emphasis():
            return detect_vocal_emphasis(_raw_source)

        def _do_fps_normalize():
            """Ensure source is exactly 30fps CFR. Skips re-encode when source
            is already 30/1 declared AND ~30.0 measured; otherwise re-encodes
            via fps=30 filter. Runs in parallel with Gemini edit (~14s
            critical path), so the ~3-5s re-encode adds zero wall-clock time.
            Returns the path to the 30fps source (raw path if no re-encode)."""
            _cached = _probe_full(_raw_source)
            _vs = next((s for s in (_cached.get("streams") or []) if s.get("codec_type") == "video"), {})
            _r_rate_str = _vs.get("r_frame_rate", "")
            _avg_rate_str = _vs.get("avg_frame_rate", "")

            def _parse_rate(s):
                if not s or s == "0/0":
                    return 0.0
                if "/" in s:
                    _n, _d = s.split("/")
                    _d = float(_d)
                    return float(_n) / _d if _d > 0 else 0.0
                return float(s)

            _avg = _parse_rate(_avg_rate_str)
            if _r_rate_str == "30/1" and abs(_avg - 30.0) < 0.005:
                print(
                    f"[fps-normalize] Source already exactly 30fps "
                    f"(r={_r_rate_str}, avg={_avg:.4f}) — no re-encode",
                    flush=True,
                )
                return _raw_source

            _norm_t0 = time.time()
            _norm_path = os.path.join(work_dir, "source_30fps.mp4")
            _r_out = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-threads", "0",
                 "-i", _raw_source,
                 "-vf", "fps=30",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                 "-c:a", "copy",
                 "-video_track_timescale", "90000",
                 _norm_path],
                capture_output=True, text=True, timeout=180,
            )
            if _r_out.returncode != 0 or not os.path.exists(_norm_path):
                raise RuntimeError(
                    f"FPS normalization to 30fps CFR failed: "
                    f"{(_r_out.stderr or '')[-500:]}"
                )
            _size_mb = os.path.getsize(_norm_path) / (1024 * 1024)
            _r_val = _parse_rate(_r_rate_str)
            print(
                f"[fps-normalize] Converted r={_r_val:.4f}fps avg={_avg:.4f}fps "
                f"→ 30.0000fps CFR in {time.time() - _norm_t0:.1f}s ({_size_mb:.1f}MB)",
                flush=True,
            )
            return _norm_path

        # ── ALL initialization + Gemini edit in ONE parallel phase ────────────
        # Gemini starts as soon as transcript + upload + trend context are ready.
        # Everything runs concurrently — no sequential network calls on main thread.
        # If cached_analysis is provided (pre-computed by content-studio), skip the
        # entire Gemini chain (proxy encode + upload + poll + API call = ~19s savings).

        # Reinterpret mode reuses the prior Gemini visual analysis if we have one,
        # saving another Gemini roundtrip. content-studio's cached_analysis (legacy)
        # still wins if both are set.
        _cached_analysis = input_data.get("cached_analysis") or (provided_analysis if mode == "reinterpret" else None)

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

        def _do_content_analysis_overlapped():
            """Run the pre-edit content-analysis Gemini call in parallel with face
            detection and signal computation. Depends on transcript + proxy; its
            output (word classifications + tonal register) drives the main edit
            call's dynamic schema enums so that anchor-on-cut is structurally
            impossible.
            Returns (mechanical_cuts, content_analysis) tuple."""
            # Wait for the same transcript the edit call will use.
            if future_url_transcript is not None:
                _transcript = future_url_transcript.result()
                if _transcript is None:
                    _transcript = future_transcribe.result() if future_transcribe is not None else {"words": []}
            elif future_transcribe is not None:
                _transcript = future_transcribe.result()
            else:
                _transcript = provided_transcript or {"words": []}
            _dg_words = _transcript.get("words", []) or []
            if not _dg_words:
                return ({"word_cuts": set(), "range_cuts": [], "reasons": {}},
                        {"word_cuts": set(), "cuttable": set(), "protected": set(),
                         "peaks": set(), "tonal_register": "casual"})
            # Mechanical pre-pass — deterministic, ~5ms.
            _mech = mechanical_cut_pass(_dg_words)
            # Need the proxy bytes for the context-aware analysis call.
            _proxy_bytes = (
                future_gemini_proxy.result() if future_gemini_proxy is not None else None
            )
            _analysis = run_content_analysis(_dg_words, _proxy_bytes, _mech)
            return _mech, _analysis

        def _do_edit_recipe_overlapped():
            """Start Gemini as soon as transcript + proxy + trend + audio + face signals are ready.
            Transcript may come from the early_pool URL-based Deepgram call (ran in parallel
            with the download), a regular mega-pool file-based call, or the provided_transcript
            for re-edit paths. Whichever landed first wins — fall back chain handles URL failure."""
            if future_url_transcript is not None:
                _transcript = future_url_transcript.result()
                if _transcript is None:
                    # URL-based call failed; fall back to mega-pool file-based one
                    print("[pipeline] URL transcript failed — awaiting fallback file-based transcribe", flush=True)
                    _transcript = future_transcribe.result() if future_transcribe is not None else {"words": []}
                else:
                    print(f"[pipeline] transcript ready from URL-based Deepgram ({len(_transcript.get('words') or [])} words)", flush=True)
            elif future_transcribe is not None:
                _transcript = future_transcribe.result()
            else:
                _transcript = provided_transcript or {"words": []}
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
            # Wait for content-analysis (runs in parallel with face/signals).
            # This is the mechanism that makes anchor-on-cut structurally
            # impossible — analysis classifies every word into disjoint cut /
            # protected sets; the main-call schema uses those as enum
            # constraints.
            _mech_cuts, _analysis_result = (
                future_content_analysis.result()
                if future_content_analysis is not None
                else (
                    {"word_cuts": set(), "range_cuts": [], "reasons": {}},
                    {"word_cuts": set(), "cuttable": set(), "protected": set(),
                     "peaks": set(), "tonal_register": "casual"},
                )
            )
            return generate_edit_gemini(
                video_path=_raw_source,
                vibe=vibe,
                duration=source_duration,
                trend_context=_trend,
                deepgram_words=_dg_words,
                shot_changes=_shots,
                vocal_emphasis=_vocal,
                source_loudness=_loudness,
                face_positions=_face_positions,
                smoothed_face_trajectory=_smoothed_trajectory,
                user_style_profile=_user_profile,
                inline_video_bytes=_proxy_bytes,
                cached_response=_cached_analysis,
                content_analysis=_analysis_result,
                mechanical_cuts=_mech_cuts,
            )

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
            if _proxy_exists:
                # Proxy is 10fps — every 7th frame ≈ 1.4fps detection (similar to every 20th @ 30fps)
                dense = detect_face_positions_dense(
                    os.path.join(work_dir, "gemini_proxy.mp4"), every_n_frames=7,
                    target_w=1080, target_h=1920,
                )
            else:
                # No proxy (render_only) or proxy missing — use raw source
                dense = detect_face_positions_dense(_raw_source, every_n_frames=20)
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
        # Content-analysis Gemini pre-pass — runs in parallel with face detection
        # and signals. Waits internally on transcript + proxy. Its output drives
        # the main edit call's disjoint schema enums. Skipped in render_only.
        future_content_analysis = (
            None if _skip_edit_gen else mega_pool.submit(_do_content_analysis_overlapped)
        )
        # Edit recipe waits on transcript + upload + content-analysis internally — skipped entirely in render_only
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

        # Start B-roll fetch IMMEDIATELY while other futures may still be running
        _broll_fetch_pool = None
        _broll_fetch_futures = {}
        broll_clips = edit_plan.get("broll_clips") or []
        if broll_clips:
            send_progress(job_id, "broll_search", 52, "Sourcing B-roll cutaways", app_url)
            print(f"[broll] Starting parallel fetch of {len(broll_clips)} B-roll clip(s) (overlapping with face detect)...", flush=True)
            _broll_fetch_pool = concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(broll_clips)))
            for _bi, _bc in enumerate(broll_clips):
                _fut = _broll_fetch_pool.submit(
                    fetch_broll_clip,
                    _bc,  # pass whole entry — fetch_broll_clip mutates it with resolved Pexels metadata
                    float(_bc.get("duration") or 2.0),
                    work_dir,
                    dialogue_reason=str(_bc.get("reason") or ""),
                )
                _broll_fetch_futures[_fut] = _bi

        # Collect fast futures (all should be done already — they finish before Gemini).
        # Face detection is collected LATER inside render_multi_clip so Remotion can
        # launch immediately without waiting for face detection to finish.
        _collect_t0 = time.time()
        source_info = future_normalize.result()
        source_path = source_info["source_path"]
        _normalize_vf = source_info.get("normalize_vf")
        if future_url_transcript is not None:
            # Early-pool URL transcript ran in parallel with the download.
            # If it failed (returned None), fall through to local fallback.
            _url_tx = future_url_transcript.result()
            if _url_tx is not None:
                transcript = _url_tx
            elif future_transcribe is not None:
                transcript = future_transcribe.result()
            else:
                transcript = provided_transcript or {"words": []}
        elif future_transcribe is not None:
            transcript = future_transcribe.result()
        else:
            # render_only / reinterpret with cached transcript — no Deepgram call this pass
            transcript = provided_transcript or {"words": []}
            print(f"[pipeline] Using provided transcript ({len(transcript.get('words') or [])} words) — skipped Deepgram", flush=True)
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
        # Swap in the 30fps-normalized source for render. fps_normalize ran in
        # parallel with Gemini so this is already done by the time we get here.
        # Downstream render detects source_fps=30.0 from the new file's r_frame_rate
        # and all frame-count math becomes exact.
        source_path = future_fps_normalize.result()
        # NOTE: future_faces NOT collected here — passed to render_multi_clip for parallel collection
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
            print(f"[reframe] Smart reframe active via normalize_vf (folded into render pass)", flush=True)
        else:
            print("[reframe] Source is native 9:16 — no reframe needed", flush=True)

        edit_plan["_user_vibe"] = vibe
        edit_plan["_source_path"] = source_path
        edit_plan["_normalize_vf"] = _normalize_vf
        edit_plan["_source_loudness"] = source_loudness
        edit_plan["_shot_changes"] = source_shot_changes
        _timings["edit_recipe_faces"] = 0
        print(f"[pipeline] Pipeline init phase complete", flush=True)

        # Hook is Gemini's decision. If it picked one, we render it. If it
        # said null, the video starts with the first content clip. No fallback
        # hook detection — Gemini has the signals (video, transcript, shot
        # changes, vocal emphasis, loudness) to make this call.
        _gh = edit_plan.get("hook_clip") if isinstance(edit_plan.get("hook_clip"), dict) else None
        if _gh:
            print(f"[hook] Gemini picked {_gh['source_start']:.2f}-{_gh['source_end']:.2f}", flush=True)
        else:
            print("[hook] Gemini picked None (no hook)", flush=True)
        analysis = edit_plan.get("analysis_data") or {}

        # B-roll fetch already started inside mega-parallel phase (right after edit_plan ready)

        print("[pipeline] step=parallel_render", flush=True)
        send_progress(job_id, "render", 65, "Rendering your edit", app_url)
        t = time.time()
        render_multi_clip(
            source_path, edit_plan["cuts"], edit_plan, output_path, transcript, work_dir,
            broll_clips=broll_clips, broll_fetch_futures=_broll_fetch_futures,
        )
        if _broll_fetch_pool:
            _broll_fetch_pool.shutdown(wait=False)
        edit_plan["_deepgram_words"] = transcript.get("words", [])

        render_elapsed = time.time() - t
        _timings["render"] = render_elapsed
        print(f"[pipeline] parallel_render complete in {render_elapsed:.1f}s", flush=True)
        _enc_label = "NVENC" if _HAS_NVENC else "libx264/ultrafast threads=auto"
        print(f"[render] Encoding: {_enc_label}", flush=True)
        speed_curve = edit_plan.get("_parsed_speed_curve")
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

        cuts = edit_plan.get("_render_cuts") or edit_plan.get("cuts") or []
        effective_durations = edit_plan.get("_render_effective_durations") or compute_effective_durations(cuts, speed_curve)
        final_dur = _rv

        # B-roll is now integrated into the first FFmpeg pass (no second encode needed)
        _timings["broll"] = 0.0

        # ── Parallel group 2: cover frame + upload ────────────────────────────────
        t = time.time()
        thumbnail_source_ts = edit_plan.get("thumbnail_timestamp")
        if thumbnail_source_ts is None:
            thumbnail_source_ts = (source_duration / 3.0) if source_duration > 0 else 1.0
        speed_curve = edit_plan.get("_parsed_speed_curve")
        cover_frame_ts = project_source_time_to_final_output(
            float(thumbnail_source_ts),
            cuts,
            effective_durations,
            speed_curve,
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
            # Direct SDK upload to S3 — faster than presigned URL PUT.
            # CloudFront serves the content via CDN.
            _s3_bucket = os.environ.get("S3_BUCKET_NAME", "")
            _cf_domain = os.environ.get("CLOUDFRONT_DOMAIN", "")
            if _aws_s3_client and _s3_bucket:
                _ul_key = f"rendered/{job_id}/output.mp4"
                _aws_s3_client.upload_file(
                    output_path, _s3_bucket, _ul_key,
                    ExtraArgs={"ContentType": "video/mp4"},
                )
                if _cf_domain:
                    _video_url = f"https://{_cf_domain.rstrip('/')}/{_ul_key}"
                else:
                    _video_url = f"https://{_s3_bucket}.s3.{os.environ.get('AWS_REGION', 'us-west-1')}.amazonaws.com/{_ul_key}"
                print(f"[pipeline] upload complete (s3-direct → {_video_url})", flush=True)
                # Store for webhook/SSE to return to client
                edit_plan["_rendered_video_url"] = _video_url
            else:
                # Legacy: presigned URL upload
                with open(output_path, "rb") as f:
                    resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=120)
                    resp.raise_for_status()
                print("[pipeline] upload complete (presigned-put)", flush=True)

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

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as post_executor:
            f_upload = post_executor.submit(_upload_main)
            f_cover  = post_executor.submit(_extract_and_upload_cover)
            f_upload.result()
            cover_bytes, _ = f_cover.result()

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

        # Sanitized recipe for persistence — drops internal _foo fields and analysis_data
        # (which is persisted separately so we don't double-store it).
        sanitized_recipe = {k: v for k, v in edit_plan.items() if k != "analysis_data" and not (isinstance(k, str) and k.startswith("_"))}

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
        if cover_frame_b64:
            result_payload["cover_frame_b64"]  = cover_frame_b64
            result_payload["cover_frame_mime"] = "image/jpeg"
        if exported_formats:
            result_payload["exported_formats"] = exported_formats
        return result_payload

    except Exception as e:
        import traceback
        traceback.print_exc()
        user_message = classify_error(e)
        return {"error": user_message, "error_detail": str(e)}

    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


# Modal entrypoint — handler() is called directly by modal_app.py
# To test locally: python3 handler.py
if __name__ == "__main__":
    print("[handler] Running in local test mode", flush=True)
