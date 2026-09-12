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
    ('sfx leaves half_ruling_refusal again - back to a silent build-time skip',
     '    if why is None and "sfx" in tr:',
     '    if False and "sfx" in tr:',
     'with no sfx_name is REFUSED'),
    # THE OBSOLETE MUTATION THAT USED TO SIT HERE tested the agreement branch
    # between `treatment` and the `sfx` field. The schema change DELETED that
    # branch — the disagreement is impossible once the field is derived — so
    # its anchor went to 0x and the harness said [ANCHOR]. A mutation whose
    # property no longer exists is retired, not repaired.
    ("the boundary stops deriving sfx, so the build reads None again",
     '    for _k, _fn in DERIVED_VERDICT_FIELDS.items():\n        rec[_k] = _fn(rec)',
     '    for _k, _fn in DERIVED_VERDICT_FIELDS.items():\n        pass',
     "derived value is 'yes' on an sfx beat"),
    # THE ANCHOR MUST BE UNIQUE AND IT MUST ACTUALLY BITE. Both stripper sites
    # carry identical text, so the bare expression matched twice ([ANCHOR]);
    # anchoring on the comment alone applied cleanly and changed NOTHING
    # ([NOT RED] — the seventh way, a mutation that does not mutate). The
    # anchor spans the unique comment AND the expression it guards.
    ("the stripper reverts to reading the sfx field alone (post-derivation)",
     '                # just established.\n                # KEYED ON TREATMENT, like its siblings _nocopy and _nocard.\n                # It read only the `sfx` FIELD, so `treatment: ["sfx"]` with no\n                # field set was never in this list and never stripped — the 25\n                # dropped placements. half_ruling_refusal now refuses these\n                # where the agent still holds the beat; this is defence in\n                # depth for anything arriving by another route.\n                _nosfx = [v.get("beat") for v in led["beat_verdicts"]\n                          if ("sfx" in [str(t).lower()\n                                        for t in (v.get("treatment") or [])]\n                              or str(v.get("sfx", "no")).lower() == "yes")\n                          and not str(v.get("sfx_name") or "").strip()]',
     '                # just established.\n                # KEYED ON TREATMENT, like its siblings _nocopy and _nocard.\n                _nosfx = [v.get("beat") for v in led["beat_verdicts"]\n                          if str(v.get("sfx", "no")).lower() == "yes"\n                          and not str(v.get("sfx_name") or "").strip()]',
     "keys on TREATMENT like _nocopy and _nocard"),
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
