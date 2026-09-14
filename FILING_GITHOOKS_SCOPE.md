# FILING — `.githooks`: one fix covering drift, scope, and the merge gap

**Owner: whoever holds the main checkout** (`/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker`).
Filed by Builder-1 (lane/agentic-editor). **Not applied — outside this lane's region.**

Filed as a document rather than a message because the session that owned that
checkout has rotated out twice while this was being investigated. A finding that
only exists in a peer's inbox dies with the peer.

---

## 1. The live hook has drifted from its tracked copy, and the drift is the part that works

```
.githooks/commit-msg and .githooks/pre-commit ARE tracked on zero-reject-routing
tracked pre-commit   87 lines   vs   live 99 lines        DIFFERENT
tracked commit-msg                                        SAME
`round_in_flight_guard` in the TRACKED pre-commit:        0 occurrences
```

The round-in-flight guard — written after rounds 61, 62 and 64 each died to a
commit landing on a mounted path mid-round — **exists only in one working tree,
in no commit anywhere.** A fresh clone gets a hook that looks legitimate and is
twelve lines short of the protection.

I first reported this as "untracked". Builder-2 corrected it: tracked **and
drifted**, which is worse. Absence is visible; drift reports PASS.

## 2. The commit-msg glob cannot see most of what the repo now ships

`.githooks/commit-msg`, line 50:

```python
for f in (glob.glob("*.py") + glob.glob("*.sh") + glob.glob("fixtures/*.sh")
```

It validates *"the message names symbols this commit contains"* against `.py`
and `.sh` only. It blocked a commit today for naming a symbol that **was** in
the diff, in a `.jsx` file it cannot read. That refusal is correct conservative
behaviour and the message was reworded rather than bypassed.

The direction that actually worries me is the other one: **a claim about
`.mjs`/`.jsx` code can never be checked, so the gate is silently inapplicable to
a growing share of commits while still reporting PASS.** This lane now ships a
motion-graphic porter (`port_mg.mjs`), a frame-differ (`framediff_mg.mjs`) and
29 ported components, and the ChatCut work adds more.

## 3. `git merge` runs neither hook

Re-derived in a throwaway repo, exit codes read bare rather than through a pipe:

| operation | hooks present | result |
|---|---|---|
| plain commit | pre-commit | **FIRED**, blocked |
| true merge | pre-commit | did **not** fire, merge commit created |
| fast-forward | pre-commit | did **not** fire, nothing to fire on |
| true merge | pre-merge-commit | **FIRED**, merge blocked |

The merge of `lane/duration-producer` went through with **no gate at all** — not
because the guard declined, because it was never invoked. It was fine only
because no round was in flight.

## The fix, as one change

1. Commit the live `pre-commit` back over its tracked copy, so the in-flight
   guard exists somewhere other than one machine.
2. Widen the `commit-msg` glob to the file types the repo actually ships.
3. Add `.githooks/pre-merge-commit` calling the same guard.

**Caveat worth keeping:** a `pre-merge-commit` hook cannot cover a fast-forward,
which creates no commit. The guard still has to be run by hand before a merge;
the hook is a backstop, not the plan. Builder-2 reached this independently.
