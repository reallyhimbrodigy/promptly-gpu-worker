# QUALITY_CAMPAIGN — the taste war, ranked, with a loop per item

**Written 2026-08-12, before ignition, so the campaign starts the afternoon
payments land with zero planning delay.** Everything ranked below is either
already built dark or is a named, scoped build. Nothing here waits on a meeting.

The reliability war is finished: 0 repairs / 0 P0 across 36 post-v527 terminal
jobs, the Render gate armed, the pre-push gate armed. What is left is not
uptime. It is whether the video is *good*.

---

## THE LOOP — the same four steps for every item, no exceptions

```
change dark  →  differ verdict in HOURS  →  fulfillment + export delta in a DAY  →  keep or kill
```

| step | what it means | who |
|---|---|---|
| **change dark** | flag off = byte-identical, cert in the deploy gate | BUILDER |
| **differ** | `harness_plan_diff.py diff --golden golden/plans --candidate <dir>` — offline, free, hours | BUILDER |
| **delta** | JUDGE's fulfillment honor-rate + the export/result_viewed ratio, cut BY ROUTE, on a clean cohort | JUDGE |
| **keep or kill** | GREEN → keep · RED → **kill, do not tune in-window** | owner |

Three rules that make the loop honest, all of them already paid for:

1. **RED is HELD, not tuned.** The compressed-window law. A route that fails
   keeps its flag off and ships next window.
2. **A differ GREEN is "the corpus saw no regression" — not proof of
   improvement.** Improvement is a taste call on pixels, and that is the
   owner's, on rendered pairs, never on a flag.
3. **Never send a pair not programmatically proven to differ.** Frame-diff at
   motion timestamps, PSNR reported. Three rounds of the owner's time were lost
   to pairs that may have been identical.

---

## THE RANKED BACKLOG

Ranked by **(measured demand or measured defect) × (confidence it moves
perceived quality) ÷ (risk to a working render)**. The first three are built.

---

### 1. PAYOFF ARMS 6 + 7 — the ruling gets its evidence · **BUILT, dark**

**The number:** 0 punchy payoffs in 253 chances.

**Read the ruling before touching this.** That zero is not a bug. It is the
system obeying the owner's own twice-expressed doctrine [CODE handler.py:1215;
prompt prose at the payoff position]: *"the slow commitment IS what makes the
payoff bigger than every beat before it; a snap would read as just another
mid_peak."* It is coherent, it is deliberate, and 0/253 is evidence it is
**working**, not failing.

What was missing is the choice, not the answer:

| arm | flag | what it changes |
|---|---|---|
| 6 (2026-07-31) | `PROMPTLY_PAYOFF_PUNCHY` | enum widened — a snap becomes *sayable* at payoff |
| 7 (2026-08-12) | `PROMPTLY_PAYOFF_OPEN` | enum widened **and** the prohibition removed from the prose (implies arm 6) |

Arm 6 alone cannot settle it, and its own pre-registered read says so: the prose
still forbids what the enum now allows, so a null there is **obeyance, not
judgement**. Arm 7 is the only configuration in which "never picked" is a real
confirmation. Arm 7 was built now rather than after arm 6 returns null purely to
take a serial dependency off ignition — both dark costs nothing, and one differ
pass separates obeyance from judgement instead of two.

**The swap neutralises, it never advocates.** It removes the prohibition and
keeps the requirement (the payoff must still commit); it never says "be punchy".
Prose arguing for a snap would measure the new instruction instead of the
model's taste — the same defect in the opposite direction.

**Pre-registered read, fixed before any data:**
- punchy IS picked → purity was obeyance. Report which beats, render the pairs.
- still never picked, prose neutral and enum open → **the model agrees with the
  ruling on its own.** A real confirmation, which arm 6 alone could never give.
- picked but the pairs read worse → **the ruling is vindicated on pixels**, the
  strongest possible outcome for it.

**No outcome changes anything by itself.** It produces the pixels the owner's
ruling stands or falls on. His call, on pixels, never on a flag.

`cert_payoff_arms.py` · gate check 368 · cost: PLAN_ONLY, ~$0.10/arm.

---

### 2. BACKGROUND MUSIC v1 — the mechanism · **BUILT, dark**

**The number:** 72 recorded asks, dropped. Nothing transforms the perceived
quality of short-form like a bed under the voice.

Built: ask detection (negation-guarded), bed selection, **sidechain** ducking
off the speech envelope, a stated volume law, and an honest note when no bed
fits.

**The volume law, in numbers so it is arguable:**

| | |
|---|---|
| bed target | **−28 LUFS integrated** (absolute, `loudnorm`) |
| duck under speech | −14 dB further, ratio 20 |
| attack / release | 20 ms / 400 ms |
| measured | bed alone **−29.8 dB** · under speech it adds **+0.00 dB** over speech-only |

Two decisions worth keeping:

- **Sidechain, not a schedule.** The duck follows the actual speech envelope, so
  it stays correct when a cut moves. A scheduled duck is a second clock over the
  same audio — the class the shared-clock law exists to stop.
- **Loudness-normalised, not gain-scaled.** A relative `volume=` multiplies
  whatever the track was mastered at, and a licensed library varies by ~20 dB.
  The first build did exactly that and produced a bed at **−57.8 dBFS**:
  inaudible — the feature shipping as a no-op that a one-sided assertion still
  called green. The audibility floor is now asserted in **both** directions.

**The safety property that lets this sit in the repo behind a flag:** all three
beds are synthesized placeholders marked `deliverable: false`, and bed selection
**refuses** anything not explicitly deliverable. Flipping the flag today
delivers **no music** and says so honestly. The audio a user receives is gated
on the owner's licensing pick, not on a flag.

**Owner's move:** pick the licensed library. Tracks land in `assets/music/`,
each gains `deliverable: true` with its licence filled in, and the mechanism is
already certified.

**Remaining build (named, not hidden):** splicing the bed into the render's
existing SFX `amix`. That touches delivered audio, so it gets its own change
with the render certs run — not a hasty ride-along.

`cert_music_v1.py` · gate check 369.

---

### 3. COMPONENT_OBEY — the honesty floor · **BUILT, dark** (shipped v527)

**The number:** cluster silent-drop **94.0% on lean** (n=215) vs 63.5% premium,
54.5% standard. One in five lean jobs carries a cluster ask; 94 of 100 vanish
without a word.

Honor where the toolbox has it; **note where it does not**. The note leg is
deterministic code after the model, because lean routes never call the editorial
model at all — a prompt-side fix cannot reach 94% of the loss by construction.

**JUDGE's acceptance bar, theirs to read:** lean cluster silent-rate 94% →
**<20%** over ≥150 post-flip cluster asks, with a matching honest-note rate.

This is the floor the rest of the campaign stands on: *the user is never
silently ignored.* Ship it first — a beautiful edit that drops your request is
still a product that does not listen.

---

### 4. DENSITY / MOMENT TUNING — the biggest quality gap not yet armed

**The numbers:** 63% of standard-editorial jobs carry **zero** motion graphics.
Density 7.76 vs the owner's reference 16.7 per 25s — **we cut half as often as
his own reference edit.**

**Known before starting, so the loop is not wasted:** the E1 density ceiling is
**architectural, not prompt-tunable** — multi-gate culling, not model
reluctance. `MG_HONORING_DIAGNOSIS.md` ranks four hypotheses (H1 prompt, H2
route mix, H3 projection-miss drops, H4 render collision/floor drops). H3 and H4
are **post-model** and cost $0 to measure: count `projection_miss_drop`
divergence rows and the render-layer drop reasons on existing traffic.

**Do the free measurement first.** If the drops are post-model, no prompt arm
can fix it and COMPONENT_OBEY's honor leg will under-deliver for a reason that
has nothing to do with the prompt.

Loop: measure H3/H4 free → arm whichever gate is culling → differ → density per
25s by route + honor rate. **Not started.**

---

### 5. CAPTION POLISH — the most-seen surface in the product

Captions are the best-fulfilled class already (**79% honored**, 235 asks, and
the one place notes actually fire). The gap is not fulfillment, it is *finish*:
entrance crispness (frame-1-is-final is law), the never-early ceiling (0% early
across all 9 styles), legibility floor, and mid-word endings.

Highest-leverage first: **caption_language** — 50 asks, 23 dropped silently
(46%), and `PROMPTLY_CAPTION_TRANSLATE` is **already built and dark**. That is a
flip with a cert, not a build.

Loop: flip caption-translate on its own window → differ → the 46% silent rate on
that class. **Ready.**

---

### 6. PREMIUM / LUMEN REVIVAL — the largest capability sitting dark

moodreel + hype have been **exactly 0 for 3+ days** (685 completions, 643
users), against a **31.6% pre-outage share**. Premium is also the *best*
performer on the product's #1 named ask (motion_graphics 37% silent on premium
vs 96% on lean).

**This is a launch-day P0 gate, not a campaign item, until it is answered.**
LAUNCH_DAY Step 2: if routes are still 0 an hour after billing with n ≥ 10,
declare the second P0 — a stuck fail-safe — and stop. Everything downstream
depends on real editorial plans.

Once routes return: Lumen Increment 1 (premium E2E 834s, 0 scenes) is the
quality ceiling worth attacking, and `PROMPTLY_UNIFIED_CORE` flips on its own
merits (premium composition identity) — **not** as an honor-rate lever. JUDGE's
verdict is explicit that it aims at the side already least broken.

---

### 7. UPSCALE v1 — shipped, awaiting its flag · **BUILT, live dark (v528)**

195 asks, 100% dropped. The negotiation ships the honesty; the pass ships the
substance (lanczos 2× to 2160×3840 + unsharp, audio copied, runs only on an
explicit ask). The note is derived from the produced artifact, never the intent.

Loop: flip → the 195-ask class stops dropping → export-rate delta on jobs that
asked. `cert_upscale_v1.py` · gate check 367.

---

## THE FIRST AFTERNOON — what actually happens when ignition lands

Ordered so nothing waits on anything else:

1. **Route-recovery check** (1 traffic hour). Premium back, or the second P0.
2. **Freeze** — `bash golden/ignite.sh`. Whole-or-nothing.
3. **COMPONENT_OBEY** first. The honesty floor; everything else is judged on top
   of a product that no longer silently ignores people.
4. **Payoff arms 6 + 7 in ONE differ pass** — PLAN_ONLY, ~$0.20 total. Obeyance
   vs judgement, settled in an afternoon.
5. **Caption-translate** — built, dark, a flip and a cert.
6. **Density H3/H4 free measurement** — no spend, no window, runs in parallel.
7. **Music** — the moment the owner names the library.

## WHAT THIS CAMPAIGN WILL NOT DO

- **No new instruments and no new watches** until launch. The scoreboard,
  fulfillment judge, differ, and export ledger already answer every question
  below. Another dashboard is not another insight.
- **No tuning inside a window.** RED is held.
- **No pair to the owner that has not been proven to differ.**
- **No taste call made by me.** I build the choice; he makes it. That is
  explicitly true of item 1, where the thing under test is his own ruling.
