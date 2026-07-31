"""DERIVE THE INSERT-CEILING for the caption sequence-aligner (Zac 2026-07-28).

The aligner marries Gemini's CORRECTED tokens onto Deepgram's timing slots (difflib
opcodes). MATCHED tokens inherit slot timing; a REPLACE distributes the slot span;
an INSERT (Gemini word with no Deepgram slot) interpolates across the gap between
neighbouring slots. 🚩 Zac's guard: interpolating across a small gap is a correction;
across a DROPPED SPAN (the Hindi clip lost 30s) it fabricates confidently-wrong
captions — worse than none. So an insert run whose interpolation gap exceeds a
CEILING must NOT interpolate (hand to coverage gate / drop). DERIVE that ceiling from
the divergence data (same discipline as the min-output-ratio floor: data said 20%,
a guessed 40% would over-fire) — do NOT pick a number.

This cert runs the aligner with NO ceiling and reports the distribution of insert-run
interpolation gaps (corrections = small; dropped span = the huge outlier) so the
valley between the two populations sets the ceiling. No production code touched.

Clips: Hindi 15c392d6 (known ~30s tail drop = the dropped-span outlier), 3 Punjabi
(garbage Deepgram text → heavy correction), 2 English (clean → correction baseline).
"""
import os, sys, json, difflib
sys.path.insert(0, "/")
import modal, modal_app

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-caption-align-derive", image=image)
SECRETS = [modal.Secret.from_name("promptly-secrets"), modal.Secret.from_name("gemini-vertex")]

CLIPS = [
    {"label": "hindi-drop", "url": "https://d1iax8jos987n3.cloudfront.net/sources/15c392d6-26bf-4838-92c4-40afe386b9e0/1785208983103-930A4D00-CF5D-4337-BB24-0F65D408538F_L0_001.mp4"},
    {"label": "punjabi-1", "url": "https://d1iax8jos987n3.cloudfront.net/sources/5bc48531-f774-40e8-b092-1c25c8548486/1784678176285-8111F14B-06DF-4C5E-8691-FDCEDCD783D6_L0_001.mp4"},
    {"label": "punjabi-2", "url": "https://d1iax8jos987n3.cloudfront.net/sources/8ebdc64d-909c-49a8-83b3-e5d3b20b7d29/1784617018415-186FADA5-12F0-4F7A-BCCB-08DB4C4F3ECA_L0_001.mp4"},
    {"label": "punjabi-3", "url": "https://d1iax8jos987n3.cloudfront.net/sources/8ebdc64d-909c-49a8-83b3-e5d3b20b7d29/1784363857233-1E39B8F5-D9E2-43DA-8BB8-A0AE3DEBAAD3_L0_001.mp4"},
    {"label": "english-1", "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1785106634357-F110DBA9-BD7B-4A59-9094-B2F22CF48D57_L0_001.mp4"},
    {"label": "english-2", "url": "https://d1iax8jos987n3.cloudfront.net/sources/ec702499-ca10-49e6-8850-df8f99840904/1782690788639-64F38CEE-4A5B-4043-ADE1-DD09E2847BC6_L0_001.mp4"},
]


def _norm(w):
    return "".join(ch for ch in str(w or "").lower() if ch.isalnum())


@app.function(secrets=SECRETS, cpu=4.0, memory=8192, timeout=1800)
def run() -> dict:
    import uuid, urllib.request, traceback
    os.environ["APP_URL"] = ""; os.environ["JOB_STATUS_WRITES_ENABLED"] = ""
    sys.path.insert(0, "/")
    import handler as H

    out = {"clips": [], "all_interior_insert_gaps_s": [], "all_replace_spans_s": [], "trailing_inserts": []}
    for clip in CLIPS:
        rec = {"label": clip["label"]}
        try:
            path = f"/tmp/{uuid.uuid4()}.mp4"
            urllib.request.urlretrieve(clip["url"], path)

            # Deepgram = baseline text + TIMING slots
            dg = H.transcribe_audio(path, language="multi")
            dgw = dg.get("words") or []
            audio_end = max((float(w.get("end") or 0.0) for w in dgw), default=0.0)

            # Gemini = the CORRECTED word sequence (native script, no timing needed)
            audio = H.prepare_audio_for_deepgram(path)
            prompt = ("Transcribe this audio into the correct sequence of SPOKEN WORDS in the "
                      "native script. Do NOT translate, number, or punctuate as separate tokens. "
                      'Return JSON {"words":["<word1>","<word2>", ...]} in spoken order.')
            _r = H._get_genai_client().models.generate_content(
                model=H.GEMINI_MODEL,
                contents=[H.genai_types.Part.from_bytes(data=audio, mime_type="audio/flac"), prompt],
                config=H.genai_types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"))
            try:
                obj = json.loads(_r.text or "{}")
                gm = obj.get("words") if isinstance(obj, dict) else obj
                gm = [t for t in (gm or []) if _norm(t)]
            except Exception as _e:
                rec["gemini_parse_error"] = str(_e)[:120]; gm = []

            rec["dg_words"] = len(dgw); rec["gemini_words"] = len(gm); rec["audio_s"] = round(audio_end, 1)
            if not dgw or not gm:
                out["clips"].append(rec); continue

            dg_toks = [_norm(w.get("word")) for w in dgw]
            gm_toks = [_norm(t) for t in gm]
            sm = difflib.SequenceMatcher(None, dg_toks, gm_toks, autojunk=False)

            n_equal = n_replace = n_insert = n_delete = 0
            interior_gaps = []      # (n_gemini_tokens, gap_s) for interior inserts
            trailing = []           # n_gemini_tokens for trailing/leading inserts (open-ended)
            replace_spans = []      # (n_dg, n_gm, span_s)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    n_equal += (i2 - i1)
                elif tag == "delete":
                    n_delete += (i2 - i1)
                elif tag == "replace":
                    n_replace += 1
                    span = float(dgw[i2 - 1].get("end") or 0) - float(dgw[i1].get("start") or 0)
                    replace_spans.append((i2 - i1, j2 - j1, round(span, 2)))
                elif tag == "insert":
                    n_insert += 1
                    m = j2 - j1
                    left = float(dgw[i1 - 1].get("end") or 0.0) if i1 > 0 else None
                    right = float(dgw[i1].get("start") or 0.0) if i1 < len(dgw) else None
                    if left is not None and right is not None:
                        interior_gaps.append((m, round(right - left, 2)))
                    else:
                        # open-ended: leading (no left) or trailing (no right) — the dropped-EDGE signature
                        trailing.append({"label": clip["label"], "n_tokens": m,
                                         "kind": "leading" if left is None else "trailing",
                                         "at_s": round(right if left is None else left, 1)})

            rec["opcodes"] = {"equal": n_equal, "replace": n_replace, "insert": n_insert, "delete": n_delete}
            rec["align_rate"] = round(n_equal / max(1, min(len(dg_toks), len(gm_toks))), 3)
            rec["interior_insert_gaps"] = sorted(g for (_m, g) in interior_gaps)
            rec["interior_insert_runs"] = [(m, g) for (m, g) in interior_gaps]
            rec["trailing_leading_inserts"] = trailing
            rec["replace_span_s_sorted"] = sorted(s for (_a, _b, s) in replace_spans)
            out["all_interior_insert_gaps_s"] += [g for (_m, g) in interior_gaps]
            out["all_replace_spans_s"] += [s for (_a, _b, s) in replace_spans]
            out["trailing_inserts"] += trailing
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"; rec["tb"] = traceback.format_exc()[-500:]
        out["clips"].append(rec)

    # aggregate distribution → find the valley
    import statistics as st
    gaps = sorted(out["all_interior_insert_gaps_s"])
    out["SUMMARY"] = {
        "interior_insert_gap_count": len(gaps),
        "interior_gap_p50": round(st.median(gaps), 2) if gaps else None,
        "interior_gap_p90": round(gaps[int(0.9 * len(gaps))], 2) if gaps else None,
        "interior_gap_p95": round(gaps[min(len(gaps) - 1, int(0.95 * len(gaps)))], 2) if gaps else None,
        "interior_gap_max": round(max(gaps), 2) if gaps else None,
        "interior_gaps_sorted": [round(g, 2) for g in gaps],
        "trailing_leading_insert_count": len(out["trailing_inserts"]),
        "trailing_leading_inserts": out["trailing_inserts"],
    }
    return out


@app.local_entrypoint()
def main():
    print("=== DERIVE THE CAPTION-ALIGNER INSERT CEILING ===")
    o = run.remote()
    for c in o.get("clips", []):
        print("\n" + "-" * 58)
        if c.get("error"):
            print(f"  {c['label']}: ERROR {c['error']}"); continue
        print(f"  {c['label']}: dg={c.get('dg_words')} gemini={c.get('gemini_words')} audio={c.get('audio_s')}s "
              f"align_rate={c.get('align_rate')}")
        print(f"    opcodes={c.get('opcodes')}")
        print(f"    interior insert gaps (s), sorted: {c.get('interior_insert_gaps')}")
        if c.get("trailing_leading_inserts"):
            print(f"    >> TRAILING/LEADING inserts (dropped-edge): {c.get('trailing_leading_inserts')}")
        rs = c.get("replace_span_s_sorted") or []
        if rs:
            print(f"    replace spans (s), sorted: {rs[:12]}{' ...' if len(rs) > 12 else ''}")
    s = o.get("SUMMARY", {})
    print("\n" + "=" * 58)
    print("AGGREGATE — interior insert-run interpolation gaps (the correction population):")
    print(f"  n={s.get('interior_insert_gap_count')}  p50={s.get('interior_gap_p50')}s  p90={s.get('interior_gap_p90')}s  "
          f"p95={s.get('interior_gap_p95')}s  max={s.get('interior_gap_max')}s")
    print(f"  all sorted: {s.get('interior_gaps_sorted')}")
    print(f"\nTRAILING/LEADING inserts (the dropped-SPAN population — never interpolate): "
          f"n={s.get('trailing_leading_insert_count')}")
    for t in s.get("trailing_leading_inserts", []):
        print(f"   {t['label']}: {t['n_tokens']} tokens, {t['kind']} @ {t['at_s']}s")
    print("\nRAW:", json.dumps(o)[:1600])
