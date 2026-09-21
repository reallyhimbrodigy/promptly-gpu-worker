# ported_mg batch 1 — and a correction to the premise

**Builder 2, 2026-09-21.** Reported before the batch is complete, because the
measurement changed what the task is.

## The correction: the 153-binding transform is ALREADY DONE

The instruction was "26 bodies, 153 top-level bindings moved inside, one build
step doing it mechanically". Measured, three ways:

| population | count | top-level bindings |
|---|--:|--:|
| `ported_mg/*.jsx` — the raw compiled blobs | 29 | **1,862** |
| `chatcut_registry.json` `components` — the contract-shaped code | **18** | **0** |

The raw blobs do carry the bindings (1,862, not 153 — that figure was carried
from memory and is wrong). But **the blobs are not what registers.** The
registry already holds a rewritten body per component: one top-level
`const Component`, `props` bound from `item.props`, every binding moved inside,
every declared property read through a `__mapped` block. Someone already did the
transform. Writing it again would have been work with no output.

The 29 account for themselves exactly: **18 contract-shaped + 10 refused + 1
superseded (StickyNotes)**. There is no set of 26 in the tree; "26" traces to
`smoke_registry_obeys_the_contract.py`'s docstring — "26 of 29 frame-diff
identical to Remotion" — which counts fidelity, not portability.

**So the remaining work per body is REGISTER · PLACE · FRAME**, which is the
three proofs, and nothing else.

## The checker would have blocked all 18, and it is wrong on two rules

`smoke_registry_obeys_the_contract.py` reads PASS 0 / FAIL 18 on the registry.
Both failing rules are text matches that convict correct code:

| rule | what it asserts | why it is wrong |
|---|---|---|
| `plain_div_root` | `"AbsoluteFill" not in code` | the contract forbids AbsoluteFill **as the ROOT**. Every one of the 18 has a plain `<div style={rootStyle}>` root and uses AbsoluteFill only as an inner layer, which is allowed — and two of the four hits are in COMMENTS |
| `no_Freeze` | `not re.search(r"\bFreeze\b", code)` | one hit is a COMMENT explaining the shim; the other is the shim itself, `const Freeze = ({children}) => children;`, declared INSIDE Component precisely because the validator scans statically and needs a binding |

**Settled by the authority rather than by argument:** NamePlate registered with
`isValid: true`, zero errors. ChatCut's validator accepts AbsoluteFill-as-inner
and the Freeze shim. This is the recorded class *a pattern tight enough to
exclude a correct implementation is not a check either* — and it is the
cross-lane review case: the rules are in a checker over Builder 1's file, so the
finding is reported rather than edited in.

## Batch 1 — 2 of 5 complete

| component | asset | registered | placed | frame | registered_diff |
|---|---|:--:|---|---|---|
| NamePlate | `c2ccaeab62` | ✅ isValid | V3 200–319 | f260 · accent rule, "Madichi" in Anton, "STREET OF LAGOS" in accent on its scrim | read back, ONE difference (below) — not yet through the differ |
| MouseDrag | `53529b88d4` | ✅ isValid | V3 400–519 | f470 · yellow card "to check big words", arrow cursor on it at the settled centre | not yet read back |
| IMessageBubble | — | pending | | | |
| Reticle | — | pending | | | |
| EditorialQuote | — | pending | | | |

Both registrations echoed the same warning, which is the already-known second
rewrite class: `Auto-fixed: Injected missing ({item}) prop`.

**The one difference, and it is the injection.** NamePlate's registered code
read back identical to source except at a single site:

    source      const Freeze = ({ children }) => children;
    registered  const Freeze = ({ children, item }) => children;

That is the nested-`({item})` injection `registered_diff` classifies as
STRIPPED/injection and exits 0 on.

**Stated as a gap rather than claimed as a pass:** I read that difference off
`inspect_asset`'s output, I did not pipe it through `registered_diff`. This MCP
surface returns the code inside a tool result, not to a file, and the differ
takes a path. Eyeballing a diff is how a second difference goes unnoticed, so
proof 2 is **INSPECTED, not DIFFED**, for NamePlate and **ABSENT** for MouseDrag
until a small persist-and-diff step exists.

## One divergence the frame exposed

MouseDrag's card text rendered DARK on yellow. Its registered `cardTextColor`
default is `#FFFFFF`, and the body reads
`cardTextColor ?? (cardColor === "#F2C211" ? "#1C1C1C" : inkFor(cardColor))` —
so a default of `#FFFFFF` should have won and produced white-on-yellow. It did
not, which means the property arrived nullish despite a registered default.

The registry predicted exactly this: MouseDrag's recorded divergence is
`cardTextColor — unresolvable fallback`, and `#FFFFFF` is a PLACEHOLDER the
porter wrote because the real default could not be resolved. The frame is
right and the registered default is wrong. Worth noting against
[registered default is the value]: a placeholder default is not a default, and
here the component's own logic silently rescued it.
