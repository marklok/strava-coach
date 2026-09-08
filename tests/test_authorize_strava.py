from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import authorize_strava


class AuthorizationTests(unittest.TestCase):
    def test_authorization_url_defaults_to_non_private_activities(self):
        url = authorize_strava.authorization_url("123", "http://localhost:8765/callback", "csrf", False)
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["client_id"], ["123"])
        self.assertEqual(query["scope"], ["read,activity:read"])
        self.assertEqual(query["state"], ["csrf"])

    def test_private_scope_is_explicit(self):
        url = authorize_strava.authorization_url("123", "http://localhost/callback", "csrf", True)
        self.assertEqual(parse_qs(urlparse(url).query)["scope"], ["read,activity:read_all"])

    def test_required_scope_must_be_granted(self):
        authorize_strava.validate_scope("read,activity:read", False)
        authorize_strava.validate_scope("read activity:read_all", True)
        with self.assertRaisesRegex(RuntimeError, "activity:read_all"):
            authorize_strava.validate_scope("read,activity:read", True)

    def test_exchange_never_embeds_secret_in_url_or_allows_redirects(self):
        response = unittest.mock.Mock(status_code=200)
        response.json.return_value = {"access_token": "access", "refresh_token": "refresh", "expires_at": 42}
        with patch("authorize_strava.requests.post", return_value=response) as post:
            authorize_strava.exchange_code("123", "secret", "one-time-code")
        self.assertEqual(post.call_args.args[0], authorize_strava.TOKEN_URL)
        self.assertEqual(post.call_args.kwargs["data"]["client_secret"], "secret")
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_persisted_token_file_is_owner_only(self):
        with TemporaryDirectory() as directory:
            authorize_strava.persist_tokens(directory, "123", {
                "access_token": "access", "refresh_token": "refresh", "expires_at": 42,
            })
            path = Path(directory) / "tokens.json"
            self.assertEqual(json.loads(path.read_text())["client_id"], "123")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
