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

**That claim was wrong, and the differ is what found it.** Once the pair went
through `registered_diff` rather than my eye, NamePlate read **DIVERGED, 3
differences, 1 unexplained** — not "identical but for one site". The extra
difference: ChatCut stores the code WITHOUT a terminal newline (source `};\n`,
366 lines; registered `};`, 365). One byte, invisible at a glance, and it would
have made every component read DIVERGED forever.

`classify()` now drops exactly one trailing newline per side — not `trim()`,
which would swallow a truncated body. Both bodies now pass by measurement:

    NamePlate  STRIPPED  injection 1  unexplained 0  exit 0
    MouseDrag  STRIPPED  injection 1  unexplained 0  exit 0

The step is `port/proof2.sh <Name>`: persist from the session transcript
(`tool_result` only — the same transcript holds the registration CALLS, whose
`code` is the source we sent, and reading one would compare the source against
itself), materialise the contract source from the registry, run the differ.
Nothing is retyped: retyping the registered code with the source on screen
biases every keystroke toward the source, and the differ then reads IDENTICAL
because both files came from one original.

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


## The ten that stay PENDING PORT

Recorded in `library_73.json` `_pending_port`, each reason COPIED from
`chatcut_registry.json` `refused` rather than restated, with a leg asserting the
two still agree. The library keeps every entry; the platter derives from the
registry instead.

| component | reason | detail |
|---|---|---|
| AnnotationArrow | structured props ChatCut cannot express | `end: { x: number, start: { x: number` |
| ChatThread | structured props ChatCut cannot express | `header: ChatThreadHeader, messages: ChatMessage[]` |
| EndCard | structured props ChatCut cannot express | `palette: { bg: string` |
| InstagramComment | the blob reads an identifier ChatCut does not have | `cancelRender`, `setTimeout`, `Image` |
| Notification | structured props ChatCut cannot express | `notifications: NotificationItem[]` |
| PillMarquee | structured props ChatCut cannot express | `pills: string[]` |
| ProgressBar | structured props ChatCut cannot express | `formatValue: (current: number) => string` |
| SpeechBubble | not a single component | a DISPATCHER — it switches on `platform` to TweetBubble / InstagramComment / TikTokComment |
| TikTokComment | the blob reads an identifier ChatCut does not have | `cancelRender`, `setTimeout`, `Image` |
| TweetBubble | structured props ChatCut cannot express | `stats: { replies: number` |

**Seven of the ten share one reason, and that reason already has a proven
escape.** StickyNotes sat in this exact bucket — "structured props ChatCut
cannot express" — and is now registered, placed and frame-proven, because its
array became a FLATTENED SEMICOLON STRING (`text|colour|rotation; ...`) parsed
inside the component. `pills: string[]` and `notifications: NotificationItem[]`
are the same shape.

It is recorded as an available pattern with precedent, **not** as something this
lane will apply unasked. The StickyNotes split was ruled wrong at the root once
already — I ported it with a one-note default I chose and then read that default
back as evidence the component was singular — so the shape of each flattening is
a taste call, and seven of them is a body of taste calls. What is measured here
is only that the blocker is the same one that has been solved once.

The remaining three do not have that escape: two read identifiers the runtime
does not have (`cancelRender`, `setTimeout`, `Image`), and SpeechBubble is a
dispatcher whose three destinations are themselves on this list.