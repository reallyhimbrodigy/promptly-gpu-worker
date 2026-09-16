#!/usr/bin/env python3
"""THE WATCHED ARTEFACT — Gemini watches all ten WITH AUDIO, moment by moment.

Zac, 2026-09-15: "Gemini watches all ten with audio. Per moment: the frame,
what's on screen, what's heard, what the cut does, why it lands. Compressed to
something readable at a glance, cached in the prefix, with the frames
themselves beside it."

WHAT THIS IS NOT. It is not `craft_pass_app.py`. That pass produced PROSE about
the ten — 16_craft_the_standard.md, 2,520 tokens of well-written paragraphs
that the ruling turn receives verbatim and that come out as generic copy. This
pass produces MOMENTS: a timestamp a frame can be grabbed from, and four short
fields beside it. The difference is that a moment can be looked at.

TWO PASSES, AND THE SECOND ONE IS THE GATE.

  1. `watch`   — the clip (video+audio) in, moments out.
  2. `verify`  — the TILED SHEET back in, with the lines, asking of each
                 numbered tile: does this frame show what its line says?

Pass 2 exists because Gemini's timestamps drift (this repo has a whole finding
on it: word timings unusable as a cut clock). A drifting timestamp does not
produce an error, it produces a frame of the wrong shot sitting under a
confident caption — a picture that teaches the opposite of what the line says.
Nothing reaches the prefix that pass 2 has not confirmed shows what it claims.

VIDEO SAMPLE RATE IS PINNED, same reason as reference_listen_app.py: without
VideoMetadata, Gemini samples video at 1fps against continuous audio, and a
300ms graphic entrance becomes audible and invisible.
"""
import os

import modal

app = modal.App("promptly-watch-moments")

image = (modal.Image.debian_slim(python_version="3.11")
         .pip_install("google-genai", "google-auth")
         .add_local_file("watch_moments_prompt.txt",
                         "/watch_moments_prompt.txt")
         .add_local_file("watch_verify_prompt.txt",
                         "/watch_verify_prompt.txt"))

_MODEL = os.environ.get("PROMPTLY_WATCH_MODEL", "gemini-2.5-pro")

# The word limits the prompt states. Enforced here as a RECORDED STATE, never a
# silent truncation: a field cut mid-sentence reads as a complete thought that
# happens to be wrong, which is worse than a long one.
_LIMITS = {"on_screen": 14, "heard": 10, "cut_does": 12, "why_lands": 18}
_WHERE = {"top", "upper", "center", "lower", "bottom", "full", "none"}
_PURPOSE = {"hook", "claim", "evidence", "turn", "payoff", "breath", "close"}


def _client():
    """Vertex or nothing. An API-key fallback would change the arm silently."""
    import json

    from google import genai as _genai
    from google.genai import types as _gt
    from google.oauth2 import service_account as _sa
    _sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    _proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not (_sa_json and _proj):
        return None, _gt, "Vertex creds absent — refusing an API-key fallback"
    creds = _sa.Credentials.from_service_account_info(
        json.loads(_sa_json),
        scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return (_genai.Client(vertexai=True, project=_proj,
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION")
                          or "global",
                          credentials=creds,
                          http_options=_gt.HttpOptions(timeout=900_000)),
            _gt, "")


def _reply_json(resp, tok):
    """(record, failure_detail). The whole response is the evidence."""
    import json
    import re
    txt = getattr(resp, "text", "") or ""
    if not txt:
        _c = getattr(resp, "candidates", None) or []
        _f = getattr(_c[0], "finish_reason", None) if _c else None
        return None, ("empty .text with out=%s finish_reason=%s — the reply "
                      "went somewhere other than .text" % (tok["out"], _f))
    m = re.search(r"\{[\s\S]*\}", txt)
    if not m:
        return None, "no JSON in %d chars of reply: %r" % (len(txt), txt[:240])
    try:
        return json.loads(m.group(0)), ""
    except json.JSONDecodeError as e:
        if tok["out"] >= 32000:
            return None, ("OUTPUT CAP HIT out=%s — TRUNCATED, not malformed; "
                          "tail: %r" % (tok["out"], txt[-240:]))
        return None, "JSON parse: %s; first 240: %r" % (e, txt[:240])


@app.function(image=image, cpu=2, memory=8192, timeout=1800,
              secrets=[modal.Secret.from_name("promptly-secrets"),
                       modal.Secret.from_name("gemini-vertex")])
def watch(video_bytes: bytes, label: str, duration_s: float,
          model: str = _MODEL, sample_fps: float = 5.0) -> dict:
    """One video watched with audio. Returns a STATE, never a guess."""
    import time

    t0 = time.time()

    def out(state, record=None, detail="", **kw):
        d = {"label": label, "state": state, "record": record or {},
             "detail": detail, "model": model, "sample_fps": sample_fps,
             "heard_audio": True, "duration_s": duration_s,
             "wall_s": round(time.time() - t0, 1)}
        d.update(kw)
        return d

    if not video_bytes:
        return out("FAILED", detail="no bytes supplied")
    try:
        prompt = open("/watch_moments_prompt.txt", encoding="utf-8").read()
    except Exception as e:                                        # noqa: BLE001
        return out("FAILED", detail="prompt absent from image: %s" % e)

    client, _gt, why = _client()
    if client is None:
        return out("ABSENT", detail=why)
    if not hasattr(_gt, "VideoMetadata"):
        return out("FAILED", detail="VideoMetadata absent from the installed "
                                    "google-genai — the visual rate cannot be "
                                    "pinned")
    try:
        _vpart = _gt.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
        _vpart.video_metadata = _gt.VideoMetadata(fps=float(sample_fps))
        resp = client.models.generate_content(
            model=model,
            contents=[_vpart, prompt + "\n\nThis clip is %.2f seconds long. "
                                       "Every t_settled_s must fall inside it."
                                       % duration_s],
            config=_gt.GenerateContentConfig(temperature=0.2,
                                             max_output_tokens=32000))
    except Exception as e:                                        # noqa: BLE001
        return out("FAILED", detail="%s: %s" % (type(e).__name__, str(e)[:300]))

    usage = getattr(resp, "usage_metadata", None)
    tok = {"in": getattr(usage, "prompt_token_count", 0) or 0,
           "out": getattr(usage, "candidates_token_count", 0) or 0}
    rec, why = _reply_json(resp, tok)
    if rec is None:
        return out("FAILED", detail=why, tokens=tok)

    # ── VALIDATION: every drop is NAMED ─────────────────────────────────────
    kept, dropped, over = [], [], []
    for i, m in enumerate(rec.get("moments") or []):
        if not isinstance(m, dict):
            dropped.append({"i": i, "why": "not an object"})
            continue
        try:
            t = float(m.get("t_settled_s"))
        except (TypeError, ValueError):
            dropped.append({"i": i, "why": "t_settled_s is %r, not a number"
                                           % m.get("t_settled_s")})
            continue
        if not (0.0 <= t <= duration_s):
            dropped.append({"i": i, "why": "t_settled_s %.2f outside [0, %.2f]"
                                           % (t, duration_s)})
            continue
        miss = [k for k in _LIMITS if not str(m.get(k) or "").strip()]
        if miss:
            dropped.append({"i": i, "t": t, "why": "empty: %s" % ",".join(miss)})
            continue
        m["t_settled_s"] = round(t, 2)
        w = str(m.get("where") or "").strip().lower()
        m["where"] = w if w in _WHERE else "none"
        p = str(m.get("purpose") or "").strip().lower()
        m["purpose"] = p if p in _PURPOSE else "evidence"
        m["families"] = [str(x).strip().lower()
                         for x in (m.get("families") or []) if str(x).strip()]
        for k, lim in _LIMITS.items():
            n = len(str(m[k]).split())
            if n > lim:
                over.append({"i": i, "field": k, "words": n, "limit": lim})
        kept.append(m)
    rec["moments"] = sorted(kept, key=lambda x: x["t_settled_s"])
    rec["dropped"] = dropped
    rec["over_word_limit"] = over
    rec["provenance"] = {"source_file": label, "duration_s": duration_s,
                         "analyzer_model": model, "fps": sample_fps,
                         "heard_audio": True}
    if not kept:
        return out("ABSENT", record=rec, detail="parsed but no usable moments "
                                                "(%d dropped)" % len(dropped),
                   tokens=tok)
    return out("MEASURED", record=rec, tokens=tok)


@app.function(image=image, cpu=2, memory=4096, timeout=1200,
              secrets=[modal.Secret.from_name("promptly-secrets"),
                       modal.Secret.from_name("gemini-vertex")])
def verify(sheet_png: bytes, lines: list, model: str = _MODEL) -> dict:
    """THE GATE. Does tile N show what line N says?

    `lines` is [{"n": 1, "on_screen": "...", "where": "...", "t": 3.4}, ...] in
    tile order. Returns a verdict per tile. Anything that is not an explicit
    YES is treated by the caller as not-shown — ABSENT and FAILED do not pass.
    """
    import time

    t0 = time.time()

    def out(state, verdicts=None, detail="", **kw):
        d = {"state": state, "verdicts": verdicts or [], "detail": detail,
             "model": model, "wall_s": round(time.time() - t0, 1)}
        d.update(kw)
        return d

    if not sheet_png or not lines:
        return out("FAILED", detail="no sheet (%d bytes) or no lines (%d)"
                                    % (len(sheet_png or b""), len(lines or [])))
    try:
        prompt = open("/watch_verify_prompt.txt", encoding="utf-8").read()
    except Exception as e:                                        # noqa: BLE001
        return out("FAILED", detail="verify prompt absent from image: %s" % e)

    client, _gt, why = _client()
    if client is None:
        return out("ABSENT", detail=why)
    import json
    # A 429 IS NOT A VERDICT. The gate treats anything that is not an explicit
    # `yes` as not-shown, which is right — and it means a transient rate limit
    # silently costs real moments their frames. So the rate limit is RETRIED,
    # with backoff, and only a persistent one becomes FAILED. Every other error
    # fails on the first try: retrying a malformed request just spends money
    # slowly.
    resp, _last = None, ""
    for _try in range(5):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[_gt.Part.from_bytes(data=sheet_png,
                                              mime_type="image/png"),
                          prompt + "\n\nTHE LINES:\n"
                          + json.dumps(lines, indent=1)],
                config=_gt.GenerateContentConfig(temperature=0.0,
                                                 max_output_tokens=8000))
            break
        except Exception as e:                                    # noqa: BLE001
            _last = "%s: %s" % (type(e).__name__, str(e)[:300])
            if "429" not in str(e) and "RESOURCE_EXHAUSTED" not in str(e):
                return out("FAILED", detail=_last)
            time.sleep(30 * (_try + 1) * (_try + 1))
    if resp is None:
        return out("FAILED", detail="rate limited on 5 attempts: %s" % _last)

    usage = getattr(resp, "usage_metadata", None)
    tok = {"in": getattr(usage, "prompt_token_count", 0) or 0,
           "out": getattr(usage, "candidates_token_count", 0) or 0}
    rec, why = _reply_json(resp, tok)
    if rec is None:
        return out("FAILED", detail=why, tokens=tok)
    v = rec.get("verdicts") or []
    if len(v) != len(lines):
        return out("FAILED", tokens=tok,
                   detail="asked about %d tiles, got %d verdicts — a partial "
                          "answer cannot be read as a pass for the rest"
                          % (len(lines), len(v)))
    return out("MEASURED", verdicts=v, tokens=tok)
