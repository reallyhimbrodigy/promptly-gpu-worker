import json, os, modal
app = modal.App("probe-video-jobs-schema")
image = modal.Image.debian_slim().pip_install("supabase", "requests")
S = [modal.Secret.from_name("promptly-secrets")]

@app.function(image=image, secrets=S, timeout=300)
def probe() -> dict:
    import requests as rq
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY"))
    out = {}
    # OpenAPI spec names required fields + types without guessing.
    r = rq.get(f"{url}/rest/v1/", headers={"apikey": key,
               "Authorization": f"Bearer {key}"}, timeout=30)
    spec = r.json()
    vj = (spec.get("definitions") or {}).get("video_jobs") or {}
    out["required"] = vj.get("required")
    props = vj.get("properties") or {}
    out["not_null_no_default"] = sorted(
        k for k, v in props.items()
        if "<nullable>" not in str(v.get("description", "")) and k in (vj.get("required") or []))
    out["all_columns"] = sorted(props.keys())[:60]
    # The CHECK constraints only surface on a real attempt — try the minimal row.
    from supabase import create_client
    sb = create_client(url, key)
    import uuid
    jid = str(uuid.uuid4())
    for attempt in ({"id": jid, "status": "queued"},
                    {"id": jid, "status": "queued", "user_id": str(uuid.uuid4())}):
        try:
            sb.table("video_jobs").insert(attempt).execute()
            out["insert_ok_with"] = sorted(attempt.keys())
            sb.table("video_jobs").delete().eq("id", jid).execute()
            break
        except Exception as e:
            out.setdefault("insert_errors", []).append(
                {"tried": sorted(attempt.keys()), "err": str(e)[:300]})
    return out

@app.local_entrypoint()
def main():
    r = probe.remote()
    print(json.dumps(r, indent=1)[:2200])
