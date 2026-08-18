#!/usr/bin/env python3
"""NO COMPONENT IS SCORED AGAINST A SOURCE THAT CANNOT TRIGGER IT. `[Rule 1, Rule 5]`

THE MISTAKE THIS MAKES UNCONSTRUCTIBLE. Three corpora in a row were selected on
properties unrelated to the component under test, and each would have reported a
CORRECT DECLINE as a component failure:

  REF-2            already edited; declining to decorate finished work is good
                   judgement, not a defect
  editorial_eng_*  no spoken name and no stated number, so brand_copy 0/4 was
                   N/A — emitting brand copy there would be FABRICATION, which
                   the directive explicitly forbids
  golden/*         measured 2026-08-17: brand_copy testable on 1 of 12, scenes
                   on 0, payoff on 0

Every source in the component corpus must therefore carry at least one directive
trigger, the manifest must record WHICH, and each component needs more than one
source — a single source cannot separate a decline from noise.

The corpus is also DURABLE (feedback_ab_durable_sources): pinned by sha256 +
etag + bytes in our own bucket, never live user media, because an A/B on drifted
bytes compares two different things.

    python3 cert_component_corpus.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "component_corpus_manifest.json")
MIN_PER_COMPONENT = 2
# The product's own band: the cap is 120s and the latency law is 90s end-to-end.
MIN_DUR_S, MAX_DUR_S = 15.0, 90.0


def main():
    if not os.path.exists(MANIFEST):
        print("CERT COMPONENT-CORPUS: FAIL\n  - manifest missing; run "
              "build_component_corpus.py --write")
        return 1
    man = json.load(open(MANIFEST))
    srcs = man.get("sources") or []
    fails = []

    if not srcs:
        fails.append("the corpus is empty")

    seen_sha = {}
    for s in srcs:
        sid = s.get("id", "?")
        trig = s.get("triggers") or {}
        if not any(trig.values()):
            fails.append(f"{sid} carries NO trigger — any component scored "
                         f"against it would count a correct decline as a defect")
        for f in ("s3_key", "sha256", "etag", "bytes"):
            if not s.get(f):
                fails.append(f"{sid} is not durably pinned: missing {f}")
        # Identical bytes under two ids double-weights one opinion. The text
        # hash cannot catch this — two ASR runs of ONE video differ in text.
        sha = s.get("sha256")
        if sha:
            if sha in seen_sha:
                fails.append(f"{sid} has identical media to {seen_sha[sha]} "
                             f"(sha256) — one source counted twice")
            seen_sha[sha] = sid
        d = s.get("duration_s") or 0
        if not (MIN_DUR_S <= d <= MAX_DUR_S):
            fails.append(f"{sid} is {d}s, outside the product band "
                         f"{MIN_DUR_S:.0f}-{MAX_DUR_S:.0f}s — it measures a "
                         f"regime users do not have")

    comps = set()
    for s in srcs:
        comps |= set((s.get("triggers") or {}).keys())
    cov = {c: sum(1 for s in srcs if (s.get("triggers") or {}).get(c)) for c in comps}
    for c, n in sorted(cov.items()):
        if n < MIN_PER_COMPONENT:
            fails.append(f"component {c!r} has {n} source(s); {MIN_PER_COMPONENT} "
                         f"minimum — one source cannot separate a decline from noise")

    if fails:
        print("CERT COMPONENT-CORPUS: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT COMPONENT-CORPUS: PASS")
    print(f"  {len(srcs)} sources, every one carrying a recorded trigger")
    print(f"  coverage: {cov} (min {MIN_PER_COMPONENT}/component)")
    print(f"  all durable (sha256+etag+bytes), no duplicate media, all in band")
    return 0


if __name__ == "__main__":
    sys.exit(main())
