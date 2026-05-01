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
    PromptlyBlendCaptionsOnlyInput as _SchemaBlendCaptionsInput,
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

_CAPTION_STYLES = Literal[
    "PaperII",
    "Prime", "TypewriterReveal", "CinematicLetterpress", "Cove",
    "EditorialPop", "Illuminate", "Lumen",
    "MagazineCutout", "Passage", "Pulse", "Quintessence", "Serif",
    "GlitchHighlight", "NegativeFlash", "Prism",
]
# Caption styles that use CSS mixBlendMode against video pixels. They CANNOT
# render correctly on the transparent overlay alone (no pixels to blend
# against). The pipeline handles this in two passes: v62 produces the full
# video without these captions (handler zeroes out caption.pages and filters
# caption_match overlays for PromptlyOverlay's input), then a small second
# Remotion pass — PromptlyBlendCaptionsOnly — takes the v62 silent
# intermediate as <OffthreadVideo> source and lays the blend captions on top.
# Audio mux is the only further step.
_BLEND_MODE_CAPTION_STYLES = frozenset({"GlitchHighlight", "NegativeFlash", "Prism"})
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
    "AnnotationArrow", "ChatThread",
    "Notification", "ProgressBar", "QuoteCard", "RecordingFrame",
    "StatCard", "StickyNotes", "Toggle", "TornPaper",
    "TweetBubble", "InstagramComment", "IMessageBubble", "TikTokComment",
]
_SEMANTIC_ANCHOR = Literal[
    "upper_third_safe", "center", "lower_third_safe", "left_safe", "right_safe",
]
_TEXT_OVERLAY_VARIANTS = Literal[
    "torn_paper", "sticky_note", "quote_card", "caption_match",
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
    # Visual layers on an emphasis: zoom_effect (optional) and motion_graphic
    # (optional). Color effects were removed from the pipeline (talking-head
    # videos don't need cinematic grades) — emphasis is now purely a
    # zoom/MG/SFX combo.
    word_indices: List[int]
    type: Literal["punchline", "statement", "question", "reaction", "transition", "revelation"]
    intensity: Literal["high", "medium"]
    duration: float
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

class _RemoveWord(BaseModel):
    # Either a word_index (surgical single-word removal) or a start/end range
    # (continuous span — dead air, abandoned tangent, breath, etc.). Gemini
    # owns every cut decision; Python applies them verbatim. `reason` is a
    # free-form short label (filler / stutter / restart / dead_air / breath /
    # tangent / redundant / ...) — informational only.
    word_index: Optional[int] = None
    start: Optional[float] = None
    end: Optional[float] = None
    reason: str

class EditPlan(BaseModel):
    """Structural contract for Gemini's edit-plan output.

    Passed to generate_content as response_json_schema so invalid outputs
    are rejected at decode time. Cross-field semantic constraints (e.g.
    word_indices must reference kept words) still live in Python validators.

    FIELD ORDER MATTERS. JSON is generated top-to-bottom; each field's
    output flows into the model's working context for every field below it.
    The order here mirrors the order a human editor works:
      1. Reasoning  (notes)
      2. Decide cuts FIRST  (remove_words) — every anchor below sees them
      3. Set overall pace  (pacing)
      4. Pick visual identity  (caption_style + caption_keywords)
      5. Place the spine  (emphasis_moments) — the 2-5 strongest beats
      6. Mark scene boundaries  (transitions)
      7. Layer audio on emphasis  (sound_effects)
      8. Reinforce moments visually  (motion_graphics)
      9. Add chapter cards / hooks  (text_overlays)
      10. Cover dialogue with cutaways  (broll_clips)
      11. Position captions around MGs / face  (caption_position_changes)
      12. Pick the strongest still  (thumbnail_word_index)
      13. Settings  (audio_denoise / outro / aspect_ratio)

    Reordering this without keeping the prompt sections in lockstep with it
    will reintroduce the anchor-on-cut pattern that this order eliminates.
    """
    notes: str
    remove_words: List[_RemoveWord]
    pacing: Literal["fast", "medium", "slow"]
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


# ── Cutting architecture ────────────────────────────────────────────────────
# Gemini owns every cut decision. There is no Python-side filler / stutter /
# phrasal-restart / dead-air pre-pass — pattern matchers cannot tell the
# difference between an abandoned restart and a rhetorical repetition, so any
# pre-pass risks killing valuable content the main edit Gemini would have
# kept (see "I said who is, I said who is, he?" — pre-passes cut both
# occurrences leaving "he?" floating).
#
# The main edit call sees the full Deepgram transcript. Its `remove_words`
# field carries every cut: filler tokens, stutters, abandoned restarts,
# silence ranges, tangents — single source of truth. Python applies them
# verbatim at sample-precise Deepgram timestamps; no refinement, no buffer,
# no crossfade.


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

    # Create soname symlinks for NVIDIA libs (Modal mounts versioned .so
    # but not symlinks). NVDEC and CUDA-using consumers (RIFE, FFmpeg
    # cuvid) need libnvidia-* and libcuda.so.1 sonames to resolve.
    for _lib_dir in _nvidia_lib_dirs:
        try:
            for _f in os.listdir(_lib_dir):
                if (
                    _f.startswith("libnvidia-")
                    and ".so." in _f
                    and not _f.endswith(".so.1")
                    and not _f.endswith(".so.0")
                ):
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
# is set by the chunked overlay + chunked blend-captions architecture
# (Phase 1) — Vulkan was supposed to help on top of that, not be
# load-bearing.


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
            # CQ 18 = visually lossless on mobile. -maxrate 8M -bufsize 16M
            # caps streaming bandwidth so AVPlayer doesn't freeze mid-playback
            # on typical wifi/LTE.
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq",
                    "-rc", "vbr", "-cq", "18", "-b:v", "0",
                    "-maxrate", "8M", "-bufsize", "16M",
                    "-spatial-aq", "1", "-temporal-aq", "1",
                    "-b_ref_mode", "middle"]
    else:
        # CPU encoding (H100 has no NVENC). `veryfast` is the right floor
        # for any encode the user actually watches: enables CABAC, B-frames,
        # and the deblocking filter that ultrafast disables. ultrafast was
        # producing visible compression artifacts at the 8M bitrate cap.
        # threads=0 lets x264 auto-detect (use all cores). Pass an explicit
        # value when running many ffmpeg processes in parallel — otherwise
        # each process tries to claim every core, producing massive
        # context-switch contention.
        # `lossless` intermediates stay on `ultrafast` since the quality
        # ceiling is already perfect (no loss) and the speed matters for
        # parallel render time.
        _x264_threads = f"threads={threads}"
        if quality == "lossless":
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                    "-fps_mode", "passthrough",
                    "-x264-params", _x264_threads]
        else:
            return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-maxrate", "8M", "-bufsize", "16M",
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

GUIDANCE — important:
- Use this profile as a LIGHT signal about general taste, NOT a "pick the same thing again" instruction.
- For caption_style specifically: AVOID picking whichever style ranks #1 in their history if it appeared in either of their last 2 videos. Variety is itself a quality signal — top creators rotate caption styles across videos to keep their feed visually fresh. Pick something else from the appropriate vibe row in the DECISION MATRIX below.
- For transitions, color effects, pacing: gentle bias toward their top picks is fine; people develop a consistent overall feel.
- If the current vibe EXPLICITLY contradicts (e.g. "completely different look"), ignore history entirely.
- The profile shows top 3 with recency-weighted counts. A score above ~3.0 means very recent + repeated; treat that as "the user already saw this; serve them something new this time."
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


def prepare_audio_for_deepgram(source_path: str) -> bytes:
    """Extract loudness-normalized mono FLAC for transcription.

    Sending raw video bytes (or pointing Deepgram at a URL) means Deepgram
    receives the source's compressed audio at whatever level the source was
    recorded at. Talking-head footage is often quiet (-27 dB RMS is typical)
    which sits at the edge of Deepgram's acoustic-model confidence on soft
    consonants — that's how words like "Stelius/Stelios" get inconsistent.

    This preprocessor produces:
      • mono channel — Deepgram's models are tuned for mono speech
      • 48 kHz sample rate — preserves all source detail
      • loudness normalized to -16 LUFS / -1.5 dBTP (broadcast standard) so
        every word arrives at a consistent, audible level
      • lossless FLAC encode — no second-generation lossy compression on top
        of whatever the source already lost in its AAC encode

    Returns FLAC bytes ready for Deepgram's transcribe_file. Typical size on
    a 60s clip: ~5-8 MB (vs 80 MB for the full video), so the upload is
    actually faster than sending the raw file too.
    """
    cmd = [
        "ffmpeg", "-v", "error", "-threads", "0",
        "-i", source_path,
        "-vn", "-ac", "1", "-ar", "48000",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
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
        f"(mono 48kHz, loudnorm -16 LUFS)",
        flush=True,
    )
    return proc.stdout


def _deepgram_options():
    return PrerecordedOptions(
        model="nova-3", detect_language=True,
        smart_format=True, utterances=True, punctuate=True, diarize=True,
        numerals=True,
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


def transcribe_audio(source_path):
    """File-based Deepgram with loudness-normalized FLAC audio prep.

    Sends the cleaned mono 48 kHz FLAC produced by prepare_audio_for_deepgram
    rather than the raw video bytes — gives the model uniform-level audio
    and saves bandwidth (FLAC of just the audio stream is much smaller than
    the full video). 3-attempt exponential backoff on retriable errors.
    """
    if DeepgramClient is None or PrerecordedOptions is None:
        print("[pipeline] transcription skipped: deepgram not available", flush=True)
        return {"text": "", "words": []}
    dg = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])
    audio_bytes = prepare_audio_for_deepgram(source_path)
    print(f"[deepgram] Sending {len(audio_bytes) / 1024:.0f}KB FLAC audio", flush=True)
    options = _deepgram_options()
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
    - sound_effects (drum_roll buildup ending at a peak, hit on the peak)

FACE VISIBILITY (source-seconds ranges; yes = face detected in 0.5s bucket)
  {_fv_display}

  Use this to choose overlays that make sense with what's on screen. When
  `visible=NO` for a window, the viewer is looking at b-roll, a product
  shot, text, or scenery — lean into that (e.g., use TornPaper/QuoteCard
  over scenery, StatCard over a product shot).

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
  {_off_center_line}{_shot_scale_block}"""

    # SYSTEM INSTRUCTION — stable content. No per-video interpolation (vibe,
    # duration, signals) lives here so the prefix stays byte-identical across
    # calls and implicit prompt caching can take effect. Per-video data is
    # injected via the USER message below.
    system_instruction = f"""You are a professional short-form video editor working on a 1080x1920 (9:16) vertical video for TikTok, Instagram Reels, and YouTube Shorts. You watch the full video at 5 frames per second — you see every shot, every face, every gesture, every on-screen element. You hear every word.

Your job: produce an edit plan that looks professionally crafted — every cut, every caption move, every zoom, every motion graphic has a narrative reason. Not random. Not accidental. Intentional.

=== HOW TO THINK ABOUT THIS EDIT ===

What does the user actually want? They want to watch the finished video and feel like a professional editor understood their footage and made it look incredible. The edit should feel intentional — every cut, every speed change, every sound has a reason.

As you watch, pay attention to:
  - Where the content changes (speaker → screen recording, topic shifts, visual changes)
  - Where the energy peaks (strong statements, reveals, punchlines) and where it dips (filler, transitions between ideas, breaths)
  - Where the viewer's attention would drift without intervention
  - What's already baked into the footage (burned-in captions, existing text, graphics)

You are the editor. You decide what stays and what gets cut. You understand the emotion and humor of what's being said. You know the difference between filler and content that matters.

=== WHAT MAKES SHORT-FORM CONTENT FEEL EDITED ===

The opening is an audition. The first 2 seconds must give the viewer a reason to stay — a visual event, a sonic hit, tight framing, text that creates curiosity. Something that signals this isn't raw footage. cut[0] must be the strongest attention-grabbing moment — see the OPENING section below for placement rules. Don't bury the lede.

Pacing creates rhythm. For short-form content, the average kept clip should be 2-3 seconds. The Captions app and top TikTok editors cut every 2-3 seconds — this is the standard. Filler and setup move even faster (1-2s). Key moments — reveals, punchlines, important statements — breathe (3-4s max). The contrast between fast and slow is what makes pacing feel alive. When in doubt, cut shorter.

Emphasis moments are the spine. The 2-5 hardest-hitting beats determine whether the edit feels professional or amateur. Identify them first — every other layer (caption_style, transitions, B-roll, per-clip speed, SFX) should orbit those beats.

Sound design adds texture. A sound effect on a punchline, a whoosh on a scene change, a boom when a statement lands — these make cuts feel physical instead of digital. But not every cut needs a sound. Continuous speech flows best with silent hard cuts.

The ending matters. On these platforms, videos auto-loop. A clean ending that flows back into the opening earns replay credit. Avoid fade to black (or fade to white) — the flash before the loop restarts breaks immersion. Default outro: "none".

=== CONTRACT ===

The pipeline enforces these rules with strict validators. Output that violates any rule is rejected.

1. POSITIONS ARE SEMANTIC ZONES. Use the named zones from the vocabulary (`upper_third_safe`, `center`, `lower_third_safe`, `left_safe`, `right_safe`). Pixel coordinates are not accepted.
2. EVERY TIMING IS WORD-ANCHORED. You never emit raw float timestamps. Anchor every time-based decision to a specific kept word via its index (start_word_index, end_word_index, word_index, word_indices, after_word_index, thumbnail_word_index). Python derives all float timestamps from word start/end times. The only float fields in your output are non-time values like `duration_seconds` (overlay lifespan), `intensity`, `scale`, and `speed`.
3. EVERY TEXT OVERLAY HAS A VARIANT + ITS REQUIRED PROPS. The `variant` field chooses which visual treatment; each variant has a specific set of required props documented in the TEXT OVERLAYS section.
4. CAPTIONS ARE WORD-ANCHORED + FACE-AWARE. Emit `caption_position_changes` as an array of `{{word_index, position}}` events — each event says "at this kept word, captions move to this position." Python synthesizes the final segment list with exact word-start timestamps. You watch the video — when the speaker's face moves into the bottom of the frame (looking down, leaning forward, low framing), emit a change to "top" at the first kept word in that window and back to "bottom" when the face returns up. Captions over the speaker's mouth are unreadable; place them so they never cover the face.
5. Z-ORDER YIELDS TO MOTION GRAPHICS — YOU OWN IT. Python does NOT auto-flip caption position for MG overlap. If a motion_graphic sits at "lower_third_safe" or any bottom-anchored zone across a window, you must emit a caption_position_change to "top" at the MG's start_word_index and back to "bottom" at the word immediately after end_word_index. Same rule for "center" MGs that visually cover the speaker.
6. ZONE DISCIPLINE FOR OVERLAYS. Overlays in DIFFERENT visual zones can freely share a time window. Overlays in the SAME zone at the SAME time collide and are rejected. Each text_overlay variant renders into a fixed zone driven by its design (torn_paper / quote_card occupy the center band; sticky_note pins to upper_third_safe; caption_match follows its `position` prop). Motion_graphic zones come from the explicit `anchor` field — that's YOUR placement decision based on what's on screen during the MG's window. Two items collide only when their zones AND time windows both overlap. High-intensity emphasis moments are spaced ≥2.5s apart regardless of zone.
7. ONE ZOOM PER KEPT-SOURCE CLIP. At most one emphasis_moment carries a zoom_effect within any single kept-source clip (the source range between your removed-words boundaries). When you want multiple zoom beats close together, stack their events onto a single emphasis_moment's `zoom_effect.events` array.
8. MOTION GRAPHIC ANCHORS ARE ABSOLUTE ZONES — FACE-AWARE. Every `motion_graphics[i].anchor` and `emphasis_moments[i].motion_graphic.anchor` is one of the 5 absolute zones. You watch the source video — look at where the speaker's face sits in the frame across the MG's word window and pick an anchor that does NOT cover the face. If the face is in the middle of the frame, do not anchor to "center". If the face is in the lower third, avoid "lower_third_safe". The MG renders exactly where you place it; there is no fallback.
9. ANCHORS ARE KEPT WORDS. The transcript you see is the FULL Deepgram output, indexed [0..N-1]. Every word_index you emit (in `emphasis_moments[i].word_indices`, `sound_effects[i].word_index`, `text_overlays[i].start_word_index`, `motion_graphics[i].{{start,end}}_word_index`, `broll_clips[i].{{start,end}}_word_index`, `transitions[i].after_word_index`, `caption_position_changes[i].word_index`, `thumbnail_word_index`) references this same source index space. Any word you also list in remove_words is NOT a kept word and CANNOT be anchored. The renderer fails validation if you cross-reference a removed word.
10. EXPLICIT NULLS. If an emphasis moment has no zoom, emit `"zoom_effect": null` — no downstream defaults fill gaps.

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
  "lower_third_safe" — lower-third band, just above the TikTok/IG UI rail. Use for: tweet bubbles that frame at the bottom, IMessageBubble at bottom.
  "left_safe"        — left edge, vertically centered. Use when the speaker is on the RIGHT half of the frame (put the overlay OPPOSITE the speaker).
  "right_safe"       — right edge, vertically centered. Use when the speaker is on the LEFT half of the frame.

DECISION — which anchor:
- Speaker on camera-left → `right_safe` for overlays (see SPEAKER POSITIONS signal).
- Speaker on camera-right → `left_safe` for overlays.
- Speaker centered or off-camera → `upper_third_safe` / `lower_third_safe` / `center`.
- Notification stacks / top title cards → `upper_third_safe`.

=== CAPTIONS — WORD-BY-WORD RUNNING SUBTITLES ===

ONE style for the whole video. POSITION can change per segment.

caption_style — pick EXACTLY ONE from 16 styles. Read each description carefully — these are real components with distinct visual identities. Pick the one whose AESTHETIC matches the video's content register, not the one you used last time.

 1. "PaperII"              — Lora serif. Words transition from dim to bright as spoken. Strip-based stacking, heavy shadow. Editorial paper-strip feel.
                              Best for: Storytelling, narrative, poetry, journal-style, long-form.
 2. "Prime"                — Two-tier system: Inter body, special words break out onto a new line in oversized italic Playfair Display. The keyword break-line is the entire visual identity.
                              Best for: Aspirational content, premium branding, lifestyle.
 3. "TypewriterReveal"     — Character-by-character typewriter in Space Mono. Blinking cursor. NO keyword highlighting (animation IS the effect — every word looks the same).
                              Optional extraProps: {{"scheme": "classic"|"terminal"|"amber"}} — classic = white on black, terminal = green-on-black hacker, amber = orange phosphor monitor.
                              Best for: Tech/coding, thoughtful narration, documentary, retro.
 4. "CinematicLetterpress" — Words emerge from blur into focus — cinematic "focus pull" effect. Cormorant Garamond serif, light weight, wide letter-spacing. NO keyword highlighting (the blur-to-focus animation IS the effect).
                              Best for: Documentary, film-style intros, art house, slow contemplative.
 5. "Cove"                 — Bold Montserrat base, special words switch to oversized italic Playfair Display with warm ethereal glow. ~2x scale contrast. Keywords get the glow treatment.
                              Best for: Premium/luxury, brand storytelling, wellness, aspirational.
 6. "EditorialPop"         — All Playfair Display — keywords scale to 1.7x bold italic, body stays light. Two-line staggered reveal. Magazine-headline feel.
                              Best for: Magazine-style, fashion, interview quotes, premium editorial.
 7. "Illuminate"           — Playfair Display with a diagonal light sweep across each word as it appears. Keywords keep a warm lingering glow. Cinematic spotlight feel.
                              Best for: Cinematic narration, atmospheric storytelling, premium docs.
 8. "Lumen"                — Montserrat body, keywords switch to Playfair with amber glow and gold underline sweep. Shine words get a brightness flash.
                              Best for: Warm inspirational, golden-hour aesthetics, brand campaigns.
 9. "MagazineCutout"       — Individually cut-out paper pieces with cream background, random rotation, size variation. Collage / zine aesthetic. NO keyword highlighting (every word is its own cutout — the chaos IS the effect).
                              Optional extraProps: {{"maxRotation": 3}} for tight controlled craft, {{"maxRotation": 10}} for wild DIY chaos. Default 6.
                              Best for: Creative/art, collage, DIY/craft, zine-style, indie.
10. "Passage"              — Cormorant Garamond serif. Keywords expand letter-spacing on reveal and switch to italic warm gold. Literary, book-page feel.
                              Best for: Literary content, book quotes, long-form storytelling.
11. "Pulse"                — Two-slot paired display — words appear in pairs that fade in together. Keywords get cyan accent. Rhythmic, lyric-video feel.
                              Best for: Music, rhythmic narration, fast dialogue, lyric videos.
12. "Quintessence"         — Single word at a time, centered, Playfair Display with dramatic vertical stretch (scaleY). Gold text, spring entrance. NO keyword highlighting (every word is the focus — that's the whole point).
                              Optional extraProps: {{"stretchY": 1.6}} default, increase to 2.0 for more dramatic stretch, decrease to 1.3 for subtle.
                              Use for: Single-word emphasis moments, dramatic pauses, poetry, art-house.
13. "Serif"                — DM Serif Display body with keywords that scale up (1.35x) in italic with blue accent. Premium editorial / brand-message feel.
                              Best for: Premium editorial, interview quotes, brand messaging, calm.
14. "GlitchHighlight"      — Montserrat body with highlighted words that explode into RGB chromatic aberration. Scanlines, slice displacement, flicker, then settle into a glow color. Uses video-pixel blend modes.
                              Optional extraProps: {{"colorPreset": "cyan"|"blue"|"red"|"green"|"yellow"|"pink"}} (default "blue") — color the keyword settles into after the glitch.
                              Best for: Tech, gaming, edgy reels, cyberpunk aesthetic.
15. "NegativeFlash"        — Playfair Display serif. Keywords trigger a negative/inverted color flash with warm tint and glow, then settle into a distinctive color. Uses video-pixel blend modes for the inversion effect.
                              Optional extraProps: {{"colorPreset": "red"|"blue"|"green"|"purple"|"gold"|"cyan"}} (default "red") — color the keyword settles into after the flash.
                              Best for: Bold statements, dramatic reveals, cinematic reels.
16. "Prism"                — Playfair Display with keywords that dramatically scale up. Solo keywords on a line get 2.2x. Shares NegativeFlash's color system. Uses video-pixel blend modes.
                              Best for: Quote highlights, single-word emphasis, editorial.

NOTES ON KEYWORDS PER STYLE:
  Styles that USE caption_keywords for highlighting: Prime, Cove, EditorialPop, Illuminate, Lumen, Passage, Pulse, Serif, GlitchHighlight, NegativeFlash, Prism (11 styles).
  Styles that IGNORE caption_keywords by design: PaperII, TypewriterReveal, CinematicLetterpress, MagazineCutout, Quintessence (5 styles — animation/aesthetic IS the effect, no per-word highlighting). When you pick one of these, the caption_keywords list still has narrative value (for emphasis_moments etc.) but won't visually highlight in captions.

NOTE on render time: GlitchHighlight, NegativeFlash, and Prism use CSS blend modes against video pixels — they require a different render path that's slightly slower (single-pass Remotion instead of parallel FFmpeg+Remotion). Pick them when their visual identity is right for the content; the render-time tax is small per video.

DECISION MATRIX — caption_style by content. Each row gives 4–5 valid choices in order of typical fit; rotate among them rather than always defaulting to the first. The user's past videos are visible to you in their style profile — if your top candidate matches the style they used in their LAST video, pick a different option from the same row.

  business, hustle, agency, motivational    → Lumen / Pulse / Cove / EditorialPop
  interview, podcast, thoughtful, calm      → Serif / Cove / Passage / Illuminate / EditorialPop
  gaming, tech, cyberpunk                   → TypewriterReveal / GlitchHighlight / Pulse
  cinematic, documentary, dramatic          → CinematicLetterpress / Illuminate / Quintessence / Passage / NegativeFlash / PaperII
  aesthetic, lifestyle, travel, minimal     → Cove / Passage / Lumen / EditorialPop / Serif
  creative, artistic, collage, music        → MagazineCutout / Pulse / Quintessence / GlitchHighlight
  luxury, fashion, premium                  → Prime / Passage / EditorialPop / Quintessence / Cove
  editorial, magazine, interview quote      → EditorialPop / Quintessence / Prism / Serif / Passage / PaperII
  storytelling, narrative, POV              → PaperII / Cove / Illuminate / Passage / CinematicLetterpress
  workout, fitness, energetic               → Pulse / GlitchHighlight
  music, rhythmic, lyric-driven             → Pulse / Lumen / Quintessence / GlitchHighlight
  comedy, casual, fun                       → MagazineCutout / Pulse
  art house, poetic, contemplative          → Quintessence / CinematicLetterpress / Passage / Illuminate / EditorialPop / Prism
  bold reveals, single-word emphasis         → Prism / Quintessence / NegativeFlash / EditorialPop
  unsure                                    → pick from any vibe row above that matches the dominant register

DON'T REPEAT YOURSELF. Top short-form creators use a VARIETY of caption styles across their videos — never the same one every time. If the user's profile shows they recently used a particular style, deliberately choose a different option from the appropriate row this time. Different content deserves different visual identity.

caption_keywords — REQUIRED. The words that get visually highlighted by the caption style. THIS IS THE VISUAL IDENTITY OF THE STYLE — keyword highlighting is what makes PaperII feel like PaperII, Cove feel like Cove, Lumen feel like Lumen. With 11 keywords on a 60-second video, the highlight color barely fires and the captions look flat and generic. With 30+ keywords, the style sings.

DENSITY TARGET: aim for ~1 keyword every 3–4 spoken words across the kept transcript. That's roughly:
  • 30s video (≈75 kept words)  → 18–25 keywords
  • 60s video (≈150 kept words) → 35–50 keywords
  • 90s video (≈225 kept words) → 55–75 keywords

Pick liberally. WHAT TO INCLUDE:
  • every concrete noun that paints a picture (shaving, mirror, bedroom, secretary, voicemail)
  • every emotional verb (told, kicked, electrocuted, crying, said, screamed)
  • every vivid adjective (dark, dramatic, scared, exhausted, brutal)
  • every punchline beat, reaction word, reveal moment
  • every name, place, brand, or specific noun a viewer would search for
  • numbers, ages, dates, prices ("six", "2023", "fifty bucks")
  • any word a top creator would visually punctuate in a caption track

WHAT TO SKIP:
  • articles (a, the, an), prepositions (to, of, in, on, at), conjunctions (and, but, so)
  • generic auxiliaries (is, was, were, had, would, could)
  • pronouns unless they're the punchline ("HE didn't")

Lowercase, no punctuation. Use the dictionary form ("crying" not "Crying,").

Pick keywords from across the ENTIRE transcript. If the back half has fewer keywords than the front half, you've under-keyworded — every section of the video should feel equally punctuated.

WHEN IN DOUBT: INCLUDE THE WORD. A keyword that doesn't fire visually is invisible; a missing keyword on a beat-landing word leaves the captions feeling flat. Sparse caption_keywords (under 1 per 10 words) is the most common failure mode — it makes every caption style look the same. Bias hard toward inclusion.

caption_position_changes — REQUIRED ARRAY (can be empty). Position-change events, each at a specific kept word.
  Format: [{{"word_index": int, "position": "top" | "center" | "bottom"}}, ...]

  ANCHOR CROSS-CHECK: every word_index MUST be a kept word. remove_words is at the top of your output. If you anchor a position change to a removed word, the change is dropped — orphan effect: caption moves at the wrong moment, or doesn't move when expected.

  Semantics:
    - Captions start at "bottom" by default.
    - Each change says: "at this word, captions move to this position and stay there until the next change."
    - Python synthesizes the actual timed segments from these events — you do not emit timestamps.
    - Empty array = captions stay "bottom" for the entire video.

  MOVE captions (emit a change) when:
    - A motion_graphic occupies the bottom half across a window → emit "top" at the MG's start_word_index, and "bottom" back at the FIRST KEPT WORD AFTER end_word_index. Not later. Captions return to bottom the moment the MG is gone.
    - The speaker is looking down / mouth is in the lower third of the frame → "top" at the word where the downward look starts, "bottom" at the word where they look up again.
    - B-roll cutaway covers the bottom with busy imagery → "top" at the b-roll's start_word_index, "bottom" at the FIRST KEPT WORD AFTER end_word_index.
  Speaker changes alone don't require caption moves — face position does.

  WINDOW TIMING — match position windows EXACTLY to what's covering the captions. If your IMessageBubble runs from word 66 to word 72, the caption flip is {{66, top}} and {{73, bottom}} (or whatever the next kept word is — skip over any word in remove_words). Do NOT extend the top window past end_word+1 to give the viewer "extra reading time" — the MG's own duration handles its visual lifespan. Captions sitting at top after the MG is gone reads as broken.

  MINIMUM SUSTAINED DURATION — every position must hold for AT LEAST 1.5 SECONDS of OUTPUT time (≈4-6 spoken words at typical pacing). The renderer drops any segment shorter than that as flicker. If your MG is too brief to justify a 1.5s caption flip, don't move captions at all for it.

=== TEXT OVERLAYS — BRIEF TITLE CARDS ===

Short framing text that appears 1-3 times per video (hook, chapter, quote, speaker attribution). NOT running captions. Each has a `variant` that picks a distinct visual treatment.

text_overlays — REQUIRED ARRAY (can be empty).

ANCHOR CROSS-CHECK: start_word_index MUST be a word you KEPT. You wrote remove_words at the top of this output — scroll back, look at it. If start_word_index is in that list, the overlay is dropped (the trigger word doesn't exist in the rendered video). The classic failure: anchoring a "THE CONFESSION" hook to word 0 'So', then also putting word 0 in remove_words because it's an opening filler. Result: the entire hook never appears. Pick a kept word.

Each entry:
  {{
    "variant": "torn_paper" | "sticky_note" | "quote_card" | "caption_match",
    "start_word_index": int,       # Deepgram word whose START the overlay appears on. Schema-constrained to kept words.
    "duration_seconds": float,     # on-screen lifespan, 1.5 - 4.0s typical
    ...variant-specific REQUIRED props
  }}

The overlay appears precisely when `start_word_index`'s word begins speaking (the pipeline projects the word's start time through the output cuts) and stays visible for `duration_seconds`. No free-form timestamp to get wrong.

Each variant has a canonical visual zone. The pipeline allows overlays in DIFFERENT zones to coexist at the same time. Same-zone at same-time is rejected.

Variants and REQUIRED props. Each variant is a DESIGN with its own visual character — pick the variant that fits the content, then accept the consequence of where it renders:

1. "torn_paper"  — Top-of-frame banner: a torn-paper sheet drops from above and two text strips slam onto it. Renders at the TOP, never covers the speaker. Confession/framing/hook/chapter-card aesthetic.
   REQUIRED: "topText" (str <=5 words UPPERCASE), "bottomText" (str <=5 words UPPERCASE)
   Text content: chapter LABEL or framing HOOK. Words like "THE CONFESSION", "BEFORE / AFTER", "MY 6YO / EXPOSED MY WIFE", "THE TURN / EVERYTHING CHANGED". Punchy short labels that frame what's coming. NEVER a verbatim quote of the dialogue at that moment — the captions already show what's being said; the torn-paper card adds editorial CONTEXT, not transcript.

2. "sticky_note" — 1-3 animated sticky notes pinned at the upper third. Doesn't cover the speaker. Handwritten-style.
   REQUIRED: "notes" (array of {{"text": str, "color": "#hex", "rotation": float}} — 1 to 3 items)
   Use for: key takeaways, tip bullets, educational moments.

3. "quote_card" — Floating card at center of frame with quote + em-dash attribution. The card is large and WILL cover the center of the frame for its full lifespan. Use ONLY when you accept the cover, which means: the speaker is OFF-camera at this moment (cutaway, B-roll, scenery), OR the moment is a hard pause/silence where the quote IS the shot — the speaker yielding the frame to the quote.
   REQUIRED: "quote" (str <=20 words), "attribution" (str)
   Do NOT use over a talking-head close-up where the speaker's face fills the center — the card lands directly on their face. If you want a quote-style emphasis WITHOUT covering the speaker, use a `Quintessence` emphasis_moment caption beat or a torn_paper at the top instead.

4. "caption_match" — zone follows its `position` prop (top→`upper_third_safe`, center→`center`, bottom→`lower_third_safe`). Renders in the same style as the main captions. Mono-brand aesthetic.
   REQUIRED: "text" (str <=6 words), "position" ("top" | "center" | "bottom")
   Use ONLY for Hormozi/hustle/mono-brand vibes where matching the caption IS the brand. Otherwise pick torn_paper / sticky_note / quote_card.

DECISION MATRIX — text overlay variant by content:
  POV, confession, narrative, story hook        → "torn_paper"
  educational, tip, how-to, tutorial            → "sticky_note"
  testimonial, pull-quote, book/article quote   → "quote_card" (only if speaker is off-camera or yielding)
  motivational/hustle/Hormozi mono-brand        → "caption_match"

CARDINAL RULE — TEXT MUST NOT DUPLICATE DIALOGUE. The text inside a torn_paper / quote_card / caption_match must NEVER be a verbatim quote of the dialogue spoken at that moment. The captions already show those words. The card adds editorial framing — a chapter label, a paraphrase, a contextual gloss — never a transcript echo. If you're tempted to put "WHO THE FUCK IS STELIUS?" on a TornPaper while the speaker is saying "who the fuck is Stelius", you've created on-screen redundancy that makes the edit feel amateur. Pick a different label ("THE NAME", "THE STRANGER", "WHO?") or skip the card.

WHEN TO USE A CARD AT ALL — torn_paper, quote_card, and sticky_note are CHAPTER PUNCTUATION, not punchline markers. They mark turns in the story (act break, before/after, the reveal moment, the inciting incident). They don't underline dialogue beats — that's what zoom + caption keyword highlight + SFX are for.

PER-VIDEO CAP — at most ONE torn_paper across the ENTIRE video, counting every place TornPaper can appear (text_overlays AND emphasis_moments[*].motion_graphic of type "TornPaper"). Two torn-papers in a 60s video is wallpaper, not punctuation. Same cap for quote_card. sticky_note: one cluster (1-3 notes) per video. Total non-caption_match overlays per 60s: 0-2. Power comes from rarity.

=== EMPHASIS MOMENTS — VISUAL HITS ===

Emphasis moments are THE MOST IMPORTANT PART OF YOUR EDIT. They are the 2-5 beats in the video that HIT HARDEST — every emphasis moment composes up to three visual layers (zoom + motion graphic) that fire simultaneously to make a moment land. Think like a professional editor: which moments make the viewer FEEL something? Those are the emphasis moments. Everything else is connective tissue.

A video with no emphasis moments is a raw upload. A video with the right 3-5 emphasis moments feels professionally crafted — every other choice (caption style, transitions, B-roll) orbits around them.

emphasis_moments — ARRAY of 2-5 items. High-intensity moments must be ≥2.5s apart — each emphasis triggers a zoom punch, and when two zoom punches land within ~2.5 seconds the viewer sees rapid-fire zooming that looks BROKEN, not dramatic. Check every emphasis moment against the previous one before committing.

ANCHOR CROSS-CHECK: every word_index in word_indices MUST be a word you KEPT. You wrote remove_words at the top of this output — scroll back, look at it. If any of these indices appears there, the emphasis moment is dropped. Pick different surviving words from the surrounding kept transcript.

Each entry:
  {{
    "word_indices": [int, ...],          # 1-3 Deepgram word indices that ARE the emphasis. Every index must target a word you are KEEPING — a word you also emit in remove_words cannot be emphasized. The pipeline derives the emphasis timestamp from word_indices[0].start; you do not emit a separate `t` field.
    "type": "punchline" | "revelation" | "statement" | "reaction" | "question",
    "intensity": "high" | "medium",
    "duration": float,                   # output-seconds the visual hit lasts, 1.5 - 3.0

    # ── Visual layers — each field REQUIRED (value or null) ──
    # zoom_effect.events: each event has {{"startMs": int, "durationMs": int, "scale": float, "originX": float, "originY": float}}
    # IMPORTANT: startMs is the ABSOLUTE source-time in milliseconds where the zoom event begins
    # (relative to the start of the source video — same coordinate system as the word timestamps
    # you see in the transcript). durationMs is the event's duration in source ms. The zoom is
    # anchored to source content — when the underlying clip plays in slow-motion, the rendered
    # zoom takes proportionally longer wall-clock time; when it speeds up, the zoom finishes
    # faster. This keeps the zoom climax synced with the spoken content regardless of speed
    # ramping. Typical durationMs: 500-1500ms. Place startMs slightly after the emphasis word's
    # start (e.g., emphasis word at 12.32s, startMs around 13500 for a 1.2s lead-in).
    "zoom_effect": {{"type": zoom_type, "events": [...]}} | null,
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

B. motion_graphic — should a text/graphic overlay land on this moment?
   Pick from the motion graphic vocabulary below. Reserve for the 1-2 PAYOFF moments. Too many = clutter.
   motion_graphic windows must NOT overlap with any text_overlay in the same visual zone.

=== MOTION GRAPHICS — HOW TO USE THEM ===

THE PURPOSE OF A MOTION GRAPHIC. An MG is a visual element that ADDS something the dialogue alone cannot — a screenshot the speaker is referencing, a stat the speaker is citing, a notification the speaker is reacting to, a chapter beat the editor is marking. It REINFORCES content, never substitutes for it. If the dialogue carries the moment on its own, no MG is needed.

WHEN TO USE ONE. Three legitimate triggers and only three:
  1. The speaker references something visual that isn't on camera ("she texted me", "I got an email", "the screen said") — render the artifact (Notification, IMessageBubble, ChatThread, TweetBubble).
  2. The speaker cites a number, stat, or quotable line that lands harder rendered ("we hit 100k followers", "she said 'don't believe everything…'") — render the metric or quote (StatCard, QuoteCard).
  3. The editor needs to mark a chapter beat or call out a detail in the frame (TornPaper for "THE CONFESSION"; AnnotationArrow for "look at THIS").

If none of those triggers are present, do NOT emit an MG just because the dialogue feels like it could use "something." A clean talking-head moment with strong captions and a zoom is more polished than a forced MG.

WHEN NOT TO USE ONE. Negative triggers — emit zero MGs in these situations:
  • The dialogue is a punchline or reaction beat — that's what zoom + caption keyword highlight + SFX are for. An MG layered on top dilutes the moment.
  • You'd be rendering text that paraphrases the dialogue verbatim — the captions already show those words. (See: TornPaper / QuoteCard text-content rule.)
  • There's already a text_overlay or another MG firing in the same 3-second window — stacking visual elements creates clutter, not punctuation.
  • The window is shorter than 2 seconds — anything briefer reads as a flicker.

DENSITY. 0-3 MGs per 60-second video is the healthy range. Zero is fine. Five is wallpaper. Each MG you emit must justify its screen time against the alternative of zero MGs at that moment.

ANCHORING — THIS IS WHERE BAD CHOICES GET DROPPED.
  remove_words is field 2 in your output schema; you committed to it BEFORE writing any motion_graphic. Now scroll back and look at it. Every word_index you reference here — start_word_index, end_word_index, AND any word in the [start, end] range — must NOT be in that array. If any of them is, the renderer will DROP this MG entirely. The caption_position_change you wrote to make room for it will orphan, and captions will move for no visible reason — a clear "this video was edited badly" signal.

  Pick anchor words from kept words only. Example: if you cut "calling" at word 197 and want an MG illustrating the wife's call, anchor the MG to a SURVIVING word in the same passage — the next "calling" at word 200, or "every 5 seconds" at word 202.

PLACEMENT — anchor zone must not cover the speaker's face. You watch the video at 5fps; you can see exactly where the speaker sits in the frame across the MG's window. Pick the zone that keeps the face visible:
  • Face in lower half of frame  → anchor "upper_third_safe"
  • Face in upper half           → anchor "lower_third_safe"
  • Face dead-center close-up    → anchor "left_safe" or "right_safe" (small MGs only) OR don't emit an MG here
  • Face off-screen / B-roll     → "center" is fair game

DURATION. Most MGs render naturally across the word range you anchor — let the word-span dictate timing. For fixed-length pins (a 3-second StatCard count-up on one punchline word), set start_word_index == end_word_index and use `duration_seconds` to override. Typical lifespan 2.0-4.0s. Under 2s reads as a flicker; over 4s overstays.

NON-OVERLAP. Two MGs cannot share a time window AND a zone. Two MGs in different zones at the same time are allowed but rarely a good idea — you're asking the viewer to track two visual additions while listening to dialogue. Prefer separating MGs by ≥3 seconds.

CAPTION COORDINATION. When an MG sits at `lower_third_safe` or any bottom-overlapping anchor, captions will visually overlap the MG. You MUST emit a `caption_position_change` to "top" at the MG's start_word_index and another to "bottom" at the word AFTER the MG ends. The renderer does NOT auto-flip; if you skip this, captions stack on top of the MG.
  IMPORTANT: if you decide AFTER emitting the MG that the anchor word should be cut, you must REMOVE both the MG and any caption_position_change tied to it. Don't leave orphaned position changes — they make captions move for no reason.

NEVER DUPLICATE DIALOGUE. The text inside QuoteCard / TornPaper / IMessageBubble / ChatThread / TweetBubble must NEVER be a verbatim transcript of the dialogue at that moment. The captions already show those words. The MG renders editorial framing — a paraphrase, a chapter label, a fabricated message that ADVANCES the story (the wife's text the speaker is referencing, not what the speaker is saying out loud).

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

 1. "AnnotationArrow"    — Hand-drawn SVG arrow animated along bezier path. Straight, curved-arc, j-shape, or custom SVG.
                            Best for: Callouts, UI annotations, "look here" moments.
                            Props: {{"start": {{"x": 0-1, "y": 0-1}}, "end": {{"x": 0-1, "y": 0-1}}, "pathType"?: "straight"|"curved-arc"|"j-shape"|"custom", "color"?: "#hex"}}

 2. "ChatThread"         — iMessage-style conversation with typing indicators, sequential delivery, status bar.
                            Best for: Text recreations, testimonials, DM screenshots.
                            Props: {{"messages": [{{"sender": "me"|"them", "text": str, "typingMs"?: int, "holdMs"?: int}}, ...], "header"?: {{"name": str, "subtitle"?: str}}}}

 3. "Notification"       — iOS/Android notification stack. 1–3 banners drop in with platform styling. 7 built-in app icons.
                            Best for: Income proof, social proof, notification montages.
                            Props: {{"notifications": [{{"app": "apple-pay"|"venmo"|"stripe"|"imessage"|"instagram"|"email"|"bank", "appName": str, "title": str, "body": str, "timestamp"?: str}}, ...], "platform"?: "ios"|"android"}}

 4. "ProgressBar"        — Animated progress bar with count-up. Optional milestones.
                            Best for: Goal tracking, fundraising, skill bars.
                            Props: EITHER {{"value": number, "total": number, "label"?: str, "fillColor"?: "#hex", "accentColor"?: "#hex"}}  OR  {{"percentage": 0-100, "label"?: str, "fillColor"?: "#hex", "accentColor"?: "#hex"}}

 5. "QuoteCard"          — Floating card with decorative quotation mark, serif text, em-dash attribution. Spring entrance.
                            Best for: Testimonials, pull quotes, book excerpts.
                            Props: {{"quote": str, "attribution": str, "theme"?: "dark"|"light", "accentColor"?: "#hex"}}

 6. "RecordingFrame"     — Full-screen recording overlay with inset border, scan line, corner annotations (timestamp, WPM).
                            Best for: Behind-the-scenes, raw/unfiltered, documentary.
                            Props: {{"accentColor"?: "#hex", "showScanLine"?: bool}}

    — SpeechBubble variants (4) — Platform-specific social bubbles. Best for: Social proof, testimonials, comment highlights.

 7. "TweetBubble"        — Twitter/X post with verified badge and engagement stats.
                            Props: {{"name": str, "handle": str, "text": str, "verified"?: bool, "stats"?: {{"replies": int, "reposts": int, "likes": int, "views": int}}, "darkMode"?: bool}}
 8. "InstagramComment"   — Instagram comment with avatar and like count.
                            Props: {{"username": str, "comment": str, "timestamp"?: str, "likes"?: int}}
 9. "IMessageBubble"     — iMessage bubble with typewriter mode.
                            Props: {{"text": str, "messageType": "incoming"|"outgoing", "status"?: "Delivered"|"Read", "typewriter"?: bool}}
10. "TikTokComment"      — TikTok comment with likes.
                            Props: {{"username": str, "comment": str, "likes"?: int}}

11. "StatCard"           — Animated count-up number with label and accent divider. Prefix/suffix formatting.
                            Best for: Revenue stats, subscriber counts, KPIs.
                            Props: {{"value": number, "label": str, "prefix"?: str, "suffix"?: str, "fromValue"?: number, "decimals"?: int, "accentColor"?: "#hex"}}

12. "StickyNotes"        — 1–3 sticky notes slam on with spring physics. Color, rotation, handwritten text (Caveat Brush).
                            Best for: Key takeaways, tip lists, educational content.
                            Props: {{"notes": [{{"text": str, "color": "#hex", "rotation": float}}, ...]}} (1-3 notes)

13. "Toggle"             — iOS-style toggle that flips on at configurable time. Label text.
                            Best for: Feature toggles, on/off reveals, settings demos.
                            Props: {{"text": str, "activateAtMs"?: int, "onColor"?: "#hex"}}

14. "TornPaper"          — Top-of-frame chapter card: torn-paper banner drops from above with two text strips. Renders at the TOP regardless of `anchor`.
                            Best for: chapter-break punctuation — the act break, the inciting incident, the before/after pivot, the moment-of-truth label. NOT a punchline marker, NOT a dialogue restatement.
                            Text content: a chapter label or framing hook ("THE CONFESSION", "THE TURN", "WHAT SHE SAID NEXT"). NEVER a verbatim quote of the dialogue at that moment — captions already show that.
                            CAP: across the ENTIRE video, TornPaper may appear AT MOST ONCE — counting both `text_overlays[i].variant=="torn_paper"` AND any `motion_graphics[i].type=="TornPaper"` AND any `emphasis_moments[i].motion_graphic.type=="TornPaper"`. If you've already used one, do not emit another. The card's power is its rarity; using it twice burns the visual currency.
                            Props: {{"topText": str (<=5 words), "bottomText": str (<=5 words)}}

(All MG usage rules — when, where, how, anti-patterns — are covered in the "MOTION GRAPHICS — HOW TO USE THEM" section above this catalog. Re-read it if you're picking an MG; the catalog only documents what each type IS, not when to reach for it.)

=== WORD EDITING — YOU OWN EVERY CUT ===

remove_words — REQUIRED ARRAY. THIS IS THE ONLY CUT AUTHORITY. The transcript you see is the FULL Deepgram output, every word indexed [0..N-1]. Python applies your cuts verbatim. There is no second pass.

DEFAULT IS KEEP. Only cut when removal makes the dialogue OBJECTIVELY tighter without losing meaning, sequence, or causation. There is NO target cut count. Clean talkers may yield 3 cuts on a 60-second clip; filler-heavy interviews may yield 30+. The right number is whatever makes the dialogue unambiguously better — never a quota.

A correct cut passes this test: a listener hearing only the output cannot tell anything was removed. If a cut creates a noticeable rhythm break, awkward pause, or grammatical bump, it was wrong. WHEN IN DOUBT, KEEP.

WHAT TO CUT — apply each rule ONLY when its specific signature is present:

1. HESITATION TOKENS — single-word cut, always:
   "um", "uh", "hmm", "er", "ah", "uhh", "uhm", "umm", "erm".

2. TRAILING-DASH FALSE STARTS — Deepgram tags incomplete words with a hyphen:
   "wh-", "shou-", "th-". Always cut.

3. STUTTERS — same word repeated 2+ times in rapid succession (gap < 80 ms or first instance < 200 ms long).

   THE RULE — find the instance that FLOWS INTO THE REAL SENTENCE. That's the keeper. Cut every other instance.

   Two instances "I I told mommy" at words [61, 62, 63, 64]:
     The keeper is [62] — the "I" followed by "told mommy" (the real sentence).
     CUT [61]. KEEP [62].
     Output: "I told mommy."

   Three instances "I'm I'm I'm gonna leave" at words [161, 162, 163, 164, 165]:
     The keeper is [163] — only this "I'm" is followed by "gonna leave" (the real sentence). The first two are stutter throat-clearing before the speaker landed.
     CUT [161, 162]. KEEP [163].
     Output: "I'm gonna leave for the rest of my life."

     COMMON FAILURE: cutting [162, 163] instead. That leaves [161] alone, followed by 0.5s of silence (where the cut words used to be), then "gonna leave". The first "I'm" is now disconnected from "gonna leave" — sounds like the speaker trailed off. WRONG. Always cut the EARLIER instances, keep the LATEST.

   Phoneme false-start "should shouldn't": the second "shouldn't" is the real word; the first "should" was abandoned mid-pronunciation. Cut "should".

   Rhetorical emphasis with audible space ("very, very good", "now, now hold on", normal pacing): both instances are intentional. KEEP both.

4. PHRASAL RESTARTS — speaker abandons a phrase and re-attempts it. PATTERN:
   <abandoned phrase> [tiny gap, breath, or filler bridge] <SAME phrase EXTENDED with NEW continuation>

   THE TWO PHRASES ARE NEAR-IDENTICAL IN WORDS. THE FIRST ENDS NOWHERE. THE SECOND CONTINUES INTO A COMPLETED THOUGHT.

   How to identify in the transcript:
     a. Find adjacent regions where the same word sequence appears twice.
     b. Look at what comes AFTER each instance:
        • First instance is followed by a near-repeat of the same words → that first instance is the ABANDONED attempt.
        • Second instance is followed by NEW words that complete the thought → that second instance is the COMPLETED one.
     c. CUT the abandoned (FIRST) instance. KEEP the completed (SECOND) instance with its continuation.
     d. Anything BETWEEN them ("like", "uh", a breath) is orphan filler → CUT.

   WORKED EXAMPLE A — DO THIS EXACTLY:
     Transcript: "...where did you hear that name? I said, who is — I said, who is he?"
       [139] I       \\
       [140] said,    | ← FIRST instance ("I said, who is"). ABANDONED.
       [141] who      |   CUT ALL FOUR.
       [142] is      /
       [143] I       \\
       [144] said,    | ← SECOND instance, continues into "he?". COMPLETED.
       [145] who      |   KEEP THESE FIVE.
       [146] is       |
       [147] he?     /
     Correct: remove_words includes word_indices [139, 140, 141, 142].

     FAILURE MODE — partial cut. If you cut only [141, 142] (just the verbatim-duplicated "who is"), you LEAVE [139, 140] "I said," still in the dialogue. The output becomes "I said, [pause] I said, who is he?" — the duplicate "I said" is still on screen, the cut accomplished nothing. The boundary of the abandoned phrase runs from its FIRST word ([139] "I") through its LAST word before the second attempt ([142] "is"). Cut all four. Don't stop at the duplicated portion.

     FAILURE MODE — wrong direction. Cutting [143, 144, 145, 146] (the second instance) leaves "I said, who is — he?" — the abandoned phrase plus a fragment. The rule is always CUT THE FIRST.

   WORKED EXAMPLE B — DO THIS EXACTLY:
     Transcript: "...calling me, like, calling me every 5 seconds..."
       [197] calling \\
       [198] me,      | ← FIRST instance. ABANDONED.
       [199] like,    | ← orphan filler bridge.
       [200] calling \\
       [201] me       | ← SECOND instance, continues into "every 5 seconds".
       [202] every  ...
     Correct: remove_words includes [197, 198, 199].
     Result heard by viewer: "calling me every 5 seconds" — clean.

     FAILURE MODE — half cut. Cutting only [199] "like" leaves "calling me, calling me every 5 seconds" — the duplicate is still there. Always cut the entire abandoned phrase plus its bridge filler.

   PARALLEL STRUCTURE IS NOT A RESTART. If both phrases end with sentence-ending punctuation (?!.) BEFORE the next begins, neither was abandoned — that's intentional rhetorical parallelism:
     "What are you gonna do? What are you gonna learn?"
     "I went, I saw, I conquered."
     "I told you. I told you again."
   KEEP both. Cutting parallel structure destroys the rhetorical device.

5. CONTEXTUAL FILLER — DEFAULT IS KEEP. Cut ONLY when the word is provably meaningless. Both signatures must hold:
   (a) The word is pause-bracketed in delivery — there's audible space (>200 ms gap) on BOTH sides, or it's set off by commas in the transcript.
   (b) Removing it leaves NO semantic, causal, or sequential gap — the surrounding sentence still says exactly the same thing.

   ✓ "I'm, like, totally exhausted" — "like" is pause-bracketed AND removing it doesn't change meaning. CUT "like".
   ✗ "they're like family to me" — "like" is a simile here, removing it changes meaning. KEEP.
   ✓ "So, anyway, I went..." — "anyway" is filler. CUT.

   MULTI-WORD FILLERS ARE PHRASAL UNITS — cut every word of the phrase together, never just one:
     "you know"  → cut both words. "What are you gonna learn? You know? What are you gonna play?" → cut [45, 46] together (BOTH "You" and "know?"). Cutting only [46] leaves "You" hanging at the end of the prior thought — sounds like the speaker trailed off mid-sentence.
     "I mean"    → cut both words.
     "kind of"   → cut both words.
     "sort of"   → cut both words.
   These are phrases, not individual fillers. Cut as a unit or don't cut at all.

   CONJUNCTIONS BETWEEN CLAUSES ARE NOT FILLER. They carry sequence, causation, or contrast and almost always KEEP:
     "and"     → sequence ("She was sleeping, AND I kicked the bed.")
     "so"      → causation ("I felt electrocuted, SO I wiped the cream off.")
     "but"     → contrast ("She said no, BUT I kept asking.")
     "because" → reason
     "then"    → temporal sequence

   When two clauses describe a single beat, causal chain, or sequence of events, the conjunction stays. Removing it runs the clauses together and breaks the rhythm.

   CONJUNCTION LITMUS TEST: read the two clauses with the conjunction removed. If the result reads as two separate sentences that were just shoved together, KEEP the conjunction.
     "I felt electrocuted. I wiped the cream off."   ← runs together. KEEP "so".
     "She was sleeping. I kicked the bed."           ← runs together. KEEP "and".
     "Got in the car. I went to work."               ← runs together. KEEP "and".

   SENTENCE-OPENING "AND" / "SO" / "BUT" — context-dependent:
     • If the speaker is mid-story and "And then..." continues a single arc → KEEP. Narrative cohesion matters.
     • If the prior thought was fully completed (long pause + topic shift) and the opener is just throat-clearing → CUT.
     • Pure bridge openers like "So, [pause] yeah..." that lead nowhere → CUT.
     • The very FIRST word of the video, if it's "So", "And", "Like" with no prior context → CUT.

   "JUST" / "REALLY" / "ACTUALLY" — context-dependent:
     ✓ Pause-bracketed OR clearly used as throat-clearing → CUT.
     ✗ Carries emphasis or distinguishes degree ("I just barely made it" / "she really hates it") → KEEP.

6. REDUNDANT RESTATEMENT — same idea expressed twice in close succession with no new information:
     "she was angry — she was so mad" → cut the weaker phrasing.
   Do NOT confuse with rhetorical emphasis where the repetition IS the point ("I told her once. I told her twice. I told her three times.").

7. DEAD AIR / SILENCE — TIME-RANGE cuts only.

   STRICT BOUNDARY RULE — the range MUST land on real word boundaries from the transcript, exactly:
     • "start" MUST equal some word[i].end timestamp shown in the transcript above.
     • "end" MUST equal some word[i+1].start timestamp shown in the transcript above.
     • Compute gap = word[i+1].start − word[i].end. Emit a range cut ONLY when gap > 0.30s.
     • The range you emit is exactly [word[i].end, word[i+1].start] — nothing else.

   THE WORST ERROR YOU CAN MAKE: emitting a range whose [start, end] interval contains any word's [start, end] timestamps. The renderer treats range cuts as "remove every word fully inside this interval" — if you accidentally span a spoken word, that word is silently deleted from the dialogue.

   VERIFY EACH RANGE before emitting:
     1. Find word[i] (the word immediately before your range) and word[i+1] (the word immediately after).
     2. Confirm range.start == word[i].end EXACTLY.
     3. Confirm range.end == word[i+1].start EXACTLY.
     4. Confirm no other word's [start, end] falls inside [range.start, range.end].

   Sub-300 ms breath-gaps inside continuous speech are NATURAL CADENCE, not silence. KEEP them — the output won't feel choppy. Only the long pauses (≥0.3s, often ≥0.5s) read as dead air to the viewer.

ENTRY FORMAT
  • Single word:   {{"word_index": int, "reason": "filler"|"stutter"|"restart"|"redundant"|"orphan_filler"|"breath"|"other"}}
  • Time range:    {{"start": float, "end": float, "reason": "dead_air"|"breath"|"tangent"|"section_skip"|"other"}}

ANCHOR INTEGRITY — any word_index you list in remove_words CANNOT be anchored elsewhere. The renderer fails validation if you anchor an emphasis_moment, motion_graphic, sound_effect, transition, broll_clip, text_overlay, or caption_position_change to a word you also removed.

Range cuts and word cuts coexist — a range cut removes every word fully contained in [start, end]; partial overlaps keep the word.

A low-value section that's too long to cut entirely but isn't punchline material → set that clip's `speed` to 1.30–1.40 to pace through it instead of cutting mid-clause.

=== OPENING (cut[0]) ===

The first 2 seconds of any short-form video are an audition — the viewer decides whether to keep watching or scroll. There is no auto-hook, no preview-then-replay structure (that pattern duplicates content and reads as amateurish; no professional editor or production tool does it).

Instead: **cut[0] must be the strongest attention-grabbing moment in the video** — the punchline, the reveal, the most extreme reaction, the emotional peak. Don't bury the lede behind setup. The viewer should be hooked by what they see and hear in cut[0] alone.

Concretely:
  - cut[0]'s source range should contain a high-energy moment, not setup
  - cut[0]'s `speed` should be 0.75–0.85x (the buildup-arrival pattern's "arrival" speed) so the moment lands with weight
  - cut[0] should start with speech (not silence) — pick a source range whose first word lands within ~0.3s of source_start
  - cut[0] should NOT need the rest of the video to make sense — that ambiguity is what keeps the viewer watching

If the speaker's strongest moment is at source second 35, your cuts list does NOT have to start at 0. Start cut[0] at ~34.5 with the punchline; let cut[1] onward fill in the chronological narrative leading up to it (or skip back to the beginning, depending on the story shape). This is a "cold open" — the climax leads, the lead-up follows.

If the source genuinely opens with a strong moment (e.g., the speaker walks in mid-rant), then cut[0] = source from 0 is fine. But this is rare; for most talking-head footage the strongest moment lives somewhere in the middle.

=== SFX — SOUND EFFECTS ===

Sound effects amplify the speaker's energy at key moments. Emit as many as the content earns — there's no hard cap. Silence is BETTER than a wrong sound. Each entry: {{"word_index": int, "sound": <name>}} — you pick the kept word that triggers the SFX; the pipeline derives the exact timing from word.start.

ANCHOR CROSS-CHECK: word_index MUST be a word you KEPT. You wrote remove_words at the top of this output — scroll back, look at it. If your word_index is in that list, the SFX is dropped (the trigger word doesn't exist in the rendered video). Pick a different surviving word.

THE CORE RULE FOR EVERY SOUND: The word you anchor each sound to must BE the thing that makes that sound in reality. Not near it, not in the same sentence, not in the same phrase — the EXACT word that NAMES the action, object, or peak moment the sound represents. Before placing any sound, ask: "does this specific word literally refer to what this sound is?" If the word is a time word, a filler word, a pronoun, a conjunction, or a generic context word — even if the surrounding phrase fits — the sound belongs elsewhere or nowhere. One 1:1 match between word and sound, not a proximity match.

Tonal context still beats vocabulary matching. If the surrounding content doesn't fit the sound's character, skip it even when a trigger word literally matches — `sad_trombone` on a serious moment is wrong even if someone says "failed."

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

BUILD-UP SOUNDS — long builds (1.3–1.7s) climaxing at the end. The renderer schedules the file early so the climax lands on the trigger word; the build plays DURING the preceding output audio (it mixes globally on the output timeline, not the source clip, so it freely spans cut boundaries).

 9. "drum_roll"      — Classic military/circus snare drum roll building for ~1.65s into a payoff crash at the end. Iconic tension-before-reveal sound. Traditional/comedic anticipation — works standalone in talking-head content.
                        Best for: big announcements, anticipation before a reveal, "and the answer is...", award moments, payoff setups.
                        Triggers on: *winner, revealed, the answer, finally, ta-da, drumroll, introducing*.
10. "reverse"        — Reverse riser. Builds continuously in volume and pitch for ~1.37s, climaxing at the very end. Engineered as a cinematic "suck-toward-the-moment" effect — the entire sound IS anticipation.
                        Best for: priming a MAJOR visual event. ALWAYS pair with something visually impactful landing on the trigger word — a hard cut to a new scene, a zoom effect landing (SnapReframe / StepZoom / LetterboxPush), a TornPaper or motion-graphic slam, or a transition peak. The 1.37s rise plays across the preceding output audio and releases into the visual beat.
                        Skip when there's no paired visual payoff — generic "wait for it" dialogue, punctuating sentences with no visual event attached, building up to a normal talking-head cut with nothing extra happening, or back-to-back triggers. Without a visual climax landing on the trigger word, this sound feels anticlimactic.
11. "sad_trombone"   — The iconic "wah wah waaah" four-note descending trombone. 1.3s descending phrase climaxing on the final low note. Unambiguously comedic — every listener recognizes this as the "you failed" joke sound. There is no way to use this sincerely; it IS the joke.
                        Best for: ONLY when the content is EXPLICITLY comedic and the "failure" is being played for laughs. Trivial mishaps, obvious mock-failures, game-show-style setups, bloopers, intentional self-own jokes.
                        Required tonal gate — verify BOTH before emitting:
                          (a) User's vibe is comedic, playful, ironic, or self-deprecating (e.g. "funny", "comedy", "blooper", "joke", "fail compilation", "roast"). If the vibe is motivational, educational, interview, storytelling, lifestyle, business, or any serious register — DO NOT USE.
                          (b) Dialogue at the trigger moment is clearly comedic — the speaker is making light of the moment intentionally, not processing something real.
                        Skip for: real failures, breakups, deaths, job losses, business collapses, mental-health struggles, motivational / overcoming-adversity content, interviews / podcasts / storytelling where a guest shares a vulnerable moment, and any reflective / emotional / vulnerable content. Trigger words alone never justify this sound — "failed" in a serious context calls for silence. Context trumps vocabulary. When in doubt, skip.

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

Pexels stock-footage cutaways that play OVER the speaker's dialogue. The viewer hears the speaker's words while watching your B-roll clip. Good B-roll makes the viewer FEEL the words — the clip reinforces and amplifies what the speaker is saying.

broll_clips — ARRAY. {{"keyword": str (13-18 words), "start_word_index": int, "end_word_index": int, "reason": str}}

ANCHOR CROSS-CHECK: start_word_index, end_word_index, and every word in [start, end] MUST be kept words. remove_words is field 2 above this one in the JSON — scroll back and verify none of the words in your B-roll range appear there. If any do, the B-roll spec drops or its window mis-aligns. Pick a range entirely inside the kept transcript.

KEYWORD CONSTRUCTION:
  The VERB in the dialogue is the starting point. Build the keyword from the verb in the speaker's dialogue, then add the subject and setting around it. The clip doesn't need to show the EXACT scene — it just needs to visually CONNECT to what the speaker is describing. A phone ringing on a desk works for "she kept calling me." A man with a towel works for "I wiped my face." Good B-roll EVOKES the dialogue, it does not recreate it literally.

  The keyword (Pexels search) should be simple and general — one subject doing one thing. Do not build complex scenes with multiple actions or props. Never search for abstract concepts or emotions. Use context words only to disambiguate (e.g. "morning routine cinematic lighting" to filter out cartoons).

  Keep keyword 13-18 words. No two keywords should return the same clip — each clip visually distinct (different settings, different subjects, different shot types).

WORD WINDOW (start_word_index → end_word_index):
  The window defines exactly when the B-roll appears on screen. The viewer hears those words while seeing the B-roll, so the dialogue at those word indices MUST literally describe what's in the cutaway.

  ANCHOR TO THE ACTION WORDS — the verbs and concrete nouns that name what's visible in the clip. Do NOT anchor to adjacent context that mentions the same SUBJECT but a different action.

  Example A — RIGHT vs WRONG anchoring:
    Dialogue: "...my oldest son is 6 years old at the time. He's sitting on the floor next to me watching me shave..."
    B-roll keyword: "young boy sitting on floor playing with toys"
    ✗ WRONG anchor: words covering "oldest son is 6 years old" — those words name the SUBJECT (the son) but describe his AGE, not what the visual shows him DOING.
    ✓ RIGHT anchor: words covering "He's sitting on the floor next to me" — these are the words that LITERALLY describe the visual (a boy sitting on the floor).
    The rule: pick the words that, if a viewer read them out loud while seeing the cutaway, the words and visual would feel synonymous.

  Example B — RIGHT vs WRONG anchoring:
    Dialogue: "...so I wiped the shaving cream off my face. I went into the bedroom..."
    B-roll keyword: "person wiping shaving cream off face"
    ✓ RIGHT anchor: words covering "wiped the shaving cream off my face" — verb "wiped" + concrete noun "shaving cream" + body part "face" — every word pulls its weight visually.
    ✗ WRONG anchor: words covering "I went into the bedroom" — wrong room, wrong action.

  WINDOW SPAN:
    - start_word_index = the first word of the action phrase being visualized.
    - end_word_index = the last word of the action phrase. Don't bleed past the action into unrelated words; don't cut off mid-action.
    - 4-10 word span is typical. Long enough to register; short enough to stay synced.
    - The pipeline derives precise on-screen timing from these indices. No duration field.

PLACEMENT DISCIPLINE:
  Only place B-roll on moments where the speaker describes a physical action or concrete scene. Stay on the speaker's face during emotional beats, opinions, punchlines, reveals, and reactions — during those moments the speaker's facial expression IS the content and cutting away destroys the impact. B-roll in the main body, NEVER during cut[0] (the opening needs the speaker's face for the first 2 seconds — viewers form snap judgments from human faces).

  Spacing: 3+ seconds of speaker face between B-roll clips. Coverage: ~30-40% of runtime is a healthy ceiling. Place B-roll on 1.0x or 1.2–1.3x clips, not on the 0.7–0.85x slow-speed clips that contain a punchline beat.

=== TRANSITIONS ===

90%+ of cuts are hard cuts. Transitions EARN their place — ideally ON a shot change.

transitions — ARRAY. {{"after_word_index": int, "type": <name>, ...component props}}

ANCHOR CROSS-CHECK: after_word_index MUST be a kept word. remove_words is field 2 above; verify your after_word_index is not in there. If it is, the transition drops and the cut between clips falls back to a hard cut.

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

=== PER-CLIP PACING (cut.speed) ===

Each clip you emit has a `speed` field — a single constant playback rate that holds for the entire clip. Range: 0.7 to 1.4. This is your one and only pacing tool. There is no continuous speed curve, no ramp, no glide — every clip plays at one constant speed and the rhythm comes from the contrast between adjacent clips.

THE EDITORIAL LOGIC — read this carefully:

Pacing is storytelling. Speed UP a clip (1.2–1.4) when the content is moving TOWARD something — setup, context, transitions between beats, filler that earns its keep by getting out of the way fast. Slow DOWN a clip (0.7–0.85) when the content ARRIVES — the reveal, the punchline, the reaction, the emotional weight. Stay at 1.0 for narrative cruise — when neither building nor arriving.

The CONTRAST between adjacent clips is what makes a moment land. A 1.25x clip cutting straight into a 0.75x clip on the punchline word is the entire effect. The viewer feels the deceleration as a hard transition, not a glide — that's the modern viral aesthetic, sharper than any smooth ramp.

THE BUILDUP-ARRIVAL PATTERN (most important):

A great emphasis isn't a single slow clip. It's a 2- or 3-cut sequence built from your `cuts` list:

  Clip A — buildup at 1.20–1.30x
           Ends just BEFORE the punchline word's start timestamp.
           Carries the setup/context.

  Clip B — arrival at 0.70–0.85x
           Starts at the punchline word and runs 0.8–1.5 seconds.
           Contains exactly the moment that matters.

  Clip C — resume at 1.00x (or back to 1.20x if continuing momentum)
           Picks up after the moment lands.

Place Clips A→B→C as three adjacent entries in your `cuts` list. Use a hard cut or a SnapReframe / SmoothPush transition between A and B to drive the speed change visually.

For every emphasis_moment you place, isolate the punchline word as its own clip at 0.7–0.85x. Don't bury an emphasis word inside a normal-speed clip — that flattens it. The emphasis_moment's `word_indices[0]` should land at or near the start of a slow-speed clip.

DON'T:
  - Use 1.0x for a clip containing an emphasis word — make it slow (0.7–0.85x).
  - Use the same speed for every clip — pacing is created by contrast.
  - Go below 0.7 (audio artifacts) or above 1.4 (looks like fast-forward, not pacing).
  - Set every clip to fast or every clip to slow — without contrast, the effect dies.

DO:
  - Use 1.0x for the majority of clips (narrative cruise).
  - Use 1.2–1.3x for setup/buildup clips that lead into a slow moment.
  - Use 0.75x for the 1–2 clips per video that contain the hardest-hitting moment.
  - Build 1–3 buildup-arrival sequences per 60 seconds of output.

A typical 60-second video has: most clips at 1.0x, two or three clips at 1.20–1.30x (setup), and one or two clips at 0.75–0.85x (the moment lands). That's it.

VIBE TUNING:
  - If the vibe mentions "speed ramp", "speed ramping", "CapCut style", or "fast-paced edit", lean into MORE buildup-arrival sequences — every emphasis moment gets its own A→B→C trio, and the resume clip itself often runs at 1.20–1.30x to keep momentum. Aim for 3–5 buildup-arrival sequences per 60s instead of 1–3.
  - If the vibe is contemplative, cinematic, interview, or documentary, dial pacing down: most clips at 1.0x, the occasional 0.85x for emphasis, and 1.10–1.20x only for clearly low-value setup. No 1.4x sprinting.
  - If the vibe is purely informational/educational with no emotional peaks, you can leave every clip at 1.0x — pacing through speed contrast is optional, not mandatory.

=== GLOBAL FIELDS ===

notes              — string <=50 words. Brief rationale.
audio_denoise      — bool. true when noise_floor > -40 dB.
outro              — "none" | "fade_black" | "fade_white". "none" best for looping.
aspect_ratio       — always "9:16".
pacing             — "fast" | "medium" | "slow". Default "fast" for short-form under 60s — TikTok/Reels live at 2-3s per cut. Use "medium" for interview/podcast/educational. Reserve "slow" for genuinely contemplative content.

=== THUMBNAIL ===

thumbnail_word_index — int. The single most important visual decision in the entire edit. The thumbnail is what makes someone scrolling stop and click. A bad thumbnail tanks the video no matter how good the edit is.

ANCHOR CROSS-CHECK: this index MUST be a kept word. remove_words is at the top of your output — verify the index is not in there. If it is, thumbnail extraction lands on a frame that doesn't exist in the rendered video.

CRITICAL — DO NOT PICK THE PUNCHLINE WORD ITSELF.
A common mistake is to pick the word whose timestamp lands ON the most dramatic moment. This is almost always WRONG because:
  - Mid-syllable mouths are in awkward shapes (open mid-vowel, contorted mid-consonant)
  - Speaking causes head movement and motion blur
  - Eyes squint from vocal effort
  - The narratively-peak word is usually the visually-WORST moment

INSTEAD, scan for the VISUAL peak. It almost always falls in one of these three zones:

  1. PRE-REVEAL ANTICIPATION (a kept word 0.3-1.5s BEFORE the dramatic word):
     The speaker is leaning into the camera, eyes WIDE, mouth set/closed, building tension. Just before they say the shocking thing — their face shows the EMOTION without the speaking distortion. Best for reveals, punchlines, and shocking statements.

  2. POST-REVEAL REACTION (a kept word 0.3-1.5s AFTER the dramatic word):
     The speaker is REACTING to what they just said. Often the most extreme expression of the entire video — eyes huge, jaw set, head tilted in disbelief, scowl, smirk, raised eyebrows. The aftermath of the statement, not the statement itself.

  3. MID-EMOTION SILENT PAUSE:
     A kept word between sentences when the speaker shows pure emotion (anger, disgust, shock, joy, contempt) with mouth closed or in a non-speaking expressive shape. These are gold.

A GREAT thumbnail frame has ALL of these:
  ✓ Face is BIG in the frame (close-up framing)
  ✓ Eyes WIDE OPEN, looking at or near the camera lens
  ✓ Extreme facial expression — shock, anger, disgust, surprise, contempt, joy. NOT neutral, NOT "talking face"
  ✓ Mouth in an EXPRESSIVE shape: gritted teeth, jaw dropped (silent), smirk, scowl, lips pressed — NOT mid-syllable
  ✓ Head STILL (no motion blur from gesturing or moving)
  ✓ Face well-LIT (not in shadow)

A BAD thumbnail frame:
  ✗ Mid-word with mouth in awkward syllable shape (vowel-O, consonant-clicks, etc.)
  ✗ Eyes half-closed mid-blink, or looking down/away
  ✗ Wide shot where the face is small
  ✗ Neutral "speaking" expression (not extreme)
  ✗ Mid-gesture motion blur from moving hands or head
  ✗ Face partially obscured (hand in front, glare, etc.)

Pick the kept word whose start timestamp lands EXACTLY on the visual peak. The pipeline fine-tunes within ±0.6s, so get within ~0.5s of the actual best frame and let Python pick the best face from that window.

=== RESPONSE FORMAT ===

Output ONLY a JSON object — no commentary, no markdown fences, no prose.

{{
  "notes": "<=50 words>",
  "thumbnail_word_index": int,
  "caption_style": "<one of 21>",
  "caption_keywords": ["<word>", "<word>", ...],
  "caption_position_changes": [
    {{"word_index": int, "position": "top" | "center" | "bottom"}},
    ...
  ],
  "audio_denoise": bool,
  "outro": "none" | "fade_black" | "fade_white",
  "aspect_ratio": "9:16",
  "pacing": "fast" | "medium" | "slow",
  "emphasis_moments": [
    {{
      "word_indices": [int, ...],
      "type": "...",
      "intensity": "high" | "medium",
      "duration": float,
      "zoom_effect": {{...}} | null,
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

=== OUTPUT ORDER ===

The schema generates fields top-to-bottom in this order. Each field below builds on every field above it:

  1.  notes                         — your reasoning (set context, identify the spine)
  2.  remove_words                   — DECIDE CUTS FIRST — every anchor below references the surviving words
  3.  pacing                         — overall pace (fast / medium / slow)
  4.  caption_style                  — visual identity
  5.  caption_keywords               — keywords for the style
  6.  emphasis_moments               — the 2-5 strongest beats
  7.  transitions                    — major scene boundaries
  8.  sound_effects                  — layer audio on emphasis
  9.  motion_graphics                — visual reinforcement on specific moments
  10. text_overlays                  — chapter / hook cards
  11. broll_clips                    — cutaways during specific dialogue
  12. caption_position_changes       — derived from where MGs / face land
  13. thumbnail_word_index           — strongest still
  14. audio_denoise / outro / aspect_ratio — settings

By the time you write any anchor field (emphasis_moments[*].word_indices, transitions[*].after_word_index, sound_effects[*].word_index, motion_graphics[*].start_word_index/end_word_index, text_overlays[*].start_word_index, broll_clips[*].start_word_index/end_word_index, caption_position_changes[*].word_index, thumbnail_word_index), you have ALREADY committed your remove_words list above. Every anchor must reference a word that is NOT in remove_words. The renderer drops any element anchored to a removed word — silently in some cases, loudly in others. Either way, the element does not appear in the rendered video. You are responsible for not making this mistake; nothing else fixes it.

Note: every anchor field in this schema is word-index-based. You never emit float timestamps that must match word boundaries — Python derives all timestamps from word indices."""

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


def generate_edit_gemini(
    video_path, vibe, duration, trend_context=None, deepgram_words=None,
    shot_changes=None, vocal_emphasis=None, source_loudness=None,
    face_positions=None, smoothed_face_trajectory=None,
    user_style_profile=None,
    gemini_file=None, cached_response=None, inline_video_bytes=None,
):
    _pre_analysis = cached_response

    _shots = list(shot_changes or [])
    _vocal = list(vocal_emphasis or [])
    _loudness = dict(source_loudness or {})
    _face_positions = list(face_positions or [])
    _smoothed_trajectory = list(smoothed_face_trajectory or [])

    # Compute face signals from dense face detections. Speaker positions,
    # off-center flag, and shot scale gate zoom and side-overlay choices.
    # Face POSITION over time is intentionally NOT computed — Gemini sees
    # the video at 5 fps and decides where to place captions / MGs around
    # the speaker by looking at the actual frames.
    (
        _face_visibility,
        _speaker_positions,
        _off_center,
        _shot_scale,
    ) = _build_face_signals(_face_positions, deepgram_words or [], duration)

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

    # Append the full Deepgram transcript to USER content. Gemini owns every
    # cut decision via remove_words — there is no Python-side pre-pass, no
    # re-indexing. Word indices in the prompt match Deepgram source indices
    # 1:1, and any anchor Gemini emits is in the same source-index space.
    if deepgram_words:
        readable_transcript = " ".join(
            (_w.get("punctuated_word") or _w.get("word") or "")
            for _w in deepgram_words
        )

        word_lines = []
        for src_idx, _w in enumerate(deepgram_words):
            word_text = _w.get("punctuated_word") or _w.get("word") or ""
            start = float(_w.get("start") or 0)
            end = float(_w.get("end") or 0)
            spk = int(_w.get("speaker") or 0)
            word_lines.append(f"  [{src_idx}] {start:.2f}-{end:.2f} spk{spk}: {word_text}")

        transcript_block = "\n".join(word_lines)
        _first_word_start = float(deepgram_words[0].get("start") or 0)
        _word_count = len(deepgram_words)
        user_content += f"""

=== FULL TRANSCRIPT ===

Read this first to understand the full story before making any editing decisions. Identify the narrative structure — what is setup, what is the buildup, and where are the punchlines or reveals. Identify every filler word, stutter, abandoned restart, breath, dead-air pause, and tangent. You will cut all of them via remove_words.

{readable_transcript}

=== WORD-BY-WORD TIMESTAMPS ({_word_count} words, indexed [0..{_word_count - 1}]) ===

The following is the FULL Deepgram word-by-word transcript with millisecond-accurate timestamps. NO words have been pre-cut. Every word_index you emit in any anchor field references this index space directly.

{transcript_block}

RULES FOR USING THESE TIMESTAMPS:
- word_index is in the index space [0..{_word_count - 1}] shown above. Use those exact indices in anchor fields (start_word_index, end_word_index, word_indices, word_index, after_word_index, thumbnail_word_index, caption_position_changes[*].word_index).
- Anchor only to words you are KEEPING. Any word you also list in remove_words cannot be anchored to — the renderer will fail validation if you do.
- Your source_start and source_end values MUST land in the gaps BETWEEN words, not inside a word.
- A gap is the time between one word's end timestamp and the next word's start timestamp.
- NEVER place a source_start or source_end between a word's start and end timestamps — that cuts the word in half.
- The first word starts at {_first_word_start:.2f}s. For talking-head videos, set your first clip's source_start to the first KEPT word's start so the video starts on speech with zero dead air.
- If the video has intentional visual content before the first word (action, scenery, product shots), start source_start at 0.0 to preserve that content.
"""
        print(
            f"[generate-edit] Transcript prepared: {_word_count} words (raw Deepgram, no pre-cuts)",
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

    # Use the base EditPlan schema. Anchor integrity (no anchor on a removed
    # word) is enforced post-decode via the validator that scans every
    # word-index field against the remove_words set. Range cuts that cover
    # an anchored word are dropped by the anchor-integrity guard below.
    print(
        f"[generate-edit] Calling Gemini model={GEMINI_MODEL} (thinking=MEDIUM, structured output, temp=1.0, "
        f"system_instruction={len(system_instruction)} chars, user_content={len(user_content)} chars, "
        f"words={len(deepgram_words or [])})...",
        flush=True,
    )
    t = time.time()
    # temperature=1.0 is Google's explicit recommendation for Gemini 3 — values
    # below 1.0 "may lead to unexpected behavior, such as looping or degraded
    # performance." (per ai.google.dev/gemini-api/docs/text-generation)
    #
    # system_instruction + stable prefix enables implicit prompt caching — the
    # system block is byte-identical across calls; per-video data lives in
    # user_content, so Gemini re-reads only the deltas (video + transcript +
    # signals).
    #
    # thinking_level=HIGH. The edit decision spans dozens of inter-related
    # field choices (cuts, anchors, zones, transitions, MGs, captions) where
    # every later choice depends on every earlier one. MEDIUM was emitting
    # anchored elements that referenced words it had also placed in
    # remove_words — the model didn't have enough cycles to cross-check
    # itself. HIGH gives it the cycles. Adds ~10s/render.
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[_video_part, user_content],
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=1.0,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_json_schema=EditPlan.model_json_schema(),
            thinking_config=genai_types.ThinkingConfig(thinking_level="HIGH"),
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

    # Gemini emitted indices directly into the Deepgram source-index space —
    # no translation step needed. Downstream code below derives float
    # timestamps from word.start / word.end.

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
    # above. Once build_gemini_edit_prompt has returned, the raw face data has
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
            if "start" in _rw and "end" in _rw and "word_index" not in _rw:
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
            f"{len(normalized_remove_words)} Gemini removals",
            flush=True,
        )
        validated_cuts, _removed_word_indices = build_clips_from_words(_dg_words, normalized_remove_words, max_silence_gap=_speech_gap, video_duration=video_duration)
        edit_plan["_removed_word_indices"] = _removed_word_indices

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
        "PaperII",
        "Prime", "TypewriterReveal", "CinematicLetterpress", "Cove",
        "EditorialPop", "Illuminate", "Lumen",
        "MagazineCutout", "Passage", "Pulse", "Quintessence", "Serif",
        "GlitchHighlight", "NegativeFlash", "Prism",
    }
    _valid_zoom_types = {
        "SmoothPush", "SnapReframe", "FocusWindow", "StepZoom", "LetterboxPush",
        "StageZoom", "DepthPull",
    }
    _valid_mg_types = {
        "AnnotationArrow", "ChatThread",
        "Notification", "ProgressBar", "QuoteCard", "RecordingFrame",
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
        "torn_paper", "sticky_note", "quote_card", "caption_match",
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

    # ── B-roll vs motion-graphic temporal overlap validator ─────────────────
    # B-roll renders full-frame (covers the entire canvas). MGs render in
    # anchored zones. If a MG and B-roll overlap in time, the MG visually
    # appears ON TOP of the B-roll — a stack the user didn't ask for and
    # most viewers read as a layout glitch. Drop any MG whose word-window
    # overlaps a B-roll word-window, prioritizing the B-roll (it's larger
    # and conveys narrative content; MGs are accents).
    if validated_mg and validated_broll:
        _broll_windows = []
        for _bc in validated_broll:
            _bs = int(_bc.get("start_word_index", -1))
            _be = int(_bc.get("end_word_index", -1))
            if _bs >= 0 and _be >= _bs:
                _broll_windows.append((_bs, _be))
        if _broll_windows:
            _kept_mgs = []
            for _mg in validated_mg:
                _ms = int(_mg.get("start_word_index", -1))
                _me = int(_mg.get("end_word_index", -1))
                if _ms < 0 or _me < _ms:
                    _kept_mgs.append(_mg)
                    continue
                _conflicts = False
                for (_bs2, _be2) in _broll_windows:
                    # Word-index overlap: max(start_a, start_b) <= min(end_a, end_b)
                    if max(_ms, _bs2) <= min(_me, _be2):
                        _conflicts = True
                        break
                if _conflicts:
                    print(
                        f"[mg] Dropping {_mg.get('type')!r} at words "
                        f"[{_ms}-{_me}] — overlaps B-roll window. "
                        f"B-roll is full-frame; MG would stack on top.",
                        flush=True,
                    )
                    continue
                _kept_mgs.append(_mg)
            if len(_kept_mgs) != len(validated_mg):
                _dropped_count = len(validated_mg) - len(_kept_mgs)
                print(f"[mg] Dropped {_dropped_count} MG(s) for B-roll overlap", flush=True)
                validated_mg = _kept_mgs
                edit_plan["motion_graphics"] = validated_mg

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
    # source content in the timeline — no production NLE does this. The
    # opening punch comes from cut[0] being the strongest moment, picked
    # by Gemini per the prompt.
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
        # continue — render proceeds without this single beat rather than
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
            _ze_out = {"type": _zt, "events": _ze_raw.get("events") or []}
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

    # High-intensity emphasis pacing: no two within 2.5s of each other. Drop
    # any second-or-later high-intensity emphasis that crowds the previous one
    # — render continues without the dropped emphasis.
    _drop_idx = set()
    _prev_high_t = None
    for _i, em in enumerate(emphasis_moments):
        if em["intensity"] != "high":
            continue
        if _prev_high_t is not None and (em["t"] - _prev_high_t) < 2.5:
            print(
                f"[generate-edit] DROP emphasis_moment [{_i}] high-intensity: "
                f"t={em['t']:.2f}s is {em['t'] - _prev_high_t:.2f}s after "
                f"previous high-intensity at {_prev_high_t:.2f}s (minimum 2.5s). "
                f"Render continues without this emphasis.",
                flush=True,
            )
            _drop_idx.add(_i)
            continue
        _prev_high_t = em["t"]
    if _drop_idx:
        emphasis_moments = [em for _i, em in enumerate(emphasis_moments) if _i not in _drop_idx]

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
            # Zoom emphasis lands in a cut/removed segment — clear just the
            # zoom and keep the rest of the emphasis (text, MG) intact.
            print(
                f"[generate-edit] CLEAR emphasis_moments[{_ei}].zoom_effect: "
                f"t={em['t']:.2f}s falls outside every validated clip. "
                f"Render continues with the emphasis but no zoom.",
                flush=True,
            )
            em["zoom_effect"] = None
            continue
        if _owning_clip in _clip_zoom_owner:
            _prev = _clip_zoom_owner[_owning_clip]
            print(
                f"[generate-edit] CLEAR emphasis_moments[{_ei}].zoom_effect: "
                f"clip {_owning_clip} already owned by emphasis [{_prev}] "
                f"({validated_cuts[_owning_clip]['source_start']:.2f}-"
                f"{validated_cuts[_owning_clip]['source_end']:.2f}s). Only one "
                f"zoom can run per clip. Render continues with this emphasis "
                f"but no zoom.",
                flush=True,
            )
            em["zoom_effect"] = None
            continue
        _clip_zoom_owner[_owning_clip] = _ei
        # Attach the emphasis zoom_effect to its owning validated_cut.
        # Mirrors how transitions attach (~line 4117): single source of
        # truth carried forward by validated_cuts → final_cuts →
        # render_cuts → clips_out. Without this, the zoom only gets written
        # to render_cuts AFTER clips_out is already built, so every
        # emphasis zoom is silently lost.
        validated_cuts[_owning_clip]["_zoom_effect"] = em["zoom_effect"]

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

    # ── Zone-aware overlap validation ────────────────────────────────────────
    # Two overlays may share a time window IF they live in different visual
    # zones. Only same-zone + overlapping-time is a real collision.
    #
    # Per-variant rendered zone for text_overlays — used for collision
    # detection only. Each variant's component pins to a fixed zone by
    # design: torn_paper = top banner (TornPaper component renders at the
    # top regardless of anchor), sticky_note = upper third pin,
    # quote_card = center floating card. `caption_match` is dynamic from
    # its `position` prop. Motion graphics carry their zone explicitly
    # via the `anchor` field.
    _TEXT_OVERLAY_ZONE = {
        "torn_paper":    "upper_third_safe",
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
        final_cuts.append(_new_cut)

    # Zoom and motion graphics are attached to each emphasis_moment explicitly
    # by Gemini (emphasis_moments[i].zoom_effect / motion_graphic). No
    # auto-SnapReframe, no auto-SmoothPush. If Gemini didn't emit a
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
        "transitions, caption_style, caption_position_changes (list of {word_index, position}), "
        "caption_position_segments (DERIVED from caption_position_changes — do not edit directly), "
        "keywords, broll_clips, text_overlays (each has a variant "
        "discriminator: torn_paper|sticky_note|quote_card|caption_match), "
        "motion_graphics (with semantic anchor), emphasis_moments (each binds explicit "
        "zoom_effect / motion_graphic), sfx_placements, thumbnail_word_index "
        "(thumbnail_timestamp derived), per-clip `speed` (constant 0.7–1.4 per cut), outro. "
        "The user has requested a change. Your job:\n\n"
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
        "clip_in/out), sfx_placements, text_overlays, motion_graphics, "
        "emphasis_moments, caption_position_changes (and the derived caption_position_segments) "
        "— everything else — unchanged. Every timing decision references a word by index; never "
        "invent or shift a raw timestamp. The pipeline derives timestamps from word_index fields.\n\n"
        "3) Emit changed_fields: dotted paths of what you changed (e.g. ['caption_style', "
        "'cuts[3].speed', 'caption_position_changes[1].position', 'text_overlays[2].variant']). "
        "Empty array for reinterpret or clarification.\n\n"
        "4) Emit human_summary: one sentence users can read (e.g. 'Changed caption style to "
        "minimal. Preserved 11 cuts, B-roll, and 2 text overlays.').\n\n"
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

TRANSITION_DURATION_DEFAULT = 0.55

def get_transition_duration(pacing=None):
    """Adaptive transition duration based on video pacing.

    The ABE pack components are designed for ~3s (90 frames at 30fps);
    cutting to 6 frames at the previous fast=0.20s left them as a
    single-frame flash with no animation arc — visible as a glitch
    rather than a transition. New durations target 16-30 frames at
    60fps, which lets the components hit their ramp-in / hold /
    ramp-out cycle while still feeling snappy on fast-paced content.
    """
    if pacing == "fast":
        return 0.4   # 24 frames at 60fps — readable but snappy
    elif pacing == "slow":
        return 0.75  # 45 frames at 60fps — smooth and cinematic
    return TRANSITION_DURATION_DEFAULT  # 33 frames at 60fps — default


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
        # fps/VFR conversion is handled by fps-normalize step (60fps + minterpolate) — no normalize_vf needed
        if abs(fps - 30) > 1 or is_vfr:
            print(f"[analyze] Source {w}x{h} @ {fps:.2f}fps (VFR={is_vfr}) — fps-normalize step handles it", flush=True)
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


def build_per_cut_audio(source_path, cuts, effective_durations, work_dir, sample_rate=48000, trans_dur_after=None, per_cut_render_dur_frames=None, source_fps=60.0, trim_head_dur=None, trim_tail_dur=None):
    """Build the per-cut audio track in one numpy pass — pro NLE overlap model.

    Source audio is extracted ONCE (one ffmpeg invocation) and held in
    memory. Each cut's RENDER range (source[start + trim_head*speed,
    end − trim_tail*speed]) is sliced and resampled at the cut's
    constant speed. Each transition's audio is the cross-fade of the
    HANDLE source ranges that were trimmed from clips A and B —
    SAME source content the transition video is rendering, so audio
    and video stay in lockstep, and no source content is heard twice.

    SAMPLE-LOCKED ALIGNMENT (sub-20ms drift target):
      Audio sample count per cut is derived from the *exact* video frame
      count (per_cut_render_dur_frames[i]) so audio and video lengths
      match within ±1 sample (~21 µs) per cut.

    PRO NLE OVERLAP — NO PADDING:
      Old model: clip A renders full eff_dur, transition adds trans_dur,
      clip B renders full eff_dur. Audio had to pad with silence or
      cross-fade buffer to match the longer video, AND clip A's tail
      was shown twice (in clip A's render and again as part of the
      transition). The "fix" was a buffer.
      New model: clip A renders for (eff_dur_A − trim_tail_A), clip B
      renders for (eff_dur_B − trim_head_B), transition fills the
      trans_dur gap using the trimmed-off handles from A and B. Audio
      and video durations match by construction. Each piece of source
      content shown ONCE.

    Returns the path to the concatenated WAV.
    """
    import numpy as np
    import wave

    output_wav = os.path.join(work_dir, "per_cut_audio.wav")

    # ── Single source extraction ────────────────────────────────────────
    full_src_wav = os.path.join(work_dir, "source_audio_full.wav")
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
            s_idx = max(0, int(round(render_src_start * sample_rate)))
            e_idx = min(src_total, s_idx + n_out)
            slc = src_samples[s_idx:e_idx]
            if len(slc) >= n_out:
                cut_audios.append(slc[:n_out].astype(np.float32))
            else:
                padded = np.zeros(n_out, dtype=np.float32)
                padded[:len(slc)] = slc
                cut_audios.append(padded)
        else:
            cut_audios.append(_resample_range(render_src_start, render_src_end, n_out))

    # ── Transition audio — equal-power cross-fade of the handle ranges ──
    # For each transition, the trimmed-off source content from clip A's
    # tail and clip B's head IS the audio for the transition. No
    # duplication: that source content is NOT played anywhere else.
    all_clips: List[np.ndarray] = []
    _n_crossfades = 0
    for ci, cut_audio in enumerate(cut_audios):
        all_clips.append(cut_audio)
        _t_after = 0.0
        if trans_dur_after is not None and ci < len(trans_dur_after):
            _t_after = float(trans_dur_after[ci] or 0.0)
        if _t_after <= 0 or ci + 1 >= len(cuts):
            continue
        cut_a = cuts[ci]
        cut_b = cuts[ci + 1]
        speed_a = float(cut_a.get("speed") or 1.0)
        speed_b = float(cut_b.get("speed") or 1.0)
        n_trans = max(1, int(round(_t_after * sample_rate)))
        # A's tail HANDLE: source[c_a_end − t_after*speed_a, c_a_end] resampled to n_trans
        c_a_end = float(cut_a["source_end"])
        a_handle = _resample_range(c_a_end - _t_after * speed_a, c_a_end, n_trans)
        # B's head HANDLE: source[c_b_start, c_b_start + t_after*speed_b] resampled to n_trans
        c_b_start = float(cut_b["source_start"])
        b_handle = _resample_range(c_b_start, c_b_start + _t_after * speed_b, n_trans)
        # Equal-power cross-fade (cos²/sin² = 1 → constant perceived loudness).
        t = np.linspace(0, np.pi / 2, n_trans, dtype=np.float32)
        cross = a_handle * np.cos(t) + b_handle * np.sin(t)
        all_clips.append(cross)
        _n_crossfades += 1

    if not all_clips:
        with wave.open(output_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00" * sample_rate * 2)
        return output_wav

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
        f"{_n_crossfades} cross-fade(s), "
        f"{_total_dur:.3f}s, {len(full_audio)} samples (single-extract)",
        flush=True,
    )
    return output_wav


def project_words_to_output(transcript, cuts, effective_durations, transition_duration=None, clip_time_maps=None, removed_word_indices=None, fps=60.0, trans_dur_after=None):
    """Project word timestamps from source to output timeline using canonical time maps.

    If removed_word_indices is provided, words at those indices are excluded.
    This is the SAME source of truth used by build_clips_from_words, so the
    caption projection cannot emit fragments of removed words.

    `trans_dur_after[i]` (when provided) is the seconds the next cut's full
    window overlaps the END of cut i's full window in the pro-NLE overlap
    model. Words in the OUTGOING cut's tail (last trans_dur seconds of
    output) are SUPPRESSED to avoid two captions rendering simultaneously
    during the transition window — the incoming cut's head words own the
    transition's caption real estate. Both sides are still audible (the
    cross-fade plays both clips), but only one caption shows at a time.
    """
    words = transcript.get("words") or []
    projected = []
    if not words or not cuts:
        return projected
    _removed = removed_word_indices if isinstance(removed_word_indices, (set, frozenset)) else set(removed_word_indices or [])
    clip_ranges = get_output_clip_ranges(cuts, effective_durations, transition_duration=transition_duration, trans_dur_after=trans_dur_after)
    output_cursor = 0.0
    for i, cut in enumerate(cuts):
        c_start = float(cut["source_start"])
        c_end   = float(cut["source_end"])
        tm = clip_time_maps[i] if clip_time_maps and i < len(clip_time_maps) else None
        # Cut's eff_dur (full output window length) and trans_tail
        # (output seconds at the END of this cut's window that overlap
        # with the incoming next cut's head — those are the "transition"
        # window where the next cut's captions take precedence).
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
            # Captions and audio share the same source-of-truth timestamps;
            # rounding to ms here would put captions on a 1 ms grid while
            # audio is sample-precise, introducing visible drift between
            # caption highlight and spoken word over a long clip.
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
        # Pro NLE overlap model: cursor advances by full eff_dur, then
        # SUBTRACT trans_dur_after (the transition overlaps with this
        # cut's tail and the next cut's head). Without subtracting,
        # caption/SFX positions land trans_dur per transition LATER
        # than the actual rendered timeline.
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

    Pro NLE OVERLAP MODEL:
      Adjacent clips overlap by `trans_dur` seconds when there's a
      transition between them. Clip A's tail (last trans_dur of output)
      and Clip B's head (first trans_dur of output) occupy the SAME
      output time range — that's the transition window. Total timeline
      shortens by trans_dur per transition, not extends by it.

      Cursor advance per cut = eff_dur − trans_dur_after (the trans_dur
      is "absorbed" by the next cut's overlap with this cut's tail).

    Args:
      cuts: list of cut dicts with source_start/source_end/transition_out.
      effective_durations: per-cut output duration in seconds (full eff_dur,
        covering source_start..source_end at the cut's speed).
      transition_duration: kept for API compatibility (unused here).
      trans_dur_after: optional list. trans_dur_after[i] = transition
        duration in seconds between cut i and cut i+1 (0 if no transition).
        When None, defaults to all-zero (no transitions).
    """
    _ = transition_duration  # API compat
    ranges = []
    cursor = 0.0
    for i, cut in enumerate(cuts):
        dur   = effective_durations[i] if i < len(effective_durations) else 0.0
        start = cursor
        end   = cursor + dur
        ranges.append({"start": start, "end": end})
        # Advance cursor by full eff_dur, then SUBTRACT trans_dur_after
        # (transitions OVERLAP — the next cut starts trans_dur seconds
        # before this cut's full window ends).
        cursor += dur
        if trans_dur_after is not None and i < len(trans_dur_after):
            cursor -= float(trans_dur_after[i] or 0.0)
    return ranges


def build_clips_from_words(deepgram_words, remove_words, max_silence_gap=0.15, video_duration=0.0):
    """Apply Gemini's remove_words decisions and split kept words into clips.

    Single cut authority: Gemini's `remove_words` (word_index + range entries)
    is the only source of cuts. Python applies them verbatim — no filler /
    stutter / phrasal-restart / dead-air detection. Pattern matchers cannot
    discriminate abandoned restarts from rhetorical repetition; Gemini reads
    the full transcript with video context and decides.

    Pipeline:
      1. Apply Gemini's remove_words (word indices + time ranges)
      2. Build clips from kept words, splitting on silence > max_silence_gap
      3. Reject sub-120ms micro-clips (orphan-island removals — Gemini's job
         to consolidate)
      4. Verify non-overlap invariant

    Cut times are sample-precise raw Deepgram timestamps — no padding,
    no cushion, no rounding. The audio cut path uses round(t * sample_rate)
    for indexing, so the rendered splice lands at the exact sample.

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

    # ── Step 2: Build clips from kept words ───────────────────────────────
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

    # ── Step 3: Build raw clips at exact word boundaries ──────────────────
    # No padding. Cuts land at Deepgram's word.start and word.end exactly.
    # The render pipeline (PCM-audio segments + AAC-once final encode) is
    # sample-accurate, so the boundary in the rendered video matches the
    # boundary we ask for here.
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

    # ── Step 4: Reject micro-clips ────────────────────────────────────────
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
    # Raw Deepgram timestamps. The downstream audio cut path uses
    # round(time * sample_rate) for indexing, so an unrounded float here
    # produces a sample-precise splice.
    final_clips = []
    for rc in raw_clips:
        s = float(rc["padded_start"])
        e = float(rc["padded_end"])
        if _vd > 0 and e > _vd:
            e = float(_vd)
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

    Final step: ffmpeg mux — stream-copy video + AAC audio into output_path.
    """
    import math

    # ── 0. Source is already canonical ──────────────────────────────────────
    # The ingest pass (_do_fps_normalize in mega_pool) folded fps + scale +
    # crop + pix_fmt into a single transcode and produced source_canonical.mp4.
    # By the time we get here, source_path is a 1080x1920 60fps yuv420p h264
    # file. Nothing in this function needs to re-normalize the source.

    # ── 1. Pre-render clip setup ────────────────────────────────────────────
    TRANSITION_DURATION = get_transition_duration(edit_plan.get("pacing"))
    print(f"[render] transition_duration={TRANSITION_DURATION:.2f}s (pacing={edit_plan.get('pacing')})", flush=True)

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

    # ── Pro-NLE overlap model for transitions ───────────────────────────────
    # Professional editors (Premiere, Resolve, Final Cut, CapCut) handle
    # transitions as OVERLAPS: clips A and B overlap by trans_dur on the
    # timeline, and the transition decides what's visible during the
    # overlap region. Total timeline = sum(eff_dur) − sum(trans_dur) per
    # pair — NOT sum(eff_dur) + sum(trans_dur). Each piece of source
    # content is shown EXACTLY ONCE (no duplication of clip A's tail or
    # clip B's head, which the previous concat-with-padding model produced).
    #
    # Implementation: for each cut, compute trim_head_dur (output seconds
    # consumed by the incoming transition) and trim_tail_dur (output
    # seconds consumed by the outgoing transition). The cut's RENDER
    # duration is `eff_dur − trim_head − trim_tail`; its render source
    # range is `[c_start + trim_head*speed, c_end − trim_tail*speed]`.
    # The "handles" — `[c_start, c_start + trim_head*speed]` and
    # `[c_end − trim_tail*speed, c_end]` — are reserved for the
    # adjacent transitions (which already pull from those exact ranges
    # via clipAStartFromFrames / clipBStartFromFrames).
    #
    # If a cut is too short to accommodate its transition handles
    # (eff_dur < trim_head + trim_tail + min_render), drop the
    # outgoing transition (preferred: affects only this pair) or the
    # incoming transition. This matches NLE behavior — "insufficient
    # handles" produces a warning, not a render failure.
    _T_trans = TRANSITION_DURATION
    _T_trans_frames = max(1, int(round(_T_trans * source_fps)))
    _MIN_RENDER_DUR = 0.05  # min seconds a clip must render after handles

    def _has_real_transition(_rc):
        return str(_rc.get("transition_out") or "none") in VALID_TRANSITION_TYPES

    _trim_head_dur = [0.0] * len(render_cuts)
    _trim_tail_dur = [0.0] * len(render_cuts)
    for _i in range(len(render_cuts)):
        _has_in = _i > 0 and _has_real_transition(render_cuts[_i - 1])
        _has_out = _i < len(render_cuts) - 1 and _has_real_transition(render_cuts[_i])
        _trim_head_dur[_i] = _T_trans if _has_in else 0.0
        _trim_tail_dur[_i] = _T_trans if _has_out else 0.0

    # Drop transitions on clips that can't afford the handles. Iterate
    # left-to-right; if a cut's render dur would go below _MIN_RENDER_DUR,
    # drop its outgoing transition first (cascades cleanly), then incoming.
    _dropped = 0
    for _i in range(len(render_cuts)):
        _eff = effective_durations[_i]
        while _eff - _trim_head_dur[_i] - _trim_tail_dur[_i] < _MIN_RENDER_DUR:
            if _trim_tail_dur[_i] > 0 and _i < len(render_cuts) - 1:
                print(
                    f"[transitions] Cut {_i} eff_dur={_eff:.3f}s lacks handles; "
                    f"dropping outgoing {render_cuts[_i].get('transition_out')!r}.",
                    flush=True,
                )
                render_cuts[_i]["transition_out"] = "none"
                _trim_tail_dur[_i] = 0.0
                _trim_head_dur[_i + 1] = 0.0
                _dropped += 1
            elif _trim_head_dur[_i] > 0 and _i > 0:
                print(
                    f"[transitions] Cut {_i} eff_dur={_eff:.3f}s lacks handles; "
                    f"dropping incoming "
                    f"{render_cuts[_i - 1].get('transition_out')!r}.",
                    flush=True,
                )
                render_cuts[_i - 1]["transition_out"] = "none"
                _trim_tail_dur[_i - 1] = 0.0
                _trim_head_dur[_i] = 0.0
                _dropped += 1
            else:
                break  # nothing left to drop; clip is just short
    if _dropped > 0:
        print(f"[transitions] Dropped {_dropped} transition(s) for insufficient handles.", flush=True)

    # Final transition durations after drops (used by audio + projection)
    _trans_dur_after = []
    _trans_frames_after = 0
    for _i, _rc in enumerate(render_cuts):
        _has_out = _i < len(render_cuts) - 1 and _has_real_transition(_rc)
        if _has_out:
            _trans_dur_after.append(_T_trans)
            _trans_frames_after += _T_trans_frames
        else:
            _trans_dur_after.append(0.0)

    # Per-cut RENDER frame count (after handle trim).
    _per_cut_render_dur_frames: List[int] = []
    for _i in range(len(render_cuts)):
        _render_dur = effective_durations[_i] - _trim_head_dur[_i] - _trim_tail_dur[_i]
        _per_cut_render_dur_frames.append(max(1, int(round(_render_dur * source_fps))))

    # Total output = sum(render frames) + sum(trans frames)
    n = len(render_cuts)
    total_output_frames = max(1, sum(_per_cut_render_dur_frames) + _trans_frames_after)
    total_output_duration = total_output_frames / float(source_fps)

    # Output clip ranges — each cut's full output window (eff_dur span,
    # including handle portions consumed by adjacent transitions). Cursor
    # advances by (eff_dur − trans_dur_after) per cut: the transition
    # OVERLAPS with this cut's tail and the next cut's head, so we
    # SUBTRACT trans_dur instead of adding. This is the pro NLE model.
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
    clips_out = []
    for i, (rc, tm, eff_dur) in enumerate(zip(render_cuts, _clip_time_maps, effective_durations)):
        _pbr = float(tm.get("avg_speed") or 1.0)
        _trim_h = _trim_head_dur[i]
        _trim_t = _trim_tail_dur[i]
        # The clip's RENDER source range is shifted forward by trim_head*speed
        # (handles for the incoming transition) and shortened by trim_tail*speed
        # (handles for the outgoing transition). Clip A's tail handle and
        # clip B's head handle are reserved for the adjacent transitions —
        # rendered there, not here, eliminating duplication.
        _source_start_seconds = float(rc["source_start"]) + _trim_h * _pbr
        _source_start_frames = int(round(_source_start_seconds * source_fps))
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
                _ev_end_ms = _new_start_ms + _new_dur_ms
                if _ev_end_ms <= 0:
                    continue
                if _new_start_ms >= _clip_render_output_ms:
                    continue
                _overlapping_events.append({
                    **_ev,
                    "startMs": _new_start_ms,
                    "durationMs": _new_dur_ms,
                })
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
    _T_trans = TRANSITION_DURATION
    _T_trans_frames = max(1, int(round(_T_trans * source_fps)))
    for i in range(len(render_cuts) - 1):
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
        print(f"[transition] {_t_raw} after clip {i} — {_T_trans_frames}f", flush=True)

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
    # BrollSpec to broll_out. PromptlyOverlay and PromptlyMicroSegments
    # ignore the broll field; only the FFmpeg composite filtergraph reads it.
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
        _source_start = float(_ov["_source_start"])
        _out_start = project_source_time_to_output(
            _source_start, render_cuts, _clip_ranges,
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

    caption_pages = _build_tiktok_pages_from_projected(
        _projected_words,
        max_words_per_page=3,
        position_boundaries_sec=sorted(set(_position_boundaries_out_sec)),
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
    for _mg in (edit_plan.get("motion_graphics") or []):
        _sw_source = float(_mg["_source_start"])
        _ew_source = float(_mg["_source_end"])
        _out_start = project_source_time_to_output(
            _sw_source, render_cuts, _clip_ranges,
            clip_time_maps=_clip_time_maps,
        )
        _out_end = project_source_time_to_output(
            _ew_source, render_cuts, _clip_ranges,
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
    # Each emphasis moment's visual layers (zoom / MG) get projected and
    # merged into the Remotion input here.
    for em in edit_plan.get("_emphasis_moments", []):
        _em_t_out = project_source_time_to_output(
            float(em["t"]), render_cuts, _clip_ranges,
            clip_time_maps=_clip_time_maps,
        )
        if _em_t_out is None:
            raise RuntimeError(
                f"Emphasis moment at source {em['t']}s was removed from the output "
                f"timeline — Gemini flagged a moment in a cut segment."
            )
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

    # Z-order: Gemini owns it. Per Rule #5 in the prompt, when any MG covers
    # the bottom band, Gemini emits a caption_position_change to "top" for
    # that window. Python does not auto-flip — caption_position_segments_out
    # is whatever Gemini decided.

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
    #                              SnapReframe / StepZoom / StageZoom) ported
    #                              to per-frame `crop` expressions, B-roll
    #                              cutaways, outro fade. Built directly by
    #                              FFmpeg in the final composite pass.
    # Net: Remotion only paints the visual layers it has to (overlay +
    # complex-segment windows). FFmpeg handles every video-paint frame at
    # native speed (libx264 ultrafast + lanczos resample on 64 cores).
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
    _expected_zooms = sum(
        1 for em in (edit_plan.get("_emphasis_moments") or [])
        if em.get("zoom_effect")
    )
    # One emphasis_moment with zoom_effect = exactly one cut with
    # zoomEffect (no fan-out — cuts are non-overlapping in source time
    # since auto-hook duplication was deleted). Strictly less actual
    # than expected means we silently dropped a zoom — bail loud.
    _actual_zooms = sum(1 for _c in clips_out if _c.get("zoomEffect"))
    if _actual_zooms < _expected_zooms:
        raise RuntimeError(
            f"Pipeline integrity violation: only {_actual_zooms} "
            f"clip(s) carry a zoomEffect in clips_out but "
            f"{_expected_zooms} validated emphasis_moment(s) had a "
            f"zoom_effect after collision check. At least one validated "
            f"zoom was dropped between validation and output spec."
        )

    _expected_transitions = sum(
        1 for c in cuts
        if c.get("transition_out") and c.get("transition_out") != "none"
    )
    if len(transitions_out) != _expected_transitions:
        raise RuntimeError(
            f"Pipeline integrity violation: transitions_out has "
            f"{len(transitions_out)} entries but validated_cuts carries "
            f"{_expected_transitions} non-none transition_out fields. "
            f"Every validated transition must reach the output spec."
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

    def _stage_file(src_abs_path):
        """Materialize `src_abs_path` into the bundle public root with a
        stage-key-prefixed basename. Returns the URL Remotion sees relative to
        publicDir (just the prefixed basename — staticFile resolves it to
        /<basename> served from /remotion/bundle/public/<basename>)."""
        if not os.path.exists(src_abs_path):
            raise RuntimeError(
                f"Cannot stage local file for Remotion: {src_abs_path} does not exist."
            )
        _orig = os.path.basename(src_abs_path)
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

    # ── Blend-mode caption flag ────────────────────────────────────────────
    # When the chosen caption_style uses CSS mixBlendMode (GlitchHighlight /
    # NegativeFlash / Prism), v62 still runs end-to-end — it just produces the
    # video WITHOUT those captions (handler zeroes their pages out and filters
    # any caption_match-variant text overlays from PromptlyOverlay's input).
    # After v62 is done, a small second Remotion pass (PromptlyBlendCaptionsOnly)
    # reads the silent intermediate as <OffthreadVideo> source and draws the
    # blend captions + caption_match overlays on top so the existing mixBlendMode
    # CSS has real frame content underneath. Audio mux happens last.
    _is_blend_render = _caption_style in _BLEND_MODE_CAPTION_STYLES
    if _is_blend_render:
        print(
            f"[render] Caption style '{_caption_style}' uses CSS blend modes — "
            f"will run v62 + PromptlyBlendCaptionsOnly second pass.",
            flush=True,
        )

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
        # B-roll is always composited by FFmpeg in v62. The src is the
        # absolute on-disk /tmp path; FFmpeg reads it directly.
        broll_out.append({
            "src": _local_path,
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

    # PromptlyOverlay input — captions/MG/text on a transparent canvas. In
    # blend-mode renders, captions and caption_match-variant text overlays
    # are dropped here because they need real video pixels underneath; they
    # render in the second-pass PromptlyBlendCaptionsOnly composition
    # instead. Other text-overlay variants (torn_paper / sticky_note /
    # quote_card) and MGs render here in both modes — they don't depend on
    # video pixels.
    if _is_blend_render:
        _v62_caption = {
            "style": _caption_style,
            "pages": [],
            "keywords": _caption_keywords,
            "positionSegments": caption_position_segments_out,
            "extraProps": _caption_extra_props,
        }
        _v62_text_overlays = [
            ov for ov in text_overlays_out
            if ov.get("variant") != "caption_match"
        ]
    else:
        _v62_caption = {
            "style": _caption_style,
            "pages": caption_pages,
            "keywords": _caption_keywords,
            "positionSegments": caption_position_segments_out,
            "extraProps": _caption_extra_props,
        }
        _v62_text_overlays = text_overlays_out
    overlay_input = {
        "sourceUrl": _source_url,
        "fps": source_fps,
        "width": 1080,
        "height": 1920,
        "totalDurationInFrames": total_output_frames,
        "clips": clips_out,
        "transitions": transitions_out,
        "broll": broll_out,
        "caption": _v62_caption,
        "textOverlays": _v62_text_overlays,
        "motionGraphics": motion_graphics_out,
        "outro": _outro,
    }
    overlay_input_path = os.path.join(_stage_dir, "overlay_input.json")
    _validate_and_write_render_input(
        "overlay", overlay_input, _SchemaOverlayInput, overlay_input_path,
    )

    # PromptlyMicroSegments input — only the windows Remotion must render.
    # Each segment carries its own clip/transition spec; Python tracks a
    # parallel list of metadata (with _clipIndex / _afterClipIndex tags) so
    # the FFmpeg final-mux filtergraph can find each segment by source.
    # Always runs — blend mode goes through v62 too, just with a captions
    # second pass on top afterwards.
    micro_input, micro_segments_meta = build_micro_segments_input(
        clips_out, transitions_out, _source_url, source_fps,
    )
    micro_input_path = None
    if micro_input is not None:
        micro_input_path = os.path.join(_stage_dir, "micro_input.json")
        _validate_and_write_render_input(
            "micro", micro_input, _SchemaMicroInput, micro_input_path,
        )

    # PromptlyBlendCaptionsOnly input — built only when caption style needs
    # video pixels for blend modes. videoUrl is set later, after the v62
    # silent intermediate is staged into the bundle public root. captionMatch
    # overlays are the subset of text_overlays that render through the
    # caption component, so they also need to be drawn on top of the video.
    blend_captions_input = None
    blend_captions_input_path = None
    if _is_blend_render:
        _blend_caption_match_overlays = [
            ov for ov in text_overlays_out
            if ov.get("variant") == "caption_match"
        ]
        blend_captions_input = {
            "videoUrl": "",  # filled in after v62 silent intermediate is staged
            "fps": source_fps,
            "width": 1080,
            "height": 1920,
            "totalDurationInFrames": total_output_frames,
            "caption": {
                "style": _caption_style,
                "pages": caption_pages,
                "keywords": _caption_keywords,
                "positionSegments": caption_position_segments_out,
                "extraProps": _caption_extra_props,
            },
            "captionMatchOverlays": _blend_caption_match_overlays,
        }

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

    # Per-cut audio — pro NLE overlap model. Each cut's audio uses its
    # RENDER range (source[start + trim_head*speed, end − trim_tail*speed]);
    # transition audio is a real cross-fade of the trimmed-off handles
    # (same source the transition video is rendering). Audio + video
    # durations match by construction — no padding, no buffer.
    _audio_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    _speed_audio_future = _audio_pool.submit(
        build_per_cut_audio, source_path, render_cuts,
        effective_durations, work_dir,
        sample_rate=sample_rate, trans_dur_after=_trans_dur_after,
        per_cut_render_dur_frames=_per_cut_render_dur_frames,
        source_fps=source_fps,
        trim_head_dur=_trim_head_dur, trim_tail_dur=_trim_tail_dur,
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
    micro_video_path = os.path.join(work_dir, "micro_segments.mp4")
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
    micro_cmd = None
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

    if micro_input is not None:
        micro_cmd = [
            "node", "/remotion/render-full.mjs",
            "--input", micro_input_path,
            "--output", micro_video_path,
            "--public-dir", _bundle_public_root,
            "--composition", "PromptlyMicroSegments",
            "--gl", _gl_mode,
        ]

    _render_t0 = time.time()
    if _overlay_chunked:
        print(
            f"[render] Spawning {len(overlay_cmds)} overlay chunk subprocesses "
            f"({total_output_frames} frames split {len(_overlay_ranges)}-ways, "
            f"concurrency={_PER_CHUNK_CONCURRENCY} each)"
            f"{' + 1 micro subprocess' if micro_cmd else ''} (gl={_gl_mode})",
            flush=True,
        )
    else:
        print(
            f"[render] Spawning Remotion renders: PromptlyOverlay (single, "
            f"{total_output_frames}f)"
            f"{' + PromptlyMicroSegments' if micro_cmd else ''} (gl={_gl_mode})",
            flush=True,
        )
    _render_pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, len(overlay_cmds) + (1 if micro_cmd else 0)),
    )
    overlay_futures = [
        _render_pool.submit(_run_remotion, _lbl, _cmd)
        for _lbl, _cmd in overlay_cmds
    ]
    micro_future = _render_pool.submit(_run_remotion, "micro", micro_cmd) if micro_cmd else None

    # ── Audio pipeline (running on a separate thread) —
    # Collect its output now so the final-audio build can start while the
    # Remotion renders are still in flight.
    _speed_audio_path = _speed_audio_future.result(timeout=60)
    _audio_pool.shutdown(wait=False)
    if not _speed_audio_path or not os.path.exists(_speed_audio_path):
        raise RuntimeError(f"Per-cut audio pipeline produced no output at {_speed_audio_path}")

    # ── 11. Build final audio (SFX mix + EQ chain) → .m4a ─────────
    # SFX play OVER the dialogue at full volume — no ducking, no dipping.
    # The dialogue stays at its full level throughout; SFX add on top via
    # amix with normalize=0 (linear sum, not auto-gain-reduced).
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

    # ── 12. Wait for Remotion renders, then ffmpeg composite ────────────
    # All the heavy v62 work happens in this one ffmpeg invocation:
    #   1. Build each ffmpeg-renderable clip from source via trim+setpts+(zoom?)
    #   2. Trim each Remotion-rendered clip/transition out of micro_segments.mp4
    #      by frame range
    #   3. Concat all timeline segments in order → [base]
    #   4. Overlay each B-roll cutaway at its output-time window
    #   5. Apply outro fade (if configured)
    #   6. Alpha-composite the PromptlyOverlay layer (captions + MGs + non-
    #      caption_match text overlays — blend captions are handled by the
    #      second-pass PromptlyBlendCaptionsOnly composition that runs after
    #      this composite finishes, when caption_style is a blend style).
    #   7. libx264 ultrafast crf 18 silent intermediate (audio mux is a
    #      separate stream-copy step at the very end).
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
    if micro_future:
        micro_elapsed = micro_future.result(timeout=320)
        print(f"[render] PromptlyMicroSegments done in {micro_elapsed:.1f}s → "
              f"{os.path.getsize(micro_video_path)/1024/1024:.1f}MB", flush=True)
    _render_pool.shutdown(wait=False)
    _render_elapsed = time.time() - _render_t0

    # ── Concat overlay chunks (-c copy, lossless) ─────────────────────────
    # ProRes 4444 chunks share identical codec parameters (resolution, fps,
    # profile, pixel format, color space) since they all came from the same
    # composition spec — concat demuxer can stream-copy them with zero
    # quality loss in <1s.
    if _overlay_chunked:
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

    print(f"[render] All Remotion renders done in {_render_elapsed:.1f}s", flush=True)

    # Validate v62 Remotion outputs (always produced — blend mode no longer
    # bypasses these; it adds a second pass on top of the v62 result).
    if not os.path.exists(overlay_video_path) or os.path.getsize(overlay_video_path) < 1000:
        raise RuntimeError(f"PromptlyOverlay output missing/invalid: {overlay_video_path}")
    if micro_input is not None and (
        not os.path.exists(micro_video_path) or os.path.getsize(micro_video_path) < 1000
    ):
        raise RuntimeError(f"PromptlyMicroSegments output missing/invalid: {micro_video_path}")

    # ── Chunked composite (4-way parallel ffmpeg) ─────────────────────────
    # The single-pass final-mux step was a libx264-encode-bound bottleneck
    # (22.9s for 1363 frames on 64 vCPUs). Splitting the work into 4 parallel
    # ffmpeg invocations on the same container — each producing one mp4
    # piece for 1/4 of the timeline — gives each piece its own encoder
    # thread pool. Lossless concat (`-c copy`) stitches the pieces and a
    # final stream-copy pass muxes the audio.
    #
    # Quality identical: same libx264 ultrafast crf 18 settings per piece;
    # concat is bit-exact, audio mux is stream-copy. The slicer
    # (slice_timeline_for_chunk) shifts zoom events with their full
    # original duration preserved, so easing curves stay smooth across
    # chunk boundaries (verified pixel-exact at boundary frames).
    #
    # For very short outputs (<400 frames) the per-process startup tax
    # dominates — fall back to single-pass.
    _N_COMPOSITE_CHUNKS = 4 if total_output_frames >= 400 else 1
    _composite_ranges = split_timeline_into_chunks(int(total_output_frames), _N_COMPOSITE_CHUNKS)
    _composite_chunked = len(_composite_ranges) > 1

    def _build_composite_cmd(
        chunk_idx: int,
        chunk_start: int,
        chunk_end: int,
        output_path_for_chunk: str,
        include_audio: bool,
    ) -> list:
        """Construct a single ffmpeg command for one composite chunk.
        When include_audio=True, the audio track is muxed in the same pass
        (used by the single-chunk fallback path)."""
        if _composite_chunked:
            _c_clips, _c_trans, _c_broll, _c_micro = slice_timeline_for_chunk(
                chunk_start, chunk_end, clips_out, transitions_out,
                broll_out, micro_segments_meta, source_fps,
            )
        else:
            _c_clips = clips_out
            _c_trans = transitions_out
            _c_broll = broll_out
            _c_micro = micro_segments_meta

        # Build inputs for THIS chunk. Source + overlay are always present;
        # micro is only present if any sliced segment is remotion-rendered
        # OR there's a transition in this chunk (transitions always live in
        # micro_segments). broll inputs only include the broll files
        # visible in this chunk.
        chunk_inputs = [source_path]
        c_source_idx = 0
        c_micro_idx = None
        c_micro_needed = (
            micro_input is not None and len(_c_micro) > 0
        )
        if c_micro_needed:
            chunk_inputs.append(micro_video_path)
            c_micro_idx = len(chunk_inputs) - 1
        # Overlay is included for every chunk — captions span the full
        # video and the filtergraph trims to this chunk's frame range.
        chunk_inputs.append(overlay_video_path)
        c_overlay_idx = len(chunk_inputs) - 1
        c_broll_start_idx = None
        if _c_broll:
            c_broll_start_idx = len(chunk_inputs)
            for _br in _c_broll:
                chunk_inputs.append(_br["src"])
        c_audio_idx = None
        if include_audio:
            c_audio_idx = len(chunk_inputs)
            chunk_inputs.append(_final_audio_path)

        chunk_size = chunk_end - chunk_start
        _fg, _final_labels = build_final_filtergraph(
            clips=_c_clips,
            transitions=_c_trans,
            broll=_c_broll,
            micro_segments=_c_micro,
            outro=_outro,
            total_output_frames=chunk_size,
            source_fps=source_fps,
            source_input_idx=c_source_idx,
            micro_input_idx=c_micro_idx,
            overlay_input_idx=c_overlay_idx,
            broll_input_start_idx=c_broll_start_idx,
            chunk_global_start_frame=(chunk_start if _composite_chunked else None),
            global_total_frames=int(total_output_frames),
        )

        cmd = ["ffmpeg", "-y", "-v", "warning", "-threads", "0"]
        for _inp in chunk_inputs:
            cmd += ["-i", _inp]
        cmd += [
            "-filter_complex", _fg,
            "-map", f"[{_final_labels[0]}]",
        ]
        if include_audio and c_audio_idx is not None:
            cmd += ["-map", f"{c_audio_idx}:a:0", "-c:a", "copy"]
        cmd += [
            # `veryfast` preset replaces `ultrafast`. ultrafast disables
            # CABAC entropy coding, B-frames, deblocking filter, and
            # advanced motion estimation — at a capped 8M bitrate that
            # produces visible blocking, banding, and motion noise (the
            # "static" + "10fps look" users were reporting). veryfast
            # enables all of those at ~2-3× the encode time, which the
            # H100 absorbs trivially since chunks run in parallel.
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            # Force constant frame rate at the output stage. Filter
            # graphs with speed-ramps produce non-uniform PTS — VFR
            # output then makes AVPlayer's display loop look juddery
            # on some devices. Targeting source_fps duplicates frames
            # during slow-mo (fine) and the source is often 60fps so
            # fast-mo segments don't lose detail.
            "-fps_mode", "cfr", "-r", str(int(round(source_fps))),
            # 14M / 28M cap for 1080p60. The previous 8M ceiling was below
            # the floor for this resolution+framerate — VBV-clamped libx264
            # could not hold detail through speed ramps, hard cuts, zoom
            # regions, or B-roll overlays, producing the visible blocking +
            # banding ("static") that users reported. 14M sits comfortably
            # under iOS Level 4.1's 50M ceiling and is in line with TikTok's
            # 1080p60 upload spec. CRF 18 is still the rate driver; the cap
            # is just a safety lid.
            "-maxrate", "14M", "-bufsize", "28M",
            # High Profile + Level 4.1 = max compatibility for iOS
            # AVPlayer / web HLS without limiting quality.
            "-profile:v", "high", "-level:v", "4.1",
            "-pix_fmt", "yuv420p",
            # Force dense keyframes on every chunk so concat -c copy joins
            # cleanly without GOP-boundary glitches.
            "-g", str(int(round(source_fps))),
            "-keyint_min", str(int(round(source_fps))),
            "-sc_threshold", "0",
            "-shortest",
            "-movflags", "+faststart",
            output_path_for_chunk,
        ]
        return cmd

    _mux_t0 = time.time()
    _silent_full = os.path.join(work_dir, "silent_full.mp4")

    if _composite_chunked:
        # ── Spawn N parallel ffmpeg processes for the silent video pieces ──
        _composite_chunk_paths = [
            os.path.join(work_dir, f"composite_chunk_{_i:02d}.mp4")
            for _i in range(len(_composite_ranges))
        ]
        _composite_cmds = [
            (
                f"composite-{_i:02d}",
                _build_composite_cmd(
                    _i, _cs, _ce, _composite_chunk_paths[_i], include_audio=False,
                ),
            )
            for _i, (_cs, _ce) in enumerate(_composite_ranges)
        ]

        def _run_ffmpeg_chunk(label, cmd):
            _t0 = time.time()
            # Composite chunks may include minterpolate on B-roll inputs
            # when broll fps < output fps. With several B-rolls in a
            # chunk, minterpolate cost can reach ~60-90s; 600s gives
            # ample headroom while still failing loud on a stuck chunk.
            _r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            _e = time.time() - _t0
            if _r.returncode != 0:
                raise RuntimeError(
                    f"[{label}] composite ffmpeg failed (rc={_r.returncode}) in "
                    f"{_e:.1f}s: {(_r.stderr or '')[-1500:]}"
                )
            return _e

        print(
            f"[render] Spawning {len(_composite_cmds)} parallel composite ffmpegs "
            f"({total_output_frames} frames split {len(_composite_ranges)}-ways)",
            flush=True,
        )
        _composite_pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(_composite_cmds))
        _composite_futures = [
            _composite_pool.submit(_run_ffmpeg_chunk, _lbl, _cmd)
            for _lbl, _cmd in _composite_cmds
        ]
        _composite_chunk_elapsed = []
        for _ci, _f in enumerate(_composite_futures):
            _e = _f.result(timeout=320)
            _composite_chunk_elapsed.append(_e)
            _path = _composite_chunk_paths[_ci]
            print(
                f"[render] composite-{_ci:02d} done in {_e:.1f}s → "
                f"{os.path.getsize(_path)/1024/1024:.1f}MB",
                flush=True,
            )
        _composite_pool.shutdown(wait=False)

        # Concat the silent pieces (lossless `-c copy`).
        _cc_list = os.path.join(work_dir, "_composite_concat_list.txt")
        with open(_cc_list, "w") as _lf:
            for _p in _composite_chunk_paths:
                _lf.write(f"file '{_p}'\n")
        _cc_t0 = time.time()
        _cc_r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-f", "concat", "-safe", "0",
             "-i", _cc_list,
             "-c", "copy",
             _silent_full],
            capture_output=True, text=True, timeout=120,
        )
        if _cc_r.returncode != 0:
            raise RuntimeError(
                f"Composite chunk concat failed (rc={_cc_r.returncode}): "
                f"{(_cc_r.stderr or '')[-1500:]}"
            )
        _cc_elapsed = time.time() - _cc_t0
        _max_chunk = max(_composite_chunk_elapsed)
        print(
            f"[render] Composite: max chunk={_max_chunk:.1f}s, concat={_cc_elapsed:.1f}s",
            flush=True,
        )
    else:
        # Single-pass for short outputs (<400 frames). Always produces a
        # silent intermediate so the downstream blend-captions / audio-mux
        # steps share the same shape as the chunked path.
        _single_cmd = _build_composite_cmd(
            0, 0, int(total_output_frames), _silent_full, include_audio=False,
        )
        _r = subprocess.run(_single_cmd, capture_output=True, text=True, timeout=300)
        if _r.returncode != 0:
            raise RuntimeError(f"Final composite failed: {(_r.stderr or '')[-1500:]}")

    if not os.path.exists(_silent_full) or os.path.getsize(_silent_full) < 1000:
        raise RuntimeError(f"Silent intermediate missing/invalid: {_silent_full}")

    # ── Blend-mode second pass ────────────────────────────────────────────
    # For blend captions (GlitchHighlight / NegativeFlash / Prism), v62 has
    # produced the full video without those captions. Stage the silent
    # intermediate into the bundle public root, run PromptlyBlendCaptionsOnly
    # to draw blend captions + caption_match overlays on top with the
    # existing mixBlendMode CSS against real frame content, and use the
    # output of THAT pass as the source for the final audio mux.
    _audio_source_video = _silent_full
    _blend_pass_elapsed = 0.0
    if _is_blend_render:
        _blend_t0 = time.time()
        _blend_video_basename = _stage_file(_silent_full)
        blend_captions_input["videoUrl"] = _blend_video_basename
        blend_captions_input_path = os.path.join(_stage_dir, "blend_captions_input.json")
        _validate_and_write_render_input(
            "blend-captions",
            blend_captions_input,
            _SchemaBlendCaptionsInput,
            blend_captions_input_path,
        )
        _blend_captions_video = os.path.join(work_dir, "blend_captions.mp4")

        # Chunk the blend captions pass the same way the overlay pass is
        # chunked. A single Remotion process hits a documented ~16-22 fps
        # ceiling on H100 (issue #4664) regardless of vCPU count — main-
        # thread + encoder serialization, not paint cost. 4 separate
        # processes each get their own ceiling, so aggregate fps scales
        # nearly linearly. For long videos this collapses the blend pass
        # from ~195s (single process, 2865 frames) to ~50s (4-way parallel).
        # Below 300 frames the per-process startup tax (~3.5s) dominates
        # — single process is faster.
        _BLEND_CHUNK_COUNT = 4 if total_output_frames >= 300 else 1
        _blend_ranges = _split_frames(int(total_output_frames), _BLEND_CHUNK_COUNT)
        _blend_chunked = len(_blend_ranges) > 1

        if _blend_chunked:
            _blend_chunk_paths = [
                os.path.join(work_dir, f"blend_captions_chunk_{_i:02d}.mp4")
                for _i in range(len(_blend_ranges))
            ]
            _blend_cmds = []
            for _i, (_fs, _fe) in enumerate(_blend_ranges):
                _blend_cmds.append((
                    f"blend-captions-{_i:02d}",
                    [
                        "node", "/remotion/render-full.mjs",
                        "--input", blend_captions_input_path,
                        "--output", _blend_chunk_paths[_i],
                        "--public-dir", _bundle_public_root,
                        "--composition", "PromptlyBlendCaptionsOnly",
                        "--gl", _gl_mode,
                        "--frame-range", f"{_fs},{_fe}",
                        "--composition-start", str(_fs),
                        "--concurrency", str(_PER_CHUNK_CONCURRENCY),
                    ],
                ))
            print(
                f"[render] Spawning {len(_blend_cmds)} blend-captions chunk subprocesses "
                f"({total_output_frames} frames split {len(_blend_ranges)}-ways, "
                f"concurrency={_PER_CHUNK_CONCURRENCY} each)",
                flush=True,
            )
            _blend_pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(_blend_cmds))
            _blend_futures = [
                _blend_pool.submit(_run_remotion, _lbl, _cmd)
                for _lbl, _cmd in _blend_cmds
            ]
            _blend_chunk_elapsed = []
            for _bi, _f in enumerate(_blend_futures):
                _e = _f.result(timeout=400)
                _blend_chunk_elapsed.append(_e)
                _path = _blend_chunk_paths[_bi]
                if not os.path.exists(_path) or os.path.getsize(_path) < 1000:
                    raise RuntimeError(
                        f"blend-captions chunk {_bi} output missing/invalid: {_path}"
                    )
                print(
                    f"[render] blend-captions-{_bi:02d} done in {_e:.1f}s → "
                    f"{os.path.getsize(_path)/1024/1024:.1f}MB",
                    flush=True,
                )
            _blend_pool.shutdown(wait=False)

            # Lossless concat of the h264 chunks. The chunks share identical
            # codec parameters (same composition spec, same Remotion render
            # config), and the dense GOP (1 keyframe/sec) means the concat
            # demuxer can stream-copy them with zero quality loss.
            _bc_list = os.path.join(work_dir, "_blend_captions_concat_list.txt")
            with open(_bc_list, "w") as _lf:
                for _p in _blend_chunk_paths:
                    _lf.write(f"file '{_p}'\n")
            _bc_t0 = time.time()
            _bc_r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error",
                 "-f", "concat", "-safe", "0",
                 "-i", _bc_list,
                 "-c", "copy",
                 _blend_captions_video],
                capture_output=True, text=True, timeout=120,
            )
            if _bc_r.returncode != 0:
                raise RuntimeError(
                    f"blend-captions chunk concat failed (rc={_bc_r.returncode}): "
                    f"{(_bc_r.stderr or '')[-1500:]}"
                )
            _bc_concat_elapsed = time.time() - _bc_t0
            _max_bc_chunk = max(_blend_chunk_elapsed)
            print(
                f"[render] blend-captions: max chunk={_max_bc_chunk:.1f}s, "
                f"concat={_bc_concat_elapsed:.1f}s",
                flush=True,
            )
        else:
            # Single-process for very short outputs (<300 frames).
            _blend_cmd = [
                "node", "/remotion/render-full.mjs",
                "--input", blend_captions_input_path,
                "--output", _blend_captions_video,
                "--public-dir", _bundle_public_root,
                "--composition", "PromptlyBlendCaptionsOnly",
                "--gl", _gl_mode,
            ]
            _run_remotion("blend-captions", _blend_cmd)

        if (
            not os.path.exists(_blend_captions_video)
            or os.path.getsize(_blend_captions_video) < 1000
        ):
            raise RuntimeError(
                f"PromptlyBlendCaptionsOnly output missing/invalid: {_blend_captions_video}"
            )
        _audio_source_video = _blend_captions_video
        _blend_pass_elapsed = time.time() - _blend_t0
        print(
            f"[render] PromptlyBlendCaptionsOnly done in {_blend_pass_elapsed:.1f}s → "
            f"{os.path.getsize(_blend_captions_video)/1024/1024:.1f}MB",
            flush=True,
        )

    # ── Final audio mux: stream-copy silent video + AAC audio → output ────
    _am_t0 = time.time()
    _am_r = subprocess.run(
        ["ffmpeg", "-y", "-v", "warning",
         "-i", _audio_source_video,
         "-i", _final_audio_path,
         "-c:v", "copy",
         "-c:a", "copy",
         "-shortest",
         "-movflags", "+faststart",
         output_path],
        capture_output=True, text=True, timeout=120,
    )
    if _am_r.returncode != 0:
        raise RuntimeError(
            f"Audio mux failed (rc={_am_r.returncode}): "
            f"{(_am_r.stderr or '')[-1500:]}"
        )
    _am_elapsed = time.time() - _am_t0

    _mux_elapsed = time.time() - _mux_t0
    print(
        f"[render] Final composite (clips+broll+overlay+encode"
        f"{'+blend-captions' if _is_blend_render else ''}+audio) done in {_mux_elapsed:.1f}s "
        f"(audio mux={_am_elapsed:.1f}s)",
        flush=True,
    )
    print(
        f"[render] Total render: remotion={_render_elapsed:.1f}s audio={_audio_elapsed:.1f}s "
        f"composite={_mux_elapsed:.1f}s → {os.path.getsize(output_path)/1024/1024:.1f}MB",
        flush=True,
    )

    # ── A/V sync verification — fail loud on drift > 20 ms ─────────────
    # The pipeline is engineered for sample-accurate A/V alignment:
    # video frame count and audio sample count both derive from the same
    # per-cut effective durations, with transitions accounted for in
    # both pipelines. After mux, the rendered file's video and audio
    # stream durations should match within ~1 frame (16.7 ms at 60fps).
    # Anything beyond 20 ms indicates a structural drift bug — log it
    # loudly so it shows up in production logs immediately, not three
    # bug reports later.
    try:
        _final_probe = _probe_full(output_path)
        _final_streams = _final_probe.get("streams") or []
        _final_v = next((s for s in _final_streams if s.get("codec_type") == "video"), {})
        _final_a = next((s for s in _final_streams if s.get("codec_type") == "audio"), {})
        _v_dur = float(_final_v.get("duration") or 0.0)
        _a_dur = float(_final_a.get("duration") or 0.0)
        _av_drift_ms = (_v_dur - _a_dur) * 1000.0
        _expected_dur = total_output_frames / float(source_fps)
        _v_drift_vs_expected_ms = (_v_dur - _expected_dur) * 1000.0
        print(
            f"[av-sync] video={_v_dur:.4f}s audio={_a_dur:.4f}s "
            f"v−a={_av_drift_ms:+.2f}ms  v−expected={_v_drift_vs_expected_ms:+.2f}ms "
            f"(expected={_expected_dur:.4f}s, target ≤±20ms)",
            flush=True,
        )
        if abs(_av_drift_ms) > 20.0:
            print(
                f"[av-sync] WARNING: A/V drift {_av_drift_ms:+.2f}ms exceeds 20ms target. "
                f"Audio and video stream durations don't match — investigate cuts, "
                f"transitions, audio extraction, or composite filtergraph.",
                flush=True,
            )
    except Exception as _av_e:
        print(f"[av-sync] sync probe skipped: {_av_e}", flush=True)

    # Cleanup staged files in the bundle public root so it doesn't pile up.
    # work_dir itself is cleaned up by the caller (handler() in the finally
    # block), so input JSONs there get freed automatically.
    for _staged_path in _staged_for_cleanup:
        try:
            if os.path.lexists(_staged_path):
                os.unlink(_staged_path)
        except Exception as _rm_err:
            print(f"[render] WARNING: stage cleanup failed for {_staged_path}: {_rm_err}", flush=True)


# ─── CAPTION / COMPONENT VOCABULARIES (enforced at validation + render time) ───

VALID_CAPTION_STYLES = {
    "PaperII",
    "Prime", "TypewriterReveal", "CinematicLetterpress", "Cove",
    "EditorialPop", "Illuminate", "Lumen",
    "MagazineCutout", "Passage", "Pulse", "Quintessence", "Serif",
    "GlitchHighlight", "NegativeFlash", "Prism",
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
    "AnnotationArrow", "ChatThread",
    "Notification", "ProgressBar", "QuoteCard", "RecordingFrame",
    "StatCard", "StickyNotes", "Toggle", "TornPaper",
    "TweetBubble", "InstagramComment", "IMessageBubble", "TikTokComment",
}


def _build_tiktok_pages_from_projected(projected_words, max_words_per_page=3, position_boundaries_sec=None):
    """Convert projected Deepgram words into TikTokPage[] structured for the
    @remotion/captions types consumed by the pack caption components.

    Each page covers up to `max_words_per_page` consecutive words. Page
    boundaries break on:
      - large gaps (>0.6s)
      - sentence-end punctuation
      - position-change boundaries (so a page never spans top→bottom etc.;
        if it did, the page would be assigned by midpoint to one position
        and visually drift relative to its actual time range)

    `position_boundaries_sec` is an optional sorted list of output-time
    seconds where the caption position changes. Pages are flushed when
    crossing one.
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

    for w in projected_words:
        w_start = float(w.get("start") or 0)
        w_end = float(w.get("end") or w_start)
        w_text = w.get("punctuated_word") or w.get("word") or ""
        if not w_text.strip():
            continue
        # Break on big gap OR position-change boundary
        if current_tokens and last_word_end is not None:
            if w_start - last_word_end > 0.6:
                _flush()
            elif _crosses_boundary(last_word_end, w_start):
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
    # PaperII / TypewriterReveal / CinematicLetterpress / MagazineCutout /
    # Quintessence don't highlight specific words — their effect is
    # style-driven (typewriter sweep, cutout collage, etc.) — so they're
    # omitted from this map. NegativeFlash and Prism DO take a keywords
    # list, but they consume it via the caption.keywords field that
    # PromptlyRender passes as a top-level prop directly to every caption
    # component, so they don't need a per-style entry here either.
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
    # Styles that expect [{text, preset?}] entries (GlitchHighlight). The
    # color preset is global; per-word preset is rare so we emit just text.
    if style == "GlitchHighlight" and kw_list and "highlightWords" not in out:
        out["highlightWords"] = [{"text": w} for w in kw_list]

    if style in simple_keyword_prop:
        prop_name = simple_keyword_prop[style]
        if kw_list and prop_name not in out:
            out[prop_name] = kw_list
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
        transcript_cache = os.path.join(cache_dir, "transcript.json")

        source_hit = os.path.exists(source_cache) and os.path.getsize(source_cache) > 1024
        transcript_hit = os.path.exists(transcript_cache) and os.path.getsize(transcript_cache) > 2

        if source_hit and transcript_hit:
            size_mb = os.path.getsize(source_cache) / (1024 * 1024)
            print(f"[prewarm] FULL HIT {cache_key} ({size_mb:.1f}MB source + transcript)", flush=True)
            return {"status": "cached", "cache_key": cache_key, "size_mb": round(size_mb, 1)}

        os.makedirs(cache_dir, exist_ok=True)

        # iOS fires prewarm as soon as the eventual S3 URL is known
        # (right after multipart-init), which can be well before the
        # upload has completed. Poll HEAD for the object to appear
        # before trying to download. This lets Deepgram + source
        # download start within milliseconds of upload-complete instead
        # of waiting for a separate client-side "now fire prewarm"
        # roundtrip — usually saves 10-15s of post-send latency.
        poll_start = time.time()
        poll_deadline = poll_start + 180
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
                if now >= poll_deadline:
                    code = getattr(head_err, 'response', {}).get('Error', {}).get('Code', 'unknown')
                    print(f"[prewarm] timed out waiting for S3 object after "
                          f"{now - poll_start:.1f}s (last={code})", flush=True)
                    return {"error": "s3 object never materialized", "cache_key": cache_key}
                # Adaptive backoff: poll fast while upload is plausibly
                # almost done, back off as time passes so we don't hammer
                # HEAD requests on huge slow uploads.
                elapsed = now - poll_start
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
            """Canonicalize source to 1080×1920 60fps CFR yuv420p.

            Single ingest pass that produces the ONE canonical shape every
            downstream module operates against. Replaces the prior dual-pass
            arrangement (a separate fps-only step, then a second scale/crop
            pass at the start of render_multi_clip).

            Routes:
              * Source already >=60fps -> plain ffmpeg pass with fps=60
                plus the analyze-derived normalize_vf (face-aware crop or
                center-crop) folded into a single filter chain. No frame
                synthesis cost.
              * Source <60fps -> RIFE 4.18 on H100 GPU via
                /rife_normalize.py for motion-compensated frame synthesis,
                then a second ffmpeg pass that applies normalize_vf and
                pix_fmt = yuv420p. Two passes is unavoidable: RIFE outputs
                its own mp4 and we don't want RIFE to know about cropping.

            Awaits future_normalize so it can read the analyze-derived
            normalize_vf. analyze typically finishes in 2-5s; the await is
            negligible against the ~30s normalize cost.

            Output: source_canonical.mp4 (1080x1920 60fps yuv420p h264
            ultrafast crf 18, 1-keyframe-per-second GOP for fast seeks).
            """
            _shape = future_normalize.result()
            _normalize_vf = _shape.get("normalize_vf")

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
            _r_val = _parse_rate(_r_rate_str)
            _src_fps_estimate = _avg or _r_val or 30.0

            _norm_t0 = time.time()
            _norm_path = os.path.join(work_dir, "source_canonical.mp4")

            # Compose the filter chain. fps=60 + (optional) scale/crop
            # + setsar=1 + final pix_fmt-yuv420p output. When normalize_vf
            # is None the source is already 1080x1920 so we just do fps
            # conversion and a yuv420p re-encode for downstream uniformity.
            _vf_parts = ["fps=60"]
            if _normalize_vf:
                _vf_parts.append(_normalize_vf)
            _vf_combined = ",".join(_vf_parts)

            if _src_fps_estimate >= 59.5:
                # Source already at or above target — plain fps filter +
                # normalize_vf in a single pass.
                _interp_mode = "fps-only"
                _r_out = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-threads", "0",
                     "-i", _raw_source,
                     "-vf", _vf_combined,
                     "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                     "-pix_fmt", "yuv420p",
                     "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
                     "-c:a", "copy",
                     "-video_track_timescale", "90000",
                     _norm_path],
                    capture_output=True, text=True, timeout=180,
                )
                if _r_out.returncode != 0 or not os.path.exists(_norm_path):
                    raise RuntimeError(
                        f"Source canonicalize (fps-only) failed: "
                        f"{(_r_out.stderr or '')[-500:]}"
                    )
            else:
                # Source below target — RIFE 4.18 first to bring fps to 60
                # at original resolution, then ffmpeg pass to scale/crop
                # to 1080x1920 yuv420p.
                _interp_mode = "rife-4.18"
                _rife_out = os.path.join(work_dir, "_rife_60fps.mp4")
                _r_out = subprocess.run(
                    ["python", "/rife_normalize.py",
                     "--input", _raw_source,
                     "--output", _rife_out,
                     "--target-fps", "60",
                     "--rife-dir", "/opt/rife"],
                    capture_output=True, text=True, timeout=480,
                )
                if _r_out.returncode != 0 or not os.path.exists(_rife_out):
                    raise RuntimeError(
                        f"Source canonicalize (RIFE) failed: "
                        f"stderr={(_r_out.stderr or '')[-1000:]} "
                        f"stdout={(_r_out.stdout or '')[-500:]}"
                    )
                # Forward RIFE's progress lines so they appear in job logs.
                for _line in (_r_out.stdout or "").splitlines():
                    if _line.startswith("[rife]"):
                        print(_line, flush=True)
                if _normalize_vf:
                    # Source needs scale/crop on top of RIFE's 60fps output.
                    # One ffmpeg pass: apply normalize_vf + yuv420p re-encode.
                    _scale_r = subprocess.run(
                        ["ffmpeg", "-y", "-v", "error", "-threads", "0",
                         "-i", _rife_out,
                         "-vf", _normalize_vf,
                         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                         "-pix_fmt", "yuv420p",
                         "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
                         "-c:a", "copy",
                         "-video_track_timescale", "90000",
                         _norm_path],
                        capture_output=True, text=True, timeout=180,
                    )
                    if _scale_r.returncode != 0 or not os.path.exists(_norm_path):
                        raise RuntimeError(
                            f"Source canonicalize (post-RIFE scale) failed: "
                            f"{(_scale_r.stderr or '')[-500:]}"
                        )
                    try:
                        os.remove(_rife_out)
                    except OSError:
                        pass
                else:
                    # Source is already 1080x1920 — RIFE already produced
                    # h264 yuv420p at the canonical resolution. Just rename
                    # the file; a second ffmpeg pass would be ~10-15s of
                    # pure waste (re-encoding bit-identical pixels).
                    os.rename(_rife_out, _norm_path)

            _size_mb = os.path.getsize(_norm_path) / (1024 * 1024)
            print(
                f"[fps-normalize] Converted r={_r_val:.4f}fps avg={_avg:.4f}fps "
                f"-> 60.0000fps CFR ({_interp_mode}) in {time.time() - _norm_t0:.1f}s "
                f"({_size_mb:.1f}MB)",
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
                            f"will be slow despite -g 30. v49 didn't take.",
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
                _refined_tx_cache["value"] = _t
                return _t

        def _do_edit_recipe_overlapped():
            """Start Gemini as soon as transcript + proxy + trend + audio + face signals are ready.
            Transcript may come from the early_pool URL-based Deepgram call (ran in parallel
            with the download), a regular mega-pool file-based call, or the provided_transcript
            for re-edit paths. Whichever landed first wins."""
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
        # Resolve transcript through the shared resolver. The edit-recipe
        # consumer already triggered this; here we retrieve the cached value.
        transcript = _get_resolved_transcript()
        if not (future_url_transcript is not None or future_transcribe is not None):
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
        # Swap in the 60fps-normalized source for render. fps_normalize ran in
        # parallel with Gemini so this is already done by the time we get here.
        # Downstream render detects source_fps=60.0 from the new file's r_frame_rate
        # and all frame-count math becomes exact.
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
        t = time.time()
        render_multi_clip(
            source_path, edit_plan["cuts"], edit_plan, output_path, transcript, work_dir,
            broll_clips=broll_clips,
        )
        edit_plan["_deepgram_words"] = transcript.get("words", [])

        render_elapsed = time.time() - t
        _timings["render"] = render_elapsed
        print(f"[pipeline] parallel_render complete in {render_elapsed:.1f}s", flush=True)
        _enc_label = "NVENC" if _HAS_NVENC else "libx264/ultrafast threads=auto"
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
            # Direct SDK upload to S3 — faster than presigned URL PUT.
            # CloudFront serves the content via CDN.
            _s3_bucket = os.environ.get("S3_BUCKET_NAME", "")
            _cf_domain = os.environ.get("CLOUDFRONT_DOMAIN", "")
            # Single deterministic upload path. The Node.js dispatcher
            # always pre-generates a presigned PUT URL targeting the
            # bucket's `renders/{jobId}/{ts}-edited.mp4` key. If it
            # didn't, fail loudly — no direct-SDK fallback to a
            # different prefix that may not be covered by CloudFront
            # origin access.
            if not upload_url:
                raise RuntimeError("No upload_url provided — Node dispatcher must pre-generate the presigned PUT URL")
            with open(output_path, "rb") as f:
                resp = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": "video/mp4"},
                    timeout=600,
                )
                resp.raise_for_status()
            if input_data.get("public_url"):
                _video_url = input_data["public_url"]
            else:
                _video_url = upload_url.split("?")[0]
            print(f"[pipeline] upload complete (presigned-put → {_video_url})", flush=True)
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
