#!/usr/bin/env python3
"""RED proof for the card-props match check and its anti-drift cert."""
import os
import shutil
import subprocess
import sys

APP = "agentic_editor_app.py"
BAK = "/tmp/_cardprops_bak.py"
shutil.copy(APP, BAK)
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
    shutil.copy(BAK, APP)
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

for _s in ("smoke_card_props_match.py", "cert_mg_prop_keys.py"):
    rc, out = run(_s)
    print(f"RESTORED {_s} exit={rc}")
    if rc != 0:
        print(out)
        sys.exit(1)
print(f"\n{sum(r)}/{len(r)} RED-proven")
sys.exit(0 if all(r) else 1)
