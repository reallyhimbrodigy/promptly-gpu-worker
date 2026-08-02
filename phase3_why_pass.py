"""phase3_why_pass.py — evidence worksheet for the WHY class.

Zac's two-axis test (2026-08-01):
  AXIS 1  GUARANTEE / CATCH / DERIVE / NONE — what does CODE do about the
          outcome this rationale explains?
  AXIS 2  MECHANICAL / GENERALISE — does the model apply the parent rule by
          JUDGEMENT on novel footage, or is the outcome code-determined?

  DELETE  only where code GUARANTEES the outcome AND the clause is MECHANICAL.
  KEEP    wherever the model must generalise. "A rule carrying its reason
          handles cases the rule did not anticipate; a bare rule does not."
          Stripping rationale from a judgement-applied rule makes it brittle on
          exactly the edge cases that produce the quality complaints.

This script does NOT decide. It gathers the evidence a decision needs: for each
WHY clause it pulls the identifiers the clause is about (fields, components,
thresholds) and finds candidate ENFORCEMENT sites for them in handler.py
OUTSIDE the prompt region — so "code guarantees it" is a named line number
rather than an assertion. Classification is then done by hand against this
sheet, which is the only honest way to do axis 2.

    python3 phase3_why_pass.py                  # worksheet, heaviest first
    python3 phase3_why_pass.py --section B-ROLL
"""
import argparse
import re

import phase3_taxonomy as T
from prompt_token_map import build_map

# Enforcement shapes: the code actually DOES something about the outcome.
_ENFORCE = re.compile(
    r"\b(min|max|clamp|assert|raise|enforce\w*|validate\w*|_guard\w*|relocat\w*"
    r"|snap\w*|abort\w*|reject\w*|drop\w*|skip\w*|strip\w*|clip\w*|coerce\w*"
    r"|repair\w*|fallback|truncat\w*|cap\w*|floor|ceil)\b", re.I)

_IDENT = re.compile(r"\b([a-z][a-z0-9]*_[a-z0-9_]+)\b")          # snake_case fields
_COMPONENT = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")     # CamelCase names
_NUM = re.compile(r"\b(\d+(?:\.\d+)?)\b")

_STOP_IDENT = {"key_moments", "word_index", "start_word_index", "end_word_index"}


def prompt_region(lines):
    """Line span of the cached prefix, so we don't match the prose to itself."""
    lo = next(i for i, l in enumerate(lines) if 'system_instruction = f"""' in l)
    hi = next(i for i in range(lo, len(lines)) if lines[i].rstrip().endswith('"""') and i > lo)
    return lo, len(lines)  # everything after the open is prompt or builder; search before+after


def enforcement_sites(src_lines, idents, region):
    """Candidate guarding lines for these identifiers, outside the prompt prose."""
    lo, _ = region
    hits = []
    for i, line in enumerate(src_lines):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("*") or s.startswith("•"):
            continue
        # skip the prompt f-string body itself
        if lo <= i < lo + 1100:
            continue
        if not _ENFORCE.search(s):
            continue
        for ident in idents:
            if ident in s:
                hits.append((i + 1, ident, s[:110]))
                break
        if len(hits) >= 4:
            break
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", default=None)
    a = ap.parse_args()

    with open("handler.py", encoding="utf-8") as fh:
        src_lines = fh.read().split("\n")
    region = prompt_region(src_lines)

    rows = [r for r in T.tag_all() if r["cls"] == "WHY"]
    if a.section:
        rows = [r for r in rows if a.section.lower() in r["section"].lower()]
    rows.sort(key=lambda r: -r["tok"])

    print(f"WHY WORKSHEET — {len(rows)} clauses, "
          f"{round(sum(r['tok'] for r in rows)):,} tok\n")
    print("axis1 = GUARANTEE|CATCH|DERIVE|NONE   axis2 = MECHANICAL|GENERALISE")
    print("delete only GUARANTEE+MECHANICAL\n")

    for n, r in enumerate(rows, 1):
        idents = set(_IDENT.findall(r["clause"])) - _STOP_IDENT
        idents |= set(_COMPONENT.findall(r["clause"]))
        sites = enforcement_sites(src_lines, idents, region) if idents else []
        print(f"[{n:>3}] {round(r['tok']):>3}t  {r['section'][:22]:<22} {r['clause'][:118]}")
        if sites:
            for ln, ident, s in sites:
                print(f"          code  handler.py:{ln}  ({ident})  {s}")
        else:
            print(f"          code  none found for {sorted(idents)[:4] or '(no identifiers)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
