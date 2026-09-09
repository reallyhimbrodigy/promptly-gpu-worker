# Scoping retrieval and a reference-grounded ruling surface — before building

Measured against the corpus, not estimated. 153 beats, 10 videos, 426.1s.

## What the corpus actually records per beat

    t_start, duration_s, purpose, treatment[], read
    raw.speaker_on_screen, raw.cutaway_subject, raw.card_text   (all 153)

`read` averages 151 chars. Whole corpus, reads plus metadata: **36,875 bytes,
~9,200 tokens.**

## The number that decides option 2

    reference treatment   beats    %      our family
    ────────────────────────────────────────────────────────────
    overlay_text           124   81.0%    text
    cut                     81   52.9%    cut
    cutaway                 72   47.1%    NOTHING — we do not do cutaways
    card                    40   26.1%    card
    sfx                     14    9.2%    sfx
    punch_in                 6    3.9%    zoom
    (none)                   0    0.0%    transition — ZERO reference examples

**47.1% of the reference corpus places a cutaway.** Cutaway was deliberately
removed from the rubric (2026-09-06) because the pipeline cannot do it.

## Option 2 — the corpus as the decision surface. It breaks, and specifically.

"The agent points at the reference beat this moment resembles, and the harness
applies the analogous placement. A placement can only exist if a reference beat
justified it."

Architecturally the strongest, and three things break on this corpus:

1. **Half the corpus points at a capability we do not have.** 72 of 153 beats
   place a cutaway. An agent pointing at the beat its moment genuinely resembles
   will land on one of those 47% of the time, and the harness has nothing to
   apply. Either it refuses (and half the good analogies produce nothing) or it
   applies the non-cutaway remainder (and the citation no longer justifies what
   was placed — intent by construction becomes intent by approximation).

2. **transition becomes unrulable.** Zero reference beats carry a transition.
   Under "a placement can only exist if a reference beat justified it", the
   family is eliminated silently — not by a decision, by the corpus's shape.

3. **zoom becomes nearly unrulable.** 6 beats, 3.9%. Every zoom in every future
   edit would cite one of six examples. That is not intent, it is a bottleneck.

The failure mode is the one this lane keeps meeting: **a constraint that looks
principled and is actually a property of the sample in front of it.** It would
also be invisible — a round with zero transitions reads as an editorial choice.

**Not buildable on this corpus.** It becomes buildable if cutaway ships, or if
the corpus is re-annotated to mark which beats are reachable.

## Option 1 — retrieve the matching moment. Buildable now, and cheap.

Fetch the k reference beats most like this one and show those.

**The join key already exists.** `zoom_arc` already asks the agent what a moment
IS in the arc — hook | build | mid_peak | payoff | breather | close — and the
corpus's `purpose` is hook | claim | turn | evidence | payoff | close | breath.
Four values coincide. Extending the arc question from zoom to every beat gives a
join key the agent is already used to supplying, and one it answered for zoom in
every round.

Match on: purpose, beat duration, speaker on screen, whether a figure is quoted.
All four exist on both sides today.

    purpose     beats   card%   text%   sfx%   avg dur   speaker on screen
    evidence      52     35%     81%      2%    3.11s      13/52  — mostly OFF
    claim         30      7%    100%      7%    2.99s      29/30  — on
    close         22     50%     64%     18%    3.98s      13/22
    turn          19     21%     79%      5%    1.22s      14/19
    hook          14     21%     93%     36%    2.40s      12/14
    payoff        10     10%     90%      0%    2.56s       7/10
    breath         6     17%     17%     17%    0.82s       3/6

That table alone answers "when does a placement earn its moment" per family,
from the examples rather than from prose.

### Cost, measured

    whole corpus in the prefix          36,875 bytes   ~9,200 tokens
    k=3 matched beats per our beat        ~700 bytes     ~175 tokens
    a 7-beat fixture, k=3                ~4,900 bytes   ~1,225 tokens
    a 10-beat fixture, k=3               ~7,000 bytes   ~1,750 tokens

**Injected into the beats brief, which is already in the cached prefix**, so it
is one cache write per run and pennies per turn after — the same economics Zac
described. Retrieval happens in the harness at brief time, so it costs no model
turn and no agent decision.

**Latency: zero network.** 36,875 bytes ships as a mounted JSON file. There is
no retrieval infrastructure to build — the whole corpus is smaller than one
knowledge doc.

### Against the four pillars

    COST      +1,225 tokens of cached prefix on a 7-beat fixture. Round 45
              talking_head was $0.0535; cached input at Sonnet rates puts this
              in the tenths of a cent per run. Inside the $0.10 law.
    SPEED     zero. No extra turn, no network, no model call.
    RELIABILITY  a mounted file with a cert that regenerates it from the corpus,
              so it cannot drift and grows when the corpus does.
    QUALITY   the point. Four real examples of what an editor did at a moment
              like this one, at the moment of ruling.

### What breaks

- **The agent may imitate a cutaway it cannot make**, exactly as in option 2 —
  but here it is a shown example rather than a binding citation, so the fix is
  to EXCLUDE cutaway-only beats from what is retrieved. 81 of 153 beats carry no
  cutaway and remain. That is a filter, not an architecture change.
- **zoom retrieves from 6 examples** and will look repetitive. Honest answer:
  say so in the brief rather than pretend six is a corpus.
- **transition retrieves nothing.** It must return an explicit "no reference
  example exists for this family" rather than an empty list that reads as
  "nothing to say".

## Recommendation

Build option 1, with the cutaway filter. It is cheap, needs no new
infrastructure, and puts the examples in front of the agent at the moment it
rules — which is Zac's actual requirement.

Option 2 is the better architecture and is blocked on a corpus where 47% of the
craft is a capability we do not ship. Worth revisiting the day cutaway exists.

**Not started. Reporting first, as asked.**
