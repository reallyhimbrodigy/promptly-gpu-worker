#!/usr/bin/env python3
"""The beat brief carries the FIGURE, not the fact that one exists.

CUTAWAY IN MINIATURE. The harness already located the number — the same regex
`derive_card_props` uses to split "10 TIMES A DAY" into 10 / TIMES A DAY — and
the brief told the agent `(has a number)`, a BOOLEAN. The pipeline found the
figure and reported its existence, leaving the agent to re-derive by eye what
had already been computed. That is the shape that made cutaway rule zero: a
capability offered as a blank rather than as material.

ONE EXTRACTOR, NOT TWO, and this is the part that must hold. If the brief showed
a figure that `derive_card_props` then failed to find, the agent would be shown
material the builder refuses — the advertise-a-shape-the-acceptor-rejects class
this repo has paid for three times (card_props' unreachable shape, the sfx names
with extensions, cutaway's unexplained enum). The two callers share
`extract_figure` so they cannot disagree.

IT IS MATERIAL, NOT AN INSTRUCTION. A beat carrying a figure is not a beat that
must take a card. The rates grade and never instruct, and the same applies here:
showing what is there is not demanding what to do about it.

RED-proven by red_proof_beat_figure_offered.py.
"""
import ast
import pathlib
import re
import sys

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_ns = {"re": re}
for _n in tree.body:
    # derive_card_props reads MG_PROP_KEYS and the brand set, so the agreement
    # leg needs them in the namespace too — a NameError deep inside a leg would
    # otherwise read as the leg failing rather than the loader being short.
    if isinstance(_n, ast.Assign) and any(
            getattr(_x, "id", "") in ("_FIGURE_RE", "MG_PROP_KEYS",
                                      "MG_BRAND_ONLY", "MG_PROPS_UNDERIVABLE")
            for _t in _n.targets for _x in ast.walk(_t)):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
    if isinstance(_n, ast.FunctionDef) and _n.name in ("extract_figure",
                                                       "derive_card_props"):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
check("extract_figure is module-level and pure", "extract_figure" in _ns)
if "extract_figure" not in _ns:
    print("\nBEAT-FIGURE: FAIL"); sys.exit(1)
f = _ns["extract_figure"]

# ── the extraction itself ───────────────────────────────────────────────────
for _phrase, _want in [("10 TIMES A DAY", "10"), ("we spent $1,200 on it", "$1,200"),
                       ("up 40% this year", "40%"), ("3x faster", "3x"),
                       ("no numbers here", None), ("", None)]:
    check(f"{_phrase!r} -> {_want!r}", f(_phrase)[0] == _want, f"{f(_phrase)}")
check("the remainder is the words AROUND the figure",
      f("10 TIMES A DAY")[1] == "TIMES A DAY", f("10 TIMES A DAY"))
check("a multiplier suffix only counts when it is not the start of a word",
      f("5 MINUTES of work")[0] == "5",
      "'5 M' in '5 MINUTES' once read as FIVE MILLION")
check("absence returns None and an empty remainder, never a guess",
      f("nothing") == (None, ""))

# ── ONE EXTRACTOR ───────────────────────────────────────────────────────────
_defs = [n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == "extract_figure"]
check("there is exactly ONE extract_figure", len(_defs) == 1, f"{len(_defs)}")
_inline = re.findall(r"re\.search\(r\"\[\$£€\]", src)
check("no caller keeps its own copy of the pattern", not _inline,
      f"{len(_inline)} inline copies — two extractors that can disagree is the "
      f"advertise-a-shape-the-acceptor-rejects class")
_dcp = ast.get_source_segment(src, next(
    n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
    and n.name == "derive_card_props")) or ""
check("derive_card_props CALLS the shared extractor",
      "extract_figure(" in _dcp,
      "if the builder used a different pattern, the brief could offer a figure "
      "the builder then refuses")

# ── AGREEMENT, driven rather than asserted ──────────────────────────────────
_dp = _ns.get("derive_card_props")
if _dp:
    _agree = []
    for _p in ("10 TIMES A DAY", "up 40% this year", "$1,200 saved", "3x faster",
               "no numbers here", "just words"):
        _shown = f(_p)[0]
        _props, _why = _dp("StatCard", _p)
        _built = bool(_props)
        if (_shown is not None) != _built:
            _agree.append(f"{_p!r}: brief shows {_shown!r} but builder "
                          f"{'built' if _built else 'refused'}")
    check("every phrase the brief would show a figure for, the builder accepts",
          not _agree, "\n         ".join(_agree))

# ── it reaches the brief, and as MATERIAL ───────────────────────────────────
check("the beat record carries the figure", '_b["figure"] = extract_figure(' in src)
check("the brief prints the figure rather than the boolean",
      '"  (figure: %s)" % b["figure"]' in src)
check("the boolean remains as the fallback when no figure parses",
      '"  (has a number)" if b["has_number"]' in src,
      "a beat whose number the extractor cannot parse must still say a number "
      "is there — dropping to silence would hide it")
check("it is offered as MATERIAL, not as an instruction",
      "must take a card" not in src.split("_b[\"figure\"]")[1][:400],
      "showing what is there is not demanding what to do about it")

print()
if fails:
    print("BEAT-FIGURE: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("BEAT-FIGURE: PASS — one extractor, brief and builder agree on every "
      "phrase, the figure reaches the beat row and the boolean survives as the "
      "fallback")
