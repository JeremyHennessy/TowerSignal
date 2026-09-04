import { expect, test, type Locator, type Page } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { testCredentials } from './auth.helpers'

type Box = { x: number; y: number; width: number; height: number }

type HeaderSnapshot = {
  header: Box
  brand: Box
  logo: Box
  nav: Box
  buttons: Record<string, Box>
  css: Record<string, string>
}

const navLabels = [
  'Home',
  'Prospect',
  'Monitor',
  'Map',
  'NYS Market',
  'NYS Changes',
  'Opportunities',
  'Companies',
  'Portfolios',
  'Workflow',
]

async function box(locator: Locator): Promise<Box> {
  const value = await locator.boundingBox()
  expect(value).not.toBeNull()
  return value as Box
}

async function snapshotHeader(page: Page, name: 'home' | 'prospect'): Promise<HeaderSnapshot> {
  const header = page.locator('header.reference-top-nav').first()
  await expect(header).toBeVisible()
  const brand = header.locator('.reference-brand').first()
  const logo = brand.locator('img').first()
  const nav = header.locator('nav').first()

  const buttons: Record<string, Box> = {}
  for (const label of navLabels) {
    buttons[label] = await box(nav.getByRole('button', { name: label, exact: true }))
  }

  const css = await header.evaluate(element => {
    const style = getComputedStyle(element)
    const navElement = element.querySelector('nav')
    const navStyle = navElement ? getComputedStyle(navElement) : null
    return {
      display: style.display,
      height: style.height,
      minHeight: style.minHeight,
      paddingLeft: style.paddingLeft,
      paddingRight: style.paddingRight,
      gap: style.gap,
      alignItems: style.alignItems,
      navDisplay: navStyle?.display ?? '',
      navJustifyContent: navStyle?.justifyContent ?? '',
      navFlex: navStyle?.flex ?? '',
    }
  })

  mkdirSync('header-proof', { recursive: true })
  await header.screenshot({ path: `header-proof/${name}-header.png` })

  return {
    header: await box(header),
    brand: await box(brand),
    logo: await box(logo),
    nav: await box(nav),
    buttons,
    css,
  }
}

function assertBoxEqual(label: string, a: Box, b: Box, tolerance = 1) {
  for (const field of ['x', 'y', 'width', 'height'] as const) {
    const delta = Math.abs(a[field] - b[field])
    expect(delta, `${label}.${field} differs by ${delta}px`).toBeLessThanOrEqual(tolerance)
  }
}

test('LIVE Home and Prospect headers use identical geometry', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1920, height: 1080 })

  await page.goto('./#/companies', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()

  const credentials = testCredentials(testInfo.project.name)
  await page.getByRole('tab', { name: 'Create account', exact: true }).click()
  await page.getByLabel('Full name').fill(credentials.name)
  await page.getByLabel('Email').fill(credentials.email)
  await page.getByLabel('Password', { exact: true }).fill(credentials.password)
  await page.getByLabel('Confirm password').fill(credentials.password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Companies', exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Home', exact: true }).click()
  await expect(page).toHaveURL(/#\/home$/)
  await expect(page.getByRole('heading', { name: /Good morning, E2E/ })).toBeVisible()
  const home = await snapshotHeader(page, 'home')

  await page.getByRole('button', { name: 'Prospect', exact: true }).click()
  await expect(page).toHaveURL(/#\/prospect$/)
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()
  const prospect = await snapshotHeader(page, 'prospect')

  assertBoxEqual('header', home.header, prospect.header)
  assertBoxEqual('brand', home.brand, prospect.brand)
  assertBoxEqual('logo', home.logo, prospect.logo)

  // The workspace may reserve a different amount of right-side tool space, but
  // its navigation must start at the same x/y position and each shared nav item
  // must occupy the same rendered box so route changes cannot visually jump.
  expect(Math.abs(home.nav.x - prospect.nav.x)).toBeLessThanOrEqual(1)
  expect(Math.abs(home.nav.y - prospect.nav.y)).toBeLessThanOrEqual(1)
  for (const label of navLabels) assertBoxEqual(`nav.${label}`, home.buttons[label], prospect.buttons[label])

  expect(home.css).toEqual(prospect.css)

  const proof = {
    testedUrl: process.env.BASE_URL,
    viewport: { width: 1920, height: 1080 },
    home,
    prospect,
    deltas: {
      headerX: prospect.header.x - home.header.x,
      headerY: prospect.header.y - home.header.y,
      headerHeight: prospect.header.height - home.header.height,
      brandX: prospect.brand.x - home.brand.x,
      brandY: prospect.brand.y - home.brand.y,
      brandWidth: prospect.brand.width - home.brand.width,
      navX: prospect.nav.x - home.nav.x,
      navY: prospect.nav.y - home.nav.y,
    },
  }
  writeFileSync('header-proof/geometry.json', JSON.stringify(proof, null, 2))
  console.log(`HEADER_LIVE_PROOF ${JSON.stringify(proof)}`)
})
