#!/usr/bin/env python3
"""RED proof for smoke_menu_lines.py.

MUTATIONS AIMED AT THE DATA, NOT AT THE RULE. Four mutations today were
VACUOUS, and all four failed the same way: they LOOSENED a rule the population
already satisfied. Widening MAX_LEN from 90 to 900 changes a real byte and
cannot change a verdict, because no line is over 90 — the eighth way a mutation
stops mutating, and the one with no generic guard.

So each mutation below puts a VIOLATING LINE into the corpus and asserts the
shipped smoke refuses it. The single exception is L5, whose population is
deliberately empty today (no second home exists), so it is driven on a fixture
inside the smoke and mutated in the CODE — the only place its property lives.

Every mutation carries the PHRASE its target leg prints. A red whose output
does not contain that phrase is reported NOT RED: twice this week a harness
went red because the file stopped parsing, and a red that is not about the
property is exactly as wrong as a green that is not.
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_menu_lines.py")
LINES = os.path.join(HERE, "measured", "MENU_LINES.json")
WATCHED = ["smoke_menu_lines.py", os.path.join("measured", "MENU_LINES.json")]


def _child_env():
    # A mutated .py re-run in a subprocess can be served a STALE .pyc — Python
    # invalidates on (mtime, size), and a proof that writes-runs-restores-writes
    # inside one mtime second serves the EARLIER mutant's bytecode. Measured on
    # red_proof_run_gates: 5/5, 4/5 and 3/5 across three runs of one harness.
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


# ---------------------------------------------------------------- data mutants
def _drop_a_component(d):
    d["components"] = d["components"][:-1]
    return d


def _overlong(d):
    d["components"][0] = (d["components"][0]
                          + " and also for any other moment you might"
                            " conceivably want it in")
    return d


def _comma(d):
    d["sounds"][0] = "boom - deep low impact, for a heavy landing"
    return d


def _no_when(d):
    d["components"][6] = "EmojiCard — a big emoji with a caption under it"
    return d


def _unknown_component(d):
    d["components"][7] = ("StatCardDeluxe — a big number that counts up"
                          " for a figure worth landing")
    return d


def _newline(d):
    d["caption_styles"][0] = d["caption_styles"][0].replace(" — ", " —\n", 1)
    return d


DATA_MUTATIONS = [
    # name, apply, leg phrase, precondition over the UNMUTATED corpus
    ("a_component_line_goes_missing", _drop_a_component,
     "L0 thirty_two_lines_one_per_asset",
     lambda d: len(d["components"]) == 12),
    ("a_line_runs_past_ninety", _overlong,
     "L1 every_line_obeys_the_rule",
     lambda d: all(len(l) <= 90 for l in d["components"])),
    ("a_comma_enters_a_sound_name", _comma,
     "L2 no_commas_anywhere",
     lambda d: not any("," in l for l in d["sounds"])),
    # A NEWLINE IS INVISIBLE IN EVERY SURFACE THAT SHOWS THE LINE, which is
    # why it gets its own mutation rather than riding on the length leg: the
    # mutant is the same characters in the same order and still breaks the name.
    ("a_newline_hides_inside_a_line", _newline,
     "L1 every_line_obeys_the_rule",
     lambda d: not any("\n" in l for l in d["caption_styles"])),
    ("a_line_says_what_and_not_when", _no_when,
     "L3 every_line_says_when_to_use_it",
     lambda d: " for " in d["components"][6]),
    ("a_line_names_a_component_that_does_not_exist", _unknown_component,
     "L4 component_lines_name_real_components",
     lambda d: d["components"][7].split(" — ")[0] == "StatCard"),
]

# ---------------------------------------------------------------- code mutants
# L5's population is EMPTY IN PRODUCTION BY DESIGN — no description field and no
# style-guide index exist yet — so there is no corpus row to corrupt. It is
# driven on a fixture inside the smoke, and the only thing that can break the
# byte-identity rule is the comparison itself.
CODE_MUTATIONS = [
    ("byte_identity_becomes_fuzzy",
     "        return a is not None and b is not None and a == b",
     "        return a is not None and b is not None and a.strip() == b.strip()",
     "L5 byte_identity_rule_discriminates",
     lambda s: "and a == b" in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_child_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def snapshot():
    return {q: open(os.path.join(HERE, q), "rb").read() for q in WATCHED}


def residue(base):
    return sorted(q for q, b in base.items()
                  if open(os.path.join(HERE, q), "rb").read() != b)


def leg_failed(out, phrase):
    """The named leg printed FAIL — not merely that the run was non-zero."""
    for ln in out.splitlines():
        if phrase in ln and "FAIL" in ln:
            return True
    return False


def main():
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:])
        return 2
    print("baseline green.\n")
    base = snapshot()
    raw = io.open(LINES, encoding="utf-8").read()
    src = io.open(SMOKE, encoding="utf-8").read()

    red, vacuous = 0, []
    total = len(DATA_MUTATIONS) + len(CODE_MUTATIONS)

    for name, apply_, phrase, pre in DATA_MUTATIONS:
        d = json.loads(raw)
        if not pre(d):
            # THE PRECONDITION ASKS WHETHER THE TARGET DOES ANYTHING. A
            # mutation that corrupts a corpus already carrying that corruption
            # proves nothing, and is indistinguishable from a blind check.
            vacuous.append(name)
            print("  %-46s VACUOUS   precondition false before the edit" % name)
            continue
        io.open(LINES, "w", encoding="utf-8").write(
            json.dumps(apply_(d), indent=1, ensure_ascii=False))
        rc2, out2 = run_smoke()
        io.open(LINES, "w", encoding="utf-8").write(raw)
        ok = rc2 != 0 and leg_failed(out2, phrase)
        red += 1 if ok else 0
        print("  %-46s %s   rc=%d leg_failed=%s"
              % (name, "RED " if ok else "NOT RED", rc2, leg_failed(out2, phrase)))

    for name, old, new, phrase, pre in CODE_MUTATIONS:
        if src.count(old) != 1:
            print("  %-46s HARNESS FAILURE: anchor %dx"
                  % (name, src.count(old)))
            continue
        if not pre(src):
            vacuous.append(name)
            print("  %-46s VACUOUS   precondition false" % name)
            continue
        io.open(SMOKE, "w", encoding="utf-8").write(src.replace(old, new, 1))
        rc2, out2 = run_smoke()
        io.open(SMOKE, "w", encoding="utf-8").write(src)
        ok = rc2 != 0 and leg_failed(out2, phrase)
        red += 1 if ok else 0
        print("  %-46s %s   rc=%d leg_failed=%s"
              % (name, "RED " if ok else "NOT RED", rc2, leg_failed(out2, phrase)))

    left = residue(base)
    if left:
        print("\nHARNESS FAILURE: residue left on disk: %s" % ", ".join(left))
        return 2

    print("\n%d/%d RED-proven%s"
          % (red, total, ("; VACUOUS: " + ", ".join(vacuous)) if vacuous else ""))
    # `all([])` is True and `0 == len([])` is True: the floor is what stops an
    # emptied mutation list reporting success. 26 of 27 red proofs in this repo
    # once passed that way.
    if vacuous or not (total and red == total):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
