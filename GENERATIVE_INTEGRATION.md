# GENERATIVE INTEGRATION — design `[§3.2, §6.2]`

**Design only. Written 2026-08-12, buildable today with no provider access.**
The point is that when the owner picks a provider, the build is a wiring job
rather than a research project. Nothing here spends a cent or assumes an
account.

**What it serves:** §3.2 — *"DOES ANY REQUEST — including generative, Veo-class
changes to the footage itself"* — the #2 value in the spec, currently not
started, with the architecture slot already present (§5).

---

## §1 What "generative" means here, precisely

Three capability classes, deliberately separated because they have different
costs, latencies and failure modes:

| class | example ask | changes the footage? | §4.1 |
|---|---|---|---|
| **G1 · synthesis** | "add a shot of the city at night" | no — new footage beside yours | carve-out |
| **G2 · transformation** | "make it look like it was shot at golden hour" | **yes — your pixels** | carve-out |
| **G3 · extension** | "make this clip longer / fill the gap" | yes | carve-out |

**All three take the §4.1 carve-out. Editing never does.** That boundary is the
whole reason the classes are named separately: a request that can be served by
the *editing* toolbox must never be routed to a generative provider, because
that would trade a 120s promise for a multi-minute one to deliver something the
existing toolbox already does. **Generative is the last resort, not the first
reach** — the same discipline as `generated_scenes`' rarity rule.

Existing machinery this reuses rather than duplicates:
- `_vibe_requests_generated_scene` (`handler.py:870`) — the ask detector shape.
- The `_UNSUPPORTED_CAPABILITIES` honesty channel — G1–G3 come **off** that list
  as they land, and not one moment before (§4.6: the note follows the artifact).
- `adapter_contract.py` — generated footage is a `FootageRef` like any other, so
  the render layer needs no new concept.

---

## §2 Provider evaluation — the axes, and the disqualifiers

**No provider is named as chosen here. That is the owner's call.** What is fixed
is *how* they get compared, so the decision is made on a table rather than a
demo reel.

### Disqualifiers (any one → out, before quality is even discussed)

1. **No commercial licence for user-generated output.** The product sells the
   output; a research licence is unusable.
2. **No content provenance / C2PA-style marking** where the platform requires it.
3. **Per-request latency with no progress signal.** §4.1's carve-out demands an
   honest progress contract — a provider that returns only a final blob makes
   "generating your scene, ~Xm" a lie.
4. **No deterministic seed.** Without it there is no A/B, no differ, no
   regression test — §4.7 becomes unenforceable and the harness goes blind.
5. **Training on our users' footage** with no opt-out.

### Scoring axes (each measured on the SAME brief set)

| axis | how it is measured | why it decides |
|---|---|---|
| **fidelity to the ask** | the fulfillment judge, same rubric as editorial | §3.2 is "does any request", not "does something" |
| **subject consistency** | same subject across 2 scenes in one edit | a face that changes between beats is worse than no scene |
| **motion coherence** | frame-diff for warping/morphing artifacts | the #1 giveaway of generated video |
| **p50 / p90 latency** | wall clock, 5s and 10s outputs | drives the progress contract's honesty |
| **$ per delivered second** | provider price ÷ accepted outputs | see §3 |
| **acceptance rate** | fraction passing the judge first try | a cheap provider with a 30% accept rate is not cheap |

**The brief set is the owner's reference examples (§7.1).** Evaluating on
anything else measures a provider against my taste instead of his.

---

## §3 Cost model — the numbers that decide whether this ships at all

The binding constraint is **§2's $40–50/month price** and the standing **$0.10
per job** cost law. Generative is one to two orders of magnitude above editorial
per unit, so it cannot be silently folded into a flat plan.

```
effective_cost_per_delivered_second
    = provider_$_per_second ÷ acceptance_rate
      + judge_cost + storage + the retry tail
```

Acceptance rate is the term people forget and it dominates: at a 50% accept
rate the true cost is **2×** the sticker price, plus a second full latency
budget the user is waiting through.

### The three viable commercial shapes

| shape | mechanics | risk |
|---|---|---|
| **A · metered credits** | generative asks consume a visible balance | the honest one; adds a concept to a product whose §1 identity is "no UI" |
| **B · fair-use ceiling** | N generative seconds/month inside Pro, then negotiate | preserves §1; a heavy user is subsidised by everyone |
| **C · premium-tier-only** | generative is the paid tier's capability | matches §3's ranking; **inherits Lumen's exact problem — a capability that sells the tier is invisible until you buy the tier** |

**Recommendation, offered as one line and not as a decision: B, with A's meter
kept dark behind it.** B protects §1 (nothing new appears in the interface until
a ceiling is actually hit, and then it is a *sentence in the conversation*, which
is what §1 says the interface is). A's meter exists so that if the economics
turn out worse than the model predicts, the switch is a flag rather than a
rebuild. **The pricing call is the owner's.**

### The go/no-go gate, pre-registered

> Ship generative only when `effective_cost_per_delivered_second × the p90
> generative ask` fits inside one month's margin at $45, **at the measured
> acceptance rate — not the sticker rate.**

Pre-registering this is the point: it is the number that will be tempting to
round in the provider's favour once a demo looks good.

---

## §4 The §4.1 carve-out contract — honest progress in the chat

§4.1: editing is ≤120s, **always**. Generative may exceed it **and must say so,
in the conversation, before the wait starts.**

### The contract

```
user:      "add a shot of the city at night"
assistant: "That needs a generated shot — about 2 minutes, longer than a normal
            edit. Want me to go ahead?"        ← ASK FIRST when over the line
user:      "yes"
assistant: "Generating your shot — about 2 minutes."   ← estimate, stated once
           … periodic honest progress …
assistant: "Here's your edit."                          ← §4.6: note follows the artifact
```

Five rules, each earned from a defect already in this codebase:

1. **Ask before spending the user's time**, whenever the estimate exceeds the
   editing promise. The §4.1 carve-out permits the wait; it does not permit
   surprising someone with it.
2. **The estimate is a measured p50, re-derived weekly** — never a hardcoded
   guess. A wrong estimate is a broken promise with extra steps.
3. **Progress is real or absent.** A fake progress bar is the same class as a
   note that describes intent rather than artifact (§4.6). If the provider
   gives no signal, say "this can take a few minutes" and give no bar.
4. **Failure is honest and free.** A failed generation costs the user nothing,
   says what happened, and delivers the edit without the generated beat rather
   than failing the whole job. Zero-reject applies: generative failure is a
   *route*, not an error.
5. **The wait is interruptible.** "Never mind" cancels and delivers what exists.

### What must NOT happen

- Generative silently entering an ask that the editing toolbox could serve —
  that trades a 120s promise for minutes to deliver the same thing.
- The 2-minute law quietly widening because generative made long waits normal.
  **The carve-out is per-ask, not per-product.**

---

## §5 Build order when a provider is picked

1. **Provider adapter behind `PROMPTLY_GENERATIVE_V1`**, dark, one interface:
   `generate(brief, seed, duration_s) -> FootageRef | None`. `None` is a route,
   never an exception (§4.5).
2. **The ask classifier** — G1/G2/G3 vs "the editing toolbox already does this".
   Deterministic, after the model (§4.3a). This is the gate that keeps
   generative from eating editing asks, and it is the highest-risk piece.
3. **The chat contract** (§4 above) — ask-first, real progress, honest failure.
4. **Cost meter + the pre-registered go/no-go**, before any user sees it.
5. **Judge + differ integration** (§4.7) — seeds pinned, so a generative change
   is as testable as an editorial one.

Steps 1–4 are buildable the day a provider is named. Step 2 is buildable
**now** and is the one worth writing first, because it is the piece that
protects §4.1 and it needs no provider at all.

---

## §6 Open, and owner-owned

1. **Provider choice** — evaluated on his reference briefs (§7.1), on the table
   in §2.
2. **The commercial shape** — A, B, or C (§3).
3. **Whether G2 (transforming the user's own pixels) ships at all in v1.** It is
   the highest-wow and the highest-risk: a user's face altered by a model is a
   different trust conversation than a generated cutaway beside their footage.
   I have no view worth acting on; it is a brand call.
