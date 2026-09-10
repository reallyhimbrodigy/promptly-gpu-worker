#!/usr/bin/env python3
"""RED proof for the card derivation."""
import os, shutil, subprocess, sys
APP="agentic_editor_app.py"; BAK="/tmp/_cd_bak.py"
shutil.copy(APP,BAK); env=dict(os.environ,PYTHONPATH=".")
def run():
    r=subprocess.run([sys.executable,"smoke_card_derived.py"],capture_output=True,text=True,env=env)
    return r.returncode, r.stdout+r.stderr
def mut(old,new,label,expect):
    src=open(APP,encoding="utf-8").read()
    if src.count(old)!=1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
    open(APP,"w",encoding="utf-8").write(src.replace(old,new,1))
    rc,out=run(); shutil.copy(BAK,APP)
    ok=rc!=0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok: print(f"      expected {expect!r}")
    return ok
rc,out=run(); print(f"BASELINE exit={rc}"); assert rc==0,out
r=[]

# 1. A claim with no figure loses its card — the "HOURS TO EDIT" miss returning.
r.append(mut('    _words = [w for w in re.split(r"\\s+", _h) if w]\n    if len(_words) <= 5:',
             '    _words = [w for w in re.split(r"\\s+", _h) if w]\n    if False:',
             "a claim with no figure gets no card",
             "a claim with no figure still gets a card"))
# 2. The figure rule goes, so the counter-hook moments stop deriving StatCard.
r.append(mut("    if _CARD_FIGURE.search(_h):", "    if False:",
             "a quoted figure stops deriving StatCard",
             "derives StatCard"))
# 3. A sentence becomes a card — a card nobody can read.
r.append(mut("    if len(_words) <= 5:", "    if len(_words) <= 500:",
             "a whole sentence becomes a card", "a sentence is not a card"))
# 4. THE SUFFIX EATS A WORD — drop the negative lookahead and "5 MINUTES"
#    matches "5 M", which coerce_mg_props reads as FIVE MILLION. Minimal
#    mutation: the first version rewrote the whole character class and the
#    harness's own escaping mangled it into a different regex, so the mutant
#    failed for a reason that was not the one under test.
r.append(mut("(?![A-Za-z])", "",
             "the multiplier suffix eats the next word again",
             # The leg that isolates the LOOKAHEAD, not the space. "5 MINUTES"
             # is protected by the absence of an optional space, so it stays
             # green with the lookahead deleted; "30KG" is the case that needs it.
             "a suffix letter inside a word does not multiply"))
# 5. The label is filled before the split, taking the whole phrase.
r.append(mut('            _p[_k] = _l or _rest or _h', '            _p[_k] = _l or _h',
             "the label takes the whole phrase instead of the remainder",
             "the label is the remainder"))
# 6. PullQuote gets StatCard's shape — the blank-card class reintroduced.
r.append(mut('        elif _k == "text":\n            _p["text"] = _h',
             '        elif _k == "text":\n            _p["value"] = _h',
             "a derived PullQuote is handed value instead of text",
             "PullQuote gets text, not value"))
# 7. The enum comes back for the agent to pick from.
r.append(mut('                                 # card_type AND card_props are GONE.',
             '                                 "card_type": {"type": "string",\n'
             '                                     "enum": list(MG_SELECTABLE_TYPES),\n'
             '                                     "description": "pick one"},\n'
             '                                 # card_type AND card_props are GONE.',
             "the 29-name enum returns to the agent's schema",
             "card_type is gone from the agent's schema"))
# 8. The build stops deriving and the type is a default again.
r.append(mut("            _ctype, _dwhy = derive_card_type(hero, str(b.get(\"text\") or \"\"),",
             "            _ctype, _dwhy = (\"StatCard\", \"x\"); _unused = (hero, str(b.get(\"text\") or \"\"),",
             "the build stops deriving the type",
             "the build DERIVES the type"))
# 9-10. The sentence goes, on either surface.
r.append(mut("                    CARD AND TEXT ARE NOT ALTERNATIVES. A beat that quotes a",
             "                    Card and text are separate choices. A beat that quotes a",
             "the system prompt stops saying card and text are not alternatives",
             "the system prompt says card and text are not alternatives"))
# Simple unique anchor — the escaped multi-line one never matched (anchor 0x)
# and the harness said so rather than counting it RED.
r.append(mut('"text are NOT alternatives "',
             '"text are ALTERNATIVES "',
             "the schema stops saying it",
             "the tool schemas says card and text are not alternatives"))
# 11. card_hero stops saying REQUIRED — it carries the whole card contract now.
r.append(mut('"description": "REQUIRED when treatment "\n                                                    "includes \'card\': the "',
             '"description": "when treatment "\n                                                    "includes \'card\': the "',
             "card_hero stops saying REQUIRED",
             "card_hero says REQUIRED, like zoom_arc"))
# 12. THE GATE DEMANDS THE RETIRED FIELD AGAIN — round 47's control loop.
r.append(mut('                        _hero6 = str(_v.get("card_hero") or "").strip()',
             '                        _hero6 = str(_v.get("card_type") or "").strip()',
             "the acceptance gate reads a retired field again",
             "no acceptance gate reads a retired field"))
rc,out=run(); print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
sys.exit(0 if all(r) and rc==0 else 1)
