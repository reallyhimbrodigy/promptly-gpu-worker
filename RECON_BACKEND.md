# RECON_BACKEND.md — Full verified map of the Promptly Modal backend

**Produced:** 2026-08-09, read-only. **Scope:** the `promptly-gpu-worker` Modal worker (`handler.py` ~38K lines, `modal_app.py`, `src/remotion/`, `validate_deploy.py`, `deploy.sh`, cert/harness scripts) and the parts of the sibling `content-studio` Node server that dispatch jobs and persist results.

**Method:** six read-only research agents, one per section-cluster, cross-checked against each other by the assembler. **Zero Modal spend** (only `modal app list`/`history`/`logs` were used — no `modal run`, no renders, no cert executions, no deploys, no edits to any source file). All DB reads were read-only SELECTs against `video_jobs`. No source file was modified in producing this document.

**Evidence tags (every claim carries exactly one):**
- `[MEASURED]` — a query or log was run; the number is shown with n and window.
- `[CODE]` — read in source; cited `file:line`.
- `[INFERRED]` — reasoned; the reasoning is stated.
- `[UNKNOWN]` — could not be determined; why is stated. Several `[UNKNOWN]`s exist specifically because verifying them required Modal spend, which was barred.

**The one thing to internalize before reading anything else:** on this codebase, **source code defaults do not describe production.** The running image is configured by the `promptly-lang-flags` Modal Secret, and the only written record of the intended live values is the CANON dict at `validate_deploy.py:7149` `[CODE]`. Multiple `handler.py` defaults (language coverage, thinking budget, route languages) are *overridden live* and their in-code defaults are misleading. Trust the CANON dict and the running image; distrust code defaults for any *state* question.

---

## CRITICAL FINDINGS (actively broken or actively dangerous in production)

**C-1 — The live image is off the documented deploy branch, and 36 commits of work exist only on one laptop.** `[MEASURED]` The running image is **v521 = `1601ae0`**, which is the HEAD of `origin/agent/smoothness` — **not** an ancestor of `zero-reject-routing` (the branch CLAUDE.md Rule 0 says is authoritative) and **not** on `main` (main is 62/93 commits diverged). The two lanes forked at `5f19901`; smoothness carries the live commit plus 9 others the documented branch never received — the exact multi-worktree race `predeploy_no_regress.py` exists to catch. `.last_deployed_commit` records `a324b7d` (v510) — **stale by 11 deploys**. Separately, local `zero-reject-routing` is **36 commits ahead of its remote** and `main` 31 ahead — those commits live only on the local machine. *Mitigation that exists:* the live commit itself is pushed (it is `origin/agent/smoothness`), so the running image is reproducible; the unpushed 36 are other work. **Nobody can currently answer "what is deployed" from `main` or from the documented branch.** (Section A.)

**C-2 — Production telemetry that the gate certifies as present is null on real traffic.** `[MEASURED]` `lang_bundle` (the 3-field language bundle) is null on **218/218** recent standard completions; `gemini_tokens`/`gemini_call` null/0 on **129/129**; `cpu_by_stage` and `prewarm_hit` absent — *despite* green `@check`s asserting each persists "on EVERY job." The data needed to diagnose language, token-cost, and prewarm questions is being silently dropped, and the gate reports success. This is the project's signature failure mode (silent no-op telemetry) reproduced live, with false green certification on top. (Sections D, S.)

**C-3 — The worker's own durable status-write layer is dark AND mis-targeted at a non-existent table.** `[CODE]` `handler.py:30726` writes durable job status to table **`jobs`**, but the real table is **`video_jobs`**; and the whole layer is gated off (`JOB_STATUS_WRITES_ENABLED` off). So the worker's independent completion path is both disabled and pointed at the wrong table — if the callback path (which is the only live one) misses, there is no durable backstop. Ties directly to C-6. (Sections D, N.)

**C-4 — No golden-output harness exists; an editorial regression passes CI green.** `[CODE]` The 353-check deploy gate is ~45% source-grep string-presence asserts, not behavioral; the byte-identity/determinism certs lock only "same plan → same bytes," which cannot detect a *worse plan*. 70 of 76 `cert_*.py` are Modal apps that cost spend and never auto-run; only 10 `test_*.py` run in-gate (53 others are never invoked by any runner). A change that makes the editorial model choose worse edits ships green. (Section Q.)

**C-5 — A per-position enum silently makes a class of output impossible.** `[CODE]`/`[MEASURED]` `ZOOM_ARC_HOMES` restricts the payoff-position zoom to `LetterboxPush`/`SmoothPush` only, so a *punchy* payoff zoom is structurally unreachable — **0/253** confirmed. This is the exact "silently-impossible-output" class the brief warned about; it went undiscovered for months and is still live. (Section F.)

**C-6 — Completion accounting is distorted by a mis-descriptive field, and a resolved outage still poisons 30-day numbers.** `[MEASURED]` `started_at` is stamped at dispatch-*attempt*, not worker-run, so "started ⇒ ran" overcounts (UPLOAD_NEVER_STARTED rows carry `started_at≈created_at+0.2s`). A resolved 25-hour dispatch outage (2026-07-30→31, HTTP 404, **1121 failed jobs / 547 users**) writes `error_message="Modal error: 404"` with **`result=NULL` and no error_code**, so every by-code query silently drops it and 30-day raw completion reads 61.8% instead of the ex-outage 75.3%. Clean 7-day: 83.1% completed/all; ~95–96% excluding client-upload-never-arrived + user-aborts; **13.0% of users got nothing** (lead the user count per Rule 7; 16.9% per-job). (Section N.)

**C-7 — The highest-traffic language has the worst known, unconfirmed-fixed defect.** `[MEASURED]` Hindi/Devanagari = **62%** of transcripted jobs (n=219 of last 500); English 29%, Spanish 6%, Arabic 2%. Hindi mid-word cut rate is **37.1% (5× English)**, "fixed" without confirmation; Spanish edge-loss (0.41 keep-ratio) has no gate and is deferred. Live multilingual works *only* because the secret sets `SCRIPT_DENYLIST=""`/`EDIT_IN_LANGUAGE=1`/`LANG_ROUTING=1`; the code defaults (`_SCRIPT_COVERAGE={"Latin"}`) would disable it. (Section R.)

**C-8 — Flag-drift blind spot.** `[CODE]`/`[UNKNOWN]` The shell-baked-flag revert hazard is closed (all operational flags now live in the `promptly-lang-flags` Secret), but **4 CANON keys are not value-pinned** (ROUTE_LANGS, MOTION_BLUR, MIN_OUTPUT_RATIO, CAPTION_ALIGN) — drift in those is uncaught — and the **actual live secret values are `[UNKNOWN]`** because reading them requires a Modal run, which was barred. The gate only catches drift at the *next* deploy, not continuously. (Section B.)

**C-9 — Cost law is met only on the orchestrator-only median; premium blows it 5×.** `[MEASURED]`/`[INFERRED]` The orchestrator (cpu=16/12GiB) is held for the whole wall *and* `render_burst` (cpu=32/64GiB) is paid during render — a confirmed double-pay (`modal_app.py:2511`). Blended cost/job ≈ $0.115 orchestrator-only → **$0.257 with burst**; **premium mean $0.481** (2–5× the $0.10 law). The real sink is non-job idle/warmup, code-stated at **~$87/day**. (Section P.)

**C-10 — The product-core surgical/re-edit path is essentially untrafficked and cannot express the target vocabulary.** `[MEASURED]`/`[CODE]` Re-edit is **7 of 6,338 jobs (0.11%)**; `tweak` mode can't add transitions, re-cut, shift sub-word timings, or edit caption text; and on re-edit the new job inherits the *parent's* `vibe_input` while the actual change lives only in `change_request` (server.js:4361) — a latent silent instruction-drop. (Section K.)

*Lower-severity-but-notable:* generated_scenes (0/2074 premium) and color_effect (removed) are dead families; MG `BarRace`/`PillMarquee` are discrimination-starved and likely unreachable (their FIGHTS lines route their trigger to a sibling that always wins); the ~900s latency p99 is a callback-fallback artifact, not compute (Section O); 424 bare `except: pass` + 290 fail-open markers form the silent-failure surface (Section N).

---

## SUMMARY (≤20 lines)

1. **What it is:** a single-source short-form video editor. One user video → Deepgram transcript → a 15-task parallel perception pool → one streaming Gemini "post-cuts" editorial call that emits a structured plan → a two-stage render (Remotion alpha overlays + FFmpeg cut/composite/encode) → one delivered 1080×1920@30 MP4. `[CODE]`
2. **Cuts are mechanical (Deepgram+VAD), not model-chosen;** the model chooses *enhancements* (zoom/emphasis/MG/transitions/captions/b-roll) over a fixed cut skeleton. `[CODE]`
3. **Two product tiers on one codebase:** the full editorial toolbox runs only on the premium route; **47% of traffic runs a stripped "lean" plan** (clips+zoom+MG+transitions, no emphasis/sfx/captions/broll). `[MEASURED]`
4. **The render layer is already more capable than the model is allowed to ask for:** clip-addressed, multi-source stitch, generated stills, pre-timed text — all built, all dark except Pexels b-roll. `[CODE]`/`[MEASURED]`
5. **Generation is inert:** Nano-Banana image-gen + QA judge exist but fired 2/6,338; Veo inert; no TTS/avatars/matting. `[MEASURED]`
6. **Deploy/branch truth is broken** (C-1): live is on `agent/smoothness`, not the documented branch; 36 commits unpushed.
7. **Live behavior ≠ code defaults** — the CANON secret dict + running image are the only truth.
8. **Latency:** 7d e2e p50 131.5s (1.46× the 90s law), tail is heavy premium renders + a ~900s callback artifact; dispatch is negligible. `[MEASURED]`
9. **Biggest unflipped latency levers:** proxy 18→2fps (9× token cut, **validation caught that the flip value must be `MEDIA_RESOLUTION_LOW` not `LOW` or every job 400s to safe edit**), HLS_COPY (72s→1s, on critical path), RENDER_FANOUT (~19%, held for cost). `[CODE]`/`[MEASURED]`
10. **The metric the rebuild will be judged on — request fulfillment — is computed nowhere,** but 6,210 vibe↔result pairs exist to build a judge from. `[MEASURED]`

---

## CROSS-CHECKS & RECONCILIATIONS (where the six agents disagreed; which I trust and why)

- **Thinking budget:** code default is `24576` `[CODE, Section E]`, but the live secret pins `POST_THINKING_BUDGET=2048` `[CODE CANON, Section B]` and Section P confirms it was flipped `24576→2048` (−29.5s). **Live = 2048; 24576 is a misleading code default.** (Instance of the C-1/state-truth pattern.)
- **Result-key strip allowlist location:** Section S found it is **worker-side** at `handler.py:38921` `[CODE]`, contradicting the code comments (and this document's own earlier working assumption) that place it in content-studio. **Trust Section S's `file:line`.** Survival still requires nesting under `stage_timings`; the correction is *where* the allowlist lives, not *that* it exists.
- **Pexels b-roll usage counts differ by cohort, not in kind:** Section G measured 208 clips/149 videos (n=3,949, 06-25→08-10); Section J measured 270 clips/180 jobs (its window); Section L cites 180 jobs. All agree it is the *only* wired generator and the *only* non-user footage on real traffic — the spread is window/definition, not conflict. Report both windows.
- **Burst CPU:** comments in `modal_app.py` say "cpu=48" in places but the real decorator is `cpu=32` `[CODE, Sections A & I]` — stale prose, live value is 32.
- **Render split** (historically mis-audited both directions) is now pinned precisely in Section I: Remotion = two ProRes-4444 alpha intermediates only; everything else (base cuts, concat, composite, denoise, SFX-audio mux, HLS, the one lossy encode) is FFmpeg.

---
# Recon A — Deploy & Branch Truth, Flags & Configuration, Unflipped Inventory

Repo: `/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker`
Read-only recon. Tags: [MEASURED] ran a command/query, [CODE] read source (file:line), [INFERRED] reasoned, [UNKNOWN] could not determine.
NO Modal spend incurred (only `modal app history` — read-only).

---

## HEADLINE FINDINGS (read first)

1. **The live image was NOT built from the documented deploy branch.** [MEASURED]
   The currently-serving deploy is **v521 = commit `1601ae0`** (full
   `1601ae0b76fc6b2233bfd4f392d399ce39b806e8`), and `1601ae0` is the HEAD of
   **`origin/agent/smoothness`** — it is **NOT an ancestor of `zero-reject-routing`**
   (the branch CLAUDE.md Rule 0 names as the deploy branch). The two deploy lanes
   diverged at merge-base `5f19901` (2026-08-04 16:55); `agent/smoothness` then took
   10 commits (including the live one) that `zero-reject-routing` never received,
   while `zero-reject-routing` took its own 2 commits. This is the exact
   multi-worktree divergence `predeploy_no_regress.py` was written to catch.

2. **`.last_deployed_commit` is stale.** [MEASURED] It records `a324b7d` = **v510**
   (2026-08-04 15:25), but 11 further deploys shipped after it (v511–v521). The file
   is written into whichever checkout runs `deploy.sh` (deploy.sh:56), so this
   checkout (`zero-reject-routing`) only recorded ITS last deploy; v511–v521 came
   from other worktrees. Do not trust this file as "what is live."

3. **36 commits on local `zero-reject-routing` are unpushed.** [MEASURED]
   `origin/zero-reject-routing..zero-reject-routing = 36`. The current checkout HEAD
   (`1032ec2`) exists only locally. (The LIVE commit `1601ae0` itself IS pushed — it
   equals `origin/agent/smoothness` — so the live image is at least recoverable from
   the remote.)

4. **Dirty flag ignores untracked files.** [CODE] `_BUILD_DIRTY` (modal_app.py:30)
   runs `git status --porcelain --untracked-files=no` → it flips to "1" only on
   MODIFIED TRACKED code, never on untracked cert/harness scripts. Current tree =
   clean by that measure (0 modified tracked; 13 untracked).

5. **The DARK/unflipped flag machinery IS present in the live image.** [MEASURED]
   Every dark flag checked (HLS_COPY, PROGRESSIVE, LEAN_SCHEMA, MEDIA_RESOLUTION,
   PLAN_ONLY, EDIT_POLICY_ENABLED, MULTI_INPUT_ENABLED, ASK_BACK_ENABLED,
   MOTION_TOKENS, DENSITY, …) is grep-present in `git show 1601ae0:handler.py`, and
   the flag-name symbol set is byte-for-byte identical between live `1601ae0` and the
   current checkout — so the "canonical-but-not-in-live-lane" class does NOT apply at
   the flag-inventory level (the divergence between the two lanes is behavioral code,
   not missing flags).

---

# SECTION A — Deploy & Branch Truth

## A1. Currently deployed image: version/tag, timestamp, git SHA

[MEASURED] `modal app history promptly-gpu-worker` (top row = current):

| Field | Value |
|---|---|
| Version | **v521** |
| Time deployed | **2026-08-04 19:39 PDT** |
| Deployed by | reallyhimbrodigy |
| Client | 1.2.6 |
| Commit (short) | **1601ae0** (no `*` → clean tree at deploy) |
| Commit (full) | `1601ae0b76fc6b2233bfd4f392d399ce39b806e8` |
| Commit subject | "ROOT-CAUSED: the TAIL-PAD is what lands mid-word — the snap was fixing the wrong place, and the live diagnostic said so" |
| Commit author date | 2026-08-04 19:37:37 -0700 |

[MEASURED] `.last_deployed_commit` file = `a324b7d1d0c2d7a8a1600bfbd1ae50c72236e63f`
= **v510** (2026-08-04 15:25 PDT), subject "SPANISH: the coverage gate is not
broken…". **This is STALE by 11 deploys** — it is NOT the live commit. Reason
(deploy.sh:53-57): the file is written into the deploying checkout only, so this
worktree recorded its own last deploy (a324b7d) and is structurally blind to the
v511–v521 deploys made from other worktrees. Authoritative live SHA = Modal app
history = `1601ae0`.

Note: the modal-history `*` suffix marks a dirty tree at deploy (`_BUILD_DIRTY=1`);
v521 `1601ae0` has NO `*` → deployed from a clean tracked tree.

## A2. Does that SHA exist on a tracked branch / worktree?

[MEASURED] `git branch -a --contains 1601ae0`:
- Local branch **`agent/smoothness`** (contains it; local head `d9543d6` is 2 commits
  ahead of `1601ae0`).
- Remote **`origin/agent/smoothness`** — head is `1601ae0` EXACTLY (i.e. the live
  commit IS the pushed head of that remote branch).

[MEASURED] `git merge-base --is-ancestor 1601ae0 zero-reject-routing` → **NOT an
ancestor**; same for `origin/zero-reject-routing`. So the live commit is on the
`agent/smoothness` line, **not** on the deploy branch Rule 0 documents.

Worktree hosting `agent/smoothness`: `/Users/zaclibman/promptly-gpu-worker/promptly-smoothness`
(worktree head `d9543d6`). [MEASURED]

## A3. Was the deploy tree dirty? Mechanism, and what it counts

[CODE] modal_app.py:29-31:
```
_BUILD_SHA   = _git("rev-parse", "HEAD") or "unknown"
_BUILD_DIRTY = "1" if _git("status", "--porcelain", "--untracked-files=no") else "0"
_BUILD_TS    = str(int(time.time()))
```
[CODE] The `--untracked-files=no` flag means **_BUILD_DIRTY counts ONLY MODIFIED
TRACKED files; untracked files are ignored.** modal_app.py:14-16 states this is
deliberate: "the image mounts only specific add_local_file/dir paths … and must not
flag a reproducible deploy as dirty (they made v418 read b5f9f2b*)". These are baked
into the image ENV at modal_app.py:461-465 (`PROMPTLY_BUILD_DIRTY: _BUILD_DIRTY`) and
logged as line 1 of every job (handler.py:32980-32983, 35222-35225).

[MEASURED] For the LIVE deploy: v521 `1601ae0` had **no `*`** in modal history →
`_BUILD_DIRTY=0` → deployed from a clean tracked tree.
[MEASURED] For the CURRENT checkout right now: `git status --porcelain
--untracked-files=no` = empty → `_BUILD_DIRTY` would be **0** (clean), despite 13
untracked files present.

## A4. What branch is prod deployed from? Is it main? How far does main diverge?

[CODE] deploy.sh:31-40 + CLAUDE.md Rule 0: the worker deploys `modal deploy
modal_app.py` against the **working tree of whatever branch is checked out** —
historically `zero-reject-routing`, **NOT `main`**. deploy.sh:35-40 prints the
deploying branch and warns if `main` is behind. content-studio is separate (deploys
from `main` via Render).

[MEASURED, and this is a finding] The live image v521/`1601ae0` was actually deployed
from the **`agent/smoothness`** line, not `zero-reject-routing` and not `main`. So on
2026-08-04 there were (at least) two live deploy lanes racing (`agent/smoothness`,
`agent/errors`, `zero-reject-routing`), which is precisely the hazard
predeploy_no_regress.py documents (v511 errors → v512 smoothness reverted it 2 min
later).

Divergence counts [MEASURED] (`git rev-list --left-right --count`):
- `main` (f7e80b1) vs local `zero-reject-routing` (1032ec2): **0 / 62** → main is 62
  commits BEHIND local zero-reject-routing (main is an ancestor).
- `origin/main` (caa9fee) vs local `zero-reject-routing`: **0 / 93** → origin/main is
  93 behind.
- `main` is NOT an ancestor of the live commit either: `main`=f7e80b1 (2026-08-03
  22:42, = v491), the live `1601ae0` is a day newer. So **neither `main` nor
  `origin/main` contains the live code.** main is not "dead 447 behind" as in the old
  Rule-0 incident, but it is materially behind (62/93) and not the source of truth.

## A5. Every branch + worktree: HEAD, base, distance behind the deploy branch

[MEASURED] `git worktree list`:

| Worktree path | Branch | HEAD |
|---|---|---|
| /Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker | zero-reject-routing | 1032ec2 |
| /Users/zaclibman/promptly-gpu-worker/hype-harness | hype-render-harness | 5d94441 |
| /Users/zaclibman/promptly-gpu-worker/promptly-errors | agent/errors | 999e684 |
| …/promptly-gpu-worker/.claude/worktrees/agent-a24db59aca6ee75f0 | worktree-agent-a24db59aca6ee75f0 | bc59e4a |
| …/agent-a38d162960bee6992 | worktree-agent-a38d162960bee6992 | 1557937 |
| …/agent-a4d999d39adcebd1d | worktree-agent-a4d999d39adcebd1d | a7579c6 (W3 PROGRESSIVE dark) |
| …/agent-a5403897f32b3ab2f | worktree-agent-a5403897f32b3ab2f | a01450d (S-PACKAGE) |
| …/agent-acc185c1ad8ef4a13 | worktree-agent-acc185c1ad8ef4a13 | c006f52 (S-DEGEN refutation) |
| …/agent-ade6c1a4e563755c2 | worktree-agent-ade6c1a4e563755c2 | acbb7a7 (DEGEN-LEVER-A) |
| …/promptly-gpu-worker/.worktrees/inc2 | inc2-buildout | 543aa90 |
| /Users/zaclibman/promptly-gpu-worker/promptly-prompt | agent/prompt | 5bd164c |
| /Users/zaclibman/promptly-gpu-worker/promptly-smoothness | agent/smoothness | d9543d6 |
| /Users/zaclibman/promptly-gpu-worker/promptly-speed | agent/speed | d0e32ac |

Key relationships to the deploy state [MEASURED]:
- **Live `1601ae0`** = `origin/agent/smoothness` head; local `agent/smoothness`
  (`d9543d6`) is **2 commits ahead** of live (2 undeployed).
- Local `zero-reject-routing` (`1032ec2`) is **2 commits ahead** of the merge-base
  with live but is **MISSING the 10 commits** on the `agent/smoothness` line
  (`git rev-list --count zero-reject-routing..1601ae0 = 10`), including the live one.
  Those 10: 1601ae0 (tail-pad), f8a0798 (HINGLISH), f8c8664 (MERGE agent/errors),
  c1fd07f (sendOwnerAlert into TOCTOU guard), eda2113 (deploy.sh TOCTOU),
  08ec2ea (failed-probe→error), e4fab3c/1710a34/3abe659 (metadata-track copies),
  5052418 (asymmetric edge extension).
- The full active branch list (48 local+remote) was captured; the noteworthy
  DARK/feature branches include: `caption-legibility-floor` (GATED NOT DEPLOYED),
  `edit-policy-step1`/`edit-policy-enforcement`, the `phase-e-substep1..5` Nano-Banana
  generation chain, `phase-b-multi-input-worker`, `phase-d-ask-back`,
  `phase-g-lite-input-quality`, `premium-tier-phase1`, `zero-fatal-ladder`,
  `general-editor`, `broll-picker-vision`, `gemini-cut-channel`.

## A6. Is the deploy branch pushed to a remote? (unpushed work = CRITICAL)

[MEASURED] `git rev-list --left-right --count origin/<branch>...<branch>`:
- **`zero-reject-routing`: 36 commits AHEAD of `origin/zero-reject-routing`
  (6dd2756).** → 36 local-only commits, NOT on the remote. **CRITICAL if this
  checkout's work is expected to be recoverable — it is not backed up.**
- `main`: **31 commits ahead** of `origin/main` (also local-only).
- `agent/smoothness`: 2 commits ahead of `origin/agent/smoothness` (the 2 beyond
  live). The LIVE commit `1601ae0` itself **IS on the remote** (= origin head), so
  the running image is reproducible from origin even though the two newest smoothness
  commits are not pushed.

Net: the live code is safe on `origin/agent/smoothness`, but 36 commits of the
nominal deploy branch and 31 of main live only on this laptop.

## A7. deploy.sh step-by-step + the deploy gate

[CODE] deploy.sh (150 lines):
1. `cd` to script dir; `set -e`.
2. **Pre-deploy validation**: `python3 validate_deploy.py` (line 13). Abort on
   non-zero (lines 16-21).
3. Export `PROMPTLY_DEPLOYER` (default `claude-code`), print deploying branch +
   short HEAD (lines 29-35); warn if `main` is an ancestor and behind (lines 36-40).
4. **NO-REGRESS gate**: `python3 predeploy_no_regress.py` (line 49) — see below.
5. `modal deploy modal_app.py` (line 51).
6. Write HEAD → `.last_deployed_commit` (line 56), print it.
7. **POST-DEPLOY TOCTOU re-check**: re-run `predeploy_no_regress.py` (lines 67-75);
   non-zero → loud "POST-DEPLOY REGRESSION" + `exit 1` (a concurrent deploy raced us).
8. **Post-deploy auth ping**: `modal run cert_auth_ping.py`; require
   `AUTH_PING_STATUS=200` (worker→server MODAL_CALLBACK_SECRET), else `exit 1`
   (lines 82-102). *(This runs `modal run` — a real container; deploy.sh spends here,
   but I did NOT run it.)*
9. **Server→worker auth gate** (conditional): only if `_require_worker_auth` is
   present in modal_app.py (it is not today) → `modal run cert_run_auth_ping.py`
   (lines 104-130). Currently inert (grep finds nothing).
10. **Regression corpus**: `modal run modal_app.py::regression_corpus` (SPAWNs a
    container that self-alerts on REGRESSED), skippable via
    `PROMPTLY_SKIP_REGRESSION` (lines 132-150). ~$0.10-0.15/source.

**validate_deploy.py**: [MEASURED] `grep -c '@check'` = **357** checks. Each is a
`@check("label")`-decorated function asserting one invariant; on assertion failure the
runner records a FAIL and deploy.sh aborts. Sampled labels (representative of the
kinds of thing pinned):
- Parse/import: "handler.py parses as valid Python", "modal_app.py parses…", "handler
  module imports cleanly", "no UnboundLocalError via static analysis (pyflakes)",
  "used-before-assignment gate: mypy possibly-undefined == 0".
- RULE-1 anti-drift guards: "INC2-TELEMETRY NEST GUARD", "VIDSTAB RIP-OUT GUARD",
  "SOURCE_DURATION PERSIST GUARD", "GEMINI_TOKENS PERSIST GUARD", "DEPLOY-STATE GUARD"
  (validate_deploy.py:167 — fails if `.last_deployed_commit` is not an ancestor of
  HEAD), "RENDER CONCURRENCY NEVER FAILS A RENDER".
- Caption/zoom taste pins: "CAPTION ENTRANCE = FRAME-1-IS-FINAL", "CAPTION
  NEVER-EARLY", "STAGEDPUSH", "SHARED-CLOCK LEAD", "MOMENT PRECISION", "VIBE-FEEL".
- Flag/value pins: **"SECRET CANONICAL VALUES"** (validate_deploy.py:7144, the CANON
  dict — see B12), "COST split Phase 0 — SPAWN_MODE COUPLING" (7100),
  **budget==cpu pin** (129-163), **x264 thread pin** (10023-10045), "inc2 RENDER
  BURST" (9902/9951 asserts `cpu=32`), "MOODREEL ROUTE" (6699), "TRANSCRIPTION-
  COVERAGE GATE" (6544), "E1 DENSITY RESHAPE" (6525), "LANGUAGE-ROUTED SCRIBE" (5263),
  "TIER-1 STAGE A" (7245), "THREE-FIELD LANGUAGE BUNDLE" (7232).
Full truncated list of all 357 labels captured to
`recon/` scratch (tool-results b7cw5kyn0.txt).

**predeploy_no_regress.py** (151 lines) [CODE]: asks **Modal itself** for the live
commit (`modal app history --json`, fallback to table parse, live_commit()), then
compares the "revert-detectable surface" of `handler.py` at the live SHA vs the tree
about to deploy. Surface = two families (_surface(), lines 72-92): (a) top-level
`def` names, (b) quoted identifiers ≥6 chars with docstrings+comments stripped. Any
def or literal present live but absent in the deploy tree = a silent revert → prints
the lost names and `exit 1`, telling you to `git merge <live_sha>` first. Deliberate
removals go in `INTENTIONAL_REMOVALS` (currently `{}`). Fails closed if it cannot
reach Modal or if the live commit is not in the repo (unpushed branch).
**Consequence for the current state:** if `deploy.sh` were run from this checkout
(`zero-reject-routing @ 1032ec2`) now, this gate would (if Modal reachable) detect
that deploying would drop the defs/literals introduced in the 10 `agent/smoothness`
commits and **FAIL**, forcing `git merge 1601ae0` first. [INFERRED from the code + the
measured 10-commit gap.]

## A8. Uncommitted changes in the working tree right now

[MEASURED] `git status --porcelain` (HEAD = `1032ec2`, branch `zero-reject-routing`):
**0 modified tracked files. 13 untracked files:**
- `WORKER_TERMINAL_ENUMERATION.md` — a markdown doc (untracked note).
- `cert_bundle_fresh_verify.py` — cert harness (verify bundle freshness).
- `cert_concurrency_ab_app.py` — concurrency A/B Modal harness.
- `cert_cpu4_analysis_timing_app.py` — cpu=4 analysis-timing harness.
- `cert_errors_proof_app.py` — errors-proof harness.
- `cert_gpu_fps.py` — GPU fps probe.
- `cert_inc2_burst_diagnose.py` — inc2 render-burst diagnostic.
- `cert_nvenc_probe_app.py` — NVENC availability probe.
- `cert_planonly_fps_ab_app.py` — plan-only fps A/B.
- `cert_scribe_proof_app.py` — ElevenLabs Scribe proof harness.
- `cert_tab_budget_app.py` — overlay tab-budget harness.
- `cert_thinking_budget_app.py` — post-thinking-budget A/B harness.
- `modal_app.py.bak-preauth` — a backup copy of modal_app.py (pre worker-auth).

None of these are mounted into the image (see A9), none are tracked, so none affect
`_BUILD_DIRTY`, the deployed bundle, or the gates.

NOTE on the system-prompt git snapshot: the header snapshot listed modified files
(`M handler.py`, `M modal_app.py`, …) and commits `ed34eb1…86e3dd0`. Those are
**stale** — `ed34eb1` is dated 2026-07-27 and is an ancestor of the current HEAD; the
live tree today has HEAD `1032ec2` (2026-08-04) with **no modified tracked files**.
Trust the live `git status`, not the header snapshot. [MEASURED]

## A9. Files mounted into the image that shouldn't be; image size + dominant layers

[CODE] modal_app.py image (lines 82-577). Base:
`nvidia/cuda:12.6.3-runtime-ubuntu22.04` + python 3.10 (line 84). apt: ca-certs,
fontconfig, ffmpeg build deps, **full Noto font family** (fonts-noto-core/cjk/extra/
color-emoji, lines 119-132), librubberband, build-essential/clang (110-137). Remotion
`node_modules` installed + patched (`patch-remotion-env.mjs`, line 454). RIFE 4.18
model bundled via add_local (models/rife-v4.18, referenced in the v65 build note).

[MEASURED] 27 `add_local_file`/`add_local_dir` entries. The mounted set is exactly the
runtime modules + assets:
- Dirs: `src/assets/fonts`→/assets/fonts (394), `src/remotion`→/remotion (415),
  `src/assets/sounds`→/assets/sounds (532).
- Files: handler.py, render_timeline.py, edit_policy.py, burned_text.py, premium.py,
  ffmpeg_base.py, rife_normalize.py, render_schemas.py, type_registries.py,
  cuda_driver_setup.py, general_editor.py, hype_editor.py, minimal_editor.py,
  moodreel_editor.py, hype_render.py, progressive_publish.py, recipe_eval.py
  (lines 533-576).
- **No stray cert/harness/test/`.bak` file is mounted** [MEASURED]: grepping the
  add_local list for `cert_|harness|.bak|test_|_app.py|probe` returns nothing. The 13
  untracked cert scripts (A8) are NOT in the image.
- [CODE] All flags moved out of `.env()` except literal schema/feature toggles (see
  B11); mounts are placed after the ENV layer because "Modal forbids any build step
  after add_local_*" (457-458).

Image size + what dominates: [UNKNOWN] — I cannot read the built image size without a
Modal call (`modal image`/inspect would spend or is not permitted). [INFERRED] the
dominant layers are (a) the CUDA 12.6 runtime base (~2-3 GB class), (b) the Remotion
`node_modules` incl. bundled Chromium/Chrome-headless-shell (typically the single
largest layer for Remotion), (c) the Noto CJK+extra fonts (hundreds of MB), (d) the
RIFE model weights (~22 MB). No measurement — tagged INFERRED.

---

# SECTION B — Flags & Configuration

## B10. Every env flag/toggle the worker reads

[MEASURED] `grep -nE 'os.environ.get|getenv|os.environ\['` over handler.py +
modal_app.py → **113 unique names**. Grouped below. "Default" is the literal in the
`os.environ.get(...)` call; "prod" is my read of the live state (secret-pinned values
in B12; shell/literal in B11). file:line is the primary read site.

### Operational feature flags (PROMPTLY_*) — the toggles

Secret-pinned LIVE-ON (value from promptly-lang-flags Secret; canonical in CANON, B12):
| Flag | file:line (default in code) | Off→On behavior | Prod (canonical) |
|---|---|---|---|
| PROMPTLY_SPAWN_MODE | modal_app.py:1270 (checks `=="1"`) | async worker spawn vs sync in-ASGI render | **1** |
| PROMPTLY_OUTCOME_GATE | handler.py:12428 (`"shadow"`) | shadow=ledger-only vs enforce | **shadow** |
| PROMPTLY_LEVER3 | handler.py:772,780,7331 (`""`→off) | degeneration-fix editorial prompt | **1** |
| PROMPTLY_EDIT_IN_LANGUAGE | handler.py:4825 (`""`→off) | multilingual + in-language editorial | **1** |
| PROMPTLY_SCRIPT_DENYLIST | handler.py:4816 (None) | scripts denied render (tofu-guard) | **"" (none denied)** |
| PROMPTLY_PLAN_CAPTURE | handler.py:778,824 (`""`) | plan-capture corpus hook | **"" (inert)** |
| PROMPTLY_BURNED_TEXT | handler.py:4836 (`""`→off) | EAST burned-in-text double-caption guard | **1** |
| PROMPTLY_ZERO_REJECT | handler.py:31691 (`""`→off) | content classes become ROUTES not rejects | **1** |
| PROMPTLY_WHY_DIET | handler.py:11993 (`"1"`→on unless off) | rationale output cap 240→96 (speed) | **1** |
| PROMPTLY_DELIVERY_FPS | handler.py:36255 (`""`=60) | delivery target fps | **30** |
| PROMPTLY_RENDER_FANOUT | handler.py:24526 (`""`→off) | 8-16 parallel render containers | **0 (deliberate emergency-off)** |
| PROMPTLY_HYPE_MODE | general_editor.py:33 (`""`→off) | no-speech+confident-beat → beat-synced edit | **1** |
| PROMPTLY_SHAPE_ABORT | handler.py:11199 (`"1"`→on unless off) | degen shape-abort stream kill | **1** |
| PROMPTLY_MOODREEL | handler.py:32270 (`""`→off) | cinematic mood-reel route | **1** |
| PROMPTLY_HQ_RESAMPLE | handler.py:22092 (`""`→off) | lanczos down + spline up resample | **1** |
| PROMPTLY_BROLL_GATE | handler.py:20481 (`""`→off) | b-roll content+safety gate | **1** |
| PROMPTLY_COVERAGE_GATE | handler.py:22157 (`""`→off) | transcription-coverage gate + bridge | **1** |
| PROMPTLY_LANG_ROUTING | handler.py:5096 (`""`→off) | TIER-1 Stage A Gemini-ID→monolingual reroute | **1** |
| PROMPTLY_SMOOTH_GRAPHICS | handler.py:19253,27568,27840 (`""`→off) | zoom/MG velocity cap | **1** |
| PROMPTLY_ASR_SCRIBE | handler.py:4491 (`""`→off) | ElevenLabs Scribe fallback on coverage fail | **1** |
| PROMPTLY_RENDER_BURST | handler.py:24546 (`""`→off) | render_stage on cpu=32 burst vs in-process | **1** |
| PROMPTLY_POST_THINKING_BUDGET | handler.py:12310 (`"24576"`) | editorial Gemini thinking tokens | **2048** |

Read-back but NOT value-pinned (in secret_flags_readback FLAG_KEYS, absent from CANON —
live value UNKNOWN without a Modal read):
| Flag | file:line (default) | Behavior |
|---|---|---|
| PROMPTLY_ROUTE_LANGS | handler.py:5181 (None) | graduated language set for Stage A (grows per-script; code default frozenset{"hi"}) |
| PROMPTLY_MOTION_BLUR | handler.py:33998 (`""`→off) | motion blur on graphics (Zac note: "BLUR stays OUT") |
| PROMPTLY_MIN_OUTPUT_RATIO | handler.py:38569 (`0.0`) | min output/source ratio gate |
| PROMPTLY_CAPTION_ALIGN | handler.py:24341 (`""`→off) | caption alignment pass |

DARK / default-OFF, NOT in CANON, NOT secret-pinned (full C14 treatment below):
PROMPTLY_HLS_COPY (31709), PROMPTLY_PROGRESSIVE (31608), PROMPTLY_LEAN_SCHEMA (12071),
PROMPTLY_LEAN_DECOR_GROUND (12084), PROMPTLY_MEDIA_RESOLUTION (12317),
PROMPTLY_PLAN_ONLY (37671), PROMPTLY_PAYOFF_PUNCHY (11908), PROMPTLY_STRUCTURE_ABORT
(11214), PROMPTLY_DWELL (12148), PROMPTLY_DENSITY (22145), PROMPTLY_MOTION_TOKENS
(27564), PROMPTLY_MOTION_ANCHORS (31915), PROMPTLY_RESPRUNG_ZOOMS (27836),
PROMPTLY_SPEAKER_CAPTIONS (7850), PROMPTLY_PROMPT_ORDER (7430, "v2" off),
PROMPTLY_SILENT_TO_MOODREEL (32084), PROMPTLY_SCHEMA_PAD (12212),
PROMPTLY_PROXY_SAMPLE_FPS (13272, default **18**, a value not a toggle),
PROMPTLY_MIN_OUTPUT_S (38571, default 1.5).

Operational-value flags with an ON default (behavior always active unless explicitly
disabled) — NOT in the secret, code-default drives them:
| Flag | file:line (default) | Behavior |
|---|---|---|
| PROMPTLY_SHARED_GEMINI_CACHE | handler.py:10021 (`"1"`) | shared Gemini cache on unless off |
| PROMPTLY_RECIPE_WALL | handler.py:10480 (`"1"`) | recipe wall-clock budget on |
| PROMPTLY_RECIPE_WALL_S / _LATENCY_S | handler.py:10495 / 10519 (`""`) | numeric overrides |
| PROMPTLY_VALIDATOR_FORCE_TH | handler.py:33555 (`"1"`) | force talking-head validator |
| PROMPTLY_STEP_DURABLE | handler.py:31371 (`"1"`) | durable step-token writes |
| PROMPTLY_RATIONALE_PERSIST | handler.py:31511 (`"1"`) | persist edit_rationale |
| PROMPTLY_PACKAGE_PERSIST | handler.py:31560 (`"1"`) | persist post_package |
| PROMPTLY_PREVIEW_PERSIST | handler.py:31628 (`"1"`) | persist preview |
| PROMPTLY_VIDSTAB_THRESHOLD | handler.py:36161 (`1e9`) | vidstab RIP-OUT clamp (never fires) |
| PROMPTLY_PREWARM_POLL_S | handler.py:33040 (`"240"`) | prewarm poll interval |
| PROMPTLY_SOURCE_POLL_S | handler.py:35463 (`"600"`) | source-wait deadline |
| PROMPTLY_RENDER_CORE_BUDGET | handler.py:3231 (`"16"`) | Remotion --concurrency cap; SET per-function in modal_app.py body |
| PROMPTLY_RENDER_CHUNKS | handler.py:28037,28299 (`8`) | overlay/micro chunk count cap |
| PROMPTLY_CHUNK_FRAMES | handler.py:28043 (`450`) | frames per render chunk |
| PROMPTLY_OVERLAY_TAB_BUDGET | handler.py:28094,28295 (cores//2) | Remotion tab budget |
| PROMPTLY_BURST_MIN_OUTPUT_S | handler.py:24685 (`45.0`) | min output secs to route to burst |
| PROMPTLY_FANOUT_MIN_OUTPUT_S | handler.py:28600 (`60.0`) | min output secs for fanout |

Other `*_ENABLED` toggles (not PROMPTLY_-prefixed):
| Flag | file:line (default) | Behavior | Prod |
|---|---|---|---|
| JOB_STATUS_WRITES_ENABLED | handler.py:30698 (`""`) | durable video_jobs status writes | **1** (baked, B11) |
| GAP_COMPRESSION_ENABLED | modal_app.py .env (baked) | inter-word gap compress | **1** (baked) |
| PACING_MAX_COMPRESSION_ENABLED | handler.py:35057 (`"0"`) | collapse boundary gaps to 75ms | **1** (baked in .env, overrides code default 0) |
| WITHIN_CLIP_DEADAIR_ENABLED | handler.py:35069 (`"1"`) | within-clip dead-air trim | on |
| SAFE_EDIT_FALLBACK_ENABLED | handler.py:31126 (`"1"`) | safe-edit degrade ladder | on |
| VIDEO_REFERENCE_ENABLED | handler.py:12957 (`"1"`) | send video to Gemini reference | on |
| PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS | handler.py:18913 (`""`)/baked "1" | array-level auto-revert on re-edit | **1** (baked) |
| RECIPE_REPAIR_MAX_ATTEMPTS | handler.py:13717 (`"1"`) | recipe repair re-ask count | 1 |
| EDIT_POLICY_ENABLED | handler.py:37643 (`""`→off) | EditPolicy enforcement | **off (DARK)** |
| ASK_BACK_ENABLED | handler.py:31249 (`""`→off) | Phase-D ask-back | **off (DARK)** |
| MULTI_INPUT_ENABLED | handler.py:35200 (`""`→off) | Phase-B multi-input concat | **off (DARK)** |

### Non-flag env (credentials / schema / infra) — read, not toggles
S3/AWS: S3_BUCKET_NAME, SUPABASE_S3_BUCKET, AWS_REGION, AWS_DEFAULT_REGION,
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, SUPABASE_S3_REGION/ACCESS_KEY/SECRET_KEY.
Supabase: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_SERVICE_KEY, SUPABASE_KEY.
LLM/ASR: GEMINI_API_KEY, DEEPGRAM_API_KEY, ELEVENLABS_API_KEY, PEXELS_API_KEY,
HF_TOKEN, HUGGINGFACE_TOKEN, GCP_SERVICE_ACCOUNT_JSON, GOOGLE_CLOUD_PROJECT,
GOOGLE_CLOUD_LOCATION. Callback/infra: APP_URL, MODAL_CALLBACK_SECRET,
PROMPTLY_DEPLOYER, PROMPTLY_BUILD_SHA/DIRTY/TS. Schema overrides (baked, B11):
PROMPTLY_TIER_TABLE/USER_COLUMN/COLUMN, PROMPTLY_PREMIUM_VALUES, PROMPTLY_JOB_TABLE/
USER_COLUMN/STATUS_COLUMN/ACTIVE_STATUSES. TLS: SSL_CERT_FILE, REQUESTS_CA_BUNDLE.
Cert-harness only (modal_app.py entrypoints): CERT_AUDIO_DIR, CERT_ONLY,
CERT_AUDIO_<lang>.

## B11. Secret-resident vs shell-baked flags

[CODE] modal_app.py Secrets (lines 580-617): `promptly-secrets` (AWS/HF/Deepgram/
Gemini keys), `promptly-cloudfront`, `gemini-vertex` (Vertex creds),
**`promptly-lang-flags`** (the operational flags), `promptly-elevenlabs`
(ELEVENLABS_API_KEY).

**The historical shell-baked hazard is CLOSED.** [CODE] modal_app.py:466-481 and
593-609: the operational flags (SPAWN_MODE, OUTCOME_GATE, LEVER3, EDIT_IN_LANGUAGE,
SCRIPT_DENYLIST, PLAN_CAPTURE — and by CANON the full 22-flag set) were removed from
the `.env()` block in 2026-07-23 because `.env()` baked them **from the deployer's
shell**, so a plain `./deploy.sh` that forgot to set them silently reverted them
("multilingual went Latin-only + lever3 off for ~40 min"). They now live in the
`promptly-lang-flags` Secret, injected at runtime — independent of the deploy shell.

Therefore, **NO operational feature flag is shell-baked today.** What remains in the
image `.env()` (modal_app.py:461-531) are **literal constants written in the source**
(not from the shell) and so are stable across a plain deploy:
- Build identity: PROMPTLY_BUILD_SHA/DIRTY/TS (from `_git`), PROMPTLY_DEPLOYER
  (the ONE value sourced from the shell via `deploy.sh` export at deploy.sh:29;
  default "unknown"/"claude-code" — cosmetic, identifies the operator only).
- Schema overrides (literals): PROMPTLY_TIER_TABLE="profiles",
  PROMPTLY_TIER_USER_COLUMN="id", PROMPTLY_PREMIUM_VALUES="pro,teams,premium",
  PROMPTLY_JOB_TABLE="video_jobs", PROMPTLY_JOB_ACTIVE_STATUSES="queued,processing".
- Feature literals: JOB_STATUS_WRITES_ENABLED="1", GAP_COMPRESSION_ENABLED="1",
  PACING_MAX_COMPRESSION_ENABLED="1", PROMPTLY_REEDIT_PHASE2_ARRAY_REVERTS="1".
- PROMPTLY_RENDER_CORE_BUDGET is set **in each Modal function body** (modal_app.py:666
  ="16" for run_pipeline_bg; :1033 ="32" for render_burst), tracking that function's
  `cpu=`; validate_deploy pins budget==cpu.

So: the only shell-sourced env is `PROMPTLY_DEPLOYER` (cosmetic). Everything
operational is either a source literal (stable) or in the Secret (stable). **No
operational flag will silently revert on a plain `./deploy.sh`.** [CODE]

## B12. Canonical flag set the gate asserts vs live

[CODE] validate_deploy.py:7144-7198, the "SECRET CANONICAL VALUES" check. The gate
runs `modal run secret_flags_readback.py` (a **Modal spend** — I did NOT run it),
reads the `READBACK {json}` line, and FAILS on any drift from CANON. secret_flags_
readback.py FLAG_KEYS (26 keys, lines 22-49) enumerates what is READ; CANON
(validate_deploy.py:7149-7172, **22 keys**) enumerates what is value-ASSERTED.

**CANON (the enforced live values)** [CODE]:
```
PROMPTLY_SPAWN_MODE=1        PROMPTLY_OUTCOME_GATE=shadow   PROMPTLY_LEVER3=1
PROMPTLY_EDIT_IN_LANGUAGE=1  PROMPTLY_SCRIPT_DENYLIST=""    PROMPTLY_PLAN_CAPTURE=""
PROMPTLY_BURNED_TEXT=1       PROMPTLY_ZERO_REJECT=1         PROMPTLY_WHY_DIET=1
PROMPTLY_DELIVERY_FPS=30     PROMPTLY_RENDER_FANOUT=0       PROMPTLY_HYPE_MODE=1
PROMPTLY_SHAPE_ABORT=1       PROMPTLY_MOODREEL=1            PROMPTLY_HQ_RESAMPLE=1
PROMPTLY_BROLL_GATE=1        PROMPTLY_COVERAGE_GATE=1       PROMPTLY_LANG_ROUTING=1
PROMPTLY_SMOOTH_GRAPHICS=1   PROMPTLY_ASR_SCRIBE=1          PROMPTLY_RENDER_BURST=1
PROMPTLY_POST_THINKING_BUDGET=2048
```

**Read-back-but-not-pinned** (in FLAG_KEYS, absent from CANON → the gate does not
assert their value): `PROMPTLY_ROUTE_LANGS`, `PROMPTLY_MOTION_BLUR`,
`PROMPTLY_MIN_OUTPUT_RATIO`, `PROMPTLY_CAPTION_ALIGN`. These four can drift without
tripping the gate — a minor gap (their behavior is dark/secondary, so low risk, but
worth noting).

**Live values vs canonical: [UNKNOWN]** — reading the live secret requires
`modal run secret_flags_readback.py`, which spends (forbidden here). I read what the
gate WOULD assert, not the live values. The gate is the enforcement point: **IF
deploy.sh was run for v521, the canonical-values check passed at that time** (deploy
succeeded), which is the strongest inference available that live == CANON as of
2026-08-04 19:39. [INFERRED] No `[readback]` line is queryable from
`modal app logs promptly-gpu-worker` because the readback runs in a *separate*
ephemeral app (`promptly-secret-readback`), not the worker app. Any drift introduced
after v521 by a raw `modal secret create … --force` without a redeploy would be
invisible until the next deploy — **UNKNOWN, cannot verify without a Modal read.**

## B13. Hardcoded constants encoding an environment assumption

[CODE] Render determinism / encoder:
- `_X264_ENCODE_THREADS = 48` — handler.py:2124. Pinned so libx264 output is
  byte-identical across any cpu (x264-auto sizes threads from machine cores). "NEVER 0
  (validate_deploy asserts it)". Env it was sized for: the render lane at any cpu
  (16/32/48). Pinned by validate_deploy.py:10023-10045.
- `_PROXY_X264_THREADS = 48` — handler.py:2137. Separate pin for the 480p/18fps
  Gemini-proxy encode so it stays byte-identical across planner cpu (4 vs 16).
- Final encode: NVENC path (`h264_nvenc -preset p4 -cq 18`) when `_has_nvenc()`, else
  `libx264 -preset ultrafast -crf 18` — handler.py:2149-2180. **The
  orchestrator/render containers have NO `gpu=`** (A9/below), so NVENC is absent in
  prod → the libx264 (thread-pinned, deterministic) path is the live one. [INFERRED
  from no gpu= on run_pipeline_bg/render_burst.]
- Output canvas **1080×1920 portrait, fps 30** hardcoded across the pipeline:
  handler.py:3399-3400 (defaults 1080/1920), :3583/:3664 (canvas 1080×1920),
  :7836 (_SPEAKER_CAP_CANVAS_H=1920), :19409-19411, :21396-21397, :22057-22069
  (scale 1080:1920, fps=30, yuv420p), :22390-22442 (needs_scale_crop w!=1080|h!=1920).

[CODE] Render concurrency / chunking:
- `PROMPTLY_RENDER_CORE_BUDGET` — the container cpu declared to Python because
  `os.cpu_count()` can't read the Modal cpu request. Set to "16" for run_pipeline_bg
  (modal_app.py:666), "32" for render_burst (:1033). Read at handler.py:3231
  (default "16"), 28076. `_render_core_budget()` returns a conservative floor of 4 on
  a miss (validate_deploy.py:137). budget==cpu pinned by validate_deploy.py:129-163.
- `_RENDER_CHUNKS` default **8** (handler.py:28037,28299,28384; PROMPTLY_RENDER_CHUNKS).
- `_CHUNK_FRAMES` default **450**, floor 150 (handler.py:28043,28386).
- `_MICRO_CHUNK_THRESHOLD = 200` (handler.py:28263); `_MICRO_CHUNK_COUNT` min 4
  (:28302).
- `_TAB_BUDGET = min(cores, OVERLAY_TAB_BUDGET or max(4, cores//2))` (handler.py:28093-95).
  Comment (28087): a stale `PROMPTLY_OVERLAY_TAB_BUDGET=32` sized for cpu=64 was a
  RENDER_FATAL source ("Maximum for --concurrency is 8"). Now derived from cores.
- `_PER_CHUNK_CONCURRENCY = min(cores, max(2, tab_budget//overlay_chunk_count))`
  clamped to cores (handler.py:28097-98) — Remotion hard-rejects concurrency>cores.
- render_chunk_fanout: `max_concurrency=32` (modal_app.py:919), subprocess
  `timeout=1080` (:950).

[CODE] Modal function resource sizing (all region us unless noted):
| Function (modal_app.py) | cpu | memory | timeout | scaledown | gpu | RENDER_CORE_BUDGET |
|---|---|---|---|---|---|---|
| run_pipeline_bg (spawned render orchestrator) :651-666 | 16 | 12288 (12GiB) | 1200 | 45 | none | 16 |
| render_chunk_fanout :898 | 16 | 32768 | 1200 | — | none | — |
| render_burst :1018-1033 | 32 | 65536 (64GiB) | 1200 | — | none | 32 |
| PromptlyWorker (main cls / dispatcher) :1154-1184 | 8 | 32768 | 3000 | 30 | none | — |
| Prewarm/source class :1307-1319 | (dflt) | 4096 | 300 | 600 | none | — |
| sample/face class :1364-1367 | 4 | 2048 | 60 | 300 | none | — |
| small class :1416-1419 | 2 | 1024 | 30 | 300 | none | — |
| tiny :1464-1467 | 0.25 | 512 | 60 | — | none | — |
| **rife_normalize_remote :1516-1529** | 4 | 16384 | 480 | 90 | **H100** | — |

Sizing history baked into comments [CODE modal_app.py:651]: cpu was 64→16 (emergency
cost cut 2026-07-30, then 8→16 CPU-starvation correction 2026-08-03); memory
128→64→24→12 GiB across the render_burst split; timeout 3000→1800→1200 (STALL CAP).
The **only GPU consumer is RIFE** (`rife_normalize_remote`, H100) — the render
orchestrator dropped its H100 (modal_app.py:1505-1510: "Splitting RIFE off lets the
orchestrator drop its H100"). Consistent with the memory note (render worker CPU-only).

[CODE] Other env-assumption constants:
- Gemini client timeout 480s (referenced modal_app.py:1154 comment; handler
  `_get_genai_client`).
- `_MICRO_CHUNK_THRESHOLD`, `PROMPTLY_BURST_MIN_OUTPUT_S`=45 (handler.py:24685),
  `PROMPTLY_FANOUT_MIN_OUTPUT_S`=60 (:28600).
- Required-field schema: the two `@check`s "\_BrollClip NO LONGER requires
  viewer_feeling" / "\_MotionGraphic NO LONGER requires viewer_feeling"
  (validate_deploy.py:2480,2488) pin that those fields are optional (the
  extra="forbid" / required-field class the memory warns about).
- content-studio reaper coupling: worker `timeout=3000` requires reaper
  `EXEC_WALL_MS >= 3300` (modal_app.py:1154 INVARIANT).

All the environments these were sized for (cpu=16 orchestrator, cpu=32 burst, H100
RIFE) currently exist. No obviously-orphaned constant sized for a retired env was
found, EXCEPT the vestigial "cpu=48" language in several render_burst comments
(modal_app.py:1010-1032, validate_deploy.py:7170) which now contradicts the actual
`cpu=32` decorator (BURST CPU CUT 48→32, 2026-08-03). The DECORATOR and the
budget-set literal are 32 (authoritative); the surrounding prose is stale. Minor doc
drift, not a behavioral bug (validate_deploy.py:9951 asserts `cpu=32`). [MEASURED]

---

# SECTION C — Unflipped Inventory (DARK / default-OFF features)

All flags below verified **present in the live image** `git show 1601ae0:handler.py`
[MEASURED]. "Present live" = grep count in the live SHA's handler.py.

## C14. Features built behind a currently-OFF flag

| Feature | Flag (file:line) | Default | Present in live 1601ae0 | What it does | Blocked on / evidence | 
|---|---|---|---|---|---|
| **Progressive delivery (W3)** | PROMPTLY_PROGRESSIVE (handler.py:31608,33945) | "" off | yes (5×) | publish preview clips while the render still runs; Phase-B status substance | module `progressive_publish.py` IS now mounted (modal_app.py:568 — the cert-found "wiring shipped, module didn't" gap is closed). Gate: validate_deploy.py:6324/6377 "PROGRESSIVE TERMINAL SEAM". Cert bar is determinism-relative, not byte-identity. Blocked on: a decision to flip + watch on real traffic. |
| **Lean schema** | PROMPTLY_LEAN_SCHEMA (handler.py:12071) | "" off | yes (5×) | trimmed Gemini output schema (token/latency lever) | `PROMPTLY_LEAN_DECOR_GROUND` (:12084) is the paired grounding sub-flag. Blocked on: A/B measurement of quality vs the token saving. |
| **HLS copy** | PROMPTLY_HLS_COPY (handler.py:31709) | "" off | yes (1×) | emit HLS variant by stream-copy (delivery format) | Blocked on: player/CDN decision; no evidence run found. |
| **Media resolution override** | PROMPTLY_MEDIA_RESOLUTION (handler.py:12317) | "" off | yes (1×) | override Gemini media_resolution (video token budget) | Blocked on: cost/quality A/B on Gemini video tokens. |
| **Plan-only seam** | PROMPTLY_PLAN_ONLY (handler.py:37671) | "" off | yes (1×) | run the planner and stop before render (A/B harness seam) | Also per-job `plan_only`. Used by cert harnesses (cert_planonly_fps_ab_app.py, untracked). Blocked on: nothing — it's an A/B tool, on-demand. |
| **EditPolicy enforcement** | EDIT_POLICY_ENABLED (handler.py:37643) | "" off | yes (2×) | resolve + enforce an edit policy that SHAPES the edit | module `edit_policy.py` mounted (modal_app.py:540). Branches `edit-policy-step1`/`edit-policy-enforcement` exist. Folded under Lumen premium on `premium-tier-phase1`. Blocked on: premium tier rollout decision. |
| **Multi-input ingest (Phase B)** | MULTI_INPUT_ENABLED (handler.py:35200) | "" off | yes (3×) | sequential concat of multiple source clips | branch `phase-b-multi-input-worker`. Blocked on: frontend contract + a flip decision. |
| **Ask-back (Phase D)** | ASK_BACK_ENABLED (handler.py:31249) | "" off | yes (2×) | pause a job to ask the user a clarifying question | branch `phase-d-ask-back` (flat resume contract). Blocked on: frontend resume UI. |
| **E1 density reshape** | PROMPTLY_DENSITY (handler.py:22145) | "" off | yes (3×) | raise component-event density toward the reference | Gate: validate_deploy.py:6525. Memory (project_e1_density_ceiling): density ceiling is ARCHITECTURAL, prompt-tunable only so far; OFF pins ~6 events/20s. Blocked on: the culling-gate architecture, not just a flip. |
| **Motion tokens** | PROMPTLY_MOTION_TOKENS (handler.py:27564) | "" off | yes (1×) | motionTokens schema field for graphics motion | Memory warns extra="forbid" once blocked motionTokens silently. Blocked on: schema mirror + A/B. |
| **Motion anchors** | PROMPTLY_MOTION_ANCHORS (handler.py:31915) | "" off | yes | anchor graphics motion to beats/words | Blocked on: A/B. |
| **Resprung zooms** | PROMPTLY_RESPRUNG_ZOOMS (handler.py:27836) | "" off | yes | spring-resettle zoom variant (pairs with SMOOTH_GRAPHICS) | Blocked on: taste A/B. |
| **Structure abort** | PROMPTLY_STRUCTURE_ABORT (handler.py:11214) | "" off | yes | degen abort on structural signal (sibling to SHAPE_ABORT=1) | Blocked on: FP measurement vs SHAPE_ABORT. |
| **Payoff punchy** | PROMPTLY_PAYOFF_PUNCHY (handler.py:11908) | "" off | yes | punchy payoff zoom arc | Memory (project_payoff_purity): the punchy payoff arc is structurally UNREACHABLE (ZOOM_ARC_HOMES['payoff']=slow-only, 0/253 prod) — flag alone won't surface it. Blocked on: the arc-home wiring. |
| **Dwell** | PROMPTLY_DWELL (handler.py:12148) | "" off | yes | dwell-time pacing variant | Blocked on: A/B. |
| **Schema pad** | PROMPTLY_SCHEMA_PAD (handler.py:12212) | "" off | yes | pad the output schema (degen mitigation) | Blocked on: measurement. |
| **Speaker captions** | PROMPTLY_SPEAKER_CAPTIONS (handler.py:7850) | "" off | yes | per-speaker caption styling (diarization) | Needs HF_TOKEN pyannote. Blocked on: diarization quality. |
| **Prompt order v2** | PROMPTLY_PROMPT_ORDER (handler.py:7430, "v2") | "" | yes | reordered system-prompt sections | Blocked on: A/B. |
| **Silent→moodreel** | PROMPTLY_SILENT_TO_MOODREEL (handler.py:32084) | "" off | yes | route silent clips to the moodreel path | MOODREEL itself is =1 live; this extends its entry condition. Blocked on: decision. |
| **Motion blur** | PROMPTLY_MOTION_BLUR (handler.py:33998) | "" off (read-back, not pinned) | yes | motion blur on graphics | Zac explicitly: "BLUR stays OUT" (CANON SMOOTH_GRAPHICS note). Blocked on: Zac taste veto — held OFF deliberately. |
| **Caption align** | PROMPTLY_CAPTION_ALIGN (handler.py:24341) | "" off (read-back, not pinned) | yes | caption alignment pass | Harnesses cert_caption_align_*.py. Blocked on: alignment-quality measurement. |
| **Min output ratio/secs** | PROMPTLY_MIN_OUTPUT_RATIO (:38569, dflt 0.0) / _MIN_OUTPUT_S (:38571, dflt 1.5) | off/inert | yes | reject if output/source too small | Blocked on: a chosen ratio threshold. |
| **Render fanout** | PROMPTLY_RENDER_FANOUT (handler.py:24526) | "" off; CANON=**0** | yes | 8-16 parallel render containers (~19% wall-clock, cert SSIM 1.0) | NOT a dark unbuilt feature — a **deliberately-held emergency cost lever** (CANON comment: implicated in the $1500 wall; turning to 1 is a PRICED trade, not a drift-fix). Blocked on: a priced cost decision. |

Note: `PROMPTLY_PROXY_SAMPLE_FPS` (default **18**) is a value, not a toggle — it is
"on" at 18 fps by default; not an unflipped feature. `PROMPTLY_ANALYSIS_SPLIT` from
the task's suspect list **does not exist anywhere** in the codebase [MEASURED] —
never built (the analysis/render split is expressed via SPAWN_MODE + RENDER_BURST +
the split Modal functions, not an ANALYSIS_SPLIT flag).

## C15. What would flip each

- **Nothing but a decision + watched-traffic flip** (built, gated green, present live):
  PROGRESSIVE (module now mounted), PLAN_ONLY (on-demand A/B tool), RENDER_FANOUT
  (priced cost decision), SILENT_TO_MOODREEL, PROMPT_ORDER-v2.
- **A measurement/A-B first**: LEAN_SCHEMA (+LEAN_DECOR_GROUND), MEDIA_RESOLUTION,
  DWELL, SCHEMA_PAD, MOTION_ANCHORS, RESPRUNG_ZOOMS, STRUCTURE_ABORT (FP-rate vs
  SHAPE_ABORT), CAPTION_ALIGN, MIN_OUTPUT_RATIO/_S, HLS_COPY (player/CDN test).
- **A frontend contract / product decision**: MULTI_INPUT_ENABLED (Phase B),
  ASK_BACK_ENABLED (Phase D), EDIT_POLICY_ENABLED (premium rollout),
  SPEAKER_CAPTIONS (diarization UX).
- **Architecture, not a flip** (flag alone insufficient): DENSITY (culling-gate
  ceiling), PAYOFF_PUNCHY (ZOOM_ARC_HOMES wiring), MOTION_TOKENS (extra="forbid"
  schema mirror).
- **A Zac taste reversal**: MOTION_BLUR (deliberately held OFF).

---

## Appendix — commands run (all read-only)
`git worktree list`, `git branch -a -vv`, `git rev-parse`, `git rev-list --count /
--left-right`, `git merge-base [--is-ancestor]`, `git log --oneline`,
`git show <sha>:handler.py | grep`, `git status --porcelain [--untracked-files=no]`,
`grep`/`wc` over handler.py/modal_app.py/validate_deploy.py, `cat .last_deployed_commit`,
`modal app history promptly-gpu-worker` (read-only). **No `modal run`/`deploy`/`shell`;
no container started; no Modal spend.**
# Promptly backend recon — Sections D (pipeline), E (model calls), F (output schema)

Repo: `/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker`
Tags: [MEASURED] direct observation · [CODE](file:line) source-verified · [INFERRED] · [UNKNOWN]
DB numbers via read-only SELECT on content-studio `video_jobs` (SUPABASE service role).

---

## SECTION D — Pipeline end-to-end

### D16. One job dispatch → delivered video (every stage, owner, critical-path vs concurrent)

Entry chain (dispatch):
1. [CODE](modal_app.py:1254) `PromptlyWorker.run_job` — synchronous `@modal.fastapi_endpoint(POST)`. The app server (content-studio) POSTs the job body here.
2. [CODE](modal_app.py:1270) When `PROMPTLY_SPAWN_MODE==1` (it is LIVE per CANON), `run_job` calls `run_pipeline_bg.spawn(body)` and returns `{"spawned":True,"call_id":...}` in ms. It does NOT render. (SPAWN_MODE=0 sync fallback calls `self._handler` in-process — dormant.)
3. [CODE](modal_app.py:656) `run_pipeline_bg(body)` — the real pipeline container. Installs shutdown handler, reloads prewarm volume, starts a daemon cpu/mem-per-stage sampler, then calls `result = _H.handler({"input": body})` [CODE](modal_app.py:768).
4. [CODE](modal_app.py:849) On return, `run_pipeline_bg` POSTs the full `result` to `{APP_URL}/api/modal-complete` (primary completion delivery, marker `[completion-post]`). Best-effort; failure falls back to dispatch's Supabase recovery + the reaper.

Inside `handler.handler()` [CODE](handler.py:34881), in order:
- **Field/tier gates** [CODE](handler.py:34921-34961): required-fields check; `fetch_user_tier` + `check_concurrency_gate` (non-premium concurrent submissions rejected → terminal `failed` write). Critical path, serial, early.
- **Premium fork** [CODE](handler.py:34974-35032): `is_premium` from server tier only; `route_premium = is_premium AND premium_pipeline_enabled`. Builds `CostMeter` + `PremiumContext`. Phase-1 scaffold = byte-identical to base.
- **Mode resolution** [CODE](handler.py:35044): `full|render_only|tweak|guided_redraft|reinterpret|resume_ask`.
- **`_early_pool`** (3 workers) [CODE](handler.py:35370): submits `get_trend_context` [CODE](handler.py:35387) early, overlapped with source acquisition. Concurrent.
- **Source acquisition** [CODE](handler.py:35529-35533): `source_poll` (await in-flight prewarm) + `download` from S3. Critical path.
- **`mega_pool`** (10 workers, `concurrent.futures.ThreadPoolExecutor`) [CODE](handler.py:37589) — THE concurrent fan-out (detail in D17). Submits ~15 tasks; the long pole is `future_edit` (the Gemini editorial recipe) collected first via `future_edit.result()` [CODE](handler.py:37665).
- **Merge + anchor translation** [CODE](handler.py:13992-14005): mechanical cuts + translated PostCutPlan → `edit_plan`. ("Translate" = kept-index→source-index reindex, NOT language.)
- **Transitions sub-call** [CODE](handler.py:14772) (separate Gemini call, gated on seams existing) → `edit_plan["transitions"]`.
- **fps_normalize result collected** [CODE](handler.py:38362); face trajectory collected [CODE](handler.py:38379); `mega_pool.shutdown(wait=False)` [CODE](handler.py:38388).
- **`render_stage`** [CODE](handler.py:33895) — render ladder, QA-judge recovery, integrity gate, upload/HLS/cover fan-out, format export. Under `PROMPTLY_RENDER_BURST=1` (LIVE) this whole stage runs in a SEPARATE container `render_burst` [CODE](modal_app.py:1024) reached via `modal.Function.from_name(...,"render_burst")`; result returns by value. `_set_cpu_stage("render")` at [CODE](handler.py:38598).
- **Terminal completion write** [CODE](handler.py:38919) `write_job_status(..., status="completed", ...)` then `return result_payload` [CODE](handler.py:38979).

[MEASURED] delivered-job stage wall-clock (n=300 recent completed, DB `result.stage_timings`):
`total` p50 44.4s / p90 189.9s / max 403s; `render` p50 19.7 / p90 140.7 / max 379; `edit_plan` p50 14.4 / p90 31.1 (n=129); `normalize_transcribe_upload` p50 18.8 / p90 61.7; `fps_normalize` p50 7.6 / p90 45; `upload_export` p50 4.4 / p90 8.9; `hls` p50 2.3 / p90 6.9; `download` p50 1.0 / p90 1.9; `source_duration_s` p50 20.9 / p90 59.4.

### D17. Serial vs parallel — the actual critical path

Parallel block = `mega_pool` (10 workers) [CODE](handler.py:37589). Tasks submitted [CODE](handler.py:37590-37649), each wrapped in `_timed()` for the `[long-pole]` instrument:
- `normalize`, `transcribe` (Deepgram), `gemini_proxy` (proxy encode), `trend`, `loudness`, `shot_changes`, `vocal_emphasis`, `shake_probe`, `exposure_probe`, `fps_normalize`, `user_style`, `platform_pulse`, `edit` (`_do_edit_recipe_overlapped` — the Gemini editorial call), `faces`, and optionally `policy` (EditPolicy resolve, gated).
- pyannote diarization is NOT in the pool — lazily dispatched from `_get_resolved_transcript` only when Deepgram reports ≥2 speakers [CODE](handler.py:37592-37598).

Critical path INSIDE the pool = `future_edit` (Gemini editorial recipe). It internally awaits transcript + proxy + faces + signals before calling Gemini, so it subsumes those. Collected first [CODE](handler.py:37662-37665) with the comment "critical path — longest wait (Gemini)". `fps_normalize` runs in parallel with Gemini so `future_fps_normalize.result()` [CODE](handler.py:38362) is usually already done.

`[long-pole]` readout [CODE](handler.py:38363-38370) prints per-task durations sorted desc at pool teardown — the instrument that decides whether the CPU-bound subset can move to a cheaper container (transcribe is network-bound → must stay).

Overall serial spine: dispatch → source download → **[parallel pool: transcribe ∥ proxy ∥ signals ∥ Gemini-recipe ∥ fps_normalize]** → merge + transitions sub-call → **render_stage (serial, own container under burst)** → upload/HLS/export → terminal write. The two dominant serial poles are the Gemini recipe (`edit_plan` p50 14.4s) and `render` (p50 19.7s, p90 140.7s).

### D18. Container classes (`modal_app.py`) — stage / cpu / memory / handoffs

| Fn/cls | file:line | cpu | mem | timeout | role / handoff |
|---|---|---|---|---|---|
| `PromptlyWorker` (`run_job`,`warmup`) | [CODE](modal_app.py:1221) | 8 | 32768 | 3000 | @app.cls dispatcher endpoint. SPAWN_MODE=1 → `run_pipeline_bg.spawn()`; returns call_id. retries=2, scaledown=30, memory_snapshot. `warmup` NEUTERED (returns instantly). |
| `run_pipeline_bg` | [CODE](modal_app.py:656) | 16 | 12288 | 1200 | The pipeline orchestrator. Runs `handler.handler`. retries=0, scaledown=45, memory_snapshot. Sets `PROMPTLY_RENDER_CORE_BUDGET=16`. POSTs completion to `/api/modal-complete`. |
| `render_burst` | [CODE](modal_app.py:1024) | 32 | 65536 | 1200 | DARK-flag `PROMPTLY_RENDER_BURST` (LIVE per notes). Runs `handler.render_stage` in its own container; reconstitutes work_dir from S3 (`_extract_workdir_from_s3`), rebuilds CostMeter+PremiumContext, drains ProgressivePublisher in `finally`. Sets core budget=32. retries=0. |
| `render_chunk_fanout` | [CODE](modal_app.py:904) | 16 | 32768 | 1200 | DARK-flag `PROMPTLY_RENDER_FANOUT`. Renders ONE Remotion chunk (composition + frame range) via `render-full.mjs`, uploads ProRes .mov to S3. Never raises (returns `{ok:False,error}`). No gemini secret. |
| `PromptlyPrewarmWorker` (`prewarm`) | [CODE](modal_app.py:1325) | (default) | 4096 | 300 | S3→Volume warm; scaledown=600, region us-west. Scales to zero. |
| `PromptlyValidator` (`validate`) | [CODE](modal_app.py:1370) | 4 | 2048 | 60 | Pre-upload talking-head face check. |
| `PromptlyDiagnoseUpload` (`diagnose`) | [CODE](modal_app.py:1422) | 2 | 1024 | 30 | Live S3 upload-state inspector. |
| `cancel_call` | [CODE](modal_app.py:1470) | 0.25 | 512 | 60 | THE money fix: `FunctionCall.from_id(call_id).cancel(terminate_containers=True)`. HMAC-auth via `MODAL_CALLBACK_SECRET`. Reaper (content-studio, no Modal creds) calls this endpoint. |
| `rife_normalize_remote` | [CODE](modal_app.py:1530) | 4 (H100) | 16384 | — | DEAD CODE per modal_app.py:1170 (CPU-only worker; no RIFE on crit path). |
| `prewarm_janitor` | [CODE](modal_app.py:1622) | 2 | 4096 | — | cron cleanup. |
| `generate_test_images_remote`, `gen_floor_compare_remote`, `validate_genscene_schema_remote`, `probe_veo_reachable`, `probe_partial_state`, `probe_multi_concat`, `cert_*` (~20 fns, lines 1694–3239) | | 2–32 | 2–65GB | | Test/cert/probe harness fns demoted from cpu=64/128GB to cpu≤8/32GB (COST de-risk 2026-07-28); flagged to move to `certs_app.py`. |

Deploy-state guard `validate_deploy_probe` [CODE](modal_app.py:2557) asserts fixed classes didn't regress on deploy.

Container handoffs: `PromptlyWorker.run_job` → **spawn** → `run_pipeline_bg` → (burst LIVE) **Function.from_name** → `render_burst` (returns `_rs` + `cost_delta`); (fanout DARK) `run_pipeline_bg` → `render_chunk_fanout` per chunk (S3 ProRes handoff). Completion leaves the worker by HTTP POST to `/api/modal-complete` [CODE](modal_app.py:849) AND the durable Supabase write inside `handler` [CODE](handler.py:38919).

### D19. What's written to the DB, when; terminal-once guarantee

Single writer: `write_job_status(job_id, *, status, phase, progress, result, partial_state, render_frames, progress_at)` [CODE](handler.py:30703). Synchronous, fail-open, no-op unless `_job_status_enabled()`. Table default `jobs`, overridable by `PROMPTLY_JOB_TABLE`/`PROMPTLY_JOB_STATUS_COLUMN` (content-studio side = `video_jobs`).

Guards that make terminal-once hold:
- **Terminal set**: `_terminal = status in ("completed","failed","canceled","needs_input")` [CODE](handler.py:30725).
- **First-terminal-wins** [CODE](handler.py:30741-30746): once `job_id in _JOB_TERMINAL_SEEN`, later NON-terminal writes drop status/phase/progress (a late daemon "processing" can't regress "completed"). Terminal re-write (needs_input→completed) still lands.
- **Monotonic progress** [CODE](handler.py:30747-30752): non-terminal progress ≤ high-water is dropped.
- **Hard-terminal DB fence** [CODE](handler.py:30790-30794): the UPDATE carries `.not_.in_(status_col,("failed","canceled"))` — a DB-side predicate so NOTHING lands on an already failed/canceled row even from another writer/container. Zero matched rows logged `[job-status] fence declined`.
- **Canonical vocabulary** [CODE](handler.py:30719-30724): only `queued/processing/completed/failed/canceled/needs_input` — the old `complete` spelling bounced off `valid_status` (check 23514) and PostgREST dropped the WHOLE patch atomically (root cause of terminal payloads never landing).

Terminal writes (exactly one of these fires per job):
- Missing fields [CODE](handler.py:34926) → `failed` `MISSING_FIELDS`.
- Tier concurrency [CODE](handler.py:34955) → `failed` `TIER_CONCURRENCY`.
- Success [CODE](handler.py:38919) → `completed`, carrying `video_url,hls_manifest_url,clean_export_key,edit_recipe,transcript,analysis_data,resolved_broll,stage_timings,post_package,floor_markers,vocab,capability_notes,tier,model,...` (explicit allowlist — unknown keys stripped by content-studio).
- Failure [CODE](handler.py:39045) → `failed`, carrying `error_code,error_subcode,error_cause,user_message,retryable,designed_rejection,error_class,error_detail,error_where,stage_timings(partial),floor_markers`.
- Minimal-route (`_MinimalRouteSignal`) [CODE](handler.py:38988] → `_run_minimal_pipeline` writes its own terminal.
- Outer safe-rescue [CODE](handler.py:39013] → inner run writes its own terminal; only falls through to the failure envelope on None.

Progress (non-terminal): `send_progress` [CODE](handler.py:32715) fires async `_async_job_status(status="processing",...)` [CODE](handler.py:30803) on a daemon thread + POSTs `/api/modal-progress` (3s timeout, fire-and-forget) + `_persist_step_token`. Render heartbeat `write_job_status(phase="render",progress=...)` [CODE](handler.py:32820-32852) writes `render_frames`/`progress_at` (the honest frozen-render watchdog signal). Progressive-preview writes land under `video_jobs.preview`.

[MEASURED] telemetry PERSISTENCE GAP (see E23): `gemini_call` and `gemini_tokens` inside the delivered `stage_timings` are 0/null on 129/129 recent completed jobs carrying the keys (p50/p90/max all 0), despite `edit_plan` p50 14.4s — corroborating the open "delivered completion carries a DIFFERENT stage_timings than the one written" suspicion flagged in [CODE](modal_app.py:820-831) ("0/125 on traffic").

### D20. Silent-death points — job can die leaving the user NOTHING and NO error

Enumerated (each = a path where no terminal `failed` row + no delivery):
1. **Completion POST fails AND Supabase terminal write disabled/failed.** `run_pipeline_bg` POST to `/api/modal-complete` is best-effort [CODE](modal_app.py:867-869); if it throws, recovery relies on the dispatch Supabase fallback + reaper. If `_job_status_enabled()` is false, `write_job_status` no-ops [CODE](handler.py:30717) → the durable terminal never lands and the completion POST is the only channel. [INFERRED] silent if both fail.
2. **Stalled spawn billed to timeout with no row until reaper.** `run_pipeline_bg` timeout=1200 [CODE](modal_app.py:651); "Nothing cancels a stalled spawn — the reaper only writes the DB row ~5min AFTER Modal's timeout kills the container". Between stall and reaper the row shows in-flight with nothing delivered. `cancel_call` [CODE](modal_app.py:1470) is the mitigation but is reaper-driven.
3. **SIGTERM/preemption before terminal write.** `run_pipeline_bg` retries=0 [CODE](modal_app.py:651); a preemption after render but before `write_job_status` loses the terminal (the shutdown handler flushes the ledger but does not write a completed row). `PromptlyWorker` has retries=2 but only guards the dispatcher leg, not the spawned pipeline.
4. **Hard-terminal fence declines a legit write.** If a row was set `canceled`/`failed` by another writer (e.g. a post-cancel race), the completed write matches 0 rows and is silently swallowed [CODE](handler.py:30790-30794) — logged, not surfaced to user. By design, but a mis-cancel strands the user.
5. **Fail-open swallow on write exception** [CODE](handler.py:30795-30796): any Supabase exception during the terminal write is caught and printed ("fail open") — the user sees no state change.
6. **SILENT completion (status=completed, zero events).** `_count_recipe_events(sanitized_recipe)==0` [CODE](handler.py:38912) delivers a "completed" video that is effectively a passthrough (no cuts/emphasis) — corpus-captured but delivered as success (not an error, but nothing was done). Not a death, but the "nothing happened" class.
7. **Progressive preview left servable as terminal.** Mitigated: `_drain_progressive_publisher` runs in `finally` on every exit [CODE](handler.py:39136) and inside `render_burst.finally` [CODE](modal_app.py:1139) so a preview is never left as the terminal state; a crash BEFORE the finally would be the residual window.
8. **`edit_plan["_lang_bundle"]` / underscore-prefixed fields stripped** [CODE](handler.py:38822-38829): not a death, but data written with a leading underscore is silently dropped by the recipe sanitizer (persisted on 0/3000 rows) — the silent-persistence-loss class Rule 2 warns about.

---

## SECTION E — Model calls

### E21. Every LLM/model call the pipeline makes

Editorial model constants [CODE](handler.py:108-109): `GEMINI_MODEL = GEMINI_EDITORIAL_MODEL = "gemini-3.1-pro-preview"`. Image model [CODE](handler.py:10182): `_IMAGE_MODEL = "gemini-3-pro-image"` (Nano Banana Pro). Client = Vertex (`vertexai=True`) [CODE](handler.py:1852); client timeout 480s [CODE](handler.py:1814 `_get_genai_client`).

| # | Call | file:line | model | input | output | crit-path | failure behavior |
|---|---|---|---|---|---|---|---|
| 1 | **Deepgram transcribe** (file) | [CODE](handler.py:4645) `_transcribe_deepgram_file` (+URL variant) | Nova-3, `language="multi"`, filler_words on | 48kHz mono FLAC [CODE](handler.py:4164) | words[] + speakers + detected_lang | YES (pool `transcribe`) | retriable classifier [CODE](handler.py:4441); ElevenLabs Scribe upgrade only if Deepgram coverage fails the gate [CODE](handler.py:4518) fail-safe. 0 words → RuntimeError "No speech" [CODE](handler.py:38413) unless render_only. |
| 2 | **MAIN editorial (post-cuts)** | [CODE](handler.py:12234) `_call_gemini_post_cuts` via `_gemini_stream_with_cache` [CODE](handler.py:12279) | gemini-3.1-pro-preview | video part + kept-only transcript + signals; PostCutPlan schema | PostCutPlan JSON (visual placement) | YES (the long pole) | degen guard + retries (E25). |
| 3 | **Transitions sub-call** | [CODE](handler.py:11841) `_call_transitions_subcall`, invoked [CODE](handler.py:14772) | gemini-3.1-pro-preview | plan-read + seam block; per-seam room-gated anyOf schema | `cut_boundary_transitions[]` + `tight_boundary_overlays[]` | YES when seams>0 (skipped if 0) | non-streaming `generate_content` [CODE](handler.py:11847); dict-tolerant. |
| 4 | **Language ID** | [CODE](handler.py:5187) `_identify_language_gemini` | GEMINI_MODEL | FLAC audio Part [CODE](handler.py:5205) | detected language | Stage-A routing (TIER-1) | thinking model, no cap. |
| 5 | **Transcript correction** | [CODE](handler.py:24453) `_gemini_correct_transcript` | GEMINI_MODEL | audio bytes | corrected token text (caption alignment) | conditional | fail-open. |
| 6 | **Plan diff (re-edit)** | [CODE](handler.py:18212) `generate_plan_diff` @[CODE](handler.py:18464) | GEMINI_MODEL, `thinking_level="HIGH"` [CODE](handler.py:18482) | old_plan + change_request | classified diff (tweak/guided_redraft/reinterpret) | YES for re-edit modes | non-streaming. |
| 7 | **Re-edit validation** | [CODE](handler.py:18759) `validate_reedit_changes` @[CODE](handler.py:18851) | GEMINI_MODEL | prior vs new plan | validation verdict | re-edit | non-streaming. |
| 8 | **B-roll visual pick** | [CODE](handler.py:19863) `fetch_broll_clip` @[CODE](handler.py:20182) | GEMINI_MODEL, `thinking_budget=256` [CODE](handler.py:20204) | Pexels candidate frames | chosen clip | render-time (broll) | drops cutaway on fail (face default). |
| 9 | **B-roll content verify** | [CODE](handler.py:20485) `_verify_broll_content` @[CODE](handler.py:20561) | GEMINI_EDITORIAL_MODEL, `thinking_budget=0` [CODE](handler.py:20565) | clip frames | relevance/safety verdict | render-time | rejects grids/watermarks. |
| 10 | **Pexels search** (not LLM) | [CODE](handler.py:19908) `_search_pexels` | Pexels API | keyword | 15 portrait video candidates | render-time | `PEXELS_API_KEY` unset → skip [CODE](handler.py:19897). |
| 11 | **Image generation** | [CODE](handler.py:10259) `_generate_image` @[CODE](handler.py:10298) | gemini-3-pro-image (Nano Banana Pro) | prompt + ref images | PNG still | PREMIUM only (GeneratedScene) | inert (model not told the type exists). |
| 12 | **Scene QA judge** | [CODE](handler.py:10773) `_qa_judge_generated_scenes` @[CODE](handler.py:10810) | GEMINI_MODEL, `_SceneQAReport` schema | rendered scene | pass/fail + reason | PREMIUM QA loop | perturb+regen [CODE](handler.py:10928). |
| 13 | **Hero-asset QA judge** | [CODE](handler.py:11005) `_qa_judge_hero_asset` @[CODE](handler.py:11015) | GEMINI_MODEL, `_HeroAssetScore` | PNG | pass/fail | PREMIUM | — |
| 14 | **Minimal-route hype** | [CODE](handler.py:32127) `_run_minimal_pipeline` @[CODE](handler.py:32229),[CODE](handler.py:32347) | GEMINI_EDITORIAL_MODEL, `HypePlan` schema, `thinking_budget=8192` | transcript | minimal caption/hype plan | zero-reject fallback | the safe-edit floor. |
| — | **Veo** | [CODE](modal_app.py:1932) `probe_veo_reachable` | Veo | — | — | NOT on crit path | probe only (404 per memory). |

[MEASURED] latency: `edit_plan` stage (dominated by call #2) p50 14.4s / p90 31.1s / max 80.8s (n=129). Deepgram/proxy/faces are subsumed under the pool; per-call Deepgram latency is not separately persisted → [UNKNOWN] exact, but `normalize_transcribe_upload` p50 18.8s bounds transcribe+normalize+upload together.

### E22. The MAIN editorial call — exact request contents

`_call_gemini_post_cuts(client, system_instruction, user_content, video_part, model_name, recipe_deadline_s, media_res_override, source_duration_s, n_words)` [CODE](handler.py:12234), executed via `_gemini_stream_with_cache` [CODE](handler.py:12279).

- **Streaming**: YES — `client.models.generate_content_stream(...)` [CODE](handler.py:11423), consumed chunk-by-chunk with early degen abort.
- **contents** = `[video_part, user_content]` [CODE](handler.py:12281).
- **system_instruction**: built by `_build_post_cuts_prompt` [CODE](handler.py:5683) ("SECOND call — visual placement on a kept-only transcript"). Passed via the CACHE (see E23), else inline [CODE](handler.py:11404). Signals embedded in prose: shot_changes, vocal_emphasis, source_loudness, face_visibility, speaker_positions, off_center, shot_scale, user_style_profile, trend guide, (guided_redraft: prior_plan + change_request).
- **user_content**: the kept-only transcript renumbered `[0..M-1]` + the per-job signal blocks.
- **video attachment** [CODE](handler.py:13279-13300): a `types.Part` with `file_data=FileData(file_uri=video_reference_url, mime_type="video/mp4")` — **REFERENCE, not inline** (the job's ONE uploaded proxy referenced, not re-sent). Inline `Blob(data=inline_video_bytes,...)` is armed as FALLBACK [CODE](handler.py:13283). `video_metadata=VideoMetadata(fps=_sample_fps)` where `_sample_fps` = `PROMPTLY_PROXY_SAMPLE_FPS` default **18** [CODE](handler.py:13272). Proxy is 480p@18fps [CODE](handler.py:13266). Resolution to the model set by `media_resolution` = `MEDIA_RESOLUTION_MEDIUM` (default) [CODE](handler.py:12316).
- **response schema**: `response_json_schema=_post_cuts_response_schema()` [CODE](handler.py:12300) (PostCutPlan + injected zoom anyOf — Section F). `response_mime_type="application/json"`.
- **thinking_budget**: `24576` (env `PROMPTLY_POST_THINKING_BUDGET`) via `ThinkingConfig` [CODE](handler.py:12305-12310).
- **max_output_tokens**: `40000` (SHARED thinking+output cap) [CODE](handler.py:12298). `temperature=1.0` [CODE](handler.py:12283).
- **abort_over_output_tokens**: `16000` (degen cutoff, Lever 1) [CODE](handler.py:12323).

### E23. Context caching

USED — explicit system-instruction cache. `_get_or_create_gemini_system_cache(client, model, system_instruction)` [CODE](handler.py:10034): `client.caches.create(config=CreateCachedContentConfig(system_instruction=..., ttl="3600s"))` [CODE](handler.py:10068). Passed as `cached_content=cache_name` [CODE](handler.py:11402); on cache-miss error it retries WITHOUT cache (inline system_instruction).

- **Cache key** = `_gemini_cache_key(model_name, system_instruction)` [CODE](handler.py:10040) → keyed on (model, hash(system_instruction)). Registry `_GEMINI_CACHE_REGISTRY` per-container [CODE](handler.py:9990) + a cross-container **Modal Dict** `_SHARED_CACHE_DICT` [CODE](handler.py:10025) so a fresh container reuses an existing server-side cache (kill switch `PROMPTLY_SHARED_GEMINI_CACHE=0`). TTL 3600s, renews on use.
- **Cached = the system_instruction prefix only**; the video part + user_content + response schema are UNCACHED per call.
- **Fragmentation**: the cache fragments whenever `system_instruction` TEXT differs. It differs by: the `PROMPTLY_DWELL` prose swap [CODE](handler.py:12167), `PROMPTLY_LEAN_SCHEMA`/`PROMPTLY_LEAN_DECOR_GROUND` (change the prompt text), the DWELL/why-diet arms, language routing (Stage A monolingual), and guided_redraft/reinterpret injections. Each distinct prompt text → its own cache entry. The RESPONSE SCHEMA is NOT in the system cache, but a schema change busts the Vertex cache key too [CODE](handler.py:12208-12211). [INFERRED] distinct cache entries in a normal day ≈ small (the base prompt is static per deploy; A/B arms + language routes multiply it), likely single digits to low tens — not directly countable from the DB.

[MEASURED] token split — DB `result.stage_timings.gemini_tokens` `{prompt,cached,output,uncached_delta,n_calls}`:
- Across 500 recent completed jobs only **9 carried non-null gemini_tokens** (all clustered 2026-08-08 10:45–11:16). The other ~273 jobs with `plan>0`, and **129/129 that carry the key, show `gemini_call=0` and `gemini_tokens=null`** (p50/p90/max = 0). This is a real telemetry-persistence gap ([CODE](modal_app.py:820-831) "0/125 on traffic"; `_gemini_token_summary` returns None when `_GEMINI_CALL_LOG` has no non-aborted entries [CODE](handler.py:11105), and the sole append site is the streaming helper [CODE](handler.py:11520) — non-streaming re-edit/minimal paths never populate it). [INFERRED] cause: recent completed jobs deliver via non-streaming Gemini wrappers (plan-diff/minimal/render_only) OR a streaming-append regression; a clean mode-cut couldn't be taken (no `mode` column in `video_jobs`).
- From the 9 jobs where it landed [MEASURED]: median **prompt 55,872**, **cached 42,192**, **output 1,461**, **uncached_delta 14,062**, n_calls median 1 (one job n_calls=2). So the cached system prefix ≈ **42K tokens**, and per-call BILLED input (prompt−cached, incl. video + user content + response schema) ≈ **14K tokens**. Example row: `{prompt:134478, cached:84396, output:4439, n_calls:2, uncached_delta:50082}` (a 2-call job).

### E24. Thinking budget

- Value: **24576** for the main post-cuts call [CODE](handler.py:12305-12310), env-overridable via `PROMPTLY_POST_THINKING_BUDGET` (DARK A/B dial, default 24576 = byte-identical).
- History: lowered from a **60000** cap [CODE](handler.py:12239-12245) — "60K bought no quality... drove the model to spiral past its output budget into an empty response. Thinking LESS is the fix." (`_get_genai_client` timeout deliberately left alone.)
- Other calls set their own budgets: plan-diff `thinking_level="HIGH"` [CODE](handler.py:18482); b-roll pick `thinking_budget=256` [CODE](handler.py:20204); b-roll verify `thinking_budget=0` [CODE](handler.py:20565); minimal hype `thinking_budget=8192` [CODE](handler.py:32235); scene QA `thinking_budget=8192` region.

### E25. Aborts / retries / degrade paths around the main call

All in `_call_gemini_post_cuts` [CODE](handler.py:12256-12531):
- **`_DEGEN_EXTRA_RETRIES = 2`** [CODE](handler.py:12273) on top of **1 standard transport retry** (`_attempt < 2`) [CODE](handler.py:12502). A repetition loop draws from the +2 degen budget so two loops can't exhaust to safe-edit.
- **Degeneration triggers** [CODE](handler.py:12350-12388): empty/None; stream aborted (shape-abort OR 16k-token cutoff); output tokens > 16000 (`_POST_CUTS_DEGEN_OUTPUT_TOKENS`); unparseable JSON; **outcome-gate** strict PostCutPlan re-validation (`PROMPTLY_OUTCOME_GATE` shadow|enforce|off) [CODE](handler.py:12428-12446); **out-of-range plan** (zoom points past source EOF) → regenerate [CODE](handler.py:12485-12494).
- **Lever 1 streaming early-abort** [CODE](handler.py:11492): stops consuming the moment running output crosses 16k tokens (catches spiral at ~200s instead of ~400s to the 40k cap).
- **DEGEN-LEVER-A shape abort** [CODE](handler.py:11418-11481): in-stream phrase-period/repetition autocorrelation catches runaway prose thousands of tokens sooner (`ABORTED@shape`).
- **Recipe wall-clock budget** [CODE](handler.py:12509): once past `recipe_deadline_s`, stop re-rolling → hand off to the deterministic safe edit (delivered simpler video) rather than grind to the Modal SIGKILL.
- **notes soft-cap** (80w/600c, trim-in-place not re-roll) [CODE](handler.py:12458); `_enforce_string_caps` at parse edge [CODE](handler.py:12406).
- **Exhaustion** [CODE](handler.py:12523-12524): `raise RuntimeError("...degenerate after retry...")` → the repair loop's transport-exhaustion path engages the safe edit.

[MEASURED] fire rate: `degen_retries` total = **0** across 500 completed; `gemini_wasted_degen>0` in only **2/500**; `n_calls>1` in **1/9** of the jobs that persisted the counter. Caveat: these counters share the same persistence gap as E23, so the true rate is [UNKNOWN] — but on the cohort where it landed, degen/retry is rare (~2/500 aborted-time, ~1 multi-call).

---

## SECTION F — Output schema

### F26. The FULL emitted response schema (PostCutPlan)

Built by `_post_cuts_response_schema()` [CODE](handler.py:12177): `PostCutPlan.model_json_schema()` with the zoom claim-anyOf injected at `$defs/_EmphasisMoment.properties.zoom_effect`, then why-diet / lean-schema / schema-pad surgery applied.

`PostCutPlan` shape [CODE](handler.py:1617-1705):
```
video_identity: str(≤500)
existing_caption_region: "none"|"bottom"|"top"|"other" = "none"
source_text_regions: Optional[List["top"|"center"|"bottom"]]
video_plan: _VideoPlan {                                   # scaffold, mostly NOT rendered
  what_happens: str(≤500), hook_word_index:int, payoff_word_index:int, close_word_index:int,
  key_moments: List[_VideoPlanMoment {word_index, what_lands(≤240), why_emphasis(≤240),
                                       what_i_saw(≤240), viewer_feeling(≤200)}],
  story_shape: str(≤500),
  arc_segments: List[_ArcSegment {start_word_index, end_word_index, position:_ArcPosition, intensity:float}],
  movements: List[_Movement {start_word_index, end_word_index, job(≤240),
                             energy:"hot"|"deep"|"calm", lead_instrument:..., captions:"run"|"rest"}],
  editorial_vision: str(≤800) }
caption_style: _CAPTION_STYLES                             # Literal from VALID_CAPTION_STYLES
caption_keywords: List[str(≤120)]
emphasis_moments: List[_EmphasisMoment {
  word_indices: List[int], type:"punchline"|"statement"|"question"|"reaction"|"revelation",
  intensity:"high"|"medium", duration:float, viewer_feeling(≤200),
  zoom_effect: Optional[<injected per-arc anyOf, see F27>],
  motion_graphic: Optional[_EmphasisMotionGraphic {type:_MG_TYPES, anchor:_SEMANTIC_ANCHOR, props:Dict}],
  sound: _SOUND_DECISION }]                                 # REQUIRED
motion_graphics: List[_MotionGraphic {type:_MG_TYPES, why?, start_word_index, end_word_index,
                                      duration_seconds?, anchor:_SEMANTIC_ANCHOR, props:Dict}]
text_overlays: List[_TextOverlay {variant:"sticky_note"|"caption_match", why?, start_word_index,
                                  duration_seconds, topText?/bottomText?/notes?/quote?/attribution?/text?,
                                  position?:"top"|"center"}]
broll_clips: List[_BrollClip {keyword(≤200), start_word_index, end_word_index, reason(≤240),
                              entry_transition?:"LightLeak"|"ShutterFlash", exit_transition?}]
generated_scenes: List[_GeneratedScene] = []               # INERT (model not told)
cut_refinements: List[_CutRefinement {start_word_index, end_word_index, reason(≤240)}] = []
preserved_silences: List[int] = []
caption_position_changes: List[_CaptionPositionChange {word_index, position:"top"|"center"|"bottom"}]
thumbnail_word_index: int
audio_denoise: bool
outro: "none"|"fade_black"|"fade_white"
aspect_ratio: "9:16"
notes: Optional[str(≤800)]
edit_rationale: Optional[str(≤400)]                        # narrative, not rendered
post_caption: Optional[str(≤120)]                          # narrative
post_hook: Optional[str(≤60)]                              # narrative
```
[INFERRED] token size of the emitted schema: the SCHEMA-PAD probe [CODE](handler.py:12201-12211) notes a proposal to move "1,269 tok" of `_MotionGraphic.props` typing; typical PostCutPlan JSON output is stated as 2–4K tokens [CODE](handler.py:12249). The schema itself (all `$defs` + zoom anyOf) is on the order of ~2–4K tokens of the ~14K uncached input delta [INFERRED] (the rest is video + user content).

### F27. Every enum + source (special attention to per-position/per-context tables)

Registry-derived Literals (single source `type_registries.py`):
- **`_CAPTION_STYLES`** [CODE](handler.py:831) ← `VALID_CAPTION_STYLES` [CODE](type_registries.py:29): `Prime, TypewriterReveal, Cove, Lumen, Pulse, Quintessence, TwoTone, CleanCut, Gadzhi, none` (9 real + "none" sentinel).
- **`_TRANSITION_TYPES`** [CODE](handler.py:832) ← `VALID_TRANSITION_TYPES` [CODE](type_registries.py:43): `CardSwipe, ZoomThrough, SlideOver, Stack, CrossfadeZoom, ShutterFlash, StepPush, FilmStrip, DipToBlack` (9). NOTE: DELETED from PostCutPlan; authored only by the transitions sub-call.
- **`_TCO_TYPES`** [CODE](handler.py:833) ← `VALID_TIGHT_CUT_OVERLAYS` [CODE](type_registries.py:58): `LightLeak, ShutterFlash` (2).
- **`_ZOOM_TYPES`** [CODE](handler.py:834) ← `VALID_ZOOM_TYPES` [CODE](type_registries.py:99): `SmoothPush, SnapReframe, FocusWindow, StepZoom, LetterboxPush, DepthPull, StagedPush` (7).
- **`_MG_TYPES`** [CODE](handler.py:1143) ← `VALID_MG_TYPES` [CODE](type_registries.py:109): 30 types (AnnotationArrow…MouseDrag; IconLabel DELETED).
- GenScene: `_GENSCENE_BG_KINDS` `gradient|solid|generated`, `_GENSCENE_ENTRANCES` `slide|scale|float|fade|rise`, `_GENSCENE_EASINGS` `spring|ease|linear` [CODE](type_registries.py:129-131).
- **`_SEMANTIC_ANCHOR`** [CODE](handler.py:1147): `upper_third_safe|center|lower_third_safe`.
- **`_TEXT_OVERLAY_VARIANTS`** [CODE](handler.py:1150): `sticky_note|caption_match`.
- **`_SFX_SOUNDS`** [CODE](handler.py:1160): 14 sound stems (`boom, punchsfx, swoosh-sound-effects, woosh-professional, transition-sfx, camera-flash, money-ching, iphoneding, mouse-click-sound, popsfx, rizz, shockingsfx, awkward-moment, wompwomp, imposter`).
- **`_SOUND_DECISION`** [CODE](handler.py:1172): the 14 sounds + **`voice`** (the signed bare choice). This is the REQUIRED `emphasis_moment.sound` enum.
- Inline literals: `_EmphasisMoment.type` (punchline/statement/question/reaction/revelation), `.intensity` (high/medium); `_ArcPosition` (hook/build/mid_peak/payoff/breather/close); `_Movement.energy` (hot/deep/calm), `.lead_instrument` (kinetic_captions/annotation/takeover_graphic/clean_frame), `.captions` (run/rest); `outro` (none/fade_black/fade_white); `aspect_ratio` (9:16 only); `existing_caption_region` (none/bottom/top/other); caption/overlay `position` literals.

**PER-POSITION / PER-CONTEXT restriction tables (the "silently-impossible-output" class):**
1. **`ZOOM_ARC_HOMES`** [CODE](handler.py:858-875) — THE table. Injected as a static anyOf via `_zoom_claim_variants()` [CODE](handler.py:11913) into `emphasis_moments[].zoom_effect` [CODE](handler.py:12188). Each variant pins `arc_position` (const) → an allowed `type` enum:
   - `hook`: DepthPull, SnapReframe, StepZoom, SmoothPush
   - `mid_peak`: FocusWindow, SnapReframe, StepZoom, StagedPush, SmoothPush
   - **`payoff`: LetterboxPush, SmoothPush ONLY** (SnapReframe added ONLY under DARK `PROMPTLY_PAYOFF_PUNCHY` [CODE](handler.py:11940))
   - `close`: SmoothPush, SnapReframe, StepZoom
   - `build`/`breather`: SnapReframe, StepZoom ONLY (mask form; durationMs ≤ 1000, scale ≤ mask max [CODE](handler.py:11950-11951))
   This is the documented case where a class of output is structurally unreachable: a **punchy payoff zoom is unrepresentable** (payoff enum = slow pair only) — confirmed 0/253 production payoffs punchy [CODE](handler.py:11897). `StagedPush` is sayable ONLY at mid_peak.
2. **Transitions sub-call room-gated enum** `_build_transitions_subcall_schema` [CODE](handler.py:11640-11648): per-seam, the `type` enum = ONLY transition types whose `TRANSITION_DURATION_FRAMES` fits the seam's usable-silence room. A seam with no fitting consuming type is offered ONLY as an overlay candidate. The sub-call `sound` enum is restricted to `transition-sfx|camera-flash` [CODE](handler.py:11648).
Import-time asserts guarantee `ZOOM_ARC_HOMES` tiles the zoom registry exactly [CODE](handler.py:891-897).

### F28. Prose vs schema agreement — every mismatch

- **Payoff zoom (ZOOM_ARC_HOMES)**: the base prompt PROSE tells the model "a snap reads as just another mid_peak" and describes the payoff as the slow committed push — this AGREES with the schema (payoff = LetterboxPush/SmoothPush). But it is a self-reinforcing restriction: the DWELL A/B [CODE](handler.py:12157-12164) and `PROMPTLY_PAYOFF_PUNCHY` exist precisely because prose+schema jointly make a punchy payoff impossible; whether that's a "promise the schema forbids" is a taste call (the prose does NOT promise a punchy payoff, so no direct mismatch — flagged as the intentional-restriction case, [CODE](handler.py:11901-11907)).
- **Transitions & tight_cut_overlays**: DELETED from PostCutPlan schema [CODE](handler.py:1649-1653) but the RESPONSE-FORMAT prose historically documented `_TightCutOverlay` [CODE](handler.py:1444-1449) — "the schema omitting it structurally forbade emission — Gemini would then CLAIM overlays in editorial_vision it could not emit." This IS a resolved prose↔schema mismatch (the [reconcile-overlays] re-ask papered over it every job); now single-owned by the sub-call. Residual: if the system_instruction still describes tight-cut overlays as authorable in the main call, that would be a live mismatch — the phrase list `TIGHT_CUT_OVERLAY_MECHANISM_PHRASES` [CODE](type_registries.py:81) still feeds the main prompt's HOW-TO section while the main schema cannot emit them (they ride broll `entry/exit_transition` only) → **partial mismatch: prose teaches overlay commitments the main schema cannot express**; caught downstream by the sub-call ownership.
- **`sound` on emphasis vs `_SFX_SOUNDS`**: `_SOUND_DECISION` adds `voice`; prose requires every beat to sign a choice — agrees.
- **`generated_scenes`**: schema permits (List default []) but the model is deliberately NOT told the type exists [CODE](handler.py:1664-1667) — prose omits it → never emitted (intentional, not a mismatch).
- **lean-schema arm**: when `PROMPTLY_LEAN_SCHEMA` on, the schema STRIPS `what_lands/why_emphasis/what_i_saw/viewer_feeling/reason` [CODE](handler.py:12093-12118) but the pydantic contract keeps them REQUIRED (backfilled "" [CODE](handler.py:12121)) — prose relocates that grounding to the thinking channel; consistent by construction.

### F29. Loosely-typed fields (schema constrains nothing) — where the real contract lives

- **`_MotionGraphic.props: Dict[str,Any]`** [CODE](handler.py:1316) and **`_EmphasisMotionGraphic.props`** [CODE](handler.py:1226): free-form. The real per-MG-type contract lives in the RENDER layer (`render_schemas.py` / `src/remotion/` component props) and the prompt prose — the schema enforces nothing. This is why the SCHEMA-PAD probe targets typing props [CODE](handler.py:12202-12203).
- **`_Transition` optional props** (`direction/palette/title/label/variant/accentColor/...`) [CODE](handler.py:1431-1443): free-form passthrough; contract in the renderer (but these are sub-call/EditPlan, not main PostCutPlan).
- **`_GenSceneBackground.colors`, `generation_prompt`** free strings; `_GenSceneTextLayer.content` constrained only by a PROSE contract ("only from a KNOWN INPUT — transcript or user string, NEVER model-invented") [CODE](handler.py:1372-1375), enforced at emission (Sub-step 5), not the schema.
- **`_TextOverlay` variant-specific fields** (topText/bottomText/notes/quote/attribution/text) are all `Optional` at the schema level; the per-variant required-field contract is enforced by a Python validator [CODE](handler.py:1285), not the schema.

### F30. Emitted-but-unread and read-but-never-emitted fields

**Emitted by the model but NOT consumed by the renderer (scaffolding / narrative only):**
- `video_plan.movements` [CODE](handler.py:1527-1534) — "Reasoning scaffolding ONLY... NOT consumed by the renderer (stays out of the PostCutPlan→EditPlan path)."
- `video_plan.arc_segments`, `story_shape`, `what_happens`, `editorial_vision`, `key_moments.*` — scaffolding that shapes the model's choices; `arc_segments`/claim honesty is measured by recipe_eval WARN, "never gated" [CODE](handler.py:840,922). `_VideoPlanMoment.what_i_saw/why_emphasis` are telemetry-only (the fields the lean schema drops [CODE](handler.py:12093)).
- `edit_rationale` [CODE](handler.py:1687-1693], `post_caption`/`post_hook` [CODE](handler.py:1694-1705] — "no renderer reads it"; persisted to `video_jobs` for the client, additive.
- `emphasis_moments[].viewer_feeling` / `_VideoPlanMoment.viewer_feeling` — grounding prose, no render consumer (dropped under lean schema).

**Read/handled downstream but the model NEVER emits (built by Python or a different call):**
- `edit_plan["transitions"]`, `edit_plan["tight_cut_overlays"]` — DELETED from PostCutPlan; authored by the transitions SUB-CALL [CODE](handler.py:14744,14794) or left `[]`. Downstream render reads them; the main model can't emit them.
- `remove_words` (EditPlan) — built mechanically by `compute_mechanical_cuts()` [CODE](handler.py:1717-1720), never a PostCutPlan output.
- `emphasis_moment.t`, caption_position_segments, zoom `startMs` — DERIVED by Python from word_indices/onsets [CODE](handler.py:1229,1194-1197,1204-1207); the model emits only word indices.
- `_face_transform`, `_face_trajectory`, `_lang_bundle`, `_clean_export_key` — pipeline-injected `_`-prefixed keys the renderer/exporter read; not model output (and `_`-prefixed ones are stripped from the persisted recipe [CODE](handler.py:38822-38829)).
- `generated_scenes` — schema-readable and renderer-capable, but the model never emits it today (inert) — the read-side exists with no emit-side.

---

### Cross-refs to standing rules touched
- Rule 2 (persist-or-it-didn't-happen): the gemini_tokens/gemini_call 0/null gap (D19/E23) is the same silent-persistence class the CANON warns about ([CODE](modal_app.py:820-831)).
- Zero-reject: `_MinimalRouteSignal` → `_run_minimal_pipeline` and the outer safe-rescue keep failures from reaching the user (D20 mitigations).
- Render determinism: `render_burst` core budget pinned to cpu ([CODE](modal_app.py:1033)); `_X264_ENCODE_THREADS` pinning is in handler render path (not re-verified here).
# Recon G/H/I — Toolbox, Usage Reality, Render Layer

Repo: `/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker` (branch `zero-reject-routing`).
All `[CODE]` cites are this repo unless noted. Worktree copies under `.claude/worktrees/` ignored (duplicates).

**Tag key:** `[MEASURED]` = DB/observed · `[CODE](file:line)` = read in source · `[INFERRED]` = reasoned · `[UNKNOWN]` = could not determine.

**Measurement window for all of Section H** `[MEASURED]`: the **3,949 most-recent `status=completed` `video_jobs`**, spanning **2026-06-25T22:01Z → 2026-08-10T02:12Z** (~46 days). Pulled via read-only PostgREST SELECT on `result` jsonb. Route split of the window: `__premium__` (no `result.route` key = premium/editorial pipeline) **2074**, `minimal_speech_uncut` **768**, `moodreel` **679**, `minimal` **374**, `hype` **54**. The full editorial toolbox (emphasis/sfx/captions/tight-overlays/broll/text-overlays) lives ONLY on the premium route; the four "lean" routes carry a stripped plan (clips+zoom+mg+transitions+outro only).

---

# SECTION G — TOOLBOX

## G31. Full component registry (every family)

Two schema seams govern the whole toolbox:
- **Recipe vocabulary** (what Gemini may emit) — frozensets in `[CODE](type_registries.py:29-131)`.
- **Render input** (what Remotion accepts) — Pydantic models in `[CODE](render_schemas.py:83-423)`, `extra="forbid"` base at `[CODE](render_schemas.py:83-84)`; TS mirror `src/remotion/src/types.ts`.
- Prompt menus that describe each family to Gemini are `===`-delimited sections inside the giant `system_instruction` f-string built by `_build_post_cuts_prompt` `[CODE](handler.py:5683)` (string opens `[CODE](handler.py:6041)`); transitions/tight-overlays are a **separate sub-call** `_TRANSITIONS_SUBCALL_SYS` `[CODE](handler.py:11591+)`.

### Family 1 — ZOOMS (7) — `VALID_ZOOM_TYPES` `[CODE](type_registries.py:99-107)`
Renders in **Remotion** for composite zooms (FocusWindow/LetterboxPush/DepthPull/StagedPush → `PromptlyMicroSegments`) and via ramp on the clip for others; per-clip pre-extracted `src` played frame-0 by the ABE zoom components. Render map `ZOOM_MAP` + `ClipRenderer` `[CODE](src/remotion/src/PromptlyRender.tsx:150-160)`; component dirs `src/remotion/src/zoom/{SmoothPush,SnapReframe,FocusWindow,StepZoom,LetterboxPush,DepthPull,StagedPush}`. Props contract: `ZoomEffectSpec`/`ZoomEventSpec`/`StageSpec` `[CODE](render_schemas.py:88-125)` (type, events[startMs,durationMs,scale,originX/Y], `punch` vibe-gate, StagedPush `stages`). Described to model in `=== EMPHASIS MOMENTS + ZOOM ===` `[CODE](handler.py:6591)`, roster header `THE 7 ZOOM TYPES` `[CODE](handler.py:6650)`, entries `[CODE](handler.py:6655-6669)`.
Names: SmoothPush, SnapReframe, FocusWindow, StepZoom, LetterboxPush, DepthPull, StagedPush. **Count = 7. All 7 render, all 7 offered.**

### Family 2 — MOTION GRAPHICS (26) — `VALID_MG_TYPES` `[CODE](type_registries.py:109-122)`
Renders in **Remotion** (`PromptlyOverlay` alpha leg). Type→component `MG_MAP` (26 keys) `[CODE](src/remotion/src/PromptlyRender.tsx:129-138)`, mounted at `[CODE](src/remotion/src/PromptlyRender.tsx:461)`. Props contract is generic: `MotionGraphicSpec{type,fromFrame,durationInFrames,props:Dict[str,Any]}` `[CODE](render_schemas.py:305-309)` (per-MG prop shapes live in each component's TSX, not the Python schema). Component exports `[CODE](src/remotion/src/motion-graphics/index.ts)`. Described in `=== MOTION GRAPHICS ===` `[CODE](handler.py:6431)`, roster `THE {26} COMPONENTS` `[CODE](handler.py:6469)`, entries grouped by `── WHEN … ──` subheads `[CODE](handler.py:6482-6583)`.
Names: AnnotationArrow, StatCard, Notification, ProgressBar, RecordingFrame, StickyNotes, ChatThread, TweetBubble, InstagramComment, IMessageBubble, TikTokComment, Timeline, Reticle, RankedList, PullQuote, PillCluster, Stamp, BarRace, SectionDivider, EditorialQuote, StepDivider, DropBanner, DropCard, PillMarquee, TimelineRoadmap, MouseDrag. **Count = 26.** (The 4 social cards TweetBubble/InstagramComment/IMessageBubble/TikTokComment all render from one file `SpeechBubble.tsx` `[CODE](src/remotion/src/motion-graphics/index.ts:15-28)`.)

### Family 3 — CAPTION STYLES (9 + `none`) — `VALID_CAPTION_STYLES` `[CODE](type_registries.py:29-41)`
Renders in **Remotion** (`PromptlyOverlay`), one component per style `src/remotion/src/captions/{Prime,TypewriterReveal,Cove,Lumen,Pulse,Quintessence,TwoTone,CleanCut,Gadzhi}`, registry `[CODE](src/remotion/src/captions/index.ts)`. Props: `CaptionSpec{style,pages,keywords,positionSegments,extraProps}` + `TikTokPage/TikTokToken` (integer ms) `[CODE](render_schemas.py:266-301)`. `none` = no-caption sentinel (render emits `caption=None`, not a style) `[CODE](render_schemas.py:360-363)`. Described in `=== CAPTIONS ===` `[CODE](handler.py:6329)`, per-style `Fits:`/`Fights:` `[CODE](handler.py:6347-6364)`. **Count = 9 real styles (+none).**

### Family 4 — TRANSITIONS (9) — `VALID_TRANSITION_TYPES` `[CODE](type_registries.py:43-47)`
CUT-BOUNDARY, handle-required. Renders in **Remotion** (`PromptlyMicroSegments`, per-layer pre-extracted `clipASrc`/`clipBSrc`). Props: `TransitionSpec` `[CODE](render_schemas.py:145-168)` (direction, palette, intensity, assetPath, flashColor, advanceFrames…). Component dirs + exports `[CODE](src/remotion/src/transitions/index.ts)`. Described in the separate sub-call `THE TRANSITIONS` header `[CODE](handler.py:11607)`, entries `[CODE](handler.py:11608-11616)`.
Names: CardSwipe, ZoomThrough, SlideOver, Stack, CrossfadeZoom, ShutterFlash, StepPush, FilmStrip, DipToBlack. **Count = 9.**

### Family 5 — TIGHT-CUT OVERLAYS (2) — `VALID_TIGHT_CUT_OVERLAYS` `[CODE](type_registries.py:58-60)`
TIGHT-BOUNDARY decoration over an unmodified hard cut, 11-frame/180ms window, no handle. Renders in **Remotion** (`PromptlyOverlay`, overlays dir `src/remotion/src/transitions/overlays/{LightLeakOverlay,ShutterFlashOverlay}.tsx`). Props: `TightCutOverlaySpec{atFrame,type,durationInFrames}` `[CODE](render_schemas.py:183-186)`. Described `THE TIGHT-CUT OVERLAYS` `[CODE](handler.py:11618)`, entries `[CODE](handler.py:11619-11620)`. Commitment-phrase detector `TIGHT_CUT_OVERLAY_MECHANISM_PHRASES` `[CODE](type_registries.py:81-97)`. Names: LightLeak, ShutterFlash. **Count = 2.**

### Family 6 — SOUND EFFECTS (15 + bare `voice`) — `_SFX_SOUNDS` Literal `[CODE](handler.py:1160)`, `_SOUND_DECISION` (+voice) `[CODE](handler.py:1172)`
Rendered by **FFmpeg** (mixed into the PCM audio pass, `amix`, at `[CODE](handler.py:28864-28872)`; assets `SFX_SOUNDS_DIR` `[CODE](handler.py:3085)`). Not a Remotion element. Described in `=== SOUND EFFECTS ===` `[CODE](handler.py:6673)`, roster `THE 16 SOUNDS + THE BARE VOICE` `[CODE](handler.py:6687)`, entries `[CODE](handler.py:6690-6720)`. Deterministic user-negative floor `_enforce_sound_negatives` `[CODE](handler.py:238)`.
Names: boom, punchsfx, swoosh-sound-effects, woosh-professional, transition-sfx, camera-flash, money-ching, iphoneding, mouse-click-sound, popsfx, rizz, shockingsfx, awkward-moment, wompwomp, imposter (+ `voice` = signed bare choice). **Count = 15 (+voice).**

### Family 7 — TEXT OVERLAYS (2 variants) — `TextOverlaySpec` discriminated union `[CODE](render_schemas.py:313-338)`
Renders in **Remotion** (`PromptlyOverlay`). Variants: `sticky_note` (`StickyNoteOverlay{notes[]}`) and `caption_match` (`CaptionMatchOverlay{text,position}`). Described `=== TEXT OVERLAYS ===` `[CODE](handler.py:6384)`. **Count = 2 variants.**

### Family 8 — B-ROLL — `_BrollClip` `[CODE](handler.py:1326)`, render `BrollSpec` `[CODE](render_schemas.py:190-196)`
Pexels stock cutaway that fully replaces the speaker. Renders in **Remotion** (`PromptlyOverlay` BrollLayer, own `src` URL). Not a fixed catalog — a **keyword-authoring task** (`{keyword, start_word_index, end_word_index, reason}`) into a Pexels search + downstream Gemini picker. Described `=== B-ROLL ===` `[CODE](handler.py:6723-6763)`; user-request obey path `_parse_broll_requests`/`_broll_request_directive` `[CODE](handler.py:250-285)`, spliced at `[CODE](handler.py:6098)`. **Count = unbounded (keyword-driven, not enumerated).**

### Family 9 — GENERATED SCENES — `GeneratedSceneSpec` `[CODE](render_schemas.py:245-262)`, dims `[CODE](type_registries.py:124-131)`
Composed premium graphic (background world → generated subject still → text → motion). `sceneType ∈ {typo_stat, hero_object, photo_card}`; subject still generated by `_generate_scene_subject` `[CODE](handler.py:10671)`. Renders in **Remotion** (`GeneratedSceneLayer`; standalone tool `lumen-reel-render.mjs` composition `LumenReel`). **Premium/Lumen-only + effectively INERT** (see H37). **Count = 3 scene types × enumerated bg/entrance/easing dims.**

### Family 10 — SPEED EFFECTS — per-cut/clip `speed` field
Not a component; a per-clip `playbackRate` on `ClipSpec` `[CODE](render_schemas.py:128-142)`. Standing law: every editorial cut renders 1.0x (feedback_no_speed_curve). Non-1.0 speed appears only on the `moodreel`/`hype` aesthetic routes (H35).

### Family 11 — COLOR EFFECTS — **REMOVED / DEAD**
`color_effect` field survives in the shared plan shape but is **force-set to None** `[CODE](handler.py:15893-15897)` ("color_effect was removed from the pipeline"); telemetry note "feature removed" `[CODE](handler.py:2979-2982)`. No render implementation. **Count = 0 live.**

### Family 12 — OUTRO — `OutroKind` `[CODE](render_schemas.py:342)`
`none | fade_black | fade_white`, rendered by **FFmpeg** fade `[CODE](ffmpeg_base.py:658-660)`. **Count = 3.**

**Family totals:** zoom 7 · MG 26 · captions 9(+none) · transitions 9 · tight-overlays 2 · SFX 15(+voice) · text-overlay variants 2 · outro 3 · genscene 3 types (dark) · color 0 (dead). Components carrying a bold `**FITS:**/**FIGHTS:**` fitness line = **59** (26 MG + 7 zoom + 15 SFX + 9 transition + 2 tight-overlay), per the fitness-line design `[CODE](handler.py:229-240)`; caption styles use the older lowercase `Fits:/Fights:` standard.

## G32. Selection guidance (verbatim FITS/FIGHTS the model receives)

Design: the 4-bucket `_VIBE_PALETTES` table was **RETIRED** (Zac 2026-07-13); selection is now EMERGENT from each component's own FITS/FIGHTS clause read against the free-text vibe `[CODE](handler.py:229-240)`. Verbatim clauses:

**ZOOMS `[CODE](handler.py:6655-6669)`**
- SmoothPush: `FITS: any vibe, leans calm/weighty/professional/story — the default lean-in for statements of weight and payoffs. FIGHTS: very fast/frenetic viral, where a slow 1.2s push drags against the pace — reach for a snap or step there.`
- SnapReframe: `FITS: viral, punchy, high-energy — punchlines and reactions. FIGHTS: calm, cinematic-smooth, story, corporate-composed — the hard snap is a shout.`
- FocusWindow: `FITS: any vibe when a detail AND its context genuinely matter at once — a specialty, gated by that need. FIGHTS: as a generic push; costume when there's no dual-view need.`
- StepZoom: `FITS: hustle, viral, rhythm-locked, beat-matched pacing. FIGHTS: calm, deliberate, cinematic, corporate — the jump-cuts read as jittery against a smooth register.`
- LetterboxPush: `FITS: cinematic, story, dramatic revelations and climaxes earning film weight. FIGHTS: casual, viral, educational — the bars are costume on an unearned beat.`
- DepthPull: `FITS: premium, story, cinematic intros and title-sequence/atmospheric reveals. FIGHTS: fast, punchy, casual — its slow 2.2s atmosphere kills pace and over-produces a plain beat.`
- StagedPush: `FITS: viral, punchy, high-energy — the stacked-climax punch. FIGHTS: corporate, calm, cinematic, educational, and ANY non-building moment — the escalating push over-dramatizes a composed beat and looks unprofessional on words that don't build.`

**MOTION GRAPHICS `[CODE](handler.py:6482-6583)`** (verbatim FITS/FIGHTS)
- StatCard: `FITS: any vibe — a quoted headline number lands anywhere… FIGHTS: nothing tonally — only wrong without a real quoted number.`
- ProgressBar: `FITS: educational, corporate, business — a quantitative arc. FIGHTS: cinematic, story — a UI bar breaks the mood; needs a real value + target.`
- BarRace: `FITS: MOMENT SHAPE — …the dialogue compares two-plus countable quantities head-to-head… business, educational, competitive, data-viral. FIGHTS: one bar toward a goal → ProgressBar; a single headline number → StatCard. cinematic, story, calm…`
- RankedList: `FITS: educational, listicle, business, viral "top 3". FIGHTS: cinematic, story — needs a genuinely ordered set.`
- StickyNotes: `FITS: casual, creative, brainstorm, vlog, educational — a hand-made texture. FIGHTS: formal-corporate, cinematic — scrappy notes clash with polish.`
- PillCluster: `FITS: viral, casual, social, educational tags. FIGHTS: cinematic, story, formal — tag pills read social/casual.`
- PillMarquee: `FITS: MOMENT SHAPE — …the speaker rattles off MANY related keywords/hashtags…6+ tags… viral, social, hype. FIGHTS: a small static popped-in group of 2–8 tags → PillCluster; an ordered ranked list → RankedList. corporate, cinematic, educational-precise…`
- DropBanner: `FITS: MOMENT SHAPE — …2–3 named points UNDER A STATED HEADER… educational, explainer, business listicle. FIGHTS: …contained floating-card version → DropCard; …→ Timeline; …→ StickyNotes; …→ RankedList. cinematic, story, calm…`
- DropCard: `FITS: educational, explainer, business — the cleaner card variant. FIGHTS: cinematic, story, calm — same instructional read.`
- PullQuote: `FITS: viral, punchy, motivational, bold — a full-frame caps takeover is inherently loud. FIGHTS: corporate, cinematic, story, educational…`
- TweetBubble: `FITS: any vibe — a REAL quoted tweet in the story is the gate… FIGHTS: as non-diegetic decoration where no tweet is referenced; …only *discourages*…never blocks a genuine reference.`
- InstagramComment: `FITS: any vibe — a real quoted IG comment is the gate… FIGHTS: as decoration where no such comment exists…never suppresses a genuine reference.`
- TikTokComment: `FITS: any vibe — a real quoted TikTok comment is the gate… FIGHTS: as decoration…never blocks a genuine reference.`
- IMessageBubble: `FITS: any vibe — a real quoted text message is the gate… FIGHTS: as decoration…`
- ChatThread: `FITS: any vibe — a real multi-message exchange is the gate… FIGHTS: as decoration…never blocks a genuine exchange.`
- Notification: `FITS: any vibe — a real phone event (paid/texted/called) is the gate… FIGHTS: as non-diegetic decoration; only *discourage* in cinematic/formal-corporate…`
- EditorialQuote: `FITS: professional, educational, documentary, premium/story. FIGHTS: viral, casual, hype — the serif quote reads formal/literary.`
- RecordingFrame: `FITS: any vibe that explicitly invokes raw-take/BTS/leaked-footage energy… FIGHTS: clean produced talking-head — reads as costume regardless of vibe (most videos don't earn it).`
- MouseDrag: `FITS: educational, product/SaaS demo, tutorial, tech — a drag action is the gate. FIGHTS: cinematic, story, non-demo…`
- Stamp: `FITS: viral, punchy, bold, product-launch. FIGHTS: cinematic, story, understated-corporate — the slam is theatrical.`
- Timeline: `FITS: MOMENT SHAPE — …ordered stages of ONE journey, named but UNDATED…2–5 named steps… educational, explainer, business, how-to. FIGHTS: …TIME labels/scenic path → TimelineRoadmap; …→ StepDivider; …→ ProgressBar; unordered → StickyNotes/RankedList. viral-fast, cinematic…`
- TimelineRoadmap: `FITS: MOMENT SHAPE — …phased roadmap whose stages carry TIME sublabels…3–5 stations. business, educational, planning/startup. FIGHTS: …NO dates → Timeline; …→ ProgressBar. viral-fast, cinematic, casual…`
- StepDivider: `FITS: MOMENT SHAPE — …the script advances through a NUMBERED sequence and ANNOUNCES its position… educational, how-to, tutorial, training. FIGHTS: …whole process at once → Timeline; …→ SectionDivider. cinematic, story, casual-viral…`
- SectionDivider: `FITS: educational, structured, documentary, corporate. FIGHTS: fast viral — a full-frame chapter card stalls pace.`
- AnnotationArrow: `FITS: educational, explainer, product-demo, casual — a hand-drawn pointer. FIGHTS: cinematic, story, premium-formal…`
- Reticle: `FITS: tech, product, viral, gaming/HUD register… FIGHTS: cinematic, story, formal-corporate — HUD brackets are a tech/gaming texture.`

**SOUND EFFECTS `[CODE](handler.py:6690-6720)`** (verbatim FITS/FIGHTS; `voice` at 6702 has none)
- boom: `FITS: viral, punchy, high-energy payoffs — the single heaviest hit. FIGHTS: corporate, clean, professional, educational; and cinematic/story climaxes — a boom PUNCHES…where a cinematic climax SWELLS…never boom's punch.`
- punchsfx: `FITS: viral, punchy, high-energy, confrontational delivery. FIGHTS: corporate, professional, calm, cinematic…`
- swoosh-sound-effects: `FITS: any vibe — the safe motion cue… FIGHTS: nothing tonally; only wrong when there's no motion or speed to voice.`
- woosh-professional: `FITS: any vibe, leans professional/corporate/educational/story… FIGHTS: nothing tonally; the restrained default.`
- transition-sfx: `FITS: cinematic, story, professional, educational act-turns; safe on the single biggest turn in any vibe. FIGHTS: nothing tonally; reserved for the ONE largest turn, not scattered.`
- camera-flash: `FITS: any vibe — a photo/screenshot literally happening…is the gate… FIGHTS: non-diegetic decoration…`
- money-ching: `FITS: viral, casual, product, hustle — …a price, cost, or "free" lands. FIGHTS: cinematic, story, serious-corporate — reads gimmicky…`
- iphoneding: `FITS: any vibe — a message/notification quoted or shown…is the gate… FIGHTS: non-diegetic filler…`
- mouse-click-sound: `FITS: educational, explainer, tech, product-demo, clean-corporate… FIGHTS: hype/high-energy edits…comedic registers.`
- popsfx: `FITS: casual, viral, upbeat — a light bonus. FIGHTS: serious-corporate, cinematic, somber…`
- rizz: `FITS: viral, comedic, casual meme-register charm — only. FIGHTS: corporate, professional, educational, cinematic, story…`
- shockingsfx: `FITS: viral, dramatic, high-energy reveals and twists. FIGHTS: corporate, professional, calm, educational…`
- awkward-moment: `FITS: viral, comedic, casual storytelling with a held cringe beat — only. FIGHTS: corporate, professional, educational, cinematic…`
- wompwomp: `FITS: viral, comedic, casual — a fail played as the punchline; only. FIGHTS: corporate, professional, story, cinematic…`
- imposter: `FITS: viral, comedic, casual suspense played for meme-effect — only. FIGHTS: corporate, professional, serious-cinematic — …for genuine dramatic suspense, prefer a swell.`

**TRANSITIONS `[CODE](handler.py:11608-11616)`**
- CardSwipe: `FITS: casual, vlog, viral pivots. FIGHTS: polished-corporate, cinematic, formal…`
- ZoomThrough: `FITS: viral, high-energy, punchy — the dive into the payoff. FIGHTS: calm, corporate, cinematic-smooth, educational…`
- SlideOver: `FITS: educational, explainer, corporate, chaptered talking-head — clean and neutral. FIGHTS: nothing strongly; too plain to carry a big emotional or hype beat.`
- Stack: `FITS: any vibe when iOS/an app IS the subject — a phone or app demo is the gate, not the vibe. FIGHTS: everywhere else it reads as costume; never as generic decoration.`
- CrossfadeZoom: `FITS: story, cinematic, documentary, sentimental bridges. FIGHTS: viral, punchy, high-energy — a soft dissolve kills momentum.`
- ShutterFlash (transition): `FITS: viral, dramatic, high-energy — where the cut itself should be the event. FIGHTS: calm, corporate, cinematic-smooth, educational…`
- StepPush: `FITS: corporate, educational, business, training. FIGHTS: casual, viral, cinematic — keynote motion is stiff…`
- FilmStrip: `FITS: a curated collection/portfolio ("5 things I made") in showcase/creative vibes. FIGHTS: as a generic scene-change; formal-corporate or somber…`
- DipToBlack: `FITS: cinematic, story, professional, documentary act-breaks — the deepest deliberate pause. FIGHTS: viral, punchy, high-energy, fast…`

**TIGHT-CUT OVERLAYS `[CODE](handler.py:11619-11620)`**
- LightLeak: `FITS: story, emotional, nostalgic, reflective — a realization or callback. FIGHTS: hard-corporate, hype, tech…`
- ShutterFlash (overlay): `FITS: viral, high-energy accents — a punch on a stat or punchline. FIGHTS: calm, professional, cinematic, somber…`

**CAPTIONS `[CODE](handler.py:6347-6364)`** (lowercase Fits/Fights; framing at 6344 "about what DELIVERY the typography suits, never about the edit")
- Prime: `Fits: aspirational, self-improvement, premium-branding…keyword peaks the breakout line can lift onto. Fights: casual speakers; flat, even-weight delivery…`
- TypewriterReveal: `Fits: tech/coding, documentary narration, hacker/retro-CRT, slow deliberate delivery. Fights: high-energy delivery; speech faster than the typing animation.`
- Cove: `Fits: premium/luxury and wellness…slow deliberate delivery… Fights: aggressive/high-energy and casual/offhand delivery…`
- Lumen: `Fits: hustle, motivational, money/business/success…value words (numbers, prices, brands) for the gold treatment to gild. Fights: understated/melancholic; delivery with no money/value words…`
- Pulse: `Fits: sung or musical delivery, rapid dialogue, the doubled cadence of a lyric video. Fights: contemplative, unhurried delivery…adjacent words of very different length.`
- Quintessence: `Fits: delivery built on dramatic pauses — poetry, mantras, slow deliberate dialogue. Fights: dense or fast dialogue, where the spring in/out turns to stutter.`
- TwoTone: `Fits: short, shouted, two-part hooks…("STOP / SCROLLING")… Fights: long sentences…calm/quiet/contemplative delivery; warm serif registers.`
- CleanCut: `Fits: serious, restrained, cinematic-register delivery; measured deliberate speech under neutral type. Fights: hype/high-energy; any moment wanting a decorated/keyword-accented word…`
- Gadzhi: `Fits: business/hustle and SMMA-style delivery; product pitches that name numbers… Fights: warm serif registers; soft/gentle/playful delivery…`

## G33. Primitives in render but NEVER offered / offered but NO render impl

**In render layer but NOT offered to the model:**
1. **LightLeak-as-full-transition** — exported as a handle-required transition with `LIGHT_LEAK_PEAK_PROGRESS` `[CODE](src/remotion/src/transitions/index.ts:22)` and a component dir `transitions/LightLeak/`, but **absent from `VALID_TRANSITION_TYPES`** `[CODE](type_registries.py:43-47)`. LightLeak is offered ONLY as a 180ms tight-cut overlay. `[INFERRED]` the CUT-boundary LightLeak transition is unreachable by any recipe.
2. **SpeechBubble (base)** — a full render component `[CODE](src/remotion/src/motion-graphics/index.ts:15)` but NOT a `VALID_MG_TYPES` member; only its 4 named variants (TweetBubble/InstagramComment/IMessageBubble/TikTokComment) are offered. The bare bubble is render-only.
3. **NewspaperWipe** — **RETIRED** (directive #13). Still has render assets/CATALOG entry `[CODE](src/remotion/src/transitions/CATALOG.md:163)` and stored plans coerce it away `[CODE](handler.py:24897-24899,25934-25937)`; not in any vocabulary. Render-adjacent but dead.

**Offered but NO render implementation:** none found among live vocabularies — every `VALID_ZOOM/MG/TRANSITION/CAPTION/TIGHT` member maps to a component (`ZOOM_MAP`, `MG_MAP` 26/26 `[CODE](src/remotion/src/PromptlyRender.tsx:129-138)`, transition/caption exports). **Caveat — `color_effect`:** it survives as a *plan field shape* (schema-level) but is force-nulled with **no render path** `[CODE](handler.py:15893-15897)` — the closest thing to "in the contract but nothing renders it." `[CODE]`

## G34. What the render layer can do that nothing currently asks for

Reading the render input contract `PromptlyRenderInput` `[CODE](render_schemas.py:345-393)` and `PromptlyMicroSegmentsInput` `[CODE](render_schemas.py:404-423)`:
- **Multi-source stitching — BUILT but dormant.** `_download_and_concat_sources(source_urls,…)` `[CODE](handler.py:22000-22083)` downloads N S3 objects, normalizes each (`scale=1080:1920:force_original_aspect_ratio=decrease,pad…,fps=30`) and `concat=n=N:v=1:a=1` into ONE file. Gated by premium + `multi_input_enabled`/`MULTI_INPUT_ENABLED` + ≥2 `video_urls` `[CODE](handler.py:35199-35210)`; described "dormant" `[CODE](handler.py:35697)`. So the pipeline *can* accept multiple uploads, but it collapses them to one source before planning (see I42).
- **Per-clip / per-layer alternate sources.** `ClipSpec.src` (per-clip pre-extracted mp4) `[CODE](render_schemas.py:128-142)`, `TransitionSpec.clipASrc/clipBSrc` `[CODE](render_schemas.py:153-156)`, `BrollSpec.src` (a *non-user* Pexels URL) `[CODE](render_schemas.py:190-196)` — the timeline can already draw pixels from files other than the top-level `sourceUrl`.
- **Still-image / generated compositions.** `GeneratedSceneSpec` with a code-generated subject still, text layers, motion, and `sceneType ∈ {typo_stat, hero_object, photo_card}` `[CODE](render_schemas.py:203-262)` — a full non-footage compositing engine, currently dark.
- **Arbitrary trims / speed.** Each clip is `startFromFrames + durationInFrames + playbackRate` `[CODE](render_schemas.py:128-142)` — arbitrary in/out and speed are expressible (speed is deliberately pinned to 1.0 on the editorial route by product law).
- **Pre-timed text from known inputs.** `GenSceneTextLayerSpec.content` is "FROM-KNOWN-INPUTS-ONLY" with per-word `popFrame` `[CODE](render_schemas.py:219-228)` — pre-scripted on-screen text sync exists.
- **NOT expressible today:** a single render input that addresses N *distinct* full sources as a timeline (the top-level contract is one `sourceUrl` + one frame space); true multi-clip assembly requires the pre-concat collapse first (I41/I42).

---

# SECTION H — USAGE REALITY

`[MEASURED]` n=3,949 completed jobs, window 2026-06-25→2026-08-10. Premium/editorial route n=2074 (the only route carrying the full toolbox). "events" = component instances; "vids" = videos with ≥1.

## H35. Absolute usage counts + rates (every family)

**ZOOMS** — 6,033 events across 2,363 videos (1.53/video overall; **79.1%** of premium videos, 2.22/premium-video). By type (events): SmoothPush **2697** · SnapReframe **1376** · StepZoom **981** · DepthPull **516** · LetterboxPush **397** · FocusWindow **38** · StagedPush **28**. All 7 fire.

**MOTION GRAPHICS** — 865 events across 625 videos (0.22/video; **21.5%** of premium videos carry any MG, 0.31/premium-video). By type: Stamp **252** · PillCluster **151** · StatCard **145** · PullQuote **51** · EditorialQuote **44** · AnnotationArrow **28** · RecordingFrame **26** · DropBanner **25** · Reticle **19** · Notification **18** · InstagramComment **16** · StickyNotes **16** · DropCard **13** · IMessageBubble **13** · ProgressBar **13** · MouseDrag **11** · RankedList **10** · TikTokComment **5** · SectionDivider **3** · Timeline **3** · TimelineRoadmap **2** · StepDivider **1** · **ChatThread 0 · TweetBubble 0 · BarRace 0 · PillMarquee 0**.

**CAPTION STYLES** — 1,722 premium videos carry a style (**83.0%** of premium); +119 explicit `none`. By style: CleanCut **599** · Gadzhi **307** · Pulse **194** · Cove **184** · Prime **147** · Lumen **109** · TwoTone **43** · Quintessence **15** · TypewriterReveal **5**. All 9 fire.

**TRANSITIONS** — 410 events across 252 videos. By type: DipToBlack **195** · CrossfadeZoom **115** · ShutterFlash **50** · ZoomThrough **26** · SlideOver **12** · CardSwipe **7** · StepPush **4** · FilmStrip **1** · **Stack 0**. (Most transitions live on lean routes: premium only 75 events / 60 videos = **2.9%** of premium; see H37/H39.)

**TIGHT-CUT OVERLAYS** — 844 events across 569 videos (all premium; **27.4%** of premium). ShutterFlash **564** · LightLeak **280**. Both fire.

**SOUND EFFECTS** — 4,753 events across 1,364 videos (all premium; **65.8%** of premium, 2.29/premium-video). swoosh-sound-effects **1066** · punchsfx **777** · boom **628** · transition-sfx **600** · popsfx **537** · woosh-professional **434** · money-ching **189** · mouse-click-sound **151** · camera-flash **115** · shockingsfx **102** · wompwomp **57** · iphoneding **38** · rizz **35** · imposter **15** · awkward-moment **9**. All 15 fire.

**TEXT OVERLAYS** — 756 events across 595 videos (all premium; **28.7%** of premium). caption_match **748** · sticky_note **8**. Both variants fire (caption_match dominates 99%).

**EMPHASIS MOMENTS** (the carrier for zoom+MG+sfx) — 6,043 across 1,710 videos (**82.4%** of premium, 2.91/premium-video). By emphasis type: statement **3275** · revelation **1296** · reaction **587** · punchline **585** · question **300**. By arc_position: mid_peak **1824** · payoff **1361** · hook **1196** · close **384** · build **310** · breather **6**.

**B-ROLL** — 208 clips across 149 videos (all premium; **7.2%** of premium, 0.10/premium-video). `resolved_broll` present on 149 jobs (matches).

**SPEED EFFECTS** — 944 non-1.0 clips across 636 videos, ALL on aesthetic routes: moodreel **607/679 = 89.4%** of moodreel, hype **29/54 = 53.7%**. Premium & minimal routes = **0** (1.0x editorial law holds).

**OUTRO** — 1,332 videos non-`none` (33.7% overall): moodreel **671/679 = 98.8%**, premium **609/2074 = 29.4%**, hype 52/54, minimal/minimal_speech_uncut 0.

**GENERATED SCENES** — **0 events / 0 videos** (0 of 2074 premium). See H37.
**COLOR EFFECTS** — **0** (dead field). See H37.

## H36. Components at/near zero — content-gated vs unreachable (per component)

**Absolute zero, CONTENT-GATED (correctly rare — a real diegetic trigger must exist):**
- **TweetBubble (0), ChatThread (0)** — FITS says "a REAL quoted tweet / real multi-message exchange **is the gate**" `[CODE](handler.py:6524,6536)`. No hard code gate; the model self-suppresses without the content. `[INFERRED]` correctly rare — talking-head uploads rarely quote a literal tweet/DM thread. (Note InstagramComment=16, IMessageBubble=13, TikTokComment=5 DO fire, so the social-card path is reachable; Tweet/Chat just lack triggering content.)
- **Stack transition (0)** — FITS "any vibe when iOS/an app **IS the subject** — a phone/app demo is the gate" `[CODE](handler.py:11611)`. Content-gated to app-demo uploads; correctly rare.

**Absolute zero, DISCRIMINATION-STARVED (likely unreachable, not just rare):**
- **PillMarquee (0)** — its FITS reserves it for "6+ tags rattled off," and its FIGHTS actively routes the 2–8-tag case to **PillCluster** `[CODE](handler.py:6503)`. PillCluster fires **151×**; PillMarquee 0. `[INFERRED]` the FITS boundary (a *stream* of 6+ vs a *group* of 2–8) rarely resolves in Marquee's favor, and the tie-break in FIGHTS points away from it — this is a fitness rule that essentially never wins, not pure content rarity.
- **BarRace (0)** — FITS "compares two-plus countable quantities head-to-head," FIGHTS routes single-quantity→ProgressBar and single-number→StatCard `[CODE](handler.py:6489)`. StatCard fires 145×, ProgressBar 13×; BarRace 0. `[INFERRED]` the "head-to-head countable comparison IS the point" trigger is both content-rare AND out-competed by StatCard whenever a single number can carry the moment.

**Near-zero, CONTENT/SPECIALTY-GATED (correctly rare by design):**
- **FocusWindow (38)** — FITS "a specialty, **gated by that need** (detail AND context at once); FIGHTS as a generic push" `[CODE](handler.py:6659)`. Correctly rare.
- **StagedPush (28)** — FIGHTS "ANY non-building moment"; the schema also requires 2–3 CONSECUTIVE building emphasis words `[CODE](type_registries.py:104-106)`, `[CODE](handler.py:6669)`. Structurally gated → correctly rare.
- **TypewriterReveal caption (5), Quintessence (15)** — delivery-gated (`Fits: slow deliberate / dramatic-pause delivery`) `[CODE](handler.py:6349,6358)`; most uploads are faster/denser. Correctly rare.
- **FilmStrip (1), StepPush (4), CardSwipe (7)** transitions, and MG tail **StepDivider (1)/TimelineRoadmap (2)/Timeline (3)/SectionDivider (3)/TikTokComment (5)** — all carry MOMENT-SHAPE or register FITS `[CODE](handler.py:6564-6573,6530,11614-11615)` that require a specific structural moment; content-gated + out-competed. `[INFERRED]` correctly rare rather than unreachable (they each fire ≥1, proving reachability).
- **SFX tail** awkward-moment (9), imposter (15), rizz (35) — "comedic/meme-register only" FITS `[CODE](handler.py:6712-6720)`; correctly rare on non-comedic traffic.

## H37. Whole families at/near zero

- **GENERATED SCENES — absolute zero (0 / 3,949; 0 / 2,074 premium).** Not content rarity: it is **premium-gated AND effectively INERT**. Emission is "defined but INERT" `[CODE](handler.py:1347)`; the composer is "ratified hybrid — INERT until cutover" `[CODE](handler.py:27258)`; `_premium_gate_scene_strip` strips scenes from any non-premium job `[CODE](handler.py:30898-30926)`; scenes are shed first under the render budget red-line `[CODE](handler.py:38480-38487)`; ladder rungs strip them `[CODE](handler.py:29784-29792)`. Even the 2,074 premium jobs emit none in this window → the family is dark in practice. **Whole family unreached on real traffic.**
- **COLOR EFFECTS — absolute zero, REMOVED.** Force-nulled `[CODE](handler.py:15893-15897)`, telemetry "feature removed" `[CODE](handler.py:2979-2982)`; no render path. **Dead family.**
- **TRANSITIONS on the premium route — near-zero (60 / 2,074 = 2.9%).** Not dead globally (410 total events), but the editorial route almost never uses handle-transitions, preferring **tight-cut overlays (27.4%)**. `[INFERRED]` the editorial pass treats hard-cut-plus-overlay as the default seam and reserves true transitions for "the ONE largest turn."
- **Entire toolbox on lean routes — zero by construction.** `minimal_speech_uncut` (768 videos) emits **nothing** (no zoom/mg/trans/sfx/caption/emphasis). `minimal` (374) emits only transitions (via the lean plan). moodreel/hype carry zoom+MG+transitions+speed but **no** sfx/captions/emphasis/tight/broll/text-overlays. `[MEASURED]` (byRoute table). So 1,875 of 3,949 completed jobs (47%) never touch the editorial toolbox at all.

## H38. Components firing OFF their stated purpose? (sampled placements)

Sampled real premium `emphasis_moments`/`_zoom_effect`/`sound_effects` placements (job dumps):
- Emphasis→zoom coherence looks correct: `{"type":"punchline","arc_position":"hook","zoom_effect":{"type":"SnapReframe"…},"word_indices":[4],"viewer_feeling":"the self-deprecating hook grabs attention"}` — a punchline/hook correctly drew **SnapReframe** (its FITS = "punchlines and reactions"). `[MEASURED]`
- SFX native-to-moment: `{"word":"आकर","sound":"punchsfx","why":"the self-deprecating hook grabs attention"}` on a hook — matches punchsfx FITS ("punchy/confrontational"). `transition-sfx` rode the DipToBlack act-turn (matches "the ONE largest turn"). `[MEASURED]`
- Tight overlay: `ShutterFlash after_word_index:140 — "accenting the exact frame the punchline hits"` — matches ShutterFlash-overlay FITS ("a punch on a stat or punchline"). `[MEASURED]`
- **Distribution sanity check** `[MEASURED]`: the top zoom SmoothPush (2697, "default lean-in for statements") pairs with the top emphasis type `statement` (3275) — the highest-volume pairing matches the stated default. SnapReframe (1376) tracks punchline+reaction (585+587). No obvious purpose/placement inversion surfaced in the sampled set. `[INFERRED]` I did not find a firing-off-purpose case; a full audit would need a larger hand-sampled `viewer_feeling`↔component join (not done here). `[UNKNOWN]` — whether MGs ever attach to a moment whose `props` lack the required real data (e.g. StatCard with no number) at the placement level; the FITS says "only wrong without a real quoted number," enforcement is prompt-side, so a stray mis-fire is possible but none seen in the sample.

## H39. Usage across routes — does stated intent steer output? (cut by route) `[MEASURED]`

| family (per-video %) | premium (2074) | moodreel (679) | hype (54) | minimal (374) | min_speech_uncut (768) |
|---|---|---|---|---|---|
| zoom | 79.1% | 98.4% | 100% | 0% | 0% |
| motion graphics | 21.5% | 20.3% | 75.9% | 0% | 0% |
| transitions | 2.9% | 3.7% | 96.3% | 30.7% | 0% |
| tight overlays | 27.4% | 0% | 0% | 0% | 0% |
| sound effects | 65.8% | 0% | 0% | 0% | 0% |
| caption style | 83.0% | 0% | 0% | 0% | 0% |
| emphasis moments | 82.4% | 0% | 0% | 0% | 0% |
| b-roll | 7.2% | 0% | 0% | 0% | 0% |
| text overlays | 28.7% | 0% | 0% | 0% | 0% |
| speed (non-1.0x) | 0% | 89.4% | 53.7% | 0% | 0% |
| outro | 29.4% | 98.8% | 96.3% | 0% | 0% |

**Route strongly steers output** `[MEASURED]`: the route selects the *entire toolbox*, not just intensity. `hype` maxes transitions (96%) + MG (76%) + zoom (100%); `moodreel` is a zoom+speed+outro aesthetic (98% zoom, 89% speed, 99% outro) with NO captions/sfx/emphasis; `premium` is the only route with sfx/captions/emphasis/tight/broll/text-overlays; the two `minimal*` routes are near-empty (minimal = transitions only; minimal_speech_uncut = raw cuts). Within premium, `vibe_input` further steers *which* component (the FITS/FIGHTS mechanism) — e.g. CleanCut+Gadzhi dominate captions (906 of ~1722) consistent with the hustle/serious skew of the traffic. `[UNKNOWN]` — a per-vibe breakdown *within* premium was not computed (vibe_input is free text; would need clustering); route-level steering is the measured axis.

---

# SECTION I — RENDER LAYER

## I40. Render input contract (complete, with strictness)

Two top-level Pydantic models, both `extra="forbid"` via base `_RemotionModel` `[CODE](render_schemas.py:83-84)` → **any unregistered key Python emits is a hard validation error at JSON-emit time** (this is the class that silently blocked `motionTokens` until it was registered — see the deliberate note `[CODE](render_schemas.py:153-156,378-381)`).

**`PromptlyRenderInput`** `[CODE](render_schemas.py:345-393)` (the overlay/full leg): `sourceUrl:str` (SINGULAR), `fps:float`, `width:int`, `height:int`, `totalDurationInFrames:int`, `clips:List[ClipSpec]`, `transitions:List[TransitionSpec]`, `broll:List[BrollSpec]`, `generatedScenes:List[GeneratedSceneSpec]=[]`, `caption:Optional[CaptionSpec]`, `textOverlays:List[TextOverlaySpec]`, `motionGraphics:List[MotionGraphicSpec]`, `tightCutOverlays:List[TightCutOverlaySpec]=[]`, `outro:Optional[OutroKind]`, feature flags `motionTokens/resprungZooms/motionBlur(+samples/shutterAngle)/smoothGraphics` all default-`False` (byte-identical when off).

**`PromptlyMicroSegmentsInput`** `[CODE](render_schemas.py:404-423)` (the micro/transition+composite-zoom leg): `sourceUrl`, `fps`, `width`, `height`, `totalDurationInFrames`, `segments:List[MicroSegmentSpec]` where `MicroSegmentSpec{type:"transition"|"zoom_clip", outputStartFrame, durationInFrames, transition?, clip?}` `[CODE](render_schemas.py:396-402)`, plus the same blur/resprung/smooth flags.

Sub-models: `ClipSpec` `[CODE](render_schemas.py:128-142)`, `TransitionSpec` `[CODE](render_schemas.py:145-168)`, `BrollSpec` `[CODE](render_schemas.py:190-196)`, `CaptionSpec` `[CODE](render_schemas.py:296-301)`, `MotionGraphicSpec` `[CODE](render_schemas.py:305-309)`, `TextOverlaySpec` union `[CODE](render_schemas.py:335-338)`, `GeneratedSceneSpec` `[CODE](render_schemas.py:245-262)`. Component-type fields are `Literal[...]` derived from `type_registries` frozensets (single source of truth) `[CODE](render_schemas.py:49-77)`.

## I41. Is it clip-addressed? Can it already express a timeline from N sources?

**Yes, clip-addressed; partially multi-source-capable, but authored against ONE frame space.** The timeline is a `List[ClipSpec]`, each clip `{id, startFromFrames, playbackRate, durationInFrames}` `[CODE](render_schemas.py:128-142)` — clips ARE addressed positions in a source's frame space, so a timeline assembled from arbitrary trims of that source is already expressible. Evidence of multi-*file* capability at the layer level:
- `ClipSpec.src` (optional per-clip pre-extracted mp4) `[CODE](render_schemas.py:133-142)` — a zoom clip plays its OWN trimmed file, not the top-level source.
- `TransitionSpec.clipASrc/clipBSrc` (per-layer sources) `[CODE](render_schemas.py:153-156)`.
- `BrollSpec.src` — a non-user Pexels URL composited into the same timeline `[CODE](render_schemas.py:190-196)`.
**But** the top-level contract carries a single `sourceUrl` and one `totalDurationInFrames` frame space, and the cut plan (`cuts[].source_start/source_end` in the premium recipe, e.g. `{"source_start":0.358,"source_end":2.423}` `[MEASURED]`) is authored against **one** normalized source. So it can express "many trims of one source + stock b-roll + generated scenes," but NOT natively "clip 0 from file A, clip 1 from file B" at the top level — that requires the pre-concat in I42.

## I42. Where N→1 collapse happens; what would stop it

**Collapse point:** `_download_and_concat_sources(source_urls, dest_path, work_dir)` `[CODE](handler.py:22000-22083)`. When a premium job carries `video_urls` (plural) AND the flag is on, it downloads all N, normalizes each to 1080×1920/fps30, and `concat=n=N:v=1:a=1` into a **single** `output.mp4` `[CODE](handler.py:22050-22072)`; downstream planning/cutting sees one source with one continuous frame space. Single-input jobs hit `len(_locals)==1 → shutil.copy` (byte-identical) `[CODE](handler.py:22042-22044)`. Gate `[CODE](handler.py:35199-35213)`: `route_premium AND (multi_input_enabled|MULTI_INPUT_ENABLED) AND len(video_urls)>1`; otherwise `_mi_urls=[video_url]`. Described "dormant" `[CODE](handler.py:35697)`.
**What would stop the collapse:** the top-level render contract accepting per-clip source identity (it partially does via `ClipSpec.src`/`clipASrc`/`clipBSrc`), plus a planner that authors cuts against multiple source frame spaces instead of one normalized source. Today the collapse is deliberate so the entire single-source cut/zoom/caption machinery stays valid. `[INFERRED]`

## I43. What renders in Remotion vs FFmpeg vs elsewhere (EXACT)

Core render fn `render_multi_clip` `[CODE](handler.py:24851)`, driven by `render_stage` `[CODE](handler.py:33895)`; filtergraph builder `ffmpeg_base.py`.

**Remotion renders exactly two ProRes-4444 intermediates (never the deliverable):** Remotion is invoked only as `node /remotion/render-full.mjs` `[CODE](handler.py:28170,28185,28317,28335)` via `_remotion_subprocess` `[CODE](handler.py:29631,29654)`, composition whitelist `[CODE](src/remotion/render-full.mjs:47-50)`:
- **`PromptlyOverlay`** → ProRes 4444 **yuva444p10le** (alpha) = every non-source pixel: captions + motion graphics + text overlays + generated scenes + **B-roll cutaways (BrollLayer)**. Output `overlay.mov` `[CODE](handler.py:27987)`; codec `[CODE](src/remotion/render-full.mjs:268-270)`. Audio muted (`muted:true`) `[CODE](src/remotion/render-full.mjs:287)`; GL `swangle` `[CODE](handler.py:28000)`.
- **`PromptlyMicroSegments`** → ProRes 4444 **yuv444p10le** (no alpha) = only the windows Remotion must own: all 9 transitions + composite-zoom clips (FocusWindow/LetterboxPush/DepthPull/StagedPush). Output `micro_segments.mov` `[CODE](handler.py:27992)`; input built by `build_micro_segments_input` `[CODE](ffmpeg_base.py:940)`.

**FFmpeg does everything else** (base cuts, concat, composite, denoise, the single lossy encode, audio, HLS): filtergraph `build_final_filtergraph` `[CODE](ffmpeg_base.py:439,476-488)` — FFmpeg-renderable clips trimmed straight from the normalized source `[CODE](ffmpeg_base.py:600-605)`; base concat `concat=n=N:v=1:a=0[base]` `[CODE](ffmpeg_base.py:617)`; outro fade `[CODE](ffmpeg_base.py:658-660)`; alpha-composite overlay onto base `overlay=format=auto:shortest=0[composited]` `[CODE](ffmpeg_base.py:692,696)`; denoise+flatten `hqdn3d=1.5:1.5:6:6,format=yuv420p[final_v]` `[CODE](ffmpeg_base.py:724-726)`. **Non-zoom clips never reach Remotion** — FFmpeg renders them directly `[CODE](src/remotion/src/PromptlyRender.tsx:148-149)`. **B-roll is composited via the Remotion alpha layer, NOT ffmpeg** `[CODE](ffmpeg_base.py:484-486)`. SFX + all audio are FFmpeg (`amix`→PCM) `[CODE](handler.py:28864-28872)`. HLS is FFmpeg `_encode_and_upload_hls` `[CODE](handler.py:31714)`.
**Elsewhere:** GeneratedScene subject stills are made by an image-gen call `_generate_scene_subject` `[CODE](handler.py:10671)` (not Remotion, not ffmpeg) then composited by Remotion. Sequence: normalize(ffmpeg) → ∥ {overlay chunks + micro chunks + audio pipeline} → composite chunks(ffmpeg ProRes) → final concat+mux (ONE libx264 pass) → HLS(ffmpeg).

## I44. Chunking / parallelization (formulas)

All chunk counts **derived from output frame count**, env-capped; concurrency derived from the container core budget.
- **Overlay** `[CODE](handler.py:28030-28101)`: `_RENDER_CHUNKS=max(1, PROMPTLY_RENDER_CHUNKS or 8)`; `_CHUNK_FRAMES=max(150, PROMPTLY_CHUNK_FRAMES or 450)`; `_EFFECTIVE_CHUNKS=min(_RENDER_CHUNKS, max(1, total_output_frames//_CHUNK_FRAMES))`; `_OVERLAY_CHUNK_COUNT = _EFFECTIVE_CHUNKS if frames>=300 else 1`.
- **Core/tab/concurrency** `[CODE](handler.py:28074-28099)`: `_CONTAINER_CORES=_render_core_budget()` (env `PROMPTLY_RENDER_CORE_BUDGET`, floor 4); `_TAB_BUDGET=min(cores, PROMPTLY_OVERLAY_TAB_BUDGET or max(4, cores//2))`; `_PER_CHUNK_CONCURRENCY=min(cores, max(2, _TAB_BUDGET//max(_OVERLAY_CHUNK_COUNT,1)) if chunks>1 else 8)` (clamped ≤ cores; Remotion self-heal on over-request `[CODE](handler.py:29704-29720)`).
- **Micro** `[CODE](handler.py:28262-28309)`: threshold 200; `_MICRO_CHUNK_COUNT=min(max(1,PROMPTLY_RENDER_CHUNKS or 8), max(1, micro_frames//_CHUNK_FRAMES))` then `max(4, …)` (never fewer than 4 when chunked), else 1; `_MICRO_CONCURRENCY=min(cores, max(2, tab_budget//len(ranges)))`.
- **Composite** `[CODE](handler.py:28384-28389)`: `_N_COMPOSITE_CHUNKS=min(max(1,PROMPTLY_RENDER_CHUNKS or 8), max(1, frames//max(150,PROMPTLY_CHUNK_FRAMES or 450))) if frames>=400 else 1`. When overlay+composite both chunk (`_pipeline_chunks` `[CODE](handler.py:28407)`), composite chunk K starts as overlay chunk K finishes (no barrier) `[CODE](handler.py:28762-28809)`.
- Thread pools: render pool `max_workers=len(overlay_cmds)+len(micro_cmds)+1` `[CODE](handler.py:28643-28645)`; composite pool `max_workers=len(_composite_ranges)` `[CODE](handler.py:28758-28760)`. Optional cross-container fan-out behind `PROMPTLY_RENDER_FANOUT` (default OFF, min 60s output) `[CODE](handler.py:28580-28632)`.
Hardcoded knobs: `_CHUNK_FRAMES=450`, thresholds 300/400/200, min-4 micro floor. Derived: all chunk counts (from frames), all concurrency (from cores).

## I45. Encode path (codecs, presets, passes, resolution, fps, quality laws)

Exactly **one lossy H.264 delivery encode**; all intermediates are lossless ProRes. `_X264_ENCODE_THREADS=48` PINNED `[CODE](handler.py:2124)` (determinism law — never x264-auto). Canvas fixed **1080×1920** `[CODE](ffmpeg_base.py:450-451)`, pix_fmt `yuv420p` everywhere, `-r/-g/-keyint_min = round(source_fps)`.
- **(A) Final concat+mux — chunked path (≥400 frames)** `[CODE](handler.py:29093-29143)`: `libx264 -preset medium -crf 18 -x264-params threads=48 -fps_mode cfr -r round(fps) -maxrate 18M -bufsize 36M -profile:v high -level 4.1 -pix_fmt yuv420p -g round(fps) -keyint_min round(fps) -sc_threshold 0` + bt709 tags; audio `aac -b:a 192k -ar 48000`; `-movflags +faststart+negative_cts_offsets`. **One pass.**
- **(B) Single-pass composite — short path (<400 frames)** `[CODE](handler.py:28530-28568)`: `libx264 -preset slow -crf 16 -maxrate 24M -bufsize 48M` (higher quality than the chunked path) + same bt709/gop/aac. **One pass.**
- **(C) Composite chunk intermediates** `[CODE](handler.py:28571-28577)`: `prores_ks -profile:v 4444 -pix_fmt yuv444p10le` (lossless — why the final mux is the only lossy step).
- **(D) Final audio** `[CODE](handler.py:28864-28872)`: `pcm_s16le` WAV (AAC deferred to the video pass so `-shortest` truncates cleanly).
- **(E) HLS ladder** `[CODE](handler.py:31762-31804)`: default 4-rendition `libx264 -preset medium` re-encode (360p 2000k / 540p 4500k / 720p 7500k / 1080p 14000k), fMP4 segments 4s; copy-mode HLS dark `[CODE](handler.py:31740-31752)`.
- **Intermediates (not shipped):** source normalize `libx264 -preset fast -crf 15` `[CODE](handler.py:36537-36556)`; per-clip pre-extract `-preset fast -crf 14` `[CODE](handler.py:27656-27665)`; multi-source concat `-preset veryfast -crf 20` `[CODE](handler.py:22065-22072)`.
- **NVENC helper exists but is NOT on the composite/final path** — `get_encode_args` returns `h264_nvenc` when `_has_nvenc()` `[CODE](handler.py:2082,2140-2183)`, used only by the aspect-crop path `[CODE](handler.py:19417)`; the main render hardcodes libx264. (Render worker is CPU-only per project memory.)
Quality laws in effect: byte-identical on a fixed plan across any CPU (pinned x264 threads); single-pass FFmpeg render; every editorial cut at 1.0x.

## I46. Can it composite non-user footage today? PROVEN vs designed

- **Pexels stock B-roll — PROVEN on real traffic.** `BrollSpec.src` (a non-user Pexels URL) composited through the Remotion `PromptlyOverlay` BrollLayer `[CODE](render_schemas.py:190-196)`, `[CODE](ffmpeg_base.py:484-486)`. `[MEASURED]` 208 clips across 149 premium videos in-window (7.2% of premium). Keyword-authoring + Gemini picker `[CODE](handler.py:6723-6763)`.
- **Generated stills / composed scenes (typo_stat, hero_object, photo_card) — DESIGNED + built, NOT proven.** Full path exists: subject-still generation `_generate_scene_subject` `[CODE](handler.py:10671)`, render input `generatedScenes` `[CODE](handler.py:27533)`, `GeneratedSceneSpec` `[CODE](render_schemas.py:245-262)`, real render tool `lumen-reel-render.mjs` (comp `LumenReel`). `[MEASURED]` **0 / 3,949 (0 / 2,074 premium)** — INERT/premium-gated (H37). Not proven on traffic.
- **Multi-clip stitching of extra user uploads — designed, dormant.** `_download_and_concat_sources` `[CODE](handler.py:22000)` (I42), gate off by default.
- **Avatar / synthetic video — NOT present.** No avatar/talking-head-generation path found. `[UNKNOWN]`/absent.
**Net:** today the pipeline composites exactly one class of non-user footage on real traffic — **Pexels b-roll**. Everything else (generated scenes, multi-source) is built-but-dark. `[INFERRED]`

---

## Cross-cutting findings / contradictions

1. **Task-brief assumption vs reality:** the brief expected components under `emphasis_moments/sfx/broll/...` in every plan; in truth **only the premium route (no `result.route` key) carries them** — 47% of completed jobs (the lean routes) run a stripped 5-key plan (clips/motion_graphics/transitions/notes/outro) with zero editorial toolbox. `[MEASURED]`
2. **Four MG types and one transition are absolute-zero in a 3,949-job window:** ChatThread, TweetBubble, BarRace, PillMarquee, and the Stack transition. Two (ChatThread/TweetBubble/Stack) are cleanly content-gated; **BarRace and PillMarquee look discrimination-starved** — their own FIGHTS lines route their trigger case to a sibling that always wins (StatCard/PillCluster). `[MEASURED]`+`[INFERRED]`
3. **Two whole families are dark:** generated_scenes (built, INERT/premium-gated, 0/2074 premium) and color_effect (removed). `[MEASURED]`+`[CODE]`
4. **Render-only primitives with no recipe path:** LightLeak-as-transition, SpeechBubble base, retired NewspaperWipe. `[CODE]`
5. **The render layer is more capable than the toolbox exercises it:** per-clip/per-layer alternate sources, multi-source concat, generated compositions, and pre-timed text all exist in the contract; only single-source trims + Pexels b-roll are used at volume. `[CODE]`+`[MEASURED]`
# Recon J/K/L/M — Perception · Re-edit · Generation · Fulfillment

Repo: `/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker` (handler.py = 39,192 lines).
Node dispatch server: `/Users/zaclibman/content-studio` (server.js + lib/).
DB: Supabase `video_jobs`, 6,338 rows, created_at range 2026-06-25 → 2026-08-10 [MEASURED].
Tagging: [MEASURED]=DB/log observed · [CODE](file:line) · [INFERRED] · [UNKNOWN].

---

# SECTION J — PERCEPTION

## J47. Every signal the pipeline detects about a source BEFORE planning

The parallel analysis fan-out is one `ThreadPoolExecutor(max_workers=10)` called `mega_pool` [CODE](handler.py:37589). Its submits [CODE](handler.py:37590-37649):

| # | mega_pool task | submit line | delegate fn |
|---|---|---|---|
| 1 | normalize (metadata + scale/crop filter) | [CODE](handler.py:37590) | `_do_normalize`→`analyze_source_video` [CODE](handler.py:35845, 22308) |
| 2 | transcribe (words, language) | [CODE](handler.py:37591) | `_do_transcribe`→`transcribe_audio` [CODE](handler.py:35848, 4644) |
| 3 | gemini_proxy (480p@18fps bytes the model watches) | [CODE](handler.py:37599) | `_do_gemini_proxy_impl` [CODE](handler.py:35894) |
| 4 | trend (weekly Apify style pulse) | [CODE](handler.py:37600) | `_do_trend_context` [CODE](handler.py:36779) |
| 5 | loudness (peak/rms/noise dB) | [CODE](handler.py:37601) | `_do_loudness`→`measure_source_loudness` [CODE](handler.py:35995, 5291) |
| 6 | shot_changes (scene cuts) | [CODE](handler.py:37602) | `_do_shot_changes`→`detect_shot_changes` [CODE](handler.py:36003, 4055) |
| 7 | vocal_emphasis (RMS-envelope peaks) | [CODE](handler.py:37603) | `_do_vocal_emphasis`→`detect_vocal_emphasis` [CODE](handler.py:36007, 5347) |
| 8 | shake_probe (handheld motion) | [CODE](handler.py:37606) | `_do_shake_probe`→`_probe_shake_intensity` [CODE](handler.py:36020, 20987) |
| 9 | exposure_probe (luminance/sharpness) | [CODE](handler.py:37607) | `_do_exposure_probe`→`_probe_exposure` [CODE](handler.py:36026, 21072) |
| 10 | fps_normalize (canonicalize 1080×1920 CFR + deshake gate) | [CODE](handler.py:37608) | `_do_fps_normalize` [CODE](handler.py:36032) |
| 11 | user_style profile (this user's past styles) | [CODE](handler.py:37613) | `fetch_user_style_profile` [CODE](handler.py:2417) |
| 12 | platform_pulse (launch nudge) | [CODE](handler.py:37619) | `fetch_platform_style_pulse` [CODE](handler.py:2545) |
| 13 | edit recipe (the Gemini editorial call itself) | [CODE](handler.py:37622) | `_do_edit_recipe_overlapped` [CODE](handler.py:36928) |
| 14 | faces (dense face positions) | [CODE](handler.py:37624) | `_do_face_detect_overlapped`→`detect_face_positions_dense` [CODE](handler.py:37496, 3377) |
| 15 | edit_policy resolve (flag/premium-gated) | [CODE](handler.py:37649) | `edit_policy.resolve_edit_policy` (import) |

Signals computed OUTSIDE mega_pool (later, or lazily):

- **Word timings** — inside the Deepgram result (`start`/`end` per word), plus a one-shot shift by `audio_stream_offset` (iPhone mic-init offset) computed in `analyze_source_video` [CODE](handler.py:22337-22343).
- **Speaker diarization** — pyannote, **LAZILY** dispatched only if Deepgram detects ≥2 speakers [CODE](handler.py:37592-37598); most selfie clips skip it.
- **Language / script** — `detected_language` from Deepgram `language=multi` [CODE](handler.py:4295) + `_dominant_script` from the words [CODE](handler.py:37299); an Arabic bridge and a Stage-A monolingual re-route sit on top (J50).
- **Transcription coverage (VAD)** — Silero-VAD `_transcription_coverage_check` [CODE](handler.py:22205); measures untranscribed speech.
- **Burned-in text** — TWO independent detectors: (a) the **model** reads the frame for burned-in captions (`existing_caption_region`, Stage 0 of the prompt) [CODE](handler.py:6204-6206); (b) a deterministic EAST detector `detect_burned_in_text` [CODE](burned_text.py:192) submitted concurrently inside `generate_edit_gemini` [CODE](handler.py:13123-13127), **DARK behind `PROMPTLY_BURNED_TEXT`** [CODE](handler.py:13123) via `_burned_text_enabled` [CODE](handler.py:4829).
- **Exposure / sharpness** — `_probe_exposure` (mean luminance, dark/bright frac, Laplacian variance) [CODE](handler.py:21072).
- **Shake / motion** — `_probe_shake_intensity` (Lucas-Kanade optical-flow magnitude) [CODE](handler.py:20987).
- **Input-quality struct** — `_assemble_input_quality` folds loudness+shake+exposure+face-ratio+dims+fps+duration into one descriptor [CODE](handler.py:21143).
- **Resolution / fps / rotation / VFR / audio-presence** — all read in `analyze_source_video` via `_probe_full` [CODE](handler.py:22322, 22350-22400); audio-presence separately re-probed at the intake audio-track gate [CODE](handler.py:35744-35748).
- **Beats** — [UNKNOWN as a standalone detector]: there is no dedicated beat-tracking task in mega_pool. Beat/rhythm reads live in (a) `vocal_emphasis` RMS peaks (the closest mechanical "beat" signal) and (b) the mood-reel/minimal path's music-beat mention [CODE](handler.py:32537). No librosa/onset beat tracker is on the main planning path [INFERRED from mega_pool enumeration].
- **thumbnail candidates** — brightness+Laplacian thumbnail picker (reused math noted in `_probe_exposure` docstring [CODE](handler.py:21075-21076)); picked later, not pre-planning.

## J48. For each signal: how computed · cost · critical-path · fail mode

Cost note: `_pool_timings` per-task wall-clock is logged at pool teardown under `[long-pole] mega_pool per-task durations` [CODE](handler.py:37578-37587, 38363-38370) — the durable per-task time source. I did not have a live job log to read, so per-task **seconds are [UNKNOWN — no readable job log in this session]**; where the code carries a documented estimate I cite it.

| Signal | How computed (lib/subprocess) | Cost (time) | $ | Critical path? | Fail mode |
|---|---|---|---|---|---|
| normalize/analyze | `ffprobe` JSON, no decode [CODE](handler.py:22322) | sub-second | $0 | feeds render | **fail-closed**: `raise "No video stream found"` [CODE](handler.py:22326) |
| transcribe | Deepgram nova-3 `language=multi`, FLAC upload, 3× backoff [CODE](handler.py:4644, 4696) | ~net-bound; est. dominant long-pole (network) [CODE](handler.py:37573) | Deepgram per-min [UNKNOWN $] | **YES** (edit_plan waits on transcript) | retriable errors retry; else raises → intake gates convert 0-words to route/reject |
| gemini_proxy | `ffmpeg` 480p@18fps encode (or client/prewarm proxy) [CODE](handler.py:35946-35991) | ~7-10s on-server, ~0 if client/prewarm proxy [CODE](handler.py:35904-35906) | $0 (compute) | **YES** (serial-before the Gemini call) [CODE](handler.py:35882-35884) | **fail-closed**: `raise "Gemini proxy encode failed"` [CODE](handler.py:35993) |
| trend | Apify-scraped cache read [CODE](handler.py:36779) | cache read | $0 | no (skippable `_skip_trend`) | fail-open to None |
| loudness | `ffmpeg -vn astats` first 60s [CODE](handler.py:5304-5308) | sub-second (`-vn` skips video) [CODE](handler.py:5299) | $0 | no | **fail-closed**: `raise "loudness measurement failed"` [CODE](handler.py:5315) |
| shot_changes | `ffmpeg scdet` (decodes every frame) [CODE](handler.py:4092-4101) | base 60s, weighted to 240s ceiling [CODE](handler.py:4100) | $0 | no | parse-recover fallback [CODE](handler.py:4123); empty scores on miss |
| vocal_emphasis | `ffmpeg` PCM extract + numpy RMS envelope [CODE](handler.py:5359-5385) | sub-second | $0 | no | returns `[]` on <1s audio [CODE](handler.py:5371) (**degrades**) |
| shake_probe | OpenCV `VideoCapture` + Lucas-Kanade optical flow @240p [CODE](handler.py:21005-21063) | 240p sampling (12 frames) | $0 | no | **fail-closed to 0.0** = "stable", skip deshake [CODE](handler.py:20997-21000) |
| exposure_probe | OpenCV luminance mean + Laplacian variance @240p [CODE](handler.py:21109-21122) | 12-frame sample | $0 | no | **fail-open** neutral struct (mean_lum=128) [CODE](handler.py:21082-21083) |
| fps_normalize | `ffmpeg` passthrough-symlink OR libx264 re-encode + optional `deshake=rx16:ry16` [CODE](handler.py:36032-36042) | passthrough ~0; re-encode/deshake ≈100s @1080p60 [CODE](handler.py:20993) | $0 | feeds render | degrades to passthrough |
| faces | `ffmpeg` NVDEC frame extract + OpenCV DNN Caffe res10 SSD [CODE](handler.py:3414-3448) | base 30s, weighted to 180s [CODE](handler.py:3437-3439) | $0 | partially (framing/zoom anchors) | returns `[]` if DNN model missing (**degrades**) [CODE](handler.py:3416-3418); extract failure **fail-closed** `raise` [CODE](handler.py:3449) |
| diarization | pyannote (GPU) lazy [CODE](handler.py:37592) | ~10-15s GPU when it runs [CODE](handler.py:37596) | GPU compute | no | skipped if <2 speakers |
| burned_text (EAST) | `burned_text.detect_burned_in_text` [CODE](burned_text.py:192) concurrent w/ Gemini [CODE](handler.py:13126) | ~3s, hidden under Gemini [CODE](handler.py:13113) | $0 | no | returns None on any error [CODE](handler.py:13115); **DARK** default |
| coverage (VAD) | Silero VAD silence regions [CODE](handler.py:22235, 22247) | VAD pass | $0 | gate before recipe | **FAIL-OPEN** on measurement error [CODE](handler.py:22213, 22303) |
| user_style / platform_pulse | Supabase reads [CODE](handler.py:2417, 2545) | DB read | $0 | no | fail-open to None [CODE](handler.py:37383, 37390) |

## J49. Which signals reach the MODEL vs only reach CODE

**Reach the MODEL** (passed into `_build_post_cuts_prompt` and rendered into prompt text) [CODE](handler.py:5683-5716, 13200-13221):
- the 480p video proxy itself (Gemini watches it) · the kept-only transcript (Deepgram words)
- `shot_changes` [CODE](handler.py:5704) · `vocal_emphasis` w/ per-peak scores [CODE](handler.py:5705) · `source_loudness` peak/rms/noise [CODE](handler.py:5706)
- `face_visibility`, `speaker_positions`, `off_center`, `shot_scale`, `face_zone` (all derived from dense faces via `_build_face_signals` [CODE](handler.py:13175-13181))
- `source_language` [CODE](handler.py:13218) · `user_style_profile` · `platform_style_note` · `trend_context`
- `prior_plan` + `prior_plan_change_request` (re-edit) [CODE](handler.py:13214-13215, 7149)
- burned-in text: the model reads it itself from the frame (`existing_caption_region`, `source_text_regions`) [CODE](handler.py:6204-6206).

**Reach only CODE** (mechanical, never in the editorial prompt):
- `shake_probe` → only the deshake gate in `_do_fps_normalize` [CODE](handler.py:20992-20995).
- `exposure_probe` → the input-quality pass (silent premium grade-lift + optional enrichment offer), not editorial [CODE](handler.py:21077-21083).
- `shot_change_scores` (scdet confidence) → the scene-floor confidence gate, side-channel kept off the return value [CODE](handler.py:35998-36002).
- burned_text EAST detector output → double-caption suppression + zoom gate at the render-projection seam [CODE](handler.py:13114-13116); **DARK**.
- `audio_stream_offset` → one-shot transcript timestamp shift [CODE](handler.py:22337-22343).
- resolution / fps / rotation / VFR → normalize filter [CODE](handler.py:22389-22402).
- `_assemble_input_quality` struct [CODE](handler.py:21143) → premium grade + enrichment; not editorial.
- `measure_source_loudness` also drives code (audio normalization) in addition to reaching the model.

## J50. Which perception results GATE deterministically vs merely ADVISE

**ADVISE-only** (model reads, decides freely): shot_changes, vocal_emphasis, source_loudness, all face signals, shot_scale, face_zone, trend, user_style. Wrong signal → a worse but still-delivered edit (no reject).

**Deterministic GATES.** Standing law: content classes are ROUTES not errors; the only hard rejections are `<2.0s` and `>300s`. Zero-reject is **LIVE** (`PROMPTLY_ZERO_REJECT=1` since Jul 25) [CODE](handler.py:32383, 33563); every other gate raises `_MinimalRouteSignal` → `_run_minimal_pipeline` instead of failing. All `_MinimalRouteSignal` raises: [CODE](handler.py:34103, 35723, 35756, 37039, 37070, 37356, 38596).

1. **Duration cap — `CLIP_TOO_LONG` >300s** [CODE](handler.py:35701-35708). HARD REJECT (one of the two permitted). `_MAX_SOURCE_DURATION_S=300.0` [CODE](handler.py:29997). Wrong-high: a 305s clip that would edit fine is turned away (refund; measured via `_log_intake_reject` [CODE](handler.py:35704)). Wrong-low: nothing (probe miss fails open, proceeds) [CODE](handler.py:35696).
2. **Duration floor** [CODE](handler.py:35716-35732). `2.0s ≤ d < 5.0s` → **minimal route** (`too_short`) [CODE](handler.py:35722-35723); `d < 2.0s` (`_MIN_MINIMAL_DURATION_S=2.0` [CODE](handler.py:31698)) → **HARD REJECT `CLIP_TOO_SHORT`** [CODE](handler.py:35724-35728) (the second permitted rejection). Flag off → old 5.0s hard reject [CODE](handler.py:35729-35732).
3. **Audio-track gate** [CODE](handler.py:35744-35756). No audio stream → `no_audio` minimal route [CODE](handler.py:35756). Wrong (probe hiccup) → fails open, proceeds [CODE](handler.py:35741-35742).
4. **Talking-head gate** [CODE](handler.py:37031-37050). `face_ratio<0.20 (≥8 samples) AND words<10 (≥15s)` → `not_talking_head` minimal [CODE](handler.py:37039). Deliberately LENIENT — BOTH must hold [CODE](handler.py:37020-37030); false-positive rejection of a real talking-head is "dramatically worse." Wrong-strip: a low-face real edit becomes a thinner minimal edit (not an error).
5. **Zero-word gate** [CODE](handler.py:37053-37084). 0 words → `no_speech_muted` (face present) / `no_speech` minimal [CODE](handler.py:37070-37071). Speech-anchored pipeline can't edit silence.
6. **Transcription-coverage gate** [CODE](handler.py:37326-37364). `_transcription_coverage_check` fail (material VAD-speech untranscribed) → **Stage-A language recovery first** [CODE](handler.py:37268-37313), then if still failing → `transcription_incomplete` minimal [CODE](handler.py:37356) (captions suppressed, never patchy — the patchy-caption law). Direction matters: a **false-positive** = refund/thinner edit; a **false-negative destroys the user's video** (cutter deletes untranscribed speech as silence) [CODE](handler.py:37323-37325). Gate is **FAIL-OPEN** on measurement error [CODE](handler.py:22303). Zero-word empty-transcript closed the old "empty passes coverage" defect [CODE](handler.py:22220-22246).
7. **Language route** — `_route_language_via_gemini` [CODE](handler.py:5223]: Gemini IDs the language, routes to ONE **graduated** monolingual Deepgram model, **fail-closed on script** (native script or bail) [CODE](handler.py:5225-5236). Flag-gated `PROMPTLY_LANG_ROUTING=1` [CODE](handler.py:5094-5096). Wrong-ID → the recovered transcript must itself pass coverage or it's discarded [CODE](handler.py:5157-5161).
8. **Render-collapse / plan-collapse** — `render_collapsed` [CODE](handler.py:34103) and `plan_collapsed` [CODE](handler.py:38596) → minimal route (a collapsed edit is delivered as a clean-cut instead of failing).
9. **Integrity gate** — `_integrity_gate` [CODE](handler.py:21895]: freezedetect ∪ blackdetect ∩ silence over the OUTPUT, masked by expected slots/MGs/broll/scenes [CODE](handler.py:21895-21960). Trips on a dead region the plan didn't intend. `integrity_observe_only` (operator fixtures) delivers anyway with a loud log [CODE](handler.py:35047-35052). Source-echo downgrade prevents blaming us for a source that ended on black/freeze [CODE](handler.py:21747, 21922-21924).
10. **Degeneration abort** — streaming shape-abort + output-token cutoff (16k) [CODE](handler.py:11115-11205, 12264); a runaway Gemini output is aborted and re-rolled (`_DEGEN_EXTRA_RETRIES=2` [CODE](handler.py:12273)), not delivered.

---

# SECTION K — RE-EDIT / SURGICAL

## K51. The complete RE-EDIT path

**Modes** (`input_data.mode`) [CODE](handler.py:35044-35045): `full` · `render_only` · `tweak` · `guided_redraft` · `reinterpret` · `resume_ask`.

**Who classifies:**
- **Server (content-studio) does NOT classify natural language.** It sets mode purely from whether a saved plan exists: `const mode = hasSavedPlan ? 'tweak' : 'reinterpret'` [CODE](/Users/zaclibman/content-studio/server.js:4351-4352), and forwards `change_request` raw [CODE](/Users/zaclibman/content-studio/lib/video-processor/dispatch-to-modal.js:589, 613).
- **Worker classifies** inside `generate_plan_diff` [CODE](handler.py:18212) via a Gemini call that emits `tweak | guided_redraft | reinterpret | needs_clarification` [CODE](handler.py:18493), with a **deterministic zero-model fast path** `_deterministic_reedit` [CODE](handler.py:17745) for pure category-off / caption-style swaps.

**What runs per mode** (dispatch at [CODE](handler.py:35554-35652)):
- `tweak`: `generate_plan_diff` [CODE](handler.py:35557); on `tweak` classification → `provided_plan = diff.new_plan; mode = "render_only"` [CODE](handler.py:35588-35591) + Layer-3 validate/revert [CODE](handler.py:35602-35624). On `needs_clarification` → terminal `needs_input` + question [CODE](handler.py:35575-35587). On `guided_redraft` → fuse vibe, keep prior plan as soft default [CODE](handler.py:35625-35642). On `reinterpret`/fallback → fuse vibe, drop prior plan [CODE](handler.py:35643-35652). A `generate_plan_diff` exception **degrades to reinterpret**, never hard-fails a paid re-edit [CODE](handler.py:35563-35572).
- `render_only`: skip recipe, render provided plan verbatim (`_skip_edit_gen`) [CODE](handler.py:35079, 35161).
- `guided_redraft`: full pipeline with `prior_plan` injected into `generate_edit_gemini` as soft default + scoped-copy of out-of-scope layers [CODE](handler.py:13097, 17804-17843, 18033).
- `reinterpret`: full pipeline from source, no carry-over.
- `resume_ask`: restore saved plan+transcript from `partial_state`, fold the ask answer, re-route to full or render_only [CODE](handler.py:35120-35156).

## K52. Path that MUTATES a plan WITHOUT re-planning

Yes — two:
1. **`render_only`** replays a provided `edit_plan` verbatim (deepcopy, no Gemini) [CODE](handler.py:35079, 35161-35162).
2. **`_deterministic_reedit`** [CODE](handler.py:17745-17801) — ZERO model calls. Vocabulary is narrow and conservative (every fragment must match or it falls to the model rail [CODE](handler.py:17774-17775)):
   - Category-OFF for exactly seven components via `_REEDIT_OFF_PATTERNS` [CODE](handler.py:17656-17664): `captions, broll, sfx, zoom, motion_graphics, text_overlays, transitions` (applied by `_enforce_off_expressive_features` [CODE](handler.py:12721)).
   - Caption-style SWAP to a `VALID_CAPTION_STYLES` value [CODE](handler.py:17766-17773).
3. **`tweak`-mode plan-diff** [CODE](handler.py:18212) is model-assisted but is still a byte-identical-echo MUTATION of the existing plan, not a re-plan. Its supported vocabulary (from the prompt [CODE](handler.py:18300-18428)):
   - REMOVE (empty an array, or drop a referenced entry), ADD (append new entry), REPLACE (edit a referenced entry) across: caption_style, sound_effects, broll_clips, emphasis_moments (+zoom_effect), motion_graphics, text_overlays, tight_cut_overlays.
   - Reference syntax: ordinal ("2nd zoom"), temporal ("zoom at 12.5s"), word-based ("zoom on 'finally'"), type+position composite [CODE](handler.py:18344-18358).
   - Composite multi-op requests in one emission [CODE](handler.py:18362-18365).
   - Everything the user did not touch is preserved byte-identical [CODE](handler.py:18409-18421).
   - USER-OBEDIENCE negatives (`_parse_off_features` [CODE](handler.py:17667), `_parse_sound_negatives` [CODE](handler.py:17705)) strip components deterministically AFTER the model, regardless of the EditPolicy flag [CODE](handler.py:13153-13160).

## K53. What a user can ask that this path CANNOT express (the product gap)

Within the surgical/tweak lane (things that force a re-plan, a capability-note, or a silent no-op):
- **Add a transition** — explicitly NOT addable in tweak; the model is told to "acknowledge the ask in notes and leave transitions untouched" [CODE](handler.py:18320-18322). Transitions are authored only in a dedicated seam pass.
- **Re-cut / change WHICH words are removed** — tweak preserves `cuts`/`remove_words` byte-identical; changing the cut set requires `guided_redraft`/`reinterpret` (a full re-plan), not the surgical path [CODE](handler.py:18409-18414).
- **Shift a raw timestamp / hold a shot N ms longer at a non-word boundary** — everything is word-index anchored; "never invent or shift a raw timestamp" [CODE](handler.py:18418). Sub-word timing asks are inexpressible.
- **New footage that isn't in the source and isn't a Pexels keyword** — b-roll only resolves a Pexels search term [CODE](handler.py:19908-19911); no generated cutaways on non-premium.
- **Change what is SAID / edit audio content / add music / voiceover** — not an edit surface. Detected and surfaced as unsupported by `_parse_unsupported_requests` [CODE](handler.py:330), whose fixed list is: color grading, background music, voiceover/AI narration, aspect-ratio change, logo/watermark, AI-generated images [CODE](handler.py:309-327).
- **Aspect ratio other than 9:16, logo/watermark, LUT/color-grade beyond `color_effect`** — same unsupported list [CODE](handler.py:318-323).
- **AI-generated scenes on a non-premium job** — premium-only fork; routed to a "doesn't support yet" note on Flare [CODE](handler.py:38782-38784).
- **Caption text override for a mis-spoken/misspelled word** (e.g. job 2026-07-24 "Change 'rise' to 'ryze'") — captions derive from transcript words; a literal caption-text substitution is not in the tweak op vocabulary [INFERRED from op list at handler.py:18300-18336, which has no caption-text-edit op].

## K54. Where the instruction is READ, and where LOST

READ (the trace):
- Client → `change_request` [CODE](/Users/zaclibman/content-studio/server.js:4172) (hard-required [CODE](server.js:4304)).
- Stored to DB `change_request` column at dispatch [CODE](/Users/zaclibman/content-studio/lib/video-processor/dispatch-to-modal.js:613); payload key `change_request` [CODE](dispatch-to-modal.js:589) + `old_vibe` [CODE](dispatch-to-modal.js:590).
- Worker reads `change_request` [CODE](handler.py:35108) and `old_vibe` [CODE](handler.py:35109).
- `tweak` → `generate_plan_diff(change_request=…)` [CODE](handler.py:35559) → into the plan-diff Gemini prompt "USER CHANGE REQUEST:" [CODE](handler.py:18428).
- `guided_redraft` → `prior_plan_change_request` into `generate_edit_gemini` [CODE](handler.py:13097, 13215) → GUIDED REDRAFT prompt block [CODE](handler.py:7149).
- `reinterpret` → fused into `vibe` [CODE](handler.py:35646).
- HONESTY fold: `change_request` is concatenated into `_honesty_intent_text` so unsupported asks in a re-edit still surface [CODE](handler.py:38735-38740).

LOST / at-risk:
- The new re-edit job's **`vibe_input` keeps the PARENT's old vibe, not the change request** [CODE](/Users/zaclibman/content-studio/server.js:4361). The instruction lives ONLY in `change_request`; any downstream reader keying off `vibe`/`vibe_input` misses it. The worker itself flags this hazard: on a surgical re-edit "`vibe` is the stale original" [CODE](handler.py:38736).
- Conditional forwarding: `change_request`/`old_vibe` are spread into the payload only when truthy, `mode` only when `!= 'full'` [CODE](dispatch-to-modal.js:583, 589-590) — a `full`/empty dispatch silently omits them (guarded by the endpoint's hard-require, so real re-edits always carry it) [MEASURED: all 7 re-edit rows carry change_request].

## K55. What happens when a request cannot be fulfilled — is the user told? counted?

- **Ambiguous/vague** → `needs_clarification`: worker returns a terminal `needs_input` status + `clarification_question` [CODE](handler.py:35575-35587]; legacy path marks the job `failed` with the question in `error_message`/`change_summary` [CODE](dispatch-to-modal.js:811-822).
- **Understood-but-unsupported** → a `capability_notes` string the user reads ("Promptly doesn't support X yet.") [CODE](handler.py:330-340, 38740).
- **B-roll subject not found** → "Couldn't find footage for '…' — the rest of your edit is done." [CODE](handler.py:38756).
- **Counted:** every intake turn-away is logged to the divergence/turn-away table via `_log_intake_reject` [CODE](handler.py:30011-30033]; `capability_notes` persist in `result` jsonb [CODE](handler.py:38863-38864]. There is NO metric that counts "% of re-edit asks honored" (see M64).

## K56. Passes that can SILENTLY UNDO an explicitly requested change

- **`apply_scalar_reverts`** [CODE](handler.py:35617) after a tweak: `validate_reedit_changes` [CODE](handler.py:18759) flags out-of-scope drift and Phase-1 auto-reverts top-level SCALAR drift (`caption_style`, `thumbnail_word_index`, `outro`) [CODE](handler.py:35593-35622]. If the classifier mislabels a genuinely-requested scalar change as out-of-scope, this reverts it. (Array-level drift is only logged, not reverted [CODE](handler.py:35598-35600].)
- **`guided_redraft` scoped-copy** [CODE](handler.py:17804-17843, 18033): every OUT-OF-SCOPE layer is overwritten with the prior plan verbatim. A model change to a layer the classifier deemed out-of-scope is discarded. (guided_redraft's own out-of-scope contract is soft — LOGGED not reverted [CODE](handler.py:18959, 18969-18983).)
- **`_enforce_off_expressive_features` / `_parse_off_features`** [CODE](handler.py:12721, 17667): a user negative deterministically strips a whole component category AFTER Gemini. A false-matching negative regex would strip a component the user actually wanted (the intended behavior is a feature; the false-match is the risk).
- **EditPolicy enforcement** (premium/flag) strips off-features post-merge [CODE](handler.py:13135-13160).
- **Degen re-roll / QA judge** can drop enhancements: `enhancements_dropped` appears in real result rows [MEASURED — seen in a sampled `result`]; premium QA drops generated scenes below the 0.6 floor [CODE](handler.py:10746, 34195-34320).

---

# SECTION L — GENERATION / ADAPTERS

## L57. Generation capability NOW (vendor · cost · latency · wired? · fired how often)

| Capability | Vendor / model | Cost | Wired? | Fired [MEASURED] |
|---|---|---|---|---|
| **Image gen** | Nano Banana Pro `gemini-3-pro-image` via Vertex [CODE](handler.py:10182) | ~$0.14/img [CODE](handler.py:10185) | **DARK / premium-only** (`route_premium`, default off; call site [CODE](handler.py:38136, 38195)) | **2 of 6,338 jobs** shipped a non-empty `generated_scenes` (832 rows carry the key, only 2 non-empty) |
| **Video gen** | Veo 3.1 (Vertex) | — | **INERT** — reachability probe only, no job caller [CODE](modal_app.py:1928-1973) | 0 |
| **TTS** | none in prod; macOS `say` in cert harnesses only [CODE](modal_app.py:2152) | — | NONE | 0 |
| **ASR alt** | ElevenLabs Scribe (speech-to-TEXT, not TTS) [CODE](handler.py:4517-4541) | ElevenLabs [UNKNOWN $] | **DARK / flag-gated** (`_scribe_enabled` + key) [CODE](handler.py:4509) | [UNKNOWN — flag state] |
| **Avatars** | — | — | NONE (pipeline consumes talking-heads, never generates one) | 0 |
| **Matting** | inline white/black triangulation `_recover_alpha_from_white_black` [CODE](handler.py:10645); **no `promptly-matting` sibling app exists** | $0 | **DARK / premium gen fork** [CODE](handler.py:10719, 38136) | ≤2 (rides the 2 generated scenes) |
| **Stock footage** | Pexels video search [CODE](handler.py:19908-19911), key `PEXELS_API_KEY` | Pexels free API | **WIRED-TO-PROD**: `prefetch_and_verify_broll` [CODE](handler.py:20573) called at [CODE](handler.py:38508) | **180 jobs, 270 clips** (180 non-empty `resolved_broll`; 180 of 854 recipes with a `broll_clips` key). Content-QA gate `_verify_broll_content` [CODE](handler.py:20485) is **DARK** [CODE](handler.py:20475-20482) |

Denominator note: recipe-persisting jobs total 1,286 (`edit_recipe` not null [MEASURED]); completed jobs 3,949. So Pexels b-roll fired on 180/1,286 ≈ 14% of recipe-bearing jobs, ≈4.6% of completed jobs [MEASURED]. Generated scenes: 2/6,338 ≈ 0.03% [MEASURED].

## L58. Image gen quality-floor · QA judge · repair loop

- **Quality-floor prompt** `_IMAGE_SYSTEM_PROMPT` [CODE](handler.py:10197): "You render bespoke graphics for a premium short-form video — the caliber of a product-render or motion-graphics studio… The lines below are the craft floor every image meets" with CALIBER / PALETTE / LIGHT & DEPTH / COMPOSITION / TEXT / REFERENCES / CLEAN-FIELD sections [CODE](handler.py:10197-10256).
- **QA judge** `_qa_judge_generated_scenes` [CODE](handler.py:10773], rubric prompt [CODE](handler.py:10795]: "You are a strict art director… score 0.0-1.0 on coherence / text_correct / on_palette / integration… a luxury edit ships NOTHING broken." Pass threshold `_QA_PASS_THRESHOLD=0.6` [CODE](handler.py:10746). Hero-asset variant `_qa_judge_hero_asset` [CODE](handler.py:11005).
- **Repair loop** `_perturb_scene_prompt` [CODE](handler.py:10878] feeds a repair note back; recovery re-render loop `_MAX_QA_ATTEMPTS=2` [CODE](handler.py:34195-34320].
- **Evidence it works:** [MEASURED] only 2 jobs ever shipped a generated scene; the `capability_notes` corpus shows the QA-drop honesty note ("generated versions didn't meet our quality bar") is a real emitted path [CODE](handler.py:38773-38777). So the judge/repair machinery is exercised but the whole fork is essentially untrafficked in production.

## L59. Still image as source? Multiple inputs?

- **Still image as source: NO.** Source is always a video downloaded to `source.mp4` [CODE](handler.py:35184, 35246); intake gates (NO_SPEECH/NOT_TALKING_HEAD) reject non-speech input. `source_type` distribution [MEASURED]: local 1,341 · icloud 60 · null 4,938 · **image 0**. The only still-image INPUTS are premium generation **reference images** (`ref_image_keys` → `_resolve_scene_ref_paths` [CODE](handler.py:10626)), not sources.
- **Multiple inputs: BUILT but PREMIUM/flag-gated and dormant.** `_multi_active = route_premium AND MULTI_INPUT_ENABLED AND ≥2 urls` [CODE](handler.py:35199-35207], concatenates via `_download_and_concat_sources` [CODE](handler.py:22000) — video concat only, no image branch. **Proven:** [UNKNOWN — no measured multi-input production job; flag dormant].

## L60. TTS integration? Pre-timed script path?

- **TTS: NONE** (L57).
- **Pre-timed script → synthesis: NONE.** There is a **pre-supplied transcript** path (`provided_transcript` [CODE](handler.py:35080], `_skip_transcribe` [CODE](handler.py:36767]) — WIRED for re-edit/resume/prewarm — but it describes EXISTING recorded audio and drives cuts/captions; it does not accept a script to be spoken/synthesized. No path turns text into timed audio [INFERRED from absence of any TTS caller].

## L61. Minimum input signature of the editorial core (`generate_edit_gemini`)

Signature [CODE](handler.py:13090-13107). **Mandatory positional (no default): `video_path`, `vibe`, `duration`.** Everything else is optional with a default: `trend_context, deepgram_words, shot_changes, shot_change_scores, vocal_emphasis, source_loudness, face_positions, smoothed_face_trajectory, user_style_profile, platform_style_note, gemini_file, cached_response, inline_video_bytes, video_reference_url, prior_plan, prior_plan_change_request, premium, resolved_policy, force_safe_reason, source_language, burned_text_override, recipe_deadline_s, density_override, density_variant, sample_fps_override, media_res_override`.

So to plan over footage it did NOT transcribe, the **strict** minimum is `video_path + vibe + duration`. BUT the architecture is speech-anchored: cuts are computed by `compute_mechanical_cuts` on the Deepgram word list [CODE](handler.py:13191-13198, 9577], and every plan `word_index` lives in the kept-only transcript index space [CODE](handler.py:13196-13197]. With `deepgram_words=None` the kept space is empty and the plan degenerates. **True FUNCTIONAL minimum = `video_path + vibe + duration + deepgram_words`** [INFERRED from the index-space construction]. The model watches the proxy via `inline_video_bytes`/`gemini_file`, so a visual-only plan would additionally need one of those.

---

# SECTION M — REQUEST FULFILLMENT

## M62. Machinery that parses the request into DISCRETE ASKS

Yes, several vibe/change-request parsers (all regex/keyword, worker-side):
- `_parse_off_features` — negatives → disabled component set [CODE](handler.py:17667).
- `_parse_sound_negatives` — specific-sound negatives ("no booms") [CODE](handler.py:17705).
- `_parse_broll_requests` / `_broll_request_directive` — explicit b-roll subjects [CODE](handler.py:260, 285).
- `_parse_unsupported_requests` — the 6 understood-but-unsupported capabilities [CODE](handler.py:330, 309-327).
- `_vibe_requests_generated_scene` — explicit bespoke/3D/AI-gen ask (with negation guard) [CODE](handler.py:360, 351-357).
- `_extract_proper_noun_keywords` — names for Deepgram boost [CODE](handler.py:35875).
- For re-edits, `generate_plan_diff` is the LLM parser that turns free text into discrete ops + a classification [CODE](handler.py:18212, 18300-18428).

Quality: precise for the enumerated negatives/subjects/unsupported set; the OPEN-ended "did the edit honor the vibe's intent" is delegated wholly to the Gemini editorial call — there is no structured decomposition of a generic vibe into an ask-checklist. The server does zero parsing (K51).

## M63. Machinery that reports what could NOT be done

- **`capability_notes`** — the honesty channel, assembled at [CODE](handler.py:38731-38786], surfaced into `result_payload` [CODE](handler.py:38863-38864] and every minimal-route delivery [CODE](handler.py:32537-32617, 32675]. Folds vibe + change_request [CODE](handler.py:38739].
- **`change_summary` / `human_summary`** — re-edit "what changed" one-liner [CODE](handler.py:18425, 35590]; stored to `change_summary` [MEASURED: 4 non-null].
- **`edit_rationale`** — user-facing "what I made" sentence, audited against the plan (`audit_edit_rationale` [CODE](handler.py:31443]) and persisted (`_persist_edit_rationale` [CODE](handler.py:31476]).
- **`post_package`** — {edit_rationale, post_caption, post_hook} [CODE](handler.py:31533-31574].
- **`clarification_question`** for ambiguous re-edits (K55).

## M64. Is FULFILLMENT counted anywhere?

**No true fulfillment fraction exists.** [MEASURED/INFERRED] There is no code computing "% of asks honored." The closest observable signals:
- `_log_intake_reject` turn-away divergence table (who couldn't get in) [CODE](handler.py:30011].
- `capability_notes` in `result` jsonb — [MEASURED] 3,807 rows carry the key; **2,030 non-empty**. But the overwhelming majority are minimal-route explainers, not unfulfilled asks. Note frequency [MEASURED]:
  - "No speech detected — cinematic mood-reel" ×679
  - "delivered complete and uncut" ×482
  - "speech couldn't be fully transcribed" ×286
  - "No speech detected — clean-cut re-edit" ×213
  - "delivered intact — already tight" ×89
  - **"doesn't support color grading" ×76 · "background music" ×72 · "AI-generated images" ×25 · "voiceover/AI narration" ×15 · "aspect ratio" ×6**
  - "clean-cut re-pace" ×72 · music-beat mood-reel ×54
- The genuine "we couldn't do what you asked" volume is therefore ~**194 unsupported-capability notes + N b-roll-miss notes** across 6,338 jobs [MEASURED, lower bound]. No aggregate is computed or stored.

## M65. Data on disk NOW a fulfillment judge could be built from

[MEASURED]
- **Re-edit pairs (explicit ask ↔ plan):** only **7 jobs** carry `change_request` (all `reedit_mode=tweak`, all with `parent_job_id`; **6 completed**), spread 2026-07-11 → 2026-08-03. Fields available per pair: `change_request`, parent's `edit_recipe`, this job's `edit_recipe`/`result`, `change_summary` (4 of 7). This is far too sparse for a statistical judge.
- **Vibe ↔ plan pairs:** **6,338 `vibe_input` (100%) ↔ 6,210 `result` / 1,286 `edit_recipe`** [MEASURED]. Every job pairs a free-text vibe with an outcome, but `vibe_input` is loose intent, not discrete asks.
- **Detected-ask ↔ outcome:** the 2,030 non-empty `capability_notes` rows pair a machine-detected ask class with the delivered handling [MEASURED].
- **Transcript/analysis on disk:** `transcript` and `analysis_data` columns exist per job for re-derivation.
- Period: full corpus 2026-06-25 → 2026-08-10 (~46 days) [MEASURED].

## M66. DESIGN (do not build) the cheapest fulfillment judge from that data

**Judge: "Vibe-Ask Honor Rate," an offline LLM-as-judge over stored (vibe_input, edit_recipe, capability_notes) triples.**
- **What it measures:** for each completed job, prompt one Gemini/Claude call to (1) decompose `vibe_input` (+ `change_request` for re-edits) into a discrete ask list, (2) mark each ask as HONORED / DROPPED-WITH-NOTE / DROPPED-SILENTLY / UNSUPPORTED, checking each against the `edit_recipe` arrays (broll_clips, emphasis_moments, caption_style, motion_graphics, text_overlays, transitions) and the emitted `capability_notes`. Output a per-job honor fraction and a per-ask-class tally. The key product number is **DROPPED-SILENTLY count** (asks neither honored nor noted) — the exact failure the honesty mechanism exists to kill.
- **Cost per run:** one LLM call per job, input ≈ vibe + a JSON-compact recipe (recipes are small). ~6,000 jobs × ~1 call. At a cheap model this is a few dollars for the whole back-catalog and pennies/day incrementally — **no Modal/GPU spend, pure API, run from the content-studio box against the DB** (respects the no-synthetic-spend law; it reads existing rows only).
- **What it CAN'T see:** (a) whether an HONORED-on-paper ask actually looks right in the rendered pixels (it reads the recipe JSON, not the video) — Rule 3 frame-truth is out of scope; (b) asks the user never phrased explicitly (implicit taste); (c) the 5,052 jobs with null `edit_recipe`/`source_type` where the recipe wasn't persisted — coverage is bounded by the 1,286 recipe-bearing rows; (d) re-edit honor at scale (only 7 pairs exist). It is a **recall-of-stated-asks** meter, not a quality meter — and its ground truth for "unsupported" is only as complete as the 6-item `_UNSUPPORTED_CAPABILITIES` list.

---

## Contradictions / flags found
- **Rule-0 doc vs. code:** the standing "only permitted rejections are `<2.0s` and `>300s`" is now TRUE in code (zero-reject LIVE), but the intake floor constant is still `_MIN_SOURCE_DURATION_S=5.0` [CODE](handler.py:30003) — only reachable when zero-reject is OFF; with the live flag the real floor is `_MIN_MINIMAL_DURATION_S=2.0` [CODE](handler.py:31698). Not a bug, but two floors coexist.
- **vibe_input carries the wrong text on re-edits** (K54) — a latent silent-drop hazard the honesty fold [CODE](handler.py:38739) patches only for the capability-note channel, not for any reader keying off `vibe_input`.
- **Re-edit is effectively unused:** 7 re-edit jobs / 6,338 total (0.11%) [MEASURED] — the entire tweak/guided_redraft/reinterpret apparatus (K51-K56) has almost no production traffic to validate against.
# Recon N/O/P — Errors & Reliability, Latency, Cost

Repo: /Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker (branch zero-reject-routing, .last_deployed_commit a324b7d1).
DB: content-studio Supabase `video_jobs`. Read-only SELECT via node+dotenv.
Tags: [MEASURED] = queried from DB / read from code output · [CODE](file:line) · [INFERRED] · [UNKNOWN].

Windows used (anchored to real now = 2026-08-10T02:18Z; DB latest row 2026-08-10T02:18Z):
- **7d** = created_at ≥ 2026-08-03T02:18Z (CLEAN — post the 07-30/07-31 outage).
- **30d** = created_at ≥ 2026-07-11T02:18Z (CONTAMINATED by a 25h render-service outage 07-30/07-31; always reported both raw and ex-outage).
- Table totals [MEASURED]: 6339 rows; status alltime = completed 3949, failed 2300, canceled 87, needs_input 1, queued 1, processing 1. Earliest 2026-06-25, latest 2026-08-10.

---

## SECTION N — ERRORS & RELIABILITY

### N67. Every error class + sub-code the pipeline produces

Two producers: (A) the **worker** `classify_error()` in handler.py (exception → structured code), and (B) the **server** (content-studio) — dispatch failures and the reaper, which write codes the worker never sees.

**(A) Worker `classify_error()`** — [CODE](handler.py:30153). Each returns `{error_code, error_subcode, error_cause, user_message, retryable, requires_new_video, requires_vibe_change}`. Sub-codes from `_ERROR_SUBCODES` [CODE](handler.py:30043); `unclassified` is the finding-signal [CODE](handler.py:30134). Ordered matching (earlier sentinels win):

| error_code | cause | ours vs external | retryable | refunded | user sees | cite |
|---|---|---|---|---|---|---|
| INTEGRITY_TRIP | post-render inspection tripped (black/freeze/dead_moment tail) | OURS | yes | yes (designed) | "caught a rendering defect on our side… credit returned" | handler.py:30207, subcodes 30115 |
| RECIPE_INVALID | recipe repair loop exhausted (safe recipe failed validation) | OURS | yes | (rescue-deny) | "edit plan didn't pass validation… run again" | 30222 |
| SAFE_EDIT_FAILED | deterministic safe-edit construction/plan-build raised | OURS | yes | yes | "simplified backup edit didn't come together… credit returned" | 30236; raise sites 13828/17482 |
| CONTAINER_TEARDOWN | container reclaimed mid-render (upstream Gemini ReadTimeout tore request down; interpreter finalizing) | infra | yes | yes | "temporary infrastructure interruption… run again" | 30254 |
| PLATFORM_TIMEOUT | platform preemption/timeout (catchable subset; most are SIGKILL → server reaper writes it) | infra | yes | yes (designed) | "interrupted by our infrastructure — you weren't charged" | 30268 |
| RENDER_FATAL | render ladder exhausted / empty output / frame-grid / concurrency. Subcodes: canon_unreadable, empty_mux, empty_output_*, concurrency, frame_grid, no_video_stream, compositor, delay_render, render_timeout, av_drift, caption_schema | OURS | yes | yes | "rendering failed even after a simplified retry" | 30281/30288/30295/30308; subcodes 30044 |
| RENDER_REMOTION | plan-independent Remotion failure. Subcodes: concurrency, no_video_stream, compositor, delay_render, component_crash, oom, browser_launch | OURS | yes | (not designed-reject) | "trouble rendering your video… try again" | 30524/30625; subcodes 30062 |
| RENDER_FFMPEG | ffmpeg failure — every one observed 07-31..08-04 was an ANALYSIS subprocess hitting a per-stage timeout on 4K HEVC (scdet/face/loudness/silence/black/freeze/proxy/normalize/composite) | OURS | yes | yes | "trouble rendering… try again" | 30619; subcodes 30085 |
| RENDER_TOO_SHORT | output-length guard tripped (sub-second render held back) | OURS | yes | yes | "result came out too short… held it back, credit returned" | 30609 |
| TRANSCRIPTION_INCOMPLETE | large part of speech untranscribed (usually unsupported language). Subcodes: untranscribed_speech, no_speech_muted | mixed (input lang, our engine) | no | yes (designed) | "couldn't transcribe a large part… stopped instead of cut-up edit, credit returned" | 30392; subcodes 30105 |
| TRANSCRIPTION_EMPTY | VAD-confirmed speech but ASR returned nothing (our engine) | OURS | yes | yes | "couldn't transcribe… that's on us, not your clip" | 30408 |
| TRANSCRIPTION | Deepgram/transcription failed. Subcodes: keyterm_limit, write_timeout, read_timeout, empty_transcript | mixed | no | yes (designed) | "trouble understanding audio… clearer speech" | 30551; subcodes 30109 |
| NO_SPEECH | no speech in clip | input | no | yes (designed) | "couldn't hear any speech… upload a clip of someone speaking" | 30416 |
| NO_SPEECH_NONENGLISH | non-English speech in denylisted script | input | no | yes (designed) | "we heard you speaking {lang}… support coming soon" | 30360 |
| NO_SPEECH_FACE | face present, no audible words (mic/inaudible) | input | no | yes (designed) | "can see you but couldn't pick up clear speech… check mic" | 30385 |
| NO_AUDIO_TRACK | no audio stream | input | no | yes (designed) | "no audio track… add audio and resubmit" | 30422 |
| NOT_TALKING_HEAD | talking-head gate failed | input | no | (designed) | "Promptly edits talking-to-camera videos" | 30442 |
| CLIP_TOO_LONG | source ≥ cap (300s) | input | no | yes (designed) | "edits videos up to N minutes… pick your best N min" | 30316 |
| CLIP_TOO_SHORT | source < floor (2.0s zero-reject min) | input | no | yes (designed) | "only a few seconds… needs at least N seconds" | 30347 |
| WRONG_ORIENTATION | landscape video | input | no | (designed) | "works with vertical 9:16" | 30537 |
| INVALID_FORMAT | no video stream / Gemini proxy encode failed / corrupt. **PROVENANCE GATE**: a render-stage marker reclassifies to RENDER_REMOTION (a render failure is never a bad file) | input (if genuine) | no | yes (designed) | "couldn't read this video file… re-export" | 30434/30531; provenance gate 30514 |
| INVALID_SOURCE_URL | malformed S3 URL | OURS/infra | no | yes (designed) | "video reference was malformed… upload again" | 30428 |
| EMPTY_UPLOAD | no video data provided | client | yes | | "didn't upload correctly… try again" | 30543 |
| UPLOAD_NEVER_STARTED | pre-spawn source gate: source never arrived on S3. Subcode source_absent | client network | yes | yes | "video didn't finish uploading" | 30451; subcodes 30124 |
| UPLOAD_STALLED | upload interrupted before finishing | client network | yes | (not designed) | "upload was interrupted… check connection" | 30457 |
| UPLOAD_TIMEOUT | source didn't arrive on S3 in time | client network | yes | | "upload didn't finish in time" | 30463 |
| S3_ACCESS / S3_GENERIC | NoSuchKey/AccessDenied / BotoCore/ClientError | infra | yes | | "trouble accessing/downloading your video" | 30469/30475 |
| NETWORK | ConnectionError / Read timed out | infra | yes | | "network hiccup" | 30483 |
| RATE_LIMIT | 429 / quota / TooManyRequests | external | yes | | "temporarily at capacity" | 30489 |
| DISPATCH_UNREACHABLE | Modal dispatch threw (unreachable). Subcodes never_spawned (NEVER_SPAWNED), ran_and_lost (RAN_AND_LOST) | infra | yes | yes | dispatch copy | subcodes 30127; server-written (below) |
| EDITOR_TIMEOUT | Gemini file upload timed out / DEADLINE_EXCEEDED | external | yes | | "our editor took too long" | 30559 |
| EDITOR_PARSE | empty/invalid Gemini JSON | external | yes | | "trouble generating your edit" | 30565 |
| EDITOR_GENERIC | any other Gemini/GEMINI_API_KEY | external | yes | | "editor service had a hiccup" | 30571 |
| EMPTY_EDIT | missing cuts / removed all words / no clips remain | OURS | yes | (vibe) | "couldn't generate an edit… try a different vibe" | 30579 |
| PLAN_INVALID / PLAN_VALIDATION | source_start/end/chronological / pydantic ValidationError | OURS | yes | | "trouble generating your edit" | 30587/30593 |
| BROLL | Pexels / broll fetch | external | yes | | "trouble finding cutaway footage" | 30633 |
| MISSING_FIELDS | mode/input missing at entry. Subcode mode_input_missing | OURS | — | | (internal) | 34929/35175 |
| TIER_CONCURRENCY | premium multi-clip concurrency gate | designed | — | | tier-gate | 34957 |
| UNKNOWN | unmatched — logs `[error-fallback]` loudly, PAGES operator | OURS (unowned) | yes | | "Something went wrong" | 30644 |

**(B) Server-side (content-studio) codes** — NOT in the worker classifier:
- **JOB_STALLED** — reaper: a `processing` job whose `updated_at` passed its per-stage lease. [CODE](lib/job-reaper.js:156,162) writes `result:{error_code:'JOB_STALLED', reaped:true}`, refunds via claim-gated leg, owner [ALERT] + lifecycle push.
- **PLATFORM_TIMEOUT** (server variant) — reaper: `processing` job past EXEC_WALL_MS = 55min on `started_at`. [CODE](lib/job-reaper.js:60,156).
- **DISPATCH_UNREACHABLE** — outer dispatch catch when the Modal fetch throws (network/unreachable). [CODE](lib/video-processor/dispatch-to-modal.js:661,710), copy at lib/failure-copy.js:16. Written via `markJobFailed(errorCode,...)` [CODE](dispatch-to-modal.js:237) → `result:{error_code, retryable:false}`, refunded inline.
- **"Modal error: 404" / RENDER_UNAVAILABLE** — Modal returned non-ok at dispatch; [CODE](dispatch-to-modal.js:738-772) writes **only `error_message`, `result` stays NULL** (no error_code). This is why these are UN-groupable by code (see N72).
- **UPLOAD_NEVER_STARTED / JOB_NEVER_STARTED** — a source-arrival watcher: waits ~600s (`waited_s:600`) for the S3 source, then fails with `modal_spawned:false`, `source_key`, `error_class`, `error_where`. [UNKNOWN — the exact writer is NOT in content-studio lib/server.js/api; row shape indicates a source-arrival watcher in another service (iOS backend or edge fn)]. handler.py owns only the classify branch + subcode "pre-spawn source gate" (30124/30451).

---

### N68. Measured rates per class — 30d and 7d [MEASURED]

Grouped on `result.error_code`; window on `created_at`. **Rule 7: users listed alongside jobs.**

**FAILED [30d] n=2299 jobs / 1398 users** (RAW — includes the 07-30/07-31 outage):
```
(no result.error_code)   jobs=1157  users=570   ← 1121 are the Modal-404 outage (see N-outage)
UPLOAD_NEVER_STARTED     jobs= 367  users=336   (only 71 ever dispatched)
NO_SPEECH                jobs= 198  users=151
UPLOAD_STALLED           jobs=  98  users= 38   ← retry-inflated (98 jobs / 38 users = 2.6x)
CLIP_TOO_SHORT           jobs=  59  users= 55
INTEGRITY_TRIP           jobs=  52  users= 38
NO_SPEECH_NONENGLISH     jobs=  47  users= 35
RENDER_FATAL             jobs=  44  users= 35
RENDER_FFMPEG            jobs=  38  users= 17   ← 2.2x
TRANSCRIPTION_INCOMPLETE jobs=  38  users= 27
NO_SPEECH_FACE           jobs=  30  users= 28
DISPATCH_UNREACHABLE     jobs=  30  users= 24
NO_AUDIO_TRACK           jobs=  27  users= 22
NOT_TALKING_HEAD         jobs=  18  users= 16
CLIP_TOO_LONG            jobs=  17  users= 16
UNKNOWN                  jobs=  16  users= 15
JOB_NEVER_STARTED        jobs=  16  users= 14
INVALID_FORMAT           jobs=  12  users=  8
JOB_STALLED              jobs=  12  users= 12
RENDER_REMOTION          jobs=   9  users=  7
TRANSCRIPTION            jobs=   5  users=  4
RENDER_TOO_SHORT         jobs=   4  users=  3
TIER_CONCURRENCY         jobs=   2  users=  2
RECIPE_INVALID           jobs=   2  users=  1
PLATFORM_TIMEOUT         jobs=   1  users=  1
```

**FAILED [7d] n=487 jobs / 424 users** (CLEAN, post-outage):
```
UPLOAD_NEVER_STARTED     jobs=347  users=316   (client source never arrived; only 51 dispatched, ALL modal_spawned=false)
DISPATCH_UNREACHABLE     jobs= 26  users= 21
INTEGRITY_TRIP           jobs= 20  users= 19
RENDER_FFMPEG            jobs= 19  users= 10   ← 1.9x
RENDER_FATAL             jobs= 18  users= 16
JOB_NEVER_STARTED        jobs= 16  users= 14
CLIP_TOO_SHORT           jobs= 14  users= 13
JOB_STALLED              jobs= 12  users= 12
RENDER_REMOTION          jobs=  7  users=  6
INVALID_FORMAT           jobs=  5  users=  2   ← 2.5x
TRANSCRIPTION            jobs=  3  users=  2
```
All classes report refunded = job-count (every failed row carries a refund; the reaper/dispatch legs refund) [MEASURED].

**Modal-404 OUTAGE cohort** [MEASURED]: 1121 jobs / **547 users** over 2026-07-30 07:19Z → 07-31 08:28Z (~25h; 833 jobs on 07-30, 288 on 07-31). Retry inflation: max 33 jobs by one user, median 1, 110 users hit it ≥3x → 2.05x job/user multiplier. **Lead with 547 users, not 1121 jobs.** Cause: dispatch got HTTP 404 from the Modal render endpoint (render service unreachable/undeployed). result=NULL so invisible to code-grouping (N72).

**Clean 30d our-fault EXCLUDING the outage, designed-rejects and client-upload = 262 jobs / 182 users** [MEASURED]:
INTEGRITY_TRIP 52, RENDER_FATAL 44, RENDER_FFMPEG 38, "trouble reaching render service"(no code) 33, DISPATCH_UNREACHABLE 30, UNKNOWN 16, JOB_NEVER_STARTED 16, JOB_STALLED 12, RENDER_REMOTION 9, RENDER_TOO_SHORT 4, TIER_CONCURRENCY 2, RECIPE_INVALID 2, "render hit time limit"(no code) 2, PLATFORM_TIMEOUT 1, "re-dispatch aborted" 1.
Two families: **render (INTEGRITY_TRIP+RENDER_FATAL+RENDER_FFMPEG+RENDER_REMOTION+RENDER_TOO_SHORT = 147 jobs)** and **dispatch/orphan (DISPATCH_UNREACHABLE 30 + JOB_NEVER_STARTED 16 + JOB_STALLED 12 + no-code render-reach 33/2/1 = ~94 jobs)**.

---

### N69. CLEAN COMPLETION RATE — explicit denominators, per-user AND per-job [MEASURED]

**Denominator caution (the misdescribing field):** `started_at` is stamped at **dispatch-ATTEMPT**, not at worker-run. UPLOAD_NEVER_STARTED rows carry `started_at ≈ created_at+0.2s` with `modal_spawned=false` — the job never ran. So "started_at ≠ null" is NOT "entered the pipeline"; a naive "started = ran" denominator overcounts real pipeline entries by the never-spawned jobs. The only clean "did compute" signals are: completed rows (0/2712 have null timestamps [MEASURED]) or failed rows with `modal_spawned=true` (which none of the 7d UPLOAD_NEVER_STARTED have). This is exactly the trap flagged.

**7d [MEASURED]** — ALL created = 3263 jobs / 2806 users:
- completed 2712 j / 2442 u · failed 487 j / 424 u (input-reject 22, client-upload 347, our-fault 118) · canceled 62 j / 60 u (user aborts) · needs_input 0 · queued/processing 2 · never-dispatched (started_at null) 304 j / 275 u.
- **RATE A** completed / ALL created = 2712/3263 = **83.1%** (denominator = every row created, incl. client-never-uploaded + user aborts).
- **RATE B** completed / (ALL − input-reject − client-upload) = 2712/2894 = **93.7%** (removes designed rejections + the client's own dropped uploads).
- **RATE C** completed / dispatched(started≠null) = 2712/2959 = **91.7%** (but "dispatched" is contaminated by the 51+ never-spawned UPLOAD_NEVER_STARTED — see caution; the honest "completed / actually-ran" is between B and C, ≈ 2712/2830 = **95.8%** using completed + our-fault-failures only).
- **PER-USER (lead)**: 2806 users, 2442 got ≥1 completed video, **364 users (13.0%) got nothing in 7d**. Per-job "got nothing" = 551/3263 = 16.9%. **Lead: 13.0% of users, not 16.9% of jobs.**

**30d [MEASURED]** — ALL created = 6253 / 4542 users (CONTAMINATED by outage):
- completed 3865 (61.8% of all) · failed 2299 · canceled 86 · never-dispatched 321.
- RATE A = 3865/6253 = **61.8%** raw; **but 1121 of the failures are the 25h outage** — excluding it, completed/(6253−1121) = 3865/5132 = **75.3%**, and RATE B (also ex input-reject 451 + client-upload 465) = 3865/(5132−451−465) = 3865/4216 = **91.7%**.
- PER-USER: 4542 users, 3347 with ≥1 completed, **1195 users (26.3%) got nothing** — but 547 of those were the outage. Ex-outage the never-completed user count drops toward the 7d ~13%.

**Verdict:** steady-state (7d) completion is ~93-96% once client-upload-never-arrived and user aborts are removed; the headline 83.1%/61.8% is dragged down by (a) 347 client uploads that never reached S3 and (b) the resolved 25h outage.

---

### N70. Fallbacks / retries / degrade ladders — masking? ever worse than failing loud?

1. **Render degrade ladder** [CODE](handler.py:22592,29517,29830) — after a render crash, drops decorations rung by rung and re-renders; if the failure is plan-independent (frame-grid, concurrency, teardown) it FAILS FAST instead of thrashing dead rungs [CODE](handler.py:22624 `_ladder_failure_is_plan_independent`). Terminal = RENDER_FATAL. **Not masking** — exhaustion surfaces a named, refunded, alerting class. Good.
2. **Safe-edit (deterministic `build_safe_recipe`)** [CODE](handler.py:13763) — the zero-fatal rung when the Gemini recipe stage fails; its OWN failure = SAFE_EDIT_FAILED (honest, refunded) rather than UNKNOWN [CODE](handler.py:13821).
3. **Outer safe-edit rescue** `_outer_safe_rescue` [CODE](handler.py:31110) — ONE guarded whole-handler re-run with the safe marker for eligible failures (codes NOT in `_OUTER_RESCUE_DENY` [CODE](handler.py:31039)). Denied for re-edits (a bare safe edit would DOWNGRADE a delivered re-edit — a WORSE outcome, correctly avoided) and for irreducible/infra classes. Records a divergence ledger entry. Risk: converts a would-be failure into a plainer edit — a quality (not reliability) downgrade, only on full mode.
4. **Moodreel → minimal fail-safe** [CODE](validate_deploy.py:6699) — every moodreel miss fail-safes to minimal; "a moodreel attempt can never cost a user their video." Byte-identical when no curve. Good.
5. **ASR ladder: Deepgram → ElevenLabs Scribe** (PROMPTLY_ASR_SCRIBE=1 live) — on a coverage-gate failure, route Scribe and keep the better-coverage transcript before rejecting (bake-off deepgram 3/40 → scribe 34/40). Deepgram runs first + unchanged so a Scribe outage can't cost a job. Good.
6. **Language routing** (PROMPTLY_LANG_ROUTING=1) — coverage fail → Gemini language-ID → Deepgram monolingual, recovers non-English into native captions instead of rejecting.
7. **Gemini video-reference → inline-bytes fallback** (LEVER 4) [CODE](handler.py:13276) — reference URL fails → retry inline, ledgered; "ships slow, never fails." Trades latency for reliability. Good.
8. **render_burst staging hiccup** — FAILS RETRYABLE (`render_burst_staging_failed`); the old in-process fallback was **disarmed** because run_pipeline_bg is now 12GiB and would OOM [CODE](handler.py:24705,24717; validate_deploy.py:7170). Correct: an in-process fallback here would be WORSE (OOM crash) than a clean retryable fail.
9. **Dispatch retry** `fetchModalWithRetry` — 3 attempts spanning the cold-start window (12s/22s backoff) [CODE](dispatch-to-modal.js:720-731). Masks transient cold-start 404s, but did NOT save the 07-30 outage (persistent 404 = service down, not cold start) — 1121 jobs still died.
10. **Completion-callback fallback** [CODE](dispatch-to-modal.js:795-802) — primary `/api/modal-complete` POST + platform webhook, else a 900s (`timeoutMs 15min`) fallback reconstructs completion from the worker's durable Supabase write. **THIS ONE PRODUCES A WORSE-THAN-NECESSARY OUTCOME (silently):** 41 completed jobs in 7d settled at e2e ≈900s while their render finished at median ~206s (N71/O76). The video is delivered ~700s late, masking a missed-callback root cause with no distinct signal on the row.

---

### N71. What can fail SILENTLY (signature mode) [CODE]/[MEASURED]

- **The worker's own durable status layer is DARK and mis-targeted.** `write_job_status` no-ops unless `JOB_STATUS_WRITES_ENABLED` (default OFF) [CODE](handler.py:30697,30717); and it writes table `PROMPTLY_JOB_TABLE` default **`jobs`**, not `video_jobs` [CODE](handler.py:30726). PostgREST silently DROPS writes to unknown columns/tables. So all worker-side progress/partial_state writes are inert; truth is the server writing `video_jobs`. An entire telemetry layer ships gate-green and does nothing (Rule 2 precedent).
- **Dispatch 404 writes result=NULL** [CODE](dispatch-to-modal.js:744) — 1121 outage failures had no error_code/error_class → invisible to every by-code counter; only findable by scanning raw `error_message` (N72).
- **424 bare-swallow `except…: pass` + 290 fail-open/"best-effort"/"silently" markers** in handler.py [MEASURED grep]. Most are best-effort telemetry (ledger/alert/subcode) which is by-design; the hazard is any fallback whose degrade path has no ledger entry. `_error_subcode` itself swallows to `unclassified` [CODE](handler.py:30149) (safe by design).
- **Gemini degeneration retries burn compute inside SUCCESSFUL jobs, unsurfaced to the user:** 128/2711 7d completed jobs have `gemini_wasted_degen>0` (median ~80s wasted) [MEASURED]; 6 have `degen_retries>0`. Recorded in stage_timings but never alerts.
- **Completion-callback fallback settles at 900s with no distinguishing field** — the row looks like a normal completion (N70 #10). 41 jobs/7d.
- **markJobFailed / no-speech gate fail OPEN to dispatch** [CODE](server.js:196) — if the terminal write fails, the job proceeds; a failed mark is only logged.

### N72. Missing instrumentation (a known failure can't be diagnosed)

1. **Dispatch-side failures carry no `result.error_code`** — the Modal-404/non-ok path writes only `error_message` [CODE](dispatch-to-modal.js:744). A 1121-job / 547-user, 25-hour outage was uncountable by class; it surfaces only as a "(no result.error_code)" bucket that a by-code query drops. Fix = write `result:{error_code:'RENDER_UNAVAILABLE'|'MODAL_HTTP_'+status}`.
2. **`started_at` conflates dispatch-attempt with worker-run** — no clean "entered pipeline" timestamp on the row (completed rows have it; failed never-spawned rows ALSO have it). `modal_spawned` exists only on some failed rows, not on completed. Completion-rate denominators are therefore ambiguous.
3. **No burst-vs-in-process flag in stage_timings** — cannot tell which completed jobs paid the render_burst double-pay (cost reconstruction can't be exact — P78).
4. **Failed rows have `completed_at = NULL`** [MEASURED] — no wall-clock for failures, so wasted compute is only proxy-estimable (P79/P80), never measured.
5. **No distinguishing signal for callback-fallback settlement** — the 900s-late deliveries (N70 #10) are only inferable from the e2e-minus-worker_total gap; the row cannot say "callback missed, fallback fired."
6. **No per-job cost field persisted** — `cost_seed_usd` exists in the worker payload [CODE](modal_app.py:1093) but the job row has no cost; every $ figure is reconstructed and the code itself says "DASHBOARD AUTHORITATIVE" [CODE](query_recovery_metrics_app.py:71).

---

## SECTION O — LATENCY (measured, 7d completed cohort n=2711 with stage_timings) [MEASURED]

**End-to-end = completed_at − created_at** (the user's wait). Worker stages from `result.stage_timings`. Dispatch = started_at − created_at. Gap = e2e − dispatch − worker_total (unaccounted, mostly completion-callback settle time). **Note:** named stages overlap/nest, so the authoritative worker figure is `stage_timings.total`; individual stage medians are diagnostic, not additive.

Route mix (7d completed): premium 1233, minimal_speech_uncut 628, moodreel 574, minimal 233, hype 43.
`source_duration` COLUMN is unreliable (many rows store 0); buckets below use `stage_timings.source_duration_s`.

### O73. Stage decomposition of e2e by source-duration bucket [MEASURED]

| bucket | n | e2e p50 | e2e p90 | e2e p99 | e2e max | dispatch p50/p90 | worker_total p50 | gap p50/p90 | render p50 | normalize p50 | plan/edit_plan p50 | gemini_call p50 | upload_export p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0-20s | 1538 | 94.8 | 332.7 | 900.8 | 1052 | 0.2/3.2 | 69.1 | 9.5/34.0 | 42.0 | 3.6 | 11.1 | 46.4 (n622) | 3.8 |
| 20-60s | 894 | 193.8 | 604.2 | 900.9 | 1256 | 0.2/3.2 | 162.1 | 12.3/55.8 | 84.3 | 8.5 | 19.6 | 57.8 (n487) | 6.2 |
| 60-120s | 198 | 250.5 | 671.6 | 913.4 | 1074 | 0.2/3.2 | 187.5 | 24.6/108.6 | 92.3 | 17.3 | 23.3 | 64.4 (n101) | 9.9 |
| 120s+ | 45 | 358.9 | 747.7 | 894.3 | 894 | 0.2/3.2 | 217.3 | 29.5/184.4 | 115.2 | 32.6 | 44.1 | 62.3 (n23) | 18.2 |

(gemini_call/download/upload_export only logged on premium/full jobs, hence lower n.)

**Dispatch is negligible at every bucket** (p50 0.2s, p90 3.2s) — queue/dispatch is NOT a latency component for jobs that run. Nearly all e2e is worker time + the tail gap.

### O74. Dominant stage / critical path per bucket

Cut BY ROUTE (Rule 5), because premium (45% of completed) dominates and blends the buckets:

| route | n | e2e p50 | e2e p90 | worker_total p50 | render p50 | plan/edit_plan p50 | gemini_call p50 | dominant |
|---|---|---|---|---|---|---|---|---|
| **premium** | 1233 | 278.2 | 658.0 | 258.7 | 121.4 | **100.4** | 52.6 | render + edit_plan(Gemini) co-dominate |
| minimal_speech_uncut | 628 | 53.2 | 165.9 | 17.5 | 5.5 | 1.2 | — | tiny worker; gap dominates (p50 28.5) |
| moodreel | 574 | 95.4 | 166.0 | 73.0 | 49.1 | 12.3 | — | render |
| minimal | 233 | 30.7 | 71.1 | 11.8 | 2.9 | 1.1 | — | render (all small) |
| hype | 43 | 147.6 | 247.0 | 118.1 | 87.2 | 15.2 | — | render |

**Premium × duration critical path** [MEASURED]:
- premium 0-20s (n622): worker_total 197.8 = render 98.8 + edit_plan 80.4 + gemini_call 46.4 (edit_plan≈render).
- premium 20-60s (n487): worker_total 329.4 = render 179.7 + edit_plan 113.9 (render leads).
- premium 60-120s (n101): worker_total 432.2 = render 188.6 + edit_plan 148.3.
- premium 120s+ (n23): worker_total 610.9 = render 225.6 + edit_plan 201.6 (render≈edit_plan).

**Critical path = render and edit_plan (the editorial Gemini call), roughly co-equal on premium**; `gemini_call` (a separate analysis call ~50-65s) and `norm_transc_upload` (~85-230s, overlapped) are secondary. On the light routes there is barely any worker time — their e2e is dominated by the callback gap (see O76).

### O75. How each stage scales with source length [MEASURED] (premium route, median seconds)
- **render**: 98.8 → 179.7 → 188.6 → 225.6 across 0-20 / 20-60 / 60-120 / 120s+ buckets. Roughly linear-then-flattening; ~2.3x from shortest to longest bucket (source median 11.5→156s = 13.6x source, so render scales ~sublinearly with source, dominated by OUTPUT length + effect density, not raw source).
- **edit_plan (Gemini editorial)**: 80.4 → 113.9 → 148.3 → 201.6. ~2.5x; scales with source length (more video tokens to reason over).
- **normalize/fps_normalize**: 3.6 → 8.5 → 17.3 → 32.6 (all-route) — near-linear in source (fps re-encode of the whole clip). ~9x across buckets.
- **gemini_call (analysis)**: 46.4 → 57.8 → 64.4 → 62.3 — nearly flat (a fixed-cost model call).
- **upload_export**: 3.8 → 6.2 → 9.9 → 18.2 — scales with output length.
- **worker_total** (premium): 197.8 → 329.4 → 432.2 → 610.9.

### O76. p50/p90/max e2e + what drives the tail
- **OVERALL 7d completed (n=2711): e2e p50=131.5s, p90=516.5s, p99=900.8s, max=1256.5s** [MEASURED].
- **The tail has TWO drivers:**
  1. **Heavy premium renders** — legit worker_total 600-1017s (e.g. tail jobs: e2e 1257s with wtot 806s render 228s + gap 450s; e2e 1074s wtot 789s render 530s; e2e 1018s wtot 1017s render 522s). Premium 120s+ p50 e2e is 621s.
  2. **Missed completion-callback → 900s fallback timer** — 138/2711 (5.1%) completed jobs have gap>120s; **41 jobs settled at e2e ∈[870,920]s with median worker_total only 205.8s** — render finished fast, but completion took ~900s (the `registerPendingModalJob` 15-min fallback, N70 #10). gap p99=636s, gap max=902s. This is why p99 pins to exactly ~900s across ALL buckets even the light ones (minimal_speech_uncut p99=900.9s on 17.5s of work). **The p99 wall is a callback artifact, not compute.**
- Degeneration is a minor tail contributor: only 6 jobs with degen_retries>0 (128 with some gemini_wasted_degen).

### O77. Latency levers in code (flipped / unflipped) + projected saving [CODE]
| lever | state | default/live | projected saving | evidence |
|---|---|---|---|---|
| PROMPTLY_POST_THINKING_BUDGET | **FLIPPED** | code-default 24576, **live secret=2048** | **−29.5s wall** on critical-path edit_plan (65.3→35.8s), lower Gemini cost | handler.py:12310; CANON validate_deploy.py:7171 |
| PROMPTLY_WHY_DIET | **FLIPPED** (=1) | rationale cap 240→96 | output-bound speed lever (unquantified) | handler.py:11993,12193; CANON 7158 |
| PROMPTLY_DELIVERY_FPS | **FLIPPED** (=30) | 30 vs 60 | "halves the render tail" | CANON 7159 |
| PROMPTLY_RENDER_BURST | **FLIPPED** (=1) | render on cpu=32/64GiB burst | speed via parallelism; **costs the double-pay** (P78) | handler.py:24531; CANON 7170 |
| PROMPTLY_RENDER_FANOUT | **UNFLIPPED** (=0, deliberate) | 8-16 parallel containers/long render | **~19% wall-clock** (cert 3/3 SSIM 1.0) — held OFF for cost | handler.py:24524; CANON 7160 |
| PROMPTLY_PROXY_SAMPLE_FPS | **UNFLIPPED** (default 18) | 18→2 = 9x fewer video tokens | lower Gemini TTFB (edit_plan/gemini) — "pinned 18 with NO cost measurement" | handler.py:13270-13272 |
| PROMPTLY_HLS_COPY | **UNFLIPPED** (DARK) | -c copy single 1080p vs 4-rendition re-encode | **~72s → ~1s** on upload_export re-encode | handler.py:31701-31711 |
| PROMPTLY_MEDIA_RESOLUTION | **UNFLIPPED** (MEDIA_RESOLUTION_MEDIUM) | LOW would cut Gemini video tokens | unquantified | handler.py:12317 |
| fps_normalize SKIP | **NOT LANDED** | future | unblocks cpu=4 (nothing then races edit_plan) | modal_app.py:651 note |

---

## SECTION P — COST

**Modal rates [INFERRED — from repo constants, "DASHBOARD AUTHORITATIVE"]**: CPU = $0.0000375/physical-core/s (~$0.135/core-hr); MEM = $0.00000667/GiB/s (~$0.024/GiB-hr) [CODE](query_recovery_metrics_app.py:19-20, scoreboard_app.py:14, hls_flip_watch_app.py:15).

**Container specs (live, modal_app.py)** [CODE]:
- `run_pipeline_bg` orchestrator (holds the whole wall under SPAWN_MODE=1): **cpu=16, mem=12288 (12GiB)** → **$0.00068004/s** (0.0006 cpu + 0.00008 mem). [CODE](modal_app.py:651)
- `render_burst` (render stage, RENDER_BURST=1, for OUTPUT ≥45s): **cpu=32, mem=65536 (64GiB)** → **$0.00162688/s**. [CODE](modal_app.py:1017-1018)
- Dispatcher cls `PromptlyWorker` (returns in ms; iOS editor-open warmup provisions it, held scaledown 30s): cpu=8, mem=32768. [CODE](modal_app.py:1183)
- transcribe_and_prep cpu=8/4GiB scaledown 600s; sample/face cpu=4/2GiB; matting H100 cpu=4/16GiB scaledown 90s.
- **Double-pay confirmed** [CODE](modal_app.py:2511): during a burst render the orchestrator (cpu=16) is billed the whole wall AND render_burst (cpu=32) is billed render_time.

### P78. Cost per completed job (arithmetic) [INFERRED — reconstructed, dashboard authoritative]
Model: job_cost = worker_total × $0.00068004 (orchestrator) + (render on burst ? render_time × $0.00162688 : 0). Burst heuristic here = render stage wall ≥30s (proxy for ≥45s output). Two bounds: **orch-only** (no burst) and **+burst**.

**Per route (7d completed)** [MEASURED inputs → INFERRED cost]:
| route | n | orch-only /job (p50 / mean) | +burst /job (p50 / mean) | route total (lo→hi) |
|---|---|---|---|---|
| premium | 1233 | $0.176 / $0.214 | $0.377 / **$0.481** | $263.5 → $593.2 |
| moodreel | 574 | $0.050 / $0.054 | $0.130 / $0.137 | $31.2 → $78.8 |
| hype | 43 | $0.080 / $0.086 | $0.224 / $0.242 | $3.7 → $10.4 |
| minimal_speech_uncut | 628 | $0.012 / $0.017 | $0.012 / $0.019 | $10.9 → $12.2 |
| minimal | 233 | $0.008 / $0.013 | $0.008 / $0.015 | $3.0 → $3.4 |

Worked example, **premium p50**: orchestrator 258.7s × $0.00068004 = **$0.176**; burst render 121.4s × $0.00162688 = **$0.198**; total ≈ **$0.374/job**.
- **Blended over all 2711 completed: orch-only mean $0.115/job; +burst mean $0.257/job** [MEASURED/INFERRED].
- **7d completed compute est: $312 (orch-only) → $698 (+burst); premium is ~85% of it ($593 of $698).**
- 7d completed total orchestrator wall = 459,230s ≈ 127.6 core-hours-equiv.
- Reconciles with the code's stated "~$0.09 job compute" [CODE](modal_app.py:651): that is the blended-median ORCHESTRATOR-only figure (~131s × $0.00068 ≈ $0.089); it EXCLUDES the burst double-pay, which the +burst mean ($0.257) captures.

### P79. Non-job spend [MEASURED counts / INFERRED $]
- **Idle/warm containers now**: `modal app list` shows promptly-gpu-worker = **4 running tasks** (warm dispatcher/transcribe/etc.), promptly-matting = 0 [MEASURED]. Each warm cpu=8 dispatcher idles at scaledown_window=30s per editor-open.
- **Editor-open warmup leak (fixed)**: was ~$700/mo when the dispatcher cls was cpu=64 (every editor-open — incl. the 63% who never render — spun a 64-core box) [CODE](modal_app.py:1183). Now cpu=8 → ~8x smaller.
- **Always-on prewarm (fixed)**: PromptlyPrewarmWorker min_containers=1 removed, ~$35/mo saved [CODE](modal_app.py:76).
- **Reaped/stalled spawns**: a stalled spawn bills to the Modal timeout. Was 3000s (~$0.71-3/job, "spawn-not-complete is the #1 wasted class, 1447s avg wall"); now capped 1200s [CODE](modal_app.py:651). 7d JOB_STALLED=12 jobs.
- **The code's own steady-state estimate**: "~$87/day of NON-JOB warmup/prewarm/idle" [CODE](modal_app.py:651) — i.e. non-job spend is stated to DWARF per-job compute (~$0.09).
- **Cert/test spend**: ephemeral cert apps priced per-run in headers (e.g. cert_core_probe ~$0.001, cert_fps ~$2-3/run) — not in job path; no synthetic pipeline spend permitted (Rule 6).

### P80. Fraction of spend producing NO video [MEASURED counts / INFERRED $]
- **7d spawned-and-failed (burned worker compute, no video) = 134 jobs** [MEASURED]: DISPATCH_UNREACHABLE 26, INTEGRITY_TRIP 20, RENDER_FFMPEG 19, RENDER_FATAL 18, JOB_NEVER_STARTED 16, CLIP_TOO_SHORT 14, RENDER_REMOTION 7, JOB_STALLED 6, INVALID_FORMAT 5, TRANSCRIPTION 3.
- **Est wasted spend ≈ $17 (7d) [INFERRED]** using medWtot=96s proxy for render-family + 1200s cap for reaped: JOB_STALLED ~$10.75 (the reaped-to-timeout jobs dominate), INTEGRITY_TRIP ~$1.31, RENDER_FFMPEG ~$1.24, RENDER_FATAL ~$1.18, DISPATCH_UNREACHABLE ~$0.85, others <$0.6.
- **As a fraction: ~$17 wasted / ~$698 completed ≈ 2.4%** of 7d job compute produces no video (INFERRED). This EXCLUDES: (a) the 25h outage (1121 jobs — but those got a 404 at dispatch, so no worker container ran → ~$0 Modal job cost, only lost outcomes); (b) UPLOAD_NEVER_STARTED (347/7d, modal_spawned=false → $0 Modal); (c) in-completed-job degen waste (128 jobs × ~80s × $0.00068 ≈ **$7** of Gemini/orch time inside successful renders).
- The dominant "no-video" spend is not failed renders (~$17) but **non-job idle/warmup (~$87/day claimed = ~$609/7d)** — an order of magnitude larger than the wasted-render class. [CODE-stated / INFERRED]

### P81. Per-job cost target + gap to measured
- **Cost law: $0.10/job** [CODE](CLAUDE.md "Standing product laws"; ~$0.09 compute claimed at modal_app.py:651). Latency law: 90s e2e.
- **Gap [MEASURED/INFERRED]:**
  - minimal / minimal_speech_uncut: **$0.008-0.017/job — UNDER the law** ✓
  - moodreel: $0.054-0.137 — at/over.
  - hype: $0.086-0.242 — over.
  - **premium: $0.214 (orch-only) to $0.481 (+burst) mean — 2-5x OVER the $0.10 law.** Driven by long edit_plan (Gemini) + render + the burst double-pay.
  - **Blended: $0.115 (orch-only, ≈law) to $0.257 (+burst, 2.6x law).** The law is met on the orchestrator-only median but the burst double-pay and the premium mix push the true blended to ~$0.26.
- **Latency-law gap:** e2e p50=131.5s vs 90s law (**1.46x over at the median**); premium p50=278s (3.1x). p99=900s is a callback artifact, not the pipeline.

---

## Cross-cutting findings (contradictions / flags)
1. **`started_at` misdescribes "ran"** (N69) — dispatch-attempt timestamp, present on never-spawned jobs. Any "started = entered pipeline" denominator is wrong. Lead completion with modal_spawned/stage_timings-based cohorts.
2. **Dispatch-404 outage was invisible to error-code analytics** (N72 #1) — 1121 jobs / 547 users, result=NULL. A by-code query silently under-reports the single largest 30d failure event.
3. **The p99 latency wall (~900s) is a missed-callback fallback, not compute** (O76) — 41/2711 jobs deliver ~700s late looking like normal completions. Not instrumented.
4. **Cost law is met only on the orchestrator-only median**; premium + the RENDER_BURST double-pay push blended to ~$0.26/job (P78/P81). Non-job idle (~$87/day claimed) dwarfs both per-job compute and wasted-render spend (P79/P80).
5. **Retry inflation is real** (Rule 7): outage 2.05x, UPLOAD_STALLED 2.6x, RENDER_FFMPEG ~2x — always lead with the user count.
# RECON — SECTIONS Q (Gates/Certs/Harnesses), R (Language), S (Data), T (Honest Unknowns)

Repo: `/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker` (branch `zero-reject-routing`).
Sibling: `/Users/zaclibman/content-studio` (server.js + lib/, deploys from `main` via Render).
Tags: **[MEASURED]** direct observation · **[CODE](file:line)** read in source · **[INFERRED]** reasoned · **[UNKNOWN]**.
NO Modal spend was incurred. NO cert_*.py / test_*.py / validate_deploy.py was executed. DB reads were read-only SELECTs.

---

## SECTION Q — GATES / CERTS / HARNESSES

### Q82. Test/cert infrastructure inventory + what it genuinely proves

**Counts [MEASURED]:**
- `grep -c '@check' validate_deploy.py` = **357** lines match; the true decorator count `read().count("\n@check(")` = **353** [CODE](validate_deploy.py:11194). The 4 extra are `@check` substrings inside assert-message strings / the self-count line.
- **76** `cert_*.py` files, **63** `test_*.py` files [MEASURED `ls | wc -l`].

**The gate mechanism [CODE](validate_deploy.py:41):** `def check(label)` is a decorator that registers-and-immediately-runs each function; a **gate-integrity self-guard** at [CODE](validate_deploy.py:11194-11198) asserts `_declared (353) == _ran` and FAILS the gate if any `@check` is defined *below* the runner and never executes. So all 353 are structurally guaranteed to run on every deploy. This is a genuinely good anti-vacuity guard for the *count*.

**What the 353 checks cover** (by reading labels, saved to `tool-results/b61sjg28l.txt`): they span caption timing/entrance/fit, zoom peak-on-word/spring/vibe-split, MG anchor/face-avoidance, transitions, B-roll gating, integrity gate (freeze/black/dead-moment echoes), render concurrency/timeout/frame-grid, the persist-guards (INC2/source_duration/gemini_tokens nesting), deploy-state guard, language routing, coverage gate, secret canonical values, progressive HLS, re-edit/plan-diff, degeneration, thread-pool leak. Effectively a per-fix regression pin per Rule 1.

**`cert_*.py` — what each covers** (docstrings, saved `tool-results/bnjxkrqx3.txt`). Notable: `cert_asr_bakeoff.py` (Deepgram vs Scribe on 40 TRANSCRIPTION_INCOMPLETE clips), `cert_gemini_vs_deepgram_timing.py` (Gemini ts drift), `cert_blur_truereplay_app.py` (spy-capture N× byte-identical toggle), `cert_regression_corpus.py` (real S3 failing sources), `cert_tier1_{hindi_e2e,grad_e2e,stageA,lang,negctrl}_app.py` (language graduation), `cert_repro_26a05f5d.py` / `cert_repro_three_classes.py` (bug reproductions), `cert_core_probe.py` (cpu=8 container reports 24 cores). `test_*.py` docstrings each name a Zac-dated defect + "the never-again pin."

**What they genuinely prove vs not:** ~**160 of 353** checks (≈45%) are **SOURCE-GREP** assertions (`assert "...string..." in _src/_h/_m`) that only prove a code string/comment is *present*, not that the guarded code path *runs* [MEASURED, heuristic classifier]. ~193 are behavioral (import handler, call a function, assert on the result). The behavioral ones are the load-bearing certs; the source-grep half is fragile to refactor (a rename that preserves behavior but changes the literal fails the gate; conversely a behavior change that keeps the literal passes).

### Q83. Which certs are NON-VACUOUS (proven to fail when the guarded thing breaks)

**Genuinely non-vacuous (a reproduction arm / "caught a real regression" pedigree):**
- `test_coverage_empty_transcript.py` — the OLD gate `if _dur<=0 or not words: return True` **PASSED** an empty transcript; the cert drives the real `_transcription_coverage_check` and asserts empty-over-VAD-speech now REJECTs [CODE](validate_deploy.py:5215-5247). Provably red before the fix.
- `test_integrity_black_echo_boundary.py` / `..._freeze_..._boundary.py` — **FORCED REPRODUCTION** of job 017fa6d3; assert a span crossing a cut is still source-checked (docstrings).
- `test_output_frame_grid.py` — reproduces the two RENDER_FATALs on the first paying subscriber (`sample_rate not integer-divisible by fps`).
- `test_render_never_blames_user_file.py` — "No video stream found" misclassified as bad user file; asserts a render failure is never INVALID_FORMAT.
- `cert_repro_26a05f5d.py`, `cert_repro_three_classes.py` — named-job bug reproductions.
- `cert_regression_corpus.py` + `modal_app.py::cert_regression_corpus` — re-renders the **real S3 source** that produced each fixed sub-code and asserts it still COMPLETES [CODE](modal_app.py:2560).
- The **10 gate-embedded tests** (Q84) are proven-red-before-fix by construction.

**Never proven to fail (source-grep pins):** the ~160 `assert "..." in _src` checks — e.g. `assert '"source_text_declared"' in _src` [CODE](validate_deploy.py:9445). They pass as long as the literal exists; there is no arm demonstrating they'd fail on the real regression. The persist-guards (INC2/source_duration/gemini_tokens, [CODE](validate_deploy.py:74,94,114)) are regex-on-indentation — clever, but they'd miss a rename of the wrapping dict.

### Q84. Tests red/skipped/never-invoked — WHICH run in the gate vs standalone

**In the deploy gate (subprocess, fails deploy):** exactly **10** test files [CODE](validate_deploy.py:5197-5205): `test_render_ladder, test_remotion_timeout_forensics, test_coverage_empty_transcript, test_asr_scribe_routing, test_render_never_blames_user_file, test_integrity_black_echo_boundary, test_integrity_freeze_echo_boundary, test_silent_to_moodreel, test_output_frame_grid, test_integrity_dead_moment_echo`. This check exists because `test_render_ladder.py` was **PERMANENTLY RED at HEAD and no runner invoked it** [CODE](validate_deploy.py:5193).
- **FINDING:** The other **53** `test_*.py` are NOT invoked by any runner. Some have their logic *replicated inline* in `@check` bodies (e.g. staged-push, caption-override), but a `test_*.py` that is neither in the list-of-10 nor inline-replicated is **effectively never run by CI** — the same class the ORPHANED-CERTS check was forged to kill, only partially closed.
- **cert_*.py: 70 of 76 are Modal apps** (`modal.App`/`.remote()`/`.map`) [MEASURED] — they cost Modal spend and are **NEVER auto-run**. Only `cert_auth_ping.py` + `cert_run_auth_ping.py` run post-deploy in deploy.sh, and `modal_app.py::regression_corpus` is spawned each deploy [CODE](deploy.sh:87,117,146). The ~70 remaining cert apps are **manual one-shot investigation harnesses** (Zac gitignored 39 of them, commit c61475a). Not red, not green — just dormant.
- **Only ~6 cert_*.py are OFFLINE** (runnable free): `cert_asr_score, cert_integrity_black_families, cert_prompt_content_diff, cert_proxy_thread_pin, cert_remotion_env_patch` [MEASURED]. Two of these (`cert_integrity_black_families`, `cert_remotion_env_patch`) are asserted to merely *exist* on disk by @checks [CODE](validate_deploy.py:5009,5059) — existence, not execution.
- No explicit `@skip`/`xfail` markers found; the "skip" hits are Lever-4 identical-input render-skips (product logic), not test skips.

### Q85. Byte-identity / golden-diff harness — what it locks; would it catch an editorial change?

**There is NO stored golden-output corpus that locks the CURRENT edit.** What exists locks **DETERMINISM** (same plan → same bytes), not correctness-vs-reference:
- x264 encode-thread pin `_X264_ENCODE_THREADS = 48` (handler.py; also cert_cpu4:40) makes a fixed plan **byte-identical across any CPU** (CLAUDE.md render-determinism law).
- `cert_blur_truereplay_app.py` — spy-captures a plan, renders it OFF/OFF2/ON, asserts `frame_locked` (OFF==OFF2==ON nb_frames) and PSNR('inf'=identical) [CODE](cert_blur_truereplay_app.py:112-125).
- `cert_concurrency_ab_app.py` — b8/b8b/b16 must be frame-locked (concurrency changes speed not pixels) [CODE](cert_concurrency_ab_app.py:76).
- `cert_progressive_app.py` — delivered FINAL must be byte-identical to publisher-off render of the same plan; preview SSIM informational [CODE](cert_progressive_app.py:275,413).
- `cert_proxy_thread_pin.py` — proxy x264 encoder thread pin → byte-identical proxy.
- `cert_regression_corpus` asserts jobs **COMPLETE** (status), NOT that output pixels are unchanged.

**Would it catch an editorial change? NO.** Every harness above renders *the same captured plan twice and compares the two renders*. An editorial change (different cuts/captions/zooms) produces a *different plan*, so there is nothing to diff it against — the determinism harness would still pass (each arm self-consistent). Only a human contact-sheet review (QUALITY_FAULT_ROADMAP.md) or a per-behavior `@check` catches editorial drift. **Gap:** no frozen golden render for any real source.

### Q86. Durable regression corpora — where, how many, reachable

- **`_REGRESSION_CORPUS`** [CODE](modal_app.py:2546) + `cert_regression_corpus.py:52`: ~**6 real S3 sources** under `s3://thisismybucketagainwooo/failure-corpus/<CODE>/<job_id>.mp4` — RENDER_FATAL ×3 (54fb3d02, 20682270, 26a05f5d), INVALID_FORMAT (2a8dc854), RENDER_FFMPEG ×2 (02242d0f, 4b32c93f). Re-run every deploy; self-alerts on REGRESSED [CODE](deploy.sh:146). "REPOINTED at the REAL S3 corpus 2026-08-04" [CODE](cert_regression_corpus.py:8).
- **`handler._capture_failure_corpus`** [CODE](handler.py:38913) — on EVERY terminal failure OR silent completion, retains the exact source to S3 `failure-corpus/<CODE>/<job_id>.mp4` (DURABLE FAILURE CORPUS, check 314). This is the *growing* corpus feeding the above.
- Local `~/promptly-failure-corpus` is **audio-only → cannot re-render** [CODE](cert_regression_corpus.py:19).
- `cert_blur_ab_app.py` durable benchmark source **c8c8264e** (1080×1920/30fps/12.6Mbps).
- multilingual-corpus / constructed-durable-source pattern (memory `feedback_ab_durable_sources`).
- **Reachability [UNKNOWN]** — the S3 keys are named but I did not (would cost spend / need S3 creds) verify the objects still exist. The deploy-time self-alert is the live liveness check.

---

## SECTION R — LANGUAGE

### R87. Languages supported end-to-end + evidence

**Tier-1 CERTIFIED (9)** [CODE](handler.py:4921): `hi, es, pt, ar, fr, de, ru, id, ja`. Tier-2 = every other font-backed language (enabled+watched, not certified) [CODE](handler.py:4915-4932).
**Script→lang map (16 scripts)** [CODE](handler.py:4875): Devanagari→hi, Cyrillic→ru, Arabic→ar, Hebrew→he, Han→zh, Hiragana/Katakana→ja, Hangul→ko, Tamil→ta, Telugu→te, Bengali→bn, Gujarati→gu, Gurmukhi→pa, Malayalam→ml, Kannada→kn, Thai→th, Greek→el. `_LANG_DISPLAY_NAME` covers ~39 codes [CODE](handler.py:4887).
**Fonts:** full Noto family (fonts-noto-core + cjk), NOTO_FALLBACK appended to every CAPTION_FONTS entry, RTL `captionDirection` (checks 205/207/208).

**LIVE state — the authority is the canonical secret, asserted every deploy** [CODE](validate_deploy.py:7149-7172):
- `PROMPTLY_EDIT_IN_LANGUAGE=1` (multilingual + in-language editorial ON)
- `PROMPTLY_SCRIPT_DENYLIST=""` → **graduated: NO script denied** — every font-backed script reaches render (flips the coverage gate from Latin-allowlist to denylist model).
- `PROMPTLY_LANG_ROUTING=1` (Stage-A Gemini-ID→Deepgram monolingual recovery).
- `PROMPTLY_COVERAGE_GATE=1`, `PROMPTLY_ASR_SCRIBE=1`.
- `PROMPTLY_ROUTE_LANGS` **NOT pinned in CANON** → defaults to `frozenset({"hi"})` [CODE](handler.py:5177). So **only Hindi is graduated for Stage-A monolingual recovery**; all other languages ride Deepgram-multi + Scribe + denylist render.

**CODE DEFAULTS are conservative and would mislead:** `_SCRIPT_COVERAGE = frozenset({"Latin"})` [CODE](handler.py:4785) and `_GRADUATED_ROUTE_LANGS_DEFAULT = frozenset({"hi"})` [CODE](handler.py:5177). Reading the code alone says "Latin-only." The LIVE `SCRIPT_DENYLIST=""` secret overrides this — you MUST read the CANON dict, not the default, to know what renders. This is the Rule-2 "secret flip not visible in code" trap.
- Reconciles memory `project_multilingual_initiative` ("9/9 Tier-1 LIVE"): true only via the live secret, not the code default. [INFERRED consistent]

### R88. How language is detected + where it goes wrong

**Detection order:**
1. **PRIMARY: Deepgram Nova-3 `language=multi`** [CODE](handler.py:4270-4295) → `detected_language` per channel [CODE](handler.py:4414-4427). This is the WHEN clock and the language label.
2. **`_dominant_script(words)`** derives script from transcript characters (drives font + coverage routing).
3. **Coverage gate** `_transcription_coverage_check` [CODE](handler.py, replicated cert_asr_score) — VAD-speech-with-no-words > 2.0s AND ≥0.10 frac of **EDGE** speech → TRANSCRIPTION_INCOMPLETE.
4. **On coverage FAIL only** — two recoveries: **Scribe** `_maybe_upgrade_transcript_scribe` [CODE](handler.py:4574) (ElevenLabs, allowlisted langs) and **Stage-A** `_route_language_via_gemini` [CODE](handler.py:5223) (Gemini IDs language → ONE Deepgram monolingual model, graduated langs=hi). Stage-A is the SAFE path: Gemini-ID, not acoustic; negative-control-gated.

**Where it goes wrong [CODE]:**
- Deepgram multi **ROMANIZES Arabic** → `_dominant_script` sees Latin → Arabic bridge routes `language=ar` (check 239; handler.py:4378-4383).
- Deepgram multi **mislabels Bengali/Tamil as 'hi'** and under-covers 40–85% (Stage-A comment handler.py:37263).
- A **0-word Deepgram result carries NO detected_language** → the Scribe allowlist excluded exactly the empty case Scribe exists to recover; language gate ran BEFORE the coverage check (fixed b5df3ea, "Scribe zero-word bypass").
- **Gemini word-timestamp DRIFT** — Gemini is language-ID / WHICH-words only, can NEVER be the cut clock (memory `project_gemini_timestamp_drift`; cert_gemini_vs_deepgram_timing).
- **The coverage gate counts EDGE speech only** [CODE](validate_deploy.py:6544 label) — interior-untranscribed speech is preserved (plays uncaptioned), edge speech is dropped. This is by design but is the mechanism behind the Spanish material-loss complaint (R89).

### R89. Language-specific defects — known/open/"fixed"-without-confirmation

- **Hindi mid-word cuts** — **MEASURED** 37.1% (49/132) vs English 7.4% (6/81), z=4.81 [MEASURED, LANGUAGE_CUTS.md; commit c613435]. Hindi = 51% of the transcript cohort. Fixes shipped: mid-word fixed-point snap (8360a93/6b3ece7), FINAL-END WORD INVARIANT (check 279), EDGE CONTENT NOT TRUNCATED / Urdu interior rule at edges (check 271, commit 199c686). **Post-fix rate NOT re-measured on traffic → "fixed" unconfirmed.** [INFERRED open]
- **Spanish / Russian material loss** — **MEASURED** Spanish 0.41 keep-ratio, 53% lose >half video; Russian 0.50 [SPANISH_COVERAGE_GATE.md; commits 06be9c0, b10818e]. ROOT: `build_clips_from_words` drops EDGE speech outside `[first..last kept word]` at ANY size, and **NOTHING gates the keep-ratio** [CODE, commit a324b7d: "the gate is not broken… it measures speech integrity while the complaint is material loss"]. The team explicitly declined a filter fix ("real fix is the prompt", 67276e5). **OPEN.**
- **vad_coverage "silently inert"** [commit b10818e] — directly corroborated by S92 below (lang_bundle null 218/218).
- **Arabic romanization** (bridge, check 239) — handled but fail-closed if `language=ar` returns no native script (handler.py:37194).
- **Bengali/Tamil→hi mislabel** — mitigated by Stage-A negative-control, but Stage-A only graduated for hi.

### R90. Fraction of real traffic non-English — [MEASURED]

Method: read `result.transcript` text over the **last 500 completed jobs (2026-08-08 → 2026-08-10)**, Unicode-script-classify. 219/500 carry transcript text (the other 281 are minimal / minimal_speech_uncut / moodreel / no-speech routes that don't expose transcript text).

| script (lang) | n | % of transcripted (n=219) |
|---|---|---|
| **Devanagari (Hindi)** | **135** | **61.6%** |
| Latin (English + other) | 64 | 29.2% |
| Latin + ES-diacritic (Spanish-ish) | 13 | 5.9% |
| Arabic | 5 | 2.3% |
| Cyrillic (Russian) | 2 | 0.9% |

**Non-English is the MAJORITY of transcripted traffic; Hindi alone dominates (~62%).** This matches LANGUAGE_CUTS.md's independent cohort (Hindi 132/257 = 51%). **The single most-traffic language (Hindi) is the one with the worst known cutting defect.** Denominator caveat: script-of-text is a proxy (a Hindi clip with romanized output would misclassify as Latin), and 281/500 have no transcript to classify. `transcript.detected_language` field was empty on all 219 → the language label is NOT stored (see S92).

---

## SECTION S — DATA

### S91. Tables the worker reads/writes + columns that matter

**Worker (handler.py) [MEASURED grep]:** writes `video_jobs` (5 sites), upserts `user_style_profiles` (handler.py:3072); reads `trend_profiles` (2321), `user_style_profiles` (2422), `analytics_events` (2465), `video_jobs` (2481). `modal_app.py` touches no tables directly.
**Server (content-studio) [MEASURED grep]:** `video_jobs`×50, `profiles`×15 (tier/entitlement), `analytics_events`×12, `videos`×10 (storage rows), `usage_events`×9 (billing/wall), `video_analysis_cache`×7 (re-edit analysis cache), `creator_submissions`×3, `edit_jobs`×2, `device_tokens`×2 (APNs), `app_feedback`×2, `chats`×1.

**`video_jobs` columns that matter [MEASURED — column existence probed]:**
- EXISTS: `status, result(jsonb), source_duration, reedit_mode, vibe_input, edit_rationale, post_package, preview, rendered_video_url, hls_manifest_url, thumbnail_url, edit_recipe, transcript, analysis_data, resolved_broll, trend_snapshot, render_version, change_summary, progress, current_step, step_message, completed_at, refunded_at`.
- **DOES NOT EXIST: `video_jobs.detected_language`** (42703) and **`video_jobs.route`** (42703) — both are NOT columns [MEASURED]. Route lives in `result.route` (minimal routes only); language lives nowhere queryable.

**`result` jsonb shape [MEASURED, 2 route families]:**
- **standard editorial** (`result.route` absent; has `tier/model/route_premium/floor/lumen_funnel`): `stage_timings` keys = broll,total,render,download,lean_arm,timeline,edit_plan,source_fps,target_fps,gemini_call,**lang_bundle**,shake_score,source_poll,degen_retries,fps_normalize,**gemini_tokens**,upload_export,lean_schema_on,edit_recipe_faces,**source_duration_s**,gemini_wasted_degen,lean_decor_ground_on,normalize_transcribe_upload.
- **minimal** (`result.route="minimal"`): sparse `stage_timings` = hls,plan,total,render,normalize,target_fps,source_duration_s (NO lang_bundle/gemini_tokens/broll).

### S92. Queryable NOW vs print-only/LOST

**Queryable (result jsonb / stage_timings):** route(minimal only)+route_reason, tier, model, floor+floor_reason, route_premium, premium_pipeline_enabled, lumen_funnel, vocab, capability_notes, change_summary, post_package, enhancements_dropped, clean_export_key, transcript, edit_recipe, analysis_data, resolved_broll, and stage_timings{total, render, download, edit_plan, gemini_call, **gemini_tokens**, source_duration_s, fps_normalize, broll, timeline, lean_arm/lean_schema_on/lean_decor_ground_on, degen_retries, gemini_wasted_degen, shake_score, edit_recipe_faces, upload_export, normalize_transcribe_upload, source_fps, target_fps}.

**LOST / null / print-only [MEASURED]:**
- **`detected_language` — NOT queryable ANYWHERE.** Not a column; not top-level result; `transcript.detected_language` empty on all 219 sampled; `stage_timings.lang_bundle` NULL (below). Only lives in the stdout line `[deepgram] Transcribed N words (lang=X)` [CODE](handler.py:4426) → gone with the log buffer.
- **`stage_timings.lang_bundle` — KEY present on 218/500, VALUE null on 218/218; ABSENT on minimal routes** [MEASURED, `scratchpad/dbq4.js`]. So detected_language + transcript_script + vad_coverage(unworded_s/frac/vad_speech_s) + words — the entire THREE-FIELD LANGUAGE BUNDLE — is **null on 100% of recent standard completions** despite check 246 ("LIVE on every job") and check 272 ("vad_coverage REACHES THE DATABASE"). ROOT [CODE + INFERRED]: the terminal write reads `edit_plan.get("_lang_bundle")` [CODE](handler.py:38829), which is only set at [CODE](handler.py:37232-37245) — a block inside the deep language-recovery/coverage path (near the Arabic-bridge, handler.py:37150-37260). For dominant English/standard traffic that block is not reached → `_lang_bundle` unset → persists null. This is the "vad_coverage silently inert" defect (commit b10818e) still live. **NEW finding.**
- **`pipeline_time` / `render_time`** (HTTP result_payload) — never persisted [CODE](handler.py:38971 comment).
- **`prewarm_hit`** — check 352 claims now nested; NOT seen in any sampled stage_timings [MEASURED absent] → likely only on cold containers or still effectively print-only [CODE](handler.py:35313-35328).
- **`cpu_by_stage` / `mem_by_stage`** — check 3 claims nested; NOT in any sampled stage_timings [MEASURED absent] → only populated under inc2 render-burst sizing, otherwise print-only.

### S93. Fields STRIPPED in transit worker→server — mechanism + everything at risk

**The stripping allowlist is WORKER-SIDE, not content-studio-side [CODE]:** the worker's own `write_job_status(result={...})` writes an **explicit key allowlist** — [CODE](handler.py:38921-38977) (standard), [CODE](handler.py:32623/32658) (minimal), [CODE](handler.py:38788+) (other terminals). Any top-level `result_payload` key NOT named there is dropped from the DB. `stage_timings` is written **whole** [CODE](handler.py:38809-38837), so **nesting a field inside stage_timings is the survival trick**.
The content-studio dispatch tail writes only OWNED playback/re-edit columns (`rendered_video_url, hls_manifest_url, thumbnail_url, edit_recipe, transcript, analysis_data, resolved_broll, trend_snapshot, render_version, change_summary`) via `ownedUpdate` [CODE](dispatch-to-modal.js:991-1016) and **explicitly NEVER writes `result`** [CODE](handler.py:38969-38970: "the worker owns result; dispatch-to-modal.js never writes result").

**CONTRADICTION (see T95):** validate_deploy checks 3/5/6 and handler comments (handler.py:38813, 38819, 38824) attribute the stripping to *"content-studio strips unknown top-level result keys."* That is the wrong attribution — the drop happens at the **worker's** write_job_status allowlist. Net effect identical; the mental model in the comments points at the wrong file.

**Currently at risk:** ANY new top-level `result_payload` field a future dev adds without (a) naming it in the write_job_status allowlist or (b) nesting it in `stage_timings`. **Precedent losses (all "fixed" by nesting):** `source_duration_s` (0/62), `cpu_by_stage`/`mem_by_stage` (0/121), `gemini_tokens`, `vad_coverage`, `_lang_bundle` (0/3000 — leading underscore also stripped by the recipe sanitizer). **Note:** `lang_bundle` was nested to survive stripping (check passes) yet is STILL null 218/218 — because that is a *population* bug (S92), not a *stripping* bug. The nest-guard checks give false confidence that the field is now present.

---

## SECTION T — HONEST UNKNOWNS

### T94. What I FAILED to determine + what it would take
- **Whether the ~70 Modal cert apps still pass** — determining it costs Modal spend; correctly not run. Would need a watched real-traffic or a budgeted Modal run.
- **Whether the S3 failure-corpus objects still exist** at their named keys — needs S3 creds / a Modal run; only the deploy-time self-alert proves liveness. [UNKNOWN]
- **Live secret values** — I read the CANON dict (validate_deploy.py:7149) and know the gate asserts live==CANON via `modal run secret_flags_readback.py` on every deploy; I did NOT run it, so the *asserted* live values are [INFERRED from the deploy invariant], not [MEASURED]. In particular `PROMPTLY_ROUTE_LANGS` is not in CANON, so which languages are graduated for Stage-A recovery beyond `hi` is [UNKNOWN] without the readback.
- **Root cause confirmation for lang_bundle null** — I have the [MEASURED] 218/218 null and the [CODE] population site, but the exact guard that skips the population block for standard jobs sits in deeply-nested handler() logic I did not fully trace. [INFERRED].
- **Whether Hindi mid-word / Spanish edge fixes actually moved the rate** — no post-fix traffic re-measure exists in the repo. [UNKNOWN].
- **prewarm_hit/cpu_by_stage real persistence rate** — [MEASURED absent] in samples but I did not compute an exact denominator across all routes.

### T95. Contradictions found (each is a finding)
1. **Stripping attribution.** Checks 3/5/6 + handler comments say *"content-studio strips unknown top-level keys"*; the actual allowlist is the **worker's** `write_job_status` [CODE](handler.py:38921), and dispatch-to-modal.js **never writes result** [CODE](handler.py:38970). Wrong file blamed.
2. **"lang_bundle persisted on EVERY job" (checks 246/272) vs reality.** [MEASURED] null on 218/218 recent standard completions, absent on minimal. The nest-guard is green; the data is empty. Classic Rule-2 (built≠working).
3. **Code default vs live language state.** `_SCRIPT_COVERAGE={"Latin"}` and default route langs `{"hi"}` [CODE](handler.py:4785,5177) read as "Latin/Hindi only," but live `SCRIPT_DENYLIST=""` + `EDIT_IN_LANGUAGE=1` [CODE](validate_deploy.py:7153-7154) mean every font-backed script renders. Reading code alone (or `origin/main`, per Rule 0) gives the wrong answer.
4. **Spanish "the gate is not broken" (a324b7d) vs the complaint.** True but a non-answer — the material-loss mechanism (edge-drop in build_clips_from_words) has **no gate at all**; the "fix" is deferred to the prompt and unconfirmed. Open defect dressed as resolved.
5. **QUALITY_FAULT_ROADMAP.md** contradicts the funnel's assumption: export rate tracks SOURCE quality, and the richest route (standard editorial) has the LOWEST export % (9.9%) while near-passthrough moodreel has the highest (20%). The heavy editorial machinery this whole gate protects may be net-negative for export.

**.md report files — durable truth vs stale:**
- **DURABLE architectural truth:** `SPANISH_COVERAGE_GATE.md` (edge-drop mechanism, still live), `LANGUAGE_CUTS.md` (Hindi 5× mid-word, measured), `WORKER_TERMINAL_ENUMERATION.md` (classify_error→38 codes map, handler.py:28495), `EVIDENCE_BEFORE_DIET.md` (prompt-line audit), `POST_PACKAGE_CONTRACT.md` / `PROGRESSIVE_CLIENT_CONTRACT.md` (live contracts), `QUALITY_FAULT_ROADMAP.md` (the only watched-output review).
- **Time-boxed / potentially stale:** `DEPLOY_LOG.md` (a specific 08-03/04 deploy window's orphan attribution — a ledger, not a spec), `MODAL_SPEND_LEDGER.md`, `LEAN_AB_PREREGISTRATION.md`, `FLIP_RUNBOOK_ZERO_REJECT.md` (a runbook for a flip already done). None are the source of truth for live state — the CANON dict + running image are.

### T96. Single most dangerous thing a new agent would not know
**`origin/main` is a dead source of truth (Rule 0), AND the *code defaults* lie about live behavior because the real config lives in the `promptly-lang-flags` Modal secret.** The worker deploys from `zero-reject-routing`, and reading either the code defaults (`_SCRIPT_COVERAGE={"Latin"}`, all the `default OFF` flags) or `main` tells you multilingual/zero-reject/burst/scribe are off — when in fact the LIVE canonical secret [CODE](validate_deploy.py:7149-7172) has them all ON. You cannot know what runs without reading the CANON dict (or the readback). Second: a **green gate check does not mean the data is populated** — lang_bundle is the proof (nest-guard green, 218/218 null).

### T97. If editorial architecture were restructured tomorrow, what breaks that nobody is thinking about
1. **The ~160 source-grep `@check`s** (Q83) — a rename/refactor that preserves behavior but changes literals fails ~45% of the gate for spurious reasons, OR (worse) a behavior change that keeps the literal passes green. A restructure would drown in false gate failures and hide real ones.
2. **The write_job_status allowlist (S93)** — a new editorial architecture emitting new result fields will silently lose every one not nested in stage_timings. Analytics goes dark exactly when you most need to measure the new architecture (the source_duration/cpu_by_stage/lang_bundle history proves this happens repeatedly).
3. **Route-shape coupling** — `result.route` exists only on minimal routes; the standard route has no route key, so `bleed-meter` and any route-cut analysis (Rule 5) that keys on `result.route` mis-buckets standard editorial as `(none)` [MEASURED 218/500]. A restructure that renames routes breaks route-cut metrics invisibly.
4. **Language recovery is wired into the coverage-FAIL path only.** Any restructure that changes where the coverage gate sits will orphan the `_lang_bundle` population, Stage-A routing, and Scribe upgrade — and since lang_bundle is already null, nobody watching the DB would notice language routing broke.
5. **Determinism harnesses lock plan→bytes, not correctness (Q85).** A restructure could ship visibly-worse edits with every determinism cert green. There is no golden-output tripwire — only human contact sheets — so editorial regressions are invisible to CI by construction.

---
### Appendix — artifacts
- Full check-label enumeration: `tool-results/b61sjg28l.txt` (353 labels).
- cert docstrings: `tool-results/bnjxkrqx3.txt`. Language greps: `tool-results/bx3mfiea1.txt`.
- DB scripts (read-only): `scratchpad/dbq.js`, `dbq3.js`, `dbq4.js`, `dbq5.js`.
