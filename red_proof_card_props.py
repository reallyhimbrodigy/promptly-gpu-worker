#!/usr/bin/env python3
"""RED proof for the card-props match check and its anti-drift cert."""
import os
import shutil
import subprocess
import sys

APP = "agentic_editor_app.py"
# BACKUP IN MEMORY, NEVER A FILE. This was `_ORIG_SRC = "/tmp/..."` — a FIXED
# PATH SHARED ACROSS EVERY BRANCH AND WORKTREE ON THIS MACHINE. Builder-2
# observed it silently restore ANOTHER BRANCH'S agentic_editor_app.py over
# their working copy: a 914-line diff, `git status` the only witness, and
# the harness printed 19/19 RED-proven about a file it had just replaced
# with a stranger.
#
# A per-branch filename does NOT fix it: the file still outlives the
# process and can be restored from after the tree moves under it. The
# backup must not survive the run that made it.
#
# THIRD SYMPTOM OF ONE DEFECT — a fixture outside the tree can be MISSING
# (dies at import, reports nothing), DRIFTED (anchor 0x), or STALE FROM
# ANOTHER BRANCH (this one, which reports SUCCESS while corrupting the
# file under test). The third is worst because it is silent AND green.
_ORIG_SRC = open(APP, encoding="utf-8").read()
None
env = dict(os.environ, PYTHONPATH=".")


def run(smoke):
    r = subprocess.run([sys.executable, smoke], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def mut(old, new, label, expect, smoke="smoke_card_props_match.py"):
    src = open(APP, encoding="utf-8").read()
    if src.count(old) != 1:
        print(f"  HARNESS FAILURE [{label}] anchor appears {src.count(old)}x")
        return False
    open(APP, "w", encoding="utf-8").write(src.replace(old, new, 1))
    rc, out = run(smoke)
    open(APP, "w", encoding="utf-8").write(_ORIG_SRC)
    ok = rc != 0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok:
        print(f"      expected {expect!r}")
    return ok


for _s in ("smoke_card_props_match.py", "cert_mg_prop_keys.py"):
    rc, out = run(_s)
    print(f"BASELINE {_s} exit={rc}")
    assert rc == 0, out
r = []

# 1. The check stops being asked at all.
r.append(mut("            _mismatch = mg_props_mismatch(_ctype, _cprops)",
             "            _mismatch = \"\"",
             "the build stops calling mg_props_mismatch",
             "the build CALLS mg_props_mismatch"))

# 2. FOREIGN props stop being refused — round 39's exact shape.
r.append(mut("    if not (keys & declared):",
             "    if False:",
             "props addressing another component are accepted again",
             # NOT the "are REFUSED" leg: {"stat":...} is ALSO missing value and
             # label, so the missing branch refuses it with this branch dead and
             # that leg stayed green. The isolating leg names a component that
             # requires nothing, where only this branch can fire.
             "which requires nothing"))

# 3. A missing required prop stops being refused.
r.append(mut("    missing = [k for k in spec[\"required\"] if k not in keys]",
             "    missing = []",
             "a missing required prop is accepted",
             "a missing required prop is REFUSED"))

# 4. An underivable type is treated as requiring nothing — the false-green.
r.append(mut('    spec = MG_PROP_KEYS.get(str(mg_type))\n    if not spec:\n        return ""',
             '    spec = MG_PROP_KEYS.get(str(mg_type)) or {"required": [], "declared": []}\n'
             '    if False:\n        return ""',
             "an underivable type is validated against an EMPTY table",
             "is not validated rather than assumed fine"))

# 5. THE CERT: the frozen table drifts from the components.
r.append(mut('    "StatCard":        {"required": ["label", "value"],',
             '    "StatCard":        {"required": ["label"],',
             "the frozen table drifts from the component",
             "required props match the component",
             smoke="cert_mg_prop_keys.py"))

# 6. THE CERT: a type quietly drops out of validation.
r.append(mut('MG_PROPS_UNDERIVABLE = ["DeviceMockup", "EmojiCard", "EvidenceCard", "ProgressBar"]',
             'MG_PROPS_UNDERIVABLE = ["DeviceMockup", "EmojiCard", "EvidenceCard", "ProgressBar", "StatCard"]',
             "a type is added to the unvalidated set without dropping out",
             "the underivable set is exactly the four known ones",
             smoke="cert_mg_prop_keys.py"))

# 7. THE FALSE GREEN ITSELF: the name can fail a round but nothing emits it.
r.append(mut('                fail("card_props_mismatch",',
             '                _unemitted = (',
             "card_props_mismatch goes back to having no producer",
             "card_props_mismatch is actually EMITTED"))

for _s in ("smoke_card_props_match.py", "cert_mg_prop_keys.py"):
    rc, out = run(_s)
    print(f"RESTORED {_s} exit={rc}")
    if rc != 0:
        print(out)
        sys.exit(1)
print(f"\n{sum(r)}/{len(r)} RED-proven")
# A FLOOR, BECAUSE all([]) IS TRUE. A red proof whose mutation list is
# emptied — by a bad merge, a botched refactor, a commented-out block —
# reports SUCCESS. An instrument built to prove a check CAN FAIL,
# rendering its own absence as success. Found in 10 of 11 here and 16 of
# 16 on Builder-2's tree: 26 of 27 across both.
sys.exit(0 if r and all(r) else 1)
