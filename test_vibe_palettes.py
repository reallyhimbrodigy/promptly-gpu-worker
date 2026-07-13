"""PART 2 — vibe-aware component palettes (Zac 2026-07-12). The free-text vibe maps
to one of four palette families (corporate/viral/educational/story), each a DEFAULT
toolkit taught in the prompt — below user instructions, above Gemini's per-moment
pick. Specific-sound negatives ('no booms') suppress one sound even against the vibe
palette. Caption SPEED is universal (MAX_ENTRANCE_MS), vibe-independent."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

# ── classifier: keyword → family, precedence, fallback ──
check("'corporate product explainer' → corporate (restraint wins over 'explainer')",
      H._classify_vibe("a corporate product explainer") == "corporate")
check("'high energy viral tiktok' → viral", H._classify_vibe("high energy viral tiktok") == "viral")
check("'calm cinematic storytime' → story", H._classify_vibe("a calm cinematic storytime") == "story")
check("'how-to tutorial' → educational", H._classify_vibe("how-to tutorial") == "educational")
check("NO keyword match → viral (default, typical creator + fullest kit)", H._classify_vibe("just make it good") == "viral")
check("EMPTY vibe → viral (default, coherent palette guaranteed)", H._classify_vibe("") == "viral")
check("MULTIPLE ('fun corporate explainer') → corporate (restraint precedence)",
      H._classify_vibe("fun corporate explainer") == "corporate")

# ── palette block: the tonal splits ──
_corp = H._vibe_palette_block("corporate saas demo")
check("corporate palette: QUIET-only SFX, NO booms", "QUIET only" in _corp and "NO booms" in _corp)
check("corporate palette: CleanCut captions", "CleanCut" in _corp)
_vir = H._vibe_palette_block("viral hype reel")
check("viral palette: the FULL SFX kit (boom, dings, comedic)",
      "boom" in _vir and "iphoneding" in _vir and "wompwomp" in _vir)
check("viral palette: kinetic captions (Prime/Pulse/TwoTone/Gadzhi)",
      "Prime" in _vir and "Pulse" in _vir)

# ── specific-sound negatives (user wins over the palette) ──
check("'no booms' → {boom} (specific, not all SFX)", H._parse_sound_negatives("viral but no booms") == {"boom"})
check("'no dings and no whooshes' → the mapped sounds",
      H._parse_sound_negatives("no dings and no whooshes") == {"iphoneding", "swoosh-sound-effects", "woosh-professional"})
check("a REQUESTED boom in corporate is NOT a negative (user gets their boom)",
      H._parse_sound_negatives("corporate but add a boom on the payoff") == set())
_pl = {"emphasis_moments": [{"sound": "boom"}, {"sound": "punchsfx"}], "sound_effects": [{"sound": "boom", "word_index": 3}]}
H._enforce_sound_negatives(_pl, {"boom"})
check("'no booms' strips boom (→voice), keeps punchsfx, removes the discrete boom",
      _pl["emphasis_moments"][0]["sound"] == "voice" and _pl["emphasis_moments"][1]["sound"] == "punchsfx"
      and _pl["sound_effects"] == [])

# ── caption SPEED is universal (vibe sets style, never speed) ──
_helper = open("src/remotion/src/captions/shared/fadeTiming.ts").read()
check("MAX_ENTRANCE_MS cap exists (universal fast floor)", "MAX_ENTRANCE_MS = 80" in _helper)
for _st in ("Lumen/Lumen", "Cove/Cove", "Quintessence/Quintessence"):
    _s = open(f"src/remotion/src/captions/{_st}.tsx").read()
    check(f"story style {_st} is fast-capped (vibe never reintroduces slow)",
          "MAX_ENTRANCE_MS" in _s or "/ 60" in _s or "boundedFade" in _s)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL VIBE-PALETTE CASES PASS")
