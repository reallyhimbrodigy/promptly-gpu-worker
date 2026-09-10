#!/usr/bin/env python3
"""CERT — MG_PROP_KEYS is what the components actually declare, still.

THE ANTI-DRIFT FINGERPRINT for the card-props table. MG_PROP_KEYS is DERIVED
from each component's types.ts and then frozen into agentic_editor_app.py so the
worker does not parse TypeScript at run time. A frozen derivation rots the moment
someone edits a component, and it rots SILENTLY: a renamed prop makes the table
demand a key the component no longer reads, and every card of that type is
skipped as a mismatch — or, worse, a newly-required prop is absent from the table
and the card renders blank exactly as before.

So the table is regenerated here from the same source and compared.

WHAT IT PINS, and why each one matters:
  1. every derivable selectable type is IN the table
  2. the required/declared sets match the interfaces exactly
  3. MG_PROPS_UNDERIVABLE is EXACTLY the four known ones — a component that
     drops out of derivation (an interface renamed, a types.ts moved) would
     otherwise stop being validated with nobody noticing, which is the same
     "absence rendered as success" this repo keeps paying for
  4. the union of the two covers all 29 selectable types, so no type is
     unaccounted for in either direction

RUN: python3 cert_mg_prop_keys.py [components-dir]
"""
import ast
import json
import os
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

ROOT = sys.argv[1] if len(sys.argv) > 1 else "src/remotion/src/motion-graphics"
# Timing and positioning are supplied by the harness (fromFrame /
# durationInFrames / the anchor table), never by card_props, so requiring them
# of the agent would reject every correct card.
SHARED = {"startMs", "durationMs", "anchor", "position", "x", "y", "offsetX",
          "offsetY", "safeArea", "positionSegments"}

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


if not os.path.isdir(ROOT):
    print(f"CERT-MG-PROP-KEYS: SKIPPED — no components at {ROOT}")
    print("  This cert is only meaningful where src/remotion is present.")
    sys.exit(0)

ifaces = {}
for _d in sorted(os.listdir(ROOT)):
    _f = os.path.join(ROOT, _d, "types.ts")
    if not os.path.isfile(_f):
        continue
    _s = re.sub(r"//[^\n]*", "", open(_f, encoding="utf-8").read())
    for _m2 in re.finditer(
            r"export interface (\w+)(?:\s+extends\s+([^{]+))?\{(.*?)\n\}", _s, re.S):
        _name, _ext, _body = _m2.group(1), (_m2.group(2) or ""), _m2.group(3)
        _decl = re.findall(r"^\s*([A-Za-z_]\w*)\s*\??\s*:", _body, re.M)
        _opt = re.findall(r"^\s*([A-Za-z_]\w*)\s*\?\s*:", _body, re.M)
        ifaces[_name] = ([b.strip() for b in _ext.split(",") if b.strip()],
                         sorted(set(_decl) - set(_opt)), sorted(set(_decl)))

check("the components were actually parsed", len(ifaces) >= 20,
      f"only {len(ifaces)} interfaces — the cert would pass vacuously")


def resolve(name, seen=None):
    seen = seen or set()
    if name in seen or name not in ifaces:
        return set(), set()
    seen.add(name)
    base, req, decl = ifaces[name]
    R, D = set(req), set(decl)
    for b in base:
        _br, _bd = resolve(b, seen)
        R |= _br
        D |= _bd
    return R, D


fresh, underivable = {}, []
for _t in sorted(A.MG_SELECTABLE_TYPES):
    if f"{_t}Props" not in ifaces:
        underivable.append(_t)
        continue
    _R, _D = resolve(f"{_t}Props")
    fresh[_t] = {"required": sorted(_R - SHARED), "declared": sorted(_D - SHARED)}

# 1 + 2. The frozen table is the derived table.
check("the frozen table covers exactly the derivable types",
      set(A.MG_PROP_KEYS) == set(fresh),
      f"frozen-only={sorted(set(A.MG_PROP_KEYS) - set(fresh))} "
      f"derived-only={sorted(set(fresh) - set(A.MG_PROP_KEYS))}")
for _t in sorted(set(A.MG_PROP_KEYS) & set(fresh)):
    check(f"{_t} required props match the component",
          A.MG_PROP_KEYS[_t]["required"] == fresh[_t]["required"],
          f"frozen {A.MG_PROP_KEYS[_t]['required']} vs component "
          f"{fresh[_t]['required']}")
    check(f"{_t} declared props match the component",
          A.MG_PROP_KEYS[_t]["declared"] == fresh[_t]["declared"],
          f"frozen {A.MG_PROP_KEYS[_t]['declared']} vs component "
          f"{fresh[_t]['declared']}")

# 3. The unvalidated set cannot grow quietly.
check("the underivable set is exactly the four known ones",
      sorted(A.MG_PROPS_UNDERIVABLE) == sorted(underivable),
      f"pinned {sorted(A.MG_PROPS_UNDERIVABLE)} vs actual {sorted(underivable)} "
      f"— a type that drops out of derivation stops being validated, and "
      f"nothing else would say so")

# 4. Nothing falls between the two.
check("every selectable type is accounted for",
      set(A.MG_PROP_KEYS) | set(A.MG_PROPS_UNDERIVABLE) == set(A.MG_SELECTABLE_TYPES),
      f"unaccounted={sorted(set(A.MG_SELECTABLE_TYPES) - set(A.MG_PROP_KEYS) - set(A.MG_PROPS_UNDERIVABLE))}")

# ── THE CATALOGUE DOCUMENTS EVERY SELECTABLE TYPE ───────────────────────────
# Inherited from the retired MG_CLAIM_INDEX, which parsed this at IMPORT to feed
# the card_type enum description. b13730c retired that enum and the parse lost
# its only reader while still running on every import — a table mounted and
# unread, and one I made.
#
# The invariant is real and belongs here: a type the pipeline can BUILD but the
# catalogue does not DESCRIBE is a component nobody can learn, and the catalogue
# is what read_knowledge serves and what any future derivation would read. It is
# a fact about the repo, checked once, rather than work the worker repeats every
# cold start.
_CAT = os.path.join(os.path.dirname(ROOT.rstrip("/")) or ".", "..", "..")
_cat_path = None
for _cand in ("knowledge/05_motion_graphics.md",
              os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "knowledge", "05_motion_graphics.md")):
    if os.path.isfile(_cand):
        _cat_path = _cand
        break
if _cat_path is None:
    print("CERT-MG-PROP-KEYS: catalogue not found — skipping the coverage leg")
else:
    _txt = open(_cat_path, encoding="utf-8").read()
    _undocumented = []
    for _t in sorted(A.MG_SELECTABLE_TYPES):
        if not re.search(r"\*\*" + re.escape(_t) + r"\*\*.*?Claim:\s*[\"\u201c]",
                         _txt, re.S):
            _undocumented.append(_t)
    check("every selectable type has a Claim line in the catalogue",
          not _undocumented,
          f"{_undocumented} — a type the pipeline can BUILD that the catalogue "
          f"does not DESCRIBE is a component nobody can learn")
    check("this leg is not vacuous", "Claim:" in _txt,
          "the catalogue has no Claim lines at all and the check passes by "
          "finding none to fail")

if fails:
    print(f"CERT-MG-PROP-KEYS: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print(f"ok cert_mg_prop_keys — {len(fresh)} components derived from their own "
      f"types.ts and matching, {len(underivable)} pinned as unvalidated, "
      f"{len(A.MG_SELECTABLE_TYPES)} selectable types all accounted for")
