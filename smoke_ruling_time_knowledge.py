#!/usr/bin/env python3
"""SMOKE: the editorial standard is IN the prefix, not behind a call nobody makes.

read_knowledge is OFFERED to Sonnet and called ZERO times in every round. A
surface the agent never opens cannot carry the standard, and this lane's own law
is that a preference is not a property.

WHICH DOCUMENTS, and why only four. All 14 are 48,033 tokens — too large whole.
The distribution is the finding: the documents that are purely RULING-TIME
JUDGEMENT are the smallest four.

    02_intent_standard              362 tok
    09_seam_treatments              213
    13_placement_findings           923
    14_card_text_placement_rules  1,288
                                  2,786 estimated / 2,286 measured

The large ones are catalogues and recipes — 05_motion_graphics (9,168) is the
component catalogue, 11_thumbnail a different product surface. A derivation reads
a catalogue; an agent mid-ruling does not. They stay behind read_knowledge, which
is the right mechanism for lookup.

AND THE SKILLS ARE NOT HERE ON PURPOSE. 952.9 KB / ~243,900 tokens, 93% Remotion
API documentation for authoring a component. Correctly on disk, correctly unread
at ruling time — a different thing from the knowledge gap, which the wiring audit
originally filed as one row and got wrong.

THE HONEST CAVEAT: rounds 12-13 measured Haiku spending NINE turns on
read_knowledge and reaching a BYTE-IDENTICAL cut to Sonnet, which read nothing.
That is evidence reading changed nothing — on a measurement of the CUT, which did
not look at placement. These four documents are about placement.
"""
import ast
import pathlib
import sys
import types

_m = types.ModuleType("modal")


class _S:
    def __init__(s, *a, **k): pass
    def __getattr__(s, n): return _S()
    def __call__(s, *a, **k): return _S()
    def function(s, *a, **k): return lambda f: f
    def local_entrypoint(s, *a, **k): return lambda f: f


for _n in ("App", "Image", "Secret", "Volume", "Cls", "Function"):
    setattr(_m, _n, _S())
_m.is_local = lambda: True
_m.enable_output = _S()
sys.modules.setdefault("modal", _m)
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


src = pathlib.Path(A.__file__).read_text()
tree = ast.parse(src)
BLOCK = A.ruling_time_knowledge()

# ── 1. THE FOUR DOCUMENTS, AND ONLY THOSE ───────────────────────────────────
# SIX, since 2026-09-10: the four judgement documents plus the two craft
# reports (the standard, then the wider field — order is load-bearing and each
# file also states its own precedence). Zac's call; the cost was MEASURED, not
# estimated: +4,690 tokens per distinct prefix on round 52 (turn-1
# cache_write + cache_read against the recorded round-51 baseline).
check("exactly six documents are selected", len(A._RULING_TIME_DOCS) == 6,
      str(A._RULING_TIME_DOCS))
check("the standard is selected before the wider field",
      A._RULING_TIME_DOCS.index("16_craft_the_standard.md")
      < A._RULING_TIME_DOCS.index("17_craft_the_wider_field.md")
      if {"16_craft_the_standard.md", "17_craft_the_wider_field.md"}
      <= set(A._RULING_TIME_DOCS) else False,
      str(A._RULING_TIME_DOCS))
for _d in ("02_intent_standard.md", "13_placement_findings.md",
           "14_card_text_placement_rules.md"):
    check(f"{_d} is included", _d in A._RULING_TIME_DOCS)
# The catalogues stay OUT. A derivation reads a catalogue; an agent mid-ruling
# does not, and 05_motion_graphics alone is 9,168 tokens — 4x the whole block.
for _d in ("05_motion_graphics.md", "15_ffmpeg_placement_recipes.md",
           "11_thumbnail.md", "01_cut_pass.md"):
    check(f"{_d} stays on disk", _d not in A._RULING_TIME_DOCS,
          "a catalogue in the prefix is 9,168 tokens of lookup material on "
          "every run")

# ── 2. IT CARRIES THE STANDARD, NOT A SUMMARY OF IT ─────────────────────────
check("the intent standard's actual question is present",
      "name what it does for the viewer" in BLOCK,
      "a paraphrase is the style-guide mistake — prose describing craft is what "
      "already failed")
check("the placement findings are present",
      "PLACEMENT FINDINGS" in BLOCK or "speaker OFF-SCREEN" in BLOCK)
check("the FITS/FIGHTS rules are present",
      "FITS" in BLOCK or "FIGHTS" in BLOCK)

# ── 3. ABSENCE IS SPOKEN ────────────────────────────────────────────────────
# The same rule the reference retrieval follows: a missing document says so
# rather than silently shrinking the block, because an absence that reads as
# nothing-to-say is a judgement nobody made.
# BEHAVIOURAL. Asking whether the phrase appears in the SOURCE passes against a
# mutant that moves it into a dead branch — the string survives, the behaviour
# does not. Twentieth instance of that trap in this lane, so these call the
# function against real directories instead.
import os as _os                                                  # noqa: E402
import tempfile as _tf                                            # noqa: E402
_d1 = _tf.mkdtemp()
with open(_os.path.join(_d1, "02_intent_standard.md"), "w") as _fh:
    _fh.write("name what it does for the viewer at that instant")
_partial = A.ruling_time_knowledge(dirs=[_d1])
check("a missing document is NAMED, not silently dropped",
      "MISSING and not read" in _partial
      and "13_placement_findings.md" in _partial, _partial[:160])
check("and the block says the standard is incomplete rather than smaller",
      "a gap, not a smaller standard" in _partial, _partial[:200])
check("the document that IS present still comes through",
      "name what it does for the viewer" in _partial)
_none = A.ruling_time_knowledge(dirs=[_tf.mkdtemp()])
check("a total failure says UNAVAILABLE, never an empty string",
      "UNAVAILABLE" in _none and len(_none) > 40, repr(_none[:80]))

# ── 4. IT REACHES THE PREFIX, WHICH IS THE CACHED BLOCK ─────────────────────
check("ruling_time_knowledge is CALLED into the system block",
      "+ ruling_time_knowledge()" in src,
      "a document nothing injects is read_knowledge again")
_sys_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Name)
              and n.func.id == "ruling_time_knowledge"]
check("asserted on the CALL, not on a mention", len(_sys_calls) >= 1)

# ── 5. THE BUDGET, WHICH IS A STANDING COST ─────────────────────────────────
# CEILING RAISED WITH THE DOCUMENTS, NOT REMOVED. The old 3,500 guarded prefix
# bloat; the two craft reports were an approved +4,690 measured. 8,000 on this
# estimator (chars/4, which reads ~7,300 today) leaves room for a document
# edit and none for a seventh document nobody approved.
check("the block is under 8,000 tokens", len(BLOCK) // 4 < 8000,
      f"{len(BLOCK)//4} tokens — it rides the cached prefix on every run")
check("and is not trivially small either", len(BLOCK) // 4 > 800,
      f"{len(BLOCK)//4} — if the documents stopped loading this would be the "
      f"only sign")

# ── 6. THE REMOVAL SWITCH — DEFAULT ON, REMOVAL ONLY ────────────────────────
# The registered follow-up is one removal at a time. Without a switch each
# removal is a code change and a freeze cycle; with one it is an env var.
#
# DEFAULT ON is the whole safety property: this repo has NINE features that
# shipped dark on an unset flag, and a switch that only SUBTRACTS from the
# shipped default cannot join them.
_saved = _os.environ.pop("PROMPTLY_DISABLE_RULING_TIME_KNOWLEDGE", None)
check("unset means ON — an unset flag can never ship a darker prefix",
      A.prefix_material_enabled("ruling_time_knowledge") is True)
_os.environ["PROMPTLY_DISABLE_RULING_TIME_KNOWLEDGE"] = "0"
check("only the literal '1' disables it",
      A.prefix_material_enabled("ruling_time_knowledge") is True,
      "'0', 'false' and 'no' must not read as a removal")
_os.environ["PROMPTLY_DISABLE_RULING_TIME_KNOWLEDGE"] = "1"
check("an explicit 1 removes it", not A.prefix_material_enabled("ruling_time_knowledge"))
_removed = A.ruling_time_knowledge()
check("and a removal SAYS it is deliberate, not a missing document",
      "REMOVED for this run" in _removed and "not a missing document" in _removed,
      "a removal that looks like an absence corrupts the next reader's "
      "diagnosis — the two are different findings")
if _saved is None:
    _os.environ.pop("PROMPTLY_DISABLE_RULING_TIME_KNOWLEDGE", None)
else:
    _os.environ["PROMPTLY_DISABLE_RULING_TIME_KNOWLEDGE"] = _saved
check("the state is PRINTED both ways", '"  PREFIX MATERIAL : "' in src,
      "a removal nobody can see in the log is a round whose prefix nobody can "
      "reconstruct")

if fails:
    print(f"RULING-TIME-KNOWLEDGE: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print(f"RULING-TIME-KNOWLEDGE: PASS — {len(A._RULING_TIME_DOCS)} documents, ~{len(BLOCK)//4} tokens in "
      f"the cached prefix; catalogues and skills stay on disk")
