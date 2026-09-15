#!/usr/bin/env python3
"""The component sheet: every component that RENDERS, as a picture, with the
condition it serves and the props it takes beside it. No ranking.

WHY A SHEET AND NOT A LIST. The worker cannot choose a component it has never
seen. A name in a prompt is a promise; a frame is the thing itself. And the
sheet is built FROM THE RENDER CHECK, so a component that did not draw pixels
in ChatCut is not on it — which is the whole point: a component not on the
sheet is not offered.

The WHEN heading and the props shape come from knowledge/05_motion_graphics.md
— the same eight conditions the pipeline's own knowledge file is organised by,
read from that file rather than restated here, so the sheet cannot drift from
the knowledge the planner uses.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KNOW = os.path.join(HERE, "knowledge", "05_motion_graphics.md")


def conditions():
    """{component: {"when": heading, "size": ..., "claim": ..., "props": ...}}"""
    src = open(KNOW, encoding="utf-8").read()
    out, when = {}, None
    for line in src.splitlines():
        m = re.match(r"^──\s*(WHEN .+?)\s*──\s*$", line)
        if m:
            when = m.group(1)
            continue
        m = re.match(r"^\*\*(\w+)\*\*\s*\(([^)]+)\)\s*—\s*(.+)$", line)
        if m and when:
            name, size, body = m.group(1), m.group(2), m.group(3)
            claim = ""
            c = re.search(r'Claim:\s*"([^"]+)"', body)
            if c:
                claim = c.group(1)
            out[name] = {"when": when, "size": size, "claim": claim,
                         "what": body.split("Claim:")[0].strip().rstrip(".")}
            continue
        m = re.match(r"^Props(?: \(([^)]+)\))?:\s*(\{\{.*\}\})\s*$", line)
        if m and out:
            last = list(out)[-1]
            shape = m.group(2).replace("{{", "{").replace("}}", "}")
            out[last].setdefault("props", []).append(
                (m.group(1) or "", shape))
    return out


def build(out_dir):
    """Compose the sheet from the frames the render check carried home.

    `rows.json` and the jpegs are written by the `rendercheck` entrypoint, so
    the sheet is built from BYTES that were verified to differ from that
    component's own empty frame — never from a presigned URL that has since
    expired, and never from a name on a list.
    """
    rows = json.load(open(os.path.join(out_dir, "rows.json"), encoding="utf-8"))
    cond = conditions()
    sheet, missing_condition = [], []
    for n in sorted(rows):
        if rows[n]["state"] != "MEASURED":
            continue
        path = os.path.join(out_dir, n + ".jpg")
        if not os.path.exists(path):
            print("  %-18s MEASURED BUT NO FRAME ON DISK — not offered" % n)
            continue
        if rows[n].get("content_unavailable"):
            print("  %-18s DRAWS, BUT ITS CONTENT CANNOT BE CARRIED (%s) "
                  "— not offered" % (n, ", ".join(rows[n]["content_unavailable"])))
            continue
        c = cond.get(n)
        if not c:
            missing_condition.append(n)
            continue
        sheet.append({"name": n, "frame": os.path.basename(path),
                      "when": c["when"], "size": c["size"],
                      "claim": c["claim"], "what": c["what"],
                      "props": c.get("props", []),
                      "evidence": rows[n]["detail"]})
    manifest = os.path.join(out_dir, "sheet.json")
    json.dump({"entries": sheet,
               "rendered_but_unconditioned": missing_condition},
              open(manifest, "w", encoding="utf-8"), indent=1)
    print("  sheet: %d components with a frame and a condition" % len(sheet))
    if missing_condition:
        print("  RENDERS BUT HAS NO `WHEN` IN THE KNOWLEDGE FILE (not offered): %s"
              % ", ".join(missing_condition))
    by = {}
    for e in sheet:
        by.setdefault(e["when"], []).append(e["name"])
    for w in sorted(by):
        print("  %-46s %s" % (w, ", ".join(sorted(by[w]))))
    return manifest


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--conditions":
        c = conditions()
        print("%d components carry a WHEN condition" % len(c))
        for n, v in sorted(c.items()):
            print("  %-18s %-44s %s" % (n, v["when"], v["size"]))
        sys.exit(0)
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "sheet"))
