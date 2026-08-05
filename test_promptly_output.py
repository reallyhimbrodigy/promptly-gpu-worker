"""pick_playable_output — with the positive and negative controls that would
have caught both probe failures before either was reported as a class.

The listing below is the REAL 4K-HEVC matrix output, verbatim: one 33.5 MB
deliverable beside a 0-byte `init.mp4` and six `.m4s` segments. My second probe
picked the 0-byte init.mp4 because it ends in ".mp4" and was written last.
"""
import sys

import promptly_output as P

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


# The exact object set that broke the probe.
REAL = [
    ("matrix-20260804/out/4K-HEVC/0041e2be-hls/master.m3u8", 0),
    ("matrix-20260804/out/4K-HEVC/0041e2be-hls/stream_1080p/init.mp4", 0),
    ("matrix-20260804/out/4K-HEVC/0041e2be-hls/stream_1080p/playlist.m3u8", 0),
    ("matrix-20260804/out/4K-HEVC/0041e2be-hls/stream_1080p/seg_0.m4s", 6_190_000),
    ("matrix-20260804/out/4K-HEVC/0041e2be-hls/stream_1080p/seg_5.m4s", 314_000),
    ("matrix-20260804/out/4K-HEVC/0041e2be.mp4", 35_127_296),
]


class _S3:
    def __init__(self, objs):
        self._objs = objs

    def get_paginator(self, _op):
        objs = self._objs

        class _P:
            @staticmethod
            def paginate(**_kw):
                return [{"Contents": [{"Key": k, "Size": s} for k, s in objs]}]
        return _P()


print("=== POSITIVE CONTROL: it must FIND the real deliverable ===")
got = P.pick_playable_output(_S3(REAL), "b", "matrix-20260804/out/4K-HEVC/")
check("picks the 33.5MB render", got is not None and got["key"].endswith("0041e2be.mp4"),
      f"got {got}")
check("  and its size is the real one", got and got["size"] == 35_127_296, f"got {got}")

print("\n=== NEGATIVE CONTROL: it must REJECT the 0-byte HLS init.mp4 ===")
# This is the exact object the second probe picked. Without this assertion the
# helper could 'work' by returning anything ending in .mp4.
check("init.mp4 is not playable",
      P.is_playable_output("x/job-hls/stream_1080p/init.mp4", 0) is False)
check("init.mp4 rejected even at a large size",
      P.is_playable_output("x/job-hls/stream_1080p/init.mp4", 99_000_000) is False,
      "an HLS artifact is never the deliverable, whatever its size")
check("m4s segments rejected", P.is_playable_output("x/job-hls/s/seg_0.m4s", 6_000_000) is False)
check("m3u8 rejected", P.is_playable_output("x/job-hls/master.m3u8", 0) is False)
check("a stub mp4 rejected", P.is_playable_output("x/job.mp4", 900) is False)
check("the deliverable accepted", P.is_playable_output("x/job.mp4", 35_000_000) is True)

print("\n=== LARGEST, not newest ===")
# HLS segments are written AFTER the deliverable, so 'newest' picks wrong. The
# helper must not depend on order at all — reversing the listing must not change
# the answer.
rev = P.pick_playable_output(_S3(list(reversed(REAL))), "b", "p/")
check("order-independent", rev is not None and rev["key"] == got["key"], f"{rev} vs {got}")

print("\n=== empty / hostile prefixes ===")
check("empty listing -> None", P.pick_playable_output(_S3([]), "b", "p/") is None)
check("HLS-only listing -> None",
      P.pick_playable_output(_S3([(k, s) for k, s in REAL if "-hls/" in k]), "b", "p/") is None,
      "a job with only streaming artifacts has no deliverable — say None, not a segment")
for bad in (None, "", "x/job.MP4x", "x/job.mov"):
    check(f"  rejects {bad!r}", P.is_playable_output(bad, 9_000_000) is False)
check("uppercase .MP4 accepted", P.is_playable_output("x/JOB.MP4", 9_000_000) is True)


print("\n=== A FAILED PROBE MUST NOT READ AS AN EMPTY FILE ===")
# The 2026-08-04 misread: ffprobe exits non-zero, stdout is empty, and the old
# code returned has_video=False/frames=0/duration=0 as a SUCCESS — reporting a
# real 4.27s h264+aac render as a 0-frame empty deliverable.
import subprocess as _sp
_real_run = _sp.run


def _fake_run(cmd, **kw):
    class _R:
        returncode = 1
        stdout = ""
        stderr = "HTTP error 403 Forbidden"
    return _R()


_sp.run = _fake_run
try:
    class _S3P:
        @staticmethod
        def generate_presigned_url(*a, **k):
            return "https://example.invalid/x.mp4"

        @staticmethod
        def download_file(_b, _k, dest):
            # a real download that yields a file ffprobe will reject
            with open(dest, "wb") as fh:
                fh.write(b"not a video")
    _res = P.probe_playable(_S3P, "b", "k")
finally:
    _sp.run = _real_run
check("a non-zero ffprobe is an ERROR, not zeros", "error" in _res, f"got {_res}")
check("  and it names the cause", "rc=" in str(_res.get("error", "")), f"got {_res}")
check("  and it does NOT claim has_video=False",
      _res.get("has_video") is None,
      "reporting has_video=False on a FAILED probe is what caused the misread")
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
