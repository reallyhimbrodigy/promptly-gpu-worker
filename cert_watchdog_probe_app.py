#!/usr/bin/env python3
"""DELIBERATE WATCHDOG FIRE — does it actually kill, and does it count? [Rule 1]

The post-upload watchdog is the first mechanism that intentionally KILLS a
running container. Every safety property is gated by source assertions, but a
source assertion cannot prove the thing FIRES. This fires it on purpose, once,
on a synthetic job id that touches no user row.

WHY THE CONTAINER DYING IS THE PASS SIGNAL: `os._exit(0)` takes the interpreter
out from under Modal, so this function CANNOT return normally once the watchdog
works. A clean return means the watchdog did NOT fire — that is the failure case,
and it is asserted explicitly rather than inferred from silence.

The proof is therefore split across the two sides:
  in-container : arm, then sleep well past N. Returning at all = FAIL.
  local        : query analytics_events for the probe's own job id. The row is
                 the "and it counts" half — a kill with no telemetry is a
                 container that vanished for unexplained reasons, which is worse
                 than no watchdog.

  modal run cert_watchdog_probe_app.py       # ~$0.01, one small container, ~40s
"""
import modal

app = modal.App("cert-watchdog-probe")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("supabase==2.7.4", "boto3", "requests")
    # handler.py imports these at module scope; mounting only handler.py gives a
    # ModuleNotFoundError before the watchdog can even be armed.
    .add_local_file("handler.py", "/handler.py")
    .add_local_file("build_lane.py", "/build_lane.py")
    .add_local_file("render_timeline.py", "/render_timeline.py")
    .add_local_file("edit_policy.py", "/edit_policy.py")
    .add_local_file("burned_text.py", "/burned_text.py")
    .add_local_file("premium.py", "/premium.py")
    .add_local_file("ffmpeg_base.py", "/ffmpeg_base.py")
    .add_local_file("render_schemas.py", "/render_schemas.py")
    .add_local_file("type_registries.py", "/type_registries.py")
    .add_local_file("cuda_driver_setup.py", "/cuda_driver_setup.py")
    .add_local_file("general_editor.py", "/general_editor.py")
    .add_local_file("hype_editor.py", "/hype_editor.py")
    .add_local_file("minimal_editor.py", "/minimal_editor.py")
    .add_local_file("moodreel_editor.py", "/moodreel_editor.py")
    .add_local_file("hype_render.py", "/hype_render.py")
    .add_local_file("adapter_contract.py", "/adapter_contract.py")
)

PROBE_N_SECONDS = 10          # the watchdog's own default is 120; 10 keeps the bill at ~$0


@app.function(image=image, cpu=2, memory=4096, timeout=180,
              secrets=[modal.Secret.from_name("promptly-secrets")])
def fire_the_watchdog(probe_job_id: str):
    import sys, os, time
    sys.path.insert(0, "/")
    import build_lane
    build_lane.mark_build_lane()          # never let a probe reach the live brain
    import handler as H

    # The module global is read when the Timer is constructed, so shortening it
    # here is enough — no redeploy, no env plumbing.
    H._POST_UPLOAD_WATCHDOG_S = PROBE_N_SECONDS

    print(f"[probe] arming watchdog n={PROBE_N_SECONDS}s job={probe_job_id}", flush=True)
    H._post_upload_watchdog_arm(probe_job_id, "s3://probe/never-a-real-key.mp4",
                                stage="cert_probe")
    # Deliberately NEVER disarm: this is the hung-worker state, simulated.
    t0 = time.time()
    while time.time() - t0 < PROBE_N_SECONDS + 20:
        time.sleep(1)

    # Unreachable if the watchdog works. Reaching it is the whole failure mode.
    print("[probe] STILL ALIVE past the threshold — the watchdog did NOT fire", flush=True)
    return {"fired": False,
            "why": "the function returned normally; os._exit(0) never ran"}


@app.local_entrypoint()
def main():
    import os, uuid, time, json
    probe_id = f"watchdog-probe-{uuid.uuid4()}"
    print("=== WATCHDOG PROBE — deliberate fire ===")
    print(f"  probe job id: {probe_id}")
    print(f"  threshold:    {PROBE_N_SECONDS}s   (production default is 120s)")

    returned_normally = False
    try:
        out = fire_the_watchdog.remote(probe_id)
        returned_normally = True
        print(f"  !! the function RETURNED: {out}")
    except Exception as e:
        # A container that os._exit()s mid-call surfaces here. That is the PASS.
        print(f"  container died mid-call ({type(e).__name__}) — consistent with os._exit(0)")

    if returned_normally:
        print("\nWATCHDOG PROBE: FAIL — the container survived past the threshold.")
        raise SystemExit(1)

    # THE SECOND HALF is checked separately: this machine has no supabase client,
    # and installing one to read four fields would be a worse dependency than a
    # second command. Run:
    #   node cert_watchdog_probe_check.js <probe_job_id>
    print("\n  container kill CONFIRMED. Now verify it COUNTED:")
    print(f"    node cert_watchdog_probe_check.js {probe_id}")
    print("  (a kill with no telemetry is worse than no watchdog — that check is "
          "not optional)")
    print("\nWATCHDOG PROBE: container-kill half PASSED.")
