#!/usr/bin/env python3
"""Stage a round's logs to S3, alongside the fixtures, keyed by round.

WHY THIS EXISTS. /tmp was wiped between rounds 25 and 26 and took rounds 6-25
with it — every per-fixture log, every score.json, every appmap. The streak
audit that reset the count from 3 to 0 was derived from those logs, and it can
no longer be re-derived by anyone, including the person who ran it. The
conclusions survive only because they were written into commit messages and
memory. A record of how a pipeline was proven cannot live in a directory the
operating system is entitled to delete.

VERIFIED AFTER WRITING, NOT ASSUMED. A put that silently no-ops leaves exactly
the same impression as a successful one — the archive looks fine until the day
someone needs it, which is the same shape as every absence-rendered-as-success
failure in this lane. Every object is HEADed back and its size compared.

  python3 archive_round.py <round-number> [bucket]
"""
import boto3, hashlib, json, os, sys

ROUND = str(sys.argv[1]) if len(sys.argv) > 1 else ""
BUCKET = sys.argv[2] if len(sys.argv) > 2 else "promptly-video-storage"
SRC = f"/tmp/fixtures/round{ROUND}"

# THE ARCHIVE PREFIX FOLLOWS THE CORPUS THE ROUND ACTUALLY RAN.
#
# This was hardcoded to reliability-fixtures-v1, which was harmless only while
# every round happened to run v1 — the very fact nobody could see, because no
# round printed its corpus. Filing a v3 round under v1 would put the provenance
# error back one layer up from where it was just fixed, and the archive is the
# ONLY copy: /tmp was wiped between rounds 25 and 26 and took rounds 6-25 with
# it. Derived from the round's own plan.tsv, the same source the collector uses.
def _corpus_of(src_dir):
    plan = os.path.join(src_dir, "plan.tsv")
    if not os.path.exists(plan):
        return None
    keys = [l.split("\t")[1] for l in open(plan, encoding="utf-8")
            if len(l.split("\t")) > 1]
    corpora = {"/".join(k.split("/")[:-1]) for k in keys}
    return corpora.pop() if len(corpora) == 1 else None


_CORPUS = _corpus_of(SRC)
if _CORPUS is None:
    # NOT a fallback to v1. A round whose corpus cannot be established must not
    # be filed under a guess — that is how the record starts lying.
    print(f"[archive] round {ROUND}: cannot establish the corpus from plan.tsv "
          f"— refusing to file it under a guess", flush=True)
    sys.exit(1)
PREFIX = f"{_CORPUS}/rounds/round{ROUND}/"

if not ROUND or not os.path.isdir(SRC):
    print(f"[archive] nothing at {SRC} — nothing to stage", flush=True)
    sys.exit(0)

s3 = boto3.client("s3")
files = sorted(f for f in os.listdir(SRC) if os.path.isfile(os.path.join(SRC, f)))
if not files:
    print(f"[archive] {SRC} is EMPTY — a round that produced no logs is itself "
          f"a finding, not a clean archive", flush=True)
    sys.exit(1)

manifest, failed = [], []
for name in files:
    p = os.path.join(SRC, name)
    size = os.path.getsize(p)
    with open(p, "rb") as fh:
        body = fh.read()
    digest = hashlib.sha256(body).hexdigest()
    key = PREFIX + name
    try:
        s3.put_object(Bucket=BUCKET, Key=key, Body=body,
                      ContentType="text/plain; charset=utf-8")
        # VERIFY. Never trust the put.
        head = s3.head_object(Bucket=BUCKET, Key=key)
        if head["ContentLength"] != size:
            failed.append(f"{name}: wrote {size}B, read back {head['ContentLength']}B")
        else:
            manifest.append({"file": name, "bytes": size, "sha256": digest})
    except Exception as e:
        failed.append(f"{name}: {type(e).__name__}: {str(e)[:120]}")

if manifest:
    body = json.dumps({"round": ROUND, "bucket": BUCKET, "prefix": PREFIX,
                       "files": manifest}, indent=1).encode()
    s3.put_object(Bucket=BUCKET, Key=PREFIX + "MANIFEST.json", Body=body,
                  ContentType="application/json")

total = sum(m["bytes"] for m in manifest)
print(f"[archive] round {ROUND}: {len(manifest)}/{len(files)} file(s), "
      f"{total/1024:.0f} KB -> s3://{BUCKET}/{PREFIX}", flush=True)
if failed:
    # LOUD. An archive that half-worked is worse than none, because it reads as
    # done.
    print(f"[archive] FAILED on {len(failed)} file(s):", flush=True)
    for f in failed:
        print(f"[archive]   - {f}", flush=True)
    sys.exit(1)
