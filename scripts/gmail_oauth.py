#!/usr/bin/env python3
"""Mint a Gmail API refresh token (local loopback OAuth flow, stdlib only).

Run this AFTER you've created a Desktop OAuth client in Google Cloud and put its
values in .env (GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET). It opens the Google consent
page in your browser, captures the redirect, and prints the refresh_token.

    python scripts/gmail_oauth.py

Then add the printed line to .env (and later to GitHub Actions secrets). Scope is
gmail.readonly — the scanner never modifies your mail.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Make the repo root importable so core.config loads .env for us.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import core.config  # noqa: E402,F401  (importing triggers .env auto-load)

# gmail.modify = read + drafts + labels (everything except permanent delete).
# Needed by the Outreach tab, which creates labeled drafts in the inbox.
SCOPE = "https://www.googleapis.com/auth/gmail.modify"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PORT = 8799
REDIRECT = f"http://localhost:{PORT}/"

_code_holder = {}


class _CB(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        _code_holder["code"] = (params.get("code") or [""])[0]
        _code_holder["error"] = (params.get("error") or [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        msg = "Authorization received — you can close this tab and return to the terminal."
        if _code_holder["error"]:
            msg = f"Error: {_code_holder['error']}"
        self.wfile.write(f"<html><body style='font:16px sans-serif;padding:40px'>{msg}</body></html>".encode())


def main() -> int:
    client_id = os.environ.get("GMAIL_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env first "
              "(from your Google Cloud Desktop OAuth client).", file=sys.stderr)
        return 2

    auth = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",   # -> returns a refresh_token
        "prompt": "consent",        # -> forces a fresh refresh_token every run
    })

    print("Opening the Google consent screen in your browser…")
    print("If it doesn't open, paste this URL:\n" + auth + "\n")
    httpd = HTTPServer(("localhost", PORT), _CB)
    webbrowser.open(auth)
    httpd.handle_request()  # serve exactly one redirect, then stop
    httpd.server_close()

    if _code_holder.get("error"):
        print("OAuth error:", _code_holder["error"], file=sys.stderr)
        return 1
    code = _code_holder.get("code")
    if not code:
        print("No authorization code received.", file=sys.stderr)
        return 1

    body = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
    }).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        tok = json.loads(resp.read().decode("utf-8"))

    refresh = tok.get("refresh_token")
    if not refresh:
        print("No refresh_token returned. Re-run; if it persists, revoke prior access at "
              "https://myaccount.google.com/permissions and try again.", file=sys.stderr)
        print("Raw response:", tok, file=sys.stderr)
        return 1

    print("\n" + "=" * 64)
    print("SUCCESS — add this line to your .env (and to Actions secrets):\n")
    print(f"GMAIL_REFRESH_TOKEN={refresh}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
