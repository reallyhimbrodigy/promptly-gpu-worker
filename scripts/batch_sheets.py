#!/usr/bin/env python3
"""The probe's sheets, out of the record and onto disk for Zac's eye: batch_sheets.py <full-record.json> <out-prefix>"""
import base64, json, sys
rec = json.load(open(sys.argv[1], encoding="utf-8")); pre = sys.argv[2]; names = []
for tag, lst in (rec.get("sheets_b64") or {}).items():
    for i, b in enumerate(lst, 1):
        p = "%s_%s_%d.jpg" % (pre, tag, i); open(p, "wb").write(base64.b64decode(b)); names.append(p)
print("SHEETS %s: %s" % (rec.get("density_fps"), ", ".join(names) or "NONE in the record"))
