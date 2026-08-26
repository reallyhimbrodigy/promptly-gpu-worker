"""BLOCKED — DO NOT TRUST THIS FILE'S SILENCE (2026-08-25).

It does not run. Modal RE-IMPORTS this module inside the container to recover the
function body, so the decorator must evaluate to the SAME dependencies on both
sides. `modal_app.py` is the app DEFINITION and is deliberately not mounted into
the image, so it cannot be imported container-side to supply `image=` — and every
workaround fails a different way:

  try/except -> image=None container-side  ->  "Function has 1 dependencies but
                                                container got 6 object ids"
  ...then     -> container runs a DEFAULT image  ->  ModuleNotFoundError: handler
  mounting modal_app.py -> its own add_local_file() calls run container-side
                           against paths that do not exist there

Two hours of Modal spend would not change that. THE EVIDENCE IS BETTER ELSEWHERE
AND FREE: `midsentence_stall_s`, `render_offthread_threads` and
`render_concurrency` are now persisted on EVERY job, so the first real completed
job answers all of it — with a denominator, on real traffic, which is a stronger
proof than a synthetic container ever was (Rule 2). Read it with
`./run_modal.sh query_stall_arms_app.py`.

Kept, not deleted, because the next agent will otherwise rediscover the same
three dead ends. Fix it by adding a plain introspection function to modal_app.py
on the next deploy — one that returns these values from inside the real worker.

---- original intent below ----

VERIFY THE THREE ITEMS IN THE RUNNING IMAGE — not in the branch, not in the SHA.

Rule 0: read what is deployed by asking Modal, then verify FUNCTION PRESENCE IN
THE RUNNING IMAGE. A branch name and a commit hash both describe intent; only the
image describes what executes.

The reading that cannot be obtained locally is the DARK one. Modal mounts secrets
at CONTAINER START, so `_midsentence_stall_s()` resolves against the deployed
secret set — not my shell. A flag that is dark on my laptop and armed in
production is exactly the class this checks, and it is unfalsifiable from here.

  ./run_modal.sh cert_deployed_three_items_app.py     (~$0.005, one CPU container)
"""
import json

import modal

# modal_app.py is the app DEFINITION and is deliberately NOT mounted into the
# image (the image adds only specific add_local_file/dir paths). So this import
# succeeds LOCALLY and fails inside the container — where it is also unnecessary,
# because the image and secret set were resolved locally and baked into the
# function definition before it was ever sent.
# THE SECRET SET, DECLARED HERE ON BOTH SIDES. Modal re-imports this module
# INSIDE the container to recover the function body, and the decorator must
# evaluate to the SAME dependencies there as it did locally — a try/except that
# yields [] in the container and 5 secrets locally fails with "Function has 1
# dependencies but container got 6 object ids".
#
# modal_app.py is the app DEFINITION and is deliberately NOT mounted into the
# image, so it cannot be imported container-side to supply them.
#
# Mirrored from modal_app.py:674. THE FULL SET, INCLUDING promptly-lang-flags:
# a harness missing a secret measures a container that was never handed the
# flag and reports DARK for it — a vacuous probe presented as a verdict.
_SECRETS = [
    modal.Secret.from_name("promptly-secrets"),
    modal.Secret.from_name("promptly-cloudfront"),
    modal.Secret.from_name("gemini-vertex"),
    modal.Secret.from_name("promptly-lang-flags"),
    modal.Secret.from_name("promptly-elevenlabs"),
]

# The image is resolved LOCALLY only; the container is already running inside it.
try:
    import modal_app
    _IMAGE = modal_app.image
except ModuleNotFoundError:
    _IMAGE = None

app = modal.App("cert-deployed-three-items", image=_IMAGE)


@app.function(timeout=180, secrets=_SECRETS)
def verify() -> dict:
    import os
    import handler as H

    out = {}

    # ── (1) THE STALL EXPERIMENT IS PRESENT AND DARK ────────────────────────
    out["stall_accessor_present"] = hasattr(H, "_midsentence_stall_s")
    out["stall_constant"] = getattr(H, "_MIDSENTENCE_STALL_S", None)
    # THE VALUE IN FORCE IN THIS CONTAINER, with the real secrets mounted.
    out["stall_resolved_in_container"] = (
        H._midsentence_stall_s() if hasattr(H, "_midsentence_stall_s") else None)
    out["stall_env_set"] = os.environ.get("PROMPTLY_MIDSENTENCE_STALL_S", "") or None
    out["stall_is_dark"] = (out["stall_resolved_in_container"] == 0.70
                            and not out["stall_env_set"])
    out["three_counters_present"] = all(
        hasattr(H, n) for n in ("_DEAD_AIR_LOCATED", "_DEAD_AIR_OFFERED",
                                "_DEAD_AIR_PRESERVED"))

    # ── (2) ladder_exhausted IS PRESENT, AND LAST ───────────────────────────
    _rf = [s for s, _ in H._ERROR_SUBCODES.get("RENDER_FATAL", ())]
    out["render_fatal_subcodes"] = _rf
    out["ladder_exhausted_is_last"] = bool(_rf) and _rf[-1] == "ladder_exhausted"
    # Behavioural, on the two shapes that matter: a named mechanism must still
    # win through the ladder prefix, and a novel cause must stay visible.
    _named = ("RENDER_FATAL after full + retry + stripped renders: RuntimeError: "
              "Compositor error: No video stream found in input file z.mp4")
    _novel = ("RENDER_FATAL after full + retry + stripped renders: "
              "KeyError: 'somethingNobodyHasEverSeen'")
    out["named_mechanism_still_wins"] = (
        H.classify_error(RuntimeError(_named)).get("error_subcode") == "no_video_stream")
    out["novel_cause_stays_visible"] = (
        H.classify_error(RuntimeError(_novel)).get("error_subcode") == "ladder_exhausted:KeyError")
    out["unnamed_shape_still_unclassified"] = (
        H.classify_error(RuntimeError("totally novel junk")).get("error_subcode") == "unclassified")

    # ── (3) THE OFFTHREAD EVIDENCE PATH IS IN THE IMAGE ─────────────────────
    out["offthread_holder_present"] = hasattr(H, "_RENDER_OFFTHREAD")
    # The .mjs that will actually run, read from the image — not from my disk.
    try:
        _m = open("/remotion/render-full.mjs", encoding="utf-8").read()
        out["mjs_in_image"] = True
        out["mjs_sets_offthread"] = "offthreadVideoThreads:" in _m
        out["mjs_logs_offthread"] = "offthreadVideoThreads=" in _m
    except Exception as e:
        # UNMEASURED, stated as such. Never a False that reads as "absent".
        out["mjs_in_image"] = f"UNREADABLE: {type(e).__name__}"
        out["mjs_sets_offthread"] = None
        out["mjs_logs_offthread"] = None

    out["build_sha"] = (H._build_stamp() if hasattr(H, "_build_stamp") else None)
    return out


@app.local_entrypoint()
def main():
    r = verify.remote()
    print(json.dumps(r, indent=1))

    checks = {
        "(1) stall accessor in image": r.get("stall_accessor_present"),
        "(1) stall DARK in container (0.70, env unset)": r.get("stall_is_dark"),
        "(1) all three dead-air counters present": r.get("three_counters_present"),
        "(2) ladder_exhausted is LAST": r.get("ladder_exhausted_is_last"),
        "(2) named mechanism still wins": r.get("named_mechanism_still_wins"),
        "(2) novel cause stays visible": r.get("novel_cause_stays_visible"),
        "(2) unnamed shape still unclassified": r.get("unnamed_shape_still_unclassified"),
        "(3) offthread holder in image": r.get("offthread_holder_present"),
        "(3) .mjs sets the option": r.get("mjs_sets_offthread"),
        "(3) .mjs logs the value handler parses": r.get("mjs_logs_offthread"),
    }
    print()
    bad = 0
    for k, v in checks.items():
        print(f"  [{'PASS' if v is True else 'FAIL'}] {k}"
              + ("" if v is True else f" — got {v!r}"))
        bad += 0 if v is True else 1
    print(f"\n  stall resolved in container: {r.get('stall_resolved_in_container')} "
          f"(env={r.get('stall_env_set')})")
    print(f"  RENDER_FATAL subcode order: ...{(r.get('render_fatal_subcodes') or [])[-3:]}")
    print(f"\n  DEPLOYED-THREE-ITEMS: {'PASS' if not bad else f'FAIL ({bad})'}")
    if bad:
        raise SystemExit(1)
