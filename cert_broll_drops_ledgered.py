"""CERT — every b-roll drop reaches the ledger (RULE-1).

WHY. The b-roll funnel could not be attributed: reference edits carry cutaways
at 3.32 per 25s, we deliver 0.04 on 4% of jobs, and only ~22 b-roll divergences
appeared across 130 organic jobs. The reason was not that b-roll is rarely
dropped — it was that SIX OF SEVEN DROP SITES ONLY print() to container stdout,
which is not queryable across jobs. The culling was invisible by construction,
so "13x from culling" was an inference with no evidence behind it either way.

Now every distinct drop cause records a divergence, mirroring the one site that
already did (the Pexels match-score floor).

THE SUMMARY LINE IS DELIBERATELY NOT LEDGERED. handler.py's
"[broll] N cutaway(s) dropped for overlay conflicts" is a SUMMARY of the
per-clip overlay drop directly above it; ledgering both would double-count every
overlay conflict and inflate exactly the number this exists to measure.

BOTH DIRECTIONS:
  PRESENT — each drop site carries a _record_divergence with a distinct reason.
  DISTINCT — the reasons do not collide, so the funnel can be cut BY CAUSE
             rather than counted in aggregate.
  NO DOUBLE-COUNT — the summary line stays unledgered.

Offline. Zero network, zero Modal, zero Gemini.
"""
import re
import sys

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"\n       :: {detail}" if detail else ""))


SRC = open("handler.py", encoding="utf-8").read()

REASONS = (
    "below_match_score_floor",      # pre-existing, the pattern the rest mirror
    "index_out_of_kept_range",
    "anchor_words_all_removed_by_cut",
    "no_portrait_candidate",
    "asset_over_byte_cap",
    "overlay_window_conflict",
)

print("=== C1: every drop cause reaches the ledger ===")
for r in REASONS:
    check(f"reason {r!r} is recorded", f'reason="{r}"' in SRC,
          "this drop is still print-only — the funnel stays blind here")

print("\n=== C2: each is a broll-component divergence with action 'drop' ===")
# Count broll drops rather than trusting one grep: the component must be "broll"
# so the funnel can be selected without string-matching action names.
# POSITIONAL, not a greedy group. The first attempt used
#   _record_divergence\(\s*\n\s*"broll",(.{0,600}?)\)
# whose non-greedy terminator matched the first ")" INSIDE the payload dict, so
# it saw one block instead of six. Scan forward a fixed window from each call
# site instead — no balanced-paren parsing needed for a presence check.
_starts = [m.start() for m in re.finditer(r'_record_divergence\(\s*\n\s*"broll",', SRC)]
_with_drop = [i for i in _starts if '"drop"' in SRC[i:i + 700]]
check(f"at least 6 broll call sites (found {len(_starts)}) all with action 'drop' (found {len(_with_drop)})",
      len(_starts) >= 6 and len(_with_drop) >= 6,
      f"only {len(_with_drop)} — a site was added without the drop action")

print("\n=== C3: the reasons are DISTINCT (cuttable by cause) ===")
check("no duplicate reason strings", len(set(REASONS)) == len(REASONS))
for r in REASONS:
    check(f"  {r!r} appears exactly once", SRC.count(f'reason="{r}"') == 1,
          f"appears {SRC.count(chr(34) + r + chr(34))} times — causes would merge")

print("\n=== C4: the summary line is NOT ledgered (no double-count) ===")
_i = SRC.find("cutaway(s) dropped for overlay")
check("the summary print exists", _i > 0)
_after = SRC[_i:_i + 400]
check("no _record_divergence attached to the SUMMARY line",
      "_record_divergence" not in _after,
      "the summary is ledgered too — every overlay conflict is counted twice")

print("\n=== C5: the per-clip overlay drop IS ledgered ===")
_j = SRC.find("Overlay wins (more deliberate editorial moment)")
check("the per-clip overlay drop exists", _j > 0)
check("it carries a divergence",
      "_record_divergence" in SRC[_j:_j + 500],
      "the per-clip overlay drop is still silent")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
