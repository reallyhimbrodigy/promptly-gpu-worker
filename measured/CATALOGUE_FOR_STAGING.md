# The catalogue, for staging into the live project
# Builder 2 · 2026-09-23 · lane/agentic-builder2

## The count does not reconcile, and here is exactly where

Zac's live menu carries SIX graphics: CaptionMatch, EmojiCard, PlainText,
QuoteCard, Stamp, TornPaper. The instruction was "your catalogue lists 22, post
the other 16", which is 22 minus 6 — and that subtraction does not apply,
because **none of those six are in the 22**. Five of them are not registry
components at all:

  * CaptionMatch, EmojiCard, PlainText, QuoteCard, TornPaper are **FRAME
    COMPOSITIONS**. They have no directory under `src/motion-graphics`, no
    `.jsx` body in `ported_mg/`, and no entry in `chatcut_registry_baked.json`.
    They are not motion graphics that happen to be unregistered; they are a
    different kind of thing, and there is nothing to stage for them.
  * **Stamp** is the one overlap: a registered motion graphic that is already
    in the live project.

So the honest numbers are:

      28   components in chatcut_registry_baked.json
       1   of them in the live project (Stamp)
      27   registered and NOT in the live project
      22   of those 27 carry a written one-line description (the catalogue)
       5   of those 27 do not (PillCluster, RankedList, Reticle, StatCard,
           StickyNotes — the live-menu motion graphics, which have measured
           natural boxes instead)

**27 is the number to stage, not 16.** The two tables below are split that way.
B1's 28 is the registry count, which agrees with this exactly: 22 + 5 + Stamp.

`natural box` is `y` only where a box was MEASURED on 2026-09-23. Those six
numbers are STARTING POINTS for B1's two-box search, ruled so by Zac — never
verdicts. Every `n` below means no measurement exists, not that the component
has no box.

## A — the 22 with written one-line descriptions

| component        | flattened | one-line | natural box | one-line description |
|------------------|-----------|----------|-------------|-----------------------------------------------------------------|
| AnnotationArrow  | n         | y        | n           | a hand-drawn arrow for pointing at a detail on screen |
| BarRace          | y         | y        | n           | bars that grow and reorder for comparing numbers over time |
| ChatThread       | y         | y        | n           | a phone message thread for conversations, replies and receipts |
| DropBanner       | y         | y        | n           | a banner of short points for feature lists and announcements |
| DropCard         | y         | y        | n           | a card of titled points for launches, drops and release notes |
| EditorialQuote   | n         | y        | n           | a magazine-style pull quote for statements worth setting apart |
| EndCard          | n         | y        | n           | a closing card for sign-offs, handles and calls to action |
| IMessageBubble   | n         | y        | n           | a single blue message bubble for a text worth showing |
| InstagramComment | n         | y        | n           | one comment with a handle for reactions and social proof |
| MouseDrag        | n         | y        | n           | a cursor that moves and clicks for showing a click or a drag |
| NamePlate        | n         | y        | n           | a compact name tag for labelling a person, place or object |
| Notification     | n         | y        | n           | a phone notification card for alerts, sales and messages |
| PillMarquee      | y         | y        | n           | a scrolling row of pills for features, benefits and tags |
| ProgressBar      | n         | y        | n           | a bar filling toward a total for progress, goals and targets |
| PullQuote        | y         | y        | n           | a large quote with a lit keyword for a line worth dwelling on |
| RecordingFrame   | y         | y        | n           | a recording overlay with corner readouts for screen captures |
| SectionDivider   | n         | y        | n           | a full-width title card for chapters and section breaks |
| StepDivider      | n         | y        | n           | a numbered step marker for tutorials, recipes and how-tos |
| TikTokComment    | n         | y        | n           | one comment in TikTok's style for reactions and replies |
| Timeline         | y         | y        | n           | titled steps down the frame for processes, stories and roadmaps |
| TimelineRoadmap  | y         | y        | n           | a compact step list for plans, roadmaps and sequences |
| TweetBubble      | y         | y        | n           | a tweet card with engagement counts for quotes and reactions |

## B — the 5 registered without a catalogue line

These are the live-menu motion graphics. They were measured rather than
described, so the missing column is the opposite one from table A.

| component        | flattened | one-line | natural box | one-line description |
|------------------|-----------|----------|-------------|---|
| PillCluster      | y         | n        | y           | — |
| RankedList       | y         | n        | y           | — |
| Reticle          | n         | n        | y           | — |
| Stamp            | n         | n        | y           | — |
| StatCard         | n         | n        | y           | — |
| StickyNotes      | y         | n        | y           | — |

## What `flattened` means

`y` = every array or object the component reads is now numbered scalar
properties, so a placement can set the content through `propertyOverrides`.
`n` = the component has no structured content to flatten (a single headline, a
number, a label), NOT that it has baked copy left — `smoke_baked_copy` reads a
ceiling of zero over all 28, and `smoke_default_text` now holds the other half
of that ceiling: a flattened content slot may not carry a DEFAULT either,
because the registered default IS the value on every placement that does not
override it.

TweetBubble moved from `n` to `y` on 2026-09-23. Its `stats` was the last baked
object in the registry and the one the copy survey could not see: the four
values are NUMBERS, and `words()` needs two letters to call something copy. So
every TweetBubble ever placed drew 128 / 412 / 1.2K / 98K under a check
correctly reporting zero. A count is content too.
