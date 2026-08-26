#!/usr/bin/env python3
"""IS THE ASR DIVERSION CORRECT? — the query the row now answers by itself.

Before 2026-08-17 this question could only be answered by downloading
production sources and re-transcribing them by hand (a night, $0.118 of
Deepgram, and a control arm to make the zeros believable). A diverted row
stored `"transcript": []` and nothing else.

Now every job carries `result.asr_diagnostics`:

    word_count          the exact number the routing gate branches on
    mean_dbfs/max_dbfs  level of the bytes ASR ACTUALLY received
    speech_band_dbfs    300-3400 Hz — where speech lives
    bass_dbfs           <250 Hz — where music lives
    level_status        measured | failed | absent  (NEVER a number on failure)
    zero_words_verdict  consistent_no_speech | suspect_miss | unknown

CALIBRATION (measured, n=9, 2026-08-17): known-speech controls separated from
diverted sources by speech_band - bass of +6.8 dB vs -0.8 dB. The threshold
here is 4.0 dB. It is a TRIAGE LABEL, not truth — every input that produced it
is stored beside it, so the label can be re-derived or overruled from the row.

    python3 read_asr_diagnostics.py [--since 2026-08-17] [--limit 500]

Reports per-USER counts alongside per-job (Rule 7): a user who retries five
times is one lost user, not five failures.
"""
import argparse
import collections
import json
import os
import sys
import urllib.request

ENV = "/Users/zaclibman/content-studio/.env.local"
ASR_REASONS = ("no_speech", "no_speech_muted", "transcription_incomplete", "no_audio")


def _creds():
    env = {}
    with open(ENV) as fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return (env["SUPABASE_URL"],
            env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SERVICE_KEY"))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-17")
    ap.add_argument("--limit", type=int, default=500)
    a = ap.parse_args(argv)
    url, key = _creds()
    q = (f"{url.rstrip('/')}/rest/v1/video_jobs"
         f"?select=id,user_id,source_duration,result,edit_recipe->>route,edit_recipe->>reason"
         f"&created_at=gte.{a.since}&status=eq.completed&limit={a.limit}")
    req = urllib.request.Request(q, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    rows = json.load(urllib.request.urlopen(req, timeout=180))

    have = [r for r in rows if isinstance((r.get("result") or {}).get("asr_diagnostics"), dict)]
    print(f"  window since {a.since}: {len(rows)} completed, "
          f"{len(have)} carry asr_diagnostics ({100.0*len(have)/max(len(rows),1):.1f}%)")
    if not have:
        # A ZERO HERE IS NOT AN ANSWER. Pre-deploy rows cannot carry the block,
        # so an empty read means "not live yet", never "no misses".
        print("  NO ROWS CARRY THE BLOCK YET — jobs from before the deploy cannot,")
        print("  so this is 'not observed', NOT 'zero misses'. Re-run after traffic lands.")
        return 0

    stat = collections.Counter(d["result"]["asr_diagnostics"].get("level_status") for d in have)
    print(f"  level_status: {dict(stat)}   (failed/absent are HONEST — never a number)")

    zero = [r for r in have
            if (r["result"]["asr_diagnostics"].get("word_count") == 0)
            and r.get("reason") in ASR_REASONS]
    print(f"\n  ASR-diverted with a measured 0-word transcript: {len(zero)} jobs, "
          f"{len({r['user_id'] for r in zero})} users")
    v = collections.Counter(r["result"]["asr_diagnostics"].get("zero_words_verdict") for r in zero)
    for k, n in v.most_common():
        users = len({r["user_id"] for r in zero
                     if r["result"]["asr_diagnostics"].get("zero_words_verdict") == k})
        print(f"     {str(k):24} {n:5} jobs   {users:5} users")

    miss = [r for r in zero
            if r["result"]["asr_diagnostics"].get("zero_words_verdict") == "suspect_miss"]
    if miss:
        print(f"\n  SUSPECT MISSES — audio is speech-shaped but ASR returned nothing.")
        print(f"  These are users who uploaded a talking video and got a music edit:")
        print(f"  {'job':10}{'dur':>7}{'mean_dB':>9}{'sp-bass':>9}{'lang':>8}  reason")
        for r in sorted(miss, key=lambda x: -(x["result"]["asr_diagnostics"].get("speech_band_dbfs") or -99))[:20]:
            d = r["result"]["asr_diagnostics"]
            sb, bs = d.get("speech_band_dbfs"), d.get("bass_dbfs")
            print(f"  {r['id'][:8]:10}{(r.get('source_duration') or 0):7.1f}"
                  f"{(d.get('mean_dbfs') or 0):9.1f}"
                  f"{((sb - bs) if sb is not None and bs is not None else 0):9.1f}"
                  f"{str(d.get('detected_language')):>8}  {r.get('reason')}")

    ed = [r for r in have if not r.get("route")]
    if ed:
        wc = sorted((r["result"]["asr_diagnostics"].get("word_count") or 0) for r in ed)
        print(f"\n  DENOMINATOR — jobs that DID reach editorial: {len(ed)}, "
              f"word_count min={wc[0]} med={wc[len(wc)//2]} max={wc[-1]}")
    else:
        print(f"\n  DENOMINATOR — 0 jobs reached editorial in this window.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
