#!/usr/bin/env python3
"""Authorize one Strava account and store rotating tokens in private local state."""

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import secrets
import sys
from urllib.parse import parse_qs, urlencode, urlparse
import webbrowser

import requests

from private_data import read_json, write_json


AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"


def authorization_url(client_id, redirect_uri, state, read_private=False):
    scope = "read,activity:read_all" if read_private else "read,activity:read"
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": str(client_id),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": scope,
        "state": state,
    })


def exchange_code(client_id, client_secret, code):
    try:
        response = requests.post(TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        }, timeout=30, allow_redirects=False)
    except requests.RequestException:
        raise RuntimeError("Could not reach Strava") from None
    if response.status_code != 200:
        raise RuntimeError("Strava rejected the authorization exchange")
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError("Strava returned an invalid response") from None
    required = ("access_token", "refresh_token", "expires_at")
    if not isinstance(payload, dict) or not all(payload.get(key) for key in required):
        raise RuntimeError("Strava returned an incomplete authorization response")
    return payload


def persist_tokens(state_dir, client_id, payload):
    write_json(Path(state_dir) / "tokens.json", {
        "client_id": str(client_id),
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "expires_at": payload["expires_at"],
    })


def validate_scope(scope_text, read_private=False):
    granted = {part for part in scope_text.replace(",", " ").split() if part}
    required = "activity:read_all" if read_private else "activity:read"
    if required not in granted:
        raise RuntimeError(f"Strava did not grant the required {required} scope")


def wait_for_callback(host, port, expected_state, timeout=180):
    result = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            received_state = query.get("state", [""])[0]
            if not hmac.compare_digest(received_state, expected_state):
                self.send_response(400)
                message = "Authorization state did not match. You can close this window."
            elif query.get("error"):
                result["error"] = "Authorization was declined"
                self.send_response(400)
                message = "Authorization was declined. You can close this window."
            elif query.get("code"):
                result["code"] = query["code"][0]
                result["scope"] = query.get("scope", [""])[0]
                self.send_response(200)
                message = "Strava is connected. You can close this window."
            else:
                self.send_response(400)
                message = "The callback did not contain an authorization code."
            body = message.encode("utf-8")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    server = HTTPServer((host, port), CallbackHandler)
    server.timeout = timeout
    try:
        server.handle_request()
    finally:
        server.server_close()
    if result.get("error"):
        raise RuntimeError(result["error"])
    if not result.get("code"):
        raise RuntimeError("Authorization timed out")
    return result["code"], result["scope"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Connect a Strava account without copying tokens manually")
    parser.add_argument("--state-dir", type=Path, default=Path(".private"))
    parser.add_argument("--read-private", action="store_true",
                        help="also request access to activities whose visibility is Only You")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    credentials = read_json(args.state_dir / "credentials.json")
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not client_id or not client_secret:
        raise ValueError("Add client_id and client_secret to .private/credentials.json first")

    redirect_uri = f"http://localhost:{args.port}/callback"
    state = secrets.token_urlsafe(32)
    url = authorization_url(client_id, redirect_uri, state, args.read_private)
    print("Opening Strava authorization in your browser…")
    if not webbrowser.open(url):
        print("Open this URL in a browser on this computer:\n" + url)
    code, granted_scope = wait_for_callback("127.0.0.1", args.port, state)
    validate_scope(granted_scope, args.read_private)
    payload = exchange_code(client_id, client_secret, code)
    persist_tokens(args.state_dir, client_id, payload)
    print("Strava connected. Tokens were saved in the private state directory.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Authorization failed: {exc}", file=sys.stderr)
        sys.exit(1)
