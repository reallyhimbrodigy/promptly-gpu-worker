#!/usr/bin/env python3
"""THE DEV PREFIX (Zac, 2026-09-19): two references, ~20k tokens, cents per call.

  build_dev_watch.py [--out watch_session_dev.jsonl] [--clips 1,3]

WHY. The full watch is 210,082 of the 226,384-token shared prefix — 92.8%, and
$0.068 to read on every call, $1.36 to write cold on every ping. The full
prefix is for QUALITY READS. A cache proof, a constraint proof, a preflight
proof and any plumbing run do not need ten reference videos to prove that a
breakpoint landed or that a caption track violates a brief — they need a
prefix SHAPED like the real one (a resumed session, a system prompt, images,
an assistant turn) and small enough to be free.

WHAT IT KEEPS. Two clips with their real frames and their real readings, in
the original wire shape, so the CLI resumes it exactly as it resumes the full
one. It does NOT keep the ten-clip synthesis: that document says "10 clips"
and would be a wrong note in a two-clip watch — worse than a missing one.

WHAT IT IS NOT. Not a quality standard. The intro sentence says so in the
prefix itself, so an agent reading it cannot mistake two references for ten.

DETERMINISTIC. The session id is derived from the content by sha256, so
rebuilding produces the same id and the same bytes — a session id that moved
would make every dev run a cold write, which is the cost this exists to avoid.
"""
import argparse
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTRO = ("You are about to watch TWO of the ten short reference videos, frame by frame. "
         "THIS IS A DEVELOPMENT PREFIX, not the reading standard: the full watch is ten "
         "clips and a synthesis, and this is a deliberately small stand-in used for "
         "plumbing runs (cache, constraint and preflight proofs). Do not treat two clips "
         "as the standard the edit is graded against.\n\n")


def blocks_of(msg):
    c = (msg.get("message") or {}).get("content")
    return c if isinstance(c, list) else []


def size_of(line):
    o = json.loads(line)
    c = (o.get("message") or {}).get("content")
    txt = c if isinstance(c, str) else " ".join((b.get("text") or "") for b in (c or []) if isinstance(b, dict))
    imgs = 0 if isinstance(c, str) else sum(1 for b in (c or []) if isinstance(b, dict) and b.get("type") == "image")
    return len(txt), imgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "watch_session.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "watch_session_dev.jsonl"))
    ap.add_argument("--sid-out", default=os.path.join(HERE, "watch_session_dev_id.txt"))
    ap.add_argument("--clips", default="1,3", help="which reference clips to keep, 1-based")
    a = ap.parse_args()
    lines = io.open(a.src, encoding="utf-8").readlines()
    # THE WIRE SHAPE, READ NOT ASSUMED: user messages carrying images are the clips,
    # each followed by the assistant turns that read it. Index them rather than
    # hard-coding line numbers, which a re-record would silently move.
    clips = []          # [(user_idx, [assistant_idx...])]
    for i, l in enumerate(lines):
        try: o = json.loads(l)
        except Exception: continue
        if o.get("type") == "user" and any(b.get("type") == "image" for b in blocks_of(o)):
            clips.append((i, []))
        elif o.get("type") == "assistant" and clips:
            txt, _ = size_of(l)
            if txt > 2000:                      # the reading, not an empty tool-turn
                clips[-1][1].append(i)
    want = [int(x) for x in a.clips.split(",") if x.strip()]
    if any(w < 1 or w > len(clips) for w in want):
        sys.exit("asked for clips %s but the watch holds %d" % (want, len(clips)))
    keep = set()
    for i, l in enumerate(lines):                # the scaffolding the CLI needs
        try: t = json.loads(l).get("type")
        except Exception: t = None
        if t in ("queue-operation", "attachment", "file-history-snapshot", "last-prompt", "mode"):
            keep.add(i)
    for w in want:
        u, asst = clips[w - 1]
        keep.add(u); keep.update(asst)
    out = []
    for i in sorted(keep):
        o = json.loads(lines[i])
        if i == clips[want[0] - 1][0]:           # the first kept clip carries the honest intro
            for b in blocks_of(o):
                if b.get("type") == "text":
                    b["text"] = INTRO + b.get("text", "").split("\n\n", 1)[-1]
                    break
        out.append(json.dumps(o, ensure_ascii=False))
    body = "\n".join(out) + "\n"
    sid = hashlib.sha256(body.encode()).hexdigest()
    sid = "%s-%s-%s-%s-%s" % (sid[:8], sid[8:12], sid[12:16], sid[16:20], sid[20:32])
    body = body.replace(json.loads(lines[clips[0][0]]).get("sessionId", ""), sid) if json.loads(lines[clips[0][0]]).get("sessionId") else body
    io.open(a.out, "w", encoding="utf-8").write(body)
    io.open(a.sid_out, "w", encoding="utf-8").write(sid + "\n")
    ch = sum(size_of(l)[0] for l in out); im = sum(size_of(l)[1] for l in out)
    print("DEV WATCH: %d lines, %.2f MB, %d text chars (~%d tok) + %d images (~%d tok) = ~%d tokens"
          % (len(out), len(body) / 1e6, ch, ch // 4, im, im * 1400, ch // 4 + im * 1400))
    print("  clips kept: %s of %d | sid %s | -> %s" % (want, len(clips), sid, a.out))


if __name__ == "__main__":
    main()
