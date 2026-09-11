#!/usr/bin/env python3
"""THE GATE'S COST IS SPLIT OUT OF THE PRODUCT'S, and the split is PRINTED.

WHY. Round 46: motion ran 628.7s against a 120s law and build_zoom was 578.92s
of it — 92.1% — for EIGHT zooms on a 540x960 source. 72s per zoom to crop and
scale half a second of tiny video is not a plausible render cost, and the stage
timer could not say what it was, because every verification pass this lane added
runs INSIDE the timed stage: a PSNR pass per zoom, two per placement, and an
ffprobe -count_frames that decodes the whole file.

So "the pipeline is 5x over the latency law" and "the gate measuring it is 5x
over the latency law" were the same number, and the speed pillar was being
reported off a total nobody had decomposed.

FOUR LEGS, because there are four ways to ship this useless:

  WRAPPED   every verification helper is counted. A new one that forgets to
            account for itself makes the product look faster than it is.
  RESET     _INSTRUMENT_S is a module global and Modal REUSES containers. Run
            two of a warm container would otherwise carry run one's gate cost.
  LEDGERED  the number reaches the ledger.
  PRINTED   and it is printed. A counter that reaches the ledger and no output
            answers nothing — this repo has done that three times in one
            session, each with the diagnosis fresh from the last one.

  python3 smoke_instrument_split.py     exit 0 = the split exists and is visible
"""
import ast
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "agentic_editor_app.py")
SRC = open(APP, encoding="utf-8").read()
TREE = ast.parse(SRC)
FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as app                                  # noqa: E402

# ── LEG 1: WRAPPED ─────────────────────────────────────────────────────────
# The helpers whose ONLY job is to verify something already built. Anything
# added to this list must be genuinely gate-only: mis-labelling moves cost off
# the product, which is the flattering direction.
MEASURERS = ("region_psnr", "zoom_scale_fit_delta", "step_changed_audio",
             "_probe_frame_count", "alpha_paint_box")
for nm in MEASURERS:
    fn = getattr(app, nm, None)
    ok(fn is not None, f"{nm} does not exist — the wrap list is stale")
    ok(getattr(fn, "__wrapped__", None) is not None,
       f"{nm} is NOT instrumented — its ffmpeg/ffprobe time is being billed to "
       f"the product stage it runs inside, and the 120s number is wrong by "
       f"however long it takes")

# PRODUCT COST MUST NOT BE LAUNDERED INTO THE GATE. detect_shot_changes feeds
# beat subdivision, so it is the product paying for a decision, not the gate
# checking one. If it ever gets wrapped, the product number improves for free.
_ds = getattr(app, "detect_shot_changes", None)
ok(_ds is not None and getattr(_ds, "__wrapped__", None) is None,
   "detect_shot_changes is instrumented — it feeds beat subdivision, so that "
   "attributes PRODUCT cost to the gate and flatters the latency number")

# ── LEG 2: RESET PER RUN ───────────────────────────────────────────────────
_edit = next((n for n in ast.walk(TREE)
              if isinstance(n, ast.FunctionDef) and n.name == "edit"), None)
ok(_edit is not None, "edit() is gone")
if _edit is not None:
    _clears = [n for n in ast.walk(_edit)
               if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute)
               and n.func.attr == "clear"
               and getattr(n.func.value, "id", "") == "_INSTRUMENT_S"]
    ok(_clears,
       "edit() never calls _INSTRUMENT_S.clear() — a Modal container is REUSED, "
       "so the second run in a warm container reports the first run's gate cost "
       "on top of its own")

# ── LEG 3: LEDGERED ────────────────────────────────────────────────────────
ok('led["instrument_s"]' in SRC,
   "instrument_s never reaches the ledger — the accumulator counts and nothing "
   "reads it")

# ── LEG 4: PRINTED ─────────────────────────────────────────────────────────
ok("PRODUCT WALL" in SRC
   and "of which INSTRUMENT (verification, not product)" in SRC,
   "the product/gate split is never PRINTED — a counter in the ledger and "
   "nowhere else answers no question anyone can ask")
# And ABSENT must be printed as absent, never as a free gate.
ok("UNMEASURED (accumulator empty" in SRC,
   "an empty accumulator prints nothing distinguishable from a zero-cost gate — "
   "absence must never render as success")

# ── the accumulator actually accumulates ───────────────────────────────────
app._INSTRUMENT_S.clear()
app._probe_frame_count("/nonexistent-for-this-check.mp4")
ok(app._INSTRUMENT_S.get("_probe_frame_count") is not None,
   f"a wrapped call did not record itself: {app._INSTRUMENT_S}")

print()
if FAIL:
    for m in FAIL:
        print(f"  [FAIL] {m}")
    print(f"\n{len(FAIL)} failure(s)")
    sys.exit(1)
print(f"ok smoke_instrument_split — {len(MEASURERS)} measurers wrapped, reset "
      f"per run, ledgered and printed")
