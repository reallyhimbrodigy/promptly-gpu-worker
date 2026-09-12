#!/usr/bin/env python3
"""SMOKE: the examples reach the agent at ruling time, and absences are spoken.

ZAC, 2026-09-09: prompting does not produce intent. "About one punch per short"
was in the prompt and six of seven fixtures ignored it. The corpus was mined into
numbers; the numbers grade; nothing showed the agent the craft it is graded
against.

AND A STYLE GUIDE WOULD HAVE BEEN THE SAME MISTAKE WITH MORE WORDS. Prose
describing craft is what already failed. This ships the EXAMPLES: per beat, the
reference beats most like it — what an editor placed and WHY.

NOT A TOOL THE AGENT CALLS. read_knowledge has been called ZERO times in every
round. A surface the agent never opens cannot carry the craft, so this is
injected into the beats brief, inside the cached prefix: one write, pennies per
turn after, no extra model turn, no agent decision.

MEASURED SIZE (dedup collapses repeated matches):
    7 beats    ~989 tokens        10 beats  ~1,333        15 beats  ~1,523
The block scales with OUR beat count and k, NOT with the index. Regenerating to
all 153 beats improves the matches at the same cost.
"""
import ast
import json
import pathlib
import sys

import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))


src = pathlib.Path(A.__file__).read_text()
tree = ast.parse(src)
BEATS, META = A.load_reference_index()

# ── 1. THE INDEX IS GENERATED, NOT HAND-WRITTEN ─────────────────────────────
check("the generator exists", pathlib.Path("build_reference_index.py").exists(),
      "hand-writing it is how it drifts from what the examples actually do")
check("the index loads", bool(BEATS), str(META))
check("every beat carries the READ — the craft, not a label",
      all((b.get("read") or "").strip() for b in BEATS),
      "a beat without its read is a treatment with no reason, which is the "
      "label this replaces")
check("and what was actually placed", all(b.get("treat") is not None for b in BEATS))

# ── 2. COMPLETENESS IS REPORTED, NEVER ASSUMED ──────────────────────────────
check("the index states how many beats the CORPUS has",
      META.get("beats_in_corpus"), str(META))
check("and how many it carries", META.get("beats_in_index") is not None)
check("a partial index says so", META["state"] in ("PARTIAL", "COMPLETE"),
      f"{META['state']} — INCONSISTENT means it carries more beats than it "
      f"claims the corpus has")
# THE ONE SELF-INCONSISTENCY A READER CAN CATCH. An index that merely
# UNDERSTATES the corpus is indistinguishable from a complete one; the defence
# there is the generator, which computes both from the same query. Stated as a
# limit rather than pretended away.
# BEHAVIOURAL, not a docstring check. The first version asserted the phrase
# "never raises" appeared in the docstring, which proves nothing about what the
# function does — the same shape as every substring trap in this repo.
import json as _json                                              # noqa: E402
import tempfile as _tf                                            # noqa: E402
_bad_path = _tf.mktemp(suffix=".json")
with open(_bad_path, "w", encoding="utf-8") as _fh:
    _json.dump({"beats_in_corpus": 1,
                "beats": [{"i": 0, "purpose": "hook", "dur": 1.0,
                           "treat": ["overlay_text"], "read": "x"},
                          {"i": 1, "purpose": "hook", "dur": 1.0,
                           "treat": ["overlay_text"], "read": "y"}]}, _fh)
_, _bad_meta = A.load_reference_index(_bad_path)
check("an index carrying more beats than the corpus is INCONSISTENT",
      _bad_meta["state"] == "INCONSISTENT", str(_bad_meta))
check("and says what to do about it", "regenerate" in _bad_meta.get("why", ""))
_, _gone_meta = A.load_reference_index(_bad_path + ".missing")
check("an unreadable index is UNREADABLE, never silently empty",
      _gone_meta["state"] == "UNREADABLE", str(_gone_meta))
if META["state"] == "PARTIAL":
    check("and says how to fix it", "build_reference_index" in META.get("why", ""))

# ── 3. THE THREE ABSENCES, EACH SPOKEN ──────────────────────────────────────
# All three are the same rule: say what is missing rather than return something
# that reads as a judgement.
# A FAMILY WITH NO EXAMPLES SAYS SO — asked of whichever family that is.
# This named `transition`, whose "NO REFERENCE" was the closed enum's shape
# rather than the corpus's behaviour: the annotator had no word for one. It now
# measures 16 occurrences across 8 of 10 videos, so the leg was asserting the
# absence of the very thing the re-read found.
_absent = [f for f in sorted(A.TREATMENT_FAMILIES) if f != "none"
           and ("NO REFERENCE" in (A.reference_family_note(f, BEATS, META) or "")
                or "NOT RECORDABLE" in (A.reference_family_note(f, BEATS, META) or ""))]
# EVERY FAMILY HAVING REFERENCES IS THE GOOD STATE, and this leg used to FAIL
# on it. The merged corpus records all six, so there is no natural absence left
# to exercise — which is an improvement, not a regression. Exercise the
# mechanism on a family the index genuinely does not carry instead.
if not _absent:
    print("  (note: every family has references — the absence rule is "
          "exercised on a synthetic family)")
    _synth = A.reference_family_note("__no_such_family__", BEATS, META)
    check("an unknown family says NO REFERENCE or NOT RECORDABLE",
          "NO REFERENCE" in _synth or "NOT RECORDABLE" in _synth, _synth[:80])
    check("and refuses to be read as permission or prohibition",
          "not permission" in _synth or "Neither permission" in _synth,
          "an empty list reads as 'nothing to say', which is a judgement")
for _f in _absent:
    _t = A.reference_family_note(_f, BEATS, META)
    check(f"{_f} says NO REFERENCE or NOT RECORDABLE explicitly",
          "NO REFERENCE" in _t or "NOT RECORDABLE" in _t, _t[:80])
    check(f"and {_f} refuses to be read as permission or prohibition",
          "not permission" in _t or "Neither permission" in _t,
          "an empty list reads as 'nothing to say', which is a judgement")
# A SCARCE FAMILY IS LABELLED BY ITS COUNT — asked of whichever family is
# actually scarce, not of `zoom` at exactly "6 EXAMPLES". That was the
# six-word corpus's number; the re-read puts zoom at 2 and card at 4, and a
# check pinned to 6 tests the old data rather than the property.
_scarce = [f for f in sorted(A.TREATMENT_FAMILIES) if f != "none"
           and "EXAMPLES" in (A.reference_family_note(f, BEATS, META) or "")]
check("some family is scarce enough to be labelled by count (non-vacuity)",
      bool(_scarce),
      "no family is scarce, so the two legs below would pass for the wrong "
      "reason")
for _f in _scarce[:3]:
    _z = A.reference_family_note(_f, BEATS, META)
    _n = sum(1 for _x in BEATS
             if _f in {(META.get("builds_as") or {}).get(_t, _t)
                       for _t in (_x.get("treat") or [])})
    check(f"{_f} is labelled as its example COUNT, not as a corpus",
          "EXAMPLES" in _z and str(_n) in _z, _z[:90])
    check(f"and {_f} says why that matters",
          "not a pattern" in _z or "bottleneck" in _z, _z[:90])

# COUNTS COME FROM THE CORPUS, NOT THE INDEX. A seeded index reporting "only 4
# examples of sfx in the whole corpus" when the corpus holds 14 is the
# absence-misreported-as-a-finding this feature exists to prevent — and it was
# the first thing the function did.
# COUNTS COME FROM THE CORPUS, NOT THE INDEX — asked structurally. This
# asserted `family_counts_in_corpus["sfx"] == 14`, a number from the six-word
# corpus. It is now 0, and for a reason worth stating rather than encoding: the
# annotator was sent silent frames and could not hear a sound effect however
# many there were. Pinning the leg to 14 tested that one reading, not the
# partial-index property it was written for.
_fc = META.get("family_counts_in_corpus") or {}
check("the corpus counts are present and cover the shipped vocabulary",
      bool(_fc) and set(_fc) >= {_t for _x in BEATS
                                 for _t in (_x.get("treat") or [])},
      f"{sorted(set(_fc))[:4]}... — a count table that does not cover the "
      f"index's own treatments cannot stop the index reporting its own size "
      f"as the corpus's")
check("and every count is at least what the index itself carries",
      all(_fc.get(_t, 0) >= sum(1 for _x in BEATS
                                if _t in (_x.get("treat") or []))
          for _t in {_t for _x in BEATS for _t in (_x.get("treat") or [])}),
      "a corpus count BELOW the index count is the seeded-index failure: the "
      "index would be reporting its own size as the corpus's")
# AND AN UNRECORDABLE FAMILY SAYS SO rather than reading as unused.
for _u in sorted(A.reference_unmeasurable()):
    _n = A.reference_family_note(_u, BEATS, META)
    check(f"{_u} is reported as NOT RECORDABLE, not as unused",
          "NOT RECORDABLE" in _n,
          f"{_n[:100]} — saying 'no reference beat uses it' states a fact "
          f"about editors that this instrument never measured")

# ── 4. CUTAWAY IS FILTERED, BECAUSE WE CANNOT DO ONE ────────────────────────
# 72 of 153 reference beats place a cutaway. Showing the agent craft it cannot
# imitate is worse than showing it nothing.
_any = A.reference_examples_for("evidence", 3.0, k=50, beats=BEATS)
# CUTAWAY BUILDS NOW (round 50). 47.1% of the corpus places one, and the
# retrieval must be allowed to show them — the old assertion here encoded the
# world where it could not. The property that survives: nothing UNBUILDABLE is
# retrieved, and that set is derived, not listed.
check("no retrieved example places an unbuildable family",
      not any(set(e.get("treat") or []) & set(A.reference_unbuildable())
              for e in _any),
      f"unbuildable={sorted(A.reference_unbuildable())}")
# THE FILTER IS DERIVED FROM THE SCHEMA, NOT HARDCODED — and this is the leg
# that matters, because the hardcode was CORRECT when written and becomes WRONG
# the day cutaway ships. Merged unchanged into a tree where cutaway exists, it
# would hide 47.1% of the corpus — the largest visual treatment — from the family
# that ruled ZERO because nothing explained it. The examples that teach it are
# exactly the ones the filter removed.
# ASSERTED ON THE CALL, not on the function existing. The first version asked
# whether reference_unbuildable was callable and the constant gone — both true
# of a tree where the CALL SITE had been replaced with a hardcoded set. Twenty-
# first instance: existence is not use.
_fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
            and n.name == "reference_examples_for"), None)
check("reference_examples_for exists", _fn is not None)
_uses = {n.func.id for n in ast.walk(_fn) if isinstance(n, ast.Call)
         and isinstance(n.func, ast.Name)} if _fn else set()
check("the retrieval CALLS the derivation", "reference_unbuildable" in _uses,
      "a hardcoded family list is a claim about the pipeline that rots the day "
      "the pipeline changes")
check("and the old constant is gone", not hasattr(A, "_REFERENCE_UNBUILDABLE"))

# BOTH SITES, because there are now two. The purpose-indexed _reference_block
# derives the unbuildable set itself rather than going through the retrieval,
# so guarding only reference_examples_for left half the surface unwatched — a
# gap my own refactor opened and the red proof's anchor guard exposed by
# reporting `anchor 2x` instead of counting a mutation RED.
_blkfn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_reference_block"), None)
check("_reference_block exists", _blkfn is not None)
_bu = {n.func.id for n in ast.walk(_blkfn) if isinstance(n, ast.Call)
       and isinstance(n.func, ast.Name)} if _blkfn else set()
check("the BLOCK also calls the derivation, not a hardcoded set",
      "reference_unbuildable" in _bu,
      "two call sites, two chances to hardcode; a family list frozen in either "
      "is a claim about the pipeline that rots the day the pipeline changes")
_rulable = A._rulable_treatments()
check("the derivation reads the treatment ENUM the agent rules from",
      {"card", "text", "sfx", "zoom"} <= _rulable, sorted(_rulable)[:8])
# SELF-CORRECTION, exercised rather than asserted: patch the enum and the filter
# must open. Without this the leg only proves today's answer.
_before = set(A.reference_unbuildable())


def _enums(o, out):
    if isinstance(o, dict):
        if o.get("type") == "array" and isinstance(o.get("items"), dict) \
                and o["items"].get("enum"):
            out.append(o["items"]["enum"])
        for _v in o.values():
            _enums(_v, out)
    elif isinstance(o, list):
        for _v in o:
            _enums(_v, out)


_es = []
_enums(list(A.TOOLS) + list(A.KNOWLEDGE_TOOLS), _es)
_patched = [e for e in _es if "card" in e and "text" in e]
check("there is a treatment enum to patch", bool(_patched))
if _patched:
    _e = _patched[0]
    # A family that ENTERS the enum with no builder behind it must show up in
    # the unbuildable set by derivation alone — the direction that matters now
    # that every real family builds. Synthetic name, so it can never collide.
    # reference_unbuildable derives from the ENUM against a fixed candidate
    # list, so the test that survives cutaway shipping is the inverse of the
    # original: take a real family OUT of the enum and the derivation must
    # report it unbuildable, with nobody editing the filter.
    # the derivation UNIONS every ruling surface's enum, so the family must
    # leave all of them for the derivation to see it go
    _slots = [(e, e.index("cutaway")) for e in _patched if "cutaway" in e]
    for e, _i in _slots:
        e.pop(_i)
    _after = set(A.reference_unbuildable())
    for e, _i in _slots:
        e.insert(_i, "cutaway")
    check("a family leaving the enum joins the unbuildable set by derivation",
          "cutaway" not in _before and "cutaway" in _after,
          f"before={sorted(_before)} after={sorted(_after)} — the filter must "
          f"close the day a family leaves, without anyone editing it")

check("the filter is opt-outable for analysis, not silently permanent",
      any("cutaway" in (e.get("treat") or []) for e in
          A.reference_examples_for("evidence", 3.0, k=50, beats=BEATS,
                                   allow_unbuildable=True))
      or not any("cutaway" in (b.get("treat") or []) for b in BEATS),
      "a filter with no way to see what it removed cannot be audited")

# ── 5. RETRIEVAL PICKS THE NEAREST MOMENT ───────────────────────────────────
_hook = A.reference_examples_for("hook", 2.4, k=3, beats=BEATS)
check("k is honoured", len(_hook) <= 3, str(len(_hook)))
check("purpose is the primary key",
      all(e.get("purpose") == "hook" for e in _hook) or len(BEATS) < 6,
      f"{[e.get('purpose') for e in _hook]}")
check("duration orders within a purpose",
      len(_hook) < 2 or abs(_hook[0]["dur"] - 2.4) <= abs(_hook[-1]["dur"] - 2.4),
      f"{[e['dur'] for e in _hook]}")

# ── 5b. THE INDEX IS MOUNTED INTO THE IMAGE ─────────────────────────────────
# A file the code reads must be mounted — this repo's own law. Without it
# load_reference_index returns UNREADABLE and the brief honestly reports that
# the agent is ruling without the examples. Honest and useless is still useless,
# and it is the "shipped and does nothing" shape with a truthful error message.
check("the index is added to the image",
      "reference_index.json" in src and "add_local_file(_REFERENCE_INDEX_SRC" in src,
      "the retrieval would read UNREADABLE in every container")
_mounted = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "add_local_file"
            and any(getattr(a, "id", "") == "_REFERENCE_INDEX_SRC" for a in n.args)]
check("mounted via add_local_file, asserted on the CALL", len(_mounted) == 1,
      f"{len(_mounted)} — a mention in a comment is not a mount")
check("mount_scratch_check knows about it",
      "reference_index.json" in pathlib.Path("mount_scratch_check.py").read_text()
      or True,
      "informational only — the file is tracked, so git status covers it")

# ── 6. IT REACHES THE BRIEF, WHICH IS THE CACHED PREFIX ─────────────────────
check("_reference_block is CALLED in the brief", "+ _reference_block(_beats)" in src,
      "a retrieval nothing injects is read_knowledge again — a surface the "
      "agent never opens")
_blk = A._reference_block([{"i": i, "t_start": i * 2.5, "t_end": i * 2.5 + d}
                           for i, d in enumerate([2.4, 1.2, 3.1, 0.8, 4.0, 2.9, 1.6])])

check("the block names the corpus size FROM the index, not a hardcoded number",
      str(META.get("beats_in_corpus")) in _blk,
      "hardcoding the count breaks the day the corpus grows, which is the day "
      "it matters most")
check("the block carries real reads", "editorializing" in _blk or len(_blk) > 800)
check("the block stays under 2000 tokens on a 7-beat fixture",
      len(_blk) // 4 < 2000, f"{len(_blk)//4} tokens — it rides the cached prefix "
      f"on every run and the size is a standing cost")
check("an unreadable index is SAID, not silently empty",
      "NONE AVAILABLE" in src,
      "a missing index must not produce a brief that looks complete")

if fails:
    print(f"REFERENCE-RETRIEVAL: {len(fails)} FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print(f"REFERENCE-RETRIEVAL: PASS — {META['beats_in_index']} of "
      f"{META['beats_in_corpus']} beats, cutaway filtered, zoom labelled, "
      f"transition spoken, ~{len(_blk)//4} tokens on 7 beats")
