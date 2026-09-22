#!/usr/bin/env python3
"""HONORED / DROPPED / NEGOTIATED / UNMEASURED, per ask, against the table.

NOT A TASTE READ. Zac judges every edit himself; this says only whether the
thing asked for is PRESENT, and it says UNMEASURED whenever it cannot tell.

── DEAD AIR IS SCORED AGAINST MEASURED SILENCE, NEVER ASSUMED ─────────────

The earlier version of this scored "cut the dead air" by assuming there was
dead air to cut. There are two ways that is wrong and both have happened here:

  * a run that removed nothing is marked DROPPED on a source with no silence in
    it, which convicts a correct edit;
  * a run that removed something is marked HONORED without anyone checking the
    silence is gone.

So the input is SPANS, measured on the EXPORT — silence remaining in the output
IS dead air that was not cut, which is the question, asked directly. With no
spans supplied the verdict is UNMEASURED and never DROPPED: absence of a
measurement is not evidence of absence.

THRESHOLD 400ms, and it is the EBU R128 block for a reason: below one block
there is no integrated reading at all, which is the same boundary that makes
four of our own sounds read -70.0. A "silence" shorter than that is a gap
between words, not dead air.
"""

JUDGE_VERSION = "2.0.0"
SILENCE_MS = 400.0

# Which table row answers which ask. An ask with no row is UNMEASURED, never
# assumed absent — that is how a family nobody read gets reported as dropped.
ASK_ROW = {
    "captions": "captions",
    "motion graphics": "graphics",
    "sound effects": "sounds",
    "transitions": "transitions",
    "zooms": None,            # zooms are item properties, not rows — see below
}


def score(asks, table, silence_spans=None, negotiated=None):
    """-> [{ask, verdict, evidence}]. `negotiated` comes from the classifier."""
    rows = table["rows"]
    neg = set(negotiated or [])
    out = []
    for ask in asks:
        a = str(ask).strip().lower()

        if a in neg:
            out.append({"ask": ask, "verdict": "NEGOTIATED",
                        "evidence": "refused or quoted at dispatch, before the box"})
            continue

        if "dead air" in a or "filler" in a:
            if silence_spans is None:
                out.append({"ask": ask, "verdict": "UNMEASURED",
                            "evidence": "no silence measurement supplied; absence "
                                        "of a measurement is not evidence of absence"})
                continue
            left = [s for s in silence_spans
                    if (s[2] if len(s) > 2 else (s[1] - s[0])) * 1000.0 >= SILENCE_MS]
            cuts = rows["cuts"]
            if left:
                out.append({"ask": ask, "verdict": "DROPPED",
                            "evidence": "%d span(s) >= %.0fms REMAIN in the export "
                                        "(longest %.3fs at %.3fs); the run removed "
                                        "%s ms of source"
                                        % (len(left), SILENCE_MS,
                                           max((s[2] if len(s) > 2 else s[1]-s[0]) for s in left),
                                           left[0][0], cuts.get("source_removed_ms"))})
            else:
                out.append({"ask": ask, "verdict": "HONORED",
                            "evidence": "no span >= %.0fms remains in the export"
                                        % SILENCE_MS})
            continue

        key = None
        for k, v in ASK_ROW.items():
            if k in a:
                key = v
                break
        if key is None:
            out.append({"ask": ask, "verdict": "UNMEASURED",
                        "evidence": "no row in the table answers this ask"})
            continue
        r = rows.get(key) or {}
        if r.get("state") in (None, "NOT_READ"):
            out.append({"ask": ask, "verdict": "UNMEASURED",
                        "evidence": "surface not read — an unread surface is not "
                                    "an empty one"})
        elif (r.get("count") or 0) > 0:
            out.append({"ask": ask, "verdict": "HONORED",
                        "evidence": "%d present" % r["count"]})
        else:
            out.append({"ask": ask, "verdict": "DROPPED",
                        "evidence": "0 present, surface read"})
    return out


def render(scored):
    w = max(len(s["ask"]) for s in scored) if scored else 10
    out = ["judge v%s" % JUDGE_VERSION]
    for s in scored:
        out.append("  %-*s  %-11s %s" % (w, s["ask"], s["verdict"], s["evidence"]))
    return "\n".join(out)
