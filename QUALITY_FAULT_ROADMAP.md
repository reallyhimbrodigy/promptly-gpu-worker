# TWENTY DELIVERED VIDEOS — watched, not measured

First time anyone has looked at the actual output. 20 random completed
deliveries since 2026-07-20, sampled across routes, pulled from the real CDN
URLs users received. `contact-sheets/` has 12 evenly-spaced frames from each;
five full videos are here to play.

## THE HEADLINE, AND IT IS NOT WHAT THE FUNNEL ASSUMED

**Export rate tracks SOURCE quality, not our editing.** The route that adds the
most (standard editorial: cuts, captions, zooms, MGs) has the **lowest** export
rate of any real route. The route that adds almost nothing but has attractive
footage (moodreel) has the **highest**.

| route | delivered | viewed | exported | export % | view→export % |
|---|---|---|---|---|---|
| standard_editorial | 392 | 67 | 39 | **9.9%** | **58.2%** |
| minimal_speech_uncut | 206 | 86 | 31 | 15.0% | 36.0% |
| minimal | 158 | 28 | 6 | **3.8%** | 21.4% |
| moodreel | 140 | 58 | 28 | **20.0%** | 48.3% |
| hype | 12 | 5 | 3 | 25.0% | 60.0% |
| **ALL** | **1000** | **316** | **133** | **13.3%** | **42.1%** |

**Only 316 of 1000 deliveries were ever OPENED.** The "nine in ten never export"
is dominated by *never viewed* (68%), not by *viewed and rejected*. Among people
who actually watch their result, **42% export**.

And standard editorial has the **lowest view rate (17%)** but the **highest
view→export (58%)**. When someone watches the full product, it converts better
than anything else. They just don't come back to watch it.

⚠️ Caveat: these are client-fired analytics. A missing `result_viewed` is not
proof of no view. But the direction is consistent across 1000 deliveries.

## 🔑 THE WIDER GAP: 51% OF TRAFFIC GETS NO EDITORIAL ANALYSIS AT ALL

Only `standard_editorial` makes an editorial planning call. Every plan marker
fires 392/392 on it and **0 on every other route**:

| route | n | source_text_regions | emphasis_moments | video_plan | caption_keywords |
|---|---|---|---|---|---|
| standard_editorial | 392 | 392 | 392 | 392 | 392 |
| minimal_speech_uncut | 206 | 0 | 0 | 0 | 0 |
| minimal | 158 | 0 | 0 | 0 | 0 |
| moodreel | 140 | 0 | 0 | 0 | 0 |
| hype | 12 | 0 | 0 | 0 | 0 |

**Every prompt improvement, component fix, FITS/FIGHTS rewrite and detector
reaches 39% of delivered jobs.** The 22 inherited prompt commits reach 39%.

### Deliberate or evolved? BOTH — and the split is the point

`route_reason` settles it:

| route | reason | n | kind |
|---|---|---|---|
| minimal_speech_uncut | **transcription_incomplete** | 61 | **FAILURE** |
| | no_speech_muted | 56 | content |
| | too_short | 53 | content |
| | **plan_collapsed** | 36 | **FAILURE** |
| minimal | no_speech / muted | 109 | content |
| | too_short | 35 | content |
| | **plan_collapsed** | 9 | **FAILURE** |
| moodreel | no_speech / not_talking_head / no_audio | 134 | content |

**moodreel is the deliberate one and it works** — content-driven routing, and it
has the best export rate of any route at 20.0%.

**`minimal_speech_uncut` is the evolved one: 97 of 206 (47%) are FAILURES** —
transcription we could not complete, or a plan that collapsed — dressed as a
route. Those users did not upload "content that needs no editing". The pipeline
failed and handed back their own footage, and it cost them a credit.

**~106 of 1000 deliveries are pipeline failures delivered as products.**

## THE FAULTS, CLUSTERED (17 of 20 watched; the pattern saturated)

### 1. CAPTIONS ARE ONE WORD AT A TIME, AND TOO SMALL TO READ
Videos 00, 01, 05. Single words — "думать," / "माहिष्मती" / "ACNE," — in thin
white or yellow at maybe 3% of frame height, over busy footage. Nothing to read,
no retention value, and on a light shirt (00) they are genuinely illegible.
Compare video 03, which uses large bold uppercase with yellow keyword highlights
and reads instantly. **The good style exists; most videos do not get it.**

### 2. CAPTION POSITION THRASHES
Video 01: bottom-centre → mid-frame → up beside her head → back to bottom, with
no scene change to justify any of it. Video 03: jumps to top for one word then
back. The anchor is unstable within a single continuous shot.

### 3. SOURCE-TEXT HANDLING — **CORRECTED, I WAS TWO-THIRDS WRONG**
I claimed `source_text_regions` "exists and did not act". It acts: **58 of 392
plans (15%) report a non-empty band list**. Checking the specific videos:

| video | observed | detector | verdict |
|---|---|---|---|
| 05 "Eid Mubarak" top | `['top']` | **FIRED** | worked — we used bottom, top was claimed |
| 04 burned captions | `existing_caption_region: bottom`, `caption_style: none` | **FIRED** | worked — our caption track correctly suppressed |
| 00 "Wednesday 1:30 PM" mid-frame | `[]` | **MISSED** | genuine miss — centre band reported clean |
| 08 / 19 TikTok UI | key **absent** | **never ran** | light routes make no editorial call |

So the real defects are narrower and different from what I wrote:
**(a)** a detector MISS on a centre-band graphic (video 00), and
**(b)** the light routes (`minimal`, `minimal_speech_uncut`, `hype`) never make an
editorial planning call at all, so **competitor UI is invisible to the pipeline
by construction** — no detector inside the plan can ever see it.

That (b) is why the fix has to sit at **INTAKE, before routing**, not in the
editorial prompt.

### 4. WE RETURN COMPETITOR UI
Video 08 is a downloaded TikTok — heart / comment / bookmark / share rail down
the right side and a `Lynne & Tatizz` username watermark — returned **uncut**.
Nobody can post that anywhere.

### 5. THE STATIC TALKING HEAD IS WHERE WE ADD NOTHING
Videos 00, 01, 05, 16 are one person, one framing, one room. Across 12 sampled
frames there is no visible cut, no zoom, no reframe. Video 16 (minimal) has
literally nothing added — no captions, no cuts — and that route exports at 3.8%.
**Our edit is invisible on exactly the footage most users upload.**

### 6. TWO OF TWENTY WERE DELIVERED SIDEWAYS — 10%
Videos 09 (lipstick tutorial) and 14 (apple picking) are rotated 90° for their
entire duration. The subject's face is on its side. This is unmissable and
unpostable, and it is the single most severe fault in the set. Note the known
rotation fix was **validator-path only** — the render path still mishandles it.

### 7. A TEXT OVERLAY THAT JUST REPEATS THE CAPTION
Video 06: frame 1 shows "SMARTEST" as a top overlay while the caption underneath
reads "workout"; frame 2 shows "WORKOUT" on top and "smartest" below. The
overlay is echoing caption words, swapped. It costs a component slot and adds
nothing.

### 8. CAPTION TYPOGRAPHY CHANGES MID-VIDEO
Video 02: Hindi captions render sans, but the embedded English words ("lift",
"service", "suspension") come out in an ITALIC SERIF. Almost certainly a font
fallback for Latin glyphs inside a Devanagari run. It reads as a mistake.

### 9. THE SAME SOURCE, PROCESSED TWICE, RETURNED RAW BOTH TIMES
Videos 08 and 19 are the same downloaded TikTok — one routed
minimal_speech_uncut, one routed hype. Both came back with the competitor UI
intact and effectively no edit. Two credits, two unpostable outputs.

### 10. WHEN THE SOURCE IS RICH, THE PRODUCT IS GOOD
Video 03 (varied scenes) and video 12 (property tour) look postable. Same
pipeline. The difference is entirely the footage.

## WHAT THIS SUGGESTS THE ROADMAP IS

0. **FIX ROTATION FIRST.** 10% of this sample shipped sideways. Nothing else on
   this list matters if the video is on its side, and it needs no taste call.
1. **Caption legibility and density is the highest-leverage fix** — it is the one
   thing on screen in every standard-editorial video, and it is currently
   unreadable in most of them.
2. **Kill the passthrough returns.** minimal at 3.8% is the floor, and it is the
   route where we hand back the upload.
3. **Strip source text / competitor UI, or refuse to deliver over it.**
4. **The static talking head needs a different answer than cuts and zooms** —
   there is nothing to cut to.
5. **68% never open the result.** That is not a video-quality problem and it may
   be larger than one. Worth pricing before more editing work.

## Method

`video_jobs` where `status=completed`, joined to `analytics_events`
(`export_completed` / `result_viewed`) on `props.job_id`. Route from
`edit_recipe.route`, falling back to presence of `cuts`. Frames via ffmpeg,
12 per video, evenly spaced.
