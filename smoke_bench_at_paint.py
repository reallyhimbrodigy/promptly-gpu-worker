#!/usr/bin/env python3
"""The second bench must run BEFORE the paint, be printed, and be ledgered.

WHY ALL THREE. The startup bench cannot separate a slow MACHINE from
CONTENTION that arrived later, because it runs minutes before the paint —
and that distinction decides whose problem the 6x spread is. A second bench
taken at paint time answers it, but only if it actually runs before the
subprocess (after is a different question), only if it is printed (a counter
that reaches the ledger and no output answers nothing — three instances in one
session), and only if it is ledgered (the log answers a reading, the ledger
answers the comparison across every fixture).

Checked on the AST, not on a substring: a call can sit after the subprocess
and still grep clean.
"""
import ast
import sys

src = open("agentic_editor_app.py").read()
fn = None
for n in ast.walk(ast.parse(src)):
    if isinstance(n, ast.FunctionDef) and n.name == "render_remotion_batch":
        fn = n
        break

fail = 0
if fn is None:
    print("  *** render_remotion_batch is gone")
    sys.exit(1)

bench_line = sub_line = ledger_line = print_line = None
for n in ast.walk(fn):
    if isinstance(n, ast.Call):
        f = n.func
        name = getattr(f, "id", None) or getattr(f, "attr", None)
        if name == "container_benchmark" and bench_line is None:
            bench_line = n.lineno
        if name == "run" and getattr(getattr(f, "value", None), "id", "") == "subprocess":
            sub_line = n.lineno
        if name == "print" and any(
                isinstance(a, ast.JoinedStr) and "BENCH AT PAINT" in ast.dump(a)
                for a in n.args):
            print_line = print_line or n.lineno
    if isinstance(n, ast.Constant) and n.value == "bench_at_paint":
        ledger_line = n.lineno

if bench_line is None:
    print("  *** no container_benchmark() call inside render_remotion_batch — "
          "the machine-vs-contention question cannot be answered")
    fail += 1
if sub_line is None:
    print("  *** no subprocess.run — this is not the paint path any more")
    fail += 1
if bench_line and sub_line and bench_line > sub_line:
    print(f"  *** the bench runs AFTER the paint (line {bench_line} > "
          f"{sub_line}) — that measures the machine the paint left behind")
    fail += 1
if ledger_line is None:
    print("  *** the second bench never reaches the ledger")
    fail += 1
if print_line is None:
    print("  *** the second bench is never PRINTED")
    fail += 1

print(f"smoke_bench_at_paint: bench@{bench_line} print@{print_line} "
      f"ledger@{ledger_line} paint@{sub_line} — {fail} wrong")
sys.exit(1 if fail else 0)
