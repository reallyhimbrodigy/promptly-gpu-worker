#!/usr/bin/env python3
"""Knobs cut from the registry, per component. Content slots are never here.

RULED BY ZAC 2026-09-24: every promoted graphic carries <=6 KNOBS with plain
names. Content slots do not count — `pill1..pill12` and `row1Title..row5Badge`
are what the component DRAWS, and cutting them would shrink capacity, which is
the opposite of what the no-baked-copy ruling bought.

WHAT A CUT DOES. The key is removed from `__mapped`, so the component receives
`undefined` and ITS OWN PARAMETER DEFAULT APPLIES. The registry then drops the
property because nothing reads it. So a cut HARDCODES THE CURRENT DEFAULT — it
does not change a value, and the render must come out byte-identical. That is
asserted by render pair, not assumed: src/remotion/knob_ab.mjs, the same
harness that decided the zIndex work.

THE RISK THIS FILE CARRIES. If a registered default ever disagreed with the
body's parameter default, cutting would silently CHANGE the render — the
registered default is the value today, and the body default becomes the value
tomorrow. That is the "registered default is the value" defect in reverse, and
it is why every cut is render-proven rather than reasoned about.

WHICH SIX KNOBS SURVIVE is a judgement, and the principle is: keep what a
model would plausibly set to match a video, cut what is render-craft. Colours
of the PRIMARY elements stay; colours of sub-parts go. One size/scale stays;
per-element sizing goes. Animation internals (stagger, reveal, blur) always
go — no agent has ever set one, and they exist because a human was tuning.
"""

CUT_KNOBS = {
    # ── STAMP AND SECTIONDIVIDER ARE HELD, AND THE RENDER IS WHY ─────────
    # Both came back DIFFERENT from the before/after pair. The claim that a
    # cut "hardcodes the current default" is FALSE for them, and the harness
    # caught it — which is the entire reason the ruling says render first.
    #
    #   SectionDivider  eyebrowColor and numberColor have NO PARAMETER DEFAULT
    #                   in the body. The registry declares them
    #                   'rgba(255,255,255,0.78)' and '#C8551F'; cutting them
    #                   renders `undefined`. That is "the registered default
    #                   IS the value" exactly as this repo already recorded it
    #                   — 135 defaults wrong, 0 of 14 components drew — and
    #                   cutting would have shipped it silently.
    #
    #   Stamp           none of its six sit in the main destructure at all, so
    #                   where each default actually comes from is UNKNOWN and
    #                   I will not cut against an unknown.
    #
    # THE FIX IS TO HARDCODE THE REGISTERED VALUE IN THE BODY FIRST, then cut,
    # then re-render. That is a body change with its own proof, not a line in
    # this table, so both are held rather than half-done.
    # "Stamp": HELD — defaults not located in the body
    # "SectionDivider": HELD — two props have no body default
    # 18 -> 6. Everything about HOW the keyword is lit is craft; THAT it is lit
    # is the component.
    "PullQuote": ["barColor", "blurIn", "fontKey", "highlightTextColor",
                  "keywordColor", "keywordScale", "maxWordsPerLine",
                  "quoteMarkColor", "showQuoteMark", "textShadow",
                  "wordReveal", "wordStagger"],
    # 16 -> 6. Layout internals (padding, gaps, direction, fade) are the
    # marquee's own business.
    "PillMarquee": ["colorMode", "edgeFade", "firstDirection", "fontKey",
                    "gap", "glass", "paddingX", "paddingY", "rowGap",
                    "uppercase"],
    # 10 -> 6. Three sub-element colours nobody has set.
    "DropCard": ["mutedColor", "railColor", "spokenColor", "titleLead"],
    # 10 -> 6, plus statusBarTime: "9:41" is phone CHROME, not the user's
    # content, and it is the one non-slot text default in this set.
    "ChatThread": ["borderRadius", "minHeight", "showHomeIndicator",
                   "showStatusBar", "statusBarTime"],
}
