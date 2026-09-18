#!/usr/bin/env python3
"""GATE B — the cross-checks, moved from the translator to the seam before export.

RULED BY ZAC 2026-09-16, building the single agent: "The thirteen refusals
don't die — they move. They're cross-checks against reality, not against
intention, and every one of them still has a second artefact to compare
against... Build them as harness checks between the placement call and the
export, not as things the agent asks itself. The agent can't self-certify, but
the harness can check its output against ChatCut's state."

THE DISTINCTION THIS FILE IS BUILT ON. A check that reads the plan and the
ruling is reading one artefact twice — the plan was WRITTEN from the ruling, so
agreement between them proves only that the writer was consistent. That is what
`refuse_incomplete` and the reconciliation in plan_for_chatcut.py were doing,
and it is why the reconciliation only ever caught emitter bugs. Here the second
artefact is CHATCUT'S OWN STATE: the items on the timeline, the sound library,
the component's real properties, the composed frames. None of it was written by
the agent whose work is being checked.

TWO RULES ABOUT HOW THE STATE IS OBTAINED, and they are the whole property:

  1. THE HARNESS ISSUES THE READ, NEVER THE AGENT. `preview_timeline` takes
     `tracks`, `fromFrame` and `toFrame`; an agent that chooses the window
     chooses what the gate sees, and a narrow read passes a gate a full read
     fails. `read_back()` in chatcut_job_app.py makes its own calls with no
     window.
  2. THE EXPORT TOOL IS NOT IN THE AGENT'S ALLOWLIST. Telling the agent not to
     export until the gate passes is a preference; not giving it the tool is a
     property. This lane's own law, earned when the prompt said "do not
     orchestrate" and the agent orchestrated anyway.

WHAT THIS MODULE OWNS: everything answerable by ARITHMETIC over the read-back —
the timeline-address family, the reconciliation, and the two catalogue lookups.
Every function here is module level and PURE so a smoke can drive it, rather
than living inside a dispatch where a check would have to restate it.

WHAT IT DELEGATES, AND WHAT IS SIMPLY NOT BUILT YET — the difference matters,
and an earlier draft of this docstring blurred it. Reimplementing the pixel
questions here against item geometry would be a guess: no MG item's y has ever
been read off a live ChatCut timeline in this repo, and this lane asserts only
what it has observed.

  DELEGATED, and already working against COMPOSED frames:
    two placements in one region  -> verify_hop5_composition in
                                     chatcut_job_app.py (per-track renders,
                                     one track hidden; the difference IS that
                                     track's pixels)
    a placement on the speaker's
    face or on the source's own
    burned-in text                -> verify_hop6_clear

  NOT BUILT. Nothing asks these yet and nothing else covers them:
    a card has room once the
    CAPTION band is accounted for -> hop 6 covers the face and the source's
                                     own text; the caption layer is a third
                                     occupant and `read_captions` returns its
                                     Cards in timeline frames, so the question
                                     is answerable and unasked.
    the placement matches the
    CONTROL that was ruled        -> the inverted form of the translator's
                                     "controls unanswered" refusal: the ruling
                                     says `where: upper_third` and the pixels
                                     say where it landed. hop 5's per-track
                                     masks and verify_chain.band_of would
                                     supply the band; NOTHING ASKS. An earlier
                                     version of this docstring listed it under
                                     DELEGATED, which read as covered — a note
                                     that is wrong is worse than one that is
                                     missing, so it is kept here as the
                                     correction.

THREE STATES, AND ABSENT DOES NOT PASS. Every check returns MEASURED, ABSENT or
FAILED. A gate that cannot run is not a gate that passed — the guard that only
checks the value is the oldest failure in this repo.
"""

MEASURED, ABSENT, FAILED = "MEASURED", "ABSENT", "FAILED"
PASS, WITHHOLD = "PASS", "WITHHOLD"

# Family -> the ChatCut item kind that family becomes. Every row was read off a
# live timeline; the table is FAMILY_MAP's `item_kind`, restated here because
# this module must not import the translator it replaces.
FAMILY_ITEM_KIND = {
    "cut":        "video",
    "cutaway":    "video",          # ...but NOT on the base track
    "text":       "motion-graphic",
    "card":       "motion-graphic",
    "sfx":        "audio",
    "zoom":       "effect",
    "transition": "transition",
}
# Families that place nothing and therefore reconcile against nothing.
FAMILY_PLACES_NOTHING = {"none", "caption"}


def finding(check, state, verdict, why, read, beat=None, family=None,
            item=None):
    """One gate finding.

    `read` is not decoration. A check that cannot say what it READ makes the
    next run the debugger — 9 of 10 failures in this repo were the checks
    themselves, and the ones carrying their evidence were fixed in one run
    each. Every finding below names the number it saw.
    """
    return {"check": check, "state": state, "verdict": verdict, "why": why,
            "read": read, "beat": beat, "family": family, "item": item}


# ── THE MAP, READ OFF CHATCUT RATHER THAN OFF OUR PLAN ───────────────────────

def _track_n(alias):
    """V2 -> 2. A track whose alias does not parse sorts LAST, never first."""
    s = str(alias or "")
    d = "".join(c for c in s if c.isdigit())
    return int(d) if d else 10 ** 6


def base_track(items):
    """(alias, state, why) — the video track the CUT lives on.

    The lowest-numbered video track. It matters that this is derived and not
    hardcoded to V1: a cutaway is also a video item pointing at the same
    source, and counting it as part of the cut would make a graphic anchored to
    a removed moment look like it survived — the exact failure the removed-
    moment checks exist to catch, wearing a pass.
    """
    vids = [i for i in (items or []) if str(i.get("itemType")) == "video"]
    if not vids:
        return None, ABSENT, ("no video items on the timeline at all — either "
                              "nothing was placed or the read-back failed. "
                              "Both are ABSENT, and neither is a pass.")
    alias = min((str(i.get("trackAlias") or "") for i in vids), key=_track_n)
    return alias, MEASURED, "%d video item(s), base track %s" % (len(vids),
                                                                 alias)


def kept_spans(items, base, fps=30.0):
    """([(src_a, src_b, f0, f1)], state, why) — the cut, as ChatCut holds it.

    THE UNIT SEAM IS THE TRAP AND IT IS PRESERVED HERE RATHER THAN SMOOTHED
    OVER: `sourceRange` is MICROSECONDS, `timelineRange` is FRAMES. Two axes,
    two units, in one item. Every row below converts the source axis to
    seconds ONCE and keeps the frame axis as frames.

    THE SHAPE IS MEASURED, NOT BORROWED. 2026-09-17, four verbatim items off
    preview_timeline (/tmp/bs/probe_sourcerange.json): `sourceRange` is
    {"start": 0, "end": 20333333} — 20.333s for 610 frames — and
    `timelineRange` is {"fromFrame": 700, "toFrame": 1310}. The previous
    `startSeconds/endSeconds` was submit_export's vocabulary (see
    chatcut_schema.json) and no item ever carries it, so this hard-failed on
    every base-track item, served rewatch 1 empty, and broke the turn machine
    in runs 7, 8 and 9 — the single cause of 38 turns.

    AND AN UNTRIMMED ITEM WITH NO sourceRange IS DERIVED, NOT FAILED (Zac,
    2026-09-17). If the read-back ever omits the source axis, an item that
    plays its whole asset from frame 0 spans source 0..(f1-f0)/fps by
    construction; the why says DERIVED so a run that leaned on it is
    distinguishable from one that read the axis.
    """
    out, derived = [], 0
    for i in (items or []):
        if str(i.get("itemType")) != "video":
            continue
        if str(i.get("trackAlias") or "") != base:
            continue
        sr = i.get("sourceRange") or {}
        tr = i.get("timelineRange") or {}
        try:
            f0, f1 = int(tr["fromFrame"]), int(tr["toFrame"])
        except (KeyError, TypeError, ValueError):
            return [], FAILED, ("a base-track video item is missing its "
                                "timelineRange{fromFrame,toFrame}: %r — "
                                "timelineRange keys %r"
                                % (i.get("id"), sorted((tr or {}).keys())))
        try:
            a, b = float(sr["start"]) / 1e6, float(sr["end"]) / 1e6
        except (KeyError, TypeError, ValueError):
            if not sr:
                a, b = 0.0, (f1 - f0) / float(fps or 30.0)
                derived += 1
            else:
                return [], FAILED, ("a base-track video item carries a "
                                    "sourceRange this reader cannot use: %r — "
                                    "keys %r (expected start/end in "
                                    "microseconds)"
                                    % (i.get("id"), sorted(sr.keys())))
        out.append((a, b, f0, f1))
    out.sort(key=lambda r: r[2])
    if not out:
        return [], ABSENT, "no video items on base track %r" % base
    return out, MEASURED, ("%d kept span(s), source %.2f-%.2fs, timeline "
                           "frames %d-%d%s"
                           % (len(out), out[0][0], out[-1][1],
                              out[0][2], out[-1][3],
                              (" — %d span(s) DERIVED from an untrimmed item "
                               "with no sourceRange" % derived)
                              if derived else ""))


def source_to_timeline(spans, t):
    """(frame, state, why) — where source second `t` lands, or that it was CUT.

    None is NOT a fallback to the raw second. A placement whose moment was
    removed has nowhere to land, and drifting it to the nearest surviving frame
    is how a graphic ends up on a line it was never written for.
    """
    if not spans:
        return None, ABSENT, "no kept spans to address"
    for a, b, f0, f1 in spans:
        if a <= t < b:
            span_frames = f1 - f0
            span_secs = b - a
            if span_secs <= 0:
                return None, FAILED, ("span [%.2f,%.2f) has no duration" % (a, b))
            return (int(round(f0 + (t - a) / span_secs * span_frames)),
                    MEASURED,
                    "source %.2fs is inside kept span [%.2f,%.2f) -> frame"
                    % (t, a, b))
    return None, MEASURED, (
        "source %.2fs is in NO kept span — the cut removed it. Kept: %s"
        % (t, ", ".join("[%.2f,%.2f)" % (a, b) for a, b, _, _ in spans[:6])
           + ("" if len(spans) <= 6 else " ...(%d spans)" % len(spans))))


def timeline_end(spans):
    """(frame, state, why) — the last frame of the edit, from the items."""
    if not spans:
        return None, ABSENT, "no kept spans"
    return max(f1 for _, _, _, f1 in spans), MEASURED, "from the base track"


def manifest_from_items(items, base=None):
    """The placement rows hop 6 needs, DERIVED FROM THE TIMELINE.

    WHY THIS EXISTS. `verify_chain.plan_manifest` reads the PLAN, and there is
    no plan any more. Hops 3, 4, 5 and 6 all guarded on `plan` and so all four
    returned ABSENT on the single-agent path — four of the seven hops silently
    off, including BOTH PIXEL CHECKS, which are the only ones that can see a
    placement that is present but illegible, covered, or on a face.

    Hop 5 turned out not to need it at all: its `man` was assigned and never
    used, and pyflakes had been saying so all day in a warning I read four
    times as pre-existing noise. Hop 6 genuinely needs the rows, and they are
    all on the timeline: the item kind, the frame it starts, how long it runs.

    `slot` is the item id rather than a plan index, because that is the handle
    that exists here — and it is what a finding has to name for anyone to act.
    """
    rows = []
    for i in (items or []):
        kind = str(i.get("itemType") or "")
        if kind not in ("motion-graphic", "video", "audio", "effect",
                        "transition"):
            continue
        if kind == "video" and base is not None \
                and str(i.get("trackAlias") or "") == base:
            continue                      # the cut itself is not a placement
        tr = i.get("timelineRange") or {}
        try:
            f0, f1 = int(tr["fromFrame"]), int(tr["toFrame"])
        except (KeyError, TypeError, ValueError):
            continue
        # THE ASSET NAME IS ON THE ENVELOPE: `asset: {id, name, type}`
        # (probe 2026-09-17). Without it band_of() matched component names
        # against nothing, fell through to the WHOLE FRAME, and run 6's hop 6
        # reported all 13 placements on the face and the source text.
        _as = i.get("asset") if isinstance(i.get("asset"), dict) else {}
        _po = i.get("propertyOverrides") if isinstance(
            i.get("propertyOverrides"), dict) else {}
        rows.append({"type": kind, "from": f0, "dur": max(0, f1 - f0),
                     "slot": str(i.get("id") or "?")[:8],
                     "track": str(i.get("trackAlias") or ""),
                     "asset": str(_as.get("name") or ""),
                     "overrides": _po})
    rows.sort(key=lambda r: (r["from"], r["slot"]))
    return rows


# ── THE CHECKS ───────────────────────────────────────────────────────────────

# THE FAMILIES THE CHECKS KNOW. A treatment token outside this set is not a
# family the gate can check, so it is not a ruling the gate can withhold on.
KNOWN_FAMILIES = {"cut", "card", "text", "title", "sfx", "zoom", "cutaway",
                  "transition", "caption", "none", "nothing"}


def _treatments(v):
    """The families a ruling names, as a list — NEVER the characters of a string.

    MEASURED 2026-09-17 (final-arch-1): the agent wrote
    `treatment: "caption:TwoTone only. There's no screenshot..."` and this
    iterated the STRING, ruling beat 0 as 'c', 'a', 'p', 't'... — 1,324
    findings per check, 2,648 withholds, on a record that named one family.
    A prose treatment is tokenised and filtered to KNOWN_FAMILIES; a list is
    read as before. `caption:TwoTone` yields `caption` (a family that places
    nothing the gate checks) and component names yield nothing here — the
    placements themselves are read off the timeline, not off this field.
    """
    t = v.get("treatment")
    if isinstance(t, str):
        import re as _re
        toks = [x.split(":", 1)[0] for x in _re.split(r"[^A-Za-z0-9_:]+", t.lower()) if x]
        fams = [x for x in toks if x in KNOWN_FAMILIES]
    elif isinstance(t, (list, tuple)):
        fams = [str(x).lower().split(":", 1)[0] for x in t]
    else:
        fams = []
    return [f for f in fams if f not in FAMILY_PLACES_NOTHING and f != "nothing"]


def _edit_anchor_explicit(v):
    """WHERE IN THE EDIT this ruling lands, in SOURCE seconds, and which field.

    THE CUTAWAY IS NOT ADDRESSED THE SAME WAY, and my first version of this got
    it backwards — the fifth instance in this repo of a question written for
    text being asked of every family, inside the module built to stop exactly
    that.

    It returned `cutaway_from_s` as a cutaway's anchor, so the survival check
    then demanded that the moment a cutaway CUTS TO had itself survived the
    cut. That is the opposite of what a cutaway is: it pulls footage from
    elsewhere in the source — usually from a stretch the edit removed — and
    plays it over the main line. Verified live on 2026-09-16: `item V2
    range=[60,150) source=[18000000,21000000)us`, source seconds 18-21 playing
    while V1 is at second 2. The gate would have withheld every correct
    cutaway, and 47% of Zac's reference beats are cutaways.

    Two different questions, two different fields:
        src_t0 / keep_from_s  WHEN IN THE EDIT it appears  -> must survive
        cutaway_from_s        WHAT IT SHOWS                -> must be a real
                                                              source second,
                                                              and must NOT
    """
    for k in ("src_t0", "keep_from_s"):
        if v.get(k) is not None:
            return float(v[k]), k
    return None, None


def _edit_anchor(v, beats=None):
    """The ruling's source anchor, explicit or BY BEAT INDEX. -> (t, field)

    THE LAST GATE ON THE OLD RECORD SHAPE (Zac, 2026-09-17). The planner wrote
    `cutaway_from_s` / `src_t0` / `keep_from_s` on every ruling; this path's
    rulings carry a `beat` index and the harness already knows each beat's
    t_start. A ruling with no explicit anchor resolves to its beat's start —
    the same moment the agent was shown when it ruled — and only a beat the
    harness never produced reads ABSENT.
    """
    t, field = _edit_anchor_explicit(v)
    if t is not None or not beats:
        return t, field
    try:
        _i = int(v.get("beat"))
    except (TypeError, ValueError):
        return None, None
    for b in beats:
        if int(b.get("i", -1)) == _i and b.get("t_start") is not None:
            return float(b["t_start"]), "beat %d t_start" % _i
    return None, None


def check_ruled_moment_survives(rulings, spans, beats=None):
    """A placement anchored at a source second THE CUT REMOVED.

    Three of the thirteen were this one check asked of three families — a
    graphic, a sound, a zoom. It is one question and it is asked once here,
    because a question written for text and then asked of every family is a
    defect this lane has already had to fix three times.
    """
    out = []
    if not spans:
        return [finding("ruled_moment_survives", ABSENT, WITHHOLD,
                        "the cut could not be read, so no anchor can be "
                        "checked against it", "no kept spans")]
    for v in (rulings or []):
        for fam in _treatments(v):
            if fam == "cut":
                continue
            t, field = _edit_anchor(v, beats)
            if t is None:
                out.append(finding(
                    "ruled_moment_survives", ABSENT, WITHHOLD,
                    "beat %s ruled %r carries no source anchor, so nothing can "
                    "say whether its moment survived the cut" % (v.get("beat"),
                                                                 fam),
                    "looked for cutaway_from_s, src_t0, keep_from_s, then the "
                    "beat index against %d beat(s)" % len(beats or []),
                    beat=v.get("beat"), family=fam))
                continue
            frame, st, why = source_to_timeline(spans, t)
            if st != MEASURED:
                out.append(finding("ruled_moment_survives", st, WITHHOLD,
                                   "beat %s (%s): %s" % (v.get("beat"), fam,
                                                         why),
                                   why, beat=v.get("beat"), family=fam))
            elif frame is None:
                out.append(finding(
                    "ruled_moment_survives", MEASURED, WITHHOLD,
                    "beat %s is ruled %r at source %.2fs (%s), which the cut "
                    "REMOVED. It has no timeline moment to land on."
                    % (v.get("beat"), fam, t, field),
                    why, beat=v.get("beat"), family=fam))
    return out or [finding("ruled_moment_survives", MEASURED, PASS,
                           "every anchored ruling falls inside a kept span",
                           "%d span(s) checked" % len(spans))]


def check_inside_timeline(rulings, spans, fps):
    """A placement past the end stretches the render to hold a graphic over
    nothing — that is how a 58.03s edit delivered as 71.68s."""
    end, st, why = timeline_end(spans)
    if st != MEASURED:
        return [finding("inside_timeline", st, WITHHOLD,
                        "the timeline end could not be read", why)]
    out = []
    for v in (rulings or []):
        for fam in _treatments(v):
            if fam == "cut":
                continue
            t, _ = _edit_anchor(v)
            if t is None:
                continue
            frame, s2, w2 = source_to_timeline(spans, t)
            if s2 == MEASURED and frame is not None and frame >= end:
                out.append(finding(
                    "inside_timeline", MEASURED, WITHHOLD,
                    "beat %s (%s) resolves to frame %d, past the %d-frame "
                    "timeline" % (v.get("beat"), fam, frame, end),
                    "timeline end %d frames (%.2fs at %g fps)"
                    % (end, end / float(fps or 30), fps),
                    beat=v.get("beat"), family=fam))
    return out or [finding("inside_timeline", MEASURED, PASS,
                           "every placement resolves inside the timeline",
                           "timeline end %d frames" % end)]


def check_zoom_has_an_item(items):
    """An EFFECT WITH NO ITEM TO SIT ON is a placement nobody can execute.

    Read off the timeline rather than off the plan: the effect item names a
    `targetItemId`, and the question is whether that id is a real item whose
    timeline range covers the effect. In the translator this was arithmetic
    over adds we were about to emit; here it is two facts ChatCut holds.
    """
    by_id = {str(i.get("id")): i for i in (items or []) if i.get("id")}
    effects = [i for i in (items or []) if str(i.get("itemType")) == "effect"]
    if not effects:
        return [finding("zoom_has_an_item", MEASURED, PASS,
                        "no effect items to check", "%d item(s) read"
                        % len(items or []))]
    out = []
    for e in effects:
        tgt = str(e.get("targetItemId") or "")
        if not tgt:
            out.append(finding("zoom_has_an_item", ABSENT, WITHHOLD,
                               "effect %s names no targetItemId"
                               % e.get("id"), "targetItemId missing",
                               item=e.get("id")))
            continue
        # ChatCut resolves an id PREFIX and returns ok, so a prefix match is
        # a real landing and an exact-only lookup would report a false absence.
        # HYPHENS OUT BEFORE THE PREFIX TEST. edit_item echoes `78d2b44bc6`;
        # preview_timeline returns `78d2b44b-c6b1-...`; a raw startswith
        # matches eight characters and dies on the hyphen, so every landed
        # target read as absent (measured on the 2026-09-17 probe).
        _n = lambda x: str(x or "").replace("-", "")                # noqa: E731
        host = by_id.get(tgt) or next(
            (v for k, v in by_id.items()
             if _n(k).startswith(_n(tgt)) or _n(tgt).startswith(_n(k))), None)
        if host is None:
            out.append(finding(
                "zoom_has_an_item", MEASURED, WITHHOLD,
                "effect %s targets item %s, which is not on the timeline"
                % (e.get("id"), tgt),
                "%d items read, none matching" % len(by_id), item=e.get("id")))
            continue
        er = e.get("timelineRange") or {}
        hr = host.get("timelineRange") or {}
        try:
            e0, e1 = int(er["fromFrame"]), int(er["toFrame"])
            h0, h1 = int(hr["fromFrame"]), int(hr["toFrame"])
        except (KeyError, TypeError, ValueError):
            out.append(finding("zoom_has_an_item", FAILED, WITHHOLD,
                               "effect %s or its host carries no timelineRange"
                               % e.get("id"), "ranges unreadable",
                               item=e.get("id")))
            continue
        if not (h0 <= e0 and e1 <= h1):
            out.append(finding(
                "zoom_has_an_item", MEASURED, WITHHOLD,
                "effect %s covers frames [%d,%d) but its host item covers "
                "[%d,%d) — the zoom runs past the clip it is on"
                % (e.get("id"), e0, e1, h0, h1),
                "effect [%d,%d) host [%d,%d)" % (e0, e1, h0, h1),
                item=e.get("id")))
    return out or [finding("zoom_has_an_item", MEASURED, PASS,
                           "every effect sits on an item that covers it",
                           "%d effect(s)" % len(effects))]


def _kind_items(items, family, base):
    """The items that COULD have come from this family."""
    kind = FAMILY_ITEM_KIND.get(family)
    if kind is None:
        return None
    got = [i for i in (items or []) if str(i.get("itemType")) == kind]
    if family == "cutaway":
        got = [i for i in got if str(i.get("trackAlias") or "") != base]
    elif family == "cut":
        got = [i for i in got if str(i.get("trackAlias") or "") == base]
    return got


def check_every_ruling_landed(rulings, items, spans, base, fps):
    """DID THE RULING BECOME A THING ON THE TIMELINE.

    THE ONE THAT GETS STRICTLY BETTER FOR BEING HERE. In the translator this
    compared rulings against the plan text written from those same rulings —
    self-referential, and it only ever caught emitter bugs. Against ChatCut's
    item list it answers what it was always meant to.

    ATTRIBUTION WITHOUT SELF-REPORT, AND WITHOUT A THRESHOLD. A ruling is
    matched to an item of its family's kind whose timeline range OVERLAPS the
    ruled window. Overlap is tolerance-free on purpose: this repo has been
    burned three times by a bar fitted to one draw, and "did the graphic land
    anywhere on the beat it was ruled for" needs no constant. A placement that
    does not even touch its beat is a real finding whatever the tolerance.
    """
    if not spans:
        return [finding("every_ruling_landed", ABSENT, WITHHOLD,
                        "the cut could not be read", "no kept spans")]
    fps = float(fps or 30)
    out, used = [], set()
    ruled_n, landed_n = 0, 0
    for v in (rulings or []):
        for fam in _treatments(v):
            if fam == "cut":
                continue
            ruled_n += 1
            cand = _kind_items(items, fam, base)
            if cand is None:
                out.append(finding(
                    "every_ruling_landed", ABSENT, WITHHOLD,
                    "beat %s ruled %r and nothing here knows what item kind "
                    "that becomes — a family with no entry is refused rather "
                    "than waved through" % (v.get("beat"), fam),
                    "FAMILY_ITEM_KIND has %s" % sorted(FAMILY_ITEM_KIND),
                    beat=v.get("beat"), family=fam))
                continue
            t, _f = _edit_anchor(v)
            if t is None:
                continue          # already reported by ruled_moment_survives
            frame, st, _w = source_to_timeline(spans, t)
            if st != MEASURED or frame is None:
                continue          # already reported by ruled_moment_survives
            hold = float(v.get("hold_s") or 0) or (1.0 / fps)
            w0, w1 = frame, frame + max(1, int(round(hold * fps)))
            hit = None
            for i in cand:
                if id(i) in used:
                    continue
                tr = i.get("timelineRange") or {}
                try:
                    a, b = int(tr["fromFrame"]), int(tr["toFrame"])
                except (KeyError, TypeError, ValueError):
                    continue
                if a < w1 and w0 < b:
                    hit = i
                    break
            if hit is None:
                out.append(finding(
                    "every_ruling_landed", MEASURED, WITHHOLD,
                    "beat %s ruled %r and NO %s item overlaps its window "
                    "[%d,%d). The ruling did not become a thing on the "
                    "timeline." % (v.get("beat"), fam,
                                   FAMILY_ITEM_KIND[fam], w0, w1),
                    "%d %s item(s) on the timeline: %s"
                    % (len(cand), FAMILY_ITEM_KIND[fam],
                       [(i.get("timelineRange") or {}).get("fromFrame")
                        for i in cand][:8]),
                    beat=v.get("beat"), family=fam))
            else:
                landed_n += 1
                used.add(id(hit))
    if out:
        return out
    return [finding("every_ruling_landed", MEASURED, PASS,
                    "every ruling has an item on the timeline",
                    "ruled %d, landed %d" % (ruled_n, landed_n))]


def check_cutaway_addressable(rulings, source_duration_s):
    """A cutaway CUTS TO a real second of the source — and to any of them.

    THE OTHER HALF OF SEPARATING THE TWO ANCHORS. `_edit_anchor` no longer
    hands `cutaway_from_s` to the survival check, because a cutaway pulling
    footage from a removed stretch is the whole point of a cutaway, not a
    defect. That leaves this field checked by nothing, and an unchecked field
    is how a family arrives at ChatCut with a blank in it.

    So the question it SHOULD be asked, which is a different one: is that
    second inside the source at all. A cutaway addressed past the end of the
    footage resolves to nothing and places an empty item.

    ABSENT WHEN THE DURATION IS NOT KNOWN, never a pass. A duration nobody
    read and a cutaway that is in range are not the same fact.
    """
    cut = [v for v in (rulings or []) if "cutaway" in _treatments(v)]
    if not cut:
        return [finding("cutaway_addressable", MEASURED, PASS,
                        "no cutaways ruled", "0 cutaway rulings")]
    if not source_duration_s:
        return [finding("cutaway_addressable", ABSENT, WITHHOLD,
                        "%d cutaway(s) ruled and the source duration could "
                        "not be read, so none of their addresses can be "
                        "checked" % len(cut),
                        "source_duration_s=%r" % (source_duration_s,))]
    out = []
    for v in cut:
        t = v.get("cutaway_from_s")
        if t is None:
            out.append(finding(
                "cutaway_addressable", ABSENT, WITHHOLD,
                "beat %s ruled a cutaway and never said what it cuts TO"
                % v.get("beat"), "cutaway_from_s missing",
                beat=v.get("beat"), family="cutaway"))
        elif not (0 <= float(t) < float(source_duration_s)):
            out.append(finding(
                "cutaway_addressable", MEASURED, WITHHOLD,
                "beat %s cuts to source %.2fs, which is outside the %.2fs "
                "source" % (v.get("beat"), float(t), float(source_duration_s)),
                "source duration %.2fs" % float(source_duration_s),
                beat=v.get("beat"), family="cutaway"))
    return out or [finding("cutaway_addressable", MEASURED, PASS,
                           "every cutaway addresses a real source second",
                           "%d cutaway(s), source %.2fs"
                           % (len(cut), float(source_duration_s)))]


# The planner's `where` vocabulary -> production's band names. It MIRRORS
# `agentic_editor_app._WHERE_TO_ANCHOR` and `smoke_the_gate_checks_reality`
# asserts the two keep agreeing, because two derivations agreeing is the
# strongest evidence available that a rule is real and neither was invented —
# and a silent drift here would judge every placement against the wrong band.
#
# `full_frame` constrains nothing: a graphic that spans the frame occupies
# every band by construction, so asking which one it is "in" has no answer.
WHERE_TO_BAND = {"middle": "center", "upper_third": "top",
                 "lower_third": "bottom", "corner": "top",
                 "full_frame": None}


def check_placement_matches_control(rulings, items, spans, fps, bands):
    """DID IT LAND WHERE THE RULING SAID — pixels against the recorded control.

    THE INVERTED FORM of the translator's "controls unanswered" refusal. That
    one asked whether the agent had ANSWERED `where`, which is
    intention-against-intention and the reason it had to move. This asks
    whether the pixels agree with the answer, which needs two artefacts: the
    ruling, and hop 6's measured band for the item that ruling produced.

    IT WAS LISTED AS DELEGATED AND WAS NOT BUILT. An earlier docstring in this
    module put it under "delegated to hop 5's per-track masks", which read as
    covered — hop 5 measures masks and asks only whether two of them overlap,
    and nothing anywhere compared a band to a `where`. A note that is wrong is
    worse than a note that is missing.

    ABSENT WHEN THE BANDS COULD NOT BE MEASURED, never a pass: a hop 6 that
    failed to load its detectors and a placement that landed correctly must not
    read the same.
    """
    want = [v for v in (rulings or [])
            if ({"text", "card"} & set(_treatments(v)))
            and str(v.get("where") or "").strip()]
    if not want:
        return [finding("placement_matches_control", MEASURED, PASS,
                        "no placement carries a `where` to check",
                        "%d ruling(s)" % len(rulings or []))]
    if not bands:
        return [finding("placement_matches_control", ABSENT, WITHHOLD,
                        "%d placement(s) name a band and hop 6 measured none, "
                        "so where they actually landed is UNCHECKED"
                        % len(want), "bands=%r" % (bands,))]
    fpsf = float(fps or 30)
    out, used = [], set()
    for v in want:
        w = str(v.get("where")).strip().lower()
        if w not in WHERE_TO_BAND:
            out.append(finding(
                "placement_matches_control", ABSENT, WITHHOLD,
                "beat %s ruled where=%r, which maps to no band — nothing can "
                "say whether it landed there" % (v.get("beat"), w),
                "known: %s" % sorted(WHERE_TO_BAND), beat=v.get("beat")))
            continue
        expect = WHERE_TO_BAND[w]
        if expect is None:
            continue                     # full_frame occupies every band
        t, _f = _edit_anchor(v)
        if t is None:
            continue                     # reported by ruled_moment_survives
        frame, st, _wy = source_to_timeline(spans, t)
        if st != MEASURED or frame is None:
            continue
        hold = float(v.get("hold_s") or 0) or (1.0 / fpsf)
        w0, w1 = frame, frame + max(1, int(round(hold * fpsf)))
        hit = None
        for i in (items or []):
            if str(i.get("itemType")) != "motion-graphic" or id(i) in used:
                continue
            tr = i.get("timelineRange") or {}
            try:
                a, b = int(tr["fromFrame"]), int(tr["toFrame"])
            except (KeyError, TypeError, ValueError):
                continue
            if a < w1 and w0 < b:
                hit = i
                break
        if hit is None:
            continue                     # reported by every_ruling_landed
        used.add(id(hit))
        slot = str(hit.get("id") or "")[:8]
        got = (bands or {}).get(slot)
        if not got:
            out.append(finding(
                "placement_matches_control", ABSENT, WITHHOLD,
                "beat %s ruled where=%r and item %s has no measured band — "
                "UNCHECKED, not correct" % (v.get("beat"), w, slot),
                "hop 6 measured %d band(s): %s"
                % (len(bands), sorted(bands)[:6]),
                beat=v.get("beat"), item=hit.get("id")))
            continue
        names = set(got.get("names") or ())
        if expect not in names:
            out.append(finding(
                "placement_matches_control", MEASURED, WITHHOLD,
                "beat %s ruled where=%r (the %s band) and its pixels landed in "
                "%s" % (v.get("beat"), w, expect, sorted(names) or "no band"),
                "measured band %s" % (got.get("band"),),
                beat=v.get("beat"), item=hit.get("id")))
    return out or [finding("placement_matches_control", MEASURED, PASS,
                           "every placement landed in the band it was ruled "
                           "for", "%d checked against hop 6's bands"
                           % len(want))]


def check_sfx_names_resolve(rulings, library_ids):
    """Every ruled sound is a recording the LIVE library actually carries.

    `library_ids` comes from a browse_library call the harness makes, not from
    the JSON cached beside the translator. A cached catalogue and a live one
    are indistinguishable right up until they are not, and a map that has
    drifted from its library is exactly the silent-empty-map rot this check
    was written for.
    """
    want = [(v.get("beat"), str(v.get("sfx_name") or "").strip().lower())
            for v in (rulings or []) if "sfx" in _treatments(v)]
    if not want:
        return [finding("sfx_names_resolve", MEASURED, PASS,
                        "no sounds ruled", "0 sfx rulings")]
    if library_ids is None:
        return [finding("sfx_names_resolve", ABSENT, WITHHOLD,
                        "%d sound(s) ruled and the library could not be read, "
                        "so none of them can be checked" % len(want),
                        "browse_library returned nothing")]
    ids = {str(s).lower() for s in library_ids}
    out = []
    for beat, name in want:
        if not name:
            out.append(finding("sfx_names_resolve", ABSENT, WITHHOLD,
                               "beat %s ruled sfx with no name" % beat,
                               "sfx_name empty", beat=beat, family="sfx"))
        elif name not in ids and not any(i.endswith(name) for i in ids):
            out.append(finding(
                "sfx_names_resolve", MEASURED, WITHHOLD,
                "beat %s ruled sound %r and the library has no such "
                "recording" % (beat, name),
                "%d sound(s) in the library" % len(ids),
                beat=beat, family="sfx"))
    return out or [finding("sfx_names_resolve", MEASURED, PASS,
                           "every ruled sound is in the library",
                           "%d ruled, %d in library" % (len(want), len(ids)))]


def check_card_props_resolve(rulings, component_props, items=None,
                             base=None):
    """A card ARRIVED CARRYING properties the component actually declares.

    THE CARD WAS LOST AT THE LAUNCHER ONCE ALREADY: registered into an asset
    with no card properties, placed, counted, and green. So the question is
    asked of the PLACED ITEM, not of the ruling — `propertyOverrides` on the
    motion-graphic item, against the component library's declared keys. Two
    artefacts, neither of them the agent's intention.

    MY OWN FIRST VERSION OF THIS CHECKED ONLY THAT `card_hero` WAS NON-EMPTY,
    computed the component's keys, and never compared against them. It read
    like a contract check and was a presence check — kept as the correction,
    because the wrong version is the evidence that the class recurs.
    """
    cards = [v for v in (rulings or []) if "card" in _treatments(v)]
    if not cards:
        return [finding("card_props_resolve", MEASURED, PASS,
                        "no cards ruled", "0 card rulings")]
    if not component_props:
        return [finding("card_props_resolve", ABSENT, WITHHOLD,
                        "%d card(s) ruled and the component's properties "
                        "could not be read, so nothing can say whether they "
                        "carry anything" % len(cards),
                        "component_props empty")]
    keys = {str(k) for k in component_props}
    out = []
    for v in cards:
        if not str(v.get("card_hero") or "").strip():
            out.append(finding("card_props_resolve", ABSENT, WITHHOLD,
                               "beat %s ruled card with no card_hero"
                               % v.get("beat"), "card_hero empty",
                               beat=v.get("beat"), family="card"))
    # ...and the placed items must CARRY something the component declares.
    mgs = [i for i in (items or [])
           if str(i.get("itemType")) == "motion-graphic"]
    if cards and items is not None:
        bare = [i for i in mgs if not (i.get("propertyOverrides") or {})]
        if len(mgs) and len(bare) == len(mgs):
            out.append(finding(
                "card_props_resolve", MEASURED, WITHHOLD,
                "%d card(s) ruled and not one motion-graphic item on the "
                "timeline carries any propertyOverrides — this is the shape "
                "that shipped a graphic rendering its title and no card"
                % len(cards),
                "%d motion-graphic item(s), %d with empty propertyOverrides"
                % (len(mgs), len(bare)), family="card"))
        for i in mgs:
            po = i.get("propertyOverrides") or {}
            stray = sorted({str(k) for k in po} - keys)
            if stray:
                out.append(finding(
                    "card_props_resolve", MEASURED, WITHHOLD,
                    "item %s sets %s, which the component does not declare — "
                    "an override on a property nobody reads renders nothing"
                    % (i.get("id"), stray),
                    "component declares %s" % sorted(keys)[:8],
                    family="card", item=i.get("id")))
    return out or [finding("card_props_resolve", MEASURED, PASS,
                           "every card carries properties the component "
                           "declares",
                           "%d card(s), component declares %s"
                           % (len(cards), sorted(keys)[:6]))]


def check_record_exists(rulings, spec):
    """THE DURABLE ARTEFACT IS PRESENT, OR NOTHING ELSE MEANS ANYTHING.

    THE HOLE THIS CLOSES, FOUND BY DRIVING MY OWN GATE: with `rulings` empty,
    every check above returns PASS — "ruled 0, landed 0", "no sounds ruled",
    "no cards ruled" — and the gate green-lights an export by an agent that
    recorded nothing. Absence rendered as success, in the gate written to stop
    exactly that, and it would have passed silently on any run where the agent
    skipped the write.

    AND THE SPEC IS LOAD-BEARING SEPARATELY. `spec.why` is the field the 43%
    was found in — seven ledgers compared, and the reason one of them gave was
    "no vibe language, so scope is limited to those two families only." A run
    that does not record its mode and its why is a run whose failure is not
    diagnosable afterwards, which is the capability the split was keeping.
    """
    out = []
    if not rulings:
        out.append(finding(
            "record_exists", ABSENT, WITHHOLD,
            "no rulings were recorded. Every other check reads as a pass on an "
            "empty record — 'ruled 0, landed 0' — so this is withheld rather "
            "than waved through.",
            "rulings=%r" % (rulings,)))
    if not spec:
        out.append(finding(
            "record_exists", ABSENT, WITHHOLD,
            "no spec was recorded. The mode and its `why` are how an edit that "
            "delivers nothing is diagnosed at all.", "spec=%r" % (spec,)))
    else:
        for k in ("mode", "why"):
            if not str((spec or {}).get(k) or "").strip():
                out.append(finding(
                    "record_exists", ABSENT, WITHHOLD,
                    "the spec records no %r. Without it a run that scopes "
                    "itself down to nothing looks identical to a run with "
                    "nothing to do." % k, "spec keys %s" % sorted(spec)))
    return out or [finding("record_exists", MEASURED, PASS,
                           "the spec and the rulings are both recorded",
                           "mode=%r, %d ruling(s)"
                           % ((spec or {}).get("mode"), len(rulings)))]


# The y-band each `where` occupies, in FRACTIONS of frame height. Mirrors
# face_bands.MG_FACE_BAND_YRANGES (top 120-640, center 640-1280, bottom
# 1280-1800 of 1920) and smoke_the_gate_checks_reality asserts the two agree.
BAND_FRACTIONS = {"top": (120/1920.0, 640/1920.0),
                  "center": (640/1920.0, 1280/1920.0),
                  "bottom": (1280/1920.0, 1800/1920.0)}
# Families that sit on a LAYER, and therefore have a band, a collision list and
# a face question. A transition is a seam and a sound is not on screen at all;
# asking either "is it clear of the face" is the text-shaped check applied to
# everything, which this lane has already had to fix three times.
ON_A_LAYER = {"text", "card", "cutaway"}


def acceptance_lines(rulings, spans, fps, face_state="ABSENT",
                     caption_band=None, source_duration_s=None,
                     face_traj=None):
    """PER PLACEMENT: the band, the collisions, the frame, the face question.

    THIS IS THE 96 SECONDS. The translator generated a block exactly like this
    and the merge dropped it — it was prose the PLAN carried, and with no plan
    nothing replaced it. Measured on run-1789522875: the review cost 125.8s of
    a 90-second budget, 119.5s of it `thinking`, because the agent had to
    derive what to check from a generic list ("something illegible, off-frame,
    on a face") instead of being handed the criteria for ITS OWN placements.
    The harness holds the rulings when it sends the frames, so it can generate
    what the translator used to.

    EVERY LINE IS A CHECK WITH AN ANSWER, NOT A JUDGEMENT. A criterion the
    harness cannot compute says NOT CHECKED and says why — a face clearance
    printed as "MEASURED clear" when no detector ran is absence rendered as a
    value, and it was the most dangerous bug this lane shipped.
    """
    out, placed = [], []
    fpsf = float(fps or 30)
    for v in (rulings or []):
        for fam in _treatments(v):
            if fam == "cut":
                continue
            t, _f = _edit_anchor(v)
            if t is None:
                continue
            frame, st, _w = source_to_timeline(spans, t)
            if st != MEASURED or frame is None:
                continue
            hold = float(v.get("hold_s") or 0) or (1.0 / fpsf)
            f0, f1 = frame, frame + max(1, int(round(hold * fpsf)))
            # JUDGED AT THE SETTLED FRAME, not the entrance. An entrance is
            # mid-animation and every placement looks wrong there; production
            # settles 8 frames in, or the midpoint on a short one.
            settle = min(f0 + 8, f0 + max(1, (f1 - f0) // 2))
            # THE SOURCE TIME TRAVELS WITH THE PLACEMENT. The face
            # trajectory is sampled on the SOURCE video in source seconds;
            # f0/f1 are TIMELINE frames. Asking the trajectory about a
            # timeline frame is a measurement of the wrong thing, and it
            # would read as a clean answer.
            placed.append({"fam": fam, "beat": v.get("beat"), "f0": f0,
                           "f1": f1, "settle": settle,
                           "src_t": t, "hold_s": hold,
                           "where": str(v.get("where") or "").strip().lower(),
                           "text": v.get("text_content") or v.get("card_hero")})
    for i, a in enumerate(placed, 1):
        out.append("  %d. %s on beat %s%s"
                   % (i, a["fam"].upper(), a["beat"],
                      (" — %r" % str(a["text"])[:48]) if a["text"] else ""))
        out.append("      judged at    : frame %d (settled; frames %d-%d)"
                   % (a["settle"], a["f0"], a["f1"]))
        if a["fam"] not in ON_A_LAYER:
            out.append("      band / face  : n/a — %s does not sit on a layer"
                       % a["fam"])
            continue
        _b = BAND_FRACTIONS.get(WHERE_TO_BAND.get(a["where"]) or "")
        if _b:
            out.append("      stays inside : the %s band, y %.0f-%.0f of 1920 "
                       "(ruled where=%s)"
                       % (WHERE_TO_BAND[a["where"]], _b[0]*1920, _b[1]*1920,
                          a["where"]))
        else:
            out.append("      stays inside : NOT CHECKED — where=%r maps to no "
                       "band, so nothing here can say where it belongs"
                       % a["where"])
        _col = [x for x in placed
                if x is not a and x["fam"] in ON_A_LAYER
                and x["f0"] < a["f1"] and a["f0"] < x["f1"]]
        out.append("      must not touch: %s"
                   % (", ".join("%s on beat %s (frames %d-%d)"
                                % (c["fam"].upper(), c["beat"], c["f0"], c["f1"])
                                for c in _col) or "nothing else is on screen"))
        if caption_band:
            out.append("                      the caption track, y %.0f-%.0f "
                       "— MEASURED from read_captions, not guessed"
                       % (caption_band[0]*1920, caption_band[1]*1920))
        else:
            out.append("                      the caption track — ITS BAND WAS "
                       "NOT READ, so judge that one BY EYE at the frame above")
        _fs = str(face_state or "ABSENT").upper()
        if a["fam"] == "cutaway":
            out.append("      clear of face: n/a — a cutaway REPLACES the "
                       "picture in its span, so a face under it is covered by "
                       "design")
        elif _fs.startswith("MEASURED"):
            # "THE DETECTOR RAN" IS NOT AN ANSWER. The question is whether
            # THIS placement sits on the face, and the trajectory can say so.
            # A MEASURED state that reports only its own existence is the
            # same shape as a count with no denominator.
            _occ, _ow = set(), None
            # MEASURED WITH NO TRAJECTORY IS NOT "NO FACE". `face_occupied_
            # bands(None, ...)` returns an empty set, which renders as
            # "the face occupies no band" — a clearance nobody measured,
            # wearing the words of one that was. The state and the evidence
            # must agree or the line refuses to answer.
            if not face_traj:
                out.append("      clear of face: NOT CHECKED — the state says "
                           "MEASURED but NO TRAJECTORY ARRIVED, so nothing "
                           "here knows where the face is. JUDGE IT BY EYE at "
                           "frame %d." % a["settle"])
                continue
            try:
                import face_bands as _fb
                _occ = _fb.face_occupied_bands(
                    face_traj, float(a["src_t"]),
                    float(a["src_t"]) + float(a["hold_s"]))
            except Exception as _fe:                              # noqa: BLE001
                _ow = "%s: %s" % (type(_fe).__name__, str(_fe)[:90])
            _mine = WHERE_TO_BAND.get(a["where"])
            if _ow:
                out.append("      clear of face: NOT CHECKED — the detector "
                           "measured this source but the bands could not be "
                           "computed (%s). JUDGE IT BY EYE at frame %d."
                           % (_ow, a["settle"]))
            elif _mine and _mine in _occ:
                out.append("      clear of face: COLLISION — the face occupies "
                           "the %s band across source %.2f-%.2fs, and this is "
                           "ruled INTO %s. It is on his face. Move it or say "
                           "why it belongs there."
                           % (_mine, a["src_t"], a["src_t"] + a["hold_s"],
                              _mine))
            elif _mine:
                out.append("      clear of face: CLEAR — the face occupies %s "
                           "across source %.2f-%.2fs; this sits in %s"
                           % (", ".join(sorted(_occ)) or "no band", a["src_t"],
                              a["src_t"] + a["hold_s"], _mine))
            else:
                out.append("      clear of face: the face occupies %s across "
                           "source %.2f-%.2fs, but where=%r maps to no band so "
                           "nothing can compare them. JUDGE IT BY EYE at frame "
                           "%d."
                           % (", ".join(sorted(_occ)) or "no band", a["src_t"],
                              a["src_t"] + a["hold_s"], a["where"],
                              a["settle"]))
        else:
            out.append("      clear of face: NOT CHECKED — no face regions on "
                       "this run (%s). Nobody looked. JUDGE IT BY EYE at frame "
                       "%d and say so if it is on his face." % (_fs, a["settle"]))
    if not out:
        return ["  (no placements carry acceptance criteria — either nothing "
                "was ruled, or nothing resolved to a timeline moment)"]
    return out


# ── THE GATE, AND WHAT IT WITHHOLDS ─────────────────────────────────────────

def gate(rulings, state):
    """Run every arithmetic check against the read-back. -> report dict.

    `state` is what the HARNESS read, never what the agent said:
        items         preview_timeline, no window, every track
        fps           the timeline's canvas
        library_ids   browse_library category="sound-effects"
        component_props  the card component's declared properties
    """
    items = state.get("items")
    fps = state.get("fps") or 30
    if items is None:
        return {"state": ABSENT, "verdict": WITHHOLD,
                "findings": [finding("read_back", ABSENT, WITHHOLD,
                                     "the harness could not read the timeline "
                                     "back, so nothing was checked",
                                     state.get("read_why") or "no items")],
                "checked": 0}
    base, bst, bwhy = base_track(items)
    spans, sst, swhy = (kept_spans(items, base, fps) if base
                        else ([], ABSENT, bwhy))
    fs = []
    if bst != MEASURED:
        fs.append(finding("base_track", bst, WITHHOLD, bwhy, bwhy))
    if sst != MEASURED:
        fs.append(finding("kept_spans", sst, WITHHOLD, swhy, swhy))
    fs += check_record_exists(rulings, state.get("spec"))
    fs += check_ruled_moment_survives(rulings, spans, state.get("beats"))
    fs += check_inside_timeline(rulings, spans, fps)
    fs += check_zoom_has_an_item(items)
    fs += check_every_ruling_landed(rulings, items, spans, base, fps)
    fs += check_placement_matches_control(rulings, items, spans, fps,
                                         state.get("bands"))
    fs += check_cutaway_addressable(rulings,
                                    state.get("source_duration_s"))
    fs += check_sfx_names_resolve(rulings, state.get("library_ids"))
    fs += check_card_props_resolve(rulings, state.get("component_props"),
                                   items, base)
    bad = [f for f in fs if f["verdict"] != PASS]
    return {"state": MEASURED if not any(f["state"] == FAILED for f in fs)
                     else FAILED,
            "verdict": WITHHOLD if bad else PASS,
            "findings": fs, "bad": bad, "checked": len(fs),
            "base_track": base, "spans": len(spans)}


def withhold(report):
    """(remove, unbuilt) — what to take off the timeline, and what never landed.

    ZAC'S RULING, 2026-09-16: withhold the placement, export the rest, name it
    in the ledger. It is the graceful drop production already does for a
    graphic that cannot clear a face — a component was considered and not
    placed, which is a decision an editor makes constantly.

    THE TWO CASES ARE DIFFERENT AND THE LEDGER MUST NOT CONFLATE THEM. An item
    that landed and is wrong is REMOVED. A ruling that never landed has nothing
    to remove and is recorded as unbuilt. DROPPED and UNBUILDABLE reading the
    same in a ledger is a distinction this lane built on purpose and then had
    turned back on it.
    """
    remove, unbuilt = [], []
    for f in (report.get("bad") or []):
        if f.get("item"):
            remove.append({"item": f["item"], "why": f["why"],
                           "check": f["check"]})
        else:
            unbuilt.append({"beat": f.get("beat"), "family": f.get("family"),
                            "why": f["why"], "check": f["check"]})
    return remove, unbuilt


def report_lines(report):
    """The gate, as the agent is shown it. Findings first, evidence attached."""
    L = ["GATE — the harness read ChatCut back and checked your placements "
         "against it.",
         "This is not a review of what you meant; it is what is on the "
         "timeline.", ""]
    L.append("  read: base track %s, %s kept span(s), %d check(s)"
             % (report.get("base_track"), report.get("spans"),
                report.get("checked", 0)))
    bad = report.get("bad") or []
    if not bad:
        L += ["", "  EVERY CHECK PASSED. The export is the harness's to "
                  "submit; you are done."]
        return L
    L += ["", "  %d FINDING(S). Fix these and say so; the export is withheld "
               "until they clear." % len(bad), ""]
    for f in bad:
        L.append("  [%s] %s" % (f["state"], f["why"]))
        L.append("        read: %s" % f["read"])
    return L
