"""IS gemini-3.7-flash AVAILABLE ON VERTEX? — the editorial catalog, not AI Studio.

`[Rule 4]`

WHY THIS IS NOT ANSWERABLE FROM THE STARTUP LOG. handler's
`_log_available_gemini_models()` builds its list with
`genai_client_mod.Client(api_key=...)` — the AI STUDIO client. So the
`gemini-3.6-flash / gemini-3.7-flash` line in every container's startup output
describes the AI Studio catalog and says NOTHING about Vertex. Editorial runs on
Vertex (`vertexai=True`, project promptly-479218, the gemini-vertex secret), and
the two catalogs differ in both membership and quota.

Reading availability off the wrong catalog is the same error as reading chat's
quota off the Vertex bucket — a plausible number about the wrong system.

WHAT IT REPORTS, per candidate model:
  listed      — does Vertex's ListModels expose it to this project
  callable    — does a MINIMAL generate_content actually return
  error       — the verbatim failure if not (404 = not in this catalog,
                429 = present but no quota, 403 = permission/billing)

`callable` is the only field that matters. A model can be listed and still have
zero provisioned quota — which is precisely how chat reached 100% 429 on a
model Google was happy to name.

PRICED: ~$0.02. One cpu container, a handful of 8-token generations.

    modal run probe_vertex_catalog_app.py
"""
import os
import sys

import modal

sys.path.insert(0, "/")

import modal_app as _prod  # noqa: E402

app = modal.App("probe-vertex-catalog")

_IMAGE = _prod.image.add_local_file("modal_app.py", "/modal_app.py")

CANDIDATES = [
    "gemini-3.7-flash",          # the owner's pick for chat + the A/B arm
    "gemini-3.6-flash",          # what chat is pinned to right now
    "gemini-3.1-pro-preview",    # THE CURRENT EDITORIAL MODEL — the control
    "gemini-3.5-flash",
]


@app.function(image=_IMAGE, cpu=2, memory=4096, timeout=600,
              secrets=[modal.Secret.from_name("promptly-secrets"),
                       modal.Secret.from_name("gemini-vertex")])
def probe() -> dict:
    sys.path.insert(0, "/")
    import handler as H

    out = {"vertex_configured": False, "listed": [], "results": {}}

    # THE EDITORIAL CLIENT ITSELF — handler._get_genai_client(). Not a rebuild.
    #
    # My first version guessed at `H.genai_client` / `H.client`, found neither,
    # and fell through to a hand-rolled google.genai Client() that relies on
    # Application Default Credentials. ADC is not configured in this container,
    # so ALL FOUR candidates returned DefaultCredentialsError — INCLUDING
    # gemini-3.1-pro-preview, the model we KNOW works because the Lumen editorial
    # run succeeded on it hours earlier.
    #
    # THE CONTROL IS WHY THAT DID NOT BECOME A FALSE FINDING. A probe whose
    # known-good arm fails is measuring itself, not its subject, and without
    # 3.1-pro in the list I would have reported "3.7 Flash is unavailable on
    # Vertex" — confidently, and wrongly.
    #
    # handler builds the client with explicit service-account credentials from
    # GCP_SERVICE_ACCOUNT_JSON (never ADC) plus an http_options timeout. Asking
    # handler for it means the probe tests the SAME client editorial uses.
    try:
        client = H._get_genai_client()
    except Exception as e:
        out["error"] = f"handler._get_genai_client() failed: {type(e).__name__}: {e}"
        return out
    out["control_model"] = getattr(H, "GEMINI_EDITORIAL_MODEL", "?")
    out["vertex_configured"] = True
    out["client_repr"] = str(type(client))

    try:
        for m in client.models.list():
            nm = str(getattr(m, "name", "") or "")
            if "gemini-3" in nm:
                out["listed"].append(nm)
    except Exception as e:
        out["list_error"] = f"{type(e).__name__}: {str(e)[:300]}"

    # LISTED IS NOT CALLABLE. Prove each one with a real (tiny) generation.
    # THE CONTROL RUNS FIRST AND ITS RESULT IS LOAD-BEARING: if the current
    # editorial model is not callable, the probe is broken and every other row is
    # noise. Report that rather than the candidates.
    for model in CANDIDATES:
        rec = {"listed": any(model in n for n in out["listed"])}
        try:
            r = client.models.generate_content(
                model=model,
                contents="Reply with the single word: ok",
                config={"max_output_tokens": 8, "temperature": 0.0},
            )
            rec["callable"] = True
            rec["sample"] = str(getattr(r, "text", ""))[:40]
        except Exception as e:
            rec["callable"] = False
            rec["error"] = f"{type(e).__name__}: {str(e)[:400]}"
        out["results"][model] = rec
        print(f"[vertex-catalog] {model:26} listed={rec['listed']} "
              f"callable={rec['callable']} {rec.get('error','')[:160]}", flush=True)
    return out


@app.local_entrypoint()
def main():
    import json
    print("=== VERTEX CATALOG PROBE — editorial surface, priced ~$0.02 ===")
    r = probe.remote()
    print(f"\nvertex client built : {r.get('vertex_configured')}")
    if r.get("error"):
        print(f"ERROR: {r['error']}")
        return
    print(f"gemini-3.x listed   : {len(r.get('listed') or [])}")
    for n in (r.get("listed") or [])[:20]:
        print(f"   {n}")
    if r.get("list_error"):
        print(f"list error          : {r['list_error']}")
    print("\nCALLABLE (the only field that matters — listed != provisioned):")
    for m, rec in (r.get("results") or {}).items():
        mark = "OK " if rec.get("callable") else "NO "
        print(f"  {mark} {m:26} listed={rec.get('listed')}")
        if rec.get("error"):
            print(f"        {rec['error'][:300]}")
    _ok = [m for m, rec in (r.get("results") or {}).items() if rec.get("callable")]
    print(f"\n  callable on Vertex: {_ok or 'NONE'}")
    if "gemini-3.7-flash" not in _ok:
        print("  -> 3.7 Flash is NOT usable for the editorial path on this project;")
        print("     the A/B cannot run against it until that changes.")
