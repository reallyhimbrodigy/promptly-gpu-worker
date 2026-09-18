#!/usr/bin/env python3
"""RED proof for smoke_chatcut_calls_match_the_schema.

The mutations reinstate the two defects that actually shipped — preview_timeline
at limit 200 and browse_library at limit 200 — plus an unknown key and a bad
enum, because `additionalProperties:false` makes those equally fatal and no run
has ever exercised them.
"""
import ast
import io
import re
import subprocess
import sys

sys.path.insert(0, ".")
import red_proof_anchor as RA                                   # noqa: E402

TARGET = "chatcut_job_app.py"
SMOKE = "smoke_chatcut_calls_match_the_schema.py"

MUTATIONS = [
    ("preview_timeline goes back to limit 200",
     '"views": ["timeline"], "limit": 100,',
     '"views": ["timeline"], "limit": 200,',
     "no numeric argument exceeds its maximum", None),
    ("browse_library goes back to limit 200",
     '{"category": "sound-effects", "limit": 30},',
     '{"category": "sound-effects", "limit": 200},',
     "no numeric argument exceeds its maximum", None),
    ("a key the schema does not accept",
     '{"projectId": pid, "views": ["timeline"], "limit": 100},',
     '{"projectId": pid, "views": ["timeline"], "limit": 100, "sortBy": "x"},',
     "no call passes a key the schema does not accept", None),
    # ANCHORED WITH ENOUGH CONTEXT TO BE UNIQUE — two submit_export sites
    # carry the same key pair, and the count guard refused the ambiguous one
    # rather than picking a site at random.
    ("a closed enum is violated",
     '{"projectId": pid, "format": "video", "codec": "h264",\n'
     '                        "resolution": "720p"})',
     '{"projectId": pid, "format": "movie", "codec": "h264",\n'
     '                        "resolution": "720p"})',
     "no closed enum is violated", None),
]


def run_smoke():
    r = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def leg_failed(out, leg):
    return re.search(r"^\s+%s\s+FAIL\s*$" % re.escape(leg), out, re.M) is not None


def main():
    src = io.open(TARGET, encoding="utf-8").read()
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated smoke not green (rc=%d)\n%s"
              % (rc, out[-700:]))
        sys.exit(2)
    red, bad = 0, []
    for label, anchor, repl, leg, pre in MUTATIONS:
        if pre is not None and pre not in src:
            bad.append("VACUOUS: %s" % label)
            print("  [VACUOUS] %s" % label)
            continue
        mode, mutant = RA.apply_one(src, anchor, repl)
        if mutant is None:
            bad.append("HARNESS FAILURE: %s — anchor %s" % (label, mode))
            print("  [ANCHOR %s] %s" % (mode, label))
            continue
        try:
            ast.parse(mutant)
        except SyntaxError as e:
            bad.append("HARNESS FAILURE: %s — will not parse: %s" % (label, e))
            print("  [UNPARSEABLE] %s" % label)
            continue
        io.open(TARGET, "w", encoding="utf-8").write(mutant)
        try:
            rc2, out2 = run_smoke()
        finally:
            io.open(TARGET, "w", encoding="utf-8").write(src)
        hit = leg_failed(out2, leg)
        if rc2 != 0 and hit:
            red += 1
            print("  [RED]  %-42s (%s) -> %r failed" % (label, mode, leg))
        else:
            bad.append("NOT RED: %s — rc=%d leg_failed=%s" % (label, rc2, hit))
            print("  [NOT RED] %-40s rc=%d leg_failed=%s" % (label, rc2, hit))
    if io.open(TARGET, encoding="utf-8").read() != src:
        print("\nRESIDUE: restoring %s" % TARGET)
        io.open(TARGET, "w", encoding="utf-8").write(src)
        bad.append("RESIDUE")
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    for b in bad:
        print("  " + b)
    sys.exit(0 if red and red == len(MUTATIONS) and not bad else 1)


if __name__ == "__main__":
    main()
