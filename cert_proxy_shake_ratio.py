"""Deflation ratio = proxy_score / source_score, across ALL shake magnitudes and fps
(Zac 2026-07-31). Two questions: (1) is the ratio FLAT vs magnitude (→ a scalar
correction is valid) or does it VARY (→ fitting noise)? (2) does ratio(fps) follow
source_fps/proxy_fps in one formula (24/30/60/120)? Then re-verify crossings with
corrected = proxy/ratio(fps) vs the ONE production threshold 5.0. HTTP+ffmpeg+cv2."""
import subprocess, os, json, urllib.request, statistics as st, math

SCRATCH = "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/e9b63b3b-7849-46b2-befa-856527c74120/scratchpad"
PROXY_FPS = 18.0
PROD_T = 5.0


def _probe(file_path, sample_count=12):  # VERBATIM handler.py:19485
    import cv2 as _cv2, numpy as _np
    cap = _cv2.VideoCapture(file_path)
    try:
        if not cap.isOpened():
            return 0.0
        tf = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH) or 0)
        if tf < 2 or w <= 0:
            return 0.0
        stride = max(1, int(tf * 0.9 // sample_count))
        start = max(1, int(tf * 0.05))
        ph = 240
        pw = max(1, int(ph * w / max(1, int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT) or 1))))
        pg, mags = None, []
        fp = dict(maxCorners=120, qualityLevel=0.01, minDistance=8, blockSize=7)
        lk = dict(winSize=(15, 15), maxLevel=2, criteria=(_cv2.TERM_CRITERIA_EPS | _cv2.TERM_CRITERIA_COUNT, 10, 0.03))
        for i in range(sample_count):
            fi = start + i * stride
            if fi >= tf:
                break
            cap.set(_cv2.CAP_PROP_POS_FRAMES, float(fi))
            ok, fr = cap.read()
            if not ok or fr is None:
                continue
            g = _cv2.cvtColor(_cv2.resize(fr, (pw, ph), interpolation=_cv2.INTER_AREA), _cv2.COLOR_BGR2GRAY)
            if pg is not None:
                p0 = _cv2.goodFeaturesToTrack(pg, mask=None, **fp)
                if p0 is not None and len(p0) >= 8:
                    p1, stt, _e = _cv2.calcOpticalFlowPyrLK(pg, g, p0, None, **lk)
                    if p1 is not None and stt is not None:
                        gn, go = p1[stt.flatten() == 1], p0[stt.flatten() == 1]
                        if len(gn) >= 8:
                            d = gn - go
                            mags.append(float(_np.median(_np.sqrt((d * d).sum(axis=-1)).flatten())))
            pg = g
        return float(_np.mean(mags)) if mags else 0.0
    finally:
        cap.release()


rows = json.load(open(f"{SCRATCH}/ratio_corpus.json"))
res = []
print(f"probing {len(rows)} clips...", flush=True)
for k, r in enumerate(rows):
    s, p = f"{SCRATCH}/_rs.mp4", f"{SCRATCH}/_rp.mp4"
    try:
        urllib.request.urlretrieve(r["url"], s)
        ssrc = _probe(s)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", s, "-vf", "scale=480:-2,fps=18", "-an", p], check=True)
        sprx = _probe(p)
        if ssrc > 0.5:
            res.append({**r, "src": round(ssrc, 2), "prx": round(sprx, 2), "ratio": round(sprx / ssrc, 3)})
        print(f"  [{k+1}/{len(rows)}] {r['id']} fps={r['fps']} shake={r['shake']} src={ssrc:.2f} prx={sprx:.2f} ratio={sprx/max(ssrc,.01):.2f}", flush=True)
    except Exception as e:
        print(f"  [{k+1}/{len(rows)}] {r['id']} SKIP {type(e).__name__}", flush=True)
    finally:
        for f in (s, p):
            if os.path.exists(f):
                os.remove(f)
json.dump(res, open(f"{SCRATCH}/ratio_results.json", "w"))

# (1) RATIO vs MAGNITUDE, 60fps only — the flatness test
print("\n=== RATIO vs SHAKE MAGNITUDE (60fps) — flat ⇒ scalar correction valid ===", flush=True)
s60 = [x for x in res if x["fps"] == 60]
bins = [(0, 3), (3, 5), (5, 8), (8, 15), (15, 999)]
for lo, hi in bins:
    b = [x["ratio"] for x in s60 if lo <= x["src"] < hi]
    if b:
        print(f"  shake [{lo},{hi}): median ratio={st.median(b):.3f}  (n={len(b)}, min={min(b):.2f} max={max(b):.2f})", flush=True)
if len(s60) >= 4:
    xs = [x["src"] for x in s60]; ys = [x["ratio"] for x in s60]
    mx, my = st.mean(xs), st.mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = sum((a - mx) ** 2 for a in xs)
    slope = cov / vx if vx else 0
    print(f"  ratio-vs-shake slope (60fps) = {slope:+.4f} per shake-unit  (≈0 ⇒ FLAT ⇒ scalar OK)", flush=True)

# (2) RATIO vs fps + one-formula fit ratio = (proxy_fps/source_fps)^p
print("\n=== RATIO vs SOURCE fps + formula ===", flush=True)
byfps = {}
for x in res:
    byfps.setdefault(x["fps"], []).append(x["ratio"])
pts = []
for f in sorted(byfps):
    m = st.median(byfps[f])
    print(f"  {f}fps: median ratio={m:.3f} (n={len(byfps[f])})", flush=True)
    if f > 0 and m > 0:
        pts.append((math.log(PROXY_FPS / f), math.log(m)))
if len(pts) >= 2:
    mx = st.mean([a for a, _ in pts]); my = st.mean([b for _, b in pts])
    cov = sum((a - mx) * (b - my) for a, b in pts); vx = sum((a - mx) ** 2 for a, _ in pts)
    p_exp = cov / vx if vx else 0
    print(f"  FIT: ratio ≈ (proxy_fps/source_fps)^{p_exp:.3f}  [ratio(fps)=(18/fps)**{p_exp:.3f}]", flush=True)

    def ratio_of(fps):
        return (PROXY_FPS / fps) ** p_exp if fps > 0 else 1.0
    # (3) re-verify crossings with corrected = proxy/ratio(fps) vs 5.0
    ss = w = 0
    for x in res:
        prod = x["shake"] >= PROD_T           # production gate (recorded)
        corr = (x["prx"] / ratio_of(x["fps"])) >= PROD_T
        if prod and not corr: ss += 1
        elif corr and not prod: w += 1
    print(f"\n=== CORRECTED crossings (corrected=proxy/ratio(fps) vs ONE threshold 5.0), n={len(res)}: "
          f"ships-shaky={ss}, waste={w} ===", flush=True)
    # also show the per-fps ratio the formula yields
    for f in (24, 30, 60, 120):
        print(f"    formula ratio({f}fps)={ratio_of(f):.3f} → effective threshold {PROD_T*ratio_of(f):.2f}", flush=True)
