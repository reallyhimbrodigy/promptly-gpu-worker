#!/usr/bin/env python3
"""RED proof: the agent must actually be told, from the table that enforces."""
import os
import shutil
import subprocess
import sys

APP = "agentic_editor_app.py"
BAK = "/tmp/_taught_bak.py"
shutil.copy(APP, BAK)
env = dict(os.environ, PYTHONPATH=".")


def run():
    r = subprocess.run([sys.executable, "smoke_card_props_taught.py"],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def mut(old, new, label, expect):
    src = open(APP, encoding="utf-8").read()
    if src.count(old) != 1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x")
        return False
    open(APP, "w", encoding="utf-8").write(src.replace(old, new, 1))
    rc, out = run()
    shutil.copy(BAK, APP)
    ok = rc != 0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok:
        print(f"      expected {expect!r}")
    return ok


rc, out = run()
print(f"BASELINE exit={rc}")
assert rc == 0, out
r = []

# 1. The description stops carrying the table — back to "read the catalogue".
r.append(mut('+ MG_PROPS_TEACH\n', '+ ""\n',
             "the agent is no longer told any props",
             "the description carries it verbatim"))

# 2. A hand-typed copy that has drifted from the table.
r.append(mut('    return "; ".join(out)',
             '    return "; ".join(out).replace("StatCard: label+value",\n'
             '                                   "StatCard: label+stat")',
             "the taught shape drifts from the enforced shape",
             "StatCard specifically teaches value"))

# 3. Styling props taught as the component's shape.
r.append(mut('            _c = [p for p in _v["declared"] if not _MG_STYLE_PROP.search(p)][:4]',
             '            _c = list(_v["declared"])[:4]',
             "styling props are taught as the shape",
             "is not taught a styling prop as its shape"))

# 4. The shorthand stops being offered.
r.append(mut('"omit card_props entirely and pass "\n                                           "card_hero + card_label; the hero "',
             '"do something else entirely; the hero "',
             "the StatCard shorthand is withdrawn",
             "the StatCard shorthand is still offered"))

rc, out = run()
print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
sys.exit(0 if all(r) and rc == 0 else 1)
