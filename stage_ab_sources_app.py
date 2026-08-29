"""STAGE the verified talking-head sources into an immutable A/B prefix.

WHY NOT READ failure-corpus/ DIRECTLY. That prefix is a CAPTURE TARGET — every
future terminal failure writes into it, and its lifecycle is owned by the
capture path (handler.py:39819), not by any experiment. An A/B whose inputs can
be appended to, rotated, or purged underneath it is an A/B whose arms are not
comparable across runs. Test fixtures must be immutable; capture targets must
not be.

CONTENT-ADDRESSED NAMES. Each staged key carries the source's own sha256 prefix,
so:
  • the same bytes always land on the same key (re-staging is idempotent)
  • a key names its content, so a silently-swapped fixture is impossible
  • duplicates across error classes collapse instead of inflating n

VERIFIED AFTER COPY, NOT ASSUMED. The destination is re-downloaded and hashed,
and the hash must equal the source's. A copy that "succeeded" per the API and
landed different bytes is exactly the class this repo keeps re-learning.

  ./run_modal.sh stage_ab_sources_app.py
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("stage-ab-sources", image=image)
SECRETS = [modal.Secret.from_name(n) for n in (
    "promptly-secrets", "promptly-cloudfront", "gemini-vertex",
    "promptly-lang-flags", "promptly-elevenlabs")]

DEST_PREFIX = "ab-sources/talking-head-v1"

# VERIFIED 2026-08-29 by probe_fc_talkinghead_app.py: face in 100% of sampled
# frames, 0.0-0.7 hard cuts/25s (vs batch-corpus 7.6-25.4), real speech levels.
# The two CLIP_TOO_SHORT candidates that passed duration/cuts/audio are
# DELIBERATELY ABSENT — both returned face in 0 of 30-40 samples.
SOURCES = [
    ("failure-corpus/INTEGRITY_TRIP/181f10ee-c684-4774-a3ad-d311a8cadf16.mp4",
     "625dfdc5", 73.3),
    ("failure-corpus/EDITOR_GENERIC/8549cf8c-3a4c-4756-ae3a-2ac5a0e264de.mp4",
     "3b2e5346", 34.9),
    ("failure-corpus/INTEGRITY_TRIP/1af68666-779b-4d00-bb26-cb54bd727dba.mp4",
     "0c17b20b", 34.9),
]


@app.function(secrets=SECRETS, cpu=4.0, memory=8192, timeout=1800)
def stage(items: list) -> list:
    import hashlib
    import boto3
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    out = []
    for src_key, want_sha8, dur in items:
        rec = {"src": src_key, "want_sha8": want_sha8, "dur": dur}
        dest = f"{DEST_PREFIX}/{want_sha8}-{int(round(dur))}s.mp4"
        rec["dest"] = dest
        try:
            # IDEMPOTENT: if the key already holds the right bytes, do nothing.
            already = False
            try:
                s3.head_object(Bucket=bucket, Key=dest)
                already = True
            except Exception:
                pass
            if not already:
                s3.copy_object(Bucket=bucket, Key=dest,
                               CopySource={"Bucket": bucket, "Key": src_key})
            rec["pre_existing"] = already

            # VERIFY THE DESTINATION'S ACTUAL BYTES.
            loc = "/tmp/verify_" + want_sha8 + ".mp4"
            s3.download_file(bucket, dest, loc)
            with open(loc, "rb") as fh:
                got = hashlib.sha256(fh.read()).hexdigest()[:8]
            os.remove(loc)
            rec["got_sha8"] = got
            rec["verified"] = (got == want_sha8)
            rec["bucket"] = bucket
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        out.append(rec)
    return out


@app.local_entrypoint()
def main():
    rows = stage.remote(SOURCES)
    print(f"\n=== STAGED -> s3://<bucket>/{DEST_PREFIX}/ ===")
    ok = 0
    for r in rows:
        if r.get("error"):
            print(f"  ✗ {r['src'].split('/')[-1][:20]}  ERROR {r['error']}")
            continue
        mark = "✓" if r.get("verified") else "✗"
        if r.get("verified"):
            ok += 1
        print(f"  {mark} {r['dest']}   sha want={r['want_sha8']} got={r['got_sha8']}"
              f"{'  (already present)' if r.get('pre_existing') else ''}")
    print(f"\n  {ok}/{len(rows)} staged AND byte-verified.")
    if ok != len(rows):
        print("  A copy that did not verify is NOT a fixture — do not run an A/B on it.")
        return
    print(f"\n  Immutable by convention: keys are content-addressed, so re-staging")
    print(f"  the same bytes is a no-op and different bytes cannot take these keys.")
    print(f"  failure-corpus/ stays a capture target; these are the test fixtures.")
