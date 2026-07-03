"""SSRF hardening (a248d42) — prod URL shapes must pass, hostile shapes must not.

R0 of the γ riders: the three production URL shapes are a PERMANENT regression
suite so future hardening can't silently break ingest. Uses real DNS for the
prod hosts (end-to-end host validation) and a stubbed requests.get for the
redirect-hop logic.
"""
import contextlib
import io
import sys

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

import os
from urllib.parse import urlparse

PROD_SHAPES = {
    "cloudfront_public": ("https://d1iax8jos987n3.cloudfront.net/sources/"
                           "ec702499-ca10-49e6-8850-df8f99840904/1783026897878-clip.mp4"),
    "pexels_video_files": ("https://videos.pexels.com/video-files/854982/854982-hd_1080_1920_25fps.mp4"),
    # the app's own S3 bucket shape (upload_url / public_url family)
    "aws_s3_virtualhost": ("https://thisismybucketagainwooo.s3.amazonaws.com/"
                            "rerun-tests/x/output.mp4"),
}
# Supabase presigned shape: the project host lives in SUPABASE_URL (Modal env;
# no wildcard DNS on *.supabase.co, so a fictional ref can't stand in). When
# the env is present (Modal / validate-on-worker) this becomes a live case;
# locally it's covered by the Modal-side probe run at R0.
_sb_host = urlparse(os.environ.get("SUPABASE_URL") or "").hostname
if _sb_host:
    PROD_SHAPES["supabase_presigned"] = (
        f"https://{_sb_host}/storage/v1/object/sign/sources/u/123-clip.mp4?token=abc")

class FakeResp:
    def __init__(self, status=200, location=None, content=b"ok"):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self.content = content

print("=== S1: every prod URL shape passes end to end (real DNS) ===")
saved_get = H.requests.get
seen = []
H.requests.get = lambda url, **kw: seen.append(url) or FakeResp()
try:
    for name, url in PROD_SHAPES.items():
        try:
            resp = H.safe_media_get(url, timeout=5)
            check(f"{name} passes", resp.status_code == 200)
        except Exception as e:
            check(f"{name} passes", False, f"{type(e).__name__}: {e}")
finally:
    H.requests.get = saved_get

print("\n=== S2: redirect hops re-validated ===")
def redirector(target):
    calls = []
    def fake_get(url, **kw):
        calls.append(url)
        if len(calls) == 1:
            return FakeResp(302, location=target)
        return FakeResp()
    return fake_get, calls
fake, calls = redirector("https://videos.pexels.com/video-files/1/1.mp4")
H.requests.get = fake
try:
    resp = H.safe_media_get(PROD_SHAPES["cloudfront_public"], timeout=5)
    check("public->public redirect followed", resp.status_code == 200 and len(calls) == 2)
finally:
    H.requests.get = saved_get
for target in ("https://169.254.169.254/latest/meta-data/",
               "https://localhost/x", "http://videos.pexels.com/x",
               "https://10.0.0.5/x"):
    fake, calls = redirector(target)
    H.requests.get = fake
    try:
        err = None
        try:
            H.safe_media_get(PROD_SHAPES["cloudfront_public"], timeout=5)
        except Exception as e:
            err = e
        check(f"redirect to {target[:32]}… rejected", isinstance(err, ValueError), repr(err))
    finally:
        H.requests.get = saved_get

print("\n=== S3: hostile direct shapes rejected ===")
for bad in ("http://videos.pexels.com/x.mp4",          # scheme
            "https://169.254.169.254/latest/meta-data/",
            "https://127.0.0.1/x.mp4",
            "https://192.168.1.10/x.mp4",
            "https://foo.internal/x.mp4",
            "https://localhost/x.mp4"):
    err = None
    try:
        H.requests.get = lambda url, **kw: FakeResp()
        H.safe_media_get(bad, timeout=5)
    except Exception as e:
        err = e
    finally:
        H.requests.get = saved_get
    check(f"{bad[:40]} rejected", isinstance(err, ValueError), repr(err))

print("\n=== S4: wiring — proxy fetch uses safe_media_get and fails OPEN ===")
src = open("handler.py").read()
check("call site wired", "safe_media_get(proxy_video_url" in src)
_cs = src.find("safe_media_get(proxy_video_url")
check("call site fail-open (falls through to prewarm/on-server encode)",
      "except Exception as _client_proxy_err" in src[_cs:_cs + 900])

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL SSRF-REGRESSION CASES PASS")
