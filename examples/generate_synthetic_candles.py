"""Synthetic OHLCV fixture generator. Never use as evidence of trading profitability."""
import csv, math
from datetime import datetime,timedelta,timezone
from pathlib import Path
p=Path(__file__).parent/'SYNTHETIC_SOLUSDC_1h.csv'
with p.open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['timestamp','open','high','low','close','volume'])
    prev=150
    for i in range(360):
        close=150+i*.075+math.sin(i/13)*5+math.sin(i/3)*.6
        opening=prev
        high=max(opening,close)+1
        low=min(opening,close)-1
        timestamp=(datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat()
        w.writerow([timestamp,f'{opening:.4f}',f'{high:.4f}',f'{low:.4f}',f'{close:.4f}',f'{300+i%27}'])
        prev=close
print(f'Created SYNTHETIC test data: {p}')
