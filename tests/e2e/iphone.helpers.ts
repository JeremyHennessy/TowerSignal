import { expect, type Locator, type Page } from '@playwright/test'

type ProjectInfo = { project: { name: string } }

const HEADING_SELECTOR = 'h1,h2,h3,h4,h5,h6'

export function isIphoneProject(testInfo: ProjectInfo): boolean {
  return testInfo.project.name.includes('iphone')
}

export async function expectContained(page: Page): Promise<void> {
  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
}

export async function expectHeading(page: Page, testInfo: ProjectInfo, name: string): Promise<Locator | null> {
  if (isIphoneProject(testInfo)) {
    await page.waitForFunction(({ selector, name }) => {
      return [...document.querySelectorAll(selector)].some(element => element.textContent?.trim() === name)
    }, { selector: HEADING_SELECTOR, name }, { timeout: 15_000 })
    return null
  }

  const heading = page.locator(HEADING_SELECTOR).filter({ hasText: name }).first()
  await expect(heading).toHaveText(name)
  await heading.scrollIntoViewIfNeeded()
  await expect(heading).toBeVisible()
  return heading
}

export async function expectSectionText(page: Page, testInfo: ProjectInfo, headingName: string, snippets: string[]): Promise<Locator | null> {
  if (isIphoneProject(testInfo)) {
    await page.waitForFunction(({ selector, headingName, snippets }) => {
      const heading = [...document.querySelectorAll(selector)].find(element => element.textContent?.trim() === headingName)
      const sectionText = heading?.closest('section')?.textContent ?? ''
      return snippets.every(snippet => sectionText.includes(snippet))
    }, { selector: HEADING_SELECTOR, headingName, snippets }, { timeout: 15_000 })
    return null
  }

  const heading = await expectHeading(page, testInfo, headingName)
  const section = heading!.locator('xpath=ancestor::section[1]')
  for (const snippet of snippets) await expect(section).toContainText(snippet)
  return section
}

export async function setTextareaValue(page: Page, selector: string, value: string): Promise<void> {
  await page.locator(selector).evaluate((element, value) => {
    if (!(element instanceof HTMLTextAreaElement)) throw new Error('Expected textarea element')
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set
    setter?.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
  }, value)
}

export async function clickElement(page: Page, selector: string): Promise<void> {
  await page.locator(selector).evaluate(element => {
    if (!(element instanceof HTMLElement)) throw new Error('Expected clickable element')
    element.click()
  })
}
