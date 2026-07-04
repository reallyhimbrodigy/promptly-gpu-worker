"""F8 — pre-captioned sources: double-caption prevention + band clamping.
Same 3-stub harness as test_mg_truth (kept-index plans, terminal raises off)."""
import contextlib
import copy
import io
import os

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


WORDS = [{"word": t, "punctuated_word": t, "start": round(i * 0.4, 2),
          "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
         for i, t in enumerate(["people", "upload", "your", "video", "type", "uh",
                                "vibe", "hit", "send", "its", "completely", "free"])]
CUT_PLAN = {"remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}


def clean_plan(**over):
    p = {
        "caption_style": "Lumen", "caption_keywords": ["upload"],
        "video_identity": "A creator pitching an app from their desk.",
        "existing_caption_region": "none",
        "transitions": [], "tight_cut_overlays": [],
        "motion_graphics": [], "emphasis_moments": [], "text_overlays": [],
        "broll_clips": [], "sound_effects": [],
        "audio_denoise": False, "outro": "none", "aspect_ratio": "9:16",
    }
    p.update(over)
    return p


def run_gen(plan, vibe="make it viral"):
    saved = {k: getattr(H, k) for k in
             ("compute_mechanical_cuts", "_call_gemini_post_cuts", "_get_genai_client")}
    safe_saved = os.environ.pop("SAFE_EDIT_FALLBACK_ENABLED", None)
    os.environ["SAFE_EDIT_FALLBACK_ENABLED"] = "0"
    H.compute_mechanical_cuts = lambda w, source_path=None: copy.deepcopy(CUT_PLAN)
    H._call_gemini_post_cuts = lambda c, s, u, v, m: copy.deepcopy(plan)
    H._get_genai_client = lambda: None
    buf = io.StringIO()
    err = None
    out = None
    try:
        with contextlib.redirect_stdout(buf):
            out = H.generate_edit_gemini(
                video_path="/nonexistent.mp4", vibe=vibe, duration=4.8,
                deepgram_words=copy.deepcopy(WORDS),
                inline_video_bytes=b"fakevideo", premium=False)
    except Exception as e:
        err = e
    finally:
        for k, v in saved.items():
            setattr(H, k, v)
        os.environ.pop("SAFE_EDIT_FALLBACK_ENABLED", None)
        if safe_saved is not None:
            os.environ["SAFE_EDIT_FALLBACK_ENABLED"] = safe_saved
    return out, err, buf.getvalue()


print("=== D1: region=bottom + Lumen → coerced to 'none' + divergence logged ===")
out, err, log = run_gen(clean_plan(existing_caption_region="bottom"))
check("delivered", err is None and out is not None, str(err)[:150])
check("caption_style coerced to none", out and out["caption_style"] == "none")
check("grep-stable divergence line",
      "action=double_caption_prevented" in log and '"region":"bottom"' in log)

print("\n=== D2: region=none → untouched ===")
out, err, log = run_gen(clean_plan())
check("Lumen survives", err is None and out and out["caption_style"] == "Lumen")
check("no divergence", "double_caption_prevented" not in log)

print("\n=== D3: explicit captions-on vibe overrides (documented behavior) ===")
out, err, log = run_gen(clean_plan(existing_caption_region="bottom"),
                        vibe="add captions and make it pop")
check("captions render on explicit ask",
      err is None and out and out["caption_style"] == "Lumen")
check("no coercion divergence", "double_caption_prevented" not in log)
check("negated mention does NOT override",
      not H._vibe_requests_captions("no captions please")
      and not H._vibe_requests_captions("without subtitles"))

print("\n=== D4: junk region value biases to none (never over-strip) ===")
out, err, log = run_gen(clean_plan(existing_caption_region="everywhere"))
check("junk region treated as none; Lumen survives",
      err is None and out and out["caption_style"] == "Lumen"
      and out["existing_caption_region"] == "none")

print("\n=== D5: MG anchored into the reported band relocates ===")
out, err, log = run_gen(clean_plan(
    existing_caption_region="bottom",
    motion_graphics=[{"type": "Stamp", "props": {"text": "free"},
                      "anchor": "lower_third_safe", "start_word_index": 10,
                      "end_word_index": 10, "duration_seconds": 2.5}]))
check("delivered", err is None and out is not None, str(err)[:150])
check("MG relocated to center",
      out and out["motion_graphics"][0]["anchor"] == "center")
check("relocation divergence logged",
      log.count("double_caption_prevented") >= 2
      and "anchored_into_burned_in_caption_band" in log)

print("\n=== D6: MG in a FREE band stays put ===")
out, err, log = run_gen(clean_plan(
    existing_caption_region="bottom",
    motion_graphics=[{"type": "Stamp", "props": {"text": "free"},
                      "anchor": "upper_third_safe", "start_word_index": 10,
                      "end_word_index": 10, "duration_seconds": 2.5}]))
check("upper anchor untouched with a bottom region",
      err is None and out and out["motion_graphics"][0]["anchor"] == "upper_third_safe")

print("\n=== D7: caption_match overlay yields the top band ===")
out, err, log = run_gen(clean_plan(
    existing_caption_region="top",
    text_overlays=[{"variant": "caption_match", "text": "upload your video",
                    "start_word_index": 1, "duration_seconds": 2.0,
                    "position": "top"}]))
check("delivered", err is None and out is not None, str(err)[:150])
check("overlay moved to center",
      out and out["text_overlays"][0]["position"] == "center")

print("\n=== D4b: field OMITTED entirely (Vertex optional-omission) → none ===")
_no_field = clean_plan()
del _no_field["existing_caption_region"]
out, err, log = run_gen(_no_field)
check("omitted field treated as none; Lumen survives",
      err is None and out and out["caption_style"] == "Lumen"
      and out["existing_caption_region"] == "none")

print("\n=== D7b: render-side face-clear respects the burned band (source pins) ===")
src0 = open("handler.py").read()
check("_face_clear_anchor takes a blocked band",
      'def _face_clear_anchor(band, sw_s, ew_s, face_traj, component="", blocked=None):' in src0)
check("render MG call passes the blocked band", "blocked=_ecr_blocked" in src0)
check("blocked band never a relocation candidate", "_b != band and _b != blocked" in src0)
band, moved = H._face_clear_anchor("bottom", 0.0, 2.0, [], component="t", blocked="bottom")
check("component IN the blocked band moves even without face data",
      band == "center")
band2, _ = H._face_clear_anchor("top", 0.0, 2.0,
    [{"t": 0.5, "cy": 400.0, "found": True}], component="t", blocked="bottom")
check("face-covered top band cannot relocate INTO the blocked bottom band",
      band2 != "bottom", band2)

print("\n=== D8: schema seams ===")
src = open("handler.py").read()
check("PostCutPlan carries the field with default",
      src.count('existing_caption_region: Literal["none", "bottom", "top", "other"] = "none"') == 2)
check("prompt teaches watch-first reporting (Stage 0, first look)",
      "Stage 0 — WHAT'S ALREADY ON THE FRAME" in src
      and "A watermark or a single title card is not a caption track" in src
      and "even when it's small or center-frame" in src)
check("RESPONSE FORMAT lists the field",
      '"existing_caption_region": "none" | "bottom" | "top" | "other"' in src)
check("re-edit rail note documented", "re-edit rail" in src)

print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
