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
        if _f(t_out) <= _acc + _len:
            return (MAPPED, _a + (_f(t_out) - _acc))
        _acc += _len
    # past the end of the kept material: report rather than clamp
    return (UNMAPPED, None)


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
    verdicts = {}
    for _v in (led.get("beat_verdicts") or []):
        verdicts.setdefault(_v.get("beat"), []).append(_v)
    _keep = led.get("keep_spans") or []
    out = []

    out.append("PLACEMENT JUDGMENT SHEET")
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
    out.append("")

    for _n, p in enumerate(placements, 1):
        _t = p.get("t_start")
        # OUTPUT time -> SOURCE time before any containment test. Beats live on
        # the source clock and placements on the output clock; comparing them
        # directly is only correct when nothing was cut.
        _mstate, _src_t = output_to_source(_keep, _t)
        _b = None
        if _mstate == MAPPED:
            for b in beats:
                if _f(b.get("t_start")) <= _src_t <= _f(b.get("t_end")):
                    _b = b
                    break
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
        out.append("%2d. %-9s at %ss out%s   beat %s (%.2fs)%s"
                   % (_n, p.get("family") or p.get("type") or "?", _t,
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
              "matched pair, two blank verdict axes, and four distinct "
              "grounding states" % len(_refs))
        sys.exit(0)
    with open(sys.argv[1], encoding="utf-8") as fh:
        _r = json.load(fh)
    print("\n".join(sheet(_r, _refs, _prov)))
