#!/usr/bin/env python3
"""THE COMPONENT-COMPLETENESS GATE — offline, $0, no network, no Modal, no Gemini.

WHY THIS EXISTS [Rule 1, §4.8]. "Built but unrequestable" has now shipped SEVEN
times in this campaign. Every instance looked finished from the inside: a module
written, image-mounted, imported, called, cert-green, and carrying a liveness
counter — and still incapable of ever producing a pixel, because the editorial
model was never told the thing existed and its response schema had no field the
model could put it in. A component the model cannot NAME is a component the
model cannot ASK FOR, and a component nobody asks for renders exactly zero times
no matter how green its own cert is.

So this gate does not test any component's behaviour. It tests the CHAIN:

    PRODUCER  ->  REQUESTABLE (response schema)  ->  TAUGHT (prompt/guidance)

and fails if any producer is missing either link. cert_brand_components.py
proves the name-plate looks right; THIS proves it can be asked for at all.
Those are different questions and the second one is the one that keeps being
answered wrong.

THE AUTHORITATIVE PRODUCER LIST IS DERIVED, NEVER TYPED HERE. A hand-maintained
list of components is the same defect wearing a different hat — it goes stale
the first time someone adds a component and forgets the list, which is precisely
the failure being gated. Two derivations, both read from the code that actually
runs:

  1. NAMED COMPONENTS — the renderer's own dispatch tables in
     src/remotion/src/PromptlyRender.tsx (CAPTION_MAP, TRANSITION_MAP, ZOOM_MAP,
     MG_MAP). If a name is a key in one of those maps, the renderer can produce
     it; if it is not, the renderer physically cannot, whatever else exports it.

  2. SPEC-BUILT COMPONENTS — the `build_*` producers in brand_components.py
     that handler.py actually CALLS. These have no name in any dispatch map:
     the model asks for them by supplying COPY (a speaker's name, a brand line),
     and the builder derives everything else from the design system. The
     name-plate and the end-card reach the frame through this path, which is
     exactly why the map-based half of this gate could never have caught them.

WHAT IS DELIBERATELY *NOT* A FAILURE. A component that is exported from the
motion-graphics barrel but appears in no dispatch map is reported as INVENTORY,
not failed: the renderer genuinely cannot produce it, so it is dead code (a
§4.8 wire-or-delete question) rather than a broken chain. Today that set is
{SpeechBubble} — the generic bubble superseded by its four branded variants.
Calling that a completeness failure would make the gate unfixable-without-
deleting and teach everyone to route around it.

    python3 cert_component_completeness.py      # exit 0 = PASS
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAILURES = []
_INVENTORY = []


def check(label, cond, detail=""):
    if cond:
        print(f"  [PASS] {label}")
    else:
        FAILURES.append(f"{label}{(' — ' + detail) if detail else ''}")
        print(f"  [FAIL] {label}{(' — ' + detail) if detail else ''}")


def _read(rel):
    with open(os.path.join(HERE, rel), encoding="utf-8") as f:
        return f.read()


def _strip_py_comments(text):
    """Drop comment-ONLY lines. Deliberately not a tokenizer: the only thing this
    must never do is let a name mentioned solely in a `#` note count as taught —
    the exact class red_proof.py's docstring records this repo writing five
    times. Trailing comments are left alone; a line with real code on it is real
    code."""
    return "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("#"))


# ── AUTHORITY 1: what the renderer can dispatch by name ─────────────────────
_MAP_RE = re.compile(
    r"(?:export\s+)?const\s+(CAPTION_MAP|TRANSITION_MAP|ZOOM_MAP|MG_MAP)"
    r"\s*:[^=]*=\s*\{(.*?)\n\};", re.S)


def renderer_maps(render_src):
    """{MAP_NAME: {component names}} straight out of PromptlyRender.tsx."""
    out = {}
    for m in _MAP_RE.finditer(render_src):
        body = re.sub(r"//[^\n]*", "", m.group(2))
        out[m.group(1)] = set(re.findall(
            r"(?:^|,)\s*([A-Za-z_$][\w$]*)\s*(?::\s*[\w$]+)?\s*(?=,|$)",
            body, re.M))
    return out


# ── AUTHORITY 2: the schema vocabulary + PROOF the schema derives from it ───
def literal_derivations(handler_src):
    """{python Literal alias: registry frozenset name} for every
    `_X = Literal[tuple(sorted(VALID_Y))]`. This is what lets the rest of the
    gate treat type_registries.py AS the response schema: handler builds the
    Pydantic Literals from those frozensets, `_post_cuts_response_schema()`
    derives from the Pydantic models, so registry membership IS emittability.
    If anyone ever hardcodes a Literal instead, that link breaks and the check
    below says so rather than silently gating against a stale vocabulary."""
    return dict(re.findall(
        r"^(_\w+)\s*=\s*Literal\[tuple\(sorted\((VALID_\w+)\)\)\]",
        handler_src, re.M))


# ── AUTHORITY 3: the fields the model can actually emit ────────────────────
_TRIPLE_RE = re.compile(r'"""(?:.|\n)*?"""' + r"|'''(?:.|\n)*?'''")


def _class_body(handler_src, class_name):
    """The declaration lines of a Pydantic model — comments AND docstrings
    removed. Both removals are load-bearing. A prose line inside a docstring
    ("only from what the video itself states: the speaker says...") parses as a
    perfect `name: annotation` declaration, and counting it as a real field is
    how a gate reports a schema carries something it does not — the
    pass-for-the-wrong-reason class red_proof.py was built for. Caught here by
    this gate's own green-transition check, which reported a phantom `states`
    field."""
    m = re.search(r"^class %s\(BaseModel\):\n(.*?)(?=^class |\Z)" % re.escape(class_name),
                  handler_src, re.S | re.M)
    if m is None:
        return None
    return _strip_py_comments(_TRIPLE_RE.sub("", m.group(1)))


def model_fields(handler_src, class_name):
    """Declared field names of a Pydantic model, or None if it does not exist."""
    body = _class_body(handler_src, class_name)
    return None if body is None else set(re.findall(r"^    ([A-Za-z_]\w*)\s*:", body, re.M))


def field_annotation(handler_src, class_name, field):
    body = _class_body(handler_src, class_name)
    if body is None:
        return ""
    hit = re.search(r"^    %s\s*:\s*([^\n=]+)" % re.escape(field), body, re.M)
    return (hit.group(1).strip() if hit else "")


# ── AUTHORITY 4: the spec-built producers and the copy they need ────────────
def brand_producers(brand_src):
    return set(re.findall(r"^def (build_\w+)\(", brand_src, re.M))


def reachable_producers(brand_src, producers, handler_code):
    """Producers handler can actually reach — directly, or through another
    producer it calls. `build_name_plate` is never named in handler.py; it is
    called by `build_brand_specs`, which is. Counting only direct calls would
    report 1-of-3 and make the honest state look broken; ignoring reachability
    entirely would let a genuinely inert builder hide behind a live sibling."""
    reached = {p for p in producers if (p + "(") in handler_code}
    changed = True
    while changed:
        changed = False
        for p in sorted(reached):
            body = re.search(r"^def %s\(.*?(?=^def |\Z)" % re.escape(p),
                             brand_src, re.S | re.M)
            if not body:
                continue
            for q in producers - reached:
                if (q + "(") in body.group(0):
                    reached.add(q)
                    changed = True
    return reached


def producer_component_name(builder):
    """`build_name_plate` -> `NamePlate`. Derived, never typed: a hand-written
    map from builder to component is the same stale-list defect this gate
    exists to prevent, one file over."""
    return "".join(w.capitalize() for w in builder[len("build_"):].split("_"))


def brand_wiring(handler_src):
    """(plan_key, {copy keys}) — what handler reads the brand copy OUT of, and
    which keys it needs. Both come from the live call site, so a rename on
    either side is caught instead of being assumed."""
    src = _strip_py_comments(handler_src)
    key = re.findall(r'_brand_src\s*=\s*\(edit_plan\.get\("([^"]+)"\)', src)
    return (key[0] if key else None), set(re.findall(r'_brand_src\.get\("([^"]+)"\)', src))


def main():
    handler = _read("handler.py")
    handler_code = _strip_py_comments(handler)
    render = _read("src/remotion/src/PromptlyRender.tsx")
    brand = _read("brand_components.py")
    mg_barrel = _read("src/remotion/src/motion-graphics/index.ts")
    import guidance_registry as gr
    import type_registries as tr

    maps = renderer_maps(render)
    print("=== ARM 1: the producer list is DERIVABLE (a stale gate gates nothing) ===")
    check("all four renderer dispatch maps parsed out of PromptlyRender.tsx",
          set(maps) == {"CAPTION_MAP", "TRANSITION_MAP", "ZOOM_MAP", "MG_MAP"},
          f"found {sorted(maps)} — the maps were renamed or reshaped, so every "
          f"parity check below would silently compare against nothing")
    for _m, _s in sorted(maps.items()):
        check(f"{_m} is non-empty ({len(_s)} components)", bool(_s))

    print("\n=== ARM 2: the SCHEMA is the registry (proved, not assumed) ===")
    derived = literal_derivations(handler)
    for alias, reg in (("_CAPTION_STYLES", "VALID_CAPTION_STYLES"),
                       ("_TRANSITION_TYPES", "VALID_TRANSITION_TYPES"),
                       ("_TCO_TYPES", "VALID_TIGHT_CUT_OVERLAYS"),
                       ("_ZOOM_TYPES", "VALID_ZOOM_TYPES"),
                       ("_MG_TYPES", "VALID_MG_TYPES")):
        check(f"handler {alias} derives from type_registries.{reg}",
              derived.get(alias) == reg,
              f"got {derived.get(alias)!r} — the response schema no longer "
              f"follows the registry, so registry membership stops proving "
              f"the model can emit the name")

    print("\n=== ARM 3: NAMED components — renderer <-> schema parity, both ways ===")
    # Both directions matter and they fail differently. A renderer name missing
    # from the schema is a component nobody can ask for (this gate's whole
    # reason). A schema name with no renderer is a component the model WILL ask
    # for and the render will then crash on or silently drop.
    families = (
        ("captions", maps.get("CAPTION_MAP", set()),
         set(tr.VALID_CAPTION_STYLES) - {"none"}),
        ("zooms", maps.get("ZOOM_MAP", set()), set(tr.VALID_ZOOM_TYPES)),
        # LightLeak renders as a tight-cut overlay, not a handle transition, so
        # the schema side of this family is the UNION of the two registries —
        # one map, two emission paths.
        ("transitions+overlays", maps.get("TRANSITION_MAP", set()),
         set(tr.VALID_TRANSITION_TYPES) | set(tr.VALID_TIGHT_CUT_OVERLAYS)),
        ("motion graphics", maps.get("MG_MAP", set()), set(tr.VALID_MG_TYPES)),
    )
    for label, rendered, emittable in families:
        check(f"{label}: every renderable name is REQUESTABLE ({len(rendered)})",
              not (rendered - emittable),
              f"renderer can produce {sorted(rendered - emittable)} but the "
              f"response schema has no enum value for it — BUILT-NOT-WIRED")
        check(f"{label}: every requestable name is RENDERABLE ({len(emittable)})",
              not (emittable - rendered),
              f"schema lets the model emit {sorted(emittable - rendered)} but "
              f"the renderer has no component for it — the model will ask for "
              f"a component that cannot render")

    print("\n=== ARM 4: NAMED components are TAUGHT, not just legal ===")
    all_named = set().union(*[s for _, s, _ in families]) if families else set()
    _guidance_text = (gr.__doc__ or "") + "".join(
        p.guidance for p in gr.PROFILES.values())
    untaught = sorted(n for n in all_named
                      if n not in handler_code and n not in _guidance_text)
    check(f"all {len(all_named)} renderable component names appear in prompt "
          f"or guidance text", not untaught,
          f"never named to the model: {untaught} — a legal enum value the "
          f"prompt never mentions is emitted at ~0 rate")

    print("\n=== ARM 5: SPEC-BUILT components — the path with no enum ===")
    # The name-plate and the end-card have no dispatch-map name. They are asked
    # for by COPY, so their completeness question is: does the schema carry a
    # field for that copy, and does the field the handler READS match the field
    # the model WRITES? This is the arm that catches instance seven.
    producers = brand_producers(brand)
    called = sorted(reachable_producers(brand, producers, handler_code))
    check(f"every brand_components producer is REACHED by handler "
          f"({len(called)}/{len(producers)})",
          set(called) == producers,
          f"{sorted(producers - set(called))} are never reached from handler — "
          f"an inert builder is a component that cannot exist")
    # Ground the spec-built producers in components a viewer can actually see:
    # each must have a real Remotion component directory. A builder with no
    # component is a spec nothing renders.
    spec_components = {producer_component_name(p) for p in called
                       if os.path.isdir(os.path.join(
                           HERE, "src/remotion/src/motion-graphics",
                           producer_component_name(p)))}
    check(f"spec-built producers map to real Remotion components "
          f"({sorted(spec_components)})", bool(spec_components),
          f"no producer in {called} has a component directory under "
          f"src/remotion/src/motion-graphics — nothing would render")

    plan_key, copy_keys = brand_wiring(handler)
    check("handler names a plan key to read brand copy out of",
          bool(plan_key), "no `_brand_src = (edit_plan.get(...)` call site found")
    check("handler names the copy fields it needs", bool(copy_keys),
          "no `_brand_src.get(...)` reads found")

    plan_fields = model_fields(handler, "PostCutPlan") or set()
    check("PostCutPlan parsed out of handler.py", bool(plan_fields),
          "the response-schema model could not be located — every check below "
          "would pass for the wrong reason")
    check(f"the brand-copy plan key {plan_key!r} is a PostCutPlan field",
          plan_key in plan_fields,
          f"handler reads brand copy from edit_plan[{plan_key!r}], but the "
          f"response schema has no {plan_key!r} field, so the model can never "
          f"put anything there and every brand component is None on 100% of "
          f"jobs — BUILT-NOT-WIRED")

    # Resolve the plan key's nested model and check every copy field exists on
    # it. Renaming a field on one side only is the quiet version of the same
    # defect and is caught here.
    ann = field_annotation(handler, "PostCutPlan", plan_key) if plan_key else ""
    nested = re.findall(r"_[A-Za-z]\w*", ann)
    copy_fields = None
    for cand in nested:
        got = model_fields(handler, cand)
        if got:
            copy_fields = got
            break
    check(f"the {plan_key!r} field resolves to a declared schema object",
          copy_fields is not None,
          f"annotation {ann!r} names no Pydantic model this gate can find")
    if copy_fields is not None:
        missing = sorted(k for k in copy_keys if k not in copy_fields)
        check(f"every copy field handler reads is EMITTABLE "
              f"({len(copy_keys) - len(missing)}/{len(copy_keys)})",
              not missing,
              f"handler reads {missing} but the schema object declares "
              f"{sorted(copy_fields)} — the model cannot supply them")

    print("\n=== ARM 6: SPEC-BUILT components are TAUGHT, and the guidance LOADS ===")
    # Two failures live here and only one is obvious. The obvious one is
    # guidance that never mentions the component. The quiet one is guidance that
    # mentions it perfectly inside a profile no route ever selects — a
    # registered profile with no route is dead text, which is this very defect
    # class reappearing one layer up.
    def _names(p):
        g = p.guidance.lower()
        return ("name-plate" in g or "name_plate" in g,
                "end-card" in g or "end_card" in g)

    teaching = {n: p for n, p in gr.PROFILES.items() if all(_names(p))}
    check("a guidance profile teaches BOTH the name-plate and the end-card",
          bool(teaching),
          "no profile in guidance_registry names both components — the model "
          "is never told they exist, so brand_copy is emitted at ~0 rate")
    routable = set()
    for stack in gr._ROUTE_STACKS.values():
        routable |= set(stack)
    check("that profile is REACHABLE from a route stack",
          bool(set(teaching) & routable),
          f"profiles {sorted(teaching)} are registered but no key in "
          f"_ROUTE_STACKS selects them — registered-but-unroutable guidance is "
          f"text that can never reach a prompt")
    for n in sorted(teaching):
        # The teaching profile must be composable with every other profile, or
        # the route that needs it raises GuidanceContradiction at compose time.
        bad = []
        for other in gr.PROFILES:
            try:
                gr.compose_suffix([other, n])
            except gr.GuidanceContradiction:
                bad.append(other)
        check(f"{n} stacks with every profile without contradiction",
              not bad, f"contradicts {bad}")
    # Teaching that never names the FIELD leaves the model knowing a component
    # exists with no idea where to put the words for it.
    check(f"the guidance names the schema field ({plan_key!r}) the copy goes in",
          bool(plan_key) and any(plan_key in p.guidance for p in teaching.values()),
          f"no teaching profile mentions {plan_key!r} — the model is told the "
          f"components exist but not which field carries them")

    print("\n=== ARM 7: the diet passes cannot strip the identity fields ===")
    lean = re.search(r"_LEAN_DROP_FIELDS = \{(.*?)\n\}", handler, re.S)
    lean_body = lean.group(1) if lean else ""
    check("no output-diet pass drops a brand-copy field",
          not [k for k in copy_keys if f'"{k}"' in lean_body],
          f"a diet arm strips {[k for k in copy_keys if chr(34) + k + chr(34) in lean_body]} "
          f"— the field would be legal, taught, and never generated")

    print("\n=== INVENTORY (reported, not failed) ===")
    # Exported from the motion-graphics barrel but in no dispatch map: the
    # renderer cannot produce these, so they are dead code (§4.8), not a broken
    # chain. Named here so the number is visible instead of discovered by
    # accident for the eighth time.
    exported = set(re.findall(r'^export \{\s*([^}]*?)\s*\} from "\./', mg_barrel, re.M | re.S))
    exported = {n.strip() for grp in exported for n in grp.split(",") if n.strip()}
    exported = {n for n in exported if n[:1].isupper()}
    dispatchable = maps.get("MG_MAP", set())
    orphans = sorted(exported - dispatchable - spec_components)
    for o in orphans:
        _INVENTORY.append(o)
        print(f"  [INFO] {o}: exported from the MG barrel, in no dispatch map, "
              f"no spec builder — the renderer cannot produce it (§4.8 "
              f"wire-or-delete)")
    print(f"  producers: {len(all_named)} named + {len(called)} spec-built "
          f"({', '.join(called) or 'none'}); {len(orphans)} exported-but-inert")
    # THE NEXT LINK, NAMED SO IT IS NOT DISCOVERED BY ACCIDENT. This gate ends
    # at REQUESTABLE + TAUGHT, which is where the last seven instances died. It
    # does NOT assert the spec ever reaches a frame: a spec-built component
    # still needs a renderer dispatch entry and something that turns
    # edit_plan["_brand_specs"] into render props. Asserting that here would
    # make the gate ungreenable and teach people to route around it — so it is
    # REPORTED, every run, with the denominator [Rule 2].
    unrendered = sorted(n for n in spec_components if n not in dispatchable)
    consumers = sum(1 for f in ("handler.py", "render_schemas.py", "ffmpeg_base.py")
                    if "_brand_specs" in _read(f))
    if unrendered:
        print(f"  [INFO] NOT-YET-RENDERABLE: {unrendered} are requestable and "
              f"taught, and their specs are built — but they are in no dispatch "
              f"map and _brand_specs has {consumers - 1} render-path consumer(s) "
              f"beyond the liveness counter. Requesting them moves the "
              f"brand_components_built counter, NOT pixels.")

    print()
    if FAILURES:
        print(f"COMPONENT-COMPLETENESS: {len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("COMPONENT-COMPLETENESS: ALL PASS (every component the pipeline can "
          "produce is requestable in the response schema and taught in the "
          "prompt or a routable guidance profile)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
