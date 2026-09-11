# Always-zero counters — the census, 2026-09-11

Zac: *"a counter that has never incremented is either a signal or a broken
wire, and the two look identical."* They look identical **from the ledger**, so
this file is the other place to look. Gated by `smoke_counters_can_grow.py`.

**Denominator: 28 ledgers, rounds 51-60**, all five fixtures. 113 countable
keys; **14 read zero in every single one.** Each is classified below. A
classification is an argument on the record — "GOOD ZERO" means the absence IS
the good news and a non-zero would be the defect; "NO WIRE" means nothing can
make it non-zero; "UNREACHED" means a real producer exists and has never fired,
which needs a reason.

| counter | class | why |
|---|---|---|
| `accounting_unbalanced` | GOOD ZERO | the ruled/built/skipped identity balancing is the whole point; non-zero is the defect |
| `axis_incoherent` | GOOD ZERO | purpose and zoom_arc never disagreed on a shared vocabulary. Non-zero would mean the reference join and the zoom lookup point at different moments |
| `cut_word_intrusions` | GOOD ZERO | no cut boundary landed inside a spoken word above the frame floor |
| `placement_effect_uncovered` | GOOD ZERO | every declared placement got an effect measurement. This one earned its keep: it was added because round 33 declared 16 placements and measured 1 |
| `plan_problems` | GOOD ZERO | every ruling was keyable to a source span, so a re-edit loses nothing |
| `overlay_skips` | GOOD ZERO | present in 1 ledger only, and zero there — no text ruling was dropped on that run |
| `caption_recent_in` | GOOD ZERO | no caption page reused a recent style. n=22 |
| `skill_gate_blocks` | **NO WIRE — FIXED 2026-09-11** | `led[K] = led.get(K, 0)`, a self-assignment. Nothing incremented it, the C7 gate it counted was retired from the prompt, and its report line printed **"0 render(s) blocked before first search (searched unprompted)" on all 28 runs** while `skill_searches` was EMPTY on all 28. The agent never searched once and the report said it searched without being told to. Counter deleted; the line now reads `skill_searches` and says NEVER SEARCHED |
| `skill_searches` | UNREACHED | a real producer exists (`led["skill_searches"].append`) and the agent has never called `search_skills` in 28 runs. This is the finding Zac already named — the skills have never fired — and it is a product fact, not a wire fault |
| `skill_hits` | UNREACHED | `+= len(hits)` is real and unreachable while `skill_searches` is empty. Downstream of the one above |
| `knowledge_reads` | UNREACHED | a real producer exists; the agent has never spent a `read_knowledge` turn. This is the same fact that cost three rounds of zero cards and put the overlay rule in a document nobody opens |
| `cmds` | UNREACHED | the shell is available and the agent has run no commands in 28 runs. Deliberate since the harness took over the mechanical work; recorded so its return would be visible |
| `component_verdicts` | UNREACHED | `component_verdict` is a tool the agent has never called. Beat rulings carry the decisions instead |
| `framing_ruled` | UNREACHED **on this lane** | written by Builder-1's framing work, which is not merged here — **zero sites in this checkout**. Not a wire fault; a merge state. Re-classify after the merge, and if it is still zero with the producer present, it is UNREACHED for real |

## What the gate can and cannot do

The mechanical half is certain and needs no traffic: `led[K] = led.get(K, ...)`
can never grow `K`, and that is the shape the phantom had. **It has to compare
the CONTAINER, not just the key** — the first version flagged
`led["reel_frames"] = rc.get("reel_frames")`, an ordinary read of the render
result into the ledger under the same name, and a detector that cannot tell
which object is being read calls every same-named field a phantom.

The other half cannot be mechanised. A counter with a real producer that has
never fired is genuinely ambiguous, and only a reason settles it. That is why
this file exists and why the gate requires every always-zero counter to appear
in it.
