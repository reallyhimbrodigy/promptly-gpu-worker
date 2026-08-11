#!/usr/bin/env python3
"""
golden/build_manifest.py — construct the golden corpus manifest (LANE 2).

Local + zero Modal spend: Supabase reads, S3 head-objects, streaming sha256.

Selection rules (LANE 2 brief + recon):
  * REAL completed jobs only, from video_jobs (status=completed).
  * Route quota: standard editorial ~12 (Hindi-majority), moodreel ~5,
    minimal+minimal_speech_uncut ~5, hype ~3 (only 9 exist in traffic — take
    what's reachable). Premium/lumen: ZERO real jobs exist [MEASURED] — flagged
    in the manifest as unsourceable, NOT substituted with synthetic.
  * Language from docs/asr_scribe_cohort2_results.json (id[:8] join) — the
    only bulk language source that works; light routes carry no transcript.
  * Hard cases tagged from DB truth: burned-in captions
    (edit_recipe plan.existing_caption_region != "none"), multi-speaker
    (>=2 distinct transcript speaker tags), near-silent (route_reason
    no_speech*/too_short).
  * Exclusions: demo rows, e2e-/test-/smoke- ids, owner uploads
    (sources/ec702499-.../), duplicate S3 keys, dur outside [5,120]s,
    objects > 250 MB (spend control).
  * Every pick verified with aws s3api head-object; sha256 computed by
    streaming `aws s3 cp - | shasum` (no bytes stored in git).

Usage:
  python3 golden/build_manifest.py            # build + verify, write manifest
  python3 golden/build_manifest.py --no-hash  # skip sha256 pass (fast dry run)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENV_LOCAL = "/Users/zaclibman/content-studio/.env.local"
COHORT2 = os.path.join(ROOT, "docs", "asr_scribe_cohort2_results.json")
BUCKET = "thisismybucketagainwooo"
CF_HOST = "d1iax8jos987n3.cloudfront.net"
OWNER_USER = "ec702499-ca10-49e6-8850-df8f99840904"

QUOTA = {"editorial": 12, "moodreel": 5, "minimal": 3,
         "minimal_speech_uncut": 2, "hype": 3}
# Hindi-majority-relevant: 62% of transcripted traffic is Hindi.
EDITORIAL_LANG_QUOTA = [("hin", 6), ("eng", 3), ("por", 1), ("spa", 1),
                        ("*", 1)]
MAX_BYTES = 250 * 1024 * 1024
DUR_RANGE = (5.0, 120.0)


def env_creds():
    url = key = None
    with open(ENV_LOCAL) as f:
        for line in f:
            if line.startswith("SUPABASE_URL="):
                url = line.split("=", 1)[1].strip()
            elif line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
                key = line.split("=", 1)[1].strip()
    assert url and key, "Supabase creds not found in .env.local"
    return url, key


def sb_get(url, key, path):
    req = urllib.request.Request(url + path, headers={
        "apikey": key, "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_jobs(url, key):
    rows = []
    for page in range(6):
        sel = ("id,created_at,video_url,vibe_input,user_id,demo,"
               "route:result->route,reason:result->route_reason,"
               "dur:result->stage_timings->source_duration_s")
        batch = sb_get(url, key,
                       "/rest/v1/video_jobs?select=%s&status=eq.completed"
                       "&order=created_at.desc&limit=1000&offset=%d"
                       % (sel, page * 1000))
        rows.extend(batch)
        if len(batch) < 1000:
            break
    return rows


def fetch_detail(url, key, job_id):
    sel = "id,edit_recipe,tw:result->transcript->words"
    rows = sb_get(url, key,
                  "/rest/v1/video_jobs?select=%s&id=eq.%s" % (sel, job_id))
    return rows[0] if rows else {}


def s3_key_of(video_url):
    m = re.match(r"https?://%s/(.+)$" % re.escape(CF_HOST), video_url or "")
    return m.group(1) if m else None


def head_object(key):
    r = subprocess.run(["aws", "s3api", "head-object", "--bucket", BUCKET,
                        "--key", key], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    d = json.loads(r.stdout)
    return {"bytes": d["ContentLength"], "etag": d["ETag"].strip('"'),
            "last_modified": d["LastModified"]}


def sha256_stream(key):
    p1 = subprocess.Popen(["aws", "s3", "cp",
                           "s3://%s/%s" % (BUCKET, key), "-"],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p2 = subprocess.run(["shasum", "-a", "256"], stdin=p1.stdout,
                        capture_output=True, text=True)
    p1.stdout.close()
    p1.wait()
    if p1.returncode != 0 or p2.returncode != 0:
        return None
    return p2.stdout.split()[0]


def plan_of_recipe(recipe):
    if not isinstance(recipe, dict):
        return {}
    return recipe.get("plan") if isinstance(recipe.get("plan"), dict) else recipe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-hash", action="store_true")
    args = ap.parse_args()
    url, key = env_creds()

    cohort = json.load(open(COHORT2))
    lang_by_prefix = {k: (v.get("scribe") or {}).get("lang")
                      for k, v in cohort.items()}

    rows = fetch_jobs(url, key)
    print("pulled %d completed jobs" % len(rows))

    seen_keys = set()
    pool = {r: [] for r in QUOTA}
    for row in rows:
        jid = str(row.get("id") or "")
        if jid.startswith(("e2e-", "test-", "smoke-")) or row.get("demo"):
            continue
        vurl = row.get("video_url") or ""
        s3k = s3_key_of(vurl)
        if not s3k or ("sources/%s/" % OWNER_USER) in vurl:
            continue
        if s3k in seen_keys:
            continue
        dur = row.get("dur")
        try:
            dur = float(dur) if dur is not None else None
        except (TypeError, ValueError):
            dur = None
        route = row.get("route") or "editorial"
        if route not in pool:
            continue
        # editorial rows must have a sane duration; light routes may miss it
        if dur is not None and not (DUR_RANGE[0] <= dur <= DUR_RANGE[1]):
            continue
        if route == "editorial" and dur is None:
            continue
        seen_keys.add(s3k)
        pool[route].append({
            "job_id": jid, "video_url": vurl, "s3_key": s3k,
            "vibe": (row.get("vibe_input") or "").strip(),
            "route": route, "reason": row.get("reason"),
            "duration_s": dur, "created_at": row.get("created_at"),
            "lang": lang_by_prefix.get(jid[:8]),
        })

    for r, lst in pool.items():
        langs = {}
        for c in lst:
            langs[c.get("lang")] = langs.get(c.get("lang"), 0) + 1
        print("pool %-22s %4d  langs=%s" % (r, len(lst), dict(
            sorted(langs.items(), key=lambda kv: -kv[1])[:6])))

    picks = []

    # --- editorial: language-stratified + hard-case tagging ----------------
    ed = pool["editorial"]
    ed_labeled = [c for c in ed if c["lang"]]
    ed_by_lang = {}
    for c in sorted(ed_labeled, key=lambda c: c["created_at"], reverse=True):
        ed_by_lang.setdefault(c["lang"], []).append(c)

    ed_picked = []
    for lang, want in EDITORIAL_LANG_QUOTA:
        cands = (sum((v for k, v in sorted(ed_by_lang.items())
                      if k not in [l for l, _ in EDITORIAL_LANG_QUOTA[:-1]]), [])
                 if lang == "*" else ed_by_lang.get(lang, []))
        cands = [c for c in cands if c not in ed_picked]
        # prefer 8-90s, mid-size handled later at head-object time
        cands.sort(key=lambda c: (abs((c["duration_s"] or 30) - 25)))
        take = cands[:want]
        if len(take) < want:
            print("  !! editorial lang %r: wanted %d, only %d available"
                  % (lang, want, len(take)))
        ed_picked.extend(take)

    # hard-case pass: fetch details for picked + a reserve, tag burned
    # captions and multi-speaker; swap reserves in if the picks lack them.
    reserve = [c for c in ed_labeled if c not in ed_picked][:25]
    def tag(c):
        det = fetch_detail(url, key, c["job_id"])
        plan = plan_of_recipe(det.get("edit_recipe"))
        c["burned_captions"] = (plan.get("existing_caption_region", "none")
                                not in ("none", None))
        words = det.get("tw") or []
        speakers = {w.get("speaker") for w in words
                    if isinstance(w, dict) and w.get("speaker") is not None}
        c["multi_speaker"] = len(speakers) >= 2
        return c

    for c in ed_picked:
        tag(c)
    have_burn = any(c["burned_captions"] for c in ed_picked)
    have_multi = any(c["multi_speaker"] for c in ed_picked)
    for c in reserve:
        if have_burn and have_multi:
            break
        tag(c)
        if not have_burn and c["burned_captions"]:
            ed_picked[-1] = c
            have_burn = True
        elif not have_multi and c["multi_speaker"]:
            ed_picked[-2 if have_burn else -1] = c
            have_multi = True
    # transcript-derived extras: cohort2 misses recent jobs; per-word language
    # tags on route-null rows are the fallback [CODE handler.py:4353].
    ISO1TO3 = {"hi": "hin", "en": "eng", "pt": "por", "es": "spa",
               "fr": "fra", "ru": "rus", "bn": "ben", "ta": "tam"}
    sel = ("id,video_url,vibe_input,created_at,"
           "tw:result->transcript->words,"
           "dur:result->stage_timings->source_duration_s")
    recent = sb_get(url, key,
                    "/rest/v1/video_jobs?select=%s&status=eq.completed"
                    "&result->>route=is.null&order=created_at.desc&limit=300"
                    % sel)
    picked_keys = {c["s3_key"] for c in ed_picked}
    extras = []
    for row in recent:
        words = row.get("tw") or []
        if not words:
            continue
        s3k = s3_key_of(row.get("video_url") or "")
        dur = row.get("dur")
        try:
            dur = float(dur) if dur is not None else None
        except (TypeError, ValueError):
            dur = None
        if (not s3k or s3k in picked_keys or dur is None
                or not (DUR_RANGE[0] <= dur <= DUR_RANGE[1])):
            continue
        langs = {}
        speakers = set()
        for w in words:
            if not isinstance(w, dict):
                continue
            if w.get("language"):
                langs[w["language"]] = langs.get(w["language"], 0) + 1
            if w.get("speaker") is not None:
                speakers.add(w.get("speaker"))
        maj = max(langs, key=langs.get) if langs else None
        extras.append({
            "job_id": str(row["id"]), "video_url": row["video_url"],
            "s3_key": s3k, "vibe": (row.get("vibe_input") or "").strip(),
            "route": "editorial", "reason": None, "duration_s": dur,
            "created_at": row.get("created_at"),
            "lang": ISO1TO3.get(maj, maj),
            "multi_speaker": len(speakers) >= 2,
            "burned_captions": False,
            "lang_source": "transcript_words_majority",
        })

    if not have_multi:
        ms = [c for c in extras if c["multi_speaker"]]
        if ms:
            pick = ms[0]
            same_lang = [c for c in ed_picked
                         if c["lang"] == pick["lang"] and
                         not c.get("burned_captions")]
            if same_lang:
                ed_picked[ed_picked.index(same_lang[-1])] = pick
            else:
                ed_picked.append(pick)
            picked_keys.add(pick["s3_key"])
            have_multi = True

    if len(ed_picked) < QUOTA["editorial"]:
        picked_langs = {c["lang"] for c in ed_picked}
        fillers = sorted(
            (c for c in extras
             if c["s3_key"] not in picked_keys and not c["multi_speaker"]),
            key=lambda c: (c["lang"] in picked_langs,
                           abs((c["duration_s"] or 30) - 25)))
        for c in fillers[:QUOTA["editorial"] - len(ed_picked)]:
            ed_picked.append(c)
            picked_keys.add(c["s3_key"])

    print("editorial: %d picked, burned_captions=%s multi_speaker=%s"
          % (len(ed_picked), have_burn, have_multi))
    picks.extend(ed_picked)

    # --- light routes ------------------------------------------------------
    for route in ("moodreel", "minimal", "minimal_speech_uncut", "hype"):
        cands = sorted(pool[route], key=lambda c: c["created_at"], reverse=True)
        if route == "minimal":
            # guarantee the near-silent hard case
            silent = [c for c in cands
                      if (c["reason"] or "").startswith(("no_speech", "too_short"))]
            rest = [c for c in cands if c not in silent]
            cands = silent[:1] + rest
        take = cands[:QUOTA[route]]
        if len(take) < QUOTA[route]:
            print("  !! route %s: wanted %d, only %d available"
                  % (route, QUOTA[route], len(take)))
        picks.extend(take)

    # --- verify + hash -----------------------------------------------------
    verified = []
    for c in picks:
        h = head_object(c["s3_key"])
        if not h:
            print("  DROP unreachable: %s (%s)" % (c["job_id"], c["route"]))
            continue
        if h["bytes"] > MAX_BYTES:
            print("  DROP oversize %.0fMB: %s (%s)"
                  % (h["bytes"] / 1e6, c["job_id"], c["route"]))
            continue
        c.update(h)
        verified.append(c)
    print("verified reachable+sized: %d/%d" % (len(verified), len(picks)))

    if not args.no_hash:
        for i, c in enumerate(verified):
            c["sha256"] = sha256_stream(c["s3_key"])
            print("  sha256 %d/%d %s %s" % (i + 1, len(verified),
                                            c["job_id"][:8],
                                            (c["sha256"] or "FAIL")[:16]))

    manifest = {
        "version": 1,
        "frozen_at_commit": "1601ae0",
        "built_from": "video_jobs completed + asr_scribe_cohort2 lang join",
        "premium_note": ("UNSOURCEABLE: zero lumen/premium jobs exist in live "
                         "traffic [MEASURED 2026-08-09]; premium arm absent "
                         "by honesty, not oversight"),
        "sources": [],
    }
    for c in verified:
        sid = "%s_%s_%s" % (c["route"], (c["lang"] or "xx"), c["job_id"][:8])
        entry = {
            "id": sid, "job_id": c["job_id"], "video_url": c["video_url"],
            "s3_key": c["s3_key"], "bytes": c["bytes"], "etag": c["etag"],
            "sha256": c.get("sha256"), "duration_s": c["duration_s"],
            "lang": c["lang"], "route_expected": c["route"],
            "route_reason": c["reason"], "vibe": c["vibe"] or
            "Clean engaging edit", "model": "flare",
            "created_at": c["created_at"],
        }
        if c.get("burned_captions"):
            entry["hard_case"] = "burned_in_captions"
        if c.get("multi_speaker"):
            entry["hard_case"] = (entry.get("hard_case", "") +
                                  "+multi_speaker").lstrip("+")
        if c["route"] == "minimal" and (c["reason"] or "").startswith(
                ("no_speech", "too_short")):
            entry["hard_case"] = (entry.get("hard_case", "") +
                                  "+near_silent").lstrip("+")
        manifest["sources"].append(entry)

    out = os.path.join(HERE, "manifest.json")
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print("wrote %s with %d sources" % (out, len(manifest["sources"])))
    by_route = {}
    by_lang = {}
    for s in manifest["sources"]:
        by_route[s["route_expected"]] = by_route.get(s["route_expected"], 0) + 1
        by_lang[s["lang"]] = by_lang.get(s["lang"], 0) + 1
    print("routes:", by_route)
    print("langs:", by_lang)


if __name__ == "__main__":
    sys.exit(main())
