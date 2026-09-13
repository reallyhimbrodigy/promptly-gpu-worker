#!/usr/bin/env python3
"""SMOKE — a protected position can be BURIED as well as cut.

THE CLASS NOBODY HAD NAMED. Every rule about the hook protected it from being
REMOVED. The ChatCut arm obeyed that perfectly — every word survived — and then
opened the edit on 1.7s of a dark title card, so the viewer met something that
was not the hook first. Same loss, different route. A rule that names one route
to a loss quietly teaches that the other routes are fine.

TWO LEGS, because the wording and the behaviour fail independently: the
sentence can be edited out of the craft, and the checker can stop
discriminating. Neither failure is visible from the other.
"""
import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location("onb", "opening_not_buried.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

fails = []


def check(what, ok, detail=""):
    if not ok:
        fails.append(what + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if ok else 'FAIL'}] {what}"
          + (f"\n         {detail}" if not ok and detail else ""))


# ── 1. THE WORDING, IN BOTH LANES ───────────────────────────────────────────
# The ChatCut path reads the craft DOCUMENT; the ffmpeg path reads the schema
# field. The rule has to be in both or one lane silently keeps the gap.
doc = open("knowledge/01_cut_pass.md", encoding="utf-8").read()
check("the craft document says a protected position can be BURIED",
      "BURIED AS WELL AS CUT" in doc.upper())
check("and names the concrete route — nothing in FRONT of the hook",
      "in front of" in doc.lower() and "hook" in doc.lower())

app = open("agentic_editor_app.py", encoding="utf-8").read()
check("the ruling field carries the same rule",
      "BURIED AS WELL AS CUT" in app.upper())

# ── 2. THE CHECKER STILL DISCRIMINATES ──────────────────────────────────────
# A checker that flags nothing is indistinguishable from one switched off, so
# drive it on the two REAL renders: one that buried the hook and one that did
# not. Skipped with a named ABSENT if the files are not on this machine —
# never silently passed.
D = os.path.expanduser("~/Desktop/Promptly Reports/chatcut-spike")
src = os.path.join(D, "SOURCE-original-25s.mp4")
bad = os.path.join(D, "batched-loop-edit.mp4")
good = os.path.join(D, "e2e-agent-edit.mp4")
if not all(os.path.exists(p) for p in (src, bad, good)):
    print("  [ABSENT] the reference renders are not on this machine — the "
          "discrimination legs did not run, which is not the same as passing")
else:
    st_bad, why_bad = M.opening_state(src, bad)
    st_good, _ = M.opening_state(src, good)
    check("it reports BURIED on the run that opened on a dark card",
          st_bad == "BURIED", f"{st_bad}: {why_bad[:90]}")
    check("and MEASURED on the run that opened on the hook",
          st_good == "MEASURED", st_good)
    check("the refusal says WHY in the viewer's terms, not just a number",
          "not the hook" in why_bad)

# ── 3. A DARK SOURCE IS NOT A BURIED HOOK ───────────────────────────────────
# The trap this check must avoid: a legitimately dark opening would be flagged
# by an absolute floor alone, which is the corpus-gate failure — a threshold
# that learns one population and rejects real footage.
if os.path.exists(bad):
    st_self, _ = M.opening_state(bad, bad)
    check("a clip compared against ITSELF is never BURIED — the rule is "
          "relative to the source, not an absolute floor", st_self != "BURIED",
          st_self)

check("an unreadable input is ABSENT, never clean",
      M.opening_state("/nope.mp4", "/nope.mp4")[0] == "ABSENT")

if fails:
    print("OPENING-NOT-BURIED: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("OPENING-NOT-BURIED: PASS — the rule is in both lanes and the checker "
      "still tells a buried hook from a dark source")
