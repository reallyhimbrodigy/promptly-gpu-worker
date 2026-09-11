#!/usr/bin/env python3
"""No dict literal in the app repeats a key.

FOUND BY PYFLAKES AFTER A MERGE, twice in one dict: the zoom segment record
already carried `"beat": v.get("beat")` as its second key and the merge
appended it again at the end. Same expression both times, so nothing was lost
— and a repeated key is a SILENT OVERWRITE waiting for the day the two values
differ. The later one wins, with no error, in a record four consumers read.

This is the merge hazard in its cheapest form: two branches each add the field
the other was missing, both are right, and the result is a dict whose shape
depends on which line came second. Pyflakes says it; nothing was reading
pyflakes as a gate, so it says it into a log.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("agentic_editor_app.py", "handler.py")

fail = 0
for name in FILES:
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        continue
    try:
        tree = ast.parse(open(p, encoding="utf-8").read())
    except SyntaxError as e:
        print(f"  *** {name} does not parse: {e}")
        fail += 1
        continue
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        seen = {}
        for k in n.keys:
            if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
                continue
            if k.value in seen:
                print(f"  *** {name}:{k.lineno} dict repeats the key "
                      f"{k.value!r} (first at line {seen[k.value]}) — the "
                      f"later value wins silently")
                fail += 1
            else:
                seen[k.value] = k.lineno

print(f"smoke_no_duplicate_dict_keys: {fail} wrong")
sys.exit(1 if fail else 0)
