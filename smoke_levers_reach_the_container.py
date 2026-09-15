#!/usr/bin/env python3
"""SMOKE — every parameter main() accepts is PASSED to the function it configures.

WHY. `--think-tokens 2048 --prestage-title "..."` were accepted by the CLI,
bound in main(), and never reached `edit`: an unasserted string replace hit the
FIRST occurrence — the `--wait` branch's `edit.remote` — and left `edit.spawn`
untouched. The run printed `THINKING CAP: UNCAPPED` and no PRESTAGE line, which
is the only reason it was caught; a lever that silently does not arrive is a
null arm reported as a result.

Third unasserted replace to land wrong in one session. A flag's test surface is
the PAIR — the parameter and the call site — not the parameter alone.
"""
import ast
import sys

fails = []
src = open("chatcut_job_app.py", encoding="utf-8").read()
tree = ast.parse(src)

main_fn = next(n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == "main")
params = [a.arg for a in main_fn.args.args]
# what main() forwards, per call site
sites = {}
for node in ast.walk(main_fn):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ("spawn", "remote"):
        sites[node.func.attr] = {k.arg for k in node.keywords}

CONFIG = [p for p in params
          if p not in ("run_id", "wait", "plan_file", "clip_url", "brief")]
for site in ("spawn", "remote"):
    if site not in sites:
        fails.append(f"no edit.{site}() call found in main()")
        continue
    for p in CONFIG:
        ok = p in sites[site] or p == "plan"
        # plan_file is read into plan_text and forwarded as `plan`
        if p == "plan_text":
            continue
        if not ok:
            fails.append(f"main() accepts `{p}` but edit.{site}() never "
                         f"receives it — the flag is accepted and discarded")
        print(f"  [{'ok' if ok else 'FAIL'}] edit.{site}() receives `{p}`")

print(("FAIL %d" % len(fails)) if fails else "OK")
sys.exit(1 if fails else 0)
