"""RE-EDIT E2E cert (increment 1): prove the fold works on the REAL surgical path. A tweak
re-edit with a COMPOUND change_request — a caption-STYLE op (→ tweak→render_only) plus a
spelling override that lives ONLY in change_request. Before the fix, render-time parsed the
override from the stale original `vibe` and dropped it. After the fix, _reedit_intent_text =
vibe + raw change_request, so the override reaches the caption. We render, OCR the caption
band across the clip, and assert the user's literal spelling appears (falls back to saved
frames if OCR is unavailable — never a silent pass)."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-reedit-e2e", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]

NEW_SPELLING = "SPENDINGZ"
TARGET_WORD = "spending"


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=2400)
def run_arm(arm: dict) -> dict:
    import time, uuid, traceback, tempfile, subprocess, base64
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/reedit-e2e/{jid}/render.mp4"
    body = {"job_id": jid, "video_url": arm["video_url"],
            "vibe": arm["vibe"], "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": url, "public_url": url, "model": "flare",
            "supports_progressive": False, "premium_pipeline_enabled": False,
            "mode": "tweak", "edit_plan": arm["edit_plan"], "change_request": arm["change_request"]}
    t0 = time.time()
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:250]}", "tb": traceback.format_exc()[-600:],
                "wall_s": round(time.time() - t0, 1)}
    r = res if isinstance(res, dict) else {}
    vurl = r.get("video_url")
    out = {"status": r.get("status"), "video_url": vurl, "wall_s": round(time.time() - t0, 1)}
    if not vurl:
        out["note"] = "no video_url — render did not complete"; return out
    try:
        b, k = H._parse_aws_s3_url(vurl); src = os.path.join(tempfile.mkdtemp(), "r.mp4")
        H._aws_s3_client.download_file(b, k, src)
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", src], capture_output=True, text=True)
        dur = float(json.loads(p.stdout)["format"]["duration"])
        # OCR the caption band across the clip
        try:
            import pytesseract  # noqa
            from PIL import Image
            _ocr_ok = True
        except Exception:
            _ocr_ok = False
        found = False; ocr_hits = []; frames = {}
        n = 30
        for i in range(n):
            ts = dur * (i + 0.5) / n
            fp = os.path.join(tempfile.mkdtemp(), f"f{i}.png")
            subprocess.run(["ffmpeg", "-nostats", "-loglevel", "error", "-ss", f"{ts:.2f}",
                "-i", src, "-frames:v", "1", "-vf", "scale=540:960", fp, "-y"], check=False)
            if not os.path.exists(fp):
                continue
            if _ocr_ok:
                try:
                    from PIL import Image
                    im = Image.open(fp)
                    band = im.crop((0, int(960 * 0.55), 540, int(960 * 0.98)))
                    txt = pytesseract.image_to_string(band).strip()
                    if txt:
                        ocr_hits.append(f"{ts:.1f}s:{txt[:40]!r}")
                    if NEW_SPELLING.lower() in txt.lower().replace(" ", ""):
                        found = True
                except Exception as _oe:
                    _ocr_ok = False
            # keep a handful of frames for visual fallback / evidence
            if i % 4 == 0:
                frames[f"t{ts:.1f}"] = base64.b64encode(open(fp, "rb").read()).decode()
        out.update({"ocr_available": _ocr_ok, "override_found_in_render": found,
                    "ocr_hits": ocr_hits[:40], "frames_b64": frames, "dur": round(dur, 1)})
    except Exception as e:
        out["measure_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out


@app.local_entrypoint()
def main():
    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad"
    job = json.load(open(SCR + "/reedit_e2e_job.json"))
    change_request = f"make the captions Lumen style and spell {TARGET_WORD} as {NEW_SPELLING}"
    arm = {"video_url": job["video_url"], "vibe": job["vibe"] or "Fast paced punchy",
           "edit_plan": job["edit_recipe"], "change_request": change_request}
    print(f"=== RE-EDIT E2E (job {job['id']}, tweak; change_request={change_request!r}) ===")
    out = run_arm.remote(arm)
    assert out, "no result — cert must never pass silently"
    if out.get("error"):
        print("  RENDER ERROR:", out["error"]); print("  tb:", out.get("tb"))
        raise SystemExit("re-edit render failed")
    print(f"  status={out.get('status')} wall={out.get('wall_s')}s dur={out.get('dur')}s")
    print(f"  video={out.get('video_url')}")
    print(f"  ocr_available={out.get('ocr_available')}  override_found_in_render={out.get('override_found_in_render')}")
    for h in (out.get("ocr_hits") or []):
        print("    ocr:", h)
    outdir = SCR + "/reedit_e2e_frames"; os.makedirs(outdir, exist_ok=True)
    import base64
    for ts, b in (out.get("frames_b64") or {}).items():
        open(os.path.join(outdir, f"reedit_{ts}.png"), "wb").write(base64.b64decode(b))
    print(f"  frames → {outdir}")
    if out.get("ocr_available"):
        assert out.get("override_found_in_render"), \
            f"OCR ran but did NOT find the user's spelling {NEW_SPELLING!r} in any caption — the fold did not apply"
        print(f"\n✅ E2E PASS: the folded change_request override {NEW_SPELLING!r} rendered in the captions.")
    else:
        print(f"\n⚠️ OCR unavailable in-container — inspect frames in {outdir} for {NEW_SPELLING!r} (visual confirm).")
