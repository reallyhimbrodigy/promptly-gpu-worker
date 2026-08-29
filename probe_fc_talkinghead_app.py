"""VERIFY the failure-corpus candidates are TALKING HEADS — the leg that was vacuous.

probe_failure_corpus_app.py called `detect_face_positions(path)` with one
argument. The real signature is `detect_face_positions(video_path,
sample_timestamps)`, so every call raised TypeError, was swallowed by a
fail-open except, and reported `face=None` on all 40 rows. A `hasattr` guard
made the absence read as "optional", so the survey shipped a talking-head
verdict with the talking-head check switched off — the exact false-green class
(a check that cannot fire is not a check).

This runs it correctly, on the shortlist only, and reports the FRACTION of
sampled timestamps with a detected face. A source with a face in <50% of samples
is not a talking head and must not become an A/B input.

  ./run_modal.sh probe_fc_talkinghead_app.py
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("probe-fc-talkinghead", image=image)
SECRETS = [modal.Secret.from_name(n) for n in (
    "promptly-secrets", "promptly-cloudfront", "gemini-vertex",
    "promptly-lang-flags", "promptly-elevenlabs")]

CANDIDATES = [
    "failure-corpus/INTEGRITY_TRIP/181f10ee-c684-4774-a3ad-d311a8cadf16.mp4",
    "failure-corpus/CLIP_TOO_SHORT/6e027d37-580f-48ba-b082-ca421ec57584.mp4",
    "failure-corpus/EDITOR_GENERIC/8549cf8c-3a4c-4756-ae3a-2ac5a0e264de.mp4",
    "failure-corpus/INTEGRITY_TRIP/1af68666-779b-4d00-bb26-cb54bd727dba.mp4",
    "failure-corpus/CLIP_TOO_SHORT/675effbb-aa7c-4d6e-9545-7c7767449b5c.mp4",
]


@app.function(secrets=SECRETS, cpu=8.0, memory=16384, timeout=1800)
def check(keys: list) -> list:
    import hashlib
    import json
    import subprocess
    import boto3
    sys.path.insert(0, "/")
    import handler as H

    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    out = []
    for k in keys:
        loc = "/tmp/" + k.replace("/", "_")
        rec = {"key": k}
        try:
            s3.download_file(bucket, k, loc)
            # SHA so duplicates across error classes are visible as duplicates
            # rather than counted as independent sources.
            with open(loc, "rb") as fh:
                rec["sha8"] = hashlib.sha256(fh.read()).hexdigest()[:8]
            _p = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "json", loc], capture_output=True, text=True, timeout=120)
            dur = float(json.loads(_p.stdout or "{}").get("format", {}).get("duration") or 0)
            rec["dur"] = round(dur, 1)
            # Sample ~1 face probe/second, capped — enough to separate a talking
            # head from b-roll without a dense pass.
            n = max(6, min(40, int(dur)))
            ts = [dur * (i + 0.5) / n for i in range(n)]
            det = H.detect_face_positions(loc, ts)
            if isinstance(det, tuple):
                det = det[0]
            if isinstance(det, list) and det:
                found = sum(1 for f in det if isinstance(f, dict) and f.get("found"))
                rec["face_frac"] = round(found / len(det), 2)
                rec["samples"] = len(det)
            else:
                rec["face_frac"] = None
                rec["note"] = f"detector returned {type(det).__name__}"
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:140]}"
        finally:
            try:
                os.remove(loc)
            except Exception:
                pass
        out.append(rec)
    return out


@app.local_entrypoint()
def main():
    rows = check.remote(CANDIDATES)
    print(f"\n=== TALKING-HEAD VERIFICATION (the leg that was switched off) ===")
    print(f"  {'dur':>6} {'face_frac':>10} {'n':>4} {'sha8':>9}  key")
    for r in rows:
        if r.get("error"):
            print(f"  {'—':>6} {'ERROR':>10} {'—':>4} {'—':>9}  {r['key']}  {r['error']}")
            continue
        print(f"  {r.get('dur', 0):>6.1f} {str(r.get('face_frac')):>10} "
              f"{str(r.get('samples')):>4} {r.get('sha8', '—'):>9}  {r['key']}")
    ok = [r for r in rows if (r.get("face_frac") or 0) >= 0.5]
    shas = {r.get("sha8") for r in ok if r.get("sha8")}
    print(f"\n  TALKING HEADS (face in >=50% of samples): {len(ok)} file(s), "
          f"{len(shas)} DISTINCT source(s) by sha256")
    for r in ok:
        print(f"      {r['dur']:.0f}s  face={r['face_frac']}  sha={r['sha8']}  {r['key']}")
    if not ok:
        print("      NONE. The shortlist survived duration and cut-density but is")
        print("      not talking-head footage — asking Zac is the correct step.")
