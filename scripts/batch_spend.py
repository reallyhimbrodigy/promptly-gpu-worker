#!/usr/bin/env python3
"""Cumulative model spend of the batch so far: CLI tallies where a record has one, at rate otherwise."""
import glob, json, re
tot = 0.0
for f in glob.glob("/tmp/batch/*.json"):
    try: r = json.load(open(f))
    except Exception: continue
    if "run_line" in r: tot += float((r["run_line"] or {}).get("usd_cli") or 0)
    elif "review" in r:
        u = (r["review"] or {}).get("usage") or {}; cc = u.get("cache_creation") or {}
        tot += (cc.get("ephemeral_1h_input_tokens") or 0)*6/1e6 + (cc.get("ephemeral_5m_input_tokens") or 0)*3.75/1e6 + (u.get("cache_read_input_tokens") or 0)*0.3/1e6 + (u.get("output_tokens") or 0)*15/1e6
try:
    ln = [l for l in open("/tmp/bs/h_warm.log", errors="replace") if "  WARM            :" in l][-1]
    m = re.search(r"write=(\d+) \(1h (\d+) / 5m (\d+)\)", ln); rd = re.search(r"read=(\d+)", ln)
    if m: tot += int(m.group(2))*6/1e6 + int(m.group(3))*3.75/1e6
    if rd: tot += int(rd.group(1))*0.3/1e6
except Exception: pass
print("%.2f" % tot)
