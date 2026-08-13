"""cert_mg_obey.py — Rule-1 gate for the dark MG user-ask directive
(LANE-SEAM MG diagnosis). Pure-local, stdlib-only, $0.

What regression each check makes impossible:
  1. DARK-OFF   — env unset ⇒ _mg_obey_enabled() False AND the directive is
     "" even for an explicit ask ⇒ the prompt is byte-identical.
  2. PRECISION  — the parser fires on the verbatim 309-tap preset and real
     positive asks, and NEVER on negatives ("no motion graphics") — a false
     positive here would inject an OBEY block against the user's stated wish.
  3. DIRECTIVE  — flag-on text keeps the earn-gates in charge (WHICH/WHERE)
     and mandates the honest note on an empty answer (never silence).
  4. WIRING     — the directive is spliced into USER INSTRUCTIONS next to
     b-roll's (the obedience-channel asymmetry H1 names), and the staged
     PLAN_ONLY app + diagnosis doc exist with the right arms/keys.

The functions are EXTRACTED from handler.py source and exec'd (importing the
39K-line module locally is not possible) — extraction failure = gate failure,
which also pins the block's continued existence.

Run: python3 cert_mg_obey.py   (exit 0 = PASS)
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
    # NOTE (2026-08-12): this allowlist has now truncated THREE times — when
    # COMPONENT_OBEY landed, when UPSCALE v1 landed, and when §4.8's
    # negotiated-never landed. The pattern is inherently brittle: it depends on
    # module layout, so any new def placed between the anchor and the target
    # silently shortens the block and every lookup KeyErrors. It stays because
    # exec-ing a slice is what keeps this cert free of a real handler import —
    # but if it breaks a fourth time, extract by AST node name instead of by
    # "the next def I do not recognise".
    with open(os.path.join(HERE, "handler.py")) as f:
        src = f.read()
    start = src.index("_MG_ASK_RE = re.compile(")
    tail = src[start:]
    m = re.search(r"\ndef (?!_mg_obey_enabled|_parse_mg_requests|_component_obey_enabled|_parse_component_requests|_component_unmet_notes|_negotiated_never_notes|_parse_music_ask|"
                  r"_mg_request_directive)", tail)
    block = tail[:m.start()] if m else tail
    ns = {"re": re, "os": os}
    exec(compile(block, "handler.py<mg-obey>", "exec"), ns)
    return ns


NS = _extract_block()
PRESET = "Make this a smooth video, add zooms, sound effects and motion graphics"


@check("dark-off: flag defaults off; directive empty even for an explicit ask")
def _dark():
    saved = os.environ.pop("PROMPTLY_MG_OBEY", None)
    try:
        assert NS["_mg_obey_enabled"]() is False
        assert NS["_mg_request_directive"](PRESET) == "", \
            "directive emitted text with the flag dark — prompt no longer byte-identical"
    finally:
        if saved is not None:
            os.environ["PROMPTLY_MG_OBEY"] = saved


@check("precision: positives fire, negatives never do")
def _precision():
    p = NS["_parse_mg_requests"]
    for pos in (PRESET,
                "add motion graphics please",
                "I want some infographics on the stats",
                "use pop-ups for the key points",
                "more animations",
                "with stat cards on the numbers"):
        assert p(pos) is True, "missed positive: %r" % pos
    for neg in ("no motion graphics",
                "without motion graphics please",
                "don't add graphics",
                "remove the graphics",
                "less animations",
                "make it cinematic and clean",
                "viral engaging video",
                ""):
        assert p(neg) is False, "false positive: %r" % neg


@check("directive: gates stay in charge; honest note mandated")
def _directive():
    os.environ["PROMPTLY_MG_OBEY"] = "1"
    try:
        d = NS["_mg_request_directive"](PRESET)
        assert d, "flag-on directive empty for the preset ask"
        for frag, why in (("OBEY", "the obedience frame"),
                          ("WHICH", "gates keep type choice"),
                          ("notes", "the honest-note mandate"),
                          ("never", "the anti-silence clause")):
            assert frag in d, "directive lost %s (%r)" % (why, frag)
        assert NS["_mg_request_directive"]("make it cinematic") == "", \
            "directive fires without an ask — it must be ask-gated even flag-on"
    finally:
        os.environ.pop("PROMPTLY_MG_OBEY", None)


@check("wiring: splice next to b-roll's + staged app + diagnosis doc")
def _wiring():
    with open(os.path.join(HERE, "handler.py")) as f:
        h = f.read()
    assert "{_broll_request_directive(vibe)}{_mg_request_directive(vibe)}" in h, \
        "the MG directive splice left the USER INSTRUCTIONS block"
    app_path = os.path.join(HERE, "cert_mg_honoring_planonly_app.py")
    assert os.path.exists(app_path), "staged PLAN_ONLY app missing"
    with open(app_path) as f:
        appsrc = f.read()
    for frag in ('("control"', '("ask"', '("ask_obey"',
                 "n_mg_standalone", "n_mg_emphasis", "PROMPTLY_MG_OBEY"):
        assert frag in appsrc, "PLAN_ONLY app lost arm/key: %s" % frag
    doc = os.path.join(HERE, "MG_HONORING_DIAGNOSIS.md")
    assert os.path.exists(doc), "diagnosis doc missing"
    with open(doc) as f:
        d = f.read()
    for frag in ("H0", "H1", "H2", "H3", "H4", "H5", "n=359", "224"):
        assert frag in d, "diagnosis doc lost section: %s" % frag


def main():
    failed = 0
    for name, fn in _checks:
        try:
            fn()
            print("PASS  %s" % name)
        except Exception as e:
            failed += 1
            print("FAIL  %s — %s: %s" % (name, type(e).__name__, e))
    print("cert_mg_obey: %d/%d PASS" % (len(_checks) - failed, len(_checks)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
