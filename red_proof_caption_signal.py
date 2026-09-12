#!/usr/bin/env python3
"""RED proof for the caption signal. Mutates the APP, never the gate."""
import pathlib, subprocess, sys

APP = pathlib.Path("agentic_editor_app.py")
GATE = "smoke_prompt_fidelity.py"
CASES = [
    ("the page layout leaves the fingerprint — a regrouping reads as a no-op",
     '_body = _j.dumps({"style": str(style or ""), "fps": fps, "pages": _pages},',
     '_body = _j.dumps({"style": str(style or ""), "fps": fps},',
     "REGROUPED still counts as changed"),
    ("no captions starts reading as an empty signature instead of ABSENT",
     '    if not pages:\n        return ("ABSENT", None)',
     '    if False:\n        return ("ABSENT", None)',
     "ABSENT, not an empty signature"),
    # MUTATE THE ANSWER, NOT THE GUARD. Deleting the guard makes
    # `prior_sig.get("fp")` raise on None, so the app crashes and the gate never
    # reaches the leg — a red for the wrong reason proves nothing.
    ("a missing prior fingerprint starts reading as 'unchanged'",
     '        return ("ABSENT", False,\n                "no caption fingerprint on the prior plan',
     '        return ("MEASURED", False,\n                "no caption fingerprint on the prior plan',
     "no prior fingerprint is ABSENT"),
    ("the signature stops riding the durable plan",
     '    _plan = plan_with_caption(_plan, led.get("caption_signature"))',
     '    _plan = list(_plan)',
     "PERSISTED on the durable plan"),
    ("fidelity stops gating captions on whether they changed",
     "                _cap_for_fid = _cap_for_fid and _cc_changed",
     "                _cap_for_fid = _cap_for_fid",
     "gated on captions_changed"),
    # THE LITERAL, not the print statement: swapping `print(` for `_np = (`
    # leaves `flush=True` inside a tuple and the app stops parsing, so the gate
    # dies instead of failing the leg.
    ("the caption delta stops being printed",
     '"  CAPTION DELTA   : %s  changed=%s — %s"',
     '"  caption_delta_renamed : %s  changed=%s — %s"',
     "reaches a real print"),
    ("a REMOVED caption run reads as delivered",
     '    if now_state == "ABSENT":\n        return ("REMOVED" if prior_sig else "ABSENT", False,',
     '    if False:\n        return ("REMOVED" if prior_sig else "ABSENT", False,',
     "gone this turn is REMOVED"),
    # THE NEGATIVE-CONSTRAINT CLASS. 7.2% of distinct briefs, 4.2% of users,
    # and the pipeline had never been tested on one.
    ("the forbidden check moves back behind the mode gate, so a full_edit\n     escapes it — the commonest real shape",
     '    _forbidden = {str(_f).lower() for _f in (_sc.get("forbidden") or [])}',
     '    _forbidden = set() if _mode != "targeted_change" else {str(_f).lower() for _f in (_sc.get("forbidden") or [])}',
     "FULL_EDIT that delivers a forbidden family"),
    ("a forbidden family stops failing the run",
     '        fail("fidelity_forbidden",',
     '        _unemitted = ("fidelity_forbidden",',
     "FAILS LOUDLY"),
    ("`forbidden` stops being offered on set_spec",
     '            "forbidden": {"type": "array", "items": {"type": "string"},',
     '            "_forbidden_unoffered": {"type": "array", "items": {"type": "string"},',
     "offered on set_spec"),
    ("the field stops saying it applies in any mode",
     '                              "ANY MODE. The families this request says NOT to "',
     '                              "targeted_change only: the families it says NOT to "',
     "applies in ANY mode"),
    # THE UNSCOPED HALF. 48.2% of users, all 37 fixture runs, 20 of them
    # INCOHERENT — and nothing judged any of it before this.
    ("a dropped family stops being INCOHERENT",
     '            (_dropped if _fam in BUILT_FAMILIES else _unb)[_fam] = (_r, _b)',
     '            _unb[_fam] = (_r, _b)',
     "is INCOHERENT"),
    ("VACANT collapses into COHERENT — placing nothing stops being a failure",
     '    if not _did_anything:',
     '    if False:',
     "VACANT is its own state"),
    ("an unbuildable family starts counting against the run",
     '        if _r > _b:\n            (_dropped if _fam in BUILT_FAMILIES else _unb)[_fam] = (_r, _b)',
     '        if _r > _b:\n            _dropped[_fam] = (_r, _b)',
     "UNBUILDABLE, not the run"),
    ("the grade stops failing the run",
     '            fail("unscoped_incoherent", _co_why)',
     '            _unemitted = ("unscoped_incoherent", _co_why)',
     "unscoped_incoherent` fails loudly"),
    ("the builder set becomes a second hand-written copy",
     '        _TYPE = dict(BUILT_FAMILIES)',
     '        _TYPE = {"text": "overlay_text", "zoom": "emphasis"}',
     "ONE declaration shared with the dispatch"),
    # THE OBSOLETE MUTATION THAT USED TO SIT HERE tested the agreement branch
    # between `treatment` and the `sfx` field. The schema change DELETED that
    # branch — the disagreement is impossible once the field is derived — so
    # its anchor went to 0x and the harness said [ANCHOR]. A mutation whose
    # property no longer exists is retired, not repaired.
    # THE ANCHOR MUST BE UNIQUE AND IT MUST ACTUALLY BITE. Both stripper sites
    # carry identical text, so the bare expression matched twice ([ANCHOR]);
    # anchoring on the comment alone applied cleanly and changed NOTHING
    # ([NOT RED] — the seventh way, a mutation that does not mutate). The
    # anchor spans the unique comment AND the expression it guards.
    ("the stripper reverts to reading the sfx field alone (post-derivation)",
     '                # just established.\n                # KEYED ON TREATMENT, like its siblings _nocopy and _nocard.\n                # It read only the `sfx` FIELD, so `treatment: ["sfx"]` with no\n                # field set was never in this list and never stripped — the 25\n                # dropped placements. half_ruling_refusal now refuses these\n                # where the agent still holds the beat; this is defence in\n                # depth for anything arriving by another route.\n                _nosfx = [v.get("beat") for v in led["beat_verdicts"]\n                          if ("sfx" in [str(t).lower()\n                                        for t in (v.get("treatment") or [])]\n                              or str(v.get("sfx", "no")).lower() == "yes")\n                          and not str(v.get("sfx_name") or "").strip()]',
     '                # just established.\n                # KEYED ON TREATMENT, like its siblings _nocopy and _nocard.\n                _nosfx = [v.get("beat") for v in led["beat_verdicts"]\n                          if str(v.get("sfx", "no")).lower() == "yes"\n                          and not str(v.get("sfx_name") or "").strip()]',
     "key on TREATMENT, not the field alone"),
    ('the blank sfx field stops being filled from the treatment, so the deriver is never reachable and the build reads no',
     '        if str(rec.get(_k) or "").strip() == "":\n            rec[_k] = _fn(rec)',
     '        if False:\n            rec[_k] = _fn(rec)',
     'blank field is filled from the treatment'),
    ('the fill starts OVERRIDING an answer the agent gave',
     '        if str(rec.get(_k) or "").strip() == "":\n            rec[_k] = _fn(rec)',
     '        if True:\n            rec[_k] = _fn(rec)',
     'answer the agent DID give is not overwritten'),
    ('the contradiction stops being refused, so treatment and field disagree silently and the build follows the field',
     '    if why is None and "sfx" in tr and str(v.get("sfx") or "").lower() == "no":',
     '    if False:',
     'is REFUSED — opposite answers'),
    ('a nameless sfx ruling goes back to being refused, pre-empting the deriver',
     '    if why is None and "card" in tr:',
     '    if why is None and "sfx" in tr and not v.get("sfx_name"):\n        why = "no name"\n    if why is None and "card" in tr:',
     'NOT refused at ruling time'),
    ('co-visibility stops being reported at all',
     '        if _both:\n            _rows.append({"beat": _p.get("beat"),',
     '        if False:\n            _rows.append({"beat": _p.get("beat"),',
     'same instant is reported'),
    ('the window becomes the whole video, so words spoken far away count',
     '            if float(_we) > float(_t0) and float(_ws) < _t1:',
     '            if True:',
     "OUTSIDE the overlay's window are not co-visible"),
    ('no overlays starts reading as a clean pass instead of ABSENT',
     '    if not _texts or not caption_words:\n        return ("ABSENT", [])',
     '    if False:\n        return ("ABSENT", [])',
     'nothing to duplicate'),
    ('the sound enum is withdrawn, so any string is a sound again',
     '                                     "enum": sorted(SFX_MOMENTS) or None,',
     '                                     "enum": None,',
     'sixteen as an ENUM'),
    ('the field goes back to telling the agent to pick by ROLE',
     '                                     "description": "WHICH sound. Pick by the "',
     '                                     "description": "which catalogue sound. Pick by ROLE "',
     'no longer tells the agent to pick by ROLE'),
    ('an empty catalogue stops naming its own absence',
     '    if not SFX_MOMENTS:',
     '    if False:',
     'NAMED ABSENCE, not silence'),
    ('the SKIP option leaves the text field again',
     '                                                    "\'WHO?\') **or SKIP IT** "',
     '                                                    "\'WHO?\'). "',
     'including the SKIP option'),
    ('the sfx field offers role-based selection again, contradicting sfx_name',
     '"beats role when you name no sound, but that is a LAST RESORT the "',
     '"beats role when you name no sound, which means a sound belongs "\n                                             "here, choose it from the beat role. "',
     'does not offer role-based sound selection'),
    ('card_hero claims to be the only card input again',
     '"IT IS NOT THE ONLY THING YOU SAY. card_props OUTRANKS it (a "',
     '"This is the ONLY thing you say about a card. card_props OUTRANKS it (a "',
     'no longer claims to be the only card input'),
    ('a second field claims authority over the component',
     '"THIS NARROWS, IT DOES NOT DECIDE: a uniquely-owned `card_props` "',
     '"the component is derived from your answer. A uniquely-owned `card_props` "',
     'at most ONE ruling field claims authority'),
    ('the cut criterion leaves the field, back to a prohibition only',
     '    "\\n\\nWHAT A CUT IS FOR. The mechanical pass already took the measured "',
     '    "\\n\\nWhat a cut is for: the mechanical pass already took the measured "',
     'says what a cut IS for'),
    ('the fluent-speech protection is dropped, so leanness becomes a reason',
     '    "never cut it for \'leanness\' or for pace. \'It took five minutes to edit. "',
     '    "cut it for leanness or for pace where it helps. \'It took five minutes to edit. "',
     'never cut for leanness'),
    ('the unsure-keep rule is dropped',
     '    "WHEN UNSURE, KEEP. A pause you cannot tell is dead or dramatic is a "',
     '    "When unsure, decide. A pause you cannot tell is dead or dramatic is a "',
     'unsure-keep rule'),
    ('the sub-beat case is DEMANDED here instead of routed, which is the unsatisfiable refusal',
     '    "sentence — this field cannot remove it, and ruling `cut` on the whole "',
     '    "sentence — rule `cut` on it, and ruling `cut` on the whole "',
     'ROUTED to build_cut'),
    ('the granularity reinterpretation stops being marked as translated',
     '    "[01_cut_pass, translated 2026-09-12: the source names three WORD-RANGE "',
     '    "[01_cut_pass, wired 2026-09-12: the source names three word-range "',
     'marked TRANSLATED, not wired'),
]

orig = APP.read_text()
r = subprocess.run([sys.executable, GATE], capture_output=True, text=True)
if r.returncode != 0:
    print("BASELINE NOT GREEN — the sandbox is wrong, not the gate")
    print((r.stdout + r.stderr)[-1500:]); sys.exit(1)
print("RED PROOF — the caption signal   (baseline green)")
fails = []
for label, old, new, phrase in CASES:
    if orig.count(old) != 1:
        fails.append("%s: anchor found %dx" % (label, orig.count(old)))
        print("  [ANCHOR] %s" % label); continue
    APP.write_text(orig.replace(old, new, 1))
    rr = subprocess.run([sys.executable, GATE], capture_output=True, text=True)
    out = rr.stdout + rr.stderr
    ok = rr.returncode != 0 and phrase.lower() in out.lower()
    if not ok:
        fails.append("%s: rc=%s phrase=%s" % (label, rr.returncode,
                                              phrase.lower() in out.lower()))
    print("  [%s] %s" % ("RED" if ok else "NOT RED", label))
APP.write_text(orig)
rr = subprocess.run([sys.executable, GATE], capture_output=True, text=True)
print("restored:", "PASS" if rr.returncode == 0 else "FAIL")
if fails:
    print("\nRED PROOF: FAILED TO GO RED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("\nRED PROOF: PASS — %d app mutations, %d reds" % (len(CASES), len(CASES)))
