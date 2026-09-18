#!/usr/bin/env python3
"""A recording proxy in front of api.anthropic.com. THE INSTRUMENT FOR ONE
QUESTION: what, byte for byte, changes in the cached prefix between two calls.

Nothing on disk holds the request the CLI sends — stream-json reports usage,
not bytes. So the CLI is pointed at this (ANTHROPIC_BASE_URL) and every
/v1/messages request is fingerprinted segment by segment before it is
forwarded unchanged: sha256 and size of the `tools` JSON, of `system`, and of
every message's content. A row per call goes to FINGERPRINTS (jsonl) with the
first segment that differs from the previous call and a bounded unified diff
of that segment's JSON — so "call 2 read 0" comes with the bytes that moved.
The first request body is kept whole at FIRST_BODY.

Streaming is passed through as it arrives; headers are forwarded as-is
(x-api-key included), never logged.
"""
import difflib
import hashlib
import http.client
import http.server
import json
import re
import os
import sys
import threading
import time

UPSTREAM = os.environ.get("API_PROXY_UPSTREAM", "api.anthropic.com")
FINGERPRINTS = os.environ.get("API_PROXY_FINGERPRINTS", "/work/prefix_calls.jsonl")
FIRST_BODY = os.environ.get("API_PROXY_FIRST_BODY", "/work/req_first.json")
# THE UPSTREAM LEG, TRACED. The first container run through this proxy
# (h-th-think0, 2026-09-17) recorded the request and then nothing for 120s:
# no stream event, no result, and no way to say whether upstream answered,
# with what status, or how long the first byte took. Every leg writes here.
TRACE = os.environ.get("API_PROXY_TRACE", "/work/proxy_trace.jsonl")


class V4HTTPSConnection(http.client.HTTPSConnection):
    """HTTPS upstream over IPv4 ONLY, with a bounded connect.

    http.client connects to each resolved address IN TURN, each with the full
    socket timeout — a blackholed AAAA record costs the whole timeout before
    the A record is tried. Node's fetch races families and never sees it.
    Selected by CONNECTION below once the egress probe measured the container.
    """
    CONNECT_TIMEOUT_S = 10

    def connect(self):
        import socket
        infos = socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_STREAM)
        if not infos:
            raise OSError("no IPv4 address for %s" % self.host)
        last = None
        for af, st, pr, _cn, sa in infos:
            sock = socket.socket(af, st, pr)
            try:
                sock.settimeout(self.CONNECT_TIMEOUT_S)
                sock.connect(sa)
                sock.settimeout(self.timeout)
                self.sock = sock
                last = None
                break
            except OSError as e:
                last = e
                sock.close()
        if last is not None:
            raise last
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


# the upstream connection class, resolved by name so a check can drive the
# relay against a canned response without touching http.client itself
CONNECTION = http.client.HTTPSConnection

# ── THE WATCH-END BREAKPOINT (Zac, ruling 2, 2026-09-18) ────────────────────
# The CLI marks only its own last two messages, so a keep-warm ping never
# leaves a cache entry at the end of the shared watch and a job's first call
# reads 12.6k of 235k (`previous_message_not_found`). No CLI flag places one.
# So the proxy does, on every /v1/messages call, ping and job alike: a
# cache_control with ttl 1h on the last content block of the message just
# before this run's own first message (found by RUN_FIRST_TEXT). The API's
# rules, honoured here and to be verified on the wire: at most four
# breakpoints per request (the CLI's second-to-last message marker is dropped
# to make room), and 1h entries must precede 5-minute ones (the CLI's system
# markers are raised to 1h; the last-message marker stays 5m, after them).
RUN_FIRST_TEXT = os.environ.get("API_PROXY_RUN_FIRST_TEXT", "")
MAX_BREAKPOINTS = 4
# THE THINKING BUDGET, PLACED ON THE WIRE (Zac, 2026-09-18: "MAX_THINKING_TOKENS=2000,
# recorded on the wire"). Measured: the CLI sends thinking {type: adaptive} with
# NO budget for any MAX_THINKING_TOKENS > 0 (3000, 2000, 1024 all alike), and
# {type: disabled} for 0. A bounded arm therefore exists only if the proxy
# writes it: thinking {type: enabled, budget_tokens: N}. Recorded per call in
# the fingerprint's request_fields, so the arm is read from the wire.
THINKING_BUDGET = int(os.environ.get("API_PROXY_THINKING_BUDGET", "0") or 0)


def apply_thinking_budget(body, budget):
    """-> (body, note). A copy with thinking {enabled, budget_tokens} when a
    budget is set and the request did not disable thinking; otherwise untouched."""
    if not budget:
        return body, {"rewritten": False, "why": "no budget"}
    th = body.get("thinking")
    if isinstance(th, dict) and th.get("type") == "disabled":
        return body, {"rewritten": False, "why": "thinking disabled on the wire; a budget does not apply"}
    b = json.loads(json.dumps(body))
    budget = max(1024, int(budget))
    mt = b.get("max_tokens")
    if isinstance(mt, int) and mt <= budget:
        b["max_tokens"] = budget + 4096
    b["thinking"] = {"type": "enabled", "budget_tokens": budget}
    return b, {"rewritten": True, "budget_tokens": budget, "was": th}


def inject_watch_breakpoint(body, run_first_text):
    """-> (body, note). PURE on its input (a deep copy is returned)."""
    if not run_first_text or not isinstance(body.get("messages"), list):
        return body, {"injected": False, "why": "no run_first_text or no messages"}
    b = json.loads(json.dumps(body))
    msgs = b["messages"]
    # THE RUN'S FIRST MESSAGE: the LAST user-role message carrying the text.
    # The first ping marked message 0 — the CLI's own system-role message at
    # index 1 contains "ping" as a substring ("skipping"), and a first-match
    # over every role took it (measured 2026-09-18: 1h entry covered 55k of
    # 226k). User role only, last match, so a watch that quotes the sentinel
    # cannot steal it either.
    first = None
    for i, m in enumerate(msgs):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        texts = [x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"] if isinstance(c, list) else [str(c or "")]
        if any(run_first_text in t for t in texts):
            first = i
    if first is None or first == 0:
        return body, {"injected": False, "why": "run_first_text not found in any message" if first is None else "run's first message is message 0 — no watch before it"}
    idx = first - 1
    tail = msgs[idx].get("content")
    if not isinstance(tail, list) or not tail or not isinstance(tail[-1], dict):
        return body, {"injected": False, "why": "message %d has no block to mark" % idx}
    # the CLI's message markers: keep the LAST, drop the rest (room for ours)
    marked = [i for i, m in enumerate(msgs) if isinstance(m.get("content"), list)
              and any(isinstance(x, dict) and x.get("cache_control") for x in m["content"])]
    dropped = []
    for i in marked[:-1]:
        if i == idx:
            continue
        for x in msgs[i]["content"]:
            if isinstance(x, dict) and x.get("cache_control"):
                x.pop("cache_control", None)
                dropped.append(i)
    # 1h must precede 5m: every system marker becomes 1h
    raised = 0
    if isinstance(b.get("system"), list):
        for x in b["system"]:
            if isinstance(x, dict) and x.get("cache_control"):
                x["cache_control"] = {**x["cache_control"], "ttl": "1h"}
                raised += 1
    tail[-1]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
    n_bp = raised + sum(1 for m in msgs if isinstance(m.get("content"), list)
                        for x in m["content"] if isinstance(x, dict) and x.get("cache_control"))
    if isinstance(b.get("tools"), list):
        n_bp += sum(1 for t in b["tools"] if isinstance(t, dict) and t.get("cache_control"))
    if n_bp > MAX_BREAKPOINTS:
        return body, {"injected": False, "why": "would carry %d breakpoints (cap %d)" % (n_bp, MAX_BREAKPOINTS)}
    return b, {"injected": True, "watch_end_message": idx, "run_first_message": first, "dropped_cli_markers": dropped,
               "system_markers_raised_to_1h": raised, "breakpoints": n_bp}


def _trace(row):
    try:
        with open(TRACE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:                                             # noqa: BLE001
        pass
_LOCK = threading.Lock()
_STATE = {"n": 0, "prev": None}


def _strip_cc(obj):
    """cache_control markers move from call to call and the API's prefix hash
    ignores them; measured 2026-09-17: three MCP-less --resume calls showed
    identical bytes everywhere except where the marker sat."""
    if isinstance(obj, dict):
        return {k: _strip_cc(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cc(x) for x in obj]
    return obj


def _sha(obj):
    b = json.dumps(_strip_cc(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()[:16], len(b)


def _content_shape(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return 1, ["text"]
    return len(c or []), [str((b or {}).get("type")) for b in (c or [])]


def _is_billing(block):
    return isinstance(block, dict) and str(block.get("text", "")).startswith("x-anthropic-billing-header:")


def fingerprint(body):
    """One request body -> its segment fingerprints. PURE."""
    tools = body.get("tools") or []
    system = body.get("system")
    msgs = body.get("messages") or []
    # THE BILLING HEADER IS NOT PREFIX. system[0] is "x-anthropic-billing-header:
    # ... cc_prev_req=<last request id>" — new bytes every call, and the API
    # reads 235k cached tokens straight past it (h-th-think0 calls 2-3). Hashed,
    # it made every call read PREFIX DIVERGED at "system" and hid the real
    # divergence (message 0, call 4). Kept out of the hash, counted beside it.
    sys_hashed = [b for b in system if not _is_billing(b)] if isinstance(system, list) else system
    row = {"model": body.get("model"),
           "tools": {"n": len(tools), "sha": _sha(tools)[0], "bytes": _sha(tools)[1],
                     "names": [t.get("name") for t in tools][:80]},
           "system": {"sha": _sha(sys_hashed)[0], "bytes": _sha(sys_hashed)[1],
                      "blocks": (len(system) if isinstance(system, list) else 1),
                      "billing_header_blocks": (sum(1 for b in system if _is_billing(b)) if isinstance(system, list) else 0),
                      # BLOCK BY BLOCK, so a cross-run miss names the block (the ping and the job
                      # differed by 8 bytes of system on 2026-09-18 and the whole watch rewrote)
                      "block_shas": [(_sha(b)[0], _sha(b)[1], (b.get("text", "")[:60] if isinstance(b, dict) else ""))
                                     for b in (sys_hashed if isinstance(sys_hashed, list) else [sys_hashed])]},
           "messages": []}
    # WHERE THE CLI PUT ITS BREAKPOINTS. The API caches at cache_control
    # markers and looks back ~20 blocks from each; which message carries a
    # marker decides what a keep-warm ping can warm and what a job's first
    # call can read. Recorded per request: tools / system / message:i.
    bps = []
    for t in tools:
        if isinstance(t, dict) and t.get("cache_control"):
            bps.append("tools"); break
    if isinstance(system, list) and any(isinstance(b, dict) and b.get("cache_control") for b in system):
        bps.append("system")
    for i, m in enumerate(msgs):
        sha, nb = _sha({"role": m.get("role"), "content": m.get("content")})
        n_blocks, kinds = _content_shape(m)
        c = m.get("content")
        if isinstance(c, list) and any(isinstance(b, dict) and b.get("cache_control") for b in c):
            bps.append("message:%d" % i)
        row["messages"].append({"role": m.get("role"), "sha": sha, "bytes": nb,
                                "blocks": n_blocks, "kinds": kinds[:24]})
    row["cache_control_at"] = bps
    # WHAT WAS SENT BESIDES THE PREFIX, per call (not hashed): the thinking arm
    # is read from the wire, never from the env that asked for it — the
    # "thinking removed" run streamed a thinking block (h-th-think0, 2026-09-17).
    row["request_fields"] = {"thinking": body.get("thinking"), "output_config": body.get("output_config"),
                             "max_tokens": body.get("max_tokens"), "stream": body.get("stream")}
    return row


def _seg_text(body, seg):
    if seg == "tools":
        return json.dumps(_strip_cc(body.get("tools") or []), indent=1, sort_keys=True, ensure_ascii=False)
    if seg == "system":
        return json.dumps(_strip_cc(body.get("system")), indent=1, sort_keys=True, ensure_ascii=False)
    i = int(seg.split(":")[1])
    m = (body.get("messages") or [])[i]
    return json.dumps(_strip_cc({"role": m.get("role"), "content": m.get("content")}), indent=1,
                      sort_keys=True, ensure_ascii=False)


def diff_prefix(prev_body, prev_fp, body, fp, max_lines=60):
    """The FIRST segment that differs between two requests, with its diff. PURE.

    Segments are compared in prefix order — tools, system, message 0, 1, ... —
    because that is the order the cache hashes them: the first difference is
    where every later byte stops being a hit.
    """
    if prev_fp is None:
        return {"state": "FIRST CALL", "first_diff": None}
    # the first differing MESSAGE is computed regardless, so a system-level
    # difference cannot hide a rewritten message behind it
    first_msg = next((i for i, (a, b) in enumerate(zip(prev_fp["messages"], fp["messages"])) if a["sha"] != b["sha"]), None)
    if prev_fp["tools"]["sha"] != fp["tools"]["sha"]:
        seg = "tools"
    elif prev_fp["system"]["sha"] != fp["system"]["sha"]:
        seg = "system"
    else:
        seg = None
        if first_msg is not None:
            seg = "message:%d" % first_msg
        if seg is None and len(fp["messages"]) > len(prev_fp["messages"]):
            return {"state": "PREFIX IDENTICAL", "first_diff": None,
                    "shared_messages": len(prev_fp["messages"]),
                    "appended": len(fp["messages"]) - len(prev_fp["messages"])}
        if seg is None:
            return {"state": "IDENTICAL REQUEST", "first_diff": None}
    a_txt = _seg_text(prev_body, seg).splitlines()
    b_txt = _seg_text(body, seg).splitlines()
    # image data is thousands of base64 chars on one line: shorten for the diff
    def _short(lines):
        return [(ln[:160] + "…(%d chars)" % len(ln)) if len(ln) > 200 else ln for ln in lines]
    ud = list(difflib.unified_diff(_short(a_txt), _short(b_txt), "previous", "this", lineterm="", n=1))
    return {"state": "PREFIX DIVERGED", "first_diff": seg, "first_message_diff": first_msg,
            "shared_messages_before": (int(seg.split(":")[1]) if seg.startswith("message") else 0),
            "diff_lines": len(ud), "diff": ud[:max_lines]}


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):                                    # quiet
        pass

    def do_POST(self):
        # PHASES, each a row: the proxied ping in the container wrote NO trace
        # row in 120s, so the stall is before the upstream leg's finally —
        # this says whether the body ever fully arrived from the CLI.
        t_in = time.time()
        n = int(self.headers.get("Content-Length") or 0)
        _trace({"phase": "received", "t": round(t_in, 3), "path": self.path, "content_length": n,
                "transfer_encoding": self.headers.get("Transfer-Encoding"), "expect": self.headers.get("Expect"),
                "request_version": self.request_version})
        raw = self.rfile.read(n) if n else b""
        _trace({"phase": "body_read", "bytes": len(raw), "s": round(time.time() - t_in, 3)})
        # the EXACT messages path: /v1/messages/count_tokens also starts with it
        # and once stood in as "the first body" (local, 2026-09-17)
        if self.path.split("?")[0] == "/v1/messages":
            try:
                body = json.loads(raw.decode("utf-8"))
                body, inj = inject_watch_breakpoint(body, RUN_FIRST_TEXT)
                body, thk = apply_thinking_budget(body, THINKING_BUDGET)
                if inj.get("injected") or thk.get("rewritten"):
                    raw = json.dumps(body).encode("utf-8")
                _trace({"phase": "breakpoint", **inj})
                _trace({"phase": "thinking", **thk})
                fp = fingerprint(body)
                fp["breakpoint"] = inj
                with _LOCK:
                    _STATE["n"] += 1
                    k = _STATE["n"]
                    prev = _STATE["prev"]
                    d = diff_prefix(prev[0] if prev else None, prev[1] if prev else None, body, fp)
                    _STATE["prev"] = (body, fp)
                    row = {"n": k, "t": round(time.time(), 3), "fp": fp, "vs_prev": d}
                    with open(FINGERPRINTS, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row) + "\n")
                    if k == 1:
                        with open(FIRST_BODY, "w", encoding="utf-8") as fh:
                            json.dump(body, fh)
            except Exception as e:                                # noqa: BLE001
                with open(FINGERPRINTS, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"n": None, "error": "%s: %s" % (type(e).__name__, str(e)[:200])}) + "\n")
        self._forward("POST", raw)

    def do_GET(self):
        self._forward("GET", b"")

    def _forward(self, method, raw):
        # accept-encoding is dropped so upstream answers in identity: the
        # relay then carries plain SSE bytes and no content-encoding header
        # has to be forwarded across the chunk boundary.
        hdrs = {k: v for k, v in self.headers.items()
                if k.lower() not in ("host", "content-length", "transfer-encoding", "connection", "accept-encoding")}
        hdrs["Host"] = UPSTREAM
        t0 = time.time()
        row = {"t": round(t0, 3), "method": method, "path": self.path, "req_bytes": len(raw),
               "req_headers": {k: (v if k.lower() not in ("x-api-key", "authorization") else "<redacted %d>" % len(v))
                               for k, v in self.headers.items()}}
        conn = CONNECTION(UPSTREAM, timeout=3600)
        relayed = 0
        try:
            conn.connect()
            _trace({"phase": "upstream_connected", "s": round(time.time() - t0, 3)})
            conn.request(method, self.path, body=raw if raw else None, headers={**hdrs, "Content-Length": str(len(raw))} if raw else hdrs)
            row["sent_s"] = round(time.time() - t0, 3)
            _trace({"phase": "request_sent", "s": row["sent_s"], "bytes": len(raw)})
            resp = conn.getresponse()
            _trace({"phase": "response_headers", "status": resp.status, "s": round(time.time() - t0, 3)})
            row["status"] = resp.status
            row["ttfb_s"] = round(time.time() - t0, 3)
            row["resp_headers"] = {k: v for k, v in resp.getheaders() if k.lower() in ("content-type", "content-encoding", "request-id", "anthropic-ratelimit-requests-remaining", "retry-after")}
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() in ("transfer-encoding", "content-length", "connection"):
                    continue
                self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            self.wfile.flush()
            head = b""
            nchunks = 0
            while True:
                # read1: whatever has ARRIVED, never blocking to fill 4096 —
                # an SSE stream's events must reach the CLI as they come.
                chunk = resp.read1(65536)
                if not chunk:
                    _trace({"phase": "upstream_eof", "s": round(time.time() - t0, 3), "chunks": nchunks, "relayed": relayed})
                    break
                nchunks += 1
                if nchunks == 1:
                    _trace({"phase": "first_chunk", "s": round(time.time() - t0, 3), "bytes": len(chunk), "head": chunk[:400].decode("utf-8", "replace")})
                if len(head) < 2000:
                    head += chunk[:2000 - len(head)]
                relayed += len(chunk)
                self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n")
                self.wfile.flush()
                if nchunks in (2, 5, 20, 100):
                    _trace({"phase": "relaying", "s": round(time.time() - t0, 3), "chunks": nchunks, "relayed": relayed,
                            "head": head.decode("utf-8", "replace") if nchunks == 20 else None})
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
            _trace({"phase": "relay_closed", "s": round(time.time() - t0, 3)})
            row["relayed_bytes"] = relayed
            row["head"] = head.decode("utf-8", "replace")
            row["done_s"] = round(time.time() - t0, 3)
            # the API's own word on the cache: message_start carries
            # diagnostics.cache_miss_reason (h-th-think0 read 12,643 of 235k
            # after a warm ping: "previous_message_not_found")
            m = re.search(r'"cache_miss_reason":(\{[^}]*\})', row["head"])
            if m:
                try:
                    row["cache_miss_reason"] = json.loads(m.group(1))
                except Exception:                                 # noqa: BLE001
                    row["cache_miss_reason"] = m.group(1)
        except Exception as e:                                    # noqa: BLE001
            row["error"] = "%s: %s" % (type(e).__name__, str(e)[:300])
            row["relayed_bytes"] = relayed
            row["failed_s"] = round(time.time() - t0, 3)
            try:
                self.send_response(502)
                self.end_headers()
                self.wfile.write(("proxy error: %s" % e).encode())
            except Exception:                                     # noqa: BLE001
                pass
        finally:
            conn.close()
            _trace(row)


def serve(port=0):
    """Start the proxy on a thread. -> port."""
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


# ── THE TRANSPARENT MODE ─────────────────────────────────────────────────────
# Measured in the container 2026-09-17: pointed at http://127.0.0.1 through
# ANTHROPIC_BASE_URL the CLI's request differs from its direct one (a "ping"
# that answers 'pong' in 19s direct thinks for 100s+ through the proxy, 3 of
# 3), while the same variable naming the real https endpoint behaves like
# direct. The instrument must not be visible to the CLI: it stays configured
# for api.anthropic.com and is handed an HTTPS proxy (CONNECT) whose
# certificate for that name only this process trusts (NODE_EXTRA_CA_CERTS).

def ensure_certs(cert_dir, host=UPSTREAM):
    """A throwaway CA and a leaf for `host`, generated with openssl. -> (ca_pem, cert_pem, key_pem)"""
    import subprocess
    os.makedirs(cert_dir, exist_ok=True)
    ca_key, ca_pem = os.path.join(cert_dir, "ca.key"), os.path.join(cert_dir, "ca.pem")
    key, csr, crt = os.path.join(cert_dir, "leaf.key"), os.path.join(cert_dir, "leaf.csr"), os.path.join(cert_dir, "leaf.pem")
    ext = os.path.join(cert_dir, "san.cnf")
    if os.path.exists(ca_pem) and os.path.exists(crt) and os.path.exists(key):
        return ca_pem, crt, key
    def run(*a):
        subprocess.run(list(a), check=True, capture_output=True, text=True)
    # a CA that OpenSSL 3 verifies: basicConstraints CA:true and keyCertSign
    # (Node accepted the bare one; Python's ssl refused it — the smoke found it)
    ca_cnf = os.path.join(cert_dir, "ca.cnf")
    with open(ca_cnf, "w") as fh:
        fh.write("[req]\ndistinguished_name=dn\nx509_extensions=v3_ca\nprompt=no\n[dn]\nCN=api_proxy throwaway CA\n"
                 "[v3_ca]\nbasicConstraints=critical,CA:true\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\n")
    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", ca_key, "-out", ca_pem,
        "-days", "3650", "-config", ca_cnf)
    run("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", csr, "-subj", "/CN=%s" % host)
    with open(ext, "w") as fh:
        fh.write("subjectAltName=DNS:%s\nextendedKeyUsage=serverAuth\n" % host)
    run("openssl", "x509", "-req", "-in", csr, "-CA", ca_pem, "-CAkey", ca_key, "-CAcreateserial",
        "-out", crt, "-days", "3650", "-extfile", ext)
    return ca_pem, crt, key


class M(H):
    """H plus CONNECT: terminate TLS as `UPSTREAM`, then serve the plaintext
    requests through the same recording handler."""
    ssl_context = None

    def do_CONNECT(self):
        host = self.path.split(":")[0]
        if host != UPSTREAM or self.ssl_context is None:
            _trace({"phase": "connect_refused", "target": self.path})
            self.send_response(502)
            self.end_headers()
            return
        self.send_response(200, "Connection established")
        self.end_headers()
        self.wfile.flush()
        _trace({"phase": "connect", "target": self.path})
        try:
            tls = self.ssl_context.wrap_socket(self.connection, server_side=True)
        except Exception as e:                                    # noqa: BLE001
            _trace({"phase": "tls_failed", "error": "%s: %s" % (type(e).__name__, str(e)[:200])})
            return
        self.connection = tls
        self.rfile = tls.makefile("rb", self.rbufsize)
        self.wfile = tls.makefile("wb", 0)
        self.close_connection = False
        while not self.close_connection:
            self.handle_one_request()


def serve_mitm(port=0, cert_dir="/work/mitm"):
    """Start the transparent proxy. -> (port, ca_pem). Hand the CLI
    HTTPS_PROXY=http://127.0.0.1:<port> and NODE_EXTRA_CA_CERTS=<ca_pem>."""
    import ssl
    ca_pem, crt, key = ensure_certs(cert_dir)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    handler = type("M_bound", (M,), {"ssl_context": ctx})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1], ca_pem


def mitm_env(port, ca_pem):
    """The two variables that route the CLI through the transparent proxy."""
    # NO_PROXY keeps every other host direct: the CLI's ChatCut shim (its
    # own scrub is the belt; this is the braces) and anything on localhost.
    return {"HTTPS_PROXY": "http://127.0.0.1:%d" % port, "https_proxy": "http://127.0.0.1:%d" % port,
            "NO_PROXY": "api.chatcut.io,localhost,127.0.0.1", "no_proxy": "api.chatcut.io,localhost,127.0.0.1",
            "NODE_EXTRA_CA_CERTS": ca_pem}


if __name__ == "__main__":
    p = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
    print("api_proxy on http://127.0.0.1:%d -> https://%s  fingerprints=%s" % (p, UPSTREAM, FINGERPRINTS), flush=True)
    while True:
        time.sleep(3600)
