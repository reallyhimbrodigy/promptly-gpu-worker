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

# The source set is a CONTRACT, not a config. Adding or removing one changes what
# "green" means, so it is a code change with a diff, not a flag.
#
# IT IS PER CORPUS, because the corpora do not share a fixture set and mapping
# one onto the other by name is actively dangerous: v3 carries a stray
# music-fb4aa93b.mp4 that is byte-identical to car_short, so a name-matched v3
# round would have scored a 10s silent car clip under a "cuts on the beat" brief.
#
# v1 is the flat/noise corpus every round from 35 to 41 unknowingly ran.
# v3 is Zac's real footage and is INCOMPLETE: three sources, not the five asked
# for. `motion` has has_speech=null at staging — its route is DELIBERATELY
# unassigned below rather than guessed, because assigning a fixture to the wrong
# route is how a speech target gets applied to a silent clip.
CORPUS_SOURCES = {
    "ab-sources/reliability-fixtures-v1": ("talking_head", "music",
                                           "screen_recording", "product_shot",
                                           "pet_video"),
    "ab-sources/reliability-fixtures-v3": ("talking_head", "motion", "car_short"),
}
DEFAULT_CORPUS = "ab-sources/reliability-fixtures-v1"
REQUIRED_SOURCES = CORPUS_SOURCES[DEFAULT_CORPUS]
REQUIRED_GREEN_ROUNDS = 10


def required_for(corpus):
    """The contract for one corpus. An unknown corpus RAISES.

    Never falls back to the default set: a round scored against another
    corpus's fixture names is the failure this whole change exists to stop,
    and a silent fallback is how it would come back.
    """
    try:
        return CORPUS_SOURCES[str(corpus).rstrip("/")]
    except KeyError:
        raise ValueError(
            f"no source contract for corpus {corpus!r}; known: "
            f"{sorted(CORPUS_SOURCES)}. Add it to CORPUS_SOURCES — changing "
            f"what 'green' means is a diff, not a fallback.")

# ── PER-ROUTE GATE SETS ──────────────────────────────────────────────────────
# A route arms on ITS OWN fixtures. The no-speech route is the cutover target —
# 46.5% of completed jobs, served by a reduced pipeline today — and it must not
# be held hostage to the speech path, which is not part of this cutover and is
# the harder problem.
#
# Splitting the gate is not weakening it: each route still needs ten consecutive
# green rounds over every fixture in ITS set, and a fixture missing from a round
# still fails that round. What changes is that a red talking_head no longer
# blocks a no-speech route that has been green for ten rounds on its own
# sources.
ROUTE_FIXTURES = {
    "no_speech": ("music", "screen_recording", "product_shot", "pet_video",
                  "car_short", "motion"),
    "speech":    ("talking_head",),
}

# `motion` WAS ABSENT FROM BOTH ROUTES until it was MEASURED, not guessed.
#
# Its staging `has_speech` was hand-declared null — the silence heuristic cannot
# separate continuous speech from ambient, and said so, which is why it refused
# to answer. The arbiter is the pipeline's own ASR, since the route branch is
# simply `"transcript" if words else "visual"`. Round 42 ran it:
#
#     [route] no speech -> VISUAL beats
#     SPEECH CHECK : NOT APPLICABLE - source carries no speech
#
# Zero words, so no_speech. Assigned off that observation, in a diff, as the
# comment this replaces asked for.
ROUTE_UNASSIGNED = ()


def route_of(source):
    for _route, _fx in ROUTE_FIXTURES.items():
        if source in _fx:
            return _route
    return None


def evaluate_route(rounds, route):
    """Consecutive green rounds for ONE route's fixtures.

    A round is green FOR A ROUTE when every fixture in that route's set is
    present and ok. Absence still fails — the whole point of the gate is that an
    unrun fixture is never a pass, and narrowing the set must not smuggle that
    back in.
    """
    fixtures = ROUTE_FIXTURES.get(route)
    if not fixtures:
        raise ValueError(f"unknown route {route!r}; known: {sorted(ROUTE_FIXTURES)}")
    streak, broke = 0, None
    for i in range(len(rounds) - 1, -1, -1):
        subset = {k: v for k, v in (rounds[i] or {}).items() if k in fixtures}
        missing = [f for f in fixtures if f not in subset]
        if missing:
            broke = {"index": i, "why": f"missing {missing} — absence is not a pass"}
            break
        green, why = round_is_green({**subset,
                                     **{f: {"ok": True, "placements": 1,
                                            "kept_ratio": 0.5}
                                        for f in REQUIRED_SOURCES if f not in fixtures}})
        if green:
            streak += 1
        else:
            broke = {"index": i, "why": why}
            break
    return {"route": route, "fixtures": list(fixtures),
            "consecutive_green": streak, "required": REQUIRED_GREEN_ROUNDS,
            "arms": streak >= REQUIRED_GREEN_ROUNDS, "streak_broken_by": broke}


def round_is_green(round_result):
    """One round: every required source present, and every one of them ok.

    `round_result` maps source -> {"ok": bool, ...}. A source that is missing,
    None, or not a dict is NOT green — it is unproven, and unproven is the same
    as failed for shipping purposes.

    EVERY FAILING LEG, NOT THE FIRST (2026-09-07). This returned on the first
    failure it found, so round 24 — red on talking_head's unresolved shortfall
    AND on screen_recording's passthrough — reported one of the two, and the
    second was found only because someone re-ran the gate by hand with the other
    fixtures stubbed clean. Reporting one leg makes a multi-cause round look
    like a single-cause one, and the fix for the reported cause then reads as a
    fix for the round. The whole point of this session was that what a scorer
    cannot show, nobody sees.
    """
    r = round_result or {}
    fails = []
    for src in REQUIRED_SOURCES:
        v = r.get(src)
        if not isinstance(v, dict):
            fails.append(f"{src}: NO RESULT (absent — never treated as a pass)")
            continue          # nothing further is knowable about this source
        if v.get("ok") is not True:
            fails.append(f"{src}: {v.get('why') or 'not ok'}")
        # GREEN MEANS THE FULL VIDEO (2026-09-05). There is no partial credit.
        # A result that shipped something lesser — components dropped, a stage
        # skipped, an output flagged degraded — is NOT a pass, because the user
        # asked for their video and got a substitute.
        # A PASSTHROUGH IS NOT A PASS (2026-09-05). Round 3 returned ok=True on
        # all five fixtures, and four of them kept 100% of the source with 0-3
        # placements — `music` produced a byte-for-byte passthrough with ZERO
        # placements against a brief that asked for "cuts landing on the beat".
        # `ok` means the pipeline did not crash. It does not mean it did the
        # job, and a gate that conflates the two would have armed a production
        # cutover after ten consecutive rounds of unedited video.
        placed = v.get("placements")
        kept = v.get("kept_ratio")
        if placed is not None and kept is not None:
            if (placed == 0) and (kept >= 0.999):
                fails.append(f"{src}: PASSTHROUGH — kept {kept} of the source "
                             f"and declared {placed} placements. ok=True only "
                             f"means it did not crash.")
        # A CONTRACT VIOLATION FAILS THE ROUND, it does not warn. Every fixture
        # rendered at 540x960 against a 1080x1920 contract for three rounds while
        # the harness logged `wrong_resolution` as a ledger event and the gate
        # called those rounds green. A violation the gate tolerates is a
        # violation that ships.
        cvs = list(v.get("contract_violations") or [])
        if cvs:
            # DEDUPED FOR DISPLAY, COUNTED IN FULL. talking_head reported the
            # same unresolved shortfall from three separate execute_plan calls;
            # printing it three times buries the distinct second violation
            # underneath. The count stays honest either way.
            seen, distinct = set(), []
            for c in cvs:
                if c not in seen:
                    seen.add(c); distinct.append(c)
            shown = "; ".join(repr(c) for c in distinct[:3])
            more = f" (+{len(distinct) - 3} more distinct)" if len(distinct) > 3 else ""
            fails.append(f"{src}: CONTRACT VIOLATION x{len(cvs)} "
                         f"({len(distinct)} distinct): {shown}{more} — the output "
                         f"does not meet the pipeline's own contract, which is "
                         f"not a warning")
        for marker in ("degraded", "partial", "components_dropped", "fallback"):
            if v.get(marker):
                fails.append(f"{src}: ok but {marker}={v[marker]!r} — green "
                             f"means the FULL video, not a lesser one")
    extra = sorted(set(r) - set(REQUIRED_SOURCES))
    if extra:
        fails.append(f"unknown source(s) {extra} in the round — the test set "
                     f"is a contract; a renamed source must not silently "
                     f"replace a required one")
    if fails:
        srcs = len({f.split(":", 1)[0] for f in fails})
        return False, (f"{len(fails)} failing leg(s) across {srcs} source(s):\n"
                       + "\n".join(f"  - {f}" for f in fails))
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
