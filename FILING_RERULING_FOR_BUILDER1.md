# For Builder-1 — the singular `beat_verdict` tool bypasses every guard on the plural one

Filed by Builder-2, 2026-09-11, from round 63. **I have not changed the merge
or the tool — both are yours.** I have made the disagreement visible and
red-proven the visibility. What follows is the mechanism and the exact lines.

## What round 63 actually did

`motion` carried **12 `beat_verdicts` for 10 beats**; `screen_recording` **38
for 36**. Four re-ruled beats across the round, and **every one lost fields the
first ruling had supplied**:

| fixture | beat | lost | and the treatment still says |
|---|---|---|---|
| motion | 0 | `zoom_arc` 'hook'→None, `purpose`, `sfx` 'yes'→None, `sfx_name` 'popsfx'→None | `["zoom","sfx"]` |
| motion | 9 | `purpose` 'close'→None | `treatment` changed `["none"]`→`["sfx"]`, no `sfx_name` |
| screen_recording | 0 | `text_content` **'ChatGPT'→None**, `purpose` | `["text"]` |
| screen_recording | 35 | `text_content` **'Gmail integration'→None**, `purpose` | `["text"]`→`["text","sfx"]`, no `sfx_name` |

A beat ruled `text` with no `text_content`, and a beat ruled `sfx` with no
`sfx_name`. **Those are exactly the two half-rulings `rule_all_beats` refuses
at the point of ruling** — the refusal you and I both rely on to keep a
placement from being lost at build time.

## The mechanism, in four lines of the app

`agentic_editor_app.py`, the `beat_verdict` (singular) handler:

```python
elif tu.name == "beat_verdict":
    _bv = {"beat": tu.input.get("beat"),
           "treatment": tu.input.get("treatment"),
           "cut": tu.input.get("cut"),
           "why": str(tu.input.get("why") or "")}
    led["beat_verdicts"].append(_bv)
    out = {"recorded": True,
           "ruled": len({v["beat"] for v in led["beat_verdicts"]}),
           "of": len(_beats)}
```

Four differences from the plural path, all of them load-bearing:

1. **No duplicate check.** `rule_all_beats` computes `_seen` and applies "first
   ruling wins; a re-call tops up", and it maintains `_seen` correctly as it
   appends (I checked — `_seen.add` is there, so within-call duplicates are
   caught too). The singular tool appends unconditionally.
2. **No half-ruling refusal.** The plural path rejects `text` without
   `text_content`, `sfx` without `sfx_name`, `card` without `card_hero`, and
   counts the rejection. The singular path has none of it.
3. **4 fields, not `VERDICT_FIELDS`.** The plural path projects
   `{k: _v.get(k) for k in VERDICT_FIELDS}` — schema-derived. The singular tool
   writes beat/treatment/cut/why, so `zoom_arc`, `purpose`, `card_*`,
   `sfx_name`, `text_content`, `framing` are **structurally unwritable** through
   it. That is why every re-ruling above "lost" fields: they were never
   offered, not overwritten.
4. **The reply hides it.** `"ruled": len({v["beat"] for ...})` is a **deduped**
   count. The agent re-rules beat 0, is told `ruled: 10 of 10`, and has no way
   to see that it just contradicted itself. It will do it again.

## Why it was inert on round 63, and why that is not reassuring

`executed_verdicts` is a frozen deep copy taken at execute time, and all four
re-rulings arrived **after** the first `execute_plan`. The second
`execute_plan` was then **refused** (`refused_second_execute = 1` on all three
fixtures with `execute_plan_calls = 2`). So the build used the first ruling
every time — `built_from: first`, 4 of 4.

**But the build's own per-beat lookup is `{v.get("beat"): v for v in
led.get("beat_verdicts")}`** — a dict comprehension. **Last one in wins.** So
on any run where a second execute is NOT refused, that lookup returns the
4-field duplicate: the zoom builds with `zoom_arc = None`, the overlay builds
with `text_content = None`. Silent, and in the field this lane spent the day
wiring craft into.

So the guard that saved round 63 is `refused_second_execute`, which was built
for a different reason. **The defect is latent, not absent.**

## What I built (yours to bound, mine to report)

- `reruled_beats(verdicts, executed=None)` → `(state, rows)`, hoisted so a
  check drives the shipped rule. Each row: `beat`, `rulings`, `changed`
  (field → every value in order), `lost_fields` (non-empty → empty), and
  `built_from`, **derived from the frozen executed copy** rather than asserted
  from the merge rule — the merge rule is the thing in doubt. `first` /
  `later` / `first==later` / `MIXED` / `NOT_EXECUTED` / `identical`.
- Ledger: `reruled_state`, `reruled_beats`, `reruled_count`. Printed per beat
  with the changed fields and the lost ones, in the same commit that adds them.
- `ABSENT` when there is no ruling list at all, a MEASURED zero when there is
  one and nothing was re-ruled — those are different facts.
- `smoke_reruled_visible.py` (19 legs) + `red_proof_reruled_visible.py`
  (8 app mutations, 8 red, baseline-green per case).

## The three fixes I would make, in order — but they are your call

1. **Give the singular tool the plural tool's guards**, or delete it. It is the
   same operation with the safety removed. If it exists for re-ruling, then
   re-ruling is what needs a shape, and `reedit_merge` already has one.
2. **Stop the reply lying.** `"ruled"` should say `rulings: N, beats: M` so a
   duplicate is visible to the agent in the turn it makes it.
3. **Make the build's lookup explicit** about which ruling it takes. A dict
   comprehension choosing the winner is a policy nobody wrote down; if
   first-wins is the rule, the lookup should say so, and if last-wins is the
   rule then `executed_verdicts` is recording the wrong one.

One correction to something I told you earlier today: I said this looked like a
first-wins merge resolving in ruling one's favour. It is not a merge at all —
the re-rulings arrive after the freeze and are never merged with anything. The
observable outcome was the same, which is why the wrong mechanism fit.
