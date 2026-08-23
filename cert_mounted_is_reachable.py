#!/usr/bin/env python3
"""cert_mounted_is_reachable.py — A MODULE IN THE IMAGE MUST BE REACHABLE.

MEASURED 2026-08-18 by sweep_built_not_wired.py, verbatim: "duration_target and
mechanical_router were built, cert-green, committed and DEPLOYED, with no
import, no mount and no call site anywhere in production." Both were cert-green
the whole time, because both certs drive the modules in isolation with injected
fakes — deleting the call site leaves them green.

The sweep that caught it was never wired into anything, so the regression it
exists to prevent has been ungated ever since. This is that gate.

WHY NOT WIRE THE SWEEP DIRECTLY. It exits 0 always and reports 142 CANDIDATES —
mostly `modal run` entrypoints that are legitimately imported by nothing. As a
gate it is either vacuous (always passes) or blocking (always fails). Baselining
142 noisy entries would ratchet noise, not protect the invariant.

THE INVARIANT INSTEAD: every module mounted into the Modal image via
add_local_file must be REACHABLE in the import graph rooted at the production
entrypoints. Mounting costs image weight and implies intent; a mounted module
nothing can reach is either dead or about to be found dead in production.

TRANSITIVE ON PURPOSE. A first cut checked handler.py only and flagged
guidance_registry.py — which is imported by unified_core.py, which handler
imports. A one-file check produces false positives that get waved through, and a
gate people learn to wave through is worse than no gate.

    python3 cert_mounted_is_reachable.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOTS = ("handler.py", "modal_app.py")
# Legitimately mounted without an importer: data/assets and the render tree.
NON_MODULE = (".mjs", ".json", ".ts", ".tsx", ".txt", ".md", ".css", ".html")


def _imports(path):
    try:
        src = open(os.path.join(HERE, path), encoding="utf-8").read()
    except OSError:
        return set()
    out = set()
    for m in re.finditer(r"^\s*(?:from\s+([a-zA-Z_][\w]*)\s+import|import\s+([a-zA-Z_][\w]*))",
                         src, re.M):
        out.add(m.group(1) or m.group(2))
    return out


def main():
    fails = []
    modal_src = open(os.path.join(HERE, "modal_app.py"), encoding="utf-8").read()
    mounts = re.findall(r"add_local_file\(\s*[\"']([^\"']+)[\"']", modal_src)
    mods = sorted({os.path.basename(f)[:-3] for f in mounts
                   if f.endswith(".py") and not f.endswith(NON_MODULE)})
    print(f"  mounted python modules: {len(mods)}")
    if not mods:
        print("  FAIL: found ZERO mounted modules — the matcher is broken, and a "
              "check that inspects nothing passes everything")
        return 1

    # transitive closure from the production entrypoints
    seen, stack = set(), list(ROOTS)
    while stack:
        cur = stack.pop()
        name = cur[:-3] if cur.endswith(".py") else cur
        if name in seen:
            continue
        seen.add(name)
        for imp in _imports(name + ".py"):
            if imp not in seen and os.path.exists(os.path.join(HERE, imp + ".py")):
                stack.append(imp + ".py")
    print(f"  modules reachable from {list(ROOTS)}: {len(seen)}")

    # KNOWN DEAD, NAMED — not an allowlist that hides things. Each entry records
    # WHY it is unreachable and what retires it. Being here is a filed decision,
    # not approval: modal_app.py itself calls the RIFE entrypoint "DEAD CODE —
    # no live callers … a §4.8 removal candidate: a dead H100 entrypoint is one
    # accidental call from ~$0.00117/s". They stay mounted until that removal
    # lands; a NEW unreachable module is not covered and fails.
    KNOWN_DEAD = {
        "rife_normalize": "RIFE interpolation entrypoint — modal_app.py marks it "
                          "DEAD CODE with no live callers; §4.8 removal candidate",
        "RIFE_HDv3":      "RIFE model class, only reachable via rife_normalize",
        "IFNet_HDv3":     "RIFE network, only reachable via rife_normalize",
        "refine":         "RIFE refinement net, only reachable via rife_normalize",
    }
    unreachable = [m for m in mods if m not in seen and m not in KNOWN_DEAD]
    still_dead = [m for m in mods if m not in seen and m in KNOWN_DEAD]
    if still_dead:
        print(f"  known-dead, still mounted ({len(still_dead)}): {still_dead}")
        for m in still_dead:
            print(f"      {m:18} {KNOWN_DEAD[m]}")
    # A KNOWN_DEAD entry that became reachable is ALSO drift — it means someone
    # wired it back up without retiring the note, and the note now lies.
    revived = [m for m in KNOWN_DEAD if m in seen]
    if revived:
        fails.append(f"KNOWN_DEAD module(s) are now REACHABLE: {revived}. Either "
                     f"they were deliberately revived (retire the entry) or "
                     f"something imports dead code by accident.")
    for m in unreachable:
        fails.append(f"{m}.py is MOUNTED into the Modal image but is reachable "
                     f"from neither handler.py nor modal_app.py, transitively. It "
                     f"costs image weight and cannot run — the exact shape that "
                     f"shipped mechanical_router and duration_target dead for "
                     f"weeks, cert-green throughout.")
    print(f"  mounted-but-unreachable: {unreachable or 'none'}")

    # NON-VACUITY: the closure must actually resolve real modules, or every
    # mounted module would look unreachable and this would fail wholesale.
    known = {"surgical_ops", "recipe_eval", "unified_core"}
    if not known & seen:
        fails.append("the import closure resolved none of the known-live modules "
                     "— the walker is broken, not the tree")

    print()
    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print("  CERT MOUNTED-IS-REACHABLE: FAIL")
        return 1
    print("  CERT MOUNTED-IS-REACHABLE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
