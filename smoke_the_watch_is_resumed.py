#!/usr/bin/env python3
"""The watch session is mounted, installed, and RESUMED — never forked.

WHY THIS EXISTS. A `--resume` onto a session file that is not there is the one
failure that looks exactly like success: the CLI silently starts a FRESH
session, the edit runs, every gate passes, and the reference layer — 852 frames
of the ten references and the model's own reading of them — was never in
context. Nothing downstream can tell that run from a good one.

AND FORKING IS THE EXPENSIVE WAY TO BE RIGHT. Measured 2026-09-16, three
consecutive runs each: plain `--resume` off a pristine copy read 70,226 and
wrote 0 ($0.0211); `--fork-session` read 32,318 and rewrote ~38,000 EVERY RUN
($0.228). A fork is safe-looking and costs an order of magnitude more, so the
flag must stay out — a preference in a comment is not a property.

IT DRIVES THE SHIPPED FUNCTION. `install_watch` takes its paths as parameters
with the production defaults precisely so this file can call it rather than
restate it.
"""
import ast
import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, ".")
import chatcut_job_app as J                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = io.open(os.path.join(HERE, "chatcut_job_app.py"), encoding="utf-8").read()
FAILS = []


def check(name, ok, why=""):
    print("  %-46s %s" % (name, "ok" if ok else "FAIL"))
    if not ok:
        FAILS.append("%s :: %s" % (name, why))
    return ok


def fixture(tmp, sid="abc12345-0000-0000-0000-00000000dead", jsonl=True,
            sidfile=True):
    c = os.path.join(tmp, "craft")
    os.makedirs(c, exist_ok=True)
    sp = os.path.join(c, "watch_session_id.txt")
    jp = os.path.join(c, "watch_session.jsonl")
    if sidfile:
        io.open(sp, "w").write(sid + "\n")
    if jsonl:
        io.open(jp, "w").write('{"type":"user"}\n{"type":"assistant"}\n')
    return sp, jp


def main():
    print("THE WATCH IS RESUMED")

    # --- the artefacts exist in the tree at all (a fixture outside the tree
    #     is the recorded failure set; this one is IN it) ---
    jt = os.path.join(HERE, "watch_session.jsonl")
    it = os.path.join(HERE, "watch_session_id.txt")
    check("the watch jsonl is in the tree", os.path.exists(jt),
          "watch_session.jsonl is missing — the mount would carry nothing")
    check("the session id is in the tree", os.path.exists(it),
          "watch_session_id.txt is missing")
    if os.path.exists(jt):
        _mb = os.path.getsize(jt) / 1048576.0
        _img = SRC.count("watch_session.jsonl")
        check("the watch carries real material (>1 MB)", _mb > 1.0,
              "watch_session.jsonl is %.2f MB — a stub, not 852 frames" % _mb)
        print("      (%.1f MB, named %d times in the app)" % (_mb, _img))

    # --- it is MOUNTED into the image ---
    # READ FROM THE MOUNT CALL, NOT FROM THE FILE'S TEXT. A substring over the
    # source is satisfied by ANY occurrence, and "/craft/watch_session.jsonl"
    # is also install_watch's DEFAULT PARAMETER — so breaking the real mount
    # left the words in place and the leg green. Measured: that mutation came
    # back NOT RED. A floor on a sum hides which contributor vanished.
    _tree0 = ast.parse(SRC)
    _mounts = set()
    for _n in ast.walk(_tree0):
        if (isinstance(_n, ast.Call)
                and getattr(_n.func, "attr", "") == "add_local_file"
                and len(_n.args) >= 2
                and isinstance(_n.args[1], ast.Constant)):
            _locals = [c.value for c in ast.walk(_n.args[0])
                       if isinstance(c, ast.Constant)
                       and isinstance(c.value, str)]
            _mounts.add((_locals[-1] if _locals else None, _n.args[1].value))
    check("the jsonl is mounted into the image",
          ("watch_session.jsonl", "/craft/watch_session.jsonl") in _mounts,
          "no add_local_file maps watch_session.jsonl to /craft/ — the "
          "container would have no watch. Mounts seen: %s"
          % sorted(m for m in _mounts if "watch" in str(m)))
    check("the session id is mounted into the image",
          ("watch_session_id.txt", "/craft/watch_session_id.txt") in _mounts,
          "the sid is not mounted, so --resume has nothing to name")

    # --- THE SHIPPED FUNCTION, DRIVEN ---
    tmp = tempfile.mkdtemp(prefix="watchsmoke_")
    try:
        sid = "abc12345-0000-0000-0000-00000000dead"
        sp, jp = fixture(tmp, sid)
        home = os.path.join(tmp, "home")
        got = J.install_watch("/work", sid_p=sp, jsonl_p=jp, home=home)
        landed = os.path.join(home, ".claude", "projects", "-work",
                              "%s.jsonl" % sid)
        check("install_watch returns the sid", got == sid,
              "returned %r, wanted %r" % (got, sid))
        check("it lands in the slug derived from cwd", os.path.exists(landed),
              "nothing at %s — a file in the wrong slug answers 'No "
              "conversation found'" % landed)

        # a DIFFERENT cwd must land somewhere else: the slug is derived, and
        # the cwd is part of the cached prefix, so this is not cosmetic
        home2 = os.path.join(tmp, "home2")
        J.install_watch("/other", sid_p=sp, jsonl_p=jp, home=home2)
        check("a different cwd derives a different slug",
              os.path.exists(os.path.join(home2, ".claude", "projects",
                                          "-other", "%s.jsonl" % sid)),
              "the slug is not derived from cwd")

        # --- ABSENCE RAISES. This is the whole point: a missing watch must
        #     not degrade into a fresh session. ---
        sp2, jp2 = fixture(tmp + "_nojsonl", sid, jsonl=False)
        raised = False
        try:
            J.install_watch("/work", sid_p=sp2, jsonl_p=jp2,
                            home=os.path.join(tmp, "h3"))
        except FileNotFoundError:
            raised = True
        check("a MISSING jsonl raises, never degrades", raised,
              "install_watch returned normally with no session file — the run "
              "would start a FRESH session and grade against nothing")

        sp3, jp3 = fixture(tmp + "_nosid", sid, sidfile=False)
        raised2 = False
        try:
            J.install_watch("/work", sid_p=sp3, jsonl_p=jp3,
                            home=os.path.join(tmp, "h4"))
        except FileNotFoundError:
            raised2 = True
        check("a MISSING sid file raises", raised2,
              "install_watch returned normally with no session id")
    finally:
        for d in (tmp, tmp + "_nojsonl", tmp + "_nosid"):
            shutil.rmtree(d, ignore_errors=True)

    # --- THE COMMAND: resume, with the installed sid, and no fork ---
    tree = ast.parse(SRC)
    edit = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "edit"), None)
    if not check("edit() is still there", edit is not None):
        return 1
    ed = ast.unparse(edit)
    _cc = ast.unparse(next(n for n in ast.walk(ast.parse(SRC)) if isinstance(n, ast.FunctionDef) and n.name == "cli_command"))
    check("the command resumes", "'--resume'" in _cc and "cli_command(_watch_sid" in ed,
          "edit() never passes --resume, so the watch is installed and ignored")
    # BOUND BY NAME, NOT BY WORDING. The sid passed must be the one
    # install_watch returned — a --resume onto a literal or a stale name is a
    # fresh session wearing the flag.
    installed = set()
    for n in ast.walk(edit):
        if isinstance(n, ast.Assign) and any(
                isinstance(c, ast.Call)
                and getattr(c.func, "id", "") == "install_watch"
                for c in ast.walk(n.value)):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    installed.add(t.id)
    check("install_watch is called in edit()", bool(installed),
          "nothing calls install_watch, so no session is ever placed")
    resumed_with = None
    for n in ast.walk(edit):
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "cli_command" and n.args:
            resumed_with = getattr(n.args[0], "id", None)
    check("--resume names the installed session",
          resumed_with in installed,
          "--resume is passed %r, which is not what install_watch returned "
          "(%s) — a fresh session wearing the flag" % (resumed_with,
                                                       sorted(installed)))
    # ordering: installed before the command is built
    _i_inst = ed.find("install_watch")
    _i_cmd = ed.find("cli_command(")
    check("the watch is installed before the command",
          _i_inst >= 0 and _i_cmd >= 0 and _i_inst < _i_cmd,
          "the command is built before the session is placed")
    # ASKED OF THE AST, NOT OF THE TEXT. The first version read the raw source
    # and failed on the COMMENT that documents this very rule ("RESUME, NEVER
    # --fork-session") — a match landing in prose, which is the recorded way a
    # check re-targets itself the moment someone writes the rule down. Only a
    # Constant node is the flag actually being passed.
    _forks = [n for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and n.value == "--fork-session"]
    check("--fork-session is NOT passed", not _forks,
          "forking reads 32,318 and rewrites ~38,000 EVERY run ($0.228 vs "
          "$0.0211) — it is the expensive way to be right; found at line(s) %s"
          % [n.lineno for n in _forks])

    if FAILS:
        print("\n%d FAILURE(S)" % len(FAILS))
        for f in FAILS:
            print("  " + f)
        return 1
    print("\nall legs green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
