import http.client
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from deployment.paper_staging_api import Handler

class StagingAPITests(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.worker.start()
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
    def request(self, method,path,token=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=2)
        headers={"Authorization":"Bearer "+token} if token else {}
        conn.request(method,path,headers=headers)
        response=conn.getresponse()
        status=response.status
        response.read()
        conn.close()
        return status
    def test_fail_closed_auth_and_disabled_methods(self):
        with patch.dict(os.environ,{"ALPHA_STAGING_READ_TOKEN":"x"*40}):
            self.assertEqual(self.request("GET","/healthz"),200)
            self.assertEqual(self.request("GET","/api/v1/paper/status"),401)
            self.assertEqual(self.request("GET","/api/v1/paper/status","wrong"),401)
            self.assertEqual(self.request("GET","/api/v1/paper/status","x"*40),200)
            for method in ("POST","PUT","PATCH","DELETE"):
                self.assertEqual(self.request(method,"/api/v1/paper/orders","x"*40),405)
    def test_missing_secret_denies(self):
        with patch.dict(os.environ,{"ALPHA_STAGING_READ_TOKEN":""}):
            self.assertEqual(self.request("GET","/api/v1/paper/status"),401)

if __name__=="__main__":
    unittest.main()
