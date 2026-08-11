# SECOND OUTAGE — chat has been down for four days, on a different billing surface

**Found by TRUTH, 2026-08-11, on the owner's explicit hunch that chat might
share the 403'd project. It does not — it fails for a different reason, and it
is worse than assumed: chat returns a hard 502 to every user.**

## What is wrong [MEASURED]

`/api/internal/gemini-diag` on production, exercising the **real** chat body
(true system prompt, 2,687 chars, real generationConfig):

```
real_chat_test: { http: 429, error_status: "RESOURCE_EXHAUSTED",
  error_message: "Your prepayment credits are depleted. Please go to AI Studio
                  at https://ai.studio/projects to manage your project and billing." }
```

Same 429 with and without `thinkingConfig`, and on the minimal body — so it is
not a request-shape problem. The API key itself is **valid and present**
(`key_present: true`, len 53) and can list models. The account is simply out of
prepaid credit.

**This is a SEPARATE surface from the worker outage:**

| | worker editorial | chat |
|---|---|---|
| credential | Vertex AI service account, GCP project `promptly-479218` | Gemini API key (AI Studio prepay) |
| failure | **403** PERMISSION_DENIED, "dunning decision is deny" | **429** RESOURCE_EXHAUSTED, "prepayment credits are depleted" |
| fix | GCP billing / dunning | top up AI Studio prepay credits |

Fixing one does not fix the other.

## What the user sees — a hard failure, not a degrade

[CODE](server.js:3350) — on any non-OK Gemini response, chat returns
**HTTP 502 `{"error":"AI service error"}`**. There is no fallback path. So
unlike the route collapse (which silently downgraded quality), **every chat
message has been failing outright.**

## How long, and how big [MEASURED]

`usage_events(kind='chat')` is written only **after** a successful AI reply
[CODE](server.js:3369), so it is a clean success counter:

| day | chat successes | distinct users |
|---|---|---|
| 2026-08-07 | **≥997** (floor — see note) | ≥548 |
| 2026-08-08 | **1** | 1 |
| 2026-08-09 | **0** | 0 |
| 2026-08-10 | **0** | 0 |
| 2026-08-11 | **2** | 2 |

**Aug 8 → Aug 11 inclusive: three successful chat messages in four days**,
against a baseline of ~1,000/day across ~548 users.

*Note on the floor:* the query returned the 1,000 most recent rows
newest-first, and its oldest row lands inside Aug 7. Everything **after** that
row is therefore complete and exact — Aug 8 onward is precise. Only Aug 7's 997
is a lower bound. (Stated explicitly rather than presenting a truncated series
as a full one.)

The collapse begins **2026-08-08 — the same day as the Vertex 403.** Two
different Google billing surfaces failing within a day is consistent with one
unpaid account cascading, but they are separately configured and must be
separately fixed and separately verified.

## Why nobody knew — the owner called this exactly

There is **no chat instrumentation**: no alert on chat error rate, no dashboard,
nothing in the daily report. A 502 on every chat message for four days produced
no signal at all. The only reason this surfaced is that the owner asked for a
one-off probe of `/api/chat` on the hunch that it might share the 403'd project.

**This belongs in the sentinel spec as a third alarm** — filed to JUDGE as an
addendum: *chat success events over the trailing 2h = 0 while chat requests > N
→ page.* Same shape as the moodreel route-extinction alarm, same reason: the
absence of a success is invisible unless something is explicitly watching for it.

## Owner action

Top up the AI Studio prepay balance for the Gemini API key
(https://ai.studio/projects), then TRUTH re-runs `/api/internal/gemini-diag` and
confirms `real_chat_test.http` = 200 plus resumed `usage_events` rows. Tracked
in `IGNITION_DAY_RUNBOOK.md` as the second billing column.
