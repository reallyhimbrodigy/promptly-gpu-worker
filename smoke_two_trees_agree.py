#!/usr/bin/env python3
"""ported_mg and the TypeScript sources are TWO TREES, and they drift silently.

FOUND 2026-09-23, the hard way. I fixed four components in `ported_mg/` — what
ChatCut renders, via chatcut_registry_baked.json — and rendered one locally to
check. The frame still showed the defect, because MGCraftProbe renders
`src/remotion/src/motion-graphics/<Type>/<Type>.tsx`, a DIFFERENT FILE. Only
one of the two had been fixed.

ported_mg IS NOT GENERATED from the .tsx. It is a hand-maintained port, so
nothing makes them agree and nothing said they disagreed: ChatCut drew the
fixed component and our own pipeline drew the broken one, indefinitely.

THIS DOES NOT CHECK THAT THE TREES ARE IDENTICAL — they cannot be. One is TSX
with types and imports, the other is a flattened JSX blob with ChatCut's
injected globals. It checks the SPECIFIC PROPERTIES that were fixed, on both
sides, so a fix landing in one tree and not the other is refused.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TSX = os.path.join(HERE, "src", "remotion", "src", "motion-graphics")
PORTED = os.path.join(HERE, "ported_mg")
FAILS, NLEGS = [], 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def code(path):
    """Source with comments stripped — a property must hold in CODE.

    Every one of these checks has already been fooled once by prose: I
    searched for "9999px" and matched the comment recording its removal, and
    again for the tag's old transform in a comment explaining why it moved.
    """
    s = open(path, encoding="utf-8").read()
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", s)


# (component, description, pattern that must NOT appear in either tree)
FORBIDDEN = [
    ("Reticle", "the 9999px window-plane spill",
     r"boxShadow:[^,}]*9999px"),
    ("Reticle", "the tag positioned above the region",
     r"translateY\(calc\(-100%"),
    ("StatCard", "toLocaleString — Intl, which their runtime answers ungrouped",
     r"toLocaleString"),
]
# (component, description, pattern that MUST appear in both trees)
REQUIRED = [
    ("Reticle", "the tag inside the region", r"top: armLength \+ 14"),
    ("StatCard", "explicit digit grouping", r"groupDigits"),
    ("StickyNotes", "fog off by default", r"showFog = false"),
]


def both(name):
    a = os.path.join(PORTED, name + ".jsx")
    b = os.path.join(TSX, name, name + ".tsx")
    if not os.path.exists(a) or not os.path.exists(b):
        return None
    return {"ported_mg": code(a), "tsx": code(b)}


def main():
    # L0 BOTH TREES EXIST FOR EVERY COMPONENT UNDER TEST. A missing file makes
    # every leg below vacuous, and a vacuous leg here reads as "the trees
    # agree" — which is the failure this whole file is about.
    # ── PARAMETER DEFAULTS MUST AGREE ACROSS THE TREES ──────────────────
    # The pattern lists above ask "does this tree contain X". They cannot see
    # a value that is PRESENT IN BOTH AND DIFFERENT, which is how two real
    # divergences survived:
    #
    #   SectionDivider showScrim/showVignette   jsx false, tsx TRUE
    #     -> our own renders put a full-frame scrim and vignette over the
    #        picture on every SectionDivider that did not override them. The
    #        .jsx even carries a comment predicting exactly this, written
    #        while it was already true in the other tree.
    #   PillCluster    width                    jsx 1000, tsx 1160
    #     -> 1160 is WIDER THAN THE 1080 FRAME, so the cluster laid out past
    #        the edge and the measured box was a clipped box read as content.
    #
    # Both were found by a knob-cut bisect run for an unrelated reason:
    # dropping a prop let the tsx default take over and the render moved,
    # which is only possible if the two defaults disagree. A check should not
    # need an accident.
    import glob as _glob, os as _os
    def _param_defaults(path):
        src = open(path, encoding="utf-8").read()
        src = re.sub(r"/\*[\s\S]*?\*/", "", src)
        src = re.sub(r"(^|[^:])//[^\n]*", lambda m: m.group(1), src)
        i = src.find("startMs")
        if i < 0:
            return {}
        j = src.find("} = props", i)
        if j < 0:
            j = src.find("}) =>", i)
        block = src[max(0, src.rfind("({", 0, i)):j] if j > 0 else ""
        return {m.group(1): m.group(2).strip()
                for m in re.finditer(r"(?m)^\s*(\w+)\s*=\s*([^,\n]+?)\s*,?\s*$", block)}

    _pairs, _dis = 0, []
    for _jsx in sorted(_glob.glob(_os.path.join(HERE, "ported_mg", "*.jsx"))):
        _n = _os.path.basename(_jsx)[:-4]
        _hits = _glob.glob(_os.path.join(HERE, "src", "remotion", "src",
                                         "motion-graphics", "*", _n + ".tsx"))
        if not _hits:
            continue
        _pairs += 1
        _a, _b = _param_defaults(_jsx), _param_defaults(_hits[0])
        for _k in sorted(set(_a) & set(_b)):
            if _a[_k] != _b[_k]:
                _dis.append("%s.%s (jsx=%s tsx=%s)" % (_n, _k, _a[_k][:20], _b[_k][:20]))
    # THE DENOMINATOR IS ASSERTED. A glob that stops matching compares zero
    # pairs and passes, which is the cheapest false green available.
    leg("parameter_defaults_agree_across_trees",
        _pairs >= 20 and not _dis,
        "%d component pair(s), %d disagreement(s)%s"
        % (_pairs, len(_dis), ("  <<< " + ", ".join(_dis[:4])) if _dis else ""))

    names = sorted({n for n, _d, _p in FORBIDDEN + REQUIRED})
    missing = [n for n in names if both(n) is None]
    leg("L0 both_trees_present_for_every_component", names and not missing,
        "%d component(s), missing a side: %s" % (len(names), missing or "none"))
    if missing:
        print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
        return 1

    bad = []
    for name, desc, pat in FORBIDDEN:
        for tree, src in sorted(both(name).items()):
            if re.search(pat, src):
                bad.append("%s/%s: %s" % (tree, name, desc))
    leg("L1 no_fixed_defect_survives_in_either_tree", not bad,
        "%d survival(s): %s" % (len(bad), bad or "none"))

    gone = []
    for name, desc, pat in REQUIRED:
        for tree, src in sorted(both(name).items()):
            if not re.search(pat, src):
                gone.append("%s/%s: %s" % (tree, name, desc))
    leg("L2 every_fix_is_present_in_both_trees", not gone,
        "%d missing: %s" % (len(gone), gone or "none"))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
