#!/usr/bin/env python3
"""SMOKE: the zoom is not inert, and an inert placement fails the round.

Every zoom in every round of this corpus was inert. Two bugs in one expression:
`zoompan` with d=1 restarts per input frame so `zoom` never accumulated
(min(zoom+0.002, 1.12) == 1.002 forever), and no x/y meant it anchored top-left.
Three of five fixtures in round 26 declared zoom as their ONLY family with
kept=1.0 — visually unchanged video, scored ok=True, placements above zero.

TWO LEGS, BECAUSE ONE IS NOT ENOUGH — measured, not assumed:
    INERT zoom (1.002x)   33.46 dB
    REAL zoom  (1.118x)   31.19 dB     a generic diff cannot separate these
    re-encode, no change  68.25 dB     only this is separable by diff
So the coarse runtime leg catches "did literally nothing"; the cert measures
whether the CLAIMED geometry happened. Shipping only the diff would have been
the fifth false green in this lane, sold as the fix for the fourth.
"""
import ast, pathlib, sys, types

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

fails=[]
def check(l,c,d=""):
    if not c: fails.append(l + (f"  :: {d}" if d else ""))

src = pathlib.Path(A.__file__).read_text()

# ── 1. THE EXPRESSION ITSELF ───────────────────────────────────────────────
fg = A.zoom_filtergraph(1.0, 3.0, 1.12)
check("the filtergraph no longer accumulates via `zoom+`",
      "min(zoom+" not in fg,
      "d=1 restarts zoompan per frame, so `zoom` resets and never accumulates")
check("z is a function of in_time", "in_time" in fg and "1+0.120000*" in fg, fg[:120])
check("the zoom is centre-anchored", "iw/2-(iw/zoom/2)" in fg and "ih/2-(ih/zoom/2)" in fg,
      "zoompan defaults to x=0,y=0 — the top-left corner")
check("strength reaches the request", "0.120000" in fg, fg[:140])

# ── 2. HOISTED, so the cert reads the SHIPPED string ───────────────────────
tree = ast.parse(src)
tops = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
check("zoom_filtergraph is module level", "zoom_filtergraph" in tops,
      "a cert over an inline expression can only replay a copy")
check("the tool CALLS it rather than rebuilding the string",
      "f = zoom_filtergraph(" in src and src.count("zoompan=z=") == 1,
      "two copies of the expression will diverge")

# ── 3. THE RUNTIME LEG, on real files ──────────────────────────────────────
P = "/tmp/zoomab"
import os
if os.path.exists(f"{P}/pattern.mp4") and os.path.exists(f"{P}/reenc.mp4"):
    ch, db = A.step_changed_output(f"{P}/pattern.mp4", f"{P}/reenc.mp4", 1.0, 3.0)
    check("a no-op step is detected as unchanged", ch is False, f"psnr {db}")
    ch2, db2 = A.step_changed_output(f"{P}/pattern.mp4", f"{P}/armD_shipped.mp4", 1.0, 3.0)
    check("a real zoom is detected as changed", ch2 is True, f"psnr {db2}")
ch3, _ = A.step_changed_output("/nonexistent.mp4", "/also-nope.mp4", 0.0, 1.0)
check("unmeasurable returns None, never False",
      ch3 is None,
      "collapsing 'could not measure' into 'did nothing' is how absence "
      "becomes success — and the inverse would page on every missing file")

# ── 4. IT FAILS THE ROUND, not a log line ──────────────────────────────────
check("placement_inert is a CONTRACT failure",
      "placement_inert" in A.CONTRACT_FAILURES)
cv = A._contract_violations({"failures":[{"kind":"placement_inert","detail":"x"}]})
check("it surfaces through _contract_violations",
      any("placement_inert" in c for c in cv), str(cv))
check("build_zoom raises it", 'fail("placement_inert"' in src)
check("the coarse leg is only consulted when it says False",
      "if _chg is False:" in src,
      "acting on None would fail every run where ffmpeg could not measure")

# ── 5. THE CHECK REPORTS ITSELF ────────────────────────────────────────────
# Round 27 fired placement_inert zero times and that was indistinguishable from
# the check never running — no tool-result field reached the log. The zoom being
# real had to be proven by pulling the shipped object from S3 and measuring it
# by hand. A check nobody can read the output of is not yet a check.
check("the effect measurement is RECORDED on the ledger",
      'led.setdefault("placement_effects"' in src,
      "otherwise zero firings and a dead check are the same log line")
check("it is PRINTED in the run summary",
      "PLACEMENT EFFECT:" in src)
check("zero measurements prints a line rather than nothing",
      "none measured" in src,
      "silence is what made round 27 unreadable")
check("UNMEASURED is reported distinctly from moved and INERT",
      "UNMEASURED=" in src and "INERT=" in src)
check("reel_frames is recorded and printed",
      'led["reel_frames"] = rc.get("reel_frames")' in src and "REEL            :" in src,
      "the startup-vs-paint split of build_reel could not be settled without it")

if fails:
    print(f"PLACEMENT-EFFECT-WIRED: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("PLACEMENT-EFFECT-WIRED: PASS")
