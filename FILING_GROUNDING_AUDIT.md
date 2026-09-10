# What the agent sees of Zac's examples at ruling time: nothing

Answered before building, as asked.

## The question

Not the derived rates — the actual reference edits, their placements, and why
each landed where it did.

## The answer, measured

**`reference_beats` appears in `agentic_editor_app.py` exactly once, in a
comment**, recording where the rates were mined from. No code reads it. No
knowledge file quotes a single reference `read` — searching the nine knowledge
docs for the corpus's own language ("whip-pan", "light-leak", "split-frame")
returns nothing.

So at ruling time the agent sees:

    the reference rates        REMOVED ENTIRELY (Zac's rubric ruling) — correct
    abstracted rules           "Cards land with the speaker OFF-SCREEN, and are
                               strongest at the CLOSE" — the corpus digested
                               into instruction
    the reference EDITS        NOTHING

## What exists and is unused

`reference_beats` — 153 beats across 10 videos, 426.1s. Per beat:

    t_start, duration_s, treatment[], purpose, read

`read` is the craft. A sample, verbatim from the corpus:

    [2] 1.13s  cut+cutaway+overlay_text+sfx   hook
        "A jarring glitch/whip-pan cut breaks the calm intro to simulate a
         reaction-video format, escalating curiosity"
    [5] 2.13s  cut+card+overlay_text          claim
        "Cuts to a full-screen bold sans-serif title card to isolate and
         emphasize the value proposition apart from the speaker"
    [7] 1.07s  cutaway+card+overlay_text      turn
        "A split-frame cutaway to genuine frustrated-editing footage visually
         literalizes 'boring parts' as a tonal pivot"

Each names WHAT WAS PLACED, WHERE, and WHY IT LANDED THERE. That is exactly the
thing the prompt describes and cannot demonstrate. It has been in the database
the whole time, and the only thing ever taken from it was a count.

**The corpus was mined into numbers. The numbers grade. Nothing shows the agent
the craft it is being graded against.**

## The family audit — who can rule without naming anything grounded

    family      must name                    grounded in the SOURCE?
    ─────────────────────────────────────────────────────────────────
    card        card_hero (REQUIRED)         YES — the figure or phrase the
                                             card is ABOUT, from the speech.
                                             And only since ff9311f, today.
    text        text_content (REQUIRED)      PARTLY — the words are the copy,
                                             not a citation. Nothing forces the
                                             ruling to name the moment the copy
                                             responds to.
    sfx         sfx yes|no (REQUIRED)        NO — names a SOUND, never what in
                sfx_name (optional)          the source earned it.
    zoom        zoom_arc (REQUIRED)          NO — arc position is a structural
                                             judgement about the video's shape,
                                             not a thing in the footage.
    transition  NOTHING                      NO — the schema has no transition
                                             field at all.

**Three families can be ruled without naming anything grounded: sfx, zoom,
transition.** Text is partial. Card is the only one that fully complies, and it
complies by accident of a fix made for a different reason this morning.

Zoom is the visible offender because it costs nothing, but transition is worse:
it has no field to be empty.

## The ordering problem, stated rather than resolved

Closing sfx, zoom and transition means adding a required grounding field to
each. That changes what the agent emits on every beat of every family — which
lands in round 47, the round I have just frozen my own card surface to keep as a
ONE-VARIABLE test of the card-and-text sentence.

I am not choosing between these. Closing three families is a standing
requirement from Zac; the one-variable round is my own discipline and worth less.
But a round carrying both is not a clean read of either, and saying so now beats
discovering it in the report.

Options, for Zac:
  a. Close all three now, and round 47 reads as "the card sentence plus a
     grounding requirement" — the card result becomes uninterpretable again.
  b. Let round 47 collect first (it separates the card sentence cleanly), then
     close all three for round 48.
  c. Close them now and drop the one-variable claim explicitly rather than
     letting it decay.

I have not started (a), (b) or (c).
