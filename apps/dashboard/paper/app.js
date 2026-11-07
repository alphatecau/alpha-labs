'use strict';
(() => {
  let token = '', snapshot = null, catalog = null, busy = false;
  const $ = id => document.getElementById(id);
  const titles = {overview:'Account overview',markets:'Global market scanner',committee:'AI trading committee',journal:'Trading journal',evidence:'Strategy evidence',controls:'Autonomous control centre'};
  const labels = {overview:'Overview',markets:'Market scanner',committee:'Agent committee',journal:'Trading journal',evidence:'Strategy evidence',controls:'Control centre'};
  const money = value => new Intl.NumberFormat('en-AU',{style:'currency',currency:snapshot?.account.currency || 'AUD',maximumFractionDigits:2}).format(Number(value));
  const pct = value => (Number(value)*100).toFixed(2)+'%';
  function message(text,error=false) { $('message').textContent=text; $('message').classList.toggle('error',error); }
  function node(tag,text,className) { const el=document.createElement(tag); if(text!==undefined) el.textContent=text; if(className) el.className=className; return el; }
  function row(label,detail,value) {const el=node('div',undefined,'row'),left=node('div');left.append(node('b',label),node('small',detail));el.append(left,node('span',value,'value'));return el;}
  async function api(path, body) {
    const response=await fetch('/api/v1/'+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{}),cache:'no-store'});
    const value=await response.json();
    if(!response.ok) throw new Error(response.status===401||response.status===403?'Access denied. Reconnect with a valid local operator token.':response.status===429?'Request limit reached. Wait one minute before trying again.':'Request unavailable. Inspect the local service and account state.');
    return value;
  }
  function view(name) {
    document.querySelectorAll('[data-panel]').forEach(el=>el.hidden=el.dataset.panel!==name);
    document.querySelectorAll('[data-view]').forEach(el=>{el.classList.toggle('selected',el.dataset.view===name);if(el.dataset.view===name)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
    $('page-name').textContent=labels[name];$('section-title').textContent=titles[name];
  }
  function render() {
    const a=snapshot.account,analytics=snapshot.analytics;
    $('workspace').hidden=false; $('login').hidden=true; $('signout').hidden=false;
    $('operator-label').textContent='ACCOUNT / '+a.id+' · '+a.currency;
    $('equity').textContent=money(a.last_equity);$('pnl').textContent=money(analytics.net_pnl);
    $('drawdown').textContent=pct(analytics.current_drawdown);$('fees').textContent=money(a.fees);
    $('currency-note').textContent=a.currency+' · synthetic funds';
    $('account-status').textContent=a.halted?'HALTED':a.enabled?'Paper session enabled':'Paper session suspended';
    $('updated-at').textContent='Marked '+new Date(a.last_time).toLocaleString('en-AU');
    $('risk-badge').textContent=a.halted?'PERSISTENT HALT':'FIXED POLICY';
    $('positions').replaceChildren(...(snapshot.positions.length?snapshot.positions.map(p=>row(p.instrument,p.quantity+' units · stop '+money(p.stop_price),money(p.unrealised_pnl))):[node('div','No open simulated positions.','empty')]));
    const limits=[['Planned position loss',a.limits.position_loss],['Aggregate stop-risk',a.limits.aggregate_stop_risk],['Daily loss suspension',a.limits.daily_loss],['Drawdown suspension',a.limits.drawdown],['Notional ceiling',a.limits.notional]];
    $('risk-limits').replaceChildren(...limits.map(([k,v])=>row(k,'Maximum of account equity',pct(v))));
    $('markets').replaceChildren(...catalog.markets.map(m=>row(m.instrument,'Feed not connected · licensing and eligibility unverified',m.status)));
    $('strategies').replaceChildren(...catalog.strategies.map(s=>row(s.id,s.status==='REJECTED'?'Historical rejection preserved':'Synthetic software fixture only',s.status==='REJECTED'?'REJECTED':'FIXTURE ONLY')));
    const last=[...snapshot.journal].reverse().find(e=>e.kind==='DECISION');
    const cards=(last?.payload.assessments || []).map(a=>{const card=node('article',undefined,'agent-card'),header=node('header');header.append(node('strong',a.agent_id.replaceAll('_',' ').toUpperCase()),node('span',a.status));card.append(header,node('p',a.summary),node('small',a.model_version+' · prompt '+a.prompt_version));const details=node('details');details.append(node('summary','Evidence references'),node('div',a.input_refs.join(' · ')),node('div',a.conflicting_evidence.join(' · ')));card.append(details);return card;});
    $('committee').replaceChildren(...(cards.length?cards:[node('div','Run a synthetic cycle to inspect the recorded committee.','empty')]));
    $('journal').replaceChildren(...[...snapshot.journal].reverse().map(e=>{const r=node('div',undefined,'journal-row');r.append(node('time',new Date(e.timestamp).toLocaleString('en-AU')));const detail=node('div',e.kind.replaceAll('_',' '));if(e.kind==='DECISION')detail.append(node('small',e.payload.outcome+' · '+e.payload.reasons.join(', ')));if(e.kind==='FILL')detail.append(node('small',e.payload.side+' '+e.payload.quantity+' '+e.payload.instrument+' at '+money(e.payload.price)+' · fee '+money(e.payload.fee)+' · SYNTHETIC'));if(e.kind==='HALT')detail.append(node('small',e.payload.reason));r.append(detail);return r;}));
    $('reconciliation').textContent=snapshot.reconciliation.ok?'PASS · Event replay matches cash, inventory, modelled fees and realised P&L.':'FAILED · Account reconciliation requires operator review.';
    $('next-title').textContent=a.halted?'Review the persistent HALT':snapshot.positions.length?'Inspect the simulated position':a.enabled?'Run a synthetic research cycle':'Enable a synthetic paper session';
    $('next-copy').textContent=a.halted?'Review account state and close remaining positions before clearing HALT.':'Use the control centre, then inspect the committee and event journal.';
  }
  async function refresh() { snapshot=await api('accounts/paper'); if(!catalog)catalog=await api('catalog');render(); }
  async function act(callback) {
    if(busy)return;busy=true;document.querySelectorAll('[data-control],[data-fixture]').forEach(el=>el.disabled=true);
    try{const result=await callback();await refresh();const outcome=result?.decision?.outcome;message(outcome?'Recorded decision: '+outcome+'.':'Account updated. All execution remains synthetic.');}catch(error){message(error.message,true);}finally{busy=false;document.querySelectorAll('[data-control],[data-fixture]').forEach(el=>el.disabled=false);}
  }
  $('login-form').addEventListener('submit',async event=>{event.preventDefault();token=$('token').value.trim();$('token').value='';catalog=null;await act(()=>api('health'));});
  $('signout').addEventListener('click',async()=>{try{await api('signout',{});}catch(error){message(error.message,true);return;}token='';snapshot=null;catalog=null;$('workspace').hidden=true;$('login').hidden=false;$('signout').hidden=true;message('Signed out. Your token is no longer held in this page.');});
  document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',()=>view(el.dataset.view)));
  document.querySelectorAll('[data-open]').forEach(el=>el.addEventListener('click',()=>view(el.dataset.open)));
  document.querySelectorAll('[data-control]').forEach(el=>el.addEventListener('click',()=>act(()=>api('accounts/paper/control',{action:el.dataset.control}))));
  document.querySelectorAll('[data-fixture]').forEach(el=>el.addEventListener('click',()=>act(()=>api('accounts/paper/fixture',{action:el.dataset.fixture,key:crypto.randomUUID()}))));
  $('halt').addEventListener('click',async()=>{try{await api('accounts/paper/control',{action:'halt'});await refresh();message('Persistent HALT recorded. New entries are blocked.');}catch(error){message(error.message,true);}});
  $('export').addEventListener('click',()=>{if(!snapshot)return;const url=URL.createObjectURL(new Blob([JSON.stringify(snapshot,null,2)],{type:'application/json'})),a=node('a');a.href=url;a.download='alpha-labs-my-simulated-records.json';a.click();URL.revokeObjectURL(url);message('Your simulated account records were exported.');});
})();
