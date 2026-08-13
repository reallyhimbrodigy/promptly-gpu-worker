#!/usr/bin/env python3
"""EDITORIAL_LIVE gate cert — offline, $0, both directions `[§3.1/§6.1]`.

THE REQUIREMENT: restoring Vertex billing must cost ZERO additional
live-traffic spend. Until the owner personally flips users onto the brain,
every live user job takes the deterministic safe edit — the same path every job
has taken throughout the outage — while the harness, the cert apps and the
Lumen build loop call Gemini freely.

So there are exactly two things to prove, and a null result on either is
worthless without the other:

  KNOWN-BAD   with the gate OFF, a live call is genuinely SUPPRESSED. Not
              "usually", not "on the happy path" — a gate that fails open on an
              edge case is not a guarantee, and the whole point is that users
              CANNOT touch the brain.
  KNOWN-GOOD  with PROMPTLY_BUILD_LANE=1, the call goes THROUGH. A suppression
              that also blocks the build lane would stop Lumen being built,
              which is the campaign this gate exists to protect.

  python3 cert_editorial_live.py
"""
import ast
import os
import sys

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")


def main():
    for k in ("PROMPTLY_EDITORIAL_LIVE", "PROMPTLY_BUILD_LANE"):
        os.environ.pop(k, None)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import handler as H

    print("=== ARM 1: DEFAULT IS OFF — the safe state needs no configuration ===")
    check("gate off by default", H._editorial_live_enabled() is False)
    check("build lane off by default", H._build_lane() is False)
    check("=> live traffic is SUPPRESSED with nothing set",
          H._editorial_suppressed() is True)

    print("\n=== ARM 2: KNOWN-BAD — the call is genuinely blocked ===")
    try:
        H._call_gemini_post_cuts(None, "sys", "user", None, "model")
        check("a live editorial call RAISES", False,
              "it returned — live traffic can reach the brain")
    except H.EditorialSuppressed as e:
        check("a live editorial call RAISES EditorialSuppressed", True)
        check("the error says how to proceed deliberately",
              "PROMPTLY_BUILD_LANE" in str(e) and "redeploy" in str(e))
    except Exception as e:  # noqa: BLE001
        check("a live editorial call raises the RIGHT type", False,
              f"got {type(e).__name__} — an outage/timeout would be indistinguishable")
    check("the exception is its OWN type, not a bare RuntimeError",
          H.EditorialSuppressed is not RuntimeError
          and issubclass(H.EditorialSuppressed, RuntimeError))

    print("\n=== ARM 3: KNOWN-GOOD — the build lane is NOT suppressed ===")
    os.environ["PROMPTLY_BUILD_LANE"] = "1"
    check("build lane is not suppressed", H._editorial_suppressed() is False)
    try:
        H._call_gemini_post_cuts(None, "sys", "user", None, "model")
        check("build-lane call passes the gate", False, "unreachable: client=None")
    except H.EditorialSuppressed:
        check("build-lane call passes the gate", False,
              "SUPPRESSED IN THE BUILD LANE — this would stop Lumen being built")
    except Exception:
        # Any OTHER failure means it got past the gate and died on the null
        # client, which is exactly what "the call went through" looks like here.
        check("build-lane call passes the gate (fails later, on the null client)", True)
    os.environ.pop("PROMPTLY_BUILD_LANE")

    print("\n=== ARM 4: the owner's flip actually opens it ===")
    os.environ["PROMPTLY_EDITORIAL_LIVE"] = "1"
    check("gate ON => live traffic no longer suppressed",
          H._editorial_suppressed() is False)
    os.environ.pop("PROMPTLY_EDITORIAL_LIVE")
    check("and OFF again re-suppresses", H._editorial_suppressed() is True)

    print("\n=== ARM 5: THE FAIL-OPEN HOLE STAYS CLOSED ===")
    # The upstream door (force_safe_reason) has two conditions of its own —
    # `kept_words` non-empty and SAFE_EDIT_FALLBACK_ENABLED. If suppression
    # lived ONLY there, an empty transcript or a flipped kill switch would let a
    # live job call the model. The hard stop at the call helper is what makes
    # the gate a guarantee instead of a tendency, so assert it is still there.
    _src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "handler.py"), encoding="utf-8").read()
    _tree = ast.parse(_src)
    _fn = next((n for n in ast.walk(_tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_call_gemini_post_cuts"), None)
    check("_call_gemini_post_cuts still exists", _fn is not None)
    if _fn:
        _body_src = "\n".join(_src.splitlines()[_fn.lineno - 1:_fn.end_lineno])
        check("the HARD STOP is inside the call helper itself",
              "_editorial_suppressed()" in _body_src and "EditorialSuppressed" in _body_src,
              "suppression moved upstream-only — it can then fail open on an "
              "empty transcript or a flipped SAFE_EDIT_FALLBACK_ENABLED")
        # and it must come BEFORE any network work
        _stop_at = _body_src.index("_editorial_suppressed()")
        _call_at = _body_src.find("client.")
        check("the stop precedes any client use",
              _call_at == -1 or _stop_at < _call_at)
    check("the upstream safe-path door is ALSO wired (defence in depth)",
          'force_safe_reason = "editorial_live_off"' in _src)

    print("\n=== ARM 6: SAFE_EDIT_FALLBACK_ENABLED is NOT the gate's dependency ===")
    # A kill switch that disables the fallback must not also disable the gate.
    os.environ["SAFE_EDIT_FALLBACK_ENABLED"] = "0"
    check("suppression holds even with the fallback kill switch off",
          H._editorial_suppressed() is True)
    try:
        H._call_gemini_post_cuts(None, "s", "u", None, "m")
        check("...and the hard stop still raises", False, "call got through")
    except H.EditorialSuppressed:
        check("...and the hard stop still raises", True)
    except Exception as e:  # noqa: BLE001
        check("...and the hard stop still raises", False, f"{type(e).__name__}")
    os.environ.pop("SAFE_EDIT_FALLBACK_ENABLED")

    print("\n=== ARM 7: the build-lane bypass is REACHABLE where it is used ===")
    # The cert apps import build_lane INSIDE their container functions. A
    # deferred import that is not image-mounted ImportErrors in the container —
    # exactly where nobody is watching — and the cert would then run SUPPRESSED
    # and report a null result that looks like data.
    _ma = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "modal_app.py"), encoding="utf-8").read()
    check("build_lane.py is image-mounted", '"build_lane.py"' in _ma,
          "deferred import not mounted — the bypass would ImportError in-container")
    import build_lane as _bl
    check("mark_build_lane sets the marker", _bl.mark_build_lane("cert") is True
          and _bl.is_build_lane() is True)
    check("...and the gate sees it", H._editorial_suppressed() is False)
    os.environ.pop("PROMPTLY_BUILD_LANE", None)
    _apps = ["cert_mg_honoring_planonly_app.py", "cert_planonly_fps_ab_app.py",
             "cert_planonly_fps_ab_corpus_app.py", "cert_e1_ab_app.py"]
    for _a in _apps:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), _a)
        if os.path.exists(_p):
            check(f"{_a} marks the build lane",
                  "mark_build_lane(" in open(_p, encoding="utf-8").read(),
                  "this Gemini-calling app would run SUPPRESSED and report a null "
                  "that looks like a result")

    print()
    if FAILURES:
        print(f"EDITORIAL-LIVE CERT: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("EDITORIAL-LIVE CERT: ALL PASS (off by default, live call blocked with its own "
          "exception type, build lane passes through, owner's flip opens it, hard stop "
          "cannot fail open on an empty transcript or a flipped kill switch)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
