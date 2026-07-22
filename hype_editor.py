"""HYPE_MUSIC editorial half — beat-synced hype/montage for no-speech clips.

DARK: reachable only when the router returns {HYPE_MUSIC} (PROMPTLY_HYPE_MODE on
+ 0 words + has_audio + beat detected). The talking-head path never touches this.

Beat-syncs to the user's OWN uploaded audio — it NEVER adds, supplies, or mixes a
track (no-music rule). Emits ONLY existing render primitives (ClipSpec cuts+speed,
ZoomEffectSpec punch, TransitionSpec, MotionGraphicSpec) — no new render-schema
family, so render_schemas.py and the deploy-gate allowlist are untouched.

Three pieces:
  - HypePlan          : Gemini's beat/second-anchored output schema
  - build_hype_prompt : the MUSIC/HYPE guidance block (FITS/FIGHTS re-anchored
                        from dialogue-arc to the energy/beat grid)
  - project_hype_plan : seconds -> output-timeline-frames -> PromptlyRenderInput
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

import type_registries as _tr

# Reuse the SAME canonical vocabularies the talking-head render uses — a hype
# edit draws from the universal toolbox, it does not get its own siloed set.
_ZOOM = tuple(sorted(_tr.VALID_ZOOM_TYPES))
_TRANSITION = tuple(sorted(_tr.VALID_TRANSITION_TYPES))
_MG = tuple(sorted(_tr.VALID_MG_TYPES))


# ── Gemini output schema (beat/second-anchored; the universal currency is time) ──
class HypeClip(BaseModel):
    start_s: float                                   # in-point on the source (s)
    end_s: float                                     # out-point on the source (s)
    speed: float = 1.0                               # 1.0 = real time; >1 faster
    zoom: Optional[str] = None                       # a zoom type, or None
    punch: bool = False                              # ease-in impact landing on the beat


class HypeTransition(BaseModel):
    after_clip: int                                  # index into clips[]
    type: str                                        # a transition type


class HypeMG(BaseModel):
    start_s: float
    end_s: float
    type: str                                        # a motion-graphic type
    text: Optional[str] = None


class HypePlan(BaseModel):
    clips: List[HypeClip]
    transitions: List[HypeTransition] = Field(default_factory=list)
    motion_graphics: List[HypeMG] = Field(default_factory=list)
    outro: Optional[Literal["none", "fade_black", "fade_white"]] = "none"
    notes: Optional[str] = None


def build_hype_prompt(vibe, duration, beat_grid, scenes=None, motion_curve=None):
    """The MUSIC/HYPE guidance block. Authored SEPARATELY from the talking-head
    monolith (never sliced from it). Returns (system_instruction, user_content).

    FITS/FIGHTS re-anchored: talking-head arcs (hook/payoff, emphasis WORDS) do
    not exist here — the spine is the ENERGY/BEAT grid. Cuts land on beats; the
    punch-zoom hits the downbeat; speed rises into a drop; transitions punctuate
    section changes. Every tool stays available; this only shapes HOW to use them.
    """
    _beats = ", ".join(f"{b:.2f}" for b in (beat_grid or [])[:64])
    _scene_s = ", ".join(f"{s:.2f}" for s in (scenes or [])[:32])
    _n_beats = len(beat_grid or [])
    system_instruction = f"""=== YOUR JOB (HYPE / MUSIC EDIT) ===
This is a NON-speech clip set to music the user already has in it — a car edit, a
gym/sports montage, an aesthetic b-roll reel. There is NO speaker, NO dialogue, NO
transcript. The music IS the structure. You cut TO THE BEAT and let motion carry
the energy. You NEVER add or reference music — it is already in the clip.

THE SPINE IS THE BEAT GRID, not an arc. Anchor every decision to the beat times
(seconds) provided. Cuts land ON beats. Emphasis (a punch-zoom, a hard transition)
lands on the STRONG beats — downbeats, the drop, a section change (use the scene
cuts as section hints).

YOUR TOOLBOX (the same universal set the whole editor uses — use what FITS hype):
- CUTS + SPEED: cut the timeline to the beat. Tighten dead sections; let a great
  shot breathe for a bar. Speed (playbackRate) ramps INTO energy — a subtle push
  into a drop reads as momentum. FITS: high-energy montages. FIGHTS: nothing here
  is calm — but do not strobe; a cut every single beat for 30s is nausea, not hype.
- PUNCH-ZOOM (zoom types {list(_ZOOM)}): a snap/step/staged push that LANDS its
  scale peak ON a strong beat. `punch=true` = ease-IN impact. FITS: the drop, a
  reveal, the hardest beat. FIGHTS: overuse — 2-4 across a 20-30s clip, on the
  beats that actually hit.
- TRANSITIONS ({list(_TRANSITION)}): punctuate a SECTION change (a new location,
  the drop), not every cut. FITS: viral, dramatic. FIGHTS: back-to-back — a
  transition on every cut deletes the footage.
- MOTION GRAPHICS ({list(_MG)}): sparse kinetic text/graphics for a title card or
  a callout the footage can't say. FITS: a hook title, a location stamp. FIGHTS:
  covering the shot; captioning what's already on screen.

HARD RULES:
- Anchor in SECONDS on the source. Cuts should fall on (or within ~50ms of) a beat.
- NEVER add music, a soundtrack, or reference adding one. The audio is the user's.
- Total edit stays within the source duration ({duration:.1f}s). Do not invent time.

=== RESPONSE FORMAT ===
Emit a HypePlan JSON: clips[{{start_s,end_s,speed,zoom,punch}}], transitions
[{{after_clip,type}}], motion_graphics[{{start_s,end_s,type,text}}], outro. Every
start_s/end_s is source seconds. zoom is one of {list(_ZOOM)} or null."""

    user_content = f"""The user wants: {vibe or "a punchy, high-energy edit synced to the beat"}
Source duration: {duration:.1f}s
BEAT GRID ({_n_beats} beats, source seconds): {_beats}
SCENE CUTS (source seconds — section-change hints): {_scene_s or "(none detected)"}
Cut to these beats. Land your punches on the strong ones."""
    return system_instruction, user_content


def _valid(v, allowed):
    return v if v in allowed else None


def project_hype_plan(plan: "HypePlan", source_url: str, source_fps: float,
                      source_duration: float, width: int = 1080, height: int = 1920) -> dict:
    """Seconds -> output-timeline-frames -> PromptlyRenderInput dict.

    Emits ONLY existing render primitives. Returns a plain dict; the caller
    validates it against render_schemas.PromptlyRenderInput (extra=forbid) — the
    correctness bar. Anchoring: output-timeline-frame (the universal currency);
    single source (N=1). Fail-open primitives: an invalid zoom/transition/MG type
    is DROPPED, never rendered as garbage.
    """
    fps = float(source_fps or 30.0)
    clips = []
    out_frame = 0
    clip_out_spans = []
    for i, c in enumerate(plan.clips):
        s0 = max(0.0, min(float(c.start_s), source_duration))
        s1 = max(s0, min(float(c.end_s), source_duration))
        start_f = int(round(s0 * fps))
        dur_src = max(1, int(round((s1 - s0) * fps)))
        rate = float(c.speed) if c.speed and c.speed > 0 else 1.0
        dur_out = max(1, int(round(dur_src / rate)))
        clip = {"id": f"h{i}", "startFromFrames": start_f,
                "playbackRate": rate, "durationInFrames": dur_out}
        _z = _valid(c.zoom, _ZOOM)
        if _z:
            _dur_ms = int(round(dur_out / fps * 1000))
            clip["zoomEffect"] = {
                "type": _z,
                "events": [{"startMs": 0, "durationMs": max(120, _dur_ms),
                            "scale": 1.18, "originX": 0.5, "originY": 0.5}],
                "punch": bool(c.punch),   # ease-IN impact (ramp zooms read this)
            }
        clips.append(clip)
        clip_out_spans.append((out_frame, out_frame + dur_out))
        out_frame += dur_out

    transitions = []
    for t in plan.transitions:
        _t = _valid(t.type, _TRANSITION)
        if _t is None or not (0 <= t.after_clip < len(clips) - 1):
            continue
        a, b = clips[t.after_clip], clips[t.after_clip + 1]
        transitions.append({
            "afterClipIndex": int(t.after_clip), "type": _t, "durationInFrames": 8,
            "clipAStartFromFrames": a["startFromFrames"], "clipBStartFromFrames": b["startFromFrames"],
            "clipAPlaybackRate": a["playbackRate"], "clipBPlaybackRate": b["playbackRate"],
        })

    motion_graphics = []
    for m in plan.motion_graphics:
        _m = _valid(m.type, _MG)
        if _m is None:
            continue
        f0 = int(round(max(0.0, float(m.start_s)) * fps))
        f1 = int(round(max(float(m.start_s), float(m.end_s)) * fps))
        # place on the OUTPUT timeline by clamping into the total span
        f0 = max(0, min(f0, out_frame - 1))
        dur = max(6, min(f1 - f0, out_frame - f0))
        mg = {"type": _m, "fromFrame": f0, "durationInFrames": dur, "props": {}}
        if m.text:
            mg["props"] = {"text": str(m.text)[:120]}
        motion_graphics.append(mg)

    return {
        "sourceUrl": source_url, "fps": fps, "width": width, "height": height,
        "totalDurationInFrames": max(1, out_frame),
        "clips": clips, "transitions": transitions, "broll": [],
        "textOverlays": [], "motionGraphics": motion_graphics,
        "caption": None,   # no speech -> no captions (caption-less is first-class)
        "outro": None if (plan.outro in (None, "none")) else plan.outro,
    }
