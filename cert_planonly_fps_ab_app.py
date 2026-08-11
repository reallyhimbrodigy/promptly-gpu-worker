"""PLAN_ONLY A/B: Gemini proxy 18fps vs 2fps+media_resolution LOW (Zac 2026-08-04).

Per-job override (proxy_sample_fps / media_resolution), inert for real traffic.
Runs the pipeline to the edit_plan TWICE on the SAME source, capturing at
render_multi_clip (bail before render — PLAN_ONLY), toggling ONLY the Gemini
sample fps + media_resolution:
    fps18_default -> proxy_sample_fps=18 (env default), media MEDIUM
    fps2_low      -> proxy_sample_fps=2,  media_resolution=LOW

Reports THREE things (Zac):
 1. token drop         (prompt / uncached_delta; expected ~253K -> ~28K)
 2. Gemini leg wall-s  (sum of non-aborted _GEMINI_CALL_LOG total_s; 155s -> 20-40s)
 3. quality signal     (zoom count + emphasis/MG count + their timestamps — do
                        zooms & emphasis SURVIVE 2fps sampling? cuts are safe by
                        construction, mechanical from Deepgram+VAD)

The override taking effect (token drop) FUNCTIONALLY verifies the flag code is
live — which commit-truth cannot under the deploy churn. cpu=16, ~$0.20-0.40.
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-planonly-fps-ab", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/e9b47b30-5edf-4bc6-825a-7d2a8fe1a43d/1785239363288-A2A4B085-5918-4575-BB13-CC3CD92EF816_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=1800)
def run() -> dict:
    import time, uuid, traceback, copy
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    # neutralize any live prod env for these flags — control PER-ARM only
    os.environ.pop("PROMPTLY_PROXY_SAMPLE_FPS", None)
    os.environ.pop("PROMPTLY_MEDIA_RESOLUTION", None)
    sys.path.insert(0, "/")
    import handler as H
    RESULT = {"arms": {}}

    class _CaptureDone(BaseException):
        pass

    _orig_render = H.render_multi_clip
    _cur = {"arm": None}

    def _zoom_ts(cuts):
        ts, dest = [], 0.0
        for c in (cuts or []):
            span = float(c.get("source_end", 0) or 0) - float(c.get("source_start", 0) or 0)
            dur = span / float(c.get("speed", 1) or 1)
            if c.get("_zoom_effect"):
                ts.append(round(dest, 1))
            dest += dur
        return ts

    def _spy(*args, **kwargs):
        source_path, cuts, edit_plan = args[0], args[1], args[2]
        arm = _cur["arm"]
        em = (edit_plan.get("emphasis_moments") if isinstance(edit_plan, dict) else None) or []
        mg = [e for e in em if isinstance(e, dict) and e.get("motion_graphic")]
        calls = [c for c in getattr(H, "_GEMINI_CALL_LOG", []) if isinstance(c, dict)]
        gemini_s = round(sum(c.get("total_s") or 0 for c in calls if not c.get("aborted")), 1)
        RESULT["arms"][arm] = {
            "tokens": H._gemini_token_summary(),
            "gemini_leg_s": gemini_s,
            "n_calls": len(calls),
            "n_zoom": len(_zoom_ts(cuts)),
            "zoom_ts": _zoom_ts(cuts)[:12],
            "n_emphasis": len(em),
            "n_motion_graphic": len(mg),
            "emphasis_ts": [round(float(e.get("t", 0) or 0), 1) for e in em[:12] if isinstance(e, dict)],
        }
        raise _CaptureDone()

    H.render_multi_clip = _spy
    for arm, ov in [("fps18_default", {}),
                    ("fps2_low", {"proxy_sample_fps": 2, "media_resolution": "MEDIA_RESOLUTION_LOW"})]:
        _cur["arm"] = arm
        try:
            H._GEMINI_CALL_LOG.clear()
        except Exception:
            pass
        jid = str(uuid.uuid4())
        url = f"https://thisismybucketagainwooo.s3.amazonaws.com/planonly-fps/{arm}/{jid}/out.mp4"
        body = {"job_id": jid, "video_url": SRC,
                "vibe": "High-energy viral edit with punchy zooms and emphasis",
                "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url,
                "public_url": url, "model": "flare", "supports_progressive": False,
                "premium_pipeline_enabled": False, "mode": "full"}
        body.update(ov)
        t0 = time.time()
        try:
            H.handler({"input": body})
        except _CaptureDone:
            pass
        except Exception as e:
            RESULT["arms"][arm] = {"err": f"{type(e).__name__}: {str(e)[:300]}",
                                   "tb": traceback.format_exc()[-700:]}
        RESULT.setdefault("wall", {})[arm] = round(time.time() - t0, 1)
    H.render_multi_clip = _orig_render
    return RESULT


@app.local_entrypoint()
def main():
    print("=== PLAN_ONLY A/B: Gemini proxy 18fps vs 2fps+LOW ===")
    o = run.remote()
    a = (o or {}).get("arms", {})
    for arm in ("fps18_default", "fps2_low"):
        d = a.get(arm, {})
        print(f"\n[{arm}]  pipeline_wall={o.get('wall', {}).get(arm)}s")
        if d.get("err"):
            print("  ERROR:", d["err"]); print("  tb:", d.get("tb", "")); continue
        t = d.get("tokens") or {}
        print(f"  tokens: prompt={t.get('prompt')} uncached_delta={t.get('uncached_delta')} out={t.get('output')} (n_calls={d.get('n_calls')})")
        print(f"  GEMINI LEG wall: {d.get('gemini_leg_s')}s")
        print(f"  zooms={d.get('n_zoom')} @ {d.get('zoom_ts')}")
        print(f"  emphasis={d.get('n_emphasis')} (motion_graphic={d.get('n_motion_graphic')}) @ {d.get('emphasis_ts')}")
    # deltas
    A, B = a.get("fps18_default", {}), a.get("fps2_low", {})
    if A.get("tokens") and B.get("tokens"):
        pa, pb = A["tokens"].get("prompt", 0), B["tokens"].get("prompt", 0)
        print(f"\n  === TOKEN DROP: {pa} -> {pb} ({100*(pa-pb)/pa:.0f}% fewer)  [override took effect => flag code IS LIVE]" if pa else "")
        ga, gb = A.get("gemini_leg_s", 0), B.get("gemini_leg_s", 0)
        print(f"  === GEMINI LEG: {ga}s -> {gb}s ({ga-gb:+.0f}s)")
        print(f"  === QUALITY: zooms {A.get('n_zoom')}->{B.get('n_zoom')}, emphasis {A.get('n_emphasis')}->{B.get('n_emphasis')}, MG {A.get('n_motion_graphic')}->{B.get('n_motion_graphic')}")
        print("      (survive => flip is safe; collapse => 2fps too coarse for placement)")
    print("\nPLAN_ONLY A/B COMPLETE.")
