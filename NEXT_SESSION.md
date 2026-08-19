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

## 3. The four generation-free compositions

**State: BUILT, NOT REACHABLE.** By this session's own standard they are not done.

    in MG_MAP (renderer dispatch)   YES
    in VALID_MG_TYPES               YES  4/4
    in COMPONENT_CONTRACT           YES  typed, required-by-trigger
    named in the prompt catalog     NO   <- no planner can request them
    worker derives atSeconds        NO   <- at_word_index -> seconds missing

Remaining: a catalog entry with a FITS/FIGHTS line per component, the
`at_word_index -> atSeconds` derivation **through `word_frame`** (that is the
whole reason the authority went first), then a cert + the ledger counter for
requested-vs-dropped per type.

`tsc` is not installed here, so `FrameCompositions.tsx` is unverified by a
compiler — only by review. Install or run the bundle build before trusting it.

## 4. Closed this session

- **Attach sweep — CLOSED.** Synthetic orphan injected into production, sweep
  reconstructed the chat in **304s**, both rows cleaned up. FRONTEND unblocked;
  waiting only on Apple. Census: `still_stranded = 0` of 5,406.
- **§8.2 backfill** — 540 renders / 476 users, verified by read-back.
- **Deliverable guard** — 0 executions / 14 failures / 76 jobs / 74 users.
  Deployed and UNEXERCISED; that is a result, not a proof.

## 5. Still open, not queued by the owner

- `dispatch-to-modal.js:751` DISPATCH_UNREACHABLE misattribution + user copy.
- prompt-v2: arm B returned a valid but EMPTY plan on **6 of 10** sources. The
  reads are excellent where they exist (37/37 carry a real read) and it beat arm
  A **+49%** on the 4 productive sources — but 60% silent is not shippable, and
  that is the thing to chase, not the density delta.
- **`generated_scenes` = 0 in BOTH arms** with a scene field available. The
  scene decline is NOT a vocabulary problem; that theory is dead.
- Cert-only modules remaining: `rhythm_dimension.py`, `harness_plan_diff.py`.

## 6. Traps this session paid for — do not re-pay

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
