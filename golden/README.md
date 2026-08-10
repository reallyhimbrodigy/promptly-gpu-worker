# golden/ — the golden-output harness (LANE 2 / HARNESS)

The quality-regression tripwire. Locks the CURRENT editorial system's
plan-level behavior on a frozen corpus of 25 real production sources so that
any change to the editorial system produces a machine-readable diff — and an
editorial regression can no longer ship CI-green. The determinism certs lock
"same plan → same bytes"; this locks **"the plan itself didn't get worse."**

## Pieces

| file | what |
|---|---|
| `golden/manifest.json` | 25 frozen sources: S3 key + sha256 + etag (bytes stay in S3, never git), route_expected, lang, real user vibe, obedience markers. Route quota: editorial 12 (Hindi-weighted: hin 6 / eng 3 / spa 1 / ben 1 / ar-ask 1 / +multi-speaker), moodreel 5, minimal 3 (incl. near-silent), minimal_speech_uncut 2, hype 3. Premium: **unsourceable** — zero lumen jobs exist in live traffic; flagged, not faked. |
| `golden/plans/<source_id>/run{1..3}.json` | The frozen golden captures — 3 stochastic runs per source through the live system (envelope, not single-sample: plan generation is stochastic and a single golden would false-alarm constantly). |
| `golden/build_manifest.py` | Rebuilds the manifest from video_jobs + the asr_scribe_cohort2 language join. Provenance documentation — the committed manifest is the frozen artifact; do not casually regenerate. |
| `../golden_freeze_app.py` | The capture runner. PLAN_ONLY seam for editorial; light routes captured at the `hype_render.render_hype` boundary with render-impossible monkeypatches — **no corpus run can ever render**. Run FROM this worktree so the image == the commit being frozen. |
| `../harness_plan_diff.py` | The differ. GREEN / YELLOW / RED + itemized dimensions + `defect_rate`. |
| `../cert_golden_output.py` | Offline zero-spend cert: manifest integrity, 3 clean runs/source, differ self-test (11 planted defect classes), golden-vs-golden baseline GREEN. Writes `golden/baseline_report.json`. |
| `golden/baseline_report.json` | The JUDGE lane's defect-rate feed: `{"verdict", "defect_rate", "dims_total", "dims_red", ...}` from the latest baseline. |

## What the differ judges

- **Family presence / death** — captions, zooms, emphasis, MGs, overlays,
  b-roll, transitions, SFX. A family firing on ≥3 golden sources and 0
  candidate sources is RED (the six-unreachable-MGs class).
- **Density bands** — per-family counts inside the 3-run envelope ± observed
  spread. Outside = YELLOW.
- **Moment-class placement** — arc_position / zoom-type / caption-style /
  emphasis-type / sound distributions; corpus-wide class death is RED (the
  0/253 payoff-enum class).
- **Route decision** — light-route sources are judged on the routing REASON +
  coarse plan shape; a route flip (editorial → moodreel, or reason change) is
  RED.
- **Obedience** — 5 markers on 4 sources whose real user vibes carry explicit
  asks ("captions cuts zooms sound effects", "zoom in the girl…", "Add Arabic
  subtitles"). A marker every golden run satisfied going unmet is RED.
- **Structural sanity** — plan parses, required keys, enum vocabulary
  (unknown enum value = RED: schema drift or fabrication).

## How SEAM runs the harness before an editorial flip

```bash
cd .worktrees/lane-harness          # or wherever the candidate code lives
# 1. capture candidate plans on the SAME corpus (costs Gemini $, ~$4-6.5):
modal run golden_freeze_app.py --runs 3 --out /tmp/candidate/plans
# 2. diff against the goldens (free, offline):
python3 harness_plan_diff.py diff --golden golden/plans \
    --candidate /tmp/candidate/plans --manifest golden/manifest.json \
    --out /tmp/candidate/report.json
```

RED = do not flip. YELLOW = read the itemized drift, decide deliberately.
GREEN = the corpus saw no regression (not proof of improvement).

**The full harness run is NOT in the deploy gate** (it costs Gemini money).
The deploy gate (`validate_deploy.py`, via TRUTH) asserts the free part: the
corpus exists and loads, every source has 3 clean frozen runs, the differ
self-test passes, golden-vs-golden is GREEN.

## Re-freezing the goldens

Re-freeze is a **deliberate act, never automatic**: only after a change is
APPROVED as better, with the owner's sign-off recorded in the commit message
that replaces `golden/plans/` (include: what changed, why it is better, Zac's
approval date). The differ judges against what WAS true — that is its entire
value; a casually re-frozen golden is a deleted tripwire.

## Freeze preconditions (learned the hard way)

1. **Vertex must be healthy.** 2026-08-09: a GCP billing dunning-denial made
   100% of editorial jobs silently fall back to `safe_edit` — a freeze that
   day would have canonized fallback plans. Before freezing, run one smoke
   capture and assert `gemini_n_calls > 0` in the output.
2. Run from the worktree pinned to the commit being frozen (image bundles the
   working tree's handler.py).
3. `models/` must exist in the worktree (untracked; copy from the main
   checkout).
4. Ledger every batch in `MODAL_SPEND_LEDGER.md`; verify `modal app list`
   shows 0 tasks afterward.
