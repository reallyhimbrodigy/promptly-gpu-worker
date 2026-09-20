"""THE INVENTORY — one uniform entry per component, derived, never invented.

Zac's restatement of item 5:

    all 79 components, one uniform entry each — picture rendered on a real frame
    at reference scale + one line (name · vibe it carries · what it's for).
    Grouped by family and occasion. No comparative language anywhere: no
    "workhorse", no "most common", no FITS/FIGHTS, nothing ranking one against
    another. Size and attack as numbers where measured, "atlas pending" where
    not. The paragraph says once that every family has its place and none
    outranks another.

EVERY LINE CITES ITS SOURCE OR IS NOT EMITTED. The line is the part a model
reads and acts on, so a line I invented would be my taste shipped as the
library's description, and nothing downstream could tell it from a measurement.
So `line_for` returns a STATE: MEASURED with the table it came from, or
ATLAS PENDING naming what is missing. There is no third option where I write a
nice sentence.

WHY THE ENTRY IS UNIFORM. A library where some entries are rich and some are
bare teaches the reader that the rich ones are the real ones — which is a
ranking, assembled by accident out of uneven effort. Uniform means every entry
has the same fields in the same order, and an unmeasured field says so in the
same words everywhere.

NO COMPARATIVE LANGUAGE, AND THE MEASUREMENTS MAKE THAT HARDER THAN IT SOUNDS.
The peaks table this reads from is written comparatively on purpose — "11.5x
less headroom", "the three above are 11x to 30x over, and that is the point" —
because it is an argument about a ceiling. An inventory entry is not an
argument. It carries the NUMBER (126.6 px/frame) and not the RATIO to anything
else, because a ratio needs a second thing and naming one ranks it.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# THE SENTENCE, SAID ONCE, AT THE TOP. Zac: "The paragraph says once that every
# family has its place and none outranks another." Once, not per entry -- a
# reassurance repeated 79 times reads as a defence, and a defence implies a
# charge.
PREAMBLE = (
    "THE LIBRARY. Every family here has its place and none outranks another; "
    "what decides is the moment in front of you, not the entry's position in "
    "this list. Each entry is the same shape: what it is, the vibe it carries, "
    "and what it is for. Numbers are measured where a number exists and say "
    "ATLAS PENDING where one does not."
)

# Occasions are the grouping Zac asked for beside family. They describe WHEN a
# family is reached for, in the moment's own terms, and deliberately not in
# terms of any other family.
FAMILY_OCCASION = {
    "caption style": "when the words themselves carry the moment",
    "zoom": "when the framing should move without a cut",
    "transition": "when one shot becomes another",
    "tight-cut overlay": "when a cut wants a mark on it",
    "motion graphic": "when something needs to be shown, not said",
    "sfx": "when a moment wants to be heard",
    "text overlay": "when a few words sit over the picture",
}


def _read(path, default=None):
    try:
        return json.load(open(os.path.join(HERE, path), encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _consts(names, src=None):
    """Pull a dict-literal constant out of chatcut_job_app.py by name.

    READ FROM THE SOURCE OF TRUTH rather than copied here. A second copy of
    CAPTION_STYLE_FONT in this file would drift from the one the harness
    actually drives, and the inventory would describe a library that no longer
    exists -- which is the failure this whole file is written against.
    """
    src = src if src is not None else open(
        os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
    out = {}
    for nm in names:
        m = re.search(nm + r"\s*=\s*\{(.*?)\n\}", src, re.S)
        out[nm] = m.group(1) if m else None
    return out


def caption_facts(src=None):
    """-> {name: {font, weight, case}} from the harness's own tables."""
    c = _consts(["CAPTION_STYLE_FONT", "CAPTION_STYLE_WEIGHT_CASE"], src)
    fonts, wc = {}, {}
    if c["CAPTION_STYLE_FONT"]:
        for k, v in re.findall(r'"([A-Za-z]+)":\s*"([^"]+)"', c["CAPTION_STYLE_FONT"]):
            fonts[k] = v
    if c["CAPTION_STYLE_WEIGHT_CASE"]:
        for k, w, cs in re.findall(r'"([A-Za-z]+)":\s*\((\d+),\s*"([a-z]+)"\)',
                                   c["CAPTION_STYLE_WEIGHT_CASE"]):
            wc[k] = (int(w), cs)
    return {k: {"font": fonts.get(k), "weight": wc.get(k, (None, None))[0],
                "case": wc.get(k, (None, None))[1]}
            for k in set(fonts) | set(wc)}


def motion_facts(path="measured/transition_peaks_2026-09-20.md"):
    """-> {name: {peak_px_frame, move}} from the measured peaks table.

    THE NUMBER TRAVELS, THE RATIO DOES NOT. The table states both; an entry
    carries only the peak, because a ratio needs a second thing and naming one
    ranks it.
    """
    out = {}
    try:
        txt = open(os.path.join(HERE, path), encoding="utf-8").read()
    except OSError:
        return out
    for ln in txt.splitlines():
        m = re.match(r"\s*\|\s*\**([A-Za-z]+)\**\s*\|\s*([^|]+?)\s*\|\s*\**([\d.]+)\**\s*\|",
                     ln)
        if m:
            out[m.group(1)] = {"peak_px_frame": float(m.group(3)),
                               "move": m.group(2).strip()}
    # DipToBlack is EXEMPT BY NATURE, not by margin: it moves no pixels, so it
    # has no peak to compare against a per-frame ceiling. Recorded as a kind of
    # fact rather than as a 0.0 in a column of 126.6 and 328.2, which is an
    # invitation to average. (Builder-2's finding, 2026-09-20.)
    out.setdefault("DipToBlack", {"peak_px_frame": None,
                                  "move": "no pixel displacement — exempt by nature"})
    return out


def sfx_facts(path="_asset_inventory.json"):
    """-> {stem: {attack_ms, file}}. Keyed by STEM, because the catalogue
    advertises names WITH extensions and the attack table stores them without —
    the exact mismatch that made `boom.mp3` unmatchable as `boommp3` and lost
    two of four ruled sfx in one run."""
    ai = _read(path, {}) or {}
    sf = ai.get("sfx") or {}
    at = sf.get("attack_ms") or {}
    files = sf.get("files") or []
    out = {}
    for f in files:
        stem = f.rsplit(".", 1)[0]
        out[stem] = {"attack_ms": at.get(stem), "file": f}
    for stem, ms in at.items():
        out.setdefault(stem, {"attack_ms": ms, "file": None})
    return out


def line_for(name, family, facts):
    """One entry. -> {state, name, family, line, numbers, source, why}

    MEASURED or ATLAS PENDING. There is no branch that writes a sentence from
    nothing.
    """
    out = {"state": "ATLAS PENDING", "name": name, "family": family,
           "line": None, "numbers": {}, "source": None,
           "why": "no measured table covers %s" % name}
    if family == "caption style":
        f = (facts.get("caption") or {}).get(name)
        if f and f.get("font"):
            case = {"none": "sentence case", "uppercase": "upper case",
                    "lowercase": "lower case"}.get(f.get("case"), f.get("case"))
            return {"state": "MEASURED", "name": name, "family": family,
                    "line": "%s · %s at weight %s, %s · when the words themselves "
                            "carry the moment" % (name, f["font"], f["weight"], case),
                    "numbers": {"weight": f["weight"]},
                    "source": "CAPTION_STYLE_FONT / CAPTION_STYLE_WEIGHT_CASE",
                    "why": "typeface, weight and case read from the harness's tables"}
        return dict(out, why="no font/weight row for %s" % name)
    if family in ("transition", "zoom", "tight-cut overlay"):
        f = (facts.get("motion") or {}).get(name)
        if f:
            if f.get("peak_px_frame") is None:
                return {"state": "MEASURED", "name": name, "family": family,
                        "line": "%s · %s · %s" % (name, f["move"],
                                                  FAMILY_OCCASION.get(family, "")),
                        "numbers": {"peak_px_frame": None},
                        "source": "measured/transition_peaks_2026-09-20.md",
                        "why": "no displacement to measure — exempt by nature"}
            return {"state": "MEASURED", "name": name, "family": family,
                    "line": "%s · %s · peak %.1f px/frame · %s"
                            % (name, f["move"], f["peak_px_frame"],
                               FAMILY_OCCASION.get(family, "")),
                    "numbers": {"peak_px_frame": f["peak_px_frame"]},
                    "source": "measured/transition_peaks_2026-09-20.md",
                    "why": "peak displacement measured at 1080x1920, 30fps"}
        return dict(out, why="%s is not in the measured peaks table yet" % name)
    if family == "sfx":
        f = (facts.get("sfx") or {}).get(name) or (facts.get("sfx") or {}).get(
            name.rsplit(".", 1)[0])
        if f and f.get("attack_ms") is not None:
            return {"state": "MEASURED", "name": name, "family": family,
                    "line": "%s · attack %dms · when a moment wants to be heard"
                            % (name, f["attack_ms"]),
                    "numbers": {"attack_ms": f["attack_ms"]},
                    "source": "_asset_inventory.json sfx.attack_ms",
                    "why": "attack measured by argmax of the RMS envelope"}
        return dict(out, why="no attack measurement for %s" % name)
    cat = (facts.get("catalogue") or {}).get(name)
    if cat and (cat.get("when") or "").strip():
        band = cat.get("size_band")
        return {"state": "MEASURED", "name": name, "family": family,
                "line": "%s · %s · %s" % (name, (band or "size atlas pending").lower(),
                                          (cat["when"] or "").strip().lower()),
                "numbers": {"size_band": band},
                "source": "chatcut_catalogue.json",
                "why": "occasion and size band from the catalogue"}
    return dict(out, why="the catalogue has no entry for %s" % name)


def build(library_path="library_73.json"):
    """-> {state, entries, measured, pending, families, why}"""
    lib = _read(library_path)
    if not isinstance(lib, dict) or not lib:
        return {"state": "FAILED", "entries": [], "measured": 0, "pending": 0,
                "families": 0, "why": "no library at %s" % library_path}
    src = open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
    cat = _read("chatcut_catalogue.json", {}) or {}
    facts = {"caption": caption_facts(src), "motion": motion_facts(),
             "sfx": sfx_facts(), "catalogue": cat.get("components") or cat}
    entries = []
    for fam, items in lib.items():
        if fam == "_why":
            continue
        for it in items:
            nm = it if isinstance(it, str) else (
                it.get("name") or it.get("component") or str(it))
            entries.append(line_for(nm, fam, facts))
    meas = sum(1 for e in entries if e["state"] == "MEASURED")
    return {"state": "MEASURED", "entries": entries, "measured": meas,
            "pending": len(entries) - meas,
            "families": len([k for k in lib if k != "_why"]),
            "why": "%d entr(ies) across %d famil(ies); %d measured, %d atlas pending"
                   % (len(entries), len([k for k in lib if k != "_why"]),
                      meas, len(entries) - meas)}


# THE CHECK THAT KEEPS IT CLEAN. Zac: "keep the check that proves it stays
# clean." It scans what the inventory EMITS, which is the surface the rule is
# about -- the catalogue being clean is necessary and is not the same claim.
COMPARATIVE = re.compile(
    r"\b(workhorse|most\s+common|go-to|default\s+to|better\s+than|best\b|worst\b"
    r"|instead\s+of|rather\s+than|unlike\b|strongest|weakest|prefer\b|preferred"
    r"|more\s+than|less\s+than|outranks|superior|inferior|FITS:|FIGHTS:)", re.I)


def comparative_hits(built=None):
    """-> [(name, phrase, line)] for every emitted line that ranks something."""
    built = built if built is not None else build()
    hits = []
    for e in built.get("entries") or []:
        if not e.get("line"):
            continue
        m = COMPARATIVE.search(e["line"])
        if m:
            hits.append((e["name"], m.group(0), e["line"][:90]))
    return hits
