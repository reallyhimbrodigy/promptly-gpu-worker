# LIVE DEFECT: a repair tool that structurally cannot reach three families

**Found:** 2026-09-07, by Builder-2, while porting transitions.
**Fixed on:** `lane/parity-sizing` (commit b860d25).
**Filed separately because it is not a parity gap** — it was live before this
port started, and a contract repair on sfx, zoom or transition has been a no-op
for as long as `rule_all_beats` has offered more families than `beat_verdict`.

## The defect

`agentic_editor_app.py` has two ruling surfaces:

```python
# rule_all_beats — the main surface
"treatment": {"type": "array",
              "items": {"enum": ["card", "text", "sfx", "zoom", "none"]}}

# beat_verdict — the per-beat repair surface
"treatment": {"type": "string",
              "enum": ["card", "text", "none"]}          # <-- three
```

`beat_verdict` is **live**. It is in `_REPAIR_ONLY`, and that set *gates* rather
than removes:

```python
_REPAIR_ONLY = {"build_cut", "build_overlays", "build_zoom", "place_sfx",
                "render_components", "author_component", "beat_verdict"}
```

The dispatch refuses those tools **until `execute_plan` has run**, and then
allows them. So the repair path — the one the agent reaches for precisely when
something came out wrong — could only ever re-rule a beat as `card`, `text` or
`none`.

## What that costs

A contract failure on sfx, zoom or transition is exactly the situation
`beat_verdict` exists for: `execute_plan` reports `ruled_not_built`, the agent
tries to repair that beat, and the enum has no word for the family that failed.
The most likely outcomes are both silent:

- it re-rules the beat as `text` or `card`, quietly changing the edit's intent
  rather than fixing the placement; or
- it re-rules as `none`, deleting the placement it was asked to repair.

Neither errors. The run finishes, the accounting balances (the beat now
genuinely has no sfx), and the repair reads as a decision.

**Nothing in the ledger distinguishes "the agent decided against a sound" from
"the agent could not say the word."**

## How it was found — and why it survived so long

`_assert_treatment_surface_agrees()` exists for this exact class. Its own
docstring:

> The PROSE must not offer a narrower family set than the SCHEMA. Shipped
> exactly this bug 2026-09-05 […] A stale narrow list is invisible: everything
> parses, the schema accepts the wide form, and the only symptom is a family
> that never appears.

It could not see this, because it looked for **one remembered spelling**:

```python
stale = _re.findall(r"'card'\s*\|\s*'text'\s*\|\s*'none'"
                    r"|\"card\" \| \"text\" \| \"none\""
                    r"|'card'\|'text'\|'none'", module_src)
```

That matches the narrow set written as PROSE, in three punctuations. It does not
match the same narrow set written as a JSON-schema `enum` list — which is where
it actually was. The check was hunting a string it had seen before instead of
comparing the two surfaces it existed to keep in agreement.

It fired the moment it started comparing them:

```
AssertionError: the treatment enum offers ['card', 'none', 'text'] while
_TREATMENT_FAMILIES declares ['card', 'none', 'sfx', 'text', 'transition',
'zoom'].
```

## The fix, and the check that makes it stick

`beat_verdict`'s enum now carries the same six families as `rule_all_beats`.

`_assert_treatment_surface_agrees` now walks the AST for every schema `enum`
that looks like a treatment surface and asserts set-equality with
`_TREATMENT_FAMILIES`. It runs at **import, in the container, on every launch** —
not in a test file that can be skipped. A third surface added later is covered
without anyone remembering this filing exists.

`smoke_five_families` asserts the family set by MEMBERS, not by count, so a
family cannot quietly swap identity either.

## The general shape, for whoever reads this next

A capability the agent cannot NAME is indistinguishable from one it declined.
Every surface that accepts a family — the main ruling tool, the repair tool, the
spec, the prose — has to be generated from or checked against one list. Two
hand-maintained copies of the same vocabulary will diverge, and the divergence
is silent by construction: the narrow one simply never produces its missing
members, and no reader can tell that from restraint.
