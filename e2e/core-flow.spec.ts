import { test, expect } from '@playwright/test'
import { loginViaApi, uniqueName } from './helpers'

/**
 * End-to-end business flow:
 * Login → Create Customer → Create Opportunity → View Dashboard
 */
test.describe('Core Business Flow', () => {
  test('full cycle: customer → opportunity → dashboard', async ({ page }) => {
    await loginViaApi(page)

    // 1. Create Customer
    const customerName = uniqueName('流程客户')
    await page.goto('/customers/new')
    await expect(page.getByLabel('客户名称')).toBeVisible({ timeout: 10_000 })
    await page.getByLabel('客户名称').fill(customerName)
    await page.getByLabel('区域').fill('华北')
    await page.getByRole('button', { name: '保存' }).click()
    await expect(page).toHaveURL('/customers', { timeout: 10_000 })
    // Verify customer appears in list
    await expect(page.locator('body')).toContainText(customerName, { timeout: 5_000 })

    // 2. Create Opportunity
    const oppName = uniqueName('流程商机')
    await page.goto('/opportunities/new')
    await expect(page.getByLabel('项目名称')).toBeVisible({ timeout: 10_000 })
    await page.getByLabel('项目名称').fill(oppName)
    await page.getByLabel('预计金额').fill('500000')
    await page.getByLabel('赢单概率').fill('70')
    await page.getByRole('button', { name: '保存' }).click()
    await expect(page).toHaveURL('/opportunities', { timeout: 10_000 })
    await expect(page.locator('body')).toContainText(oppName, { timeout: 5_000 })

    // 3. Dashboard loads with data
    await page.goto('/')
    await expect(page.locator('body')).toContainText(/仪表盘|商机|客户/, { timeout: 10_000 })
  })
})
