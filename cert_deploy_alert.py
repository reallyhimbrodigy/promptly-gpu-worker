"""PAGE THE OWNER ON A DEPLOY RACE (Zac 2026-08-04).

Speed's post-deploy TOCTOU guard (1032ec2) detects the race that predeploy
cannot prevent: a concurrent lane deploying between our check and our
`modal deploy`, so live diverges from what we just shipped. It PRINTED the
finding and explicitly deferred the paging to this lane — "wire sendOwnerAlert
here in the canonical deploy.sh so every lane pages on this, not just prints."

A printed warning is read by whoever is watching that terminal. v512 dropped
clean_export_key on both routes and nobody saw it for 70 minutes, which is
exactly the failure mode a print does not fix.

The local shell has no MODAL_CALLBACK_SECRET — deploy.sh runs on an operator's
laptop. So this borrows the same trick as cert_auth_ping.py: run INSIDE Modal,
where the deployed secret set is mounted, and POST from there. DEPLOY_RACE is
not in the server's NON_ALERTING set, so it pages (loud-failsafe).

  modal run cert_deploy_alert.py --detail "..."   -> prints DEPLOY_ALERT_STATUS=<code>
"""
import modal

image = modal.Image.debian_slim().pip_install("requests")
app = modal.App("cert-deploy-alert", image=image)


@app.function(secrets=[modal.Secret.from_name("promptly-secrets")])
def fire(detail: str = ""):
    import os
    import requests
    app_url = (os.environ.get("APP_URL", "").rstrip("/")) or "https://usepromptly.app"
    secret = os.environ.get("MODAL_CALLBACK_SECRET", "")
    try:
        r = requests.post(
            f"{app_url}/api/internal/render-alert",
            headers={"X-Modal-Secret": secret},
            json={
                "job_id": "deploy-race",
                "error_code": "DEPLOY_RACE",
                "detail": str(detail)[:500],
                "category": "deploy",
            },
            timeout=15,
        )
        return {"status": r.status_code, "body": r.text[:120]}
    except Exception as e:                                        # noqa: BLE001
        return {"status": -1, "note": str(e)[:160]}


@app.local_entrypoint()
def main(detail: str = "post-deploy TOCTOU: live diverged from the shipped tree"):
    out = fire.remote(detail)
    print(f"DEPLOY_ALERT_STATUS={out.get('status')}")
    print(f"DEPLOY_ALERT_DETAIL={out}")
