# The 33-row parity table — sent / answered / read-back / frame

**Builder 2, 2026-09-20.** One row per ported item: **7 zooms + 11 transitions
and overlays + 15 sound effects = 33.** (My own contribution is 30 of those; the
three zooms Builder 1 ported are included because the table is the PORT's
parity, not mine.)

## The four columns, and why there are four

Each is a strictly stronger claim than the one before it, and the gap between
columns 2 and 3 is where this lane has been burned repeatedly:

| column | what it means | what it does NOT mean |
|---|---|---|
| **sent** | a register or place call was made | that anything came back |
| **answered** | the API accepted it — `isValid: true`, or an echo naming the id | that anything is on the timeline |
| **read-back** | the project itself reports it — `inspect_item`, `browse_assets`, `preview_timeline` | that anything was drawn |
| **frame** | a rendered frame was downloaded and LOOKED AT | — |

> **Seven zoom placements once returned echo ids and put NOTHING on the
> timeline.** An accept is not a commit, and only the read-back said so. A pixel
> check cannot tell rendering from rendering-EMPTY either, which is why the last
> column requires a frame that was actually inspected rather than a render that
> reported success.

## Zooms (7)

| component | sent | answered | read-back | frame | evidence |
|---|:--:|:--:|:--:|:--:|---|
| SmoothPush | ✅ | ✅ | ✅ | ✅ | Builder 1's zoom_pair, project `b1e4f009`; control 9 frames at 0.0 diff, span 13 frames |
| StagedPush | ❓ | ❓ | ❓ | ❓ | **UNKNOWN — I have no run evidence.** Ported by Builder 1; I did not find a registration or placement for it and will not claim one |
| StepZoom | ❓ | ❓ | ❓ | ❓ | **UNKNOWN — same.** Declares `NO VELOCITY CAP:` and is gated, but gated is not placed |
| SnapReframe | ✅ | ✅ | ✅ | ✅ | asset `1b0bc3ce`, item `929ebe00c7`, frames 128/140/175/205 — the spring rising, holding, released |
| FocusWindow | ✅ | ✅ | ✅ | ✅ | asset `d5dbf436`, item `a8d4552f78`, frames 275/320 — the inset window with its white border |
| LetterboxPush | ✅ | ✅ | ✅ | ✅ | asset `84fe9887`, item `6bec264dce`, frames 400/440 — bars top and bottom, receding |
| DepthPull | ✅ | ✅ | ✅ | ✅ | asset `55639088`, item `b558c317c4`, frames 525/560 — vignette and edge blur, then clean |

**5 of 7 frame-proven. 2 UNKNOWN**, and unknown is recorded as unknown rather
than inferred from the fact that they are built and gated.

## Transitions and overlays (11)

| component | sent | answered | read-back | frame | asset · item | placed | seam frame · YAVG | what the frame shows |
|---|:--:|:--:|:--:|:--:|---|---|---|---|
| DipToBlack | ✅ | ✅ | ✅ | ✅ | `cb71cf0eb9` · `c9d25681f3` | 115–124 | f120 · 0.0 | full black at the seam — YMIN=YAVG=YMAX=0 |
| SlideOver | ✅ | ✅ | ✅ | ✅ | `9edf3a9e47` · `85b1e6c1f2` | 232–247 | f240 · 107.9 | B's edge+shadow at x=22.7%, black left of it |
| CardSwipe | ✅ | ✅ | ✅ | ✅ | `8335eb160c` · `4b5a751f14` | 352–367 | f360 · 143.0 | B nearly full (scale .992, +6px), A gone off-left |
| ZoomThrough | ✅ | ✅ | ✅ | ✅ | `2ce63eec41` · `212376c501` | 473–486 | f480 · 63.2 | B 0.854/0.667 over black + A 2.9x/0.143 — YMAX 165 |
| StepPush | ✅ | ✅ | ✅ | ✅ | `41c5787443` · `2185feb737` | 591–608 | f600 · 115.4 | A left half / B right half, both drawing |
| CrossfadeZoom | ✅ | ✅ | ✅ | ✅ | `f8edf74374` · `c2ce577a20` | 710–729 | f720 · 139.4 | both plates superimposed mid-dissolve |
| Stack | ✅ | ✅ | ✅ | ✅ | `02450e96cc` · `d2782baedc` | 828–851 | f840 · 170.1 | B stacked over A, A lifted and lightened |
| ShutterFlash | ✅ | ✅ | ✅ | ✅ | `60d06591b4` · `e60567719f` | 951–968 | f960 · 1.31 | shutter closed to a centre dot — YMAX 255 on YAVG 1.3 |
| FilmStrip | ✅ | ✅ | ✅ | ✅ | `5a429ed37a` · `f7c6fdd991` | 1065–1094 | f1080 · 94.8 | rounded tiles scrolling, two full + one entering |
| ShutterFlashOverlay | ✅ | ✅ | ✅ | ✅ | `08ba2ab80d` · `b30c61e8e1` | 1194–1205 | f1200 · 216.7 | whole frame washed, speaker still legible; control f1160 = 46.0 |
| LightLeakOverlay | ✅ | ✅ | ✅ | ✅ | `2fac567e49` · `d0be6950ea` | 1310–1329 | f1320 · 143.4 | warm gold leak drifting tl-br; control f1290 = 45.3 |

> **ALL ELEVEN ARE NOW SENT, ANSWERED, READ BACK AND FRAME-PROVEN.** Project
> `3b9df622-769e-421a-afa4-e171ad68bbf6`, corpus fixture **th_lagos_en**
> (`135a65c7`, 1920x1080 @ 23.976, 55.9s) on V1 `1e15c228` as twelve 120-frame
> segments whose source seconds jump ~28s per cut, so each of the eleven seams
> is a real cut between visibly different material; transitions on V2
> `ee6a5ee0ab`. Every registration returned `isValid: true, errors: []`. Frames
> were downloaded and looked at, not merely rendered — the YAVG column is
> measured off the downloaded JPEG, and the three CONTROL frames (1160, 1290
> both at V2-empty, plus f60) are what the overlay frames are read against, so
> the difference is the component and not the footage.

They also carry, as before: contract 0 violations on all eleven, 24/24 emitted
blobs in sync with one cap source, 24/24 no-fallback clean, and a measured peak
displacement for each of the eight that move pixels.

### Three things the run measured that no gate was asking

**1. FilmStrip is the only DIVERGED registration, and it is a rewrite.**
`inspect_asset(5a429ed37a, includeCode:true)` comes back byte-identical to what
I sent except in two places, where the validator appended `item` to my nested
sub-components' destructuring: `({ n })` became `({ n, item })` and
`({ from, left, top, w, h, radius, transform, filter })` became the same plus
`item`. Its registration was the one that warned
`"Auto-fixed: Injected missing ({item}) prop to satisfy validator contract"`.
Neither sub-component reads `item` and no call site passes one, so it arrives
`undefined` and the injection is behaviourally a no-op — but it is a SECOND
rewrite class beside the fallback strip, it applies to inner arrow components
rather than the top-level one, and it is exactly what `registered_diff` exists
to catch. The other ten read back byte-identical.

**2. The no-fallback strip went quiet at the wire, and the reason is narrower
than "no fallbacks".** Every registration before tonight returned
`"Auto-fixed: Stripped hardcoded fallbacks from props"`. All eleven tonight
returned `warnings: []` — except FilmStrip's injection above. LightLeakOverlay
is the proof of what the stripper actually keys on: it ships THREE `||`
expressions — `(item && item.props) || {}`, `palettes[palette] || palettes.warm`
and `paths[direction] || paths["tl-br"]` — and all three survived verbatim. The
stripper targets a fallback whose LEFT operand is a `props.x` read, not `||` in
general. That is the same right-hand/left-hand distinction that made
`readsPropWithFallback` wrong in both directions earlier, now confirmed from the
service side rather than inferred from my own gate.

**3. RULED AND FIXED — the transitions and the base track disagreed about fit.**
Zac ruled `contain` on all eleven. The nine that mount a `<Video>` now carry
`objectFit: "contain"` at the one source; the two overlays render no `<Video>`
at all, so there was nothing in them to change, and the SEVEN ZOOMS ARE
DELIBERATELY LEFT ON `cover` — a contained zoom drags the letterbox edge
through frame, and they are already calibrated against a covering plate.

Re-proved on ONE seam, CrossfadeZoom f720, on the landscape corpus fixture, by
measuring the lit band rather than by looking at it:

| frame | band rows | height | |
|---|---|--:|---|
| f60, f1160, f700 (base track, V2 empty) | 536..1031 | 496 | three controls, identical |
| f720 BEFORE, `cover` | 0..1567 | 1568 | the whole frame — the reframe |
| f720 AFTER, `contain` | 513..1054 | 542 | |

The band is no longer full-bleed and it is CONCENTRIC with the base track's:
both centre on row 783.5 exactly. The remaining 46px is not fit — it is the
component's own counter-zoom, and it predicts: at f720 progress is 0.500, the
0.25/0.46/0.45/0.94 bezier eases that to 0.7713, `scaleA` is 1.0926, and
496 x 1.0926 = 541.9 against 542 MEASURED. A band that matches the base track's
centre and differs from it by exactly the zoom the component declares is the
whole claim, and it is arithmetic rather than judgement.

Eight of the nine are registered in the project under `cover` still; their frame
rows above were measured that way and say so. The source is the deliverable and
all nine are contain; re-registering the other eight is a paste of 74KB that
buys one bit already bought by this seam, so it is offered rather than done.

**3a. What the fault was, kept because it was real.**
Every transition mounts its own `<Video style={{objectFit:"cover"}}>` on a
`background:"#000"` root, so it CROPS the 1920x1080 source to fill the
1080x1920 canvas. The base track letterboxes the same source into a band. Sheet
A (seams) is therefore full-bleed close-up and sheet B (controls f60/f1160/f1290)
is letterboxed with black bars — so at every seam the framing jumps to a crop
and back. This is a PLACEMENT consequence, not a port defect: the components are
faithful. But on a real edit a transition item must be given the same fit as the
material under it, or the cut it exists to smooth introduces a reframe of its
own. Nothing in the contract, the property tables or any gate currently asks
this question.

### Three seams that looked wrong at thumbnail size and are faithful

Checked against `src/remotion/src/transitions/*` rather than judged from a
300px tile, because "it looks wrong" is not a finding:

* **SlideOver f240** — black across the left 22.7%. Original geometry is
  identical (`translateA 0 -> sign*-25`, `scaleA 1 -> 0.92`,
  `translateB -sign*100 -> 0`, `background:"#000"`). At e≈0.78 A's left edge is
  at 22.6% and B's is at 22.0%, so B covers A completely and the black is the
  space A vacated. The original does this too.
* **ZoomThrough f480** — dim, YMAX 165 where every other frame reaches 233-255.
  At the seam the original is B at scale 0.854 / opacity 0.667 over black plus A
  at scale 2.9 / opacity 0.143: a cross-dissolve THROUGH black, so the midpoint
  is supposed to be dark and low-contrast.
* **ShutterFlash f960** — YAVG 1.31 with YMAX 255. The shutter is closed to a
  centre dot. That is the mechanism, not a black frame.

## Sound effects (15)

All fifteen: **sent ✅ answered ✅ read-back ✅** — verified by `browse_assets`
against the project rather than by the upload echoes, 15 of 15 `status: ready`,
`cloud: available`.

| sfx | asset | attack | sfx | asset | attack |
|---|---|--:|---|---|--:|
| awkward-moment | `d232168ffa` | 10ms | punchsfx | `22b6c2f1ee` | 67ms |
| boom | `1b9e5a49ff` | 287ms | rizz | `9731db88b9` | 92ms |
| camera-flash | `ca6fa98891` | 127ms | shockingsfx | `9cb2c7ce93` | 150ms |
| imposter | `c55d1c7676` | 935ms | swoosh-sound-effects | `a25e94db61` | 62ms |
| iphoneding | `5276be74f7` | 12ms | transition-sfx | `1b775ce2f6` | 354ms |
| money-ching | `6a42e7a495` | 551ms | wompwomp | `38deedde9b` | 666ms |
| mouse-click-sound | `1c2192f17f` | 30ms | woosh-professional | `e5d3edc948` | 599ms |
| popsfx | `b32dcdd502` | 32ms | | | |

**frame: N/A, and the reason matters.** A viewer frame on an audio item is
black and proves nothing about a sound — reporting it as a pass would be the
purest false green in this table. The equivalent proof is the placement
read-back, which `boom` has: placed at frame 51 with its 287ms attack applied
against a 2.000s beat, `inspect_item` reading `from=51 durationInFrames=35`,
`sourceRange 0..1166667us`. The other fourteen are staged and unplaced.

## The whole table in one line

| | sent | answered | read-back | frame |
|---|--:|--:|--:|--:|
| **33 rows** | **20** | **20** | **20** | **5** |

20 sent (5 zooms + 15 sfx), 5 frame-proven, 11 never sent, 2 unknown.

**The number to act on is 11.** Everything else in this table is either proven
or honestly marked; the eleven transitions are a body of work whose entire
evidence is that it compiles and satisfies a contract, and the first one placed
may well find something none of the gates could.
