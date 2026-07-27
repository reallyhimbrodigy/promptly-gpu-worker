"""Read back the ACTUAL values injected from the promptly-lang-flags Modal Secret.

Standalone ephemeral Modal app — does NOT import modal_app/handler. `modal run` only.
Two uses:
  1. Ops: `modal run secret_flags_readback.py` — prints the live secret values so a
     human/agent can verify them without guessing.
  2. Deploy gate: validate_deploy.py shells out to this and asserts the values are
     canonical (SPAWN_MODE=1 etc.), so a future "preserve the current value" sweep
     that sets a WRONG value is caught at the gate instead of shipping.

Prints one machine-parseable line:  READBACK {"PROMPTLY_SPAWN_MODE": "1", ...}
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
]


@app.function(image=image, secrets=[modal.Secret.from_name("promptly-lang-flags")])
def read_flags():
    # Runs INSIDE a container with the secret injected → os.environ has the real values.
    return {k: os.environ.get(k, "<UNSET>") for k in FLAG_KEYS}


@app.local_entrypoint()
def main():
    vals = read_flags.remote()
    print("READBACK " + json.dumps(vals))
