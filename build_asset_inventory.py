"""Extract the REAL asset inventory from the pipeline's own source.

WHY EXTRACTED AND NEVER HAND-COPIED. Every one of these tables is a measured
artifact that has already moved once: `_MG_ATTACK_MS` had three entries
re-measured on 2026-08-29 after a catalogue pass, and a stale copy would have
back-timed them early, silently, on every job that placed them. A transcribed
inventory is a second source of truth with no fingerprint — so this reads
handler.py and type_registries.py and fails loudly rather than guessing.

Parsed with `ast`, not regex: these are Python dict/frozenset literals and the
repo's own rule is that a mechanical rewrite needs a semantic check. ast IS the
semantic check — a renamed or restructured table raises here instead of
silently yielding {}.
"""
import ast
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
# THE CHECKOUT THIS FILE IS IN, not the checkout two directories up. _ROOT was
# `../..`, which from `.worktrees/<lane>/` is the MAIN checkout — so every lane
# built its inventory from whatever branch the main tree happened to have
# checked out, and a throwaway worktree anywhere else (a red proof's) could not
# import the app at all: `/T/type_registries.py` does not exist. handler.py and
# type_registries.py are tracked at the repo root, so the checkout that holds
# this file holds them too. `../..` survives only as a fallback, and it says so.
_ROOT = _HERE
if not os.path.exists(os.path.join(_HERE, "type_registries.py")):
    _ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
    print(f"[asset-inventory] type_registries.py is not beside this file; reading "
          f"the checkout at {_ROOT} — a CROSS-CHECKOUT read, another branch's "
          f"literals", flush=True)


def _literals_from(path, wanted):
    """Return {name: python_value} for each top-level assignment in `wanted`."""
    src = open(path, encoding="utf-8", errors="ignore").read()
    tree = ast.parse(src)
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id in wanted:
                try:
                    found[tgt.id] = ast.literal_eval(node.value)
                except ValueError:
                    # frozenset({...}) is a Call, not a literal — unwrap it.
                    v = node.value
                    if (isinstance(v, ast.Call) and getattr(v.func, "id", "") == "frozenset"
                            and v.args):
                        found[tgt.id] = sorted(ast.literal_eval(v.args[0]))
    return found


def build():
    reg = os.path.join(_ROOT, "type_registries.py")
    hdl = os.path.join(_ROOT, "handler.py")
    sounds_dir = os.path.join(_ROOT, "src", "assets", "sounds")

    r = _literals_from(reg, {"VALID_CAPTION_STYLES", "VALID_TRANSITION_TYPES",
                             "VALID_MG_TYPES"})
    h = _literals_from(hdl, {"_SFX_ATTACK_MS", "_MG_ATTACK_MS", "_MG_SEQUENCED"})

    sounds = sorted(f for f in os.listdir(sounds_dir) if f.endswith(".mp3")) \
        if os.path.isdir(sounds_dir) else []

    # ── SFX AS A LOOKUP TABLE, NOT PROSE ────────────────────────────────────
    # The catalogue lived as ~15 paragraphs of prose in handler.py, and SFX has
    # been placed ZERO times on every run ever measured against a corpus rate of
    # 0.82/25s. Prose is what the agent reads and ignores; a table keyed by ROLE
    # is what it can pick from. Parsed from the prose rather than transcribed,
    # so the two cannot drift.
    import re as _re
    import subprocess as _sp
    hdl_src = open(hdl, encoding="utf-8", errors="ignore").read()
    catalogue = {}
    for line in hdl_src.splitlines():
        mm = _re.match(r"^\*\*([a-z0-9\-]+)\*\* — (.*)$", line.strip())
        if not mm:
            continue
        nm, body = mm.group(1), mm.group(2)

        def _grab(tag, _b=body):
            g = _re.search(rf"\*\*{tag}:\*\*\s*(.*?)(?=\*\*[A-Z ]+:\*\*|$)", _b, _re.S)
            return g.group(1).strip().rstrip(".") if g else ""
        row = {"role": _grab("THE MOMENT")[:220],
               "fits": _grab("FITS")[:120],
               "fights": _grab("FIGHTS")[:120]}
        f = os.path.join(sounds_dir, nm + ".mp3")
        if os.path.isfile(f):
            pr = _sp.run(f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{f}"',
                         shell=True, capture_output=True, text=True)
            try:
                row["duration_s"] = round(float(pr.stdout.strip()), 2)
            except Exception:
                row["duration_s"] = None
            row["file"] = nm + ".mp3"
        else:
            # `voice` is the signed BARE choice — a real option with no file.
            row["file"] = None
            row["duration_s"] = None
        catalogue[nm] = row

    # WHICH BEAT PURPOSE EACH FAMILY LANDS ON — measured from the 153-beat
    # reference corpus, not asserted. 64% of corpus SFX are on hook or close.
    beat_fit = {
        "sfx":     {"hook": 5, "close": 4, "claim": 2, "breath": 1, "evidence": 1, "turn": 1},
        "card":    {"evidence": 18, "close": 11, "turn": 4, "hook": 3, "claim": 2},
        "cutaway": {"evidence": 44, "turn": 8, "claim": 7, "close": 4, "payoff": 4},
        "zoom":    {"hook": 3, "evidence": 3},
    }

    inv = {
        "beat_fit": beat_fit,
        "sfx_catalogue": catalogue,
        "sfx": {
            "files": sounds,
            "dir": "/assets/sounds",
            # The attack table is the whole reason the SFX library is not just
            # 15 mp3s: it is how many ms EARLIER the file must start so its peak
            # lands ON the target word. Placing a sound without it puts the hit
            # in the wrong place, audibly, and nothing errors.
            "attack_ms": h.get("_SFX_ATTACK_MS", {}),
        },
        "motion_graphics": {
            "types": r.get("VALID_MG_TYPES", []),
            "attack_ms": h.get("_MG_ATTACK_MS", {}),
            "sequenced": sorted(h.get("_MG_SEQUENCED", []) or []),
            "note": "sequenced types use container-arrival min(hit, settle); "
                    "simple pops use settle",
        },
        "transitions": {"types": r.get("VALID_TRANSITION_TYPES", [])},
        "caption_styles": {"types": r.get("VALID_CAPTION_STYLES", [])},
    }

    # A CLEAN ZERO IS GUILTY. Every one of these is non-empty in the pipeline
    # today; an empty list here means the parse broke, not that the feature was
    # removed, and shipping it would hand the agent an inventory of nothing
    # while every check stayed green.
    empties = [k for k, v in {
        "sfx.files": inv["sfx"]["files"],
        "sfx.attack_ms": inv["sfx"]["attack_ms"],
        "motion_graphics.types": inv["motion_graphics"]["types"],
        "motion_graphics.attack_ms": inv["motion_graphics"]["attack_ms"],
        "transitions.types": inv["transitions"]["types"],
        "caption_styles.types": inv["caption_styles"]["types"],
        "sfx_catalogue": catalogue,
    }.items() if not v]
    if empties:
        raise AssertionError(
            f"asset inventory extracted EMPTY for {empties} — the source tables "
            f"moved or were renamed. Fix the extractor; do not ship an agent "
            f"an inventory of nothing.")

    # Every sound the attack table names must exist as a file, and vice versa.
    # A named-but-absent sound is a placement the agent cannot render; a
    # present-but-untimed sound would be placed with the default offset and land
    # in the wrong place.
    names = {os.path.splitext(f)[0] for f in inv["sfx"]["files"]}
    timed = set(inv["sfx"]["attack_ms"])
    if names - timed or timed - names:
        raise AssertionError(
            f"SFX library and attack table disagree — files without timing "
            f"{sorted(names - timed)}, timing without files {sorted(timed - names)}")
    return inv


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
