"""Offline Google Drive folder permission policy. No API calls or credentials."""


class DrivePermissionDenied(ValueError):
    """Folder is not confined to the intended auditor identity."""


def verify_auditor_folder(metadata, auditor_email):
    if not isinstance(metadata, dict) or not isinstance(auditor_email, str) or not auditor_email.strip():
        raise DrivePermissionDenied("invalid folder evidence")
    if metadata.get("mimeType") != "application/vnd.google-apps.folder":
        raise DrivePermissionDenied("not a folder")
    if metadata.get("trashed") is not False:
        raise DrivePermissionDenied("trashed folder")
    owners = metadata.get("owners")
    if not isinstance(owners, list) or len(owners) != 1:
        raise DrivePermissionDenied("ambiguous folder ownership")
    owner = owners[0]
    if (not isinstance(owner, dict) or not isinstance(owner.get("emailAddress"), str)
            or owner["emailAddress"].lower() != auditor_email.lower()):
        raise DrivePermissionDenied("auditor does not own folder")
    permissions = metadata.get("permissions")
    if not isinstance(permissions, list) or not permissions:
        raise DrivePermissionDenied("missing permission evidence")
    for permission in permissions:
        if not isinstance(permission, dict) or permission.get("type") != "user":
            raise DrivePermissionDenied("public, domain or group access denied")
        if permission.get("role") not in ("owner", "reader"):
            raise DrivePermissionDenied("unexpected write permission")
        if (not isinstance(permission.get("emailAddress"), str)
                or not permission["emailAddress"].strip()):
            raise DrivePermissionDenied("missing permission identity")
        if permission.get("role") == "owner" and permission["emailAddress"].lower() != auditor_email.lower():
            raise DrivePermissionDenied("unexpected owner")
    return True
