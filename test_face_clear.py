"""Face-cover validator (PR-γ) — behavioral tests on the real helper."""
import contextlib
import io
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def traj(cy, t0=0.0, t1=5.0, n=6, found=True):
    return [{"t": t0 + i * (t1 - t0) / (n - 1), "cx": 540.0, "cy": cy, "found": found}
            for i in range(n)]

print("=== FC1: face in the center band + center anchor -> coerced away ===")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    band, applied = H._face_clear_anchor("center", 1.0, 3.0, traj(960.0), component="mg:StatCard")
o = buf.getvalue()
check("coerced", applied is True and band in ("top", "bottom"), str((band, applied)))
check("divergence action=face_clear_coerce", "face_clear_coerce" in o and "[divergence]" in o)
check("lesser-overlap alternative picked", band in ("top", "bottom"))

print("\n=== FC2: clear anchor untouched ===")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    band, applied = H._face_clear_anchor("top", 1.0, 3.0, traj(1400.0))
check("face low + top anchor -> unchanged", band == "top" and applied is False)
check("zero divergence lines", "face_clear_coerce" not in buf.getvalue())

print("\n=== FC3: fail-open — no face data / no samples in window / junk ===")
band, applied = H._face_clear_anchor("center", 1.0, 3.0, [])
check("empty trajectory -> passthrough", band == "center" and not applied)
band, applied = H._face_clear_anchor("center", 100.0, 103.0, traj(960.0))
check("no samples in window -> passthrough", band == "center" and not applied)
band, applied = H._face_clear_anchor("center", 1.0, 3.0, traj(960.0, found=False))
check("found=False coasting samples -> passthrough", band == "center" and not applied)
band, applied = H._face_clear_anchor("weird_band", 1.0, 3.0, traj(960.0))
check("unknown band -> passthrough", band == "weird_band" and not applied)
band, applied = H._face_clear_anchor("center", 1.0, 3.0, ["junk", None])
check("junk entries never raise", band == "center" and not applied)

print("\n=== FC4: face high in frame -> top coerces DOWN, bottom stays ===")
with contextlib.redirect_stdout(io.StringIO()):
    band, applied = H._face_clear_anchor("top", 1.0, 3.0, traj(420.0))
check("top over a high face coerces", applied is True and band in ("center", "bottom"), str(band))
band, applied = H._face_clear_anchor("bottom", 1.0, 3.0, traj(420.0))
check("bottom clear of the high face -> unchanged", band == "bottom" and not applied)

print("\n=== FC5: wire pins — all three resolution sites call the validator ===")
src = open("handler.py").read()
check("main MG site", 'component=f"mg:{_mg.get(\'type\')}"' in src)
check("emphasis MG site", 'component=f"emphasis-mg:' in src)
check("text overlay site", 'component=f"text_overlay:' in src)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL FACE-CLEAR CASES PASS")
