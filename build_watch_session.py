#!/usr/bin/env python3
"""Build THE WATCH as a real Claude Code session: sheets in, analysis out.

Zac, 2026-09-16: "Cache the watch session itself, not its artefacts. The full
watching conversation as the prefix: the frames it examined, its analysis turn
by turn, its conclusions — as prior context every run resumes from. Not a
document about it, not frames without it."

WHY A SESSION AND NOT A DOCUMENT. A document is a summary handed to the model.
A session is the model's own prior context — it resumes holding the frames it
looked at and the reading it produced, and can be asked about a moment the
summary never mentioned. `--resume` was verified before this was built: a
seeded token came back verbatim from a different cwd, and the session file
transplants (moved to a `-work` slug, original slug deleted, still resolved).

AND RESUMING IS CACHED, MEASURED NOT ASSUMED — AND NEVER WITH --fork-session.
Three consecutive plain `--resume` runs off a pristine copy of a seeded session
read 70,226 / wrote 0 / cost $0.0211, identically every time. The SAME session
under `--fork-session` read 32,318 and wrote ~38,000 EVERY RUN — $0.228, an
order of magnitude worse — and it is forking, not the cwd, that does it: two
forks from the same cwd wrote just as much as two forks from different ones.

So the prefix IS byte-identical across two different jobs and hits in full.
Plain `--resume` is safe in a container precisely BECAUSE the filesystem is
ephemeral: each run mounts a fresh copy of the canonical jsonl and physically
cannot mutate the original, which is the only thing forking was buying.

ONE CLIP PER TURN, ON PURPOSE. Ten turns of analysis is what makes it a watch
rather than a wall of stills: each turn reasons over the clip in front of it
with the previous nine already in context, which is exactly the thing a
document flattens.
"""
import argparse
import base64
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

SEED = """You are about to watch ten short videos, frame by frame.

These ten are the reference standard for a video-editing product. Every edit
the product makes is graded against them. You are watching so that later, when
you edit, you edit like them.

You will get them one clip at a time, as contact sheets. Each cell is a frame
with its source timestamp burned into the corner, sampled at 2 frames per
second, in order, left to right then top to bottom.

For each clip, look at it and write what you see. Be specific and cite
timestamps: where components sit and why, how cuts are made, what the captions
do and where they sit, when a moment is deliberately left alone, what the
opening does in its first seconds, how it ends. Note anything a later editor
would need to reproduce the effect.

Do not summarise politely. Write the reading an editor would write.

There is no audio. Do not describe sound, and do not infer it from the picture.
"""

CLIP_PROMPT = """Clip {n} of 10 — asset {asset}, {dur:.1f}s, {wh}, {frames}
frames at 2fps across {sheets} contact sheet(s).

Watch it and write your reading."""

FINAL = """You have now watched all ten.

Write the synthesis: what these ten share STRUCTURALLY, what differs between
them, and what an editor must do to meet this bar. Where they disagree, say so
— a rule that only one of them follows is not the standard.

This is the reading every edit will resume from. Write it for yourself, later,
mid-edit, deciding whether a placement is good enough."""


def msg(text, sheets=()):
    """A stream-json user message carrying text and contact sheets."""
    blocks = [{"type": "text", "text": text}]
    for p in sheets:
        with open(p, "rb") as fh:
            blocks.append({"type": "image",
                           "source": {"type": "base64",
                                      "media_type": "image/png",
                                      "data": base64.b64encode(
                                          fh.read()).decode()}})
    return json.dumps({"type": "user",
                       "message": {"role": "user", "content": blocks}})


def call(payload, model, sid=None, cwd="/tmp"):
    """One turn. -> (session_id, result_text, usage). Raises on a hard failure."""
    # --input-format stream-json REQUIRES a stream-json output format (the CLI
    # refuses the pairing with `json`), and stream-json output requires
    # --verbose. So the result arrives as the last NDJSON event, not as the
    # whole of stdout.
    cmd = ["claude", "-p", "--input-format", "stream-json",
           "--output-format", "stream-json", "--verbose", "--model", model]
    if sid:
        cmd += ["--resume", sid]
    r = subprocess.run(cmd, input=payload, capture_output=True, text=True,
                       cwd=cwd, timeout=1800)
    d = None
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            d = ev
    # ABSENT IS NOT FAILURE IS NOT SUCCESS. No result event at all is its own
    # state: the stream ended without the turn completing, which a rc-only
    # check reads as fine whenever the CLI exits 0 on a truncated stream.
    if d is None:
        raise RuntimeError("no result event rc=%s: %s"
                           % (r.returncode, (r.stderr or r.stdout)[-400:]))
    if r.returncode != 0:
        raise RuntimeError("claude failed rc=%s: %s"
                           % (r.returncode, (r.stderr or r.stdout)[-400:]))
    # A REFUSAL IS NOT A READING. `is_error` false with an API-error result
    # string is how an errored turn looks like a successful one, and this
    # session's whole value is that the analysis is real.
    res = str(d.get("result") or "")
    if d.get("is_error") or res.startswith("API Error"):
        raise RuntimeError("turn errored: %s" % res[:300])
    return d.get("session_id"), res, (d.get("usage") or {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="/tmp/refwatch/index.json")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--cwd", default="/tmp/watchsession")
    ap.add_argument("--out", default=os.path.join(HERE, "watch_session.json"))
    a = ap.parse_args()

    idx = json.load(open(a.index, encoding="utf-8"))
    os.makedirs(a.cwd, exist_ok=True)
    sid, notes, usage_rows = None, [], []

    for i, (tag, v) in enumerate(sorted(idx.items()), 1):
        sheets = v["sheets"]
        text = (SEED + "\n\n" if i == 1 else "") + CLIP_PROMPT.format(
            n=i, asset=v["asset"][:8], dur=v["dur"], wh=v["wh"],
            frames=v["frames"], sheets=len(sheets))
        sid, out, u = call(msg(text, sheets), a.model, sid, a.cwd)
        usage_rows.append({"turn": i, "tag": tag, **{
            k: u.get(k) for k in ("input_tokens", "output_tokens",
                                  "cache_creation_input_tokens",
                                  "cache_read_input_tokens")}})
        notes.append({"clip": tag, "reading": out})
        print("  %s  %-6s %3d frames  read=%-7s write=%-7s out=%s"
              % (tag, v["wh"], v["frames"],
                 u.get("cache_read_input_tokens"),
                 u.get("cache_creation_input_tokens"),
                 u.get("output_tokens")), flush=True)

    sid, synth, u = call(msg(FINAL), a.model, sid, a.cwd)
    usage_rows.append({"turn": "synthesis", **{
        k: u.get(k) for k in ("input_tokens", "output_tokens",
                              "cache_creation_input_tokens",
                              "cache_read_input_tokens")}})
    print("  synthesis  read=%s write=%s out=%s"
          % (u.get("cache_read_input_tokens"),
             u.get("cache_creation_input_tokens"), u.get("output_tokens")),
          flush=True)

    # WHERE THE SESSION FILE LANDED, resolved rather than assumed — the slug is
    # derived from cwd and a guessed path is a mount that silently carries
    # nothing.
    jsonl = None
    for root, _d, files in os.walk(os.path.expanduser("~/.claude/projects")):
        if "%s.jsonl" % sid in files:
            jsonl = os.path.join(root, "%s.jsonl" % sid)
            break
    rec = {"session_id": sid, "jsonl": jsonl,
           "jsonl_mb": round(os.path.getsize(jsonl) / 1048576.0, 1)
                       if jsonl else None,
           "clips": len(idx), "usage": usage_rows,
           "synthesis": synth, "readings": notes}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    print("\nsession %s  jsonl %s (%s MB)" % (sid, jsonl, rec["jsonl_mb"]))
    print("wrote %s" % a.out)


if __name__ == "__main__":
    sys.exit(main())
