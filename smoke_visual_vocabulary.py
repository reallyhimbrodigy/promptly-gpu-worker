#!/usr/bin/env python3
"""The silent route reasons in footage terms, not borrowed speech terms.

THE DEFECT, WITH THE EVIDENCE. 46.5% of real traffic has no narration. The
silent route was told to "rule on them exactly as you would rule on spoken
beats" and that stillness is "the visual equivalent of dead air" — it borrowed
the speech route's language because it had none of its own. Round 52, car_short
beat 0: the beat's OWN TEXT said "visible content, not dead air", and the
agent's why said "5.7s of pre-speech setup is dead air" and cut it. Wet street
footage building tension, deleted as silence.

NOT A SECOND VOCABULARY. The seven purposes stay the join key. What changes is
the DEFINITION each gets on the silent route: the same seven words in what
footage DOES. A visual axis beside `purpose` would recreate the purpose/zoom_arc
collision, and this file asserts it did not happen.

RED-proven by red_proof_visual_vocabulary.py.
"""
import ast
import pathlib
import sys

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_ns = {}
for _n in tree.body:
    if isinstance(_n, ast.Assign) and any(
            getattr(_x, "id", "") in ("BEAT_PURPOSES", "VISUAL_PURPOSE_READS")
            for _t in _n.targets for _x in ast.walk(_t)):
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
    if isinstance(_n, ast.FunctionDef) and _n.name == "visual_purpose_block":
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
check("the visual reads exist and are drivable",
      "VISUAL_PURPOSE_READS" in _ns and "visual_purpose_block" in _ns)
if "visual_purpose_block" not in _ns:
    print("\nVISUAL-VOCABULARY: FAIL"); sys.exit(1)
_reads, _purp = _ns["VISUAL_PURPOSE_READS"], _ns["BEAT_PURPOSES"]
_blk = _ns["visual_purpose_block"]()

# ── ONE VOCABULARY, SEVEN DEFINITIONS ───────────────────────────────────────
check("the visual reads cover EXACTLY the seven purposes — no eighth axis",
      set(_reads) == set(_purp), f"{sorted(set(_reads) ^ set(_purp))}")
check("every purpose appears in the silent-route block",
      all(_p.upper() in _blk for _p in _purp))

# ── THE DEFINITIONS ARE ABOUT FOOTAGE, NOT SENTENCES ────────────────────────
_SPEECH = ("word", "said", "says", "sentence", "line", "spoken", "narrat",
           "transcript", "quote")
_FOOTAGE = ("motion", "framing", "shot", "subject", "picture", "look", "still",
            "held", "frame", "footage", "eye", "reveal", "impact", "angle",
            "close-up", "energy")
for _p, _r in _reads.items():
    _lo = _r.lower()
    check(f"{_p}: defined in footage terms",
          any(w in _lo for w in _FOOTAGE) and not any(w in _lo for w in _SPEECH),
          f"{_r[:90]}")

# ── THE THREE SLIPS ARE GONE — FROM THE STRINGS, NOT THE SOURCE ─────────────
# The prompt is assembled from string literals; comments never reach the agent.
# The first draft of this leg grepped SOURCE and failed on the comment that
# records the slip for the next reader (the correction kept in place, per the
# stale-comment rule). A check that reads source cannot tell code from prose —
# so read the literals the AST holds, which is exactly the set that can reach a
# prompt.
_lits = [n.value for n in ast.walk(tree)
         if isinstance(n, ast.Constant) and isinstance(n.value, str)]
_in_lits = lambda t: any(t in v for v in _lits)
check("'rule exactly as you would rule on spoken beats' reaches no string",
      not _in_lits("exactly as you would rule on spoken beats"),
      "that sentence IS the instruction to borrow the speech route's language")
check("'the visual equivalent of dead air' reaches no string",
      not _in_lits("visual equivalent of dead air"))
check("and the block says so outright", "STILLNESS IS NOT DEAD AIR" in _blk)
check("edge beats no longer describe themselves as waiting for the first word",
      not _in_lits("visible content, not dead air")
      and _in_lits("footage doing a job before"),
      "the beat text itself must not frame footage as a gap between words")

# ── IT REACHES THE SILENT ROUTE ONLY ────────────────────────────────────────
check("the block is wired into the NO SPEECH branch of the brief",
      "+ visual_purpose_block() +" in src)
_no_speech = src[src.index("NO SPEECH. This source"):src.index("NO SPEECH. This source") + 2400]
check("and it sits inside the no-speech branch, not the shared prompt",
      "visual_purpose_block()" in _no_speech,
      "a speech source told its footage is silent would be the inverse slip")

# ── breath is the one that was being deleted ────────────────────────────────
check("BREATH is defined as a beat to rule on, not dead air to delete",
      "not dead air" in _reads["breath"].lower()
      and "rule on" in _reads["breath"].lower(), _reads["breath"])

print()
if fails:
    print("VISUAL-VOCABULARY: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("VISUAL-VOCABULARY: PASS — seven purposes defined in footage terms, the "
      "three slips gone, wired to the silent route only")
