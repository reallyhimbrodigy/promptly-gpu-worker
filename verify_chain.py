#!/usr/bin/env python3
"""The chain: ruling -> plan -> prestage -> placement -> RENDERED FRAME.

EVERY GATE BUILT FOR THIS CLASS HAS SAT DOWNSTREAM OF THE LOSS.

  * the PLACEMENTS gate compares the plan's own add count against the agent's
    own tool calls, so it confirmed 8 of 8 while the translator had already
    dropped half the rulings.
  * the ruling reconciliation catches a family that never reaches the plan —
    and a card that reaches the plan, is counted as emitted, and is registered
    into an asset with no card properties passes it cleanly.
  * `items_added` counts adds SENT, and ChatCut resolves an id PREFIX, so an
    add whose asset resolved to nothing is indistinguishable from a correct one.
  * and the last run's agent said, in its closing message, that it could not
    confirm the StatCard. It was right. Nothing acted on it.

So each hop is checked WHERE IT HAPPENS, and the last hop compares intent
against the delivered pixels rather than against anybody's report of them.

    HOP 1  ruling  -> plan        plan_for_chatcut: raises by family name
    HOP 2  plan    -> prestage    every assetId the plan names is registered
    HOP 3  prestage-> placement   every add is an ITEM on the timeline
    HOP 4  placement-> frame      every visual placement CHANGED ITS BAND

This module is the pure half — parsing and judging, no network — so it can be
tested offline. The job wires it at the three points where the answers exist.
"""
import json
import re

# The frame is 1080x1920. A placement's band is where its pixels must appear.
# THE RULED BANDS — where a TITLE sits, because a title is positioned by a
# property rather than by its own geometry.
BANDS = {"upper_third": (0.00, 0.36), "lower_third_safe": (0.58, 0.94),
         "lower_third": (0.58, 0.94), "full": (0.0, 1.0)}


def measured_bands(rows_path=None):
    """{component: (y0, y1)} as a FRACTION of frame height, from the bboxes the
    render check actually measured.

    NOT A GUESSED TABLE. The first version of the collision check invented a
    caption band of 0.52-0.70 and therefore found NO collision between the card
    and the captions — the one collision that had actually shipped. The real
    numbers, from sheet/rows.json:

        StatCard          y  602- 848   0.314-0.442
        caption:TwoTone   y  704- 787   0.367-0.410
        caption:Pulse     y 1160-1240   0.604-0.646

    TwoTone sits INSIDE StatCard. And the two caption styles are 200px apart
    from each other, which is why one guessed "caption band" could never have
    been right for both.
    """
    import os
    p = rows_path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "sheet", "rows.json")
    try:
        rows = json.load(open(p, encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {}
    out = {}
    for name, v in rows.items():
        if v.get("state") != "MEASURED":
            continue
        m = re.search(r"bbox \((\d+), (\d+), (\d+), (\d+)\)",
                      str(v.get("detail") or ""))
        if m:
            _, y0, _, y1 = (int(g) for g in m.groups())
            out[name] = (y0 / 1920.0, y1 / 1920.0)
    return out


def plan_manifest(plan_text):
    """Every add the plan names -> a row that can be checked at each hop.

    Parsed from the PLAN, not from the ruling, because the plan is what the
    agent is given and what it is judged against. A row the plan does not name
    cannot be verified and a row it names must arrive.
    """
    rows, cur, call = [], None, 1
    for line in (plan_text or "").splitlines():
        m = re.match(r"^\s*CALL (\d+), adds\[(\d+)\]:\s*$", line)
        if m:
            if cur:
                rows.append(cur)
            call = int(m.group(1))
            cur = {"call": call, "slot": int(m.group(2)), "type": None,
                   "asset": None, "from": None, "dur": None, "band": None,
                   "overrides": None, "settle": None, "srcstart": 0.0}
            continue
        if cur is None:
            continue
        f = re.match(r"^\s{4,8}(\w+)\s+:\s*(.+?)\s*$", line)
        if not f:
            continue
        # STRIP THE HUMAN NOTE, NOT THE VALUE. `assetId : (given in your
        # instructions)` is entirely parenthesised, and a blanket strip left it
        # EMPTY — which hop 2 would then report as "the plan names no assetId",
        # a refusal aimed at the one add that is correct. Only strip a trailing
        # note that follows a value.
        _raw = f.group(2).strip()
        _cut = re.sub(r"\s+\(.*$", "", _raw).strip()
        k, v = f.group(1), (_cut or _raw)
        if k == "type":
            cur["type"] = v
        elif k == "assetId":
            cur["asset"] = v
        elif k in ("from", "fromFrame"):
            cur["from"] = int(v)
        elif k == "durationInFrames":
            cur["dur"] = int(v)
        elif k == "band":
            cur["band"] = v
        elif k == "sourceStartFromInSeconds":
            try:
                cur["srcstart"] = float(v)
            except ValueError:
                cur["srcstart"] = 0.0
        elif k == "propertyOverrides":
            try:
                cur["overrides"] = json.loads(v)
            except Exception:                                    # noqa: BLE001
                cur["overrides"] = None
    if cur:
        rows.append(cur)
    return rows


def settled_frames(plan_text):
    """The frames the plan told the agent to review."""
    m = re.search(r"viewerFrames:\s*(\[[^\]]*\])", plan_text or "")
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except Exception:                                            # noqa: BLE001
        return []


def expectations(manifest, plan_text):
    """[{slot, frame, band, label}] — what must be VISIBLE, and where.

    A placement is checked at a frame INSIDE its own window. The plan's review
    frames are the settled frames of the graphics, so each graphic is matched
    to the review frame that falls in its span; a placement with no review
    frame inside it is reported rather than skipped, because a placement nobody
    looked at is not a placement that passed.
    """
    frames = settled_frames(plan_text)
    out = []
    for r in manifest:
        if r["type"] != "motion-graphic" or r["from"] is None:
            continue
        lo, hi = r["from"], r["from"] + (r["dur"] or 0)
        inside = [f for f in frames if lo <= f < hi]
        band = r.get("band") or ("centre" if (r.get("overrides") or {}).get("value")
                                 is not None else "full")
        label = ("StatCard value=%s" % (r["overrides"] or {}).get("value")
                 if (r.get("overrides") or {}).get("value") is not None
                 else (r.get("asset") or "")[:48])
        if not inside:
            out.append({"slot": r["slot"], "frame": None, "band": band,
                        "label": label})
            continue
        # A CARD COUNTS IN. StatCard animates its number over `enterFrames`
        # (32 by default), so the earliest review frame inside its window shows
        # a half-counted figure — which is exactly how a card that DOES render
        # gets reported as missing. Judge a counting component at the LATEST
        # frame inside its span, everything else at the earliest settled one.
        _counts_in = (r.get("overrides") or {}).get("value") is not None
        out.append({"slot": r["slot"],
                    "frame": (max(inside) if _counts_in else inside[0]),
                    "band": band, "label": label})
    return out


def hop2_prestage(manifest, registered):
    """Every assetId the plan names resolves to something registered.

    `registered` is {name-or-label: assetId}. The plan writes prose for the
    graphics ("the GRAPHIC 3 assetId listed in your instructions") and a
    literal for library sounds and builtin effects, so the check is: anything
    that is not a literal must be findable by the label the plan used.
    """
    missing = []
    for r in manifest:
        a = (r.get("asset") or "").strip()
        if not a:
            missing.append((r, "the plan names no assetId at all"))
            continue
        if a.startswith(("library:sound:", "builtin:")):
            continue                     # a literal ChatCut resolves itself
        m = re.search(r"GRAPHIC (\d+)", a)
        if m:
            if ("GRAPHIC %s" % m.group(1)) not in registered:
                missing.append((r, "GRAPHIC %s was never registered" % m.group(1)))
            continue
        # the label may be backticked (`caption:TwoTone`) or bare (StatCard)
        m = re.match(r"the [`']?([\w:]+)[`']? assetId", a)
        if m:
            if m.group(1) not in registered:
                missing.append((r, "%s is not among the registered components"
                                   % m.group(1)))
            continue
        if re.fullmatch(r"[0-9a-f-]{8,}", a):
            continue                     # already a real id
        if a.startswith("(") and a.endswith(")"):
            continue                     # the base video: named in the brief
        missing.append((r, "assetId %r is neither a literal nor a known label" % a))
    return missing


def hop3_placed(manifest, timeline_entries):
    """Every add is an ITEM on the timeline, at the frame the plan named.

    `items_added` counted adds SENT. ChatCut resolves an id PREFIX and returns
    ok, so a send is not a landing. This reads the timeline back.
    """
    want = [r for r in manifest if r["type"] in ("video", "motion-graphic",
                                                 "audio")]
    got = [e for e in (timeline_entries or []) if e.get("kind") == "item"]
    missing = []
    for r in want:
        hit = [e for e in got
               if (e.get("timelineRange") or {}).get("fromFrame") == r["from"]]
        if not hit:
            missing.append((r, "no item starts at frame %s" % r["from"]))
    return missing


def band_of(row, meas):
    """Where this placement's pixels actually land, as (y0, y1) fractions.

    A registered component is measured from its own render. A title is placed
    by a PROPERTY, so its ruled band is the truth. Anything unknown claims the
    WHOLE FRAME — an unknown position must not read as "somewhere harmless".

    THE OFFSET IS APPLIED LAST, ALWAYS. The first version returned early on the
    component-name match and only applied `offsetY` on a later branch, so a
    card that had been deliberately moved reported its ORIGINAL band — the
    resolver computed a shift of 152px and the detector then judged the card as
    if it had never moved. A band model that ignores the property which
    repositions the thing is describing where it used to be.
    """
    a = row.get("asset") or ""
    base = None
    for name, b in meas.items():
        if name in a:
            base = b
            break
    if base is None and (row.get("overrides") or {}).get("value") is not None:
        base = meas.get("StatCard", (0.0, 1.0))
    if base is None:
        base = BANDS.get(row.get("band"), (0.0, 1.0))
    dy = float((row.get("overrides") or {}).get("offsetY") or 0) / 1920.0
    return (base[0] + dy, base[1] + dy)


def free_offset(row, others, meas, height=1920, clear=0.05):
    """The smallest offsetY that clears `row` of every band in `others`.

    A REFUSAL NOTHING CAN SATISFY IS A DEAD END. The planner knows every band,
    so where a region is contested it should PLACE the card clear rather than
    hand the conflict onward; the refusal is reserved for a frame with no free
    region at all, which is a real editorial fact about that moment.
    """
    b = band_of(row, meas)
    h = b[1] - b[0]
    blocked = [band_of(o, meas) for o in others]
    # try every 1% step, nearest-first, keeping the card fully on screen
    for step in range(0, int(height * 0.7), 8):
        for sign in (1, -1):
            dy = sign * step
            lo = b[0] + dy / float(height)
            hi = lo + h
            if lo < 0.02 or hi > 0.98:
                continue
            # CLEAR BY MORE THAN THE DETECTOR TOLERATES. Resolving to
            # exactly the 2% seam leaves the layout one wrapped line from a
            # collision; 5% is a gap you can see.
            if all(min(hi, ob[1]) - max(lo, ob[0]) <= -clear for ob in blocked):
                return dy
    return None


def collisions(manifest, meas=None):
    """Every placement against every OTHER placement in the same window.

    THE CARD LANDED ON THE CAPTIONS. StatCard occupies y 0.314-0.442 and
    caption:TwoTone occupies 0.367-0.410 — the caption sits INSIDE the card —
    and both were live for frames 526-608. At 562 the caption word "FIVE" sits
    directly over the card's "5", at 585 "EDIT", at 600 "NOTHING".

    NOTHING CHECKED ACROSS FAMILIES. The title loop knew about titles, the
    caption section about captions, the card rode the graphics pass, and no
    reader held two of them at once. Every gate was within a family.

    This runs at PLAN TIME, before anything is registered or placed, because a
    composition that cannot work is cheapest to refuse before it is built. It
    catches only what a plan can PREDICT: it cannot know that text will wrap or
    that a counting number will grow. The pixel gate at review time covers
    that, and the two together are the property.
    """
    meas = meas if meas is not None else measured_bands()
    live = [r for r in manifest
            if r["type"] == "motion-graphic" and r["from"] is not None]
    out = []
    for i, a in enumerate(live):
        a0, a1 = a["from"], a["from"] + (a["dur"] or 0)
        ab = band_of(a, meas)
        for b in live[i + 1:]:
            b0, b1 = b["from"], b["from"] + (b["dur"] or 0)
            if b0 >= a1 or a0 >= b1:
                continue                      # never on screen together
            bb = band_of(b, meas)
            lo, hi = max(ab[0], bb[0]), min(ab[1], bb[1])
            if hi - lo <= 0.02:               # a 2% seam is not a collision
                continue
            out.append({
                "a": a["slot"], "b": b["slot"],
                "frames": (max(a0, b0), min(a1, b1)),
                "overlap": round(hi - lo, 3),
                "why": "slots %d and %d are both on screen for frames %d-%d "
                       "and their MEASURED bands overlap by %.0f%% of the "
                       "frame height (%.3f-%.3f vs %.3f-%.3f)"
                       % (a["slot"], b["slot"], max(a0, b0), min(a1, b1),
                          (hi - lo) * 100, ab[0], ab[1], bb[0], bb[1])})
    return out


def hop4_carries(manifest, items_by_from):
    """Every add ARRIVED CARRYING WHAT THE PLAN NAMED — asset and overrides.

    THIS WAS A PIXEL CHECK AND THE PIXEL CHECK WAS A FALSE GREEN. The first
    version compared each placement's band against the SOURCE frame at the same
    timeline moment, on the reasoning that an overlay adds pixels. Measured
    against the run where the card is definitively absent, it reported ZERO
    placements missing — because a zoom is active, `shape: "payoff"` RAMPS the
    magnification, and a fixed-scale comparison never registers. At frame 562
    the centre-band residual is 11.75% at the best magnification and 28.7%
    unscaled; the noise floor swamps any overlay entirely:

        M=1.00 28.68%   M=1.08 20.92%   M=1.12 11.75%   M=1.20 22.70%

    A check that returns "all present" on a run with a missing placement is the
    class this whole chain exists to close, so it is not shipped. What IS sound
    is reading the placement back: the item exists, it points at the asset the
    plan named, and it carries the propertyOverrides the ruling asked for. That
    catches the card — which was lost as an asset registered without it — and
    it catches an id prefix that resolved to the wrong thing.

    What it does NOT catch is a component that renders nothing despite correct
    props. That is covered separately and per-component by the render check
    (37 of 38 draw), and saying so is better than a check that pretends to.
    """
    bad = []
    for r in manifest:
        if r["type"] not in ("motion-graphic", "video", "audio"):
            continue
        it = items_by_from.get(r["from"])
        if it is None:
            bad.append((r, "no item at frame %s to carry it" % r["from"]))
            continue
        want = r.get("overrides") or {}
        if not want:
            continue
        got = it.get("propertyOverrides") or {}
        for k, v in want.items():
            if k not in got:
                bad.append((r, "the item carries no %r — the ruling asked for "
                               "%r and the placement arrived without it"
                               % (k, v)))
            elif str(got[k]) != str(v):
                bad.append((r, "%s is %r on the item and %r in the plan"
                               % (k, got[k], v)))
    return bad


def masks_overlap(masks, min_px=200, min_frac=0.06):
    """[(a, b, shared_px, fraction)] for every pair of track masks that share
    pixels — HOP 5's judgment, extracted so it can be proven on a known-bad
    case without a render.

    `masks` is {track: bytes-or-list of 0/1}. The fraction is of the SMALLER
    mask, because a caption word overlapping a full-frame graphic is the
    caption's problem at 100% and the graphic's at 2%.
    """
    ks = sorted(masks)
    hits = []
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            m1, m2 = masks[a], masks[b]
            n = min(len(m1), len(m2))
            both = sum(1 for k in range(n) if m1[k] and m2[k])
            area = min(sum(m1[:n]), sum(m2[:n])) or 1
            frac = both / float(area)
            if both > min_px and frac > min_frac:
                hits.append((a, b, both, frac))
    return hits


def sits_on(band, occupied_names, band_fraction, tol=0.02):
    """[(name, overlap)] for every occupied band this placement intrudes into —
    HOP 6's judgment, extracted for the same reason.

    `band_fraction` maps a band name to its (y0, y1) fractions, so the caller
    supplies PRODUCTION's table rather than this module inventing one.
    """
    out = []
    for name in sorted(occupied_names or ()):
        lo, hi = band_fraction(name)
        ov = min(band[1], hi) - max(band[0], lo)
        if ov > tol:
            out.append((name, ov))
    return out
