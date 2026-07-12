"""Camera-shutter swap (Zac 2026-07-12): the DSLR shutter (camera-flash key)
has EXACTLY TWO homes — (1) the diegetic emphasis beat (photo-moment scenario)
and (2) the transition rider (the snapping-cut scenario). Neither leaks into
the other's surface; the two scenarios discriminate. Deterministic, offline."""
import os
import sys
import typing

import handler as H

PASS = []
FAIL = []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

_SFX = set(typing.get_args(H._SFX_SOUNDS))
_DEC = set(typing.get_args(H._SOUND_DECISION))
_src = open("handler.py").read()

# ─── file swapped; key = filename stem (the resolution seam) ────────────────
# get_sfx_path builds SFX_SOUNDS_DIR/{normalize(key)}.mp3; the deploy source of
# truth is src/assets/sounds (bundled to /assets/sounds on Modal). Assert the
# stem seam + the source file, not the env-dependent local dir resolution.
check("camera-flash key normalizes to its own stem (key=stem seam)",
      H.normalize_sfx_style("camera-flash") == "camera-flash")
check("the deploy source file exists (src/assets/sounds/camera-flash.mp3)",
      os.path.exists("src/assets/sounds/camera-flash.mp3"))
check("get_sfx_path builds the {stem}.mp3 candidate", "{normalized}.mp3" in
      open("handler.py").read().split("def get_sfx_path", 1)[1][:400])

# ─── measured attack (WS1): the shutter peak-attack subsumes its 76ms silence ─
check("WS1 attack table carries the shutter's measured peak (127ms, 76ms silence inside it)",
      H._SFX_ATTACK_MS.get("camera-flash") == 127,
      H._SFX_ATTACK_MS.get("camera-flash"))

# ─── HOME 1: the diegetic emphasis beat ─────────────────────────────────────
check("home 1: camera-flash on the emphasis-beat surface (_SFX_SOUNDS)", "camera-flash" in _SFX)
check("home 1: rides the sound-decision enum too (_SFX_SOUNDS ∪ voice)", "camera-flash" in _DEC)
check("camera-flash has a mix category (medium)", H._SFX_CATEGORIES.get("camera-flash") == "medium")
check("home 1 scenario is the diegetic PHOTO moment",
      "**camera-flash**" in _src and "photo or screenshot is taken" in _src)

# ─── HOME 2: the transition rider (the new home) ────────────────────────────
seams = [{"awi": 5, "gap_ms": 2000, "kind": "cut"}]
schema, _cc, _oc = H._build_transitions_subcall_schema(seams)
_variants = schema["properties"]["cut_boundary_transitions"]["items"]["anyOf"]
_sound_enum = _variants[0]["properties"]["sound"]["enum"]
check("home 2: transition-rider sound enum has BOTH members (construction probe)",
      set(_sound_enum) == {"transition-sfx", "camera-flash"}, _sound_enum)
check("home 2: the rider sound field is still nullable (omittable per seam)",
      _variants[0]["properties"]["sound"].get("nullable") is True)
check("home 2 scenario is the SNAPPING CUT (distinct from the sweep)",
      "snapping picture-change" in _src or "snaps a single decisive cut" in _src)
# the rider path accepts ANY schema-emitted sound (no transition-sfx-only whitelist)
check("rider carries the sound verbatim (no whitelist gate at the store site)",
      'clip["_transition_sound"] = str(tr["sound"])' in _src)

# ─── THE BOUNDARY: exactly the two intended surfaces, two distinct scenarios ─
# the transition scenario names the shutter as a CUT; the beat scenario names it
# as a PHOTO — the discriminator is the scenario, per the library doctrine.
check("boundary: the two scenarios discriminate (photo-moment vs snapping-cut)",
      ("photo or screenshot" in _src) and ("DSLR shutter" in _src) and ("decisive cut" in _src))
# no THIRD surface: the shutter is NOT offered on any zoom-event sound enum
# (there is no zoom sound surface — sounds live only on emphasis beats + the
# transition rider). Assert the rider enum is the ONLY schema enum that gained it.
_rider_enum_lines = [ln for ln in _src.splitlines()
                     if '"sound"' in ln and "enum" in ln and "transition-sfx" in ln]
check("boundary: exactly ONE schema sound-enum offers the transition rider",
      len(_rider_enum_lines) == 1, _rider_enum_lines)
check("boundary: that rider enum contains camera-flash",
      _rider_enum_lines and "camera-flash" in _rider_enum_lines[0])

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
print("ALL SHUTTER TWO-HOMES CASES PASS")
