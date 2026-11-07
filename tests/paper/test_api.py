from datetime import datetime, timedelta, timezone
import http.client
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from alpha_lab.paper.api import LocalServer
from alpha_lab.paper.contracts import Forbidden, Principal
from alpha_lab.paper.engine import PaperEngine
from alpha_lab.paper.identity import LocalIdentity
from alpha_lab.paper.store import Store
from fixtures import ALICE, BOB, VIEWER


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'api.db')
        self.store.create_account(ALICE,'paper'); self.store.create_account(BOB,'paper',initial_cash='20000')
        self.engine=PaperEngine(self.store); self.identity=LocalIdentity()
        self.token=self.identity.issue(ALICE); self.bob=self.identity.issue(BOB)
        self.viewer=self.identity.issue(VIEWER)
        self.server=LocalServer(('127.0.0.1',0),self.engine,self.identity)
        self.thread=Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def request(self,path='/api/v1/accounts/paper',*,token=True,body=None,headers=None,raw=None):
        h={}
        if token: h['Authorization']='Bearer '+(self.token if token is True else token)
        if body is not None or raw is not None: h['Content-Type']='application/json'
        h.update(headers or {})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        data=raw if raw is not None else json.dumps(body) if body is not None else None
        conn.request('POST' if data is not None else 'GET',path,body=data,headers=h)
        response=conn.getresponse();payload=response.read();hs=dict(response.getheaders());status=response.status;conn.close()
        return status,json.loads(payload) if hs.get('Content-Type','').startswith('application/json') else payload,hs

    def test_health_has_no_account_information_and_live_disabled(self):
        code,data,_=self.request('/api/v1/health',token=False)
        self.assertEqual(code,200);self.assertFalse(data['live_trading_enabled']);self.assertNotIn('account',data)

    def test_unauthenticated_and_forged_credentials_rejected(self):
        self.assertEqual(self.request(token=False)[0],401)
        self.assertIn(self.request(token='forged-token')[0],(401,403))

    def test_tenant_identity_comes_only_from_token(self):
        code,a,_=self.request();code,b,_=self.request(token=self.bob)
        self.assertEqual(a['account']['cash'],'10000');self.assertEqual(b['account']['cash'],'20000')
        self.assertEqual(self.request(headers={'X-Tenant-ID':ALICE.tenant},token=self.bob)[0],403)
        self.assertEqual(self.request('/api/v1/accounts/paper?tenant=tenant-alice',token=self.bob)[0],400)

    def test_missing_account_returns_no_data(self):
        code,data,_=self.request('/api/v1/accounts/secret')
        self.assertEqual(code,403);self.assertEqual(data,{'status':'access_denied'})

    def test_forged_role_or_privileged_body_rejected(self):
        self.assertEqual(self.request('/api/v1/accounts/paper/control',body={'action':'enable'},headers={'X-Role':'admin'})[0],403)
        self.assertEqual(self.request('/api/v1/accounts/paper/control',body={'action':'enable','live':True})[0],400)
        self.assertEqual(self.request('/api/v1/accounts/paper/fixture',body={'action':'cycle','key':'a','risk_approved':True})[0],400)

    def test_host_origin_and_cross_site_protections(self):
        for header in ({'Host':'evil.example'},{'Origin':'https://evil.example'},{'Sec-Fetch-Site':'cross-site'}):
            self.assertEqual(self.request(headers=header)[0],403)

    def test_viewer_cannot_mutate(self):
        self.assertEqual(self.request(token=self.viewer)[0],200)
        self.assertEqual(self.request('/api/v1/accounts/paper/control',token=self.viewer,body={'action':'enable'})[0],403)

    def test_session_revoked_on_signout(self):
        self.assertEqual(self.request('/api/v1/signout',body={})[0],200)
        self.assertEqual(self.request()[0],403)

    def test_token_expiry_and_hash_storage(self):
        with self.assertRaises(Forbidden):
            self.identity.authenticate(self.token,now=datetime.now(timezone.utc)+timedelta(hours=2))
        self.assertNotIn(self.token,self.identity._tokens)
        self.assertTrue(all(len(k)==64 for k in self.identity._tokens))

    def test_request_rate_limit(self):
        for _ in range(60): self.server.rate_limit((ALICE.tenant,ALICE.subject))
        code,_,headers=self.request()
        self.assertEqual(code,429);self.assertEqual(headers['Retry-After'],'60')

    def test_duplicate_keys_nonfinite_and_oversize_inputs_rejected(self):
        for raw in ('{"action":"halt","action":"enable"}','{"action":NaN}','x'*32769):
            self.assertEqual(self.request('/api/v1/accounts/paper/control',raw=raw)[0],400)

    def test_directory_traversal_and_private_files_not_served(self):
        for path in ('/../pyproject.toml','/operator-tokens.json','/paper.db','/%2e%2e/README.md'):
            self.assertEqual(self.request(path)[0],404)

    def test_mobile_terminal_assets_and_security_headers(self):
        for path in ('/','/app.js','/style.css'):
            code,data,headers=self.request(path,token=False)
            self.assertEqual(code,200);self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
            self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertIn(b'Live trading disabled',self.request('/',token=False)[1])

    def test_api_autonomous_cycle_halt_and_tenant_isolation(self):
        self.request('/api/v1/accounts/paper/control',body={'action':'enable'})
        code,order,_=self.request('/api/v1/accounts/paper/fixture',body={'action':'cycle','key':'http-order'})
        self.assertEqual(code,200);self.assertEqual(order['status'],'FILLED')
        self.assertEqual(self.request(token=self.bob)[1]['positions'],[])
        self.request('/api/v1/accounts/paper/control',body={'action':'halt'})
        code,result,_=self.request('/api/v1/accounts/paper/fixture',body={'action':'cycle','key':'after-halt'})
        self.assertEqual(result['decision']['outcome'],'HALT')
        snapshot=self.request()[1]
        self.assertTrue(snapshot['reconciliation']['ok']);self.assertTrue(snapshot['account']['halted'])

    def test_live_endpoints_absent_and_brokers_not_connected(self):
        self.assertEqual(self.request('/api/v1/live',body={})[0],404)
        code,data,_=self.request('/api/v1/catalog')
        self.assertFalse(data['live_enabled_in_any_jurisdiction'])
        self.assertTrue(all(not x['real_trading_eligible'] for x in data['strategies']))

    def test_server_cannot_bind_publicly(self):
        with self.assertRaises(ValueError):
            LocalServer(('0.0.0.0',0),self.engine,self.identity)

if __name__=='__main__': unittest.main()
