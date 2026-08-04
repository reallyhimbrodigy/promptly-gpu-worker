# THE VIBE CORPUS — what users ask for, and whether we do it

1000 jobs, **567 distinct vibe strings**. Clusters are by WHAT IS ASKED FOR, not
wording; a string can carry several asks, so shares sum past 100%.

## ✅ THE HEADLINE: THE VIBE IS **NOT** DECORATIVE

The three preset strings are a natural experiment — same product, same button,
different label. If the vibe did nothing, these columns would match. They do not:

| | Viral engaging | Clean and engaging | Professional corporate |
|---|---|---|---|
| n (planned) | 29 | 14 | 7 |
| **cuts / 25s** | **9.85** | 7.01 | **6.15** |
| caption keywords / 25s | 13.66 | 14.63 | **8.93** |
| emphasis moments / 25s | 6.15 | 5.38 | 4.89 |
| **caption style** | Pulse 12, Gadzhi 6, TwoTone 5 | Prime/Gadzhi/Cove spread | **CleanCut 6 of 7** |
| **zoom mix** | **SnapReframe 40%**, SmoothPush 30% | SmoothPush 54% | **SmoothPush 95%** |
| outro | none 83% | none 79% | **fade_black 71%** |

Viral gets the punchy snap zoom, the energetic caption styles, the densest cuts
and no outro. Professional corporate gets the calm push (95%!), CleanCut, the
quietest captions and a fade to black. **That is a coherent, correct reading of
the request.** "Always tailored to user requests" is true at the plan level.

⚠️ Small n (29/14/7). The direction is consistent across six independent metrics,
which is what makes it credible, but it wants re-running at n≥100.

## 🚩 WHAT THE SAME TABLE EXPOSES

**Three instrument families are at 0.00 per 25s for EVERY vibe:**

| | Viral | Clean | Professional |
|---|---|---|---|
| motion graphics / 25s | **0.00** | **0.00** | **0.00** |
| text overlays / 25s | **0.00** | **0.00** | **0.00** |
| transitions / 25s | **0.00** | **0.00** | **0.00** |

The vibe cannot steer an instrument that never fires. Cuts, zooms and captions
carry the entire product.

**And two fields do not discriminate at all:**
- `pacing` = **`fast` on 100% of jobs** — 29/29, 14/14, **7/7 including
  "Professional corporate style"**. A corporate edit marked fast-paced is not a
  reading of the request; it is a constant wearing a field's name.
- `color_effect` = **`None` on 100%** — never fires for any vibe.

## THE REQUEST CLUSTERS, CROSS-JOINED WITH EXPORT

| cluster | n | share | bucket | export % | view→exp % |
|---|---|---|---|---|---|
| viral / engaging (generic) | 380 | 38.0% | FULFILLED | 12.9% | 42.2% |
| zooms | 227 | 22.7% | FULFILLED | 10.6% | 44.4% |
| smooth | 220 | 22.0% | FULFILLED | 11.8% | 44.8% |
| captions / text on screen | 199 | 19.9% | FULFILLED | **14.1%** | 45.2% |
| professional / corporate | 183 | 18.3% | FULFILLED | 12.6% | 40.4% |
| sound effects | 176 | 17.6% | FULFILLED | 10.8% | 44.2% |
| motion graphics | 169 | 16.9% | **PARTIAL** — 0.00/25s at the median | 13.6% | 48.9% |
| music / beat-sync | 102 | 10.2% | **IMPOSSIBLE** | **8.8%** | 30.0% |
| colour grade / filter | 90 | 9.0% | **PARTIAL** — color_effect never fires | 10.0% | 33.3% |
| script / narrative given | 87 | 8.7% | **PARTIAL** | **4.6%** | **18.2%** |
| resolution / 4K | 46 | 4.6% | **IMPOSSIBLE** | 8.7% | 33.3% |
| audio cleanup / denoise | 36 | 3.6% | PARTIAL | **5.6%** | 22.2% |
| speed / slow-mo | 36 | 3.6% | **IMPOSSIBLE** | **5.6%** | 18.2% |
| b-roll / stock | 33 | 3.3% | PARTIAL | **6.1%** | **15.4%** |
| crop / aspect / resize | 31 | 3.1% | PARTIAL | 6.5% | 20.0% |
| fast / punchy pacing | 30 | 3.0% | PARTIAL — pacing is always `fast` | **3.3%** | **14.3%** |
| translate / language | 27 | 2.7% | FULFILLED (Tier-1) | 11.1% | 60.0% |
| face / avatar reference | 8 | 0.8% | **IMPOSSIBLE** | **0.0%** | 0.0% |
| generate footage | 1 | 0.1% | **IMPOSSIBLE** | 0.0% | — |
| (unclassified) | 188 | 18.8% | — | 13.8% | 38.8% |
| **ALL** | **1000** | | | **13.3%** | **42.2%** |

**The export signal is unambiguous: every cluster we cannot actually do sits at
the bottom.** Face reference 0.0%, fast/punchy 3.3%, script-given 4.6%,
slow-mo 5.6%, denoise 5.6%, b-roll 6.1% — against 13.3% overall. The things we
genuinely do (captions 14.1%, MGs-requested 13.6%) sit at or above average.

## 5. "MAKE IT VIRAL" — DOES IT HAVE AN ANSWER?

**Yes, and it is coherent — not a silent default.** It is the most common request
(380 by cluster, 175 as the exact preset) and it produces the densest cuts
(9.85/25s vs 6.15 corporate), the punchy SnapReframe at 40%, Pulse/Gadzhi/TwoTone
caption styles and no outro. The system has a real "viral" identity.

It exports at **12.9%, slightly BELOW the 13.3% average.** So the answer exists
and is not obviously wrong — it just is not winning. With MGs, overlays and
transitions all at zero, "viral" is being expressed through cuts, zooms and
captions alone, which is a thin vocabulary for the most demanding request.

## WHAT WOULD MAKE EACH GOOD

| bucket | action |
|---|---|
| **IMPOSSIBLE** (music-sync 102, 4K 46, slow-mo 36, face 8) — **192 jobs, 19%** | Say so at intake. They export at 0–8.8% and every one is a paid disappointment. An honest "we can't do beat-sync yet" beats a silent miss. |
| **`pacing` is a constant** | Make it discriminate or delete it. 7/7 corporate jobs marked `fast`. |
| **`color_effect` never fires** | Same test: reachable, or delete. 90 jobs asked for a grade. |
| **MG / overlay / transition at 0.00** | This is the reachability work — the instruments exist and do not fire, so no vibe can reach them. |
| **script / narrative given (87, 4.6% export)** | Users are pasting whole briefs and scripts. We read them as a "vibe". Worst view→export in the set at 18.2%. |

## Method

`video_jobs.vibe_input` (1000 rows, all statuses), regex clusters over the
lowered string, joined to `analytics_events.export_completed` /
`result_viewed` on `props.job_id`. Plan metrics from `edit_recipe.plan` on the
planned (standard_editorial) subset only — the light routes carry no plan.
