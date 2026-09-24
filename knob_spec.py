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
    # ── STAMP AND SECTIONDIVIDER: HELD, DIAGNOSED, THEN RESTORED ─────────
    # Both came back DIFFERENT from the first before/after pair and both were
    # held. A bisect — drop one knob at a time, then all at once — found two
    # DIFFERENT causes, and neither was "the cut is unsafe":
    #
    #   STAMP  every knob dropped alone was SAME, and dropping ALL SIX was
    #          also SAME. The first DIFFERENT verdict does not reproduce: it
    #          was comparing against a registry snapshot that had moved for
    #          other reasons, not a real change. I held a component on a
    #          harness artefact, and only the bisect separated the two.
    #
    #   SECTIONDIVIDER  showScrim and showVignette were the movers, and NOT
    #          eyebrowColor/numberColor as I first diagnosed from reading the
    #          destructure. The real cause was a TWO-TREE DIVERGENCE: the jsx
    #          said false, the tsx said TRUE, so dropping the prop let the
    #          tsx default take over. Our own renders had been putting a
    #          full-frame scrim and vignette over the picture. Fixed in the
    #          tsx and pinned by a new two-trees leg; the cut is then clean.
    #
    # THE LESSON IS THE ORDER. Reading the source gave me a confident wrong
    # cause twice; the bisect gave the right one in one run each time.
    # `style` IS NOT CUTTABLE AND THE RENDER IS THE ONLY THING THAT SAID SO.
    # Stamp reads `const d = STYLE_DEFAULTS[props.style ?? "seal"]` and then
    # derives THREE other defaults from it — size, fontSize and mark. Cut
    # `style` from __mapped and the deriver can no longer resolve `d`, so
    # those three COLLAPSE:
    #
    #     size      900   -> 0
    #     fontSize   64   -> 0
    #     mark      star  -> none
    #
    # A registered size of 0 renders nothing. That is the failure a cut is
    # supposed to be incapable of, arriving through a prop that was not even
    # in the cut list.
    #
    # AND MY BISECT SAID IT WAS FINE, because it deleted props from the props
    # OBJECT at render time and never re-derived the registry. Dropping a prop
    # is not the same operation as CUTTING it: only the second changes what
    # the deriver can resolve for everything else. The bisect answered a
    # question I had not asked, and it answered it correctly.
    "Stamp": ["distress", "doubleRing", "entryScale", "fontKey", "textShadow"],
    "SectionDivider": ["eyebrowColor", "fontKey", "numberColor", "scrimColor",
                       "showScrim", "showVignette", "vignetteStrength",
                       "textShadow"],
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
