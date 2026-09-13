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

# THE CLOCK IDENTITY. Framing changes the picture, never the length: the split
# must partition the kept spans exactly, or every output-to-source mapping in
# every sheet shifts silently.
for _spans, _fs in (([[0, 10]], [(0, 4, "crop"), (6, 10, "blur")]),
                    ([[0, 4], [6, 10]], [(2, 8, "fit")]),
                    ([[1.234, 5.678]], [(2.0, 3.0, "crop"), (3.0, 4.0, "blur")]),
                    ([[0, 10]], None)):
    _segs = A.split_spans_by_framing(_spans, _fs)
    _v = sum(b - a for a, b, _ in _segs)
    _s = sum(b - a for a, b in _spans)
    if abs(_v - _s) > 1e-6:
        print(f"  *** the split covers {_v}s of {_s}s — video and audio clocks "
              f"would diverge: {_segs}")
        fail += 1
# The assertion must be IN build_cut, not only in this file — checked on the
# AST so a comment mentioning it cannot satisfy it.
import ast                                                       # noqa: E402
_bc = next((n for n in ast.walk(ast.parse(open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "agentic_editor_app.py")).read()))
    if isinstance(n, ast.FunctionDef) and n.name == "build_cut"), None)
# THE PROPERTY ROSE, SO THE CHECK HAD TO. This looked for an `abs(...) > eps`
# comparison — the shape of the duration-sum identity that used to guard the
# framing split. That identity is TRUE UNDER ANY PERMUTATION of the segments:
# swap two and every frame after the swap carries the wrong sound while the sum
# stays equal. It has been replaced by av_spans_agree, which compares the
# SEQUENCES — the video segments must tile the audio spans in order, with no
# gap and no overlap — and that implies the duration identity as a corollary.
#
# So accept either: the stronger sequence contract, or the old sum for anyone
# who still spells it that way. A check pinned to the weaker shape would have
# failed the file for getting better, which is the calibrated-on-a-spelling
# trap this suite has now hit four times in one session.
_seq = _bc is not None and any(
    isinstance(n, ast.Call) and getattr(n.func, "id", "") == "av_spans_agree"
    for n in ast.walk(_bc))
_sum = _bc is not None and any(
    isinstance(n, ast.Compare) and isinstance(n.ops[0], ast.Gt)
    and any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "abs"
            for c in ast.walk(n.left))
    for n in ast.walk(_bc))
if not (_seq or _sum):
    print("  *** build_cut asserts NEITHER the span-sequence contract "
          "(av_spans_agree) nor the duration identity — a split that loses or "
          "reorders time would only surface as a shifted sheet")
    fail += 1
elif _seq:
    # AND THE STRONGER ONE MUST ACT ON A FAILURE, not merely compute it.
    _acts = any(isinstance(n, ast.Return) and "error" in ast.unparse(n)
                for n in ast.walk(_bc))
    if not _acts:
        print("  *** av_spans_agree is called and its FAILED state is never "
              "returned as an error — a contract that computes and does not "
              "refuse is the caption gate all over again")
        fail += 1

print(f"smoke_framing_per_beat: {fail} wrong")
sys.exit(1 if fail else 0)
