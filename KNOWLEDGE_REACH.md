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


---

# ADDENDUM 2026-09-11 — the wiring, and a correction to this file's own count

## My "27 instructable" was over-counted, and reading the bodies is why

The first pass mapped each DOCUMENT to the field it governs and counted its
headings. That is a mapping, not an audit: it never asked whether each claim
describes a field **this lane actually exposes**. Reading the bodies:

| document | claimed instructable | actually applicable here | why the rest are not |
|---|---|---|---|
| `06_emphasis_zoom` | 11 | **4** | the other 7 describe `durationMs`, `scale`, `originX/Y`, `key_moments` and per-clip splitting — fields this app does not expose — or are harness-owned back-timing and spacing |
| `08_broll` | 6 | **0 on this lane** | **`cutaway` is not in this lane's treatment enum** (card, text, sfx, zoom, transition, none). Builder-1 built the family and it is not merged here. Wiring a field that does not exist is offering a capability that cannot fire |
| `04_text_overlays` | 2 | **0** | position is harness-chosen (`build_overlays` defaults to top and the agent has no position field); the two-homes routing choice does not exist in this lane's shape |
| `03_captions` | 2 | **0** | `caption_style` is not a field here at all — the harness picks it |
| `05_motion_graphics` | 5 remaining | **3** | the three-band layout is positioning the harness owns; "reach for the choice that reads as inevitable" is framing, not a rule |
| `07_sound_effects` | 1 | **0** | "pick by ROLE from the table" is already in the `sfx_name` description |
| `00_job_and_arc` | 14 | **not assessed** | identity and arc framing; needs Zac's read on which are craft and which are the old pipeline's voice |

**So the honest instructable count for fields this lane exposes is 7, not 27** —
4 zoom, 3 motion-graphics — and **five were wired today.** The remaining two
are the three-band layout and the inevitability framing, both judgement calls
rather than mechanical gaps.

That correction stays here rather than replacing the original number, because
the original number is the evidence that a document-to-field mapping is not an
audit.

## What was wired, and how it is counted

`knowledge_reach` matches a document's HEADING against the agent's surface. It
is mechanical and cannot drift — and it **understates** reach, because wiring a
claim's substance without copying its heading does not move the number. Four
claims were wired and the heading count stayed at 8.

So every wired claim now carries a marker naming its source document, and
`wired_claims()` counts the markers. The marker is IN the text the agent reads,
so a claim cannot be counted as wired unless its text is actually on the
surface — not a hand-kept list, and not fuzzy matching.

| field | claim | source |
|---|---|---|
| `zoom_arc` | the arc-position JOBS — hook = GRIP, mid_peak = PUNCTUATION, payoff = COMMITMENT, close = CALLBACK — extracted as bullets at import, with `build` and `breather` named as having NO guidance because the catalogue predates this enum | `06_emphasis_zoom` |
| `why` (both surfaces) | "name the specific moment that asked for it, in twelve words or fewer" | `05_motion_graphics` |
| `card_hero` | author it in the speaker's own voice | `05_motion_graphics` |
| `card_props` | `timestamp`, `wordcount`, `wpm` are computed live rather than typed | `05_motion_graphics` |
| `card_condition` | the eight WHEN conditions | `05_motion_graphics` |

**`rule_all_beats`' `why` field had NO DESCRIPTION AT ALL** — on the surface
called every single run, while `beat_verdict`'s repair path had one. Both now
read one hoisted constant, because a field on one ruling surface and not the
other is now the fourth instance in this lane after `purpose`,
`card_condition` and this.

## What belongs to Builder-1

`08_broll`'s six claims are ready to wire and cannot be wired here. Two of them
matter most and neither is in any document the agent can reach:

- **"B-roll earns its place by EXTENDING the moment"** — name what the frame
  gives the viewer beyond what the words and the speaker's face already
  deliver. When the frame and the line carry the same single fact, the speaker
  and the captions own that beat.
- **The next-footage rule, which is in NO document at all.** Builder-1's guard
  rejects a cutaway whose window sits in `[beat end, beat end + hold + 1s]`,
  and it fired 2 of 2 on round 58 — both times on a cutaway the agent proposed
  in good faith, because nothing told it the rule existed. A mechanically
  enforced rule the agent is never told is a refusal it will keep earning.
