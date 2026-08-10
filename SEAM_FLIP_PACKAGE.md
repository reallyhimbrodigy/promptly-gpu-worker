# LANE-SEAM flip package — status, evidence, remaining gates

Assembled 2026-08-09. Branches: worker `lane/seam` (base `1601ae0`, live),
content-studio `lane/seam` (base `324d907`, origin/main). Session spend to
date: **$0.00** (every check below is local; no Modal container, no Gemini
call, no render was run).

## What exists, dark

| Flag | Surface | Commit |
|---|---|---|
| `PROMPTLY_ADAPTER_V1` (+ per-job `adapter_v1_test`) | adapter_contract.py; one call-site touchpoint in handler.py; #2/#3 stub sockets | 1c9bd13 |
| `PROMPTLY_UNIFIED_CORE` (+ `unified_core_test`) | guidance_registry.py + unified_core.py; guidance_profiles kwarg + compose seam | 3d0a822 |
| `PROMPTLY_SURGICAL_V2` (+ `surgical_v2_test`) | surgical_ops.py; caption-text override + add-transition tweak ops, deterministic enforcement | cca357c |
| `PROMPTLY_CHAT_ACTIONS` | lib/chat-actions.js + routes/chat-actions.js (content-studio); iOS handoff page | 5477348 |

## Evidence in hand (all $0, all re-runnable)

- `cert_adapter_contract.py` **5/5** — is-identity carrier, dark-off default,
  structural rejection, honest stubs, wiring+mount fingerprints.
- `cert_unified_core.py` **8/8** — premium-identity (flag-ON main route
  composes to the SAME base object), cache-prefix law, contradiction RED,
  no-tool-stripping (structural), conservatism, determinism, dark-off, wiring.
- `cert_surgical_ops.py` **6/6** — dark-off, flag-off prompt byte-identity
  (refusal-bullet fingerprint, single source), no-fabrication vs transcript,
  natural-duration skip-never-shorten, no-op safety, wiring.
- content-studio `npm run validate` **20/20** smokes incl. new
  `__smoke_chat_actions.js` (dark-404 before auth, conservatism matrix,
  verb-drift containment, no-parallel-path).

Byte-identity OFF is currently proven **structurally** (aliasing off-path,
empty premium profile, schema-enum exclusion, fingerprinted prompt bytes,
dark-404 route). The **runtime** proof — spy-capture/true-replay, N×
byte-identical on a captured real job body with flags absent (the blur-cert
method) — is a REMAINING GATE and runs through TRUTH's deploy queue (it
renders; state the dollar figure when scheduled, ~1 job ≈ $0.10-0.8 by route).

## Remaining gates before any flip (in order)

1. **HARNESS golden corpus lands** (`golden/` does not exist yet in either
   tree — the Step-2b blocker, named 2026-08-09).
2. **PLAN_ONLY differ runs, one route at a time** (budget ≤ $10 pre-approved,
   ~$0.10/run): for each of hype / moodreel / minimal / minimal_speech_uncut —
   compose `base + profile` via `unified_core.compose_system_instruction`,
   PLAN_ONLY call on that route's golden inputs, hand plans to the HARNESS
   differ. **Per-route target: GREEN vs that route's golden envelope**
   (imitate before improve). Premium route: flag-ON is byte-identical by
   construction (cert), so its differ run is a confirmation, not a risk.
   Any obedience-marker miss = hard stop + report.
3. **Surgical obedience cases S3-A / S3-B green** (specs delivered in
   `SEAM_OBEDIENCE_CASES_FOR_HARNESS.md`, incl. the flag-off byte-identity
   twin).
4. **JUDGE fulfillment non-regression** on the A/B'd plans (JUDGE lane owns
   the meter; M66 design is the reference).
5. **True-replay byte-identity, flags off** (item above).
6. **Owner sign-off**, then flips through TRUTH one at a time, each with a
   24h scoreboard watch: `PROMPTLY_ADAPTER_V1` → `PROMPTLY_UNIFIED_CORE`
   (per-route progressive) → `PROMPTLY_SURGICAL_V2` → `PROMPTLY_CHAT_ACTIONS`
   (only after the iOS router change ships).

## For TRUTH (registration + merge queue)

- Register the 4 flags in CANON.
- Wire `cert_adapter_contract.py`, `cert_unified_core.py`,
  `cert_surgical_ops.py` into validate_deploy (each is a plain
  `python3 <cert>.py`, exit-0-gated; content-studio smoke self-registers).
- server.js mount, ONE line (verbatim in routes/chat-actions.js header):
  `if (parsed.pathname === '/api/chat/actions' && req.method === 'POST') return require('./routes/chat-actions').handle(req, res, { requireSupabaseUser, readJsonBody, sendJson, supabaseAdmin, checkRateLimit, PORT });`
- Optional: add `chat_action_classified/dispatched/clarified/refused` to the
  `/api/events` ALLOWED set if the SQL mirror should carry them (they flow
  server-side via posthog-sink regardless).
- A secret flip is not live until a redeploy (memory-snapshot env freeze).

## Deviations / findings for the owner

- **Step-2b blocked on HARNESS** `golden/` — named the same day, not ground
  silently.
- **Finding:** the caption-text-override capability was HALF-built already
  (deterministic parser `_parse_caption_text_overrides` + display applicator
  `_apply_caption_text_overrides`, shipped 2026-07-28) but unreachable from
  tweak for BARE asks ("change 'rise' to 'ryze'" without the word
  'caption') — the fabrication-hazard split in the parser is deliberate and
  was kept; Step 3 routes bare asks through the MODEL with deterministic
  post-validation instead of loosening the regex.
- **Finding:** `_apply_plan_ops` could always add transitions — only the
  prompt refused. The fork between "mechanically possible" and "taught" was
  one bullet of prose.
