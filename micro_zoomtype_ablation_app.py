"""TIER 1 — does a SCALE-ONLY zoom cost the same as a COMPOSITE one?

If SnapReframe (pure scale) costs what LetterboxPush/FocusWindow (multi-layer,
blur masks, overlays) cost, then the ~939 ms/frame is the COMPOSITION FRAME
ITSELF — decoding the source and painting 1080x1920 — and per-component
profiling (Tier 2) has nothing to find. If composites cost materially more, the
effect implementations are the lever.

WHY THIS IS ANSWERABLE AT ALL: SIMPLE_ZOOM_TYPES is an EMPTY SET, deliberately.
The FFmpeg crop+lanczos path for scale-only zooms was retired because n7.1
stopped re-evaluating out_w/out_h per frame, so EVERY zoom now paints in
Remotion. That means a scale-only zoom and a composite zoom go through the same
composition and differ only in what the component draws — a clean comparison.

METHOD. One harvested plan, mode=render_only, five arms. Each arm rewrites the
`type` of all five emphasis moments' zoom_effect to ONE value, holding scale,
duration and word_indices FIXED — so the frame set is identical and only the
component changes. Plus a BASELINE arm with the moments removed entirely, which
bounds what a chunk costs with NO zoom at all.

FRAME COUNTS ARE VERIFIED EQUAL across the four zoom arms before any comparison
is reported. The last sweep compared arms that rendered 239/634/272/287 frames
and produced a trend that evaporated under control; that is the mistake this
guard exists to prevent. The baseline is EXPECTED to differ (zero micro frames)
and is reported separately rather than pooled.

  ./run_modal.sh micro_zoomtype_ablation_app.py --no-dry     # ~$0.50, 5 renders
  ./run_modal.sh micro_zoomtype_ablation_app.py --read-only
"""
import copy
import json
import os
import sys
import uuid

import modal

app = modal.App("micro-zoomtype-ablation")
IMG = modal.Image.debian_slim().pip_install(["supabase", "boto3"])
S = [modal.Secret.from_name("promptly-secrets")]
BUCKET = "thisismybucketagainwooo"
SRC_KEY = "ab-sources/talking-head-v1/625dfdc5-73s.mp4"
# scale-only first, then composite. NONE removes the moments entirely.
ARMS = ("SnapReframe", "StepZoom", "LetterboxPush", "FocusWindow", "NONE")


def _arm_plan(base, zoom_type):
    """Rewrite every CUT's _zoom_effect to ONE type, or strip it entirely.

    THE LEVER IS cuts[]._zoom_effect, NOT emphasis_moments. The first version of
    this ablation mutated emphasis_moments and every arm — including the
    zero-moment BASELINE — still rendered the identical 5 segments / 271 frames,
    because emphasis_moments is a PLANNING input and mode=render_only skips
    planning: the resolved zoom already lives on the cut. The fixture check
    caught it; the wall-time differences it produced were host contention, not
    the arm.
    """
    p = copy.deepcopy(base)
    n = 0
    for c in p.get("cuts") or []:
        ze = c.get("_zoom_effect")
        if not isinstance(ze, dict):
            continue
        n += 1
        if zoom_type == "NONE":
            c.pop("_zoom_effect", None)     # no zoom -> categorize_clip -> ffmpeg
        else:
            ze["type"] = zoom_type          # scale/timing/events UNTOUCHED
    p["_ablation_touched"] = n
    return p


@app.function(image=IMG, secrets=S, timeout=600)
def presign_and_insert(rows: list) -> dict:
    import boto3
    from supabase import create_client
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    b = os.environ.get("S3_BUCKET_NAME") or BUCKET
    s3.head_object(Bucket=b, Key=SRC_KEY)
    src = s3.generate_presigned_url("get_object",
                                    Params={"Bucket": b, "Key": SRC_KEY},
                                    ExpiresIn=14400)
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out = {"src": src, "dst": {}, "inserted": 0, "errors": []}
    for r in rows:
        out["dst"][r["arm"]] = s3.generate_presigned_url(
            "put_object", Params={"Bucket": b,
                                  "Key": f"zoom-ablation/{r['job_id']}.mp4",
                                  "ContentType": "video/mp4"}, ExpiresIn=14400)
        try:
            sb.table("video_jobs").insert({
                "id": r["job_id"], "status": "queued", "video_url": SRC_KEY,
                "vibe_input": "viral", "demo": True}).execute()
            out["inserted"] += 1
        except Exception as e:
            out["errors"].append(str(e)[:140])
    return out


@app.function(image=IMG, secrets=S, timeout=900)
def collect(pairs: list) -> list:
    from supabase import create_client
    sb = create_client(os.environ.get("SUPABASE_URL"),
                       os.environ.get("SUPABASE_SERVICE_KEY")
                       or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    out = []
    for p in pairs:
        r = (sb.table("video_jobs").select("status,result")
             .eq("id", p["job_id"]).limit(1).execute())
        d = (r.data or [{}])[0]
        res = d.get("result") if isinstance(d.get("result"), dict) else {}
        stt = res.get("stage_timings") if isinstance(res.get("stage_timings"), dict) else {}
        out.append({"arm": p["arm"], "job": p["job_id"][:8],
                    "status": d.get("status"), "render": stt.get("render"),
                    "total": stt.get("total"), "hls": stt.get("hls"),
                    "err": str(res.get("error_code") or "")})
    return out


@app.local_entrypoint()
def main(dry: bool = True, read_only: bool = False,
         plan_file: str = "/tmp/harvested_plan.json", only: str = ""):
    if read_only:
        pairs = json.load(open("/tmp/zoom_ablation_pairs.json"))
        rows = collect.remote(pairs)
        print("\n=== ZOOM-TYPE ABLATION — identical plan, only the effect changes ===")
        print(f"  {'arm':<14} {'job':<10} {'status':<11} {'render_s':>9} {'total_s':>8}")
        for r in rows:
            print(f"  {r['arm']:<14} {r['job']:<10} {str(r['status']):<11} "
                  f"{str(r['render']):>9} {str(r['total']):>8}"
                  + (f"  {r['err']}" if r["err"] else ""))
        ok = [r for r in rows if r["status"] == "completed"
              and isinstance(r["render"], (int, float))]
        zoom = [r for r in ok if r["arm"] != "NONE"]
        base = next((r for r in ok if r["arm"] == "NONE"), None)
        if len(zoom) < 2:
            print("\n  fewer than 2 zoom arms completed — NOT a comparison.")
            return
        print("\n  --- render stage, zoom arms ---")
        lo = min(r["render"] for r in zoom)
        for r in sorted(zoom, key=lambda z: z["render"]):
            print(f"    {r['arm']:<14} {r['render']:>7.1f}s   "
                  f"{100.0*(r['render']-lo)/max(1e-9, lo):+5.1f}% vs fastest")
        spread = (max(r["render"] for r in zoom) - lo) / max(1e-9, lo)
        print(f"\n    spread across zoom types: {100*spread:.1f}%")
        if base:
            print(f"\n  --- BASELINE (no emphasis moments -> no micro) ---")
            print(f"    NONE           {base['render']:>7.1f}s")
            for r in sorted(zoom, key=lambda z: z["render"]):
                d = r["render"] - base["render"]
                print(f"    {r['arm']:<14} +{d:>6.1f}s of micro on top of baseline")
        print(f"\n  READ: a small spread means the cost is the COMPOSITION FRAME")
        print(f"  (source decode + 1080x1920 paint), not the effect — and Tier 2")
        print(f"  per-component profiling has nothing to find. A large spread")
        print(f"  means the composite implementations are the lever.")
        return

    if not os.path.exists(plan_file):
        print(f"  ❌ no plan at {plan_file}")
        sys.exit(2)
    base = json.load(open(plan_file))
    zc = [c for c in (base.get("cuts") or []) if isinstance(c.get("_zoom_effect"), dict)]
    if not zc:
        print("  ❌ no cut carries _zoom_effect — nothing to ablate")
        sys.exit(2)
    from collections import Counter as _C
    print(f"  base plan: {len(base.get('cuts') or [])} cuts, "
          f"{len(zc)} carrying _zoom_effect "
          f"{dict(_C(c['_zoom_effect'].get('type') for c in zc))}")
    print(f"  arms: {', '.join(ARMS)}")
    # SEQUENTIAL by default. The first run fired all five at once and identical
    # work split into two clusters (1108-1175 vs 1907-2001 ms/frame) — host
    # contention between my own arms. --only fires one, so a caller can space
    # them and compare wall times that mean something.
    _arms = [a for a in ARMS if not only or a == only]
    if only and not _arms:
        print(f"  ❌ unknown arm {only!r}; choose from {ARMS}")
        sys.exit(2)
    pairs = [{"arm": a, "job_id": str(uuid.uuid4())} for a in _arms]
    if dry:
        print(f"  DRY — {len(ARMS)} render_only jobs (~$0.10 each). --no-dry to fire.")
        return
    pi = presign_and_insert.remote(pairs)
    print(f"  pre-inserted {pi['inserted']}/{len(pairs)} {pi['errors'] or ''}")
    if pi["inserted"] != len(pairs):
        print("  ❌ refusing to dispatch — a job with no row reports nowhere")
        sys.exit(2)
    fn = modal.Function.from_name("promptly-gpu-worker", "run_pipeline_bg")
    fn.hydrate()
    for p in pairs:
        plan = _arm_plan(base, p["arm"])
        dst = pi["dst"][p["arm"]]
        cid = fn.spawn({"job_id": p["job_id"], "video_url": pi["src"],
                        "vibe": "viral", "user_id": str(uuid.uuid4()),
                        "upload_url": dst, "public_url": dst,
                        "mode": "render_only", "edit_plan": plan}).object_id
        n = plan.get("_ablation_touched", 0)
        zc = sum(1 for c in (plan.get("cuts") or []) if c.get("_zoom_effect"))
        print(f"  → {p['arm']:<14} {p['job_id'][:8]}  cuts_touched={n} "
              f"zoomed_cuts_remaining={zc}  {cid}")
    _prev = []
    if only and os.path.exists("/tmp/zoom_ablation_pairs.json"):
        try:
            _prev = [x for x in json.load(open("/tmp/zoom_ablation_pairs.json"))
                     if x.get("arm") != only]
        except Exception:
            _prev = []
    json.dump(_prev + pairs, open("/tmp/zoom_ablation_pairs.json", "w"))
    print("\n  read with: ./run_modal.sh micro_zoomtype_ablation_app.py --read-only")
