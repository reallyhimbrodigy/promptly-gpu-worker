"""adapter_contract.py — the input-adapter contract (LANE-SEAM Step 1, 2026-08-09).

THE SOCKET. Every input type the product accepts resolves to ONE normalized
envelope before it reaches the editorial core:

    {user_text, attachments[], user_context}  →  SourceEnvelope{
        footage_refs[]   — the footage the plan may draw pixels from
        word_timings[]   — the resolved word list (Deepgram format), the
                           pipeline's one clock; None when no speech exists
        intent_hints{}   — free-text + structured intent (vibe, change_request,
                           user_context) — NEVER a tool allowlist (router
                           conservatism law: guidance, not capability)
        source_kind      — which adapter produced this envelope
    }

Adapter #1 (single_video) is LIVE behind PROMPTLY_ADAPTER_V1 and is an
IDENTITY CARRIER: `core_inputs()` returns the very same objects that were
passed in (is-identity, certified by cert_adapter_contract.py), so routing the
current path through the contract cannot change a plan byte. Adapters #2/#3
are documented stubs — capability lanes fill them; this file defines the
socket, not the capabilities.

Flag: PROMPTLY_ADAPTER_V1 (env, dark) or per-job input_data.adapter_v1_test —
exactly the burned_text_test / zero_reject_test pattern (inert for real
traffic). Flag OFF ⇒ handler never calls into this module at plan time.

Python 3.9-compatible (modal CLI constraint): no `X | Y` unions.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

SINGLE_VIDEO = "single_video"
MULTI_CLIP = "multi_clip"
IMAGE_STILL = "image_still"

_SOURCE_KINDS = (SINGLE_VIDEO, MULTI_CLIP, IMAGE_STILL)


def enabled(input_data=None):
    """DARK by default. PROMPTLY_ADAPTER_V1=1 routes the single-video path
    through the contract globally; input_data.adapter_v1_test is the per-job
    override for the pre-flip cert (inert for real traffic — the app never
    sets it)."""
    if input_data and input_data.get("adapter_v1_test"):
        return True
    return os.environ.get("PROMPTLY_ADAPTER_V1", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


@dataclass
class FootageRef:
    """One piece of footage the plan may draw pixels from.

    local_path — container-local file the pipeline reads (the ONLY field the
                 single-video core consumes today; render is already
                 clip-addressed via ClipSpec.src / clipASrc / clipBSrc).
    kind       — "video" | "image".
    duration_s — measured duration (0.0 for stills).
    source_url — where it came from (S3/user), provenance only.
    role       — "primary" | "supplementary"; adapter #1 has exactly one
                 primary and nothing else.
    """
    local_path: str
    kind: str = "video"
    duration_s: float = 0.0
    source_url: Optional[str] = None
    role: str = "primary"


@dataclass
class SourceEnvelope:
    """The normalized input every adapter resolves to. The editorial core's
    functional minimum (video_path + vibe + duration + deepgram_words, per
    generate_edit_gemini's real signature) reads straight off this shape."""
    source_kind: str
    footage_refs: List[FootageRef]
    word_timings: Optional[List[dict]] = None
    intent_hints: Dict[str, Any] = field(default_factory=dict)
    # MULTI_CLIP only. The editorial core reads ONE video on ONE clock; N clips
    # therefore resolve to a stitched file, and word_timings are re-clocked onto
    # that same timeline. Keeping it on the envelope (rather than passing a
    # second path alongside) is what stops a second clock existing at all — the
    # class the shared-clock law exists to prevent. None for every other kind.
    stitched_path: Optional[str] = None


def adapt_single_video(user_text, attachments, user_context=None,
                       word_timings=None):
    """Adapter #1 — the current product: ONE user talking-head video.

    attachments: list of exactly one FootageRef(kind="video") whose
    local_path is the downloaded source the pipeline already holds.
    word_timings: the resolved Deepgram word list — passed through UNTOUCHED
    (same object), because it is the pipeline's index-space clock and any
    copy/transform here would be a second clock (the class of bug the
    shared-clock law exists to prevent).

    Raises ValueError on structural violation; the caller catches LOUDLY and
    falls back to the raw path (degrade allowed, silence is not).
    """
    if not attachments or len(attachments) != 1:
        raise ValueError(
            "adapter #1 takes exactly one attachment, got %r" % (
                0 if not attachments else len(attachments)))
    ref = attachments[0]
    if not isinstance(ref, FootageRef):
        raise ValueError("attachment must be a FootageRef, got %s"
                         % type(ref).__name__)
    if ref.kind != "video" or not ref.local_path:
        raise ValueError("adapter #1 needs one local video path")
    if not (ref.duration_s and ref.duration_s > 0):
        raise ValueError("adapter #1 needs a measured positive duration, got %r"
                         % (ref.duration_s,))
    hints = dict(user_context or {})
    hints["vibe"] = user_text
    return SourceEnvelope(
        source_kind=SINGLE_VIDEO,
        footage_refs=[ref],
        word_timings=word_timings,
        intent_hints=hints,
    )


def core_inputs(envelope):
    """SourceEnvelope → the editorial core's functional-minimum inputs, as
    (video_path, vibe, duration, deepgram_words).

    IDENTITY GUARANTEE: every returned value is the same object that entered
    the envelope — this function maps, it never transforms. That guarantee is
    what makes flag-ON provably plan-identical for adapter #1, and it is
    asserted by cert_adapter_contract.py (Rule 1: the check that makes the
    regression impossible).
    """
    if not isinstance(envelope, SourceEnvelope):
        raise ValueError("core_inputs needs a SourceEnvelope")
    if envelope.source_kind not in _SOURCE_KINDS:
        raise ValueError("unknown source_kind %r" % (envelope.source_kind,))
    if envelope.source_kind == MULTI_CLIP:
        # ONE video, ONE clock. The core is handed the stitched file and the
        # re-clocked word list; footage_refs keeps all N so the clip-addressed
        # render layer can still reach the originals.
        if not envelope.stitched_path:
            raise ValueError(
                "multi_clip envelope has no stitched_path — concat must run "
                "before the core reads it (adapter #2 resolution contract)")
        return (envelope.stitched_path,
                envelope.intent_hints.get("vibe"),
                sum(float(r.duration_s or 0.0) for r in envelope.footage_refs),
                envelope.word_timings)
    if envelope.source_kind != SINGLE_VIDEO:
        raise NotImplementedError(
            "core_inputs maps adapters #1 and #2; %s lands with its "
            "adapter" % envelope.source_kind)
    primary = envelope.footage_refs[0]
    return (primary.local_path,
            envelope.intent_hints.get("vibe"),
            primary.duration_s,
            envelope.word_timings)


# ── Adapter #2 — MULTI-CLIP (stub; socket defined, capability lane fills) ────
def adapt_multi_clip(user_text, attachments, user_context=None,
                     word_timings_per_clip=None, stitched_path=None):
    """Adapter #2 — N ordered user clips → one envelope.

    Input signature (frozen now so the capability lane builds to it):
      attachments            — List[FootageRef], length ≥ 2, order = timeline
                               order; each kind="video" with a measured
                               duration_s.
      word_timings_per_clip  — Optional[List[Optional[List[dict]]]] parallel
                               to attachments (a silent clip is None).
    Resolution contract: footage_refs keeps ALL N refs (the render layer is
    already clip-addressed — ClipSpec.src, clipASrc/clipBSrc, and the dormant
    _download_and_concat_sources collapse exists as a fallback); word_timings
    becomes ONE concatenated list re-clocked to the stitched timeline with
    per-word provenance {"_clip_index": i} so plan word-indices stay a single
    index space. intent_hints/source_kind as adapter #1, source_kind=MULTI_CLIP.
    """
    if not attachments or len(attachments) < 2:
        raise ValueError(
            "adapter #2 takes two or more attachments, got %r" % (
                0 if not attachments else len(attachments)))
    for _i, _r in enumerate(attachments):
        if not isinstance(_r, FootageRef):
            raise ValueError("attachment %d must be a FootageRef, got %s"
                             % (_i, type(_r).__name__))
        if _r.kind != "video" or not _r.local_path:
            raise ValueError("adapter #2 needs a local video path on clip %d" % _i)
        if not (_r.duration_s and _r.duration_s > 0):
            raise ValueError(
                "adapter #2 needs a measured positive duration on clip %d, got %r"
                % (_i, _r.duration_s))
    if word_timings_per_clip is not None and len(word_timings_per_clip) != len(attachments):
        raise ValueError(
            "word_timings_per_clip must be parallel to attachments (%d vs %d)"
            % (len(word_timings_per_clip), len(attachments)))

    # RE-CLOCK onto the stitched timeline. Every word keeps its own object's
    # fields and gains an OFFSET plus provenance — one index space, so a plan's
    # word indices mean exactly what they mean today. A silent clip is None and
    # contributes no words while still advancing the offset by its duration:
    # dropping its time would slide every later word early, which is the
    # off-by-a-clip version of the drift class.
    _words = None
    if word_timings_per_clip is not None:
        _words = []
        _offset = 0.0
        for _i, _ref in enumerate(attachments):
            _clip_words = word_timings_per_clip[_i] or []
            for _w in _clip_words:
                _nw = dict(_w)
                for _k in ("start", "end"):
                    if isinstance(_nw.get(_k), (int, float)):
                        _nw[_k] = float(_nw[_k]) + _offset
                _nw["_clip_index"] = _i
                _words.append(_nw)
            _offset += float(_ref.duration_s or 0.0)

    hints = dict(user_context or {})
    hints["vibe"] = user_text
    # Roles: clip 0 is primary (it owns the opening), the rest supplementary.
    # Mutating the caller's FootageRefs would be a transform, so they are copied.
    _refs = [FootageRef(local_path=_r.local_path, kind=_r.kind,
                        duration_s=_r.duration_s, source_url=_r.source_url,
                        role=("primary" if _i == 0 else "supplementary"))
             for _i, _r in enumerate(attachments)]
    return SourceEnvelope(
        source_kind=MULTI_CLIP,
        footage_refs=_refs,
        word_timings=_words,
        intent_hints=hints,
        stitched_path=stitched_path,
    )


# ── Adapter #3 — IMAGE / STILL (stub; socket defined, capability lane fills) ─
def adapt_image_still(user_text, attachments, user_context=None):
    """Adapter #3 — one or more stills (+ optional script text) → one envelope.

    Input signature (frozen now):
      attachments   — List[FootageRef] with kind="image", duration_s=0.0;
                      order = narrative order.
      user_text     — carries BOTH intent and any script the stills speak
                      over; the adapter splits intent_hints["vibe"] vs
                      intent_hints["script_text"].
    Resolution contract: word_timings is None (no recorded speech — a
    TTS/pre-timed-script capability, when it exists, lands its timings here
    in the same Deepgram word shape rather than inventing a second clock);
    footage_refs carries the stills; source_kind=IMAGE_STILL. The core treats
    an envelope with word_timings=None as a visual-only plan (the moodreel
    restraint profile is the guidance analogue).
    """
    raise NotImplementedError(
        "adapter #3 (image_still) is a defined socket — not yet built")
