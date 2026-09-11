#!/usr/bin/env python3
"""A round's arms must outlive a signal to the launcher's process group.

ROUND 58 LOST FOUR OF FIVE ARMS. Three cancelled twice, one deadline. Every
failed log ends with "[modal-client] Received a cancellation signal" — CLIENT
side, a catchable signal, delivered to the process group the round runs in.
car_mid had already reached BENCH AT PAINT. The arms were never a Modal
problem, and the retry block's own note — "Modal has cancelled a fixture
mid-run ... so it is infrastructure" — has been wrong about at least this
class since round 19.

`modal run --detach` keeps the Modal APP alive when the client disconnects. It
does not stop the client cancelling its own inputs when the CLIENT is
signalled. Two different things, one flag name.

TWO LEGS, and the second is why this file exists rather than a comment:
  1. run_round.sh launches through setsid.py at BOTH sites (the launch and
     the retry — a retry that dies the same way is the same lost round);
  2. BEHAVIOURALLY: a setsid child outlives a TERM to its group and a naive
     child does not. The second half is the floor. A wrapper that detached
     nothing would pass leg 1 forever.
"""
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
fail = 0

src = open(os.path.join(HERE, "run_round.sh")).read()
launches = src.count("modal run --detach agentic_editor_app.py")
wrapped = src.count('setsid.py" modal run --detach agentic_editor_app.py')
if launches == 0:
    print("  *** run_round.sh no longer launches arms the way this checks")
    fail += 1
elif wrapped != launches:
    print(f"  *** {wrapped} of {launches} launch site(s) go through setsid.py "
          f"— an unwrapped retry dies the same way the first attempt did")
    fail += 1

tmp = tempfile.mkdtemp(prefix="setsidproof_")
out = os.path.join(tmp, "proof.txt")
script = (
    f'python3 "{os.path.join(HERE, "setsid.py")}" bash -c '
    f'"sleep 4; echo DETACHED >> {out}" & '
    f'bash -c "sleep 4; echo NAIVE >> {out}" & '
    'sleep 1; kill -TERM 0 2>/dev/null'
)
# THE PROOF MUST NOT KILL ITS OWN RUNNER. `kill -TERM 0` signals the caller's
# process group, and without this the group is the one running this check —
# the first version of this file exited 144 by TERMing the shell that started
# it. os.setpgrp in a preexec_fn gives the proof its own group: the signal
# reaches the two children under test and nothing else.
subprocess.run(["bash", "-c", script], capture_output=True,
               preexec_fn=os.setpgrp)
time.sleep(6)
got = ""
if os.path.exists(out):
    got = open(out).read()
if "DETACHED" not in got:
    print("  *** the setsid-wrapped child did NOT survive a TERM to its group "
          "— the wrapper detaches nothing")
    fail += 1
if "NAIVE" in got:
    print("  *** the NAIVE child also survived — this platform does not "
          "deliver the signal, so the proof is vacuous and proves nothing")
    fail += 1

print(f"smoke_round_arms_survive_a_signal: {wrapped}/{launches} wrapped, "
      f"survivors={got.split() or ['none']}, {fail} wrong")
sys.exit(1 if fail else 0)
