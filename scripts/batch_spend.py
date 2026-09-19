#!/usr/bin/env python3
"""Cumulative model spend of the batch so far: CLI tallies where a record has one, at rate otherwise.
   batch_spend.py [dir=/tmp/batch] — a probe record is TWO calls (control + planted), both counted."""
import glob, json, os, re, sys
D = sys.argv[1] if len(sys.argv) > 1 else "/tmp/batch"


def at_rate(u):
    cc = u.get("cache_creation") or {}
    return ((cc.get("ephemeral_1h_input_tokens") or 0) * 6 / 1e6 + (cc.get("ephemeral_5m_input_tokens") or 0) * 3.75 / 1e6
            + (u.get("cache_read_input_tokens") or 0) * 0.3 / 1e6 + (u.get("output_tokens") or 0) * 15 / 1e6 + (u.get("input_tokens") or 0) * 3 / 1e6)


def total(d, ping_logs=("/tmp/bs/h_warm.log", "/tmp/bs/h_warmlow.log")):
    tot = 0.0
    for f in glob.glob(os.path.join(d, "*.json")):
        if f.endswith("_full.json"):
            continue
        try: r = json.load(open(f))
        except Exception: continue
        if "run_line" in r: tot += float((r["run_line"] or {}).get("usd_cli") or 0)
        elif "review" in r:
            for part in ("control", "review"):
                tot += at_rate((r.get(part) or {}).get("usage") or {})
    for lg in ping_logs:
        try:
            ln = [l for l in open(lg, errors="replace") if "  WARM            :" in l][-1]
            m = re.search(r"write=(\d+) \(1h (\d+) / 5m (\d+)\)", ln); rd = re.search(r"read=(\d+)", ln)
            if m: tot += int(m.group(2)) * 6 / 1e6 + int(m.group(3)) * 3.75 / 1e6
            if rd: tot += int(rd.group(1)) * 0.3 / 1e6
        except Exception: pass
    return tot


if __name__ == "__main__":
    print("%.2f" % total(D))
