#!/usr/bin/env python3
"""PROMPT V2 IS WIRED, AND CANNOT BE ARMED INTO A WORSE EDIT. `[RULE-1]`

Arm B of the pre-registered A/B swaps a 111-line doctrine for the ~2,000-line
one and REUSES this call's catalog verbatim. Four ways that wiring can be wrong,
each of which would produce a plausible-looking number:

  1. THE CATALOG SLICE SILENTLY MISSES. If the section heading it cuts on ever
     moves, the slice returns -1 and a naive implementation would send a
     catalog-less prompt — the model would be asked for components nobody named,
     and the A/B would read it as the doctrine failing. Must raise, not degrade.

  2. ARM A STOPS BEING PRODUCTION. The whole comparison rests on arm A being
     byte-identical to what ships. If the v2 branch leaks into the default path,
     the control is contaminated and nothing measured means anything.

  3. THE SCHEMA DRIFTS FROM THE MODEL. The response schema is inlined (pydantic
     emits $defs/$ref that this surface does not reliably accept), so it can
     silently fall out of step with BeatMajorPlan. Both directions are asserted.

  4. THE SECRET FLAG ARMS IT ON LIVE TRAFFIC. This is the one that costs users.
     BeatMajorPlan can express component placements and four globals — and
     NOTHING else. No cut_refinements, emphasis_moments, text_overlays,
     broll_clips, caption_keywords, caption_position_changes or thumbnail, while
     the v2 doctrine's own steps tell the model to cut for pace, vary the texture
     and land the payoff with sound and zoom. A job run this way returns an
     MG-only plan: no zooms, no b-roll, no sound, no caption keywords. So
     PROMPTLY_PROMPT_V2 alone must NOT arm it — only the per-job harness override.

Run: python3 cert_prompt_v2_wiring.py
"""
import ast
import inspect
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  [PASS] {name}")
    else:
        FAILS.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} — {detail}")


def main():
    src = open(os.path.join(HERE, "handler.py")).read()

    # ── 1. the catalog slice RAISES when the marker moves ────────────────────
    v2_block = src[src.find("# ── PROMPT V2 (DARK"):]
    v2_block = v2_block[:v2_block.find("# ── UNIFIED CORE")]
    check("the v2 block exists in generate_edit_gemini", bool(v2_block.strip()),
          "no PROMPT V2 block found")
    mark = re.search(r'_CATALOG_MARK\s*=\s*"([^"]+)"', v2_block)
    check("the catalog marker is declared", bool(mark), "no _CATALOG_MARK")
    if mark:
        check("the marker actually occurs in the built prompt",
              f'{mark.group(1)}' in src,
              f"{mark.group(1)!r} is not present in handler.py at all — the slice "
              f"would return -1 on every job")
    # ── PARSED, NOT GREPPED ──────────────────────────────────────────────────
    # The first version of these three was substring-based and every one of them
    # was VACUOUS: a mutation that APPENDS to a line still contains the original
    # substring, so `_v2_on = bool(x) or v2_enabled()` matched a check looking
    # for `_v2_on = bool(x)`. Three RED mutations passed GREEN — including the
    # one that arms this on live traffic. Ask the syntax tree what the code IS.
    _tree = ast.parse(src)
    _gen = next((n for n in ast.walk(_tree) if isinstance(n, ast.FunctionDef)
                 and n.name == "generate_edit_gemini"), None)
    check("generate_edit_gemini is parseable", _gen is not None, "not found")

    _assigns = [n for n in ast.walk(_gen) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_v2_on" for t in n.targets)]
    check("_v2_on is assigned exactly once", len(_assigns) == 1,
          f"{len(_assigns)} assignments — a second one can re-arm it")
    if len(_assigns) == 1:
        _rhs = _assigns[0].value
        _harness_only = (isinstance(_rhs, ast.Call)
                         and getattr(_rhs.func, "id", None) == "bool"
                         and len(_rhs.args) == 1
                         and isinstance(_rhs.args[0], ast.Name)
                         and _rhs.args[0].id == "prompt_v2_override")
        check("the secret flag ALONE does not arm it (harness-only)", _harness_only,
              f"_v2_on must be EXACTLY bool(prompt_v2_override) — anything wider "
              f"(an `or v2_enabled()`) ships MG-only plans to users. Got: "
              f"{ast.dump(_rhs)[:140]}")

    _guards = [n for n in ast.walk(_gen) if isinstance(n, ast.If)
               and isinstance(n.test, ast.Compare)
               and isinstance(n.test.left, ast.Name) and n.test.left.id == "_cut"
               and any(isinstance(b, ast.Raise) for b in ast.walk(n))]
    check("a missing marker RAISES rather than sending a catalog-less prompt",
          bool(_guards),
          "the `if _cut < 0:` branch must RAISE; a silent -1 slices the WHOLE "
          "prompt away and the A/B reads it as the doctrine failing")

    check("a set-but-refused secret says so out loud",
          "refused on this path" in v2_block,
          "an ignored flag must explain itself or it reads as a broken deploy")
    _armed = [n for n in ast.walk(_gen) if isinstance(n, ast.If)
              and isinstance(n.test, ast.Name) and n.test.id == "_v2_on"
              and "build_v2_system_instruction" in ast.dump(n)]
    check("the v2 prompt is built ONLY inside `if _v2_on:`", bool(_armed),
          "the v2 system instruction must be unreachable unless armed")

    # ── 3. the inlined schema matches BeatMajorPlan, both directions ─────────
    import prompt_v2_schema as pv2s
    model_fields = set(pv2s.BeatMajorPlan.model_fields.keys())
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_v2_response_schema"), None)
    check("_v2_response_schema exists", fn is not None, "not defined")
    if fn is not None:
        schema_src = ast.get_source_segment(src, fn) or ""
        ns = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "<cert>", "exec"), ns)
        schema = ns["_v2_response_schema"]()
        schema_fields = set(schema.get("properties", {}).keys())
        check("every BeatMajorPlan field is in the wire schema",
              model_fields <= schema_fields,
              f"missing from the schema: {sorted(model_fields - schema_fields)}")
        check("the wire schema invents no field the model lacks",
              schema_fields <= model_fields,
              f"not on BeatMajorPlan: {sorted(schema_fields - model_fields)}")
        beat = (schema["properties"]["beats"]["items"]["properties"])
        check("beats are anchored on word_index, never a float second",
              beat.get("word_index", {}).get("type") == "integer"
              and not any(k in beat for k in ("start_s", "time_s", "at_s")),
              f"beat keys: {sorted(beat)} — a float clock here is a SECOND clock")
        # PROPERTY, NOT LOCATION. The first version of this grepped the
        # function's SOURCE — which failed on its own docstring, because the
        # docstring explains what $defs and $ref are. Ask the built object.
        import json as _json
        _wire = _json.dumps(schema)
        check("the schema carries no $ref/$defs this surface may reject",
              '"$ref"' not in _wire and '"$defs"' not in _wire,
              f"references must be inlined; found in the emitted schema: {_wire[:160]}")
        # And prove the pydantic route WOULD have tripped it, so the check is
        # not vacuous — this is the exact reason the schema is written by hand.
        _pyd = _json.dumps(pv2s.BeatMajorPlan.model_json_schema())
        check("the negative control holds: model_json_schema DOES emit $defs",
              '"$defs"' in _pyd or '"$ref"' in _pyd,
              "pydantic no longer emits references — the hand-written schema may "
              "no longer be necessary; re-check before keeping the duplication")

    # ── 4. the flatten runs BEFORE the downstream guards ────────────────────
    call_fn = src[src.find("def _call_gemini_post_cuts"):]
    call_fn = call_fn[:call_fn.find("\ndef ", 10)]
    _cfn = next((n for n in ast.walk(_tree) if isinstance(n, ast.FunctionDef)
                 and n.name == "_call_gemini_post_cuts"), None)
    check("_call_gemini_post_cuts is parseable", _cfn is not None, "not found")
    # GUARDED BY `if v2:`, not merely PRESENT. Disabling the branch (`if False:`)
    # left the old substring check green while arm B silently returned a raw beat
    # plan that no downstream guard understands.
    _flat_ifs = [n for n in ast.walk(_cfn) if isinstance(n, ast.If)
                 and isinstance(n.test, ast.Name) and n.test.id == "v2"
                 and "flatten_beats" in ast.dump(n)]
    check("the flatten is reachable — guarded by `if v2:`", bool(_flat_ifs),
          "flatten_beats must sit under `if v2:`; a disabled branch means arm B "
          "returns beats[] that nothing downstream can read")
    _caps = [n for n in ast.walk(_cfn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "_enforce_string_caps"]
    check("flatten_beats runs before _enforce_string_caps",
          bool(_flat_ifs) and bool(_caps)
          and _flat_ifs[0].lineno < min(c.lineno for c in _caps),
          "the beat plan must become component-major BEFORE the caps and the "
          "strict validation, or arm B skips every downstream invariant")
    check("dropped placements go to the component ledger as dropped BY US",
          "_ledger_requested, _ledger_dropped" in call_fn,
          "the ledger pair must be passed or a transform drop reads as a model "
          "decline — the exact distinction the ledger exists to make")
    check("v2 is a parameter, defaulting OFF",
          "n_words=None, v2=False" in call_fn,
          "the default must be arm A")

    # ── 5. the three modules are mounted into the image ─────────────────────
    ma = open(os.path.join(HERE, "modal_app.py")).read()
    for mod in ("prompt_v2_editor", "prompt_v2_schema", "prompt_v2_exemplars"):
        check(f"{mod} is baked into the worker image",
              f'"{mod}.py"' in ma,
              "a deferred import of an unmounted module dies inside its fail-safe")

    # ── 6. THE HONEST SCOPE. Named here so it cannot be forgotten. ──────────
    # If someone extends BeatMajorPlan to carry the other families, this check
    # is what tells them the refusal above can be revisited.
    expressible = set(pv2s.BeatMajorPlan.model_fields.keys())
    for family in ("cut_refinements", "emphasis_moments", "text_overlays",
                   "broll_clips", "caption_keywords"):
        if family in expressible:
            FAILS.append(
                f"{family} is now expressible in BeatMajorPlan — the live-path "
                f"refusal in handler was written because it was NOT. Re-read it.")
    print("  [NOTE] BeatMajorPlan expresses component placements + "
          f"{sorted(expressible - {'beats'})} and nothing else; the live-path "
          f"refusal stands until that changes.")

    print(f"\nCERT PROMPT-V2 WIRING: {'FAIL' if FAILS else 'PASS'}")
    for f in FAILS:
        print(f"  - {f}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
