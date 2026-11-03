'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const Alpha=require('../research-engine.js'),Evidence=require('../evidence-engine.js');
function bars(n=480){return Alpha.generateDemo(n)}
test('deterministic chronological partitions are disjoint with embargo',()=>{
  const p=Evidence.folds(bars(),{trainPct:60,validationPct:20,embargoBars:2});
  assert.equal(p.training.endIndex+2,p.validation.startIndex);
  assert.equal(p.validation.endIndex+2,p.test.startIndex);
  assert.ok(p.test.endIndex>p.test.startIndex);
});
test('refuses insufficient data and invalid zero-cost assumptions',()=>{
  assert.throws(()=>Evidence.runAudit(bars(120)),/at least 180/);
  assert.throws(()=>Evidence.runAudit(bars(),{slippageBps:0}),/nonzero/);
});
test('candidate selection does not read the final test period',()=>{
  const original=bars(480),modified=structuredClone(original);
  const split=Evidence.folds(original),first=split.test.startIndex;
  for(let i=first;i<modified.length;i++){
    const p=modified[i].open*(1+(i-first+1)*.005);
    modified[i].high=Math.max(modified[i].high,p,modified[i].open,modified[i].close);
    modified[i].low=Math.min(modified[i].low,p,modified[i].open,modified[i].close);
    modified[i].close=p;
  }
  const a=Evidence.runAudit(original),b=Evidence.runAudit(modified);
  assert.equal(a.selected,b.selected);
  assert.deepEqual(a.candidates,b.candidates);
  if(a.selected!==null)assert.notEqual(a.holdout?.netReturnPct,b.holdout?.netReturnPct);
});
test('evaluation windows reset starting capital, and do not trade before evaluation start',()=>{
  const market=bars(480),partition=Evidence.folds(market);
  const conf={strategy:'ema',fast:4,slow:16,feeBps:8,slippageBps:12};
  const a=Alpha.runBacktest(market,conf,partition.test);
  assert.equal(a.series[0].timestamp,market[partition.test.startIndex].timestamp);
  assert.ok(a.fills.every(f=>f.timestamp>=market[partition.test.startIndex].timestamp));
  assert.equal(a.sourceRows,partition.test.endIndex-partition.test.startIndex);
  assert.ok(Math.abs(a.finalEquity-(conf.initialEquity||10000)-a.netPnl)<.01);
});
test('future data cannot change completed training or validation results',()=>{
  const a=bars(480),b=structuredClone(a),p=Evidence.folds(a);
  const k=p.test.startIndex+10;
  b[k].open*=2;b[k].close*=2;b[k].high*=2;b[k].low*=2;
  const x=Evidence.runAudit(a),y=Evidence.runAudit(b);
  assert.deepEqual(x.candidates,y.candidates);
});
test('fixed selection reproducible, never outputs live trade approval',()=>{
  const a=Evidence.runAudit(bars()),b=Evidence.runAudit(bars());
  assert.deepEqual(a,b);
  assert.ok(!['LIVE_APPROVED','PROFIT_GUARANTEED'].includes(a.decision));
  assert.ok(a.warnings.some(x=>/not executable quotes/i.test(x)));
});
test('AI budget is zero at zero calls, bounded and accurate for a known fixture',()=>{
  const z=Evidence.estimateAiCost();assert.equal(z.totalTokens,0);assert.equal(z.estimatedUsd,0);
  const r=Evidence.estimateAiCost({callsPerDay:10,inputTokensPerCall:1000,outputTokensPerCall:500,inputPriceUsdPerMillion:1,outputPriceUsdPerMillion:2,days:30});
  assert.equal(r.calls,300);assert.equal(r.totalTokens,450000);assert.equal(r.estimatedUsd,.6);
  assert.throws(()=>Evidence.estimateAiCost({callsPerDay:-1}),/Invalid/);
});
