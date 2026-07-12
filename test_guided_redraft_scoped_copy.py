"""Part 3 — guided_redraft scoped-copy. Deterministic, offline (no LLM/render).

Exercises H._scoped_copy_out_of_scope(new_plan, prior_plan, layers_in_scope):
a general re-edit re-authors ONLY its in-scope layers; every out-of-scope
layer is byte-identical to the prior plan BY CONSTRUCTION — UNLESS the
in-scope re-author touches cuts, in which case out-of-scope word-anchored
layers are RE-DERIVED (orphan entries whose anchor word the new cuts remove
are dropped), never corrupted-by-verbatim-copy.

Ruling pinned (Zac 2026-07-11): pacing in scope ⇒ cuts effectively in scope;
'captions' binds all four caption fields as one unit.
"""
import copy
import sys

import handler as H

PASS = []
FAIL = []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

# A source transcript long enough that every word_index below is in-bounds.
# Passed through so the function and production share ONE removed-set path
# (_remove_words_to_src_indices), never a test-only shortcut.
DG = [{"word": f"w{i}", "start": i * 0.1, "end": i * 0.1 + 0.05} for i in range(200)]


def prior_plan():
    """The plan the user already saw and liked. Distinct values in every field."""
    return {
        "notes": "PRIOR notes",
        "remove_words": [{"word_index": 3, "reason": "um"}],
        "pacing": "slow",
        "video_identity": "PRIOR identity",
        "existing_caption_region": "none",
        "caption_style": "PRIOR_STYLE",
        "caption_keywords": ["prior", "kw"],
        "caption_position_changes": [{"word_index": 5, "position": "top"}],
        "emphasis_moments": [{"word_indices": [7], "t": 1.0, "kind": "prior"}],
        "sound_effects": [{"_word_idx": 9, "sound": "whoosh", "t": 2.0}],
        "motion_graphics": [{"type": "StatCard", "start_word_index": 10, "end_word_index": 12, "props": {"value": 1}}],
        "text_overlays": [{"word_index": 14, "text": "PRIOR"}],
        "broll_clips": [{"start_word_index": 8, "end_word_index": 12, "query": "prior"}],
        "transitions": [{"after_word_index": 6, "type": "whip"}],
        "thumbnail_word_index": 2,
        "audio_denoise": True,
        "outro": "fade_black",
        "aspect_ratio": "9:16",
    }


def new_plan_full():
    """The redraft's fresh authoring. Differs from prior in EVERY field."""
    return {
        "notes": "NEW notes",
        "remove_words": [{"word_index": 99, "reason": "new"}],
        "pacing": "fast",
        "video_identity": "NEW identity",
        "existing_caption_region": "bottom",
        "caption_style": "NEW_STYLE",
        "caption_keywords": ["new", "words"],
        "caption_position_changes": [{"word_index": 50, "position": "bottom"}],
        "emphasis_moments": [{"word_indices": [70], "t": 5.0, "kind": "new"}],
        "sound_effects": [{"_word_idx": 90, "sound": "boom", "t": 6.0}],
        "motion_graphics": [{"type": "LowerThird", "start_word_index": 30, "end_word_index": 32, "props": {"value": 9}}],
        "text_overlays": [{"word_index": 40, "text": "NEW"}],
        "broll_clips": [{"start_word_index": 20, "end_word_index": 24, "query": "new"}],
        "transitions": [{"after_word_index": 60, "type": "fade"}],
        "thumbnail_word_index": 88,
        "audio_denoise": False,
        "outro": "none",
        "aspect_ratio": "9:16",
    }


if not hasattr(H, "_scoped_copy_out_of_scope"):
    print("  FAIL  _scoped_copy_out_of_scope not implemented yet (RED)")
    print("\n=== RESULT: 0 passed, 1 failed ===")
    sys.exit(1)


# ─── A. NO CUT CHANGE → out-of-scope layers byte-identical to prior ─────────
print("=== A. scope=[emphasis,sounds], no cut touch → out-of-scope byte-identical ===")
P = prior_plan()
N = new_plan_full()
res = copy.deepcopy(N)
applied = H._scoped_copy_out_of_scope(res, P, ["emphasis", "sounds"], DG)

# in-scope layers keep the redraft's authoring
check("emphasis (in scope) == redraft", res["emphasis_moments"] == N["emphasis_moments"], res["emphasis_moments"])
check("sounds (in scope) == redraft", res["sound_effects"] == N["sound_effects"], res["sound_effects"])
# out-of-scope layers byte-identical to prior
check("caption_style oos == prior", res["caption_style"] == P["caption_style"])
check("caption_keywords oos == prior", res["caption_keywords"] == P["caption_keywords"])
check("caption_position_changes oos == prior", res["caption_position_changes"] == P["caption_position_changes"])
check("existing_caption_region oos == prior", res["existing_caption_region"] == P["existing_caption_region"])
check("motion_graphics oos == prior", res["motion_graphics"] == P["motion_graphics"])
check("broll_clips oos == prior", res["broll_clips"] == P["broll_clips"])
check("text_overlays oos == prior", res["text_overlays"] == P["text_overlays"])
check("transitions oos == prior", res["transitions"] == P["transitions"])
check("remove_words oos (cuts not in scope) == prior", res["remove_words"] == P["remove_words"])
check("pacing oos == prior", res["pacing"] == P["pacing"])
check("video_identity oos == prior", res["video_identity"] == P["video_identity"])
check("thumbnail_word_index unclaimed==prior", res["thumbnail_word_index"] == P["thumbnail_word_index"])
check("audio_denoise unclaimed==prior", res["audio_denoise"] == P["audio_denoise"])
check("outro unclaimed==prior", res["outro"] == P["outro"])
# notes is a rationale string describing THIS edit → keep the redraft's
check("notes always-redraft == new", res["notes"] == N["notes"])
# nothing mutated the caller's prior plan
check("prior plan untouched", P == prior_plan())


# ─── B. pacing ⇒ cuts: pacing in scope keeps redraft cuts + triggers rederive ─
print("\n=== B. scope=[pacing] ⇒ cuts effectively in scope ===")
P = prior_plan()
N = new_plan_full()
res = copy.deepcopy(N)
H._scoped_copy_out_of_scope(res, P, ["pacing"], DG)
check("pacing (in scope) == redraft", res["pacing"] == N["pacing"])
check("remove_words kept from redraft (pacing⇒cuts)", res["remove_words"] == N["remove_words"])
# out-of-scope layers still from prior; redraft cuts {99} orphan nothing here
check("motion_graphics oos == prior (no orphan at 99)", res["motion_graphics"] == P["motion_graphics"])
check("caption_style oos == prior", res["caption_style"] == P["caption_style"])


# ─── C. CUT TOUCH → out-of-scope word-anchored layers re-derived, not copied ──
print("\n=== C. scope=[emphasis,cuts], new cut removes word 10 → orphan-drop ===")
P = prior_plan()
# prior carries out-of-scope entries anchored at word 10 (RE-ANCHORED, not
# dropped, since a survivor exists) AND survivors untouched.
P["motion_graphics"] = [
    {"type": "StatCard", "start_word_index": 10, "end_word_index": 12, "props": {"v": 1}, "tag": "mg_at_10"},
    {"type": "LowerThird", "start_word_index": 20, "end_word_index": 22, "props": {"v": 2}, "tag": "mg_at_20"},
    # a StatCard whose WHOLE span is a single cut word → the one correct drop
    {"type": "StatCard", "start_word_index": 10, "end_word_index": 10, "props": {"v": 9}, "tag": "mg_gone"},
]
P["broll_clips"] = [
    {"start_word_index": 10, "end_word_index": 13, "tag": "broll_at_10"},
    {"start_word_index": 30, "end_word_index": 34, "tag": "broll_at_30"},
]
P["caption_position_changes"] = [
    {"word_index": 10, "position": "top", "tag": "cpc_10"},
    {"word_index": 5, "position": "bottom", "tag": "cpc_5"},
]
P["text_overlays"] = [{"word_index": 14, "text": "keep"}]
P["transitions"] = [{"after_word_index": 6, "type": "whip"}]
P["sound_effects"] = [{"_word_idx": 9, "sound": "whoosh", "t": 2.0}]

N = new_plan_full()
N["remove_words"] = [{"word_index": 10, "reason": "weak take"}]   # cuts in scope → kept

res = copy.deepcopy(N)
applied = H._scoped_copy_out_of_scope(res, P, ["emphasis", "cuts"], DG)

def _by_tag(lst, tag):
    return next((x for x in lst if x.get("tag") == tag), None)

check("cuts in scope: remove_words == redraft", res["remove_words"] == N["remove_words"])
check("emphasis in scope: == redraft", res["emphasis_moments"] == N["emphasis_moments"])
# RE-ANCHORED (not dropped): anchor word 10 cut → start snaps forward to 11,
# end (12, a survivor) unchanged, CONTENT byte-identical.
_mg10 = _by_tag(res["motion_graphics"], "mg_at_10")
check("mg_at_10 RE-ANCHORED not dropped (start 10→11, content preserved)",
      _mg10 is not None and _mg10["start_word_index"] == 11 and _mg10["end_word_index"] == 12
      and _mg10["props"] == {"v": 1} and _mg10["type"] == "StatCard", _mg10)
check("mg_at_20 byte-identical (anchors survive)", _by_tag(res["motion_graphics"], "mg_at_20") == P["motion_graphics"][1])
# the ONE correct drop: whole span is the cut word
check("mg_gone dropped (whole span is the cut word — no survivor)",
      _by_tag(res["motion_graphics"], "mg_gone") is None)
# broll endpoint cut → start snaps forward, content preserved, NOT dropped
_b10 = _by_tag(res["broll_clips"], "broll_at_10")
check("broll_at_10 RE-ANCHORED (start 10→11), not dropped",
      _b10 is not None and _b10["start_word_index"] == 11 and _b10["end_word_index"] == 13)
check("broll_at_30 byte-identical", _by_tag(res["broll_clips"], "broll_at_30") == P["broll_clips"][1])
# caption position change point-anchored at the cut word → re-anchored to 11
_c10 = _by_tag(res["caption_position_changes"], "cpc_10")
check("cpc_10 RE-ANCHORED (word 10→11), position preserved",
      _c10 is not None and _c10["word_index"] == 11 and _c10["position"] == "top")
check("cpc_5 byte-identical", _by_tag(res["caption_position_changes"], "cpc_5") == P["caption_position_changes"][1])
# survivors whose words are NOT cut stay byte-identical to prior
check("text_overlays byte-identical (word 14 survives)", res["text_overlays"] == P["text_overlays"])
check("transitions byte-identical (word 6 survives)", res["transitions"] == P["transitions"])
check("sound_effects byte-identical (word 9 survives, oos)", res["sound_effects"] == P["sound_effects"])

# THE CORRUPTION GUARD: no surviving out-of-scope entry anchors to a removed word
R = {10}
def _anchors(entry):
    idxs = set()
    for k in ("word_index", "start_word_index", "end_word_index", "after_word_index", "_word_idx"):
        v = entry.get(k)
        if isinstance(v, int):
            idxs.add(v)
    for v in (entry.get("word_indices") or []):
        if isinstance(v, int):
            idxs.add(v)
    return idxs
survivors = (res["motion_graphics"] + res["broll_clips"] + res["caption_position_changes"]
             + res["text_overlays"] + res["transitions"] + res["sound_effects"])
check("NO surviving oos entry anchors to a removed word (all re-anchored to survivors)",
      all(not (_anchors(e) & R) for e in survivors),
      [e for e in survivors if _anchors(e) & R])


# ─── D. IDEMPOTENCE: derive(derive(plan)) == derive(plan) ───────────────────
print("\n=== D. idempotence (derive²==derive) ===")
P = prior_plan()
N = new_plan_full()
once = copy.deepcopy(N)
H._scoped_copy_out_of_scope(once, P, ["emphasis", "sounds"], DG)
twice = copy.deepcopy(once)
H._scoped_copy_out_of_scope(twice, P, ["emphasis", "sounds"], DG)
check("scoped-copy is idempotent", twice == once, {"once": once, "twice": twice})

# idempotent under the cut-touch branch too
P2 = prior_plan()
P2["motion_graphics"] = [{"type": "StatCard", "start_word_index": 10, "end_word_index": 12, "props": {}, "tag": "a"}]
N2 = new_plan_full(); N2["remove_words"] = [{"word_index": 10, "reason": "x"}]
o = copy.deepcopy(N2); H._scoped_copy_out_of_scope(o, P2, ["emphasis", "cuts"], DG)
t = copy.deepcopy(o); H._scoped_copy_out_of_scope(t, P2, ["emphasis", "cuts"], DG)
check("scoped-copy idempotent under cut-touch", t == o, {"once": o, "twice": t})


# ─── E. ABSENCE IS A LEGAL PLAN CHOICE (.get()-tolerant) ────────────────────
print("\n=== E. absence semantics: prior lacks a field → match prior's absence ===")
P = prior_plan()
del P["text_overlays"]          # prior had no text_overlays layer at all
del P["broll_clips"]
N = new_plan_full()             # redraft invented both
res = copy.deepcopy(N)
try:
    H._scoped_copy_out_of_scope(res, P, ["emphasis"], DG)
    check("no crash when prior lacks an out-of-scope field", True)
except Exception as e:
    check("no crash when prior lacks an out-of-scope field", False, repr(e))
check("out-of-scope field absent in prior → absent in result", "text_overlays" not in res, res.get("text_overlays"))
check("out-of-scope broll absent in prior → absent in result", "broll_clips" not in res)


# ─── F. ONE-PLAN CONTRACT: scoped-copy → _revalidate_reedit_plan ────────────
# The redraft path runs the full fresh span (generate_edit_gemini); after
# scoped-copy overwrites out-of-scope layers, the SAME validation span
# (_revalidate_reedit_plan, the Part-2 rail) must run on the merged plan, set
# the one-plan marker, and be idempotent (derive²==derive, standing law #2).
print("\n=== F. one-plan contract: scoped-copy → _revalidate_reedit_plan ===")

def valid_plan(kind):
    """Minimal plan that passes _revalidate cleanly (no burned-caption
    suppression: existing_caption_region='none'; empty MG so no grounding
    fixtures needed). Differs prior vs new in every field."""
    return {
        "notes": f"{kind} notes",
        "remove_words": ([{"word_index": 3, "reason": "um"}] if kind == "prior"
                         else [{"word_index": 4, "reason": "uh"}]),
        "pacing": "slow" if kind == "prior" else "fast",
        "video_identity": f"{kind} identity",
        "existing_caption_region": "none",
        "source_text_regions": [],
        "caption_style": "karaoke" if kind == "prior" else "bold_center",
        "caption_keywords": [kind],
        "caption_position_changes": [],
        "emphasis_moments": [],
        "sound_effects": [],
        "motion_graphics": [],
        "text_overlays": [{"word_index": 14, "text": kind.upper()}],
        "broll_clips": [{"start_word_index": 8, "end_word_index": 12, "query": kind}],
        "transitions": [],
        "thumbnail_word_index": 2 if kind == "prior" else 5,
        "audio_denoise": True,
        "outro": "fade_black" if kind == "prior" else "none",
        "aspect_ratio": "9:16",
        "video_plan": {"hook_word_index": 0, "payoff_word_index": 1,
                       "close_word_index": 2, "key_moments": []},
    }

PR = valid_plan("prior")
NW = valid_plan("new")

def derive(plan_in):
    """The composed re-edit derivation: scoped-copy then the one-plan span."""
    p = copy.deepcopy(plan_in)
    H._scoped_copy_out_of_scope(p, PR, ["emphasis", "sounds"], DG)
    H._revalidate_reedit_plan(p, DG, [], "a clean punchy vibe", 30.0, pre_analysis={})
    return p

d1 = derive(NW)
check("one-plan marker set after revalidate", d1.get("_reedit_revalidated") is True)
check("out-of-scope caption_style == prior", d1["caption_style"] == PR["caption_style"])
check("out-of-scope broll == prior", d1["broll_clips"] == PR["broll_clips"])
check("out-of-scope text_overlays == prior", d1["text_overlays"] == PR["text_overlays"])
check("out-of-scope pacing == prior", d1["pacing"] == PR["pacing"])
# derive(derive(plan)) == derive(plan) — law #2, on the COMPOSED derivation
d2 = derive(d1)
_diff_keys = [k for k in set(d1) | set(d2) if d1.get(k) != d2.get(k)]
check("composed derive²==derive (law #2)", d2 == d1, _diff_keys)


print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
print("ALL SCOPED-COPY CASES PASS")
