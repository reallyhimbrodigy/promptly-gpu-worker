"""thinking_budget LATENCY A/B (Zac 2026-08-02): the editorial post-cuts Gemini
call is ~44% of the median e2e. thinking_budget is a PURE LATENCY knob (Zac) — the
comment at handler.py:1822 says ~135s at 24576 scaling ~linearly. Sweep it across
the 16 REAL coverage-passing TH clips (plan_ab_propern's corpus), PLAN_ONLY, and
report gemini_call_s per level. Properly powered: N=16 per level.

Levels: 24576 (current) / 12288 / 6144 / 2048 / 0. ~16x5 plan calls, ~$5-7.
HOLDING the proxy 480p->360p downscale — that's a quality change, needs its own arm.

  modal run cert_thinking_budget_app.py"""
import os, sys, json
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-thinking-budget", image=image)
SECRETS = [modal.Secret.from_name(s) for s in
           ("promptly-secrets", "promptly-cloudfront", "gemini-vertex", "promptly-lang-flags")]
# same 16 real coverage-passing TH clips as plan_ab_propern
CLIPS = [
    ('https://d1iax8jos987n3.cloudfront.net/sources/11d10886-8e7d-479d-b313-3007b22004d0/1785553314588-B557ABA6-09CD-47B4-BB56-7D3A59BFADF0_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/e3756671-202d-4c67-9a33-97086f759ecc/1785551975768-6D051B2A-ED19-4778-AE4B-2671904314F6_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/fc60800e-548c-4d5e-a800-c1092592aff9/1785551189136-95E88B2F-ACED-4D4A-B833-A9B5C44068FE_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/63c1b134-0328-40ca-b949-639f5f74d552/1785395111241-D4F29537-8279-477A-948C-63019ACCEB53_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/44606c90-6e94-4af3-bdab-473209819d0f/1785394115287-97EA5BBD-DA8E-4953-B2DC-351AC2EB16B7_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/f563c015-6ac5-48c8-bf37-32f465706efc/1785393525407-EAB8E057-BE45-438B-9210-9E6003179BE5_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/d95a3e0c-b3d8-4232-92c7-fe34c9b14c20/1785393819055-4F11ED19-D6A2-478E-9FEC-247319F3D749_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/16eeba22-ac1d-4c83-8fdc-555fd2799a9d/1785393441656-4CD89C65-57DF-48D7-8B30-9C164F061946_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/40ead0cd-86c1-4a1f-aee5-5dc308b671c8/1785393377104-417AB7BA-3F72-43B3-82AF-04B0A94C8ADF_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/3322e884-af62-4c44-af32-3914e853ed11/1785393253461-28594D0D-DA73-4F5B-B4F5-ADADFAB1380A_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/aec9efcb-af3d-4ca0-b950-c5143336e062/1785393091559-C2C582C6-75F2-47C2-97AC-25492477DE48_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/01c2fd4c-4921-4e11-8c84-6448229a7961/1785393191173-0319E30A-84A6-4032-977D-900867540EFC_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/76b86e26-6721-4899-bb6d-09ced35e6521/1785392878774-C8F5476D-65B5-4939-BFCD-A9965E03D5E1_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/a8aa0e76-8d6c-4837-ac32-4e07a8aeccfd/1785392896448-E0388336-1C07-4413-A06C-3699B1E75861_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/2e9459fe-91a4-4a6c-89f2-580d0abeb75c/1785392757711-51E40A81-2750-4D25-A350-BBF90BEC1D66_L0_001.mp4'),
    ('https://d1iax8jos987n3.cloudfront.net/sources/e14a48db-c40e-432b-9b6e-ed378868b48d/1785392555090-2F75E901-08CF-4C4B-A7BA-6F4F0631B819_L0_001.mp4'),
]
LEVELS = [24576, 12288, 6144, 2048, 0]


@app.function(secrets=SECRETS, cpu=8.0, memory=32768, region="us", timeout=1800)
def plan(src, budget):
    import uuid
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_PLAN_ONLY"] = "1"
    os.environ["PROMPTLY_POST_THINKING_BUDGET"] = str(budget)
    import handler as H
    jid = str(uuid.uuid4())
    body = {"job_id": jid, "video_url": src, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/tb-ab/{jid}.mp4",
            "public_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/tb-ab/{jid}.mp4",
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False}
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:150]}"}
    out = {"budget": budget}
    try:
        pc = [c for c in H._GEMINI_CALL_LOG if "post" in (c.get("label") or "") and not c.get("aborted")]
        if pc:
            c = pc[-1]
            out["gemini_call_s"] = c.get("total_s"); out["ttfb_s"] = c.get("ttfb_s"); out["out_tok"] = c.get("out_tok")
    except Exception:
        pass
    ep = (res or {}).get("edit_plan") or {}
    out["n_cuts"] = len(ep.get("cuts") or [])
    out["n_em"] = len(ep.get("emphasis_moments") or [])
    return out


@app.local_entrypoint()
def main():
    import statistics as st
    print(f"=== thinking_budget LATENCY sweep: {len(CLIPS)} clips x {len(LEVELS)} levels ===")
    h = {b: [plan.spawn(src, b) for src in CLIPS] for b in LEVELS}
    R = {b: [f.get() for f in fs] for b, fs in h.items()}
    print(f"\n  {'budget':>8} {'gemini_s p50':>13} {'gemini_s mean':>14} {'ttfb p50':>9} {'out_tok':>8} {'n':>3}  vs24576")
    base = None
    for b in LEVELS:
        rs = [r for r in R[b] if isinstance(r, dict) and r.get("gemini_call_s")]
        if not rs:
            print(f"  {b:>8}  (no telemetry, {sum(1 for r in R[b] if isinstance(r,dict) and r.get('error'))} errors)"); continue
        g = [r["gemini_call_s"] for r in rs]; tt = [r.get("ttfb_s") or 0 for r in rs]; ot = [r.get("out_tok") or 0 for r in rs]
        p50 = st.median(g); mean = sum(g) / len(g)
        if base is None: base = p50
        print(f"  {b:>8} {p50:>13.1f} {mean:>14.1f} {st.median(tt):>9.1f} {sum(ot)/len(ot):>8,.0f} {len(rs):>3}  {p50-base:+.1f}s")
    print("\n→ thinking_budget is pure latency (Zac). Lower budget that holds gemini_s down"
          " with stable cuts/em = free plan latency on EVERY clip (the median lever).")
