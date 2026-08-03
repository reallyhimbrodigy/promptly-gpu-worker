"""OVER-FIRING AUDIT — when a component fires, does the MOMENT match its FITS?

Zac's standard: components go WHERE THEY FIT, never on a cadence. "Each and
every component should earn its place." Under-firing (unreachable) and
over-firing (a FITS rule too loose) are the same defect inverted, and only the
second one is what spam looks like. The second has never been measured.

WHAT THIS DOES
  For every placement in a stored plan, pull the DIALOGUE AROUND ITS WORD INDEX
  from the persisted transcript and test whether that dialogue actually carries
  the trigger the component's own Claim/FITS names. StatCard says "can you quote
  the dialogue line where the speaker says THAT number?" — so check whether the
  number is there. Notification says the trigger is "an action VERB on the
  timeline: called, texted, paid, pinged, buzzed" — so check for one.

WHAT THIS IS NOT
  It is NOT the blind judge pass. A mechanical trigger test can prove the
  DIALOGUE EVIDENCE IS ABSENT — which is a hard miss, the component fired with
  nothing to point at. It CANNOT prove a placement is tasteful when the trigger
  IS present. So:
      trigger absent -> strong evidence of over-firing
      trigger present -> NOT a pass, only "not disproved"
  Components whose fit is genuinely a taste call (PillCluster's "sibling
  keywords", sticky_note's "three parallel items of equal weight") are listed as
  JUDGE-ONLY rather than scored, because scoring them mechanically would invent
  a number.

CPU-only DB read. ~$0.01.
"""
import os
import re
from collections import defaultdict

import modal

app = modal.App("query-fit-audit")
image = modal.Image.debian_slim().pip_install("supabase")
SECRETS = [modal.Secret.from_name("promptly-secrets")]

# Trigger = what the component's OWN Claim/FITS says the dialogue must contain.
TRIGGERS = {
    "StatCard":         r"\d",
    "ProgressBar":      r"\d",
    "BarRace":          r"\d",
    "RankedList":       r"\b(number one|number two|first|second|third|top \d|one of|reasons?)\b",
    "Notification":     r"\b(called|texted|paid|pinged|buzzed|sent|notification|venmo|message)\b",
    "IMessageBubble":   r"\b(text|texted|texting|message|messaged|said|wrote|dm)\b",
    "ChatThread":       r"\b(text|texted|message|messaged|said|replied|conversation)\b",
    "TweetBubble":      r"\b(tweet|tweeted|twitter|posted|x\.com)\b",
    "InstagramComment": r"\b(instagram|insta|ig|comment|commented|post)\b",
    "TikTokComment":    r"\b(tiktok|tik tok|fyp|comment|commented)\b",
    "Stamp":            r"\b(verified|certified|official|officially|authentic|approved|guaranteed|brand new)\b",
    "MouseDrag":        r"\b(drag|drop|dropped|move it|drag and drop)\b",
    "RecordingFrame":   r"\b(raw|bts|behind the scenes|leaked|unfiltered|caught|recording)\b",
    "AnnotationArrow":  r"\b(this|here|look|see|right there|notice)\b",
    "Reticle":          r"\b(this|here|look|see|right there|button|click)\b",
    "PullQuote":        None,     # checked by text-matches-transcript instead
    "EditorialQuote":   None,
}
JUDGE_ONLY = {"PillCluster", "PillMarquee", "StickyNotes", "SectionDivider",
              "StepDivider", "Timeline", "TimelineRoadmap", "DropBanner", "DropCard"}
SFX_TRIGGERS = {
    "money-ching":   r"\b(money|dollar|paid|cash|revenue|profit|\$|sold|price)\b",
    "iphoneding":    r"\b(text|message|notification|ding|dm|email)\b",
    "wompwomp":      r"\b(fail|failed|flop|flopped|nothing|zero|nope|didn't work)\b",
    "imposter":      r"\b(suspicious|something felt|off|weird|shady|sus|turns out)\b",
    "rizz":          r"\b(number|charm|smooth|flirt|date|cute)\b",
    "awkward-moment": r"\b(awkward|cringe|silence|weird|embarrass)\b",
    "camera-flash":  r"\b(photo|picture|shot|camera|snap|reveal)\b",
}
WINDOW = 12   # words either side of the anchor


@app.function(image=image, secrets=SECRETS, timeout=900)
def query(hours: int = 336) -> dict:
    from datetime import datetime, timedelta, timezone
    from supabase import create_client
    sb = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY"))
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    _diag = {"result_keys": {}, "transcript_type": {}, "transcript_sample": None,
             "n_result": 0, "n_recipe": 0, "dict_keys": {}, "dict_shape": None}
    hit = defaultdict(int)
    miss = defaultdict(int)
    examples = defaultdict(list)
    n_plans = 0

    def words_of(tr):
        """The persisted transcript is a DICT on most rows (446) and an empty
        list on others (421) — my first pass assumed a list of words and scored
        ZERO plans as a result. Handle both, and record the dict's keys so a
        miss teaches the shape instead of just failing."""
        if isinstance(tr, list):
            return [str(w.get("text") or w.get("word") or "") if isinstance(w, dict) else str(w)
                    for w in tr]
        if isinstance(tr, dict):
            for k in tr.keys():
                _diag["dict_keys"][k] = _diag["dict_keys"].get(k, 0) + 1
            for key in ("words", "word_list", "tokens", "segments", "transcript", "items"):
                v = tr.get(key)
                if isinstance(v, list) and v:
                    if _diag["dict_shape"] is None:
                        _diag["dict_shape"] = f"{key}: {str(v[:2])[:220]}"
                    return [str(x.get("text") or x.get("word") or "") if isinstance(x, dict)
                            else str(x) for x in v]
            for k, v in tr.items():            # any list-of-things value
                if isinstance(v, list) and v:
                    if _diag["dict_shape"] is None:
                        _diag["dict_shape"] = f"{k}: {str(v[:2])[:220]}"
                    return [str(x.get("text") or x.get("word") or "") if isinstance(x, dict)
                            else str(x) for x in v]
        return []

    for off in range(0, 20000, 1000):
        try:
            r = (sb.table("video_jobs").select("result")
                 .gte("created_at", since).range(off, off + 999).execute())
        except Exception as e:  # noqa: BLE001
            print(f"[query] {off}: {e}", flush=True)
            break
        rows = r.data or []
        if not rows:
            break
        for row in rows:
            res = row.get("result")
            if not isinstance(res, dict):
                continue
            _diag["n_result"] += 1
            if _diag["n_result"] <= 400:
                for k in res.keys():
                    _diag["result_keys"][k] = _diag["result_keys"].get(k, 0) + 1
            rec = res.get("edit_recipe")
            if isinstance(rec, dict):
                _diag["n_recipe"] += 1
            _tr = res.get("transcript")
            _tt = type(_tr).__name__ + (f"[{len(_tr)}]" if isinstance(_tr, (list, str)) else "")
            _diag["transcript_type"][_tt] = _diag["transcript_type"].get(_tt, 0) + 1
            if _diag["transcript_sample"] is None and isinstance(_tr, list) and _tr:
                _diag["transcript_sample"] = str(_tr[:2])[:300]
            w = words_of(_tr)
            if not isinstance(rec, dict) or not w:
                continue
            n_plans += 1

            def ctx(idx):
                if not isinstance(idx, (int, float)):
                    return None
                i = int(idx)
                return " ".join(w[max(0, i - WINDOW): i + WINDOW]).lower()

            def score(name, idx, pat, text_probe=None):
                c = ctx(idx)
                if c is None:
                    return
                ok = bool(re.search(pat, c)) if pat else (
                    bool(text_probe) and any(t in c for t in text_probe.lower().split()[:4]))
                (hit if ok else miss)[name] += 1
                if not ok and len(examples[name]) < 3:
                    examples[name].append(c[:150])

            mgs = list(rec.get("motion_graphics") or [])
            for em in (rec.get("emphasis_moments") or []):
                if isinstance(em, dict) and isinstance(em.get("motion_graphic"), dict):
                    g = dict(em["motion_graphic"])
                    g.setdefault("start_word_index", em.get("word_index"))
                    mgs.append(g)
            for g in mgs:
                if not isinstance(g, dict):
                    continue
                t = g.get("type")
                if t in JUDGE_ONLY or t not in TRIGGERS:
                    continue
                idx = g.get("start_word_index", g.get("word_index"))
                pr = g.get("props") or {}
                score(t, idx, TRIGGERS[t], pr.get("text"))
            for s in (rec.get("sound_effects") or []):
                if isinstance(s, dict) and s.get("sound") in SFX_TRIGGERS:
                    score(f"sfx:{s['sound']}", s.get("word_index"),
                          SFX_TRIGGERS[s["sound"]])
            for em in (rec.get("emphasis_moments") or []):
                if isinstance(em, dict) and em.get("sound") in SFX_TRIGGERS:
                    score(f"sfx:{em['sound']}", em.get("word_index"),
                          SFX_TRIGGERS[em["sound"]])
    return {"n_plans": n_plans, "hit": dict(hit), "miss": dict(miss),
            "examples": {k: v for k, v in examples.items()},
            "diag": _diag}


@app.local_entrypoint()
def main(hours: int = 336):
    d = query.remote(hours)
    print(f"\nFIT AUDIT — {d['n_plans']:,} plans with a persisted transcript, last {hours}h\n")
    names = sorted(set(d["hit"]) | set(d["miss"]))
    if not names:
        print("  no scorable placements found")
        dg = d.get("diag") or {}
        print(f"\n  DIAGNOSTIC: {dg.get('n_result',0)} results, {dg.get('n_recipe',0)} with edit_recipe")
        print(f"  transcript types seen: {dg.get('transcript_type')}")
        print(f"  transcript sample: {dg.get('transcript_sample')}")
        print(f"  transcript DICT keys: {sorted((dg.get('dict_keys') or {}).items(), key=lambda kv:-kv[1])[:12]}")
        print(f"  dict shape: {dg.get('dict_shape')}")
        return
    print(f"  {'component':<22} {'fires':>6} {'trigger in':>11} {'trigger':>9} {'MISS':>7}")
    print(f"  {'':<22} {'':>6} {'dialogue':>11} {'absent':>9} {'rate':>7}")
    print("  " + "-" * 62)
    tot_h = tot_m = 0
    for nm in sorted(names, key=lambda n: -(d["hit"].get(n, 0) + d["miss"].get(n, 0))):
        h, m = d["hit"].get(nm, 0), d["miss"].get(nm, 0)
        tot_h += h
        tot_m += m
        rate = 100.0 * m / max(1, h + m)
        flag = "  <-- OVER-FIRING" if rate >= 50 and (h + m) >= 5 else ""
        print(f"  {nm:<22} {h+m:>6} {h:>11} {m:>9} {rate:>6.0f}%{flag}")
    print("  " + "-" * 62)
    print(f"  {'ALL SCORED':<22} {tot_h+tot_m:>6} {tot_h:>11} {tot_m:>9} "
          f"{100.0*tot_m/max(1,tot_h+tot_m):>6.0f}%")
    print(f"\n  JUDGE-ONLY (fit is a taste call; scoring mechanically would invent a number):")
    print(f"    {', '.join(sorted(JUDGE_ONLY))}")
    print("\n  READ: trigger ABSENT is strong evidence the component fired with no")
    print("  dialogue evidence to point at. Trigger PRESENT is NOT a pass — only")
    print("  'not disproved'. This is a floor on over-firing, not a fit score.")
    for nm, ex in sorted(d["examples"].items()):
        if ex:
            print(f"\n  {nm} — dialogue where the trigger was ABSENT:")
            for e in ex:
                print(f"    …{e}…")
