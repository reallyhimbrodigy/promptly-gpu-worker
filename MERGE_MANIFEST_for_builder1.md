# Merge manifest — lane/duration-producer → lane/agentic-editor

Zac's ruling 2026-09-12. Builder-1 owns the merge. This is what I know about the
collisions, measured against the tree round 66 is mounting (`1aa9317`), so the
fourth collision does not have to be discovered by conflict.

**Do not merge while a round is live.** Round 66 is on `1aa9317` and my lane is
not an ancestor of it, so everything below is safe to prepare and none of it can
drift that round's fingerprint.

## Already done on my side, so the merge has less to resolve

- **The cutaway gate is retired.** `smoke_five_families` asserted
  `"cutaway" not in _TREATMENT_FAMILIES` and required exactly six families. It
  now accepts six **or** seven and the "cutaway is back" leg is retired
  outright, with the ruling recorded in place. A leg that contradicts a decision
  is worse than no leg, so it is gone rather than weakened — but the property it
  protected still holds: a family cannot leave the list silently, and the
  members are still named so the set cannot change identity.
- **`geometry_normalise_filter` is renamed on my side** to
  `delivery_geometry_chain`. Yours keeps the name, per the ruling. Mine returns
  a plain comma chain with no placeholders; yours takes `framing` and returns a
  labelled multi-segment graph. Renaming removes a conflict whose *silent*
  resolution would swap one contract for the other — which is the failure that
  cost you five "Too many inputs specified for the scale filter".

## The one where MY side has to win

**`derive_card_type`** — and this is the item I would most like you to check by
hand rather than let a merge tool decide.

```
mine  : (hero, beat_text, vibe, condition, card_props)
theirs: (hero, beat_text, vibe)
```

Your lane does not have the condition/props derivation at all. Mine carries the
whole card selection layer: `MG_CONDITIONS`, `condition_components`,
`MG_UNIQUE_PROP_OWNER`, `card_condition` and `card_props` as ruling fields, and
the precedence **props > figure-in-hero > condition > PullQuote**.

**If the merge takes `theirs` here, my schema's `card_condition` and
`card_props` fields survive with no deriver that reads them.** That is an
orphaned demand at merge scale: two fields the agent is asked for and nothing
consumes, which reads to the agent as a question worth answering and produces
nothing. My `_assert_build_reads_only_stored_fields` would not catch it, because
those fields would still be *stored* — they would simply stop *deciding*.

## Signature collisions, all seven

| function | who is the superset | note |
|---|---|---|
| `admit_verdict` | **theirs** (`can_express`) | your surface-scoping param; take theirs and my body's extra arms fold in |
| `half_ruling_refusal` | **theirs** (`can_express`) | same |
| `edit` | **theirs** (`offer_readers`, `prefix_removals`) | |
| `main` | **theirs** (`prefix_removals`) | |
| `render_remotion_batch` | **theirs** (`led`) | |
| `derive_card_type` | **MINE** | see above — the only one where theirs loses |
| `geometry_normalise_filter` | true conflict | resolved by rename, above |

## Constant collisions — all of them are the cutaway retirement

Theirs wins on every one, per the ruling:

- `_TREATMENT_FAMILIES` — theirs has `cutaway` (7), mine removed it (6)
- `REFERENCE_PER_25S` — theirs has `cutaway: 4.22`
- `REFERENCE_PER_25S_NOSPEECH` — theirs has `cutaway: 0.0`
- `_CUTAWAY_MIN_S` / `_CUTAWAY_MAX_S` / `_CUTAWAY_MIN_DIFF` — yours only

Note the treatment **enum** must move with `_TREATMENT_FAMILIES`: my
`_assert_treatment_surface_agrees` compares every schema enum containing
`none`+`card` against the declared list and raises at import if they disagree.
It fired on me when I tried to add cutaway to one and not the other.

## A fourth collision, same class, not yet costed

**`DERIVED_VERDICT_FIELDS` (mine) vs `BOUNDARY_DERIVED` (yours)** — two names
for one concept: fields the boundary computes rather than asks for. Both
currently hold `sfx`. After the merge there would be two mechanisms doing the
same job, which is how `cut` and the sfx field got here. Worth folding to one
name in the merge rather than after it.

## What my import-time certs will demand of the merged tree

These run at import in the container, so a bad merge fails at launch rather than
quietly at build. That is the intent, but you should know what they enforce:

1. `_assert_one_admission_surface` — nothing may `.append`/`.extend` into
   `led["beat_verdicts"]` outside `admit_verdict`. Whole-list rebinds are
   allowed (seeding a re-edit from a prior plan is legitimate).
2. `_assert_verdict_surfaces_offer_the_same_fields` — `rule_all_beats` and
   `beat_verdict` must offer identical field sets. My `KNOWN` exception set is
   **empty**: I closed the eight-field gap by deriving `beat_verdict`'s
   properties from the plural tool's item schema (`_sync_verdict_surfaces`). If
   your `beat_verdict` differs, either keep my sync or record the divergence in
   `KNOWN` with its consequence.
3. `_assert_no_orphaned_demand` — every field `half_ruling_refusal` demands must
   be offered by the ruling schema. Your `can_express` scoping and this cert are
   solving the same problem from two directions; they should compose, but it is
   worth one look.
4. `_assert_build_reads_only_stored_fields` — every verdict field `execute_plan`
   reads must be offered-or-derived **and** stored, and a derived field must
   actually be written into the record. The `_both` leg that would have failed
   your offered+derived `sfx` is **removed**, per Zac's ruling.
5. `_assert_treatment_surface_agrees` — prose and enum must not offer different
   family sets.

## Additive, no conflict

27 functions exist only on my lane and nothing of yours calls them:
`unscoped_coherence`, `overlay_covisible`, `caption_evidence`,
`caption_signature`/`captions_changed`/`plan_with_caption`/`caption_from_plan`,
`reruled_beats`, `reedit_delta`, `sfx_moments`/`sfx_name_teach`,
`enum_craft`/`craft_lines`, `knowledge_reach`, `mg_conditions`,
`condition_components`, `mg_unique_prop_owner`, `component_selection_arrows`,
`arc_rules`, `catalogue_bullets`, and the rest of the card/knowledge layer.

Same for the checks: `smoke_prompt_fidelity`, `smoke_reruled_visible`,
`smoke_red_proof_census`, `minimal_briefs_harness`, and 38 red proofs.

## The thing worth saying plainly

**No round has ever mounted my lane** — rounds 58 through 65 all resolve to
`lane/agentic-editor` and 51–57 predate the format. So none of this has been
observed working. The merge is the first time a week of it runs, and the first
round on the merged tree is where I would expect to find out which of my
instruments fire on real output and which were written against ledgers from a
tree that is not mine.
