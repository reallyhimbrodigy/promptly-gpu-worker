"""REORDER A/B — does POSITION change plan quality? (Zac 2026-08-02)

THE HYPOTHESIS, and it is specific. HARD CONSTRAINTS — the window rule, the
per-component rules, the variety ceiling, the density caps, i.e. THE PACE SYSTEM
— sits at 91.6% THROUGH THE PREFIX, buried inside the THUMBNAIL header span.
It is the most decision-critical block in the prompt and it is read last.
PROMPTLY_PROMPT_ORDER=v2 moves it to 12.3%, immediately after the preamble.

100% LOSSLESS: the move is a pure permutation of lines, asserted at build time
(the swap raises if the sorted line multiset changes). Zero tokens differ. So any
measured difference is POSITION, not content — which is exactly Zac's attention
theory under test.

READS (plan quality, not tokens):
  window compliance  dominant events (zooms+MGs+transitions) vs the ~2s window
                     ceiling -> dominant_per_2s_window, 1.0 = at the ceiling
  density            all visual events per 25s
  variety            max share of any single zoom type (the rule is <=60%)
  emphasis           emphasis_moments per 25s

ARM c2 IS NON-NEGOTIABLE: control-vs-control em-Jaccard measured 0.516, so two
identical configs agree on only ~52% of emphasis words. An arm that merely
DIFFERS from control proves nothing; it must beat the c1-vs-c2 band.

COST: 3 arms x 16 clips = 48 PLAN_ONLY runs, cpu=8/32GiB, no render.
  ~$4 by the harness per-clip figure; ~$7 recomputing from the resource request.
  Budget against $7.
"""
import os, sys, json
from collections import Counter
sys.path.insert(0, "/")
import modal, modal_app
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-modality-read", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]
CLIPS = [
    ("c0", 'https://d1iax8jos987n3.cloudfront.net/sources/11d10886-8e7d-479d-b313-3007b22004d0/1785553314588-B557ABA6-09CD-47B4-BB56-7D3A59BFADF0_L0_001.mp4'),
    ("c1", 'https://d1iax8jos987n3.cloudfront.net/sources/e3756671-202d-4c67-9a33-97086f759ecc/1785551975768-6D051B2A-ED19-4778-AE4B-2671904314F6_L0_001.mp4'),
    ("c2", 'https://d1iax8jos987n3.cloudfront.net/sources/fc60800e-548c-4d5e-a800-c1092592aff9/1785551189136-95E88B2F-ACED-4D4A-B833-A9B5C44068FE_L0_001.mp4'),
    ("c3", 'https://d1iax8jos987n3.cloudfront.net/sources/63c1b134-0328-40ca-b949-639f5f74d552/1785395111241-D4F29537-8279-477A-948C-63019ACCEB53_L0_001.mp4'),
    ("c4", 'https://d1iax8jos987n3.cloudfront.net/sources/44606c90-6e94-4af3-bdab-473209819d0f/1785394115287-97EA5BBD-DA8E-4953-B2DC-351AC2EB16B7_L0_001.mp4'),
    ("c5", 'https://d1iax8jos987n3.cloudfront.net/sources/f563c015-6ac5-48c8-bf37-32f465706efc/1785393525407-EAB8E057-BE45-438B-9210-9E6003179BE5_L0_001.mp4'),
    ("c6", 'https://d1iax8jos987n3.cloudfront.net/sources/d95a3e0c-b3d8-4232-92c7-fe34c9b14c20/1785393819055-4F11ED19-D6A2-478E-9FEC-247319F3D749_L0_001.mp4'),
    ("c7", 'https://d1iax8jos987n3.cloudfront.net/sources/16eeba22-ac1d-4c83-8fdc-555fd2799a9d/1785393441656-4CD89C65-57DF-48D7-8B30-9C164F061946_L0_001.mp4'),
    ("c8", 'https://d1iax8jos987n3.cloudfront.net/sources/40ead0cd-86c1-4a1f-aee5-5dc308b671c8/1785393377104-417AB7BA-3F72-43B3-82AF-04B0A94C8ADF_L0_001.mp4'),
    ("c9", 'https://d1iax8jos987n3.cloudfront.net/sources/3322e884-af62-4c44-af32-3914e853ed11/1785393253461-28594D0D-DA73-4F5B-B4F5-ADADFAB1380A_L0_001.mp4'),
    ("c10", 'https://d1iax8jos987n3.cloudfront.net/sources/aec9efcb-af3d-4ca0-b950-c5143336e062/1785393091559-C2C582C6-75F2-47C2-97AC-25492477DE48_L0_001.mp4'),
    ("c11", 'https://d1iax8jos987n3.cloudfront.net/sources/01c2fd4c-4921-4e11-8c84-6448229a7961/1785393191173-0319E30A-84A6-4032-977D-900867540EFC_L0_001.mp4'),
    ("c12", 'https://d1iax8jos987n3.cloudfront.net/sources/76b86e26-6721-4899-bb6d-09ced35e6521/1785392878774-C8F5476D-65B5-4939-BFCD-A9965E03D5E1_L0_001.mp4'),
    ("c13", 'https://d1iax8jos987n3.cloudfront.net/sources/a8aa0e76-8d6c-4837-ac32-4e07a8aeccfd/1785392896448-E0388336-1C07-4413-A06C-3699B1E75861_L0_001.mp4'),
    ("c14", 'https://d1iax8jos987n3.cloudfront.net/sources/2e9459fe-91a4-4a6c-89f2-580d0abeb75c/1785392757711-51E40A81-2750-4D25-A350-BBF90BEC1D66_L0_001.mp4'),
    ("c15", 'https://d1iax8jos987n3.cloudfront.net/sources/e14a48db-c40e-432b-9b6e-ed378868b48d/1785392555090-2F75E901-08CF-4C4B-A7BA-6F4F0631B819_L0_001.mp4'),
]



def _read(plan, H, src_dur):
    """Modality split + output size for ONE call, tagged with SOURCE duration so
    every number can be cut at a 60-second source instead of blended."""
    pc = [c for c in H._GEMINI_CALL_LOG
          if "post" in (c.get("label") or "") and not c.get("aborted")]
    if not pc:
        return {"error": "no post-cuts call"}
    c = pc[-1]
    return {"src_dur": src_dur, "modality": c.get("modality"),
            "prompt_tok": c.get("prompt_tok"), "cached_tok": c.get("cached_tok"),
            "out_tok": c.get("out_tok"), "ttfb_s": c.get("ttfb_s"),
            "total_s": c.get("total_s")}


@app.function(secrets=SECRETS, cpu=8.0, memory=32768, region="us", timeout=1800)
def probe(src):
    import uuid
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_PLAN_ONLY"] = "1"
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    body = {"job_id": jid, "video_url": src, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/mod/{jid}.mp4",
            "public_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/mod/{jid}.mp4",
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False}
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:140]}"}
    sd = None
    try:
        sd = ((res or {}).get("stage_timings") or {}).get("source_duration_s")
    except Exception:
        pass
    return _read((res or {}).get("edit_plan"), H, sd)


@app.local_entrypoint()
def main():
    print("MODALITY + OUTPUT READ — item 8 and item 9, one run\n")
    hs = [probe.spawn(src) for _, src in CLIPS[:8]]
    R = [h.get() for h in hs]
    for r in R:
        print(f"  {r}")
    ok = [r for r in R if isinstance(r, dict) and r.get("prompt_tok")]
    if not ok:
        print("\nNO USABLE ROWS"); return
    import statistics as st
    print("\n=== ITEM 8 — MODALITY SPLIT of the input ===")
    agg = {}
    for r in ok:
        for m in (r.get("modality") or []):
            agg.setdefault(m.get("modality") or "?", []).append(m.get("tokens") or 0)
    if not agg:
        print("  prompt_tokens_details EMPTY — the SDK did not return a modality"
              "\n  breakdown on this call. Report as unavailable, do not infer.")
    else:
        for k, v in sorted(agg.items(), key=lambda kv: -st.median(kv[1])):
            print(f"  {k:<12} median {st.median(v):>8,.0f} tok   (n={len(v)})")
    pt = st.median([r["prompt_tok"] for r in ok])
    ct = st.median([r["cached_tok"] or 0 for r in ok])
    print(f"\n  prompt_tok {pt:,.0f} | cached {ct:,.0f} | UNCACHED {pt-ct:,.0f}")
    print("\n=== ITEM 9 — OUTPUT TOKENS PER PLAN ===")
    o = sorted(r["out_tok"] for r in ok if r.get("out_tok"))
    if o:
        print(f"  n={len(o)}  median {st.median(o):,.0f}  p90 {o[int(.9*len(o))-1]:,.0f}  max {o[-1]:,.0f}")
    print("\n=== CUT BY SOURCE DURATION (Zac: report at a 60s source) ===")
    print(f"  {'src_dur':>8} {'uncached':>9} {'out_tok':>8} {'ttfb_s':>7} {'total_s':>8}")
    for r in sorted(ok, key=lambda r: (r.get("src_dur") or 0)):
        u = (r["prompt_tok"] or 0) - (r["cached_tok"] or 0)
        print(f"  {str(r.get('src_dur')):>8} {u:>9,} {r.get('out_tok') or 0:>8,} "
              f"{r.get('ttfb_s'):>7} {r.get('total_s'):>8}")
