"""F5/F6/F7 launch wave — MG truth (grounding), readability (reading-time
floor), and clearance (clear-region rule). Drives the REAL generate_edit_gemini
validation span via the 3-stub harness (test_recipe_repair pattern)."""
import contextlib
import copy
import io
import os
import re
import textwrap

import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


def make_words(texts):
    return [{"word": t, "punctuated_word": t, "start": round(i * 0.4, 2),
             "end": round(i * 0.4 + 0.35, 2), "confidence": 0.99, "speaker": 0}
            for i, t in enumerate(texts)]

# 12 words, real-ish: "people upload your video type your vibe hit send its
# completely free" — word 5 removed by the cut stub (like the base harness).
WORDS = make_words(["people", "upload", "your", "video", "type", "uh",
                    "vibe", "hit", "send", "its", "completely", "free"])
CUT_PLAN = {"remove_words": [{"word_index": 5}], "notes": "stub", "pacing": "fast"}

EXHIBIT_TITLE = "1. The Missing Piece"
EXHIBIT_CAPTION = "Tell them what they don't know yet so they have to keep watching."


def clean_plan(**over):
    p = {
        "caption_style": "Prime", "caption_keywords": ["upload"],
        "video_identity": "A creator pitching an app from their desk.",
        "transitions": [], "tight_cut_overlays": [],
        "motion_graphics": [], "emphasis_moments": [], "text_overlays": [],
        "broll_clips": [], "sound_effects": [],
        "audio_denoise": False, "outro": "none", "aspect_ratio": "9:16",
    }
    p.update(over)
    return p


class Stub:
    def __init__(self, plans):
        self.plans = list(plans)
        self.post_users = []
    def __call__(self, client, post_sys, post_user, video_part, model):
        self.post_users.append(post_user)
        return copy.deepcopy(self.plans.pop(0))


def run_gen(plans, face_traj=None, vibe="make it viral", attempts="0"):
    # attempts="0": a validation failure is TERMINAL (raise tests);
    # attempts="1": one re-ask (the repair test). MG indices in plans are
    # KEPT-space (the two-pass re-index translates to source indices).
    stub = Stub(plans)
    saved = {k: getattr(H, k) for k in
             ("compute_mechanical_cuts", "_call_gemini_post_cuts", "_get_genai_client")}
    safe_saved = os.environ.pop("SAFE_EDIT_FALLBACK_ENABLED", None)
    att_saved = os.environ.pop("RECIPE_REPAIR_MAX_ATTEMPTS", None)
    os.environ["SAFE_EDIT_FALLBACK_ENABLED"] = "0"
    os.environ["RECIPE_REPAIR_MAX_ATTEMPTS"] = attempts
    H.compute_mechanical_cuts = lambda words, source_path=None: copy.deepcopy(CUT_PLAN)
    H._call_gemini_post_cuts = stub
    H._get_genai_client = lambda: None
    buf = io.StringIO()
    err = None
    plan = None
    try:
        with contextlib.redirect_stdout(buf):
            plan = H.generate_edit_gemini(
                video_path="/nonexistent.mp4", vibe=vibe, duration=4.8,
                deepgram_words=copy.deepcopy(WORDS), shot_changes=[],
                vocal_emphasis=[], source_loudness={}, face_positions=[],
                smoothed_face_trajectory=copy.deepcopy(face_traj or []),
                inline_video_bytes=b"fakevideo", premium=False,
            )
    except Exception as e:
        err = e
    finally:
        for k, v in saved.items():
            setattr(H, k, v)
        os.environ.pop("SAFE_EDIT_FALLBACK_ENABLED", None)
        if safe_saved is not None:
            os.environ["SAFE_EDIT_FALLBACK_ENABLED"] = safe_saved
        os.environ.pop("RECIPE_REPAIR_MAX_ATTEMPTS", None)
        if att_saved is not None:
            os.environ["RECIPE_REPAIR_MAX_ATTEMPTS"] = att_saved
    return plan, err, stub, buf.getvalue()


def mg(type_, props, sw=1, ew=3, dur=None):
    return {"type": type_, "props": props, "anchor": "upper_third_safe",
            "start_word_index": sw, "end_word_index": ew,
            "duration_seconds": dur}


print("=== F5-1: the exhibit's exact card raises with the exact message ===")
# The grounded title isolates the exhibit line as the FIRST ungrounded field —
# the validator names the first offender (a fully-ungrounded card raises on
# its title; either way it raises, which F5-2's all-ungrounded variant pins).
bad = clean_plan(motion_graphics=[mg("DropCard", {
    "title": "upload your video",
    "points": [{"title": EXHIBIT_TITLE, "caption": EXHIBIT_CAPTION}]}, dur=4.5)])
plan, err, stub, out = run_gen([bad])
expected = ('MG DropCard at word 1: card text must be drawn from the dialogue — '
            f'"{EXHIBIT_TITLE}" appears nowhere in it. '
            'Rewrite from the speaker\'s own words or remove the card.')
check("terminal error carries the verbatim F5 message",
      err is not None and expected in str(err), str(err)[:220])

print("\n=== F5-2: the repair net feeds the message back and the rewrite lands ===")
good = clean_plan(motion_graphics=[mg("DropCard", {
    "title": "hit send",
    "steps": [{"label": "Upload"}, {"label": "Vibe"}, {"label": "Send"}]}, dur=4.5)])
plan, err, stub, out = run_gen([bad, good], attempts="1")
check("repaired plan delivered", err is None and plan is not None)
check("re-ask carried the F5 message to Gemini",
      len(stub.post_users) == 2 and expected in stub.post_users[1])
check("repaired card survived",
      plan and plan["motion_graphics"][0]["props"]["title"] == "hit send")

print("\n=== F5-3: grounded StickyNotes pass untouched (the burn-in case) ===")
grounded = clean_plan(motion_graphics=[mg("StickyNotes", {
    "notes": [{"text": "UPLOAD VIDEO", "color": "#FFE066", "rotation": -3},
              {"text": "TYPE VIBE", "color": "#FFB3C1", "rotation": 1},
              {"text": "HIT SEND", "color": "#A8E6CF", "rotation": 4}]}, dur=4.0)])
plan, err, stub, out = run_gen([grounded])
check("grounded notes pass", err is None and plan is not None)
check("notes untouched",
      plan and [n["text"] for n in plan["motion_graphics"][0]["props"]["notes"]]
      == ["UPLOAD VIDEO", "TYPE VIBE", "HIT SEND"])

print("\n=== F5-4: numbers-only — StatCard value validates against numerals ===")
badnum = clean_plan(motion_graphics=[mg("StatCard",
    {"value": 42, "label": "upload video"}, dur=3.0)])
plan, err, stub, out = run_gen([badnum])
check("ungrounded number raises with the template",
      err is not None and 'value=42' in str(err) and "drawn from the dialogue" in str(err))
plan, err, stub, out = run_gen([badnum], vibe="make a video about my 42 clients")
check("numeral from the vibe grounds the value (known set = transcript ∪ vibe ∪ identity)",
      err is None and plan is not None)

print("\n=== F5-5: paraphrase edge, documented ===")
para = clean_plan(motion_graphics=[mg("StatCard",
    {"value": 0, "label": "COST", "prefix": "$"}, dur=3.0)])
plan, err, stub, out = run_gen([para])
check("'$0 COST' vs spoken 'completely free' RAISES at threshold 0.6 "
      "(paraphrase edge: the model rewrites toward the speaker's words, e.g. 'FREE')",
      err is not None and "drawn from the dialogue" in str(err))
verbatim = clean_plan(motion_graphics=[mg("Stamp", {"text": "FREE"}, sw=11, ew=11, dur=2.5)])
plan, err, stub, out = run_gen([verbatim])
check("the verbatim rewrite ('FREE') passes", err is None and plan is not None)

print("\n=== F6-1: the reading-time floor raises with the verbatim message ===")
short = clean_plan(motion_graphics=[mg("ProgressBar",
    {"value": 50, "total": 100, "label": "completely free"}, sw=9, ew=10)])
# kept 9..10 -> source words 10..11 ("completely free") = 4.0..4.75 → 0.75s;
# 2 content words → floor 1.5s. ProgressBar isolates F6 (no number check).
plan, err, stub, out = run_gen([short])
check("short window raises",
      err is not None and re.search(
          r"ProgressBar at word 10 shows 2 words for 0\.8s; viewers need ~1\.5s — "
          r"shorten the text or widen the window", str(err)) is not None,
      str(err)[:200])

print("\n=== F6-1b: short window WITH free space passes (render backstop extends) ===")
spacey = clean_plan(motion_graphics=[mg("ProgressBar",
    {"value": 50, "total": 100, "label": "upload video"}, sw=1, ew=2)])
# window 0.4..1.15 = 0.75s < floor 1.5s, but no neighbor and video end at 4.8s
# → 4.4s of free space → the render backstop extends; the validator stays quiet.
plan, err, stub, out = run_gen([spacey])
check("space-aware validator does not raise", err is None and plan is not None,
      str(err)[:150])

print("\n=== F5-6: number normalization (final-wave review fixes) ===")
kt, kn = H._mg_known_sets(
    [{"word": "it's"}, {"word": "a"}, {"word": "$1,000"}, {"word": "3.5%"}, {"word": "win"}],
    set(), "make it pop", "the zero-dollar price tag")
check("compound '$1,000' grounds 1000", 1000.0 in kn)
check("decimal '3.5%' grounds 3.5", 3.5 in kn)
check("hyphenated 'zero-dollar' grounds 0", 0.0 in kn)

print("\n=== F5-7: social chrome is not graded against the dialogue ===")
check("TweetBubble name/handle exempt; text grounds",
      H._MG_TEXT_FIELDS["TweetBubble"] == ("text",))
check("Notification appName/timestamp exempt",
      H._MG_TEXT_FIELDS["Notification"] == ("notifications[].title", "notifications[].body"))

print("\n=== F6-2: a 4-word card at 2s passes (3 content words → floor 1.85s) ===")
four = clean_plan(motion_graphics=[mg("IconLabel",
    {"label": "upload your video vibe"}, dur=2.0)])
plan, err, stub, out = run_gen([four])
check("4-word card at 2s passes", err is None and plan is not None)

print("\n=== F6-3: render-side backstop block (extract + exec) ===")
src = open("handler.py").read()
lines = src.split("\n")
starts = [i for i, l in enumerate(lines) if "# F6 backstop:" in l]
check("backstop block present exactly once", len(starts) == 1)
s = starts[0]
e = s
while "flush=True," not in lines[e]:
    e += 1
    assert e - s < 40, "backstop end not found"
e += 1  # include closing paren line
block = textwrap.dedent("\n".join(lines[s:e + 1]))
ns = {
    "_MG_MIN_DURATION_SECONDS": 2.5,
    "_mg_reading_floor_s": H._mg_reading_floor_s,
    "_mg_content_word_count": H._mg_content_word_count,
    "_mg": {"type": "DropCard", "props": {"title": "upload your video",
            "points": [{"title": "type vibe", "caption": "hit send completely free"}]}},
    "_out_start": 10.0, "_out_end": 11.0,   # 1.0s window, wordy card
    "_boundary_starts_sec": [], "_other_mg_starts_sec": [], "_i": 0,
    "print": print,
}
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    exec(block, ns)
# 8 content words (your = stopword) → floor = 0.8 + 2.8 = 3.6s
check("extension fires to the reading floor when space exists",
      abs(ns["_out_end"] - (10.0 + H._mg_reading_floor_s(8))) < 1e-6, str(ns["_out_end"]))
check("extension logs [mg-fit] extended", "[mg-fit] extended type=DropCard" in buf.getvalue())
ns2 = dict(ns, _out_end=11.0, _other_mg_starts_sec=[(11.5, 1)])
with contextlib.redirect_stdout(io.StringIO()):
    exec(block, ns2)
check("extension caps at the next component (collision-aware)",
      abs(ns2["_out_end"] - 11.5) < 1e-6, str(ns2["_out_end"]))

print("\n=== F7: clear-region rule ===")
face_centered = [{"t": round(0.2 + i * 0.3, 2), "cx": 540, "cy": 960, "found": True}
                 for i in range(16)]
face_low = [{"t": round(0.2 + i * 0.3, 2), "cx": 340, "cy": 1500, "found": True}
            for i in range(16)]
fullcard = clean_plan(motion_graphics=[mg("DropCard", {
    "title": "upload video", "steps": [{"label": "vibe"}]}, dur=3.0)])
plan, err, stub, out = run_gen([fullcard], face_traj=face_centered)
check("full-width card over a centered face RAISES with the verbatim message",
      err is not None and re.search(
          r"DropCard at word 1: no face-clear region exists for a card this size — "
          r"reduce its content, or move it to a window where the speaker sits "
          r"lower/off-center", str(err)) is not None, str(err)[:220])
plan, err, stub, out = run_gen([fullcard], face_traj=face_low)
check("same card over a low/off-center face passes", err is None and plan is not None)
compact = clean_plan(motion_graphics=[mg("Stamp",
    {"text": "free"}, dur=3.0)])
plan, err, stub, out = run_gen([compact], face_traj=face_centered)
check("compact card over the same centered face passes (top band clears)",
      err is None and plan is not None)
plan, err, stub, out = run_gen([fullcard], face_traj=[])
check("fail-open when face data is absent", err is None and plan is not None)

print("\n=== F-BATCH: one raise carries every correction ===")
multi = clean_plan(motion_graphics=[
    mg("Stamp", {"text": "Synergy"}, sw=1, ew=2, dur=2.5),          # F5: ungrounded
    mg("StatCard", {"value": 42, "label": "upload video"}, sw=3, ew=4, dur=2.5),  # F5.3
])
plan, err, stub, out = run_gen([multi])
check("both violations in ONE raise (single repair attempt carries all)",
      err is not None and '"Synergy"' in str(err) and 'value=42' in str(err),
      str(err)[:250])

print("\n=== W: wire pins ===")
check("sticky_note overlay grounded (same law)",
      "F5 grounding — the sticky_note overlay renders the SAME" in src)
check("emphasis-nested MGs grounded",
      "F5 grounding applies to emphasis-nested MGs identically" in src)
check("constants named + tunable",
      "_MG_GROUNDING_THRESHOLD = 0.6" in src and "_MG_READ_BASE_S = 0.8" in src
      and "_MG_READ_PER_WORD_S = 0.35" in src and "_MG_READ_FLOOR_S = 1.5" in src)

print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
