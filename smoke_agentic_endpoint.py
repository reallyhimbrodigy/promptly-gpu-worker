#!/usr/bin/env python3
"""The server has a way in, and it cannot be handed the wrong plan shape.

THE GAP THIS CLOSES. Every job dispatches to MODAL_ENDPOINT_URL — `run_job` on
modal_app.py, handler.py's path. Nothing routed to the agentic app:
`grep -ic agentic server.js lib/` returned ZERO. Re-edit and multi-upload were
built in the worker and unreachable from the product.

A SEPARATE URL IS THE ROUTE DECISION. The scope required a per-job record of
which pipeline produced a job, stored at creation, never inferred from which
plan column is populated. Its own endpoint makes the choice explicit at
dispatch: the server picks a URL and THE URL IS THE PIPELINE.

THE SHAPE GUARD IS THE ONE THAT MATTERS. handler's `edit_recipe` is a dict; the
agentic plan is a LIST of source-span entries. If the server ever hands one to
the other, `typeof === 'object'` passes on both and the failure is a confident
edit built from a plan the path cannot read — the _delivered predicate class
that already cost three delivery paths. This refuses rather than coerces.

RED-proven by red_proof_agentic_endpoint.py.
"""
import ast
import pathlib
import sys

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
            and n.name == "run_agentic"), None)
check("the app exposes run_agentic", _fn is not None)
if _fn is None:
    print("\nAGENTIC-ENDPOINT: FAIL"); sys.exit(1)

_decs = [ast.unparse(d) for d in _fn.decorator_list]
check("it is a POST fastapi_endpoint",
      any("fastapi_endpoint" in d and "POST" in d for d in _decs), f"{_decs}")
check("it is an app.function, so it has the image and secrets",
      any("app.function" in d for d in _decs), f"{_decs}")

# ── SPAWN, NOT CALL ─────────────────────────────────────────────────────────
_calls = [ast.unparse(n) for n in ast.walk(_fn) if isinstance(n, ast.Call)]
check("it SPAWNS the edit rather than calling it",
      any("edit.spawn" in c for c in _calls),
      "an edit runs for minutes and .remote() dies with the client — this repo "
      "has already paid for that")
check("and it does NOT block on the result",
      not any(".remote(" in c for c in _calls), f"{[c[:40] for c in _calls]}")
check("it returns a call id the server can poll",
      "call_id" in ast.unparse(_fn))

# ── THE SHAPE GUARD ─────────────────────────────────────────────────────────
_body = ast.unparse(_fn)
check("a prior_plan of the wrong TYPE is refused, not coerced",
      "isinstance(_plan, list)" in _body and "error" in _body,
      "handler's edit_recipe is a dict and this plan is a list; typeof === "
      "'object' passes on both")
check("the refusal names which shape it expected",
      "edit_recipe" in _body,
      "a refusal that does not say what was wrong sends the reader to the "
      "wrong file")

# ── THE RE-EDIT PAYLOAD REACHES edit() ──────────────────────────────────────
_spawn = next((n for n in ast.walk(_fn) if isinstance(n, ast.Call)
               and "spawn" in ast.unparse(n.func)), None)
_kw = {k.arg for k in (_spawn.keywords if _spawn else [])}
for _need in ("source_key", "brief", "prior_plan", "instruction",
              "src_url", "out_url", "out_key"):
    check(f"{_need} is forwarded", _need in _kw, f"{sorted(_kw)}")

# ── edit() ACCEPTS WHAT IS FORWARDED ────────────────────────────────────────
_edit = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
              and n.name == "edit"), None)
_eargs = {a.arg for a in _edit.args.args} if _edit else set()
check("every forwarded name is a real parameter of edit()",
      _kw <= _eargs, f"forwarded but unknown: {sorted(_kw - _eargs)}")

# ── THE MODE IS REPORTED, so a re-edit is countable ─────────────────────────
# QUOTE-AGNOSTIC. The first version looked for '"mode"' and ast.unparse emits
# single quotes — the check failed on a response that was correct. Asserting the
# RETURNED DICT has the key, rather than pattern-matching the rendered source.
_rets = [n for n in ast.walk(_fn) if isinstance(n, ast.Return)
         and isinstance(n.value, ast.Dict)]
_keys = {k.value for r in _rets for k in r.value.keys
         if isinstance(k, ast.Constant)}
check("the response says whether this was an edit or a reedit",
      "mode" in _keys and "reedit" in _body,
      "a re-edit that reports as an edit is uncountable, and the count is how "
      "we know the feature is used")

print()
if fails:
    print("AGENTIC-ENDPOINT: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("AGENTIC-ENDPOINT: PASS — POST endpoint, spawns rather than blocks, "
      "refuses a wrong-shaped plan, forwards the whole re-edit payload to real "
      "parameters, and reports its mode")
