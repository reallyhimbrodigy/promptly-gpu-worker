"""ONE-CLOCK TIMELINE invariant (Zac 2026-08-02 'one clock'): the per-job
wall-clock tree must satisfy union(children) + unaccounted == parent at EVERY
node, parallel must be DERIVED (not asserted), and gaps must be explicit — that
single rule is what catches a hidden span (the 130s class). Pure, no network.
  python3 test_one_clock_timeline.py"""
import sys
sys.path.insert(0, ".")
from handler import _JobTimeline


def _covered(node):
    return round(node["dur"] - node["unaccounted"], 1)


def test():
    # ── overlapping (parallel) + sequential + tail gap ──
    tl = _JobTimeline()
    tl.now = lambda: 150.0
    tl.add("a", 0, 100, "job")     # ┐ overlap 50-100 → parallel
    tl.add("b", 50, 120, "job")    # ┘
    tl.add("c", 130, 140, "job")   # sequential; gap 120-130 and tail 140-150
    tr = tl.finalize()
    assert abs(tr["dur"] - 150.0) < 0.1, tr["dur"]
    # union = [0,120] ∪ [130,140] = 120 + 10 = 130 → unaccounted 20
    assert abs(tr["unaccounted"] - 20.0) < 1.0, f"unaccounted={tr['unaccounted']} want 20"
    assert abs(_covered(tr) - 130.0) < 1.0, _covered(tr)
    # INVARIANT: covered(children union) + unaccounted == parent, within 1s
    assert abs(_covered(tr) + tr["unaccounted"] - tr["dur"]) < 1.0
    # parallel DERIVED: a+b+c sum durations 100+70+10=180 > union 130
    assert tr["parallel"] is True, "overlapping children must derive parallel=True"

    # ── nested parent with a hidden gap (the 130s shape) ──
    tl2 = _JobTimeline()
    tl2.now = lambda: 200.0
    tl2.add("edit_plan", 0, 189, "job")     # the pre-render critical path
    tl2.add("gemini_call", 10, 70, "edit_plan")  # only 60 of 189 explained
    tr2 = tl2.finalize()
    ep = next(c for c in tr2["children"] if c["name"] == "edit_plan")
    assert ep["unaccounted"] > 120.0, f"the 130s gap must be VISIBLE, got {ep['unaccounted']}"
    assert abs(_covered(ep) + ep["unaccounted"] - ep["dur"]) < 1.0

    # ── sequential-only → parallel False ──
    tl3 = _JobTimeline()
    tl3.now = lambda: 100.0
    tl3.add("x", 0, 40, "job")
    tl3.add("y", 40, 80, "job")
    tr3 = tl3.finalize()
    assert tr3["parallel"] is False, "non-overlapping children must be parallel=False"
    assert abs(tr3["unaccounted"] - 20.0) < 1.0  # tail gap 80-100

    # ── empty tree: no children → all time unaccounted, no crash ──
    tl4 = _JobTimeline()
    tl4.now = lambda: 42.0
    tr4 = tl4.finalize()
    assert abs(tr4["unaccounted"] - 42.0) < 0.1 and tr4["children"] == []

    print("[test] one-clock timeline: ALL PASS "
          "(invariant union+unaccounted==parent, derived-parallel, explicit 130s-shape gap, empty-safe)")


if __name__ == "__main__":
    test()
