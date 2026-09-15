#!/usr/bin/env python3
"""Turn a ruled `card_hero` into props a StatCard will actually render.

THE FAILURE THIS PREVENTS, measured by this repo already:
    StatCard {"value":10000,"label":"FOLLOWERS"}   184,920 bytes — renders
    StatCard {"stat":10000,"caption":"FOLLOWERS"}   48,138 bytes — BLANK
Both exit 0. Both report a successful render. One is a transparent frame.

The ported component is stricter than the prose suggests — it returns null
unless `value` is a FINITE NUMBER:

    if (typeof value !== "number" || !Number.isFinite(value)) return null;

So a hero of "3 YEARS" placed verbatim renders nothing, at placement time,
inside a run whose every gate passes. The catalogue's blank check caught this
class in a still; this catches it one layer earlier, in the props.

SPLIT, DO NOT COERCE. "3 YEARS" is a number and a unit: the number is the
value, the rest belongs with the label. A hero with no number at all is not a
StatCard — refuse it rather than render an empty frame, because the caller can
choose another component and cannot un-ship a blank one.
"""
import re

_NUM = re.compile(r"(-?\d[\d,]*\.?\d*)")


def hero_to_props(hero, label=None):
    """(props, why) or raises ValueError when the hero carries no number."""
    raw = (hero or "").strip()
    m = _NUM.search(raw)
    if not m:
        raise ValueError(
            "card_hero %r carries no number, and StatCard returns null unless "
            "`value` is a finite number — it would render a transparent frame "
            "and report success. Rule a different component, or give the hero "
            "its figure." % hero)
    num = float(m.group(1).replace(",", ""))
    value = int(num) if num == int(num) else num
    before = raw[:m.start()].strip()
    after = raw[m.end():].strip()
    # PREFIX vs SUFFIX, from where they sat in the hero. "$20M" and "3 YEARS"
    # are the same shape read from opposite sides.
    props = {"value": value, "label": (label or "").strip()}
    if before:
        props["prefix"] = before
    if after:
        # The unit belongs to the figure, not to the caption: "3 YEARS" reads
        # as one object. Carried as the suffix so the label stays the claim.
        props["suffix"] = after
    why = "hero %r -> value %s%s%s" % (
        hero, value,
        ", prefix %r" % before if before else "",
        ", suffix %r" % after if after else "")
    return props, why


if __name__ == "__main__":
    import sys
    cases = [("3 YEARS", "STILL UNEMPLOYED"), ("1700", "THAT'S WHAT HE THOUGHT"),
             ("$20,000,000", "RAISED"), ("100K", "SUBSCRIBERS"),
             ("2.5x", "FASTER"), ("SOLD OUT", "NO NUMBER HERE")]
    bad = 0
    for h, l in cases:
        try:
            p, w = hero_to_props(h, l)
            ok = isinstance(p["value"], (int, float))
            bad += not ok
            print(f"  [{'ok' if ok else 'FAIL'}] {h!r:15s} -> {p}")
        except ValueError as e:
            expect = h == "SOLD OUT"
            bad += not expect
            print(f"  [{'ok' if expect else 'FAIL'}] {h!r:15s} -> REFUSED: {str(e)[:60]}…")
    sys.exit(1 if bad else 0)
