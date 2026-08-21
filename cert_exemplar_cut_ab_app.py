#!/usr/bin/env python3
"""cert_exemplar_cut_ab_app.py — DOES CUTTING THE WORKED EXAMPLES COST QUALITY?

THE MEASUREMENT THAT ORDERED THIS. The assembled editorial instruction is
~178,000 chars. Broken down properly:

    MOTION GRAPHICS   35,513  (19.9%)   catalog
    MOVEMENTS         33,352  (18.7%)   doctrine
    B-ROLL            18,184  (10.2%)   catalog
    WORKED EXAMPLES   16,568  ( 9.3%)   EXEMPLARS  <- this cell
    EMPHASIS+ZOOM     14,204  ( 8.0%)
    SOUND EFFECTS     11,784  ( 6.6%)
    CAPTIONS          10,106  ( 5.7%)
    THUMBNAIL          1,369  ( 0.8%)

(THUMBNAIL was first mis-measured at 17,937 chars because WORKED EXAMPLES sits
between it and the next `=== X ===` marker under a box-rule header. THUMBNAIL is
in fact the most efficient block in the prompt: six lines for the cover frame.)

WORKED EXAMPLES is the largest EXEMPLAR block — four fully worked edits. Cutting
exemplars is the classic condensation move and the classic condensation
disaster, because exemplars teach the WHOLE recipe rather than one field. So
this cell measures BOTH halves, and quality is the half that decides:

    SPEED    — prompt tokens, and the Gemini leg wall
    QUALITY  — cuts, emphasis, motion graphics BY TYPE, overlays, zooms, SFX,
               b-roll, thumbnail index, and the model's own rationale

THE CONFOUND, NAMED SO NO ARM IS READ NAIVELY. The system prompt is deliberately
byte-identical across jobs so Gemini's IMPLICIT CACHE hits. Arm B changes the
prefix, so its FIRST call pays a cold cache that arm A does not. A single A/B
pair therefore measures cache state as much as prompt length. This runs each arm
TWICE and reports both; read the SECOND call of each, and treat the first pair
as a lower bound on the cut's benefit.

PLAN_ONLY: the render is spied out, so nothing renders and nothing uploads. One
source, one vibe, one variable. ~$0.10-0.15/cell x 4 cells = ~$0.40-0.60.

    modal run cert_exemplar_cut_ab_app.py
"""
import os
import sys

sys.path.insert(0, "/")
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-exemplar-cut-ab", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]
SRC = ("https://d1iax8jos987n3.cloudfront.net/sources/"
       "e9b47b30-5edf-4bc6-825a-7d2a8fe1a43d/"
       "1785239363288-A2A4B085-5918-4575-BB13-CC3CD92EF816_L0_001.mp4")


@app.function(secrets=SECRETS, cpu=16.0, memory=49152, timeout=2400)
def run() -> dict:
    import time
    import uuid
    import traceback
    import collections
    from build_lane import mark_build_lane
    mark_build_lane("cert_exemplar_cut_ab_app.py")
    os.environ["APP_URL"] = ""
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    os.environ.pop("PROMPTLY_CUT_EXEMPLARS", None)   # per-arm ONLY
    sys.path.insert(0, "/")
    import handler as H
    RESULT = {"arms": {}, "wall": {}}

    class _CaptureDone(BaseException):
        pass

    _orig_render = H.render_multi_clip
    _cur = {"arm": None}

    # Capture the ASSEMBLED prompt length per arm at the seam that builds it,
    # so the cut is proven to have happened rather than assumed from the flag.
    _seen = {}
    _orig_cut = H._cut_worked_examples

    def _cut_spy(txt):
        out = _orig_cut(txt)
        _seen[_cur["arm"]] = {"pre": len(txt or ""), "post": len(out or "")}
        return out
    H._cut_worked_examples = _cut_spy

    def _spy(*args, **kwargs):
        cuts, edit_plan = args[1], args[2]
        p = edit_plan if isinstance(edit_plan, dict) else {}
        em = p.get("emphasis_moments") or []
        mgs = [e.get("motion_graphic") for e in em
               if isinstance(e, dict) and e.get("motion_graphic")]
        mg_types = collections.Counter(
            str(m.get("type")) for m in mgs if isinstance(m, dict))
        calls = [c for c in getattr(H, "_GEMINI_CALL_LOG", []) if isinstance(c, dict)]
        RESULT["arms"][_cur["arm"]] = {
            "prompt_chars": _seen.get(_cur["arm"]),
            "tokens": H._gemini_token_summary(),
            "gemini_leg_s": round(sum(c.get("total_s") or 0 for c in calls
                                      if not c.get("aborted")), 1),
            "n_calls": len(calls),
            # ── QUALITY ──────────────────────────────────────────────────────
            "n_cuts": len(cuts or []),
            "n_emphasis": len(em),
            "n_motion_graphic": len(mgs),
            "mg_types": dict(mg_types),
            "n_text_overlays": len(p.get("text_overlays") or []),
            "n_zoom": sum(1 for c in (cuts or []) if c.get("_zoom_effect")),
            "n_sfx": len(p.get("sound_effects") or []),
            "n_broll": len(p.get("broll_clips") or p.get("broll") or []),
            "n_transitions": len(p.get("transitions") or []),
            "thumbnail_word_index": p.get("thumbnail_word_index"),
            "edit_rationale": str(p.get("edit_rationale") or "")[:340],
            "post_hook": str(p.get("post_hook") or "")[:90],
        }
        raise _CaptureDone()

    H.render_multi_clip = _spy
    # control, cut, control#2, cut#2 — interleaved so a drift in Vertex latency
    # over the run cannot masquerade as an arm effect.
    for arm, cut_on in [("control_1", False), ("cut_1", True),
                        ("control_2", False), ("cut_2", True)]:
        _cur["arm"] = arm
        if cut_on:
            os.environ["PROMPTLY_CUT_EXEMPLARS"] = "1"
        else:
            os.environ.pop("PROMPTLY_CUT_EXEMPLARS", None)
        try:
            H._GEMINI_CALL_LOG.clear()
        except Exception:
            pass
        jid = str(uuid.uuid4())
        url = (f"https://thisismybucketagainwooo.s3.amazonaws.com/"
               f"exemplar-cut/{arm}/{jid}/out.mp4")
        body = {"job_id": jid, "video_url": SRC,
                "vibe": "High-energy viral edit with punchy zooms and emphasis",
                "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
                "upload_url": url, "public_url": url, "model": "flare",
                "supports_progressive": False, "premium_pipeline_enabled": False,
                "mode": "full"}
        t0 = time.time()
        try:
            H.handler({"input": body})
        except _CaptureDone:
            pass
        except Exception as e:
            RESULT["arms"][arm] = {"err": f"{type(e).__name__}: {str(e)[:300]}",
                                   "tb": traceback.format_exc()[-800:]}
        RESULT["wall"][arm] = round(time.time() - t0, 1)
    H.render_multi_clip = _orig_render
    H._cut_worked_examples = _orig_cut
    return RESULT


@app.local_entrypoint()
def main():
    print("=== EXEMPLAR CUT A/B — WORKED EXAMPLES (16,568 chars, 9.3%) ===")
    print("    PLAN_ONLY. Each arm runs TWICE: arm B's first call pays a cold")
    print("    implicit cache that arm A does not. Read the SECOND of each.\n")
    o = run.remote() or {}
    a = o.get("arms", {})
    ARMS = ("control_1", "cut_1", "control_2", "cut_2")
    for arm in ARMS:
        d = a.get(arm, {})
        print(f"\n[{arm}]  pipeline_wall={o.get('wall', {}).get(arm)}s")
        if d.get("err"):
            print("  ERROR:", d["err"])
            print("  tb:", d.get("tb", ""))
            continue
        pc = d.get("prompt_chars")
        if pc:
            delta = pc["pre"] - pc["post"]
            print(f"  prompt: {pc['pre']:,} -> {pc['post']:,} chars "
                  f"({-delta:+,}, {-100*delta/max(1,pc['pre']):+.2f}%)"
                  + ("   ** NO CUT APPLIED **" if delta == 0 and "cut" in arm else ""))
        elif "cut" in arm:
            print("  ** the cutter never ran — this is NOT a cut arm **")
        t = d.get("tokens") or {}
        print(f"  tokens: prompt={t.get('prompt')} uncached_delta="
              f"{t.get('uncached_delta')} out={t.get('output')} "
              f"(n_calls={d.get('n_calls')})")
        print(f"  GEMINI LEG: {d.get('gemini_leg_s')}s")
        print(f"  QUALITY  cuts={d.get('n_cuts')} emphasis={d.get('n_emphasis')} "
              f"mg={d.get('n_motion_graphic')} {d.get('mg_types')}")
        print(f"           overlays={d.get('n_text_overlays')} "
              f"zooms={d.get('n_zoom')} sfx={d.get('n_sfx')} "
              f"broll={d.get('n_broll')} transitions={d.get('n_transitions')} "
              f"thumb_idx={d.get('thumbnail_word_index')}")
        print(f"           rationale: {d.get('edit_rationale')}")
        print(f"           hook: {d.get('post_hook')}")

    print("\n" + "=" * 66)
    A2, B2 = a.get("control_2", {}), a.get("cut_2", {})
    A1, B1 = a.get("control_1", {}), a.get("cut_1", {})
    if A2.get("tokens") and B2.get("tokens"):
        pa, pb = A2["tokens"].get("prompt") or 0, B2["tokens"].get("prompt") or 0
        if pa:
            print(f"  TOKENS   {pa} -> {pb} ({100*(pa-pb)/pa:+.1f}%)  "
                  f"<- proves the cut reached the model")
        for lbl, X, Y in (("1st pair (cold cache for B)", A1, B1),
                          ("2nd pair (both warm)", A2, B2)):
            ga, gb = X.get("gemini_leg_s"), Y.get("gemini_leg_s")
            if ga and gb:
                print(f"  GEMINI   {lbl:28} {ga}s -> {gb}s ({gb-ga:+.1f}s, "
                      f"{100*(gb-ga)/ga:+.1f}%)")
        print("\n  QUALITY (the half that decides):")
        for k in ("n_cuts", "n_emphasis", "n_motion_graphic", "n_text_overlays",
                  "n_zoom", "n_sfx", "n_broll", "n_transitions"):
            va, vb = A2.get(k), B2.get(k)
            if va is None and vb is None:
                continue
            flag = ""
            if isinstance(va, int) and isinstance(vb, int) and va:
                d = (vb - va) / va * 100
                flag = "   <-- COLLAPSE" if d <= -40 else ("   <-- surge" if d >= 60 else "")
            print(f"    {k:<20} {va} -> {vb}{flag}")
        print(f"    {'mg_types':<20} {A2.get('mg_types')} -> {B2.get('mg_types')}")
        print("\n  READ: exemplars teach the WHOLE recipe. A token/latency win "
              "that costs\n        component density or grounding is NOT a win — "
              "quality wins over speed.")
    print("\nEXEMPLAR CUT A/B COMPLETE.")
