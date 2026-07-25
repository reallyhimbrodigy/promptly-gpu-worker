"""A-L4 RENDER FAN-OUT pixel-equivalence cert — proves chunks rendered on
SEPARATE Modal containers (render_chunk_fanout) are pixel-equivalent to the
same chunks rendered as local subprocesses, BEFORE the flag ever flips.

Ephemeral (`modal run cert_fanout_app.py`, never deployed). Three CONSTRUCTED
durable talking-head sources (multilingual-cert face video looped over looped
EN TTS audio — the durable-sources law; ~30s / ~90s / ~155s) each run the
REAL pipeline ONCE (fan-out flag OFF — today's local path) with a capture
hook that snapshots the render inputs at the instant the chunk subprocesses
spawn: overlay_input.json (+ micro_input.json when present) + every staged
/remotion/bundle/public file. Both legs then render THE SAME captured inputs
(Gemini nondeterminism is out of the frame by construction):

  leg A (local):  the chunk subprocess commands exactly as handler runs them
                  (same chunk count / ranges / concurrency arithmetic)
  leg B (fanout): handler's OWN _fanout_prepare + _fanout_render_chunks
                  against the DEPLOYED render_chunk_fanout function, with the
                  per-chunk local fallback POISONED (a silent fallback would
                  vacuously pass) — any remote failure fails the case loudly

Compare bar per leg pair (overlay leg always; micro leg when the plan yields
a chunked PromptlyMicroSegments render, i.e. a transition/complex zoom exists
and its timeline is >= 200 frames):
  - per-chunk decoded frame-count equality (and == the planned range size)
  - total concatenated frame counts equal exactly (A/V untouched: the legs
    are video-only lossless ProRes intermediates; audio never leaves the
    orchestrator in the fan-out design)
  - global SSIM(legA, legB) >= 0.99 (exact value reported)
  - seam scan: per-frame SSIM at every chunk-boundary frame AND its
    predecessor >= 0.99 (parsed from the same ssim stats file)
  - framemd5 equality reported as a bonus signal (not gated)

MODES:
  modal run cert_fanout_app.py
      Full cert — the remote hop runs against the DEPLOYED promptly-gpu-worker
      app, which must already contain render_chunk_fanout. If it predates the
      function, the case reports the prepare failure and tells you to use:
  modal run cert_fanout_app.py --local-only
      Leg B re-renders locally: certs chunk-render determinism + the entire
      compare machinery, NOT the remote hop. Use when the deployed app
      predates render_chunk_fanout.

S3 hygiene: sources land under cert/fanout/{jid}/, the fan-out round-trip
under fanout/{jid}/ — both deleted best-effort at case end.
"""
import os
import sys
sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-fanout", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-cloudfront"),
]
CDN = "https://d1iax8jos987n3.cloudfront.net/"

FACE_KEY = "multilingual-cert/_face/face.mp4"
AUDIO_KEY = "multilingual-cert/_bridge_regression/en.m4a"
PUBLIC_DIR = "/remotion/bundle/public"


def _split_frames(total_frames, n_chunks):
    """VERBATIM copy of handler.render_multi_clip's _split_frames arithmetic
    (closure, not importable) — keep in lockstep so the cert's chunk plan is
    the production chunk plan."""
    if total_frames <= 0 or n_chunks <= 0:
        return []
    per = total_frames // n_chunks
    remainder = total_frames % n_chunks
    ranges = []
    cursor = 0
    for i in range(n_chunks):
        chunk_size = per + (1 if i < remainder else 0)
        if chunk_size == 0:
            continue
        ranges.append((cursor, cursor + chunk_size - 1))
        cursor += chunk_size
    return ranges


@app.function(secrets=SECRETS, timeout=3600, cpu=64, memory=131072)
def run_case(case: dict) -> dict:
    import glob
    import json
    import re
    import shutil
    import subprocess
    import tempfile
    import threading
    import time
    import traceback
    import uuid
    import concurrent.futures as futures
    import boto3
    sys.path.insert(0, "/")
    # Kill server traffic + phantom DB rows BEFORE importing handler; force the
    # capture run onto TODAY'S local chunk path (the fan-out must stay dark —
    # the cert exercises the remote function explicitly, with poison fallback).
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ.pop("PROMPTLY_RENDER_FANOUT", None)
    import handler as H

    name = case["name"]
    dur = float(case["dur"])
    local_only = bool(case.get("local_only"))
    out = {"case": name, "dur_s": dur,
           "mode": "local-only" if local_only else "remote", "ok": False}
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    jid = f"certfo-{uuid.uuid4().hex[:12]}"
    base_key = f"cert/fanout/{jid}"
    work = tempfile.mkdtemp(prefix="certfo_")
    try:
        # ── 1. Construct the durable talking-head source (face × looped TTS) ──
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
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
             "-shortest", src_p],
            check=True, capture_output=True, text=True)

        # ── 2. ONE real pipeline run with the render-input capture hook ──────
        # The hook fires on the FIRST `node render-full.mjs` subprocess: at
        # that instant every staged public file + both input JSONs exist and
        # are exactly what the local chunks are about to render.
        cap_dir = os.path.join(work, "capture")
        os.makedirs(os.path.join(cap_dir, "public"), exist_ok=True)
        cap = {"done": False, "stage_key": None}
        cap_lock = threading.Lock()
        orig_run = subprocess.run

        def capturing_run(cmd, *a, **kw):
            try:
                if (isinstance(cmd, (list, tuple)) and len(cmd) >= 2
                        and str(cmd[0]) == "node"
                        and "render-full.mjs" in str(cmd[1])):
                    with cap_lock:
                        if not cap["done"]:
                            ip = str(list(cmd)[list(cmd).index("--input") + 1])
                            wd = os.path.dirname(ip)
                            sk = os.path.basename(wd.rstrip("/"))
                            for nme in ("overlay_input.json", "micro_input.json"):
                                p = os.path.join(wd, nme)
                                if os.path.exists(p):
                                    shutil.copy2(p, os.path.join(cap_dir, nme))
                            for p in glob.glob(f"{PUBLIC_DIR}/{sk}__*"):
                                shutil.copy2(
                                    p, os.path.join(cap_dir, "public",
                                                    os.path.basename(p)))
                            cap["stage_key"] = sk
                            cap["done"] = True
                            print(f"[cert-capture] snapshot taken (stage_key={sk})",
                                  flush=True)
            except Exception as ce:
                print(f"[cert-capture] snapshot failed: {ce}", flush=True)
            return orig_run(cmd, *a, **kw)

        src_key = f"{base_key}/source.mp4"
        s3.upload_file(src_p, bucket, src_key,
                       ExtraArgs={"ContentType": "video/mp4"})
        video_url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": src_key},
            ExpiresIn=7200)
        out_key = f"{base_key}/output.mp4"
        upload_url = s3.generate_presigned_url(
            "put_object", Params={"Bucket": bucket, "Key": out_key,
                                  "ContentType": "video/mp4"}, ExpiresIn=7200)
        thumb_key = f"{base_key}/thumb.jpg"
        upload_url_thumb = s3.generate_presigned_url(
            "put_object", Params={"Bucket": bucket, "Key": thumb_key,
                                  "ContentType": "image/jpeg"}, ExpiresIn=7200)
        body = {"job_id": jid, "user_id": "cert-fanout", "vibe": "viral",
                "video_url": video_url, "upload_url": upload_url,
                "upload_url_thumb": upload_url_thumb,
                "public_url": f"{CDN}{out_key}", "mode": "full"}
        subprocess.run = capturing_run
        try:
            res = H.handler({"input": body})
        finally:
            subprocess.run = orig_run
        out["pipeline_status"] = res.get("status")
        if res.get("status") != "success":
            out["error"] = (f"capture pipeline run failed: "
                            f"{str(res.get('error'))[:300]} "
                            f"(code={res.get('error_code')})")
            return out
        ov_json = os.path.join(cap_dir, "overlay_input.json")
        if not cap["done"] or not os.path.exists(ov_json):
            out["error"] = "capture hook never fired (no render-full.mjs call observed)"
            return out

        # ── 3. Chunk plan — handler's exact arithmetic ────────────────────────
        with open(ov_json) as f:
            ov_in = json.load(f)
        total_frames = int(ov_in.get("totalDurationInFrames") or 0)
        n_chunks = (max(1, int(os.environ.get("PROMPTLY_RENDER_CHUNKS", "") or 8))
                    if total_frames >= 300 else 1)
        ranges = _split_frames(total_frames, n_chunks)
        out["overlay_frames"] = total_frames
        out["overlay_chunks"] = len(ranges)
        if len(ranges) <= 1:
            out["error"] = (f"overlay not chunked ({total_frames} frames < 300)"
                            f" — case too short to exercise the fan-out")
            return out
        micro_json = os.path.join(cap_dir, "micro_input.json")
        micro_frames = 0
        micro_ranges = []
        if os.path.exists(micro_json):
            with open(micro_json) as f:
                mi_in = json.load(f)
            micro_frames = int(mi_in.get("totalDurationInFrames") or 0)
            if micro_frames >= 200:
                micro_ranges = _split_frames(micro_frames, 4)
                if len(micro_ranges) <= 1:
                    micro_ranges = []
        out["micro_frames"] = micro_frames
        out["micro_chunks"] = len(micro_ranges)

        # ── 4. Re-stage the captured public files (the capture run's teardown
        # unlinked them; both legs resolve the SAME basenames) ────────────────
        restaged = []
        for p in sorted(glob.glob(os.path.join(cap_dir, "public", "*"))):
            dst = os.path.join(PUBLIC_DIR, os.path.basename(p))
            if os.path.lexists(dst):
                os.unlink(dst)
            try:
                os.link(os.path.realpath(p), dst)
            except OSError:
                shutil.copy2(p, dst)
            restaged.append(dst)
        out["staged_files"] = [os.path.basename(p) for p in restaged]

        # ── 5. Leg renderers ─────────────────────────────────────────────────
        def leg_local(input_json, comp, rngs, conc, outdir, tag):
            os.makedirs(outdir, exist_ok=True)

            def one(i, fs, fe):
                cp = os.path.join(outdir, f"{tag}_chunk_{i:02d}.mov")
                cmd = ["node", "/remotion/render-full.mjs",
                       "--input", input_json, "--output", cp,
                       "--public-dir", PUBLIC_DIR,
                       "--composition", comp, "--gl", "swangle",
                       "--frame-range", f"{fs},{fe}",
                       "--composition-start", str(fs),
                       "--concurrency", str(conc)]
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=900)
                if r.returncode != 0:
                    raise RuntimeError(
                        f"{tag}-{i:02d} local render failed rc={r.returncode}: "
                        f"{(r.stderr or '')[-1200:]}")
                return cp

            with futures.ThreadPoolExecutor(max_workers=len(rngs)) as pool:
                fs_ = [pool.submit(one, i, a, b)
                       for i, (a, b) in enumerate(rngs)]
                return [f.result(timeout=1000) for f in fs_]

        def leg_fanout(ctx, kind, rngs, conc, outdir, tag):
            os.makedirs(outdir, exist_ok=True)

            def poison(label):
                def _p(_l, _c, _t):
                    raise RuntimeError(
                        f"remote hop failed for {label} — local fallback is "
                        f"POISONED in the cert (a silent fallback would "
                        f"vacuously pass); see the [fanout] error above")
                return _p

            def one(i, fs, fe):
                cp = os.path.join(outdir, f"{tag}_chunk_{i:02d}.mov")
                lbl = f"{tag}-{i:02d}"
                # handler's OWN helper — the exact code the flag will run.
                H._fanout_render_chunks(ctx, kind, lbl, ["poisoned"], 1, cp,
                                        fs, fe, fs, conc, poison(lbl))
                return cp

            with futures.ThreadPoolExecutor(max_workers=len(rngs)) as pool:
                fs_ = [pool.submit(one, i, a, b)
                       for i, (a, b) in enumerate(rngs)]
                return [f.result(timeout=900) for f in fs_]

        # ── 6. Compare machinery ─────────────────────────────────────────────
        def count_frames(p):
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-count_frames",
                 "-select_streams", "v:0",
                 "-show_entries", "stream=nb_read_frames",
                 "-of", "csv=p=0", p],
                capture_output=True, text=True, timeout=600)
            return int((r.stdout or "0").strip().splitlines()[0] or 0)

        def concat(paths, dst):
            lst = dst + ".txt"
            with open(lst, "w") as f:
                for p in paths:
                    f.write(f"file '{p}'\n")
            r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", lst, "-c", "copy", dst],
                capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                raise RuntimeError(f"concat failed: {(r.stderr or '')[-500:]}")
            return dst

        def compare(tag, a_paths, b_paths, rngs, total):
            v = {"chunks": len(rngs)}
            pc = []
            for i, ((fs, fe), ap, bp) in enumerate(zip(rngs, a_paths, b_paths)):
                na, nb = count_frames(ap), count_frames(bp)
                pc.append({"i": i, "range": [fs, fe],
                           "expected": fe - fs + 1, "legA": na, "legB": nb,
                           "equal": (na == nb == fe - fs + 1)})
            v["per_chunk_frames"] = pc
            v["per_chunk_frames_ok"] = all(c["equal"] for c in pc)
            ca = concat(a_paths, os.path.join(work, f"{tag}_legA.mov"))
            cb = concat(b_paths, os.path.join(work, f"{tag}_legB.mov"))
            ta, tb = count_frames(ca), count_frames(cb)
            v["total_frames"] = {"expected": total, "legA": ta, "legB": tb,
                                 "equal": (ta == tb == total)}
            stats = os.path.join(work, f"{tag}_ssim.log")
            r = subprocess.run(
                ["ffmpeg", "-v", "info", "-i", ca, "-i", cb,
                 "-lavfi", f"ssim=stats_file={stats}", "-f", "null", "-"],
                capture_output=True, text=True, timeout=1800)
            m = re.search(r"All:([0-9.]+)", r.stderr or "")
            v["ssim_all"] = float(m.group(1)) if m else None
            per_frame = {}
            try:
                with open(stats) as f:
                    for line in f:
                        mn = re.search(r"n:(\d+)", line)
                        ma = re.search(r"All:([0-9.]+)", line)
                        if mn and ma:
                            per_frame[int(mn.group(1))] = float(ma.group(1))
            except Exception:
                pass
            v["frame_ssim_min"] = (round(min(per_frame.values()), 6)
                                   if per_frame else None)
            # Seam scan: for every chunk boundary at 0-based frame fs, the
            # boundary frame and its predecessor. ssim stats n is 1-based →
            # predecessor (0-based fs-1) is n=fs, boundary frame is n=fs+1.
            seams = []
            for (fs, _fe) in rngs[1:]:
                for n1 in (fs, fs + 1):
                    if n1 in per_frame:
                        seams.append({"frame_0based": n1 - 1,
                                      "ssim": per_frame[n1]})
            v["boundary_frames"] = seams
            v["boundary_ok"] = (bool(seams)
                                and all(sm["ssim"] >= 0.99 for sm in seams))

            def framemd5(p):
                r2 = subprocess.run(
                    ["ffmpeg", "-v", "error", "-i", p, "-f", "framemd5", "-"],
                    capture_output=True, text=True, timeout=1800)
                return r2.stdout
            v["framemd5_identical"] = (framemd5(ca) == framemd5(cb))
            v["ok"] = bool(
                v["per_chunk_frames_ok"] and v["total_frames"]["equal"]
                and v["ssim_all"] is not None and v["ssim_all"] >= 0.99
                and v["boundary_ok"])
            return v

        # ── 7. Run both legs + compare ───────────────────────────────────────
        legdir = os.path.join(work, "legs")
        verdicts = {}
        ctx = None
        if not local_only:
            try:
                # handler's OWN prepare — uploads once, resolves the DEPLOYED
                # render_chunk_fanout (raises if the deployed app predates it).
                ctx = H._fanout_prepare(
                    jid, restaged, ov_json,
                    micro_json if micro_ranges else None)
            except Exception as pe:
                out["error"] = (
                    f"fanout prepare failed ({type(pe).__name__}: {pe}) — if "
                    f"the DEPLOYED app predates render_chunk_fanout, deploy "
                    f"first or run `modal run cert_fanout_app.py --local-only`")
                return out

        t_leg = time.time()
        ovA = leg_local(ov_json, "PromptlyOverlay", ranges, 8,
                        os.path.join(legdir, "ov_a"), "overlay")
        out["legA_overlay_s"] = round(time.time() - t_leg, 1)
        t_leg = time.time()
        if local_only:
            ovB = leg_local(ov_json, "PromptlyOverlay", ranges, 8,
                            os.path.join(legdir, "ov_b"), "overlay")
        else:
            ovB = leg_fanout(ctx, "overlay", ranges, 8,
                             os.path.join(legdir, "ov_b"), "overlay")
        out["legB_overlay_s"] = round(time.time() - t_leg, 1)
        verdicts["overlay"] = compare("overlay", ovA, ovB, ranges, total_frames)

        if micro_ranges:
            miA = leg_local(micro_json, "PromptlyMicroSegments", micro_ranges,
                            4, os.path.join(legdir, "mi_a"), "micro")
            if local_only:
                miB = leg_local(micro_json, "PromptlyMicroSegments",
                                micro_ranges, 4,
                                os.path.join(legdir, "mi_b"), "micro")
            else:
                miB = leg_fanout(ctx, "micro", micro_ranges, 4,
                                 os.path.join(legdir, "mi_b"), "micro")
            verdicts["micro"] = compare("micro", miA, miB, micro_ranges,
                                        micro_frames)
        else:
            verdicts["micro"] = {"skipped": (
                "no_micro_input" if not os.path.exists(micro_json)
                else f"micro_not_chunked_{micro_frames}f")}

        out["verdicts"] = verdicts
        micro_ok = (True if verdicts["micro"].get("skipped")
                    else bool(verdicts["micro"].get("ok")))
        out["ok"] = bool(verdicts["overlay"]["ok"] and micro_ok)
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-2500:]
        return out
    finally:
        # Best-effort S3 hygiene: cert source/output/HLS + the fan-out prefix.
        try:
            for pref in (base_key, f"fanout/{jid}"):
                resp = s3.list_objects_v2(Bucket=bucket, Prefix=pref + "/")
                objs = [{"Key": o["Key"]}
                        for o in (resp.get("Contents") or [])]
                if objs:
                    s3.delete_objects(Bucket=bucket,
                                      Delete={"Objects": objs})
        except Exception as cle:
            print(f"[cert-fanout] S3 cleanup failed: {cle}", flush=True)
        try:
            import shutil as _sh
            _sh.rmtree(work, ignore_errors=True)
        except Exception:
            pass


@app.local_entrypoint()
def main(local_only: bool = False):
    import json
    cases = [
        {"name": "short_30s", "dur": 30.0, "local_only": local_only},
        {"name": "mid_90s", "dur": 90.0, "local_only": local_only},
        {"name": "long_155s", "dur": 155.0, "local_only": local_only},
    ]
    results = list(run_case.map(cases))
    print("\n============ A-L4 RENDER FAN-OUT PIXEL-EQUIVALENCE CERT ============")
    npass = 0
    for r in results:
        npass += 1 if r.get("ok") else 0
        print(json.dumps(r, indent=2, default=str))
    mode = ("local-only (remote hop NOT exercised)" if local_only
            else "remote (DEPLOYED render_chunk_fanout exercised, poisoned fallback)")
    verdict = {"cert": "fanout-pixel-equivalence", "mode": mode,
               "cases": len(cases), "pass": npass,
               "ok": npass == len(cases)}
    print("VERDICT: " + json.dumps(verdict))
    print(f"==================== {npass}/{len(cases)} PASS ====================")
