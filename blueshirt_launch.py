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
        txt = p.get("text_content") or ""
        if str(p.get("case") or "").lower() == "upper":
            txt = txt.upper()
        out.append({"text": txt, "controls": ctl})
    return out


def main(result_json):
    os.makedirs(OUT, exist_ok=True)
    d = json.load(open(result_json, encoding="utf-8"))
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
