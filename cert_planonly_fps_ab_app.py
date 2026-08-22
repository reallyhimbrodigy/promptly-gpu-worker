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
    from build_lane import mark_build_lane
    mark_build_lane("cert_planonly_fps_ab_app.py")
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
        import collections as _coll
        _p = edit_plan if isinstance(edit_plan, dict) else {}
        _mgt = _coll.Counter(str(e["motion_graphic"].get("type"))
                             for e in mg if isinstance(e.get("motion_graphic"), dict))
        RESULT["arms"][arm] = {
            "tokens": H._gemini_token_summary(),
            "gemini_leg_s": gemini_s,
            "n_calls": len(calls),
            "n_zoom": len(_zoom_ts(cuts)),
            "zoom_ts": _zoom_ts(cuts)[:12],
            "n_emphasis": len(em),
            "n_motion_graphic": len(mg),
            # PLACEMENT, not a count. The previous cut read e.get("t") — a key
            # _EmphasisMoment does not have (it carries word_indices) — so every
            # timestamp came back 0.0 in BOTH arms and the run reported
            # "emphasis 4->4, placement identical" while measuring nothing at
            # all. Counts holding is the WEAK claim; whether 2fps moves WHERE
            # emphasis lands is the question the cut turns on, because visual
            # grounding is the only thing fps feeds.
            "emphasis_anchors": [sorted(e.get("word_indices") or [])
                                 for e in em[:14] if isinstance(e, dict)],
            "emphasis_kinds": [f"{e.get('type')}/{e.get('intensity')}"
                               for e in em[:14] if isinstance(e, dict)],
            # MG placement rides its own anchor; a card that survives but moves
            # to a different word is a different edit.
            "mg_anchors": [sorted((e.get("motion_graphic") or {}).get("word_indices")
                                  or e.get("word_indices") or [])
                           for e in em[:14]
                           if isinstance(e, dict) and e.get("motion_graphic")],
            # ── FULL COMPONENT CUT (2026-08-21). The original capture read only
            # zooms/emphasis/MG, so a cut that silently moved the CUT LIST or the
            # captions would have passed as "quality held". Cuts and captions are
            # the CONTROL surfaces here: they are timed off Deepgram, not off the
            # video, so they must be IDENTICAL across arms. If they move, the arm
            # is not isolating video sampling and no other number can be trusted.
            "n_cuts": len(cuts or []),
            "cut_bounds": [(round(float(c.get("source_start", 0) or 0), 2),
                            round(float(c.get("source_end", 0) or 0), 2))
                           for c in (cuts or [])[:14]],
            "mg_types": dict(_mgt),
            "n_text_overlays": len(_p.get("text_overlays") or []),
            "n_sfx": len(_p.get("sound_effects") or []),
            "n_broll": len(_p.get("broll_clips") or _p.get("broll") or []),
            "n_transitions": len(_p.get("transitions") or []),
            "n_caption_keywords": len(_p.get("caption_keywords") or []),
            "caption_style": str(_p.get("caption_style") or ""),
            "thumbnail_word_index": _p.get("thumbnail_word_index"),
            "post_hook": str(_p.get("post_hook") or "")[:80],
        }
        raise _CaptureDone()

    H.render_multi_clip = _spy
    # THREE ARMS, and the third is the point. A single A/B at n=1 cannot tell an
    # fps effect from Gemini's own run-to-run variance: the last run showed
    # emphasis placement sharing only 2/5 anchors between arms, which is either
    # a real degradation or just the model being non-deterministic. A-vs-A
    # measures the noise floor with the SAME input, so B's delta can be read
    # against it instead of against zero.
    #
    # Interleaved A, B, A2 rather than A, A2, B so a drift in Vertex latency
    # across the run cannot masquerade as the control being stable.
    for arm, ov in [("fps18_default", {}),
                    ("fps2_low", {"proxy_sample_fps": 2, "media_resolution": "MEDIA_RESOLUTION_LOW"}),
                    ("fps18_control", {})]:
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
    # DERIVED from what actually ran, never a hardcoded list. The previous cut
    # iterated ("fps18_default", "fps2_low") while the run loop had THREE arms,
    # so the A-vs-A control executed, cost money, returned data — and was never
    # printed. Eighth reporter bug of this shape in this campaign.
    for arm in [k for k in ("fps18_default", "fps2_low", "fps18_control") if k in a] \
               + [k for k in a if k not in ("fps18_default", "fps2_low", "fps18_control")]:
        d = a.get(arm, {})
        print(f"\n[{arm}]  pipeline_wall={o.get('wall', {}).get(arm)}s")
        if d.get("err"):
            print("  ERROR:", d["err"]); print("  tb:", d.get("tb", "")); continue
        t = d.get("tokens") or {}
        print(f"  tokens: prompt={t.get('prompt')} uncached_delta={t.get('uncached_delta')} out={t.get('output')} (n_calls={d.get('n_calls')})")
        print(f"  GEMINI LEG wall: {d.get('gemini_leg_s')}s")
        print(f"  zooms={d.get('n_zoom')} @ {d.get('zoom_ts')}")
        print(f"  emphasis={d.get('n_emphasis')} (motion_graphic={d.get('n_motion_graphic')})")
        print(f"    anchors: {d.get('emphasis_anchors')}")
        print(f"    kinds  : {d.get('emphasis_kinds')}")
    # deltas
    A, B = a.get("fps18_default", {}), a.get("fps2_low", {})
    if A.get("tokens") and B.get("tokens"):
        pa, pb = A["tokens"].get("prompt", 0), B["tokens"].get("prompt", 0)
        print(f"\n  === TOKEN DROP: {pa} -> {pb} ({100*(pa-pb)/pa:.0f}% fewer)  [override took effect => flag code IS LIVE]" if pa else "")
        ga, gb = A.get("gemini_leg_s", 0), B.get("gemini_leg_s", 0)
        print(f"  === GEMINI LEG: {ga}s -> {gb}s ({ga-gb:+.0f}s)")
        print(f"  === QUALITY: zooms {A.get('n_zoom')}->{B.get('n_zoom')}, emphasis {A.get('n_emphasis')}->{B.get('n_emphasis')}, MG {A.get('n_motion_graphic')}->{B.get('n_motion_graphic')}")
        print("      (survive => flip is safe; collapse => 2fps too coarse for placement)")

        # ── CONTROL SURFACES: must be IDENTICAL, or the arm isolates nothing ──
        print("\n  === CONTROL (Deepgram-timed, NOT video-derived — must be identical) ===")
        _ctl_ok = True
        for k in ("n_cuts", "n_caption_keywords", "caption_style"):
            va, vb = A.get(k), B.get(k)
            same = (va == vb)
            _ctl_ok &= same
            print(f"    {k:<22} {va} -> {vb}   {'OK' if same else '** MOVED **'}")
        ca, cb = A.get("cut_bounds"), B.get("cut_bounds")
        if ca is not None and cb is not None:
            same = (ca == cb)
            _ctl_ok &= same
            print(f"    {'cut_bounds':<22} {'identical' if same else '** DIFFER **'}")
            if not same:
                print(f"      A: {ca}")
                print(f"      B: {cb}")
        if not _ctl_ok:
            print("\n    !! A CONTROL SURFACE MOVED. Video sampling is not the only")
            print("       variable in this pair — read NOTHING else from it.")

        print("\n  === THE REAL TEST (video-grounded placement) ===")
        for k in ("n_emphasis", "n_motion_graphic", "n_zoom", "n_text_overlays",
                  "n_sfx", "n_broll", "n_transitions", "thumbnail_word_index"):
            va, vb = A.get(k), B.get(k)
            flag = ""
            if isinstance(va, int) and isinstance(vb, int) and va:
                d = (vb - va) / va * 100
                flag = "   <-- COLLAPSE" if d <= -40 else ("   <-- surge" if d >= 60 else "")
            print(f"    {k:<22} {va} -> {vb}{flag}")
        print(f"    {'mg_types':<22} {A.get('mg_types')} -> {B.get('mg_types')}")
        # THE REAL TEST: does 2fps move WHERE emphasis lands?
        _aa, _ab = A.get("emphasis_anchors") or [], B.get("emphasis_anchors") or []
        _same = (_aa == _ab)
        print(f"\n    emphasis PLACEMENT identical: {_same}")
        print(f"      18fps : {_aa}")
        print(f"      2fps  : {_ab}")
        if not _same:
            _sa = {tuple(x) for x in _aa}; _sb = {tuple(x) for x in _ab}
            print(f"      only@18fps: {sorted(_sa - _sb)}")
            print(f"      only@2fps : {sorted(_sb - _sa)}")
            print(f"      shared    : {len(_sa & _sb)}/{max(len(_sa), len(_sb))}")
        print(f"    emphasis KINDS  A={A.get('emphasis_kinds')}")
        print(f"                    B={B.get('emphasis_kinds')}")
        print(f"    MG anchors      A={A.get('mg_anchors')}  B={B.get('mg_anchors')}")
        if not (A.get("mg_anchors") or B.get("mg_anchors")):
            print("      ** MG=0 in BOTH arms on this source — MG placement is "
                  "UNTESTED here, not held. **")
    print("\nPLAN_ONLY A/B COMPLETE.")
