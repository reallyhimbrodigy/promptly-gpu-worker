"""FINDING 1 (MG-over-face, Zac 2026-07-12) — a graphic NEVER covers the speaker's
face. The face is now a rigid band occupant in _compose_band_occupancy, so an MG
authored on the face band is RELOCATED (move-not-drop) to the clear band. Fixes the
talking-head case where zone=upper misled the anchor to center while the face body
fills the center band."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def face_at(cy, t0=0.0, t1=5.0, step=0.1):
    n = int((t1 - t0) / step) + 1
    return [{"found": True, "cy": cy, "t": round(t0 + i * step, 2)} for i in range(n)]

# ── _face_occupied_bands: the face's band from its cy ──
check("talking-head face (cy=960, frame center) occupies CENTER band",
      H._face_occupied_bands(face_at(960), 0.0, 2.0) == {"center"})
check("high face (cy=380) occupies TOP band (not center)",
      "top" in H._face_occupied_bands(face_at(380), 0.0, 2.0))
check("no face data → empty (fail-open, no forced avoidance)",
      H._face_occupied_bands([], 0.0, 2.0) == set())
check("face outside the interval window → empty",
      H._face_occupied_bands(face_at(960, t0=10.0, t1=12.0), 0.0, 2.0) == set())

# ── composer: an MG authored on the face band is RELOCATED off it ──
# MG anchored center for frames [0,120); face fills center the whole time.
FPS = 60.0
mgs = [{"type": "StatCard", "fromFrame": 0, "durationInFrames": 120, "props": {"anchor": "center"}}]
_composed = H._compose_band_occupancy(
    [], mgs, [], [], shadow=False, face_trajectory=face_at(960, 0.0, 3.0), source_fps=FPS)
_mg_bands = {band for (_a, _b, band) in (_composed["element_bands"].get("mg0") or [])}
check("MG authored on the face (center) is NOT rendered at center",
      "center" not in _mg_bands, _mg_bands)
check("MG relocated to a real clear band (top or bottom), not dropped",
      _mg_bands and _mg_bands <= {"top", "bottom"}, _mg_bands)

# apply step writes the moved band back to props.anchor
_km, _ko, _mv, _dp = H._apply_composed_accent_bands(mgs, [], _composed["element_bands"])
check("applied: the MG's anchor moved OFF center (never covers the face)",
      _km and _km[0]["props"]["anchor"] != "center", _km[0]["props"]["anchor"] if _km else None)

# no face → MG keeps its authored center (fail-open, nothing forced)
_c2 = H._compose_band_occupancy([], [{"type": "StatCard", "fromFrame": 0, "durationInFrames": 120, "props": {"anchor": "center"}}],
                                [], [], shadow=False, face_trajectory=[], source_fps=FPS)
_b2 = {band for (_a, _b, band) in (_c2["element_bands"].get("mg0") or [])}
check("no face data → MG keeps authored center (fail-open)", _b2 == {"center"}, _b2)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL MG-FACE-AVOIDANCE CASES PASS")
