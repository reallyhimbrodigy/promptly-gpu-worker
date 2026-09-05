"""THE RELIABILITY GATE — ten consecutive green rounds, or nothing ships.

WHY A SEPARATE MODULE. The gate must be able to fail the thing that produced
the runs it is judging. Living inside agentic_editor_app.py would make it
subject to the same import that a broken change breaks, and a gate that cannot
run when the code is broken is not a gate.

THE RULE, exactly as specified: the five-source test set runs green ten
consecutive times before anything ships; ONE failure resets the count to zero.

Everything below exists to make one specific lie impossible: a round that
LOOKS green because a source did not run. Absence is the shape every silent
defect in this product has taken, so absence is never a pass here — a round is
green only if every declared source is present AND ok. A gate that counts
"zero failures" instead of "five successes" would read an empty run as perfect,
and that is precisely the class this gate exists to catch.
"""

# The five sources are a CONTRACT, not a config. Adding or removing one changes
# what "green" means, so it is a code change with a diff, not a flag.
REQUIRED_SOURCES = ("talking_head", "music", "screen_recording",
                    "product_shot", "pet_video")
REQUIRED_GREEN_ROUNDS = 10


def round_is_green(round_result):
    """One round: every required source present, and every one of them ok.

    `round_result` maps source -> {"ok": bool, ...}. A source that is missing,
    None, or not a dict is NOT green — it is unproven, and unproven is the same
    as failed for shipping purposes.
    """
    r = round_result or {}
    for src in REQUIRED_SOURCES:
        v = r.get(src)
        if not isinstance(v, dict):
            return False, f"{src}: NO RESULT (absent — never treated as a pass)"
        if v.get("ok") is not True:
            return False, f"{src}: {v.get('why') or 'not ok'}"
    extra = sorted(set(r) - set(REQUIRED_SOURCES))
    if extra:
        return False, (f"unknown source(s) {extra} in the round — the test set "
                       f"is a contract; a renamed source must not silently "
                       f"replace a required one")
    return True, "all five green"


def evaluate(rounds):
    """Count CONSECUTIVE green rounds from the most recent backwards.

    Consecutive from the END, not a total: ten greens with a red in the middle
    is not a stable pipeline, it is a flaky one, and the reset is the entire
    point of the rule.
    """
    streak, broke_on = 0, None
    for i in range(len(rounds) - 1, -1, -1):
        green, why = round_is_green(rounds[i])
        if green:
            streak += 1
        else:
            broke_on = {"index": i, "why": why}
            break
    return {
        "rounds_recorded": len(rounds),
        "consecutive_green": streak,
        "required": REQUIRED_GREEN_ROUNDS,
        "ships": streak >= REQUIRED_GREEN_ROUNDS,
        "streak_broken_by": broke_on,
        "sources": list(REQUIRED_SOURCES),
    }


def assert_fallbacks_tested(pipeline_stages, tested):
    """A DECLARED FALLBACK WITH NO TEST IS A LIE.

    Contract point 1 is "every stage has a fallback, and the fallback is
    tested". The second half is the half that rots: a fallback nobody exercised
    is a comment. This makes the pair structural — declaring a fallback creates
    an obligation to test it, and the gate fails until that obligation is met.
    """
    declared = {n: m["fallback"] for n, m in pipeline_stages if m.get("fallback")}
    missing = sorted(set(declared) - set(tested or ()))
    if missing:
        raise AssertionError(
            f"stage(s) {missing} declare a fallback with NO TEST exercising it. "
            f"An untested fallback is a comment, not a fallback — it has never "
            f"been shown to produce a degraded result rather than a crash. "
            f"Declared: { {k: declared[k] for k in missing} }")
    return {"fallbacks_declared": len(declared), "tested": sorted(declared)}
