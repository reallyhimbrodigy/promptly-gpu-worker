"""PLAN-GUARD DETERMINISTIC PROOF (Zac 2026-07-28 note #1).

The collapse is stochastic (can't be forced by source), but the floor is a per-job
override: min_output_ratio_test=0.99 makes the min-output-ratio guard fire on ANY
plan (no plan keeps 99% of source). One render exercises the WHOLE plan_collapsed
route — pre-render routing, minimal render, delivery, and BOTH divergences
(plan_output_ratio telemetry on every job + plan_collapsed_to_minimal on the fire).

Asserts: the guard fired (plan_collapsed_to_minimal divergence), the per-job ratio
telemetry fired (plan_output_ratio), status success with a real video_url (minimal),
and NOT a RENDER_TOO_SHORT dead-end."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-plan-guard-verify2", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/0f739aeb-a5e1-458d-a117-eb326841b069/1785241163074-2BE40123-3749-4120-8902-D1B5BBC28552_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=32.0, memory=131072, timeout=2400)
def run() -> dict:
    import uuid, traceback
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_ZERO_REJECT"] = "1"
    sys.path.insert(0, "/")
    import handler as H

    divs = []
    _orig = H._record_divergence
    def _spy(*a, **k):
        try:
            divs.append({"action": (a[2] if len(a) > 2 else k.get("action")),
                         "reason": k.get("reason"),
                         "data": (a[1] if len(a) > 1 else k.get("data"))})
        except Exception:
            pass
        return _orig(*a, **k)
    H._record_divergence = _spy

    out = {}
    jid = str(uuid.uuid4()); base = f"https://thisismybucketagainwooo.s3.amazonaws.com/planguard/{jid}"
    body = {"job_id": jid, "video_url": SRC, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": f"{base}/out.mp4", "public_url": f"{base}/out.mp4",
            "upload_url_thumb": f"{base}/thumb.jpg",
            "min_output_ratio_test": 0.99,   # force the guard on ANY plan
            "model": "flare", "supports_progressive": False,
            "premium_pipeline_enabled": False, "mode": "full"}
    try:
        res = H.handler({"input": body})
    except Exception as e:
        out["raised"] = f"{type(e).__name__}: {str(e)[:300]}"; out["tb"] = traceback.format_exc()[-800:]; res = {}
    finally:
        H._record_divergence = _orig
    rp = res if isinstance(res, dict) else {}

    guard = [d for d in divs if d["action"] == "plan_collapsed_to_minimal"]
    ratio = [d for d in divs if d["action"] == "plan_output_ratio"]
    checks = []
    def ck(n, c, d=""): checks.append({"name": n, "pass": bool(c), "detail": str(d)[:200]})
    ck("plan-guard FIRED (plan_collapsed_to_minimal divergence)", len(guard) >= 1, guard[0]["reason"] if guard else "NOT FIRED")
    ck("per-job ratio TELEMETRY fired (plan_output_ratio, every job)", len(ratio) >= 1, ratio[0]["reason"] if ratio else "NOT FIRED")
    ck("guard fired BEFORE render (proj_out < floor recorded)", bool(guard) and "projected_out_s" in (guard[0]["data"] if guard else {}), guard[0]["data"] if guard else {})
    ck("status success (routed to minimal, not a dead-end)", rp.get("status") in ("success", None) and not rp.get("error"),
       f"status={rp.get('status')} error={rp.get('error')} code={rp.get('error_code')}")
    vu = rp.get("video_url") or ""
    ck("user got a real video_url", vu.startswith("http") and vu.endswith(".mp4"), vu)
    ck("NOT RENDER_TOO_SHORT", rp.get("error_code") != "RENDER_TOO_SHORT" and "RENDER_TOO_SHORT" not in str(out.get("raised") or ""), rp.get("error_code"))

    out["checks"] = checks
    out["all_pass"] = all(c["pass"] for c in checks)
    out["status"] = rp.get("status"); out["video_url"] = rp.get("video_url"); out["route"] = rp.get("route")
    out["divergence_actions"] = sorted(set(d["action"] for d in divs))
    out["guard_reason"] = guard[0]["reason"] if guard else None
    out["ratio_reason"] = ratio[0]["reason"] if ratio else None
    return out


@app.local_entrypoint()
def main():
    print("=== PLAN-GUARD DETERMINISTIC PROOF (min_output_ratio_test=0.99) ===")
    o = run.remote()
    if o.get("raised"): print("RAISED:", o["raised"]); print(o.get("tb", ""))
    print("status:", o.get("status"), "| video_url:", o.get("video_url"), "| route:", o.get("route"))
    print("guard_reason:", o.get("guard_reason"))
    print("ratio_reason:", o.get("ratio_reason"))
    print("divergence_actions:", json.dumps(o.get("divergence_actions")))
    print("\n--- CHECKS ---")
    for c in (o.get("checks") or []):
        print(("  PASS " if c["pass"] else "  FAIL ") + c["name"] + (f"   [{c['detail']}]" if not c["pass"] else ""))
    print("\nALL PASS:", o.get("all_pass"))
