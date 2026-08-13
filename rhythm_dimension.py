#!/usr/bin/env python3
"""THE ~1s MOTION RHYTHM LAW, MEASURED `[§4.7, §3.1]`.

LUMEN_REFERENCE_SPEC §1.G: *"Something animates roughly every second in both
refs — a cut, a word, a scene, a zoom. REF-1 median shot 1.8s; REF-2 substitutes
caption-beat + scene-insert rhythm over long takes. Stillness never exceeds
~2s."*

That is a vibe until it is a number. This makes it a number.

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

  events_per_second   density. Easy to game — 40 captions in 2s scores well and
                      looks like a seizure.
  max_still_gap_s     THE LAW. The longest stretch with NOTHING happening.
                      §1.G's real claim is about the GAP, not the average: an
                      edit can average 1.2 events/s and still have a dead 6s
                      hole, and the hole is what reads as amateur.

So the gate is on the GAP, and density is reported beside it as context. A
single average would have hidden exactly the defect the references rule out.

Usage:
    python3 rhythm_dimension.py <plan.json> [...]        # report
    from rhythm_dimension import measure_rhythm          # in the harness
"""
import json
import sys

# §1.G: "stillness never exceeds ~2s". 2.0 is the bar the references set; the
# gate warns above it rather than failing, because a legitimate long take with a
# strong caption cadence is a real editorial choice (REF-2 does exactly that).
STILL_GAP_BAR_S = 2.0


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

    return {
        "events": len(ev),
        "per_second": round(len(ev) / total, 3) if total else 0.0,
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
    verdict = "WITHIN BAR" if measured["within_bar"] else "TOO STILL"
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
        if m.get("within_bar") is False:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
