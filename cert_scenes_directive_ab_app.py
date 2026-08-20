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
# TWO SOURCES, contrasting. 536daed2 is the 61s face-filling talking head whose
# StatCard could not be placed on 2026-08-19 — the hard case, and the one the
# ladder now has to degrade rather than kill. 43c8dbe8 is 25.9s with a
# named-concrete-object trigger, a different framing.
#
# I am NOT claiming to know which has headroom: the rung that fires is the
# measurement. A source where reposition succeeds has room; one where the drop
# fires does not, and the cert already showed contraction cannot save a static
# face — so the outcome names the framing rather than my guess doing it.
SOURCE_IDS = ["comp_scenes_536daed2", "comp_scenes_43c8dbe8"]


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=3600)
def run(source_ids: list, run_tag: str) -> dict:
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
    _by_id = {s["id"]: s for s in manifest["sources"]}
    OUT = {"sources": source_ids, "cells": []}

    def _one(src, label, v2_on):
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
        # TEE, don't redirect. The first run of this harness recorded a cell that
        # produced NO PLAN with no error and no evidence, and I had to pay for a
        # log pull to find out why. I had already fixed exactly this in the
        # prompt-v2 harness and then wrote a new one without the lesson.
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
        try:
            res = H.handler({"input": body}) or {}
        except Exception as e:
            return {"cell": label, "v2": v2_on, "error": f"{type(e).__name__}: {e}",
                    "traceback": traceback.format_exc()[-800:],
                    "stdout_tail": _tee.buf.getvalue()[-3000:],
                    "wall_s": round(time.time() - t0, 1)}
        finally:
            sys.stdout = _orig
        plan = res.get("edit_plan") if isinstance(res, dict) else None
        _no_plan = not isinstance(plan, dict)
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
            # THE DEDICATED DECLINE CHANNEL. `notes` is a MECHANICAL field by
            # design (silence/filler/stutter counts from the first call, merged
            # in after), so an editorial decline placed there collides with
            # bookkeeping — measured: one source carried a real reason, the other
            # carried "2 located_silence, 0 filler". An EMPTY scenes_declined
            # means no beat triggered; it is not the same as a zero with no text.
            "scenes_declined": (plan or {}).get("scenes_declined") if isinstance(plan, dict) else None,
            "edit_rationale": (plan or {}).get("edit_rationale") if isinstance(plan, dict) else None,
            "video_identity": (plan or {}).get("video_identity") if isinstance(plan, dict) else None,
            "counts": {k: len(v) for k, v in (plan or {}).items()
                       if isinstance(v, list)} if isinstance(plan, dict) else {},
            "gemini_output_tokens": (res or {}).get("gemini_output_tokens"),
            "ledger": H._component_ledger_snapshot(),
            # THE THIRD STATE. `generated_scenes: None` means the cell produced no
            # plan; `0` means it produced one and declined. Folding those together
            # is what made my own verdict print "BOTH ZERO" on a run where the ON
            # cell had CRASHED — and that reading would have promoted the
            # frame-grab arm on a false premise.
            "no_plan": _no_plan,
            # the ladder's own outcomes, so the re-run doubles as its first
            # real-traffic exercise
            "placement_notes": [ln for ln in _tee.buf.getvalue().splitlines()
                                if "component(s) left unplaced" in ln
                                or "clear_region_repositioned" in ln
                                or "clear_region_unfittable" in ln][:12],
            "edit_rationale_final": (plan or {}).get("edit_rationale") if isinstance(plan, dict) else None,
        }
        if _no_plan:
            cell["result_error"] = {k: res.get(k) for k in
                                    ("status", "error", "error_code", "user_message")
                                    if isinstance(res, dict)}
            cell["stdout_tail"] = _tee.buf.getvalue()[-3000:]
        return cell

    for _sid in source_ids:
      src = _by_id[_sid]
      for label, v2 in (("ON_v2", True), ("OFF_control", False)):
        c = _one(src, label, v2)
        c["source"] = _sid
        c["triggers"] = src.get("triggers")
        c["duration_s"] = src.get("duration_s")
        OUT["cells"].append(c)
        print(f"[cell] {_sid[:26]:28} {label:12} scenes={c.get('generated_scenes')} "
              f"no_plan={bool(c.get('no_plan'))} wall={c.get('wall_s')}s", flush=True)
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
    out = run.remote(SOURCE_IDS, tag)
    for c in out.get("cells", []):
        print(f"\n  SOURCE {c.get('source')}  ({c.get('duration_s')}s)  "
              f"triggers={c.get('triggers')}")
        print(f"\n  ── {c.get('cell')} (SCENES_DIRECTIVE_V2={'1' if c.get('v2') else '0'}) ──")
        if c.get("error"):
            print(f"     ERROR: {c['error']}")
            continue
        print(f"     generated_scenes : {c.get('generated_scenes')}")
        print(f"     wall / out-tokens: {c.get('wall_s')}s / {c.get('gemini_output_tokens')}")
        print(f"     scenes_declined  : {c.get('scenes_declined')!r}   <- the decline channel")
        print(f"     notes (mechanical): {str(c.get('notes'))[:150]}")
        print(f"     LADDER           : {c.get('placement_notes') or 'no rung fired'}")
        print(f"     rationale FINAL  : {str(c.get('edit_rationale_final'))[:260]}")
        print(f"     edit_rationale   : {str(c.get('edit_rationale'))[:300]}")
        if c.get("scenes"):
            for s in c["scenes"][:4]:
                print(f"       scene: {json.dumps(s, default=str)[:220]}")
    for _sid in SOURCE_IDS:
        _cs = [c for c in out.get("cells", []) if c.get("source") == _sid]
        _on = next((c for c in _cs if c.get("v2")), {})
        _off = next((c for c in _cs if not c.get("v2")), {})
        print(f"\n  == {_sid} ==  ON scenes={_on.get('generated_scenes')} "
              f"(no_plan={bool(_on.get('no_plan'))})  |  OFF scenes="
              f"{_off.get('generated_scenes')} (no_plan={bool(_off.get('no_plan'))})")
    a = next((c for c in out.get("cells", []) if c.get("v2")), {})
    b = next((c for c in out.get("cells", []) if not c.get("v2")), {})
    na, nb = a.get("generated_scenes"), b.get("generated_scenes")
    if a.get("no_plan") or b.get("no_plan") or a.get("error") or b.get("error"):
        print("     INCONCLUSIVE — a cell produced NO PLAN. A failed cell is not a "
              "zero, and reading it as one is how a crash gets reported as a "
              "decline. Fix the failure before reading the scene question.")
        for c in (a, b):
            if c.get("no_plan") or c.get("error"):
                print(f"       {c.get('cell')}: error={c.get('error')} "
                      f"result_error={str(c.get('result_error'))[:160]}")
        return
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
