#!/usr/bin/env python3
"""PASS 2 — find the repeated vocabulary across ten freely-named videos.

Zac, 2026-09-11: "Let the annotator name freely, then find the repeated
vocabulary across ten videos in a second pass. A family that appears in eight of
ten under different words is a real family; one that appears once is an
observation. That's how you discover families rather than assume them."

WHY TWO PASSES AND NOT ONE. A single pass that both observes and categorises
will categorise into whatever it was primed with, which is the closed enum
wearing a different hat. Pass 1 never sees a family list. Pass 2 never sees the
video — only the names, so it cannot re-watch and re-decide.

THE DISCOVERY STATISTIC IS VIDEOS, NOT OCCURRENCES. One video that whip-cuts
forty times is one editor's habit; four videos that each whip-cut twice is a
FAMILY. Counting occurrences would rank the habit above the family, which is
exactly the mistake the per-25s rates made.

EVERY OBSERVATION IS ACCOUNTED FOR. The clustering is checked afterwards: each
input name must land in exactly one cluster, and a name the model dropped or
invented FAILS the pass. A clustering that quietly loses observations reports a
smaller vocabulary than the corpus holds, which is the partial-index failure in
a new place.

    python3 cluster_reference_vocabulary.py /tmp/refcorpus_open
"""
import json
import os
import re
import sys
import urllib.request

MODEL = "claude-sonnet-5"
MAX_TOKENS = int(os.environ.get("CLUSTER_MAX_TOKENS", "64000"))
# Bounded so the answer has room. See the note at the request body.
EFFORT = os.environ.get("CLUSTER_EFFORT", "low")

PROMPT = """You are finding the REPEATED VOCABULARY in how ten short-form videos are edited.

Ten videos were annotated INDEPENDENTLY, each naming what it saw in its own
words with no family list to choose from. Below is every treatment observed,
with the video it came from and what the annotator said it does.

Your job is to find which of these are THE SAME MOVE under different words.

Return JSON only:

{
  "families": [
    {
      "family": "<your name for this move — the words an editor would use>",
      "what_it_does": "<the observable effect, in one sentence>",
      "members": ["<every observation name that belongs here, VERBATIM>"],
      "why_one_family": "<what makes these the same move rather than similar ones>"
    }
  ],
  "singletons": ["<observation names that belong to no family, VERBATIM>"]
}

RULES:

- EVERY name below must appear exactly once, either in one family's `members`
  or in `singletons`. Do not drop one, do not invent one, do not put one in two
  families. This is checked mechanically and a mismatch fails the pass.

- CLUSTER BY WHAT IT DOES, NOT BY WORDING. 'warm color-wash flash', 'flash whip
  transition' and 'white flash wipe' are one move. 'screen-recording cutaway'
  and 'cutaway to money-counting b-roll' are NOT — one is a UI demo and one is
  mood footage, and they do different work even though both are cutaways.

- DO NOT MERGE TO TIDY. Two moves that genuinely differ stay separate even if
  the names are similar. A vocabulary of 6 families that hid the distinctions is
  worse than 15 that kept them — the whole point of this pass is to find
  families that a six-value enum could not express.

- A SINGLETON IS A REAL AND USEFUL ANSWER. A move one editor used once is an
  observation, not a family, and saying so is the finding. Do not force it into
  a family to reduce the singleton count.

- `what_it_does` is REQUIRED on every family. A family that cannot say what it
  does is a label, not a finding.

OBSERVATIONS:
"""


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "/tmp/refcorpus_open"
    obs, per_video, skipped = {}, {}, []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".mp4.json"):
            continue
        r = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        if r.get("state") != "MEASURED":
            skipped.append((r.get("video", fn), r.get("state")))
            continue
        vid = r["video"]
        for b in (r.get("record") or {}).get("beats") or []:
            for t in (b.get("treatment") or []):
                nm = (t.get("name") or "").strip()
                if not nm:
                    continue
                obs.setdefault(nm, {"what": t.get("what_it_does", ""),
                                    "videos": set()})
                obs[nm]["videos"].add(vid)
                per_video.setdefault(vid, set()).add(nm)
    if skipped:
        print("  NOT MEASURED, excluded from clustering:")
        for v, st in skipped:
            print(f"    {st}: {v}")
        print("  *** the vocabulary below is PARTIAL — it does not cover the "
              "corpus and the video-counts are out of a smaller denominator")
        return 2
    n_videos = len(per_video)
    print(f"  {len(obs)} distinct observation name(s) across {n_videos} video(s)")

    lines = []
    for nm in sorted(obs):
        lines.append(f"- {nm}  [seen in {len(obs[nm]['videos'])} video(s)]  "
                     f"-> {obs[nm]['what'][:160]}")
    # THINKING IS BOUNDED, BECAUSE IT ATE THE WHOLE BUDGET TWICE.
    # max_tokens covers thinking AND the answer. Left unbounded this returned a
    # single content block of type "thinking" at exactly 32,000 and then exactly
    # 64,000 tokens — reasoning that never reached the reply, twice, for $1.52.
    # An unbounded budget on a 173-item clustering is not "more careful", it is
    # a run with no output. Bound the thinking, leave the rest for the answer,
    # and the cap check above now distinguishes truncation from malformation.
    req_body = {
        "model": MODEL, "max_tokens": MAX_TOKENS,
        # THE MODEL NAMED ITS OWN CONTROL. "thinking.type.enabled" is refused
        # by claude-sonnet-5 with: use "thinking.type.adaptive" and
        # "output_config.effort". Effort LOW, because this task's rules are
        # explicit and the failure mode was reasoning that never landed.
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": EFFORT},
        "messages": [{"role": "user",
                      "content": PROMPT + "\n".join(lines)}],
    }
    body = json.dumps(req_body).encode()

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        for line in open(os.path.expanduser("~/content-studio/.env.local")):
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        print("  no ANTHROPIC_API_KEY — UNMEASURED")
        return 2
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} — {e.read().decode(errors='replace')[:400]}")
        return 2
    u = resp.get("usage", {})
    out_tok = u.get("output_tokens", 0)
    print(f"  MEASURED   in={u.get('input_tokens',0):,} out={out_tok:,}  "
          f"${u.get('input_tokens',0)/1e6*3 + out_tok/1e6*15:.3f}")
    # SAVE THE WHOLE RESPONSE, NOT THE PART I EXPECTED TO FIND.
    # First version wrote only the concatenated `type=="text"` blocks — and on a
    # truncated reply that produced an EMPTY file beside out=32,000, so a call
    # that was already PAID FOR left no evidence of what it actually returned
    # and the shape could not be diagnosed without buying it again.
    # build_reference_records.py learned this on 2026-08-29 and says so in a
    # comment; I reimplemented the same script without carrying the protection
    # across. The response is the evidence — keep all of it, before parsing.
    json.dump(resp, open(os.path.join(d, "clusters.response.json"), "w"),
              ensure_ascii=False, indent=1)
    blocks = resp.get("content") or []
    txt = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
    if not txt:
        print(f"  NO TEXT in {len(blocks)} content block(s) — types: "
              f"{[b.get('type') for b in blocks if isinstance(b, dict)]}. "
              f"Full response kept at clusters.response.json")
    open(os.path.join(d, "clusters.raw.txt"), "w").write(txt)
    # THE CAP IS CHECKED BEFORE ANY PARSE, NOT INSIDE ONE BRANCH OF IT.
    # First version put this check only in the JSONDecodeError handler — but a
    # response truncated before its closing brace never REACHES that handler:
    # the `{...}` regex simply fails and it exits at "no JSON in response",
    # which names the wrong cause. Two exits, one check, and the check was in
    # the other one. Exactly the defect just fixed in build_reference_records,
    # reintroduced two files later by putting the guard where the first failure
    # happened to land rather than where the condition is true.
    if out_tok >= MAX_TOKENS:
        print(f"  OUTPUT CAP HIT: out={out_tok:,} == max_tokens={MAX_TOKENS:,}. "
              f"The response was TRUNCATED — this is a FAILED measurement, not "
              f"a malformed one. If the only content block is `thinking`, the "
              f"budget was spent reasoning and never reached the answer — lower "
              f"CLUSTER_EFFORT rather than only raising the cap. Raw kept "
              f"at {os.path.join(d, 'clusters.raw.txt')}")
        return 1
    m = re.search(r"\{[\s\S]*\}", txt)
    if not m:
        print(f"  no JSON in response (out={out_tok:,}, under the "
              f"{MAX_TOKENS:,} cap, so this is genuinely malformed)")
        return 1
    try:
        cl = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        if out_tok >= MAX_TOKENS:
            print(f"  OUTPUT CAP HIT: out={out_tok:,} == {MAX_TOKENS:,} — "
                  f"TRUNCATED, not malformed. Raise CLUSTER_MAX_TOKENS.")
        print(f"  JSON PARSE FAILED ({e}) — raw kept")
        return 1

    # EVERY OBSERVATION ACCOUNTED FOR, checked mechanically.
    placed = []
    for f in cl.get("families") or []:
        placed.extend(f.get("members") or [])
    placed.extend(cl.get("singletons") or [])
    lost = sorted(set(obs) - set(placed))
    invented = sorted(set(placed) - set(obs))
    dupes = sorted({x for x in placed if placed.count(x) > 1})
    if lost or invented or dupes:
        print(f"  *** CLUSTERING IS NOT A PARTITION — "
              f"{len(lost)} dropped, {len(invented)} invented, "
              f"{len(dupes)} in two families")
        for x in lost[:8]:
            print(f"      DROPPED  {x!r}")
        for x in invented[:8]:
            print(f"      INVENTED {x!r}")
        for x in dupes[:8]:
            print(f"      TWICE    {x!r}")
        return 1

    # THE DISCOVERY STATISTIC: how many of the ten videos each family spans.
    fams = []
    for f in cl.get("families") or []:
        vids = set()
        for mname in f.get("members") or []:
            vids |= obs[mname]["videos"]
        fams.append({**f, "videos": len(vids), "n_members": len(f.get("members") or []),
                     "video_list": sorted(vids)})
    fams.sort(key=lambda x: (-x["videos"], -x["n_members"]))
    doc = {"n_videos": n_videos, "n_observations": len(obs),
           "families": fams, "singletons": sorted(cl.get("singletons") or [])}
    outp = os.path.join(d, "vocabulary.json")
    json.dump(doc, open(outp, "w"), ensure_ascii=False, indent=1)

    print(f"\n  {len(fams)} FAMILIES, {len(doc['singletons'])} singleton(s), "
          f"partition verified over {len(obs)} observations\n")
    print(f"  {'videos':>7}  {'obs':>4}  family")
    for f in fams:
        mark = "  <-- in 8+ of 10" if f["videos"] >= 8 else ""
        print(f"  {f['videos']:>4}/{n_videos}  {f['n_members']:>4}  "
              f"{f['family']}{mark}")
        print(f"            {f['what_it_does'][:110]}")
    print(f"\n  written {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
