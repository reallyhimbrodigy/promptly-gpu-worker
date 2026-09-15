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
BANDS = {"upper_third": (0.00, 0.36), "centre": (0.32, 0.68),
         "center": (0.32, 0.68), "lower_third_safe": (0.58, 0.94),
         "lower_third": (0.58, 0.94), "full": (0.0, 1.0)}


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
