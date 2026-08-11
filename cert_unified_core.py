"""cert_unified_core.py — Rule-1 gate for the unified editorial core
(LANE-SEAM Step 2). Pure-local, stdlib-only, $0 — no Modal, no network.

What regression each check makes impossible:
  1. PREMIUM-IDENTITY — the "full" route stack composes to the SAME base
     object (premium_full is the empty profile). If anyone puts text in
     premium_full or reroutes "full", unified-core-ON stops being
     byte-identical on the main route and this fails BEFORE traffic does.
  2. CACHE-PREFIX  — every route stack composes to text that starts with the
     unchanged base (the 42K cached prefix survives profile variation; the
     2.1x-cost relocation class is unwritable).
  3. CONTRADICTION — hype_pacing + moodreel_aesthetic pin the spine axis two
     ways and MUST raise GuidanceContradiction at compose time (build-time
     RED, never a prompt the model arbitrates).
  4. NO-TOOL-STRIPPING — GuidanceProfile structurally has no field that could
     express tool availability. A field named tools/allow/deny/exclude
     appearing on the dataclass is the fork growing back; hard fail.
  5. CONSERVATISM  — unknown routes select the full-core default, never a
     stripped stack, never an exception; unknown profile NAMES raise loudly.
  6. DETERMINISM   — a stack composes to the same bytes regardless of caller
     order (registry order wins → per-route cache stability).
  7. DARK-OFF      — enabled() defaults False; per-job override works.
  8. WIRING        — generate_edit_gemini carries guidance_profiles, the
     compose call exists after the prompt builder, the call site selects
     under the flag, and modal_app mounts both modules.

Run: python3 cert_unified_core.py   (exit 0 = PASS)
"""

import dataclasses
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_checks = []


def check(name):
    def deco(fn):
        _checks.append((name, fn))
        return fn
    return deco


@check("premium-identity: 'full' stack composes to the same base object")
def _premium_identity():
    import unified_core as uc
    base = "=== BASE DOCTRINE ===\neverything"
    stack = uc.select_stack("full")
    assert stack == ["premium_full"], "main-route stack drifted: %r" % stack
    composed = uc.compose_system_instruction(base, stack)
    assert composed is base, (
        "premium_full no longer composes to the identical base object — "
        "unified-core-ON is no longer byte-identical on the main route")
    assert uc.compose_system_instruction(base, None) is base
    assert uc.compose_system_instruction(base, []) is base


@check("cache-prefix: every route stack keeps base as unchanged prefix")
def _cache_prefix():
    import guidance_registry as gr
    import unified_core as uc
    base = "=== BASE DOCTRINE ===\nthe full toolbox lives here\n"
    for route in ("full", "premium", "__premium__", "hype", "moodreel",
                  "minimal", "minimal_speech_uncut", "never-heard-of-it"):
        stack = uc.select_stack(route)
        composed = uc.compose_system_instruction(base, stack)
        assert composed.startswith(base), \
            "route %r composed text does not start with base" % route
        for name in stack:
            g = gr.PROFILES[name].guidance
            if g:
                assert g in composed, \
                    "route %r lost profile %r text" % (route, name)


@check("contradiction: hype + moodreel stack is a build-time RED")
def _contradiction():
    import guidance_registry as gr
    try:
        gr.compose_suffix(["hype_pacing", "moodreel_aesthetic"])
    except gr.GuidanceContradiction:
        pass
    else:
        raise AssertionError(
            "hype_pacing+moodreel_aesthetic composed without raising — the "
            "contradiction law is dead")
    # a compatible stack must NOT raise
    gr.compose_suffix(["minimal_restraint", "speech_preservation"])


@check("no-tool-stripping: GuidanceProfile cannot express tool availability")
def _no_tools():
    import guidance_registry as gr
    fields = {f.name for f in dataclasses.fields(gr.GuidanceProfile)}
    assert fields == {"name", "kind", "guidance", "axes"}, (
        "GuidanceProfile grew fields %r — if any of these can express a tool "
        "allowlist/denylist, the fork is growing back; extend this cert only "
        "with a field that provably cannot remove capability"
        % sorted(fields - {"name", "kind", "guidance", "axes"}))
    banned = ("tool", "allow", "deny", "exclude", "disable", "strip")
    for f in fields:
        for b in banned:
            assert b not in f.lower(), "field %r smells like tool-gating" % f


@check("conservatism: unknown route → full core; unknown profile name raises")
def _conservatism():
    import guidance_registry as gr
    assert gr.profiles_for_route("mystery_route") == [gr.DEFAULT_PROFILE]
    assert gr.profiles_for_route(None) == [gr.DEFAULT_PROFILE]
    assert gr.profiles_for_route("") == [gr.DEFAULT_PROFILE]
    try:
        gr.compose_suffix(["hype_pacing_TYPO"])
    except KeyError:
        pass
    else:
        raise AssertionError("unknown profile name silently accepted")


@check("determinism: caller order never changes composed bytes")
def _determinism():
    import guidance_registry as gr
    a = gr.compose_suffix(["minimal_restraint", "speech_preservation"])
    b = gr.compose_suffix(["speech_preservation", "minimal_restraint"])
    assert a == b and a, "stack composition depends on caller order"


@check("dark-off: enabled() defaults False; per-job override works")
def _dark():
    import unified_core as uc
    saved = os.environ.pop("PROMPTLY_UNIFIED_CORE", None)
    try:
        assert uc.enabled() is False
        assert uc.enabled({}) is False
        assert uc.enabled({"unified_core_test": True}) is True
        os.environ["PROMPTLY_UNIFIED_CORE"] = "1"
        assert uc.enabled({}) is True
    finally:
        if saved is None:
            os.environ.pop("PROMPTLY_UNIFIED_CORE", None)
        else:
            os.environ["PROMPTLY_UNIFIED_CORE"] = saved


@check("wiring: kwarg + compose call + call-site selection + mounts")
def _wiring():
    with open(os.path.join(HERE, "handler.py")) as f:
        h = f.read()
    with open(os.path.join(HERE, "modal_app.py")) as f:
        m = f.read()
    for needle, why in (
        ("guidance_profiles=None,", "generate_edit_gemini kwarg"),
        ("post_sys = _ucore.compose_system_instruction(post_sys, "
         "guidance_profiles)", "compose after the prompt builder"),
        ("import unified_core as _uc", "call-site unconditional import"),
        ("_uc.enabled(input_data)", "flag check at the call site"),
        ('_seam_profiles = _uc.select_stack("full")', "main-route selection"),
        ("guidance_profiles=_seam_profiles,", "call passes the stack"),
        ('_ledger_defect("missing_module", "unified_core"',
         "loud missing-mount ledger"),
    ):
        assert needle in h, "handler.py lost: %s (%s)" % (needle, why)
    for mod in ("guidance_registry.py", "unified_core.py"):
        assert 'add_local_file("%s", "/%s")' % (mod, mod) in m, \
            "modal_app.py mount for %s missing" % mod


def main():
    failed = 0
    for name, fn in _checks:
        try:
            fn()
            print("PASS  %s" % name)
        except Exception as e:
            failed += 1
            print("FAIL  %s — %s: %s" % (name, type(e).__name__, e))
    print("cert_unified_core: %d/%d PASS" % (len(_checks) - failed, len(_checks)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
