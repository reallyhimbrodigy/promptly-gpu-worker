#!/usr/bin/env python3
"""SMOKE — a plan crossing into ChatCut is written in ChatCut's primitives.

Our families are a schema for OUR builder: text, card, sfx, zoom, cutaway,
transition. ChatCut's are timeline items, motion graphics, tracks, captions.
Where the two meet unmapped the agent spends turns reconciling them — measured
at TEN in the 999s run, eight of them guessing the parameter name for one
`adds` and two more guessing `geometry` then `rect`.

The legs drive the shipped translator. They do not restate the map.
"""
import re
import sys

import plan_for_chatcut as T

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


FULL = dict(beat=0, treatment=["text"], text_content="X", src_t0=0.0,
            src_t1=5.76, purpose="hook", why="w", size="large", case="upper",
            where="upper_third", colour="white_on_footage", hold_s=2.5)

# A POPULATION CAN BE EMPTY AND ASSERT NOTHING — both arms need a floor, or a
# map with every family verified would silently test nothing on the first arm.
check("there is at least one unverified family to refuse",
      any(not v["verified"] for v in T.FAMILY_MAP.values()),
      "every family is verified — the refusal arm now asserts nothing")
check("there is at least one verified family to pass",
      any(v["verified"] for v in T.FAMILY_MAP.values()))

# ── 1. AN UNMAPPED FAMILY IS REFUSED AT THE BOUNDARY ────────────────────────
# NAMED, NOT COUNTED. A family that quietly loses its mapping is the one that
# reaches the agent as prose, and a total would stay green while it happened.
# DERIVED FROM THE MAP, NOT RESTATED. This leg hardcoded zoom and sfx as
# families that must be refused; the day both were verified against the live
# API the check went red for asserting a fact that had changed. A check that
# restates its subject has to be edited every time the subject moves, and the
# edit is where it silently stops matching. Ask the map instead.
for fam in sorted(f for f, v in T.FAMILY_MAP.items() if not v["verified"]):
    try:
        T.refuse_unmapped({fam})
        check(f"unmapped family `{fam}` is REFUSED", False,
              "it passed — this family would reach the agent unmapped")
    except T.Unmapped as e:
        check(f"unmapped family `{fam}` is REFUSED", True)
        check(f"  ...and the refusal NAMES `{fam}`", fam in str(e))

# ── 2. A VERIFIED FAMILY PASSES ─────────────────────────────────────────────
# The other arm. A gate that refuses everything is not a gate, and these three
# are the only shapes actually observed on a live ChatCut timeline.
for fam in sorted(f for f, v in T.FAMILY_MAP.items() if v["verified"]):
    try:
        T.refuse_unmapped({fam})
        check(f"verified family `{fam}` passes", True)
    except T.Unmapped as e:
        check(f"verified family `{fam}` passes", False, str(e)[:120])

# ── 3. EVERY CONTROL IS INDIVIDUALLY DEMANDED AT THE BOUNDARY TOO ───────────
try:
    T.refuse_incomplete([FULL])
    check("a complete placement is NOT refused", True)
except T.Incomplete as e:
    check("a complete placement is NOT refused", False, str(e)[:150])

for f in T.CONTROLS:
    try:
        T.refuse_incomplete([{**FULL, f: None}])
        check(f"a placement missing `{f}` IS refused", False)
    except T.Incomplete as e:
        check(f"a placement missing `{f}` IS refused", True)
        check(f"  ...and the refusal NAMES `{f}`", f in str(e), str(e)[:120])

check("a beat placing nothing is not asked for controls",
      T.refuse_incomplete([dict(beat=9, treatment=["none"])]) is None)

# ── 4. THE MAP ITSELF ───────────────────────────────────────────────────────
# `text` and `card` are one primitive in ChatCut. A plan that presents them as
# different kinds of object is the contradiction that cost the first run two
# motion graphics and a re-decide.
# THE CLAIM IS OBJECT KIND, NOT WORDING. Comparing the two prose strings made
# this leg fail the moment one description gained four words — a pattern tight
# enough to reject a correct implementation, in the smoke written to catch that.
check("`text` and `card` are the same KIND of ChatCut object",
      T.FAMILY_MAP["text"]["item_kind"] == T.FAMILY_MAP["card"]["item_kind"],
      f'{T.FAMILY_MAP["text"]["item_kind"]!r} vs {T.FAMILY_MAP["card"]["item_kind"]!r}')
check("every family declares an item_kind",
      all("item_kind" in v for v in T.FAMILY_MAP.values()),
      str([f for f, v in T.FAMILY_MAP.items() if "item_kind" not in v]))
check("`caption` is mapped as NOT an item",
      "NOT AN ITEM" in T.FAMILY_MAP["caption"]["primitive"])
check("no family is marked verified without an observed shape",
      all(("how" in v and v["how"]) for v in T.FAMILY_MAP.values()))

# ── 5. NO TWO INSTRUCTIONS MAY ADDRESS ONE ARRAY SLOT ──────────────────────
# The base video and the graphic BOTH said `edit_item adds[0]`. The agent made
# one call with one element and the title was never placed — twice, at 153.8s
# and 214s, both exiting 0 with a green visual pass. A plan that numbers two
# different things into the same slot is an unsatisfiable instruction wearing a
# precise one's clothes.
import subprocess, tempfile, os
_pl = "/tmp/plan2.json"
if os.path.exists(_pl):
    _out = tempfile.mktemp(suffix=".md")
    subprocess.run([sys.executable, "plan_for_chatcut.py", _pl, _out, "--staged"],
                   capture_output=True)
    _txt = open(_out, encoding="utf-8").read() if os.path.exists(_out) else ""
    _ix = re.findall(r"edit_item adds\[(\d+)\]", _txt)
    check("the emitted plan numbers every add", bool(_ix), "none found")
    check("no two adds share an index", len(_ix) == len(set(_ix)),
          f"indices: {_ix}")
    check("the indices are contiguous from 0",
          sorted(int(i) for i in _ix) == list(range(len(_ix))),
          f"indices: {_ix}")
    check("the plan states how many adds it names",
          "THE PLAN NAMES" in _txt)
else:
    print("  [--] add-index legs SKIPPED: no ruling at /tmp/plan2.json")

print(("FAIL %d" % len(fails)) if fails else "OK")
sys.exit(1 if fails else 0)
