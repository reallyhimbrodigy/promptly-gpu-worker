"""CERT — the seam-candidate widening A/B arm (RULE-1).

SHIPS DARK: _SEAM_WIDE_SPLIT = 0.0 puts nobody in the wide arm, so this is
inert until Zac's GO changes one constant.

WHAT MUST HOLD, and why each leg exists:
  DARK        — at split 0.0 every job is narrow. A cohort that is live before
                its GO is the "built-not-wired" class inverted.
  DETERMINISM — a retry must land in the SAME arm; a job that flips between
                attempts pollutes both arms.
  DECORRELATION — the salt. The lean A/B hashes the bare job_id; hashing it
                again here would put every job on the same side of BOTH
                experiments, making neither effect separable. This is the leg
                most likely to be broken by a well-meaning simplification.
  OVERRIDE    — an explicit env flag wins, so the kill switch works and a cert
                can force an arm.
  PERSISTED   — the arm reaches stage_timings. An A/B whose arm is not
                persisted is not an A/B (precedent: _lang_bundle 0/3000).

Offline. Zero network, zero Modal, zero Gemini.
"""
import os
import sys

import handler as H

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"\n       :: {detail}" if detail else ""))


IDS = [f"job-{i:05d}-aaaa-bbbb-cccc-dddddddddddd" for i in range(4000)]


def arm_for(jid, split):
    _old_split, _old_jid = H._SEAM_WIDE_SPLIT, H._ACTIVE_JOB_ID
    H._SEAM_WIDE_SPLIT = split
    H._ACTIVE_JOB_ID = jid
    try:
        return H._seam_wide_arm()
    finally:
        H._SEAM_WIDE_SPLIT, H._ACTIVE_JOB_ID = _old_split, _old_jid


print("=== C1: SHIPS DARK ===")
check("_SEAM_WIDE_SPLIT is 0.0", H._SEAM_WIDE_SPLIT == 0.0,
      f"got {H._SEAM_WIDE_SPLIT} — the cohort is LIVE before its GO")
_dark = [arm_for(j, 0.0) for j in IDS[:500]]
check("at split 0.0 every job is narrow", set(_dark) == {"narrow"},
      f"got {set(_dark)}")

print("\n=== C2: DETERMINISM — a retry lands in the same arm ===")
_a = [arm_for(j, 0.5) for j in IDS[:300]]
_b = [arm_for(j, 0.5) for j in IDS[:300]]
check("same job_id -> same arm across calls", _a == _b)
check("no job_id -> narrow (off-job paths unaffected)",
      arm_for("", 1.0) == "narrow")

print("\n=== C3: THE SPLIT IS THE SPLIT ===")
for split, lo, hi in ((0.5, 0.45, 0.55), (0.2, 0.16, 0.24), (1.0, 1.0, 1.0)):
    frac = sum(1 for j in IDS if arm_for(j, split) == "wide") / len(IDS)
    check(f"split {split} -> observed {frac:.3f} in [{lo}, {hi}]",
          lo <= frac <= hi, f"got {frac:.3f}")

print("\n=== C4: DECORRELATION from the lean A/B (the salt) ===")
# If the two arms shared a hash, agreement would be ~100%. Independent arms
# agree ~50% of the time. This is the leg a "simplification" would break.
def lean_for(jid):
    _o = H._ACTIVE_JOB_ID
    H._ACTIVE_JOB_ID = jid
    try:
        return H._lean_ab_arm()
    finally:
        H._ACTIVE_JOB_ID = _o

_agree = sum(1 for j in IDS
             if (arm_for(j, 0.5) == "wide") == (lean_for(j) == "lean"))
_frac = _agree / len(IDS)
check(f"seam and lean arms are INDEPENDENT (agreement {_frac:.3f} ~ 0.5)",
      0.44 <= _frac <= 0.56,
      f"agreement {_frac:.3f} — the arms are correlated; neither effect is "
      f"separable from the other")
check("the salt is present in the source",
      '"seamwide:"' in open(H.__file__.replace(".pyc", ".py"), encoding="utf-8").read(),
      "the decorrelating salt is gone")

print("\n=== C5: the env override wins (kill switch + cert forcing) ===")
_o = os.environ.get("PROMPTLY_SEAM_CANDIDATES")
try:
    os.environ["PROMPTLY_SEAM_CANDIDATES"] = "wide"
    check("env=wide forces wide even at split 0.0", H._seam_candidates_wide() is True)
    os.environ["PROMPTLY_SEAM_CANDIDATES"] = "narrow"
    check("env=narrow forces narrow", H._seam_candidates_wide() is False)
    os.environ.pop("PROMPTLY_SEAM_CANDIDATES", None)
    check("unset -> the A/B decides (dark => False)",
          H._seam_candidates_wide() is False)
finally:
    if _o is None:
        os.environ.pop("PROMPTLY_SEAM_CANDIDATES", None)
    else:
        os.environ["PROMPTLY_SEAM_CANDIDATES"] = _o

print("\n=== C6: the arm is PERSISTED where the analysis can read it ===")
_src = open(H.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
check('"seam_arm" is written into stage_timings', '"seam_arm": _seam_wide_arm()' in _src)
check('"seam_wide_on" is written too', '"seam_wide_on"' in _src)
_i_st = _src.find('"stage_timings"')
_i_arm = _src.find('"seam_arm"')
check("seam_arm is NESTED (content-studio strips unknown top-level keys)",
      _i_arm > 0 and _i_st > 0,
      "seam_arm sits outside stage_timings and would be stripped")

print("\n=== C7: the gate actually consumes the arm ===")
check("_seam_candidates_wide() is what the candidate gate reads",
      "_wide = _seam_candidates_wide()" in _src,
      "the gate still reads the raw env — the arm is decorative")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
