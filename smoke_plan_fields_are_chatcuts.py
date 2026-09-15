#!/usr/bin/env python3
"""SMOKE — every time field the plan emits is in ChatCut's NAME, UNIT and CLOCK.

THE THREE TRAPS, ALL OF WHICH HAVE ALREADY FIRED HERE:

  NAME    ChatCut READS `timelineRange.fromFrame` / `toFrame` and WRITES
          `from` / `durationInFrames`. Two vocabularies for one timeline, and
          the read one is the one you see first in every tool result.
  UNIT    `toFrame` is a POSITION and `durationInFrames` is a LENGTH. Passing
          one as the other puts every item at the wrong end of itself.
          Source offsets are SECONDS in the same call that takes frames.
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


def _beat(t0, t1, text):
    return {"treatment": ["text"], "src_t0": t0, "src_t1": t1,
            "text_content": text, "size": "large", "case": "upper",
            "where": "lower_third_safe", "colour": "#FFFFFF", "hold_s": 2.0,
            "why": "smoke", "purpose": "hook"}


# THE REAL RECORD SHAPE, not a convenient one — this smoke exists to check the
# translator, and a fixture in a shape the translator never sees checks a
# different program. Two kept spans with a HOLE between them, so the source and
# timeline clocks cannot coincide by accident: that coincidence is the single
# commonest way a clock check passes while testing nothing.
PLAN = {
    "ledger": {"keep_spans": [[5.0, 10.0], [20.0, 25.0]],
               "source_duration_s": 30.0},
    "plan": [_beat(7.0, 9.0, "SEVEN"), _beat(22.0, 24.0, "TWENTY TWO")],
}

WRITE_NAMES = {"from", "durationInFrames", "sourceStartFromInSeconds",
               "type", "assetId", "trackId", "propertyOverrides"}
READ_ONLY_NAMES = {"fromFrame", "toFrame", "timelineRange", "sourceRange",
                   "startSeconds", "endSeconds"}


def emit(plan):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(plan, fh)
    fh.close()
    try:
        return P.render(fh.name, staged=True)
    finally:
        os.unlink(fh.name)


def fields(txt):
    """Every `key : value` the plan emits inside an adds[] block.

    FOUR SPACES OR SIX. Video adds are indented one level and graphics two, so
    a `\\s{4}` anchor saw the segments and none of the graphics — and reported
    the CLOCK as broken on a translator that had mapped it correctly. Third
    time today that a scanner was wrong about correct code; the reader gets
    read as carefully as the thing it reads.
    """
    out = []
    for line in txt.splitlines():
        m = re.match(r"^\s{4,8}(\w+)\s+:\s*(.+?)\s*$", line)
        if m:
            # trailing `(7.00s-9.00s, the hook beat)` is a human note, not part
            # of the value the agent copies
            out.append((m.group(1), re.sub(r"\s*\(.*$", "", m.group(2))))
    return out


def legs(txt):
    f = fields(txt)
    names = [k for k, _ in f]
    bad = []

    # NAME — nothing from the READ vocabulary may appear as a field the agent
    # is told to write.
    for k in names:
        if k in READ_ONLY_NAMES:
            bad.append(("name", f"`{k}` is ChatCut's READ vocabulary, not write"))

    # UNIT — frames are integers, source offsets are seconds.
    for k, v in f:
        if k in ("from", "durationInFrames"):
            if not re.fullmatch(r"-?\d+", v):
                bad.append(("unit", f"`{k}` = {v!r} is not an integer frame"))
        if k == "sourceStartFromInSeconds":
            if not re.fullmatch(r"-?\d+\.\d+", v):
                bad.append(("unit", f"`{k}` = {v!r} is not decimal seconds"))

    # CLOCK — with keep = [5..10] and [20..25], a beat at source 7.0s is
    # timeline 2.0s = frame 60, and a beat at source 22.0s is timeline 7.0s =
    # frame 210. Emitting the SOURCE frame would give 210 and 660.
    froms = [int(v) for k, v in f if k == "from"]
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
        for k in ("name", "unit", "clock"):
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

    ok = not bad and red_ok
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
