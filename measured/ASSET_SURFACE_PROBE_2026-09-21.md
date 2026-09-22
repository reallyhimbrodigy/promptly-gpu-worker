# What their agent can actually read on an asset — MEASURED, not assumed

Zac's instruction was "don't guess the surface". Every line below is a real call
against 6c0ca574-a975-4641-930d-cdc4a4648a15.

## MOTION GRAPHIC — every field `inspect_asset` returns

    id · name · type · durationMs · folder · status · dimensions
    editableProperties[] {key, type, defaultValue}
    schema[]             {key, type, label, options[], defaultValue}
    file{} · defaults:null · code (only with includeCode:true)

**No description. No tags. No thumbnail.**

## AUDIO — every field `inspect_asset` returns

    id · name · type · durationMs · folder · status
    sourceAccess{cloud} · audio{loudness} · transcript{state, readyForEditing}
    file{mimeType, sizeKb} · metadataProvenance

**No description. No tags. No waveform. No preview of any kind.**
`transcript.state` on an SFX is `no_audio`, so even the transcript surface is
empty for a sound effect.

## CAN A DESCRIPTION BE WRITTEN AT ALL?

Tested by writing one and reading it back, because an accept is not a commit.

    AUDIO            edit_asset {description: ...}
                     -> REFUSED, and the refusal names the schema:
                        "Column description was not found in the Zero schema
                         for the table AudioAsset"

    MOTION GRAPHIC   edit_asset {description: ...}
                     -> ACCEPTED: {"id": "...", "type": "motion-graphic"}
                     -> inspect_asset afterwards: NO description field.
                        Silently dropped.

The motion-graphic case is the dangerous one. It returns success, writes
nothing, and a convention built on it would read as shipped while being absent
from every surface the agent sees. The audio refusal is the honest failure of
the two.

## SO THE ONLY FREE-TEXT SURFACE ON AN ASSET IS ITS **NAME**

Plus `folder`, which is a one-level grouping and is currently "Master" for all
26. Both are returned by `browse_assets` and `inspect_asset`, so both are
readable by their agent.

That is the whole writable vocabulary. An inventory convention of
NAME · DESCRIPTION · PREVIEW cannot be implemented as three fields, because two
of the three do not exist on the record.

## WHAT SURVIVES OF THE THREE

  NAME         real, writable, read by their agent. Carries everything.
  FOLDER       real, writable, one level. Can carry the CATEGORY.
  DESCRIPTION  NOT AVAILABLE on either asset type. Must fold into the name, or
               live on a project-level surface and be found there instead.
  PREVIEW      for a motion graphic, the only in-pool preview is the asset's
               own `dimensions` and its property `schema` — there is no
               thumbnail field. A rendered clip must be carried as a SEPARATE
               VIDEO ASSET whose name ties it to the component.
  AUDIO PREVIEW  impossible in-pool. Their agent cannot hear, waveform, or
               transcribe an SFX. For sounds the NAME is the preview, and that
               is a measured limit rather than a choice.

## STILL OPEN — the project-level surface

Whether the project `description` (writable, confirmed — I set one on this
project and it persisted) or the Design Style notes are read by THEIR agent at
ruling time is NOT yet measured. It is writable on our side; being read on
theirs is a different claim and needs its own evidence before an inventory is
staked on it.

---

# ROUND 2 — the writable surfaces, all probed by writing and reading back

Every row is a real call. The Zero schema errors name the actual columns, which
made this cheap.

    SURFACE                          WRITE            READ BACK
    asset.description (audio)        REFUSED          — "Column description was not
                                                        found in the Zero schema for
                                                        the table AudioAsset"
    asset.description (motion-gfx)   ACCEPTED         ABSENT. Silently dropped.
    asset.filename   (motion-gfx)    REFUSED          — no such column
    asset.name       (motion-gfx)    ACCEPTED         PERSISTS, and browse_assets
                                                      MATCHES ON IT and returns a
                                                      snippet — so it is indexed and
                                                      searchable by their agent.
    asset.name       (audio)         REFUSED          — "Column name was not found in
                                                        the Zero schema for the table
                                                        AudioAsset"
    project.description              ACCEPTED         PERSISTS.
    designSpec.styleGuide            ACCEPTED         PERSISTS VERBATIM. 1,847 chars
                                                      written, 1,847 read back, no
                                                      truncation. It is ONE STRING,
                                                      not an array — the create was
                                                      refused with "expected string,
                                                      received array", which is how
                                                      the type was learned.

## The consequences, in order of how much they constrain the inventory

**A SOUND CANNOT BE RENAMED.** AudioAsset has neither `name` nor `description`.
The name comes from the uploaded FILENAME at import and is fixed afterwards. So
"for sounds the name is the whole preview" is only reachable by RE-UPLOADING
each sound under a descriptive filename and deleting the original. Thirteen
re-uploads, not thirteen renames.

**A MOTION GRAPHIC CAN CARRY ITS DESCRIPTION IN ITS NAME**, and that name is
searchable. Confirmed live: `PlainText — bold line on the picture, for one claim`
was written, read back, and matched by a `browse_assets` query on "PlainText"
with the whole line returned as the snippet.

**THE MENU FITS IN THE DESIGN STYLE.** `styleGuide` took all twelve components,
all thirteen sounds and their one-line descriptions in a single string and gave
every character back. No image was needed to carry text.

## Still unmeasured, and deliberately not staked on

Whether THEIR agent reads `designSpec.styleGuide` or `project.description` at
ruling time. Both are writable and both persist on our side; being read on
theirs is a different claim. Canary planted 2026-09-21 on 6c0ca574:

    designSpec.styleGuide  -> CANARY-KESTREL ... write the word KESTREL
    project.description    -> CANARY-MARLIN  ... write the word MARLIN

The next brief's chat text answers it. Whichever word comes back names the
surface their agent actually reads; the other one gets dropped rather than
maintained. If NEITHER comes back, both surfaces are decorative and the
inventory has to live somewhere else entirely — which is the outcome worth
knowing most, and the one an unmeasured inventory would have hidden.
