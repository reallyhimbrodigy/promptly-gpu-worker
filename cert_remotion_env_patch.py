"""REGRESSION CERT — Remotion environment patch (W1-FIX-DEEP Class B).

Proves, locally and without any deploy, that patch-remotion-env.mjs:
  1. applies cleanly to a pristine copy of the PINNED @remotion/renderer
     (4.0.450) dist tree — all four patterns land, exit 0;
  2. is IDEMPOTENT (second run: no-op, exit 0) — safe on cached image layers;
  3. is BEHAVIOR-PRESERVING where it must be:
       - with the Modal cgroup sentinel (~2^63 bytes) mocked in, the PATCHED
         getAvailableMemory returns the same practical value as the
         UNPATCHED one (the unpatched code already took
         min(freemem, 2^63) = freemem) while the multi-line "Detected
         differing memory amounts" warning — the noise that got the whole
         class misfiled as a memory failure — fires ONLY in the unpatched
         module (also proving the mock exercised the path, non-vacuous);
       - with a SANE cgroup limit mocked in, the guard does NOT null it —
         a real container limit is still respected;
  4. moves ONLY the browser-connect failure deadline (25000 → 120000) —
     the patched files carry no other 25000 in the openBrowser call.

Run locally: python3 cert_remotion_env_patch.py
Exits 0 on full PASS, 1 on any failure.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.abspath(__file__))
SRC_RENDERER = os.path.join(REPO, "src/remotion/node_modules/@remotion/renderer")
PATCH_SCRIPT = os.path.join(REPO, "src/remotion/patch-remotion-env.mjs")
SENTINEL = 9223372036854771712   # what Modal's cgroup memory.max reports (~2^63)
SANE_LIMIT = 8 * 1024 ** 3       # a real 8 GiB container limit

_results = []


def check(label, cond, detail=""):
    _results.append((label, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))


def run_node(script, cwd=None):
    return subprocess.run(["node", "-e", script], capture_output=True, text=True, cwd=cwd)


def main():
    if not os.path.isdir(SRC_RENDERER):
        print("FATAL: pristine @remotion/renderer not found locally")
        return 1
    tmp = tempfile.mkdtemp(prefix="cert_remotion_patch_")
    print(f"[cert] sandbox: {tmp}")
    sandbox_nm = os.path.join(tmp, "node_modules")
    dst = os.path.join(sandbox_nm, "@remotion", "renderer")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.makedirs(dst, exist_ok=True)
    # dist + package.json are all require() needs on the renderer itself…
    shutil.copytree(os.path.join(SRC_RENDERER, "dist"), os.path.join(dst, "dist"))
    shutil.copy2(os.path.join(SRC_RENDERER, "package.json"), dst)
    # …plus the sibling `remotion` package (renderer's logger→repro chain
    # requires remotion/version). Symlink — it is never patched.
    os.symlink(os.path.join(os.path.dirname(SRC_RENDERER), "..", "remotion"),
               os.path.join(sandbox_nm, "remotion"))

    # ── 1. patch applies cleanly ──────────────────────────────────────────
    print("\n[cert] 1 — patch applies to pristine 4.0.450")
    r = subprocess.run(["node", PATCH_SCRIPT, sandbox_nm], capture_output=True, text=True)
    check("patch run exits 0", r.returncode == 0, (r.stdout + r.stderr)[-200:].strip())
    esm = open(os.path.join(dst, "dist/esm/index.mjs")).read()
    ob = open(os.path.join(dst, "dist/open-browser.js")).read()
    gam = open(os.path.join(dst, "dist/memory/get-available-memory.js")).read()
    check("esm: connect deadline 120000, no 25000 left",
          "timeout: 120000," in esm and "timeout: 25000" not in esm)
    check("cjs: connect deadline 120000, no 25000 left",
          "timeout: 120000," in ob and "timeout: 25000" not in ob)
    check("esm: cgroup sentinel guard present", "1125899906842624" in esm)
    check("cjs: cgroup sentinel guard present", "1125899906842624" in gam)

    # ── 2. idempotent ─────────────────────────────────────────────────────
    print("\n[cert] 2 — idempotent second run")
    r2 = subprocess.run(["node", PATCH_SCRIPT, sandbox_nm], capture_output=True, text=True)
    check("second run exits 0 (already-patched)", r2.returncode == 0
          and "already patched" in r2.stdout)

    # ── 3. behavior-preserving under the mocked bogus cgroup ─────────────
    print("\n[cert] 3 — mocked-cgroup unit proof (patched vs pristine)")
    probe = """
const cgPath = %(cg)s;
const gamPath = %(gam)s;
const cg = require(cgPath);
cg.getAvailableMemoryFromCgroup = () => %(mock)s;
let warned = [];
const origWarn = console.warn;
console.warn = (...a) => { warned.push(a.join(' ')); };
const gam = require(gamPath);
const v = gam.getAvailableMemory('info');
console.warn = origWarn;
console.log(JSON.stringify({value: v, warned: warned.join('|')}));
"""

    def run_probe(renderer_dir, mock):
        script = probe % {
            "cg": json.dumps(os.path.join(renderer_dir, "dist/memory/from-docker-cgroup.js")),
            "gam": json.dumps(os.path.join(renderer_dir, "dist/memory/get-available-memory.js")),
            "mock": str(mock),
        }
        pr = run_node(script)
        if pr.returncode != 0:
            print(f"  [probe-error] rc={pr.returncode}: {(pr.stderr or '')[:300]}")
            return None
        return json.loads(pr.stdout.strip().splitlines()[-1])

    patched = run_probe(dst, SENTINEL)
    pristine = run_probe(SRC_RENDERER, SENTINEL)
    check("both probes ran", patched is not None and pristine is not None)
    if patched and pristine:
        check("UNPATCHED warns 'Detected differing memory amounts' (mock exercised — non-vacuous)",
              "Detected differing memory amounts" in pristine["warned"])
        check("PATCHED emits NO differing-memory warning",
              "Detected differing memory amounts" not in patched["warned"])
        pv, uv = float(patched["value"]), float(pristine["value"])
        check("values agree (behavior-preserving: unpatched already took min(freemem, 2^63)=freemem)",
              uv > 0 and abs(pv - uv) / uv < 0.25,
              f"patched={pv:.3e} unpatched={uv:.3e}")
        check("patched value is sane (not the sentinel)", pv < 1e15, f"{pv:.3e}")
    sane = run_probe(dst, SANE_LIMIT)
    check("SANE cgroup limit still respected (guard nulls sentinels only)",
          sane is not None and float(sane["value"]) <= SANE_LIMIT,
          str(sane and sane["value"]))

    shutil.rmtree(tmp, ignore_errors=True)
    n_fail = sum(1 for _, ok in _results if not ok)
    print(f"\n[cert] {len(_results) - n_fail}/{len(_results)} checks passed")
    if n_fail:
        print("[cert] FAIL")
        return 1
    print("[cert] PASS — patch applies, idempotent, behavior-preserving, noise-kill proven")
    return 0


if __name__ == "__main__":
    sys.exit(main())
