#!/usr/bin/env python3
"""One modal stub, imported by every check that needs to import the app.

WHY THIS EXISTS. Twenty-eight check files each carried their own near-identical
copy of a `types.ModuleType("modal")` stub, and every one modelled the same six
symbols: App, Image, Secret, Volume, Cls, Function.

Then the app grew `@modal.fastapi_endpoint` — the server's way in — and the
import died with "module 'modal' has no attribute 'fastapi_endpoint'" in EVERY
ONE OF THEM, one file at a time. The gate reported a defect in its own STUB as
a defect in the code and blocked a commit whose message was accurate.

TWENTY-EIGHT COPIES OF A RULE IS THE COPY PROBLEM AT ITS LARGEST. This repo has
now paid for it three ways in one session: a smoke driving its own
reimplementation of the merge while the shipped path went untested, two call
sites deriving the unbuildable set with only one guarded, and this. The fix is
always the same — one definition, imported.

A STUB THAT MODELS LESS THAN THE MODULE USES turns every new surface into a
false failure, and a false failure on arrival gets the surface reverted rather
than the stub fixed. So this is deliberately GENEROUS: every decorator Modal
offers at module level is an identity decorator here, because these checks ask
whether symbols EXIST, not what Modal does with them.

    import modal_stub; modal_stub.install()
    import agentic_editor_app as A

`install()` uses setdefault, so a real `modal` already imported wins — the stub
is for environments without one, never a way to shadow the real package.
"""
import sys
import types


class _Any:
    """Accepts anything, returns itself. Enough for import-time symbol checks."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, n):
        return _Any()

    def __call__(self, *a, **k):
        return _Any()

    def function(self, *a, **k):
        return lambda f: f

    def local_entrypoint(self, *a, **k):
        return lambda f: f

    def cls(self, *a, **k):
        return lambda f: f


# Module-level DECORATORS. Identity, because existence is the question.
_DECORATORS = ("fastapi_endpoint", "web_endpoint", "asgi_app", "wsgi_app",
               "enter", "exit", "method", "batched", "concurrent")
# Module-level CLASSES and factories.
_OBJECTS = ("App", "Image", "Secret", "Volume", "Cls", "Function", "Mount",
            "NetworkFileSystem", "Dict", "Queue", "Sandbox", "Retries",
            "Period", "Cron")


def build():
    """The stub module, without installing it. Pure, so a test can inspect it."""
    _m = types.ModuleType("modal")
    for _n in _OBJECTS:
        setattr(_m, _n, _Any())
    for _n in _DECORATORS:
        setattr(_m, _n, lambda *a, **k: (lambda f: f))
    _m.is_local = lambda: True
    _m.enable_output = _Any()
    return _m


def install():
    """Install the stub unless a real `modal` is already present.

    setdefault, not assignment: a check running where the real package is
    importable should use it. Shadowing a real module would make these checks
    pass against a fiction.
    """
    return sys.modules.setdefault("modal", build())


if __name__ == "__main__":
    _m = build()
    _missing = [n for n in _OBJECTS + _DECORATORS + ("is_local", "enable_output")
                if not hasattr(_m, n)]
    # The decorators must actually decorate, not merely exist — a stub whose
    # decorator returns something uncallable fails at import in a way that reads
    # like a defect in the app.
    _bad = []
    for _n in _DECORATORS:
        try:
            if getattr(_m, _n)(method="POST")(lambda: 1)() != 1:
                _bad.append(_n)
        except Exception as _e:                               # noqa: BLE001
            _bad.append("%s (%s)" % (_n, type(_e).__name__))
    print("MODAL-STUB: %s — %d object(s), %d decorator(s)"
          % ("FAIL" if (_missing or _bad) else "PASS",
             len(_OBJECTS), len(_DECORATORS)))
    for _m2 in _missing:
        print("  - missing: " + _m2)
    for _b in _bad:
        print("  - does not decorate: " + _b)
    sys.exit(1 if (_missing or _bad) else 0)
