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
    "PillMarquee": [{"key": "pills", "n": 12,
                     "fields": [(None, "pill%d", "Pill %d", "text")]}, {
        # The palette is a bare ARRAY of colours the body indexes modulo its
        # length. Every slot keeps a default, so the array can never come back
        # empty — `palette[i % 0]` is NaN, and the parameter default that used
        # to catch that is unreachable once the mapping always supplies a value.
        "key": "palette", "n": 3,
        "fields": [(None, "paletteColor%d", "Palette colour %d", "color")],
        "defaults": {"paletteColor1": "#C8551F", "paletteColor2": "#4F9DF7",
                     "paletteColor3": "#36E27A"},
    }],
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
    # ── THE LAST FOUR, 2026-09-23 ────────────────────────────────────────
    # "flattened: n" was ambiguous and hid these: it meant BOTH "has no lists
    # to flatten" and "has lists and has not been done". Four components were
    # in the second group, and two of them were WORSE than baked copy — their
    # payload had been emptied to remove our words, which took the CAPABILITY
    # with it. EndCard.lines was `[]` and Notification.notifications was `[]`,
    # so a placement could not give an end card its sign-off or a notification
    # its text AT ALL. Removing our copy and removing the slot look identical
    # in a copy survey; only the split tells them apart.
    "AnnotationArrow": [{
        # GEOMETRY, NOT COPY — and baked geometry is still baked. The arrow
        # exists to point at a detail on screen, and the detail's position was
        # a literal, so every arrow ever placed pointed at the same spot.
        "key": "start", "n": 1, "object": True,
        "fields": [("x", "startX", "Start X (0-1)", "number"),
                   ("y", "startY", "Start Y (0-1)", "number")],
        "defaults": {"startX": 0.25, "startY": 0.35},
    }, {
        "key": "end", "n": 1, "object": True,
        "fields": [("x", "endX", "End X (0-1)", "number"),
                   ("y", "endY", "End Y (0-1)", "number")],
        "defaults": {"endX": 0.72, "endY": 0.62},
    }],
    "EndCard": [{
        "key": "lines", "n": 4,
        "fields": [("text", "line%dText", "Line %d", "text"),
                   ("icon", "line%dIcon", "Line %d icon", "text")],
    }, {
        # The palette is CHROME. It keeps its values as defaults, because an
        # empty colour is not a blank colour — it is an unpainted element.
        "key": "palette", "n": 1, "object": True,
        "fields": [("bg", "paletteBg", "Background", "color"),
                   ("fg", "paletteFg", "Text colour", "color"),
                   ("accent", "paletteAccent", "Accent colour", "color")],
        "defaults": {"paletteBg": "#14141A", "paletteFg": "#FEFCFD",
                     "paletteAccent": "#C8551F"},
    }],
    "Notification": {
        # `title` IS FIRST BECAUSE THE FIRST FIELD DECIDES EMPTINESS. A
        # notification with no title is not a notification, so the whole slot
        # drops and the stack closes up. `timestamp` is deliberately NOT a
        # field: the body reads `item.timestamp ?? "now"`, and adding a text
        # property would make it "" — present and empty — which defeats the
        # ?? and draws a blank where "now" belongs.
        "key": "notifications", "n": 3,
        "fields": [("title", "notif%dTitle", "Notification %d title", "text"),
                   ("body", "notif%dBody", "Notification %d body", "text"),
                   ("appName", "notif%dApp", "Notification %d app name", "text"),
                   ("app", "notif%dIcon", "Notification %d icon key", "text")],
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
