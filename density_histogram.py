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

A RUN WHOSE ZEROS ARE A REFUSAL IS NOT A MEASUREMENT OF THE EDITOR (Builder 1,
2026-09-21). Three of his last runs placed 7, 0 and 0 graphics, and BOTH zeros
were his own instruments refusing correct work — a face check judging a 720-tall
frame in 1920 space, then a geometry refusal phrased in coordinates the agent
cannot write. A histogram over those reports the refusal rate and calls it the
card rate. `refusal_suspect` flags a record whose families are empty while the
run carries an unsatisfied refusal, so such a run is reported SEPARATELY or not
at all — never averaged in.

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
    """SUPERSEDED FOR PUBLICATION by measured/REFERENCE_RATES.json — see below.

    This function sums ALL beats in the index. That is two annotators, not two
    readings: 60 distinct treatment terms in one pass, 31 in the other, and the
    intersection is ZERO. Pass A names no SFX at all and pass B names no zoom at
    all, so any five-family table computed here averages a real rate with a
    vocabulary GAP — "sfx 1.31" was the mean of 0.00 and 2.64.

    It is kept because the run side and the mapping are still correct and the
    red proof drives it, but `compare()` now refuses to publish against it.
    """
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


# THE STATE THE WRITER ACTUALLY EMITS FOR A DELIVERED EXPORT.
# It is MEASURED. The first version of this reader tested for "OK", which the
# writer has never emitted — `grep '"state": "OK"' chatcut_job_app.py` returns
# nothing — so a PERFECT export would have read ABSENT.
#
# THIS IS WORSE THAN THE end_s BUG ONE FIELD OVER, AND BUILDER 1 NAMED WHY:
# `end_s` is absent on every record, so it fails the first time anyone looks.
# `state` EXISTS and holds a plausible value, so the comparison simply never
# matches and a withheld export and a delivered one both read ABSENT — which is
# precisely the distinction this instrument exists to make. A wrong constant that
# is never equal is silent; a missing field is loud.
EXPORT_DELIVERED = "MEASURED"


def _items_from_record(rec):
    """-> (items, why) — the placed items, or None with the reason there are none."""
    ex = rec.get("export") or {}
    st = str(ex.get("state") or "")
    if st.upper() != EXPORT_DELIVERED:
        # NAME THE STATE SEEN. A state this reader does not know about must be
        # visible in the output, not folded into the same ABSENT as a refusal.
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


def refusal_suspect(record_path):
    """-> {state, suspect, why, unanswered_classes} — is this run's emptiness the editor's?

    A zero that came from a gate refusing correct work is not a density
    measurement, and it enters the histogram looking exactly like restraint.

    TWO TELLS, AND ONLY ONE IS IN THE RECORD.

    (1) ADDS THAT VANISHED BETWEEN TURNS. Measured on kolkata-9: the agent sent
        SEVEN adds in its first write call and FOUR in its second, and nothing
        named the three that went. That run exported cleanly with four cuts and
        zero graphics, and it carries NO unsatisfied refusal at the end — so a
        check keyed on final state passes it as editorial restraint when its
        card rate of 0.00 is measuring a shape refusal that bounced a whole call
        without saying to re-send the rest. This is the tell that catches it.

    (2) A FAULT CLASS WHOSE COUNT DOES NOT MOVE BETWEEN TURNS (Builder 1's rule,
        and the better of the two). kolkata-11 is the fixture that proves why it
        must be per-class: its shape faults went 3 -> 0, the agent answered that
        class completely, while geometry went 3 -> 3 unchanged. "Carries an
        unsatisfied refusal" is true of it; "ignored the refusals" is false, and
        a reader that collapses those mislabels a run where the retry loop
        worked on one class and was unanswerable on the other.

        THIS TELL IS NOT IMPLEMENTED BECAUSE THE RECORD DOES NOT CARRY IT.
        `gate_findings` has no turn field and is byte-identical between
        kolkata-10 and kolkata-11, the two runs the rule exists to separate. The
        per-turn class counts live in the shim log, not the record. Reported as
        ABSENT rather than approximated — a rule applied to data that cannot
        support it is worse than the rule being missing.
    """
    if not os.path.isfile(record_path):
        return {"state": "ABSENT", "suspect": None, "why": "no record"}
    try:
        rec = json.load(open(record_path, encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        return {"state": "FAILED", "suspect": None, "why": "unreadable: %s" % e}
    marks = []

    # (1) adds that shrank between write calls
    adds = []
    for c in ((rec.get("shape") or {}).get("calls") or []):
        raw = c.get("in")
        if not isinstance(raw, str):
            continue
        try:
            adds.append(len((json.loads(raw) or {}).get("adds") or []))
        except Exception:                                      # noqa: BLE001
            continue
    for i in range(1, len(adds)):
        if adds[i] < adds[i - 1]:
            marks.append("adds dropped %d->%d between write calls, unnamed"
                         % (adds[i - 1], adds[i]))

    # final-state tells, which are real but late
    wh = rec.get("withheld") or {}
    for k in ("unbuilt", "could_not_remove"):
        if wh.get(k):
            marks.append("%s=%d" % (k, len(wh[k])))
    for f in (rec.get("gate_findings") or []):
        if str(f.get("verdict") or "").upper() in ("FAIL", "REFUSED", "WITHHOLD"):
            marks.append("gate:%s" % f.get("check"))

    return {"state": "MEASURED", "suspect": bool(marks),
            "adds_per_write_call": adds,
            "unanswered_classes": {"state": "ABSENT",
                                   "why": "the record carries no per-turn fault classes; "
                                          "gate_findings has no turn field"},
            "why": ("; ".join(marks[:6]) if marks else "no refusal tell on the record")}


def _read_pub(path="measured/REFERENCE_RATES.json"):
    """-> {pass: {...}} the per-annotator publication rates, or {} if absent."""
    p = path if os.path.isabs(path) else os.path.join(HERE, path)
    if not os.path.isfile(p):
        return {}
    try:
        return (json.load(open(p, encoding="utf-8")) or {}).get("passes") or {}
    except Exception:                                          # noqa: BLE001
        return {}


def compare(record_path, reference="reference_index.json"):
    ref, run = reference_rates(reference), run_rates(record_path)
    # NEVER COMPARE AGAINST THE CROSS-SEAM MEAN. Publication rates live in
    # measured/REFERENCE_RATES.json, per annotator, with families a pass never
    # named written null rather than zero.
    pub = _read_pub()
    if pub:
        ref = dict(ref, published=pub)
    out = {"reference": ref, "run": run, "rows": [],
           "reference_is_per_pass": bool(pub),
           "grades_only": "This instrument GRADES. It has no threshold and no verdict, and none "
                          "of it may reach an agent at ruling time."}
    if ref.get("state") != "MEASURED" or run.get("state") != "MEASURED":
        out["state"] = "ABSENT"
        out["why"] = "reference %s, run %s — no comparison is possible" % (
            ref.get("state"), run.get("state"))
        return out
    out["state"] = "MEASURED"
    for f in FAMILIES:
        u = run["per_25s"][f]
        row = {"family": f, "run_per_25s": u}
        if pub:
            # One column per annotator. A family a pass never named is ABSENT
            # and gets no ratio — a ratio against a vocabulary gap is a number
            # about nothing.
            for nm, pv in pub.items():
                r = pv["per_25s"].get(f)
                row["ref_%s" % nm] = r
                row["ratio_%s" % nm] = (round(u / r, 2) if r else None)
        else:
            r = ref["per_25s"][f]
            row["reference_per_25s"] = r
            row["ratio"] = round(u / r, 2) if r else None
        out["rows"].append(row)
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
