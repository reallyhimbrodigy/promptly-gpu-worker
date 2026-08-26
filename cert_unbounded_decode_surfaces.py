#!/usr/bin/env python3
"""cert_unbounded_decode_surfaces.py — EVERY DECODE SURFACE IS BOUNDED SOMEWHERE.

WHAT THIS PROTECTS. Lever 3 (2026-07-11) capped 42 free-text strings and made an
in-string repetition loop decode-impossible. It did not end the runaway — it
moved it. Enumerated on the live schema 2026-08-19, exactly four surfaces
survived Lever 3 unbounded, and the observed spirals landed on them:

    _MotionGraphic.props            free-form object   uncappable by construction
    _EmphasisMotionGraphic.props    free-form object   uncappable by construction
    PostCutPlan.caption_keywords    list, itemMax 120, no bound on ITEM COUNT
    _GenSceneSubject.ref_image_keys list, itemMax 200, no bound on ITEM COUNT

Verbatim from a shape-abort tail: 4,096 chars of "#newlaunch #exclusiveaccess
#presale #booknow #downpayment …". Every item was already inside its 120-char
cap; the spiral simply ran on the axis nobody had capped.

THE THREE CLAUSES:

  1  NO NEW UNBOUNDED SURFACE. Every string in the decode schema has a
     maxLength, or is an enum, or is on the documented exception list. Every
     string-list has an entry in _LIST_ITEM_CAPS. A new uncapped field fails
     here rather than in a spiral six weeks later.

  2  THE props ASYMMETRY HOLDS. props is REQUIRED in the schema sent to Vertex
     (so constrained decoding cannot close a motion graphic without it) and NOT
     required on the pydantic model (so a response lacking it still PARSES
     instead of failing the whole plan). Both halves are load-bearing: drop the
     first and the empty-props drop returns; add the second and one missing
     field rejects a whole edit.

  3  maxItems IS NEVER SENT. Vertex's passthrough rejects maxItems with 400
     INVALID_ARGUMENT — a total outage of the editorial path, since every job
     takes this call. Anyone "fixing" clause 1 by declaring maxItems on the
     model would ship that outage. The cap belongs at the parse edge.

  4  THE CAP ACTUALLY TRUNCATES. Clause 1 only proves a number is declared;
     this drives the real _enforce_string_caps with an over-long list and
     asserts the list came back at the cap.

    python3 cert_unbounded_decode_surfaces.py
"""
import os
import sys

os.environ.setdefault("APP_URL", "")

# Strings with no maxLength that are NOT runaway surfaces, each with its reason.
# An entry here is a claim someone can check, not a silencer.
_STRING_EXCEPTIONS = {
    # (none today — every non-enum string in the schema carries a cap)
}


def _is_enum(pv, defs):
    if not isinstance(pv, dict):
        return False
    if pv.get("enum") or pv.get("const"):
        return True
    ref = pv.get("$ref") or ""
    if ref.startswith("#/$defs/"):
        return bool((defs.get(ref.split("/")[-1]) or {}).get("enum"))
    for key in ("anyOf", "allOf", "oneOf"):
        for sub in pv.get(key) or []:
            if _is_enum(sub, defs):
                return True
    return False


def main():
    import handler as H

    schema = H._post_cuts_response_schema()
    defs = schema.get("$defs") or {}
    fails = []

    # ── 1: no new unbounded surface ─────────────────────────────────────────
    unbounded_str, unbounded_list, free_objs = [], [], []
    for owner, d in list(defs.items()) + [("PostCutPlan", schema)]:
        for pn, pv in (d.get("properties") or {}).items():
            if not isinstance(pv, dict) or _is_enum(pv, defs):
                continue
            t = pv.get("type")
            if t == "string" and pv.get("maxLength") is None:
                if f"{owner}.{pn}" not in _STRING_EXCEPTIONS:
                    unbounded_str.append(f"{owner}.{pn}")
            elif t == "array" and (pv.get("items") or {}).get("type") == "string":
                if pn not in H._LIST_ITEM_CAPS:
                    unbounded_list.append(f"{owner}.{pn}")
            elif t == "object" and pv.get("additionalProperties") is True:
                free_objs.append(f"{owner}.{pn}")
    print(f"  [1] uncapped strings : {unbounded_str or 'none'}")
    print(f"      uncapped lists   : {unbounded_list or 'none'}")
    print(f"      free-form objects: {free_objs}  (uncappable; bounded by the "
          f"in-stream shape abort)")
    if unbounded_str:
        fails.append(f"uncapped string(s): {unbounded_str}")
    if unbounded_list:
        fails.append(f"string-list(s) with no _LIST_ITEM_CAPS entry: {unbounded_list}")

    # ── 2: the props asymmetry ──────────────────────────────────────────────
    for mg in ("_MotionGraphic", "_EmphasisMotionGraphic"):
        sent_req = set((defs.get(mg) or {}).get("required") or [])
        if "props" not in sent_req:
            fails.append(f"{mg}.props is NOT required in the schema sent to Vertex "
                         f"— the empty-props drop returns")
        print(f"  [2] {mg:24} decode-required props: {'props' in sent_req}")
    parse_req = set(H.PostCutPlan.model_json_schema()["$defs"]["_MotionGraphic"]
                    .get("required") or [])
    if "props" in parse_req:
        fails.append("props is required on the PYDANTIC model — a response "
                     "missing it would fail the WHOLE plan instead of dropping "
                     "one component (K7)")
    print(f"      pydantic parse-required props: {'props' in parse_req}  "
          f"(must be False)")

    # ── 3: maxItems is never sent ───────────────────────────────────────────
    import json as _json
    blob = _json.dumps(schema)
    n_maxitems = blob.count('"maxItems"')
    print(f"  [3] maxItems occurrences in the sent schema: {n_maxitems}  "
          f"(must be 0 — Vertex 400s on it)")
    if n_maxitems:
        fails.append(f"maxItems appears {n_maxitems}x in the schema sent to Vertex "
                     f"— that is a 400 INVALID_ARGUMENT on every job")

    # ── 4: the cap actually truncates ───────────────────────────────────────
    for field, cap in H._LIST_ITEM_CAPS.items():
        parsed = {field: [f"#tag{i}" for i in range(cap + 37)]}
        H._enforce_string_caps(parsed, schema, "cert")
        got = len(parsed[field])
        print(f"  [4] {field:18} {cap + 37} items -> {got}  (cap {cap})")
        if got != cap:
            fails.append(f"{field} was not truncated to its cap: {got} != {cap}")
    # and a legit-sized list is untouched
    for field, cap in H._LIST_ITEM_CAPS.items():
        parsed = {field: [f"#tag{i}" for i in range(cap)]}
        H._enforce_string_caps(parsed, schema, "cert")
        if len(parsed[field]) != cap:
            fails.append(f"{field} at exactly the cap was clipped — the bound "
                         f"must never touch a legal plan")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT UNBOUNDED-DECODE: FAIL")
        return 1
    print("  CERT UNBOUNDED-DECODE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
