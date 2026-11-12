from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from alpha_lab.paper.contracts import Principal
from alpha_lab.paper.engine import PaperEngine
from alpha_lab.paper.ledger import reconcile
from alpha_lab.paper.store import Store
from fixtures import NOW,proposal,quote


class LocalConcurrencyTests(unittest.TestCase):
    def test_sixteen_independent_tenants_concurrently(self):
        with TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'load.db');engine=PaperEngine(store)
            users=[Principal('tenant-'+str(i),'operator-'+str(i)) for i in range(16)]
            for p in users:
                store.create_account(p,'paper',now=NOW);engine.control(p,'paper','enable',NOW)
            def cycle(p):
                begin=time.perf_counter()
                order=engine.autonomous_cycle(p,proposal(),quote(),NOW)
                self.assertEqual(order['status'],'FILLED')
                return time.perf_counter()-begin
            with ThreadPoolExecutor(max_workers=8) as pool:
                durations=list(pool.map(cycle,users))
            for p in users:
                self.assertEqual(len(store.snapshot(p,'paper')['orders']),1)
                self.assertTrue(reconcile(store,p,'paper')['ok'])
            # This is a bounded correctness test, not a capacity/SLA claim.
            self.assertEqual(len(durations),16)
