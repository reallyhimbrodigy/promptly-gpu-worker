"""General-editor scaffold — the seams the music increment lands into.

Brick 1 ships the CONTRACT + a conservative router stub that is INERT: nothing
in handler.py calls _route_guidance yet. Step 1 wires it at the reject gates
(handler.py:27140 / 28203 / 28219), replacing "reject" with "route." The
router-inertness gate (preservation_harness lock 3) proves TALKING_HEAD + Lumen
perception fixtures ALWAYS resolve to {"TALKING_HEAD"} — a real talking-head can
never reach a changed guidance block set.

The router selects GUIDANCE BLOCKS; it never restricts the toolbox. Every render
primitive stays available to Gemini regardless of which blocks load.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# Guidance block names (a block is a body of prompt guidance, not a tool gate).
TALKING_HEAD = "TALKING_HEAD"
MUSIC = "MUSIC"


@dataclass
class PerceptionResult:
    """Content-agnostic perception contract, emitted for EVERY job (Step 0).

    For a pure-speech job it carries today's exact signals; the new fields
    (beat_grid, motion_curve, has_music, content_class) are computed but unread
    by TALKING_HEAD guidance → inert. N≥2 clips are the timeline case (Step 4);
    single-clip is N=1.
    """
    content_class: str = "unknown"       # talking_head | music | comedy | aesthetic | ...
    has_speech: bool = False
    has_music: bool = False
    has_audio: bool = False
    beat_grid: List[float] = field(default_factory=list)     # onset/beat times (s) — Step 1 (aubio)
    motion_curve: List[float] = field(default_factory=list)  # per-window optical-flow magnitude — Step 1
    scenes: List[float] = field(default_factory=list)        # shot-change times (s) — reuses detect_shot_changes
    loudness: Dict = field(default_factory=dict)             # peak/rms/noise_floor dB
    faces: bool = False                                      # any face detected


def _route_guidance(perception: PerceptionResult, user_request: Optional[Dict] = None):
    """Select which guidance blocks load. Returns a set of block names.

    CONSERVATIVE INVARIANT (locked by preservation_harness lock 3): a job with
    speech present ALWAYS resolves to exactly {TALKING_HEAD} — today's live path,
    byte-for-byte. The non-speech (MUSIC) branch is reachable ONLY when there is
    no speech, so a real talking-head — including premium/Lumen — can never reach
    a changed block set. Step 1 fills in the MUSIC branch below; until then every
    input routes to TALKING_HEAD (fully inert).
    """
    p = perception
    # The live success condition. This branch MUST NOT change.
    if getattr(p, "has_speech", False):
        return {TALKING_HEAD}
    # --- Step 1 will add here (only reachable when has_speech is False): ---
    #   if p.has_audio and (p.beat_grid or _hype_hint(user_request)):
    #       return {MUSIC}
    # Until built, remain inert — no non-speech input changes behavior yet.
    return {TALKING_HEAD}
