"""WS1 — the SFX perceptual ATTACK table (Zac 2026-07-12). Every SFX has an
INDIVIDUALLY MEASURED envelope-peak attack (ms, from file start); the mixer
schedules each at (placement − ATTACK) so the COMPENSATED PEAK lands on the
word — peak-on-word, the same derivation ZOOM_PEAK_REACH_MS applies to zooms.
The attack subsumes the old onset offset (no double-compensation). Offline."""
import sys
import typing

import handler as H

PASS = []
FAIL = []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

_SFX = set(typing.get_args(H._SFX_SOUNDS))
_src = open("handler.py").read()

# ─── complete, individual coverage — no sound falls to a generalized default ─
check("_SFX_ATTACK_MS covers EVERY SFX (individually measured, never generalized)",
      _SFX <= set(H._SFX_ATTACK_MS.keys()), _SFX - set(H._SFX_ATTACK_MS.keys()))
check("the onset-offset table is REPLACED by the attack table (no double-compensation)",
      "_SFX_ONSET_OFFSETS" not in _src)

# ─── the derivation: schedule at (placement − attack), BOTH homes ───────────
check("emphasis-beat SFX schedules at (placement − attack)",
      "_attack = _SFX_ATTACK_MS.get(_sound_style, 0) / 1000.0" in _src
      and "_ts = max(0.0, _projected_t - _attack)" in _src)
check("transition-rider SFX schedules at (placement − attack)",
      "_rs_attack = _SFX_ATTACK_MS.get(_rs_style, 0) / 1000.0" in _src
      and "_rs_ts = max(0.0, _rs_t - _rs_attack)" in _src)
# unified with the zoom peak-reach (the same peak-on-word class)
check("zooms already use the peak-on-word reach (ZOOM_PEAK_REACH_MS) — one class",
      "ZOOM_PEAK_REACH_MS" in _src and isinstance(H.ZOOM_PEAK_REACH_MS, dict))

# ─── individually measured: impulsive short, swell long (not generalized) ───
check("impulsive sounds have short attacks (<100ms)",
      all(H._SFX_ATTACK_MS[s] < 100 for s in
          ("popsfx", "punchsfx", "mouse-click-sound", "iphoneding", "swoosh-sound-effects")),
      {s: H._SFX_ATTACK_MS[s] for s in ("popsfx", "punchsfx", "mouse-click-sound", "iphoneding", "swoosh-sound-effects")})
check("swell sounds have long attacks (>250ms) — start under preceding words (correct by derivation)",
      all(H._SFX_ATTACK_MS[s] > 250 for s in
          ("boom", "money-ching", "woosh-professional", "wompwomp", "imposter")),
      {s: H._SFX_ATTACK_MS[s] for s in ("boom", "money-ching", "woosh-professional", "wompwomp", "imposter")})
check("the shutter's peak-attack subsumes its 76ms leading silence (127ms)",
      H._SFX_ATTACK_MS["camera-flash"] == 127)

# ─── sanity: no absurd values ───────────────────────────────────────────────
check("all attacks within a sane 0..1500ms range",
      all(isinstance(v, int) and 0 <= v <= 1500 for v in H._SFX_ATTACK_MS.values()),
      {k: v for k, v in H._SFX_ATTACK_MS.items() if not (0 <= v <= 1500)})

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
print("ALL WS1 ATTACK-TABLE CASES PASS")
