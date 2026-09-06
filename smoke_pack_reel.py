"""SMOKE — pack_reel's two clocks, unit-tested the way remap_words was.

WHY THIS EXISTS. pack_reel's own docstring says it is "pure and unit-tested
rather than inlined". It was pure. It was NOT tested — there was no test of it
anywhere in the lane, so the claim was a comment about work nobody had done.

WHAT IT GETS WRONG SILENTLY. There are two clocks and confusing them produces a
video, not an error:

  REEL time   — where a component sits in the single rendered PNG strip.
  OUTPUT time — where it must appear in the finished edit.

A component that lands two seconds off does not look like a bug, it looks like a
placement decision. Nothing downstream can catch it: the render exits 0, the
composite exits 0, the manifest counts it as placed.

THE MEASUREMENT THIS PROTECTS. Painting the full 58s timeline to get 10
components is 1,740 frames / 169.3s / 128MB — WORSE than ten separate renders
(~161s). Packing the same ten back-to-back is 600 frames / 72.2s / 75MB. The
packing IS the optimisation; break the offsets and the only options are a wrong
video or going back to 2.3x the render time.
"""
import ast
import sys

FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)
_ns = {}
_fn = next((n for n in TREE.body
            if isinstance(n, ast.FunctionDef) and n.name == "pack_reel"), None)
ok(_fn is not None, "pack_reel is not defined at module level")
if _fn:
    exec(compile(ast.Module([_fn], []), "<s>", "exec"), _ns)
    pack = _ns["pack_reel"]

    # ── CONTIGUOUS, and that is the whole point ───────────────────────────
    r = pack([{"t_start": 3.0, "duration_s": 2.0},
              {"t_start": 20.0, "duration_s": 2.0},
              {"t_start": 40.0, "duration_s": 2.0}], 30)
    ok(r["reel_frames"] == 180,
       f"three 2s components packed to {r['reel_frames']} frames, expected 180 "
       f"— the reel is painting timeline, not components")
    ok([s["reel_from_s"] for s in r["segments"]] == [0.0, 2.0, 4.0],
       f"reel starts {[s['reel_from_s'] for s in r['segments']]} are not "
       f"back-to-back — gaps mean wasted frames, overlaps mean a wrong video")
    ok([s["out_at_s"] for s in r["segments"]] == [3.0, 20.0, 40.0],
       "OUTPUT times were altered — the reel clock leaked into the edit clock, "
       "which lands every component in the wrong place and still exits 0")

    # ── VARIABLE DURATIONS: the case a fixed stride gets wrong ────────────
    # i * dur_f silently overlaps or gaps everything after the first component
    # whose length differs, and the render still exits 0.
    r = pack([{"t_start": 1.0, "duration_s": 1.0},
              {"t_start": 5.0, "duration_s": 3.0},
              {"t_start": 9.0, "duration_s": 0.5}], 30)
    ok([s["reel_from_s"] for s in r["segments"]] == [0.0, 1.0, 4.0],
       f"variable-duration packing gave {[s['reel_from_s'] for s in r['segments']]}, "
       f"expected [0.0, 1.0, 4.0] — a fixed stride instead of a cumulative cursor")
    ok(r["reel_frames"] == 135, f"expected 30+90+15=135 frames, got {r['reel_frames']}")
    ok([s["reel_to_s"] for s in r["segments"]] == [1.0, 4.0, 4.5],
       f"segment ENDs {[s['reel_to_s'] for s in r['segments']]} do not follow "
       f"their starts — the composite would cut each component mid-animation")

    # every reel entry's frame window must match its segment, or the composite
    # reads a different slice than the renderer painted
    for i, (e, s) in enumerate(zip(r["reel"], r["segments"])):
        ok(e["fromFrame"] == round(s["reel_from_s"] * 30),
           f"component {i}: reel entry starts at frame {e['fromFrame']} but the "
           f"composite reads from {s['reel_from_s']}s — they must be one number")
        ok(e["durationInFrames"] == round((s["reel_to_s"] - s["reel_from_s"]) * 30),
           f"component {i}: painted {e['durationInFrames']} frames, composite "
           f"reads {(s['reel_to_s'] - s['reel_from_s']) * 30}")

    # ── no component may be zero-length: a 0-frame render is a black hole ─
    r = pack([{"t_start": 2.0, "duration_s": 0.0}], 30)
    ok(r["reel_frames"] >= 1,
       "a 0s component packed to 0 frames — remotion renders nothing and the "
       "composite reads an empty slice")

    # ── author order is preserved; the composite indexes by position ──────
    r = pack([{"t_start": 30.0, "duration_s": 1.0},
              {"t_start": 2.0, "duration_s": 1.0}], 30)
    ok([s["out_at_s"] for s in r["segments"]] == [30.0, 2.0],
       "pack_reel reordered the items — the composite maps segment i to item i, "
       "so reordering silently swaps two components' positions in the edit")
    ok([s["i"] for s in r["segments"]] == [0, 1], "segment indices are not author order")

    # ── fps is honoured, not assumed ─────────────────────────────────────
    r60 = pack([{"t_start": 0.0, "duration_s": 2.0}], 60)
    ok(r60["reel_frames"] == 120,
       f"at 60fps a 2s component packed to {r60['reel_frames']} frames, not 120 "
       f"— a hardcoded 30 would halve every duration on a 60fps render")

# ── AN IDENTICAL REEL IS NOT RE-RENDERED ──────────────────────────────────
# render_components is the most expensive stage in the run (47.96s, 15.1% of
# wall on round 13), and execute_plan is called more than once: round 15's
# talking_head called it THREE times and rendered the reel TWICE, which is the
# difference between its 186.5s and round 14's 104.7s.
#
# Keyed on the CARD CONTENT, not a call count — if the cards genuinely change
# the key changes and it re-renders. That is a cache; a call-count skip would be
# a bug that ships the first reel forever.
ok("_reel_key" in SRC and "reel_reused" in SRC,
   "an identical reel is re-rendered on every execute_plan call — the single "
   "most expensive stage, repeated for no change")
_ki = SRC.index("_ckey = json.dumps(_cards")
ok("sort_keys=True" in SRC[_ki:_ki + 120],
   "the reel key is not order-stable — two identical card sets serialised in "
   "different key order would miss the cache and re-render")
ok('os.path.exists("/work/reel.mov")' in SRC,
   "the reuse path does not confirm the reel artifact still EXISTS — a cached "
   "key with no file composites nothing and reports success")
_ri = SRC.index("led.get(\"_reel_key\") == _ckey")
_ei = SRC.index("rc = render_components(_cards)")
ok(_ri < _ei, "the cache check runs after the render it is meant to avoid")

if FAIL:
    print("FAIL smoke_pack_reel:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_pack_reel — contiguous packing, cumulative cursor under variable "
      "durations, reel/output clocks kept separate, entry and segment agree, "
      "author order preserved, fps honoured")
