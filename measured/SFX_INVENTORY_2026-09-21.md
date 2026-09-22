# The thirteen sounds: describable after all, and one number I got wrong

## THE SURFACE EXISTS, contrary to what both lanes concluded

An audio asset refuses `name` AND `description` via `edit_asset` — both errors
name the Zero schema. From that we both concluded the sounds were surfaceless
and that the whole sound half of the inventory hung on the KESTREL/MARLIN canary.

That was wrong, and one query settles it:

    browse_assets query "heavy landing"
      -> match.fields ["name"]
         snippets   ["name: boom - deep low impact for a heavy landing.ogg"]
         searchCoverage.metadata "complete"

The name is READABLE and INDEXED. It is only unwritable AFTER import — it comes
from the uploaded FILENAME. So a re-upload delivers a descriptive, searchable
name, and the sounds were never blocked on a project-level surface.

Not writable and not reachable are different claims, and we had collapsed them.

## A COMMA IN A FILENAME BREAKS THE IMPORT

Measured, from a failure:

    ffmpeg failed with exit code 8:
    [AVFilterGraph] No such filter: 'for a heavy landing-waveform-98360-1.txt'

The upload helper builds an ffmpeg FILTER GRAPH from the filename, and ffmpeg
separates filters with commas. A descriptive filename containing a comma splits
mid-name and the waveform step dies. Every name here uses no comma.

It also leaves an ORPHANED PLACEHOLDER per failed file, in `status: processing`
with `sourceAccess.cloud: not-available` — five of them from two attempts. They
are invisible to a caller who only counts successes, and they sit in the pool
looking like assets.

## THE NUMBER I GOT WRONG, AND HOW FAR IT TRAVELLED

I reported camera-flash as MEASURED SILENT at -70.0 LUFS and wrote "do not place
it; it makes no sound" into the Design Style menu AND into the uploaded
filename. It peaks at **-0.8 dB**. It is one of the loudest sounds in the set.

FOUR sounds read -70.0 LUFS and all four are SHORTER THAN THE MEASUREMENT
WINDOW. Integrated LUFS integrates over ~400ms:

    sound                  duration   integrated LUFS   PEAK (volumedetect)
    camera-flash             235ms         -70.0             -0.8 dB
    popsfx                   217ms         -70.0             -5.4 dB
    swoosh-sound-effects     254ms         -70.0             -0.7 dB
    mouse-click-sound        151ms         -70.0             -4.5 dB
    boom                    1156ms          -9.2             -0.8 dB
    punchsfx                 594ms          -6.2              0.0 dB

A sound shorter than the window has NO VALID INTEGRATED READING. -70.0 there
means UNMEASURABLE, not silent — and I read it as a value and published it.

This is this repo's oldest rule failing in my own hands: a failed measurement
and a real result are indistinguishable once you are only reading the number.
The instrument could not measure the thing; it returned its floor; the floor
looked like a fact. Same shape as `alpha_layer_max` returning None and the guard
reading `x <= 260`, and I have been quoting that one all session.

WHAT IT COST: an instruction in front of their agent telling it not to place a
working sound, and a filename saying the same thing. Both corrected — the menu
now states every sound is audible with the peak range, and carries the note
above so the loudness column misleads nobody else. The mis-named asset is
deleted and re-uploaded as "camera-flash - short bright shutter click for a
snap or a cut".

THE CHECK IS THE NOTE ITSELF, in the styleGuide, where the next reader of that
column will be. A duration-aware guard in my lane would not have helped: the
reading is ChatCut's and it appears on their card, not in my code.

## STATE OF THE POOL on 6c0ca574

    13 sounds, descriptive names, key-first so prefix readers still match
    12 motion graphics, real default content, renamed by Builder 1 key-first
     1 video, zac_blueshirt
     3 bare-named sound duplicates DELIBERATELY KEPT — iphoneding.ogg,
       popsfx.ogg, punchsfx.ogg are the three placed on the timeline by the
       agent's own edit. Deleting them would delete those placements, which are
       the record of what it did. Zac's call; the pool is otherwise clean.
     0 orphaned placeholders (5 deleted, every impact 0)
