"""TRUE-REPLAY BLUR A/B (Zac 2026-07-28, $0.75 approved, redesign).

render_only was proven NOT a pure replay (it re-runs normalize+transcribe and
re-validates -> 7-frame drift). This isolates blur WITHOUT the pipeline: run the
full pipeline ONCE, and at the render_multi_clip call MONKEYPATCH-CAPTURE its
fully-staged args (source_path, cuts, edit_plan, transcript, work_dir, broll all
prepared), then call the REAL render_multi_clip 3x on BYTE-IDENTICAL inputs,
toggling ONLY edit_plan["_motion_blur"]:
    OFF   -> out_OFF.mp4     (blur disabled)
    OFF2  -> out_OFF2.mp4    (blur disabled AGAIN — DETERMINISM PROOF)
    ON    -> out_ON.mp4      (s3_sh180: samples=3, shutter=180)
Because it is the SAME deterministic function on identical inputs, the outputs
are frame-locked; the only pixel difference OFF->ON is the blur. The harness is
SELF-VALIDATING: if OFF and OFF2 are not frame/pixel-identical the render is
nondeterministic and blur CANNOT be pixel-isolated — we report that honestly.

Source: 28f03ca9 — picked by data (10 blur sites: 5 composite zooms + 5 motion
graphics), a motion-rich edit, NOT the c8c8264e locked-off tripod. Crops are
taken at the edit_plan's ACTUAL blur-site timestamps (extracted from cuts), not
random fractions."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-blur-truereplay", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/e9b47b30-5edf-4bc6-825a-7d2a8fe1a43d/1785239363288-A2A4B085-5918-4575-BB13-CC3CD92EF816_L0_001.mp4"
SRC_JOB = "28f03ca9"


@app.function(secrets=SECRETS, cpu=32.0, memory=131072, timeout=3000)
def run() -> dict:
    import time, uuid, traceback, tempfile, subprocess, base64, copy, re
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_MOTION_BLUR"] = ""  # neutralize live env; blur is controlled PER-ARM
    sys.path.insert(0, "/")
    import handler as H

    RESULT = {"src_job": SRC_JOB}

    class _CaptureDone(BaseException):  # BaseException so the handler's `except
        pass                            # Exception` can't swallow it -> no rescue re-run, no error-write

    _orig_render = H.render_multi_clip

    def _blur_site_timestamps(cuts):
        """edit-relative timestamps where CameraMotionBlur fires (zoom mid / transition end)."""
        marks, dest = [], 0.0
        for c in (cuts or []):
            span = float(c.get("source_end", 0) or 0) - float(c.get("source_start", 0) or 0)
            dur = span / float(c.get("speed", 1) or 1)
            if c.get("_zoom_effect"):
                marks.append(round(dest + dur * 0.5, 2))
            to = c.get("transition_out")
            if to and to not in ("none", "cut", "hard"):
                marks.append(round(dest + dur, 2))
            dest += dur
        return marks or [round(dest * f, 2) for f in (0.25, 0.5, 0.75)]

    def _probe(p):
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries", "stream=nb_read_frames,width,height,r_frame_rate,codec_name,bit_rate:format=duration",
             "-of", "json", p], capture_output=True, text=True)
        try:
            j = json.loads(pr.stdout or "{}"); s = (j.get("streams") or [{}])[0]
            return {"nb_frames": s.get("nb_read_frames"), "w": s.get("width"), "h": s.get("height"),
                    "fps": s.get("r_frame_rate"), "codec": s.get("codec_name"),
                    "bitrate": s.get("bit_rate"), "dur": (j.get("format") or {}).get("duration")}
        except Exception:
            return {"err": pr.stderr[-200:]}

    def _frame(p, ts):
        fp = os.path.join(tempfile.mkdtemp(), f"f_{int(ts*100)}.png")
        subprocess.run(["ffmpeg", "-nostats", "-loglevel", "error", "-ss", f"{ts:.2f}", "-i", p,
            "-frames:v", "1", "-vf", "crop=1080:720:0:600", fp, "-y"], check=False)
        return fp if os.path.exists(fp) else None

    def _psnr(a, b):
        """PSNR between two PNG frames; 'inf' => pixel-identical."""
        pr = subprocess.run(["ffmpeg", "-i", a, "-i", b, "-lavfi", "psnr", "-f", "null", "-"],
                            capture_output=True, text=True)
        m = re.search(r"average:(inf|[0-9.]+)", pr.stderr or "")
        return m.group(1) if m else "?"

    def _upload(local, arm, jid):
        key = f"blur-truereplay/{arm}/{jid}/out.mp4"
        H._aws_s3_client.upload_file(local, "thisismybucketagainwooo", key,
                                     Config=H._S3_TRANSFER_CONFIG)
        return f"https://thisismybucketagainwooo.s3.amazonaws.com/{key}"

    def _spy(*args, **kwargs):
        source_path, cuts, edit_plan, output_path, transcript, work_dir = args[:6]
        jid = str(uuid.uuid4())
        marks = _blur_site_timestamps(cuts)
        RESULT["blur_site_ts"] = marks
        RESULT["captured"] = True
        arms = [("OFF", {"enabled": False}),
                ("OFF2", {"enabled": False}),
                ("ON", {"enabled": True, "samples": 3, "shutter": 180})]
        outs, walls = {}, {}
        for name, blur in arms:
            ep = copy.deepcopy(edit_plan); ep["_motion_blur"] = blur
            outp = os.path.join(work_dir, f"out_{name}.mp4")
            t0 = time.time()
            _orig_render(source_path, copy.deepcopy(cuts), ep, outp, transcript,
                         work_dir, **kwargs)
            walls[name] = round(time.time() - t0, 1)
            outs[name] = outp
        RESULT["render_wall_s"] = walls
        RESULT["probe"] = {n: _probe(p) for n, p in outs.items()}
        # frame-lock proof
        nf = {n: RESULT["probe"][n].get("nb_frames") for n in outs}
        RESULT["frame_locked"] = (nf["OFF"] == nf["OFF2"] == nf["ON"] and nf["OFF"] is not None)
        # per-timestamp PSNR: OFF-vs-OFF2 (determinism) and OFF-vs-ON (blur delta)
        psnr_det, psnr_blur, crops = {}, {}, {}
        for ts in marks[:6]:
            fo, fo2, fn = _frame(outs["OFF"], ts), _frame(outs["OFF2"], ts), _frame(outs["ON"], ts)
            if fo and fo2:
                psnr_det[f"t{ts}"] = _psnr(fo, fo2)
            if fo and fn:
                psnr_blur[f"t{ts}"] = _psnr(fo, fn)
                crops[f"OFF_t{ts}"] = base64.b64encode(open(fo, "rb").read()).decode()
                crops[f"ON_t{ts}"] = base64.b64encode(open(fn, "rb").read()).decode()
        RESULT["psnr_determinism_OFFvsOFF2"] = psnr_det
        RESULT["psnr_blur_OFFvsON"] = psnr_blur
        RESULT["crops"] = crops
        # deliverable URLs
        RESULT["arm_urls"] = {"OFF": _upload(outs["OFF"], "OFF", jid),
                              "ON": _upload(outs["ON"], "ON", jid)}
        raise _CaptureDone()

    H.render_multi_clip = _spy
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/blur-truereplay/main/{jid}/out.mp4"
    body = {"job_id": jid, "video_url": SRC,
            "vibe": "High-energy viral edit with punchy zooms and emphasis",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url,
            "public_url": url, "model": "flare", "supports_progressive": False,
            "premium_pipeline_enabled": False, "mode": "full"}
    try:
        H.handler({"input": body})
    except _CaptureDone:
        pass  # expected: spy captured + rendered 3 arms, then bailed the pipeline
    except Exception as e:
        RESULT["pipeline_err"] = f"{type(e).__name__}: {str(e)[:300]}"
        RESULT["tb"] = traceback.format_exc()[-900:]
    finally:
        H.render_multi_clip = _orig_render
    if not RESULT.get("captured"):
        RESULT["warn"] = "spy never ran — pipeline did not reach render_multi_clip"
    return RESULT


@app.local_entrypoint()
def main():
    print(f"=== TRUE-REPLAY BLUR A/B on motion-rich {SRC_JOB} (3 renders: OFF/OFF2/ON) ===")
    o = run.remote()
    assert o, "no result"
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/blur_truereplay"
    os.makedirs(SCR, exist_ok=True)
    if o.get("pipeline_err"):
        print("PIPELINE ERROR:", o["pipeline_err"]); print("tb:", o.get("tb", ""))
    print("captured:", o.get("captured"), "| warn:", o.get("warn"))
    print("blur_site_ts:", o.get("blur_site_ts"))
    print("frame_locked:", o.get("frame_locked"))
    print("probe:", json.dumps(o.get("probe"), indent=None))
    print("render_wall_s:", json.dumps(o.get("render_wall_s")))
    print("PSNR determinism (OFF vs OFF2, want inf/high):", json.dumps(o.get("psnr_determinism_OFFvsOFF2")))
    print("PSNR blur (OFF vs ON, lower=more blur delta):", json.dumps(o.get("psnr_blur_OFFvsON")))
    print("arm_urls:", json.dumps(o.get("arm_urls")))
    import base64
    for tag, b in (o.get("crops") or {}).items():
        open(os.path.join(SCR, f"{tag}.png"), "wb").write(base64.b64decode(b))
    print(f"crops -> {SCR}")
    json.dump({k: v for k, v in o.items() if k != "crops"}, open(os.path.join(SCR, "result.json"), "w"), indent=2)
    print("\nTRUE-REPLAY BLUR A/B COMPLETE.")
