# Person segmentation for text-behind-subject `[§3.1 component C]`

**Spike result: the evaluation was already run, and it chose. This documents the
choice, the constraint nobody has priced yet, and the merge path.** No Modal
spend. No re-derivation of work that exists.

---

## 1 — What the local inventory actually allows `[MEASURED]`

```
absent     cv2          OpenCV (DNN + GrabCut)
absent     mediapipe    SelfieSegmentation
absent     rembg        U2-Net
absent     torch        RVM / MODNet host
absent     onnxruntime  CPU inference
AVAILABLE  Pillow 12.3.0
ffmpeg:    alphaextract · alphamerge · maskedmerge · chromakey · colorkey · despill
```

**No CV runtime is installed in this checkout**, so a local model benchmark is
not possible without adding dependencies. What *is* available is the entire
**compositing** half: `alphamerge` + `maskedmerge` are exactly the operators
text-behind-subject needs once a matte exists. The hard part is the matte; the
composite is solved.

## 2 — The evaluation already happened `[behind-layer-phase1]`

`matting/matting_app.py` is a complete sibling Modal app, and its choices are
made and reasoned:

| decision | value | why |
|---|---|---|
| model | **Robust Video Matting** (PeterL1n) | video matting, not per-frame segmentation — it carries recurrent state, so edges do not flicker between frames |
| variants | `rvm_mobilenetv3` (fast) · `rvm_resnet50` (best) | a real quality/cost ladder rather than one setting |
| weights | **baked into the image** | no runtime download — the same law as the Remotion bundle |
| downsample | fast 0.25 · best 0.375 · full 1.0 | RVM's guidance: the backbone wants ~256-512px on the short side |
| lead-in | **1.0s before each window** | the recurrent state must settle or the first frames bite |
| alpha post | temporal median (3) → erode 1px → feather 1.0px | |

And the tiebreak is written down, which is the part that matters most:

> *"a hair-thin dark bite (erode) reads better than a bright un-dimmed halo —
> the wash shot is the worst case and the tiebreak."*

That is a taste ruling backed by a specimen, with `bite/lag` metrics and a
"matte quality ladder" in commits `9859bde` / `04733da`. **Re-running this spike
would produce the same answer more expensively.**

## 3 — RECOMMENDATION

**Adopt RVM as chosen. Merge `behind-layer-phase1`, do not rebuild.**

The remaining work is not research:

1. **Merge and re-cert** against current HEAD (the branch predates ~2 weeks of
   worker changes).
2. **Price it** — see §4, the open question.
3. **Wire it into the Lumen scene vocabulary** — text-behind-subject is a
   *composition* the plan asks for, so it needs a spec field and a renderer
   path, not just a matte service.

**Do NOT switch to MediaPipe/rembg/U2-Net.** They are per-frame segmenters: no
temporal state, so edges shimmer on video. RVM exists precisely because that
class of model fails on moving footage, and the branch already learned it.

## 4 — THE OPEN QUESTION NOBODY HAS PRICED `[§4.1, §2.1]`

**RVM is GPU.** The matting app is a *separate* Modal app with its own GPU
image, and every one of these is unpriced today:

- **Latency** — matting runs per window with a 1s lead-in each. §4.1 gives
  editing **120s total**, and text-behind-subject is an *editing* effect, not a
  generative one, so it gets **no carve-out**. If matting adds 30s to a 90s
  render, the law is broken by a component.
- **Cost** — a second GPU app per job, against §2.1's ≤$1 Lumen budget which is
  already sized around scene generation.
- **Concurrency** — a sibling app that spawns per job is a second scaling
  surface, and the `.spawn()`-orphan class has bitten this project before.

**These three are the gate, not the matte quality.** The quality question is
answered; the affordability question has never been asked. First measurement
when the campaign opens: **one window, one clip, wall-clock and dollars** —
which is a single priced run, not a spike.

## 5 — Where it sits in the vocabulary

Text-behind-subject is component **C**, and it is the only Lumen component that
needs a *service* rather than a renderer. That makes it the natural **last** of
the deterministic vocabulary: D (name-plate), F (end-cards), A (keyword
emphasis) and the canvas work all render from the plan with no external call,
so they carry no latency or cost risk. C is where the vocabulary stops being
free.

**Sequencing consequence:** build D/F/A/landscape first (done), merge C second,
and let the §4.1 measurement decide whether C ships inside the two-minute law or
becomes the first editing component to need its own budget conversation.
