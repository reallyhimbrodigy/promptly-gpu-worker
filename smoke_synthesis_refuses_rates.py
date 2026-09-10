#!/usr/bin/env python3
"""RED PROOF: the rate guard on the cached-prefix report.

The regression it makes impossible: a rate reaching the prefix as an
INSTRUCTION. It has happened before in exactly this shape — "Overlay text is
the WORKHORSE (~7.5 per 25s)" survived a careful removal because prose that
DESCRIBES a rate looks harmless. So the guard runs on PROSE, and the RED cases
below are prose, not schema fields.

Both directions are proven: rate-bearing text must FAIL, and a report written
in conditions must PASS. A guard that rejects everything is not a guard.
"""
import ast
import sys

src = open("craft_pass_app.py").read()
mod = ast.parse(src)
ns = {}
WANT = ("_RATE_PATTERNS", "_DENSITY_ELEMENT", "_DENSITY_ANY",
        "rate_language")
picked = []
for node in mod.body:
    name = None
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        name = node.targets[0].id
    elif isinstance(node, ast.FunctionDef):
        name = node.name
    if name in WANT:
        picked.append(name)
        exec(compile(ast.Module([node], []), "<x>", "exec"), ns)

# A LOOKUP THAT FOUND NOTHING MUST NOT LOOK LIKE A CLEAN RUN.
missing = [w for w in WANT if w not in picked]
if missing:
    print(f"  *** the guard itself is ABSENT from craft_pass_app.py: {missing}")
    sys.exit(1)
rate_language = ns["rate_language"]

RED = [
    "Overlay text is the workhorse of these videos (~7.5 per 25s).",
    "The references cut roughly every 2 seconds when the energy is high.",
    "On average the hook resolves before the third beat.",
    "Sound lands on 60% of the emphasis moments.",
    "Text density is higher in the field videos than in the references.",
    "Cut density sits around 12 across these edits.",
    "These edits average about 16 cuts per video.",
    "Cuts arrive every 1.5 to 3 seconds through the middle section.",
]
GREEN = [
    "When a claim has just landed and the proof is visual, cut on the breath "
    "after the claim rather than the last word — the silence is what makes "
    "the viewer look up.",
    "Hold on the face when the sentence is still resolving; leave it the "
    "moment the voice starts describing something the viewer cannot see.",
    "A sound belongs where the picture changes against the voice, not where "
    "the voice is already loud.",
    "The 3-second mark is where a viewer decides, so the first idea has to be "
    "complete before it.",
    # THE FALSE POSITIVE THAT REJECTED A CORRECT REPORT. An idea, not a rate.
    "These are jump cuts that sacrifice visual smoothness for information "
    "density, which is the correct trade for this form.",
    "The emotional density of the opening is what earns the next line.",
]

fail = 0
for t in RED:
    hits = rate_language(t)
    if not hits:
        print(f"  *** RED CASE PASSED THE GUARD (guard is blind): {t}")
        fail += 1
for t in GREEN:
    hits = rate_language(t)
    if hits:
        print(f"  *** GREEN CASE REFUSED (guard over-fires): {t}\n      {hits}")
        fail += 1

print(f"smoke_synthesis_refuses_rates: {len(RED)} red + {len(GREEN)} green, "
      f"{fail} wrong")
sys.exit(1 if fail else 0)
