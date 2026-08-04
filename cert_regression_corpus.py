"""REGRESSION CORPUS — the input that caused each fixed class runs on every deploy.

Zac 2026-08-03: "No fixed class can ever return silently, because the input that
caused it runs on every deploy." And it kills the ambiguity that reopened five
classes today: "the fix regressed", "the fix never ran" and "these predate it"
become impossible to confuse, because the shape is re-run at a known instant.

WHY NOT THE EXISTING FAILURE CORPUS. /Users/zaclibman/promptly-failure-corpus
holds audio-only derivatives (audio-wav16, audio-flac48) — it CANNOT re-render
video. The original triggering sources live behind user-media URLs which the
pipeline deletes at teardown ("[video-ref] reference deleted"), so they are not
durable either. Per the durable-source law these are CONSTRUCTED sources that
reproduce the SHAPE, held in our own bucket.

ROUND 1 OF THE PROOF RUN IS WHY EACH ENTRY NAMES A WITNESS. Four silent sources
completed 4/4 while executing NEITHER fix — zero-reject routed them to moodreel,
which never touches the code under test. A green row proves nothing on its own.
Each arm therefore asserts a LOG WITNESS: the line only the fixed path emits.

EXPECTATIONS ARE EXPLICIT. `complete` = fixed, must render. `known_fail` = the
mechanism is named but NOT yet fixed; it must still fail, and a known_fail that
starts completing is a signal to promote it, not a silent pass.
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
BASE = f"https://{BUCKET}.s3.amazonaws.com/regression-corpus"

# Every entry is forged from a REAL job. `witness` is the log substring that
# proves the code under test actually executed.
CORPUS = [
    {
        "sub_code": "RENDER_FATAL:frame_grid",
        "src": f"{BASE}/sp_ntsc.mp4",
        "expect": "complete",
        "witness": "Output frame grid:",
        "why": "29.97 (30000/1001) + 44100 audio = 1471.47 samples/frame. Killed "
               "user 1aa24c33 twice on 08-03. h264/1080x1920 so it takes the "
               "PASSTHROUGH path and the ragged rate really reaches the render.",
    },
    {
        "sub_code": "RENDER_REMOTION:concurrency",
        "src": f"{BASE}/sp_band.mp4",
        "expect": "complete",
        "witness": "concurrency=",
        "why": "61s of speech -> 2-3 overlay chunks. At cpu=8 the hardcoded "
               "32//chunks gave 16 and 10, both above the core count, and "
               "Remotion refused. Job c9e980fe, 08-03 20:23Z.",
    },
    {
        "sub_code": "TRANSCRIPTION:keyterm_limit",
        "src": f"{BASE}/sp_band.mp4",
        "expect": "complete",
        "witness": "keyterms capped",
        # The trigger is the VIBE, not the source: a screenplay-length brief
        # harvests ~200 proper nouns and blows Deepgram's 500-TOKEN cap.
        "vibe": ("FADE IN. INT. WAREHOUSE - NIGHT. " + " ".join(
            f"Sarah Marcus Delgado Okonkwo Fitzgerald Rivera{i}" for i in range(60))
            + " CUT TO: EXT. ROOFTOP - DAY. MONTAGE."),
        "why": "DeepgramApiError: Keyterm limit exceeded (max 500 tokens), "
               "2026-08-04T00:27Z. Also pins that a 4xx is not retried 3x.",
    },
    {
        "sub_code": "RENDER_FFMPEG:analyze_*",
        "src": f"{BASE}/hevc4k.mp4",
        "expect": "known_fail",
        "witness": None,
        "why": "4K HEVC 60fps. ALL 18 RENDER_FFMPEG failures (07-31..08-04) are "
               "analysis subprocesses hitting fixed 30s/60s budgets sized for "
               "1080p h264 — scdet, face-detect, astats. NOT YET FIXED, so this "
               "is expected to fail; when it starts completing, promote it.",
    },
]

# NOT REPRODUCIBLE ON DEMAND, and saying so beats a fake green:
#   RENDER_FATAL:no_video_stream — an internal zoomclip intermediate emitted with
#     no video stream. Depends on a trim running past the source, not on input.
#   TRANSCRIPTION:write_timeout  — a Deepgram network timeout. No input causes it.
UNREPRODUCIBLE = ("RENDER_FATAL:no_video_stream", "TRANSCRIPTION:write_timeout")


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
    key = f"regression-corpus/out/{job_id}.mp4"
    url = f"https://{BUCKET}.s3.amazonaws.com/{key}"
    body = {
        "job_id": job_id,
        "video_url": case["src"],
        "vibe": case.get("vibe") or "Clean and engaging edit",
        "user_id": "00000000-0000-0000-0000-0000000000ee",
        "upload_url": url, "public_url": url,
        "model": "flare", "supports_progressive": False,
        "premium_pipeline_enabled": False,
    }
    # Capture stdout so the WITNESS can be asserted — a completed render that
    # never ran the fixed code is exactly the false green round 1 produced.
    buf = io.StringIO()
    t0 = time.time()
    err = None
    res = None
    try:
        with contextlib.redirect_stdout(buf):
            res = H.handler({"input": body})
    except Exception as e:                                  # noqa: BLE001
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-600:]}"
    log = buf.getvalue()
    print(log[-4000:], flush=True)                          # keep it in modal logs
    ok = bool(res) and isinstance(res, dict) and not res.get("error") and not err
    wit = case.get("witness")
    return {
        "sub_code": case["sub_code"],
        "expect": case["expect"],
        "completed": ok,
        "witness": wit,
        "witness_seen": (wit in log) if wit else None,
        "seconds": round(time.time() - t0, 1),
        "video_url": (res or {}).get("video_url"),
        "error_cause": (res or {}).get("error_cause"),
        "error_detail": (str((res or {}).get("error_detail") or err or ""))[:300],
    }


@app.local_entrypoint()
def main():
    import json
    results = list(run_case.map(CORPUS))
    print("\n" + "=" * 84)
    failures = []
    for r in sorted(results, key=lambda x: x["sub_code"]):
        want_complete = r["expect"] == "complete"
        good = (r["completed"] == want_complete)
        # A 'complete' arm must ALSO prove the fixed code ran.
        if want_complete and r["witness"] and not r["witness_seen"]:
            good = False
            r["error_detail"] = (f"WITNESS MISSING ({r['witness']!r}) — the job completed "
                                 f"without executing the fixed path. " + r["error_detail"])
        tag = "PASS" if good else "FAIL"
        if not good:
            failures.append(r["sub_code"])
        print(f"{tag}  {r['sub_code']:34} expect={r['expect']:11} "
              f"completed={str(r['completed']):5} witness={r['witness_seen']} {r['seconds']:>6.1f}s")
        if r.get("error_cause") or r.get("error_detail"):
            print(f"      {r.get('error_cause') or ''} {r.get('error_detail','')[:160]}")
    print("=" * 84)
    print(f"NOT REPRODUCIBLE (no input causes them): {', '.join(UNREPRODUCIBLE)}")
    print("RESULT " + json.dumps(results, default=str))
    if failures:
        print(f"\nREGRESSION: {failures}")
        raise SystemExit(1)
    print("\nregression corpus GREEN — every fixed class still fixed, on its own input")
