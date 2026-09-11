#!/usr/bin/env python3
"""The standard must separate DEAD AIR from SETUP, in the shipped document.

WHAT THIS PREVENTS. Round 52's car_short cut 5.68s out of a 10.0s source — the
opening 57% — because the report said "trim all dead air" flat and the ruling
read it as general. The beat it overrode said, in those words, "visible
content, not dead air". A re-synthesis regenerates this document from scratch
and would flatten the distinction again; this is the check that says so before
the document ships, not after a round has spent the footage.

Checked through the ASSEMBLED prefix, not the file, because the file being
right is not the same as the agent reading it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

text = A.ruling_time_knowledge()
i = text.find("THE STANDARD — HOW THE EXAMPLES")
j = text.find("THE WIDER FIELD — WHAT OTHER PEOPLE")
std = text[i:j if j > i else len(text)] if i >= 0 else ""

fail = 0
if not std:
    print("  *** the standard is not in the assembled prefix at all")
    fail = 1
else:
    low = std.lower()
    # The DEFINITION, not merely the phrase: dead air distinguished from what
    # a silence with content in it is.
    if "dead air is silence with nothing in it" not in low:
        print("  *** the standard does not DEFINE dead air as silence with "
              "nothing in it")
        fail += 1
    if "setup" not in low or "visible content" not in low:
        print("  *** the standard does not name pre-speech visible content as "
              "SETUP")
        fail += 1
    # And the flat instruction must not be standing unqualified.
    import re
    for m in re.finditer(r"trim all dead air|cut all dead air", low):
        a = max(0, m.start() - 400)
        if "nothing in it" not in low[a:m.start()]:
            print(f"  *** an unqualified {m.group(0)!r} with no definition "
                  f"above it")
            fail += 1

print(f"smoke_dead_air_distinction: {fail} wrong")
sys.exit(1 if fail else 0)
