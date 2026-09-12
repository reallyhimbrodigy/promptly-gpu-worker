#!/usr/bin/env python3
"""RED proof for the card-props match check and its anti-drift cert."""
import ast
import os
import shutil
import subprocess
import sys

APP = "agentic_editor_app.py"
_ORIG_SRC = {}   # IN MEMORY, never a file
_ORIG_SRC.setdefault(APP, open(APP, encoding="utf-8").read())
env = dict(os.environ, PYTHONPATH=".")


def run(smoke):
    r = subprocess.run([sys.executable, smoke], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def mut(old, new, label, expect, smoke="smoke_card_props_match.py"):
    src = open(APP, encoding="utf-8").read()
    if src.count(old) != 1:
        print(f"  HARNESS FAILURE [{label}] anchor appears {src.count(old)}x")
        return False
    _mutant = src.replace(old, new, 1)
    # A MUTANT THAT DOES NOT PARSE NEVER RAN. The check then fails for a reason
    # unrelated to the property under test, which is a pass it did not earn.
    # None of the other guards see it: the anchor matched, the match was code.
    try:
        ast.parse(_mutant)
    except SyntaxError as _se:
        print(f"  HARNESS FAILURE [{label}] mutant does not parse: {_se.msg} "
              f"(line {_se.lineno}) — it never ran, so it proved nothing")
        return False
    open(APP, "w", encoding="utf-8").write(_mutant)
    rc, out = run(smoke)
    open(APP, "w", encoding="utf-8").write(_ORIG_SRC[APP])
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

# 8-12. THE TWO COUNTERS THAT ANSWER "DID 15 COMPONENTS GET REACHED".
# Round 63 could not answer it and I reported KEY ABSENT as `null`. Each of
# these restores one of the three real defects: setdefault-only keys, an
# unprinted counter, and a guarded print that made zero look like unwired.
r.append(mut('    led["card_conditions_named"] = []',
             '    _dropped_init_ccn = []',
             "card_conditions_named goes back to setdefault-only, so a "
             "card-less run has no key at all",
             "INITIALISED to []"))

r.append(mut('    led["card_props_seen"] = []',
             '    _dropped_init_cps = []',
             "card_props_seen goes back to setdefault-only",
             "INITIALISED to []"))

r.append(mut('    else:\n        print("  CARD CONDITIONS : %s  no card beat reached derive_card_type"\n              % ("MEASURED 0" if isinstance(_ccn, list) else "ABSENT"))',
             '    else:\n        pass',
             "the card-conditions zero goes silent again",
             "printed in BOTH states"))

r.append(mut('    else:\n        print("  CARD PROPS      : %s  no card carried props this run"\n              % ("MEASURED 0" if isinstance(_cps, list) else "ABSENT"))',
             '    else:\n        pass',
             "the card-props zero goes silent again - the `if _cps:` guard "
             "that made zero and unwired identical",
             "printed in BOTH states"))

r.append(mut('              % ("MEASURED 0" if isinstance(_ccn, list) else "ABSENT"))',
             '              % ("MEASURED 0" if isinstance(_ccn, list) else "MEASURED 0"))',
             "a missing key starts printing as a zero",
             "ABSENT word reaches"))

for _s in ("smoke_card_props_match.py", "cert_mg_prop_keys.py"):
    rc, out = run(_s)
    print(f"RESTORED {_s} exit={rc}")
    if rc != 0:
        print(out)
        sys.exit(1)
print(f"\n{sum(r)}/{len(r)} RED-proven")
# A HARNESS WITH NO LEGS MUST NOT EXIT 0. all([]) is True and 0 == 0 is
# True, so every red proof in this repo reported success on an empty leg
# list — the empty-set rule, sixteen times, inside the instruments built
# to catch exactly this. A suite PASS has to mean "ran and passed", not
# "did not run".
sys.exit(0 if r and all(r) else 1)
