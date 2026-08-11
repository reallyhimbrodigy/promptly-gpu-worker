#!/usr/bin/env python3
"""Static Rule-1 gate for the lane/delivery fixes (2026-08-10). Zero-cost AST
checks that make each fix's regression impossible to reintroduce silently.
Proposed for validate_deploy wiring (TRUTH owns the wiring; this file is the
check). Exit 0 = all pass; non-zero prints the first violated law.

Laws asserted:
 1. LANG-BUNDLE SCOPE — no `edit_plan` name reference inside
    _do_edit_recipe_overlapped. The bundle thread runs BEFORE the enclosing
    scope binds edit_plan (future_edit.result() awaits the thread), so any such
    reference is the unbound-name NameError that nulled lang_bundle on 218/218
    while a green nest-guard swore the field was wired.
 2. LANG-BUNDLE CHANNEL — _lang_bundle_holder is stored in handler scope and
    read by the result build (the thread→result channel exists end to end).
 3. COMPLETION-POST RETRY — run_pipeline_bg's completion POST retries (a for
    loop with >=3 backoff delays wrapping requests.post). The single-shot POST
    is what turned every transient miss into a 900s fallback settle.
 4. JOB-TABLE DEFAULT — write_job_status defaults to the real table
    ("video_jobs"), never "jobs" (a table that does not exist; PostgREST 404s
    and the fail-open catch swallows the entire durable layer).
"""
import ast
import re
import sys

HANDLER = "handler.py"
MODAL_APP = "modal_app.py"


def fail(msg):
    print(f"CERT-DELIVERY FAIL: {msg}")
    sys.exit(1)


# ── 1 + 2: lang-bundle scope + channel ──────────────────────────────────────
tree = ast.parse(open(HANDLER).read())

class Scope(ast.NodeVisitor):
    def __init__(self):
        self.stack = []
        self.edit_plan_in_overlapped = []
        self.holder_store = []
        self.holder_load = []

    def visit_FunctionDef(self, n):
        self.stack.append(n.name)
        self.generic_visit(n)
        self.stack.pop()

    def visit_Name(self, n):
        if n.id == "edit_plan" and "_do_edit_recipe_overlapped" in self.stack:
            self.edit_plan_in_overlapped.append(n.lineno)
        if n.id == "_lang_bundle_holder":
            if isinstance(n.ctx, ast.Store):
                self.holder_store.append((n.lineno, tuple(self.stack)))
            else:
                self.holder_load.append((n.lineno, tuple(self.stack)))
        self.generic_visit(n)

s = Scope()
s.visit(tree)
if s.edit_plan_in_overlapped:
    fail(f"edit_plan referenced inside _do_edit_recipe_overlapped at "
         f"{s.edit_plan_in_overlapped} — this is the unbound-closure NameError "
         f"that nulled lang_bundle on every job (0/218). Use _lang_bundle_holder.")
if not any(st == ("handler",) for _, st in s.holder_store):
    fail("_lang_bundle_holder is no longer stored in handler scope — the "
         "thread→result lang-bundle channel is broken.")
in_thread = any("_do_edit_recipe_overlapped" in st for _, st in s.holder_load)
in_result = any(st == ("handler",) for _, st in s.holder_load)
if not (in_thread and in_result):
    fail(f"_lang_bundle_holder channel incomplete (thread write: {in_thread}, "
         f"result read: {in_result}).")

# ── 3: completion-post retry ────────────────────────────────────────────────
src = open(MODAL_APP).read()
m = re.search(r"for _cb_i, _cb_delay in enumerate\(\(([^)]*)\)\)", src)
if not m:
    fail("run_pipeline_bg completion POST retry loop is gone — a single-shot "
         "POST turns every transient miss into a 900s fallback settle.")
delays = [d.strip() for d in m.group(1).split(",") if d.strip()]
if len(delays) < 3:
    fail(f"completion POST retry has only {len(delays)} attempts — need >=3.")
if "callback_post" not in src:
    fail("completion POST failure persistence (result->callback_post) removed — "
         "the miss mechanism becomes unmeasurable again.")

# ── 4: job-table default ────────────────────────────────────────────────────
hsrc = open(HANDLER).read()
if re.search(r"PROMPTLY_JOB_TABLE.{0,40}or\s+[\"']jobs[\"']", hsrc):
    fail('write_job_status default table regressed to "jobs" (nonexistent — '
         'the whole durable layer silently no-ops without the env override).')
if not re.search(r"PROMPTLY_JOB_TABLE.{0,40}or\s+[\"']video_jobs[\"']", hsrc):
    fail("write_job_status video_jobs default not found.")

print("CERT-DELIVERY PASS: lang-bundle scope+channel, completion-post retry+persist, video_jobs default")
