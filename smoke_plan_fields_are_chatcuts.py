#!/usr/bin/env python3
"""SMOKE — every time field the plan emits is in ChatCut's NAME, UNIT and CLOCK.

THE THREE TRAPS, ALL OF WHICH HAVE ALREADY FIRED HERE:

  NAME    ChatCut READS `timelineRange.fromFrame` / `toFrame` and WRITES
          `from` / `durationInFrames`. Two vocabularies for one timeline, and
          the read one is the one you see first in every tool result.
  UNIT    `toFrame` is a POSITION and `durationInFrames` is a LENGTH. Passing
          one as the other puts every item at the wrong end of itself.
          Source offsets are SECONDS in the same call that takes frames.
  DISCOVERY
          an id the plan sends the agent to LOOK UP is a turn the edit does
          not need. Five browse_library calls went on one sound and three
          failed inspect_item calls on one zoom. The sfx assetId is a real
          `library:sound:<id>` resolved offline, and the zoom's targetItemId
          names the adds[] index whose id is already in the agent's hand.
  CLOCK   a plan's timestamps are SOURCE seconds; a timeline `from` is
          TIMELINE frames. Emitting src_t0 as `from` once put 12 of 13 titles
          up to 13.6s late and stretched a 58.03s edit to 71.68s — both
          numbers plausible, both in seconds, in the same document.

Each leg is RED-proven against a mutated plan in the same run.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_for_chatcut as P                                   # noqa: E402

FPS = 30


def _beat(t0, t1, text, treatment=("text",), **kw):
    d = dict(kw)
    d.update({"treatment": list(treatment), "src_t0": t0, "src_t1": t1,
            "text_content": text, "size": "large", "case": "upper",
            "where": "lower_third_safe", "colour": "#FFFFFF", "hold_s": 2.0,
            "why": "smoke", "purpose": "hook"})
    return d


# THE REAL RECORD SHAPE, not a convenient one — this smoke exists to check the
# translator, and a fixture in a shape the translator never sees checks a
# different program. Two kept spans with a HOLE between them, so the source and
# timeline clocks cannot coincide by accident: that coincidence is the single
# commonest way a clock check passes while testing nothing.
PLAN = {
    "ledger": {"keep_spans": [[5.0, 10.0], [20.0, 25.0]],
               "source_duration_s": 30.0},
    "plan": [_beat(7.0, 9.0, "SEVEN"), _beat(22.0, 24.0, "TWENTY TWO"),
             # the two families that were never emitted at all, and are now the
             # two that must arrive PRE-RESOLVED.
             _beat(8.0, 8.5, None, ("sfx",), sfx_name="transition-sfx"),
             _beat(23.0, 24.0, None, ("zoom",), zoom_arc="payoff")],
}

WRITE_NAMES = {"from", "durationInFrames", "sourceStartFromInSeconds",
               "type", "assetId", "trackId", "propertyOverrides"}
READ_ONLY_NAMES = {"fromFrame", "toFrame", "timelineRange", "sourceRange",
                   "startSeconds", "endSeconds"}
# ...EXCEPT ON A LIBRARY SOUND. browse_library states the write shape itself:
# `edit_item adds:[{type:"audio",assetId:"library:sound:<id>",fromFrame:<n>}]`,
# and it is an ANCHOR, not a start — edit_item shifts the item so the sound's
# anchor lands there. Banning `fromFrame` outright would reject the one add
# that is spelled correctly, which is the same shape of error as a scanner that
# reads an object key as a variable: right about the vocabulary, wrong about
# the code. The exemption is scoped to the block, not to the name.
SOUND_WRITE_NAMES = {"fromFrame"}


def emit(plan):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(plan, fh)
    fh.close()
    try:
        return P.render(fh.name, staged=True)
    finally:
        os.unlink(fh.name)


def fields(txt):
    """Every `(key, value, assetId-of-enclosing-block)` inside an adds[] block.

    FOUR SPACES OR SIX. Video adds are indented one level and graphics two, so
    a `\\s{4}` anchor saw the segments and none of the graphics — and reported
    the CLOCK as broken on a translator that had mapped it correctly. Third
    time today that a scanner was wrong about correct code; the reader gets
    read as carefully as the thing it reads.
    """
    out, asset = [], ""
    for line in txt.splitlines():
        if re.search(r"\bedit_item adds\[\d+\]:", line):
            asset = ""
        m = re.match(r"^\s{4,8}(\w+)\s+:\s*(.+?)\s*$", line)
        if m:
            # trailing `(7.00s-9.00s, the hook beat)` is a human note, not part
            # of the value the agent copies
            v = re.sub(r"\s*\(.*$", "", m.group(2))
            if m.group(1) == "assetId":
                asset = v
            out.append((m.group(1), v, asset))
    return out


def legs(txt):
    f = fields(txt)
    bad = []

    # NAME — nothing from the READ vocabulary may appear as a field the agent
    # is told to write, unless the block is a library sound and the name is the
    # one that surface actually writes.
    for k, _v, asset in f:
        if k in READ_ONLY_NAMES:
            if k in SOUND_WRITE_NAMES and asset.startswith("library:sound:"):
                continue
            bad.append(("name", f"`{k}` is ChatCut's READ vocabulary, not write"))

    # ...and the inverse, which is the error that was actually shipped: a
    # library sound written with `from`. It would be accepted, land the item at
    # the beat, and put the audible hit LATE by the sound's own attack.
    for k, _v, asset in f:
        if k == "from" and asset.startswith("library:sound:"):
            bad.append(("name", "a library sound takes `fromFrame` (an "
                                "ANCHOR), not `from`"))
    if not any(a.startswith("library:sound:") for _k, _v, a in f):
        bad.append(("name", "no library sound reached the plan; the sfx leg "
                            "checked nothing"))

    # DISCOVERY — no id the agent is sent to find.
    for k, v, _a in f:
        if k == "assetId" and ("<id>" in v or "resolve the id" in v.lower()):
            bad.append(("discover", f"assetId is a placeholder: {v!r}"))
    # A PROHIBITION IS NOT AN INSTRUCTION. The plan says "DO NOT call
    # inspect_item, preview_timeline or read_project to find it" — a scanner
    # that matches the bare name calls that a discovery instruction and is
    # wrong about the one line whose whole job is to prevent discovery.
    # Scan per sentence, and skip any sentence that forbids.
    for _sent in re.split(r"(?<=[.\n])", txt):
        if re.search(r"\b(?:do not|don't|never|no need to|without)\b",
                     _sent, re.I):
            continue
        # ...and NAMING a tool is not sending the agent to it either. The
        # plan teaches the read-vs-write vocabulary with "`preview_timeline`
        # REPORTS ...", which is the sentence that PREVENTS a whole class of
        # error. What makes a mention a discovery instruction is that it is
        # told to go and get an ID.
        if not re.search(r"\b(id|ids|assetId|targetItemId|find|look ?up|"
                         r"search(?:ing)?|read it back|discover)\b",
                         _sent, re.I):
            continue
        for _call in ("browse_library", "inspect_item", "preview_timeline",
                      "read_project"):
            if re.search(r"\b%s\b" % _call, _sent):
                bad.append(("discover",
                            "the plan sends the agent to %s: %r"
                            % (_call, _sent.strip()[:90])))
    for k, v, _a in f:
        if k == "targetItemId" and not re.search(r"adds\[\d+\]", v):
            bad.append(("discover", "targetItemId does not name an adds[] "
                                    "index the agent already holds"))

    # UNIT — frames are integers, source offsets are seconds.
    for k, v, _a in f:
        if k in ("from", "durationInFrames", "fromFrame"):
            if not re.fullmatch(r"-?\d+", v):
                bad.append(("unit", f"`{k}` = {v!r} is not an integer frame"))
        if k == "sourceStartFromInSeconds":
            if not re.fullmatch(r"-?\d+\.\d+", v):
                bad.append(("unit", f"`{k}` = {v!r} is not decimal seconds"))

    # CLOCK — with keep = [5..10] and [20..25], a beat at source 7.0s is
    # timeline 2.0s = frame 60, and a beat at source 22.0s is timeline 7.0s =
    # frame 210. Emitting the SOURCE frame would give 210 and 660.
    froms = [int(v) for k, v, _a in f if k == "from"]
    if 210 in froms and 60 not in froms:
        bad.append(("clock", "a beat landed on its SOURCE frame, not timeline"))
    if 660 in froms:
        bad.append(("clock", "source seconds emitted as a timeline frame"))
    # the two video segments start at 0 and 150; the two graphics at 60 and 210
    for want in (0, 150, 60, 210):
        if want not in froms:
            bad.append(("clock", f"expected a `from` of {want}; got {froms}"))
    return bad


if __name__ == "__main__":
    txt = emit(PLAN)
    bad = legs(txt)
    for kind, why in bad:
        print("  [FAIL] %-6s %s" % (kind, why))
    if not bad:
        for k in ("name", "unit", "clock", "discover"):
            print("  [ok] every emitted field is right on %s" % k)

    print("\n  RED PROOF")
    red_ok = True
    # CLOCK: a translator that skips the source->timeline mapping.
    _real = P.render

    def _no_clock(path, **kw):
        # REGEX, NOT A SPACING-EXACT STRING. The first version hard-coded the
        # video add's column width and silently matched nothing in the graphic
        # blocks, so the RED proof reported 0 legs red and looked like a check
        # that could not fail.
        out = _real(path, **kw)
        return re.sub(r"(from\s+: )60\b", r"\g<1>210", out)
    P.render = _no_clock
    r1 = legs(emit(PLAN))
    P.render = _real
    print("    source frame as timeline -> %d leg(s) red" % len(r1))
    red_ok &= bool(r1)

    # UNIT: a frame emitted as seconds.
    def _sec(path, **kw):
        out = _real(path, **kw)
        return re.sub(r"(durationInFrames\s+: )150\b", r"\g<1>5.000", out)
    P.render = _sec
    r2 = legs(emit(PLAN))
    P.render = _real
    print("    frames emitted as seconds -> %d leg(s) red" % len(r2))
    red_ok &= bool(r2)

    # NAME: the read vocabulary leaking into a write instruction.
    def _read_vocab(path, **kw):
        out = _real(path, **kw)
        return re.sub(r"\bfrom(\s+: )", r"fromFrame\g<1>", out)
    P.render = _read_vocab
    r3 = legs(emit(PLAN))
    P.render = _real
    print("    read vocabulary in a write -> %d leg(s) red" % len(r3))
    red_ok &= bool(r3)

    # DISCOVERY — the three shapes that actually shipped, each restored.
    def _placeholder(path, **kw):
        out = _real(path, **kw)
        return re.sub(r"(assetId\s+: )library:sound:\S+.*",
                      r'\g<1>library:sound:<id> — resolve the id ONCE with '
                      r'browse_library category="sound-effects" searching '
                      r"'whoosh'", out)
    P.render = _placeholder
    r4 = legs(emit(PLAN))
    P.render = _real
    print("    sfx id left for the agent -> %d leg(s) red" % len(r4))
    red_ok &= bool(r4)

    def _bare_from(path, **kw):
        return re.sub(r"fromFrame(\s+): ", r"from\g<1>     : ", _real(path, **kw))
    P.render = _bare_from
    r5 = legs(emit(PLAN))
    P.render = _real
    print("    a library sound written with `from` -> %d leg(s) red" % len(r5))
    red_ok &= bool(r5)

    def _lookup(path, **kw):
        return re.sub(r"(targetItemId\s+: ).*",
                      r"\g<1>the id of the VIDEO item covering that frame — "
                      r"read it back with inspect_item", _real(path, **kw))
    P.render = _lookup
    r6 = legs(emit(PLAN))
    P.render = _real
    print("    zoom target left for the agent -> %d leg(s) red" % len(r6))
    red_ok &= bool(r6)

    ok = not bad and red_ok
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
