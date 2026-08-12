"""Prove the DEPLOYED image's Remotion bundle was built from the DEPLOYED source
(SafeImg is LIVE, not inert). Reads /remotion/bundle/.src_hash from the same image
the worker runs, recomputes the hash from /remotion/src, and asserts they match —
the exact check _assert_bundle_fresh runs on the first render, but run NOW so no
user is the first to discover a stale bundle.  modal run cert_bundle_fresh_verify.py"""
import modal, modal_app
app = modal.App("cert-bundle-fresh", image=modal_app.image)


@app.function(timeout=120)
def verify():
    import os, hashlib
    stamp_p, src = "/remotion/bundle/.src_hash", "/remotion/src"
    out = {"stamp_exists": os.path.exists(stamp_p), "src_exists": os.path.isdir(src)}
    if not out["stamp_exists"] or not out["src_exists"]:
        return out
    files = []
    for root, dirs, fs in os.walk(src):
        dirs[:] = [d for d in dirs if d != "node_modules"]
        for f in fs:
            if f.endswith((".ts", ".tsx", ".mjs")):
                files.append(os.path.join(root, f))
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(p[len(src):].encode())
        with open(p, "rb") as fh:
            h.update(fh.read())
    live = h.hexdigest()
    stamped = open(stamp_p).read().strip()
    out.update({"live_src_sha": live[:16], "bundle_stamp_sha": stamped[:16],
                "MATCH": live == stamped, "n_src_files": len(files)})
    # confirm SafeImg is actually compiled into the bundle JS
    try:
        bj = os.popen("grep -rl SAFEIMG /remotion/bundle 2>/dev/null | head -1").read().strip()
        out["safeimg_in_bundle_js"] = bool(bj)
    except Exception:
        out["safeimg_in_bundle_js"] = None
    return out


@app.local_entrypoint()
def main():
    r = verify.remote()
    print("\n=== DEPLOYED BUNDLE FRESHNESS ===")
    for k, v in r.items():
        print(f"  {k}: {v}")
    if r.get("MATCH") and r.get("safeimg_in_bundle_js"):
        print("\n✅ SafeImg is LIVE: bundle built from deployed source AND [SAFEIMG] present in compiled JS.")
    elif r.get("MATCH"):
        print("\n⚠️ hash matches but SAFEIMG grep inconclusive — check bundle JS manually.")
    else:
        print("\n❌ STALE OR MISSING — bundle not built from deployed source. SafeImg may be inert.")
