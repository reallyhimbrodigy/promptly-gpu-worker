#!/usr/bin/env python3
"""Per-placement judgment sheet: what was placed, at what moment, against what
an editor did at a moment of that shape.

THE OBJECTIVE THIS SERVES. After round 51 the question is not whether a family
fired. It is whether the placement was RIGHT. Six rounds of counting found less
than one assessment did.

WHAT THIS DOES AND DOES NOT DO. It constructs the matched pair and nothing else.
It does NOT score, rank or verdict — taste is not automatable and a number here
would be the density-rubric mistake in a new costume. It puts our placement, at
its moment, beside the reference beats of that shape and the EDITOR'S OWN READ
of what they did there, so the eye is pointed at the right comparison.

    python3 judge_placements.py RESULT.json [--fixture NAME]

THE MATCHING KEY, and its limit stated. Reference beats carry `purpose`
(hook/evidence/claim/turn/payoff/close/breath), `dur`, `treat`, `card_text` and
`read`. OUR beats carry no purpose — the agent never names one, which is why
retrieval matches on DURATION alone at ruling time. So this matches on duration
too, and reports the reference beat's purpose as INFORMATION rather than as a
claim that our beat shares it. Position hints (first beat, last beat) are
labelled INFERRED where shown.

THREE VERDICTS FOR A WRONG PLACEMENT, because they are three different fixes:

    WRONG MOMENT    the family belongs in this edit, not on this beat
    WRONG FAMILY    something belonged here, but not this
    WRONG CONTENT   right family, right beat, and the words or the figure are
                    wrong

And a fourth that matters as much: RIGHT, said specifically. Knowing which
family already works is as useful as knowing which does not — the zooms were
found to be the one family working, and that was only visible because someone
said so.
"""
import json
import sys


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def load_reference(path="reference_index.json"):
    try:
        with open(path, encoding="utf-8") as fh:
            _d = json.load(fh)
        return _d.get("beats") or [], _d.get("provenance") or {}
    except (OSError, ValueError) as e:
        return [], {"error": str(e)[:120]}


MAPPED, UNMAPPED = "MAPPED", "UNMAPPED"


def output_to_source(keep_spans, t_out):
    """(state, source_t) — put an OUTPUT timestamp back on the SOURCE clock.

    THE DEFECT THIS CLOSES, found by building the sheet and reading it rather
    than by running it. Placement records carry `t_start` in OUTPUT seconds;
    beats carry t_start/t_end in SOURCE seconds. My first containment match
    compared one against the other — TWO CLOCKS, ONE COMPARISON — which is
    correct only on a run where nothing was cut. On any real edit it would have
    pointed the eye at the wrong beat and every verdict written from it would
    have been wrong about a moment it never saw.

    WITHOUT keep_spans IT REFUSES. A sheet that guesses the moment is worse than
    one that says it cannot place it: the whole output is a judgement about
    moments, so an unmapped placement must be visible as unmapped rather than
    silently attributed.
    """
    if not keep_spans:
        return (UNMAPPED, None)
    _acc = 0.0
    for _sp in keep_spans:
        try:
            _a, _b = float(_sp[0]), float(_sp[1])
        except (TypeError, ValueError, IndexError):
            return (UNMAPPED, None)
        _len = max(0.0, _b - _a)
        # HALF-OPEN. An output instant exactly at a span boundary is the START
        # of the next kept span, not the end of this one: the agent places at
        # beat starts, and a kept span's start IS a beat start. The first draft
        # used <= and sent r51 screen_recording's "CHAT HISTORY" (out 2.75) to
        # source 4.50 — the last instant of a beat ruled none — instead of 6.50,
        # the start of the sidebar-with-chat-history beat it was ruled for. The
        # third boundary convention in this file to hand a placement to the
        # wrong beat; the last span's end stays closed.
        if _f(t_out) < _acc + _len:
            return (MAPPED, _a + (_f(t_out) - _acc))
        _acc += _len
    _last = keep_spans[-1]
    try:
        if abs(_f(t_out) - _acc) < 1e-6:
            return (MAPPED, float(_last[1]))
    except (TypeError, ValueError, IndexError):
        pass
    # past the end of the kept material: report rather than clamp
    return (UNMAPPED, None)


def placement_moment(p, led):
    """(moment_out, source) — the OUTPUT-clock instant a placement is FOR.

    Producers since f5ffe09 write t_moment. Older ledgers carry only t_start,
    the render start, which sits attack_ms (cards), a pre-roll (zooms) or an
    attack (sfx) before the moment — so this joins the placement to its step
    in execute_plan and takes the moment the step recorded: a card item's
    anchor_s, a zoom step's beat_at_s. sfx and text steps record the moment
    as t already. A placement with neither falls back to t_start and SAYS SO.
    """
    if p.get("t_moment") is not None:
        return _f(p.get("t_moment")), "moment"
    _fam = str(p.get("family") or p.get("type") or "").lower()
    _t = _f(p.get("t_start"))
    _ep = (led or {}).get("execute_plan")
    _steps = _ep.get("steps") if isinstance(_ep, dict) else None
    for _s in (_steps or []):
        if _s.get("step") != _fam:
            continue
        if _fam == "card":
            for _it in (_s.get("items") or []):
                if abs(_f(_it.get("t")) - _t) < 1e-6 and _it.get("anchor_s") is not None:
                    return _f(_it.get("anchor_s")), "step anchor_s"
        elif _fam == "zoom":
            _st = _s.get("t")
            if isinstance(_st, list) and _st and abs(_f(_st[0]) - _t) < 1e-6 \
                    and _s.get("beat_at_s") is not None:
                return _f(_s.get("beat_at_s")), "step beat_at_s"
    return _t, "render start"


# ── DOES THE STATED REASON HOLD UP AGAINST THE FRAME? ───────────────────────
#
# A SECOND AXIS, and it is not the same question as whether the moment was
# right. A placement with a GOOD REASON THAT DOES NOT MATCH THE FOOTAGE is a
# different failure from one with no reason at all:
#
#   the first reads WELL. The log is editorially sensible, the why is the sort
#   of thing an editor would say, and it is about a moment that does not exist.
#   Nothing in the ledger can catch it — only the frame can.
#   the second is merely thin, and visible without watching anything.
#
# Confabulation and thoughtlessness need different fixes: one is a grounding
# problem (the agent asserting what it did not see), the other is a prompt
# problem (the agent not being asked to say why).
#
# WHAT THIS CLASSIFIES IS WHERE THE REASON CAN BE CHECKED, not whether it is
# true. Truth needs the frame. This says which placements REQUIRE the frame and
# which can be settled from the ledger, so the watching is spent where it is the
# only instrument that works.

_PICTURE_WORDS = (
    "shows", "showing", "shown", "holds", "holding", "points", "pointing",
    "gestures", "gesture", "on screen", "on-screen", "we see", "you see",
    "visible", "visually", "the shot", "the frame", "cuts to", "cut to",
    "behind", "background", "b-roll", "broll", "footage", "product",
    "close-up", "closeup", "zoom in on", "looking", "face", "hands",
)
_STOP = {"the", "a", "an", "and", "or", "but", "this", "that", "these", "those",
         "is", "it", "to", "of", "in", "on", "for", "with", "at", "as", "beat",
         "here", "so", "then", "we", "you", "i", "its", "it's", "their", "there"}

GROUND_SPEECH, GROUND_PICTURE, GROUND_NEITHER, GROUND_ABSENT = (
    "CITES SPEECH", "CLAIMS PICTURE", "NEITHER", "NO REASON")


def _words(text):
    return {w for w in "".join(
        c.lower() if (c.isalnum() or c == "'") else " " for c in str(text or "")
    ).split() if len(w) > 3 and w not in _STOP}


def resolve_beat(beats, src_t):
    """The beat a SOURCE-clock instant belongs to: half-open [t_start, t_end),
    the last beat closed at its end.

    WHY HALF-OPEN. 53 of 80 placements across rounds 51-52 sit EXACTLY on a
    boundary two beats share, because the agent places at the beat's t_start
    and the previous beat's t_end is the same number. The first draft of this
    sheet tested `t_start <= t <= t_end` and took the FIRST match — so two
    thirds of placements were judged against the PREVIOUS beat's vision and
    the previous beat's ruling, which is where most of "BUILT BUT NOT RULED"
    came from: the ruling naming the family was on the next beat, one number
    away. The why-vs-frame column was comparing the right why to the wrong
    frame. A closed interval and first-match-wins is a tie-break nobody chose.
    """
    if not beats:
        return None
    # SNAP. output_to_source returns _a + (t_out - _acc), and 8.16 through a
    # span starting at 2.88 came back 8.719999999999999 — 1e-15 below the beat
    # that starts at 8.72, so it resolved to the beat that ENDS there. Ledger
    # times carry 2-3 decimals; compare at that resolution.
    src_t = round(float(src_t), 3)
    for b in beats:
        if round(_f(b.get("t_start")), 3) <= src_t < round(_f(b.get("t_end")), 3):
            return b
    # No beat starts at or contains this instant. If a beat ENDS exactly here
    # — the last beat, or a beat followed by a gap — it owns the instant. The
    # first draft closed only the LAST beat and left 2 of 80 real placements
    # UNMATCHED at the end of a beat that had a gap after it.
    for b in beats:
        if abs(src_t - _f(b.get("t_end"))) < 1e-6:
            return b
    return None


RESOLVED_DECLARED = "DECLARED"
RESOLVED_INTERIOR = "INTERIOR"
RESOLVED_BOUNDARY = "BOUNDARY TIE-BREAK"
RESOLVED_FALLBACK = "MOMENT FALLBACK"
RESOLVED_SPAN_EDGE = "SPAN EDGE"
RESOLVED_UNMAPPED = "UNMAPPED"


def resolution_basis(p, beats, keep_spans):
    """(basis, detail) — HOW this placement reached the beat it is judged on.

    THE INSTRUMENT THIS FILE OWED AND DID NOT HAVE. Four conventions in this
    sheet each silently assigned placements to the wrong beat, and the counts
    they produced — BUILT BUT NOT RULED 14 and 19 — were reported onward as
    facts about the pipeline. They were facts about the tie-breaks.

    What would have caught it in one line: 44 of 47 of those rows sat EXACTLY
    on a convention's edge. A finding concentrated on the edge of a tie-break
    is a finding about the tie-break. So every count this sheet prints now
    carries how much of it rests on a convention rather than on an instant that
    falls unambiguously inside one beat.

    INTERIOR is the only basis that needs no convention to be right.
    """
    # DECLARED BEATS EVERY RECONSTRUCTION. The producer knows which beat a
    # placement is for; when it says so there is no convention in play at all.
    # Round 57 read 35 of 38 placements as BOUNDARY TIE-BREAK with nothing
    # ambiguous about any of them: a placement sits on a beat boundary BY
    # CONSTRUCTION, because its instant IS the beat's start. The warning was
    # correct about the reconstruction and wrong about the pipeline, which is
    # the same error one level up — so the fix is to stop reconstructing.
    if p.get("beat") is not None:
        return (RESOLVED_DECLARED, "the producer recorded the beat")
    _t, _tsrc = placement_moment(p, {})
    _mstate, _src_t = output_to_source(keep_spans, _t)
    if _mstate != MAPPED:
        return (RESOLVED_UNMAPPED, "no source instant")
    if _tsrc != "moment":
        return (RESOLVED_FALLBACK,
                "no t_moment: judged on the RENDER start, which leads the "
                "moment by the family's attack or pre-roll")
    _acc = 0.0
    for _sp in (keep_spans or []):
        try:
            _acc += max(0.0, float(_sp[1]) - float(_sp[0]))
        except (TypeError, ValueError, IndexError):
            break
        if abs(_f(_t) - _acc) < 1e-6:
            return (RESOLVED_SPAN_EDGE,
                    "the output instant is exactly a kept-span boundary; which "
                    "span owns it is a convention")
    _st = round(float(_src_t), 3)
    for _b in (beats or []):
        if abs(_st - round(_f(_b.get("t_start")), 3)) < 1e-6 \
                or abs(_st - round(_f(_b.get("t_end")), 3)) < 1e-6:
            return (RESOLVED_BOUNDARY,
                    "the source instant is exactly a beat boundary; which beat "
                    "owns it is a convention")
    return (RESOLVED_INTERIOR, "strictly inside one beat")


def reason_grounding(why, beat_text):
    """(state, detail) — WHERE the stated reason could be checked.

    NOT whether it is true. A CLAIMS PICTURE reason may be perfectly accurate;
    it simply cannot be settled without watching, which is the point — it tells
    the eye where to go.
    """
    _w = str(why or "").strip()
    if not _w:
        return (GROUND_ABSENT, "no why recorded")
    _low = _w.lower()
    _pic = [p for p in _PICTURE_WORDS if p in _low]
    if _pic:
        return (GROUND_PICTURE,
                "asserts about the picture (%s) — ONLY THE FRAME CAN CONFIRM "
                "IT, and a confident reason about footage that is not there is "
                "the failure this column exists for" % ", ".join(_pic[:3]))
    _shared = _words(_w) & _words(beat_text)
    if _shared:
        return (GROUND_SPEECH,
                "cites what was said (%s) — checkable against the transcript "
                "without watching" % ", ".join(sorted(_shared)[:4]))
    return (GROUND_NEITHER,
            "asserts nothing checkable about this moment — neither the words "
            "nor the picture. Thin rather than wrong, and visible without "
            "watching anything.")


def nearest_by_duration(ref_beats, dur, k=3):
    """The k reference beats closest in duration. Duration is the only key we
    honestly have — see the docstring."""
    return sorted(ref_beats, key=lambda b: abs(_f(b.get("dur")) - _f(dur)))[:k]


def sheet(result, ref_beats, provenance):
    """The matched-pair sheet as lines. Pure, so it can be tested."""
    led = (result or {}).get("ledger") or {}
    beats = led.get("beats") or []
    placements = led.get("placements") or []
    # ALL RULINGS PER BEAT, NOT THE LAST. Beats get ruled more than once — a
    # second pass re-rules some — and a dict keyed by beat index SILENTLY KEEPS
    # THE LAST. car_short has 6 verdicts for 3 beats and its beat 1 went
    # `zoom+cutaway+sfx` then `zoom+sfx`: the re-rule DROPPED cutaway. Keying by
    # beat would have shown the second and hidden that the first existed, and
    # every "agent's why" in this sheet would have been the wrong ruling with
    # nothing to indicate it. (Flagged by Builder-1 before I ran it.)
    # THE RULINGS THE BUILD USED, when the ledger carries them. beat_verdicts is
    # mutated after the fact (the half-ruling stripper rewrites treatment in
    # place; later passes replace entries), so on round 54 talking_head the
    # recorded beat 0 read ['cutaway'] while the overlay at 0.0s was built from
    # a ruling that named text — and this sheet called the agent's own
    # placement BUILT BUT NOT RULED. executed_verdicts is the frozen copy
    # execute_plan built from; a ledger without it falls back and SAYS SO.
    _exec_v = led.get("executed_verdicts")
    _vsrc = "EXECUTED" if isinstance(_exec_v, list) and _exec_v else "RECORDED"
    verdicts = {}
    for _v in (_exec_v if _vsrc == "EXECUTED" else (led.get("beat_verdicts") or [])):
        verdicts.setdefault(_v.get("beat"), []).append(_v)
    _keep = led.get("keep_spans") or []
    out = []

    out.append("PLACEMENT JUDGMENT SHEET")
    out.append("  rulings read: %s (%d)%s"
               % (_vsrc, sum(len(x) for x in verdicts.values()),
                  "" if _vsrc == "EXECUTED" else
                  " — this ledger predates executed_verdicts; treatments may "
                  "have been rewritten after the build"))
    out.append("  reference corpus: %s by %s, n=%s, %s"
               % (provenance.get("kind") or "KIND UNSTATED",
                  provenance.get("annotator") or "ANNOTATOR UNSTATED",
                  provenance.get("n_videos", "?"), provenance.get("annotated") or "?"))
    out.append("  MODEL-ANNOTATED means these reads are one model's judgement of "
               "ten videos, not counts.")
    out.append("")
    if not placements:
        out.append("  NO PLACEMENTS IN THIS RESULT — nothing to judge. That is a "
                   "different finding from a wrong placement and it is not this "
                   "sheet's question.")
        return out
    out.append("  %d placement(s) over %d beat(s)" % (len(placements), len(beats)))
    _bases = [resolution_basis(p, beats, _keep) for p in placements]
    _conv = [b for b, _d in _bases
             if b not in (RESOLVED_INTERIOR, RESOLVED_DECLARED)]
    out.append("  resolution: %d of %d placement(s) rest on a CONVENTION, not "
               "on an instant strictly inside one beat  [%s]"
               % (len(_conv), len(placements),
                  "  ".join("%s %d" % (_k, _conv.count(_k))
                            for _k in (RESOLVED_BOUNDARY, RESOLVED_FALLBACK,
                                       RESOLVED_SPAN_EDGE, RESOLVED_UNMAPPED)
                            if _conv.count(_k))
                  or "none"))
    if placements and len(_conv) > len(placements) / 2:
        out.append("  !! MORE THAN HALF OF THIS SHEET RESTS ON TIE-BREAKS. Any "
                   "count below is a claim about the conventions before it is a "
                   "claim about the pipeline. Do not pass one on as the other.")
    out.append("")

    for _n, p in enumerate(placements, 1):
        # THE MOMENT, NOT THE RENDER START. A card renders attack_ms before the
        # moment it is for, so t_start sits 0.08s before the beat it was ruled
        # on — resolving on it put 4 of 5 card placements one beat early and
        # called them BUILT BUT NOT RULED. t_moment is written by the producer;
        # a record without it (older ledgers) falls back to t_start and the
        # sheet says which it used.
        _t, _tsrc = placement_moment(p, led)
        # OUTPUT time -> SOURCE time before any containment test. Beats live on
        # the source clock and placements on the output clock; comparing them
        # directly is only correct when nothing was cut.
        _mstate, _src_t = output_to_source(_keep, _t)
        if p.get("beat") is not None:
            _b = next((x for x in beats if x.get("i") == p.get("beat")), None)
        else:
            _b = resolve_beat(beats, _src_t) if _mstate == MAPPED else None
        _dur = (_f(_b.get("t_end")) - _f(_b.get("t_start"))) if _b else 0.0
        _all_v = verdicts.get(_b.get("i")) if _b else None
        # The ruling that PRODUCED this placement is the one whose treatment
        # names its family — not simply the newest.
        _fam = str(p.get("family") or p.get("type") or "").lower()
        _v = None
        if _all_v:
            _match = [x for x in _all_v
                      if _fam in [str(t).lower() for t in (x.get("treatment") or [])]]
            _v = _match[-1] if _match else _all_v[-1]
            _unruled = not _match
        _pos = ""
        if _b and beats:
            if _b.get("i") == beats[0].get("i"):
                _pos = "  [INFERRED: first beat — a hook position]"
            elif _b.get("i") == beats[-1].get("i"):
                _pos = "  [INFERRED: last beat — a close position]"

        out.append("─" * 74)
        _basis, _bwhy = resolution_basis(p, beats, _keep)
        out.append("%2d. %-9s at %ss out (%s)%s   beat %s (%.2fs)%s"
                   % (_n, p.get("family") or p.get("type") or "?", _t, _tsrc,
                      (" = %.2fs src" % _src_t) if _mstate == MAPPED else "",
                      _b.get("i") if _b else "UNMATCHED", _dur, _pos))
        out.append("    placed: %s" % (str(p.get("content") or "")[:88] or "(no content recorded)"))
        if _b:
            out.append("    beat text: %s" % str(_b.get("text") or "")[:88])
        if _v and locals().get("_unruled"):
            # BUILT BUT NOT RULED — the inverse of ruled_but_not_built, and it
            # has never had a name. A placement exists whose beat carries NO
            # ruling naming its family, so the `why` shown below is the agent's
            # reasoning about a DIFFERENT decision. Judging the placement
            # against it would be judging the wrong sentence.
            out.append("    !! BUILT BUT NOT RULED: no verdict on this beat "
                       "names '%s'. The why below belongs to another ruling."
                       % _fam)
            out.append("       resolved %s — %s%s"
                       % (_basis, _bwhy,
                          "" if _basis == RESOLVED_INTERIOR else
                          "  <-- THIS ROW IS A CONVENTION'S OUTPUT, not yet a "
                          "finding about the pipeline"))
        if _v:
            out.append("    agent's why: %s" % str(_v.get("why") or "")[:88])
            out.append("    agent ruled: %s%s"
                       % ("+".join(_v.get("treatment") or []) or "none",
                          ("   purpose=%s" % _v.get("purpose"))
                          if _v.get("purpose") else ""))
            _gs, _gd = reason_grounding(_v.get("why"),
                                        (_b or {}).get("text"))
            out.append("    reason is %s — %s" % (_gs, _gd))
            if _all_v and len(_all_v) > 1:
                _trs = ["+".join(x.get("treatment") or []) or "none"
                        for x in _all_v]
                out.append("    !! this beat was ruled %d times: %s"
                           % (len(_all_v), " THEN ".join(_trs)))
                if len(set(_trs)) > 1:
                    out.append("       the re-rule CHANGED the treatment — the "
                               "verdict below is about the ruling that names "
                               "this family, and the other ruling is a "
                               "different decision the agent also made")
        else:
            out.append("    NO VERDICT FOUND for this beat — the placement "
                       "exists and the ruling behind it does not, which is a "
                       "finding about the manifest rather than about taste")
        if _mstate == UNMAPPED:
            out.append("    !! UNMAPPED: no keep_spans in this result, so the "
                       "OUTPUT timestamp cannot be put back on the SOURCE clock. "
                       "This placement is NOT judgeable here — matching it to a "
                       "beat anyway would point at a moment it never occupied.")
        elif not _b:
            out.append("    !! this placement maps to %.2fs source and no beat "
                       "contains it — a finding about the manifest, not about "
                       "taste" % _src_t)
        out.append("")
        out.append("    what an editor did at a moment of this LENGTH:")
        for _e in nearest_by_duration(ref_beats, _dur):
            out.append("      %-8s %4.2fs  %-26s %s"
                       % (_e.get("purpose") or "?", _f(_e.get("dur")),
                          "+".join(_e.get("treat") or []),
                          str(_e.get("read") or "")[:120]))
            if _e.get("card_text"):
                out.append("               words: %s"
                           % str(_e.get("card_text"))[:90])
        out.append("")
        out.append("    PLACEMENT: ____  (RIGHT | WRONG MOMENT | WRONG FAMILY "
                   "| WRONG CONTENT)")
        out.append("    REASON:    ____  (HOLDS | UNGROUNDED | NO REASON)")
        out.append("               HOLDS      = the why matches what is in the "
                   "frame")
        out.append("               UNGROUNDED = the why is sensible and the "
                   "footage does not support it")
        out.append("               NO REASON  = nothing checkable was asserted")
        out.append("    because: ")
        out.append("")
    return out


if __name__ == "__main__":
    _refs, _prov = load_reference()
    if not _refs:
        print("NO REFERENCE CORPUS — the sheet has nothing to compare against. "
              "%s" % _prov.get("error", ""))
        sys.exit(2)
    if len(sys.argv) < 2:
        # SELF-TEST rather than usage-and-exit-2: the suite runs every file with
        # no arguments, and a harness that is permanently red stops being read.
        _demo = {"ledger": {
            "beats": [{"i": 0, "t_start": 0.0, "t_end": 2.9, "text": "ten times a day"},
                      {"i": 1, "t_start": 2.9, "t_end": 9.0, "text": "and it never worked"}],
            "placements": [{"family": "card", "t_start": 0.4, "content": "10"}],
            "beat_verdicts": [{"beat": 0, "treatment": ["card"], "why": "a figure"}]}}
        _lines = sheet(_demo, _refs, _prov)
        _bad = []

        # BEAT RESOLUTION ON THE BOUNDARY. 53 of 80 real placements (rounds
        # 51-52) sit exactly on a boundary two beats share; the rule that says
        # which beat owns it decides which why and which FRAME the placement is
        # judged against. Closed-interval-first-match judged two thirds of them
        # against the previous beat.
        _rb = [{"i": 0, "t_start": 0.0, "t_end": 2.0},
               {"i": 1, "t_start": 2.0, "t_end": 4.0},
               {"i": 2, "t_start": 5.0, "t_end": 6.0}]
        for _t, _want, _lbl in (
                (2.0, 1, "a shared boundary belongs to the beat that STARTS there"),
                (6.0, 2, "the last beat is closed at its end"),
                (4.0, 1, "an end with a gap after it belongs to the beat that ENDS there"),
                (3.0, 1, "an interior instant belongs to the beat containing it"),
                (1.9999999999999998, 1, "a float 1e-16 below a beat start is that beat, not the one ending there"),
                (4.5, None, "an instant inside a gap belongs to no beat")):
            _got = resolve_beat(_rb, _t)
            _gi = _got.get("i") if _got else None
            if _gi != _want:
                _bad.append("resolve_beat(%.1f) -> %s, expected %s: %s"
                            % (_t, _gi, _want, _lbl))

        # BUILT BUT NOT RULED fires on a placement whose beat carries no ruling
        # naming its family, and stays silent on the ruled one.
        # keep_spans is REQUIRED here: without it every placement is UNMAPPED,
        # no beat resolves, and this leg reads 0 for a reason that has nothing
        # to do with the rule it tests — the first run of it did exactly that.
        _demo2 = {"ledger": {
            "keep_spans": [[0.0, 9.0]],
            "beats": _demo["ledger"]["beats"],
            "placements": [{"family": "card", "t_start": 0.4, "content": "10"},
                           {"family": "zoom", "t_start": 0.5}],
            "beat_verdicts": _demo["ledger"]["beat_verdicts"]}}
        _n_bnr = sum("BUILT BUT NOT RULED" in x for x in sheet(_demo2, _refs, _prov))
        # EXECUTED RULINGS WIN. The recorded ruling says cutaway; the executed
        # copy says text; the text overlay on that beat is RULED.
        _demo4 = {"ledger": {
            "keep_spans": [[0.0, 9.0]],
            "beats": _demo["ledger"]["beats"],
            "placements": [{"family": "text", "t_start": 0.0, "content": "HOOK"}],
            "beat_verdicts": [{"beat": 0, "treatment": ["cutaway"], "why": "recorded"}],
            "executed_verdicts": [{"beat": 0, "treatment": ["text"], "why": "executed"}]}}
        _l4 = sheet(_demo4, _refs, _prov)
        if any("BUILT BUT NOT RULED" in x for x in _l4) or not any(
                "rulings read: EXECUTED" in x for x in _l4):
            _bad.append("executed_verdicts must be read in preference to the "
                        "recorded beat_verdicts, and the sheet must say so")
        # A card ruled on beat 1 renders 0.08s before beat 1 starts (attack
        # lead). Resolving on t_moment keeps it on beat 1 and ruled; resolving
        # on t_start would put it on beat 0 and call it BUILT BUT NOT RULED.
        _demo3 = {"ledger": {
            "keep_spans": [[0.0, 9.0]],
            "beats": _demo["ledger"]["beats"],
            "placements": [{"family": "card", "t_start": 2.82, "t_moment": 2.9,
                            "content": "10"}],
            "beat_verdicts": [{"beat": 1, "treatment": ["card"], "why": "a figure"}]}}
        _l3 = sheet(_demo3, _refs, _prov)
        if any("BUILT BUT NOT RULED" in x for x in _l3) or not any(
                "beat 1 " in x and "(moment)" in x for x in _l3):
            _bad.append("a card with t_moment on beat 1 and t_start 0.08s before "
                        "it must resolve to beat 1 via the moment, ruled")
        if _n_bnr != 1:
            _bad.append("BUILT BUT NOT RULED fired %d time(s) on one unruled + "
                        "one ruled placement; expected exactly 1" % _n_bnr)

        # OUTPUT -> SOURCE through a cut, and UNMAPPED past the kept material.
        _o2s = [(output_to_source([[0.0, 1.0], [3.0, 4.0]], 1.5), (MAPPED, 3.5),
                 "an output instant inside the second kept span maps into it"),
                (output_to_source([[0.0, 1.0], [3.0, 4.0]], 2.5), None,
                 "an output instant past the kept total is UNMAPPED"),
                # THE BOUNDARY: out 1.0 is the START of the second span (3.0),
                # not the end of the first (1.0).
                (output_to_source([[0.0, 1.0], [3.0, 4.0]], 1.0), (MAPPED, 3.0),
                 "an output instant on a span boundary is the START of the next span"),
                (output_to_source([[0.0, 1.0], [3.0, 4.0]], 2.0), (MAPPED, 4.0),
                 "the last span's end stays closed")]
        # THE RESOLUTION BASIS. INTERIOR is the only one that needs no
        # convention; every other basis is a tie-break this sheet chose.
        _rb2 = [{"i": 0, "t_start": 0.0, "t_end": 2.0},
                {"i": 1, "t_start": 2.0, "t_end": 4.0}]
        _ks2 = [[0.0, 2.0], [3.0, 5.0]]
        for _p, _want, _lbl in (
                ({"family": "text", "t_start": 1.0, "t_moment": 1.0},
                 RESOLVED_INTERIOR, "strictly inside one beat needs no convention"),
                ({"family": "text", "t_start": 0.5, "t_moment": 0.5},
                 RESOLVED_INTERIOR, "another interior instant"),
                ({"family": "card", "t_start": 1.9},
                 RESOLVED_FALLBACK, "no t_moment is a fallback, not an interior hit"),
                ({"family": "text", "t_start": 2.0, "t_moment": 2.0},
                 RESOLVED_SPAN_EDGE, "an output instant on a kept-span boundary"),
                ({"family": "text", "t_start": 1.0, "t_moment": 1.0,
                  "_ks": [[0.0, 9.0]]},
                 RESOLVED_INTERIOR, "unchanged when the span does not bite"),
                ({"family": "text", "t_start": 9.0, "t_moment": 9.0},
                 RESOLVED_UNMAPPED, "past the kept material")):
            _got = resolution_basis(_p, _rb2, _p.get("_ks") or _ks2)[0]
            if _got != _want:
                _bad.append("resolution_basis: %s -> %s, expected %s"
                            % (_lbl, _got, _want))
        # a BEAT boundary, with the span out of the way
        if resolution_basis({"family": "text", "t_start": 2.0, "t_moment": 2.0},
                            _rb2, [[0.0, 9.0]])[0] != RESOLVED_BOUNDARY:
            _bad.append("resolution_basis: an instant exactly on a shared beat "
                        "boundary must report BOUNDARY TIE-BREAK")
        # the disclosure reaches the sheet, and the loud line fires
        _demo5 = {"ledger": {
            "keep_spans": [[0.0, 9.0]],
            "beats": _rb2,
            "placements": [{"family": "text", "t_start": 2.0, "t_moment": 2.0},
                           {"family": "card", "t_start": 1.9}],
            "beat_verdicts": [{"beat": 1, "treatment": ["text"], "why": "x"}]}}
        _l5 = sheet(_demo5, _refs, _prov)
        if not any("rest on a CONVENTION" in x for x in _l5):
            _bad.append("the sheet does not disclose how many placements rest "
                        "on a convention")
        if not any("MORE THAN HALF OF THIS SHEET RESTS ON TIE-BREAKS" in x
                   for x in _l5):
            _bad.append("a sheet that is mostly tie-breaks does not say so "
                        "loudly — which is how its counts get passed on as "
                        "facts about the pipeline")

        # A DECLARED BEAT IS NOT A CONVENTION.
        if resolution_basis({"family": "text", "t_start": 2.0, "t_moment": 2.0,
                             "beat": 1}, _rb2, _ks2)[0] != RESOLVED_DECLARED:
            _bad.append("a placement that RECORDS its beat must resolve "
                        "DECLARED — reconstructing a fact the producer already "
                        "stated is how 35 of 38 rows read as tie-breaks")
        _demo6 = {"ledger": {
            "keep_spans": [[0.0, 9.0]], "beats": _demo["ledger"]["beats"],
            "placements": [{"family": "card", "t_start": 2.9, "t_moment": 2.9,
                            "beat": 1, "content": "10"}],
            "beat_verdicts": [{"beat": 1, "treatment": ["card"], "why": "x"}]}}
        _l6 = sheet(_demo6, _refs, _prov)
        if any("MORE THAN HALF" in x for x in _l6):
            _bad.append("a sheet of DECLARED placements must not warn about "
                        "tie-breaks — there are none")
        if any("BUILT BUT NOT RULED" in x for x in _l6):
            _bad.append("a declared beat must be used to find the ruling, not "
                        "only to report the basis")

        # THE MOMENT FROM THE STEP, for ledgers that predate t_moment.
        _led_old = {"execute_plan": {"steps": [
            {"step": "card", "items": [{"t": 1.92, "anchor_s": 2.0, "content": "10"}]},
            {"step": "zoom", "t": [4.167, 4.867], "beat_at_s": 4.5}]}}
        for _p, _want, _lbl in (
                ({"family": "card", "t_start": 1.92}, (2.0, "step anchor_s"),
                 "a card without t_moment takes its step's anchor_s"),
                ({"family": "zoom", "t_start": 4.167}, (4.5, "step beat_at_s"),
                 "a zoom without t_moment takes its step's beat_at_s"),
                ({"family": "text", "t_start": 3.25}, (3.25, "render start"),
                 "a text placement with no step moment falls back and says so"),
                ({"family": "card", "t_start": 1.92, "t_moment": 2.0}, (2.0, "moment"),
                 "t_moment wins when present")):
            _got = placement_moment(_p, _led_old)
            if (round(_got[0], 6), _got[1]) != _want:
                _bad.append("placement_moment: %s (got %r, want %r)" % (_lbl, _got, _want))
        for _got, _want, _lbl in _o2s:
            if _want is None:
                if _got[0] == MAPPED:
                    _bad.append("output_to_source: %s (got %r)" % (_lbl, _got))
            elif (_got[0], round(_got[1], 6)) != _want:
                _bad.append("output_to_source: %s (got %r)" % (_lbl, _got))
        if not any("what an editor did" in x for x in _lines):
            _bad.append("no matched pair produced")
        for _need in ("PLACEMENT: ____", "REASON:    ____"):
            if not any(_need in x for x in _lines):
                _bad.append("missing blank verdict line: %s" % _need)

        # THE REASON AXIS, driven through all four states. It classifies WHERE a
        # reason can be checked, never whether it is true — truth needs the
        # frame, and saying otherwise would be the density-rubric mistake again.
        _cases = [
            ("the speaker holds up the product here", "we tried it for a week",
             GROUND_PICTURE),
            # MY FIRST CASE HERE WAS WRONG, NOT THE FUNCTION. I wrote "the
            # figure is the point of this line" against "we lose ten hours a
            # week" and expected CITES SPEECH — but it shares no content word
            # with the beat, so NEITHER was the correct answer. A reason that
            # cites speech ECHOES THE WORDS; one that talks about the beat in
            # the abstract does not, and the distinction is the whole point.
            ("ten hours a week is the number worth stamping",
             "we lose ten hours a week to this", GROUND_SPEECH),
            ("felt right", "we lose ten hours a week", GROUND_NEITHER),
            ("", "anything", GROUND_ABSENT),
        ]
        for _why, _txt, _want in _cases:
            _got = reason_grounding(_why, _txt)[0]
            if _got != _want:
                _bad.append("reason_grounding(%r) -> %s, expected %s"
                            % (_why[:28], _got, _want))
        _states = {reason_grounding(w, t)[0] for w, t, _x in _cases}
        if len(_states) != 4:
            _bad.append("the four grounding states are not distinct: %s"
                        % sorted(_states))
        print("\n".join(_lines[:6]))
        print("...")
        for _why, _txt, _want in _cases:
            print("  %-38r -> %s" % (_why[:36], reason_grounding(_why, _txt)[0]))
        print()
        if _bad:
            print("JUDGE-PLACEMENTS (self-test): FAIL")
            for _m in _bad:
                print("  - " + _m)
            sys.exit(1)
        print("JUDGE-PLACEMENTS (self-test): PASS — %d reference beat(s), a "
              "matched pair, two blank verdict axes, four distinct grounding "
              "states, boundary resolution (5 legs), BUILT BUT NOT RULED "
              "fires once, output->source through a cut, and every count "
              "discloses how much of it rests on a tie-break" % len(_refs))
        sys.exit(0)
    with open(sys.argv[1], encoding="utf-8") as fh:
        _r = json.load(fh)
    print("\n".join(sheet(_r, _refs, _prov)))
