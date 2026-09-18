#!/usr/bin/env python3
"""Every ChatCut call the harness makes is valid against the LIVE schema.

WHY THIS EXISTS. `preview_timeline` was called with `limit: 200` against a
schema whose maximum is 100. It failed `-32602 Invalid arguments`, the harness
could not read its own timeline back, and the review had no window to render —
on a run where the agent had successfully placed items. One call site used 100
and satisfied the schema; the other used 200 and nobody had compared them.

AND THE SWEEP FOUND A SECOND ONE NOBODY HAD HIT: `browse_library` with
`limit: 200` against a maximum of 30. That call had never been exercised, so it
would have failed the first time the sound library was read, in a run that had
already spent its budget getting there.

THE TABLE IS READ FROM THE LIVE TOOL DEFINITIONS, NOT FROM MEMORY OR THE SKILL
DOCS — both mismatches were invisible to a reading of either. `chatcut_schema.json`
records its provenance and the date. When ChatCut changes a bound, this check
goes red against a stale table, which is the correct failure: it means someone
must re-read the definitions rather than guess.
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
SCHEMA = json.load(io.open(os.path.join(HERE, "chatcut_schema.json"),
                           encoding="utf-8"))
FAILS = []


def check(name, ok, why=""):
    print("  %-56s %s" % (name, "ok" if ok else "FAIL"))
    if not ok:
        FAILS.append("%s :: %s" % (name, why))
    return ok


def call_sites(tree):
    """(line, tool, {key: literal-or-None}) for every _mcp_call / call()."""
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = getattr(n.func, "id", "") or getattr(n.func, "attr", "")
        if fn not in ("_mcp_call", "call"):
            continue
        # tool name is the first string arg
        tool = None
        for a in n.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                tool = a.value
                break
        if tool is None:
            continue
        args = {}
        for a in n.args:
            if isinstance(a, ast.Dict):
                for k, v in zip(a.keys, a.values):
                    if isinstance(k, ast.Constant):
                        args[k.value] = (v.value
                                         if isinstance(v, ast.Constant)
                                         else (
                                             [e.value for e in v.elts
                                              if isinstance(e, ast.Constant)]
                                             if isinstance(v, ast.List) else None))
        out.append((n.lineno, tool, args))
    return out


def main():
    print("CHATCUT CALLS MATCH THE SCHEMA")
    print("  table read from: %s" % SCHEMA["_source"][:72] + "...")
    tree = ast.parse(SRC)
    sites = call_sites(tree)

    # FLOOR. A sweep over an empty population passes and asserts nothing —
    # 26 of 27 red proofs in this repo once did exactly that.
    check("the sweep found call sites at all", len(sites) >= 8,
          "found %d — the extractor is probably wrong, and a check over an "
          "empty set passes quietly" % len(sites))
    known = [s for s in sites if s[1] in SCHEMA]
    check("...and some of them are tools we have a schema for",
          len(known) >= 5,
          "only %d of %d sites match a recorded tool; the table is too thin "
          "to be a check" % (len(known), len(sites)))
    print("      %d call site(s), %d against a recorded schema"
          % (len(sites), len(known)))

    bad_key, bad_max, bad_enum, bad_req = [], [], [], []
    for ln, tool, args in known:
        sch = SCHEMA[tool]
        for k, v in args.items():
            if k not in sch["keys"]:
                bad_key.append("%s:%d %s has no %r (additionalProperties is "
                               "false)" % (tool, ln, tool, k))
            if k in sch.get("max", {}) and isinstance(v, int):
                if v > sch["max"][k]:
                    bad_max.append("%s:%d %s=%s exceeds the maximum of %s"
                                   % (tool, ln, k, v, sch["max"][k]))
            if k in sch.get("enum", {}) and v is not None:
                vals = v if isinstance(v, list) else [v]
                for one in vals:
                    if isinstance(one, str) and one not in sch["enum"][k]:
                        bad_enum.append("%s:%d %s=%r is not in the enum"
                                        % (tool, ln, k, one))
        for r in sch.get("required", []):
            if r not in args:
                bad_req.append("%s:%d omits required %r" % (tool, ln, r))

    check("no call passes a key the schema does not accept", not bad_key,
          "; ".join(bad_key))
    check("no numeric argument exceeds its maximum", not bad_max,
          "; ".join(bad_max))
    check("no closed enum is violated", not bad_enum, "; ".join(bad_enum))
    check("no required argument is missing", not bad_req, "; ".join(bad_req))

    # the two that actually bit, pinned by name so a regression is obvious
    lims = [(ln, tool, a.get("limit")) for ln, tool, a in known
            if "limit" in a and isinstance(a.get("limit"), int)]
    for ln, tool, v in lims:
        print("      limit at %s:%d = %s (max %s)"
              % (tool, ln, v, SCHEMA[tool].get("max", {}).get("limit", "-")))

    if FAILS:
        print("\n%d FAILURE(S)" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("\nall legs green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
