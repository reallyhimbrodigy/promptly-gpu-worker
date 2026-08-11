#!/usr/bin/env python3
"""ONE-VALUE flag flip on the promptly-lang-flags Modal Secret, without dropping keys.

THE LANDMINE THIS REMOVES
-------------------------
`modal secret create --force` REPLACES the whole secret: every key not restated
is DROPPED, silently, each one reverting to its absent-default. The live secret
holds 31 keys. `secret_flags_readback.py` used to declare only 26. A flip typed
by hand off that list — the documented procedure in LANE4_FLIP_HLS_COPY.md —
would have deleted five live flags (HLS_COPY, MEDIA_RESOLUTION,
PROXY_SAMPLE_FPS, SILENT_TO_MOODREEL, STRUCTURE_ABORT) while reporting success.

So the restate is never typed. It is DERIVED from a live readback of every
PROMPTLY_* key the secret actually injects, one value is changed, and the result
is verified by a second independent readback before this exits 0. Rule 1: the
check that makes the regression impossible, not a note asking the next agent to
be careful.

WHAT IT GUARANTEES (asserted, not intended)
  1. every key present before is present after      — no silent drop
  2. no key gained except the one named             — no silent addition
  3. exactly ONE value differs, and it is the named one, with the named value
  4. the post-flip readback is a SEPARATE container run — not the dict we sent

NOT LIVE UNTIL A REDEPLOY. Modal memory-snapshots capture os.environ at deploy
time, so the flip only reaches running code after `./deploy.sh`. This tool says
so on exit and refuses to claim otherwise.

AUTHORITY. A live-secret VALUE change needs the owner's explicit GO naming the
key (secret-auth law). This tool does not check that for you — it is recorded in
the flip filing (e.g. LANE4_FLIP_HLS_COPY.md) and in DEPLOY_LOG.md.

USAGE
  python3 secret_flip.py --key PROMPTLY_HLS_COPY --value 1            # dry run
  python3 secret_flip.py --key PROMPTLY_HLS_COPY --value 1 --apply
  python3 secret_flip.py --key PROMPTLY_HLS_COPY --value '' --apply   # revert

Cost: two ephemeral debian_slim CPU containers (~10s each), well under $0.01.
"""
import argparse
import json
import subprocess
import sys

SECRET_NAME = "promptly-lang-flags"
READBACK = "secret_flags_readback.py"


def _readback() -> dict:
    """Live values, straight out of a container with the secret attached."""
    p = subprocess.run(["modal", "run", READBACK], capture_output=True, text=True, timeout=600)
    line = next((l for l in (p.stdout + p.stderr).splitlines() if l.startswith("READBACK ")), None)
    if not line:
        sys.exit(f"FATAL: no READBACK line from `modal run {READBACK}`.\n"
                 f"stdout:\n{p.stdout[-2000:]}\nstderr:\n{p.stderr[-2000:]}\n"
                 "Refusing to touch the secret without a live reading of it.")
    return json.loads(line[len("READBACK "):])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, help="exact key, e.g. PROMPTLY_HLS_COPY")
    ap.add_argument("--value", required=True, help="exact value; '' clears (exact-string law: MEDIA_RESOLUTION_LOW, never LOW)")
    ap.add_argument("--apply", action="store_true", help="without this it is a dry run")
    a = ap.parse_args()

    if not a.key.startswith("PROMPTLY_"):
        sys.exit(f"FATAL: {a.key} is not a PROMPTLY_* flag; this tool only flips those.")

    before = _readback()
    print(f"READ {len(before)} live keys from `{SECRET_NAME}`")

    # A key absent from the live secret is a typo or a NEW key. Adding one is a
    # different, larger act than flipping a value (CANON registration must ride
    # with it), so it is refused here rather than done by accident.
    if a.key not in before:
        sys.exit(f"FATAL: {a.key} is NOT in the live secret. Live keys:\n  "
                 + "\n  ".join(sorted(before)) + "\nAdding a NEW key is not a flip — register it in CANON in the same change.")

    old = before[a.key]
    old_disp = "<UNSET>" if old == "<UNSET>" else repr(old)
    if old == a.value:
        print(f"NO-OP: {a.key} is already {a.value!r}. Secret untouched.")
        return
    print(f"FLIP  {a.key}: {old_disp} -> {a.value!r}")

    after_intent = dict(before)
    after_intent[a.key] = a.value
    # "<UNSET>" is the readback's word for "declared but absent". Restating it
    # literally would write the STRING "<UNSET>" into the secret — a truthy
    # value for every `if os.environ.get(...)` in the codebase. Drop those keys
    # instead: absent is what they already are.
    payload = {k: v for k, v in after_intent.items() if v != "<UNSET>"}
    dropped_unset = sorted(k for k, v in after_intent.items() if v == "<UNSET>")
    if dropped_unset:
        print(f"NOTE: {len(dropped_unset)} key(s) read <UNSET> and stay absent: {', '.join(dropped_unset)}")

    if not a.apply:
        print(f"\nDRY RUN — nothing written. Would restate {len(payload)} keys with --force.")
        print("Re-run with --apply. Then ./deploy.sh: the flip is NOT live until a redeploy.")
        return

    cmd = ["modal", "secret", "create", SECRET_NAME, "--force"] + [f"{k}={v}" for k, v in sorted(payload.items())]
    print(f"\nWriting {len(payload)} keys...")
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        sys.exit(f"FATAL: secret create failed (rc={p.returncode}).\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")

    # VERIFY from a second, independent container read — never from what we sent.
    after = _readback()
    lost = sorted(set(before) - set(after))
    gained = sorted(set(after) - set(before))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])

    problems = []
    if lost:
        problems.append(f"KEYS LOST: {lost}")
    if gained:
        problems.append(f"KEYS GAINED (unexpected): {gained}")
    if changed != [a.key]:
        problems.append(f"CHANGED SET is {changed}, expected exactly ['{a.key}']")
    if after.get(a.key) != a.value:
        problems.append(f"{a.key} reads {after.get(a.key)!r}, expected {a.value!r}")

    if problems:
        print("\n".join("FAIL: " + x for x in problems), file=sys.stderr)
        sys.exit("SECRET IS IN AN UNVERIFIED STATE — do NOT deploy. Restore from the printed before-set.")

    print(f"VERIFIED: {len(after)} keys, 0 lost, 0 gained, exactly 1 changed ({a.key}={a.value!r}).")
    print("NOT LIVE YET — memory snapshots freeze env at deploy time. Run ./deploy.sh to arm it.")


if __name__ == "__main__":
    main()
