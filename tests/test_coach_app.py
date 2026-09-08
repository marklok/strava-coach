import unittest
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import strava_coach
import coach_app
from coach_app import Handler
from private_data import read_keychain_secret, store_keychain_secret, write_json


class LocalAppTests(unittest.TestCase):
    def setUp(self):
        self.handler=Handler.__new__(Handler)
        self.handler.server=SimpleNamespace(app_token="local-token")

    def test_catalog_is_local_and_state_changing_requests_need_token(self):
        self.handler.headers={"Host":"localhost:8765"}
        self.assertTrue(self.handler._local_request())
        self.assertFalse(self.handler._authorized())
        self.handler.headers["X-Coach-Token"]="local-token"
        self.assertTrue(self.handler._authorized())

    def test_foreign_host_and_origin_are_rejected(self):
        self.handler.headers={"Host":"attacker.invalid"}
        self.assertFalse(self.handler._local_request())
        self.handler.headers={"Host":"localhost:8765","Origin":"https://attacker.invalid"}
        self.assertFalse(self.handler._local_request())

    def test_email_setup_keeps_password_out_of_json(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(coach_app,"store_keychain_secret") as store:
            self.handler.server.state_dir=Path(directory);self.handler._json=unittest.mock.Mock()
            self.handler._save_email({"sender":"runner@example.com","recipient":"coach@example.com",
                                      "app_password":"abcd efgh ijkl mnop"})
            saved=strava_coach.read_json(Path(directory)/"credentials.json")
            self.assertNotIn("gmail_app_password",saved)
            self.assertTrue(saved["gmail_app_password_keychain"])
            store.assert_called_once_with("gmail:runner@example.com","abcdefghijklmnop")

    def test_dashboard_is_written_to_private_report_files(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory);self.handler.server.state_dir=state;self.handler._json=unittest.mock.Mock()
            write_json(state/"coach_config.json",{})
            with patch.object(coach_app,"credentials",return_value={}), \
                 patch.object(coach_app,"get_token",return_value="token"), \
                 patch.object(coach_app,"fetch_runs",return_value=[]), \
                 patch.object(coach_app,"enrich_runs"), \
                 patch.object(coach_app,"build_report",return_value=("<html>dashboard</html>","dashboard",{})):
                self.handler._build_dashboard({})
            self.assertEqual((state/"reports"/"report.html").read_text(),"<html>dashboard</html>")


class KeychainTests(unittest.TestCase):
    @patch("private_data.sys.platform","darwin")
    @patch("private_data.subprocess.run")
    def test_secret_is_passed_as_argument_and_errors_are_generic(self,run):
        run.return_value.returncode=0
        store_keychain_secret("strava:123","top-secret")
        args=run.call_args.args[0]
        self.assertEqual(args[-1],"top-secret")
        self.assertNotIsInstance(args,str)

    @patch("private_data.sys.platform","darwin")
    @patch("private_data.subprocess.run")
    def test_keychain_read_strips_only_trailing_newline(self,run):
        run.return_value.returncode=0;run.return_value.stdout="secret value\n"
        self.assertEqual(read_keychain_secret("strava:123"),"secret value")

    def test_weekly_report_loads_anthropic_key_from_keychain_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory);write_json(state/"ai_credentials.json",{"anthropic_api_keychain":True})
            with patch.object(strava_coach,"read_keychain_secret",return_value="private-ai-key"):
                self.assertEqual(strava_coach.credentials(state)["anthropic_api_key"],"private-ai-key")

    def test_weekly_report_loads_gmail_password_from_keychain_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory);write_json(state/"credentials.json",{
                "gmail_sender":"runner@example.com","email_to":"runner@example.com",
                "gmail_app_password_keychain":True})
            with patch.object(strava_coach,"read_keychain_secret",return_value="private-mail-password"):
                self.assertEqual(strava_coach.credentials(state)["gmail_app_password"],
                                 "private-mail-password")


if __name__ == "__main__":
    unittest.main()
