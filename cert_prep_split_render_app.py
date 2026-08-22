#!/usr/bin/env python3
"""cert_prep_split_render_app.py — ONE FULL RENDER TO NAME THE p95 FIX.

THE FORK, pre-registered (read_prep_split.py carries the same words):
  * prep LARGE -> the dark render seconds are ffmpeg prep (staging +
    pre-extracts). Fix is prep-side.
  * prep SMALL and unaccounted still large -> prep is innocent, the seconds are
    inside the Remotion spawn, and the search moves there NARROWED.
  * render_attempts > 1 -> the wall is a LADDER cost, not a slow render.

Already eliminated on production data: upload/HLS/exports explain 1% of the
dark time; source duration r=0.132, drawn components r=0.224, cut count r=0.064.

THE BUILD-LANE TRAP THIS APP DISARMS, and it is specific to this measurement.
Build-lane apps call H.handler() DIRECTLY and never run modal_app.py's container
setup, so PROMPTLY_RENDER_CORE_BUDGET is unset and falls to a floor of 4 instead
of production's 16 — Remotion concurrency 2 instead of 8. That would inflate the
REMOTION half of the very ratio this cell exists to measure, biasing the answer
AGAINST the prep hypothesis by roughly 4x. So the budget is pinned to 16 here to
match run_pipeline_bg's cpu=16, and the container is sized cpu=16 to make that
pin honest rather than a lie told to an env var.

SOURCE CHOICE IS THE HYPOTHESIS. Prep cost should scale with source RESOLUTION
and zoom count, not output duration — that is why a 24.6s source rendered in
750.7s while a 154.7s source rendered in 207s. This uses the 2160x3840 (4K
portrait) source, which is the stressing case. A 1080p source would under-test
prep and could produce a false "prep is innocent".

~$0.30-0.60: one orchestrator at cpu=16 for the job, plus the cpu=32 burst if
the output clears the 45s floor (in which case this ALSO tests the v564 graft).

    modal run --detach cert_prep_split_render_app.py
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-prep-split-render", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]
SRC = ("https://d1iax8jos987n3.cloudfront.net/sources/"
       "e9b47b30-5edf-4bc6-825a-7d2a8fe1a43d/"
       "1785239363288-A2A4B085-5918-4575-BB13-CC3CD92EF816_L0_001.mp4")


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=3000)
def run() -> dict:
    import time
    import uuid
    import traceback
    from build_lane import mark_build_lane
    mark_build_lane("cert_prep_split_render_app.py")
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    # THE PIN — see the module docstring. Without this the render runs at
    # concurrency 2 and the prep/remotion ratio this cell reports is fiction.
    os.environ["PROMPTLY_RENDER_CORE_BUDGET"] = "16"
    sys.path.insert(0, "/")
    import handler as H

    jid = str(uuid.uuid4())
    url = (f"https://thisismybucketagainwooo.s3.amazonaws.com/"
           f"prep-split/{jid}/out.mp4")
    body = {"job_id": jid, "video_url": SRC,
            "vibe": "High-energy viral edit with punchy zooms and emphasis",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": url, "public_url": url, "model": "flare",
            "supports_progressive": False, "premium_pipeline_enabled": False,
            "mode": "full"}
    t0 = time.time()
    out = {"job_id": jid, "core_budget": os.environ.get("PROMPTLY_RENDER_CORE_BUDGET")}
    try:
        res = H.handler({"input": body})
        out["wall"] = round(time.time() - t0, 1)
        if isinstance(res, dict):
            _r = res.get("output") if isinstance(res.get("output"), dict) else res
            st = (_r or {}).get("stage_timings") or {}
            out["stage_timings"] = {k: v for k, v in st.items()
                                    if not isinstance(v, (dict, list))}
            out["timeline"] = st.get("timeline")
            out["render_attempts"] = st.get("render_attempts")
            out["source_duration_s"] = st.get("source_duration_s")
    except Exception as e:
        out["wall"] = round(time.time() - t0, 1)
        out["err"] = f"{type(e).__name__}: {str(e)[:400]}"
        out["tb"] = traceback.format_exc()[-1200:]
        # The timeline is the POINT of this run — capture it even on failure,
        # because a render that died slowly still says where the seconds went.
        try:
            if H._TL is not None:
                out["timeline"] = H._TL.finalize()
        except Exception:
            pass
    return out


def _find(node, name):
    if not isinstance(node, dict):
        return None
    if node.get("name") == name:
        return node
    for c in node.get("children") or []:
        f = _find(c, name)
        if f:
            return f
    return None


@app.local_entrypoint()
def main():
    print("=== PREP SPLIT — one full render, cpu=16, CORE_BUDGET pinned to 16 ===\n")
    o = run.remote() or {}
    if o.get("err"):
        print("RENDER ERROR:", o["err"])
        print(o.get("tb", ""))
    print(f"job={o.get('job_id','')[:8]}  wall={o.get('wall')}s  "
          f"core_budget={o.get('core_budget')}  "
          f"source={o.get('source_duration_s')}s  "
          f"attempts={o.get('render_attempts')}")
    tl = o.get("timeline")
    if not tl:
        print("\nNO TIMELINE — this run answers nothing. Do not read the wall as "
              "a result.")
        return
    node = _find(tl, "render")
    if not node:
        print("\nNO `render` SPAN in the timeline — the job died before the "
              "render. Unmeasured, not innocent.")
        return
    dur = float(node.get("dur") or 0.0)
    kids = {c["name"]: float(c.get("dur") or 0.0) for c in (node.get("children") or [])}
    print(f"\n  render span {dur:.1f}s")
    for k, v in sorted(kids.items(), key=lambda kv: -kv[1]):
        print(f"    {k:<34}{v:>8.1f}s{v/dur*100 if dur else 0:>7.0f}%")
    unacc = float(node.get("unaccounted") or 0.0)
    print(f"    {'unaccounted':<34}{unacc:>8.1f}s{unacc/dur*100 if dur else 0:>7.0f}%")

    prep = kids.get("render_prep", 0.0)
    frac = (prep / dur * 100) if dur else 0
    print("\n  ── VERDICT ──")
    if (o.get("render_attempts") or 0) > 1:
        print(f"  RETRY: {o['render_attempts']} render attempts — this wall is a "
              f"LADDER cost. Fix the failure, not the renderer.")
    if frac >= 40:
        print(f"  PREP IS THE ANSWER: {frac:.0f}% of the render is prep "
              f"(zoom {kids.get('render_zoom_pre_extract', 0):.1f}s, "
              f"transition {kids.get('render_transition_pre_extract', 0):.1f}s). "
              f"Source-resolution-bound ffmpeg decodes — fix is prep-side.")
    elif unacc > 0.4 * dur:
        print(f"  PREP IS INNOCENT ({frac:.0f}%) and {unacc:.0f}s is STILL dark. "
              f"The seconds are inside the Remotion spawn. Search moves there.")
    else:
        print(f"  ACCOUNTED: prep {frac:.0f}%, unaccounted {unacc/dur*100 if dur else 0:.0f}%. "
              f"Read the largest child — the render now explains itself.")
    print("\n  NOTE: build lane. CORE_BUDGET pinned to 16 so the prep/remotion "
          "RATIO is production-shaped; absolute wall may still differ.")
