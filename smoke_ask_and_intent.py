#!/usr/bin/env python3
"""Nothing is placed without a ruling, and an ambiguous request ASKS.

THREE PROPERTIES, one theme: every pixel this editor adds traces to a decision
the agent made on the record, and when the request does not determine the
decision the run stops instead of guessing.

1. THE SECOND CHANNEL IS CLOSED. `build_overlays` treated caller-supplied items
   as additive — "a hand-authored overlay that is not a beat ruling still
   lands" — reachable through the repair tool. That is placing without intent.
   An item now lands only if its instant falls inside a beat ruled `text`;
   otherwise REFUSED, printed, and fail()ed.

2. THE RECORD FOLLOWS THE BUILD. `beat_verdicts` is MUTATED after the fact:
   the half-ruling stripper rewrites `treatment` in place, and a later ruling
   pass replaces entries. Round 54 talking_head beat 0 ended up reading
   ['cutaway'] while the overlay at 0.0s had been built from a ruling that
   named text — so the judgment sheet called the agent's own placement BUILT
   BUT NOT RULED. `executed_verdicts` is the frozen copy execute_plan built
   from.

3. AN AMBIGUOUS REQUEST ASKS (K5). "Cut the part where I stumble" on a source
   with three stumbles is two materially different edits. `set_spec
   .clarification` stops the run — no plan, no render, no charge — and
   `result_agentic` returns NEEDS_INPUT, a fourth state beside DONE / RUNNING /
   FAILED. Karpathy §1 "if something is unclear, stop, name what is confusing,
   ask"; Zac's ruling for ambiguous re-edit instructions, 2026-09-10.

RED-proven by red_proof_ask_and_intent.py.
"""
import ast
import pathlib
import sys

import modal_stub                                              # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                 # noqa: E402

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


def _fn(name):
    return next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == name), None)


def _has_const(node, val):
    return any(isinstance(x, ast.Constant) and x.value == val
               for x in ast.walk(node))


# ── 1. NO PLACEMENT WITHOUT A RULING ────────────────────────────────────────
_bo = _fn("build_overlays")
check("build_overlays exists and is drivable", _bo is not None)
# THE GUARD, NOT THE NAME. The first draft asserted the name _unruled_refused
# appeared somewhere in build_overlays — and it appears in its own
# initialisation, so DELETING THE WHOLE GUARD left the smoke green. A presence
# check cannot see control flow; this reads the If that does the refusing.
_guard = [n for n in ast.walk(_bo) if isinstance(n, ast.If)
          and any(isinstance(x, ast.Name) and x.id == "_text_windows"
                  for x in ast.walk(n.test))
          and any(isinstance(x, ast.Name) and x.id == "_unruled_refused"
                  for x in ast.walk(n))
          and any(isinstance(x, ast.Continue) for x in ast.walk(n))] if _bo else []
check("a caller-supplied overlay is refused when no beat ruled text at its instant",
      bool(_guard),
      "an If testing the ruled-text windows, recording the refusal, and "
      "skipping the item — all three, or the item still lands")
# The candidate beats must be FILTERED BY THE RULING. The first draft of this
# leg looked for "text" and _text_windows in ONE assignment; they are two
# (_text_beats filters, _text_windows maps to output time), so it read FAIL on
# correct code — a check measuring the layout of the source, again.
_tb = [n for n in ast.walk(_bo) if isinstance(n, ast.Assign)
       and any(getattr(t, "id", "") == "_text_beats" for t in n.targets)] if _bo else []
_tw = [n for n in ast.walk(_bo) if isinstance(n, ast.Assign)
       and any(getattr(t, "id", "") == "_text_windows" for t in n.targets)] if _bo else []
check("the refusal is built against windows of beats RULED text, not all beats",
      bool(_tb) and bool(_tw)
      and any(_has_const(a_, "text") and _has_const(a_, "treatment") for a_ in _tb),
      "the candidate set must be filtered on a treatment naming text")
check("the old 'additive' passthrough sentence is gone from the source",
      "still lands." not in src,
      "the comment that licensed the second channel")
_prints = [n for n in ast.walk(_bo) if isinstance(n, ast.Call)
           and getattr(n.func, "id", "") == "print"
           and "OVERLAY REFUSED" in ast.unparse(n)] if _bo else []
check("the refusal is PRINTED in the same commit that adds it", bool(_prints))
_fails_c = [n for n in ast.walk(_bo) if isinstance(n, ast.Call)
            and getattr(n.func, "id", "") == "fail"
            and "overlay_unruled_refused" in ast.unparse(n)] if _bo else []
check("and fail()s loudly, so it is a defect and not a taste call", bool(_fails_c))

# ── 2. THE RECORD FOLLOWS THE BUILD ─────────────────────────────────────────
_ev = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
       and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
               and t.slice.value == "executed_verdicts" for t in n.targets)]
check("execute_plan freezes the rulings it built from as executed_verdicts",
      bool(_ev))
check("it is a DEEP COPY — beat_verdicts is mutated in place downstream",
      any("deepcopy" in ast.unparse(a_.value) for a_ in _ev),
      "a shallow reference would be rewritten by the half-ruling stripper")
# A LITERAL SURVIVES ITS OWN print() BEING RENAMED. Read the call.
check("and the count is printed",
      any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"
          and any(isinstance(x, ast.Constant) and isinstance(x.value, str)
                  and "EXECUTED FROM" in x.value for x in ast.walk(n))
          for n in ast.walk(tree)))
# the mutation it defends against is real and still present
check("the half-ruling stripper still rewrites treatment in place "
      "(the reason the snapshot exists)",
      '_v4["treatment"] = _tr or ["none"]' in src)

# ── 3. AN AMBIGUOUS REQUEST ASKS ────────────────────────────────────────────
check("K5 is in the working-discipline block", "K5." in src)
check("K5 says to stop and ask rather than pick",
      "STOP AND ASK" in src and "set_spec.clarification" in src)
check("K5 is in the prompt-section fingerprint, so its removal is visible",
      '"K5."' in src and src.count('"K5."') >= 2)
_ss = next((n for n in ast.walk(tree) if isinstance(n, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value == "name"
                    for k in n.keys)
            and any(isinstance(v, ast.Constant) and v.value == "set_spec"
                    for v in n.values)), None)
check("set_spec publishes a `clarification` field", _ss is not None
      and _has_const(_ss, "clarification"))
check("the dispatch reads it and sets the terminal",
      'led["terminal"] = "needs_input"' in src and 'led["needs_input"] = {' in src)
# ast.unparse renders single quotes, so a leg written against the double-quoted
# literal never matches. Read the dict node.
_ni_assign = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                      and t.slice.value == "needs_input" for t in n.targets)]
def _dict_val(node, key):
    for d in ast.walk(node):
        if isinstance(d, ast.Dict):
            for k, v in zip(d.keys, d.values):
                if isinstance(k, ast.Constant) and k.value == key:
                    return v
    return None
check("asking charges nothing",
      bool(_ni_assign) and any(
          isinstance(_dict_val(a_, "credit_charged"), ast.Constant)
          and _dict_val(a_, "credit_charged").value is False for a_ in _ni_assign))
check("it stops the run through the SAME mechanism as unsupported",
      src.count("_unsupported_stop = True") == 2,
      "one stop path, two reasons — a second bespoke stop is a second thing to break")
_ra = _fn("result_agentic")
check("result_agentic returns NEEDS_INPUT as a fourth state",
      _ra is not None and _has_const(_ra, "NEEDS_INPUT"))
check("NEEDS_INPUT carries the question, not just a flag",
      _ra is not None and any(
          isinstance(n, ast.Return) and _has_const(n, "NEEDS_INPUT")
          and _has_const(n, "question") for n in ast.walk(_ra)))
check("and it is distinct from DONE — no plan comes back with a question",
      _ra is not None and any(
          isinstance(n, ast.Return) and _has_const(n, "NEEDS_INPUT")
          and any(isinstance(x, ast.Constant) and x.value == 0 for x in ast.walk(n))
          for n in ast.walk(_ra)))
check("the wire contract documents it for the server half",
      "NEEDS_INPUT" in pathlib.Path("CONTRACT_agentic_wire.md").read_text())

# ── 4. K6: MEASURE BEFORE YOU REBUILD ───────────────────────────────────────
# Distilled from obra/superpowers the way Karpathy's four were: its iron law
# "NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST" is the one rule in that
# repo not already covered by K1-K5, and it has evidence HERE — rounds 51-54,
# 9 of 15 runs called execute_plan more often than inspect_output.
check("K6 is in the working-discipline block", "K6." in src)
check("K6 is in the prompt-section fingerprint", src.count('"K6."') >= 2)
# DRIVEN, not read. Both of the first draft's legs were AST-shape checks and
# both mutants PASSED: gutting the counting branch left the For loop standing,
# and rewriting the print's format string left the literal and the variable
# standing. The rule is hoisted now, so these run it.
_T = lambda *seq: [{"tools": list(t)} for t in seq]
check("a rebuild after a measurement is not blind",
      A.blind_rebuilds(_T(("execute_plan",), ("inspect_output",), ("execute_plan",)))
      == ("MEASURED", 0, 2))
check("a rebuild with NO measurement since the last one IS blind",
      A.blind_rebuilds(_T(("execute_plan",), ("execute_plan",)))
      == ("MEASURED", 1, 2))
check("the first build is never blind — there is nothing to have measured",
      A.blind_rebuilds(_T(("execute_plan",))) == ("MEASURED", 0, 1))
check("two measurements do not bank credit for two rebuilds",
      A.blind_rebuilds(_T(("inspect_output",), ("execute_plan",), ("execute_plan",)))
      == ("MEASURED", 1, 2))
check("a turn calling both counts the measurement it actually made",
      A.blind_rebuilds(_T(("execute_plan",), ("inspect_output", "execute_plan")))
      == ("MEASURED", 0, 2))
check("NO TURN RECORD IS ABSENT, never a clean zero",
      A.blind_rebuilds([]) == ("ABSENT", 0, 0)
      and A.blind_rebuilds(None) == ("ABSENT", 0, 0))
_blind = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
          and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                  and t.slice.value == "rebuilds_without_measurement" for t in n.targets)]
check("the counter is ledgered", bool(_blind))
check("the ledger value comes FROM the hoisted rule, not a local copy",
      any(isinstance(x, ast.Name) and x.id == "_k6_blind"
          for a_ in _blind for x in ast.walk(a_.value))
      and any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "blind_rebuilds"
              for n in ast.walk(tree)))
_k6p = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
        and getattr(n.func, "id", "") == "print"
        and any(isinstance(x, ast.Constant) and isinstance(x.value, str)
                and "K6 REBUILDS" in x.value for x in ast.walk(n))]
check("and PRINTED with BOTH numbers and the state",
      any(all(any(isinstance(x, ast.Name) and x.id == _nm for x in ast.walk(n))
              for _nm in ("_k6_state", "_k6_blind", "_k6_total")) for n in _k6p),
      "a count with no denominator is the reporting defect this repo bans")

# ── 5. THE OVERLAY TRACK IS NOT A SECOND SUBTITLE TRACK ─────────────────────
# talking_head shipped an upper overlay accumulating the transcript verbatim in
# caps while the caption track below showed the same words. The rule against it
# has always existed, perfectly stated, in knowledge/04_text_overlays.md — a
# document reachable only by spending a read_knowledge turn the agent does not
# spend. Same shape as card_props, which cost three rounds of zero cards.
_B = [{"i": 0, "t_start": 0.0, "t_end": 2.0, "text": "being a content creator is not easy"},
      {"i": 1, "t_start": 2.0, "t_end": 4.0, "text": "posting ten times a day takes hours"},
      {"i": 2, "t_start": 4.0, "t_end": 6.0, "text": "editing your own videos takes forever"}]
_V = lambda *copy: [{"beat": i, "treatment": ["text"], "text_content": c}
                    for i, c in enumerate(copy)]
_sub = A.overlay_restates_speech(
    _V("BEING A CONTENT CREATOR", "POSTING TEN TIMES A DAY", "EDITING YOUR OWN VIDEOS"), _B)
check("three consecutive beats each chunking their own sentence is a SUBTITLE TRACK",
      _sub["verdict"] == "SUBTITLE TRACK" and _sub["longest_run"] == 3, str(_sub))
_lab = A.overlay_restates_speech(_V("THE REAL COST", "WHO?", "10"), _B)
check("labels that say what the captions cannot are editorial",
      _lab["verdict"] == "editorial" and _lab["n_restating"] == 0, str(_lab))
_stamp = A.overlay_restates_speech(_V("CREATOR", "HOURS", "FOREVER"), _B)
check("a ONE-WORD stamp taken from the speech is still editorial, not a subtitle",
      _stamp["verdict"] == "editorial", str(_stamp))
# THE TWO ARMS, ISOLATED. The first draft's cases all tripped BOTH arms, so
# deleting either one left the smoke green — two mutants passed. A case that
# fires on both proves neither.
_B6 = [{"i": i, "t_start": i * 2.0, "t_end": i * 2.0 + 2.0,
        "text": t} for i, t in enumerate(
    ["being a content creator is not easy", "posting ten times a day takes hours",
     "editing your own videos takes forever", "so i made a mobile app",
     "it takes care of everything", "five minutes to edit"])]
_run_only = A.overlay_restates_speech(
    [{"beat": 0, "treatment": ["text"], "text_content": "BEING A CONTENT CREATOR"},
     {"beat": 1, "treatment": ["text"], "text_content": "POSTING TEN TIMES A DAY"},
     {"beat": 2, "treatment": ["text"], "text_content": "EDITING YOUR OWN VIDEOS"},
     {"beat": 3, "treatment": ["text"], "text_content": "THE REAL COST"},
     {"beat": 4, "treatment": ["text"], "text_content": "WHO?"},
     {"beat": 5, "treatment": ["text"], "text_content": "60x"}], _B6)
check("the CONSECUTIVE-RUN arm alone catches a rolling transcript "
      "(3 in a row, share only 0.5)",
      _run_only["verdict"] == "SUBTITLE TRACK" and _run_only["longest_run"] == 3
      and _run_only["share"] == 0.5, str(_run_only))
_share_only = A.overlay_restates_speech(
    [{"beat": 0, "treatment": ["text"], "text_content": "BEING A CONTENT CREATOR"},
     {"beat": 2, "treatment": ["text"], "text_content": "EDITING YOUR OWN VIDEOS"},
     {"beat": 4, "treatment": ["text"], "text_content": "TAKES CARE OF EVERYTHING"}], _B6)
check("the SHARE arm alone catches it when no three are adjacent "
      "(3 of 3 restating, longest run 1)",
      _share_only["verdict"] == "SUBTITLE TRACK" and _share_only["longest_run"] == 1,
      str(_share_only))

_gap = A.overlay_restates_speech(
    [{"beat": 0, "treatment": ["text"], "text_content": "BEING A CONTENT CREATOR"},
     {"beat": 2, "treatment": ["text"], "text_content": "EDITING YOUR OWN VIDEOS"}], _B)
check("two NON-consecutive restating beats are not a track (car_mid's shape)",
      _gap["verdict"] == "editorial" and _gap["longest_run"] == 1, str(_gap))
check("no text rulings reads ABSENT, never a clean 'editorial'",
      A.overlay_restates_speech([], _B)["state"] == "ABSENT"
      and A.overlay_restates_speech(None, None)["state"] == "ABSENT")
check("a ruling with no copy cannot be counted as clean",
      A.overlay_restates_speech([{"beat": 0, "treatment": ["text"]}], _B)["state"]
      == "ABSENT")
# the surface where the choice is made must carry the rule
_tc = [v for n in ast.walk(tree) if isinstance(n, ast.Dict)
       for k, v in zip(n.keys, n.values)
       if isinstance(k, ast.Constant) and k.value == "text_content"]
check("the text_content FIELD says the captions already carry every spoken word",
      any("CAPTIONS ALREADY" in ast.unparse(v).upper() for v in _tc),
      "the rule lives in a knowledge doc the agent does not read; it has to be "
      "where the ruling is written")
check("and it says what to write INSTEAD, not only what to avoid",
      any("worth" in ast.unparse(v) and "label" in ast.unparse(v) for v in _tc),
      "educate rather than validate")
check("the measurement is wired, printed with its denominator, and named",
      any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"
          and any(isinstance(x, ast.Constant) and isinstance(x.value, str)
                  and "OVERLAY vs SPEECH" in x.value for x in ast.walk(n))
          and any(isinstance(x, ast.Name) and x.id == "_ors" for x in ast.walk(n))
          for n in ast.walk(tree)))
check("and a subtitle track fails LOUDLY to us",
      any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "fail"
          and any(isinstance(x, ast.Constant)
                  and x.value == "overlay_is_a_second_subtitle_track"
                  for x in ast.walk(n)) for n in ast.walk(tree)))
check("it reads the EXECUTED rulings first — the record is rewritten after the build",
      any(isinstance(n, ast.Call)
          and getattr(n.func, "id", "") == "overlay_restates_speech"
          and any(isinstance(x, ast.Constant) and x.value == "executed_verdicts"
                  for x in ast.walk(n)) for n in ast.walk(tree)))

# ── 6. A BAR THAT FALLS INSIDE ONE POPULATION IS NOT A THRESHOLD ────────────
# _REGION_EFFECT_BAR_DB = 6.0 was drawn when text overlays were whole sentences
# (worst CHANGED 19.98, best INERT 0.24 — a 19.7 dB gap). Round 58 shipped the
# text_content fix, overlays became short labels, and all seven read 4.70-6.76:
# the bar fell inside a single cluster and called five correctly-rendered
# overlays INERT. Nobody moved the bar; the CONTENT moved under it.
check("a clean gap on one side of the bar SEPARATES",
      A.bar_separates([1.0, 2.0, 9.0, 12.0], bar=6.0)[0] == "SEPARATES")
check("every value on one side also SEPARATES — nothing straddles",
      A.bar_separates([8.0, 9.0, 12.0], bar=6.0)[0] == "SEPARATES"
      and A.bar_separates([1.0, 2.0], bar=6.0)[0] == "SEPARATES")
_ic = A.bar_separates([4.70, 5.09, 5.11, 5.70, 5.91, 6.24, 6.76], bar=6.0)
check("round 58's REAL text deltas report INSIDE_CLUSTER",
      _ic[0] == "INSIDE_CLUSTER" and "0.33" in _ic[1], str(_ic))
check("round 57's REAL text deltas still SEPARATE — the bar was fine until "
      "the population moved",
      A.bar_separates([4.29, 7.94, 8.11, 8.13, 8.19, 8.20, 9.75], bar=6.0)[0]
      == "SEPARATES")
check("fewer than two values is ABSENT — two points cannot show a gap",
      A.bar_separates([5.0], bar=6.0)[0] == "ABSENT"
      and A.bar_separates([], bar=6.0)[0] == "ABSENT")
check("an infinite delta is not counted as a value",
      A.bar_separates([float("inf"), 5.0], bar=6.0)[0] == "ABSENT")
# PER FAMILY, read from the AST rather than from a name that appears four
# times. `"region_bar_separation" in src` would survive deleting the per-family
# loop entirely, because the key is also read where the verdicts are resolved.
_bsl = [n for n in ast.walk(tree) if isinstance(n, ast.For)
        and any(isinstance(x, ast.Call)
                and getattr(x.func, "id", "") == "bar_separates"
                for x in ast.walk(n))]
check("the separation is checked PER FAMILY — only the text family's "
      "distribution moved",
      bool(_bsl) and any("_fx" in ast.unparse(n.iter) or "items()" in ast.unparse(n.iter)
                         for n in _bsl),
      "bar_separates must be called inside a loop over the families, not once "
      "over everything")
check("and an unsupportable bar fails LOUDLY, naming its verdicts unvalidated",
      any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "fail"
          and any(isinstance(x, ast.Constant)
                  and x.value == "inert_bar_inside_population"
                  for x in ast.walk(n)) for n in ast.walk(tree))
      and any(isinstance(n, ast.Constant) and isinstance(n.value, str)
              and "UNVALIDATED" in n.value and "do not read them as defects" in n.value
              for n in ast.walk(tree)))

# ── 7. THE BAR IS PER CONTROL SCHEME, AND REFUSES WHERE NONE IS SUPPORTABLE ──
# One bar was being applied to two populations whose nulls differ by 8 dB. It
# is now chosen by the control that produced the number, and where the measured
# null exceeds the real signal there is no bar and therefore no verdict.
check("the same-window control has a bar drawn on its measured null",
      A.region_bar_for("same_window_layer_withheld")[0] == 1.0)
check("the window-elsewhere control has NO bar — its null exceeds the signal",
      A.region_bar_for("window_elsewhere")[0] is None
      and "no bar separates them" in A.region_bar_for("window_elsewhere")[1])
check("an unknown scheme gets no bar and says why, rather than a default",
      A.region_bar_for("invented_later")[0] is None
      and "nobody measured" in A.region_bar_for("invented_later")[1])
check("a missing scheme is treated as unknown, not as the old default",
      A.region_bar_for(None)[0] is None)
check("and the basis is carried with the bar, never just the number",
      all(isinstance(A.region_bar_for(k)[1], str) and A.region_bar_for(k)[1]
          for k in ("same_window_layer_withheld", "window_elsewhere", "x")))
# THE ASSIGNMENT, not the word. "UNVALIDATED" appears three times in the app.
_unv = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                and t.slice.value == "region_verdict" for t in n.targets)
        and isinstance(n.value, ast.Constant) and n.value.value == "UNVALIDATED"]
check("a region measurement with no supportable bar records UNVALIDATED and "
      "changed=None, never CHANGED or INERT",
      bool(_unv) and any(
          isinstance(n, ast.Assign)
          and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                  and t.slice.value == "changed" for t in n.targets)
          and isinstance(n.value, ast.Constant) and n.value.value is None
          for n in ast.walk(tree)))
# THE BRANCH, NOT THE NAME. `'_deferred_inert' in src` survived gutting the
# deferral entirely, because the name still appears in the block that resolves
# the list at the end of the run. Read the If that does the deferring: it must
# test the region mode, append to the list, and RETURN before the inline fail.
_defer = [n for n in ast.walk(tree) if isinstance(n, ast.If)
          and any(isinstance(x, ast.Constant) and x.value == "region"
                  for x in ast.walk(n.test))
          and any(isinstance(x, ast.Constant) and x.value == "_deferred_inert"
                  for x in ast.walk(n))
          and any(isinstance(x, ast.Return) for x in ast.walk(n))]
check("the INERT verdict is DEFERRED to the end of the run, where the "
      "family's population exists",
      bool(_defer)
      and any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "fail"
              and any(isinstance(x, ast.Constant) and x.value == "inert_verdict_unvalidated"
                      for x in ast.walk(n)) for n in ast.walk(tree)),
      "an If testing region mode, recording the deferral, and returning before "
      "the inline fail — all three, or the verdict still fires per placement")
check("and it is reported as a defect ONLY where the bar separates that family",
      '_sep == "SEPARATES"' in src)

print()
if fails:
    print("ASK-AND-INTENT: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("ASK-AND-INTENT: PASS — no overlay without a ruling, the executed rulings "
      "are frozen, an ambiguous request stops and asks for free, and a blind "
      "rebuild is counted against its denominator, and an overlay track that "
      "repeats the captions is named, and a bar that no longer splits its "
      "population refuses to hand down verdicts, with the bar chosen by "
      "the control that produced the number")
