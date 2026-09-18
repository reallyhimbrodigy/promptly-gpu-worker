#!/usr/bin/env python3
"""CAN CLAUDE WATCH A REFERENCE THROUGH CHATCUT? Settled by calling, not reading.

Zac, 2026-09-16: "Settle whether Claude can watch a reference through ChatCut.
Not from docs. By doing it."

THE QUESTION IS DENSITY, AND DENSITY IS A PIXEL FACT. `inspect_asset` accepts
25 arbitrary millisecond timestamps per call, so the SCHEMA permits any
spacing. What the schema cannot tell you is whether two timestamps 10ms apart
come back as two different pictures or the same decoded frame twice — and
"the tool accepted it" is exactly the kind of evidence this lane has been
burned by. So every frame is downloaded and HASHED, and the answer is the
count of DISTINCT images, not the count of URLs returned.

Runs on Modal because that is where the ChatCut credential lives. Read-only:
it inspects an asset and downloads JPEGs. It places nothing and exports
nothing.
"""
import hashlib
import json
import os

import modal

app = modal.App("chatcut-watch-probe")
_HERE = os.path.dirname(os.path.abspath(__file__))
IMG = (modal.Image.debian_slim(python_version="3.11")
       .pip_install("requests")
       .add_local_file(os.path.join(_HERE, "chatcut_job_app.py"),
                       "/root/chatcut_job_app.py", copy=True)
       .add_local_file(os.path.join(_HERE, "turn_clock.py"),
                       "/root/turn_clock.py", copy=True))

PROJECT = "74036980-7215-4852-8423-0dca60e2403c"
ASSET = "07ccc1fc-b343-451f-8f6d-2fa46918745c"       # 25.45s, 576x1024


@app.function(image=IMG, timeout=1800,
              secrets=[modal.Secret.from_name("chatcut-oauth")])
def probe(asset: str = ASSET, project: str = PROJECT):
    import sys
    import urllib.request
    sys.path.insert(0, "/root")
    import chatcut_job_app as J

    tok = J._access_token()
    out = {"asset": asset, "spacings": [], "notes": []}

    def frames_at(times):
        """-> [(ms, url)] from one inspect_asset call."""
        r = J.mcp_rpc(tok, "tools/call",
                      {"name": "inspect_asset",
                       "arguments": {"assetId": asset, "projectId": project,
                                     "sourceTimesMs": times,
                                     "includeTimecode": False}}, 900)
        res = (r.get("result") or {})
        urls = []
        for b in (res.get("content") or []):
            if isinstance(b, dict) and b.get("type") == "resource_link":
                u = b.get("uri") or b.get("url")
                if u:
                    urls.append(u)
        return urls, res

    def fetch_hashes(urls):
        """-> (hashes, bytes_each, dims) — the PIXELS, not the URLs."""
        hs, szs, dims = [], [], []
        for u in urls:
            try:
                with urllib.request.urlopen(u, timeout=60) as fh:
                    b = fh.read()
            except Exception as e:                                # noqa: BLE001
                hs.append("FETCH_FAILED:%s" % type(e).__name__)
                szs.append(0)
                continue
            hs.append(hashlib.sha256(b).hexdigest()[:16])
            szs.append(len(b))
            dims.append(_jpeg_dims(b))
        return hs, szs, dims

    def _jpeg_dims(b):
        """(w, h) from the SOF marker — no pillow in this image."""
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            m = b[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3):
                h = (b[i + 5] << 8) | b[i + 6]
                w = (b[i + 7] << 8) | b[i + 8]
                return (w, h)
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            i += 2 + ((b[i + 2] << 8) | b[i + 3])
        return (0, 0)

    # ── THE SPACING LADDER. 1ms is far below any frame interval; 33ms is one
    # frame at 30fps. Where DISTINCT stops tracking REQUESTED is the floor.
    for step in (1, 5, 10, 20, 33, 40, 100):
        times = [8000 + i * step for i in range(8)]
        try:
            urls, res = frames_at(times)
        except Exception as e:                                    # noqa: BLE001
            out["spacings"].append({"step_ms": step, "state": "FAILED",
                                    "why": str(e)[:160]})
            continue
        hs, szs, dims = fetch_hashes(urls)
        out["spacings"].append({
            "step_ms": step, "requested": len(times), "urls": len(urls),
            "distinct_images": len(set(h for h in hs
                                       if not h.startswith("FETCH"))),
            "dims": sorted(set(dims)), "median_kb": (sorted(szs)[len(szs) // 2]
                                                     // 1024) if szs else 0})

    # ── HOW MANY CALLS TO COVER THE WHOLE CLIP AT THE FLOOR ──────────────────
    try:
        r = J.mcp_rpc(tok, "tools/call",
                      {"name": "inspect_asset",
                       "arguments": {"assetId": asset, "projectId": project}},
                      900)
        txt = json.dumps(r)[:4000]
        out["asset_card"] = txt[:1200]
    except Exception as e:                                        # noqa: BLE001
        out["asset_card"] = "FAILED %s" % str(e)[:120]

    # ── DOES ANYTHING RETURN AUDIO? Ask for a transcript range and see what
    # comes back: rows of TEXT, or a media handle.
    try:
        r = J.mcp_rpc(tok, "tools/call",
                      {"name": "inspect_asset",
                       "arguments": {"assetId": asset, "projectId": project,
                                     "transcriptRangesMs": [
                                         {"startMs": 5000, "endMs": 12000}]}},
                      900)
        res = (r.get("result") or {})
        kinds = sorted({b.get("type") for b in (res.get("content") or [])
                        if isinstance(b, dict)})
        blob = json.dumps(res)
        out["transcript_probe"] = {
            "block_types": kinds,
            "has_audio_mime": any(k in blob for k in ("audio/", ".mp3", ".wav",
                                                      ".m4a", "audioUrl")),
            "sample": blob[:700]}
    except Exception as e:                                        # noqa: BLE001
        out["transcript_probe"] = {"state": "FAILED", "why": str(e)[:160]}

    # ── request_asset_download: the one tool that could hand over the FILE ───
    try:
        r = J.mcp_rpc(tok, "tools/call",
                      {"name": "request_asset_download",
                       "arguments": {"assetId": asset, "projectId": project}},
                      900)
        out["request_asset_download"] = json.dumps(r)[:900]
    except Exception as e:                                        # noqa: BLE001
        out["request_asset_download"] = "FAILED %s" % str(e)[:200]

    print(json.dumps(out, indent=1)[:6000], flush=True)
    return out


@app.local_entrypoint()
def main(out: str = "/tmp/watch_probe.json"):
    r = probe.remote()
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=1)
    print("\nwrote %s" % out)
