# The agentic wire — worker side READY. Contract for the server half.

Worker half built and checked. This is what the server calls, what comes back,
and the three things that will silently produce a wrong edit if they are guessed.

App: `agentic-editor` (Modal). Two endpoints, both POST, both JSON.

## 1. DISPATCH — `run_agentic`

    POST { job_id, source_key, brief, src_url, out_url, out_key,
           result_url?, prior_plan?, instruction? }
    -> { spawned: true, call_id, job_id, source_key, result_url_given,
         mode: "edit" | "reedit" }

ONE SOURCE PER CALL. Call it N times for a multi-upload — see PRICING below.
`source_key` is ECHOED BACK because the client picked ASSETS, not job ids: if
that mapping dies here, the UI can say "four failed" and not WHICH four, and a
refund nobody can attribute to a clip reads as a random credit change.

Returns in milliseconds. It SPAWNS; it does not hold the request open across a
multi-minute edit.

    prior_plan   the `plan` array from the previous run's result. PRESENT means
                 this is a MODIFICATION. Absent means a plain edit.
    instruction  the user's `change_request`, verbatim.

`mode` comes back so a re-edit is countable. A re-edit reported as an edit is
uncountable, and the count is how anyone knows the feature is used.

## 2. COLLECT — `result_agentic`

    POST { call_id } -> { state, call_id, result?, error?, plan_entries }

    DONE     `result` carries the ledger AND `result["plan"]`
    RUNNING  not finished. NOT an error — poll again.
    FAILED   the edit raised; `error` says what.

A poll rather than a callback ON PURPOSE: handler's path posts back to
/api/modal-complete, which means the worker calls the server and needs its URL
and reachability. This container is deliberately credential-free. The server
already knows where Modal is and already holds the call id it was handed.

## THE PLAN ENTRY SCHEMA (fc's A)

A plan is a LIST. Every element is an object with exactly these keys:

    src_t0          number   source seconds, start of the beat this rules
    src_t1          number   source seconds, end
    id              string   12 hex chars, DERIVED from (src_t0, src_t1,
                             family, content) — not assigned, so it reproduces
    purpose         string|null   hook|claim|evidence|turn|payoff|close|breath
    treatment       array|null    of card|text|sfx|zoom|transition|none
    cut             string|null   "keep"|"cut"
    text_content    string|null
    card_hero       string|null
    card_label      string|null
    sfx             any|null
    sfx_name        string|null
    zoom_arc        string|null   hook|build|mid_peak|payoff|breather|close
    why             string|null

Validate `src_t0`, `src_t1` and `id` on EVERY element — those three are what
make it a plan rather than a list of dicts. The rest may be null.

## COLLECTION SURVIVES A DEPLOY (fc's B) — the dependency is removed, not characterised

**I do not know whether a Modal call id stays resolvable across an app
redeploy, and I am not willing to establish it on real traffic.** You named the
precedent yourself: a completion tail behind an in-process await that no deploy
survived.

So pass `result_url` — a presigned PUT. The worker writes the full result JSON
there BEFORE returning, and a failure to write is loud. Collection then becomes
a read of YOUR OWN storage and a deploy mid-edit strands nothing.
`result_agentic` stays the fast path, not the only one.

## FAILED CARRIES A CODE (fc's C)

`AGENTIC_CODES`: BAD_REQUEST, UNSUPPORTED, SOURCE_UNREADABLE, AGENT_FAILED,
RENDER_FAILED, UPLOAD_FAILED, INTERNAL. **UNSUPPORTED is a designed refusal, not
an error** — the request needed something this pipeline does not do. If a code
you need is missing, say which and it gets added rather than mapped on your side.

## plan_entries (fc's E)

`len(result["plan"])` — the number of rulings that got a durable address. It is
there so an EMPTY plan is visible without parsing the result: a re-edit against
a plan of zero entries would silently behave as a fresh edit.

## PRICING: NOT MINE, AND I REMOVED WHAT I BUILT (fc's D, ee's 1)

I built batch pricing. **It is deleted.** You established that credits are
RevenueCat virtual currencies and that `debit()` deliberately has NO PRE-READ —
RC checks and deducts atomically, so reading first only opens a race. A
price-then-dispatch design IS that race one process further away, and it would
have put a money decision inside a container holding no RC credentials by
design.

**Debit per source, in order, stop at the first INSUFFICIENT.** "Six answered,
four held by name" becomes an OUTCOME of the debits rather than a prediction.
The held list must come from the real attempts, not an estimate.

## WHAT THIS CONTRACT ASSUMES ABOUT MONEY, said out loud

- The debit path has **ZERO executions in production** — deliberately, because
  `CREDITS_DEBIT_ENABLED` is OFF while `CREDITS=1` lights the display. Fail-
  closed on purpose. Nothing here has been exercised against a real spend.
- **A re-edit NEVER debits.** `shouldDebit({mode, isReEdit})` is false for every
  re-edit variant. That makes the `mode` this endpoint returns LOAD-BEARING FOR
  MONEY: if it comes back wrong it is a free render, not a mis-count. Three
  checks guard it — derived from one thing, settable in one place, never read
  from the request body.
- COST_PER_RENDER=10; allowances free 30 / pro 200 / max 1000.

## THE SHIPPING RE-EDIT ENDPOINT ALREADY USES THE TRAP (ee's finding)

`POST /api/video-jobs/re-edit` documents itself as routing through Modal "in
either tweak or reinterpret mode". So trap 3 is not hypothetical — it is the
mapping the live endpoint already uses, and whoever wires `run_agentic` into
that endpoint meets it on the first try. **The agentic path must not reuse it
as-is.**

## THE THREE THINGS THAT MUST NOT BE GUESSED

**1. `edit_recipe` MUST NOT HOLD THE AGENTIC PLAN.** handler's recipe is a
DICT; the agentic plan is a LIST of source-span entries. Put one where the
other is expected and `orig.edit_recipe && typeof === 'object'` is TRUE for
both — `hasSavedPlan` passes, `mode` becomes `'tweak'`, and the job dispatches
to handler.py carrying a plan it cannot read. Every value is legal, nothing
errors, and the user gets a confidently wrong edit.

That is the `_delivered` predicate class already on record here: a check that
tested PRESENCE where it needed to test SHAPE, and three delivery paths were
never real because of it. **`typeof === 'object'` is presence.**

A separate column (`agentic_plan`), or a discriminator inside the value that
the mode resolution reads. The worker refuses a dict on `prior_plan` and says
which shape it expected — but that refusal is the last line, not the design.

**2. WHICH PIPELINE PRODUCED A JOB IS STORED AT CREATION, never inferred.**
There is no per-job record of it today, and inferring it from which plan column
is populated is the same presence-for-shape mistake one level up. The endpoint
URL IS the route decision: the server picks a URL, and that choice is the fact
to store.

**3. THERE IS NO `reinterpret` HERE.** handler's modes are `tweak` (we have a
recipe, adjust it) and `reinterpret` (we do not, redo from the vibe). The
agentic no-plan case is a PLAIN EDIT. Mapping `reinterpret` onto a re-edit call
sends an `instruction` with no `prior_plan` — a fresh edit wearing a re-edit's
name, counted as one in every metric.

    change_request -> instruction        clean
    tweak          -> prior_plan present clean
    reinterpret    -> NOT a re-edit. Dispatch it as an edit.

## WHAT THE SERVER PERSISTS

`result["plan"]` against the job id, and hands it back as `prior_plan` on the
next re-edit. The container holds no Supabase credentials — deliberately, which
is why it is handed a presigned URL rather than a bucket name — so it CANNOT
persist its own plan. That is the boundary that keeps the credential surface
small, not a limitation to work around.

## WHAT THE WORKER GUARANTEES

- A no-op re-edit re-derives nothing: identical verdicts round-trip to identical
  ids. (The BYTE-identical half needs a run; the harness is
  `cert_reedit_byte_identity.py`, priced at ~$0.05.)
- A ruling outside the declared scope is REFUSED and counted, not silently
  applied. An empty scope is a no-op, not a free hand.
- A prior ruling that cannot be placed on this run's beats FAILS LOUDLY rather
  than being dropped — a re-edit that silently loses part of the previous edit
  is the failure the feature exists to prevent.
- Ten sources are priced BEFORE dispatch: 60 credits answers SIX, with the
  shortfall named, and holds the other four by name rather than sending them to
  fail.

## AUTH

`run_job` on modal_app.py is unauthenticated today and MODAL_RUN_SECRET is
half-built (shipping it would 403 all dispatch). These two endpoints match that
posture rather than inventing a new one. When the inbound gate lands it lands on
both, and this is not the place to fix it quietly.
