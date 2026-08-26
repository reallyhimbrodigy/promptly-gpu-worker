# One component must never cost the whole edit — the graceful placement ladder

**Status:** spec. **Blocks:** shipping `PROMPTLY_SCENES_DIRECTIVE_V2`.
**Measured:** 2026-08-19.

---

## 1. What happens today

`_mg_clear_region_exists` (handler.py:1490) is called at two sites (18279,
20499). When an oversized card has no face-clear anchor at its fitted size, the
check appends to `_mg_violations`, which becomes `RECIPE_INVALID`:

    RECIPE_INVALID: StatCard at word 62: no face-clear region exists for a card
    this size — reduce its content, or move it to a window where the speaker
    sits lower/off-center.

That string is then handed to the MODEL as a repair re-ask. Twice. If the model
does not fix it, `safe_edit_refused` fires and the user gets nothing — after we
have paid for transcription, analysis, and a full planning call.

**The pipeline asks the model to perform a computation the pipeline can do
itself, and throws away a paid render when the model declines.** The error text
already names both remedies. Nothing applies them.

## 2. Blast radius — measured before speccing, so the urgency is honest

Server-side counts, `created_at >= 2026-07-20` (no 1000-row cap):

    TOTAL jobs             7712
    failed                 2505
    RECIPE_INVALID            2   <- both the same user, same minute,
                                     "not enough values to unpack" — unrelated
    cite face-clear           0
    UPLOAD_NEVER_STARTED    631   } probe non-vacuity: the same query shape
    RENDER_FATAL             93   } returns large counts, so 0 is a real 0

**This is a LATENT class, not a live one.** Nobody is bleeding today.

**And the change under test is what wakes it.** The V2 scenes directive exists to
make the planner PLACE MORE. On the first source tried (`comp_scenes_536daed2`,
61s, face-filling talking head) the ON cell hit F7 immediately and died, while
the OFF cell completed. So this ladder is not an emergency repair — it is a
**precondition for shipping the directive**, which is a better reason to build it
than a frightening rate would have been.

## 3. The ladder — applied BY THE PIPELINE, in order, per component

THREE rungs, not four. Each is attempted only if the one above fails, and every
outcome is ledgered. The fourth rung I originally specced is documented below as
impossible, in place, so it is not re-added by the next reader.

### Rung 1 — ~~SHRINK~~ — DOES NOT EXIST, AND MUST NOT BE RE-ADDED

I specced this rung and it is impossible against the check it was meant to
satisfy. **F7 judges size by TYPE MEMBERSHIP, not by content extent:**

    _MG_FULLSIZE_TYPES = frozenset({"DropBanner", "DropCard", ...})

`_mg_clear_region_exists` branches on `mg_type in _MG_FULLSIZE_TYPES` — full-size
classes are tested against band PAIRS, everything else against single bands. A
StatCard carrying two words and one carrying twelve get the IDENTICAL verdict,
because the content never reaches the function. Reducing props would therefore
run, log, and provably never flip a single decision: a rung that exists to be
seen doing something.

The 2026-08-19 failure makes it concrete. The component was a `StatCard` — NOT
in `_MG_FULLSIZE_TYPES`, so it was already judged on single bands, the most
permissive case available, and STILL found nothing clear. Shrinking it could not
have helped; the frame was genuinely full.

**To make shrink real**, F7 would have to become content-aware — design-system
size metrics per component, a fitted height derived from props, and a re-test at
each step. That is a real feature with a real design question behind it (what is
the legibility floor?), and it belongs in its own decision, not smuggled in
under "graceful placement".

### Rung 2 — REPOSITION
Search the component's own span, then a bounded neighbourhood of adjacent word
windows, for a window where a clear region exists. The anchor MUST remain on a
word the component is grounded in — moving a StatCard off the number it
displays is a lie, and grounding is checked upstream (F5.3). **Bound the search**
so a reposition never drifts past the beat it belongs to.

**AND IT MUST CLEAR OUR OWN CAPTIONS, NOT JUST THE FACE.** F7 excludes `burned_bands`
— the bands the SOURCE's text occupies — and knows nothing about the caption
track WE are about to render. A face-only reposition will cheerfully move a card
into the band the captions land in, trading a collision with the speaker for a
collision with our own type. `caption_position_segments`
(`from_seconds`/`to_seconds`/`position`) carries exactly this, on the same three
band names, so it composes with the existing exclusion rather than needing new
machinery.

ONE EXCEPTION, and getting it wrong makes reposition fail for a reason that does
not exist: when `caption_style` is `"none"` the source carries its OWN burned
captions and we render no caption track. There is nothing of ours to avoid, and
`source_text_regions` already covers those bands — counting caption occupancy
there would double-exclude and strand a card that had somewhere to go.

### Rung 3 — DROP WITH A NOTE
Remove the component, keep the edit. Ledger it:

    _ledger_dropped("motion_graphic", mg_type, "clear_region_unfittable")

and record a divergence so it is visible in the daily read. This is where the
`degrade-not-drop` precedent (v197 cut-stack reform) inverts deliberately: for a
CUT, degrading preserved the edit; for an unplaceable overlay, the edit is
better without it than with it collided onto a face.

**AND IT IS USER-FACING, AT THE MOMENT IT WAS REQUESTED.** The ledger is for us;
the user gets a plain sentence naming the beat where something was intended:

    "I wanted a stat card on 'four sets of twelve' — the frame is too tight
     there for one to sit clear of your face, so I let the line carry it."

Three rules on the wording, because this is the seam where a transparency note
becomes an error message:

- **It is an editorial note, never a failure.** The standing law is fail loudly
  to US, never to the user — and this does not violate it, because nothing
  failed: a component was considered and not placed, which is a decision an
  editor makes constantly. Phrase it as intent, never as `RECIPE_INVALID`,
  never with a component's internal type name.
- **It names the MOMENT, not the machinery.** "on 'four sets of twelve'" is the
  user's own words; "StatCard at word 62" is ours. The user knows their video by
  what they said in it.
- **Silence when there is nothing to say.** No note for a component that shrank
  or repositioned successfully — the user does not need a changelog of things
  that worked. Only rung 3 speaks.

WHY SURFACE IT AT ALL: the user asked for an edit and got one with a beat
deliberately left bare. Saying so converts an invisible subtraction into a
visible judgment, and it is the difference between a tool that quietly did less
and a collaborator that made a call and told you. It also gives the user the one
piece of information that lets them fix it — reframe the shot — which no
internal ledger can.

Carrier: the existing `change_summary` / edit-rationale surface, which already
reaches the client. It must NOT create a new error channel.

### Rung 4 — FAIL
Only if the plan is structurally invalid for a reason that is not this component.
**Dropping one motion graphic must never reach this rung.** If it does, the bug
is elsewhere and the honest failure is the one that fires.

## 4. What must NOT change

- **Grounding stays hard.** F5.3 (a card's number must come from the dialogue)
  and the burned-text bands are correctness, not placement. The ladder never
  relaxes them; it only answers "where does this fit".
- **The model is still told.** A dropped component is reported in the ledger and
  the divergence stream so the planner's requested-vs-shipped gap stays legible.
  Silently absorbing bad placements would hide the very signal that tells us
  whether a doctrine change is working.
- **No fabrication.** Reposition moves an anchor within its own grounding;
  shrink reduces content the component already had.

## 5. The check that makes the regression impossible

`cert_graceful_placement.py`, RED-proven, asserting on a CONSTRUCTED plan +
synthetic face trajectory (no model call, no render):

1. a card that fits is placed **unchanged** — the ladder is inert when it should be;
2. a card whose own window is blocked is **REPOSITIONED** to a clear window —
   and the search REJECTS a window occupied by our caption track, not just by
   the face;
3. reposition never leaves the component's grounding (the anchor stays on a word
   it is grounded in);
4. one that can do neither is **DROPPED AND LEDGERED**, and the plan still
   validates — the edit survives;
5. **the drop is never silent**: `_COMPONENT_LEDGER` shows
   `dropped_by_us` with `clear_region_unfittable`, a divergence is recorded, AND
   a user-facing note names the beat in the user's own words;
5b. **the note is an editorial note, not an error**: it contains no internal type
   name, no error code, and no failure language — asserted by regex against the
   rendered sentence, with the negative control being the raw violation string
   (`StatCard at word 62: no face-clear region exists...`), which must NEVER
   reach the user surface;
5c. **silence when nothing was subtracted**: a component that SHRANK or
   REPOSITIONED successfully produces NO note — the user gets a changelog of
   subtractions, never of successes;
6. **no rung fabricates**: the repositioned anchor is still a word the component
   is grounded in;
7. `RECIPE_INVALID` is **no longer reachable** from a clear-region violation
   alone — the negative control drives the exact 2026-08-19 failure
   (`StatCard at word 62`) and asserts it now degrades instead of raising.

## 6. Production counter

`clear_region_unfittable` in the component ledger, read per-job and per-user.
Post-ship it answers two questions with one number: how often the planner asks
for something unplaceable, and whether the V2 directive raises that rate — which
is exactly the signal that would tell us the directive is over-placing rather
than placing well.

## 7. Order

1. Ladder + cert (this spec), behind no flag — it can only convert a hard
   failure into a degrade, and the failure is currently unreachable on live
   traffic, so shipping it dark would test nothing.
2. Re-run the two-cell scene test on two deliberately chosen sources.
3. Only then consider arming `PROMPTLY_SCENES_DIRECTIVE_V2`.
