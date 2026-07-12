"""FINDING 3 — the VISUAL REFRACTORY PERIOD (Zac 2026-07-12). Two hard visual
moves (zooms) landing within the refractory window in OUTPUT time fight each
other and read as a glitch. The lower arc-ranked beat DOWNGRADES (loses its
zoom, rides caption/sound); the higher-ranked keeps it. Structural, signed,
tunable. Rebuilds the min-zoom-spacing deleted 2026-07-09 — but rank-based, so
it downgrades the WEAKER beat, never blunt-drops the payoff. Offline."""
import copy
import sys

import handler as H

PASS = []
FAIL = []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   :: {detail}" if (detail and not cond) else ""))

for _fn in ("_source_t_to_output_t", "_zoom_refractory_rank", "_enforce_zoom_refractory",
            "_VISUAL_REFRACTORY_S"):
    if not hasattr(H, _fn):
        print(f"  FAIL  {_fn} not implemented yet (RED)")
        print("\n=== RESULT: 0 passed, 1 failed ===")
        sys.exit(1)

# ─── output-time projection (speed 1.0): a cut between two beats tightens them ─
CUTS = [{"source_start": 0.0, "source_end": 10.0},
        {"source_start": 12.0, "source_end": 20.0}]   # 2s removed at 10-12
check("output time within first clip == source", abs(H._source_t_to_output_t(5.0, CUTS) - 5.0) < 1e-6)
check("output time after a cut subtracts removed span",
      abs(H._source_t_to_output_t(15.0, CUTS) - 13.0) < 1e-6, H._source_t_to_output_t(15.0, CUTS))

# ─── the threshold is a single tunable constant ─────────────────────────────
check("refractory threshold is 2.0s (tunable constant)", abs(H._VISUAL_REFRACTORY_S - 2.0) < 1e-9)

# ─── rank: committed push (payoff) outranks a snap at equal intensity ────────
_snap = {"intensity": "high", "zoom_effect": {"type": "SnapReframe"}}
_push = {"intensity": "high", "zoom_effect": {"type": "SmoothPush"}}
_med = {"intensity": "medium", "zoom_effect": {"type": "SmoothPush"}}
check("committed push outranks snap at equal intensity",
      H._zoom_refractory_rank(_push) > H._zoom_refractory_rank(_snap))
check("high intensity outranks medium",
      H._zoom_refractory_rank(_snap) > H._zoom_refractory_rank(_med))

# ─── THE GLITCH: @74 SnapReframe (17.4s) + @78 SmoothPush (18.3s), ~0.9s apart ─
# The payoff push @78 keeps its zoom; the mid-peak snap @74 downgrades.
def zoom_moment(t, ztype, intensity, word):
    return {"t": t, "word": word, "intensity": intensity, "zoom_effect": {"type": ztype}}

ems = [zoom_moment(17.4, "SnapReframe", "high", "word74"),
       zoom_moment(18.3, "SmoothPush", "high", "word78")]
cuts_flat = [{"source_start": 0.0, "source_end": 30.0}]   # no cuts → source==output
recs = H._enforce_zoom_refractory(ems, cuts_flat, H._VISUAL_REFRACTORY_S)
check("the mid-peak snap @74 DOWNGRADES (loses its zoom)", ems[0]["zoom_effect"] is None, ems[0])
check("the payoff push @78 KEEPS its zoom", ems[1]["zoom_effect"] is not None, ems[1])
check("exactly one downgrade recorded", len(recs) == 1, recs)
check("the downgrade record is signed (ranks + spacing + why)",
      recs and all(k in recs[0] for k in ("downgraded_word", "kept_word", "gap_s")), recs)
check("the record names the correct downgraded beat",
      recs and recs[0]["downgraded_word"] == "word74" and recs[0]["kept_word"] == "word78", recs)

# ─── beats spaced ≥ threshold are BOTH kept (no false downgrade) ─────────────
ems2 = [zoom_moment(5.0, "SnapReframe", "high", "a"),
        zoom_moment(9.0, "SmoothPush", "high", "b")]   # 4s apart
recs2 = H._enforce_zoom_refractory(ems2, cuts_flat, H._VISUAL_REFRACTORY_S)
check("beats ≥2s apart: both keep their zoom", ems2[0]["zoom_effect"] and ems2[1]["zoom_effect"])
check("no downgrade when well-spaced", recs2 == [])

# ─── a CUT between two beats can tighten them into conflict (output-time) ─────
# source 8.0 and 12.5 are 4.5s apart in SOURCE, but a 4s cut (9-13) puts them
# ~0.5s apart in OUTPUT → conflict.
ems3 = [zoom_moment(8.0, "SnapReframe", "high", "x"),
        zoom_moment(13.5, "SmoothPush", "high", "y")]
cuts3 = [{"source_start": 0.0, "source_end": 9.0}, {"source_start": 13.0, "source_end": 20.0}]
recs3 = H._enforce_zoom_refractory(ems3, cuts3, H._VISUAL_REFRACTORY_S)
check("output-time (not source) drives the refractory: cut-tightened pair conflicts",
      ems3[0]["zoom_effect"] is None and ems3[1]["zoom_effect"] is not None, {"recs": recs3})

# ─── idempotence: re-running changes nothing (already resolved) ─────────────
before = copy.deepcopy(ems)
recs_again = H._enforce_zoom_refractory(ems, cuts_flat, H._VISUAL_REFRACTORY_S)
check("refractory is idempotent (a re-run downgrades nothing more)",
      ems == before and recs_again == [], recs_again)

print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
print("ALL VISUAL-REFRACTORY CASES PASS")
