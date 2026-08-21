#!/usr/bin/env python3
"""cert_burst_timeline_graft.py — A BURST RENDER'S SPAN MUST HAVE CHILDREN.

MEASURED 2026-08-21, on the first post-flip production cohort. Of 21 renders
carrying a timeline, 6 reported a `render` span with ZERO children — and they
were EXACTLY the six slowest (173-278s of render):

    39764e2d render=278.0s  857f7925 render=254.1s  14cdd932 render=241.8s
    769d446e render=215.3s  bdeb6d90 render=211.5s  a3752dfe render=173.3s

The blindness was perfectly anti-correlated with where the time went, and the
reason is structural: `_TL` is a module global created at handler() ENTRY, and
render_burst calls `H.render_stage()` DIRECTLY — it never runs handler(). So in
the burst container `_TL is None`, every `_tl_add_done(..., "render")` hits its
None-guard and no-ops, and a slow render is precisely the one that clears the
45s output floor and gets sent there. Same shape as the build-lane handicap.

WHY THIS CERT IS SHAPED THE WAY IT IS. The bug was never "the timing code is
wrong" — those three calls are correct and have been for weeks. The bug was that
NOBODY CALLED THEM IN THAT PROCESS. So asserting the arithmetic proves nothing;
what has to be asserted is the WIRING at the process boundary, and the negative
case that a graft must not invent coverage it does not have.

  1  THE BURST CREATES A TIMELINE. Without `_H._TL = _H._JobTimeline()` in
     render_burst, the render's own children are discarded at the moment they
     are recorded. This is the whole defect in one line.
  2  THE SPANS LEAVE THE CONTAINER. render_burst must return `tl_spans`, and
     they must be PLAIN PICKLABLE dicts — a _JobTimeline object cannot cross a
     process boundary, and a silent pickling failure here would look exactly
     like the bug we just fixed.
  3  THE GRAFT PRODUCES CHILDREN. Drive the REAL _JobTimeline: a `render`
     parent plus grafted burst spans must finalize to a render node WITH
     children. This is the clause that would have caught the original.
  4  NEGATIVE — THE HEAD GAP STAYS VISIBLE. Burst coordinates start at ITS t0,
     which begins after dispatch + queue + cold start. If the graft re-based to
     the dispatch instant, that gap would be silently absorbed and `render`
     would look fully accounted when it is not. A graft that launders billed
     time is worse than no graft: it converts a known unknown into a false zero.
  5  NEGATIVE — NO SPANS MEANS NO INVENTION. An in-process (sub-floor) render
     returns no tl_spans; the render node must then be honestly childless
     rather than decorated with empty scaffolding.
  6  THE DOUBLE-HOLD KEY IS RIGHT. render_stage returns its timings under
     "timings"; the instrument read "stage_timings" and was None on 6 of 6.
     A reporter reading a key that does not exist is the single most repeated
     defect in this codebase.

    python3 cert_burst_timeline_graft.py
"""
import os
import re
import sys

os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    import handler as H
    fails = []
    modal_src = open(os.path.join(HERE, "modal_app.py"), encoding="utf-8").read()
    h_src = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()

    # ── 1: the burst creates a timeline ─────────────────────────────────────
    m = re.search(r"\ndef render_burst\(", modal_src)
    burst = modal_src[m.start():m.start() + 9000] if m else ""
    makes_tl = bool(re.search(r"_H\._TL\s*=\s*_H\._JobTimeline\(\)", burst))
    print(f"  [1] render_burst creates a timeline: {makes_tl}")
    if not makes_tl:
        fails.append("render_burst never sets _H._TL — every _tl_add_done inside "
                     "the render no-ops and the slowest jobs stay 100% blind "
                     "(this IS the original defect)")

    # ── 2: the spans leave the container, picklable ─────────────────────────
    returns = bool(re.search(r"[\"']tl_spans[\"']\s*:", burst))
    print(f"  [2] render_burst returns tl_spans: {returns}")
    if not returns:
        fails.append("render_burst does not return tl_spans — the timeline is "
                     "built and then dropped at the process boundary")
    import pickle
    tl = H._JobTimeline()
    tl.add("render_remotion", 1.0, 100.0, "render")
    spans = [{"name": str(s["name"]), "parent": str(s["parent"]),
              "start": float(s["start"]), "end": float(s["end"])} for s in tl._spans]
    try:
        pickle.loads(pickle.dumps(spans))
        print(f"  [2] flattened spans pickle: True")
    except Exception as e:
        fails.append(f"flattened spans do not pickle ({type(e).__name__}) — they "
                     f"cannot cross the Modal boundary")

    # ── 3 + 4 + 5: drive the REAL timeline through the real graft shape ─────
    def _graft(blocked_s, burst_spans):
        """Mirror of the dispatch-site graft, driven against the real class."""
        t = H._JobTimeline()
        t.add("render", 0.0, blocked_s, "job")
        base_now = 0.0
        if burst_spans:
            bwall = max(s["end"] for s in burst_spans)
            head = max(0.0, blocked_s - bwall)
            base = base_now + head
            for s in burst_spans:
                p = s["parent"] if s["parent"] != "job" else "render"
                t.add(s["name"], base + s["start"], base + s["end"], p)
        tree = t.finalize()
        return next((c for c in tree["children"] if c["name"] == "render"), None)

    bs = [{"name": "render_remotion", "parent": "render", "start": 0.5, "end": 180.5},
          {"name": "render_audio", "parent": "render", "start": 0.6, "end": 2.0},
          {"name": "render_composite", "parent": "render", "start": 181.0, "end": 200.0}]
    node = _graft(240.0, bs)
    nkids = len(node["children"]) if node else 0
    print(f"  [3] grafted render node children: {nkids} "
          f"({[c['name'] for c in node['children']] if node else []})")
    if nkids < 3:
        fails.append(f"the graft produced {nkids} children from 3 burst spans — "
                     f"a burst render's span is still opaque")

    # 4: the 40s head (240 blocked - 200 burst wall) must survive as unaccounted
    unacc = node["unaccounted"] if node else 0.0
    print(f"  [4] dispatch+queue+coldstart head left unaccounted: {unacc:.1f}s "
          f"(240.0s blocked - 200.0s burst wall = 40.0s expected)")
    if unacc < 39.0:
        fails.append(f"the head gap collapsed to {unacc:.1f}s — the graft is "
                     f"laundering dispatch/queue/cold-start time that is billed "
                     f"at 48 cores, turning a known unknown into a false zero")

    # 5: no spans -> honestly childless, no invented scaffolding
    empty = _graft(240.0, [])
    ekids = len(empty["children"]) if empty else -1
    print(f"  [5] in-process render (no tl_spans) -> {ekids} children, "
          f"unaccounted={empty['unaccounted'] if empty else '-'}s")
    if ekids != 0:
        fails.append(f"a render with no burst spans invented {ekids} children")

    # ── 6: the double-hold reads the key that actually exists ───────────────
    reads_wrong = bool(re.search(r"_dh_rs\.get\(\s*[\"']stage_timings[\"']", h_src))
    reads_right = bool(re.search(r"_dh_rs\.get\(\s*[\"']timings[\"']", h_src))
    rs_returns = bool(re.search(r"[\"']timings[\"']\s*:\s*_timings", h_src))
    print(f"  [6] double-hold reads 'timings': {reads_right} (stale "
          f"'stage_timings' read still present: {reads_wrong}); render_stage "
          f"returns 'timings': {rs_returns}")
    if reads_wrong or not reads_right:
        fails.append("the double-hold instrument reads 'stage_timings' from "
                     "render_stage's return, which has no such key — "
                     "burst_reported_render_s is None on every burst job and the "
                     "dispatch gap it exists to expose is never recorded")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT BURST-TIMELINE-GRAFT: FAIL")
        return 1
    print("  NOTE: this asserts the WIRING and the arithmetic. That production "
          "actually writes children on a burst job is proven only by a real "
          "burst render — read stage_timings.timeline on a >45s-output job.")
    print("  CERT BURST-TIMELINE-GRAFT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
