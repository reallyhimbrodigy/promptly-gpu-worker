# What ChatCut's motion-graphic runtime gives a component — measured, by frame

Three questions, one run, no model calls. Each component registered, placed, one
frame read while it was on the timeline, then deleted before the next.

| capability | verdict | what the frame shows |
|---|---|---|
| **two `<Video>` layers** | **MEASURED** | one graphic, the SAME asset at two offsets side by side: left is source frame 0, right is frame 300 — visibly different moments |
| **`spring`** | **MEASURED** | the component ran and drew; a missing global would have thrown |
| **`interpolate` + `Easing`** | **MEASURED** | drawn at partial opacity, consistent with a cubic ease mid-fade |

## What this unblocks

**All nine transitions and both tight-cut overlays.** Every one of them takes
`clipA` and `clipB` and renders both sides itself, and ChatCut's transition slot
accepts only its own thirteen presets with no custom code. The only shape
available was a graphic spanning the cut that draws both sides — which needs two
video layers from one asset at two offsets. That is now proven by frame.

**SnapReframe.** Its curve IS a spring (damping 22, mass 0.6, stiffness 260).
`spring` being available means it ports by CALLING the runtime's solver rather
than carrying a second copy of one — which is the rule the velocity cap's build
step exists to enforce.

## The fourth contract rule, learned here

The first run of this probe was refused three times for my own bug, and said so
once a refusal could carry words:

> Motion Graphic property "text" is declared in properties array but not used in
> code. Remove the property entry or read props.text in the component.

Every declared property must be READ, and every `props.x` read must be DECLARED.
`component_contract` checks both directions now, against the component's own
property table.

## What is still NOT proven

Registering, placing and drawing ONE frame is not the same as a transition
looking right across its span. The port of each transition still needs its own
frames.

## Second run, 2026-09-21 — the still-asset questions

Three frame-composition components need to take a STILL. Nothing in the port had
ever declared an `image` property (0 in the registry), and `<Img>` was not in the
table above — so it was UNKNOWN, not available. One probe, one frame, then
deleted.

| capability | verdict | what the frame shows |
|---|---|---|
| **`Img`** | **MEASURED** | `typeof Img !== "undefined"` rendered **YES**, and the band using it drew the still |
| **an `image`-typed property** | **MEASURED** | delivers a plain **URL string**, 240 chars |
| **`backgroundImage: url(...)`** | **MEASURED** | drew the same still, so CSS is a real second path |

**YOU PASS AN ASSET ID; THE COMPONENT RECEIVES A URL.** The override sent the
36-character asset id `5170f875-…` and the component read a 240-character S3
URL. So a body must treat an image property as a STRING it can put in `src`, and
must not expect the id it was given — and anything that tries to parse the value
as an id will be reading a URL.

## Two more auto-rewrites, which makes three classes

The registration echo carried a warning nobody asked for:

> Auto-fixed: Fixed `<img>` → `<Img>` (Remotion component)

**A plain `<img>` cannot be shipped in this runtime — it is silently converted.**
That is benign here and it is still a rewrite: it means source and registered
code differ for any body containing one, and `registered_diff` will report
DIVERGED unless it knows. It also destroyed half of my own probe: bands A and B
were written to compare `Img` against plain `img`, and the validator made them
the same thing before either rendered. **A probe whose arms the system can
silently merge is not a two-arm probe** — the `Img defined: YES` label is what
actually answered the question, and it answered it only because it was computed
rather than drawn.

The three known rewrites are now: the props-fallback strip, the nested
`({item})` injection, and this.

## A blocked property name, found by being refused

The probe's first registration was rejected outright:

> Blocked property: "prototype" is not allowed

`Object.prototype.toString.call(x)` — the ordinary way to ask what a value is —
is not available. `typeof` plus `Array.isArray` answers the same question and is
what the shipped probe used. Worth knowing before a port reaches for it.
