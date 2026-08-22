#!/usr/bin/env python3
"""cert_rasterisation_split.py — THE LARGEST TERM MUST NOT BE 100% BLIND.

MEASURED 2026-08-22, from the production timeline JSON (not from an ASCII tree —
I misread one of those and reported a 12.7s gap that did not exist):

    277f6a2e  render_remotion dur=267.5s  unaccounted=267.5s  children=0
    bd3b6eed  render_remotion dur= 91.2s  unaccounted= 91.2s  children=0
    bc4d1128  render_remotion dur=  8.7s  unaccounted=  8.7s  children=0
    2b79465d  render_remotion dur= 22.6s  unaccounted= 22.6s  children=0

unaccounted == dur, every job. render_remotion is 80-85% of the render span and
none of it was attributed — the same signature `render` carried before v566, one
level deeper. Everything else is already eliminated: duration r=0.132,
components r=0.224, cuts r=0.064, upload/HLS/exports 1%, prep 3%, attempts=1.

  1  The wrapper exists and is TRANSPARENT — same return value. _remotion_subprocess
     returns elapsed seconds and callers use it; a wrapper that swallowed the
     return would silently zero every downstream timing print.
  2  Spans are parented to render_remotion, so they subdivide the blind term
     rather than inflating `render` beside it.
  3  Emitted in a FINALLY — a chunk that times out still reports its seconds.
     The failing chunk is precisely the one whose cost matters, because the
     degrade ladder re-renders on top of it.
  4  OVERLAP IS HANDLED, not summed. The pool runs chunks concurrently; the
     timeline must report union-coverage and derive parallel=True, never treat
     N x 100s inside a 120s parent as 500s of work. Driven against the real
     _JobTimeline.
  5  Instrumentation NEVER breaks the render: a raising _tl_add_done is
     swallowed.

    python3 cert_rasterisation_split.py
"""
import os
import re
import sys

os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    import handler as H
    fails = []
    raw = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
    src = "\n".join(re.sub(r"#.*$", "", ln) for ln in raw.splitlines())

    # ── 1 + 2 + 3: the wrapper's shape ──────────────────────────────────────
    has_raw = "_run_remotion_raw = _remotion_subprocess" in src
    m = re.search(r"def _run_remotion\(.*?\n(.*?)\n\s{4}def ", src, re.S)
    body = m.group(1) if m else ""
    returns = "return _run_remotion_raw(" in body
    finally_ = "finally:" in body
    parented = re.search(r'_tl_add_done\(\s*f"remotion:\{_rr_label\}".*?,\s*"(\w+)"',
                         body, re.S)
    print(f"  [1] alias captured={has_raw}  transparent return={returns}")
    print(f"  [3] emitted in finally={finally_}")
    print(f"  [2] span parent={parented.group(1) if parented else None}")
    if not has_raw or not returns:
        fails.append("the wrapper does not return the raw call's value — "
                     "_remotion_subprocess returns ELAPSED SECONDS that callers "
                     "print; swallowing it zeroes every downstream timing")
    if not finally_:
        fails.append("the span is not emitted in a finally — a chunk that times "
                     "out would report nothing, and that is the chunk whose cost "
                     "matters most")
    if not parented or parented.group(1) != "render_remotion":
        fails.append(f"chunk spans are parented to "
                     f"{parented.group(1) if parented else None!r}, not "
                     f"'render_remotion' — they would inflate `render` beside "
                     f"the blind term instead of subdividing it")

    # ── 4: overlap is union-covered, not summed ────────────────────────────
    tl = H._JobTimeline()
    tl.add("render", 0.0, 300.0, "job")
    tl.add("render_remotion", 10.0, 130.0, "render")
    for i in range(4):                      # 4 chunks, 100s each, CONCURRENT
        tl.add(f"remotion:overlay-{i:02d}", 15.0, 115.0, "render_remotion")
    node = H._JobTimeline.finalize(tl)
    rr = None

    def _walk(n):
        nonlocal rr
        if n.get("name") == "render_remotion":
            rr = n
        for c in n.get("children") or []:
            _walk(c)
    _walk(node)
    print(f"  [4] 4 concurrent 100s chunks in a 120s parent -> "
          f"children={len(rr['children'])} unaccounted={rr['unaccounted']:.1f}s "
          f"parallel={rr.get('parallel')}")
    if not rr or len(rr["children"]) != 4:
        fails.append("the concurrent chunks did not attach")
    elif rr["unaccounted"] > 25:
        fails.append(f"unaccounted {rr['unaccounted']:.1f}s on a parent whose "
                     f"children cover 100 of its 120s — union coverage is broken")
    elif not rr.get("parallel"):
        fails.append("parallel was not DERIVED for overlapping children — the "
                     "tree would read 4x100s as sequential work")

    # ── 5: telemetry failure cannot break the render ───────────────────────
    guarded = bool(re.search(r"finally:\s*\n\s*try:\s*\n\s*_tl_add_done", body, re.S))
    print(f"  [5] _tl_add_done guarded against raising: {guarded}")
    if not guarded:
        fails.append("a raising _tl_add_done would propagate out of the finally "
                     "and kill a render that had already succeeded")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT RASTERISATION-SPLIT: FAIL")
        return 1
    print("  NOTE: asserts the WIRING and the union arithmetic. That "
          "render_remotion actually reports children is proven only by reading "
          "stage_timings.timeline on a real job — unaccounted must stop equalling dur.")
    print("  CERT RASTERISATION-SPLIT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
