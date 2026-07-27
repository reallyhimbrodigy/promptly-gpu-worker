"""Caption chunking A/B — render the SAME source at word-by-word (max_words=2, the
current default) vs phrase-level (4, 5) and return the render URLs for an eyeball pair.
This is the caption workstream's lever 1 (per advisor): phrase chunking gives each
caption CHANGE real visual mass. Presentation deliverable, not a density measurement —
n=1 per arm, but the loud degradation guard still applies (never eyeball a rescued render).
"""
import os, sys
sys.path.insert(0, "/")   # container mounts modal_app.py at /modal_app.py; / not on path at import
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-caption-chunk", image=image)
SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-lang-flags"),
]
# Real captioned showcase source (ca6202f9, 20s, "Clean and engaging edit").
SHOWCASE = "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785106634357-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=2400)
def run_arm(arm: dict) -> dict:
    import time, uuid, traceback, io
    if arm.get("stagger_s"):
        time.sleep(float(arm["stagger_s"]))
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H
    _render_key = f"caption-chunk-cert/{arm['job_id']}/render.mp4"
    _url = f"https://thisismybucketagainwooo.s3.amazonaws.com/{_render_key}"
    body = {
        "job_id": arm["job_id"],
        "video_url": arm["src"],
        "vibe": arm.get("vibe", "Clean and engaging edit"),
        "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
        "upload_url": _url,
        "public_url": _url,
        "model": "flare",
        "supports_progressive": False,
        "premium_pipeline_enabled": False,
    }
    if arm.get("caption_max_words"):
        body["caption_max_words"] = int(arm["caption_max_words"])
    t0 = time.time()
    _buf = io.StringIO(); _orig = sys.stdout
    class _Tee:
        def write(self, s):
            try: _orig.write(s)
            except Exception: pass
            _buf.write(s); return len(s)
        def flush(self):
            try: _orig.flush()
            except Exception: pass
    sys.stdout = _Tee()
    try:
        res = H.handler({"input": body})
    except Exception as e:
        sys.stdout = _orig
        return {"arm": arm["label"], "error": f"{type(e).__name__}: {str(e)[:300]}",
                "tb": traceback.format_exc()[-800:], "wall_s": round(time.time() - t0, 1)}
    finally:
        sys.stdout = _orig
    _logs = _buf.getvalue()
    _DEGRADE = ["[safe-edit] engaged", "safe_edit_rescue", "action=safe_edit",
                "[render-degrade]", "render_stripped", "[error-fallback]", "error-fallback]",
                "outer:UNKNOWN"]
    _hits = sorted({m for m in _DEGRADE if m in _logs})
    rec = res.get("edit_recipe") if isinstance(res, dict) else None
    # count caption pages + their word-lengths (proves the chunking actually changed)
    pages = (rec or {}).get("caption_pages") if isinstance(rec, dict) else None
    pg = None
    if isinstance(pages, list) and pages:
        wl = [len((p.get("text") or "").split()) for p in pages if isinstance(p, dict)]
        pg = {"n_pages": len(pages), "mean_words": round(sum(wl) / len(wl), 2) if wl else 0,
              "max_words": max(wl) if wl else 0, "hist": {k: wl.count(k) for k in sorted(set(wl))}}
    # Extract eyeball frames at fixed timestamps (SAME across arms → direct chunk compare).
    # The cert bucket is private, so pull the render back via the container's OWN creds.
    frames_b64 = {}
    vurl = res.get("video_url") if isinstance(res, dict) else None
    if vurl:
        try:
            import base64, subprocess, tempfile
            b, k = H._parse_aws_s3_url(vurl)
            if b and k and getattr(H, "_aws_s3_client", None) is not None:
                tmp = os.path.join(tempfile.mkdtemp(), "r.mp4")
                H._aws_s3_client.download_file(b, k, tmp)
                for ts in (5, 9, 13, 17):
                    fp = os.path.join(tempfile.mkdtemp(), "f.png")
                    subprocess.run(["ffmpeg", "-nostats", "-loglevel", "error", "-ss", str(ts),
                                    "-i", tmp, "-frames:v", "1", "-vf", "scale=337:600", fp, "-y"], check=False)
                    if os.path.exists(fp):
                        with open(fp, "rb") as f:
                            frames_b64[f"t{ts}"] = base64.b64encode(f.read()).decode()
        except Exception as _fe:
            frames_b64 = {"error": str(_fe)[:200]}
    return {
        "arm": arm["label"],
        "status": res.get("status") if isinstance(res, dict) else "?",
        "degraded_markers": _hits,
        "raw_error": (res.get("error") or res.get("error_code")) if isinstance(res, dict) else None,
        "video_url": res.get("video_url") if isinstance(res, dict) else None,
        "caption_pages": pg,
        "frames_b64": frames_b64,
        "wall_s": round(time.time() - t0, 1),
    }


@app.local_entrypoint()
def main():
    import json, uuid
    arms = [
        {"label": "wordbyword_2", "caption_max_words": 2, "src": SHOWCASE, "job_id": str(uuid.uuid4()), "stagger_s": 0},
        {"label": "phrase_4",     "caption_max_words": 4, "src": SHOWCASE, "job_id": str(uuid.uuid4()), "stagger_s": 15},
        {"label": "phrase_5",     "caption_max_words": 5, "src": SHOWCASE, "job_id": str(uuid.uuid4()), "stagger_s": 30},
    ]
    print("=== CAPTION CHUNK A/B — word-by-word(2) vs phrase(4) vs phrase(5) ===")
    out = list(run_arm.map(arms))
    fails = []
    for r in out:
        print(f"\n--- {r.get('arm')} ---")
        if r.get("error"):
            print("  ERROR:", r["error"]); print("  tb:", r.get("tb", "")[-400:])
            fails.append(f"{r.get('arm')}: {r.get('error')}")
        else:
            print("  status:", r.get("status"), "degraded:", r.get("degraded_markers"))
            print("  wall_s:", r.get("wall_s"))
            print("  CAPTION_PAGES:", json.dumps(r.get("caption_pages")))
            print("  VIDEO:", r.get("video_url"))
            if r.get("degraded_markers"):
                fails.append(f"{r.get('arm')}: DEGRADED {r['degraded_markers']} — render invalid")
            if not r.get("video_url"):
                fails.append(f"{r.get('arm')}: no video_url (raw_error={r.get('raw_error')})")
    if fails:
        raise RuntimeError("CAPTION CHUNK A/B INVALID:\n  " + "\n  ".join(fails))
    print("\n=== RENDER URLS ===")
    for r in out:
        print(f"{r['arm']}: {r.get('video_url')}")
    # save eyeball frames locally (main runs on the client machine)
    import base64
    outdir = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/caption_frames"
    os.makedirs(outdir, exist_ok=True)
    saved = 0
    for r in out:
        for ts, b64 in (r.get("frames_b64") or {}).items():
            if ts == "error":
                print(f"  frame error {r['arm']}: {b64}"); continue
            with open(os.path.join(outdir, f"{r['arm']}_{ts}.png"), "wb") as f:
                f.write(base64.b64decode(b64)); saved += 1
    print(f"\nFRAMES: saved {saved} to {outdir}")
