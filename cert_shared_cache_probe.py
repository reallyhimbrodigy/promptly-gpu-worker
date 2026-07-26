"""SHARED CACHE probe: verify the cross-container reuse logic. One container:
create a cache (writes the shared Dict), clear the LOCAL registry, call again ->
must shared-HIT (same cache_name, no second create)."""
import os, sys
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-shared-cache", image=image)
SECRETS=[modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("gemini-vertex")]

@app.function(secrets=SECRETS, timeout=300, cpu=2.0, memory=4096)
def run() -> dict:
    os.environ["APP_URL"]=""
    import handler as H
    client=H._get_genai_client(); model=H.GEMINI_EDITORIAL_MODEL
    sysi="SHARED-CACHE PROBE static system instruction. " + ("word " * 4000)  # >1024 tokens (Vertex caching minimum)
    out={}
    c1=H._get_or_create_gemini_system_cache(client, model, sysi)
    out["first"]=c1
    # clear LOCAL registry -> next call must consult the shared Dict
    with H._GEMINI_CACHE_LOCK:
        H._GEMINI_CACHE_REGISTRY.clear()
    H._SHARED_CACHE_DICT=None; H._SHARED_CACHE_DICT_TRIED=False  # force re-resolve
    c2=H._get_or_create_gemini_system_cache(client, model, sysi)
    out["second"]=c2
    out["shared_reuse_ok"]=bool(c1 and c2 and c1==c2)
    # cleanup the test cache
    try: client.caches.delete(name=c1)
    except Exception: pass
    return out

@app.local_entrypoint()
def main():
    import json
    print("SHARED-CACHE VERDICT: "+json.dumps(run.remote(), indent=1))
