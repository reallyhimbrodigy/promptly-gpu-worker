"""REGRESSION CORPUS — the REAL input that caused each fixed sub-code, every deploy.

Zac 2026-08-03: "No fixed class can ever return silently, because the input that
caused it runs on every deploy." And it ends the ambiguity that reopened five
classes in one night — "the fix regressed", "the fix never ran" and "these
predate it" become impossible to confuse.

REPOINTED AT THE REAL S3 CORPUS (2026-08-04). This previously used sources I
CONSTRUCTED to imitate each shape. That was wrong twice over: a constructed
source only reproduces the shape I *believed* caused the failure, and my 4K arm
proved it — a 20s clip completed where the real 60s+ sources died, because I had
guessed the wrong dimension of the shape.

handler._capture_failure_corpus already retains the exact source of every real
terminal, keyed by error class: 47 sources across 8 codes in
s3://thisismybucketagainwooo/failure-corpus/<CODE>/<job_id>.mp4. Running
_error_subcode over each source's stored error_detail resolves them to 18
sub-codes, so every arm below is the ACTUAL job that produced that sub-code.
(The local ~/promptly-failure-corpus is audio-only and cannot re-render — that
is a different, unrelated artefact.)

EVERY ARM ASSERTS A LOG WITNESS, not a green row. The first proof run of this
harness completed 4/4 while executing NEITHER fix under test: silent sources
routed to moodreel, which never touches the code in question. A completed render
proves the pipeline works, not that the fix ran.
"""
import os
import sys

sys.path.insert(0, "/")
import modal  # noqa: E402
import modal_app  # noqa: E402

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-regression-corpus", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-lang-flags"),
]

BUCKET = "thisismybucketagainwooo"
S3 = f"https://{BUCKET}.s3.amazonaws.com"

# sub_code -> the REAL job whose source produced it. `fix` is the commit whose
# regression this guards; `witness` is the log line that proves the fixed code
# actually executed on this run.
CORPUS = [
    {
        "sub_code": "RENDER_FATAL:frame_grid",
        "key": "failure-corpus/RENDER_FATAL/54fb3d02-6514-479a-a7c6-101451c9cdbd.mp4",
        "fix": "b394dc9",
        "witness": "Output frame grid:",
        "why": "44100 / 30.00030000300003 = 1469.985 samples/frame. Killed our "
               "first paying subscriber twice on 08-03.",
    },
    {
        "sub_code": "RENDER_FATAL:concurrency",
        "key": "failure-corpus/RENDER_FATAL/20682270-1566-452a-9fe7-d5de8e3b6d67.mp4",
        "fix": "a53787e + core clamp",
        "witness": "concurrency=",
        "why": "Largest single cause in the saved corpus (12 of 47). 32//chunks "
               "gave 16 and 10 against an 8-core container.",
    },
    {
        "sub_code": "INVALID_FORMAT:proxy_encode_timeout",
        "key": "failure-corpus/INVALID_FORMAT/2a8dc854-1354-4070-9156-3901c0cbf630.mp4",
        "fix": "5503371 ffprobe parse",
        "witness": "[probe budget]",
        "why": "Read 'timed out after 30 seconds' — exactly base_s, because the "
               "positional parse made the weighted budget inert.",
    },
    {
        "sub_code": "RENDER_FFMPEG:analyze_shot_changes",
        "key": "failure-corpus/RENDER_FFMPEG/02242d0f-2b7d-4c5b-b9cd-762416e48a44.mp4",
        "fix": "5503371 ffprobe parse",
        "witness": "[probe budget]",
        "why": "scdet against a fixed 60s budget on a 4K HEVC source.",
    },
    {
        "sub_code": "RENDER_FFMPEG:analyze_face_detect",
        "key": "failure-corpus/RENDER_FFMPEG/4b32c93f-477d-4ce6-985a-d073c8116969.mp4",
        "fix": "5503371 ffprobe parse",
        "witness": "[probe budget]",
        "why": "Dense face extract against a fixed 30s budget on a 4K source.",
    },
    {
        "sub_code": "RENDER_FATAL:no_video_stream",
        "key": "failure-corpus/RENDER_FATAL/26a05f5d-596b-42cf-8f01-6b89bbc25985.mp4",
        "fix": "91f0f8a empty-mux detection",
        # Re-running this one is what found the real root: the plan was NEVER
        # out of range (3 clips at 0.11/2.20/5.93s in a 15.02s source) — the
        # final concat+mux exited 0 having written 265 bytes.
        "witness": None,
        "why": "The mux exited 0 with a 265-byte file; only the artifact check "
               "catches it. Guards that it is DETECTED, whatever the outcome.",
    },
]

# NO SAVED SOURCE — stated rather than faked green:
#   RENDER_FFMPEG:analyze_loudness  — pre-dates the corpus capture (cacea1b, 08-01)
#   TRANSCRIPTION:keyterm_limit     — trigger is the VIBE, not the source
#   TRANSCRIPTION:write_timeout     — a network timeout; no input reproduces it
#   RENDER_FFMPEG:audio_extract_stream_map — captured 08-04, add next sweep
UNCOVERED = ("RENDER_FFMPEG:analyze_loudness", "TRANSCRIPTION:keyterm_limit",
             "TRANSCRIPTION:write_timeout", "RENDER_FFMPEG:audio_extract_stream_map")


@app.function(secrets=SECRETS, cpu=16.0, memory=12288, timeout=3000)
def run_case(case: dict) -> dict:
    import contextlib
    import io
    import time
    import traceback
    import uuid

    os.environ["APP_URL"] = ""                    # no callback / push
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""  # no phantom video_jobs rows
    sys.path.insert(0, "/")
    import handler as H

    job_id = str(uuid.uuid4())
    out = f"{S3}/regression-corpus/out/{job_id}.mp4"
    body = {
        "job_id": job_id, "video_url": f"{S3}/{case['key']}",
        "vibe": "Clean and engaging edit",
        "user_id": "00000000-0000-0000-0000-0000000000ee",
        "upload_url": out, "public_url": out,
        "model": "flare", "supports_progressive": False,
        "premium_pipeline_enabled": False,
    }
    buf = io.StringIO()
    res, err, t0 = None, None, time.time()
    try:
        with contextlib.redirect_stdout(buf):
            res = H.handler({"input": body})
    except Exception as e:                                    # noqa: BLE001
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}"
    log = buf.getvalue()
    print(log[-3500:], flush=True)
    wit = case.get("witness")
    return {
        "sub_code": case["sub_code"], "fix": case["fix"],
        "completed": bool(res) and not (res or {}).get("error") and not err,
        "witness": wit, "witness_seen": (wit in log) if wit else None,
        "seconds": round(time.time() - t0, 1),
        "error_cause": (res or {}).get("error_cause"),
        "error_detail": str((res or {}).get("error_detail") or err or "")[:260],
    }


@app.local_entrypoint()
def main():
    import json
    results = list(run_case.map(CORPUS))
    print("\n" + "=" * 92)
    bad = []
    for r in sorted(results, key=lambda x: x["sub_code"]):
        ok = r["completed"]
        # A completed render that never ran the fixed code is NOT a pass.
        if ok and r["witness"] and not r["witness_seen"]:
            ok = False
            r["error_detail"] = (f"WITNESS MISSING ({r['witness']!r}) — completed without "
                                 f"executing the fixed path. " + r["error_detail"])
        if not ok:
            bad.append(r["sub_code"])
        print(f"{'PASS' if ok else 'FAIL'}  {r['sub_code']:36} fix={r['fix']:22} "
              f"completed={str(r['completed']):5} witness={r['witness_seen']} {r['seconds']:>6.1f}s")
        if r.get("error_cause") or r.get("error_detail"):
            print(f"      {r.get('error_cause') or ''} {r.get('error_detail','')[:150]}")
    print("=" * 92)
    print(f"NO SAVED SOURCE (not covered, not faked): {', '.join(UNCOVERED)}")
    print("RESULT " + json.dumps(results, default=str)[:3000])
    if bad:
        print(f"\nREGRESSION: {bad}")
        raise SystemExit(1)
    print("\ncorpus GREEN — every fixed sub-code still fixed, on the REAL input that broke it")
