"""PLAN_ONLY corpus A/B — proxy 18fps/MEDIUM vs 2fps/MEDIA_RESOLUTION_LOW.
STAGED FOR IGNITION (lane/delivery 2026-08-11). DO NOT RUN until the Vertex
canary passes — the 2026-08-08 GCP dunning outage makes every plan leg fall to
safe_edit (n_calls=0), which is exactly how the single-source run on 08-10 went
vacuous. This runner makes that impossible to miss: Phase 0 is a one-source
canary that HARD-ABORTS unless gemini_n_calls > 0.

Corpus: fps_ab_corpus_manifest.json — HARNESS's 25-source frozen manifest
(golden/manifest.json @ frozen_at_commit 1601ae0, all sources carry video_url;
constructed durable sources per the A/B-sources law, never live user media).

Arms (per source, PLAN_ONLY per-job overrides — zero flag flips, inert to prod):
    A fps18_default : proxy_sample_fps=18, media MEDIUM      (prod today)
    B fps2_low      : proxy_sample_fps=2,  MEDIA_RESOLUTION_LOW (the lever)

Per-source report: prompt/uncached tokens, Gemini leg wall, zoom/emphasis/MG
counts + timestamps, safe-edit flag. Flip bar: B's plans keep zoom/emphasis
placement (survival, not identity) at ~9x fewer video tokens.

COST (state before running): ~$0.10-0.20 per source (both arms, cpu=16,
plan-only). Default N_SOURCES=8 ≈ $1-2; full 25 ≈ $3-5. Runs sequentially in
ONE container; synchronous .remote() — no spawn orphans.

IGNITION:  modal run cert_planonly_fps_ab_corpus_app.py            (canary+8)
           N_SOURCES=25 modal run cert_planonly_fps_ab_corpus_app.py  (full)
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = (modal_app.image
         .add_local_file("modal_app.py", "/modal_app.py")
         .add_local_file("fps_ab_corpus_manifest.json", "/fps_ab_corpus_manifest.json"))
app = modal.App("cert-planonly-fps-ab-corpus", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]

N_SOURCES = int(os.environ.get("N_SOURCES", "8") or "8")


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=3000)
def run(n_sources: int) -> dict:
    import time, uuid, traceback
    from build_lane import mark_build_lane
    mark_build_lane("cert_planonly_fps_ab_corpus_app.py")
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    # per-arm control ONLY — neutralize any live values for the two lever flags
    os.environ.pop("PROMPTLY_PROXY_SAMPLE_FPS", None)
    os.environ.pop("PROMPTLY_MEDIA_RESOLUTION", None)
    sys.path.insert(0, "/")
    import handler as H

    manifest = json.load(open("/fps_ab_corpus_manifest.json"))
    sources = [s for s in manifest["sources"] if s.get("video_url")][:max(1, n_sources)]
    RESULT = {"canary": None, "sources": {}, "manifest_frozen_at": manifest.get("frozen_at_commit")}

    class _CaptureDone(BaseException):
        pass

    _cur = {"arm": None, "cap": None}

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
        cuts, edit_plan = args[1], args[2]
        em = (edit_plan.get("emphasis_moments") if isinstance(edit_plan, dict) else None) or []
        mg = [e for e in em if isinstance(e, dict) and e.get("motion_graphic")]
        calls = [c for c in getattr(H, "_GEMINI_CALL_LOG", []) if isinstance(c, dict)]
        _cur["cap"] = {
            "tokens": H._gemini_token_summary(),
            "gemini_leg_s": round(sum(c.get("total_s") or 0 for c in calls if not c.get("aborted")), 1),
            "n_calls": len(calls),
            "n_zoom": len(_zoom_ts(cuts)), "zoom_ts": _zoom_ts(cuts)[:12],
            "n_emphasis": len(em), "n_motion_graphic": len(mg),
            "emphasis_ts": [round(float(e.get("t", 0) or 0), 1) for e in em[:12] if isinstance(e, dict)],
        }
        raise _CaptureDone()

    H.render_multi_clip = _spy

    def _one(src, arm, overrides):
        _cur["arm"], _cur["cap"] = arm, None
        try:
            H._GEMINI_CALL_LOG.clear()
        except Exception:
            pass
        jid = str(uuid.uuid4())
        url = f"https://thisismybucketagainwooo.s3.amazonaws.com/planonly-fps-corpus/{arm}/{jid}/out.mp4"
        body = {"job_id": jid, "video_url": src["video_url"],
                "vibe": src.get("vibe") or "High-energy viral edit with punchy zooms and emphasis",
                "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url,
                "public_url": url, "model": "flare", "supports_progressive": False,
                "premium_pipeline_enabled": False, "mode": "full", "plan_only": True}
        body.update(overrides)
        t0 = time.time()
        try:
            H.handler({"input": body})
        except _CaptureDone:
            pass
        except Exception as e:
            return {"err": f"{type(e).__name__}: {e}", "tb": traceback.format_exc()[-1200:]}
        cap = _cur["cap"] or {"err": "no capture (plan_only returned before render spy?)"}
        cap["wall_s"] = round(time.time() - t0, 1)
        return cap

    # ── Phase 0: VERTEX CANARY (hard gate) ──────────────────────────────────
    canary = _one(sources[0], "canary_fps18", {})
    RESULT["canary"] = canary
    if not canary.get("n_calls"):
        RESULT["ABORT"] = ("VERTEX STILL DEAD: canary made 0 Gemini calls "
                           "(safe_edit fallback — the 2026-08-08 dunning outage). "
                           "No arms were run; ~1 source of spend consumed. "
                           "Re-ignite after Zac's GCP billing fix.")
        return RESULT

    # ── Phase 1: corpus arms ────────────────────────────────────────────────
    ARMS = [("fps18_default", {}),
            ("fps2_low", {"proxy_sample_fps": 2, "media_resolution": "MEDIA_RESOLUTION_LOW"})]
    for src in sources:
        sid = src.get("id") or src["job_id"][:8]
        RESULT["sources"][sid] = {"lang": src.get("lang"), "duration_s": src.get("duration_s")}
        for arm, ov in ARMS:
            RESULT["sources"][sid][arm] = _one(src, arm, ov)
    return RESULT


@app.local_entrypoint()
def main():
    n = N_SOURCES
    print(f"=== PLAN_ONLY corpus A/B: {n} sources × 2 arms (canary-gated) ===")
    o = run.remote(n)
    if o.get("ABORT"):
        print("\n*** ABORTED:", o["ABORT"])
        print("canary:", json.dumps(o.get("canary"), default=str)[:400])
        return
    surv_zoom = surv_emph = tok_a = tok_b = leg_a = leg_b = n_ok = 0
    for sid, d in o["sources"].items():
        A, B = d.get("fps18_default", {}), d.get("fps2_low", {})
        print(f"\n[{sid}] lang={d.get('lang')} dur={d.get('duration_s')}s")
        for arm, x in (("A fps18", A), ("B fps2/LOW", B)):
            if x.get("err"):
                print(f"  {arm}: ERROR {x['err'][:160]}")
                continue
            t = x.get("tokens") or {}
            print(f"  {arm}: prompt={t.get('prompt')} leg={x.get('gemini_leg_s')}s "
                  f"zoom={x.get('n_zoom')}@{x.get('zoom_ts')} emph={x.get('n_emphasis')} MG={x.get('n_motion_graphic')}")
        if not A.get("err") and not B.get("err") and A.get("n_calls") and B.get("n_calls"):
            n_ok += 1
            surv_zoom += 1 if (B.get("n_zoom") or 0) >= max(1, (A.get("n_zoom") or 0) - 1) else 0
            surv_emph += 1 if (B.get("n_emphasis") or 0) >= max(1, (A.get("n_emphasis") or 0) - 1) else 0
            tok_a += (A["tokens"].get("prompt") or 0); tok_b += (B["tokens"].get("prompt") or 0)
            leg_a += A.get("gemini_leg_s") or 0; leg_b += B.get("gemini_leg_s") or 0
    if n_ok:
        print(f"\n=== AGGREGATE over {n_ok} clean pairs ===")
        print(f"  tokens: {tok_a} -> {tok_b} ({100*(tok_a-tok_b)/max(1,tok_a):.0f}% fewer)")
        print(f"  gemini leg: {leg_a:.0f}s -> {leg_b:.0f}s")
        print(f"  zoom survival {surv_zoom}/{n_ok} · emphasis survival {surv_emph}/{n_ok}")
        print("  flip bar: survival >= ~90% of pairs AND no arm-B error class")
    print("\nCORPUS A/B COMPLETE.")
