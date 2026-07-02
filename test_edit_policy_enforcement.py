"""EditPolicy Steps 2-5 matrix test — deterministic, offline.
Exercises the ACTUAL functions: _derive_features (policy tier logic) and
_enforce_off_expressive_features (Step-2 enforcement). No LLM / render needed."""
import copy
import sys

import edit_policy as EP
import handler as H

PASS = []
FAIL = []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

EXPR = list(EP.EXPRESSIVE_FEATURES)   # captions,zoom,broll,motion_graphics,sfx,transitions,text_overlays
BASE = list(EP.BASELINE_FEATURES)     # filler_trim,stabilize,audio_denoise

def off_of(mode, allowed, excluded):
    feats = EP._derive_features(mode, allowed, excluded)
    return sorted(f for f, v in feats.items() if v == "off")

print("=== A. POLICY TIER LOGIC (_derive_features) ===")
# 1. bias-to-on default → nothing off
check("default → nothing off", off_of("default", [], []) == [])
# 2. each expressive off individually (deny_list)
for f in EXPR:
    check(f"deny [{f}] → off==[{f}]", off_of("deny_list", [], [f]) == [f], off_of("deny_list", [], [f]))
# 3. combinations
check("deny [broll,sfx]", off_of("deny_list", [], ["broll", "sfx"]) == ["broll", "sfx"])
check("deny [zoom,transitions,text_overlays]",
      set(off_of("deny_list", [], ["zoom", "transitions", "text_overlays"])) == {"zoom", "transitions", "text_overlays"})
# 4. only-captions (allow_list) → every OTHER expressive off, baseline stays on
_oc = set(off_of("allow_list", ["captions"], []))
check("only captions → 6 other expressive off", _oc == set(EXPR) - {"captions"}, sorted(_oc))
check("only captions → baseline stays ON", not (_oc & set(BASE)))
# 5. allow_list empty (baseline-only edit, 'just remove the silences') → all expressive off, baseline on
_ae = set(off_of("allow_list", [], []))
check("allow_list [] → all 7 expressive off", _ae == set(EXPR), sorted(_ae))
check("allow_list [] → baseline stays ON", not (_ae & set(BASE)))
# 6. raw / unedited → all three baseline off (deny path)
_raw = set(off_of("deny_list", [], BASE))
check("raw → all baseline off", _raw == set(BASE), sorted(_raw))
# 7. baseline exclusion alone (keep my pacing → filler_trim)
check("deny [filler_trim] → off==[filler_trim]", off_of("deny_list", [], ["filler_trim"]) == ["filler_trim"])
# 8. allow_list never strips baseline even if excluded names an expressive
check("allow_list [captions] baseline untouched",
      not (set(off_of("allow_list", ["captions"], [])) & set(BASE)))

print("\n=== B. resolve_edit_policy fail-safes (no LLM) ===")
# empty vibe / no key → DEFAULT_POLICY (nothing off)
check("empty vibe → default policy", EP.resolve_edit_policy("").off_features() == [])
check("None vibe → default policy", EP.resolve_edit_policy(None).off_features() == [])
_saved = None
import os as _os
_saved = _os.environ.pop("ANTHROPIC_API_KEY", None)
check("no API key → default policy (nothing off)", EP.resolve_edit_policy("no b-roll").off_features() == [])
if _saved is not None:
    _os.environ["ANTHROPIC_API_KEY"] = _saved
# language_hint passthrough (multilingual): the model carries lang; derivation is language-agnostic
_pt = EP.EditPolicy(language_hint="pt", mode="deny_list",
                    features=EP.EditPolicyFeatures(**EP._derive_features("deny_list", [], ["captions"])))
check("multilingual: lang carried + captions off", _pt.language_hint == "pt" and _pt.off_features() == ["captions"])

print("\n=== C. ENFORCEMENT (_enforce_off_expressive_features) ===")
def full_plan():
    return {
        "caption_style": "Prime",
        "caption_keywords": ["alpha", "beta"],
        "caption_position_changes": [{"after_word_index": 3, "position": "top"}],
        "broll_clips": [{"src": "x.mp4"}],
        "sound_effects": [{"word_index": 2, "sound": "whoosh"}],
        "text_overlays": [{"variant": "sticky_note", "text": "hi"}],
        "motion_graphics": [{"type": "StatCard", "start_word_index": 1, "end_word_index": 2}],
        "transitions": [{"afterClipIndex": 0, "type": "ZoomThrough"}],
        "tight_cut_overlays": [{"after_word_index": 4, "type": "ShutterFlash"}],
        "emphasis_moments": [
            {"type": "punchline", "intensity": "high", "word_indices": [5],
             "zoom_effect": {"type": "SmoothPush", "events": [{"startMs": 0}]},
             "motion_graphic": {"type": "IconLabel", "props": {}}},
            {"type": "statement", "intensity": "medium", "word_indices": [8],
             "zoom_effect": {"type": "StepZoom", "events": []}, "motion_graphic": None},
        ],
    }

def em_zooms(p): return [ (m.get("zoom_effect") is not None) for m in p["emphasis_moments"] ]
def em_mgs(p): return [ (m.get("motion_graphic") is not None) for m in p["emphasis_moments"] ]

# no-op (default / flag-off): edit_plan byte-identical
p = full_plan(); orig = copy.deepcopy(p)
rem, kept = H._enforce_off_expressive_features(p, set())
check("off={} → edit_plan UNCHANGED (bias-to-on / flag-off identical)", p == orig, "mutated!")
check("off={} → removed empty, kept all 7", rem == [] and len(kept) == 7)

# each expressive off individually → that feature absent, others intact
def assert_only_stripped(feature, checks_absent, checks_present_keys):
    p = full_plan()
    rem, kept = H._enforce_off_expressive_features(p, {feature})
    ok = all(cond(p) for cond in checks_absent)
    # everything NOT in this feature's footprint stays populated
    present = all(p.get(k) for k in checks_present_keys)
    check(f"off={{{feature}}} → stripped & isolated", ok and present and rem == [feature] and feature not in kept)

assert_only_stripped("broll", [lambda p: p["broll_clips"] == []],
                     ["sound_effects", "text_overlays", "motion_graphics", "transitions", "tight_cut_overlays"])
assert_only_stripped("sfx", [lambda p: p["sound_effects"] == []],
                     ["broll_clips", "text_overlays", "motion_graphics", "transitions"])
assert_only_stripped("text_overlays", [lambda p: p["text_overlays"] == []],
                     ["broll_clips", "sound_effects", "motion_graphics", "transitions"])
assert_only_stripped("captions",
                     [lambda p: p["caption_style"] == "none", lambda p: p["caption_keywords"] == [],
                      lambda p: p["caption_position_changes"] == []],
                     ["broll_clips", "sound_effects", "motion_graphics", "transitions"])

# zoom: emphasis zoom_effect nulled, motion_graphic + other arrays intact
p = full_plan(); H._enforce_off_expressive_features(p, {"zoom"})
check("off={zoom} → all zoom_effect null", em_zooms(p) == [False, False])
check("off={zoom} → motion_graphic preserved", em_mgs(p) == [True, False])
check("off={zoom} → other arrays intact", p["broll_clips"] and p["motion_graphics"] and p["transitions"])

# motion_graphics: top-level [] AND emphasis motion_graphic null; zoom preserved
p = full_plan(); H._enforce_off_expressive_features(p, {"motion_graphics"})
check("off={motion_graphics} → top-level []", p["motion_graphics"] == [])
check("off={motion_graphics} → emphasis motion_graphic null", em_mgs(p) == [False, False])
check("off={motion_graphics} → zoom_effect preserved", em_zooms(p) == [True, True])

# transitions: transitions AND tight_cut_overlays both cleared
p = full_plan(); H._enforce_off_expressive_features(p, {"transitions"})
check("off={transitions} → transitions [] AND tight_cut_overlays []",
      p["transitions"] == [] and p["tight_cut_overlays"] == [])

# only-captions: captions kept, all 6 others stripped
p = full_plan()
rem, kept = H._enforce_off_expressive_features(p, set(EXPR) - {"captions"})
check("only-captions → captions intact", p["caption_style"] == "Prime" and p["caption_keywords"] == ["alpha", "beta"])
check("only-captions → broll/sfx/text/mg/transitions all stripped",
      p["broll_clips"] == [] and p["sound_effects"] == [] and p["text_overlays"] == []
      and p["motion_graphics"] == [] and p["transitions"] == [] and em_zooms(p) == [False, False])
check("only-captions → kept==[captions]", kept == ["captions"])

# combo off={broll,sfx}: both gone, rest intact
p = full_plan(); rem, kept = H._enforce_off_expressive_features(p, {"broll", "sfx"})
check("combo {broll,sfx} → both stripped, rest intact",
      p["broll_clips"] == [] and p["sound_effects"] == [] and p["motion_graphics"] and p["transitions"]
      and set(rem) == {"broll", "sfx"})

# baseline feature in off-set must NOT touch expressive arrays (baseline gates elsewhere)
p = full_plan(); orig = copy.deepcopy(p)
rem, kept = H._enforce_off_expressive_features(p, {"filler_trim", "stabilize", "audio_denoise"})
check("off={baseline only} → enforcement no-op on expressive (baseline gates elsewhere)", p == orig and rem == [])

# "raw + no captions" mixed: captions stripped, baseline ignored here
p = full_plan(); H._enforce_off_expressive_features(p, {"captions", "filler_trim", "stabilize", "audio_denoise"})
check("mixed raw+captions → captions stripped, other expressive intact",
      p["caption_style"] == "none" and p["broll_clips"] and p["motion_graphics"])

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL MATRIX CASES PASS")
