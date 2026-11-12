const {test} = require('node:test');
const assert = require('node:assert/strict');
const {healthySnapshot, createIntentStore, validIntent, installPaperConsole} = require('../owner-paper/paper.js');
const terms = {symbol:'SOL-USD', side:'BUY', quantity:'1', stop_price:'90'};
function memory() { const values = new Map(); return {getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}; }
function snapshot() { return {mode:'SIMULATION_ONLY',currency:'USD',risk:{data_healthy:true},portfolio:{reconciled:true},market:Object.fromEntries(['BTC-USD','ETH-USD','SOL-USD'].map(s=>[s,{healthy:true,age_seconds:1,bid:'100',ask:'100.02'}]))}; }
test('browser freshness locks controls when polling stalls or any book is unavailable',()=>{
  const s=snapshot(); assert.equal(healthySnapshot(s,1000,1000),true);
  assert.equal(healthySnapshot(s,1000,12000),false);
  delete s.market['ETH-USD']; assert.equal(healthySnapshot(s,1000,1000),false);
});
test('malformed currency, mode, reconciliation and quote evidence cannot enable controls',()=>{
  for(const change of [s=>s.currency='USDT',s=>s.mode='LIVE',s=>s.portfolio.reconciled=false,s=>s.market['BTC-USD'].bid='Infinity',s=>s.market['BTC-USD'].age_seconds=-1]){
    const s=snapshot(); change(s); assert.equal(healthySnapshot(s,1000,1000),false);
  }
});
test('uncertain order retries and page restart reuse a single durable intent ID',()=>{
  const storage=memory();let count=0;
  const first=createIntentStore(storage,()=>`synthetic_order_${++count}`);
  const order=first.prepare(terms);
  assert.deepEqual(first.prepare(terms),order);
  const restarted=createIntentStore(storage,()=>{throw Error('must not allocate another ID')});
  assert.deepEqual(restarted.prepare(terms),order); assert.equal(count,1);
  assert.throws(()=>restarted.prepare({...terms,quantity:'2'}),/pending order/);
  restarted.resolve(); assert.equal(restarted.current(),null);
});
test('browser rejects malformed order terms and never treats cache data as a fill',()=>{
  for(const quantity of ['', '-1', 'NaN', '1e9', 1]) assert.equal(validIntent({...terms,quantity}),false);
  const storage=memory(); storage.setItem('alpha.paper.pending.v1','{"side":"BUY"}');
  assert.equal(createIntentStore(storage,()=> 'synthetic_order_0001').current(),null);
});

function harness(fetcher, confirmation=true) {
  const nodes=new Map(), calls=[];
  const element=()=>({textContent:'',value:'',disabled:false,hidden:false,listeners:{},
    addEventListener(name,fn){this.listeners[name]=fn},replaceChildren(){},append(){}});
  const doc={getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)},
    querySelector(){return {content:'a'.repeat(64)}},createElement:element};
  let ids=0;
  const win={document:doc,sessionStorage:memory(),crypto:{randomUUID:()=>`synthetic_order_${++ids}`},
    confirm:()=>confirmation,setInterval(){},AbortSignal:{timeout:()=>undefined},
    fetch:async(url,opts)=>{calls.push({url,opts});return fetcher(url,opts)}};
  doc.getElementById('symbol').value='SOL-USD';doc.getElementById('side').value='BUY';
  doc.getElementById('quantity').value='1';doc.getElementById('stop-price').value='90';
  return {win,doc,nodes,calls,ids:()=>ids};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
test('offline API locks controls while emergency HALT still uses the authenticated CSRF boundary',async()=>{
  const h=harness(async()=>{throw Error('network unavailable')});
  Object.defineProperty(h.win,'sessionStorage',{get(){throw Error('storage denied')}});
  installPaperConsole(h.win);await flush();
  assert.equal(h.nodes.get('submit-order').disabled,true);
  await h.nodes.get('halt').listeners.click();
  const req=h.calls.at(-1);assert.equal(req.url,'/api/v1/paper/control');
  assert.equal(req.opts.credentials,'same-origin');assert.equal(req.opts.headers['X-Alpha-CSRF'],'a'.repeat(64));
  assert.deepEqual(JSON.parse(req.opts.body),{action:'halt'});
  assert.match(h.nodes.get('message').textContent,/unknown/);
});
test('confirmation and transport failure preserve a single order ID through the real controller retry',async()=>{
  let fail=true;const s=snapshot();s.risk.armed=true;s.risk.can_arm=true;s.risk.revision=1;s.server_time='synthetic UTC';s.fills=[];
  const h=harness(async(url)=>{
    if(url.endsWith('/orders')){if(fail)throw Error('timeout');return {ok:true,json:async()=>({mode:'SIMULATION_ONLY',status:'ALREADY_COMMITTED'})}}
    return {ok:true,json:async()=>s};
  });
  installPaperConsole(h.win);await flush();
  const submit=h.nodes.get('order-form').listeners.submit;
  await submit({preventDefault(){}});
  assert.equal(h.ids(),1);assert.equal(h.nodes.get('retry-pending').hidden,false);
  const original=JSON.parse(h.calls.find(c=>c.url.endsWith('/orders')).opts.body);
  fail=false;await h.nodes.get('retry-pending').listeners.click();await flush();
  const last=JSON.parse(h.calls.filter(c=>c.url.endsWith('/orders')).at(-1).opts.body);
  assert.deepEqual(last,original);assert.equal(h.ids(),1);
  assert.equal(h.nodes.get('retry-pending').hidden,true);
  h.win.confirm=()=>false;await submit({preventDefault(){}});
  assert.equal(h.calls.filter(c=>c.url.endsWith('/orders')).length,2);
});
