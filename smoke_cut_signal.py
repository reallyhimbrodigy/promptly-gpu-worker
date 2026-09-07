"""SMOKE — the no-speech route has a cut signal, and it is not stillness alone.

MEASURED, round 17 and the three-arm check. visual_cut_candidates returned
0 spans on FOUR OF FIVE no-speech fixtures, after which the prompt told the
agent, verbatim:

    (none — this clip is evenly paced; cut on shot changes or not at all)

The agent obeyed. cut came back 0.00 on every no-speech arm INCLUDING one
briefed "hard cuts, maximum energy" — and 0.00 on the minimal arm too, so the
brief could not move it either.

TWO DEFECTS, and the second is the one that matters:

  1. Stillness is the wrong signal for these sources. visual_cut_candidates is
     MEDIAN-RELATIVE (quiet_frac 0.35), so continuously-moving footage — a pet
     video, music, a screen recording — never drops below 35% of its own median
     and correctly returns nothing. That is the detector working, not failing.

  2. The fallback it named was never wired. beats_from_visual documents its
     boundaries as motion resolves UNIONED WITH shot changes, and
     segment_beats_visual was called WITHOUT shot_changes — so the union was
     resolves alone. probe_source can detect them, but it is a TOOL: it runs
     only if the agent calls it, and by then the beats are already cut.

     The prompt was pointing at a signal that did not exist.
"""
import ast
import sys

FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)
SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)

# ── the detector is module-level, callable before the agent runs ──────────
_top = {n.name for n in TREE.body if isinstance(n, ast.FunctionDef)}
ok("detect_shot_changes" in _top,
   "detect_shot_changes is not module-level — shot detection lives only inside "
   "probe_source, which is a TOOL and runs only if the agent calls it, after "
   "the beats are already cut")

# ── it is CALLED, and its result reaches beat extraction ─────────────────
_calls = [n for n in ast.walk(TREE)
          if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "detect_shot_changes"]
ok(len(_calls) >= 1, "nothing calls detect_shot_changes")

_sbv = [n for n in ast.walk(TREE)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "segment_beats_visual"]
ok(len(_sbv) >= 1, "segment_beats_visual is never called")
for c in _sbv:
    ok(any(k.arg == "shot_changes" for k in c.keywords),
       f"segment_beats_visual at line {c.lineno} is called WITHOUT shot_changes — "
       f"beats_from_visual's documented union of resolves AND shot changes is "
       f"resolves alone, which is the round-17 defect exactly")

# ── the union actually uses them ─────────────────────────────────────────
_bfv = next((n for n in TREE.body
             if isinstance(n, ast.FunctionDef) and n.name == "beats_from_visual"), None)
ok(_bfv is not None, "beats_from_visual not found")
if _bfv:
    ok("shot_changes" in ast.dump(_bfv),
       "beats_from_visual ignores its shot_changes argument")

# ── THE PROMPT MUST NOT NAME A SIGNAL IT DOES NOT PROVIDE ────────────────
ok("cut on shot changes or not at all" not in SRC,
   "the prompt still tells the agent to 'cut on shot changes' in the branch "
   "where no shot changes were computed — advice pointing at nothing, which is "
   "what produced cut=0.00 under a hard-cuts brief")
ok("HARD CUTS ALREADY DETECTED" in SRC,
   "shot changes are detected but never OFFERED to the agent — a signal the "
   "agent cannot see is a signal that does not exist")
ok("led[\"shot_changes\"] = _shots" in SRC,
   "shot changes are not ledgered, so the prompt block and the printer have "
   "nothing to read")

# ── AND PRINTED, beside stillness ────────────────────────────────────────
ok("SHOT CHANGES    :" in SRC,
   "shot changes are not printed — '0 stillness spans' was read as 'no cut "
   "signal' precisely because the other signal was invisible")
ok("evenly paced — nothing to cut on" not in SRC,
   "the printer still says 'nothing to cut on' when stillness is empty; that "
   "conflates one detector finding nothing with there being nothing to find")

if FAIL:
    print("FAIL smoke_cut_signal:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_cut_signal — shot changes detected before beats, unioned into "
      "the boundaries, offered in the prompt and printed beside stillness")
