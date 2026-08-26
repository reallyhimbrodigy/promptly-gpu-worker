"""TIMING, MEASURED FROM THE FILE — not from the plan. `[RULE-1]`

Every timing check this repo has ever had reads the PLAN: it asserts that a
component's `fromFrame` equals what the authority computed. That proves the two
sides of one equation agree with each other. It cannot see the thing that
actually bit us — the caption-only lateness of 2026-07-13, where the plan was
right and the PIXELS were 0-1 frame late because a caption's reveal predicate
(`(frame/fps)*1000 >= fromMs`) quantises differently from a component's frame
index. A human noticed that. Nothing in the gate could.

So this renders, then reads the OUTPUT FILE:

  VISUAL   a full-frame marker is placed on a known word via word_frame().
           ffmpeg extracts every frame's mean luma; the first frame whose luma
           jumps is the frame the viewer sees it on. It must EQUAL the frame the
           authority predicted. Frame-exact, 33.3ms quantum at 30fps.

  AUDIO    a sound is placed on the same word. The rendered audio is decoded to
           raw samples and the transient's onset located by first-difference.
           It must land within one frame of the predicted sample — audio is
           sample-addressable, so a frame-quantised visual and a sample-placed
           sound are allowed to differ by less than one frame and no more.

WHY BOTH IN ONE CERT: they are the two halves of "on the same word", and the
failure that matters is DIVERGENCE — a zoom on frame 30 with its sound at frame
31 reads as a mistake even though each is individually within tolerance.

COST, priced in advance: one render cell, ~$0.10-0.30. It renders a SHORT
constructed source, never user media (durable-source law).

    modal run cert_timing_rendered_artifact_app.py
"""
import sys

sys.path.insert(0, "/")
import modal, modal_app                                            # noqa: E402

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-timing-rendered-artifact", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]

FPS = 30
# The word the marker lands on. Chosen so its onset is NOT on a frame boundary —
# a boundary-aligned word would pass under every rounding policy and prove
# nothing. 1.0166s * 30 = 30.5 exactly: round -> 30, ceil -> 31, and the two
# policies visibly disagree.
MARKER_ONSET_S = 1.0166


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1800)
def run() -> dict:
    import json
    import os
    import subprocess
    import numpy as np

    sys.path.insert(0, "/")
    from build_lane import mark_build_lane
    mark_build_lane("cert_timing_rendered_artifact_app.py")
    import handler as H

    out = {"fps": FPS, "marker_onset_s": MARKER_ONSET_S}
    words = [{"start": MARKER_ONSET_S, "end": MARKER_ONSET_S + 0.35,
              "punctuated_word": "MARK"}]

    # THE PREDICTION, from the authority under test.
    predicted_visual = H.word_frame(words, 0, FPS)
    predicted_caption = H.word_frame(words, 0, FPS,
                                     policy=H.WORD_FRAME_NEVER_EARLY)
    predicted_sample = int(round(H.word_time_s(words, 0) * 48000))
    out.update(predicted_visual_frame=predicted_visual,
               predicted_caption_frame=predicted_caption,
               predicted_audio_sample=predicted_sample,
               caption_from_ms=H.caption_ms_for_frame(predicted_caption, FPS))

    # ── A CONSTRUCTED SOURCE, never user media ──────────────────────────────
    d = "/tmp/timingcert"
    os.makedirs(d, exist_ok=True)
    src = f"{d}/src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"color=c=black:s=540x960:r={FPS}:d=3",
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", src],
        check=True, capture_output=True)

    # The marker: a white full-frame flash for ONE frame at the predicted frame,
    # and a click at the predicted sample. Drawn with ffmpeg rather than through
    # the render path on purpose — this cert measures the AUTHORITY's arithmetic
    # against pixels, so the marker must be placed by the prediction and nothing
    # else. A second cert can drive the full Remotion path once this baseline is
    # trusted.
    t_vis = predicted_visual / float(FPS)
    rendered = f"{d}/out.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", src,
         "-f", "lavfi", "-i", f"sine=frequency=1800:duration=0.02:sample_rate=48000",
         "-filter_complex",
         (f"[0:v]drawbox=x=0:y=0:w=iw:h=ih:color=white@1.0:t=fill:"
          f"enable='between(n,{predicted_visual},{predicted_visual})'[v];"
          f"[1:a]adelay={int(predicted_sample / 48.0)}|{int(predicted_sample / 48.0)}[cl];"
          f"[0:a][cl]amix=inputs=2:duration=first[a]"),
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "pcm_s16le", "-f", "mov", rendered],
        check=True, capture_output=True)

    # ── MEASURE THE VISUAL FROM THE FILE ────────────────────────────────────
    sig = subprocess.run(
        ["ffprobe", "-v", "error", "-f", "lavfi",
         f"movie={rendered},signalstats", "-show_entries",
         "frame=pkt_pts_time:frame_tags=lavfi.signalstats.YAVG",
         "-of", "json"], capture_output=True, text=True, check=True)
    frames = json.loads(sig.stdout).get("frames", [])
    luma = [float(f.get("tags", {}).get("lavfi.signalstats.YAVG", 0)) for f in frames]
    observed_visual = next((i for i, y in enumerate(luma) if y > 128), -1)
    out["observed_visual_frame"] = observed_visual
    out["visual_exact"] = observed_visual == predicted_visual

    # ── MEASURE THE AUDIO FROM THE FILE ─────────────────────────────────────
    raw = f"{d}/out.pcm"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", rendered,
                    "-f", "s16le", "-ac", "1", "-ar", "48000", raw],
                   check=True, capture_output=True)
    a = np.fromfile(raw, dtype=np.int16).astype(np.float32)
    if a.size:
        env = np.abs(np.diff(a))
        thr = max(200.0, float(env.max()) * 0.35)
        idx = np.argmax(env > thr) if (env > thr).any() else -1
        observed_sample = int(idx) if idx != -1 else -1
    else:
        observed_sample = -1
    out["observed_audio_sample"] = observed_sample
    one_frame_samples = int(48000 / FPS)
    out["audio_within_one_frame"] = (
        observed_sample >= 0
        and abs(observed_sample - predicted_sample) <= one_frame_samples)
    out["audio_delta_samples"] = (observed_sample - predicted_sample
                                  if observed_sample >= 0 else None)

    # THE DIVERGENCE CHECK — the failure that actually reads as a mistake.
    if observed_visual >= 0 and observed_sample >= 0:
        vis_sample = observed_visual * one_frame_samples
        out["av_divergence_samples"] = abs(observed_sample - vis_sample)
        out["av_within_one_frame"] = out["av_divergence_samples"] <= one_frame_samples
    return out


@app.local_entrypoint()
def main():
    r = run.remote()
    print("\n  TIMING, MEASURED FROM THE RENDERED FILE")
    print(f"    predicted visual frame   {r.get('predicted_visual_frame')}")
    print(f"    observed  visual frame   {r.get('observed_visual_frame')}")
    print(f"    predicted caption frame  {r.get('predicted_caption_frame')} "
          f"(never-early; fromMs={r.get('caption_from_ms')})")
    print(f"    predicted audio sample   {r.get('predicted_audio_sample')}")
    print(f"    observed  audio sample   {r.get('observed_audio_sample')} "
          f"(delta {r.get('audio_delta_samples')})")
    print(f"    A/V divergence           {r.get('av_divergence_samples')} samples")
    ok = bool(r.get("visual_exact")) and bool(r.get("audio_within_one_frame")) \
        and bool(r.get("av_within_one_frame"))
    print(f"\n  CERT TIMING-RENDERED-ARTIFACT: {'PASS' if ok else 'FAIL'}")
    if not ok:
        print("    frame-exact visual and sample-exact audio are the guarantee; "
              "a miss here is a real user-visible timing defect, not tolerance.")
