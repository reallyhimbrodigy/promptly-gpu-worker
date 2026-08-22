#!/usr/bin/env python3
"""cert_ledger_survives_asr.py — THE COMPONENT LEDGER MUST SURVIVE THE JOB.

MEASURED 2026-08-22 on the post-flip cohort: 22 of 70 editorial jobs shipped
with NO component_ledger, and they were the SLOW ones —

    with ledger    n=48  p50 render 153.7s  max 396.2s
    WITHOUT        n=22  p50 render 247.7s  max 750.7s   (1.61x)

— holding the ENTIRE p95 tail (e4750766 751s, 40c3ddc5 632s, c193e0a8 598s).
The render-cost hypothesis could therefore only be tested on the fast half.

ROOT: `_component_ledger_reset()` was called inside `_asr_diag_set()`, OUTSIDE
its `if not _ASR_DIAG:` guard. That setter runs repeatedly during a job, so any
ASR diagnostic update landing after `_ledger_absorb_plan` erased the record and
`_component_ledger_snapshot()` wrote `{}`. A slow job is exactly the job that
picks up a late level re-measure or language re-route — so the instrument was
erased by the jobs it most needed to describe.

  1  A ledger populated from a plan SURVIVES an _asr_diag_set call. This is the
     defect, stated directly.
  2  The reset still happens ONCE PER JOB — a ledger that never resets is worse
     than one that resets too often: it would attribute job A's components to
     job B in a warm container.
  3  _asr_diag_set still does its own job (ASR fields land).
  4  The accessor returns MISSING, not 0, for an uninstrumented job. A reader
     that cannot tell "absent" from "zero" manufactures confident zeros — the
     shape of all five wrong-key reader bugs this campaign.
  5  ledger_totals sums the PER-KIND `requested`, since there is no top-level
     one; a reader that looks for it scores every job 0.

    python3 cert_ledger_survives_asr.py
"""
import os
import sys

os.environ.setdefault("APP_URL", "")


def main():
    import handler as H
    from promptly_read import ledger_totals, component_ledger, MISSING
    fails = []

    PLAN = {
        "motion_graphics": [{"type": "StatCard"}, {"type": "PillCluster"}],
        "text_overlays": [{"x": 1}],
        "emphasis_moments": [{"a": 1}, {"a": 2}, {"a": 3}],
        "broll_clips": [],
    }

    # ── 1: the ledger survives an ASR update ────────────────────────────────
    H._component_ledger_reset()
    H._ledger_absorb_plan(PLAN)
    before = H._component_ledger_snapshot()
    n_before = sum(v.get("requested", 0) for v in before.values())
    H._asr_diag_set(level_status="measured", mean_dbfs=-26.8)
    after = H._component_ledger_snapshot()
    n_after = sum(v.get("requested", 0) for v in after.values())
    print(f"  [1] requested before _asr_diag_set={n_before}  after={n_after}")
    if n_before == 0:
        fails.append("the fixture never populated the ledger — clause 1 proves "
                     "nothing (check _ledger_absorb_plan's key names)")
    if n_after != n_before:
        fails.append(f"_asr_diag_set WIPED the ledger ({n_before} -> {n_after}) "
                     f"— this is the original defect: the slowest jobs ship "
                     f"uninstrumented because they pick up late ASR updates")

    # a SECOND set must not erase it either
    H._asr_diag_set(language="en")
    n_after2 = sum(v.get("requested", 0) for v in H._component_ledger_snapshot().values())
    print(f"      after a second _asr_diag_set={n_after2}")
    if n_after2 != n_before:
        fails.append(f"a second _asr_diag_set wiped the ledger ({n_after2})")

    # ── 3: _asr_diag_set still does its own job ─────────────────────────────
    snap = H._asr_diag_snapshot()
    print(f"  [3] asr fields still land: level_status="
          f"{snap.get('level_status')!r} language={snap.get('language')!r}")
    if snap.get("level_status") != "measured":
        fails.append("_asr_diag_set no longer records ASR fields — the fix broke "
                     "the function it was removed from")

    # ── 2: the reset still exists and is per-job ────────────────────────────
    H._component_ledger_reset()
    n_reset = sum(v.get("requested", 0) for v in H._component_ledger_snapshot().values())
    print(f"  [2] after an explicit reset={n_reset} (must be 0)")
    if n_reset != 0:
        fails.append("the ledger no longer resets — in a warm container job B "
                     "would inherit job A's components")
    raw = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "handler.py"), encoding="utf-8").read()
    import re
    # STRIP COMMENTS FIRST. The first cut of this clause matched
    # `_component_ledger_reset()` inside the COMMENT that explains why the call
    # was removed — a self-inflicted instance of the exact defect
    # validate_deploy's own meta-check exists for: a short token proves nothing
    # about CODE because it also appears in prose. Assert on code only.
    src = "\n".join(re.sub(r"#.*$", "", ln) for ln in raw.splitlines())
    in_setter = re.search(
        r"def _asr_diag_set\(\*\*kw\):(?:(?!\ndef ).)*?_component_ledger_reset\(\)",
        src, re.S)
    at_entry = "_component_ledger_reset()" in src.split("del _GEMINI_CALL_LOG[:]")[-1][:900]
    print(f"      reset inside _asr_diag_set: {bool(in_setter)} (must be False); "
          f"at handler entry: {at_entry} (must be True)")
    if in_setter:
        fails.append("_component_ledger_reset is back inside _asr_diag_set — "
                     "every ASR update will erase the ledger again")
    if not at_entry:
        fails.append("no _component_ledger_reset at handler entry — a warm "
                     "container would carry the previous job's ledger forward")

    # ── 4 + 5: the accessor distinguishes ABSENT from ZERO ──────────────────
    absent = component_ledger({"result": {}})
    zeroed = component_ledger({"result": {"component_ledger":
                                          {"text_overlays": {"requested": 0,
                                                             "survived_derived": 0}}}})
    print(f"  [4] uninstrumented job -> {absent!r}   instrumented-but-zero -> "
          f"{type(zeroed).__name__}")
    if absent is not MISSING:
        fails.append(f"an uninstrumented job read as {absent!r} instead of "
                     f"MISSING — it would be counted as a job with zero "
                     f"components, which is how the fast-half bias got in")
    if zeroed is MISSING:
        fails.append("a real ledger of all zeros read as MISSING — the opposite "
                     "error, and it would drop honest zeros from the denominator")

    tot = ledger_totals({"result": {"component_ledger": {
        "motion_graphics": {"requested": 2, "survived_derived": 2},
        "text_overlays": {"requested": 1, "survived_derived": 1}}}})
    print(f"  [5] ledger_totals -> {tot}")
    if tot is MISSING or tot[0] != 3 or tot[1] != 3:
        fails.append(f"ledger_totals returned {tot} for 3 requested — it is not "
                     f"summing the PER-KIND requested, which scores every job 0")
    if ledger_totals({"result": {}}) is not MISSING:
        fails.append("ledger_totals invented a number for an uninstrumented job")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT LEDGER-SURVIVES-ASR: FAIL")
        return 1
    print("  CERT LEDGER-SURVIVES-ASR: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
