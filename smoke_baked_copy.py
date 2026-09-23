#!/usr/bin/env python3
"""Baked copy ships verbatim on every placement and cannot be overridden.

THE MECHANISM, RULED 2026-09-14 AND WORKING AS DESIGNED. ChatCut has no array
or object property type, so structured content is BAKED INTO THE CODE at
registration and the declared property is DROPPED — both halves move together,
because ChatCut refuses a declared property the code does not read as firmly as
a read that is not declared. That is why nineteen components could be given the
thing they exist to show.

THE CONSEQUENCE NOBODY WROTE DOWN: a baked value is a LITERAL. It is not in
`properties`, so `propertyOverrides` cannot reach it, so EVERY PLACEMENT OF
THAT COMPONENT DRAWS THAT EXACT COPY, on every user's video, forever. Measured
2026-09-23: 23 of 37 registered components carry copy-bearing baked content.
Every RankedList says HOOK / PROOF / CLOSE. Every PillCluster says FAST /
CHEAP / GOOD / NO WATERMARK.

THIS CHECK DOES NOT FORBID BAKED COPY. It pins the population so a new one
cannot appear silently, and it refuses the two classes that are not demo copy
at all but OUR MATERIAL ON A STRANGER'S VIDEO.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "chatcut_registry_baked.json")
FAILS, NLEGS = [], 0

# The set as measured 2026-09-23. A FLOOR AND A CEILING: it may not grow
# without a ruling, and a component leaving it is equally news.
# EndCard AND Notification LEFT THIS SET ON 2026-09-23, deliberately, and the
# check demanded the removal be written down before it would go green again —
# which is the leg doing its job in the direction nobody designs for.
# ZERO. Ruled by Zac 2026-09-23: no baked copy, anywhere. Every array is
# numbered scalar properties now, so there is nothing left for a placement to
# be unable to override. This set is EMPTY and must stay empty.
RULED_COPY_BEARING = set()

# OUR BRAND ON SOMEONE ELSE'S VIDEO. EndCard bakes "@promptly" and
# "promptly.video" — a placement puts our handle on a customer's edit and there
# is no property to change it.
BRAND = re.compile(r"@promptly|promptly\.(video|day|app|io|com)|usepromptly", re.I)

# A FABRICATED RECORD. Notification bakes "Payment Received" / "$249.00 from
# Kellan" — a made-up financial notification naming a person, rendered as if
# real on a user's video. Money beside a personal name is the shape.
MONEY = re.compile(r"[$£€]\s?\d[\d,]*(?:\.\d{2})?")


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def payload(code, key):
    """-> the baked value, or [] for an expression that draws from props.

    A FLATTENED KEY IS NOT A LITERAL ANY MORE. After 2026-09-23 the mapped
    value is an EXPRESSION — `[props.pill1, ...].filter(...)` — which json
    cannot parse, and the first version of this reported every flattened
    component as UNPARSED-so-treat-as-copy. Conservative, and wrong about the
    facts: an expression over props is the opposite of baked copy.

    THE HOLE THIS MUST NOT OPEN is an expression with a string literal inside
    it — `[props.pill1, "FREE"]` is still our word on a user's video. So an
    unparseable value is not waved through: its STRING LITERALS are extracted
    and returned as the payload, and only a literal-free expression is clean.
    """
    # LINE-BASED, because __mapped writes one entry per line and the value can
    # be either a single-line JSON literal or a JS expression. The previous
    # bracket-balanced pattern could not match
    # `tags: [props.pill1, ...].filter(...)` — it wanted `],` and found
    # `].filter(` — so every flattened component came back None and the survey
    # read None as "unparsed, treat as copy". A READER THAT CANNOT PARSE THE
    # NEW SHAPE REPORTS THE OLD PROBLEM EVERYWHERE, which is a reader bug
    # wearing twelve findings.
    m = re.search(r"^\s{4}%s:\s*(.+),$" % re.escape(key), code, re.M)
    if not m:
        return None
    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:                                          # noqa: BLE001
        pass
    if "props." not in raw:
        # Not JSON and not built from props — it is something this reader does
        # not understand, and an unknown is not a clean result.
        return "UNPARSED"
    return [x for x in re.findall(r'"([^"\\]*)"', raw)]


def words(o, acc=None):
    acc = [] if acc is None else acc
    if isinstance(o, str):
        if not re.fullmatch(r"#[0-9A-Fa-f]{3,8}", o) and re.search(r"[A-Za-z]{2,}", o):
            acc.append(o)
    elif isinstance(o, list):
        for x in o:
            words(x, acc)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k.lower() in ("color", "colour", "bg", "background", "accent"):
                continue
            words(v, acc)
    return acc


def survey(reg):
    out = {}
    for n, e in reg.items():
        got = []
        for key in (e.get("baked") or []):
            if "=" in key:
                continue
            p = payload(e["code"], key)
            got += ["<UNPARSED>"] if p in (None, "UNPARSED") else words(p)
        if got:
            out[n] = got
    return out


def main():
    reg = json.load(io.open(ART, encoding="utf-8"))["components"]
    found = survey(reg)

    # L0 THE POPULATION IS PINNED IN BOTH DIRECTIONS. A component acquiring
    # baked copy is a component that starts printing our words on every
    # placement, and nothing else would say so.
    # AND THE DENOMINATOR IS ASSERTED, because zero is the answer here and a
    # zero over an empty population is the cheapest false green available: a
    # registry that failed to load, or a survey that stopped recognising the
    # baked shape, both produce "no copy-bearing components" and both are
    # reader bugs. It has already happened once — the survey read the new
    # FLATTENED marker as a key name and reported all twelve as copy.
    offenders = sorted(set(found) - RULED_COPY_BEARING)
    leg("L0 no_component_carries_baked_copy",
        len(reg) >= 20 and not offenders,
        "%d component(s) surveyed, %d carrying baked copy%s"
        % (len(reg), len(offenders),
           ("  <<< " + ", ".join(offenders)) if offenders else " — the ceiling is zero"))

    # L1 BAKED COPY IS UNSETTABLE, AND THAT IS THE WHOLE RISK. Asserted rather
    # than assumed: if a baked key ever comes back as a property, this stops
    # being a one-way door and the check should be told.
    settable = []
    for n, e in reg.items():
        keys = {p["key"] for p in e["properties"]}
        for b in (e.get("baked") or []):
            if "=" not in b and b in keys:
                settable.append("%s.%s" % (n, b))
    leg("L1 baked_content_is_not_a_property", not settable,
        "%d baked key(s) still settable: %s" % (len(settable), settable or "none"))

    # L2 NO BRAND MARK IN COPY THAT SHIPS TO A USER.
    branded = {n: [w for w in ws if BRAND.search(w)] for n, ws in found.items()}
    branded = {n: v for n, v in branded.items() if v}
    leg("L2 no_brand_mark_in_baked_copy", not branded,
        "%s" % (branded or "none"))

    # L3 NO FABRICATED FINANCIAL RECORD.
    money = {n: [w for w in ws if MONEY.search(w)] for n, ws in found.items()}
    money = {n: v for n, v in money.items() if v}
    leg("L3 no_money_amount_in_baked_copy", not money, "%s" % (money or "none"))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
