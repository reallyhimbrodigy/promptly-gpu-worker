"""TIMED PROBE — what Claude Code costs inside a Modal container.

THE NUMBER THIS EXISTS FOR. Zac's law is 120s end to end. If Claude Code drives
ChatCut per job, the per-job overhead is boot + CLI start + MCP connect, BEFORE
the agent has done any thinking. That number decides whether this architecture
needs warm containers designed in from the start or can run cold per job.

MEASURED HERE, NOT ESTIMATED:
  t_import     container is alive and Python is running
  t_node       node -v         (runtime present)
  t_cli        claude --version (the CLI itself starts)
  t_mcp_probe  an unauthenticated POST to ChatCut's MCP endpoint — the network
               round trip the real OAuth handshake pays, without needing a
               token to measure it

WHAT THIS DOES NOT MEASURE, said out loud rather than folded into a total: the
OAuth token exchange, the skill load, and the agent's own turns. Turns dominate
on the current pipeline (7-10 on a talking head, round 70) and they will dominate
here too. This bounds the FLOOR, not the job.
"""
import subprocess
import time

import modal

app = modal.App("probe-claude-boot")

# NODE 22 FROM NODESOURCE, and the CLI baked in — not npx'd at run time. A
# 267MB install inside the job would land as an opaque stall in the middle of
# an edit, which is the same lesson the Chrome download taught this lane.
IMG = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl", "ca-certificates", "git")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs",
        "npm install -g @anthropic-ai/claude-code",
    )
)


@app.function(image=IMG, timeout=600)
def probe():
    t0 = time.time()
    out = {}

    def run(label, cmd):
        s = time.time()
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=120)
            out[label] = {"s": round(time.time() - s, 3),
                          "rc": r.returncode,
                          "out": (r.stdout or r.stderr).strip()[:120]}
        except Exception as e:                                    # noqa: BLE001
            out[label] = {"s": round(time.time() - s, 3), "rc": None,
                          "out": f"{type(e).__name__}: {e}"[:120]}

    run("node", "node --version")
    run("cli_cold", "claude --version")
    run("cli_warm", "claude --version")
    # THE NETWORK LEG OF THE MCP CONNECT, measured without a token. A 401 here
    # is the SUCCESS case for this probe: it proves the endpoint is reachable
    # from a Modal container and times the round trip.
    run("mcp_reach",
        "curl -sS -o /dev/null -w '%{http_code} %{time_total}' --max-time 30 "
        "-X POST https://api.chatcut.io/api/external-mcp/mcp "
        "-H 'Content-Type: application/json' -d '{}'")
    run("npm_root", "du -sh $(npm root -g) 2>/dev/null | cut -f1")

    out["_total_in_container_s"] = round(time.time() - t0, 3)
    return out


@app.local_entrypoint()
def main():
    w0 = time.time()
    res = probe.remote()
    wall = round(time.time() - w0, 2)
    print("\n=== CLAUDE CODE IN A MODAL CONTAINER ===")
    for k, v in res.items():
        if k.startswith("_"):
            continue
        print(f"  {k:12s} {v['s']:>7.3f}s  rc={v['rc']}  {v['out']}")
    print(f"\n  in-container total   {res['_total_in_container_s']:>7.3f}s")
    print(f"  WALL incl. cold start{wall:>7.2f}s   <- the per-job floor")
