#!/usr/bin/env python3
"""Every libx264 encode in the agentic path pins its thread count.

THIS IS THE PRECONDITION FOR RE-EDIT, and it does not hold today.

Zac's re-edit requirement is a surgical modification, and the check that decides
whether a re-edit MODIFIES or RE-PLANS is byte-identity: a no-op instruction
must return a byte-identical file. That check rests entirely on renders being
byte-identical on a fixed plan — which this repo established, paid for, and
pinned on 2026-08-01:

    the x264 encode thread count is PINNED (_X264_ENCODE_THREADS=48 in
    handler.py, never x264-auto — auto makes output depend on the machine's
    core count). Renders are byte-identical on a fixed plan across ANY cpu.

THE FIX NEVER REACHED THE AGENTIC PATH. handler.py passes
`-x264-params threads=48` (857). agentic_editor_app.py has THIRTEEN libx264
invocations and passes it NOWHERE — `x264-params` appears zero times, and
`_X264_ENCODE_THREADS` is neither imported nor referenced. So the agentic path
encodes with x264's AUTO thread count, derived from the machine.

WHY THAT IS WORSE HERE THAN IT LOOKS. The function requests `cpu=8`, but this
repo already measured that `os.cpu_count()` inside these containers reports the
HOST's cores — 24, 28 and 48 for arms requesting 8, 16 and 32. So two runs of
the SAME PLAN can land on hosts with different core counts and encode
differently, and nothing would report it: the video looks right, every gate
passes, and only a byte comparison sees it.

WHAT IT COSTS IF NOT FIXED FIRST. The re-edit byte-identity proof would fail for
a reason that has nothing to do with re-edit, intermittently, depending on which
host each run landed on. A check that fails for the wrong reason is a check
reporting a pass it did not earn — or in this case a failure nobody can act on.

INFERENCE, labelled: I have not measured two agentic renders of a fixed plan on
different hosts. The mechanism is established in this repo and the pin is absent;
that is a static finding, not an observed byte difference. Measuring it would
cost Modal spend on a synthetic comparison, which Rule 6 forbids — the honest
order is pin it, then prove byte-identity on real traffic.

RED-proven by red_proof_encode_threads_pinned.py.
"""
import ast
import pathlib
import re
import sys

APP = pathlib.Path("agentic_editor_app.py")
src = APP.read_text()
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


# Every string constant that invokes libx264, with its line. Strings rather than
# argv lists because this file builds ffmpeg commands both ways.
_tree = ast.parse(src)
_enc = []
for _n in ast.walk(_tree):
    if isinstance(_n, ast.Constant) and isinstance(_n.value, str) \
            and "libx264" in _n.value:
        _enc.append((_n.lineno, _n.value))
check(f"the scan finds libx264 encode sites ({len(_enc)}) — non-vacuity",
      len(_enc) >= 5,
      "the matcher found almost nothing; it would forbid nothing")

# An encode is PINNED when the same command carries an explicit x264 thread
# count. Accepted forms: `-x264-params threads=N` in one string, or the flag and
# its value as adjacent argv constants.
_PIN = re.compile(r"x264-params[^\"']*threads=\d+")
_unpinned = []
for _ln, _val in _enc:
    # The command may be split across adjacent constants, so look at a window of
    # the source around the site rather than at the single string. A pin two
    # lines below the -c:v is still a pin.
    _lines = src.split("\n")
    _window = "\n".join(_lines[max(0, _ln - 6):_ln + 8])
    if not _PIN.search(_window):
        _unpinned.append(f"line {_ln}: {_val.strip()[:64]}")

# QUARANTINED WITH AN OWNER AND A DATE, not shipped red. Zac's rule: a red that
# will not be fixed today is fixed, quarantined with an owner and a date, or
# deleted — because a check that is always red stops being read. The 13 sites
# are a BASELINE: this check is GREEN on exactly them and RED on a fourteenth.
# That stops the class growing while the per-site ruling is made, and it is the
# same shape as the `or 0` pin table.
#
# THE RULING EACH SITE NEEDS, and it is not "pin everything". handler.py
# documents a deliberate EXEMPTION: the 480p/18fps Gemini proxy is "analysed
# then discarded, never delivered", so it is exempt from the render determinism
# pin. The test is not whether a site writes out.mp4 — an intermediate like
# cut.mp4 feeds the delivered bytes and is fully determinism-relevant. The test
# is whether the ENCODED BYTES EVER REACH THE DELIVERED FILE.
#
#     DELIVERED or feeding it   -> pin required
#     analysed and discarded    -> exempt, with the reason written down
#
# OWNER: Builder-2. DATE OPENED: 2026-09-09. Blocked on: round 49 running, and
# agentic_editor_app.py is a mounted path.
_BASELINE_UNPINNED = 13

check(f"the unpinned set has not grown beyond the {_BASELINE_UNPINNED} known "
      f"sites (quarantined 2026-09-09, owner Builder-2)",
      len(_unpinned) <= _BASELINE_UNPINNED,
      f"{len(_unpinned)} unpinned, baseline {_BASELINE_UNPINNED} — a NEW "
      f"unpinned encode landed. Every added libx264 site pins threads unless "
      f"its bytes are analysed and discarded, and that exemption is written "
      f"down at the site.")
check("the known-unpinned set is reported, not hidden", True,
      f"{len(_unpinned)} of {len(_enc)} libx264 sites unpinned — OPEN DEFECT, "
      f"see the header. Not a pass; a stated debt.")

check("NOT YET TRUE, tracked: every libx264 encode pins its thread count",
      not _unpinned,
      f"{len(_unpinned)} of {len(_enc)} unpinned:\n         "
      + "\n         ".join(_unpinned[:14])
      + (f"\n         ... showing {min(14, len(_unpinned))} of "
         f"{len(_unpinned)}" if len(_unpinned) > 14 else "")
      + "\n         x264-auto derives its thread count from the machine, so the "
        "same plan encodes differently on different hosts. Byte-identity is the "
        "cert bar and re-edit's whole proof rests on it.")

check("the pin uses x264-params, not ffmpeg's -threads",
      "-threads" not in src or "x264-params" in src,
      "handler.py's comment is explicit that the deploy gate requires "
      "`-x264-params threads=N`, not ffmpeg's -threads, which does something "
      "else")

# The quarantined leg is reported but does not fail the run, and it is named
# in the summary either way so it cannot be forgotten. Everything else fails.
_open_debt = [f for f in fails if f.startswith("NOT YET TRUE")]
fails = [f for f in fails if not f.startswith("NOT YET TRUE")]

print()
for _d in _open_debt:
    print("  OPEN DEBT: " + _d.split("  :: ")[0])
if fails:
    print("ENCODE-THREADS-PINNED: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print(f"ENCODE-THREADS-PINNED: PASS — {len(_enc)} libx264 site(s), "
      f"{len(_unpinned)} unpinned and QUARANTINED at baseline "
      f"{_BASELINE_UNPINNED} (owner Builder-2, opened 2026-09-09). "
      f"A fourteenth fails this check.")
