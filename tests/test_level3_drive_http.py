"""Offline Google Drive HTTP transport tests; no real credentials or network."""
import io
import json
import unittest
import urllib.parse
from tools.level3_staging.drive_http import GoogleDriveClient, DriveTransportError

PARENT = "118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6"
NAME = "a" * 64 + ".bin"
OBJECT = "drive_object_12345678"

class Response:
    def __init__(self, body):
        self._io = io.BytesIO(body)
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, n):
        return self._io.read(n)

class TransportTests(unittest.TestCase):
    def test_lookup_empty(self):
        def opener(request, timeout):
            self.assertIn("files?", request.full_url)
            self.assertIn("Bearer token", request.headers.values())
            return Response(b'{"files":[]}')
        self.assertEqual(GoogleDriveClient(lambda: "token", opener=opener).lookup(PARENT, NAME), [])
    def test_lookup_duplicate_preserved(self):
        data = {"files":[{"id":OBJECT,"name":NAME,"parents":[PARENT],"mimeType":"application/octet-stream"}]*2}
        client = GoogleDriveClient(lambda: "token", opener=lambda *_args,**_kw: Response(json.dumps(data).encode()))
        self.assertEqual(len(client.lookup(PARENT, NAME)), 2)
    def test_lookup_pagination_fails_closed(self):
        client = GoogleDriveClient(lambda: "token", opener=lambda *_args,**_kw: Response(b'{"files":[],"nextPageToken":"next"}'))
        with self.assertRaises(DriveTransportError):
            client.lookup(PARENT, NAME)
    def test_create_and_read(self):
        seen = []
        def opener(request, timeout):
            seen.append(request)
            if len(seen) == 1:
                return Response(b'{"files":[]}')
            if len(seen) == 2:
                self.assertEqual(request.get_method(), "POST")
                self.assertIn(b"hello", request.data)
                return Response(json.dumps({"id":OBJECT,"name":NAME,"parents":[PARENT],"mimeType":"application/octet-stream"}).encode())
            return Response(b"hello")
        client = GoogleDriveClient(lambda: "token", opener=opener)
        self.assertEqual(client.create(PARENT, NAME, b"hello"), OBJECT)
        self.assertEqual(client.read(OBJECT), b"hello")
    def test_existing_object_blocks_create(self):
        data = {"files":[{"id":OBJECT,"name":NAME,"parents":[PARENT],"mimeType":"application/octet-stream"}]}
        client = GoogleDriveClient(lambda: "token", opener=lambda *_args,**_kw: Response(json.dumps(data).encode()))
        with self.assertRaises(DriveTransportError):
            client.create(PARENT, NAME, b"hello")
    def test_token_newline_denied(self):
        client = GoogleDriveClient(lambda: "bad\ntoken", opener=lambda *_args,**_kw: self.fail("network reached"))
        with self.assertRaises(DriveTransportError):
            client.lookup(PARENT, NAME)
    def test_oversized_response_denied(self):
        client = GoogleDriveClient(lambda: "token", opener=lambda *_args,**_kw: Response(b"x"*65537))
        with self.assertRaises(DriveTransportError):
            client.read(OBJECT)
    def test_untrusted_lookup_metadata_denied(self):
        client = GoogleDriveClient(lambda: "token", opener=lambda *_args,**_kw: Response(b'{"files":[{"id":"bad","name":"evil"}]}'))
        with self.assertRaises(DriveTransportError):
            client.lookup(PARENT, NAME)

if __name__ == "__main__":
    unittest.main()
