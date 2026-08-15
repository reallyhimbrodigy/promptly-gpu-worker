# BUILT-NOT-WIRED — the swept list `[Rule 2, §4.8]`

**Six instances were found BY ACCIDENT** while working on something else. Six by
accident implies more by search, so this searched: `sweep_built_not_wired.py`,
both repos, three shapes.

**103 raw candidates. Adjudicated below.** These are candidates, not verdicts —
entrypoints, decorators and dynamic dispatch are legitimately "uncalled", and
saying so is part of the job.

---

## THE FINDING THAT MATTERS: the render frame watcher never runs

```
handler.py:34352   def _start_render_frame_watcher(...)     ← ZERO call sites
handler.py:34417   def _start_progress_heartbeat(...)       ← 3 call sites
```

**`_start_render_frame_watcher` is never started.** It is the only writer of
`render_frames` and `progress_at`.

This is not a hypothesis — it is the *cause* of two facts already measured
independently:

| observed | explanation |
|---|---|
| `render_frames` null in **0/293 and 0/183** (called vestigial from the data) | its only writer never runs |
| `progress_at` null in **180/180** of the envelope-lost cohort | same writer |

**And it disarms a watchdog that was designed to exist.** `modal_app.py` argues
for a "DURATION-PROPORTIONAL watchdog… progress-aware, kills in minutes" and
distinguishes `progress_at` from `updated_at` precisely because *"progress_at is
written ONLY when the caller confirms frames advanced, so a frozen render leaves
it stale — the honest signal a progress-delta watchdog kills on (unlike
updated_at, which the heartbeat keeps fresh even during a stall)."*

That reasoning is correct and the column is never written, so **the honest signal
is always null and any watchdog keyed on it can never fire.** The post-upload
watchdog I shipped keys on the worker's own write state instead, which is why it
works — but a frozen-*render* watchdog remains impossible until this is wired.

**Verdict: WIRE IT or delete it (§4.8).** It is not a candidate; it is inert
machinery with a documented purpose.

## SECOND: a duplicated safe-zone doctrine, one copy inert

```
handler.py:1024        _safe_zones_for()   ← ZERO call sites
design_system.py:149   safe_zones()        ← live, and its docstring says
                                             "Mirrors handler._safe_zones_for"
```

Two copies of one doctrine, one of them dead — and the live copy documents itself
as mirroring the dead one. **Verdict: delete handler's copy (§4.8); the mirror
comment becomes the definition.** Anti-drift matters here: two safe-zone
doctrines that can disagree is exactly the class the MG fingerprint exists for.

## ZERO-CALL FUNCTIONS — the full list, adjudicated

| function | verdict |
|---|---|
| `handler.py:34352 _start_render_frame_watcher` | **REAL — wire or delete.** See above. |
| `handler.py:1024 _safe_zones_for` | **REAL — delete**, duplicated by design_system. |
| `handler.py:25424 align_caption_tokens` | investigate — `_apply_caption_alignment` is live; likely a superseded twin |
| `handler.py:9806 _frame_activity_timeline`, `9849 _gap_visual_activity` | investigate — dead-air/transition work |
| `handler.py:21769 _kb_crop_exprs`, `23544 get_pitch_preserving_speed_filter` | likely dead: speed-ramping is forbidden by standing law, Ken-Burns crop retired |
| `handler.py:5754 _cyrillic_lid` | multilingual LID; may be reached via a registry |
| `handler.py:34768 diagnose_upload_handler`, `35365 _tl_add` | diagnostics/timeline helpers |
| `burned_text.py:192 detect_burned_in_text` | investigate |
| `general_editor.py:110 build_perception`, `168 _route_guidance` | general-editor is HELD pre-Step-0; expected |
| `ffmpeg_base.py:213 _spring_response_expr` | zoom easing; may be string-built |
| `surgical_ops.py:52 caption_override_anchor` | surgical v2 is dark by design |

## ANALYTICS EVENTS

**Written, never read (3)** — all three are **mine, from this week**:
`burst_double_hold`, `caption_modes_applied`, `design_system_built`.

They are read ad-hoc from the shell, not from committed code. That is the
"cost with no answer" shape and it is fair: **an instrument with no committed
reader is one context-loss away from being noise.** They belong in
`scripts/verify_envelope_fixes.js` or the scoreboard. **Owed.**

**Read, never written (11)** — mostly FALSE POSITIVES, and the sweep cannot see
why: `upload_started`, `upload_completed`, `export_completed`,
`not_talking_head_rejected`, `too_long_rejected`, `too_short_rejected`,
`no_audio_rejected` are written by the **iOS client**, which is not in either
swept tree. `delivery_stamp_lost` **does** have a writer
(`dispatch-to-modal.js:836`) — the sweep missed it because the two repos are
swept as separate roots.

**The sweep's own limitation, stated:** it covers two of three trees. A
cross-repo event map needs the client in scope, and until then every
"read-never-written" here must be checked by hand before it means anything.

## ZERO-IMPORT MODULES (74)

Dominated by legitimate standalone entrypoints — `preflight_quiet_window.py` and
`predeploy_no_regress.py` are invoked as SUBPROCESSES by `deploy.sh`,
`owner_sql_watch.py` is a CLI, and `*_app.py` are Modal harnesses run via
`modal run`. The sweep's `import`-based test cannot see subprocess invocation.

**Worth checking**: `caption_proof.py`, `gap3_proof.py`, `perceptual_sync_check.py`,
`pexels_coverage_probe.py`, `phase3_block.py`, `phase3_ceiling.py`,
`quality_table.py`, `mg_entrance_step_audit.py` — one-shot probes from finished
investigations. If their question is answered, §4.8 applies.

**A first pass excluded nothing and returned 179**, burying 5 real findings under
174 of stale-worktree noise. Skipping `.claude/`, `models/`, `golden/` and
`bundle/` is what made the list readable — a sweep nobody reads finds nothing.
