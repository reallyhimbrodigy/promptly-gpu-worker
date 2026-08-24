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
     empty beats across 9 seconds is a gap it can see and fix in the same
     generation. Filling seven separate arrays, nobody can see the gaps, us
     included;
  3. `read` sits where it does work — one line per beat, immediately before the
     decision it justifies, rather than as a preamble at the top;
  4. the intent/execution gap becomes legible: `read` (what it saw), the beat's
     own treatments (what it asked for), the component ledger (what shipped).
     Every "the planner declined" finding in this campaign resolved into
     something WE did.

═══ THE BEAT CARRIES THE WHOLE EDIT, NOT JUST GRAPHICS (2026-08-18) ═══════════

The first version of this schema could express ONE thing: a component placement.
It had no field for a cut, a zoom, an overlay, a b-roll clip, a caption beat or a
generated scene — while the doctrine's own steps 3, 5 and 6 tell the model to cut
for pace, vary the texture, and land the payoff with sound and zoom. So the
doctrine asked for an edit and the schema could only receive decoration, and any
job run that way returned an MG-only plan: no zooms, no b-roll, no sound.

That also made the pre-registered win condition unmeasurable — `generated_scenes`
coming off zero cannot be observed in a vocabulary with no scene in it.

A beat now carries every treatment an editor applies at a moment:

    cut       remove from here to there — the FIRST tool, per doctrine step 3
    emphasis  the zoom + sound + intensity of a stressed moment
    overlay   a text overlay
    broll     a cutaway
    scene     a generated scene (the win condition)
    caption   keyword emphasis and caption position
    place     component placements (motion graphics)

Seven treatments, one timeline, one clock. THE CLOCK IS THE WORD LIST: spanning
treatments end at `until_word_index`, never at a float second. This pipeline has
paid twice for a second clock, and a beat list is exactly where a third would be
tempting to introduce.

THE RENDER SIDE DOES NOT CHANGE. flatten_beats() converts the beats back into the
component-major arrays the pipeline already consumes, in the EXACT shapes
PostCutPlan declares, and DECLARES the per-family counts that handler.py's
equality assertion needs.

ON TYPED PROPS AND WHAT IS ACTUALLY EXPRESSIBLE (§5). The honest constraint:
Vertex's structured-output schema does not reliably carry discriminated unions
(anyOf + discriminator), and a schema the model cannot satisfy is worse than a
loose one — it fabricates or drops. So the WIRE schema is one flat props object
with everything optional, and PYTHON enforces the per-component contract:

    required-by-trigger  -> the fields the beat's own trigger guarantees exist
    everything else      -> optional
    missing required     -> THE TREATMENT IS DROPPED, never fabricated, and the
                            drop is ledgered with its reason

That is the same guarantee a discriminated union would give, enforced where it
can actually run — and it now applies to all seven treatments, not just
placements. A treatment dropped here is dropped BY US, which is the distinction
the component ledger exists to make.
"""
from typing import Annotated, Any, Dict, List, Literal, Optional

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
    # ── GENERATION-FREE COMPOSITIONS ────────────────────────────────────────
    # required = what the beat's trigger GUARANTEES. Each takes a WORD INDEX for
    # the frame it shows (`at_word_index`), never a second: the worker derives
    # the source time. A renderer that did clock arithmetic would be a second
    # clock, and this pipeline has paid for two.
    "EvidenceCard":   {"required": ["claim"], "optional": ["caption"]},
    "DeviceMockup":   {"required": [], "optional": ["label"]},
    "EmojiCard":      {"required": ["emoji"], "optional": ["words"]},
}
# Components that carry no content — timing only. An empty props dict is CORRECT
# for these, and must never be read as a grounding miss.
TIMING_ONLY = frozenset({"Reticle", "RecordingFrame", "SectionDivider",
                         "StepDivider", "MouseDrag", "AnnotationArrow",
                         "PillMarquee", "EchoOutro"})

# ── THE TREATMENT CONTRACT ───────────────────────────────────────────────────
# Mirrors PostCutPlan's own `required` sets, read off the live schema rather than
# guessed, so a flattened beat plan validates against the SAME strict model arm A
# does. cert_prompt_v2_families asserts these stay in step with PostCutPlan.
TREATMENT_REQUIRED: Dict[str, List[str]] = {
    "cut":      ["until_word_index", "reason"],
    "emphasis": ["type", "intensity", "duration", "viewer_feeling", "sound"],
    "overlay":  ["variant", "duration_seconds"],
    "broll":    ["keyword", "until_word_index", "reason"],
    "scene":    ["background", "subject", "motion", "until_word_index", "anchor"],
}


class BeatPlacement(BaseModel):
    """One component placed at one beat."""
    component: str = Field(max_length=60)
    props: Dict[str, Any] = Field(default_factory=dict)
    # Optional, and only meaningful for spanning components.
    hold_s: Optional[float] = None


class BeatZoom(BaseModel):
    """The camera move on an emphasised beat. Mirrors PostCutPlan's zoom claim."""
    arc_position: str = Field(max_length=40)
    type: str = Field(max_length=40)
    scale: Optional[float] = None
    originX: Optional[float] = None
    originY: Optional[float] = None
    durationMs: Optional[int] = None


class BeatCut(BaseModel):
    """Remove from this beat's word through `until_word_index`, inclusive.

    Doctrine step 3: the cut is the FIRST tool, not the last. This is the field
    that makes that instruction answerable.
    """
    until_word_index: int
    reason: str = Field(max_length=200)


class BeatEmphasis(BaseModel):
    """A stressed moment: how it lands, how it sounds, how the camera moves."""
    type: str = Field(max_length=40)
    intensity: str = Field(max_length=24)
    duration: float
    viewer_feeling: str = Field(max_length=200)
    sound: str = Field(max_length=60)
    until_word_index: Optional[int] = None
    zoom: Optional[BeatZoom] = None


class BeatOverlay(BaseModel):
    """A text overlay starting at this beat."""
    variant: str = Field(max_length=40)
    duration_seconds: float
    text: Optional[str] = Field(default=None, max_length=200)
    quote: Optional[str] = Field(default=None, max_length=300)
    attribution: Optional[str] = Field(default=None, max_length=80)
    topText: Optional[str] = Field(default=None, max_length=120)
    bottomText: Optional[str] = Field(default=None, max_length=120)
    position: Optional[str] = Field(default=None, max_length=40)
    why: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=200)


class BeatBroll(BaseModel):
    """A cutaway covering this beat through `until_word_index`."""
    keyword: str = Field(max_length=80)
    until_word_index: int
    reason: str = Field(max_length=200)
    entry_transition: Optional[str] = Field(default=None, max_length=40)
    exit_transition: Optional[str] = Field(default=None, max_length=40)


class BeatScene(BaseModel):
    """A generated scene — the component class the campaign was built around."""
    background: str = Field(max_length=300)
    subject: str = Field(max_length=300)
    motion: str = Field(max_length=200)
    until_word_index: int
    anchor: str = Field(max_length=40)
    scene_type: Optional[str] = Field(default=None, max_length=40)
    stat: Optional[Dict[str, Any]] = None
    text_layers: Optional[List[Dict[str, Any]]] = None
    land_word_index: Optional[int] = None
    duration_seconds: Optional[float] = None


class BeatCaption(BaseModel):
    """Caption treatment at this beat: emphasised words, and/or a move."""
    # Each keyword is ONE spoken word. The per-ITEM cap is the load-bearing
    # one: a list cap bounds how many, only an item cap bounds how long, and an
    # unbounded string is what the runaway detector kills the call over.
    keywords: List[Annotated[str, Field(max_length=60)]] = Field(default_factory=list)
    position: Optional[str] = Field(default=None, max_length=40)


class Beat(BaseModel):
    """A unit of meaning — a claim, a number, a name, a turn, a payoff."""
    # Anchored on a WORD INDEX, not a float second: every existing time field in
    # this pipeline is word-anchored and Python derives seconds. A float here
    # would be a second clock, and this repo has already paid for two.
    word_index: int
    # REQUIRED, both of them, and this is load-bearing. With defaults, the ONLY
    # required field on a beat was word_index — and a measured cell returned 14
    # beats carrying a word index each, no `says`, no `read`, no treatment, in
    # 1,688 output tokens. That is a schema-minimal response: the model answered
    # exactly what it was obliged to answer. The doctrine says `read` sits on
    # EVERY beat, before the decision it justifies; the schema now says the same
    # thing, so an empty beat costs a sentence explaining why it is empty rather
    # than being the cheapest legal answer.
    says: str = Field(max_length=300)
    read: str = Field(max_length=400)
    place: List[BeatPlacement] = Field(default_factory=list)
    # The other six treatments. All optional: most beats carry one or none, and
    # some deliberately carry nothing — stillness is a decision too.
    cut: Optional[BeatCut] = None
    emphasis: Optional[BeatEmphasis] = None
    overlay: Optional[BeatOverlay] = None
    broll: Optional[BeatBroll] = None
    scene: Optional[BeatScene] = None
    caption: Optional[BeatCaption] = None


# NO LIST-LENGTH CAPS ANYWHERE BELOW. pydantic renders `max_length` on a List as
# `maxItems`, which is the ONE json-schema keyword this schema used that arm A's
# does not — and adding it made Vertex reject the whole request with
# `400 INVALID_ARGUMENT`, measured. Per-ITEM caps (maxLength on the string) are
# kept: those are what bound a runaway, and arm A uses them too.


class ArcSegment(BaseModel):
    start_word_index: int
    end_word_index: int
    position: str = Field(max_length=40)
    intensity: str = Field(max_length=24)


class KeyMoment(BaseModel):
    word_index: int
    what_lands: str = Field(max_length=200)
    why_emphasis: str = Field(max_length=200)
    what_i_saw: str = Field(max_length=200)
    viewer_feeling: str = Field(max_length=200)


class Movement(BaseModel):
    start_word_index: int
    end_word_index: int
    job: str = Field(max_length=120)
    energy: str = Field(max_length=40)
    lead_instrument: str = Field(max_length=40)
    captions: str = Field(max_length=60)


class VideoPlan(BaseModel):
    """The narrative arc. NOT derivable from the beats — it is a separate read.

    Deriving this (hook = first beat, payoff = loudest emphasis, arc from spans)
    would be INVENTING structure the model never declared, which is the one thing
    this schema refuses to do anywhere else. So arm B asks for it, exactly as arm
    A does, and the A/B stays a test of the doctrine rather than of how cleverly
    the transform can guess an arc.
    """
    what_happens: str = Field(max_length=600)
    hook_word_index: int
    payoff_word_index: int
    close_word_index: int
    story_shape: str = Field(max_length=200)
    editorial_vision: str = Field(max_length=600)
    key_moments: List[KeyMoment] = Field(default_factory=list)
    arc_segments: List[ArcSegment] = Field(default_factory=list)
    movements: List[Movement] = Field(default_factory=list)


class BeatMajorPlan(BaseModel):
    """The v2 response shape. Globals stay global; everything timed is a beat.

    THE GLOBALS ARE NOT OPTIONAL, and finding that out cost four paid cells: the
    pipeline REQUIRES audio_denoise, outro, thumbnail_word_index and video_plan
    on every plan, and a beat list without them is rejected as RECIPE_INVALID
    after the model has already done all the work. "Everything timed is a beat"
    was never a licence to drop the untimed contract.
    """
    beats: List[Beat] = Field(default_factory=list)
    caption_style: Optional[str] = Field(default=None, max_length=60)
    aspect_ratio: Optional[str] = Field(default=None, max_length=16)
    video_identity: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=600)
    # Required by the plan contract — see the docstring above.
    audio_denoise: bool = False
    outro: Literal["none", "fade_black", "fade_white"] = "none"
    thumbnail_word_index: int = 0
    video_plan: Optional[VideoPlan] = None


# The families a beat can emit, in flatten order. Named once so the transform,
# the counts and the cert cannot disagree about what "all families" means.
BEAT_FAMILIES = ("cut", "emphasis", "overlay", "broll", "scene", "caption", "place")
# family -> the component-major array it flattens into.
FAMILY_TARGET = {
    "cut": "cut_refinements",
    "emphasis": "emphasis_moments",
    "overlay": "text_overlays",
    "broll": "broll_clips",
    "scene": "generated_scenes",
    "caption": "caption_keywords",          # + caption_position_changes
    "place": "motion_graphics",
}


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


def _missing(obj: Dict[str, Any], family: str):
    """Which required fields this treatment did not supply. Never fabricates."""
    return [k for k in TREATMENT_REQUIRED.get(family, [])
            if obj.get(k) in (None, "", [], {})]


def _empty_contract(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Every array and global the plan contract requires, at their empty value.

    A beat plan that emitted nothing still owes the pipeline a COMPLETE object:
    the validator rejects a missing key, not just a wrong one, and it does so
    after the model has already done all the work.
    """
    for _k in ("motion_graphics", "cut_refinements", "emphasis_moments",
               "text_overlays", "broll_clips", "generated_scenes",
               "caption_keywords", "caption_position_changes", "sound_effects"):
        if not isinstance(plan.get(_k), list):
            plan[_k] = []
    plan.setdefault("audio_denoise", False)
    plan.setdefault("outro", "none")
    plan.setdefault("thumbnail_word_index", 0)
    return plan


def flatten_beats(plan: Dict[str, Any], *, ledger=None,
                  ensure_contract: bool = False,
                  word_times: Dict[int, float] = None) -> Dict[str, Any]:
    """beats[] -> the component-major arrays the render path already consumes.

    Returns the SAME dict, mutated, so every downstream reader is untouched.

    handler.py asserts
        len(motion_graphics_out) + misses == top-level + emphasis + brand
    and derives `top-level` from len(edit_plan["motion_graphics"]). Because this
    transform runs BEFORE that count is taken, the equality holds by
    construction — but the counts are ALSO declared explicitly in
    `v2_counts` so a mismatch is diagnosable rather than merely fatal.

    `ledger` is handler's (_ledger_requested, _ledger_dropped) pair when
    available: a treatment dropped HERE is dropped BY US, and that is exactly
    the distinction the component ledger exists to make.
    """
    beats = plan.get("beats")
    if not isinstance(beats, list):
        # NOT A BEAT PLAN. Two very different situations, and conflating them
        # cost a paid cell: outside arm B this is simply someone else's plan and
        # must be left untouched; INSIDE arm B it means the model returned an
        # object with no beats — which is exactly what the repair re-ask
        # produces, because it is told to "fix caption_keywords" and re-emits a
        # corrected object rather than a whole beat list. Early-returning there
        # left every required array ABSENT, and the plan died on
        # `caption_keywords must be an array, got NoneType` AFTER a full
        # generation. In arm B the contract is guaranteed either way.
        if ensure_contract:
            _empty_contract(plan)
        return plan

    mgs: List[Dict[str, Any]] = []
    cuts: List[Dict[str, Any]] = []
    emphases: List[Dict[str, Any]] = []
    overlays: List[Dict[str, Any]] = []
    brolls: List[Dict[str, Any]] = []
    scenes: List[Dict[str, Any]] = []
    cap_words: List[str] = []
    cap_moves: List[Dict[str, Any]] = []

    counts: Dict[str, int] = {}
    dropped: Dict[str, int] = {}
    per_family: Dict[str, int] = {f: 0 for f in BEAT_FAMILIES}

    def _req(kind, ctype=None):
        if ledger:
            ledger[0](kind, ctype)

    def _drop(kind, ctype, why):
        dropped[kind] = dropped.get(kind, 0) + 1
        if ledger:
            ledger[1](kind, ctype, why)

    # V3 (b): t_start/t_end ARE RESOLVED TO WORD INDICES HERE, and what cannot
    # be resolved is COUNTED rather than vanishing.
    #
    # The previous loop did `continue` on a beat with no usable word_index —
    # silently. A v3 beat reasons in seconds, so a plan can now be entirely
    # well-formed and still land here with no word_index at all; dropping those
    # without a count would report "the model emitted nothing" when the truth is
    # "we discarded everything it emitted". That distinction is pre-registered as
    # `unresolvable beats` and it is the difference between a model finding and
    # one of ours.
    unresolvable = []

    def _resolve_wi(beat):
        """word_index if the model gave one; else the word nearest t_start."""
        try:
            return int(beat.get("word_index"))
        except (TypeError, ValueError):
            pass
        t0 = beat.get("t_start")
        if not isinstance(t0, (int, float)) or not word_times:
            return None
        # NEAREST, not floor: a beat boundary landing 10ms before a word should
        # attach to that word, and floor() would push it onto the previous one.
        return min(word_times, key=lambda i: abs(word_times[i] - float(t0)))

    for b in beats:
        if not isinstance(b, dict):
            continue
        wi = _resolve_wi(b)
        if wi is None:
            unresolvable.append({
                "purpose": b.get("purpose"),
                "t_start": b.get("t_start"),
                "t_end": b.get("t_end"),
                "why": ("no word_index and no t_start" if b.get("t_start") is None
                        else "t_start present but no word_times available"),
            })
            continue

        # ── place -> motion_graphics ────────────────────────────────────────
        for pl in (b.get("place") or []):
            if not isinstance(pl, dict):
                continue
            comp = str(pl.get("component") or "").strip()
            if not comp:
                continue
            _req("motion_graphic", comp)
            ok, props, why = _validate_props(comp, pl.get("props") or {})
            if not ok:
                _drop("motion_graphic", comp, why)
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
            per_family["place"] += 1

        # ── cut -> cut_refinements ──────────────────────────────────────────
        cut = b.get("cut")
        if isinstance(cut, dict):
            _req("cut_refinement")
            miss = _missing(cut, "cut")
            if miss:
                _drop("cut_refinement", None, f"missing_required:{','.join(miss)}")
            else:
                cuts.append({
                    "start_word_index": wi,
                    "end_word_index": int(cut["until_word_index"]),
                    "reason": str(cut["reason"]),
                })
                per_family["cut"] += 1

        # ── emphasis -> emphasis_moments ────────────────────────────────────
        em = b.get("emphasis")
        if isinstance(em, dict):
            _req("emphasis", em.get("type"))
            miss = _missing(em, "emphasis")
            if miss:
                _drop("emphasis", em.get("type"),
                      f"missing_required:{','.join(miss)}")
            else:
                until = em.get("until_word_index")
                try:
                    end = int(until) if until is not None else wi
                except (TypeError, ValueError):
                    end = wi
                entry = {
                    "word_indices": list(range(wi, max(end, wi) + 1)),
                    "type": str(em["type"]),
                    "intensity": str(em["intensity"]),
                    "duration": float(em["duration"]),
                    "viewer_feeling": str(em["viewer_feeling"]),
                    "sound": str(em["sound"]),
                }
                z = em.get("zoom")
                if isinstance(z, dict) and z.get("arc_position") and z.get("type"):
                    entry["zoom_effect"] = {k: v for k, v in z.items() if v is not None}
                emphases.append(entry)
                per_family["emphasis"] += 1

        # ── overlay -> text_overlays ────────────────────────────────────────
        ov = b.get("overlay")
        if isinstance(ov, dict):
            _req("text_overlay", ov.get("variant"))
            miss = _missing(ov, "overlay")
            if miss:
                _drop("text_overlay", ov.get("variant"),
                      f"missing_required:{','.join(miss)}")
            else:
                entry = {"variant": str(ov["variant"]),
                         "start_word_index": wi,
                         "duration_seconds": float(ov["duration_seconds"])}
                for k in ("text", "quote", "attribution", "topText", "bottomText",
                          "position", "why", "notes"):
                    if ov.get(k) not in (None, ""):
                        entry[k] = ov[k]
                overlays.append(entry)
                per_family["overlay"] += 1

        # ── broll -> broll_clips ────────────────────────────────────────────
        br = b.get("broll")
        if isinstance(br, dict):
            _req("broll")
            miss = _missing(br, "broll")
            if miss:
                _drop("broll", None, f"missing_required:{','.join(miss)}")
            else:
                entry = {"keyword": str(br["keyword"]),
                         "start_word_index": wi,
                         "end_word_index": int(br["until_word_index"]),
                         "reason": str(br["reason"])}
                for k in ("entry_transition", "exit_transition"):
                    if br.get(k) not in (None, ""):
                        entry[k] = br[k]
                brolls.append(entry)
                per_family["broll"] += 1

        # ── scene -> generated_scenes (THE WIN CONDITION) ───────────────────
        sc = b.get("scene")
        if isinstance(sc, dict):
            _req("generated_scene", sc.get("scene_type"))
            miss = _missing(sc, "scene")
            if miss:
                _drop("generated_scene", sc.get("scene_type"),
                      f"missing_required:{','.join(miss)}")
            else:
                entry = {"background": str(sc["background"]),
                         "subject": str(sc["subject"]),
                         "motion": str(sc["motion"]),
                         "start_word_index": wi,
                         "end_word_index": int(sc["until_word_index"]),
                         "anchor": str(sc["anchor"])}
                for k in ("scene_type", "stat", "text_layers", "land_word_index",
                          "duration_seconds"):
                    if sc.get(k) not in (None, "", [], {}):
                        entry[k] = sc[k]
                scenes.append(entry)
                per_family["scene"] += 1

        # ── caption -> caption_keywords + caption_position_changes ──────────
        cap = b.get("caption")
        if isinstance(cap, dict):
            kws = [str(k) for k in (cap.get("keywords") or []) if str(k).strip()]
            if kws:
                _req("caption_keyword")
                cap_words.extend(kws)
                per_family["caption"] += len(kws)
            if cap.get("position"):
                _req("caption_position")
                cap_moves.append({"word_index": wi, "position": str(cap["position"])})
                per_family["caption"] += 1

    plan["motion_graphics"] = mgs
    # THE UNTIMED CONTRACT. These are not derived from beats and must survive
    # the flatten: the pipeline rejects a plan without them (RECIPE_INVALID),
    # and it does so AFTER the model has done all the work.
    plan.setdefault("audio_denoise", False)
    plan.setdefault("outro", "none")
    plan.setdefault("thumbnail_word_index", 0)
    # sound_effects: arm A does not declare it either — the validator only
    # requires the KEY to be an array. An empty list is the honest value; the
    # sound intent itself rides emphasis_moments[].sound, exactly as in arm A.
    if not isinstance(plan.get("sound_effects"), list):
        plan["sound_effects"] = []
    plan["cut_refinements"] = cuts
    plan["emphasis_moments"] = emphases
    plan["text_overlays"] = overlays
    plan["broll_clips"] = brolls
    plan["generated_scenes"] = scenes
    # De-duplicated, order preserved: the same word emphasised at two beats is
    # one caption keyword, and a duplicate would double-count the density read.
    plan["caption_keywords"] = list(dict.fromkeys(cap_words))
    plan["caption_position_changes"] = cap_moves

    # DECLARED, not inferred. The equality assertion at the render seam is an
    # equality; when it trips, this is the record of what the transform believed
    # it built — now for every family, not just the graphics.
    # NOT UNDERSCORE-PREFIXED, and that is load-bearing. handler sanitises plans
    # with `k.startswith("_")` filters, so `_v2_counts` was STRIPPED before the
    # plan ever reached a reader — the metrics were computed, certified, proven
    # end to end, and then deleted in transit. A leading underscore in this
    # codebase means "internal, safe to drop"; these are the pre-registered
    # measurements and they must survive.
    plan["v2_counts"] = {
        "beats": len(beats),
        # PRE-REGISTERED METRIC. A beat we could not anchor is OUR drop, not the
        # model's silence, and reporting zero here without the denominator would
        # repeat the reading that made "0/779 scenes" unreadable for weeks.
        "beats_unresolvable": len(unresolvable),
        "unresolvable_detail": unresolvable[:20],
        "purpose_distribution": _purpose_distribution(beats),
        "beat_durations_s": _beat_durations(beats),
        "placements_requested": sum(counts.values()) + sum(dropped.values()),
        "placements_emitted": sum(counts.values()),
        "dropped_by_us": dropped,
        "by_component": counts,
        "by_family": dict(per_family),
        "emitted_by_family": {
            "cut_refinements": len(cuts),
            "emphasis_moments": len(emphases),
            "text_overlays": len(overlays),
            "broll_clips": len(brolls),
            "generated_scenes": len(scenes),
            "caption_keywords": len(plan["caption_keywords"]),
            "caption_position_changes": len(cap_moves),
            "motion_graphics": len(mgs),
        },
        # The equality's own left-hand side, stated where a human can read it.
        "motion_graphics_len": len(mgs),
    }
    return plan


def _purpose_distribution(beats) -> Dict[str, int]:
    """Purpose counts. A near-constant distribution means the enum carries no
    information and v3 has reduced to v2 with extra fields — pre-registered as
    reading (2) of a worse result."""
    out: Dict[str, int] = {}
    for b in beats:
        if isinstance(b, dict):
            k = str(b.get("purpose") or "(absent)")
            out[k] = out.get(k, 0) + 1
    return out


def _beat_durations(beats) -> list:
    """t_end - t_start per beat. Uniform durations mean the model segmented
    mechanically rather than reading the video — reading (4)."""
    out = []
    for b in beats:
        if not isinstance(b, dict):
            continue
        a, z = b.get("t_start"), b.get("t_end")
        if isinstance(a, (int, float)) and isinstance(z, (int, float)) and z > a:
            out.append(round(float(z) - float(a), 2))
    return out


def _beat_moves(b: Dict[str, Any]) -> int:
    """How many MOVING SAMPLES this beat contributes (§4's unit)."""
    if not isinstance(b, dict):
        return 0
    n = len(b.get("place") or [])
    for f in ("cut", "emphasis", "overlay", "broll", "scene"):
        if isinstance(b.get(f), dict):
            n += 1
    cap = b.get("caption")
    if isinstance(cap, dict):
        n += len([k for k in (cap.get("keywords") or []) if str(k).strip()])
        if cap.get("position"):
            n += 1
    return n


def density_of(plan: Dict[str, Any], duration_s: float) -> Dict[str, Any]:
    """Motion density — and now it IS comparable to §4's 3.5/sec.

    THE UNIT ERROR THIS AVOIDS, caught on the exemplars before the A/B ran: §4's
    ~3.5 moving samples/sec counts EVERY motion kind together — cuts, caption
    beats, graphics, camera moves. While the schema could only express component
    placements, those were ONE of those four, and reporting REF-2's 6 placements
    in 43s (0.14/sec) against a 3.5 target read as a catastrophic miss when the
    two numbers measured different things.

    Now that a beat carries all seven treatments, the same plan yields BOTH
    numbers honestly: `placements_per_s` for the like-for-like exemplar
    comparison, and `moves_per_s` — every motion kind — which is the number §4's
    3.5 target is actually about. They are reported separately and labelled,
    because collapsing them is the error this docstring exists to prevent.
    """
    beats = [b for b in (plan.get("beats") or []) if isinstance(b, dict)]
    placed = sum(len(b.get("place") or []) for b in beats)
    moves = sum(_beat_moves(b) for b in beats)
    d = max(float(duration_s or 0.0), 0.001)
    return {
        "placements": placed,
        "placements_per_s": round(placed / d, 3),
        # measured off the exemplars: REF-1 6/40s, REF-2 6/43s
        "reference_placements_per_s": 0.14,
        "moves": moves,
        "moves_per_s": round(moves / d, 3),
        "reference_moves_per_s": 3.5,     # §4, all motion kinds together
        "beats_total": len(beats),
        "beats_empty": sum(1 for b in beats if _beat_moves(b) == 0),
        "note": "placements_per_s is components only; moves_per_s counts every "
                "motion kind and is the one comparable to §4's 3.5/sec",
    }


def stillness_violations(plan: Dict[str, Any], word_times: Dict[int, float],
                         ceiling_s: float = 3.5) -> List[Dict[str, Any]]:
    """§4: no still stretch longer than 3.5s, measured between MOVING beats.

    Needs the word-index -> seconds map, because beats are word-anchored (there
    is one clock in this pipeline and it is the word list). Returns the gaps
    that exceed the ceiling, so a violation names its own window.

    A beat counts as moving if it carries ANY treatment — a cut or a caption beat
    breaks stillness exactly as a graphic does. Counting only placements
    (as this did while placements were all that existed) reports stillness that
    the finished video does not have.
    """
    placed = sorted(int(b["word_index"]) for b in (plan.get("beats") or [])
                    if isinstance(b, dict) and _beat_moves(b) > 0
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
