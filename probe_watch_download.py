#!/usr/bin/env python3
"""Does the download URL actually hand over the FILE — with its audio?

`request_asset_download` returns
  https://api.chatcut.io/api/assets/<id>/download?projectId=<pid>
described as "an authenticated ChatCut download URL". Authenticated by WHAT is
the question, and "the schema says so" is not an answer this lane accepts. This
fetches it with the same bearer the MCP calls use, writes the bytes, and runs
ffprobe over them: if a real audio stream comes back, then the richest view of
a reference through ChatCut is the WHOLE CLIP, not a sequence of stills.
"""
import json
import os

import modal

app = modal.App("chatcut-download-probe")
_HERE = os.path.dirname(os.path.abspath(__file__))
IMG = (modal.Image.debian_slim(python_version="3.11")
       .apt_install("ffmpeg")
       .add_local_file(os.path.join(_HERE, "chatcut_job_app.py"),
                       "/root/chatcut_job_app.py", copy=True)
       .add_local_file(os.path.join(_HERE, "turn_clock.py"),
                       "/root/turn_clock.py", copy=True))

PROJECT = "74036980-7215-4852-8423-0dca60e2403c"
ASSET = "07ccc1fc-b343-451f-8f6d-2fa46918745c"


@app.function(image=IMG, timeout=900,
              secrets=[modal.Secret.from_name("chatcut-oauth")])
def probe(asset: str = ASSET, project: str = PROJECT):
    import subprocess
    import sys
    import urllib.error
    import urllib.request
    sys.path.insert(0, "/root")
    import chatcut_job_app as J

    tok = J._access_token()
    out = {}

    r = J.mcp_rpc(tok, "tools/call",
                  {"name": "request_asset_download",
                   "arguments": {"assetId": asset, "projectId": project,
                                 "variant": "source"}}, 300)
    txt = ""
    for b in ((r.get("result") or {}).get("content") or []):
        if isinstance(b, dict) and b.get("text"):
            txt += b["text"]
    try:
        card = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    except Exception:                                             # noqa: BLE001
        card = {}
    url = card.get("downloadUrl")
    out["downloadUrl"] = url
    out["sizeKb_claimed"] = card.get("sizeKb")
    if not url:
        out["state"] = "ABSENT — no downloadUrl in the card"
        print(json.dumps(out, indent=1), flush=True)
        return out

    # ── WITH the bearer, and WITHOUT, because which one works is the finding ──
    for label, hdrs in (("with_bearer", {"Authorization": "Bearer %s" % tok}),
                        ("no_auth", {})):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=300) as fh:
                data = fh.read()
                ct = fh.headers.get("Content-Type")
            out[label] = {"state": "OK", "bytes": len(data),
                          "content_type": ct}
            if label == "with_bearer":
                open("/tmp/ref.mp4", "wb").write(data)
        except urllib.error.HTTPError as e:
            out[label] = {"state": "HTTP %s" % e.code,
                          "body": e.read()[:160].decode("utf-8", "replace")}
        except Exception as e:                                    # noqa: BLE001
            out[label] = {"state": "FAILED %s" % type(e).__name__,
                          "why": str(e)[:160]}

    # ── IS THERE AUDIO IN IT? ffprobe the bytes, not the metadata. ───────────
    if os.path.exists("/tmp/ref.mp4") and os.path.getsize("/tmp/ref.mp4") > 0:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,width,height,r_frame_rate,"
             "sample_rate,channels", "-show_entries", "format=duration,size",
             "-of", "json", "/tmp/ref.mp4"],
            capture_output=True, text=True, timeout=120)
        try:
            out["ffprobe"] = json.loads(p.stdout)
        except Exception:                                         # noqa: BLE001
            out["ffprobe"] = {"state": "FAILED", "err": p.stderr[:200]}
        # and prove the audio is REAL, not a silent track
        v = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", "/tmp/ref.mp4", "-t", "10",
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=180)
        out["volumedetect"] = [l for l in (v.stderr or "").splitlines()
                               if "volume" in l][:4]
    print(json.dumps(out, indent=1)[:3000], flush=True)
    return out


@app.local_entrypoint()
def main(out: str = "/tmp/dl_probe.json"):
    r = probe.remote()
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=1)
    print("\nwrote %s" % out)
