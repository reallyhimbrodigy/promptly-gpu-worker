#!/usr/bin/env python3
"""SMOKE: the motion-graphic catalogue is reachable — 29 types, not one.

THE GAP WAS NEVER THE PROSE. knowledge/05_motion_graphics.md has been MOUNTED
the whole time — 36,674 chars, every selectable type with its claim, its
FITS/FIGHTS and its props shape. The agent could read it and could not act on
it, because the harness placed `"type": "StatCard"` at one hardcoded site
whatever the ruling said. That is the entire "1 of 29".

TWENTY-NINE, NOT THIRTY-ONE, and the difference is not a rounding error.
VALID_MG_TYPES has 31; two of them are BRAND components the pipeline emits from
brand settings, and production's own prompt says so:

    "These render as the `NamePlate` and `EndCard` components. DO NOT put
     `NamePlate` or `EndCard` in `motion_graphics` yourself — the pipeline
     builds [them]"                                      (handler.py:2784)

Neither appears in the catalogue prose at all — production cannot place them
from a ruling either. Offering them would be MORE than parity, and the ruling is
"no more and no less".

THE TYPE IS THE ONE THING THE HARNESS CANNOT DERIVE. A quoted headline number is
a StatCard, an ordered set is a RankedList, a verbatim line is a PullQuote — the
choice reads the DIALOGUE, not the timing. Zoom's type comes from an arc
position and a vibe; a transition's comes from measured room. This one is
semantic, so it stays with the agent, and the harness's job is to refuse a
choice the renderer cannot honour.
"""
import ast
import json
import pathlib
import re
import sys
import types

_m = types.ModuleType("modal")


class _S:
    def __init__(s, *a, **k): pass
    def __getattr__(s, n): return _S()
    def __call__(s, *a, **k): return _S()
    def function(s, *a, **k): return lambda f: f
    def local_entrypoint(s, *a, **k): return lambda f: f


for _n in ("App", "Image", "Secret", "Volume", "Cls", "Function"):
    setattr(_m, _n, _S())
_m.is_local = lambda: True
_m.enable_output = _S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A                                    # noqa: E402
import type_registries as TR                                      # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


src = pathlib.Path(A.__file__).read_text()
tree = ast.parse(src)

# ── 1. THE CATALOGUE IS 29 AND THE BRAND PAIR IS OUT ────────────────────────
check("the selectable catalogue is 29", len(A.MG_SELECTABLE_TYPES) == 29,
      f"got {len(A.MG_SELECTABLE_TYPES)}")
check("the brand components are excluded",
      A.MG_BRAND_ONLY == {"NamePlate", "EndCard"})
check("selectable + brand covers the whole registry",
      set(A.MG_SELECTABLE_TYPES) | A.MG_BRAND_ONLY == set(TR.VALID_MG_TYPES),
      "a registry type that is neither selectable nor brand-built can never be "
      "placed by anything")

# ── 2. THE PROSE THE AGENT CHOOSES FROM IS ACTUALLY MOUNTED ─────────────────
_kb = pathlib.Path(A.__file__).with_name("knowledge") / "05_motion_graphics.md"
check("the catalogue file is mounted", _kb.is_file())
if _kb.is_file():
    _txt = _kb.read_text()
    _named = {t for t in A.MG_SELECTABLE_TYPES
              if re.search(r"\b" + re.escape(t) + r"\b", _txt)}
    check("every selectable type is TAUGHT in the mounted catalogue",
          _named == set(A.MG_SELECTABLE_TYPES),
          f"offered but never taught: {sorted(set(A.MG_SELECTABLE_TYPES) - _named)} "
          f"— an enum entry with no teach is a type the agent can name and "
          f"cannot choose well")
    check("the brand pair is NOT taught as selectable",
          not any(re.search(r"\*\*" + t + r"\*\*", _txt) for t in A.MG_BRAND_ONLY))
    check("the teach carries FITS and FIGHTS, not just names",
          _txt.count("FITS:") >= 25 and _txt.count("FIGHTS:") >= 25,
          f"FITS {_txt.count('FITS:')}, FIGHTS {_txt.count('FIGHTS:')}")

# ── 3. THE SCHEMA OFFERS EXACTLY THAT SET ───────────────────────────────────
_tools = {t["name"]: t for t in list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS)}
_vp = (_tools["rule_all_beats"]["input_schema"]["properties"]["verdicts"]
       ["items"]["properties"])
check("card_type is offered", "card_type" in _vp)
check("its enum IS the selectable catalogue",
      set(_vp.get("card_type", {}).get("enum") or []) == set(A.MG_SELECTABLE_TYPES),
      "an enum that drifts from the catalogue either hides types or offers "
      "ones nothing teaches")
check("card_props is offered", "card_props" in _vp,
      "every type reads different keys; hero/label is StatCard's vocabulary "
      "and a component carrying the wrong props renders empty")

# ── 4. THE BUILD USES IT ────────────────────────────────────────────────────
# EVERY ASSIGNMENT, FROM THE AST. A substring test for '"type": "StatCard",'
# passed when the mutation wrote `_ctype = "StatCard"` instead — the literal
# moved one line and the check could not see it. Same lesson as the zoom type:
# is-it-mentioned is not is-it-derived.
_ep = next((n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "execute_plan"), None)
check("execute_plan is present to walk", _ep is not None)
_ct_assigns = [n.value for n in ast.walk(_ep or ast.Module(body=[], type_ignores=[]))
               if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "_ctype" for t in n.targets)]
check("the component type is assigned somewhere", bool(_ct_assigns))
check("NO assignment of the component type is a literal",
      not any(isinstance(v, ast.Constant) for v in _ct_assigns),
      "a hardcoded type ignores the ruling, which is the whole 1-of-29")
check("it is read off the verdict",
      any("card_type" in ast.dump(v) for v in _ct_assigns),
      "the type is the one thing the harness cannot derive — it reads the "
      "dialogue, not the timing")
check("the ruled type reaches the reel", '"type": _ctype' in src)


def _guarded_by(marker):
    """The names appearing in conditions that wrap `marker`."""
    out, stack = set(), [(tree, [])]
    while stack:
        node, guards = stack.pop()
        for child in ast.iter_child_nodes(node):
            g = guards + [node.test] if isinstance(node, ast.If) and child in node.body else guards
            if (isinstance(child, ast.Constant) and isinstance(child.value, str)
                    and marker in child.value):
                for t in g:
                    out |= {n.id for n in ast.walk(t) if isinstance(n, ast.Name)}
            stack.append((child, g))
    return out


# GUARDED BY THE TEST, not merely present. `if False:` left both refusal
# strings in the file and a substring check passed on an unreachable branch.
check("a brand component is REFUSED under a test that names the brand set",
      "MG_BRAND_ONLY" in _guarded_by("is a BRAND component the"),
      f"guarded by {sorted(_guarded_by('is a BRAND component the'))}")
check("an unknown type is refused under a test against the catalogue",
      "MG_SELECTABLE_TYPES" in _guarded_by("is not in the catalogue"),
      f"guarded by {sorted(_guarded_by('is not in the catalogue'))}")
check("explicit props win over the StatCard shorthand",
      "_cprops = v.get(\"card_props\")" in src and '"props": _cprops' in src)

# ── 5. BACK-TIMING — the table that was never read ──────────────────────────
_inv = json.loads((pathlib.Path(A.__file__).with_name("_asset_inventory.json")).read_text())
_att = (_inv.get("motion_graphics") or {}).get("attack_ms") or {}
check("the MG attack table is in the inventory", len(_att) >= 20,
      f"{len(_att)} rows")
check("a component is back-timed to be SETTLED on its anchor",
      A.mg_back_timed_start_s("PullQuote", 4.0, _att)[0] == 3.5,
      f"PullQuote's 500ms attack should start it at 3.500s, got "
      f"{A.mg_back_timed_start_s('PullQuote', 4.0, _att)[0]}")
check("an unmeasured type takes the documented default, not zero",
      A.mg_back_timed_start_s("MouseDrag", 4.0, _att)[0] == 3.85,
      f"got {A.mg_back_timed_start_s('MouseDrag', 4.0, _att)[0]}")
check("the head clamps and SAYS it clamped",
      A.mg_back_timed_start_s("PullQuote", 0.2, _att) == (0.0, True))
check("the back-timing is CALLED, not merely defined",
      "mg_back_timed_start_s(_ctype" in src,
      "this table has been in the inventory since it was built and nothing "
      "read it — every motion graphic placed by this lane entered LATE by its "
      "own attack")
check("the anchor and the applied attack are both RECORDED",
      '"anchor_s": round(at, 2)' in src and '"attack_ms":' in src,
      "a shift nobody can read back is indistinguishable from no shift")
check("the placed type is RECORDED per placement",
      '"type": _c3.get("type"),' in src,
      "the mix line reads these items; without the field it prints nothing and "
      "still passes a grep for its own header")
check("and PRINTED",
      "MG CATALOGUE    :" in src,
      "'card=4' is true of four StatCards and of four different types, and the "
      "difference is the entire point of this port")

if fails:
    print(f"MG-CATALOGUE-WIRED: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print(f"MG-CATALOGUE-WIRED: PASS  ({len(A.MG_SELECTABLE_TYPES)} selectable, "
      f"{len(A.MG_BRAND_ONLY)} brand-built)")
