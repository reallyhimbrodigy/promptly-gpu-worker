# CUTAWAY PACING — the visual cut that needs no content removal

**Status: SPEC. Nothing built. `pace_cuts` remains HELD; this does not touch a
single word the speaker said.**

Target: **one visual change every 5-7 seconds**, carried by insert scenes and
b-roll as the PRIMARY pacing tool, with the audio continuing underneath.

---

## 1. The instrument already exists, and it is already failing

`recipe_eval` measures exactly this, every job, and already FAILS on it. Two
renders from this session:

```
                      delivered (34.4s out)     c9ad1bbf (60.3s out)
runtime_windows                19                      59
visual_events                   7                       7
events_per_window            0.37                    0.12
empty_windows              13 / 19                 48 / 59
max_dead_gap_s               11.6                    70.4
zoom/trans/broll/mg/ovl/sfx  4/0/0/2/1/4            4/0/0/2/1/4

FAIL [dead-zone] 11.6s with no visual event starting at 25.2s
                 — the swipe happens here
FAIL [dead-zone] 70.4s with no visual event starting at 43.0s
```

**The eval already names the user consequence** ("the swipe happens here") and
the job ships anyway. So this capability does not need a new measurement, a new
threshold, or a new model. It needs the warning to become a thing the pipeline
ACTS on, and it needs the tool that would fill those windows to actually fire.

**B-ROLL FIRED ZERO TIMES ON BOTH RENDERS.** That is the whole problem in one
number. The pacing tool nominated for this job is not running.

---

## 2. Why b-roll fires zero — seven gates, and they compound

Every b-roll entry must survive all of these, and each is individually defensible:

1. **Opening gate** — nothing in the first ~3s or inside the hook segment.
2. **Exclusivity** — dropped if its frames overlap ANY `motion_graphic` or
   `text_overlay`. *Overlays win.*
3. **Face moments off-limits** — any word inside an `emphasis_moments[]`
   with a non-null zoom.
4. **Arc placement** — "build is where B-roll lives".
5. **The extend test** — it must EXTEND the moment, not illustrate it.
6. **The look test** — its colour world must sit against the source's.
7. **Mode gates** — modes (2) APP-INPUT and (4) ABSTRACT ATTRIBUTE default to
   the speaker's face; mode (5) SOURCE IS ALREADY ITS OWN EVIDENCE emits none.

**The compounding is the defect, not any one gate.** This is the third time this
session a component has been found at zero because gates stacked until the
surviving population was empty — after the compositions (requested 0/3, filed in
the wrong prompt section) and dead-air (0 candidates, gated on punctuation an
ASR never emits). Same shape every time: each gate correct in isolation, the
conjunction empty.

**Gate 2 is the one that matters most here, because it is self-defeating.** In
the delivered render: `mg=2, overlay=1, broll=0`. Every motion graphic placed
*excludes* b-roll from its window. We spent this session trying to raise
component density, and each component we added closed a window against the tool
that fills dead air.

**And in the 13 EMPTY windows, gate 2 is not even binding** — nothing is there
to conflict with. B-roll is excluded from the ~6 occupied windows and simply
never requested for the 13 empty ones.

---

## 3. The inversion this spec proposes

Today b-roll is framed as a SCARCE component that must EARN its place against a
referent. That framing is why it loses every contest.

> **The empty window becomes the trigger.**

Not "does this beat deserve a cutaway" but "this 6-second stretch has no visual
event, and a cutaway is the cheapest honest way to fix it."

Concretely, three changes and no new model:

**3a. A cadence budget is computed and stated, not inferred.** Before the visual
pass, Python computes the windows and marks which are empty — it already does
this in `recipe_eval`, but AFTER the fact. Move the same computation BEFORE the
ask, and hand the model the actual list: *"these stretches have no visual event:
[8.2-14.9s], [25.2-36.8s]. Fill them."* The model is currently asked to place
b-roll well; it is never told where the holes are.

**3b. Gate 2 inverts inside an empty window.** Where a window has no motion
graphic and no overlay, exclusivity is vacuous and the b-roll opening gate,
extend test, and look test are the only checks that apply. Where a window is
already occupied, today's rules stand unchanged — overlays keep winning.

**3c. Insert scenes fill what b-roll cannot.** `generated_scenes` measured 0 on
11 of 11 cells. Where no honest stock referent exists (the Pexels
thin-relevance path), a generation-free composition — the family already built,
wired and taught this session — is the fallback that needs no fetch and cannot
be thin. That is what those compositions are FOR, and this is the first job that
gives them a trigger they can actually satisfy.

---

## 4. The bar, and the standing rule it collides with

**Target:** one visual change every 5-7s = **8.6-12 changes/min**.

Reference calibration (`score_component.py`):

```
REF-1  21 cuts  24.0/min   mean_change 0.0864
REF-2   8 cuts  11.1/min   mean_change 0.0596
```

5-7s lands on REF-2's density and well under REF-1's. The delivered render
measured `mean_change 0.0358` — below the 0.6x floor of the LOWER reference.

**THE COLLISION, surfaced rather than silently overridden.** A standing rule
says: *"~10-15% B-roll coverage is fine; 30-40% is a CEILING not a target."* One
cutaway every 6s at 1-2s each is **17-33% coverage** — at or above that ceiling.

Two honest readings, and this needs an owner call, not a quiet reinterpretation:

- The ceiling was about b-roll as ILLUSTRATION (does the video become stock
  footage with a voiceover?). Cutaways as PACING is a different use, and the
  same percentage means something different.
- Or the ceiling is a ceiling, and the 5-7s target must be met by a MIX —
  insert scenes, compositions, motion graphics, reframes — with b-roll carrying
  only its 10-15% share.

**The second reading is the safer default and this spec assumes it** until ruled
otherwise: b-roll fills empty windows up to its existing coverage ceiling, and
compositions/insert scenes carry the remainder. That also removes the dependency
on Pexels having something honest for every hole.

---

## 5. What must NOT happen

- **No content removal.** The audio runs continuously underneath every cutaway.
  This is the capability that closes the gap WITHOUT touching the ruling.
- **No cadence quota in the prompt.** Telling the model "one every 6 seconds"
  produces cutaways for the count's sake — the same failure mode as telling it a
  cut count. Python names the HOLES; the model decides what fills them, or
  declines with a reason.
- **No thin b-roll to hit a number.** The existing honest-fallback path (thin
  Pexels relevance -> decline) stays. An empty window is better than a lying
  cutaway, and the decline must be ledgered so the hole is attributable.

---

## 6. How it gets verified

1. **The instrument is already there.** `recipe_eval`'s `max_dead_gap_s`,
   `empty_windows`, `events_per_window` are the pre/post metric — no new
   measurement to build, and it already runs on every job.
2. **Pre-registered win condition:** `max_dead_gap_s <= 7.0` and
   `empty_windows / runtime_windows` materially down, on the same sources,
   with b-roll and composition counts reported separately so it is clear WHAT
   filled the holes.
3. **Then a render, and then the eye.** `mean_change` >= 0.6x the lower
   reference is the scorecard bar; whether the cutaways feel motivated rather
   than mechanical is a taste call on a differing pair, and no instrument here
   settles it.
4. **Cut by route.** moodreel/minimal/hype already carry their own pacing; this
   is about the standard editorial path. A blended number across routes would
   hide the thing being fixed.

---

# INVESTIGATION RESULTS (2026-08-20) — answered before building, nothing wired

**Headline: this is a DENSITY AND TRIGGERING problem, not a rendering one. The
architecture already does what a cutaway needs.**

## 1. Replacement — ALREADY WORKS

`BrollClip` renders `<AbsoluteFill><Video style={{width:"100%",height:"100%",
objectFit:"cover"}}/></AbsoluteFill>` inside a `<Sequence from= durationInFrames=>`,
composited above the source layer. **During its span it FULLY REPLACES the
talking head.** Generated scenes render the same way. Nothing to build here.

## 2. Audio continuity — STRUCTURALLY GUARANTEED, not merely observed

Audio is built as a SEPARATE WAV from the cut plan, before the visual render
finishes:

    [audio] Built per-cut audio: 2 cuts, 0 transition(s), 34.400s, 1517040 samples
    [sfx]   Mixed 4 SFX track(s) into audio (no ducking)
    [render] Final audio built in 1.4s → final_audio.wav

and the mux is explicit:

    -map 0:v    video from the visual render
    -map 1:a    audio from final_audio.wav ONLY

**A full-frame takeover CANNOT interrupt speech — impossible by construction.**

**ONE HAZARD, LOAD-BEARING AND UNDOCUMENTED:** the b-roll `<Video>` carries NO
`muted` prop. Its stock audio would leak — except `-map 1:a` discards it. The
law holds TODAY BY ACCIDENT OF THE MUX, not by intent at the component. Anyone
who later adds an audio path to the visual render breaks the one property this
whole capability rests on, with no check to catch it. If cutaways are built,
`muted` belongs on that component and a gate assertion belongs on the mapping.

## 3. What the prompt asks — GARNISH, with a per-clip justification burden

> "B-roll earns its place by EXTENDING the moment. … before you request the
> cutaway it surfaced, name what the frame gives the viewer beyond what the
> words and the speaker's face already deliver."

Plus a ~15%-of-runtime coverage guide. That is a SCARCITY DOCTRINE: every clip
argues for itself against the speaker's face. The references make cutaways the
DEFAULT STATE OF THE SCREEN. The gap is a posture, not a threshold.

## 4. Trigger vocabulary — EVERY FIELD IS CONTENT-TYPED, NONE IS PACING-TYPED

    named object                 broll_clips.keyword          full-frame  OK
    place                        broll_clips.keyword          full-frame  OK
    action described not shown   broll_clips.keyword          full-frame  OK
    stated claim                 EvidenceCard                 full-frame  BUT CLASSED AS A MOTION GRAPHIC
    a number                     StatCard                     OVERLAY — "no card background,
                                                              the number floats over the footage"

The planner can say WHAT to show. It has NO WAY to say "this stretch needs a
visual change." There is no field. `recipe_eval` computes exactly that
information — AFTER the plan, as a warning nobody acts on.

## 5. Sources ranked — THE CHEAPEST IS ALREADY BUILT AND REQUESTED ZERO TIMES

    1. user's own frame (EvidenceCard/DeviceMockup)  $0, instant, always relevant,
                                                     cannot be thin. Full-frame.
                                                     Built+wired+taught. REQUESTED 0/3.
    2. b-roll fetch                                  $0, adds fetch latency. FIRES 0.
    3. EmojiCard                                     $0 pure type.
    4. generated scenes                              quota-bound, ~$0.14. FIRES 0/11.
                                                     Correctly the last resort.

Sources 1 and 3 are MISCLASSED AS MOTION GRAPHICS, so they compete in the MG
slot AND block b-roll through the exclusivity gate — the family that should be
the cheapest cutaway supply is currently the thing that suppresses the supply.
