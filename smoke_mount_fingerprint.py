#!/usr/bin/env python3
"""SMOKE: the mount fingerprint covers every path the image mounts.

WHY. run_round.sh hashed one file of eight mounted paths and called it the
cohort guard. PROVEN blind: appending a line to remotion_batch.mjs left the old
sha byte-identical while the tree the image ships genuinely differed. Rounds 32
and 33 differ 6.1x on caption paint under shas that could not distinguish them.

WHAT MAKES THIS FIRE: a mounted path that the fingerprint does not read. That is
the whole failure, and it is silent — the guard prints a matching sha and
certifies two arms as the same code.
"""
import ast, os, sys
import mount_fingerprint as M

fails=[]
def ok(label, cond, detail=""):
    if not cond: fails.append(label + (f"  :: {detail}" if detail else ""))

paths = M.mounted_paths()

# ── DERIVED FROM THE IMAGE, so a new mount is covered the day it is written ──
src = open(M.APP, encoding="utf-8").read()
n_calls = sum(1 for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.Call)
              and getattr(n.func, "attr", "") in ("add_local_file", "add_local_dir"))
ok("every add_local_* call is resolved to a path",
   len(paths) == n_calls + 1,          # +1 for the app file itself
   f"{n_calls} add_local_* calls in the image but {len(paths)-1} resolved — an "
   "unresolved mount is an uncovered tree, and the guard would still print a sha")

# ── the paths that were invisible before, named explicitly ──────────────────
joined = " ".join(paths)
for must, why in (("agentic_editor_app.py", "the app itself"),
                  ("remotion_batch.mjs", "the batch renderer Builder-2 changes"),
                  ("src/remotion", "the Remotion source tree the caption port lives in"),
                  ("knowledge", "the knowledge the agent reads"),
                  ("type_registries.py", "mounted module"),
                  ("moodreel_editor.py", "mounted module")):
    ok(f"covers {must}", must in joined, f"uncovered: {why}")

ok("every mounted path exists", all(os.path.exists(p) for p in paths),
   f"missing: {[p for p in paths if not os.path.exists(p)]}")

# ── it produces a stable, non-empty fingerprint ─────────────────────────────
fp1, fp2 = M.fingerprint(), M.fingerprint()
ok("the fingerprint is non-empty", bool(fp1))
ok("the fingerprint is stable across calls", fp1 == fp2, f"{fp1} != {fp2}")

# ── CONTENT, not mtime: a touched-but-unchanged file must not move it ───────
import pathlib, time
_f = pathlib.Path(M.APP)
_st = _f.stat()
os.utime(_f, (_st.st_atime + 60, _st.st_mtime + 60))
try:
    ok("a touched-but-unchanged file does NOT move the fingerprint",
       M.fingerprint() == fp1,
       "an mtime-sensitive fingerprint aborts rounds for nothing and gets "
       "disabled, which is how a guard stops guarding")
finally:
    os.utime(_f, (_st.st_atime, _st.st_mtime))

# ── a missing mounted path must ABORT, never hash a subset ─────────────────
_real = M._hash_path
try:
    def _boom(p):
        if p.endswith("remotion_batch.mjs"):
            raise FileNotFoundError(p)
        return _real(p)
    M._hash_path = _boom
    try:
        M.fingerprint()
        fails.append("a MISSING mounted path did not abort — a fingerprint over "
                     "a subset certifies arms as identical while a mounted tree "
                     "differs between them")
    except SystemExit:
        pass
finally:
    M._hash_path = _real

if fails:
    print(f"MOUNT-FINGERPRINT: {len(fails)} FAILED")
    for f in fails: print("  - " + f)
    sys.exit(1)
print(f"MOUNT-FINGERPRINT: PASS ({len(paths)} mounted paths, fingerprint {fp1})")
