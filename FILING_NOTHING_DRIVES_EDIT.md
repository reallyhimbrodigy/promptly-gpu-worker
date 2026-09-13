# A NameError reached a round because nothing in this lane calls `edit()`

Filed by BUILDER-1, 2026-09-12, after round 66 collected 5/5 `ok=False`.

## What happened

`_stalls = beat_stalls(words, _beats)` was inserted by a string anchor that
matched **inside the `else:` branch** of the cutaway conditional. Syntactically
valid there, so the file parsed. The BEATS block 140 lines below reads `_stalls`
unconditionally. Every fixture taking the `if` branch reached:

    NameError: cannot access free variable '_stalls'
    where it is not associated with a value in enclosing scope

Five arms, no signature, zero placements, ~$1, and a round that answered nothing
about cutaway — which is what it was launched for.

## Why every existing check passed

| check | why it was blind |
|---|---|
| pyflakes | sees an assignment and a use in one function; does not reason about reachability |
| 108 smokes | **none of them calls `edit()`** |
| import-time asserts | execute no function body |
| adversarial gate, tree-parses | read source, and the source is valid |
| the pre-commit hook | runs all of the above |

This is a new member of *a failure that renders identically to a success*: the
anchor did not go stale, and the occurrence guard counted exactly one match. It
matched in the **wrong branch**. Counting matches cannot tell you which control
path one lands in.

## I tried to check it statically and could not, in four attempts

| version | rule | findings | verdict |
|---|---|---:|---|
| v1 | bound inside any branch, read outside | 79 | almost all correct code (`try: r = run() except: return`) |
| v2 | …whose sibling path falls through | 34 | still wrong — `try: g = x except: g = -6.0` binds on both |
| v3 | bound on every path (naive prefix walk) | 1326 | worse; top-level-only prefix misses loop and nested bindings |
| v4 | one-armed if/else binding read after | many | still fires on correct code |

A sound version needs real reachability analysis. **A check that fires on
correct code is one somebody switches off within a day** — this repo says so
twice — so it is not shipped. Recording the four attempts rather than the
conclusion alone, because the next person will reach for the same idea.

## The actual gap, which is worth more than the check

**Nothing in this lane exercises `edit()`.** 108 smokes, and the largest
function in the file — the one that builds every prompt, runs the tool loop and
holds ~3,000 lines — is driven only by a paid Modal round. Every defect on a
path a round happens not to take is invisible until it costs an arm.

That is the thing to fix, and it is not a smoke: it is a local harness that can
call `edit()` against stubs. Filed rather than built, because it is a day of
work and the merge and the cutaway question come first.

Until then the honest statement is: **this lane's static checks cannot see a
runtime error in `edit()`, and a round is the first thing that will.**
