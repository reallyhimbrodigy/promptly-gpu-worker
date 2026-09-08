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
import types

# fastapi is an IMAGE dependency, not a local one — modal_app imports
# JSONResponse only on the refusal path. Stubbed so this smoke can drive that
# branch and read the status code; the stub records exactly what the real class
# is constructed with, which is all this check needs.
if "fastapi" not in sys.modules:
    _fa = types.ModuleType("fastapi")
    _far = types.ModuleType("fastapi.responses")

    class _JSONResponse:                      # noqa: N801 - mirrors fastapi
        def __init__(self, status_code=200, content=None):
            self.status_code, self.content = status_code, content

    _far.JSONResponse = _JSONResponse
    _fa.responses = _far
    sys.modules["fastapi"] = _fa
    sys.modules["fastapi.responses"] = _far

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
    # EVERY module-level _RUN_AUTH_* constant, not a hand-kept list of one.
    # The named-constant version broke the moment _RUN_AUTH_LEGACY_ARMED was
    # added: the extracted function raised NameError deep inside the first
    # assertion. It failed LOUDLY here, which is luck — the gate's own leg (3)
    # carries a comment warning that a missing constant can make a leg "silently
    # test nothing". A prefix match means a new constant arrives with its
    # function instead of being remembered.
    if (isinstance(_n, ast.Assign)
            and getattr(_n.targets[0], "id", "").startswith("_RUN_AUTH")):
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
    # STATUS CODE, not just a body. The first armed build returned a plain dict,
    # which FastAPI serialises as HTTP 200 — and content-studio's dispatch judges
    # success with `if (r.ok)`, so a refusal read as a SUCCESSFUL dispatch and
    # the job silently never ran. Asserting only the body would have passed that
    # build: 8 of 8 live unauthenticated POSTs returned 200 with
    # {"error":"unauthorized"} while this smoke was green.
    for body, label in (({}, "missing"), ({FIELD: "wrong"}, "wrong"), (None, "null body")):
        r = check(body, "run_job")
        ok(r is not None, f"ARMED mode ALLOWED a request with a {label} secret")
        ok(getattr(r, "status_code", None) == 403,
           f"a {label} secret is refused with status "
           f"{getattr(r, 'status_code', '200 (a plain dict)')}, not 403 — the "
           f"caller checks r.ok, so a 200 makes a refused dispatch look "
           f"successful and the job is lost with no error anywhere")
    env(secret=None, enforce="1")
    r = check({FIELD: SECRET}, "run_job")
    _c = getattr(r, "content", None) if r is not None else None
    ok(isinstance(_c, dict) and _c.get("verdict") == "server_secret_unset"
       and getattr(r, "status_code", None) == 403,
       "ARMED with an UNSET server secret ALLOWED the request (or refused it "
       "without a 403) — an unset secret must never mean 'let everyone in'")

    # ── PER-ENDPOINT ARMING ────────────────────────────────────────────────
    # PROMPTLY_RUN_AUTH_ENFORCE=1 is LIVE in production (measured 2026-09-07:
    # 40/40 [runauth] lines read enforcing=1). The observer and the enforcer are
    # the same call, so without per-endpoint arming, wiring _check_run_auth into
    # prewarm/validate/diagnose would have enforced on them the instant the
    # image deployed — no dark phase, no denominator, and 403s to callers never
    # proven to send the secret. These assertions are the reason the observer
    # can ship at all.
    env(secret=SECRET, enforce="1")
    for _ep in ("run_job", "warmup"):
        ok(check({}, _ep) is not None,
           f"=1 no longer arms {_ep} — this DISARMS auth that is live today")
    for _ep in ("prewarm", "validate", "diagnose"):
        ok(check({}, _ep) is None,
           f"=1 armed {_ep}: the ALREADY-SET live flag would 403 it on deploy, "
           f"turning the dark observer into a blind arm")
    # A named endpoint arms, and ONLY it.
    env(secret=SECRET, enforce="run_job,warmup,validate")
    ok(check({}, "validate") is not None,
       "an explicitly named endpoint is not armed — there is no way to arm one "
       "endpoint at a time, so the only available move is to arm everything")
    ok(check({}, "prewarm") is None,
       "arming validate also armed prewarm — arming is not per-endpoint")
    ok(check({FIELD: SECRET}, "validate") is None,
       "an armed endpoint refused a CORRECT secret")
    # Whitespace-separated form, and an unknown name arms nothing.
    env(secret=SECRET, enforce="validate diagnose")
    ok(check({}, "diagnose") is not None, "space-separated arming does not parse")
    ok(check({}, "run_job") is None,
       "an explicit list that omits run_job still armed it — the list is not "
       "authoritative, so it cannot be used to disarm one endpoint")
    env(secret=SECRET, enforce="not_an_endpoint")
    for _ep in ("run_job", "warmup", "prewarm", "validate", "diagnose"):
        ok(check({}, _ep) is None,
           f"an unrecognised flag value armed {_ep} — a typo in the secret "
           f"would 403 production")

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
      "(incl. unset server secret), compare_digest, 5 endpoints check FIRST, per-endpoint arming")
