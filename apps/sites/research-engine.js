/* Alpha Labs: deterministic, offline-only exploratory research engine.
   No live data access, wallet functionality, order signing or trading API calls. */
(function(root,factory){
  'use strict';
  const exported=factory();
  if(typeof module==='object' && module.exports)module.exports=exported;
  if(root)root.AlphaEngine=exported;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const MAX_ROWS=20000;
  const dayms=86400000;
  function finite(n){return typeof n==='number' && Number.isFinite(n)}
  function round(n,p=8){return Number(n.toFixed(p))}
  function parseCsvRows(text){
    if(typeof text!=='string'||text.length>6_000_000)throw Error('The CSV must be a text file under 6 MB.');
    const result=[];let row=[],cell='',quoted=false;
    for(let i=0;i<text.length;i++){
      const c=text[i];
      if(c==='"'){
        if(quoted&&text[i+1]==='"'){cell+='"';i++;}
        else if(!quoted&&cell.trim().length){throw Error('Unexpected quote in CSV.');}
        else quoted=!quoted;
      }else if((c===','||c==='\n'||c==='\r')&&!quoted){
        row.push(cell.trim());cell='';
        if(c!==','){
          if(row.some(x=>x!==''))result.push(row);
          row=[];
          if(c==='\r'&&text[i+1]==='\n')i++;
          if(result.length>MAX_ROWS+1)throw Error('CSV exceeds 20,000 data rows.');
        }
      }else{cell+=c;}
    }
    if(quoted)throw Error('Unclosed quoted field in CSV.');
    row.push(cell.trim());if(row.some(x=>x!==''))result.push(row);
    return result;
  }
  function parseCsv(text){
    const rows=parseCsvRows(text.replace(/^\uFEFF/,''));
    if(rows.length<31)throw Error('Provide at least 30 price observations plus a header.');
    const names=rows[0].map(x=>x.toLowerCase());
    const required=['timestamp','open','high','low','close'];
    const idx={};for(const name of required){idx[name]=names.indexOf(name);if(idx[name]<0)throw Error('Required column missing: '+name+'.');}
    idx.volume=names.indexOf('volume');
    const bars=[],seen=new Set();let last=-Infinity;
    for(let i=1;i<rows.length;i++){
      const r=rows[i];if(r.length!==rows[0].length)throw Error('CSV row '+(i+1)+' has a different column count.');
      const rawTime=r[idx.timestamp];
      if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(rawTime)||!/(Z|[+-]\d{2}:\d{2})$/i.test(rawTime))throw Error('CSV row '+(i+1)+' needs an ISO-8601 timestamp with timezone.');
      const t=Date.parse(rawTime);if(!finite(t))throw Error('Invalid timestamp on row '+(i+1)+'.');
      if(t<=last||seen.has(t))throw Error('Timestamps must increase strictly, without duplicates (row '+(i+1)+').');
      last=t;seen.add(t);
      const v={timestamp:new Date(t).toISOString()};
      for(const key of ['open','high','low','close']){
        if(r[idx[key]]==='')throw Error('Missing '+key+' value on row '+(i+1)+'.');
        v[key]=Number(r[idx[key]]);
        if(!finite(v[key])||v[key]<=0)throw Error('Invalid '+key+' value on row '+(i+1)+'.');
      }
      if(v.high+1e-9<Math.max(v.open,v.close,v.low)||v.low-1e-9>Math.min(v.open,v.close,v.high))throw Error('Inconsistent OHLC values on row '+(i+1)+'.');
      v.volume=idx.volume<0||r[idx.volume]===''?null:Number(r[idx.volume]);
      if(v.volume!==null&&(!finite(v.volume)||v.volume<0))throw Error('Invalid volume on row '+(i+1)+'.');
      bars.push(v);
    }
    if(bars.length<30)throw Error('At least 30 price observations are required.');
    if(bars.length>MAX_ROWS)throw Error('Maximum 20,000 observations per dataset.');
    return bars;
  }
  function generateDemo(n=360){
    // Fixed synthetic series, designed to demonstrate interface only: not historical markets.
    if(!Number.isInteger(n)||n<60||n>MAX_ROWS)throw Error('Invalid demonstration length.');
    const out=[];let seed=20261102,price=145;
    const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296};
    const start=Date.UTC(2026,5,1,0,0,0);
    for(let i=0;i<n;i++){
      const open=price;
      const drift=i<90?.0011:i<175?-.0014:i<265?.0009:-.0001;
      const shock=(random()-.5)*.025+Math.sin(i/19)*.0025;
      const close=Math.max(1,open*(1+drift+shock));
      const high=Math.max(open,close)*(1+random()*.007);
      const low=Math.min(open,close)*(1-random()*.007);
      out.push({timestamp:new Date(start+i*3600000).toISOString(),open:round(open),high:round(high),low:round(low),close:round(close),volume:round(150000+random()*850000,2)});
      price=close;
    }
    return out;
  }
  const DEFAULTS={strategy:'ema',fast:10,slow:30,feeBps:8,slippageBps:12,exposurePct:25,initialEquity:10000};
  function validateConfig(config,bars){
    const c={...DEFAULTS,...config};
    if(!Array.isArray(bars)||bars.length<30||bars.length>MAX_ROWS)throw Error('A valid price dataset of 30–20,000 bars is required.');
    if(!['ema','sma'].includes(c.strategy))throw Error('Unsupported strategy type.');
    for(const x of ['fast','slow','feeBps','slippageBps','exposurePct','initialEquity'])if(!finite(c[x]))throw Error('Invalid numeric setting: '+x+'.');
    if(!Number.isInteger(c.fast)||!Number.isInteger(c.slow)||c.fast<2||c.slow<5||c.fast>=c.slow||c.slow>=bars.length-1)throw Error('Require integer fast/slow windows: 2 ≤ fast < slow < dataset length - 1.');
    if(c.feeBps<0||c.feeBps>200||c.slippageBps<0||c.slippageBps>500)throw Error('Fee/slippage assumptions exceed permitted range.');
    if(c.exposurePct<=0||c.exposurePct>100||c.initialEquity<=0||c.initialEquity>1e12)throw Error('Invalid equity or exposure setting.');
    return c;
  }
  function indicators(bars,c){
    const closes=bars.map(b=>b.close),f=[],s=[];let ef=closes[0],es=closes[0];
    for(let i=0;i<closes.length;i++){
      ef=i===0?closes[i]:ef+(2/(c.fast+1))*(closes[i]-ef);
      es=i===0?closes[i]:es+(2/(c.slow+1))*(closes[i]-es);
      f.push(ef);s.push(es);
    }
    const sma=[];
    for(let i=0;i<closes.length;i++){
      sma.push(i>=c.slow-1?closes.slice(i-c.slow+1,i+1).reduce((a,b)=>a+b,0)/c.slow:null);
    }
    return {fast:f,slow:s,sma};
  }
  function signal(i,c,bars,ind){
    // Trading at bar i OPEN based only on completed bars through i-1.
    const previous=i-1;if(i<c.slow)return false;
    return c.strategy==='ema'?ind.fast[previous]>ind.slow[previous]:bars[previous].close>ind.sma[previous];
  }
  function maxDrawdown(equity){
    let peak=-Infinity,dd=0;
    for(const n of equity){peak=Math.max(peak,n);if(peak>0)dd=Math.max(dd,(peak-n)/peak*100);}
    return dd;
  }
  function runBacktest(bars,config={},window={}){
    const c=validateConfig(config,bars);
    const begin=window.startIndex===undefined?0:window.startIndex;
    const end=window.endIndex===undefined?bars.length:window.endIndex;
    if(!Number.isInteger(begin)||!Number.isInteger(end)||begin<0||end>bars.length||begin>=end)
      throw Error('Invalid chronological evaluation interval.');
    const first=Math.max(c.slow,begin);
    if(first>=end)throw Error('Evaluation window has no eligible observations after indicator warm-up.');
    const ind=indicators(bars,c),fee=c.feeBps/10000,slip=c.slippageBps/10000;
    let cash=c.initialEquity,qty=0,costBasis=0,entryTs=null,feesPaid=0,slipCost=0;
    const trades=[],fills=[],series=[],benchSeries=[];
    let bc=c.initialEquity,bq=0,benchmarkFees=0;
    for(let i=begin;i<end;i++){
      const bar=bars[i],ts=bar.timestamp;
      if(i>=c.slow){
        const shouldOwn=signal(i,c,bars,ind);
        if(shouldOwn&&qty===0){
          const target=(cash*c.exposurePct/100);
          const effective=bar.open*(1+slip);
          const units=Math.min(target/(effective*(1+fee)),cash/(effective*(1+fee)));
          if(units>1e-12){const gross=units*effective,commission=gross*fee;cash-=gross+commission;qty=units;costBasis=gross+commission;entryTs=ts;feesPaid+=commission;slipCost+=units*(effective-bar.open);fills.push({timestamp:ts,action:'BUY',price:effective,quantity:units,fee:commission,signalBasedOn:bars[i-1].timestamp});}
        }else if(!shouldOwn&&qty>0){
          const effective=bar.open*(1-slip),gross=qty*effective,commission=gross*fee;
          cash+=gross-commission;feesPaid+=commission;slipCost+=qty*(bar.open-effective);
          const netPnL=gross-commission-costBasis;
          trades.push({entryTime:entryTs,exitTime:ts,pnl:netPnL,returnPct:(netPnL/costBasis)*100,qty,exitPrice:effective});
          fills.push({timestamp:ts,action:'SELL',price:effective,quantity:qty,fee:commission,signalBasedOn:bars[i-1].timestamp});
          qty=0;costBasis=0;entryTs=null;
        }
        if(i===first){
          const effective=bar.open*(1+slip),units=(bc*c.exposurePct/100)/(effective*(1+fee));
          const commission=units*effective*fee;bc-=units*effective+commission;bq=units;benchmarkFees+=commission;
        }
      }
      // Open inventory is shown at an estimated net liquidation price, not an executable final fill.
      const estimatedLiquidation=qty*bar.close*(1-slip)*(1-fee);
      const value=cash+estimatedLiquidation;
      const benchmarkValue=bc+bq*bar.close*(1-slip)*(1-fee);
      series.push({timestamp:ts,value:round(value,4)});
      benchSeries.push({timestamp:ts,value:round(benchmarkValue,4)});
    }
    const endEquity=series.at(-1).value;
    const closedWinners=trades.filter(t=>t.pnl>0);
    return {
      config:c,sourceRows:end-begin,start:bars[begin].timestamp,end:bars[end-1].timestamp,window:{startIndex:begin,endIndex:end,firstEligibleIndex:first},
      netPnl:round(endEquity-c.initialEquity,2),netReturnPct:round((endEquity/c.initialEquity-1)*100,3),
      finalEquity:round(endEquity,2),maxDrawdownPct:round(maxDrawdown(series.map(x=>x.value)),3),
      benchmarkPnl:round(benchSeries.at(-1).value-c.initialEquity,2),benchmarkReturnPct:round((benchSeries.at(-1).value/c.initialEquity-1)*100,3),
      tradeCount:trades.length,fillCount:fills.length,winRatePct:trades.length?round(closedWinners.length/trades.length*100,2):null,
      feesPaid:round(feesPaid,2),slippageCost:round(slipCost,2),openPosition:qty>0?{quantity:round(qty),estimatedValue:round(qty*bars.at(-1).close*(1-slip)*(1-fee),2),entryTime:entryTs}:null,
      trades,fills,series,benchmarkSeries:benchSeries,notice:'Exploratory simulation only: bar-open fills are assumptions, not executable quotes; no orderbook depth, price impact, failed fills, taxes, custody costs or API costs.'
    };
  }
  function stressTest(bars,config={}){
    const c=validateConfig(config,bars);
    return [1,1.5,2].map(scale=>{
      const r=runBacktest(bars,{...c,feeBps:Math.min(200,c.feeBps*scale),slippageBps:Math.min(500,c.slippageBps*scale)});
      return {multiplier:scale,returnPct:r.netReturnPct,netPnl:r.netPnl,maxDrawdownPct:r.maxDrawdownPct,closedTrades:r.tradeCount,feesPaid:r.feesPaid,slippageCost:r.slippageCost};
    });
  }
  function csvForBars(bars){return 'timestamp,open,high,low,close,volume\n'+bars.map(b=>[b.timestamp,b.open,b.high,b.low,b.close,b.volume??''].join(',')).join('\n')+'\n'}
  return Object.freeze({MAX_ROWS,DEFAULTS,parseCsv,generateDemo,validateConfig,runBacktest,stressTest,csvForBars,dayms});
});
