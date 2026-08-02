"""phase3_taxonomy.py — Zac's taxonomy, weighted in TOKENS, on the live prompt.

Zac's ruling (2026-08-01):
    KEEP  GOAL · DIRECTION · CONTEXT
    CUT   CONSTRAINT · WHY · CONTRADICTION
"the goal we want to move toward, not the reasons or the prohibitions."

WHY THIS MEASURES THE PROMPT, NOT THE LEDGER
  PHASE1_FACT_LEDGER's 1,086 items are PARAPHRASES with no per-item line refs,
  so their character weight is not the prompt's token weight — re-tagging them
  would answer "how many items" and not "how many of the 40,473 tokens". The
  question Zac asked is a token question, so the classes are applied to the live
  cached prefix and the ledger is used for what it uniquely holds: the §5
  CONTRADICTION register (seeded verbatim below).

WHY THE UNIT IS THE CLAUSE, NOT THE SENTENCE
  Zac's classes split INSIDE sentences, and that split is the whole lever:
      "Place it in the EMPTY SPACE: the gap above the head (upper)   <- DIRECTION
       — a graphic on the face is the most obviously-amateur thing"  <- WHY
  Sentence-level tagging would score that entire sentence one class and hide the
  exact tokens Zac wants cut. So text is split on sentence boundaries and then
  on em-dash / semicolon / colon / parenthetical seams.

HONESTY
  This is a keyword-and-shape classifier, not a judge. Its output is a MAP, not
  a verdict on any line. `--audit N` emits a stratified random sample for hand
  scoring so the reported weights carry a measured precision, not an assumed
  one. Run that before believing the totals.

    python3 phase3_taxonomy.py                 # class weights, overall + per section
    python3 phase3_taxonomy.py --audit 120     # stratified sample to hand-score
    python3 phase3_taxonomy.py --class WHY --section B-ROLL   # inspect one cell
"""
import argparse
import random
import re
import sys

from prompt_token_map import CHARS_PER_TOKEN, VERTEX_BASELINE_TOKENS, build_map

KEEP = ("GOAL", "DIRECTION", "CONTEXT")
CUT = ("CONSTRAINT", "WHY", "CONTRADICTION")

# ── §5 CONTRADICTIONS REGISTER (ledger), seeded as exact prompt phrases ───────
CONTRADICTION_PHRASES = [
    "the peak set is fixed upstream",
    "a snap would read as just another mid_peak",
    "the slowest and deepest move of the video",
    "LAST RESORT ONLY",
    "single largest act turn",
    "16 sounds",
    "first 2 seconds",
    "re-pictures the literal words",
]

# ── ordered rules; FIRST MATCH WINS. Order is itself a stated decision. ───────
_PROHIBIT = re.compile(
    r"\b(never|don't|do not|must not|cannot|can't|no longer|not allowed|forbidden"
    r"|avoid|refuse|reject|suppress|banned|off-limits|last resort|except|unless"
    r"|at most|no more than|only when|only if|only for|caps? at|capped|ceiling"
    r"|maximum|minimum|floor|budget of|stays? under|stays? below)\b", re.I)
_LIMIT = re.compile(r"(≤|≥|<\s*\d|>\s*\d|\bno\s+\w+\s+(background|marks|name|card)\b)")

# Rationale: it explains a rule already given rather than telling you to act.
_WHY = re.compile(
    r"\b(because|since it|that's why|this is why|which is why|the reason"
    r"|is what makes|is why|otherwise|the metaphor depends|depends on it"
    r"|reads? as|reads? like|would read|announce themselves|is the most"
    r"|the viewer (feels|reads|calls|leaves|scrolls)|the eye goes)\b", re.I)
# A failure frame turns an outcome clause into a justification.
_FAILURE = re.compile(
    r"\b(amateur|wrong|broken|hollow|anxious|scattered|noise|costume|seam|defect"
    r"|glaring|mutilate\w*|clash\w*|leak\w*|stall\w*|drags?|busy|over-dressed"
    r"|unserved|deleted the|second-guessing|tell that a tool|reads decorated)\b", re.I)

_IMPERATIVE = re.compile(
    r"^\W*(emit|use|place|set|write|pick|read|keep|match|author|reach|weigh"
    r"|listen|lift|choose|anchor|trigger|pass|treat|name|hold|carry|give|make"
    r"|start|land|cut|fill|deviate|redistribute|compose|ground|report|look"
    r"|answer|run|apply|prefer|flip|split|add|drop|omit|show|quote|check)\b", re.I)

_GOAL = re.compile(
    r"\b(the goal|so the|so that|so it|the result|we want|should feel|should read"
    r"|feels? (inevitable|composed|intentional|earned)|reads? (composed|coherent"
    r"|inevitable|intentional|clean)|the version they wish|lands? twice"
    r"|the moment lands|stays the star)\b", re.I)


def clauses(text):
    """Sentence split, then em-dash / semicolon / colon / parenthetical seams."""
    out = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or set(line) <= set("─═-= "):
            continue
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z*\"'(])", line):
            for c in re.split(r"\s+—\s+|\s*;\s*|\s*:\s+|(?<=\))\s+|\s+\((?=[a-z])", sent):
                c = c.strip()
                if len(c) >= 12:
                    out.append(c)
    return out


_CAUSAL_OPENER = re.compile(r"^\W*(because|since|the reason|that is why|which is why)\b", re.I)
# Component routing ("scattered notes -> StickyNotes") is DIRECTION; the arrow
# makes it a lookup, whatever failure-flavoured noun it happens to contain.
_ROUTING = re.compile(r"[→>]\s*[A-Z]")


def classify(c):
    low = c.lower()
    if _CAUSAL_OPENER.match(c):
        return "WHY"
    if _ROUTING.search(c):
        return "DIRECTION"
    if _PROHIBIT.search(c) or _LIMIT.search(c):
        return "CONSTRAINT"
    if _WHY.search(c):
        # "reads as composed" (desired) vs "reads as costume" (failure) — the
        # failure frame is what makes an outcome clause a justification.
        return "WHY" if _FAILURE.search(c) or not _GOAL.search(c) else "GOAL"
    if _FAILURE.search(c):
        return "WHY"
    if _IMPERATIVE.match(c):
        return "DIRECTION"
    if _GOAL.search(c):
        return "GOAL"
    return "CONTEXT"


def tag_all():
    rows = []
    for section, text in build_map()["sections"].items():
        for c in clauses(text):
            rows.append({"section": section, "clause": c,
                         "cls": classify(c), "tok": len(c) / CHARS_PER_TOKEN})
    return rows


ALL = KEEP + CUT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", type=int, default=0)
    ap.add_argument("--class", dest="cls", default=None)
    ap.add_argument("--section", default=None)
    ap.add_argument("--seed", type=int, default=20260801)
    a = ap.parse_args()
    rows = tag_all()

    if a.cls or a.section:
        sel = [r for r in rows
               if (not a.cls or r["cls"] == a.cls.upper())
               and (not a.section or a.section.lower() in r["section"].lower())]
        print(f"{len(sel)} clauses, {round(sum(r['tok'] for r in sel)):,} tok\n")
        for r in sorted(sel, key=lambda r: -r["tok"])[:60]:
            print(f"  [{r['cls']:<13} {round(r['tok']):>4}t] {r['clause'][:150]}")
        return

    if a.audit:
        random.seed(a.seed)
        per = max(1, a.audit // len(ALL))
        print(f"STRATIFIED AUDIT SAMPLE (seed {a.seed}) — score each, then compute precision\n")
        for cls in ALL:
            pool = [r for r in rows if r["cls"] == cls]
            for r in random.sample(pool, min(per, len(pool))):
                print(f"[{cls}] {r['clause'][:170]}")
            print()
        return

    tot = sum(r["tok"] for r in rows)
    print("ZAC'S TAXONOMY — token weight on the live cached prefix")
    print(f"clauses={len(rows):,}  classified tokens={round(tot):,} "
          f"of the {VERTEX_BASELINE_TOKENS:,}-token prefix "
          f"({100 * tot / VERTEX_BASELINE_TOKENS:.0f}%; the rest is headers/whitespace)\n")

    print(f"{'tok':>7} {'share':>7} {'clauses':>8}  verdict  class")
    print("-" * 62)
    for cls in ALL:
        sel = [r for r in rows if r["cls"] == cls]
        t = sum(r["tok"] for r in sel)
        verdict = "KEEP " if cls in KEEP else " CUT "
        print(f"{round(t):>7,} {100 * t / tot:>6.1f}% {len(sel):>8,}  {verdict}    {cls}")
    print("-" * 62)
    keep = sum(r["tok"] for r in rows if r["cls"] in KEEP)
    cut = sum(r["tok"] for r in rows if r["cls"] in CUT)
    print(f"{round(keep):>7,} {100 * keep / tot:>6.1f}%           KEEP  GOAL+DIRECTION+CONTEXT")
    print(f"{round(cut):>7,} {100 * cut / tot:>6.1f}%            CUT  CONSTRAINT+WHY+CONTRADICTION")
    print(f"\nIf every CUT-class token vanished: {VERTEX_BASELINE_TOKENS:,} -> "
          f"~{round(VERTEX_BASELINE_TOKENS - cut):,} = "
          f"{VERTEX_BASELINE_TOKENS / max(1, VERTEX_BASELINE_TOKENS - cut):.2f}x")
    print("That is the CEILING for classification alone, and it assumes a total")
    print("delete of every constraint — which Zac's step 3 explicitly does not do")
    print("(constraints get REPLACED by the goal they protect, not removed).\n")

    print(f"{'section':<46} {'CUT tok':>8} {'CUT %':>7}")
    print("-" * 64)
    per_sec = {}
    for r in rows:
        d = per_sec.setdefault(r["section"], {"cut": 0.0, "all": 0.0})
        d["all"] += r["tok"]
        if r["cls"] in CUT:
            d["cut"] += r["tok"]
    for sec, d in sorted(per_sec.items(), key=lambda kv: -kv[1]["cut"]):
        print(f"{sec[:45]:<46} {round(d['cut']):>8,} {100 * d['cut'] / max(1, d['all']):>6.1f}%")


if __name__ == "__main__":
    sys.exit(main())
