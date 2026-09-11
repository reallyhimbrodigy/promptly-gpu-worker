#!/usr/bin/env python3
"""SMOKE: every declared family measures its effect, and each instrument is
RED-proven on fixtures it builds itself.

WHY. `step_changed_output()` was generic and called from exactly ONE site —
inside build_zoom. Round 33 read "PLACEMENT EFFECT: 1 measured" on a run that
DECLARED SIXTEEN placements (text 10, card 4, sfx 1, zoom 1). Fifteen
declarations carried no evidence they changed anything, and nothing in the run
said so, because the only thing that could have said so was a count of a list
nobody compared to anything.

A ported 31-type motion-graphics catalogue and a catalogue that composites
NOTHING produce the identical report under that coverage. So this lands before
any component is ported, not after.

FOUR LEGS, and the third is the one this repo keeps learning:

  1. STRUCTURE — every family that declares into the manifest calls
     _record_effect, walked from the AST rather than grepped, because a comment
     mentioning a family reads identically to a call placing one.
  2. THE VIDEO INSTRUMENT — a no-op re-encode reads unchanged, a real overlay
     reads changed, an unmeasurable pair reads None and never False.
  3. THE AUDIO INSTRUMENT — RED-proven on FIXTURES BUILT HERE, and the -8.0 dB
     floor is RE-DERIVED from them rather than trusted. place_sfx writes
     `-c:v copy`, so the picture is byte-identical BY CONSTRUCTION and a video
     check would report psnr=inf / changed=False on a PERFECT sound placement.
     Standing a video check in for an audio family would not be a weak check —
     it would be an INVERTED one, marking every correct sfx inert.
  4. THE COVERAGE IDENTITY fails the round rather than annotating it.

Runs locally, needs only ffmpeg. No Modal, no spend.
"""
import ast
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import types

import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


def _run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=300)


SRC = pathlib.Path(A.__file__).read_text()

# ── 1. STRUCTURE: every declaring family measures ────────────────────────────
# Walked from the AST. A grep for `_record_effect("card"` matches a COMMENT
# saying so, and this lane has already shipped one check that passed on a
# comment (`Gate leg 4: a comment armed the branch, so it now reads the AST`).
tree = ast.parse(SRC)


def _find_func(node, name):
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


_ep = _find_func(tree, "execute_plan")
check("execute_plan is present to walk", _ep is not None)

measured = set()
if _ep:
    for n in ast.walk(_ep):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_record_effect" and n.args
                and isinstance(n.args[0], ast.Constant)):
            measured.add(n.args[0].value)

# The families execute_plan can DECLARE into the manifest. Read from the app's
# own _TYPE map rather than restated here, so a family added later is covered
# without anyone remembering to update this list.
_type_map = {}
for n in ast.walk(_ep) if _ep else []:
    if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_TYPE" for t in n.targets):
        if isinstance(n.value, ast.Dict):
            _type_map = {k.value for k in n.value.keys
                         if isinstance(k, ast.Constant)}
check("the declaring families were read from the app's own _TYPE map",
      bool(_type_map), f"parsed {_type_map!r}")

# zoom measures inside build_zoom, not execute_plan — its call site is separate
# and predates this. Everything else must measure where it declares.
_zoom_measures = 'led.setdefault("placement_effects"' in SRC
check("zoom still records an effect (via build_zoom)", _zoom_measures)

for fam in sorted(_type_map - {"zoom"}):
    check(f"family {fam!r} calls _record_effect where it declares",
          fam in measured,
          f"declares into the manifest but measures nothing; measured={sorted(measured)}")

check("caption measures even though it is not a manifest family",
      "caption" in measured,
      "path=remotion composited=True fires on a file existing and ffmpeg "
      "exiting 0 — a fully transparent .mov satisfies both")

# ── 2. THE COVERAGE IDENTITY FAILS THE ROUND ─────────────────────────────────
check("placement_effect_uncovered is a CONTRACT failure",
      "placement_effect_uncovered" in A.CONTRACT_FAILURES)
_cv = A._contract_violations(
    {"failures": [{"kind": "placement_effect_uncovered", "detail": "x"}]})
check("it surfaces through _contract_violations",
      any("placement_effect_uncovered" in c for c in _cv), str(_cv))
check("execute_plan raises it", 'fail("placement_effect_uncovered"' in SRC)

# THE IDENTITY ITSELF, CALLED — not its error string looked for in the source.
# RED-proving found this hole: neutering the identity to `set()` left every leg
# green, because the string this line greps for was still in the file. The logic
# now lives in a module-level function so a test can run it on real inputs.
check("uncovered_families is importable at runtime, not merely present in text",
      callable(getattr(A, "uncovered_families", None)),
      "source is where code might be; runtime is where it is")
if callable(getattr(A, "uncovered_families", None)):
    _P = [{"family": "text"}, {"family": "card"}, {"family": "zoom"}]
    check("a family that declared and never measured is NAMED",
          A.uncovered_families(_P, [{"family": "text"}]) == ["card", "zoom"],
          str(A.uncovered_families(_P, [{"family": "text"}])))
    check("full coverage returns nothing",
          A.uncovered_families(_P, [{"family": f} for f in ("text", "card", "zoom")]) == [])
    check("an UNMEASURED effect still counts as COVERED — 'could not measure' "
          "is not 'never looked'",
          A.uncovered_families([{"family": "sfx"}],
                               [{"family": "sfx", "changed": None}]) == [])
    check("measuring a family nobody declared is not an error",
          A.uncovered_families([{"family": "text"}],
                               [{"family": "text"}, {"family": "caption"}]) == [])
    check("no declarations, no gap", A.uncovered_families([], []) == [])
    check("junk rows are ignored rather than crashing the identity",
          A.uncovered_families([{"family": "text"}, {}, None, "x"],
                               [{"family": "text"}]) == [])
check("the coverage verdict is PRINTED, not only ledgered",
      "EFFECT COVERAGE :" in SRC,
      "a counter added to answer a question gets printed in the same commit")
check("bundle_ms is PRINTED, not only ledgered",
      "bundle {(_cr.get('bundle_ms') or 0)/1000:.1f}s" in SRC,
      "it was captured at two sites and printed nowhere, so the "
      "startup-vs-paint split could not be read from any round")

# ── 3. THE INSTRUMENTS, RED-PROVEN ON FIXTURES BUILT HERE ────────────────────
if not shutil.which("ffmpeg"):
    print("PLACEMENT-EFFECT-FAMILIES: ffmpeg absent — instrument legs SKIPPED")
    print("  (structure legs above still ran; a skip is reported, never passed)")
    fails.append("ffmpeg unavailable: the instrument legs did not run, and a "
                 "leg that did not run must never read as a leg that passed")
else:
    D = tempfile.mkdtemp(prefix="peff-")
    try:
        base = os.path.join(D, "base.mp4")
        _run(["ffmpeg", "-v", "error", "-y",
              "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=30:duration=6",
              "-f", "lavfi", "-i", "anoisesrc=d=6:c=pink:a=0.15:seed=20260907",
              "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
              "-shortest", base])
        loud = os.path.join(D, "loud.mp4")
        _run(["ffmpeg", "-v", "error", "-y",
              "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=30:duration=6",
              "-f", "lavfi", "-i", "anoisesrc=d=6:c=pink:a=0.6:seed=20260908",
              "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
              "-shortest", loud])
        hit = os.path.join(D, "hit.mp3")
        _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
              "-i", "sine=frequency=900:duration=0.35",
              "-af", "afade=t=out:st=0.05:d=0.3,volume=0.9", "-c:a", "mp3", hit])
        check("fixtures built", all(os.path.exists(f) and os.path.getsize(f)
                                    for f in (base, loud, hit)))

        # ---- VIDEO -----------------------------------------------------------
        reenc = os.path.join(D, "reenc.mp4")
        _run(["ffmpeg", "-v", "error", "-y", "-i", base, "-c:v", "libx264",
              "-crf", "18", "-preset", "veryfast", "-c:a", "copy", reenc])
        drawn = os.path.join(D, "drawn.mp4")
        _run(["ffmpeg", "-v", "error", "-y", "-i", base, "-vf",
              "drawbox=x=40:y=200:w=240:h=120:color=white@1.0:t=fill:"
              "enable='between(t,1.5,3.5)'",
              "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
              "-c:a", "copy", drawn])

        # THE ABSOLUTE BAR IS NOT ENOUGH, AND THIS IS THE LEG THAT FOUND IT.
        # step_changed_output's 50 dB threshold was set where a re-encode read
        # 68.25 dB. On a high-detail fixture a PURE RE-ENCODE — nothing drawn —
        # reads ~45 dB, i.e. CHANGED. A family compositing NOTHING would have
        # reported "moved". Asserted here so the weakness cannot come back
        # unnoticed, and so the relative leg below has a reason on the record.
        _, _abs_reenc = A.step_changed_output(base, reenc, 2.0, 2.5)
        check("the absolute bar is documented as insufficient on detailed "
              "content (this is why the relative leg exists)",
              _abs_reenc is not None and _abs_reenc < 60.0,
              f"a pure re-encode read {_abs_reenc} dB; if this is now >60 the "
              f"fixture stopped being representative, not the problem going away")

        # RELATIVE: placement window against a control window in the same pair.
        _, p_re = A.step_changed_output(base, reenc, 2.0, 2.5)
        _, c_re = A.step_changed_output(base, reenc, 4.8, 5.3)
        _, p_dr = A.step_changed_output(base, drawn, 2.0, 2.5)
        _, c_dr = A.step_changed_output(base, drawn, 4.8, 5.3)
        check("VIDEO RED: nothing drawn — control and placement degrade equally",
              (c_re - p_re) < A._VIDEO_REL_MARGIN_DB,
              f"placed {p_re} dB, control {c_re} dB, delta {c_re - p_re:.2f} dB")
        check("VIDEO GREEN: a real overlay separates from its control",
              (c_dr - p_dr) >= A._VIDEO_REL_MARGIN_DB,
              f"placed {p_dr} dB, control {c_dr} dB, delta {c_dr - p_dr:.2f} dB")
        check("the relative margin has room on both sides",
              (c_re - p_re) < A._VIDEO_REL_MARGIN_DB - 1.0
              and (c_dr - p_dr) > A._VIDEO_REL_MARGIN_DB + 1.0,
              f"inert delta {c_re - p_re:.2f}, real delta {c_dr - p_dr:.2f}, "
              f"margin {A._VIDEO_REL_MARGIN_DB}")
        print(f"  [derived] video inert delta {c_re - p_re:+.2f} dB   "
              f"real delta {c_dr - p_dr:+.2f} dB   "
              f"margin {A._VIDEO_REL_MARGIN_DB} dB")
        ch, db = A.step_changed_output(base, drawn, 2.0, 2.5)
        check("VIDEO: a real overlay also clears the absolute bar", ch is True,
              f"psnr {db} dB")
        ch, _ = A.step_changed_output(os.path.join(D, "nope.mp4"), base, 0.0, 1.0)
        check("VIDEO: unmeasurable is None, never False", ch is None,
              "collapsing 'could not measure' into 'did nothing' is how "
              "absence becomes success")

        # ---- AUDIO -----------------------------------------------------------
        # Four arms across an 11 dB change in bed loudness AND a 14 dB change in
        # sfx gain. The point of the loud/quiet pair is that NO ABSOLUTE
        # threshold separates them: the loud bed's INERT diff is louder than the
        # quiet bed's REAL diff. Only the normalised metric survives both.
        arms = {}
        for tag, bed, gain in (("quiet", base, "-6dB"), ("loud", loud, "-20dB")):
            inert = os.path.join(D, f"{tag}_inert.mp4")
            _run(["ffmpeg", "-v", "error", "-y", "-i", bed, "-map", "0:v",
                  "-map", "0:a", "-c:v", "copy", "-c:a", "aac", inert])
            real = os.path.join(D, f"{tag}_real.mp4")
            _run(["ffmpeg", "-v", "error", "-y", "-i", bed, "-i", hit,
                  "-filter_complex",
                  f"[1:a]adelay=2000|2000,volume={gain}[s];"
                  f"[0:a][s]amix=inputs=2:duration=first:dropout_transition=0[outa]",
                  "-map", "0:v", "-map", "[outa]", "-c:v", "copy", "-c:a", "aac",
                  real])
            for kind, path in (("INERT", inert), ("REAL", real)):
                c, n = A.step_changed_audio(bed, path, 2.0, 2.35)
                arms[f"{tag}-{kind}"] = (c, n)

        for name, (c, n) in sorted(arms.items()):
            want = name.endswith("REAL")
            check(f"AUDIO {'GREEN' if want else 'RED'}: {name} reads "
                  f"{'CHANGED' if want else 'UNCHANGED'}",
                  c is want, f"nsr {n} dB")

        # THE FLOOR IS RE-DERIVED, NOT TRUSTED. It was measured against
        # place_sfx's own `-c:a aac` at default bitrate; change that encoder and
        # the constant is stale. A threshold nobody re-checks is a magic number
        # waiting to drift, so this asserts the SEPARATION still exists rather
        # than asserting the constant is right.
        _inerts = [n for k, (c, n) in arms.items() if k.endswith("INERT") and n is not None]
        _reals = [n for k, (c, n) in arms.items() if k.endswith("REAL") and n is not None]
        if _inerts and _reals:
            worst_real, worst_inert = min(_reals), max(_inerts)
            # The SPREAD is a sanity bound on the normalisation, not the bar.
            # The bar is the two margin checks below — those are what decide
            # whether the instrument separates. Measured spread across an 11 dB
            # bed change has run to ~3.5 dB with the arms still cleanly apart,
            # so a tighter bound here would fail on encoder noise while the
            # instrument was working perfectly.
            check("the codec floor stays in a narrow band across bed loudness",
                  max(_inerts) - min(_inerts) < 5.0,
                  f"inert nsr spread {min(_inerts)}..{max(_inerts)} dB — if this "
                  f"widens the normalisation no longer holds")
            check("the threshold sits between the arms with real margin",
                  worst_inert < A._AUDIO_INERT_FLOOR_DB < worst_real,
                  f"worst inert {worst_inert} dB, floor "
                  f"{A._AUDIO_INERT_FLOOR_DB} dB, worst real {worst_real} dB")
            check("the margin is at least 1.5 dB on both sides",
                  (A._AUDIO_INERT_FLOOR_DB - worst_inert) >= 1.5
                  and (worst_real - A._AUDIO_INERT_FLOOR_DB) >= 1.5,
                  f"inert margin {A._AUDIO_INERT_FLOOR_DB - worst_inert:.2f} dB, "
                  f"real margin {worst_real - A._AUDIO_INERT_FLOOR_DB:.2f} dB")
            print(f"  [derived] inert floor {min(_inerts):.2f}..{max(_inerts):.2f} dB   "
                  f"real {min(_reals):.2f}..{max(_reals):.2f} dB   "
                  f"threshold {A._AUDIO_INERT_FLOOR_DB} dB")

        # SILENCE IS UNMEASURABLE, NOT INERT. A normalised metric divides by the
        # local signal; with no local signal there is nothing to normalise
        # against. Reporting False here would page on every sound placed over a
        # silent beat — which is where a sound effect most often goes.
        mute = os.path.join(D, "mute.mp4")
        _run(["ffmpeg", "-v", "error", "-y",
              "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=30:duration=6",
              "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:d=6",
              "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
              "-shortest", mute])
        c, n = A.step_changed_audio(mute, mute, 2.0, 2.35)
        check("AUDIO: silence in the window is UNMEASURED, never INERT",
              c is None, f"nsr {n} — a sound over a silent beat must not page")
        c, _ = A.step_changed_audio(os.path.join(D, "nope.mp4"), base, 0.0, 1.0)
        check("AUDIO: unmeasurable is None, never False", c is None)

        # THE INVERSION, DEMONSTRATED. This is the leg that justifies a second
        # instrument existing at all: on a real sfx placement the VIDEO check
        # says INERT, because place_sfx copies the video stream.
        sfxonly = os.path.join(D, "sfxonly.mp4")
        _run(["ffmpeg", "-v", "error", "-y", "-i", base, "-i", hit,
              "-filter_complex",
              "[1:a]adelay=2000|2000,volume=-6dB[s];"
              "[0:a][s]amix=inputs=2:duration=first:dropout_transition=0[outa]",
              "-map", "0:v", "-map", "[outa]", "-c:v", "copy", "-c:a", "aac",
              sfxonly])
        vch, vdb = A.step_changed_output(base, sfxonly, 2.0, 2.35)
        ach, adb = A.step_changed_audio(base, sfxonly, 2.0, 2.35)
        check("a video check on a REAL sfx placement reports INERT — which is "
              "why sfx needs its own instrument",
              vch is False and ach is True,
              f"video says changed={vch} (psnr {vdb}), audio says changed={ach} "
              f"(nsr {adb})")
    finally:
        shutil.rmtree(D, ignore_errors=True)

if fails:
    print(f"PLACEMENT-EFFECT-FAMILIES: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("PLACEMENT-EFFECT-FAMILIES: PASS")
