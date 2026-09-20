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
