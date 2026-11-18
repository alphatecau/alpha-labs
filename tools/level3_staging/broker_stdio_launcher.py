"""Broker launcher. Must run under independent UID with private custody."""
import base64
import os
from tools.level3_staging.broker import serve

def main():
    keys=("LEVEL3_BROKER_SOCKET","LEVEL3_STAGING_ROOT","LEVEL3_LEDGER_PATH",
          "LEVEL3_AUDIT_PATH","LEVEL3_APPROVER_PUBLIC_KEY_B64","LEVEL3_WORKER_UID")
    if any(not os.environ.get(k) for k in keys):
        raise SystemExit("Level 3 broker configuration incomplete")
    try:
        worker_uid=int(os.environ["LEVEL3_WORKER_UID"])
        pub=base64.b64decode(os.environ["LEVEL3_APPROVER_PUBLIC_KEY_B64"],validate=True)
    except (ValueError,TypeError) as exc:
        raise SystemExit("invalid broker identity or public key") from exc
    serve(os.environ["LEVEL3_BROKER_SOCKET"],os.environ["LEVEL3_STAGING_ROOT"],
          os.environ["LEVEL3_LEDGER_PATH"],os.environ["LEVEL3_AUDIT_PATH"],
          pub,worker_uid)

if __name__=="__main__":
    main()
