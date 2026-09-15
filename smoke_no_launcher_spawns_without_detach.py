#!/usr/bin/env python3
"""SMOKE — every entrypoint that starts a Modal job calls require_detach().

FIFTH TIME THE CLASS HAS COST A RUN. The guard existed — in chatcut_job_app.py,
inline — and `agentic_editor_app.py::main` did not have it, so it ran 468s, the
client dropped, and the app stopped mid-ruling with the whole ledger lost. A
guard written once in one file is not a rule; it is a rule one file happens to
know.

SO THE CHECK IS AN ENUMERATION, NOT A REMINDER. It walks the AST of every Modal
app in this lane, finds every `@app.local_entrypoint` that calls `.remote(` or
`.spawn(`, and asserts each one calls require_detach. Adding a new launcher
without the guard fails here rather than on the run that loses the work.

AND IT TAKES A DESCRIPTION, NEVER A SKIP LIST. An entrypoint that genuinely
does not need it — one that reads a Dict and returns in a second — still CALLS
require_detach, with `why_not=` saying so in its own words. That keeps it
enumerable: the check sees a call either way, and the reason is readable by the
next person instead of being an absence they have to interpret.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# SCOPED TO THIS LANE'S LAUNCHERS, DELIBERATELY. Run across every *_app.py in
# the repo this check finds 150 unguarded entrypoints — and that IS a real
# finding, reported rather than silently fixed, because most of them belong to
# other lanes and the working agreement is that nobody edits outside their
# region. Many are also one-shot probes and queries where a client drop costs a
# second, not a run; guarding those would be a check tight enough to reject
# correct code, which this repo has paid for before.
#
# So the enumeration is over what this lane OWNS and what actually loses work.
# Widening it is a decision someone makes on purpose, by adding a name here.
APPS = ["chatcut_job_app.py", "agentic_editor_app.py"]


def launchers(path):
    """[(name, starts_job, guards)] for every local_entrypoint in one file."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decs = [ast.unparse(d) for d in node.decorator_list]
        if not any("local_entrypoint" in d for d in decs):
            continue
        starts, guards = False, False
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                f = sub.func
                if isinstance(f, ast.Attribute) and f.attr in ("remote", "spawn"):
                    starts = True
                if isinstance(f, ast.Name) and f.id == "require_detach":
                    guards = True
        out.append((node.name, starts, guards))
    return out


def scan(files):
    rows, bad = [], []
    for f in files:
        for name, starts, guards in launchers(os.path.join(HERE, f)):
            rows.append((f, name, starts, guards))
            if starts and not guards:
                bad.append("%s::%s starts a Modal job and never calls "
                           "require_detach — a client drop loses the run"
                           % (f, name))
    return rows, bad


if __name__ == "__main__":
    rows, bad = scan(APPS)
    starters = [r for r in rows if r[2]]
    print("  %d Modal app file(s); %d local_entrypoint(s); %d start a job"
          % (len(APPS), len(rows), len(starters)))
    for f, name, starts, guards in starters:
        print("    [%s] %s::%s" % ("ok" if guards else "FAIL", f, name))
    for b in bad:
        print("  [FAIL] %s" % b)

    # RED PROOF — a launcher without the call must fail, in a real file shape.
    print("\n  RED PROOF")
    tmp = os.path.join(HERE, "_red_launcher_app.py")
    open(tmp, "w").write(
        "import modal\napp = modal.App('x')\n\n"
        "@app.local_entrypoint()\ndef main():\n    edit.remote(1)\n")
    try:
        _, red = scan(["_red_launcher_app.py"])
        print("    an unguarded launcher -> %d leg(s) red" % len(red))
        red_ok = bool(red)
    finally:
        os.unlink(tmp)

    ok = not bad and red_ok and len(starters) >= 2
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
