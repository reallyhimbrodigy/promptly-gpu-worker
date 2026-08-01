"""PLAN-DECISION A/B (Zac refinements 2026-07-31): one PLAN_ONLY seam, THREE A/Bs.
  • LEAN-SCHEMA  — does removing the telemetry-only rationale prose (+ grounding
    relocated to the thinking channel) shift the plan's decisions?
  • DWELL        — payoff zoom-type distribution: OLD (slow/deep) vs DWELL (land+hold).
  • (compression later rides the same seam.)

n≈16 clips × 4 arms (control, control', lean, dwell). control-vs-control' = the
temperature=1.0 NOISE floor; control-vs-{lean,dwell} = the effect. Reports BOTH
pairwise DISTANCE (Jaccard) and DIRECTIONAL arm-MEANS (component counts, zoom mix,
emphasis density, payoff distribution) — a systematic mean shift is a real effect
even at noise-level pairwise magnitude.

COST (stated honestly): PLAN_ONLY still spins a container through download +
transcribe + Gemini (~380s @cpu=16; this harness uses cpu=8 → ~$0.06-0.09/run).
16 clips × 4 arms = 64 runs ≈ $4-6 — inside the spend law, NOT free. No render.
Coverage-gate OFF so every clip takes the editorial (TH) path and hits the seam.
"""
import os, sys, json
from collections import Counter
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("plan-decision-ab", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"), modal.Secret.from_name("promptly-lang-flags")]

CF = "https://d1iax8jos987n3.cloudfront.net/sources/"
CLIPS = [
    ("clean_93s", CF + "watched-clean/goodEN_93s.mp4"),
    ("goodEN_7513987a", CF + "ec702499-ca10-49e6-8850-df8f99840904/1782599246881-AB653DB0-BCCF-4C67-9910-0355686EC183_L0_001.mp4"),
    ("goodEN_233ef734", CF + "ec702499-ca10-49e6-8850-df8f99840904/1782690788639-64F38CEE-4A5B-4043-ADE1-DD09E2847BC6_L0_001.mp4"),
    ("bg_0909a327", CF + "3a0fe91b-2e6a-4f9a-861d-7d1f60343589/1784898556353-01872AE4-1423-4D62-8E8A-E1B6D5DDEF80_L0_001.mp4"),
    ("bg_b6ca5284", CF + "670ba2a1-c1d3-4f83-a1d1-88a9b029404a/1784679626911-B73364F3-9C55-47E6-8AB6-4082B866A83E_L0_001.mp4"),
    ("bg_e4fddb37", CF + "1eea8ab0-d365-4ff2-9eab-289194932e39/1784925058383-FAAD6F24-94E6-439F-81BE-25E1B87854E6_L0_001.mp4"),
    ("bg_febe1098", CF + "4326653f-927b-4caa-bb51-927a9baffb8e/1784286698284-0093D893-F594-4FBB-900B-4EB519CCF002_L0_001.mp4"),
    ("bg_3045ef1c", CF + "d26f9f96-f38b-486c-99ae-8502030d7ad9/1784274080968-9383B9FD-1F75-4FFC-9689-898BB7B2D3D8_L0_001.mp4"),
    ("bg_de548e46", CF + "ac984a64-b7a4-4362-b60d-ce11714a2b67/1784296682758-C2A2D859-49D2-4238-84B9-04439A4B21E4_L0_001.mp4"),
    ("bg_8b2aed41", CF + "a0290ba1-1bc8-4a6a-ac26-fd33c8d97546/1784271717407-EAF477DD-1BB7-4AFB-913D-41AC99166FC0_L0_001.mp4"),
    ("bg_fede192a", CF + "429257b9-8670-4901-b579-524e37ca465b/1783522440664-EE72C8FD-0F01-40E3-9A8D-7D33004CF570_L0_001.mp4"),
    ("bg_5f2e913f", CF + "618e81dd-a88c-490f-b451-453e8c2cf173/1784564569682-118511E9-FDAE-47FA-A3CD-2447578051BC_L0_001.mp4"),
    ("bg_2b2b93e0", CF + "2460c4ef-4e7a-4533-b4f8-6981b9ae0b11/1784708798937-F540C0F7-92B9-40A9-8536-74AA15320280_L0_001.mp4"),
    ("bg_edc99dda", CF + "59327a64-221a-4539-b37d-eb26ed386f74/1784306340933-C6C6B976-0366-4348-8135-58FCF7C68B97_L0_001.mp4"),
    ("bg_2844f6f7", CF + "7c0278a3-ba9f-4619-9c71-8d5432c28869/1784298291335-849A1595-1E17-46AA-8333-A97708F046E6_L0_001.mp4"),
    ("bg_de52fa48", CF + "51667d23-3916-4552-934d-423d098f1f29/1784282952043-85FAA299-CB11-4A3A-8506-2397205AD640_L0_001.mp4"),
]
SLOW = {"DepthPull", "LetterboxPush", "SmoothPush"}
PUNCHY = {"SnapReframe", "StepZoom", "StagedPush"}
COUNT_KEYS = ["key_moments", "emphasis_moments", "cut_refinements", "motion_graphics",
              "text_overlays", "sound_effects", "transitions", "broll_clips"]


def _decisions(plan):
    if not isinstance(plan, dict):
        return {"error": "no-plan"}
    def wi(m): return m.get("word_index", m.get("word_indices"))
    em = [m for m in (plan.get("emphasis_moments") or []) if isinstance(m, dict)]
    payoff = None
    for m in em:
        ze = m.get("zoom_effect") or {}
        if ze.get("arc_position") == "payoff" and ze.get("type"):
            payoff = ze.get("type"); break
    return {
        "km_words": sorted(str(wi(m)) for m in (plan.get("key_moments") or []) if isinstance(m, dict) and wi(m) is not None),
        "em_words": sorted(str(wi(m)) for m in em if wi(m) is not None),
        "zoom_types": sorted((m.get("zoom_effect") or {}).get("type") for m in em if (m.get("zoom_effect") or {}).get("type")),
        "payoff_zoom": payoff,
        "counts": {k: len(plan.get(k) or []) for k in COUNT_KEYS},
    }


@app.function(secrets=SECRETS, cpu=8.0, memory=32768, region="us", timeout=1800)
def plan(src: str, lean: bool, dwell: bool) -> dict:
    import uuid, traceback
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ["PROMPTLY_PLAN_ONLY"] = "1"
    os.environ["PROMPTLY_COVERAGE_GATE"] = "0"     # take the editorial path for every clip
    os.environ["PROMPTLY_LEAN_SCHEMA"] = "1" if lean else ""
    os.environ["PROMPTLY_DWELL"] = "1" if dwell else ""
    sys.path.insert(0, "/")
    import handler as H
    jid = str(uuid.uuid4())
    body = {"job_id": jid, "video_url": src, "vibe": "Clean engaging edit",
            "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
            "upload_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/plan-ab/{jid}.mp4",
            "public_url": f"https://thisismybucketagainwooo.s3.amazonaws.com/plan-ab/{jid}.mp4",
            "model": "flare", "supports_progressive": False, "premium_pipeline_enabled": False}
    try:
        res = H.handler({"input": body})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:160]}"}
    return _decisions((res or {}).get("edit_plan"))


def _jac(x, y):
    sx, sy = set(x), set(y)
    return len(sx & sy) / max(1, len(sx | sy)) if (sx or sy) else 1.0


def _arm_means(rows):
    rows = [r for r in rows if isinstance(r, dict) and "counts" in r]
    n = max(1, len(rows))
    m = {k: round(sum(r["counts"].get(k, 0) for r in rows) / n, 2) for k in COUNT_KEYS}
    zc = Counter(z for r in rows for z in r["zoom_types"])
    tot = max(1, sum(zc.values()))
    m["zoom_slow_frac"] = round(sum(zc[z] for z in SLOW) / tot, 2)
    m["zoom_punchy_frac"] = round(sum(zc[z] for z in PUNCHY) / tot, 2)
    pc = Counter(r["payoff_zoom"] for r in rows if r.get("payoff_zoom"))
    m["payoff_slow"] = sum(pc[z] for z in SLOW)
    m["payoff_punchy"] = sum(pc[z] for z in PUNCHY)
    m["payoff_dist"] = dict(pc)
    m["n_plans"] = len(rows)
    return m


@app.local_entrypoint()
def main():
    print(f"=== PLAN-DECISION A/B: {len(CLIPS)} clips x 4 arms (control/control'/lean/dwell), planning-only ===")
    h = {}
    for name, src in CLIPS:
        h[name] = {"c1": plan.spawn(src, False, False), "c2": plan.spawn(src, False, False),
                   "lean": plan.spawn(src, True, False), "dwell": plan.spawn(src, False, True)}
    R = {name: {k: v.get() for k, v in hs.items()} for name, hs in h.items()}

    noise, lean_eff, dwell_eff = [], [], []
    for name, r in R.items():
        c1, c2, ln, dw = r["c1"], r["c2"], r["lean"], r["dwell"]
        ok = lambda d: isinstance(d, dict) and "counts" in d
        if ok(c1) and ok(c2):
            noise.append((_jac(c1["km_words"], c2["km_words"]), _jac(c1["em_words"], c2["em_words"])))
        if ok(c1) and ok(ln):
            lean_eff.append((_jac(c1["km_words"], ln["km_words"]), _jac(c1["em_words"], ln["em_words"])))
        if ok(c1) and ok(dw):
            dwell_eff.append((_jac(c1["km_words"], dw["km_words"]), _jac(c1["em_words"], dw["em_words"])))

    def avg(pairs, i): return round(sum(p[i] for p in pairs) / max(1, len(pairs)), 3)
    print("\n=== PAIRWISE DISTANCE (mean Jaccard; higher=more similar) ===")
    print(f"  NOISE  (c vs c') : km={avg(noise,0)} em={avg(noise,1)}  (n={len(noise)})")
    print(f"  LEAN   (c vs lean): km={avg(lean_eff,0)} em={avg(lean_eff,1)}  (n={len(lean_eff)})")
    print(f"  DWELL  (c vs dwell): km={avg(dwell_eff,0)} em={avg(dwell_eff,1)}  (n={len(dwell_eff)})")

    print("\n=== DIRECTIONAL ARM-MEANS (systematic shift = real effect) ===")
    arms = {"control": [R[n]["c1"] for n in R], "lean": [R[n]["lean"] for n in R], "dwell": [R[n]["dwell"] for n in R]}
    means = {a: _arm_means(rows) for a, rows in arms.items()}
    for a, m in means.items():
        print(f"  {a:8}: {json.dumps(m)}")
    print("\n=== DWELL payoff prediction (slow DOWN, punchy UP control->dwell) ===")
    print(f"  control: slow={means['control']['payoff_slow']} punchy={means['control']['payoff_punchy']} dist={means['control']['payoff_dist']}")
    print(f"  dwell  : slow={means['dwell']['payoff_slow']} punchy={means['dwell']['payoff_punchy']} dist={means['dwell']['payoff_dist']}")

    SCR = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad/plan_decision_ab.json"
    open(SCR, "w").write(json.dumps({"raw": R, "means": means}, indent=2, default=str))
    print(f"\nfull → {SCR}")
