# Remotion's own conventions, audited against this catalogue (2026-08-24)

Source: remotion-dev/remotion `AGENTS.md` + `.agents/skills/remotion-markup`
(their agent-facing component-authoring rules, v4.0.516; we run 4.0.450).
Full audit: 184 interpolate calls, 26 component files. Every rule below is
marked ADOPTED (already true), FIXED (this commit), FORWARD (the law for every
future craft pass, applied with render-proof when a component is touched), or
NOT ADOPTED (with the reason).

## ADOPTED — already compliant

- **Frame-driven animation only** (`useCurrentFrame` + `interpolate`; CSS
  `transition`/`animation` never render correctly): zero violations found.
- **Clamp frame-driven interpolates**: all 148 frame-input calls clamp.
- **Deterministic randomness**: `hash01(i)` everywhere (≡ their seeded
  `random()`); no `Math.random`.
- **One-frame render check**: `render-mg-proof.mjs` exceeds their
  `remotion still` suggestion (multi-frame, before/after, references).

## FIXED — this commit

- **Font loading**: optionless `loadFont()` pulled every weight+subset —
  the SDK printed its own warning in our archive logs (63–126 requests per
  family per render). Now constrained to the censused weights + latin/latin-ext
  (see `shared/fonts.ts`; the census includes the `FONT_WEIGHT` indirection
  maps). A new weight must be added there or it silently synthesizes.
  Render-verified: zero warnings remain from MG families. FOUND, NOT
  TOUCHED: `captions/shared/fonts.ts` loads 10 families optionless (the
  remaining 65 warnings) — constraining it interacts with the multilingual
  Noto-fallback design (its primary fonts only ever need Latin coverage by
  design, so latin+latin-ext SHOULD be safe), but captions render user
  transcripts and that subsystem's changes require the by-language render
  vetting pass. Flagged for its own slice.

## FORWARD — the law for every future craft pass

- **fps-relative keyframe ranges** (`n * fps`, or ms-based like
  `cappedEntranceProgress`): 80 raw-frame ranges remain — fps-dependent by
  construction (the entrance-cap work measured exactly this class:
  peak_step 0.46 from an 8-frame range). Entrances are already covered by the
  ms-based cap system; non-entrance timings (pulses, rules, labels) convert
  as components are touched, render-proven.
- **`scale`/`translate`/`rotate` properties over `transform` strings**
  (26 files use strings, 0 use properties): more Studio-editable and
  independently composable. CAUTION: CSS individual properties apply in fixed
  order translate→rotate→scale — convert only where the authored string order
  matches, and render-prove (a reordered transform is a different composition).
- **`Easing.*` module over hand-rolled cubics** on new code (`easeOutCubic`
  duplicates `Easing.out(Easing.cubic)`); existing call sites are correct,
  convert opportunistically.
- **`output: 'perceptual-scale'` for scale animations**: adopt when we
  upgrade past 4.0.450 if available; check on upgrade.

## NOT ADOPTED — deliberate, with reasons

- **Inline `interpolate()` in the style prop + `Interactive.*` wrappers**:
  those exist for Remotion Studio's write-back editing. This catalogue is
  headless — components are typed instances driven by the worker's
  edit_recipe; there is no Studio editing surface. Precomputed consts shared
  across sibling nodes stay.
- **Blanket-clamping ALL interpolates**: the naive rule misses two cases we
  rely on: (1) spring-driven interpolates are deliberately UNCLAMPED — the
  overshoot past the input range IS the designed bounce (Stamp's press,
  DropBanner's card); clamping kills it. (2) bounded-progress inputs
  (clamp01/useMGPhase outputs) make extrapolation unreachable — a clamp is
  dead code. Frame-driven calls (the case their rule exists for) all clamp.
- **`<Sequence>`-based delays**: `useMGPhase` is the system-wide phase
  contract (enter/exit windows, durable timing, exit progress). Replacing it
  per-component would fork the timing model the whole catalogue shares.
- **Nullable-over-optional internal params**: their rule for Remotion's
  internal APIs. Our props ARE the wire format of the worker's edit_recipe
  JSON — optional keys are the contract.
- **Bun/turbo setup, Studio dev loop**: repo-tooling sections, not
  applicable to this vendored render tree.
