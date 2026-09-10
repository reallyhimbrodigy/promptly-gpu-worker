# A MINIMAL IMAGE, AND THE REASONING THAT DIFFERS FROM THE EDITORIAL PATH.
#
# The first version borrowed `_prod.image` to make version drift structurally
# impossible — the same argument lumen_first_edit_app.py makes, and a good one
# THERE. It does not apply here, and the deploy proved it: the production image
# carries add_local_file entries for models/rife-v4.18/ which do not exist in a
# lane worktree, so the build failed before any work could run.
#
# The reasoning differs because the JOBS differ. The editorial path's output
# depends on the exact model and library versions, so drift changes the product.
# This job downloads one file and asks Gemini a question — it renders nothing,
# touches no component, and its only version-sensitive dependency is the MODEL
# NAME, which is pinned explicitly below to match the stored gemini_model field.
#
# So: a small pinned image with the three things it actually needs. Fewer
# moving parts than the production image, and no dependency on files that only
# exist in one checkout.

#!/usr/bin/env python3
"""RE-ANNOTATE THE TREND CORPUS WITH A CURRENT MODEL, ON THE ORIGINAL PROMPT.

WHY THIS EXISTS AND WHAT IT IS FOR. `trend_analyses` holds 19 of 103 videos,
annotated 2026-03-16 by gemini-2.5-pro. The other 84 have files and no
annotation. Re-reading ALL 103 with a current model gives:

  the 84   a fivefold corpus, before any scraping happens
  the 19   THE ONLY OVERLAP THAT WILL EVER EXIST — the same videos read by two
           models, which is the only way to measure how much of a rate is the
           footage and how much is the annotator

WHY THE PROMPT IS RECOVERED RATHER THAN REWRITTEN. The script in content-studio
today (`scripts/trend-video-pipeline.js`) asks for a FLAT schema — hook_type,
total_cuts, caption_style — and the stored rows are NESTED and quantitative.
IT DID NOT PRODUCE THEM. The real annotator is `scripts/trend-analyzer.js`,
DELETED from that repo and surviving only at commit f98981a: a 10,868-char
static EXTRACTION_PROMPT naming all twelve stored keys, pinning
GEMINI_MODEL = 'gemini-2.5-pro' — which matches the stored `gemini_model` field.

Using that exact text is what makes the comparison CONTROLLED. Rewriting the
prompt would vary prompt AND model together and the difference would be
attributed to the annotator — the two-variables-one-name shape this lane has hit
repeatedly. The prompt is mounted from `trend_extraction_prompt.txt`, byte for
byte, and this file must never paraphrase it.

WHAT CROSSES THE BOUNDARY. A SIGNED URL and the prompt text. Nothing else.
Supabase credentials stay on the caller's machine: the bucket is PRIVATE and
stays private (743 MB of scraped third-party video), the URL is short-lived and
scoped to one object, and no new secret enters the container. Vertex comes from
the LIVE `gemini-vertex` secret the editorial path already uses, so no key is
minted for a job the existing credential covers.

Returns a STATE, never a bare value: MEASURED / ABSENT / FAILED, so an analysis
that did not happen cannot read as an analysis that found nothing.
"""
import json
import os

import modal

app = modal.App("promptly-trend-analysis")

# THE PRODUCTION IMAGE, AND modal_app.py MOUNTED WITH IT.
#
# Importing modal_app to borrow the exact production image is what makes version
# drift impossible — but the import RUNS AGAIN IN THE CONTAINER, and modal_app.py
# is not in its own image's file list. Omitting the mount is why
# lumen_first_edit_app.py could not start for three weeks. Both sibling harnesses
# already do this; this one does it from the first commit.

# A MINIMAL IMAGE, AND WHY THE REASONING DIFFERS FROM THE EDITORIAL PATH.
#
# The first version borrowed `_prod.image` to make version drift structurally
# impossible — the argument lumen_first_edit_app.py makes, and a good one THERE.
# It does not apply here, and the deploy proved it: the production image carries
# add_local_file entries for models/rife-v4.18/ which do not exist in a lane
# worktree, so the build failed before any work could run.
#
# The reasoning differs because the JOBS differ. The editorial path's output
# depends on exact model and library versions, so drift changes the product.
# This job downloads one file and asks Gemini a question — it renders nothing,
# touches no component, and its only version-sensitive dependency is the MODEL
# NAME, pinned below to match the stored gemini_model field exactly.
image = (modal.Image.debian_slim(python_version="3.11")
         .apt_install("curl")
         .pip_install("google-genai", "google-auth")
         .add_local_file("trend_extraction_prompt.txt",
                         "/trend_extraction_prompt.txt"))

_MODEL = os.environ.get("PROMPTLY_TREND_MODEL", "gemini-2.5-pro")


@app.function(image=image, cpu=2, memory=8192, timeout=1800,
              secrets=[modal.Secret.from_name("promptly-secrets"),
                       modal.Secret.from_name("gemini-vertex")])
def analyse(signed_url: str, video_id: str, model: str = _MODEL) -> dict:
    """(state, analysis, detail) for ONE video. Pure w.r.t. the database."""
    import subprocess
    import tempfile
    import time

    t0 = time.time()

    def _out(state, analysis=None, detail=""):
        return {"video_id": video_id, "state": state, "analysis": analysis,
                "detail": detail, "model": model,
                "wall_s": round(time.time() - t0, 2)}

    # ── the prompt, from the mounted file, never from this source ───────────
    try:
        prompt = open("/trend_extraction_prompt.txt", encoding="utf-8").read()
    except Exception as e:                                        # noqa: BLE001
        return _out("FAILED", detail=f"prompt unreadable: {e}")
    if len(prompt) < 5000:
        # The recovered prompt is 10,868 chars. A short one means the mount is
        # wrong or truncated, and annotating on a truncated prompt would produce
        # plausible JSON against a different question.
        return _out("FAILED", detail=f"prompt is {len(prompt)} chars, expected "
                                     f"~10868 — the mount is wrong")

    # ── fetch the video via the signed URL ──────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    r = subprocess.run(["curl", "-sSL", "--max-time", "300", "-o", tmp.name,
                        signed_url], capture_output=True, text=True)
    size = os.path.getsize(tmp.name) if os.path.exists(tmp.name) else 0
    if r.returncode != 0 or size < 10000:
        return _out("FAILED", detail=f"download failed rc={r.returncode} "
                                     f"size={size}: {(r.stderr or '')[-160:]}")

    # ── Vertex, the same client shape handler.py uses ───────────────────────
    try:
        from google import genai as _genai
        from google.genai import types as _gt
        from google.oauth2 import service_account as _sa
        _sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        _proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not (_sa_json and _proj):
            # ABSENT, not a silent fallback to an API key. A missing credential
            # must page rather than quietly annotate through another route.
            return _out("ABSENT", detail="Vertex creds absent "
                                         "(GCP_SERVICE_ACCOUNT_JSON / "
                                         "GOOGLE_CLOUD_PROJECT) — refusing to "
                                         "fall back to an API key")
        _creds = _sa.Credentials.from_service_account_info(
            json.loads(_sa_json),
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        client = _genai.Client(
            vertexai=True, project=_proj,
            location=os.environ.get("GOOGLE_CLOUD_LOCATION") or "global",
            credentials=_creds,
            http_options=_gt.HttpOptions(timeout=480_000))
        resp = client.models.generate_content(
            model=model,
            contents=[_gt.Part.from_bytes(data=open(tmp.name, "rb").read(),
                                          mime_type="video/mp4"),
                      prompt])
        text = (resp.text or "").strip()
    except Exception as e:                                        # noqa: BLE001
        return _out("FAILED", detail=f"{type(e).__name__}: {str(e)[:240]}")
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:                                         # noqa: BLE001
            pass

    if not text:
        return _out("ABSENT", detail="the model returned no text")
    clean = text.replace("```json", "").replace("```", "").strip()
    try:
        analysis = json.loads(clean)
    except Exception as e:                                        # noqa: BLE001
        return _out("FAILED", detail=f"unparseable JSON: {e}; "
                                     f"raw[:200]={clean[:200]!r}")
    # THE SCHEMA MUST MATCH THE STORED ONE OR THE COMPARISON IS MEANINGLESS.
    _want = {"cuts", "hook", "audio", "broll", "speed", "ending", "transitions",
             "text_on_screen", "color_and_grade", "overall_production",
             "framing_and_movement", "video_duration_seconds"}
    _missing = sorted(_want - set(analysis))
    if _missing:
        return _out("FAILED", analysis=analysis,
                    detail=f"schema mismatch, missing {_missing} — this cannot "
                           f"be compared against the 2026-03-16 rows")
    return _out("MEASURED", analysis=analysis,
                detail=f"{len(_want)} keys, {size/1e6:.1f}MB")
