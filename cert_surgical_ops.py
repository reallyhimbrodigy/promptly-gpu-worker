"""cert_surgical_ops.py — Rule-1 gate for the Step-3 surgical ops
(LANE-SEAM). Pure-local, stdlib + type_registries only, $0.

What regression each check makes impossible:
  1. DARK-OFF     — enabled() defaults False; per-job override works.
  2. PROMPT-IDENTITY — the flag-off refusal bullet is BYTE-IDENTICAL to the
     historical prompt text (hardcoded fingerprint), handler builds it ONLY
     from surgical_ops (no drifting inline copy), and the conditional exists.
  3. NO-FABRICATION — a caption override whose find-text matches no
     consecutive transcript words is rejected (with reason), never applied.
  4. NATURAL-DURATION LAW — an added transition that can't fit its seam's
     silence room is SKIPPED with a note, never shortened; wrong types,
     dead anchors, and seam collisions are dropped with notes; pre-existing
     transitions are never judged.
  5. NO-OP SAFETY — with nothing added, both validators change nothing
     (flag-off tweaks stay byte-identical by construction).
  6. WIRING       — anchors entry, flag-aware schema enum, dispatcher plumb,
     post-apply enforcement, render-side merge, image mount.

Run: python3 cert_surgical_ops.py   (exit 0 = PASS)
"""

import copy
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


_WORDS = [
    {"word": "our", "start": 0.0, "end": 0.2},
    {"word": "brand", "start": 0.2, "end": 0.5},
    {"word": "will", "start": 0.5, "end": 0.7},
    {"word": "rise", "start": 0.7, "end": 1.1},
    {"word": "this", "start": 3.0, "end": 3.2},   # 1.9s gap after 'rise'
    {"word": "year", "start": 3.2, "end": 3.6},
]

_FRAMES = {"DipToBlack": 30, "CrossfadeZoom": 90}


@check("dark-off: enabled() defaults False; per-job override works")
def _dark():
    import surgical_ops as so
    saved = os.environ.pop("PROMPTLY_SURGICAL_V2", None)
    try:
        assert so.enabled() is False
        assert so.enabled({}) is False
        assert so.enabled({"surgical_v2_test": True}) is True
        os.environ["PROMPTLY_SURGICAL_V2"] = "1"
        assert so.enabled({}) is True
    finally:
        if saved is None:
            os.environ.pop("PROMPTLY_SURGICAL_V2", None)
        else:
            os.environ["PROMPTLY_SURGICAL_V2"] = saved


@check("prompt-identity: flag-off refusal bullet is the historical bytes")
def _prompt_identity():
    import surgical_ops as so
    expected = (
        "  • 'add a transition at the chapter break' / 'add a DipToBlack after the setup'\n"
        "      → transitions are authored in the dedicated seam pass — not addable here;\n"
        "        acknowledge the ask in notes and leave the plan's transitions untouched.\n"
    )
    assert so.TRANSITION_REFUSAL_BULLET == expected, (
        "TRANSITION_REFUSAL_BULLET drifted — flag-off tweak prompt is no "
        "longer byte-identical to the pre-Step-3 prompt")
    with open(os.path.join(HERE, "handler.py")) as f:
        h = f.read()
    assert "transitions are authored in the dedicated seam pass" not in h, (
        "handler.py still carries an inline copy of the refusal bullet — "
        "two copies WILL drift; it must come only from surgical_ops")
    # RE-EXPRESSED AS A PROPERTY (2026-08-18). This pinned the EXACT source
    # bytes of one ternary, so it failed the moment the caption op was split
    # onto its own flag — a legitimate refactor that STRENGTHENED the gating.
    # Third time today a location-pinned check fired on a refactor; the property
    # is what matters, so it is resolved on the parsed tree.
    #
    # THE PROPERTY: transition-add is selected by surgical_v2 and ONLY by
    # surgical_v2; the refusal bullet is the flag-off alternative; and neither
    # bullet is inlined (asserted above).
    import ast as _ast
    _tree = _ast.parse(h)
    _add_sel = [n for n in _ast.walk(_tree)
                if isinstance(n, _ast.IfExp)
                and "TRANSITION_ADD_BULLET" in (_ast.get_source_segment(h, n) or "")]
    assert _add_sel, "transition-add is no longer flag-selected at all"
    for _n in _add_sel:
        _t = _ast.get_source_segment(h, _n.test) or ""
        assert "surgical_v2" in _t, (
            "transition-add must be gated by surgical_v2")
        assert "caption_text_ops_enabled" not in _t, (
            "transition-add must NOT be gated by the caption flag — that would "
            "ship a creative capability inside the mechanical text-swap change")
        _alt = _ast.get_source_segment(h, _n.orelse) or ""
        assert "TRANSITION_REFUSAL_BULLET" in _alt, (
            "flag-off must still select the refusal bullet verbatim")
    for frag in ("after_word_index", "\"type\""):
        assert frag in so.TRANSITION_ADD_BULLET
    for frag in ("find", "replace"):
        assert frag in so.CAPTION_TEXT_BULLET


@check("no-fabrication: caption overrides validate against the transcript")
def _no_fabrication():
    import surgical_ops as so
    entries = [
        {"find": "rise", "replace": "ryze"},           # present → valid
        {"find": "our brand", "replace": "OurBrand"},  # consecutive → valid
        {"find": "moon", "replace": "Mars"},           # absent → rejected
        {"find": "brand rise", "replace": "x"},        # non-consecutive → rejected
        {"find": "", "replace": "y"},                  # empty → rejected
        "not-a-dict",                                  # malformed → rejected
    ]
    valid, rejected = so.validate_caption_overrides(entries, _WORDS)
    assert [e["find"] for e in valid] == ["rise", "our brand"], valid
    assert len(rejected) == 4, rejected
    assert all(why for _, why in rejected), "a rejection lost its reason"
    # dict conversion feeds the existing display applicator's key shape
    d = so.overrides_dict_from_plan({so.CAPTION_TEXT_LIST_KEY: valid})
    assert d[("rise",)] == "ryze" and d[("our", "brand")] == "OurBrand", d


@check("natural-duration law: added transitions validated, never squeezed")
def _transitions():
    import surgical_ops as so
    old = {"transitions": [{"after_word_index": 1, "type": "NotEvenReal"}]}
    new = copy.deepcopy(old)
    new["transitions"] += [
        {"after_word_index": 3, "type": "DipToBlack"},     # 1.9s gap ≥ 1.0s → kept
        {"after_word_index": 3, "type": "CrossfadeZoom"},  # seam collision → drop
        {"after_word_index": 0, "type": "CrossfadeZoom"},  # 0s gap < 3.0s → drop
        {"after_word_index": 99, "type": "DipToBlack"},    # dead anchor → drop
        {"after_word_index": 4, "type": "SpinWipe"},       # bad type → drop
    ]
    notes, kept = so.validate_added_transitions(new, old, _WORDS, _FRAMES)
    anchors = [(t.get("after_word_index"), t.get("type"))
               for t in new["transitions"]]
    assert (1, "NotEvenReal") in anchors, \
        "pre-existing transition was judged — validator must only judge adds"
    assert (3, "DipToBlack") in anchors, "a fitting add was wrongly dropped"
    assert len(new["transitions"]) == 2 and kept == 2, anchors
    assert len(notes) == 4, notes
    assert any("skipped rather than squeezed" in n for n in notes), (
        "the room-law drop lost its honest never-shortened note")


@check("no-op safety: nothing added ⇒ nothing changes")
def _noop():
    import surgical_ops as so
    plan = {"caption_style": "Prime"}
    before = copy.deepcopy(plan)
    notes, kept = so.validate_added_transitions(plan, plan, _WORDS, _FRAMES)
    assert notes == [] and kept == 0 and plan == before
    old = {"transitions": [{"after_word_index": 1, "type": "DipToBlack"}]}
    new = copy.deepcopy(old)
    notes, kept = so.validate_added_transitions(new, old, _WORDS, _FRAMES)
    assert notes == [] and new == old
    assert so.overrides_dict_from_plan({}) == {}
    valid, rejected = so.validate_caption_overrides(None, _WORDS)
    assert valid == [] and rejected == []


@check("wiring: anchors + flag-aware schema + dispatch + enforce + merge + mount")
def _wiring():
    with open(os.path.join(HERE, "handler.py")) as f:
        h = f.read()
    with open(os.path.join(HERE, "modal_app.py")) as f:
        m = f.read()
    for needle, why in (
        ('"caption_text_overrides": lambda e: (', "_DIFF_LIST_ANCHORS entry"),
        ('_lks.discard("caption_text_overrides")',
         "flag-off schema enum exclusion"),
        ("def _plan_diff_ops_schema(surgical_v2=False)", "flag-aware schema"),
        ("_plan_diff_ops_schema(surgical_v2=surgical_v2)", "schema call plumb"),
        ("surgical_v2=_surgical_v2,", "dispatcher plumb"),
        ("_surgical_ops.validate_added_transitions(", "post-apply transition enforcement"),
        ("_surgical_ops.validate_caption_overrides(", "post-apply caption enforcement"),
        ("_sops_merge.overrides_dict_from_plan(edit_plan)", "render-side merge"),
        ('_ledger_defect("missing_module", "surgical_ops"', "loud missing-mount ledger"),
    ):
        assert needle in h, "handler.py lost: %s (%s)" % (needle, why)
    assert 'add_local_file("surgical_ops.py", "/surgical_ops.py")' in m, \
        "modal_app.py mount for surgical_ops.py missing"


def main():
    failed = 0
    for name, fn in _checks:
        try:
            fn()
            print("PASS  %s" % name)
        except Exception as e:
            failed += 1
            print("FAIL  %s — %s: %s" % (name, type(e).__name__, e))
    print("cert_surgical_ops: %d/%d PASS" % (len(_checks) - failed, len(_checks)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
