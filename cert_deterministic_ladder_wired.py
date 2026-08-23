#!/usr/bin/env python3
"""cert_deterministic_ladder_wired.py — THE LADDER MUST BE CALLED, AND CANARYABLE.

MEASURED 2026-08-18 (sweep_built_not_wired.py, verbatim): "duration_target and
mechanical_router were built, cert-green, committed and DEPLOYED, with no
import, no mount and no call site anywhere in production." Both certs stayed
green the entire time, because both drive their module in ISOLATION with
injected fakes. Delete the call site and they still pass — which is exactly what
happened, for weeks.

cert_mounted_is_reachable.py (check 427) closes the mount half. This closes the
CALL half: a module can be mounted and imported and still never invoked.

  1  BOTH helpers are invoked from generate_plan_diff — the live re-edit path.
  2  BOTH pass input_data, so the per-job canary works. Without it the only way
     to arm either is the secret plus a redeploy, on features whose mis-fire
     produces a WRONG EDIT with no model in the loop. surgical_ops passes it;
     these two did not, and nothing noticed.
  3  duration_target receives source_duration_s. Deriving the denominator from
     the last word's end time makes trailing silence invisible — a 40s video
     whose speech ends at 28s answered "already shorter than 30s", to the user.
  4  mechanical_router receives the transcript, because the caption-swap
     validation now runs BEFORE the mechanical return. Its own docstring used
     to claim validation happened "downstream"; it did not — that path returns
     first.
  5  aspect_ratio is NOT in the mechanical vocabulary. It is a dead field
     (handler.py: "the pipeline always outputs 1080x1920 regardless"), and
     routing it emitted a set-op that cannot change a pixel plus a user-facing
     "aspect=1:1 — everything else untouched."

    python3 cert_deterministic_ladder_wired.py
"""
import os
import re
import sys

os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    fails = []
    raw = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
    src = "\n".join(re.sub(r"#.*$", "", ln) for ln in raw.splitlines())
    router = "\n".join(re.sub(r"#.*$", "", ln) for ln in
                       open(os.path.join(HERE, "mechanical_router.py"),
                            encoding="utf-8").read().splitlines())

    # ── 1 + 2: called, with the canary ─────────────────────────────────────
    mr = re.search(r"_det = _mechanical_reedit\(([^)]*)\)", src, re.S)
    dt = re.search(r"_det = _duration_reedit\(([^)]*)\)", src, re.S)
    print(f"  [1] _mechanical_reedit called: {bool(mr)}   "
          f"_duration_reedit called: {bool(dt)}")
    for m, name in ((mr, "_mechanical_reedit"), (dt, "_duration_reedit")):
        if not m:
            fails.append(f"{name} has NO call site in generate_plan_diff — the "
                         f"module is built, mounted, cert-green and dead, which "
                         f"is the exact state the sweep found on 2026-08-18")
            continue
        args = m.group(1)
        if "input_data" not in args:
            fails.append(f"{name} is called WITHOUT input_data — the per-job "
                         f"canary cannot fire, so the only way to arm a feature "
                         f"whose mis-fire writes a wrong edit is a secret plus a "
                         f"redeploy")
    if mr:
        print(f"  [2] mechanical args: {mr.group(1).strip()[:90]}")
    if dt:
        print(f"  [2] duration args  : {dt.group(1).strip()[:90]}")

    # ── 3: the honest denominator ──────────────────────────────────────────
    if dt and "source_duration_s" not in dt.group(1):
        fails.append("_duration_reedit is called without source_duration_s — it "
                     "falls back to the last word's end time, so trailing "
                     "silence is invisible and 'make it 30s' answers about a "
                     "video the user never saw")
    print(f"  [3] duration gets source_duration_s: "
          f"{bool(dt and 'source_duration_s' in dt.group(1))}")

    # ── 4: validation ahead of the return ──────────────────────────────────
    got_tr = bool(mr and "transcript" in mr.group(1))
    validates = bool(re.search(r"validate_caption_overrides", src[:src.find("_record_divergence(\n        \"reedit\"")] if "_record_divergence(\n        \"reedit\"" in src else src))
    print(f"  [4] router gets transcript: {got_tr}   validates before return: "
          f"{'validate_caption_overrides' in src}")
    if not got_tr:
        fails.append("_mechanical_reedit is called without the transcript, so a "
                     "caption swap naming text that was never spoken cannot be "
                     "checked — it no-ops silently at render and the user is "
                     "told it worked")

    # ── 5: aspect is not routable ──────────────────────────────────────────
    in_vocab = bool(re.search(r'MECHANICAL_SCALARS = \([^)]*"aspect_ratio"', router, re.S))
    print(f"  [5] aspect_ratio in the mechanical vocabulary: {in_vocab} "
          f"(must be False)")
    if in_vocab:
        fails.append("aspect_ratio is back in MECHANICAL_SCALARS — it is a DEAD "
                     "FIELD (the pipeline always outputs 1080x1920), so routing "
                     "it returns a confident success for a change that cannot "
                     "happen")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT DETERMINISTIC-LADDER-WIRED: FAIL")
        return 1
    print("  CERT DETERMINISTIC-LADDER-WIRED: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
