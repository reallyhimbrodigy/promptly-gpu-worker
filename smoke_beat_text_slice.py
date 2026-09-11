#!/usr/bin/env python3
"""A split beat carries its own words; a figure carries its instant; a card
lands on it; a placement records the moment it is for.

Four producer defects found by the round 51-52 placement judgment, all on the
same fixture (talking_head, 4 beats -> 7):
  * both halves of a split beat copied the parent's sentence, so beat 0 read
    "...10 times a day..." while "10" is spoken at 3.52s inside beat 1;
  * the beat offered the figure's VALUE and not its INSTANT, and the card was
    anchored at the beat start — 6 of 6 figure cards led their number by
    0.96-1.52s, both rounds, deterministically;
  * the card's time is derived by the harness from the beat start, so the fix
    is in the harness, not the prompt;
  * the placement record carried only the render start (attack_ms before the
    moment), so a reader put every card one beat early.

RED-proven by red_proof_beat_text_slice.py.
"""
import ast
import pathlib
import sys

import modal_stub                                              # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                 # noqa: E402

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []

# ast.unparse renders single quotes — a leg written against "t_start" in double
# quotes matches the LAYOUT of a literal, which is the mistake this file's own
# docstring family records. Read the AST nodes, not their rendering.
def _has_sub(node, key):
    return any(isinstance(x, ast.Subscript) and isinstance(x.slice, ast.Constant)
               and x.slice.value == key for x in ast.walk(node))


def _has_const(node, val):
    return any(isinstance(x, ast.Constant) and x.value == val for x in ast.walk(node))




def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


W = [{"w": "being", "s": 0.0, "e": 0.3}, {"w": "a", "s": 0.3, "e": 0.4},
     {"w": "creator", "s": 0.4, "e": 1.0}, {"w": "posting", "s": 2.1, "e": 2.5},
     {"w": "10", "s": 3.4, "e": 3.6}, {"w": "times", "s": 3.6, "e": 4.0}]
B = {"i": 0, "t_start": 0.0, "t_end": 5.84, "text": "being a creator posting 10 times"}

# ── THE SPLIT ───────────────────────────────────────────────────────────────
check("each half carries ITS OWN words",
      A.split_beat_text(B, 2.0, W) == ("being a creator", "posting 10 times"))
check("a half with no words inside says so instead of borrowing",
      A.split_beat_text({"t_start": 1.05, "t_end": 5.84, "text": "x"}, 1.5, W)[0]
      .startswith("[no words in"))
check("no words at all: the parent's text on both halves",
      A.split_beat_text(B, 2.0, None) == (B["text"], B["text"]))
check("neither half has words (an un-narrated edge split): parent kept",
      A.split_beat_text({"t_start": 10.0, "t_end": 12.0, "text": "[no narration] tail"}, 11.0, W)
      == ("[no narration] tail", "[no narration] tail"))
_out = A.subdivide_beats([dict(B)], words=W, shot_changes=[2.0])
check("subdivide_beats produces halves with their own words",
      len(_out) == 2 and [o["text"] for o in _out] == ["being a creator", "posting 10 times"],
      str([(o.get("t_start"), o.get("text")) for o in _out]))
_sub = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "subdivide_beats")
check("subdivide_beats CALLS split_beat_text (not a local copy)",
      any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "split_beat_text"
          for n in ast.walk(_sub)))

# ── THE INSTANT ─────────────────────────────────────────────────────────────
check("figure_instant: first numeric instant inside the beat",
      A.figure_instant({"t_start": 2.0, "t_end": 5.84}, {12.56, 3.52}) == 3.52)
check("figure_instant: None when no numeric instant falls inside",
      A.figure_instant({"t_start": 0.0, "t_end": 2.0}, {3.52}) is None)
check("figure_note shows the instant when it is known",
      A.figure_note({"figure": "10", "figure_t": 3.52}) == "  (figure: 10 spoken @3.52s)")
check("figure_note without an instant shows the figure alone",
      A.figure_note({"figure": "10"}) == "  (figure: 10)")
_ft_assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                       and t.slice.value == "figure_t" for t in n.targets)]
check("the beat's figure_t is assigned FROM figure_instant",
      any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "figure_instant"
          for a_ in _ft_assigns for c in ast.walk(a_.value)))
_fn_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "figure_note"]
check("both beat-line sites (brief and unruled list) call figure_note",
      len(_fn_calls) >= 2, f"{len(_fn_calls)} call(s)")

# ── THE CARD LANDS ON IT ────────────────────────────────────────────────────
_cst = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "_card_src_t" for t in n.targets)]
check("the card's source instant is chosen from figure_t",
      any(any(isinstance(x, ast.Name) and x.id == "_ft" for x in ast.walk(a_.value))
          for a_ in _cst)
      and any(_has_sub(a_.value, "t_start") for a_ in _cst),
      "the anchor must read figure_t with the beat start as the phrase-card fallback")
_at = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
       and any(getattr(t, "id", "") == "at" for t in n.targets)
       and any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "src_to_out"
               for c in ast.walk(n.value))]
_at_card = [a_ for a_ in _at if any(isinstance(x, ast.Name) and x.id == "_card_src_t"
                                    for x in ast.walk(a_.value))]
check("`at` is src_to_out of that chosen instant, not of the beat start",
      bool(_at_card) and not any(_has_sub(a_.value, "t_start") for a_ in _at_card))

# ── THE LEAD IS MEASURED ON ONE CLOCK AND PRINTED ───────────────────────────
def _setdefault_calls(key):
    """led.setdefault(<key>, ...)... — found by node shape, not by rendering."""
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        for c in ast.walk(n):
            if (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                    and c.func.attr == "setdefault" and c.args
                    and isinstance(c.args[0], ast.Constant) and c.args[0].value == key):
                out.append(n)
                break
    return out


_cvf_set = [n for n in _setdefault_calls("card_vs_figure")
            if isinstance(n.func, ast.Attribute) and n.func.attr == "append"]
check("card_vs_figure is ledgered", bool(_cvf_set))
def _dict_value(call, key):
    for d in (a_ for a_ in call.args if isinstance(a_, ast.Dict)):
        for k, v in zip(d.keys, d.values):
            if isinstance(k, ast.Constant) and k.value == key:
                return v
    return None


_lead = [_dict_value(n, "lead_s") for n in _cvf_set]
check("the lead subtracts figure_t ON THE OUTPUT CLOCK (src_to_out), not source vs output",
      any(v is not None
          and any(isinstance(x, ast.Name) and x.id == "_ft_out" for x in ast.walk(v))
          and not any(isinstance(x, ast.Name) and x.id == "_ft" for x in ast.walk(v))
          for v in _lead),
      "lead_s must be built from _ft_out (output clock) and never from _ft (source clock)")
_prints = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
           and getattr(n.func, "id", "") == "print"
           and "CARD vs FIGURE" in ast.unparse(n)]
check("and PRINTED, reading the ledgered list (not a bare header)",
      any(any(isinstance(x, ast.Name) and x.id in ("_cvf", "_cvf_m") for x in ast.walk(pn))
          for pn in _prints))
check("a beat without an instant reads ABSENT, never on-time",
      any(_has_const(n, "ABSENT") for n in _cvf_set))

# ── THE PLACEMENT RECORDS THE MOMENT ────────────────────────────────────────
_pl = [n for n in _setdefault_calls("placements")
       if isinstance(n.func, ast.Attribute) and n.func.attr == "append"]
_dicts = [a_ for c in _pl for a_ in c.args if isinstance(a_, ast.Dict)]
check("every placement record carries t_moment beside t_start",
      len(_dicts) >= 2 and all(
          any(isinstance(k, ast.Constant) and k.value == "t_moment" for k in d.keys)
          for d in _dicts), f"{len(_dicts)} record literal(s)")
check("a card's t_moment is its anchor_s (the moment), falling back to t",
      any(_has_const(d, "anchor_s") for d in _dicts))
check("a zoom's t_moment is its step's beat_at_s, not the pre-roll start",
      any(_has_const(d, "beat_at_s") for d in _dicts))
_cba = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
        and getattr(n.func, "id", "") == "card_beat_alignment" and n.args
        and isinstance(n.args[0], ast.Dict)]
check("card_beat_alignment is handed the card's SOURCE-clock instant, not _mg_at",
      any(any(isinstance(x, ast.Name) and x.id == "_card_src_t" for x in ast.walk(c.args[0]))
          and not any(isinstance(x, ast.Name) and x.id == "_mg_at" for x in ast.walk(c.args[0]))
          for c in _cba))

print()
if fails:
    print("BEAT-TEXT-SLICE: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("BEAT-TEXT-SLICE: PASS — halves carry their own words, the figure carries "
      "its instant, the card anchors on it, the lead is one-clock and printed, "
      "the placement records its moment")
