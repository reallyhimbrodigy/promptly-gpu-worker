"""HYPE render — drive the projected caption-less PromptlyRenderInput through the
REAL render primitives, bridging render_multi_clip's word coupling.

render_multi_clip (handler.py) is ~2800 lines built around projecting Deepgram
WORDS onto the output timeline (captions, SFX onsets, word-anchored transitions).
A hype/music edit has NO words. But the RENDERING half of the pipeline is already
factored out of that coupling in ffmpeg_base.py:

    categorize_clip(clip)                -> "ffmpeg" | "remotion"  (word-free)
    build_micro_segments_input(...)      -> the PromptlyMicroSegments plan
    build_final_filtergraph(...)         -> the composite filtergraph

…and render-full.mjs renders the two Remotion compositions. So the "bridge" is to
drive those primitives directly from the projected PromptlyRenderInput (which
hype_editor.project_hype_plan already produces), skipping the word-coupled
input-building entirely.

Split (identical to production):
  • FFmpeg base   — cut/seek/speed clips + no-zoom / SIMPLE_ZOOM clips + composite.
  • PromptlyMicroSegments (Remotion) — transitions + composite-effect zooms.
  • PromptlyOverlay      (Remotion) — motion graphics (hype has no captions/B-roll).
  • Audio: the source's OWN audio, per-clip trimmed + speed-warped + concatenated.
           NEVER adds a track (no-music rule) — it beat-syncs what the user gave us.

DARK: this module has ZERO callers in the live talking-head path (grep-provable),
so the preservation harness stays green. It is exercised only by the sample
harness (hype_sample_app.py) and, later, a PROMPTLY_HYPE_MODE render branch.
"""
import os
import json
import re
import subprocess
from typing import Optional

import ffmpeg_base as _fb


# ── shell helper ─────────────────────────────────────────────────────────────
def _run(cmd, label, timeout=1800):
    print(f"[hype-render] {label}: ffmpeg/node {' '.join(str(c) for c in cmd[1:9])} …", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(
            f"[hype-render] {label} failed rc={r.returncode}\n"
            f"CMD: {' '.join(str(c) for c in cmd)}\n"
            f"STDERR:\n{(r.stderr or '')[-2000:]}"
        )
    return r


def _has_audio(path: str) -> bool:
    """True only for a DECODABLE audio stream.

    An iPhone "Core Media Metadata" track is classified by ffmpeg as an AUDIO
    stream with codec_name `none` — the live log reads
    `[aist#0:2/none] Decoding requested, but no decoder found for: none`. Asking
    only for the stream INDEX counts that track as audio, so normalize_source
    then asks aac to encode a stream nothing can decode.

    handler.py learned this on 2026-08-03 (14d758c) and this file did not — the
    fix landed in one of the two copies. Read the codec, not the index.
    """
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=codec_name", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    return any(c.strip() and c.strip() != "none"
               for c in (r.stdout or "").splitlines())


def _has_video(path: str) -> bool:
    """True only for a DECODABLE video stream — the canon's precondition."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=codec_name", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    return any(c.strip() and c.strip() != "none"
               for c in (r.stdout or "").splitlines())


# ── ingest: canonicalize the source to WxH@fps (build_final_filtergraph's
#    precondition is "source is already 1080×1920, source_fps") ───────────────
def normalize_source(src: str, out: str, fps: float, w: int = 1080, h: int = 1920) -> str:
    """Scale+crop+fps to the canonical portrait canvas, mirroring the production
    ingest so the composite filtergraph samples a clean, known-geometry source."""
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={w}:{h},fps={fps}")
    # MAP EXPLICITLY, NEVER AUTO-SELECT (2026-08-04). Automatic stream selection
    # picks ffmpeg's idea of the "best" stream, and iPhone sources carry tracks
    # that confuse it — the Core Media Metadata track is reported as audio with
    # codec `none`. Naming 0:v:0 and 0:a:0? removes the guess entirely; the `?`
    # makes the audio map optional so a genuinely silent source still renders.
    cmd = ["ffmpeg", "-y", "-v", "warning", "-i", src,
           "-map", "0:v:0",
           "-vf", vf, "-r", f"{fps:g}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "16",
           "-pix_fmt", "yuv420p"]
    if _has_audio(src):
        cmd += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += [out]
    _run(cmd, "normalize-source")

    # THE PRODUCING STAGE OWNS ITS OUTPUT. Three users in 24h hit
    # "No video stream found in input file .../minimal_canon.mp4" — the failure
    # surfaced at Remotion, several rungs downstream, as RENDER_REMOTION or
    # RENDER_FATAL:canon_unreadable. Naming it there was a DETECTOR, not a cure.
    # rc==0 is not success (91f0f8a): verify the artifact here, where the stage
    # that wrote it can still say what it was given.
    if not _has_video(out):
        _sz = os.path.getsize(out) if os.path.exists(out) else -1
        raise RuntimeError(
            f"RENDER_CANON_NO_VIDEO: normalize-source exited 0 but wrote a canon "
            f"with no decodable video stream "
            f"({'missing' if _sz < 0 else f'{_sz} bytes'}) — "
            f"src={os.path.basename(src)} fps={fps:g} {w}x{h}")
    return out


# ── audio: the source's own audio, warped per clip, concatenated ─────────────
def _atempo_chain(rate: float) -> str:
    """FFmpeg atempo accepts 0.5–2.0 per stage; chain stages for larger factors.
    rate == playbackRate (video speed). Audio follows the video so A/V stay locked."""
    if abs(rate - 1.0) < 1e-3:
        return ""
    stages, r = [], float(rate)
    while r > 2.0 + 1e-6:
        stages.append(2.0); r /= 2.0
    while r < 0.5 - 1e-6:
        stages.append(0.5); r /= 0.5
    stages.append(r)
    return ",".join(f"atempo={s:.6f}" for s in stages)


def build_hype_audio(source_canonical: str, clips: list, transitions: list,
                     fps: float, out_path: str) -> str:
    """Per-clip source-audio segments (trim [start,end] + speed-warp) concatenated
    to the output timeline. Transitions are ADDITIVE frames on the video timeline
    (build_micro_segments_input advances the cursor by the transition duration), so
    the audio MUST insert matching silence at each transition — otherwise the audio
    ends `sum(transition_frames)` short and the whole track drifts early (measured:
    2 transitions × 8f = 0.53s A/V skew). NEVER synthesizes music — clip audio is
    the user's own track; transition gaps are brief silence (the visual break)."""
    SR = 48000
    trans_after = {int(t["afterClipIndex"]): int(t["durationInFrames"])
                   for t in (transitions or [])}
    trans_total = sum(trans_after.values())
    total_out = sum(int(c["durationInFrames"]) for c in clips) + trans_total or 1
    if not _has_audio(source_canonical):
        dur_s = total_out / fps
        _run(["ffmpeg", "-y", "-v", "warning", "-f", "lavfi", "-t", f"{dur_s:.4f}",
              "-i", f"anullsrc=r={SR}:cl=stereo", "-c:a", "pcm_s16le", out_path],
             "hype-audio-silent")
        return out_path
    parts, labels = [], []
    idx = 0
    _afmt = f"aformat=sample_rates={SR}:channel_layouts=stereo"
    for i, c in enumerate(clips):
        start_f = int(c["startFromFrames"])
        rate = float(c.get("playbackRate") or 1.0)
        dur_out = int(c["durationInFrames"])
        dur_src = max(1, int(round(dur_out * rate)))
        s0 = start_f / fps
        s1 = (start_f + dur_src) / fps
        chain = f"atrim=start={s0:.5f}:end={s1:.5f},asetpts=PTS-STARTPTS"
        tempo = _atempo_chain(rate)
        if tempo:
            chain += "," + tempo
        parts.append(f"[0:a]{chain},{_afmt}[a{idx}]")
        labels.append(f"[a{idx}]"); idx += 1
        if i in trans_after:
            # TRANSITION AUDIO = clip A's source audio CONTINUING through the
            # window — never silence. The taste-read diagnosis (2026-07-25)
            # measured that an inserted 267ms silence is not a beat multiple
            # (0.57-0.62 beat at 128-140bpm), so every transition broke the
            # groove's phase by construction — Zac heard it as "random". The
            # music keeps playing under the visual transition (A has source
            # material past its out-point by construction on a music clip);
            # total length still matches the video timeline exactly.
            tdur_s = trans_after[i] / fps
            _t0 = s1
            _t1 = s1 + tdur_s * rate      # source-time span covering the window
            # apad + output-side atrim force the EXACT window length even if A
            # ends at the source tail (pad the remainder with silence — never
            # drift A/V).
            parts.append(
                f"[0:a]atrim=start={_t0:.5f}:end={_t1:.5f},asetpts=PTS-STARTPTS"
                + ("," + tempo if tempo else "")
                + f",{_afmt},apad,atrim=end={tdur_s:.5f}[a{idx}]")
            labels.append(f"[a{idx}]"); idx += 1
    fc = ";".join(parts) + ";" + "".join(labels) + f"concat=n={idx}:v=0:a=1[aout]"
    _run(["ffmpeg", "-y", "-v", "warning", "-i", source_canonical,
          "-filter_complex", fc, "-map", "[aout]", "-c:a", "pcm_s16le", out_path],
         "hype-audio")
    return out_path


# ── Remotion overlay/micro render (render-full.mjs) ──────────────────────────
def _render_remotion(input_json_path: str, output_path: str, public_dir: str,
                     composition: str, bundle_dir: Optional[str] = None,
                     node_bin: str = "node",
                     render_script: str = "/remotion/render-full.mjs") -> str:
    """Invoke the SAME production renderer (render-full.mjs) for one composition.
    PROMPTLY_BUNDLE_DIR lets a local run point at a project bundle instead of the
    Modal image's /remotion/bundle."""
    env = dict(os.environ)
    if bundle_dir:
        env["PROMPTLY_BUNDLE_DIR"] = bundle_dir
    # Remotion caps --concurrency at the core count; its default (half the thread
    # count) overshoots on hyperthreaded containers. Pin it under the core count.
    _cores = os.cpu_count() or 4
    _conc = max(1, min(_cores - 1, 8))
    cmd = [node_bin, render_script,
           "--input", input_json_path,
           "--output", output_path,
           "--public-dir", public_dir,
           "--composition", composition,
           "--concurrency", str(_conc),
           "--gl", "swangle"]
    print(f"[hype-render] remotion {composition}: {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=1800)
    if r.returncode != 0 or not os.path.exists(output_path):
        # SIGNATURE-FIRST (2026-08-02). This used to open with STDOUT, so the
        # thrown exception sat ~700 chars in and the degrade ladder's [:300]
        # truncation cut it off entirely: job b8ab1276's durable error_detail
        # ended at "[render-full] progress 0% rendered=0" and the actual cause
        # was never recoverable from the job row. handler._remotion_subprocess
        # has led with the real error since 2026-08-01; this call site (the
        # hype/minimal bridge) was the one still dumping stdout first.
        #
        # Pull the LAST line-anchored *Error/Exception line — the thrown one —
        # to the front, exactly as the handler path does, so the first 300
        # characters name the failure rather than the startup banner.
        _stderr_full = r.stderr or ""
        _stdout_full = r.stdout or ""
        _err_lines = re.findall(
            r"^[A-Za-z_.$]*(?:Error|Exception)\b.*", _stderr_full, re.M)
        _salient = (_err_lines[-1].strip()[:400] + " ||| ") if _err_lines else ""
        raise RuntimeError(
            f"[hype-render] render-full.mjs {composition} failed rc={r.returncode}: "
            f"{_salient}STDERR:\n{_stderr_full[-2000:]}\nSTDOUT:\n{_stdout_full[-1200:]}"
        )
    return output_path


# ── the render ───────────────────────────────────────────────────────────────
def render_hype(render_input: dict, source_canonical: str, output_path: str,
                work_dir: str, public_dir: Optional[str] = None,
                bundle_dir: Optional[str] = None, remotion: bool = True) -> dict:
    """Render a projected (caption-less) PromptlyRenderInput to MP4 via the real
    primitives. Returns a small manifest describing what rendered.

    `public_dir` is where render-full.mjs resolves source BASENAMES — the source
    is staged there under its basename. `remotion=False` is the local dev-loop:
    it renders the FFmpeg-only path and REFUSES (loud) if the plan needs Remotion
    (any zoom/transition), so a base-only test can't silently drop elements.
    """
    os.makedirs(work_dir, exist_ok=True)
    clips = render_input["clips"]
    transitions = render_input.get("transitions", []) or []
    mgs = render_input.get("motionGraphics", []) or []
    fps = float(render_input["fps"])
    total_frames = int(render_input["totalDurationInFrames"])
    outro = render_input.get("outro") or "none"
    src_base = os.path.basename(source_canonical)

    # stage the source under its basename in the public dir (render-full.mjs +
    # the sourceUrl basenames in the render input resolve against public_dir)
    if public_dir:
        os.makedirs(public_dir, exist_ok=True)
        staged = os.path.join(public_dir, src_base)
        if os.path.abspath(staged) != os.path.abspath(source_canonical):
            try:
                if os.path.exists(staged):
                    os.remove(staged)
                os.link(source_canonical, staged)
            except Exception:
                import shutil
                shutil.copyfile(source_canonical, staged)

    inputs = [source_canonical]
    micro_input_idx = None
    overlay_input_idx = None
    manifest = {"clips": len(clips), "transitions": len(transitions),
                "motion_graphics": len(mgs), "total_frames": total_frames,
                "fps": fps, "ffmpeg_clips": 0, "remotion_clips": 0,
                "micro_rendered": False, "overlay_rendered": False}
    manifest["ffmpeg_clips"] = sum(1 for c in clips if _fb.categorize_clip(c) == "ffmpeg")
    manifest["remotion_clips"] = len(clips) - manifest["ffmpeg_clips"]

    # 1. PromptlyMicroSegments — transitions + composite-effect zooms
    micro_input, micro_meta = _fb.build_micro_segments_input(
        clips, transitions, src_base, fps)
    if micro_input is not None:
        if not remotion:
            raise RuntimeError(
                "[hype-render] plan needs Remotion (transitions/complex zooms) but "
                "remotion=False. Use a no-zoom/no-transition plan for the local "
                f"dev-loop, or run on Modal. micro segments={len(micro_meta)}")
        micro_json = os.path.join(work_dir, "micro_input.json")
        with open(micro_json, "w") as f:
            json.dump(micro_input, f)
        micro_video = os.path.join(work_dir, "micro.mov")
        _render_remotion(micro_json, micro_video, public_dir or work_dir,
                         "PromptlyMicroSegments", bundle_dir=bundle_dir)
        inputs.append(micro_video)
        micro_input_idx = len(inputs) - 1
        manifest["micro_rendered"] = True

    # 2. PromptlyOverlay — motion graphics (hype has no captions/B-roll/text)
    if mgs:
        if not remotion:
            raise RuntimeError(
                "[hype-render] plan has motion graphics (needs PromptlyOverlay) but "
                "remotion=False.")
        # PromptlyOverlay reads {caption, motionGraphics, textOverlays, fps, broll,
        # tightCutOverlays, generatedScenes} — the projected render_input already
        # carries them (caption=None, broll=[]). Pass it straight through.
        overlay_json = os.path.join(work_dir, "overlay_input.json")
        with open(overlay_json, "w") as f:
            json.dump(render_input, f)
        overlay_video = os.path.join(work_dir, "overlay.mov")
        _render_remotion(overlay_json, overlay_video, public_dir or work_dir,
                         "PromptlyOverlay", bundle_dir=bundle_dir)
        inputs.append(overlay_video)
        overlay_input_idx = len(inputs) - 1
        manifest["overlay_rendered"] = True

    # 3. Audio — source's own track, warped per clip, concatenated (transition
    #    silences keep it frame-locked to the video timeline)
    audio_path = build_hype_audio(source_canonical, clips, transitions, fps,
                                  os.path.join(work_dir, "hype_audio.wav"))
    inputs.append(audio_path)
    audio_idx = len(inputs) - 1

    # 4. Composite (the production filtergraph, word-free)
    fg, final_labels = _fb.build_final_filtergraph(
        clips=clips, transitions=transitions, micro_segments=micro_meta,
        outro=outro, total_output_frames=total_frames, source_fps=fps,
        source_input_idx=0, micro_input_idx=micro_input_idx,
        overlay_input_idx=overlay_input_idx,
    )
    cmd = ["ffmpeg", "-y", "-v", "warning", "-threads", "0"]
    for inp in inputs:
        cmd += ["-i", inp]
    cmd += [
        "-filter_complex", fg,
        "-map", f"[{final_labels[0]}]",
        "-map", f"{audio_idx}:a:0",
        "-c:a", "aac", "-b:a", "256k",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-fps_mode", "cfr", "-r", str(int(round(fps))),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, "composite")
    manifest["output"] = output_path
    manifest["output_bytes"] = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    print(f"[hype-render] DONE {output_path} ({manifest['output_bytes']} bytes) "
          f"clips={manifest['clips']} (ffmpeg={manifest['ffmpeg_clips']} "
          f"remotion={manifest['remotion_clips']}) trans={manifest['transitions']} "
          f"mg={manifest['motion_graphics']}", flush=True)
    return manifest
