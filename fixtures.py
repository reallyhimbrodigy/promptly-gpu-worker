"""FIXTURES BY NAME. A URL is derived at use time and never written down.

Zac, 2026-09-20, after a run was blocked asking for a paste:

    "a fixture manifest keyed by NAME -> S3 key, signed at stage time, never a
     URL on a command line."

WHY A URL ON A COMMAND LINE IS THE BUG. A presigned URL is three things at once
and all three are wrong to keep: it EXPIRES, so yesterday's is dead; it is not
in the TREE, so nobody can review which clip a round actually ran on; and it is
unrecoverable the next morning, which is how this lane spent a turn asking for
something it could have listed itself. `--clip-url https://...?X-Amz-...` looks
like configuration and is really a credential with a source attached.

A NAME is durable, diffable, and reviewable. `--fixture talking_head` says what
ran in a way a reader six weeks later can check.

THE MANIFEST IS A FIXTURE AND LIVES IN THE TREE (fixtures.json), for the reason
this repo already wrote down: a fixture must drift WITH the tree or fail loudly
at merge. The S3-side manifest.json is a different artifact with a different
job -- it carries the reliability corpus's scoring regimes -- and it is not a
substitute, as this session proved: it was written 2026-09-08 and could not see
the Hindi and multi-clip fixtures staged 2026-09-18, so four staged fixtures
were invisible to every reader of it for two days.

NOTHING HERE MINTS A URL WITHOUT SAYING SO. `sign` returns a state, and the URL
it returns carries its expiry, because a signed URL that has quietly gone stale
fails at the next `curl` as a download error -- which reads as a bad clip rather
than as an expired grant.
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "fixtures.json")
DEFAULT_EXPIRY_S = 3600


def load(path=MANIFEST):
    """-> {state, bucket, fixtures, why}. The manifest, or a named absence."""
    out = {"state": "ABSENT", "bucket": None, "fixtures": {}, "why": "not attempted"}
    if not os.path.exists(path):
        return dict(out, why="no manifest at %s" % path)
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        return dict(out, state="FAILED", why="%s: %s" % (type(e).__name__, str(e)[:160]))
    fx = raw.get("fixtures")
    if not isinstance(fx, dict) or not fx:
        return dict(out, state="FAILED",
                    why="the manifest carries no fixtures map (%s)" % type(fx).__name__)
    return {"state": "MEASURED", "bucket": raw.get("_bucket"), "fixtures": fx,
            "why": "%d fixture(s) from %s" % (len(fx), os.path.basename(path))}


def names(path=MANIFEST):
    """Every fixture name, sorted. For an error message that can be acted on."""
    return sorted((load(path).get("fixtures") or {}))


def sign(name, expires_in=DEFAULT_EXPIRY_S, path=MANIFEST, runner=None):
    """NAME -> a signed URL. -> {state, url, key, expires_in, meta, why}

    REFUSES AN UNKNOWN NAME AND LISTS THE KNOWN ONES. A typo that returned None
    would reach curl as an empty URL and fail as a download error, which is the
    same symptom as an expired grant and a deleted object -- three causes, one
    message, and the run is the debugger.
    """
    out = {"state": "ABSENT", "url": None, "key": None,
           "expires_in": expires_in, "meta": None, "why": "not attempted"}
    man = load(path)
    if man["state"] != "MEASURED":
        return dict(out, state=man["state"], why="manifest %s: %s" % (man["state"], man["why"]))
    fx = man["fixtures"].get(name)
    if not fx:
        return dict(out, state="REFUSED",
                    why="no fixture named %r. Known: %s"
                        % (name, ", ".join(sorted(man["fixtures"]))))
    key = fx.get("s3_key")
    if not key:
        return dict(out, state="FAILED",
                    why="fixture %r carries no s3_key" % name)
    bucket = man.get("bucket")
    if not bucket:
        return dict(out, state="FAILED", why="the manifest names no bucket")
    try:
        r = (runner or subprocess.run)(
            ["aws", "s3", "presign", "s3://%s/%s" % (bucket, key),
             "--expires-in", str(int(expires_in))],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return dict(out, state="FAILED", key=key,
                    why="presign: %s: %s" % (type(e).__name__, str(e)[:160]))
    if getattr(r, "returncode", 1) != 0:
        return dict(out, state="FAILED", key=key,
                    why="aws s3 presign exited %s: %s"
                        % (r.returncode, (r.stderr or "")[-200:]))
    url = (r.stdout or "").strip()
    if not url.startswith("http"):
        return dict(out, state="FAILED", key=key,
                    why="presign returned something that is not a URL: %r" % url[:120])
    return {"state": "MEASURED", "url": url, "key": key, "expires_in": expires_in,
            "meta": {k: fx.get(k) for k in
                     ("duration", "width", "height", "vcodec", "covers", "sha256_16")},
            "why": "s3://%s/%s signed for %ds (%sx%s, %ss)"
                   % (bucket, key, expires_in, fx.get("width"), fx.get("height"),
                      fx.get("duration"))}


def resolve(fixture="", clip_url="", expires_in=DEFAULT_EXPIRY_S, path=MANIFEST):
    """What a launcher calls. -> {state, url, source, why}

    A RAW URL IS STILL ACCEPTED AND IS LABELLED AS SUCH. Refusing it outright
    would break every probe entrypoint in this file on the day the manifest
    landed -- a correct rule arriving as a wave of red gets reverted, not
    investigated. So it works, and the ledger says `source: "raw_url"`, which
    is the number that has to go to zero rather than an argument that has to be
    won.
    """
    if fixture and clip_url:
        return {"state": "REFUSED", "url": None, "source": None,
                "why": "both --fixture %r and --clip-url given; they are two "
                       "answers to one question" % fixture}
    if fixture:
        s = sign(fixture, expires_in=expires_in, path=path)
        return {"state": s["state"], "url": s.get("url"), "source": "fixture:%s" % fixture,
                "key": s.get("key"), "meta": s.get("meta"), "why": s["why"]}
    if clip_url:
        return {"state": "MEASURED", "url": clip_url, "source": "raw_url",
                "why": "a raw URL was passed rather than a fixture name — it is "
                       "not in the tree, so this run is not reproducible from "
                       "the repo alone"}
    return {"state": "REFUSED", "url": None, "source": None,
            "why": "pass --fixture NAME (one of: %s) or --clip-url"
                   % ", ".join(names(path))}
