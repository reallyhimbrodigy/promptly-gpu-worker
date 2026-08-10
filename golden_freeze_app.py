#!/usr/bin/env python3
"""
golden_freeze_app.py — freeze the golden reference plans (LANE 2 / HARNESS).

Runs every source in golden/manifest.json through the CURRENT editorial system
via the PLAN_ONLY seam [CODE handler.py:37714] and captures the emitted plan —
NO render, NO video output, on ANY route:

  * editorial route: PROMPTLY_PLAN_ONLY=1 returns {"status":"plan_only",
    "edit_plan": ...} before render [CODE handler.py:37727].
  * light routes (moodreel/minimal/hype/minimal_speech_uncut) never reach that
    seam [CODE handler.py:32161] — they converge on hype_render.render_hype
    [CODE handler.py:32468]. We monkeypatch it to raise a capture exception
    carrying the converged render_input. render_multi_clip is patched too as
    pure insurance. A render is therefore IMPOSSIBLE in this app.

Routing is left REAL: no PROMPTLY_COVERAGE_GATE override, no moodreel_test —
the golden must record what production would actually do with each source.

Spend: PLAN_ONLY @ cpu=8/32GiB ≈ $0.06–0.09/run [CODE plan_decision_ab_app.py:13].
Owner-priced cap for the whole freeze: $8 (LANE 2 brief). Every batch appends
to MODAL_SPEND_LEDGER.md.

Run (from the lane-harness worktree so the image == live 1601ae0):
  modal run golden_freeze_app.py --runs 3 --out golden/plans
  modal run golden_freeze_app.py --runs 1 --only <source_id>   # smoke a single
"""
import json
import os
import sys

sys.path.insert(0, "/")  # in-container: modal_app.py is mounted at /modal_app.py
import modal  # noqa: E402
import modal_app  # noqa: E402

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("golden-freeze", image=image)

# The FULL deployed secret set — a missing secret changes flags and confounds
# the capture (CLAUDE.md render-determinism law).
SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-lang-flags"),
]

S3 = "https://thisismybucketagainwooo.s3.amazonaws.com"


@app.function(secrets=SECRETS, cpu=8.0, memory=32768, region="us", timeout=1800)
def freeze(source: dict, run_idx: int) -> dict:
    """One capture run. Returns a JSON-safe dict, never renders."""
    import contextlib
    import io
    import time
    import traceback
    import uuid

    os.environ["APP_URL"] = ""                    # no callback / push
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""  # no phantom video_jobs rows
    os.environ["PROMPTLY_PLAN_ONLY"] = "1"        # editorial seam ON
    sys.path.insert(0, "/")
    import handler as H
    import hype_render as _hr

    class _NoRenderCapture(BaseException):
        """Raised at any render boundary; carries the route's plan."""
        def __init__(self, kind, payload):
            self.kind, self.payload = kind, payload

    captured = {"minimal_reason": None}

    _orig_minimal = H._run_minimal_pipeline

    def _spy_minimal(job_id, input_data, work_dir, source_path,
                     source_duration, app_url, reason, pipeline_start):
        captured["minimal_reason"] = reason
        captured["minimal_duration_s"] = source_duration
        return _orig_minimal(job_id, input_data, work_dir, source_path,
                             source_duration, app_url, reason, pipeline_start)

    def _no_render_hype(render_input, source_canonical, output_path, work_dir,
                        *a, **k):
        raise _NoRenderCapture("light_route", {"render_input": render_input})

    def _no_render_editorial(*a, **k):
        # Insurance only — PLAN_ONLY returns before render on the editorial
        # path. If this fires, the seam was bypassed; capture what we can.
        plan = None
        for arg in a:
            if isinstance(arg, dict) and ("emphasis_moments" in arg
                                          or "caption_style" in arg):
                plan = arg
                break
        raise _NoRenderCapture("editorial_render_boundary", {"edit_plan": plan})

    H._run_minimal_pipeline = _spy_minimal
    _hr.render_hype = _no_render_hype
    H.render_multi_clip = _no_render_editorial

    job_id = str(uuid.uuid4())
    sink = f"{S3}/golden-freeze/void/{job_id}.mp4"  # never written (no render)
    body = {
        "job_id": job_id,
        "video_url": source["video_url"],
        "vibe": source.get("vibe", "Clean engaging edit"),
        "user_id": "00000000-0000-0000-0000-00000000901d",
        "upload_url": sink, "public_url": sink,
        "model": source.get("model", "flare"),
        "mode": "full",
        "supports_progressive": False,
        "premium_pipeline_enabled": bool(source.get("premium", False)),
        "plan_only": True,                       # belt AND braces with the env
    }

    buf = io.StringIO()
    t0 = time.time()
    out = {"source_id": source["id"], "run_idx": run_idx, "job_id": job_id}
    try:
        with contextlib.redirect_stdout(buf):
            res = H.handler({"input": body})
        if isinstance(res, dict) and res.get("status") == "plan_only":
            out["kind"] = "editorial"
            out["capture"] = {
                "edit_plan": res.get("edit_plan"),
                "source_duration_s": res.get("source_duration_s"),
                "gemini_call_s": res.get("gemini_call_s"),
                "gemini_output_tokens": res.get("gemini_output_tokens"),
                "gemini_n_calls": res.get("gemini_n_calls"),
            }
        else:
            out["kind"] = "unexpected_return"
            out["capture"] = {"repr": repr(res)[:2000]}
    except _NoRenderCapture as nr:
        out["kind"] = nr.kind
        payload = {}
        try:
            payload = json.loads(json.dumps(nr.payload, default=str))
        except Exception as ser:
            payload = {"_unserializable": type(ser).__name__}
        out["capture"] = payload
        out["capture"]["route_reason"] = captured.get("minimal_reason")
        out["capture"]["source_duration_s"] = captured.get("minimal_duration_s")
    except Exception as err:
        out["kind"] = "error"
        out["capture"] = {"error": f"{type(err).__name__}: {str(err)[:400]}",
                          "trace": traceback.format_exc()[-2000:]}
    out["elapsed_s"] = round(time.time() - t0, 1)
    log = buf.getvalue()
    out["log_tail"] = log[-1500:]
    err_lines = [ln for ln in log.splitlines()
                 if any(t in ln.lower() for t in
                        ("error", "exception", "clienterror", "vertex",
                         "traceback", "429", "403", "400", "transport"))]
    out["log_errors"] = err_lines[-60:]
    try:
        out["gemini_call_log"] = json.loads(
            json.dumps(list(getattr(H, "_GEMINI_CALL_LOG", [])), default=str))
    except Exception:
        pass
    return out


@app.local_entrypoint()
def main(runs: int = 3, out: str = "golden/plans", only: str = "",
         manifest: str = "golden/manifest.json"):
    with open(manifest) as f:
        mf = json.load(f)
    sources = [s for s in mf["sources"] if not only or s["id"] == only]
    if not sources:
        print(f"no sources matched (only={only!r})")
        return
    jobs = [(s, r) for s in sources for r in range(1, runs + 1)]
    est_lo, est_hi = 0.06 * len(jobs), 0.09 * len(jobs)
    print(f"[golden-freeze] {len(sources)} sources x {runs} runs = {len(jobs)} "
          f"PLAN_ONLY captures, est ${est_lo:.2f}-${est_hi:.2f} "
          f"(cap $8, LANE 2 brief)")
    handles = [(s["id"], r, freeze.spawn(s, r)) for (s, r) in jobs]
    n_ok = n_err = 0
    total_container_s = 0.0
    for sid, r, h in handles:
        try:
            res = h.get()
        except Exception as e:
            res = {"source_id": sid, "run_idx": r, "kind": "spawn_error",
                   "capture": {"error": str(e)[:400]}, "elapsed_s": 0}
        total_container_s += float(res.get("elapsed_s") or 0)
        d = os.path.join(out, sid)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"run{r}.json")
        with open(path, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True, default=str)
        ok = res.get("kind") in ("editorial", "light_route")
        n_ok += ok
        n_err += (not ok)
        print(f"  {sid} run{r}: {res.get('kind')} "
              f"({res.get('elapsed_s')}s) -> {path}")
    # cpu=8 + 32GiB; Modal ~$0.135/core-h + ~$0.024/GiB-h
    est = total_container_s * (8 * 0.135 + 32 * 0.024) / 3600
    print(f"[golden-freeze] done: {n_ok} captured, {n_err} failed, "
          f"{total_container_s:.0f} container-s, est ${est:.2f}")
    print("[golden-freeze] APPEND TO MODAL_SPEND_LEDGER.md and verify "
          "`modal app list` shows 0 tasks for golden-freeze.")
