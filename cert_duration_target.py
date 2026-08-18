#!/usr/bin/env python3
""""MAKE IT 30 SECONDS" ANSWERS HONESTLY. `[Rule 1]`

A top-five request that is currently impossible. The dangerous failure is not
"it did not work" — it is **over-cutting to hit a number**: a video that reaches
30s by removing meaning is a worse answer than one that honestly reports 78s.

So the negotiation floor is the property under test, and the ladder order is the
mechanism that protects it: spend the cheapest seconds first (silence removes NO
words), stop the moment the target is met, and never touch a phrase retake for a
two-second trim.

Fake detectors are injected so the ladder is exercised deterministically — this
tests the POLICY, not the five detectors, each of which is already trusted on the
fresh path.

    python3 cert_duration_target.py
"""
import sys

import duration_target as D


def words(n, per=1.0):
    """n words, `per` seconds each, contiguous."""
    return [{"word": f"w{i}", "start": i * per, "end": (i + 1) * per}
            for i in range(n)]


def det(**by_class):
    """Build the detector dict the policy expects, from class -> [indices]."""
    name = {c: f for c, f in D.LADDER}
    out = {}
    for cls, idxs in by_class.items():
        out[name[cls]] = (lambda ii: (lambda w: [{"word_index": i} for i in ii]))(idxs)
    return out


def main():
    fails = []

    def chk(nm, cond, detail=""):
        if not cond:
            fails.append(f"{nm}{(' — ' + detail) if detail else ''}")

    W = words(60)                      # 60 words, 1s each, 60s source

    # 1. IMPOSSIBLE — we cannot add footage. Must say so, not silently no-op.
    r = D.plan_to_target(words(25), 25.0, 30.0, det(silence=[1, 2]))
    chk("target longer than the source must be IMPOSSIBLE",
        r["verdict"] == "impossible", r["verdict"])
    chk("impossible must remove NOTHING", r["remove_words"] == [], str(r["remove_words"]))
    chk("impossible must carry an honest sentence", "already shorter" in r["message"])

    # 2. MET — reachable inside the ladder.
    r = D.plan_to_target(W, 60.0, 55.0, det(silence=list(range(10))))
    chk("a reachable target must be MET", r["verdict"] == "met", r["verdict"])
    chk("met must reach at or under the target",
        r["achieved_s"] <= 55.0 + 1e-6, f"achieved {r['achieved_s']}")

    # 3. THE FLOOR — the property this cert exists for. Ladder exhausted, target
    #    still short: report the honest number, remove ONLY what the ladder
    #    offered, and never cut further.
    r = D.plan_to_target(W, 60.0, 20.0, det(silence=[0, 1, 2], filler=[3, 4]))
    chk("an unreachable target must return FLOOR", r["verdict"] == "floor", r["verdict"])
    chk("floor must NOT over-cut past what the ladder offered",
        len(r["remove_words"]) == 5, f"removed {len(r['remove_words'])}")
    chk("floor must report the achievable duration, not the target",
        abs(r["achieved_s"] - 55.0) < 0.01, f"achieved {r['achieved_s']}")
    chk("floor must say what going further would cost",
        "cutting what you" in r["message"], r["message"][:60])

    # 4. LADDER ORDER — a small trim must never reach a phrase retake.
    r = D.plan_to_target(W, 60.0, 58.0,
                         det(silence=[0, 1, 2, 3], filler=[10],
                             phrase_retake=[20, 21, 22]))
    chk("a 2s trim must be paid for with SILENCE only",
        r["spent_rungs"] == ["silence"], str(r["spent_rungs"]))
    chk("a 2s trim must NOT touch a phrase retake",
        all(i not in (20, 21, 22) for i in r["remove_words"]), str(r["remove_words"]))

    # 5. ...and a deep cut MAY reach it, in order, only after the cheap rungs.
    r = D.plan_to_target(W, 60.0, 52.0,
                         det(silence=[0, 1], filler=[10, 11],
                             false_start=[12], stutter=[13],
                             phrase_retake=[20, 21, 22, 23]))
    chk("a deep cut must spend rungs in ladder order",
        r["spent_rungs"][:2] == ["silence", "filler"], str(r["spent_rungs"]))
    chk("a deep cut reaching rung 5 must have used every cheaper rung first",
        ("phrase_retake" not in r["spent_rungs"]) or
        all(c in r["spent_rungs"] for c in
            ("silence", "filler", "false_start", "stutter")), str(r["spent_rungs"]))

    # 6. DEDUPE — a word flagged by two rungs is removed ONCE, at its cheapest.
    ranked, _ = D.rank_removable_spans(W, det(silence=[5], phrase_retake=[5]))
    chk("a doubly-flagged word appears once", len(ranked) == 1, str(ranked))
    chk("...and at its CHEAPEST rung",
        ranked and ranked[0]["class"] == "silence", str(ranked))

    # 7. A MISSING RUNG IS SKIPPED, NEVER TREATED AS EMPTY-AND-FINE. If a
    #    detector is unavailable, the floor must not be reported as if that rung
    #    had been evaluated and found empty.
    ranked, seen = D.rank_removable_spans(W, det(silence=[1]))
    chk("only evaluated rungs are reported as seen",
        seen == ["silence"], str(seen))

    # 8. NO TARGET => untouched.
    r = D.plan_to_target(W, 60.0, None, det(silence=[1]))
    chk("no target must leave the plan alone",
        r["verdict"] == "no_target" and r["remove_words"] == [], str(r))

    # 9. THE INVARIANT ACROSS EVERY BRANCH: achieved never goes below the floor.
    for tgt in (5.0, 20.0, 40.0, 59.0, 60.0, 120.0):
        r = D.plan_to_target(W, 60.0, tgt,
                             det(silence=[0, 1, 2], filler=[3], stutter=[4]))
        if r["verdict"] in ("met", "floor"):
            chk(f"achieved must never undercut the floor (target {tgt})",
                r["achieved_s"] >= r["floor_s"] - 1e-6,
                f"achieved {r['achieved_s']} floor {r['floor_s']}")

    if fails:
        print("CERT DURATION-TARGET: FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CERT DURATION-TARGET: PASS")
    print("  impossible / met / floor all answer honestly; nothing over-cuts")
    print("  ladder spends cheapest-first and stops early — a 2s trim stays on silence")
    print("  doubly-flagged words removed once at their cheapest rung")
    print("  achieved never undercuts the floor, in any branch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
