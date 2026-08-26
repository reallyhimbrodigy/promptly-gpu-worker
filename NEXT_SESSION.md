# NEXT SESSION — the queue, in the owner's order

Written 2026-08-19 at the end of a long session. Everything below is stated as
BUILT / REACHABLE / PROVEN separately, because this session's most expensive
lesson was that those three are not the same and the gate only ever checked the
first one.

---

## 1. Migrate the 26 word→seconds sites onto `word_time_s`

**The no-op property IS the verification.** `_SHARED_CLOCK_LEAD_MS` is `0.0`
today, so routing every inline `float(words[i].get("start"/"end"))` through the
authority must produce a BYTE-IDENTICAL plan. If a diff appears, the migration is
wrong — not the baseline.

    authority   handler.py  word_time_s / word_frame / caption_ms_for_frame
    policies    WORD_FRAME_COMPONENT (round)  ·  WORD_FRAME_NEVER_EARLY (ceil)
    audited     26 inline sites, 4 rounding policies, 3 partial authorities

**Do not collapse the two policies.** They are two encodings of ONE instant under
two reveal semantics: a component fires on a frame index; a caption reveals when
`(frame/fps)*1000 >= fromMs`. Rounding a caption down reintroduces the earliness
Zac's 2026-07-15 ruling removed, and there is a gate check on it.

Method: migrate in batches, gate after each, diff a plan from a fixed source
before/after. The lead being 0.0 is what makes this safe; if anyone raises it
first, the migration stops being verifiable.

## 2. Run `cert_timing_rendered_artifact_app.py` ONCE (~$0.30)

Turns the timing guarantee from asserted into observed. It renders a constructed
source, then measures the OUTPUT FILE: first frame whose luma jumps (must equal
the predicted frame, exactly) and the audio transient's sample (must land within
one frame), plus the A/V divergence — which is the failure that actually reads as
a mistake.

Every timing check before this one read the PLAN, which is why the caption-only
lateness of 2026-07-13 needed a human to notice it.

## 3. THE SCENES ZERO IS A HARNESS ARTEFACT — retest it before spending anything else

**Two cells. The control is what makes it readable.**

    arm  premium=True, PROMPTLY_SCENES_DIRECTIVE_V2=1, PLAN_ONLY
    ctl  premium=True, PROMPTLY_SCENES_DIRECTIVE_V2=0, PLAN_ONLY
    same sources, serial, plan-only

**WHY THIS COMES BEFORE THE FRAME-GRAB ARM.** `generated_scenes` is taught ONLY
on the premium path and only behind a dark flag:

    if premium and _scenes_directive_v2():

and the comment says it plainly: *"Appended ONLY on the Lumen/premium path →
free/Flare never sees it → the model never emits a GeneratedScene on the base
path."*

**The 2026-08-18 A/B ran `premium_pipeline_enabled: False` on all 26 cells.** So
BOTH arms were structurally incapable of emitting a scene. `generated_scenes = 0`
in arm A and arm B is not a decline, not a doctrine failure and not a vocabulary
gap — it is the harness measuring a path where the feature is switched off. Same
class as the four corpora that scored correct declines as defects.

**RETIRED FINDING:** "the model could ask for a scene and didn't, so the decline
is not a vocabulary problem." It could not ask. I checked whether the SCHEMA
could express a scene and never whether the PROMPT offered one — verifying the
row instead of the columns.

**The earn-gate is real, already diagnosed, and already rewritten** (dark, behind
`PROMPTLY_SCENES_DIRECTIVE_V2`). The old block's own post-mortem, in handler:

    1. opened "You may emit" — permission, not a trigger
    2. green light was an AND of three conditions, one subjective
    3. FATAL: said leaving it empty is "correct and expected" —
       the prompt blessed the zero it was written to explain

So the flag-off control is not ceremony: it separates "the V2 directive works"
from "premium alone was the whole story".

## 4. FRAMES_PLAN vs PLAN_ONLY — ONLY IF item 3 returns zero

One variable: same doctrine, same schema, same sources, exemplar mode the only
difference. It answers "does the model need to SEE a scene to emit one" — but
ONLY once item 3 has shown the model is actually being asked for one. Running it
before that spends money re-measuring a switched-off feature.

**Already known:** arm B DID carry exemplars in PLAN_ONLY (harness never sets
`PROMPTLY_PROMPT_V2_EXEMPLARS`, so handler defaults to it; the block is 4,795
chars and carries both REF beat lists). So plan-exemplars alone did not move
scenes — but see item 3 for why that conclusion is not yet safe.

`INLINE_VIDEO` stays off the live path permanently. It exists in the mode enum
only so its cost can be priced and rejected on evidence rather than assumed.

## 5. The four generation-free compositions

**State: BUILT, NOT REACHABLE.** By this session's own standard they are not done.

**VERIFIED state at handover (not remembered — read back from the tree):**

    FrameCompositions.tsx exists      YES  4 components, ART_DIRECTION §4
    COMPONENT_CONTRACT                YES  4/4 typed, required-by-trigger
    VALID_MG_TYPES                    NO   0/4  <- BACKED OUT
    types.ts MotionGraphicType        NO   0/4  <- BACKED OUT
    MG_MAP / import in PromptlyRender NO   0    <- BACKED OUT
    named in the prompt catalog       NO        <- no planner can request them
    worker derives atSeconds          NO        <- at_word_index -> seconds

The registration was backed out of all three mirrors ON PURPOSE. Registering
them tripped "EVERY COMPONENT THE RENDERER CAN PRODUCE IS REQUESTABLE AND
TAUGHT" — flagged in the gate as the SEVENTH instance of that class — because
nothing teaches them to the planner. Re-register them ONLY in the same commit
that teaches them; the contract entry is left in place because it is inert
without registration and is the shape the catalog entry should mirror.

Remaining: a catalog entry with a FITS/FIGHTS line per component, the
`at_word_index -> atSeconds` derivation **through `word_frame`** (that is the
whole reason the authority went first), then a cert + the ledger counter for
requested-vs-dropped per type.

`tsc` is not installed here, so `FrameCompositions.tsx` is unverified by a
compiler — only by review. Install or run the bundle build before trusting it.

**Taught with OUR OWN grabs, not abstract references.** The style guide should
show these components, which means they must RENDER before the frame-grab arm
(item 4) can use their stills. Until then item 4's grabs come from the reference
edits. Registering them without a catalog entry trips "EVERY COMPONENT THE
RENDERER CAN PRODUCE IS REQUESTABLE AND TAUGHT" — the gate already refused this
once, correctly, and the registration was backed out of all three mirrors.

## 6. Closed this session

- **Attach sweep — CLOSED.** Synthetic orphan injected into production, sweep
  reconstructed the chat in **304s**, both rows cleaned up. FRONTEND unblocked;
  waiting only on Apple. Census: `still_stranded = 0` of 5,406.
- **§8.2 backfill** — 540 renders / 476 users, verified by read-back.
- **Deliverable guard** — 0 executions / 14 failures / 76 jobs / 74 users.
  Deployed and UNEXERCISED; that is a result, not a proof.

## 7. Still open, not queued by the owner

- `dispatch-to-modal.js:751` DISPATCH_UNREACHABLE misattribution + user copy.
- prompt-v2: arm B returned a valid but EMPTY plan on **6 of 10** sources. The
  reads are excellent where they exist (37/37 carry a real read) and it beat arm
  A **+49%** on the 4 productive sources — but 60% silent is not shippable, and
  that is the thing to chase, not the density delta.
- **`generated_scenes` = 0 in BOTH arms — RETIRED as a finding.** The cells ran
  non-premium with the directive dark, so neither arm was ever offered a scene.
  See item 3. The vocabulary theory is neither dead nor alive; it was never
  tested.
- Cert-only modules remaining: `rhythm_dimension.py`, `harness_plan_diff.py`.

## 8. Traps this session paid for — do not re-pay

- **Look for the tool before writing one.** Wrote `cert_no_orphan_modules.py`
  before finding `sweep_built_not_wired.py`; nearly wired a second re-edit engine
  beside `_deterministic_reedit`, whose docstring says "reuse, never parallel".
- **Grep the repo before spending.** `maxItems` is rejected by Vertex —
  handler.py:19590 has said so since 2026-07-11. I rediscovered it by burning a
  paid A/B cell.
- **Read the error.** Four probe attempts for one `ModuleNotFoundError`: an
  ephemeral app must mount `modal_app.py` explicitly.
- **A long `modal run` dies with its client.** Use `--detach`, and persist
  results FROM INSIDE the container — a result that lives only in the process
  watching the run is not a result.
- **Mutating a module in place poisons `__pycache__`** when size and mtime-second
  match. The gate now runs in a pycache jail.
