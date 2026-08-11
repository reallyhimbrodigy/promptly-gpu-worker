"""cert_upscale_negotiate.py — Rule-1 gate for the dark upscale
honest-negotiation path (LANE-SEAM). Pure-local, stdlib-only, $0.

What regression each check makes impossible:
  1. DARK-OFF   — flag defaults off; per-job override works; the note can
     only enter capability_notes under the flag (source fingerprint).
  2. PRECISION  — real corpus asks fire ("Trun in to 4k", "8k", "make video
     HD"); style asks NEVER do ("make a high quality edit" is not an
     upscale ask) and negations never do.
  3. TRUTHFULNESS — the note states the real delivery contract (1080p) and
     never claims native-resolution passthrough; it stays a negotiation
     (limit + what-was-delivered + why-it-serves), not a bare refusal.
  4. WIRING     — the touchpoint sits after _parse_unsupported_requests in
     the honesty assembly and ledgers the upscale_negotiated divergence.

Functions extracted from handler.py source and exec'd (importing the module
locally is not possible); extraction failure = gate failure.

Run: python3 cert_upscale_negotiate.py   (exit 0 = PASS)
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

_checks = []


def check(name):
    def deco(fn):
        _checks.append((name, fn))
        return fn
    return deco


def _extract_block():
    with open(os.path.join(HERE, "handler.py")) as f:
        src = f.read()
    start = src.index("_UPSCALE_ASK_RE = re.compile(")
    tail = src[start:]
    m = re.search(r"\ndef (?!_upscale_negotiate_enabled|"
                  r"_parse_upscale_request)", tail)
    block = tail[:m.start()] if m else tail
    ns = {"re": re, "os": os}
    exec(compile(block, "handler.py<upscale>", "exec"), ns)
    return ns


NS = _extract_block()


@check("dark-off: flag defaults off; per-job override works")
def _dark():
    saved = os.environ.pop("PROMPTLY_UPSCALE_NEGOTIATE", None)
    try:
        assert NS["_upscale_negotiate_enabled"]() is False
        assert NS["_upscale_negotiate_enabled"]({}) is False
        assert NS["_upscale_negotiate_enabled"](
            {"upscale_negotiate_test": True}) is True
        os.environ["PROMPTLY_UPSCALE_NEGOTIATE"] = "1"
        assert NS["_upscale_negotiate_enabled"]({}) is True
    finally:
        if saved is None:
            os.environ.pop("PROMPTLY_UPSCALE_NEGOTIATE", None)
        else:
            os.environ["PROMPTLY_UPSCALE_NEGOTIATE"] = saved


@check("precision: corpus asks fire; style asks and negations never")
def _precision():
    p = NS["_parse_upscale_request"]
    for pos in ("Trun in to 4k",          # the real corpus typo, verbatim
                "8k",
                "make video HD",
                "turn this into hd",
                "upscale this please",
                "enhance the resolution",
                "boost the sharpness a bit",
                "export in 4K"):
        assert p(pos) is True, "missed positive: %r" % pos
    for neg in ("make a high quality edit",   # STYLE ask — must not fire
                "high quality viral video",
                "enhance the energy",
                "hdr look",                    # \bhd\b must not match inside hdr
                "no 4k needed",
                "don't upscale it",
                "make it punchy and clean",
                ""):
        assert p(neg) is False, "false positive: %r" % neg


@check("truthfulness: 1080p stated; no native-res claim; negotiation shape")
def _truth():
    note = NS["_UPSCALE_NEGOTIATION_NOTE"]
    assert "1080p" in note, "the note must state the real delivery resolution"
    assert "native resolution" not in note.lower(), \
        "the note claims native-res passthrough — FALSE for 4K sources (render canvas is 1080x1920)"
    for frag, why in (("isn't in Promptly yet", "names the limit"),
                      ("delivered", "names what WAS done"),
                      ("re-rendered", "names the future lever")):
        assert frag in note, "note lost the %s clause (%r)" % (why, frag)


@check("wiring: touchpoint in the honesty assembly + divergence marker")
def _wiring():
    with open(os.path.join(HERE, "handler.py")) as f:
        h = f.read()
    i_parse = h.index("_capability_notes = _parse_unsupported_requests(")
    i_touch = h.index("_upscale_negotiate_enabled(input_data)")
    assert i_touch > i_parse, \
        "negotiation touchpoint no longer follows the unsupported-notes parse"
    assert "_capability_notes.append(_UPSCALE_NEGOTIATION_NOTE)" in h, \
        "the note no longer lands in capability_notes"
    assert '"upscale_negotiated"' in h, \
        "the upscale_negotiated divergence (the demand counter) is gone"


def main():
    failed = 0
    for name, fn in _checks:
        try:
            fn()
            print("PASS  %s" % name)
        except Exception as e:
            failed += 1
            print("FAIL  %s — %s: %s" % (name, type(e).__name__, e))
    print("cert_upscale_negotiate: %d/%d PASS"
          % (len(_checks) - failed, len(_checks)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
