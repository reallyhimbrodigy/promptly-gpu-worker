# Reading what landed: transitions are INVISIBLE to preview_timeline

MEASURED 2026-09-21 on 6c0ca574-a975-4641-930d-cdc4a4648a15, both endpoints.

## The defect this exists for

`preview_timeline` with `views:["timeline"]` lists **items and gaps and nothing
else**. It does not list transitions, and it does not say that it is not listing
them. So a "what landed" table built from it reports **zero transitions, always**
— and reads as the agent declining to use any, which is a verdict about the
agent produced entirely by the instrument.

I shipped exactly that table. It said three overlays and three sounds. The
timeline also carried a transition, and I only learned so because an unrelated
delete was refused:

    transition 13ca9fd9b7 would reference a deleted or missing outgoing item
    8ef5fa67e4 after this edit.

An error message was the only surface that admitted it existed.

Same family as the frame-window blind spot and the `@@VELOCITY_CAP@@` drift
check: the capability to report it existed, and nothing invoked it.

## The method that works

`inspect_item` on a placed item reports transitions under a trailing
**`Attached`** block. Its own description says so — "attached effects/transitions
when present" — which is another way of saying the information was always
reachable and the reader was pointed at the wrong tool.

A transition appears on BOTH of its endpoints, with the SAME id, under opposite
kinds. Measured, not assumed — both calls below were made:

    inspect_item e4d1cf3924   (the outgoing item)
      transition-out [f1aab7098d] audio Audio Cross Fade
        [builtin:tr-audio-cross-fade] → incomingItemId=67570d1ae8 duration=4f

    inspect_item 67570d1ae8   (the incoming item)
      transition-in  [f1aab7098d] audio Audio Cross Fade
        [builtin:tr-audio-cross-fade] ← outgoingItemId=e4d1cf3924 duration=4f

So the enumeration is:

1. `preview_timeline views:["timeline"]` -> every item id. This is complete for
   ITEMS and empty for transitions.
2. `inspect_item` on EVERY item -> collect each `Attached` row.
3. **Dedupe by transition id.** Each transition is reported twice, once per
   endpoint. A count that skips the dedupe doubles every transition, which is
   the opposite error and just as wrong.
4. A transition whose id appears only ONCE across all items is a dangling
   reference, not a transition — report it as a FAULT rather than counting it.

## What the field actually carried

The one on that timeline is `builtin:tr-audio-cross-fade`, 4 frames, on the
AUDIO, spanning the splice at source 5.300s / 5.320s.

Worth recording because it changes a judgement: the agent cut inside a real
silence and then cross-faded the audio across its own cut. That is a craft
decision, and a table that cannot see transitions scores it as nothing at all.

## The rule

**A "what landed" count names the surface it read and the surface it did not.**
Items come from `preview_timeline`; transitions come from `inspect_item` per
item; captions come from `read_captions` (`preview_timeline` reports only a
present/absent flag, and that flag tracks the existence of a caption PROGRAM,
not whether any card carries text). Three surfaces, three reads. A judge that
reads one and reports "what landed" is reporting what ONE SURFACE SHOWS, and
should say so.
