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
# EXEC WHAT IT DEPENDS ON, not just the function. Isolating pack_reel alone hid
# a real dependency: it calls _require_mg_type, and running it in an empty
# namespace raised NameError — a harness failure that reads exactly like a
# defect in the function under test.
_deps = ("_require_mg_type", "pack_reel")
_fns = [n for n in TREE.body
        if isinstance(n, ast.FunctionDef) and n.name in _deps]
ok({f.name for f in _fns} == set(_deps),
   f"missing at module level: {sorted(set(_deps) - {f.name for f in _fns})}")
_fn = next((f for f in _fns if f.name == "pack_reel"), None)
if len(_fns) == len(_deps):
    exec(compile(ast.Module(_fns, []), "<s>", "exec"), _ns)
    pack = _ns["pack_reel"]

    # ── NO SILENT DEFAULT ─────────────────────────────────────────────────
    # An untyped item used to become a StatCard here, so a caller bug arrived
    # as a rendered StatCard nobody chose and reported as chosen.
    try:
        pack([{"t_start": 1.0, "duration_s": 2.0}])
        FAIL.append("an item with no `type` still defaults to StatCard — a "
                    "component nobody chose reaches the video and reports as "
                    "chosen")
    except ValueError:
        pass

    # ── CONTIGUOUS, and that is the whole point ───────────────────────────
    r = pack([{"t_start": 3.0, "duration_s": 2.0, "type": "StatCard"},
              {"t_start": 20.0, "duration_s": 2.0, "type": "StatCard"},
              {"t_start": 40.0, "duration_s": 2.0, "type": "StatCard"}], 30)
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
    r = pack([{"t_start": 1.0, "duration_s": 1.0, "type": "StatCard"},
              {"t_start": 5.0, "duration_s": 3.0, "type": "StatCard"},
              {"t_start": 9.0, "duration_s": 0.5, "type": "StatCard"}], 30)
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
    r = pack([{"t_start": 2.0, "duration_s": 0.0, "type": "StatCard"}], 30)
    ok(r["reel_frames"] >= 1,
       "a 0s component packed to 0 frames — remotion renders nothing and the "
       "composite reads an empty slice")

    # ── author order is preserved; the composite indexes by position ──────
    r = pack([{"t_start": 30.0, "duration_s": 1.0, "type": "StatCard"},
              {"t_start": 2.0, "duration_s": 1.0, "type": "StatCard"}], 30)
    ok([s["out_at_s"] for s in r["segments"]] == [30.0, 2.0],
       "pack_reel reordered the items — the composite maps segment i to item i, "
       "so reordering silently swaps two components' positions in the edit")
    ok([s["i"] for s in r["segments"]] == [0, 1], "segment indices are not author order")

    # ── fps is honoured, not assumed ─────────────────────────────────────
    r60 = pack([{"t_start": 0.0, "duration_s": 2.0, "type": "StatCard"}], 60)
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

# ── THE REMAP ANNOTATES, IT DOES NOT RECONSTRUCT ───────────────────────────
# A peer lost a run to this exact shape: their ASR ingest measured per-word
# confidence correctly (85 words, median 0.999) and the output-clock remap
# REBUILT each word as {w, s, e}, dropping the field. Their caption gate then
# read no confidence, returned ABSENT, and refused captions on the clearest
# speech in the corpus. Third copy of one shape on their lane; mine had the
# same two sites plus an ingest that never captured the field at all.
#
# Nothing on this lane reads confidence, which is what made it a MERGE hazard
# rather than a bug: their gate merges in, my whitelist survives, and the gate
# refuses captions on every run. So the property is not "confidence is
# carried" — it is that the remap moves the CLOCK and preserves everything
# else, whatever the ingest attached and whoever reads it later.
_w_in = [{"w": "hello", "s": 0.0, "e": 0.5, "conf": 0.999, "spk": 1},
         {"w": "world", "s": 2.0, "e": 2.4, "conf": 0.95, "spk": 1}]
# LOADED THE WAY THIS FILE LOADS EVERYTHING ELSE — by AST, not by import, so
# the check drives the shipped source without the module needing to import.
_rm_node = next((_n for _n in TREE.body
                 if isinstance(_n, ast.FunctionDef) and _n.name == "remap_words"),
                None)
ok(_rm_node is not None, "remap_words is not at module level any more")
_rm_ns = {}
if _rm_node is not None:
    exec(compile(ast.Module([_rm_node], []), "<s>", "exec"), _rm_ns)
_remap = _rm_ns.get("remap_words", lambda *_a, **_k: [])
_w_out = _remap([[0.0, 1.0], [2.0, 3.0]], _w_in)
ok(len(_w_out) == 2, f"remap dropped words: {_w_out}")
ok(all("conf" in _k and "spk" in _k for _k in _w_out),
   f"the remap RECONSTRUCTED its input and dropped fields: {_w_out}")
ok([round(_k["s"], 3) for _k in _w_out] == [0.0, 1.0],
   f"the remap stopped moving the clock, which is its actual job: {_w_out}")
# .get(), NOT [] — indexing raises when the key is gone, and the traceback
# pre-empts the clean failure above it: the harness then reports red for a
# CRASH rather than for the property, which is red-for-the-wrong-reason in the
# leg written to catch a dropped field.
ok(len(_w_out) > 1 and _w_out[1].get("conf") == 0.95,
   "a preserved field must keep its VALUE, not merely its key")

if FAIL:
    print("FAIL smoke_pack_reel:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_pack_reel — contiguous packing, cumulative cursor under variable "
      "durations, reel/output clocks kept separate, entry and segment agree, "
      "author order preserved, fps honoured")
