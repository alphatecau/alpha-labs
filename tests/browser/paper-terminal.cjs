/* Real local API + browser checks. No external service or broker. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const modules=process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES;
const {chromium}=modules?require(path.join(modules,'playwright')):require('playwright');
const executable=process.env.ALPHA_BROWSER_EXECUTABLE;
const output=process.env.ALPHA_BROWSER_ARTIFACTS;

async function main(){
  const root=path.resolve(__dirname,'../..');
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'alpha-paper-browser-'));
  const results=[];
  const browser=await chromium.launch({headless:true,...(executable?{executablePath:executable}:{}),args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
  try{
    for(const width of [320,390,768,1440]){
      const state=path.join(tmp,String(width));
      const child=spawn(process.env.PYTHON || 'python',['-m','alpha_lab.paper.cli','serve','--state-dir',state,'--port','0'],{cwd:root,env:{...process.env,PYTHONPATH:path.join(root,'packages/alpha_lab/src')},stdio:['ignore','pipe','pipe']});
      let logs='';child.stderr.on('data',d=>logs+=String(d));
      const url=await new Promise((resolve,reject)=>{let stdout='';const timeout=setTimeout(()=>reject(new Error('local server startup timeout')),10000);child.stdout.on('data',data=>{stdout+=data;const match=stdout.match(/http:\/\/127.0.0.1:\d+\//);if(match){clearTimeout(timeout);resolve(match[0]);}});child.on('exit',code=>{clearTimeout(timeout);reject(new Error('server exited '+code));});});
      const tokens=JSON.parse(fs.readFileSync(path.join(state,'operator-tokens.json'),'utf8'));
      const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
      const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
      try{
        await page.goto(url);await page.waitForSelector('#login');
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
        await page.locator('#token').fill(tokens.alice);await page.locator('#login-form button').click();
        await page.waitForSelector('#workspace:visible');assert.match(await page.locator('#equity').innerText(),/10,000/);
        await page.locator('[data-view="controls"]').click();
        await page.locator('[data-control="enable"]').click();await page.waitForFunction(()=>document.querySelector('#account-status').textContent==='Paper session enabled');
        await page.locator('[data-fixture="cycle"]').click();await page.waitForFunction(()=>document.querySelector('#positions').textContent.includes('2 units'));
        await page.locator('[data-view="committee"]').click();assert.equal(await page.locator('.agent-card').count(),14);
        assert.match(await page.locator('#committee').innerText(),/UNVERIFIED/);
        await page.locator('[data-view="journal"]').click();assert.match(await page.locator('#reconciliation').innerText(),/^PASS/);
        assert.match(await page.locator('#journal').innerText(),/SYNTHETIC/);
        const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#export').click()]);
        assert.equal(download.suggestedFilename(),'alpha-labs-my-simulated-records.json');
        const bobContext=await browser.newContext({viewport:{width,height:900}});const bob=await bobContext.newPage();
        await bob.goto(url);await bob.locator('#token').fill(tokens.bob);await bob.locator('#login-form button').click();await bob.waitForSelector('#workspace:visible');
        assert.match(await bob.locator('#positions').innerText(),/No open/);assert.match(await bob.locator('#equity').innerText(),/10,000/);await bobContext.close();
        await page.locator('[data-view="controls"]').click();await page.locator('#halt').click();await page.waitForFunction(()=>document.querySelector('#account-status').textContent==='HALTED');
        await page.locator('[data-fixture="cycle"]').click();await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('HALT'));
        assert.equal(await page.getByRole('button',{name:'Live trading unavailable'}).isDisabled(),true);
        await page.locator('[data-fixture="close"]').click();await page.waitForFunction(()=>document.querySelector('#positions').textContent.includes('No open'));
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
        await page.locator('[data-view="overview"]').click();
        if(output){fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,`paper-${width}.png`),fullPage:true});}
        await page.locator('#signout').click();await page.waitForSelector('#login:visible');
        const status=await page.evaluate(async token=>(await fetch('/api/v1/accounts/paper',{headers:{Authorization:'Bearer '+token}})).status,tokens.alice);
        assert.equal(status,403);assert.equal(errors.length,0,errors.join('\n'));
        results.push({width,status:'PASS',checks:['login','autonomous-cycle','fourteen-roles','tenant-isolation','journal-export','HALT','reduce-only-close','disabled-live','signout-revocation','no-horizontal-overflow','no-page-errors']});
      }finally{await context.close();child.kill('SIGINT');await once(child,'exit');}
    }
    console.log(JSON.stringify({browser:await browser.version(),results},null,2));
  }finally{await browser.close();fs.rmSync(tmp,{recursive:true,force:true});}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
