"""F4 caption width-fit guarantee — the permanent "never again" pin.

Renders EVERY caption style (+ the sticky_note overlay renderer) with
worst-case strings through the REAL components (FitSpecimen composition,
strict fit invariant armed: any post-fit overflow throws inside the render
and the still fails), then pixel-scans each frame's horizontal margins.

Bar: no text pixel outside the safe text region derived from the safe-zone
single source of truth (H_TEXT_MARGIN=80 → x ∈ [80, 1000]). An 8px grace
absorbs soft glow/shadow diffusion (glows are not glyphs); a hard frame-edge
scan (x<8 / x>=1072) tolerates nothing.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
REMOTION = os.path.join(REPO, "src", "remotion")
OUT = os.path.join(REMOTION, "fit-battery-out")

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


print("=== B1: render the battery (strict invariant armed in-browser) ===")
r = subprocess.run(["node", "fit-battery.mjs", OUT], cwd=REMOTION,
                   capture_output=True, text=True, timeout=1200)
tail = (r.stdout + r.stderr)
print("\n".join(l for l in tail.splitlines() if l.startswith(("STILL_", "BATTERY_", "[caption-fit]"))))
check("battery rendered with zero strict-invariant failures",
      r.returncode == 0 and "failed=0" in tail, tail[-400:])

print("\n=== B2: pixel-scan every still's margins ===")
try:
    from PIL import Image
except ImportError:
    check("PIL available", False, "pip install pillow")
    Image = None

H_MARGIN = 80
GRACE = 8            # soft glow/shadow allowance inside the margin band
GLOW_THRESHOLD = 40  # brightness above this in the margin band = glyph, not glow
EDGE_THRESHOLD = 24  # near the frame edge, tolerate nothing bright

if Image is not None and os.path.isdir(OUT):
    stills = sorted(f for f in os.listdir(OUT) if f.endswith(".png"))
    check("battery produced stills for every case", len(stills) >= 47,
          f"got {len(stills)}")
    for f in stills:
        img = Image.open(os.path.join(OUT, f)).convert("RGB")
        w, h = img.size
        px = img.load()
        # StickyNotes cards legally occupy x∈[~72,~1004] after their designed
        # rotations — for those stills the band sits outside any card corner
        # and catches only text ESCAPING a card toward the frame edge.
        left_bar = 60 if f.startswith("StickyNotes") else H_MARGIN - GRACE
        right_bar = (w - 60) if f.startswith("StickyNotes") else (w - H_MARGIN + GRACE)
        worst_margin = 0
        worst_edge = 0
        for y in range(0, h, 2):
            for x in list(range(0, left_bar)) + list(range(right_bar, w)):
                v = max(px[x, y])
                if v > worst_margin:
                    worst_margin = v
            for x in list(range(0, 8)) + list(range(w - 8, w)):
                v = max(px[x, y])
                if v > worst_edge:
                    worst_edge = v
        ok = worst_margin <= GLOW_THRESHOLD and worst_edge <= EDGE_THRESHOLD
        check(f"margins clean: {f}", ok,
              f"margin_max={worst_margin} edge_max={worst_edge}")

print("\n=== B3: wiring pins — the fit layer is in every text renderer ===")
CAPTIONS = ["CleanCut", "Cove", "Gadzhi", "Lumen", "Prime", "Pulse",
            "Quintessence", "TwoTone", "TypewriterReveal"]
for style in CAPTIONS:
    src = open(os.path.join(REMOTION, "src", "captions", style, f"{style}.tsx")).read()
    check(f"{style} imports the shared fit layer", 'from "../shared/fit"' in src)
sticky = open(os.path.join(REMOTION, "src", "motion-graphics", "StickyNotes", "StickyNotes.tsx")).read()
check("StickyNotes (sticky_note overlay) uses the shared measurer",
      'from "../../captions/shared/fit"' in sticky)
fit_src = open(os.path.join(REMOTION, "src", "captions", "shared", "fit.ts")).read()
check("SAFE_TEXT_WIDTH derives from the safe-zone source of truth",
      "TIKTOK_SAFE_SIDE" in fit_src and "CANVAS_WIDTH - 2 * H_TEXT_MARGIN" in fit_src)
check("MIN_FIT_SCALE floor is 0.6", "MIN_FIT_SCALE = 0.6" in fit_src)
check("prod invariant clamps+logs; strict throws",
      "REMOTION_FIT_STRICT" in fit_src and "INVARIANT VIOLATION" in fit_src)
root_src = open(os.path.join(REMOTION, "src", "Root.tsx")).read()
check("FitSpecimen composition registered", 'id="FitSpecimen"' in root_src)

print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
