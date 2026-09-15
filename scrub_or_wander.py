#!/usr/bin/env python3
"""Does the agent scrub like an editor, or wander? Written BEFORE the run.

PRE-REGISTERED ON PURPOSE. The turn count is no longer bounded by design, so a
run now measures what the agent CHOOSES to look at — and "it scrubbed
sensibly" is exactly the kind of verdict that gets fitted to whatever the
record turns out to say. So the criterion is code, and it exists before the
number it will judge.

An EDITOR's looking has a shape:
  NEAR      the frames it asks for cluster on its own placements — entrances,
            exits, the moments it just changed. An editor checks its work, not
            the whole timeline uniformly.
  FOLLOWED  a look is followed by a decision: a fix, or the export. Looks that
            lead to nothing are the tell for wandering.
  FRESH     it does not ask for the same frame twice. A repeat is not scrubbing,
            it is being lost.
  BOUNDED   the count is proportionate to what it placed, not escalating.

WANDERING is the inverse: frames spread evenly with no relation to the
placements, repeats, and looks that change nothing.

This reports the four, and a verdict only when all four are answerable — a
partial read is ABSENT, not a lean.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_chain as V                                       # noqa: E402


def frames_asked(calls):
    """Every timeline frame the agent asked to see, in order."""
    out = []
    for c in calls:
        if not c["tool"].endswith("preview_timeline"):
            continue
        try:
            a = json.loads(c["in"])
        except Exception:                                      # noqa: BLE001
            continue
        for f in (a.get("viewerFrames") or []):
            if isinstance(f, int):
                out.append((c["turn"], f))
        if a.get("viewerFrameCount"):
            out.append((c["turn"], None))        # a uniform sample, not a moment
    return out


def report(record_path, plan_path=None, near_frames=45):
    """The record carries the agent's calls; the PLAN carries the placements.

    The result record does not embed the plan — `d.get("plan")` is empty — so
    the edges have to come from the plan file beside the run. A first version
    read the record alone and reported ABSENT with "no placement edges", which
    was true and useless: the input was in the next directory.
    """
    d = json.load(open(record_path, encoding="utf-8"))
    calls = (d.get("shape") or {}).get("calls") or []
    plan = ""
    for cand in ([plan_path] if plan_path else []) + ["/tmp/bs/PLAN_CC.md"]:
        if cand and os.path.exists(cand):
            plan = open(cand, encoding="utf-8").read()
            break
    man = V.plan_manifest(plan) if plan else []
    # the moments the agent itself created: every placement's start and end
    edges = sorted({e for r in man if r.get("from") is not None
                    for e in (r["from"], r["from"] + (r.get("dur") or 0))})
    asked = frames_asked(calls)
    exact = [f for _t, f in asked if f is not None]
    out = {"looks": len(asked), "exact_frames": len(exact),
           "placement_edges": len(edges)}

    if not edges or not exact:
        out["verdict"] = "ABSENT"
        out["why"] = ("no placement edges from the plan" if not edges
                      else "the agent asked for no exact frame — it took the "
                           "uniform sample and nothing else")
        return out

    # THE WINDOW IS CHOSEN BY THE CHANCE RATE ON THIS TIMELINE, not fixed.
    # At +/-45 frames, 8 placements across 608 frames cover 89% of it — so
    # "did it look near a placement" carries almost no information, and a
    # synthetic WANDERER scored 83% against a 60% bar. Tuning the window until
    # it discriminated would be fitting the instrument to the verdict I wanted.
    # Instead: take the WIDEST window whose coverage is still low enough to be
    # informative on this particular timeline, and report the margin over
    # chance at that window. If no window qualifies, the edit is too dense for
    # this question and the leg says so rather than guessing.
    span = max(edges) - min(edges) or 1

    def _cov(w):
        c = set()
        for e in edges:
            c |= set(range(max(0, e - w), e + w + 1))
        return len(c) / float(span + 1)

    win = None
    for w in range(near_frames, 1, -1):
        if _cov(w) <= 0.40:
            win = w
            break
    if win is None:
        out["verdict"] = "ABSENT"
        out["why"] = ("the placements are too dense on this timeline for "
                      "'near a placement' to mean anything — even a +/-2 frame "
                      "window covers %.0f%% of it" % (_cov(2) * 100))
        return out
    out["window_frames"] = win
    out["chance_share"] = round(_cov(win), 3)
    near = sum(1 for f in exact if any(abs(f - e) <= win for e in edges))
    out["near_share"] = round(near / float(len(exact)), 3)
    out["near_over_chance"] = round(out["near_share"] - out["chance_share"], 3)
    out["repeats"] = len(exact) - len(set(exact))

    # a look is FOLLOWED if a fix or the export comes after it
    _acts = [i for i, c in enumerate(calls)
             if c["tool"].endswith(("edit_item", "submit_export"))]
    _looks = [i for i, c in enumerate(calls)
              if c["tool"].endswith("preview_timeline")]
    out["followed"] = sum(1 for li in _looks if any(a > li for a in _acts))
    out["looks_leading_nowhere"] = len(_looks) - out["followed"]

    # proportionate: one look per placement is generous for a 10-item edit
    out["per_placement"] = round(len(exact) / float(max(1, len(man))), 2)

    editorly = (out["near_over_chance"] >= 0.15 and out["repeats"] == 0
                and out["looks_leading_nowhere"] == 0
                and out["per_placement"] <= 3.0)
    out["verdict"] = "SCRUBS" if editorly else "WANDERS"
    out["why"] = (
        "%.0f%% of its frames sit within %d of something it placed, against "
        "%.0f%% by chance on this timeline (+%.0f points), no repeats, every "
        "look followed by a fix or the export, %.2f frames per placement"
        % (out["near_share"] * 100, out["window_frames"],
           out["chance_share"] * 100,
           out["near_over_chance"] * 100, out["per_placement"])
        if editorly else
        "near=%.0f%% vs %.0f%% by chance (+%.0f, want >=+15), repeats=%d "
        "(want 0), looks leading nowhere=%d (want 0), frames per "
        "placement=%.2f (want <=3)"
        % (out["near_share"] * 100, out["chance_share"] * 100,
           out["near_over_chance"] * 100, out["repeats"],
           out["looks_leading_nowhere"], out["per_placement"]))
    return out


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "/tmp/bs/run22_record.json"
    r = report(p, sys.argv[2] if len(sys.argv) > 2 else None)
    print("SCRUB OR WANDER — %s" % os.path.basename(p))
    for k in ("looks", "exact_frames", "placement_edges", "near_share",
              "repeats", "followed", "looks_leading_nowhere", "per_placement"):
        if k in r:
            print("  %-22s %s" % (k, r[k]))
    print("\n  VERDICT: %s" % r["verdict"])
    print("  %s" % r["why"])
