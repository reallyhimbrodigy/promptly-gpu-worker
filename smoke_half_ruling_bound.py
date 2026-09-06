"""SMOKE — a half-ruled beat gets EXACTLY TWO attempts, then it is dropped.

WHY THIS EXISTS. Round 12 logged "beat 10: incomplete after 7 attempts" and
"beat 3: incomplete after 8 attempts" against a rule documented as
"two attempts, then terminal". The counter was a SINGLE GLOBAL incremented on
every rule_all_beats call, so it measured how many times the tool ran, not how
many chances a beat had — wrong in both directions at once:

  * the message printed the CALL count, so a beat dropped correctly on its own
    second attempt was reported as "after 7 attempts";
  * once the global passed 2, a beat that first went incomplete LATER was
    dropped on its FIRST offence, with no second chance at all.

Both are the same shape as the livelock this bound was written to end: a refusal
that is neither satisfiable nor terminal.
"""
import sys

FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)


def bound(sequence):
    """Replay the per-beat bound over a sequence of reject-sets, one per call.

    Mirrors the shipped logic: increment per beat present in this call's reject
    set, drop at 2, keep asking the rest.
    """
    att, dropped, asked_each_call = {}, [], []
    for reject in sequence:
        # ONCE DROPPED, STAYS DROPPED — mirrors the shipped guard. Without it a
        # beat the agent re-rules after its drop is counted and dropped again,
        # and "terminal" becomes a slower loop.
        reject = {b for b in reject if b not in dropped}
        for b in reject:
            att[str(b)] = att.get(str(b), 0) + 1
        spent = {b for b in reject if att[str(b)] >= 2}
        dropped.extend(sorted(spent))
        asked_each_call.append(sorted(reject - spent))
    return {"dropped": dropped, "asked": asked_each_call, "attempts": att}


# ── the shipped rule: two attempts per beat ────────────────────────────────
r = bound([{10}, {10}, {10}, {10}])
ok(r["dropped"] == [10], f"beat 10 dropped {len(r['dropped'])} times, expected once")
ok(r["attempts"]["10"] == 2,
   f"beat 10 accrued {r['attempts']['10']} attempts before dropping, expected 2 "
   f"— this is the 'after 7 attempts' defect")
ok(r["asked"] == [[10], [], [], []],
   f"beat 10 was asked again after being dropped: {r['asked']}")

# ── A BEAT THAT GOES INCOMPLETE LATE STILL GETS TWO ────────────────────────
# The global counter dropped these on sight. This is the half the old bound got
# backwards, and it is the one that silently discards work.
r = bound([{1}, {1}, {3}, {3}])
ok(r["dropped"] == [1, 3], f"expected both dropped once each, got {r['dropped']}")
ok(r["attempts"]["3"] == 2,
   f"beat 3 was dropped after {r['attempts']['3']} attempt(s) — a beat that goes "
   f"incomplete after another beat has exhausted its budget must still get two")
ok(r["asked"][2] == [3],
   "beat 3 was not asked even once before being dropped")

# ── independence: one beat's budget never spends another's ─────────────────
r = bound([{1, 2, 3}, {2}])
ok(r["dropped"] == [2], f"only beat 2 reached two attempts, got {r['dropped']}")
ok(r["attempts"] == {"1": 1, "2": 2, "3": 1},
   f"attempts leaked between beats: {r['attempts']}")

# ── terminal: never more than two, however long the run ───────────────────
r = bound([{7}] * 12)
ok(max(r["attempts"].values()) == 2,
   f"a beat accrued {max(r['attempts'].values())} attempts over 12 calls — the "
   f"bound is not terminal, which is the livelock it was written to end")
ok(r["dropped"] == [7], f"beat 7 dropped {len(r['dropped'])} times")

# ── the shipped code must actually key on the beat ────────────────────────
src = open("agentic_editor_app.py", encoding="utf-8").read()
ok("half_ruling_attempts_by_beat" in src,
   "the per-beat counter is gone — a single global counts CALLS, not chances")
ok("_reject = _reject - _spent" in src and "half_ruling_dropped\") or [])" in src,
   "first-offence beats are not separated from spent ones; collapsing them "
   "loses beats that are neither retried nor dropped")

if FAIL:
    print("FAIL smoke_half_ruling_bound:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_half_ruling_bound — exactly two attempts per beat, late beats "
      "get their full two, budgets independent, terminal over 12 calls")
