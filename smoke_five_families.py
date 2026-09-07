"""SMOKE — five families, and an unsupported request is ANSWERED not edited.

CUTAWAY WAS REMOVED (2026-09-06), not left unbuilt. It had been the largest
corpus family (72 placements, 4.22/25s) building ZERO on every run, which read
as the pipeline's biggest gap. It is a scope decision: this editor works with
the footage the user uploaded.

WHY A SMOKE AND NOT A NOTE. This lane's own law is that A CAPABILITY IN THE
SCHEMA WILL BE USED — the prompt said "do not orchestrate" and the agent
orchestrated anyway. Removal therefore has to be checked as an ABSENCE from the
tool surface, the enums and the rubric, or the next person to widen an enum
quietly restores a family with no implementation behind it.
"""
import ast
import sys

SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)
FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

_top = {}
for _n in TREE.body:
    if isinstance(_n, ast.Assign) and isinstance(_n.targets[0], ast.Name):
        try:
            _top[_n.targets[0].id] = ast.literal_eval(_n.value)
        except Exception:
            pass

# ── 1. the family vocabulary ────────────────────────────────────────────────
fams = _top.get("_TREATMENT_FAMILIES")
ok(fams is not None, "_TREATMENT_FAMILIES is gone")
ok("cutaway" not in (fams or []), "cutaway is back in _TREATMENT_FAMILIES")
ok(set(fams or []) == {"card", "text", "sfx", "zoom", "none"},
   f"the family set changed: {fams}")

ref = _top.get("REFERENCE_PER_25S") or {}
ok("cutaway" not in ref,
   "the corpus cutaway rate is back in REFERENCE_PER_25S — every run would "
   "again report 0% against a capability this pipeline deliberately lacks, "
   "which reads as a gap rather than a scope decision")
fit = _top.get("REFERENCE_BEAT_FIT") or {}
ok("cutaway" not in fit, "cutaway is back in REFERENCE_BEAT_FIT")
ok("cutaway" not in (_top.get("PLACEMENT_FAMILY") or {}),
   "cutaway is back in PLACEMENT_FAMILY")

# ── 2. THE TOOL IS GONE FROM THE SURFACE ────────────────────────────────────
# Withholding the capability is the property; forbidding it in prose is only a
# preference.
ok("def place_cutaway" not in SRC, "place_cutaway is implemented again")
# BOTH LISTS. The agent's surface is `TOOLS + KNOWLEDGE_TOOLS` (see the
# dispatch), and TOOLS holds only 5 entries — execute_plan, probe_source,
# build_zoom, place_sfx, inspect_output. set_spec, rule_all_beats and
# place_cutaway all live in KNOWLEDGE_TOOLS. The first version of this smoke
# read TOOLS alone, so "place_cutaway not in names" was TRUE about a list that
# never contained it, and a mutation re-adding the tool passed clean. Checking
# the wrong collection is indistinguishable from checking nothing.
tools = list(_top.get("TOOLS") or []) + list(_top.get("KNOWLEDGE_TOOLS") or [])
ok(_top.get("TOOLS") is not None, "TOOLS could not be read")
ok(_top.get("KNOWLEDGE_TOOLS") is not None, "KNOWLEDGE_TOOLS could not be read")
names = [t.get("name") for t in tools]
# Non-vacuity: the surface must contain the tools we know are there.
for _must in ("set_spec", "rule_all_beats", "execute_plan"):
    ok(_must in names,
       f"{_must!r} is not in the tool surface this smoke reads — it is "
       f"inspecting the wrong collection and every absence check below is vacuous")
ok("place_cutaway" not in names,
   "place_cutaway is back in the TOOLS schema — the agent will call it")
ok(len(names) == len(set(names)), f"duplicate tool names: {names}")

# Every enum the agent reads must be free of it — RECURSIVELY. The first
# version of this walked only input_schema.properties and MISSED the one that
# matters: `treatment` is an array, so its enum lives at
# properties.beats.items.properties.treatment.items.enum, two levels down. A
# mutation re-adding "cutaway" there passed cleanly. Depth is exactly where a
# schema check gets fooled, so walk the whole tree.
def _enums(node, path="input_schema"):
    if isinstance(node, dict):
        if isinstance(node.get("enum"), list):
            yield path, node["enum"]
        for k, v in node.items():
            yield from _enums(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _enums(v, f"{path}[{i}]")

_seen_enums = 0
for t in (tools or []):
    for path, vals in _enums(t.get("input_schema") or {}):
        _seen_enums += 1
        ok("cutaway" not in vals,
           f"tool {t.get('name')!r} still offers 'cutaway' at {path}")
# A walk that finds nothing asserts nothing.
ok(_seen_enums >= 5,
   f"only {_seen_enums} enums found in the tool schemas — the walk is not "
   f"reaching them, so this check passes vacuously")

# ── 3. THE UNSUPPORTED CLASS ────────────────────────────────────────────────
modes = _top.get("SPEC_MODES") or ()
ok("unsupported" in modes, "set_spec has no 'unsupported' mode")
classes = _top.get("UNSUPPORTED_CLASSES") or ()
ok(set(classes) == {"generate_footage", "change_in_frame"},
   f"UNSUPPORTED_CLASSES changed: {classes}")

_ns = {}
for _n in TREE.body:
    if isinstance(_n, ast.Assign) and getattr(_n.targets[0], "id", "") in (
            "SPEC_MODES", "SPEC_FAMILIES", "UNSUPPORTED_CLASSES",
            "REFERENCE_PER_25S"):
        exec(compile(ast.Module([_n], []), "<s>", "exec"), _ns)
_nsf = next(n for n in TREE.body
            if isinstance(n, ast.FunctionDef) and n.name == "normalize_spec")
exec(compile(ast.Module([_nsf], []), "<s>", "exec"), _ns)
norm = _ns["normalize_spec"]

got = norm({"mode": "unsupported", "unsupported_class": "generate_footage"})
ok(got.get("unsupported_class") == "generate_footage",
   "normalize_spec drops the unsupported class")
try:
    norm({"mode": "unsupported"})
    FAIL.append("an unsupported request with NO class is accepted — an unnamed "
                "refusal cannot be counted, and the count is the demand signal")
except ValueError:
    pass
try:
    norm({"mode": "unsupported", "unsupported_class": "make_it_cool"})
    FAIL.append("an arbitrary unsupported_class is accepted")
except ValueError:
    pass
ok("cutaway" not in _ns["SPEC_FAMILIES"],
   "cutaway is back in SPEC_FAMILIES — a targeted_change could scope to it")

# ── 4. THE TERMINAL PATH IS REAL ────────────────────────────────────────────
# A flag that nothing reads is the producer-with-no-consumer defect this repo
# keeps rediscovering; assert BOTH ends exist.
ok(SRC.count("_unsupported_stop = False") == 1,
   "_unsupported_stop is not initialised before the loop — the ordinary path "
   "would raise NameError")
ok(SRC.count("_unsupported_stop = True") == 1,
   "nothing SETS _unsupported_stop")
ok(SRC.count("if _unsupported_stop:") == 1,
   "nothing READS _unsupported_stop — the run would continue and produce an "
   "edit that ignores the request, and charge for it")
# BOTH sites, and the absence of the opposite. A substring test for
# '"credit_charged": False' passed while one of the two was flipped to True,
# because the other still matched — an existence check cannot see a change it
# does not count.
ok(SRC.count('"credit_charged": False') == 2,
   f'expected credit_charged:False at BOTH the ledger and the tool-result '
   f'site, found {SRC.count(chr(34) + "credit_charged" + chr(34) + ": False")} '
   f'— the user must not be charged for a request we cannot serve')
ok('"credit_charged": True' not in SRC,
   "something records credit_charged: True on the unsupported path")
_break = [n for n in ast.walk(TREE)
          if isinstance(n, ast.If)
          and any(getattr(t, "id", "") == "_unsupported_stop" for t in ast.walk(n.test))
          and any(isinstance(b, ast.Break) for b in ast.walk(n))]
ok(len(_break) == 1,
   "the _unsupported_stop branch does not BREAK the turn loop — it would fall "
   "through and keep spending turns")

# ── 5. THE UNSUPPORTED BRANCH MUST SHORT-CIRCUIT derive_rubric ─────────────
# derive_rubric REJECTS mode 'unsupported' (RUBRIC_MODES is the three editing
# modes), which is correct — an unsupported request has no rubric. It is safe
# only because the handler `continue`s first. Reorder those and every
# unsupported request raises ValueError instead of answering the user, so the
# ordering is asserted rather than remembered.
_ifs = [n for n in ast.walk(TREE)
        if isinstance(n, ast.If)
        and any(isinstance(c, ast.Constant) and c.value == "unsupported"
                for c in ast.walk(n.test))]
_guard = [n for n in _ifs if any(isinstance(x, ast.Continue) for x in ast.walk(n))]
ok(len(_guard) >= 1,
   "the set_spec 'unsupported' branch does not `continue` — control would fall "
   "through to derive_rubric, which rejects the mode, and the user would get a "
   "ValueError instead of the plain answer")
_dr = [n for n in ast.walk(TREE)
       if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "derive_rubric"]
ok(_dr and _guard and min(g.lineno for g in _guard) < min(d.lineno for d in _dr),
   "derive_rubric is called BEFORE the unsupported branch short-circuits")
# And the rubric never carries the removed family.
_rm = {}
for _n in TREE.body:
    if isinstance(_n, ast.Assign) and isinstance(_n.targets[0], ast.Name):
        try:
            exec(compile(ast.Module([_n], []), "<s>", "exec"), _rm)
        except Exception:
            pass
for _n in TREE.body:
    if isinstance(_n, ast.FunctionDef) and _n.name == "derive_rubric":
        exec(compile(ast.Module([_n], []), "<s>", "exec"), _rm)
_r = _rm["derive_rubric"](None, "full_edit")
ok("cutaway" not in str(_r),
   f"derive_rubric still emits a cutaway target: {_r}")
ok(set(_r["targets"]) == {"text", "cut", "card", "sfx", "zoom", "transition"},
   f"the rubric target set changed: {sorted(_r['targets'])}")

# ── 6. ONE MANIFEST PER RUN, NOT A UNION OF EVERY ATTEMPT ──────────────────
# execute_plan rebuilds the whole pipeline, so a second call REPLACES the first
# one's output — but placements were appended, so two calls declared both builds
# while `built` reported only the last. Round 13 measured it exactly: 3 calls ->
# text BUILT 2 / DECLARED 4, 2 calls -> 3 / 5, 1 call -> no gap.
_ep = [n for n in ast.walk(TREE)
       if isinstance(n, ast.FunctionDef) and n.name == "execute_plan"]
ok(len(_ep) == 1, "execute_plan not found (or defined more than once)")
if _ep:
    _resets = [n for n in ast.walk(_ep[0])
               if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Subscript)
                       and getattr(t.value, "id", "") == "led"
                       and getattr(getattr(t, "slice", None), "value", None) == "placements"
                       for t in n.targets)
               and isinstance(n.value, ast.List) and not n.value.elts]
    ok(len(_resets) == 1,
       "execute_plan does not reset led['placements'] to [] — a second call "
       "appends to the first call's manifest, so the declared count becomes a "
       "union of every attempt while `built` reports only the last")
    _appends = [n for n in ast.walk(_ep[0])
                if isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "append"
                and "placements" in ast.dump(n.func)]
    if _resets and _appends:
        ok(_resets[0].lineno < min(a.lineno for a in _appends),
           "the placements reset runs AFTER the declare loop — it would erase "
           "the manifest it just wrote")

# ── 7. A SILENT CLIP IS NOT A TALKING HEAD WITH THE SOUND OFF ─────────────
# REFERENCE_PER_25S is a TALKING-HEAD corpus — its text rate is
# transcript-derived. Round 20 was GREEN with four of five fixtures placing one
# family, and the mix check would have fired forever against a target never
# measured for these sources.
#
# MEASURED over 1,463 shipped no-speech jobs (moodreel + minimal, 30 days):
# cut 4.26, card 0.23 (91.7% place zero), transition 0.27, and text 0.00 —
# because the no-speech plan shape has NO text field at all.
_ns_ref = _top.get("REFERENCE_PER_25S_NOSPEECH")
ok(isinstance(_ns_ref, dict) and _ns_ref,
   "there is no no-speech reference — silent sources are being scored against a "
   "talking-head corpus whose text rate is transcript-derived")
if isinstance(_ns_ref, dict):
    ok(set(_ns_ref) == set(_top.get("REFERENCE_PER_25S") or {}),
       f"the two references cover different families: {sorted(_ns_ref)} vs "
       f"{sorted(_top.get('REFERENCE_PER_25S') or {})} — derive_rubric iterates "
       f"one of them, so a family present in only one silently loses its target")
    ok(_ns_ref.get("text") == 0.0,
       f"no-speech text reference is {_ns_ref.get('text')}, not 0.0 — production "
       f"cannot place text on these sources at all")
    ok(_ns_ref.get("cut", 0) > 3.0,
       "the no-speech cut reference collapsed — cut is the one family that "
       "transfers between the two corpora (4.26 vs 4.75)")

_dr = next((n for n in TREE.body
            if isinstance(n, ast.FunctionDef) and n.name == "derive_rubric"), None)
ok(_dr is not None and any(a.arg == "beat_source" for a in _dr.args.args),
   "derive_rubric cannot tell which corpus applies — it takes no beat_source")
_calls = [n for n in ast.walk(TREE)
          if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "derive_rubric"]
ok(_calls and all(any(k.arg == "beat_source" for k in c.keywords) for c in _calls),
   "a derive_rubric call site does not pass beat_source — it would silently "
   "score a silent clip against the talking-head corpus, which is the defect "
   "this exists to remove")

if FAIL:
    print("FAIL smoke_five_families:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_five_families — 5 families, cutaway absent from tools/enums/"
      "rates/rubric, unsupported class validated, terminal path breaks the loop "
      "and charges nothing")
