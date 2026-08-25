"""PROMPT V2 A/B — arm A (production doctrine) vs arm B (beat-major), PLAN-ONLY.

Runs exactly what PROMPT_V2_AB_PREREGISTRATION.md specifies, and nothing it does
not. The thresholds were fixed BEFORE this file existed; this only produces the
numbers they are read against.

  arm A   the current ~2,000-line doctrine, component-major arrays
  arm B   prompt_v2_editor's 111-line doctrine, beat-major, catalog REUSED
  both    gemini-3.7-flash, thinking 2048, SERIAL, plan-only

SERIAL IS NOT OPTIONAL AND NOT A PREFERENCE. The concurrency confound is
measured: a 24-way cell.map produced a 41.7% safe-edit fallback rate that a
serial control refuted at 0/5. Anything run concurrently here measures the
harness. One container, one cell at a time, synchronous .remote() — and no
.spawn(), because a spawned container outlives this process and a batch is only
dead when `modal app list` shows 0 tasks.

PLAN-ONLY because a render cannot change what the PLANNER emits, and rendering
26 cells would cost more than the question is worth. The PLAN_ONLY seam returns
the finalized plan with full-fidelity upstream signals (real transcribe, proxy,
faces) — the planner sees exactly what it sees in production.

CORPUS: component_corpus_manifest.json — 13 trigger-annotated sources
(brand_copy 7 / scenes 10 / payoff 5). A component with no trigger in the source
is a CORRECT decline, and scoring that as a defect manufactures a signal; three
corpora in a row did exactly that before this one existed.

COST, priced in advance: 26 cells x ~$0.20 = ~$5.20. No render.

    modal run cert_prompt_v2_ab_app.py
"""
import os
import sys
import json

sys.path.insert(0, "/")
import modal, modal_app                                            # noqa: E402

image = (modal_app.image
         .add_local_file("modal_app.py", "/modal_app.py")
         .add_local_file("component_corpus_manifest.json",
                         "/component_corpus_manifest.json"))
app = modal.App("cert-prompt-v2-ab", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           # The FULL live secret set, including lang-flags: a missing secret
           # changes the flags the planner runs under and confounds both arms.
           modal.Secret.from_name("promptly-lang-flags")]

RUN_TAG = "run"
FAMILIES = ("cut_refinements", "emphasis_moments", "text_overlays", "broll_clips",
            "generated_scenes", "motion_graphics", "caption_keywords",
            "caption_position_changes")


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=7200)
def run(n_sources: int, run_tag: str, arms: str = "AB", repeats: int = 1,
        offset: int = 0) -> dict:
    global RUN_TAG
    RUN_TAG = run_tag
    import time
    import uuid
    import traceback
    from build_lane import mark_build_lane
    mark_build_lane("cert_prompt_v2_ab_app.py")
    # No completion callback, no phantom video_jobs rows — this must not touch
    # production analytics or leave rows a later read would cut into a cohort.
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    # Both arms at the pre-registered thinking budget, set here rather than
    # inherited, so the run cannot silently measure a different one.
    os.environ["PROMPTLY_POST_THINKING_BUDGET"] = "2048"
    # The global v2 flag must NOT decide anything here — the arm does, per job.
    os.environ.pop("PROMPTLY_PROMPT_V2", None)
    sys.path.insert(0, "/")
    import handler as H

    manifest = json.load(open("/component_corpus_manifest.json"))
    # OFFSET crosses as an ARGUMENT, like arms and repeats — an env var read
    # inside the container does not exist there. Resuming a run that died
    # part-way needs the tail, not the head.
    _all = [s for s in manifest["sources"] if s.get("video_url")]
    sources = _all[max(0, offset):max(0, offset) + max(1, n_sources)]
    OUT = {"built": manifest.get("built"), "cells": [], "errors": []}

    def _plan_counts(plan):
        if not isinstance(plan, dict):
            return {}
        c = {}
        for f in FAMILIES:
            v = plan.get(f)
            c[f] = len(v) if isinstance(v, list) else 0
        return c

    def _one(src, arm):
        jid = str(uuid.uuid4())
        url = ("https://thisismybucketagainwooo.s3.amazonaws.com/"
               f"prompt-v2-ab/{arm}/{jid}/out.mp4")
        body = {
            "job_id": jid,
            "video_url": src["video_url"],
            "vibe": src.get("vibe") or "Make it viral",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": url, "public_url": url,
            "model": "flare",
            "supports_progressive": False,
            "premium_pipeline_enabled": False,
            "plan_only": True,
        }
        if arm == "B":
            body["prompt_v2_test"] = True
        try:
            H._component_ledger_reset()
            H._GEMINI_CALL_LOG.clear()
        except Exception:
            pass
        t0 = time.time()
        # TEE, don't redirect: a failed cell must carry the TEXT it failed on.
        # Three arm-B cells died with `string-runaway` and the harness recorded
        # only the class name, so each diagnosis cost another paid run. The tail
        # of the model's own output is the evidence; keep it on the cell.
        import io as _io

        class _Tee:
            def __init__(self, real):
                self.real, self.buf = real, _io.StringIO()

            def write(self, s):
                self.real.write(s)
                try:
                    self.buf.write(s)
                except Exception:
                    pass
                return len(s)

            def flush(self):
                self.real.flush()

        _tee = _Tee(sys.stdout)
        _orig = sys.stdout
        sys.stdout = _tee
        try:
            # handler takes the RunPod envelope, not the body — job["input"].
            res = H.handler({"input": body}) or {}
        except Exception as e:
            return {"source": src["id"], "arm": arm, "error": f"{type(e).__name__}: {e}",
                    "traceback": traceback.format_exc()[-900:],
                    "stdout_tail": _tee.buf.getvalue()[-2500:],
                    "wall_s": round(time.time() - t0, 1)}
        finally:
            sys.stdout = _orig
        plan = res.get("edit_plan") if isinstance(res, dict) else None
        _no_plan = not isinstance(plan, dict)
        beats = (plan or {}).get("beats") if isinstance(plan, dict) else None
        cell = {
            "source": src["id"],
            "arm": arm,
            "triggers": sorted((src.get("triggers") or {}).keys()),
            "duration_s": src.get("duration_s"),
            "status": (res or {}).get("status"),
            "wall_s": round(time.time() - t0, 1),
            "gemini_call_s": (res or {}).get("gemini_call_s"),
            "gemini_output_tokens": (res or {}).get("gemini_output_tokens"),
            "gemini_n_calls": (res or {}).get("gemini_n_calls"),
            "tokens": (H._gemini_token_summary() if hasattr(H, "_gemini_token_summary") else None),
            "counts": _plan_counts(plan),
            # requested / dropped_by_us per component — the two numbers the
            # pre-registration actually reads. Rendered counts cannot tell a
            # decline from our own drop.
            "ledger": H._component_ledger_snapshot(),
            "safe_edit": bool((plan or {}).get("_safe_edit")) if isinstance(plan, dict) else None,
        }
        if _no_plan:
            # A CELL THAT PRODUCED NO PLAN IS A FAILED CELL, even when handler
            # returned an envelope instead of raising — three arm-B cells read
            # `err=False, counts={}` and the harness kept no evidence, so each
            # diagnosis cost another paid run. Keep the model's own tail.
            cell["no_plan"] = True
            cell["result_error"] = {k: res.get(k) for k in
                                    ("status", "error", "error_code", "error_class",
                                     "user_message", "reason") if isinstance(res, dict)}
            cell["stdout_tail"] = _tee.buf.getvalue()[-2500:]
        if isinstance(beats, list):
            cell["n_beats"] = len(beats)
            # `beats[].read` verbatim — the first look at what the model saw.
            cell["reads"] = [str(b.get("read") or "")[:200]
                             for b in beats[:40] if isinstance(b, dict)]
            try:
                import prompt_v2_schema as P
                cell["density"] = P.density_of(plan, float(src.get("duration_s") or 0))
            except Exception:
                pass
            # THE PRE-REGISTERED METRICS, SURFACED. flatten_beats computes these
            # into _v2_counts and this harness read only `counts`/`density`/
            # `ledger` — so they were built, certified, proven end to end, and
            # invisible in the result. A $0.40 smoke found it; 26 cells would
            # have cost $5.20 to reach the same blindness.
            _vc = plan.get("v2_counts") or {}
            for _k in ("beats_unresolvable", "purpose_distribution",
                       "beat_durations_s", "unresolvable_detail"):
                if _k in _vc:
                    cell[_k] = _vc[_k]
            # PURPOSE x EMPTY, paired per beat. "Which KIND of beat gets left
            # bare" is the arcads claim under test: if `breath` beats are the
            # empty ones, restraint is being chosen deliberately; if `payoff`
            # beats are empty, the model is failing to place where it matters
            # most. A total bare-count cannot tell those apart.
            _pe = {}
            for _b in beats:
                if not isinstance(_b, dict):
                    continue
                _p = str(_b.get("purpose") or "(absent)")
                _slot = _pe.setdefault(_p, {"total": 0, "empty": 0})
                _slot["total"] += 1
                if not P._beat_moves(_b):
                    _slot["empty"] += 1
            cell["purpose_x_empty"] = _pe
        return cell

    for src in sources:
        # SMOKE MODE (2026-08-24). ARMS=B runs arm B alone so the schema change
        # can be proven for ~$0.20 before the remaining 25 cells are fired. v2's
        # cells died three times on `string-runaway` before producing data;
        # learning that at $0.20 instead of $5.20 is the entire point.
        # ARMS CROSSES AS AN ARGUMENT, NOT AN ENV VAR. The first cut read
        # os.environ inside the container, where the local `ARMS=B` was never
        # set — so the filter silently did nothing and both arms ran ($0.40, not
        # $0.20). Same class as the build-lane CORE_BUDGET trap: an env var set
        # locally does not exist remotely.
        for arm in tuple(arms.upper()):
          # REPEATS: the same source, same arm, N times. Silence turned out to be
          # NON-DETERMINISTIC — one source answered with 8 beats and then went
          # silent 20 minutes later — so a single cell per source cannot tell a
          # broken shape from a coin flip, which is exactly what the
          # silent-source threshold was about to be scored on.
          for _rep in range(max(1, repeats)):
            cell = _one(src, arm)
            cell["rep"] = _rep          # so silence is attributable PER SOURCE
            OUT["cells"].append(cell)
            if cell.get("error"):
                OUT["errors"].append({"source": cell["source"], "arm": arm,
                                      "error": cell["error"]})
            print(f"[cell] {src['id'][:28]:30} arm={arm} wall={cell.get('wall_s')}s "
                  f"counts={cell.get('counts')} err={bool(cell.get('error'))} "
                  f"no_plan={bool(cell.get('no_plan'))}", flush=True)
            # THE DURABLE RECORD. The first full run died on `local client
            # disconnected` with 0 cells written: the results only existed in the
            # local entrypoint's return value, so a dropped client threw away
            # every completed cell AND the money that bought it. One JSON line
            # per cell means `modal app logs` is the record of truth, and the
            # run survives losing the thing watching it.
            print("[celljson] " + json.dumps(cell, default=str), flush=True)
            # AND PERSIST FROM INSIDE THE CONTAINER. Two full runs died on the
            # LOCAL client — once "local client disconnected", once
            # "ConnectionError: Deadline exceeded" — and took every completed
            # cell with them, because the results only ever existed in the
            # entrypoint's return value. A result that lives only in the thing
            # watching the run is not a result; the run must survive losing its
            # observer. Written after EVERY cell, so a death costs one cell.
            try:
                import boto3
                boto3.client("s3").put_object(
                    Bucket="thisismybucketagainwooo",
                    Key=f"prompt-v2-ab/{RUN_TAG}/partial.json",
                    Body=json.dumps(OUT, default=str).encode(),
                    ContentType="application/json")
            except Exception as _s3e:
                print(f"[celljson] S3 persist failed (non-fatal): "
                      f"{type(_s3e).__name__}", flush=True)
    return OUT


@app.local_entrypoint()
def main():
    n = int(os.environ.get("N_SOURCES", "13") or "13")
    tag = os.environ.get("RUN_TAG") or "run"
    print(f"PROMPT V2 A/B — {n} sources x 2 arms, SERIAL, plan-only, ~${n * 2 * 0.20:.2f}")
    out = run.remote(n, tag, (os.environ.get("ARMS") or "AB").upper(),
                     int(os.environ.get("REPEATS", "1") or "1"),
                     int(os.environ.get("SOURCE_OFFSET", "0") or "0"))
    path = "/tmp/prompt_v2_ab_result.json"
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    cells = out.get("cells") or []
    A = [c for c in cells if c["arm"] == "A" and not c.get("error") and not c.get("no_plan")]
    B = [c for c in cells if c["arm"] == "B" and not c.get("error") and not c.get("no_plan")]
    print(f"\n  cells: {len(cells)}  usable A={len(A)} B={len(B)}  errors={len(out.get('errors') or [])}")

    def _req(cells_):
        n_req = n_drop = 0
        for c in cells_:
            for _k, v in (c.get("ledger") or {}).items():
                n_req += int(v.get("requested", 0))
                n_drop += int(v.get("dropped_by_us", 0))
        return n_req, n_drop

    ra, da = _req(A)
    rb, db = _req(B)
    print(f"\n  {'':22}{'arm A':>12}{'arm B':>12}")
    print(f"  {'components requested':22}{ra:>12}{rb:>12}")
    print(f"  {'dropped BY US':22}{da:>12}{db:>12}")
    for f in FAMILIES:
        sa = sum((c.get("counts") or {}).get(f, 0) for c in A)
        sb = sum((c.get("counts") or {}).get(f, 0) for c in B)
        print(f"  {f:22}{sa:>12}{sb:>12}")
    for label, key in (("p50 wall_s", "wall_s"), ("output tokens", "gemini_output_tokens")):
        va = sorted(x for x in (c.get(key) for c in A) if isinstance(x, (int, float)))
        vb = sorted(x for x in (c.get(key) for c in B) if isinstance(x, (int, float)))
        ma = va[len(va) // 2] if va else None
        mb = vb[len(vb) // 2] if vb else None
        print(f"  {label:22}{str(ma):>12}{str(mb):>12}")
    print(f"\n  full result: {path}")
    print("  Read against PROMPT_V2_AB_PREREGISTRATION.md — the thresholds were "
          "fixed before this ran.")
