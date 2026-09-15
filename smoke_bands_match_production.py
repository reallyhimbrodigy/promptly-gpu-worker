#!/usr/bin/env python3
"""SMOKE — the lane's face-band table IS production's, not a second opinion.

WHY A COPY AT ALL. `handler.py` is the production worker and does not import
into the ChatCut lane's Modal image; `detect_face_positions` sits inside 24,000
lines of it. So `face_bands.py` carries the constants and the band logic
VERBATIM. A copied table that drifts is worse than no copy — the lane would
route placements around bands production does not believe in, and nobody would
see the two answers disagree.

WHAT WENT WRONG WITHOUT IT. The lane invented its own zones three times:
a caption band of 0.52-0.70 (the real TwoTone is 0.367-0.410, and the card
shipped on top of the captions), a face zone of 0.04-0.34 that returned "30%
overlap" for every title, and an edge-density text scan whose min-to-max union
covered 0.284-0.667 so everything overlapped. Production had the real answers
the whole time — including `_caption_occupied_bands`, whose docstring dated
2026-08-19 describes the exact defect that shipped.

Legs, each RED-proven:
  TABLE      the y-ranges match handler.py's `_MG_FACE_BAND_YRANGES`
  THRESHOLD  the clear-threshold matches `_MG_FACE_CLEAR_THRESHOLD`
  CONF       the detector confidence matches the one production uses
  MODEL      the model paths match, so the lane loads the same weights
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import face_bands as FB                                        # noqa: E402

HANDLER = os.path.join(HERE, "handler.py")


def prod_values(src):
    """The production constants, read by AST from handler.py itself."""
    tree = ast.parse(src)
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            name = n.targets[0].id
            if name in ("_MG_FACE_BAND_YRANGES", "_MG_FACE_CLEAR_THRESHOLD"):
                try:
                    out[name] = ast.literal_eval(n.value)
                except Exception:                                # noqa: BLE001
                    pass
    # the detector's own constants live inside the function
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "detect_face_positions"), None)
    if fn is not None:
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                    and isinstance(n.targets[0], ast.Name):
                nm = n.targets[0].id
                if nm in ("CONFIDENCE_THRESHOLD", "PROTOTXT", "CAFFEMODEL"):
                    try:
                        out[nm] = ast.literal_eval(n.value)
                    except Exception:                            # noqa: BLE001
                        pass
    return out


def legs(prod):
    bad = []
    if not prod:
        # ABSENT IS NOT PASS. If handler.py could not be read, every leg below
        # would be comparing against nothing.
        return [("read", "handler.py yielded NO constants — this smoke "
                         "compared the lane against an empty table")]
    for key, mine, label in (
            ("_MG_FACE_BAND_YRANGES", FB.MG_FACE_BAND_YRANGES, "table"),
            ("_MG_FACE_CLEAR_THRESHOLD", FB.MG_FACE_CLEAR_THRESHOLD, "threshold"),
            ("CONFIDENCE_THRESHOLD", FB.CONFIDENCE_THRESHOLD, "conf"),
            ("PROTOTXT", FB.PROTOTXT, "model"),
            ("CAFFEMODEL", FB.CAFFEMODEL, "model")):
        if key not in prod:
            bad.append((label, "handler.py has no %s to compare against" % key))
        elif prod[key] != mine:
            bad.append((label, "%s: production %r, the lane %r"
                               % (key, prod[key], mine)))
    return bad


if __name__ == "__main__":
    src = open(HANDLER, encoding="utf-8").read()
    prod = prod_values(src)
    bad = legs(prod)
    for k, w in bad:
        for_ = "  [FAIL] %-9s %s" % (k, w)
        print(for_)
    if not bad:
        print("  [ok] band table matches production: %s" % FB.MG_FACE_BAND_YRANGES)
        print("  [ok] clear threshold matches: %s" % FB.MG_FACE_CLEAR_THRESHOLD)
        print("  [ok] detector confidence matches: %s" % FB.CONFIDENCE_THRESHOLD)
        print("  [ok] both model paths match, so the same weights load")

    print("\n  RED PROOF")
    red = True
    m = dict(prod)
    m["_MG_FACE_CLEAR_THRESHOLD"] = 0.9
    r1 = legs(m)
    print("    production moves its threshold -> %d leg(s) red" % len(r1))
    red &= any(k == "threshold" for k, _ in r1)

    m2 = dict(prod)
    m2["_MG_FACE_BAND_YRANGES"] = {"top": (0.0, 500.0)}
    r2 = legs(m2)
    print("    production re-cuts its bands    -> %d leg(s) red" % len(r2))
    red &= any(k == "table" for k, _ in r2)

    m3 = dict(prod)
    m3["CAFFEMODEL"] = "/models/face_detector/yunet.onnx"
    r3 = legs(m3)
    print("    production swaps the model      -> %d leg(s) red" % len(r3))
    red &= any(k == "model" for k, _ in r3)

    r4 = legs({})
    print("    handler.py unreadable           -> %d leg(s) red" % len(r4))
    red &= bool(r4)

    ok = not bad and red
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
