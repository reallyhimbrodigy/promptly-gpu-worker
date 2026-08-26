#!/usr/bin/env python3
"""A BEAT CARRIES THE WHOLE EDIT, IN THE SHAPES ARM A ALREADY EMITS. `[RULE-1]`

The first beat schema could express ONE thing: a component placement. No cut, no
zoom, no overlay, no b-roll, no caption beat, no generated scene — while the
doctrine's own steps told the model to cut for pace, vary the texture and land
the payoff with sound. The schema could not receive most of what the prompt asked
for, so arm B would have returned MG-only plans, and the pre-registered win
condition (`generated_scenes` off zero) was not even observable.

All seven treatments now exist. This asserts the four ways that can still be
wrong, each of which produces a plausible-looking A/B number:

  1. A FAMILY IS DECLARED BUT NEVER FLATTENED. The field exists on the beat, the
     model fills it, and the transform silently drops it on the floor — read
     afterwards as "the planner didn't ask for b-roll".

  2. THE FLATTENED SHAPE IS NOT WHAT THE PIPELINE CONSUMES. Every expectation
     here is READ OFF PostCutPlan's own resolved schema rather than written from
     memory, because a hand-copied expectation drifts in exactly the same way the
     hand-copied wire schema would have.

  3. A REQUIRED FIELD IS FABRICATED. The standing law is that a missing required
     field DROPS the treatment and ledgers the reason; inventing a
     `viewer_feeling` to satisfy a schema is the failure mode the whole
     drop-never-fabricate rule exists to prevent.

  4. A SECOND CLOCK. Spans must end on a WORD INDEX. This repo has paid twice for
     a parallel seconds clock, and a beat list is precisely where a third is
     tempting.

Run: python3 cert_prompt_v2_families.py
"""
import os
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


def resolved(schema, node):
    defs = schema.get("$defs", {})
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 10:
        node = defs.get(node["$ref"].split("/")[-1], {})
        seen += 1
    if isinstance(node, dict) and "anyOf" in node and "properties" not in node:
        for alt in node["anyOf"]:
            alt_r = resolved(schema, alt)
            if isinstance(alt_r, dict) and alt_r.get("properties"):
                return alt_r
    return node


def main():
    import io
    import contextlib
    _buf = io.StringIO()
    with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(_buf):
        import handler                      # noisy startup banner, suppressed
    import prompt_v2_schema as pv2s

    schema = handler._post_cuts_response_schema()

    # ── 1. every declared family has a field on Beat and a flatten target ────
    beat_fields = set(pv2s.Beat.model_fields.keys())
    for fam in pv2s.BEAT_FAMILIES:
        check(f"family {fam!r} is a field on Beat", fam in beat_fields,
              f"Beat fields: {sorted(beat_fields)}")
        target = pv2s.FAMILY_TARGET.get(fam)
        check(f"family {fam!r} names a component-major target", bool(target),
              "no FAMILY_TARGET entry")
        if target:
            check(f"{target!r} is a real PostCutPlan field",
                  target in schema.get("properties", {}),
                  f"not in the arm-A schema — the flatten would write a key "
                  f"nothing downstream reads")

    # ── 1b. NO UNBOUNDED STRING ANYWHERE IN THE WIRE SCHEMA ────────────────
    # MEASURED, three arm-B cells in a row: `shape-abort string-runaway
    # (run=4096ch)` — one string field ran away and the degeneration detector
    # killed the call, every time, while arm A completed on the same source.
    # Arm A caps its strings by declaration and enforces them at the parse edge;
    # this schema declared `notes`, `background`, `subject`, `motion`, every
    # `reason` and each caption keyword with NO max_length at all. An unbounded
    # string in a structured-output schema is an invitation to a repetition loop.
    def _uncapped(node, path=""):
        out = []
        if isinstance(node, dict):
            # BOUNDED is the property, not "has a maxLength". An enum-constrained
            # string cannot run away — its value set is finite — so requiring a
            # length on it tests the wrong thing and would push a pointless cap
            # onto every closed vocabulary.
            _bounded = ("maxLength" in node or "enum" in node or "const" in node)
            if node.get("type") == "string" and not _bounded:
                out.append(path or "<root>")
            for k, v in node.items():
                out += _uncapped(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                out += _uncapped(v, f"{path}[{i}]")
        return out
    _wire = pv2s.BeatMajorPlan.model_json_schema()
    _open = _uncapped(_wire)
    check("every string field in the wire schema declares a maxLength",
          not _open,
          f"unbounded: {_open} — an uncapped string is what three measured "
          f"arm-B cells ran away in")

    # ── 2. a full-coverage plan flattens into arm A's shapes ────────────────
    plan = {"beats": [
        {"word_index": 0, "says": "hello", "read": "open",
         "cut": {"until_word_index": 3, "reason": "throat-clear before the line"}},
        {"word_index": 5, "says": "forty percent", "read": "the number",
         "emphasis": {"type": "number", "intensity": "high", "duration": 0.8,
                      "viewer_feeling": "that is a lot", "sound": "impact",
                      "until_word_index": 6,
                      "zoom": {"arc_position": "mid_peak", "type": "punch_in",
                               "scale": 1.12}},
         "place": [{"component": "StatCard",
                    "props": {"value": "40", "label": "percent"}}]},
        {"word_index": 9, "read": "name it",
         "overlay": {"variant": "lower_third", "duration_seconds": 2.0,
                     "text": "Ada Lovelace"}},
        {"word_index": 14, "read": "cut away to the thing",
         "broll": {"keyword": "server rack", "until_word_index": 18,
                   "reason": "he is describing hardware"}},
        {"word_index": 21, "read": "the claim deserves a scene",
         "scene": {"background": "deep navy gradient", "subject": "a rising bar",
                   "motion": "slow push", "until_word_index": 26,
                   "anchor": "center_safe", "scene_type": "stat_reveal"}},
        {"word_index": 30, "read": "stress the verb",
         "caption": {"keywords": ["shipped", "shipped"], "position": "top"}},
        {"word_index": 34, "read": "let it breathe"},
    ]}
    seen_req, seen_drop = [], []
    out = pv2s.flatten_beats(
        plan, ledger=(lambda k, c=None, n=1: seen_req.append((k, c)),
                      lambda k, c=None, r="", n=1: seen_drop.append((k, c, r))))

    for fam, target in pv2s.FAMILY_TARGET.items():
        if target == "caption_keywords":
            continue                     # a list of strings, checked separately
        arr = out.get(target)
        check(f"{target} is populated by the transform", bool(arr),
              f"family {fam!r} produced nothing — declared but never flattened")
        if not arr:
            continue
        item_schema = resolved(schema, schema["properties"][target].get("items", {}))
        props = set((item_schema.get("properties") or {}).keys())
        req = set(item_schema.get("required") or [])
        for it in arr:
            missing = req - set(it.keys())
            check(f"{target} item carries every field PostCutPlan requires",
                  not missing, f"missing {sorted(missing)} from {sorted(it.keys())}")
            extra = set(it.keys()) - props
            check(f"{target} item invents no field PostCutPlan lacks",
                  not extra, f"invented {sorted(extra)}")

    # THE WIN CONDITION, measurable at last.
    check("generated_scenes is expressible and non-empty",
          len(out.get("generated_scenes") or []) == 1,
          f"got {out.get('generated_scenes')} — the pre-registered win condition "
          f"cannot be observed if a scene cannot be asked for")

    # ── 3. spans end on WORD INDICES, never seconds ─────────────────────────
    for target, key in (("cut_refinements", "end_word_index"),
                        ("broll_clips", "end_word_index"),
                        ("generated_scenes", "end_word_index")):
        it = (out.get(target) or [{}])[0]
        check(f"{target} span ends on a word index", isinstance(it.get(key), int),
              f"{key}={it.get(key)!r} — a float seconds field here is a SECOND "
              f"CLOCK, which this repo has paid for twice")
    check("emphasis expands its span into word_indices",
          out["emphasis_moments"][0]["word_indices"] == [5, 6],
          f"got {out['emphasis_moments'][0].get('word_indices')}")

    # ── 4. caption keywords de-duplicate ────────────────────────────────────
    check("a word emphasised twice counts once",
          out["caption_keywords"] == ["shipped"],
          f"got {out['caption_keywords']} — duplicates double-count the density read")
    check("caption position changes are word-anchored",
          out["caption_position_changes"] == [{"word_index": 30, "position": "top"}],
          f"got {out['caption_position_changes']}")

    # ── 5. MISSING REQUIRED DROPS, NEVER FABRICATES ────────────────────────
    broken = {"beats": [
        {"word_index": 1, "cut": {"until_word_index": 4}},                       # no reason
        {"word_index": 2, "emphasis": {"type": "x", "intensity": "high",
                                       "duration": 0.5, "sound": "s"}},          # no viewer_feeling
        {"word_index": 3, "overlay": {"variant": "lower_third"}},                # no duration
        {"word_index": 4, "broll": {"keyword": "k", "reason": "r"}},             # no until
        {"word_index": 5, "scene": {"background": "b", "subject": "s",
                                    "motion": "m", "anchor": "a"}},              # no until
        {"word_index": 6, "place": [{"component": "StatCard",
                                     "props": {"value": "40"}}]},                # no label
    ]}
    dreq, ddrop = [], []
    bout = pv2s.flatten_beats(
        broken, ledger=(lambda k, c=None, n=1: dreq.append((k, c)),
                        lambda k, c=None, r="", n=1: ddrop.append((k, c, r))))
    for target in ("cut_refinements", "emphasis_moments", "text_overlays",
                   "broll_clips", "generated_scenes", "motion_graphics"):
        check(f"an incomplete {target} entry is DROPPED, not invented",
              bout.get(target) == [],
              f"got {bout.get(target)} — a fabricated required field is the exact "
              f"failure drop-never-fabricate exists to prevent")
    check("every drop is ledgered with a reason", len(ddrop) == 6,
          f"{len(ddrop)} drops ledgered, expected 6: {ddrop}")
    check("every drop names the missing field",
          all("missing_required" in d[2] for d in ddrop),
          f"reasons: {[d[2] for d in ddrop]}")
    check("a drop is still counted as REQUESTED", len(dreq) == 6,
          f"{len(dreq)} requested — a dropped treatment the planner ASKED for "
          f"must not vanish from the ledger, or it reads as a decline")

    # ── 6. the counts declare every family ─────────────────────────────────
    counts = out.get("_v2_counts") or {}
    check("_v2_counts declares per-family emissions",
          set(counts.get("emitted_by_family") or {}) >= {
              "cut_refinements", "emphasis_moments", "text_overlays",
              "broll_clips", "generated_scenes", "motion_graphics"},
          f"got {counts.get('emitted_by_family')}")
    check("_v2_counts still declares the motion-graphics equality's own side",
          counts.get("motion_graphics_len") == len(out["motion_graphics"]),
          f"{counts.get('motion_graphics_len')} vs {len(out['motion_graphics'])}")

    # ── 7. density reports BOTH numbers, and does not collapse them ────────
    d = pv2s.density_of(plan, 40.0)
    check("density reports placements and all-motion separately",
          d["placements"] == 1 and d["moves"] > d["placements"],
          f"placements={d.get('placements')} moves={d.get('moves')} — collapsing "
          f"these is the unit error that made 0.14/sec read against a 3.5 target")
    check("the 3.5 reference is attached to the all-motion number",
          d.get("reference_moves_per_s") == 3.5,
          f"got {d.get('reference_moves_per_s')}")
    # a cut-only beat breaks stillness exactly as a graphic does
    wt = {0: 0.0, 5: 6.0, 9: 9.0, 14: 12.0, 21: 15.0, 30: 20.0, 34: 24.0}
    v = pv2s.stillness_violations(plan, wt)
    check("stillness counts ANY treatment, not just placements",
          all(g["from_word"] != 0 or g["gap_s"] <= 6.0 for g in v)
          and any(g["gap_s"] > 3.5 for g in v),
          f"violations: {v} — a beat that only cuts still breaks stillness")

    print(f"\nCERT PROMPT-V2 FAMILIES: {'FAIL' if FAILS else 'PASS'}")
    for f in FAILS:
        print(f"  - {f}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
