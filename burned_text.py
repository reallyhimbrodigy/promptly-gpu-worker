"""Deterministic burned-in-text detector — the GUARANTEE layer of the burned-in-text guard.

Every burned-text value in the pipeline today is MODEL-DECLARED (Gemini watching a
480p@18fps proxy) or frontend-declared. When Gemini misses burned-in captions, the
existing suppression gate (handler.py:13268) never fires and the render double-captions.
This module gives the gates a deterministic signal so they fire on TRUTH.

CRITICAL: it samples the ORIGINAL SOURCE frames, NOT the 480p Gemini proxy. Reading the
same degraded proxy would inherit the model's small-text handicap and stop being a better
oracle — which defeats the point. The caller passes the raw downloaded source path.

FAIL-SAFE: any error (missing model, unreadable video, cv2 quirk) returns None → the
caller treats it as 'unknown' → the pipeline behaves EXACTLY as today (model-declared
signals only). It can never make the render worse than the pre-feature baseline.

Detection: EAST text detector via cv2.dnn (cv2 is already in the worker image for face
detection; the model ships by wget like /models/face_detector/). EAST finds text REGIONS
(not recognition), which is all the gates need: has_burned_text, the bands text occupies,
coverage, and persistent(captions)-vs-incidental(signage/watermark).
"""

import os

# The EAST model ships in the image by wget (see modal_app.py), mirroring the
# face-detector Caffe model. Absent locally → detector returns None (unknown).
EAST_MODEL_PATH = os.environ.get("PROMPTLY_EAST_MODEL_PATH", "/models/east/frozen_east_text_detection.pb")

# Detection resolution long-side (rounded to a multiple of 32 as EAST requires).
# Deliberately ABOVE the 480p proxy so the detector out-resolves the model on small
# text; tunable via env to trade cost for small-text recall (cost is measured, not assumed).
# 896px is load-bearing for PRECISION: at this res EAST merges a caption LINE into
# one wide box (width ~0.55), cleanly separable from texture noise (<=0.27). Dropping
# to 736 split the caption into word-boxes (max 0.245 -> missed) AND let a mandelbrot
# noise box reach 0.447 (false-suppress) — worst of both. Precision > cost here: a
# false suppression is a SILENT worse-than-double defect. Cost comes from frames only.
EAST_LONG_SIDE = int(os.environ.get("PROMPTLY_EAST_LONG_SIDE", "896"))
EAST_SAMPLE_N = int(os.environ.get("PROMPTLY_EAST_SAMPLE_N", "6"))
# Score threshold kept HIGH: EAST fires weak responses on busy texture (a fractal
# base produced 60-110 sub-glyph boxes/frame at 0.5). Real burned-in text scores
# ~0.99, so a high bar keeps real captions and kills texture noise.
EAST_SCORE_THRESH = float(os.environ.get("PROMPTLY_EAST_SCORE", "0.9"))
EAST_NMS_THRESH = float(os.environ.get("PROMPTLY_EAST_NMS", "0.4"))
# Minimum box size (normalized) to count as real text — filters sub-glyph texture
# flecks. A real word-group is wider than a fleck and a real caption line taller.
MIN_BOX_W = float(os.environ.get("PROMPTLY_EAST_MIN_W", "0.05"))
MIN_BOX_H = float(os.environ.get("PROMPTLY_EAST_MIN_H", "0.018"))
# A band counts as occupied only if a real box lands there in >=2 frames AND the
# band's summed box area is above a floor — one stray survivor is not "burned text".
MIN_BAND_FRAMES = 2
# SYNCED signal: real captions CHANGE across frames (new words with the speech); a
# static handle/logo/title banner does NOT. Temporal per-pixel std of the band
# separates them — a persistent WIDE but STATIC bottom band (a watermark handle) is
# signage, not captions, so it never triggers a false caption-suppression. Calibrated
# on real clips: changing caption bands run well above this; static handles below.
CHANGE_MIN = float(os.environ.get("PROMPTLY_EAST_CHANGE_MIN", "9.0"))
_SG_W, _SG_H = 96, 168  # small grayscale used only for the temporal-change measure

# Persistence: a band with text in >= this fraction of sampled frames is PERSISTENT
# (Zac's rule: same band >=~70% of frames = synced captions).
PERSIST_FRAC = float(os.environ.get("PROMPTLY_EAST_PERSIST", "0.70"))
# A caption ROW spans >= this fraction of frame width. Set to 0.50 (not 0.33) after
# real-clip calibration: a synced caption line runs 0.54-0.91 wide, while a handle/
# watermark row (e.g. "@user") tops out ~0.37 — 0.50 cleanly separates them, so a wide
# handle can't trigger a false caption-suppression. Precision > recall here by design.
CAPTION_MIN_WIDTH = float(os.environ.get("PROMPTLY_EAST_CAPTION_WIDTH", "0.50"))
# A box is a corner mark (watermark/handle) if it is small AND hugs a frame corner.
CORNER_MAX_WIDTH = 0.30
CORNER_MARGIN = 0.18  # within this fraction of an edge counts as "near the edge"


def _band_of(ny_center):
    """Map a box's normalized vertical center to top / center / bottom third."""
    if ny_center < 1.0 / 3.0:
        return "top"
    if ny_center < 2.0 / 3.0:
        return "center"
    return "bottom"


def _decode_east(scores, geometry, score_thresh):
    """Standard OpenCV EAST decode → axis-aligned rects (in the resized-frame space)
    + confidences. Angle is ignored: burned-in captions are horizontal, and axis-
    aligned boxes are all the band/width logic needs."""
    import numpy as np
    (num_rows, num_cols) = scores.shape[2:4]
    rects = []
    confidences = []
    for y in range(num_rows):
        scores_data = scores[0, 0, y]
        x0 = geometry[0, 0, y]
        x1 = geometry[0, 1, y]
        x2 = geometry[0, 2, y]
        x3 = geometry[0, 3, y]
        angles = geometry[0, 4, y]
        for x in range(num_cols):
            score = float(scores_data[x])
            if score < score_thresh:
                continue
            offset_x, offset_y = x * 4.0, y * 4.0
            angle = angles[x]
            cos_a, sin_a = np.cos(angle), np.sin(angle)
            h = x0[x] + x2[x]
            w = x1[x] + x3[x]
            end_x = int(offset_x + cos_a * x1[x] + sin_a * x2[x])
            end_y = int(offset_y - sin_a * x1[x] + cos_a * x2[x])
            start_x = int(end_x - w)
            start_y = int(end_y - h)
            rects.append([start_x, start_y, int(w), int(h)])  # x,y,w,h for NMSBoxes
            confidences.append(score)
    return rects, confidences


def _detect_frame(net, frame, score_thresh, nms_thresh, long_side):
    """Run EAST on one BGR frame → list of normalized boxes (nx0,ny0,nx1,ny1,conf)."""
    import cv2
    import numpy as np
    fh, fw = frame.shape[:2]
    if fh == 0 or fw == 0:
        return []
    # Resize so the long side ~ long_side, both dims rounded to a multiple of 32.
    scale = long_side / float(max(fw, fh))
    rw = max(32, int(round(fw * scale / 32)) * 32)
    rh = max(32, int(round(fh * scale / 32)) * 32)
    blob = cv2.dnn.blobFromImage(frame, 1.0, (rw, rh),
                                 (123.68, 116.78, 103.94), swapRB=True, crop=False)
    net.setInput(blob)
    scores, geometry = net.forward(
        ["feature_fusion/Conv_7/Sigmoid", "feature_fusion/concat_3"])
    rects, confs = _decode_east(scores, geometry, score_thresh)
    if not rects:
        return []
    idxs = cv2.dnn.NMSBoxes(rects, confs, score_thresh, nms_thresh)
    if idxs is None or len(idxs) == 0:
        return []
    out = []
    for i in np.array(idxs).flatten():
        x, y, w, h = rects[int(i)]
        # rects are in the RESIZED frame space → normalize by the resized dims
        nx0 = max(0.0, x / rw)
        ny0 = max(0.0, y / rh)
        nx1 = min(1.0, (x + w) / rw)
        ny1 = min(1.0, (y + h) / rh)
        if nx1 <= nx0 or ny1 <= ny0:
            continue
        # drop sub-glyph texture flecks — real text boxes clear a minimum size
        if (nx1 - nx0) < MIN_BOX_W or (ny1 - ny0) < MIN_BOX_H:
            continue
        out.append((nx0, ny0, nx1, ny1, float(confs[int(i)])))
    return out


def _is_corner_mark(nx0, ny0, nx1, ny1):
    """A small box hugging a frame corner = watermark / handle / logo (incidental)."""
    w = nx1 - nx0
    if w > CORNER_MAX_WIDTH:
        return False
    near_left = nx0 <= CORNER_MARGIN
    near_right = nx1 >= 1.0 - CORNER_MARGIN
    near_top = ny0 <= CORNER_MARGIN
    near_bot = ny1 >= 1.0 - CORNER_MARGIN
    return (near_left or near_right) and (near_top or near_bot)


def _widest_row_extent(boxes, y_tol=0.04):
    """Widest horizontal extent of any single TEXT ROW among these boxes.

    Groups boxes by y-center proximity into rows, then returns the widest row's
    (max x1 - min x0). This is the ROBUST caption signal: a caption LINE spans a
    wide extent even when EAST splits it into word-boxes (a lucky single merged box
    is no longer required), while scattered texture noise sits at varied y, so each
    'row' is one small box → small extent. Resolution-stable where max-box-width was
    fragile (0.55 at 9 frames vs 0.23 at 6 — same clip, same res)."""
    if not boxes:
        return 0.0
    rows = []
    for b in sorted(boxes, key=lambda bb: (bb[1] + bb[3]) / 2.0):
        yc = (b[1] + b[3]) / 2.0
        placed = False
        for row in rows:
            if abs(row["yc"] - yc) <= y_tol:
                row["x0"] = min(row["x0"], b[0])
                row["x1"] = max(row["x1"], b[2])
                row["yc"] = (row["yc"] * row["n"] + yc) / (row["n"] + 1)
                row["n"] += 1
                placed = True
                break
        if not placed:
            rows.append({"yc": yc, "x0": b[0], "x1": b[2], "n": 1})
    return max((r["x1"] - r["x0"] for r in rows), default=0.0)


def detect_burned_in_text(source_path, sample_n=None, long_side=None, debug=False):
    """Detect pre-existing burned-in text in the ORIGINAL source video.

    Returns a JSON-safe dict, or None on ANY error (→ caller treats as unknown →
    pipeline behaves exactly as today). Never raises.

    dict:
      has_burned_text: bool
      has_burned_captions: bool         # a persistent wide lower/center band = synced captions
      existing_caption_region: 'none'|'top'|'center'|'bottom'
      source_text_regions: [bands with persistent OR corner text — camera/overlay avoid]
      regions: [{band, class, persistence, max_width, coverage, n_boxes}]
      frames_sampled, detector_long_side, cost_ms
    """
    try:
        import cv2
        import numpy as np
        import time
        t0 = time.time()
        if not os.path.exists(EAST_MODEL_PATH):
            return None
        _n = int(sample_n or EAST_SAMPLE_N)
        _long = int(long_side or EAST_LONG_SIDE)
        cap = cv2.VideoCapture(source_path)
        if not cap.isOpened():
            return None
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if n_frames <= 0 or fw <= 0 or fh <= 0:
            cap.release()
            return None
        net = cv2.dnn.readNet(EAST_MODEL_PATH)
        # sample evenly, skipping the first/last 8% (title cards, fades, black frames)
        fracs = np.linspace(0.08, 0.92, max(1, _n))
        idxs = sorted({int(n_frames * f) for f in fracs})
        band_hits = {"top": 0, "center": 0, "bottom": 0}          # frames with any real box
        band_wide_hits = {"top": 0, "center": 0, "bottom": 0}     # frames with a caption-WIDTH row
        band_max_extent = {"top": 0.0, "center": 0.0, "bottom": 0.0}
        band_boxcount = {"top": 0, "center": 0, "bottom": 0}
        band_corner = {"top": False, "center": False, "bottom": False}
        gray_frames = []
        frames_read = 0
        for idx in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            frames_read += 1
            gray_frames.append(cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (_SG_W, _SG_H)))
            boxes = _detect_frame(net, frame, EAST_SCORE_THRESH, EAST_NMS_THRESH, _long)
            per_band = {"top": [], "center": [], "bottom": []}
            for (nx0, ny0, nx1, ny1, conf) in boxes:
                band = _band_of((ny0 + ny1) / 2.0)
                per_band[band].append((nx0, ny0, nx1, ny1))
                if _is_corner_mark(nx0, ny0, nx1, ny1):
                    band_corner[band] = True
            # per-FRAME row analysis (not accumulated) — a caption is a wide row
            # present in MANY frames, not one lucky merged box across all frames.
            for band, bxs in per_band.items():
                if not bxs:
                    continue
                band_hits[band] += 1
                band_boxcount[band] += len(bxs)
                ext = _widest_row_extent(bxs)
                if ext > band_max_extent[band]:
                    band_max_extent[band] = ext
                if ext >= CAPTION_MIN_WIDTH:
                    band_wide_hits[band] += 1
        cap.release()
        if frames_read == 0:
            return None

        # Per-band temporal change (synced-caption signal): high per-pixel std across
        # frames = the band's content is CHANGING (a caption track) vs a static handle.
        band_change = {"top": 0.0, "center": 0.0, "bottom": 0.0}
        if len(gray_frames) >= 2:
            stack = np.stack(gray_frames).astype("float32")   # (N, H, W)
            thirds = {"top": (0, _SG_H // 3),
                      "center": (_SG_H // 3, 2 * _SG_H // 3),
                      "bottom": (2 * _SG_H // 3, _SG_H)}
            for _b, (y0, y1) in thirds.items():
                band_change[_b] = float(stack[:, y0:y1, :].std(axis=0).mean())

        regions = []
        source_text_regions = []
        has_caps = False
        ecr = "none"
        for band in ("top", "center", "bottom"):
            n_hit = band_hits[band]
            if n_hit == 0:
                continue
            persistence = n_hit / frames_read              # frames with ANY box here
            wide_persistence = band_wide_hits[band] / frames_read  # frames with a caption-width ROW
            max_ext = band_max_extent[band]
            is_persistent = persistence >= PERSIST_FRAC
            only_corner = band_corner[band] and max_ext <= CORNER_MAX_WIDTH
            is_dynamic = band_change[band] >= CHANGE_MIN
            # captions = a caption-WIDTH ROW that (a) PERSISTS across >=PERSIST_FRAC
            # of frames, (b) sits in BOTTOM/CENTER, (c) is not a corner mark, and
            # (d) is DYNAMIC — its content changes across frames like synced speech.
            # (d) is the guard against false-suppression on a persistent STATIC wide
            # band (a watermark handle, a fixed title banner): those are signage, and
            # calling them captions would silently drop the user's real captions —
            # worse than the doubled captions we're fixing. Requiring persistence +
            # dynamism also rejects texture noise and survives EAST word-splitting.
            if (band in ("bottom", "center") and wide_persistence >= PERSIST_FRAC
                    and not only_corner and is_dynamic):
                cls = "captions"
            elif is_persistent or n_hit >= 2:
                cls = "signage"          # top text, persistent-but-narrow, corner mark, STATIC banner, logo
            else:
                cls = "incidental"       # one-off / transient text (a passing sign)
            regions.append({
                "band": band, "class": cls,
                "persistence": round(persistence, 3),
                "wide_persistence": round(wide_persistence, 3),
                "max_row_extent": round(float(max_ext), 3),
                "change": round(band_change[band], 2),
                "n_boxes": band_boxcount[band],
                "corner": band_corner[band],
            })
            # captions + signage are burned text the CAMERA and overlays must respect
            if cls in ("captions", "signage"):
                source_text_regions.append(band)
            # only a caption-like band suppresses OUR caption track
            if cls == "captions" and not has_caps:
                has_caps = True
                ecr = band
        cost_ms = int((time.time() - t0) * 1000)
        result = {
            "has_burned_text": bool(source_text_regions),
            "has_burned_captions": has_caps,
            "existing_caption_region": ecr,
            "source_text_regions": source_text_regions,
            "regions": regions,
            "frames_sampled": frames_read,
            "detector_long_side": _long,
            "cost_ms": cost_ms,
        }
        return result
    except Exception:
        # FAIL-SAFE: never raise into the pipeline. Unknown → behave as today.
        return None
