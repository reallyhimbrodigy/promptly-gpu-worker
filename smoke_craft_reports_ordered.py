#!/usr/bin/env python3
"""The two craft reports reach the prefix as TWO documents, standard first.

WHAT THIS PREVENTS, and it is not hypothetical in this repo: a prefix document
that is present in the tuple but says nothing about its own authority. The
field report describes a hundred strangers' habits. Read without its
precedence line it is indistinguishable from the standard, and the agent would
average a taste Zac did not choose — the same failure as blending them in one
call, arriving one layer later.

Checked by BEHAVIOUR, through ruling_time_knowledge, not by grepping the
source: a string can sit in a dead branch. The order is checked by where the
two headers land in the ASSEMBLED text.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

STD, FIELD = "16_craft_the_standard.md", "17_craft_the_wider_field.md"
fail = 0

docs = A._RULING_TIME_DOCS
for name in (STD, FIELD):
    if name not in docs:
        print(f"  *** {name} is not in _RULING_TIME_DOCS — it never reaches "
              f"the prefix"); fail += 1
if STD in docs and FIELD in docs and docs.index(STD) > docs.index(FIELD):
    print("  *** the field report is placed BEFORE the standard"); fail += 1

text = A.ruling_time_knowledge()
if "MISSING and not read" in text and (STD in text or FIELD in text):
    print("  *** a craft report is missing from knowledge/ — the prefix says "
          "so, which is right, but the document is not there"); fail += 1

i_std, i_field = text.find("THE STANDARD — HOW THE EXAMPLES"), \
    text.find("THE WIDER FIELD — WHAT OTHER PEOPLE")
if i_std < 0:
    print("  *** the standard report is not in the assembled prefix"); fail += 1
if i_field < 0:
    print("  *** the field report is not in the assembled prefix"); fail += 1
if i_std >= 0 and i_field >= 0 and i_std > i_field:
    print("  *** the field report is assembled BEFORE the standard"); fail += 1

# EACH DOCUMENT DECLARES ITS OWN AUTHORITY. Order alone is not a statement.
if i_std >= 0 and "THIS ONE WINS" not in text[i_std:i_field if i_field > i_std
                                              else len(text)]:
    print("  *** the standard does not say it wins a contradiction"); fail += 1
if i_field >= 0 and "THE STANDARD WINS" not in text[i_field:]:
    print("  *** the field report does not defer to the standard"); fail += 1

# AND NO RATES SURVIVED INTO THE PREFIX. The guard runs at synthesis time; this
# is the same question asked of what actually shipped.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ast                                                       # noqa: E402
ns = {}
for n in ast.parse(open("craft_pass_app.py").read()).body:
    nm = (n.targets[0].id if isinstance(n, ast.Assign)
          and isinstance(n.targets[0], ast.Name)
          else n.name if isinstance(n, ast.FunctionDef) else None)
    if nm in ("_RATE_PATTERNS", "_DENSITY_ELEMENT", "_DENSITY_ANY",
              "rate_language"):
        exec(compile(ast.Module([n], []), "<x>", "exec"), ns)
if "rate_language" not in ns:
    print("  *** the rate guard is absent from craft_pass_app.py"); fail += 1
else:
    for name in (STD, FIELD):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "knowledge", name)
        if not os.path.isfile(p):
            continue
        hits = ns["rate_language"](open(p, encoding="utf-8").read())
        if hits:
            print(f"  *** {name} carries {len(hits)} rate(s) IN THE PREFIX:")
            for h in hits[:3]:
                print(f"      {h}")
            fail += 1

print(f"smoke_craft_reports_ordered: {fail} wrong")
sys.exit(1 if fail else 0)
