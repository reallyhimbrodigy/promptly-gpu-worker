#!/usr/bin/env python3
"""The five minimal briefs, judged by the SHIPPED fidelity rules.

NOT A ROUND. No model is called and no video is rendered: this drives
`spec_fidelity` and `reedit_delta` — the same functions the pipeline calls, not
copies — with the spec and placements each brief would produce, and prints what
fidelity would say. It answers "does the standard give the right verdict on a
minimal brief", which is the half that does not need a round. The other half —
does the AGENT produce that spec and those placements — needs Builder-1's round
and is not claimed here.

Run it again against a real round by passing a ledger path; the same rules run.
"""
import json, sys, importlib.util
import modal_stub                                            # noqa: F401

_spec = importlib.util.spec_from_file_location("A", "agentic_editor_app.py")
A = importlib.util.module_from_spec(_spec); sys.modules["A"] = A
_spec.loader.exec_module(A)


def P(*fams, beat=0):
    return [{"family": f, "beat": beat + i} for i, f in enumerate(fams)]


def spec(mode, families, targets=None):
    return {"mode": mode, "families": list(families), "targets": targets or {}}


ROWS = []


def main_case(label, brief, sp, placements, cut_made=False, captions_made=False,
              expect=None):
    st, missing, unasked, why = A.spec_fidelity(
        sp, placements, cut_made=cut_made, captions_made=captions_made)
    ROWS.append(("MAIN", label, brief, st, expect, why))


def reedit_case(label, brief, sp, prior, current, placements,
                cut_made=False, captions_made=False, expect=None,
                prior_cap=None, now_cap=("ABSENT", None)):
    rd_state, rd_beats, rd_fams = A.reedit_delta(prior, current)
    # BEAT **AND** FAMILY — mirrors the shipped call site.
    pl = [p for p in placements
          if p.get("beat") in set(rd_beats)
          and str(p.get("family") or "").lower() in set(rd_fams)]
    # CAPTIONS GET THEIR OWN SIGNAL — the beat delta is blind to them.
    cc_state, cc_changed, cc_why = A.captions_changed(
        prior_cap, now_cap[0], now_cap[1])
    caps = captions_made
    if cc_state == "MEASURED":
        caps = caps and cc_changed
    elif cc_state == "REMOVED":
        caps = False
    st, missing, unasked, why = A.spec_fidelity(
        sp, pl,
        cut_made=cut_made and "cut" in rd_fams,
        captions_made=caps)
    ROWS.append(("RE-EDIT", label, brief,
                 "%s  (delta %s: %d beat(s) %s; captions %s)"
                 % (st, rd_state, len(rd_beats), rd_fams or "[]",
                    cc_state + ("/changed" if cc_changed else "")),
                 expect, why))


# ── THE MAIN PATH ───────────────────────────────────────────────────────────
main_case("1", "just add captions",
          spec("targeted_change", ["caption"]),
          P(), captions_made=True, expect="FAITHFUL")
main_case("1b", "just add captions  (and it also placed four zooms)",
          spec("targeted_change", ["caption"]),
          P("zoom", "zoom", "zoom", "zoom"), captions_made=True,
          expect="OVERREACHED")
main_case("1c", "just add captions  (and no captions composited)",
          spec("targeted_change", ["caption"]),
          P(), captions_made=False, expect="SHORT")
main_case("2", "cut the part where I stumble",
          spec("targeted_change", ["cut"]),
          P(), cut_made=True, expect="FAITHFUL")
main_case("2b", "cut the part where I stumble  (kept the whole source)",
          spec("targeted_change", ["cut"]),
          P(), cut_made=False, expect="SHORT")

# ── THE RE-EDIT PATH. The prior plan already contains the whole edit, which is
#    exactly what made a no-op read as success before the delta narrowed it.
_PRIOR = [{"beat": 0, "treatment": ["text"], "text_content": "hi", "cut": "keep"},
          {"beat": 1, "treatment": ["zoom"], "zoom_arc": "build", "cut": "keep"},
          {"beat": 2, "treatment": ["none"], "cut": "keep"}]
_PL = [{"family": "caption", "beat": 0}, {"family": "zoom", "beat": 1},
       {"family": "sfx", "beat": 2}]

import copy
_CAPS_A = A.caption_signature("CleanCut", 15, [["hello", "world"], ["again"]])
_CAPS_BIG = A.caption_signature("TypewriterReveal", 30, [["hello", "world"], ["again"]])
_same = copy.deepcopy(_PRIOR)
# THE ONE THE RE-EDIT PATH CANNOT ANSWER, and it is named rather than guessed.
# Captions are BURNED, not ruled per beat: they leave no verdict and no manifest
# entry, so reedit_delta sees 0 changed beats whether the captions were restyled
# or nothing happened at all. Fidelity falls back to caption_composited, which
# is true in both cases, so this reads FAITHFUL. That is a KNOWN BLIND SPOT and
# the run prints RE-EDIT LIMIT saying so — the alternative, gating captions on
# the beat delta, made every genuine caption re-edit read SHORT.
reedit_case("3-noop", "make the captions bigger  (run changed NOTHING)",
            spec("targeted_change", ["caption"]), _PRIOR, _same, _PL,
            captions_made=True,
            prior_cap=_CAPS_A[1], now_cap=_CAPS_A,
            expect="SHORT  [the caption fingerprint is IDENTICAL, so the no-op is caught]")

_bigger = copy.deepcopy(_PRIOR); _bigger[0]["text_content"] = "HI (bigger)"
reedit_case("3", "make the captions bigger  (captions really restyled)",
            spec("targeted_change", ["caption"]), _PRIOR, _bigger, _PL,
            captions_made=True,
            prior_cap=_CAPS_A[1], now_cap=_CAPS_BIG,
            expect="FAITHFUL")

_regroup = A.caption_signature("CleanCut", 15, [["hello"], ["world", "again"]])
reedit_case("3b", "make the captions bigger  (same style, words REGROUPED)",
            spec("targeted_change", ["caption"]), _PRIOR, _same, _PL,
            captions_made=True,
            prior_cap=_CAPS_A[1], now_cap=_regroup,
            expect="FAITHFUL")

reedit_case("3c", "make the captions bigger  (prior plan predates the fingerprint)",
            spec("targeted_change", ["caption"]), _PRIOR, _same, _PL,
            captions_made=True,
            prior_cap=None, now_cap=_CAPS_A,
            expect="FAITHFUL  [ABSENT: unknowable this turn, and said so]")

_cutlast = copy.deepcopy(_PRIOR); _cutlast[2]["cut"] = "cut"
reedit_case("4", "remove the last clip",
            spec("targeted_change", ["cut"]), _PRIOR, _cutlast, _PL,
            cut_made=True, expect="FAITHFUL")

_sfx = copy.deepcopy(_PRIOR)
_sfx[2]["treatment"] = ["sfx"]; _sfx[2]["sfx_name"] = "whoosh"
reedit_case("5", "add a sound effect at the end",
            spec("targeted_change", ["sfx"]), _PRIOR, _sfx, _PL,
            expect="FAITHFUL")

_sfx_over = copy.deepcopy(_sfx)
_sfx_over[1]["zoom_arc"] = "payoff"          # touched a beat nobody asked about
reedit_case("5b", "add a sound effect at the end  (also re-ruled the zoom)",
            spec("targeted_change", ["sfx"]), _PRIOR, _sfx_over, _PL,
            expect="OVERREACHED")

_bad = [r for r in ROWS
        if r[4] and not str(r[3]).startswith(str(r[4]).split()[0])]
print("THE FIVE MINIMAL BRIEFS, judged by the shipped rules (NOT a round)\n")
_w = max(len(r[2]) for r in ROWS)
for path, label, brief, got, exp, why in ROWS:
    print("  [%-7s] %-3s %-*s -> %s" % (path, label, _w, brief, got))
    if exp:
        print("  %*s   expected: %s" % (12, "", exp))
    print("  %*s   %s" % (12, "", why[:140]))
    print()

if _bad:
    print("DISAGREEMENTS: %d" % len(_bad))
    for _p, _l, _b, _got, _exp, _w in _bad:
        print("  %s %s: expected %s, got %s" % (_p, _l, _exp, _got))
    sys.exit(1)
print("ALL %d CASES MATCH. The main path judges a minimal brief correctly in "
      "both directions. The re-edit path judges the DELTA, so a no-op reads "
      "SHORT rather than FAITHFUL — INCLUDING captions, which are not per-beat "
      "and now carry their own fingerprint (style + fps + page layout): an "
      "identical fingerprint is a caught no-op, a regrouping of the same style "
      "still counts as a change, and a prior plan that predates the "
      "fingerprint reads ABSENT and says so instead of guessing." % len(ROWS))
