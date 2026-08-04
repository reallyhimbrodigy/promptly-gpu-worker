"""inc2 render_burst CANARY — one real job, the cpu=48 burst vs the in-process
render on the SAME plan.

Ephemeral (`modal run cert_render_burst_app.py`), never deployed. It runs the
real pipeline ONCE in an ephemeral planner container; at the render seam a wrapped
dispatcher renders the SAME edit_plan three ways so the only variable is WHERE the
render runs:
  1. BURST  — the real deployed render_burst (cpu=48) via render_burst_test=1;
              output uploaded to S3, downloaded back for the byte compare.
  2. LOCAL  — H.render_stage in THIS container (what flag-OFF does today).
  3. LOCAL2 — a determinism control: LOCAL vs LOCAL2 is the render's own run-to-
              run noise floor, so BURST≠LOCAL is only meaningful beyond it.

Reports: byte-identity (burst vs local, against the noise floor), planner vs
burst vs local wall-clock, and the seam's own timings. The staged work_dir SIZE +
STAGING SECONDS and the burst peak RSS + cpu plateau are printed by the deployed
render_burst itself ([render_burst staged ...], [burst-cpu], [burst-mem]) — grep
`modal app logs promptly-gpu-worker` for this job_id after the run.

Durable source: the multilingual-cert face video looped over looped EN TTS (the
durable-sources law), NOT user media. S3 hygiene: everything under
cert/render_burst/{jid}/, deleted best-effort at case end.
"""
import os
import sys
sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-render-burst", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-cloudfront"),
    # MUST match the deployed app's secrets EXACTLY: the deployed render_burst
    # carries promptly-lang-flags app-wide, so without it here the LOCAL arms
    # render with different flags than the burst → a spurious burst!=local
    # divergence (the env-mismatch confound, not a render_burst defect).
    modal.Secret.from_name("promptly-lang-flags"),
]
CDN = "https://d1iax8jos987n3.cloudfront.net/"
FACE_KEY = "multilingual-cert/_face/face.mp4"
AUDIO_KEY = "multilingual-cert/_bridge_regression/en.m4a"


@app.function(secrets=SECRETS, timeout=4800, cpu=16, memory=65536)
def run_case(dur: float = 20.0, run_id: str = "") -> dict:
    import copy
    import filecmp
    import json
    import shutil
    import subprocess
    import tempfile
    import time
    import uuid
    import boto3
    sys.path.insert(0, "/")
    # Kill server traffic + phantom DB rows; the burst env flag stays DARK — the
    # per-job render_burst_test override drives the burst arm.
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ.pop("PROMPTLY_RENDER_BURST", None)
    import handler as H

    out = {"dur_s": dur, "ok": False}
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    jid = f"certburst-{uuid.uuid4().hex[:12]}"
    out["job_id"] = jid
    base_key = f"cert/render_burst/{jid}"
    work = tempfile.mkdtemp(prefix="certburst_")
    keep = os.path.join(work, "keep")
    os.makedirs(keep, exist_ok=True)
    try:
        # ── 1. Durable talking-head source (face × looped TTS) ───────────────
        face_p = os.path.join(work, "face.mp4")
        audio_p = os.path.join(work, "en.m4a")
        src_p = os.path.join(work, "source.mp4")
        s3.download_file(bucket, FACE_KEY, face_p)
        s3.download_file(bucket, AUDIO_KEY, audio_p)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-stream_loop", "-1", "-i", face_p,
             "-stream_loop", "-1", "-i", audio_p,
             "-map", "0:v:0", "-map", "1:a:0", "-t", f"{dur:.2f}",
             "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest", src_p],
            check=True, capture_output=True, text=True)
        src_key = f"{base_key}/source.mp4"
        s3.upload_file(src_p, bucket, src_key, ExtraArgs={"ContentType": "video/mp4"})

        def _pget(key, ct=None):
            return s3.generate_presigned_url(
                "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=7200)

        def _pput(key, ct):
            return s3.generate_presigned_url(
                "put_object", Params={"Bucket": bucket, "Key": key, "ContentType": ct},
                ExpiresIn=7200)

        video_url = _pget(src_key)
        burst_out_key = f"{base_key}/burst.mp4"
        upload_url = _pput(burst_out_key, "video/mp4")
        upload_url_thumb = _pput(f"{base_key}/burst_thumb.jpg", "image/jpeg")
        local_upload = _pput(f"{base_key}/local.mp4", "video/mp4")
        local_upload_thumb = _pput(f"{base_key}/local_thumb.jpg", "image/jpeg")
        local2_upload = _pput(f"{base_key}/local2.mp4", "video/mp4")
        local2_upload_thumb = _pput(f"{base_key}/local2_thumb.jpg", "image/jpeg")

        # ── 2. wrapped dispatcher: SAME plan, 3 renders (BURST, LOCAL, LOCAL2) ─
        orig_disp = H._run_render_via_burst_or_local
        cap = {"ran": False, "burst_secs": None, "local_secs": None,
               "local2_secs": None, "burst_vs_local_identical": None,
               "local_deterministic": None, "burst_regen": None,
               "local_regen": None, "local2_regen": None,
               "psnr_burst_vs_local": None, "psnr_local_vs_local2": None,
               "err": None}
        t_marks = {"handler_start": None}

        def wrapped(job_id, input_data, edit_plan, work_dir, source_path,
                    output_path, transcript, source_duration, app_url,
                    broll_clips, upload_url_, _timings, _floor_state,
                    route_premium, premium_ctx, _cost_meter,
                    integrity_observe_only, _render_est, _prog_pub_cell,
                    _rs_cost_cell, is_premium):
            if cap["ran"]:
                return orig_disp(
                    job_id, input_data, edit_plan, work_dir, source_path,
                    output_path, transcript, source_duration, app_url,
                    broll_clips, upload_url_, _timings, _floor_state,
                    route_premium, premium_ctx, _cost_meter,
                    integrity_observe_only, _render_est, _prog_pub_cell,
                    _rs_cost_cell, is_premium)
            cap["ran"] = True
            if t_marks["handler_start"]:
                out["planner_secs"] = round(time.time() - t_marks["handler_start"], 1)
            # Snapshot pristine inputs for the LOCAL arms BEFORE the burst stages
            # the work_dir (the burst pickles a COPY of edit_plan, so the
            # canary's stay pristine; deep-copy anyway for the local re-renders).
            l_plan = copy.deepcopy(edit_plan)
            l_tx = copy.deepcopy(transcript)
            l2_plan = copy.deepcopy(edit_plan)
            l2_tx = copy.deepcopy(transcript)
            l_in = dict(input_data); l_in.pop("render_burst_test", None)
            l_in["upload_url_thumb"] = local_upload_thumb
            l2_in = dict(input_data); l2_in.pop("render_burst_test", None)
            l2_in["upload_url_thumb"] = local2_upload_thumb
            l_out = os.path.join(work_dir, "cert_local.mp4")
            l2_out = os.path.join(work_dir, "cert_local2.mp4")

            # A) BURST arm — real deployed render_burst, work_dir still pristine.
            tb = time.time()
            rs_burst = orig_disp(
                job_id, input_data, edit_plan, work_dir, source_path,
                output_path, transcript, source_duration, app_url, broll_clips,
                upload_url_, _timings, _floor_state, route_premium, premium_ctx,
                _cost_meter, integrity_observe_only, _render_est, _prog_pub_cell,
                _rs_cost_cell, is_premium)
            cap["burst_secs"] = round(time.time() - tb, 1)
            cap["burst_regen"] = int(_rs_cost_cell[1])  # QA-regen count from the burst

            # B) LOCAL arm — H.render_stage in THIS container (flag-OFF path).
            l_cell = [0.0, 0]
            tl = time.time()
            H.render_stage(
                job_id, l_in, l_plan, work_dir, source_path, l_out, l_tx,
                source_duration, app_url, copy.deepcopy(broll_clips),
                local_upload, copy.deepcopy(_timings), copy.deepcopy(_floor_state),
                route_premium, premium_ctx, _cost_meter, integrity_observe_only,
                _render_est, [None], l_cell)
            cap["local_secs"] = round(time.time() - tl, 1)
            cap["local_regen"] = int(l_cell[1])

            # C) LOCAL2 — determinism control (same plan, in-process again).
            l2_cell = [0.0, 0]
            tl2 = time.time()
            H.render_stage(
                job_id, l2_in, l2_plan, work_dir, source_path, l2_out, l2_tx,
                source_duration, app_url, copy.deepcopy(broll_clips),
                local2_upload, copy.deepcopy(_timings), copy.deepcopy(_floor_state),
                route_premium, premium_ctx, _cost_meter, integrity_observe_only,
                _render_est, [None], l2_cell)
            cap["local2_secs"] = round(time.time() - tl2, 1)
            cap["local2_regen"] = int(l2_cell[1])

            # Compare: download the burst output; local outputs are local files.
            kb = os.path.join(keep, "burst.mp4")
            kl = os.path.join(keep, "local.mp4")
            kl2 = os.path.join(keep, "local2.mp4")
            s3.download_file(bucket, burst_out_key, kb)
            shutil.copy2(l_out, kl)
            shutil.copy2(l2_out, kl2)
            cap["local_deterministic"] = filecmp.cmp(kl, kl2, shallow=False)
            cap["burst_vs_local_identical"] = filecmp.cmp(kb, kl, shallow=False)
            out["sizes_mb"] = {
                "burst": round(os.path.getsize(kb) / 1e6, 2),
                "local": round(os.path.getsize(kl) / 1e6, 2),
                "local2": round(os.path.getsize(kl2) / 1e6, 2)}

            # PIXEL proof (Rule 3): if burst != local by bytes, is it PIXEL-
            # identical (benign x264 thread-count slicing from cpu48 vs cpu16) or
            # real content drift? PSNR average = 'inf' → frame-identical.
            def _psnr(a, b):
                try:
                    import re as _re
                    r = subprocess.run(
                        ["ffmpeg", "-i", a, "-i", b, "-lavfi", "psnr",
                         "-f", "null", "-"],
                        capture_output=True, text=True, timeout=300)
                    m = _re.search(r"average:(inf|[0-9.]+)", r.stderr or "")
                    return m.group(1) if m else "parse_fail"
                except Exception as e:
                    return f"err:{type(e).__name__}"
            cap["psnr_burst_vs_local"] = _psnr(kb, kl)
            cap["psnr_local_vs_local2"] = _psnr(kl, kl2)
            return rs_burst

        body = {"job_id": jid, "user_id": "cert-render-burst", "vibe": "viral",
                "video_url": video_url, "upload_url": upload_url,
                "upload_url_thumb": upload_url_thumb,
                "public_url": f"{CDN}{burst_out_key}", "mode": "full",
                "render_burst_test": True}
        H._run_render_via_burst_or_local = wrapped
        t_marks["handler_start"] = time.time()
        try:
            res = H.handler({"input": body})
        finally:
            H._run_render_via_burst_or_local = orig_disp
        out["pipeline_status"] = res.get("status")
        out.update({k: cap[k] for k in (
            "burst_secs", "local_secs", "local2_secs",
            "burst_vs_local_identical", "local_deterministic",
            "burst_regen", "local_regen", "local2_regen",
            "psnr_burst_vs_local", "psnr_local_vs_local2")})
        if res.get("status") != "success":
            out["error"] = (f"pipeline failed: {str(res.get('error'))[:300]} "
                            f"(code={res.get('error_code')})")
            return out
        # STRICT PASS/FAIL (Zac 2026-08-01): the render is proven deterministic on
        # a fixed plan (OFF vs OFF2, 2026-07-28) → noise floor is ZERO. PASS
        # requires burst == local AND local == local2; any difference is a defect.
        # If burst != local, the QA-regen COUNTS below localize it (a
        # reconstructed CostMeter seed / PremiumContext changing the budget gate
        # at handler:30841 shows as a different regen count, not pixel drift).
        out["ok"] = bool(cap["burst_vs_local_identical"]) and bool(cap["local_deterministic"])
        print(f"[canary] VERDICT ok={out['ok']} burst==local="
              f"{cap['burst_vs_local_identical']} local==local2="
              f"{cap['local_deterministic']} psnr_bl={cap['psnr_burst_vs_local']} "
              f"psnr_ll2={cap['psnr_local_vs_local2']} burst_s={cap['burst_secs']} "
              f"local_s={cap['local_secs']} local2_s={cap['local2_secs']} "
              f"sizes={out.get('sizes_mb')}", flush=True)
        return out
    except Exception as e:
        import traceback
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-1800:]
        return out
    finally:
        # Persist the verdict to a SURVIVING prefix (NOT base_key, which is deleted
        # below) so a `modal run --detach` result is retrievable after the client
        # disconnects — the first canary was cancelled mid-3rd-arm by exactly that
        # disconnect, not a code fault.
        if run_id:
            try:
                s3.put_object(Bucket=bucket,
                              Key=f"cert/render_burst_results/{run_id}.json",
                              Body=json.dumps(out).encode(),
                              ContentType="application/json")
                print(f"[canary] verdict → s3://{bucket}/cert/render_burst_results/"
                      f"{run_id}.json", flush=True)
            except Exception as _pe:
                print(f"[canary] verdict persist FAILED: {_pe}", flush=True)
        # S3 hygiene — best-effort delete of the whole cert prefix.
        try:
            _objs = s3.list_objects_v2(Bucket=bucket, Prefix=base_key).get("Contents", [])
            if _objs:
                s3.delete_objects(Bucket=bucket, Delete={
                    "Objects": [{"Key": o["Key"]} for o in _objs]})
        except Exception:
            pass
        shutil.rmtree(work, ignore_errors=True)


@app.local_entrypoint()
def main(dur: float = 20.0, run_id: str = ""):
    import json
    r = run_case.remote(dur, run_id)
    print("\n" + "=" * 70)
    print("inc2 render_burst CANARY")
    print("=" * 70)
    print(json.dumps(r, indent=2))
    print("-" * 70)
    if r.get("error"):
        print(f"PIPELINE FAILED: {r.get('error')}")
        if r.get("traceback"):
            print(r["traceback"])
        print("=" * 70)
        return
    bi = r.get("burst_vs_local_identical")
    det = r.get("local_deterministic")
    print(f"CORRECTNESS (STRICT — noise floor is zero): burst==local={bi}  "
          f"local==local2 (determinism control)={det}")
    print(f"  QA-regen counts: burst={r.get('burst_regen')} "
          f"local={r.get('local_regen')} local2={r.get('local2_regen')}")
    print(f"  PSNR: burst-vs-local={r.get('psnr_burst_vs_local')}  "
          f"local-vs-local2={r.get('psnr_local_vs_local2')}  (inf = frame-identical)")
    psnr = str(r.get("psnr_burst_vs_local"))
    if bi and det:
        print("  → PASS ✅ burst is BYTE-IDENTICAL to the in-process render.")
    elif det and not bi and psnr == "inf":
        print("  → BENIGN: bytes differ but frames are PIXEL-IDENTICAL (PSNR=inf). "
              "Cause = x264 auto thread-count (get_encode_args threads=0) differing "
              "at cpu48 vs cpu16 — an encode-slicing artifact, NOT content drift "
              "(regen counts equal). Byte-identity needs a pinned encode thread "
              "count; else use a pixel bar. → ZAC'S CALL (A pin threads / B pixel bar).")
    elif det and not bi:
        print(f"  → FAIL ❌ DEFECT: deterministic render, burst DIVERGED, and PSNR="
              f"{psnr} (NOT pixel-identical). Real content drift — check regen "
              f"counts (budget gate at handler:30841) FIRST.")
    else:
        print("  → FAIL ❌ determinism control broke (local != local2) — investigate "
              "the plan/harness before blaming the burst.")
    print(f"WALL-CLOCK: planner={r.get('planner_secs')}s  "
          f"burst(cpu48)={r.get('burst_secs')}s  local(cpu16)={r.get('local_secs')}s "
          f"(local2={r.get('local2_secs')}s)")
    print(f"SIZES (MB): {r.get('sizes_mb')}")
    print(f"\nGrep the burst's own staging/RSS/cpu telemetry:")
    print(f"  modal app logs promptly-gpu-worker | grep {r.get('job_id')}")
    print(f"  (look for: [render_burst] staged work_dir → ...MB ...s ; "
          f"[burst-cpu] peak/mean of N cores ; [burst-mem] peak RSS)")
    print("=" * 70)
