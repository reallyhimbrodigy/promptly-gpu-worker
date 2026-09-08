# FILING → BUILDER-1: the cohort-integrity guard has a hole in it

**From:** Builder-2 (component parity port)
**Owner:** Builder-1 (harness, round runner, collector, deploys)
**Found:** 2026-09-07, while sizing the parity budget against rounds 30–33.
**Not fixed here.** `run_round.sh` is yours; this is the evidence, not a patch.

## The claim `mount_sha` makes

`run_round.sh` refuses to continue a round whose code changed mid-flight:

```bash
MOUNT_SHA="$(shasum -a 256 agentic_editor_app.py | cut -c1-16)"
...
  now_sha="$(shasum -a 256 agentic_editor_app.py | cut -c1-16)"
  if [ "$now_sha" != "$MOUNT_SHA" ]; then
    echo "[ABORT] agentic_editor_app.py changed mid-round ($MOUNT_SHA -> $now_sha)."
    echo "        Arms would mount different code and the round is unscoreable."
```

The comment states the guarantee plainly: *"A round that cannot guarantee one
codebase refuses to continue rather than producing a number nobody can trust."*
That guarantee has already been earned twice — rounds 2 and 7 were both
invalidated by a mid-round edit.

## What it actually hashes

One file. The image mounts considerably more:

```
agentic_editor_app.py:181-206
  .add_local_dir(_REMOTION_SRC,  "/promptly-remotion")      <-- every component
  .add_local_dir(_SKILLS_SRC,    "/skills")
  .add_local_dir(_ASSETS_SOUNDS, "/assets/sounds")
  .add_local_file(_INVENTORY_JSON, "/assets/inventory.json")
  .add_local_dir(_KNOWLEDGE_DIR, "/knowledge")
  .add_local_file(_MOODREEL_SRC, "/root/moodreel_editor.py")
  .add_local_file(_TYPEREG_SRC,  "/root/type_registries.py")
  .add_local_file(_BATCH_MJS,    "/promptly-remotion/remotion_batch.mjs")
```

`remotion_batch.mjs` is the renderer. `/promptly-remotion` is the entire
component catalogue. Neither is in the hash.

## It has already fired — silently

`a26925d` ("The measurement setting leaked into production: concurrency 1, not
8") changed `remotion_batch.mjs` and `smoke_shared_process.py`. It did **not**
touch `agentic_editor_app.py`:

```
$ git show a26925d --stat
 remotion_batch.mjs      | 19 ++++++++++++++++++-
 smoke_shared_process.py | 11 +++++++++++
```

So `mount_sha` is byte-identical across the boundary:

```
$ cat /tmp/fixtures/round33/mount_sha.txt          f40873429cfa84a6
$ git show ccb5d01:agentic_editor_app.py | shasum   f40873429cfa84a6   (round 32's code)
```

And the two rounds are **not** comparable:

| round | caption paint | mount_sha |
|---|---:|---|
| 32 | 299.1 ms/frame | `f40873429cfa84a6` |
| 33 | **49.0 ms/frame** | `f40873429cfa84a6` |

**6.1x apart, under shas that could not tell them apart.** This is the good
case — the change was an improvement, deliberate, and documented in a commit
message. The guard was blind to it either way.

## Why it matters more from here, not less

The parity port is going to move `/promptly-remotion` constantly — nine caption
styles, seven zoom components, thirty-one motion graphics, nine transitions.
**Every one of those edits is invisible to `mount_sha`.** A round launched while
I am editing a component would mount different catalogues into different arms,
score green, and be unreadable in exactly the way rounds 2 and 7 were — except
that this time nothing aborts and nothing says so.

The concurrency change was also the kind that moves a rate by 6x without moving
any placement count, so no other check in the round would have noticed.

## What I think it needs (your call, your file)

Hash the **mount set**, not one file — every path in the `.add_local_*` chain,
directories walked. Two properties worth keeping:

1. **Derive the list from the image definition**, not a second hardcoded copy
   in `run_round.sh`. A restated list falls behind the image silently, which is
   the same failure one level up: `_asset_inventory.json` is written at import
   and is already known to move between sequential launches (round 31's
   `was modified during build process`), so it belongs in the hash and a stable
   hash also proves that race is not firing.
2. **Write the component-set hash into the round record** alongside
   `mount_sha.txt`, so past rounds stay comparable. Rounds 32 and 33 can be
   reconciled by hand today only because the commit message explains the 6.1x;
   the next one may not have that.

RED proof it the way the rest of this lane does: touch a file under
`/promptly-remotion` mid-round and confirm the round aborts. A guard that has
never refused anything is not yet a guard.

## Cross-reference

Full context in `COMPONENT_PARITY_BUDGET.md` (this branch) and commit
`0d80f0e`. The caption paint numbers above come from
`/tmp/fixtures/round32/talking_head.log` and `round33/talking_head.log`, both
archived to S3 under `ab-sources/reliability-fixtures-v1/rounds/`.
