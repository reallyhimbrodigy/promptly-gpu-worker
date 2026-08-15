#!/usr/bin/env python3
"""THE LUMEN DESIGN SYSTEM — palette lock, type scale, safe zones [§3.1/§4.2].

Every scene component consumes ONE of these. A scene with a foreign palette is a
defect, and the only way to make that checkable is to have a single object that
says what the edit's colours ARE.

WHY DETERMINISTIC EXTRACTION AND NOT A MODEL CALL: the palette must be identical
for every component in one edit, must cost nothing, must be reproducible for the
differ, and must exist even when the model is suppressed [EDITORIAL_LIVE]. A
model-chosen palette would be a second source of truth that drifts between
scenes — which is exactly the "parts borrowed from different tools" failure the
prompt already warns about.

NO-TEMPLATING [§4.2]: the extractor is a TOOL; the palette it returns is derived
from THIS video's own frames, so two videos produce two different design
systems. Nothing here is a fixed brand.
"""
import colorsys
import json
import os
import subprocess

# Type scale as ratios of frame height, so it is canvas-independent by
# construction — the same object works on 1080x1920 and 1080x608.
TYPE_SCALE = {
    "hero": 0.140,      # a glorified number owning the frame (REF-2's "13")
    "display": 0.085,   # end-card / kinetic display type
    "title": 0.052,     # name-plate name
    "body": 0.034,      # caption base
    "label": 0.020,     # role lines, handles, small caps
}

_SAMPLE_COUNT = 12          # frames sampled across the source
_QUANT_COLORS = 12          # palette size before selection


def _probe_duration(video_path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", video_path],
            capture_output=True, timeout=60)
        return float((r.stdout or b"0").decode().strip() or 0)
    except Exception:
        return 0.0


def _sample_frames(video_path, work_dir, n=_SAMPLE_COUNT):
    """n frames spread across the WHOLE source.

    The first version used select='not(mod(n,30))' with -frames:v n, which reads
    only the first ~n*30 frames — the opening seconds. On both references that
    returned five near-identical whites and no real accent at all, so the
    hue-rotation fallback fired and invented a green. REF-1 is documented
    orange/blue/white; the extractor was wrong, not the reference [canon rule].
    Spreading by fps=n/duration is what makes the sample representative.
    """
    os.makedirs(work_dir, exist_ok=True)
    for f in os.listdir(work_dir):
        if f.startswith("ds_"):
            try:
                os.remove(os.path.join(work_dir, f))
            except OSError:
                pass
    dur = _probe_duration(video_path)
    vf = f"fps={max(1, n)}/{dur:.3f},scale=160:-1" if dur > 1 else "scale=160:-1"
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video_path,
         "-vf", vf, "-frames:v", str(n), os.path.join(work_dir, "ds_%03d.png")],
        capture_output=True, timeout=300)
    if r.returncode != 0:
        return []
    return sorted(os.path.join(work_dir, f) for f in os.listdir(work_dir)
                  if f.startswith("ds_") and f.endswith(".png"))


def _luma(rgb):
    return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255.0


def _sat(rgb):
    return colorsys.rgb_to_hsv(*[c / 255.0 for c in rgb])[1]


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(int(max(0, min(255, c))) for c in rgb)


def extract_palette(video_path, work_dir="/tmp/ds", n_frames=_SAMPLE_COUNT):
    """-> {"bg","fg","accent","source":"extracted"|"fallback","swatches":[...]}

    THE SELECTION RULE, and why each part exists:
      bg      the most COMMON colour — the world the footage already lives in.
      fg      maximum contrast against bg, pushed to near-black/near-white so
              text is always legible. Legibility is not negotiable, so fg is
              derived rather than picked.
      accent  the most SATURATED colour that is not the bg — the one the eye
              reads as the brand. Falls back to a hue-rotation of bg when the
              footage is genuinely colourless (a grey office wall has no accent
              to find, and inventing a loud one is how a foreign palette gets in).
    Deterministic: same video in, same palette out.
    """
    fallback = {"bg": "#0E0E12", "fg": "#FFFFFF", "accent": "#F5A11E",
                "source": "fallback", "swatches": []}
    try:
        from PIL import Image
    except Exception:
        return fallback
    frames = _sample_frames(video_path, work_dir, n_frames)
    if not frames:
        return fallback

    counts = {}
    for f in frames:
        try:
            im = Image.open(f).convert("RGB").quantize(colors=_QUANT_COLORS)
            pal = im.getpalette() or []
            for cnt, idx in im.getcolors() or []:
                rgb = tuple(pal[idx * 3:idx * 3 + 3])
                if len(rgb) == 3:
                    counts[rgb] = counts.get(rgb, 0) + cnt
        except Exception:
            continue
    if not counts:
        return fallback

    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    bg = ranked[0][0]
    # accent: most saturated with real presence (>=3% of sampled pixels)
    total = sum(counts.values()) or 1
    # Presence floor lowered to 0.5%: a brand accent is deliberately RARE —
    # REF-1's orange is a rule and a few words, not a wall. Requiring 3% of
    # pixels selected the wall instead of the brand.
    cands = [c for c, n in ranked if n / total >= 0.005 and c != bg]
    chromatic = [c for c in cands if _sat(c) >= 0.35]
    accent = max(chromatic, key=lambda c: _sat(c) * (0.5 + _luma(c))) if chromatic else None
    if accent is None:
        h, s, v = colorsys.rgb_to_hsv(*[c / 255.0 for c in bg])
        r, g, b = colorsys.hsv_to_rgb((h + 0.5) % 1.0, max(0.55, s), max(0.75, v))
        accent = (r * 255, g * 255, b * 255)
    fg = (250, 250, 252) if _luma(bg) < 0.5 else (18, 18, 24)
    return {"bg": _hex(bg), "fg": _hex(fg), "accent": _hex(accent),
            "source": "extracted",
            "swatches": [_hex(c) for c, _ in ranked[:5]]}


def safe_zones(canvas_w, canvas_h):
    """Mirrors handler._safe_zones_for — TWO DOCTRINES, not one rescaled.
    Vertical dodges platform UI; landscape uses broadcast title-safe, because a
    landscape promo has no app chrome to dodge."""
    if canvas_w >= canvas_h:
        mx, my = round(canvas_w * 0.05), round(canvas_h * 0.05)
        return {"doctrine": "broadcast_title_safe",
                "x": (mx, canvas_w - mx), "y": (my, canvas_h - my)}
    sx, sy = canvas_w / 1080.0, canvas_h / 1920.0
    return {"doctrine": "platform_ui_exclusion",
            "x": (round(60 * sx), round(1020 * sx)),
            "y": (round(108 * sy), round(1812 * sy))}


def build_design_system(video_path=None, canvas=(1080, 1920), work_dir="/tmp/ds",
                        palette=None):
    """The ONE object every Lumen component consumes."""
    w, h = canvas
    pal = palette or (extract_palette(video_path, work_dir) if video_path
                      else {"bg": "#0E0E12", "fg": "#FFFFFF", "accent": "#F5A11E",
                            "source": "default", "swatches": []})
    return {
        "canvas": {"width": w, "height": h,
                   "orientation": "landscape" if w >= h else "vertical"},
        "palette": pal,
        "type_scale": {k: round(v * h) for k, v in TYPE_SCALE.items()},
        "type_ratios": dict(TYPE_SCALE),
        "safe": safe_zones(w, h),
    }


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        ds = build_design_system(p, canvas=(1080, 1920))
        print(f"{os.path.basename(p)}: {json.dumps(ds['palette'])}")
