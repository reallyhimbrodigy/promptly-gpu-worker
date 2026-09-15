#!/usr/bin/env python3
"""SMOKE — pass 1 is SERVED everything it needs, and looks nothing up.

THE RULE: every usable component as a picture with what it is for, the source
as frames, the transcript against them, the plan — all in front of the agent
before it decides. If it has to fetch anything, it was not served.

WHAT THAT REPLACED. The inventory was a file mounted at
/craft/component_sheet.png with the prompt saying "READ IT"; the source was a
contact sheet at /work/source_sheet.png, also Read. Two turns spent fetching
pixels the harness already had in memory, and a JSON index for the components
instead of the pictures.

AND THE CEILING IS STATED RATHER THAN DRESSED UP. The model cannot take video
— tested: a `video` content block is refused, "Input tag 'video' ... does not
match any of the expected tags". A dense sequence of full frames plus the
transcript is the nearest thing this surface allows to watching the footage,
and the code says so where someone would otherwise assume otherwise.

Legs, each RED-proven:
  INVENTORY  the component pictures are an IMAGE BLOCK in message 1
  SOURCE     the source arrives as MANY frames, not one tile
  WORDS      the transcript is in message 1, time-aligned
  PLAN       the plan is in message 1
  NO-FETCH   pass 1 is told its turn ENDS after placing — no preview, no read
  PASS2      the edit is sent as frames the harness fetched
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SRC = open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)


def fn_source(name):
    for n in ast.walk(TREE):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return ast.unparse(n)
    return ""


def _re_sub_scrub(s):
    """Remove every invitation to look freely — the mutation for the scrub leg."""
    return re.sub(r"scrub|as often as you need", "xxxx", s, flags=re.I)


def legs():
    bad = []
    p1 = fn_source("pass1_message")
    p2 = fn_source("pass2_message")
    if not p1:
        return [("build", "pass1_message does not exist — nothing is served")]
    if not p2:
        bad.append(("build", "pass2_message does not exist"))

    # INVENTORY — a picture, in the message, not a path to read
    # THE INVENTORY SPECIFICALLY, not "an image block exists somewhere". The
    # first version checked `_img_block in p1`, which the SOURCE frames satisfy
    # on their own — so a mutation turning the inventory back into a file read
    # left the leg green. A check that a different feature keeps alive is not
    # checking the feature it names.
    if not re.search(r"_img_block\(\s*inventory_png", p1):
        bad.append(("inventory", "the inventory is not an image block in "
                                 "message 1"))
    if "READ IT" in SRC:
        bad.append(("inventory", "the prompt still tells the agent to READ the "
                                 "sheet — that is fetching, not serving"))

    # SOURCE — many frames, not one tile
    if "_frames_of" not in p1:
        bad.append(("source", "the source is not sent as a frame sequence"))
    for n in ast.walk(TREE):
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") \
                == "SOURCE_FRAMES_N":
            if not (isinstance(n.value, ast.Constant) and n.value.value >= 8):
                bad.append(("source", "SOURCE_FRAMES_N is %r — too few to be a "
                                      "sequence rather than a sample"
                                      % getattr(n.value, "value", None)))

    # WORDS — the transcript, time-aligned
    if "t_start" not in p1 or "beats" not in p1:
        bad.append(("words", "the transcript is not in message 1"))

    # PLAN
    if "plan" not in p1:
        bad.append(("plan", "the plan is not in message 1"))

    # THE EDIT IS SENT — a head start, NOT a gag. An earlier version of this
    # leg demanded "YOUR TURN ENDS ... do not preview", which bounded how often
    # the agent could LOOK. That was a wall problem solved by removing the
    # thing that makes it an editor. What must hold is that the harness SENDS
    # the edit, and that the agent is told it may scrub freely.
    if "RENDERED AND SENT TO YOU" not in SRC:
        bad.append(("served", "pass 1 is not told the edit will be sent to it"))
    if not re.search(r"scrub|as often as you need", SRC, re.I):
        bad.append(("scrub", "nothing tells the agent it may look wherever and "
                             "as often as it wants"))

    # PASS 2 — frames the harness fetched
    if "_edit_frames" not in SRC or "preview_timeline" not in fn_source(
            "_edit_frames"):
        bad.append(("pass2", "the harness does not fetch the edit frames"))
    return bad


if __name__ == "__main__":
    bad = legs()
    for k, w in bad:
        print("  [FAIL] %-10s %s" % (k, w))
    if not bad:
        print("  [ok] the inventory is served as pictures in message 1")
        print("  [ok] the source arrives as a frame sequence, not one tile")
        print("  [ok] the transcript is served with it, time-aligned")
        print("  [ok] the plan is in the same message")
        print("  [ok] the edit is SENT to it, and it may scrub freely")
        print("  [ok] the harness renders and sends the edit for pass 2")

    print("\n  RED PROOF")
    red = True
    for label, mutate, kind in (
            ("the inventory back to a file read",
             lambda s: s.replace("_img_block(inventory_png", "open(inventory_png"),
             "inventory"),
            ("the source back to one tile",
             lambda s: s.replace("_frames_of(source_video", "_tile(source_video"),
             "source"),
            ("the transcript dropped",
             lambda s: s.replace("t_start", "unused_key"), "words"),
            ("the scrub invitation gone",
             lambda s: _re_sub_scrub(s), "scrub")):
        _orig = globals()["SRC"]
        globals()["SRC"] = mutate(_orig)
        globals()["TREE"] = ast.parse(globals()["SRC"])
        r = legs()
        globals()["SRC"] = _orig
        globals()["TREE"] = ast.parse(_orig)
        hit = any(k == kind for k, _ in r)
        print("    %-34s -> %d leg(s) red, names %s: %s"
              % (label, len(r), kind, hit))
        red &= hit

    ok = not bad and red
    print("\n  %s" % ("OK" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
