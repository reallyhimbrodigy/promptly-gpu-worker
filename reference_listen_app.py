#!/usr/bin/env python3
"""The reference index pass, WITH AUDIO. Send the clip, not frames.

Zac, 2026-09-11: "give the index pass audio. Same treatment as the craft pass:
send the clip, not frames. An open vocabulary on a deaf reader can still only
discover visual families."

WHAT WAS WRONG. Every reading of this corpus — including the open-vocabulary one
that found 23 families — was made from silent JPEG frames plus a transcript.
build_reference_records.py extracts stills with ffmpeg and posts them as base64
images. The reader could not hear a sound effect however many there were, and
the corpus reported `sfx 0.82/25s from 14 beats` anyway. That number, like
`transition: 0 of 153`, was a fact about the instrument.

THE CONFOUND, STATED. Claude cannot take video, so hearing the clip means
changing the MODEL as well as the modality: claude-sonnet-5 over frames becomes
gemini over video+audio. Those move together and nothing here can separate them.
Any family that appears in this pass and not the silent one is attributable to
"a different reader that can also hear", not to hearing alone. The one thing it
does settle is the direction the silent pass could never reach: a family that is
audible-only was structurally unsayable before, so its appearance is not a
close call.

SAME SCHEMA, ONE ADDITION. reference_listen_prompt.txt is the frames annotator's
open-vocabulary schema verbatim plus an audio section — so the passes differ in
what the reader can perceive, not in what it is asked for.

VIDEO SAMPLE RATE IS PINNED. Without VideoMetadata, Gemini samples video at 1fps
while audio arrives continuously — two resolutions from one file, which is
exactly how a 300ms dissolve becomes audible and invisible. Pinned to 5 to match
the silent arm's frame rate.
"""
import os

import modal

app = modal.App("promptly-reference-listen")

image = (modal.Image.debian_slim(python_version="3.11")
         .pip_install("google-genai", "google-auth")
         .add_local_file("reference_listen_prompt.txt",
                         "/reference_listen_prompt.txt"))

_MODEL = os.environ.get("PROMPTLY_REF_MODEL", "gemini-2.5-pro")


@app.function(image=image, cpu=2, memory=8192, timeout=1800,
              secrets=[modal.Secret.from_name("promptly-secrets"),
                       modal.Secret.from_name("gemini-vertex")])
def listen(video_bytes: bytes, label: str, duration_s: float,
           mechanical_cuts: list, transcript: str = "",
           model: str = _MODEL, sample_fps: float = 5.0) -> dict:
    """One reference record read from the CLIP. Returns a STATE, never a guess."""
    import json
    import re
    import time

    t0 = time.time()

    def out(state, record=None, detail="", **kw):
        d = {"label": label, "state": state, "record": record or {},
             "detail": detail, "model": model, "sample_fps": sample_fps,
             "heard_audio": True, "wall_s": round(time.time() - t0, 1)}
        d.update(kw)
        return d

    if not video_bytes:
        return out("FAILED", detail="no bytes supplied")
    try:
        prompt = open("/reference_listen_prompt.txt", encoding="utf-8").read()
    except Exception as e:                                        # noqa: BLE001
        return out("FAILED", detail=f"prompt absent from image: {e}")

    try:
        from google import genai as _genai
        from google.genai import types as _gt
        from google.oauth2 import service_account as _sa
        _sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        _proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not (_sa_json and _proj):
            return out("ABSENT", detail="Vertex creds absent — refusing to "
                                        "fall back to an API key")
        creds = _sa.Credentials.from_service_account_info(
            json.loads(_sa_json),
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        client = _genai.Client(
            vertexai=True, project=_proj,
            location=os.environ.get("GOOGLE_CLOUD_LOCATION") or "global",
            credentials=creds,
            http_options=_gt.HttpOptions(timeout=900_000))

        _vpart = _gt.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
        # NAMED, NOT DEFAULTED. Absent VideoMetadata means 1fps video against a
        # continuous audio track, and a rate comparison against the silent arm
        # would then be comparing two different visual samplings as well.
        if not hasattr(_gt, "VideoMetadata"):
            return out("FAILED", detail="VideoMetadata absent from the "
                                        "installed google-genai — the visual "
                                        "rate cannot be pinned and the arm "
                                        "would not match the silent one")
        try:
            _vpart.video_metadata = _gt.VideoMetadata(fps=float(sample_fps))
        except Exception as e:                                    # noqa: BLE001
            return out("FAILED", detail=f"VideoMetadata(fps={sample_fps}) "
                                        f"refused: {type(e).__name__} "
                                        f"{str(e)[:120]}")

        ctx = json.dumps({"duration_s": duration_s,
                          "mechanical_cut_timestamps_s": mechanical_cuts,
                          "transcript": (transcript or "")[:6000]}, indent=1)
        resp = client.models.generate_content(
            model=model,
            contents=[_vpart, prompt + "\n\nCONTEXT:\n" + ctx],
            config=_gt.GenerateContentConfig(
                temperature=0.2, max_output_tokens=32000))
    except Exception as e:                                        # noqa: BLE001
        return out("FAILED", detail=f"{type(e).__name__}: {str(e)[:300]}")

    txt = getattr(resp, "text", "") or ""
    usage = getattr(resp, "usage_metadata", None)
    tok = {"in": getattr(usage, "prompt_token_count", 0) or 0,
           "out": getattr(usage, "candidates_token_count", 0) or 0}
    if not txt:
        # THE WHOLE RESPONSE IS THE EVIDENCE. An empty `.text` with tokens
        # spent means the reply was somewhere else — a finish_reason, a safety
        # block, a thinking-only turn. Returning "no text" without saying which
        # is the probe-collapse class.
        _cands = getattr(resp, "candidates", None) or []
        _fin = getattr(_cands[0], "finish_reason", None) if _cands else None
        return out("FAILED",
                   detail="empty .text with out=%s finish_reason=%s — the "
                          "reply went somewhere other than .text; naming which "
                          "is the difference between a diagnosis and a mystery"
                          % (tok["out"], _fin),
                   tokens=tok)
    m = re.search(r"\{[\s\S]*\}", txt)
    if not m:
        return out("FAILED", detail=f"no JSON in {len(txt)} chars of reply",
                   raw=txt[:4000], tokens=tok)
    try:
        rec = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        if tok["out"] >= 32000:
            return out("FAILED", detail=f"OUTPUT CAP HIT out={tok['out']} — "
                                        f"TRUNCATED, not malformed",
                       raw=txt[-3000:], tokens=tok)
        return out("FAILED", detail=f"JSON parse: {e}", raw=txt[:4000],
                   tokens=tok)

    # ANYTHING NAMED MUST SAY WHAT IT DOES — enforced here too, identically.
    ungrounded = []
    for b in rec.get("beats") or []:
        keep = []
        for t in (b.get("treatment") or []):
            if not isinstance(t, dict):
                ungrounded.append({"beat": b.get("beat_index"),
                                   "name": str(t)[:60], "why": "not an object"})
                continue
            nm = str(t.get("name") or "").strip()
            wd = str(t.get("what_it_does") or "").strip()
            if not nm:
                ungrounded.append({"beat": b.get("beat_index"),
                                   "name": "(none)", "why": "unnamed"})
            elif not wd:
                ungrounded.append({"beat": b.get("beat_index"), "name": nm,
                                   "why": "no what_it_does"})
            else:
                # KEEP THE WHOLE OBJECT — SECOND COPY OF THE SAME BUG.
                # build_reference_records.py had this identical line and it
                # deleted every field the annotator answered beyond the two
                # being validated. I fixed that copy and not this one, so the
                # listening arm returned 253 placements with all six placement
                # fields answered and stored NONE of them.
                #
                # Two copies of one rule is how a rule ends up enforced on one
                # of them — the lesson this file has already paid for twice
                # (half_ruling_refusal, the verdict surfaces). A validator that
                # RECONSTRUCTS its input instead of annotating it throws away
                # everything it was not looking for, and doing it in two places
                # means fixing it in two places.
                t2 = dict(t)
                t2["name"], t2["what_it_does"] = nm, wd
                keep.append(t2)
        b["treatment"] = keep
    rec["ungrounded_dropped"] = ungrounded
    rec["provenance"] = {"source_file": label, "duration_s": duration_s,
                         "analyzer_model": model, "fps": sample_fps,
                         "heard_audio": True,
                         "mechanical_cuts": mechanical_cuts}
    if not (rec.get("beats") or []):
        return out("ABSENT", record=rec, detail="parsed but no beats",
                   tokens=tok)
    return out("MEASURED", record=rec, tokens=tok)
