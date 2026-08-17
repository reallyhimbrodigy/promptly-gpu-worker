"""REPLAY THE MASKED FAILURES — read the cause the error handler destroyed.

`[Rule 2, Rule 4]`

WHY. 135 production failures across 44 users all reported ONE frame
(`handler.py:41270 in <dictcomp>()`) and ONE reason
(`TypeError: float() ... not 'dict'`). That was the error handler crashing on
top of whatever actually went wrong: each job entered the `except` for some REAL
reason and the coercion overwrote it. v549 fixed the coercion, so a job that
fails now records its own cause — but production traffic is ~5-8 jobs/hour and
will not produce a 20-failure diagnostic tonight.

So replay the failures instead of waiting for new ones.

REPLAY FIDELITY IS THE WHOLE POINT — it must reproduce PRODUCTION, not a
friendlier pipeline:
  • BUILD LANE IS **NOT** MARKED. `_editorial_suppressed()` is
    `(not build_lane) and (not EDITORIAL_LIVE)`, so marking the lane would open
    the editorial gate and run a DIFFERENT pipeline than the one that failed.
    Left unmarked, these replays take the deterministic path exactly as live
    traffic does.
  • The payload mirrors dispatch-to-modal.js's real `payload` object
    (job_id / video_url / vibe / user_id / app_url / model), so the worker
    branches the same way.

IT MUST NOT TOUCH THE USERS' ROWS. These are 10 real jobs belonging to 10 real
people, already failed and already refunded:
  • `JOB_STATUS_WRITES_ENABLED` unset -> the durable status layer no-ops.
  • `APP_URL=""` -> no completion POST, no callback, no SSE.
  • `upload_url` points at a SCRATCH key (`replay-scratch/<job>-replay.mp4`),
    never the user's delivery key, and the job's s3 output bucket/key are not
    passed at all. Safety comes from WHERE it writes. My first attempt OMITTED
    upload_url entirely, which did not make the replay safe — handler requires
    the field, so it made the replay INERT and it rejected in 0.0s.
  • The job_id is SUFFIXED so any write that escapes those three cannot collide
    with the real row.

WHAT IT REPORTS. Per job: the exception type/message and the deepest frame in
our own code, extracted the same way `_worker_terminalise` does. Then the
DISTRIBUTION — how many distinct reasons and frames across the ten. If the
replays SUCCEED where production failed, that is the more important finding and
it is reported first, because it inverts the investigation: the cause would then
be environmental (concurrency, container state, a source that has since changed)
rather than a defect in the plan or the render code.

PRICED: ~$1.00 for ten. Sources are 5.3-10.6s (87s total), cpu=16/12GiB, and a
short render is well under a dollar in aggregate.

    modal run replay_masked_app.py --jobs-json "$(cat /tmp/replay10.json)"
"""
import json
import os
import sys

import modal

# `/` MUST be on sys.path BEFORE this import, at MODULE scope. Modal re-imports
# this module inside the container to deserialize the function, and that import
# runs long before any function body — so a sys.path fix inside replay_one() is
# far too late. The first two runs died exactly here with
# `ModuleNotFoundError: No module named 'modal_app'`, crash-looping the
# container. cert_blur_truereplay_app.py puts this line at module scope for the
# same reason.
sys.path.insert(0, "/")

import modal_app as _prod  # noqa: E402 — must follow the sys.path insert above

app = modal.App("replay-masked")

# modal_app.py is NOT one of the production image's add_local_file mounts (only
# handler.py and its siblings are), but this module imports it at module level —
# and Modal re-imports the module inside the container to deserialize the
# function. So without this the container dies at IMPORT, before any of the
# harness's own error handling exists, and surfaces as a bare RemoteError with no
# Python traceback. That is exactly how the first run of this file failed.
# cert_blur_truereplay_app.py already carried this line; I did not copy it.
_IMAGE = _prod.image.add_local_file("modal_app.py", "/modal_app.py")

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-lang-flags"),
]


@app.function(image=_IMAGE, secrets=SECRETS, cpu=16, memory=12288, timeout=1800)
def replay_one(job: dict) -> dict:
    import time as _t
    import traceback as _tb

    sys.path.insert(0, "/")
    # PRODUCTION CONDITIONS. Not the build lane — see the module docstring.
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ.pop("PROMPTLY_BUILD_LANE", None)

    import handler as H

    _jid = str(job.get("job_id") or "")
    out = {
        "job_id": _jid[:8],
        "build_sha": os.environ.get("PROMPTLY_BUILD_SHA", "")[:12],
        "editorial_suppressed": None,
        "ok": False,
        "reason": None,
        "frame": None,
        "frames": [],
        "wall_s": None,
    }
    try:
        out["editorial_suppressed"] = H._editorial_suppressed()
    except Exception:
        pass

    # upload_url IS REQUIRED — handler rejects the job without it, which is what
    # the corrected harness surfaced ("Missing required input fields: upload_url")
    # after I omitted it for safety. Omitting it did not make the replay safe, it
    # made it inert. So point it at a SCRATCH key instead: safety comes from
    # WHERE it writes, never from refusing to give it a destination.
    _dest = ""
    try:
        # The bucket env is S3_BUCKET_NAME (fallback SUPABASE_S3_BUCKET, then the
        # literal default) — NOT AWS_S3_BUCKET, which I guessed and which does
        # not exist. The guess produced an empty _dest, the presign block was
        # skipped silently, and the replay rejected on the very field this code
        # was added to supply. The `[replay] scratch destination:` line never
        # printing is what gave it away.
        _bucket = (os.environ.get("S3_BUCKET_NAME")
                   or os.environ.get("SUPABASE_S3_BUCKET")
                   or "promptly-video-storage")
        if _bucket and getattr(H, "_aws_s3_client", None) is not None:
            _dest = H._aws_s3_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": _bucket,
                        "Key": f"replay-scratch/{_jid}-replay.mp4"},
                ExpiresIn=3600,
            )
            print(f"[replay] scratch destination: replay-scratch/{_jid}-replay.mp4 "
                  f"(NEVER the user's delivery key)", flush=True)
    except Exception as _de:
        print(f"[replay] !! scratch presign FAILED ({type(_de).__name__}: {_de}) — "
              f"the replay CANNOT run; it would reject on the missing field and "
              f"report a harness fault as a pipeline finding", flush=True)
    if not _dest:
        # FAIL LOUD RATHER THAN PRODUCE A FALSE READ. An empty destination makes
        # handler reject in 0.0s on a missing field, which looks like a result
        # and is not one.
        out["reason"] = ("HARNESS FAULT: no scratch upload_url could be presigned "
                         f"(bucket={_bucket!r}, client={getattr(H, '_aws_s3_client', None) is not None}) "
                         "— this is NOT a pipeline finding")
        print(f"[replay] {out['job_id']} {out['reason']}", flush=True)
        return out

    payload = {
        "job_id": _jid + "-replay",   # never collide with the real row
        "upload_url": _dest,
        "video_url": job.get("video_url"),
        "vibe": job.get("vibe") or "",
        "user_id": job.get("user_id"),
        "app_url": "",
        "model": "flare",
        "premium_pipeline_enabled": False,
        "supports_progressive": False,
    }
    _t0 = _t.time()
    try:
        res = H.handler({"input": payload})
        out["wall_s"] = round(_t.time() - _t0, 1)
        _r = res if isinstance(res, dict) else {}
        _o = _r.get("output") if isinstance(_r.get("output"), dict) else _r
        _o = _o or {}
        out["produced_video"] = bool(_o.get("video_url"))
        out["result_keys"] = sorted(k for k in _o if not k.startswith("_"))[:14]
        # NOT RAISING IS NOT SUCCEEDING. handler() catches its own errors and
        # RETURNS an error envelope — so treating "no exception" as ok=True
        # reported `SUCCEEDED in 0.0s video=False` for two jobs that plainly did
        # not render, and would have had me announce that the investigation
        # inverts on a harness artifact. A replay SUCCEEDED only if it produced
        # a video and carries no error code.
        _err = (_o.get("error_code") or _o.get("error")
                or _r.get("error_code") or _r.get("error"))
        # ASSERT THE ARTIFACT, NOT THE FIELD. `video_url` is a CLAIM the
        # pipeline makes about its own output; the object either exists in S3 or
        # it does not. This whole night has been a run of harness results that
        # looked right and were not — "SUCCEEDED in 0.0s video=False" was the
        # worst — and every one of them was a field being trusted instead of a
        # thing being checked. HEAD the scratch key and require real bytes.
        _artifact_bytes = 0
        try:
            _h = H._aws_s3_client.head_object(
                Bucket=_bucket, Key=f"replay-scratch/{_jid}-replay.mp4")
            _artifact_bytes = int(_h.get("ContentLength") or 0)
        except Exception as _he:
            out["artifact_probe"] = f"{type(_he).__name__}"
        out["artifact_bytes"] = _artifact_bytes
        _ARTIFACT_FLOOR = 100_000   # a real render is MB; anything less is a stub
        out["ok"] = (_artifact_bytes >= _ARTIFACT_FLOOR) and not _err
        if out["ok"] and not out["produced_video"]:
            print(f"[replay] {out['job_id']} NOTE: artifact exists "
                  f"({_artifact_bytes} B) but result carried no video_url", flush=True)
        if not out["ok"]:
            out["reason"] = (f"RETURNED ERROR ENVELOPE: {_err}"
                             if _err else
                             f"NO ARTIFACT IN S3 ({_artifact_bytes} B, floor "
                             f"{_ARTIFACT_FLOOR}) despite no error_code; "
                             f"video_url_claimed={out['produced_video']} "
                             f"keys={out['result_keys']}")
            out["envelope"] = {k: str(_o.get(k))[:1200] for k in
                               ("error", "error_code", "error_detail", "user_message",
                                "error_where", "requires_new_video") if _o.get(k)}
            print(f"[replay] {out['job_id']} NOT-OK in {out['wall_s']}s -> "
                  f"{out['reason']}", flush=True)
        else:
            print(f"[replay] {out['job_id']} SUCCEEDED in {out['wall_s']}s "
                  f"artifact={_artifact_bytes/1e6:.2f}MB", flush=True)
    except BaseException as e:   # noqa: BLE001 — the point is to catch everything
        out["wall_s"] = round(_t.time() - _t0, 1)
        out["reason"] = f"{type(e).__name__}: {str(e)[:300]}"
        try:
            for fr in reversed(_tb.extract_tb(e.__traceback__)):
                fn = str(fr.filename or "")
                if "/site-packages/" in fn or "/usr/lib/" in fn:
                    continue
                out["frames"].append({
                    "file": fn.rsplit("/", 1)[-1], "line": fr.lineno,
                    "func": fr.name, "code": (fr.line or "")[:160],
                })
                if len(out["frames"]) >= 3:
                    break
            if out["frames"]:
                f0 = out["frames"][0]
                out["frame"] = f"{f0['file']}:{f0['line']} in {f0['func']}()"
        except Exception:
            pass
        print(f"[replay] {out['job_id']} FAILED {out['reason']} @ {out['frame']}", flush=True)
    return out


@app.local_entrypoint()
def main(jobs_json: str = ""):
    jobs = json.loads(jobs_json) if jobs_json else json.load(open("/tmp/replay10.json"))
    print(f"=== REPLAY {len(jobs)} MASKED RENDER FAILURES on v549 — priced ~$1.00 ===")
    results = list(replay_one.map(jobs))

    ok = [r for r in results if r.get("ok")]
    bad = [r for r in results if not r.get("ok")]
    print("\n" + "=" * 66)
    print(f"REPLAYED {len(results)}  |  SUCCEEDED {len(ok)}  |  FAILED {len(bad)}")
    print("=" * 66)
    if ok:
        print(f"\n!! {len(ok)}/{len(results)} REPLAYS SUCCEEDED where production FAILED.")
        print("   That INVERTS the investigation: the cause is environmental")
        print("   (concurrency, container state, a source that changed), not a")
        print("   defect in the plan or the render code.")
        for r in ok:
            print(f"     {r['job_id']} ok in {r['wall_s']}s "
                  f"artifact={(r.get('artifact_bytes') or 0)/1e6:.2f}MB")
    import collections
    if bad:
        reasons = collections.Counter(str(r.get("reason"))[:90] for r in bad)
        frames = collections.Counter(r.get("frame") for r in bad)
        print(f"\n  DISTINCT REASONS ({len(reasons)}):")
        for k, v in reasons.most_common():
            print(f"     {v:3}x  {k}")
        print(f"\n  DISTINCT FRAMES ({len(frames)}):")
        for k, v in frames.most_common():
            print(f"     {v:3}x  {k}")
        _mask = sum(1 for r in bad if "41270" in str(r.get("frame")))
        print(f"\n  STILL THE MASK: {_mask}/{len(bad)}"
              + ("  -> v549 did NOT take" if _mask else "  -> the mask is gone; these are REAL causes"))
        for r in bad[:4]:
            print(f"\n  --- {r['job_id']} ---")
            if r.get("envelope"):
                print(f"      envelope: {r['envelope']}")
            for f in r.get("frames", []):
                print(f"      {f['file']}:{f['line']} in {f['func']}()  ->  {f['code']}")
    print(f"\n  suppressed(editorial) on the replays: "
          f"{sorted({r.get('editorial_suppressed') for r in results})}  (True == production conditions)")
    print(f"  build_sha: {sorted({r.get('build_sha') for r in results})}")
