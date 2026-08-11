"""caption_translate.py — caption translation, dark end-to-end
(LANE-SEAM build phase, 2026-08-11). DARK behind PROMPTLY_CAPTION_TRANSLATE.

THE DEMAND [MEASURED — JUDGE 2026-08-10]: 58 explicit asks (31 "translate" +
27 "captions in <language>"), and the captions_language class drops silently
~46% of the time. Today no translation path exists at all.

THE DESIGN — a DISPLAY-layer transform at the caption-page seam:
- The ask is parsed deterministically from vibe+change_request into a target
  language (high-precision, negation-guarded — the caption-text-override
  parser's fabrication lesson applied).
- Translation happens AFTER pagination, per page: page boundaries, startMs
  and durationMs are PRESERVED EXACTLY (the never-early and clip/position
  boundary laws are untouched); only the words inside each page change, with
  token times redistributed proportionally as INTEGERS (the strict-int
  fromMs/toMs law — a float kills every caption render).
- Cuts, the transcript, audio, word-index spaces: untouched. This translates
  what the captions DISPLAY, nothing else.

THE FULL-OR-NOTHING LAW (patchy captions are a DEFECT, Zac 2026-07-28):
translate_pages replaces EVERY page or NO page. Any failure — the model call
raising, a length mismatch, an empty translation — returns the ORIGINAL
pages unchanged with a failure meta the caller ledgers loudly. The user
never sees a half-translated caption track.

The model call itself is INJECTED (translate_fn) — this module stays pure
and unit-certifiable with zero network. The handler touchpoint builds the
real Gemini closure; flag off ⇒ the transient key is never set ⇒ this module
is never consulted at render time.

Python 3.9-compatible.
"""

import os
import re
from typing import Callable, Dict, List, Optional, Tuple

TRANSIENT_KEY = "_caption_translate_target"

# Canonical language names the parser may emit — a whitelist so a stray noun
# can never become a "language" (fabrication guard). Keys are match tokens,
# values the canonical name handed to the translator.
_LANGUAGES = {
    "english": "English", "spanish": "Spanish", "hindi": "Hindi",
    "arabic": "Arabic", "french": "French", "german": "German",
    "portuguese": "Portuguese", "urdu": "Urdu", "russian": "Russian",
    "japanese": "Japanese", "korean": "Korean", "chinese": "Chinese",
    "mandarin": "Chinese", "italian": "Italian", "turkish": "Turkish",
    "indonesian": "Indonesian", "vietnamese": "Vietnamese",
    "tagalog": "Filipino", "filipino": "Filipino", "punjabi": "Punjabi",
    "tamil": "Tamil", "telugu": "Telugu", "bengali": "Bengali",
    "gujarati": "Gujarati", "marathi": "Marathi", "thai": "Thai",
    "polish": "Polish", "dutch": "Dutch", "ukrainian": "Ukrainian",
    "romanian": "Romanian", "greek": "Greek", "hebrew": "Hebrew",
    "swahili": "Swahili", "malay": "Malay", "farsi": "Persian",
    "persian": "Persian",
}

_LANG_ALT = "|".join(sorted(_LANGUAGES))

# Two families, mirroring the caption-text-override precision split:
#   1. translate … (in)to <lang> — the verb itself carries the intent.
#   2. <lang> captions/subtitles, or captions/subtitles in <lang> — the
#      caption noun is REQUIRED so "speak hindi in the video" never matches.
_PAT_TRANSLATE = re.compile(
    r"\btranslat\w*\b[^.!?\n]{0,60}?\b(?:in)?to\s+(?P<lang1>" + _LANG_ALT + r")\b",
    re.IGNORECASE)
_PAT_CAPTIONS_IN = re.compile(
    r"\b(?:captions?|subtitles?|subs)\b[^.!?\n]{0,40}?\bin\s+(?P<lang2>"
    + _LANG_ALT + r")\b"
    r"|\b(?P<lang3>" + _LANG_ALT + r")\s+(?:captions?|subtitles?|subs)\b",
    re.IGNORECASE)
_NEG_RE = re.compile(
    r"\b(?:no|without|don'?t|dont|remove|not)\b[^.!?\n]{0,24}$", re.IGNORECASE)


def enabled(input_data=None):
    """DARK by default. PROMPTLY_CAPTION_TRANSLATE=1 arms parsing globally;
    input_data.caption_translate_test is the per-job override for the
    pre-flip cert (burned_text_test pattern — inert for real traffic)."""
    if input_data and input_data.get("caption_translate_test"):
        return True
    return os.environ.get("PROMPTLY_CAPTION_TRANSLATE", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def parse_target_language(text):
    """The explicit caption-translation ask → canonical language name, or
    None. Whitelist-bound, negation-guarded, caption-noun-required for the
    bare '<lang> captions' family."""
    t = str(text or "")
    for pat in (_PAT_TRANSLATE, _PAT_CAPTIONS_IN):
        for m in pat.finditer(t):
            if _NEG_RE.search(t[:m.start()]):
                continue
            lang = (m.groupdict().get("lang1") or m.groupdict().get("lang2")
                    or m.groupdict().get("lang3") or "")
            canon = _LANGUAGES.get(lang.lower())
            if canon:
                return canon
    return None


def _rebuild_tokens(page, translated_text):
    """Distribute the translated words across the page's EXACT window with
    integer-ms boundaries: token i of n spans
    [start + round(i*dur/n), start + round((i+1)*dur/n)], last lands on
    start+dur precisely. Monotonic, non-overlapping, int by construction."""
    words = [w for w in re.split(r"\s+", str(translated_text).strip()) if w]
    start = int(page["startMs"])
    dur = int(page["durationMs"])
    n = len(words)
    tokens = []
    for i, w in enumerate(words):
        f = start + int(round(i * dur / float(n)))
        t = start + int(round((i + 1) * dur / float(n))) if i < n - 1 else start + dur
        if t <= f:
            t = f + 1
        tokens.append({"text": w, "fromMs": f, "toMs": t})
    return tokens


def translate_pages(caption_pages, target_lang, translate_fn):
    """FULL-OR-NOTHING page translation.

    translate_fn: Callable[[List[str], str], List[str]] — page texts in
    order → translated texts, SAME length, every entry non-empty. Injected;
    never called when there are no pages.

    Returns (pages, meta). On ANY failure meta = {"ok": False, "reason": …}
    and `pages` IS the original list object, untouched — the delivered video
    keeps its correct original captions (degrade allowed, patchy never).
    On success meta = {"ok": True, "target": …, "n_pages": …} and every page
    keeps its exact startMs/durationMs with rebuilt integer-ms tokens.
    """
    pages = caption_pages or []
    if not pages:
        return pages, {"ok": False, "reason": "no_pages"}
    texts = [str(p.get("text") or "") for p in pages]
    try:
        out = translate_fn(texts, target_lang)
    except Exception as e:
        return pages, {"ok": False,
                       "reason": "translate_fn_error:%s" % type(e).__name__}
    if (not isinstance(out, list) or len(out) != len(pages)
            or any(not str(t or "").strip() for t in out)):
        return pages, {"ok": False, "reason": "shape_mismatch"}
    new_pages = []
    for p, txt in zip(pages, out):
        np = dict(p)
        np["text"] = str(txt).strip()
        np["tokens"] = _rebuild_tokens(p, txt)
        new_pages.append(np)
    return new_pages, {"ok": True, "target": target_lang,
                       "n_pages": len(new_pages)}


def build_translation_prompt(page_texts, target_lang):
    """The (system, user) pair the handler's Gemini closure sends. Kept here
    so prompt and contract version together. The response contract is a JSON
    array of exactly len(page_texts) strings — enforced by translate_pages'
    shape check regardless of what the model does."""
    system = (
        "You translate short-form video caption pages. Translate EACH page "
        "into %s, preserving meaning, register, and any numbers/names "
        "verbatim. Keep each translation roughly as compact as its source — "
        "these render as on-screen captions. Return ONLY a JSON array of "
        "strings, exactly one per input page, same order, no commentary."
        % target_lang)
    user = "\n".join("%d. %s" % (i, t) for i, t in enumerate(page_texts))
    return system, user
