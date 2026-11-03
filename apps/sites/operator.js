'use strict';
/* Alpha Labs read-only operator UI v0.6. No fetch, no order submission, no credentials. */
(function(){
  const pageNames=Object.freeze({home:'Overview',markets:'Markets',intelligence:'Intelligence',activity:'Activity',settings:'Settings & Advanced'});
  const ids=id=>document.getElementById(id);
  const state={route:'home',demo:false,marketSearch:'',marketFilter:'all',selectedAsset:null,activityFilter:'all'};
  const staticMarkets=[
    {symbol:'BTC',name:'Bitcoin',pair:'BTC / USD'},
    {symbol:'ETH',name:'Ethereum',pair:'ETH / USD'},
    {symbol:'SOL',name:'Solana',pair:'SOL / USD'}
  ];
  const agents=[
    ['Market signals','Price, momentum and regime research'],
    ['Liquidity & execution','Spread, fees and route feasibility'],
    ['Derivatives intelligence','Funding, margin and short eligibility'],
    ['Data integrity','Freshness, timestamp and source verification'],
    ['Research & critique','Exception-based analysis and evidence review'],
    ['Portfolio risk','Independent policy and exposure checks']
  ];
  function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n}
  function text(id,value){ids(id).textContent=String(value)}
  function fmtMoney(n){return new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD',minimumFractionDigits:2,maximumFractionDigits:2}).format(n).replace('$','A$')}
  function fmtUSD(n){return new Intl.NumberFormat('en-AU',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}).format(n)}
  function formatTime(iso){return new Date(iso).toLocaleString('en-AU',{timeZone:'Australia/Brisbane',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:false})+' AEST'}
  function getDemo(){return window.AlphaDemo}
  function resetClasses(node){node.classList.remove('demo-pos','demo-neg','demo-muted')}
  function route(){const name=window.location.hash.replace(/^#/,'');return Object.hasOwn(pageNames,name)?name:'home'}
  function showRoute(name){state.route=Object.hasOwn(pageNames,name)?name:'home';
    for(const node of document.querySelectorAll('[data-view]'))node.classList.toggle('active',node.dataset.view===state.route);
    for(const node of document.querySelectorAll('[data-route]')){const active=node.dataset.route===state.route;node.classList.toggle('active',active);if(active)node.setAttribute('aria-current','page');else node.removeAttribute('aria-current')}
    text('current-section',pageNames[state.route]);document.title=pageNames[state.route]+' — Alpha Labs';window.scrollTo({top:0,behavior:'instant'});
    if(state.route==='markets')renderMarkets();if(state.route==='activity')renderActivity();
  }
  function changeRoute(name){if(window.location.hash==='#'+name)showRoute(name);else window.location.hash=name}
  function setDemo(yes){state.demo=Boolean(yes);ids('demo-toggle').checked=state.demo;ids('demo-banner').hidden=!state.demo;state.selectedAsset=null;
    renderHome();renderMarkets();renderIntelligence();renderActivity();renderAgents();
  }
  function renderHome(){const d=getDemo(),on=state.demo;
    const value=ids('equity-value'),delta=ids('equity-change');resetClasses(value);resetClasses(delta);
    text('equity-provenance',on?'SYNTHETIC DEMO':'NOT CONNECTED');
    text('equity-value',on?fmtMoney(d.equityAUD):'Unavailable');
    text('equity-change',on?`+${fmtMoney(d.changeAUD)} (+${d.changePct.toFixed(2)}%) · fictional scenario`:'No broker or paper ledger connected');
    if(on)delta.classList.add('demo-pos');
    text('realised-pnl',on?fmtMoney(d.realisedAUD)+' (demo)':'—');
    text('unrealised-pnl',on?fmtMoney(d.unrealisedAUD)+' (demo)':'—');
    text('portfolio-costs',on?fmtMoney(d.costsAUD)+' (demo)':'—');
    text('portfolio-note',on?'All values are synthetic and unrelated to live, paper or historical market performance. No broker account exists.':'Values require a reconciled account or modelled paper ledger. An absent result is not zero.');
    text('exposure-value',on?d.exposure.direction+' · '+d.exposure.asset:'None');
    text('exposure-detail',on?`Hypothetical notional: ${fmtMoney(d.exposure.notionalAUD)}. No actual position opened.`:'No connected positions or trading account.');
    text('exposure-status',on?'Synthetic scenario — no order':'Execution not configured');
    text('decision-value',on?'SHORT · SOL/USD':'Not evaluated');
    text('decision-detail',on?'Fictional research candidate. Blocked: short eligibility and executable prices unverified.':'Verified market observations are required before the engine can assess LONG, SHORT or FLAT.');
    text('chart-caption',on?'Fictional 30-day curve · not market history':'No observations available');text('chart-source',on?'SYNTHETIC / NOT TRADED':'RESEARCH ONLY');
    text('risk-summary','Not connected');text('data-summary',on?'Demo fixture only':'No live feed');text('ai-summary','Not deployed');renderChart();
  }
  function renderChart(){const root=ids('equity-chart');root.replaceChildren();if(!state.demo){const empty=el('div','chart-empty');
    const ic=document.createElementNS('http://www.w3.org/2000/svg','svg');ic.setAttribute('class','ico big');const use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#i-chart');ic.append(use);
    empty.append(ic,el('strong','', 'Performance data unavailable'),el('span','','Connect a verified ledger to display a portfolio curve.'));root.append(empty);return;}
    const pts=getDemo().equityCurve,svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 640 245');svg.setAttribute('class','chart-svg');svg.setAttribute('role','img');svg.setAttribute('aria-label','Synthetic demonstration equity curve, fabricated data, not actual profit');
    const make=(tag,attrs)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));return n};
    const defs=make('defs',{}),grad=make('linearGradient',{id:'demo-fill',x1:'0',x2:'0',y1:'0',y2:'1'}),stop1=make('stop',{offset:'0%','stop-color':'#B7F486','stop-opacity':'.22'}),stop2=make('stop',{offset:'100%','stop-color':'#B7F486','stop-opacity':'0'});grad.append(stop1,stop2);defs.append(grad);svg.append(defs);
    const low=Math.min(...pts)-18,high=Math.max(...pts)+18,x=i=>18+i*604/(pts.length-1),y=v=>218-(v-low)*191/(high-low);
    for(let i=0;i<4;i++){const gy=35+i*53;svg.append(make('line',{x1:'0',x2:'640',y1:gy,y2:gy,stroke:'#36433f','stroke-dasharray':'3 7','stroke-width':1}))}
    const path=pts.map((v,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(v).toFixed(1)).join(' ');
    svg.append(make('path',{d:path+` L${x(pts.length-1)} 240 L18 240 Z`,fill:'url(#demo-fill)'}));svg.append(make('path',{d:path,fill:'none',stroke:'#b7f486','stroke-width':3,'stroke-linecap':'round','stroke-linejoin':'round'}));
    svg.append(make('circle',{cx:x(pts.length-1),cy:y(pts.at(-1)),r:5,fill:'#b7f486'}));root.append(svg);
  }
  function makeMarketRow(m){const btn=el('button','market-row'+(state.selectedAsset===m.symbol?' selected':''));btn.type='button';btn.setAttribute('aria-label','View '+m.name+' research details');
    const info=el('div','asset-info'),logo=el('span','asset-icon',m.symbol==='BTC'?'₿':m.symbol==='ETH'?'Ξ':'◎'),infot=el('div',''),name=el('span','asset-name',m.name),sym=el('span','asset-symbol',m.pair);infot.append(name,sym);info.append(logo,infot);
    const signal=el('div','');signal.append(el('span','signal-pill '+(state.demo?m.decision.toLowerCase():'unavailable'),state.demo?m.decision:'NOT EVALUATED'));
    if(state.demo)signal.append(el('span','market-sub',m.edge+' · illustrative'));const eligibility=el('span','eligibility','RESEARCH ONLY');const chev=document.createElementNS('http://www.w3.org/2000/svg','svg');chev.setAttribute('class','ico market-chevron');const use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#i-chevron');chev.append(use);
    btn.append(info,signal,eligibility,chev);btn.addEventListener('click',()=>{state.selectedAsset=state.selectedAsset===m.symbol?null:m.symbol;renderMarkets();});return btn;
  }
  function renderMarkets(){const d=getDemo(),all=staticMarkets.map(m=>({...m,...(state.demo?d.markets.find(x=>x.symbol===m.symbol):{})}));
    const needle=state.marketSearch.trim().toLowerCase();const items=all.filter(m=>(m.name+' '+m.symbol+' '+m.pair).toLowerCase().includes(needle)).filter(m=>state.marketFilter==='all'||(state.demo?m.decision:'UNAVAILABLE')===state.marketFilter);
    const root=ids('market-list');root.replaceChildren();for(const m of items)root.append(makeMarketRow(m));if(!items.length){const e=el('div','empty-results');e.append(el('strong','','No matching markets'),el('p','','Adjust the filters or return to the full research watchlist.'));root.append(e)}
    const details=ids('market-details');details.replaceChildren();const selected=all.find(m=>m.symbol===state.selectedAsset);details.hidden=!selected;if(!selected)return;
    details.append(el('h2','',selected.name+' · '+selected.pair),el('p','',state.demo?selected.details:'No verified market prices, funding, executable quotes, short eligibility or forecasts are connected.'));
    const grid=el('div','detail-grid');const fields=state.demo?[
      ['Price',fmtUSD(selected.price)+' · invented'],['Illustrative movement',(selected.changePct>0?'+':'')+selected.changePct.toFixed(2)+'%'],['Assessment',selected.decision+' · synthetic'],['Market regime',selected.regime+' · synthetic'],['Net edge',selected.edge+' · not validated'],['Execution eligibility','RESEARCH ONLY']
    ]:[['Price','Unavailable'],['Latest quote','Unavailable'],['Assessment','Not evaluated'],['Market regime','Not evaluated'],['Expected net advantage','Unavailable'],['Execution eligibility','RESEARCH ONLY']];
    for(const [k,v] of fields){const cell=el('div','');cell.append(el('span','',k),el('strong','',v));grid.append(cell)}details.append(grid);
  }
  function fillList(id,items){const root=ids(id);root.replaceChildren();if(Array.isArray(items)){const ul=el('ul','');for(const line of items)ul.append(el('li','',line));root.append(ul)}else root.append(el('p','',items))}
  function renderIntelligence(){const on=state.demo,d=getDemo();text('intel-provenance',on?'SYNTHETIC DEMO':'NOT EVALUATED');text('intel-decision',on?'SHORT · '+d.intelligence.asset:'Unavailable');text('intel-context',on?`${d.intelligence.horizon} · ${d.intelligence.edge} · not a real forecast`:'Market, forecast and data source not connected.');
    fillList('intel-reasons',on?d.intelligence.reasons:'Evidence will appear here after independently sourced market observations are evaluated.');
    fillList('intel-challenges',on?d.intelligence.challenges:'Risk, data quality and opposing evidence must be considered before any proposal is approved.');
    text('veto-summary',on?'REJECTED':'Not evaluated');text('veto-detail',on?'Synthetic candidate rejected because shorting eligibility, executable prices and margin data are unavailable. No order submitted.':'The independent risk service is not deployed. No trade can be authorised.');
  }
  function renderAgents(){const root=ids('agent-grid');root.replaceChildren();for(const [name,desc] of agents){const card=el('div','agent-card');card.append(el('strong','',name),el('p','',desc),el('small','','PLANNED · OFFLINE'));root.append(card)}}
  function renderActivity(){const root=ids('activity-list');root.replaceChildren();const events=state.demo?getDemo().activities.filter(x=>state.activityFilter==='all'||state.activityFilter===x.type):[];
    ids('activity-export').disabled=!events.length;text('activity-count',events.length?events.length+' synthetic event'+(events.length!==1?'s':''):'No connected events');
    if(!events.length){const empty=el('div','activity-empty');const ic=document.createElementNS('http://www.w3.org/2000/svg','svg');ic.setAttribute('class','ico');const u=document.createElementNS('http://www.w3.org/2000/svg','use');u.setAttribute('href','#i-clock');ic.append(u);empty.append(ic,el('strong','',state.demo?'No matching synthetic events':'No activity to display'),el('p','',state.demo?'Change the filter to view more demonstration records.':'No broker, paper ledger or market decision stream is connected.'));root.append(empty);return}
    for(const item of events){const row=el('div','activity-row'),ic=el('div','activity-icon');const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','ico');const u=document.createElementNS('http://www.w3.org/2000/svg','use');u.setAttribute('href',item.type==='decision'?'#i-shield':item.type==='research'?'#i-brain':'#i-clock');svg.append(u);ic.append(svg);
      const body=el('div','activity-body');body.append(el('strong','',item.title),el('p','',item.detail),el('span','activity-tag',item.status+' · '+item.id));row.append(ic,body,el('time','activity-date',formatTime(item.time)));root.append(row)}
  }
  function exportActivity(){if(!state.demo)return;const rows=getDemo().activities.filter(x=>state.activityFilter==='all'||state.activityFilter===x.type);if(!rows.length)return;
    const fields=['id','type','title','detail','time','status'];const csv=[fields.join(','),...rows.map(item=>fields.map(f=>'"'+String(item[f]||'').replaceAll('"','""')+'"').join(','))].join('\r\n');
    const blob=new Blob(['# SYNTHETIC DEMO; NOT ACTUAL TRADES\r\n'+csv],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='alpha-labs-SYNTHETIC-demo-activity.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function clock(){text('local-time',new Date().toLocaleString('en-AU',{timeZone:'Australia/Brisbane',hour:'2-digit',minute:'2-digit',hour12:false})+' AEST')}
  document.addEventListener('click',e=>{const action=e.target.closest('[data-action]')?.dataset.action;if(!action)return;
    if(action==='settings')changeRoute('settings');else if(action==='intelligence')changeRoute('intelligence');else if(action==='show-advanced')changeRoute('settings');else if(action==='demo-off'){setDemo(false);changeRoute('home')}});
  ids('market-search').addEventListener('input',e=>{state.marketSearch=e.target.value;renderMarkets()});
  ids('market-filter').addEventListener('change',e=>{state.marketFilter=e.target.value;renderMarkets()});
  ids('activity-filter').addEventListener('change',e=>{state.activityFilter=e.target.value;renderActivity()});
  ids('activity-export').addEventListener('click',exportActivity);
  ids('demo-toggle').addEventListener('change',e=>setDemo(e.target.checked));
  window.addEventListener('hashchange',()=>showRoute(route()));
  clock();setInterval(clock,60000);setDemo(false);showRoute(route());
})();
