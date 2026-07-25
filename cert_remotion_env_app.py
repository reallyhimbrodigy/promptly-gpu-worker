"""Ephemeral LIVE cert — Remotion environment patch on a real Modal host
(W1-FIX-DEEP Class B). `modal run cert_remotion_env_app.py` — never deployed.

Builds the CURRENT image (which now runs patch-remotion-env.mjs at build; the
build itself fails if the patch does not land) and proves ON A REAL MODAL
HOST:
  1. the image's bundled @remotion/renderer carries both patches
     (browser-connect deadline 120000, cgroup >1PiB sentinel guard);
  2. the live host's cgroup memory.max really is the sentinel the patch
     exists for (reported; informational if Modal ever fixes it);
  3. openBrowser() — the EXACT code path that produced the RENDER_FATAL
     browser-connect TimeoutError (job 7f09fe28) — opens and closes Chrome
     successfully with the patched deadline, using the same executable +
     chromiumOptions render-full.mjs uses;
  4. the launch's stderr carries NO "Detected differing memory amounts"
     block — on this host the UNPATCHED renderer always printed it (cgroup
     sentinel), so its absence proves the sentinel guard is live, not just
     present on disk.

A full composition render is deliberately NOT part of this cert: the two
patches cannot alter render output (the deadline only fires on failure; the
memory guard is log-only — value equivalence proven unit-level in
cert_remotion_env_patch.py). The browser open IS the failing code path.
"""
import sys

import modal

sys.path.insert(0, ".")
import modal_app  # noqa: E402

image = modal_app.image
app = modal.App("cert-remotion-env", image=image)


@app.function(cpu=8, memory=16384, timeout=900)
def probe():
    import os
    import subprocess

    out = {}
    base = "/remotion/node_modules/@remotion/renderer"
    esm = open(os.path.join(base, "dist/esm/index.mjs")).read()
    ob = open(os.path.join(base, "dist/open-browser.js")).read()
    gam = open(os.path.join(base, "dist/memory/get-available-memory.js")).read()
    out["esm_timeout_patched"] = ("timeout: 120000," in esm
                                  and "timeout: 25000" not in esm)
    out["cjs_timeout_patched"] = ("timeout: 120000," in ob
                                  and "timeout: 25000" not in ob)
    out["sentinel_guard_present"] = ("1125899906842624" in esm
                                     and "1125899906842624" in gam)
    try:
        out["live_cgroup_memory_max"] = open("/sys/fs/cgroup/memory.max").read().strip()
    except Exception as e:  # pragma: no cover — cgroup v1 host
        out["live_cgroup_memory_max"] = "unreadable: %s" % e

    node_script = r"""
const {openBrowser} = require("/remotion/node_modules/@remotion/renderer");
(async () => {
  const t0 = Date.now();
  const browser = await openBrowser("chrome", {
    browserExecutable: "/usr/local/bin/chrome-headless-shell",
    chromiumOptions: {gl: "swangle", enableMultiProcessOnLinux: true, disableWebSecurity: true},
  });
  console.log("[probe] browser open in " + ((Date.now() - t0) / 1000).toFixed(2) + "s");
  try { await browser.close({silent: false}); } catch (e) { console.log("[probe] close warning: " + e.message); }
  console.log("[probe] PROBE_OK");
})().catch((e) => { console.error("[probe] PROBE_FAIL", e); process.exit(1); });
"""
    r = subprocess.run(["node", "-e", node_script], capture_output=True,
                       text=True, timeout=300, cwd="/remotion")
    out["open_browser_rc"] = r.returncode
    out["open_browser_ok"] = "PROBE_OK" in (r.stdout or "")
    out["open_browser_log"] = (r.stdout or "")[-400:] + (r.stderr or "")[-400:]
    out["differing_memory_warning_fired"] = (
        "Detected differing memory" in (r.stdout or "") + (r.stderr or ""))
    return out


@app.local_entrypoint()
def main():
    out = probe.remote()
    print("\n===== cert-remotion-env (live Modal host) =====")
    for k, v in out.items():
        print("  %s = %s" % (k, v))
    ok = (out["esm_timeout_patched"] and out["cjs_timeout_patched"]
          and out["sentinel_guard_present"] and out["open_browser_ok"]
          and not out["differing_memory_warning_fired"])
    print("\nRESULT: %s" % ("PASS" if ok else "FAIL"))
    if not ok:
        raise SystemExit(1)
