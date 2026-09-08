#!/usr/bin/env python3
"""SMOKE: the ruling diff separates the record from restatement.

WHY. rule_all_beats is 66-80% of a run's output and ran 5 times for ~45s of
model time. A whole-payload hash said "5 distinct payloads", which proves they
are not byte-identical and NOTHING about how much is new information: a payload
restating 20 beats while rewording one `why` hashes as distinct. This is the
instrument that decides whether ~45s is the ruling record or a restatement of
it, so it has to be right about exactly that distinction.

WHAT MAKES IT FIRE:
  - a WHY-only rewrite counted as a decision change. Then restatement reads as
    new information and the 45s looks unavoidable.
  - a partial re-call scored against the beats it omits. The tool's own
    description invites one ("call again with only those"), so a diff that
    assumed full payloads would score a 3-beat follow-up as 18 deletions.
"""
import sys, types

_m = types.ModuleType("modal")
class _S:
    def __init__(s,*a,**k): pass
    def __getattr__(s,n): return _S()
    def __call__(s,*a,**k): return _S()
    def function(s,*a,**k): return lambda f: f
    def local_entrypoint(s,*a,**k): return lambda f: f
for _n in ("App","Image","Secret","Volume","Cls","Function"): setattr(_m,_n,_S())
_m.is_local=lambda: True; _m.enable_output=_S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A

fails=[]
def ok(label, cond, detail=""):
    if not cond: fails.append(label + (f"  :: {detail}" if detail else ""))

def call(*verdicts):
    return A.ruling_fingerprint({"verdicts": list(verdicts)})

B0 = {"beat": 0, "treatment": ["zoom"], "cut": "keep", "why": "the hook lands"}
B1 = {"beat": 1, "treatment": ["text"], "cut": "keep", "why": "names the number",
      "text_content": "62 FOLLOWERS"}

# ── identical re-emission ────────────────────────────────────────────────
st = {}
c1, st = A.diff_rulings(st, call(B0, B1))
ok("first call is all NEW", c1["new"] == 2 and c1["identical"] == 0, str(c1))
c2, st = A.diff_rulings(st, call(B0, B1))
ok("an identical re-call is IDENTICAL, not changed",
   c2["identical"] == 2 and c2["decision_changed"] == 0 and c2["why_only"] == 0, str(c2))

# ── WHY-ONLY rewrite: the category the coarse hash could not see ─────────
B0w = dict(B0, why="the hook lands on the number, and it is the strongest beat")
c3, st = A.diff_rulings(st, call(B0w, B1))
ok("a rewritten WHY with an unchanged decision is WHY-ONLY",
   c3["why_only"] == 1 and c3["decision_changed"] == 0,
   f"{c3} — counting a rationale rewrite as a decision change makes restatement "
   "read as new information, and the 45s look unavoidable")

# ── a real decision change ───────────────────────────────────────────────
B1d = dict(B1, treatment=["text", "zoom"])
c4, st = A.diff_rulings(st, call(B0w, B1d))
ok("a changed treatment is DECISION-CHANGED",
   c4["decision_changed"] == 1 and c4["identical"] == 1, str(c4))
B1c = dict(B1d, cut="cut")
c5, st = A.diff_rulings(st, call(B1c))
ok("a changed cut is DECISION-CHANGED", c5["decision_changed"] == 1, str(c5))
B1t = dict(B1c, text_content="I MADE $400")
c6, st = A.diff_rulings(st, call(B1t))
ok("changed on-screen copy is DECISION-CHANGED", c6["decision_changed"] == 1, str(c6))

# ── PARTIAL re-call must not be scored against omitted beats ─────────────
c7, st = A.diff_rulings(st, call(B0w))
ok("a partial re-call counts only the beats it carries",
   c7["beats"] == 1 and c7["identical"] == 1,
   f"{c7} — the tool tells the agent to 'call again with only those', so a "
   "partial call is normal and must not be scored against what it omits")

# ── a genuinely new beat ─────────────────────────────────────────────────
c8, st = A.diff_rulings(st, call({"beat": 7, "treatment": ["sfx"], "cut": "keep",
                                  "why": "the close needs a hit"}))
ok("an unseen beat is NEW", c8["new"] == 1, str(c8))

# ── malformed entries must not crash or invent beats ─────────────────────
ok("a verdict with no beat is skipped",
   A.ruling_fingerprint({"verdicts": [{"treatment": ["zoom"]}]}) == {})
ok("a non-dict verdict is skipped",
   A.ruling_fingerprint({"verdicts": ["nonsense", None]}) == {})
ok("an absent verdicts key is empty, not an error",
   A.ruling_fingerprint({}) == {})

# ── `why` must NOT be in the decision fields ─────────────────────────────
ok("why is not a decision field", "why" not in A.RULING_DECISION_FIELDS,
   "with why in the decision signature every rationale rewrite scores as a "
   "decision change and the two categories collapse into one")

if fails:
    print(f"RULING-DIFF: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print("RULING-DIFF: PASS (11 behaviours driven, incl. why-only and partial re-calls)")
