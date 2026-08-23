#!/usr/bin/env python3
"""cert_edit_plan_accounted.py — THE PLAN STAGE MUST ACCOUNT FOR ITS OWN SECONDS.

MEASURED 2026-08-23 across 77 editorial jobs: `edit_plan` is 68.8s at p50 with
45% UNACCOUNTED. Its only children were gemini_call[post-cuts] (31.2s),
proxy_encode (0.9s) and proxy_upload (0.0s).

WHY THAT 45% COST SOMETHING REAL. TARGET_ARCHITECTURE.md sized "stream the plan"
as recovering 68.5s of blocking. It cannot: streaming can only touch the Gemini
call, and the rest of the stage was never measured. A lever was scoped against a
number that was mostly dark — the SECOND time in two days (the render's dark
seconds were the first, where prep turned out to be 3%).

ROOT: `edit_plan` is a 3-line span around `future_edit.result()`, and the future
it awaits itself waits on SEVEN upstream futures — transcript, proxy encode,
trend, shot changes, vocal emphasis, loudness, faces — none of which emitted a
child span.

  1  Every one of the seven waits is instrumented. Named individually because
     the point is to find the LONG POLE; a single "waits" span would say the
     stage is blocked without saying on what, which is the situation today.
  2  Spans are parented to `edit_plan`, not to `job` — a wait parented at the
     root inflates the job tree and leaves edit_plan just as blind.
  3  _tl_wait RETURNS the future's value. It wraps `.result()` calls whose
     values feed the prompt; swallowing one would not slow the pipeline, it
     would silently plan against None.
  4  It ends the span in a `finally`, so a future that RAISES still reports the
     seconds it burned — a failing dependency is exactly the one worth timing.
  5  ARITHMETIC on the real _JobTimeline: adding the wait spans must reduce
     `edit_plan`'s unaccounted.

    python3 cert_edit_plan_accounted.py
"""
import os, re, sys
os.environ.setdefault("APP_URL", "")
HERE = os.path.dirname(os.path.abspath(__file__))
WAITS = ("wait_transcript", "wait_proxy_encode", "wait_trend", "wait_shot_changes",
         "wait_vocal_emphasis", "wait_loudness", "wait_faces")


def main():
    import handler as H
    fails = []
    raw = open(os.path.join(HERE, "handler.py"), encoding="utf-8").read()
    src = "\n".join(re.sub(r"#.*$", "", ln) for ln in raw.splitlines())

    # ── 1: all seven, individually named ───────────────────────────────────
    missing = [w for w in WAITS if f'"{w}"' not in src]
    print(f"  [1] instrumented waits: {len(WAITS)-len(missing)}/{len(WAITS)}")
    if missing:
        fails.append(f"un-instrumented wait(s): {missing} — the plan stage stays "
                     f"blind on exactly the dependency that may be the long pole")

    # ── 2: parented to edit_plan ───────────────────────────────────────────
    m = re.search(r'def _tl_wait\(name, fn, parent="(\w+)"\)', src)
    print(f"  [2] _tl_wait default parent: {m.group(1) if m else None}")
    if not m or m.group(1) != "edit_plan":
        fails.append("the wait spans do not default to the edit_plan parent — "
                     "parented at the job root they inflate the tree and leave "
                     "edit_plan just as unaccounted")

    # ── 3 + 4: returns the value, ends in finally ──────────────────────────
    body = re.search(r"def _tl_wait\(.*?\n(.*?)\n\n\ndef ", src, re.S)
    b = body.group(1) if body else ""
    print(f"  [3] returns the future's value: {'return fn()' in b}")
    print(f"  [4] ends the span in finally  : {'finally:' in b and '_tl_end' in b}")
    if "return fn()" not in b:
        fails.append("_tl_wait does not return fn() — these wrap .result() calls "
                     "whose values feed the prompt; the pipeline would plan "
                     "against None rather than fail loudly")
    if not ("finally:" in b and "_tl_end" in b):
        fails.append("_tl_wait does not end its span in a finally — a dependency "
                     "that RAISES would report nothing, and that is the one "
                     "worth timing")

    # ── 5: the arithmetic, driven against the real class ───────────────────
    tl = H._JobTimeline()
    tl.add("edit_plan", 0.0, 70.0, "job")
    tl.add("gemini_call[post-cuts]", 40.0, 70.0, "edit_plan")
    bare = H._JobTimeline()
    bare.add("edit_plan", 0.0, 70.0, "job")
    bare.add("gemini_call[post-cuts]", 40.0, 70.0, "edit_plan")
    for i, nm in enumerate(WAITS):
        tl.add(nm, 1.0 + i, 38.0, "edit_plan")

    def _ep(t):
        return next(c for c in t.finalize()["children"] if c["name"] == "edit_plan")
    got, base = _ep(tl), _ep(bare)
    print(f"  [5] unaccounted WITH waits {got['unaccounted']:.1f}s vs WITHOUT "
          f"{base['unaccounted']:.1f}s")
    if got["unaccounted"] >= base["unaccounted"]:
        fails.append("adding the wait spans did not reduce edit_plan's "
                     "unaccounted — they are not covering real stage wall")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT EDIT-PLAN-ACCOUNTED: FAIL")
        return 1
    print("  NOTE: asserts the WIRING and the arithmetic. Which dependency is the "
          "long pole is answered only by production — read the edit_plan children "
          "on a real job.")
    print("  CERT EDIT-PLAN-ACCOUNTED: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
