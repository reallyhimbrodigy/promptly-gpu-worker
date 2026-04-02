"""
Python-native caption renderer — replaces Remotion's Chrome-based rendering.

Generates transparent PNG overlays for each caption state (word highlight change),
then FFmpeg composites them in the existing single-pass render.

All 30+ style presets from Remotion are cached here as Python dicts.
Rendering 60-80 PNGs with Pillow takes <0.5 seconds vs 40-130s in Chrome.
"""

import os
import math
import numpy
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Font Loading ────────────────────────────────────────────────────────────

FONT_DIR = "/assets/fonts"

# Map style fontFamily + weight to .ttf files
_FONT_MAP = {
    ("Montserrat", 800):  "Montserrat-ExtraBold.ttf",
    ("Montserrat", 900):  "Montserrat-Black.ttf",
    ("Montserrat", 700):  "Montserrat-Bold.ttf",
    ("Montserrat", 600):  "Montserrat-Bold.ttf",      # closest
    ("Montserrat", 500):  "Montserrat-Bold.ttf",      # closest
    ("Montserrat", 400):  "Montserrat-Bold.ttf",      # fallback
    ("Poppins", 800):     "Poppins-ExtraBold.ttf",
    ("Poppins", 700):     "Poppins-Bold.ttf",
    ("Poppins", 600):     "Poppins-SemiBold.ttf",
    ("Poppins", 500):     "Poppins-SemiBold.ttf",
    ("Poppins", 400):     "Poppins-SemiBold.ttf",     # fallback
    ("Bangers", 400):     "Bangers-Regular.ttf",
    ("Bebas Neue", 400):  "BebasNeue-Regular.ttf",
    ("Oswald", 700):      "Oswald-Variable.ttf",
    ("Permanent Marker", 400): "PermanentMarker-Regular.ttf",
    ("Playfair Display", 700): "PlayfairDisplay-Variable.ttf",
    ("Space Grotesk", 700):    "SpaceGrotesk-Variable.ttf",
    ("Space Grotesk", 500):    "SpaceGrotesk-Variable.ttf",
}

_font_cache = {}

def _get_font(family, weight, size):
    key = (family, weight, size)
    if key in _font_cache:
        return _font_cache[key]
    ttf_name = _FONT_MAP.get((family, weight))
    if not ttf_name:
        # Try family with any weight
        for (f, w), name in _FONT_MAP.items():
            if f == family:
                ttf_name = name
                break
    if not ttf_name:
        ttf_name = "Montserrat-ExtraBold.ttf"
    path = os.path.join(FONT_DIR, ttf_name)
    if not os.path.exists(path):
        # Fallback for local development
        path = os.path.join("src/assets/fonts", ttf_name)
    try:
        font = ImageFont.truetype(path, size)
    except Exception:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


# ─── Style Presets (ported from Remotion TypeScript) ─────────────────────────

KEYWORD_COLORS = ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"]

SHADOW_DEEP = [
    {"x": 0, "y": 4, "blur": 12, "color": (0, 0, 0, 178)},
    {"x": 0, "y": 2, "blur": 6, "color": (0, 0, 0, 128)},
    {"x": 0, "y": 1, "blur": 2, "color": (0, 0, 0, 230)},
]
SHADOW_SUBTLE = [
    {"x": 0, "y": 2, "blur": 8, "color": (0, 0, 0, 128)},
    {"x": 0, "y": 1, "blur": 3, "color": (0, 0, 0, 178)},
]
SHADOW_GLOW = [
    {"x": 0, "y": 0, "blur": 20, "color": (255, 255, 255, 77)},
    {"x": 0, "y": 3, "blur": 8, "color": (0, 0, 0, 204)},
    {"x": 0, "y": 1, "blur": 2, "color": (0, 0, 0, 230)},
]

def _hex_to_rgba(hex_str, alpha=255):
    """Convert hex color to RGBA tuple."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 6:
        r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
        return (r, g, b, alpha)
    elif len(hex_str) == 8:
        r, g, b, a = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16), int(hex_str[6:8], 16)
        return (r, g, b, a)
    return (255, 255, 255, alpha)

def _parse_rgba_str(s):
    """Parse 'rgba(r,g,b,a)' to RGBA tuple."""
    if s.startswith("rgba("):
        parts = s[5:-1].split(",")
        return (int(parts[0]), int(parts[1]), int(parts[2]), int(float(parts[3]) * 255))
    if s.startswith("#"):
        return _hex_to_rgba(s)
    if s == "transparent":
        return (0, 0, 0, 0)
    return (255, 255, 255, 255)

BASE_STYLE = {
    "fontFamily": "Montserrat",
    "fontWeight": 800,
    "lineHeight": 1.05,
    "textTransform": "uppercase",
    "maxWordsPerGroup": 3,
    "yPercent": 68,
    "pillEnabled": False,
    "pillColor": "transparent",
    "pillRadius": 16,
    "textColor": "#FFFFFF",
    "activeColor": "#FFFFFF",
    "dimColor": "#A0A0A0",
    "keywordColors": KEYWORD_COLORS,
    "shadowLayers": SHADOW_DEEP,
    "glowEnabled": False,
    "glowColor": "transparent",
    "glowRadius": 0,
    "activeWordScale": 1.25,
    "textStroke": None,
    "outlineOnly": False,
    "gradientColors": None,
    "backgroundShape": "none",
    "highlightColor": None,
    "underlineColor": None,
    "underlineThickness": 0,
    "stackedLayout": False,
    "shadowExtrude": None,
    "speakerColors": ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
    "animation": "spring",
    "fadeInMs": 80,
    "fadeOutMs": 100,
}

def _preset(overrides):
    p = dict(BASE_STYLE)
    p.update(overrides)
    return p

STYLE_PRESETS = {
    "captions_dynamic": _preset({
        "animation": "spring",
        "pillEnabled": True, "pillColor": "rgba(0,0,0,0.55)",
        "glowEnabled": True, "glowColor": "#FFE600", "glowRadius": 36,
    }),
    "captions_clean": _preset({
        "animation": "pop",
        "shadowLayers": SHADOW_SUBTLE, "activeWordScale": 1.05,
    }),
    "word_pop": _preset({
        "animation": "spring",
        "pillEnabled": True, "pillColor": "rgba(15,15,15,0.82)",
        "glowEnabled": True, "glowColor": "#FF3C64", "glowRadius": 40,
        "activeWordScale": 1.30,
    }),
    "hormozi": _preset({
        "animation": "spring",
        "fontWeight": 900, "pillEnabled": False,
        "glowEnabled": True, "glowColor": "#FFE600", "glowRadius": 48,
        "shadowLayers": SHADOW_GLOW,
        "keywordColors": ["#FFE600"] * 4, "activeWordScale": 1.35,
    }),
    "keyword_pop": _preset({
        "animation": "spring",
        "pillEnabled": True, "pillColor": "rgba(15,15,15,0.75)",
        "glowEnabled": True, "glowColor": "#00DCC8", "glowRadius": 44,
        "activeWordScale": 1.0,
    }),
    "impact": _preset({
        "animation": "typewriter",
        "pillEnabled": True, "pillColor": "rgba(0,0,0,0.85)", "pillRadius": 12,
        "glowEnabled": True, "glowColor": "#3B82F6", "glowRadius": 20,
        "activeWordScale": 1.0,
    }),
    "slide": _preset({
        "animation": "slide",
        "pillEnabled": True, "pillColor": "rgba(20,20,20,0.75)", "pillRadius": 20,
        "activeWordScale": 1.04, "shadowLayers": SHADOW_SUBTLE,
    }),
    "wave": _preset({
        "animation": "wave",
        "pillEnabled": True, "pillColor": "rgba(10,10,10,0.80)",
        "glowEnabled": True, "glowColor": "#A855F7", "glowRadius": 22,
        "activeWordScale": 1.06,
    }),
    "capcut": _preset({
        "animation": "pop",
        "pillEnabled": True, "pillColor": "rgba(0,0,0,0.70)", "pillRadius": 10,
        "activeWordScale": 1.03, "shadowLayers": SHADOW_SUBTLE,
        "textTransform": "none",
    }),
    "cinema": _preset({
        "animation": "slide",
        "fontFamily": "Bebas Neue", "fontWeight": 400,
        "backgroundShape": "none",
        "shadowLayers": [
            {"x": 0, "y": 4, "blur": 14, "color": (30, 60, 120, 153)},
            {"x": 0, "y": 2, "blur": 6, "color": (0, 0, 0, 178)},
            {"x": 0, "y": 1, "blur": 2, "color": (0, 0, 0, 230)},
        ],
    }),
    "news_ticker": _preset({
        "animation": "typewriter",
        "fontFamily": "Oswald", "fontWeight": 700,
        "pillEnabled": True, "pillColor": "#CC0000", "pillRadius": 6,
        "activeWordScale": 1.0, "backgroundShape": "pill",
    }),
    "neon_gradient": _preset({
        "animation": "spring",
        "fontFamily": "Poppins", "fontWeight": 800,
        "pillEnabled": True, "pillColor": "rgba(15,15,15,0.80)",
        "glowEnabled": True, "glowColor": "#00D2FF", "glowRadius": 24,
        "gradientColors": ["#FF3CAC", "#00D2FF"],
    }),
    "sunset_gradient": _preset({
        "animation": "pop",
        "fontWeight": 900,
        "gradientColors": ["#FF6B35", "#FF3C64", "#8B5CF6"],
    }),
    "gold_gradient": _preset({
        "animation": "slide",
        "fontFamily": "Playfair Display", "fontWeight": 700,
        "gradientColors": ["#FFD700", "#FFA000"],
        "backgroundShape": "underline", "underlineColor": "#FFD700", "underlineThickness": 4,
        "textTransform": "none",
    }),
    "outline_bold": _preset({
        "animation": "spring",
        "fontWeight": 900,
        "textStroke": {"width": 3, "color": "#FFFFFF"}, "outlineOnly": True,
    }),
    "outline_neon": _preset({
        "animation": "spring",
        "fontFamily": "Poppins", "fontWeight": 800,
        "glowEnabled": True, "glowColor": "#00DCC8", "glowRadius": 28,
        "textStroke": {"width": 2, "color": "#00DCC8"}, "outlineOnly": True,
    }),
    "handwritten": _preset({
        "animation": "pop",
        "fontFamily": "Permanent Marker", "fontWeight": 400,
        "textTransform": "none",
    }),
    "marker_highlight": _preset({
        "animation": "pop",
        "fontFamily": "Permanent Marker", "fontWeight": 400,
        "textColor": "#1A1A1A", "activeColor": "#1A1A1A", "dimColor": "#333333",
        "backgroundShape": "highlight", "highlightColor": "#FFE600",
        "shadowLayers": SHADOW_SUBTLE, "textTransform": "none",
    }),
    "comic_pop": _preset({
        "animation": "spring",
        "fontFamily": "Bangers", "fontWeight": 400,
        "textColor": "#FFE600", "activeColor": "#FFE600", "dimColor": "#CCBB00",
        "textStroke": {"width": 3, "color": "#000000"}, "activeWordScale": 1.30,
        "keywordColors": ["#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6", "#FFE600"],
    }),
    "meme_bold": _preset({
        "animation": "pop",
        "fontFamily": "Bangers", "fontWeight": 400,
        "textStroke": {"width": 4, "color": "#000000"},
        "keywordColors": ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    }),
    "luxury": _preset({
        "animation": "slide",
        "fontFamily": "Playfair Display", "fontWeight": 700,
        "shadowLayers": SHADOW_SUBTLE,
        "backgroundShape": "underline", "underlineColor": "#D4AF37", "underlineThickness": 3,
        "textTransform": "none",
        "keywordColors": ["#D4AF37", "#FFD700", "#D4AF37", "#FFA000", "#D4AF37", "#FFD700"],
    }),
    "editorial": _preset({
        "animation": "slide",
        "fontFamily": "Playfair Display", "fontWeight": 700,
        "textColor": "#1A1A1A", "activeColor": "#000000", "dimColor": "#444444",
        "pillEnabled": True, "pillColor": "rgba(255,255,255,0.92)", "pillRadius": 12,
        "shadowLayers": [{"x": 0, "y": 1, "blur": 3, "color": (0, 0, 0, 26)}],
        "textTransform": "none",
        "keywordColors": ["#8B5CF6", "#3B82F6", "#059669", "#DC2626", "#D97706", "#7C3AED"],
    }),
    "stacked_bold": _preset({
        "animation": "spring",
        "fontWeight": 900, "stackedLayout": True, "activeWordScale": 1.30,
    }),
    "stacked_color": _preset({
        "animation": "pop",
        "fontFamily": "Poppins", "fontWeight": 800,
        "pillEnabled": True, "pillColor": "rgba(15,15,15,0.80)",
        "glowEnabled": True, "glowColor": "#FF3C64", "glowRadius": 22,
        "stackedLayout": True,
        "keywordColors": ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    }),
    "retro_3d": _preset({
        "animation": "spring",
        "fontFamily": "Bangers", "fontWeight": 400,
        "textColor": "#FFE600", "activeColor": "#FFE600", "dimColor": "#CCBB00",
        "shadowExtrude": {"angle": 135, "distance": 6, "color": "#000000"},
        "keywordColors": ["#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#FFE600", "#3B82F6"],
    }),
    "neon_3d": _preset({
        "animation": "spring",
        "fontFamily": "Space Grotesk", "fontWeight": 700,
        "textColor": "#00DCC8", "activeColor": "#00DCC8", "dimColor": "#008F80",
        "glowEnabled": True, "glowColor": "#00DCC8", "glowRadius": 24,
        "shadowExtrude": {"angle": 135, "distance": 2, "color": "#005F54"},
        "keywordColors": ["#00DCC8", "#3B82F6", "#A855F7", "#00DCC8", "#FFE600", "#FF3C64"],
    }),
    "tech_clean": _preset({
        "animation": "pop",
        "fontFamily": "Space Grotesk", "fontWeight": 500,
        "shadowLayers": SHADOW_SUBTLE,
        "backgroundShape": "underline", "underlineColor": "#00DCC8", "underlineThickness": 3,
        "activeWordScale": 1.04, "textTransform": "none",
        "keywordColors": ["#00DCC8", "#3B82F6", "#A855F7", "#00DCC8", "#FFE600", "#3B82F6"],
    }),
    "tech_glow": _preset({
        "animation": "pop",
        "fontFamily": "Space Grotesk", "fontWeight": 700,
        "textColor": "#00DCC8", "activeColor": "#00FFEE", "dimColor": "#008F80",
        "glowEnabled": True, "glowColor": "#00DCC8", "glowRadius": 22,
        "shadowLayers": SHADOW_GLOW,
        "keywordColors": ["#00DCC8", "#3B82F6", "#A855F7", "#FFE600", "#00DCC8", "#FF3C64"],
    }),
    "minimal_sans": _preset({
        "animation": "pop",
        "fontFamily": "Poppins", "fontWeight": 600,
        "activeWordScale": 1.04, "textTransform": "none",
        "shadowLayers": [{"x": 0, "y": 2, "blur": 6, "color": (0, 0, 0, 128)}],
        "keywordColors": ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    }),
    "minimal_lower": _preset({
        "animation": "slide",
        "fontFamily": "Poppins", "fontWeight": 600,
        "pillEnabled": True, "pillColor": "rgba(10,10,10,0.55)", "pillRadius": 10,
        "activeWordScale": 1.02, "textTransform": "none",
        "shadowLayers": [{"x": 0, "y": 1, "blur": 3, "color": (0, 0, 0, 102)}],
        "keywordColors": ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    }),
}

# Aliases
STYLE_PRESETS["dynamic"] = STYLE_PRESETS["captions_dynamic"]
STYLE_PRESETS["clean"] = STYLE_PRESETS["captions_clean"]

def get_style(name):
    return STYLE_PRESETS.get(name, STYLE_PRESETS["captions_dynamic"])


# ─── Animation Helpers (port of Remotion spring/interpolate/noise) ───────────

def _spring_value(frame, fps, damping=12, stiffness=180, mass=0.8):
    """Simulate damped spring physics (port of Remotion's spring function).
    Returns value 0->1 representing spring progress from rest to target.
    """
    dt = 1.0 / fps
    pos = 0.0
    vel = 0.0
    for _ in range(int(frame)):
        force = -stiffness * (pos - 1.0) - damping * vel
        vel += (force / mass) * dt
        pos += vel * dt
    return max(0.0, min(1.5, pos))  # clamp to avoid extreme overshoot

def _interpolate(val, in_start, in_end, out_start, out_end):
    """Linear interpolation with clamping (port of Remotion's interpolate)."""
    t = (val - in_start) / max(0.0001, in_end - in_start)
    t = max(0.0, min(1.0, t))
    return out_start + t * (out_end - out_start)

def _ease_out_cubic(t):
    """Cubic ease-out (port of Remotion's Easing.out(Easing.cubic))."""
    return 1.0 - (1.0 - max(0.0, min(1.0, t))) ** 3

def _ease_out_back(t, overshoot=1.5):
    """Back ease-out (port of Remotion's Easing.out(Easing.back(1.5)))."""
    t = max(0.0, min(1.0, t))
    c1 = overshoot
    c3 = c1 + 1
    return 1 + c3 * ((t - 1) ** 3) + c1 * ((t - 1) ** 2)

def _smooth_noise(seed, t):
    """Smooth pseudo-random oscillation for organic sway (approximates noise2D)."""
    s = hash(seed) % 1000 / 1000.0
    return (math.sin(t * 2.71 + s * 13.37) * 0.6
            + math.sin(t * 4.33 + s * 7.13) * 0.4)


def _paste_rgba(dst, src, x, y, opacity=1.0):
    """Paste src RGBA numpy array onto dst at (x,y) with opacity, handling bounds."""
    sh, sw = src.shape[:2]
    dh, dw = dst.shape[:2]
    # Clip to bounds
    sx1, sy1 = max(0, -x), max(0, -y)
    dx1, dy1 = max(0, x), max(0, y)
    sx2 = min(sw, dw - dx1 + sx1) if dx1 < dw else sx1
    sy2 = min(sh, dh - dy1 + sy1) if dy1 < dh else sy1
    if sx2 <= sx1 or sy2 <= sy1:
        return
    cw, ch = sx2 - sx1, sy2 - sy1
    dx2, dy2 = dx1 + cw, dy1 + ch
    # Alpha composite
    src_crop = src[sy1:sy2, sx1:sx2].astype(numpy.float32)
    dst_crop = dst[dy1:dy2, dx1:dx2].astype(numpy.float32)
    alpha = (src_crop[:, :, 3:4] / 255.0) * opacity
    dst[dy1:dy2, dx1:dx2] = (src_crop * alpha + dst_crop * (1 - alpha)).astype(numpy.uint8)


def _scale_image(arr, scale):
    """Scale RGBA numpy array by factor, centered."""
    if abs(scale - 1.0) < 0.005:
        return arr
    h, w = arr.shape[:2]
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return cv2.resize(arr, (nw, nh), interpolation=cv2.INTER_LINEAR)


# ─── Auto Font Size (matches CaptionPage.tsx) ───────────────────────────────

def auto_font_size(token_count, scale=1.0):
    sizes = {1: 200, 2: 155, 3: 125, 4: 105, 5: 90}
    base = sizes.get(min(token_count, 5), 90)
    return round(base * scale)


# ─── Word Grouping (matches @remotion/captions createTikTokStyleCaptions) ───

def group_words_into_pages(words, max_gap_ms=400):
    """Group words into caption pages based on timing gaps.

    Matches @remotion/captions combineTokensWithinMilliseconds behavior:
    consecutive words within max_gap_ms are grouped together.
    """
    if not words:
        return []

    pages = []
    current_page = [words[0]]

    for i in range(1, len(words)):
        prev_end = float(current_page[-1].get("end", 0))
        curr_start = float(words[i].get("start", 0))
        gap_ms = (curr_start - prev_end) * 1000

        if gap_ms > max_gap_ms or len(current_page) >= 4:
            pages.append(current_page)
            current_page = [words[i]]
        else:
            current_page.append(words[i])

    if current_page:
        pages.append(current_page)

    return pages


# ─── PNG Caption Renderer ────────────────────────────────────────────────────

def _draw_text_with_effects(img, text, x, y, font, color, style, is_keyword=False):
    """Draw a single word with all style effects (shadow, outline, glow)."""
    draw = ImageDraw.Draw(img)
    color_rgba = _hex_to_rgba(color) if isinstance(color, str) else color

    # 3D extrude shadow
    extrude = style.get("shadowExtrude")
    if extrude:
        angle_rad = math.radians(extrude["angle"])
        ex_color = _hex_to_rgba(extrude["color"]) if isinstance(extrude["color"], str) else extrude["color"]
        for d in range(extrude["distance"], 0, -1):
            dx = round(math.cos(angle_rad) * d)
            dy = round(math.sin(angle_rad) * d)
            draw.text((x + dx, y + dy), text, font=font, fill=ex_color)

    # Shadow layers — blur radius matches CSS text-shadow (CSS blur = ~2σ, Pillow radius ≈ blur)
    for shadow in style.get("shadowLayers", []):
        s_color = shadow["color"]
        if isinstance(s_color, str):
            s_color = _parse_rgba_str(s_color)
        blur_r = shadow.get("blur", 0)
        if blur_r > 0:
            shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            shadow_draw.text((x + shadow["x"], y + shadow["y"]), text, font=font, fill=s_color)
            # CSS text-shadow blur ≈ Pillow GaussianBlur radius (1:1 mapping)
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=max(1, blur_r)))
            img.alpha_composite(shadow_layer)
        else:
            draw.text((x + shadow["x"], y + shadow["y"]), text, font=font, fill=s_color)

    # Glow effect — matches Remotion: applied to keywords that are active or past
    if style.get("glowEnabled") and is_keyword:
        glow_color = _hex_to_rgba(style["glowColor"], 100) if isinstance(style["glowColor"], str) else style["glowColor"]
        # Remotion renders two glow layers: inner (0.18×fontSize) + outer (0.35×fontSize)
        # We approximate with a single pass at the outer radius for similar visual softness
        glow_radius = max(1, style.get("glowRadius", 20))
        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_draw.text((x, y), text, font=font, fill=glow_color)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
        img.alpha_composite(glow_layer)

    # Text stroke/outline
    stroke = style.get("textStroke")
    if stroke:
        stroke_color = _hex_to_rgba(stroke["color"]) if isinstance(stroke["color"], str) else stroke["color"]
        draw = ImageDraw.Draw(img)
        if style.get("outlineOnly"):
            # Outline only: stroke with transparent fill
            draw.text((x, y), text, font=font, fill=(0, 0, 0, 0),
                      stroke_width=stroke["width"], stroke_fill=stroke_color)
            return
        else:
            draw.text((x, y), text, font=font, fill=color_rgba,
                      stroke_width=stroke["width"], stroke_fill=stroke_color)
            return  # stroke_fill already draws both stroke + fill in one call

    # Main text — gradient or solid fill
    gradient_colors = style.get("gradientColors")
    if gradient_colors and len(gradient_colors) >= 2:
        # Render gradient text: draw white text on mask, create gradient, composite
        text_mask = Image.new("L", img.size, 0)
        mask_draw = ImageDraw.Draw(text_mask)
        mask_draw.text((x, y), text, font=font, fill=255)
        # Build vertical or horizontal gradient
        gradient = Image.new("RGBA", img.size, (0, 0, 0, 0))
        c1 = _hex_to_rgba(gradient_colors[0])
        c2 = _hex_to_rgba(gradient_colors[-1])
        for row in range(img.height):
            frac = row / max(1, img.height - 1)
            r = int(c1[0] + (c2[0] - c1[0]) * frac)
            g = int(c1[1] + (c2[1] - c1[1]) * frac)
            b = int(c1[2] + (c2[2] - c1[2]) * frac)
            a = int(c1[3] + (c2[3] - c1[3]) * frac)
            gradient.paste((r, g, b, a), (0, row, img.width, row + 1))
        # Apply text mask to gradient
        gradient.putalpha(text_mask)
        img.alpha_composite(gradient)
    else:
        draw = ImageDraw.Draw(img)
        draw.text((x, y), text, font=font, fill=color_rgba)


def render_caption_state(page_words, active_idx, style, keyword_set,
                         width=1080, height=1920, kw_color_idx=0):
    """Render one caption state (specific word highlighted) as transparent PNG.

    Returns: PIL Image (RGBA)
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    n_words = len(page_words)
    base_size = auto_font_size(n_words)
    font_family = style["fontFamily"]
    font_weight = style["fontWeight"]
    text_transform = style.get("textTransform", "uppercase")
    active_scale = style.get("activeWordScale", 1.25)

    # Build display text and sizes for each word
    word_info = []
    kw_idx = kw_color_idx
    for i, w in enumerate(page_words):
        raw = w.get("punctuated_word") or w.get("word") or ""
        display = raw.upper() if text_transform == "uppercase" else raw

        clean = raw.strip().lower()
        for ch in ".,!?;:'\"\\":
            clean = clean.replace(ch, "")
        is_kw = clean in keyword_set

        is_active = (i == active_idx)
        is_past = (i < active_idx)

        # Font size
        if is_kw:
            word_size = round(base_size * 1.35)
        elif is_active:
            word_size = round(base_size * active_scale)
        else:
            word_size = base_size

        # Color — speaker colors only override activeColor when multiple speakers detected
        if is_active:
            if is_kw:
                kw_colors = style.get("keywordColors", KEYWORD_COLORS)
                color = kw_colors[kw_idx % len(kw_colors)]
            else:
                speaker_idx = w.get("speaker", 0) or 0
                speaker_colors = style.get("speakerColors", [])
                # Only use speaker colors if this word has a non-zero speaker index
                # (indicates multi-speaker content). Otherwise use preset's activeColor.
                if speaker_colors and speaker_idx > 0:
                    color = speaker_colors[speaker_idx % len(speaker_colors)]
                else:
                    color = style.get("activeColor", "#FFFFFF")
        elif is_past:
            if is_kw:
                kw_colors = style.get("keywordColors", KEYWORD_COLORS)
                color = kw_colors[kw_idx % len(kw_colors)]
            else:
                color = style.get("textColor", "#FFFFFF")
        else:
            color = style.get("dimColor", "#A0A0A0")

        if is_kw:
            kw_idx += 1

        font = _get_font(font_family, font_weight if not is_kw else 900, word_size)
        word_info.append({
            "display": display, "font": font, "size": word_size,
            "color": color, "is_kw": is_kw, "is_active": is_active,
        })

    # Measure total layout
    y_center = int(height * style.get("yPercent", 68) / 100)

    # Stacked layout: one word per line, centered (matches Remotion's CSS gap: 2px)
    _WORD_GAP = 2
    line_heights = []
    line_widths = []
    line_bbox_offsets = []  # (bbox_x0, bbox_y0) for positioning correction
    for wi in word_info:
        bbox = wi["font"].getbbox(wi["display"])
        w_px = bbox[2] - bbox[0]
        h_px = bbox[3] - bbox[1]
        line_widths.append(w_px)
        line_heights.append(h_px)
        line_bbox_offsets.append((bbox[0], bbox[1]))

    total_h = sum(line_heights) + max(0, (n_words - 1) * _WORD_GAP)
    start_y = y_center - total_h // 2

    # Pill background
    if style.get("pillEnabled") and style.get("pillColor", "transparent") != "transparent":
        pill_color = _parse_rgba_str(style["pillColor"])
        pill_w = max(line_widths) + round(base_size * 0.32)
        pill_h = total_h + round(base_size * 0.16)
        pill_x = (width - pill_w) // 2
        pill_y = start_y - round(base_size * 0.08)
        pill_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        pill_draw = ImageDraw.Draw(pill_layer)
        pill_draw.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=style.get("pillRadius", 16),
            fill=pill_color,
        )
        img.alpha_composite(pill_layer)

    # Highlight background (marker_highlight style)
    if style.get("backgroundShape") == "highlight" and style.get("highlightColor"):
        hl_color = _hex_to_rgba(style["highlightColor"], 200)
        hl_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        hl_draw = ImageDraw.Draw(hl_layer)
        cy = start_y
        for i, wi in enumerate(word_info):
            if wi["is_active"] or (active_idx >= 0 and i <= active_idx):
                pad_x = round(wi["size"] * 0.1)
                pad_y = round(wi["size"] * 0.04)
                lw = line_widths[i]
                lh = line_heights[i]
                lx = (width - lw) // 2 - pad_x
                hl_draw.rounded_rectangle(
                    [lx, cy - pad_y, lx + lw + pad_x * 2, cy + lh + pad_y],
                    radius=6, fill=hl_color,
                )
            cy += line_heights[i] + _WORD_GAP
        img.alpha_composite(hl_layer)

    # Draw each word — compensate for bbox origin offset for accurate centering
    cur_y = start_y
    for i, wi in enumerate(word_info):
        lw = line_widths[i]
        bx0, by0 = line_bbox_offsets[i]
        x = (width - lw) // 2 - bx0  # compensate for left bearing
        y = cur_y - by0  # compensate for ascender offset
        _draw_text_with_effects(img, wi["display"], x, y, wi["font"],
                                wi["color"], style, is_keyword=wi["is_kw"])
        cur_y += line_heights[i] + _WORD_GAP

    # Underline
    if style.get("backgroundShape") == "underline" and style.get("underlineColor"):
        ul_color = _hex_to_rgba(style["underlineColor"])
        ul_thick = style.get("underlineThickness", 3)
        draw = ImageDraw.Draw(img)
        max_w = max(line_widths)
        ul_x = (width - max_w) // 2
        ul_y = cur_y + 2
        draw.rectangle([ul_x, ul_y, ul_x + max_w, ul_y + ul_thick], fill=ul_color)

    return img


def generate_caption_pngs(projected_words, style_name, keywords, work_dir,
                          width=1080, height=1920):
    """Generate all caption PNG overlays + timing data for FFmpeg.

    Returns list of:
        {"path": str, "start": float, "end": float}
    """
    import time as _time
    t0 = _time.time()

    style = get_style(style_name)
    keyword_set = set()
    for k in (keywords or []):
        clean = k.lower().strip()
        for ch in ".,!?;:'\"\\":
            clean = clean.replace(ch, "")
        if clean:
            keyword_set.add(clean)
    for w in projected_words:
        if w.get("_kw"):
            clean = (w.get("word") or "").lower().strip()
            for ch in ".,!?;:'\"\\":
                clean = clean.replace(ch, "")
            if clean:
                keyword_set.add(clean)

    pages = group_words_into_pages(projected_words, max_gap_ms=400)

    overlays = []
    png_idx = 0
    kw_color_idx = 0

    for page in pages:
        if not page:
            continue
        page_start = float(page[0].get("start", 0))
        page_end = float(page[-1].get("end", 0)) + 0.05

        if page_end - page_start < 0.01:
            continue

        # Count keywords in this page for color cycling
        page_kw_count = 0
        for w in page:
            clean = (w.get("word") or "").lower().strip()
            for ch in ".,!?;:'\"\\":
                clean = clean.replace(ch, "")
            if clean in keyword_set:
                page_kw_count += 1

        # Render one PNG per word-highlight state
        for wi in range(len(page)):
            word_start = float(page[wi].get("start", 0))
            word_end = float(page[wi].get("end", 0)) + 0.05

            # This state starts when word becomes active, ends when next word starts
            state_start = word_start
            if wi + 1 < len(page):
                state_end = float(page[wi + 1].get("start", 0))
            else:
                state_end = page_end

            if state_end - state_start < 0.01:
                continue

            png = render_caption_state(
                page, active_idx=wi, style=style, keyword_set=keyword_set,
                width=width, height=height, kw_color_idx=kw_color_idx,
            )

            png_path = os.path.join(work_dir, f"cap_{png_idx:04d}.png")
            png.save(png_path, "PNG", optimize=False, compress_level=1)
            overlays.append({
                "path": png_path,
                "start": round(state_start, 3),
                "end": round(state_end, 3),
            })
            png_idx += 1

        kw_color_idx += page_kw_count

    elapsed = _time.time() - t0
    print(f"[captions] Rendered {png_idx} PNGs in {elapsed:.2f}s "
          f"({len(pages)} pages, {len(projected_words)} words, style={style_name})",
          flush=True)

    return overlays


def compile_caption_video(overlays, total_duration, work_dir, fps=30, width=1080, height=1920):
    """Compile caption PNG overlays into a single transparent video for FFmpeg overlay.

    Instead of 60-80 separate PNG inputs each with their own overlay filter
    (which creates a massive sequential filter chain), this creates ONE transparent
    video that can be overlaid with a single overlay filter.

    Uses VP8 with yuva420p (alpha channel) encoded via libvpx.
    Falls back to returning the raw overlays if encoding fails.

    Returns either:
        {"type": "video", "path": str} — single transparent video to overlay
        {"type": "pngs", "overlays": list} — fallback to individual PNGs
    """
    import subprocess
    import time as _time

    if not overlays:
        return {"type": "pngs", "overlays": []}

    t0 = _time.time()
    total_frames = max(1, round(total_duration * fps))

    # Build a frame-by-frame PNG sequence: for each frame, determine which
    # caption PNG (if any) should be shown. Frames with no caption get a
    # transparent blank.
    blank_path = os.path.join(work_dir, "cap_blank.png")
    blank = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    blank.save(blank_path, "PNG", optimize=False)

    # Create concat demuxer file: each entry is a PNG displayed for its duration
    concat_path = os.path.join(work_dir, "cap_concat.txt")
    entries = []

    # Sort overlays by start time
    sorted_ovs = sorted(overlays, key=lambda o: o["start"])

    # Fill gaps between overlays with blank frames
    current_t = 0.0
    for ov in sorted_ovs:
        gap = ov["start"] - current_t
        if gap > 0.001:
            # Blank for the gap
            entries.append(f"file '{blank_path}'\nduration {gap:.6f}")
        dur = ov["end"] - ov["start"]
        if dur > 0.001:
            entries.append(f"file '{ov['path']}'\nduration {dur:.6f}")
            current_t = ov["end"]
        else:
            current_t = ov["start"]

    # Trailing blank after last caption
    remaining = total_duration - current_t
    if remaining > 0.001:
        entries.append(f"file '{blank_path}'\nduration {remaining:.6f}")
    # concat demuxer needs last file repeated without duration
    entries.append(f"file '{blank_path}'")

    with open(concat_path, "w") as f:
        f.write("\n".join(entries))

    caption_video_path = os.path.join(work_dir, "captions_overlay.webm")
    n_threads = os.cpu_count() or 8

    # Encode transparent caption video: VP9 with alpha, constant quality
    # VP9 has better alpha fidelity than VP8. CRF 10 = near-lossless text edges.
    # -row-mt 1 enables row-based multithreading for parallel encoding.
    cmd = [
        "ffmpeg", "-y", "-threads", str(n_threads),
        "-f", "concat", "-safe", "0", "-i", concat_path,
        "-vf", f"fps={fps},format=yuva420p",
        "-c:v", "libvpx-vp9",
        "-auto-alt-ref", "0",    # required for alpha channel
        "-deadline", "realtime", # fastest VP9 mode
        "-cpu-used", "8",        # max speed for realtime
        "-row-mt", "1",          # parallel row encoding
        "-crf", "10",            # near-lossless quality (text edges)
        "-b:v", "0",             # pure CRF mode (no bitrate cap)
        "-t", f"{total_duration:.3f}",
        caption_video_path,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and os.path.exists(caption_video_path):
            elapsed = _time.time() - t0
            size_kb = os.path.getsize(caption_video_path) / 1024
            print(f"[captions] Compiled {len(overlays)} PNGs → single overlay video "
                  f"({size_kb:.0f}KB) in {elapsed:.2f}s", flush=True)
            return {"type": "video", "path": caption_video_path}
        else:
            print(f"[captions] Caption video encode failed — falling back to PNG overlays", flush=True)
            if result.stderr:
                print(f"[captions] stderr: {result.stderr[-500:]}", flush=True)
            return {"type": "pngs", "overlays": overlays}
    except Exception as e:
        print(f"[captions] Caption video encode error: {e} — falling back to PNG overlays", flush=True)
        return {"type": "pngs", "overlays": overlays}


# ─── Frame-by-frame Animated Caption Video (matches Remotion CaptionPage.tsx) ─

def generate_animated_caption_video(projected_words, style_name, keywords, work_dir,
                                     total_duration, fps=30, width=1080, height=1920):
    """Generate frame-by-frame animated caption overlay video matching Remotion quality.

    Animations ported from CaptionPage.tsx:
    - Page entrance: spring/pop/slide/wave/typewriter
    - Page fade in (80ms) / fade out (100ms)
    - Organic sway (noise-based position drift, +/-2px X, +/-1.5px Y)
    - Per-word active spring scale (0.88 -> activeScale, damping=14, stiffness=300, mass=0.5)
    - Wave: staggered word entrance with back easing
    - Typewriter: words appear at their start time

    Returns: {"type": "video", "path": str} or {"type": "error"}
    """
    import subprocess
    import time as _time

    try:
        t0 = _time.time()

        if not projected_words or total_duration <= 0:
            return {"type": "error"}

        style = get_style(style_name)
        animation_type = style.get("animation", "spring")
        fade_in_s = style.get("fadeInMs", 80) / 1000.0
        fade_out_s = style.get("fadeOutMs", 100) / 1000.0
        active_scale = style.get("activeWordScale", 1.25)
        font_family = style["fontFamily"]
        font_weight = style["fontWeight"]
        text_transform = style.get("textTransform", "uppercase")

        # Build keyword set
        keyword_set = set()
        for k in (keywords or []):
            clean = k.lower().strip()
            for ch in ".,!?;:'\"\\":
                clean = clean.replace(ch, "")
            if clean:
                keyword_set.add(clean)
        for w in projected_words:
            if w.get("_kw"):
                clean = (w.get("word") or "").lower().strip()
                for ch in ".,!?;:'\"\\":
                    clean = clean.replace(ch, "")
                if clean:
                    keyword_set.add(clean)

        # Group words into pages
        pages = group_words_into_pages(projected_words, max_gap_ms=400)
        if not pages:
            return {"type": "error"}

        PAD = 100  # padding for shadow/glow spread

        # ── Pre-render phase ──────────────────────────────────────────────
        t_prerender = _time.time()

        # For each page, pre-render word images in 3 states: future, active, past
        page_data = []
        kw_color_idx = 0

        for page in pages:
            if not page:
                continue
            page_start = float(page[0].get("start", 0))
            page_end = float(page[-1].get("end", 0)) + 0.05
            if page_end - page_start < 0.01:
                continue

            n_words = len(page)
            base_size = auto_font_size(n_words)

            word_data_list = []
            page_kw_idx = kw_color_idx

            for wi, w in enumerate(page):
                raw = w.get("punctuated_word") or w.get("word") or ""
                display = raw.upper() if text_transform == "uppercase" else raw
                if not display.strip():
                    display = " "

                clean_w = raw.strip().lower()
                for ch in ".,!?;:'\"\\":
                    clean_w = clean_w.replace(ch, "")
                is_kw = clean_w in keyword_set

                # Determine colors for each state
                kw_colors = style.get("keywordColors", KEYWORD_COLORS)
                if is_kw:
                    kw_c = kw_colors[page_kw_idx % len(kw_colors)]
                    page_kw_idx += 1

                # Future state: dim color, base size
                future_color = style.get("dimColor", "#A0A0A0")
                future_size = base_size

                # Active state: active/keyword color, scaled size
                if is_kw:
                    active_color = kw_c
                    active_size = round(base_size * 1.35)
                else:
                    speaker_idx = w.get("speaker", 0) or 0
                    speaker_colors = style.get("speakerColors", [])
                    if speaker_colors and speaker_idx > 0:
                        active_color = speaker_colors[speaker_idx % len(speaker_colors)]
                    else:
                        active_color = style.get("activeColor", "#FFFFFF")
                    active_size = round(base_size * active_scale)

                # Past state: text/keyword color, base size
                if is_kw:
                    past_color = kw_c
                else:
                    past_color = style.get("textColor", "#FFFFFF")
                past_size = base_size

                # Render 3 versions of this word
                states = {}
                for state_name, s_color, s_size in [
                    ("future", future_color, future_size),
                    ("active", active_color, active_size),
                    ("past", past_color, past_size),
                ]:
                    font = _get_font(font_family, font_weight if not is_kw else 900, s_size)
                    bbox = font.getbbox(display)
                    w_px = bbox[2] - bbox[0]
                    h_px = bbox[3] - bbox[1]
                    if w_px < 1 or h_px < 1:
                        w_px, h_px = max(w_px, 1), max(h_px, 1)

                    word_img = Image.new("RGBA", (w_px + PAD * 2, h_px + PAD * 2), (0, 0, 0, 0))
                    _draw_text_with_effects(
                        word_img, display,
                        PAD - bbox[0], PAD - bbox[1],
                        font, s_color, style, is_keyword=is_kw,
                    )
                    word_arr = numpy.array(word_img)
                    states[state_name] = {
                        "arr": word_arr,
                        "w_px": w_px,
                        "h_px": h_px,
                        "bbox_x0": bbox[0],
                        "bbox_y0": bbox[1],
                    }

                word_data_list.append({
                    "display": display,
                    "states": states,
                    "is_kw": is_kw,
                    "start": float(w.get("start", 0)),
                    "end": float(w.get("end", 0)),
                    "base_size": base_size,
                })

            # Count keywords for color cycling
            page_kw_count = sum(1 for wd in word_data_list if wd["is_kw"])
            kw_color_idx += page_kw_count

            # Compute layout positions (stacked, one word per line, centered)
            _WORD_GAP = 2
            y_center = int(height * style.get("yPercent", 68) / 100)

            # Use base size metrics for layout (active size words will be scaled)
            layout_heights = []
            layout_widths = []
            for wd in word_data_list:
                # Use future state for base layout (unscaled)
                layout_widths.append(wd["states"]["future"]["w_px"])
                layout_heights.append(wd["states"]["future"]["h_px"])

            total_h = sum(layout_heights) + max(0, (n_words - 1) * _WORD_GAP)
            start_y = y_center - total_h // 2

            # Compute center-x, top-y for each word (layout position)
            word_positions = []
            cur_y = start_y
            for i, wd in enumerate(word_data_list):
                lw = layout_widths[i]
                cx = width // 2  # center x
                ty = cur_y  # top y
                word_positions.append((cx, ty, lw, layout_heights[i]))
                cur_y += layout_heights[i] + _WORD_GAP

            # Pre-render pill background as numpy array (if needed)
            pill_arr = None
            if style.get("pillEnabled") and style.get("pillColor", "transparent") != "transparent":
                pill_color = _parse_rgba_str(style["pillColor"])
                pill_w = max(layout_widths) + round(base_size * 0.32)
                pill_h = total_h + round(base_size * 0.16)
                pill_x = (width - pill_w) // 2
                pill_y = start_y - round(base_size * 0.08)
                pill_img = Image.new("RGBA", (pill_w + 4, pill_h + 4), (0, 0, 0, 0))
                pill_draw = ImageDraw.Draw(pill_img)
                pill_draw.rounded_rectangle(
                    [0, 0, pill_w, pill_h],
                    radius=style.get("pillRadius", 16),
                    fill=pill_color,
                )
                pill_arr = numpy.array(pill_img)
                pill_pos = (pill_x, pill_y)

            # Pre-render highlight backgrounds for each word (marker_highlight)
            highlight_arrs = []
            if style.get("backgroundShape") == "highlight" and style.get("highlightColor"):
                hl_color = _hex_to_rgba(style["highlightColor"], 200)
                for i, wd in enumerate(word_data_list):
                    pad_x = round(wd["base_size"] * 0.1)
                    pad_y = round(wd["base_size"] * 0.04)
                    lw = layout_widths[i]
                    lh = layout_heights[i]
                    hl_img = Image.new("RGBA", (lw + pad_x * 2 + 4, lh + pad_y * 2 + 4), (0, 0, 0, 0))
                    hl_draw = ImageDraw.Draw(hl_img)
                    hl_draw.rounded_rectangle(
                        [0, 0, lw + pad_x * 2, lh + pad_y * 2],
                        radius=6, fill=hl_color,
                    )
                    highlight_arrs.append({
                        "arr": numpy.array(hl_img),
                        "offset_x": -pad_x,
                        "offset_y": -pad_y,
                    })

            # Pre-render underline
            underline_arr = None
            if style.get("backgroundShape") == "underline" and style.get("underlineColor"):
                ul_color = _hex_to_rgba(style["underlineColor"])
                ul_thick = style.get("underlineThickness", 3)
                max_w = max(layout_widths) if layout_widths else 0
                if max_w > 0:
                    ul_img = Image.new("RGBA", (max_w + 4, ul_thick + 4), (0, 0, 0, 0))
                    ul_draw = ImageDraw.Draw(ul_img)
                    ul_draw.rectangle([0, 0, max_w, ul_thick], fill=ul_color)
                    underline_arr = numpy.array(ul_img)
                    underline_x = (width - max_w) // 2
                    underline_y = cur_y + 2  # cur_y is after last word

            page_data.append({
                "words": word_data_list,
                "positions": word_positions,
                "page_start": page_start,
                "page_end": page_end,
                "pill_arr": pill_arr,
                "pill_pos": pill_pos if pill_arr is not None else None,
                "highlight_arrs": highlight_arrs,
                "underline_arr": underline_arr,
                "underline_x": underline_x if underline_arr is not None else 0,
                "underline_y": underline_y if underline_arr is not None else 0,
                "layout_widths": layout_widths,
                "layout_heights": layout_heights,
                "base_size": base_size,
            })

        prerender_elapsed = _time.time() - t_prerender
        print(f"[captions-anim] Pre-rendered {sum(len(p['words']) for p in page_data)} words "
              f"x3 states in {prerender_elapsed:.2f}s", flush=True)

        # ── Frame generation + VP9 encoding ───────────────────────────────
        t_frames = _time.time()
        total_frames = max(1, round(total_duration * fps))

        output_path = os.path.join(work_dir, "captions_animated.webm")
        n_threads = os.cpu_count() or 8

        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgba",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-i", "pipe:0",
            "-c:v", "libvpx-vp9",
            "-auto-alt-ref", "0",
            "-deadline", "realtime",
            "-cpu-used", "8",
            "-row-mt", "1",
            "-threads", str(n_threads),
            "-crf", "10",
            "-b:v", "0",
            "-pix_fmt", "yuva420p",
            "-t", f"{total_duration:.3f}",
            output_path,
        ]

        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

        blank = numpy.zeros((height, width, 4), dtype=numpy.uint8)
        blank_bytes = blank.tobytes()

        # Spring value cache to avoid recomputing converged springs
        _spring_cache = {}

        def _cached_spring(frame_int, fps_val, damping, stiffness, mass):
            key = (frame_int, fps_val, damping, stiffness, mass)
            if key not in _spring_cache:
                _spring_cache[key] = _spring_value(frame_int, fps_val, damping, stiffness, mass)
            return _spring_cache[key]

        for fi in range(total_frames):
            t = fi / fps

            # Check if any page is visible at this time
            any_visible = False
            for pd in page_data:
                if pd["page_start"] <= t < pd["page_end"]:
                    any_visible = True
                    break

            if not any_visible:
                proc.stdin.write(blank_bytes)
                continue

            frame_arr = blank.copy()

            for pd in page_data:
                pg_start = pd["page_start"]
                pg_end = pd["page_end"]

                if t < pg_start or t >= pg_end:
                    continue

                page_age = t - pg_start
                page_age_frames = int(page_age * fps)
                page_remaining = pg_end - t

                # ── Page fade (opacity) ──
                fade_in = min(1.0, page_age / fade_in_s) if fade_in_s > 0 else 1.0
                fade_out = min(1.0, page_remaining / fade_out_s) if fade_out_s > 0 else 1.0
                page_opacity = fade_in * fade_out

                if page_opacity < 0.01:
                    continue

                # ── Page entrance animation ──
                page_scale = 1.0
                page_translate_y = 0.0

                if animation_type == "spring":
                    sp = _cached_spring(page_age_frames, fps, 12, 180, 0.8)
                    page_scale = _interpolate(sp, 0, 1, 0.3, 1.0)
                elif animation_type == "pop":
                    sp = _cached_spring(page_age_frames, fps, 18, 260, 0.8)
                    page_scale = _interpolate(sp, 0, 1, 0.3, 1.0)
                elif animation_type == "slide":
                    progress = _ease_out_cubic(min(1.0, page_age / 0.15))
                    page_scale = _interpolate(progress, 0, 1, 0.8, 1.0)
                    page_translate_y = _interpolate(progress, 0, 1, 40.0, 0.0)
                elif animation_type in ("wave", "typewriter"):
                    page_scale = 1.0  # per-word animation instead

                # ── Organic sway ──
                sway_x = _smooth_noise("sway-x", fi * 0.008) * 2.0
                sway_y = _smooth_noise("sway-y", fi * 0.008) * 1.5

                # ── Render pill background ──
                if pd["pill_arr"] is not None:
                    _paste_rgba(frame_arr, pd["pill_arr"],
                                int(pd["pill_pos"][0] + sway_x),
                                int(pd["pill_pos"][1] + page_translate_y + sway_y),
                                page_opacity)

                # ── Render each word ──
                words = pd["words"]
                positions = pd["positions"]

                for wi, wd in enumerate(words):
                    cx, ty, lw, lh = positions[wi]

                    # Determine word state
                    w_start = wd["start"]
                    w_end = wd["end"]

                    if t >= w_start and t < w_end + 0.05:
                        state = "active"
                    elif t >= w_end + 0.05:
                        state = "past"
                    else:
                        state = "future"

                    # Per-word animation
                    word_scale = 1.0
                    word_opacity = 1.0

                    if animation_type == "wave":
                        # Staggered entrance per word with back easing
                        word_delay = wi * 0.06  # 60ms stagger per word
                        word_age = page_age - word_delay
                        if word_age < 0:
                            word_opacity = 0.0
                            word_scale = 0.5
                        else:
                            progress = min(1.0, word_age / 0.2)
                            eased = _ease_out_back(progress, 1.5)
                            word_scale = _interpolate(eased, 0, 1, 0.5, 1.0)
                            word_opacity = _interpolate(progress, 0, 1, 0.0, 1.0)
                    elif animation_type == "typewriter":
                        # Words appear at their start time
                        if t < w_start:
                            word_opacity = 0.0

                    # Active word spring scale
                    if state == "active":
                        frames_since_active = int((t - w_start) * fps)
                        sp = _cached_spring(max(0, frames_since_active), fps, 14, 300, 0.5)
                        word_scale *= _interpolate(sp, 0, 1, 0.88, active_scale)

                    # Get word image for current state
                    state_data = wd["states"][state]
                    word_arr = state_data["arr"]

                    # Highlight background (marker_highlight)
                    if pd["highlight_arrs"] and (state == "active" or state == "past"):
                        hl = pd["highlight_arrs"][wi]
                        hl_x = int(cx - lw // 2 + hl["offset_x"] + sway_x)
                        hl_y = int(ty + hl["offset_y"] + page_translate_y + sway_y)
                        _paste_rgba(frame_arr, hl["arr"], hl_x, hl_y, page_opacity * word_opacity)

                    # Apply word scale (page_scale * word_scale)
                    total_scale = page_scale * word_scale
                    if abs(total_scale - 1.0) > 0.005:
                        word_arr = _scale_image(word_arr, total_scale)

                    # Position: center word image at the layout position
                    # The word image has PAD pixels of padding, and the text is at PAD offset
                    img_h, img_w = word_arr.shape[:2]

                    # Place centered on the layout line
                    place_x = int(cx - img_w // 2 + sway_x)
                    place_y = int(ty + lh // 2 - img_h // 2 + page_translate_y + sway_y)

                    final_opacity = page_opacity * word_opacity
                    if final_opacity > 0.01:
                        _paste_rgba(frame_arr, word_arr, place_x, place_y, final_opacity)

                # ── Underline ──
                if pd["underline_arr"] is not None:
                    _paste_rgba(frame_arr, pd["underline_arr"],
                                int(pd["underline_x"] + sway_x),
                                int(pd["underline_y"] + page_translate_y + sway_y),
                                page_opacity)

            try:
                proc.stdin.write(frame_arr.tobytes())
            except (BrokenPipeError, OSError):
                print(f"[captions-anim] FFmpeg pipe broke at frame {fi}/{total_frames}", flush=True)
                break

        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.stdin = None  # prevent communicate() from trying to flush closed stdin
        _, stderr = proc.communicate(timeout=60)

        frames_elapsed = _time.time() - t_frames
        total_elapsed = _time.time() - t0

        if proc.returncode == 0 and os.path.exists(output_path):
            size_kb = os.path.getsize(output_path) / 1024
            print(f"[captions-anim] Generated {total_frames} frames in {frames_elapsed:.2f}s, "
                  f"pre-render {prerender_elapsed:.2f}s, total {total_elapsed:.2f}s "
                  f"({size_kb:.0f}KB, style={style_name}, anim={animation_type})", flush=True)
            return {"type": "video", "path": output_path}
        else:
            print(f"[captions-anim] VP9 encode failed (rc={proc.returncode})", flush=True)
            if stderr:
                print(f"[captions-anim] stderr: {stderr.decode('utf-8', errors='replace')[-500:]}", flush=True)
            return {"type": "error"}

    except Exception as e:
        import traceback
        print(f"[captions-anim] Error: {e}", flush=True)
        traceback.print_exc()
        return {"type": "error"}
