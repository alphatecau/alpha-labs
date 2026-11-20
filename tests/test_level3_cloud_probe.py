"""Cloud probe must never advertise readiness or accept writes."""
import http.client
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from deployment import level3_cloud_probe
from deployment.level3_cloud_probe import Handler

class CloudProbeTests(unittest.TestCase):
    def test_listener_is_local_outside_render(self):
        for platform, expected in [("", "127.0.0.1"), ("true", "0.0.0.0")]:
            with self.subTest(platform=platform), patch.dict(os.environ, RENDER=platform, PORT="6789"):
                with patch.object(level3_cloud_probe, "ThreadingHTTPServer") as server:
                    level3_cloud_probe.main()
                    server.assert_called_once_with((expected, 6789), Handler)

    def test_fail_closed_http_contract(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            port=server.server_address[1]
            for method,path,expected in (("GET","/healthz",200),("GET","/readyz",503),
                                         ("POST","/tools/call",405),("GET","/tools/list",404)):
                conn=http.client.HTTPConnection("127.0.0.1",port,timeout=3)
                conn.request(method,path)
                response=conn.getresponse()
                self.assertEqual(response.status,expected)
                response.read()
                conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

if __name__=="__main__":
    unittest.main()
