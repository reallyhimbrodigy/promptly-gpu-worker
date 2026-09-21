#!/usr/bin/env python3
"""Persist the code ChatCut ACTUALLY REGISTERED to a file, mechanically.

WHY THIS EXISTS. `registered_diff.mjs` takes a PATH. `inspect_asset` returns the
registered code inside an MCP tool result, which lands in the agent's context and
nowhere else. The gap between those two facts was being closed by an agent
reading the diff by eye — and eyeballing a diff is exactly how a SECOND
difference goes unnoticed while the first one is explained away.

THE CIRCULARITY THIS FILE REFUSES. The obvious shortcut is to retype the
registered code into a heredoc. That is not a transcription risk, it is a
CORRECTNESS risk with a direction: retyping the registered code while the SOURCE
is on screen biases every keystroke toward the source, and the differ then reads
IDENTICAL because the two files were copied from one original. A diff whose
inputs were reconciled by the person running it proves nothing.

So the registered code is never touched by hand. It is read out of the session
transcript, which the harness writes verbatim, and only ever out of a
`tool_result` block.

**tool_result ONLY, and this is the whole safety property.** The same transcript
also holds `tool_use` blocks — the registration CALLS — whose `code` argument is
the SOURCE I sent. Reading one of those would compare the source against itself
and print IDENTICAL for a component ChatCut had rewritten. The two are one JSON
key apart in the same file, so the guard is explicit and the extractor REFUSES a
tool_use rather than silently preferring a tool_result.

Usage: python3 port/persist_registered.py <AssetName> <out-path> [transcript]
Exit 0 on a written file; exit 2 on ABSENT/ambiguous, which is a state, not a
zero-length file.
"""
import json
import os
import sys

DEFAULT_T = os.path.expanduser(
    "~/.claude/projects/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/"
    "20a96082-2335-4611-b170-f082b4b734ff.jsonl")


def _payloads(line):
    """Yield (block_type, parsed_json) for every block on one transcript line."""
    try:
        ev = json.loads(line)
    except Exception:
        return
    msg = ev.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, list):
        return
    for b in content:
        if not isinstance(b, dict):
            continue
        bt = b.get("type")
        if bt == "tool_result":
            c = b.get("content")
            texts = []
            if isinstance(c, str):
                texts = [c]
            elif isinstance(c, list):
                texts = [x.get("text") or "" for x in c if isinstance(x, dict)]
            for t in texts:
                try:
                    yield bt, json.loads(t)
                except Exception:
                    continue
        elif bt == "tool_use":
            yield bt, b.get("input") or {}


def find(name, transcript=DEFAULT_T):
    """Return (code, line_no) for the LAST inspect_asset read-back of `name`.

    Refuses tool_use outright — see the module docstring. Counts what it saw so
    an empty population can never pass as a clean result.
    """
    found, refused_tool_use = [], 0
    with open(transcript, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            if name not in line:
                continue
            for bt, obj in _payloads(line):
                if not isinstance(obj, dict):
                    continue
                if bt == "tool_use":
                    # the registration CALL. Its `code` is the SOURCE.
                    if obj.get("name") == name and "code" in obj:
                        refused_tool_use += 1
                    continue
                asset = obj.get("asset")
                if not isinstance(asset, dict):
                    continue
                if asset.get("name") != name:
                    continue
                code = asset.get("code")
                if isinstance(code, str) and code:
                    found.append((code, ln, asset.get("id")))
    return found, refused_tool_use


def main():
    if len(sys.argv) < 3:
        print("usage: persist_registered.py <AssetName> <out-path> [transcript]")
        return 2
    name, out = sys.argv[1], sys.argv[2]
    t = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_T
    if not os.path.exists(t):
        print("HARNESS FAILURE: transcript ABSENT at %s" % t)
        return 2
    found, refused = find(name, t)
    print("  tool_use registration calls REFUSED : %d" % refused)
    print("  inspect_asset read-backs found      : %d" % len(found))
    if not found:
        print("  ABSENT — no inspect_asset read-back for %r in the transcript. "
              "Run inspect_asset on it first; this is a missing measurement, "
              "not an empty diff." % name)
        return 2
    code, ln, aid = found[-1]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(code)
    print("  WROTE %s  (%d chars) from transcript line %d, asset %s"
          % (out, len(code), ln, aid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
