"""A RENDER failure must never be classified as a bad user file.

WHY THIS EXISTS (2026-08-02)
----------------------------
Seven jobs across NINE users died in the render — `render-full.mjs
PromptlyMicroSegments failed rc=1`, at `progress 0% rendered=0`, with
fps_normalize having already run cleanly (15fps -> 30fps in 0.5-0.7s). Their
stderr contained the substring "No video stream found", and classify_error
matched it to:

    INVALID_FORMAT
    "We couldn't read your video file. Please make sure it's a standard
     video format (MP4, MOV, or similar)."
    retryable=False, requires_new_video=True

So we told nine people their file was unreadable, gave them no retry, and asked
them to shoot again — for a render that failed on our side. `retryable=False` +
`requires_new_video=True` is a DEAD END: the user cannot recover, and the class
looks like an input problem in every count, which is why it sat unexamined since
07-30.

THE RULE THIS PINS
------------------
`INVALID_FORMAT` / `WRONG_ORIENTATION` and friends are INTAKE verdicts about the
user's file. Once we are inside the renderer, a failure is OURS, whatever
substring its stderr happens to contain. The renderer's own output is not
evidence about the upload.

This is independent of the underlying render defect: even after the render is
fixed, a render failure must never be dressed up as a bad upload.
"""
import sys

import handler as H

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


# The real prod message, verbatim in shape (job e421415f and six siblings).
RENDER_STAGE = (
    "[hype-render] render-full.mjs PromptlyMicroSegments failed rc=1\n"
    "STDOUT:\n"
    "[render-full] composition=PromptlyMicroSegments (ProRes 4444 no-alpha) "
    "frames 0-7, 1 segments, concurrency=8\n"
    "[render-full] Browser opened in 1.50s\n"
    "[render-full] progress 0% rendered=0\n"
    "STDERR:\n"
    "No video stream found"
)

print("=== U0: the exact prod shape must NOT blame the user's file ===")
env = H.classify_error(RuntimeError(RENDER_STAGE))
check("does NOT classify as INVALID_FORMAT",
      env.get("error_code") != "INVALID_FORMAT", env.get("error_code"))
check("classifies as a RENDER class",
      str(env.get("error_code") or "").startswith("RENDER"), env.get("error_code"))
check("is RETRYABLE (a render failure is not a dead end)",
      env.get("retryable") is True, str(env))
check("does NOT demand a new video",
      env.get("requires_new_video") is not True, str(env))
check("copy does not tell the user their file is unreadable",
      "couldn't read your video file" not in str(env.get("user_message") or "").lower(),
      str(env.get("user_message"))[:120])

print("\n=== U1: every render-stage marker is covered, not just this one ===")
for marker in (
    "[hype-render] render-full.mjs PromptlyOverlay failed rc=1 ... No video stream found",
    "[micro-02] Remotion render failed (rc=1): No video stream found",
    "[overlay-00] Remotion render TIMEOUT after 600.0s (budget 600s) — No video stream found",
    "render-full.mjs PromptlyMicroSegments failed rc=1\nNo video stream found",
):
    _e = H.classify_error(RuntimeError(marker))
    check(f"render-stage marker not blamed on the file: {marker[:44]}…",
          _e.get("error_code") != "INVALID_FORMAT", _e.get("error_code"))

print("\n=== U2: GENUINE intake problems still classify as INVALID_FORMAT ===")
# No render marker anywhere — these are real probe/intake verdicts and MUST
# keep telling the user to re-export. Over-correcting here would hide a real
# bad-file class behind a retry loop.
for intake in (
    "No video stream found",
    "ffprobe: No video stream found in source",
    "Gemini proxy encode failed",
):
    _e = H.classify_error(RuntimeError(intake))
    check(f"intake verdict preserved: {intake[:40]}…",
          _e.get("error_code") == "INVALID_FORMAT", _e.get("error_code"))
_e = H.classify_error(RuntimeError("No video stream found"))
check("intake INVALID_FORMAT still asks for a new video",
      _e.get("requires_new_video") is True, str(_e))

print("\n=== U3: other intake verdicts unaffected ===")
for msg, code in (
    ("Landscape video detected", "WRONG_ORIENTATION"),
    ("CLIP_TOO_SHORT: source is 1.2s", "CLIP_TOO_SHORT"),
    ("NO_SPEECH: 0 words", "NO_SPEECH"),
):
    _e = H.classify_error(RuntimeError(msg))
    check(f"{code} unchanged", _e.get("error_code") == code, _e.get("error_code"))

print("\n=== U4: existing render classes unchanged ===")
for msg, code in (
    ("RENDER_FATAL after full + retry + stripped renders: boom", "RENDER_FATAL"),
    ("INTEGRITY_TRIP: black=[[1.0, 2.0]]", "INTEGRITY_TRIP"),
    ("[composite] ffmpeg failed rc=1", "RENDER_FFMPEG"),
):
    _e = H.classify_error(RuntimeError(msg))
    check(f"{code} unchanged", _e.get("error_code") == code, _e.get("error_code"))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print(f"  FAILED: {f}")
sys.exit(1 if FAIL else 0)
