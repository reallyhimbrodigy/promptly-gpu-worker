"""REGRESSION CERT — INTEGRITY_TRIP residual black families (W1-FIX-DEEP).

Reconstructs, at the ffmpeg level, the three FAITHFUL-render geometries that
produced the 7 residual "genuine" black trips (25-job forensic sweep,
2026-07-25), and proves with the REAL gate functions that:

  PRE-FIX  (masks/echo without the fix's knowledge): each geometry TRIPS —
           the reconstruction is non-vacuous, it is the failing geometry.
  POST-FIX (the shipped masks/echo): each geometry passes CLEAN, and the
           last real frame is preserved (the fix masks the gate, it never
           trims or alters the render).
  NEGATIVE: a genuine render-written black hole (bright source, black
           output span outside every designed window) STILL TRIPS — the
           gate is not weakened into vacuity.

Families (evidence: forensics/{job}/output.mp4 + integrity/{job}.json +
raw sources, all measured locally):
  1. outro fade_black — jobs 270d756a, 2f5e1b2f, acf712cf, fb141d88.
     Sources hold constant luma to the last frame; outputs ramp smoothly to
     black across exactly the 1.0s fade window (ffmpeg_base fade=t=out).
     Frame counts exact (1919/1919, 1782/1782). The plan's own designed
     outro was tripping the plan's own gate.
  2. dark B-roll content — job df1fa136. Black spans wholly inside the
     B-roll window (keyword "cinematic glowing smartphone screen in dark
     room"). Non-source pixels, chosen deliberately — same doctrine as the
     freeze mask, which already masks B-roll.
  3. dark source SCENE under designed framing — jobs 3bfc7b63 + 91150d15
     (same source). Night-metro scene, canonical-crop YAVG ~28: blackdetect
     on the source finds NOTHING (bright lights >2% of pixels) while the
     render's tighter zoom framing legitimately reads black. The echo needs
     mean-luma, not blackdetect, for scenes.

Run locally: python3 cert_integrity_black_families.py
Exits 0 on full PASS, 1 on any failure.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handler  # noqa: E402
from ffmpeg_base import OUTRO_FADE_DUR_S  # noqa: E402

FPS = 60
_results = []


def _run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{p.stderr[-800:]}")
    return p


def _probe(path):
    p = _run(["ffprobe", "-v", "quiet", "-select_streams", "v:0",
              "-count_frames", "-show_entries",
              "stream=duration,nb_read_frames", "-of", "csv=p=0", path])
    dur_s, nb = p.stdout.strip().split(",")[:2]
    return float(dur_s), int(nb)


def _gate(output, v_dur, nb, expected, masks, source=None, out_to_src=None):
    return handler._integrity_gate(
        output, v_dur, v_dur, expected, nb, float(FPS), masks,
        source_path=source, out_to_src=out_to_src)


def check(label, cond, detail=""):
    _results.append((label, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="cert_ig_black_")
    print(f"[cert] workspace: {tmp}")

    # ── Family 1: outro fade_black ─────────────────────────────────────────
    # Bright moving source, 8s. Output = source + the EXACT fade the render
    # emits (ffmpeg_base: fade=t=out:st=total-OUTRO_FADE_DUR_S:d=OUTRO_FADE_DUR_S:c=black).
    print("\n[cert] Family 1 — outro fade_black tail")
    src1 = os.path.join(tmp, "f1_src.mp4")
    out1 = os.path.join(tmp, "f1_out.mp4")
    # luma scaled to realistic phone-footage levels (convicted sources hold
    # mean 41-56): a full-brightness test pattern's p98 luma is so high the
    # sub-threshold fade tail would be shorter than the real one.
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i", f"testsrc2=duration=8:size=1080x1920:rate={FPS}",
          "-vf", "lutyuv=y=val*0.45",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", src1])
    src1_yavg = handler._ig_window_yavg(src1, 6.5, 8.0)
    check("synthetic source luma is realistic AND above the dark-scene floor",
          src1_yavg is not None and 32.0 < src1_yavg < 90.0,
          f"yavg={src1_yavg}")
    total_s = 8.0
    fade_st = total_s - OUTRO_FADE_DUR_S
    _run(["ffmpeg", "-y", "-v", "error", "-i", src1,
          "-vf", f"fade=t=out:st={fade_st:.6f}:d={OUTRO_FADE_DUR_S:.6f}:c=black",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", out1])
    v_dur, nb = _probe(out1)
    expected = int(round(total_s * FPS))
    check("fade preserves every frame (fix must mask, never trim)",
          nb == expected, f"nb={nb} expected={expected}")

    plan_prefix = {"_render_fps": float(FPS),
                   "_render_total_output_frames": expected}
    # PRE-FIX masks: outro unknown to the mask builder (outro='none' plan).
    pre_masks = handler._build_integrity_masks({**plan_prefix, "outro": "none"})
    # identity map: output == source timeline here; the echo sees the
    # UN-faded source (exactly the deployed geometry: the fade exists only
    # in the output), so v349's source-echo cannot downgrade it.
    ident = lambda t: t  # noqa: E731
    v = _gate(out1, v_dur, nb, expected, pre_masks, source=src1, out_to_src=ident)
    trip_checks = [t["check"] for t in v["trips"]]
    check("PRE-FIX: fade tail TRIPS black (geometry reconstructed, echo can't save it)",
          "black" in trip_checks, str(v["trips"])[:120])

    post_masks = handler._build_integrity_masks({**plan_prefix, "outro": "fade_black"})
    check("POST-FIX: fade_black window present in black mask",
          any(s <= fade_st + 0.01 and e >= total_s - 0.01
              for (s, e) in post_masks["black"]), str(post_masks["black"]))
    v = _gate(out1, v_dur, nb, expected, post_masks, source=src1, out_to_src=ident)
    check("POST-FIX: fade tail CLEAN", v["clean"] is True, str(v["trips"])[:120])
    # fade_white must NOT get a black mask (evidence-based membership)
    white_masks = handler._build_integrity_masks({**plan_prefix, "outro": "fade_white"})
    check("fade_white gets NO black mask (membership stays evidence-based)",
          white_masks["black"] == [], str(white_masks["black"]))

    # ── Family 2: dark B-roll content in the B-roll window ────────────────
    print("\n[cert] Family 2 — dark B-roll content")
    out2 = os.path.join(tmp, "f2_out.mp4")
    # bright source with a near-black (but composited, i.e. non-source) window
    # [4.0, 5.0] — the dark stock-footage cutaway.
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i", f"testsrc2=duration=8:size=1080x1920:rate={FPS}",
          "-vf", "drawbox=enable='between(t,4,5)':c=0x050505:t=fill",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", out2])
    v_dur, nb = _probe(out2)
    pre_masks = handler._build_integrity_masks({**plan_prefix, "outro": "none"})
    v = _gate(out2, v_dur, nb, expected, pre_masks, source=src1, out_to_src=ident)
    check("PRE-FIX: dark B-roll window TRIPS black (source underneath is bright)",
          "black" in [t["check"] for t in v["trips"]], str(v["trips"])[:120])
    post_masks = handler._build_integrity_masks(
        {**plan_prefix, "outro": "none", "_broll_output_ranges": [(4.0, 5.0)]})
    v = _gate(out2, v_dur, nb, expected, post_masks, source=src1, out_to_src=ident)
    check("POST-FIX: B-roll window in black mask → CLEAN",
          v["clean"] is True, str(v["trips"])[:120])

    # ── Family 3: dark source SCENE under designed (tighter) framing ──────
    print("\n[cert] Family 3 — dark scene + zoom framing (echo discriminator)")
    src3 = os.path.join(tmp, "f3_src.mp4")
    out3 = os.path.join(tmp, "f3_out.mp4")
    # Source: bright first 4s; [4,7] a dark scene (luma ~20, temporal sensor
    # noise so nothing freezes) carrying a moving bright block (~4% of
    # pixels) — blackdetect's 98% rule never fires on it, exactly the
    # night-metro signature. The block lives in the TOP band (y 200-584).
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i", f"testsrc2=duration=8:size=1080x1920:rate={FPS}",
          "-vf", ("drawbox=enable='between(t,4,7)':c=0x0a0a0a:t=fill,"
                  "drawbox=enable='between(t,4,7)':x='100+mod(t*240\\,400)':"
                  "y=200:w=216:h=384:c=0x8c8c8c:t=fill,"
                  "noise=alls=6:allf=t:enable='between(t,4,7)'"),
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", src3])
    # Output: the render's tighter framing (zoom into the BOTTOM band, the
    # designed crop excludes the bright block) → the same scene reads BLACK
    # in the output.
    _run(["ffmpeg", "-y", "-v", "error", "-i", src3,
          "-vf", "crop=540:960:500:900,scale=1080:1920",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", out3])
    v_dur, nb = _probe(out3)
    # the output must actually read black in the scene window (reconstruction)
    p = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", out3,
         "-vf", "blackdetect=d=%s:pix_th=%s" % (
             handler._IG_BLACK_DETECT_S, handler._IG_BLACK_PIX_TH),
         "-an", "-f", "null", "-"], capture_output=True, text=True)
    out_black = handler._ig_parse_spans(p.stderr or "", r"black_start:([\d.]+)",
                                        r"black_end:([\d.]+)", 8.0)
    check("output reads black in the scene window", len(out_black) >= 1,
          str(out_black))
    # the SOURCE must NOT read black there (blackdetect finds nothing → the
    # pre-fix cover-only echo keeps the defect → pre-fix TRIP)
    p = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", src3,
         "-vf", "blackdetect=d=%s:pix_th=%s" % (
             handler._IG_BLACK_DETECT_S, handler._IG_BLACK_PIX_TH),
         "-an", "-f", "null", "-"], capture_output=True, text=True)
    src_black = handler._ig_parse_spans(p.stderr or "", r"black_start:([\d.]+)",
                                        r"black_end:([\d.]+)", 8.0)
    check("PRE-FIX: source blackdetect finds NOTHING (cover-only echo would trip)",
          len(src_black) == 0, str(src_black))
    # the scene really is dark by mean luma (the discriminator's evidence)
    yavg = handler._ig_window_yavg(src3, 4.5, 6.5)
    check("scene YAVG at/below dark-scene floor",
          yavg is not None and yavg <= handler._IG_DARK_SCENE_YAVG,
          f"yavg={yavg}")
    # POST-FIX: the real echo downgrades via the dark-scene discriminator
    defects, downgraded = handler._ig_source_echo_black(src3, out_black, ident)
    check("POST-FIX: dark-scene echo downgrades (src_dark_scene_yavg)",
          not defects and downgraded
          and all("src_dark_scene_yavg" in d for d in downgraded),
          str(downgraded)[:140])
    # and the full gate goes CLEAN with source echo wired
    v = _gate(out3, v_dur, nb, expected,
              handler._build_integrity_masks({**plan_prefix, "outro": "none"}),
              source=src3, out_to_src=ident)
    check("POST-FIX: full gate CLEAN on dark-scene geometry",
          v["clean"] is True, str(v["trips"])[:140])

    # ── NEGATIVE CONTROL: genuine render-written black still trips ────────
    print("\n[cert] Negative control — genuine defect still trips")
    out4 = os.path.join(tmp, "f4_out.mp4")
    # bright source everywhere; output has a black HOLE [2.0, 2.6] the plan
    # never designed (no broll there, no outro there, source bright there).
    _run(["ffmpeg", "-y", "-v", "error", "-i", src1,
          "-vf", "drawbox=enable='between(t,2,2.6)':c=black:t=fill",
          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", out4])
    v_dur, nb = _probe(out4)
    masks = handler._build_integrity_masks(
        {**plan_prefix, "outro": "fade_black",
         "_broll_output_ranges": [(6.0, 7.0)]})
    v = _gate(out4, v_dur, nb, expected, masks, source=src1, out_to_src=ident)
    check("NEGATIVE: mid-video black hole STILL TRIPS with every fix active",
          v["clean"] is False
          and "black" in [t["check"] for t in v["trips"]],
          str(v["trips"])[:140])

    n_fail = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n[cert] {len(_results) - n_fail}/{len(_results)} checks passed")
    if n_fail:
        print("[cert] FAIL")
        return 1
    print("[cert] PASS — all three families reconstructed, pre-fix trip / "
          "post-fix clean / negative control intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
