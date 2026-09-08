#!/usr/bin/env python3
"""SMOKE: the seven zooms are WIRED, back-timed, and proven on pixels.

The tables were pinned and DARK for one commit — defined, asserted at import,
and called by nothing while execute_plan still ran a single generic 1.12x
zoompan. This is the file that stops that state coming back.

THE FAILURE THIS FAMILY HAS THAT NO OTHER FAMILY HAS.
ClipRenderer mounts a zoom component only under
`if (clip.zoomEffect && clip.src)`. Without a pre-extracted per-clip file it
falls through to a plain <Video> and renders the footage UN-ZOOMED — right frame
count, right duration, real footage, no error. Measured while probing paint
rates: seven different zoom types produced seven BYTE-IDENTICAL files at a
perfectly plausible ~1020 ms/frame. No per-file signal can see that.

SO THE BAR IS PIXELS AGAINST THE CLIP'S OWN SOURCE, and the threshold is
measured rather than assumed. I first set it at 40.0 dB from an ffmpeg re-encode
reading 45.1 — but a passthrough does not go through ffmpeg, it goes through
Chromium, which loses far more. Rendered locally, all seven types, both arms,
psnr measured WHERE EACH MOVE IS LARGEST:

    type            real    passthrough
    SmoothPush      16.00   26.11
    SnapReframe     16.00   24.30
    FocusWindow     16.65   26.11
    StepZoom        16.01   26.08
    LetterboxPush   15.94   26.10
    DepthPull       16.84   26.08
    StagedPush      16.76   26.09
    ---------------------------------
    real 15.94..16.84       passthrough 24.30..26.11

At 40.0 BOTH arms read as "changed" and the check would have passed a
passthrough — the exact failure it exists to catch. 20.0 sits between them with
3.16 dB above the real ceiling and 4.30 dB below the passthrough floor.

AND THE WINDOW MATTERS AS MUCH AS THE THRESHOLD. Every ramp type starts at scale
1.0, so a real zoom's first frames are legitimately near-identical to their
source. Measured at the HEAD, StagedPush read 20.37 dB and would have been
called inert while applying perfectly.
"""
import ast
import pathlib
import sys
import types

_m = types.ModuleType("modal")


class _S:
    def __init__(s, *a, **k): pass
    def __getattr__(s, n): return _S()
    def __call__(s, *a, **k): return _S()
    def function(s, *a, **k): return lambda f: f
    def local_entrypoint(s, *a, **k): return lambda f: f


for _n in ("App", "Image", "Secret", "Volume", "Cls", "Function"):
    setattr(_m, _n, _S())
_m.is_local = lambda: True
_m.enable_output = _S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A                                    # noqa: E402
import type_registries as TR                                      # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


src = pathlib.Path(A.__file__).read_text()
tree = ast.parse(src)


def _find(name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


_ep = _find("execute_plan")
check("execute_plan is present", _ep is not None)
_calls = {n.func.id for n in ast.walk(_ep) if isinstance(n, ast.Call)
          and isinstance(n.func, ast.Name)} if _ep else set()

# ── 1. NOT DARK ─────────────────────────────────────────────────────────────
check("pick_zoom_type is CALLED, not merely defined", "pick_zoom_type" in _calls,
      "pinned, asserted and called by nothing is the shape of nine features "
      "this repo shipped gate-green that did nothing")
# AND THE TYPE IS NEVER A LITERAL. RED-proving caught this: replacing the
# primary `_ztype = pick_zoom_type(...)` with `_ztype = "SmoothPush"` left the
# check green, because the StagedPush fallback still calls the picker further
# down. "Is it called somewhere" is not "is it choosing".
_zt_assigns = []
for n in ast.walk(_ep) if _ep else []:
    if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_ztype" for t in n.targets):
        _zt_assigns.append(n.value)
check("the zoom type is assigned somewhere", bool(_zt_assigns))
check("EVERY assignment of the zoom type derives it — none is a literal",
      not any(isinstance(v, ast.Constant) for v in _zt_assigns),
      "a hardcoded type ignores the arc, and payoff purity is only enforced "
      "through the arc")
check("at least one assignment comes from pick_zoom_type",
      any(any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
              and c.func.id == "pick_zoom_type" for c in ast.walk(v))
          for v in _zt_assigns))
check("zoom_natural_ms is CALLED", "zoom_natural_ms" in _calls)
check("staged_push_stages is CALLED", "staged_push_stages" in _calls)
check("the generic zoompan no longer builds the family",
      "build_zoom(a2, z2, 1.12" not in src,
      "one 1.12x filtergraph for every moment is the gap the catalogue closes")

# ── 2. THE MOVE IS DERIVED, NOT NAMED BY THE AGENT ──────────────────────────
_verdict_props = set()
for n in ast.walk(tree):
    if (isinstance(n, ast.Dict) and any(
            isinstance(k, ast.Constant) and k.value == "zoom_arc" for k in n.keys)):
        _verdict_props |= {k.value for k in n.keys if isinstance(k, ast.Constant)}
check("the verdict schema offers zoom_arc", bool(_verdict_props))
check("the schema does NOT let the agent name the zoom type",
      '"zoom_type"' not in src,
      "naming the move directly would let a snap land on a payoff, which is "
      "the one thing payoff purity forbids")

# ── 3. PRODUCTION'S DERIVATIONS, EXERCISED ──────────────────────────────────
check("every arc position resolves to a type its home allows",
      all(A.pick_zoom_type(a, "viral punchy money") in A.ZOOM_ARC_HOMES[a]
          and A.pick_zoom_type(a, "calm corporate cinematic") in A.ZOOM_ARC_HOMES[a]
          for a in A.ZOOM_ARC_HOMES))
check("PAYOFF PURITY holds under a vibe that fights both committed pushes",
      A.pick_zoom_type("payoff", "viral punchy frenetic fast")
      in ("LetterboxPush", "SmoothPush"),
      "a snap or a step on the reason-to-exist word is the defect this pins")
check("StagedPush is reachable only at mid_peak",
      [a for a in A.ZOOM_ARC_HOMES
       if A.pick_zoom_type(a, "building stacked money numbers hustle")
       == "StagedPush"] == ["mid_peak"])
def _try_unknown(M):
    try:
        M.pick_zoom_type("not-an-arc", "viral")
        return False
    except ValueError:
        return True


check("an unknown arc RAISES rather than quietly defaulting",
      _try_unknown(A),
      "a zoom placed at a position nobody taught is a move landing on the "
      "wrong kind of moment")
check("the picker is deterministic",
      len({A.pick_zoom_type("mid_peak", "viral punchy") for _ in range(5)}) == 1,
      "a type that changed between two runs of one brief makes every A/B on "
      "this path unreadable")

# ── 4. BACK-TIMING ──────────────────────────────────────────────────────────
check("every offerable type is back-timeable",
      set(A.ZOOM_PEAK_REACH_MS) == set(TR.VALID_ZOOM_TYPES))
check("the clip is started peak-reach EARLY so the peak lands on the beat",
      "_cs = a2 - _peak_s" in src,
      "timing the event's math endpoint to the word puts the peak hundreds of "
      "ms early with scale already back at 1.0")
check("a head clamp is RECORDED, not hidden",
      '"head_clamped"' in src,
      "at the top of the video there is nothing to start early into, and the "
      "peak then lands late by whatever was unavailable")

# ── 5. PRE-EXTRACTION, AND THE PIXELS ───────────────────────────────────────
check("each clip is pre-extracted to its own file", '"src": _zsrc' in src,
      "ClipRenderer mounts a zoom only under `clip.zoomEffect && clip.src`")
check("the extract is re-encoded, not stream-copied",
      '"-c:v", "libx264", "-crf", "16"' in src,
      "a copy starts at the nearest keyframe and the components require a "
      "frame-exact origin")
check("the extract lands where staticFile can serve it",
      '_zpub = "/promptly-remotion/public"' in src or
      '"/promptly-remotion/public"' in src)
# THESE TWO LEGS ARE INVERTED BY THE RULING, and are kept inverted rather than
# deleted so the file records that the check once existed and why it does not.
# They asserted that a zoom the unzoomed source explains better FAILS the round.
# It no longer does, because no bar separating those two cases survived
# validation — see the block below.
# THE BAR IS CONTENT-INDEPENDENT, and the absolute one was not.
# Calibrated on ONE high-detail fixture, 20.0 dB INVERTED on flat content:
#     content    arm    abs psnr   bar 20.0 says   scale-fit delta
#     detailed   real      15.99   APPLIED               +6.06
#     detailed   pass      26.11   NOT APPLIED          -10.91
#     FLAT       real      26.91   NOT APPLIED  <-- WRONG   -4.68
#     FLAT       pass      53.25   NOT APPLIED          -31.71
# Three of round 36's fixtures are flat fields, and the absolute bar produced
# three false failures that would have sent someone to edit working components.
check("the absolute geometry bar is gone",
      not hasattr(A, "_ZOOM_GEOMETRY_MAX_DB"),
      "an absolute psnr against the source is a function of the CONTENT, and "
      "the corpus is not one content class")
# ══════════════════════════════════════════════════════════════════════════
# ZOOM GEOMETRY IS UNMEASURED. Zac's ruling, 2026-09-08: ship neither bar.
#
# THREE INSTRUMENTS, THREE FAILURES, each fitted to whatever population was in
# front of it:
#
#   absolute bar 20.0     fitted to SYNTHETIC. On Zac's real footage a 1.10x
#                         zoom reads 19.13 dB (talking head) and 22.33 (car) —
#                         0.87 dB of margin on one, NEGATIVE on the other.
#   scale-fit -8.0        fitted to REAL footage. On the v1 corpus the rounds
#                         actually run on, FocusWindow reads -12.57 — a
#                         correctly applied zoom called NOT APPLIED. And it
#                         already had a documented blind spot: real 720p
#                         upscaled to 1080 gives a PASSTHROUGH of -7.64, above
#                         the bar, uncaught.
#   delta + intrinsic     refuted by the first population outside the fitted
#                         range, across EVERY reproducible value of its own
#                         input (7.07..10.21). v2-geometry's raw reals sit where
#                         Zac's real footage sits — identical behaviour — while
#                         their intrinsics differ by 12 dB, so the correction
#                         drove them apart. A term that separates two things
#                         which measured the same is injecting, not cancelling.
#
# THE BEST REMAINING CANDIDATE was the raw delta at -14.15: 5/5 across five
# populations, 1.58 dB either side. That is UNDER the 2.0 dB margin registered
# before the data — and adopting a bar that fails its own pre-registered
# standard is what the three failures above are made of.
#
# THE ASYMMETRY DECIDES IT. A wrong zoom check costs a component edit on WORKING
# code, which round 36 nearly bought. Unmeasured is honest and cheap;
# mismeasured is expensive and LOOKS LIKE KNOWLEDGE.
#
# The five-population data lives in zoom_bar_populations.py so the next
# instrument starts from measurement rather than from a fresh guess.
# ══════════════════════════════════════════════════════════════════════════
check("no scale-fit BAR exists any more",
      not hasattr(A, "_ZOOM_SCALE_FIT_FAIL_DB"),
      "a constant nobody validated is a verdict nobody can defend")
check("zoom geometry is declared UNMEASURED",
      getattr(A, "_ZOOM_GEOMETRY_UNMEASURED", False) is True)

# NOTHING REFUSES ON GEOMETRY — and this is the leg that matters, because
# "removed the gate" and "the gate now always passes" look identical from the
# outside and are opposite mistakes. geometry_ok must be None (UNMEASURED),
# never True.
_tree = ast.parse(src)
_geom_fails = [n for n in ast.walk(_tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "fail" and n.args
               and isinstance(n.args[0], ast.Constant)
               and n.args[0].value in ("zoom_not_applied", "zoom_geometry_failed")]
check("nothing fails a round on zoom geometry", not _geom_fails,
      f"{len(_geom_fails)} producer(s) remain")
check("zoom_not_applied is gone from CONTRACT_FAILURES too",
      "zoom_not_applied" not in A.CONTRACT_FAILURES,
      "a name that can fail a round with no producer is the card_props_mismatch "
      "defect — removing the producer and leaving the name recreates it")
check("geometry_ok is set to None, not True",
      '_sg["geometry_ok"] = None' in src and '_sg["geometry_ok"] = _gch' not in src,
      "None is UNMEASURED; True would be an unearned pass, which is the whole "
      "thing this ruling avoids")
check("and the segment carries the word",
      '_sg["geometry_verdict"] = "UNMEASURED"' in src)

# UNMEASURED MUST BE VISIBLE. An absence nobody prints reads as a green — the
# lesson from four ledgered-and-unprinted counters this session.
check("the unmeasured count is ledgered",
      'led["zoom_geometry_unmeasured"] += 1' in src)
check("and PRINTED in the same commit that records it",
      "ZOOM GEOMETRY   :" in src,
      "a counter that reaches the ledger and no output answers nothing")

check("the delta is RECORDED on every segment",
      '_sg["scale_fit_delta_db"] = _gd' in src,
      "a threshold nobody can read the inputs of cannot be re-calibrated when "
      "the corpus changes")
check("the check is aimed at the PEAK, not the head",
      "_pk_s = (_sg[\"stage_peak_s\"] if _sg.get(\"stage_peak_s\")" in src,
      "a ramp starts at scale 1.0, so a real zoom's head is legitimately "
      "near-identical to its source — StagedPush read 20.37 dB there")

# ── 6. STAGEDPUSH ───────────────────────────────────────────────────────────
_w = [{"s": 1.0}, {"s": 1.5}, {"s": 2.0}, {"s": 9.0}]
_st = A.staged_push_stages(_w, 1.0, 2.5, 0.8)
check("stages come from WORD ONSETS, clip-local", len(_st) == 3,
      f"got {_st}")
check("the scale climbs in equal +8% steps, production's ruling",
      [s["scale"] for s in _st] == [1.08, 1.16, 1.24], str(_st))
check("the first stage is offset by the clip start",
      _st[0]["atMs"] == 200, str(_st))
check("fewer than two words is NOT a staged push",
      A.staged_push_stages([{"s": 1.0}], 1.0, 2.5, 0.8) == [],
      "its component returns nothing on <2 stages — a passthrough with no error")
check("a beat that cannot supply stages falls back INSIDE the arc",
      "staged_push_downgrades" in src,
      "and the downgrade is recorded, because a family that quietly changed "
      "moves is a family nobody can audit")
check("the stages reach the render plan", '"stages": _stages' in src)
check("the event's scale is the FINAL stage's, not a default",
      '_stages[-1]["scale"] if _stages' in src)

# ── 7. ONE PROCESS, AND THE FRAME COUNT ─────────────────────────────────────
check("every zoom renders in ONE batch", "render_remotion_batch(_zoom_jobs" in src,
      "N zooms spawning N processes pays 12.24s of bundle+browser N times")
check("each job declares its expected frame count",
      '"expect_frames": _n_frames' in src)
check("the composite measures its effect like every other family",
      '_record_effect("zoom"' in src)

if fails:
    print(f"ZOOM-WIRED: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ZOOM-WIRED: PASS")
