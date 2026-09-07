#!/usr/bin/env python3
"""SMOKE: real captions render through PromptlyOverlay, not an ffmpeg burn.

THE LARGEST GAP IN THE PARITY AUDIT. Production has nine Remotion caption styles
with per-word animation; the agentic path burned ONE ffmpeg subtitle track with
force_style='Fontname=DejaVu Sans'. Not a lower-fidelity caption — a different
renderer, different typography, no per-word timing at all, on every video.

MEASURED BEFORE PORTING (bands, with sample counts):
  in-container paint  112-133 ms/frame across nine styles, n=1 each
  central at conc 8   85.4 ms/frame, spread 83.2-87.9, n=3
  concurrency         saturates at 4; 2.6x ceiling, NOT the encoder — the
                      paint-only sweep flattens identically
  half rate           8 of 9 styles are ALREADY 80-97% static at 30fps, so
                      halving adds 0-5% held frames. TypewriterReveal is 42%
                      static (per-character cursor) and adds 17%, so it stays
                      at full rate.
"""
import sys, types, pathlib
_m = types.ModuleType("modal")
class _S:
    def __init__(s,*a,**k): pass
    def __getattr__(s,n): return _S()
    def __call__(s,*a,**k): return _S()
    def function(s,*a,**k): return lambda f: f
    def local_entrypoint(s,*a,**k): return lambda f: f
for _n in ("App","Image","Secret","Volume","Cls","Function"): setattr(_m,_n,_S())
_m.is_local=lambda: True; _m.enable_output=_S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A
src = pathlib.Path(A.__file__).read_text()
fails=[]
def check(l,c,d=""):
    if not c: fails.append(l + (f"  :: {d}" if d else ""))

# ── the symbols exist at RUNTIME, not merely in source ────────────────────
for n in ("pick_caption_style", "caption_pages", "caption_overlay_plan"):
    check(f"{n} is importable", hasattr(A, n),
          "source is where code might be; runtime is where it is")

# ── production's composition, no new component ────────────────────────────
plan = A.caption_overlay_plan([{"startMs":0,"durationMs":500,"text":"x","tokens":[]}],
                              "CleanCut", 60)["input"]
check("it drives PromptlyOverlay's shape", "caption" in plan and "motionGraphics" in plan)
check("motionGraphics is EMPTY — captions only", plan["motionGraphics"] == [])
check("the caption spec carries style, pages and position segments",
      set(plan["caption"]) >= {"style","pages","positionSegments"})
check("the composition id used is PromptlyOverlay",
      '"composition": "PromptlyOverlay"' in src,
      "production's own overlay composition — a new component would be a second "
      "implementation to keep in sync")

# ── one clock ─────────────────────────────────────────────────────────────
kept=[{"s":0.0,"e":0.4,"w":"a"},{"s":0.4,"e":0.9,"w":"b"}]
pg=A.caption_pages(kept,2)
check("tokens carry INTEGER ms",
      all(isinstance(t["fromMs"],int) and isinstance(t["toMs"],int)
          for p in pg for t in p["tokens"]),
      "a token carrying a float lands mid-frame")
check("pages are built from the SRT's own remapped words",
      'led["kept_words_out"]' in src and "caption_pages(_cap_words" in src,
      "caption drift against speech is silent and ffmpeg exits 0 either way")

# ── the rotation rule actually rotates ────────────────────────────────────
V="hustle money business success motivational"
check("rotation avoids the recently used style",
      A.pick_caption_style(V, recent=[A.pick_caption_style(V)]) != A.pick_caption_style(V),
      "production: avoid the #1 style if it appeared in either of the last 2")
check("selection is deterministic",
      len({A.pick_caption_style(V) for _ in range(5)}) == 1,
      "a style that varies between runs of one brief makes every A/B unreadable")

# ── half rate, per style ──────────────────────────────────────────────────
check("TypewriterReveal renders at full rate, the rest at half",
      '30 if _cap_style == "TypewriterReveal" else 15' in src,
      "it is 42% static natively where the others are 80-97%")

# ── the batch, and the fallback ───────────────────────────────────────────
check("captions go through the shared batch", "render_remotion_batch([{" in src)
check("alpha is requested", '"alpha": True' in src)
check("the ffmpeg burn survives ONLY as a fallback",
      'not led.get("caption_mov")' in src,
      "no captions at all is worse than plain ones")
check("a failed render is LOUD", 'fail("caption_render_failed"' in src)
check("a failed composite is LOUD", 'fail("caption_composite_failed"' in src,
      "render ok + composite failed = a video with NO captions")
check("which path painted is recorded", 'led["caption_path"]' in src)
check("and PRINTED", "CAPTIONS        :" in src,
      "any counter added to answer a question gets printed in the commit that "
      "adds it")

if fails:
    print(f"CAPTION-PORT: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("CAPTION-PORT: PASS")
