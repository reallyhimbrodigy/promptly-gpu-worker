"""CONTROLLED BLUR A/B + hqdn3d + fidelity (Zac 2026-07-28). Standard benchmark
source c8c8264e (1080x1920/30fps/12.6Mbps, bpp=0.203 — the clean end; 41s, 3.3 wps).
Arm A: mode=full, blur OFF -> capture the edit recipe. Arm B: mode=render_only on
that SAME recipe, blur ON at s3_sh180 (samples=3 shutter=180). Identical edit, only
blur differs, frames align. ffprobe both (1080x1920/30, CRF), pull 100% crops during
motion for the hqdn3d trail check. Both on v385 (post-cutter-fix)."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-blur-ab", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/0f739aeb-a5e1-458d-a117-eb326841b069/1785241163074-2BE40123-3749-4120-8902-D1B5BBC28552_L0_001.mp4"
SRC_JOB = "c8c8264e"


@app.function(secrets=SECRETS, cpu=32.0, memory=131072, timeout=2400)  # render needs the production 128GB (Remotion overlay+micro + ffmpeg composite); 32GB OOM'd
def run() -> dict:
    import time, uuid, traceback, tempfile, subprocess, base64
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H

    def _render(arm, mode, edit_plan, blur_on):
        jid = str(uuid.uuid4())
        url = f"https://thisismybucketagainwooo.s3.amazonaws.com/blur-ab/{arm}/{jid}/out.mp4"
        # blur control: arm A forces OFF (override the live PROMPTLY_MOTION_BLUR=1);
        # arm B forces ON via motion_blur_test s3_sh180 (independent of env).
        os.environ["PROMPTLY_MOTION_BLUR"] = "1" if blur_on else ""
        body = {"job_id": jid, "video_url": SRC, "vibe": "Clean engaging edit",
                "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url,
                "public_url": url, "model": "flare", "supports_progressive": False,
                "premium_pipeline_enabled": False, "mode": mode}
        if edit_plan is not None:
            body["edit_plan"] = edit_plan
        if blur_on:
            body["motion_blur_test"] = True
            body["motion_blur_samples"] = 3
            body["motion_blur_shutter"] = 180
        t0 = time.time()
        res = H.handler({"input": body})
        r = res if isinstance(res, dict) else {}
        return {"arm": arm, "status": r.get("status"), "video_url": r.get("video_url"),
                "edit_recipe": r.get("edit_recipe"), "removed_word_reasons": (r.get("edit_recipe") or {}).get("_removed_word_reasons") if isinstance(r.get("edit_recipe"), dict) else None,
                "wall_s": round(time.time() - t0, 1), "err": r.get("error") or r.get("code")}

    out = {}
    try:
        # Arm A — fresh plan, blur OFF
        a = _render("A_blur_off", "full", None, False)
        out["arm_a"] = {k: a[k] for k in ("status", "video_url", "wall_s", "err")}
        plan = a.get("edit_recipe")
        if a.get("status") != "success" or not plan:
            out["error"] = f"arm A failed: {a.get('err')} status={a.get('status')}"
            return out
        # Arm B — SAME recipe (render_only), blur ON s3_sh180
        b = _render("B_blur_on_s3sh180", "render_only", plan, True)
        out["arm_b"] = {k: b[k] for k in ("status", "video_url", "wall_s", "err")}
        # fidelity + frames for both delivered outputs
        for tag, res in (("A", a), ("B", b)):
            vurl = res.get("video_url")
            if not vurl:
                continue
            try:
                bkt, key = H._parse_aws_s3_url(vurl)
                loc = os.path.join(tempfile.mkdtemp(), "o.mp4")
                H._aws_s3_client.download_file(bkt, key, loc)
                pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height,r_frame_rate,codec_name,nb_frames,bit_rate:format=duration",
                     "-of", "json", loc], capture_output=True, text=True)
                out.setdefault("fidelity", {})[tag] = json.loads(pr.stdout or "{}")
                # 100% crops at 3 motion timestamps for the hqdn3d trail + blur read
                dur = float(json.loads(pr.stdout)["format"]["duration"])
                frames = {}
                for frac in (0.30, 0.55, 0.80):
                    ts = dur * frac
                    fp = os.path.join(tempfile.mkdtemp(), "f.png")
                    # full-res crop of the center-motion region (no downscale = 100% crop)
                    subprocess.run(["ffmpeg", "-nostats", "-loglevel", "error", "-ss", f"{ts:.2f}",
                        "-i", loc, "-frames:v", "1", "-vf", "crop=1080:720:0:600", fp, "-y"], check=False)
                    if os.path.exists(fp):
                        frames[f"t{ts:.1f}"] = base64.b64encode(open(fp, "rb").read()).decode()
                out.setdefault("frames", {})[tag] = frames
            except Exception as e:
                out.setdefault("measure_err", {})[tag] = str(e)[:160]
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        out["tb"] = traceback.format_exc()[-600:]
        return out


@app.local_entrypoint()
def main():
    print(f"=== CONTROLLED BLUR A/B on benchmark {SRC_JOB} (1080x1920/30, bpp=0.203) ===")
    o = run.remote()
    assert o, "no result"
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/blur_ab"
    os.makedirs(SCR, exist_ok=True)
    if o.get("error"):
        print("ERROR:", o["error"]); print("tb:", o.get("tb", "")); raise SystemExit("blur A/B failed")
    print("Arm A (blur OFF):", json.dumps(o.get("arm_a"), indent=None))
    print("Arm B (blur ON s3_sh180):", json.dumps(o.get("arm_b"), indent=None))
    print("Fidelity:", json.dumps(o.get("fidelity"), indent=None)[:600])
    import base64
    for tag, frames in (o.get("frames") or {}).items():
        for ts, b in frames.items():
            open(os.path.join(SCR, f"{tag}_{ts}.png"), "wb").write(base64.b64decode(b))
    print(f"100% crops -> {SCR} (compare A vs B at matching timestamps for blur + hqdn3d trails)")
    json.dump({k: v for k, v in o.items() if k != "frames"}, open(os.path.join(SCR, "result.json"), "w"), indent=2)
    print("\nBLUR A/B COMPLETE — arm_a.video_url and arm_b.video_url are the side-by-side deliverables.")
