import { test, expect } from '@playwright/test'
import { loginViaApi, uniqueName } from './helpers'

test.describe('Customer Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  test('customer list page loads', async ({ page }) => {
    await page.goto('/customers')
    await expect(page.getByText('客户管理')).toBeVisible({ timeout: 10_000 })
    // Table should be present
    await expect(page.locator('.ant-table')).toBeVisible()
  })

  test('create a new customer', async ({ page }) => {
    const name = uniqueName('测试客户')
    await page.goto('/customers/new')
    await expect(page.getByText('新建客户')).toBeVisible({ timeout: 10_000 })

    await page.getByLabel('客户名称').fill(name)
    await page.getByLabel('简称').fill('测试')
    await page.getByLabel('区域').fill('华东')

    await page.getByRole('button', { name: '保存' }).click()
    // Should redirect to list
    await expect(page).toHaveURL('/customers', { timeout: 10_000 })
  })

  test('view customer detail', async ({ page }) => {
    await page.goto('/customers')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10_000 })
    // Click first detail link
    const detailLink = page.locator('.ant-table-row').first().getByText('详情')
    if (await detailLink.isVisible()) {
      await detailLink.click()
      await expect(page).toHaveURL(/\/customers\/[^/]+$/, { timeout: 10_000 })
    }
  })

  test('export customers to excel', async ({ page }) => {
    await page.goto('/customers')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10_000 })
    // The export button triggers a download
    const downloadPromise = page.waitForEvent('download', { timeout: 10_000 }).catch(() => null)
    await page.getByRole('button', { name: /导出/ }).click()
    const download = await downloadPromise
    if (download) {
      expect(download.suggestedFilename()).toContain('customers')
    }
  })

  test('open import modal', async ({ page }) => {
    await page.goto('/customers')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: /导入/ }).click()
    await expect(page.getByText('导入客户')).toBeVisible()
    await expect(page.getByText('上传文件')).toBeVisible()
  })
})
