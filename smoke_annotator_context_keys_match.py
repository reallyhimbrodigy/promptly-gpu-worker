#!/usr/bin/env python3
"""Every context key the annotator prompt names must exist in the payload.

CAUGHT ITSELF WITHIN MINUTES. Renaming `cut` -> `shot_change` updated the prompt
in both annotators and the PAYLOAD in only one: the listening app advertised
`mechanical_shot_change_timestamps_s` and sent `mechanical_cut_timestamps_s`.
Nothing would have errored — the annotator is simply told to read a field that
is not there, the mechanical shot changes go unread, and the records come back
looking normal.

This is "advertise a shape, accept that shape" pointed at a prompt rather than a
schema: the prompt PUBLISHES a key, so the payload must carry that key.

TWO PROPERTIES:
  1. every `"key"` the prompt refers to inside its CONTEXT description exists in
     the JSON the code actually sends;
  2. both annotators name the same keys — they are built from one schema and a
     divergence means the rebuild did not happen.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "build_reference_records.py")
LISTEN_PROMPT = os.path.join(HERE, "reference_listen_prompt.txt")
LISTEN_APP = os.path.join(HERE, "reference_listen_app.py")

fail = 0
frames_src = open(FRAMES, encoding="utf-8").read()
listen_prompt = open(LISTEN_PROMPT, encoding="utf-8").read()
listen_app = open(LISTEN_APP, encoding="utf-8").read()

# THE CONTEXT KEYS ARE NAMED IN THE CODE, NOT IN THE PROMPT TEXT — which the
# first version of this check got wrong. It asked whether the PROMPT named a key
# and then whether the app sent it; the prompt names none of them (they live in
# each app's CONTEXT payload), so the guard was always False and that leg
# asserted nothing. It passed a mutation that drifted the key, which is how I
# found out.
#
# The real invariant: the two annotators read ONE schema and must therefore be
# handed the SAME context keys. A key present in one payload and absent from the
# other means one reader is answering with information the other never had.
def _ctx_keys(src):
    """The keys each app puts in its CONTEXT json, read from the source."""
    out = set()
    for m in re.finditer(r'"(mechanical_[a-z_]+|duration_s|transcript)"\s*:', src):
        out.add(m.group(1))
    return out

frames_keys = _ctx_keys(frames_src)
listen_keys = _ctx_keys(listen_app)
if not frames_keys or not listen_keys:
    print(f"  *** context keys could not be read (frames={sorted(frames_keys)}, "
          f"listen={sorted(listen_keys)}) — this check inspected nothing")
    fail += 1
only_f = sorted(frames_keys - listen_keys)
only_l = sorted(listen_keys - frames_keys)
if only_f or only_l:
    print(f"  *** the two annotators are handed DIFFERENT context keys — "
          f"frames-only {only_f}, listening-only {only_l}. They read one schema, "
          f"so one of them is being told to read a field the other never sends, "
          f"and nothing errors: the value simply goes unread.")
    fail += 1
KEYS = frames_keys | listen_keys

# 2. ONE SCHEMA, TWO READERS. The listening prompt is rebuilt from the frames
#    annotator's SCHEMA_INSTRUCTION; a divergence means the rebuild was skipped.
i = frames_src.index('SCHEMA_INSTRUCTION = """') + len('SCHEMA_INSTRUCTION = """')
j = frames_src.index('"""', i)
base = frames_src[i:j]
if not listen_prompt.startswith(base):
    print("  *** the listening prompt is not the frames schema plus its audio "
          "section — the two annotators have diverged and answer different "
          "questions about the same ten videos")
    fail += 1

print(f"smoke_annotator_context_keys_match: {len(KEYS)} context key(s), {fail} wrong")
sys.exit(1 if fail else 0)
