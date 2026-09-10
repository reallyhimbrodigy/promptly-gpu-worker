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
#    Retargeted: the pool comprehension was rewritten when the hardcode became a
#    derivation, so the old anchor no longer existed and the harness said
#    "anchor 0x" rather than counting it RED. A refactor is exactly where a
#    mutation stops applying.
# THIS MUTATION WENT VACUOUS THE DAY CUTAWAY SHIPPED, and that is worth stating
# rather than quietly reversing. It removed the unbuildable filter to prove the
# filter filters — but in a tree where cutaway IS rulable, `_unbuildable` is
# EMPTY and removing an empty filter changes nothing. The mutant was
# byte-different and behaviourally identical, so the proof read NOT RED with
# nothing wrong.
#
# A mutation that does not mutate proves nothing — and this is the subtler form
# of it: the anchor still matched, the edit still applied, and the SEMANTICS had
# gone no-op underneath. Counting occurrences cannot catch that.
#
# So it is inverted to the defect that is live in THIS tree: the filter drops
# examples the agent CAN rule. The smoke now asserts cutaway examples appear
# exactly when cutaway is rulable, so suppressing them must fire it.
r.append(mut(APP,
    '             or not (_unbuildable & set(x.get("treat") or []))]',
    '             or not set(x.get("treat") or []) & {"cutaway"}]',
    "the filter suppresses a family the agent CAN rule",
    "cutaway examples appear exactly when cutaway is rulable"))

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
# 9. THE HARDCODE COMES BACK — correct today, wrong the day cutaway ships.
r.append(mut(APP, '    _unbuildable = reference_unbuildable()',
    '    _unbuildable = {"cutaway"}',
    "the unbuildable set is hardcoded again",
    "the retrieval CALLS the derivation"))
# 10. The derivation stops reading the enum, so a shipped family stays filtered.
r.append(mut(APP, '    _ours = {v for k, v in REFERENCE_FAMILY_NAME.items()\n             if v and k in _rulable}',
    '    _ours = {v for k, v in REFERENCE_FAMILY_NAME.items()\n             if v and k in _rulable and k != "cutaway"}',
    "a shipped family never leaves the unbuildable set",
    # The leg patches whichever direction THIS tree allows: cutaway ships here,
    # so the live assertion is that removing it from the enum makes it
    # unbuildable again. The add-direction wording only existed in a tree
    # where cutaway was absent.
    "a family LEAVING the enum joins the unbuildable set"))
rc,out=run(); print(f"RESTORED exit={rc}")
print(f"\n{sum(r)}/{len(r)} RED-proven")
# A FLOOR, BECAUSE all([]) IS TRUE. A red proof whose mutation list is
# emptied — by a bad merge, a botched refactor, a commented-out block —
# reports SUCCESS. An instrument built to prove a check CAN FAIL,
# rendering its own absence as success. Found in 10 of 11 here and 16 of
# 16 on Builder-2's tree: 26 of 27 across both.
sys.exit(0 if r and all(r) and rc==0 else 1)
