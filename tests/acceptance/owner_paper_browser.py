"""Exercise the private paper desk in Chromium at an Android-sized touch viewport."""
import argparse
import ipaddress
import json
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import Mock
from wsgiref.simple_server import WSGIRequestHandler, make_server

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from playwright.sync_api import expect, sync_playwright

from alpha_lab.research.live_paper_session import LivePaperSession
from alpha_lab.research.paper_account_service import VerifiedPrincipal
from alpha_lab.research.postgres_paper_security import PostgresIdentityLimiter, PostgresPaperOwnership, SCHEMA
from deployment.account_role_research_reader import AccountRoleResearchReader
from deployment.owner_paper_bff import OwnerPaperBFF
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions, SCHEMA as SESSION_SCHEMA
from deployment.postgres_paper_checkpoints import checkpoint_schema
from deployment.staging_authenticated_bff import StagingResearchBFF
from deployment.verified_proxy_ingress import VerifiedProxyIngress
from protected_paper_recovery import DisposablePostgres
from test_paper_commit_boundaries import FixedFeed, NOW


class BrowserFeed(FixedFeed):
    available = True

    def snapshot(self, now):
        return super().snapshot(now) if self.available else ({}, {}, {})


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def tls_context(root):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "local disposable browser fixture")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(minutes=10))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                           critical=False).sign(key, hashes.SHA256()))
    cert_path, key_path = root / "browser.crt", root / "browser.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    key_path.chmod(0o600)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert_path, key_path)
    return tls


def browser_checks(chromium, origin, token, feed):
    browser = chromium
    context = browser.new_context(viewport={"width": 393, "height": 873}, device_scale_factor=2.75,
                                  is_mobile=True, has_touch=True, ignore_https_errors=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    assert page.goto(origin + "/api/v1/paper/state").status == 401
    context.add_cookies([{"name": "__Host-alpha_session", "value": token, "url": origin,
                          "secure": True, "httpOnly": True, "sameSite": "Lax"}])
    page.on("dialog", lambda dialog: dialog.accept())
    assert page.goto(origin + "/owner-paper/").status == 200
    expect(page.locator("#risk-status")).to_have_text("HALTED")
    assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")
    page.locator("#arm").tap()
    expect(page.locator("#risk-status")).to_have_text("ARMED · PAPER ONLY")
    page.locator("#symbol").select_option("SOL-USD")
    page.locator("#quantity").fill("1")
    page.locator("#stop-price").fill("90")
    page.locator("#order-type").select_option("LIMIT")
    page.locator("#limit-price").fill("99")
    page.locator("#submit-order").tap()
    expect(page.locator("#orders")).to_contain_text("PENDING")
    page.locator("#orders").get_by_role("button", name="Cancel").tap()
    expect(page.locator("#orders")).to_contain_text("CANCELLED")
    page.locator("#order-type").select_option("MARKET")
    page.locator("#submit-order").tap()
    expect(page.locator("#fills")).to_contain_text("SOL-USD / BUY")
    page.reload()
    expect(page.locator("#fills")).to_contain_text("SOL-USD / BUY")
    expect(page.locator("#recovery")).to_contain_text("Verified checkpoint")
    page.locator("#load-checkpoints").tap()
    expect(page.locator("#checkpoints tr")).not_to_have_count(0)
    feed.available = False
    page.reload()
    expect(page.locator("#risk-status")).to_have_text("UNAVAILABLE · LOCKED")
    expect(page.locator("#submit-order")).to_be_disabled()
    page.locator("#sign-out").tap()
    expect(page.get_by_role("heading", name="Signed out")).to_be_visible()
    assert page.goto(origin + "/api/v1/paper/state").status == 401
    assert not errors, errors
    context.close()


def verify(pg, root, executable):
    pg.setup()
    database = "fixture_verified"
    principal = VerifiedPrincipal("browser-fixture-owner", "https://issuer.example/")
    with pg.connect(database) as admin:
        admin.execute(SCHEMA)
        admin.execute(SESSION_SCHEMA)
        admin.execute("CREATE ROLE alpha_fixture_quota LOGIN NOINHERIT PASSWORD 'disposable-recovery-only'")
        admin.execute("GRANT SELECT,INSERT,UPDATE ON public.identity_rate_limit TO alpha_fixture_quota")
    sessions = PostgresOpaqueSessions(lambda: pg.connect(database))
    ownership = PostgresPaperOwnership(lambda: pg.connect(database))
    ownership.provision(principal, "primary")
    sid = sessions.create(principal.subject, principal.issuer)
    owner = sessions.resolve_owner(sid)
    with pg.connect(database) as admin:
        admin.execute(checkpoint_schema(owner))
        admin.execute("GRANT SELECT,INSERT ON public.paper_journal_checkpoints TO alpha_fixture_checkpoint")
    feed = BrowserFeed()
    paper = LivePaperSession(root, owner, feed, clock=lambda: NOW,
                             checkpoint_store=pg.store(database, owner=owner), provision=True)
    server = make_server("127.0.0.1", 0, None, handler_class=QuietHandler)
    try:
        origin = f"https://127.0.0.1:{server.server_port}"
        limiter = PostgresIdentityLimiter(lambda: pg.connect(database, user="alpha_fixture_quota"),
                                          limit=120, window=60)
        research = StagingResearchBFF(object(), object(), sessions, Mock(spec=AccountRoleResearchReader),
                                      origin=origin, rate_limiter=limiter,
                                      authorize_owner=lambda value: ownership.require_owner_id(value, "primary"))
        owner_app = OwnerPaperBFF(research, paper, owner_id=owner, csrf_key=b"browser-fixture-csrf-key-material")
        ingress = VerifiedProxyIngress(owner_app, origin, trusted_peer_cidrs=["127.0.0.1/32"])

        def fixture_proxy(env, start):
            env["HTTP_X_FORWARDED_PROTO"] = "https"
            return ingress(env, start)

        server.set_app(fixture_proxy)
        server.socket = tls_context(root).wrap_socket(server.socket, server_side=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=executable)
                try:
                    browser_checks(browser, origin, sid, feed)
                finally:
                    browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
    finally:
        server.server_close()
        paper.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-bin", type=Path, required=True)
    parser.add_argument("--chromium", required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="alpha-browser-") as directory:
        root = Path(directory)
        pg = DisposablePostgres(args.postgres_bin.resolve(), root)
        try:
            pg.start()
            verify(pg, root, args.chromium)
        finally:
            pg.stop()
    print(json.dumps({"viewport": [393, 873], "touch": True, "synthetic_auth0_and_quotes": True,
                      "market_limit_cancel_refresh_stale_sign_out": "PASS"}))


if __name__ == "__main__":
    main()
