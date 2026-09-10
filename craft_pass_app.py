#!/usr/bin/env python3
"""WATCH ONE VIDEO PROPERLY AND EXPLAIN HOW IT WAS EDITED.

Not counting. Not rating. A moment-by-moment account of what the editor did and
why it lands, in an editor's own terms.

WHY THIS AND NOT THE RATES. The trend corpus was annotated for COUNTS — cuts,
text elements, sfx — and the counts turned out to be 36-1600% self-inconsistent
between two readings of the same footage by the same model family. Counting is
the thing a model does badly here. Explaining WHY A CUT LANDS is a different
task, and the existing hook_structure rows in reference_videos show the model
does that one well: "a credibility hook rather than a question-based curiosity
gap" is craft, and it was produced by the same kind of pass.

THE OUTPUT IS PROSE, DELIBERATELY. A schema would pull this back toward
counting — the moment there is a `cuts: []` field, the model fills it with
timestamps and stops explaining. The prompt asks for reasons attached to
moments, and a bare timestamp is called worthless in it.

TWO WEIGHTS, NEVER BLENDED. Zac's ten examples are confirmed
beautifully-edited videos and are the standard. The Apify hundred are other
people's work, useful as breadth and marked as such, so the synthesis can say
"his examples do X, the wider field does Y" rather than averaging a taste he did
not choose.
"""
import os

import modal

app = modal.App("promptly-craft-pass")

image = (modal.Image.debian_slim(python_version="3.11")
         .apt_install("curl")
         .pip_install("google-genai", "google-auth")
         .add_local_file("craft_pass_prompt.txt", "/craft_pass_prompt.txt")
         .add_local_file("craft_synthesis_prompt.txt",
                         "/craft_synthesis_prompt.txt"))

_MODEL = os.environ.get("PROMPTLY_CRAFT_MODEL", "gemini-2.5-pro")


@app.function(image=image, cpu=2, memory=8192, timeout=1800,
              secrets=[modal.Secret.from_name("promptly-secrets"),
                       modal.Secret.from_name("gemini-vertex")])
def analyse(video_bytes: bytes, label: str, weight: str,
            model: str = _MODEL, url: str = "") -> dict:
    """(state, prose, detail).

    TWO WAYS IN, because the two corpora live in different places. Zac's ten
    references are on a laptop and have no signed URL, so they arrive as
    BYTES. The Apify hundred are in a private Supabase bucket, so a signed URL
    arrives instead and the CONTAINER fetches — the bytes never touch the
    laptop's uplink, and the service-role key never enters this image."""
    import json
    import time

    t0 = time.time()

    def out(state, prose=None, detail=""):
        return {"label": label, "weight": weight, "state": state,
                "prose": prose, "detail": detail, "model": model,
                "wall_s": round(time.time() - t0, 1)}

    if url and not video_bytes:
        # A DOWNLOAD THAT RETURNED SOMETHING THAT IS NOT A VIDEO must not be
        # handed to the model as if it were one: an expired signed URL returns
        # a 400 JSON body, and the model would dutifully "analyse" it.
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                ctype = (r.headers.get("Content-Type") or "").lower()
                video_bytes = r.read()
        except Exception as e:                                    # noqa: BLE001
            return out("FAILED", detail=f"fetch: {type(e).__name__}: "
                                        f"{str(e)[:160]}")
        if len(video_bytes) < 100_000:
            return out("FAILED", detail=f"fetched only {len(video_bytes)} "
                                        f"bytes ({ctype}) — not a video")
        if "video" not in ctype and "octet-stream" not in ctype:
            return out("FAILED", detail=f"fetched Content-Type {ctype!r} — "
                                        f"not a video")
    if not video_bytes:
        return out("FAILED", detail="neither bytes nor a url were supplied")

    try:
        prompt = open("/craft_pass_prompt.txt", encoding="utf-8").read()
    except Exception as e:                                        # noqa: BLE001
        return out("FAILED", detail=f"prompt unreadable: {e}")
    if len(prompt) < 1500:
        return out("FAILED", detail=f"prompt is {len(prompt)} chars — the mount "
                                    f"is wrong and this would answer a "
                                    f"different question")
    try:
        from google import genai as _genai
        from google.genai import types as _gt
        from google.oauth2 import service_account as _sa
        _sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        _proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not (_sa_json and _proj):
            return out("ABSENT", detail="Vertex creds absent — refusing to fall "
                                        "back to an API key")
        creds = _sa.Credentials.from_service_account_info(
            json.loads(_sa_json),
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        client = _genai.Client(
            vertexai=True, project=_proj,
            location=os.environ.get("GOOGLE_CLOUD_LOCATION") or "global",
            credentials=creds,
            http_options=_gt.HttpOptions(timeout=900_000))
        contents = [_gt.Part.from_bytes(data=video_bytes,
                                        mime_type="video/mp4"), prompt]
        text, waited = "", 0.0
        for attempt in range(4):
            try:
                resp = client.models.generate_content(model=model,
                                                      contents=contents)
                text = (resp.text or "").strip()
                break
            except Exception as e:                                # noqa: BLE001
                # ONLY quota. Anything else is a real error and must surface
                # on the first occurrence — a retry over a defect hides it.
                msg = str(e)
                if "RESOURCE_EXHAUSTED" not in msg and "429" not in msg:
                    raise
                if attempt == 3:
                    return out("FAILED", detail=f"quota after 4 attempts "
                                                f"({waited:.0f}s waited): "
                                                f"{msg[:160]}")
                nap = (attempt + 1) * 25.0
                waited += nap
                time.sleep(nap)
    except Exception as e:                                        # noqa: BLE001
        return out("FAILED", detail=f"{type(e).__name__}: {str(e)[:240]}")

    if not text:
        return out("ABSENT", detail="the model returned no text")
    # A PASS THAT PRODUCED A TIMESTAMP LIST IS A FAILED PASS, not a short one.
    # The whole point is reasons; bare timestamps mean the prompt lost.
    import re
    stamps = len(re.findall(r"\b\d+[:.]\d+s?\b", text))
    words = len(text.split())
    if words < 200:
        return out("FAILED", prose=text,
                   detail=f"only {words} words — too thin to be a moment-by-"
                          f"moment account")
    return out("MEASURED", prose=text,
               detail=f"{words} words, {stamps} timestamps "
                      f"({stamps / max(words, 1) * 100:.1f}% density)")


# A RATE IN THE CACHED PREFIX IS THE REGRESSION THIS WHOLE PASS EXISTS TO AVOID.
# The reference rates GRADE; they never instruct (standing rule, 2026-09-08).
# One survived a careful removal last time as prose — "the WORKHORSE (~7.5 per
# 25s)" — because a sentence that DESCRIBES a rate reads as harmless beside a
# schema field that DEMANDS one. So this is not a review note: it FAILS the
# synthesis, and the report never reaches the prefix.
_RATE_PATTERNS = [
    r"\b\d+(?:\.\d+)?\s*(?:\w+\s+)?per\s+(?:\d+\s*)?(?:s\b|secs?\b|seconds?\b|min\b|minutes?\b|video\b|clip\b)",
    r"\bon average\b",
    r"\baverages?\s+(?:about\s+|around\s+|~)?\d",
    r"\b\d+(?:\.\d+)?\s*%",
    r"\bdensit(?:y|ies)\b",
    r"\bper-(?:minute|second)\b",
    r"\bevery\s+\d+(?:\.\d+)?\s*(?:-|\s)?\s*(?:to\s+\d+(?:\.\d+)?\s*)?seconds?\b",
]


def strip_preamble(text: str):
    """A sentence about the task is not editorial understanding, and this
    report is read on every render forever. The prompt asks for none; the
    model writes one anyway. So it is removed MECHANICALLY rather than by
    re-rolling the call — and only when the thing being removed is provably a
    preamble: a short run of prose before the first header, near the top.
    Returns (text, what_was_removed) so the removal is never silent."""
    lines = text.split("\n")
    for i, ln in enumerate(lines[:6]):
        if ln.lstrip().startswith("#"):
            head = "\n".join(lines[:i]).strip().strip("*").strip()
            if not head:
                return text, ""
            if len(head) > 300:      # that is content, not a preamble
                return text, ""
            return "\n".join(lines[i:]).lstrip(), head
    return text, ""


def rate_language(text: str) -> list:
    """Every place the report tried to instruct with a NUMBER instead of a
    CONDITION. Returns the offending snippets, with enough either side to
    judge them by."""
    import re as _re
    hits = []
    for pat in _RATE_PATTERNS:
        for m in _re.finditer(pat, text, _re.I):
            a, b = max(0, m.start() - 60), min(len(text), m.end() + 60)
            hits.append("..." + text[a:b].replace("\n", " ") + "...")
    return hits


@app.function(image=image, cpu=2, memory=8192, timeout=3600,
              secrets=[modal.Secret.from_name("promptly-secrets"),
                       modal.Secret.from_name("gemini-vertex")])
def synthesise(analyses: list, model: str = _MODEL) -> dict:
    """ONE report from all the per-video analyses.

    `analyses` is a list of {label, weight, prose}. The weights are kept
    SEPARATE in the assembled input and named in the prompt — the two corpora
    are never averaged into one claim."""
    import json
    import time

    t0 = time.time()

    def out(state, prose=None, detail="", **kw):
        d = {"state": state, "prose": prose, "detail": detail, "model": model,
             "wall_s": round(time.time() - t0, 1)}
        d.update(kw)
        return d

    try:
        prompt = open("/craft_synthesis_prompt.txt", encoding="utf-8").read()
    except Exception as e:                                        # noqa: BLE001
        return out("FAILED", detail=f"synthesis prompt unreadable: {e}")
    if len(prompt) < 3000:
        return out("FAILED", detail=f"synthesis prompt is {len(prompt)} chars "
                                    f"— the mount is wrong")

    ref = [a for a in analyses if a.get("weight") == "zac_reference"]
    field = [a for a in analyses if a.get("weight") != "zac_reference"]
    if not ref:
        return out("ABSENT", detail="no zac_reference analyses — the standard "
                                    "is missing and the field alone is not a "
                                    "taste he chose")

    def block(items, header):
        parts = [header]
        for i, a in enumerate(items, 1):
            parts.append(f"\n----- {i}. {a.get('label','?')} -----\n"
                         f"{a.get('prose','')}")
        return "\n".join(parts)

    body = block(ref, "=" * 78 + "\nZAC'S REFERENCES — THE STANDARD "
                                 f"({len(ref)} videos)\n" + "=" * 78)
    if field:
        body += "\n\n" + block(
            field, "=" * 78 + "\nTHE WIDER FIELD — OTHER PEOPLE'S WORK "
                              f"({len(field)} videos)\n" + "=" * 78)

    try:
        from google import genai as _genai
        from google.genai import types as _gt
        from google.oauth2 import service_account as _sa
        _sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        _proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not (_sa_json and _proj):
            return out("ABSENT", detail="Vertex creds absent")
        creds = _sa.Credentials.from_service_account_info(
            json.loads(_sa_json),
            scopes=["https://www.googleapis.com/auth/cloud-platform"])
        client = _genai.Client(
            vertexai=True, project=_proj,
            location=os.environ.get("GOOGLE_CLOUD_LOCATION") or "global",
            credentials=creds,
            http_options=_gt.HttpOptions(timeout=1800_000))
        resp = client.models.generate_content(
            model=model, contents=[prompt + "\n\n" + body])
        text = (resp.text or "").strip()
    except Exception as e:                                        # noqa: BLE001
        return out("FAILED", detail=f"{type(e).__name__}: {str(e)[:240]}")

    if not text:
        return out("ABSENT", detail="the model returned no text")

    text, preamble = strip_preamble(text)
    words = len(text.split())
    rates = rate_language(text)
    counts = {"n_reference": len(ref), "n_field": len(field), "words": words,
              "preamble_stripped": preamble}
    if rates:
        return out("RATES_PRESENT", prose=text, rate_hits=rates, **counts,
                   detail=f"{len(rates)} rate(s) in a report bound for the "
                          f"cached prefix — REFUSED")
    # A field corpus that vanished into an average is the other failure.
    if field and "wider field" not in text.lower():
        return out("BLENDED", prose=text, **counts,
                   detail="the field corpus was read but never named — it was "
                          "blended into the standard")
    if words < 600:
        return out("FAILED", prose=text, **counts,
                   detail=f"{words} words is not a combined understanding of "
                          f"{len(ref) + len(field)} videos")
    return out("MEASURED", prose=text, rate_hits=[], **counts,
               detail=f"{words} words from {len(ref)} references"
                      + (f" + {len(field)} field videos" if field else "")
                      + ", 0 rates")
