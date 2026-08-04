"""Settle the SafeImg dispute by grepping the RUNNING prebundle.

⚠️ THE PROPOSED CHECK WOULD GIVE A FALSE NEGATIVE. Grepping the bundle for
"[SAFEIMG]" finds nothing whether or not SafeImg is present, because
SafeImg.tsx contains no such log line — verified: 0 occurrences of "SAFEIMG"
in the component source. A grep for a log line that was never written cannot
distinguish "absent" from "silent".

So this greps for what actually identifies the component in the compiled
bundle, and — the part that matters — whether any bare <Img> survives beside
it. SafeImg being PRESENT is not the same as SafeImg being USED.
"""
import os
import sys

sys.path.insert(0, "/")
import modal  # noqa: E402
import modal_app  # noqa: E402

image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-safeimg-bundle", image=image)


@app.function(image=image, cpu=1, memory=2048, timeout=300)
def inspect_bundle() -> dict:
    import glob
    import re
    import subprocess

    out = {"bundle_root": None, "files": 0, "hits": {}, "samples": {}}
    root = "/remotion/bundle"
    out["bundle_exists"] = os.path.isdir(root)
    if not out["bundle_exists"]:
        return out
    out["bundle_root"] = root
    js = glob.glob(f"{root}/**/*.js", recursive=True) + glob.glob(f"{root}/**/*.mjs", recursive=True)
    out["files"] = len(js)

    # Compiled bundles mangle local identifiers but PRESERVE string literals and
    # component displayName/prop names. Probe several independent markers so one
    # minifier decision cannot produce a false verdict.
    probes = {
        "SafeImg_identifier": r"SafeImg",
        "SAFEIMG_logline": r"\[SAFEIMG\]",          # expected ABSENT — no such log exists
        "delayRender": r"delayRender",
        "continueRender": r"continueRender",
        "onError_handler": r"onError",
        "blob_url": r"blob:",
    }
    for name, pat in probes.items():
        n = 0
        sample = None
        rx = re.compile(pat)
        for f in js:
            try:
                with open(f, "r", errors="ignore") as fh:
                    txt = fh.read()
            except Exception:
                continue
            c = len(rx.findall(txt))
            if c:
                n += c
                if sample is None:
                    i = rx.search(txt).start()
                    sample = f"{os.path.basename(f)}: …{txt[max(0,i-70):i+90]}…"
        out["hits"][name] = n
        if sample:
            out["samples"][name] = sample[:240]

    # Source tree, if the image carries it — the authored side of the question.
    src = {}
    for p in ("/remotion/src", "/remotion"):
        tsx = glob.glob(f"{p}/**/*.tsx", recursive=True)
        if tsx:
            src["tsx_files"] = len(tsx)
            src["SafeImg.tsx_present"] = any("SafeImg.tsx" in f for f in tsx)
            bare = used = 0
            for f in tsx:
                try:
                    t = open(f, errors="ignore").read()
                except Exception:
                    continue
                bare += len(re.findall(r"<Img[\s/>]", t))
                used += len(re.findall(r"<SafeImg[\s/>]", t))
            src["bare_Img_tags"] = bare
            src["SafeImg_tags"] = used
            break
    out["source"] = src
    try:
        out["bundle_mtime"] = subprocess.run(
            ["sh", "-c", f"stat -c %y {root} 2>/dev/null || stat -f %Sm {root}"],
            capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        pass
    return out


@app.local_entrypoint()
def main():
    import json
    r = inspect_bundle.remote()
    print("\n" + "=" * 78)
    print(f"bundle exists : {r.get('bundle_exists')}  ({r.get('files')} js/mjs files)")
    print(f"bundle mtime  : {r.get('bundle_mtime')}")
    print("\nMARKERS IN THE RUNNING BUNDLE:")
    for k, v in (r.get("hits") or {}).items():
        print(f"   {k:22} {v}")
    print("\nSAMPLES:")
    for k, v in (r.get("samples") or {}).items():
        print(f"   {k}: {v}")
    print(f"\nSOURCE TREE IN IMAGE: {json.dumps(r.get('source'))}")
    print("=" * 78)
    print("RESULT " + json.dumps(r, default=str)[:2500])
