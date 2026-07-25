"""HYPE sample-render harness — DARK machinery proof for Zac's eye.

Standalone Modal app (`modal run hype_sample_app.py`), NEVER deployed, never
touches the live worker. Reuses the production worker image (modal_app.image:
/remotion bundle + chrome + ffmpeg + aubio + google-genai) + secrets, and drives
the DARK hype machinery end-to-end on rights-clear test clips:

  Pexels clip  +  synthetic 4/4 beat track (the "user's own audio", never added
  to a real user's video — this is a constructed durable test source)
    → general_editor.compute_beat_grid   (aubio tempo-confidence)
    → hype_editor.build_hype_prompt       (the MUSIC/HYPE guidance block)
    → Gemini HypePlan                     (the editorial block's instincts)
    → hype_editor.project_hype_plan       (→ caption-less PromptlyRenderInput)
    → hype_render.render_hype             (real ffmpeg_base + render-full.mjs)
    → MP4 → S3/CloudFront

These are MACHINERY proof (does the pipeline choose beat-aligned cuts, zoom hits,
speed ramps and render them?), NOT the taste read. The flip gates (real-music
threshold validation + Zac's taste sign-off) are unchanged; nothing deploys.
"""
import os
import sys
# The worker image bakes local .py at container root ("/"); make them importable
# both locally (CWD is on sys.path) and in-container (this puts "/" first) BEFORE
# the module-top `import modal_app` runs in either place.
sys.path.insert(0, "/")
import modal
import modal_app  # image reused from the worker app (baked into the image below)

# The production render-capable image + the three DARK modules it doesn't carry.
image = (
    modal_app.image
    .add_local_file("modal_app.py", "/modal_app.py")
    .add_local_file("general_editor.py", "/general_editor.py")
    .add_local_file("hype_editor.py", "/hype_editor.py")
    .add_local_file("minimal_editor.py", "/minimal_editor.py")
    .add_local_file("hype_render.py", "/hype_render.py")
)

app = modal.App("hype-sample", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),      # PEXELS_API_KEY, AWS S3
    modal.Secret.from_name("gemini-vertex"),         # Vertex creds for Gemini
    modal.Secret.from_name("promptly-cloudfront"),   # CDN
]

CDN = "https://d1iax8jos987n3.cloudfront.net/"
FPS = 30.0


# ── source prep ──────────────────────────────────────────────────────────────
def _synth_beat_wav(path, bpm, dur_s, subdiv=2, sr=44100):
    """4/4 kick+hat click track — the proven beat-cert synth (aubio-confident)."""
    import numpy as np, wave
    n = int(dur_s * sr)
    audio = np.zeros(n, dtype=np.float32)
    hit_period = (60.0 / bpm) / subdiv
    length = int(0.04 * sr)
    env = np.exp(-np.linspace(0, 8, length))
    t, idx = 0.0, 0
    while t < dur_s - 0.05:
        pos = int(t * sr)
        downbeat = (idx % subdiv == 0)
        freq = 60.0 if downbeat else 8000.0
        amp = 0.95 if downbeat else 0.5
        hit = (amp * np.sin(2 * np.pi * freq * np.arange(length) / sr) * env).astype(np.float32)
        end = min(pos + length, n)
        audio[pos:end] += hit[:end - pos]
        t += hit_period
        idx += 1
    audio = np.clip(audio, -1, 1)
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((audio * 32767).astype("<i2").tobytes())


def _fetch_pexels(query, work, min_dur=12.0):
    """Search Pexels for a portrait video, download a mid-size rendition. Returns
    (local_path, meta). Pexels footage is free to use (rights-clear)."""
    import json, urllib.request, urllib.parse
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("PEXELS_API_KEY not set in promptly-secrets")
    url = ("https://api.pexels.com/videos/search?query="
           + urllib.parse.quote(query) + "&orientation=portrait&per_page=15&size=medium")
    # Pexels sits behind Cloudflare, which 403s urllib's default bot UA — send a
    # browser UA (+ the API key).
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": ua})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    vids = data.get("videos") or []
    # prefer a clip long enough to cut, portrait, with a downloadable HD-ish file
    best = None
    for v in sorted(vids, key=lambda x: -float(x.get("duration") or 0)):
        if float(v.get("duration") or 0) < min_dur:
            continue
        files = [f for f in (v.get("video_files") or [])
                 if (f.get("height") or 0) >= (f.get("width") or 0)]  # portrait
        files = sorted(files, key=lambda f: abs((f.get("height") or 0) - 1280))
        if files:
            best = (v, files[0]); break
    if best is None and vids:  # fallback: any video, any file
        v = vids[0]
        best = (v, sorted(v.get("video_files") or [],
                          key=lambda f: abs((f.get("height") or 0) - 1280))[0])
    if best is None:
        raise RuntimeError(f"Pexels returned no usable video for '{query}'")
    v, f = best
    out = os.path.join(work, "pexels_raw.mp4")
    dl = urllib.request.Request(f["link"], headers={"User-Agent": ua})
    with urllib.request.urlopen(dl, timeout=120) as resp, open(out, "wb") as fh:
        fh.write(resp.read())
    meta = {"pexels_id": v.get("id"), "duration": v.get("duration"),
            "res": f"{f.get('width')}x{f.get('height')}", "url": v.get("url")}
    print(f"[hype-sample] pexels '{query}' → id={meta['pexels_id']} {meta['res']} {meta['duration']}s", flush=True)
    return out, meta


def _duration(path):
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return float((r.stdout or "0").strip() or 0)


def _mux_beat(video, beat_wav, work):
    """Replace the clip's audio with the synthetic beat → the 'user's own music'."""
    import subprocess
    out = os.path.join(work, "with_beat.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "warning", "-i", video, "-i", beat_wav,
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-shortest", out], check=True, capture_output=True, text=True)
    return out


def _extract_wav(video, work):
    import subprocess
    out = os.path.join(work, "audio.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "warning", "-i", video, "-vn",
                    "-ac", "1", "-ar", "44100", out], check=True, capture_output=True, text=True)
    return out


def _gemini_hype(system_instruction, user_content):
    """Call Gemini for a HypePlan — the editorial block's instincts, rendered."""
    import handler, hype_editor as he
    client = handler._get_genai_client()
    cfg = handler.genai_types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=1.0,
        response_mime_type="application/json",
        response_schema=he.HypePlan,
        thinking_config=handler.genai_types.ThinkingConfig(thinking_budget=8192),
    )
    resp = client.models.generate_content(
        model=handler.GEMINI_EDITORIAL_MODEL, contents=user_content, config=cfg)
    plan = getattr(resp, "parsed", None)
    if isinstance(plan, he.HypePlan):
        return plan
    import json
    return he.HypePlan.model_validate(json.loads(resp.text))


def _upload(path, key):
    import boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3.upload_file(path, bucket, key, ExtraArgs={"ContentType": "video/mp4"})
    return CDN + key


# ── the E2E, one sample ──────────────────────────────────────────────────────
@app.function(secrets=SECRETS, timeout=2400, cpu=8.0, memory=32768)
def render_sample(spec: dict) -> dict:
    import sys, os, time, traceback
    sys.path.insert(0, "/")
    import general_editor as ge
    import hype_editor as he
    import hype_render as hr

    name = spec["name"]
    work = f"/tmp/hype/{name}"
    os.makedirs(work, exist_ok=True)
    stage = "init"
    try:
        # 1. source: pexels visual + synthetic beat = the constructed durable clip
        stage = "pexels"
        raw, pmeta = _fetch_pexels(spec["pexels_query"], work)
        vdur = min(_duration(raw), float(spec.get("max_src_s", 24.0)))
        stage = "synth_beat"
        beat = os.path.join(work, "beat.wav")
        _synth_beat_wav(beat, spec["bpm"], vdur + 1.0)
        stage = "mux_beat"
        withbeat = _mux_beat(raw, beat, work)
        # 2. canonicalize to 1080x1920@fps
        stage = "normalize"
        canon = hr.normalize_source(withbeat, os.path.join(work, "canon.mp4"), FPS)
        dur = _duration(canon)
        # 3. perception (aubio beat grid on the clip's OWN audio)
        stage = "perception"
        wav = _extract_wav(canon, work)
        beats, conf = ge.compute_beat_grid(wav, has_audio=True)
        print(f"[hype-sample] {name}: {len(beats)} beats, tempo_confidence={conf} "
              f"(music gate = > {ge.BEAT_CONF_MIN})", flush=True)
        # 4-5. plan. MINIMAL path = deterministic cuts+transitions (no Gemini, no
        # captions/zooms/beat-sync); HYPE path = Gemini HypePlan off the beat grid.
        mode = spec.get("mode", "hype")
        if mode == "minimal":
            stage = "minimal_plan"
            import minimal_editor as me
            plan = me.build_minimal_plan(dur, fps=FPS, motion_curve=None)
        else:
            stage = "prompt"
            sys_i, user_c = he.build_hype_prompt(spec["vibe"], dur, beats)
            stage = "gemini"
            plan = _gemini_hype(sys_i, user_c)
        # 6. project → caption-less PromptlyRenderInput
        stage = "project"
        ri = he.project_hype_plan(plan, source_url=os.path.basename(canon),
                                  source_fps=FPS, source_duration=dur)

        # plan summary — what the editorial block CHOSE (built BEFORE render so a
        # render failure still surfaces the machinery's instincts)
        clip_durs_s = [c.end_s - c.start_s for c in plan.clips]
        zooms = [(i, c.zoom, c.punch) for i, c in enumerate(plan.clips) if c.zoom]
        speeds = [(i, c.speed) for i, c in enumerate(plan.clips) if abs(c.speed - 1.0) > 0.01]
        out_dur = ri["totalDurationInFrames"] / FPS
        summary = {
            "name": name, "ok": True,
            "source": pmeta, "src_dur_s": round(dur, 1), "out_dur_s": round(out_dur, 1),
            "beats_detected": len(beats), "tempo_confidence": conf,
            "n_clips": len(plan.clips),
            "cut_density_per_10s": round(len(plan.clips) / max(out_dur, 0.1) * 10, 1),
            "mean_clip_len_s": round(sum(clip_durs_s) / max(len(clip_durs_s), 1), 2),
            "zooms": [{"clip": i, "type": z, "punch": p} for i, z, p in zooms],
            "speed_ramps": [{"clip": i, "speed": s} for i, s in speeds],
            "transitions": [{"after_clip": t.after_clip, "type": t.type} for t in plan.transitions],
            "motion_graphics": [{"type": m.type, "text": m.text} for m in plan.motion_graphics],
            "outro": plan.outro, "notes": plan.notes,
        }

        # 7. render through the REAL primitives (ffmpeg_base + render-full.mjs).
        #    A render/upload failure is attached to the summary, not fatal — the
        #    plan is the machinery proof and is worth returning either way.
        try:
            stage = "render"
            out = os.path.join(work, f"{name}_hype.mp4")
            # render-full.mjs resolves source BASENAMES against the bundle's public
            # dir (/remotion/bundle/public) — stage there, exactly as production does.
            manifest = hr.render_hype(ri, canon, out, work,
                                      public_dir="/remotion/bundle/public", remotion=True)
            stage = "upload"
            ts = spec.get("ts", "0")
            summary["url"] = _upload(out, f"hype-samples/{name}_{ts}.mp4")
            summary["render_manifest"] = manifest
            print(f"[hype-sample] {name} DONE → {summary['url']}", flush=True)
        except Exception as re:
            import traceback as _tb
            summary["render_ok"] = False
            summary["render_stage"] = stage
            summary["render_error"] = f"{type(re).__name__}: {re}"
            summary["render_traceback"] = _tb.format_exc()[-2500:]
            print(f"[hype-sample] {name} plan OK but render FAILED @{stage}: {re}", flush=True)
        return summary
    except Exception as e:
        return {"name": name, "ok": False, "stage": stage,
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc()[-2500:]}


@app.local_entrypoint()
def main():
    import json, time
    ts = str(int(time.time()))
    specs = [
        {"name": "car_action", "ts": ts, "bpm": 128, "max_src_s": 22.0,
         "pexels_query": "sports car driving fast",
         "vibe": "high-energy car edit synced to the beat, punchy cuts on the drop"},
        {"name": "gym_hype", "ts": ts, "bpm": 140, "max_src_s": 22.0,
         "pexels_query": "gym workout weightlifting",
         "vibe": "gym hype montage, hard cuts and speed into the lift"},
        # MINIMAL path (#3): silent/no-speech clips → clean cuts + calm transitions,
        # deterministic (no Gemini, no captions/zooms/beat-sync). bpm still muxes a
        # bed so the clip isn't pure-silent, but the minimal plan ignores it.
        {"name": "minimal_nature", "ts": ts, "bpm": 100, "max_src_s": 22.0, "mode": "minimal",
         "pexels_query": "aerial nature landscape drone", "vibe": "minimal clean cuts"},
        {"name": "minimal_city", "ts": ts, "bpm": 100, "max_src_s": 22.0, "mode": "minimal",
         "pexels_query": "city street timelapse", "vibe": "minimal clean cuts"},
    ]
    results = list(render_sample.map(specs))
    print("\n================ HYPE SAMPLE RESULTS ================")
    for r in results:
        print(json.dumps(r, indent=2, default=str))
    print("====================================================")
