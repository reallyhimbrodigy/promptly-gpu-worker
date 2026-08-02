"""phase3_ceiling.py — the MECHANICAL CAVEMAN CEILING, per section.

Read-only. Answers the only question that decides whether Phase 3 is worth
continuing: if we deleted EVERY structural word the cert permits us to delete —
no judgement, no readability, the theoretical maximum of "uniform caveman" — how
many tokens would the cached prefix actually lose?

Method: tokenize each section, drop every word on cert_prompt_content_diff's
STRUCTURAL stoplist, keep every content word / number / name verbatim, and
re-join with single spaces. The result is NOT shippable prose — it is the
LOWER BOUND on section size under the "keep every content word" contract, so
the ratio it reports is the UPPER BOUND on caveman compression.

Any real rewrite lands strictly worse than this, because real rewrites keep
enough connective tissue to stay readable. So: if this ceiling says 1.4x, no
amount of effort produces 2x, and a 5x claim is arithmetically impossible
without dropping content.

    python3 phase3_ceiling.py
"""
import re

import cert_prompt_content_diff as C
from prompt_token_map import build_map

_TOK = re.compile(r"\S+")


def strip_structural(text):
    """Maximal legal caveman: delete every structural word, keep all else."""
    out = []
    for raw in _TOK.findall(text):
        core = re.sub(r"^[^\w#$≥≤<>•·\-]+|[^\w%\"'\]})]+$", "", raw)
        low = re.sub(r"[^\w'-]", "", core).lower()
        if low and low in C.STRUCTURAL and not C._is_name(core) and not re.search(r"\d", core):
            continue
        out.append(raw)
    return " ".join(out)


def main():
    m = build_map()
    cpt = m["chars_per_token"]
    rows, tot_b, tot_a = [], 0, 0
    for label, text in m["sections"].items():
        floor = strip_structural(text)
        tb, ta = len(text) / cpt, len(floor) / cpt
        # Prove the floor is legal: nothing but structural words left.
        rep = C.audit(text, floor)
        legal = not (rep["lost_content_words"] or rep["lost_numbers"] or rep["lost_names"])
        rows.append((label, round(tb), round(ta), tb / max(1.0, ta), legal))
        tot_b += tb
        tot_a += ta

    print("MECHANICAL CAVEMAN CEILING — upper bound on lossless compression")
    print("(every structural word deleted; any readable rewrite lands WORSE than this)\n")
    print(f"{'tok now':>8}  {'floor':>7}  {'CEILING':>8}  {'legal':>5}  section")
    print("-" * 78)
    for label, tb, ta, r, legal in sorted(rows, key=lambda x: -x[1]):
        print(f"{tb:>8,}  {ta:>7,}  {r:>7.2f}x  {'ok' if legal else 'LOSS':>5}  {label}")
    print("-" * 78)
    print(f"{round(tot_b):>8,}  {round(tot_a):>7,}  {tot_b / tot_a:>7.2f}x  {'':>5}  "
          f"WHOLE CORE (13 sections)")
    print(f"\nCeiling on the cached prefix: {m['baseline_tokens']:,} -> "
          f"~{round(m['baseline_tokens'] / (tot_b / tot_a)):,} tokens.")
    print("This is the arithmetic maximum. It is not shippable text.")


if __name__ == "__main__":
    main()
