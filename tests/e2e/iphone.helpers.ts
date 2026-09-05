import { expect, type Locator, type Page } from '@playwright/test'

type ProjectInfo = { project: { name: string } }

const HEADING_SELECTOR = 'h1,h2,h3,h4,h5,h6'
const HOSTED_IPHONE_DOM_TIMEOUT = process.env.CI ? 90_000 : 25_000

export function isIphoneProject(testInfo: ProjectInfo): boolean {
  return testInfo.project.name.includes('iphone')
}

export async function expectContained(page: Page): Promise<void> {
  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
}

export async function expectElementContained(page: Page, selector: string): Promise<void> {
  const viewportWidth = page.viewportSize()?.width ?? 0
  const width = await page.evaluate(selector => document.querySelector(selector)?.getBoundingClientRect().width ?? 0, selector)
  expect(width).toBeGreaterThan(0)
  expect(width).toBeLessThanOrEqual(viewportWidth + 0.5)
}

export async function expectDomText(page: Page, snippets: string[], selector = 'body'): Promise<void> {
  await expect.poll(async () => {
    return page.evaluate(({ selector, snippets }) => {
      const text = document.querySelector(selector)?.textContent ?? ''
      return snippets.every(snippet => text.includes(snippet))
    }, { selector, snippets })
  }, { timeout: HOSTED_IPHONE_DOM_TIMEOUT }).toBe(true)
}

export async function expectDomCount(page: Page, selector: string, count: number): Promise<void> {
  await expect.poll(async () => {
    return page.evaluate(selector => document.querySelectorAll(selector).length, selector)
  }, { timeout: HOSTED_IPHONE_DOM_TIMEOUT }).toBe(count)
}

export async function expectDomAttribute(page: Page, selector: string, name: string, value: RegExp | string): Promise<void> {
  await expect.poll(async () => {
    const attribute = await page.evaluate(({ selector, name }) => {
      return document.querySelector(selector)?.getAttribute(name) ?? ''
    }, { selector, name })
    return typeof value === 'string' ? attribute.includes(value) : value.test(attribute)
  }, { timeout: HOSTED_IPHONE_DOM_TIMEOUT }).toBe(true)
}

export async function expectHeading(page: Page, testInfo: ProjectInfo, name: string): Promise<Locator | null> {
  if (isIphoneProject(testInfo)) {
    await expect.poll(async () => {
      return page.evaluate(({ selector, name }) => {
        return [...document.querySelectorAll(selector)].some(element => element.textContent?.trim() === name)
      }, { selector: HEADING_SELECTOR, name })
    }, { timeout: HOSTED_IPHONE_DOM_TIMEOUT }).toBe(true)
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
    await expect.poll(async () => {
      return page.evaluate(({ selector, headingName, snippets }) => {
        const heading = [...document.querySelectorAll(selector)].find(element => element.textContent?.trim() === headingName)
        const sectionText = heading?.closest('section')?.textContent ?? ''
        return snippets.every(snippet => sectionText.includes(snippet))
      }, { selector: HEADING_SELECTOR, headingName, snippets })
    }, { timeout: HOSTED_IPHONE_DOM_TIMEOUT }).toBe(true)
    return null
  }

  const heading = await expectHeading(page, testInfo, headingName)
  const section = heading!.locator('xpath=ancestor::section[1]')
  for (const snippet of snippets) await expect(section).toContainText(snippet)
  return section
}

export async function expectAccountDetailHydrated(page: Page): Promise<void> {
  const detail = page.locator('.detail-panel')
  await expect(detail).toHaveCount(1, { timeout: HOSTED_IPHONE_DOM_TIMEOUT })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: HOSTED_IPHONE_DOM_TIMEOUT })
}

export async function setInputValue(page: Page, selector: string, value: string): Promise<void> {
  await page.evaluate(({ selector, value }) => {
    const element = document.querySelector(selector)
    if (!(element instanceof HTMLInputElement)) throw new Error(`Expected input element for ${selector}`)
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
    setter?.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
  }, { selector, value })
}

export async function setSelectValue(page: Page, selector: string, value: string): Promise<void> {
  await page.evaluate(({ selector, value }) => {
    const element = document.querySelector(selector)
    if (!(element instanceof HTMLSelectElement)) throw new Error(`Expected select element for ${selector}`)
    element.value = value
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
  }, { selector, value })
}

export async function setTextareaValue(page: Page, selector: string, value: string): Promise<void> {
  await page.evaluate(({ selector, value }) => {
    const element = document.querySelector(selector)
    if (!(element instanceof HTMLTextAreaElement)) throw new Error('Expected textarea element')
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set
    setter?.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
  }, { selector, value })
}

export async function setWorkflowAccountFields(page: Page, sectionSelector: string, status: string, nextActionDate: string, note: string): Promise<void> {
  await page.evaluate(({ sectionSelector, status, nextActionDate, note }) => {
    const root = document.querySelector(sectionSelector)
    if (!(root instanceof HTMLElement)) throw new Error(`Expected workflow account section for ${sectionSelector}`)
    const select = root.querySelector('select')
    const input = root.querySelector('input[type="date"]')
    const textarea = root.querySelector('textarea')
    if (!(select instanceof HTMLSelectElement)) throw new Error('Expected workflow status select')
    if (!(input instanceof HTMLInputElement)) throw new Error('Expected workflow next-action input')
    if (!(textarea instanceof HTMLTextAreaElement)) throw new Error('Expected workflow note textarea')

    select.value = status
    select.dispatchEvent(new Event('input', { bubbles: true }))
    select.dispatchEvent(new Event('change', { bubbles: true }))

    const inputSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
    inputSetter?.call(input, nextActionDate)
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))

    const textareaSetter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set
    textareaSetter?.call(textarea, note)
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    textarea.dispatchEvent(new Event('change', { bubbles: true }))
  }, { sectionSelector, status, nextActionDate, note })
}

export async function clickElement(page: Page, selector: string): Promise<void> {
  await page.evaluate(selector => {
    const element = document.querySelector(selector)
    if (!(element instanceof HTMLElement)) throw new Error('Expected clickable element')
    element.click()
  }, selector)
}
