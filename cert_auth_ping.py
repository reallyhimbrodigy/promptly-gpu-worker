"""Deploy-time AUTH PING (Zac 2026-08-03): prove the worker can AUTHENTICATE to
the server. Reads MODAL_CALLBACK_SECRET (the exact value the worker sends) + APP_URL
from the deployed secret set and POSTs to /api/internal/auth-ping. deploy.sh fails
the deploy LOUDLY on non-200 so a secret mismatch can NEVER again degrade silently
into the recovery path (tonight it cost hours). Generalises to MODAL_RUN_SECRET.

  modal run cert_auth_ping.py     → prints AUTH_PING_STATUS=<code>
"""
import modal

image = modal.Image.debian_slim().pip_install("requests")
app = modal.App("cert-auth-ping", image=image)


@app.function(secrets=[modal.Secret.from_name("promptly-secrets")])
def ping():
    import os
    import requests
    app_url = (os.environ.get("APP_URL", "").rstrip("/")) or "https://usepromptly.app"
    secret = os.environ.get("MODAL_CALLBACK_SECRET", "")
    try:
        r = requests.post(f"{app_url}/api/internal/auth-ping",
                          headers={"X-Modal-Secret": secret}, json={}, timeout=15)
        return {"status": r.status_code, "url": app_url,
                "sent_len": len(secret),
                "sent_fp": (secret[:4] + ".." + secret[-4:]) if secret else "",
                "body": r.text[:120]}
    except Exception as e:
        return {"status": -1, "note": str(e)[:150], "url": app_url}


@app.local_entrypoint()
def main():
    import json
    r = ping.remote()
    print("AUTH_PING_STATUS=" + str(r.get("status")))
    print("AUTH_PING_DETAIL=" + json.dumps(r))
