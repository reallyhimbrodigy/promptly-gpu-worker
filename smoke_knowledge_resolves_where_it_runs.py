#!/usr/bin/env python3
"""SMOKE — knowledge documents resolve at the MOUNT, not just beside the file.

THE DEFECT, AND WHY 112 GREEN SMOKES COULD NOT SEE IT. `_KNOWLEDGE_DIR` is
`<dir of agentic_editor_app.py>/knowledge`. The image mounts the same documents
at `/knowledge`. ON THIS MACHINE THOSE ARE ONE DIRECTORY. In the container the
app lands at /root and the second path does not exist.

The merge brought in six readers that used only `_KNOWLEDGE_DIR`. Every local
check passed — all 112 smokes, ten import-time certs, a clean pyflakes — and
round 68's first arm died at IMPORT: `cannot read 06_emphasis_zoom.md: [Errno
2] ... '/root/knowledge/06_emphasis_zoom.md'`, raised by the zoom catalogue's
own FAILED state. The guard was right; the path had never executed anywhere.

SO THE CRAFT BLOCKS THOSE READERS BUILD — the cut corpus craft, the zoom arc
jobs, the family craft — had never run in any container on either lane.

WHAT THIS FILE CAN AND CANNOT PROVE. It cannot prove the mount path is correct:
that needs a container. It proves the resolver tries BOTH roots in the right
order, that a missing document is a reported STATE naming every path tried
rather than an exception, and that each reader still reports its own state when
the documents are unreachable.
"""
import os
import sys

import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                    # noqa: E402

fails = []


def check(what, passed, detail=""):
    if not passed:
        fails.append(what + (f"  [{detail}]" if detail else ""))
    print(f"  [{'ok' if passed else 'FAIL'}] {what}"
          + (f"\n         {detail}" if not passed and detail else ""))


# ── 1. THE RESOLVER TRIES BOTH ROOTS, MOUNT FIRST ───────────────────────────
_txt, _p = A.knowledge_doc("06_emphasis_zoom.md")
check("the zoom catalogue resolves at all", _txt is not None, _p)
check("and it resolved from a real file on disk",
      bool(_txt) and len(_txt) > 200, f"{len(_txt or '')} chars")

# ORDER: the mount is tried before the source path. Given two roots that both
# hold the document, the FIRST must win — in the container only that one exists.
import tempfile                                                   # noqa: E402
with tempfile.TemporaryDirectory() as _d1, tempfile.TemporaryDirectory() as _d2:
    open(os.path.join(_d1, "x.md"), "w").write("FIRST")
    open(os.path.join(_d2, "x.md"), "w").write("SECOND")
    _t, _q = A.knowledge_doc("x.md", dirs=(_d1, _d2))
    check("the FIRST candidate root wins — the container has only one of them",
          _t == "FIRST", f"{_t!r} from {_q}")
    _t2, _q2 = A.knowledge_doc("x.md", dirs=("/nonexistent-mount", _d2))
    check("and it falls through a root that does not exist", _t2 == "SECOND")

# ── 2. ABSENT IS A REPORTED STATE THAT NAMES EVERY PATH TRIED ───────────────
# A resolver that raises turns a missing document into a stack trace from
# whichever reader happened to be first, which is how this failure presented.
_t3, _q3 = A.knowledge_doc("this_document_does_not_exist.md")
check("a missing document returns None rather than raising", _t3 is None)
check("and the second value NAMES both paths tried, so the next person does "
      "not have to guess which root was wrong",
      "/knowledge/" in _q3 and A._KNOWLEDGE_DIR in _q3, _q3)

# ── 3. EVERY READER REPORTS A STATE WHEN THE DOCUMENTS ARE UNREACHABLE ──────
# Not an exception. `catalogue_bullets` returning FAILED is what MADE the round
# die loudly at import instead of shipping zoom_arc with no craft behind it —
# that part was correct and must stay correct.
_state, _bullets, _why = A.catalogue_bullets("no_such_doc.md")
check("catalogue_bullets reports FAILED, not an exception", _state == "FAILED")
check("and its reason names the paths it tried",
      "tried" in _why and "/knowledge" in _why, _why)

_ms, _mv, _mw = A.mask_zoom_job("no_such_doc.md")
check("mask_zoom_job reports FAILED", _ms == "FAILED", f"{_ms} {_mw}")

# ── 4. THE SHAPE RULE, DRIVEN FROM THE SHIPPED CERT ─────────────────────────
_src = open("agentic_editor_app.py", encoding="utf-8").read()
try:
    A._assert_one_knowledge_resolver(_src)
    check("no reader builds a knowledge path outside knowledge_doc", True)
except AssertionError as _e:
    check("no reader builds a knowledge path outside knowledge_doc", False,
          str(_e)[:300])

# AND THE RULE MUST DISCRIMINATE.
def _raises(src):
    try:
        A._assert_one_knowledge_resolver(src)
        return False
    except AssertionError:
        return True


check("it fires on a reader that joins _KNOWLEDGE_DIR itself",
      _raises(_src.replace("def knowledge_doc(doc, dirs=None):",
                           "def _rogue(doc):\n"
                           "    return open(os.path.join(_KNOWLEDGE_DIR, doc)).read()\n"
                           "\n\ndef knowledge_doc(doc, dirs=None):", 1)))
check("it fires on a candidate list that names only the source root",
      _raises(_src.replace('["/knowledge", _KNOWLEDGE_DIR]',
                           '[_KNOWLEDGE_DIR]', 1)))
check("it fires when the resolver is gone entirely",
      _raises(_src.replace("def knowledge_doc(doc, dirs=None):",
                           "def _renamed(doc, dirs=None):", 1)))
check("empty source is ABSENT, not passing", _raises(""))

if fails:
    print("KNOWLEDGE-RESOLVES: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("KNOWLEDGE-RESOLVES: PASS — mount first, source second, ABSENT names "
      "both, and every reader still reports a state")
