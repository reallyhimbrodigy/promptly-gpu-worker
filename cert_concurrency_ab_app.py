"""CONCURRENCY A/B — true-replay (Zac 2026-08-04, ~$0.10-0.30, measurement not build).

Reuses the blur-truereplay pattern: run the pipeline ONCE, monkeypatch-capture the
fully-staged render_multi_clip args, then call the REAL render N times on
BYTE-IDENTICAL inputs, toggling ONLY PROMPTLY_OVERLAY_TAB_BUDGET:
    b8   -> 8  (cores//2 default on a 16-core box => 8//4 chunks = 2 tabs/chunk)
    b8b  -> 8  (DETERMINISM PROOF: same budget again => must be frame-locked)
    b16  -> 16 (=> 4 tabs/chunk, uses the 8 idle cores)

Runs at cpu=16 (PROMPTLY_RENDER_CORE_BUDGET=16) — the EXACT box where the 2/chunk
half-idle scenario lives. Question: does budget=16 render FASTER (uses idle cores)
or SLOWER (re-contends, the reason cores//2 was tuned DOWN from 48 tabs)? Total
render wall time answers it; the captured micro-leg log gives fps if extractable.
Concurrency changes SPEED not pixels, so all three arms must be frame-locked — if
b8 vs b8b diverge the render is nondeterministic and the A/B is void (reported).
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-concurrency-ab", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/e9b47b30-5edf-4bc6-825a-7d2a8fe1a43d/1785239363288-A2A4B085-5918-4575-BB13-CC3CD92EF816_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=3000)
def run() -> dict:
    import time, uuid, traceback, tempfile, subprocess, copy, io, contextlib, re
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_RENDER_CORE_BUDGET"] = "16"  # clamp Remotion concurrency to the real 16-core box
    sys.path.insert(0, "/")
    import handler as H
    RESULT = {"cores_reported": os.cpu_count()}

    class _CaptureDone(BaseException):
        pass

    _orig_render = H.render_multi_clip

    def _probe(p):
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries", "stream=nb_read_frames,width,height:format=duration", "-of", "json", p],
            capture_output=True, text=True)
        try:
            j = json.loads(pr.stdout or "{}"); s = (j.get("streams") or [{}])[0]
            return {"nb_frames": s.get("nb_read_frames"), "dur": (j.get("format") or {}).get("duration")}
        except Exception:
            return {"err": pr.stderr[-200:]}

    def _micro_fps(log):
        # best-effort: pull any Remotion/micro fps or micro-leg timing the render logs
        hits = re.findall(r"(micro[^\n]*?(?:fps|rendered|[0-9.]+\s*fps)[^\n]*)", log, re.I)
        return hits[-3:] if hits else None

    def _spy(*args, **kwargs):
        source_path, cuts, edit_plan, output_path, transcript, work_dir = args[:6]
        RESULT["captured"] = True
        arms = [("b8", "8"), ("b8b", "8"), ("b16", "16")]
        outs, walls, micro = {}, {}, {}
        for name, budget in arms:
            os.environ["PROMPTLY_OVERLAY_TAB_BUDGET"] = budget
            outp = os.path.join(work_dir, f"out_{name}.mp4")
            _buf = io.StringIO()
            t0 = time.time()
            with contextlib.redirect_stdout(_buf):
                _orig_render(source_path, copy.deepcopy(cuts), copy.deepcopy(edit_plan),
                             outp, transcript, work_dir, **kwargs)
            walls[name] = round(time.time() - t0, 1)
            outs[name] = outp
            micro[name] = _micro_fps(_buf.getvalue())
        RESULT["render_wall_s"] = walls
        RESULT["micro_log"] = micro
        RESULT["probe"] = {n: _probe(p) for n, p in outs.items()}
        nf = {n: RESULT["probe"][n].get("nb_frames") for n in outs}
        RESULT["frame_locked"] = (nf["b8"] == nf["b8b"] == nf["b16"] and nf["b8"] is not None)
        RESULT["nb_frames"] = nf
        raise _CaptureDone()

    H.render_multi_clip = _spy
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/concurrency-ab/{jid}/out.mp4"
    body = {"job_id": jid, "video_url": SRC,
            "vibe": "High-energy viral edit with punchy zooms and emphasis",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url,
            "public_url": url, "model": "flare", "supports_progressive": False,
            "premium_pipeline_enabled": False, "mode": "full"}
    try:
        H.handler({"input": body})
    except _CaptureDone:
        pass
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
    print("=== CONCURRENCY A/B (true-replay): PROMPTLY_OVERLAY_TAB_BUDGET 8 vs 16 @ cpu=16 ===")
    o = run.remote()
    assert o, "no result"
    if o.get("pipeline_err"):
        print("PIPELINE ERROR:", o["pipeline_err"]); print("tb:", o.get("tb", ""))
    print("captured:", o.get("captured"), "| warn:", o.get("warn"), "| cores_reported:", o.get("cores_reported"))
    print("frame_locked (must be True for a clean A/B):", o.get("frame_locked"), "| nb_frames:", o.get("nb_frames"))
    walls = o.get("render_wall_s") or {}
    print("render_wall_s:", json.dumps(walls))
    if walls.get("b8") and walls.get("b16"):
        b8, b8b, b16 = walls["b8"], walls.get("b8b", walls["b8"]), walls["b16"]
        noise = abs(b8 - b8b)
        delta = b8 - b16  # positive => 16 FASTER (uses idle cores)
        print(f"\n  b8={b8}s  b8b={b8b}s (determinism noise {noise}s)  b16={b16}s")
        print(f"  16-vs-8: {delta:+.1f}s ({100*delta/b8:+.0f}%)  =>",
              "16 FASTER — uses the idle cores, FLIP IT" if delta > noise else
              ("16 SLOWER — RE-CONTENDS, cores//2 stays" if delta < -noise else "within noise — inconclusive"))
    print("micro_log:", json.dumps(o.get("micro_log")))
    print("\nCONCURRENCY A/B COMPLETE.")
