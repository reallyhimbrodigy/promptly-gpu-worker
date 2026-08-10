#!/usr/bin/env python3
"""
harness_plan_diff.py — the golden-output plan differ (LANE 2 / HARNESS).

Judges PLANS, not pixels. Compares a candidate set of editorial plans against
the frozen golden ENVELOPE (3 stochastic runs per source, stored under
golden/plans/<source_id>/run*.json) and emits a single machine-readable
verdict: GREEN / YELLOW / RED.

Why this exists: the determinism certs lock "same plan -> same bytes", which by
construction cannot detect a WORSE plan. Every editorial defect in this
codebase's history (payoff-zoom enum 0/253, six MGs unreachable 0/709) was a
plan-level distribution collapse — exactly what this differ measures.

Zero Modal, zero Gemini, zero network. Python 3.9-compatible (modal CLI runs
3.9 — no X|Y unions here).

Usage:
  python3 harness_plan_diff.py self-test
  python3 harness_plan_diff.py diff --golden golden/plans --candidate <dir> \
      --manifest golden/manifest.json [--out report.json]
  python3 harness_plan_diff.py baseline --golden golden/plans \
      --manifest golden/manifest.json [--out golden/baseline_report.json]

Input file shape: either a raw PLAN_ONLY seam return
({"status": "plan_only", "edit_plan": {...}, "source_duration_s": ...}) or a
bare edit_plan dict. Light-route captures use {"route": "...", "plan": {...}}.

Frozen enums below are the reference behavior at live commit 1601ae0 — they
are the GOLDEN's vocabulary, deliberately not imported from handler.py (the
differ must judge a candidate against what WAS true, not what the candidate's
handler now claims).
"""
import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Frozen reference enums @ 1601ae0
# ---------------------------------------------------------------------------
# [CODE] handler.py:1494-1501 (_ArcPosition — six values, incl. breather)
ARC_POSITIONS = ("hook", "build", "mid_peak", "payoff", "breather", "close")
# [CODE] type_registries.py:104-114 (VALID_ZOOM_TYPES)
ZOOM_TYPES = ("SmoothPush", "SnapReframe", "FocusWindow", "StepZoom",
              "LetterboxPush", "DepthPull", "StagedPush")
# [CODE] handler.py:858-877 (ZOOM_ARC_HOMES — which zoom is sayable where)
ZOOM_ARC_HOMES = {
    "hook": ("DepthPull", "SnapReframe", "StepZoom", "SmoothPush"),
    "mid_peak": ("FocusWindow", "SnapReframe", "StepZoom", "StagedPush", "SmoothPush"),
    "payoff": ("LetterboxPush", "SmoothPush"),
    "close": ("SmoothPush", "SnapReframe", "StepZoom"),
    "build": ("SnapReframe", "StepZoom"),
    "breather": ("SnapReframe", "StepZoom"),
}
# [CODE] type_registries.py:29-45 (VALID_CAPTION_STYLES, 9 real + none)
CAPTION_STYLES = ("Prime", "TypewriterReveal", "Cove", "Lumen", "Pulse",
                  "Quintessence", "TwoTone", "CleanCut", "Gadzhi", "none")
# [CODE] handler.py:1228-1268 (_EmphasisMoment.type)
EMPHASIS_TYPES = ("punchline", "statement", "question", "reaction", "revelation")
# [CODE] type_registries.py:117-127 (VALID_MG_TYPES, 26)
MG_TYPES = ("AnnotationArrow", "ChatThread", "Notification", "ProgressBar",
            "RecordingFrame", "StatCard", "StickyNotes", "TweetBubble",
            "InstagramComment", "IMessageBubble", "TikTokComment", "Timeline",
            "Reticle", "RankedList", "PullQuote", "PillCluster", "Stamp",
            "BarRace", "SectionDivider", "EditorialQuote", "StepDivider",
            "DropBanner", "DropCard", "PillMarquee", "TimelineRoadmap",
            "MouseDrag")
# [CODE] handler.py:1160-1179 (_SFX_SOUNDS 15 + "voice")
SFX_SOUNDS = ("boom", "punchsfx", "swoosh-sound-effects", "woosh-professional",
              "transition-sfx", "camera-flash", "money-ching", "iphoneding",
              "mouse-click-sound", "popsfx", "rizz", "shockingsfx",
              "awkward-moment", "wompwomp", "imposter")
SOUND_DECISIONS = SFX_SOUNDS + ("voice",)
# [CODE] type_registries.py:47-51 (VALID_TRANSITION_TYPES, 9)
TRANSITION_TYPES = ("CardSwipe", "ZoomThrough", "SlideOver", "Stack",
                    "CrossfadeZoom", "ShutterFlash", "StepPush", "FilmStrip",
                    "DipToBlack")
# [CODE] handler.py:1150-1152
TEXT_OVERLAY_VARIANTS = ("sticky_note", "caption_match")

# Component families the differ tracks (presence + density per source).
FAMILIES = ("captions", "zooms", "emphasis", "motion_graphics",
            "text_overlays", "broll", "transitions", "sfx")

# A distribution class must appear in goldens on >= this many sources for its
# corpus-wide death to be a RED (below that, absence is within noise).
DEATH_MIN_SOURCES = 3

VERDICT_ORDER = {"GREEN": 0, "YELLOW": 1, "RED": 2}


# ---------------------------------------------------------------------------
# Plan loading + metric extraction
# ---------------------------------------------------------------------------
def load_plan_file(path):
    """Returns (plan_dict_or_None, meta) — meta carries route/duration if the
    file is a seam return or light-route capture rather than a bare plan."""
    with open(path) as f:
        raw = json.load(f)
    meta = {}
    if not isinstance(raw, dict):
        return None, meta
    if "edit_plan" in raw:  # PLAN_ONLY seam return [CODE] handler.py:37727
        meta["route"] = "editorial"
        meta["source_duration_s"] = raw.get("source_duration_s")
        plan = raw.get("edit_plan")
        return (plan if isinstance(plan, dict) else None), meta
    if "route" in raw and "plan" in raw:  # light-route capture
        meta["route"] = raw.get("route")
        meta["source_duration_s"] = raw.get("source_duration_s")
        plan = raw.get("plan")
        return (plan if isinstance(plan, dict) else None), meta
    return raw, meta


def _as_list(x):
    return x if isinstance(x, list) else []


def extract_metrics(plan, duration_s):
    """One run's plan -> flat metric dict. Never raises on malformed input —
    structural problems land in metrics['structural_fails']."""
    m = {
        "counts": {f: 0 for f in FAMILIES},
        "dist": {"arc_position": {}, "zoom_type": {}, "arc_zoom_pair": {},
                 "caption_style": {}, "emphasis_type": {}, "mg_type": {},
                 "transition_type": {}, "sound": {}},
        "structural_fails": [],
        "structural_warns": [],
        "density": {},
    }

    def bump(dist, key):
        m["dist"][dist][key] = m["dist"][dist].get(key, 0) + 1

    if not isinstance(plan, dict) or not plan:
        m["structural_fails"].append("plan is empty or not a dict")
        return m
    if plan.get("_unserializable"):
        m["structural_fails"].append(
            "plan is an _unserializable tombstone: %s" % plan.get("_unserializable"))
        return m

    # Core required keys [CODE] handler.py:1627-1707 (PostCutPlan)
    for key in ("video_plan", "caption_style", "emphasis_moments"):
        if key not in plan:
            m["structural_fails"].append("missing required key %r" % key)

    style = plan.get("caption_style")
    if style is not None:
        if style not in CAPTION_STYLES:
            m["structural_fails"].append("unknown caption_style %r" % style)
        else:
            bump("caption_style", style)
        if style != "none":
            m["counts"]["captions"] = 1

    for e in _as_list(plan.get("emphasis_moments")):
        if not isinstance(e, dict):
            m["structural_fails"].append("emphasis moment is not a dict")
            continue
        m["counts"]["emphasis"] += 1
        etype = e.get("type")
        if etype is not None:
            if etype not in EMPHASIS_TYPES:
                m["structural_fails"].append("unknown emphasis type %r" % etype)
            else:
                bump("emphasis_type", etype)
        wi = e.get("word_indices")
        if wi is not None and (not isinstance(wi, list) or
                               any(not isinstance(w, int) or w < 0 for w in wi)):
            m["structural_fails"].append("emphasis word_indices not non-negative ints: %r" % (wi,))
        z = e.get("zoom_effect")
        if isinstance(z, dict):
            m["counts"]["zooms"] += 1
            ztype, arc = z.get("type"), z.get("arc_position")
            if ztype is not None and ztype not in ZOOM_TYPES:
                m["structural_fails"].append("unknown zoom type %r" % ztype)
            else:
                if ztype:
                    bump("zoom_type", ztype)
            if arc is not None and arc not in ARC_POSITIONS:
                m["structural_fails"].append("unknown arc_position %r" % arc)
            else:
                if arc:
                    bump("arc_position", arc)
            if ztype in ZOOM_TYPES and arc in ARC_POSITIONS:
                bump("arc_zoom_pair", "%s:%s" % (arc, ztype))
                # Sayability is a recipe_eval WARN in prod [CODE] handler.py:858-861
                if ztype not in ZOOM_ARC_HOMES[arc]:
                    m["structural_warns"].append(
                        "zoom %s claims arc %s outside ZOOM_ARC_HOMES" % (ztype, arc))
        mg = e.get("motion_graphic")
        if isinstance(mg, dict):
            m["counts"]["motion_graphics"] += 1
            mgt = mg.get("type")
            if mgt is not None:
                if mgt not in MG_TYPES:
                    m["structural_fails"].append("unknown emphasis MG type %r" % mgt)
                else:
                    bump("mg_type", mgt)
        snd = e.get("sound")
        if snd is not None:
            if snd not in SOUND_DECISIONS:
                m["structural_fails"].append("unknown sound %r" % snd)
            else:
                bump("sound", snd)
                if snd != "voice":
                    m["counts"]["sfx"] += 1

    for g in _as_list(plan.get("motion_graphics")):
        if not isinstance(g, dict):
            continue
        m["counts"]["motion_graphics"] += 1
        mgt = g.get("type")
        if mgt is not None:
            if mgt not in MG_TYPES:
                m["structural_fails"].append("unknown MG type %r" % mgt)
            else:
                bump("mg_type", mgt)

    for o in _as_list(plan.get("text_overlays")):
        if isinstance(o, dict):
            m["counts"]["text_overlays"] += 1

    for b in _as_list(plan.get("broll_clips")):
        if isinstance(b, dict):
            m["counts"]["broll"] += 1

    for t in _as_list(plan.get("transitions")):
        if not isinstance(t, dict):
            continue
        m["counts"]["transitions"] += 1
        tt = t.get("type")
        if tt is not None:
            if tt not in TRANSITION_TYPES:
                m["structural_fails"].append("unknown transition type %r" % tt)
            else:
                bump("transition_type", tt)

    for s in _as_list(plan.get("sound_effects")):  # legacy standalone array
        if isinstance(s, dict):
            m["counts"]["sfx"] += 1

    vp = plan.get("video_plan")
    if isinstance(vp, dict):
        for seg in _as_list(vp.get("arc_segments")):
            if isinstance(seg, dict):
                pos = seg.get("position")
                if pos is not None and pos not in ARC_POSITIONS:
                    m["structural_fails"].append("unknown arc_segment position %r" % pos)
    elif vp is not None:
        m["structural_fails"].append("video_plan is not a dict")

    minutes = (duration_s / 60.0) if duration_s else None
    if minutes and minutes > 0:
        m["density"] = {f: m["counts"][f] / minutes for f in FAMILIES}
    return m


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------
def build_envelope(runs_by_source, manifest):
    """runs_by_source: {source_id: [metrics, ...]} (goldens, >=1 run each).
    Returns the envelope: per-source count bands + corpus-level class support."""
    env = {"per_source": {}, "corpus": {
        "family_sources": {f: set() for f in FAMILIES},
        "class_sources": {d: {} for d in ("arc_position", "zoom_type",
                                          "arc_zoom_pair", "caption_style",
                                          "emphasis_type", "mg_type",
                                          "transition_type", "sound")},
        "n_sources": len(runs_by_source),
    }}
    for sid, runs in runs_by_source.items():
        bands = {}
        for f in FAMILIES:
            vals = [r["counts"][f] for r in runs]
            lo, hi = min(vals), max(vals)
            spread = max(1, hi - lo)
            # 3 runs under-sample the true variance; pad by the observed
            # spread (>=1) on both sides, and never demand a negative floor.
            bands[f] = {"lo": max(0, lo - spread), "hi": hi + spread,
                        "observed": vals}
        env["per_source"][sid] = {
            "bands": bands,
            "fired": {f: any(r["counts"][f] > 0 for r in runs) for f in FAMILIES},
            "always_fired": {f: all(r["counts"][f] > 0 for r in runs) for f in FAMILIES},
            "n_runs": len(runs),
        }
        for f in FAMILIES:
            if any(r["counts"][f] > 0 for r in runs):
                env["corpus"]["family_sources"][f].add(sid)
        for dist, table in env["corpus"]["class_sources"].items():
            for r in runs:
                for cls in r["dist"][dist]:
                    table.setdefault(cls, set()).add(sid)
    return env


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------
def _item(items, level, dimension, detail, source_id=None):
    row = {"level": level, "dimension": dimension, "detail": detail}
    if source_id is not None:
        row["source_id"] = source_id
    items.append(row)


def diff(env, cand_by_source, manifest):
    """Compare candidate runs against the golden envelope.
    Every evaluated dimension is counted; verdict = worst item level.
    Returns the machine-readable report dict."""
    items = []
    dims_total = 0
    obedience_by_source = {}
    for src in manifest.get("sources", []):
        if src.get("obedience"):
            obedience_by_source[src["id"]] = src["obedience"]

    missing = sorted(set(env["per_source"]) - set(cand_by_source))
    for sid in missing:
        dims_total += 1
        _item(items, "RED", "coverage",
              "candidate has no runs for golden source", sid)

    # --- per-source dimensions -------------------------------------------
    for sid, runs in sorted(cand_by_source.items()):
        if sid not in env["per_source"]:
            dims_total += 1
            _item(items, "YELLOW", "coverage",
                  "candidate source not in golden corpus (ignored by bands)", sid)
            continue
        e = env["per_source"][sid]

        # structural: every candidate run must be structurally sound
        dims_total += 1
        fails = [f for r in runs for f in r["structural_fails"]]
        if fails:
            _item(items, "RED", "structural",
                  "; ".join(sorted(set(fails))[:6]), sid)
        warns = [w for r in runs for w in r["structural_warns"]]
        if warns and not fails:
            _item(items, "YELLOW", "structural-warn",
                  "; ".join(sorted(set(warns))[:4]), sid)

        # density bands per family
        for f in FAMILIES:
            band = e["bands"][f]
            dims_total += 1
            vals = [r["counts"][f] for r in runs]
            out = [v for v in vals if v < band["lo"] or v > band["hi"]]
            if not out:
                continue
            # total per-source loss of an always-firing family is stronger
            # than a band miss, but still per-source: YELLOW (corpus-level
            # death below is the RED).
            _item(items, "YELLOW", "density",
                  "%s count %r outside golden band [%d,%d] (golden runs %r)"
                  % (f, vals, band["lo"], band["hi"], band["observed"]), sid)

        # obedience markers (explicit vibe asks)
        for marker in obedience_by_source.get(sid, []):
            dims_total += 1
            ok, golden_ok, desc = _eval_marker(marker, runs, e)
            if not golden_ok:
                _item(items, "YELLOW", "obedience",
                      "golden itself does not satisfy marker %s — excluded" % desc, sid)
            elif not ok:
                _item(items, "RED", "obedience",
                      "candidate misses marker %s that every golden run satisfied" % desc, sid)

    # --- corpus-level dimensions -----------------------------------------
    cand_family_sources = {f: set() for f in FAMILIES}
    cand_class_sources = {d: {} for d in env["corpus"]["class_sources"]}
    for sid, runs in cand_by_source.items():
        for f in FAMILIES:
            if any(r["counts"][f] > 0 for r in runs):
                cand_family_sources[f].add(sid)
        for dist in cand_class_sources:
            for r in runs:
                for cls in r["dist"][dist]:
                    cand_class_sources[dist].setdefault(cls, set()).add(sid)

    for f in FAMILIES:
        g = env["corpus"]["family_sources"][f]
        dims_total += 1
        if len(g) >= DEATH_MIN_SOURCES and not cand_family_sources[f]:
            _item(items, "RED", "family-death",
                  "family %s fired on %d/%d golden sources but 0 candidate sources"
                  % (f, len(g), env["corpus"]["n_sources"]))
        elif len(g) >= DEATH_MIN_SOURCES:
            gshare = len(g)
            cshare = len(cand_family_sources[f])
            if cshare < gshare * 0.5:
                _item(items, "YELLOW", "family-drift",
                      "family %s fired on %d golden sources but only %d candidate sources"
                      % (f, gshare, cshare))

    for dist, table in env["corpus"]["class_sources"].items():
        for cls, srcs in sorted(table.items()):
            if len(srcs) < DEATH_MIN_SOURCES:
                continue
            dims_total += 1
            cand_srcs = cand_class_sources[dist].get(cls, set())
            if not cand_srcs:
                _item(items, "RED", "class-death",
                      "%s=%s appeared on %d golden sources but 0 candidate sources "
                      "(the payoff-enum defect class)" % (dist, cls, len(srcs)))
            elif len(cand_srcs) < len(srcs) * 0.4:
                _item(items, "YELLOW", "class-drift",
                      "%s=%s fell from %d golden sources to %d candidate sources"
                      % (dist, cls, len(srcs), len(cand_srcs)))

    dims_red = sum(1 for i in items if i["level"] == "RED")
    dims_yellow = sum(1 for i in items if i["level"] == "YELLOW")
    verdict = "RED" if dims_red else ("YELLOW" if dims_yellow else "GREEN")
    return {
        "verdict": verdict,
        "defect_rate": (dims_red / dims_total) if dims_total else 0.0,
        "dims_total": dims_total,
        "dims_red": dims_red,
        "dims_yellow": dims_yellow,
        "items": sorted(items, key=lambda i: -VERDICT_ORDER[i["level"]]),
    }


def _eval_marker(marker, cand_runs, env_src):
    """Returns (candidate_ok, golden_ok, description). golden_ok is derived
    from the envelope's fired/always_fired tables where possible."""
    kind = marker.get("check")
    if kind == "family_min":
        fam, lo = marker["family"], int(marker.get("min", 1))
        desc = "family_min(%s>=%d)" % (fam, lo)
        golden_ok = env_src["always_fired"].get(fam, False) if lo > 0 else True
        ok = all(r["counts"].get(fam, 0) >= lo for r in cand_runs)
        return ok, golden_ok, desc
    if kind == "class_present":
        dist, value = marker["dist"], marker["value"]
        desc = "class_present(%s=%s)" % (dist, value)
        golden_ok = bool(marker.get("golden_satisfies", True))
        ok = all(value in r["dist"].get(dist, {}) for r in cand_runs)
        return ok, golden_ok, desc
    if kind == "family_absent":
        fam = marker["family"]
        desc = "family_absent(%s)" % fam
        golden_ok = not env_src["fired"].get(fam, False)
        ok = all(r["counts"].get(fam, 0) == 0 for r in cand_runs)
        return ok, golden_ok, desc
    return False, False, "unknown-marker(%r)" % (kind,)


# ---------------------------------------------------------------------------
# Directory loading
# ---------------------------------------------------------------------------
def load_run_dir(root, manifest):
    """golden/plans layout: <root>/<source_id>/run*.json ->
    {source_id: [metrics...]}. Duration comes from the run file when the seam
    recorded it, else from the manifest."""
    durations = {s["id"]: s.get("duration_s")
                 for s in manifest.get("sources", [])}
    out = {}
    if not os.path.isdir(root):
        raise FileNotFoundError("run dir missing: %s" % root)
    for sid in sorted(os.listdir(root)):
        sdir = os.path.join(root, sid)
        if not os.path.isdir(sdir):
            continue
        runs = []
        for fn in sorted(os.listdir(sdir)):
            if not fn.endswith(".json"):
                continue
            plan, meta = load_plan_file(os.path.join(sdir, fn))
            dur = meta.get("source_duration_s") or durations.get(sid)
            runs.append(extract_metrics(plan, dur))
        if runs:
            out[sid] = runs
    return out


def load_manifest(path):
    with open(path) as f:
        mf = json.load(f)
    assert isinstance(mf.get("sources"), list) and mf["sources"], \
        "manifest has no sources"
    ids = [s["id"] for s in mf["sources"]]
    assert len(ids) == len(set(ids)), "duplicate source ids in manifest"
    return mf


# ---------------------------------------------------------------------------
# Self-test — the non-vacuity core. Synthetic fixtures; asserts the differ
# actually goes RED on each planted defect class and GREEN on clean input.
# ---------------------------------------------------------------------------
def _fixture_plan(seed, payoff=True, mg=True, styles=("Prime", "Gadzhi")):
    """A structurally valid plan; `seed` perturbs counts like run variance."""
    emphasis = [
        {"word_indices": [3], "type": "statement", "intensity": "high",
         "duration": 2.0, "viewer_feeling": "locked in",
         "zoom_effect": {"type": "SnapReframe", "arc_position": "hook"},
         "sound": "boom"},
        {"word_indices": [11], "type": "punchline", "intensity": "medium",
         "duration": 1.8, "viewer_feeling": "payoff lands",
         "zoom_effect": ({"type": "LetterboxPush", "arc_position": "payoff"}
                         if payoff else
                         {"type": "StepZoom", "arc_position": "build"}),
         "sound": "voice"},
    ]
    if seed % 2:
        emphasis.append(
            {"word_indices": [17], "type": "revelation", "intensity": "high",
             "duration": 2.2, "viewer_feeling": "whoa",
             "zoom_effect": {"type": "SmoothPush", "arc_position": "mid_peak"},
             "sound": "popsfx"})
    plan = {
        "video_identity": "fixture",
        "video_plan": {"what_happens": "x", "hook_word_index": 0,
                       "payoff_word_index": 11, "close_word_index": 20,
                       "key_moments": [], "story_shape": "x",
                       "arc_segments": [
                           {"start_word_index": 0, "end_word_index": 10,
                            "position": "hook", "intensity": 0.8},
                           {"start_word_index": 11, "end_word_index": 20,
                            "position": "payoff", "intensity": 1.0}],
                       "movements": [], "editorial_vision": "x"},
        "caption_style": styles[seed % len(styles)],
        "caption_keywords": ["one"],
        "emphasis_moments": emphasis,
        "motion_graphics": ([{"type": "StatCard", "why": "n",
                              "start_word_index": 5, "end_word_index": 9,
                              "duration_seconds": None,
                              "anchor": "upper_third_safe", "props": {}}]
                            if mg else []),
        "text_overlays": [],
        "broll_clips": [{"keyword": "city", "start_word_index": 6,
                         "end_word_index": 8, "reason": "cover"}],
        "cut_refinements": [],
        "thumbnail_word_index": 3,
        "audio_denoise": False,
        "outro": "none",
        "aspect_ratio": "9:16",
    }
    return plan


def _fixture_corpus(n_sources=5, payoff=True, mg=True):
    out = {}
    for i in range(n_sources):
        sid = "src%02d" % i
        runs = []
        for seed in range(3):
            plan = _fixture_plan(seed + i, payoff=payoff, mg=mg)
            runs.append(extract_metrics(plan, 60.0))
        out[sid] = runs
    return out


def self_test(verbose=False):
    """Non-vacuity built in: a clean candidate must be GREEN, and each planted
    defect class must go RED. Raises AssertionError on any miss."""
    manifest = {"sources": [
        {"id": "src%02d" % i, "duration_s": 60.0} for i in range(5)]}
    manifest["sources"][0]["obedience"] = [
        {"check": "family_min", "family": "motion_graphics", "min": 1}]
    golden = _fixture_corpus()
    env = build_envelope(golden, manifest)

    # 1. clean candidate (goldens vs themselves) -> GREEN
    r = diff(env, _fixture_corpus(), manifest)
    assert r["verdict"] == "GREEN", "clean candidate not GREEN: %r" % (r["items"][:3],)
    assert r["defect_rate"] == 0.0

    # 2. moment-class death: payoff arm rerouted -> class-death RED
    #    (the 0/253 payoff-enum defect class)
    r = diff(env, _fixture_corpus(payoff=False), manifest)
    assert r["verdict"] == "RED", "payoff death not RED"
    assert any(i["dimension"] == "class-death" and "payoff" in i["detail"]
               for i in r["items"]), "payoff class-death not itemized: %r" % (r["items"][:5],)

    # 3. family death: MGs zeroed everywhere -> family-death RED
    #    (obedience marker on src00 also fires)
    r = diff(env, _fixture_corpus(mg=False), manifest)
    assert r["verdict"] == "RED", "MG family death not RED"
    assert any(i["dimension"] == "family-death" and "motion_graphics" in i["detail"]
               for i in r["items"]), "MG family-death not itemized"
    assert any(i["dimension"] == "obedience" for i in r["items"]), \
        "obedience miss not itemized"

    # 4. structural fail: corrupt plan -> RED
    bad = _fixture_corpus()
    bad["src01"] = [extract_metrics({"garbage": True}, 60.0)]
    r = diff(env, bad, manifest)
    assert r["verdict"] == "RED", "structural corruption not RED"
    assert any(i["dimension"] == "structural" for i in r["items"])

    # 5. unknown enum value (schema drift / fabrication) -> RED
    drift = _fixture_corpus()
    p = _fixture_plan(0)
    p["emphasis_moments"][0]["zoom_effect"]["type"] = "MegaZoom"
    drift["src02"] = [extract_metrics(p, 60.0)]
    r = diff(env, drift, manifest)
    assert r["verdict"] == "RED", "unknown enum not RED"

    # 6. missing source -> coverage RED
    partial = _fixture_corpus()
    del partial["src03"]
    r = diff(env, partial, manifest)
    assert r["verdict"] == "RED", "missing source not RED"
    assert any(i["dimension"] == "coverage" and i["level"] == "RED"
               for i in r["items"])

    # 7. density blowout (one family way outside band) -> at least YELLOW
    dense = _fixture_corpus()
    p = _fixture_plan(0)
    p["broll_clips"] = p["broll_clips"] * 9
    dense["src04"] = [extract_metrics(p, 60.0) for _ in range(3)]
    r = diff(env, dense, manifest)
    assert r["verdict"] in ("YELLOW", "RED"), "density blowout stayed GREEN"
    assert any(i["dimension"] == "density" for i in r["items"])

    # 8. envelope tolerance: natural 3-run variance must NOT false-alarm —
    #    already covered by (1), but assert bands are non-degenerate too.
    b = env["per_source"]["src00"]["bands"]["emphasis"]
    assert b["hi"] > b["lo"], "degenerate band"

    if verbose:
        print("self-test: 8/8 defect classes behave (GREEN stays green, "
              "planted defects go RED)")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("self-test")
    for name in ("diff", "baseline"):
        p = sub.add_parser(name)
        p.add_argument("--golden", required=True)
        p.add_argument("--manifest", required=True)
        p.add_argument("--out")
        if name == "diff":
            p.add_argument("--candidate", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "self-test":
        self_test(verbose=True)
        print("PASS")
        return 0

    manifest = load_manifest(args.manifest)
    golden = load_run_dir(args.golden, manifest)
    env = build_envelope(golden, manifest)
    cand = golden if args.cmd == "baseline" else load_run_dir(args.candidate, manifest)
    report = diff(env, cand, manifest)
    report["golden_sources"] = len(golden)
    report["candidate_sources"] = len(cand)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
    print("VERDICT: %s  (red=%d yellow=%d of %d dims, defect_rate=%.3f)"
          % (report["verdict"], report["dims_red"], report["dims_yellow"],
             report["dims_total"], report["defect_rate"]))
    for i in report["items"][:20]:
        print("  [%s] %s%s: %s" % (i["level"], i["dimension"],
                                   " " + i.get("source_id", "") if i.get("source_id") else "",
                                   i["detail"]))
    return 0 if report["verdict"] != "RED" else 1


if __name__ == "__main__":
    sys.exit(main())
