#!/usr/bin/env python3
"""Merge the SILENT and LISTENING readings, keeping both. Never collapse.

Zac, 2026-09-11: "Neither is a superset and collapsing them throws away
whichever half the winner is weaker at. Carry both with their provenance, the
way treat_raw sits beside treat — and let a family that appears in both arms be
stronger evidence than one that appears in either."

THE CONFOUND CUTS BOTH WAYS AND THAT IS WHY BOTH ARE KEPT:

    arm       reader                    names  craft  audible names  videos
    silent    claude-sonnet-5, frames     173     70              1     1/10
    heard     gemini-2.5-pro, clip+audio  136     46             25    10/10

Claude sees better — 173 names to 136, 70 craft notes to 46, and it writes
"Giant kinetic title-card slam" where Gemini writes "Text overlay". Gemini hears
at all. An L-cut — audio carrying across a picture cut — is not under-sampled in
the silent arm, it is UNSAYABLE there.

WHY A THIRD MODEL PASS AND NOT A STRING MATCH. The arms name the same move
differently ("Screen-recording UI demo cutaway" / "Screen Recording Product
Demo"). Matching on words would merge those two and miss them at the same time.
This pass sees only the two family lists — never the videos — so it cannot
re-decide what either arm observed, only which of their names are the same move.

PARTITION, ENFORCED. Every family from BOTH arms lands in exactly one merged
entry. A dropped or invented name fails the pass, because a merge that quietly
loses a family reports a smaller vocabulary than the two arms found — the same
failure as a clustering that loses observations, one level up.

    python3 merge_reference_arms.py /tmp/refcorpus_open /tmp/refcorpus_listen_c
"""
import json
import os
import re
import sys
import urllib.request

MODEL = "claude-sonnet-5"
MAX_TOKENS = int(os.environ.get("MERGE_MAX_TOKENS", "32000"))
EFFORT = os.environ.get("MERGE_EFFORT", "low")

PROMPT = """Two independent readings of the SAME ten videos produced two family vocabularies.

Reading A saw SILENT FRAMES (stills, no audio).
Reading B saw the CLIP WITH AUDIO.

They are different readers, so they name the same move differently, and each can
see things the other cannot: A describes visual craft in more detail, B is the
only one that can hear.

Your job is to say which families in A and B are THE SAME MOVE.

Return JSON only:

{
  "merged": [
    {
      "family": "<the clearest name for this move — you may take either arm's name or write a better one>",
      "what_it_does": "<one sentence>",
      "a_members": ["<verbatim family names from reading A, may be empty>"],
      "b_members": ["<verbatim family names from reading B, may be empty>"]
    }
  ]
}

RULES:

- EVERY family name from BOTH lists must appear exactly once across all
  `a_members` and `b_members`. Do not drop, invent, or double-place one. This is
  checked mechanically and a mismatch fails the pass.

- A family seen by only ONE arm is a REAL AND EXPECTED ANSWER — give it an entry
  with the other arm's list empty. Every audible family will be B-only, because
  A could not hear. Several fine visual distinctions will be A-only, because B
  names more coarsely. Do NOT force a match to make the lists line up.

- MATCH ON WHAT IT DOES, not on wording. "Screen-recording UI demo cutaway" and
  "Screen Recording Product Demo" are the same move. "Cutaway to Grounding
  B-roll" and "Screen Recording Product Demo" are NOT — one is atmospheric
  footage and one is a UI demo, and they do different work.

- DO NOT MERGE TO TIDY. If A drew a distinction B did not, keep A's two entries
  separate and attach B's single family to whichever it actually matches, or to
  neither.

READING A FAMILIES (silent, frames):
{A}

READING B FAMILIES (heard, clip+audio):
{B}
"""


def load(d):
    v = json.load(open(os.path.join(d, "vocabulary.json"), encoding="utf-8"))
    fam = {f["family"]: f for f in v.get("families") or []}
    for s in v.get("singletons") or []:
        fam[s] = {"family": s, "videos": 1, "n_members": 1,
                  "what_it_does": "(singleton — one editor, once)",
                  "video_list": []}
    return v, fam


def main():
    da = sys.argv[1] if len(sys.argv) > 1 else "/tmp/refcorpus_open"
    db = sys.argv[2] if len(sys.argv) > 2 else "/tmp/refcorpus_listen_c"
    va, fa = load(da)
    vb, fb = load(db)
    print(f"  A silent : {len(fa)} families+singletons over {va['n_videos']} videos")
    print(f"  B heard  : {len(fb)} families+singletons over {vb['n_videos']} videos")

    def block(fam):
        return "\n".join(
            f"- {k}  [{v.get('videos', 0)} video(s)]  -> "
            f"{(v.get('what_it_does') or '')[:130]}" for k, v in sorted(fam.items()))

    body = json.dumps({
        "model": MODEL, "max_tokens": MAX_TOKENS,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": EFFORT},
        "messages": [{"role": "user", "content":
                      PROMPT.replace("{A}", block(fa)).replace("{B}", block(fb))}],
    }).encode()
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
        with urllib.request.urlopen(req, timeout=900) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} — {e.read().decode(errors='replace')[:400]}")
        return 2
    json.dump(resp, open("/tmp/merge.response.json", "w"), ensure_ascii=False)
    u = resp.get("usage", {})
    out_tok = u.get("output_tokens", 0)
    print(f"  MEASURED   in={u.get('input_tokens',0):,} out={out_tok:,}  "
          f"${u.get('input_tokens',0)/1e6*3 + out_tok/1e6*15:.3f}")
    # CAP CHECKED BEFORE THE PARSE, not inside one branch of it.
    txt = "".join(b.get("text", "") for b in (resp.get("content") or [])
                  if isinstance(b, dict))
    if out_tok >= MAX_TOKENS:
        print(f"  OUTPUT CAP HIT out={out_tok:,} — TRUNCATED, not malformed")
        return 1
    if not txt:
        print(f"  NO TEXT — block types: "
              f"{[b.get('type') for b in (resp.get('content') or [])]}")
        return 1
    m = re.search(r"\{[\s\S]*\}", txt)
    if not m:
        print("  no JSON in response")
        return 1
    merged = json.loads(m.group(0)).get("merged") or []

    pa = [x for e in merged for x in (e.get("a_members") or [])]
    pb = [x for e in merged for x in (e.get("b_members") or [])]
    for nm, placed, src in (("A", pa, fa), ("B", pb, fb)):
        lost = sorted(set(src) - set(placed))
        inv = sorted(set(placed) - set(src))
        dup = sorted({x for x in placed if placed.count(x) > 1})
        if lost or inv or dup:
            print(f"  *** arm {nm} is not a partition: {len(lost)} dropped, "
                  f"{len(inv)} invented, {len(dup)} twice")
            for x in (lost[:6] + inv[:6] + dup[:6]):
                print(f"      {x!r}")
            return 1

    rows = []
    for e in merged:
        am, bm = e.get("a_members") or [], e.get("b_members") or []
        va_ = max([fa[x].get("videos", 0) for x in am], default=0)
        vb_ = max([fb[x].get("videos", 0) for x in bm], default=0)
        arms = ("both" if am and bm else ("silent" if am else "heard"))
        rows.append({
            "family": e.get("family"), "what_it_does": e.get("what_it_does"),
            "arms": arms,
            # BOTH ARMS IS STRONGER EVIDENCE. Two independent readers, different
            # models and different modalities, landing on the same move.
            "evidence": "CORROBORATED" if arms == "both" else "single-arm",
            "videos_silent": va_, "videos_heard": vb_,
            "videos_max": max(va_, vb_),
            "silent_names": am, "heard_names": bm,
        })
    rows.sort(key=lambda r: (r["arms"] != "both", -r["videos_max"]))
    doc = {"n_videos": va["n_videos"],
           "arm_a": {"dir": os.path.abspath(da), "reader": "claude-sonnet-5, silent frames"},
           "arm_b": {"dir": os.path.abspath(db), "reader": "gemini-2.5-pro, clip with audio"},
           "families": rows}
    outp = "reference_vocabulary_merged.json"
    json.dump(doc, open(outp, "w"), ensure_ascii=False, indent=1)

    nb = sum(1 for r in rows if r["arms"] == "both")
    print(f"\n  {len(rows)} merged famil(ies): {nb} CORROBORATED, "
          f"{sum(1 for r in rows if r['arms']=='silent')} silent-only, "
          f"{sum(1 for r in rows if r['arms']=='heard')} heard-only")
    print(f"  partition verified over {len(fa)} A + {len(fb)} B names\n")
    print(f"  {'evidence':13} {'sil':>4} {'heard':>5}  family")
    for r in rows:
        if r["videos_max"] >= 3 or r["arms"] == "both":
            print(f"  {r['evidence']:13} {r['videos_silent']:>3}/10 "
                  f"{r['videos_heard']:>3}/10  {r['family'][:52]}")
    print(f"\n  written {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
