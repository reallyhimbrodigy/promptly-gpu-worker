#!/usr/bin/env python3
"""Every array becomes numbered scalar properties. No baked copy anywhere.

WHY, RULED BY ZAC 2026-09-23. A baked value is a LITERAL: `bake()` inlines the
content and DROPS the declared property, because ChatCut refuses a declared
property the code does not read as firmly as the reverse. So propertyOverrides
cannot reach it and every placement of that component draws OUR words on a
user's video, forever. Every RankedList said HOOK / PROOF / CLOSE.

THE SHAPE OF THE FIX. ChatCut has no array type — that has not changed, and it
is why the content was baked in the first place. What it does have is scalar
text properties, so an array of N becomes N numbered scalars, and the component
rebuilds the array from them at render time. `note1`, `note2`, `note3`.
`row1Title`, `row1Badge` .. `row5Title`, `row5Badge`. `pill1` .. `pill12`.

AN EMPTY FIELD DRAWS NOTHING AND THE LAYOUT CLOSES UP. Not a gap, not a
placeholder. That is the difference between a component that can take three of
its five rows and one that shows two empty rows — and it is the same ruling as
the six placeholder strings that became empty roots: a component's internal
state is never the viewer's content.

THE CAPS ARE THE ONES THE MENU LINES ALREADY STATE. RankedList's line says "up
to 5 numbered rows" and PillCluster's says "up to 12 labelled pills", so the
counts here are not new limits — they are the limits already published to their
agent, made real in the property list. StickyNotes says "exactly three".
"""

# key      the structured prop the component's __mapped reads
# n        how many slots (the cap the menu line already states)
# fields   (item_field, property_suffix, label) per slot; the FIRST field
#          decides emptiness — a slot whose first field is blank is dropped
#          entirely, which is what makes the layout close up.
# fixed    item fields that are NOT user copy and keep their baked value,
#          keyed by slot index (colours, rotations — geometry, not words)
# auto     item fields computed from the slot number (RankedList's rank)
FLATTEN = {
    "StickyNotes": {
        "key": "notes", "n": 3,
        "fields": [("text", "note%d", "Note %d", "text")],
        "fixed": {"color": ["#FFE86B", "#9BE7A6", "#FFB3C1"],
                  "rotation": [-4, 3, -2]},
    },
    "RankedList": {
        "key": "items", "n": 5,
        "fields": [("label", "row%dTitle", "Row %d title", "text"),
                   ("value", "row%dBadge", "Row %d badge", "text")],
        # THE RANK IS THE DRAWN POSITION, NOT THE SLOT. Assigned AFTER the
        # empty slots are dropped, so filling rows 1, 3 and 4 draws 1, 2, 3 —
        # "the layout closes up" has to mean the numbering closes up too, or
        # a user who leaves a row blank gets a list that skips a number.
        "auto": {"rank": "String(__i + 1)"},
    },
    "PillCluster": {"key": "tags", "n": 12,
                    "fields": [(None, "pill%d", "Pill %d", "text")]},
    "PillMarquee": {"key": "pills", "n": 12,
                    "fields": [(None, "pill%d", "Pill %d", "text")]},
    "PullQuote": {"key": "keywords", "n": 4,
                  "fields": [(None, "keyword%d", "Keyword %d", "text")]},
    "DropBanner": {"key": "points", "n": 4,
                   "fields": [(None, "point%d", "Point %d", "text")]},
    "DropCard": [{
        "key": "points", "n": 4,
        "fields": [("title", "point%dTitle", "Point %d title", "text"),
                   ("caption", "point%dCaption", "Point %d caption", "text")],
    }, {
        "key": "steps", "n": 4,
        "fields": [(None, "step%d", "Step %d", "text")],
    }],
    "BarRace": {
        "key": "bars", "n": 6,
        "fields": [("label", "bar%dLabel", "Bar %d label", "text"),
                   ("value", "bar%dValue", "Bar %d value", "number")],
    },
    "ChatThread": [{
        "key": "messages", "n": 6,
        "fields": [("text", "message%d", "Message %d", "text"),
                   ("sender", "message%dSender", "Message %d sender (me/them)", "text")],
    }, {
        # `header` is an OBJECT, not a list — one slot, three named fields.
        "key": "header", "n": 1, "object": True,
        "fields": [("name", "headerName", "Header name", "text"),
                   ("subtitle", "headerSubtitle", "Header subtitle", "text"),
                   ("initials", "headerInitials", "Header initials", "text")],
    }],
    "Timeline": {
        "key": "steps", "n": 4,
        "fields": [("label", "step%dTitle", "Step %d title", "text"),
                   ("description", "step%dBody", "Step %d body", "text")],
        "auto": {"index": "String(__i + 1).padStart(2, \"0\")"},
    },
    "TimelineRoadmap": {
        "key": "steps", "n": 4,
        "fields": [("label", "step%dTitle", "Step %d title", "text"),
                   ("sublabel", "step%dBody", "Step %d body", "text")],
        "auto": {"index": "String(__i + 1).padStart(2, \"0\")"},
    },
    "TweetBubble": {
        # RULED 2026-09-23. `stats` was the LAST baked object in the registry
        # and the one smoke_baked_copy could not see: its four values are
        # NUMBERS, so `words()` — which needs two letters to call something
        # copy — walked straight past 128 / 412 / 1200 / 98000. Every
        # TweetBubble ever placed drew the same fabricated engagement counts,
        # under a check reading a ceiling of zero. A count is content too.
        #
        # AN OBJECT, NOT A LIST: one slot, four named fields, and NO filter
        # here. The component destructures `stats.replies` and friends, so the
        # object must exist even when every field is blank — dropping it would
        # be a crash, not an empty row. The filter that closes the row up lives
        # IN THE COMPONENT, on the labels, which is the only place that can
        # tell "no replies" from "no stats row at all".
        #
        # TEXT, NOT NUMBER, ON ALL FOUR. A number property has no empty state:
        # unset arrives as 0 and draws "0", which is absence rendered as a
        # value in a field a viewer reads as a fact.
        "key": "stats", "n": 1, "object": True,
        "fields": [("replies", "statReplies", "Replies", "text"),
                   ("reposts", "statReposts", "Reposts", "text"),
                   ("likes", "statLikes", "Likes", "text"),
                   ("views", "statViews", "Views", "text")],
    },
    "RecordingFrame": {
        "key": "annotations", "n": 4,
        "fields": [("label", "note%dLabel", "Note %d label", "text"),
                   ("value", "note%dValue", "Note %d value", "text")],
        "fixed": {"corner": ["top-left", "top-right", "bottom-left", "bottom-right"]},
    },
}
