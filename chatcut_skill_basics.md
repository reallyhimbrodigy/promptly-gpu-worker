# ChatCut: how this surface works (the plugin guide, cut to what the edit needs)

This is the operating part of the ChatCut plugin guide. The MCP server asks
for the guide to be loaded before the first ChatCut call; it is here, so that
precondition is met. Everything about signing in, aligning with a user, editor
hand-off, connectors, billing and exporting is out: this run is headless, the
project is already open and populated, the harness exports.

## The data model

A **project** owns a shared asset library and one or more timelines. Each
timeline has its own canvas (fps, width, height), video tracks, audio tracks
and timeline items. Every id you use comes from a tool result — never infer or
shorten one.

**Assets** are source media in the library: video, audio, image, gif,
motion-graphic, svg. One asset can be referenced by many timeline items.
Content-level properties — the media, the filename, a Motion Graphic's code
and its editable property defaults — belong to the asset.

**Tracks** are lanes. Video tracks stack: a higher video track renders above a
lower one; an item on an upper track covers lower video for its duration, and
lower video shows through where the upper track is empty. If audio continues
while no video item is visible, the canvas is black. Audio tracks mix in
parallel and never cover each other. Items on the same track must not overlap.
Sequential clips go on the same track in increasing time order; layered
visuals — overlays, B-roll, Motion Graphics — go on higher video tracks above
what they cover.

**Items** are timeline instances of assets. An item owns placement and timing:
timeline start, duration, track, position, size, opacity, fades, source
offset, playback speed, and — for a Motion Graphic — its per-instance
`propertyOverrides`. Change the item to change when or where something
appears; change the asset to change reusable content. Placement and duration
are frame-native.

## Editing operations

Timeline edits leave gaps by default. Deleting an item does not move later
items unless ripple is used; shortening an item leaves a gap. Adding into an
occupied range on the same track is rejected unless the edit makes room.
Ripple affects only its own track; after a structural edit, captions, Motion
Graphics and other layered tracks may no longer line up with the speech and
must be checked. On an overlap conflict decide first whether the content is
sequential (same track, in time order) or layered (a higher track).

## Reading the timeline back

`read_project` returns only the project map and timeline directory — omitted
detail is unknown, not empty. `preview_timeline` returns tracks, paginated
items, gaps, markers, composed frames and bounded speech; request only the
`views` you need and narrow with `tracks`, `itemIds`, `fromFrame`, `toFrame`,
and follow `nextOffset` when an entry is not on the page. `inspect_item` is
the complete detail of exactly one placed item; `inspect_asset` is the
source-asset detail (including transcript ranges). Composed pixels — clips,
trims, captions, overlays, effects, final framing as they actually render —
come from `preview_timeline` with `views:["viewer"]` and bounded frames.

## Before reporting done

Verify the actual result: the intended items changed, no unintended gaps,
overlaps or misplaced layers remain, and dependent layers still line up with
the structure. Judge visual work from a composed frame, not from the item
list.
