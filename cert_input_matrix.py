"""PROPERTY-BASED INPUT MATRIX — find tomorrow's classes tonight.

Zac 2026-08-04: "EVERY CLASS FOUND TONIGHT WAS A FIXED ASSUMPTION MEETING AN
UNTESTED INPUT — an iPhone metadata track, a screenplay's keyterms, a '500'
inside 'max 500 tokens'. A SURGE IS WHEN NEW SHAPES ARRIVE."

Tonight's roll-call, every one a constant meeting a shape nobody tried:
  · ffprobe field ORDER            -> the weighted probe budget never scaled
  · 1000000/33333 microsecond fps  -> 44100/30.0003 broke the audio frame grid
  · a Core Media Metadata track    -> ffmpeg auto-selected a codec-less stream
  · 32//chunks against 8 cores     -> Remotion refused the concurrency
  · "max 500 tokens"               -> a deterministic 400 retried three times

ASSERTS RENDERS WELL, NOT MERELY COMPLETES. A completed render proves the
pipeline ran; it does not prove the output is watchable. Round 1 of the earlier
proof harness passed 4/4 while executing neither fix under test. So each cell
also checks the artifact: real duration, real frames, audio present when the
source had it, and NOT a stream-less or stub file.
"""
import os
import sys

sys.path.insert(0, "/")
import modal  # noqa: E402
import modal_app  # noqa: E402

image = (modal_app.image
         .add_local_file("modal_app.py", "/modal_app.py")
         .add_local_file("promptly_output.py", "/promptly_output.py"))
app = modal.App("cert-input-matrix", image=image)

SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-lang-flags"),
]

BUCKET = "thisismybucketagainwooo"
BASE = f"https://{BUCKET}.s3.amazonaws.com/matrix-20260804"

# Each cell isolates ONE property. `why` names the constant it probes.
MATRIX = [
    {"cell": "fps-23.976", "src": "m_2397.mp4",
     "why": "24000/1001 — non-integral fps against the output frame grid"},
    {"cell": "fps-29.97", "src": "m_2997.mp4",
     "why": "30000/1001 NTSC — 44100/29.97 is 1471.47 samples/frame"},
    {"cell": "fps-25-PAL", "src": "m_25.mp4",
     "why": "PAL, 48kHz — a rate the 30/60 assumptions never see"},
    {"cell": "fps-120", "src": "m_120.mp4",
     "why": "4x the frames per second against every per-frame budget"},
    {"cell": "dims-1276x718", "src": "m_odd.mp4",
     "why": "odd non-16:9 dimensions — the shape under the live INTEGRITY_TRIP:black"},
    {"cell": "4K-HEVC", "src": "m_hevc4k.mp4",
     "why": "2160x3840 HEVC — 4x pixels, ~2x decode, against the probe budgets"},
    {"cell": "ProRes-422", "src": "m_prores.mov",
     "why": "intra-frame 10-bit 422 — a codec the h264 assumptions never meet"},
    {"cell": "VFR", "src": "m_vfr.mp4",
     "why": "variable frame rate — r_frame_rate lies about the real cadence"},
]


@app.function(secrets=SECRETS, cpu=16.0, memory=12288, timeout=3000)
def run_cell(cell: dict) -> dict:
    import contextlib
    import io
    import json as _json
    import subprocess
    import time
    import traceback
    import uuid

    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H

    job_id = str(uuid.uuid4())
    key = f"matrix-20260804/out/{cell['cell']}/{job_id}.mp4"
    url = f"https://{BUCKET}.s3.amazonaws.com/{key}"
    body = {
        "job_id": job_id, "video_url": f"{BASE}/{cell['src']}",
        "vibe": "Clean and engaging edit",
        "user_id": "00000000-0000-0000-0000-0000000000ee",
        "upload_url": url, "public_url": url,
        "model": "flare", "supports_progressive": False,
        "premium_pipeline_enabled": False,
    }
    buf = io.StringIO()
    res, err, t0 = None, None, time.time()
    try:
        with contextlib.redirect_stdout(buf):
            res = H.handler({"input": body})
    except Exception as e:                                     # noqa: BLE001
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-400:]}"
    log = buf.getvalue()
    print(f"--- {cell['cell']} ---\n" + log[-2500:], flush=True)

    out = {
        "cell": cell["cell"], "why": cell["why"],
        "completed": bool(res) and not (res or {}).get("error") and not err,
        "seconds": round(time.time() - t0, 1),
        "error_cause": (res or {}).get("error_cause"),
        "error_detail": str((res or {}).get("error_detail") or err or "")[:300],
        "video_url": (res or {}).get("video_url"),
    }

    # RENDERS WELL, not merely completes — via the SHARED resolver. Probing the
    # upload_url directly 403s on a private bucket, and matching ".mp4" picks the
    # 0-byte HLS init.mp4. Both of those reported the pipeline as broken when it
    # was fine; promptly_output exists so neither can be written a third time.
    out["well"] = None
    if out["completed"]:
        try:
            import boto3
            import promptly_output as _po
            _s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
            _picked = _po.pick_playable_output(_s3, BUCKET, f"matrix-20260804/out/{cell['cell']}/")
            if not _picked:
                out["well"] = False
                out["probe_error"] = "no playable output under the prefix"
            else:
                _pr = _po.probe_playable(_s3, BUCKET, _picked["key"])
                if _pr.get("error"):
                    out["well"] = False
                    out["probe_error"] = _pr["error"]
                else:
                    checks = {
                        "has_video": _pr["has_video"],
                        "has_audio": _pr["has_audio"],
                        "duration_ge_2s": _pr["duration"] >= 2.0,
                        "frames_ge_60": _pr["frames"] >= 60,
                        "size_ge_100k": _picked["size"] >= 100000,
                    }
                    out["probe"] = {"duration": round(_pr["duration"], 2),
                                    "frames": _pr["frames"],
                                    "size_mb": round(_picked["size"] / 1048576, 1)}
                    out["checks"] = checks
                    out["well"] = all(checks.values())
        except Exception as e:                                  # noqa: BLE001
            out["well"] = False
            out["probe_error"] = f"{type(e).__name__}: {e}"[:160]
    return out


@app.local_entrypoint()
def main():
    import json
    results = list(run_cell.map(MATRIX))
    print("\n" + "=" * 96)
    bad = []
    for r in sorted(results, key=lambda x: x["cell"]):
        ok = r["completed"] and r.get("well") is True
        if not ok:
            bad.append(r["cell"])
        tag = "PASS" if ok else ("FAIL" if not r["completed"] else "POOR")
        print(f"{tag}  {r['cell']:16} {r['seconds']:>7.1f}s  completed={str(r['completed']):5} "
              f"well={r.get('well')}  {r.get('probe') or ''}")
        print(f"      {r['why']}")
        if not ok:
            print(f"      >>> {r.get('error_cause') or ''} {r.get('error_detail','')[:170]}")
            if r.get("checks"):
                print(f"      >>> failed checks: {[k for k, v in r['checks'].items() if not v]}")
    print("=" * 96)
    print("RESULT " + json.dumps(results, default=str)[:3500])
    if bad:
        print(f"\nCELLS THAT WOULD HAVE BEEN TOMORROW'S CLASSES: {bad}")
        raise SystemExit(1)
    print("\nMATRIX GREEN — every shape renders WELL, not merely completes")
