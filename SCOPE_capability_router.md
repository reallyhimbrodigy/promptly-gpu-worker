# Scope — the capability router

Asked by Zac 2026-09-10: *what reads the request, what capabilities it can
route to, what it does when two are plausible, and what the cost and latency of
each path are — because a generated clip is minutes and an edit is seconds, and
the router needs to know before it commits.*

Scoped, not built. Every number below is either **MEASURED** with its
population stated or **ABSENT** and named as such.

---

## 1. What reads the request

**`set_spec`, which already is the router, one capability short.** It is the
first call of every run, it consumes the user's brief, and it already emits a
classification:

| mode | meaning today | today's behaviour |
|---|---|---|
| `full_edit` | the request describes a vibe | edits |
| `targeted_change` | names specific families | edits, scoped to those families |
| `question` | asks something | answers, edits nothing |
| `unsupported` | needs footage that does not exist | **terminates**, charges nothing |

`unsupported` carries a class already: `generate_footage` ("add a shot of a
city", "put some b-roll over this") and `change_in_frame` ("remove the
background", "make it night").

**So the router exists and its fourth branch is a refusal.** Building the
generation surface is not adding a router — it is turning one branch of the
existing one from a terminal into a route. That is the zero-reject law arriving
at the capability layer: *content classes are ROUTES, not errors* becomes
*capability classes are ROUTES, not errors*.

Nothing new reads the request. `unsupported_class` becomes `route`.

## 2. What it can route to

| route | status | what it does |
|---|---|---|
| `edit` | **BUILT** | this app: cut, caption, text, card, zoom, sfx, transition, cutaway over the user's own footage |
| `generate` | **UNBUILT** | a clip that does not exist in the upload. Mounted material: `arcads-claude-code` (Seedance 2.0, Sora 2, Veo 3.1, Kling 3.0, Nano Banana), un-ignored 2026-09-10 for exactly this surface |
| `edit + generated insert` | **UNBUILT** | the hybrid, and the one that actually gets asked for: "add a shot of a city" means *keep my edit and put a generated clip in it* |
| `question` | **BUILT** | answers, edits nothing |
| `change_in_frame` | **UNBUILT, and not arcads' shape** | editing pixels inside existing footage (background removal, wardrobe) is an image-edit surface, not a clip generator. Named separately so it is not routed to a generator that cannot do it |

**The hybrid is the default case, not the exotic one.** Every
`generate_footage` phrasing in the schema today is additive: *add* a shot, *put*
b-roll *over this*. A router that treats generate and edit as exclusive answers
the question nobody asked.

## 3. When two are plausible

**It asks. The mechanism is already built and shipped: K5.**

`set_spec.clarification` stops the run through the same path as `unsupported` —
no plan, no render, no charge — and `result_agentic` returns `NEEDS_INPUT`
carrying the question. The server shows it and re-dispatches with the answer
folded into the brief.

This is the one place where asking is unambiguously right, because **the two
routes differ by two orders of magnitude in time and by an unmeasured amount in
money**. "Make the intro punchier" against a source with no usable intro is
either a tighter cut or a generated opener, and guessing wrong costs either the
user's money or the user's edit.

Three rules for the router, in the order they apply:

1. **Additive phrasing routes to hybrid, never to pure generate.** "Add", "put
   in", "over this" all keep the edit.
2. **When the request names a capability the pipeline has, take it.** A brief
   that can be satisfied by cutting is satisfied by cutting; the generator is
   not a tie-break.
3. **Otherwise ask, and name both readings in the question.** Not "what do you
   mean" — "do you want me to tighten what you shot, or generate a new opening
   shot? The second takes minutes and costs more."

The one thing the router must NOT do is pick silently and label it a preference.
That is the `full_edit`-for-a-narrow-request failure at the capability layer,
and `spec_fidelity` already exists to catch its smaller cousin.

## 4. Cost and latency, per path

### `edit` — MEASURED

Population: 15 runs, rounds 51/52/54, five fixtures × three rounds. Wall clock
from the ledger's own `wall_s`.

| fixture | source s | wall p50 | wall max |
|---|---|---|---|
| car_short | 10.0 | 219.0 | 253.7 |
| car_mid | 13.8 | 203.3 | 327.3 |
| talking_head | 20.4 | 226.8 | 233.5 |
| motion | 27.9 | 254.3 | 372.4 |
| screen_recording | 90.5 | 328.4 | 416.2 |
| **all** | | **233.5** | **416.2** |

Tokens over the same 15 runs: `in 748`, `out 49,031`, `cache_read 3,252,219`,
`cache_write 165,258` — about 217k cache-read and 3.3k output per run.

**Two things this table says that the router needs and one it says to us.**
Latency scales with source length, not with how much is placed. And **an edit
is not "seconds": p50 is 233.5s against a 90s latency law**, so the framing
"generated clips are minutes and edits are seconds" is not true of this pipeline
today. The router must compare 4 minutes against whatever generation costs, not
4 seconds.

**`cost_usd` is ABSENT from the ledger.** It carries `tokens` and
`tokens_by_model` and no dollar figure, and Modal container time is not in it at
all. A router that needs to price a decision cannot price the path we have
already built. **This is the first thing to fix and it is cheap** — the token
counts and the wall clock are both already there.

### `generate` — ABSENT

No number. Not "minutes" — **ABSENT**, because nothing here has ever called a
generator. What is required before the router may quote a figure:

- per-model wall clock for a 4–15s clip, measured, not taken from a vendor page
- per-clip dollar cost from an actual invoice line
- failure rate and what a failure costs (a refused generation still bills)
- whether the clip lands in a usable aspect and frame rate, or needs a
  normalising pass that the edit path then pays for

Until those exist the router may say *"this takes longer and costs more"* and
may not say a number. **`unsupported_request` was built to be the demand signal
and has fired ZERO times across rounds 51–55** — so the case for building
generation at all currently rests on an ABSENT count, not a low one. The fixture
corpus contains no generate-shaped brief; nobody has asked it in a measured
window. That is the cheapest thing to learn next and it needs real traffic, not
a fixture.

## 5. What I would build first, in order

1. **`cost_usd` on the edit path.** It is arithmetic over numbers already in the
   ledger, and no routing decision can be priced without it.
2. **Turn `unsupported` into `route`** with `edit`/`generate`/`hybrid`/
   `change_in_frame`, still terminal for the three unbuilt ones, still charging
   nothing — and start counting. The demand signal has to exist before the
   surface does.
3. **The router's ask**, which is K5 with a capability-shaped question and both
   readings named.
4. **Only then** the generation call, priced from a real invoice.

Steps 1–3 are this app and this lane. Step 4 is a different surface and should
not live in `agentic_editor_app.py`: it holds no vendor credentials, and a
container that edits video has no business holding a generation API key.

## 6. What is already true and must not regress

- Asking charges nothing, and both terminals say so at two sites each
  (`smoke_five_families`, per-terminal, terminals discovered from the source).
- A capability we do not have is refused **plainly and without a competent edit
  delivered in its place** — "do NOT deliver a competent edit that ignores what
  they asked for; that reads as the product not working."
- The request is the complete specification, and placing more than was asked is
  a failure (`spec_fidelity`). A router that upgrades a cut request into a
  generation is that failure with a bigger bill.
