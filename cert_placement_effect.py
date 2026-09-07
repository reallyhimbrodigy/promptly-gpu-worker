#!/usr/bin/env python3
"""CERT: a declared placement must produce the effect it CLAIMS.

THE MOST EXPENSIVE FALSE GREEN OF THIS LANE. Every zoom in every round of this
corpus was inert. The shipped filtergraph travelled 0.2% of frame where it
claimed 12%, and anchored at (-169, 38) — off-frame, diagonally. Three of five
fixtures in round 26 declared zoom as their ONLY family with kept=1.0, so they
shipped VISUALLY UNCHANGED VIDEO and scored ok=True with placements above zero.

Why nothing caught it:
  * the passthrough leg requires placements == 0, and these declared 1-2;
  * the manifest counts DECLARATIONS, and the declaration was honest — the
    pipeline genuinely asked for a zoom, it just never got one;
  * no log line differs between a 1.002x zoom and a 1.12x one.

AND A GENERIC BEFORE/AFTER DIFF WOULD NOT HAVE CAUGHT IT EITHER. Measured on the
same pattern, PSNR against the source:

    INERT zoom (1.002x)   33.46 dB     <-- indistinguishable from real
    REAL zoom  (1.118x)   31.19 dB
    SmoothPush            30.77 dB
    re-encode, no change  68.25 dB

A 1.002x scale still shifts every pixel, and on detailed content that reads as a
large diff. "Something changed" is not "the claimed thing happened", and a check
that only asserted the former would have been the fifth false green in this
lane, shipped as the fix for the fourth.

So this cert renders the SHIPPED filtergraph — imported, never copied, the same
reason spec_shortfall was hoisted — on a constructed static pattern where the
ONLY possible motion is the transform under test, and measures the geometry.
"""
import os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import types as _t
_m = _t.ModuleType("modal")
class _S:
    def __init__(s, *a, **k): pass
    def __getattr__(s, n): return _S()
    def __call__(s, *a, **k): return _S()
    def function(s, *a, **k): return lambda f: f
    def local_entrypoint(s, *a, **k): return lambda f: f
for _n in ("App", "Image", "Secret", "Volume", "Cls", "Function"):
    setattr(_m, _n, _S())
_m.is_local = lambda: True; _m.enable_output = _S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A       # THE SHIPPED MODULE

try:
    import numpy as np
    from PIL import Image, ImageDraw
except ImportError:
    print("CERT-PLACEMENT-EFFECT: SKIP (numpy/PIL absent — cannot measure geometry)")
    sys.exit(0)

if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
    print("CERT-PLACEMENT-EFFECT: SKIP (no ffmpeg)")
    sys.exit(0)

W, H, FPS, SECS = 1080, 1920, 30, 3
MARKS = [(270, 480), (810, 480), (270, 1440), (810, 1440)]

def _pattern(path):
    """A STATIC source: every pixel that moves, moved because of the transform."""
    im = Image.new("RGB", (W, H), (8, 8, 8))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill=(40, 40, 40))
    for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=(40, 40, 40))
    for (x, y) in MARKS: d.ellipse([x-9, y-9, x+9, y+9], fill=(255, 255, 255))
    png = path + ".png"
    im.save(png)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", png,
                    "-t", str(SECS), "-r", str(FPS), "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-crf", "12", path],
                   check=True, capture_output=True)

def _marker_width(png):
    a = np.asarray(Image.open(png).convert("RGB")).astype(np.int16)
    m = (a[:, :, 0] > 200) & (a[:, :, 1] > 200) & (a[:, :, 2] > 200)
    xs = np.nonzero(m)[1]
    if len(xs) < 20: return None
    return float(xs.max() - xs.min())

def _scale_curve(mp4, tmp):
    d = os.path.join(tmp, "fr"); os.makedirs(d, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp4, "-vsync", "0",
                    os.path.join(d, "f%03d.png")], check=True, capture_output=True)
    fs = sorted(os.listdir(d))
    ws = [_marker_width(os.path.join(d, f)) for f in fs]
    ws = [w for w in ws if w]
    return [w / ws[0] for w in ws] if ws else []

fails = []
with tempfile.TemporaryDirectory() as tmp:
    src = os.path.join(tmp, "pattern.mp4")
    _pattern(src)

    # ── ZOOM: the geometry must match the CLAIM ────────────────────────────
    T0, T1, Z = 1.0, 3.0, 1.12
    fg = A.zoom_filtergraph(T0, T1, Z)          # the SHIPPED string
    out = os.path.join(tmp, "zoomed.mp4")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                        "-filter_complex", fg, "-map", "[outv]",
                        "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        fails.append(f"zoom filtergraph failed to render: {(r.stderr or '')[-200:]}")
    else:
        curve = _scale_curve(out, tmp)
        if not curve:
            fails.append("zoom: could not measure the marker geometry")
        else:
            peak = max(curve)
            want = Z - 1.0
            got = peak - 1.0
            # AT LEAST 90% OF THE CLAIMED TRAVEL. The inert expression reached
            # 1.5% of it (0.0018 of 0.12) and would fail on any bar at all; the
            # bar is high because the tolerance that matters is the eye's.
            if got < 0.90 * want:
                fails.append(
                    f"zoom claims {Z:.3f}x but reaches {peak:.4f}x — "
                    f"{100*got/want:.1f}% of the claimed travel. THE PLACEMENT IS INERT.")
            # ── THE DWELL, WHICH IS THE WHOLE POINT ────────────────────
            # handler.py's zoom teach: "The commitment IS the dwell, not the
            # arrival speed... one that cuts away the instant it lands does not,
            # however slowly it came." The old shape reached peak at t=1.9s of a
            # 2.0s window — it landed and the window ended, the literal
            # disqualified case. Peak must arrive EARLY and be HELD.
            n0, n1 = int(T0*FPS), int(T1*FPS)
            win = curve[n0:n1]
            if win:
                pk = max(win)
                first_peak = next(i for i, v in enumerate(win) if v >= pk - 0.002)
                frac = first_peak / max(1, len(win))
                if frac > 0.55:
                    fails.append(
                        f"zoom reaches its peak {100*frac:.0f}% into the window — "
                        f"it lands as the window ends and never holds. "
                        f"Production ramps in {100*A.ZOOM_RAMP_FRACTION:.0f}%.")
                # HELD THROUGH TO THE CUT, not released before it.
                tail = win[int(0.85*len(win)):]
                if tail and min(tail) < pk - 0.01:
                    fails.append(
                        f"zoom releases before the cut (tail {min(tail):.4f} vs "
                        f"peak {pk:.4f}) — the landed state is not held through")
            # MONOTONIC: a push that goes backwards is a lurch.
            ramp = curve[int(T0*FPS):int(T1*FPS)]
            backs = sum(1 for i in range(1, len(ramp)) if ramp[i] < ramp[i-1] - 1e-6)
            if backs > 1:
                fails.append(f"zoom reverses on {backs} frames — not a monotonic push")
            # ANCHORED AT THE CENTRE, not a corner. With a centre-anchored zoom
            # the marker bounding box stays centred; a corner anchor drags it.
            d2 = os.path.join(tmp, "fr")
            last = sorted(os.listdir(d2))[-1]
            a2 = np.asarray(Image.open(os.path.join(d2, last)).convert("RGB")).astype(np.int16)
            m2 = (a2[:, :, 0] > 200) & (a2[:, :, 1] > 200) & (a2[:, :, 2] > 200)
            ys2, xs2 = np.nonzero(m2)
            cx, cy = xs2.mean(), ys2.mean()
            if abs(cx - W/2) > 40 or abs(cy - H/2) > 40:
                fails.append(
                    f"zoom anchors at ({cx:.0f}, {cy:.0f}), not the frame centre "
                    f"({W//2}, {H//2}) — it is drifting, not pushing in")

# ── THE RAMP FRACTION IS PRODUCTION'S, AND MUST NOT DRIFT ──────────────────
# It is not a taste parameter to pick. handler.py:
#   ZOOM_PEAK_REACH_MS["SmoothPush"] = 420   # 35% x 1200ms (ramp-in end)
# My first version used 40% because it made the point; that was a guess and is
# exactly the kind of invented constant that silently becomes doctrine.
import re as _re
_hp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "handler.py")
if os.path.exists(_hp):
    _hs = open(_hp, encoding="utf-8", errors="ignore").read()
    _m = _re.search(r'"SmoothPush":\s*(\d+),\s*#\s*(\d+)%\s*.\s*(\d+)ms', _hs)
    if not _m:
        fails.append("could not read ZOOM_PEAK_REACH_MS['SmoothPush'] from handler.py "
                     "— the ramp fraction is unverifiable, which is not a pass")
    else:
        _reach, _pct, _natural = int(_m.group(1)), int(_m.group(2)), int(_m.group(3))
        _want = _reach / _natural
        if abs(A.ZOOM_RAMP_FRACTION - _want) > 0.005:
            fails.append(
                f"ZOOM_RAMP_FRACTION is {A.ZOOM_RAMP_FRACTION} but production's "
                f"SmoothPush reaches peak at {_reach}/{_natural} = {_want:.3f} "
                f"({_pct}%) — the agentic shape has drifted from the doctrine it cites")
else:
    fails.append("handler.py not found — cannot verify the ramp fraction against production")

if fails:
    print(f"CERT-PLACEMENT-EFFECT: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("CERT-PLACEMENT-EFFECT: PASS — the zoom reaches its claimed travel, "
      "monotonically, anchored at the centre")
