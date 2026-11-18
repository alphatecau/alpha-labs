"""Google Drive v3 HTTP transport for the Level 3 *research-only* custody adapter.

Uses a broker-scoped OAuth access-token supplier. No refresh tokens, credentials,
or independent auditor signing keys may be stored in this module. Google Drive
is NOT immutable storage. Never set LEVEL3_CUSTODY_MODE based on this transport.
"""
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request

class DriveTransportError(RuntimeError):
    pass

_ID = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
_NAME = re.compile(r"^[a-f0-9]{64}\.bin$")

class _RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise DriveTransportError("Google Drive redirect denied")

class GoogleDriveClient:
    def __init__(self, token_supplier, *, timeout=15, opener=None):
        if not callable(token_supplier):
            raise ValueError("token supplier required")
        if type(timeout) not in (int, float) or not 1 <= timeout <= 60:
            raise ValueError("invalid timeout")
        self._token_supplier = token_supplier
        self._timeout = timeout
        self._opener = opener or urllib.request.build_opener(_RejectRedirect()).open

    def _request(self, url, *, method="GET", body=None, content_type=None):
        if not url.startswith(("https://www.googleapis.com/drive/v3/",
                               "https://www.googleapis.com/upload/drive/v3/")):
            raise DriveTransportError("unapproved Google Drive API origin")
        token = self._token_supplier()
        if not isinstance(token, str) or not token or any(c in token for c in "\r\n"):
            raise DriveTransportError("invalid OAuth access token")
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener(request, timeout=self._timeout) as response:
                data = response.read(65537)
                if len(data) > 65536:
                    raise DriveTransportError("oversized API response")
                return data
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            # Do not include provider error bodies or tokens in logs.
            raise DriveTransportError("Google Drive request failed; outcome may be ambiguous") from exc

    def lookup(self, parent_id, name):
        if not isinstance(parent_id, str) or not _ID.fullmatch(parent_id):
            raise ValueError("invalid parent folder")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("invalid evidence name")
        safe_name = name.replace("'", "\\'")
        query = f"'{parent_id}' in parents and name = '{safe_name}' and trashed = false"
        params = urllib.parse.urlencode({"q": query, "fields": "nextPageToken,files(id,name,parents,mimeType)",
                                          "page_size": 100})
        url = "https://www.googleapis.com/drive/v3/files?" + params
        try:
            response = json.loads(self._request(url))
        except (ValueError, UnicodeDecodeError) as exc:
            raise DriveTransportError("invalid lookup response") from exc
        if not isinstance(response, dict) or response.get("nextPageToken"):
            raise DriveTransportError("ambiguous or paginated lookup")
        files = response.get("files")
        if not isinstance(files, list):
            raise DriveTransportError("invalid lookup files")
        ids = []
        for item in files:
            if (not isinstance(item, dict) or item.get("name") != name
                or parent_id not in item.get("parents", [])
                or item.get("mimeType") != "application/octet-stream"
                or not isinstance(item.get("id"), str) or not _ID.fullmatch(item["id"])):
                raise DriveTransportError("untrusted lookup metadata")
            ids.append(item["id"])
        return ids

    def create(self, parent_id, name, payload):
        if not isinstance(parent_id, str) or not _ID.fullmatch(parent_id):
            raise ValueError("invalid parent folder")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("invalid evidence name")
        if type(payload) is not bytes or len(payload) > 32768:
            raise ValueError("invalid payload")
        # Preflight is NOT an atomic create-only guarantee. A concurrent writer
        # can still create the same name; reconciliation must detect duplicates.
        if self.lookup(parent_id, name):
            raise DriveTransportError("existing evidence object; reconcile instead")
        boundary = "alpha_labs_" + secrets.token_hex(24)
        metadata = json.dumps({"name": name, "parents": [parent_id],
                               "mimeType": "application/octet-stream"},
                              separators=(",", ":")).encode("ascii")
        body = (b"--" + boundary.encode() + b"\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                + metadata + b"\r\n--" + boundary.encode()
                + b"\r\nContent-Type: application/octet-stream\r\n\r\n"
                + payload + b"\r\n--" + boundary.encode() + b"--\r\n")
        url = ("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
               "&fields=id,name,parents,mimeType")
        try:
            response = json.loads(self._request(url, method="POST", body=body,
                content_type="multipart/related; boundary=" + boundary))
        except (ValueError, UnicodeDecodeError) as exc:
            raise DriveTransportError("invalid create response; reconcile") from exc
        if (not isinstance(response, dict) or response.get("name") != name
            or parent_id not in response.get("parents", [])
            or response.get("mimeType") != "application/octet-stream"
            or not isinstance(response.get("id"), str) or not _ID.fullmatch(response["id"])):
            raise DriveTransportError("untrusted create metadata; reconcile")
        return response["id"]

    def read(self, file_id):
        if not isinstance(file_id, str) or not _ID.fullmatch(file_id):
            raise ValueError("invalid file id")
        url = "https://www.googleapis.com/drive/v3/files/" + file_id + "?alt=media"
        return self._request(url)
