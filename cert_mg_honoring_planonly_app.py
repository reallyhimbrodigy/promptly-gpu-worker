"""PLAN_ONLY A/B — MG-honoring confirmation (LANE-SEAM, staged 2026-08-11).

QUEUED FOR IGNITION DAY — NOT run at build time. Confirms/refutes H1 of
MG_HONORING_DIAGNOSIS.md: an explicit user MG ask dies at the PLANNER
(restraint doctrine + earn-gates, no obedience channel), and the dark
PROMPTLY_MG_OBEY directive closes the gap without breaking the gates.

Three arms on the SAME source, pipeline captured at render_multi_clip (bail
before render — PLAN_ONLY, zero render spend), mirroring
cert_planonly_fps_ab_app.py:
    control   -> neutral vibe, flag off
    ask       -> the VERBATIM 309-tap preset text ("Make this a smooth video,
                 add zooms, sound effects and motion graphics"), flag off
    ask_obey  -> same text, PROMPTLY_MG_OBEY=1 (the dark directive arm)

Measured per arm: standalone motion_graphics[] count+types+whys, emphasis-
bound emphasis_moments[].motion_graphic count+types (BOTH keys — the H0
lesson: the judge's v1 zoom defect was reading one key), sfx count (the
preset also names them), tokens, Gemini leg wall.

Verdicts the printout states:
  ask ≈ control on MG count      -> H1 CONFIRMED (the ask does not move the planner)
  ask_obey > ask, whys name real moments -> the obedience channel works; queue differ + flip request
  ask_obey == ask                -> H1 alone insufficient; escalate to H2/H3 reads

COST: ~$0.10-0.20/arm plan-only => ~$0.40-0.80 for 4 arms x 1 source. Scale
to N golden sources only on approval inside the standing <=$10 PLAN_ONLY
budget. Run: `modal run cert_mg_honoring_planonly_app.py`.
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-mg-honoring-planonly", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]

# Same durable constructed source the fps A/B used (feedback_ab_durable_sources).
SRC = ("https://d1iax8jos987n3.cloudfront.net/sources/e9b47b30-5edf-4bc6-825a-"
       "7d2a8fe1a43d/1785239363288-A2A4B085-5918-4575-BB13-CC3CD92EF816_L0_001.mp4")

PRESET_ASK = "Make this a smooth video, add zooms, sound effects and motion graphics"
# The cluster ask: names components from more than one family, so the arm
# tests the GENERALIZATION rather than re-testing the MG leg.
CLUSTER_ASK = PRESET_ASK + " and add some transitions and text overlays"
CONTROL_VIBE = "Make this a smooth video"

ARMS = [
    ("control", CONTROL_VIBE, {}),
    ("ask", PRESET_ASK, {}),
    ("ask_obey", PRESET_ASK, {"PROMPTLY_MG_OBEY": "1"}),
    # CLUSTER ARM (2026-08-12, JUDGE's DISHONOR_ROUTE_VERDICT). MG_OBEY was the
    # narrow predecessor; COMPONENT_OBEY arms the same directive for the whole
    # dishonor cluster (transitions, text_overlay, broll, motion_graphics). This
    # arm answers the one question only real Gemini can: does the generalized
    # directive change the PLAN, and does it do so WITHOUT the density collapse
    # the MG diagnosis named. Everything else about the override — dark
    # byte-identity, the negation guard, the note leg — is proven offline for $0
    # by cert_component_obey.py, which runs in the deploy gate.
    ("ask_cluster", CLUSTER_ASK, {"PROMPTLY_COMPONENT_OBEY": "1"}),
]


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=2400)
def run() -> dict:
    import time
    import traceback
    import uuid

    from build_lane import mark_build_lane

    mark_build_lane("cert_mg_honoring_planonly_app.py")

    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ.pop("PROMPTLY_MG_OBEY", None)   # per-ARM control only
    sys.path.insert(0, "/")
    import handler as H

    RESULT = {"arms": {}}

    class _CaptureDone(BaseException):
        pass

    _orig_render = H.render_multi_clip
    _cur = {"arm": None}

    def _spy(*args, **kwargs):
        edit_plan = args[2]
        plan = edit_plan if isinstance(edit_plan, dict) else {}
        mgs = [m for m in (plan.get("motion_graphics") or []) if isinstance(m, dict)]
        em = [e for e in (plan.get("emphasis_moments") or []) if isinstance(e, dict)]
        em_mgs = [e["motion_graphic"] for e in em
                  if isinstance(e.get("motion_graphic"), dict)]
        calls = [c for c in getattr(H, "_GEMINI_CALL_LOG", []) if isinstance(c, dict)]
        RESULT["arms"][_cur["arm"]] = {
            "tokens": H._gemini_token_summary(),
            "gemini_leg_s": round(sum(c.get("total_s") or 0 for c in calls
                                      if not c.get("aborted")), 1),
            # BOTH MG keys — the H0 lesson
            "n_mg_standalone": len(mgs),
            "mg_types": [str(m.get("type")) for m in mgs][:8],
            "mg_whys": [str(m.get("why") or "")[:60] for m in mgs][:8],
            "n_mg_emphasis": len(em_mgs),
            "em_mg_types": [str(m.get("type")) for m in em_mgs][:8],
            "n_emphasis": len(em),
            "n_sfx": len([e for e in em
                          if str(e.get("sound") or "voice") != "voice"]),
            "notes": str(plan.get("notes") or "")[:200],
        }
        raise _CaptureDone()

    H.render_multi_clip = _spy
    try:
        for arm, vibe, env in ARMS:
            _cur["arm"] = arm
            for k in ("PROMPTLY_MG_OBEY",):
                os.environ.pop(k, None)
            os.environ.update(env)
            try:
                H._GEMINI_CALL_LOG.clear()
            except Exception:
                pass
            jid = str(uuid.uuid4())
            url = (f"https://thisismybucketagainwooo.s3.amazonaws.com/"
                   f"planonly-mg/{arm}/{jid}/out.mp4")
            body = {"job_id": jid, "video_url": SRC, "vibe": vibe,
                    "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
                    "upload_url": url, "public_url": url, "model": "flare",
                    "supports_progressive": False,
                    "premium_pipeline_enabled": False, "mode": "full"}
            t0 = time.time()
            try:
                H.handler({"input": body})
            except _CaptureDone:
                pass
            except Exception as e:
                RESULT["arms"][arm] = {
                    "err": f"{type(e).__name__}: {str(e)[:300]}",
                    "tb": traceback.format_exc()[-700:]}
            RESULT.setdefault("wall", {})[arm] = round(time.time() - t0, 1)
    finally:
        H.render_multi_clip = _orig_render
        os.environ.pop("PROMPTLY_MG_OBEY", None)
    return RESULT


@app.local_entrypoint()
def main():
    print("=== PLAN_ONLY: component-honoring A/B (control / ask / ask_obey / ask_cluster) ===")
    o = run.remote()
    a = (o or {}).get("arms", {})
    for arm, _, _env in ARMS:
        d = a.get(arm, {})
        print(f"\n[{arm}]  pipeline_wall={(o.get('wall') or {}).get(arm)}s")
        if d.get("err"):
            print("  ERROR:", d["err"])
            print("  tb:", d.get("tb", ""))
            continue
        print(f"  MG standalone={d.get('n_mg_standalone')} {d.get('mg_types')}")
        print(f"  MG emphasis-bound={d.get('n_mg_emphasis')} {d.get('em_mg_types')}")
        print(f"  whys: {d.get('mg_whys')}")
        print(f"  emphasis={d.get('n_emphasis')} sfx={d.get('n_sfx')}")
        print(f"  notes: {d.get('notes')!r}")
        t = d.get("tokens") or {}
        print(f"  tokens prompt={t.get('prompt')} delta={t.get('uncached_delta')} "
              f"gemini_leg={d.get('gemini_leg_s')}s")
    C, K, O = a.get("control", {}), a.get("ask", {}), a.get("ask_obey", {})

    def _tot(d):
        return (d.get("n_mg_standalone") or 0) + (d.get("n_mg_emphasis") or 0)
    if C and K and O and not any(x.get("err") for x in (C, K, O)):
        print(f"\n  === MG total: control={_tot(C)}  ask={_tot(K)}  ask_obey={_tot(O)}")
        if _tot(K) <= _tot(C):
            print("  === H1 CONFIRMED at the planner: the explicit ask did not move MG output.")
        else:
            print("  === H1 WEAKENED: the ask alone moved MG output — re-rank vs H0/H2/H3.")
        if _tot(O) > _tot(K):
            print("  === OBEY ARM WORKS: directive closes the gap — inspect whys/types, "
                  "then queue the differ + flip request for PROMPTLY_MG_OBEY.")
        else:
            print("  === OBEY ARM DID NOT MOVE: H1-fix insufficient — run the H0/H2/H3 "
                  "$0 DB reads before any prompt surgery.")
    print("\nPLAN_ONLY MG A/B COMPLETE. (One source; scale to golden N on approval.)")
