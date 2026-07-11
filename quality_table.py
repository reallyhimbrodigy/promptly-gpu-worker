"""THE WEEKLY QUALITY TABLE — the Phase-2 instrument (Zac 2026-07-10).

One command:  modal run quality_table.py            (last 7 days)
              modal run quality_table.py --days 14

Reads the divergence ledger (s3://<bucket>/divergences/*.jsonl) and prints
rule × count × style × vibe for every quality watch in one view:
  recipe_eval:<rule>       — the taste telemetry (this pin)
  recipe_repair:repair_reask — the four MG raise-classes + every repair class
  recipe_transport:gemini_degen_tail — degeneration fires, tail included
  transition:slot_clamp    — room-at-execution (new-generation = real alarm)
  render:video_reference_fallback · motion_graphic:drop_empty_props · the rest
The loop: read the aggregate → edit the prompt → next week's table confirms.
Never a gate, never a repair trigger — a human reads this.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal
try:
    from modal_app import image
except ModuleNotFoundError:
    image = None
app = modal.App("promptly-quality-table", image=image,
                secrets=[modal.Secret.from_name("promptly-secrets")])


@app.function(timeout=600, cpu=4, memory=8192, region=["us-west", "us-east"])
def run(days: int = 7):
    import boto3, json, datetime
    from collections import Counter, defaultdict
    bucket = os.environ.get("S3_BUCKET_NAME") or "promptly-video-storage"
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION") or "us-west-1")
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    keys = []
    tok = None
    while True:
        kw = {"Bucket": bucket, "Prefix": "divergences/"}
        if tok:
            kw["ContinuationToken"] = tok
        resp = s3.list_objects_v2(**kw)
        for o in resp.get("Contents", []):
            if o["LastModified"] >= cutoff:
                keys.append(o["Key"])
        if not resp.get("IsTruncated"):
            break
        tok = resp.get("NextContinuationToken")
    counts = Counter()
    by_style = defaultdict(Counter)
    by_vibe = defaultdict(Counter)
    samples = defaultdict(list)
    n_jobs = 0
    for k in keys:
        n_jobs += 1
        body = s3.get_object(Bucket=bucket, Key=k)["Body"].read().decode("utf-8", "replace")
        # DEDUP (rule audit 2026-07-10): records written inside the repair
        # loop double-write on re-attempts (convicted in both audits — the
        # ×9 was 5, the ×12 was 6). Identical full lines within one job
        # collapse to one; only the shipped plan's story counts.
        for line in dict.fromkeys(body.splitlines()):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            comp = str(rec.get("component") or "?")
            act = str(rec.get("action") or "?")
            rule = f"{comp}:{act}"
            counts[rule] += 1
            orig = rec.get("original") or {}
            if isinstance(orig, dict):
                if orig.get("style"):
                    by_style[rule][str(orig["style"])] += 1
                if orig.get("vibe"):
                    by_vibe[rule][str(orig["vibe"])[:40]] += 1
            r = str(rec.get("reason") or "")[:110]
            if r and len(samples[rule]) < 2 and r not in samples[rule]:
                samples[rule].append(r)
    lines = [f"WEEKLY QUALITY TABLE — last {days}d · {n_jobs} job ledger(s) · "
             f"{sum(counts.values())} record(s) (repair-attempt duplicates collapsed)", "=" * 78]
    for rule, n in counts.most_common():
        lines.append(f"{n:>5}  {rule}")
        st = ", ".join(f"{s}×{c}" for s, c in by_style[rule].most_common(3))
        vb = ", ".join(f"{s!r}×{c}" for s, c in by_vibe[rule].most_common(2))
        if st:
            lines.append(f"       style: {st}")
        if vb:
            lines.append(f"       vibe:  {vb}")
        for smp in samples[rule]:
            lines.append(f"       e.g.   {smp}")
    return "\n".join(lines)


@app.local_entrypoint()
def main(days: int = 7):
    print(run.remote(days))
