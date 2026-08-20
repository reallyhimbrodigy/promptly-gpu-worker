#!/usr/bin/env python3
"""SELECT THE REFERENCE STILLS THAT ACTUALLY SHOW AN INSERT SCENE. `[Rule 3]`

`exemplar_block("FRAMES_PLAN")` emits the sentence "Stills from each reference
are attached" — and NOTHING EVER ATTACHED THEM. The module's own docstring says
"the caller attaches the media parts; this module never builds a request", and
no caller does. So FRAMES_PLAN today tells the model to look at something that
is not in the payload, which is worse than not mentioning stills at all.

This produces the stills. The hard part is not extraction, it is SELECTION: a
grid of evenly-spaced frames from a talking-head reference is mostly the
talking head, and stills of a speaker's face teach nothing about insert scenes.

THE MECHANICAL SIGNAL. A composed takeover REPLACES the frame, and per
ART_DIRECTION §4 it is built on a flat near-white ground with type over it. A
camera frame almost never contains a large area of one flat colour. So:

    flatness  = fraction of pixels within a tight band of the modal colour
    edge-ness = fraction of pixels on a strong luminance edge (type has many)

An insert scene scores HIGH flatness (the ground) with real edge content (the
type). A face scores low flatness. Neither alone is enough — a black frame is
flat with no edges, a busy room is edgy with no flatness — so both are required
and both are REPORTED per still, so the selection can be audited rather than
trusted.

NOT FACE DETECTION, and that is a compromise worth naming: the pipeline's own
detector lives at /models/face_detector inside the container, and cv2 is not
installed locally. Face-absence would be the cleaner signal. This heuristic is
the honest local substitute, and every candidate's numbers are written to the
manifest so a human can overrule it.

    python3 build_reference_stills.py [--out reference_stills] [--n 8]
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

REFS = [
    ("REF1", "golden/lumen-refs/ref1-legalsoft-corporate-landscape.mp4"),
    ("REF2", "golden/lumen-refs/ref2-viral-creator-doc-vertical.mp4"),
]
SAMPLE_EVERY_S = 0.5


def _score(path):
    """(flatness, edginess) for one frame."""
    im = Image.open(path).convert("L").resize((240, 320))
    a = np.asarray(im, dtype=np.float32)
    hist, _ = np.histogram(a, bins=32, range=(0, 255))
    flatness = float(hist.max()) / float(a.size)
    gx = np.abs(np.diff(a, axis=1))
    gy = np.abs(np.diff(a, axis=0))
    edginess = float(((gx > 28).mean() + (gy > 28).mean()) / 2.0)
    return flatness, edginess


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reference_stills")
    ap.add_argument("--n", type=int, default=8)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    tmp = os.path.join(a.out, "_candidates")
    os.makedirs(tmp, exist_ok=True)

    picked = []
    for tag, src in REFS:
        if not os.path.exists(src):
            print(f"  {tag}: MISSING {src} — cannot build stills"); return 1
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", src,
             "-vf", f"fps=1/{SAMPLE_EVERY_S},scale=480:-2",
             os.path.join(tmp, f"{tag}_%04d.jpg")],
            check=True, capture_output=True)
        cands = sorted(os.listdir(tmp))
        scored = []
        for c in cands:
            p = os.path.join(tmp, c)
            fl, ed = _score(p)
            scored.append({"file": c, "flatness": round(fl, 3),
                           "edginess": round(ed, 3),
                           "t_s": round(int(c.split("_")[1].split(".")[0]) * SAMPLE_EVERY_S, 1)})
        # BOTH required: flat ground AND real type. A black frame is flat with no
        # edges; a busy room is edgy with no flatness. Neither is an insert scene.
        keep = [s for s in scored if s["flatness"] >= 0.16 and s["edginess"] >= 0.045]
        keep.sort(key=lambda s: -(s["flatness"] * s["edginess"]))
        print(f"  {tag}: {len(cands)} frames sampled, {len(keep)} look like takeovers")
        for s in keep[:max(1, a.n // 2)]:
            dst = os.path.join(a.out, f"{tag}_t{s['t_s']}.jpg")
            os.replace(os.path.join(tmp, s["file"]), dst)
            s["path"] = dst
            s["ref"] = tag
            picked.append(s)
            print(f"     t={s['t_s']:5.1f}s  flat={s['flatness']:.3f} "
                  f"edge={s['edginess']:.3f}  -> {os.path.basename(dst)}")

    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    man = os.path.join(a.out, "manifest.json")
    with open(man, "w") as fh:
        json.dump({"built": "2026-08-19", "sample_every_s": SAMPLE_EVERY_S,
                   "selector": "flatness>=0.16 AND edginess>=0.045 (composed "
                               "takeover: flat ground + real type)",
                   "caveat": "NOT face detection — cv2 and /models/face_detector "
                             "are container-only. Numbers are reported per still "
                             "so the selection can be audited, not trusted.",
                   "stills": picked}, fh, indent=1)
    print(f"\n  {len(picked)} stills -> {a.out}/  (manifest: {man})")
    if len(picked) < 4:
        print("  *** FEWER THAN 4 STILLS. FRAMES_PLAN would be a weak stimulus; "
              "loosen the thresholds or select by hand before spending a cell.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
