#!/usr/bin/env python3
"""RED proof: every absence must stay spoken, and the filter must stay on."""
import os, shutil, subprocess, sys
APP="agentic_editor_app.py"; IDX="reference_index.json"
BAK="/tmp/_rr_app.py"; BAKI="/tmp/_rr_idx.json"
shutil.copy(APP,BAK); shutil.copy(IDX,BAKI)
env=dict(os.environ,PYTHONPATH=".")
def run():
    r=subprocess.run([sys.executable,"smoke_reference_retrieval.py"],
                     capture_output=True,text=True,env=env)
    return r.returncode, r.stdout+r.stderr
def mut(path,old,new,label,expect):
    bak = BAK if path==APP else BAKI
    src=open(path,encoding="utf-8").read()
    if src.count(old)!=1:
        print(f"  HARNESS FAILURE [{label}] anchor {src.count(old)}x"); return False
    open(path,"w",encoding="utf-8").write(src.replace(old,new,1))
    rc,out=run(); shutil.copy(bak,path)
    ok=rc!=0 and expect in out
    print(f"  {'RED ok ' if ok else 'NOT RED'} [{label}] exit={rc}")
    if not ok: print(f"      expected {expect!r}")
    return ok
rc,out=run(); print(f"BASELINE exit={rc}"); assert rc==0,out
r=[]

# 1. THE CUTAWAY FILTER COMES OFF — the agent is shown craft it cannot imitate.
r.append(mut(APP,
    '    _pool = [x for x in _b\n             if allow_unbuildable\n             or _REFERENCE_UNBUILDABLE not in (x.get("treat") or [])]',
    '    _pool = list(_b)',
    "cutaway beats are retrieved again",
    "no retrieved example places a cutaway"))

# 2. transition returns an empty list instead of saying nothing exists.
r.append(mut(APP,
    '        return ("NO REFERENCE: no reference beat uses %s. The corpus has nothing "',
    '        return ("" or "" if True else "NO REFERENCE: no reference beat uses %s. The corpus has nothing "',
    "transition returns silence instead of NO REFERENCE",
    "transition says NO REFERENCE explicitly"))

# 3. zoom is presented as a corpus rather than as six examples.
r.append(mut(APP, '    if _n <= 8:', '    if False:',
    "zoom stops being labelled as its example count",
    "zoom is labelled as its example COUNT"))

# 4. COUNTS FALL BACK TO THE INDEX — a partial index reports its own size as the
#    corpus's, which is the absence-misreported-as-a-finding this prevents.
r.append(mut(APP,
    '    _corpus_counts = (meta or {}).get("family_counts_in_corpus") or {}',
    '    _corpus_counts = {}',
    "family counts come from the partial index again",
    # The leg that FIRES is the sfx one: the index carries fewer sfx beats than
    # the corpus, so an index-derived count falsely calls 14 examples scarce.
    "a family the index under-carries is NOT falsely flagged"))

# 5. The block stops reaching the brief — retrieval nothing injects.
r.append(mut(APP, '            + _reference_block(_beats) + "\\n\\n"', '            + "" + "\\n\\n"',
    "the block stops being injected into the brief",
    "_reference_block is CALLED in the brief"))

# 6. THE READS ARE DROPPED and only the labels remain — the style-guide mistake.
# Mutating the loader, not the file: "read": appears once per beat (39x) and an
# anchor that matches 39 times proves nothing. The harness said so rather than
# counting it RED.
r.append(mut(APP, '            "read": b.get("read") or "",', '            "read": "",',
    "the reads are dropped, leaving only labels",
    "every beat carries the READ") if False else
    mut(APP, '    _b = _d.get("beats") or []',
        '    _b = [dict(x, read="") for x in (_d.get("beats") or [])]',
        "the reads are dropped at load, leaving only labels",
        "every beat carries the READ"))

# 7. A PARTIAL index stops declaring itself.
r.append(mut(IDX, '"beats_in_corpus": 153', '"beats_in_corpus": 2',
    "an index claims a corpus smaller than itself",
    "a partial index says so"))

# 8. THE INDEX STOPS BEING MOUNTED — UNREADABLE in every container.
r.append(mut(APP, '       .add_local_file(_REFERENCE_INDEX_SRC, "/root/reference_index.json", copy=True))',
    '       )',
    "the index is no longer mounted into the image",
    "mounted via add_local_file, asserted on the CALL"))
rc,out=run(); print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
sys.exit(0 if all(r) and rc==0 else 1)
