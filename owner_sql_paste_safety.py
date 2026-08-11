"""PASTE-SAFETY VALIDATOR for Desktop/Promptly Reports/*.sql

A file passes only if its ENTIRE contents can be select-all -> copy -> paste ->
Run in the Supabase SQL editor with zero editing. That means: pure SQL plus
`--` comments. No markdown of any kind.

Two independent legs:
  1. CONTAMINATION  — regex for markdown artifacts a Postgres parser would reject
                      (fences, ATX headers, pipe tables, bold, bare prose).
  2. PARSE          — sqlglot, postgres dialect, statement by statement.
"""
import glob
import os
import re
import sys

sys.path.insert(0, "/tmp/sqlvenv/lib/python3.14/site-packages")
import sqlglot
from sqlglot.errors import ParseError

FOLDER = "/Users/zaclibman/Desktop/Promptly Reports"


def contamination(text):
    bad = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        if s.startswith("```"):
            bad.append((i, "code fence", line))
        elif re.match(r"^#{1,6}\s", s):
            bad.append((i, "markdown header", line))
        elif s.startswith("|") and s.endswith("|"):
            bad.append((i, "markdown table row", line))
        elif s.startswith("**") or s.startswith("> "):
            bad.append((i, "markdown emphasis/quote", line))
        elif re.match(r"^\*\s|^\d+\.\s+[A-Z]", s) and not s.lower().startswith(
                ("select", "insert", "update", "delete", "create", "alter", "with")):
            bad.append((i, "markdown list / prose", line))
    return bad


def parse_check(text):
    # Strip comments for statement splitting; sqlglot handles them, but a bare
    # comment-only trailing chunk parses to None which is fine, not an error.
    try:
        stmts = sqlglot.parse(text, read="postgres")
    except ParseError as e:
        return [f"PARSE ERROR: {str(e)[:300]}"]
    except Exception as e:
        return [f"PARSE EXCEPTION: {type(e).__name__}: {str(e)[:200]}"]
    return [] if stmts else ["no statements parsed"]


def main():
    files = sorted(glob.glob(os.path.join(FOLDER, "**", "*.sql"), recursive=True))
    if not files:
        print("no .sql files found")
        return 1
    fails = 0
    for f in files:
        text = open(f, encoding="utf-8", errors="replace").read()
        c = contamination(text)
        p = parse_check(text)
        rel = os.path.relpath(f, FOLDER)
        if not c and not p:
            n = len([s for s in text.split(";") if s.strip() and not all(
                l.strip().startswith("--") or not l.strip() for l in s.splitlines())])
            print(f"  PASTE-SAFE   {rel}  (~{n} statements)")
        else:
            fails += 1
            print(f"  ✗ FAIL       {rel}")
            for ln, why, txt in c[:4]:
                print(f"       line {ln}: {why}: {txt[:70]}")
            for e in p[:2]:
                print(f"       {e}")
    print(f"\n{len(files) - fails}/{len(files)} paste-safe")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
