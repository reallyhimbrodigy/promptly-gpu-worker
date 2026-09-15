#!/usr/bin/env python3
"""SMOKE — the pre-staged title ACCEPTS every control the planner rules.

v1 accepted `colour` and nothing else. A plan carrying band=upper_third had
nowhere to put it, so the title rendered centred — across the subject's face,
on top of the source's own burned-in caption, and colliding with the platform
handle. The same day, `half_ruling_refusal` was changed to force the planner to
ANSWER all five controls. A planner that must answer and an acceptor that drops
four is the same defect from the two ends, and only the producer side had a
check.

The colour control landed correctly in that run precisely because it was the
one baked in. That is the argument for baking in all of them, and this is the
check that keeps them there.

NAMED, NOT COUNTED. A floor on "how many props" stays green while one specific
control quietly stops being read — and the control that goes is the one nobody
sees go.
"""
import re
import sys

SRC = open("chatcut_job_app.py", encoding="utf-8").read()
i = SRC.index('TITLE_COMPONENT = r"""')
COMP = SRC[i:SRC.index('"""', i + 22)]
j = SRC.index("TITLE_PROPS = [")
PROPS_SRC = SRC[j:SRC.index("\n]", j)]
DECLARED = re.findall(r'"key": "(\w+)"', PROPS_SRC)

# The planner's five controls, in the planner's vocabulary, mapped to the
# component's prop names. `case` is not here on purpose: the component applies
# textTransform: uppercase itself, which IS the answer to case for a title.
RULED = {"where": "band", "size": "size", "hold_s": "holdSeconds",
         "colour": "textColor"}

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


for ruled, prop in RULED.items():
    check(f"planner control `{ruled}` has a home as prop `{prop}`",
          prop in DECLARED, f"declared props: {DECLARED}")
    check(f"  ...and the component READS props.{prop}",
          f"props.{prop}" in COMP,
          "declared but never read is the v1 defect exactly")

for p in DECLARED:
    check(f"declared prop `{p}` is read by the component",
          f"props.{p}" in COMP)

# The band must actually move the layout, not just be read into a variable.
check("`band` reaches justifyContent",
      "justifyContent: justify" in COMP and "upper_third" in COMP)
check("`size` reaches fontSize",
      "fontSize: fontSize" in COMP and "dominant" in COMP)
check("`holdSeconds` reaches an exit",
      "holdFrames" in COMP and "exit" in COMP)

# The contract rules the validator taught, so a rewrite cannot quietly break them.
check("exactly one top-level component", COMP.count("const Component = (") == 1)
check("values are read through an identifier named `props`",
      "const props = (item && item.props)" in COMP)
check("the root is a plain div, never an AbsoluteFill",
      "<div style={rootStyle}>" in COMP and "AbsoluteFill" not in COMP)
check("no imperative font loading", "loadFont" not in COMP)

print(("FAIL %d" % len(fails)) if fails else "OK")
sys.exit(1 if fails else 0)
