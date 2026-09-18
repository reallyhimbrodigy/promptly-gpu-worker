#!/usr/bin/env python3
"""Fetch the signed frames and tile them into contact sheets I can actually read.

WHY TILE AT ALL, since tokens scale with PIXELS and tiling saves none of them:
because a sheet shows SEQUENCE. Judging how a cut is made, whether an entrance
is late, how long a title holds — none of that is visible in a frame on its
own, and 85 separate images is 85 separate looks at a still. The cost is the
same; the reading is not.

EVERY CELL CARRIES ITS OWN TIMESTAMP, burned in. A contact sheet whose cells
are unlabelled is a wall of stills: any claim about timing made from it is
unfalsifiable, and a drifting index produces a confident sentence about the
wrong shot — which is the one failure this artefact cannot survive.
"""
import json
import os
import sys
import urllib.request

from PIL import Image, ImageDraw


def fetch(urls, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths, bad = [], []
    for i, u in enumerate(urls):
        p = os.path.join(out_dir, "f%05d.jpg" % i)
        if os.path.exists(p) and os.path.getsize(p) > 2000:
            paths.append(p)
            continue
        try:
            with urllib.request.urlopen(u, timeout=90) as fh:
                b = fh.read()
            if len(b) < 2000:
                bad.append("%d: %d bytes" % (i, len(b)))
                continue
            with open(p, "wb") as fh:
                fh.write(b)
            paths.append(p)
        except Exception as e:                                    # noqa: BLE001
            bad.append("%d: %s" % (i, type(e).__name__))
    return paths, bad


def tile(paths, times_ms, out_png, cols=6, rows=4, cell_w=240, label=True):
    """Contact sheets of cols*rows cells. -> [sheet paths]."""
    sheets = []
    per = cols * rows
    for s in range(0, len(paths), per):
        chunk = paths[s:s + per]
        tms = times_ms[s:s + per]
        with Image.open(chunk[0]) as im0:
            ar = im0.height / float(im0.width)
        cell_h = int(round(cell_w * ar))
        pad = 18
        sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + pad)),
                          (16, 16, 18))
        d = ImageDraw.Draw(sheet)
        for k, p in enumerate(chunk):
            cx, cy = (k % cols) * cell_w, (k // cols) * (cell_h + pad)
            try:
                with Image.open(p) as im:
                    sheet.paste(im.convert("RGB").resize((cell_w, cell_h),
                                                         Image.LANCZOS),
                                (cx, cy + pad))
            except Exception:                                     # noqa: BLE001
                d.rectangle([cx, cy + pad, cx + cell_w, cy + pad + cell_h],
                            fill=(60, 0, 0))
            if label and k < len(tms):
                d.text((cx + 4, cy + 4), "%.2fs" % (tms[k] / 1000.0),
                       fill=(255, 210, 120))
        out = out_png.replace(".png", "_%02d.png" % (s // per))
        sheet.save(out, optimize=True)
        sheets.append(out)
    return sheets


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ref_urls.json"
    tag = sys.argv[2] if len(sys.argv) > 2 else "clip"
    cw = int(sys.argv[3]) if len(sys.argv) > 3 else 240
    cols = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    rows = int(sys.argv[5]) if len(sys.argv) > 5 else 4
    d = json.load(open(src, encoding="utf-8"))
    base = "/tmp/refwatch/%s" % tag
    paths, bad = fetch(d["urls"], base)
    sheets = tile(paths, d["times"], base + "/sheet.png", cols, rows, cw)
    px = 0
    for s in sheets:
        with Image.open(s) as im:
            px += im.width * im.height
    print("%s: %d frame(s) fetched (%d bad), %d sheet(s), ~%d tok total"
          % (tag, len(paths), len(bad), len(sheets), px // 750))
    for s in sheets:
        with Image.open(s) as im:
            print("   %s  %dx%d  ~%d tok" % (s, im.width, im.height,
                                             im.width * im.height // 750))
