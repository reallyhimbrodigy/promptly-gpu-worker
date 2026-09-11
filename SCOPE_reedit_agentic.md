# Re-edit in the agentic path — SCOPE, not a build

Zac's requirement: **a prior plan plus an instruction producing a surgical
modification, not a re-plan.** This document says what exists, what is missing,
and what would make the difference checkable. Nothing is built.

Everything under OBSERVED is read from `agentic_editor_app.py` on
`lane/duration-producer` with line numbers. Everything else is labelled.

## OBSERVED — what the agentic path has today

**A scope vocabulary that already fits.** `SPEC_MODES` (1197) is
`("full_edit", "targeted_change", "question", "unsupported")`, and
`normalize_spec` (1231) refuses a `targeted_change` that does not name the
families it may touch — *"an unbounded 'targeted' change is a full edit wearing
a smaller name"*. The agent declares it through the `set_spec` tool (1799) at
step 0.

**One enforcement site.** `execute_plan` (8465) drops any family not in
`spec.families` and ledgers `not_asked_for`. The comment there is already the
right instinct: *"a targeted_change that also ships four new overlays looks like
a good edit to anyone not reading the manifest against the request."*

**A placement manifest.** `led["placements"]` entries (8474, 8480) are
`{type, family, t_start, method, declared_by, content}`.

## OBSERVED — the four things that make re-edit impossible today

**1. There is no prior plan, because nothing is loaded.** `edit()`'s parameters
are `source_key, brief, src_url, out_url, out_key, max_iters, use_knowledge,
effort, model, route_models, cap_exec_effort, cheap_model, exec_model,
recent_styles`. No parameter can carry a previous plan. Every run re-downloads,
re-transcribes, re-derives beats and re-rules from scratch.

**2. There is no prior plan, because nothing is persisted.** The only thing that
leaves the container is `/work/out.mp4`, PUT to `out_url` (10134). The result
dict — which carries the whole ledger — is RETURNED to `main()`, the local
entrypoint, and printed. **Nothing writes it anywhere durable.** A second run
has no way to read the first.

**3. Placements are not addressable.** No id, and the only positional key is
`t_start` in OUTPUT seconds. Output time is a function of the cut, so the moment
a re-edit changes one cut, every downstream placement's address moves. An
instruction naming "the caption at 0:12" cannot be resolved to the same element
twice.

**4. `spec.beats` are ints, and beat indices are derived per run.** Beats come
from `segment_beats` / `segment_beats_visual` then `subdivide_beats`. Round 48
moved a fixture from 8 beats to 9 (`beats] 8 -> 9`). **Nothing asserts beat
indices are stable across code versions**, so an int index is not a durable
address either.

## THE FINDING

**`targeted_change` today means "run a fresh edit but only touch these
families". That is a re-plan with a narrower scope, which is exactly the thing
Zac's requirement distinguishes itself from.** The vocabulary for a surgical
change exists; the thing to be surgical ON does not.

INFERENCE, stated as such: this is the same shape as the defect already on
record in the non-agentic pipeline — `tweak -> render_only` never folded
`change_request` into the vibe, so paid re-edits no-opped. A re-edit rail that
exists in name and does not carry the change. The agentic path would reproduce
it by a different route: the change would be carried, but everything ELSE would
be re-derived, so the user's untouched work would silently move.

## WHAT RE-EDIT REQUIRES, in dependency order

**A. Persist the plan.** The ledger, or a plan projection of it, written where a
second run can read it. Decision needed: alongside the output object, or in the
caller's DB. **This is the frontend's domain as much as mine** — I own what the
worker emits, not where it is stored.

**B. Anchor to the SOURCE clock, not the output clock.** Source time does not
move when a cut changes; output time does. A placement addressed as
`(source_t, family, ordinal-within-beat)` survives a re-cut. Beats are already
derived from source time (`t_start`/`t_end` on the beat records), so the anchor
exists — it is simply not what the manifest records.

**C. Give every placement a stable id at declaration.** Cheapest durable form: a
hash of `(source_t, family, content)` assigned where the placement is declared,
carried into the manifest, and echoed in the render. An ordinal alone is not
enough — inserting one placement renumbers its neighbours.

**D. An instruction -> target resolver.** "Make that caption bigger", "drop the
zoom on the opening line", "same but no sound effects" must resolve to plan
elements. This is a judgement, so the PLAN MUST BE IN THE PROMPT — which is
affordable: the manifest is small, and it goes in the cached prefix.

**E. A preservation guarantee, and it is the whole point.** Everything not named
by the instruction must come back BYTE-IDENTICAL.

## THE CHECK THAT MAKES IT SURGICAL RATHER THAN A RE-PLAN

We can already prove this, and it is the strongest check available anywhere in
the pipeline: **renders are byte-identical on a fixed plan across any CPU**, since
the x264 thread count is pinned (`_X264_ENCODE_THREADS=48`). Byte-identity is
the cert bar and any difference on a fixed plan is a DEFECT, not variance.

So:

    RE-EDIT WITH A NO-OP INSTRUCTION MUST PRODUCE A BYTE-IDENTICAL FILE.

That is falsifiable, cheap, and it fails loudly the moment the path is
re-planning rather than modifying. It is the re-edit equivalent of the
`both_on` arm proving a wire before any removal is trusted.

Second check, for a real instruction: **every plan element NOT named by the
instruction is unchanged in the new plan**, compared by id, and the diff of the
manifests is exactly the elements the instruction named. A re-edit that produces
a correct-looking output while silently re-deriving six untouched placements is
the failure this catches, and it is invisible in the video.

## THE PLAN ALREADY EXISTS — DESIGN, after Zac's rulings

Rulings taken: a re-edit MAY change the cut, so source-clock anchoring is
mandatory; the plan lives server-side keyed by job id, with `edit_recipe` on
`video_jobs` as the precedent; an ambiguous instruction ASKS, and is counted
either way.

**OBSERVED: `execute_plan` takes NO ARGUMENTS** — `"input_schema": {"properties":
{}, "required": []}` (1735). It runs "from your verdicts", which live in harness
state as `led["beat_verdicts"]` (8984), over `led["beats"]` (8983). Its docstring
is already explicit about the split: *the agent rules; the pipeline executes*,
and what stays with the agent is treatment per beat, cut/keep per beat, and
text_content — *"the words do not exist until written"*.

**So the plan is the beat verdicts, and it is already the right size.** Nothing
new has to be invented to have a plan; it has to be given a durable address and
written down.

### The one change that makes it durable

`beat_verdicts` are keyed by beat INDEX, and beat indices are derived per run —
round 48 moved a fixture 8 -> 9. **Persist each verdict keyed by its beat's
SOURCE TIME SPAN**, resolved at write time from `led["beats"]`:

    {"src_t0": 4.12, "src_t1": 7.80, "treatment": [...], "cut": "keep",
     "text_content": "...", "card_hero": "...", "zoom_arc": "...",
     "cutaway_from_s": 12.4, "id": <hash of (src_t0, src_t1, family, content)>}

Source spans survive everything a re-edit can do. Re-segmentation moves indices
and does not move the moment an editor ruled on; a changed cut moves OUTPUT time
and does not move source time. A persisted verdict re-maps onto a fresh beat
list by TIME OVERLAP, which is well-defined even when subdivision changes.

That single re-keying satisfies both of Zac's ordered items: it is the
persistence shape AND the addressable id, because the id is derived from the
anchor rather than bolted on beside it.

### What re-edit then does

    load     the persisted verdicts for the job id
    resolve  the instruction against them — the plan goes in the prompt, which
             is affordable and belongs in the cached prefix
    modify   only the verdicts the instruction names
    execute  execute_plan on the merged set, unchanged

The agent loop is not re-entered for untouched beats. That is what makes it a
modification rather than a re-plan, and it is why the byte-identity check is the
right proof: identical verdicts in, identical bytes out.

### The precondition, stated once more because it gates the proof

Byte-identity cannot be claimed until the x264 pin lands — 13 of 13 encodes in
this path are unpinned, so today two runs of an identical plan need not agree.
Ordered by Zac: pin first, then persistence, then ids, then the proof on real
traffic.

### Per-site ruling for the pin, prepared so landing it is mechanical

The test is whether the encoded bytes ever reach the delivered file.

    6705, 6708  build_cut               source -> cut.mp4 -> capped.mp4
    6873        build_overlays          overlay intermediate
    7058        render_components       -> out.mp4                DELIVERED
    7093, 7099  run_ffmpeg_from_recipe  source -> cut.mp4
    7588, 7753, 7922, 7982, 8062, 8307  execute_plan stage chain
                                        (zoomed / transitioned / carded / reel)
    8656        build_zoom              zoom intermediate

`cut.mp4`, `reel.mov` and `out.mp4` are confirmed by direct `-i` reference; the
`execute_plan` stages hand their output to the next stage through a variable, so
they are read as a chain rather than by literal filename. PROVISIONAL RULING:
**all 13 feed the delivered file and none is an analysed-and-discarded proxy**,
so all 13 take the pin. The chain sites get confirmed at the moment the pin
lands rather than asserted now.

## WHAT I WOULD MEASURE, before believing any of it

- Re-edit wall time and cost against a full edit on the same fixture, BY ROUTE.
  A surgical path that re-transcribes and re-derives beats has not saved
  anything; the saving is the claim, so it gets a denominator.
- How many instructions resolve to a target at all. An instruction the resolver
  cannot place is a REFUSAL, not a silent full edit — and it must be counted,
  the way `unsupported_class` is counted, because the count is the demand signal.

## DECISIONS I NEED, and cannot make alone

1. **Where the plan is persisted** — worker-side beside the output, or
   caller-side in the DB. Frontend owns client and DB truth.
2. **Whether a re-edit may change the cut at all.** If it may, every downstream
   output-time address moves and B becomes mandatory rather than merely correct.
   If it may not, "tighten the pacing" is unsupported and must say so.
3. **What happens when the instruction is ambiguous** — refuse and name it, or
   ask. This lane's standing law is fail loudly to us, never to the user.

## NOT IN THIS SCOPE

Multi-upload. It is the other stated requirement and it is a different problem —
several sources, one timeline, and a cutaway family that can already only draw
from the user's own material. Scoped separately.
