"""LOCATE THE DURABLE CORPUS + SELECT STALL CLIPS BY MEASUREMENT ($0.01, no render).

TWO JOBS, ONE CONTAINER:

1. WHICH BUCKET HOLDS `failure-corpus/`? batch_renderclock_app.py assumed the
   Supabase bucket "videos" and got a 404 — wrong client AND wrong bucket.
   handler._capture_failure_corpus WRITES the prefix to the AWS bucket
   S3_BUCKET_NAME (default promptly-video-storage) via the AWS client, while
   cert_input_matrix reads a different bucket entirely. Rather than pick between
   two plausible answers, LIST BOTH and report which actually contains objects.
   A guessed bucket that happens to work is indistinguishable from one that is
   right, until the day it isn't.

2. STALL-CLIP SELECTION BY SILENCE GAPS. `preserved=1 in both arms` is a
   SAMPLING problem: a random clip mostly has no pause in the 250-700ms band at
   all, so both arms measure nothing. This ranks corpus sources by how many gaps
   fall in that band, so the forced batch uses clips that CAN exercise the gate.

   HONEST LIMIT, stated because it bounds the claim: ffmpeg finds SILENCE, not
   SENTENCE POSITION. Whether a gap is mid-sentence needs a transcript, and this
   runs no ASR. A high band-count is ENRICHMENT — it makes a mid-sentence pause
   much likelier — not a guarantee. Selecting on it is still strictly better
   than selecting at random, which is what produced preserved=1.
"""
import json
import os
import sys

import modal

app = modal.App("probe-corpus")
image = modal.Image.debian_slim().apt_install("ffmpeg").pip_install("boto3")
SECRETS = [modal.Secret.from_name("promptly-secrets")]

CANDIDATE_BUCKETS = ["promptly-video-storage", "thisismybucketagainwooo"]
PREFIX = "failure-corpus/"
BAND_LO, BAND_HI = 0.25, 0.70          # the arms' window, exactly


@app.function(image=image, secrets=SECRETS, timeout=900)
def probe(max_objects: int = 12) -> dict:
    import boto3, subprocess, tempfile, re
    out = {"buckets": {}, "chosen_bucket": None, "clips": []}
    env_bucket = os.environ.get("S3_BUCKET_NAME")
    buckets = ([env_bucket] if env_bucket else []) + [
        b for b in CANDIDATE_BUCKETS if b != env_bucket]
    out["env_S3_BUCKET_NAME"] = env_bucket

    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    keys = []
    for b in buckets:
        try:
            r = s3.list_objects_v2(Bucket=b, Prefix=PREFIX, MaxKeys=max_objects)
            n = r.get("KeyCount", 0)
            out["buckets"][b] = {"objects_under_prefix": n}
            if n and not out["chosen_bucket"]:
                out["chosen_bucket"] = b
                keys = [(o["Key"], o["Size"]) for o in r.get("Contents", [])]
        except Exception as e:
            # A permissions error and an empty bucket are DIFFERENT facts.
            out["buckets"][b] = {"error": f"{type(e).__name__}: {str(e)[:110]}"}

    if not out["chosen_bucket"]:
        out["error"] = ("NO CANDIDATE BUCKET CONTAINS THE PREFIX — this is a "
                        "FAILED LOCATION, not an empty corpus")
        return out

    for key, size in keys:
        fd, p = tempfile.mkstemp(suffix=".mp4"); os.close(fd)
        rec = {"key": key, "bytes": size}
        try:
            s3.download_file(out["chosen_bucket"], key, p)
            d = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "default=nw=1:nk=1", p],
                               capture_output=True, text=True, timeout=120)
            rec["duration_s"] = round(float((d.stdout or "0").strip() or 0), 2)
            # Gaps: silencedetect at a bar below the band so nothing in-band is
            # missed by the detector itself.
            sd = subprocess.run(
                ["ffmpeg", "-i", p, "-af", "silencedetect=noise=-30dB:d=0.20",
                 "-f", "null", "-"], capture_output=True, text=True, timeout=300)
            durs = [float(m) for m in re.findall(r"silence_duration: ([0-9.]+)",
                                                 (sd.stdout or "") + (sd.stderr or ""))]
            rec["gaps_total"] = len(durs)
            rec["gaps_in_band"] = sum(1 for x in durs if BAND_LO <= x <= BAND_HI)
            rec["gaps_over_band"] = sum(1 for x in durs if x > BAND_HI)
        except Exception as e:
            # UNMEASURED, never a zero that reads as "this clip has no pauses".
            rec["error"] = f"{type(e).__name__}: {str(e)[:110]}"
        finally:
            try:
                os.unlink(p)
            except OSError:
                pass
        out["clips"].append(rec)
    return out


@app.local_entrypoint()
def main(max_objects: int = 12):
    r = probe.remote(max_objects=max_objects)
    print(json.dumps(r, indent=1)[:3000])
    print(f"\n  env S3_BUCKET_NAME = {r.get('env_S3_BUCKET_NAME')!r}")
    for b, v in (r.get("buckets") or {}).items():
        print(f"  {b:<28} {v}")
    if r.get("error"):
        print(f"\n  ❌ {r['error']}")
        sys.exit(2)
    print(f"\n  CHOSEN BUCKET: {r['chosen_bucket']}")
    ok = [c for c in r["clips"] if not c.get("error") and c.get("duration_s")]
    if not ok:
        print("  NO CLIP MEASURED — failed reads, not an empty corpus.")
        sys.exit(2)
    print(f"\n  {'dur_s':>7} {'band':>5} {'over':>5} {'all':>5}  key")
    for c in sorted(ok, key=lambda c: -(c.get("gaps_in_band") or 0)):
        print(f"  {c['duration_s']:>7} {c.get('gaps_in_band', 0):>5} "
              f"{c.get('gaps_over_band', 0):>5} {c.get('gaps_total', 0):>5}  "
              f"{c['key'].split('/')[-1][:34]}")
    best = max(ok, key=lambda c: c.get("gaps_in_band") or 0)
    print(f"\n  STALL-CLIP PICK: {best['key']}")
    print(f"  {best.get('gaps_in_band', 0)} gaps in the {BAND_LO}-{BAND_HI}s band "
          f"({best['duration_s']}s source)")
    if not best.get("gaps_in_band"):
        print("  ⚠ ZERO in-band gaps anywhere in the corpus. Forcing these clips "
              "through both arms would reproduce preserved=1 — the arms would "
              "again measure nothing. Say so rather than firing.")
