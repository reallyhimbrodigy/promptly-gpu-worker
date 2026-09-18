#!/usr/bin/env python3
"""THE WATCHED ARTEFACT — the ten reference edits, as the standard, in one place.

EXTRACTED 2026-09-16 when Zac ruled the single agent: "One session: watches the
source, HAS THE REFERENCES CACHED, decides, places, looks, fixes, exports."

The ChatCut session is now the only agent, so it needs the reference standard
the planner used to hold — and copying the rubric and the tile-ordering rule
across would be two copies of a rule, which is how a rule ends up enforced on
one of them. Both images mount this module and both read the same artefact.

WHAT IS A RULE HERE AND MUST NOT BE RETYPED, rather than mere file reading:
  * the RUBRIC, which changes how everything under it is read — the same sheet
    is either a set of examples or the bar, and only one of those makes an
    agent compare its own output against them
  * the TILE ORDER. STRIP_ sheets come first and globbing SHEET_* alone would
    show the agent none of the strips — a producer with no consumer, in the
    half of the artefact that exists because one frame was not enough.

THE ABLATION SWITCH STAYS WITH THE PLANNER. `prefix_material_enabled` reads
os.environ in whichever process calls it, and an observable must be computed on
the side of the boundary it describes — so this module never consults it, and
each caller applies its own removal in its own container.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_WATCHED_DIR = os.path.join(_HERE, "watched")


# error, it produces a confident caption under the wrong shot — which would
# then teach the opposite of what it says, on every turn, from inside the
# cache.
_WATCHED_DIRS = ("/watched", _WATCHED_DIR)


def _watched_path(*parts):
    for _d in _WATCHED_DIRS:
        _p = os.path.join(_d, *parts)
        if os.path.exists(_p):
            return _p
    return None


# WHAT THE REFERENCES ARE, SAID ONCE, PLAINLY, WHERE THE PLANNER READS IT.
#
# Zac, 2026-09-15: "Not moments with reasons — the rubric. These are finished
# edits at the standard every output is held to; the density, the placement and
# the restraint are the bar." It is a one-line framing gap and it may be why
# the copy comes out generic: the sheet said "this is what an editor did at a
# specific moment", which reads as INTERESTING REFERENCE. Nothing said it was
# the LEVEL. An agent shown ten good edits and not told they are the bar will
# produce something adjacent to them and call it done.
#
# NO NUMBERS IN HERE, DELIBERATELY. This repo's standing law is that the
# density rates GRADE and never instruct — they must never reach the agent as a
# target or a floor, and one sentence describing a rate survived a careful
# removal precisely because prose about a rate looks harmless. Saying the ten
# ARE the bar does not require quoting one: the sheets show how much these
# videos place, where, and what they leave alone. The bar is visible in them.
_REFERENCE_RUBRIC = (
    "THE TEN BELOW ARE THE STANDARD. Not inspiration, not a mood board, not a "
    "library to browse — they are FINISHED EDITS at the level every output of "
    "this pipeline is held to, chosen by the person whose product this is.\n"
    "\n"
    "Your edit is judged against them. Three things in particular, and they "
    "are all visible in the frames:\n"
    "  HOW MUCH THEY PLACE — these videos are not quiet. Look at how often "
    "something arrives on screen, and how rarely a beat is left bare by "
    "accident.\n"
    "  WHERE IT SITS — the band, the size, the relationship to the speaker's "
    "face and to the words already burned into the frame.\n"
    "  WHAT THEY LEAVE ALONE — the restraint moments are not gaps. Every one "
    "of them is a place a competent editor would have reached for something "
    "and this one did not, ON PURPOSE, and the video is better for it.\n"
    "\n"
    "An edit that is quieter than these is under the bar, not tasteful. An "
    "edit that places something everywhere is not at the bar either — the "
    "restraint is half of what you are looking at. Rule against what these "
    "actually do, not against what a cautious editor would do.\n")


def watched_moments():
    """The rubric, then the glanceable lines. Absence is SPOKEN, never omitted.

    The RUBRIC leads because it changes how everything under it is read: the
    same sheet is either a set of examples or the bar, and only one of those
    makes an agent compare its own output against them.
    """
    _p = _watched_path("SHEET.md")
    if not _p:
        return ("THE TEN, AT THE MOMENTS THAT MATTER: UNAVAILABLE — no "
                "SHEET.md under %s. You are ruling without the examples."
                % " or ".join(_WATCHED_DIRS))
    try:
        _t = open(_p, encoding="utf-8").read().strip()
    except Exception as _e:                                       # noqa: BLE001
        return ("THE TEN, AT THE MOMENTS THAT MATTER: UNREADABLE — %s: %s"
                % (_p, _e))
    if not _t:
        return ("THE TEN, AT THE MOMENTS THAT MATTER: EMPTY — %s is a "
                "zero-length file, which is not the same as no examples "
                "existing." % _p)
    return _REFERENCE_RUBRIC + "\n" + _t


def watched_frames():
    """(blocks, state). The sheets as Anthropic image blocks, in tile order.

    Returns a STATE beside the blocks so the caller records ABSENT rather than
    reporting an empty list as a successful zero — the class this lane has paid
    for four times in one day.
    """
    import base64
    import glob
    _d = _watched_path("tiles")
    if not _d:
        return [], "ABSENT: no tiles/ under %s" % " or ".join(_WATCHED_DIRS)
    # BOTH KINDS, AND THE STRIPS FIRST. A SHEET_ is single settled frames; a
    # STRIP_ is rows of five frames through a change — a cut, a transition, a
    # sound landing — which one settled frame cannot show. Globbing SHEET_*
    # alone would have mounted the strips into the image and shown the agent
    # none of them: a producer with no consumer, in the half of the artefact
    # that exists because one frame was not enough.
    _files = sorted(glob.glob(os.path.join(_d, "STRIP_*.png"))) + \
        sorted(glob.glob(os.path.join(_d, "SHEET_*.png")))
    _files = sorted(_files, key=lambda p: (os.path.basename(p)[:5],
                                           int("".join(c for c in
                                                       os.path.basename(p)
                                                       if c.isdigit()) or 0)))
    if not _files:
        return [], "ABSENT: %s holds no SHEET_*.png or STRIP_*.png" % _d
    _blocks = []
    for _f in _files:
        try:
            _b = open(_f, "rb").read()
        except Exception as _e:                                   # noqa: BLE001
            return [], "FAILED: %s: %s" % (_f, _e)
        if not _b:
            return [], "FAILED: %s is zero bytes" % _f
        _blocks.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/png",
                                   "data": base64.b64encode(_b).decode()}})
    _ns = sum(1 for f in _files if os.path.basename(f).startswith("STRIP_"))
    return _blocks, "MEASURED: %d sheet(s) (%d strip, %d frame), %d KB" % (
        len(_files), _ns, len(_files) - _ns,
        sum(os.path.getsize(f) for f in _files) // 1024)
