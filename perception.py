"""PERCEPTION SIGNALS FOR TURN 1 — ported from the old pipeline's detectors.

Zac, item 4: the agent's first message carries what the old pipeline already
knows how to see, ms-precise. Shot changes are the PRIMARY anchor; the rest sit
under them.

WHAT THIS MODULE IS AND IS NOT. Five of the seven signals ruled are PORTS of
detectors that already exist in handler.py / moodreel_editor.py, and the port is
deliberately faithful — same ffmpeg invocations, same thresholds, same parse.
One (audio energy) is NEW, because a per-time energy series does not exist in
the old pipeline: it has overall loudness (astats/volumedetect over the whole
file) and per-SFX RMS, and neither is a curve. One (the beat grid) is NOT HERE
by ruling — it exists on branch `general-editor` at b550e72 (compute_beat_grid /
_aubio_beats, tempo confidence, gated on has_audio) and is ported when the music
route needs it.

EVERY DETECTOR RETURNS A STATE. MEASURED / ABSENT / FAILED, because the whole
point of this file is that the failures here are the silent kind: a detector
that finds nothing and a detector that could not run produce the same empty
list, and the agent cannot tell an uncut single-take clip from scdet failing to
decode. `extract_motion_curve` in the old pipeline returns [] on ANY error by
design ("standalone + fail-safe"); that is correct for a render that must not
die and wrong for a signal the agent reasons from, so it is wrapped rather than
copied.

NO OUT-PARAMETERS. `detect_shot_changes(source_path, threshold, out_scores=)`
fills a caller-supplied dict — the exact shape CLAUDE.md forbids across a seam
("a second output wearing an input's clothes", which would cross a container
boundary and arrive EMPTY). Here the scores are RETURNED.
"""
import json
import os
import re
import subprocess

# ── SHOT CHANGES — THE PRIMARY ANCHOR ──────────────────────────────────────
# Ported from handler.detect_shot_changes. The threshold history is load-bearing
# and travels with it: 0.30 was read as a 0-1 dial and produced 300+ detections
# on a 22s clip; 12.0 filtered real cuts that score 8-11 on normal framing; 7.0
# sits in the measured gap between the motion ceiling (1-3) and the cut floor
# (8.72-10.23). scdet runs internally at the SWEEP threshold so every detection
# is observable with its score, and the RETURN is filtered to `threshold` — the
# sweep is purely observational and is what tells you whether a missed cut was
# below the threshold or below the noise floor entirely.
SCDET_SWEEP_THRESHOLD = 1.0
SCDET_THRESHOLD = 7.0
# Same-framing same-spot splices score ~2-6 because the visual delta between
# back-to-back takes is near zero — below ANY threshold the noise floor allows.
# Those need an audio-discontinuity detector, not threshold tuning. Recorded
# because a shot-change list that misses them looks complete.
SCDET_BLIND_TO = "same-framing same-spot splices (delta ~2-6, under the noise floor)"


def _probe_duration_s(path):
    """-> float or None. NEVER `or 0`: a duration that could not be read is not
    a zero-second video, and this lane has already shipped a 0.0 that segmented
    one (CLAUDE.md, the laundering instance)."""
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    t = (p.stdout or "").strip()
    if p.returncode != 0 or not t:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return v if v > 0 else None


def _weighted_timeout(path, base_s=60, ceiling_s=240):
    """scdet decodes every frame; a 60fps source pays twice. Ported intent from
    handler._probe_weighted_timeout without its ledger dependency."""
    d = _probe_duration_s(path)
    if d is None:
        return ceiling_s
    return int(max(base_s, min(ceiling_s, base_s + d * 2)))


def _parse_scdet(stdout, stderr):
    """-> [(t_s, score)] from ffmpeg's metadata=print stream.

    READS BOTH STREAMS. ffmpeg writes the metadata print to stdout when
    file=- is given and the frame headers to stderr, and which one carries
    what has moved between builds; reading one of them is how a detector
    returns a confident empty list.
    """
    out, t = [], None
    for line in ((stdout or "") + "\n" + (stderr or "")).splitlines():
        m = re.search(r"pts_time:\s*([\d.]+)", line)
        if m:
            try:
                t = float(m.group(1))
            except ValueError:
                t = None
            continue
        m = re.search(r"lavfi\.scd\.score=\s*([\d.]+)", line)
        if m and t is not None:
            try:
                out.append((t, float(m.group(1))))
            except ValueError:
                pass
            t = None
    return out


def shot_changes(path, threshold=SCDET_THRESHOLD, runner=None):
    """THE PRIMARY ANCHOR. -> {state, changes, swept, threshold, why}

    `changes` is [{t, score}] at or above `threshold`; `swept` is every
    detection down to the sweep floor, so a missing cut can be told from a
    filtered one without a second run.
    """
    out = {"state": "ABSENT", "changes": [], "swept": [],
           "threshold": threshold, "why": "not attempted",
           "blind_to": SCDET_BLIND_TO}
    if not path or not os.path.exists(path):
        return dict(out, why="no file at %r" % (path,))
    cmd = ["ffmpeg", "-i", path, "-an", "-vf",
           "scdet=threshold=%s:sc_pass=1,metadata=print:file=-" % SCDET_SWEEP_THRESHOLD,
           "-f", "null", "-"]
    try:
        r = (runner or subprocess.run)(cmd, capture_output=True, text=True,
                                      timeout=_weighted_timeout(path))
    except (OSError, subprocess.SubprocessError) as e:
        return dict(out, state="FAILED",
                    why="scdet: %s: %s" % (type(e).__name__, str(e)[:160]))
    if getattr(r, "returncode", 1) != 0:
        return dict(out, state="FAILED",
                    why="ffmpeg exited %s: %s" % (r.returncode, (r.stderr or "")[-160:]))
    swept = _parse_scdet(r.stdout, r.stderr)
    # A CLIP GENUINELY WITHOUT CUTS IS A REAL ANSWER and must not read as a
    # failure — but it is only a real answer if ffmpeg ran and decoded. The
    # returncode above is what separates them, and it is why the empty case is
    # MEASURED here rather than ABSENT.
    out.update({"state": "MEASURED",
                "swept": [{"t": round(t, 3), "score": round(s, 2)} for t, s in swept],
                "changes": [{"t": round(t, 3), "score": round(s, 2)}
                            for t, s in swept if s >= threshold]})
    out["why"] = ("%d change(s) at or above %.1f, %d swept from %.1f"
                  % (len(out["changes"]), threshold, len(swept), SCDET_SWEEP_THRESHOLD))
    return out


# ── MOTION CURVE ───────────────────────────────────────────────────────────
# Ported from moodreel_editor.extract_motion_curve / motion_features. Optical-
# flow-LITE: downscale, sample, read lavfi scene score per frame, average per
# window, normalise to the peak.
#
# THE ONE CHANGE FROM THE ORIGINAL, AND WHY. The original returns [] on ANY
# error, documented as "standalone + fail-safe" — correct for a render that
# must not die, wrong for a signal the agent reasons from. An empty curve there
# is indistinguishable from a still clip, and the agent would read "no gestures"
# off a failed ffmpeg. Here the two are different states.
def motion_curve(path, window_s=1.0, sample_fps=6.0, scale_w=160, runner=None):
    """-> {state, curve, peaks, resolves, window_s, why}

    A PEAK is a local max above the curve's median (a gesture cresting); its
    RESOLVE is the end of the following descent (the gesture completing). The
    doctrine's "cut where motion resolves" lands on the resolve, never the rise.
    """
    out = {"state": "ABSENT", "curve": [], "peaks": [], "resolves": [],
           "window_s": window_s, "why": "not attempted"}
    if not path or not os.path.exists(path):
        return dict(out, why="no file at %r" % (path,))
    # file=- AND NOT A BARE metadata=print. THE VOLUMEDETECT LESSON, COMMITTED
    # AGAIN BY THE PERSON WHO HAD JUST READ IT (measured on the morning run,
    # 2026-09-20): `metadata=print` writes at INFO level, this call runs at
    # `-v error`, and the print is therefore suppressed -- so the filter ran,
    # ffmpeg exited 0, and the parse found no scores. The detector reported
    # FAILED rather than a still clip, which is the one thing that went right;
    # the detector still did not work. `file=-` writes to stdout regardless of
    # log level, which is what shot_changes already did and why it worked.
    vf = ("scale=%d:-2:flags=bilinear,fps=%g,select='gte(scene,0)',"
          "metadata=print:file=-" % (int(scale_w), sample_fps))
    try:
        r = (runner or subprocess.run)(
            ["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as e:
        return dict(out, state="FAILED",
                    why="motion: %s: %s" % (type(e).__name__, str(e)[:160]))
    if getattr(r, "returncode", 1) != 0:
        return dict(out, state="FAILED",
                    why="ffmpeg exited %s: %s" % (r.returncode, (r.stderr or "")[-160:]))
    scores = [float(m) for m in
              re.findall(r"lavfi\.scene_score=\s*([\d.]+)",
                         (r.stdout or "") + "\n" + (r.stderr or ""))]
    if not scores:
        # NOT a still clip: a still clip produces scores near ZERO, not NO
        # scores. No scores means the filter printed nothing we could read.
        return dict(out, state="FAILED",
                    why="the metadata print yielded no scene scores — a still "
                        "clip reads as scores near zero, not as none at all")
    per = max(1, int(round(sample_fps * window_s)))
    buckets = [scores[i:i + per] for i in range(0, len(scores), per)]
    raw = [sum(b) / len(b) for b in buckets if b]
    peak = max(raw) if raw else 0.0
    curve = [round(v / peak, 4) for v in raw] if peak > 0 else [0.0] * len(raw)
    out["curve"] = curve
    n = len(curve)
    if n >= 3:
        # Floor at 0.15 so noise wiggles on a still clip never read as gestures;
        # the median term keeps busy clips from calling every window a peak.
        thresh = max(sorted(curve)[n // 2], 0.15)
        for i in range(1, n - 1):
            if curve[i] >= curve[i - 1] and curve[i] >= curve[i + 1] and curve[i] > thresh:
                out["peaks"].append(round((i + 0.5) * window_s, 2))
                j = i + 1
                while j + 1 < n and curve[j + 1] <= curve[j]:
                    j += 1
                out["resolves"].append(round((j + 0.5) * window_s, 2))
    out["state"] = "MEASURED"
    out["why"] = ("%d window(s) of %.2fs, %d peak(s); peak raw %.4f"
                  % (n, window_s, len(out["peaks"]), peak))
    return out


# ── AUDIO ENERGY — NEW, NOT A PORT ─────────────────────────────────────────
# The old pipeline has overall loudness (astats/volumedetect over a whole file)
# and per-SFX RMS. Neither is a curve, so there was nothing to port and this is
# built: resample to a fixed rate so the window is a real 100ms regardless of
# the source, cut into fixed-sample windows, and read astats' per-window RMS.
AUDIO_WINDOW_MS = 100
AUDIO_RATE = 16000


def audio_energy(path, window_ms=AUDIO_WINDOW_MS, rate=AUDIO_RATE, runner=None):
    """-> {state, window_ms, times, rms_db, floor_db, why}

    RMS in dBFS per window, plus the times. `-inf` windows (digital silence)
    are carried as None rather than as a number: a silent window is not
    "0 dB", and substituting a floor would make every silence look like quiet
    speech to anything that averages.
    """
    out = {"state": "ABSENT", "window_ms": window_ms, "times": [], "rms_db": [],
           "floor_db": None, "why": "not attempted"}
    if not path or not os.path.exists(path):
        return dict(out, why="no file at %r" % (path,))
    n = max(1, int(round(rate * window_ms / 1000.0)))
    af = ("aresample=%d,asetnsamples=n=%d:p=0,astats=metadata=1:reset=1,"
          "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-"
          % (rate, n))
    try:
        r = (runner or subprocess.run)(
            ["ffmpeg", "-v", "error", "-i", path, "-map", "0:a:0", "-af", af,
             "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        return dict(out, state="FAILED",
                    why="astats: %s: %s" % (type(e).__name__, str(e)[:160]))
    if getattr(r, "returncode", 1) != 0:
        # A VIDEO WITH NO AUDIO STREAM IS ABSENT, NOT FAILED — it is a real
        # and common answer, and the map failure is how it announces itself.
        txt = (r.stderr or "")
        if "Stream map" in txt or "does not contain any stream" in txt:
            return dict(out, state="ABSENT", why="the source carries no audio stream")
        return dict(out, state="FAILED",
                    why="ffmpeg exited %s: %s" % (r.returncode, txt[-160:]))
    times, vals = [], []
    t = None
    for line in ((r.stdout or "") + "\n" + (r.stderr or "")).splitlines():
        m = re.search(r"pts_time:\s*([\d.]+)", line)
        if m:
            try:
                t = float(m.group(1))
            except ValueError:
                t = None
            continue
        m = re.search(r"lavfi\.astats\.Overall\.RMS_level=\s*(-?inf|-?[\d.]+)", line)
        if m and t is not None:
            raw = m.group(1)
            times.append(round(t, 3))
            vals.append(None if "inf" in raw else round(float(raw), 2))
            t = None
    if not times:
        return dict(out, state="FAILED",
                    why="astats printed no RMS windows — the filter ran and read nothing")
    heard = [v for v in vals if v is not None]
    out.update({"state": "MEASURED", "times": times, "rms_db": vals,
                "floor_db": round(min(heard), 2) if heard else None,
                "why": "%d window(s) of %dms at %dHz, %d silent"
                       % (len(times), window_ms, rate, len(vals) - len(heard))})
    return out


# ── SILENCE SPANS ──────────────────────────────────────────────────────────
# Ported from handler._detect_silence_regions_level. LEVEL, not VAD, on
# purpose: Silero holds through quiet room-tone pauses and calls them speech,
# so it misses the ~-30 dB inter-word dead air the ear catches (convicted
# 2026-07-08: 0.45-0.61s gaps survived at -25/-30 dB with the VAD-gated
# detector on).
def silence_spans(path, threshold_db=-30.0, min_silence_s=0.05, runner=None):
    """-> {state, spans, why}. `spans` is [{start, end, dur}]."""
    out = {"state": "ABSENT", "spans": [], "threshold_db": threshold_db,
           "why": "not attempted"}
    if not path or not os.path.exists(path):
        return dict(out, why="no file at %r" % (path,))
    try:
        r = (runner or subprocess.run)(
            ["ffmpeg", "-i", path, "-map", "0:a:0", "-af",
             "silencedetect=noise=%sdB:d=%s" % (threshold_db, min_silence_s),
             "-f", "null", "-"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return dict(out, state="FAILED",
                    why="silencedetect: %s: %s" % (type(e).__name__, str(e)[:160]))
    txt = (r.stderr or "") + (r.stdout or "")
    if getattr(r, "returncode", 1) != 0:
        if "Stream map" in txt or "does not contain any stream" in txt:
            return dict(out, state="ABSENT", why="the source carries no audio stream")
        return dict(out, state="FAILED",
                    why="ffmpeg exited %s: %s" % (r.returncode, txt[-160:]))
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", txt)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", txt)]
    spans = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None      # trailing unmatched -> skip
        if e is not None and e > s:
            spans.append({"start": round(max(0.0, s), 3), "end": round(e, 3),
                          "dur": round(e - max(0.0, s), 3)})
    out.update({"state": "MEASURED", "spans": spans,
                "why": "%d span(s) below %.0f dB for >= %.2fs%s"
                       % (len(spans), threshold_db, min_silence_s,
                          "; %d unmatched start(s) dropped" % (len(starts) - len(ends))
                          if len(starts) > len(ends) else "")})
    return out


# ── FILLER WORDS ───────────────────────────────────────────────────────────
# Ported from handler.detect_filler. Three deterministic, word-boundary-clean
# classes. Words the user explicitly does NOT want cut (literally, basically,
# actually, really) are deliberately in no list — that is a ruling, not an
# omission, and it is the reason this is a fixed list rather than a model call.
FILLER_HESITATION = re.compile(
    r"^(?:"
    r"u+m+"        # um, umm, ummm, ummmm
    r"|u+h+m*"     # uh, uhh, uhm, uhhh, uhmm
    r"|e+r+m*"     # er, err, erm
    r"|a+h+"       # ah, ahh, ahhh
    r"|h+m+"       # hm, hmm, hmmm
    r"|m+h+m*"     # mhm, mhmm, mmhm
    r"|m+"         # mm, mmm (standalone only)
    r")$", re.IGNORECASE)
PAREN_FILLER_MULTI = (("you", "know"), ("i", "mean"))
PAREN_FILLER_SINGLE = frozenset({"like"})
COMMA_CHARS = (",", "،", "、")


def _lemma(w):
    t = (w.get("punctuated_word") or w.get("word") or "")
    return "".join(c.lower() for c in t if c.isalpha())


def _comma(w):
    t = str(w.get("punctuated_word") or w.get("word") or "").rstrip()
    return t.endswith(COMMA_CHARS)


def filler_words(words):
    """-> {state, fillers, why}. `fillers` is [{word_index, reason, t}]."""
    out = {"state": "ABSENT", "fillers": [], "why": "not attempted"}
    if words is None:
        return dict(out, why="no word list — a transcript that was never read "
                             "is not a transcript with no fillers")
    if not words:
        return dict(out, state="MEASURED", why="0 word(s) in the transcript")
    res, consumed, n = [], set(), len(words)
    for i, w in enumerate(words):
        if i in consumed:
            continue
        lem = _lemma(w)
        if lem and FILLER_HESITATION.match(lem):
            res.append({"word_index": i, "reason": "hesitation", "t": w.get("start")})
            continue
        hit = False
        for phrase in PAREN_FILLER_MULTI:
            pl = len(phrase)
            if i + pl > n:
                continue
            if any(_lemma(words[i + k]) != phrase[k] for k in range(pl)):
                continue
            prev_ok = (i == 0) or _comma(words[i - 1])
            if prev_ok and _comma(words[i + pl - 1]):
                for k in range(pl):
                    res.append({"word_index": i + k, "reason": "parenthetical",
                                "t": words[i + k].get("start")})
                    consumed.add(i + k)
                hit = True
                break
        if hit:
            continue
        if lem in PAREN_FILLER_SINGLE and 0 < i < n - 1:
            if _comma(words[i - 1]) and _comma(w):
                res.append({"word_index": i, "reason": "parenthetical",
                            "t": w.get("start")})
    out.update({"state": "MEASURED", "fillers": res,
                "why": "%d filler(s) in %d word(s)" % (len(res), n)})
    return out


# ── FACES — YuNet, NOT res10 ───────────────────────────────────────────────
# THE DETECTOR CHOICE IS THE WHOLE POINT OF THIS BLOCK.
#
# handler.py carries both. `detect_face_positions` / `_dense` — the ones the
# PRODUCTION face trajectory uses — are res10. `_validator_face_signals` is
# YuNet and is marked "ISOLATED to validate_handler". The measurement that
# motivated YuNet is in handler.py beside it, on this product's own traffic:
#
#     res10 face_ratio below 0.25 ....... 52% of clips
#     YuNet face_ratio below 0.25 ....... 22% of clips
#     p50 face ratio .................... res10 0.2   YuNet 0.8
#     "the low-res10 clips were real people YuNet detected"
#     "systematically failed on distant / non-frontal / darker-skin faces —
#      our IND-dominant traffic"
#
# So the better detector has existed since 2026-08-01 and reaches only the
# validator, while every placement decision downstream reads res10.
#
# WHY THAT IS WORSE THAN A QUALITY GAP. A face box that is ABSENT does not
# make the face-collision check fail — it makes it VACUOUS. The check exists to
# stop a card landing on someone's face, and on the 52% of clips res10 cannot
# see, it would pass everything. A check over an empty population asserts
# nothing, and here the empty population is a group of users.
#
# FRAMES COME FROM FFMPEG, NOT cv2. ffmpeg applies the display-matrix rotation
# (autorotate on by default) AND preserves display aspect via scale=-2:H,
# fixing both the cv2-autorotate double-rotation and the coded-dims distortion
# that once sent a portrait talking-head to an upright-only detector SIDEWAYS
# and returned 0 faces.
YUNET_MODEL = "/models/face_detector/yunet.onnx"
YUNET_SCORE = 0.6
YUNET_NMS = 0.3
FACE_SAMPLE_H = 480


def face_track(path, every_n_frames=6, model=YUNET_MODEL, fps_hint=30.0,
               sample_h=FACE_SAMPLE_H):
    """-> {state, boxes, faces_per_s, samples, hits, detector, why}

    `boxes` is [{t, x, y, w, h, score}] in the SAMPLED frame's pixel space,
    with `frame_w`/`frame_h` beside them so a caller can normalise. Absolute
    pixels of an unstated frame size is the shape that produced a card placed
    off the bottom of the picture.
    """
    out = {"state": "ABSENT", "boxes": [], "faces_per_s": None, "samples": 0,
           "hits": 0, "detector": "yunet", "frame_w": None, "frame_h": None,
           "why": "not attempted"}
    if not path or not os.path.exists(path):
        return dict(out, why="no file at %r" % (path,))
    if not os.path.exists(model):
        # NAMED, NOT SILENT, AND NOT FALLEN BACK TO res10. Quietly using the
        # detector this block exists to replace is how the 52% comes back.
        return dict(out, state="ABSENT",
                    why="the YuNet model is not mounted at %s — refusing to "
                        "fall back to res10, which is the detector this "
                        "replaces" % model)
    try:
        import cv2
    except ImportError as e:
        return dict(out, state="FAILED", why="cv2 is not importable: %s" % e)
    import glob
    import shutil
    import tempfile
    fdir = tempfile.mkdtemp(prefix="faces_")
    try:
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", path, "-vf",
                 "select=not(mod(n\\,%d)),scale=-2:%d" % (every_n_frames, sample_h),
                 "-vsync", "0", os.path.join(fdir, "f_%05d.jpg")],
                capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.SubprocessError) as e:
            return dict(out, state="FAILED",
                        why="frame extraction: %s: %s" % (type(e).__name__, str(e)[:140]))
        frames = sorted(glob.glob(os.path.join(fdir, "f_*.jpg")))
        if not frames:
            return dict(out, state="FAILED",
                        why="ffmpeg extracted no frames (%s)" % (r.stderr or "")[-140:])
        det = cv2.FaceDetectorYN_create(model, "", (320, 320), YUNET_SCORE,
                                        YUNET_NMS, 5000)
        boxes, hits = [], 0
        for i, fp in enumerate(frames):
            img = cv2.imread(fp)
            if img is None:
                continue
            h, w = img.shape[:2]
            out["frame_w"], out["frame_h"] = w, h
            det.setInputSize((w, h))
            _n, faces = det.detect(img)
            t = round(i * every_n_frames / float(fps_hint or 30.0), 3)
            if faces is not None and len(faces) > 0:
                hits += 1
                for f in faces:
                    boxes.append({"t": t, "x": float(f[0]), "y": float(f[1]),
                                  "w": float(f[2]), "h": float(f[3]),
                                  "score": round(float(f[14]), 3)})
        dur = _probe_duration_s(path)
        out.update({"state": "MEASURED", "boxes": boxes, "hits": hits,
                    "samples": len(frames),
                    "faces_per_s": (round(len(boxes) / dur, 2) if dur else None),
                    "face_ratio": round(hits / len(frames), 3) if frames else None})
        out["why"] = ("%d face(s) over %d sampled frame(s), %d with a face; "
                      "%s faces/s" % (len(boxes), len(frames), hits,
                                      out["faces_per_s"] if out["faces_per_s"] is not None
                                      else "unknown (no duration)"))
        return out
    finally:
        shutil.rmtree(fdir, ignore_errors=True)


# ── ADAPTIVE FRAME DENSITY ─────────────────────────────────────────────────
# Zac: 1-2fps baseline, EVERY frame within +-0.5s of a shot change, an emphasis
# peak, the hook and the close. Shot changes are the primary anchor.
DENSITY_WINDOW_S = 0.5


def frame_density(dur_s, changes=None, peaks=None, base_fps=1.0, src_fps=30.0,
                  window_s=DENSITY_WINDOW_S, hook_s=2.0, close_s=2.0):
    """-> {state, times, dense_spans, n_base, n_dense, why}

    THE COST IS THE POINT, so it is returned rather than described: `n_dense`
    is how many extra frames the anchors bought, and a caller that cannot
    afford them can see the number before it pays it.
    """
    out = {"state": "ABSENT", "times": [], "dense_spans": [], "n_base": 0,
           "n_dense": 0, "why": "not attempted"}
    if not dur_s or dur_s <= 0:
        return dict(out, why="no duration (%r) — density is a rate over a span"
                             % (dur_s,))
    if not src_fps or src_fps <= 0:
        return dict(out, state="FAILED", why="no source fps (%r)" % (src_fps,))
    anchors = []
    for c in (changes or []):
        t = c.get("t") if isinstance(c, dict) else c
        if t is not None:
            anchors.append(("shot", float(t)))
    for p in (peaks or []):
        anchors.append(("peak", float(p)))
    anchors.append(("hook", min(hook_s, dur_s) / 2.0))
    anchors.append(("close", max(0.0, dur_s - close_s / 2.0)))
    spans = []
    for kind, t in sorted(anchors, key=lambda a: a[1]):
        a, b = max(0.0, t - window_s), min(dur_s, t + window_s)
        if spans and a <= spans[-1]["end"]:
            spans[-1]["end"] = max(spans[-1]["end"], b)
            if kind not in spans[-1]["kinds"]:
                spans[-1]["kinds"].append(kind)
        else:
            spans.append({"start": round(a, 3), "end": round(b, 3), "kinds": [kind]})
    step = 1.0 / float(base_fps)
    times, i = [], 0
    while i * step <= dur_s:
        times.append(round(i * step, 3))
        i += 1
    n_base = len(times)
    fstep = 1.0 / float(src_fps)
    for sp in spans:
        t = sp["start"]
        while t <= sp["end"]:
            times.append(round(t, 3))
            t += fstep
    times = sorted(set(times))
    out.update({"state": "MEASURED", "times": times, "dense_spans": spans,
                "n_base": n_base, "n_dense": len(times) - n_base,
                "why": "%d frame(s): %d at %.1ffps baseline plus %d across %d "
                       "dense span(s) at %.0ffps (+-%.1fs of %d shot change(s), "
                       "%d peak(s), hook, close)"
                       % (len(times), n_base, base_fps, len(times) - n_base,
                          len(spans), src_fps, window_s,
                          len(changes or []), len(peaks or []))})
    return out


# ── THE TURN-1 BLOCK ───────────────────────────────────────────────────────
def perception_lines(sig):
    """The signals as the agent reads them. -> (text, n_measured, n_total)

    EVERY SIGNAL SAYS ITS STATE IN THE AGENT'S OWN MESSAGE. A detector that
    failed and a detector that found nothing must not look the same to the
    model any more than they do to us — an agent told "0 shot changes" edits a
    single take; an agent told "shot changes FAILED" knows not to trust its
    own anchor list.
    """
    order = [("shot changes", "shot_changes", "changes"),
             ("motion", "motion_curve", "peaks"),
             ("audio energy", "audio_energy", "times"),
             ("silence", "silence_spans", "spans"),
             ("fillers", "filler_words", "fillers"),
             ("faces", "face_track", "boxes")]
    lines, ok = ["PERCEPTION — measured from the source, not inferred. "
                 "Shot changes are the primary anchor; every other signal sits "
                 "under them."], 0
    for label, key, listkey in order:
        s = (sig or {}).get(key) or {}
        st = s.get("state", "ABSENT")
        if st == "MEASURED":
            ok += 1
        lines.append("  %-14s %-8s %s" % (label, st, str(s.get("why", ""))[:150]))
    d = (sig or {}).get("frame_density") or {}
    lines.append("  %-14s %-8s %s" % ("density", d.get("state", "ABSENT"),
                                      str(d.get("why", ""))[:150]))
    return "\n".join(lines), ok, len(order)


# ── THE CENSUS ─────────────────────────────────────────────────────────────
# Every detector here feeds the agent's first message, which is a seam, so each
# one is driven blind by a leg with the input missing the thing it reads. The
# expected word is read FROM this table by the check, not from a list in the
# check — the same fix the app-side census needed the day a key started
# answering REFUSED.
PERCEPTION_READERS = (
    ("shot_changes", "no file to decode", "ABSENT"),
    ("motion_curve", "no file to sample", "ABSENT"),
    ("audio_energy", "no file to measure", "ABSENT"),
    ("silence_spans", "no file to scan", "ABSENT"),
    ("filler_words", "a transcript that was never read", "ABSENT"),
    ("face_track", "no file, and no fallback to res10", "ABSENT"),
    ("frame_density", "no duration to spread frames over", "ABSENT"),
)
