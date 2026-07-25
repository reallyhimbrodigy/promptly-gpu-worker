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


def build_minimal_plan(source_duration: float, fps: float = 30.0,
                       motion_curve: Optional[List[float]] = None,
                       target_clip_s: float = 2.5, min_clip_s: float = 1.2,
                       transition_every: int = 4) -> HypePlan:
    """Deterministic minimal edit for a silent/no-speech clip: clean sequential
    cuts (motion-guided if a curve is given, else even) + a calm transition every
    `transition_every` cuts. speed=1.0, zoom=None, no MG, no captions.
    """
    if motion_curve:
        cuts = _motion_cuts(list(motion_curve), source_duration, target_clip_s, min_clip_s)
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
