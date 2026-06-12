"""
recipe_eval.py — machine-check a Gemini edit recipe against the window doctrine
and hard constraints from the v2 system prompt.

Usage:
    from recipe_eval import evaluate_recipe
    report = evaluate_recipe(edit_plan, words, cut_boundaries, duration)
    print(report.summary())
    if report.failures:
        # feed report.patch_list() back to Gemini for a repair pass, or log it

Inputs:
    edit_plan      — the parsed recipe JSON (dict)
    words          — kept-only word list, each {"word": str, "start": float, "end": float},
                     index position == kept-word index (same list you already pass to render)
    cut_boundaries — list[int], the authoritative CUT BOUNDARIES after_word_index values
    duration       — float, output duration in seconds (post-cut runtime is fine; window
                     math uses word timestamps, duration is only for the summary line)

No deps beyond stdlib. Every check maps to a named rule in the prompt so when
quality drifts you know WHICH rule drifted.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field

WINDOW_S = 2.0
ZOOM_NATURAL_MS = {
    "SmoothPush": 1200, "SnapReframe": 700, "FocusWindow": 1500,
    "StepZoom": 800, "LetterboxPush": 1400, "StageZoom": 1800, "DepthPull": 2200,
}


@dataclass
class Report:
    failures: list = field(default_factory=list)   # (rule, detail) — hard violations
    warnings: list = field(default_factory=list)   # (rule, detail) — judgment flags
    stats: dict = field(default_factory=dict)

    def fail(self, rule, detail): self.failures.append((rule, detail))
    def warn(self, rule, detail): self.warnings.append((rule, detail))

    def summary(self):
        lines = [f"RECIPE EVAL — {len(self.failures)} failures, {len(self.warnings)} warnings"]
        for k, v in self.stats.items():
            lines.append(f"  {k}: {v}")
        for rule, d in self.failures:
            lines.append(f"  FAIL [{rule}] {d}")
        for rule, d in self.warnings:
            lines.append(f"  WARN [{rule}] {d}")
        return "\n".join(lines)

    def patch_list(self):
        """Compact text block suitable for a Gemini repair-pass prompt."""
        items = [f"- [{r}] {d}" for r, d in self.failures]
        return "Fix these violations and re-emit the full JSON:\n" + "\n".join(items)


def _word_time(words, idx, attr="start"):
    if idx is None or idx < 0 or idx >= len(words):
        return None
    return words[idx][attr]


def _arc_position_of(arc_segments, word_index):
    for seg in arc_segments:
        if seg["start_word_index"] <= word_index <= seg["end_word_index"]:
            return seg["position"]
    return None


def evaluate_recipe(plan, words, cut_boundaries, duration):
    r = Report()
    vp = plan.get("video_plan") or {}
    arc = vp.get("arc_segments") or []
    key_moments = vp.get("key_moments") or []
    emphases = plan.get("emphasis_moments") or []
    transitions = plan.get("transitions") or []
    brolls = plan.get("broll_clips") or []
    mgs = plan.get("motion_graphics") or []
    overlays = plan.get("text_overlays") or []
    sfx = plan.get("sound_effects") or []
    n_words = len(words)

    # ---------------------------------------------------------------- arc spine
    if not arc:
        r.fail("arc_segments", "missing or empty — nothing downstream is groundable")
    else:
        if arc[0]["start_word_index"] != 0:
            r.fail("arc_segments", f"first segment starts at {arc[0]['start_word_index']}, not 0")
        if arc[-1]["end_word_index"] != n_words - 1:
            r.fail("arc_segments", f"last segment ends at {arc[-1]['end_word_index']}, final kept word is {n_words - 1}")
        for a, b in zip(arc, arc[1:]):
            if b["start_word_index"] != a["end_word_index"] + 1:
                r.fail("arc_segments", f"gap/overlap between segments ending {a['end_word_index']} and starting {b['start_word_index']}")
        payoffs = [s for s in arc if s["position"] == "payoff"]
        if len(payoffs) != 1:
            r.fail("arc_segments", f"{len(payoffs)} payoff segments — exactly 1 required")

    # ----------------------------------------------- 1:1 zooms <-> key_moments
    km_indices = {km["word_index"] for km in key_moments}
    emp_anchors = [e["word_indices"][0] for e in emphases if e.get("word_indices")]
    for a in emp_anchors:
        if a not in km_indices:
            r.fail("zoom-1to1", f"emphasis at word {a} has no matching key_moment")
    for k in km_indices:
        if k not in emp_anchors:
            r.warn("zoom-1to1", f"key_moment at word {k} has no emphasis_moment")
    if not (2 <= len(key_moments) <= 9):
        r.warn("key_moments-count", f"{len(key_moments)} key_moments (typical 4-7 per 30s)")

    # ------------------------------------------------- per-emphasis arc + type
    for e in emphases:
        a = e["word_indices"][0]
        pos = _arc_position_of(arc, a)
        ztype = (e.get("zoom_effect") or {}).get("type")
        if pos in ("build", "breather"):
            r.fail("zoom-arc", f"zoom on {pos} word {a} — builds/breathers get no zoom")
        if pos == "payoff" and ztype == "StepZoom":
            r.fail("payoff-commitment", f"StepZoom on payoff word {a} — payoff requires SmoothPush/LetterboxPush")
        for ev in (e.get("zoom_effect") or {}).get("events", []):
            for forbidden in ("durationMs", "scale"):
                if forbidden in ev:
                    r.warn("zoom-omit-fields", f"event at word {a} emits {forbidden} (should omit; pipeline auto-fills)")

    # zoom variety
    ztypes = [(e.get("zoom_effect") or {}).get("type") for e in emphases if e.get("zoom_effect")]
    if ztypes:
        most, cnt = Counter(ztypes).most_common(1)[0]
        if len(ztypes) >= 3 and cnt / len(ztypes) > 0.6:
            r.fail("variety-zoom", f"{most} is {cnt}/{len(ztypes)} of zooms (>60%)")
        if len(set(ztypes)) < 2 and len(ztypes) >= 3:
            r.fail("variety-zoom", "only one zoom type across all emphases")

    # ----------------------------------------------------------- transitions
    boundary_set = set(cut_boundaries)
    seen_boundaries = set()
    prev_type = None
    for t in transitions:
        awi = t["after_word_index"]
        if awi not in boundary_set:
            r.fail("transition-boundary", f"after_word_index {awi} not in CUT BOUNDARIES {sorted(boundary_set)}")
        seen_boundaries.add(awi)
        if t["type"] == prev_type:
            r.fail("variety-transition", f"'{t['type']}' repeated back-to-back at word {awi}")
        prev_type = t["type"]
    for b in boundary_set - seen_boundaries:
        r.warn("transition-coverage", f"cut boundary at word {b} has no transition (valid only if mid-sentence flow or sub-800ms sandwich)")

    # ----------------------------------------------------------------- B-roll
    emphasis_words = {w for e in emphases if e.get("zoom_effect") for w in e["word_indices"]}
    overlay_ranges = [(o["start_word_index"],
                       o.get("end_word_index", o["start_word_index"]))
                      for o in overlays]
    mg_ranges = [(m["start_word_index"], m["end_word_index"]) for m in mgs]
    payoff_word = vp.get("payoff_word_index")
    close_word = vp.get("close_word_index")
    first_boundary = min(boundary_set) if boundary_set else None
    for b in brolls:
        s, e_ = b["start_word_index"], b["end_word_index"]
        covered = set(range(s, e_ + 1))
        if covered & emphasis_words:
            r.fail("broll-face", f"B-roll [{s}-{e_}] covers zoomed face word(s) {sorted(covered & emphasis_words)}")
        if payoff_word is not None and payoff_word in covered:
            r.fail("broll-payoff", f"B-roll [{s}-{e_}] covers the payoff word {payoff_word}")
        if close_word is not None and close_word in covered:
            r.fail("broll-close", f"B-roll [{s}-{e_}] covers the close word {close_word}")
        start_t = _word_time(words, s)
        hook_end = max((seg["end_word_index"] for seg in arc if seg["position"] == "hook"), default=-1)
        if (start_t is not None and start_t < 3.0) or s <= hook_end:
            r.fail("broll-opening", f"B-roll [{s}-{e_}] starts at {start_t}s / word {s} — the opening (~first 3s + hook) belongs to the speaker")
        for (os_, oe) in overlay_ranges + mg_ranges:
            if s <= oe and os_ <= e_:
                r.fail("broll-overlay-conflict", f"B-roll [{s}-{e_}] overlaps overlay/MG [{os_}-{oe}] — pipeline will drop the B-roll")
        pos = _arc_position_of(arc, s)
        if pos in ("hook", "payoff"):
            r.fail("broll-arc", f"B-roll [{s}-{e_}] starts in {pos}")
        wc = len(b.get("keyword", "").split())
        if not (8 <= wc <= 20):
            r.warn("broll-keyword", f"keyword is {wc} words (target 13-18): '{b.get('keyword','')[:60]}'")

    # ------------------------------------------------------------------- SFX
    # Build the set of word indices where a visual event lands.
    visual_words = set(emphasis_words)
    for t in transitions:
        visual_words.update({t["after_word_index"], t["after_word_index"] + 1})
    for s_, e_ in mg_ranges:
        visual_words.add(s_)
    for o in overlays:
        visual_words.add(o["start_word_index"])
    for b in brolls:
        visual_words.add(b["start_word_index"])
    for s in sfx:
        wi = s["word_index"]
        if wi not in visual_words:
            r.fail("sfx-partner", f"'{s['sound']}' at word {wi} has no visual partner on its trigger word")
        if _arc_position_of(arc, wi) == "breather":
            r.fail("sfx-breather", f"'{s['sound']}' at word {wi} lands on a breather")
    sounds = [s["sound"] for s in sfx]
    if sounds:
        if len(set(sounds)) < 3 and len(sounds) >= 4:
            r.fail("variety-sfx", f"only {len(set(sounds))} distinct sounds across {len(sounds)} SFX (need ≥3)")
        for once_only in ("boom", "drum_roll", "reverse"):
            if sounds.count(once_only) > 1:
                r.fail("sfx-once", f"'{once_only}' used {sounds.count(once_only)}× (max once)")
        most, cnt = Counter(sounds).most_common(1)[0]
        if cnt / len(sounds) > 0.6 and len(sounds) >= 4:
            r.fail("variety-sfx", f"'{most}' is {cnt}/{len(sounds)} of SFX (>60%)")

    # --------------------------------------------------------- THE WINDOW WALK
    # Collect visual events with output-relevant timestamps (word starts).
    events = []  # (time, kind, word)
    for e in emphases:
        if e.get("zoom_effect"):
            t = _word_time(words, e["word_indices"][0])
            if t is not None: events.append((t, "zoom", e["word_indices"][0]))
    for t_ in transitions:
        t = _word_time(words, t_["after_word_index"], "end")
        if t is not None: events.append((t, "transition", t_["after_word_index"]))
    for b in brolls:
        t = _word_time(words, b["start_word_index"])
        if t is not None: events.append((t, "broll", b["start_word_index"]))
    for m in mgs:
        t = _word_time(words, m["start_word_index"])
        if t is not None: events.append((t, "mg", m["start_word_index"]))
    for o in overlays:
        t = _word_time(words, o["start_word_index"])
        if t is not None: events.append((t, "overlay", o["start_word_index"]))

    end_t = words[-1]["end"] if words else duration
    n_windows = max(1, int(end_t // WINDOW_S) + 1)
    windows = defaultdict(list)
    for t, kind, w in events:
        windows[int(t // WINDOW_S)].append((kind, w))

    # Which windows are breathers / hook (by midpoint word)?
    def window_position(wi_idx):
        mid_t = wi_idx * WINDOW_S + WINDOW_S / 2
        for j, w in enumerate(words):
            if w["start"] <= mid_t <= w["end"] or w["start"] > mid_t:
                return _arc_position_of(arc, j)
        return _arc_position_of(arc, n_words - 1)

    empty, stacked = [], []
    for i in range(n_windows):
        evs = windows.get(i, [])
        pos = window_position(i)
        kinds = [k for k, _ in evs]
        # composed pair: transition + zoom = one event; hook window: zoom + overlay allowed
        effective = len(evs)
        if "transition" in kinds and "zoom" in kinds:
            effective -= 1
        if pos == "hook" and "zoom" in kinds and "overlay" in kinds:
            effective -= 1
        if pos == "breather":
            if evs:
                r.fail("window-breather", f"window {i} ({i*2}-{i*2+2}s) is a breather but has {evs}")
        elif effective == 0:
            empty.append(i)
        elif effective > 1:
            stacked.append((i, evs))

    for i, evs in stacked:
        r.fail("window-stacked", f"window {i} ({i*2}-{i*2+2}s) has {len(evs)} events: {evs}")
    if len(empty) > max(1, n_windows // 5):
        r.warn("window-empty", f"{len(empty)} non-breather windows empty: {empty} — thin unless the dialogue truly offered nothing")

    r.stats = {
        "runtime_windows": n_windows,
        "visual_events": len(events),
        "events_per_window": round(len(events) / n_windows, 2),
        "zooms/transitions/broll/mgs/overlays/sfx":
            f"{len(emphases)}/{len(transitions)}/{len(brolls)}/{len(mgs)}/{len(overlays)}/{len(sfx)}",
        "empty_windows": len(empty),
        "stacked_windows": len(stacked),
    }
    return r


if __name__ == "__main__":
    import json, sys
    # quick CLI: python recipe_eval.py plan.json words.json boundaries.json
    plan = json.load(open(sys.argv[1]))
    words = json.load(open(sys.argv[2]))
    boundaries = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else []
    dur = words[-1]["end"] if words else 0.0
    print(evaluate_recipe(plan, words, boundaries, dur).summary())
