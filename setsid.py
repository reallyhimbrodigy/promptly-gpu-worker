#!/usr/bin/env python3
"""setsid(1) for macOS, which does not ship it.

WHY THIS EXISTS. Round 58 lost four of five arms. Every failed log ends
"[modal-client] Received a cancellation signal" — CLIENT side, a catchable
signal, delivered to the process group the round runs in. `modal run --detach`
keeps the Modal APP alive across a client disconnect; it does not stop the
client cancelling its own inputs when the client itself is signalled. car_mid
had already reached BENCH AT PAINT when it died.

os.setsid() puts the child in a new session with no controlling terminal, so a
signal sent to the launcher's process group does not reach it. The signals are
also ignored explicitly: a new session is not a new process group for signals
sent by PID, and one belt is cheaper than a lost round.

    python3 setsid.py <cmd> [args...]
"""
import os
import signal
import sys

if len(sys.argv) < 2:
    sys.stderr.write("usage: setsid.py <cmd> [args...]\n")
    raise SystemExit(2)
try:
    os.setsid()
except OSError:
    # already a session leader — fine, the point is not being in the caller's
    pass
for _s in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
    try:
        signal.signal(_s, signal.SIG_IGN)
    except (ValueError, OSError):
        pass
os.execvp(sys.argv[1], sys.argv[1:])
