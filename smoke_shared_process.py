#!/usr/bin/env python3
"""SMOKE: the shared-process renderer exists, is mounted, and reports its saving.

WHAT IT REMOVES, measured in-container: bundle 9.79s + selectComposition 2.05s +
renderMedia overhead 0.40s = 12.24s per PROCESS, paid by every `npx remotion
render`. Captions, cards and zooms each spawning their own pays it three times.

WHAT IT SAVES TODAY: close to nothing, and that is recorded rather than hidden.
Lever 2 collapsed the rule/execute loop first, so talking_head now makes ~2 real
renders rather than 4 — half the "four renders become one" prize was already
collected by the change before this one. The reason to build it is captions
(~885 frames) and zooms joining the SAME process; the number to quote is the one
measured after they land, not the one that justified the queue.

ALPHA VIA THE NODE API. The CLI refuses --pixel-format=yuva*, which forced the
single-render path into PNG sequences. renderMedia accepts prores 4444 +
yuva444p10le directly — verified by ffprobe on a local render reporting
`prores, yuva444p12le`. One .mov instead of thousands of PNGs.
"""
import ast, os, pathlib, sys, types

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

HERE = pathlib.Path(__file__).parent
src = pathlib.Path(A.__file__).read_text()
mjs_path = HERE / "remotion_batch.mjs"
fails=[]
def check(l,c,d=""):
    if not c: fails.append(l + (f"  :: {d}" if d else ""))

# ── it exists as a real symbol, not just source text ──────────────────────
check("render_remotion_batch is importable", hasattr(A, "render_remotion_batch"),
      "source is where code might be; runtime is where it is")
check("the batch script is on disk", mjs_path.exists())
check("the batch script is MOUNTED into the image",
      "_BATCH_MJS" in src and "/promptly-remotion/remotion_batch.mjs" in src,
      "a deferred file must be backed by an image mount or it is a silent degrade")

mjs = mjs_path.read_text()
# ── one bundle, many renders — the entire point ───────────────────────────
check("it bundles exactly once", mjs.count("await bundle(") == 1,
      "bundling per job would reintroduce the 12.24s it exists to remove")
check("it renders in a loop over the queue", "for (const j of jobs)" in mjs)
check("alpha goes through prores 4444, not a PNG sequence",
      "yuva444p10le" in mjs and "proResProfile" in mjs,
      "the CLI refuses yuva*; the Node API does not")

# ── per-job status, so one bad job does not lose the batch ────────────────
check("each job reports its own outcome", 'console.log(`JOB ' in mjs)
check("a failing job is caught, not thrown", "catch (e)" in mjs,
      "one bad composition must not take the others down")
check("the caller parses per-job results",
      'line.startswith("JOB ")' in src)

# ── the saving is REPORTED, per the standing rule ─────────────────────────
check("the batch records what startup was amortised over",
      '"startup_amortised_over"' in src,
      "any counter added to answer a question gets printed in the commit that "
      "adds it — three failures of this in one session")
check("bundle time is captured so the saving can be measured, not assumed",
      '"bundle_ms"' in src)

# ── THE MEASUREMENT SETTING MUST NOT LEAK INTO THE THING MEASURED ─────────
# It shipped at concurrency 1, copied from the probe where 1 was deliberate to
# keep the marginal ms/frame clean — after that same probe established 8 is
# 2.63x faster. Round 32 painted 443 caption frames at 299.1 ms/frame.
check("the batch does NOT hardcode concurrency 1",
      "concurrency: 1," not in mjs,
      "that is the measurement harness's setting, not production's")
check("concurrency defaults to the measured flat top of the curve",
      "PROMPTLY_REMOTION_CONCURRENCY || 8" in mjs,
      "saturates at 4; 8 is the top of the plateau on an 8-CPU box")

if fails:
    print(f"SHARED-PROCESS: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("SHARED-PROCESS: PASS")
