"""ONE PLACE for the things both lanes were each keeping a copy of.

Ruled by Zac 2026-09-21. Every leg this replaces existed to police AGREEMENT
between two copies of one fact. That is a real class of defect and the legs were
right — but a check that two copies agree is a worse answer than not having two
copies, and it costs a leg, a fixture and a reader's attention forever.

WHAT WAS COSTING WHAT, before this file:

  * `export.state` was a constant in my reader and a literal in the writer. They
    disagreed — the reader tested "OK", which the writer has never emitted — and
    a PERFECT export read ABSENT. The fix was a leg asserting the reader's
    constant appears in the writer. One definition removes the leg AND the bug.
  * A component's name was in the library on one side of a lane boundary and in
    PORTED_PROPS on the other, so a rename landed in two commits with a resolver
    and two legs bridging the gap. One registry removes the gap.
  * Four zoom property tables existed in a JSON file and in the harness, with
    the harness winning silently. A leg asserted they agreed. One place removes
    the leg.

STATES ARE THE REPO'S THREE-STATE RULE, NAMED ONCE. A measurement has three
outcomes and a delivery has four; writing them as bare strings in each reader is
how "OK" happened.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ── record states ──────────────────────────────────────────────────────────
MEASURED = "MEASURED"     # the thing was read and is what it says
ABSENT = "ABSENT"         # nothing to read — NEVER the same as a measured zero
FAILED = "FAILED"         # the read was attempted and errored
WITHHELD = "WITHHELD"     # a terminal fired; nothing was produced
REFUSED = "REFUSED"       # a floor refused it before it ran

RECORD_STATES = (MEASURED, ABSENT, FAILED, WITHHELD, REFUSED)

# The state an EXPORT carries when the bytes exist. Not "OK" — the writer has
# never emitted that, and a reader comparing against it silently never matches.
EXPORT_DELIVERED = MEASURED

# ── the record schema a reader may key on ──────────────────────────────────
# Named here so a reader does not invent a field. `timeline_sample.end_s` was
# invented once and is not in any record, which made every run read ABSENT.
RECORD_FIELDS = {
    "export.state": "one of RECORD_STATES; MEASURED means the bytes exist",
    "export.why": "the reason, when it is not MEASURED",
    "timeline_sample.items[].itemType": "caption|audio|video|effect|motion-graphic",
    "timeline_sample.items[].timelineRange": "{fromFrame,toFrame} — FRAMES",
    "timeline_sample.items[].sourceRange": "{start,end} — MICROSECONDS, not seconds",
    "shape.calls[].in": "the write call's JSON, whose `adds` length is the tell for dropped items",
    "fault_class_progress.classes": "{class: [count per refused call, in turn order]}",
    "fault_class_progress.stuck": "classes raised and never fallen",
}

# itemType -> the family it counts as, for any per-family tally.
FAMILY_OF_ITEM_TYPE = {
    "caption": "text", "audio": "sfx", "video": "cut",
    "effect": "zoom", "motion-graphic": "card",
}


def _read(name, default=None):
    p = os.path.join(HERE, name)
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return default


def registry(library="library_73.json"):
    """-> {state, components, placements, families, two_home, by_family, why}

    THE ONE COUNT. A component in two families occupies two family placements
    and is still one component, so both numbers are returned and neither is
    called "the total".
    """
    lib = _read(library)
    if not isinstance(lib, dict) or not lib:
        return {"state": FAILED, "why": "no library at %s" % library}
    fams = {k: v for k, v in lib.items()
            if isinstance(v, list) and not k.startswith("_")}
    two_home = set(lib.get("_two_home") or [])
    names = sorted({n for v in fams.values() for n in v})
    placements = sum(len(v) for v in fams.values())
    return {"state": MEASURED, "components": names, "n_components": len(names),
            "placements": placements, "families": len(fams),
            "two_home": sorted(two_home), "by_family": {k: sorted(v) for k, v in fams.items()},
            "why": "%d component(s) in %d famil(ies), %d placement(s), %d two-home"
                   % (len(names), len(fams), placements, len(two_home))}
