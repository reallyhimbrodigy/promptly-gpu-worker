#!/usr/bin/env python3
"""cert_render_prep_accounted.py — THE RENDER MUST ACCOUNT FOR ITS OWN SECONDS.

MEASURED 2026-08-22. `render` unaccounted is 17.1s at p50 but 499.0s at max, and
THE TAIL IS THE UNACCOUNTED:

    e4750766  render 750.7s = remotion 241.6 + composite 14.6 + upload 4.1
                              -> 494.9s DARK  (upload_export explains 1%)
    40c3ddc5  render 632.2s -> 489.7s dark
    c193e0a8  render 597.7s -> 343.4s dark

And no PLAN variable predicts it — duration r=0.132, components r=0.224, cuts
r=0.064, all on the full population including the tail. So the seconds are spent
inside the render and nothing named them. Three spans and one counter close it:

  render_prep                    catch-all, entry -> Remotion spawn
  render_zoom_pre_extract        ffmpeg decode per zoom clip
  render_transition_pre_extract  ffmpeg decode per transition
  render_attempts                ladder retries, COUNTED not absorbed

WHY THE COUNTER MATTERS SEPARATELY. A rung-2 retry re-runs the ENTIRE render.
Two 240s renders and one 480s render are identical on every dashboard we have
and need OPPOSITE fixes. degen_retries counts Gemini degeneration, not this, and
read 0 on every job that retried.

  1  All three spans attach to `render`, not to `job`. A prep span parented at
     the root would inflate the job tree and still leave render unaccounted.
  2  render_prep is a CATCH-ALL: it must cover the pre-extracts, so its duration
     is >= their sum. If prep were merely another sibling, a gap between them
     would stay dark and this whole exercise would repeat.
  3  The retry counter is per-JOB: it resets at handler entry, not in a setter.
     This is the _component_ledger_reset lesson stated as an assertion — that
     one lived in _asr_diag_set and was wiped by the slowest jobs.
  4  render_attempts is PERSISTED, nested under stage_timings so
     content-studio's top-level key strip cannot eat it (the class that hid
     gemini_tokens, vad_coverage, _lang_bundle and source_duration).
  5  A timeline with these children leaves materially LESS unaccounted than one
     without — driven against the real _JobTimeline, since the point is the
     arithmetic, not the presence of a string.

    python3 cert_render_prep_accounted.py
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
    # comments stripped: a token in prose proves nothing about code, and this
    # cert's own sibling made exactly that mistake yesterday.
    src = "\n".join(re.sub(r"#.*$", "", ln) for ln in raw.splitlines())

    # ── 1: the spans exist and are parented to `render` ─────────────────────
    for name in ("render_prep", "render_zoom_pre_extract",
                 "render_transition_pre_extract"):
        m = re.search(r'_tl_add_done\(\s*f?"' + name + r'"[^)]*?,\s*"(\w+)"\s*\)',
                      src, re.S)
        parent = m.group(1) if m else None
        print(f"  [1] {name:32} parent={parent}")
        if not m:
            fails.append(f"{name} span is not emitted — the seconds it covers "
                         f"stay in unaccounted")
        elif parent != "render":
            fails.append(f"{name} is parented to {parent!r}, not 'render' — it "
                         f"would inflate the job tree and leave render blind")
    # NOTE the character class: the duration argument is `time.time() - _t0`,
    # which CONTAINS a paren, so an [^)]* run stops short and the parent never
    # matches. The first cut of this clause did exactly that and failed a
    # correctly-wired span — a false RED is as expensive as a false GREEN,
    # because it teaches you to distrust the gate.
    m = re.search(r'_tl_add_done\(\s*f"render_attempt_rung\{_rung\}"'
                  r'.*?,\s*"(\w+)"\s*\)', src, re.S)
    print(f"  [1] render_attempt_rung<N>          parent="
          f"{m.group(1) if m else None}")
    if not m or m.group(1) != "render":
        fails.append("the per-attempt span is missing or misparented — ladder "
                     "cost stays inseparable from render cost")

    # ── 2: prep is a CATCH-ALL that encloses the pre-extracts ───────────────
    i_prep = src.find("_prep_t0 = time.time()")
    i_zoom = src.find("_t_pre_extract_all = time.time()")
    i_trans = src.find("_t_trans_extract = time.time()")
    i_close = src.find("_tl_add_done(\"render_prep\"")
    print(f"  [2] prep opens before zoom={i_prep < i_zoom} "
          f"transition={i_prep < i_trans}; closes after both="
          f"{i_close > i_zoom and i_close > i_trans}")
    if not (0 < i_prep < i_zoom and i_prep < i_trans):
        fails.append("render_prep does not open before the pre-extracts — it is "
                     "not a catch-all, so a gap between spans stays dark")
    if not (i_close > i_zoom and i_close > i_trans):
        fails.append("render_prep closes before the pre-extracts finish — it "
                     "under-reports exactly the work it exists to bound")

    # ── 3: the retry counter is per-JOB, reset at handler entry ────────────
    at_entry = "_RENDER_ATTEMPTS[0] = 0" in src.split("del _GEMINI_CALL_LOG[:]")[-1][:1200]
    in_setter = bool(re.search(r"def _asr_diag_\w+\([^)]*\):(?:(?!\ndef ).)*?"
                               r"_RENDER_ATTEMPTS", src, re.S))
    print(f"  [3] reset at handler entry={at_entry}  hidden in a setter={in_setter}")
    if not at_entry:
        fails.append("_RENDER_ATTEMPTS is never reset at handler entry — a warm "
                     "container would carry the previous job's retry count")
    if in_setter:
        fails.append("_RENDER_ATTEMPTS is reset inside an ASR setter — the exact "
                     "shape that erased the component ledger on the slowest jobs")

    # ── 4: persisted, and NESTED ───────────────────────────────────────────
    i_attempts = src.find('"render_attempts": int(_RENDER_ATTEMPTS[0])')
    i_tokens = src.find('"gemini_tokens"')
    i_timeline = src.find('"timeline": _tl_report()')
    nested = i_attempts > 0 and i_timeline > 0 and abs(i_attempts - i_timeline) < 8000
    print(f"  [4] render_attempts persisted={i_attempts > 0} nested with the "
          f"other strip-proof keys={nested}")
    if i_attempts < 0:
        fails.append("render_attempts is never written to the payload — the "
                     "retry stays invisible, which is the defect")
    elif not nested:
        fails.append("render_attempts is not nested near timeline/gemini_tokens "
                     "— a top-level key is stripped by content-studio, the class "
                     "that hid five other fields")

    # ── 5: the arithmetic, on the REAL timeline ────────────────────────────
    tl = H._JobTimeline()
    tl.add("render", 0.0, 600.0, "job")
    tl.add("render_prep", 5.0, 400.0, "render")
    tl.add("render_zoom_pre_extract", 50.0, 380.0, "render")
    tl.add("render_remotion", 400.0, 560.0, "render")
    node = next(c for c in tl.finalize()["children"] if c["name"] == "render")
    bare = H._JobTimeline()
    bare.add("render", 0.0, 600.0, "job")
    bare.add("render_remotion", 400.0, 560.0, "render")
    bare_node = next(c for c in bare.finalize()["children"] if c["name"] == "render")
    print(f"  [5] unaccounted WITH prep spans {node['unaccounted']:.1f}s vs "
          f"WITHOUT {bare_node['unaccounted']:.1f}s")
    if node["unaccounted"] >= bare_node["unaccounted"]:
        fails.append("adding the prep spans did not reduce unaccounted — the "
                     "spans are not covering real render wall")
    if node["unaccounted"] > 60:
        fails.append(f"prep spans still leave {node['unaccounted']:.0f}s "
                     f"unaccounted on the fixture — the catch-all is not "
                     f"catching")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT RENDER-PREP-ACCOUNTED: FAIL")
        return 1
    print("  NOTE: asserts the WIRING and the arithmetic. Whether prep actually "
          "holds the 490s is answered only by a slow job on real traffic — "
          "read stage_timings.timeline, not this cert.")
    print("  CERT RENDER-PREP-ACCOUNTED: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
