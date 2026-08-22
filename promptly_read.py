#!/usr/bin/env python3
"""promptly_read.py — ONE canonical accessor for every job-result shape.

WHY THIS EXISTS. Five separate investigations were spent, or nearly spent, on
readers that looked at the wrong key. Every one of them ran clean, returned a
confident number, and was wrong:

  1. `edit_plan` vs `edit_recipe`      -> "shipped: NONE" for a render that
                                          shipped a StatCard.
  2. `result['timeline']`               -> it is nested under
                                          `stage_timings['timeline']` (put there
                                          deliberately, to survive content-studio's
                                          top-level key strip). Reported "the
                                          render is 100% blind" when the tree was
                                          right there.
  3. `_dh_rs['stage_timings']`          -> render_stage returns it as `timings`.
                                          burst_reported_render_s was None on
                                          6 of 6 burst jobs.
  4. `emphasis.get('t')`                -> _EmphasisMoment carries word_indices.
                                          Every timestamp read 0.0 in BOTH arms
                                          of an A/B, so placement went unmeasured
                                          while the counts "held".
  5. `component_ledger['requested']`    -> `requested` is nested PER KIND. Every
                                          job scored 0 and the render-cost
                                          hypothesis could not be tested at all.

The common shape is not carelessness — it is that the SAME datum lives under
different keys in different envelopes, and a wrong key is not an error. It is a
None, a 0, or an empty dict, which reads exactly like a real negative result.
That is the dangerous part: these bugs manufacture confident zeros.

So: every reader goes through here. A function that returns UNKNOWN when it
cannot find a thing is worth more than one that returns 0.

    from promptly_read import stage_timings, timeline, component_ledger
"""
import json

__all__ = ["as_dict", "stage_timings", "timeline", "render_span",
           "component_ledger", "ledger_totals", "gemini_tokens", "edit_plan",
           "route", "MISSING"]


class _Missing:
    """Distinct from 0, {}, None and False.

    A reader that cannot distinguish "absent" from "zero" will eventually
    report a zero it did not measure — which is exactly how a 100%-blind render
    tree and an untestable cost hypothesis both got written down as findings.
    """
    __slots__ = ()

    def __bool__(self):
        return False

    def __repr__(self):
        return "MISSING"


MISSING = _Missing()


def as_dict(v):
    """jsonb columns arrive as dict OR as a JSON string, depending on the client
    and the column. Every accessor below funnels through this."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v:
        try:
            out = json.loads(v)
            return out if isinstance(out, dict) else {}
        except Exception:
            return {}
    return {}


def stage_timings(row):
    """Timings live on the ROW as `stage_timings`, and are ALSO mirrored inside
    `result`. Prefer the row; fall back to the mirror."""
    row = as_dict(row)
    st = as_dict(row.get("stage_timings"))
    if st:
        return st
    return as_dict(as_dict(row.get("result")).get("stage_timings"))


def timeline(row):
    """BUG 2. Nested under stage_timings, NOT under result — deliberately, so
    content-studio's top-level key strip cannot eat it. Returns MISSING when
    absent, never {}."""
    tl = as_dict(stage_timings(row)).get("timeline")
    return as_dict(tl) if isinstance(tl, (dict, str)) and tl else MISSING


def render_span(row):
    """The `render` node of the job timeline, wherever it sits in the tree.
    Returns MISSING if there is no timeline at all — which is NOT the same as a
    render span with no children, and the two must never be conflated."""
    tl = timeline(row)
    if tl is MISSING:
        return MISSING

    def _walk(n):
        if not isinstance(n, dict):
            return None
        if n.get("name") == "render":
            return n
        for c in n.get("children") or []:
            f = _walk(c)
            if f:
                return f
        return None
    return _walk(tl) or MISSING


def component_ledger(row):
    """BUG 5. Shape is {kind: {requested, dropped_by_us, survived_derived,
    drop_reasons}}. Returns MISSING when the job carries no ledger, so a job
    that was never instrumented cannot be counted as a job with zero
    components."""
    cl = as_dict(as_dict(as_dict(row).get("result")).get("component_ledger"))
    return cl if cl else MISSING


def ledger_totals(row):
    """(requested, survived, per_kind_survived) or MISSING.

    `requested` is nested PER KIND — summing a top-level 'requested' key, which
    does not exist, silently yields 0 for every job."""
    cl = component_ledger(row)
    if cl is MISSING:
        return MISSING
    req = surv = 0
    per = {}
    for kind, d in cl.items():
        if not isinstance(d, dict):
            continue
        r, s = d.get("requested"), d.get("survived_derived")
        if isinstance(r, int):
            req += r
        if isinstance(s, int):
            surv += s
            per[kind] = s
    return req, surv, per


def gemini_tokens(row):
    """Nested in stage_timings for the same key-strip reason as the timeline.
    Carries n_calls — the ONLY trace of a recipe repair re-ask, which has no
    counter of its own and is invisible in degen_retries."""
    gt = as_dict(stage_timings(row)).get("gemini_tokens")
    return as_dict(gt) if gt else MISSING


def edit_plan(row):
    """BUG 1. The payload key is `edit_recipe`. `edit_plan` is the in-process
    variable name and is NOT what lands in the row or the envelope."""
    row = as_dict(row)
    for src in (row, as_dict(row.get("result"))):
        rec = src.get("edit_recipe")
        if rec:
            return as_dict(rec)
    return MISSING


def route(row):
    """Premium routes self-declare via result.route; the editorial path does not
    declare one and is identified by its Gemini fingerprints instead."""
    res = as_dict(as_dict(row).get("result"))
    r = res.get("route")
    if r in ("hype", "moodreel"):
        return str(r)
    st = stage_timings(row)
    if any(k in st for k in ("gemini_call", "edit_plan", "degen_retries")):
        rec = edit_plan(row)
        note = str((rec or {}).get("notes") or "") if rec is not MISSING else ""
        return "safe-edit" if "safe-edit" in note else "EDITORIAL"
    if "plan" in st:
        return "lean/plan"
    return "other"
