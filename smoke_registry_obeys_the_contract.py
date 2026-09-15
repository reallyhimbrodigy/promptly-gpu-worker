#!/usr/bin/env python3
"""SMOKE — every component the harness pre-registers obeys ChatCut's MG contract.

WHY A CHECKER AND NOT A PORT. The instruction was to pre-register all 34 ported
components. They cannot be: 26 of 29 frame-diff identical to Remotion and 0 of
29 LOAD, because ChatCut's validator refuses them on six counts — ~60 top-level
constants, four top-level components where exactly one is allowed,
React.createContext, Freeze, loadFont, and static prop-name matching. Faithful
to Remotion is not the same as correct here; each component needs rewriting to
the contract, as the title was.

So this is the gate that makes adding one CHEAP AND SAFE: the six rules, checked
statically, against every entry in the registry. A component that passes here
still has to validate at ChatCut — this catches the six known refusals before a
run pays for them, it does not replace the real validator.

RULES LEARNED FROM THE VALIDATOR, not from documentation.
"""
import re
import sys

SRC = open("chatcut_job_app.py", encoding="utf-8").read()

# every r""" ... """ component the harness can register
ENTRIES = {}
for m in re.finditer(r'(\w*COMPONENT\w*) = r"""(.*?)"""', SRC, re.S):
    ENTRIES[m.group(1)] = m.group(2)

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


check("the registry is not empty", bool(ENTRIES),
      "a check over an empty population asserts nothing")

for name, code in ENTRIES.items():
    print(f"  -- {name} --")
    check(f"{name}: exactly ONE top-level component",
          code.count("const Component = (") == 1,
          f"found {code.count('const Component = (')}")
    # no top-level constants: every const/let/var must be indented (inside fn)
    tops = [ln for ln in code.split("\n")
            if re.match(r"^(const|let|var)\s", ln)
            and not ln.startswith("const Component")]
    check(f"{name}: no top-level constants", not tops, str(tops[:3]))
    check(f"{name}: root is a plain div, never AbsoluteFill",
          "<div style={rootStyle}>" in code and "AbsoluteFill" not in code)
    check(f"{name}: values read through an identifier named `props`",
          "item.props" in code and re.search(r"\bconst props\b", code) is not None,
          "a static NAME match — binding item.props to `p` reports every "
          "property as declared-but-unused")
    check(f"{name}: no React.createContext", "createContext" not in code)
    check(f"{name}: no Freeze", not re.search(r"\bFreeze\b", code))
    check(f"{name}: no imperative loadFont", "loadFont" not in code)
    check(f"{name}: no `void` operator (the validator refuses it)",
          not re.search(r"\bvoid\s", code))

print(("FAIL %d" % len(fails)) if fails else "OK")
sys.exit(1 if fails else 0)
