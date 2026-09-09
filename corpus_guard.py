#!/usr/bin/env python3
"""Refuse a round whose plan does not match ONE DECLARED, MANIFESTED corpus.

WHY THIS EXISTS. Rounds 35 through 41 all ran on ab-sources/reliability-
fixtures-v1 — the flat/noise corpus — after the real-footage corpus had been
built, probed, uploaded and given a provenance manifest. Nothing was broken in
the staging: `stage_fixtures_v3.py` writes its manifest to S3 and `run_round.sh`
reads a DIFFERENT file, /tmp/fixtures/staged.json, which nothing updated. The
corpus was real, certified, and unreachable.

THE ROOT CAUSE IS NOT THE MISSING WRITE. It is that the round never printed
which corpus it ran. Seven rounds produced logs, scores and a streak, and not
one of them recorded the sources the numbers came from, so there was no surface
on which the mistake could be noticed. Fixing only the wiring would leave that
hole open for the next corpus.

So this does two things, and the printing is the more important one:

  1. PRINTS the corpus, every fixture, its duration and its provenance, into
     the round log, so any later reader can tell what was measured.
  2. REFUSES the round when the plan and the corpus disagree.

FOUR WAYS A PLAN CAN BE WRONG, all of them observed or one edit away:

  spans two corpora    a half-migrated staged.json — the worst case, because
                       the round looks normal and the cohort is mixed. Rule 5.
  wrong corpus         what actually happened: every key in a corpus nobody
                       meant to run.
  key not in manifest  ab-sources/reliability-fixtures-v3/music-fb4aa93b.mp4 is
                       BYTE-IDENTICAL to car_short-fb4aa93b.mp4 (same ETag) and
                       is not in the v3 manifest — a leftover from slotting the
                       car clip under a v1 fixture name. Wiring v3 by matching
                       v1's five names would have run the music brief ("cuts
                       landing on the beat, no captions") against a ten-second
                       silent car clip and scored it. The manifest is the
                       allowlist precisely because the filename is not.
  duplicate content    two fixtures, one video. Every per-fixture number is then
                       the same draw twice, and the round reports five sources.

A MANIFEST IS REQUIRED, NEVER OPTIONAL. If it is missing this fails rather than
degrading to a weaker check: absence rendered as success is the exact false
green this lane keeps paying for, and an unmanifested corpus has no provenance,
which is the whole reason v3 was built.

  python3 corpus_guard.py <plan.tsv> <declared-corpus-prefix>
      exit 0  plan agrees with the corpus; the CORPUS block is printed
      exit 3  it does not; nothing is printed but the reason
"""
import json
import os
import sys


def _load_manifest(bucket, prefix):
    """The corpus's own manifest, or None. Tries both spellings in use."""
    import boto3
    s3 = boto3.client("s3")
    for name in ("manifest.json", "MANIFEST.json"):
        try:
            body = s3.get_object(Bucket=bucket, Key=f"{prefix}/{name}")["Body"].read()
        except Exception:
            continue
        try:
            return json.loads(body)
        except Exception:
            return None
    return None


def _manifest_index(man):
    """{basename: entry} from either manifest shape.

    v3 is a list of per-fixture dicts carrying s3_key; older ones are a mapping.
    Reading only the shape in front of you is how a parser learns one format and
    breaks on the next — both are handled explicitly and anything else is a
    refusal, not a guess.
    """
    out = {}
    if isinstance(man, list):
        for e in man:
            k = (e or {}).get("s3_key") or ""
            if k:
                out[k.split("/")[-1]] = e
    elif isinstance(man, dict):
        for name, e in man.items():
            if isinstance(e, dict) and e.get("key"):
                out[str(e["key"]).split("/")[-1]] = e
            elif isinstance(e, str):
                out[e.split("/")[-1]] = {"fixture": name}
    return out


def check(plan_path, declared, bucket=None):
    """(ok, lines) — lines are printed by the caller on success, on stderr on failure."""
    bucket = bucket or os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    declared = declared.rstrip("/")
    rows = []
    with open(plan_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                rows.append((parts[0], parts[1]))
    if not rows:
        return False, [f"empty plan: {plan_path}"]

    # 1. ONE corpus.
    corpora = sorted({"/".join(k.split("/")[:-1]) for _, k in rows})
    if len(corpora) != 1:
        return False, ["plan SPANS MULTIPLE CORPORA — the cohort is mixed and "
                       "every per-family number would blend them:"] + \
                      [f"    {c}" for c in corpora]
    got = corpora[0]

    # 2. The corpus somebody DECLARED.
    if got != declared:
        return False, [f"plan runs   {got}",
                       f"declared    {declared}",
                       "the round would measure a corpus nobody asked for "
                       "(this is what rounds 35-41 did, unnoticed, because "
                       "nothing printed the corpus)"]

    # 3. Every key allowlisted BY THE MANIFEST, not by its filename.
    man = _load_manifest(bucket, got)
    if man is None:
        return False, [f"corpus {got} has NO MANIFEST (manifest.json / MANIFEST.json).",
                       "A corpus without provenance cannot be reported against, and",
                       "passing here would render absence as success."]
    idx = _manifest_index(man)
    if not idx:
        return False, [f"corpus {got} manifest parsed to ZERO entries — "
                       "unrecognised shape; refusing rather than guessing."]
    unlisted = [(n, k) for n, k in rows if k.split("/")[-1] not in idx]
    if unlisted:
        return False, ["plan key(s) NOT IN THE CORPUS MANIFEST — the filename is "
                       "not the allowlist:"] + \
                      [f"    {n:18} {k.split('/')[-1]}" for n, k in unlisted]

    # 4. No two fixtures on the same video.
    seen = {}
    dupes = []
    for n, k in rows:
        base = k.split("/")[-1]
        if base in seen:
            dupes.append(f"    {seen[base]} and {n} are BOTH {base}")
        seen[base] = n
    if dupes:
        return False, ["two fixtures point at ONE video — every per-fixture "
                       "number would be the same draw twice:"] + dupes

    # PASS. Print what was measured, so the log carries its own provenance.
    lines = [f"CORPUS          : {got}   {len(rows)} fixture(s)"]
    for n, k in rows:
        e = idx.get(k.split("/")[-1]) or {}
        dur = e.get("duration")
        prov = e.get("provenance") or e.get("source_file") or "no provenance recorded"
        cannot = e.get("cannot_score") or []
        lines.append(f"    {n:18} {('%.1fs' % dur) if dur else '  ?  ':>7}  {prov[:52]}"
                     + (f"   CANNOT SCORE {cannot}" if cannot else ""))
    return True, lines


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    ok, lines = check(sys.argv[1], sys.argv[2])
    if ok:
        for ln in lines:
            print("  " + ln)
        return 0
    sys.stderr.write("[CORPUS ABORT] " + lines[0] + "\n")
    for ln in lines[1:]:
        sys.stderr.write("               " + ln + "\n")
    return 3


if __name__ == "__main__":
    sys.exit(main())
