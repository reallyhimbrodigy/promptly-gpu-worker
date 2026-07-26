"""CINEMATIC MOOD-REEL editorial half — motion-anchored composure for
posed/aesthetic no-speech clips WITHOUT confident music.

DARK: zero callers in the live path (grep-provable). Exercised only by the
sample harness (moodreel_sample_app.py); a routing branch lands LATER, after
Zac's taste sign-off — this module is the sample stage only.

WHY THIS MODE EXISTS: S-ANYVIDEO's intake data nominated it — the largest
underserved class is the posed/aesthetic clip with no speech and no confident
beat (aubio tempo-confidence below the music gate). Hype grammar has nothing to
sync to there; minimal grammar is honest but flat. Users type "make a
cinematic". This mode re-anchors the hype architecture from the BEAT GRID to
the MOTION CURVE: same HypePlan schema, same project_hype_plan projection, same
hype_render bridge — no new render primitives, no new schema family.

Three pieces:
  - extract_motion_curve  : per-window motion energy from the source (cheap
                            ffmpeg frame-difference sampling, ~seconds)
  - motion_features       : peaks + resolve-points (the cut anchors) from a curve
  - build_moodreel_prompt : the CINEMATIC doctrine (authored fresh, not sliced
                            from hype) — emits the SAME HypePlan schema

SPEED LAW NOTE: the locked quality law says every cut renders 1.0x — written
for the talking-head path. The hype path already ships ≠1.0 speeds (its ramps
are the exception that shipped). Mood-reel mirrors hype's allowance but inverts
its direction and biases hard to 1.0: 0.85-1.0 ONLY (a slow-motion FEEL on a
savoring shot), never >1.0. The tension is noted, not resolved, here.
"""
import os
import re
import subprocess
import tempfile
from typing import List, Optional, Tuple

import type_registries as _tr

# The SAME canonical vocabularies every path uses — a mood reel draws from the
# universal toolbox; the doctrine shapes HOW, it never gates WHAT.
_ZOOM = tuple(sorted(_tr.VALID_ZOOM_TYPES))
_TRANSITION = tuple(sorted(_tr.VALID_TRANSITION_TYPES))
_MG = tuple(sorted(_tr.VALID_MG_TYPES))


# ── motion curve extractor ───────────────────────────────────────────────────
def extract_motion_curve(video_path: str, window_s: float = 1.0,
                         sample_fps: float = 6.0, scale_w: int = 160,
                         duration: Optional[float] = None) -> List[float]:
    """Per-window motion-energy curve from the source — the mood reel's spine.

    Cheap by construction (~seconds on a 30s clip): downscale to `scale_w`,
    sample at `sample_fps`, read lavfi scene-score (mean abs frame difference)
    per sampled frame, average per `window_s` bucket, normalize 0-1 by the peak.
    This is optical-flow-LITE — frame difference tracks gesture energy (a turn,
    a step, light moving) without paying for real flow.

    Standalone + fail-safe: returns [] on ANY error; every consumer
    (minimal_editor._motion_cuts, build_moodreel_prompt) falls back to even
    pacing on an empty curve.
    """
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="motioncurve_")
        os.close(fd)
        vf = (f"scale={int(scale_w)}:-2:flags=bilinear,fps={sample_fps:g},"
              f"select='gte(scene,0)',metadata=print:file={tmp}")
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", video_path, "-vf", vf,
             "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            return []
        with open(tmp) as f:
            text = f.read()
        # metadata=print emits pairs:
        #   frame:N pts:P pts_time:T
        #   lavfi.scene_score=0.003917
        t_cur, samples = None, []
        for line in text.splitlines():
            m = re.search(r"pts_time:([0-9.]+)", line)
            if m:
                t_cur = float(m.group(1))
                continue
            m = re.match(r"lavfi\.scene_score=([0-9.eE+-]+)", line.strip())
            if m and t_cur is not None:
                samples.append((t_cur, float(m.group(1))))
        if not samples:
            return []
        span = float(duration) if duration else (samples[-1][0] + 1.0 / sample_fps)
        n = max(1, int(round(span / window_s)))
        sums = [0.0] * n
        counts = [0] * n
        for t, v in samples:
            i = min(int(t / window_s), n - 1)
            sums[i] += v
            counts[i] += 1
        curve = [(sums[i] / counts[i]) if counts[i] else 0.0 for i in range(n)]
        # Normalize by the 95th percentile, capped at 1.0 — a hard scene change
        # is a single huge frame-difference spike, and max-normalizing by it
        # would flatten every real gesture to ~0. The p95 keeps gesture energy
        # on-scale while cut spikes saturate at 1.0.
        ordered = sorted(curve)
        norm = ordered[min(n - 1, int(0.95 * (n - 1)))] or max(curve)
        if norm > 0:
            curve = [round(min(v / norm, 1.0), 4) for v in curve]
        return curve
    except Exception:
        return []
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


def motion_features(motion_curve: List[float],
                    window_s: float = 1.0) -> Tuple[List[float], List[float]]:
    """(peaks, resolves) in seconds — the mood reel's cut anchors.

    A PEAK is a local max above the curve's median (a gesture cresting). Its
    RESOLVE is the end of the following descent (the gesture completing and
    breathing) — the doctrine's "cut where motion resolves" lands there, never
    on the rise. Times are window centers.
    """
    c = list(motion_curve or [])
    n = len(c)
    peaks: List[float] = []
    resolves: List[float] = []
    if n < 3:
        return peaks, resolves
    # Floor at 0.15 (normalized scale) so noise wiggles on a still clip never
    # read as gestures; the median term keeps busy clips from calling every
    # window a peak.
    thresh = max(sorted(c)[n // 2], 0.15)
    for i in range(1, n - 1):
        if c[i] >= c[i - 1] and c[i] >= c[i + 1] and c[i] > thresh:
            peaks.append(round((i + 0.5) * window_s, 2))
            j = i + 1
            while j + 1 < n and c[j + 1] <= c[j]:
                j += 1
            resolves.append(round((j + 0.5) * window_s, 2))
    return peaks, resolves


# ── the CINEMATIC doctrine ───────────────────────────────────────────────────
def build_moodreel_prompt(vibe, duration, motion_curve, scenes=None):
    """The CINEMATIC MOOD-REEL guidance block. Authored FRESH (never sliced from
    the hype or talking-head prompts). Returns (system_instruction, user_content).

    Re-anchoring: hype's spine is the beat grid; the mood reel's spine is VISUAL
    RHYTHM — motion peaks, composition changes, light. Same HypePlan schema out,
    same projection, same bridge. Every tool stays available; this only shapes
    HOW to use them (educate-Gemini, no code-side drops).
    """
    curve = list(motion_curve or [])
    peaks, resolves = motion_features(curve)
    _curve_s = ", ".join(f"{v:.2f}" for v in curve[:120])
    _peaks_s = ", ".join(f"{t:.1f}" for t in peaks[:32])
    _resolves_s = ", ".join(f"{t:.1f}" for t in resolves[:32])
    _scene_s = ", ".join(f"{s:.2f}" for s in (scenes or [])[:32])

    system_instruction = f"""=== YOUR JOB (CINEMATIC MOOD REEL) ===
This is a posed/aesthetic NON-speech clip with no confident music driving it — a
fashion pose held for the lens, a landscape at dusk, a city exhaling. There is
NO speaker, NO transcript, NO beat grid to obey. The footage is the music.

THE SPINE IS VISUAL RHYTHM: the motion curve (per-second motion energy),
composition changes, and light. You are not hyping this footage — you are
composing with it. Where hype cuts TO the beat, you cut WITH the motion.

THE THREE LAWS OF THE MOOD REEL:
1. A LINGERING SHOT EARNS ITS LENGTH. A shot may hold 3-6 seconds ONLY while
   something in the frame is still developing — a turn completing, light
   crawling across a face, a pose settling into stillness. The moment the frame
   stops giving, cut. A hold with nothing developing is not cinematic; it is
   stalled.
2. CUTS LAND WHERE MOTION RESOLVES. Read the motion curve: cut in the valley
   just AFTER a peak — the gesture completes, breathes, then the cut. Never cut
   on the rise (that is hype grammar) and never mid-gesture. The RESOLVE times
   provided are exactly these landing zones.
3. THE PACE IS THE GRADE. You cannot color-grade, but pacing reads as grade:
   long-held frames and slow drift read moody and expensive; fast even cuts
   read like a slideshow. Pick the mood the user asked for and make every
   duration serve it.

YOUR TOOLBOX (the same universal set the whole editor uses — use what FITS):
- CUTS: few and deliberate. 4-8 shots across 15-25s is the register; most shots
  2.5-5s, with ONE allowed to run long while it keeps developing. FITS: letting
  composition changes mark time. FIGHTS: metronomic spacing — a mood reel that
  cuts every 2.5s like clockwork is a slideshow, not cinema.
- DRIFT ZOOMS (zoom types {list(_ZOOM)}): slow push-ins and drift ONLY —
  SmoothPush and DepthPull, `punch=false` ALWAYS. The camera leans in to look
  closer; it never punches. 1-3 per reel, on the most composed frames. FITS: a
  held pose, a static wide with light moving. FIGHTS: any shot already moving —
  motion plus push is churn, and a punch zoom here breaks the spell.
- SPEED: 1.0 is the reel's pulse — most shots stay EXACTLY 1.0. A shot MAY
  float at 0.85-1.0 when its motion arc is smooth and worth savoring (a hair
  flip, a slow pan, fabric in wind) — a slow-motion FEEL, never a ramp. NEVER
  above 1.0: nothing in a mood reel hurries. Never below 0.85.
- TRANSITIONS ({list(_TRANSITION)}): ALMOST NEVER. The hard cut is the joint;
  restraint is the whole style. At most ONE dissolve (CrossfadeZoom) and only
  at a TRUE mood shift — day to dusk, street to interior, motion to stillness.
  If you cannot name the mood shift, there is no dissolve. ZERO transitions is
  the expected answer.
- MOTION GRAPHICS ({list(_MG)}): almost never — default NONE. At most a single
  restrained stamp (a place, a mood word) placed low, never on the subject,
  never explaining what the image already says.
- OUTRO: END WITH INTENTION. Close on the reel's most settled frame and either
  let it fall away (`outro: fade_black`) or let the final hard frame BE the
  ending (`outro: none` on a strong last composition). An ending that just runs
  out of footage is a failure; a transition floating near the end that is not
  the outro reads as an accident.

HARD RULES:
- Anchor in SECONDS on the source. Use the RESOLVE times as cut landing zones.
- NEVER add music, a soundtrack, or reference adding one. The clip's own audio
  — or its silence — is the bed.
- Total edit stays within the source duration ({duration:.1f}s). Do not invent
  time.

=== RESPONSE FORMAT ===
Emit a HypePlan JSON: clips[{{start_s,end_s,speed,zoom,punch}}], transitions
[{{after_clip,type}}], motion_graphics[{{start_s,end_s,type,text}}], outro. Every
start_s/end_s is source seconds. zoom is one of {list(_ZOOM)} or null; punch is
always false here; speed is 1.0 or a float in [0.85, 1.0)."""

    user_content = f"""The user wants: {vibe or "a cinematic mood reel — let the footage breathe"}
Source duration: {duration:.1f}s
MOTION CURVE (per-second energy, normalized 0-1): {_curve_s or "(unavailable — pace by the scene cuts and your eye)"}
MOTION PEAKS (s — gestures crest here; never cut on these): {_peaks_s or "(none found)"}
MOTION RESOLVES (s — the breath after each peak; cuts land here): {_resolves_s or "(none found)"}
SCENE CUTS (s — composition-change hints): {_scene_s or "(none detected)"}
Compose with the motion. Linger only while the frame develops; cut where the
motion resolves; end with intention."""
    return system_instruction, user_content
