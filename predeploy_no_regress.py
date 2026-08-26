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
INTENTIONAL_REMOVALS = {
    # ── TREND REMOVAL, 2026-08-23 (8 symbols) ──────────────────────────────
    # The trend pipeline was retired: 6,298 chars out of handler.py, the cron
    # out of render.yaml, four scripts left .deprecated. It scraped Apify,
    # aggregated 50 videos into ONE style-guide row in trend_profiles, and
    # format_trend_section pasted that row into the directive as prose.
    #
    # WHY IT WENT: the aggregate was the defect. A guide averaged over 50 videos
    # says "trending videos cut fast and use bold captions" — true, unconditional,
    # unqueryable for THIS source — and it rode in an already implicitly-cached
    # 60,540-token prompt where prompt-cutting was measured to buy nothing.
    # Replaced by REFERENCE_CORPUS_SPEC.md: records, never an aggregate;
    # retrieved, never recited. Ten records are landed in Supabase.
    #
    # CROSS-REPO CHECK, because this is the half that could break someone else:
    # content-studio's dispatch-to-modal.js still SENDS `trendSnapshot` (the
    # re-edit replay field). The worker no longer reads it. An ignored extra
    # field in the payload is a NO-OP, not a break — verified by reading the
    # call site, not assumed. The other three content-studio references
    # (update-style-guide, analyze-reference-videos, trend-video-pipeline) are
    # standalone scripts, required-by-server: 0.
    "get_trend_context": "trend pipeline retired 2026-08-23; the aggregate was the defect",
    "format_trend_section": "same — it pasted the aggregated row into the directive",
    "trend_profiles": "the aggregated style-guide table; superseded by reference_videos/reference_beats",
    "style_guide": "the aggregate itself",
    "profile_json": "trend profile payload",
    "numeric_patterns": "trend profile field",
    "valid_until": "trend profile TTL",
    "wait_trend": "the trend wait span; the stage no longer exists",

    # ── _v2_counts -> v2_counts, 2026-08-24 (rename, not a deletion) ───────
    # handler sanitises plans with `k.startswith("_")` filters, so the LEADING
    # UNDERSCORE meant these metrics were STRIPPED IN TRANSIT: computed by
    # flatten_beats, asserted by a cert, proven end to end, and deleted before
    # any reader saw them. Two paid A/B cells reported the pre-registered
    # metrics as ABSENT for exactly that reason. Renamed across all five
    # files; cert_v3_beat_resolution clause 7 asserts the key survives an
    # underscore strip. No consumer outside this repo reads it
    # (content-studio: 0 files).
    "_v2_counts": "renamed to v2_counts — a leading underscore was stripping it in transit",

    # WATCHDOG RECOVERY FIELDS RENAMED 2026-08-15. The gate fired on these and it
    # was RIGHT to — two live analytics field names vanish in this deploy. The
    # removal is deliberate and the rename is the whole point:
    #   LIVE (v536 b052af0): recovered_core_s_vs_reconciler_cluster
    #                        recovered_core_s_vs_repair_cluster
    #   NOW:                 recovered_lower  /  recovered_upper
    #                        + recovered_upper_is_a_bound: true
    # The old names invited the error the band exists to prevent: treating the
    # repair-cluster figure as "the saving" and SUMMING it. LOWER is what the job
    # would have burned reaching the ~210s reconciler cluster and is the only
    # summable one; UPPER is a bound on a job that was already going to be
    # rescued sooner, so summing it counts savings that never occur (~4x
    # overstatement at 60 jobs/day). validate_deploy now REFUSES the old name by
    # literal, so this pair cannot come back quietly.
    # Data note: post_upload_watchdog_fired rows written before this deploy carry
    # the OLD keys. Any query spanning the boundary must read both.
    "recovered_core_s_vs_reconciler_cluster":
        "watchdog recovery band renamed to recovered_lower (the summable one)",
    "recovered_core_s_vs_repair_cluster":
        "watchdog recovery band renamed to recovered_upper (a BOUND, never summed)",
    # W1/DELIVERY 2026-08-11, reviewed by TRUTH against both trees before allowing.
    # The gate fired on this and it was RIGHT to: a live identifier vanished.
    # Verified deliberate, not an accidental drop.
    #   LIVE (v522 9ee9e6d): edit_plan["_lang_bundle"] = _lang_bundle   (write)
    #                        (edit_plan or {}).get("_lang_bundle")      (read)
    #   The write ran on the recipe THREAD before the enclosing scope had bound
    #   `edit_plan` -> NameError on EVERY job, swallowed, so the read returned
    #   null 218/218 times.
    #   NOW: `_lang_bundle_holder = {}` is bound BEFORE the thread starts, the
    #   thread writes _lang_bundle_holder["value"], and the consumer reads
    #   _lang_bundle_holder.get("value"). The quoted dict KEY "_lang_bundle" is
    #   therefore gone by design; the variable _lang_bundle still exists.
    "_lang_bundle": "W1/DELIVERY: dict-key channel replaced by _lang_bundle_holder "
                    "(the key write was an unbound-name NameError on every job, "
                    "null 218/218). Variable retained; only the quoted key is gone.",
}

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


# SCOPE WIDENED 2026-08-15 [Law 1]. This gate covered handler.py ONLY, so every
# Modal ENTRYPOINT in modal_app.py had no revert detection at all — a lane could
# drop `render_burst`, the ASGI app, or a cert entrypoint and this gate would
# report "all still present" while the deployed surface silently shrank. Found
# when removing the dead H100 function passed the gate cleanly: the pass was
# CORRECT (out of scope) but the scope was the bug.
#
# modal_app.py is where the money-path resource decorators live (cpu=, memory=,
# gpu=), so a silent drop there is both a functional and a billing regression.
_TRACKED_FILES = ("handler.py", "modal_app.py")


def _surface_multi(read):
    """Union the surface across every tracked file. `read` maps path -> source
    or None when the file is absent at that ref (a file that did not yet exist
    contributes nothing rather than raising)."""
    defs, lits = set(), set()
    for path in _TRACKED_FILES:
        src = read(path)
        if not src:
            continue
        d, l = _surface(src)
        defs |= d
        lits |= l
    return defs, lits


def surface_at(ref):
    """(defs, literals) at a git ref, or None if the ref is unreachable."""
    def _read(path):
        r = _sh(["git", "show", f"{ref}:{path}"])
        return r.stdout if r.returncode == 0 else None
    # handler.py must exist at the ref, or the ref itself is unusable.
    if _read("handler.py") is None:
        return None
    return _surface_multi(_read)


def surface_in_worktree():
    import os as _os2

    def _read(path):
        if not _os2.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    return _surface_multi(_read)


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
