# The card catalogue is two wide, not thirty-one — what it would take

Zac, 2026-09-11: *"derive_card_type can only ever return StatCard or PullQuote.
Zac ruled full component parity and watched all of them; the pipeline can reach
two. Report what it would take to make the other 27 derivable — and whether the
25-type prop table, still never exercised, is the thing that unlocks it."*

**Answer: the prop table unlocks 12 of them and is irrelevant to 7. The 7 are
one field away, and the field is not a component name.**

## The census

31 types in `VALID_MG_TYPES`; `derive_card_type` can return **2**.

| group | n | what the required props need | reachable today |
|---|---|---|---|
| **A — one text field** | 8 | `title` / `text` / `label`, nothing else | 1 (PullQuote) |
| **B — structured content** | 13 | a list, or two-plus fields | 1 (StatCard) |
| **C — not language-derivable** | 8 | coordinates, platform metadata, or no prop spec at all | 0 |
| **D — brand-only** | 2 | the pipeline builds them | n/a, correctly excluded |

**Group A** — DropBanner, DropCard, EditorialQuote, MouseDrag, PullQuote,
SectionDivider, Stamp, StepDivider. Every one takes a single phrase. **The
information to fill them already arrives: it is `card_hero`, the same field
that derives PullQuote today.** The prop table has nothing to do with these.

**Group B** — BarRace, ChatThread, Notification, PillCluster, PillMarquee,
RankedList, RecordingFrame, Reticle, StatCard, StickyNotes, Timeline,
TimelineRoadmap, TweetBubble. These need `messages`, `notifications`, `notes`,
`items`, `pills`, or several fields at once. StatCard is reachable only because
`card_label` supplies its second field. **This is what `card_props` is for, and
`card_props` has never been exercised — every card ever built came through the
`card_hero` shorthand.** So yes: the prop table is the unlock here, for 12
components.

**Group C** — AnnotationArrow needs `start`/`end` coordinates. IMessageBubble,
InstagramComment and TikTokComment need platform, username and timestamp
metadata that does not exist in a UGC beat. DeviceMockup, EmojiCard,
EvidenceCard and ProgressBar have **no prop spec at all** and are pinned in
`MG_PROPS_UNDERIVABLE`. Four of these are also **undocumented in the catalogue**
(DeviceMockup, EmojiCard, EvidenceCard, plus the two brand-only), so nothing
tells the agent they exist or what they claim.

## What blocks group A, and it is not the prop table

`derive_card_type` has no rule to CHOOSE between eight components that all take
one phrase. It resolves the shape of the hero — a figure wants StatCard, a
phrase wants a phrase card — and then has to pick one phrase card, so it picks
the only one it was told about.

**THE CATALOGUE ALREADY ANSWERS THIS AND THE AGENT HAS NEVER SEEN IT.**
`knowledge/05_motion_graphics.md` is organised under eight condition headings,
and every documented component sits under the question it answers:

| condition | group-A components under it |
|---|---|
| WHEN A NUMBER LANDS | — (StatCard, group B) |
| WHEN STEPS OR ITEMS ARE ENUMERATED | DropBanner, DropCard |
| WHEN SOMETHING IS NAMED OR REVEALED | PullQuote |
| WHEN SOCIAL PROOF OR A MESSAGE IS QUOTED | EditorialQuote |
| WHEN THE SCREEN OR APP IS THE SUBJECT | MouseDrag |
| WHEN A CLAIM GETS A VERDICT OR STAMP | Stamp |
| WHEN TIME OR SEQUENCE IS THE STORY | SectionDivider, StepDivider |
| WHEN A REGION OF THE FRAME NEEDS POINTING AT | — (group C) |

Each group-A component sits under a **different** condition. The discriminator
is not taste anyone has to invent — it is which question the beat answers, and
the catalogue has stated it for months in a document `read_knowledge` has been
called **zero** times on.

**Third instance of that class.** The overlay rule that stopped talking_head
subtitling itself was in `04_text_overlays.md`. The `card_props` shape that cost
three rounds of zero cards was "in the shape its catalogue entry shows". This is
the same: a rule in a document the agent does not open is indistinguishable from
a rule nobody wrote.

`mg_conditions()` now extracts that mapping from the catalogue rather than
hand-copying it, so a catalogue edit cannot leave it behind — the standing rule
after the hand-copied asset tables. It returns MEASURED / ABSENT / FAILED, and
ABSENT fires if the WHEN headings ever disappear, because a silent `{}` would
read as "no conditions" rather than "the source changed shape".

## What it would take, in order of cost

1. **Group A, 7 components: ONE field on the ruling — the CONDITION, not the
   component.** Eight conditions, each already carrying its own sentence, is a
   smaller and more answerable choice than 29 bare names — and the 29-name enum
   is exactly what failed: *a bare enum is a list of words*, and round 42 read
   "1 distinct of 29 selectable, StatCard=4" because the cached prefix named
   StatCard and nothing else. `derive_card_type` then maps condition + hero
   shape to a component, which keeps the derivation in the harness where it can
   be checked. **This is a schema addition to a ruling surface and needs Zac's
   go before I add it.**
2. **Group B, 12 components: `card_props` has to be exercised.** The prop table
   is generated into the schema already; what has never happened is an agent
   filling it. It needs the shape shown where the ruling is made — the *when we
   advertise a shape, the acceptor must take the shape we advertised* rule — and
   it needs a reason to reach past the shorthand, which today is strictly
   easier and always works.
3. **Group C: not language-derivable.** Four have no prop spec, four are
   undocumented, one needs coordinates, three need platform metadata. Any of
   these is a new signal, not a selection rule.

## The number that is not the argument

The whole authoring surface costs $0.00092 a run (see `AUTHORING_VERDICT.md`).
At Haiku's cache rate **prefix size is nearly free and wall clock is where the
money is** — so widening the catalogue is not a cost question in either
direction. It is a quality question, and the evidence that it matters is that
Zac ruled full component parity and watched all of them while the pipeline can
reach two.
