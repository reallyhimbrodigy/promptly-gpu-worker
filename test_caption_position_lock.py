"""GAP 1B — user caption-position lock (Zac 2026-07-12). "captions at the bottom
middle" still drifted a caption to the top toward the end. An explicit user position
instruction is now a HARD LOCK: every caption pinned to that band for the whole
video, above the default, Gemini's choices, and the overlay/composer force-flips —
a colliding accent relocates, the caption never moves."""
import sys
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

# ── parse ──
check("'captions at the bottom' → bottom", H._parse_caption_position_lock("captions at the bottom") == "bottom")
check("'keep the captions on top' → top", H._parse_caption_position_lock("keep the captions on top") == "top")
check("'captions bottom middle' → bottom (middle is horizontal; band is vertical)",
      H._parse_caption_position_lock("captions bottom middle") == "bottom")
check("'subtitles in the center' → center", H._parse_caption_position_lock("put subtitles in the center") == "center")
check("no position instruction → None", H._parse_caption_position_lock("make it punchy, no zooms") is None)
check("'bottom drawer' with no caption word → None (no false positive)",
      H._parse_caption_position_lock("a video about my bottom drawer") is None)

# ── composer: the lock pins captions + relocates a colliding accent ──
mgs = [{"type": "StatCard", "fromFrame": 0, "durationInFrames": 120, "props": {"anchor": "bottom"}}]
_c = H._compose_band_occupancy([{"fromFrame": 0, "toFrame": 120, "position": "top"}], mgs, [], [],
                               shadow=False, caption_lock="bottom")
_cap = {band for (_a, _b, band) in _c["caption_track"]}
_mgb = {band for (_a, _b, band) in (_c["element_bands"].get("mg0") or [])}
check("captions pinned to the locked band (bottom), ignoring Gemini's authored 'top'", _cap == {"bottom"}, _cap)
check("an MG that wanted the locked band RELOCATES off it (caption never moves)", "bottom" not in _mgb, _mgb)

# lock survives a B-roll window (which normally forces captions to top)
_c2 = H._compose_band_occupancy([{"fromFrame": 0, "toFrame": 120, "position": "bottom"}], [], [],
                                [(0, 120)], shadow=False, caption_lock="bottom")
check("lock survives a B-roll window (would otherwise force top)",
      {band for (_a, _b, band) in _c2["caption_track"]} == {"bottom"})

# no lock → normal behavior (composer picks a free band)
_c3 = H._compose_band_occupancy([{"fromFrame": 0, "toFrame": 120, "position": "bottom"}], [], [],
                                [], shadow=False, caption_lock=None)
check("no lock → captions use the authored band (bottom)",
      {band for (_a, _b, band) in _c3["caption_track"]} == {"bottom"})

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL CAPTION-POSITION-LOCK CASES PASS")
