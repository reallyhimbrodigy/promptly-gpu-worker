"""FORCE the three open error classes on their OWN sources (Zac 2026-08-02).

Waiting for a user to hit these again cost a full day. Every source is still
reachable and every diagnostic is now live, so reproduce them deliberately:

  1. INTEGRITY_TRIP  — the black clip (source carries 7.97s of its own black).
                       The echo diagnostic (21d6567) prints
                         [echo: source=… map=… downgraded=N]
                       which names WHICH precondition of _ig_source_echo_black
                       failed. That line is the fix.
  2. 15fps           — one of the seven INVALID_FORMAT jobs. 83bf426 makes the
                       hype bridge signature-first, so the exception that was
                       truncated nine times lands in the first 300 chars.
  3. <Img>           — the RENDER_FATAL whose delayRender handles were stuck on
                       blob: URLs. SafeImg is deployed, so the render should
                       survive AND name what the blob is.

Runs handler IN-PROCESS exactly like watched_render_app: JOB_STATUS_WRITES_ENABLED=""
so no phantom video_jobs rows, APP_URL="" so no progress posts to prod. Container
is prod-matched (cpu=16, memory=64GiB) — the 128GiB in watched_render_app is
stale and would misprice the run.

Cost: $0.001027/s. Declared ceiling $2.00 for all three (MODAL_SPEND_LEDGER.md).
"""
import os
import sys

sys.path.insert(0, "/")   # modal_app is added to the image at /modal_app.py;
                          # without this the CONTAINER cannot import it at
                          # module load (watched_render_app does the same).
import modal
import modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-repro-three-classes", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("promptly-cloudfront"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]

CDN = "https://d1iax8jos987n3.cloudfront.net/sources"

# Each case carries the ORIGINAL vibe — the edit plan (and therefore the render
# shape) depends on it, so substituting a generic vibe would not reproduce.
CASES = {
    "integrity_black": {
        "src": f"{CDN}/85b6c8e0-f917-46ef-8e33-925440ea4a1c/"
               "1785692126492-4E3BABD2-28E4-445E-A81C-178A3A58FC6E_L0_001.mp4",
        "vibe": "Add dynamite captions and crop the video well and add effects",
        "want": "[echo:",
        "note": "job 0e794beb — 5 trips / 2 accounts / 1 source, 7.97s of source black",
    },
    "fps15_invalid_format": {
        "src": f"{CDN}/79f0bb16-09f6-4e3f-89e2-7282cd017a20/"
               "1785612670949-00BE0079-CC82-4E1E-B0D6-141BDD09FCCE_L0_001.mp4",
        "vibe": "Viral engaging video",
        "want": "Error",
        "note": "job 7a3e7ad5 — 15fps, PromptlyMicroSegments rc=1 at rendered=0",
    },
    "img_blob": {
        "src": f"{CDN}/2a200e51-2664-4ca7-8d30-cd9598bb8736/"
               "1785698327384-6D8F7B8A-4CE3-46F6-AACE-8429AF33B2FE_L0_001.mp4",
        "vibe": "Make this a smooth video, add zooms sound effects and motion graphic",
        "want": "SAFEIMG",
        "note": "job 1047def9 — delayRender stuck on blob: <Img> handles at frame 134",
    },
}


@app.function(secrets=SECRETS, cpu=16.0, memory=65536, region="us", timeout=1800)
def render_one(case: str, src: str, vibe: str) -> dict:
    """One reproduction render. Diagnostics go to the CONTAINER log, not a
    captured buffer — see the note below."""
    import time
    import traceback
    import uuid

    os.environ["APP_URL"] = ""                    # no progress posts to prod
    os.environ["JOB_STATUS_WRITES_ENABLED"] = ""  # no phantom video_jobs rows
    sys.path.insert(0, "/")
    import handler as H

    jid = str(uuid.uuid4())
    out = f"https://thisismybucketagainwooo.s3.amazonaws.com/repro/{jid}/render.mp4"
    body = {
        "job_id": jid, "video_url": src, "vibe": vibe,
        "user_id": "ec702499-ca10-49e6-8850-df8f99840904",
        "upload_url": out, "public_url": out,
        "model": "flare", "supports_progressive": False,
        "premium_pipeline_enabled": False,
    }
    # NO redirect_stdout (2026-08-02): the capture used to live in the RETURN
    # VALUE, so when the local `modal run` exited while the container ran on —
    # the .spawn()-outlives-the-orchestrator hazard in a new costume — the
    # captured diagnostic would have died with it. Case 1 only survived by
    # luck. Everything now goes to the container's own stdout, which Modal
    # retains independently of the local process.
    t0 = time.time()
    err = None
    res = None
    try:
        res = H.handler({"input": body})
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:1500]
        traceback.print_exc()
    log = ""   # stdout went straight to the container log — durable by design

    # The lines that answer each class, pulled out so the result is readable
    # without trawling a 200KB log.
    keep = []
    for line in log.splitlines():
        if any(m in line for m in (
            "[echo:", "[integrity-gate]", "[SAFEIMG]", "[safeimg]",
            "delayRender", "blob:", "Error:", "Exception",
            "[hype-render]", "render-full.mjs", "[render-degrade]",
            "[minimal-route]", "rc=1", "INVALID_FORMAT", "No video stream",
        )):
            keep.append(line[:400])
    return {
        "case": case, "job_id": jid, "elapsed_s": round(time.time() - t0, 1),
        "error": err,
        "result_error_code": (res or {}).get("error_code") if isinstance(res, dict) else None,
        "result_status": (res or {}).get("status") if isinstance(res, dict) else None,
        "salient_lines": keep[-60:],
        "log_tail": log[-3000:],
    }


@app.local_entrypoint()
def main(case: str = "integrity_black"):
    c = CASES.get(case)
    if not c:
        print(f"unknown case {case}; choose from {list(CASES)}")
        return
    if "PLACEHOLDER" in c["src"]:
        print(f"case {case} has a PLACEHOLDER source — fill it from the job row first")
        return
    print(f"=== {case}: {c['note']}")
    r = render_one.remote(case, c["src"], c["vibe"])
    print(f"\nelapsed={r['elapsed_s']}s  status={r['result_status']}  code={r['result_error_code']}")
    print(f"error={r['error']}")
    print(f"\n--- salient lines (looking for {c['want']!r}) ---")
    for line in r["salient_lines"]:
        print("  " + line)
    hit = any(c["want"] in ln for ln in r["salient_lines"])
    print(f"\n=== {c['want']!r} FOUND: {hit} ===")
