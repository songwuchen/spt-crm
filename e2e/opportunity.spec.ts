import { test, expect } from '@playwright/test'
import { loginViaApi, uniqueName } from './helpers'

test.describe('Opportunity Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  test('opportunity list page loads', async ({ page }) => {
    await page.goto('/opportunities')
    await expect(page.getByText('商机管理')).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('.ant-table')).toBeVisible()
  })

  test('create a new opportunity', async ({ page }) => {
    const name = uniqueName('测试商机')
    await page.goto('/opportunities/new')
    await expect(page.getByText('新建商机')).toBeVisible({ timeout: 10_000 })

    await page.getByLabel('项目名称').fill(name)
    await page.getByLabel('预计金额').fill('100000')
    await page.getByLabel('赢单概率').fill('60')

    await page.getByRole('button', { name: '保存' }).click()
    await expect(page).toHaveURL('/opportunities', { timeout: 10_000 })
  })

  test('kanban view loads', async ({ page }) => {
    await page.goto('/opportunities/kanban')
    // Should see stage columns
    await expect(page.locator('body')).toContainText(/S1|需求|线索/, { timeout: 10_000 })
  })

  test('view opportunity detail and stage history', async ({ page }) => {
    await page.goto('/opportunities')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10_000 })
    const detailLink = page.locator('.ant-table-row').first().getByText('详情')
    if (await detailLink.isVisible()) {
      await detailLink.click()
      await expect(page).toHaveURL(/\/opportunities\/[^/]+$/, { timeout: 10_000 })
      // Detail page should have tabs
      await expect(page.locator('body')).toContainText(/报价|合同|阶段|互动/)
    }
  })

  test('open import modal', async ({ page }) => {
    await page.goto('/opportunities')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: /导入/ }).click()
    await expect(page.getByText('导入商机')).toBeVisible()
  })
})
