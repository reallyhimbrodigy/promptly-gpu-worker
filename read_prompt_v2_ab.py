#!/usr/bin/env python3
"""READ THE PROMPT-V2 A/B AGAINST ITS PRE-REGISTRATION. `[Rule 5, Rule 2]`

Written BEFORE the run finished, deliberately. PROMPT_V2_AB_PREREGISTRATION.md
fixed the thresholds before the harness existed; this applies them mechanically
so the verdict is not chosen after seeing the columns. This project's standing
habit is explaining an outcome once it exists — the defence is that the rule
runs itself.

WHAT IT ENFORCES WITHOUT ASKING:

  · the WIN condition — requested placements >= 2x arm A on trigger-bearing
    sources, dropped_by_us not rising faster than requested, and at least one
    component class off zero (generated_scenes is the one the campaign was
    built around);
  · INCONCLUSIVE AT THIS n — any delta under 30% is reported as a non-result at
    n=13, never as a direction. 13 sources can see a 2x effect and cannot
    resolve a 20% one;
  · the wall ceiling — 36s p50 (28.0s measured + the 30% the pre-registration
    allows) — and a token INCREASE reported as a red flag, not a cost;
  · TOKENS PER BEAT WITH A REAL READ — raw output tokens are not comparable
    across arms that emit different shapes. A beat whose `read` is blank cost
    tokens and bought nothing; normalising by beats that actually carry a read
    is what says whether the doctrine is expensive or merely verbose.

    python3 read_prompt_v2_ab.py [/tmp/prompt_v2_ab_result.json]
"""
import json
import statistics
import sys

FAMILIES = ("cut_refinements", "emphasis_moments", "text_overlays", "broll_clips",
            "generated_scenes", "motion_graphics", "caption_keywords",
            "caption_position_changes")
INCONCLUSIVE_BAND = 0.30
WALL_CEILING_S = 36.0


def _p50(vals):
    v = sorted(x for x in vals if isinstance(x, (int, float)))
    return statistics.median(v) if v else None


def _ledger_totals(cells):
    req = drop = 0
    for c in cells:
        for _k, v in (c.get("ledger") or {}).items():
            req += int(v.get("requested", 0))
            drop += int(v.get("dropped_by_us", 0))
    return req, drop


def _real_reads(cell):
    """Beats whose `read` says something. A blank read is a beat that cost
    tokens and bought nothing — counting it would flatter the arm that emits
    empty scaffolding, which is exactly what one measured cell did (14 beats,
    every read blank, 1,688 tokens)."""
    return [r for r in (cell.get("reads") or []) if r and len(r.strip()) >= 12]


def _delta(a, b):
    if not a:
        return None
    return (b - a) / float(a)


def main(argv):
    path = argv[0] if argv else "/tmp/prompt_v2_ab_result.json"
    d = json.load(open(path))
    cells = d.get("cells") or []
    ok = [c for c in cells if not c.get("error") and not c.get("no_plan")]
    A = [c for c in ok if c["arm"] == "A"]
    B = [c for c in ok if c["arm"] == "B"]
    deadA = [c for c in cells if c["arm"] == "A" and c not in ok]
    deadB = [c for c in cells if c["arm"] == "B" and c not in ok]

    print(f"  CELLS: {len(cells)} run | usable A={len(A)} B={len(B)} | "
          f"failed A={len(deadA)} B={len(deadB)}")
    if deadB:
        # A dead cell is not a zero. Reporting arm B's totals over a denominator
        # that silently lost cells is the contaminated-window error.
        print(f"  *** arm B lost {len(deadB)} cell(s): "
              f"{[c['source'][:26] for c in deadB]}")
    if not A or not B:
        print("  NOT ENOUGH USABLE CELLS — this is 'not observed', not a result.")
        return 0

    ra, da = _ledger_totals(A)
    rb, db = _ledger_totals(B)
    print(f"\n  {'':26}{'arm A':>10}{'arm B':>10}{'delta':>10}")
    print(f"  {'components requested':26}{ra:>10}{rb:>10}"
          f"{(f'{_delta(ra, rb):+.0%}' if _delta(ra, rb) is not None else 'n/a'):>10}")
    print(f"  {'dropped BY US':26}{da:>10}{db:>10}")
    for f in FAMILIES:
        sa = sum((c.get("counts") or {}).get(f, 0) for c in A)
        sb = sum((c.get("counts") or {}).get(f, 0) for c in B)
        mark = "  <-- WIN CONDITION" if f == "generated_scenes" else ""
        print(f"  {f:26}{sa:>10}{sb:>10}{'':>10}{mark}")

    # THE CEILING IS ON THE EDITORIAL CALL, NOT THE CELL. The pre-registration's
    # 28.0s baseline (3.7-flash, serial, 2048) is the Gemini leg; a plan-only
    # cell also pays transcription, proxy and face extraction, so comparing
    # cell wall against a 36s editorial ceiling compares two different things —
    # the same unit error density_of exists to prevent. Both are printed, and
    # only the editorial leg is judged.
    ea = _p50(c.get("gemini_call_s") for c in A)
    eb = _p50(c.get("gemini_call_s") for c in B)
    wa, wb = _p50(c.get("wall_s") for c in A), _p50(c.get("wall_s") for c in B)
    ta = _p50(c.get("gemini_output_tokens") for c in A)
    tb = _p50(c.get("gemini_output_tokens") for c in B)
    print(f"\n  {'p50 EDITORIAL call_s':26}{str(ea):>10}{str(eb):>10}"
          f"   ceiling {WALL_CEILING_S}s  <-- the judged number")
    print(f"  {'p50 cell wall_s':26}{str(wa):>10}{str(wb):>10}"
          f"   (includes transcribe/proxy/faces — NOT the ceiling)")
    print(f"  {'p50 output tokens':26}{str(ta):>10}{str(tb):>10}")

    # TOKENS PER BEAT WITH A REAL READ. Arm A emits no beats, so this is a
    # within-arm-B efficiency number reported beside the raw total, never a
    # cross-arm ratio pretending the two shapes are comparable.
    print(f"\n  ── arm B shape (arm A emits no beats, so this is B-only) ──")
    tot_beats = sum(c.get("n_beats") or 0 for c in B)
    tot_real = sum(len(_real_reads(c)) for c in B)
    tot_tok = sum(c.get("gemini_output_tokens") or 0 for c in B)
    print(f"     beats total            {tot_beats}")
    print(f"     beats with a real read {tot_real}"
          f"{'' if not tot_beats else f'  ({100.0 * tot_real / tot_beats:.0f}%)'}")
    if tot_real:
        print(f"     output tokens / beat-with-a-real-read  {tot_tok / tot_real:.0f}")
    if tot_beats and tot_real < tot_beats:
        print(f"     {tot_beats - tot_real} beat(s) carried NO real read — they cost "
              f"tokens and bought nothing")

    # ── THE PRE-REGISTERED VERDICT, applied mechanically ────────────────────
    print(f"\n  ── VERDICT (thresholds fixed before the run) ──")
    dr = _delta(ra, rb)
    if dr is None:
        print("     arm A requested 0 components — no ratio is definable.")
    elif abs(dr) < INCONCLUSIVE_BAND:
        print(f"     requested delta {dr:+.0%} is INSIDE the ±30% band. At n={len(B)} "
              f"this is INCONCLUSIVE — reported as a non-result, not a direction.")
    else:
        drop_rate_a = (da / ra) if ra else 0
        drop_rate_b = (db / rb) if rb else 0
        doubled = rb >= 2 * ra
        drops_ok = drop_rate_b <= drop_rate_a * 1.0001 or db <= da
        scenes_b = sum((c.get("counts") or {}).get("generated_scenes", 0) for c in B)
        scenes_a = sum((c.get("counts") or {}).get("generated_scenes", 0) for c in A)
        off_zero = scenes_b > 0 and scenes_a == 0
        print(f"     requested {dr:+.0%}  |  >=2x: {doubled}  |  "
              f"drops did not outpace: {drops_ok}  |  scenes off zero: {off_zero}")
        if doubled and drops_ok and off_zero:
            print("     WIN by the pre-registered condition.")
        else:
            print("     NOT a win by the pre-registered condition — the direction "
                  "is real but at least one clause failed. Report which.")
    if eb and eb > WALL_CEILING_S:
        print(f"     *** arm B p50 EDITORIAL leg {eb}s EXCEEDS the {WALL_CEILING_S}s ceiling "
              f"— the 120s end-to-end law is at risk and the trade must be "
              f"re-argued, not assumed.")
    if ta and tb and tb > ta:
        print(f"     *** arm B costs MORE output tokens ({tb} vs {ta}). The "
              f"pre-registration calls this a RED FLAG, not a cost: it would mean "
              f"the approach is more expensive per call forever.")

    # ── beats[].read VERBATIM, EVERY v2 CELL, win or lose ───────────────────
    print(f"\n  ── beats[].read, VERBATIM, every arm-B cell ──")
    for c in [x for x in cells if x["arm"] == "B"]:
        rs = c.get("reads")
        head = (f"  [{c['source'][:30]}] beats={c.get('n_beats')} "
                f"tok={c.get('gemini_output_tokens')} "
                f"{'FAILED: ' + str(c.get('error') or c.get('result_error')) [:60] if (c.get('error') or c.get('no_plan')) else ''}")
        print(head)
        if not rs:
            print("      (no beats — nothing to read)")
            continue
        for i, r in enumerate(rs):
            print(f"      {i:>3}: {r if r.strip() else '(EMPTY)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
