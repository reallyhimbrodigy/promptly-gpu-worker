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

No third-party deps. Shares the type_registries source of truth (a local module)
so component whitelists can't drift out of the eval. Every check maps to a named
rule in the prompt so when quality drifts you know WHICH rule drifted.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from type_registries import VALID_TIGHT_CUT_OVERLAYS

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


def evaluate_recipe(plan, words, cut_boundaries, duration, tight_boundaries=None):
    """Evaluate a Gemini edit recipe against the window doctrine + hard rules.

    cut_boundaries     — slots-only list (boundaries with enough handle room
                         for a transition). Gemini may place transitions
                         only at these indices.
    tight_boundaries   — real cuts with no handle room. Gemini sees them as
                         awareness-only (per the user-message TIGHT BOUNDARIES
                         block) — must NOT place transitions here, but should
                         mask each with a zoom on the immediately-following
                         word to hide the jump.

    Passing tight_boundaries=None preserves the pre-tight-awareness behavior:
    only the slots check runs and the new tight-mask warning is skipped.
    """
    r = Report()
    vp = plan.get("video_plan") or {}
    arc = vp.get("arc_segments") or []
    key_moments = vp.get("key_moments") or []
    emphases = plan.get("emphasis_moments") or []
    transitions = plan.get("transitions") or []
    tight_overlays = plan.get("tight_cut_overlays") or []
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
    # boundary_set is SLOTS-ONLY (handle-room verified). tight_set is real
    # cuts that render as hard cuts. A transition emitted at a tight index
    # would be dropped by the renderer's handle check — the eval flags
    # this distinctly so the failure points to the right fix (re-anchor
    # the transition to a slot, or replace with a masking zoom).
    boundary_set = set(cut_boundaries)
    tight_set = set(tight_boundaries or [])
    seen_boundaries = set()
    prev_type = None
    for t in transitions:
        awi = t["after_word_index"]
        if awi in tight_set:
            r.fail("transition-tight-boundary", f"transition '{t['type']}' at word {awi} — boundary is TIGHT (no handle room); renderer will drop it. Replace with a masking zoom on word {awi + 1}.")
        elif awi not in boundary_set:
            r.fail("transition-boundary", f"after_word_index {awi} not in CUT BOUNDARIES {sorted(boundary_set)}")
        seen_boundaries.add(awi)
        if t["type"] == prev_type:
            r.fail("variety-transition", f"'{t['type']}' repeated back-to-back at word {awi}")
        prev_type = t["type"]
    for b in boundary_set - seen_boundaries:
        r.warn("transition-coverage", f"cut boundary at word {b} has no transition (valid only if mid-sentence flow or sub-800ms sandwich)")

    # ─────────────────────────────────────────────── tight-cut overlay caps
    # Overlay-on-top-of-hard-cut decoration for TIGHT BOUNDARIES. Hard rules
    # (from the HOW TO PLACE TIGHT-CUT OVERLAYS section of the prompt):
    #   • after_word_index must be a TIGHT boundary (the field is for tight
    #     cuts; CUT boundaries already get full transitions)
    #   • type must be "LightLeak" or "ShutterFlash" (no others wired)
    #   • per-video cap of 2 — sparing keeps the overlay editorial, not
    #     templated
    #   • if 2 are emitted, prefer distinct types (warning, not failure —
    #     same type twice can be right if the editorial character actually
    #     matches)
    if tight_overlays:
        _VALID_TCO_TYPES = set(VALID_TIGHT_CUT_OVERLAYS)  # derive; no hardcoded copy
        _TCO_CAP = 2  # across ALL types combined — sparing is the whole point
        if len(tight_overlays) > _TCO_CAP:
            r.fail(
                "tight-overlay-cap",
                f"{len(tight_overlays)} tight_cut_overlays emitted (max {_TCO_CAP} per video "
                f"across all types — sparing keeps the overlay editorial, not templated)",
            )
        _tco_types_seen = []
        for tco in tight_overlays:
            tco_type = (tco or {}).get("type")
            tco_awi = (tco or {}).get("after_word_index")
            tco_title = (tco or {}).get("title")
            tco_label = (tco or {}).get("label")
            if tco_type not in _VALID_TCO_TYPES:
                r.fail(
                    "tight-overlay-type",
                    f"tight_cut_overlay type {tco_type!r} not in {sorted(_VALID_TCO_TYPES)}",
                )
            # SceneTitle requires a title; the other three forbid title/label.
            # Mirrors the handler.py application-layer enforcement so
            # misuses surface at eval time too (observability before the
            # render rejects them).
            if tco_type == "SceneTitle":
                if not (isinstance(tco_title, str) and tco_title.strip()):
                    r.fail(
                        "tight-overlay-scenetitle-title",
                        f"SceneTitle tight_cut_overlay at word {tco_awi} is missing "
                        f"a `title` — the typographic panel requires 1-3 uppercase words.",
                    )
            elif tco_type in _VALID_TCO_TYPES:
                # LightLeak / ShutterFlash / NewspaperWipe: extras forbidden.
                _bad_extras = []
                if tco_title not in (None, ""):
                    _bad_extras.append("title")
                if tco_label not in (None, ""):
                    _bad_extras.append("label")
                if _bad_extras:
                    r.fail(
                        "tight-overlay-extras-misuse",
                        f"{tco_type} tight_cut_overlay at word {tco_awi} carries "
                        f"{_bad_extras} — only SceneTitle uses title/label.",
                    )
            if tco_awi is None:
                r.fail("tight-overlay-anchor", "tight_cut_overlay missing after_word_index")
                continue
            if tco_awi in boundary_set:
                # Wrong boundary type — Gemini placed the overlay at a CUT
                # boundary (which already gets a full transition).
                r.fail(
                    "tight-overlay-boundary",
                    f"tight_cut_overlay {tco_type!r} at word {tco_awi} — that's a CUT "
                    f"BOUNDARY (transitions live there). Move it to a TIGHT BOUNDARY.",
                )
            elif tco_awi not in tight_set:
                r.fail(
                    "tight-overlay-boundary",
                    f"tight_cut_overlay {tco_type!r} at word {tco_awi} — not in TIGHT "
                    f"BOUNDARIES {sorted(tight_set)}",
                )
            _tco_types_seen.append(tco_type)
        if len(_tco_types_seen) == 2 and _tco_types_seen[0] == _tco_types_seen[1]:
            r.warn(
                "tight-overlay-variety",
                f"both tight_cut_overlays use type {_tco_types_seen[0]!r} — prefer two "
                f"different types unless both moments genuinely earn the same character "
                f"(two SceneTitles in one video is almost always wrong — a video usually "
                f"has at most one true chapter break worth labeling).",
            )

    # ──────────────────────────────────────────────── tight-boundary masking
    # Prompt rule: "land a zoom on the first word after a tight cut to mask
    # the jump." Warn for every tight boundary whose following word doesn't
    # carry a zoom emphasis. This catches the same-spot-splice case where
    # the cut WAS surfaced to Gemini but no masking treatment was placed.
    if tight_set:
        zoom_anchor_indices = {
            (e.get("word_indices") or [None])[0]
            for e in emphases
            if e.get("zoom_effect")
        }
        for tb in sorted(tight_set):
            mask_word = tb + 1
            if mask_word >= n_words:
                continue
            if mask_word not in zoom_anchor_indices:
                r.warn("tight-no-mask", f"tight cut at word {tb} has no masking zoom on word {mask_word} — jump will read as broken editing")

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
        # composed pairs: transition+zoom = one; zoom+MG on the same beat = one;
        # hook window: zoom + overlay allowed
        effective = len(evs)
        if "transition" in kinds and "zoom" in kinds:
            effective -= 1
        if "zoom" in kinds and "mg" in kinds:
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
    if len(empty) > max(1, n_windows // 4):
        r.fail("window-empty", f"{len(empty)}/{n_windows} non-breather windows empty: {empty} — under-mined")
    elif empty:
        r.warn("window-empty", f"{len(empty)} non-breather windows empty: {empty}")

    # max dead gap between consecutive visual events (thinness killer metric)
    ev_times = sorted([t for t, _, _ in events]) + [end_t]
    prev_t, max_gap, gap_at = 0.0, 0.0, 0.0
    for t in ev_times:
        if t - prev_t > max_gap:
            max_gap, gap_at = t - prev_t, prev_t
        prev_t = t
    r.stats_max_gap = round(max_gap, 1)
    if max_gap > 4.0:
        r.fail("dead-zone", f"{max_gap:.1f}s with no visual event starting at {gap_at:.1f}s — the swipe happens here")

    # breather budget: each ≤3.0s, total ≤20% of runtime
    breather_total = 0.0
    for seg in arc:
        if seg["position"] == "breather":
            bs = _word_time(words, seg["start_word_index"]) or 0.0
            be = _word_time(words, seg["end_word_index"], "end") or bs
            d = be - bs
            breather_total += d
            if d > 3.0:
                r.fail("breather-budget", f"breather [{seg['start_word_index']}-{seg['end_word_index']}] runs {d:.1f}s (max ~2.5s) — that's build wearing a disguise")
    if end_t > 0 and breather_total / end_t > 0.20:
        r.fail("breather-budget", f"breathers total {breather_total:.1f}s = {breather_total/end_t*100:.0f}% of runtime (max ~15%)")

    # caption keyword density for keyword styles
    KEYWORD_STYLES = {"Prime", "Cove", "EditorialPop", "Illuminate", "Lumen", "Passage", "Pulse", "Serif"}
    if plan.get("caption_style") in KEYWORD_STYLES:
        kw = len(plan.get("caption_keywords") or [])
        floor = n_words // 5  # hard floor: 1 per 5 words (target 1 per 3-4)
        if kw < floor:
            r.fail("keyword-density", f"{kw} keywords for {n_words} words on keyword style '{plan['caption_style']}' — floor is {floor} (target ~{n_words//4}-{n_words//3})")

    r.stats = {
        "runtime_windows": n_windows,
        "visual_events": len(events),
        "events_per_window": round(len(events) / n_windows, 2),
        "zooms/transitions/broll/mgs/overlays/sfx":
            f"{len(emphases)}/{len(transitions)}/{len(brolls)}/{len(mgs)}/{len(overlays)}/{len(sfx)}",
        "tight_cut_overlays": len(tight_overlays),
        "empty_windows": len(empty),
        "stacked_windows": len(stacked),
        "max_dead_gap_s": getattr(r, "stats_max_gap", 0.0),
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
