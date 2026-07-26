"""MOOD-REEL sample-render harness — DARK machinery proof for Zac's eye.

Standalone Modal app (`modal run moodreel_sample_app.py`), NEVER deployed,
never touches the live worker. Reuses the production worker image
(modal_app.image: /remotion bundle + chrome + ffmpeg + google-genai) + secrets
and drives the DARK mood-reel machinery end-to-end on rights-clear Pexels
clips (posed/aesthetic, no confident music — the S-ANYVIDEO underserved class):

  Pexels clip (id-pinned, its OWN audio or silence — nothing is ever added)
    → moodreel_editor.extract_motion_curve   (per-second motion energy)
    → moodreel_editor.build_moodreel_prompt  (the CINEMATIC doctrine)
    → Gemini HypePlan                        (same schema as hype — no new family)
    → hype_editor.project_hype_plan          (→ caption-less PromptlyRenderInput)
    → hype_render.render_hype                (real ffmpeg_base + render-full.mjs)
    → mechanical probe (A/V skew ≤56ms, no stray black) → MP4 → S3/CloudFront

Entry modes (env-selected, the HYPE_V2-style pattern):
  PEXELS_PICK=1  — search-only: list candidate clips so ids can be PINNED.
  MOODREEL=1     — the two cinematic mood-reel samples (pinned sources).
  MOODPAIRS=1    — ruling 4b minimal A/B pairs on ONE pinned source:
                     PAIR-1: baseline minimal vs boundary skip-trim (0.4-0.8s
                             skipped at low-motion boundaries)
                     PAIR-2: even-2.5s baseline vs motion-curve pacing
                             (build_minimal_plan(motion_curve=...) goes live
                             ONLY here — the live default call is untouched)

These are MACHINERY + taste-sample proof, not a deploy: nothing flips, no
routing is wired, the live path is byte-identical.
"""
import os
import sys
# The worker image bakes local .py at container root ("/"); make them importable
# both locally (CWD is on sys.path) and in-container BEFORE `import modal_app`.
sys.path.insert(0, "/")
import modal
import modal_app  # image reused from the worker app (baked into the image below)

# The production render-capable image + the DARK modules this harness drives
# (re-added so THIS worktree's copies win over any staler baked-in versions).
image = (
    modal_app.image
    .add_local_file("modal_app.py", "/modal_app.py")
    .add_local_file("general_editor.py", "/general_editor.py")
    .add_local_file("hype_editor.py", "/hype_editor.py")
    .add_local_file("minimal_editor.py", "/minimal_editor.py")
    .add_local_file("hype_render.py", "/hype_render.py")
    .add_local_file("moodreel_editor.py", "/moodreel_editor.py")
)

app = modal.App("moodreel-sample", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),      # PEXELS_API_KEY, AWS S3
    modal.Secret.from_name("gemini-vertex"),         # Vertex creds for Gemini
    modal.Secret.from_name("promptly-cloudfront"),   # CDN
]

CDN = "https://d1iax8jos987n3.cloudfront.net/"
FPS = 30.0
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


# ── Pexels (id-pinning pattern, copied from the hype harness) ────────────────
def _fetch_pexels(query, work, min_dur=14.0):
    """Search Pexels for a portrait video, download a mid-size rendition.
    "id:12345" fetches that EXACT video — samples must be reproducible, so the
    committed specs pin ids. Pexels footage is free to use (rights-clear)."""
    import json, urllib.request, urllib.parse
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("PEXELS_API_KEY not set in promptly-secrets")
    if query.startswith("id:"):
        vid = query[3:]
        req = urllib.request.Request(f"https://api.pexels.com/videos/videos/{vid}",
                                     headers={"Authorization": key, "User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            v = json.loads(r.read().decode())
        files = sorted([f for f in (v.get("video_files") or [])
                        if (f.get("height") or 0) >= (f.get("width") or 0)],
                       key=lambda f: abs((f.get("height") or 0) - 1280)) \
            or sorted(v.get("video_files") or [],
                      key=lambda f: abs((f.get("height") or 0) - 1280))
        out = os.path.join(work, "pexels_raw.mp4")
        dl = urllib.request.Request(files[0]["link"], headers={"User-Agent": _UA})
        with urllib.request.urlopen(dl, timeout=120) as resp, open(out, "wb") as fh:
            fh.write(resp.read())
        meta = {"pexels_id": v.get("id"), "duration": v.get("duration"),
                "res": f"{files[0].get('width')}x{files[0].get('height')}", "pinned": True}
        print(f"[moodreel] pexels pinned id={vid} {meta['res']} {meta['duration']}s", flush=True)
        return out, meta
    url = ("https://api.pexels.com/videos/search?query="
           + urllib.parse.quote(query) + "&orientation=portrait&per_page=15&size=medium")
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    vids = data.get("videos") or []
    best = None
    for v in sorted(vids, key=lambda x: -float(x.get("duration") or 0)):
        if float(v.get("duration") or 0) < min_dur:
            continue
        files = [f for f in (v.get("video_files") or [])
                 if (f.get("height") or 0) >= (f.get("width") or 0)]  # portrait
        files = sorted(files, key=lambda f: abs((f.get("height") or 0) - 1280))
        if files:
            best = (v, files[0]); break
    if best is None and vids:
        v = vids[0]
        best = (v, sorted(v.get("video_files") or [],
                          key=lambda f: abs((f.get("height") or 0) - 1280))[0])
    if best is None:
        raise RuntimeError(f"Pexels returned no usable video for '{query}'")
    v, f = best
    out = os.path.join(work, "pexels_raw.mp4")
    dl = urllib.request.Request(f["link"], headers={"User-Agent": _UA})
    with urllib.request.urlopen(dl, timeout=120) as resp, open(out, "wb") as fh:
        fh.write(resp.read())
    meta = {"pexels_id": v.get("id"), "duration": v.get("duration"),
            "res": f"{f.get('width')}x{f.get('height')}", "url": v.get("url")}
    print(f"[moodreel] pexels '{query}' → id={meta['pexels_id']} {meta['res']} "
          f"{meta['duration']}s", flush=True)
    return out, meta


def _duration(path):
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return float((r.stdout or "0").strip() or 0)


def _trim_to(path, work, max_s):
    """Cap the source length (stream copy — keyframe-imprecise is fine for a
    sample source; the canonical re-encode follows)."""
    import subprocess
    if _duration(path) <= max_s + 0.5:
        return path
    out = os.path.join(work, "trimmed.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "warning", "-i", path, "-t", str(max_s),
                    "-c", "copy", out], check=True, capture_output=True, text=True)
    return out


def _scene_cuts(path, thresh=0.35):
    """Shot-change times (s) via ffmpeg scene detection — composition-change
    hints for the doctrine. Fail-safe []."""
    import re, subprocess, tempfile
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="scenecuts_")
        os.close(fd)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-vf",
             f"select='gt(scene,{thresh})',metadata=print:file={tmp}",
             "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=600)
        with open(tmp) as f:
            text = f.read()
        return [round(float(m), 2)
                for m in re.findall(r"pts_time:([0-9.]+)", text)][:32]
    except Exception:
        return []
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


# ── PAIR-1 B-side: boundary skip-trim (harness-only; live call untouched) ────
def build_skip_trim_plan(duration, motion_curve, fps=30.0, target_clip_s=2.5,
                         min_clip_s=1.2, trim_lo=0.4, trim_hi=0.8,
                         transition_every=4):
    """Baseline even pacing, but every boundary that lands in LOW motion skips
    0.4-0.8s of source at the seam — the dead air the even baseline drags
    through. Deeper below the curve median → the bigger skip. Deterministic;
    same calm-transition cadence as build_minimal_plan so the A/B isolates the
    trim variable only."""
    import minimal_editor as me
    from hype_editor import HypePlan, HypeClip, HypeTransition
    curve = list(motion_curve or [])
    med = sorted(curve)[len(curve) // 2] if curve else 1.0
    win = (duration / len(curve)) if curve else 1.0
    cuts, t = [], 0.0
    while t < duration - min_clip_s:
        end = min(t + target_clip_s, duration)
        if end - t >= min_clip_s:
            cuts.append((round(t, 3), round(end, 3)))
        trim = 0.0
        if end < duration and curve:
            e = curve[min(int(end / win), len(curve) - 1)]
            if e <= med:
                trim = trim_hi if e <= 0.5 * med else trim_lo
        t = end + trim
    if not cuts:
        cuts = [(0.0, round(min(duration, max(min_clip_s, 1.0)), 3))]
    clips = [HypeClip(start_s=a, end_s=b, speed=1.0, zoom=None, punch=False)
             for a, b in cuts]
    transitions = [
        HypeTransition(after_clip=i,
                       type=me._MINIMAL_TRANSITIONS[k % len(me._MINIMAL_TRANSITIONS)])
        for k, i in enumerate(range(transition_every - 1, len(clips) - 1,
                                    transition_every))]
    return HypePlan(clips=clips, transitions=transitions,
                    motion_graphics=[], outro="none")


# ── mechanical probe (the ruling's bar: A/V ≤56ms, no stray black) ───────────
def _mech_probe(path, outro="none", fade_dur_s=1.0):
    import re, subprocess
    def _sdur(sel):
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", sel, "-show_entries",
             "stream=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True)
        try:
            return float((r.stdout or "0").strip().splitlines()[0] or 0)
        except Exception:
            return 0.0
    vd, ad = _sdur("v:0"), _sdur("a:0")
    blk = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf",
         "blackdetect=d=0.2:pic_th=0.98", "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    spans = [(float(a), float(b)) for a, b in
             re.findall(r"black_start:([0-9.]+).*?black_end:([0-9.]+)",
                        blk.stderr or "")]
    # A fade_black outro is DESIGNED black — mask the fade window's tail
    # (mirrors the production integrity gate's outro mask).
    designed_from = (vd - (fade_dur_s + 0.5)) if outro == "fade_black" else None
    stray = [s for s in spans if designed_from is None or s[0] < designed_from]
    skew_ms = round(abs(vd - ad) * 1000, 1)
    return {"v_dur": round(vd, 3), "a_dur": round(ad, 3), "av_skew_ms": skew_ms,
            "black_spans": spans, "stray_black_spans": stray,
            "mech_pass": bool(skew_ms <= 56 and not stray)}


def _gemini_moodreel(system_instruction, user_content):
    """Gemini → HypePlan (SAME schema as hype — the whole point of the re-anchor)."""
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


# ── search-only (for pinning ids) ────────────────────────────────────────────
@app.function(secrets=SECRETS, timeout=300)
def pexels_pick(query: str) -> dict:
    import json, urllib.request, urllib.parse
    key = os.environ.get("PEXELS_API_KEY")
    url = ("https://api.pexels.com/videos/search?query="
           + urllib.parse.quote(query) + "&orientation=portrait&per_page=10&size=medium")
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    out = []
    for v in (data.get("videos") or []):
        out.append({"id": v.get("id"), "duration": v.get("duration"),
                    "w": v.get("width"), "h": v.get("height"),
                    "url": v.get("url")})
    return {"query": query, "candidates": out}


# ── the E2E, one sample ──────────────────────────────────────────────────────
@app.function(secrets=SECRETS, timeout=2400, cpu=8.0, memory=32768)
def render_case(spec: dict) -> dict:
    import time, traceback
    sys.path.insert(0, "/")
    import hype_editor as he
    import hype_render as hr
    import minimal_editor as me
    import moodreel_editor as mr

    name = spec["name"]
    mode = spec.get("mode", "moodreel")
    work = f"/tmp/moodreel/{name}"
    os.makedirs(work, exist_ok=True)
    stage = "init"
    try:
        # 1. source (id-pinned Pexels; its OWN audio or none — nothing added)
        stage = "pexels"
        raw, pmeta = _fetch_pexels(spec["pexels_query"], work)
        raw = _trim_to(raw, work, float(spec.get("max_src_s", 24.0)))
        # 2. canonicalize to 1080x1920@30 (the bridge's contract)
        stage = "normalize"
        canon = hr.normalize_source(raw, os.path.join(work, "canon.mp4"), FPS)
        dur = _duration(canon)
        # 3. perception: motion curve (the mood reel's spine) + scene cuts
        stage = "motion_curve"
        t0 = time.time()
        curve = mr.extract_motion_curve(canon, duration=dur)
        curve_wall = time.time() - t0
        scenes = _scene_cuts(canon)
        peaks, resolves = mr.motion_features(curve)
        # 4. plan
        if mode == "moodreel":
            stage = "prompt"
            sys_i, user_c = mr.build_moodreel_prompt(
                spec.get("vibe") or "", dur, curve, scenes)
            stage = "gemini"
            plan = _gemini_moodreel(sys_i, user_c)
        elif mode == "pair_skiptrim":
            stage = "plan_skiptrim"
            plan = build_skip_trim_plan(dur, curve, fps=FPS)
        elif mode == "pair_motion":
            stage = "plan_motion"
            # THE DEAD CODE GOES LIVE ONLY HERE: motion_curve= is passed inside
            # the sample harness for the pair; the live default call in
            # handler._run_minimal_pipeline stays motion_curve-less.
            plan = me.build_minimal_plan(dur, fps=FPS, motion_curve=curve)
        else:  # "pair_baseline" — the even-2.5s deterministic minimal
            stage = "plan_baseline"
            plan = me.build_minimal_plan(dur, fps=FPS, motion_curve=None)
        # 5. project → caption-less PromptlyRenderInput (the SAME bridge)
        stage = "project"
        ri = he.project_hype_plan(plan, source_url=os.path.basename(canon),
                                  source_fps=FPS, source_duration=dur)

        clip_durs = [c.end_s - c.start_s for c in plan.clips]
        summary = {
            "name": name, "mode": mode, "ok": True,
            "source": pmeta, "src_dur_s": round(dur, 1),
            "out_dur_s": round(ri["totalDurationInFrames"] / FPS, 1),
            "curve_windows": len(curve), "curve_wall_s": round(curve_wall, 2),
            "motion_peaks_s": peaks, "motion_resolves_s": resolves,
            "scene_cuts_s": scenes,
            "n_clips": len(plan.clips),
            "mean_clip_len_s": round(sum(clip_durs) / max(len(clip_durs), 1), 2),
            "clip_spans": [[round(c.start_s, 2), round(c.end_s, 2)] for c in plan.clips],
            "zooms": [{"clip": i, "type": c.zoom, "punch": c.punch}
                      for i, c in enumerate(plan.clips) if c.zoom],
            "speeds_ne_1": [{"clip": i, "speed": c.speed}
                            for i, c in enumerate(plan.clips)
                            if abs(c.speed - 1.0) > 0.005],
            "transitions": [{"after_clip": t.after_clip, "type": t.type}
                            for t in plan.transitions],
            "motion_graphics": [{"type": m.type, "text": m.text}
                                for m in plan.motion_graphics],
            "outro": plan.outro, "notes": plan.notes,
        }

        # 6. render through the REAL primitives + mechanical probe + upload
        try:
            stage = "render"
            out = os.path.join(work, f"{name}.mp4")
            manifest = hr.render_hype(ri, canon, out, work,
                                      public_dir="/remotion/bundle/public",
                                      remotion=True)
            stage = "probe"
            summary["mech"] = _mech_probe(out, outro=(plan.outro or "none"))
            stage = "upload"
            ts = spec.get("ts", "0")
            summary["url"] = _upload(out, f"hype-samples/moodreel/{name}_{ts}.mp4")
            summary["render_manifest"] = manifest
            print(f"[moodreel] {name} DONE → {summary['url']} "
                  f"mech={summary['mech']}", flush=True)
        except Exception as re_:
            summary["render_ok"] = False
            summary["render_stage"] = stage
            summary["render_error"] = f"{type(re_).__name__}: {re_}"
            summary["render_traceback"] = traceback.format_exc()[-2500:]
            print(f"[moodreel] {name} plan OK but render FAILED @{stage}: {re_}",
                  flush=True)
        return summary
    except Exception as e:
        return {"name": name, "mode": mode, "ok": False, "stage": stage,
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc()[-2500:]}


@app.local_entrypoint()
def main():
    import json, time
    ts = str(int(time.time()))
    if os.environ.get("PEXELS_PICK"):
        queries = [q.strip() for q in os.environ["PEXELS_PICK"].split("|") if q.strip()]
        if queries == ["1"]:
            queries = ["fashion model posing studio", "moody city street night rain"]
        for res in pexels_pick.map(queries):
            print(json.dumps(res, indent=2, default=str))
        return
    if os.environ.get("MOODREEL"):
        # The two cinematic mood-reel samples — posed/aesthetic, no confident
        # music (the S-ANYVIDEO class). PINNED ids (reproducibility law):
        #   8893569  = "a model wearing a suit and black boots" (27s, 2160x4096
        #              portrait) — the posed/fashion face of the class
        #   31521814 = "moody urban night cityscape with traffic" (54s,
        #              2160x3840 portrait) — the moody city/landscape face
        specs = [
            {"name": "mood_pose", "ts": ts, "mode": "moodreel", "max_src_s": 24.0,
             "pexels_query": os.environ.get("MOOD_POSE_ID", "id:8893569"),
             "vibe": "a cinematic mood reel — slow, expensive, editorial"},
            {"name": "mood_city", "ts": ts, "mode": "moodreel", "max_src_s": 24.0,
             "pexels_query": os.environ.get("MOOD_CITY_ID", "id:31521814"),
             "vibe": "a moody cinematic city reel — dusk, weight, stillness"},
        ]
        results = list(render_case.map(specs))
        print("\n================ MOODREEL RESULTS ================")
        for r in results:
            print(json.dumps(r, indent=2, default=str))
        print("==================================================")
        return
    if os.environ.get("MOODPAIRS"):
        # Ruling 4b: two minimal A/B pairs on ONE pinned source.
        #   29583716 = "rainy night street scene with lights and mountains"
        #              (53s, 2160x3840 portrait) — aesthetic no-speech with
        #              genuinely varying motion (rain, traffic, light)
        src = os.environ.get("MOODPAIR_ID", "id:29583716")
        specs = [
            {"name": "pair1_baseline", "ts": ts, "mode": "pair_baseline",
             "max_src_s": 22.0, "pexels_query": src},
            {"name": "pair1_skiptrim", "ts": ts, "mode": "pair_skiptrim",
             "max_src_s": 22.0, "pexels_query": src},
            {"name": "pair2_even", "ts": ts, "mode": "pair_baseline",
             "max_src_s": 22.0, "pexels_query": src},
            {"name": "pair2_motion", "ts": ts, "mode": "pair_motion",
             "max_src_s": 22.0, "pexels_query": src},
        ]
        results = list(render_case.map(specs))
        print("\n================ MOOD PAIR RESULTS ================")
        for r in results:
            print(json.dumps(r, indent=2, default=str))
        print("===================================================")
        return
    print("Set PEXELS_PICK=1 | MOODREEL=1 | MOODPAIRS=1 (see module docstring).")
