# Resolution defaults — AI video, credits per 5-second clip
# Builder 2 · 2026-09-23 · for Zac's ruling

Rows are model x resolution, priced from `credit_prices.py`, which is read from
ChatCut's **/docs/credits-policy** page (not /pricing) on 2026-09-23. Our
credits are `ceil(their_rate x 10)` per second — `OUR_PER_THEIRS = 10` — and
the last column is that number x 5.

| model | resolution | ChatCut credits/sec | our credits/sec | **credits per 5s clip** |
|-------|-----------|--------------------:|----------------:|------------------------:|
| Seedance 2.0 Fast | 480p | 0.16500 | 2 | **10** |
| Seedance 2.0 | 480p | 0.28000 | 3 | **15** |
| Seedance 2.0 Fast | 720p | 0.36000 | 4 | **20** |
| Seedance 2.5 | 480p | 0.39820 | 4 | **20** |
| Gemini Omni | 720p | 0.40544 | 5 | **25** |
| Kling 3.0 Standard | 720p | 0.60000 | 6 | **30** |
| Seedance 2.0 | 720p | 0.60000 | 6 | **30** |
| Kling 3.0 Pro | 1080p | 0.80000 | 8 | **40** |
| Seedance 2.5 | 720p | 0.89600 | 9 | **45** |
| Seedance 2.0 | 1080p | 1.32000 | 14 | **70** |
| Seedance 2.5 | 1080p | 2.21750 | 23 | **115** |

11 rows, and the spread across them is **11.5x on the same five seconds**
(10 to 115). That is the whole argument against the flat `AI_VIDEO_CREDITS = 20`
this replaces: it was under cost on seven of these eleven rows and 5.8x under
at Seedance 2.5 / 1080p.

## Recommended default: **Seedance 2.0 at 720p — 30 credits per 5s clip**

720p is the floor that survives the canvas: the app renders 1080x1920, so a
480p generation is upscaled 2.25x on the long edge and reads as soft b-roll,
which is worse than no b-roll — and Seedance 2.0 rather than Seedance 2.0 Fast
(20) because quality wins over speed in every trade, including the cheap one.

Two notes on the recommendation rather than the number:

  * **This is the incumbent.** `AI_VIDEO_DEFAULT = ("Seedance 2.0", "720p")` is
    already the constant in `generation_billing.py`. I am recommending it
    rather than moving it, because the standing instruction is that no constant
    changes until you have seen it — and because I could not find a reason to
    move it that was not just "cheaper".
  * **A default is a vote for the incumbent, and it will win almost every
    time.** Whatever sits here is what nearly every generation costs, because
    the registered default IS the value on every request that does not override
    it. If 30 is the wrong number, it is wrong 90%+ of the time, not
    occasionally.

## What free users can reach at these prices

A free balance is **10 credits**. The cheapest row on this table is 10, so a
free user could afford exactly one 480p Seedance 2.0 Fast clip and nothing
else — which is why AI video is Pro-only and why the free brief now says so in
those words: *"Only generate new images, music or sound effects if asked. Don't
generate video or voiceover."* An image is 5 credits, so the free balance is
sized for two images, and the old free line told their agent to refuse them.

## Not on this table

`avatar` has **no published rate at all** on the credits-policy page, and
`image` and `motion_graphics` are published as VARIABLE ("by model, output
quality, resolution, and image count"). They are in `UNPRICED` with ChatCut's
own words, and `priceFor` refuses them rather than returning a guess: a real
charge priced from an invented number is the error that costs money rather
than credibility.
