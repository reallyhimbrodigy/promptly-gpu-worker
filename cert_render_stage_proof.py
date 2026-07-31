"""PHASE 1 render_stage CONTRACT PROOF (Zac 2026-07-28, corrected).

The trap (Zac): in-process the 3 mutated dicts cross by SHARED REFERENCE, so a
green happy-path run proves the extraction didn't break TODAY but NOT the return
contract increment 2 (separate process) depends on. A forgotten/wrong return
sails through and breaks when the burst serializes its result.

This proves the CONTRACT:
  RUN 1 (happy + RETURN CONTRACT): snapshot each mutated dict's KEYS before the
    render_stage call; after, assert the RETURNED object gained the render-stage
    mutations (keys absent pre-call, present in the return) AND json-serializes
    (the real S3 handoff). floor_state: assert the KEY EXISTS + is a list (a clean
    job never fills it, so 'empty' proves nothing about whether it crosses).
  RUN 2 (EXCEPTION PATH): monkeypatch the render ladder to RAISE with progressive
    ON, assert the terminal failed write carries error_code=RENDER_FATAL
    (refund rides on str(e) — runtime, not a design claim), designed_rejection
    False (at-fault), the alert fires, and the finally completes cleanly (no
    NameError on the _prog_pub_cell -> the cell delivered the handle across the
    raise). Fast: the ladder raises before any real render.
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-rs-proof-v2", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/0f739aeb-a5e1-458d-a117-eb326841b069/1785241163074-2BE40123-3749-4120-8902-D1B5BBC28552_L0_001.mp4"
_TIMING_KEYS = {"download", "normalize_transcribe_upload", "edit_recipe_faces",
                "render", "broll", "upload_export", "total"}
_RS_KEYS = {"edit_plan", "timings", "floor_state", "render_elapsed", "output_size_mb",
            "cover_frame_ts", "thumbnail_source_ts", "cover_frame_b64", "thumbnail_url", "exported_formats"}


@app.function(secrets=SECRETS, cpu=32.0, memory=131072, timeout=2400)
def run() -> dict:
    import uuid, traceback
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H
    import shutil as _shutil
    checks = []
    def ck(name, cond, detail=""):
        checks.append({"name": name, "pass": (None if cond is None else bool(cond)), "detail": str(detail)[:220]})

    # ================= RUN 1: happy path + RETURN CONTRACT =================
    cap = {}
    _orig_rs = H.render_stage
    def _spy(*a, **k):
        if len(a) > 12:
            cap["pre_ep_keys"] = set(a[2].keys())      # edit_plan
            cap["pre_tim_keys"] = set(a[11].keys())    # _timings
            cap["pre_floor_keys"] = set(a[12].keys())  # _floor_state
        ret = _orig_rs(*a, **k)
        cap["ret"] = ret
        return ret
    H.render_stage = _spy
    jid = str(uuid.uuid4()); base = f"https://thisismybucketagainwooo.s3.amazonaws.com/rs-proof/{jid}"
    body = {"job_id": jid, "video_url": SRC, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": f"{base}/out.mp4", "public_url": f"{base}/out.mp4",
            "upload_url_thumb": f"{base}/thumb.jpg",
            "export_formats": [{"aspect_ratio": "1:1", "upload_url": f"{base}/out_1x1.mp4"}],
            "model": "flare", "supports_progressive": False,
            "premium_pipeline_enabled": False, "mode": "full"}
    try:
        res = H.handler({"input": body})
    except Exception as e:
        cap["h1_raised"] = f"{type(e).__name__}: {str(e)[:200]}"; res = {}
    finally:
        H.render_stage = _orig_rs
    rp = res if isinstance(res, dict) else {}
    ret = cap.get("ret")

    ck("RUN1: render_stage spy fired", ret is not None, cap.get("h1_raised"))
    if isinstance(ret, dict) and "pre_tim_keys" in cap:
        ck("RUN1: return has full key set", set(ret.keys()) == _RS_KEYS,
           f"missing={_RS_KEYS-set(ret.keys())} extra={set(ret.keys())-_RS_KEYS}")
        # --- _timings: RETURN gained render/broll/upload_export (not just shared ref) ---
        r_tim = ret.get("timings") or {}
        gained_tim = set(r_tim) - cap["pre_tim_keys"]
        ck("RUN1: RETURNED timings gained {render,broll,upload_export} absent pre-call",
           {"render", "broll", "upload_export"} <= gained_tim, f"gained={sorted(gained_tim)}")
        try:
            json.dumps(r_tim); ck("RUN1: RETURNED timings json-serializable (S3 handoff)", True)
        except Exception as e:
            ck("RUN1: RETURNED timings json-serializable", False, e)
        # --- edit_plan: RETURN carries the url + deepgram-words mutations ---
        r_ep = ret.get("edit_plan") or {}
        for key in ("_rendered_video_url", "_hls_manifest_url", "_deepgram_words"):
            ck(f"RUN1: RETURNED edit_plan gained {key} (absent pre-call)",
               key in r_ep and key not in cap["pre_ep_keys"],
               f"in_return={key in r_ep} in_pre={key in cap['pre_ep_keys']}")
        try:
            json.dumps(r_ep, default=str); ck("RUN1: RETURNED edit_plan json-serializable (default=str, burst handoff)", True)
        except Exception as e:
            ck("RUN1: RETURNED edit_plan json-serializable", False, e)
        try:
            json.dumps(r_ep); ck("RUN1: RETURNED edit_plan STRICT-json (no opaque objects) [advisory for inc2]", True)
        except Exception as e:
            ck("RUN1: RETURNED edit_plan STRICT-json [advisory for inc2]", None, str(e)[:140])
        # --- floor_state: KEY EXISTS + TYPE (empty proves nothing; Zac gap 2) ---
        r_floor = ret.get("floor_state") or {}
        ck("RUN1: RETURNED floor_state has enhancements_dropped KEY of type list (not just empty)",
           "enhancements_dropped" in r_floor and isinstance(r_floor.get("enhancements_dropped"), list),
           f"present={'enhancements_dropped' in r_floor} type={type(r_floor.get('enhancements_dropped')).__name__}")
        try:
            json.dumps(r_floor); ck("RUN1: RETURNED floor_state json-serializable", True)
        except Exception as e:
            ck("RUN1: RETURNED floor_state json-serializable", False, e)

    # --- happy-path result_payload (final delivery well-formed) ---
    ck("RUN1: status success", rp.get("status") in ("success", None) and not rp.get("error"),
       f"status={rp.get('status')} error={rp.get('error')}")
    vu = rp.get("video_url") or ""
    ck("RUN1: video_url well-formed", vu.startswith("http") and vu.endswith(".mp4"), vu)
    hu = rp.get("hls_manifest_url") or ""
    ck("RUN1: hls_manifest_url well-formed", hu.startswith("http") and ".m3u8" in hu, hu)
    ck("RUN1: exported_formats has 1:1", any((f or {}).get("aspect_ratio") == "1:1" for f in (rp.get("exported_formats") or [])),
       rp.get("exported_formats"))
    st = rp.get("stage_timings") or {}
    ck("RUN1: stage_timings full key set", _TIMING_KEYS <= set(st.keys()), f"missing={_TIMING_KEYS-set(st.keys())}")

    # ================= RUN 2: EXCEPTION PATH =================
    ws_calls, alert_calls, drain_calls, rmtree_calls = [], [], [], []
    _o_ws, _o_alert, _o_ladder = H.write_job_status, H._fire_render_alert, H._render_degrade_ladder
    _o_rmtree = _shutil.rmtree
    def _ws_spy(*a, **k): ws_calls.append({"a": a, "k": k}); return None
    def _alert_spy(*a, **k): alert_calls.append({"a": a, "k": k}); return None
    def _ladder_raise(*a, **k): raise RuntimeError("RENDER_FATAL: injected exception-path proof")
    def _rmtree_spy(*a, **k): rmtree_calls.append(a[0] if a else None); return _o_rmtree(*a, **k)
    try:
        from progressive_publish import ProgressivePublisher as _PP
        _o_drain, _o_cancel = _PP.drain, _PP.cancel
        def _drain_spy(self, *a, **k): drain_calls.append("drain"); return _o_drain(self, *a, **k)
        def _cancel_spy(self, *a, **k): drain_calls.append("cancel"); return _o_cancel(self, *a, **k)
        _PP.drain, _PP.cancel = _drain_spy, _cancel_spy
    except Exception:
        _PP = None
    H.write_job_status, H._fire_render_alert, H._render_degrade_ladder = _ws_spy, _alert_spy, _ladder_raise
    H.shutil.rmtree = _rmtree_spy
    os.environ["PROMPTLY_PROGRESSIVE"] = "1"
    jid2 = str(uuid.uuid4()); base2 = f"https://thisismybucketagainwooo.s3.amazonaws.com/rs-proof2/{jid2}"
    body2 = {"job_id": jid2, "video_url": SRC, "vibe": "Clean engaging edit",
             "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
             "upload_url": f"{base2}/out.mp4", "public_url": f"{base2}/out.mp4",
             "supports_progressive": True, "progressive_test": True,
             "premium_pipeline_enabled": False, "mode": "full"}
    err2 = None
    try:
        H.handler({"input": body2})
    except Exception as e:
        err2 = f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        H.write_job_status, H._fire_render_alert, H._render_degrade_ladder = _o_ws, _o_alert, _o_ladder
        H.shutil.rmtree = _o_rmtree
        if _PP is not None:
            _PP.drain, _PP.cancel = _o_drain, _o_cancel
        os.environ.pop("PROMPTLY_PROGRESSIVE", None)

    term = [c for c in ws_calls if c["k"].get("status") == "failed"]
    ck("RUN2: handler returned cleanly (finally did NOT crash on _prog_pub_cell)", err2 is None, err2)
    ck("RUN2: terminal failed write fired", len(term) >= 1, f"{len(term)} failed / {len(ws_calls)} total writes")
    if term:
        r = term[-1]["k"].get("result") or {}
        ck("RUN2: error_code=RENDER_FATAL (refund rides on str(e) — runtime proof)", r.get("error_code") == "RENDER_FATAL", r.get("error_code"))
        ck("RUN2: designed_rejection is False (at-fault, refundable)", r.get("designed_rejection") is False, r.get("designed_rejection"))
        ck("RUN2: partial stage_timings present at death", isinstance(r.get("stage_timings"), dict), list((r.get("stage_timings") or {}).keys()))
    ck("RUN2: _fire_render_alert fired (at-fault pages)", len(alert_calls) >= 1, len(alert_calls))
    ck("RUN2: finally reached teardown rmtree(work_dir) after the raise", len(rmtree_calls) >= 1, len(rmtree_calls))
    ck("RUN2: prog_pub drain/cancel fired via cell [bonus — publisher was active]", (None if not drain_calls else True), drain_calls[:4])

    out = {"checks": checks, "all_pass": all(c["pass"] for c in checks if c["pass"] is not None),
           "stage_timings": {k: round(float(v), 1) for k, v in st.items()} if st else {},
           "video_url": rp.get("video_url"), "hls_manifest_url": rp.get("hls_manifest_url"),
           "exported_formats": rp.get("exported_formats"), "h1_raised": cap.get("h1_raised"), "err2": err2}
    return out


@app.local_entrypoint()
def main():
    print("=== PHASE 1 render_stage CONTRACT PROOF (return-contract + exception path) ===")
    o = run.remote()
    print("\nstage_timings:", json.dumps(o.get("stage_timings")))
    print("video_url:", o.get("video_url"), "| hls:", o.get("hls_manifest_url"))
    print("exported_formats:", json.dumps(o.get("exported_formats")))
    if o.get("h1_raised"): print("RUN1 raised:", o["h1_raised"])
    if o.get("err2"): print("RUN2 handler propagated:", o["err2"])
    print("\n--- CHECKS ---")
    for c in (o.get("checks") or []):
        mark = "PASS" if c["pass"] else ("SKIP" if c["pass"] is None else "FAIL")
        print(f"  {mark}  {c['name']}" + (f"   [{c['detail']}]" if c["detail"] and c["pass"] is not True else ""))
    print("\nALL PASS:", o.get("all_pass"))
