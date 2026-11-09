import io
import json
import unittest
from deployment.research_readonly_api import ResearchReadOnlyAPI, sign_assertion, verify_assertion
SECRET="test-only-signing-secret-longer-than-32-characters"

class Reader:
    def list_runs(self, owner, limit=50):
        return [{"run_id": owner+"-r1", "evidence_sha256": "a"*64}]
    def summary(self, owner):
        return {"owner_run_count": 1, "performance": {"status": "unavailable"}}

class ReadOnlyAPITests(unittest.TestCase):
    def request(self, api, path="/api/v1/research/runs", method="GET", token=None):
        state=[]
        env={"PATH_INFO":path,"REQUEST_METHOD":method}
        if token is not None: env["HTTP_AUTHORIZATION"]="Bearer "+token
        body=b"".join(api(env,lambda status,headers:state.append((status,dict(headers)))))
        return state[0][0],json.loads(body),state[0][1]
    def test_missing_token_rejected(self):
        status,body,_=self.request(ResearchReadOnlyAPI(Reader(),SECRET,lambda:100))
        self.assertEqual(status,"401 Unauthorized")
    def test_expired_and_forged_token_rejected(self):
        api=ResearchReadOnlyAPI(Reader(),SECRET,lambda:200)
        token=sign_assertion("owner-a",SECRET,now=100)
        self.assertEqual(self.request(api,token=token)[0],"401 Unauthorized")
        forged=token[:-1]+("A" if token[-1]!="A" else "B")
        self.assertEqual(self.request(api,token=forged)[0],"401 Unauthorized")
    def test_owner_is_derived_from_verified_assertion(self):
        api=ResearchReadOnlyAPI(Reader(),SECRET,lambda:100)
        token=sign_assertion("owner-a",SECRET,now=100)
        status,body,headers=self.request(api,"/api/v1/research/runs?owner=owner-b",token=token)
        self.assertEqual(status,"404 Not Found")
        status,body,headers=self.request(api,token=token)
        self.assertEqual(body["data"][0]["run_id"],"owner-a-r1")
        self.assertEqual(headers["Cache-Control"],"no-store")
    def test_summary_explicitly_unavailable_performance(self):
        api=ResearchReadOnlyAPI(Reader(),SECRET,lambda:100)
        status,body,_=self.request(api,path="/api/v1/research/summary",token=sign_assertion("owner-a",SECRET,now=100))
        self.assertEqual(status,"200 OK")
        self.assertEqual(body["data"]["performance"]["status"],"unavailable")
    def test_write_denied(self):
        status,_,_=self.request(ResearchReadOnlyAPI(Reader(),SECRET),method="POST")
        self.assertEqual(status,"405 Method Not Allowed")
    def test_missing_data_fails_closed(self):
        api=ResearchReadOnlyAPI(None,SECRET,lambda:100)
        status,_,_=self.request(api,token=sign_assertion("owner-a",SECRET,now=100))
        self.assertEqual(status,"503 Service Unavailable")
if __name__=="__main__": unittest.main()
