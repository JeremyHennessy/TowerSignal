import { mkdirSync, writeFileSync } from 'node:fs'
import { expect, test } from './fixtures'
import { installCandidateRoutes } from './candidate-routes'
import { devices } from '@playwright/test'

// Shared inventory is exercised against candidate bytes before release and actual hosted bytes afterward.
test('NYC application page and tab visual inventory', async ({ page, browser }, testInfo) => {
  test.setTimeout(900_000)
  const folder=testInfo.outputPath('page-inventory')
  mkdirSync(folder,{recursive:true})
  const states: Array<Record<string,unknown>>=[]
  const issues: Array<Record<string,unknown>>=[]
  const pending=new Set<string>()
  page.on('request',r=>{if(r.url().includes('/TowerSignal/data/'))pending.add(r.url())})
  page.on('requestfinished',r=>pending.delete(r.url()))
  page.on('requestfailed',r=>{pending.delete(r.url()); if(r.url().includes('/TowerSignal/'))issues.push({request:r.url(),error:r.failure()?.errorText})})
  page.on('pageerror',e=>issues.push({error:String(e)}))
  const prefix=process.env.CANDIDATE_ROOT?'CANDIDATE_NOT_HOSTED':'ACTUAL_HOSTED_NYC'
  async function ready() {
    await page.waitForTimeout(350)
    const limit=Date.now()+60_000
    while(pending.size && Date.now()<limit) await page.waitForTimeout(200)
    expect(pending.size,'Unsettled account/source requests').toBe(0)
    await expect(page.locator('body')).not.toContainText('Loading source-backed details')
    await expect(page.getByText('Intelligence workspace unavailable',{exact:true})).toHaveCount(0)
    await page.waitForTimeout(250)
  }
  async function capture(name:string) {
    await ready()
    await page.evaluate(()=>scrollTo(0,0))
    const data=await page.evaluate(()=>({hash:location.hash,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,
      headings:[...document.querySelectorAll('h1,h2,h3')].filter(e=>e.getClientRects().length).map(e=>e.textContent),text:document.body.innerText}))
    expect(data.text.length).toBeGreaterThan(200)
    expect(data.scrollWidth,`${name} viewport overflow`).toBeLessThanOrEqual(data.width+2)
    const stem=String(states.length+1).padStart(3,'0')+'-'+name.toLowerCase().replace(/[^a-z0-9]+/g,'-').slice(0,100)
    const images=[stem+'.png']
    await page.screenshot({path:`${folder}/${images[0]}`,scale:'css',animations:'disabled',timeout:60_000})
    if(data.height<24000) {
      images.push(stem+'-full.png')
      await page.screenshot({path:`${folder}/${images[1]}`,scale:'css',animations:'disabled',fullPage:true,timeout:60_000})
    } else {
      for(let y=page.viewportSize()!.height;y<data.height;y+=page.viewportSize()!.height) {
        await page.evaluate(top=>scrollTo(0,top),y)
        const file=`${stem}-y${y}.png`
        await page.screenshot({path:`${folder}/${file}`,scale:'css',animations:'disabled',timeout:60_000})
        images.push(file)
      }
    }
    writeFileSync(`${folder}/${stem}.json`,JSON.stringify(data,null,2))
    states.push({name,hash:data.hash,images,diagnostics:stem+'.json'})
    writeFileSync(`${folder}/manifest.json`,JSON.stringify({mode:prefix,project:testInfo.project.name,code_sha:process.env.GITHUB_SHA,states,issues},null,2))
  }
  async function tabs(name:string) {
    const seen=new Set<string>()
    for(let count=0;count<100;count++) {
      const inventory=await page.evaluate(()=>{
        const selector='[role="tablist"],[class*="tabs"],[class*="view-toggle"],[class*="timeline-filters"]'
        return [...document.querySelectorAll(selector)].filter(e=>e.getClientRects().length && !e.closest('.portal-navigation,.reference-top-nav')).reverse().flatMap(group=>
          [...group.querySelectorAll('button,[role="tab"]')].filter(e=>e.getClientRects().length && !(e as HTMLButtonElement).disabled && e.closest(selector)===group).map(e=>{
            const label=(e.getAttribute('aria-label')||e.textContent||'').trim()
            const key=(group.getAttribute('aria-label')||group.className)+'|'+label
            e.setAttribute('data-audit-tab',key)
            return {key,label}
          }))
      })
      const next=inventory.find(i=>!seen.has(i.key))
      if(!next) return
      seen.add(next.key)
      await page.locator(`[data-audit-tab=${JSON.stringify(next.key)}]`).click()
      await capture(name+' / '+next.label)
    }
    throw new Error('Tab inventory exceeded traversal guard')
  }
  const routes=['home','prospect','monitor','map','opportunities','companies','water-quality','portfolios','workflow','source-health','my-account','nys','nys-changes']
  for(const route of routes) {
    await page.evaluate(hash=>{location.hash=hash},'#/'+route)
    await capture(route)
    await tabs(route)
  }
  // Explicit NYC fixtures cover outbreak notices, history, institutions, and multi-system accounts.
  for(const id of ['2000003324','2000015925','2000000660','2000015564','2000012577','2000002409','2000000006']) {
    await page.evaluate(hash=>{location.hash=hash},'#/account/'+id)
    await capture('Account '+id)
    await tabs('Account '+id)
  }
  for(const id of ['known-firm-4abb52cdffb968606f23','observed-company-69f2a028243abcb16658']) {
    await page.evaluate(hash=>{location.hash=hash},'#/company/'+id)
    await capture('Firm '+id)
    await tabs('Firm '+id)
  }
  // Public marketing and auth form states use an empty context, never another user's session.
  const publicContext=await browser.newContext({...(testInfo.project.name==='iphone'?devices['iPhone 13']: {viewport:{width:1440,height:1000}}),baseURL:String(testInfo.project.use.baseURL)})
  const publicPage=await publicContext.newPage()
  await installCandidateRoutes(publicPage)
  await publicPage.goto('./',{waitUntil:'domcontentloaded'})
  await publicPage.screenshot({path:`${folder}/public-marketing.png`,scale:'css',fullPage:true})
  await publicPage.goto('./#/companies',{waitUntil:'domcontentloaded'})
  await expect(publicPage.getByRole('heading',{name:'Sign in to TowerSignal',exact:true})).toBeVisible()
  await publicPage.screenshot({path:`${folder}/public-login.png`,scale:'css',fullPage:true})
  await publicPage.getByRole('tab',{name:'Create account',exact:true}).click()
  await publicPage.screenshot({path:`${folder}/public-create-account.png`,scale:'css',fullPage:true})
  await publicContext.close()
  expect(issues).toEqual([])
  expect(states.some(s=>String(s.name).includes('Map + table'))).toBe(true)
  expect(states.some(s=>String(s.name).includes('Reference library'))).toBe(true)
  expect(states.some(s=>String(s.name).includes('History'))).toBe(true)
})
