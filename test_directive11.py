"""Directive #11 builds B1/B2/B4/B6 — behavioral tests."""
import contextlib
import copy
import io
import os
import sys
import textwrap

import handler as H
import recipe_eval

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

print("=== B1: SFX re-anchor tolerance — extracted commit block, both geometries ===")
src = open("handler.py").read()
lines = src.split("\n")
starts = [i for i, l in enumerate(lines) if "Cut-partnered SFX re-anchor (B1, directive #11)" in l]
check("B1 block present once", len(starts) == 1)
s = starts[0]
e = s
while "sfx_reanchor_declined" not in lines[e]:
    e += 1
depth = e
while ")" not in lines[depth] or "reason=" not in lines[depth - 1] and "the sound serves its word" not in lines[depth - 1]:
    depth += 1
    if depth - e > 12:
        break
block = textwrap.dedent("\n".join(lines[s:depth + 1]))

def run_b1(word_start, boundary):
    ns = {"_record_divergence": H._record_divergence, "print": print, "abs": abs,
          "_SFX_REANCHOR_TOLERANCE_S": H._SFX_REANCHOR_TOLERANCE_S,
          "_sfx_cut_anchor_t": {12: boundary}, "_sfx_wi": 12,
          "_sound_style": "money-ching", "_projected_t": word_start, "round": round}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(block, "<b1>", "exec"), ns)
    return ns["_projected_t"], buf.getvalue()

t, o = run_b1(2.610, 3.167)   # render C's ching geometry
check("render C ching STAYS on its word (557ms > tolerance)", t == 2.610, str(t))
check("declined divergence", "sfx_reanchor_declined" in o and "557ms" in o, o[-200:])
t, o = run_b1(2.610, 2.700)   # word-adjacent boundary (90ms)
check("word-adjacent boundary still re-anchors", t == 2.700, str(t))
check("re-anchor logged", "re-anchor ching" in o)

print("\n=== B4: SFX why round-trips the span; audit counts it ===")
WORDS = [{"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.4, 2),
          "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
         for i in range(24)]
def plan(**over):
    p = {"video_identity": "x" * 40,
         "video_plan": {"what_happens": "a", "key_moments": [{"word_index": 10}],
                        "arc_segments": [{"start_word_index": 0, "end_word_index": 22,
                                           "position": "hook", "intensity": 0.5}],
                        "editorial_vision": "v", "hook_word_index": 0,
                        "payoff_word_index": 15, "close_word_index": 22},
         "caption_style": "Prime", "caption_keywords": [],
         "transitions": [], "tight_cut_overlays": [], "motion_graphics": [],
         "emphasis_moments": [], "text_overlays": [], "broll_clips": [],
         "sound_effects": [], "caption_position_changes": [],
         "thumbnail_word_index": 1, "audio_denoise": False,
         "outro": "none", "aspect_ratio": "9:16"}
    p.update(over)
    return p
H.compute_mechanical_cuts = lambda w, source_path=None: {
    "remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}
H._get_genai_client = lambda: None
H._call_gemini_post_cuts = lambda *a, **k: plan(sound_effects=[
    {"word_index": 10, "sound": "boom",
     "why": "one two three four five six seven eight nine ten eleven twelve extra"}])
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    out = H.generate_edit_gemini(video_path="/x.mp4", vibe="t", duration=9.6,
                                 deepgram_words=copy.deepcopy(WORDS), inline_video_bytes=b"x")
sfx = (out.get("sound_effects") or [])
check("sfx why normalized to 12 words", sfx and len((sfx[0].get("why") or "").split()) == 12,
      str(sfx[:1]))
H._SoundEffect.model_validate({"word_index": 3, "sound": "popsfx"})
check("why omission tolerated by schema", True)
check("why in _SoundEffect schema, optional",
      "why" in H._SoundEffect.model_json_schema().get("properties", {})
      and "why" not in set(H._SoundEffect.model_json_schema().get("required", [])))
words30 = [{"word": f"w{i}", "start": i * 0.4, "end": i * 0.4 + 0.35} for i in range(30)]
rep = recipe_eval.evaluate_recipe(
    plan(sound_effects=[{"word_index": 10, "sound": "boom"}],
         emphasis_moments=[{"word_indices": [10], "zoom_effect": {"type": "SmoothPush"}}],
         video_plan={**plan()["video_plan"],
                     "arc_segments": [{"start_word_index": 0, "end_word_index": 29,
                                        "position": "hook", "intensity": 0.5}],
                     "close_word_index": 29}),
    words30, [], 12.0, tight_boundaries=[])
check("why-audit counts the why-less SFX", rep.stats.get("why_missing", 0) >= 1,
      str(rep.stats))

print("\n=== B6: gap compression — flag-off byte-identical, flag-on compresses ===")
ws = [{"word": f"w{i}", "punctuated_word": f"w{i}", "start": round(i * 0.5, 3),
       "end": round(i * 0.5 + 0.4, 3)} for i in range(6)]
ws[3]["start"] += 0.8; ws[3]["end"] += 0.8   # 0.9s kept gap after w2
for i in (4, 5):
    ws[i]["start"] += 0.8; ws[i]["end"] += 0.8
def clips_with(flag):
    saved = os.environ.pop("GAP_COMPRESSION_ENABLED", None)
    if flag is not None:
        os.environ["GAP_COMPRESSION_ENABLED"] = flag
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            ret = H.build_clips_from_words(copy.deepcopy(ws), [], video_duration=30.0)
        return ret[0] if isinstance(ret, tuple) else ret
    finally:
        os.environ.pop("GAP_COMPRESSION_ENABLED", None)
        if saved is not None:
            os.environ["GAP_COMPRESSION_ENABLED"] = saved
off = clips_with(None)
off2 = clips_with("0")
on = clips_with("1")
check("flag-off: single clip (gap kept)", len(off) == 1 and len(off2) == 1,
      str((len(off), len(off2))))
check("flag-on: gap split into two clips", len(on) == 2, str(len(on)))
def gap_compress_label():
    saved = os.environ.pop("GAP_COMPRESSION_ENABLED", None)
    os.environ["GAP_COMPRESSION_ENABLED"] = "1"
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            H.build_clips_from_words(copy.deepcopy(ws), [], video_duration=30.0)
        return buf.getvalue()
    finally:
        os.environ.pop("GAP_COMPRESSION_ENABLED", None)
        if saved is not None:
            os.environ["GAP_COMPRESSION_ENABLED"] = saved
_o = gap_compress_label()
check("compressed boundary logs action=gap_compress (attributable)",
      "action=gap_compress" in _o and "action=cut_pad" not in _o.split("first_clip_head")[0].replace("action=gap_compress", ""),
      _o[-300:])
if len(on) == 2:
    kept_gap = on[1]["source_start"] - on[0]["source_end"]
    removed = (ws[3]["start"] - ws[2]["end"]) - (H._GAP_COMPRESS_FLOOR_S)
    check("kept pause ≈ floor (0.30s)", abs(kept_gap - (0.9 - H._GAP_COMPRESS_FLOOR_S)) < 0.02
          or abs((0.9 - kept_gap) - H._GAP_COMPRESS_FLOOR_S) < 0.02,
          f"kept_gap={kept_gap:.3f}")

print("\n=== B2/B3 pins ===")
check("cleanup append present", "the cleanup removes what has no moment and protects what does" in src)
check("shop grammar append present", "the spec, the price, and the name earn their cards" in src)
check("band luma measured + delivered", "_measure_caption_band_luma" in src
      and '"bandLuma"' in src.replace("'", '"'))
leg = open("src/remotion/src/captions/shared/legibility.ts").read()
check("B3 helper + trigger in legibility module",
      "KEYWORD_CONTRAST_TRIGGER = 40" in leg and "keywordContrastShadow" in leg)
lum = open("src/remotion/src/captions/Lumen/Lumen.tsx").read()
check("Lumen permanent floor + step-up wired",
      "KEYWORD_CONTRAST_LAYERS" in lum and "keywordContrastShadow(keywordColor, bandLuma)" in lum)

print("\n=== D14: retired-style successor coercion (real block, exec'd) ===")
lines2 = open("handler.py").read().split("\n")
s2 = next(i for i, l in enumerate(lines2) if "# Directive #13: NewspaperWipe retired" in l)
e2 = next(i for i, l in enumerate(lines2) if "_caption_extra_props = _resolve_caption_extra_props" in l)
block2 = textwrap.dedent("\n".join(lines2[s2:e2]))
ep = {"transitions": [{"type": "NewspaperWipe", "after_word_index": 4}],
      "tight_cut_overlays": [{"type": "NewspaperWipe", "after_word_index": 7}],
      "_resolved_tight_cut_overlays": [],
      "caption_style": "MagazineCutout"}
ns = {"_record_divergence": H._record_divergence, "print": print,
      "edit_plan": ep, "_caption_style": ep["caption_style"], "isinstance": isinstance, "dict": dict}
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    exec(compile(block2, "<successors>", "exec"), ns)
o = buf.getvalue()
check("NewspaperWipe transition coerced", ep["transitions"][0]["type"] == "ShutterFlash")
check("NewspaperWipe TCO coerced", ep["tight_cut_overlays"][0]["type"] == "ShutterFlash")
check("MagazineCutout -> Quintessence", ns["_caption_style"] == "Quintessence"
      and ep["caption_style"] == "Quintessence", str(ns["_caption_style"]))
check("divergences logged", o.count("retired_style_coerced") >= 3, o[-200:])
ep2 = {"transitions": [], "tight_cut_overlays": [], "_resolved_tight_cut_overlays": [],
       "caption_style": "EmojiPop"}
ns2 = {"_record_divergence": H._record_divergence, "print": print,
       "edit_plan": ep2, "_caption_style": "EmojiPop", "isinstance": isinstance, "dict": dict}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(block2, "<successors>", "exec"), ns2)
check("EmojiPop -> TwoTone (ONE hop, re-chained by #16)", ns2["_caption_style"] == "TwoTone")
# Directive #16: every loud register lands on TwoTone in ONE hop — a stored
# EmojiPop plan must resolve directly, never through the dead HormoziPopIn.
for _retired, _succ in (("Spectrum", "TwoTone"), ("NeonStripe", "TwoTone"),
                        ("EmojiPop", "TwoTone"), ("HormoziPopIn", "TwoTone")):
    ep3 = {"transitions": [], "tight_cut_overlays": [], "_resolved_tight_cut_overlays": [],
           "caption_style": _retired}
    ns3 = {"_record_divergence": H._record_divergence, "print": print,
           "edit_plan": ep3, "_caption_style": _retired, "isinstance": isinstance, "dict": dict}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(block2, "<successors>", "exec"), ns3)
    check(f"{_retired} -> {_succ}", ns3["_caption_style"] == _succ, str(ns3["_caption_style"]))

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL DIRECTIVE-11 CASES PASS")
