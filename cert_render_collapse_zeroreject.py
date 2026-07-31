"""RENDER-COLLAPSE ZERO-REJECT PROOF (Zac 2026-07-28).

The deterministic reproducer: a30c027c's source collapsed to RENDER_TOO_SHORT
TWICE in prod (23:03 + 23:11, post-v385). With the fix (flag-gated behind
PROMPTLY_ZERO_REJECT, live=1) the collapse must now fall back to MINIMAL — the
user gets a real video instead of a dead-end + refund. This also exercises the
POST-render _MinimalRouteSignal path (raised inside render_stage after the render,
distinct from the intake gates that raise pre-render) — the known-untested class.

Asserts: status success (NOT a RENDER_TOO_SHORT failure), a real video_url, and
the render_collapsed_to_minimal divergence fired (collapse detected + routed, not
suppressed)."""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-collapse-zeroreject", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
SRC = "https://d1iax8jos987n3.cloudfront.net/sources/a30c027c-14b8-435b-98ff-45653047ab65/1785279752327-4766D77A-178D-41C5-95FD-3F3F7B4F47B2_L0_001.mp4"


@app.function(secrets=SECRETS, cpu=32.0, memory=131072, timeout=2400)
def run() -> dict:
    import uuid, traceback
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_ZERO_REJECT"] = "1"   # the fallback is flag-gated; ensure ON
    sys.path.insert(0, "/")
    import handler as H

    divs = []
    _orig_div = H._record_divergence
    def _div_spy(component, data, action, reason=None, **k):
        divs.append({"component": component, "action": action, "reason": reason})
        return _orig_div(component, data, action, reason=reason, **k)
    H._record_divergence = _div_spy

    out = {}
    jid = str(uuid.uuid4()); base = f"https://thisismybucketagainwooo.s3.amazonaws.com/collapse-proof/{jid}"
    body = {"job_id": jid, "video_url": SRC, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": f"{base}/out.mp4", "public_url": f"{base}/out.mp4",
            "upload_url_thumb": f"{base}/thumb.jpg",
            "model": "flare", "supports_progressive": False,
            "premium_pipeline_enabled": False, "mode": "full"}
    try:
        res = H.handler({"input": body})
    except Exception as e:
        out["raised"] = f"{type(e).__name__}: {str(e)[:300]}"; out["tb"] = traceback.format_exc()[-900:]; res = {}
    finally:
        H._record_divergence = _orig_div
    rp = res if isinstance(res, dict) else {}

    collapse_div = [d for d in divs if d["action"] == "render_collapsed_to_minimal"]
    checks = []
    def ck(n, c, d=""): checks.append({"name": n, "pass": bool(c), "detail": str(d)[:200]})
    ck("collapse detected + routed (render_collapsed_to_minimal divergence fired)", len(collapse_div) >= 1,
       collapse_div[0]["reason"] if collapse_div else "NOT FIRED — source did not collapse this run")
    ck("status success (NOT a RENDER_TOO_SHORT dead-end)", rp.get("status") in ("success", None) and not rp.get("error"),
       f"status={rp.get('status')} error={rp.get('error')} code={rp.get('error_code')}")
    vu = rp.get("video_url") or ""
    ck("user got a real video_url", vu.startswith("http") and vu.endswith(".mp4"), vu)
    ck("route is minimal/hype (not the TH edit that collapsed)", str(rp.get("route") or (rp.get("edit_recipe") or {}).get("route") or "").lower() in ("minimal", "hype", "moodreel", "") or "minimal" in str(rp.get("route") or "").lower(), rp.get("route"))
    ck("NOT RENDER_TOO_SHORT", rp.get("error_code") != "RENDER_TOO_SHORT" and "RENDER_TOO_SHORT" not in str(out.get("raised") or ""), rp.get("error_code"))

    out["checks"] = checks
    out["all_pass"] = all(c["pass"] for c in checks)
    out["route"] = rp.get("route"); out["video_url"] = rp.get("video_url"); out["status"] = rp.get("status")
    out["divergences"] = [d["action"] for d in divs]
    out["collapse_reason"] = collapse_div[0]["reason"] if collapse_div else None
    return out


@app.local_entrypoint()
def main():
    print("=== RENDER-COLLAPSE ZERO-REJECT PROOF (a30c027c deterministic reproducer) ===")
    o = run.remote()
    if o.get("raised"): print("RAISED:", o["raised"]); print(o.get("tb", ""))
    print("status:", o.get("status"), "| route:", o.get("route"), "| video_url:", o.get("video_url"))
    print("collapse_reason:", o.get("collapse_reason"))
    print("divergences:", json.dumps(o.get("divergences")))
    print("\n--- CHECKS ---")
    for c in (o.get("checks") or []):
        print(("  PASS " if c["pass"] else "  FAIL ") + c["name"] + (f"   [{c['detail']}]" if not c["pass"] else ""))
    print("\nALL PASS:", o.get("all_pass"))
