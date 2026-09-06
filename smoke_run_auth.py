"""SMOKE — inbound auth on the public worker endpoints.

WHAT WAS OPEN. run_job and warmup are modal.fastapi_endpoint POSTs reachable
from the open internet with no authentication: an unauthenticated curl returned
{"spawned": true} and started a real job on a GPU worker.

WHY THIS SMOKE EXISTS SEPARATELY FROM THE DEPLOY GATE. The gate asserts the
wiring is present in the source; this drives the LOGIC through every branch,
including the two that only matter once enforcement is armed. A check that has
never seen its failure branch is not yet a check.
"""
import ast
import os
import sys

FAIL = []


def ok(cond, msg):
    if not cond:
        FAIL.append(msg)


# Load the two pure helpers WITHOUT importing modal_app (which needs the modal
# SDK and would build an image). Their purity is what makes this possible.
_src = open("modal_app.py", encoding="utf-8").read()
_tree = ast.parse(_src)
_ns = {}
_wanted = {"_run_auth_verdict", "_run_auth_enforcing", "_check_run_auth"}
_found = set()
for _n in _tree.body:
    if isinstance(_n, ast.FunctionDef) and _n.name in _wanted:
        exec(compile(ast.Module([_n], []), "<smoke>", "exec"), _ns)
        _found.add(_n.name)
    if isinstance(_n, ast.Assign) and getattr(_n.targets[0], "id", "") == "_RUN_AUTH_FIELD":
        exec(compile(ast.Module([_n], []), "<smoke>", "exec"), _ns)

ok(_found == _wanted,
   f"auth helpers missing from modal_app.py at TOP LEVEL: {sorted(_wanted - _found)} "
   f"— a helper nested inside another function would also land here, and would "
   f"never run for a real request")

if _found == _wanted:
    verdict = _ns["_run_auth_verdict"]
    check = _ns["_check_run_auth"]
    FIELD = _ns.get("_RUN_AUTH_FIELD", "_worker_auth")
    SECRET = "s3cr3t-value-for-the-smoke"

    def env(secret=None, enforce=None):
        os.environ.pop("MODAL_RUN_SECRET", None)
        os.environ.pop("PROMPTLY_RUN_AUTH_ENFORCE", None)
        if secret is not None:
            os.environ["MODAL_RUN_SECRET"] = secret
        if enforce is not None:
            os.environ["PROMPTLY_RUN_AUTH_ENFORCE"] = enforce

    # ── the four verdicts ───────────────────────────────────────────────────
    env(secret=SECRET)
    ok(verdict({FIELD: SECRET}) == "ok", "a correct secret is not 'ok'")
    ok(verdict({}) == "missing", "an absent field is not 'missing'")
    ok(verdict({FIELD: ""}) == "missing", "an EMPTY secret is not 'missing'")
    ok(verdict({FIELD: "wrong"}) == "mismatch", "a wrong secret is not 'mismatch'")
    ok(verdict(None) == "missing", "a null body is not 'missing'")
    ok(verdict({FIELD: SECRET + "x"}) == "mismatch",
       "a secret with a trailing byte is accepted — prefix comparison")
    ok(verdict({FIELD: SECRET[:-1]}) == "mismatch",
       "a TRUNCATED secret is accepted — prefix comparison")
    env(secret="")
    ok(verdict({FIELD: SECRET}) == "server_secret_unset",
       "an UNSET server secret is not reported as such")
    ok(verdict({FIELD: ""}) == "server_secret_unset",
       "an unset server secret with an empty client secret must still be "
       "'server_secret_unset' — otherwise empty==empty reads as a match")

    # ── DARK: observes, refuses nothing ─────────────────────────────────────
    env(secret=SECRET, enforce=None)
    for body in ({FIELD: SECRET}, {}, {FIELD: "wrong"}, None):
        ok(check(body, "run_job") is None,
           "DARK mode refused a request — shipping this would 403 live dispatch "
           "before the caller was proven to send the secret")
    env(secret=None, enforce=None)
    ok(check({}, "warmup") is None, "DARK mode refused with no server secret set")
    env(secret=SECRET, enforce="0")
    ok(check({}, "run_job") is None, "enforce=0 still refused")

    # ── ARMED: fails closed ─────────────────────────────────────────────────
    env(secret=SECRET, enforce="1")
    ok(check({FIELD: SECRET}, "run_job") is None,
       "ARMED mode refused a CORRECT secret — this would 403 all real dispatch")
    for body, label in (({}, "missing"), ({FIELD: "wrong"}, "wrong"), (None, "null body")):
        r = check(body, "run_job")
        ok(isinstance(r, dict) and r.get("error") == "unauthorized",
           f"ARMED mode ALLOWED a request with a {label} secret")
    env(secret=None, enforce="1")
    r = check({FIELD: SECRET}, "run_job")
    ok(isinstance(r, dict) and r.get("verdict") == "server_secret_unset",
       "ARMED with an UNSET server secret ALLOWED the request — an unset secret "
       "must never mean 'let everyone in'")

    # ── timing safety, asserted on the AST ─────────────────────────────────
    # NOT a substring search. The first version of this check was
    # `"compare_digest" in <function source>`, and it PASSED against a mutant
    # that used `==`, because the comment above the return explains why
    # compare_digest is used — the comment defended the code from its own test.
    # Same class as every text-match false green in this repo: source is where
    # code might be, the AST is where it is.
    _vfn = next(n for n in _tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_run_auth_verdict")
    _cmp_calls = [c for c in ast.walk(_vfn)
                  if isinstance(c, ast.Call)
                  and getattr(c.func, "attr", "") == "compare_digest"]
    ok(len(_cmp_calls) == 1,
       "the secret is compared without a real hmac.compare_digest CALL — a wrong "
       "secret becomes recoverable a byte at a time from response timing")
    # And no bare ==/!= against the secret anywhere in the function.
    _bad_eq = [c for c in ast.walk(_vfn)
               if isinstance(c, ast.Compare)
               and any(isinstance(o, (ast.Eq, ast.NotEq)) for o in c.ops)
               and any(getattr(n, "id", "") in ("_given", "_expected")
                       for n in ast.walk(c))]
    ok(not _bad_eq,
       "the secret is compared with ==/!= somewhere in _run_auth_verdict — "
       "short-circuiting byte comparison leaks the secret through timing")

# ── both endpoints call it, and BEFORE they do any work ────────────────────
_cls = [n for n in ast.walk(_tree) if isinstance(n, ast.ClassDef)]
_fns = {}
for _c in _cls:
    for _f in _c.body:
        if isinstance(_f, ast.FunctionDef):
            _fns[_f.name] = _f
for _name in ("run_job", "warmup"):
    _f = _fns.get(_name)
    ok(_f is not None, f"{_name} not found in modal_app.py")
    if not _f:
        continue
    body = [st for st in _f.body
            if not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant))]
    calls = [c for c in ast.walk(_f)
             if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_check_run_auth"]
    ok(len(calls) == 1, f"{_name} does not call _check_run_auth exactly once")
    # The FIRST executable statement must be the auth assignment. Anything
    # before it is work done for an unauthenticated caller.
    first = body[0] if body else None
    ok(first is not None and isinstance(first, ast.Assign)
       and any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "_check_run_auth"
               for c in ast.walk(first)),
       f"{_name} does WORK before checking auth — an unauthenticated caller "
       f"would still reach it")
    ok(any(isinstance(st, ast.If) and any(isinstance(x, ast.Return) for x in ast.walk(st))
           for st in body[:2]),
       f"{_name} computes the verdict but never RETURNS on denial")

if FAIL:
    print("FAIL smoke_run_auth:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_run_auth — 9 verdicts, dark allows all, armed fails closed "
      "(incl. unset server secret), compare_digest, both endpoints check FIRST")
