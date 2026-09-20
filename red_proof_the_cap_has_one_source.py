#!/usr/bin/env python3
"""RED PROOF — the velocity cap has ONE source, and every emitted copy agrees with it.

WHY THIS GATE EXISTS (Zac, 2026-09-19). A ChatCut motion graphic is one inline
blob with no imports, so the 316-line velocity cap has to travel INSIDE each
ported zoom. Seven hand-maintained copies of one rule is the August agent-config
incident exactly: a file duplicated five times that no longer agreed with itself.
So the blobs are GENERATED from the module and never hand-edited, and this gate
asserts it: any edit to the cap re-emits every blob or fails here.

FOUR CHECKS, THREE OF THEM DRIVEN RED BELOW.
  1. every built blob carries the CURRENT sha256 of velocity-cap.ts
  2. a fresh emit byte-equals every built blob
  3. the emitted JS computes what the TypeScript computes (2,000+ comparisons,
     exact equality — Node runs the .ts directly, so both sides are executable
     and this is MEASURED, not assumed)
  4. every body carries exactly one marker, and no built blob still carries one

WHY 3 IS NOT REDUNDANT WITH 2. A byte-compare proves the blobs were generated.
It cannot prove the generator still generates the right thing: a stripper change,
or a `.replace` in the emitter that ate a line, would byte-compare clean against
its own output forever.
"""
import hashlib
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
CAP = "src/remotion/src/zoom/shared/velocity-cap.ts"
MARKER = "// @@VELOCITY_CAP@@"
NODE_TIMEOUT_S = 120


def _node(args, cwd):
    """-> (rc, out). A HANG IS A HARNESS FAILURE: rc 124 is reserved for it."""
    try:
        r = subprocess.run(["node"] + args, cwd=str(cwd), capture_output=True,
                           text=True, timeout=NODE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return 124, "*** node did not exit within %ds" % NODE_TIMEOUT_S
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run(tree):
    """-> [(name, ok, read)] for the tree at `tree`. Every row carries what it READ."""
    tree = pathlib.Path(tree)
    rows = []
    sha = hashlib.sha256((tree / CAP).read_bytes()).hexdigest()

    built = sorted((tree / "port" / "build").glob("*.jsx"))
    bodies = sorted((tree / "port" / "bodies").glob("*.jsx"))
    rows.append(("a built blob exists for every body", len(built) == len(bodies) and len(bodies) > 0,
                 "%d bodies, %d built" % (len(bodies), len(built))))

    # ONLY THE BLOBS THAT CARRY THE CAP. A component with no ramp has no cap
    # section and so no sha to check — but it may only be exempt because its BODY
    # declared `NO VELOCITY CAP:`, never because the section went missing. An
    # exemption nobody declared is the same silent absence the whole gate is for.
    stale, n_cap = [], 0
    for b in built:
        t = b.read_text(encoding="utf-8")
        m = re.search(r"sha256:\s+([0-9a-f]{64})", t)
        if m:
            n_cap += 1
            if m.group(1) != sha:
                stale.append("%s: marker %s != source %s" % (b.name, m.group(1)[:12], sha[:12]))
            continue
        body = tree / "port" / "bodies" / b.name
        declared = body.exists() and "NO VELOCITY CAP:" in body.read_text(encoding="utf-8")
        if not declared:
            stale.append("%s: no cap section and its body never declared one" % b.name)
    rows.append(("every capped blob carries the CURRENT sha, and every uncapped one declared it",
                 not stale, "; ".join(stale) if stale else "%d capped at %s, %d declared uncapped"
                 % (n_cap, sha[:12], len(built) - n_cap)))

    rc, out = _node(["port/emit_zoom_component.mjs", "--check"], tree)
    rows.append(("a fresh emit byte-equals every built blob", rc == 0,
                 out.strip().replace("\n", " | ")[:220] or "rc=%d" % rc))

    rc, out = _node(["port/cap_parity.mjs"], tree)
    rows.append(("the emitted JS computes what the TypeScript computes", rc == 0,
                 out.strip().splitlines()[-1][:220] if out.strip() else "rc=%d" % rc))

    bad = []
    capped = uncapped = 0
    for b in bodies:
        t = b.read_text(encoding="utf-8")
        n = sum(1 for l in t.splitlines() if l.strip() == MARKER)
        if n == 1:
            capped += 1
        elif n == 0 and "NO VELOCITY CAP:" in t:
            uncapped += 1
        else:
            bad.append("%s has %d markers and %s reason"
                       % (b.name, n, "no" if "NO VELOCITY CAP:" not in t else "a"))
    for b in built:
        if MARKER in b.read_text(encoding="utf-8"):
            bad.append("%s still carries the marker" % b.name)
    rows.append(("every body either carries the cap or says why it does not", not bad,
                 "; ".join(bad) if bad else "%d capped, %d declared uncapped, %d blobs"
                 % (capped, uncapped, len(built))))
    return rows


# (label, file, old, new, the leg it must drive red)
REDS = [
    ("the cap source is edited without re-emitting", CAP,
     "export const PEAK_DISPLACEMENT_CAP_PX = 11;",
     "export const PEAK_DISPLACEMENT_CAP_PX = 12;",
     "every capped blob carries the CURRENT sha, and every uncapped one declared it"),
    ("a built blob is hand-edited", "port/build/SmoothPush.jsx",
     "const betas = [1.0, 0.85, 0.7, 0.6, MIN_BLEND_FRACTION];",
     "const betas = [1.0];",
     "a fresh emit byte-equals every built blob"),
    ("the emitter drops a line on its way out", "port/emit_zoom_cap.mjs",
     '.map((l) => l.replace(/^export\\s+/, "").replace(/\\s+$/, ""))',
     '.map((l) => l.replace(/^export\\s+/, "").replace(/\\s+$/, "")).filter((l) => !l.includes("k * bIn *"))',
     "the emitted JS computes what the TypeScript computes"),
    ("a ramping body loses its marker", "port/bodies/SmoothPush.jsx",
     "  // @@VELOCITY_CAP@@",
     "  // the cap used to go here",
     "a fresh emit byte-equals every built blob"),
    ("a blob silently loses its cap section", "port/build/SmoothPush.jsx",
     "   sha256:  ",
     "   sha-was:  ",
     "every capped blob carries the CURRENT sha, and every uncapped one declared it"),
    ("an uncapped body stops saying why it is uncapped", "port/bodies/StepZoom.jsx",
     " * NO VELOCITY CAP: there is no ramp to cap.",
     " * There is no ramp to cap.",
     "a fresh emit byte-equals every built blob"),
]


def main():
    print("GREEN — the tree as it stands")
    rows = run(ROOT)
    for name, ok, read in rows:
        print("  [%s] %-58s %s" % ("ok" if ok else "FAIL", name, read))
    green = all(ok for _, ok, _ in rows)

    print("\nRED PROOF — each check driven red against the thing it names")
    red_ok = True
    for label, rel, old, new, leg in REDS:
        with tempfile.TemporaryDirectory(prefix="capsrc_") as td:
            # A UNIQUE COPY PER INVOCATION. An isolated copy is isolated from the
            # TREE and nothing else; a fixed path is shared by every caller that
            # computes it the same way, and the loser reports a missing SOURCE
            # file, which reads as a broken environment rather than as a race.
            dst = pathlib.Path(td) / "tree"
            subprocess.run(["rsync", "-a", "--exclude", ".git", "--exclude", ".worktrees",
                            str(ROOT) + "/", str(dst) + "/"], check=True, capture_output=True)
            p = dst / rel
            s = p.read_text(encoding="utf-8")
            if s.count(old) != 1:
                print("  [VACUOUS] %-46s anchor appears %dx in %s" % (label, s.count(old), rel))
                red_ok = False
                continue
            p.write_text(s.replace(old, new), encoding="utf-8")
            after = {n: ok for n, ok, _ in run(dst)}
            reads = {n: r for n, _, r in run(dst)}
            if after.get(leg, True):
                print("  [NOT RED] %-46s '%s' still passes" % (label, leg))
                red_ok = False
            else:
                print("  [RED]     %-46s -> %s" % (label, reads.get(leg, "")[:88]))
    ok = green and red_ok
    print("\n%s" % ("OK — one source, %d emitted copies, %d/%d red"
                    % (len(list((ROOT / "port" / "build").glob("*.jsx"))), len(REDS), len(REDS))
                    if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
