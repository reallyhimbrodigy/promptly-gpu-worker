#!/usr/bin/env python3
"""LUMEN FIRST LIGHT — the envelope that sizes the whole campaign [§3.1/§6.1].

Phase 0 steps 4+5. Generates the FIRST Lumen scene assets in the product's
history and measures the three numbers every later phase depends on:

    $/scene · seconds/scene · failure rate over N attempts

WHY THIS RUNS AT ALL, given the code already estimates $0.14/image: that is an
ESTIMATE with "Tune to the confirmed Vertex rate" written next to it, and the
entire Phase 2 design is sized off it. An estimate is not a measurement, and
this campaign's Law 1 says the number is measured, never estimated.

PRICED BEFORE SPENDING [Rule 6 / Law 1]:
    10 attempts x 1 image x $0.14 est   = $1.40
    + alpha probe: 2 attempts x 2 calls = $0.56
    + Modal cpu container ~4 min        ~ $0.02
    ------------------------------------------------
    CEILING ~$2.00. Aborts at the cap rather than overrunning.

BUILD LANE: marks itself, so the EDITORIAL_LIVE gate does not suppress it.
Live user traffic remains on the free path throughout — this app is the only
thing calling the model.

    modal run lumen_first_light_app.py
"""
import json
import os
import sys

# sys.path BEFORE importing modal_app: Modal imports this module inside the
# container too, where modal_app lives at /modal_app.py. Without this the app
# crash-loops at container start — which is exactly what it did.
sys.path.insert(0, "/")

import modal
import modal_app

app = modal.App("lumen-first-light")
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")

# HARD SPEND CEILING. The owner is funding this from a small prepay balance, so
# the run stops itself rather than trusting me to have counted right.
MAX_SPEND_USD = 2.00

# Scene briefs drawn from the REFERENCES, not invented: REF-2's stat callouts
# and evidence cards, REF-1's infographic register.
BRIEFS = [
    ("stat_callout", "A clean full-frame stat callout on a soft lavender-to-white "
                     "gradient: an enormous numeral as the hero element, centred, "
                     "with generous negative space. Editorial, premium, modern."),
    ("evidence_card", "A polaroid-style photo card tilted slightly, with a strip of "
                      "matte tape at the top corner, resting on a clean off-white "
                      "surface. Soft realistic shadow. Documentary evidence look."),
    ("icon_composition", "A closed padlock beside a laptop, rendered as clean 3D "
                         "objects on a plain brand-blue background, soft studio "
                         "lighting, generous space around the objects."),
    ("ui_mockup", "A modern smartphone standing upright on a plain background, "
                  "screen facing forward, clean product-photography lighting."),
    ("infographic", "A simple stylised map shape on a clean white background with "
                    "a few small location pins, flat editorial illustration style."),
]


@app.function(image=image, secrets=[modal.Secret.from_name("promptly-secrets"),
                        modal.Secret.from_name("gemini-vertex"),
                        modal.Secret.from_name("promptly-lang-flags")], timeout=1800, cpu=4, memory=8192)
def first_light(n_attempts: int = 10, alpha_probe: int = 2) -> dict:
    import sys
    import time

    sys.path.insert(0, "/")
    from build_lane import mark_build_lane
    mark_build_lane("lumen_first_light")

    import handler as H

    work = "/tmp/first_light"
    os.makedirs(work, exist_ok=True)
    out = {"model": H._IMAGE_MODEL, "est_per_image": H._IMAGE_COST_USD_EST,
           "attempts": [], "alpha": [], "spend_stopped": False}

    def _spent():
        return (sum(1 for a in out["attempts"] if a.get("called"))
                + sum(a.get("calls", 0) for a in out["alpha"])) * H._IMAGE_COST_USD_EST

    # ── single-image attempts: cost, latency, failure rate
    for i in range(n_attempts):
        if _spent() + H._IMAGE_COST_USD_EST > MAX_SPEND_USD:
            out["spend_stopped"] = True
            break
        kind, prompt = BRIEFS[i % len(BRIEFS)]
        rec = {"i": i, "kind": kind, "called": True}
        t0 = time.time()
        try:
            p = H._generate_image(prompt, out_path=os.path.join(work, f"fl_{i:02d}.png"))
            rec["ok"] = bool(p and os.path.exists(p) and os.path.getsize(p) > 10000)
            rec["bytes"] = os.path.getsize(p) if p and os.path.exists(p) else 0
        except Exception as e:  # noqa: BLE001
            rec["ok"] = False
            rec["err"] = f"{type(e).__name__}: {str(e)[:160]}"
        rec["secs"] = round(time.time() - t0, 2)
        out["attempts"].append(rec)
        print(f"[first-light] {i} {kind} ok={rec.get('ok')} {rec['secs']}s "
              f"{rec.get('err','')}", flush=True)

    # ── alpha probe: a hero cutout costs TWO calls (white + black). Confirm.
    for j in range(alpha_probe):
        if _spent() + 2 * H._IMAGE_COST_USD_EST > MAX_SPEND_USD:
            out["spend_stopped"] = True
            break
        kind, prompt = BRIEFS[(j + 2) % len(BRIEFS)]
        rec = {"j": j, "kind": kind, "calls": 2}
        t0 = time.time()
        try:
            w = H._generate_image(prompt + " Pure WHITE background, no shadow.",
                                  out_path=os.path.join(work, f"al_{j}_w.png"))
            b = H._generate_image(prompt + " Pure BLACK background, no shadow.",
                                  out_path=os.path.join(work, f"al_{j}_b.png"))
            rec["ok"] = all(x and os.path.exists(x) for x in (w, b))
        except Exception as e:  # noqa: BLE001
            rec["ok"] = False
            rec["err"] = f"{type(e).__name__}: {str(e)[:160]}"
        rec["secs"] = round(time.time() - t0, 2)
        out["alpha"].append(rec)
        print(f"[first-light] alpha {j} ok={rec.get('ok')} {rec['secs']}s", flush=True)

    # ── upload the winners so the owner can SEE the first Lumen assets
    try:
        import boto3
        _b = (os.environ.get("SUPABASE_S3_BUCKET") or os.environ.get("S3_BUCKET_NAME") or "")
        if _b:
            s3 = boto3.client("s3")
            for f in sorted(os.listdir(work)):
                if f.endswith(".png") and os.path.getsize(os.path.join(work, f)) > 10000:
                    k = f"lumen-first-light/{f}"
                    s3.upload_file(os.path.join(work, f), _b, k,
                                   ExtraArgs={"ContentType": "image/png"})
                    out.setdefault("uploaded", []).append(k)
    except Exception as e:  # noqa: BLE001
        out["upload_err"] = str(e)[:160]

    ok = [a for a in out["attempts"] if a.get("ok")]
    secs = [a["secs"] for a in out["attempts"] if a.get("ok")]
    out["summary"] = {
        "n": len(out["attempts"]),
        "ok": len(ok),
        "failure_rate": round(1 - (len(ok) / max(1, len(out["attempts"]))), 3),
        "p50_secs": round(sorted(secs)[len(secs) // 2], 2) if secs else None,
        "max_secs": max(secs) if secs else None,
        "est_spend_usd": round(_spent(), 2),
    }
    return out


@app.local_entrypoint()
def main(n: int = 10, alpha: int = 2):
    print(f"=== LUMEN FIRST LIGHT — ceiling ${MAX_SPEND_USD:.2f} ===")
    r = first_light.remote(n_attempts=n, alpha_probe=alpha)
    print(json.dumps(r, indent=2)[:4000])
    s = r.get("summary", {})
    print("\n=== THE ENVELOPE ===")
    print(f"  model            {r.get('model')}")
    print(f"  $/image (est)    ${r.get('est_per_image')}")
    print(f"  attempts         {s.get('n')}  ok={s.get('ok')}  "
          f"failure_rate={s.get('failure_rate')}")
    print(f"  seconds/scene    p50 {s.get('p50_secs')}s   max {s.get('max_secs')}s")
    print(f"  spend this run   ~${s.get('est_spend_usd')}")
    _al = [a for a in r.get("alpha", []) if a.get("ok")]
    if _al:
        print(f"  alpha (2 calls)  p50 {sorted(a['secs'] for a in _al)[len(_al)//2]}s "
              f"=> ${2 * r.get('est_per_image', 0):.2f}/hero-scene")
