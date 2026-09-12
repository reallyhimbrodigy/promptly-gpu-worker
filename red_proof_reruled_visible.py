#!/usr/bin/env python3
"""RED proof for smoke_reruled_visible.py, in a throwaway git worktree.

EVERY MUTATION MUTATES THE ARTIFACT THE GATE READS — the app — NEVER THE GATE.
Weakening a check makes it PASS, so a harness that mutates the gate's own legs
reads "not red" for the expected outcome and measures nothing in either
direction. That correction cost four wrong expectations once already.

Each case also runs the UNMUTATED gate in the same worktree first and requires
green, so a red result is attributable to the mutation and not to the sandbox.
"""
import pathlib, shutil, subprocess, sys, tempfile

SMOKE = pathlib.Path("smoke_reruled_visible.py").resolve()
APPNAME = "agentic_editor_app.py"

# (label, old, new, expected phrase in the gate's failure output)
MUTATIONS = [
    # THE ANCHOR IS THE THING THAT ROTS. This mutation went stale the moment
    # the call site gained its third argument, and the harness said [ANCHOR]
    # rather than [RED] — which is the sixth way a mutation stops mutating,
    # caught by the leg that requires the anchor to be unique rather than by a
    # green run. A red proof whose mutation no longer applies is not evidence.
    ("the call drops the executed copy, so `built_from` is unanswerable",
     '''    _rr_state, _rr_rows = reruled_beats(led.get("beat_verdicts"),
                                        led.get("executed_verdicts"),
                                        led.get("executed_verdicts_fp"))''',
     '''    _rr_state, _rr_rows = reruled_beats(led.get("beat_verdicts"))''',
     "called with the executed copy"),

    ("the state is ledgered but never printed",
     '''          % (_rr_state, len(_rr_rows),''',
     '''          % ("", len(_rr_rows),''',
     "reaches a print"),

    ("a ledger key stops being written",
     '''    led["reruled_count"] = len(_rr_rows)''',
     '''    _unused_count = len(_rr_rows)''',
     "reruled_count"),

    ("the per-beat rows stop being printed — a count alone cannot say which "
     "beat changed",
     '''    for _r in _rr_rows:
        print("     beat %s: %d rulings, BUILT FROM %s%s"''',
     '''    for _r in []:
        print("     beat %s: %d rulings, BUILT FROM %s%s"''',
     "RE-RULED VISIBLE"),

    ("absence starts reading as a zero",
     '''        return ("ABSENT", [])''',
     '''        return ("MEASURED", [])''',
     "ABSENT, not a zero"),

    ("a lost field stops being recorded",
     '''                    _lost.append(_k)''',
     '''                    pass''',
     "names the LOST field"),

    ("identical duplicates start reading as a confident `first`",
     '''            _built = "identical"          # not vacuously "first": nothing differs''',
     '''            _built = "first"''',
     "not a vacuous"),

    ("`built_from` is asserted instead of derived — always `first`",
     '''                      "first" if _first else "later" if _last else "MIXED")''',
     '''                      "first")''',
     "derived from the executed copy"),

    ("the freeze stops being fingerprinted, so built_from cannot fail",
     '        led["executed_verdicts_fp"] = verdicts_fingerprint(led["executed_verdicts"])',
     '        _unused_fp = verdicts_fingerprint(led["executed_verdicts"])',
     "records its own fingerprint"),

    ("the call site stops passing the fingerprint — the freeze is trusted "
     "rather than checked",
     "                                        led.get(\"executed_verdicts_fp\"))",
     "                                        )",
     "passes the fingerprint"),

    ("a mutated freeze goes back to reading a confident `first`",
     '        if not _freeze_ok:\n            _built = "FREEZE_MUTATED"     # the record of what built was rewritten\n        elif not _changed:',
     '        if not _changed:',
     "FREEZE_MUTATED"),

    ("the fingerprint stops distinguishing anything",
     '    return _hl.sha256(\n        _js.dumps(vs, sort_keys=True, default=str).encode("utf-8")).hexdigest()',
     '    return "constant"',
     "FREEZE_MUTATED"),

    ("the singular tool's reply goes back to a deduped count",
     '                out = {"recorded": bool(_ok7),\n                       "rulings": len(_bseen),',
     '                out = {"recorded": bool(_ok7),\n                       "ruled": len(set(_bseen)),',
     "RULINGS and BEATS separately"),

    ("the reply stops naming the duplicated beat back to the agent",
     '                    out["DISCARDED_already_ruled"] = _bv.get("beat")',
     '                    _unused = _bv.get("beat")',
     "NAMES the duplicated beat"),

    ("the singular handler goes back to a hand-written field list",
     '                _bv = {k: tu.input.get(k) for k in VERDICT_FIELDS\n                       if k in tu.input}',
     '                _bv = {"beat": tu.input.get("beat")}',
     "projects the schema-derived field list"),

    ("a key never written reads as None again, hiding whether the default "
     "survives",
     '            _vals = [(_r[_k] if _k in _r else _MISSING) for _r in _rul]',
     '            _vals = [_r.get(_k) for _r in _rul]',
     "rendered as absent, not as None"),

    ("fields empty in every ruling flood the report again",
     '            if all(_x in _EMPTYISH or _x == _MISSING for _x in _vals):\n                continue\n',
     '',
     "not reported as a change"),

    ("the surfaces diverge again — a field is dropped from the sync",
     '        if _k not in _dst:\n            _dst[_k] = _cp.deepcopy(_v)\n            _added.append(_k)',
     '        if _k not in _dst and _k != "zoom_arc":\n            _dst[_k] = _cp.deepcopy(_v)\n            _added.append(_k)',
     # STRONGER THAN THE LEG: the import-time cert fires first and the
     # container refuses to start, so the smoke never reaches its legs.
     "ruling surfaces offer different fields"),

    ("the sync stops running at import",
     "VERDICT_SURFACES_SYNCED = _sync_verdict_surfaces()",
     "VERDICT_SURFACES_SYNCED = []",
     "ruling surfaces offer different fields"),

    ("the sync reads an empty source schema — it must RAISE, not\n     silently leave beat_verdict as it was",
     '    _src_props = _items.get("properties") or {}',
     '    _src_props = {}',
     "declares no verdict item properties"),

    ("the tool stops being withheld on a first edit",
     '    if not _reedit:\n        _bv = [t for t in tools if t.get("name") == "beat_verdict"]',
     '    if False:\n        _bv = [t for t in tools if t.get("name") == "beat_verdict"]',
     "WITHHELD on a first edit"),

    ("the equal-capability assert is removed, so a path could lose the\n     plural ruling surface silently",
     '            "rule_all_beats is not offered on this path (%s) — withholding "',
     '            "rule_all_beats was not checked on this path (%s) — withholding "',
     "RAISES if rule_all_beats is ever absent"),

    ("the conditional saving stops being printed as two numbers",
     '"  TOOL SURFACE    : %s  ~%d tok%s"',
     '"  tool_surface_renamed : %s  ~%d tok%s"',
     "both numbers reach a real print"),

    ("beat_verdict goes back into _REPAIR_ONLY, forcing a re-edit to rebuild\n     the whole prior edit before it can change one beat",
     '                    "render_components", "author_component"}',
     '                    "render_components", "author_component", "beat_verdict"}',
     "no longer in _REPAIR_ONLY"),

    ("the description goes back to reading as a general ruling surface",
     '        "THE SURGICAL INSTRUMENT, AND IT IS ONLY OFFERED ON A RE-EDIT. You are "',
     '        "Every beat in your brief needs one before you finish. You are "',
     "no longer tells the agent every beat needs one"),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="rerul_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("could not create a throwaway worktree"); sys.exit(1)

fails = []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    _app = pathlib.Path(_wt) / APPNAME
    _pristine = _app.read_text()

    rc0, out0 = run(_wt)
    if rc0 != 0:
        print("BASELINE NOT GREEN in the worktree — the sandbox is wrong, not "
              "the gate\n" + out0[-2000:])
        sys.exit(1)
    print("RED PROOF — re-ruled visibility   (baseline green)")

    for _label, _old, _new, _phrase in MUTATIONS:
        _app.write_text(_pristine)
        if _pristine.count(_old) != 1:
            fails.append(f"{_label}: anchor found {_pristine.count(_old)}x, "
                         f"need exactly 1 — the mutation did not apply, so "
                         f"'not red' would be meaningless")
            print(f"  [ANCHOR] {_label}")
            continue
        _app.write_text(_pristine.replace(_old, _new, 1))
        rc, out = run(_wt)
        _red = rc != 0
        _said = _phrase.lower() in out.lower()
        if not (_red and _said):
            fails.append(f"{_label}: rc={rc} red={_red} "
                         f"phrase({_phrase!r})={_said}\n{out[-1200:]}")
        print(f"  [{'RED' if _red and _said else 'NOT RED'}] {_label}")

    _app.write_text(_pristine)
finally:
    subprocess.run(["git", "worktree", "remove", "--force", _wt],
                   capture_output=True)
    shutil.rmtree(_tmp, ignore_errors=True)

print()
if fails:
    print("RED PROOF: FAILED TO GO RED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("RED PROOF: PASS — %d app mutations, %d reds, baseline green"
      % (len(MUTATIONS), len(MUTATIONS)))
