# DELETION MENU — Gemini Call-2 cached prefix (prompt agent, 2026-08-02)

**Rewording is closed** (caveman ceiling 1.29×, classification 1.12×, WHY ~1%).
2× can only come from deleting blocks. This is the menu.

Baseline **40,473 tok** (Vertex `cached_content_token_count`; live reading 41,344
on 2026-08-01). **2× needs ~20,200 tok deleted.**
Usage evidence = **709 stored `edit_recipe`s** (`query_component_usage_app.py`).

---

## 🚩 FIRST — THE HEADLINE CANDIDATE WAS MIS-MEASURED

The ledger's "THUMBNAIL = 4,276 tok, the biggest single deletion candidate" is
**wrong**. The section splitter runs THUMBNAIL from its header to the next
`=== header ===`, and **three unrelated doctrine areas live in that span**:

| paras | tok | what it actually is |
|---|---:|---|
| 1–3 | **~350** | THUMBNAIL proper — `thumbnail_word_index`, pre-reveal anticipation, great-frame criteria |
| 4–26 | **~1,834** | WORKED EXAMPLES — 4 accepted recipes + 3 rejected (THIN / STACKED / DECORATED) |
| 27–33 | **~1,602** | HARD CONSTRAINTS — THE WINDOW RULE, PER-COMPONENT RULES, VARIETY, TIEBREAKER, CEILINGS |
| 34–37 | **~421** | BEFORE-YOU-EMIT — Pass 1 movement walk, Pass 2 specificity audit |

**The thumbnail doctrine is ~350 tokens, not 4,276.** The thumbnail A/B — the
campaign's biggest planned win — is worth about **8% of what was budgeted for
it**, and the block it was going to delete is mostly the pace system.

---

## THE MENU

Ordered by tokens. **KEEP/CUT is my recommendation; the call is Zac's.**

| # | block | tok | capability lost if deleted | used on real traffic? | rec |
|---|---|---:|---|---|---|
| 1 | **PREAMBLE — MOVEMENTS** | 2,022 | the movement/arc system: how the video is tiled into energy movements before any component is placed | every plan carries `video_plan`/arc positions | **KEEP** |
| 2 | **THUMBNAIL span — WORKED EXAMPLES** | 1,834 | the prompt's **only few-shot**. 4 accepted recipes + 3 rejected teaching THIN / STACKED / DECORATED by counter-example | not directly measurable from plans | **A/B** — biggest honest candidate |
| 3 | **THUMBNAIL span — HARD CONSTRAINTS** | 1,602 | **the pace system.** ~2s window ceiling, emphasis 1:1 with key_moments, density caps, variety ≤60%/category | this *is* the events/25s machinery | **KEEP — deleting attacks the pace goal** |
| 4 | **PREAMBLE — WATCH THE VIDEO FIRST** | 1,333 | the instruction to read the footage before planning | — | **KEEP** |
| 5 | **B-ROLL — "modes that DO emit"** | 1,070 | keyword construction for the Pexels picker (13–18 words, verb-first) | `broll_clips` 0.56/plan | **KEEP** |
| 6 | **MG — 6 never-fired, NOT content-gated** | 1,266 | BarRace · DropBanner · PillMarquee · StepDivider · Timeline · TimelineRoadmap | **0 / 709 plans** | **REWRITTEN, NOT DELETED** (`d98cd8d`) — re-audit before any cut |
| 7 | **SFX — 5 sounds under 30 uses** | 734 | imposter(10) · awkward-moment(10) · iphoneding(16) · rizz(22) · wompwomp(28) | 86 uses total / 709 plans | **CUT CANDIDATE** — but check discrimination first, same failure as #6 |
| 8 | **ZOOM — StagedPush entry** | 455 | the 2–3-part stepped push | **3 / 709** | **CUT CANDIDATE** — 455 tok for 0.4% of zooms is the worst ratio in the prompt |
| 9 | **MG — 3 never-fired, CONTENT-GATED** | 549 | TweetBubble · ChatThread · TikTokComment | 0 / 709, but gate is a *real* tweet/exchange | **KEEP** — absence is likely correct, not a description failure |
| 10 | **THUMBNAIL span — BEFORE-YOU-EMIT passes** | 421 | Pass 1 movement walk, Pass 2 specificity audit | — | **A/B** |
| 11 | **THUMBNAIL proper** | 350 | `thumbnail_word_index` seed | live every job — but the pipeline runs its **own** OpenCV scorer ±0.6s, and the minimal route already seeds at `payoff_word_index` | **A/B** (the original plan, at 1/12 the size) |
| 12 | **ZOOM — DepthPull + FocusWindow** | 173 | two zoom types | 7 and 9 / 709 | **CUT CANDIDATE** |

**Total marked CUT CANDIDATE: ~1,362 tok. Total marked A/B: ~2,605 tok.**

---

## THE ARITHMETIC ZAC NEEDS

| | tok |
|---|---:|
| baseline | 40,473 |
| everything I can defend cutting outright (#7, #8, #12) | −1,362 |
| everything gated behind an A/B (#2, #10, #11) | −2,605 |
| the 6 rewritten components, IF the re-audit still shows 0 (#6) | −1,266 |
| **floor if every one of those lands** | **35,240 = 1.15×** |

**2× is not on this menu.** To reach 20,200 tok of deletion you would have to
take #1, #3, #4 and #5 — the movement system, the pace system, watch-the-video,
and the b-roll picker contract. Those are the product.

**The honest statement: the prompt is not 2× compressible or 2× deletable.**
It is ~40k tokens because it carries a component catalogue, a pace system, a
movement system and a few-shot. Every measurement this session — caveman 1.29×,
classification 1.12×, WHY 1%, and now deletion 1.15× — converges on the same
answer from a different direction.

---

## WHAT I'D ACTUALLY DO WITH THIS

The prefix is **cached at 0.25×** and the uncached half already costs more per
call (12,765 × 1.0 vs 41,344 × 0.25). **Shrinking it is not where the money or
the latency is** — that was measured, not assumed.

The three cut candidates (#7, #8, #12, ~1,362 tok) are worth taking anyway, not
for the tokens but because **an instrument the model never reaches for is a
described capability that does not exist** — the same defect as the six
components in #6, and the fix is the same: discriminate or remove.

**Blocked on:** #6's re-audit needs a 2-arm PLAN_ONLY run (~$3, priced in
`MODAL_SPEND_LEDGER.md`) and Zac's approval under Rule 8. Everything else here
is free and already done.
