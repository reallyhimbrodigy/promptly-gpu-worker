# POST PACKAGE CONTRACT (S-PACKAGE, 2026-07-25)

When a video completes, the user receives substance beyond the file: a small
package of posting-ready copy. This document is the contract for the 219
client build.

## Shape

One JSON object, delivered in two places (identical content):

```json
{
  "edit_rationale": "Tightened the intro and held on the reveal at 0:14 so the punchline lands.",
  "post_caption":   "Behind every launch is a spreadsheet nobody saw #startup #buildinpublic",
  "post_hook":      "Nobody talks about the spreadsheet."
}
```

## Field semantics + caps

| Field | Cap | Meaning |
|---|---|---|
| `edit_rationale` | 400 chars | 1-2 sentences, written TO the user: why the edit was cut this way. Honest on thin material (says so + suggests a longer talking-head). Plain language — never internal component/style names. |
| `post_caption` | 120 chars | Platform-ready posting caption: one line in the speaker's voice selling the content, plus 1-2 relevant hashtags. Paste-and-post. |
| `post_hook` | 60 chars | The scroll-stopping first line for the post — the video's sharpest claim or question. Plain text, no hashtags. |

Every field is OPTIONAL. An absent key (or an absent package) means "not
available" — render nothing, never an empty box. The package object is never
present-but-empty: if no field survived, the key is omitted entirely.

Caps are enforced at token-generation (Vertex `maxLength` in the response
schema) AND re-capped server-side at the persistence boundary — the client may
rely on the caps but must not rely on minimum lengths.

## Where it lives + availability timing

1. **`video_jobs.post_package` (jsonb)** — written by the worker mid-pipeline
   (talking-head: right after the edit plan resolves, ~29% progress, i.e.
   BEFORE the render finishes; caption-less routes: just before terminal). The
   write is daemon-threaded, fail-open, terminal-fenced (never relabels a
   failed/canceled/completed row), kill switch `PROMPTLY_PACKAGE_PERSIST=0`.
   PostgREST silently no-ops writes to an unknown column, so the worker side
   is safe to deploy before the migration; **the 219 client build owns the
   migration that adds the column** (mirror of `edit_rationale`):

   ```sql
   alter table video_jobs add column if not exists post_package jsonb;
   ```

2. **`result.post_package`** — carried in the worker's HTTP result payload and
   in the durable completed write on EVERY route (talking-head, minimal,
   hype). Available the moment `status = completed`. This is the durable copy:
   if the column write ever raced the terminal fence, the completed row's
   `result.post_package` is still authoritative.

Read order for the client: `result.post_package` on the completed row;
`video_jobs.post_package` for an early read while the job is still rendering
(talking-head jobs have it up around the 29%-progress mark).

## Copy-through-server note

The server (dispatch/API) needs NO changes: the worker owns `result` and the
package rides the existing result copy-through verbatim — no server-side
transformation, truncation, or re-encoding happens between the worker and the
DB row the client reads. `video_jobs.edit_rationale` (text column, already
live) continues to carry the rationale alone; `post_package.edit_rationale`
duplicates it by design so the package is one self-contained object.

## Per-route behavior

- **Talking-head**: all three fields authored by the planning model in the
  same call as the edit plan (measured cost ~57 output tokens ≈ 1.8-2.5s at
  observed rates — under the latency bar; the render is never delayed).
  Safe-edit / degraded plans may omit any or all fields.
- **Minimal** (no speech / no audio / too short): deterministic-honest values
  derived from the route reason — no model call.
- **Hype** (beat-synced): deterministic values derived from the measured beat
  grid (names the BPM when confidently measured) — no extra model call.
