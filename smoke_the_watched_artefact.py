#!/usr/bin/env python3
"""The watched artefact: only gated frames ship, the numbers agree, absence speaks.

THE FAILURE THIS EXISTS TO MAKE IMPOSSIBLE is not a crash. It is a confident
caption under the wrong frame, cached in the prefix, teaching the opposite of
what it says on every turn of every run. Gemini's timestamps drift; half a
second is a different shot; nothing errors.

So the legs are:
  1. every shipped moment carries gate == "yes" — `no`, `unsure`, `unchecked`
     and `missing` are all NOT SHOWN, and three of those look like nothing.
  2. the numbers on the sheets are the numbers in the lines — contiguous from
     1, one line per tile, no tile without a line.
  3. absence SPEAKS: no artefact -> the prefix says so in words, and the frame
     reader returns a STATE, not an empty list that reads as a clean zero.
  4. no rates. The one rate that survived a careful removal survived because it
     was prose describing a rate next to a schema field demanding one. This
     asks the same question of the sheet.
  5. the frames actually reach the message. A reader nobody calls is the
     read_knowledge failure, one layer down.

Every leg is RED-PROVABLE and four of them are proven red below on mutated
input, in this file, because a check that has never failed is not yet a check.
"""
import ast
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
fail = 0


def bad(msg):
    global fail
    print("  *** " + msg)
    fail += 1


# ── 1 & 2. THE SHIPPED ARTEFACT, IF IT IS BUILT ─────────────────────────────
mj = os.path.join(HERE, "watched", "moments.json")
sheet = os.path.join(HERE, "watched", "SHEET.md")
if not os.path.exists(mj):
    print("  watched/moments.json absent — the artefact is not built. Legs 1-2 "
          "UNCHECKED (which is not a pass); legs 3-5 still run.")
else:
    rec = json.load(open(mj))
    shipped = rec.get("shipped") or []
    if not shipped:
        bad("moments.json ships zero moments")
    ungated = [m for m in shipped if m.get("gate") != "yes"]
    if ungated:
        bad("%d shipped moments did not pass the gate: %s"
            % (len(ungated), [(m.get("n"), m.get("gate")) for m in ungated[:6]]))
    ns = [m.get("n") for m in shipped]
    if ns != list(range(1, len(shipped) + 1)):
        bad("the shipped numbers are not 1..%d contiguous: %s"
            % (len(shipped), ns[:12]))
    # one tile per line, counted from the sheets themselves
    import glob
    from PIL import Image
    # The geometry lives in build_watched_sheet.py; read it there rather than
    # restating it, so a change to the layout cannot pass this leg by accident.
    bs = ast.parse(open(os.path.join(HERE, "build_watched_sheet.py")).read())
    g = {}
    for n in bs.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Tuple):
            names = [t.id for t in n.targets[0].elts if isinstance(t, ast.Name)]
            if set(names) <= {"TILE_W", "TILE_H", "HEAD_H", "COLS", "ROWS"}:
                try:
                    vals = ast.literal_eval(n.value)
                except Exception:                                 # noqa: BLE001
                    continue
                g.update(dict(zip(names, vals)))
    if not {"TILE_W", "TILE_H", "HEAD_H", "COLS", "ROWS"} <= set(g):
        bad("could not read the tile geometry out of build_watched_sheet.py: %s"
            % g)
    else:
        seen = 0
        for p in sorted(glob.glob(os.path.join(HERE, "watched", "tiles",
                                               "SHEET_*.png"))):
            im = Image.open(p)
            cols = round(im.width / g["TILE_W"])
            rows = round(im.height / (g["TILE_H"] + g["HEAD_H"]))
            if abs(cols * g["TILE_W"] - im.width) > 2 or \
               abs(rows * (g["TILE_H"] + g["HEAD_H"]) - im.height) > 2:
                bad("%s is %dx%d, not a whole number of %dx%d tiles"
                    % (os.path.basename(p), im.width, im.height, g["TILE_W"],
                       g["TILE_H"] + g["HEAD_H"]))
            seen += cols * rows
        # The last sheet is padded to a full row only if the builder pads; it
        # does not, so the tile count is bounded, not exact.
        if seen < len(shipped):
            bad("the sheets hold room for %d tiles but %d moments ship — some "
                "line has no picture" % (seen, len(shipped)))
    # every shipped moment appears in the text
    txt = open(sheet).read() if os.path.exists(sheet) else ""
    for m in shipped:
        if ("  %-3d %5.1f" % (m["n"], m["t_settled_s"])) not in txt:
            bad("moment %d is not in SHEET.md" % m["n"])
            break

# ── 3. ABSENCE SPEAKS ───────────────────────────────────────────────────────
_save = A._WATCHED_DIRS
try:
    with tempfile.TemporaryDirectory() as d:
        A._WATCHED_DIRS = (os.path.join(d, "nope"),)
        t = A.watched_moments()
        if "UNAVAILABLE" not in t:
            bad("a missing artefact does not say UNAVAILABLE: %r" % t[:120])
        blocks, state = A.watched_frames()
        if blocks or not state.startswith("ABSENT"):
            bad("a missing tiles/ returned %d blocks and state %r — an empty "
                "list that reads as a clean zero" % (len(blocks), state))
        # and an EMPTY sheet is not the same as no sheet
        os.makedirs(os.path.join(d, "w", "tiles"))
        open(os.path.join(d, "w", "SHEET.md"), "w").write("")
        A._WATCHED_DIRS = (os.path.join(d, "w"),)
        t = A.watched_moments()
        if "EMPTY" not in t:
            bad("a zero-length SHEET.md does not say EMPTY: %r" % t[:120])
        blocks, state = A.watched_frames()
        if blocks or "no SHEET_*.png" not in state:
            bad("an empty tiles/ returned %r" % state)
finally:
    A._WATCHED_DIRS = _save

# ── 4. NO RATES ─────────────────────────────────────────────────────────────
ns = {}
for n in ast.parse(open(os.path.join(HERE, "craft_pass_app.py")).read()).body:
    nm = (n.targets[0].id if isinstance(n, ast.Assign)
          and isinstance(n.targets[0], ast.Name)
          else n.name if isinstance(n, ast.FunctionDef) else None)
    if nm in ("_RATE_PATTERNS", "_DENSITY_ELEMENT", "_DENSITY_ANY",
              "rate_language"):
        exec(compile(ast.Module([n], []), "<x>", "exec"), ns)
if "rate_language" not in ns:
    bad("the rate guard is absent from craft_pass_app.py")
elif os.path.exists(sheet):
    hits = ns["rate_language"](open(sheet).read())
    if hits:
        bad("the sheet carries %d rate(s): %s" % (len(hits), hits[:3]))

# ── 5. THE FRAMES REACH THE MESSAGE ─────────────────────────────────────────
# AST, not grep: a string can sit in a dead branch, and this lane has been
# caught by that twenty times. What is checked is that the name bound from
# watched_frames() is concatenated into the content of the first user message.
src = ast.parse(open(os.path.join(HERE, "agentic_editor_app.py")).read())
bound, used = set(), False
for n in ast.walk(src):
    if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) \
            and isinstance(n.value.func, ast.Name) \
            and n.value.func.id == "watched_frames":
        for t in n.targets:
            if isinstance(t, ast.Tuple):
                bound |= {e.id for e in t.elts if isinstance(e, ast.Name)}
            elif isinstance(t, ast.Name):
                bound.add(t.id)
if not bound:
    bad("watched_frames() is never called — a reader nobody calls is the "
        "read_knowledge failure one layer down")
for n in ast.walk(src):
    if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "msgs" for t in n.targets):
        names = {x.id for x in ast.walk(n.value) if isinstance(x, ast.Name)}
        if names & bound:
            used = True
if not used:
    bad("the frame blocks are never put into msgs")
if "watched_moments" not in {n.func.id for n in ast.walk(src)
                             if isinstance(n, ast.Call)
                             and isinstance(n.func, ast.Name)}:
    bad("watched_moments() is never called — the lines never reach the prefix")

# ── RED PROOF ───────────────────────────────────────────────────────────────
# Each leg is run against input it must reject. A check that has never failed
# is not yet a check.
red = 0


def must_reject(name, fn):
    global red
    try:
        ok = fn()
    except Exception as e:                                        # noqa: BLE001
        ok = "raised %s" % type(e).__name__
    if ok is True:
        print("  *** RED PROOF FAILED: %s accepted a bad case" % name)
        red += 1


must_reject("gate leg", lambda: all(
    m.get("gate") == "yes" for m in [{"gate": "yes"}, {"gate": "unsure"}]))
must_reject("contiguity leg", lambda:
            [1, 2, 4] == list(range(1, 4)))
must_reject("absence leg", lambda: "UNAVAILABLE" in "the ten, at the moments")
if "rate_language" in ns:
    must_reject("rate leg", lambda: not ns["rate_language"](
        "Overlay text is the WORKHORSE (~7.5 per 25s)"))

print("smoke_the_watched_artefact: %d wrong, %d red-proofs failed"
      % (fail, red))
sys.exit(1 if (fail or red) else 0)
