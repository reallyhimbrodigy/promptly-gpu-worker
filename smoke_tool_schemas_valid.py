#!/usr/bin/env python3
"""SMOKE — every offered tool schema is legal, and an absence never renders null.

ROUND 69 LOST ALL FIVE ARMS TO ONE `null`, before a single tool ran:

    tools.10.custom.input_schema: JSON schema is invalid. It must match JSON
    Schema draft 2020-12.

`sfx_name` declared `"enum": sorted(SFX_MOMENTS) or None`. The sound catalogue
was read from a CWD-relative path, so it came back empty in the container and
the enum became `null`. The API refuses the WHOLE REQUEST for one malformed
tool, so nothing ran on any fixture: one turn each, $0 of output, five arms.

THE SHAPE IS THE POINT AND IT IS THIS LANE'S OLDEST FAMILY. `or None` was
written as a graceful degradation — `sfx_name_teach()` already returns a named
absence for the description. But the absence was handled where a HUMAN reads
and rendered raw where a MACHINE parses, so a degradation emitted an illegal
value and became a total outage wearing one. An absent `enum` means "any
string". A null `enum` means "no request".

The ledger could only say `model_call_failed`, and every downstream instrument
then reported a true and useless zero: 0 rulings, 0 placements, 0 chars of
reasoning, `unscoped_vacant`. Five arms of instruments measuring a request that
was never accepted.
"""
import json
import sys

import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(what, passed, detail=""):
    if not passed:
        fails.append(what + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if passed else 'FAIL'}] {what}"
          + (f"\n         {detail}" if not passed and detail else ""))


# ── 1. THE SHIPPED TOOL LIST ────────────────────────────────────────────────
try:
    A._assert_tool_schemas_are_valid()
    check("every offered tool schema is legal", True)
except AssertionError as e:
    check("every offered tool schema is legal", False, str(e)[:400])

_tools = list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS)
check("there are tools to check at all — an empty list would pass every leg "
      "below and assert nothing", len(_tools) >= 8, f"{len(_tools)} tools")

# NO null ANYWHERE, checked independently of the cert so this file is not just
# re-running the same walk under a different name.
_nulls = []


def _walk(o, p):
    if isinstance(o, dict):
        for k, v in o.items():
            if v is None:
                _nulls.append(f"{p}.{k}")
            _walk(v, f"{p}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _walk(v, f"{p}[{i}]")


for _t in _tools:
    _walk(_t.get("input_schema") or {}, _t.get("name", "?"))
check("no null anywhere in any tool schema", not _nulls, str(_nulls[:5]))

# ── 2. THE FIELD THAT DID IT, ON BOTH SURFACES ──────────────────────────────
# _sync_verdict_surfaces copies properties from the plural tool to the singular
# one, so a malformed property arrives on BOTH. The cert caught it twice, which
# is the sync working and the blast radius doubling.
for _name in ("rule_all_beats", "beat_verdict"):
    _t = next((x for x in _tools if x.get("name") == _name), None)
    if _t is None:
        check(f"{_name} exists", False)
        continue
    _s = _t["input_schema"]
    _props = (_s["properties"]["verdicts"]["items"]["properties"]
              if _name == "rule_all_beats" else _s["properties"])
    _sn = _props.get("sfx_name") or {}
    check(f"{_name}.sfx_name has no null enum", _sn.get("enum", "absent") is not None)
    check(f"{_name}.sfx_name either omits enum or lists at least one sound",
          "enum" not in _sn or len(_sn["enum"]) >= 1,
          json.dumps(_sn.get("enum"))[:80])

# ── 3. AND THE RULE MUST DISCRIMINATE ───────────────────────────────────────
# Driven by mutating a COPY of the shipped list, so this exercises the cert's
# real walk rather than a hand-built example.
_orig = A.TOOLS


def _with(mutate):
    import copy
    _copy = copy.deepcopy(list(A.TOOLS))
    mutate(_copy)
    try:
        A.TOOLS = _copy
        A._assert_tool_schemas_are_valid()
        return False
    except AssertionError:
        return True
    finally:
        A.TOOLS = _orig


def _first_obj(tools):
    return next(t for t in tools if isinstance(t.get("input_schema"), dict))


check("it fires on a null enum",
      _with(lambda ts: _first_obj(ts)["input_schema"]
            .setdefault("properties", {}).setdefault("x", {}).update(
                {"type": "string", "enum": None})))
check("it fires on an empty enum — an empty choice list is an absence, not a "
      "choice",
      _with(lambda ts: _first_obj(ts)["input_schema"]
            .setdefault("properties", {}).setdefault("x", {}).update(
                {"type": "string", "enum": []})))
check("it fires on a null value anywhere, not only in an enum",
      _with(lambda ts: _first_obj(ts)["input_schema"]
            .setdefault("properties", {}).update({"x": None})))
check("it fires when input_schema is not an object schema",
      _with(lambda ts: _first_obj(ts).update({"input_schema": {"type": "string"}})))

# IT MUST NOT FIRE ON A PROPERTY *NAMED* LIKE A KEYWORD. This check caught
# itself here the first time it ran: render_components declares a property
# called `type` whose value is a schema, and a walk that reads every key named
# "type" as the JSON Schema keyword reported a correct tool as malformed.
check("it does NOT fire on a property named `type` — a property NAME is not a "
      "keyword, and this check reported a correct tool as broken until it "
      "learned the difference",
      not _with(lambda ts: _first_obj(ts)["input_schema"]
                .setdefault("properties", {}).update(
                    {"type": {"type": "string", "description": "a field called type"}})))
check("and not on a property named `enum`",
      not _with(lambda ts: _first_obj(ts)["input_schema"]
                .setdefault("properties", {}).update(
                    {"enum": {"type": "string", "description": "a field called enum"}})))

if fails:
    print("TOOL-SCHEMAS-VALID: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("TOOL-SCHEMAS-VALID: PASS — %d tools, no nulls, no empty enums, and the "
      "rule tells a property NAME from a keyword" % len(_tools))
