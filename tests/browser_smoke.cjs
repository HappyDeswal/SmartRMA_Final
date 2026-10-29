const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const checks=[],errors=[],external=[];
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:8010')&&!r.url().startsWith('blob:')&&!r.url().startsWith('data:'))external.push(r.url());});
 const check=(name,ok)=>{if(!ok)throw Error(name);checks.push(name);};
 const entryResponse=page.waitForResponse(r=>r.url().endsWith('/api/auth/me'));
 await page.goto('http://127.0.0.1:8010');const entry=await entryResponse;
 if(entry.status()===401){const credentials=JSON.parse(fs.readFileSync(path.join(root,'var/first_login.json')));const signed=await page.request.post('http://127.0.0.1:8010/api/auth/login',{data:{username:'admin',password:credentials.password}});if(!signed.ok())throw Error('Test client authentication failed');await page.reload();}
 await page.locator('#workspace').waitFor({state:'visible'});check('workspace entry works in configured authentication mode',true);
 await page.locator('#order-id').fill('HAPPY-LIVE-T1');await page.locator('#product-name').fill('Gigabyte RTX 4070 · live smoke');await page.locator('#manufacturer').fill('GIGABYTE');await page.locator('#price').fill('250');await page.locator('#complaint').fill('Live software verification with licensed sample photo; synthetic test value.');
 await page.locator('#photo-0').setInputFiles(path.join(root,'sample_data/T1/01_graphics_card.jpg'));check('original photo preview',await page.locator('.photo-slot img').count()===1);
 const existing=await page.evaluate(async()=>{const r=await fetch('/api/cases?search=HAPPY-LIVE-T1');return r.json()});let submitted;
 if(existing.items.length){submitted={case_id:existing.items[0].id};await page.locator('[data-view=review]').click();check('earlier browser upload persisted',true);}else{
 const saved=page.waitForResponse(r=>r.url().endsWith('/api/cases')&&r.request().method()==='POST');await page.locator('#submit-case').click();const response=await saved;check('browser upload accepted as durable job',response.status()===202);submitted=await response.json();}
 await page.locator('#view-review').waitFor({state:'visible'});await page.locator(`[data-case="${submitted.case_id}"]`).click();await page.waitForFunction(id=>document.querySelector('#case-detail').textContent.includes(id),submitted.case_id);check('review displays submitted case',true);
 await page.reload();await page.locator('#workspace').waitFor({state:'visible'});check('session and queue survive reload',true);
 await page.locator('[data-view=policies]').click();await page.locator('#policy-documents a').first().waitFor();check('policy PDFs listed',await page.locator('#policy-documents a').count()>10);
 await page.locator('#policy-query').fill('warranty physical damage');await page.locator('#policy-brand').fill('NVIDIA');await page.locator('#policy-form button').click();await page.waitForTimeout(500);check('policy search renders sources',await page.locator('#policy-results').innerText().then(t=>t.length>20));
 await page.locator('[data-view=system]').click();await page.locator('#verify-audit').click();await page.waitForFunction(()=>/Verification (passed|failed)/.test(document.querySelector('#audit-result').textContent));check('integrity verification runs in browser',await page.locator('#audit-result').innerText().then(t=>!/failed/i.test(t)));
 await page.locator('[data-view=account]').click();await page.locator('#user-list').waitFor({state:'visible'});check('admin account controls available',await page.locator('#new-user').isVisible());
 await page.locator('[data-view=intake]').click();await page.locator('#theme-toggle').click();await page.screenshot({path:path.join(__dirname,'artifacts/desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});await page.waitForTimeout(500);await page.screenshot({path:path.join(__dirname,'artifacts/mobile.png'),fullPage:true});check('mobile layout fits viewport',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 check('no browser JavaScript errors',errors.length===0);check('no external browser requests',external.length===0);
 fs.writeFileSync(path.join(__dirname,'artifacts/browser.json'),JSON.stringify({checks,errors,external,case_id:submitted.case_id},null,2));
 console.log(JSON.stringify({passed:checks.length,case_id:submitted.case_id,errors,external}));await browser.close();
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exit(1)});
