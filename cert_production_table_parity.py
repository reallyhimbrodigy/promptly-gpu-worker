#!/usr/bin/env python3
"""CERT: every table this lane copied from production still MATCHES production.

TWO CERTS WERE CITED IN THE CODE AND NEITHER EXISTED.

  agentic_editor_app.py, on ZOOM_RAMP_FRACTION:
    "cert_zoom_ramp_matches_production.py reads that table and fails if the
     two drift."
  agentic_editor_app.py, on CAPTION_STYLE_FITS:
    "cert_caption_style_parity.py reads them back out and fails on drift, the
     same way the zoom ramp fraction is pinned."

  $ ls cert_zoom_ramp_matches_production.py cert_caption_style_parity.py
    No such file or directory   (both)

Anyone reading those comments believes the ported values are pinned. They were
not pinned by anything. A check named in prose reads exactly like a check that
exists — it is the cheapest false green there is, because it costs one sentence
and buys a whole category of confidence that was never earned.

This is the one that exists. It reads handler.py — production's actual source,
by AST, never by import (handler.py is 45k lines and pulls the world) — and
compares every value the agentic lane copied.

WHY IT MATTERS MORE FROM HERE. The parity port copies four more production
tables: ZOOM_ARC_HOMES, ZOOM_PEAK_REACH_MS, the zoom naturals, _SFX_ATTACK_MS.
Each is a set of measured constants — spring settle times, RMS-envelope argmaxes
— that were expensive to measure and are silent when wrong. A drifted attack
offset puts a sound in the wrong place and NOTHING errors; a drifted peak-reach
lands a zoom off the word and nothing errors. Copies rot. This is what stops it.

ABSENCE IS NOT SUCCESS. If handler.py cannot be found or a table cannot be
parsed out of it, this FAILS rather than skipping — a parity cert that quietly
checks nothing is the exact thing it was written to replace.

  python3 cert_production_table_parity.py [path/to/handler.py]
"""
import ast
import os
import sys
import types

import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


# ── LOCATE PRODUCTION ────────────────────────────────────────────────────────
# The worktree sits under .worktrees/<name>, so handler.py is two levels up.
# Every candidate is tried and the ones that missed are REPORTED, because
# "could not find production" must never look like "production matches".
# FROM THE DEPLOY BRANCH, NOT THE FILE ON DISK.
#
# The first version of this read `handler.py` from the worktree and passed. The
# worktree is a full checkout of lane/agentic-editor, whose handler.py is a
# DIFFERENT FILE from the deploy branch's:
#
#     worktree handler.py       b5810c89c3aaa1bb
#     zero-reject-routing       ea14d2c69126311c
#
# So it was pinning the ported tables against a stale sibling copy and calling
# that production parity — a table could drift from what actually ships and this
# cert would stay green. That is the exact failure it was written to prevent,
# inside itself, one commit after being written.
#
# Rule 0: the canonical worker deploy branch is zero-reject-routing.
PROD_REF = os.environ.get("PROMPTLY_PROD_REF", "zero-reject-routing")
_src, HANDLER = None, None
if len(sys.argv) > 1:
    if os.path.isfile(sys.argv[1]):
        HANDLER = os.path.abspath(sys.argv[1])
        _src = open(HANDLER, encoding="utf-8").read()
else:
    import subprocess
    _r = subprocess.run(["git", "show", f"{PROD_REF}:handler.py"],
                        capture_output=True, text=True,
                        cwd=os.path.dirname(os.path.abspath(__file__)))
    if _r.returncode == 0 and _r.stdout:
        _src, HANDLER = _r.stdout, f"git:{PROD_REF}:handler.py"

if not _src:
    print("PRODUCTION-TABLE-PARITY: FAILED — could not read production's "
          f"handler.py from {PROD_REF}")
    print("  A parity cert that cannot read production checks NOTHING. This is "
          "a failure, not a skip.")
    print("  Pass an explicit path to override, or set PROMPTLY_PROD_REF.")
    sys.exit(1)

_tree = ast.parse(_src)
_prod = {}
for _n2 in _tree.body:
    if isinstance(_n2, ast.Assign) and len(_n2.targets) == 1 \
            and isinstance(_n2.targets[0], ast.Name):
        try:
            _prod[_n2.targets[0].id] = ast.literal_eval(_n2.value)
        except Exception:
            pass


def prod(name):
    """A production value, or None — and None is always a failure, never a skip."""
    if name not in _prod:
        fails.append(f"{name} could not be read out of handler.py — the cert "
                     f"cannot compare what it cannot parse, and a table that "
                     f"silently drops out of this list stops being pinned")
        return None
    return _prod[name]


def compare(name, ported, normalise=None):
    p = prod(name)
    if p is None:
        return
    a, b = (normalise(p), normalise(ported)) if normalise else (p, ported)
    if a == b:
        return
    ka, kb = set(a or {}), set(b or {})
    detail = []
    if ka - kb:
        detail.append(f"production has {sorted(ka - kb)} and this lane does not")
    if kb - ka:
        detail.append(f"this lane has {sorted(kb - ka)} and production does not")
    for k in sorted(ka & kb):
        if a[k] != b[k]:
            detail.append(f"{k}: production {a[k]!r} vs ported {b[k]!r}")
    fails.append(f"{name} has DRIFTED from production  :: " + "; ".join(detail))


# ── THE TABLES ───────────────────────────────────────────────────────────────
# Each is only checked if the lane has actually ported it yet. A table that is
# NOT yet ported is reported as such rather than passing silently — porting one
# and forgetting to pin it is precisely the gap the two phantom certs left.
_expected_ports = {
    "ZOOM_PEAK_REACH_MS": "per-type perceptual peak, so the zoom lands on the word",
    "ZOOM_NATURAL_DURATION_MS": "the duration each move was designed for",
    "ZOOM_NATURAL_SCALE": "the perceptible-baseline scale per type",
    "ZOOM_ARC_HOMES": "arc position -> the types that may be offered there",
    "TRANSITION_DURATION_FRAMES": "how much room each seam treatment needs",
    "TRANSITION_NATURAL_DURATION_MS": "the derived ms view of the same",
    "TRANSITION_FPS": "the grid those frame counts are declared on",
}
# _SFX_ATTACK_MS is deliberately NOT expected on the module: this lane reads it
# from _asset_inventory.json, and adding a copy here would make three.
_ported_now, _not_yet = [], []
for _t2 in _expected_ports:
    (_ported_now if hasattr(A, _t2) else _not_yet).append(_t2)

# PRODUCTION BUILDS THIS ONE IN A LOOP. `ZOOM_NATURAL_DURATION_MS = {}` is the
# literal in handler.py and a for-loop fills it from the FRAMES table, so
# literal_eval sees an empty dict — and comparing against it reported the whole
# ported table as drift. Derive it exactly as production does, from the source
# of truth production derives it from.
# Same loop-built shape as the zoom durations: handler.py declares
# `TRANSITION_NATURAL_DURATION_MS = {}` and a for-loop fills it, so literal_eval
# sees an empty dict. Derive it the way production does.
_prod["TRANSITION_NATURAL_DURATION_MS"] = {
    k: (int(v) * 1000) // (_prod.get("TRANSITION_FPS") or 60)
    for k, v in (_prod.get("TRANSITION_DURATION_FRAMES") or {}).items()}
_prod["ZOOM_NATURAL_DURATION_MS"] = {
    k: (int(v) * 1000) // 60
    for k, v in (_prod.get("ZOOM_NATURAL_DURATION_FRAMES") or {}).items()}

for _t2 in _ported_now:
    if _t2 == "ZOOM_ARC_HOMES":
        # Tuples vs lists must not read as drift; membership is the contract.
        compare(_t2, getattr(A, _t2),
                normalise=lambda d: {k: sorted(v) for k, v in (d or {}).items()})
    else:
        compare(_t2, getattr(A, _t2))

# ── THE SFX ATTACK TABLE, PINNED WHERE IT ACTUALLY LIVES ────────────────────
# This lane does not hold its own copy: build_asset_inventory.py parses
# `_SFX_ATTACK_MS` out of handler.py at deploy time and the container reads
# /assets/inventory.json. That is one fewer copy to rot — but it parses the
# handler.py ON DISK, and this worktree's differs from the deploy branch's
# (b5810c89c3aaa1bb vs ea14d2c69126311c). So the inventory can be built from a
# stale sibling and nothing would say so. Comparing the BUILT ARTIFACT against
# the DEPLOY BRANCH is what closes that.
# The path is overridable so the RED proof can hand this a doctored copy.
# build_asset_inventory computes _ROOT as <worktree>/../.. — which lands on the
# MAIN checkout, not this worktree — so the inventory happens to be built from
# the deploy branch's handler.py today by accident of the worktree layout, and
# there is no way to make it drift from inside this worktree. That accident is
# exactly why the comparison has to exist: move the worktree one level and the
# inventory silently starts following a different handler.py.
_inv_path = os.environ.get("PROMPTLY_INVENTORY_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_asset_inventory.json")
_p_sfx = prod("_SFX_ATTACK_MS")
if _p_sfx is not None:
    if not os.path.isfile(_inv_path):
        fails.append("_asset_inventory.json is absent — the container reads its "
                     "attack offsets from it, so an absent inventory is a "
                     "failure and not a skip")
    else:
        import json as _json
        _inv = _json.load(open(_inv_path))
        _i_sfx = ((_inv.get("sfx") or {}).get("attack_ms") or {})
        # Compared directly: `compare()` re-looks-up by name, and the display
        # label is not a key in handler.py.
        if _i_sfx != _p_sfx:
            _ka, _kb = set(_p_sfx), set(_i_sfx)
            _d = []
            if _ka - _kb:
                _d.append(f"production has {sorted(_ka - _kb)} and the "
                          f"inventory does not")
            if _kb - _ka:
                _d.append(f"the inventory has {sorted(_kb - _ka)} and "
                          f"production does not")
            _d += [f"{k}: production {_p_sfx[k]!r} vs inventory {_i_sfx[k]!r}"
                   for k in sorted(_ka & _kb) if _p_sfx[k] != _i_sfx[k]]
            fails.append("_SFX_ATTACK_MS has DRIFTED between the deploy branch "
                         "and _asset_inventory.json  :: " + "; ".join(_d))
        # And the sounds on disk must all BE timed: an untimed file placed by
        # name starts at the beat instead of peaking on it, silently.
        _files = set((_inv.get("sfx") or {}).get("files") or [])
        _stems = {f.rsplit(".", 1)[0] for f in _files}
        _untimed = sorted(_stems - set(_i_sfx))
        check("every catalogue sound carries an attack offset",
              not _untimed,
              f"{_untimed} would be placed at the beat rather than peaking on "
              f"it, with nothing to say so")

# ── THE DERIVED CONSTANT ─────────────────────────────────────────────────────
# ZOOM_RAMP_FRACTION is the one the missing cert was named for. It is not a copy
# of a production table but a value DERIVED from two of them, and the derivation
# is what has to hold: SmoothPush reaches its peak 35% into a 1200ms move.
if hasattr(A, "ZOOM_RAMP_FRACTION"):
    _pk = (prod("ZOOM_PEAK_REACH_MS") or {}).get("SmoothPush")
    _du = (prod("ZOOM_NATURAL_DURATION_MS") or {}).get("SmoothPush")
    if _pk and _du:
        _derived = round(_pk / _du, 4)
        check("ZOOM_RAMP_FRACTION still equals production's SmoothPush "
              "peak-reach over its natural duration",
              abs(A.ZOOM_RAMP_FRACTION - _derived) < 0.005,
              f"lane {A.ZOOM_RAMP_FRACTION} vs production {_pk}/{_du} "
              f"= {_derived}")
    else:
        # ZOOM_NATURAL_DURATION_MS is BUILT by a loop in handler.py, so a
        # literal_eval of the module body cannot see it. Derive it the same way
        # production does rather than declaring the check unavailable.
        _fr = prod("ZOOM_NATURAL_DURATION_FRAMES") or {}
        if _fr.get("SmoothPush") and _pk:
            _du2 = _fr["SmoothPush"] * 1000 // 60
            _derived = round(_pk / _du2, 4)
            check("ZOOM_RAMP_FRACTION still equals production's SmoothPush "
                  "peak-reach over its natural duration (frames-derived)",
                  abs(A.ZOOM_RAMP_FRACTION - _derived) < 0.005,
                  f"lane {A.ZOOM_RAMP_FRACTION} vs production {_pk}/{_du2} "
                  f"= {_derived}")
        else:
            fails.append("ZOOM_RAMP_FRACTION is pinned to nothing — neither "
                         "ZOOM_NATURAL_DURATION_MS nor "
                         "ZOOM_NATURAL_DURATION_FRAMES could be read out of "
                         "handler.py")

# ── THE REGISTRIES THE CATALOGUE MUST TILE ──────────────────────────────────
# Zac's ruling is "every component the current pipeline uses, no more and no
# less", so the count is a contract and not a detail. type_registries is the
# same module production imports, which makes this an equality rather than a
# copy.
try:
    import type_registries as TR
    if hasattr(A, "ZOOM_ARC_HOMES"):
        _housed = {t for h in A.ZOOM_ARC_HOMES.values() for t in h}
        check("the arc homes house EXACTLY the zoom registry — no extinct type, "
              "no stranger",
              _housed == set(TR.VALID_ZOOM_TYPES),
              f"housed {sorted(_housed)} vs registry "
              f"{sorted(TR.VALID_ZOOM_TYPES)}")
    if hasattr(A, "TRANSITION_FITS"):
        # LIGHTLEAK IS IN THE DURATION TABLE AND IS NOT A TRANSITION. It is a
        # tight-cut overlay, and ShutterFlash is BOTH. Reading the ten-row table
        # as "ten transitions" is the mistake this leg exists to catch.
        check("every registry transition has a natural duration",
              set(TR.VALID_TRANSITION_TYPES) <= set(A.TRANSITION_DURATION_FRAMES),
              f"{sorted(set(TR.VALID_TRANSITION_TYPES) - set(A.TRANSITION_DURATION_FRAMES))} "
              f"have none")
        check("every tight-cut overlay has one too",
              set(TR.VALID_TIGHT_CUT_OVERLAYS) <= set(A.TRANSITION_DURATION_FRAMES))
        check("LightLeak is NOT offerable as a transition",
              "LightLeak" not in TR.VALID_TRANSITION_TYPES,
              "it is a cover graphic, not a picture change")
        check("every type in the table carries a fitness clause",
              set(A.TRANSITION_FITS) == set(A.TRANSITION_DURATION_FRAMES))
    if hasattr(A, "CAPTION_STYLE_FITS"):
        # "none" IS IN THE REGISTRY AND MUST NOT BE IN THE FITNESS TABLE. It is
        # a valid caption_style meaning NO CAPTIONS — the absence of a style,
        # not a style — so it has no FITS clause and cannot be picked by fit.
        # Named here rather than papered over, because the difference between
        # "the catalogue is short by one" and "the registry carries a sentinel"
        # is exactly what a parity cert exists to keep straight.
        _reg_styles = set(TR.VALID_CAPTION_STYLES) - {"none"}
        check("the caption catalogue is exactly production's styles",
              set(A.CAPTION_STYLE_FITS) == _reg_styles,
              f"symmetric difference "
              f"{sorted(set(A.CAPTION_STYLE_FITS) ^ _reg_styles)}")
        check("'none' carries no fitness clause — it is the absence of a style",
              "none" not in A.CAPTION_STYLE_FITS,
              "a fitness entry for 'none' would let the picker choose "
              "no-captions on vibe fit rather than on the brief asking for it")
except ImportError as e:
    fails.append(f"type_registries could not be imported ({e}) — the registry "
                 f"legs did not run, and a leg that did not run is not a pass")

# ── PORTED IS NOT WIRED ─────────────────────────────────────────────────────
# Rule 2: built != committed != deployed != working. Nine features in this repo
# have shipped gate-green and done nothing, and a table that is pinned, asserted
# and never CALLED is exactly that shape — every check above passes while the
# pipeline still runs the thing the port was meant to replace.
#
# Reported LOUDLY rather than failed: this is a true statement about work in
# progress, and a cert that goes red for a known-incomplete step is one people
# learn to run with their eyes closed. It is printed where nobody can miss it,
# and BUILT_NOT_WIRED.md is where the repo keeps this class.
_dark = []
_app_src = open(A.__file__, encoding="utf-8").read()
_app_tree = ast.parse(_app_src)
_called = {n.func.id for n in ast.walk(_app_tree)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
for _fn in ("pick_zoom_type", "zoom_natural_ms", "pick_caption_style",
            "pick_transition", "pick_tight_cut_overlay",
            "transition_room_ms", "alpha_pass_needed", "sfx_start_s"):
    if hasattr(A, _fn) and _fn not in _called:
        _dark.append(_fn)

# ── REPORT ───────────────────────────────────────────────────────────────────
print(f"PRODUCTION-TABLE-PARITY  (production: {HANDLER})")
print(f"  pinned  : {_ported_now or '[]'}")
if _not_yet:
    print(f"  NOT YET PORTED: {_not_yet}")
    print("            (listed, not failed — but nothing pins them until they land)")
if _dark:
    print()
    print("  " + "!" * 68)
    print(f"  PORTED BUT DARK: {_dark}")
    print("  These are defined, pinned against production and asserted at import")
    print("  — and NOTHING CALLS THEM. The pipeline still runs whatever they were")
    print("  meant to replace. Every check above passes in this state, which is")
    print("  precisely why it is printed here. (Rule 2 / BUILT_NOT_WIRED.md)")
    print("  " + "!" * 68)

if fails:
    print(f"\n  {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("  PASS")
