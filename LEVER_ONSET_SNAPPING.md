# LEVER — ONSET SNAPPING

Filed 2026-08-24 from the reference corpus's first Pass A read. **Free to
measure, bounded to build, and it is the first craft property found that our
pipeline structurally cannot produce.**

## The measurement

Ten owner-selected references, cuts from ffmpeg, onsets from the audio envelope
(a ≥6 dB RMS rise), joined at a 120ms tolerance:

```
alignment   median 68%   range 40–90%
median Δ    72ms         range 27–167ms
cuts/s      median 0.24  range 0.14–0.69
```

**Our pipeline aligns cuts to audio nowhere.** Cuts are mechanical — silence and
filler removal — placed off the transcript. Every cut we make lands wherever the
words end, and an on-beat cut versus a 200ms-late one is invisible to every
instrument we own.

## The hypothesis: SNAP WHEN FAST, and it is testable

Alignment is not a universal rule in the corpus — it is a dial, and the
references sit at different settings. The obvious reading is that **fast cutting
requires onset alignment to feel intentional**, while slow cutting does not.

Tested on the ten:

```
cuts/s vs aligned_frac    r = +0.317
cuts/s vs median_delta    r = -0.423        (faster -> tighter)

fast (>=0.25 c/s)  n=5   align 72%   medianΔ 58ms
slow (<0.25 c/s)   n=5   align 61%   medianΔ 93ms
```

**The direction matches. The magnitude does not survive n=10.** r=+0.317 and
r=-0.423 on ten points are not significant, and the counter-examples are real:
one slow reference is tight (0.20 c/s, 80%, 32ms) and one fast-ish reference is
loose (0.40 c/s, 52%, 113ms). This is filed as a HYPOTHESIS WITH A DIRECTION,
not a finding — and it is exactly what more references resolve.

## The build, if it is taken

Bounded and cheap: the cut list already exists, onsets are ffmpeg-derived, and
snapping is arithmetic.

- For each mechanical cut, find the nearest audio onset. **If it is within a
  tolerance, move the cut to it; otherwise leave it alone.**
- **No model involvement. No per-job cost.** One ffmpeg pass already in budget.
- Tolerance is the whole design: too tight and it never fires; too loose and it
  moves cuts across words. The corpus's median Δ of 72ms is the starting point,
  and 120ms was the join tolerance that produced these numbers.

**THE CONSTRAINT THAT BINDS IT:** a cut that moves must still respect the word
boundary. Every timing here derives from a word index through the timing
authority, and snapping to an onset that sits mid-word would reintroduce the
second clock this pipeline has paid for twice. **Snap only within the silence
between words** — which is where onsets that matter mostly are.

## The check, before it ships

- A cert that a snapped cut never crosses a word boundary — RED-proven against a
  deliberately mid-word onset.
- A production counter for how often snapping FIRES. "Built and never fires" is
  the class with nine precedents here; alignment rate on real jobs is the number
  that makes it reportable.
- Cut density recorded per job, so the snap-when-fast hypothesis is testable on
  our own traffic rather than only on the corpus.

## Not included, deliberately

**Motion character stays out of this lever.** The native-fps classifier put 141
of 141 corpus cuts in one bucket (`snap`) — one class, zero discrimination — and
it is UNPROVEN pending a known-eased control clip. Tuning its thresholds now
would manufacture the variety it is supposed to detect. The audio half stands on
its own; the motion half is not evidence yet.
