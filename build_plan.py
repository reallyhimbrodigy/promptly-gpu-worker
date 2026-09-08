#!/usr/bin/env python3
"""Build a round's plan.tsv FROM THE CORPUS MANIFEST, for one declared corpus.

WHY THIS REPLACES /tmp/fixtures/staged.json. staged.json was a local cache
written by whichever staging script ran last. stage_fixtures_v3.py never wrote
it, so it kept five reliability-fixtures-v1 keys from 2026-09-07 and rounds 35
through 41 all ran the flat/noise corpus while the real-footage corpus sat
staged, probed and manifested in S3. A per-checkout cache that no staging step
updates is not a source of truth; the corpus's own manifest is.

Same class as `.last_deployed_commit`: ask the system that holds the truth, do
not trust a local file that merely once agreed with it.

BRIEFS ARE PER CORPUS, keyed by the fixture names that corpus actually
contains. v1 and v3 do not share a fixture set, and mapping one onto the other
by position or by name is how the v3 stray `music-fb4aa93b.mp4` — byte-identical
to car_short — would have been run under a brief asking for cuts on the beat.

  python3 build_plan.py <corpus-prefix> > plan.tsv
"""
import json
import os
import sys

# THE BRIEF IS A PROPERTY OF THE FIXTURE, not of its slot. Each is written for
# what that source IS; a brief demanding captions on a silent clip measures the
# brief, not the pipeline.
BRIEFS = {
    "ab-sources/reliability-fixtures-v1": {
        "talking_head": "Punchy and direct. Fast cuts — cut the filler and dead air hard. Big bold captions, hit the numbers. This should feel urgent.",
        "music": "Let it breathe. Cinematic and moody, cuts landing on the beat, no captions at all.",
        "screen_recording": "Clean and professional. Few cuts, subtle overlays only, no sound effects. Calm and legible.",
        "product_shot": "Premium and slow. One hero moment, restrained motion, nothing busy.",
        "pet_video": "Playful and quick. Fun energy, snappy cuts, a sound effect where it lands.",
    },
    "ab-sources/reliability-fixtures-v3": {
        # Zac's real footage. Briefs written against what each clip actually is,
        # from the staging probe — not carried over from the v1 slot names.
        "talking_head": "Punchy and direct. Fast cuts — cut the filler and dead air hard. Big bold captions, hit the numbers. This should feel urgent.",
        # 27.9s, mean -11.7 dB, speech UNDETERMINED at staging time. The brief
        # must not assume captions are possible; it asks for them only if there
        # is speech, so a no-speech route is not scored against a caption target.
        "motion": "Energetic and modern. Let the movement lead. Captions only if there is speech worth showing; otherwise carry it with motion and sound.",
        # 10.0s, no speech, zero scene cuts, sfx OUT OF SCOPE at this duration
        # (D_zero 15.2s). A brief asking for a sound effect here would be asking
        # for something the regime rule says cannot be scored.
        "car_short": "Bold and kinetic. One strong moment, tight and punchy. No captions — let the shot and the motion do it.",
    },
}

MODEL = "claude-haiku-4-5"


def main():
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    corpus = sys.argv[1].rstrip("/")
    briefs = BRIEFS.get(corpus)
    if not briefs:
        sys.stderr.write(
            f"no BRIEFS for corpus {corpus!r}. A corpus without briefs cannot be\n"
            f"run: inventing one per fixture at launch time is how a brief stops\n"
            f"matching the source it describes. Add them to build_plan.py.\n"
            f"known: {sorted(BRIEFS)}\n")
        return 2

    import boto3
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3 = boto3.client("s3")
    man = None
    for name in ("manifest.json", "MANIFEST.json"):
        try:
            man = json.loads(s3.get_object(Bucket=bucket,
                                           Key=f"{corpus}/{name}")["Body"].read())
            break
        except Exception:
            continue
    if man is None:
        sys.stderr.write(f"corpus {corpus} has no manifest in s3://{bucket}/\n")
        return 2

    # Only what the manifest lists. An object sitting in the prefix is not part
    # of the corpus — that is exactly what the v3 stray is.
    entries = []
    if isinstance(man, list):
        for e in man:
            if e.get("fixture") and e.get("s3_key"):
                entries.append((e["fixture"], e["s3_key"]))
    elif isinstance(man, dict):
        for fixture, e in sorted(man.items()):
            key = e.get("key") if isinstance(e, dict) else e
            if key:
                entries.append((fixture, key))

    missing = [f for f, _ in entries if f not in briefs]
    if missing:
        sys.stderr.write(f"manifest lists fixture(s) with no brief: {missing}\n")
        return 2
    if not entries:
        sys.stderr.write(f"corpus {corpus} manifest lists no fixtures\n")
        return 2

    for fixture, key in entries:
        sys.stdout.write(f"{fixture}\t{key}\t{briefs[fixture]}\t{MODEL}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
