#!/usr/bin/env python3
"""DOES THE PLANNER ASK FOR THE THREE COMPOSITIONS, NOW THAT THEY ARE FILED UNDER
=== MOTION GRAPHICS === INSTEAD OF THE SEAM SECTION?

THE ONE NUMBER: requested, per composition. Nothing else in this probe matters.

PLAN_ONLY, NOT A RENDER. The catalog section is read by the planning call; the
render cannot change what was asked for. A render costs ~$0.30, takes ~13
minutes, and exposes the answer to render-stage failure — which is exactly what
happened on the first confirming attempt: 4/4 post-cuts attempts came back
degenerate, the job died with EDITOR_GENERIC, and the question went unanswered
after full price. A plan-only cell is ~$0.05 and answers it directly.

THREE STATES, NEVER TWO. `requested=0` and `the cell never produced a plan` are
different facts, and collapsing them is how this campaign spent a week believing
generated_scenes was zero when the harness was broken:

    REQUESTED      >=1 of the four appears in a plan that came back
    NOT_REQUESTED  a plan came back, carried motion graphics, none were ours
    NO_MG          a plan came back and asked for NO motion graphics at all
                   (uninformative for this question — not evidence of refusal)
    FAILED         no plan (degeneration, transport, crash) — NOT a zero

N CELLS BECAUSE THE PLANNER IS A SAMPLER. Two runs of the identical prompt on
this identical source, minutes apart, produced different plans (one filled
props, one wrote the payload into `why`). One cell is an anecdote either way.

    modal run probe_compositions_requested.py            # ~$0.05/cell
"""
import json
import os
import sys

sys.path.insert(0, "/")
import modal, modal_app                                            # noqa: E402

image = (modal_app.image
         .add_local_file("modal_app.py", "/modal_app.py")
         .add_local_file("scene_corpus_manifest.json", "/scene_corpus_manifest.json"))
app = modal.App("probe-compositions-requested", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]

SOURCE_ID = "cada6a1b"
THREE = ["EvidenceCard", "DeviceMockup", "EmojiCard"]
CELLS = 3


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=1800)
def cell(i: int) -> dict:
    import time
    import uuid
    import traceback
    import io as _io
    from build_lane import mark_build_lane
    mark_build_lane("probe_compositions_requested.py")
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H

    man = json.load(open("/scene_corpus_manifest.json"))
    src = next(s for s in man["sources"] if s["id"].startswith(SOURCE_ID))
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/comp-probe/{jid}/out.mp4"
    body = {
        "job_id": jid, "video_url": src["video_url"],
        "vibe": src.get("vibe") or "Make it viral",
        "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
        "upload_url": url, "public_url": url, "model": "flare",
        "supports_progressive": False,
        "premium_pipeline_enabled": True,
        "plan_only": True,
    }
    try:
        H._component_ledger_reset()
    except Exception:
        pass

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

    _tee, _orig = _Tee(sys.stdout), sys.stdout
    sys.stdout = _tee
    t0 = time.time()
    try:
        res = H.handler({"input": body}) or {}
        err = None
    except Exception as e:
        res, err = {}, f"{type(e).__name__}: {e}"
    finally:
        sys.stdout = _orig
    log = _tee.buf.getvalue()

    plan = res.get("edit_recipe") or res.get("edit_plan") or {}
    mgs = [m for m in (plan.get("motion_graphics") or []) if isinstance(m, dict)]
    # THE PLAN IS POST-DROP. A component the planner ASKED for and we dropped
    # (empty props, ungrounded text) is gone from this list, so reading it alone
    # under-reports the request — cell 1 of the first run asked for two
    # StatCards, lost both to empty_props, and was classified NO_MG, which reads
    # as "asked for nothing". REQUESTED = what survived + what we dropped.
    import re as _re0
    dropped_types = _re0.findall(r"DROP motion_graphic '([A-Za-z]+)'", log)
    types = [m.get("type") for m in mgs] + dropped_types
    ours = [t for t in types if t in THREE]
    # The model's own JSON is the backstop: if the payload shape ever changes
    # again, a raw scan of the transcript still sees what was asked for.
    raw = {t: log.count(f'"type": "{t}"') for t in THREE}

    if err or (not plan and not mgs and not dropped_types):
        state = "FAILED"
    elif ours:
        state = "REQUESTED"
    elif types:
        state = "NOT_REQUESTED"
    else:
        state = "NO_MG"

    return {
        "i": i, "state": state, "wall_s": round(time.time() - t0, 1),
        "error": err or (res.get("error") if isinstance(res, dict) else None),
        "error_code": res.get("error_code") if isinstance(res, dict) else None,
        "mg_types_requested": types,
        "dropped_types": dropped_types,
        "four_requested": ours,
        "four_in_raw_json": {k: v for k, v in raw.items() if v},
        "ledger": {k: v for k, v in (res.get("component_ledger") or {}).items()
                   if k.startswith("motion_graphic:")},
        "degen_attempts": log.count("Degenerate response"),
        "props_empty_drops": log.count("props are empty"),
    }


@app.local_entrypoint()
def main():
    rows = list(cell.map(range(CELLS)))
    print("\n  ════ REQUESTED PER COMPOSITION — the entire result ════")
    got = {k: 0 for k in THREE}
    states = {}
    for r in rows:
        states[r["state"]] = states.get(r["state"], 0) + 1
        for t in r["four_requested"]:
            got[t] = got.get(t, 0) + 1
        print(f"\n  cell {r['i']}  {r['state']:14} wall={r['wall_s']}s  "
              f"degen_retries={r['degen_attempts']}  empty_props={r['props_empty_drops']}")
        print(f"    MG types requested : {r['mg_types_requested']}"
              f"   (incl. dropped: {r.get('dropped_types') or 'none'})")
        print(f"    OURS               : {r['four_requested'] or 'none'}   "
              f"raw-json scan: {r['four_in_raw_json'] or '{}'}")
        if r.get("error"):
            print(f"    error [{r.get('error_code')}]: {str(r['error'])[:150]}")
        for k, v in sorted((r.get("ledger") or {}).items()):
            print(f"    ledger {k.split(':')[-1]:14} requested={v.get('requested')} "
                  f"dropped_by_us={v.get('dropped_by_us')} {v.get('drop_reasons')}")
    usable = sum(v for k, v in states.items() if k != "FAILED")
    print(f"\n  ──────────────────────────────────────────────")
    print(f"  cells: {states}   usable (a plan came back): {usable}/{len(rows)}")
    for k in THREE:
        print(f"    {k:14} requested in {got[k]}/{usable} usable cells")
    if usable == 0:
        print("  VERDICT: NO EVIDENCE — every cell failed. This is NOT a zero.")
    elif any(got.values()):
        print("  VERDICT: REQUESTED — the section move opened the path.")
    else:
        print(f"  VERDICT: NOT REQUESTED in {usable} usable cell(s) — the move was "
              f"necessary but not sufficient.")
    with open("/tmp/comp_probe.json", "w") as fh:
        json.dump(rows, fh, indent=1)
