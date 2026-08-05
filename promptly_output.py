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
    import os
    import subprocess
    import tempfile
    # DOWNLOAD, DO NOT STREAM (2026-08-04). ffprobe in the worker image is built
    # WITHOUT https protocol support — probing a presigned URL returns
    # "Protocol not found" (rc=1), which the pre-returncode version silently
    # rendered as has_video=False / frames=0 / duration=0. So this probe could
    # NEVER have worked over a URL in-container, and every `well=` verdict it
    # produced from one was unearned. boto3 is already required here to list the
    # prefix; use it to fetch the bytes and probe a local file, which removes
    # the protocol dependency entirely rather than hoping for a better build.
    _tmpd = tempfile.mkdtemp()
    _local = os.path.join(_tmpd, "probe_target.mp4")
    try:
        s3.download_file(bucket, key, _local)
    except Exception as e:                                        # noqa: BLE001
        return {"error": f"download for probe failed: {type(e).__name__}: {e}"[:200]}
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,nb_frames:format=duration,size",
             "-of", "json", _local],
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


# ── THREE-VALUED PROBE CONTRACT ─────────────────────────────────────────────
# MEASURED / ABSENT / FAILED — and FAILED is never expressible as a number.
#
# Every probe collapse this project has suffered is the same shape: a probe
# fails, its empty stdout parses to zero, and a caller reads that zero as a
# measurement. Four instances, one root:
#   1. ffprobe 403 on a private S3 object -> "all zeros" -> seven matrix cells
#      reported broken when they were fine.
#   2. probe_playable ignoring returncode -> a real 4.27s / 128-frame render
#      reported as a 0-frame empty deliverable, which put the whole
#      completion-rate denominator in doubt for an afternoon.
#   3. probe_content_duration ignoring returncode -> a partial read could
#      truncate a REAL timeline to the short value, silent content destruction
#      wearing the costume of a legitimate clamp.
#   4. .endswith('.mp4') picking a 0-byte init.mp4 -> the same "confident wrong
#      number" failure in the resolver rather than the probe.
#
# The fix is not per-site vigilance; it is making the wrong shape unsayable.
# ABSENT means the file genuinely lacks that stream/field (a legitimate input to
# a decision). FAILED means we do not know, and a caller that treats it as a
# number is a bug. Callers MUST branch on .failed before reading .value.

class ProbeResult:
    """MEASURED / ABSENT / FAILED. `.value` raises unless MEASURED."""

    __slots__ = ("state", "_value", "detail")

    def __init__(self, state, value=None, detail=""):
        self.state = state           # "measured" | "absent" | "failed"
        self._value = value
        self.detail = detail

    @property
    def measured(self):
        return self.state == "measured"

    @property
    def absent(self):
        return self.state == "absent"

    @property
    def failed(self):
        return self.state == "failed"

    @property
    def value(self):
        if self.state != "measured":
            raise ValueError(
                f"probe is {self.state.upper()}, not a measurement "
                f"({self.detail}) — branch on .failed/.absent, or call "
                f".or_default(x) to state the fallback EXPLICITLY")
        return self._value

    def or_default(self, default):
        """The ONLY way to get a number out of a non-measurement, and it forces
        the caller to name the fallback at the call site."""
        return self._value if self.state == "measured" else default

    def __repr__(self):
        return f"ProbeResult({self.state}, {self._value!r})"


def probe_field(args, parse=float, timeout=60):
    """Run an ffprobe argv and return a ProbeResult — never a bare number.

    rc != 0            -> FAILED (stderr retained)
    rc == 0, no output -> ABSENT
    rc == 0, unparsable-> FAILED (not zero!)
    """
    import subprocess
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except Exception as e:                                        # noqa: BLE001
        return ProbeResult("failed", None, f"{type(e).__name__}: {e}"[:200])
    if r.returncode != 0:
        return ProbeResult("failed", None,
                           f"rc={r.returncode}: {(r.stderr or '').strip()[-160:]}")
    out = (r.stdout or "").strip()
    if not out:
        return ProbeResult("absent", None, "probe returned no rows")
    try:
        # `-of csv=p=0` emits a trailing comma per row; strip separators
        # before parsing. Note this raised rather than returning 0 the first
        # time it met one — which is the contract behaving correctly.
        _tok = out.splitlines()[0].strip().rstrip(",").strip()
        if not _tok or _tok.upper() == "N/A":
            return ProbeResult("absent", None, "field present but N/A")
        return ProbeResult("measured", parse(_tok))
    except Exception as e:                                        # noqa: BLE001
        return ProbeResult("failed", None,
                           f"unparsable {out[:40]!r}: {type(e).__name__}")
