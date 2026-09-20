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

| component | sent | answered | read-back | frame |
|---|:--:|:--:|:--:|:--:|
| DipToBlack | ❌ | ❌ | ❌ | ❌ |
| SlideOver | ❌ | ❌ | ❌ | ❌ |
| CardSwipe | ❌ | ❌ | ❌ | ❌ |
| ZoomThrough | ❌ | ❌ | ❌ | ❌ |
| StepPush | ❌ | ❌ | ❌ | ❌ |
| CrossfadeZoom | ❌ | ❌ | ❌ | ❌ |
| Stack | ❌ | ❌ | ❌ | ❌ |
| ShutterFlash | ❌ | ❌ | ❌ | ❌ |
| FilmStrip | ❌ | ❌ | ❌ | ❌ |
| ShutterFlashOverlay | ❌ | ❌ | ❌ | ❌ |
| LightLeakOverlay | ❌ | ❌ | ❌ | ❌ |

> **ELEVEN OF THIRTY-THREE ARE AUTHORED, BUILT AND GATED — AND HAVE NEVER BEEN
> SENT.** This is the honest headline of the table and it should not be softened.
> Each one passes the component contract, carries its property table, emits
> through the one-source build step and holds the no-fallback rule. None of that
> is evidence it draws. `built` is not `committed` is not `deployed` is not
> `working`, and every one of these sits at `built`.

What they have instead, which is real but is not parity: contract 0 violations
on all eleven, 24/24 emitted blobs in sync with one cap source, 24/24
no-fallback clean, and a measured peak displacement for each of the eight that
move pixels.

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
