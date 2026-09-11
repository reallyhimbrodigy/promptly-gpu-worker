#!/usr/bin/env python3
"""A VFR SOURCE IS NORMALISED ON INGEST; A CFR SOURCE IS LEFT ALONE.

MEASURED, round 48: `motion` renders zoom frames at 5.92s/frame against
1.17-1.51 on every CFR fixture. It is the corpus's only variable-rate source —
declared 59.94, actual 35.941. Phone cameras record VFR by default, so this is
a production cost on real uploads (1.9% of 1,776 jobs over 30 days), not a
fixture artifact.

fps_verdict IS EXTRACTED AND EXECUTED, not imported. Importing the app pulls its
whole module-level world — sibling modules, asset inventories, import-time
asserts — none of which is the thing under test, and it makes the check
unrunnable wherever those siblings do not resolve. Compiling the ONE function
keeps the derivation legs honest and portable.

  python3 smoke_vfr_normalised.py     exit 0 = normalised, or deliberately not
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

_ns = {}
_tree = ast.parse(SRC)
_fn = next((n for n in _tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "fps_verdict"), None)
if _fn is None:
    print("  [FAIL] fps_verdict is gone — the verdict this gate reads does not exist")
    sys.exit(1)
exec(compile(ast.Module([_fn], []), "<fps>", "exec"), _ns)
fps_verdict = _ns["fps_verdict"]

CASES = [
    ("motion   VFR phone footage", "60000/1001", "1004", "27.94", "VFR"),
    ("car_mid  CFR 30", "30/1", "414", "13.80", "CFR"),
    ("talking_head CFR 30", "30/1", "611", "20.36", "CFR"),
    ("no frame count", "30/1", None, "20.0", "UNMEASURED"),
    ("no duration", "30/1", "600", None, "UNMEASURED"),
    ("garbage rate", "not/a/rate", "600", "20.0", "UNMEASURED"),
]
for label, r, n, d, want in CASES:
    _dec, _act, _st = fps_verdict(r, n, d)
    ok(_st == want,
       f"{label}: state {_st!r}, expected {want!r} (declared={_dec} actual={_act})")

# UNMEASURED MUST NOT BE TREATED AS CFR — that is absence rendered as a value,
# and it would either leave a VFR source unnormalised or re-encode a good one.
_d, _a, _s = fps_verdict("30/1", None, "20.0")
ok(_s == "UNMEASURED" and _s != "CFR",
   "an unmeasurable frame rate reports CFR — a guess in the direction that "
   "hides the defect")

_w = SRC[SRC.index("# ── VFR NORMALISATION, ON INGEST"):]
_w = _w[:_w.index('print(f"  SOURCE FPS')]
ok('_fps_state == "VFR"' in _w,
   "normalisation is not gated on the VFR verdict — either every source is "
   "re-encoded (a generation of quality for nothing) or none is")
ok("fps_mode" in _w and "cfr" in _w,
   "the normalise command does not resample to a constant rate")
ok('"-c:a", "copy"' in _w,
   "audio is re-encoded during normalisation — the sound must be untouched")
ok("float(_actual)" in _w,
   "the target is not the MEASURED actual — resampling to the DECLARED rate "
   "normalises to the lie")
ok("vfr_normalise_failed" in _w,
   "a failed normalisation is silent — the job would proceed as though the "
   "source had been fixed")
ok('led["vfr_normalised"]' in SRC
   and "-> NORMALISED to CFR" in SRC,
   "the outcome never reaches the ledger and the log together")

print(f"VFR-NORMALISED  {len(CASES)} rate cases driven against fps_verdict")
if FAIL:
    for m in FAIL:
        print(f"  [FAIL] {m}")
    print(f"\n{len(FAIL)} failure(s)")
    sys.exit(1)
print("  VFR normalised to its actual rate, CFR untouched, UNMEASURED loud")
