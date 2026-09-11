#!/usr/bin/env python3
"""WHICH CONTROL SCHEME CAN SEE A SHORT LABEL?

The question the bar cannot answer on its own. Production's control is a
DIFFERENT WINDOW of the same before/after pair, so the delta carries the
difference between two unrelated moments' encode noise. This measures how big
that noise is against the signal a short label actually produces, and compares
it with a SAME-WINDOW control (the layer withheld, one extra render per run).

Ink is drawn with drawbox, not text — this ffmpeg has no drawtext. A label's
ink is a few thousand lit pixels inside the overlay box; the three coverages
below bracket that. The ABSOLUTE dB is not production's, and is not used to set
a bar. What transfers is the COMPARISON between the two control schemes, which
is a property of the metric and not of the ink.
"""
import glob, json, os, subprocess, sys
sys.path.insert(0, "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/.worktrees/mgfix")
import modal_stub; modal_stub.install()
import agentic_editor_app as A

OUT = os.path.dirname(os.path.abspath(__file__))
CLIPS = sorted(glob.glob("/Users/zaclibman/Desktop/EXAMPLES/*.mp4"))[:8]
BOX = (76, 280, 916, 1332)                      # the overlay box production used
PLACE = [(1.0, 1.5), (3.25, 3.75), (6.4, 6.9), (10.4, 10.9)]
CTRL = [(2.2, 2.7), (4.6, 5.1), (8.0, 8.5), (12.2, 12.7)]
FPS, DUR = 30, 14.0
# coverage of the 916x1332 box: a short label is ~1-2%, a full sentence ~4-6%
ARMS = {"null": 0.0, "ink_1pct": 0.01, "ink_2pct": 0.02, "ink_5pct": 0.05}


def sh(a):
    return subprocess.run(a, capture_output=True, text=True, timeout=300)


def prep(src, dst):
    return sh(["ffmpeg", "-y", "-v", "error", "-i", src, "-t", "%.2f" % DUR,
               "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
                      "crop=1080:1920,fps=%d" % FPS,
               "-c:v", "libx264", "-crf", "18", "-x264-params", "threads=48",
               "-preset", "veryfast", "-an", dst])


def layer(dst, coverage):
    """Ink via geq, NOT drawbox. drawbox does not write ALPHA: measured here,
    alpha max 0 over the whole frame, so every 'ink' layer came out fully
    transparent and all four arms returned byte-identical numbers. A fixture
    that silently produces the null for every arm is the most expensive kind —
    it reads as 'the metric cannot separate anything'."""
    _bx, _by, _bw, _bh = BOX
    if coverage <= 0:
        _a = "0"
    else:
        _h = 96                                  # a caption-sized band
        _w = min(_bw, max(8, int(_bw * _bh * coverage / _h)))
        _x0 = _bx + (_bw - _w) // 2
        _y0 = _by + int(_bh * 0.14)
        # TIME-GATED TO THE PLACEMENT WINDOWS. The first version drew the band
        # for the whole clip, so the CONTROL window carried the same ink as the
        # placement window and the difference cancelled — production's scheme
        # scored a median of -0.21 on a 5% band, which read as 'the metric
        # cannot see ink' when it was the fixture that could not present any.
        _when = "+".join("between(T,%.3f,%.3f)" % (a0, a1) for a0, a1 in PLACE)
        _a = ("if(between(Y,%d,%d)*between(X,%d,%d)*(%s),255,0)"
              % (_y0, _y0 + _h, _x0, _x0 + _w, _when))
    _vf = "format=rgba,geq=r='255':g='255':b='255':a='%s'" % _a
    return sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
               "-i", "color=c=white:s=1080x1920:r=%d:d=%.2f" % (FPS, DUR),
               "-vf", _vf, "-c:v", "qtrle", dst])


def composite(base, lay, dst):
    return sh(["ffmpeg", "-y", "-v", "error", "-i", base, "-i", lay,
               "-filter_complex", A.alpha_composite_filter(FPS), "-map", "[outv]",
               "-c:v", "libx264", "-crf", "18", "-x264-params", "threads=48",
               "-preset", "veryfast", dst])


def alpha_mean(p, at=None):
    """Alpha at a given instant. `at` matters once the ink is time-gated: frame
    1 sits outside every placement window, so a layer that DOES carry ink reads
    0.0 there and the ink-present assertion rejects a correct fixture."""
    _pre = ["-ss", "%.3f" % at] if at is not None else []
    r = subprocess.run(["ffmpeg", "-v", "error"] + _pre + ["-i", p, "-vf",
                        "alphaextract,scale=4:4", "-frames:v", "1",
                        "-f", "rawvideo", "-"], capture_output=True)
    d = r.stdout or b""
    return (sum(d[:16]) / 16.0) if d else None


rows = []
_null_lay = os.path.join(OUT, "L_null.mov")
_rc = layer(_null_lay, 0.0).returncode
_am = alpha_mean(_null_lay)
# `(alpha_mean(...) or 255) > 1.0` was the first version of this guard and it
# REFUSED THE CORRECT FIXTURE: a fully transparent layer measures 0.0, and
# `0.0 or 255` is 255 because 0.0 is falsy. The absent-as-zero family, running
# backwards — a real zero read as the sentinel — inside the guard written to
# catch a broken fixture. Three states, and ABSENT is not OPAQUE.
if _rc:
    print("FIXTURE FAILED: the null layer did not build"); sys.exit(2)
if _am is None:
    print("FIXTURE ABSENT: the layer's alpha could not be read — not the same "
          "thing as an opaque layer, and not a pass"); sys.exit(2)
if _am > 1.0:
    print("FIXTURE FAILED: the null layer is not transparent (alpha mean %.2f) "
          "— an opaque layer measures a black frame and calls it a null" % _am)
    sys.exit(2)
print("fixture ok: null layer alpha mean %.2f (0 = transparent)" % _am)

for ci, clip in enumerate(CLIPS):
    base = os.path.join(OUT, "cb%d.mp4" % ci)
    if prep(clip, base).returncode:
        continue
    # the SAME-WINDOW control needs the layer withheld: that IS the null composite
    null_comp = os.path.join(OUT, "cnull%d.mp4" % ci)
    if composite(base, _null_lay, null_comp).returncode:
        continue
    for arm, cov in ARMS.items():
        lay = _null_lay if cov == 0 else os.path.join(OUT, "L_%s.mov" % arm)
        if cov:
            if layer(lay, cov).returncode:
                continue
            _ia = alpha_mean(lay, at=(PLACE[0][0] + PLACE[0][1]) / 2.0)
            if _ia is None or _ia <= 0.0:
                print("  SKIP %s: the ink layer carries NO ink (alpha mean %s) "
                      "— measuring it would report the null under another name"
                      % (arm, _ia))
                continue
        comp = os.path.join(OUT, "c%s_%d.mp4" % (arm, ci))
        if composite(base, lay, comp).returncode:
            continue
        for (p0, p1), (c0, c1) in zip(PLACE, CTRL):
            _p = A.region_psnr(base, comp, p0, p1, box=BOX)
            _cd = A.region_psnr(base, comp, c0, c1, box=BOX)       # production: other window
            _cs = A.region_psnr(base, null_comp, p0, p1, box=BOX)  # proposed: same window, no layer
            rows.append({
                "arm": arm, "clip": os.path.basename(clip)[:18], "w": [p0, p1],
                "diff_window": None if (d := A.region_effect_delta(_p, _cd)) in (float("inf"), float("-inf"), None) else round(d, 3),
                "same_window": None if (s := A.region_effect_delta(_p, _cs)) in (float("inf"), float("-inf"), None) else round(s, 3)})

json.dump(rows, open(os.path.join(OUT, "ctrl_rows.json"), "w"), indent=1)
print("\n  %-10s %4s   %-28s %-28s" % ("arm", "n", "DIFF-WINDOW (production)", "SAME-WINDOW (proposed)"))
stats = {}
for arm in ARMS:
    d = sorted(r["diff_window"] for r in rows if r["arm"] == arm and r["diff_window"] is not None)
    s = sorted(r["same_window"] for r in rows if r["arm"] == arm and r["same_window"] is not None)
    stats[arm] = (d, s)
    f = lambda v: ("%7.2f .. %7.2f  med %6.2f" % (v[0], v[-1], v[len(v)//2])) if v else "no data"
    print("  %-10s %4d   %-28s %-28s" % (arm, len(d), f(d), f(s)))
for scheme, idx in (("DIFF-WINDOW", 0), ("SAME-WINDOW", 1)):
    n = stats["null"][idx]
    for arm in ("ink_1pct", "ink_2pct", "ink_5pct"):
        v = stats[arm][idx]
        if n and v:
            gap = min(v) - max(n)
            print("  %-11s %-9s gap to null = %7.2f dB  %s"
                  % (scheme, arm, gap, "SEPARATES" if gap > 0 else "OVERLAPS"))
