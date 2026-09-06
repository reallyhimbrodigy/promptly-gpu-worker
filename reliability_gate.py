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
        # GREEN MEANS THE FULL VIDEO (2026-09-05). There is no partial credit.
        # A result that shipped something lesser — components dropped, a stage
        # skipped, an output flagged degraded — is NOT a pass, because the user
        # asked for their video and got a substitute. Any of these markers fails
        # the round even though `ok` is True, so a future degrade path cannot
        # quietly satisfy this gate.
        # A PASSTHROUGH IS NOT A PASS (2026-09-05). Round 3 returned ok=True on
        # all five fixtures, and four of them kept 100% of the source with 0-3
        # placements — `music` produced a byte-for-byte passthrough with ZERO
        # placements against a brief that asked for "cuts landing on the beat".
        # `ok` means the pipeline did not crash. It does not mean it did the
        # job, and a gate that conflates the two would have armed a production
        # cutover after ten consecutive rounds of unedited video.
        #
        # Evidence of WORK is therefore part of green: a full edit must have
        # changed something. Both signals count, because a legitimate edit may
        # be all-cuts (a tighten) or all-placements (an overlay pass) — but not
        # neither.
        placed = v.get("placements")
        kept = v.get("kept_ratio")
        if placed is not None and kept is not None:
            did_nothing = (placed == 0) and (kept is not None and kept >= 0.999)
            if did_nothing:
                return False, (f"{src}: PASSTHROUGH — kept {kept} of the source "
                               f"and declared {placed} placements. ok=True only "
                               f"means it did not crash.")
        # A CONTRACT VIOLATION FAILS THE ROUND, it does not warn. Every fixture
        # rendered at 540x960 against a 1080x1920 contract for three rounds while
        # the harness logged `wrong_resolution` as a ledger event and the gate
        # called those rounds green. A violation the gate tolerates is a
        # violation that ships.
        for v_ in (v.get("contract_violations") or []):
            return False, (f"{src}: CONTRACT VIOLATION {v_!r} — the output does "
                           f"not meet the pipeline's own contract, which is not "
                           f"a warning")
        for marker in ("degraded", "partial", "components_dropped", "fallback"):
            if v.get(marker):
                return False, (f"{src}: ok but {marker}={v[marker]!r} — green "
                               f"means the FULL video, not a lesser one")
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


def assert_no_degrade_paths(sources):
    """NO DEGRADED OUTPUT, EVER — enforced against the code, not remembered.

    Replaces assert_fallbacks_tested (2026-09-05). That function made declaring a
    fallback create an obligation to TEST it; the contract has since changed to
    forbid degraded output outright, so the obligation is now the opposite one:
    no degrade path may exist to be tested. External calls retry to success,
    internal failures get root-caused, and the only terminal state is a clean
    refund-and-retry.
    """
    banned = ("degraded_composite_plan", "render_degraded", '"degraded": True',
              "ships_degraded")
    hits = []
    for name, src in (sources or {}).items():
        for b in banned:
            if b in src:
                hits.append(f"{name}: {b}")
    if hits:
        raise AssertionError(
            f"degrade path(s) present: {hits}. A degraded result is a defect "
            f"wearing a success's clothes — it converts a diagnosable failure "
            f"into an invisible quality loss the user never asked for. Fix the "
            f"cause or refund and let them retry.")
    return {"checked": sorted((sources or {})), "degrade_paths": 0}
