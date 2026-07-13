"""CAPTION FRAME ALIGNMENT (Zac 2026-07-13). Captions felt consistently LATE by a few
ms in every video — AFTER the fade was removed, so not the fade. Root: a caption reveals
at the first frame whose time reaches fromMs (the reveal is `(frame/fps)*1000 >= fromMs`
= CEIL(start*fps)), while every other component fires at ROUND(start*fps). So captions
landed 0-1 frame LATER than SFX/zoom/MG on the SAME word. Fix: shift token fromMs earlier
by HALF A FRAME so ceil(start*fps - 0.5) == round(start*fps) — the caption reveals on the
IDENTICAL frame the components fire. This asserts that alignment, especially for the
fractional-frame onsets (f in (0,0.5)) that used to reveal a frame late."""
import sys, math
import handler as H

FPS = 60.0
PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

def reveal_frame(from_ms, fps):
    # first integer frame f where (f/fps)*1000 >= from_ms  (the component reveal condition)
    f = from_ms * fps / 1000.0
    fr = math.floor(f)
    return fr if (fr / fps) * 1000.0 >= from_ms - 1e-9 else fr + 1

def component_frame(start_s, fps):
    return int(round(start_s * fps))  # exactly what render_timeline uses: int(round(start*fps))

# start times chosen to span the fractional-frame position f = frac(start*fps):
#   f in (0, 0.5) → the OLD ceil reveal was 1 frame LATE; f in [0.5,1) → was on time.
W = lambda s: {"word": "w", "punctuated_word": "w", "start": s, "end": s + 0.30,
               "start_word_index": 0}
STARTS = [1.000, 1.005, 1.010, 1.008, 2.083, 2.088, 2.091, 0.503, 0.508, 3.333, 3.337]

# build each as a one-word page so pageStartMs == the word and the token carries fromMs
_late_before = 0
for _s in STARTS:
    _pages = H._build_tiktok_pages_from_projected([W(_s)], fps=FPS)
    _tok = _pages[0]["tokens"][0]
    _rf = reveal_frame(_tok["fromMs"], FPS)
    _cf = component_frame(_s, FPS)
    check(f"start={_s:.3f}s → caption reveals frame {_rf} == component frame {_cf}", _rf == _cf,
          f"fromMs={_tok['fromMs']:.3f} reveal={_rf} component={_cf}")
    # how many WOULD have been late under the old int-ms ceil (no half-frame shift)
    _old_from = round(_s * 1000)
    if reveal_frame(_old_from, FPS) > _cf:
        _late_before += 1

check(f"the fix actually mattered: {_late_before}/{len(STARTS)} of these were a frame LATE before",
      _late_before >= 3, f"only {_late_before} were late before — pick more fractional cases")

# the half-frame shift constant is present + derived from fps (not hardcoded to 60)
_src = open("handler.py").read()
check("fromMs is shifted earlier by half a frame (500/fps)", "500.0 / float(fps" in _src and "w_start * 1000.0 - _half_frame_ms" in _src)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL); sys.exit(1)
print("ALL CAPTION-FRAME-ALIGNMENT CASES PASS")
