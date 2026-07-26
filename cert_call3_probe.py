"""CALL-3 (transitions subcall) LATENCY PROBE — measures the wall-clock of the
transitions subcall that runs SERIAL after Call 2. Ephemeral (modal run only).
Constructs a realistic plan_read + seam_block and times _call_transitions_subcall
across N runs (total wall-clock + a streaming ttfb approximation). No video part
(the subcall is text-only), so this isolates the pure subcall cost."""
import os, sys
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-call3-probe", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]

@app.function(secrets=SECRETS, timeout=1200, cpu=4.0, memory=8192)
def run_probe(n_seams: int = 6, iters: int = 5) -> dict:
    import time, json, statistics as st
    os.environ["APP_URL"] = ""
    import handler as H
    from google.genai import types as _gt
    client = H._get_genai_client()
    model = H.GEMINI_EDITORIAL_MODEL
    # realistic plan_read (the video_plan fields the subcall receives)
    plan_read = "=== THE PLAN'S READ ===\n" + json.dumps({
        "editorial_vision": "A punchy, high-energy breakdown that builds to a clear payoff.",
        "story_shape": "hook -> three escalating points -> resolution",
        "arc_segments": [{"label":"hook","start":0,"end":40},{"label":"build","start":40,"end":300},{"label":"payoff","start":300,"end":461}],
        "key_moments": [{"awi":6,"why":"the promise lands"},{"awi":57,"why":"turn"},{"awi":144,"why":"the reveal"}],
        "movements": ["establish","escalate","resolve"],
    })
    seams = [{"awi": 28+30*i, "kind": "TIGHT" if i%2 else "GAP", "gap_ms": 0 if i%2 else 420} for i in range(n_seams)]
    seam_lines = []
    for s in seams:
        seam_lines.append(f'{s["awi"]} ({s["kind"]}, {s["gap_ms"]}ms usable silence) — "...context words around the seam here..."')
    seam_block = "\n".join(seam_lines)
    schema, _nv, _no = H._build_transitions_subcall_schema(seams)
    out = {"n_seams": n_seams, "iters": iters, "runs": []}
    if schema is None:
        out["error"] = "schema None"; return out
    # total wall-clock via the real _call_transitions_subcall
    for i in range(iters):
        t0 = time.time()
        r = H._call_transitions_subcall(client, model, plan_read, seam_block, schema)
        dt = time.time() - t0
        out["runs"].append({"total_s": round(dt,1), "ok": isinstance(r, dict),
                            "n_transitions": len((r or {}).get("cut_boundary_transitions") or []) if isinstance(r,dict) else 0})
    # one streaming call to approximate ttfb vs output
    try:
        t0=time.time(); ttfb=None; parts=[]
        stream=client.models.generate_content_stream(model=model,
            contents=f"{plan_read}\n\n=== THE SEAMS ===\n{seam_block}",
            config=_gt.GenerateContentConfig(system_instruction=H._TRANSITIONS_SUBCALL_SYS,
                response_mime_type="application/json", response_schema=schema,
                temperature=1.0, max_output_tokens=8192))
        for ch in stream:
            if ttfb is None: ttfb=time.time()-t0
            if getattr(ch,"text",None): parts.append(ch.text)
        out["stream"]={"ttfb_s":round(ttfb or 0,1),"total_s":round(time.time()-t0,1)}
    except Exception as e:
        out["stream_error"]=f"{type(e).__name__}: {e}"
    tots=[r["total_s"] for r in out["runs"]]
    out["summary"]={"total_p50":round(st.median(tots),1),"total_min":min(tots),"total_max":max(tots)}
    return out

@app.local_entrypoint()
def main():
    import json
    for ns in (3, 8):
        r = run_probe.remote(n_seams=ns, iters=5)
        print(f"\n===== CALL-3 PROBE n_seams={ns} =====")
        print(json.dumps(r, indent=1))
