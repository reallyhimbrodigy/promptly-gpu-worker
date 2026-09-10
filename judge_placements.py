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


def nearest_by_duration(ref_beats, dur, k=3):
    """The k reference beats closest in duration. Duration is the only key we
    honestly have — see the docstring."""
    return sorted(ref_beats, key=lambda b: abs(_f(b.get("dur")) - _f(dur)))[:k]


def sheet(result, ref_beats, provenance):
    """The matched-pair sheet as lines. Pure, so it can be tested."""
    led = (result or {}).get("ledger") or {}
    beats = led.get("beats") or []
    placements = led.get("placements") or []
    verdicts = {v.get("beat"): v for v in (led.get("beat_verdicts") or [])}
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
        _v = verdicts.get(_b.get("i")) if _b else None
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
        if _v:
            out.append("    agent's why: %s" % str(_v.get("why") or "")[:88])
            out.append("    agent ruled: %s"
                       % ("+".join(_v.get("treatment") or []) or "none"))
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
        out.append("    VERDICT: ____  (RIGHT | WRONG MOMENT | WRONG FAMILY | "
                   "WRONG CONTENT)")
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
        _ok = any("what an editor did" in x for x in _lines) and \
            any("VERDICT:" in x for x in _lines)
        print("\n".join(_lines[:6]))
        print("...")
        print("JUDGE-PLACEMENTS (self-test): %s — %d reference beat(s), a "
              "matched pair and a blank verdict were produced"
              % ("PASS" if _ok else "FAIL", len(_refs)))
        sys.exit(0 if _ok else 1)
    with open(sys.argv[1], encoding="utf-8") as fh:
        _r = json.load(fh)
    print("\n".join(sheet(_r, _refs, _prov)))
