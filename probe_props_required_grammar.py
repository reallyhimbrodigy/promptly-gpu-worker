#!/usr/bin/env python3
"""DOES VERTEX COMPILE A CONSTRAINED GRAMMAR WITH props REQUIRED?

THE PRECEDENT THAT MAKES THIS A REAL QUESTION (handler.py, the zoom-claim
anyOf): six item-level emphasis variants hit a Vertex constrained-decoding
grammar ceiling on the full PostCutPlan schema — 400 INVALID_ARGUMENT — and
STRIPPING motion_graphic (the free-form props Dict) from the variants un-tipped
it. The props object is already the grammar's known pressure point, so marking
it REQUIRED is exactly the kind of change that can 400 the whole plan call.

A 400 here would be a total outage of the editorial path, not a degradation:
every job takes this call. So it gets checked before it ships, on the REAL
schema (_post_cuts_response_schema(), zoom-claim anyOf and diets included), not
on a toy model.

MINIMAL CALL. Tiny prompt, tiny output cap: the grammar is compiled and rejected
(or not) at request time, so a 400 costs nothing and a success costs ~$0.01.
The probe reports which of the two schemas — with and without props required —
compiles, so a failure is attributable rather than ambiguous.

    modal run probe_props_required_grammar.py
"""
import json
import os
import sys

sys.path.insert(0, "/")
import modal, modal_app                                            # noqa: E402

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("probe-props-required-grammar", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"),
           modal.Secret.from_name("gemini-vertex"),
           modal.Secret.from_name("promptly-lang-flags")]


@app.function(secrets=SECRETS, cpu=2.0, memory=4096, timeout=900)
def run() -> dict:
    from build_lane import mark_build_lane
    mark_build_lane("probe_props_required_grammar.py")
    os.environ["APP_URL"] = ""
    sys.path.insert(0, "/")
    import handler as H
    from google.genai import types as genai_types

    client = H._get_genai_client()
    schema_req = H._post_cuts_response_schema()

    # The control: the SAME schema with props required removed again. If both
    # fail, the probe is broken or the path is down — not a verdict on props.
    schema_opt = json.loads(json.dumps(schema_req))
    for _k in ("_MotionGraphic", "_EmphasisMotionGraphic"):
        _d = schema_opt.get("$defs", {}).get(_k) or {}
        _d["required"] = [r for r in (_d.get("required") or []) if r != "props"]

    out = {}
    for label, schema in (("props_OPTIONAL_control", schema_opt),
                          ("props_REQUIRED", schema_req)):
        req = set(schema["$defs"]["_MotionGraphic"].get("required") or [])
        try:
            r = client.models.generate_content(
                model=H.GEMINI_EDITORIAL_MODEL,
                contents=["Return the minimal valid object for this schema. "
                          "One motion graphic, type StatCard, props {\"value\": 1}."],
                config=genai_types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=900,
                    response_mime_type="application/json",
                    response_json_schema=schema,
                ),
            )
            txt = (getattr(r, "text", "") or "")
            out[label] = {
                "compiled": True,
                "props_in_required": "props" in req,
                "chars": len(txt),
                "head": txt[:220],
            }
        except Exception as e:
            out[label] = {
                "compiled": False,
                "props_in_required": "props" in req,
                "error": f"{type(e).__name__}: {str(e)[:400]}",
            }
    return out


@app.local_entrypoint()
def main():
    r = run.remote()
    print("\n  ════ VERTEX GRAMMAR COMPILE — props required ════")
    for k, v in r.items():
        print(f"\n  {k}   props_in_required={v.get('props_in_required')}")
        print(f"    compiled: {v.get('compiled')}")
        if v.get("compiled"):
            print(f"    returned {v.get('chars')} chars: {v.get('head')}")
        else:
            print(f"    ERROR: {v.get('error')}")
    ctl = r.get("props_OPTIONAL_control", {}).get("compiled")
    req = r.get("props_REQUIRED", {}).get("compiled")
    print("\n  ──────────────────────────────────────────────")
    if not ctl:
        print("  NO VERDICT — the control failed too. The path or probe is broken, "
              "not the props change.")
    elif req:
        print("  PASS — the grammar compiles with props REQUIRED. Safe to ship.")
    else:
        print("  FAIL — props required 400s the grammar. DO NOT SHIP; the "
              "empty-props fix must be code-side instead.")
