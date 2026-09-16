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
import modal_stub                                         # noqa: E402
modal_stub.install()
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
# RUN, NOT WALKED. The structural form of this could not tell a CONJUNCTION
# from a DISJUNCTION: `if items:` (the defect) and `speech OR text` (correct)
# both put `items` in a wrapping condition. It fired on the correct one.
check("alpha_pass_needed is importable at runtime", 
      callable(getattr(A, "alpha_pass_needed", None)))
check("a SPEECH job that rules ZERO text overlays still renders captions",
      A.alpha_pass_needed(True, 40, 0) is True,
      "this is the original defect: captions gated on the text family")
check("a NO-SPEECH job with text overlays still gets the alpha pass",
      A.alpha_pass_needed(False, 0, 3) is True,
      "text on a silent source used to fall through to the ffmpeg burn")
check("speech with no transcribed words does not open the pass",
      A.alpha_pass_needed(True, 0, 0) is False)
check("neither family means no pass", A.alpha_pass_needed(False, 0, 0) is False)
check("the guard in execute_plan IS that predicate",
      "alpha_pass_needed(_want_caps, len(_cap_words), len(items))" in src,
      "a predicate nothing calls is not a guard")
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

# ── THE ROTATION RULE IS FED, NOT MERELY IMPLEMENTED ──────────────────────
# pick_caption_style has carried `recent` since the port, and the ONLY call site
# passed `pick_caption_style(brief)` — so the rule was structurally present and
# UNEXERCISED on every run ever made. Its own docstring said so, which is why it
# was a wiring gap rather than a false green; wiring is what closes it.
#
# The history is PASSED IN, never fetched: production reads it from the stored
# style profile over Supabase, and this container deliberately holds no
# credentials.
_pcs_calls = []
for _n in _ast.walk(_tree):
    if (isinstance(_n, _ast.Call) and isinstance(_n.func, _ast.Name)
            and _n.func.id == "pick_caption_style"):
        _pcs_calls.append({k.arg for k in _n.keywords})
check("pick_caption_style is called somewhere", bool(_pcs_calls))
check("EVERY call site passes `recent` — a default of () is the inert case",
      all("recent" in kw for kw in _pcs_calls),
      f"{sum(1 for k in _pcs_calls if 'recent' not in k)} of {len(_pcs_calls)} "
      f"call site(s) let it default to empty")
check("edit() accepts the history from its caller",
      "recent_styles" in [a.arg for _f in _ast.walk(_tree)
                          if isinstance(_f, _ast.FunctionDef) and _f.name == "edit"
                          for a in _f.args.args + _f.args.kwonlyargs],
      "the container cannot read the user profile — it holds no credentials, so "
      "the history has to arrive as an argument")
check("the entrypoint forwards it BY KEYWORD",
      "recent_styles=recent_styles" in src,
      "it sits after exec_model; appended positionally it would bind to "
      "cap_exec_effort and become a boolean")
# BOTH HALVES, SEPARATELY. RED-proving caught this too: deleting the ledger
# WRITE left the name in the PRINT statement, so a single substring check passed
# while nothing was being recorded.
check("what the rule received is RECORDED",
      'led["caption_recent_in"] = _recent' in src)
check("and it is PRINTED", "recent={(r.get('ledger') or {}).get('caption_recent_in')" in src,
      "a rotation that rotated on nothing reads identically to one that rotated")

# ── THE PROPS ACTUALLY REACH THE COMPOSITION ──────────────────────────────
# THE MOST EXPENSIVE FALSE GREEN THIS PORT PRODUCED. remotion_batch.mjs passed
# `JSON.parse(file).input` as inputProps while BOTH compositions read
# `props.input` — so the unwrapped object merged in beside a defaultProps that
# still carried `input`, and every render silently used DEFAULT_RENDER_INPUT:
# 600 frames, 60fps, `caption.pages: []`. Six hundred frames of NOTHING,
# reported as `path=remotion composited=True` because the file existed and
# ffmpeg exited 0.
#
# MEASURED LOCALLY, both nestings, actual output:
#   overlay unwrapped (shipped)  compDuration 600   21,028,986 bytes
#   overlay wrapped              compDuration  20    1,663,820 bytes
# After the fix, a 52-frame 15fps request produced exactly 52 frames at 15/1
# with alpha varying frame to frame (YAVG 256 -> 308) — real animating captions.
_batch_src = pathlib.Path(A.__file__).with_name("remotion_batch.mjs")
check("remotion_batch.mjs is beside the app", _batch_src.exists())
if _batch_src.exists():
    _bs = _batch_src.read_text()
    check("the batch passes the WHOLE props file, not `.input`",
          'readFileSync(j.propsFile, "utf8")).input' not in _bs
          and 'JSON.parse(fs.readFileSync(j.propsFile, "utf8"));' in _bs,
          "stripping the wrapper makes every composition fall back to "
          "defaultProps, which renders and reports success")

# THE CATEGORICAL CHECK: ask the ARTIFACT, never the request.
check("_probe_frame_count exists at runtime",
      callable(getattr(A, "_probe_frame_count", None)))
check("the caption job DECLARES how many frames it expects",
      '"expect_frames": _cap_frames' in src,
      "without a declared expectation there is nothing to compare the file to")
check("the batch measures frames off the FILE",
      '_d["frames_actual"] = _probe_frame_count(' in src)
check("unmeasurable frames are None, never a pass",
      '_d["frames_ok"] = (None if _d["frames_actual"] is None' in src,
      "the same law the effect legs carry")
check("a mismatch FAILS the round", "render_frames_mismatch" in A.CONTRACT_FAILURES)
# GUARDED BY THE MEASUREMENT, not merely present in the file. RED-proving
# caught this: neutering the condition to `if False:` left the fail() call in
# the source, so a substring check passed while the raise was unreachable.
_fm_guards = set()
for _g in _enclosing_ifs(_tree, "render_frames_mismatch"):
    for _t in _g:
        for _n in _ast.walk(_t):
            if isinstance(_n, _ast.Constant) and isinstance(_n.value, str):
                _fm_guards.add(_n.value)
check("the mismatch raise is guarded by the MEASURED result",
      "frames_ok" in _fm_guards,
      f"guarded by {sorted(_fm_guards)} — a fail() the condition can never "
      f"reach is not a raise")
check("the actual frame count is PRINTED",
      "frames_actual={_cr.get('frames_actual')}" in src,
      "two rounds reported a frame count Python had only requested")

# ── TEXT MOVED ONTO THIS PASS, AND THE ffmpeg BURN NO LONGER DRAWS IT ─────
# build_overlays re-encoded the whole video to draw text with drawtext — 32.20s
# for ten items over a 23.17s output on round 33 — across a span this alpha
# layer already covers frame for frame. Passing `items` to BOTH would
# double-draw every overlay: once in the layer, once burned underneath it.
check("the alpha pass carries the text overlays",
      "text_overlays=_text_overlays" in src)
# COUNTED, NOT PRESENT. The literal sits at TWO ledger writes (14360 and
# 14408) and an `in` leg is satisfied by either — so deleting the one that
# matters leaves this green, which is the whole failure this smoke exists to
# prevent one layer up. Assert the count: a third site is a commit that has to
# say why, and a second deletion fails here.
_n_rec = src.count('"text_overlays": len(_text_overlays),')
check("how many it carried is RECORDED, at BOTH ledger writes", _n_rec == 2,
      "a text family that silently carried zero reads exactly like one that "
      "carried ten — and this is written at two sites, found %d" % _n_rec)
check("the ffmpeg burn is handed NO text",
      "build_overlays([], _want_caps, cur" in src,
      "passing items here as well draws every overlay twice")
check("the burn survives only as the caption fallback",
      "_need_burn = _want_caps and not led.get(\"caption_mov\")" in src
      and "if _need_burn:" in src)
check("the text family's effect is measured where the text now LANDS",
      '_record_effect("text", _cc_before, _cco,' in src,
      "measuring it at a burn that no longer happens would report every "
      "overlay inert")

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
