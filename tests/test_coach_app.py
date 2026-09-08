import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from coach_app import CoachServer, Handler
from private_data import read_json, read_keychain_secret, store_keychain_secret


class LocalAppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=CoachServer(("127.0.0.1",0),Handler,Path(self.temp.name))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()

    def request(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_address[1],timeout=3)
        supplied={"Host":f"localhost:{self.server.server_address[1]}"}|(headers or {})
        conn.request(method,path,body=body,headers=supplied)
        response=conn.getresponse();data=response.read();conn.close()
        return response.status,data

    def test_catalog_is_local_and_state_changing_requests_need_token(self):
        status,body=self.request("GET","/api/catalog")
        self.assertEqual(status,200)
        self.assertEqual(len(json.loads(body)["races"]),40)
        status,_=self.request("POST","/api/plan",body=b"{}",headers={"Content-Type":"application/json"})
        self.assertEqual(status,403)

    def test_foreign_host_and_origin_are_rejected(self):
        status,_=self.request("GET","/",headers={"Host":"attacker.invalid"})
        self.assertEqual(status,421)
        status,_=self.request("POST","/api/plan",body=b"{}",headers={
            "Origin":"https://attacker.invalid","X-Coach-Token":self.server.app_token,
            "Content-Type":"application/json"})
        self.assertEqual(status,403)


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


if __name__ == "__main__":
    unittest.main()
