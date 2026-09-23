# The free-tier global budget — DESIGN ONLY, nothing built

A monthly ceiling on what FREE videos may cost us in ChatCut credits, metered
against ChatCut's own balance. Pro and Max are exempt. Not built: the number at
the centre of it has to come from run two's measured per-edit cost, and a
budget set from a guess is a guess with a 402 attached.

## 1. What is being counted, and where it is read

**ChatCut's real balance, not our estimate.** `GET /api/payment/credits` before
and after each run — already captured per run, so the instrument exists and the
design only has to use it honestly.

    spend(run) = balance_before - balance_after

**THE DELTA IS TWO READS AND THEREFORE THREE STATES.** This is the whole risk
surface, and it is the defect this repo has shipped more than any other:

| before | after | state | what the budget does |
|---|---|---|---|
| read | read | `MEASURED` | debit the real delta |
| either failed | — | `UNMEASURED` | debit the ESTIMATE, flag the run |
| read | read, delta < 0 | `IMPOSSIBLE` | debit the estimate, PAGE |

A negative delta is arithmetic saying the model is wrong — a top-up landed
mid-run, or the two reads are of different accounts — and the honest response
is to say so, not to clamp it to zero.

**A FAILED READ MUST NEVER DEBIT ZERO.** `balance_after or 0` would turn an
unreadable balance into a free run, and free runs are exactly what this budget
exists to bound. A month of failed reads would report a budget perfectly intact
while the money left.

### 1a. The estimate cannot come from the price table, and my first draft said it could

This section originally read "the estimate comes from `credit_prices.py`". That
is wrong for the commonest case, and wrong in exactly the way the paragraph
above forbids.

**A DEFAULT FREE EDIT GENERATES NOTHING** — the brief tells their agent to
generate only if the user asked — so what it actually spends on is AGENT
MESSAGES and MOTION GRAPHICS. Checked against the table rather than assumed:

    agent_messages   priceable = False   VARIABLE, no rate published
    motion_graphics  priceable = False   VARIABLE, no rate published

Both are unpriced. `credit_prices.py` has no row that a non-generative edit
would match, so the estimate it returns for a normal free video is **zero** —
`or 0` reintroduced one level up, arriving as a well-typed number from a
function whose whole purpose is to refuse to invent one. The producer-side
laundering defect, in the design written to prevent it.

**THE FALLBACK IS THE TRAILING MEDIAN OF MEASURED RUNS**, not a price lookup:

| case | estimate | state |
|---|---|---|
| ≥ N measured runs this window | their median spend | `UNMEASURED_EST` |
| generative line items present | `max(median, price-table sum)` | `UNMEASURED_EST` |
| no measured runs yet | **none — do not debit** | `UNMEASURED_UNPRICEABLE` |

The third row is the one that matters. A run we cannot measure and cannot
estimate is not a free run: it is COUNTED, PAGED, and left undebited with its
state on the record, so the month's total is visibly incomplete rather than
quietly wrong. A budget that silently absorbs unmeasurable runs at zero is the
clean zero this repo has been caught by four times in one day.

**And it means the meter must run before the ceiling can exist at all** — the
median has to come from somewhere. Section 6's dark period is therefore not a
cautious choice, it is the only order in which this can be built.

## 2. Reserve, then reconcile — never check-then-act

A global counter read by concurrent jobs is a race: two free jobs both read
"6 credits left", both pass, both spend 9.

    at dispatch   reserve the ESTIMATE for this edit, atomically
                  refuse if the reservation would exceed the month's ceiling
    at completion reconcile the reservation to the MEASURED spend
    on failure    release the reservation

The ceiling is therefore checked against `spent + reserved`, never `spent`. A
job that has started is FUNDED — it cannot be killed mid-edit by another job's
reservation, which is the only way "what happens at 0 credits mid-edit" has a
defined answer on our side. (ChatCut's own docs say NOTHING about their
behaviour in that case; the nearest statement is that voice credits are
"deducted only after generation succeeds", which is one feature generalised by
me and is not a fact about theirs.)

## 3. The month, and whose month

**Reuse `periodKey()` from `lib/free-credits.js`.** A second month boundary is
two numbers with the same name: the free grant rolls on a calendar month in UTC
and this must roll on the same one, or there is a window each month where
credits have been granted under one period and spent under another.

## 4. Who it applies to

Free only. Pro and Max are exempt, and the exemption is read from
`creditTierFor(profileRow)` — the same resolver `videosLimitFor` uses, not a
second tier derivation. A tier resolver that collapsed every row to `free` has
already shipped once here and reported the free allowance to Max subscribers.

**An unreadable profile row is NOT free.** It is unknown, and the budget treats
unknown as exempt-and-paged rather than as free-and-refused: refusing a paying
subscriber because their row would not load is a self-inflicted outage, and
paging us is what the law already requires — fail loudly to us, never to the
user.

## 5. The 402

Body says **videos**, not credits, because credits are the mechanism and videos
are what was sold:

    {"error": "free_budget_exhausted",
     "kind":  "free_videos",
     "message": "Free videos are used up for this month. They reset on the 1st."}

The user never learns there is a global pool — it is our cost control, not a
term of their plan, and a message that mentions a shared budget invites the
question of whose videos used it.

## 6. Dark until the number is measured, and metered the whole time

**The budget ships with NO ceiling and FULL metering.** Nine features have
shipped gate-green and done nothing here, most of them because a flag had a
reader and no writer or a threshold nobody set. This one is deliberately the
other shape: with `FREE_MONTHLY_CREDIT_BUDGET` unset, nothing is ever refused,
every run is still measured, reserved, reconciled and ledgered, and the month's
real free-tier spend accumulates.

Then the ceiling is set FROM that measurement instead of from arithmetic on a
per-edit estimate — which is the same discipline as measuring the prize again
after the lever, and it means the first month of enforcement is calibrated on
the population it will govern rather than on run two's sample.

**An unset ceiling must be UNSET, not zero.** `budget or 0` would refuse every
free video on the day the constant is missing.

## 7. What is printed, in the commit that adds it

Every counter added to answer a question gets printed in the same commit — this
repo has three instances of a counter reaching the ledger and no output, each
diagnosed from the previous one.

    [free-budget] 2026-10  spent 412 of UNSET  reserved 18  runs 47
                  MEASURED 44  UNMEASURED 3  IMPOSSIBLE 0  refused 0

Never a bare number: `spent` always with the ceiling it is out of and the run
count it came from, and the three states always beside it. A month reading
`spent 0` with `runs 0` is a quiet month; `spent 0` with `runs 47` is a broken
meter, and only the denominator separates them.

## 8. The checks, named — Rule 1

| check | what it makes impossible |
|---|---|
| `free_budget_states` | a failed balance read debiting 0 |
| `free_budget_reserves` | check-then-act: two concurrent jobs passing one ceiling |
| `free_budget_period_shared` | a second month boundary diverging from the grant's |
| `free_budget_tier_exempt` | Pro/Max metered, or an unreadable row treated as free |
| `free_budget_unset_is_not_zero` | a missing constant refusing every free video |
| `free_budget_estimate_is_never_zero` | an unpriceable run debiting 0 instead of paging |
| `free_budget_402_says_videos` | the copy drifting back to credits |

## 9. What this design does NOT decide

- **The ceiling itself.** Owed by run two's measured per-edit cost — and NOT
  derivable from the price table even in principle, because the two things a
  non-generative edit spends on are the two ChatCut does not publish rates for.
  This is the finding that decides the build order: the number cannot be
  argued into existence, only measured.
- **What ChatCut does at 0 credits mid-generation.** Not published on any docs
  page I read. Our reservation makes a started edit funded on OUR side; it says
  nothing about theirs, and the two must not be conflated in a report.
- **Top-ups.** Whether an exhausted month is topped up is a money decision, and
  their top-up price per credit is not published anywhere.
