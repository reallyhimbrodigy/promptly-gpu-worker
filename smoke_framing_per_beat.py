#!/usr/bin/env python3
"""Framing is a per-beat choice, and it is offered, built and defaulted.

ZAC RULED IT 2026-09-08 AND IT WAS NEVER BUILT. Every non-9:16 source was
cover-cropped: screen_recording delivered at 68% crop_loss with every heading
cut mid-word ("Point me in", "Where I can f"), which is why that content class
has no route. Landscape and square uploads are normal uploads and must never
be refused — so the choice is fit / crop / blur-fill, per beat, by the agent,
blur-fill when it cannot tell.

FOUR PROPERTIES, and the last one is the one that protects everything else:
  1. the ruling surfaces OFFER it (a builder for a field nobody can rule is
     dead code, and a field nobody builds is a promise);
  2. each mode produces a DIFFERENT filter, and blur/fit lose nothing;
  3. the default is blur, not crop — an unruled beat keeps its whole frame;
  4. A CONFORMING SOURCE IS UNTOUCHED. 9:16 in, identical filter out,
     whatever the framing says — so this cannot change any of the four
     fixtures that were already right.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

fail = 0

# 1. offered on both ruling surfaces
_sch = json.dumps(list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS))
if _sch.count('"framing"') < 2:
    print(f"  *** `framing` appears on {_sch.count('\"framing\"')} ruling "
          f"surface(s), needs both — a builder for a field nobody can rule "
          f"is dead code")
    fail += 1
for _m in ("blur", "fit", "crop"):
    if f'"{_m}"' not in _sch:
        print(f"  *** {_m!r} is not in the framing enum")
        fail += 1

# 2/3. the modes differ, and the default keeps the frame
LAND = (3826, 2160)
mods = {}
for _f in ("blur", "fit", "crop", None):
    filt, mode, loss = A.geometry_normalise_filter(*LAND, framing=_f)
    mods[_f] = (filt, mode, loss)
if len({v[0] for v in mods.values()}) < 3:
    print("  *** the framing modes do not produce distinct filters: "
          f"{ {k: v[1] for k, v in mods.items()} }")
    fail += 1
if mods["crop"][2] in (None, 0.0):
    print("  *** crop reports no crop_loss on a landscape source — the loss "
          "is the whole point of reporting it")
    fail += 1
for _f in ("blur", "fit"):
    if mods[_f][2]:
        print(f"  *** {_f} reports crop_loss {mods[_f][2]} — it loses nothing")
        fail += 1
if mods[None][1] != "blur_fill":
    print(f"  *** an UNRULED beat defaults to {mods[None][1]!r}, not blur_fill "
          f"— the default must keep the whole frame")
    fail += 1

# 4. a conforming source is untouched, whatever framing says
CONF = [(1080, 1920), (720, 1272), (540, 960)]
for wh in CONF:
    got = {A.geometry_normalise_filter(*wh, framing=_f)[0]
           for _f in ("blur", "fit", "crop", None)}
    if len(got) != 1:
        print(f"  *** {wh[0]}x{wh[1]} (already 9:16) renders differently by "
              f"framing — framing must not touch a conforming source")
        fail += 1

# the split is at beat boundaries, and an unruled stretch is None not a hole
segs = A.split_spans_by_framing([[0, 10]], [(0, 4, "crop"), (6, 10, "blur")])
if [(round(a, 2), round(b, 2), f) for a, b, f in segs] != \
        [(0.0, 4.0, "crop"), (4.0, 6.0, None), (6.0, 10.0, "blur")]:
    print(f"  *** split_spans_by_framing lost or mis-assigned a stretch: {segs}")
    fail += 1
if sum(b - a for a, b, _ in segs) != 10.0:
    print(f"  *** the split does not cover the kept span: {segs}")
    fail += 1

# and build_cut actually takes them
import inspect                                                   # noqa: E402
_src = inspect.getsource(A.edit) if hasattr(A, "edit") else open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "agentic_editor_app.py")).read()
if "def build_cut(keep_spans, words_per_cue=4, framing_spans=None)" not in _src:
    print("  *** build_cut does not accept framing_spans")
    fail += 1
if "build_cut(merged, framing_spans=_fr_spans)" not in _src:
    print("  *** execute_plan does not PASS the rulings to build_cut — the "
          "field would be accepted and ignored")
    fail += 1

print(f"smoke_framing_per_beat: {fail} wrong")
sys.exit(1 if fail else 0)
