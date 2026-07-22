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
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# Guidance block names (a block is a body of prompt guidance, not a tool gate).
TALKING_HEAD = "TALKING_HEAD"
MUSIC = "MUSIC"
HYPE_MUSIC = "HYPE_MUSIC"   # beat-synced hype/montage on the user's OWN audio

# The music-detector gate: rhythmic music scores aubio tempo-confidence ~0.25-0.79;
# ambient/noise/silence ~0.06. ~0.15 separates them on the synth corpus. PROVISIONAL
# — validate on a REAL busy-trap clip before the flip (synth trap_dense hit 0.245).
BEAT_CONF_MIN = float(os.environ.get("PROMPTLY_HYPE_BEAT_CONF_MIN", "0.15"))


def _hype_mode_enabled():
    """DARK by default. The router activates HYPE_MUSIC ONLY when this flag is on,
    so with it off the live path is byte-identical (router always {TALKING_HEAD}).
    The flip to on is GATED on Zac's quality sign-off after the real-clip loop.
    Rollback = unset the env."""
    return os.environ.get("PROMPTLY_HYPE_MODE", "").strip().lower() not in ("", "0", "false", "off", "no")


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
    beat_grid: List[float] = field(default_factory=list)     # beat times (s) — aubio.tempo
    beat_confidence: float = 0.0                             # aubio tempo confidence — the MUSIC discriminant
    motion_curve: List[float] = field(default_factory=list)  # per-window optical-flow magnitude — Step 1
    scenes: List[float] = field(default_factory=list)        # shot-change times (s) — reuses detect_shot_changes
    loudness: Dict = field(default_factory=dict)             # peak/rms/noise_floor dB
    faces: bool = False                                      # any face detected


def _aubio_beats(wav_path):
    """Returns (beat_times_seconds, mean_tempo_confidence) on an audio WAV.

    DETECTION ONLY — finds the beat in the user's OWN audio so an edit can cut to
    it. NEVER adds/supplies/mixes a track; the app ships no music.

    tempo CONFIDENCE is the MUSIC discriminant. aubio.tempo is a beat TRACKER — it
    returns a beat grid on ANY audio (noise, silence, speech), so beat-grid-non-empty
    is useless as a detector. Confidence separates rhythmic music (~0.25-0.79) from
    ambient/noise (~0.06). (The old onset-density discriminant was refuted — an
    artifact of anomalously-smooth studio BGM; it inverts on real percussive music.)

    Fail-safe: ([], 0.0) if aubio is unavailable (Modal-image-only) or on ANY error.
    Isolated so unit tests can stub it.
    """
    try:
        import aubio
    except Exception:
        return [], 0.0
    try:
        win_s, hop_s = 1024, 512
        src = aubio.source(wav_path, 0, hop_s)
        sr = src.samplerate
        tempo = aubio.tempo("default", win_s, hop_s, sr)
        beats, confs = [], []
        while True:
            samples, read = src()
            if tempo(samples):
                beats.append(round(float(tempo.get_last_s()), 3))
                try:
                    confs.append(float(tempo.get_confidence()))
                except Exception:
                    pass
            if read < hop_s:
                break
        conf = (sum(confs) / len(confs)) if confs else 0.0
        return beats, round(conf, 3)
    except Exception:
        return [], 0.0


def compute_beat_grid(audio_path, has_audio):
    """Gate + compute (beat_grid, tempo_confidence) on the user's own audio.

    GATED on has_audio: no-audio jobs return ([], 0.0) without touching aubio, so a
    talking-head job pays ~nothing new. Fail-safe. `audio_path` is a WAV the caller
    extracted (handler owns I/O; this stays pure + unit-testable).
    """
    if not has_audio or not audio_path:
        return [], 0.0
    return _aubio_beats(audio_path)


def build_perception(has_speech=False, has_audio=False, faces=False,
                     loudness=None, scenes=None, content_class="unknown",
                     has_music=False, beat_grid=None, beat_confidence=0.0,
                     motion_curve=None):
    """Assemble a PerceptionResult from already-computed mega_pool signals.

    Step 0: populates the signals the live pipeline already produces
    (has_speech / has_audio / faces / loudness / scenes / content_class). The
    music fields (has_music / beat_grid) and motion_curve default empty — they
    are FILLED IN STEP 1 (aubio beat_grid on the USER'S OWN audio; the shake
    probe's per-window array). Nothing reads this result in Step 0 → inert.

    NOTE: beat_grid detects the beat in the user's uploaded audio (to cut to it).
    It NEVER implies adding music — the app supplies no tracks, ever.
    """
    return PerceptionResult(
        content_class=content_class,
        has_speech=bool(has_speech),
        has_music=bool(has_music),
        has_audio=bool(has_audio),
        beat_grid=list(beat_grid or []),
        beat_confidence=float(beat_confidence or 0.0),
        motion_curve=list(motion_curve or []),
        scenes=list(scenes or []),
        loudness=dict(loudness or {}),
        faces=bool(faces),
    )


# ── Timeline currency (Step 0 contract; N≥2 assembly built in Step 4) ─────────
# The universal anchor is the OUTPUT-TIMELINE-FRAME. A Timeline is an ordered
# list of clips, each a window {source_index, in_frame, out_frame, playback_rate}
# on some source. Single-clip is simply N=1.
#
# MANDATORY INVARIANT (Step 0): the N=1 case routes through the EXACT current
# projection path (handler._pw_by_idx / _translate_post_cut_anchors_to_src) —
# NOT a generalized recompute — until the general path is proven frame-identical
# against a talking-head golden render. word_index is the N=1 projection, not the
# universal currency. This contract exists so Step 4 has a shape to fill; it does
# NOT reroute today's rendering.
@dataclass
class TimelineClip:
    source_index: int          # which source (N=1 → always 0)
    in_frame: int              # in-point on that source
    out_frame: int             # out-point on that source
    playback_rate: float = 1.0


@dataclass
class Timeline:
    clips: List["TimelineClip"] = field(default_factory=list)

    @property
    def is_single_source(self) -> bool:
        """N=1 (the only case that renders today) — must use the current path."""
        return len({c.source_index for c in self.clips}) <= 1


def _route_guidance(perception: PerceptionResult, user_request: Optional[Dict] = None):
    """Select which guidance blocks load. Returns a set of block names.

    CONSERVATIVE INVARIANT (locked by preservation_harness lock 3): a job with
    speech present ALWAYS resolves to exactly {TALKING_HEAD} — today's live path,
    byte-for-byte. The HYPE_MUSIC branch is reachable ONLY when (a) there is NO
    speech, AND (b) the DARK flag PROMPTLY_HYPE_MODE is on. So a real talking-head
    — including premium/Lumen — can NEVER reach a changed block set, and with the
    flag off (production default) NOTHING routes to HYPE_MUSIC: byte-identical.

    HYPE_MUSIC beat-syncs to the user's OWN uploaded audio; it never adds a track.
    """
    p = perception
    # The live success condition. This branch MUST NOT change.
    if getattr(p, "has_speech", False):
        return {TALKING_HEAD}
    # Non-speech branch — DARK-flag-gated + conditioned on a REAL music detector.
    # NOT beat_grid-non-empty (aubio.tempo returns a grid on any audio incl.
    # silence/noise) — gate on tempo CONFIDENCE, which separates rhythmic music
    # from ambient/noise. Flag off (default) or weak/no beat -> {TALKING_HEAD}
    # (inert; the live NO_SPEECH reject then fires exactly as today).
    if _hype_mode_enabled():
        if getattr(p, "has_audio", False) and getattr(p, "beat_confidence", 0.0) > BEAT_CONF_MIN:
            return {HYPE_MUSIC}
    return {TALKING_HEAD}
