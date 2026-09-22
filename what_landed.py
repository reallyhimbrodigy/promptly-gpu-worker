#!/usr/bin/env python3
"""ONE TABLE OF WHAT LANDED. No verdicts — Zac judges every edit himself.

THREE SURFACES, BECAUSE NO ONE OF THEM SEES THE EDIT:

    items         preview_timeline
    captions      read_captions — CAPTIONS ARE NOT ITEMS. preview_timeline
                  showed two video items and two empty tracks on run one, where
                  24 caption cards had landed. An instrument reporting "nothing"
                  and an edit where nothing landed are indistinguishable.
    transitions   inspect_item, DEDUPED BY ID — transitions are invisible to
                  preview_timeline and appear under Attached TWICE, once per
                  endpoint. Counting the rows doubles them.
    export        the rendered file, read back

ABSENT IS NOT ZERO, AND THAT IS THE WHOLE DESIGN. "0 transitions" from a read
that happened and "0 transitions" from a read that was never made are the same
number and different facts. Every row carries which it is, so a run line cannot
report an unread surface as an empty one.
"""

READER_VERSION = "1.0.0"
FPS_DEFAULT = 30


def _ms(us):
    return us / 1000.0


def cuts_from_items(items):
    """Source time removed, derived from the gaps BETWEEN consecutive source
    ranges on one track.

    REPORTED IN BOTH UNITS, because they are different numbers and both true:
    the SOURCE removed is what the cut took out; the TIMELINE delta is what the
    viewer loses, and frames quantise. Run one removed 20ms of source and the
    timeline lost a whole frame at 33.3ms. Reporting either alone invites the
    other to be inferred from it.
    """
    vid = [i for i in items if i.get("type") == "video" and i.get("source_us")]
    vid = sorted(vid, key=lambda i: i["timeline"][0])
    cuts = []
    for a, b in zip(vid, vid[1:]):
        gap_us = b["source_us"][0] - a["source_us"][1]
        if gap_us > 0:
            cuts.append({"at_timeline_frame": b["timeline"][0],
                         "source_removed_ms": round(_ms(gap_us), 3)})
    return cuts


def dedupe_transitions(inspect_rows):
    """Transitions appear once per ENDPOINT, so the same transition is listed
    twice. Dedupe by id; the count of rows is not the count of transitions."""
    seen, out = set(), []
    for r in inspect_rows or []:
        tid = r.get("id")
        if tid is None or tid in seen:
            continue
        seen.add(tid)
        out.append(r)
    return out


def build(surfaces):
    """-> the table. Each family carries a STATE as well as a count."""
    def state(key, value):
        if key not in surfaces:
            return "NOT_READ"
        return "READ"

    items = surfaces.get("items")
    caps = surfaces.get("captions")
    trans = surfaces.get("transitions_inspected")
    exp = surfaces.get("export")
    tl = surfaces.get("timeline") or {}
    fps = tl.get("fps", FPS_DEFAULT)

    t_ded = dedupe_transitions(trans) if trans is not None else None
    cuts = cuts_from_items(items) if items is not None else None

    rows = {
        "items": {"state": state("items", items),
                  "count": None if items is None else len(items),
                  "video": None if items is None else
                           len([i for i in items if i.get("type") == "video"])},
        "cuts": {"state": "DERIVED" if cuts is not None else "NOT_READ",
                 "count": None if cuts is None else len(cuts),
                 "source_removed_ms": None if cuts is None else
                     round(sum(c["source_removed_ms"] for c in cuts), 3),
                 "timeline_frames": tl.get("durationFrames"),
                 "frame_ms": round(1000.0 / fps, 1) if fps else None,
                 "detail": cuts},
        "captions": {"state": state("captions", caps),
                     "count": None if caps is None else caps.get("total"),
                     "preset": None if caps is None else caps.get("preset")},
        "transitions": {"state": state("transitions_inspected", trans),
                        "count": None if t_ded is None else len(t_ded),
                        "_note": "deduped by id; rows are per-endpoint"},
        "graphics": {"state": state("items", items),
                     "count": None if items is None else
                              len([i for i in items
                                   if i.get("type") == "motion-graphic"])},
        "sounds": {"state": state("items", items),
                   "count": None if items is None else
                            len([i for i in items if i.get("type") == "audio"])},
        "export": {"state": state("export", exp),
                   "duration_s": None if exp is None else exp.get("duration_s")},
    }
    return {"reader_version": READER_VERSION, "rows": rows}


def render(table):
    """The run line. Counts only, and NOT_READ never prints as 0."""
    out = ["what landed  (reader v%s)" % table["reader_version"]]
    for name, r in table["rows"].items():
        if r["state"] == "NOT_READ":
            out.append("  %-12s NOT READ — surface not consulted" % name)
            continue
        if name == "cuts":
            out.append("  %-12s %s cut(s), %s ms of source removed "
                       "(timeline %s frames, a frame is %s ms)"
                       % (name, r["count"], r["source_removed_ms"],
                          r["timeline_frames"], r["frame_ms"]))
        elif name == "export":
            out.append("  %-12s %ss" % (name, r["duration_s"]))
        elif name == "captions":
            out.append("  %-12s %s card(s), preset %r" % (name, r["count"], r["preset"]))
        else:
            out.append("  %-12s %s" % (name, r["count"]))
    return "\n".join(out)
