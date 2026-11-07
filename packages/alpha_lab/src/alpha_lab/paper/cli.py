"""Local operator/replay commands. No hosting or production configuration."""
from __future__ import annotations
import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import secrets
import time

from .contracts import Principal, Proposal, canonical, timestamp, utc
from .engine import PaperEngine
from .identity import LocalIdentity
from .ledger import reconcile
from .market_data import synthetic_quote
from .store import Store


def replay():
    """Repeatable software scenario, including a gap stop and two isolated users."""
    from tempfile import TemporaryDirectory
    now='2026-11-07T00:00:01Z'
    with TemporaryDirectory() as tmp:
        store=Store(Path(tmp)/'replay.db'); engine=PaperEngine(store)
        alice=Principal('fixture-alice','alice'); bob=Principal('fixture-bob','bob')
        for user in (alice,bob):
            store.create_account(user,'paper',now=now)
            engine.control(user,'paper','enable',now)
        quote=synthetic_quote(now)
        p=Proposal('paper','TEST/AUD','synthetic-contract-v1','LONG','2','98','entry-1')
        engine.autonomous_cycle(alice,p,quote,now)
        later=timestamp(utc(now)+timedelta(seconds=2))
        gap=synthetic_quote(later,midpoint='95')
        p=Proposal('paper','TEST/AUD','synthetic-contract-v1','LONG','2','98','gap-1')
        engine.autonomous_cycle(alice,p,gap,later)
        engine.control(alice,'paper','halt',later)
        snap=store.snapshot(alice,'paper')
        # UUIDs and wall-clock latency are excluded from deterministic evidence.
        return dict(schema='alpha-labs.synthetic-replay.v1', synthetic=True,
                    purpose='software contract check; no market performance claim',
                    alice=snap['account'], bob=store.snapshot(bob,'paper')['account'],
                    fill_count=sum(e['kind']=='FILL' for e in store.events(alice,'paper')),
                    reconciliation=reconcile(store,alice,'paper'),
                    live_trading_enabled=False, production_deployment_enabled=False)


def serve(state_dir: Path, port: int):
    from .api import LocalServer
    state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(state_dir,0o700)
    store=Store(state_dir/'paper.db'); engine=PaperEngine(store); identity=LocalIdentity()
    credentials={}
    now=timestamp()
    for name in ('alice','bob'):
        user=Principal('demo-'+name,name)
        with store.transaction() as db:
            exists=db.execute('SELECT 1 FROM accounts WHERE tenant=? AND id=?',(user.tenant,'paper')).fetchone()
        if not exists: store.create_account(user,'paper',now=now)
        else:
            # A process restart always requires an explicit operator enable.
            engine.recover(user,'paper',now)
            engine.control(user,'paper','suspend',now)
        credentials[name]=identity.issue(user)
    credential_path=state_dir/'operator-tokens.json'
    if credential_path.is_symlink(): raise ValueError('credential file cannot be a symlink')
    fd=os.open(credential_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'w') as f: f.write(canonical(credentials)+'\n')
    os.chmod(credential_path,0o600)
    with LocalServer(('127.0.0.1',port),engine,identity) as server:
        print(f'Local simulation terminal: http://127.0.0.1:{server.server_port}/',flush=True)
        print(f'One-hour local operator tokens: {credential_path} (private; never commit)',flush=True)
        print('All real strategies unverified/rejected; live trading and deployment disabled.',flush=True)
        try: server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt: pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    srv=sub.add_parser('serve'); srv.add_argument('--state-dir',type=Path,required=True)
    srv.add_argument('--port',type=int,default=8765)
    sub.add_parser('replay')
    args=parser.parse_args()
    if args.command=='serve': serve(args.state_dir,args.port)
    else: print(canonical(replay()))

if __name__=='__main__': main()
