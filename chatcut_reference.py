#!/usr/bin/env python3
"""SCRUB THE REFERENCES AT RULING TIME — the planner's half of the frame server.

Zac, 2026-09-15: "Same frame server as the execution half: planner asks
inspect_asset, harness fetches, planner looks."

WHY `inspect_asset` AND NOT `preview_timeline`, read off their schema rather
than inferred: `preview_timeline` returns "actual composed TIMELINE pixels...
up to 9 frames", addressed in TIMELINE time, and ChatCut's own plugin skill
says "Do not create a temporary timeline just to inspect source assets."
`inspect_asset` addresses ORIGINAL SOURCE TIME, returns up to 25 exact frames
per call at native resolution, and carries WORD-LEVEL transcript for the same
range. For looking at a reference video it is not a workaround — it is the
better instrument, and the only one that does not require building a timeline
nobody wants.

THE SHAPE IS THE SAME AS THE EXECUTION HALF and for the same measured reason:
ChatCut hands back SIGNED URLS, not pixels. An agent left to fetch them types
the URL into a curl command — 89% of everything the execution agent typed was
signed S3 URLs, ~275s of generation plus 156s of Bash on one run. So the
harness fetches and the model looks.

THE DIFFERENCE: the planner is not a Claude Code conversation. It is a direct
Anthropic API loop, so there is no stream to intercept — the frames ride the
TOOL RESULT itself, which is cleaner than a follow-up message and keeps the
pictures attached to the question that asked for them.

THE TOKEN RACE IS REAL AND STATED: ChatCut rotates the refresh token on use and
this lane stores one in a Modal Dict. A planner scrubbing references while a
ChatCut execution job runs is two containers sharing one token. Serialise them,
or give the planner its own grant.
"""
import json
import os
import urllib.request

MCP_URL = "https://api.chatcut.io/api/external-mcp/mcp"
TOKEN_URL = "https://api.chatcut.io/auth/mcp/token"
# The reference library, written by the import and read here. A missing file is
# a STATE, never an empty reference list: "no references configured" and "the
# manifest did not ship in the image" are different facts.
_HERE = os.path.dirname(os.path.abspath(__file__))
_MANIFEST = [os.path.join("/craft", "reference_project.json"),
             os.path.join(_HERE, "reference_project.json")]
# Their cap, not ours: `sourceTimesMs` takes at most 25, `transcriptRangesMs`
# at most 6 ranges covering at most 120 seconds.
MAX_FRAMES = 25


def manifest():
    """(dict, state). The reference project and its ten assets."""
    for p in _MANIFEST:
        if os.path.isfile(p):
            try:
                return json.load(open(p, encoding="utf-8")), "MEASURED %s" % p
            except Exception as e:                                # noqa: BLE001
                return None, "FAILED to parse %s: %s" % (p, e)
    return None, ("ABSENT — no reference_project.json under %s. The planner "
                  "cannot scrub what it cannot address." % " or ".join(_MANIFEST))


def access_token(tokens_dict=None):
    """A ChatCut access token, or a named failure. Never a silent None."""
    import urllib.error
    import urllib.parse
    cid = os.environ.get("CHATCUT_CLIENT_ID")
    rt = None
    if tokens_dict is not None:
        try:
            rt = tokens_dict.get("refresh_token")
        except Exception:                                         # noqa: BLE001
            rt = None
    rt = rt or os.environ.get("CHATCUT_REFRESH_TOKEN")
    if not (rt and cid):
        raise RuntimeError(
            "CHATCUT_REFRESH_TOKEN / CHATCUT_CLIENT_ID are ABSENT — the Modal "
            "Secret is not attached to this function. A missing credential, "
            "not an expired one.")
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": rt,
        "client_id": cid, "resource": MCP_URL}).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError("refresh failed HTTP %s: %s"
                           % (e.code, e.read()[:200].decode()))
    if tokens_dict is not None and tok.get("refresh_token") \
            and tok["refresh_token"] != rt:
        # PERSISTED, NOT ANNOUNCED — the same rotation trap the execution half
        # already paid for: a warning about a credential you then discard is
        # absence-as-success wearing a log line.
        try:
            tokens_dict["refresh_token"] = tok["refresh_token"]
        except Exception:                                         # noqa: BLE001
            pass
    if not tok.get("access_token"):
        raise RuntimeError("refresh returned no access_token — ABSENT")
    return tok["access_token"]


def rpc(token, method, params, mid=1):
    """One MCP call over plain HTTP; SSE or JSON, both handled."""
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                         "params": params}).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Authorization": "Bearer %s" % token},
        method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read().decode()
    if raw.lstrip().startswith("{"):
        return json.loads(raw)
    for line in reversed(raw.splitlines()):
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise RuntimeError("unparseable MCP response: %s" % raw[:200])


def frame_urls(result):
    """Signed frame URLs from an inspect_asset result, IN ORDER.

    THE URLS ARRIVE IN THEIR OWN BLOCK TYPE. This lane has already lost a run
    to guessing where an MCP payload lives — the frame URL was in a
    `resource_link` block while three readers looked at `content[].text` and
    `structuredContent`. All three are read here, and the order is the order
    the tool returned, because the caller pairs them with the times it asked
    for.
    """
    out, seen = [], set()
    blocks = ((result or {}).get("result") or {}).get("content") or []
    for b in blocks:
        u = None
        if isinstance(b, dict):
            if b.get("type") == "resource_link":
                u = b.get("uri") or b.get("url")
            elif b.get("type") == "resource":
                u = ((b.get("resource") or {}).get("uri"))
        if u and u.startswith("http") and u not in seen:
            seen.add(u)
            out.append(u)
    if not out:
        # the text blocks carry them inline on some surfaces
        import re
        _t = " ".join(str(b.get("text") or "") for b in blocks
                      if isinstance(b, dict))
        for u in re.findall(r'https://[^\s"\'\\)]+', _t):
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


def structured(result):
    """The JSON half of an inspect_asset result: asset, frames, transcript."""
    r = (result or {}).get("result") or {}
    if isinstance(r.get("structuredContent"), dict):
        return r["structuredContent"]
    for b in (r.get("content") or []):
        if isinstance(b, dict) and b.get("type") == "text":
            t = (b.get("text") or "").strip()
            if t.startswith("{"):
                try:
                    return json.loads(t)
                except Exception:                                 # noqa: BLE001
                    continue
    return {}


def fetch(urls, out_dir, cap=MAX_FRAMES):
    """[(url, path)], state. Bytes on disk, or a named failure per URL."""
    os.makedirs(out_dir, exist_ok=True)
    got, bad = [], []
    for i, u in enumerate(urls[:cap]):
        p = os.path.join(out_dir, "ref%02d.jpg" % i)
        try:
            with urllib.request.urlopen(u, timeout=60) as r:
                b = r.read()
            if not b:
                bad.append("empty body")
                continue
            open(p, "wb").write(b)
            got.append((u, p))
        except Exception as e:                                    # noqa: BLE001
            bad.append("%s: %s" % (type(e).__name__, str(e)[:60]))
    if not got:
        return [], ("SERVED 0 of %d — %s" % (len(urls), bad[:3] or "no urls"))
    return got, ("SERVED %d of %d%s"
                 % (len(got), len(urls),
                    ("; %d failed: %s" % (len(bad), bad[:2])) if bad else ""))


def transcript_lines(struct, limit=60):
    """Word rows as one readable line per range, or a spoken absence."""
    tr = (struct or {}).get("transcript") or {}
    rows = []
    for rng in (tr.get("ranges") or []):
        segs = rng.get("segments") or []
        if not segs:
            continue
        rows.append("  %.2f-%.2fs: %s"
                    % ((rng.get("range") or {}).get("startMs", 0) / 1000.0,
                       (rng.get("range") or {}).get("endMs", 0) / 1000.0,
                       " ".join(str(s.get("text") or "") for s in segs[:limit])))
        rows.append("    word timings: %s"
                    % ", ".join("%s@%.2f" % (s.get("text"),
                                             s.get("startMs", 0) / 1000.0)
                                for s in segs[:12]))
    if not rows:
        return ("  (no transcript rows for that range — the range may be "
                "silent, or outside the clip)")
    return "\n".join(rows)
