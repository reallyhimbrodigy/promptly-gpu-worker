"""FINDING 1 (cross-type collision, Zac 2026-07-12) — MOVE-NOT-DROP. Two accents
(MG vs overlay, MG vs MG) must never occupy the same band. The composer computes
disjoint bands (MG keeps its spot, the loser re-bands); _apply_composed_accent_bands
APPLIES that — relocating the loser, dropping only when no band is free."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

# COLLISION: MG wants center, overlay wants center — composer gives MG center, overlay top.
mgs = [{"type": "StatCard", "props": {"anchor": "center"}}]
overlays = [{"variant": "caption_match", "position": "center"}]
eb = {"mg0": [(0, 60, "center")], "to0": [(0, 60, "top")]}
_km, _ko, _mv, _dp = H._apply_composed_accent_bands(mgs, overlays, eb)
check("MG keeps its spot (center)", _km[0]["props"]["anchor"] == "center", _km[0]["props"]["anchor"])
check("overlay MOVED to its alternate (top), not dropped", _ko and _ko[0]["position"] == "top", _ko)
check("one move, zero drops", _mv == 1 and _dp == 0, (_mv, _dp))

# NO COLLISION: bands already disjoint → no change, no divergence
mgs2 = [{"type": "StatCard", "props": {"anchor": "center"}}]
ov2 = [{"variant": "caption_match", "position": "top"}]
eb2 = {"mg0": [(0, 60, "center")], "to0": [(0, 60, "top")]}
_k2, _o2, _mv2, _dp2 = H._apply_composed_accent_bands(mgs2, ov2, eb2)
check("disjoint accents unchanged", _mv2 == 0 and _dp2 == 0 and _o2[0]["position"] == "top")

# DROP only when no free band (rigid top-pinned collision the composer couldn't place)
mgs3 = [{"type": "Notification", "props": {"anchor": "top"}}]
eb3 = {"mg0": [(0, 60, "dropped_collision")]}
_k3, _o3, _mv3, _dp3 = H._apply_composed_accent_bands(mgs3, [], eb3)
check("no-free-band accent is DROPPED (unavoidable rigid collision)", _dp3 == 1 and _k3 == [], (_dp3, _k3))

# MG-vs-MG: the composer's priority resolved it; we just apply (loser re-bands)
mgs4 = [{"type": "StatCard", "props": {"anchor": "center"}}, {"type": "BarRace", "props": {"anchor": "center"}}]
eb4 = {"mg0": [(0, 60, "center")], "mg1": [(0, 60, "top")]}
_k4, _o4, _mv4, _dp4 = H._apply_composed_accent_bands(mgs4, [], eb4)
check("MG-vs-MG: first keeps center, second moved to top", _k4[0]["props"]["anchor"] == "center" and _k4[1]["props"]["anchor"] == "top")

# overlay never lands in the caption home (bottom → top)
eb5 = {"to0": [(0, 60, "bottom")]}
_k5, _o5, _mv5, _dp5 = H._apply_composed_accent_bands([], [{"variant": "caption_match", "position": "top"}], eb5)
check("overlay assigned bottom is coerced to top (never the caption home)", _o5[0]["position"] == "top")

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL CROSS-TYPE-COLLISION CASES PASS")
