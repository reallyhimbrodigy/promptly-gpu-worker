#!/usr/bin/env python3
"""Translate a Promptly ruling into a plan written in CHATCUT'S PRIMITIVES.

WHY THIS FILE EXISTS, ruled by Zac 2026-09-13 after the first plan-first run.
Our families — text, card, sfx, zoom, cutaway, transition — are a schema for OUR
builder. ChatCut's are timeline items, motion graphics, tracks and captions.
Anywhere the two vocabularies meet UNMAPPED, the agent spends turns reconciling
them, and the turns are the whole cost.

IT WAS MEASURED, NOT SUPPOSED. In the 999s run the agent knew what to build and
spent ten turns discovering HOW TO SAY IT: turns 35-42 are eight failing `adds`
of one video item, 43 succeeds; 44 and 45 guess `geometry` then `rect` for one
update and both fail. Ten turns on parameter spelling.

AND THE FIRST PLAN CONTAINED AN UNSATISFIABLE INSTRUCTION. It said "add one
title" and "do not create a motion graphic" — but in ChatCut a title IS a motion
graphic; there is no text-overlay item type. The agent had to resolve a
contradiction, and resolving a contradiction is deciding. That is this repo's
own rule about the acceptor taking the shape we advertise, broken from the
PRODUCER side.

EVERY SHAPE BELOW WAS READ OFF A LIVE TIMELINE, never inferred from a schema
description. `preview_timeline` on the project that run built returned:

    itemType "video",          trackAlias "V1",
      sourceRange   {startSeconds: 0, endSeconds: 21.333333333333332}
      timelineRange {fromFrame: 0, toFrame: 640}
    itemType "motion-graphic", trackAlias "V2",
      timelineRange {fromFrame: 99, toFrame: 141}

THE UNIT SEAM, WHICH IS THE TRAP. Timeline time is FRAMES; source time is
SECONDS. Two axes, two units, in one item. A plan that gives seconds for both
makes the agent convert, and a conversion it gets wrong is a placement on the
wrong moment that every gate passes.
"""
import json
import re
import sys

FPS_DEFAULT = 30

# ── THE MAP. One row per family we can rule. ────────────────────────────────
# VERIFIED means the shape was read off a live ChatCut timeline in this repo.
# UNVERIFIED means nobody has observed it, and the translator REFUSES to emit a
# plan containing it — because the alternative is shipping prose the agent has
# to reconcile at the price measured above. Assert only what you can observe.
FAMILY_MAP = {
    "cut": {
        "item_kind": "video-item",
        "verified": True,
        "primitive": "ONE video item on track V1",
        "how": ("a kept span is a single video item whose `sourceRange` is the "
                "source seconds and whose `timelineRange` is the frames it "
                "occupies. A trailing DROP is not an operation — it is simply "
                "an endSeconds. Do not split and delete."),
    },
    "text": {
        "item_kind": "motion-graphic-item",
        "verified": True,
        "primitive": "a motion-graphic asset + an item on track V2",
        "how": ("ChatCut has NO text-overlay item type. A title is a motion "
                "graphic: one create_motion_graphic_from_code, then one item "
                "on a video track ABOVE the footage. Building the placement "
                "means exactly one motion graphic, not zero and not two."),
    },
    "card": {
        "item_kind": "motion-graphic-item",
        "verified": True,
        "primitive": "a motion-graphic asset + an item, with propertyOverrides",
        "how": ("same ITEM primitive as `text`; the difference is which "
                "component and which props. The per-item override field is "
                "`propertyOverrides` — documented in "
                "skills/shader-gen/references/property-changes.md and "
                "validated live. Two guesses (`props`, `propertyValues`) were "
                "refused before I stopped and read."),
    },
    "cutaway": {
        "item_kind": "video-item",
        "verified": False,
        "primitive": "a video item on a track above the base",
        "how": "the covering item's shape has not been observed in this repo.",
    },
    "sfx": {
        "item_kind": "audio-item",
        "verified": True,
        "primitive": "an audio item — type:\"audio\", assetId:\"library:sound:<id>\"",
        "how": ("COMMITTED, not dry-run: library sounds REFUSE validateOnly by "
                "design (\"Adding a Library Sound Effect first creates or "
                "reuses a project audio asset\"), so the dry run cannot be the "
                "proof for this family. A commit created audio track A1 and "
                "item 135b011eac. Ids come from browse_library "
                "category=\"sound-effects\"."),
    },
    "zoom": {
        "item_kind": "effect-on-item",
        "verified": True,
        "primitive": ("an effect ON a clip — type:\"effect\", "
                      "assetId:\"builtin:zoom\", targetItemId:<clip id>"),
        "how": ("read from skills/shader-gen/SKILL.md, then validated live: it "
                "returned a real effect item. propertyOverrides carries "
                "{magnification, shape}. NOT item geometry — the two guesses "
                "that failed (`geometry`, `rect`) were the wrong idea, not the "
                "wrong spelling."),
    },
    "transition": {
        "item_kind": "transition-item",
        "verified": False,
        "primitive": "a transition entry in edit_item",
        "how": "not observed.",
    },
    "caption": {
        "item_kind": "not-an-item",
        "verified": True,
        "primitive": ("NOT AN ITEM — `edit_captions` enable, then template and "
                      "set_max_characters"),
        "how": (
            "captions are a separate surface, and the surface OWNS THE TEXT. "
            "`edit_captions action:\"enable\"` makes ChatCut transcribe the "
            "audible timeline sources itself and returns Cards keyed in "
            "TIMELINE FRAMES — verified live 2026-09-14: 42 Cards on a 2148-"
            "frame timeline, then `set_max_characters {scope:\"all\",value:14}` "
            "and `template templatePreset:\"dogme\"`, composed and read back "
            "from the rendered frame.\n"
            "  SO THE PIPELINE'S CAPTIONS DO NOT TRANSFER, and that is the "
            "finding rather than a wiring gap. Our nine styles (CleanCut, "
            "Gadzhi, Prime, Cove, Lumen, Pulse, Quintessence, TwoTone, "
            "TypewriterReveal) are full Remotion components with their own "
            "word-level motion; ChatCut's caption layer is ChatCut's, with 26 "
            "presets of its own. What CAN be carried is: that the video is "
            "captioned at all, the pagination (max characters per line, words "
            "per page), the position, and a per-Card text correction where our "
            "ASR is better. The style choice is a MAPPING between two "
            "catalogues and it is a taste call — it is not made here."),
    },
}


# ── PRODUCTION'S GRACEFUL PLACEMENT, PORTED ─────────────────────────────────
# handler.py has carried this ladder for months and this lane could not use it,
# because the plan is built offline and `agentic_editor_app.py` produces no
# `face_traj` and no `source_text_regions`. The detectors now run once in the
# image (`chatcut_job_app.py::detect`) and the answer travels with the ruling,
# so the plan can do what the pipeline does.
#
# THE RULE IS NOT "FAIL". A graphic with nowhere clear is REPOSITIONED in time
# and, if nothing clears, DROPPED with a sentence the user reads — because
# nothing failed: a component was considered and not placed, which is a
# decision an editor makes constantly.
MG_REPOSITION_STEP_S = 0.25          # verbatim, handler.py
MG_MIN_WINDOW_S = 0.8                # verbatim, handler.py


def _regions(led=None):
    """{face_traj, source_text_regions} FROM THE RULING, or a named absence.

    NO FILESYSTEM FALLBACK. The first version fell back to a regions.json
    sitting beside this module, and that is a global implicit input: every plan
    built anywhere would pick up whichever clip's face trajectory happened to
    be adjacent. It showed up immediately — a smoke about CLOCKS started
    dropping its synthetic graphics, because they were being judged against the
    blue-shirt speaker's face. One clip's face applied to another video is
    worse than no face data at all, because the second case fails open and says
    so while the first is confidently wrong.

    Regions belong to a CLIP, so they travel with the ruling for that clip.
    Absent, the ladder fails open exactly as production does with no face data,
    and the plan prints the ABSENT state rather than implying it looked.
    """
    r = dict((led or {}).get("regions") or {})
    if not r:
        return {"face_state": "ABSENT", "text_state": "ABSENT",
                "why": "the ruling carries no regions — run "
                       "`modal run chatcut_job_app.py::detect` and attach them"}
    return r


def _band_clear(band_name, t0, t1, traj, burned):
    """Is `band_name` clear of the face over [t0,t1] and un-owned by the source?

    handler.py's `band_overlap`, verbatim: a 600px window around each detected
    face centre, its mean fractional coverage of the band, clear at or below
    MG_FACE_CLEAR_THRESHOLD.
    """
    import face_bands as fb
    if band_name in (burned or ()):
        return False
    pts = [p for p in (traj or [])
           if p.get("found") and (t0 - 0.5) <= float(p.get("t") or 0.0) <= (t1 + 0.5)]
    if not pts:
        return True                      # fail-open on face data, as production does
    y0, y1 = fb.MG_FACE_BAND_YRANGES[band_name]
    FH = 600.0
    cov = sum(max(0.0, min(y1, float(p.get("cy") or 960.0) + FH / 2.0)
                  - max(y0, float(p.get("cy") or 960.0) - FH / 2.0)) / FH
              for p in pts) / len(pts)
    return cov <= fb.MG_FACE_CLEAR_THRESHOLD


def place_gracefully(band_name, t0, t1, traj, burned):
    """THE LADDER: placed -> repositioned -> dropped. Never raises.

    REPOSITION CONTRACTS THE END, NEVER THE START. The anchor is where the
    planner grounded the beat; only the end moves, looking for a sub-window in
    which the band is clear. The face moves during a shot, so a shorter window
    often has a clear band the full one does not — and grounding survives by
    construction rather than by a second check. Verbatim from handler.py.
    """
    if _band_clear(band_name, t0, t1, traj, burned):
        return "placed", t1, None
    end = t1
    while (end - t0) - MG_REPOSITION_STEP_S >= MG_MIN_WINDOW_S:
        end -= MG_REPOSITION_STEP_S
        if _band_clear(band_name, t0, end, traj, burned):
            return "repositioned", end, None
    return "dropped", t1, "unfittable"


def unplaced_note(said):
    """The sentence a user reads when a beat was deliberately left bare.

    Verbatim from handler.py's `_mg_unplaced_note`: names the moment in the
    USER'S words, never a component type, never an error code, never failure
    language.
    """
    _s = str(said or "").strip()
    if _s:
        return ("I wanted a graphic on \u201c%s\u201d \u2014 the frame is too "
                "tight there for one to sit clear of your face, so I let the "
                "line carry it." % _s)
    return ("One beat was too tight for a graphic to sit clear of your face, "
            "so I let the line carry it.")


def _card_overrides(hero, label):
    """`card_hero` -> StatCard's (value, suffix), or a named refusal.

    THE CARD WAS LOST AT THE LAUNCHER. `titles_from` built the prestage payload
    from five control fields and `card_hero`/`card_label` were not among them,
    so a beat ruled text+card registered a TITLE-ONLY asset. The plan then told
    the agent "the card and the title are ONE placement here — the component
    carries both", which was a claim about an asset nobody had checked. The
    accounting counted the card as emitted, the placement landed, the run went
    green, and frames 534/560/580/600 of that graphic's window carry the title
    and no card.

    StatCard is registered, DRAWS (9.710% px), and is offered under exactly
    this beat's condition — "WHEN A NUMBER LANDS". It takes `value` (a number),
    `suffix` and `label`. So the card becomes its OWN placement rather than a
    property of a component that has none.
    """
    h = str(hero or "").strip()
    m = re.match(r"^\s*([£$€]?)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(.*)$", h)
    if not m:
        return None, ("card_hero %r carries no number, and StatCard is a "
                      "NUMBER card — `value` is numeric and the whole "
                      "component is built to land on a figure. A card ruled "
                      "on a beat with no figure is a ruling this surface "
                      "cannot execute." % h)
    pre, num, suf = m.group(1), m.group(2).replace(",", ""), m.group(3).strip()
    val = float(num)
    if val == int(val):
        val = int(val)
    ov = {"value": val, "label": str(label or "").strip()}
    if suf:
        ov["suffix"] = " " + suf
    if pre:
        ov["prefix"] = pre
    # `decimals` is a REAL SURFACE LIMIT, recorded rather than papered over:
    # StatCard rounds to whole numbers by default, so a fractional hero needs
    # it set or the card shows a different figure than the speaker said.
    if isinstance(val, float):
        ov["decimals"] = len(num.split(".")[1])
    return ov, None


def _target_of(frame, seg_add):
    """Which adds[] entry made the video item under `frame`.

    THE ZOOM COST THREE FAILED inspect_item CALLS because the plan said "read
    it back from the adds you just made" — an instruction to go looking. The
    segment covering a timeline frame is arithmetic this file already has: the
    segments are emitted first, in order, so adds[k] IS the k-th segment. Name
    the index and the id arrives in the response the agent already holds.
    """
    for k, a, b, f0, f1 in seg_add:
        if f0 <= frame < f1:
            return ("the id returned for CALL 1 adds[%d] (source %.2fs-%.2fs, "
                    "timeline frames %d-%d). edit_item returns createdItems in "
                    "adds order — take the WHOLE uuid from the response you "
                    "already have. DO NOT call inspect_item, preview_timeline "
                    "or read_project to find it." % (k, a, b, f0, f1))
    raise Incomplete(
        "a zoom is ruled on timeline frame %d and NO video segment covers it "
        "(segments end at frame %d). An effect with no item to sit on is a "
        "placement nobody can execute."
        % (frame, seg_add[-1][4] if seg_add else 0))


# ── THE TWO SOUND VOCABULARIES, MAPPED BY HAND AND CLOSED ────────────────────
# The planner's `sfx_name` is a CLOSED ENUM OF SIXTEEN PREDICATES ("the speaker
# throws a verbal blow", "a photo is taken"), each a MOMENT in the footage.
# ChatCut's library is thirty-five NAMED RECORDINGS. Neither is a spelling of
# the other, and the first version of this resolver matched them by shared
# tokens — which answered `whoosh` and `ding` and returned nothing at all for
# `transition-sfx` and `punchsfx`, the only two sounds the real edit ruled.
#
# Same shape as `white_on_footage` arriving in a `color` field: a field match
# that checked names, units and clock and never checked VOCABULARIES. So the
# map is written out, and a token that is not in it is DROPPED AND NAMED rather
# than fuzzily satisfied — a wrong sound on a beat is a worse edit than a
# missing one, and a matcher that always finds something can never say so.
SFX_LIBRARY = {
    # the four whooshes-and-turns, by weight
    "swoosh-sound-effects": "simple-whoosh",
    "woosh-professional":   "airy-short-whoosh",      # narration travels: light
    "transition-sfx":       "deep-short-whoosh",      # the act turn: heaviest
    # impacts. The library has ONE impact and two predicates want it — the
    # heaviest claim and the verbal blow are the same sound at this surface.
    "boom":                 "vine-boom-impact",
    "punchsfx":             "vine-boom-impact",
    # a reversal STOPS; it does not build. The riser was wrong for `shocking`
    # for the same reason `from` was wrong for a sound anchor — plausible, and
    # backwards.
    "shockingsfx":          "record-scratch-stop",
    "imposter":             "fast-suspense-riser",    # suspicion BUILDS
    "awkward-moment":       "awkward-crow-flyby",
    "wompwomp":             "short-drum-roll-sting",
    # literals
    "popsfx":               "tiny-bubble-pop",
    "iphoneding":           "phone-notification-ping",
    "money-ching":          "cash-register-success",
    "camera-flash":         "camera-shutter",
    "mouse-click-sound":    "mouse-click",
}
# `voice` IS NOT A SOUND. Its predicate is "a beat whose delivery already does
# what a sound would do" — a SIGNED choice to place nothing. Mapping it to any
# recording would add a sound the planner explicitly declined.
SFX_MEANS_SILENCE = {"voice"}
# ...and `rizz` has no recording here. The library carries no charm sting, and
# `anime-wow-reaction` is a reaction, not a flex. Named, not substituted.
SFX_NO_SOUND_IN_LIBRARY = {"rizz"}


def _sound_ids():
    """The library's real ids, read from the fetched file — never hand-typed."""
    import os as _os
    _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                       "chatcut_sound_library.json")
    lib = json.load(open(_p, encoding="utf-8"))["sounds"]
    return {s["id"].split(":")[-1]: (s["id"], s["name"]) for s in lib}


def _resolve_sound(want):
    """`sfx_name` -> (assetId, name, state). Offline, closed, and honest.

    THE AGENT SPENT FIVE browse_library CALLS on one placement, because the plan
    told it to go and find the id. The library does not change between runs, so
    it is fetched once and stored beside this file — the same move as
    pre-staging the project, the asset and the components.

    state is MEASURED (a real id), SILENT (`voice`: the planner declined a
    sound) or ABSENT (nothing in the library plays this moment).
    """
    w = str(want or "").strip().lower()
    if w in SFX_MEANS_SILENCE:
        return None, None, "SILENT"
    slug = SFX_LIBRARY.get(w)
    if slug is None:
        return None, None, "ABSENT"
    ids = _sound_ids()
    if slug not in ids:
        # the map names a recording the library does not carry. Loud, because a
        # silently-empty map is how a closed enum rots into a no-op.
        raise Incomplete(
            "SFX_LIBRARY maps %r to %r and chatcut_sound_library.json has no "
            "such sound. The map and the library moved apart." % (w, slug))
    return ids[slug][0], ids[slug][1], "MEASURED"


class Unmapped(Exception):
    """A family with no verified ChatCut primitive reached the translator."""


class Incomplete(Exception):
    """A graphic reached the translator with a control left unanswered."""


CONTROLS = ("size", "case", "where", "colour", "hold_s")


def refuse_incomplete(rows):
    """A HOLE IN THE PLAN IS A DECISION HANDED TO THE EXECUTOR.

    The same refusal `half_ruling_refusal` now makes at ruling time, repeated
    at the boundary — because the two can drift and because a ledger written
    BEFORE that fix will still carry nulls. Measured on the 999s run: `colour`
    was left open, the agent picked black, and the title rendered black-on-dark
    over a purple backdrop. An open field does not only cost turns; it costs
    the frame.
    """
    bad = []
    for p in rows:
        tr = [t for t in (p.get("treatment") or []) if t != "none"]
        if not tr:
            continue
        miss = [f for f in CONTROLS if str(p.get(f) or "").strip() == ""]
        if miss:
            bad.append("beat %s (%s): %s" % (p.get("beat", p.get("id")),
                                             "+".join(tr), ", ".join(miss)))
    if bad:
        raise Incomplete(
            "these placements reach ChatCut with controls unanswered:\n    "
            + "\n    ".join(bad)
            + "\n  Each blank is a decision the executing agent has to make, "
              "and deciding is the\n  cost this whole path exists to remove. "
              "They are refused at ruling time by\n  half_ruling_refusal; a "
              "ledger carrying nulls predates that fix. Re-rule it.")


def families_in(plan_rows):
    fams = set()
    for p in plan_rows:
        for t in (p.get("treatment") or []):
            t = str(t).lower()
            if t and t != "none":
                fams.add(t)
    return fams


def refuse_unmapped(fams):
    """Stop HERE, where it costs one line, not in the agent's turn budget."""
    bad = sorted(f for f in fams
                 if not FAMILY_MAP.get(f, {}).get("verified"))
    if bad:
        raise Unmapped(
            "these families have no VERIFIED ChatCut primitive: %s.\n"
            "  Each one reaches the agent as prose it must reconcile against a "
            "tool surface\n"
            "  nobody has checked, and that reconciliation is exactly what "
            "costs turns —\n"
            "  ten of them went on parameter spelling in the 999s run. "
            "Observe the shape on a\n"
            "  live timeline and mark it verified, or leave the family out of "
            "the plan." % ", ".join(bad))


def render(result_json, fps=FPS_DEFAULT, staged=False, allow_drop=False):
    d = json.load(open(result_json, encoding="utf-8"))
    led = d["ledger"]
    rows = d["plan"]
    fams = families_in(rows)
    # THE SPEC IS WHERE `caption` IS RULED, and this file never read it. The
    # beat rows carry text/card/zoom/sfx; captions are ruled ONCE, for the whole
    # edit, in set_spec's `families`. So `families_in(rows)` cannot see them and
    # the section below asserted "NO CAPTIONS. They are not in the brief."
    # UNCONDITIONALLY — on a run whose spec said families ["caption","cut"] and
    # whose brief said "Burn readable captions". The plan told the agent not to
    # do the thing the pipeline had ruled, and the export came back without
    # them. Not an omission in the wiring: an instruction to skip.
    _spec_fams = {str(f).lower() for f in ((led.get("spec") or {}).get("families") or [])}
    # AND `families` IS NULL ON A full_edit. Keying only off the spec's family
    # list answered "caption" correctly for a targeted_change and WRONGLY for
    # every full edit — where families is None by construction and captions are
    # ruled by the brief, not by a scope list. Caught before spending a run:
    # the plan would have said NO CAPTIONS on a ledger showing
    # caption_composited=true, 29 pages, 85 words, style TwoTone. The second
    # signal is the pipeline's OWN RENDER: if its edit burned captions, the
    # ChatCut edit of the same ruling carries them too.
    _wants_captions = ("caption" in _spec_fams
                       or bool(led.get("caption_composited")))
    # DROPPED IS NOT OMITTED. Refusing outright is right when an unmapped family
    # would reach the agent as prose to reconcile. But a ruling this pipeline
    # made and this surface cannot execute is a FACT about the run, and burying
    # it is the silent-omission failure one layer up. With --allow-drop the
    # unmapped families are removed from the instructions AND named in the plan,
    # so the edit is honest about what it is not doing.
    dropped = sorted(f for f in fams
                     if not FAMILY_MAP.get(f, {}).get("verified"))
    if dropped and not allow_drop:
        refuse_unmapped(fams)
    if dropped:
        rows = [dict(p, treatment=[t for t in (p.get("treatment") or [])
                                   if t not in dropped]) for p in rows]
    refuse_incomplete(rows)

    keep = led["keep_spans"]
    dur = led["source_duration_s"]
    end = keep[-1][1]
    total_frames = int(round(end * fps))

    L = ["# THE DECIDED EDIT — in ChatCut's primitives",
         "",
         "Produced by the Promptly pipeline in 5 turns. Every value below is "
         "already decided.",
         "",
         "THE WRITE VOCABULARY IS NOT THE READ VOCABULARY. `preview_timeline` "
         "REPORTS",
         "trackAlias / timelineRange.fromFrame / timelineRange.toFrame / "
         "sourceRange.startSeconds.",
         "`edit_item` ACCEPTS different names for the same things, and one of "
         "them is a",
         "different QUANTITY:",
         "",
         "    reported                      pass to edit_item",
         "    trackAlias  \"V1\"             OMIT trackId entirely — ChatCut "
         "auto-places",
         "                                  on a free track, which is what you "
         "want",
         "    timelineRange.fromFrame       from",
         "    timelineRange.toFrame         durationInFrames  <-- A LENGTH, "
         "NOT AN END",
         "    sourceRange.startSeconds      sourceStartFromInSeconds",
         "    (geometry)                    left / top / width / height",
         "",
         "Every add below gives you `from` and `durationInFrames` directly so "
         "there is",
         "nothing to convert and nothing to subtract.",
         "",
         "UNITS: timeline time is FRAMES, source time is SECONDS.",
         f"The project is {fps}fps, 1080x1920. Both are given for every item so "
         "you never convert.",
         "",
         "## 1. THE BASE VIDEO — one item on V1",
         "",
         "EVERY add BELOW IS LABELLED WITH ITS CALL AND ITS SLOT — `CALL 1, "
         "adds[3]:`.",
         "Send each call's adds TOGETHER, in one call, in the order given, and "
         "check the",
         "returned item count equals the number of adds that call names. The "
         "plan states",
         "at the end how many calls there are and why.",
         ""]
    # A PLAN THAT SAYS "CREATE" BESIDE A PROMPT THAT SAYS "DO NOT CREATE" is
    # the unsatisfiable instruction that cost the first plan-first run two
    # motion graphics. When the harness has already imported and authored, the
    # plan must stop telling the agent to.
    _nseg = len(keep)
    L += ([("The media is ALREADY IMPORTED and the asset id is in your "
            "instructions. Add %d video item%s"
            % (_nseg, "" if _nseg == 1 else "s")),
           ("referencing it — the cut is these segments laid end to end, each "
            "with its own"),
           ("sourceStartFromInSeconds. Do not split and delete, and do not "
            "import anything."), ""]
          if staged else
          ["Import /work/source.mp4, then add ONE video item. The trailing "
           "drop is not an",
           "operation; it is this item's endSeconds. Do not split and delete.",
           ""])
    # ── TWO CLOCKS, AND THEY ARE BOTH IN SECONDS ───────────────────────────
    # The video segments are laid out cumulatively (timeline time); a graphic's
    # src_t0 is where it sits in the SOURCE. Once 15.3s has been cut those are
    # different numbers, and emitting src_t0 as a timeline `from` put 12 of 13
    # titles up to 13.6s late and stretched a 58.03s edit to 71.68s.
    #
    # Third form of one trap: frames-vs-seconds on two axes, then toFrame-vs-
    # durationInFrames, now source-clock-vs-timeline-clock — both in seconds,
    # both plausible, in the same document.
    _segs, _c = [], 0.0
    for _a, _b in keep:
        _segs.append((_a, _b, _c))
        _c += (_b - _a)
    _timeline_end = _c

    def _to_timeline(t):
        """Source seconds -> timeline seconds, or None if that moment was CUT.

        None is not a fallback to raw t. A placement whose moment was removed
        has nowhere to land, and drifting it to the nearest surviving frame is
        how a graphic ends up on a line it was never written for.
        """
        for _a, _b, _off in _segs:
            if _a <= t < _b:
                return _off + (t - _a)
        return None

    _idx = [0]
    _seg_add = []          # (adds index, source a, source b, timeline f0, f1)
    t_cursor = 0
    for a, b in keep:
        f0, f1 = int(round(t_cursor * fps)), int(round((t_cursor + (b - a)) * fps))
        _seg_add.append((_idx[0], a, b, f0, f1))
        L += [f"  CALL 1, adds[{_idx[0]}]:",
              f"    type                     : video",
              f"    assetId                  : (given in your instructions)",
              f"    from                     : {f0}",
              f"    durationInFrames         : {f1 - f0}",
              f"    sourceStartFromInSeconds : {a:.3f}",
              f"    (omit trackId — this is the base layer, it goes on the "
              f"first free track)",
              ""]
        _idx[0] += 1
        t_cursor += (b - a)
    L += [f"  RESULT: a {total_frames}-frame timeline ({end:.2f}s). "
          f"The source is {dur:.2f}s; the last {dur - end:.2f}s is silent dead",
          f"  footage and is dropped because an edit ENDS ON THE LAST THING "
          f"WORTH SEEING.", ""]

    # EVERY RULING IS ACCOUNTED FOR OR THE PLAN REFUSES TO EXIST.
    #
    # The loop below used to emit ONE GRAPHIC PER TREATED BEAT whatever the
    # beat was ruled, so a beat ruled `text+card+sfx` produced a title and the
    # card and the sfx simply disappeared. Measured on the blue-shirt edit:
    # the pipeline ruled 14 placements — text 7, cutaway 3, sfx 2, zoom 1,
    # card 1 — and the plan carried 7. Three cutaways were NAMED as dropped
    # because cutaway is unverified; the other four vanished in silence,
    # including a StatCard whose hero was the video's own closing line.
    #
    # And the PLACEMENTS gate could not see it: it compares the plan's own
    # `planned_adds` against what the agent built, so it confirmed 8 of 8 while
    # the plan had already lost half the rulings. The check sat downstream of
    # the loss — the same shape as the caption contradiction.
    #
    # So the accounting is kept here and reconciled at the end. A ruling that
    # does not reach the plan RAISES, exactly like the two clock refusals: a
    # placement with nowhere to land is not a smaller edit, it is an edit
    # nobody ruled.
    # THE CAPTION STYLE, HOISTED. The card has to clear it, and the caption
    # section is emitted three hundred lines later — so the fact that decides
    # the card's position was not in scope where the card is placed. That is
    # the same shape as the collision itself: two families, and no reader that
    # held both.
    _cap_style = (((led.get("caption_render") or {}).get("style")
                   or led.get("caption_style") or "") if _wants_captions else "")
    # THE REGIONS, AND WHAT THE LADDER DECIDED. A beat whose graphic has
    # nowhere clear is not a failure and not a silent omission — it is dropped
    # and NAMED, in the user's own words, exactly as the pipeline does.
    _reg = _regions(led)
    _traj = _reg.get("face_traj")
    _burned = list(_reg.get("source_text_regions") or ())
    _regions_state = "%s/%s" % (_reg.get("face_state", "ABSENT"),
                                _reg.get("text_state", "ABSENT"))
    _unplaced = []
    _ruled, _emitted = {}, {}
    for p in rows:
        for t in (p.get("treatment") or []):
            if t != "none":
                _ruled[t] = _ruled.get(t, 0) + 1

    L += ["## 2. THE GRAPHICS — motion graphics on V2", ""]
    _settle = []
    # What every placement must be true of, collected here and emitted as one
    # ACCEPTANCE section beside the review frames — which is where it is read.
    _accept = []
    n = 0
    for p in rows:
        tr = [t for t in (p.get("treatment") or []) if t != "none"]
        if not tr:
            continue
        if "text" not in tr and "card" not in tr:
            continue          # zoom/sfx-only beats are emitted in their own pass
        n += 1
        _tl0 = _to_timeline(p["src_t0"])
        _tl1 = _to_timeline(max(p["src_t0"], p["src_t1"] - 1.0 / fps))
        if _tl0 is None:
            raise Incomplete(
                "graphic %r is ruled at source %.2fs, which the cut REMOVED. "
                "It has no timeline moment to land on. Re-rule the beat or "
                "keep its span — drifting it to the nearest surviving frame "
                "would put it on a line it was not written for."
                % (p.get("text_content"), p["src_t0"]))
        if _tl1 is None:
            _tl1 = _tl0 + (p["src_t1"] - p["src_t0"])
        f0 = int(round(_tl0 * fps))
        f1 = int(round(min(_tl1 + 1.0 / fps, _timeline_end) * fps))
        if f0 >= int(round(_timeline_end * fps)):
            raise Incomplete(
                "graphic %r would start at frame %d, past the %d-frame "
                "timeline. A placement beyond the end stretches the render to "
                "hold a graphic over nothing — that is how a 58.03s edit "
                "delivered as 71.68s."
                % (p.get("text_content"), f0, int(round(_timeline_end * fps))))
        # AN INSTRUCTION, NOT A DESCRIPTION. The base video carried a literal
        # `edit_item adds[0]:` header and got placed; the graphic listed its
        # values with no adds block and no assetId line, so it read as a
        # description of a component rather than a call to make — and the run
        # placed the video, skipped the title, previewed, exported and exited 0.
        # The presentational values move BELOW the call and are marked as
        # already baked into the asset, so nothing dilutes the instruction.
        # ── THE LADDER, BEFORE ANYTHING IS EMITTED ──────────────────────
        _band_name = "top" if str(p.get("where") or "").startswith("upper") \
            else ("bottom" if "lower" in str(p.get("where") or "") else "center")
        _out, _newend, _why = place_gracefully(_band_name, _tl0, _tl1,
                                               _traj, _burned)
        if _out == "dropped":
            _unplaced.append((p.get("text_content"), _band_name, _tl0, _tl1))
            for _t in ("text", "card"):
                if _t in tr:
                    _emitted[_t] = _emitted.get(_t, 0) + 1
            n -= 1
            continue
        if _out == "repositioned":
            f1 = int(round(min(_newend + 1.0 / fps, _timeline_end) * fps))
        _gi = _idx[0]
        _idx[0] += 1
        L += [(f"  GRAPHIC {n} — the asset ALREADY EXISTS. PLACE IT."
               if staged else
               f"  GRAPHIC {n} — one create_motion_graphic_from_code, then one "
               f"item on V2"),
              f"    text          : {p['text_content']!r}",
              f"    CALL 1, adds[{_gi}]:",
              f"      type                   : motion-graphic",
              f"      assetId                : the GRAPHIC {n} assetId listed "
              f"in your instructions",
              f"      from                   : {f0}",
              f"      durationInFrames       : {f1 - f0}   "
              f"({p['src_t0']:.2f}s-{p['src_t1']:.2f}s, the {p['purpose']} beat)",
              f"      (omit trackId — it must sit ABOVE the video, and omitting "
              f"it places it on a free track)",
              f"    ALREADY BAKED INTO THE ASSET — nothing to pass, nothing to "
              f"decide:",
              f"    case          : {p.get('case')}",
              f"    band          : {p.get('where')}",
              f"    size          : {p.get('size')}",
              f"    colour        : {p.get('colour')}",
              f"    hold          : {p.get('hold_s')}",
              f"    why           : {p.get('why')}",
              ""]
        # 8 frames past the entrance, or the midpoint on a short graphic —
        # whichever still lands inside the window.
        _sf = min(f0 + 8, max(f0, (f0 + f1) // 2))
        _settle.append(_sf)
        # ── THE ACCEPTANCE RECORD ───────────────────────────────────────
        # MEASURED 2026-09-15: 102.7 of 112.0 thinking seconds on the
        # execution half sat on the two turns that follow the review frames
        # arriving — turns that emit almost no tool payload. The agent is not
        # re-deriving the plan and it is not working out the tools; it is
        # deciding, from scratch, what "wrong" would look like. The plan
        # already knows: the ladder computed this band, the face detector ran
        # at plan time, and the settled frame is named three lines up. Writing
        # it down turns an open judgement into a check.
        _accept.append({"n": n, "kind": "GRAPHIC", "band": _band_name,
                        "f0": f0, "f1": f1, "settle": _sf,
                        "ladder": _out, "text": p.get("text_content")})
        for _t in ("text", "card"):
            if _t in tr:
                _emitted[_t] = _emitted.get(_t, 0) + 1
        if "card" in tr:
            # ITS OWN ADD. The house title component has no card properties —
            # text, band, size, holdSeconds, textColor, accentColor and nothing
            # else — so a card folded into it is a card that does not render.
            _ov, _why = _card_overrides(p.get("card_hero"), p.get("card_label"))
            if _why:
                raise Incomplete(
                    "the beat at %.2fs is ruled `card` and %s" % (p["src_t0"], _why))
            _ci = _idx[0]
            _idx[0] += 1
            # PLACE IT CLEAR. The card's own band is measured; so are the
            # caption's and every other component's. Where the region is
            # contested, shift the card rather than hand the conflict onward.
            try:
                import verify_chain as _vc2
                _meas = _vc2.measured_bands()
                _self = {"type": "motion-graphic", "asset": "StatCard",
                         "overrides": _ov, "band": None, "slot": _ci,
                         "from": f0, "dur": f1 - f0}
                _others = [{"type": "motion-graphic", "asset": "", "band":
                            p.get("where"), "overrides": None, "slot": -1,
                            "from": f0, "dur": f1 - f0}]
                if _cap_style:
                    _others.append({"type": "motion-graphic",
                                    "asset": "caption:%s" % _cap_style,
                                    "band": None, "overrides": None,
                                    "slot": -2, "from": 0, "dur": 10 ** 6})
                _dy = _vc2.free_offset(_self, _others, _meas)
                if _dy is None:
                    raise Incomplete(
                        "the card ruled at %.2fs has nowhere to sit: its own "
                        "band, the title's and the caption's leave no free "
                        "region in the frame. That is an editorial fact about "
                        "this moment, not a layout bug — the beat is carrying "
                        "more than the frame holds." % p["src_t0"])
                if _dy:
                    _ov = dict(_ov, offsetY=_dy)
            except ImportError:
                pass
            L += [f"    THIS BEAT IS ALSO RULED `card`: "
                  f"{p.get('card_condition')!r} — a SECOND placement, in the "
                  f"same window, on StatCard.",
                  f"    CALL 1, adds[{_ci}]:",
                  f"      type                   : motion-graphic",
                  f"      assetId                : the StatCard assetId listed "
                  f"in your instructions",
                  f"      from                   : {f0}",
                  f"      durationInFrames       : {f1 - f0}",
                  f"      propertyOverrides      : {json.dumps(_ov)}",
                  f"      (offsetY is COMPUTED, not chosen: the card's "
                  f"measured band, the title's and the caption's were checked "
                  f"against each other and this is the nearest position that "
                  f"clears both. Do not move it.)",
                  ""]
            # reviewed at its own settled frame — StatCard counts IN over
            # `enterFrames` (32 by default), so 8 frames in shows a half-counted
            # number and reads as a defect.
            _cs = min(f0 + 36, max(f0, (f0 + f1) // 2))
            _settle.append(_cs)
            _accept.append({"n": n, "kind": "CARD", "band": "card",
                            "f0": f0, "f1": f1, "settle": _cs,
                            "ladder": "computed offsetY",
                            "text": p.get("card_hero") or p.get("card_condition"),
                            "offsetY": _ov.get("offsetY")})
    # ── ZOOM AND SFX ARE NOT GRAPHICS, AND WERE NEVER EMITTED AT ALL ──────
    # FAMILY_MAP carries a VERIFIED primitive for each: zoom is an effect ON a
    # clip (`builtin:zoom`, targetItemId), sfx is an audio item whose assetId
    # is `library:sound:<id>`. Both were observed live. The graphics loop above
    # could not express either, so both fell out of every plan in silence while
    # the map said they were ready.
    _zoom_rows = [q for q in rows if "zoom" in (q.get("treatment") or [])]
    _sfx_rows = [q for q in rows if "sfx" in (q.get("treatment") or [])]
    _sfx_unplayed = []
    if _sfx_rows:
        L += ["## 2b. THE SOUND EFFECTS — audio items on their own track", ""]
        for q in _sfx_rows:
            _t0 = _to_timeline(q["src_t0"])
            if _t0 is None:
                raise Incomplete(
                    "a sound effect is ruled at source %.2fs, which the cut "
                    "REMOVED." % q["src_t0"])
            _gi = _idx[0]
            _idx[0] += 1
            _want = str(q.get("sfx_name") or "").strip()
            _sid, _sname, _sst = _resolve_sound(_want)
            if _sst != "MEASURED":
                # NAMED, NOT VANISHED, and not raised either: one unplayable
                # moment must not cost the other thirteen placements. This is
                # the `dropped` discipline applied one level down, to a single
                # beat instead of a whole family.
                _sfx_unplayed.append((q["src_t0"], _want, _sst))
                _emitted["sfx"] = _emitted.get("sfx", 0) + 1
                continue
            L += ["  CALL 1, adds[%d]:" % _gi,
                  "    type                   : audio",
                  "    assetId                : %s   (%s — resolved here; do "
                  "NOT call browse_library)" % (_sid, _sname),
                  # `fromFrame`, NOT `from`, AND IT IS AN ANCHOR. browse_library
                  # states the shape outright: "edit_item imports/reuses the
                  # Library sound asset and SHIFTS THE ITEM START so the sound
                  # anchor lands on fromFrame." A sound placed with `from`
                  # starts where the beat starts, which puts the audible hit
                  # LATE by the length of its own attack.
                  "    fromFrame              : %d   (the editorial moment — "
                  "edit_item shifts the item so the sound's ANCHOR lands here)"
                  % int(round(_t0 * fps)),
                  "    NOTE: library sounds REFUSE validateOnly by design — "
                  "commit them, do not dry-run them.",
                  "    why                    : %s" % q.get("why"), ""]
            _emitted["sfx"] = _emitted.get("sfx", 0) + 1
        for _t, _w, _st in _sfx_unplayed:
            L += ["  NO SOUND AT %.2fs — ruled %r, %s." % (_t, _w, _st),
                  "    %s" % ("the planner's own `voice` ruling: this beat's "
                              "delivery already does what a sound would do, so "
                              "placing one would overrule it."
                              if _st == "SILENT" else
                              "ChatCut's 35-sound library carries no recording "
                              "for this moment. Named here rather than "
                              "substituted — a wrong sound on a beat is a "
                              "worse edit than a missing one."), ""]

    _zi = 0
    if _zoom_rows:
        L += ["## 2c. THE ZOOMS — CALL 2. An effect ON a video item, not an "
              "item of its own;", "    it names an item that must already "
              "exist, so it cannot ride CALL 1.", ""]
        for q in _zoom_rows:
            _t0 = _to_timeline(q["src_t0"])
            if _t0 is None:
                raise Incomplete(
                    "a zoom is ruled at source %.2fs, which the cut REMOVED."
                    % q["src_t0"])
            # THE EFFECT DOES NOT CONSUME A CALL 1 SLOT. It has its own
            # counter because it is sent in its own call; taking one from the
            # shared counter left a hole in CALL 1's index space and pushed the
            # caption to adds[12] of an 11-element array.
            L += ["  CALL 2, adds[%d]:" % _zi,
                  "    type                   : effect",
                  "    assetId                : builtin:zoom",
                  "    targetItemId           : %s" % _target_of(
                      int(round(_t0 * fps)), _seg_add),
                  '    propertyOverrides      : {"magnification": 1.12, '
                  '"shape": "%s"}' % (q.get("zoom_arc") or "payoff"),
                  "    why                    : %s" % q.get("why"), ""]
            _zi += 1
            _emitted["zoom"] = _emitted.get("zoom", 0) + 1

    # ── THE RECONCILIATION. Loud, by name, or the plan does not exist. ──────
    _lost = {f: _ruled[f] - _emitted.get(f, 0) for f in _ruled
             if f not in dropped and _ruled[f] - _emitted.get(f, 0) > 0}
    if _lost:
        raise Incomplete(
            "THESE RULINGS DO NOT REACH THE PLAN: %s.\n"
            "  Ruled %s, emitted %s, dropped-and-named %s.\n"
            "  A placement that vanishes here is not a smaller edit — it is an "
            "edit nobody ruled, delivered as its own weaker half with every "
            "downstream gate green. The PLACEMENTS gate cannot catch it: it "
            "counts the PLAN's own adds, so it confirms 8 of 8 while the plan "
            "has already lost half the rulings."
            % (", ".join("%s x%d" % (f, k) for f, k in sorted(_lost.items())),
               dict(sorted(_ruled.items())), dict(sorted(_emitted.items())),
               sorted(dropped)))

    if dropped:
        # DROPPED IS NOT OMITTED. The pipeline ruled these and this surface has
        # no verified primitive, so they are removed from the instructions AND
        # NAMED — burying them would be the silent-omission failure one layer
        # up, in the document whose whole job is to say what the edit is.
        L += ["", "  RULED BUT NOT EXECUTABLE HERE — the pipeline ruled these "
              "families and this",
              "  surface has no verified primitive for them, so they are "
              "DROPPED, not guessed at:",
              "      " + ", ".join(dropped),
              "  Do not attempt them. They are named so the edit is honest "
              "about its gaps.", ""]
    # TWO CALLS, AND THE PLAN SAYS SO — because an EFFECT names an item that
    # must already exist. The last run spent a turn on
    # `ToolSearch("edit_item adds effect targetItemId reference same batch temp
    # id")` working this out, then split into two calls anyway. An instruction
    # that says "one call" while the surface needs two is not a simpler
    # instruction; it is a turn spent discovering the contradiction.
    _n_eff = len(_zoom_rows)
    if _n_eff:
        L += ["", "  THE PLAN NAMES %d adds, IN TWO edit_item CALLS:" % _idx[0],
              "    CALL 1 — the %d video / motion-graphic / audio adds. An "
              "item is created for each," % (_idx[0] - _n_eff),
              "             and the response lists them IN adds ORDER. KEEP "
              "THAT RESPONSE.",
              "    CALL 2 — the %d effect add%s, whose targetItemId is an id "
              "from CALL 1's" % (_n_eff, "" if _n_eff == 1 else "s"),
              "             response. An effect names an item that must "
              "ALREADY EXIST, so it",
              "             cannot ride the batch that creates it.",
              "",
              "  IDS ARE FULL UUIDS. A tool result may ABBREVIATE an id for "
              "display; the",
              "  id you pass is the whole thing from CALL 1's response. Three "
              "inspect_item",
              "  calls went on guessing a truncated one (`d57895d3`, then "
              "`d57895d37f`, then",
              "  the real uuid). Copy, do not retype.", ""]
    else:
        L += ["", f"  THE PLAN NAMES {_idx[0]} adds. One edit_item call, "
              f"{_idx[0]} elements.", ""]
    L += ["  If the timeline afterwards holds fewer items than that, the edit "
          "is incomplete and you are not done.", ""]

    # ── THE FRAMES TO REVIEW, CHOSEN HERE ───────────────────────────────────
    # The agent previewed TWICE — `viewerFrameCount: 16` (silently capped at 9)
    # and then six hand-picked frames — because nothing told it which moments
    # mattered. That is two preview calls, two curl batches and two reads for
    # one review, and it is the same shape as the sfx and item ids: a question
    # the plan can already answer being handed to the agent to work out.
    #
    # The SETTLED frame of a graphic is where it should be judged: a few frames
    # after its entrance, before its exit, so an entrance animation is not
    # mistaken for a defect. This file knows every graphic's window, so it
    # knows those frames.
    if _settle:
        _fr = sorted(set(_settle))[:9]      # the viewer takes at most 9
        # A STARTING POINT, NOT A RATION. These were "do not pick your own and
        # do not call preview_timeline twice" — bounding how often the agent
        # could LOOK, which was a wall problem being solved by taking away the
        # thing that makes it an editor. The settled frames are worth naming
        # because the planner knows where each graphic lands; what the agent
        # does after seeing them is its own business.
        L += ["  THE SETTLED FRAMES of the graphics above — past each entrance "
              "and before each",
              "  exit, so an animation mid-flight is not read as a defect:",
              "      %s" % json.dumps(_fr),
              "  These are a STARTING POINT. Scrub wherever you like with "
              "preview_timeline —",
              "  any moment, as often as you need. Nobody is counting.", ""]
    # ── WHAT "RIGHT" MEANS, PER PLACEMENT ───────────────────────────────────
    # The review was an open question and it cost 102.7 of 112.0 thinking
    # seconds: nothing told the agent what wrong looks like, so it worked it out
    # from scratch on every graphic. All three criteria were already computed
    # here — the ladder picked the band, the face detector ran at plan time, and
    # the settled frame is named above. They were simply never written down.
    #
    # THIS IS NOT A NEW CONSTRAINT ON THE AGENT. Every line below is a statement
    # of what this plan already guarantees; the agent's job is to confirm it
    # survived contact with the renderer, which is a check, not a judgement.
    if _accept:
        try:
            import face_bands as _fb2
            _yr = _fb2.MG_FACE_BAND_YRANGES
        except Exception:                                         # noqa: BLE001
            _yr = {}
        _cap_band, _cap_why = None, ""
        if _wants_captions:
            try:
                import verify_chain as _vc3
                _mb = _vc3.measured_bands()
                # READ HERE, NOT BORROWED FROM BELOW. `_cstyle` is assigned
                # in the captions block ~70 lines further down; using it here
                # is a NameError on every run with captions — the
                # definition-after-use trap this repo has already paid for
                # twice (_PLAN_ONLY_NOTE, and a pyflakes catch on a mechanical
                # rewrite). The value comes from the same ledger key either way.
                _cs2 = ((led.get("caption_render") or {}).get("style")
                        or "CleanCut")
                _cap_band = _mb.get("caption:%s" % _cs2) if _mb else None
            except Exception as _e3:                              # noqa: BLE001
                # SPOKEN, NOT OMITTED. `measured_bands()` RAISES when rows.json
                # is unreadable — which is the in-container case the raise was
                # added for — and swallowing it here would drop the caption
                # line from every acceptance block in silence. An acceptance
                # list that is quietly one criterion short is the failure this
                # whole section exists to stop, arriving from inside it.
                _cap_band = None
                _cap_why = "%s: %s" % (type(_e3).__name__, str(_e3)[:90])
        L += ["  ACCEPTANCE — what RIGHT means for each placement. These are "
              "not new rules;",
              "  they are what this plan already computed. Check them, do not "
              "re-derive them.", ""]
        for _a in _accept:
            _y = _yr.get(_a["band"])
            _ov2 = [x for x in _accept
                    if x is not _a and x["f0"] < _a["f1"] and x["f1"] > _a["f0"]]
            L.append("    %s %d  %r" % (_a["kind"], _a["n"],
                                        str(_a.get("text") or "")[:48]))
            L.append("      judged at frame : %d  (%.2fs) — the settled frame, "
                     "not the entrance" % (_a["settle"], _a["settle"] / fps))
            if _y:
                L.append("      stays inside    : the %s band, y %.0f-%.0f of "
                         "1920. Anything outside it is the defect."
                         % (_a["band"], _y[0], _y[1]))
            elif _a.get("offsetY") is not None:
                L.append("      stays inside    : its measured band at "
                         "offsetY %s — COMPUTED against the title's band and "
                         "the caption's, and the nearest position that clears "
                         "both." % _a["offsetY"])
            L.append("      clear of a face : %s over frames %d-%d. The "
                     "detector ran on this source at plan time; a graphic on "
                     "the speaker's face is the defect this checks for."
                     % ({"placed": "MEASURED clear",
                         "repositioned": "MEASURED clear after the end was "
                                         "contracted to fit",
                         "computed offsetY": "MEASURED, and the offset was "
                                             "computed from it"}.get(
                             _a["ladder"], _a["ladder"]),
                        _a["f0"], _a["f1"]))
            _col = ", ".join("%s %d (%s band, frames %d-%d)"
                             % (x["kind"], x["n"], x["band"], x["f0"], x["f1"])
                             for x in _ov2) or "nothing"
            L.append("      must not touch  : %s" % _col)
            if _cap_band:
                L.append("                        the caption track, y %.0f-%.0f "
                         "— MEASURED from the component, not guessed"
                         % (_cap_band[0] * 1920, _cap_band[1] * 1920))
            elif _wants_captions:
                L.append("                        the caption track — ITS BAND "
                         "COULD NOT BE MEASURED HERE (%s), so judge it by eye "
                         "at that frame and say so if you cannot"
                         % (_cap_why or "no measurement available"))
            L.append("      legible         : readable at that frame without "
                     "leaning in — right size, not clipped by the frame edge.")
            L.append("")
        # ── THE STOP CONDITION ──────────────────────────────────────────────
        # Nothing told the agent when it was finished, so "have I looked enough"
        # was part of what it was deciding on every review turn. An edit that
        # satisfies its acceptance lines IS the finished edit.
        L += ["  WHEN YOU ARE DONE. Look at the settled frames. For each "
              "placement, check the",
              "  four lines above against what you see.",
              "",
              "    every line holds        -> THE EDIT IS RIGHT. submit_export "
              "and stop. There is",
              "                               nothing further to confirm and no "
              "second review to do.",
              "    a line fails            -> name it (which placement, which "
              "line, which frame),",
              "                               fix it in ONE edit_item call, "
              "look at that frame again,",
              "                               then stop.",
              "    you cannot tell         -> look at more frames. That is what "
              "scrubbing is for.",
              "",
              "  Looking again at a placement whose lines all hold does not make "
              "the edit better.", ""]
    L += ["## 3. WHAT IS NOT IN THIS EDIT", "",
          f"  Exactly {n} motion graphic{'' if n == 1 else 's'}. A second one is "
          f"the thing ruled out.",
          ("  You author no component code and you import no media — both are "
           "already done." if staged else ""),
          "  No movement, no sound, no b-roll, no stock media."]
    if _wants_captions:
        _cstyle = ((led.get("caption_render") or {}).get("style")
                   or "CleanCut")
        _cpages = (led.get("caption_render") or {}).get("pages")
        _cframes = int(round(_timeline_end * fps))
        _gi = _idx[0]
        _idx[0] += 1
        L += ["  (Captions ARE in this edit — see the section below.)",
              "", "## 4. THE CAPTIONS — a COMPONENT, not ChatCut's preset", "",
              "  The pipeline ruled captions and chose the style %r." % _cstyle,
              "",
              "  ChatCut's own caption surface has 26 presets of its own and "
              "none of them is",
              "  this one. Our nine styles are Remotion components with "
              "word-level motion — the",
              "  typography, the per-word timing, the keyword treatment — and "
              "mapping them onto",
              "  someone else's presets throws away exactly the part that "
              "makes them ours. So a",
              "  caption style is REGISTERED AS A COMPONENT like every other, "
              "with its pages",
              "  baked into the code at registration, and PLACED AS ONE ITEM "
              "over the whole",
              "  timeline. Verified live 2026-09-14: TwoTone rendered "
              "\"BEING A\" white over",
              "  \"CONTENT\" in its gold accent, its own drop shadow intact.",
              "",
              "  CALL 1, adds[%d]:" % _gi,
              "    type                   : motion-graphic",
              "    assetId                : the `caption:%s` assetId listed in "
              "your instructions" % _cstyle,
              "    from                   : 0",
              "    durationInFrames       : %d   (the whole timeline — one "
              "item, %s pages inside it)" % (_cframes, _cpages or "all"),
              "    (omit trackId — captions sit ABOVE the graphics)",
              "",
              "  DO NOT call edit_captions. That surface would transcribe the "
              "audio again and",
              "  render ChatCut's typography over the top of ours.",
              ""]
        _emitted["caption"] = _emitted.get("caption", 0) + 1
    else:
        L += ["  NO CAPTIONS. The spec did not rule them. Captions are not "
              "items in ChatCut —",
              "  they are their own surface — so do not go looking for a "
              "caption track either."]
    L += [""]
    if _unplaced:
        L += ["", "## 2z. BEATS LEFT BARE — considered and not placed", "",
              "  The face and the source's own burned-in text own every band "
              "over these",
              "  moments, so a graphic would have sat on the speaker or on his "
              "existing",
              "  captions. Nothing failed: a component was considered and not "
              "placed, which",
              "  is a decision an editor makes constantly. Detector state: "
              "%s." % _regions_state, ""]
        for _txt, _bn, _a2, _b2 in _unplaced:
            L += ["    %.2fs-%.2fs  %r  (wanted the %s band)"
                  % (_a2, _b2, _txt, _bn),
                  "      %s" % unplaced_note(_txt), ""]

    # ── TWO THINGS MAY NOT BE RULED INTO ONE REGION ────────────────────────
    # Checked on the finished plan, across ALL families at once, because that
    # is the reader nothing had: the title loop knew titles, the caption
    # section knew captions, the card rode the graphics pass, and no reader
    # ever held two of them together. StatCard occupies y 0.314-0.442 and
    # caption:TwoTone 0.367-0.410 — measured from their own renders, not
    # guessed — and both were live for frames 526-608. The card shipped with
    # caption words across its number.
    #
    # REFUSED HERE because it is the cheapest place and it is deterministic: no
    # asset registered, no call made, no render spent. What a plan CANNOT
    # predict — text wrapping, a counting number growing, a caption line
    # running long — is the review gate's job, and the two together are the
    # property.
    _txt = "\n".join(L)
    try:
        import verify_chain as _vc
    except ImportError:
        _vc = None
    if _vc is not None:
        _col = _vc.collisions(_vc.plan_manifest(_txt))
        if _col:
            raise Incomplete(
                "TWO PLACEMENTS ARE RULED INTO ONE REGION:\n  %s\n"
                "Both would be on screen together and their measured bands "
                "overlap, so one lands on top of the other. Move one of them, "
                "shorten a window so they do not coincide, or drop one — but "
                "do not ship a frame with two things in the same place."
                % "\n  ".join(c["why"] for c in _col))
    return _txt


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/plan_for_chatcut.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/PLAN_CC.md"
    try:
        txt = render(src, staged=("--staged" in sys.argv),
                     allow_drop=("--allow-drop" in sys.argv))
    except (Unmapped, Incomplete) as e:
        print("REFUSED (%s): %s" % (type(e).__name__, e))
        sys.exit(1)
    open(out, "w", encoding="utf-8").write(txt)
    print(f"WROTE {out}  ({len(txt)} chars)")
    print(txt)
