#!/usr/bin/env python3
"""A flattened content slot may not carry a default, and TweetBubble is flat.

WHY THIS CHECK EXISTS, AND WHY IT IS NOT smoke_baked_copy. That check reads a
ceiling of ZERO and was correct when it said so — and TweetBubble's `stats` was
baked the whole time, as {"replies": 128, "reposts": 412, "likes": 1200,
"views": 98000}. It walked past because `words()` needs two letters to call
something copy, and an engagement count has none. A COUNT IS CONTENT TOO: every
TweetBubble ever placed drew the same fabricated numbers, under a check
reporting zero. A clean zero is guilty until proven innocent, and this one was
guilty of exactly the thing its denominator could not see.

AND THE SECOND HALF IS THE REGRESSION NOBODY WOULD FIND. Flattening moves the
content into properties; a DEFAULT on one of those properties puts it straight
back, because the registered default IS the value on every placement that does
not override it. The difference from a bake is that a baked literal is
GREPPABLE — `{"replies": 128}` sits in the blob — and a default is not: it is a
well-formed property like every other, and no survey of the code finds it.

SCOPED TO THE KEYS FLATTEN CREATED. Fourteen components carry a non-empty text
default today (textShadow's rgba(), StickyNotes' "5%", StepDivider's "STEP").
A blanket rule would arrive as a wave of red on working components and be
reverted the same day. Geometry is not copy; chrome is not a slot the user
fills. L5 asserts that scoping rather than trusting it.
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bake_registry as bk                                     # noqa: E402
import flatten_spec                                            # noqa: E402

ART = os.path.join(HERE, "chatcut_registry_baked.json")
FAILS, NLEGS = [], 0

STAT_KEYS = ["statReplies", "statReposts", "statLikes", "statViews"]
# The numbers that were baked into every placement until 2026-09-23.
BAKED_COUNTS = ("128", "412", "1200", "98000")


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-48s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    reg = json.load(io.open(ART, encoding="utf-8"))["components"]

    # L0 THE POPULATION, ASSERTED. Every leg below iterates the keys flatten
    # created; if that set came back empty — a renamed spec, a reader that
    # stopped understanding `object`, a FLATTEN dict that failed to import —
    # every one of them would pass over nothing and report a clean sheet.
    allkeys = {n: bk.flattened_keys(n) for n in flatten_spec.FLATTEN}
    total = sum(len(v) for v in allkeys.values())
    leg("L0 flattened_slots_are_a_real_population",
        len(allkeys) >= 13 and total >= 100,
        "%d component(s), %d content slot(s)" % (len(allkeys), total))

    # L1 THE PROPERTY ITSELF: no flattened content slot carries a default, in
    # the artifact ChatCut actually reads.
    off = []
    for n, e in reg.items():
        off += ["%s.%s" % (n, x) for x in bk.default_text_offenders(n, e["properties"])]
    leg("L1 no_flattened_slot_carries_a_default", not off,
        "%d offender(s)%s" % (len(off), ("  <<< " + ", ".join(off)) if off else ""))

    # L2 TWEETBUBBLE IS FLAT, AND THE FOUR SLOTS ARE TEXT. Text and not number
    # because a number property has no empty state: unset arrives as 0 and
    # draws "0", which is absence rendered as a value a viewer reads as a fact.
    tb = reg.get("TweetBubble") or {}
    props = {p["key"]: p for p in tb.get("properties", [])}
    shaped = [k for k in STAT_KEYS
              if props.get(k, {}).get("type") == "text"
              and props.get(k, {}).get("defaultValue") == ""]
    leg("L2 tweetbubble_stats_are_four_empty_text_props",
        sorted(shaped) == sorted(STAT_KEYS),
        "%d/4 shaped: %s" % (len(shaped), sorted(shaped)))

    # L3 AND THE COUNTS ARE GONE FROM THE BLOB. The property existing does not
    # prove the literal left — both halves of a bake move together, and this
    # is the half that was drawing.
    code = tb.get("code", "")
    left = [c for c in BAKED_COUNTS if re.search(r"\b%s\b" % c, code)]
    leg("L3 no_engagement_count_left_in_the_blob", code and not left,
        "%s" % (("still literal: " + ", ".join(left)) if left else "none of 128/412/1200/98000"))

    # L4 THE MAPPING BUILDS THE OBJECT FROM PROPS AND THE ROW FILTERS ON THE
    # LABEL. The object must survive an all-empty placement — the component
    # destructures stats.replies, so dropping it is a crash, not an empty row —
    # and the thing that closes the row up is the label filter, in the body.
    mapped = re.search(r"stats: \{([^}]*)\}", code)
    wired = bool(mapped) and all(("props.%s" % k) in mapped.group(1) for k in STAT_KEYS)
    leg("L4 empty_draws_nothing_and_the_row_closes_up",
        wired and 's.label !== ""' in code and "__shownStats" in code,
        "object_from_props=%s label_filter=%s row_packs=%s"
        % (wired, 's.label !== ""' in code, "__shownStats" in code))

    # L5 THE REFUSAL IS SCOPED. The fourteen components carrying a non-empty
    # text default today are chrome and geometry, and none of them is a
    # flattened slot — asserted, because a rule that reddens working
    # components is a rule that gets reverted rather than read.
    chrome = 0
    for n, e in reg.items():
        keys = bk.flattened_keys(n)
        for p in e["properties"]:
            if (p.get("type") == "text" and p["key"] not in keys
                    and isinstance(p.get("defaultValue"), str)
                    and p["defaultValue"].strip()):
                chrome += 1
    # THE PROPERTY IS "CHROME IS LEFT ALONE", NOT "THERE ARE FOURTEEN OF
    # THEM". This pinned chrome >= 14 and went red when the <=6-knob ruling
    # cut two chrome text defaults — PullQuote's textShadow and ChatThread's
    # statusBarTime. The count was always going to fall as knobs are cut, so
    # the leg was defending a DECISION and firing on the ruling working.
    # Second time today a count-pin has done this; the floor is now only that
    # the population is non-empty, because a leg over zero chrome defaults
    # would assert nothing at all.
    leg("L5 refusal_does_not_touch_chrome_defaults", chrome > 0 and not off,
        "%d non-slot text default(s) left alone" % chrome)

    # L6 THE REFUSAL FIRES. L1 is an assertion about today's artifact and
    # would read exactly the same if the detector had stopped detecting —
    # zero offenders and a blind check are indistinguishable in a tally. So
    # the detector is DRIVEN on a known-bad input: the real function, the real
    # TweetBubble property list, one default put back.
    bad = [dict(p) for p in tb.get("properties", [])]
    for p in bad:
        if p["key"] == "statLikes":
            p["defaultValue"] = "1.2K"
    fires = bk.default_text_offenders("TweetBubble", bad)
    leg("L6 the_refusal_actually_fires",
        len(fires) == 1 and fires[0].startswith("statLikes="),
        "injected statLikes='1.2K' -> %s" % (fires or "NOTHING — the detector is blind"))

    # L7 A COLOUR OR A COORDINATE MAY KEEP ITS DEFAULT, AND A WORD MAY NOT.
    # The first draft of the detector asked only whether the default was a
    # non-empty string — and a colour default is a non-empty string, so it
    # refused EndCard and PillMarquee for keeping "#14141A" on a palette slot.
    # An empty colour is not a blank colour, it is an unpainted element, and
    # an absent coordinate is the top-left corner rather than "nowhere". This
    # leg pins the distinction so the rule cannot drift wide again, and pins
    # it in BOTH directions so it cannot drift narrow either.
    probe = [
        {"key": "paletteBg", "type": "color", "defaultValue": "#14141A"},
        {"key": "startX", "type": "number", "defaultValue": 0.25},
        {"key": "line1Text", "type": "text", "defaultValue": "Follow for more"},
        {"key": "line2Text", "type": "text", "defaultValue": ""},
    ]
    got = bk.default_text_offenders("EndCard", probe)
    leg("L7 chrome_keeps_its_default_and_copy_does_not",
        len(got) == 1 and got[0].startswith("line1Text="),
        "colour+coordinate allowed, one text default refused -> %s" % got)

    # L8 NO ERROR STRING IS EVER DRAWN AS CONTENT — the other half of "an
    # empty slot draws nothing", on the SOURCE rather than the registry.
    #
    # COMMENTS ARE STRIPPED FIRST, AND THAT IS THE WHOLE REASON THIS EXISTS.
    # smoke_poster_frame_legible L1 (no_error_string_as_poster) was GREEN while
    # EmojiCard returned the literal string NO STILL, and
    # measured/REGISTERED_BODIES.json recorded why: the files it read carry
    # "NO STILL" TWICE IN COMMENTS EXPLAINING THE FIX, so a string test on
    # source cannot answer this question even in principle — it matches the
    # prose about the repair and calls that a hit.
    #
    # Run on 2026-09-23 over 120 files it found TWO live ones: DeviceMockup
    # and EvidenceCard, both rendering `NO STILL` at 44px white in the
    # `if (!still)` branch. A plain grep reported FOUR, two of which were the
    # comments saying it had been fixed.
    def _strip_comments(src):
        src = re.sub(r"/\*[\s\S]*?\*/", "", src)
        return re.sub(r"(^|[^:])//[^\n]*", lambda m: m.group(1), src)

    PLACEHOLDER = re.compile(
        r"NO STILL|NO IMAGE|NO PHOTO|NO MEDIA|placeholder"
        r"|Your (?:text|logo|image|photo)|Lorem", re.I)
    files = sorted(glob.glob(os.path.join(HERE, "port", "bodies", "*.jsx"))
                   + glob.glob(os.path.join(HERE, "port", "build", "*.jsx"))
                   + glob.glob(os.path.join(HERE, "ported_mg", "*.jsx"))
                   + glob.glob(os.path.join(HERE, "src", "remotion", "src",
                                            "motion-graphics", "*", "*.tsx")))
    drawn = []
    for f in files:
        body = _strip_comments(io.open(f, encoding="utf-8").read())
        for m in PLACEHOLDER.finditer(body):
            drawn.append("%s:%s" % (os.path.basename(f), m.group(0)))
    # THE DENOMINATOR IS ASSERTED. A glob that stops matching returns zero
    # files and this leg would pass over nothing — the cheapest false green
    # available, and the one this whole family keeps writing down.
    leg("L8 no_error_string_is_drawn_as_content",
        len(files) >= 100 and not drawn,
        "%d file(s) scanned, %d drawn placeholder(s)%s"
        % (len(files), len(drawn), ("  <<< " + ", ".join(drawn[:6])) if drawn else ""))

    # L9 A PICTURE SLOT IS EMPTY BY DEFAULT — and the answer to "can ChatCut's
    # AI fill it" is in the TYPE LIST, which is the finding rather than the leg.
    # ChatCut's registry offers exactly boolean / color / number / select /
    # text. THERE IS NO IMAGE, ASSET OR MEDIA TYPE AT ALL, so every picture
    # slot we have is a `text` field holding a URL: fillable only with an
    # absolute external URL, never with a reference to an asset in the user's
    # own project.
    types = sorted({p["type"] for e in reg.values() for p in e["properties"]})
    media = [(n, p["key"], p.get("defaultValue"))
             for n, e in reg.items() for p in e["properties"]
             if re.search(r"src|url|image|photo|logo|avatar|poster|thumb", p["key"], re.I)
             and p["type"] == "text"]
    bad_media = [m for m in media if isinstance(m[2], str) and m[2].strip()]
    leg("L9 every_picture_slot_defaults_to_empty",
        media and not bad_media and "image" not in types and "asset" not in types,
        "%d picture slot(s), %d with a default; registry types = %s"
        % (len(media), len(bad_media), types))

    # L10 THE LIVE FIVE CARRY THE STRICTER RULE: every text key empty, not
    # only the flatten-created slots. They come from the frame-composition
    # lineage, which never went through the flattening work, and they carry
    # SAMPLE COPY as registered defaults — "THIS IS THE PART THAT MATTERS",
    # "ALEX RIVERA", "NOBODY TELLS YOU". A registered default IS the value on
    # every placement that does not override it.
    #
    # DRIVEN, NOT ASSERTED ON TODAY'S ARTIFACT. Stamp is currently clean, so a
    # leg that only read it would pass with the rule switched off entirely —
    # the zero-offenders-and-a-blind-check problem this file already carries.
    _probe = [{"key": "text", "type": "text",
               "defaultValue": "THIS IS THE PART THAT MATTERS"},
              {"key": "textShadow", "type": "text",
               "defaultValue": "0 1px 2px rgba(0,0,0,0.35)"}]
    _live = bk.default_text_offenders("Stamp", _probe)
    _other = bk.default_text_offenders("BarRace", _probe)
    leg("L10 the_live_five_refuse_every_text_default",
        len(_live) == 1 and _live[0].startswith("text=") and _other == [],
        "live five -> %s | non-live -> %s" % (_live, _other or "unchanged"))

    # L11 AND CSS IS NOT COPY. textShadow is type `text` and holds
    # "0 1px 2px rgba(...)"; emptying it removes a drop shadow rather than a
    # sentence. Named as an exception rather than carved out silently.
    leg("L11 a_css_valued_text_default_is_not_sample_copy",
        bk._is_css_value("0 1px 2px rgba(0,0,0,0.35)")
        and bk._is_css_value("none") and bk._is_css_value("5%")
        and not bk._is_css_value("THIS IS THE PART THAT MATTERS")
        and not bk._is_css_value("ALEX RIVERA"),
        "CSS recognised, sentences not")

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
