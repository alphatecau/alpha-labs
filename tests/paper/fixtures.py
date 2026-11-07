"""Independent synthetic inputs. No market prices or performance data."""
from dataclasses import replace
from alpha_lab.paper.contracts import Principal, Proposal, Quote

NOW = '2026-11-07T00:00:01Z'
ALICE = Principal('tenant-alice', 'alice')
BOB = Principal('tenant-bob', 'bob')
VIEWER = Principal('tenant-alice', 'observer', 'viewer')


def quote(**changes):
    values = dict(instrument='TEST/AUD', venue='synthetic', currency='AUD',
                  event_time='2026-11-07T00:00:00Z', received_time='2026-11-07T00:00:00.100000Z',
                  bid='99.9', ask='100.1', bid_size='100', ask_size='100', source_ref='fixture-1', synthetic=True)
    values.update(changes)
    return Quote(**values)


def proposal(**changes):
    values = dict(account_id='paper', instrument='TEST/AUD', strategy_id='synthetic-contract-v1',
                  direction='LONG', quantity='2', stop_price='98', idempotency_key='fixture-order')
    values.update(changes)
    return Proposal(**values)
