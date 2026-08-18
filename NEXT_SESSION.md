# NEXT SESSION — front of the queue

**Live: v556 = `d9f40dd`.** Branch green at 399 checks, no-regress clean,
working tree clean.

---

## 1. Settle the two suspect misses (~$0.02, first thing)

`SUSPECT_MISS_QUEUE.json` holds both sources with their measured levels and
live URLs, so no re-derivation is needed.

| job | dur | mean dBFS | speech−bass | routed |
|---|---|---|---|---|
| `c4739d9f` | 28.3s | −24.7 | **+9.1** | `no_speech_muted` |
| `0d590a4b` | 37.2s | −34.3 | **+7.4** | `no_speech_muted` |

Both are speech-shaped by the heuristic and both got zero words. **Replay each
through Deepgram directly** (same options as `_deepgram_options`: nova-3,
`language=multi`, `filler_words=true`) and compare against production's zero.

- **words come back** → ASR failed on good audio; the heuristic was right and
  two users got a music edit on a talking video.
- **zero again** → the `speech_band − bass ≥ 4.0` threshold is over-triggering
  and the label needs recalibrating. The raw inputs are all persisted, so it can
  be re-derived without another render.

**Run the known-good control in the same batch.** Every zero this project has
believed without one has been wrong at least once — the Vertex probe returned
`DefaultCredentialsError` on all four models *including* the control, and only
the control stopped it shipping as "3.7 unavailable".

## 2. Render-only across the three gates — narrowly scoped, RED-proven

Unblocks `held/echo_outro/` (built, mirror test 14/14, see its `BLOCKER.md`).

Three gates currently insist every renderable name is requestable by the model
and named in the prompt. That check is the **seventh** instance of the
built-not-wired class and has a 7-for-7 catch record — weaken it carefully.

Scope the exemption so an ordinary component cannot claim it. A render-only type
must satisfy **all** of:

1. produced by a `build_*` in `brand_components.py`;
2. dispatched through a spec adapter (not the bare component) in `MG_MAP`;
3. **a non-zero production counter** — the exemption is only honoured for a type
   that has actually rendered on real traffic. Without this, "render-only"
   becomes the hiding place the gate exists to prevent.

RED-prove each clause: an ordinary component claiming the exemption must fail,
and a render-only type with a zero counter must fail.

---

## Then, in order

3. The fourth `brand_components_built` state — spec built **and emitted** vs
   spec built **and dropped**. The emission seam (v556) makes this
   distinguishable for the first time; the counter still reports only three.
4. The echo outro (unblocked by 2).
5. **The ledger baseline.** `component_ledger` went live at v555 and rides both
   result payloads and both durable writes. First read separates "the planner
   declined" from "we dropped it", per type — which re-opens scenes 0/779,
   brand_copy 0/198 and MG ~62%, none of which could make that distinction.
6. `prompt_v2` A/B — `prompt_v2_editor.py` + `prompt_v2_exemplars.py` are
   written, dark and unwired; `PROMPTLY_PROMPT_V2=1` selects them. Read
   requested-vs-dropped on both arms, not rendered counts.
7. Typed props — filed (`FILING_TYPED_MG_PROPS.md`), deliberately behind the
   ledger's first read, since that read may change which fields should be
   required.

## Open filings

- `FILING_EMPHASIS_OUTSIDE_VIDEO.md` — **Step-C precondition.**
  `emphasis_moments[4] derived t=73.217s is outside video` on a **74.8s**
  source. 1 in 11 silent downgrades to safe-edit. First move is cheap: make the
  message name the bound it compared against.
- `FILING_CANON_MIRROR_CONSOLIDATION.md` — four surfaces, low priority,
  gate-enforced today.
- `FILING_TYPED_MG_PROPS.md` — see 7 above.

## Corrections carried forward (do not re-derive)

- **"props empty 210/210" is WITHDRAWN.** It read the render-side projected
  shape (`end_s/start_s/text/type`) out of `edit_recipe`, not the model's plan
  shape. The historical props-in-prose rate is **unmeasured**; it should come
  from the S3 divergence ledgers, which hold the raw plan.
- **The 41.7% safe-edit fallback rate is WITHDRAWN** — it was `cell.map`
  concurrency, refuted by a serial control (0/5 fallbacks).
- Step A's real numbers, serial at production's canonical `thinking=2048`:
  3.7-flash **2.50×** faster at p50 (70.1s → 28.0s), **cut count identical 5/5**,
  marginally less decorative (emphasis 16 vs 14, mg 1 vs 0).
