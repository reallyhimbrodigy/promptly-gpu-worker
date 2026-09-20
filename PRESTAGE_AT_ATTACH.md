# Prestage at attach — the entry, the key, and what Builder-2 calls

Written for Builder-2 (the content-studio side) and Zac (the ruling).
Design only. **Nothing here has run against ChatCut yet.**

**Status (Zac, 2026-09-20): APPROVED, sequenced AFTER the morning run.** The
attach-to-send gap came back **~10s mean / ~1s median**, which makes this a
much smaller prize than the 49s it removes — see *The saving* below. The
sequencing follows from the number.

---

## What moves, and why it is not an optimisation

Prestage is **24.2s** and it is **97–98% import** — ChatCut ingesting the
source. That is a production floor: the file genuinely has to get there. The
source watch is another **~25s** behind it. Neither can be made faster and
neither depends on the **brief**.

Both depend only on the **source**, and the source exists at **attach** time —
before the user presses send.

*(An earlier draft of this line said “minutes before”. The measured gap is
~1s median. The sentence is kept corrected rather than rewritten, because the
assumption in it is the one that made this look like a 49s saving.)*

So the work does not get faster. It gets moved into a gap that is already being
spent waiting for a human.

---

## The one line Builder-2 adds

At the point where an upload finishes and the asset row is written:

```ts
// fire-and-forget: an attach must never fail an upload
modal.lookup("promptly-gpu-worker", "attach")
     .spawn({ clip_url: signedUrl, source_sha: sha256OfUploadedBytes })
```

- `clip_url` — any URL the worker can `curl -fsSL`. A signed URL is fine.
- `source_sha` — **optional but wanted.** content-studio holds the bytes at
  upload, so it can hash them for free. If it is passed, `attach` compares it
  against the bytes the URL actually serves and **refuses on a mismatch** —
  a URL serving something other than what was uploaded is a real finding, and
  neither number is the one to prefer.
- `.spawn`, not `.remote` — the upload request must not wait, and the entry
  catches every exception rather than raising into the caller's path.

Nothing else changes on the server. No callback, no status to poll, no row to
write. The job that arrives later finds the record or does not.

### The gap — ANSWERED, and it was the deciding input

Asked of `upload_timing`; answered **~10s mean / ~1s median** (Zac). That is
the whole prize calculation and it is worked through in *The saving* below.
Kept here as the record that the number came from the events rather than from
this lane's estimate — the estimate would have been wrong by an order of
magnitude, because *minutes before the user presses send* (above) is what I
assumed and it is a second.

---

## The key

`prestage_key(source_sha, registry_digest, account, w, h, fps, version)`
→ sha256 of the sorted parts, first 32 hex.

**It is not the source hash.** It is everything a claimed project would be
*wrong* about if it differed, and each part earns its place by naming a way a
hit could be worse than a miss:

| part | what a collision on it costs |
|---|---|
| `source_sha` | different bytes are a different clip. **The URL cannot serve as the key** — a signed URL differs on every attach for the same object, so keying on it would miss every time and look like a cache that does not work. |
| `registry_digest` | a prestaged project **carries its component registrations**. A record made before a component changed holds the old code under the same name; the agent places an id that renders last week's component. Invisible: the placement succeeds, the frame is wrong, nothing mentions the registry. |
| `account` | a project belongs to a ChatCut user. Another account's project id is a 404 at the first `edit_item`, twenty minutes in. |
| `w`, `h`, `fps` | the canvas is fixed at `create_project` and cannot be changed afterwards. |
| `version` | one edit invalidates every stored record the day a record's *shape* changes. |

**A missing part is REFUSED, never hashed.** `str(None)` is a perfectly good
hash input and would give every run with an unread registry one shared key.

### The account part is the weak one, and it is named as weak

It is the digest of `CHATCUT_CLIENT_ID` — stable across the token rotation that
happens mid-run. It does **not** distinguish two ChatCut *users* sharing one
client id; they would be offered each other's projects. The replacement is a
user id read from a ChatCut envelope, and this lane has not yet **observed**
which field carries it, so keying on it now would be the shape-guessing that
has cost ten turns before. One account runs this lane today. The day a second
does, this is the line that has to change.

---

## The unit is ONE ATTACHED FILE, not one source

This is the decision that shapes everything else.

A prestaged project is **stateful and single-use**. The moment a job edits it,
it holds that job's timeline. The dispatch path already refuses an inherited
timeline by name — `CONTAMINATED ARM` — and a cache that handed the same
project to a second job would be manufacturing that case deliberately.

So **a hit CLAIMS the record and REMOVES it.** A second job on identical bytes
misses and prestages cold. One attach, one project, one edit.

The claim is a `Dict.pop` — one server-side round trip, therefore atomic as far
as a client can tell. *As far as a client can tell* is an assumption about
somebody else's implementation, so it is **instrumented rather than trusted**:
every claim is appended to `chatcut-attach-claims`, a second claim on one key
sets `double_claim` on the run record, and the verify below is the second line
of defence that does not depend on the assumption at all.

---

## Three states, not two

Zac named `prestage_cold`. The third is the one that would otherwise hide
inside the other two.

| `prestage_source` | means | acted on by |
|---|---|---|
| `warm` | claimed and verified | nothing |
| `cold` | nobody attached this source | product — is the hook wired? are there repeats? |
| `stale` | somebody attached it **and it rotted** | engineering — the feature is broken |
| `reused` | a preemption retry reusing its own stage | neither |

A stale rate folded into the cold one is a broken feature wearing a workload's
clothes. Printed at the decision (`PRESTAGE SOURCE :`) and on every run record —
a counter that reaches the ledger and no output answers nothing, and this lane
has run a whole round to learn whether a gate fired and could not.

---

## A hit is READ, never trusted

The whole point of an early prestage is that **time passes**, and time is
exactly what invalidates it. `attach_verify` returns MEASURED / STALE / FAILED
after four reads:

1. **fields** — every id the stage needs is present.
2. **sheets** — each watch sheet is **opened off the volume and its size
   compared** against what was stored. A record listing files the reader cannot
   open is precisely what an uncommitted volume write leaves behind, and it is
   indistinguishable from a good record in the Dict.
3. **density** — sheets watched at 2fps do not serve a job asking for 1fps.
   Not a key part: the *project* is correct either way, only the pictures are
   wrong, and folding it into the key would miss the project too.
4. **timeline** — read back through ChatCut: the base clip is there and
   **nothing else** is. An unreadable read-back is STALE and says so —
   *an unreadable timeline is not an empty one*.

**No reader is FAILED, not a pass.** Whether the project still exists is
UNKNOWN, and UNKNOWN rendered as fine is the family this repo has the most
rules about.

**STALE is not an error.** It falls through to the cold path — the path that
worked yesterday. The only thing a stale hit costs is the lookup.

---

## What cannot move, and is therefore refused rather than dropped

- **Titles** are registered per *plan*, which comes from the brief, which did
  not exist at attach. A job passing `prestage_titles` goes **COLD** and says
  so. A warm hit that silently dropped them would be the half-ruling shape:
  the job asked for fifteen graphics, got a project with none, and nothing
  anywhere said the request was discarded.
- **The contact sheet** is brief-independent but costs ~2s off a file dispatch
  downloads anyway. Moving it trades a disk read for a network hop.

## What moves without being moved

**Transcription.** The import is what starts ChatCut transcribing, so an early
import means the words are ready when `source_beats` asks instead of waiting on
them. That is a **consequence to be measured on the first warm run**, not a
saving claimed here.

---

## The saving

```
saved = min(attach-to-send gap, cold setup cost)
```

**Bounded by the gap, not by the cost of the work.** A user who attaches and
sends three seconds later has given prestage three seconds to run; the other
46 are still on the job's clock. Quoting the full setup cost as the saving is
the arithmetic that turns a real 3s into a claimed 49s, per job, across the
whole population.

`attach_saving()` returns **ABSENT** rather than a number when either input is
missing. Both come from somewhere else — the gap from your `upload_timing`
events, the cold setup from this harness's own stage marks — and neither is
derivable from the other.

Today: `cold setup ≈ 24.2s prestage + ~25s source watch ≈ 49s`, measured on
this lane.

### The gap arrived, and it is small (Zac, 2026-09-20)

**~10s mean / ~1s median.**

| | gap | `min(gap, 49)` | against a 120s budget |
|---|---|---|---|
| median job | ~1s | **~1s** | 0.8% |
| mean job | ~10s | **< 10s** | < 8% |

The mean row is an upper bound and the inequality is the point:
`E[min(gap, 49)] ≤ min(E[gap], 49)`, and it is **strictly** less here, because
a mean ten times the median means the distribution is tail-dominated and the
tail is exactly what gets clipped at 49.

**So this saves almost nothing for most jobs and up to 49s for a few.** Most
users attach and send in about a second; prestage has had a second to run.

That is the honest read and it argues for Zac's sequencing rather than against
it: work that helps every job comes first. It also means the feature must never
be reported as a mean — a blended saving over a population where the median is
1s and the tail is 49s is precisely the shape Rule 5 forbids. **Cut it by gap
decile, or do not quote it.**

What the number does *not* devalue: the design's second effect. The import is
what starts ChatCut transcribing, and that wait is not bounded by the gap the
same way — it continues in ChatCut's own time after the job starts. Whether
that is worth anything is **still ABSENT** and is measured on the first warm
run, not estimated here.

---

## Hazards recorded rather than solved

- **The volume must be reloaded and committed.** A Modal Volume shows what it
  held at container start; `attach` commits after that. A missing `reload()`
  reads as sheets that were never written — the same file, absent, no error.
  Both calls are asserted by a leg, and both mounts are asserted to use the
  same constant rather than the literal twice.
- **Orphans.** A prestaged project the user never sends is a project with a
  storage bill. Bounded at `ATTACH_TTL_S = 24h` — a **policy choice, not a
  measurement**, and labelled as one in the code. There is no sweeper yet;
  expired records are claimed and discarded, the ChatCut project is not
  deleted. That is the next thing this design owes.
- **A double attach** on one key answers `PRESENT` and does not create a second
  project.

---

## Checks

`smoke_the_machine_holds_off_the_happy_path.py` — 14 legs, all RED-proven in
`red_proof_the_machine_holds.py`. The claim-removes leg is the one that matters:
it is the whole single-use design in one assertion.

Nine new readers are in `STATEFUL_READERS` and each is driven blind with the
input missing the thing it reads.

The census-shape check itself was **wrong and is fixed here**: it held a literal
`("ABSENT", "UNREADABLE")` and went red on four *correct* readers, because a key
REFUSES, a claim MISSES and a lookup goes COLD. It now reads the expected word
from the census entry, so the two halves are one fact and a new state word
cannot drift from a list that no longer exists.
