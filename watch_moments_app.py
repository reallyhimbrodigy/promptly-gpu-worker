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
_LIMITS = {"on_screen": 14, "heard": 10, "cut_does": 12, "why_lands": 18,
           "instead_of": 16}
_WHERE = {"top", "upper", "center", "lower", "bottom", "full", "none"}
_PURPOSE = {"hook", "claim", "evidence", "turn", "payoff", "breath", "close"}
_KIND = {"placement", "restraint"}
_SYNC = {"before_the_word", "on_the_word", "after_the_word", "on_the_cut",
         "over_silence", "under_speech"}
# A SPAN IS THE CHANGE, NOT THE SCENE. A four-second "cut" produces a strip of
# six frames of someone talking — a picture of nothing, which is worse than one
# frame of the aftermath because it looks like evidence. Spans outside this are
# recorded as OVER-WIDE and fall back to the single settled frame rather than
# being silently trimmed to fit: trimming would invent a boundary the reader
# did not give.
_SPAN_MIN_S, _SPAN_MAX_S = 0.12, 2.5
_STRIP_FAMILIES = {"cut", "transition", "sfx"}


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
        # KIND IS REQUIRED AND NEVER DEFAULTED. An unlabelled moment folded
        # into "placement" would make the restraint density a measurement of
        # the default, which is the whole question this artefact was extended
        # to answer.
        _k = str(m.get("kind") or "").strip().lower()
        if _k not in _KIND:
            dropped.append({"i": i, "t": t,
                            "why": "kind is %r, not placement/restraint"
                                   % m.get("kind")})
            continue
        m["kind"] = _k
        # AN EMPTY FAMILY LIST IS A CORRECT ANSWER FOR A RESTRAINT MOMENT and
        # a defect for a placement: a placement that names no family has not
        # said what it placed.
        m["families"] = [str(x).strip().lower()
                         for x in (m.get("families") or []) if str(x).strip()]
        if _k == "placement" and not m["families"]:
            dropped.append({"i": i, "t": t,
                            "why": "a placement naming no family has not said "
                                   "what was placed"})
            continue
        # ── THE SPAN ────────────────────────────────────────────────────
        _a, _b = m.get("t_from_s"), m.get("t_to_s")
        m["span_state"] = "NONE"
        if _a is not None and _b is not None:
            try:
                _a, _b = float(_a), float(_b)
            except (TypeError, ValueError):
                m["span_state"] = "BAD (%r, %r are not numbers)" % (_a, _b)
                _a = _b = None
            if _a is not None:
                if not (0.0 <= _a < _b <= duration_s):
                    m["span_state"] = ("BAD (%.2f..%.2f outside [0, %.2f] or "
                                       "not ordered)" % (_a, _b, duration_s))
                elif (_b - _a) > _SPAN_MAX_S:
                    m["span_state"] = ("OVER-WIDE %.2fs > %.2fs — a span this "
                                       "long is a scene, not a change; falling "
                                       "back to the settled frame"
                                       % (_b - _a, _SPAN_MAX_S))
                elif (_b - _a) < _SPAN_MIN_S:
                    m["span_state"] = ("TOO NARROW %.3fs — fewer than two "
                                       "distinct frames" % (_b - _a))
                else:
                    m["t_from_s"], m["t_to_s"] = round(_a, 2), round(_b, 2)
                    m["span_state"] = "MEASURED %.2fs" % (_b - _a)
        if not m["span_state"].startswith("MEASURED"):
            m["t_from_s"] = m["t_to_s"] = None
        # A CHANGE-FAMILY MOMENT WITH NO SPAN IS RECORDED, NOT REFUSED. The
        # reader may be right that one frame shows it; what must not happen is
        # the omission being invisible, because then "no strips in this corpus"
        # and "the reader was never asked for spans" look identical.
        if (set(m["families"]) & _STRIP_FAMILIES) and not m["t_from_s"]:
            m["span_missing"] = ("families %s but no usable span (%s)"
                                 % (sorted(set(m["families"])
                                           & _STRIP_FAMILIES), m["span_state"]))

        # ── THE AUDIO ───────────────────────────────────────────────────
        _sl = m.get("sound_lands_s")
        if _sl is not None:
            try:
                _sl = float(_sl)
            except (TypeError, ValueError):
                _sl = None
            if _sl is None or not (0.0 <= _sl <= duration_s):
                m["sound_lands_s"] = None
                m["audio_state"] = ("DROPPED — sound_lands_s %r is not a time "
                                    "inside this clip" % m.get("sound_lands_s"))
            else:
                m["sound_lands_s"] = round(_sl, 2)
        _sy = str(m.get("sync") or "").strip().lower()
        m["sync"] = _sy if _sy in _SYNC else None
        if m.get("sound_lands_s") is not None and not m["sync"]:
            m["audio_state"] = ("PARTIAL — a sound with no `sync` says WHEN it "
                                "hits and not where it sits against the word, "
                                "which is the half an editor acts on")
        elif m.get("sound_lands_s") is not None:
            m["audio_state"] = "MEASURED"
        else:
            m["audio_state"] = "NO SOUND NAMED"
        if str(m.get("punctuates") or "").strip():
            _n = len(str(m["punctuates"]).split())
            if _n > 10:
                over.append({"i": i, "field": "punctuates", "words": _n,
                             "limit": 10})
        for k, lim in _LIMITS.items():
            n = len(str(m[k]).split())
            if n > lim:
                over.append({"i": i, "field": k, "words": n, "limit": lim})
        kept.append(m)
    rec["moments"] = sorted(kept, key=lambda x: x["t_settled_s"])
    rec["dropped"] = dropped
    rec["over_word_limit"] = over
    # THE DENSITY, RECORDED WHERE IT IS READ. A video that returned only
    # placements read exactly like a video with no restraint in it, and the
    # prompt asks for both — so the split is a STATE of this record, not
    # something a later script infers from the rows.
    rec["kinds"] = {_k: sum(1 for _m in kept if _m["kind"] == _k)
                    for _k in sorted(_KIND)}
    # THE SEQUENCE AND AUDIO DENSITIES, recorded where they are read. A corpus
    # with no strips and a reader that was never asked for spans produce the
    # same empty artefact.
    rec["spans"] = {
        "with_span": sum(1 for _m in kept if _m.get("t_from_s") is not None),
        "change_family_without_span": sum(1 for _m in kept
                                          if _m.get("span_missing")),
        "rejected": [_m["span_state"] for _m in kept
                     if _m["span_state"] not in ("NONE",)
                     and not _m["span_state"].startswith("MEASURED")][:6]}
    rec["audio"] = {
        "with_a_sound": sum(1 for _m in kept
                            if _m.get("sound_lands_s") is not None),
        "fully_described": sum(1 for _m in kept
                               if _m.get("audio_state") == "MEASURED"),
        "partial": sum(1 for _m in kept
                       if str(_m.get("audio_state") or "").startswith("PARTIAL"))}
    if not rec["kinds"].get("restraint"):
        rec["kinds"]["note"] = ("NO RESTRAINT MOMENT — either this video "
                                "genuinely places at every marked moment, or "
                                "the reader did not look for the empty ones. "
                                "Those are different and this record cannot "
                                "tell them apart.")
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
