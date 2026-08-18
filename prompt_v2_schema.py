#!/usr/bin/env python3
"""BEAT-MAJOR PLAN SCHEMA + the flatten transform. `[EDITORIAL_PROMPT_V2 §1, §5]`

WHY BEAT-MAJOR. Today the model fills parallel arrays — motion_graphics[],
text_overlays[], transitions[], emphasis_moments[]. That is COMPONENT-MAJOR: a
form sorted by our internal taxonomy, asking "list all your motion graphics",
which is not a question any editor has ever asked themselves.

Editors work along a timeline, so the plan does too. Four consequences, and only
the first is cosmetic:

  1. it answers "exactly what component, exactly where" LITERALLY — that IS a
     beat list; component-major arrays answer "what exists" and only imply where;
  2. density becomes visible TO THE MODEL WHILE IT WRITES — three consecutive
     `place: []` beats across 9 seconds is a gap it can see and fix in the same
     generation. Filling four separate arrays, nobody can see the gaps, us
     included;
  3. `read` sits where it does work — one line per beat, immediately before the
     decision it justifies, rather than as a preamble at the top;
  4. the intent/execution gap becomes legible: `read` (what it saw), `place`
     (what it asked for), the component ledger (what shipped). Every "the
     planner declined" finding in this campaign resolved into something WE did.

THE RENDER SIDE DOES NOT CHANGE. flatten_beats() converts beats[].place[] back
into the component-major arrays the pipeline already consumes, and DECLARES the
per-component counts that handler.py:28540's equality assertion needs.

ON TYPED PROPS AND WHAT IS ACTUALLY EXPRESSIBLE (§5). The honest constraint:
Vertex's structured-output schema does not reliably carry discriminated unions
(anyOf + discriminator), and a schema the model cannot satisfy is worse than a
loose one — it fabricates or drops. So the WIRE schema is one flat props object
with everything optional, and PYTHON enforces the per-component contract:

    required-by-trigger  -> the fields the beat's own trigger guarantees exist
    everything else      -> optional
    missing required     -> THE PLACEMENT IS DROPPED, never fabricated, and the
                            drop is ledgered with its reason

That is the same guarantee a discriminated union would give, enforced where it
can actually run.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

try:
    from type_registries import VALID_MG_TYPES
except Exception:                                    # pragma: no cover
    VALID_MG_TYPES = frozenset()

# ── §5 PER-COMPONENT CONTRACT ────────────────────────────────────────────────
# required: what the beat's TRIGGER guarantees. A stated number guarantees a
# value AND the words around it (the label); a spoken name guarantees the name.
# Nothing is required that the transcript cannot supply, because a required
# field the model cannot answer is an invitation to invent one.
#
# Field names mirror the components' own TS interfaces (StatCard.value/label,
# PullQuote.text, PillCluster.tags …) so this is a mapping, not a fifth dialect.
COMPONENT_CONTRACT: Dict[str, Dict[str, Any]] = {
    "StatCard":       {"required": ["value", "label"],
                       "optional": ["prefix", "suffix", "decimals", "fromValue"]},
    "PillCluster":    {"required": ["tags"], "optional": ["accentEvery"]},
    "PullQuote":      {"required": ["text"], "optional": ["keywords"]},
    "EditorialQuote": {"required": ["text"], "optional": []},
    "DropBanner":     {"required": ["title"], "optional": ["caption", "subtitle"]},
    "DropCard":       {"required": ["title"], "optional": ["subtitle", "points"]},
    "RankedList":     {"required": ["items"], "optional": ["order", "highlightTop"]},
    "ProgressBar":    {"required": ["at"], "optional": ["label"]},
    "Stamp":          {"required": ["text"], "optional": []},
    "NamePlate":      {"required": ["name"], "optional": ["role"]},
    "EndCard":        {"required": ["title"], "optional": ["lines", "kind"]},
    "Notification":   {"required": ["text"], "optional": ["title"]},
    "ChatThread":     {"required": ["messages"], "optional": []},
    "Timeline":       {"required": ["items"], "optional": []},
}
# Components that carry no content — timing only. An empty props dict is CORRECT
# for these, and must never be read as a grounding miss.
TIMING_ONLY = frozenset({"Reticle", "RecordingFrame", "SectionDivider",
                         "StepDivider", "MouseDrag", "AnnotationArrow",
                         "PillMarquee", "EchoOutro"})


class BeatPlacement(BaseModel):
    """One component placed at one beat."""
    component: str
    props: Dict[str, Any] = Field(default_factory=dict)
    # Optional, and only meaningful for spanning components.
    hold_s: Optional[float] = None


class Beat(BaseModel):
    """A unit of meaning — a claim, a number, a name, a turn, a payoff."""
    # Anchored on a WORD INDEX, not a float second: every existing time field in
    # this pipeline is word-anchored and Python derives seconds. A float here
    # would be a second clock, and this repo has already paid for two.
    word_index: int
    says: str = Field(default="", max_length=300)
    # §1.3 — one line of reasoning, immediately before the decision it justifies.
    read: str = Field(default="", max_length=400)
    place: List[BeatPlacement] = Field(default_factory=list)


class BeatMajorPlan(BaseModel):
    """The v2 response shape. Globals stay global; everything timed is a beat."""
    beats: List[Beat] = Field(default_factory=list)
    caption_style: Optional[str] = None
    aspect_ratio: Optional[str] = None
    video_identity: Optional[str] = None
    notes: Optional[str] = None


# ── THE FLATTEN TRANSFORM ────────────────────────────────────────────────────
def _validate_props(component: str, props: Dict[str, Any]):
    """(ok, cleaned, reason). MISSING REQUIRED => DROP, never fabricate."""
    if component in TIMING_ONLY:
        return True, dict(props or {}), None
    spec = COMPONENT_CONTRACT.get(component)
    if spec is None:
        # An unknown component is not an error here — the enum upstream owns
        # that. Pass its props through untouched rather than inventing a
        # contract we never wrote down.
        return True, dict(props or {}), None
    p = dict(props or {})
    missing = [k for k in spec["required"]
               if p.get(k) in (None, "", [], {})]
    if missing:
        return False, p, f"missing_required:{','.join(missing)}"
    return True, p, None


def flatten_beats(plan: Dict[str, Any], *, ledger=None) -> Dict[str, Any]:
    """beats[] -> the component-major arrays the render path already consumes.

    Returns the SAME dict, mutated, so every downstream reader is untouched.

    handler.py:28540 asserts
        len(motion_graphics_out) + misses == top-level + emphasis + brand
    and derives `top-level` from len(edit_plan["motion_graphics"]). Because this
    transform runs BEFORE that count is taken, the equality holds by
    construction — but the counts are ALSO declared explicitly in
    `_v2_counts` so a mismatch is diagnosable rather than merely fatal.

    `ledger` is handler's _ledger_requested/_ledger_dropped pair when available:
    a placement dropped HERE is dropped BY US, and that is exactly the
    distinction the component ledger exists to make.
    """
    beats = plan.get("beats")
    if not isinstance(beats, list):
        return plan                      # not a v2 plan — leave it alone

    mgs: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    dropped: Dict[str, int] = {}

    for b in beats:
        if not isinstance(b, dict):
            continue
        try:
            wi = int(b.get("word_index"))
        except (TypeError, ValueError):
            continue
        for pl in (b.get("place") or []):
            if not isinstance(pl, dict):
                continue
            comp = str(pl.get("component") or "").strip()
            if not comp:
                continue
            if ledger:
                ledger[0]("motion_graphic", comp)        # requested
            ok, props, why = _validate_props(comp, pl.get("props") or {})
            if not ok:
                dropped[comp] = dropped.get(comp, 0) + 1
                if ledger:
                    ledger[1]("motion_graphic", comp, why)   # dropped BY US
                continue
            entry = {
                "type": comp,
                "start_word_index": wi,
                "end_word_index": wi,
                "anchor": pl.get("anchor") or "upper_third_safe",
                "props": props,
            }
            if pl.get("hold_s") is not None:
                entry["duration_seconds"] = pl["hold_s"]
            mgs.append(entry)
            counts[comp] = counts.get(comp, 0) + 1

    plan["motion_graphics"] = mgs
    # DECLARED, not inferred. The assertion at handler.py:28540 is an equality;
    # when it trips, this is the record of what the transform believed it built.
    plan["_v2_counts"] = {
        "beats": len(beats),
        "placements_requested": sum(counts.values()) + sum(dropped.values()),
        "placements_emitted": sum(counts.values()),
        "dropped_by_us": dropped,
        "by_component": counts,
        # The equality's own left-hand side, stated where a human can read it.
        "motion_graphics_len": len(mgs),
    }
    return plan


def density_of(plan: Dict[str, Any], duration_s: float) -> Dict[str, Any]:
    """PLACEMENT density — and it is NOT the §4 3.5/sec figure.

    THE UNIT ERROR THIS AVOIDS, caught on the exemplars before the A/B ran: §4's
    ~3.5 moving samples/sec counts EVERY motion kind together — cuts, caption
    beats, graphics, camera moves. Component placements are one of those four.
    REF-2 carries 6 placements in 43s = 0.14/sec, and reporting that against a
    3.5 target reads as a catastrophic miss when the two numbers measure
    different things.

    So this returns placement density ONLY, with the comparable reference
    measured off the same exemplars, and deliberately does not carry the §4
    figure into the same table. Motion density needs cuts and caption pages,
    which live on the flattened plan, not here.
    """
    beats = [b for b in (plan.get("beats") or []) if isinstance(b, dict)]
    placed = sum(len(b.get("place") or []) for b in beats)
    d = max(float(duration_s or 0.0), 0.001)
    return {
        "placements": placed,
        "placements_per_s": round(placed / d, 3),
        # measured off the exemplars: REF-1 6/40s, REF-2 6/43s
        "reference_placements_per_s": 0.14,
        "beats_total": len(beats),
        "beats_empty": sum(1 for b in beats if not (b.get("place") or [])),
        "note": "placement density only; §4's 3.5/sec counts all motion kinds "
                "(cuts + captions + graphics + camera) and is NOT this number",
    }


def stillness_violations(plan: Dict[str, Any], word_times: Dict[int, float],
                         ceiling_s: float = 3.5) -> List[Dict[str, Any]]:
    """§4: no still stretch longer than 3.5s, measured between PLACED beats.

    Needs the word-index -> seconds map, because beats are word-anchored (there
    is one clock in this pipeline and it is the word list). Returns the gaps
    that exceed the ceiling, so a violation names its own window.
    """
    placed = sorted(int(b["word_index"]) for b in (plan.get("beats") or [])
                    if isinstance(b, dict) and (b.get("place") or [])
                    and b.get("word_index") is not None)
    out = []
    for i in range(len(placed) - 1):
        t0, t1 = word_times.get(placed[i]), word_times.get(placed[i + 1])
        if t0 is None or t1 is None:
            continue
        if (t1 - t0) > ceiling_s:
            out.append({"from_word": placed[i], "to_word": placed[i + 1],
                        "gap_s": round(t1 - t0, 2)})
    return out
