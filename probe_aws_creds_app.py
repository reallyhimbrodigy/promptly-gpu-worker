"""IS THE WORKER'S AWS KEY ALIVE? Distinguish three states that all look alike.

The sweep's presign got `InvalidAccessKeyId` on ListObjectsV2 and `403 Forbidden`
on HeadObject, mounting only `promptly-secrets`. Three very different causes
produce that pair, and they have three different owners:

  A. WRONG SECRET MOUNTED — AWS_* lives in a secret my function did not mount,
     and boto3 fell through to some other credential source. My harness's bug.
  B. THE KEY IS DEAD — AWS_ACCESS_KEY_ID is present in the deployed secret set
     and AWS no longer recognises it. Then EVERY production path that touches
     AWS S3 (clean export, thumbnails, image upload) is broken too, and this is
     a live incident that outranks the sweep. Zac's to fix — a credential.
  C. THE KEY IS ALIVE, THE OBJECT IS NOT THERE — access is fine and
     batch-corpus/<clip> simply does not exist. Harness data problem, no incident.

Mounts the DEPLOYED APP'S FULL SECRET SET, per the standing rule that a harness
missing a secret measures a different world than production.

`sts get-caller-identity` is the discriminator: it needs no bucket permission at
all, so it separates "who am I" from "may I read this". A 403 on HeadObject
alone cannot — HEAD has no response body, so S3 collapses 404 and 403 into 403.

  ./run_modal.sh probe_aws_creds_app.py      (~$0.005, one CPU container)
"""
import os

import modal

app = modal.App("probe-aws-creds")
image = modal.Image.debian_slim().pip_install("boto3")

# THE DEPLOYED APP'S FULL SECRET SET (modal_app.py:695-725), not a subset.
SECRETS = [modal.Secret.from_name(n) for n in (
    "promptly-secrets", "promptly-cloudfront", "gemini-vertex",
    "promptly-lang-flags", "promptly-elevenlabs")]

BUCKET = "thisismybucketagainwooo"
KEY = "batch-corpus/v24044gl0000d2rj4k7og65tcgn43lr0.mp4"


@app.function(image=image, secrets=SECRETS, timeout=300)
def probe() -> dict:
    import boto3
    out = {}
    _ak = os.environ.get("AWS_ACCESS_KEY_ID") or ""
    out["AWS_ACCESS_KEY_ID_present"] = bool(_ak)
    # Prefix only — enough to tell WHICH key is mounted and whether it rotated,
    # never enough to be a credential in a log.
    out["AWS_ACCESS_KEY_ID_prefix"] = (_ak[:8] + "…") if _ak else None
    out["AWS_SECRET_present"] = bool(os.environ.get("AWS_SECRET_ACCESS_KEY"))
    out["AWS_SESSION_TOKEN_present"] = bool(os.environ.get("AWS_SESSION_TOKEN"))
    out["AWS_REGION"] = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    out["S3_BUCKET_NAME"] = os.environ.get("S3_BUCKET_NAME")

    # (1) WHO AM I — needs no bucket permission.
    try:
        out["sts"] = boto3.client(
            "sts", region_name=out["AWS_REGION"] or "us-west-1"
        ).get_caller_identity().get("Arn")
    except Exception as e:
        out["sts"] = f"FAILED: {type(e).__name__}: {str(e)[:160]}"

    s3 = boto3.client("s3", region_name=out["AWS_REGION"] or "us-west-1")

    # (2) MAY I LIST — separates dead key from missing object.
    try:
        r = s3.list_objects_v2(Bucket=BUCKET, Prefix="batch-corpus/", MaxKeys=20)
        out["list"] = [o["Key"] for o in r.get("Contents", [])]
        out["list_count"] = r.get("KeyCount")
    except Exception as e:
        out["list"] = f"FAILED: {type(e).__name__}: {str(e)[:160]}"

    # (3) IS THE SPECIFIC OBJECT THERE.
    try:
        out["head_bytes"] = s3.head_object(Bucket=BUCKET, Key=KEY)["ContentLength"]
    except Exception as e:
        out["head_bytes"] = f"FAILED: {type(e).__name__}: {str(e)[:160]}"

    # (4) DOES PRODUCTION'S OWN UPLOAD PATH WORK? This is the question that
    # decides whether B is an incident. A tiny put/delete under a scratch key
    # exercises the same client the worker uses for clean exports.
    try:
        s3.put_object(Bucket=BUCKET, Key="_probe/aws_cred_check.txt",
                      Body=b"probe", ContentType="text/plain")
        out["put"] = "OK"
        s3.delete_object(Bucket=BUCKET, Key="_probe/aws_cred_check.txt")
    except Exception as e:
        out["put"] = f"FAILED: {type(e).__name__}: {str(e)[:160]}"
    return out


@app.local_entrypoint()
def main():
    d = probe.remote()
    print("\n=== worker AWS credential state (FULL deployed secret set) ===")
    for k in ("AWS_ACCESS_KEY_ID_present", "AWS_ACCESS_KEY_ID_prefix",
              "AWS_SECRET_present", "AWS_SESSION_TOKEN_present", "AWS_REGION",
              "S3_BUCKET_NAME", "sts", "list_count", "head_bytes", "put"):
        print(f"  {k:>26} : {d.get(k)}")
    _l = d.get("list")
    if isinstance(_l, list):
        print(f"  {'batch-corpus/ keys':>26} : {len(_l)}")
        for k in _l[:12]:
            print(f"  {'':>26}   {k}")
    else:
        print(f"  {'batch-corpus/ list':>26} : {_l}")

    print("\n  VERDICT:")
    _sts_ok = isinstance(d.get("sts"), str) and d["sts"].startswith("arn:")
    if not d.get("AWS_ACCESS_KEY_ID_present"):
        print("    A — no AWS key in the deployed secret set. Harness/config, not creds.")
    elif not _sts_ok:
        print("    B — KEY PRESENT AND REJECTED BY AWS. This is a LIVE CREDENTIAL")
        print("        INCIDENT, not a sweep problem: every production path that")
        print("        uploads to AWS S3 uses this same key. Escalate to Zac.")
        print(f"        sts said: {d.get('sts')}")
    elif isinstance(d.get("head_bytes"), str):
        print("    C — key is ALIVE; the corpus object is missing or unreadable.")
        print("        Harness data problem. Pick a source that exists.")
    else:
        print("    key alive AND object present — the earlier 403 was the "
              "single-secret mount. Harness bug, now fixed.")
