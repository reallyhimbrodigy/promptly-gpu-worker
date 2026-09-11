#!/usr/bin/env python3
"""One fingerprint over EVERY path the image mounts.

WHY. run_round.sh hashed agentic_editor_app.py ALONE and called it "the mount".
The image also mounts /promptly-remotion (the whole Remotion source tree),
remotion_batch.mjs, the knowledge dir, the skills tree, the sound assets, the
asset inventory, moodreel_editor.py and type_registries.py — eight paths, one
hashed. Rounds 32 and 33 differ 6.1x on caption paint under mount shas that
could not have distinguished them, and the caption port itself lives in a tree
the sha never covered.

A cohort-integrity guard blind to the files being changed is worse than none:
it prints a matching sha and certifies that two arms ran the same code when
they did not.

THE MOUNT LIST IS DERIVED FROM THE IMAGE DEFINITION, never hand-kept. A new
add_local_* line is covered the day it is written, which is the only way this
does not rot the way the single-file version did.

  python3 mount_fingerprint.py            -> 16-char fingerprint
  python3 mount_fingerprint.py --verbose  -> per-path breakdown
"""
import ast
import hashlib
import os
import sys

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "agentic_editor_app.py")


def mounted_paths(app_path=APP):
    """Every local path the image mounts, resolved, in source order."""
    src = open(app_path, encoding="utf-8").read()
    tree = ast.parse(src)
    # Re-create the module-level path variables by exec'ing ONLY the simple
    # assignments they need. Executing the module itself would import modal and
    # build an image; this evaluates the handful of os.path expressions.
    ns = {"os": os, "__file__": app_path}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            exec(compile(ast.Module([node], []), "<mounts>", "exec"), ns)
        except Exception:
            continue          # anything needing modal or runtime state is not a path
    paths = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") in ("add_local_file",
                                                       "add_local_dir")):
            continue
        if not node.args:
            continue
        try:
            val = ast.literal_eval(node.args[0])
        except Exception:
            val = ns.get(getattr(node.args[0], "id", ""), None)
        if isinstance(val, str):
            paths.append(val)
    # The app file itself is mounted by `modal run` as the entrypoint.
    return [app_path] + paths


def _hash_path(p):
    """(sha, n_files, bytes) for a file or a directory tree.

    A MISSING path is a hard error, not a skipped one: silently hashing seven of
    eight paths is exactly the blindness this replaces.
    """
    h = hashlib.sha256()
    n = tot = 0
    if os.path.isfile(p):
        b = open(p, "rb").read()
        h.update(b)
        return h.hexdigest(), 1, len(b)
    if os.path.isdir(p):
        for root, dirs, files in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d != "node_modules"
                             and not d.startswith("."))
            for f in sorted(files):
                if f.startswith("."):
                    continue
                fp = os.path.join(root, f)
                try:
                    b = open(fp, "rb").read()
                except Exception:
                    continue
                h.update(os.path.relpath(fp, p).encode())
                h.update(b)
                n += 1
                tot += len(b)
        return h.hexdigest(), n, tot
    raise FileNotFoundError(p)


def fingerprint(verbose=False):
    paths, rows, top = mounted_paths(), [], hashlib.sha256()
    missing = []
    for p in paths:
        try:
            sha, n, tot = _hash_path(p)
        except FileNotFoundError:
            missing.append(p)
            continue
        top.update(p.encode())
        top.update(sha.encode())
        rows.append((p, sha[:12], n, tot))
    if missing:
        raise SystemExit(
            "MOUNT FINGERPRINT FAILED — these mounted paths do not exist:\n  "
            + "\n  ".join(missing)
            + "\nA fingerprint over a subset would certify arms as identical "
              "while a mounted tree differed between them.")
    fp = top.hexdigest()[:16]
    # THE COMMIT, BESIDE THE FINGERPRINT. The fingerprint is a content hash of
    # the mounted paths and is NOT a git object, so it cannot answer "which
    # tree did this round run". Builder-2 hit that on round 57: settling
    # whether a fix was in the tree took my word plus an ancestry check
    # instead of a read. HEAD is printed alongside, with -dirty when the
    # worktree differs from it, because a clean sha over a dirty tree is the
    # more expensive half of the same ambiguity.
    try:
        import subprocess as _sp
        _sha = _sp.run(["git", "rev-parse", "--short", "HEAD"],
                       capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.abspath(__file__))
                       ).stdout.strip() or "UNKNOWN"
        _dirty = _sp.run(["git", "status", "--porcelain", "--untracked-files=no"],
                         capture_output=True, text=True,
                         cwd=os.path.dirname(os.path.abspath(__file__))
                         ).stdout.strip()
        _head = _sha + ("-dirty" if _dirty else "")
    except Exception:                                             # noqa: BLE001
        _head = "UNKNOWN"
    fp = f"{fp} @{_head}"
    if verbose:
        print(f"{'path':70} {'sha':14}{'files':>7}{'bytes':>12}")
        for p, sha, n, tot in rows:
            print(f"{p[-70:]:70} {sha:14}{n:>7}{tot:>12,}")
        print(f"\n  {len(rows)} mounted path(s) -> fingerprint {fp}")
    return fp


if __name__ == "__main__":
    _v = "--verbose" in sys.argv
    _fp = fingerprint(verbose=_v)
    if not _v:
        print(_fp)
