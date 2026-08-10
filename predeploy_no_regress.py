"""A DEPLOY MUST NEVER SILENTLY REVERT A FIX THAT IS ALREADY LIVE.

RULE 1 gate for the multi-agent deploy line. Twice in 16 hours the worker's two
deploy lines diverged and the LAST deploy won, silently reverting whatever the
previous one shipped:

  2026-08-03 23:50  agent/smoothness and zero-reject-routing had diverged 29h;
                    each deploy was reverting the other (6dd2756 / baac8aa).
  2026-08-04 15:29  v511 = f6bef0f (errors) shipped the private clean export.
                    v512 = 199c686 (smoothness) replaced the image TWO MINUTES
                    later from a branch that did not contain it. Observed gone
                    from the live image: clean_export_key on BOTH routes,
                    RENDER_CANON_UNREADABLE, and _frame_coverage_s (the VFR
                    clamp). Four completions ran on the reverted image before
                    anyone noticed, and only a DB read noticed at all.

WHY THE EXISTING GUARD COULD NOT CATCH IT: `.last_deployed_commit` is written
into the deploying checkout. Every agent has their own worktree, so each one's
copy records only their OWN last deploy and is blind to everyone else's. The
only shared, authoritative record of what is actually live is Modal's app
history. This gate reads THAT.

THE CHECK: every top-level function defined in the LIVE image's handler.py must
still be defined in the tree about to be deployed. A deploy that drops one is
reverting somebody's shipped fix, and it fails here with the names.

Deleting a function on purpose is allowed — name it in INTENTIONAL_REMOVALS
with a reason. The rule is not "never delete", it is "never delete by accident".

  python3 predeploy_no_regress.py    -> exit 0 clean, 1 on a would-be revert
"""
import json
import re
import subprocess
import sys

# Intentional deletions: "symbol": "why it went, and what replaced it".
# An entry here is a claim that the removal was deliberate and reviewed.
INTENTIONAL_REMOVALS = {}

APP = "promptly-gpu-worker"


def _sh(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def live_commit():
    """The commit of the image currently serving traffic, per Modal itself."""
    r = _sh(["modal", "app", "history", APP, "--json"])
    if r.returncode != 0 or not r.stdout.strip():
        # Fall back to the table form; --json is not on every CLI version.
        r = _sh(["modal", "app", "history", APP])
        if r.returncode != 0:
            return None, f"modal app history failed: {(r.stderr or '')[:200]}"
        for line in r.stdout.splitlines():
            m = re.search(r"│\s*v(\d+)\s*│[^│]*│[^│]*│[^│]*│\s*([0-9a-f]{7,40})\*?\s*│", line)
            if m:
                return m.group(2), f"v{m.group(1)}"
        return None, "could not parse `modal app history` output"
    try:
        rows = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return None, f"could not parse --json history: {e}"
    if not rows:
        return None, "no deploy history"
    top = rows[0]
    sha = str(top.get("Commit") or "").strip().rstrip("*")
    return (sha or None), str(top.get("Version") or "?")


def _surface(src):
    """The revert-detectable surface of handler.py.

    Two families, because neither alone covers the real incident:

      defs     — top-level functions. Caught _frame_coverage_s (the VFR clamp).
      literals — quoted identifiers >=6 chars, with docstrings and comments
                 stripped first. The clean-export revert was invisible to defs
                 (it is inline code and a dict key in the completion allowlist);
                 literals caught both `clean_export_key` and the
                 `RENDER_CANON_UNREADABLE` error code.

    Comments MUST be stripped: a bare substring matched inside a comment is a
    bug this repo has now written five times, most recently in the very gate
    written to prevent it.
    """
    defs = set(re.findall(r"(?m)^def\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(", src))
    stripped = re.sub(r'(?s)""".*?"""', "", src)
    stripped = re.sub(r"(?m)#.*$", "", stripped)
    lits = set(re.findall(r"""["']([A-Za-z_][A-Za-z_0-9]{5,60})["']""", stripped))
    return defs, lits


def surface_at(ref):
    """(defs, literals) at a git ref, or None if the ref is unreachable."""
    r = _sh(["git", "show", f"{ref}:handler.py"])
    if r.returncode != 0:
        return None
    return _surface(r.stdout)


def surface_in_worktree():
    with open("handler.py") as fh:
        return _surface(fh.read())


def main():
    sha, ver = live_commit()
    if not sha:
        print(f"NO-REGRESS: FAIL — cannot determine the live image ({ver}).")
        print("  This gate is the only thing that sees another agent's deploy.")
        print("  Refusing to deploy blind. Fix modal auth/CLI and re-run.")
        return 1

    live = surface_at(sha)
    if live is None:
        # Another agent's commit may simply not be fetched yet.
        _sh(["git", "fetch", "--all", "--quiet"], timeout=240)
        live = surface_at(sha)
    if live is None:
        print(f"NO-REGRESS: FAIL — live commit {sha[:7]} (deploy {ver}) is not in this repo.")
        print("  It was deployed from a branch that was never pushed, so this")
        print("  deploy CANNOT be checked for reverts. Push it, then re-run.")
        return 1

    # LINEAGE CHECK (TRUTH 2026-08-09). The surface diff below catches DROPPED
    # identifiers, but two diverged branches with identical handler surfaces
    # still fork the lineage — the state that produced the v512 race in the
    # first place. The live commit must be an ANCESTOR of what deploys next, so
    # there is exactly one deploy lineage. A deliberate rollback is the only
    # exception: set PROMPTLY_ALLOW_ROLLBACK=1 (loud, per-run).
    import os as _os
    anc = _sh(["git", "merge-base", "--is-ancestor", sha, "HEAD"])
    if anc.returncode != 0 and not _os.environ.get("PROMPTLY_ALLOW_ROLLBACK"):
        print(f"NO-REGRESS: FAIL — live commit {sha[:7]} (deploy {ver}) is NOT an ancestor of HEAD.")
        print("  This deploy would FORK the deploy lineage — the exact two-lane divergence")
        print(f"  that produced v512. Merge the live commit first:  git merge {sha[:7]}")
        print("  (Deliberate rollback: PROMPTLY_ALLOW_ROLLBACK=1 ./deploy.sh)")
        return 1

    live_defs, live_lits = live
    my_defs, my_lits = surface_in_worktree()
    allow = set(INTENTIONAL_REMOVALS)
    lost_defs = sorted(live_defs - my_defs - allow)
    lost_lits = sorted(live_lits - my_lits - allow)

    if lost_defs or lost_lits:
        n = len(lost_defs) + len(lost_lits)
        print(f"NO-REGRESS: FAIL — this deploy would REVERT {n} thing(s) that are LIVE.")
        print(f"  live image: {sha[:7]} (deploy {ver})")
        for name in lost_defs:
            print(f"    - def {name}()")
        for name in lost_lits:
            print(f"    - '{name}'")
        print(f"  Merge the live commit first:  git merge {sha[:7]}")
        print("  Or, if a removal is deliberate, name it in INTENTIONAL_REMOVALS.")
        return 1

    print(f"NO-REGRESS: OK — {len(live_defs)} live functions and {len(live_lits)} live "
          f"identifiers all still present (live {sha[:7]}, deploy {ver}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
