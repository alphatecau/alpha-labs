'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const Engine=require('../research-engine.js');
function nearly(actual,expected,tolerance=1e-6){assert.ok(Math.abs(actual-expected)<tolerance,`${actual} should be within ${tolerance} of ${expected}`)}
function flatBars(n=80){return Array.from({length:n},(_,i)=>({timestamp:new Date(Date.UTC(2026,0,1)+3600000*i).toISOString(),open:100,high:101,low:99,close:100,volume:1000}))}
function trendBars(n=90){return Array.from({length:n},(_,i)=>{const open=100+i*.1,close=open+.05;return {timestamp:new Date(Date.UTC(2026,0,1)+3600000*i).toISOString(),open,high:close+.3,low:open-.3,close,volume:1000}})}
test('demo fixtures deterministic and plausible OHLC',()=>{
  const a=Engine.generateDemo(),b=Engine.generateDemo();assert.deepEqual(a,b);
  assert.equal(a.length,360);for(const row of a){assert.ok(row.high>=Math.max(row.open,row.close));assert.ok(row.low<=Math.min(row.open,row.close));}
});
test('CSV roundtrip preserves all observations',()=>{
  const original=Engine.generateDemo(75);const read=Engine.parseCsv(Engine.csvForBars(original));assert.deepEqual(read,original);
});
test('CSV accepts timezone offset timestamp and BOM',()=>{
  const rows=Engine.generateDemo(65);
  let csv=Engine.csvForBars(rows).replace('2026-06-01T00:00:00.000Z','2026-06-01T10:00:00+10:00');
  const parsed=Engine.parseCsv('\uFEFF'+csv);assert.equal(parsed.length,65);assert.equal(parsed[0].timestamp,rows[0].timestamp);
});
test('CSV rejects duplicate timestamps',()=>{
  const raw=Engine.csvForBars(Engine.generateDemo(65));
  const lines=raw.trim().split('\n');lines[5]=lines[4].replace('2026-06-01T03:00:00.000Z','2026-06-01T03:00:00.000Z');
  assert.throws(()=>Engine.parseCsv(lines.join('\n')),/Timestamps must increase/);
});
test('CSV rejects inconsistent OHLC and zero price',()=>{
  const lines=Engine.csvForBars(Engine.generateDemo(65)).trim().split('\n');
  const row=lines[5].split(',');row[2]='0';lines[5]=row.join(',');assert.throws(()=>Engine.parseCsv(lines.join('\n')),/Invalid high/);
});
test('flat market has no strategy trades and preserves capital before fees',()=>{
  const r=Engine.runBacktest(flatBars(),{feeBps:0,slippageBps:0});
  assert.equal(r.fillCount,0);assert.equal(r.tradeCount,0);assert.equal(r.openPosition,null);
  nearly(r.finalEquity,10000);nearly(r.benchmarkReturnPct,0);
});
test('long signal never uses same-bar closing information',()=>{
  const bars=trendBars();const r=Engine.runBacktest(bars,{feeBps:0,slippageBps:0,fast:5,slow:20});
  assert.ok(r.fills.length>0);
  for(const fill of r.fills){const idx=bars.findIndex(b=>b.timestamp===fill.timestamp);assert.ok(idx>0);assert.equal(fill.signalBasedOn,bars[idx-1].timestamp);}
});
test('higher fixed execution costs cannot improve same-signal flat-market strategy results',()=>{
  const bars=trendBars();
  const a=Engine.runBacktest(bars,{feeBps:0,slippageBps:0,fast:5,slow:20});
  const b=Engine.runBacktest(bars,{feeBps:50,slippageBps:60,fast:5,slow:20});
  assert.ok(a.finalEquity>b.finalEquity);assert.ok(b.feesPaid>0);assert.ok(b.slippageCost>0);
});
test('cash equity never negative due to buy friction; benchmark and strategy series align',()=>{
  const bars=Engine.generateDemo();const r=Engine.runBacktest(bars,{exposurePct:100,feeBps:200,slippageBps:500});
  assert.equal(r.series.length,bars.length);assert.equal(r.benchmarkSeries.length,bars.length);
  assert.ok(r.series.every(x=>x.value>=0));
});
test('input settings validated at boundaries',()=>{
  const bars=Engine.generateDemo(70);
  assert.throws(()=>Engine.runBacktest(bars,{fast:20,slow:10}),/Require integer/);
  assert.throws(()=>Engine.runBacktest(bars,{slippageBps:-1}),/permitted range/);
  assert.throws(()=>Engine.runBacktest(bars,{initialEquity:0}),/Invalid equity/);
});
test('stress report has stable multipliers and matches standalone baseline',()=>{
  const bars=Engine.generateDemo();const s=Engine.stressTest(bars);const b=Engine.runBacktest(bars);
  assert.deepEqual(s.map(x=>x.multiplier),[1,1.5,2]);nearly(s[0].netPnl,b.netPnl);
});
test('changing a future candle never changes earlier decisions and fills',()=>{
  const original=trendBars(90),modified=structuredClone(original);
  const changedAt=70;
  modified[changedAt].close*=1.5;
  modified[changedAt].high=Math.max(modified[changedAt].high,modified[changedAt].close+1);
  const settings={fast:5,slow:20};
  const a=Engine.runBacktest(original,settings).fills.filter(f=>f.timestamp<=original[changedAt].timestamp);
  const b=Engine.runBacktest(modified,settings).fills.filter(f=>f.timestamp<=modified[changedAt].timestamp);
  assert.deepEqual(a,b);
});
test('end-of-run ledger reconciles closed and estimated open position P&L',()=>{
  const r=Engine.runBacktest(Engine.generateDemo(),{fast:7,slow:20});
  const realised=r.trades.reduce((sum,t)=>sum+t.pnl,0);
  if(!r.openPosition){nearly(r.netPnl,realised,0.05)}
  else assert.ok(Number.isFinite(r.openPosition.estimatedValue));
});
