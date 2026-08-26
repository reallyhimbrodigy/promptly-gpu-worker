"""FORCED RENDER BATCH — RENDERCLOCK curve x offthread arm. PRICED: ~$1.00-1.20.

WHY FORCED, NOT ORGANIC. 155 makers/day split across two live experiments does
not produce a readable duration curve today, and `preserved=1 in both arms` is a
SAMPLING problem rather than a traffic problem. The per-job overrides
(offthread_test / stall_test) exist so a batch can AIM at an arm instead of
hoping the hash cooperates.

THE READ IS A CURVE, NOT A VERDICT. Fixed overhead does not scale with clip
length, so a 20s leg can read stitch- or frames-dominant for reasons that wash
out by 120s. Three durations, and no single leg decides it.

WHAT THE SPLIT DECIDES (stated before the run, so it cannot be fitted after):
  stitch_ms dominant                  -> NVENC (B.2) is the lever; the GPU
                                         re-run is worth its $0.50, decomposed.
  frames_ms dominant                  -> does NOT reopen B.1 (settled dead:
                                         Vulkan unrecoverable, angle-egl never
                                         verified). ~110s/chunk needs a
                                         different attack.
  browser/select/unaccounted dominant -> not a GPU question at all. A cold
                                         Chromium launch is a WARM-POOL problem.

DURABLE + CONSTRUCTED SOURCES (Rule: A/Bs never use user media). One durable
failure-corpus base, trimmed in-container to the three duration points, so the
only variable across the curve is LENGTH.

  ./run_modal.sh batch_renderclock_app.py --durations 20,60,120 --repeats 2
"""
import json
import os
import sys

import modal

app = modal.App("batch-renderclock")
image = modal.Image.debian_slim().pip_install("boto3")
SECRETS = [modal.Secret.from_name("promptly-secrets")]

# Durable, already in S3, and a real talking-head source the pipeline can edit.
BASE_KEY = "failure-corpus/RENDER_FFMPEG/41403891-1953-4a5b-85a6-e247eb9932bd.mp4"


@app.function(image=image, secrets=SECRETS, timeout=900)
def probe_base() -> dict:
    """Duration of the base source. UNMEASURED is reported, never guessed."""
    import boto3, subprocess, tempfile
    s3 = boto3.client("s3",
                      aws_access_key_id=os.environ.get("SUPABASE_S3_ACCESS_KEY"),
                      aws_secret_access_key=os.environ.get("SUPABASE_S3_SECRET_KEY"),
                      endpoint_url=(os.environ.get("SUPABASE_URL", "").rstrip("/")
                                    + "/storage/v1/s3"),
                      region_name="us-east-1")
    bucket = os.environ.get("SUPABASE_BUCKET") or "videos"
    fd, p = tempfile.mkstemp(suffix=".mp4"); os.close(fd)
    try:
        s3.download_file(bucket, BASE_KEY, p)
    except Exception as e:
        return {"error": f"DOWNLOAD FAILED: {type(e).__name__}: {e}",
                "bucket": bucket, "key": BASE_KEY}
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "default=nw=1:nk=1", p],
                       capture_output=True, text=True)
    try:
        return {"duration_s": float((r.stdout or "").strip()),
                "bytes": os.path.getsize(p), "bucket": bucket, "key": BASE_KEY}
    except ValueError:
        return {"error": "PROBE FAILED — no duration; this is a FAILED "
                         "measurement, not a zero", "stderr": (r.stderr or "")[:300]}


@app.local_entrypoint()
def main(durations: str = "20,60,120", repeats: int = 2, dry: bool = True):
    want = [int(x) for x in durations.split(",") if x.strip()]
    arms = ["2", "control"]
    n = len(want) * len(arms) * repeats
    print(f"  PLAN: {len(want)} durations x {len(arms)} offthread arms x {repeats} "
          f"repeats = {n} renders")
    print(f"  durations: {want}s   arms: {arms}")
    print(f"  base source: s3://.../{BASE_KEY}")
    print(f"  PRICED: ~$0.07-0.10 per std-editorial render -> ~${0.07*n:.2f}-${0.10*n:.2f}")

    b = probe_base.remote()
    print(f"\n  base probe: {json.dumps(b)[:300]}")
    if b.get("error"):
        print("\n  ❌ BASE SOURCE UNUSABLE — not firing. A batch on a source we "
              "could not probe would produce timings nobody can attribute.")
        sys.exit(2)
    if b["duration_s"] < max(want):
        print(f"\n  ⚠ base is {b['duration_s']:.1f}s but the curve asks for "
              f"{max(want)}s. The long point CANNOT be constructed by trimming.")
        print("  Report the curve over the durations that ARE constructible and "
              "say which point is missing — do not silently drop it.")
    if dry:
        print("\n  DRY RUN — nothing rendered.")
        sys.exit(0)

    # ── NOT IMPLEMENTED, AND IT SAYS SO LOUDLY ─────────────────────────────
    # Only the probe/plan/pricing half of this harness exists. The render leg —
    # trim the durable base to each duration, dispatch through the real handler
    # with offthread_test, collect RENDERCLOCK — is NOT written.
    #
    # Without this guard `--dry=False` would print a plan, probe a source,
    # render NOTHING, and exit 0. A batch that reads as fired and did nothing is
    # the false-green class this session has caught nine times, and it would be
    # worse here than elsewhere: the next reader would go looking for results
    # that never existed and conclude the traffic was thin.
    print("\n  ❌ NOT IMPLEMENTED — the render leg of this harness does not exist.")
    print("  Implemented: base probe, plan, pricing. NOT implemented: trim to")
    print("  duration, dispatch with offthread_test, collect RENDERCLOCK.")
    print("  Refusing to exit 0 on a batch that rendered nothing.")
    sys.exit(2)
