#!/usr/bin/env python3
"""No launcher spawns a long job without `--detach`. One guard, not a copy.

FIFTH TIME THIS CLASS HAS COST A RUN, and the fourth spelling of it:

  round 58   four of five arms lost to a signal delivered to the launcher's
             PROCESS GROUP — client-side, catchable. Fixed with setsid.py.
  plan-first `.spawn()` protected against the client dying and did NOT keep the
             APP alive; an ephemeral `modal run` stops its app the moment the
             entrypoint returns, and the spawned call died with it.
  chatcut    fixed by refusing to launch without --detach... in ONE launcher.
  2026-09-14 `agentic_editor_app.py::main` launched without it, ran 468s, the
             client dropped, and the app stopped mid-ruling. The guard existed
             and was in the other file.

"--detach keeps the APP alive; it does not stop the CLIENT cancelling" is
already written in CLAUDE.md. Both halves are true and NEITHER MECHANISM COVERS
THE OTHER'S FAILURE — which is exactly why the fix cannot be a paragraph either
launcher might not have read. It is a call, and a smoke enumerates the
launchers that must make it.

A CHECK THAT BLOCKS YOU WANTS A DESCRIPTION, NEVER A SKIP LIST. An entrypoint
that legitimately does not need this — one that reads a Dict and returns in a
second — passes `why_not=` saying so, in its own words, and that reason is
printed. It is still a call, so it is still enumerable.
"""
import sys


def require_detach(what="this job", why_not=""):
    """Refuse to launch unless `--detach` is on the command line.

    Returns None. Raises SystemExit with the command to re-run, because a
    launcher that dies without telling you how to relaunch costs the same
    minutes twice.
    """
    if why_not:
        print("  DETACH          : not required — %s" % why_not, flush=True)
        return
    if "--detach" in sys.argv:
        print("  DETACH          : on", flush=True)
        return
    _cmd = " ".join(sys.argv)
    raise SystemExit(
        "REFUSING TO LAUNCH %s WITHOUT --detach.\n"
        "  An ephemeral `modal run` stops its app when the local client "
        "disconnects, and\n"
        "  a long job outlives the connection often enough that this has now "
        "cost five runs.\n"
        "  The work is lost mid-flight and the log says only 'App state is "
        "APP_STATE_STOPPED'.\n"
        "\n"
        "  Re-run with --detach immediately after `modal run`:\n"
        "    %s\n"
        % (what, _cmd.replace("modal run", "modal run --detach", 1)
           if "modal run" in _cmd else "modal run --detach " + _cmd))
