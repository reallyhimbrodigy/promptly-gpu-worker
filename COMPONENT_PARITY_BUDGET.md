# Component parity — what it costs, and what actually breaks the clock

BUILDER-2, 2026-09-07. Sized before porting anything, per the brief.
**This is a ruling for Zac, not a compromise made quietly.**

## The headline

**The full library fits on COST with room to spare. It does not fit on TIME —
and it did not fit on time before I touched it.**

|                | ceiling | today (talking_head) | full parity | verdict |
|----------------|--------:|---------------------:|------------:|---------|
| cost / job     |  $0.25  |  $0.1127             |  ~$0.143    | **FITS** — 57% of ceiling |
| wall / job     |   120s  |  226.7s              |  ~245.7s    | **FAILS — and already failed at 226.7s** |

The port spends **$0.030 of the $0.17 remaining budget (18%)** and **+19.0s**.
It is not what breaks the clock. The clock was broken by 106.7s before the
first component was ported.

## Where the numbers come from

Cut to the talking_head fixture: it is the ONLY speech source in the corpus
(4 of 5 fixtures print `SPEECH CHECK: NOT APPLICABLE`) and therefore the only
one that exercises captions, text, card and sfx together. A blended five-fixture
number would answer a different question (Rule 5).

**OBSERVED — round 33, mount `f40873429cfa84a6`, talking_head:**
- source 38.5s → output 23.17s, 11 beats, kept 0.767
- wall 226.7s; cost $0.1127; 12 turns
- `model_thinking 152.81s (67.4%)`, `build_overlays 32.20s`,
  `build_captions 28.59s`, `build_reel 24.14s`, `composite_captions 3.82s`,
  `build_zoom 2.28s`
- tokens: in 58, out 12,990, cache_read 173,343, cache_write 24,300
- captions: `Gadzhi @ 15fps, 443 frames, paint 21.7s (49.0 ms/frame),
  path=remotion, composited=True`

**OBSERVED — alpha-overlay paint rate in THIS lane: 49.0 ms/frame**, post the
concurrency-8 fix (a26925d). Round 32 was 299.1 ms/frame on the identical
fixture, so the fix is worth 6.1x and is already banked.

**PRODUCTION-MEASURED, NOT MEASURED IN THIS LANE — micro-segment paint
(video decoded and composited through Remotion): p50 1047.8 ms/frame vs overlay
114.5 (9.2x), over 83/94 organic jobs with legs
(`sweep_micro_concurrency_app.py:337-339`).**
Every number below that depends on it is labelled INFERRED. Measuring the
lane's own rate is the first thing to do and costs ~$0.05 (§ "What I need").

## Cost: the port is cheap because the port is mostly TABLES

Marginal token cost at 12 turns on Haiku 4.5
(cache_write $1.25/1M once + cache_read $0.10/1M × 11 reads = **$0.00235 per
1,000 prompt tokens**):

| family | what it actually is | prompt tok | cost |
|---|---|---:|---:|
| Motion graphics, 31 types | catalogue prose, `handler.py:8364-8475` | 6,602 | $0.0155 |
| SFX, 16 sounds | prose + `_SFX_ATTACK_MS` (16 floats) | 2,264 | $0.0053 |
| Zoom, 7 types | prose + `ZOOM_ARC_HOMES` / `ZOOM_PEAK_REACH_MS` / naturals | 1,046 | $0.0025 |
| Transitions, 9 + 2 tight-cut | `_TRANSITIONS_SUBCALL_SYS:13798-13810` | 1,011 | $0.0024 |
| Captions, 9 styles | **already ported**; style choice is a dict lookup | 0 | $0.0000 |
| | **prose subtotal** | **10,923** | **$0.0257** |
| richer verdicts | zoom_type, mg type+props, transition type | ~150 out | $0.0008 |
| transitions sub-call | one extra turn over the grown prefix | — | $0.0040 |
| | **TOTAL** | | **$0.030** |

$0.1127 + $0.030 = **$0.143 against a $0.25 ceiling.**

Two things make this cheap, and both are worth stating because they are the
reason "the whole library" is not the expensive ask it sounds like:

1. **The selection tables cost the agent nothing.** `_SFX_ATTACK_MS`,
   `ZOOM_PEAK_REACH_MS`, `ZOOM_NATURAL_DURATION_MS`, `_MG_ATTACK_MS` are
   applied by the harness from data the agent already emits (`sfx_name`,
   `card_hero`). SFX attack timing — the whole of item 4 — is **16 floats,
   $0 and 0.0s.** It is free and it should ship first.
2. **Output tokens, not schemas, are the cost.** 58% of $0.1127 is output.
   Prompt prose is 15% at 3x the current prompt size.

## Time: the port is +19.0s, and 106.7s is already over

Reference density on this fixture (38.5s = 1.54 × 25s), against what round 33
actually built:

| family | ref /25s | expected | **built r33** | gap |
|---|---:|---:|---:|---|
| text    | 7.28 | 11.2 | 10 | at reference |
| card/MG | 2.35 |  3.6 |  4 | **above** reference |
| sfx     | 0.82 |  1.3 |  1 | at reference |
| zoom    | 0.35 |  0.5 |  1 | **above** reference |
| transition | 0.00 | 0.0 | 0 | at reference (corpus is ZERO on this route) |

**This is the finding that reframes the whole brief: the lane is already AT
reference DENSITY. What is missing is VARIETY — 1 of 31 MG types, 1 of 7 zoom
types, 1 caption style not chosen by vibe, 0 of 9 transitions.** Zac's ruling
("every component used in the current pipeline must be used in this") is a
question about WHICH component gets placed, not HOW MANY. Variety is a table
lookup. It is nearly free.

Marginal wall at reference density:

| family | Δ wall | basis |
|---|---:|---|
| SFX attack table | **0.0s** | data applied at `place_sfx` — OBSERVED cost of the call is 0.51s today |
| Captions, 9 styles | **0.0s** | already rendering; style is a dict lookup |
| MG, 31 types | **−2.8s** | same reel, 3.6 at reference vs 4 built; 49.0 ms/frame OBSERVED |
| Transitions | **+0.0s** | corpus rate is 0.00/25s on the speech route |
| **Zoom, 7 real types** | **+21.8s** | INFERRED — see below |
| | **+19.0s** | → 245.7s |

### The one expensive family is zoom, and the reason is architectural

Today's `build_zoom` is an ffmpeg `zoompan` filtergraph: 2.28s, PSNR-proven to
move (22.79 dB). **Production has no such path.** `PromptlyRender.tsx:979-993`
says it outright, and it was stale until 2026-08-31 in a way that already cost
someone a diagnosis:

> `ffmpeg_base.SIMPLE_ZOOM_TYPES` is now an EMPTY SET, so `categorize_clip()`
> returns "remotion" for EVERY clip carrying a zoomEffect and every zoom paints
> here. […] "3 SnapReframe + 1 StepZoom + 1 LetterboxPush" put FOUR scale-only
> zooms through this composition at ~1000 ms/frame.

All 7 zoom components take `src` — they wrap the video. So porting them
faithfully means video through Remotion at ~9.2x the overlay rate.

INFERRED at production's 1047.8 ms/frame: 0.5 zooms × 1.37s mean natural ×
30fps = 21 frames → 22.0s, replacing 2.28s of ffmpeg = **+21.8s** at reference
density. On a job placing 3 zooms (music, round 33) it is **+132s**.

**This is the ruling I need from Zac** (§ "The one taste call").

## What makes it net-negative on time

The brief asks the port to come out net-negative. It can — and the change that
does it is the same change the port needs anyway: **one Remotion batch.**

Three facts, all observed:

1. `render_components` shells `npx remotion render` (`agentic_editor_app.py:3443`)
   while captions go through `node remotion_batch.mjs`. **Two processes, two
   startups.** `render_remotion_batch`'s own docstring measures the startup it
   removes: bundle 9.79s + selectComposition 2.05s + renderMedia 0.40s =
   **12.24s per process.**
2. `build_overlays` burns text with ffmpeg and re-encodes the whole video:
   **32.20s** for 10 items over a 23.17s output. Those items are alpha content
   over a span the caption layer already covers.
3. `composite_captions` already pays one libx264 pass (3.82s).

| lever | Δ |
|---|---:|
| reel + captions + text into ONE batch (one startup, not two) | **−12.2s** |
| text overlays move from ffmpeg burn into the alpha layer | **−32.2s** |
| 7 real zoom types (INFERRED) | **+21.8s** |
| MG at reference density | **−2.8s** |
| **net** | **−25.4s → ~201.3s** |

Net-negative, as asked. **Still 81s over the 120s ceiling**, and the remaining
overage is `model_thinking` at 152.81s / 67.4% — 12 turns carrying
4× `rule_all_beats` and 3× `execute_plan` (`EXECUTION PASSES: 3 call(s)
refused=1`). That is Builder-1's lane, not mine. **No arrangement of components
reaches 120s while the agent spends 152.81s ruling.**

## The one taste call for Zac

Faithful zoom is +21.8s at reference density and +132s on a 3-zoom job, because
production paints every zoom through Remotion over decoded video.

- **(a) Full fidelity.** All 7 through Remotion micro-segments. Exactly what
  ships today. Costs the time above.
- **(b) Split the register.** SmoothPush / SnapReframe / StepZoom / StagedPush
  are scale-and-origin moves an ffmpeg filtergraph can carry at ~2.3s;
  FocusWindow (dual-view), LetterboxPush (bars over a push) and DepthPull
  (multi-layer) genuinely need Remotion. Roughly 4 of 7 types stay cheap.
  **This resurrects the path production deliberately retired** — and the retirement
  note says the ffmpeg path did not actually render a zoom at all (out_w/out_h
  locked at full source). Rebuilding it means owning a second zoom implementation
  and proving byte-parity against the Remotion one, per the frame-diff law.
- **(c) Fidelity, and take the time from `model_thinking` instead.**

**My recommendation: (c).** (b) trades a taste-approved component set for
seconds we can get more cheaply from a 152.81s thinking budget, and it puts us
back on a path that has already failed silently once. Quality wins over speed —
including reconsidering speed decisions already made.

## What I need before building

1. **Measure this lane's micro-segment ms/frame.** Every zoom number above is
   INFERRED from production's p50, and there are two concrete reasons to think
   that p50 is pessimistic here:
   - This lane's alpha rate (49.0 ms/frame) is already **2.3x better** than
     production's overlay p50 (114.5) — same composition, same content class.
   - **1047.8 was measured under production's default render concurrency.**
     `sweep_micro_concurrency_app.py` exists specifically to sweep that variable
     on micro segments, and **there is no recorded result anywhere in the repo**
     — its own confirmation step is the last thing written about it. Meanwhile
     the identical lever on the overlay path in THIS lane was worth **2.63x**
     (a26925d). If micro responds anything like overlay, the zoom cost is ~+8s,
     not +21.8s, and **the taste call above may not need making at all.**

   **~$0.05, one short Modal run, no synthetic render of a full job.** This is
   the cheapest question in the port and it gates the most expensive decision in
   it. Measure before building (Rule 6).
2. **Zac's ruling on the zoom register** (a/b/c) — only if (1) confirms the cost.

## Five findings, all one class: declared is not observed

Applying the false-green law to the port itself — ask what makes each check
fire, then verify that specific thing exists.

1. **`placement_inert` covers ZOOM AND NOTHING ELSE.** `step_changed_output()`
   is fully generic (`before_path, after_path, t0, t1`) but is called from
   exactly one site: inside `build_zoom` (`agentic_editor_app.py:4228`).
   Round 33 read `PLACEMENT EFFECT: 1 measured moved=1` on a run that declared
   **16 placements** — text 10, card 4, sfx 1, zoom 1. **Fifteen of sixteen
   declarations have no evidence they changed a pixel.**
   This is the finding that should reorder the work: porting 31 MG types and 7
   zoom types under a check that measures one family makes "every component is
   used" a claim about the manifest, not about the video.

2. **Caption liveness is unverified.** `path=remotion composited=True` fires on
   `_cj["ok"] and os.path.exists("/work/captions.mov")` plus an ffmpeg exit 0.
   That proves a file existed and a composite ran. It does **not** prove the
   alpha layer carried visible pixels — a fully transparent `.mov` composites
   successfully and reports exactly the same green. I am **not** reporting the
   caption port as verified working; I am reporting that it rendered.

3. **Captions are gated on the TEXT family, not on speech.** The caption block
   sits inside `if items:` (`agentic_editor_app.py:3723`), so a speech job that
   rules zero text overlays renders zero captions — while the code's own comment
   three lines above says "Captions only where speech exists." Latent in round 33
   (the one speech fixture ruled 10 text items). It would present as silently
   missing captions, never as an error.

4. **The anti-repetition rule is structurally present and unfed.**
   `pick_caption_style(vibe, recent=(), ...)` implements production's rotation
   rule; the only call site is `pick_caption_style(brief)` (line 3746) — `recent`
   is always empty. The docstring says so honestly, which is why this is a wiring
   gap rather than a false green. It needs a per-user style history the agentic
   lane does not currently have; **that is a dependency, and I am naming it now
   rather than shipping the rule inert.**

5. **`bundle_ms` is ledgered and never printed** (captured at lines 2386 and
   3770, printed nowhere). The split between Remotion startup and paint — the
   exact number the one-batch lever above turns on — is being recorded and
   thrown away. This is the standing rule earned 2026-09-07 ("any counter added
   to answer a question gets PRINTED in the same commit that adds it"), broken
   inside the caption code itself. **I could not quote the startup cost from
   round 33 for this document because of it**, and had to fall back on the
   docstring's older in-container figure.

**Not mine, filed to Builder-1:** `run_round.sh` computes `mount_sha` over
`agentic_editor_app.py` alone. The image also mounts `remotion_batch.mjs` and
`/promptly-remotion`. The concurrency-8 fix changed the renderer with **no change
to `mount_sha`** — rounds 32 (299.1 ms/frame) and 33 (49.0) differ 6.1x under
mount shas that could not have distinguished them. The guard refuses mid-round
drift in one file and is blind to it in the others.

## What I build first, and why it is not a component

**Extend placement-effect measurement to text, card, caption and sfx —
RED-proven on each — before porting a single component.**

The instrument already exists and is generic; wiring it is small. The reason it
goes first is finding 1: every component I port lands as a manifest entry, and
the manifest is the only instrument this lane has left since op-counting was
retired. Under today's coverage, a perfectly ported catalogue and a catalogue
that silently composites nothing produce the identical report.

sfx needs its own instrument (an audio-domain diff, not PSNR) — same shape,
different measurement, and I will not pretend a video check covers it.

Then, in cost order: SFX attack table (free) → caption reachability + the nine
styles proven live → MG variety → the one Remotion batch → zoom, after the
measurement in "What I need".

## Ledger

No Modal spend incurred. All figures read from archived round logs
(`/tmp/fixtures/round30..33`) and from source. Proposed next spend: ~$0.05.
