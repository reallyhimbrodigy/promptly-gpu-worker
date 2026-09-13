#!/usr/bin/env python3
"""Obtain a ChatCut refresh token for headless containers. ONE human click.

WHY THIS EXISTS AND WHY IT IS NOT A CREDENTIAL GRAB. The Modal container has no
browser and no interactive session, so it cannot complete an OAuth consent. It
needs a REFRESH TOKEN obtained once, by the account owner, deliberately.

MEASURED FROM THE SERVER'S OWN DISCOVERY DOCUMENT, not assumed:

    grant_types_supported            ['authorization_code', 'refresh_token']
    code_challenge_methods_supported ['S256']
    registration_endpoint            /auth/mcp/register   (RFC 7591, open)
    client_credentials supported     FALSE

That last line is the architecture: there is NO machine-to-machine grant, so a
backend cannot mint its own token. Consent is the only door, and `offline_access`
is what makes it survive past one session.

PUBLIC CLIENT + PKCE. Registration returns `token_endpoint_auth_method: none`,
so there is no client secret to protect — the code verifier is the proof. That
is the correct shape for a client whose code ships inside an image.

WHAT THIS SCRIPT NEVER DOES: read Claude Code's own session, the keychain, or
any stored credential. It runs the standard flow and the user approves it in
their own browser. The tokens it prints go into a Modal Secret, never a file in
the repo and never the image.
"""
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request

BASE = "https://api.chatcut.io"
DISCOVERY = f"{BASE}/.well-known/oauth-authorization-server"
REDIRECT_PORT = 8765
REDIRECT = f"http://127.0.0.1:{REDIRECT_PORT}/callback"


def _get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def _post(url, payload, form=False):
    if form:
        data = urllib.parse.urlencode(payload).encode()
        hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        data = json.dumps(payload).encode()
        hdrs = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:                           # noqa: PERF203
        raise SystemExit(f"{url} -> HTTP {e.code}: {e.read()[:300].decode()}")


class _Catch(http.server.BaseHTTPRequestHandler):
    code = None

    def do_GET(self):                                             # noqa: N802
        q = urllib.parse.urlparse(self.path).query
        params = dict(urllib.parse.parse_qsl(q))
        _Catch.code = params.get("code")
        body = (b"<h2>ChatCut connected.</h2><p>You can close this tab and "
                b"return to the terminal.</p>") if _Catch.code else \
               (b"<h2>No code returned.</h2><pre>" + q.encode() + b"</pre>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):                                    # noqa: A003
        pass


def main():
    meta = _get(DISCOVERY)
    for k in ("authorization_endpoint", "token_endpoint", "registration_endpoint"):
        if k not in meta:
            raise SystemExit(f"discovery is missing {k} — ABSENT, not assumed")
    if "client_credentials" in (meta.get("grant_types_supported") or []):
        print("NOTE: client_credentials now advertised — a backend grant may "
              "exist and this consent flow may no longer be necessary.")

    client = _post(meta["registration_endpoint"], {
        "client_name": "Promptly headless editor",
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": "openid profile email offline_access",
    })
    cid = client["client_id"]

    verifier = base64.urlsafe_b64encode(os.urandom(40)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(16)

    url = meta["authorization_endpoint"] + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT,
        # offline_access IS THE POINT. Without it there is no refresh token and
        # the container works once, then fails quietly the next day.
        "scope": "openid profile email offline_access",
        "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": f"{BASE}/api/external-mcp/mcp",
    })

    srv = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), _Catch)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print("\nOpen this once and approve:\n")
    print("  " + url + "\n")
    print(f"Listening on {REDIRECT} ...")
    try:
        while _Catch.code is None:
            pass
    except KeyboardInterrupt:
        raise SystemExit("cancelled")
    srv.shutdown()

    tok = _post(meta["token_endpoint"], {
        "grant_type": "authorization_code", "code": _Catch.code,
        "redirect_uri": REDIRECT, "client_id": cid, "code_verifier": verifier,
        "resource": f"{BASE}/api/external-mcp/mcp",
    }, form=True)

    if not tok.get("refresh_token"):
        raise SystemExit(
            "NO REFRESH TOKEN RETURNED. The access token alone expires and the "
            "container would fail quietly on the second day. Check that "
            "offline_access was granted.")

    print("\nGot tokens. Put them in a Modal Secret — NOT in the repo:\n")
    print("  modal secret create chatcut-oauth \\")
    print(f"    CHATCUT_CLIENT_ID={cid} \\")
    print("    CHATCUT_REFRESH_TOKEN=<the value printed below>\n")
    print("refresh_token:", tok["refresh_token"])
    print("expires_in   :", tok.get("expires_in"))
    print("scope        :", tok.get("scope"))


if __name__ == "__main__":
    sys.exit(main())
