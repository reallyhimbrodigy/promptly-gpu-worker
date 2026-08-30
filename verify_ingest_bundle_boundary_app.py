"""LANE 3 — THE SECOND CHECK: a real job through the REAL boundary.

WHY THIS EXISTS AND WHY THE CERT IS NOT ENOUGH. cert_ingest_bundle_contract
proves the SIGNATURE change is safe — the closures delegate, the payload is
plain data, the validator pages on every silent-empty shape. It proves NOTHING
about what survives the crossing, because a local work_dir works whether or not
the return contract is right. Two checks, two failure classes; this is the
second one.

WHAT IT DOES. The same source, twice:

  BASELINE   cpu=16, /prewarm mounted — the orchestrator's shape. Runs the four
             _ingest_* IN-PROCESS, exactly as the dark path does today.
  BOUNDARY   the deployed cpu=8 `ingest_bundle`, called for real.

Then it diffs all four outputs. These are DETERMINISTIC functions of the source
bytes (scdet at a fixed threshold, astats, a proxy encode with x264 threads
PINNED at _PROXY_X264_THREADS, face detection over that proxy), so the bar here
is EQUALITY — not a similarity band. A difference on a fixed input is a DEFECT.

THE FIXTURE MUST PROVE ITSELF. A run where both sides return nothing is
indistinguishable from "the relocation is perfect" and would ship as a
confident null — the shape that has burned this session repeatedly. So the
baseline must show NON-EMPTY shot_changes and a real proxy before any
comparison is reported. If it does not, that is a FIXTURE FAILURE and is
reported as one.

CONFOUND CONTROLLED: the proxy has three paths (client URL / prewarm cache /
encode) and two sides on different paths would differ for a legitimate reason.
Both functions mount /prewarm and neither is given a proxy_video_url, so both
resolve the same way; `source_from` and the proxy path are reported so a
mismatch cannot be silently attributed to the boundary.

  ./run_modal.sh verify_ingest_bundle_boundary_app.py            # ~$0.06
"""
import hashlib
import os
import sys

import modal

app = modal.App("verify-ingest-bundle-boundary")
IMG = modal.Image.debian_slim().pip_install(["boto3"])
S = [modal.Secret.from_name("promptly-secrets")]
BUCKET = "thisismybucketagainwooo"
SRC_KEY = "ab-sources/talking-head-v1/625dfdc5-73s.mp4"


IMG_FF = (modal.Image.debian_slim()
          .apt_install("ffmpeg")
          .pip_install(["boto3"]))

# A CONSTRUCTED DURABLE SOURCE, per the A/B law — never user media, and never a
# source whose properties we only hope are right. Three real talking-head clips
# concatenated: two HARD CUTS the scene detector must find, and real faces so
# the face-detect arm is exercised instead of comparing [] against [].
# The first attempt used a single 73s talking head and the fixture guard caught
# it: no shot changes, so both arms returned [] and the comparison would have
# read as a perfect relocation.
CONCAT_PARTS = [
    "ab-sources/talking-head-v1/625dfdc5-73s.mp4",
    "ab-sources/talking-head-v1/3b2e5346-35s.mp4",
    "ab-sources/talking-head-v1/0c17b20b-35s.mp4",
]
BUILT_KEY = "ab-sources/lane3-boundary/concat-3clip-2cut.mp4"


@app.function(image=IMG_FF, secrets=S, timeout=1800, cpu=8, memory=8192)
def build_source(parts: list, dest: str) -> dict:
    """Concatenate real clips into one durable source with known hard cuts."""
    import subprocess
    import tempfile

    import boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    wd = tempfile.mkdtemp()
    local = []
    for i, k in enumerate(parts):
        p = os.path.join(wd, f"p{i}.mp4")
        s3.download_file(b, k, p)
        local.append(p)
        print(f"  fetched {k} ({os.path.getsize(p)/1e6:.1f}MB)", flush=True)
    out = os.path.join(wd, "concat.mp4")
    # Normalise to one geometry/fps so concat is legal; the CUTS between clips
    # are what this source exists to provide.
    fc = "".join(
        f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:-1:-1,setsar=1,fps=30[v{i}];" for i in range(len(local)))
    fc += "".join(f"[v{i}][{i}:a]" for i in range(len(local)))
    fc += f"concat=n={len(local)}:v=1:a=1[v][a]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in local:
        cmd += ["-i", p]
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", out]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500)
    if r.returncode != 0 or not os.path.exists(out):
        return {"ok": False, "why": (r.stderr or "")[-500:]}
    s3.upload_file(out, b, dest, ExtraArgs={"ContentType": "video/mp4"})
    return {"ok": True, "bucket": b, "key": dest, "bytes": os.path.getsize(out),
            "parts": len(local)}


@app.function(image=IMG, secrets=S, timeout=300)
def resolve(key: str) -> dict:
    """Confirm the source exists BEFORE any compute is spent on it."""
    import boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    try:
        h = s3.head_object(Bucket=b, Key=key)
    except Exception as e:
        return {"missing": True, "bucket": b, "key": key, "why": str(e)[:120]}
    return {"bucket": b, "key": key, "bytes": h["ContentLength"]}


@app.local_entrypoint()
def main(key: str = BUILT_KEY, rebuild: bool = False):
    src = resolve.remote(key)
    if src.get("missing") or rebuild:
        print(f"  building the durable source ({len(CONCAT_PARTS)} clips -> "
              f"{len(CONCAT_PARTS) - 1} hard cuts)...")
        bres = build_source.remote(CONCAT_PARTS, key)
        if not bres.get("ok"):
            print(f"  ❌ source build failed: {bres.get('why')}")
            sys.exit(2)
        print(f"  built s3://{bres['bucket']}/{bres['key']} "
              f"({bres['bytes'] / 1e6:.1f} MB)")
        src = resolve.remote(key)
    print(f"\n  source: s3://{src['bucket']}/{src['key']}  "
          f"({src['bytes'] / 1e6:.1f} MB)")

    payload = {"job_id": None, "app_url": None,
               "dl_bucket": src["bucket"], "dl_key": src["key"],
               "proxy_video_url": None, "source_duration": 0, "want_proxy": True}

    print("\n  [1/2] BASELINE — the four tasks in-process on a cpu=16 box "
          "(the orchestrator's shape)")
    base = modal.Function.from_name("promptly-gpu-worker", "ingest_baseline_probe")
    base.hydrate()
    b = base.remote(payload)

    print("  [2/2] BOUNDARY — the deployed cpu=8 ingest_bundle, called for real")
    bun = modal.Function.from_name("promptly-gpu-worker", "ingest_bundle")
    bun.hydrate()
    r = bun.remote(payload)

    for name, d in (("baseline", b), ("boundary", r)):
        if d.get("error"):
            print(f"\n  ❌ {name} FAILED: {d['error']}")
            sys.exit(2)

    # ── FIXTURE VALIDITY, before any comparison is reported ────────────────
    print("\n  --- fixture validity (the control must be non-empty) ---")
    bad = []
    if not b.get("shot_changes"):
        bad.append("baseline found NO shot changes — this source cannot "
                   "discriminate; both sides returning [] proves nothing")
    if not b.get("gemini_proxy"):
        bad.append("baseline produced NO proxy — the encode path never ran")
    if not b.get("loudness"):
        bad.append("baseline produced NO loudness")
    if not b.get("faces_dense"):
        bad.append("baseline detected NO faces — comparing [] against [] says "
                   "nothing about whether the face arm survives the crossing")
    if bad:
        print("  ❌ FIXTURE FAILURE — not a result:")
        for x in bad:
            print(f"       {x}")
        sys.exit(2)
    print(f"  ✓ baseline is non-empty: {len(b['shot_changes'])} shot changes, "
          f"{len(b['gemini_proxy'])} proxy bytes, loudness present")
    print(f"    source resolved from: baseline={b.get('source_from')}  "
          f"boundary={r.get('source_from')}")
    if b.get("source_from") != r.get("source_from"):
        print("    ⚠️  DIFFERENT SOURCE PATHS — a proxy mismatch below would be "
              "explained by this, not by the boundary")

    # ── the comparison ─────────────────────────────────────────────────────
    print("\n  --- the four relocated outputs, across the real boundary ---")
    print(f"      {'output':>16} {'equal':>7}   detail")

    def sha(x):
        return hashlib.sha256(bytes(x)).hexdigest()[:16] if x else "—"

    fails = []

    def cmp(label, ba, ra, detail):
        eq = ba == ra
        if not eq:
            fails.append(label)
        print(f"      {label:>16} {'✓' if eq else '✗ DIFFER':>7}   {detail}")

    cmp("loudness", b["loudness"], r["loudness"],
        f"{b['loudness']}" if b["loudness"] == r["loudness"]
        else f"base={b['loudness']}  bound={r['loudness']}")
    cmp("shot_changes", b["shot_changes"], r["shot_changes"],
        f"{len(b['shot_changes'])} cuts {b['shot_changes'][:6]}"
        if b["shot_changes"] == r["shot_changes"]
        else f"base={b['shot_changes'][:8]}  bound={r['shot_changes'][:8]}")
    cmp("shot_scores", b["shot_scores"], r["shot_scores"],
        f"{len(b['shot_scores'])} scored")
    cmp("faces_dense", b["faces_dense"], r["faces_dense"],
        f"{len(b['faces_dense'])} samples")
    cmp("faces_smoothed", b["faces_smoothed"], r["faces_smoothed"],
        f"{len(b['faces_smoothed'])} keyframes")
    _pb, _pr = b["gemini_proxy"], r["gemini_proxy"]
    cmp("gemini_proxy", sha(_pb), sha(_pr),
        f"{len(_pb)} bytes, sha {sha(_pb)}"
        if sha(_pb) == sha(_pr)
        else f"base {len(_pb)}B/{sha(_pb)}  bound {len(_pr)}B/{sha(_pr)}")

    print(f"\n      wall: baseline {b.get('_far_wall_s')}s (cpu=16, in-process) "
          f"vs boundary {r.get('_far_wall_s')}s (cpu=8, relocated)")
    print(f"      per-task baseline: {b.get('pool_task_s')}")
    print(f"      per-task boundary: {r.get('pool_task_s')}")

    if fails:
        print(f"\n  ❌ {len(fails)} output(s) DIFFER across the boundary: "
              f"{', '.join(fails)}")
        print("     On a fixed input these are deterministic. A difference is a "
              "DEFECT, not variance — do NOT arm the bundle.")
        sys.exit(1)
    print("\n  ✅ ALL FOUR OUTPUTS IDENTICAL ACROSS THE REAL BOUNDARY.")
    print("     The return contract survives the crossing. This is the check")
    print("     the in-process cert could not make.")
