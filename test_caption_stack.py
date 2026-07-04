"""Caption-stack — the SINGLE-PAINT INVARIANT (2026-07-04 launch-day blocker).

Exhibit: job 4fc6dac9 painted "but," and "luckily," STACKED for ~1s: Deepgram
gave 'but' a prosody-stretched span (14.88-16.08) fully containing 'luckily,'
(15.005-15.645); page windows ran to the last word's END, so both page windows
were live and every style painted both. Drives the REAL page builder with the
REAL recovered word timings across all four seam classes."""
import handler as H

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))


def w(text, start, end):
    return {"word": text, "punctuated_word": text, "start": start, "end": end}


def assert_single_paint(pages):
    """The invariant: no two page windows overlap by even 1ms."""
    for a, b in zip(pages, pages[1:]):
        if a["startMs"] + a["durationMs"] > b["startMs"]:
            return False, f'"{a["text"]}" [{a["startMs"]}+{a["durationMs"]}] overlaps "{b["text"]}" @{b["startMs"]}'
    return True, ""


print("=== S1: the exhibit — 'but' containing 'luckily,' (real timings) ===")
words = [w("that", 14.2, 14.6), w("but", 14.88, 16.08), w("luckily,", 15.005, 15.645),
         w("we", 16.1, 16.3), w("made", 16.3, 16.6), w("it.", 16.6, 16.9)]
pages = H._build_tiktok_pages_from_projected(words, max_words_per_page=2)
ok, detail = assert_single_paint(pages)
check("exhibit pages non-overlapping by construction", ok, detail)
lk = [p for p in pages if "luckily" in p["text"]]
check("'luckily,' page exists and starts at its word", lk and lk[0]["startMs"] == 15005)
bt = [p for p in pages if p["text"].endswith("but")]
check("'but' page clamped to end at 'luckily,' start",
      bt and bt[0]["startMs"] + bt[0]["durationMs"] <= 15005)

print("\n=== S2: the towel anchor's latent pair — 'nice' containing 'warm' ===")
words = [w("a", 13.9, 14.1), w("nice", 14.24, 15.6), w("warm", 14.635, 15.035),
         w("towel", 15.1, 15.5), w("ready.", 15.5, 15.9)]
pages = H._build_tiktok_pages_from_projected(words, max_words_per_page=2)
ok, detail = assert_single_paint(pages)
check("towel pair non-overlapping", ok, detail)

print("\n=== S3: synthetic geometry — partial overlap, exact touch, gap ===")
words = [w("aa", 0.0, 1.2), w("bb", 1.0, 1.5),      # partial overlap
         w("cc.", 1.5, 2.0),                          # exact touch (legal)
         w("dd", 3.0, 3.4), w("ee.", 3.5, 3.9)]      # gap
pages = H._build_tiktok_pages_from_projected(words, max_words_per_page=1)
ok, detail = assert_single_paint(pages)
check("synthetic set non-overlapping", ok, detail)
check("exact-touch pages keep full duration (no over-clamp)",
      any(p["startMs"] == 1500 and p["durationMs"] == 500 for p in pages),
      str([(p['text'], p['startMs'], p['durationMs']) for p in pages]))
check("gapped page unclamped",
      any(p["startMs"] == 3000 for p in pages))

print("\n=== S4: seam classes stay safe by construction ===")
# cut-spanning: a page never spans a clip boundary (builder flushes there)
words = [w("end", 1.0, 1.4), w("start", 1.45, 1.9)]
pages = H._build_tiktok_pages_from_projected(words, max_words_per_page=2,
                                             clip_boundaries_sec=[1.42])
check("clip boundary splits the page (no cut-spanning paint)",
      len(pages) == 2 and assert_single_paint(pages)[0])
# position flip: same rule via position boundaries
pages = H._build_tiktok_pages_from_projected(words, max_words_per_page=2,
                                             position_boundaries_sec=[1.42])
check("position boundary splits the page (no flip-seam paint)",
      len(pages) == 2 and assert_single_paint(pages)[0])

print("\n=== S5: wiring pins ===")
src = open("handler.py").read()
check("builder carries the invariant clamp",
      "SINGLE-PAINT INVARIANT" in src and
      '_limit = pages[_pi + 1]["startMs"] - pages[_pi]["startMs"]' in src)
tsx = open("src/remotion/src/PromptlyRender.tsx").read()
check("renderer tripwire present ([caption-paint] deduped)",
      "[caption-paint] deduped" in tsx and "SINGLE-PAINT INVARIANT tripwire" in tsx)
check("tripwire clamps, never drops",
      "durationMs: Math.max(1, limit)" in tsx)
# premount guard audit (documented map; paints gated per style)
for style, pat in (("TypewriterReveal", "if (frame < 0) return null"),
                   ("Prime", "if (frame < 0) return null")):
    s2 = open(f"src/remotion/src/captions/{style}/{style}.tsx").read()
    check(f"{style} premount frame<0 guard", pat in s2)
for style, pat in (("Gadzhi", 'visibility: isSpoken ? "visible" : "hidden"'),
                   ("Lumen", "hasAppeared")):
    s2 = open(f"src/remotion/src/captions/{style}/{style}.tsx").read()
    check(f"{style} premount paint gated by word activation", pat in s2)

print(f"\n{'='*60}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
