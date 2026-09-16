#!/usr/bin/env python3
"""ONE CONTINUOUS RUN: source in, planner, translate, ChatCut, export out.

Zac, 2026-09-15: "Both numbers are additions of separate phases on the same
clip and that isn't a measurement."

He is right, and the gap was not only arithmetic. Adding two phases assumes a
SEAM THAT HAS NEVER RUN — the planner's result reaching the translator, the
translator's plan reaching ChatCut, and the titles the prestage registers being
derived from the SAME rows the plan text was written from. Every one of those
is a place a real end-to-end run can fail and two separate runs cannot.

SO THE TITLES ARE DERIVED HERE, from the result's plan rows, in the same step
that writes the plan text. The previous launcher carried a HAND-WRITTEN title
list next to a generated plan: two artefacts from one source, free to drift,
and that drift is exactly how the card was lost once before (the plan named it,
the launcher never carried card_hero, the asset registered without it, and the
run went green on a graphic that rendered its title and no card).

THE CLOCK IS ONE CLOCK. Phase walls are reported, but the number that matters
is T0 to export-submitted, including the seam — which is the part nobody has
ever timed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

# The band a planner `where` maps to on the prestaged title component. Named
# rather than passed through: `where` is the planner's vocabulary and `band` is
# ChatCut's, and a silent identity mapping between two vocabularies is how a
# rename becomes a placement nobody ordered.
_BAND = {"upper_third": "upper_third", "upper": "upper_third",
         "lower_third": "lower_third", "lower": "lower_third",
         "center": "center", "centre": "center"}


def titles_from(result):
    """The prestage title list, from the SAME rows the plan text is built from.

    Returns (titles, why) — `why` names every row that was skipped and the
    reason, because a title list that is quietly short registers fewer assets
    than the plan names and HOP 2 then refuses the run with a number nobody can
    trace back.
    """
    rows = result.get("plan") or []
    out, skipped = [], []
    for r in rows:
        tr = set(r.get("treatment") or [])
        if "text" not in tr:
            continue
        txt = (r.get("text_content") or "").strip()
        if not txt:
            skipped.append("beat %s ruled text with no text_content"
                           % r.get("beat"))
            continue
        c = {}
        if r.get("size"):
            c["size"] = r["size"]
        w = _BAND.get(str(r.get("where") or "").lower())
        if w:
            c["band"] = w
        elif r.get("where"):
            skipped.append("beat %s has where=%r, which maps to no band"
                           % (r.get("beat"), r.get("where")))
        if r.get("hold_s"):
            c["holdSeconds"] = float(r["hold_s"])
        out.append({"text": txt, "controls": c})
    return out, skipped


def run(cmd, log, label, env=None):
    """MY BUG, KEPT AS THE COMMENT IT EARNED: the first version built an `env`
    carrying PROMPTLY_RESULT_JSON and never passed it to subprocess.run. A
    value correctly computed and dropped at the call — the producer/consumer
    shape, in the driver written to close a producer/consumer seam."""
    t0 = time.time()
    print("  -> %s" % label, flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True,
                       env=env or os.environ.copy())
    open(log, "w").write((r.stdout or "") + (r.stderr or ""))
    return r, round(time.time() - t0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip-url", required=True)
    ap.add_argument("--brief", default="Cut this into a punchy vertical short. "
                                       "Remove silence and filler. Keep the "
                                       "meaning intact. Burn readable captions.")
    ap.add_argument("--out", default="/tmp/bs/e2e")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    base = os.path.basename(a.clip_url.split("?")[0]).rsplit(".", 1)[0]
    res_path = os.path.join(a.out, "result.json")

    T0 = time.time()
    marks = {}

    # ── PHASE 1: THE PLANNER ────────────────────────────────────────────────
    env = dict(os.environ, PROMPTLY_RESULT_JSON=res_path)
    r1, s1 = run(["modal", "run", "--detach", "agentic_editor_app.py::main",
                  "--plan-only", "--src-url", a.clip_url, "--brief", a.brief],
                 os.path.join(a.out, "planner.log"), "planner (plan_only)",
                 env=env)
    # the entrypoint writes the result on THIS machine; env has to reach it
    if not os.path.exists(res_path):
        # the env var is read inside main(), which runs locally — but only if
        # subprocess carried it. Retry the read from the default path rather
        # than guessing the run failed.
        # AND THE FALLBACK READS THE LOG RATHER THAN GUESSING. The planner
        # PRINTS the path it wrote; deriving a second guess from the clip name
        # is how the driver looked for `result_talking_head-f4195ca9.json`
        # while the file on disk was `result_625dfdc5-73s.json`, named after a
        # default parameter the run never used.
        _pl = open(os.path.join(a.out, "planner.log"), errors="replace").read()
        _m = re.search(r"RESULT JSON\s+:\s+(\S+\.json)", _pl)
        alt = _m.group(1) if _m else "/tmp/result_%s.json" % base
        if os.path.exists(alt):
            print("     (result at %s — the env var did not reach the "
                  "entrypoint)" % alt)
            res_path = alt
        else:
            print("PLANNER PRODUCED NO RESULT JSON. Nothing downstream can "
                  "run; this is the seam failing, not the plan being empty.")
            print((r1.stdout or "")[-1500:])
            return 2
    marks["planner"] = s1
    result = json.load(open(res_path))
    led = result.get("ledger") or {}
    rulings = led.get("executed_verdicts") or led.get("beat_verdicts") or []
    fams = {}
    for v in rulings:
        for f in (v.get("treatment") or []):
            fams[f] = fams.get(f, 0) + 1
    print("     %d ruling(s): %s" % (len(rulings), fams))

    # ── THE SEAM ────────────────────────────────────────────────────────────
    t = time.time()
    plan_path = os.path.join(a.out, "PLAN.md")
    p = subprocess.run([sys.executable, "plan_for_chatcut.py", res_path,
                        plan_path, "--staged"], capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(plan_path):
        print("TRANSLATOR REFUSED — and a refusal here is the pipeline working:")
        print((p.stdout or p.stderr or "")[:900])
        return 3
    titles, skipped = titles_from(result)
    # THE LEDGER'S OWN BEATS, PASSED THROUGH — not a shape invented here.
    #
    # MY BUG, AND IT IS THE SEAM ZAC SAID HAD NEVER RUN. I wrote
    # `{"beats": [{"t0","t1","purpose","text"}]}` from the plan rows. The
    # harness iterates the value it is given, so a DICT iterated as a list
    # yields its KEYS — strings — and `pass1_message` died on
    # `'str' object has no attribute 'get'`. It also printed
    # "transcript=1 beat(s)", which is the dict's one key counted as a beat: a
    # wrong shape reporting a plausible number on its way to a crash.
    #
    # And the keys were wrong twice over: `t0/t1` against the `t_start/t_end`
    # the harness reads, and `text` taken from `text_content` — the OVERLAY
    # copy — where the transcript wants what was SPOKEN. Three mistakes in one
    # four-line translation, none of which two separate phases could surface.
    #
    # `led["beats"]` is already exactly the shape the harness reads. Passing it
    # through is not a shortcut; re-deriving it is the bug.
    tx_path = os.path.join(a.out, "transcript.json")
    _beats = led.get("beats") or []
    if not _beats:
        print("     *** the ledger carries no beats — the harness will run "
              "without a transcript, and that is a gap, not a shorter one")
    json.dump(_beats, open(tx_path, "w"))
    marks["seam"] = round(time.time() - t, 1)
    print("     transcript %d beat(s) passed through" % len(_beats))
    print("     plan %d chars, %d title(s) derived%s"
          % (os.path.getsize(plan_path), len(titles),
             ("; skipped: %s" % skipped[:2]) if skipped else ""))

    # ── PHASE 2: CHATCUT ────────────────────────────────────────────────────
    cmd = ["modal", "run", "--detach", "chatcut_job_app.py::main",
           "--clip-url", a.clip_url, "--plan-file", plan_path,
           "--brief", "Execute the plan.",
           "--transcript-file", tx_path]
    if titles:
        cmd += ["--prestage-title", titles[0]["text"],
                "--prestage-titles", json.dumps(titles)]
    r2, s2 = run(cmd, os.path.join(a.out, "chatcut.log"), "ChatCut (execute)")
    marks["chatcut_launch"] = s2
    m = re.search(r"SPAWNED run_id=(\S+)", r2.stdout or "")
    if not m:
        print("CHATCUT DID NOT LAUNCH:")
        print((r2.stdout or "")[-1200:])
        return 4
    rid = m.group(1)
    rec = os.path.join(a.out, "chatcut_record.json")
    for _ in range(90):
        time.sleep(20)
        subprocess.run(["modal", "run", "chatcut_read_result.py",
                        "--run-id", rid, "--out", rec],
                       capture_output=True, text=True)
        if os.path.exists(rec):
            break
    if not os.path.exists(rec):
        print("NO CHATCUT RECORD after 30min — the execution half is ABSENT, "
              "not empty.")
        return 5
    d = json.load(open(rec))
    T1 = time.time()

    # ── THE REPORT ──────────────────────────────────────────────────────────
    tb = d.get("turn_budget") or {}
    sh = d.get("shape") or {}
    gb = tb.get("generating_by_block_s") or {}
    prev = [c for c in (sh.get("calls") or [])
            if "preview_timeline" in c["tool"]]
    hops = {k: (v or {}).get("state")
            for k, v in sorted((d.get("chain") or {}).items())
            if isinstance(v, dict) and k.startswith("hop")}
    out = {
        "END TO END (T0 -> record in hand)": round(T1 - T0, 1),
        "phases": dict(marks, chatcut_agent=d.get("wall_s")),
        "planner_rulings": fams,
        "chatcut": {
            "wall_s": d.get("wall_s"),
            "assistant_turns": sh.get("assistant_turns"),
            "tool_calls": sh.get("tool_calls"),
            "review_previews": len(prev),
            "thinking_s": gb.get("thinking"),
            "tool_use_s": gb.get("tool_use"),
            "frames_served": (d.get("frames_served") or {}).get("state"),
            "pass2": d.get("pass2"),
            "placements": (d.get("placements") or {}).get("state"),
            "hops": hops},
        "per_turn_thinking": [
            {"n": t["n"], "s": t["s"],
             "thinking": (t.get("blocks") or {}).get("thinking", 0)}
            for t in (tb.get("per_turn") or [])],
    }
    json.dump(out, open(os.path.join(a.out, "e2e.json"), "w"), indent=1)
    print("\n" + json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
