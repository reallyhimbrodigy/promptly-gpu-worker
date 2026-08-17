"""TRACK 1 — EDITORIAL MODEL x THINKING MATRIX. Quality AND wall clock per cell.

`[§3.1, Rule 2, Rule 5]`

THE THESIS. Four optional components sit at or near zero:

    generated_scenes   0 / 779 planned jobs
    brand_copy         0 / 198 (100% no_copy_in_plan, design system present on ALL)
    motion graphics    ~62% dropped
    payoff zoom        0 / 253

Every one is the same posture: THE PLANNER DECLINES WHAT IT IS OFFERED. The
mechanisms are proven live — the first full Lumen render carried a design system
(accent #8B350D) and still emitted zero scenes and zero brand copy. So this is
not four wiring bugs. It is one behaviour, and instruction-following fidelity is
the axis aimed at it.

BOTH AXES ARE ALREADY DIALS — no code change is needed to move them:
    model    handler.GEMINI_EDITORIAL_MODEL   (attribute)
    thinking PROMPTLY_POST_THINKING_BUDGET    (env; a dark A/B knob since
                                               2026-07-31, default 24576)

THE LATENCY AXIS COSTS NOTHING EXTRA and is now load-bearing. The first Lumen
render measured `editorial_plan = 97.1s` — 54.3% of a 178.8s wall that misses the
120s law by 59s. Whatever this matrix says about quality, the wall clock per cell
decides whether the answer is affordable.

PLAN-ONLY, DELIBERATELY. The render adds ~72s and ~$0.50 per cell and cannot
change what the PLANNER emits. Every metric here is read off the plan.

WHAT IS MEASURED PER CELL
    wall_s        the editorial call only — the latency axis
    scenes        len(generated_scenes)
    brand_copy    did the model emit it at all (the 0/198 class)
    mg            len(motion_graphics)
    payoff        emphasis moments whose zoom_effect claims arc_position=payoff
    emphasis / transitions / broll   richness, to catch a model that simply
                  emits less of everything rather than more of the rare things
    notes         the honor-or-note text. BOTH rewritten directives require an
                  explicit reason when a matching beat is declined, so this is
                  the most direct evidence of instruction-following available.

A CONFOUND, STATED RATHER THAN HIDDEN. Both directives were rewritten
condition-bound hours before this ran, so a model difference here is measured
against the NEW prompt, not the one the 0/779 and 0/198 numbers came from. The
scenes directive is flag-gated (PROMPTLY_SCENES_DIRECTIVE_V2), so the prompt axis
is switchable; brand_copy's rewrite is unconditional and would need its old text
restored to isolate. This run holds the prompt CONSTANT (v2 on) and varies model
x thinking only — so it answers "which model/effort follows the NEW instruction
best", NOT "was it the model or the prompt".

PRICED: ~$1.20 for six cells on one reference. One container per cell, plan only,
no render, no image generation (scenes at zero generate nothing).

    modal run ab_matrix_app.py
"""
import json
import os
import sys

import modal

sys.path.insert(0, "/")

import modal_app as _prod  # noqa: E402

app = modal.App("ab-editorial-matrix")

_IMAGE = _prod.image.add_local_file("modal_app.py", "/modal_app.py")

REF = "golden/lumen-refs/ref2-viral-creator-doc-vertical.mp4"

# 2 models x 3 thinking budgets. 24576 is production's current default (the
# control); 0 tests whether thinking is load-bearing at all; 60000 was the prior
# cap and tests whether MORE effort buys the declined components.
MODELS = ["gemini-3.1-pro-preview", "gemini-3.7-flash"]
THINKING = [0, 24576, 60000]


@app.function(image=_IMAGE, cpu=8, memory=16384, timeout=1800,
              secrets=[modal.Secret.from_name("promptly-secrets"),
                       modal.Secret.from_name("gemini-vertex"),
                       modal.Secret.from_name("promptly-lang-flags")])
def cell(spec: dict) -> dict:
    import time as _t
    import traceback as _tb

    sys.path.insert(0, "/")
    import build_lane as _bl
    _bl.mark_build_lane()                       # opens the editorial gate IN-LANE
    os.environ["PREMIUM_PIPELINE_ENABLED"] = "1"
    os.environ["PROMPTLY_SCENES_DIRECTIVE_V2"] = "1"   # prompt held CONSTANT
    os.environ["PROMPTLY_POST_THINKING_BUDGET"] = str(spec["thinking"])

    import handler as H
    H.GEMINI_EDITORIAL_MODEL = spec["model"]     # the model axis

    out = {"model": spec["model"], "thinking": spec["thinking"],
           "build_sha": os.environ.get("PROMPTLY_BUILD_SHA", "")[:12], "ok": False}
    src = "/tmp/ab_src.mp4"
    try:
        with open(src, "wb") as f:
            f.write(spec["source_bytes"])
        dur = H.probe_duration(src)
        tr = H.transcribe_audio(src, keywords=None, language="multi") or {}
        words = tr.get("words") or []
        with open(src, "rb") as f:
            vbytes = f.read()

        t0 = _t.monotonic()
        plan = H.generate_edit_gemini(
            src, vibe="make it viral", duration=dur, trend_context=None,
            deepgram_words=words, shot_changes=None, shot_change_scores=None,
            vocal_emphasis=None, source_loudness=None, face_positions=None,
            smoothed_face_trajectory=None, user_style_profile=None,
            premium=True, inline_video_bytes=vbytes)
        out["wall_s"] = round(_t.monotonic() - t0, 1)
        p = plan or {}

        ems = p.get("emphasis_moments") or []
        def _arc(e):
            z = (e or {}).get("zoom_effect") or {}
            return str(z.get("arc_position") or "")
        out.update({
            "ok": True,
            "scenes": len(p.get("generated_scenes") or []),
            "brand_copy_emitted": bool(p.get("brand_copy")),
            "brand_specs_built": {k: bool(v) for k, v in
                                  ((p.get("_brand_specs") or {}) or {}).items()},
            "mg": len(p.get("motion_graphics") or []),
            "payoff": sum(1 for e in ems if _arc(e) == "payoff"),
            "emphasis": len(ems),
            "transitions": len(p.get("transitions") or []),
            "broll": len(p.get("broll_clips") or []),
            "cuts": len(p.get("cuts") or []),
            "notes": str(p.get("notes") or "")[:600],
            "accent": ((p.get("_design_system") or {}).get("palette") or {}).get("accent"),
        })
        print(f"[cell] {spec['model']} think={spec['thinking']} "
              f"wall={out['wall_s']}s scenes={out['scenes']} "
              f"brand={out['brand_copy_emitted']} mg={out['mg']} "
              f"payoff={out['payoff']}", flush=True)
    except BaseException as e:   # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        try:
            for fr in reversed(_tb.extract_tb(e.__traceback__)):
                fn = str(fr.filename or "")
                if "/site-packages/" in fn or "/usr/lib/" in fn:
                    continue
                out["frame"] = f"{fn.rsplit('/',1)[-1]}:{fr.lineno} in {fr.name}()"
                break
        except Exception:
            pass
        print(f"[cell] {spec['model']} think={spec['thinking']} FAILED "
              f"{out['error']} @ {out.get('frame')}", flush=True)
    return out


@app.local_entrypoint()
def main(source_path: str = REF):
    with open(source_path, "rb") as f:
        b = f.read()
    specs = [{"model": m, "thinking": t, "source_bytes": b}
             for m in MODELS for t in THINKING]
    print(f"=== TRACK 1 MATRIX — {len(specs)} cells, priced ~$1.20 ===")
    print(f"    source: {os.path.basename(source_path)} ({len(b)/1e6:.1f}MB)")
    print(f"    prompt HELD CONSTANT (scenes v2 ON) — model x thinking only\n")
    res = list(cell.map(specs))

    print("\n" + "=" * 92)
    print(f"{'model':26} {'think':>7} {'wall_s':>8} {'scenes':>7} {'brand':>6} "
          f"{'mg':>4} {'payoff':>7} {'emph':>5} {'cuts':>5}")
    print("=" * 92)
    for r in res:
        if not r.get("ok"):
            print(f"{r['model']:26} {r['thinking']:>7}   FAILED  {str(r.get('error'))[:44]}")
            continue
        print(f"{r['model']:26} {r['thinking']:>7} {r['wall_s']:>8} {r['scenes']:>7} "
              f"{str(r['brand_copy_emitted']):>6} {r['mg']:>4} {r['payoff']:>7} "
              f"{r['emphasis']:>5} {r['cuts']:>5}")
    ok = [r for r in res if r.get("ok")]
    print("\n  THE FOUR DECLINED CLASSES — did any cell lift one off zero?")
    for k, label in (("scenes", "generated_scenes"), ("payoff", "payoff zoom")):
        best = max((r[k] for r in ok), default=0)
        print(f"    {label:18} best across all cells: {best}"
              + ("   <- STILL ZERO" if best == 0 else "   <- LIFTED"))
    anybrand = [r for r in ok if r.get("brand_copy_emitted")]
    print(f"    brand_copy         emitted in {len(anybrand)}/{len(ok)} cells"
          + ("   <- STILL ZERO" if not anybrand else "   <- LIFTED"))
    if ok:
        fastest = min(ok, key=lambda r: r["wall_s"])
        print(f"\n  LATENCY: fastest cell {fastest['model']} think={fastest['thinking']} "
              f"-> {fastest['wall_s']}s (production baseline 97.1s @ 3.1-pro/24576)")
    print("\n  NOTES (honor-or-note evidence — a declined beat must state why):")
    for r in ok:
        if r.get("notes"):
            print(f"    [{r['model']} t={r['thinking']}] {r['notes'][:200]}")
    print(json.dumps(res, default=str)[:1500])
