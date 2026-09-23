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
    leg("L5 refusal_does_not_touch_chrome_defaults", chrome >= 14 and not off,
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

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
