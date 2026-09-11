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
# SIX now: `transition` joined when the seam-dressing family was wired. The
# count is asserted so a family cannot quietly leave, and the MEMBERS are
# asserted so it cannot quietly change identity either.
ok(set(fams or []) == {"card", "text", "sfx", "zoom", "transition", "none"},
   f"the treatment families are {sorted(fams or [])}, not the six expected — "
   f"a family that leaves this list stops being rulable while every other "
   f"surface still mentions it")
ok("cutaway" not in (fams or []), "cutaway is back in _TREATMENT_FAMILIES")


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
# IMPORTED, NOT literal_eval'd. The schemas stopped being pure literals the
# moment an enum was built from a constant (`"enum": list(MG_SELECTABLE_TYPES)`)
# — literal_eval returned nothing for the whole TOOLS assignment and this walk
# found ZERO enums. The non-vacuity leg below caught it, which is the only
# reason it was not a silent hole.
#
# The categorical fix is this repo's own law: IMPORT THE MODULE AND ASSERT THE
# SYMBOL. Source is where code might be; runtime is where it is.
import types as _types
import modal_stub                                         # noqa: E402
modal_stub.install()
import agentic_editor_app as _A5                                  # noqa: E402
tools = list(_A5.TOOLS) + list(_A5.KNOWLEDGE_TOOLS)
ok(getattr(_A5, "TOOLS", None) is not None, "TOOLS could not be read")
ok(getattr(_A5, "KNOWLEDGE_TOOLS", None) is not None,
   "KNOWLEDGE_TOOLS could not be read")
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
# The router's constants and its two pure functions, so the checks below DRIVE
# the shipped rule instead of restating it.
for _n in TREE.body:
    if isinstance(_n, ast.Assign) and getattr(_n.targets[0], "id", "").startswith(
            ("ROUTE_", "ROUTES_", "_ADDITIVE_MARKERS", "_ROUTE_COST")):
        exec(compile(ast.Module([_n], []), "<s>", "exec"), _ns)
for _fname in ("normalize_spec", "capability_route", "route_cost"):
    _f = next((n for n in TREE.body
               if isinstance(n, ast.FunctionDef) and n.name == _fname), None)
    if _f is not None:
        exec(compile(ast.Module([_f], []), "<s>", "exec"), _ns)
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
ok(SRC.count("if _unsupported_stop:") == 1,
   "nothing READS _unsupported_stop — the run would continue and produce an "
   "edit that ignores the request, and charge for it")

# PER TERMINAL, DISCOVERED FROM THE SOURCE — not counted. These three legs were
# `count(...) == 1` and `count(...) == 2`, fitted to a world with exactly ONE
# terminal (`unsupported`). K5's `needs_input` is a second, and the counts went
# red on correct code while asserting nothing about the new branch: a count
# tells you the number changed, never which terminal is unguarded. The property
# is per-terminal — EVERY terminal stops the loop and charges NOTHING — so the
# terminals are enumerated from the source and each is checked. A third one
# added later is covered the day it lands.
_terms = {}
for _if in ast.walk(TREE):
    if not isinstance(_if, ast.If):
        continue
    _names = [n.value.value for n in ast.walk(_if)
              if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
              and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                      and t.slice.value == "terminal" for t in n.targets)]
    for _nm in _names:
        # the TIGHTEST enclosing If wins — a nested branch is the real owner
        _prev = _terms.get(_nm)
        if _prev is None or len(ast.dump(_if)) < len(ast.dump(_prev)):
            _terms[_nm] = _if
ok(len(_terms) >= 2,
   f"expected at least two terminals (unsupported_request, needs_input), "
   f"found {sorted(_terms)} — a terminal that stops the run without being "
   f"named here is one nobody checked for charging")
for _nm, _if in sorted(_terms.items()):
    _charged = [n for n in ast.walk(_if) if isinstance(n, ast.Dict)
                for k, v in zip(n.keys, n.values)
                if isinstance(k, ast.Constant) and k.value == "credit_charged"]
    _vals = [v.value for n in ast.walk(_if) if isinstance(n, ast.Dict)
             for k, v in zip(n.keys, n.values)
             if isinstance(k, ast.Constant) and k.value == "credit_charged"
             and isinstance(v, ast.Constant)]
    ok(len(_vals) >= 2,
       f"terminal {_nm!r} states credit_charged at {len(_vals)} site(s) — it "
       f"must say so at BOTH the ledger and the tool-result site, because an "
       f"existence check cannot see one of two flipped")
    ok(_vals and all(v is False for v in _vals),
       f"terminal {_nm!r} records credit_charged {_vals} — the user must not "
       f"be charged for a request we did not serve")
    ok(any(isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
           and n.value.value is True
           and any(getattr(t, "id", "") == "_unsupported_stop" for t in n.targets)
           for n in ast.walk(_if)),
       f"terminal {_nm!r} does not set _unsupported_stop — it names itself "
       f"terminal and then lets the run continue")
ok('"credit_charged": True' not in SRC,
   "something records credit_charged: True on a terminal path")

# ── THE CAPABILITY ROUTER ───────────────────────────────────────────────────
# set_spec's fourth branch was a refusal; it is a ROUTE now. One route is
# built, the others terminate and are COUNTED — unsupported_request has fired
# zero times across rounds 51-59, so what gets built next currently rests on a
# count nobody has taken.
_cr, _rcost = _ns.get("capability_route"), _ns.get("route_cost")
ok(callable(_cr) and callable(_rcost),
   "capability_route/route_cost are not importable — a router that can only be "
   "exercised through the dispatch is a rule the check has to restate")
if callable(_cr) and callable(_rcost):
    ok(_cr("full_edit", None, "punchy")[0] == "edit",
       "an editable request does not route to edit")
    ok(_cr("question", None, "what is this")[0] == "question",
       "a question does not route to question")
    ok(_cr("unsupported", "change_in_frame", "remove the background")[0]
       == "change_in_frame",
       "an in-frame change routes to a CLIP GENERATOR, which cannot serve it")
    # THE ADDITIVE RULE, both directions. "Add a shot OVER THIS" keeps the
    # user's edit; answering it as pure generation throws their footage away.
    ok(_cr("unsupported", "generate_footage", "add a shot of a city over this")[0]
       == "hybrid",
       "an ADDITIVE generate request does not route to hybrid — the user's own "
       "edit would be discarded")
    ok(_cr("unsupported", "generate_footage", "make a scene where a car drives")
       [1] == "AMBIGUOUS",
       "a non-additive generate request is answered silently instead of asked "
       "about — two readings differing by minutes and dollars")
    ok(_cr("weird_mode", None, "x")[1] == "AMBIGUOUS",
       "an unrecognised mode resolves silently rather than recording the "
       "ambiguity")
    ok(_cr("weird_mode", None, "x")[0] == "edit",
       "an unrecognised mode does not default to the BUILT route, which is the "
       "safe direction")
    # COST: measured where it was measured, ABSENT where nothing ever ran.
    ok(_rcost("edit")[0] == "MEASURED" and _rcost("edit")[1]["n"] == 15,
       "the edit route's cost is not MEASURED with its denominator")
    for _r in ("generate", "hybrid", "change_in_frame"):
        ok(_rcost(_r)[0] == "ABSENT",
           f"route {_r} quotes a cost figure — nothing here has ever run it, "
           f"and a router that quotes a number it does not have is probe "
           f"collapse making a product decision")
        ok("never been run" in str(_rcost(_r)[1]),
           f"route {_r}'s ABSENT does not say what must be measured first")
# COUNTED, not merely mentioned. `"route_demand" in SRC` survived deleting the
# increment, because the setdefault that creates the dict is a separate line —
# so the demand signal would have stayed permanently empty while the check read
# green. That is the exact defect this counter exists to end.
_inc = [n for n in ast.walk(TREE) if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Subscript)
                and isinstance(getattr(t, "value", None), ast.Subscript)
                and isinstance(t.value.slice, ast.Constant)
                and t.value.slice.value == "route_demand" for t in n.targets)
        and "+ 1" in ast.unparse(n.value)]
ok(bool(_inc) and "capability_route" in SRC,
   "nothing INCREMENTS led['route_demand'] — the demand signal would stay "
   "empty while the ledger key exists, which is how unsupported_request read "
   "zero for nine rounds")
ok('fail("route_ambiguous"' in SRC,
   "an AMBIGUOUS route does not fail loudly — it would be chosen silently")
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
print("ok smoke_five_families — 6 families, cutaway absent from tools/enums/"
      "rates/rubric, unsupported class validated, terminal path breaks the loop "
      "and charges nothing")
