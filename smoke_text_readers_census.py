#!/usr/bin/env python3
"""A census of checks that assert on SOURCE TEXT instead of on behaviour.

THE RATE IS THE FINDING. Eight readers broke on CORRECT code in a single
session — four of them on changes that were one commit old, two of those my
own. Each was repaired by converting it to an AST or behavioural leg, and
repairing them one at a time treats eight symptoms of one condition. The
measurement that matters is how many more are waiting: 25 code-shaped text
readers across 16 files, first counted 2026-09-14.

WHAT MAKES A READER FRAGILE. A check that asserts a string appears in a source
file is asking "is this code spelled this way", when the question it means is
"does this code behave this way". Rename a variable, widen an `==` to an `in`,
split a line, and the check fails on code that is more correct than before —
and the failure points at the wrong file. Worse, the inverse: reword the code
and a `not in` leg goes green having checked nothing.

WHAT IS NOT FRAGILE. Most text readers here are RIGHT: 99 of the 124 assert on
PROSE — the system prompt, the plan, a refusal message. There the text IS the
artifact the agent reads, and checking it as text is checking the thing itself.
This census counts only needles that look like code we own.

SO: the set is NAMED, and the ratchet runs one way.
  * an ADDITION fails — a new code-shaped reader needs a deliberate `--adopt`,
    and the author has to decide whether an AST leg would do instead.
  * a REMOVAL passes and is recorded — converting one to AST is the progress
    this file exists to encourage.
Same instrument as `red_proof_census`, pointed the other way: there the members
must never disappear, here they must never multiply.
"""
import ast
import json
import pathlib
import re
import sys

CENSUS = pathlib.Path("text_reader_census.json")

# A needle is CODE-SHAPED when it reads like Python rather than prose. Kept
# deliberately broad: a false CODE call costs one `--adopt` line, a false
# `prose` call hides exactly the reader this file is for.
CODE = re.compile(
    r"(^\s*(if|for|while|def|class|return|elif|else|try|except|with)\b)"
    r"|(\w+\s*(==|!=|>=|<=)\s*\w)"
    r"|(\w+\s*=\s*[\w\[\(\"'])"
    r"|(\w+\([\w\"'\s,=\[\]{}]*\))"
    r"|(\bself\.|\w+\.\w+\()"
    r"|(^[\w\"']+\s*:\s*[\w\"'\[])"
)


def sources_read(tree):
    """Names bound to the text of a .py file — the haystacks."""
    names = set()
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign):
            continue
        u = ast.unparse(n.value)
        if re.search(r"\.read\(\)|read_text\(\)", u) and ".py" in u:
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
    return names


def readers(root="."):
    """{"<file>::<needle>"} for every code-shaped `"lit" in SRC` comparison.

    THREE STATES. A file that will not parse is FAILED and is reported, never
    skipped: a scanner that quietly drops what it cannot read returns a clean
    number for a corpus it did not inspect.
    """
    found, failed = set(), []
    files = sorted(pathlib.Path(root).glob("smoke_*.py"))
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except Exception as e:                                    # noqa: BLE001
            failed.append("%s: %s" % (p.name, type(e).__name__))
            continue
        srcs = sources_read(tree)
        if not srcs:
            continue
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Compare) and len(n.ops) == 1
                    and isinstance(n.ops[0], (ast.In, ast.NotIn))
                    and isinstance(n.left, ast.Constant)
                    and isinstance(n.left.value, str)
                    and isinstance(n.comparators[0], ast.Name)
                    and n.comparators[0].id in srcs):
                continue
            needle = n.left.value
            if len(needle) < 4 or not CODE.search(needle):
                continue
            found.add("%s::%s" % (p.name, needle[:70]))
    return found, failed, len(files)


if __name__ == "__main__":
    found, failed, nfiles = readers()
    adopt = "--adopt" in sys.argv

    if failed:
        print("  [FAIL] %d smoke(s) did not parse — this census did NOT "
              "inspect them: %s" % (len(failed), ", ".join(failed[:5])))
        sys.exit(1)

    if not CENSUS.exists():
        if adopt:
            CENSUS.write_text(json.dumps(
                {"note": "code-shaped text readers; see "
                         "smoke_text_readers_census.py",
                 "first_counted": "2026-09-14",
                 "readers": sorted(found)}, indent=1) + "\n")
            print("  ADOPTED %d reader(s) into %s" % (len(found), CENSUS))
            sys.exit(0)
        print("  [FAIL] %s is ABSENT — with no census this check cannot "
              "answer its question, and an empty answer is not a pass. Run "
              "with --adopt to record the current set." % CENSUS)
        sys.exit(1)

    recorded = set(json.loads(CENSUS.read_text())["readers"])
    added = sorted(found - recorded)
    gone = sorted(recorded - found)

    print("  %d smoke(s) scanned, %d code-shaped text reader(s) found "
          "(census holds %d)" % (nfiles, len(found), len(recorded)))
    for g in gone:
        print("  [ok] CONVERTED or removed: %s" % g)
    for a in added:
        print("  [FAIL] NEW code-shaped text reader: %s" % a)
        print("         It asserts how code is SPELLED. If the question is how "
              "the code BEHAVES, write an AST or behavioural leg instead — "
              "eight of these broke on correct code in one session. If text "
              "really is the right instrument, adopt it deliberately: "
              "python3 %s --adopt" % sys.argv[0])

    if gone and adopt:
        d = json.loads(CENSUS.read_text())
        d["readers"] = sorted(found)
        CENSUS.write_text(json.dumps(d, indent=1) + "\n")
        print("  census updated: %d -> %d" % (len(recorded), len(found)))
    elif gone:
        print("  (%d removal(s) not yet recorded — rerun with --adopt to bank "
              "the progress)" % len(gone))

    if added:
        print("\n  FAIL")
        sys.exit(1)
    print("\n  OK — the count did not grow")
    sys.exit(0)
