"""Mint the two presigned URLs a job needs. Runs OUTSIDE the container.

The modal CLI ships its own interpreter without boto3, so signing cannot happen
inside `modal run`. It should not anyway: the whole point is that credentials
live with the caller and the container receives two URLs that each permit one
operation on one key.

  python3 presign.py <source-key> [bucket]  ->  TSV: src_url \t out_url \t out_key
"""
import boto3, os, sys, time

src = sys.argv[1]
bucket = sys.argv[2] if len(sys.argv) > 2 else (
    os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage")
s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
out_key = f"agentic-editor/{int(time.time())}-{os.path.basename(src)}"
print("\t".join([
    s3.generate_presigned_url("get_object",
        Params={"Bucket": bucket, "Key": src}, ExpiresIn=3600),
    s3.generate_presigned_url("put_object",
        Params={"Bucket": bucket, "Key": out_key, "ContentType": "video/mp4"},
        ExpiresIn=3600),
    out_key]))
