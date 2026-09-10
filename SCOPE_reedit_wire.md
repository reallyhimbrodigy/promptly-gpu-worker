# The wire between "re-edit works" and "a user can re-edit"

Re-edit works in the worker. Nothing reaches it. This is what the wire is today,
traced with line numbers, and the four things that have to change.

Everything under OBSERVED is read from `content-studio` (branch
`lane/account-deletion`) and `handler.py`. Inference is labelled.

## OBSERVED — the wire that exists

**Client.** `APIService.swift:646`

    func reeditFromJob(originalJobId: String, changeRequest: String)
        POST /api/video-jobs/re-edit
        { original_job_id, change_request, reply_language }

**Server.** `server.js:6705`. Loads the original job (`:6862`) selecting
`id, user_id, status, video_url, vibe_input, edit_recipe, transcript,
analysis_data, resolved_broll, trend_snapshot`, then:

    const hasSavedPlan = orig.edit_recipe && typeof orig.edit_recipe === 'object';
    const mode = hasSavedPlan ? 'tweak' : 'reinterpret';      // :6903

creates a derivative job, and dispatches with `mode`, `editPlan`, `transcript`,
`analysisData`, `resolvedBroll`, `trendSnapshot`, `changeRequest`, `oldVibe`,
`parentJobId` (`:6918-6938`).

**Where it goes.** `MODAL_ENDPOINT_URL` (`:111`) — the handler.py path.

**Who writes the plan.** `handler.py:17584-17588`, guarded by
`_job_column_exists("edit_recipe")`, writes `edit_recipe` back to the job row.

**THE AGENTIC PATH IS NEVER INVOKED.** `grep -ic agentic server.js lib/` returns
nothing. There is no branch, no flag and no second endpoint. Every re-edit —
every edit — goes to handler.py.

## THE GAP, precisely

The surface, the mode concept and the persisted-plan column all EXIST and all
point at the old path. The agentic path now produces a durable plan
(`result["plan"]`, verdicts keyed by source span) and accepts `prior_plan` +
`instruction`, and nothing calls it. **Neither half is missing. The wire between
them is.**

## FOUR THINGS, in dependency order

**1. The agentic worker's plan has to be persisted, and the worker cannot do it.**
handler.py writes `edit_recipe` itself because it holds Supabase credentials.
The agentic container deliberately does not — it is even handed a presigned URL
so that "the container cannot pick where output lands, which is the other half of
holding no credentials". So the plan travels in the RESULT, which is what
`result["plan"]` is for, and the SERVER persists it. That is a server change, not
a worker one.

**2. `edit_recipe` MUST NOT hold both shapes.** handler's recipe and the agentic
plan are different artefacts. If the agentic plan is written into `edit_recipe`,
then `hasSavedPlan` is true for an agentic job, `mode` becomes `'tweak'`, and the
job dispatches TO HANDLER.PY WITH AN AGENTIC PLAN. Nothing would report it: the
shapes are both objects, the mode is legal, and the failure is a silently wrong
edit.

That is the `_delivered` predicate class already on record here — a check that
tested presence where it needed to test SHAPE, and three delivery paths were
never real because of it. So: a separate column (`agentic_plan`), or a
discriminator inside the value that the mode resolution reads. **Presence is not
shape, and `typeof === 'object'` is presence.**

**3. The dispatch needs a route decision, and it does not have one.** There is no
per-job record of which path produced a job, so a re-edit cannot know which path
to send the derivative to. INFERENCE: this is fine today only because there is
exactly one path. The moment two exist, "which path made this?" has to be stored
at creation, not inferred at re-edit time from which plan column is populated —
inferring it from the artefact is the same presence-for-shape mistake one level
up.

**4. `change_request` maps to `instruction`, and `mode` mostly does not.**
`instruction` is the agentic parameter and `change_request` is exactly it. But
`tweak` vs `reinterpret` is handler's distinction: tweak = "we have a recipe,
adjust it", reinterpret = "we do not, redo it from the vibe". The agentic path
has ONE mode with a load and a scope, and its no-plan case is not `reinterpret` —
it is a plain edit. Mapping `reinterpret` onto a re-edit call would send an
`instruction` with no `prior_plan`, which is a fresh edit wearing a re-edit's
name and would be counted as a re-edit in every metric.

## WHAT I AM NOT DOING

Writing the server change. `server.js` is the frontend lane's file and the DB is
their truth; this is the worker-side statement of what the wire needs so the
change can be made once, correctly, by whoever owns it. The worker half is
already built and proven: `prior_plan`, `instruction`, `result["plan"]`,
`plan_onto_beats`, `reedit_merge`, and the surgical guarantee enforced rather
than asserted.

## THE SMALLEST THING THAT WOULD PROVE THE WIRE

One agentic job whose `result["plan"]` is stored, and one re-edit of it that
comes back byte-identical under a no-op instruction. That is the same proof
`cert_reedit_byte_identity.py` runs, with the plan making a round trip through
the database instead of staying in memory — and it is the difference between
"re-edit works" and "a user can re-edit".
