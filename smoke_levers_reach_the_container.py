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
sites, site_vals = {}, {}
for node in ast.walk(main_fn):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ("spawn", "remote"):
        sites[node.func.attr] = {k.arg for k in node.keywords}
        # THE VALUE NAMES TOO, not only the keyword names. A lever can reach
        # the container under a DIFFERENT keyword — `--transcript-file` is read
        # into `_tx` and forwarded as `transcript=_tx` — and a leg that only
        # matches the parameter's own spelling calls that a discarded flag.
        # This is the readers-keyed-to-wording class inside a check: the
        # PROPERTY is "the value arrives", and the keyword's name is one
        # spelling of it.
        site_vals[node.func.attr] = {
            x.id for k in node.keywords for x in ast.walk(k.value)
            if isinstance(x, ast.Name)}

# WHICH LOCALS CARRY WHICH PARAMETER. One hop is enough for every case here and
# a second hop would be a resolver guessing; anything deeper must be named in
# the exclusion list with a reason, so it is an argument on the record.
carries = {}
for node in ast.walk(main_fn):
    if isinstance(node, ast.Assign):
        srcs = {x.id for x in ast.walk(node.value) if isinstance(x, ast.Name)}
        for t in node.targets:
            for nm in ([t] if isinstance(t, ast.Name) else []):
                for pr in srcs & set(params):
                    carries.setdefault(pr, set()).add(nm.id)
    elif isinstance(node, ast.With):
        # `with open(transcript_file) as fh:` then a read inside — the param is
        # consumed by the with-item and the local is bound in the body.
        for it in node.items:
            srcs = {x.id for x in ast.walk(it.context_expr)
                    if isinstance(x, ast.Name)}
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign):
                    for t in sub.targets:
                        if isinstance(t, ast.Name):
                            for pr in srcs & set(params):
                                carries.setdefault(pr, set()).add(t.id)

CONFIG = [p for p in params
          if p not in ("run_id", "wait", "plan_file", "clip_url", "brief")]
for site in ("spawn", "remote"):
    if site not in sites:
        fails.append(f"no edit.{site}() call found in main()")
        continue
    for p in CONFIG:
        ok = (p in sites[site] or p == "plan"
              or bool(carries.get(p, set()) & site_vals[site]))
        # plan_file is read into plan_text and forwarded as `plan`
        if p == "plan_text":
            continue
        if not ok:
            fails.append(f"main() accepts `{p}` but edit.{site}() never "
                         f"receives it — the flag is accepted and discarded")
        _via = sorted(carries.get(p, set()) & site_vals[site])
        print(f"  [{'ok' if ok else 'FAIL'}] edit.{site}() receives `{p}`"
              + (f" (as {_via[0]})" if _via and p not in sites[site] else ""))

print(("FAIL %d" % len(fails)) if fails else "OK")
sys.exit(1 if fails else 0)
