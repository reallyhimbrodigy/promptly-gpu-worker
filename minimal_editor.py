"""Minimal-edit path — silent / no-speech clips get clean cuts + occasional
transitions, nothing else.

DARK: reached only via the router's future no-speech/silent route (staged behind
the 3 certs). The talking-head path never touches this.

What it is NOT: no captions (nothing is being said), no zooms (that's a taste move
the hype path owns), no beat grid (there may be no audio, and beat-sync is the
hype upgrade that lands after its own cert). What it IS: sequential clean cuts that
re-pace the footage, with a calm transition every few cuts to mark sections.

Pacing: motion_curve peaks when available (cut where the motion changes), else even
spacing — both deterministic, so the MECHANICAL cert (A/V sync, no black frames,
sane durations) is reproducible with no model in the loop.

Renders through the SAME caption-less bridge the hype path uses:
    build_minimal_plan(...) -> HypePlan -> project_hype_plan -> render_hype
so there is ONE render path for every caption-less edit, not a second one.
"""
import re
from typing import List, Optional

from hype_editor import HypePlan, HypeClip, HypeTransition

# Calm, universal transitions — no strobe, no flash. A minimal edit marks a
# section change, it doesn't punctuate a drop (that's hype).
_MINIMAL_TRANSITIONS = ("DipToBlack", "CrossfadeZoom")


def _even_cuts(duration: float, target_s: float, min_s: float) -> List[tuple]:
    """Sequential, in-order segments covering the source. Preserves temporal flow
    (a b-roll reel plays forward); the cuts add pacing + transition seams."""
    cuts: List[tuple] = []
    t = 0.0
    while t < duration - min_s:
        end = min(t + target_s, duration)
        if end - t >= min_s:
            cuts.append((round(t, 3), round(end, 3)))
        t = end
    return cuts


def _motion_cuts(motion_curve: List[float], duration: float, target_s: float,
                 min_s: float) -> List[tuple]:
    """Cut near local motion-energy peaks so seams land on movement (a step, a
    turn, a reveal) rather than mid-gesture. motion_curve is a per-window energy
    array over the clip; falls back to even spacing if too short/flat."""
    n = len(motion_curve)
    if n < 4:
        return _even_cuts(duration, target_s, min_s)
    win = duration / n
    # candidate boundaries = windows whose energy exceeds the local neighbourhood
    peaks = []
    for i in range(1, n - 1):
        if motion_curve[i] >= motion_curve[i - 1] and motion_curve[i] >= motion_curve[i + 1]:
            peaks.append(i * win)
    if not peaks:
        return _even_cuts(duration, target_s, min_s)
    # walk peaks, enforcing target/min spacing so we don't strobe
    cuts, t = [], 0.0
    for p in peaks:
        if p - t >= max(min_s, target_s * 0.7) and p <= duration - min_s:
            cuts.append((round(t, 3), round(p, 3)))
            t = p
    if duration - t >= min_s:
        cuts.append((round(t, 3), round(duration, 3)))
    return cuts or _even_cuts(duration, target_s, min_s)


# WHAT THE USER ASKED FOR, ON THE ONE PATH THAT COULD NOT READ IT (Zac 2026-08-04).
# This function had NO vibe parameter at all — 204 jobs / 188 users received a
# video whose pacing never consulted a word they wrote, which is the most direct
# violation of "always tailored to what the user asks for".
#
# THIS IS A FLOOR, NOT THE ANSWER. Zac's ruling is that every path calls the
# MODEL; a keyword table is still a deterministic edit. It is here because this
# path is what remains when the model call is unavailable (plan_collapsed, or a
# clip under the mood-reel floor), and a tailored fallback beats an untailored
# one while the deterministic routes are being deleted.
_VIBE_PACE = (
    (re.compile(r"fast|punch|snapp|viral|hype|energet|quick|tight|aggress|chaos",
                re.I), 1.6),
    (re.compile(r"slow|calm|cinemat|smooth|relax|gentle|corporate|professional|"
                r"documentar|elegant|luxur|serene|moody", re.I), 3.6),
)


def pace_from_vibe(vibe, default: float = 2.5) -> float:
    """Target clip length in seconds, read off the user's own words.

    Fast wins ties: a vibe naming both registers ("fast but cinematic") is asking
    for energy with a look, and the pace is the energy. Returns the default when
    the vibe says nothing about pace, so silence changes nothing.
    """
    _v = str(vibe or "")
    if not _v.strip():
        return default
    for _pat, _pace in _VIBE_PACE:
        if _pat.search(_v):
            return _pace
    return default


def build_minimal_plan(source_duration: float, fps: float = 30.0,
                       motion_curve: Optional[List[float]] = None,
                       target_clip_s: Optional[float] = None,
                       min_clip_s: float = 1.2,
                       transition_every: int = 4,
                       trim_lo: float = 0.4, trim_hi: float = 0.8,
                       vibe: Optional[str] = None) -> HypePlan:
    """Deterministic minimal edit for a silent/no-speech clip. ADOPTED (Zac
    PAIR1 B + PAIR2 B, 2026-07-25, on the sample pairs): WITH a motion curve —
    boundaries land at motion PEAKS (pair 2) and any boundary whose following
    region is LOW motion skip-trims 0.4-0.8s of dead seam air (pair 1; deeper
    below the median → the bigger skip). WITHOUT a curve (extractor fail-safe):
    today's even pacing, unchanged. speed=1.0, zoom=None, no MG, no captions.
    """
    # an explicit target_clip_s still wins (the certs pass one); otherwise the
    # user's words set the pace, falling back to the old 2.5s constant.
    if target_clip_s is None:
        target_clip_s = pace_from_vibe(vibe)
    curve = list(motion_curve or [])
    if curve:
        cuts = _motion_cuts(curve, source_duration, target_clip_s, min_clip_s)
        # PAIR1 B: skip dead air at low-motion boundaries. Rebuild the cut list
        # inserting source-skips AFTER any boundary sitting at/below the median
        # motion energy.
        med = sorted(curve)[len(curve) // 2]
        win = source_duration / len(curve)
        trimmed, consumed = [], 0.0
        for (a, b) in cuts:
            a2 = max(a, consumed)
            if b - a2 < min_clip_s:
                continue
            trimmed.append((round(a2, 3), round(b, 3)))
            e = curve[min(int(b / win), len(curve) - 1)]
            skip = (trim_hi if e <= 0.5 * med else trim_lo) if e <= med else 0.0
            consumed = b + skip
        cuts = trimmed or cuts
    else:
        cuts = _even_cuts(source_duration, target_clip_s, min_clip_s)
    if not cuts:
        cuts = [(0.0, round(min(source_duration, max(min_clip_s, 1.0)), 3))]
    clips = [HypeClip(start_s=a, end_s=b, speed=1.0, zoom=None, punch=False)
             for (a, b) in cuts]
    transitions = []
    for k, i in enumerate(range(transition_every - 1, len(clips) - 1, transition_every)):
        transitions.append(HypeTransition(
            after_clip=i, type=_MINIMAL_TRANSITIONS[k % len(_MINIMAL_TRANSITIONS)]))
    return HypePlan(clips=clips, transitions=transitions,
                    motion_graphics=[], outro="none")
