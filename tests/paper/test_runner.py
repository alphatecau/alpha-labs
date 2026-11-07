import asyncio
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from alpha_lab.paper.contracts import timestamp,utc
from alpha_lab.paper.engine import PaperEngine
from alpha_lab.paper.ledger import reconcile
from alpha_lab.paper.market_data import synthetic_quote
from alpha_lab.paper.runner import SimulationEvent,run_session
from alpha_lab.paper.store import Store
from fixtures import ALICE,NOW


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'state.db');self.store.create_account(ALICE,'paper',now=NOW)
        self.engine=PaperEngine(self.store);self.engine.control(ALICE,'paper','enable',NOW)

    async def asyncTearDown(self): self.tmp.cleanup()

    async def test_autonomous_event_sequence_enters_and_stops_without_human_steps(self):
        async def events():
            yield SimulationEvent('event-1',NOW,synthetic_quote(NOW))
            later=timestamp(utc(NOW)+timedelta(seconds=2))
            yield SimulationEvent('event-2',later,synthetic_quote(later,midpoint='95'))
        result=await run_session(self.engine,ALICE,'paper',events())
        self.assertEqual([r['side'] for r in result],['BUY','SELL'])
        self.assertEqual(self.store.snapshot(ALICE,'paper')['positions'],[])
        self.assertTrue(reconcile(self.store,ALICE,'paper')['ok'])

    async def test_provider_timeout_persists_halt(self):
        async def events():
            await asyncio.sleep(.1)
            yield None
        with self.assertRaises(TimeoutError):
            await run_session(self.engine,ALICE,'paper',events(),event_timeout_seconds=.001)
        self.assertTrue(self.store.snapshot(ALICE,'paper')['account']['halted'])

    async def test_budget_and_persistent_halt_stop_future_events(self):
        async def events():
            for i in range(20): yield SimulationEvent('event-'+str(i),NOW,synthetic_quote(NOW))
        result=await run_session(self.engine,ALICE,'paper',events(),max_events=1)
        self.assertEqual(len(result),1)
        self.engine.control(ALICE,'paper','halt',NOW)
        self.assertEqual(await run_session(self.engine,ALICE,'paper',events()),[])
