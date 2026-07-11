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


# OCCURRENCE records (never deduped — each one is a real second/dollar):
OCCURRENCE_RULES = {
    "recipe_repair:repair_reask",
    "recipe_transport:gemini_degen_tail",
    "recipe_transport:degen_retry",
    "render:video_reference_fallback",
    "recipe:safe_edit_fallback",
    "render:render_stripped",
}


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
    # WATCH 1 (Zac 2026-07-10): per-class repair columns — the convergence
    # finding generalizes (whole-plan re-ask × per-component predicates =
    # whack-a-mole for EVERY raise class; F5 was just the loudest). The
    # table decides per class whether raise keeps its value or takes K7.
    def _repair_class(r):
        if "NUMBER must come" in r:
            return "F5.3-number"
        if "no face-clear region" in r:
            return "F7-clear-region"
        if "viewers need" in r:
            return "F6-reading-floor"
        if "card text must be drawn" in r:
            return "F5-text(dead-9495895)"
        return "other"
    repair_fires = Counter()
    repair_jobs = defaultdict(set)
    repair_fixed = defaultdict(set)
    repair_exhausted = defaultdict(set)
    # WATCH 2: drop-precision — the dropped texts, verbatim, with counts.
    drop_texts = Counter()
    for k in keys:
        n_jobs += 1
        body = s3.get_object(Bucket=bucket, Key=k)["Body"].read().decode("utf-8", "replace")
        # DEDUP SEMANTICS (Zac ruling 2026-07-10) — two record species:
        #   OBSERVATION — a property of the final plan/timeline (recipe_eval
        #     rules, cut_boundary geometry, ...): repair re-attempts re-observe
        #     the same property, so identical records (minus wall-clock t)
        #     collapse — only the shipped plan's story counts.
        #   OCCURRENCE — a real event, a real second, a real dollar
        #     (repair re-asks, degen fires, reference fallbacks, safe edits,
        #     render strips): NEVER deduped — the weekly repair fire-rate is
        #     a latency line item and must be the attempt count.
        _seen = set()
        for line in body.splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            _rule_key = f"{rec.get('component')}:{rec.get('action')}"
            if _rule_key not in OCCURRENCE_RULES:
                _k = json.dumps({k2: v2 for k2, v2 in rec.items() if k2 != "t"},
                                sort_keys=True, default=str)
                if _k in _seen:
                    continue
                _seen.add(_k)
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
            if rule == "recipe_repair:repair_reask":
                _cls = _repair_class(str(rec.get("reason") or ""))
                repair_fires[_cls] += 1
                repair_jobs[_cls].add(k)
            if rule.endswith(":drop_ungrounded_text") and isinstance(orig, dict):
                drop_texts[str(orig.get("text") or "?")[:60]] += 1
        # outcome attribution: exhaust attributed to EVERY class that fired
        # in the job (the whack-a-mole mechanism makes single-attribution
        # dishonest — attempt 2's violation is often a different class).
        _job_safe = "safe_edit_fallback" in body
        for _cls, _jobs in repair_jobs.items():
            if k in _jobs:
                (repair_exhausted if _job_safe else repair_fixed)[_cls].add(k)
    lines = [f"WEEKLY QUALITY TABLE — last {days}d · {n_jobs} job ledger(s) · "
             f"{sum(counts.values())} record(s) (observations deduped; occurrences counted raw)", "=" * 78]
    if repair_fires:
        lines.append("")
        lines.append("REPAIR CLASSES — fire / fixed / exhausted (whack-a-mole watch; "
                     "exhaust attributed to each class firing in the job)")
        for _cls, _n in repair_fires.most_common():
            lines.append(f"{_n:>5}  {_cls}: jobs={len(repair_jobs[_cls])} "
                         f"fixed={len(repair_fixed[_cls])} exhausted={len(repair_exhausted[_cls])}")
        lines.append("       standing: F5.3 stays raise by the brand bar (an invented "
                     "number is a fabrication); if its exhausts kill videos, "
                     "drop-the-lying-card removes the lie AND saves the plan.")
    if drop_texts:
        lines.append("")
        lines.append("DROP-PRECISION WATCH — drop_ungrounded_text verbatim (audit record "
                     "4/4 false-positive; sustained designer-quality drops convict the "
                     "predicate → the drop ruling revisits, and this line IS the priced "
                     "Lumen-tier business case)")
        for _t, _n in drop_texts.most_common(8):
            lines.append(f"{_n:>5}  {_t!r}")
    lines.append("")
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
