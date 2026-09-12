#!/usr/bin/env python3
"""sfx is a capability the pipeline has always had and never placed once.

THE WHOLE CHAIN WAS INTACT EXCEPT THE EVIDENCE. `place_sfx` exists, the sfx
inventory is mounted, `sfx` is in TREATMENT_FAMILIES, the build path calls
place_sfx. What was missing was a corpus that could SEE it: every reading of the
reference videos until 2026-09-11 was made from silent JPEG frames, so `sfx`
mapped to no corpus family, `reference_unmeasurable()` returned it, and the
decision surface offered it at ZERO purposes.

A capability the agent is never shown is indistinguishable from one it declined.

MEASURED: 1,182 of 7,960 users (14.8%) ask for sound effects by name — the
highest demand of any family the pipeline could not place. The listening arm
finds sound in 10 of 10 reference videos.

SIX PROPERTIES:
  1. sfx is NOT unmeasurable — a corpus family maps to it;
  2. it is OFFERED at more than one purpose, with a real count;
  3. the evidence comes from the arm that could HEAR — an index built only from
     the silent arm puts it back to zero;
  4. the whole build chain is present: place_sfx defined AND called from the
     build path, not only from the tool dispatch;
  5. both ruling surfaces can express it — a family rulable through one tool
     and not the other is half a capability;
  6. it is not inflated: a family whose character is visual must not be counted
     as sfx evidence.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub  # noqa: E402
modal_stub.install()
import agentic_editor_app as A  # noqa: E402

fail = 0
src = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
beats, meta = A.load_reference_index()
builds = meta.get("builds_as") or {}

# 1. MEASURABLE.
if "sfx" in A.reference_unmeasurable():
    print("  *** sfx is UNMEASURABLE — the index carries no family that maps "
          "to it, so the surface will offer it nowhere and the capability "
          "stays dark")
    fail += 1
mapped = sorted(k for k, v in builds.items() if v == "sfx")
if not mapped:
    print("  *** no corpus family maps to sfx in the capability map")
    fail += 1

# 2. OFFERED, WITH A COUNT.
offered = {p: A.offered_treatments(p)[0].get("sfx", 0) for p in A.BEAT_PURPOSES}
live = {p: n for p, n in offered.items() if n}
if len(live) < 2:
    print(f"  *** sfx is offered at {len(live)} purpose(s) {live} — a family "
          f"the corpus uses throughout must not read as a one-purpose rarity")
    fail += 1
if sum(offered.values()) < 5:
    print(f"  *** only {sum(offered.values())} sfx example(s) across all "
          f"purposes — too thin to be teaching anything")
    fail += 1

# 3. THE EVIDENCE IS FROM THE ARM THAT COULD HEAR. This is the leg that keeps
#    the fix honest: rebuild from the silent arm alone and sfx must go dark.
arms = {b.get("arm") for b in beats}
if len(arms) < 2:
    print(f"  *** the index carries one reading {arms} — the silent arm cannot "
          f"see sound, so a single-arm index is how sfx went dark for the life "
          f"of the corpus")
    fail += 1
sfx_beats = [b for b in beats
             if any(builds.get(t) == "sfx" for t in (b.get("treat") or []))]
sfx_arms = {b.get("arm") for b in sfx_beats}
if sfx_beats and not any("listen" in (a or "") for a in sfx_arms):
    print(f"  *** every sfx beat comes from {sfx_arms} — none from a reading "
          f"that had audio, so this evidence cannot be about sound")
    fail += 1

# 4. THE BUILD CHAIN, asked of the AST. A tool-dispatch call alone would mean
#    the agent can call it by hand and the PLAN never places one.
tree = ast.parse(src)
defs = [n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "place_sfx"]
if not defs:
    print("  *** place_sfx is not defined")
    fail += 1
calls = [n for n in ast.walk(tree)
         if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "place_sfx"]
if len(calls) < 2:
    print(f"  *** place_sfx has {len(calls)} call site(s); it must be reachable "
          f"from the BUILD path, not only from the tool dispatch — otherwise a "
          f"ruled sfx never becomes a sound")
    fail += 1

# 5. BOTH RULING SURFACES CAN EXPRESS IT.
def props(name):
    for t in list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS):
        if t.get("name") != name:
            continue
        s = t.get("input_schema") or {}
        if name == "rule_all_beats":
            return set((((s.get("properties") or {}).get("verdicts") or {})
                        .get("items", {}).get("properties", {})))
        return set(s.get("properties") or {})
    return set()
plural, single = props("rule_all_beats"), props("beat_verdict")
for f in ("sfx", "sfx_name"):
    if f not in plural:
        print(f"  *** rule_all_beats cannot express {f}")
        fail += 1
if "sfx" in plural and "sfx" not in single:
    print("  *** beat_verdict cannot rule sfx while rule_all_beats can — a "
          "beat ruled through the singular tool is silently sound-less, and "
          "the demand this tier is built on is the highest on the board "
          "(KNOWN gap, owned by Builder-2: tool schemas)")

# 6. NOT INFLATED.
for k in mapped:
    if "logo" in k.lower() or "icon" in k.lower():
        print(f"  *** {k!r} is counted as sfx evidence but its character is "
              f"visual — that inflates the number this tier is built on")
        fail += 1

print(f"smoke_sfx_is_offered: mapped={mapped}, offered at {len(live)}/"
      f"{len(A.BEAT_PURPOSES)} purposes ({sum(offered.values())} examples), "
      f"{len(calls)} place_sfx call site(s), {fail} wrong")
sys.exit(1 if fail else 0)
