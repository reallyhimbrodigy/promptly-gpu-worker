# Background execution — what is missing between a completed job and a delivered notification

Scoped 2026-09-09. **The server side is not what is missing.** Every number below
is from queries I ran against the production DB and code I read; the iOS reading
is mine and the frontend lane owns that domain, so it should confirm.

## The requirement

Upload → finished product completes with the app closed. Not "resumes when they
come back" — completes, and the user is told.

## What already survives, verified

| link | state |
|---|---|
| upload | `URLSessionConfiguration.background`, `isDiscretionary=false`, `sessionSendsLaunchEvents=true` — survives closure |
| dispatch / render / delivery | server + Modal, already independent of the client |
| completion → push | `lib/lifecycle-push.js`, 11+ call sites, exactly-once claim, 15-min sweep for worker-written terminals |
| push → the video | `render-complete` tap handler opens that specific job |

`USER_LIFECYCLE_PUSHES` is **on**: the flag gate is checked BEFORE the claim, so
a claim marker can only exist if a send was attempted — and 4,886 jobs carry one
in 30 days. Pushes are being sent right now.

## The gap, per user (Rule 7)

Of **3,023 users who completed a job in the last 30 days**, 99.7% of them iOS:

    1,374 (45.5%)  reachable — have a device token
    1,649 (54.5%)  UNREACHABLE — no token exists to send to

Confirmed from the send side, independently: of 4,791 `render-complete` pushes,
**2,953 delivered to zero devices**. APNs rejected 0. There was nothing to send to.

## Why those 1,649 have no token

    1,056   declined the IN-APP SOFT PROMPT — never saw the OS dialog
      453   saw no prompt at all
       88   denied at the OS level — genuinely hard-blocked
       62   granted but no token — a real registration failure

**Only 88 users actually said no to iOS.** 94.2% of everyone who reached the
system dialog granted it.

## The mechanism, and it is one line

    var shouldOfferSoftPrompt: Bool { !hasAskedForPermission && !didOfferSoftPrompt }

`markSoftPromptOffered()` fires on **either** button of the in-app alert,
including "Not now". So a single "Not now" sets `didOfferSoftPrompt` forever:

  * the soft prompt never returns,
  * the OS dialog is never reached, so iOS stays `.notDetermined`,
  * and `maybeOfferDeliveryPrimer` also refuses, because it guards on
    `shouldOfferSoftPrompt` — the newer primer inherits the burn.

The decline rate on that alert is **44.7% (2,522 of 5,644)**. Nearly half of
everyone asked is permanently removed from the addressable set by one tap on a
custom alert that iOS never saw.

**These 1,056 users are not blocked by iOS.** Their OS state is still
`.notDetermined`, which means the system dialog would still show if the app
asked. The block is entirely our own flag.

## The primer is live but cannot reach them

`push_primer_viewed` = 118, accepted 55 (46.6%). It works. It is small because
it requires `shouldOfferSoftPrompt` — so it only reaches users who have NOT been
asked, and by construction never the 1,056 who were asked and said "not now".

The one recovery mechanism is gated on the absence of the thing it exists to
recover from.

## What the work is, smallest first

1. **Let the ask return.** The one-shot is per-install and permanent. A decline
   should cost a cooling-off period, not the addressable user. Re-offering to
   the 1,056 at a moment of demonstrated value costs nothing at the OS level
   because they are still `.notDetermined`.
2. **Ask after the payoff, not before it.** The primer converts at 46.6% at the
   moment the first video appears; the pre-render alert converts at 55.3%
   overall but burns the rest. Order matters more than copy.
3. **The 453 who saw nothing** — find out which trigger did not fire. Separate
   defect, and I have not diagnosed it.
4. **The 62 granted-but-no-token** — a real registration failure, 2.1%. Smallest
   of the four and the only one that is a bug rather than a policy.

## What I am NOT claiming

That any of this improves retention. It makes the completion reachable for the
54.5% it currently is not; whether a reachable user returns is a different
measurement with its own denominator.

I also have not verified the end-to-end path with the app force-quit on a real
device. Everything above is code and production data, not a device test, and the
requirement is specifically about the closed-app case.
