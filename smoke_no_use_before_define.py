#!/usr/bin/env python3
"""No body reaches registration with a temporal-dead-zone ReferenceError.

WHY THIS EXISTS. ChatCut REFUSED CaptionMatch and QuoteCard — "Undefined
identifier 'text'" — because removing a placeholder branch left a `const fit`
line reading a binding declared twenty lines BELOW it. `const` has a temporal
dead zone, so that is a ReferenceError their validator catches statically, and
NO LEG OF MINE EXECUTED OR SCOPE-CHECKED AN EDITED BODY. Every check I had read
the text of the file.

WHY IT IS NOT A REGEX, measured rather than argued. Builder 1 wrote this rule
twice with brace-counting and BOTH VERSIONS REFUSED 37 OF 37 BODIES CHATCUT HAD
ACCEPTED. A reference inside a nested function is DEFERRED — the body runs after
the declaration — so it is legal and ubiquitous. Only a same-scope reference is
the error. Telling those apart needs to know which function encloses the
reference, which is a scope analysis; eslint-scope is the library that does it
and is what eslint's own rule stands on.

HIS TWO STICKYNOTES FINDINGS WERE BOTH FALSE POSITIVES, and they are the two
ways a regex fails here:
  'notes'  in port/build — the hits are at lines 21, 41 and 43, all COMMENTS.
           The real declaration is line 111 and every use follows it. A match
           landing in prose.
  'script' in the baked blob — THREE SEPARATE BINDINGS in three scopes: a
           for-of loop head at 61, and two different function-locals at 74 and
           81. The use at 62 resolves to the loop's binding, not to line 74's.
           Shadowing read as use-before-declare.
Both are exactly what scope analysis answers and text cannot.

CALIBRATION IS THE WHOLE VALUE. The 37 accepted are the negative population and
they must all pass; the two refused are the positives and must all fail. A rule
that convicts correct components is not a stricter rule, it is a broken one.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CHECKER = os.path.join(HERE, "check_use_before_define.mjs")
BAKED = os.path.join(HERE, "chatcut_registry_baked.json")

FAILS = []
NLEGS = 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def run(paths):
    """-> (exit, stdout). Bare, no pipe: the status is the checker's."""
    p = subprocess.run([ "node", CHECKER ] + list(paths),
                       capture_output=True, text=True, cwd=HERE)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def extract_baked(outdir):
    """The blobs that ACTUALLY register the catalogue components."""
    import re as _re
    d = json.load(open(BAKED, encoding="utf-8"))
    os.makedirs(outdir, exist_ok=True)
    n = 0

    def walk(o, path=""):
        nonlocal n
        if isinstance(o, dict):
            if isinstance(o.get("code"), str) and "const Component" in o["code"]:
                nm = o.get("name") or o.get("id") or path
                safe = _re.sub(r"[^A-Za-z0-9_.-]", "_", str(nm))[:60]
                open(os.path.join(outdir, safe + ".jsx"), "w").write(o["code"])
                n += 1
            for k, v in o.items():
                walk(v, path + "/" + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + "[%d]" % i)
    walk(d)
    return n


def main():
    if not os.path.isfile(CHECKER):
        print("HARNESS FAILURE: no checker at %s" % CHECKER)
        return 2

    # L0 THE NEGATIVE POPULATION: every blob ChatCut accepted must pass. This is
    # the leg that caught Builder 1 twice, on the first run, both times.
    tmp = os.path.join(HERE, "_ubd_baked")
    try:
        n = extract_baked(tmp)
        files = sorted(os.path.join(tmp, f) for f in os.listdir(tmp) if f.endswith(".jsx"))
        rc, out = run(files)
        leg("L0 the_37_chatcut_accepted_all_pass", n == 37 and rc == 0,
            "%d baked blob(s), checker exit=%d %s"
            % (n, rc, "" if rc == 0 else out.strip().splitlines()[-1:]))

        # L1 THE POSITIVE POPULATION, derived not invented: take a real body and
        # move its declaration BELOW the use, which is exactly what the
        # placeholder removal did. If this does not fire, the rule is asleep.
        src = open(os.path.join(HERE, "port", "bodies", "CaptionMatch.jsx"),
                   encoding="utf-8").read()
        decl = "  const text = String(props.text);\n"
        broken_ok = decl in src
        if broken_ok:
            broken = src.replace(decl, "", 1).replace(
                "  const rootStyle", decl + "  const rootStyle", 1)
            bp = os.path.join(tmp, "_BROKEN_CaptionMatch.jsx")
            open(bp, "w").write(broken)
            brc, bout = run([bp])
            broken_ok = brc != 0 and "USE_BEFORE_DEFINE" in bout
        leg("L1 a_declaration_moved_below_its_use_is_caught", broken_ok,
            "derived from the real body by moving `const text` below `rootStyle`")

        # L2 A DEFERRED REFERENCE IS NOT CONVICTED. The exact shape that made
        # both regex attempts refuse all 37.
        deferred = os.path.join(tmp, "_DEFERRED.jsx")
        open(deferred, "w").write(
            "const Component = ({ item }) => {\n"
            "  const render = () => later;\n"          # nested, deferred: legal
            "  const later = 1;\n"
            "  return render();\n};\n")
        drc, _ = run([deferred])
        leg("L2 a_nested_deferred_reference_is_legal", drc == 0,
            "nested arrow reading a later outer const: exit=%d (want 0)" % drc)

        # L3 AN UNPARSEABLE BODY IS UNKNOWN, NEVER CLEAN. Loosening the rule on
        # a parse failure is how a whole class walks through.
        bad = os.path.join(tmp, "_UNPARSEABLE.jsx")
        open(bad, "w").write("const Component = ({ item }) => { const x = ;\n")
        prc, pout = run([bad])
        leg("L3 unparseable_is_reported_not_passed",
            prc != 0 and "PARSE_ERROR" in pout,
            "exit=%d, states: %s" % (prc, "PARSE_ERROR" if "PARSE_ERROR" in pout else pout[:60]))
    finally:
        if os.path.isdir(tmp):
            for f in os.listdir(tmp):
                os.remove(os.path.join(tmp, f))
            os.rmdir(tmp)

    # L4 EVERY BODY ON THE REGISTRATION PATH IS CLEAN RIGHT NOW.
    live = sorted(os.path.join(HERE, "port", "build", f)
                  for f in os.listdir(os.path.join(HERE, "port", "build"))
                  if f.endswith(".jsx"))
    lrc, lout = run(live)
    leg("L4 every_port_build_body_is_clean", bool(live) and lrc == 0,
        "%d body(ies); %s" % (len(live), "clean" if lrc == 0 else lout.strip()[-200:]))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
