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
app = modal.App("plan-ab-reorder", image=image)
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

def _dec(plan):
    if not isinstance(plan, dict):
        return {"error": "no-plan"}
    em = [m for m in (plan.get("emphasis_moments") or []) if isinstance(m, dict)]
    cuts = [c for c in (plan.get("cuts") or []) if isinstance(c, dict)]
    dur = 0.0
    for c in cuts:
        s, e = c.get("source_start"), c.get("source_end")
        if isinstance(s, (int, float)) and isinstance(e, (int, float)) and e > s:
            dur += (e - s)
    zooms = [(m.get("zoom_effect") or {}).get("type") for m in em
             if (m.get("zoom_effect") or {}).get("type")]
    mgs = len(plan.get("motion_graphics") or []) + sum(1 for m in em if m.get("motion_graphic"))
    trans = len(plan.get("transitions") or []) + len(plan.get("tight_cut_overlays") or [])
    dominant = len(zooms) + mgs + trans
    allev = dominant + len(cuts) + len(plan.get("caption_keywords") or []) \
            + len(plan.get("text_overlays") or []) + len(plan.get("broll_clips") or [])
    zc = Counter(zooms)
    return {"dur": round(dur, 1),
            "windows": round(dur / 2.0, 1) if dur else 0,
            # 1.0 = exactly at the one-dominant-event-per-2s-window ceiling
            "window_load": round(dominant / max(1.0, dur / 2.0), 3) if dur else None,
            "events_per25": round(25.0 * allev / dur, 2) if dur else None,
            "emph_per25": round(25.0 * len(em) / dur, 2) if dur else None,
            "zoom_top_share": round(max(zc.values()) / max(1, sum(zc.values())), 3) if zc else None,
            "n_zoom_types": len(zc),
            # BUG FOUND ON THE FIRST RUN: emphasis moments carry `word_indices`
            # (plural, a LIST — StagedPush needs 2-3 of them), not `word_index`.
            # Reading the singular returned None for every moment, so em_words was
            # empty on 48/48 results and _jac's both-empty branch returned 1.0 —
            # which reads as PERFECT AGREEMENT and is actually NO DATA. Any
            # similarity metric must assert it saw something.
            "em_words": sorted({str(w) for m in em
                                for w in (m.get("word_indices")
                                          if isinstance(m.get("word_indices"), list)
                                          else [m.get("word_index")])
                                if w is not None})}

@app.function(secrets=SECRETS, cpu=8.0, memory=32768, region="us", timeout=1800)
def plan(src, order):
    import uuid
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_PLAN_ONLY"] = "1"
    if order: os.environ["PROMPTLY_PROMPT_ORDER"] = order
    else: os.environ.pop("PROMPTLY_PROMPT_ORDER", None)
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    body = {"job_id": jid, "video_url": src, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/reorder/{jid}.mp4",
            "public_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/reorder/{jid}.mp4",
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False}
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:150]}"}
    return _dec((res or {}).get("edit_plan"))

def _jac(x, y):
    sx, sy = set(x), set(y)
    if not sx and not sy:
        return None      # NO DATA — never 1.0, which would read as agreement
    return len(sx & sy) / max(1, len(sx | sy))

@app.local_entrypoint()
def main():
    print(f"=== REORDER A/B: {len(CLIPS)} clips x 3 arms (c1, c2 noise, v2) ===")
    h = {}
    for name, src in CLIPS:
        h[name] = {"c1": plan.spawn(src, ""), "c2": plan.spawn(src, ""),
                   "v2": plan.spawn(src, "v2")}
    R = {n: {k: v.get() for k, v in hs.items()} for n, hs in h.items()}
    ok = lambda d: isinstance(d, dict) and d.get("dur")
    import statistics as st
    print("\n=== PLAN QUALITY per arm (medians) ===")
    print(f"  {'arm':<6} {'n':>3} {'window_load':>12} {'events/25s':>11} {'emph/25s':>9} "
          f"{'zoom_top%':>10} {'#zoomtypes':>11}")
    for a in ("c1", "c2", "v2"):
        rs = [R[n][a] for n in R if ok(R[n][a])]
        if not rs:
            print(f"  {a:<6} (none)"); continue
        med = lambda k: st.median([r[k] for r in rs if r.get(k) is not None]) if any(
            r.get(k) is not None for r in rs) else None
        print(f"  {a:<6} {len(rs):>3} {med('window_load'):>12} {med('events_per25'):>11} "
              f"{med('emph_per25'):>9} {med('zoom_top_share'):>10} {med('n_zoom_types'):>11}")
    d = lambda a, b: round(sum(_jac(R[n][a]["em_words"], R[n][b]["em_words"])
                               for n in R if ok(R[n][a]) and ok(R[n][b]))
                           / max(1, sum(1 for n in R if ok(R[n][a]) and ok(R[n][b]))), 3)
    print(f"\n=== em-Jaccard ===  noise floor c1-vs-c2 = {d('c1','c2')} | v2 vs c1 = {d('c1','v2')}")
    print("READ: v2 must beat the c1-c2 band on window_load / variety to count.")
    _o = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-prompt/52a12dcb-5435-4fe2-9813-8f9fb7279262/scratchpad/reorder_ab.json"
    try:
        os.makedirs(os.path.dirname(_o), exist_ok=True); open(_o, "w").write(json.dumps(R, default=str))
        print(f"raw -> {_o}")
    except Exception as e:
        print(f"(raw dump skipped: {e})")
