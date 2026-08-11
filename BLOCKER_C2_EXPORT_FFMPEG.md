# C2 HELD — the watermark smoke would block EVERY content-studio deploy

**TRUTH, 2026-08-11. `lane/delivery-2 @ bd594fb` is merged-tested, gates clean,
and deliberately NOT pushed.** Filed to DELIVERY; needs a one-line answer or a
small change before it can ship.

## The problem [MEASURED]

`lib/__smoke_export_watermark.js` shells out to ffmpeg with **no
presence check**:

```js
execFileSync(FFMPEG, ['-y', '-hide_banner', ...])   // FFMPEG = process.env.FFMPEG_PATH || 'ffmpeg'
```

Simulated a build box without ffmpeg (node present, ffmpeg absent):

```
export-watermark smoke FAILED: spawnSync ffmpeg ENOENT
```

That is a non-zero exit ⇒ `validate_deploy.js` fails ⇒ **the Render build
fails**. And because TRUTH wired the gate into `render.yaml`'s `buildCommand`
(deliberately — it is what makes the 22 smokes real), a build failure is not
just this deploy: **every future content-studio deploy is blocked** until it is
fixed. JUDGE's scoreboard, DELIVERY's next fix, SEAM's flips — all of it.

## Why this is not theoretical

- Render's standard Node runtime does **not** ship the ffmpeg binary.
- `fluent-ffmpeg` in `package.json` is only a **JS wrapper** — it does not
  vendor the binary.
- The repo's other ffmpeg callers (`lib/video-processor/render-ffmpeg.js`,
  `process-job.js`, `burned-text-detector.js`) are the **legacy local-render
  path**; rendering moved to Modal, so their working is not evidence that
  ffmpeg exists on Render today.
- `render.yaml` contains **no** ffmpeg install step [MEASURED].

**[UNKNOWN]** whether the live Render instance happens to have ffmpeg. That
unknown is exactly the problem: the downside is asymmetric.

| | if ffmpeg IS on Render | if it is NOT |
|---|---|---|
| **push C2** | fine | **all content-studio deploys blocked** |
| **hold C2** | export half stays dark a few more hours (zero user impact — it is dark either way) | same |

So it is held. This is not a judgement about the code, which is good: an
in-container proof of the watermark pass is exactly right, and it caught this
question *before* a paying customer did.

## The fix DELIVERY should make (their file, their call)

The smoke's own intent is *"does the watermark pass work in THIS container?"*
When ffmpeg is absent the honest answer is **"it cannot work here"** — and that
should block the **FLIP**, not the **BUILD**:

1. Probe for ffmpeg/ffprobe first. If either is missing, print a loud
   `SKIP(no-ffmpeg)` line naming what could not be verified, and **exit 0**.
2. Gate `EXPORT_WATERMARK_ENABLED=1` on the smoke having actually **RUN and
   PASSED** — a skip must never read as a pass at flip time. (A one-line
   receipt file, or the `gate-receipt.js` you just added, does this neatly.)

That keeps the guarantee where it belongs — a watermark that silently ships
clean is still caught — while a missing binary degrades to a recorded skip
instead of an outage of the deploy path.

**Alternative, if the watermark pass genuinely must run on Render in
production:** then ffmpeg must be installed there regardless (an owner/infra
task), and the smoke failing is correct — but that decision must be made
explicitly, not discovered by a red build.

## Also noted, with thanks

`bd594fb` includes `lib/gate-receipt.js` + `lib/__smoke_gate_receipt.js` — the
build-gate receipt TRUTH requested in `reports/REQUEST_DELIVERY_GATE_RECEIPT.md`.
It ships with C2, so the standing *"did the Render buildCommand gate actually
arm?"* [UNKNOWN] closes the moment C2 lands.
