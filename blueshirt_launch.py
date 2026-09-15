#!/usr/bin/env python3
"""Turn the pipeline's result into the ChatCut launch — nothing hand-typed.

WHY NOT BY HAND. The title text, its band, size, hold and colour are RULINGS the
pipeline made. Retyping any of them into a launch command makes the run test a
plan nobody produced, and the difference is invisible in the output — the same
shape as an agent quietly re-deciding, one layer further out. So every value
below is read from the result JSON, and the command is printed rather than
typed.

Reads   : the pipeline result JSON (the one with `ledger` and `plan`)
Writes  : /tmp/bs/PLAN_CC.md   — the plan in ChatCut's primitives
          /tmp/bs/titles.json  — one entry per ruled graphic, with its controls
Prints  : the exact `modal run` line, with --detach already on it
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = "/tmp/bs"

CONTROLS = ("size", "case", "where", "colour", "hold_s")
# the acceptor's own names, from TITLE_PROPS in chatcut_job_app.py
TO_PROP = {"where": "band", "size": "size", "hold_s": "holdSeconds",
           "colour": "textColor"}

# `colour` IS A TREATMENT, NOT A COLOUR. The planner's field is a closed enum
# of four semantic tokens — white_on_footage, white_on_black, black_on_white,
# accent — each naming how the words READ against the picture. `textColor` on
# the house title is a ChatCut `color` property, which takes a hex. Mapping the
# name straight across would have posted the string "white_on_footage" into a
# colour field: a value the schema cannot mean, from a field match that checked
# names, units and clock and never checked VOCABULARIES.
#
# Two of the four need a PLATE behind the words, and TITLE_PROPS has no plate
# property — text, band, size, holdSeconds, textColor, accentColor and nothing
# else. So they are refused rather than flattened to their text colour, which
# would silently drop the thing that makes them legible on a busy frame.
COLOUR_TOKENS = {
    "white_on_footage": {"textColor": "#FFFFFF"},
    "accent": {"textColor": "#C8551F"},          # the video's own accent
}
COLOUR_NEEDS_PLATE = {"white_on_black", "black_on_white"}


def titles_from(rows):
    """One entry per ruled `text`/`card` beat, carrying its own controls.

    REFUSES rather than defaults. A graphic whose controls are unanswered would
    be staged with the house defaults and the run would report a placement the
    planner never ruled — `half_ruling_refusal` exists upstream for exactly
    this, and skipping it here would reintroduce the hole one layer out.
    """
    out = []
    for p in rows:
        tr = [t for t in (p.get("treatment") or []) if t != "none"]
        if not ({"text", "card"} & set(tr)):
            continue
        miss = [c for c in CONTROLS if str(p.get(c) or "").strip() == ""]
        if miss:
            raise SystemExit(
                "REFUSING: beat at %.2fs is ruled %s but leaves %s unanswered. "
                "Staging it would invent a ruling the planner did not make."
                % (p.get("src_t0", -1), "+".join(tr), ", ".join(miss)))
        ctl = {TO_PROP[c]: p[c] for c in CONTROLS if c in TO_PROP}
        ctl["holdSeconds"] = float(ctl["holdSeconds"])
        _tok = str(p.get("colour") or "").strip()
        if _tok in COLOUR_NEEDS_PLATE:
            raise SystemExit(
                "REFUSING: beat at %.2fs is ruled colour=%s, which puts the "
                "words on a solid plate so they survive a busy frame. The "
                "house title component has no plate property, so staging it "
                "would drop the plate and keep only the text colour — the "
                "ruling delivered as its own weaker half."
                % (p.get("src_t0", -1), _tok))
        if _tok not in COLOUR_TOKENS:
            raise SystemExit(
                "REFUSING: beat at %.2fs is ruled colour=%r, which is not one "
                "of the planner's four tokens %s. An unmapped token posted "
                "into a ChatCut `color` property is a value the schema cannot "
                "mean." % (p.get("src_t0", -1), _tok,
                           sorted(set(COLOUR_TOKENS) | COLOUR_NEEDS_PLATE)))
        ctl.update(COLOUR_TOKENS[_tok])
        txt = p.get("text_content") or ""
        if str(p.get("case") or "").lower() == "upper":
            txt = txt.upper()
        out.append({"text": txt, "controls": ctl})
    return out


def main(result_json):
    os.makedirs(OUT, exist_ok=True)
    d = json.load(open(result_json, encoding="utf-8"))
    # THE REGIONS TRAVEL WITH THE RULING, because they belong to THIS clip. The
    # translator takes them from the ledger and nowhere else — a regions file
    # picked up off the filesystem would apply one video's face to another.
    _rp = f"{OUT}/regions.json"
    if os.path.exists(_rp):
        d.setdefault("ledger", {})["regions"] = json.load(
            open(_rp, encoding="utf-8"))
        print("  REGIONS     : %s face / %s text %s"
              % (d["ledger"]["regions"].get("face_state"),
                 d["ledger"]["regions"].get("text_state"),
                 d["ledger"]["regions"].get("source_text_regions")))
    else:
        print("  REGIONS     : ABSENT — no %s; the ladder will fail open and "
              "the plan will say so" % _rp)
    json.dump(d, open(f"{OUT}/plan.json", "w"))

    sys.path.insert(0, HERE)
    import plan_for_chatcut as P
    # ALLOW-DROP, NOT REFUSE. `cutaway` and `transition` have no VERIFIED
    # ChatCut primitive, so an outright refusal would kill the run over a
    # family the plan may not even use. With --allow-drop they are removed from
    # the instructions AND NAMED in the plan, so the edit is honest about what
    # it is not doing instead of silently omitting it.
    txt = P.render(f"{OUT}/plan.json", staged=True, allow_drop=True)
    open(f"{OUT}/PLAN_CC.md", "w", encoding="utf-8").write(txt)

    titles = titles_from(d["plan"])
    json.dump(titles, open(f"{OUT}/titles.json", "w"), indent=1)

    keep = d["ledger"]["keep_spans"]
    print("  PLAN        : %d chars, %d kept span(s), %d graphic(s)"
          % (len(txt), len(keep), len(titles)))
    for t in titles:
        print("    %-34r %s" % (t["text"][:34], json.dumps(t["controls"])))
    if not titles:
        print("    (no text/card beats — the run would place cuts only)")

    urls = json.load(open(f"{OUT}/urls.json", encoding="utf-8"))
    cmd = [
        "modal", "run", "--detach", "chatcut_job_app.py::main",
        "--clip-url", urls["src_url"],
        "--plan-file", f"{OUT}/PLAN_CC.md",
        "--brief", "Execute the plan.",
    ]
    # NO TITLE ARGUMENT WHEN THE PLAN NAMES NO GRAPHIC. A placeholder "TITLE"
    # would register an asset the plan never places, and the PLACEMENTS gate
    # would then be explaining away a graphic the harness invented.
    if titles:
        cmd[-2:-2] = ["--prestage-title", titles[0]["text"],
                      "--prestage-titles", json.dumps(titles)]
    open(f"{OUT}/launch.json", "w").write(json.dumps(cmd))
    print("\n  launch argv written to %s/launch.json" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else f"{OUT}/result.json"))
