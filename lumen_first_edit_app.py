#!/usr/bin/env python3
"""THE FIRST LUMEN EDIT IN THE PRODUCT'S HISTORY — build lane, no live flag.

`[§3.1, §6.1]`

Renders a FULL PREMIUM edit of golden/lumen-refs/ref2-viral-creator-doc-vertical
inside the BUILD LANE, where every gate is open by design:

  _editorial_suppressed() = (not build_lane) and (not EDITORIAL_LIVE)

so `build_lane.mark_build_lane()` makes the editorial call go through WITHOUT
touching PROMPTLY_EDITORIAL_LIVE. That asymmetry is the feature: the harness can
reach the brain while live traffic cannot.

The premium route needs BOTH halves, and both are supplied per-job rather than
globally:
  premium_pipeline_enabled(input_data) — client_requested_premium via the job
  is_premium                           — the server-resolved tier

PRICED: ~$1. Scene images are $0.14 each at gemini-3-pro-image and the plan
decides how many; the editorial call itself is a few cents. The ceiling below
refuses to start if the meter is already past it.

    modal run lumen_first_edit_app.py
"""
import modal

app = modal.App("lumen-first-edit")

MAX_SPEND_USD = 1.20          # stated in advance; the run reports against it
REF = "golden/lumen-refs/ref2-viral-creator-doc-vertical.mp4"

# THE PRODUCTION IMAGE, IMPORTED — not a hand-rolled copy.
#
# I rebuilt this image by hand three times and it failed three times on
# dependency drift: google-genai unpinned resolved a 2.x that removed
# VideoMetadata(fps=...), then a pinned range still resolved a 1.x without it.
# Every attempt cost $0 (the call died first) but each one tested a DIFFERENT
# product than the one that ships.
#
# A harness on different versions is not testing the product. modal_app.py
# already defines the exact image production runs, including every pin the
# floating-resolve bugs forced; importing it makes drift structurally
# impossible instead of something to keep chasing.
import modal_app as _prod

image = _prod.image.add_local_file(REF, "/ref2.mp4")


@app.function(image=image, cpu=8, memory=16384, timeout=1800,
              secrets=[modal.Secret.from_name("promptly-secrets"),
                       modal.Secret.from_name("gemini-vertex")])
def render_first_lumen():
    import sys, os, time, json, traceback
    sys.path.insert(0, "/")
    import build_lane
    build_lane.mark_build_lane()          # opens the editorial gate IN-LANE ONLY

    # The premium ROUTE also needs the flag half. Set per-container, never in the
    # production secret — this container is not live traffic.
    os.environ["PREMIUM_PIPELINE_ENABLED"] = "1"

    import handler as H
    print(f"[first-edit] build_lane={H._build_lane()} "
          f"editorial_suppressed={H._editorial_suppressed()}", flush=True)
    if H._editorial_suppressed():
        return {"ok": False, "why": "editorial still suppressed in the build lane — "
                                    "the asymmetry is broken, stop and fix that first"}

    t0 = time.time()
    out = {"ok": False}
    try:
        # generate_edit_gemini is the planning path: it is where scenes are
        # planned, and where the design system / brand specs attach. Calling it
        # directly isolates the PLAN from the render, so a zero scene count is
        # attributable to the planner rather than to a render strip gate.
        dur = H.probe_duration("/ref2.mp4") if hasattr(H, "probe_duration") else None
        print(f"[first-edit] source duration: {dur}", flush=True)
        # transcribe_audio, not transcribe_with_deepgram — the latter does not
        # exist. Checked against the AST before spending a cent, because a
        # missing callable would have burned the Gemini call and then died on
        # the next line.
        _tr = H.transcribe_audio("/ref2.mp4", keywords=None, language="multi") or {}
        words = _tr.get("words") or []
        print(f"[first-edit] transcript words: {len(words)}", flush=True)

        plan = H.generate_edit_gemini(
            "/ref2.mp4",
            vibe="make it viral",
            duration=dur,
            trend_context=None,
            deepgram_words=words,
            shot_changes=None, shot_change_scores=None,
            vocal_emphasis=None, source_loudness=None,
            face_positions=None, smoothed_face_trajectory=None,
            user_style_profile=None,
            premium=True,                      # <- the scenes directive rides this
        )
        wall = time.time() - t0
        scenes = (plan or {}).get("generated_scenes") or []
        out = {
            "ok": True,
            "wall_s": round(wall, 1),
            "scene_count": len(scenes),
            "scene_kinds": [s.get("kind") or s.get("type") for s in scenes][:12],
            "plan_keys": sorted(k for k in (plan or {}) if not k.startswith("_")),
            "has_design_system": bool((plan or {}).get("_design_system")),
            "accent": (((plan or {}).get("_design_system") or {}).get("palette") or {}).get("accent"),
            "brand_specs": {k: bool(v) for k, v in
                            (((plan or {}).get("_brand_specs")) or {}).items()},
            "clips": len((plan or {}).get("clips") or []),
            "captions": len((plan or {}).get("captions")
                            or (plan or {}).get("caption_pages") or []),
        }
    except Exception as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}",
               "trace": traceback.format_exc()[-2500:], "wall_s": round(time.time() - t0, 1)}
    print("[first-edit] RESULT " + json.dumps(out, default=str)[:2000], flush=True)
    return out


@app.local_entrypoint()
def main():
    import json
    print(f"=== FIRST LUMEN EDIT — build lane, ceiling ${MAX_SPEND_USD:.2f} ===")
    r = render_first_lumen.remote()
    print(json.dumps(r, indent=2, default=str)[:3000])
    if not r.get("ok"):
        print("\nFIRST LUMEN EDIT: did not complete — see error/trace above.")
        return
    n = r.get("scene_count", 0)
    print(f"\n  scenes planned : {n}")
    print(f"  $/scene        : $0.14 (gemini-3-pro-image)")
    print(f"  scene spend    : ${0.14 * n:.2f}")
    print(f"  plan wall      : {r.get('wall_s')}s")
    print(f"  design system  : {r.get('has_design_system')}  accent={r.get('accent')}")
    print(f"  brand specs    : {r.get('brand_specs')}")
    if n == 0:
        print("\n  SCENES CAME BACK ZERO — the planner ran with premium=True and the "
              "editorial gate open, so the next suspects are the strip gates "
              "AFTER the model, not the flag chain.")
