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
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))


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

    inv = {
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
