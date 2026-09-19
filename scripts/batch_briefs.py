#!/usr/bin/env python3
"""UP TO THREE PRODUCTION BRIEFS for the batch, from Builder-2's fixture file.

  batch_briefs.py [fixtures/production_briefs.v1.jsonl] [outdir]
  stdout: one TAB line per pick   id <TAB> s3-source-key <TAB> brief-file <TAB> slot
  stderr: EVERY row, named:  PICKED / SKIPPED (why) / UNRUNNABLE (fixture without a staged source) / UNREADABLE (line n)
  exit 0 always — zero picks is a listing ("no briefs"), not a failure; a missing file is one UNREADABLE line.

Zac's three slots (2026-09-18): a preset+modifier, a "no captions" constraint, one structured brief. The first
runnable row of each slot in file order is picked; a slot with no row stays empty and is reported so.
The fixture is a NAME (fixtures/README.md); this side maps it to the staged source key. A row whose
fixture has no staged source here is UNRUNNABLE by name, never silently dropped.
Builder-2's rows (landed 7abf206) carry `request_class` (PRESET_PLUS_MODIFIER / STRUCTURED_BRIEF), `flags`
(negative_constraint) and `asks[]` each with `expect` and `means`; the means are recorded beside the pick
for the post-run read-back check; an ask without one is marked UNCHECKED. A preset brief that carries a
no-captions phrase fills the CONSTRAINT slot first — that is the slot Zac named.
"""
import io
import json
import os
import re
import sys

# the staged sources this side can presign (scripts/h_stage.sh carries the same three)
KEYS = {"talking_head": "ab-sources/reliability-fixtures-v3/talking_head-f4195ca9.mp4",
        "motion": "ab-sources/reliability-fixtures-v3/motion-31fa2646.mp4",
        "car_mid": "ab-sources/reliability-fixtures-v3/car_mid-0643be1c.mp4"}
SLOTS = ("preset+modifier", "no-captions constraint", "structured")


def _first(row, *keys):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


_NO_CAPS = re.compile(r"\b(?:no|without|skip|drop|zero)\s+(?:the\s+|any\s+)?(?:captions?|subtitles?|subs)\b|\bcaption-?free\b", re.I)


def slot_of(row, brief):
    """Which of Zac's three slots a row fills: a no-captions phrase claims the constraint slot first
    (whatever the row's class says), then the declared class (Builder-2's `request_class`, or kind/
    category/class/type/slot), then the content."""
    kind = str(_first(row, "request_class", "kind", "category", "class", "type", "slot") or "").lower()
    text = brief if isinstance(brief, str) else json.dumps(brief)
    if _NO_CAPS.search(text) or "caption" in kind or "constraint" in kind:
        return SLOTS[1]
    if "preset" in kind or _first(row, "preset") is not None:
        return SLOTS[0]
    if "structured" in kind or not isinstance(brief, str) or text.lstrip().startswith("{"):
        return SLOTS[2]
    return "other"


def means_of(row):
    """The read-back checks a row asks for: its `asks[]` (n, expect, means) or a row-level means."""
    asks = row.get("asks")
    if isinstance(asks, list) and asks:
        return "; ".join("n%s %s: %s" % (a.get("n"), a.get("expect") or "-", (a.get("means") or "UNCHECKED (no means)")) for a in asks if isinstance(a, dict))
    return row.get("means") or "UNCHECKED (no means)"


def report(status, rid, why=""):
    print("  %-10s %s%s" % (status, rid, (" — " + why) if why else ""), file=sys.stderr)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "fixtures/production_briefs.v1.jsonl"
    outdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/bs"
    os.makedirs(outdir, exist_ok=True)
    print("BRIEFS from %s" % path, file=sys.stderr)
    if not os.path.exists(path):
        report("UNREADABLE", path, "no such file (Builder-2's rows have not landed)")
        return 0
    picked, seen = {}, 0
    for n, line in enumerate(io.open(path, encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("not an object")
        except Exception as e:                                    # noqa: BLE001
            report("UNREADABLE", "line %d" % n, str(e)[:80]); continue
        seen += 1
        rid = re.sub(r"[^A-Za-z0-9_.-]", "-", str(_first(row, "id", "name") or "row%d" % n))[:40]
        fixture = str(_first(row, "fixture", "fixture_name", "source") or "")
        brief = _first(row, "brief", "text", "prompt")
        if brief is None:
            report("SKIPPED", rid, "no brief"); continue
        if fixture not in KEYS:
            report("UNRUNNABLE", rid, "fixture %r has no staged source here%s" % (fixture, (": " + str(row.get("fixture_note"))) if row.get("fixture_note") else "")); continue
        slot = slot_of(row, brief)
        if slot not in SLOTS:
            report("SKIPPED", rid, "fills none of the three slots"); continue
        if slot in picked:
            report("SKIPPED", rid, "slot %s already filled by %s" % (slot, picked[slot])); continue
        text = brief if isinstance(brief, str) else json.dumps(brief, ensure_ascii=False, indent=1)
        bf = os.path.join(outdir, "brief_%s.txt" % rid)
        io.open(bf, "w", encoding="utf-8").write(text.strip() + "\n")
        picked[slot] = rid
        report("PICKED", rid, "%s | fixture %s | class %s | asks %s" % (slot, fixture, _first(row, "request_class", "kind") or "-", means_of(row)[:400]))
        print("\t".join([rid, KEYS[fixture], bf, slot]))
    for sl in SLOTS:
        if sl not in picked:
            report("EMPTY", sl, "no runnable row fills this slot")
    print("%d row(s) read, %d picked" % (seen, len(picked)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
