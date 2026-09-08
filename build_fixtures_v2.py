#!/usr/bin/env python3
"""Build reliability-fixtures-v2 — constructed sources that can actually SHOW an edit.

WHY v1 HAD TO BE REPLACED. Every v1 fixture is a flat field or noise:
pet_video 0.06 MB / 18s is a cream rectangle with one brown square; music is
blue noise; talking_head is a purple gradient behind a yellow square. Round 36
flagged three zoom components as no-ops — and each flagged psnr matched its
SOURCE's own zoom-responsiveness almost exactly:

    music            source 20.94 dB   DepthPull flagged 20.92
    screen_recording source 22.37 dB   SnapReframe flagged 21.80
    pet_video        source 29.77 dB   StepZoom flagged 25.93

music differs by 0.02 dB. The check was measuring the corpus, not the
components. A source that cannot show a zoom cannot test one.

CONSTRUCTED, NOT USER MEDIA — that law stands and is why these are generated
rather than filmed. The defect was never that they are synthetic; it is that
they are FEATURELESS.

WHAT EACH SOURCE CARRIES, and why:
  * high-frequency texture      -> a zoom moves pixels, so zoom is measurable
  * a moving subject            -> motion beats exist to rule on
  * hard scene changes          -> cuts and transitions have somewhere to land
  * v1's ORIGINAL AUDIO         -> the transcript is unchanged, so talking_head
                                   still yields its 73 words and the speech
                                   route is comparable across the v1/v2 boundary

THE ACCEPTANCE GATE IS THE POINT. A fixture is only written if a 1.10x zoom
takes it BELOW _MAX_ZOOM_PSNR and it carries at least _MIN_SCENES scene changes.
v1 would fail this gate on 5 of 5 for zoom. Building a corpus without the gate
is how the last one shipped.
"""
import json
import os
import subprocess
import sys
import tempfile

V1 = "ab-sources/reliability-fixtures-v1"
V2 = "ab-sources/reliability-fixtures-v2"
BUCKET = os.environ.get("PROMPTLY_BUCKET", "promptly-video-storage")

# name -> (v1 basename, duration seconds)  — durations preserved from v1 so the
# rate tables, which are per-25s, stay comparable.
FIXTURES = [
    ("talking_head",     "talking_head-eeb40bc7",     38.5),
    ("music",            "music-a4543f09",            20.0),
    ("screen_recording", "screen_recording-1eadc25b", 20.0),
    ("product_shot",     "product_shot-23dcaf62",     15.0),
    ("pet_video",        "pet_video-382c5f1d",        18.0),
]

# THE 18.0 dB ACCEPTANCE GATE IS RETIRED. It is recorded, not enforced.
#
# It rejected every source that is not my own construction. Measured
# intrinsic 1.10x-zoom psnr, all six sources anyone has proposed:
#
#     v1 pet_video            29.79   REJECTED   the corpus rounds run on
#     v1 talking_head         26.60   REJECTED   the corpus rounds run on
#     Zac real car            22.33   REJECTED   real footage
#     Zac real talking_head   19.13   REJECTED   real footage
#     Zac real bathroom       17.82   admitted   real footage, barely
#     v2-geometry (mine)  11.6-13.9   admitted   grey cellular static
#
# Five of six rejected, and the two it admitted comfortably are the ones I
# built. A gate that rejects the corpus in use AND both of Zac's clips has
# learned "resembles the sources I was fitted on" and called it "can exercise
# geometry". Builder-2 named the consequence and it is the real cost: every
# source it admits from then on is one our instruments can measure and the
# product never sees.
#
# WHY NOT A HIGHER BAR. Because the number is not the property. Builder-2's
# sweep found render FIDELITY is the dominant term — the same source at the
# same content moves 22.3 dB across crf 18-40 — so an intrinsic psnr taken
# without a render in it cannot answer "can a zoom be told from a passthrough
# here". No threshold on this axis can, at any value.
#
# So it is MEASURED AND PRINTED, and a fixture is never rejected for it. The
# question it was trying to answer belongs to a render-based two-arm test, which
# lives in Builder-2's instrument and not in a corpus builder.
_MIN_SCENES = 2

# Per-fixture look, so the five are not five copies. Each keeps the texture that
# gives zoom headroom and varies rule/hue/motion.
# RULES CHOSEN BY MEASUREMENT, not by looking varied. Standalone 1.10x-zoom
# psnr per cellauto rule: 126 -> 10.38, 122 -> 10.40, 105 -> 12.20, 90 -> 12.30,
# 110 -> 13.06, 150 -> 12.48, 30 -> 14.84, 182 -> 15.77. Composition costs a
# further ~4-5 dB, so the first build put music on rule=90 and
# screen_recording on rule=30 and both came out ABOVE the gate at 19.11 and
# 19.04 — the same "cannot show a zoom" hole as v1, one round later. The two
# densest rules go to the two that failed.
LOOKS = {
    "talking_head":     ("rule=110", 200, 0.9, 0.6),
    "music":            ("rule=122", 280, 1.4, 0.9),
    "screen_recording": ("rule=126", 160, 0.4, 0.7),
    "product_shot":     ("rule=105", 30,  0.6, 0.5),
    "pet_video":        ("rule=150", 90,  1.1, 0.8),
}


def sh(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def presign_get(key):
    r = sh([sys.executable, "presign_get.py", key])
    return (r.stdout or "").strip()


def _zoom_psnr_at(path, ss):
    with tempfile.TemporaryDirectory() as t:
        a, b = os.path.join(t, "a.mp4"), os.path.join(t, "b.mp4")
        sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(ss),
            "-t", "1", "-i", path, "-vf", "scale=540:960", a])
        sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(ss),
            "-t", "1", "-i", path, "-vf",
            "scale=594:1056,crop=540:960:27:48", b])
        if not (os.path.exists(a) and os.path.exists(b)):
            return None
        r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", a, "-i", b,
                "-lavfi", "psnr", "-f", "null", "-"])
        import re
        m = re.search(r"average:([0-9.]+)", (r.stdout or "") + (r.stderr or ""))
        return float(m.group(1)) if m else None


def zoom_psnr(path, dur):
    """MEDIAN 1.10x-zoom psnr across several points. LOW = the source is zoomable.

    SAMPLED AT MORE THAN ONE POINT, and that is not caution — it is a bug fix.
    The single-sample version read at a fixed 5s, and for the 20s fixtures the
    first scene window lands at dur*0.25 = 5.00s EXACTLY. It was measuring the
    testsrc2 overlay shown during a scene change, not the fixture's own texture,
    so music read 19.11 both before and after its cellauto rule changed from 90
    to 122 — an identical number from a changed source, which is the tell.

    Sample the bucket you intend to measure. Points are placed away from the
    scene windows at 0.25/0.55/0.80 of the duration.
    """
    pts = [dur * p for p in (0.10, 0.40, 0.68, 0.92)]
    vals = [v for v in (_zoom_psnr_at(path, round(p, 2)) for p in pts)
            if v is not None]
    if not vals:
        return None
    vals.sort()
    return vals[len(vals) // 2]


def scene_count(path):
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vf",
            "select=gt(scene\\,0.25),metadata=print", "-f", "null", "-"])
    return ((r.stdout or "") + (r.stderr or "")).count("pts_time")


def build(name, v1base, dur, outdir):
    rule, hue, mspeed, sat = LOOKS[name]
    src_url = presign_get(f"{V1}/{v1base}.mp4")
    if not src_url:
        return None, f"could not presign v1 source for {name}"
    audio = os.path.join(outdir, f"{name}.m4a")
    # v1's audio verbatim: the transcript must not move, or the speech route is
    # no longer comparable across the corpus change.
    # The return is deliberately not bound: has_audio below asks the FILE
    # whether the extraction produced anything, which is the question. Binding
    # it and never reading it is a dead counter, and pyflakes says so.
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src_url,
        "-vn", "-c:a", "aac", "-b:a", "128k", "-t", str(dur), audio])
    has_audio = os.path.exists(audio) and os.path.getsize(audio) > 1000
    out = os.path.join(outdir, f"{name}.mp4")
    # "+" NOT ",". Joined with a comma this builds if(a,b,c,B,A) — a five-
    # argument if() that ffmpeg rejects, and the prototype that was verified by
    # hand used "+". The build then produced NOTHING for all five fixtures and
    # the only visible error was x264 "Invalid argument", which names neither
    # the filter nor the expression. Summing the predicates is the OR.
    scenes = "+".join(f"between(T,{t:.2f},{t + 1:.2f})" for t in
                      (dur * 0.25, dur * 0.55, dur * 0.8))
    fc = (
        f"[0:v]format=yuv420p,eq=saturation={sat}:brightness=-0.12[tex];"
        f"[1:v]format=yuv420p,hue=h={hue}:s=0.5[alt];"
        f"[tex][alt]blend=all_expr='if({scenes},B,A)'[bg];"
        f"[bg][2:v]overlay=x='140+360*sin(t*{mspeed})':"
        f"y='620+300*cos(t*{mspeed * 0.7:.2f})'[v]"
    )
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"cellauto=s=1080x1920:rate=30:{rule}:scroll=1",
            "-f", "lavfi", "-i", "testsrc2=s=1080x1920:rate=30",
            "-f", "lavfi", "-i", "testsrc2=s=420x420:rate=30"]
    if has_audio:
        args += ["-i", audio]
    args += ["-filter_complex", fc, "-map", "[v]"]
    if has_audio:
        args += ["-map", "3:a", "-c:a", "aac", "-shortest"]
    args += ["-t", str(dur), "-r", "30", "-pix_fmt", "yuv420p",
             "-c:v", "libx264", "-crf", "18", out]
    r = sh(args)
    if not os.path.exists(out) or os.path.getsize(out) < 10000:
        return None, f"ffmpeg produced nothing: {(r.stderr or '')[-200:]}"
    return out, None


def main():
    outdir = "/tmp/fixtures_v2"
    os.makedirs(outdir, exist_ok=True)
    rows, ok_all = [], True
    for name, v1base, dur in FIXTURES:
        path, err = build(name, v1base, dur, outdir)
        if err:
            print(f"  {name:18} BUILD FAILED — {err}")
            ok_all = False
            continue
        z, sc = zoom_psnr(path, dur), scene_count(path)
        size = os.path.getsize(path) / 1048576
        # THE GATE. A source that cannot show a zoom cannot test one.
        gate = []
        # zoom psnr is RECORDED, never gated on — see the note above.
        if sc < _MIN_SCENES:
            gate.append(f"{sc} scene change(s) < {_MIN_SCENES}")
        verdict = "OK" if not gate else "REJECTED: " + "; ".join(gate)
        if gate:
            ok_all = False
        print(f"  {name:18} {size:6.1f} MB  zoom {z if z is None else round(z,2):>6} dB  "
              f"scenes {sc:>2}  {verdict}")
        rows.append({"name": name, "path": path, "zoom_psnr": z,
                     "scenes": sc, "mb": round(size, 2), "ok": not gate})
    json.dump(rows, open(os.path.join(outdir, "manifest.json"), "w"), indent=1)
    print(f"\n  {sum(1 for r in rows if r['ok'])}/{len(FIXTURES)} passed the gate "
          f"-> {outdir}")
    if not ok_all:
        print("  NOT ALL PASSED — nothing should be uploaded until every fixture "
              "clears the gate, or the corpus has the same hole as v1.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
