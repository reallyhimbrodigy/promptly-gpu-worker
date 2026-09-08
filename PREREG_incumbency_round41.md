# Pre-registration — StatCard incumbency, round 41

Written while round 41 is IN FLIGHT (fingerprint 7cfeb5da03a6e3ea) and **before
any result from it exists**. Launched by Builder-1 before I wrote this; I have
seen no MG CATALOGUE, no CARD PROPS line and no frames. Recorded now because the
prediction has been open since round 37 and I have twice been unable to test it,
which is exactly the situation in which a criterion gets invented after the fact.

## What I predicted, and what already happened to it

Original mechanism (fe3a544): the agent picks StatCard because it is the only
component it has been told anything about. 29 types were offered as BARE NAMES.

**That was tested and it failed.** Round 39 put a claim line for all 29 types in
the cached prefix and MG CATALOGUE still read `1 distinct of 29, StatCard=4`. I
pre-registered that as a refutation and I am not withdrawing it. Rounds 40 and 41
do not get to re-run the same prediction; visibility-as-description is dead.

The new intervention is different in kind and must be judged as a NEW claim:
round 41 is the first where the agent is told each component's PROP SHAPE — what
it would have to supply to use one. Description makes a component *nameable*;
props make it *usable*.

## What the agent can currently see (measured 2026-09-08)

    SYSTEM prompt        names  2 of 29   (StatCard, ProgressBar)
    _KNOWLEDGE_SYSTEM    names  1 of 29   (StatCard)
    tool schemas         names 29 of 29   (enum + the new prop table)

So StatCard remains the ONLY type named in prose the agent reads. That is a live
alternative explanation and it is not addressed by this change.

## The confound that would let me explain away a bad result

**A beat with a quoted figure choosing StatCard is CORRECT, not incumbency.**
talking_head's beats are stat-heavy — round 39's four cards carried 10,000, $400,
3 and 30,000. If every card beat in round 41 quotes a number, StatCard=N is the
RIGHT answer and says nothing about incumbency either way.

So the verdict is cut by beat content, not by the raw distinct count:

    incumbency  = StatCard chosen on a beat with NO quoted figure
    correct     = StatCard chosen on a beat WITH one

`1 distinct of 29` on three stat beats is not evidence of incumbency. I am
stating this BEFORE the numbers because it is the exact escape hatch I would
otherwise reach for afterwards.

## Resolution criteria

Judged across ALL fixtures in the round, not talking_head alone.

1. **Cards do not build.** Nothing resolves. The props fix failed and that is a
   separate defect to chase. Not a data point about incumbency.

2. **Cards build, ≥2 distinct types.** The prop-shape claim is SUPPORTED: the
   barrier was usability, not description. Weak if the second type appears once;
   report the count, never just "≥2".

3. **Cards build, 1 distinct, and ≥1 card beat has NO quoted figure.**
   Incumbency SURVIVES a second intervention. My mechanism is wrong twice, and
   the remaining candidates are (a) StatCard being the only type named in prose,
   and (b) genuine editorial fit. I will say which I think it is and I will not
   propose a third round of the same shape.

4. **Cards build, 1 distinct, and EVERY card beat quotes a figure.**
   UNRESOLVED, and I must say so rather than bank it. The round could not
   distinguish incumbency from correct selection, and the answer needs a fixture
   whose card beats are not stat-shaped.

## Denominator

Report `n` card beats and `n` fixtures with any card. Below 3 card beats total,
no outcome above is anything but suggestive, and I will say so.

## What I will not do

Re-run this prediction a fourth time on a new intervention and call the earlier
failures untested. Rounds 39, 40 and 41 are three attempts; 39 refuted the
original mechanism, 40 could not test anything (zero cards built), and 41 tests a
different claim. That is the record.

---

# AMENDMENT (2026-09-08, still before any round-41 number)

Builder-1 applied my own criterion 4 to round 39 and it holds. I am withdrawing
the refutation and marking round 39 **UNRESOLVED**.

Round 39's four card beats quoted 10,000, $400, 3 and 30,000. Every one warranted
a StatCard. So the agent was never on a beat where naming a different component
was the right answer, and visibility-as-description was never put in a position
to fail. `1 distinct of 29` there means what it means on any all-stat set:
nothing.

**A confound that makes a positive result unreadable makes a negative result
unreadable too.** I wrote the rule for round 41 and did not apply it backwards.

## This correction favours me, which is why it needs stating plainly

It converts a failed prediction of mine into an untested one. That is the shape
of an argument I should distrust, so the test is whether the logic stands
independent of who benefits — and it does, because it is symmetric and it is
mine. A beat that genuinely warrants StatCard cannot discriminate between "chose
it because it is the only one it knows" and "chose it because it is right."

**The corrected record is WORSE for the project, not better.** Not "one
refutation and two nulls" but THREE ROUNDS THAT TESTED NOTHING:

    round 39   all four card beats stat-shaped — no discriminating beat
    round 40   zero cards built — nothing to measure
    round 41   running on v1, where the only card-generating fixture is
               stat-shaped, so it lands here again by construction

The mechanism has never been tested. That is not a rescue; it is a more expensive
finding than a clean refutation, because three rounds bought no information.

## One asymmetry that keeps round 39 above zero evidence

The agent chooses WHICH BEATS get cards as well as which component. With claim
lines for all 29 types in the prefix, an agent that understood PullQuote or
EditorialQuote had the option of carding a quote beat instead of, or as well as,
a stat beat. It carded four stat beats. That is weak evidence against the
mechanism — weak because beat selection has its own drivers and I have not
isolated them, and because n=1 fixture.

So: **UNRESOLVED, leaning slightly against.** Not refuted, not alive.

## What I will not now do

Treat "visibility is dead" as settled, and treat it as vindicated. It is neither.
The next test needs a fixture whose card beats are NOT stat-shaped — which is in
v3, and which round 41 cannot reach.

## What this does not change

Round 40's zero-cards finding and the prop-shape fix stand on their own: the
agent invented a key name because it had never been told any component's props,
and that was directly observed in round 40's skip line, not inferred from a
distinct count.
