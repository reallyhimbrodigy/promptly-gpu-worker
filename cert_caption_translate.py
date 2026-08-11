"""cert_caption_translate.py — Rule-1 gate for dark caption translation
(LANE-SEAM). Pure-local, stdlib-only, $0 — the model call is injected, never
made here.

What regression each check makes impossible:
  1. DARK-OFF     — enabled() defaults False; per-job override works; the
     parse-site fingerprint sets the transient key ONLY under the flag.
  2. PRECISION    — the parser hits real asks (incl. the verbatim corpus ask
     "Make captions in hindi in this video") and never negatives or
     non-caption language mentions ("speak hindi in the video").
  3. FULL-OR-NOTHING — a raising/mismatched/empty translation returns the
     ORIGINAL page list object untouched (patchy captions are a defect).
  4. INT-MS LAW   — rebuilt tokens are all ints, monotonic, non-overlapping,
     first starts at page startMs, last ends EXACTLY at startMs+durationMs;
     page text/startMs/durationMs preserved (never-early untouched).
  5. WIRING       — parse-site touchpoint, transient-key declaration in
     _RENDER_TRANSIENT_KEYS, build-site seam with both divergence markers,
     image mount.

Run: python3 cert_caption_translate.py   (exit 0 = PASS)
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_checks = []


def check(name):
    def deco(fn):
        _checks.append((name, fn))
        return fn
    return deco


_PAGES = [
    {"text": "our brand will rise", "startMs": 120, "durationMs": 900,
     "tokens": [{"text": "our", "fromMs": 120, "toMs": 300},
                {"text": "brand", "fromMs": 300, "toMs": 560},
                {"text": "will", "fromMs": 560, "toMs": 700},
                {"text": "rise", "fromMs": 700, "toMs": 1020}]},
    {"text": "this year", "startMs": 3000, "durationMs": 601,
     "tokens": [{"text": "this", "fromMs": 3000, "toMs": 3200},
                {"text": "year", "fromMs": 3200, "toMs": 3601}]},
]


@check("dark-off: enabled() defaults False; per-job override works")
def _dark():
    import caption_translate as ct
    saved = os.environ.pop("PROMPTLY_CAPTION_TRANSLATE", None)
    try:
        assert ct.enabled() is False
        assert ct.enabled({}) is False
        assert ct.enabled({"caption_translate_test": True}) is True
        os.environ["PROMPTLY_CAPTION_TRANSLATE"] = "1"
        assert ct.enabled({}) is True
    finally:
        if saved is None:
            os.environ.pop("PROMPTLY_CAPTION_TRANSLATE", None)
        else:
            os.environ["PROMPTLY_CAPTION_TRANSLATE"] = saved


@check("precision: real asks hit, negatives and non-caption mentions never")
def _precision():
    import caption_translate as ct
    for text, want in (
        ("Make captions in hindi in this video", "Hindi"),
        ("translate to spanish", "Spanish"),
        ("translate the captions into french please", "French"),
        ("spanish subtitles", "Spanish"),
        ("english captions please", "English"),
        ("add subs in urdu", "Urdu"),
    ):
        got = ct.parse_target_language(text)
        assert got == want, "%r -> %r (want %r)" % (text, got, want)
    for text in (
        "no subtitles",
        "don't add hindi captions",
        "remove the spanish subtitles",
        "he speaks hindi in the video",
        "make it viral in england",
        "add captions",
        "translate my dreams into reality",
        "",
    ):
        got = ct.parse_target_language(text)
        assert got is None, "false positive: %r -> %r" % (text, got)


@check("full-or-nothing: any failure returns the original object untouched")
def _full_or_nothing():
    import copy
    import caption_translate as ct
    before = copy.deepcopy(_PAGES)

    def _raises(_t, _l):
        raise RuntimeError("boom")
    pages, meta = ct.translate_pages(_PAGES, "Hindi", _raises)
    assert pages is _PAGES and meta["ok"] is False and _PAGES == before
    pages, meta = ct.translate_pages(_PAGES, "Hindi", lambda t, l: ["only one"])
    assert pages is _PAGES and meta["reason"] == "shape_mismatch" and _PAGES == before
    pages, meta = ct.translate_pages(_PAGES, "Hindi", lambda t, l: ["ok", "  "])
    assert pages is _PAGES and meta["reason"] == "shape_mismatch" and _PAGES == before
    pages, meta = ct.translate_pages([], "Hindi", lambda t, l: [])
    assert pages == [] and meta["ok"] is False


@check("int-ms law: rebuilt tokens int/monotonic; page windows preserved")
def _int_ms():
    import copy
    import caption_translate as ct
    before = copy.deepcopy(_PAGES)
    out, meta = ct.translate_pages(
        _PAGES, "Hindi",
        lambda t, l: ["हमारा ब्रांड ऊपर उठेगा", "इस साल"])
    assert meta["ok"] is True and meta["n_pages"] == 2
    assert _PAGES == before, "translate_pages mutated its input"
    for src, np in zip(_PAGES, out):
        assert np["startMs"] == src["startMs"], "page start moved"
        assert np["durationMs"] == src["durationMs"], "page duration moved"
        toks = np["tokens"]
        assert toks, "page lost its tokens"
        assert toks[0]["fromMs"] == src["startMs"], "first token not at page start"
        assert toks[-1]["toMs"] == src["startMs"] + src["durationMs"], \
            "last token does not land exactly on the page end"
        prev_end = None
        for tk in toks:
            assert isinstance(tk["fromMs"], int) and isinstance(tk["toMs"], int), \
                "float ms leaked — the strict-int schema kills every caption render"
            assert tk["toMs"] > tk["fromMs"], "non-positive token span"
            if prev_end is not None:
                assert tk["fromMs"] == prev_end, "token gap/overlap inside page"
            prev_end = tk["toMs"]
    assert out[0]["text"].startswith("हमारा"), "page text not replaced"


@check("wiring: parse site + transient declaration + build seam + mount")
def _wiring():
    with open(os.path.join(HERE, "handler.py")) as f:
        h = f.read()
    with open(os.path.join(HERE, "modal_app.py")) as f:
        m = f.read()
    for needle, why in (
        ("import caption_translate as _ctr", "parse-site import"),
        ("if _ctr.enabled(input_data):", "flag gate at the parse site"),
        ("edit_plan[_ctr.TRANSIENT_KEY] = _ctr.parse_target_language(",
         "transient target set under the flag only"),
        ('"_caption_translate_target",  # re-parsed from the vibe every render',
         "_RENDER_TRANSIENT_KEYS declaration (the cannot-deploy-undeclared law)"),
        ('_ct_target = edit_plan.get("_caption_translate_target")',
         "build-site read"),
        ("_ctr2.translate_pages(", "full-or-nothing application"),
        ('"caption_translated"', "success divergence marker"),
        ('"caption_translate_failed"', "failure divergence marker"),
        ('_ledger_defect("missing_module", "caption_translate"',
         "loud missing-mount ledger"),
    ):
        assert needle in h, "handler.py lost: %s (%s)" % (needle, why)
    assert 'add_local_file("caption_translate.py", "/caption_translate.py")' \
        in m, "modal_app.py mount for caption_translate.py missing"


def main():
    failed = 0
    for name, fn in _checks:
        try:
            fn()
            print("PASS  %s" % name)
        except Exception as e:
            failed += 1
            print("FAIL  %s — %s: %s" % (name, type(e).__name__, e))
    print("cert_caption_translate: %d/%d PASS"
          % (len(_checks) - failed, len(_checks)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
