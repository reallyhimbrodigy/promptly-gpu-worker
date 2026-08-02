"""phase3_block.py — the per-BLOCK Phase-3 gate.

Read-only. Extracts a live block from handler.py by line range, diffs a candidate
rewrite against it through cert_prompt_content_diff (content words + numbers +
names + DO-NOT-COLLAPSE invariants), and reports Vertex-calibrated tokens.

    python3 phase3_block.py --lines 5744,5762 --section "MOTION GRAPHICS" \
                            --candidate blocks/mg_anchor.txt

Exit 0 = PASS (nothing removed, no invariant collapsed). Exit 1 = FAIL.
A block only reaches handler.py after this exits 0.
"""
import argparse
import sys

import cert_prompt_content_diff as C
from prompt_token_map import VERTEX_BASELINE_TOKENS, build_map


def live_block(lo, hi):
    with open("handler.py", encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    # RAW source text — candidates are written as they will sit in handler.py,
    # doubled braces and all, so what certs is exactly what ships.
    return "\n".join(lines[lo - 1: hi])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", required=True, help="LO,HI 1-indexed inclusive in handler.py")
    ap.add_argument("--section", required=True, help="section name, for the invariant check")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--label", default=None)
    a = ap.parse_args()

    lo, hi = (int(x) for x in a.lines.split(","))
    original = live_block(lo, hi)
    with open(a.candidate, encoding="utf-8") as fh:
        rewrite = fh.read()

    cpt = build_map()["chars_per_token"]
    ok, rep, collapsed = C.cert_section(a.section, original, rewrite)
    tb, ta = round(len(original) / cpt), round(len(rewrite) / cpt)

    label = a.label or f"{a.section} L{lo}-{hi}"
    print(f"\n=== {label} ===")
    print(f"  tokens   {tb:,} -> {ta:,}   ({tb - ta:+,}; ratio {tb / max(1, ta):.2f}x)"
          f"   [Vertex-calibrated @ {cpt} chars/tok, baseline {VERTEX_BASELINE_TOKENS:,}]")
    print(f"  content  {rep['n_content_original']:,} -> {rep['n_content_rewrite']:,} distinct words")
    if rep["lost_content_words"]:
        print(f"  LOST WORDS   ({len(rep['lost_content_words'])}): {rep['lost_content_words']}")
    if rep["lost_numbers"]:
        print(f"  LOST NUMBERS ({len(rep['lost_numbers'])}): {rep['lost_numbers']}")
    if rep["lost_names"]:
        print(f"  LOST NAMES   ({len(rep['lost_names'])}): {rep['lost_names']}")
    for iid, missing, desc in collapsed:
        print(f"  INVARIANT COLLAPSED: {iid} missing {missing} — {desc}")
    print(f"  {'PASS — nothing removed' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
