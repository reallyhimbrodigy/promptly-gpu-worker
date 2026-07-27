"""Coverage-gate E2E — run the REAL handler.handler with coverage_gate_test=True on a
mangled Urdu source and confirm it rejects END-TO-END with error_code
TRANSCRIPTION_INCOMPLETE + designed_rejection=true (the refund flag). Fast: the gate
fires at intake, before any render. Proves the raise→classify→refund wiring before flip.
"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-coverage-e2e", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
CORPORA = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/corpora.json"


@app.function(secrets=SECRETS, cpu=16.0, memory=32768, timeout=1200)
def run_arm(arm: dict) -> dict:
    import time, uuid, traceback
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    url = f"https://thisismybucketagainwooo.s3.amazonaws.com/coverage-e2e/{jid}/render.mp4"
    body = {"job_id": jid, "video_url": arm["video_url"], "vibe": "Clean and engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904", "upload_url": url, "public_url": url,
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False,
            "coverage_gate_test": bool(arm.get("gate_on"))}
    t0 = time.time()
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"label": arm["label"], "exc": f"{type(e).__name__}: {str(e)[:200]}",
                "tb": traceback.format_exc()[-500:], "wall_s": round(time.time()-t0,1)}
    r = res if isinstance(res, dict) else {}
    # error_code may live at top-level or nested in result
    ec = r.get("error_code") or (r.get("result") or {}).get("error_code")
    dr = r.get("designed_rejection") or (r.get("result") or {}).get("designed_rejection")
    um = r.get("user_message") or (r.get("result") or {}).get("user_message") or r.get("error")
    return {"label": arm["label"], "gate_on": bool(arm.get("gate_on")),
            "status": r.get("status"), "error_code": ec, "designed_rejection": dr,
            "user_message": (um or "")[:180], "keys": list(r.keys())[:12], "wall_s": round(time.time()-t0,1)}


@app.local_entrypoint()
def main():
    items = json.load(open(CORPORA))
    urdu = next(i for i in items if i["label"] == "URDU" and i["job_id"].startswith("16b4bdd2"))
    arms = [
        {"label": "URDU_gateON",  "video_url": urdu["video_url"], "gate_on": True},
        {"label": "URDU_gateOFF", "video_url": urdu["video_url"], "gate_on": False},  # control: proceeds (byte-identical)
    ]
    print("=== COVERAGE GATE E2E (Urdu source, gate ON vs OFF) ===")
    out = list(run_arm.map(arms))
    for r in out:
        print("\n---", r["label"], f"(wall {r.get('wall_s')}s) ---")
        if r.get("exc"):
            print("  EXC:", r["exc"]); print("  tb:", r.get("tb","")[-300:]); continue
        print("  status:", r.get("status"), "error_code:", r.get("error_code"),
              "designed_rejection:", r.get("designed_rejection"))
        print("  user_message:", r.get("user_message"))
    # verdict
    on = next((r for r in out if r["label"]=="URDU_gateON"), {})
    print("\nVERDICT:", "PASS — gate rejects mangled Urdu E2E with refund flag"
          if on.get("error_code")=="TRANSCRIPTION_INCOMPLETE" and on.get("designed_rejection")
          else f"FAIL — expected TRANSCRIPTION_INCOMPLETE+designed_rejection, got code={on.get('error_code')} dr={on.get('designed_rejection')}")
