# MG-honoring diagnosis — ranked mechanism hypotheses (static analysis)

LANE-SEAM, 2026-08-11. Build-phase: no Gemini calls made. Inputs: JUDGE's
per-ask drop rows [MEASURED — origin/lane/judge `reports/FULFILLMENT_BASELINE.md`:
motion_graphics n=359, honored 133, DROPPED_SILENTLY 224 (62%), the #1
concrete silent drop; 309 preset taps literally name motion graphics], the
FIGHTS/discrimination prose, and the post-model drop chain. All `[CODE]`
cites are the lane-seam worktree @ `1601ae0`+lane commits.

## The question

A user asks for motion graphics (309 preset taps say exactly "add zooms,
sound effects and motion graphics"; 88+39 custom asks name them) and 62% of
those asks produce a plan with no MG and no note. WHERE does the ask die?

## Ranked hypotheses

### H0 — MEASUREMENT: the judge cannot see emphasis-bound MGs (check FIRST, $0)

JUDGE's evidence extractor counts ONLY the standalone array —
`ev.n_motion_graphics = arr(er.motion_graphics).length`
[CODE fulfillment-judge.js:112-113] — but the pipeline has a SECOND MG emit
path: `emphasis_moments[].motion_graphic` (`_EmphasisMotionGraphic`
[CODE handler.py:1226]), rendered through the same overlay leg and projected
at its own site [CODE handler.py:26417-26429]. This is the exact defect class
as the judge's own v1→v2 zoom correction (zoom evidence was read from the
wrong key; 88% "dropped" collapsed to 23%). If emphasis-bound MGs are a
material share of real MG output, the true 62% is inflated.
**Confirmation ($0, DB read, no Gemini):** count `motion_graphics[]` vs
non-null `emphasis_moments[].motion_graphic` across the judged corpus's
recipes. Queued in the ignition checklist below.

### H1 — PROMPT: a restraint-doctrine + earn-gate stack with NO user-ask override (leading product mechanism)

The MG section is a chain of discrimination gates, each individually
defensible, jointly teaching abstention:
- Restraint-first framing: "Reach for the choice that reads as inevitable…
  strongest edits reach for the quietest one… plainer treatment … is the
  MORE produced choice" [CODE handler.py:6438].
- Per-placement burden of proof: mandatory ≤12-word `why` naming the moment,
  written FIRST [CODE handler.py:6443]; "every component survives the
  question 'which moment asked for you?'" [CODE handler.py:6017]; the
  decorated-edit cautionary block teaching that rule-satisfying placements
  are STILL wrong [CODE handler.py:6846].
- Per-type earn-gates: StatCard "can you quote the dialogue line where the
  speaker says THAT number" [CODE handler.py:6448 region]; MOMENT-SHAPE
  clauses on BarRace/PillMarquee/DropBanner/Timeline/StepDivider; diegetic
  "real quoted tweet/comment/message is the gate" on all six social cards
  [CODE handler.py:6482-6583].
- **The asymmetry that convicts this stack:** explicit B-ROLL asks get an
  obedience directive spliced into USER INSTRUCTIONS
  (`_broll_request_directive` [CODE handler.py:6067 splice, parser :260-296]);
  TRANSITIONS got a measured anti-restraint counterweight after firing on
  only 4.9% of jobs ("'The few' has become 'almost none'… that is a miss,
  not restraint" [CODE handler.py:6281]). **MG asks have neither** — an
  explicit "add motion graphics" competes unaided with every gate above.
- Independent support: the E1 density A/B found the density ceiling
  ARCHITECTURAL (multi-gate culling, not prompt-tunable by addition;
  memory `project_e1_density_ceiling`); MG density runs at HALF the owner's
  reference with 63% of std-editorial jobs at zero MGs
  (memory `project_mg_density_vs_reference`) [MEASURED].

### H2 — ROUTES: 47% of traffic plans with restrained-or-absent MG capability

Lean routes: `minimal` / `minimal_speech_uncut` emit no MGs by construction
(deterministic/uncut paths [CODE handler.py:32161+]); `hype` is taught
"sparse" and `moodreel` "almost never — default NONE"
[CODE hype_editor.py:build_hype_prompt, moodreel_editor.py:build_moodreel_prompt].
A preset tap naming MGs that routes lean is structurally droppable. JUDGE's
recent-slice worsening (52.3% silent on 08-09 vs 35.1% corpus) is attributed
to exactly this route mix [MEASURED/INFERRED — FULFILLMENT_BASELINE].
**Confirmation ($0):** split the 359 MG asks by route key in `result`.
(The unified core's guidance profiles — Step 2, dark — are the structural
fix lane for this half.)

### H3 — POST-MODEL: projection-miss drops

Both MG paths are DROPPED when their anchor words fall off the output
timeline (transition-tail/refinement): standalone
[CODE handler.py:26286-26295] and emphasis-bound [CODE handler.py:26417-26429],
each ledgered as a `projection_miss_drop` divergence, plus the count-honesty
assert [CODE handler.py:26576]. Historical precedent: the phantom-miss
hotfix a47221f (memory `project_hotfix_phantom_mg_miss`).
**Confirmation ($0):** count `projection_miss_drop` divergence rows over the
judged window — bounds this mechanism's share directly.

### H4 — RENDER: collision/floor drops

The MG minimum-duration floor is collision-aware and downstream collision
rules silently drop components (overlay collision keep-list
[CODE handler.py:27169-27184]; floor-extension cap rationale
[CODE handler.py:26183, 26309-26322]). Bounded, per-component; ranked below
H1-H3 because it requires an MG to have been emitted AND projected first.

### H5 — NEGATIVE FALSE-POSITIVES: `_parse_off_features` stripping MGs

[CODE handler.py:17667+ region]. No evidence of a false match in the ask
corpus; lowest rank.

## Expected mechanism split (prior, to be replaced by measurement)

H1 ≫ H2 > H0 (unknown until counted) > H3 > H4 > H5. The 62% cannot be
mostly H3/H4 — those ledger divergences, and nothing in the recon flagged a
projection-miss epidemic; H1+H2 are consistent with the zero-MG-majority
density read.

## Confirmation plan — queued for ignition day (differ-runs, not construction)

**$0 DB reads (run first, in order):**
1. H0: emphasis-bound vs standalone MG counts across judged recipes → correct
   the 62% if needed (and hand JUDGE the evidence-key fix, their v3).
2. H2: route split of the 359 MG asks.
3. H3: `projection_miss_drop` divergence rate over the same window.

**PLAN_ONLY A/B (staged: `cert_mg_honoring_planonly_app.py`, ~$0.30-0.60
for 3 arms × 1 source, scale to N sources on approval within the standing
≤$10 PLAN_ONLY budget):**
- arm A control: neutral vibe, flags off.
- arm B ask: the verbatim 309-tap preset text, flags off. If plan-level MG
  count (BOTH keys) does not move vs arm A → H1 confirmed at the planner.
- arm C fix: same ask + `PROMPTLY_MG_OBEY=1` — the dark directive built in
  this commit (`_mg_request_directive`, spliced at the USER INSTRUCTIONS
  block next to b-roll's [CODE handler.py splice at `{_broll_request_directive(vibe)}{_mg_request_directive(vibe)}`]).
  Measures whether the obedience channel closes the gap without breaking the
  earn-gates (types/whys inspected in the output).

**Fix lanes if confirmed:** H1 → flip PROMPTLY_MG_OBEY after differ GREEN +
JUDGE honor-rate watch; H2 → the unified-core guidance profiles (Step 2);
H0 → JUDGE evidence-key correction (their side, one line).
