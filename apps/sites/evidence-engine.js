/* Alpha Labs v0.3 — deterministic experiment and AI-cost audit.
 * Runs entirely offline; no market access, trading, credentials or inference calls. */
(function(root,factory){
  const x=factory(typeof module==='object'&&module.exports?require('./research-engine.js'):root.AlphaEngine);
  if(typeof module==='object'&&module.exports)module.exports=x;
  if(root)root.EvidenceEngine=x;
})(typeof globalThis!=='undefined'?globalThis:this,function(Alpha){
  'use strict';
  const PROTOCOL='research-v0.3';
  const RESEARCH_CANDIDATES=Object.freeze([
    Object.freeze({id:'EMA-04-16',strategy:'ema',fast:4,slow:16}),
    Object.freeze({id:'EMA-08-24',strategy:'ema',fast:8,slow:24}),
    Object.freeze({id:'SMA-06-18',strategy:'sma',fast:6,slow:18}),
    Object.freeze({id:'SMA-10-30',strategy:'sma',fast:10,slow:30})
  ]);
  function folds(bars,{trainPct=60,validationPct=20,embargoBars=1}={}){
    if(!Array.isArray(bars)||bars.length<180)throw Error('Evidence audit requires at least 180 observations.');
    if(!(trainPct>=50&&trainPct<=75&&validationPct>=15&&validationPct<=30&&trainPct+validationPct<=85))throw Error('Invalid research split.');
    if(!Number.isInteger(embargoBars)||embargoBars<1||embargoBars>10)throw Error('Embargo must be 1–10 bars.');
    const n=bars.length,a=Math.floor(n*trainPct/100),b=Math.floor(n*(trainPct+validationPct)/100);
    if(a<50||b-a<40||n-b<30)throw Error('Insufficient observations in a research window.');
    return {training:{startIndex:0,endIndex:a},validation:{startIndex:a+embargoBars,endIndex:b},test:{startIndex:b+embargoBars,endIndex:n},embargoBars};
  }
  function score(result){
    // Selection happens on validation only. No test set inspection during selection.
    // Penalize high drawdown; zero/one completed trades are not a basis for selection.
    if(result.tradeCount<2 || result.netReturnPct<=0 || result.netReturnPct<=result.benchmarkReturnPct)return -Infinity;
    return result.netReturnPct-result.benchmarkReturnPct-0.35*result.maxDrawdownPct;
  }
  function runAudit(bars,options={}){
    const {currency='USDC',trainPct=60,validationPct=20,embargoBars=1,...config}=options;
    const partition=folds(bars,{trainPct,validationPct,embargoBars});
    const base={feeBps:8,slippageBps:12,initialEquity:10000,exposurePct:25,...config};
    if(!(base.feeBps>0)||!(base.slippageBps>0))throw Error('Evidence audit requires nonzero fee and slippage assumptions.');
    const candidates=RESEARCH_CANDIDATES.map(candidate=>{
      const conf={...base,...candidate};
      const train=Alpha.runBacktest(bars,conf,partition.training);
      const validation=Alpha.runBacktest(bars,conf,partition.validation);
      return {id:candidate.id,settings:candidate,train:{netReturnPct:train.netReturnPct,benchmarkReturnPct:train.benchmarkReturnPct,trades:train.tradeCount,maxDrawdownPct:train.maxDrawdownPct},validation:{netReturnPct:validation.netReturnPct,benchmarkReturnPct:validation.benchmarkReturnPct,trades:validation.tradeCount,maxDrawdownPct:validation.maxDrawdownPct},selectionScore:score(validation)};
    });
    const ranked=candidates.slice().sort((a,b)=>b.selectionScore-a.selectionScore);
    const selected=ranked[0];
    const adequate=selected&&Number.isFinite(selected.selectionScore);
    const warnings=[
      'Simulated fills are next-candle open assumptions, not executable quotes or actual trades.',
      'This browser-only selection cannot enforce a sealed holdout or prevent repeated optimisation.',
      'Four fixed candidates are compared; selecting the best introduces multiple-testing risk.',
      'Small samples and a single dataset cannot establish a positive future trading edge.'
    ];
    if(!adequate)warnings.push('No candidate had at least two completed validation trades and a positive net return exceeding the passive comparator; evidence is insufficient.');
    let holdout=null;
    if(adequate){
      const cfg={...base,...selected.settings};
      const r=Alpha.runBacktest(bars,cfg,partition.test);
      const expensive=Alpha.runBacktest(bars,{...cfg,feeBps:Math.min(200,base.feeBps*2),slippageBps:Math.min(500,base.slippageBps*2)},partition.test);
      holdout={netReturnPct:r.netReturnPct,netPnl:r.netPnl,benchmarkReturnPct:r.benchmarkReturnPct,excessVsBenchmarkPct:r.netReturnPct-r.benchmarkReturnPct,maxDrawdownPct:r.maxDrawdownPct,trades:r.tradeCount,feesPaid:r.feesPaid,slippageCost:r.slippageCost,stress2xNetReturnPct:expensive.netReturnPct};
      if(r.tradeCount<10)warnings.push('Test window has fewer than 10 closed trades; no meaningful statistical confidence can be inferred.');
      if(r.netReturnPct<=0||r.netReturnPct<=r.benchmarkReturnPct)warnings.push('Test failed the positive-return or passive benchmark criterion.');
    }
    const minGap=(a,b)=>Date.parse(b.timestamp)-Date.parse(a.timestamp);
    const gaps=[];for(let i=1;i<bars.length;i++)gaps.push(minGap(bars[i-1],bars[i]));
    const sorted=gaps.slice().sort((a,b)=>a-b),median=sorted[Math.floor(sorted.length/2)];
    const irregular=gaps.filter(x=>x>median*2).length;
    if(irregular)warnings.push(irregular+' material time gaps detected: missing periods may bias results.');
    return {protocol:PROTOCOL,currency,datasetRows:bars.length,partition,windows:Object.fromEntries(Object.entries(partition).filter(([k])=>k!=='embargoBars').map(([k,v])=>[k,{...v,from:bars[v.startIndex].timestamp,to:bars[v.endIndex-1].timestamp}])),candidates,selected:adequate?selected.id:null,holdout,dataChecks:{medianIntervalMs:median,largeGaps:irregular},warnings,decision:irregular?'DATA_QUALITY_BLOCKED':!adequate?'INSUFFICIENT_DATA':!holdout||holdout.trades<10?'INSUFFICIENT_TEST_EVIDENCE':holdout.netReturnPct>holdout.benchmarkReturnPct&&holdout.netReturnPct>0&&holdout.stress2xNetReturnPct>0?'RESEARCH_ONLY_PROMISING':'REJECT_OR_RESEARCH_MORE'};
  }
  function estimateAiCost({callsPerDay=0,inputTokensPerCall=300,outputTokensPerCall=100,inputPriceUsdPerMillion=0.5,outputPriceUsdPerMillion=2.5,days=30}={}){
    const nums=[callsPerDay,inputTokensPerCall,outputTokensPerCall,inputPriceUsdPerMillion,outputPriceUsdPerMillion,days];
    if(nums.some(x=>typeof x!=='number'||!Number.isFinite(x)||x<0)||callsPerDay>100000||inputTokensPerCall>100000||outputTokensPerCall>100000||days>365)throw Error('Invalid model usage assumptions.');
    const calls=callsPerDay*days,inputTokens=calls*inputTokensPerCall,outputTokens=calls*outputTokensPerCall;
    return {calls,inputTokens,outputTokens,totalTokens:inputTokens+outputTokens,estimatedUsd:Math.round((inputTokens*inputPriceUsdPerMillion+outputTokens*outputPriceUsdPerMillion)/1e6*100)/100,unit:'USD',note:'User-entered illustrative API prices; no provider prices, cache discounts or FX rates are verified by this calculator.'};
  }
  return Object.freeze({PROTOCOL,RESEARCH_CANDIDATES,folds,runAudit,estimateAiCost});
});
