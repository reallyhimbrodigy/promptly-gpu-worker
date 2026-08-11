"""Read back the ACTUAL values injected from the promptly-lang-flags Modal Secret.

Standalone ephemeral Modal app — does NOT import modal_app/handler. `modal run` only.
Two uses:
  1. Ops: `modal run secret_flags_readback.py` — prints the live secret values so a
     human/agent can verify them without guessing.
  2. Deploy gate: validate_deploy.py shells out to this and asserts the values are
     canonical (SPAWN_MODE=1 etc.), so a future "preserve the current value" sweep
     that sets a WRONG value is caught at the gate instead of shipping.

Prints one machine-parseable line:  READBACK {"PROMPTLY_SPAWN_MODE": "1", ...}

ENUMERATES, NEVER ASSUMES (2026-08-11, RULE-1). This used to return a hardcoded
26-key list while the live secret held 31. `modal secret create --force`
REPLACES the whole secret — any key not restated is DROPPED — so a one-value
flip driven off this readback would have silently deleted PROMPTLY_HLS_COPY,
PROMPTLY_MEDIA_RESOLUTION, PROMPTLY_PROXY_SAMPLE_FPS,
PROMPTLY_SILENT_TO_MOODREEL and PROMPTLY_STRUCTURE_ABORT: five live flags gone,
each reverting to its absent-default, with nothing in any gate to say so.
The container now reports EVERY PROMPTLY_* key the secret actually injects, so
the readback cannot lag the secret again. FLAG_KEYS survives only as a
minimum-presence floor: a key that vanishes from the live secret is a loud
failure here, not a quiet default. secret_flip.py builds its restate from this
enumeration, never from a hand-typed list.
"""
import modal
import os
import json

app = modal.App("promptly-secret-readback")
image = modal.Image.debian_slim()

# The operational flags that live in the secret (order/keys only — the
# canonical VALUES are asserted by validate_deploy.py, the single enforcement point).
FLAG_KEYS = [
    "PROMPTLY_SPAWN_MODE",
    "PROMPTLY_OUTCOME_GATE",
    "PROMPTLY_LEVER3",
    "PROMPTLY_EDIT_IN_LANGUAGE",
    "PROMPTLY_SCRIPT_DENYLIST",
    "PROMPTLY_PLAN_CAPTURE",
    "PROMPTLY_BURNED_TEXT",
    "PROMPTLY_ZERO_REJECT",
    "PROMPTLY_WHY_DIET",
    "PROMPTLY_DELIVERY_FPS",
    "PROMPTLY_RENDER_FANOUT",
    "PROMPTLY_HYPE_MODE",
    "PROMPTLY_SHAPE_ABORT",
    "PROMPTLY_MOODREEL",
    "PROMPTLY_HQ_RESAMPLE",
    "PROMPTLY_BROLL_GATE",
    "PROMPTLY_COVERAGE_GATE",
    "PROMPTLY_LANG_ROUTING",
    "PROMPTLY_ROUTE_LANGS",
    "PROMPTLY_MOTION_BLUR",
    "PROMPTLY_MIN_OUTPUT_RATIO",
    "PROMPTLY_CAPTION_ALIGN",
    "PROMPTLY_SMOOTH_GRAPHICS",
    "PROMPTLY_ASR_SCRIBE",
    "PROMPTLY_POST_THINKING_BUDGET",
    "PROMPTLY_RENDER_BURST",
]


@app.function(image=image, secrets=[modal.Secret.from_name("promptly-lang-flags")])
def read_flags():
    # Runs INSIDE a container with the secret injected → os.environ has the real
    # values. Enumerate what the secret ACTUALLY injects (debian_slim sets no
    # PROMPTLY_* of its own, so every such key here came from the secret), then
    # union the declared floor so a DISAPPEARED key reads "<UNSET>" loudly
    # instead of just being missing from the dict.
    live = {k: v for k, v in os.environ.items() if k.startswith("PROMPTLY_")}
    for k in FLAG_KEYS:
        live.setdefault(k, "<UNSET>")
    return dict(sorted(live.items()))


@app.local_entrypoint()
def main():
    vals = read_flags.remote()
    print("READBACK " + json.dumps(vals))
