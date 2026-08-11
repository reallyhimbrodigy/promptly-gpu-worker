"""unified_core.py — ONE editorial core, guidance-profiled (LANE-SEAM Step 2).

The seam that retires the route fork: the editorial system instruction becomes
BASE (the full toolbox doctrine — today's monolith, byte-for-byte, so the
~42K-token cached prefix survives) + ADDITIVE GUIDANCE PROFILES appended after
it (guidance_registry). The router selects WHICH PROFILES LOAD — never which
tools are allowed; the full toolbox is in the base always.

DARK: PROMPTLY_UNIFIED_CORE (env) / input_data.unified_core_test (per-job).
Flag OFF  → generate_edit_gemini receives guidance_profiles=None and composes
            nothing — byte-identical to today.
Flag ON   → the main (talking-head/premium) route selects the `premium_full`
            profile, which is the EMPTY additive block — so ON is byte-identical
            there TOO, by construction (certified). Lean routes only switch to
            composed prompts after their profile is proven GREEN through the
            HARNESS differ on the golden corpus (PLAN_ONLY, ≤$10 budget);
            until then their fork is untouched.

Cache-prefix law (measured 2.1x cost precedent): compose() ASSERTS the base is
an unchanged prefix of the composed text — relocation is structurally
impossible, not just discouraged.

Python 3.9-compatible.
"""

import os

import guidance_registry as _gr

__all__ = ["enabled", "select_stack", "compose_system_instruction"]


def enabled(input_data=None):
    """DARK by default. PROMPTLY_UNIFIED_CORE=1 arms profile selection
    globally; input_data.unified_core_test is the per-job override for the
    pre-flip cert (burned_text_test pattern — inert for real traffic)."""
    if input_data and input_data.get("unified_core_test"):
        return True
    return os.environ.get("PROMPTLY_UNIFIED_CORE", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def select_stack(route_name):
    """Deterministic route → profile-name stack (guidance_registry's router).
    Conservatism law: unknown/uncertain → the full-core default, never a
    stripped prompt, never an exception."""
    return _gr.profiles_for_route(route_name)


def compose_system_instruction(base_sys, profile_names):
    """BASE + additive profile suffix. The ONLY way profile text reaches a
    prompt. Guarantees, in order:
      1. contradiction law — a stack pinning one axis two ways raises
         GuidanceContradiction before any model call (build-time RED);
      2. cache-prefix law — the returned text ALWAYS startswith(base_sys),
         asserted, so the cached base block can never be relocated/fragmented
         by a profile;
      3. empty stacks / empty profiles compose to base_sys UNCHANGED (same
         object), which is what makes premium_full flag-ON byte-identical.
    """
    suffix = _gr.compose_suffix(profile_names or [])
    if not suffix:
        return base_sys
    composed = base_sys + suffix
    # Structural, not advisory: a future edit that prepends/injects rather
    # than appends dies here, not in the Vertex bill.
    assert composed.startswith(base_sys), "cache-prefix law violated"
    return composed
