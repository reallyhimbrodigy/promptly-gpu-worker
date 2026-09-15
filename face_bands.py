#!/usr/bin/env python3
"""The face detector and the band vocabulary PRODUCTION already uses.

NOT A NEW DETECTOR AND NOT A NEW BAND TABLE. handler.py has carried
`detect_face_positions` (res10 SSD via cv2.dnn, CONFIDENCE_THRESHOLD 0.5) and
`_face_occupied_bands` for months, together with `_MG_FACE_BAND_YRANGES` and
`_MG_FACE_CLEAR_THRESHOLD`, and `_mg_clear_region_exists` routes placements
around faces, the source's own burned text AND our own captions.

THE LANE DIVERGED FROM ALL OF IT. `agentic_editor_app.py` contains ZERO
references to `source_text_regions`, `face_traj` or `detect_face`, so the
agentic ruling carries none of those facts, and the ChatCut translator invented
its own zones instead. `_caption_occupied_bands`' docstring, dated 2026-08-19,
describes the exact defect that then shipped:

    "A face-only reposition will happily move a card into the band the captions
     land in, trading a collision with the speaker for a collision with our own
     type."

So the constants and the band logic are COPIED VERBATIM from handler.py rather
than re-derived, and the copy is asserted against the original by
smoke_bands_match_production.py — a second table that drifts is worse than no
second table.
"""
import os

# ── verbatim from handler.py ────────────────────────────────────────────────
MG_FACE_BAND_YRANGES = {"top": (120.0, 640.0), "center": (640.0, 1280.0),
                        "bottom": (1280.0, 1800.0)}
MG_FACE_CLEAR_THRESHOLD = 0.35
CONFIDENCE_THRESHOLD = 0.5
PROTOTXT = "/models/face_detector/deploy.prototxt"
CAFFEMODEL = "/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel"


def detect_face_positions(video_path, sample_timestamps):
    """[{t, cx, cy, found, confidence}] — res10 SSD, the production detector.

    FAIL-SAFE AND NAMED: returns None when cv2 or the model is missing, so the
    caller reports ABSENT rather than an empty list that reads like "no faces".
    """
    try:
        import cv2
    except ImportError:
        return None
    if not (os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL)):
        return None
    net = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    out, last = [], (540, 960)
    for t in sample_timestamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            out.append({"t": float(t), "cx": last[0], "cy": last[1],
                        "found": False, "confidence": 0.0})
            continue
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                                     (300, 300), (104.0, 177.0, 123.0),
                                     swapRB=False, crop=False)
        net.setInput(blob)
        det = net.forward()
        best_conf, best, found, best_area = 0.0, last, False, 0
        for i in range(det.shape[2]):
            conf = float(det[0, 0, i, 2])
            if conf < CONFIDENCE_THRESHOLD:
                continue
            x1, y1 = int(det[0, 0, i, 3] * w), int(det[0, 0, i, 4] * h)
            x2, y2 = int(det[0, 0, i, 5] * w), int(det[0, 0, i, 6] * h)
            area = (x2 - x1) * (y2 - y1)
            if conf > best_conf or area > best_area:
                best_conf, best_area = conf, area
                best, found = ((x1 + x2) // 2, (y1 + y2) // 2), True
        if found:
            last = best
        out.append({"t": float(t), "cx": best[0], "cy": best[1],
                    "found": found, "confidence": best_conf})
    cap.release()
    return out


def face_occupied_bands(face_traj, t0_s, t1_s, frame_h=1920):
    """The bands the SUBJECT'S FACE occupies over [t0,t1] — handler.py's rule.

    Verbatim logic: a 600px face window around each detected centre, the mean
    fractional coverage of each band across the sampled points, and a band is
    occupied when that mean exceeds MG_FACE_CLEAR_THRESHOLD.
    """
    pts = [p for p in (face_traj or [])
           if p.get("found") and (t0_s - 0.5) <= float(p.get("t") or 0.0)
           <= (t1_s + 0.5)]
    if not pts:
        return set()
    FH = 600.0
    occ = set()
    for band, (y0, y1) in MG_FACE_BAND_YRANGES.items():
        cov = sum(max(0.0, min(y1, float(p.get("cy") or 960.0) + FH / 2.0)
                      - max(y0, float(p.get("cy") or 960.0) - FH / 2.0)) / FH
                  for p in pts) / len(pts)
        if cov > MG_FACE_CLEAR_THRESHOLD:
            occ.add(band)
    return occ


def band_to_fraction(band, frame_h=1920.0):
    y0, y1 = MG_FACE_BAND_YRANGES[band]
    return (y0 / frame_h, y1 / frame_h)
