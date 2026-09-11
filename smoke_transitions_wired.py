#!/usr/bin/env python3
"""SMOKE: seam dressing — nine transitions, two tight-cut overlays, room-fitted.

THREE THINGS THIS FAMILY GETS WRONG IF NOBODY CHECKS.

1. LIGHTLEAK IS NOT A TRANSITION. It sits in the same duration table as the
   nine, and ShutterFlash is in BOTH registries — the heavy form halts the
   video, the light form accents a cut that plays straight. Reading the ten-row
   table as "ten transitions" offers a cover graphic to carry a picture change.

2. THE ROOM IS THE SHORTER SIDE, not the gap and not the sum. A transition
   overlaps A's tail and B's head, so both must carry its full duration.
   Offering a 1200ms FilmStrip across a 400ms span asks the renderer for frames
   that do not exist.

3. NONE IS A REAL ANSWER. The corpus rate on the speech route is 0.00/25s. Most
   seams are meant to play straight, and a picker that always finds something
   has stopped reading the room.

AND THE TIMELINE MUST NOT MOVE. Production plans transitions BEFORE the render,
so a type that consumes handle frames simply shortens the timeline and
everything downstream is timed against the result. This lane has already cut,
captioned, zoomed and timed the sfx against `cur` — a family that shortened the
video here would desync every one of them.
"""
import ast
import pathlib
import sys
import types

import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402
import type_registries as TR                                      # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


src = pathlib.Path(A.__file__).read_text()
tree = ast.parse(src)
_ep = next((n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "execute_plan"), None)
_calls = {n.func.id for n in ast.walk(_ep) if isinstance(n, ast.Call)
          and isinstance(n.func, ast.Name)} if _ep else set()

# ── 1. THE VOCABULARY ───────────────────────────────────────────────────────
check("all nine registry transitions are offerable",
      set(TR.VALID_TRANSITION_TYPES) <= set(A.TRANSITION_NATURAL_DURATION_MS),
      f"missing {sorted(set(TR.VALID_TRANSITION_TYPES) - set(A.TRANSITION_NATURAL_DURATION_MS))}")
check("LightLeak is never offered as a transition",
      A.pick_transition(10_000, "story emotional nostalgic") != "LightLeak",
      "it is a cover graphic; asking it to carry a picture change is the "
      "ten-row-table mistake")
check("both tight-cut overlays are reachable",
      {A.pick_tight_cut_overlay("story emotional nostalgic realization"),
       A.pick_tight_cut_overlay("viral high-energy stat")}
      == set(TR.VALID_TIGHT_CUT_OVERLAYS),
      f"got {sorted({A.pick_tight_cut_overlay('story emotional nostalgic realization'), A.pick_tight_cut_overlay('viral high-energy stat')})}")

# ── 2. ROOM FITTING ─────────────────────────────────────────────────────────
_spans = [[0.0, 5.0], [5.0, 5.4], [5.4, 9.0]]
check("the room is the SHORTER side, not the gap or the sum",
      abs(A.transition_room_ms(_spans, 0) - 400.0) < 1e-6,
      f"got {A.transition_room_ms(_spans, 0)} for a 5.0s span meeting a 0.4s one")
check("a 400ms seam is offered only what fits in 400ms",
      A.transitions_fitting(400) == ["DipToBlack"],
      f"got {A.transitions_fitting(400)}")
check("a roomy seam is offered the whole vocabulary",
      set(A.transitions_fitting(2000)) == set(TR.VALID_TRANSITION_TYPES))
check("nothing fits a seam shorter than the shortest type",
      A.transitions_fitting(200) == [],
      f"the shortest is DipToBlack at "
      f"{A.TRANSITION_NATURAL_DURATION_MS['DipToBlack']}ms")
check("NONE is returned when nothing fits — not a fallback",
      A.pick_transition(200, "viral punchy") is None,
      "a family that always places something has stopped reading the room")
check("the room is never negative or nonsense at the ends",
      A.transition_room_ms(_spans, -1) == 0.0
      and A.transition_room_ms(_spans, 99) == 0.0
      and A.transition_room_ms([], 0) == 0.0)

# ── 3. THE VIBE SCOPES THE REGISTER ─────────────────────────────────────────
for _vibe, _want in (("clean professional explainer chaptered", "SlideOver"),
                     ("viral high-energy punchy payoff", "ZoomThrough"),
                     ("cinematic story documentary act", "DipToBlack"),
                     ("casual vlog pivot", "CardSwipe"),
                     ("corporate educational business training", "StepPush")):
    check(f"{_vibe.split()[0]} seams take {_want}",
          A.pick_transition(2000, _vibe) == _want,
          f"got {A.pick_transition(2000, _vibe)}")
check("the picker is deterministic",
      len({A.pick_transition(2000, "viral punchy") for _ in range(5)}) == 1,
      "a type that changed between runs makes every A/B unreadable")

# ── 4. WIRED, NOT DARK ──────────────────────────────────────────────────────
check("pick_transition is CALLED", "pick_transition" in _calls)
check("pick_tight_cut_overlay is CALLED", "pick_tight_cut_overlay" in _calls)
check("transition_room_ms is CALLED", "transition_room_ms" in _calls)
check("transition joins the treatment families",
      "transition" in A._TREATMENT_FAMILIES)
check("transition is accounted like every other family",
      '"transition": "transition"' in src
      and '"transition": sum(1 for v in vs' in src,
      "a family the agent can rule and the accounting cannot see reports a "
      "drop for something nobody counted")

# ── 5. THE OVERLAYS RIDE THE ALPHA PASS ─────────────────────────────────────
_p = A.caption_overlay_plan([], "CleanCut", 60, fps=30,
                            tight_cut_overlays=[{"type": "LightLeak",
                                                 "fromFrame": 10,
                                                 "durationInFrames": 5}])
# INDEXED SAFELY. The first version subscripted [0] and raised IndexError when
# the list came back empty — a check that CRASHES on the failure it detects
# reports a harness bug, not a finding, and a traceback is not a verdict.
_tco = (_p.get("input") or {}).get("tightCutOverlays") or []
check("the alpha plan carries tightCutOverlays",
      len(_tco) == 1 and _tco[0].get("type") == "LightLeak",
      f"got {_tco}")
check("they are chosen BEFORE the alpha pass renders",
      src.index("_tr_choices = []") < src.index("_tc_overlays = [\n"),
      "choosing them after would need a SECOND alpha render to carry them — "
      "the doubled work this port keeps deleting")
check("an empty list is the default, so a run with no seams is unchanged",
      A.caption_overlay_plan([], "CleanCut", 60)["input"]["tightCutOverlays"] == [])

# ── 6. THE TIMELINE DOES NOT MOVE ───────────────────────────────────────────
check("the composite OVERLAYS the seam window rather than concatenating",
      "overlay=0:0:enable='between(t," in src and "[tm{_k2}]" in src,
      "a concat would shorten the video and desync the captions, sfx and zooms "
      "already timed against it")
check("audio is passed through untouched",
      '"-map", "0:a?",\n                           "-c:v", "libx264"' in src
      or src.count('"-c:a", "copy", "/work/transitioned.mp4"') == 1,
      "a seam treatment must not re-encode or shift the audio")
check("each transition declares its expected frame count",
      '"expect_frames": _nf' in src)
# BY CALL NAME, FROM THE AST. A substring test passed when the call was renamed
# to `_NOT_record_effect("transition"` — which still CONTAINS the string it was
# looking for. Substring containment is not identity.
_eff_families = set()
for _n2 in ast.walk(_ep) if _ep else []:
    if (isinstance(_n2, ast.Call) and isinstance(_n2.func, ast.Name)
            and _n2.func.id == "_record_effect" and _n2.args
            and isinstance(_n2.args[0], ast.Constant)):
        _eff_families.add(_n2.args[0].value)
check("a transition measures its effect like every other family",
      "transition" in _eff_families,
      f"families measured: {sorted(_eff_families)}")
check("the composite refuses to read and write the same file",
      'if cur == "transitioned.mp4":' in src)

if fails:
    print(f"TRANSITIONS-WIRED: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("TRANSITIONS-WIRED: PASS")
