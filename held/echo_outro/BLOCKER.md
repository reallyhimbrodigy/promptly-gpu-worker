# HELD — the copy-free echo outro, and the seam it uncovered

**Status: built, mirror-green, and NOT shippable without an owner call.**
Held outside `src/remotion/src/motion-graphics/` because the gates enumerate
components off the filesystem — even sitting there unwired, this directory
tripped the MG attack-table check.

---

## What got built and proved

The full chain, and `brand-mg-wiring.test.mjs` went **14/14 green** with it:

| link | state |
|---|---|
| `build_echo_outro()` producer | built — palette + last frame, no copy |
| `EchoOutro.tsx` component | built — tint ramp, vignette, closing rule |
| `EchoOutroMG` spec adapter | built — fails CLOSED on a missing tint |
| `MG_MAP` dispatch | registered, via the adapter (not the bare component) |
| TS `MotionGraphicType` union | registered |
| mirror test | **14 checks passed** |

Verified behaviour: no headline → echo fires (`start_s` 53.05 + 1.6s hold on a
54.9s edit, ending *with* the cut); headline present → the copy-bearing card
wins and echo is `None`; no design system → both `None`.

## Why it is held — the gate contract, not a bug

Four gates fail, and they all say one thing:

```
motion graphics: every renderable name is REQUESTABLE (29) —
  renderer can produce ['EchoOutro'] but the response schema has no enum
  value for it — BUILT-NOT-WIRED
all 55 renderable component names appear in prompt or guidance text —
  never named to the model: ['EchoOutro']
Python<->TS MotionGraphicType: extra in TS=['EchoOutro']
```

**The existing contract is: anything the renderer can produce must be
requestable by the model and taught in the prompt.** That gate is the SEVENTH
instance of the built-not-wired class and it exists for good reason.

A deterministic, universal, model-invisible component contradicts it by design.
`VALID_RENDER_ONLY_MG_TYPES` — "a type the renderer must accept and Gemini must
never emit" — is honoured by the wiring test and **unknown to the other three**.

So the choice is an owner call, not an implementation detail:

**(a)** Extend render-only support across the three gates. Correct, but it
weakens the exact check that has caught seven instances of this class, and it
needs its own RED proof that render-only types still can't hide a real
built-not-wired defect.

**(b)** Make `EchoOutro` requestable and taught. Cheap and gate-clean, but the
model then decides whether an edit gets a close — which is the 2%-reach problem
the echo exists to solve.

My recommendation is **(a)**, scoped narrowly: a render-only type must be
produced by a `build_*` in `brand_components.py` and dispatched through a spec
adapter, so the exemption cannot be claimed by an ordinary component.

## THE BIGGER FINDING — and this one is not about the echo

While wiring the emission I checked whether the handler ever turns
`_brand_specs` into `motion_graphics_out` entries.

**It does not. There is no emission site at all.**

`BrandSpecMG.tsx` documents "THE CONTRACT WITH THE HANDLER" in detail —
`motion_graphics_out.append({"type": "NamePlate", "fromFrame": ..., "props":
<spec>})` — and the handler half was never written.

So **NamePlate and EndCard have never produced a pixel, even on a job where the
spec was successfully built.** `brand_copy` being empty on 0/198 was the visible
cause; this is the one underneath it, and it would have swallowed the
transcript-triggered plate shipped in v555 exactly the same way.

Anything appended there must also satisfy the integrity invariant at
`handler.py:28540` — `len(motion_graphics_out) + _mg_projection_misses ==
_expected_total_mgs` — which raises rather than warns, so the count has to be
declared, not just appended.

**This is the next thing to fix, ahead of the echo.** A universal close that
cannot reach the renderer is worth nothing, and neither is the plate.
