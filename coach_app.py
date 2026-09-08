#!/usr/bin/env python3
"""Local-only browser interface for onboarding and marathon-plan drafting."""

import argparse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import secrets
import sys
from urllib.parse import parse_qs, urlparse
import webbrowser
from zoneinfo import ZoneInfo

from authorize_strava import authorization_url, exchange_code, persist_tokens, validate_scope
from plan_generator import analyse_training, draft_marathon_plan, race_candidates
from private_data import read_json, write_json, store_keychain_secret, read_keychain_secret
from race_catalog import public_catalog
from strava_coach import credentials, fetch_runs_since, get_token
from training_plan import load_plan


MAX_BODY = 1024 * 1024
ASSETS = Path(__file__).with_name("web")


class CoachServer(ThreadingHTTPServer):
    def __init__(self, address, handler, state_dir):
        super().__init__(address, handler)
        self.state_dir = Path(state_dir)
        self.app_token = secrets.token_urlsafe(32)
        self.oauth = None


class Handler(BaseHTTPRequestHandler):
    server: CoachServer

    def log_message(self, _format, *_args):
        pass

    def _json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _asset(self, name, mime):
        path = ASSETS / name
        if not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        if name == "index.html":
            body = body.replace(b"__APP_TOKEN__", self.server.app_token.encode("ascii"))
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _payload(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid request") from None
        if not 0 < length <= MAX_BODY:
            raise ValueError("Invalid request size")
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Invalid JSON") from None
        if not isinstance(value, dict):
            raise ValueError("Request must be an object")
        return value

    def _authorized(self):
        supplied = self.headers.get("X-Coach-Token", "")
        return hmac.compare_digest(supplied, self.server.app_token)

    def _local_request(self):
        host = self.headers.get("Host", "").split(":", 1)[0].lower()
        if host not in {"localhost", "127.0.0.1"}:
            return False
        origin = self.headers.get("Origin")
        return not origin or urlparse(origin).hostname in {"localhost", "127.0.0.1"}

    def do_GET(self):
        if not self._local_request():
            self.send_error(421)
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._asset("index.html", "text/html; charset=utf-8")
        elif parsed.path == "/styles.css":
            self._asset("styles.css", "text/css; charset=utf-8")
        elif parsed.path == "/app.js":
            self._asset("app.js", "text/javascript; charset=utf-8")
        elif parsed.path == "/api/catalog":
            self._json({"races": public_catalog()})
        elif parsed.path == "/api/status":
            self._json({"strava_connected": (self.server.state_dir / "tokens.json").is_file(),
                        "plan_saved": (self.server.state_dir / "coach_config.json").is_file()})
        elif parsed.path == "/oauth/callback":
            self._oauth_callback(parse_qs(parsed.query))
        else:
            self.send_error(404)

    def _oauth_callback(self, query):
        pending = self.server.oauth
        received = query.get("state", [""])[0]
        if not pending or not hmac.compare_digest(received, pending["state"]):
            self.send_error(400, "Authorization state did not match")
            return
        try:
            if query.get("error") or not query.get("code"):
                raise ValueError("Authorization was declined")
            validate_scope(query.get("scope", [""])[0], pending["read_private"])
            saved = read_json(self.server.state_dir / "credentials.json")
            secret = saved.get("client_secret") or read_keychain_secret(f"strava:{saved['client_id']}")
            if not secret:
                raise ValueError("Strava secret is unavailable")
            payload = exchange_code(saved["client_id"], secret, query["code"][0])
            persist_tokens(self.server.state_dir, saved["client_id"], payload)
            self.server.oauth = None
            self.send_response(303)
            self.send_header("Location", "/?strava=connected")
            self.send_header("Content-Length", "0")
            self.end_headers()
        except (ValueError, RuntimeError, KeyError):
            self.server.oauth = None
            self.send_error(400, "Strava authorization failed")

    def do_POST(self):
        if not self._local_request() or not self._authorized():
            self._json({"error": "Unauthorized local request"}, 403)
            return
        try:
            payload = self._payload()
            if self.path == "/api/strava/start":
                self._start_strava(payload)
            elif self.path == "/api/strava/analyse":
                self._analyse_strava(payload)
            elif self.path == "/api/plan":
                self._json(draft_marathon_plan(payload))
            elif self.path == "/api/save":
                config = payload.get("config")
                if not isinstance(config, dict):
                    raise ValueError("Missing plan configuration")
                load_plan(config)
                write_json(self.server.state_dir / "coach_config.json", config)
                self._json({"saved": True})
            else:
                self._json({"error": "Not found"}, 404)
        except (ValueError, RuntimeError, KeyError) as exc:
            self._json({"error": str(exc)}, 400)

    def _start_strava(self, payload):
        client_id = str(payload.get("client_id", "")).strip()
        client_secret = str(payload.get("client_secret", "")).strip()
        if not client_id.isdigit() or not 8 <= len(client_secret) <= 200:
            raise ValueError("Enter a valid Strava Client ID and Client Secret")
        store_keychain_secret(f"strava:{client_id}", client_secret)
        saved = read_json(self.server.state_dir / "credentials.json")
        saved.pop("client_secret", None)
        saved.update({"client_id": client_id, "client_secret_keychain": True})
        write_json(self.server.state_dir / "credentials.json", saved)
        state = secrets.token_urlsafe(32)
        read_private = bool(payload.get("read_private"))
        self.server.oauth = {"state": state, "read_private": read_private}
        port = self.server.server_address[1]
        redirect = f"http://localhost:{port}/oauth/callback"
        self._json({"url": authorization_url(client_id, redirect, state, read_private)})

    def _analyse_strava(self, payload):
        cfg = credentials(self.server.state_dir)
        token = get_token(cfg, self.server.state_dir)
        today = date.today()
        try:
            tz = ZoneInfo(str(payload.get("timezone") or "UTC"))
        except (ValueError, KeyError):
            raise ValueError("Unknown local timezone") from None
        runs = fetch_runs_since(token, today, tz, 53)
        self._json({"baseline": analyse_training(runs, today, tz),
                    "race_candidates": race_candidates(runs, today, tz)})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the private Strava Coach setup app")
    parser.add_argument("--state-dir", type=Path, default=Path(".private"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    server = CoachServer(("127.0.0.1", args.port), Handler, args.state_dir)
    url = f"http://localhost:{args.port}/"
    print(f"Strava Coach is running locally at {url}")
    print("Press Ctrl+C to stop it.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStrava Coach stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
