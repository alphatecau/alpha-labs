"""Isolated broker: Unix socket, Linux peer credentials, signed create only.

Run as a distinct OS UID with its own ledger/audit storage. Never expose TCP.
The signing private key is held by a THIRD identity, not this broker.
"""
import base64
import json
import os
import socket
import stat
from pathlib import Path

from tools.level3_staging.audit_reconcile import inspect_outbox
from tools.level3_staging.signed_create import Denied, apply

MAX_REQUEST=100_000

def custody_check(root, ledger, audit):
    root=Path(root).resolve(strict=True)
    for location in (ledger,audit):
        path=Path(location)
        if path.parent.resolve().is_relative_to(root) or path.is_symlink():
            raise Denied("unsafe broker custody path")
        parent=path.parent.stat()
        if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            raise Denied("broker custody directory not private")
        if path.exists():
            st=path.stat()
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise Denied("broker custody file not private")
    return root

def serve(socket_path, root, ledger, audit, public_key, worker_uid):
    if worker_uid == os.getuid():
        raise Denied("worker and broker must have separate UIDs")
    if len(public_key)!=32:
        raise Denied("invalid verifier key")
    root=custody_check(root,ledger,audit)
    if Path(ledger).exists() and inspect_outbox(ledger,audit)["blocked"]:
        raise Denied("unreconciled audit evidence")
    sock=Path(socket_path)
    if sock.exists() or sock.is_symlink():
        raise Denied("socket path already exists")
    if sock.parent.stat().st_mode & 0o002:
        raise Denied("world writable socket directory")
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        server.bind(str(sock))
        os.chmod(sock,0o660)
        server.listen(8)
        while True:
            conn,_=server.accept()
            with conn:
                try:
                    import struct
                    peer_pid,peer_uid,peer_gid=struct.unpack("3i",conn.getsockopt(
                        socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if peer_uid != worker_uid:
                        raise Denied("unauthorised worker UID")
                    raw=bytearray()
                    while len(raw)<MAX_REQUEST:
                        part=conn.recv(min(4096,MAX_REQUEST-len(raw)))
                        if not part:
                            break
                        raw.extend(part)
                        if b"\\n" in part:
                            break
                    if len(raw)>=MAX_REQUEST or raw.count(b"\\n")!=1 or not raw.endswith(b"\\n"):
                        raise Denied("invalid request framing")
                    request=json.loads(raw)
                    if not isinstance(request,dict) or set(request)!={"path","content","approval","signature"}:
                        raise Denied("invalid broker request")
                    custody_check(root,ledger,audit)
                    if Path(ledger).exists() and inspect_outbox(ledger,audit)["blocked"]:
                        raise Denied("unreconciled audit evidence")
                    old=os.environ.get("LEVEL3_AUDIT_PATH")
                    os.environ["LEVEL3_AUDIT_PATH"]=str(audit)
                    try:
                        result=apply(root,ledger,public_key,request["approval"],request["signature"],
                                     request["path"],request["content"])
                    finally:
                        if old is None:
                            os.environ.pop("LEVEL3_AUDIT_PATH",None)
                        else:
                            os.environ["LEVEL3_AUDIT_PATH"]=old
                    if inspect_outbox(ledger,audit)["blocked"]:
                        raise Denied("audit delivery incomplete")
                    response={"ok":True,"receipt":result}
                except (Denied,ValueError,TypeError,KeyError,OSError) as exc:
                    response={"ok":False,"error":type(exc).__name__}
                conn.sendall(json.dumps(response,separators=(",",":")).encode()+b"\\n")
    finally:
        server.close()
        sock.unlink(missing_ok=True)

def request(socket_path, arguments, timeout=5):
    if not isinstance(arguments,dict) or set(arguments)!={"path","content","approval","signature"}:
        raise Denied("invalid broker arguments")
    payload=json.dumps(arguments,separators=(",",":")).encode()+b"\\n"
    if len(payload)>MAX_REQUEST:
        raise Denied("request too large")
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(socket_path))
        client.sendall(payload)
        data=bytearray()
        while len(data)<8192:
            chunk=client.recv(8192-len(data))
            if not chunk:
                break
            data.extend(chunk)
            if b"\\n" in chunk:
                break
    if not data.endswith(b"\\n") or data.count(b"\\n")!=1:
        raise Denied("invalid broker response")
    result=json.loads(data)
    if not isinstance(result,dict) or result.get("ok") is not True:
        raise Denied("broker refused request")
    return result["receipt"]
