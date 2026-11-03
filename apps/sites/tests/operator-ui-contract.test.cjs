'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const dir=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(dir,'index.html'),'utf8');
const css=fs.readFileSync(path.join(dir,'operator.css'),'utf8');
const js=fs.readFileSync(path.join(dir,'operator.js'),'utf8');
const fixture=fs.readFileSync(path.join(dir,'demo-fixture.js'),'utf8');
test('approved four-screen information architecture and separate settings are present',()=>{
 for(const name of ['home','markets','intelligence','activity','settings']){
  assert.match(html,new RegExp(`id="view-${name}"`));assert.match(html,new RegExp(`data-route="${name}"`));
 }
});
test('mobile-first dark design uses approved tokens and safe-area navigation',()=>{
 for(const c of ['#101419','#192028','#b7f486','#f5f7f6'])assert.ok(css.toLowerCase().includes(c));
 assert.match(css,/env\(safe-area-inset-bottom\)/);assert.match(css,/@media\(max-width:360px\)/);
});
test('all operator JavaScript assets exist with no external runtime dependency',()=>{
 for(const n of ['operator.css','operator.js','demo-fixture.js']){
  assert.ok(fs.statSync(path.join(dir,n)).size>100);assert.ok(html.includes('./'+n));
 }
 assert.doesNotMatch(html,/<script[^>]*https?:\/\//i);
});
test('research mode is explicit and trade routes are absent',()=>{
 assert.match(html,/RESEARCH/);assert.match(html,/DATA OFFLINE/);
 assert.match(html,/Trading permissions/);assert.match(html,/DISABLED/);
 for(const src of [js,fixture]){
  assert.doesNotMatch(src,/\bfetch\s*\(/);assert.doesNotMatch(src,/\bXMLHttpRequest\s*\(/);
  assert.doesNotMatch(src,/\bsendTransaction\s*\(/);assert.doesNotMatch(src,/\bsignTransaction\s*\(/);
 }
});
test('initial financial values are unavailable rather than fictional returns',()=>{
 assert.match(html,/id="equity-value">Unavailable/);
 assert.match(html,/No broker or paper ledger connected/);
 assert.match(js,/setDemo\(false\);showRoute/);
});
test('synthetic preview uses unequivocal provenance, never becomes live',()=>{
 assert.match(html,/SYNTHETIC DEMO/);assert.match(fixture,/SYNTHETIC DEMO/);
 assert.match(html,/No actual market data or transactions/);
 assert.match(js,/state\.demo/);assert.match(js,/RESEARCH ONLY/);
});
test('markets, activity, forecast and rejection states are coded',()=>{
 for(const name of ['renderMarkets','renderActivity','renderIntelligence','veto-summary','activity-export','market-filter']){
  assert.ok(js.includes(name)||html.includes(name),name);
 }
 assert.match(js,/replaceChildren\(/);
});
test('Advanced links preserve all six specialist research sections',()=>{
 for(const name of ['research','backtest','evidence','risk','roadmap','architecture']){
  assert.match(html,new RegExp(`advanced/index.html#${name}`));
 }
 const original=fs.readFileSync(path.join(dir,'advanced','index.html'),'utf8');
 for(const name of ['overview','research','backtest','evidence','risk','roadmap','architecture'])assert.ok(original.includes(`id="page-${name}"`));
 assert.match(original,/\.\.\/style.css/);assert.match(original,/\.\.\/app.js/);
 assert.match(original,/Return to Alpha Labs/);
});
test('UI never conflates synthetic data with paper or real profitability',()=>{
 assert.match(html,/No live trading, funded account, verified market signals/);
 assert.match(html,/The research tools are exploratory, offline and long\/flat only/);
 assert.match(js,/No broker account exists/);
});
