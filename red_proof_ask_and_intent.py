#!/usr/bin/env python3
"""RED proof for smoke_ask_and_intent.py, in a throwaway worktree.

The mutations are the three properties reverting: the second overlay channel
reopening (silently, and loudly-but-uselessly), the executed-ruling snapshot
becoming a shallow reference the stripper rewrites, and the ask being demoted
to a note that lets the run guess anyway.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile

SMOKE = pathlib.Path("smoke_ask_and_intent.py").resolve()
APPNAME = "agentic_editor_app.py"
_INJECTS = None
MUTATIONS = [
    ("the second overlay channel reopens — caller items land unruled again",
     "                if not any(_a - 1e-3 <= _it_t <= _b + 1e-3 for _a, _b in _text_windows):\n"
     "                    _unruled_refused.append(\n"
     "                        {\"t_start\": _it_t, \"text\": str(it.get(\"text\") or \"\")[:60]})\n"
     "                    continue\n",
     "",
     "a caller-supplied overlay is refused", _INJECTS),
    ("the candidate windows stop being filtered by the ruling",
     '        _text_beats = [_by_i.get(v.get("beat")) for v in (led.get("beat_verdicts") or [])\n'
     '                       if "text" in (v.get("treatment") or [])]',
     '        _text_beats = [_by_i.get(v.get("beat")) for v in (led.get("beat_verdicts") or [])]',
     "filtered on a treatment naming text", _INJECTS),
    ("the refusal stops being printed",
     '            print(f"  OVERLAY REFUSED : {len(_unruled_refused)} caller-supplied "',
     '            _quiet(f"  OVERLAY REFUSED : {len(_unruled_refused)} caller-supplied "',
     "PRINTED in the same commit", _INJECTS),
    ("the refusal stops failing loudly — a lost overlay reads as taste",
     '            fail("overlay_unruled_refused",',
     '            _note("overlay_unruled_refused",',
     "fail()s loudly", _INJECTS),
    ("the executed-ruling snapshot becomes a shallow reference the stripper rewrites",
     '        led["executed_verdicts"] = _copy.deepcopy(vs)',
     '        led["executed_verdicts"] = vs',
     "it is a DEEP COPY", _INJECTS),
    ("the snapshot count stops being printed",
     '        print("  EXECUTED FROM   : %d ruling(s) — %s"',
     '        _quiet("  EXECUTED FROM   : %d ruling(s) — %s"',
     "the count is printed", _INJECTS),
    ("K5 is demoted to advice with no field to carry it",
     '            "clarification": {"type": "string",',
     '            "_clarification_unused": {"type": "string",',
     "publishes a `clarification` field", _INJECTS),
    ("asking no longer stops the run — the agent guesses after asking",
     '                        _unsupported_stop = True\n                        continue\n                    if _sc["mode"] == "unsupported":',
     '                        continue\n                    if _sc["mode"] == "unsupported":',
     "SAME mechanism as unsupported", _INJECTS),
    ("asking starts charging the user",
     '                        led["needs_input"] = {"question": _clar[:500],\n'
     '                                              "why": str((tu.input or {}).get("why") or "")[:200],\n'
     '                                              "credit_charged": False}',
     '                        led["needs_input"] = {"question": _clar[:500],\n'
     '                                              "why": str((tu.input or {}).get("why") or "")[:200],\n'
     '                                              "credit_charged": True}',
     "asking charges nothing", _INJECTS),
    ("the blind-rebuild counter stops counting — every rebuild reads as measured",
     "                if not _seen:\n                    _blind += 1",
     "                if False:\n                    pass",
     "NO measurement since the last one IS blind", _INJECTS),
    ("a measurement banks credit for every later rebuild",
     "                _seen = False\n    return (\"MEASURED\", _blind, _total)",
     "                pass\n    return (\"MEASURED\", _blind, _total)",
     "do not bank credit", _INJECTS),
    ("an absent turn record reads as a clean zero",
     '    if not turns:\n        return ("ABSENT", 0, 0)',
     '    if not turns:\n        return ("MEASURED", 0, 0)',
     "never a clean zero", _INJECTS),
    ("the ledger takes a local copy instead of the hoisted rule",
     '    led["rebuilds_without_measurement"] = _k6_blind',
     '    led["rebuilds_without_measurement"] = 0',
     "FROM the hoisted rule", _INJECTS),
    ("the print loses its denominator",
     '          % (_k6_state, _k6_blind, _k6_total), flush=True)',
     '          % (_k6_state, _k6_blind, _k6_blind), flush=True)',
     "BOTH numbers and the state", _INJECTS),
    ("NEEDS_INPUT collapses into DONE — the question never reaches the server",
     '        return {"state": "NEEDS_INPUT", "call_id": _cid,',
     '        return {"state": "DONE", "call_id": _cid,',
     "fourth state", _INJECTS),
]


def run(wt):
    r = subprocess.run([sys.executable, str(pathlib.Path(wt) / SMOKE.name)],
                       cwd=wt, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_tmp = tempfile.mkdtemp(prefix="aai_")
_wt = str(pathlib.Path(_tmp) / "wt")
if subprocess.run(["git", "worktree", "add", "--detach", "-q", _wt, "HEAD"],
                  capture_output=True).returncode != 0:
    print("no isolated worktree"); sys.exit(2)
red, harness = 0, []
try:
    shutil.copy(SMOKE, pathlib.Path(_wt) / SMOKE.name)
    shutil.copy(pathlib.Path("CONTRACT_agentic_wire.md").resolve(),
                pathlib.Path(_wt) / "CONTRACT_agentic_wire.md")
    APP = pathlib.Path(_wt) / APPNAME
    ORIG = APP.read_text()
    rc, out = run(_wt)
    if rc != 0:
        print("BASELINE IS NOT GREEN:\n" + out[-1500:]); sys.exit(2)
    print("baseline: PASS (isolated worktree)\n")
    for label, old, new, expect, precond in MUTATIONS:
        txt = APP.read_text(); n = txt.count(old)
        if n != 1:
            harness.append(f"{label}: anchor {n}x")
            print(f"  HARNESS FAILURE  {label}  :: anchor {n}x"); continue
        _m = txt.replace(old, new, 1)
        try:
            ast.parse(_m)
        except SyntaxError as e:
            harness.append(f"{label}: mutant does not parse")
            print(f"  HARNESS FAILURE  {label}  :: does not parse ({e.msg})"); continue
        APP.write_text(_m); mrc, mout = run(_wt); APP.write_text(ORIG)
        if mrc == 0:
            print(f"  NOT RED          {label}  :: the mutant PASSED")
            harness.append(f"{label}: mutant passed")
        elif expect not in mout:
            print(f"  WRONG REASON     {label}  :: expected '{expect}'")
            harness.append(f"{label}: wrong reason")
        else:
            red += 1
            print(f"  RED              {label}\n                   caught by: {expect}")
    frc, _ = run(_wt)
    print(f"\nRESTORED exit={frc}")
finally:
    subprocess.run(["git", "worktree", "remove", "--force", _wt], capture_output=True)
    shutil.rmtree(_tmp, ignore_errors=True)
    print(f"isolated worktree removed: {not pathlib.Path(_wt).exists()}")
print(f"{red}/{len(MUTATIONS)} RED-proven"
      + (f"   HARNESS FAILURES: {harness}" if harness else ""))
sys.exit(0 if red and red == len(MUTATIONS) and not harness else 1)
