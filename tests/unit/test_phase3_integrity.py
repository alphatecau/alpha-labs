import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from alpha_lab.research.phase3_integrity import (
    POSTGRES_RUNS_DDL, register_postgres_run, Session, next_eligible_open,
    require_settlement_at_open, reconcile_long_only_orders,
)
from alpha_lab.backtest.engine import replay
from alpha_lab.backtest.costs import CostModel
from alpha_lab.data.csv_import import Bar

UTC = timezone.utc
def hour(day, h=0):
    return datetime(2026, 1, day, h, tzinfo=UTC)

class Cursor:
    def __init__(self): self.seen=set()
    def execute(self, sql, params):
        if params[:2] in self.seen: raise RuntimeError("duplicate key")
        self.seen.add(params[:2]); self.last=params
    def fetchone(self): return self.last[:2]

class Phase3IntegrityTests(unittest.TestCase):
    def test_sql_enforces_owner_scoped_primary_key(self):
        self.assertIn("PRIMARY KEY (owner_id, run_id)", POSTGRES_RUNS_DDL)
        self.assertNotIn("ON CONFLICT", POSTGRES_RUNS_DDL)

    def test_run_registration_rejects_duplicate_and_scopes_owner(self):
        cursor=Cursor()
        register_postgres_run(cursor,"owner-a","run-1","a"*64)
        with self.assertRaisesRegex(RuntimeError,"duplicate"):
            register_postgres_run(cursor,"owner-a","run-1","a"*64)
        register_postgres_run(cursor,"owner-b","run-1","a"*64)

    def test_invalid_registration_does_not_touch_cursor(self):
        cursor=Cursor()
        with self.assertRaises(ValueError):
            register_postgres_run(cursor,"owner","run","invalid")
        self.assertFalse(cursor.seen)

    def test_holiday_and_weekend_skip(self):
        sessions=[Session(hour(2,9),hour(2,16)),Session(hour(6,9),hour(6,16))]
        self.assertEqual(next_eligible_open(hour(2,15),sessions),hour(6,9))
        require_settlement_at_open(hour(2,15),hour(6,9),sessions)
        with self.assertRaisesRegex(ValueError,"settlement"):
            require_settlement_at_open(hour(2,15),hour(3,9),sessions)

    def test_no_calendar_or_future_session_fails_closed(self):
        with self.assertRaises(ValueError): next_eligible_open(hour(2),[])
        with self.assertRaises(ValueError):
            next_eligible_open(hour(7),[Session(hour(2,9),hour(2,16))])

    def test_overlapping_sessions_rejected(self):
        with self.assertRaisesRegex(ValueError,"overlapping"):
            next_eligible_open(hour(1),[Session(hour(2,9),hour(2,16)),Session(hour(2,15),hour(2,18))])

    def test_independent_replay_reconciliation(self):
        origin=hour(1)
        bars=tuple(Bar(origin+timedelta(hours=i),Decimal("100"),Decimal("101"),Decimal("99"),Decimal("100"),Decimal("1")) for i in range(90))
        signals=[False]*90
        for i in range(35,41): signals[i]=True
        result=replay(bars,signals,35,45)
        actual=reconcile_long_only_orders(result.starting_balance,result.orders,bars[44].close,CostModel(),result.final_liquidatable_value)
        self.assertEqual(actual["total_modelled_fees"],Decimal(result.total_modelled_fees))
        self.assertEqual(actual["quantity"],Decimal("0"))
        with self.assertRaisesRegex(ValueError,"NAV"):
            reconcile_long_only_orders(result.starting_balance,result.orders,bars[44].close,CostModel(),Decimal(result.final_liquidatable_value)+1)

    def test_forged_order_rejected(self):
        with self.assertRaises(ValueError):
            reconcile_long_only_orders("100",[{"kind":"SELL","quantity":"1","fee":"0","quote_received":"100"}],"100",CostModel(),"100")

if __name__=="__main__": unittest.main()
