#!/usr/bin/env python3
"""Every step the executor emits must be a step the manifest can represent.

THE DEFECT THIS PINS, found by Builder-2 running the judgment on rounds 51-53:
execute_plan appends {"step": "cutaway", ...} and the placement loop looks the
step up in _TYPE, which lists text/zoom/sfx/card/transition and never learned
the word. So a cutaway was ruled, planned, BUILT — built["cutaway"]=1 on three
fixtures — and then silently skipped by a lookup table. Zero placements with
family=cutaway across 540 painted frames of three rounds. "Cutaway ruled zero"
was partly the instrument, and every placements-per-beat number computed on
those rounds excluded cutaway by construction.

TWO CHECKS, because two things were true and nobody subtracted them:
  1. STATIC, on the AST: the set of step names execute_plan emits must be a
     subset of _TYPE's keys. Catches the NEXT family before it ships.
  2. IDENTITY, on the ledgers: built[family] == placements with that family,
     for every family, every result on disk. The ruled/planned/built line
     printed three numbers for months; this is the subtraction.
"""
import ast
import glob
import json
import sys

# A STEP CAN BE REPRESENTED SOMEWHERE OTHER THAN placements — but only on
# purpose, named, and checked. `cut` is the keep/remove decision and lives in
# keep_spans (output-time <-> source-time is computed FROM it; making every
# cut a placement would double-represent it and pollute placements-per-beat).
# So the exclusion is an allowlist that names the field carrying it, and the
# ledger check verifies that field is non-empty whenever the step was built.
# An exclusion with no named carrier is an omission, and fails.
REPRESENTED_ELSEWHERE = {"cut": "keep_spans"}

src = open("agentic_editor_app.py").read()
tree = ast.parse(src)

fail = 0

# ── 1. STATIC ─────────────────────────────────────────────────────────────
type_keys = None
emitted = set()
for n in ast.walk(tree):
    if (isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_TYPE" for t in n.targets)
            and isinstance(n.value, ast.Dict)):
        ks = [k.value for k in n.value.keys if isinstance(k, ast.Constant)]
        if {"text", "zoom", "sfx"} <= set(ks):        # the placement table, not another _TYPE
            type_keys = set(ks)
    # steps.append({"step": "<literal>", ...})
    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "append"
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "steps"
            and n.args and isinstance(n.args[0], ast.Dict)):
        d = n.args[0]
        for k, v in zip(d.keys, d.values):
            if (isinstance(k, ast.Constant) and k.value == "step"
                    and isinstance(v, ast.Constant)):
                emitted.add(v.value)

if type_keys is None:
    print("  *** the placement _TYPE table was not found — nothing can be checked")
    sys.exit(1)
if not emitted:
    print("  *** no steps.append({'step': <literal>}) found — the emitter moved")
    sys.exit(1)
missing = sorted(emitted - type_keys - set(REPRESENTED_ELSEWHERE))
for m in missing:
    print(f"  *** step {m!r} is EMITTED by execute_plan but ABSENT from _TYPE — "
          f"it is built and then dropped before the manifest")
    fail += 1
print(f"  static: emitted {sorted(emitted)}  _TYPE {sorted(type_keys)}  "
      f"elsewhere {REPRESENTED_ELSEWHERE}  missing {missing or 'none'}")

# ── 2. IDENTITY, every ledger that can say which code produced it ─────────
# Ledgers from before the fix were produced by the code with the defect, and
# would fail this forever. They carry NO provenance (no commit, no fingerprint
# — a gap in its own right), so the fix also writes led["app_sha"], and this
# check runs only on ledgers that carry it. The legacy ones are COUNTED and
# NAMED as skipped, never silently passed.
n_led = n_legacy = 0
for f in sorted(glob.glob("/tmp/fixtures/round5*/*.result.json")):
    try:
        led = json.load(open(f))
        led = led.get("ledger") or led
    except Exception:                                             # noqa: BLE001
        continue
    built = ((led.get("execute_plan") or {}).get("built")) or {}
    if not built:
        continue
    if not led.get("app_sha"):
        n_legacy += 1
        continue
    n_led += 1
    tag = f"{f.split('/')[-2]}/{f.split('/')[-1][:-12]}"
    fams = {}
    for p in (led.get("placements") or []):
        fams[p.get("family")] = fams.get(p.get("family"), 0) + 1
    for fam, nb in built.items():
        if not nb:
            continue
        if fam in REPRESENTED_ELSEWHERE:
            carrier = REPRESENTED_ELSEWHERE[fam]
            if not led.get(carrier):
                print(f"  *** {tag}: built[{fam}]={nb} and its carrier "
                      f"{carrier!r} is empty — represented nowhere")
                fail += 1
            continue
        if fam in ("text", "card"):
            continue        # batched: one build burns many; identity is per-item there
        npl = fams.get(fam, 0)
        if npl != nb:
            print(f"  *** {tag}: built[{fam}]={nb} but placements[{fam}]={npl} — "
                  f"built and then lost before the manifest")
            fail += 1
print(f"  identity: {n_led} ledgers checked, {n_legacy} legacy ledgers SKIPPED "
      f"(no app_sha — produced before provenance existed)")
if n_led == 0 and n_legacy:
    print("  (identity NOT YET EXERCISED on any post-fix ledger — the next round "
          "is the first one that can fail it)")

print(f"smoke_every_step_becomes_a_placement: {fail} wrong")
sys.exit(1 if fail else 0)
