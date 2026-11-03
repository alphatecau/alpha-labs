/* Alpha Labs — browser-only research interface. No exchange access or trade execution. */
'use strict';
const STORAGE = 'solana_alpha_lab_v01'; // Retained to preserve existing browser-saved research.
const ENGINE_VERSION = '0.3.0';
const seedHypotheses = [
  {id:'AL-001',name:'Regime-conditioned momentum',market:'SOL/USDC',mechanism:'Trend persistence',thesis:'Test whether price continuation following volatility-adjusted breakouts survives transaction costs and regime changes.',status:'Not tested',system:true},
  {id:'AL-002',name:'Liquidity dislocation',market:'SOL/USDC',mechanism:'Price/liquidity imbalance',thesis:'Test whether short-lived price dislocations exist after all routing, timing, fee and impact costs.',status:'Not tested',system:true},
  {id:'AL-003',name:'Post-volatility mean reversion',market:'SOL/USDC',mechanism:'Temporary overreaction',thesis:'Test whether unusually large short-horizon returns partially reverse when liquidity is sufficient.',status:'Not tested',system:true},
  {id:'AL-004',name:'Post-launch stabilisation',market:'Other',mechanism:'Launch lifecycle',thesis:'Test whether screened post-launch tokens show a defensible pattern after manipulative activity and unexitable pools are excluded.',status:'Not tested',system:true}
];
const roadmap = [
  {weeks:'WEEKS 01–02',title:'Research foundation',body:'Lock market universe, data contracts, hypothesis registry, budget and threat model. Build clean source-controlled scaffolding.'},
  {weeks:'WEEK 03',title:'Deterministic backtest',body:'Reconstruct point-in-time decisions, execution costs and accounting with reproducible historical replay.'},
  {weeks:'WEEKS 04–05',title:'Alpha hypothesis evaluation',body:'Test registered strategies; control data leakage, overfitting, multiple comparisons and cost sensitivity.'},
  {weeks:'WEEK 06',title:'First evidence gate',body:'Reject unsupported strategies. Proceed only where evidence justifies further engineering.'},
  {weeks:'WEEKS 07–09',title:'Shadow mode and independent risk',body:'Integrate real-time signals and executable quotes; simulate order lifecycles and enforce exposure limits.'},
  {weeks:'WEEKS 10–12',title:'Operational platform beta',body:'Implement essential dashboard, alerting, security, recovery tests and independent paper-only hosting.'},
  {weeks:'WEEKS 13–15',title:'Frozen forward evaluation',body:'Collect unseen market observations, measure quote deviations and preserve every decision in an audit trail.'},
  {weeks:'WEEK 16',title:'Formal go/no-go review',body:'Produce technical, statistical and economic assessments; continue testing or reject unsupported strategies.'}
];
const $=id=>document.getElementById(id);
const money = n => new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD',maximumFractionDigits:2}).format(Number.isFinite(n)?n:0);
function getSaved(){try{const v=JSON.parse(localStorage.getItem(STORAGE)||'{}');return v && typeof v==='object'?v:{}}catch{return {}}}
let store=getSaved();
if(!Array.isArray(store.hypotheses)) store.hypotheses=seedHypotheses;
if(!Array.isArray(store.milestones)) store.milestones=[];
if(!store.risk||typeof store.risk!=='object') store.risk={equity:10000,price:200,riskPct:.25,stopPct:4,costPct:.4,capPct:10};
function persist(){try{localStorage.setItem(STORAGE,JSON.stringify(store))}catch{showToast('Storage unavailable. Export your work to keep a copy.')}}
function showToast(message){const el=$('toast');el.textContent=message;el.hidden=false;clearTimeout(showToast.timer);showToast.timer=setTimeout(()=>el.hidden=true,3300)}
const pageNames={overview:'Overview',research:'Alpha research',backtest:'Backtest studio',evidence:'Evidence audit',risk:'Risk laboratory',roadmap:'Development plan',architecture:'Architecture'};
function showPage(page){if(!(page in pageNames))page='overview';document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active',p.id==='page-'+page));document.querySelectorAll('.nav-item').forEach(n=>{const selected=n.dataset.page===page;n.classList.toggle('active',selected);n.setAttribute('aria-current',selected?'page':'false')});$('crumb-page').textContent=pageNames[page];document.title=pageNames[page]+' — Alpha Labs';$('sidebar').classList.remove('open');$('scrim').hidden=true;$('menu-button').setAttribute('aria-expanded','false');window.scrollTo({top:0,behavior:'instant'});if(location.hash!=='#'+page)history.replaceState(null,'','#'+page)}
document.addEventListener('click',e=>{const link=e.target.closest('[data-page]');if(link){e.preventDefault();showPage(link.dataset.page)}});
$('menu-button').addEventListener('click',()=>{$('sidebar').classList.toggle('open');const open=$('sidebar').classList.contains('open');$('scrim').hidden=!open;$('menu-button').setAttribute('aria-expanded',String(open))});$('scrim').addEventListener('click',()=>{$('sidebar').classList.remove('open');$('scrim').hidden=true;$('menu-button').setAttribute('aria-expanded','false')});
window.addEventListener('hashchange',()=>showPage(location.hash.slice(1)));
function makeCell(tag,text,sub){const el=document.createElement(tag);const top=document.createElement(tag==='td'?'strong':'span');top.textContent=text;el.appendChild(top);if(sub){const small=document.createElement('small');small.textContent=sub;el.appendChild(small)}return el}
function renderHypotheses(){const filter=$('filter-market').value;const rows=store.hypotheses.filter(h=>filter==='all'||h.market===filter);const tbody=$('hypothesis-body');tbody.replaceChildren();for(const h of rows){const tr=document.createElement('tr');tr.appendChild(makeCell('td',h.name,h.id));tr.appendChild(makeCell('td',h.market));tr.appendChild(makeCell('td',h.mechanism||'Unclassified'));const td=document.createElement('td');const b=document.createElement('span');b.className='pill unverified';b.textContent='NOT TESTED';td.appendChild(b);tr.appendChild(td);const last=document.createElement('td');const button=document.createElement('button');button.className='button subtle small';button.textContent='View thesis ↗';button.addEventListener('click',()=>showThesis(h));last.appendChild(button);tr.appendChild(last);tbody.appendChild(tr)}$('research-total').textContent=store.hypotheses.length;$('metric-hypotheses').textContent=String(store.hypotheses.length).padStart(2,'0');if(!rows.length){const tr=document.createElement('tr');const td=document.createElement('td');td.colSpan=5;td.textContent='No registered hypotheses in this filter.';tr.appendChild(td);tbody.appendChild(tr)}}
function showThesis(h){const wrap=document.createElement('div');const main=document.createElement('p');main.textContent=h.thesis;const falsifier=document.createElement('p');falsifier.textContent='Falsification criterion: '+(h.falsifier||'Not specified in the original registry entry.');const evidence=document.createElement('p');evidence.textContent='Evidence required: '+(h.evidence||'Not specified in the original registry entry.');const notice=document.createElement('p');notice.textContent='Status: Not independently tested. No verified trading results or scientific approval attached.';notice.style.color='#a4ba9f';notice.style.fontSize='12px';wrap.append(main,falsifier,evidence,notice);openModal('Research thesis',wrap,false)}
let previousFocus=null;
function openModal(title,content,showForm){previousFocus=document.activeElement;$('modal-title').textContent=title;const form=$('register-form');const old=$('thesis-view');if(old)old.remove();form.hidden=!showForm;if(content){const div=document.createElement('div');div.id='thesis-view';div.style.lineHeight='1.7';div.style.color='#d7e5d3';div.appendChild(content);form.before(div)}$('register-modal').hidden=false;if(showForm)form.elements.name.focus();else $('close-modal').focus()}
function closeModal(){$('register-modal').hidden=true;$('register-form').hidden=false;const old=$('thesis-view');if(old)old.remove();if(previousFocus&&previousFocus.isConnected)previousFocus.focus();previousFocus=null}
$('open-register').addEventListener('click',()=>openModal('Register a hypothesis',null,true));['close-modal','cancel-modal'].forEach(id=>$(id).addEventListener('click',closeModal));$('register-modal').addEventListener('click',e=>{if(e.target===$('register-modal'))closeModal()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('register-modal').hidden)closeModal();if(e.key==='Escape'&&$('sidebar').classList.contains('open')){$('sidebar').classList.remove('open');$('scrim').hidden=true;$('menu-button').setAttribute('aria-expanded','false')}if(e.key==='Tab'&&!$('register-modal').hidden){const nodes=[...$('register-modal').querySelectorAll('button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled])')].filter(n=>n.offsetParent!==null);if(!nodes.length)return;const first=nodes[0],last=nodes.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}});
$('register-form').addEventListener('submit',e=>{e.preventDefault();const fields=new FormData(e.target);const name=String(fields.get('name')||'').trim();const thesis=String(fields.get('thesis')||'').trim();const falsifier=String(fields.get('falsifier')||'').trim();const evidence=String(fields.get('evidence')||'').trim();const market=String(fields.get('market')||'Other');if(!name||!thesis||!falsifier)return;const existing=store.hypotheses.map(h=>parseInt(h.id.replace('AL-',''),10)).filter(Number.isFinite);const next=Math.max(0,...existing)+1;store.hypotheses.push({id:'AL-'+String(next).padStart(3,'0'),name,market,thesis,falsifier,evidence,mechanism:'New research idea',status:'Not tested',createdAt:new Date().toISOString()});persist();renderHypotheses();e.target.reset();closeModal();showToast('Hypothesis registered locally. No validation has been performed.')});
$('filter-market').addEventListener('change',renderHypotheses);
$('export-registry').addEventListener('click',()=>download('alpha-lab-hypotheses.json',JSON.stringify({exportedAt:new Date().toISOString(),status:'Unverified research ideas',hypotheses:store.hypotheses},null,2),'application/json'));
function download(filename,text,mime){const blob=new Blob([text],{type:mime});const href=URL.createObjectURL(blob);const a=document.createElement('a');a.href=href;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(href),1000);showToast('Export prepared: '+filename)}
const riskInputs=[['equity','equity'],['price','price'],['risk-pct','riskPct'],['stop-pct','stopPct'],['cost-pct','costPct'],['cap-pct','capPct']];
function updateRisk(){const r=store.risk;const equity=Math.max(0,+r.equity||0),price=Math.max(.01,+r.price||.01),riskPct=+r.riskPct,stopPct=+r.stopPct,costPct=+r.costPct,capPct=+r.capPct;const riskBudget=equity*riskPct/100;const perUnitLoss=price*(stopPct+costPct)/100;const qty=Math.max(0,Math.min(perUnitLoss?riskBudget/perUnitLoss:0,equity*capPct/100/price));const notional=qty*price;const fees=notional*costPct/100;const potentialLoss=notional*(stopPct+costPct)/100;$('risk-pct-label').textContent=riskPct.toFixed(2)+'%';$('stop-pct-label').textContent=stopPct.toFixed(1)+'%';$('cost-pct-label').textContent=costPct.toFixed(2)+'%';$('cap-pct-label').textContent=capPct.toFixed(0)+'%';$('position-aud').textContent=money(notional);$('risk-budget').textContent=money(riskBudget);$('position-qty').textContent=qty.toFixed(4)+' units';$('position-fees').textContent=money(fees);$('potential-loss').textContent=money(potentialLoss);$('exposure-ratio').textContent=(equity?notional/equity*100:0).toFixed(2)+'%'}
for(const [id,key] of riskInputs){$(id).value=store.risk[key];$(id).addEventListener('input',e=>{const value=Number(e.target.value);store.risk[key]=Number.isFinite(value)?value:0;updateRisk();persist()})}
$('reset-risk').addEventListener('click',()=>{store.risk={equity:10000,price:200,riskPct:.25,stopPct:4,costPct:.4,capPct:10};for(const [id,key]of riskInputs)$(id).value=store.risk[key];updateRisk();persist();showToast('Illustrative risk parameters reset.')});
function renderRoadmap(){const container=$('timeline');container.replaceChildren();roadmap.forEach((m,i)=>{const row=document.createElement('label');row.className='milestone'+(store.milestones.includes(i)?' done':'');const cb=document.createElement('input');cb.type='checkbox';cb.checked=store.milestones.includes(i);cb.setAttribute('aria-label','Mark milestone '+(i+1)+' tracked');cb.addEventListener('change',()=>{if(cb.checked&&!store.milestones.includes(i))store.milestones.push(i);if(!cb.checked)store.milestones=store.milestones.filter(x=>x!==i);persist();renderRoadmap()});const content=document.createElement('div');const label=document.createElement('span');label.className='weeks';label.textContent=m.weeks;const title=document.createElement('h3');title.textContent=m.title;const p=document.createElement('p');p.textContent=m.body;content.append(label,title,p);row.append(cb,content);container.appendChild(row)});$('roadmap-progress-label').textContent=store.milestones.length+' / '+roadmap.length+' milestones tracked';$('roadmap-progress').style.width=(100*store.milestones.length/roadmap.length)+'%'}
$('reset-roadmap').addEventListener('click',()=>{if(store.milestones.length&&!confirm('Clear locally tracked milestone checkboxes?'))return;store.milestones=[];persist();renderRoadmap();showToast('Local milestone tracking reset.')});
function updateClock(){const d=new Date();$('clock').textContent=new Intl.DateTimeFormat('en-AU',{timeZone:'Australia/Brisbane',hour:'2-digit',minute:'2-digit',hour12:false}).format(d)+' AEST'}
/* Bootstrap deliberately deferred to the end of the module: all const state must be initialised first. */


/* OFFLINE BACKTEST STUDIO — No exchange integrations. No real trading or authenticated data. */
const bt = {bars:null,source:null,lastRun:null,filename:null,fingerprint:null};
const btFields = {
  strategy:'bt-strategy',fast:'bt-fast',slow:'bt-slow',feeBps:'bt-fee',
  slippageBps:'bt-slip',exposurePct:'bt-exposure',initialEquity:'bt-capital'
};
function btMoney(n){
  const value=Number(n),currency=$('bt-currency').value;
  if(currency==='AUD')return money(value);
  const prefix=currency==='USD'?'US$':currency==='USDC'?'USDC ':'QUOTE ';
  return prefix+new Intl.NumberFormat('en-AU',{minimumFractionDigits:2,maximumFractionDigits:2}).format(value);
}
function btConfig(){
  const c={currency:$('bt-currency').value};
  for(const [key,id] of Object.entries(btFields))c[key]=key==='strategy'?$(id).value:Number($(id).value);
  return c;
}
function btClearResults(){
  bt.lastRun=null;
  $('export-backtest').disabled=true;
  $('bt-result-status').textContent='Run the model to produce exploratory results.';
  for(const id of ['bt-return','bt-pnl','bt-benchmark','bt-drawdown','bt-trades','bt-winrate'])$(id).textContent='—';
  $('bt-chart').replaceChildren();
  $('bt-open-note').textContent='Results will appear after a local simulation.';
  $('bt-audit').textContent='No completed simulation for this dataset.';
  $('bt-stress-rows').replaceChildren();
  $('bt-trade-rows').replaceChildren();
}
async function btHashDataset(bars){
  if(!globalThis.crypto?.subtle){if(bt.bars===bars)$('bt-dataset-fingerprint').textContent='SHA-256 unavailable in this viewing environment.';return}
  try{
    const encoded=new TextEncoder().encode(JSON.stringify(bars));
    const raw=await crypto.subtle.digest('SHA-256',encoded);
    const digest=Array.from(new Uint8Array(raw)).map(v=>v.toString(16).padStart(2,'0')).join('');
    if(bt.bars===bars){bt.fingerprint=digest;$('bt-dataset-fingerprint').textContent='Normalised dataset SHA-256: '+digest.slice(0,20)+'…';}
  }catch{if(bt.bars===bars)$('bt-dataset-fingerprint').textContent='Dataset hash could not be calculated.'}
}
function btSetDataset(bars,name,kind){
  bt.bars=bars;bt.filename=name;bt.source=kind;bt.fingerprint=null;btClearResults();
  if($('ev-data-source'))$('ev-data-source').textContent='Dataset: '+(kind==='synthetic'?'SYNTHETIC DEMO':'USER CSV / UNVERIFIED')+' · '+bars.length+' bars';
  if($('ev-verdict'))$('ev-verdict').textContent='Dataset changed. Prior audit is not applicable; run the experiment again.';
  if($('ev-export'))$('ev-export').disabled=true;
  $('bt-source-tag').textContent=kind==='synthetic'?'SYNTHETIC DEMO':'USER CSV / UNVERIFIED';
  $('bt-dataset-name').textContent=name;
  $('bt-dataset-rows').textContent=bars.length.toLocaleString('en-AU')+' observations · '+(kind==='synthetic'?'simulated prices':'user-supplied prices, not independently authenticated');
  const friendly=t=>new Date(t).toLocaleString('en-AU',{timeZone:'UTC',year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit'});
  $('bt-dataset-range').textContent=friendly(bars[0].timestamp)+' – '+friendly(bars.at(-1).timestamp)+' UTC';
  const gaps=[];
  for(let i=1;i<bars.length;i++)gaps.push(Date.parse(bars[i].timestamp)-Date.parse(bars[i-1].timestamp));
  const ordered=gaps.slice().sort((a,b)=>a-b),median=ordered[Math.floor(ordered.length/2)];
  const wide=gaps.filter(v=>v>median*2).length;
  $('bt-dataset-quality').textContent=wide?('Data quality caution: '+wide+' intervals exceed twice the median spacing; possible missing periods.'):'Spacing check: no intervals exceed twice the median.';
  $('bt-dataset-fingerprint').textContent='Computing normalised dataset SHA-256…';
  void btHashDataset(bars);
  $('bt-error').hidden=true;
}
function btError(message){
  $('bt-error').hidden=false;
  $('bt-error').textContent=message;
  showToast('Backtest: '+message);
}
function btTextCell(tag,text){const el=document.createElement(tag);el.textContent=String(text);return el}
function btRows(id,columns,rows,empty){
  const root=$(id);root.replaceChildren();
  if(!rows.length){const tr=document.createElement('tr');const td=btTextCell('td',empty);td.colSpan=columns.length;tr.appendChild(td);root.appendChild(tr);return}
  for(const values of rows){const tr=document.createElement('tr');for(const value of values)tr.appendChild(btTextCell('td',value));root.appendChild(tr)}
}
function btPercent(v){return (v>=0?'+':'')+v.toFixed(2)+'%'}
function btDrawChart(strategy,benchmark){
  const holder=$('bt-chart');holder.replaceChildren();
  if(!strategy?.length)return;
  const width=900,height=310,pad={left:91,right:20,top:19,bottom:36};
  const vals=[...strategy.map(s=>s.value),...benchmark.map(s=>s.value)];
  let lo=Math.min(...vals),hi=Math.max(...vals);
  if(!(hi>lo)){lo*=.98;hi*=1.02}
  const margin=(hi-lo)*.07;lo-=margin;hi+=margin;
  const x=i=>pad.left+(width-pad.left-pad.right)*i/(strategy.length-1);
  const y=v=>pad.top+(height-pad.top-pad.bottom)*(1-(v-lo)/(hi-lo));
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','Offline simulated strategy equity versus passive comparison, both in Australian dollars');
  const add=(tag,attrs,txt)=>{const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs||{}))el.setAttribute(k,String(v));if(txt!==undefined)el.textContent=txt;svg.appendChild(el);return el};
  for(let i=0;i<=4;i++){
    const val=lo+(hi-lo)*i/4,py=y(val);
    add('line',{x1:pad.left,y1:py,x2:width-pad.right,y2:py,stroke:'#304034','stroke-width':1,'stroke-dasharray':'3 7'});
    add('text',{x:pad.left-12,y:py+4,'text-anchor':'end',fill:'#93ad94','font-size':12},new Intl.NumberFormat('en-AU',{maximumFractionDigits:0}).format(val));
  }
  const dates=[0,Math.floor((strategy.length-1)/2),strategy.length-1];
  for(const i of dates){const d=new Date(strategy[i].timestamp).toLocaleDateString('en-AU',{month:'short',day:'numeric',year:'2-digit',timeZone:'UTC'});add('text',{x:x(i),y:height-8,'text-anchor':i===0?'start':i===strategy.length-1?'end':'middle',fill:'#8ba28e','font-size':12},d)}
  const plot=(points,color,dash)=>{
    const step=Math.max(1,Math.ceil(points.length/700));
    const pairs=[];for(let i=0;i<points.length;i+=step)pairs.push(`${x(i).toFixed(2)},${y(points[i].value).toFixed(2)}`);
    if((points.length-1)%step!==0)pairs.push(`${x(points.length-1).toFixed(2)},${y(points.at(-1).value).toFixed(2)}`);
    const poly=add('polyline',{points:pairs.join(' '),fill:'none',stroke:color,'stroke-width':2.5,'stroke-linejoin':'round','stroke-linecap':'round'});
    if(dash)poly.setAttribute('stroke-dasharray','7 5');
  };
  plot(benchmark,'#819f90',true);plot(strategy,'#c5f58a',false);
  holder.appendChild(svg);
}
function btAudit(result){
  const el=$('bt-audit');el.replaceChildren();
  const rows=[
    ['Source',bt.source==='synthetic'?'Synthetic demo — not market data':'User-provided CSV — not authenticated'],
    ['Engine','Local deterministic replay v'+ENGINE_VERSION],
    ['Quote currency',result.config.currency],
    ['Execution','Next-bar open, assumed per-side costs'],
    ['Modelled fills',String(result.fillCount)],
    ['Actual model fees charged',btMoney(result.feesPaid)],
    ['Modelled slippage cost',btMoney(result.slippageCost)],
    ['Open inventory',result.openPosition?'Yes — marked for estimated liquidation':'None'],
    ['Real transactions','Zero · no network requests']
  ];
  for(const [label,value]of rows){const div=document.createElement('div');div.className='bt-audit-row';div.append(btTextCell('span',label),btTextCell('strong',value));el.appendChild(div)}
}
function btRun(){
  if(!bt.bars)return btError('A dataset is required before simulation.');
  try{
    const config=btConfig();
    const result=AlphaEngine.runBacktest(bt.bars,config);
    const stress=AlphaEngine.stressTest(bt.bars,config);
    bt.lastRun={result,stress,config,runAt:new Date().toISOString(),dataset:{name:bt.filename,source:bt.source,rows:bt.bars.length}};
    $('bt-error').hidden=true;
    $('export-backtest').disabled=false;
    $('bt-result-status').textContent=bt.source==='synthetic'?'Synthetic demonstration — generated prices, not historical Solana returns.':'User-imported data — local exploratory replay; source and fills are not independently verified.';
    $('bt-result-badge').textContent=bt.source==='synthetic'?'SYNTHETIC / DEMO':'IMPORTED / UNVERIFIED';
    $('bt-return').textContent=btPercent(result.netReturnPct);
    $('bt-pnl').textContent=btMoney(result.netPnl);
    $('bt-benchmark').textContent=btPercent(result.benchmarkReturnPct);
    $('bt-drawdown').textContent=result.maxDrawdownPct.toFixed(2)+'%';
    $('bt-chart-currency').textContent='Modelled net liquidation value · '+config.currency;
    $('bt-trade-currency').textContent='NET P&L ('+config.currency+')';
    $('bt-trades').textContent=String(result.tradeCount);
    $('bt-winrate').textContent=result.winRatePct===null?'N/A':result.winRatePct.toFixed(1)+'%';
    $('bt-open-note').textContent=(result.openPosition?'Final position remains open and is valued using an estimated liquidation price. ':'No final open inventory. ')+result.notice;
    btDrawChart(result.series,result.benchmarkSeries);
    btAudit(result);
    btRows('bt-stress-rows',['x','return','drawdown','trades'],stress.map(x=>[
      x.multiplier.toFixed(1)+'×',btPercent(x.returnPct),x.maxDrawdownPct.toFixed(2)+'%',String(x.closedTrades)
    ]),'No stress results.');
    btRows('bt-trade-rows',['entry','exit','pnl','return'],result.trades.slice(-40).reverse().map(t=>[
      t.entryTime.replace('T',' ').slice(0,16),t.exitTime.replace('T',' ').slice(0,16),btMoney(t.pnl),btPercent(t.returnPct)
    ]),result.openPosition?'No completed positions — open inventory remains.':'No completed positions in this replay.');
    showToast('Offline replay completed. Results are exploratory only.');
  }catch(err){btClearResults();btError(err instanceof Error?err.message:'Simulation could not run.');}
}
function initBacktestStudio(){
  if(typeof AlphaEngine==='undefined'){btError('Research engine not loaded. Check that research-engine.js is present.');return}
  btSetDataset(AlphaEngine.generateDemo(),'Synthetic hourly demonstration · fixed seed 20261102','synthetic');
  if(store.backtestSettings&&typeof store.backtestSettings==='object'){
    for(const [key,id]of Object.entries(btFields)){
      const value=store.backtestSettings[key];
      if(value!==undefined&&value!==null)$(id).value=value;
    }
    if(['AUD','USD','USDC','QUOTE'].includes(store.backtestSettings.currency))$('bt-currency').value=store.backtestSettings.currency;
  }
  $('bt-form').addEventListener('submit',e=>{
    e.preventDefault();
    store.backtestSettings=btConfig();persist();btRun();
  });
  $('bt-demo').addEventListener('click',()=>{btSetDataset(AlphaEngine.generateDemo(),'Synthetic hourly demonstration · fixed seed 20261102','synthetic');btRun();});
  $('bt-file').addEventListener('change',async e=>{
    const file=e.target.files?.[0];if(!file)return;
    try{
      if(file.size>6_000_000)throw Error('CSV is larger than 6 MB.');
      const bars=AlphaEngine.parseCsv(await file.text());
      btSetDataset(bars,file.name,'csv');btRun();
    }catch(err){btError(err instanceof Error?err.message:'Could not read this CSV.');}
    finally{e.target.value='';}
  });
  $('bt-template').addEventListener('click',()=>{
    const rows=AlphaEngine.generateDemo(65);
    download('alpha-labs-SYNTHETIC-example.csv',AlphaEngine.csvForBars(rows),'text/csv');
  });
  $('export-backtest').addEventListener('click',()=>{
    if(!bt.lastRun)return;
    const report={schemaVersion:'0.3',createdAt:new Date().toISOString(),normalizedDatasetSHA256:bt.fingerprint,warning:'OFFLINE RESEARCH ONLY. This is not independent validation or a live trading record.',...bt.lastRun};
    download('alpha-labs-replay-report.json',JSON.stringify(report,null,2),'application/json');
  });
  btRun(); // Default demonstration is visibly labelled SYNTHETIC throughout the UI.
}


/* V0.3 EVIDENCE LAB — selection and costs run locally, no AI call or exchange access. */
let evLast=null;
const evInputs=['ev-calls','ev-input','ev-output','ev-input-price','ev-output-price'];
function evCost(){
  try{
    const d=EvidenceEngine.estimateAiCost({
      callsPerDay:Number($('ev-calls').value),inputTokensPerCall:Number($('ev-input').value),
      outputTokensPerCall:Number($('ev-output').value),inputPriceUsdPerMillion:Number($('ev-input-price').value),
      outputPriceUsdPerMillion:Number($('ev-output-price').value)
    });
    $('ev-monthly').textContent='US$'+d.estimatedUsd.toFixed(2);
    $('ev-tokens').textContent=d.totalTokens.toLocaleString('en-AU');
  }catch{$('ev-monthly').textContent='Invalid settings';$('ev-tokens').textContent='—'}
}
evInputs.forEach(id=>$(id).addEventListener('input',evCost));evCost();
$('ev-run').addEventListener('click',()=>{
  try{
    evLast=EvidenceEngine.runAudit(bt.bars,btConfig());
    const report=evLast;
    $('ev-error').hidden=true;$('ev-export').disabled=false;
    $('ev-badge').textContent=bt.source==='synthetic'?'SYNTHETIC / NOT EVIDENCE':'IMPORTED / UNVERIFIED';
    $('ev-verdict').textContent='Research decision: '+report.decision.replaceAll('_',' ')+(bt.source==='synthetic'?' · SYNTHETIC DATA; NO PROFIT CLAIM':' · SOURCE UNVERIFIED');
    btRows('ev-candidates',['name','train','val','trades','selected'],report.candidates.map(c=>[c.id,btPercent(c.train.netReturnPct),btPercent(c.validation.netReturnPct),String(c.validation.trades),c.id===report.selected?'Selected':'—']),'No candidates.');
    const r=report.holdout;
    $('ev-return').textContent=r?btPercent(r.netReturnPct):'—';
    $('ev-excess').textContent=r?btPercent(r.excessVsBenchmarkPct):'—';
    $('ev-stress').textContent=r?btPercent(r.stress2xNetReturnPct):'—';
    $('ev-trades').textContent=r?String(r.trades):'—';
    $('ev-drawdown').textContent=r?r.maxDrawdownPct.toFixed(2)+'%':'—';
    const warnings=$('ev-warnings');warnings.replaceChildren();
    for(const message of report.warnings){const p=document.createElement('p');p.className='footnote';p.textContent='• '+message;warnings.appendChild(p)}
    showToast('Offline evidence check completed. No trading has occurred.');
  }catch(e){evLast=null;$('ev-export').disabled=true;$('ev-error').hidden=false;$('ev-error').textContent=e instanceof Error?e.message:'Evaluation failed.';}
});
$('ev-export').addEventListener('click',()=>{
  if(!evLast)return;
  const report={schemaVersion:'0.3',createdAt:new Date().toISOString(),source:bt.source,filename:bt.filename,datasetSHA256:bt.fingerprint,
    warning:'Exploratory browser-only audit; no independent market provenance, sealed holdout, real fills or verified profits.',audit:evLast,
    aiBudget:EvidenceEngine.estimateAiCost({callsPerDay:Number($('ev-calls').value),inputTokensPerCall:Number($('ev-input').value),outputTokensPerCall:Number($('ev-output').value),inputPriceUsdPerMillion:Number($('ev-input-price').value),outputPriceUsdPerMillion:Number($('ev-output-price').value)})};
  download('alpha-lab-v03-evidence-audit.json',JSON.stringify(report,null,2),'application/json');
});

renderHypotheses();updateRisk();renderRoadmap();updateClock();setInterval(updateClock,60000);initBacktestStudio();showPage(location.hash.slice(1)||'overview');
