# The agentic wire — worker side READY. Contract for the server half.

Worker half built and checked. This is what the server calls, what comes back,
and the three things that will silently produce a wrong edit if they are guessed.

App: `agentic-editor` (Modal). Two endpoints, both POST, both JSON.

## 1. DISPATCH — `run_agentic`

    POST { job_id, source_key, brief, src_url, out_url, out_key,
           prior_plan?, instruction? }
    -> { spawned: true, call_id, job_id, mode: "edit" | "reedit" }

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
