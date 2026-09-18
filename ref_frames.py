#!/usr/bin/env python3
"""Signed frame URLs for one reference clip, at a chosen rate. Read-only.

WHY IT RETURNS URLS AND NOT BYTES. The ChatCut credential lives in a Modal
Secret, so the inspect_asset call has to happen there; but the frames are tens
of megabytes and a Modal return value is the wrong pipe for that. What comes
back is the signed URL list — small — and the local side fetches. The token
never leaves the container and never reaches a transcript.

THE URLS EXPIRE IN 900s. Fetch promptly or refetch; a stale URL is a 403, not
an empty frame, so a slow consumer fails loudly rather than silently short.
"""
import json
import os

import modal

app = modal.App("chatcut-ref-frames")
_HERE = os.path.dirname(os.path.abspath(__file__))
IMG = (modal.Image.debian_slim(python_version="3.11")
       .add_local_file(os.path.join(_HERE, "chatcut_job_app.py"),
                       "/root/chatcut_job_app.py", copy=True)
       .add_local_file(os.path.join(_HERE, "turn_clock.py"),
                       "/root/turn_clock.py", copy=True))

PROJECT = "74036980-7215-4852-8423-0dca60e2403c"


@app.function(image=IMG, timeout=3600,
              secrets=[modal.Secret.from_name("chatcut-oauth")])
def urls_for(asset: str, duration_s: float, fps: float = 2.0,
             project: str = PROJECT, start_s: float = 0.0,
             end_s: float = 0.0):
    """-> {"times": [...], "urls": [...], "state": ...} for one clip."""
    import sys
    sys.path.insert(0, "/root")
    import chatcut_job_app as J

    tok = J._access_token()
    hi = end_s or duration_s
    # THE LAST FRAME IS AVOIDED. inspect_asset's own note says a coarse
    # overview skips the final 1-5s "for decoder safety"; an exact timestamp
    # past the last decodable frame is an error, not a blank.
    hi = max(0.0, min(hi, duration_s - 0.20))
    step_ms = int(round(1000.0 / fps))
    times = list(range(int(start_s * 1000), int(hi * 1000), step_ms))
    out = {"asset": asset, "fps": fps, "requested": len(times),
           "times": [], "urls": [], "errors": []}
    for i in range(0, len(times), 25):
        batch = times[i:i + 25]
        try:
            r = J.mcp_rpc(tok, "tools/call",
                          {"name": "inspect_asset",
                           "arguments": {"assetId": asset,
                                         "projectId": project,
                                         "sourceTimesMs": batch,
                                         "includeTimecode": False}}, 900)
        except Exception as e:                                    # noqa: BLE001
            out["errors"].append("batch@%dms: %s" % (batch[0], str(e)[:120]))
            continue
        got = []
        for b in ((r.get("result") or {}).get("content") or []):
            if isinstance(b, dict) and b.get("type") == "resource_link":
                u = b.get("uri") or b.get("url")
                if u:
                    got.append(u)
        # A SHORT BATCH IS NAMED. Returning fewer URLs than timestamps and
        # zipping them anyway would silently shift every later frame's label
        # onto the wrong picture — a caption under the wrong shot, which is
        # the one failure this artefact cannot survive.
        if len(got) != len(batch):
            out["errors"].append("batch@%dms asked %d got %d"
                                 % (batch[0], len(batch), len(got)))
        n = min(len(got), len(batch))
        out["times"] += batch[:n]
        out["urls"] += got[:n]
    out["state"] = ("MEASURED %d/%d" % (len(out["urls"]), len(times))
                    if out["urls"] else "ABSENT — no frames came back")
    return out


@app.function(image=IMG, timeout=3600,
              secrets=[modal.Secret.from_name("chatcut-oauth")])
def urls_for_all(assets, fps: float = 2.0, project: str = PROJECT):
    """Every clip in ONE container. Ten cold starts is ten minutes of nothing."""
    out = {}
    for a in assets:
        try:
            out[a["assetId"]] = urls_for.local(a["assetId"], a["duration_s"],
                                               fps, project)
        except Exception as e:                                    # noqa: BLE001
            out[a["assetId"]] = {"state": "FAILED %s" % str(e)[:120],
                                 "urls": [], "times": [], "errors": []}
    return out


@app.local_entrypoint()
def main(asset: str = "", duration_s: float = 0.0, fps: float = 2.0,
         out: str = "/tmp/ref_urls.json", start_s: float = 0.0,
         end_s: float = 0.0, all_clips: bool = False,
         manifest: str = "reference_project.json"):
    if all_clips:
        A = json.load(open(manifest, encoding="utf-8"))["assets"]
        r = urls_for_all.remote(A, fps, PROJECT)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(r, fh)
        for k, v in r.items():
            print("  %s  %s  errors=%s" % (k[:8], v.get("state"),
                                           (v.get("errors") or [])[:1]))
        print("wrote %s" % out)
        return
    if not asset:
        raise SystemExit("pass --asset <assetId> --duration-s <n>")
    r = urls_for.remote(asset, duration_s, fps, PROJECT, start_s, end_s)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(r, fh)
    print("%s  %s  errors=%s" % (asset[:8], r["state"], r["errors"][:2]))
    print("wrote %s" % out)
