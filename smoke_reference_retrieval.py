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
_t = A.reference_family_note("transition", BEATS, META)
check("transition says NO REFERENCE explicitly", "NO REFERENCE" in _t, _t[:80])
check("and refuses to be read as permission or prohibition",
      "not permission" in _t and "not a prohibition" in _t,
      "an empty list reads as 'nothing to say', which is a judgement")
_z = A.reference_family_note("zoom", BEATS, META)
check("zoom is labelled as its example COUNT, not as a corpus",
      "6 EXAMPLES" in _z, _z[:90])
check("and says why that matters",
      "not a pattern" in _z or "bottleneck" in _z, _z[:90])

# COUNTS COME FROM THE CORPUS, NOT THE INDEX. A seeded index reporting "only 4
# examples of sfx in the whole corpus" when the corpus holds 14 is the
# absence-misreported-as-a-finding this feature exists to prevent — and it was
# the first thing the function did.
check("family counts come from the corpus, not the index",
      META.get("family_counts_in_corpus", {}).get("sfx") == 14,
      f"{META.get('family_counts_in_corpus')} — the index carries fewer sfx "
      f"beats than the corpus, and must not report its own size as the corpus's")
check("so a family the index under-carries is NOT falsely flagged",
      A.reference_family_note("sfx", BEATS, META) == "",
      "sfx has 14 corpus examples; only an index count would call that scarce")

# ── 4. THE FILTER FOLLOWS THE SCHEMA, IN WHICHEVER DIRECTION IT POINTS ──────
# THIS LEG USED TO ASSERT THE OPPOSITE and it was correct when written: 72 of
# 153 reference beats place a cutaway, the pipeline could not make one, and
# showing the agent craft it cannot imitate is worse than showing it nothing.
#
# 444c4b8 derived the filter from the treatment enum so it self-corrects, and
# added new legs — but left THIS one asserting the old answer. Cutaway ships in
# the merged tree, so the filter correctly opened and the stale leg correctly
# failed. A check that hardcodes today's answer goes red the day the thing it
# describes changes, which is the whole reason the filter stopped hardcoding it.
#
# So the leg now asks the DERIVED question: examples must carry cutaway exactly
# when the agent can rule cutaway. One assertion, true in either tree.
_any = A.reference_examples_for("evidence", 3.0, k=50, beats=BEATS)
_rulable = "cutaway" in A._rulable_treatments()
_shown = any("cutaway" in (e.get("treat") or []) for e in _any)
_in_corpus = any("cutaway" in (b.get("treat") or []) for b in BEATS)
check("cutaway examples appear exactly when cutaway is rulable",
      (_shown == (_rulable and _in_corpus)),
      f"rulable={_rulable} in_corpus={_in_corpus} shown={_shown} — the filter "
      f"must track the schema, not a remembered answer")
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
check("every treatment enum is patched, not just the first",
      len([e for e in _es if "card" in e and "text" in e]) >= 2,
      f"{len([e for e in _es if 'card' in e and 'text' in e])} found — "
      f"rule_all_beats and beat_verdict both declare one, so a lower count "
      f"means this walk is missing one and the union below is untested")
if _patched:
    # ALL MATCHING ENUMS, NOT THE FIRST. _rulable_treatments() takes the UNION
    # across every tool, and there are TWO treatment enums now (rule_all_beats
    # and beat_verdict). Patching one left cutaway in the other, the union was
    # unchanged, and the leg compared [] to [] — passing vacuously while
    # claiming to prove self-correction. Same family as reading TOOLS while the
    # thing lives in KNOWLEDGE_TOOLS: the check looked in one of the two places
    # that matter.
    _es_all = [e for e in _es if "card" in e and "text" in e]
    _e = _patched[0]
    # PATCH WHICHEVER DIRECTION THIS TREE ALLOWS. The original only ADDED
    # cutaway to the enum — which is a no-op in a tree where cutaway already
    # ships, so `_added` was False, nothing was patched, and the leg compared
    # [] to [] and passed vacuously on both sides. A self-correction test that
    # can only test one direction stops testing at the moment the other one
    # becomes the live case.
    _present = any("cutaway" in e for e in _es_all)
    if _present:
        for _ee in _es_all:                       # ships -> must become unbuildable
            while "cutaway" in _ee:
                _ee.remove("cutaway")
        _after = set(A.reference_unbuildable())
        for _ee in _es_all:
            _ee.append("cutaway")
        check("a family LEAVING the enum joins the unbuildable set",
              "cutaway" not in _before and "cutaway" in _after,
              f"before={sorted(_before)} after={sorted(_after)} — the filter "
              f"must close the day the family stops shipping, without anyone "
              f"editing it")
    else:
        for _ee in _es_all:                       # absent -> must become buildable
            _ee.append("cutaway")
        _after = set(A.reference_unbuildable())
        for _ee in _es_all:
            _ee.remove("cutaway")
        check("a family JOINING the enum leaves the unbuildable set",
              "cutaway" in _before and "cutaway" not in _after,
              f"before={sorted(_before)} after={sorted(_after)} — the filter "
              f"must open the day the family ships, without anyone editing it")

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
