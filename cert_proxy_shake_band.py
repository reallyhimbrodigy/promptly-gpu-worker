"""Proxy-detect DECISION-NEUTRAL threshold on the in-band [4,7] corpus (Zac 2026-07-31).
Download each source (public CloudFront), probe full-res (cross-check vs recorded
shake) + 480p@18fps proxy, then pick the T_proxy that best REPRODUCES production's
gate (recorded_shake >= 5.0) — minimize crossings, not err safe. Compare single vs
fps-aware. HTTP + ffmpeg + cv2; no Modal, no S3 creds."""
import subprocess, os, json, urllib.request, statistics as st

SCRATCH = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad"
PROD_THRESH = 5.0


def _probe_shake_intensity(file_path, sample_count=12):  # VERBATIM handler.py:19485
    import cv2 as _cv2, numpy as _np
    cap = _cv2.VideoCapture(file_path)
    try:
        if not cap.isOpened():
            return 0.0
        total_frames = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
        src_w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH) or 0)
        if total_frames < 2 or src_w <= 0:
            return 0.0
        stride = max(1, int(total_frames * 0.9 // sample_count))
        start = max(1, int(total_frames * 0.05))
        probe_h = 240
        probe_w = max(1, int(probe_h * src_w / max(1, int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT) or 1))))
        prev_gray, magnitudes = None, []
        fp = dict(maxCorners=120, qualityLevel=0.01, minDistance=8, blockSize=7)
        lk = dict(winSize=(15, 15), maxLevel=2, criteria=(_cv2.TERM_CRITERIA_EPS | _cv2.TERM_CRITERIA_COUNT, 10, 0.03))
        for i in range(sample_count):
            fi = start + i * stride
            if fi >= total_frames:
                break
            cap.set(_cv2.CAP_PROP_POS_FRAMES, float(fi))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            gray = _cv2.cvtColor(_cv2.resize(frame, (probe_w, probe_h), interpolation=_cv2.INTER_AREA), _cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                p0 = _cv2.goodFeaturesToTrack(prev_gray, mask=None, **fp)
                if p0 is not None and len(p0) >= 8:
                    p1, stt, _e = _cv2.calcOpticalFlowPyrLK(prev_gray, gray, p0, None, **lk)
                    if p1 is not None and stt is not None:
                        gn, go = p1[stt.flatten() == 1], p0[stt.flatten() == 1]
                        if len(gn) >= 8:
                            d = gn - go
                            magnitudes.append(float(_np.median(_np.sqrt((d * d).sum(axis=-1)).flatten())))
            prev_gray = gray
        return float(_np.mean(magnitudes)) if magnitudes else 0.0
    finally:
        cap.release()


rows = json.load(open(f"{SCRATCH}/inband_corpus.json"))
results = []
print(f"processing {len(rows)} in-band clips...")
for r in rows:
    src = f"{SCRATCH}/_s.mp4"
    prx = f"{SCRATCH}/_p.mp4"
    try:
        urllib.request.urlretrieve(r["url"], src)
        s_src = _probe_shake_intensity(src)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", "scale=480:-2,fps=18", "-an", prx], check=True)
        s_prx = _probe_shake_intensity(prx)
        results.append({**r, "src_probe": round(s_src, 2), "prx_probe": round(s_prx, 2)})
        print(f"  {r['id']} fps={r['fps']} rec={r['shake']:>4} local_src={s_src:>5.2f} proxy={s_prx:>5.2f}")
    except Exception as e:
        print(f"  {r['id']} SKIP ({type(e).__name__}: {str(e)[:50]})")
    finally:
        for f in (src, prx):
            if os.path.exists(f):
                os.remove(f)

# harness fidelity: local full-res probe vs production's recorded shake
paired = [(x["shake"], x["src_probe"]) for x in results]
if paired:
    diffs = [abs(a - b) for a, b in paired]
    print(f"\n=== harness fidelity: local full-res probe vs recorded shake — median|Δ|={st.median(diffs):.2f}, max={max(diffs):.2f} ===")

# GROUND-TRUTH gate = production's recorded shake >= 5.0 (that's the decision set to reproduce)
def crossings(items, tproxy_fn):
    ship_shaky = waste = 0
    for x in items:
        prod = x["shake"] >= PROD_THRESH
        prox = x["prx_probe"] >= tproxy_fn(x)
        if prod and not prox: ship_shaky += 1   # prod stabilized, proxy skips → ships shaky (REGRESSION)
        elif prox and not prod: waste += 1       # prod skipped, proxy stabilizes → wasted 44s
    return ship_shaky, waste

print(f"\n=== DECISION-NEUTRAL sweep vs production gate (recorded_shake>=5.0), n={len(results)} ===")
best = None
for t10 in range(35, 56):
    t = t10 / 10.0
    ss, w = crossings(results, lambda x, t=t: t)
    tot = ss + w
    if best is None or tot < best[0] or (tot == best[0] and abs(t - 5.0) < abs(best[1] - 5.0)):
        best = (tot, t, ss, w)
print(f"  best SINGLE threshold T_proxy={best[1]:.1f}: {best[0]} crossings (ships-shaky={best[2]}, waste={best[3]})")
ss5, w5 = crossings(results, lambda x: 5.0)
print(f"  naive T_proxy=5.0: {ss5+w5} crossings (ships-shaky={ss5}, waste={w5})")

# fps-aware: separate decision-neutral threshold for 60fps vs the rest
def best_t_for(subset):
    b = None
    for t10 in range(30, 56):
        t = t10 / 10.0
        ss, w = crossings(subset, lambda x, t=t: t)
        if b is None or ss + w < b[0]: b = (ss + w, t)
    return b
sub60 = [x for x in results if x["fps"] == 60]
subrest = [x for x in results if x["fps"] != 60]
if sub60:
    b60 = best_t_for(sub60); brest = best_t_for(subrest)
    fa = crossings(results, lambda x: b60[1] if x["fps"] == 60 else brest[1])
    print(f"\n  fps-AWARE: 60fps→T={b60[1]:.1f} (n={len(sub60)}), other→T={brest[1]:.1f} (n={len(subrest)}): {sum(fa)} crossings (ship={fa[0]}, waste={fa[1]})")
    print(f"  → SINGLE {best[0]} crossings vs fps-AWARE {sum(fa)} crossings — pick the lower.")
print(f"\n  production 60fps share = 21% (DB, 45/210); 60fps in-band here = {len(sub60)}/{len(results)}")
