#!/usr/bin/env python3
"""Did the edit open on the hook, or on something placed in front of it?

THE DEFECT, MEASURED. The ChatCut arm protected every word of the hook from
being cut and then opened the edit on 1.7s of a dark title card. Mean luma 13.9
at t=0 against 125.7 for the run that did not do it. The hook survived intact
and the viewer still met something else first — a loss delivered by a route the
rule did not name.

WHY LUMA AND NOT "IS THERE AN ITEM AT FRAME 0". A card at frame 0 is not
automatically wrong: a bright full-frame title that IS the hook is a real
editorial choice, and a rule against any first item would forbid it. What is
always wrong is the viewer meeting DEAD SCREEN. So the question asked here is
the one the viewer experiences: does the output open substantially darker than
the source it came from?

THREE STATES. A source we cannot read is ABSENT, never "fine".
"""
import subprocess
import sys


def mean_luma(path, t=0.0):
    """Mean luma 0-255 at t seconds, or None. None is ABSENT, not 0."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1",
         "-vf", "scale=64:64,format=gray", "-f", "rawvideo", "-"],
        capture_output=True, timeout=60)
    if r.returncode != 0 or not r.stdout:
        return None
    return round(sum(r.stdout) / len(r.stdout), 1)


def opening_state(src, out, floor=40.0, drop=0.45, probe_s=(0.0, 0.5, 1.0)):
    """(state, why). MEASURED | BURIED | ABSENT.

    BURIED when the output's opening is both dark in absolute terms AND much
    darker than the source's own opening. Both arms matter: a legitimately dark
    source must not be flagged, and a bright source that opens on black must be.
    """
    s_vals = [v for v in (mean_luma(src, t) for t in probe_s) if v is not None]
    o_vals = [v for v in (mean_luma(out, t) for t in probe_s) if v is not None]
    if not s_vals or not o_vals:
        return ("ABSENT",
                f"could not read an opening frame (source {len(s_vals)}/3, "
                f"output {len(o_vals)}/3) — ABSENT, not clean")
    s_open = max(s_vals)
    o_open = max(o_vals)
    if o_open < floor and o_open < s_open * drop:
        return ("BURIED",
                f"the edit opens at luma {o_open} against the source's "
                f"{s_open} — the first thing the viewer meets is not the hook. "
                f"A protected position can be buried as well as cut.")
    return ("MEASURED",
            f"opening luma {o_open} vs source {s_open} — the edit opens on "
            f"picture, not on a pre-roll")


def tail_state(out, floor=40.0, tail_s=2.5, probe_n=4):
    """(state, why) — does the edit END on dead screen? MEASURED | DEAD | ABSENT.

    THE OTHER EDGE, AND THE ONE A FORCED LOOK DID NOT CATCH. The Haiku arm was
    handed a 20-frame contact sheet whose last three tiles are pure TikTok app
    chrome. The harness gate confirmed it READ the sheet and previewed before
    rendering — read_source_sheet True, previewed_before_render True, state
    MEASURED — and it still shipped 4.4s of app UI on the end and cut nothing
    at all.

    THAT IS THE LESSON: the gate proved the LOOK happened, not that the look
    was USED. A check on behaviour is not a check on outcome, and the two are
    indistinguishable from the ledger. So this asks the delivered file the
    question the viewer answers — does it end on nothing?

    PROVISIONAL, AND THE LIMIT IS NAMED. Run across four delivered arms it
    flags three, and one of those is a DELIBERATE dark close card (the 840s
    Sonnet run trimmed the app chrome and then ended on its own navy card,
    luma 25-26). Luma alone cannot tell a branded close card from leftover app
    UI — both are dark — so this REPORTS rather than gates. Shipping it as a
    hard gate would be the corpus-gate failure this repo has already paid for:
    a threshold that learns one population and rejects real work.

    It also corrects something I reported earlier: I said the 840s run handled
    the tail correctly. It removed the artifact and then ended on dead screen
    by another route, which is the burial lesson pointing at the other edge.
    """
    d = _duration(out)
    if d is None:
        return ("ABSENT", f"could not read the duration of {out}")
    span = min(tail_s, d / 2.0)
    ts = [d - span * (i + 0.5) / probe_n for i in range(probe_n)]
    vals = [v for v in (mean_luma(out, t) for t in reversed(ts)) if v is not None]
    if not vals:
        return ("ABSENT", "could not read any tail frame — ABSENT, not clean")
    if max(vals) < floor:
        return ("DEAD",
                f"the last {span:.1f}s reads {vals} — the edit ends on dead "
                f"screen. Nothing after the final word earns its place.")
    return ("MEASURED", f"the last {span:.1f}s reads {vals} — the edit ends on "
                        f"picture")


def _duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, timeout=60)
    try:
        return float((r.stdout or "").strip())
    except ValueError:
        return None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: opening_not_buried.py SOURCE OUTPUT")
    st, why = opening_state(sys.argv[1], sys.argv[2])
    print(f"  OPEN  {st}: {why}")
    st2, why2 = tail_state(sys.argv[2])
    print(f"  TAIL  {st2}: {why2}")
    # ONLY the opening check gates. The tail check reports — see tail_state.
    sys.exit(1 if st == "BURIED" else 0)
