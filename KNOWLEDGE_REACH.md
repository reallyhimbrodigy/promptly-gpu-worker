# Is the knowledge wired properly? — 77 claims, 8 reachable

Zac asked twice. The answer is not three rules.

**77 structural claims across 14 documents. 8 reachable at ruling time — and
all 8 were wired today.** Before 2026-09-11 the number was **zero**.

The documents are readable only through `read_knowledge`, and `read_knowledge`
has been called **0 times in 30 runs**. So every structural claim in the corpus
has been invisible at the moment the agent rules. Measured by
`knowledge_reach()`, which derives it from the documents and the agent's own
surface rather than from a list anyone maintains.

## The three found by accident, each after it had cost something

| document | claim | what it cost |
|---|---|---|
| `04_text_overlays` | "the transcript already lives in the captions… rewrite it as a label or skip it" | talking_head subtitled itself for four rounds |
| `05_motion_graphics` | "in the shape its catalogue entry shows" | three rounds of zero cards |
| `05_motion_graphics` | the eight `WHEN …` condition headings | a 31-type catalogue read two wide |

Three found by damage is not a sampling method. This is the census.

## NOT EVERYTHING HERE SHOULD BE WIRED

That is the point of classifying rather than counting, and it is the first
thing a reader of the 10% figure would get wrong.

**GRADING-ONLY — must stay out of the prompt.** `13_placement_findings` and
`14_card_text_placement_rules` are measured RATES: *"77% of cards and 83% of
text placements share their beat"*, *"Card almost never runs alone: 39 of 40
(97.5%)"*, *"Text is the default, and its absence is the decision"*. The
standing law is that **the density rates GRADE; they never instruct.** Wiring
these is the density-rubric mistake with a bigger corpus behind it — and one
rate already survived a careful removal once, because prose that DESCRIBES a
rate reads as harmless beside a schema field that DEMANDS one.

**HARNESS-OWNED — already enforced, and prose would be a second copy.**
`15_ffmpeg_placement_recipes` (the harness builds every filtergraph),
`01_cut_pass` stages 0-4 (the harness segments and the agent rules per beat),
`09_seam_treatments` (the harness picks transitions from measured room). A rule
the harness enforces does not need to reach the agent; a SECOND statement of it
is a drift surface.

**INSTRUCTABLE — craft the agent decides and cannot see.** This is the live
list, per field the agent actually fills:

| field | document | claims it cannot see |
|---|---|---|
| `zoom_arc` | `06_emphasis_zoom` | 11 — "Peaks must differ in WEIGHT, not just type", "Zoom personality by arc position", "Count follows the footage" |
| `cutaway` | `08_broll` | 6 — "B-roll earns its place by EXTENDING the moment", "A cutaway also belongs by its LOOK", and the test that decides between modes |
| `text_content` | `04_text_overlays` | 2 — "ONE COMPONENT, TWO HOMES, route it never duplicate it", and that position is "top" on centered talking-head |
| `caption_style` | `03_captions` | 2 — the pipeline owns caption position during MG windows; when a graphic becomes the text, the captions rest |
| `card_*` | `05_motion_graphics` | 5 remaining — the three-band base layout, "Author every word of on-screen text in the speaker's own voice", the special value strings |
| `sfx_name` | `07_sound_effects` | 1 — "The scenarios live in the source" |
| the whole spec | `00_job_and_arc` | 14 — identity, "The spine is everything", "Specificity over genre", "The camera's moves are emotional vocabulary" |
| thumbnail | `11_thumbnail` | 5 — a surface this editor does not have; correctly unreachable |

**`06_emphasis_zoom` is the largest instructable gap: 11 claims about a field
the agent fills on every beat.** `zoom_arc` is answered on every ruling and not
one word of the zoom craft reaches it.

## What the count is and is not

10% is not a target. Wiring all 77 would be worse than wiring none: the
grading-only ones would corrupt the instrument that judges us, the
harness-owned ones would become a second source of truth, and the thumbnail
document describes a surface that does not exist here.

The honest number is **the instructable gap: 27 claims across five fields the
agent fills**, none of which it can see. Every one is a candidate, and each
needs the same treatment the three accidental finds got — put it where the
choice is made, in the field description or the beats brief, never in a
document the agent must spend a turn to open.

**The cost is not the obstacle.** Measured: the whole authoring surface is 920
tokens and $0.00092 a run; at Haiku's cache rate prefix size is nearly free and
wall clock is where the money is. 27 claims is a few hundred tokens.

## The ratchet

`smoke_knowledge_reach` fails if the reachable count FALLS. It cannot be a
target in the other direction, because three of these documents must stay
unreachable and a check that pushed the number up would be arguing for exactly
the wiring this file says not to do.
