import { mkdirSync, writeFileSync } from 'node:fs'
import { devices } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expect, test } from './fixtures'
import { expectContained } from './iphone.helpers'

const categories = ['All changes', 'High priority', 'Violations', 'OATH activity', 'DOB / permits', 'Sampling', 'Property / contact']

test('every Monitor tab has readable source values, responsive tables and usable controls', async ({ page: initialPage, browser }, testInfo) => {
  let page = initialPage
  test.setTimeout(300_000)
  const folder=testInfo.outputPath('monitor-format');mkdirSync(folder,{recursive:true})
  const states: Record<string,unknown>[]=[]
  await page.evaluate(()=>{location.hash='#/monitor'})
  let monitor=page.getByRole('region',{name:'TowerSignal changes'})
  await expect(monitor.locator('.change-reference-row').first()).toBeVisible()
  const original=page.viewportSize()!
  const widths=testInfo.project.name==='iphone'?[390,320]:[1280,1024,768,1440]
  async function capture(name:string){
    await expectContained(page)
    const metrics=await monitor.evaluate(root=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
      clipped:[...root.querySelectorAll('.monitor-open-link,.change-kind,.badge,.monitor-field-list dd')].filter(e=>e.getClientRects().length && e.scrollWidth>e.clientWidth+2).map(e=>e.textContent)}))
    expect(metrics.width, `Actual layout viewport for ${name}`).toBe(page.viewportSize()!.width)
    expect(metrics.scrollWidth, `Document viewport containment for ${name}`).toBeLessThanOrEqual(page.viewportSize()!.width + 2)
    expect(metrics.clipped,`Clipped Monitor content: ${name}`).toEqual([])
    const stem=name.replace(/[^a-zA-Z0-9]+/g,'-')
    await page.screenshot({path:`${folder}/${stem}.png`,scale:'css',animations:'disabled'})
    states.push({name,...metrics})
    writeFileSync(`${folder}/manifest.json`,JSON.stringify({mode:process.env.CANDIDATE_ROOT?'CANDIDATE_NOT_HOSTED':'ACTUAL_HOSTED_NYC',code_sha:process.env.GITHUB_SHA,project:testInfo.project.name,states},null,2))
  }
  for(const width of widths){
    // WebKit can authenticate this GitHub Pages tab in memory even when its
    // cross-site session cookie is blocked. A new context therefore cannot
    // inherit the authenticated user from storageState alone. For the 320px
    // proof, establish the same existing E2E account in that fresh context.
    const narrowContext = testInfo.project.name === 'iphone' && width !== original.width
      ? await browser.newContext({ ...devices['iPhone 13'], baseURL: String(testInfo.project.use.baseURL),
          viewport: { width, height: original.height }, screen: { width, height: original.height } }) : null
    if (narrowContext) {
      page = await narrowContext.newPage()
      await signInForProject(page, testInfo.project.name, '#/monitor')
      monitor = page.getByRole('region', { name: 'TowerSignal changes' })
      await expect(monitor.locator('.change-reference-row').first()).toBeVisible()
    } else if (testInfo.project.name !== 'iphone') {
      await page.setViewportSize({width,height:original.height})
    }
    for(const category of categories){
      const tab=monitor.getByRole('tab',{name:new RegExp('^'+category.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\s*\\d')})
      await tab.click();await expect(tab).toHaveAttribute('aria-selected','true')
      const table=monitor.getByRole('table',{name:`${category} events`,exact:true})
      await expect(table.locator('th')).toHaveCount(5)
      const row=table.locator('tbody tr').first();await expect(row).toBeVisible()
      await expect(row).not.toContainText('{"')
      await expect(row.locator('.monitor-account-cell').getByRole('link',{name:'Open account',exact:true})).toBeVisible()
      await monitor.locator('.change-tabs').scrollIntoViewIfNeeded();await capture(`${width}-${category}-tabs`)
      await row.scrollIntoViewIfNeeded();await capture(`${width}-${category}-row`)
    }
    if (narrowContext) {
      await narrowContext.close()
      page = initialPage
      monitor = page.getByRole('region', { name: 'TowerSignal changes' })
    }
  }
  if (testInfo.project.name !== 'iphone') await page.setViewportSize(original)
  for(const [type,required] of [['OATH_PENALTY_CHANGED','$'],['OATH_BALANCE_CHANGED','$'],['DOB_JOB_FILED','Job'],['LATEST_SAMPLE_CHANGED','Public sample date'],['HPD_CONTACT_ADDED','Business address']]){
    await monitor.getByLabel(/^Change type/).selectOption(type)
    const row=monitor.locator('.change-reference-row').first();await expect(row).toContainText(required)
    await row.scrollIntoViewIfNeeded();await capture(`detail-${type}`)
  }
  await monitor.getByLabel(/^Change type/).selectOption('OATH_BALANCE_CHANGED')
  await expect(monitor.locator('.monitor-source-date time').first()).not.toHaveAttribute('datetime',/\d/)
  await monitor.getByLabel('Sort events').selectOption('priority_score:desc')
  const scores=await monitor.locator('.monitor-priority-cell').allTextContents()
  expect(scores.map(Number)).toEqual(scores.map(Number).sort((a,b)=>b-a))
  const top=monitor.getByRole('navigation',{name:'Monitor pagination top'})
  await top.getByRole('button',{name:'Next',exact:true}).click();await expect(top).toContainText('Page 2')
  const bottom=monitor.getByRole('navigation',{name:'Monitor pagination bottom'});await expect(bottom).toContainText('Page 2')
  await bottom.scrollIntoViewIfNeeded();await capture('bottom-pagination')
  await bottom.getByRole('button',{name:'Previous',exact:true}).click();await expect(top).toContainText('Page 1')
  const first=monitor.locator('.change-reference-row').first()
  await first.locator('.monitor-row-provenance summary').click()
  await expect(first.getByText(/^First seen by TowerSignal/)).toBeVisible();await expect(page).toHaveURL(/#\/monitor$/)
  await first.scrollIntoViewIfNeeded();await capture('expanded-provenance')
  await first.locator('.monitor-row-provenance summary').click()
  await expect(first.getByText(/^First seen by TowerSignal/)).toBeHidden()
  await monitor.getByLabel('Event date range').selectOption('custom')
  await monitor.getByLabel('From',{exact:true}).fill('1900-01-01');await monitor.getByLabel('To',{exact:true}).fill('1900-01-02')
  await expect(monitor.getByText('No recorded events match these filters.',{exact:true})).toBeVisible()
  await monitor.locator('.reference-empty-state').scrollIntoViewIfNeeded();await capture('empty-filter-state')
})
