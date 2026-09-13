"""Diagnose why the ChatCut skill is 'Unknown' inside the container."""
import subprocess, os, modal

app = modal.App("probe-plugin-state")
IMG = (modal.Image.debian_slim(python_version="3.11")
       .apt_install("curl", "ca-certificates", "git")
       .run_commands(
           "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
           "apt-get install -y nodejs",
           "npm install -g @anthropic-ai/claude-code")
       .add_local_dir(os.path.expanduser(
           "~/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12"),
           "/root/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12", copy=True)
       .add_local_dir("/tmp/cc_marketplace",
                      "/root/.claude/plugins/marketplaces/chatcut-inc",
                      copy=True)
       .run_commands(
           "mkdir -p /root/.claude/plugins",
           """cat > /root/.claude/plugins/known_marketplaces.json <<'JSON'
{"chatcut-inc":{"source":{"source":"git",
  "url":"https://github.com/ChatCut-Inc/agent-plugin.git","ref":"main"},
  "installLocation":"/root/.claude/plugins/marketplaces/chatcut-inc"}}
JSON""",
           """cat > /root/.claude/settings.json <<'JSON'
{"enabledPlugins":{"chatcut@chatcut-inc":true}}
JSON""",
           """cat > /root/.claude/plugins/installed_plugins.json <<'JSON'
{"version":2,"plugins":{"chatcut@chatcut-inc":[{"scope":"user",
"installPath":"/root/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12",
"version":"1.10.12"}]}}
JSON"""))


@app.function(image=IMG, timeout=300,
              secrets=[modal.Secret.from_name("anthropic-api-key")])
def probe():
    o = {}
    o["HOME"] = os.environ.get("HOME")
    o["cwd"] = os.getcwd()
    o["whoami"] = subprocess.run("whoami", shell=True, capture_output=True,
                                 text=True).stdout.strip()
    for p in ("/root/.claude/settings.json",
              "/root/.claude/plugins/installed_plugins.json",
              "/root/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12/skills/chatcut-plugin-basics-claude/SKILL.md",
              "/root/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12/.claude-plugin/plugin.json"):
        o[p] = os.path.exists(p)
    o["plugin_root_ls"] = subprocess.run(
        "ls /root/.claude/plugins/cache/chatcut-inc/chatcut/1.10.12 2>&1 | head -20",
        shell=True, capture_output=True, text=True).stdout.strip()
    r = subprocess.run(
        ["claude", "-p", "List every skill name available to you, one per line. "
         "Do not call any tool.", "--output-format", "text"],
        capture_output=True, text=True, timeout=180, cwd="/root")
    o["skills_seen"] = (r.stdout or r.stderr)[:1200]
    return o


@app.local_entrypoint()
def main():
    for k, v in probe.remote().items():
        print(f"{k}:\n  {v}\n" if len(str(v)) > 60 else f"{k}: {v}")
