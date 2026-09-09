#!/usr/bin/env python3
"""Presign a GET for one S3 key. Read-only; used to fetch a round's own output."""
import sys, os, boto3
from botocore.config import Config
key = sys.argv[1] if len(sys.argv) > 1 else ""
if not key:
    sys.exit(2)
b = os.environ.get("PROMPTLY_BUCKET", "promptly-video-storage")
try:
    s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
    print(s3.generate_presigned_url("get_object",
                                    Params={"Bucket": b, "Key": key},
                                    ExpiresIn=3600))
except Exception as e:
    print("", end="")
    sys.exit(1)
