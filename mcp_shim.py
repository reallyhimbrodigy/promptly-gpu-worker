#!/usr/bin/env python3
"""A stdio MCP server in front of the hosted ChatCut MCP: the SAME tools, only
the ones this job may call, and NONE of the server's own instructions.

WHY. The tool block is the largest thing in the prefix after the watch —
59 ChatCut schemas, 182,903 bytes, for a run allowed to call nine — and
`--tools` provably leaves MCP definitions in the request (a proxied local run
with `--tools Bash` still sent 169 MCP schemas). The block is whatever the
server advertises, so this advertises less: `tools/list` is the upstream list
filtered to MCP_SHIM_ALLOW. `initialize` answers without the upstream's
`instructions` — the sentence that mandated a Skill-tool turn before the first
ChatCut call. And because a stdio server is started and initialised before the
CLI's first request, the block is the same on call 1 as on every call after,
which the hosted (HTTP) server was not: a proxied local run showed the tool
block growing 169 -> 289 between calls 1 and 2 as servers finished connecting.

Transport: newline-delimited JSON-RPC 2.0 on stdin/stdout (the MCP stdio
transport). Upstream: MCP over HTTP at MCP_SHIM_UPSTREAM with the bearer in
MCP_SHIM_TOKEN. Everything else — tools/call, ping — is forwarded verbatim.
"""
import json
import os
import sys
import urllib.request

UPSTREAM = os.environ.get("MCP_SHIM_UPSTREAM", "https://api.chatcut.io/api/external-mcp/mcp")
TOKEN = os.environ.get("MCP_SHIM_TOKEN", "")
ALLOW = [t for t in os.environ.get("MCP_SHIM_ALLOW", "").split(",") if t]
LOG = os.environ.get("MCP_SHIM_LOG", "")


def _log(line):
    if LOG:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def upstream(method, params, mid):
    req = urllib.request.Request(
        UPSTREAM, method="POST",
        data=json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                 "Authorization": "Bearer " + TOKEN, "x-chatcut-mcp-client": "claude_code",
                 "x-chatcut-mcp-surface": "embedded-preview"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read().decode("utf-8", "replace")
    # the hosted server may answer as SSE; take the first data: line that parses
    if body.lstrip().startswith("{"):
        return json.loads(body)
    for ln in body.splitlines():
        if ln.startswith("data:"):
            try:
                return json.loads(ln[5:].strip())
            except ValueError:
                continue
    raise RuntimeError("upstream returned no JSON-RPC body: %r" % body[:200])


HIDDEN_PROPS = {"json"}


def unwrap_json_arg(args):
    """If the ops arrived as ChatCut's `json` string, lift them into the real
    fields so the why-strip and the op log see them. -> (args, unwrapped)"""
    if not isinstance(args.get("json"), str):
        return args, False
    try:
        inner = json.loads(args["json"])
    except ValueError:
        return args, False
    if not isinstance(inner, dict):
        return args, False
    out = dict(args); del out["json"]
    for k, v in inner.items():
        out.setdefault(k, v)
    return out, True


def slim_tool(t):
    """A tool definition cut to NAME AND ARGUMENTS. PURE.

    Zac, 2026-09-17: "descriptions cut to name and arguments — the paragraph
    already carries the add-shape; the MCP prose is redundant." Keeps the
    name, every property with its type/enum/items type and the required list;
    drops the tool description and every property description. Measured on
    the nine ChatCut schemas: 34,637 -> a few thousand bytes.
    """
    def _prop(p):
        if not isinstance(p, dict):
            return {}
        q = {}
        for k in ("type", "enum", "const", "format", "minimum", "maximum", "minItems", "maxItems"):
            if k in p:
                q[k] = p[k]
        if "items" in p:
            q["items"] = _prop(p["items"]) if isinstance(p["items"], dict) else p["items"]
        if isinstance(p.get("properties"), dict):
            q["properties"] = {k: _prop(v) for k, v in p["properties"].items()}
            if p.get("required"):
                q["required"] = p["required"]
        if isinstance(p.get("anyOf"), list):
            q["anyOf"] = [_prop(x) for x in p["anyOf"]]
        if isinstance(p.get("oneOf"), list):
            q["oneOf"] = [_prop(x) for x in p["oneOf"]]
        return q or {"type": p.get("type", "string")}
    schema = t.get("inputSchema") or t.get("input_schema") or {}
    # `json` is ChatCut's stringified-arguments escape hatch. Advertised, the
    # agent used it (h-th-think0: every edit_item came as {"json": "..."}),
    # its ops bypassed the why-strip and the harness's op reader, and ChatCut
    # refused the call for the `why` inside. Not offered.
    out = {"name": t.get("name"), "description": t.get("name", "").replace("_", " "),
           "inputSchema": {"type": "object",
                           "properties": {k: _prop(v) for k, v in (schema.get("properties") or {}).items() if k not in HIDDEN_PROPS}}}
    if schema.get("required"):
        out["inputSchema"]["required"] = schema["required"]
    return out


def handle(msg):
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        # NO `instructions`: the upstream's mandate a Skill turn; the guide the
        # job needs is in the prefix already.
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": params.get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "chatcut-shim", "version": "1"}}}
    if method == "tools/list":
        up = upstream("tools/list", {}, mid)
        tools = (up.get("result") or {}).get("tools") or []
        kept = [slim_tool(t) for t in tools if not ALLOW or t.get("name") in ALLOW]
        _log("tools/list upstream=%d kept=%d missing=%s" % (
            len(tools), len(kept), sorted(set(ALLOW) - {t.get("name") for t in tools})))
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": kept}}
    if method == "tools/call":
        name = (params or {}).get("name")
        if ALLOW and name not in ALLOW:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "tool %r is not offered on this surface" % name}}
        # THE WHY RIDES INSIDE THE OPS (Zac, 2026-09-17). Each add/update/delete
        # may carry a `why`; ChatCut's schema does not know it, so it is taken
        # off here, logged beside the op's position, and the clean op goes up.
        # Every call is logged with what it asked for: an inspect_item or a
        # preview_timeline at rewatch time is the harness's omission, not the
        # agent's fault, and the log is how that is seen.
        args = dict((params or {}).get("arguments") or {})
        whys = []
        args, unwrapped = unwrap_json_arg(args) if name == "edit_item" else (args, False)
        if name == "edit_item":
            for kind in ("adds", "updates", "deletes"):
                ops = args.get(kind)
                if isinstance(ops, list):
                    cleaned = []
                    for i, op in enumerate(ops):
                        if isinstance(op, dict) and "why" in op:
                            op = dict(op); whys.append({"op": "%s[%d]" % (kind, i), "why": str(op.pop("why"))[:400]})
                        cleaned.append(op)
                    args[kind] = cleaned
            if "why" in args:
                whys.append({"op": "call", "why": str(args.pop("why"))[:400]})
        fwd = dict(params or {}); fwd["arguments"] = args
        up = upstream("tools/call", fwd, mid)
        up["id"] = mid
        try:
            echo = json.dumps(up.get("result") or {})[:20000]
            import re as _re
            ids = _re.findall(r'\\?"id\\?":\s*\\?"([0-9a-f-]{6,})', echo)
            _log(json.dumps({"call": name, "mid": mid, "asked": {k: (v if k != "arguments" else {kk: (vv if kk in ("sourceTimesMs", "sourceFrameCount", "itemId", "assetId", "viewerFrames", "viewerFrameCount", "fromFrame", "toFrame") else "…") for kk, vv in (v or {}).items()}) for k, v in fwd.items()},
                             "ops": {k: len(args.get(k) or []) for k in ("adds", "updates", "deletes") if isinstance(args.get(k), list)},
                             "whys": whys, "echo_ids": ids[:40], "unwrapped_json": unwrapped,
                             "is_error": bool(up.get("error")) or bool((up.get("result") or {}).get("isError"))}))
        except Exception as _le:                                  # noqa: BLE001
            _log(json.dumps({"call": name, "mid": mid, "log_error": str(_le)[:120]}))
        return up
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if mid is None:                       # a notification: nothing to answer
        return None
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "unsupported: %s" % method}}


PROXY_VARS = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")


def scrub_proxy_env(environ):
    """Drop the proxy variables the CLI hands its children. -> names removed.

    The job routes the CLI through a transparent recording proxy
    (HTTPS_PROXY + a throwaway CA). This shim is spawned by the CLI with
    that environment, urllib honours https_proxy, and its ChatCut calls were
    tunnelled to a proxy that only speaks to api.anthropic.com — refused, so
    the ping of 2026-09-17 carried 5 tools instead of 13. The shim talks to
    ChatCut directly, always.
    """
    removed = [k for k in PROXY_VARS if k in environ]
    for k in removed:
        del environ[k]
    return removed


def main():
    scrub_proxy_env(os.environ)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        try:
            out = handle(msg)
        except Exception as e:                                    # noqa: BLE001
            out = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32000, "message": "%s: %s" % (type(e).__name__, str(e)[:300])}}
        if out is not None:
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
