#!/usr/bin/env python3
"""EVERY KEY HANDLER STAMPS ONTO A RENDER-INPUT DICT MUST BE DECLARED. `[Rule 1]`

MEASURED 2026-08-17: handler.py:30889 stamps `_page["emphasis"]` whenever a
design-system accent exists. `render_schemas.TikTokPage` is `extra="forbid"` and
never declared it, so EVERY emphasised caption page failed render-input
validation with `extra_forbidden`. The degrade ladder tried full -> retry ->
stripped, every rung carried the SAME caption pages, and it exhausted "with no
input-differing rung". 135 RENDER_FATALs across 44 users.

The rate tracked the DESIGN-SYSTEM ATTACH RATE (1, 5, 5, 30, 54 per hour), not
any deploy boundary — which is why every deploy-correlation hypothesis failed to
fit it, and why it looked like a mystery for a day.

THIS IS THE THIRD TIME. `motionTokens` was silently blocked by the same
extra="forbid" mirror. `source_duration_s`, `cpu_by_stage` and `gemini_tokens`
were each stripped by content-studio's top-level filter and had to be re-nested.
The shape is always identical: a producer adds a key, the consumer's schema does
not know it, and the failure surfaces far from the edit.

WHAT THIS CHECKS: for each render-input model that forbids extras, every key
handler.py assigns into the corresponding dict must be a declared field. It reads
the ASSIGNMENTS out of handler's source rather than a hand-kept list, because a
hand-kept list is the stale-list defect one file over.

    python3 cert_render_input_mirror.py
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# (the dict handler builds, the model that validates it, how handler names it)
TARGETS = [
    ("caption page", "TikTokPage", r'_page\["(\w+)"\]\s*='),
]


def main():
    sys.path.insert(0, HERE)
    import render_schemas as R

    src = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
    # comments are DOCUMENTATION — a key named in prose is not a key assigned.
    code = re.sub(r"#[^\n]*", "", src)

    failures = []
    for label, model_name, pattern in TARGETS:
        model = getattr(R, model_name, None)
        if model is None:
            failures.append(f"{model_name} is gone from render_schemas")
            continue
        forbids = (getattr(model, "model_config", {}) or {}).get("extra") == "forbid"
        declared = set(model.model_fields)
        stamped = set(re.findall(pattern, code))
        print(f"  {label} -> {model_name}  extra=forbid:{forbids}")
        print(f"     declared({len(declared)}): {sorted(declared)}")
        print(f"     stamped ({len(stamped)}): {sorted(stamped)}")
        if not forbids:
            continue
        missing = stamped - declared
        if missing:
            failures.append(
                f"handler stamps {sorted(missing)} onto the {label} dict, but "
                f"{model_name} is extra='forbid' and does not declare them — every "
                f"render input carrying one FAILS validation and the degrade ladder "
                f"cannot strip it (all rungs share the same pages)")

    print()
    if failures:
        print(f"RENDER-INPUT MIRROR: {len(failures)} FAILED")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RENDER-INPUT MIRROR: ALL PASS (every key handler stamps onto a "
          "render-input dict is declared on the forbidding model)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
