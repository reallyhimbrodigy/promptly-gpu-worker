"""ITEM 2 — the src↔kept SHAPE BRIDGE: the precise re-anchor Part 3 deferred.

When a re-edit CHANGES cuts, an out-of-scope word-anchored layer is RE-ANCHORED
to the nearest surviving SOURCE word (CONTENT byte-identical, only the anchor
position follows the cuts) — NOT dropped when a surviving word exists, NOT
re-authored. Range anchors snap inward (start forward, end backward — broll's
proven pattern at handler.py:11648); point anchors snap to the nearest survivor
(forward-first on a tie). A drop is correct ONLY when the whole span is gone.
Deterministic, offline."""
import sys

import handler as H

PASS = []
FAIL = []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


for _fn in ("_snap_forward", "_snap_backward", "_nearest_survivor",
            "_reanchor_entry_to_survivors"):
    if not hasattr(H, _fn):
        print(f"  FAIL  {_fn} not implemented yet (RED)")
        print("\n=== RESULT: 0 passed, 1 failed ===")
        sys.exit(1)


KEPT = [i for i in range(20) if i != 10]        # source word 10 was cut
KEPT_END = [i for i in range(20) if i < 15]     # 15..19 cut (nothing ahead)

# ─── snap primitives ────────────────────────────────────────────────────────
check("snap_forward past a cut → next survivor", H._snap_forward(10, KEPT) == 11)
check("snap_forward on a survivor → itself", H._snap_forward(12, KEPT) == 12)
check("snap_backward past a cut → prev survivor", H._snap_backward(10, KEPT) == 9)
check("snap_backward on a survivor → itself", H._snap_backward(8, KEPT) == 8)
check("nearest_survivor tie → forward-first", H._nearest_survivor(10, KEPT) == 11)
check("nearest_survivor on a survivor → itself", H._nearest_survivor(5, KEPT) == 5)
check("snap_forward with none ahead → None", H._snap_forward(17, KEPT_END) is None)
check("nearest falls back backward when none ahead", H._nearest_survivor(17, KEPT_END) == 14)

# ─── range entry: start snaps forward, end snaps backward; CONTENT preserved ─
mg = {"type": "StatCard", "start_word_index": 10, "end_word_index": 12,
      "props": {"value": "5000"}, "tag": "x"}
ra = H._reanchor_entry_to_survivors(mg, KEPT)
check("range: start re-anchored forward past the cut", ra["start_word_index"] == 11)
check("range: end unchanged (survivor)", ra["end_word_index"] == 12)
check("range: CONTENT byte-identical (props/type/tag preserved)",
      ra["props"] == {"value": "5000"} and ra["type"] == "StatCard" and ra["tag"] == "x")
check("re-anchor does not mutate the input", mg["start_word_index"] == 10)

# ─── point entry (caption_position_change) ──────────────────────────────────
cpc = {"word_index": 10, "position": "top"}
rc = H._reanchor_entry_to_survivors(cpc, KEPT)
check("point: word_index re-anchored to nearest survivor, content preserved",
      rc["word_index"] == 11 and rc["position"] == "top")

# ─── a surviving entry is byte-identical (unchanged) ────────────────────────
keep = {"word_index": 5, "position": "bottom"}
check("survivor entry unchanged", H._reanchor_entry_to_survivors(keep, KEPT) == keep)

# ─── the ONE correct drop: whole range gone → None ──────────────────────────
gone = {"start_word_index": 10, "end_word_index": 10, "props": {}}
check("range fully cut → None (drop only when NO survivor exists)",
      H._reanchor_entry_to_survivors(gone, KEPT) is None)

# ─── word_indices list (emphasis) snaps each member ─────────────────────────
em = {"word_indices": [10], "kind": "z"}
re_ = H._reanchor_entry_to_survivors(em, KEPT)
check("word_indices re-anchored to survivor, content preserved",
      re_["word_indices"] == [11] and re_["kind"] == "z")

# ─── transition (after_word_index) point-snaps ──────────────────────────────
tr = {"after_word_index": 10, "type": "whip"}
rt = H._reanchor_entry_to_survivors(tr, KEPT)
check("transition after_word_index re-anchored", rt["after_word_index"] == 11 and rt["type"] == "whip")

# ─── idempotence: re-anchor of a re-anchored entry is a fixed point ─────────
check("re-anchor idempotent (survivor anchors unchanged)",
      H._reanchor_entry_to_survivors(ra, KEPT) == ra)


print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
print("ALL SHAPE-BRIDGE RE-ANCHOR CASES PASS")
