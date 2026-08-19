"""IS THE SCENES ZERO A JUDGMENT OR AN ABSENCE? — two cells, with the control.

`generated_scenes` has fired on 0 of 779 planned jobs. The 2026-08-18 prompt-v2
A/B appeared to confirm it — zero in BOTH arms — and that reading was WRONG: the
directive is appended only `if premium and _scenes_directive_v2()`, and every
cell of that A/B ran `premium_pipeline_enabled: False`. Both arms were
structurally incapable of emitting a scene. The zero measured a switched-off
feature, which is the same class as the four corpora that scored correct
declines as defects.

So this is the FIRST time the question is asked on a path where the feature
exists.

    arm  premium=True, PROMPTLY_SCENES_DIRECTIVE_V2=1, PLAN_ONLY
    ctl  premium=True, PROMPTLY_SCENES_DIRECTIVE_V2=0, PLAN_ONLY
    same source, serial

THE CONTROL IS WHAT MAKES IT READABLE. A non-zero ON-cell alone cannot tell
"the v2 rewrite works" from "premium alone was the gate and the rewrite is
incidental" — and those imply completely different next moves.

PRE-REGISTERED READINGS (fixed before the numbers exist):

    ON non-zero, OFF zero   the v2 directive works; the old one was the blocker
    both non-zero           premium alone was the gate; the rewrite is
                            incidental, and the earn-gate theory is retired
    both zero               the ONLY outcome that promotes the frame-grab arm.
                            Directive, schema and path all present and it still
                            will not emit -> "it has never seen one" becomes the
                            leading explanation

WHAT IS REPORTED, AND WHY `notes`: the v2 block DEMANDS a written decline — "If
a beat matches and you still decline it, SAY SO in `notes` with the reason (one
clause). A silent zero is not an answer." That field is the only window into
whether a zero is a decision or an absence; it is what told us REF-2 was already
edited, and that StatCards were dropped "in favor of crisp kinetic typography".
Reported VERBATIM, never summarised.

COST: 2 cells, plan-only, ~$0.40. Results persist to S3 after every cell — a
result that lives only in the process watching the run is not a result.

    modal run cert_scenes_directive_ab_app.py
"""
import os
import sys
import json

sys.path.insert(0, "/")
import modal, modal_app                                            # noqa: E402

image = (modal_app.image
         .add_local_file("modal_app.py", "/modal_app.py")
         .add_local_file("component_corpus_manifest.json",
                         "/component_corpus_manifest.json"))
app = modal.App("cert-scenes-directive-ab", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]

# A source whose triggers include BOTH "stated number/stat" and "claim the
# footage cannot show" — two of the three beats the v2 block names as
# scene-triggering. Picking a source with no trigger would score a correct
# decline as a defect, which is the exact error this corpus exists to prevent.
SOURCE_ID = "comp_scenes_536daed2"


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=3600)
def run(source_id: str, run_tag: str) -> dict:
    import time
    import uuid
    import traceback
    from build_lane import mark_build_lane
    mark_build_lane("cert_scenes_directive_ab_app.py")
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_POST_THINKING_BUDGET"] = "2048"
    sys.path.insert(0, "/")
    import handler as H

    manifest = json.load(open("/component_corpus_manifest.json"))
    src = next(s for s in manifest["sources"] if s["id"] == source_id)
    OUT = {"source": source_id, "triggers": src.get("triggers"),
           "duration_s": src.get("duration_s"), "cells": []}

    def _one(label, v2_on):
        # The flag is read at call time by _scenes_directive_v2(), so setting it
        # here is what makes the two cells differ — and it is the ONLY thing
        # that differs. One variable.
        os.environ["PROMPTLY_SCENES_DIRECTIVE_V2"] = "1" if v2_on else ""
        jid = str(uuid.uuid4())
        url = ("https://thisismybucketagainwooo.s3.amazonaws.com/"
               f"scenes-directive/{label}/{jid}/out.mp4")
        body = {
            "job_id": jid, "video_url": src["video_url"],
            "vibe": src.get("vibe") or "Make it viral",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": url, "public_url": url, "model": "flare",
            "supports_progressive": False,
            # THE WHOLE POINT: the directive only exists on the premium path.
            "premium_pipeline_enabled": True,
            "plan_only": True,
        }
        try:
            H._component_ledger_reset()
            H._GEMINI_CALL_LOG.clear()
        except Exception:
            pass
        t0 = time.time()
        try:
            res = H.handler({"input": body}) or {}
        except Exception as e:
            return {"cell": label, "v2": v2_on, "error": f"{type(e).__name__}: {e}",
                    "traceback": traceback.format_exc()[-800:],
                    "wall_s": round(time.time() - t0, 1)}
        plan = res.get("edit_plan") if isinstance(res, dict) else None
        scenes = (plan or {}).get("generated_scenes") if isinstance(plan, dict) else None
        cell = {
            "cell": label, "v2": v2_on,
            "wall_s": round(time.time() - t0, 1),
            "premium_confirmed": bool((plan or {}).get("_premium")
                                      if isinstance(plan, dict) else None),
            "generated_scenes": len(scenes) if isinstance(scenes, list) else None,
            "scenes": scenes if isinstance(scenes, list) else None,
            # VERBATIM. The decline reason is the finding when the count is 0.
            "notes": (plan or {}).get("notes") if isinstance(plan, dict) else None,
            "edit_rationale": (plan or {}).get("edit_rationale") if isinstance(plan, dict) else None,
            "video_identity": (plan or {}).get("video_identity") if isinstance(plan, dict) else None,
            "counts": {k: len(v) for k, v in (plan or {}).items()
                       if isinstance(v, list)} if isinstance(plan, dict) else {},
            "gemini_output_tokens": (res or {}).get("gemini_output_tokens"),
            "ledger": H._component_ledger_snapshot(),
        }
        return cell

    for label, v2 in (("ON_v2", True), ("OFF_control", False)):
        c = _one(label, v2)
        OUT["cells"].append(c)
        print(f"[cell] {label:12} scenes={c.get('generated_scenes')} "
              f"wall={c.get('wall_s')}s err={bool(c.get('error'))}", flush=True)
        print("[celljson] " + json.dumps(c, default=str)[:4000], flush=True)
        try:
            import boto3
            boto3.client("s3").put_object(
                Bucket="thisismybucketagainwooo",
                Key=f"scenes-directive/{run_tag}/partial.json",
                Body=json.dumps(OUT, default=str).encode(),
                ContentType="application/json")
        except Exception as e:
            print(f"[celljson] S3 persist failed: {type(e).__name__}", flush=True)
    return OUT


@app.local_entrypoint()
def main():
    tag = os.environ.get("RUN_TAG") or "scenes"
    out = run.remote(SOURCE_ID, tag)
    print(f"\n  SOURCE {out.get('source')}  triggers={out.get('triggers')}")
    for c in out.get("cells", []):
        print(f"\n  ── {c.get('cell')} (SCENES_DIRECTIVE_V2={'1' if c.get('v2') else '0'}) ──")
        if c.get("error"):
            print(f"     ERROR: {c['error']}")
            continue
        print(f"     generated_scenes : {c.get('generated_scenes')}")
        print(f"     wall / out-tokens: {c.get('wall_s')}s / {c.get('gemini_output_tokens')}")
        print(f"     notes (VERBATIM) : {c.get('notes')}")
        print(f"     edit_rationale   : {str(c.get('edit_rationale'))[:300]}")
        if c.get("scenes"):
            for s in c["scenes"][:4]:
                print(f"       scene: {json.dumps(s, default=str)[:220]}")
    a = next((c for c in out.get("cells", []) if c.get("v2")), {})
    b = next((c for c in out.get("cells", []) if not c.get("v2")), {})
    na, nb = a.get("generated_scenes"), b.get("generated_scenes")
    print("\n  ── PRE-REGISTERED READING ──")
    if na and not nb:
        print("     ON non-zero, OFF zero -> the v2 directive WORKS; the old one blocked it.")
    elif na and nb:
        print("     both non-zero -> PREMIUM ALONE was the gate; the rewrite is incidental "
              "and the earn-gate theory is retired.")
    elif not na and not nb:
        print("     BOTH ZERO -> directive, schema and path all present and it still will "
              "not emit. This promotes the frame-grab arm: 'it has never seen one' "
              "becomes the leading explanation.")
    else:
        print("     OFF non-zero with ON zero — unexpected; read the notes before theorising.")
