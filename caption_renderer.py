"""
Python-native caption renderer — replaces Remotion's Chrome-based rendering.

Generates transparent PNG overlays for each caption state (word highlight change),
then FFmpeg composites them in the existing single-pass render.

All 30+ style presets from Remotion are cached here as Python dicts.
Rendering 60-80 PNGs with Pillow takes <0.5 seconds vs 40-130s in Chrome.
"""

import os
import math
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
}

def _preset(overrides):
    p = dict(BASE_STYLE)
    p.update(overrides)
    return p

STYLE_PRESETS = {
    "captions_dynamic": _preset({
        "pillEnabled": True, "pillColor": "rgba(0,0,0,0.55)",
        "glowEnabled": True, "glowColor": "#FFE600", "glowRadius": 36,
    }),
    "captions_clean": _preset({
        "shadowLayers": SHADOW_SUBTLE, "activeWordScale": 1.05,
    }),
    "word_pop": _preset({
        "pillEnabled": True, "pillColor": "rgba(15,15,15,0.82)",
        "glowEnabled": True, "glowColor": "#FF3C64", "glowRadius": 40,
        "activeWordScale": 1.30,
    }),
    "hormozi": _preset({
        "fontWeight": 900, "pillEnabled": False,
        "glowEnabled": True, "glowColor": "#FFE600", "glowRadius": 48,
        "shadowLayers": SHADOW_GLOW,
        "keywordColors": ["#FFE600"] * 4, "activeWordScale": 1.35,
    }),
    "keyword_pop": _preset({
        "pillEnabled": True, "pillColor": "rgba(15,15,15,0.75)",
        "glowEnabled": True, "glowColor": "#00DCC8", "glowRadius": 44,
        "activeWordScale": 1.0,
    }),
    "impact": _preset({
        "pillEnabled": True, "pillColor": "rgba(0,0,0,0.85)", "pillRadius": 12,
        "glowEnabled": True, "glowColor": "#3B82F6", "glowRadius": 20,
        "activeWordScale": 1.0,
    }),
    "slide": _preset({
        "pillEnabled": True, "pillColor": "rgba(20,20,20,0.75)", "pillRadius": 20,
        "activeWordScale": 1.04, "shadowLayers": SHADOW_SUBTLE,
    }),
    "wave": _preset({
        "pillEnabled": True, "pillColor": "rgba(10,10,10,0.80)",
        "glowEnabled": True, "glowColor": "#A855F7", "glowRadius": 22,
        "activeWordScale": 1.06,
    }),
    "capcut": _preset({
        "pillEnabled": True, "pillColor": "rgba(0,0,0,0.70)", "pillRadius": 10,
        "activeWordScale": 1.03, "shadowLayers": SHADOW_SUBTLE,
        "textTransform": "none",
    }),
    "cinema": _preset({
        "fontFamily": "Bebas Neue", "fontWeight": 400,
        "backgroundShape": "none",
        "shadowLayers": [
            {"x": 0, "y": 4, "blur": 14, "color": (30, 60, 120, 153)},
            {"x": 0, "y": 2, "blur": 6, "color": (0, 0, 0, 178)},
            {"x": 0, "y": 1, "blur": 2, "color": (0, 0, 0, 230)},
        ],
    }),
    "news_ticker": _preset({
        "fontFamily": "Oswald", "fontWeight": 700,
        "pillEnabled": True, "pillColor": "#CC0000", "pillRadius": 6,
        "activeWordScale": 1.0, "backgroundShape": "pill",
    }),
    "neon_gradient": _preset({
        "fontFamily": "Poppins", "fontWeight": 800,
        "pillEnabled": True, "pillColor": "rgba(15,15,15,0.80)",
        "glowEnabled": True, "glowColor": "#00D2FF", "glowRadius": 24,
        "gradientColors": ["#FF3CAC", "#00D2FF"],
    }),
    "sunset_gradient": _preset({
        "fontWeight": 900,
        "gradientColors": ["#FF6B35", "#FF3C64", "#8B5CF6"],
    }),
    "gold_gradient": _preset({
        "fontFamily": "Playfair Display", "fontWeight": 700,
        "gradientColors": ["#FFD700", "#FFA000"],
        "backgroundShape": "underline", "underlineColor": "#FFD700", "underlineThickness": 4,
        "textTransform": "none",
    }),
    "outline_bold": _preset({
        "fontWeight": 900,
        "textStroke": {"width": 3, "color": "#FFFFFF"}, "outlineOnly": True,
    }),
    "outline_neon": _preset({
        "fontFamily": "Poppins", "fontWeight": 800,
        "glowEnabled": True, "glowColor": "#00DCC8", "glowRadius": 28,
        "textStroke": {"width": 2, "color": "#00DCC8"}, "outlineOnly": True,
    }),
    "handwritten": _preset({
        "fontFamily": "Permanent Marker", "fontWeight": 400,
        "textTransform": "none",
    }),
    "marker_highlight": _preset({
        "fontFamily": "Permanent Marker", "fontWeight": 400,
        "textColor": "#1A1A1A", "activeColor": "#1A1A1A", "dimColor": "#333333",
        "backgroundShape": "highlight", "highlightColor": "#FFE600",
        "shadowLayers": SHADOW_SUBTLE, "textTransform": "none",
    }),
    "comic_pop": _preset({
        "fontFamily": "Bangers", "fontWeight": 400,
        "textColor": "#FFE600", "activeColor": "#FFE600", "dimColor": "#CCBB00",
        "textStroke": {"width": 3, "color": "#000000"}, "activeWordScale": 1.30,
        "keywordColors": ["#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6", "#FFE600"],
    }),
    "meme_bold": _preset({
        "fontFamily": "Bangers", "fontWeight": 400,
        "textStroke": {"width": 4, "color": "#000000"},
        "keywordColors": ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    }),
    "luxury": _preset({
        "fontFamily": "Playfair Display", "fontWeight": 700,
        "shadowLayers": SHADOW_SUBTLE,
        "backgroundShape": "underline", "underlineColor": "#D4AF37", "underlineThickness": 3,
        "textTransform": "none",
        "keywordColors": ["#D4AF37", "#FFD700", "#D4AF37", "#FFA000", "#D4AF37", "#FFD700"],
    }),
    "editorial": _preset({
        "fontFamily": "Playfair Display", "fontWeight": 700,
        "textColor": "#1A1A1A", "activeColor": "#000000", "dimColor": "#444444",
        "pillEnabled": True, "pillColor": "rgba(255,255,255,0.92)", "pillRadius": 12,
        "shadowLayers": [{"x": 0, "y": 1, "blur": 3, "color": (0, 0, 0, 26)}],
        "textTransform": "none",
        "keywordColors": ["#8B5CF6", "#3B82F6", "#059669", "#DC2626", "#D97706", "#7C3AED"],
    }),
    "stacked_bold": _preset({
        "fontWeight": 900, "stackedLayout": True, "activeWordScale": 1.30,
    }),
    "stacked_color": _preset({
        "fontFamily": "Poppins", "fontWeight": 800,
        "pillEnabled": True, "pillColor": "rgba(15,15,15,0.80)",
        "glowEnabled": True, "glowColor": "#FF3C64", "glowRadius": 22,
        "stackedLayout": True,
        "keywordColors": ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    }),
    "retro_3d": _preset({
        "fontFamily": "Bangers", "fontWeight": 400,
        "textColor": "#FFE600", "activeColor": "#FFE600", "dimColor": "#CCBB00",
        "shadowExtrude": {"angle": 135, "distance": 6, "color": "#000000"},
        "keywordColors": ["#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#FFE600", "#3B82F6"],
    }),
    "neon_3d": _preset({
        "fontFamily": "Space Grotesk", "fontWeight": 700,
        "textColor": "#00DCC8", "activeColor": "#00DCC8", "dimColor": "#008F80",
        "glowEnabled": True, "glowColor": "#00DCC8", "glowRadius": 24,
        "shadowExtrude": {"angle": 135, "distance": 2, "color": "#005F54"},
        "keywordColors": ["#00DCC8", "#3B82F6", "#A855F7", "#00DCC8", "#FFE600", "#FF3C64"],
    }),
    "tech_clean": _preset({
        "fontFamily": "Space Grotesk", "fontWeight": 500,
        "shadowLayers": SHADOW_SUBTLE,
        "backgroundShape": "underline", "underlineColor": "#00DCC8", "underlineThickness": 3,
        "activeWordScale": 1.04, "textTransform": "none",
        "keywordColors": ["#00DCC8", "#3B82F6", "#A855F7", "#00DCC8", "#FFE600", "#3B82F6"],
    }),
    "tech_glow": _preset({
        "fontFamily": "Space Grotesk", "fontWeight": 700,
        "textColor": "#00DCC8", "activeColor": "#00FFEE", "dimColor": "#008F80",
        "glowEnabled": True, "glowColor": "#00DCC8", "glowRadius": 22,
        "shadowLayers": SHADOW_GLOW,
        "keywordColors": ["#00DCC8", "#3B82F6", "#A855F7", "#FFE600", "#00DCC8", "#FF3C64"],
    }),
    "minimal_sans": _preset({
        "fontFamily": "Poppins", "fontWeight": 600,
        "activeWordScale": 1.04, "textTransform": "none",
        "shadowLayers": [{"x": 0, "y": 2, "blur": 6, "color": (0, 0, 0, 128)}],
        "keywordColors": ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    }),
    "minimal_lower": _preset({
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
