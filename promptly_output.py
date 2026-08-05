"""ONE way to resolve a job's playable output. Import this; never re-match .mp4.

WHY THIS EXISTS. The same bug was written twice in one night, both times in a
verification probe, and both times it reported the pipeline as broken when the
pipeline was fine:

  1. `ffprobe` on a private S3 URL 403'd and returned zeros. Seven matrix cells
     read as "POOR" and were one step from being reported as seven new classes.
  2. Selecting the newest key ending in ".mp4" picked
     `<job>-hls/stream_1080p/init.mp4` — a 0-BYTE HLS INIT SEGMENT sitting
     beside the real 13-44 MB render. All seven cells read 0.0MB / 0.00s again.

A render pipeline emits several objects per job: the deliverable mp4, an HLS
master playlist, per-variant playlists, `init.mp4`, and `seg_N.m4s`. Exactly one
of them is the thing a user watches. Every probe that guesses gets it wrong
eventually, and a wrong probe is worse than no probe — it manufactures failures.

USE `pick_playable_output` TO CHOOSE, AND `presign` TO READ. Private buckets are
the norm here, so a plain https URL will 403.
"""

# Anything under an `-hls/` (or `/hls/`) prefix is a streaming artifact, never
# the deliverable — including `init.mp4`, which ends in .mp4 and is 0 bytes.
_HLS_MARKERS = ("-hls/", "/hls/")

# A real render is megabytes. This only has to exclude stubs and headers-only
# containers; the caller does the real quality assertions.
MIN_PLAYABLE_BYTES = 100_000


def is_playable_output(key, size=None):
    """True when `key` looks like the deliverable render, not an HLS artifact."""
    k = str(key or "")
    if not k.lower().endswith(".mp4"):
        return False
    if any(m in k for m in _HLS_MARKERS):
        return False                     # init.mp4 / segment dirs live here
    if size is not None and int(size) < MIN_PLAYABLE_BYTES:
        return False                     # a stub is not playable
    return True


def pick_playable_output(s3, bucket, prefix, min_bytes=MIN_PLAYABLE_BYTES):
    """The single largest playable mp4 under `prefix`, or None.

    Largest rather than newest: HLS segments are written AFTER the deliverable,
    so "newest" reliably picks the wrong object — which is exactly how this went
    wrong the second time.

    Returns {"key", "size"} or None. Never raises on an empty prefix.
    """
    best = None
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            key, size = obj.get("Key"), int(obj.get("Size") or 0)
            if not is_playable_output(key, size) or size < min_bytes:
                continue
            if best is None or size > best["size"]:
                best = {"key": key, "size": size}
    return best


def presign(s3, bucket, key, expires=900):
    """A readable URL for a PRIVATE object. A plain https URL 403s."""
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)


def probe_playable(s3, bucket, key, ffprobe_timeout=240):
    """ffprobe the object and return what a viewer would actually get.

    Returns {"duration", "frames", "has_video", "has_audio", "size"} — or
    {"error": ...}. Callers assert on these; this function never decides.
    """
    import json
    import subprocess
    url = presign(s3, bucket, key)
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,nb_frames:format=duration,size",
             "-of", "json", url],
            capture_output=True, text=True, timeout=ffprobe_timeout)
        # A FAILED PROBE IS AN ERROR, NEVER A CONFIDENT ZERO. Without this,
        # ffprobe exiting non-zero (a 403 on a private object, a dead presign,
        # a network blip) leaves stdout empty, json.loads("{}") yields no
        # streams, and this returned has_video=False / frames=0 / duration=0 as
        # a SUCCESSFUL result. The caller then reports a healthy render as an
        # empty deliverable. That misread cost a full re-examination of the
        # completion-rate denominator on 2026-08-04, and it is the same class as
        # the session's first probe failure (403 -> all zeros).
        if r.returncode != 0:
            return {"error": f"ffprobe rc={r.returncode}: "
                             f"{(r.stderr or '').strip()[-200:]}"}
        j = json.loads(r.stdout or "{}")
        if not (j.get("streams") or []):
            return {"error": "ffprobe returned no streams — treat as UNKNOWN, "
                             "not as an empty file"}
    except Exception as e:                                        # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    streams = j.get("streams") or []
    vid = [s for s in streams if s.get("codec_type") == "video"]
    aud = [s for s in streams if s.get("codec_type") == "audio"]
    fmt = j.get("format") or {}
    try:
        frames = int(float((vid[0].get("nb_frames") or 0))) if vid else 0
    except Exception:                                             # noqa: BLE001
        frames = 0
    return {
        "duration": float(fmt.get("duration") or 0),
        "frames": frames,
        "has_video": bool(vid),
        "has_audio": bool(aud),
        "size": int(fmt.get("size") or 0),
    }
