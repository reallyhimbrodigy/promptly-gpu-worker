#!/usr/bin/env python3
"""THE MECHANICAL ROUTER — decided BEFORE the model is consulted. `[DARK]`

WHAT THIS IS FOR. `edit_recipe` is already a durable editable document: the TIER-3
merge applies OPS to a deepcopy, so untouched fields are byte-identical by
construction. But today the CLASSIFICATION of a request comes FROM a model call —
so even "change the captions to Cove" costs a Gemini round trip, and its outcome
is stochastic.

A large class of requests needs no model at all. This routes those before
anything is consulted, and falls through to the existing classifier for
everything else.

THE PREDICTABILITY GUARANTEE. A mechanical request produces the same edit every
time, in ~0 seconds, at $0. That is a different product promise from "usually
does what you meant", and it applies to the most common small requests there are.

═══ THE DIRECTION OF FAILURE IS THE WHOLE DESIGN ═══

**Ambiguous ⇒ CREATIVE.** A mechanical path that guesses produces a wrong edit
with NO MODEL IN THE LOOP TO CATCH IT — silently, deterministically, every time.
A creative path that handles a mechanical request wastes $0.02 and one round
trip. Those costs are not comparable, so this router only ever routes what it can
prove, and every uncertainty falls through.

═══ THE INTERSECTION THAT MATTERS MOST ═══

A request can be BOTH mechanical and word-mutating:

    "use Cove captions and cut the dead air at the start"
     ^^^^^^^^^^^^^^^^^^  mechanical scalar
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  WORD-SPACE MUTATION

Routing that mechanically would apply the caption style and SILENTLY DROP the
cut — the user gets a changed video that ignored half of what they asked, and
nothing anywhere records the dropped half. It is the worst failure this router
can produce, because it looks like success.

So word-mutation intent is checked FIRST and is DISQUALIFYING, even when a
perfectly good mechanical scalar sits beside it. Mechanical means the request is
ENTIRELY mechanical.
"""
import os
import re

# The scalars the merge may `set` — the mechanical vocabulary, mirrored from
# handler._REEDIT_SET_SCALARS. A scalar absent there cannot be set at all, so
# routing it mechanically would promise something the merge cannot deliver.
# aspect_ratio REMOVED 2026-08-23 — dead field (see the refusal at the aspect
# branch below). color_effect is also inert: handler force-sets it to None
# because the feature was removed, so the router must never emit it either.
MECHANICAL_SCALARS = ("caption_style", "outro",
                      "thumbnail_word_index", "pacing", "audio_denoise",
                      "color_effect", "notes")

# ── DISQUALIFIERS, CHECKED FIRST ─────────────────────────────────────────────
# Anything that mutates the kept-word space. Every anchor in the document is a
# word index, so a word mutation re-times the whole plan — that is re-anchoring
# work with real correctness risk, and it is never mechanical.
_WORD_MUTATION = re.compile(
    r"\b(cut|trim|shorten|tighten|remove|delete|drop|snip|speed\s*up|"
    r"condense|shave|clip)\b"
    r"|\b\d+\s*(?:s|sec|secs|seconds|min|minute|minutes)\b"      # "make it 30 seconds"
    r"|\bdead\s*air\b|\bsilence[s]?\b|\bfiller\b|\bums?\b|\bpauses?\b"
    r"|\bfaster\b|\bshorter\b|\blonger\b|\bextend\b",
    re.I)

# Anything asking for NEW creative content or judgement. A mechanical router that
# accepted these would be inventing.
_CREATIVE_INTENT = re.compile(
    r"\b(better|nicer|punchier|more\s+\w+|less\s+\w+|redo|rework|reinterpret|"
    r"different|creative|viral|engaging|dynamic|exciting|improve|fix\s+the\s+"
    r"(?:pacing|flow|vibe|feel)|make\s+it\s+(?:good|great|pop|slap)|"
    r"add\s+(?:some|more)\b)",
    re.I)

# ── MECHANICAL RECOGNISERS ───────────────────────────────────────────────────
# Each returns an OP the merge already understands, or None. Deliberately narrow:
# an unrecognised phrasing must fall through, never be approximated.
_CAPTION_STYLE = re.compile(
    r"\b(?:caption|subtitle)s?\s+(?:style\s+)?(?:to\s+)?([A-Z][A-Za-z]{2,20})\b"
    r"|\b(?:use|switch\s+to|change\s+to)\s+([A-Z][A-Za-z]{2,20})\s+captions?\b")
_ASPECT = re.compile(r"\b(9:16|16:9|1:1|4:5|vertical|horizontal|square)\b", re.I)
_NO_CAPTIONS = re.compile(r"\b(no|remove|turn\s+off|without|disable)\s+"
                          r"(?:the\s+)?(?:caption|subtitle)s?\b", re.I)
# Connectors widened after the near-miss matrix caught a real phrasing:
# 'you spelled "X" wrong, it should be "Y"'. The miss was in the SAFE direction
# (it fell through to creative), but the most common wording of the most common
# request must route, or the mechanical path is a promise it does not keep.
_TEXT_SWAP = re.compile(
    r"\b(?:spell|spelt|spelled|change|replace|fix|correct)\b[^.]{0,60}?"
    r"[\"“']([^\"”']{1,40})[\"”'][^.]{0,30}?"
    r"(?:to|with|not|should\s+be|is|→|->)\s*[\"“']([^\"”']{1,40})[\"”']", re.I)
_DENOISE = re.compile(r"\b(clean\s+up|reduce|remove)\s+(?:the\s+)?"
                      r"(?:background\s+)?(?:noise|hiss|hum)\b", re.I)


def _aspect_value(tok):
    t = tok.lower()
    return {"vertical": "9:16", "horizontal": "16:9", "square": "1:1"}.get(t, tok)


def classify(message, *, valid_caption_styles=None):
    """(verdict, ops, reason).

    verdict: "mechanical" -> `ops` are applicable with NO model call
             "creative"   -> fall through to the existing model classifier
    `ops` are in the merge's own shape: {op, list_key, anchor?, field?, value_json}
    """
    import json
    msg = str(message or "").strip()
    if not msg:
        return "creative", [], "empty message"

    # 1. DISQUALIFIERS FIRST. The intersection case: a word mutation anywhere in
    #    the request disqualifies the WHOLE request, even beside a clean scalar.
    if _WORD_MUTATION.search(msg):
        return "creative", [], "word-space mutation intent — re-timing and "\
                               "re-anchoring are never mechanical"
    if _CREATIVE_INTENT.search(msg):
        return "creative", [], "creative/judgement intent"

    ops, why = [], []

    # 2. caption OFF — a scalar set, and unambiguous.
    if _NO_CAPTIONS.search(msg):
        ops.append({"op": "set", "list_key": "caption_style",
                    "value_json": json.dumps("none")})
        why.append("captions off")

    # 3. caption STYLE — only when the named style is a REAL registered style.
    #    An unrecognised name falls through rather than being coerced: coercing
    #    it would silently give the user a style they did not ask for.
    else:
        m = _CAPTION_STYLE.search(msg)
        if m:
            name = m.group(1) or m.group(2)
            if valid_caption_styles and name in valid_caption_styles:
                ops.append({"op": "set", "list_key": "caption_style",
                            "value_json": json.dumps(name)})
                why.append(f"caption_style={name}")
            else:
                return "creative", [], f"caption style {name!r} is not a "\
                                       f"registered style — refusing to guess"

    # 4. ASPECT RATIO — REFUSED, not routed (2026-08-23).
    #
    # `aspect_ratio` IS A DEAD FIELD. handler.py:18373 states it outright:
    # "aspect_ratio is informational — the pipeline always outputs 1080x1920
    # regardless of this field", the plan schema is Literal["9:16"], and real
    # format export is driven by input_data["export_formats"], which this router
    # never touches.
    #
    # Routing it mechanically produced the WORST possible outcome: a `set` op
    # that cannot change a pixel, plus human_summary "aspect=1:1 — everything
    # else untouched." surfaced to the user as change_summary. A confident
    # success message for a change that did not happen — precisely the class
    # this module's own docstring exists to prevent, and three of the ten
    # "mechanical" cases in its cert routed to it.
    #
    # Falling through to the creative path does not make aspect work either —
    # nothing in the pipeline does — but it stops us CLAIMING it did. Making it
    # real means wiring export_formats, which is a product change, not a router
    # fix.
    if _ASPECT.search(msg):
        return "creative", [], ("aspect ratio is not something this pipeline "
                                "can change — output is always 1080x1920 — so "
                                "it is not answered mechanically")

    # 5. TEXT SWAP — the most common small request there is, and purely
    #    mechanical: find-text -> replace-text, validated downstream against the
    #    transcript (surgical_ops already refuses a find that is not spoken).
    m = _TEXT_SWAP.search(msg)
    if m:
        ops.append({"op": "add", "list_key": "caption_text_overrides",
                    "value_json": json.dumps({"find": m.group(1),
                                              "replace": m.group(2)})})
        why.append(f"text swap {m.group(1)!r}->{m.group(2)!r}")

    # 6. denoise toggle.
    if _DENOISE.search(msg):
        ops.append({"op": "set", "list_key": "audio_denoise",
                    "value_json": json.dumps(True)})
        why.append("audio_denoise=True")

    if not ops:
        return "creative", [], "no mechanical op recognised"
    return "mechanical", ops, "; ".join(why)


def enabled(input_data=None):
    """DARK by default. Unset => every request takes today's model path."""
    if input_data and input_data.get("mechanical_router_test"):
        return True
    return os.environ.get("PROMPTLY_MECHANICAL_ROUTER", "").strip().lower() in (
        "1", "true", "yes", "on")
