# FILING — type the MG `props` field as a discriminated union

**Status: FILED, next model-contract change.** Not shipped in this batch: it
changes the response schema every editorial call is made against, so it wants
its own window, its own A/B, and its own RED proof rather than riding behind a
caption fix and a name plate.

---

## The defect, at both layers

**Pydantic model** — `handler.py:_MotionGraphic`:

```python
props: Dict[str, Any] = Field(default_factory=dict)
```

**The prompt's JSON shape** — what the model is actually shown:

```json
"motion_graphics": [{
  "type": <28-way enum>,
  "why": "<=12 words: the moment that asked for this>",
  "start_word_index": int, "end_word_index": int,
  "duration_seconds": float | null,
  "anchor": "upper_third_safe" | "center" | "lower_third_safe",
  "props": {...}          <-- a literal, unspecified black box
}]
```

The model is told **what each component needs** in prose elsewhere in the
prompt — *"StatCard (MEDIUM) — hero number (~120-180pt, white) counting up
digit-by-digit from 0 to target; accent divider; caps label below"* — and is
then given no typed place to put `value`, `label`, `suffix` or `accentColor`.

**So it put them in `why`.** Observed directly on the trigger-source render:

```json
{"type": "StatCard", "start_word_index": 26, "anchor": "upper_third_safe",
 "why": "visualizes two years of editing experience quoted directly in dialogue
         context header: EXPERIENCE value: 2 suffix: YRS accentColor: #F5C..."}
```

`why` is capped at **12 words** in the prompt (240 chars in Pydantic). The model
overran it to ~30 words because it had nowhere else to go. Both MGs on that
render were then dropped:

```
component=motion_graphic action=drop_empty_props
  reason=empty props dict — grounding miss dropped at the component
```

**The props were present. They were in the wrong field. We dropped them and
recorded it as the planner declining.**

## What is NOT established, stated plainly

I reported "props empty on 210 of 210 historical MG entries — 100%". **That
measurement was invalid and is withdrawn.** It read `edit_recipe.plan
.motion_graphics` from the DB, whose entries carry keys
`['end_s','start_s','text','type']` — the **render-side projected shape**, not
the model's plan shape. It measured the wrong object.

**The historical props-in-prose rate is therefore UNMEASURED.** The only
confirmed instance is the one render read directly. The claim that this "may
retire the 62%" is a hypothesis with n=1 behind it, and the measurement should
come from the S3 divergence ledgers (`[divergence-ledger] persisted N`), which
hold the model's raw plan, before any of this is treated as sized.

## The change

A discriminated union on `type`, so the model fills a form instead of guessing:

```python
class _StatCardProps(BaseModel):
    value: str                      # the number as spoken
    label: str                      # caps label beneath
    suffix: Optional[str] = None
    prefix: Optional[str] = None

class _PillClusterProps(BaseModel):
    tags: List[str] = Field(min_length=2, max_length=5)

# ... one per MG type, then:
props: Union[_StatCardProps, _PillClusterProps, ...] = Field(discriminator=...)
```

**The TS `types.ts` files are the source of truth** — each component already
declares exactly what it needs (`NamePlateProps`, `EndCardProps`, etc. are
precise and well-commented). The Python union mirrors them, which makes this the
**fourth instance of the mirror-drift class** (render_schemas ↔ types.ts ↔
handler ↔ prompt), so it must ship with a mirror check, not a note.

**Colour props are already governed** by `art_invariants.in_palette()` — a
component emitting an off-palette colour is a §6 defect, and the invariants layer
shipped in this batch can enforce it the moment props are typed.

## Sizing honestly

28 MG types in `VALID_MG_TYPES`. Not all need props (some are pure timing), and
the TS types already exist, so this is mechanical rather than inventive — but it
is 28 models plus a prompt-shape rewrite plus a mirror cert, and it changes the
schema of **every editorial call**. It is not a small diff even though it is a
small idea.

## The check, named before the work (Rule 1)

1. **Mirror cert** — every MG type in `VALID_MG_TYPES` has a props model, and
   its fields match the component's TS `types.ts`. Fails on drift in either
   direction. This is the check the other three mirrors each learned the hard
   way.
2. **No free-form escape** — `Dict[str, Any]` may not reappear as the props
   type, or the form becomes optional again.
3. **A production counter** — MGs *requested* vs MGs *rendered*, per type. The
   whole point is that these two numbers currently differ and nobody measured
   it. Without the counter this ships and we still cannot say whether it worked.

## Risk worth stating

A typed schema the model cannot satisfy is worse than a loose one: if a required
prop is genuinely underivable from the transcript, the model will either
fabricate it or drop the component — and fabrication is the failure mode the
brand-copy directive explicitly forbids. **Every required field must be
answerable from what the speaker actually said.** Optional-by-default, with only
the genuinely load-bearing fields required.
