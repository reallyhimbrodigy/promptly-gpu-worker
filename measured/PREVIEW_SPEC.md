# Preview spec — every menu component, derived from its own curve

For Builder 1's `preview_spec_plan` / `extract_clip`. All frames are at 30fps
and are **offsets into the component's own window**, counted from the placed
item's first frame — the harness adds the item's `from`. Nothing here is
derived from a placement; every number comes from the body or the registered
property table, which is the thing that went wrong when it was derived from a
placement once before.

## THE HEADLINE: ALL TWELVE GET A CLIP. NONE GETS A STILL.

Every component on the menu animates on entrance. There is no genuinely static
one, so there is no component for which a single frame is the honest preview.
A still of any of them is a picture of the resting state with the entrance —
the part that makes it read as motion graphics rather than a caption — removed.

That also means `preview_spec_plan` should report **zero** UNSPECIFIED for the
menu. If it reports any, the spec and the menu have drifted and the drift is the
finding.

## Group A — SIX of the seven I ported. Entrance is a position ease, then rest.

The curve is identical in these six, and it is in each body verbatim:

    const t = Math.min(Math.max(frame / Math.max(1, Math.round(0.28 * fps)), 0), 1);
    const ease = 1 - Math.pow(1 - t, 3);

`Math.round(0.28 * 30)` = **8 frames**. The entrance is complete at frame 8 and
the component is static from frame 9 until its item ends. Position eases; opacity
does not — this repo's caption law is FRAME-1-IS-FINAL for readable text, so the
words are legible on frame 1 and the motion is a rise, not a fade.

    component      clip frames   length   what the clip shows
    PlainText          0 – 36     1.2s    rise and settle, then a second at rest
    CaptionMatch       0 – 36     1.2s    same curve, caption-styled face
    LowerThird         0 – 36     1.2s    name/role rise behind the accent rule
    QuoteCard          0 – 36     1.2s    quote and attribution rise
    TornPaper          0 – 36     1.2s    both strips rise together
    StickyNotes        0 – 45     1.5s    LONGER ON PURPOSE — three notes, each
                                          offset by (1 - ease) * (26 + i*10), so
                                          the third note is still arriving when
                                          the first has landed. 36 frames cuts
                                          the stagger; 45 contains it.

## EmojiCard is NOT in group A, and I nearly put it there.

I wrote "the curve is identical in all seven" and then checked, and six of the
seven carry `0.28 * fps`. EmojiCard carries neither that nor an ease — it is
TWO SPRINGS:

    const enter = spring({ frame, fps,
      config: { damping: 24, mass: 0.7, stiffness: 190 }, ... })
    const pop   = spring({ frame: frame - Math.round(fps * 0.22), fps, ... })

The card enters on the first spring from frame 0. The badge pops on the SECOND,
which does not start until `frame - round(0.22 * 30)` = **frame 7**, and the
body's own note puts that pop at ~0.4s. So the badge is still arriving around
frame 19-25, long after a 36-frame clip would have been cut.

    component      clip frames   length   what the clip shows
    EmojiCard          0 – 45     1.5s    card springs in, THEN the badge pops
                                          at frame 7+. A 36-frame clip shows the
                                          badge mid-pop and reads as a glitch.

Recorded rather than quietly fixed, because the error is the one this repo keeps
making: I inferred a universal shape from six sampled instances and was about to
hand Builder 1 a number that would have shot one of the twelve in the wrong
place — which is exactly the failure he described from deriving windows off a
placement.

## Group B — the five from the catalogue. Entrance is `enterFrames`.

Read from the registered property table on 6c0ca574, not from the source:

    component     durationMs  enterFrames  exitFrames   clip frames  length
    StatCard         3000         32           12         0 – 60      2.0s
    Stamp            3000         30           16         0 – 54      1.8s
    RankedList       3000         20           18         0 – 54      1.8s
    PillCluster      3000         24           16         0 – 48      1.6s
    Reticle          3000         16           16         0 – 45      1.5s

Each clip is `enterFrames` plus roughly a further second of rest, so the preview
shows the thing arriving AND what it looks like once it has arrived.

**Four of the five need more than their entrance to read correctly:**

  StatCard     the number counts `fromValue` 0 -> `value` 20,000,000 across the
               entrance. A clip that stops at frame 32 shows the count still
               running and never shows the figure. 60 lets it land and hold.
  RankedList   rows are staggered, so row 3 arrives after `enterFrames`. 54.
  Stamp        `entryScale` 1.28 means it lands OVERSIZE and settles to 1.0;
               the settle is the strike. Stopping at 30 shows it mid-strike.
  Reticle      the scan line animates for the whole window, not just the
               entrance, so any frame range reads as moving. 45 is enough to
               see the line travel.

**The hard ceiling for group B: `durationMs` 3000 = frame 90.** The component
has exited by then and renders nothing. Every clip above ends well inside that,
but a spec that ever asks for frames past 90 on these five is asking for empty
frames — and empty frames are indistinguishable from a component that failed.

## What a clip must carry beside the pixels

The **body sha** the clip was rendered from. A preview is evidence about the
code that drew it and no other code; seven of my eleven stills turned out to
photograph bodies I had re-authored hours later and every one still looked fine.

## One thing the inventory must not claim

Builder 1 measured captions occupying **0.367–0.666 of frame height across all
nine styles**. Seven of the twelve default to `position: "middle"`. So any
inventory line calling a component "centred" is describing a region captions
usually own, and a preview clip rendered without captions shows a placement the
user will not get once captions are on. Either the previews carry captions, or
the line says "centre, behind captions" — but it cannot silently say "centre".
