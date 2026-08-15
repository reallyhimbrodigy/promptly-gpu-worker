#!/usr/bin/env python3
"""THE ~1s MOTION RHYTHM LAW, MEASURED `[§4.7, §3.1]`.

LUMEN_REFERENCE_SPEC §1.G: *"Something animates roughly every second in both
refs — a cut, a word, a scene, a zoom. REF-1 median shot 1.8s; REF-2 substitutes
caption-beat + scene-insert rhythm over long takes. Stillness never exceeds
~2s."*

That is a vibe until it is a number. This makes it a number — JUDGE's numbers,
measured off the two references on 2026-08-14:

    PRIMARY    ~3.5 moving samples per second
    SECONDARY  3.5s maximum stillness

**Build to those, not to cut rate.** The references run 21 and 8 hard cuts with
longest cut-to-cut gaps of 6.1s and 9.5s — a system built to cut rate rejects the
very edits it is meant to imitate. Motion is captions, scenes, zooms and type;
cuts are one contributor among several.

WHAT IT MEASURES — motion events on ONE timeline, from the PLAN alone. No
render, no Gemini, no spend, so it runs in the deploy gate and on every differ
candidate. An event is anything that changes the frame:

  cut            a clip boundary
  caption        a caption/word group appearing
  scene          a designed insert scene (GeneratedScene) starting
  zoom           an emphasis zoom firing
  transition     a transition starting
  broll          a b-roll cutaway starting
  text/MG        a motion graphic or text overlay appearing

THE TWO NUMBERS THAT MATTER, and why they are not one number:

  events_per_second   density — THE PRIMARY TARGET, 3.5/s. The thing that
                      separates a Lumen-class edit from a competent trim.
  max_still_gap_s     SECONDARY, 3.5s. The longest stretch with NOTHING
                      happening. Density alone is gameable: 40 captions in 2s
                      averages beautifully and still leaves a dead 6s hole, and
                      the hole is what reads as amateur.

Neither subsumes the other, which is why both survive. My first version of this
file gated on the GAP alone at a 2.0s bar and reported density as context — so
an edit could sit at 1.2 samples/s, visibly sparse, and pass clean. That was
stricter than JUDGE on the lesser number and silent on the greater one. Both are
targets now, and every report prints them in JUDGE's order.

Usage:
    python3 rhythm_dimension.py <plan.json> [...]        # report
    from rhythm_dimension import measure_rhythm          # in the harness
"""
import json
import sys

# JUDGE's targets, 2026-08-14 — these REPLACE my earlier read of §1.G.
#
#   PRIMARY    ~3.5 moving samples per second
#   SECONDARY  3.5s maximum stillness
#
# The primary target is DENSITY, not cut rate, and that ordering is the whole
# point: the references run 21 and 8 hard cuts, with longest cut-to-cut gaps of
# 6.1s and 9.5s, so anything built to cut rate rejects the bar itself. Motion
# comes from captions, scenes, zooms and type — cuts are one contributor among
# several.
#
# My earlier bar was a 2.0s gap with no density target at all. That was stricter
# on stillness and silent on the thing JUDGE ranks FIRST, so an edit could sit at
# 1.2 samples/s — visibly sparse — and still pass. Both targets now exist, in
# JUDGE's order.
MOVING_SAMPLES_PER_S_TARGET = 3.5    # PRIMARY
STILL_GAP_BAR_S = 3.5                # SECONDARY


def _num(v):
    try:
        f = float(v)
        return f if f == f and f not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None


def _collect(plan):
    """Every motion event's timestamp, tagged by kind. Tolerant by design: a
    plan shape that has drifted must degrade to 'fewer events seen', never to a
    crash inside a gate."""
    ev = []

    def add(t, kind):
        t = _num(t)
        if t is not None and t >= 0:
            ev.append((t, kind))

    clips = plan.get("clips") or []
    for c in clips:
        if not isinstance(c, dict):
            continue
        add(c.get("startFrameInOutput") or c.get("start_s") or c.get("fromMs"), "cut")
        for z in ("_zoom_effect", "zoom_effect", "zoom"):
            if c.get(z):
                add(c.get("startFrameInOutput") or c.get("start_s"), "zoom")
                break

    for key, kind in (("captions", "caption"), ("caption_pages", "caption"),
                      ("generated_scenes", "scene"), ("broll_clips", "broll"),
                      ("broll", "broll"), ("transitions", "transition"),
                      ("motion_graphics", "mg"), ("text_overlays", "text"),
                      ("emphasis_moments", "emphasis")):
        for item in (plan.get(key) or []):
            if not isinstance(item, dict):
                continue
            add(item.get("fromMs") or item.get("start_s") or item.get("startMs")
                or item.get("start") or item.get("startFrame"), kind)

    return sorted(ev, key=lambda e: e[0])


def measure_rhythm(plan, duration_s=None):
    """-> {events, per_second, max_still_gap_s, gap_at_s, by_kind, within_bar}

    Timestamps in a plan are a mix of ms, seconds and frames depending on the
    field. Rather than guess per field, the scale is inferred ONCE from the
    whole set against the known duration — a wrong guess would silently scale
    the gap by 1000 and make every edit look perfect."""
    ev = _collect(plan)
    if not ev:
        return {"events": 0, "per_second": 0.0, "max_still_gap_s": None,
                "gap_at_s": None, "by_kind": {}, "within_bar": None,
                "note": "no motion events found — plan shape unrecognised or genuinely empty"}

    ts = [t for t, _ in ev]
    dur = _num(duration_s)
    span = max(ts) - min(ts)
    # Infer the unit from the span against the stated duration.
    scale = 1.0
    if dur and dur > 0:
        if span > dur * 100:        # milliseconds
            scale = 0.001
        elif span > dur * 2.5:      # frames (assume 30fps)
            scale = 1.0 / 30.0
    elif span > 600:                # no duration given: >10min of "seconds" is ms
        scale = 0.001
    ts = [t * scale for t in ts]

    total = dur if (dur and dur > 0) else (max(ts) - min(ts)) or 1.0
    gaps = [(ts[i + 1] - ts[i], ts[i]) for i in range(len(ts) - 1)]
    max_gap, gap_at = max(gaps, default=(0.0, 0.0))

    by_kind = {}
    for _, k in ev:
        by_kind[k] = by_kind.get(k, 0) + 1

    _per_s = round(len(ev) / total, 3) if total else 0.0
    return {
        "events": len(ev),
        "per_second": _per_s,
        # PRIMARY target [JUDGE 2026-08-14]. Reported as a ratio so a read is
        # actionable at a glance: 1.0 is on target, 0.4 is 40% of the bar.
        "density_ratio": round(_per_s / MOVING_SAMPLES_PER_S_TARGET, 2)
                         if MOVING_SAMPLES_PER_S_TARGET else None,
        "meets_density": _per_s >= MOVING_SAMPLES_PER_S_TARGET,
        "max_still_gap_s": round(max_gap, 2),
        "gap_at_s": round(gap_at, 2),
        "by_kind": by_kind,
        "within_bar": max_gap <= STILL_GAP_BAR_S,
        "duration_s": round(total, 2),
    }


def compare_to_reference(measured, ref_name="REF"):
    """One line a human can act on. Names WHERE the hole is, because 'too still'
    without a timestamp is not actionable."""
    if measured.get("max_still_gap_s") is None:
        return f"{ref_name}: unmeasurable ({measured.get('note')})"
    # PRIMARY first, secondary second — JUDGE's order, so a report cannot lead
    # with the lesser number.
    _d = "DENSITY OK" if measured.get("meets_density") else "TOO SPARSE"
    _s = "gap ok" if measured["within_bar"] else "TOO STILL"
    verdict = f"{_d} / {_s}"
    return (f"{ref_name}: {verdict} — {measured['events']} events over "
            f"{measured['duration_s']}s = {measured['per_second']}/s; longest "
            f"still gap {measured['max_still_gap_s']}s at t={measured['gap_at_s']}s "
            f"(bar {STILL_GAP_BAR_S}s) · {measured['by_kind']}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    rc = 0
    for path in argv[1:]:
        try:
            with open(path, encoding="utf-8") as f:
                plan = json.load(f)
        except Exception as e:
            print(f"{path}: unreadable ({e})")
            rc = 1
            continue
        if isinstance(plan, dict) and "plan" in plan and isinstance(plan["plan"], dict):
            plan = plan["plan"]
        m = measure_rhythm(plan, plan.get("duration_s") or plan.get("source_duration_s"))
        print(compare_to_reference(m, path.split("/")[-1]))
        # Either target missed is a miss. Gating on the gap alone was exactly
        # the blind spot JUDGE's ordering corrects.
        if m.get("within_bar") is False or m.get("meets_density") is False:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
