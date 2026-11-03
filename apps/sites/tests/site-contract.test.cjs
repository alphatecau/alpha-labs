'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(base,'advanced','index.html'),'utf8');
const app=fs.readFileSync(path.join(base,'app.js'),'utf8');
test('all navigation pages have section destinations',()=>{
  for(const name of ['overview','research','backtest','evidence','risk','roadmap','architecture']){
    assert.match(html,new RegExp(`id="page-${name}"`));
    assert.match(html,new RegExp(`data-page="${name}"`));
    assert.match(app,new RegExp(`${name}:'`));
  }
});
test('all locally referenced script/stylesheets are supplied',()=>{
  for(const name of ['style.css','app.js','research-engine.js','evidence-engine.js']){
    assert.match(html,new RegExp(`\\../${name.replace('.','\\.')}`));
    assert.ok(fs.statSync(path.join(base,name)).size>100);
  }
});
test('no fetch, signing or exchange execution in frontend research scripts',()=>{
  const js=app+'\n'+fs.readFileSync(path.join(base,'research-engine.js'),'utf8')+'\n'+fs.readFileSync(path.join(base,'evidence-engine.js'),'utf8');
  assert.doesNotMatch(js,/\bfetch\s*\(/);
  assert.doesNotMatch(js,/\bXMLHttpRequest\s*\(/);
  assert.doesNotMatch(js,/\bsendTransaction\s*\(/);
  assert.doesNotMatch(js,/\bsignTransaction\s*\(/);
});
test('site warns about synthetic data and no actual trading',()=>{
  assert.match(html,/SYNTHETIC DEMO/);
  assert.match(html,/No financial performance is verified/);
  assert.match(html,/No orders can be placed/);
});
test('research page includes full hypothesis falsification input',()=>{
  assert.match(html,/name="falsifier"/);
  assert.match(app,/Falsification criterion/);
});

test('evidence page keeps real trading prohibited and AI prices editable',()=>{
  assert.match(html,/id="ev-run"/);assert.match(html,/id="ev-input-price"/);
  assert.match(html,/Real-money deployment remains blocked/);
});
test('bootstraps after state declarations, avoiding temporal-dead-zone runtime failure',()=>{
  assert.ok(app.lastIndexOf('initBacktestStudio();showPage(')>app.indexOf('const bt ='));
});
