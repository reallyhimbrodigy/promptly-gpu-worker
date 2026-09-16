#!/usr/bin/env python3
"""The prefix carries ZAC'S STANDARD, and nothing that describes strangers.

WHAT THIS FILE USED TO CHECK, and why that was the wrong thing to check. It
asserted the two craft reports both reached the prefix, standard first. That
was CORRECT WHEN WRITTEN — the ordering existed so the agent could tell which
document a line came from and resolve a contradiction in the standard's favour.

Then Zac ruled (2026-09-15): the field report comes out. "Other people's videos
described in prose is the weakest thing in there." The old legs then failed on
a now-correct prefix — the second stale-check class this lane has named: a
check that defends a DECISION rather than the PROPERTY the decision served.

So the legs below are written against the property, which survives the ruling
in either direction:

    the prefix states a standard, that standard says it is the standard, and
    nothing in the prefix describes other people's habits as if they were it.

If Zac ever puts the field report back, the third leg is the one that must be
edited, deliberately, by a person who read this paragraph.
"""
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

STD, FIELD = "16_craft_the_standard.md", "17_craft_the_wider_field.md"
HERE = os.path.dirname(os.path.abspath(__file__))
fail = 0

docs = A._RULING_TIME_DOCS
text = A.ruling_time_knowledge()

# ── 1. THE STANDARD IS THERE, AS TEXT, NOT AS A NAME IN A TUPLE ─────────────
if STD not in docs:
    print(f"  *** {STD} is not in _RULING_TIME_DOCS — it never reaches the "
          f"prefix"); fail += 1
if text.find("THE STANDARD — HOW THE EXAMPLES") < 0:
    print("  *** the standard is not in the ASSEMBLED prefix (a name in the "
          "tuple is not a document in the block)"); fail += 1
if "MISSING and not read" in text:
    print("  *** the prefix says a document is missing: "
          + text[text.find("MISSING and not read"):][:120]); fail += 1

# ── 2. IT DECLARES ITS OWN AUTHORITY ────────────────────────────────────────
# Order alone is not a statement, and with one craft document there is no order
# to rely on at all.
if "THIS ONE WINS" not in text:
    print("  *** the standard does not say it wins a contradiction"); fail += 1

# ── 3. NOTHING IN THE PREFIX IS A SURVEY OF STRANGERS ───────────────────────
# Checked on the ASSEMBLED text, which is what the turn receives, not on the
# tuple — a document could arrive by any route and the property is the same.
for marker, why in (("THE WIDER FIELD — WHAT OTHER PEOPLE", "the field report"),
                    ("gathered in bulk from", "a bulk survey"),
                    ("103 videos", "the Apify corpus")):
    if marker in text:
        print(f"  *** {why} is in the prefix ({marker!r}) — Zac ruled it out "
              f"2026-09-15"); fail += 1
if FIELD in docs:
    print(f"  *** {FIELD} is back in _RULING_TIME_DOCS"); fail += 1

# ── 4. IT IS STILL ON DISK ──────────────────────────────────────────────────
# Removed from the prefix is not deleted. A document that vanished from the
# repo cannot be reconsidered, and this removal is a cost call, not a verdict
# on the document.
if not os.path.isfile(os.path.join(HERE, "knowledge", FIELD)):
    print(f"  *** {FIELD} is gone from knowledge/ — it was removed from the "
          f"prefix, not from the repo"); fail += 1

# ── 5. AND NO RATES SURVIVED INTO THE PREFIX ────────────────────────────────
# The guard runs at synthesis time; this is the same question asked of what
# actually ships. Asked of the ASSEMBLED text so it covers every document in
# the block, not only the craft report.
ns = {}
for n in ast.parse(open(os.path.join(HERE, "craft_pass_app.py")).read()).body:
    nm = (n.targets[0].id if isinstance(n, ast.Assign)
          and isinstance(n.targets[0], ast.Name)
          else n.name if isinstance(n, ast.FunctionDef) else None)
    if nm in ("_RATE_PATTERNS", "_DENSITY_ELEMENT", "_DENSITY_ANY",
              "rate_language"):
        exec(compile(ast.Module([n], []), "<x>", "exec"), ns)
if "rate_language" not in ns:
    print("  *** the rate guard is absent from craft_pass_app.py"); fail += 1
else:
    p = os.path.join(HERE, "knowledge", STD)
    if os.path.isfile(p):
        hits = ns["rate_language"](open(p, encoding="utf-8").read())
        if hits:
            print(f"  *** {STD} carries {len(hits)} rate(s) IN THE PREFIX:")
            for h in hits[:3]:
                print(f"      {h}")
            fail += 1

print(f"smoke_craft_reports_ordered: {fail} wrong")
sys.exit(1 if fail else 0)
