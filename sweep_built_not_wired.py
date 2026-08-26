#!/usr/bin/env python3
"""BUILT-NOT-WIRED SWEEP — find the inert code before it finds us `[Rule 2]`.

SIX instances were found BY ACCIDENT while working on something else:
  the BOOLEAN preview column, an unmounted moodreel_editor, _progressive_enabled
  reading only a dark global, an unset KNOWN_OUTAGE_UNTIL, the memory-snapshot
  env freeze, unallowlisted analytics events, the extra="forbid" schema mirror
  that silently blocked motionTokens — and, this week, design_system.py and
  _keyword_emphasis_spec, both fully written, cert-green and never called.

Six by accident implies more by search. This searches.

THREE SHAPES, because each fails differently and each has bitten:

  zero-import module    a .py that nothing imports. Ships in the image, costs
                        build time, does nothing. (design_system.py, until it
                        was wired.)
  zero-call function    defined, tested, never invoked. The most dangerous
                        shape: it passes its cert forever. (_keyword_emphasis_
                        spec, until it was wired.)
  one-sided event       an analytics event WRITTEN but never READ, or READ but
                        never WRITTEN. A read-with-no-writer reports a confident
                        zero; a write-with-no-reader is a cost with no answer.

WHAT THIS IS NOT: a dead-code linter. It reports CANDIDATES with the evidence,
because plenty of legitimate code is reached dynamically (entrypoints, Modal
decorators, getattr dispatch). The output is a list to adjudicate, not to delete
— and §4.8 says dead-purpose code goes, so adjudicating it is the point.

    python3 sweep_built_not_wired.py            # this repo
    python3 sweep_built_not_wired.py <dir> ...  # other trees
"""
import ast
import json
import os
import re
import sys

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", ".worktrees", ".next", "coverage",
             # stale agent worktrees and vendored model code are not the live
             # tree; including them buried 5 real findings under 174 of noise
             ".claude", "models", "golden", "bundle"}
# Files that are entrypoints by nature — never "unimported" in a meaningful way.
ENTRYPOINT_HINTS = ("modal_app.py", "validate_deploy.py", "deploy.sh",
                    "sweep_built_not_wired.py", "red_proof.py")


def _py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def _js_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.endswith((".js", ".mjs", ".ts")):
                yield os.path.join(dirpath, f)


def sweep_python(root):
    files = list(_py_files(root))
    blobs = {}
    for f in files:
        try:
            blobs[f] = open(f, encoding="utf-8", errors="ignore").read()
        except Exception:
            pass
    all_src = "\n".join(blobs.values())

    # ── zero-import modules ────────────────────────────────────────────────
    unimported = []
    for f, src in blobs.items():
        mod = os.path.basename(f)[:-3]
        if os.path.basename(f) in ENTRYPOINT_HINTS or mod.startswith("cert_") \
                or mod.startswith("test_") or mod.startswith("probe_") \
                or mod.startswith("sweep_"):
            continue
        # imported by name anywhere else, or mounted into an image?
        pat = re.compile(rf"\b(?:import\s+{re.escape(mod)}\b"
                         rf"|from\s+{re.escape(mod)}\s+import"
                         rf"|import_module\(\s*['\"]{re.escape(mod)}['\"]"
                         rf"|['\"]{re.escape(mod)}\.py['\"])")
        others = "\n".join(v for k, v in blobs.items() if k != f)
        if not pat.search(others):
            unimported.append({"file": os.path.relpath(f, root), "module": mod})

    # ── cert-only modules ──────────────────────────────────────────────────
    # THE SHAPE THIS SWEEP COULD NOT SEE, found 2026-08-18. duration_target and
    # mechanical_router were built, cert-green, committed and DEPLOYED, with no
    # import, no mount and no call site anywhere in production — and this sweep
    # called them wired, because `others` includes cert files and each module IS
    # imported: by its own cert. A module whose only caller is the thing that
    # tests it is exactly as unreachable as one nobody imports at all, and it is
    # harder to notice, because it has a green check next to its name.
    cert_only = []
    for f, src in blobs.items():
        mod = os.path.basename(f)[:-3]
        base = os.path.basename(f)
        if base in ENTRYPOINT_HINTS or mod.startswith(
                ("cert_", "test_", "probe_", "sweep_", "read_", "heal_")):
            continue
        pat = re.compile(rf"\b(?:import\s+{re.escape(mod)}\b"
                         rf"|from\s+{re.escape(mod)}\s+import"
                         rf"|import_module\(\s*[\'\"]{re.escape(mod)}[\'\"]"
                         rf"|[\'\"]{re.escape(mod)}\.py[\'\"])")
        prod_importers, any_importers = [], []
        for k, v in blobs.items():
            if k == f or not pat.search(v):
                continue
            kb = os.path.basename(k)
            any_importers.append(kb)
            if not kb.startswith(("cert_", "test_", "probe_", "sweep_")):
                prod_importers.append(kb)
        if any_importers and not prod_importers:
            cert_only.append({"file": os.path.relpath(f, root), "module": mod,
                              "by": sorted(set(any_importers))[:3]})

    # ── zero-call functions ────────────────────────────────────────────────
    uncalled = []
    for f, src in blobs.items():
        base = os.path.basename(f)
        if base.startswith(("cert_", "test_", "probe_", "sweep_")):
            continue
        try:
            tree = ast.parse(src)
        except Exception:
            continue
        for node in tree.body:            # top level only
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name
            if name.startswith("__") or name == "main":
                continue
            # decorated functions are dispatched by their decorator (Modal, checks)
            if node.decorator_list:
                continue
            uses = len(re.findall(rf"\b{re.escape(name)}\s*\(", all_src))
            # 1 use == the definition itself
            if uses <= 1 and f"\"{name}\"" not in all_src and f"'{name}'" not in all_src:
                uncalled.append({"file": os.path.relpath(f, root), "func": name,
                                 "line": node.lineno})
    return unimported, uncalled, cert_only


def sweep_events(roots):
    """analytics_events written vs read, across every tree given."""
    written, read = {}, {}
    for root in roots:
        for f in list(_py_files(root)) + list(_js_files(root)):
            try:
                src = open(f, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            rel = os.path.relpath(f, root)
            for m in re.finditer(r'["\']event["\']\s*:\s*["\']([a-z0-9_]+)["\']', src):
                written.setdefault(m.group(1), set()).add(rel)
            for m in re.finditer(r'\.eq\(\s*["\']event["\']\s*,\s*["\']([a-z0-9_]+)["\']', src):
                read.setdefault(m.group(1), set()).add(rel)
            for m in re.finditer(r'\.in_?\(\s*["\']event["\']\s*,\s*\[([^\]]+)\]', src):
                for e in re.findall(r'["\']([a-z0-9_]+)["\']', m.group(1)):
                    read.setdefault(e, set()).add(rel)
    return written, read


def main(argv):
    roots = argv[1:] or [os.path.dirname(os.path.abspath(__file__))]
    roots = [os.path.abspath(r) for r in roots]
    print("BUILT-NOT-WIRED SWEEP")
    print("=" * 72)
    total = 0
    for root in roots:
        unimported, uncalled, cert_only = sweep_python(root)
        print(f"\n## {root}")
        print(f"\n  ZERO-IMPORT MODULES ({len(unimported)}) — in the tree, imported by nothing:")
        for u in sorted(unimported, key=lambda x: x["file"])[:40]:
            print(f"    {u['file']}")
        print(f"\n  CERT-ONLY MODULES ({len(cert_only)}) — imported ONLY by their own "
              f"cert/harness, so unreachable from production:")
        for u in sorted(cert_only, key=lambda x: x["file"]):
            print(f"    {u['file']}   (only: {', '.join(u['by'])})")
        print(f"\n  ZERO-CALL TOP-LEVEL FUNCTIONS ({len(uncalled)}) — defined, never invoked:")
        for u in sorted(uncalled, key=lambda x: (x["file"], x["line"]))[:60]:
            print(f"    {u['file']}:{u['line']}  {u['func']}()")
        total += len(unimported) + len(uncalled) + len(cert_only)

    written, read = sweep_events(roots)
    w_only = sorted(set(written) - set(read))
    r_only = sorted(set(read) - set(written))
    print(f"\n## ANALYTICS EVENTS (across {len(roots)} tree(s))")
    print(f"\n  WRITTEN, NEVER READ ({len(w_only)}) — a cost with no answer:")
    for e in w_only:
        print(f"    {e:38} written in {sorted(written[e])[0]}")
    print(f"\n  READ, NEVER WRITTEN ({len(r_only)}) — reports a CONFIDENT ZERO:")
    for e in r_only:
        print(f"    {e:38} read in {sorted(read[e])[0]}")
    total += len(w_only) + len(r_only)
    print(f"\n{'=' * 72}\n  {total} candidates. These are CANDIDATES, not verdicts —")
    print("  dynamic dispatch, decorators and entrypoints are legitimately 'uncalled'.")
    print("  §4.8: dead-purpose code goes. Adjudicating the list is the point.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
