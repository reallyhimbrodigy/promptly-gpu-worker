#!/usr/bin/env python3
"""THE CAPTION TEXT SWAP SHIPS ALONE. `[Rule 1, owner ruling 2026-08-18]`

`PROMPTLY_SURGICAL_V2` reads like a caption flag and is not. At the call site it
gates THREE things at once:

    1. caption_text_overrides in the op enum        MECHANICAL — wanted now
    2. TRANSITION_ADD_BULLET replacing the refusal  CREATIVE capability
    3. OPS_VOCAB_ADDENDUM in the prompt             teaches op 1

Flipping it to ship the text swap would ALSO hand the model the ability to add
transitions on re-edit, where it currently refuses. That is a second variable
inside a one-variable change, and it is how a regression gets attributed to the
wrong cause — the reason the secret-auth law names KEYS and not features.

So the text swap gets its own key. It is the single most common small request
there is ("you spelled my name wrong"), it is purely mechanical, and it is the
first user-visible proof that the diff path works at all — that proof carries
one variable.

THE ASSERTION THAT MATTERS is the negative one: PROMPTLY_CAPTION_TEXT_OPS must
NOT arm transition-add. A future edit that collapses the two flags back together
fails here.

    python3 cert_caption_text_ops_split.py
"""
import ast
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    fails = []
    for k in ("PROMPTLY_SURGICAL_V2", "PROMPTLY_CAPTION_TEXT_OPS"):
        os.environ.pop(k, None)
    import surgical_ops as S
    importlib.reload(S)

    # 1. DARK BY DEFAULT — both off means today's behaviour, byte-identical.
    if S.caption_text_ops_enabled() or S.enabled():
        fails.append("both flags unset must leave BOTH off (byte-identical default)")

    # 2. THE NARROW FLAG ARMS THE CAPTION OP...
    os.environ["PROMPTLY_CAPTION_TEXT_OPS"] = "1"
    if not S.caption_text_ops_enabled():
        fails.append("PROMPTLY_CAPTION_TEXT_OPS=1 must arm the caption text op")
    # ...AND MUST NOT ARM TRANSITION-ADD. THE WHOLE POINT.
    if S.enabled():
        fails.append("PROMPTLY_CAPTION_TEXT_OPS must NOT arm surgical_v2 — that "
                     "would hand the model transition-add inside a one-variable "
                     "change, which is exactly what the split prevents")
    os.environ.pop("PROMPTLY_CAPTION_TEXT_OPS", None)

    # 3. SURGICAL_V2 STAYS A SUPERSET — arming the broad flag must not turn the
    #    caption op OFF (that would be a silent regression of the narrow one).
    os.environ["PROMPTLY_SURGICAL_V2"] = "1"
    if not (S.enabled() and S.caption_text_ops_enabled()):
        fails.append("PROMPTLY_SURGICAL_V2=1 must arm BOTH (it is a superset)")
    os.environ.pop("PROMPTLY_SURGICAL_V2", None)

    # 4. STRUCTURAL: the prompt's transition bullet must be selected by
    #    surgical_v2 ALONE, never by the caption flag. Resolved on the parsed
    #    tree rather than by substring, because the two flag names differ by a
    #    prefix and a substring check would pass on the wrong one.
    src = open(os.path.join(HERE, "handler.py")).read()
    tree = ast.parse(src)
    bad = 0
    for n in ast.walk(tree):
        if not isinstance(n, ast.IfExp):
            continue
        seg = ast.get_source_segment(src, n) or ""
        if "TRANSITION_ADD_BULLET" not in seg:
            continue
        test = ast.get_source_segment(src, n.test) or ""
        if "caption_text_ops_enabled" in test:
            bad += 1
    if bad:
        fails.append(f"{bad} transition-add selection(s) test the CAPTION flag — "
                     f"transition-add must be gated by surgical_v2 alone")

    if fails:
        print("CERT CAPTION-TEXT-OPS SPLIT: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT CAPTION-TEXT-OPS SPLIT: PASS")
    print("  dark by default; the narrow flag arms the text swap ONLY")
    print("  transition-add stays behind surgical_v2 alone")
    print("  surgical_v2 remains a superset")
    return 0


if __name__ == "__main__":
    sys.exit(main())
