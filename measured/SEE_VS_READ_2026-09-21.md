# SEE vs READ — what their agent actually gets, measured 2026-09-21

Three surfaces, read live on `6c0ca574`. Nothing here is inferred from a
tool description.

## 1. THE MEDIA POOL LISTING CARRIES NO PIXELS AT ALL

`browse_assets(type="motion-graphic")` returns, per asset and nothing more:

    id · name · type · durationMs · folder · status · dimensions
    editableProperties[]  -> {key, type, defaultValue}

No thumbnail, no preview URL, no frame, no image of any kind. **The media-pool
listing is a NAME and a DEFAULTS TABLE.** That is the whole of what an agent
browsing the pool gets before it opens anything.

So Zac's diagnosis was right and is now measured rather than asserted: their
agent has been choosing from bare names and empty defaults, because at the
browse step there is nothing else to choose from.

## 2. PIXELS ARE REACHABLE, BUT ONLY THROUGH inspect_asset

`inspect_asset(assetId, sourceFrameCount=N)` returns a `frames` object:

    status: "available"      renderedBy: "frontend"      grid 3x1
    cells sampled at 0.000s / 3.500s / 7.000s of the 8000ms asset

`renderedBy: "frontend"` is the load-bearing word: the contact sheet is drawn by
the OPEN EDITOR'S WEB RENDERER. It is a real render of the component, not a
stored poster — which is why it can exist at all for a motion graphic with no
video file, and why it is only available while an editor session can serve it.

## 3. AND SIX OF THE TWELVE RENDER BLACK

Two sampled, both at `sourceFrameCount=3`:

    PlainText   f0 legible · f105 legible · f210 legible     ALL THREE READ
    Reticle     f0 BLACK   · f105 BLACK   · f210 BLACK       NOTHING READS

Reticle is black for TWO INDEPENDENT REASONS and they need separate fixes:

**(a) It stops drawing at 3s of an 8s asset.** The asset is registered
`durationMs: 8000`; the component carries its own `durationMs` property
defaulting to **3000**. Past 3s it renders nothing, so 5 of every 8 seconds are
empty — and `inspect_asset`'s default sampling spreads across the ASSET, so two
of its three cells land in the dead zone by construction. **62% of the asset's
timeline is blank.** This is not only a preview problem: a default placement of
the 8s asset puts 5s of nothing on the timeline.

**(b) It is invisible at frame 0.** `enterFrames: 16`, entering from zero, so
the first frame of its own window is blank. PlainText is legible at f0 because
the ported bodies obey this repo's caption law — FRAME-1-IS-FINAL, position
eases, opacity does not.

**THE SPLIT IS EXACTLY THE PORT BOUNDARY**, which is what makes the cause
credible rather than coincidental:

    carry durationMs: 3000 (the catalogue five + StickyNotes)
      PillCluster · RankedList · Reticle · Stamp · StatCard · StickyNotes
    no durationMs property (the six I ported)
      CaptionMatch · EmojiCard · LowerThird · PlainText · QuoteCard · TornPaper

MEASURED: 2 of 12 (PlainText legible, Reticle black).
PREDICTED, and labelled as prediction: the other five carrying `durationMs:
3000` go black past 3s by the same mechanism. Frame-0 legibility is a SEPARATE
question per component and is not predicted from this — `smoke_poster_frame_
legible` reasons about it from the bodies.

## 4. NAMING: ONE OF TWELVE

Only `PlainText — bold line on the picture, for one claim` carries the
descriptive name. The other eleven are bare (`Reticle`, `StatCard`, ...). The
convention was ruled for all twelve and is applied to one, and `asset.name` is
the ONLY per-asset free text a motion graphic has — asset.description is
write-only and AudioAsset has neither field.

## 5. THE CANARY: PLANTED, VERIFIED ON OUR SIDE, NOT YET ANSWERED

Both words are present and both are READABLE BACK BY US:

    designSpec.styleGuide  CANARY-KESTREL   via manage_design_style(get)  CONFIRMED
    project.description    CANARY-MARLIN    via read_project              CONFIRMED

Note the scope correction this forces: `description` being **write-only** is
true of **asset.description**, not of **project.description**, which
`read_project` returns in full.

**NEITHER HAS BEEN ANSWERED, and I cannot answer it.** The canary asks whether
THEIR agent reads either surface at ruling time, which only their agent's reply
can say. I checked the tool surface: of the ~50 ChatCut MCP tools, none submits
a prompt to their in-app agent. `web_browser` exists but driving their chat box
through it is not a measurement I would trust and not a cost I would spend
unasked.

So the canary needs one of two things, both Zac's:
  - a line typed in the box on a scratch duplicate, costing nothing, or
  - the next brief, whose chat text answers it as a side effect.

Whichever word comes back names the surface; the other is dropped rather than
carried on a guess. **Until then, which surface their agent reads is UNMEASURED,
and the menu lives in the styleGuide on an assumption, not a finding.**
