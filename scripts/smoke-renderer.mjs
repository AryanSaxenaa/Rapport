import { chromium } from 'playwright'
import fs from 'node:fs/promises'

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 460, height: 720 } })
const errors = []

page.on('console', (message) => {
  if (message.type() === 'error') errors.push(message.text())
})
page.on('pageerror', (error) => errors.push(error.message))

await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle' })

const result = {
  title: await page.locator('h1').first().textContent(),
  orbVisible: await page.locator('.ambient-orb').isVisible(),
  graphVisible: await page.locator('.graph-panel svg').isVisible(),
  commandButtonCount: await page.locator('button').count(),
  errors,
}

await page.screenshot({ path: 'renderer-smoke.png', fullPage: true })
await browser.close()

await fs.writeFile('renderer-smoke.json', JSON.stringify(result, null, 2))
console.log(JSON.stringify(result, null, 2))
