# MERGE HANDOFF — `agent/prompt` → speed agent (2026-08-02)

22 commits, `3f30009..ad8d33f`. **Six touch `handler.py`. The rest are tools,
measurements and documents with zero production surface.**

Gate state at HEAD:
```
CERT PASS — nothing removed, no invariant collapsed, no gate phrase broken
FITS=60 FIGHTS=60   (validate_deploy floor 59)
CORE 39,793 → 39,924 tok = +131
```

**Net prompt size is +131 tokens.** Compression is closed — five independent
measurements (caveman 1.29× · classification 1.12× · WHY ~1% · deletion 1.15× ·
variant caches 1.12×) and the −209 I did cut was reinvested in discrimination,
which is the part that changes what the model *chooses*.

---

## A. TOUCHES `handler.py` — review these

| commit | what it changes | risk | gate |
|---|---|---|---|
| `d98cd8d` | **Six FITS/FIGHTS rewritten to discriminate on MOMENT SHAPE** (Timeline · TimelineRoadmap · StepDivider · DropBanner · BarRace · PillMarquee). All six fired **0 / 709** stored plans because every one of them fought on the same axis ("educational, fights cinematic") — which separates them from other vibes, not from each other. **This is the highest-value item in the list** and the one most likely to move pace. +119 tok. | prompt text only, live on next call | cert-PASS, FITS 60/60 |
| `857713c` | **`sticky_note` routing.** It renders the *identical* `<StickyNotes>` component as the MG (verified `PromptlyRender.tsx:398`) — one instrument, two catalogue entries, no routing rule, 8 uses split across both. Now: structure → text_overlay, evidence → motion_graphic. +223 tok. | prompt text only | cert-PASS |
| `a82867f` | MG anchor + intro condensed, −209 tok. The face/anchor rule was stated 3×. | prompt text only | cert-PASS |
| `e40d696` | **`_GEMINI_CALL_LOG` records `prompt_tok` + `cached_tok`.** They were computed and printed but never kept, so reading input cost meant scraping Modal stdout inside its ~1h buffer. | additive telemetry, no behaviour | — |
| `199578e` | **`_GEMINI_CALL_LOG` records the per-modality split.** `usage_metadata.prompt_tokens_details` was always returned and never read. This is what killed the fps lever. | additive telemetry, no behaviour | — |
| `7efb193` | Two **dark flags**, both default-OFF and asserted byte-identical when off: `PROMPTLY_SCHEMA_PAD` (inert unreferenced `$defs`, for the unfinished schema-billing probe) and `PROMPTLY_PROMPT_ORDER=v2` (moves HARD CONSTRAINTS 91.6% → 12.3%; the swap **raises** if the sorted line multiset changes, so a lossy reorder cannot ship). | inert unless flagged | flag-off byte-identical, asserted |

**If you merge only one thing, merge `d98cd8d`.**

## B. NO PRODUCTION SURFACE — tools, gates, documents

`phase3_section_cert.py` (13-section content-diff, arm-aware, + gate-pinned-phrase
check) · `prompt_token_map.py` · `phase3_block.py` · `phase3_ceiling.py` ·
`phase3_taxonomy.py` · `phase3_why_pass.py` · `phase3_schema_guaranteed.py` ·
`query_component_usage_app.py` · **`query_silent_failures_app.py`** ·
`query_stage_decomp_app.py` · `cert_modality_read_app.py` ·
`plan_ab_reorder_app.py` · `cert_prompt_content_diff.py` (was missing from this
branch; recovered from `inc2-buildout`) · `DELETION_MENU.md` ·
`VARIANT_CACHE_SCOPING.md` · `QUALITY_VS_LENGTH_TEST.md` ·
`MODAL_SPEND_LEDGER.md`.

**`query_silent_failures_app.py` is the one worth wiring into the daily report.**
It found 80 of 177 users getting nothing, and the class is invisible to
error-rate monitoring by construction.

## C. KNOWN BROKEN — do not merge as-is

`cert_schema_billing_probe.py` — never ran. Three attempts, the third
crash-looped and orphaned a Modal app that survived a local kill (stopped with
`modal app stop`). The design is sound (+5,214 tok = 28× noise; inert
unreferenced `$defs`; flag-off byte-identical); the invocation is not. Whoever
picks it up should copy `plan_ab_reorder_app.py`'s header verbatim.

---

## D. WHAT I MEASURED THAT BELONGS TO OTHER LANES

- **`edit_plan` = 130.7s median** (p90 270.6), of which `gemini_call` is 80.3s
  (61%) and **~50s is everything else** — proxy build, faces, scene detect,
  recipe assembly, transitions sub-call. `gemini_wasted_degen` is 0.0s at the
  median but **p90 94.0s, max 423.1s**.
- **`edit_plan` is not the biggest stage.** `render` 149.5s and
  `normalize_transcribe_upload` 140.1s both beat it. `total` 360.4s.
- **Uncached input is 78% TEXT** (12,872 tok: transcript + faces + shot-changes
  + vibe), 20% video, 4% audio. TTFB prefill is 1.80 ms/uncached token. If
  anyone wants TTFB, that text is 4× the video.

⚠️ **Every latency figure above is a production median across all source
durations, not at a 60-second source.** PLAN_ONLY returns
`{status, job_id, edit_plan}` with no `stage_timings`, so I could not cut my own
runs by source length. Adding `source_duration_s` to that return is one line in
your seam and would let every future prompt-side read comply.
