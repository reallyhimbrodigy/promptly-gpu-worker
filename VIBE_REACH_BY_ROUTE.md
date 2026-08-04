# DOES THE VIBE REACH EVERY ROUTE?

Traced in code, not inferred. `input_data["vibe"]` per route:

| route | n | share | reads the vibe? | how |
|---|---|---|---|---|
| standard_editorial | 818 | 46.0% | **YES** | the editorial prompt |
| moodreel | 307 | 17.3% | **YES** | `build_moodreel_prompt(input_data.get("vibe"), …)` |
| hype | 25 | 1.4% | **YES** | `build_hype_prompt(input_data.get("vibe"), …)` |
| **minimal** | 204 | 11.5% | **NO** | `build_minimal_plan(_dur, fps, motion_curve)` — no vibe parameter exists |
| **minimal_speech_uncut** | 424 | 23.8% | **NO** | no plan at all; passthrough |

**628 jobs / 601 USERS / 35.3% of completions receive a video that never
consulted what they asked for.** They export at 12.4%.

⚠️ One correction to the brief: **hype DOES read the vibe.** The no-decision
routes are two, not three — `minimal` and `minimal_speech_uncut`.

## THE RE-ROUTE ZAC ASKED FOR IS ALREADY BUILT, AND IT IS DARK

> "Start by routing the no-speech cases there instead of to uncut."

`_silent_route_eligible()` does exactly that. It is gated on
`PROMPTLY_SILENT_TO_MOODREEL`, whose default is **OFF**:

```python
def _silent_to_moodreel_enabled():
    """PROMPTLY_SILENT_TO_MOODREEL=1 arms the re-route. Default OFF => today's
    routing, byte-identical."""
```

**Addressable today, if flipped:**

| route | route_reason | n | users | export now |
|---|---|---|---|---|
| minimal_speech_uncut | transcription_incomplete | 124 | 119 | 18.5% |
| minimal_speech_uncut | no_speech_muted | 87 | 86 | 12.6% |
| **minimal** | **no_speech_muted** | **58** | **55** | **3.4%** |
| **TOTAL** | | **269** | **260** | |

The safety property is already right: `_vad_confirms_silence()` is
**positive-confirmation only** and fails safe to uncut, so a clip we merely
failed to TRANSCRIBE but which actually carries speech is not re-cut as silent
b-roll. That was the obvious way this could destroy speech, and it is guarded.

**Where I would expect the gain, and where I would not:** the `minimal` /
`no_speech_muted` arm is at **3.4%** and has the most room. The
`transcription_incomplete` arm already exports at 18.5% — above the 13.3%
average — so I would watch that one for a REGRESSION rather than a gain.

This is a live-secret value change, so per the standing rule it needs an
explicit GO naming the key: **`PROMPTLY_SILENT_TO_MOODREEL`**. And a secret flip
is not live until a redeploy — memory snapshots capture `os.environ` at deploy
time.

## THE MINIMUM EDITORIAL CALL EACH ROUTE COULD MAKE

- **minimal** — `build_minimal_plan` already computes cuts from a motion curve.
  It takes no `vibe`. The cheapest real fix is a vibe parameter that steers the
  three constants it already has: `target_clip_s` (pace), `transition_every`,
  and the trim window. That is a decision made from the user's words with no
  extra model call.
- **minimal_speech_uncut** — makes no plan at all. The honest floor is the
  moodreel call when VAD confirms silence (above), and for the genuinely
  speech-bearing ones an intake note rather than a silent passthrough.

## Method and cost

Route and reason from `result.route` / `result.route_reason` over 1,781
completions since 2026-07-25, joined to `export_completed`. Vibe plumbing read
from source. **Spend: zero.**
