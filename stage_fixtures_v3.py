#!/usr/bin/env python3
"""Stage Zac's REAL reference footage as reliability-fixtures-v3, with provenance.

WHY v3 EXISTS AND v2-GEOMETRY STAYS. Three corpora now, and each answers a
different question:

  v1            flat fields and noise. Cannot show a zoom (20.9-41.5 dB). The
                corpus that made three working zoom components look broken.
  v2-geometry   constructed grey cellular static. Enormous geometry headroom
                (11.6-13.9 dB) and NOT representative of anything a user shoots.
                Kept as a CONTROL: geometry checks have real margins on it.
  v3-real       Zac's footage. The only corpus where the density rubric, caption
                placement, MG choice and editorial judgment mean anything,
                because it is the only one that looks like what users upload.

PROVENANCE IS RECORDED, not remembered. Every fixture carries where it came
from, its measured properties, and — for the ones that cannot score a family —
WHY, so nobody later reads a zero as a result. The v1 corpus had none of this
and it cost two rounds of wrong conclusions.

  python3 stage_fixtures_v3.py --dry     (default: probe + manifest, no upload)
  python3 stage_fixtures_v3.py --upload
"""
import hashlib
import json
import os
import re
import subprocess
import sys

REF_DIR = os.path.expanduser("~/Desktop/Promptly Reports/references")
V3 = "ab-sources/reliability-fixtures-v3"
BUCKET = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"

# Per-25s rates and the regime rule, mirrored from agentic_editor_app so the
# manifest can say what each fixture CANNOT score before a round discovers it.
RATES = {"text": 7.28, "cut": 4.75, "card": 2.35, "sfx": 0.82, "zoom": 0.35}
_FIT, _ZERO = 2.5, 0.5


def regime(rate, dur):
    e = rate * dur / 25.0
    return ("per_run" if e >= _FIT else
            "aggregate" if e >= _ZERO else "out_of_scope"), round(e, 2)


def sh(a):
    return subprocess.run(a, capture_output=True, text=True)


def probe(path):
    r = sh(["ffprobe", "-v", "error",
            "-show_entries", "format=duration,size",
            "-show_entries", "stream=codec_type,codec_name,width,height,channels",
            "-of", "json", path])
    try:
        j = json.loads(r.stdout)
    except Exception:
        return None
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), {})
    f = j.get("format", {})
    return {"duration": round(float(f.get("duration") or 0), 2),
            "size_mb": round(int(f.get("size") or 0) / 1048576, 2),
            "width": v.get("width"), "height": v.get("height"),
            "vcodec": v.get("codec_name"), "acodec": a.get("codec_name"),
            "channels": a.get("channels")}


def zoom_psnr(path, dur):
    """Median 1.10x-zoom psnr, sampled away from the ends."""
    vals = []
    for p in (0.15, 0.40, 0.65, 0.85):
        ss = round(dur * p, 2)
        t = "/tmp/_z"
        os.makedirs(t, exist_ok=True)
        a, b = f"{t}/a.mp4", f"{t}/b.mp4"
        sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(ss),
            "-t", "1", "-i", path, "-vf", "scale=540:960", a])
        sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(ss),
            "-t", "1", "-i", path, "-vf", "scale=594:1056,crop=540:960:27:48", b])
        if not (os.path.exists(a) and os.path.exists(b)):
            continue
        r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", a, "-i", b,
                "-lavfi", "psnr", "-f", "null", "-"])
        m = re.search(r"average:([0-9.]+)", (r.stdout or "") + (r.stderr or ""))
        if m:
            vals.append(float(m.group(1)))
    if not vals:
        return None
    vals.sort()
    return round(vals[len(vals) // 2], 2)


def has_speech(path):
    """Speech-carrying, judged on silence structure rather than loudness alone.

    A loud clip is not a speaking clip: the car fixture peaks at -0.9 dB and
    contains no dialogue at all. Continuous speech shows FEW long silences;
    ambient shows none either, so this reports both numbers and lets the
    manifest say 'unknown' rather than guess. It is recorded, never inferred.
    """
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
            "-af", "silencedetect=noise=-30dB:d=0.4", "-f", "null", "-"])
    out = (r.stdout or "") + (r.stderr or "")
    return {"silence_segments": out.count("silence_start"),
            "mean_db": (lambda m: float(m.group(1)) if m else None)(
                re.search(r"mean_volume:\s*(-?[0-9.]+)", sh(
                    ["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                     "-af", "volumedetect", "-f", "null", "-"]).stderr or ""))}


def scenes(path):
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
            "-vf", "select=gt(scene\\,0.25),metadata=print", "-f", "null", "-"])
    return ((r.stdout or "") + (r.stderr or "")).count("pts_time")


# fixture name -> (source filename, the content class it covers, speech?)
# ROUTE IS RECORDED AS MEASURED, NOT AS ASSUMED. The third clip's audio has ZERO
# silence segments at both -30dB/0.4s and -25dB/0.25s — the identical signature
# to the car clip's pure ambient — so a silence heuristic cannot tell continuous
# overlapping speech from crowd noise. Its route is UNRESOLVED until the
# pipeline's own transcriber sees it, and the manifest says so rather than
# guessing. The car clip is kept: at 10.0s it cannot score sfx or zoom, but its
# 720p upscale is the only source that finds the geometry test's blind spot.
ASSIGN = {
    "talking_head": ("3e002565603e47ca832ed38f8609e58f.mov", "talking_head", True),
    "motion":       ("DF3EFE06-AB65-4862-82BD-5220AE3935F3.mov", "no_speech_motion_UNRESOLVED", None),
    "car_short":    ("F65074CC-AC1B-43BF-8E00-C9B9DB6D77AB.mov", "geometry_edge_case_10s", False),
}


def main():
    upload = "--upload" in sys.argv
    rows = []
    for name, (fn, klass, speech) in ASSIGN.items():
        p = os.path.join(REF_DIR, fn)
        if not os.path.exists(p):
            print(f"  {name:16} MISSING {fn}")
            continue
        meta = probe(p)
        if not meta:
            print(f"  {name:16} UNPROBEABLE")
            continue
        z = zoom_psnr(p, meta["duration"])
        aud = has_speech(p)
        sc = scenes(p)
        regs = {f: regime(r, meta["duration"]) for f, r in RATES.items()}
        blocked = [f for f, (g, _) in regs.items() if g == "out_of_scope"]
        sha = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
        key = f"{V3}/{name}-{sha[:8]}.mp4"
        rows.append({
            "fixture": name, "covers": klass, "source_file": fn,
            "sha256_16": sha, "s3_key": key, "provenance":
                "Zac reference footage, ~/Desktop/Promptly Reports/references/",
            **meta, "zoom_psnr": z, "scene_cuts": sc, "audio": aud,
            "has_speech": speech,
            "regimes": {f: g for f, (g, _) in regs.items()},
            "exact": {f: e for f, (_, e) in regs.items()},
            "cannot_score": blocked,
        })
        print(f"  {name:16} {meta['width']}x{meta['height']} {meta['duration']:>6.2f}s "
              f"{meta['size_mb']:>6.2f}MB  zoom {z}dB  cuts {sc}  "
              f"cannot score: {blocked or 'nothing'}")
    man = "/tmp/fixtures_v3/manifest.json"
    os.makedirs("/tmp/fixtures_v3", exist_ok=True)
    json.dump(rows, open(man, "w"), indent=1)
    print(f"\n  manifest -> {man}")
    if not upload:
        print("  DRY RUN — nothing uploaded. Re-run with --upload to stage to S3.")
        return 0
    import boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    for r in rows:
        src = os.path.join(REF_DIR, r["source_file"])
        s3.upload_file(src, BUCKET, r["s3_key"],
                       ExtraArgs={"ContentType": "video/mp4"})
        print(f"  uploaded {r['s3_key']}")
    s3.put_object(Bucket=BUCKET, Key=f"{V3}/manifest.json",
                  Body=json.dumps(rows, indent=1).encode(),
                  ContentType="application/json")
    print(f"  uploaded {V3}/manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
