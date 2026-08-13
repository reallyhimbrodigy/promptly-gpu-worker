# QUALITY_CAMPAIGN — ranked by PRODUCT_SPEC §3, sequenced by §6

**Rewritten 2026-08-12 against the constitution.** The previous ranking was
mine and it was wrong: it led with floor work (payoff, density, captions) and
put the premium look sixth. §3 ranks the premium look **first** and §6.4 files
payoff/density/captions as **floor maintenance, never the headline**. This file
now follows the spec, not my judgement.

Every item cites its section (§8). An item that cannot cite one is not in this
file.

---

## THE LOOP — unchanged, applies to every item (§4.7)

```
change dark  →  differ verdict in HOURS  →  fulfillment + export delta in a DAY  →  keep or kill
```

Three standing rules: **RED is HELD, never tuned in-window** · a differ GREEN
means "the corpus saw no regression", **not** proof of improvement — improvement
is a taste call on pixels, the owner's, never mine · **no pair reaches him that
has not been programmatically proven to differ.**

---

# CAMPAIGN #1 — LUMEN REVIVAL `[§3.1, §6.1]`

**The #1 value in the spec. Fires 0 in 2,074 production jobs.**

## Step 1 — DONE TODAY, no Gemini required: the trigger is named

The mechanics are proven end to end. Nothing is broken in Lumen. **The model is
never told generated scenes exist.**

```
server.js:5020-5022   premiumPipeline = entitlement.isPro === true
                                     && body?.premium_pipeline_enabled === true
                                     && premiumPipelineEnabled()
server.js:590-592     premiumPipelineEnabled() → process.env.PREMIUM_PIPELINE_ENABLED
render.yaml           ← NOT DECLARED. THE TRIGGER DIES HERE.
dispatch-to-modal.js:1024   premium_pipeline_enabled: false   (always)
handler.py:35879-35880      route_premium = is_premium AND _premium_flag_on → False
handler.py:7746             if premium:   ← the GENERATED SCENES directive never appends
```

`handler.py:7746` is the last gate: the entire generated-scenes art-directive is
appended **only** when `premium` is true. It never is. So the model has never
once been asked for a generated scene, and 0/2,074 is not the model declining —
it is an instruction that was never sent.

**Evidence [MEASURED], probe proven live by its own population:** 6,329
`render_started` events since 2026-07-01 carry `premium: false` — **6,329 of
6,329**.

*(Recorded because it nearly became a false finding: my first probe read
`route_premium` out of `result` and returned a confident 0. That key is a
`render_burst` payload (`handler.py:25487`) and is never persisted. Discarded,
not reported.)*

## Step 2 — the second cause, independent of the first

**`profiles.tier` = 3 pro / 997 free.** Even with the flag on, `entitlement.isPro`
gates Lumen to **0.3%** of the base. Flipping the env var does not produce a
campaign; it produces three users' worth of Lumen.

**This is a §3 tension for the owner, not a bug and not my call.** §3 says the
premium look is *what makes it worth $50 instead of $10* — but it is currently
reachable only by users who already pay, and only if they open a model picker
and choose it. A capability that can only be seen after purchase cannot do the
selling. Whether Lumen is the paid tier's reward or the product's shop window is
a pricing decision, and it is his.

## Step 3 — what unblocks, in order

1. **Owner: declare `PREMIUM_PIPELINE_ENABLED`** on Render. `/api/health` now
   reports `premium_pipeline` so this is a curl, not a log dig — shipped today
   for exactly this reason.
2. **Owner: the Lumen blind-sheet scores** (§7.2). They calibrate the judge for
   the #1 value; nothing downstream is trustworthy without them.
3. **Owner: the reference set** (§7.1) — he has offered generated-graphics
   examples. Those seed the golden references the look is tuned against.
4. **Then me:** wire Lumen into the live flow, quality-tune the scenes against
   his references until the look commands the price.

**Until 1–3 land this campaign is owner-blocked, and no amount of my building
moves it.** That is the honest status, and it is why the diagnosis was worth
doing today: it converts "why doesn't Lumen fire" from a research project into
three decisions only he can make.

---

# CAMPAIGN #2 — GENERATIVE INTEGRATION `[§3.2, §6.2]`

Veo-class changes to the footage itself — the #2 value, **not started**. Design
is buildable today with no provider access: see `GENERATIVE_INTEGRATION.md`
(provider evaluation, cost model, and the §4.1 honest-progress carve-out
contract). Design lands first so that when the owner picks a provider the build
is a wiring job, not a research project.

---

# CAMPAIGN #3 — SURGICAL DEPTH `[§3.3, §6.3]`

The deferred re-plan ops (re-cut, timing shifts). Deliberately sequenced after
226 ships, because 226 is what finally generates a real re-edit corpus — building
surgical depth against an imagined corpus is how the re-edit taxonomy went wrong
the first time. `PROMPTLY_SURGICAL_V2` is built dark and flips at ignition.

---

# CAMPAIGN #4 — THE FLOOR, CONTINUOUSLY `[§3.4, §6.4]`

**Ranked last by the spec and that is correct — but "last" means "held at
pro-freelancer parity forever", not "neglected".** §3's interpretation is
binding: the floor is mandatory, assumed, and invisible when right. These run at
ignition as floor maintenance. **None of them is the headline.**

| item | status | measured gap | loop |
|---|---|---|---|
| **COMPONENT_OBEY** `[§4.5]` | built dark | cluster silent-drop **94% on lean** (n=215) | flip → differ → lean silent-rate 94%→<20% over ≥150 asks |
| **Payoff arms 6+7** `[§6.4]` | built dark | 0 punchy payoffs / 253 | one differ pass, ~$0.20, PLAN_ONLY |
| **Caption translate** `[§4.5]` | built dark | 50 asks, 23 silent (46%) | flip → differ → that class's silent rate |
| **Density / moment tuning** `[§6.4]` | not started | 63% of std-editorial carry **zero** MGs; 7.76 vs the owner's 16.7 per 25s | measure H3/H4 **free** first |
| **Upscale v1** `[§3.2 edge]` | live dark | 195 asks | flip → the class stops dropping |

**Density's free measurement comes first.** The E1 ceiling is *architectural,
not prompt-tunable* — multi-gate culling. H3 (projection-miss drops) and H4
(render collision/floor drops) are **post-model** and cost $0 to count on
existing traffic. Arming a prompt arm before that measurement burns a window on
the wrong layer.

**Payoff arms carry one correction to my own framing:** 0/253 is the system
**obeying** the owner's twice-expressed doctrine. It is not a defect. Arm 7
neutralises the prose so "never picked" can finally mean judgement rather than
obeyance — it produces the pixels his ruling stands or falls on, and changes
nothing by itself.

---

# CAMPAIGN #5 — THE TWO-MINUTE LAW `[§4.1, §6.5]`

Staged latency levers validated at ignition (`PROMPTLY_HLS_COPY` is already on),
plus a premium-path budget until Lumen-class edits land ≤120s. The §4.1
carve-out is explicit: generative operations may exceed it **with an honest
progress contract in the chat**; editing never does.

---

## A CONFLICT I HAVE TO DECLARE `[§4.4]`

**§4.4 makes the legacy lean routes anti-spec** — "no route may strip the
toolbox; simplicity is restraint guidance on the full core, never removed
capability."

**COMPONENT_OBEY's note leg is built on the opposite premise.** Its
`_ROUTE_TOOLBOX` encodes lean routes as having an *empty* toolbox and writes an
honest note saying so ("this clip took the clean re-pace route, which doesn't
build them").

Both things are true at once:
- Under **§4.5**, the note leg is correct and is the single biggest honesty win
  available (94% → <20%). It should still flip at ignition.
- Under **§4.4**, the note is a **transitional** artifact. The compliant end
  state is the unified core's restraint profiles, where the toolbox is never
  stripped and the note becomes unnecessary because the ask can simply be
  honored.

So: **ship the note leg now, retire it with the unified core.** I have not
changed the code — the note is honest today and honesty now beats architectural
purity later. But it is on record that `_ROUTE_TOOLBOX`'s empty sets are
spec-debt with a named payoff date, not a design I intend to keep.

---

## WHAT THIS CAMPAIGN WILL NOT DO

### Struck 2026-08-12 `[§4.8]`

**Background music: REMOVED, not deferred.** §4.8 — dead-purpose code does not
stay dark, it goes. The bed synthesis, selection, placeholder tracks, sidechain
chain and its cert are deleted from the tree.

What did NOT go with it is the **ask**. 72 people wanted music; deleting the
build does not delete the demand, and §4.5 is unconditional. The ask now lives
in COMPONENT_OBEY's **negotiated-never** vocabulary, unflagged: *"Promptly
doesn't add background music — your edit uses your own audio, cut and balanced
around what you actually said."* It deliberately does not say "yet" — that word
belongs to a roadmap, not to a decision.

SFX mixing and speech normalization are untouched. They are the edit.

- **No new instruments, no new watches** until launch (owner's standing order).
- **No tuning inside a window.** RED is held.
- **No taste call made by me.** I build the choice; he makes it.
- **Nothing in §6.1–§6.3 is claimed as progress while it is owner-blocked.**
  Campaign #1's honest status today is: diagnosed, and waiting on three
  decisions.
