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
# ── GATED ON SPEECH, NOT ON THE TEXT FAMILY ───────────────────────────────
# The caption render sat inside `if items:` — the TEXT overlay list — so a
# SPEECH job that ruled zero text overlays rendered ZERO CAPTIONS, silently,
# while the comment on the block's first line said "captions only where speech
# exists". The gate and its own stated intent disagreed and the gate won.
#
# LATENT, never fired: round 33's only speech fixture ruled 10 text items, so
# the two conditions were indistinguishable there, and the other four fixtures
# carry no speech and are correctly capless either way. It would have shipped as
# a video that simply has no captions — no error, nothing to grep for.
#
# WALKED FROM THE AST, and over the ENCLOSING conditions rather than the call
# line: the defect was never visible at the call site, only in what wrapped it.
import ast as _ast
_tree = _ast.parse(src)


def _enclosing_ifs(root, want):
    """Every `if` test that wraps a node whose source contains `want`."""
    out, stack = [], [(root, [])]
    while stack:
        node, guards = stack.pop()
        for child in _ast.iter_child_nodes(node):
            g = guards
            if isinstance(node, _ast.If) and child in node.body:
                g = guards + [node.test]
            if (isinstance(child, _ast.Constant) and isinstance(child.value, str)
                    and child.value == want):
                out.append(g)
            stack.append((child, g))
    return out


_names_guarding = set()
for _g in _enclosing_ifs(_tree, "captions"):
    for _t in _g:
        for _n in _ast.walk(_t):
            if isinstance(_n, _ast.Name):
                _names_guarding.add(_n.id)
check("the caption render is NOT gated on the text-overlay list",
      "items" not in _names_guarding,
      f"conditions wrapping the caption render reference {sorted(_names_guarding)} "
      f"— a speech job that rules no text overlays would render no captions")
check("it IS gated on speech", "_want_caps" in _names_guarding or "words" in _names_guarding,
      f"guarded by {sorted(_names_guarding)}; captions on a visual beat source "
      f"ask libass to render an empty file")
# AND THE GATE IS DERIVED FROM SPEECH, not merely named after it. RED-proving
# caught this: replacing `_want_caps = bool(words)` with `_want_caps = True`
# left the name in the guard, so the check above passed while the gate was gone.
# A check that survives the mutation it exists to catch is not yet a check.
_wc_from = set()
for _n in _ast.walk(_tree):
    if isinstance(_n, _ast.Assign) and any(
            isinstance(_t2, _ast.Name) and _t2.id == "_want_caps" for _t2 in _n.targets):
        for _v in _ast.walk(_n.value):
            if isinstance(_v, _ast.Name):
                _wc_from.add(_v.id)
check("the speech gate is DERIVED from the transcript words",
      "words" in _wc_from,
      f"_want_caps is assigned from {sorted(_wc_from) or 'a constant'} — a gate "
      f"named after speech but not computed from it is not a gate")

# The COMPOSITE has the same shape one layer down: it used to run only on the
# overlay SUCCESS path, so a job with captions and no text would have rendered a
# .mov and never laid it on the picture.
_comp_guards = set()
for _g in _enclosing_ifs(_tree, "/work/captioned.mp4"):
    for _t in _g:
        for _n in _ast.walk(_t):
            if isinstance(_n, _ast.Name):
                _comp_guards.add(_n.id)
check("the caption COMPOSITE is not gated on the text-overlay list either",
      "items" not in _comp_guards and "ov" not in _comp_guards and "r2" not in _comp_guards,
      f"conditions wrapping the composite reference {sorted(_comp_guards)}")

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
