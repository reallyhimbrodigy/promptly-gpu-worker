#!/usr/bin/env python3
"""Do the stuck jobs' renders EXIST in S3? The load-bearing question for the repair.

CONTEXT. 9 users / 32 (28%) in the clean cohort (jobs created >= 2026-08-11
18:29Z) were terminalised `failed` with "trouble reaching the render service"
while their row read progress=100 / current_step='complete'. The classifier
shipped at 23:12Z named the write-loss root 9 minutes later:

    cause=update_error  err_code=23514  (Postgres CHECK constraint)
    "refusing status=completed with no deliverable URL in columns or result"

So the completion patch tried to flip status='completed' carrying NO deliverable
URL, and the constraint — correctly — refused. The row stayed non-terminal and
the ~900s fallback timer later called it failed.

[MEASURED] 0 of 10 of those rows carry ANY deliverable (rendered_video_url,
result.video_url, hls_manifest_url, clean_export_key). The probe is non-vacuous:
the same read shows 18/18 completed jobs in the same window WITH assets.

THEREFORE "progress=100 + current_step=complete" is the worker's CLAIM, not
evidence of a deliverable, and the honest question is: did a render actually get
produced? S3 is the arbiter, not the DB (recover-hls-orphans.js's stated law).

  renders EXIST  -> the row lost its URL. Repair-to-completed rescues these
                    users, and the fallback timer must consult S3 before failing.
  renders ABSENT -> nothing was produced. The row is telling the truth and the
                    root is upstream in the worker; repairing to 'completed'
                    would hand users a job with no video, which is worse.

Read-only: ListObjectsV2 only, no writes anywhere. One debian_slim CPU
container, ~15s => well under $0.01. No render, no Gemini.

  modal run probe_stuck_renders_s3.py
"""
import json
import os

import modal

app = modal.App("probe-stuck-renders-s3")
image = modal.Image.debian_slim().pip_install("boto3")
SECRETS = [modal.Secret.from_name("promptly-secrets")]

# The clean cohort's half-landed failures (progress=100 + step=complete + failed)
# plus 202ae70d, the live one whose classifier event named the constraint.
JOB_IDS = [
    "19dd793b", "ef093b1f", "e00d38c6", "a01acfa1", "0cc59825",
    "4f37eb44", "38f09b33", "2bb98d6f", "3b2b3040", "202ae70d",
]


@app.function(image=image, secrets=SECRETS, timeout=300)
def probe(full_ids: list) -> dict:
    import boto3

    bucket = (os.environ.get("SUPABASE_S3_BUCKET") or os.environ.get("S3_BUCKET_NAME")
              or os.environ.get("S3_BUCKET") or "")
    s3 = boto3.client("s3")
    out = {"bucket": bucket, "jobs": {}}

    # NON-VACUITY: a listing probe that can see nothing returns a confident
    # "absent" for everything. Prove the bucket is readable first.
    try:
        probe_list = s3.list_objects_v2(Bucket=bucket, Prefix="renders/", MaxKeys=5)
        out["bucket_readable"] = True
        out["renders_prefix_sample"] = [o["Key"] for o in probe_list.get("Contents", [])][:5]
    except Exception as e:  # noqa: BLE001
        out["bucket_readable"] = False
        out["error"] = f"{type(e).__name__}: {e}"
        return out

    for jid in full_ids:
        try:
            r = s3.list_objects_v2(Bucket=bucket, Prefix=f"renders/{jid}/", MaxKeys=100)
            objs = [{"key": o["Key"], "size": o["Size"]} for o in r.get("Contents", [])]
            # pickPlayableOutput's law, mirrored: .mp4, not under an hls prefix,
            # >= 100000 bytes; prefer -edited.mp4; then LARGEST (never newest —
            # HLS artifacts are written after the deliverable).
            playable = [o for o in objs
                        if o["key"].lower().endswith(".mp4")
                        and "-hls/" not in o["key"] and "/hls/" not in o["key"]
                        and o["size"] >= 100000]
            edited = [o for o in playable if o["key"].lower().endswith("-edited.mp4")]
            pool = edited or playable
            best = max(pool, key=lambda o: o["size"]) if pool else None
            out["jobs"][jid[:8]] = {
                "n_objects": len(objs), "n_playable": len(playable),
                "deliverable": best,
                "sample_keys": [o["key"].split("/")[-1] for o in objs][:6],
            }
        except Exception as e:  # noqa: BLE001
            out["jobs"][jid[:8]] = {"error": f"{type(e).__name__}: {e}"}
    return out


@app.local_entrypoint()
def main():
    import urllib.request

    env = {}
    for line in open("/Users/zaclibman/content-studio/.env.local"):
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    url = env["SUPABASE_URL"].rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY")
    req = urllib.request.Request(
        f"{url}/rest/v1/video_jobs?select=id&created_at=gte.2026-08-11T18:29:00Z&limit=200",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    allids = [r["id"] for r in json.loads(urllib.request.urlopen(req, timeout=45).read())]
    full = [i for i in allids if i[:8] in JOB_IDS]

    res = probe.remote(full)
    print(f"bucket={res.get('bucket')!r} readable={res.get('bucket_readable')}")
    if not res.get("bucket_readable"):
        print("PROBE COLLAPSED — cannot read the bucket; this is UNKNOWN, not 'absent'.")
        print(res.get("error"))
        return
    print(f"non-vacuity: renders/ sample = {res.get('renders_prefix_sample')}\n")
    found = 0
    for jid, d in sorted(res["jobs"].items()):
        if d.get("deliverable"):
            found += 1
            mb = d["deliverable"]["size"] / 1e6
            print(f"  {jid}  RENDER EXISTS  {mb:6.2f} MB  {d['deliverable']['key'].split('/')[-1]}")
        else:
            print(f"  {jid}  no deliverable   objects={d.get('n_objects')}  {d.get('sample_keys')}")
    n = len(res["jobs"])
    print(f"\n  {found}/{n} stuck jobs HAVE a playable render in S3")
    print("  EXIST  => the row lost its URL; repair-to-completed rescues these users.")
    print("  ABSENT => nothing was produced; failing is honest and the root is upstream.")
