"""B-ROLL CAPTION PLACEMENT (Zac 2026-07-13). Zac caught a caption placed RIGHT OVER
the face at the TOP of a b-roll clip, middle/lower empty. Root: the pipeline is blind
to b-roll content (face detection runs only on the SOURCE speaker), and the composer
force-flipped captions to TOP during every b-roll window on an inverted assumption
("top is the safe zone") — but portrait Pexels clips of people/places put the SUBJECT'S
FACE at the top. The lower third is the clear zone. Fix: over b-roll, captions default
LOWER (bottom), never top; center only if an MG already holds the bottom."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def pos_at(out, f):
    for s in out:
        if int(s["fromFrame"]) <= f < int(s["toFrame"]):
            return s["position"]
    return None

SEG = [{"fromFrame": 0, "toFrame": 800, "position": "top"}]  # even if Gemini said top

# ── b-roll alone → captions LOWER (bottom), never top (the clear zone under the face) ──
_out = H._force_caption_position_around_overlays(SEG, [], [(150, 250)])
check("b-roll window → captions BOTTOM (clear of the upper-center subject), not top",
      pos_at(_out, 180) == "bottom", pos_at(_out, 180))
check("b-roll NEVER forces top (the face zone)",
      all(s["position"] != "top" for s in _out if 150 <= s["fromFrame"] < 250), _out)

# ── b-roll + an MG holding the bottom → center (bottom taken), still never top ──
_mg_bottom = [{"type": "StatCard", "fromFrame": 150, "durationInFrames": 100, "props": {"anchor": "bottom"}}]
_out2 = H._force_caption_position_around_overlays(SEG, _mg_bottom, [(150, 250)])
check("b-roll + MG-at-bottom → captions CENTER (bottom occupied), never top",
      pos_at(_out2, 180) == "center", pos_at(_out2, 180))

# ── outside b-roll: unchanged (MG rules still apply as before) ──
_seg_b = [{"fromFrame": 0, "toFrame": 800, "position": "bottom"}]
_mg_top = [{"type": "Notification", "fromFrame": 300, "durationInFrames": 100, "props": {}}]
_out3 = H._force_caption_position_around_overlays(_seg_b, _mg_top, [])
check("MG at top (no b-roll) → captions bottom (unchanged behavior)", pos_at(_out3, 350) == "bottom")
check("outside any window → Gemini's choice preserved", pos_at(_out3, 50) == "bottom")

# ── the prompt no longer tells Gemini captions go TOP during b-roll ──
_src = open("handler.py").read()
check("prompt teaches captions go to the LOWER third during b-roll (not top)",
      "to the top during B-roll" not in _src)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL B-ROLL-CAPTION-PLACEMENT CASES PASS")
