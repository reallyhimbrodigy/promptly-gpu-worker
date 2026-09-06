"""Does the API enforce CONDITIONAL requirements in a tool schema?

THE QUESTION, and why it cannot be assumed. The ask is that a `card` ruling with
no card_hero be rejected AT THE API BOUNDARY, before it reaches the harness. That
is only possible if two things are true, and both are empirical:

  1. the API ACCEPTS a tool input_schema carrying if/then (or dependentRequired);
  2. the API REJECTS a tool_use whose arguments violate that conditional.

(1) failing means conditional requirements are unavailable and enforcement must
live in the dispatch. (1) passing and (2) failing is worse than either: the
schema would LOOK like a guarantee and be a suggestion, which is the shape of
every false green in this lane. So this probe reports which of the two happened
rather than a pass/fail.
"""
import json
import modal

app = modal.App("probe-conditional-schema")
image = modal.Image.debian_slim(python_version="3.11").pip_install(["anthropic"])
SECRETS = [modal.Secret.from_name("promptly-secrets")]

# The verdict item, with the conditional the ask requires: naming a family in
# `treatment` makes that family's content field required.
ITEM = {
    "type": "object",
    "properties": {
        "beat": {"type": "integer"},
        "treatment": {"type": "array",
                      "items": {"type": "string",
                                "enum": ["card", "text", "sfx", "zoom", "none"]}},
        "text_content": {"type": "string"},
        "card_hero": {"type": "string"},
        "sfx_name": {"type": "string"},
        "why": {"type": "string"},
    },
    "required": ["beat", "treatment", "why"],
    "allOf": [
        {"if": {"properties": {"treatment": {"contains": {"const": "card"}}}},
         "then": {"required": ["card_hero"]}},
        {"if": {"properties": {"treatment": {"contains": {"const": "sfx"}}}},
         "then": {"required": ["sfx_name"]}},
        {"if": {"properties": {"treatment": {"contains": {"const": "text"}}}},
         "then": {"required": ["text_content"]}},
    ],
}
TOOL = {"name": "rule_all_beats",
        "description": "Rule on every beat in one call.",
        "input_schema": {"type": "object",
                         "properties": {"verdicts": {"type": "array", "items": ITEM}},
                         "required": ["verdicts"]}}


# THE RESTRUCTURE. If conditionals are not enforced, the question becomes
# whether PLAIN `required` on a NESTED object is — because then the fix is
# structural rather than conditional: the ruling for a family IS the object that
# carries its content, so "card without a hero" becomes unsayable rather than
# merely disallowed.
ITEM_NESTED = {
    "type": "object",
    "properties": {
        "beat": {"type": "integer"},
        "why": {"type": "string"},
        "card": {"type": "object",
                 "description": "Include ONLY to rule a card. hero is required.",
                 "properties": {"hero": {"type": "string"},
                                "label": {"type": "string"}},
                 "required": ["hero"]},
        "sfx": {"type": "object",
                "description": "Include ONLY to rule a sound. name is required.",
                "properties": {"name": {"type": "string"}},
                "required": ["name"]},
    },
    "required": ["beat", "why"],
}
TOOL_NESTED = {"name": "rule_all_beats_nested",
               "description": "Rule on every beat in one call.",
               "input_schema": {"type": "object",
                                "properties": {"verdicts": {"type": "array",
                                                            "items": ITEM_NESTED}},
                                "required": ["verdicts"]}}


@app.function(image=image, secrets=SECRETS, timeout=300)
def probe():
    import anthropic
    c = anthropic.Anthropic()
    out = {}

    # ── (1) is the schema even accepted? ───────────────────────────────────
    try:
        r = c.messages.create(
            model="claude-haiku-4-5", max_tokens=700, tools=[TOOL],
            tool_choice={"type": "tool", "name": "rule_all_beats"},
            messages=[{"role": "user", "content":
                       "Rule beat 0 as a CARD. Do NOT include card_hero — omit "
                       "that field entirely. Include why."}])
        out["schema_accepted"] = True
        tu = [b for b in r.content if getattr(b, "type", "") == "tool_use"]
        args = tu[0].input if tu else {}
        out["emitted"] = args
        vs = args.get("verdicts") or []
        # (2) did a violating emission get through?
        bad = [v for v in vs
               if "card" in [str(t).lower() for t in (v.get("treatment") or [])]
               and not str(v.get("card_hero") or "").strip()]
        out["violating_verdicts_returned"] = len(bad)
        out["enforced_at_boundary"] = (len(vs) > 0 and len(bad) == 0)
    except Exception as e:
        out["schema_accepted"] = False
        out["error"] = f"{type(e).__name__}: {str(e)[:400]}"

    # ── (3) is PLAIN nested `required` enforced? ──────────────────────────
    try:
        r2 = c.messages.create(
            model="claude-haiku-4-5", max_tokens=700, tools=[TOOL_NESTED],
            tool_choice={"type": "tool", "name": "rule_all_beats_nested"},
            messages=[{"role": "user", "content":
                       "Rule beat 0 with a card. Do NOT include the hero field "
                       "inside card — omit it entirely. Include why."}])
        tu2 = [b for b in r2.content if getattr(b, "type", "") == "tool_use"]
        a2 = tu2[0].input if tu2 else {}
        out["nested_emitted"] = a2
        v2 = a2.get("verdicts") or []
        bad2 = [v for v in v2
                if isinstance(v.get("card"), dict)
                and not str(v["card"].get("hero") or "").strip()]
        out["nested_violating"] = len(bad2)
        out["nested_enforced"] = (len(v2) > 0 and len(bad2) == 0)
    except Exception as e:
        out["nested_enforced"] = None
        out["nested_error"] = f"{type(e).__name__}: {str(e)[:300]}"

    print(json.dumps(out, indent=2)[:2500])
    return out


@app.local_entrypoint()
def main():
    r = probe.remote()
    print("\n=== VERDICT ===")
    if not r.get("schema_accepted"):
        print("  API REJECTED THE SCHEMA — conditional requirements are not")
        print("  available at the boundary. Enforce in the dispatch.")
        print("  ", r.get("error"))
    elif r.get("enforced_at_boundary"):
        print("  ENFORCED: the API accepted the conditional AND no violating")
        print("  verdict came back even when explicitly asked for one.")
    else:
        print("  ACCEPTED BUT NOT ENFORCED — the schema looks like a guarantee")
        print("  and behaves as a suggestion. This is the false-green shape:")
        print(f"  {r.get('violating_verdicts_returned')} violating verdict(s) returned.")
    print()
    if r.get("nested_enforced"):
        print("  NESTED `required` IS ENFORCED — the restructure works: a card")
        print("  ruling without a hero becomes UNSAYABLE, not merely disallowed.")
    elif r.get("nested_enforced") is False:
        print(f"  NESTED `required` NOT enforced either "
              f"({r.get('nested_violating')} violating). The only boundary that")
        print("  holds is the dispatch.")
    else:
        print("  nested probe errored:", r.get("nested_error"))
