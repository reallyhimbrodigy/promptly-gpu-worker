# APIFY CLIP-BRAIN — scope, measured against what already exists

Written 2026-08-31. Scoped **after** reading `REFERENCE_CORPUS_SPEC.md` (2026-08-24)
and querying the live Supabase, not before.

---

## 1. What is already built — observed, not assumed

Queried `ejxkzsfruykvgeouymfy` (Promptly) directly:

| table | rows | what it actually is |
|---|---|---|
| `reference_videos` | 10 | **owner-selected** clips, craft-analyzed |
| `reference_beats` | 153 | per-beat purpose / treatment / speaker_on_screen |
| `reference_pairs` | **absent** | the clip↔source half was never built |
| `trend_videos` / `trend_analyses` / `trend_profiles` | 103 / 19 / 3 | the **retired** 2026-08-23 pipeline's leftovers |

`reference_videos` columns as built: `source_file, sha256, duration_s, native_fps,
cuts, cuts_per_s, first_visual_change_s, hook_structure, onset_count,
cut_onset_aligned_frac, cut_onset_median_ms, in_instrument, selected_by,
analyzed_at, analyzer_version, raw`.

## 2. The finding that sets the scope

**There is no performance data in the corpus at all.** Not missing-and-recoverable
— absent. All 10 rows are `selected_by='owner'`. The spec's §4 columns
`platform, source_url, author, views, account_median_views, performance_multiple`
were **never created**, and `raw` carries none of them (`raw ? 'views'` = false on
all 10, likewise `source_url` and `author`).

So the existing corpus answers *"how was this moment treated"* and cannot answer
*"did it perform"* or *"what was it cut from"*.

**These 10 cannot be upgraded in place.** §3.2 is explicit and it is right: the
pairing metadata and the account baseline live on the post and are gone once the
clip is downloaded in isolation. The filenames are TikTok CDN ids
(`v09044g40000cm9oa7nog65s2crhkf00.mp4`), not post ids — author and URL are not
recoverable from them. **A performance-scored corpus requires a fresh scrape.**
The 10 stay as craft records; they are not the seed of this.

## 3. The one rule this build must not break

The prior generation was retired because **the aggregate was the defect** — 50
videos averaged into one `trend_profiles` row, recited as prose. The two rules
that replaced it govern here too:

1. **Records, never an aggregate.** Averaging at query time only. An average
   cannot be un-averaged.
2. **Retrieved, never recited.** Queried for the case at hand.

Zac's ask — *"derive the patterns: which hooks, which moments, which pacing
correlate with performance"* — is a **query over records**, not a written-down
summary. The correlation is computed at read time against the cohort that matches
the source in hand. If it is ever written back as prose into a prompt, this is the
retired pipeline with a new name.

## 4. Scope

### 4.1 Short-form scrape — performance is a MULTIPLIER
Per §2.1: score `views / median(views of that account's recent posts)`. A raw view
threshold selects for follower count, which is distribution, not craft. Requires
scraping the account's recent posts to get the denominator — **not just the clip**.

Capture at scrape time (non-negotiable, §3.2): `platform, post_url, author,
source_url (the long-form), views, likes, comments, posted_at`.

### 4.2 Long-form scrape — transcript + timestamps
The original the clip was cut from, with a full timestamped transcript.

### 4.3 The match is MECHANICAL
Align clip transcript against long-form transcript, best contiguous window.
**Never ask a model where a clip came from** — it will answer, and a confident
wrong offset poisons every downstream selection fact. `UNMATCHED` is a
first-class value.

### 4.4 Storage
`reference_pairs` per §3.2, plus the performance columns `reference_videos` lacks.
Both derived and rebuildable from pinned sources.

### 4.5 Frame extraction
`/watch` (installed, from `bradautomates/claude-video`) at the proxy's own
sampling.

## 5. BLOCKED — credential

No Apify token exists: not in env, not in the keychain, not among the five Modal
secrets (`promptly-elevenlabs`, `promptly-lang-flags`, `gemini-vertex`,
`promptly-cloudfront`, `promptly-secrets`). Per the working agreement, credentials
are a Zac ask.

**Needed:** an Apify API token, and a ruling on which accounts to scrape — §2
selects on craft (single speaker, 15–90s, carries a card and a cutaway), and the
account list is a taste call, not a measurement.

## 6. What would make this a failure, said now

- A corpus scraped on raw view count — that is the retired selection error.
- Patterns written back into the prompt as prose — that is the retired shape.
- A model-guessed clip↔source offset stored as if measured.
- A `performance_multiple` computed against a global median rather than the
  account's own.
