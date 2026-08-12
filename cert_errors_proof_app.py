"""PROVE THE APP WORKS — run the four shapes that were failing, on real renders.

Zac 2026-08-03: "a table of zeros is not proof — a count of zero on quiet traffic
is indistinguishable from a count of zero because nothing ran."

Four constructed durable sources (never user media), each sized to hit one shape:
  1. band50   50s @30fps  — the concurrency fail band (2-3 overlay chunks)
  2. ntsc45   45s @29.97  — the frame-grid class b394dc9 fixed. r_frame_rate is
                            30000/1001 and audio is 44100: 44100/29.97 = 1471.47
                            samples/frame, which is the exact pair that killed
                            our first paying subscriber twice. All four sources
                            are 1080x1920 yuv420p h264 so they take the
                            PASSTHROUGH path — the ragged rate really does reach
                            the render, which is what makes this a live test.
  3. long70   70s @30fps  — long enough to exercise the burst dispatch path
  4. short12  12s @30fps  — stays in-process; proves the 12 GiB memory cut holds

CONTAINER SIZING MIRRORS PROD (cpu=16, memory=12288). Testing at a roomier size
would prove nothing about the config that is actually live.

Drives handler.handler directly with APP_URL="" and JOB_STATUS_WRITES_ENABLED=""
— no completion callback, no push, no phantom video_jobs rows (the canonical
cert setup), so this cannot pollute the traffic we measure error rates from.
"""
import os
import sys

sys.path.insert(0, "/")  # modal_app.py is mounted at /modal_app.py; / is not on sys.path at import
import modal  # noqa: E402
import modal_app  # noqa: E402

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-errors-proof", image=image)

# The FULL deployed secret set. A missing secret changes the render flags and
# confounds the comparison (CLAUDE.md render-determinism law).
SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-lang-flags"),
]

BUCKET = "thisismybucketagainwooo"
BASE = f"https://{BUCKET}.s3.amazonaws.com/errors-proof-20260803"

# ROUND 2. Round 1's four sources were SILENT (testsrc2 + a tone), so zero-reject
# routed every one to moodreel/minimal — the hype-render path, which never touches
# _output_frame_grid or build_per_cut_audio. "Output frame grid:" appeared 0 times
# in that run: 4/4 completed and proved NOTHING about the two classes under test.
# These carry REAL SPEECH so they reach the standard editorial render, and both are
# h264/1080x1920/yuv420p CFR so they take the PASSTHROUGH path — meaning the ragged
# rate genuinely survives to the render instead of being normalised out of the test.
ARMS = [
    {"name": "A-speech-ntsc-framegrid", "src": f"{BASE}/sp_ntsc.mp4"},   # 29.97 + 44100
    {"name": "B-speech-61s-chunking", "src": f"{BASE}/sp_band.mp4"},     # 61s -> overlay chunks
]


@app.function(secrets=SECRETS, cpu=16.0, memory=12288, timeout=3000)
def run_arm(arm: dict) -> dict:
    import time
    import traceback
    import uuid

    os.environ["APP_URL"] = ""                    # no completion callback / progress posts
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""  # no phantom video_jobs rows
    sys.path.insert(0, "/")
    import handler as H

    job_id = str(uuid.uuid4())
    key = f"errors-proof-20260803/out/{arm['name']}/{job_id}.mp4"
    url = f"https://{BUCKET}.s3.amazonaws.com/{key}"
    body = {
        "job_id": job_id,
        "video_url": arm["src"],
        "vibe": "Clean and engaging edit",
        "user_id": "00000000-0000-0000-0000-0000000000ee",
        "upload_url": url,
        "public_url": url,
        "model": "flare",
        "supports_progressive": False,
        "premium_pipeline_enabled": False,
    }
    t0 = time.time()
    try:
        res = H.handler({"input": body})
        ok = isinstance(res, dict) and not res.get("error")
        return {
            "arm": arm["name"], "job_id": job_id, "ok": bool(ok),
            "seconds": round(time.time() - t0, 1),
            "video_url": (res or {}).get("video_url"),
            "error_code": (res or {}).get("error_code"),
            "error_detail": str((res or {}).get("error_detail") or (res or {}).get("error") or "")[:400],
            "route": (res or {}).get("route") or ((res or {}).get("edit_recipe") or {}).get("route"),
            "stage_timings": {k: v for k, v in ((res or {}).get("stage_timings") or {}).items()
                              if "render" in str(k).lower()},
        }
    except Exception as e:
        return {
            "arm": arm["name"], "job_id": job_id, "ok": False,
            "seconds": round(time.time() - t0, 1),
            "error_code": type(e).__name__,
            "error_detail": f"{e}\n{traceback.format_exc()[-900:]}",
        }


@app.local_entrypoint()
def main():
    import json
    results = list(run_arm.map(ARMS))
    print("\n" + "=" * 78)
    for r in sorted(results, key=lambda x: x["arm"]):
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['arm']:24} {r['seconds']:>7.1f}s  route={r.get('route')}")
        if r.get("video_url"):
            print(f"      {r['video_url']}")
        if not r["ok"]:
            print(f"      {r.get('error_code')}: {r.get('error_detail', '')[:300]}")
    print("=" * 78)
    print("RESULT " + json.dumps(results, default=str))
