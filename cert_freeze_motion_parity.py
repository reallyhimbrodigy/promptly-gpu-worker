"""CERT — the freeze discriminator's MOTION PARITY escape (RULE-1).

WHAT WAS WRONG. freezedetect uses an ABSOLUTE noise threshold. On very dark
footage genuine motion produces sub-threshold inter-frame differences, so a
render that is plainly animating reads as frozen. MEASURED on job 579dcbe6
(ab-sources/talking-head-v1/625dfdc5-73s.mp4): across the flagged 1.0s span the
subject BLINKS and the caption CHANGES; only 1 of 30 frames is byte-identical to
its predecessor; the flagged span's median inter-frame delta (0.000217) is
indistinguishable from the unflagged window immediately after it (0.000215);
YAVG is 25-27 where normal exposure is 90-140.

WHY NOT THE DARK-SCENE SKIP THAT ALREADY EXISTS. _IG_DARK_SCENE_YAVG is real and
this footage qualifies (25.0 <= 32.0) — but it is wired into the BLACK
discriminator only, and extending it to freeze would let a genuinely frozen DARK
render ship. Dark is exactly where a freeze is hardest for a user to notice and
easiest for us to miss. So the test is RELATIVE: does the output still move
about as much as its own source at the mapped window?

THE TWO PROPERTIES, and the second is the one that matters:
  1. dark-but-moving  -> output ~ source  -> DOWNGRADE (the false trip is gone)
  2. genuinely frozen -> output ~ 0       -> TRIPS ANYWAY, whatever the source
     did. Without (2) this escape would swallow the class the gate exists for.

Fixtures are CONSTRUCTED here with ffmpeg — a real frozen clip and a real
dark-but-moving clip — so the cert proves the primitive on actual video rather
than on mocked numbers.

Offline. Zero network, zero Modal, zero Gemini.
"""
import os
import subprocess
import sys
import tempfile

import handler as H

PASS = FAIL = 0


def ok(m):
    global PASS
    PASS += 1
    print(f"[PASS] {m}")


def bad(m, why):
    global FAIL
    FAIL += 1
    print(f"[FAIL] {m}\n       {why}")


def check(m, cond, why=""):
    ok(m) if cond else bad(m, why)


TMP = tempfile.mkdtemp(prefix="cert_freeze_")


def _mk(name, vf_src, extra=None):
    p = os.path.join(TMP, name)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", vf_src]
    if extra:
        cmd += extra
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", p]
    subprocess.run(cmd, capture_output=True, timeout=120)
    return p if os.path.exists(p) else None


print("\n=== C0 — build the fixtures (a cert on mocked numbers proves nothing) ===")
FROZEN = _mk("frozen.mp4", "color=c=gray:s=320x240:r=30:d=2")
BRIGHT = _mk("bright.mp4", "testsrc2=s=320x240:r=30:d=2")
# Dark BUT MOVING: the same moving source crushed to ~10% luma — the exact
# condition that fools an absolute threshold.
DARK = _mk("dark.mp4", "testsrc2=s=320x240:r=30:d=2",
           ["-vf", "colorlevels=rimax=0.10:gimax=0.10:bimax=0.10"])
for nm, p in (("frozen", FROZEN), ("bright-moving", BRIGHT), ("dark-moving", DARK)):
    check(f"fixture {nm} built", p is not None, "ffmpeg did not produce it")
if not all((FROZEN, BRIGHT, DARK)):
    print("\n  cannot proceed without fixtures")
    sys.exit(1)

print("\n=== C1 — _ig_window_motion separates frozen from moving ===")
m_frozen = H._ig_window_motion(FROZEN, 0.2, 1.5)
m_bright = H._ig_window_motion(BRIGHT, 0.2, 1.5)
m_dark = H._ig_window_motion(DARK, 0.2, 1.5)
print(f"      frozen={m_frozen}  bright={m_bright}  dark-moving={m_dark}")
check("frozen clip reads at/below the frozen ceiling",
      m_frozen is not None and m_frozen <= H._IG_MOTION_FROZEN_MAX,
      f"frozen measured {m_frozen}, ceiling {H._IG_MOTION_FROZEN_MAX} — the "
      f"zero-guard would not fire on a real freeze")
check("bright moving clip reads well above it",
      m_bright is not None and m_bright > H._IG_MOTION_FROZEN_MAX * 10,
      f"bright measured {m_bright}")
check("DARK moving clip ALSO reads above it (the whole point)",
      m_dark is not None and m_dark > H._IG_MOTION_FROZEN_MAX,
      f"dark-moving measured {m_dark} — if this is at the floor the parity test "
      f"cannot rescue dark footage and the fix does not work")
check("_ig_window_motion returns None on an unreadable path (fails CLOSED)",
      H._ig_window_motion(os.path.join(TMP, "nope.mp4"), 0, 1) is None)
check("_ig_window_motion returns None on a zero-length window",
      H._ig_window_motion(BRIGHT, 0.0, 0) is None)

print("\n=== C2 — the decision, on the REAL measured numbers from job 579dcbe6 ===")
OUT_MED, SRC_MED = 0.000217, 0.00067          # measured, not invented


def decide(out_med, src_med):
    """The discriminator's branch, in isolation."""
    if out_med is None or src_med is None:
        return "trip (unreadable -> fail closed)"
    if out_med <= H._IG_MOTION_FROZEN_MAX:
        return "trip (at a standstill)"
    if out_med >= src_med * H._IG_MOTION_PARITY:
        return "downgrade (motion parity)"
    return "trip (much quieter than its source)"


check("the real false-trip is now DOWNGRADED",
      decide(OUT_MED, SRC_MED) == "downgrade (motion parity)",
      f"out={OUT_MED} src={SRC_MED} ratio={OUT_MED/SRC_MED:.3f} -> "
      f"{decide(OUT_MED, SRC_MED)}; parity is {H._IG_MOTION_PARITY}")
print(f"      measured ratio {OUT_MED/SRC_MED:.3f} vs parity {H._IG_MOTION_PARITY}")

print("\n=== C3 — the ZERO-GUARD: a real freeze still trips ===")
print("    (without this the escape swallows the class the gate exists for)")
check("frozen output + moving source -> TRIPS",
      decide(0.0, 0.00067) == "trip (at a standstill)")
check("frozen output + FROZEN source -> still trips via the guard",
      decide(0.0, 0.0) == "trip (at a standstill)",
      "a standstill output must trip on the guard before parity is consulted; "
      "0/0 would otherwise satisfy parity trivially")
check("output just under the ceiling -> TRIPS",
      decide(H._IG_MOTION_FROZEN_MAX, 0.001) == "trip (at a standstill)")
check("output far below its source -> TRIPS",
      decide(0.00001 * 3, 0.01) == "trip (at a standstill)"
      or decide(0.0002, 0.01) == "trip (much quieter than its source)")
check("unreadable output -> fails CLOSED (trips)",
      decide(None, 0.001).startswith("trip"))

print("\n=== C4 — the wiring: output_path actually reaches the discriminator ===")
import ast
_src = open("handler.py").read()
_t = ast.parse(_src)
_fn = next((n for n in ast.walk(_t) if isinstance(n, ast.FunctionDef)
            and n.name == "_ig_source_echo"), None)
check("_ig_source_echo takes output_path",
      _fn is not None and "output_path" in [a.arg for a in _fn.args.args],
      "the relative test cannot run without the output")
_body = ast.get_source_segment(_src, _fn) or ""
check("it calls _ig_window_motion on BOTH sides",
      _body.count("_ig_window_motion") >= 2,
      "one-sided motion is not a parity test")
check("the call site passes output_path",
      "_ig_source_echo(\n            source_path, freeze_resid, out_to_src, output_path=output_path)" in _src
      or "output_path=output_path" in _src,
      "the gate would pass None and the escape would never fire — an inert fix")
check("the guard is checked BEFORE parity (order is load-bearing)",
      _body.index("_IG_MOTION_FROZEN_MAX") < _body.index("_IG_MOTION_PARITY"),
      "parity evaluated first would downgrade a 0/0 standstill")


print("\n=== C5 — the FALL-THROUGH cannot swallow a span ===")
print("    (my first patch left this line inside the parity block; a span with")
print("     an unreadable motion read was neither tripped nor downgraded)")


def _fallthrough_ok():
    _f = next(n for n in ast.walk(ast.parse(_src))
              if isinstance(n, ast.FunctionDef) and n.name == "_ig_source_echo")
    # Every path through the loop must land in exactly one list.
    _seg = (ast.get_source_segment(_src, _f) or "").split("\n")
    _loop = [l for l in _seg if l.strip() == "defects.append((s, e))"]
    assert _loop, "no unconditional defect fall-through found"
    # the LAST one is the fall-through; it must sit at the loop body's indent
    # (8 spaces), not nested inside a conditional (12+).
    _ind = len(_loop[-1]) - len(_loop[-1].lstrip())
    assert _ind == 8, (
        f"the fall-through defects.append is indented {_ind}, not 8 — it is "
        f"nested inside a conditional, so a span that reaches it under a false "
        f"branch is dropped from BOTH lists and the gate goes blind to it")


check("the final defects.append is the loop-level fall-through", True
      if _fallthrough_ok() is None else False)

print(f"\n{'=' * 70}\n  cert_freeze_motion_parity: {PASS} passed, {FAIL} failed\n{'=' * 70}")
sys.exit(1 if FAIL else 0)
