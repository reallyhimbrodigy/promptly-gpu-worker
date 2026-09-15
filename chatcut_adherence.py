#!/usr/bin/env python3
"""Did the agent EXECUTE the plan, or quietly decide it again?

THE FAILURE THIS EXISTS FOR. An agent handed a plan can re-derive the edit and
produce a perfectly good result. The output looks right, the export succeeds,
and the wall does not move — so the lever reads as refuted when it was never
tested. That failure is invisible in the artifact and visible only in the CALL
STREAM, which is why this reads the stream and not the mp4. (Same shape as the
week's governing lesson: a check on the artifact is not a check on the
behaviour.)

THE HEADLINE NUMBER IS TOOL-FREE TURNS. 39 of 88 turns in the 728s deciding run
called no tool at all — that is the model thinking between decisions, and it is
~700 of the 728 seconds. If handing over a plan removes decisions, that share
falls. If it does not, the agent re-decided whatever the prompt said.

STATES, NOT VALUES. Every block reports MEASURED / ABSENT so a run whose stream
failed to classify is never read as a run that did nothing.
"""
import json
import re
import sys


def load(p):
    with open(p, encoding="utf-8") as fh:
        raw = fh.read()
    i = raw.find("{")
    if i < 0:
        return None
    return json.loads(raw[i:raw.rindex("}") + 1])


def main(res_path, plan_path):
    d = load(res_path)
    if not d:
        print("RESULT: ABSENT — no JSON object in", res_path)
        return 2
    plan = open(plan_path, encoding="utf-8").read()
    shape = d.get("shape") or {}
    calls = shape.get("calls") or []

    print("=" * 64)
    print("PLAN-FIRST RUN — %s" % d.get("run_id", "?"))
    print("=" * 64)
    print("  WALL            : %s s" % d.get("wall_s"))
    for k, v in (d.get("marks") or {}).items():
        print("      %-12s %ss" % (k, v))

    # ── TURNS, AND THE ONES THAT CALLED NOTHING ────────────────────────────
    turns = shape.get("turns")
    toolless = shape.get("toolless_turns", shape.get("no_tool_turns"))
    if turns is None:
        print("  TURNS           : ABSENT — the classifier produced no turn count")
    else:
        share = (100.0 * toolless / turns) if (toolless is not None and turns) else None
        print("  TURNS           : MEASURED  %s total, %s called no tool%s"
              % (turns, toolless if toolless is not None else "?",
                 ("  (%.0f%%)" % share) if share is not None else ""))
        print("      BASELINE    : the 728s deciding run was 39 of 88 (44%)")

    # ── WHAT IT CALLED ─────────────────────────────────────────────────────
    if not calls:
        print("  CALLS           : ABSENT — no classified calls; adherence UNDECIDABLE")
        return 1
    byt = {}
    for c in calls:
        byt[c["tool"].split("__")[-1]] = byt.get(c["tool"].split("__")[-1], 0) + 1
    print("  CALLS           : MEASURED  %d total" % len(calls))
    for t, n in sorted(byt.items(), key=lambda kv: -kv[1]):
        print("      %-34s %d" % (t, n))

    # ── ADHERENCE: WHAT THE PLAN RULED OUT, AND WHETHER IT APPEARED ────────
    # NAMED, NOT COUNTED. A total would stay green while one specific ruled-out
    # family crept back in, and the one that slips is the one nobody sees.
    ruled_out = {
        "a motion graphic (0 cards ruled)": ("create_motion_graphic_from_code",
                                             "edit_asset"),
        "sound (0 sfx ruled)":              ("submit_sound", "submit_music"),
        "b-roll (0 cutaways ruled)":        ("search_stock_media", "submit_video"),
        # `trigger_transcript` is TRANSCRIPTION, not a caption placement —
        # ChatCut needs a transcript before read_script works at all. Counting
        # it as a caption violation made a legitimate, required call read as
        # the agent adding something the brief refused.
        "captions (flagged as overreach)":  ("edit_captions", "read_captions"),
    }
    print("  RULED OUT BY THE PLAN:")
    for label, tools in ruled_out.items():
        hit = [c["tool"].split("__")[-1] for c in calls
               if c["tool"].split("__")[-1] in tools]
        print("      %-36s %s" % (label,
              "CLEAN" if not hit else "VIOLATED -> " + ", ".join(sorted(set(hit)))))

    # ── UNDER-DELIVERY, WHICH THIS INSTRUMENT WAS BLIND TO ─────────────────
    # Every adherence leg above asks whether the agent ADDED something the plan
    # ruled out. None asked whether it placed what the plan ruled IN. A run
    # that skips a placement is FASTER and passes every gate: 153.8s, visual
    # pass MEASURED, exit 0, export submitted — and no title, which is the one
    # thing the brief asked for. Over-reach was instrumented; under-delivery
    # was not, and it is the cheaper failure to have.
    planned = len(re.findall(r"^\s*GRAPHIC \d+", plan, re.M)) + \
        len(re.findall(r"^\s*PLACEMENT \d+", plan, re.M))
    adds = 0
    for c in calls:
        if c["tool"].endswith("edit_item"):
            adds += str(c.get("in") or "").count('"type"')
    print("  PLACEMENTS      : plan names %d graphic(s) + 1 base video; "
          "edit_item added %d item(s)  -> %s"
          % (planned, adds,
             "COMPLETE" if adds >= planned + 1 else
             "UNDER-DELIVERED — the plan asked for more than was placed"))

    # ── THE REVIEW PASS, WHICH STAYS ───────────────────────────────────────
    prev = [i for i, c in enumerate(calls)
            if c["tool"].endswith("preview_timeline")]
    exp = [i for i, c in enumerate(calls) if c["tool"].endswith("submit_export")]
    print("  REVIEW PASS     : %d preview(s), %d export(s), looked_before_render=%s"
          % (len(prev), len(exp),
             bool(prev) and (not exp or min(prev) < max(exp))))
    vp = d.get("visual_pass") or {}
    print("  VISUAL PASS     : %s  (sheet=%s preview_before_render=%s)"
          % (vp.get("state", "ABSENT"), vp.get("read_source_sheet"),
             vp.get("previewed_before_render")))

    # ── THE OPEN QUESTIONS IT WAS TOLD TO NAME ─────────────────────────────
    # The plan left size/hold_s/colour unruled and the prompt required the agent
    # to NAME them rather than present them as decided. Whether it did is the
    # test of whether a silent fill is happening.
    msg = d.get("agent_last_message") or shape.get("final_text") or ""
    opens = [f for f in ("size", "hold", "colour", "color")
             if re.search(r"\b%s\b" % f, msg, re.I)]
    print("  OPEN QUESTIONS  : %s"
          % ("named -> " + ", ".join(opens) if opens
             else "NONE NAMED — the plan left 3 fields open and the final "
                  "message mentions none of them"))
    print("  PLAN GIVEN      : %d chars" % len(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/planfirst_result.json",
                  sys.argv[2] if len(sys.argv) > 2 else "/tmp/PLAN.md"))
