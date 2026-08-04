"""Server→WORKER auth ping (Zac 2026-08-03): the inverse of cert_auth_ping.py.

IF the run-job auth gate (_require_worker_auth, keyed on MODAL_RUN_SECRET) is
present in the image, this proves the SERVER's own credential authenticates to
the worker BEFORE the deploy completes — the exact check that would have caught
v446, where the gate 403'd every dispatch because no caller sent _worker_auth.

Reads MODAL_RUN_SECRET (the server's credential) from the deployed secret set and
POSTs it as _worker_auth to a gated worker endpoint. _require_worker_auth runs
FIRST, before any endpoint logic, so a 403 means the auth FAILED and a non-403
means it PASSED (whatever the endpoint then does with a benign payload). deploy.sh
fails the deploy on is_403=true.

  modal run cert_run_auth_ping.py   → prints RUN_AUTH_PING {..., "is_403": bool}
"""
import modal

image = modal.Image.debian_slim().pip_install("requests")
app = modal.App("cert-run-auth-ping", image=image)

# The validator endpoint is one of the five _require_worker_auth gates; the auth
# decision is made before it touches the (absent) video, so a benign body only
# ever yields a non-403 error AFTER auth passes.
_VALIDATE_URL = ("https://reallyhimbrodigy--promptly-gpu-worker-"
                 "promptlyvalidator--3ad3a2.modal.run")


@app.function(secrets=[modal.Secret.from_name("promptly-secrets")])
def ping():
    import os
    import requests
    secret = os.environ.get("MODAL_RUN_SECRET", "")
    if not secret:
        # No credential configured — the gate (if present) would 503, not 403.
        # Report it so deploy.sh can treat a missing run secret as a failure too.
        return {"status": 0, "is_403": False, "note": "MODAL_RUN_SECRET unset"}
    try:
        r = requests.post(_VALIDATE_URL, json={"_worker_auth": secret}, timeout=30)
        return {"status": r.status_code, "is_403": r.status_code == 403,
                "sent_len": len(secret), "body": (r.text or "")[:120]}
    except Exception as e:
        return {"status": -1, "is_403": False, "note": str(e)[:150]}


@app.local_entrypoint()
def main():
    import json
    print("RUN_AUTH_PING " + json.dumps(ping.remote()))
