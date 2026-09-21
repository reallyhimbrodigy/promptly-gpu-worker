"""THE DENSITY HISTOGRAM — a run's per-25s rates beside the reference's.

THE RATES GRADE; THEY NEVER INSTRUCT. This is a reading instrument. It returns
numbers and a ratio. It has no threshold, no verdict and no gate, and nothing
here may reach an agent at ruling time: a run that placed two zooms because two
moments deserved them is correct, and a rubric calling it short is the rubric's
problem. Zac's standing rule, and the reason one rate survived a careful removal
once by being prose instead of a field.

THREE STATES ON BOTH SIDES. A family with no placements is only 0.0 if the
timeline was READ; a timeline that could not be read is ABSENT, and an error is
FAILED. A clean zero is guilty until proven innocent, and "the agent placed no
cards" and "nobody read the cards" are the same number otherwise.

THE TWO SIDES HAVE DIFFERENT PROVENANCE AND IT IS PRINTED EVERY TIME.
The REFERENCE side is a MODEL'S READING of ten videos — beat spans and treatment
names a model assigned — not mechanical counts. The RUN side is COUNTED from the
items on the timeline. Comparing them is legitimate and the seam is real, so the
seam is named in the output rather than in a footnote nobody reads.

ONE DENOMINATOR CAVEAT, BECAUSE IT DECIDES EVERY NUMBER HERE. The reference
side divides by the SUM OF BEAT DURATIONS (861.6s across 294 beats, 10 videos),
not by the videos' wall time. Those are the same number only if the beats tile
their videos with no gaps. If they sample moments instead, the denominator is
SMALLER than the footage and every reference rate above is correspondingly
HIGH. That is unresolved here and is printed with the rate rather than buried:
the run side divides by real timeline seconds, so a ratio between them inherits
the question. Settle it before any number from this file is quoted as a target —
which it must not be anyway, per the paragraph above.

AND THE PER-25s NORMALISATION IS KNOWN TO FIT BADLY ON REAL DURATIONS
(measured 2026-09-07): a per-25s rate reproduced real traffic within 20% for
zoom on 0.5% of jobs and for sfx on 7.5%. So a ratio here is an observation
about THIS pair of durations, not a law, and the durations are printed beside it.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
FAMILIES = ("cut", "card", "text", "sfx", "zoom")

# THE MAPPING IS KEYWORD-BASED AND ITS MISSES ARE REPORTED. The reference
# vocabulary is 90+ free-text treatment names a model wrote; folding an
# unrecognised one into a family would inflate that family by exactly the amount
# nobody can see. Anything unmatched is counted as UNMAPPED and printed.
_MAP = (
    ("sfx",  r"\bsfx\b|whoosh|swoosh|click|pop accent|sound effect"),
    ("zoom", r"punch-?in|push-?in|zoom|reframe|whip-?pan|dolly"),
    ("card", r"card|stat|counter|numeral|quote|title|end ?card|nameplate|name/identity|"
             r"callout|highlight box|badge|banner|logo|icon|graphic|chart|list|"
             r"progress|split-?screen|mockup|polaroid|overlay graphic"),
    ("text", r"caption|text overlay|kinetic text|typed|search-?bar|word-by-word|"
             r"subtitle|keyword|font"),
    ("cut",  r"\bcut\b|cutaway|b-?roll|transition|wipe|flash|montage|"
             r"hard cut|l-cut|angle/shot change|pov|shot"),
)


def _fam_of_treatment(name):
    n = str(name).lower()
    for fam, pat in _MAP:
        if re.search(pat, n):
            return fam
    return None


def reference_rates(path="reference_index.json"):
    """-> {state, per_25s, counts, seconds, videos, unmapped, coverage, provenance}"""
    p = path if os.path.isabs(path) else os.path.join(HERE, path)
    if not os.path.isfile(p):
        return {"state": "ABSENT", "why": "no reference index at %s" % path}
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        return {"state": "FAILED", "why": "unreadable reference index: %s" % e}
    beats = d.get("beats") or []
    if not beats:
        return {"state": "ABSENT", "why": "the reference index carries no beats"}
    counts = {f: 0 for f in FAMILIES}
    unmapped, seconds, seen = {}, 0.0, 0
    for b in beats:
        seconds += float(b.get("dur") or 0)
        seen += 1
        for t in (b.get("treat") or []):
            fam = _fam_of_treatment(t)
            if fam is None:
                unmapped[t] = unmapped.get(t, 0) + 1
            else:
                counts[fam] += 1
    if seconds <= 0:
        return {"state": "FAILED", "why": "beat durations sum to %r — cannot normalise" % seconds}
    mapped = sum(counts.values())
    total = mapped + sum(unmapped.values())
    return {
        "state": "MEASURED",
        "per_25s": {f: round(counts[f] * 25.0 / seconds, 3) for f in FAMILIES},
        "counts": counts, "seconds": round(seconds, 1), "beats": seen,
        "videos": d.get("distinct_videos"),
        "unmapped": sorted(unmapped.items(), key=lambda kv: -kv[1]),
        "coverage": round(100.0 * mapped / total, 1) if total else 0.0,
        "provenance": "MODEL-ANNOTATED — beat spans and treatment names are a model's reading "
                      "of %s videos, not mechanical counts" % d.get("distinct_videos"),
    }


def _items_from_record(rec):
    """-> (items, why) — the placed items, or None with the reason there are none."""
    ex = rec.get("export") or {}
    if str(ex.get("state") or "").upper() != "OK":
        return None, "export state is %s (%s)" % (ex.get("state"), ex.get("why"))
    tl = rec.get("timeline_sample") or {}
    items = tl.get("items")
    if not isinstance(items, list):
        return None, "the record carries no readable timeline items"
    return items, None


def _duration_s(items):
    """-> (seconds, None) or (None, (STATE, why)).

    THE RECORD DOES NOT CARRY THE TIMELINE FPS, and the reader's first version
    read a `timeline_sample.end_s` that does not exist — so it would have
    returned ABSENT on every run, including a perfectly good export, and the
    failure would have looked exactly like "the run placed nothing". Caught by
    reading a real record before trusting the reader, not after.

    FPS IS DERIVABLE AND IS NEVER DEFAULTED. An item carries `timelineRange` in
    FRAMES and `sourceRange` in MICROSECONDS, so frames / seconds is the rate:
    2032 / 72.571429 = 28.0 on the kolkata fixture, which is its real rate and
    not the 30 that a default would have supplied. Defaulting it is precisely
    the canvas-never-followed-the-source defect, and a rate is the one number
    this instrument divides by.

    ITEMS THAT DISAGREE ARE FAILED, NOT AVERAGED. Two rates in one timeline mean
    a speed change or a mixed source, and either way the divisor is not a single
    number — picking one would publish a duration nothing has.
    """
    rates, last = [], 0
    for i in items:
        tr, sr = i.get("timelineRange") or {}, i.get("sourceRange") or {}
        f0, f1 = tr.get("fromFrame"), tr.get("toFrame")
        s0, s1 = sr.get("start"), sr.get("end")
        if f1 is not None:
            last = max(last, int(f1))
        if None in (f0, f1, s0, s1):
            continue
        secs = (int(s1) - int(s0)) / 1e6
        frames = int(f1) - int(f0)
        if secs > 0 and frames > 0:
            rates.append(frames / secs)
    if not rates:
        return None, ("ABSENT", "no item carries both a frame range and a source range, "
                                "so the timeline fps cannot be derived and nothing may be "
                                "divided by a guess")
    lo, hi = min(rates), max(rates)
    if hi - lo > 0.5:
        return None, ("FAILED", "items imply %d different frame rates (%.2f..%.2f) — a speed "
                                "change or a mixed source, and there is no single divisor"
                                % (len(set(round(r, 2) for r in rates)), lo, hi))
    fps = sum(rates) / len(rates)
    if last <= 0:
        return None, ("ABSENT", "no item carries a timeline end frame")
    return last / fps, None


def run_rates(record_path):
    """-> {state, per_25s, counts, seconds, why} for one run record."""
    if not os.path.isfile(record_path):
        return {"state": "ABSENT", "why": "no record at %s" % record_path}
    try:
        rec = json.load(open(record_path, encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        return {"state": "FAILED", "why": "unreadable record: %s" % e}
    items, why = _items_from_record(rec)
    if items is None:
        # NOT ZEROS. A run that was withheld, or whose timeline was not read,
        # has NO rate — it does not have a rate of nothing.
        return {"state": "ABSENT", "why": why, "record": os.path.basename(record_path)}
    end, why = _duration_s(items)
    if end is None:
        return {"state": why[0], "why": why[1], "record": os.path.basename(record_path)}
    counts = {f: 0 for f in FAMILIES}
    other = {}
    for i in items:
        t = str(i.get("itemType") or i.get("type") or "")
        fam = {"caption": "text", "audio": "sfx", "video": "cut",
               "effect": "zoom", "motion-graphic": "card"}.get(t)
        if fam is None:
            other[t] = other.get(t, 0) + 1
        else:
            counts[fam] += 1
    return {"state": "MEASURED",
            "per_25s": {f: round(counts[f] * 25.0 / float(end), 3) for f in FAMILIES},
            "counts": counts, "seconds": round(float(end), 1),
            "unmapped_types": sorted(other.items(), key=lambda kv: -kv[1]),
            "record": os.path.basename(record_path),
            "provenance": "COUNTED from the items on the exported timeline"}


def compare(record_path, reference="reference_index.json"):
    ref, run = reference_rates(reference), run_rates(record_path)
    out = {"reference": ref, "run": run, "rows": [],
           "grades_only": "This instrument GRADES. It has no threshold and no verdict, and none "
                          "of it may reach an agent at ruling time."}
    if ref.get("state") != "MEASURED" or run.get("state") != "MEASURED":
        out["state"] = "ABSENT"
        out["why"] = "reference %s, run %s — no comparison is possible" % (
            ref.get("state"), run.get("state"))
        return out
    out["state"] = "MEASURED"
    for f in FAMILIES:
        r, u = ref["per_25s"][f], run["per_25s"][f]
        out["rows"].append({"family": f, "reference_per_25s": r, "run_per_25s": u,
                            "ratio": round(u / r, 2) if r else None})
    return out


if __name__ == "__main__":
    import sys
    ref = reference_rates()
    print("REFERENCE  state=%s" % ref["state"])
    if ref["state"] == "MEASURED":
        print("  %s" % ref["provenance"])
        print("  %d beat(s), %.1fs of beat span, %s video(s); vocabulary coverage %.1f%%"
              % (ref["beats"], ref["seconds"], ref["videos"], ref["coverage"]))
        for f in FAMILIES:
            print("    %-5s %6.2f /25s   (%d)" % (f, ref["per_25s"][f], ref["counts"][f]))
        if ref["unmapped"]:
            print("  UNMAPPED (counted, never folded into a family): %d term(s), top: %s"
                  % (len(ref["unmapped"]), ", ".join("%s x%d" % (n, c)
                                                     for n, c in ref["unmapped"][:4])))
    for path in sys.argv[1:]:
        c = compare(path)
        print("\nRUN %s  state=%s" % (os.path.basename(path), c["state"]))
        if c["state"] != "MEASURED":
            print("  %s" % c["why"])
            print("  run: %s" % c["run"].get("why"))
            continue
        print("  %s" % c["run"]["provenance"])
        print("  %.1fs of timeline" % c["run"]["seconds"])
        for r in c["rows"]:
            print("    %-5s ref %6.2f   run %6.2f   x%s"
                  % (r["family"], r["reference_per_25s"], r["run_per_25s"], r["ratio"]))
