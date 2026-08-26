"""RENDER ONE REAL EDIT WITH THE GENERATION-FREE COMPOSITIONS AVAILABLE.

The first Promptly edit that can carry composed cards built on the USER'S OWN
FRAMES. Rendered on cada6a1b — the source where, measured this session, the
planner requested StatCard x2 and Stamp while refusing a full-frame takeover.
That makes it the right test: the family it was already asking for is now
buildable, and this shows whether it picks them up.

NOT A PROOF OF ANYTHING ON ITS OWN. One render is an artifact for eyes, not a
rate. What it CAN show: whether the specs build from the design system, whether
the adapters receive them, whether the ladder degrades instead of killing, and
what it actually looks like.

Reports requested-vs-shipped from the component ledger, any ladder activity with
the user-facing note verbatim, wall clock, and the build SHA.

    modal run render_composition_artifact_app.py
"""
import json
import os
import sys

sys.path.insert(0, "/")
import modal, modal_app                                            # noqa: E402

image = (modal_app.image
         .add_local_file("modal_app.py", "/modal_app.py")
         .add_local_file("scene_corpus_manifest.json", "/scene_corpus_manifest.json"))
app = modal.App("render-composition-artifact", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]

SOURCE_ID = "cada6a1b"


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=3600)
def run(build_sha: str) -> dict:
    import time
    import uuid
    import traceback
    from build_lane import mark_build_lane
    mark_build_lane("render_composition_artifact_app.py")
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H

    man = json.load(open("/scene_corpus_manifest.json"))
    src = next(s for s in man["sources"] if s["id"].startswith(SOURCE_ID))
    jid = str(uuid.uuid4())
    key = f"composition-artifact/{jid}/render.mp4"
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/{key}"
    body = {
        "job_id": jid, "video_url": src["video_url"],
        "vibe": src.get("vibe") or "Make it viral",
        "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
        "upload_url": url, "public_url": url, "model": "flare",
        "supports_progressive": False,
        # premium ON so the design system + brand path are live, which is what
        # the composition specs derive their palette and type scale from.
        "premium_pipeline_enabled": True,
    }
    try:
        H._component_ledger_reset()
    except Exception:
        pass

    import io as _io

    class _Tee:
        def __init__(self, real):
            self.real, self.buf = real, _io.StringIO()

        def write(self, x):
            self.real.write(x)
            try:
                self.buf.write(x)
            except Exception:
                pass
            return len(x)

        def flush(self):
            self.real.flush()

    _tee = _Tee(sys.stdout)
    _orig = sys.stdout
    sys.stdout = _tee
    t0 = time.time()
    try:
        res = H.handler({"input": body}) or {}
        err = None
    except Exception as e:
        res, err = {}, f"{type(e).__name__}: {e}\n{traceback.format_exc()[-900:]}"
    finally:
        sys.stdout = _orig
    log = _tee.buf.getvalue()
    # THE PAYLOAD KEY IS `edit_recipe`, NOT `edit_plan`, AND THE LEDGER RIDES THE
    # PAYLOAD. The first run of this harness read res["edit_plan"] (absent) and
    # the MODULE-GLOBAL ledger (empty by then), and reported `MG types shipped:
    # []` / an empty requested-vs-shipped table for a render that had in fact
    # shipped a StatCard — a false zero of exactly the class that cost this
    # campaign a week on generated_scenes. Read the payload, and cross-check
    # against the render's own `[mg] <Type> src=` lines, which are emitted at
    # the moment a graphic is written into the output spec.
    plan = ((res or {}).get("edit_recipe")
            or (res or {}).get("edit_plan") or {})
    mgs = plan.get("motion_graphics") or []
    import re as _re
    _rendered = _re.findall(r"^\[mg\] ([A-Za-z]+) src=", log, _re.M)
    THREE = {"EvidenceCard", "DeviceMockup", "EmojiCard"}
    return {
        "build_sha": build_sha,
        "result_keys": sorted((res or {}).keys()),
        "mg_types_in_output": _rendered,
        "compositions_in_output": [t for t in _rendered if t in THREE],
        "source": src["id"], "source_url": src["video_url"],
        "trigger": src.get("trigger_verbatim"),
        "wall_s": round(time.time() - t0, 1),
        "error": err,
        "video_url": (res or {}).get("video_url") or (res or {}).get("public_url") or url,
        "s3_key": key,
        # the ledger the PIPELINE emitted, not a module global read after the fact
        "ledger": (res or {}).get("component_ledger") or H._component_ledger_snapshot(),
        "mg_types_shipped": [m.get("type") for m in mgs if isinstance(m, dict)],
        "compositions_shipped": [m.get("type") for m in mgs
                                 if isinstance(m, dict) and m.get("type") in THREE],
        "composition_specs": [{"type": m.get("type"),
                               "spec": (m.get("props") or {}).get("spec")}
                              for m in mgs if isinstance(m, dict)
                              and m.get("type") in THREE],
        "edit_rationale": plan.get("edit_rationale"),
        # the ladder's own lines, verbatim
        "ladder": [ln for ln in log.splitlines()
                   if "clear_region_unfittable" in ln
                   or "clear_region_repositioned" in ln
                   or "component(s) left unplaced" in ln
                   or "[frame-comp]" in ln][:12],
        "log_tail": log[-1800:] if err else None,
    }


@app.local_entrypoint()
def main():
    sha = os.environ.get("BUILD_SHA", "unknown")
    r = run.remote(sha)
    print(f"\n  BUILD {r['build_sha']}   source {r['source']}   wall {r['wall_s']}s")
    print(f"  trigger: {str(r.get('trigger'))[:100]}")
    if r.get("error"):
        print(f"  ERROR: {r['error'][:400]}")
    print(f"\n  MG types IN OUTPUT   : {r.get('mg_types_in_output')}   (from the render's own [mg] lines)")
    print(f"  MG types in plan     : {r.get('mg_types_shipped')}")
    print(f"  COMPOSITIONS in out  : {r.get('compositions_in_output') or 'NONE'}")
    print(f"  payload keys         : {r.get('result_keys')}")
    for cs in (r.get("composition_specs") or []):
        s = cs.get("spec") or {}
        print(f"    {cs['type']}: at={s.get('at_seconds')}s tilt={s.get('tilt_deg')} "
              f"entrance={s.get('entrance')} accent={s.get('accent')}")
    print("\n  REQUESTED vs SHIPPED (component ledger):")
    for k, v in sorted((r.get("ledger") or {}).items()):
        if not k.startswith("motion_graphic:"):
            continue
        print(f"    {k.split(':')[-1]:16} requested={v.get('requested')} "
              f"dropped_by_us={v.get('dropped_by_us')} reasons={v.get('drop_reasons')}")
    print(f"\n  LADDER: {r.get('ladder') or 'no rung fired'}")
    print(f"  edit_rationale: {str(r.get('edit_rationale'))[:220]}")
    print(f"\n  s3://thisismybucketagainwooo/{r.get('s3_key')}")
    with open("/tmp/composition_artifact.json", "w") as fh:
        json.dump(r, fh, indent=1)
    print("  (result -> /tmp/composition_artifact.json)")
