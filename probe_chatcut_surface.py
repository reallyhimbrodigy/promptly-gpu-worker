#!/usr/bin/env python3
"""EVERY tool ChatCut exposes, from tools/list — not from their docs.

Three questions, answered by CALLING the surface:
  1. does any tool return AUDIO in any form?
  2. does any tool return MOTION — a segment, a GIF, a sequence?
  3. is there a help/capability surface to ask directly?
"""
import json
import modal

app = modal.App("promptly-cc-surface")
image = (modal.Image.debian_slim(python_version="3.11")
         .add_local_file("chatcut_reference.py", "/root/chatcut_reference.py"))
TOK = modal.Dict.from_name("chatcut-tokens", create_if_missing=True)


@app.function(image=image, timeout=900,
              secrets=[modal.Secret.from_name("chatcut-oauth-planner")])
def surface():
    import chatcut_reference as cr
    tok = cr.access_token(TOK, key=cr.PLANNER_KEY)
    r = cr.rpc(tok, "tools/list", {})
    tools = ((r or {}).get("result") or {}).get("tools") or []
    out = []
    for t in tools:
        out.append({"name": t.get("name"),
                    "desc": (t.get("description") or ""),
                    "outputSchema": t.get("outputSchema"),
                    "inputSchema": t.get("inputSchema"),
                    "annotations": t.get("annotations")})
    return {"n": len(tools), "tools": out,
            "server": ((r or {}).get("result") or {}).get("serverInfo")}


@app.local_entrypoint()
def main():
    d = surface.remote()
    json.dump(d, open("/tmp/bs/cc_tools.json", "w"), indent=1)
    print("TOOLS: %d" % d["n"])
    for t in d["tools"]:
        print("  %s" % t["name"])
