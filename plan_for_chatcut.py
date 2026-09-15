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
         "EVERY add BELOW IS ONE ELEMENT OF ONE edit_item CALL. The indices run "
         "across the",
         "whole plan — adds[0], adds[1], … — so send them together in a single "
         "call and",
         "check the returned item count equals the number of adds the plan "
         "names.",
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
    t_cursor = 0
    for a, b in keep:
        f0, f1 = int(round(t_cursor * fps)), int(round((t_cursor + (b - a)) * fps))
        L += [f"  edit_item adds[{_idx[0]}]:",
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
    _ruled, _emitted = {}, {}
    for p in rows:
        for t in (p.get("treatment") or []):
            if t != "none":
                _ruled[t] = _ruled.get(t, 0) + 1

    L += ["## 2. THE GRAPHICS — motion graphics on V2", ""]
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
        _gi = _idx[0]
        _idx[0] += 1
        L += [(f"  GRAPHIC {n} — the asset ALREADY EXISTS. PLACE IT."
               if staged else
               f"  GRAPHIC {n} — one create_motion_graphic_from_code, then one "
               f"item on V2"),
              f"    text          : {p['text_content']!r}",
              f"    edit_item adds[{_gi}]:",
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
        for _t in ("text", "card"):
            if _t in tr:
                _emitted[_t] = _emitted.get(_t, 0) + 1
        if "card" in tr:
            L += [f"    THIS BEAT IS ALSO RULED `card`: {p.get('card_condition')!r}",
                  f"      hero        : {p.get('card_hero')!r}",
                  f"      label       : {p.get('card_label')!r}",
                  f"    The card and the title are ONE placement here — the "
                  f"component carries both.", ""]
    # ── ZOOM AND SFX ARE NOT GRAPHICS, AND WERE NEVER EMITTED AT ALL ──────
    # FAMILY_MAP carries a VERIFIED primitive for each: zoom is an effect ON a
    # clip (`builtin:zoom`, targetItemId), sfx is an audio item whose assetId
    # is `library:sound:<id>`. Both were observed live. The graphics loop above
    # could not express either, so both fell out of every plan in silence while
    # the map said they were ready.
    _zoom_rows = [q for q in rows if "zoom" in (q.get("treatment") or [])]
    if _zoom_rows:
        L += ["## 2b. THE ZOOMS — an effect ON the video item, not an item", ""]
        for q in _zoom_rows:
            _t0 = _to_timeline(q["src_t0"])
            if _t0 is None:
                raise Incomplete(
                    "a zoom is ruled at source %.2fs, which the cut REMOVED."
                    % q["src_t0"])
            _gi = _idx[0]
            _idx[0] += 1
            L += ["  edit_item adds[%d]:" % _gi,
                  "    type                   : effect",
                  "    assetId                : builtin:zoom",
                  "    targetItemId           : the id of the VIDEO item "
                  "covering timeline frame %d — read it back from the adds you "
                  "just made" % int(round(_t0 * fps)),
                  '    propertyOverrides      : {"magnification": 1.12, '
                  '"shape": "%s"}' % (q.get("zoom_arc") or "payoff"),
                  "    why                    : %s" % q.get("why"), ""]
            _emitted["zoom"] = _emitted.get("zoom", 0) + 1

    _sfx_rows = [q for q in rows if "sfx" in (q.get("treatment") or [])]
    if _sfx_rows:
        L += ["## 2c. THE SOUND EFFECTS — audio items on their own track", ""]
        for q in _sfx_rows:
            _t0 = _to_timeline(q["src_t0"])
            if _t0 is None:
                raise Incomplete(
                    "a sound effect is ruled at source %.2fs, which the cut "
                    "REMOVED." % q["src_t0"])
            _gi = _idx[0]
            _idx[0] += 1
            L += ["  edit_item adds[%d]:" % _gi,
                  "    type                   : audio",
                  '    assetId                : library:sound:<id> — resolve '
                  'the id ONCE with browse_library category="sound-effects" '
                  'searching %r' % (q.get("sfx_name") or "the beat"),
                  "    from                   : %d" % int(round(_t0 * fps)),
                  "    NOTE: library sounds REFUSE validateOnly by design — "
                  "commit them, do not dry-run them.",
                  "    why                    : %s" % q.get("why"), ""]
            _emitted["sfx"] = _emitted.get("sfx", 0) + 1

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
    L += ["", f"  THE PLAN NAMES {_idx[0]} adds. One edit_item call, "
          f"{_idx[0]} elements. If the timeline",
          "  afterwards holds fewer items than that, the edit is incomplete "
          "and you are not done.",
          "", "## 3. WHAT IS NOT IN THIS EDIT", "",
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
              "  edit_item adds[%d]:" % _gi,
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
    return "\n".join(L)


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
