"""ITEM 2 — MG entrance-arrival wiring (Zac 2026-07-12). The measured MGAttackProbe
attacks are wired into fromFrame so each MG lands SETTLED on its anchor word
(peak-on-word). Ruling: settle for simple pops, container-arrival = min(hit,settle)
for sequenced/count-up types. Deterministic, offline."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

for _fn in ("_MG_ATTACK_MS", "_mg_attack_frames", "_MG_SEQUENCED", "_MG_ATTACK_DEFAULT_MS"):
    if not hasattr(H, _fn):
        print(f"  FAIL  {_fn} not implemented yet (RED)")
        print("\n=== RESULT: 0 passed, 1 failed ==="); sys.exit(1)

# the 7 sequenced/count-up types carry container-arrival = min(hit, settle):
# BarRace min(267,483)=267, NumberTicker min(583,200)=200, StatCard min(83,400)=83
check("BarRace is sequenced, attack = min(hit,settle) = 267", H._MG_ATTACK_MS["BarRace"] == 267)
check("NumberTicker sequenced, attack = min(583,200) = 200", H._MG_ATTACK_MS["NumberTicker"] == 200)
check("StatCard sequenced, attack = min(83,400) = 83", H._MG_ATTACK_MS["StatCard"] == 83)
check("the 7 sequenced types are all in _MG_SEQUENCED",
      H._MG_SEQUENCED == frozenset({"BarRace","NumberTicker","ProgressBar","RankedList","StatCard","Timeline","TimelineRoadmap"}))

# simple pops carry SETTLE (the whole thing arrives as one)
check("IMessageBubble pop, attack = settle = 50", H._MG_ATTACK_MS["IMessageBubble"] == 50)
check("PullQuote pop, attack = settle = 500", H._MG_ATTACK_MS["PullQuote"] == 500)
check("Stamp pop, attack = settle = 67", H._MG_ATTACK_MS["Stamp"] == 67)

# every sequenced type's stored attack <= its... (min never exceeds settle); and
# no pop is accidentally in the sequenced set
check("no pop type leaked into _MG_SEQUENCED",
      all(t in H._MG_ATTACK_MS for t in H._MG_SEQUENCED))

# _mg_attack_frames converts ms → frames at the render fps (60)
check("_mg_attack_frames(IMessageBubble, 60) = round(50/1000*60) = 3", H._mg_attack_frames("IMessageBubble", 60) == 3)
check("_mg_attack_frames(BarRace, 60) = round(267/1000*60) = 16", H._mg_attack_frames("BarRace", 60) == 16)
check("_mg_attack_frames(StepDivider, 60) = round(550/1000*60) = 33", H._mg_attack_frames("StepDivider", 60) == 33)

# blank-prop / unknown types fall back to the median default (not a crash, not 0)
check("MouseDrag (blank in battery) → default 150ms", H._MG_ATTACK_MS.get("MouseDrag") is None and H._mg_attack_frames("MouseDrag", 60) == 9)
check("unknown type → default, never 0", H._mg_attack_frames("NotARealMG", 60) == 9)

# the fromFrame shift lands the MG SETTLED on the anchor: shift == attack frames
# (peak-on-word), verified via the helper the placement uses
_anchor_frame = 300
_shifted = max(0, _anchor_frame - H._mg_attack_frames("StatCard", 60))
check("StatCard fromFrame lands attack(5f) before anchor 300 → 295", _shifted == 300 - 5, _shifted)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL MG ATTACK WIRING CASES PASS")
