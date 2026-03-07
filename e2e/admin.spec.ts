import { test, expect } from '@playwright/test'
import { loginViaApi } from './helpers'

test.describe('Admin Pages', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  test('user list page loads', async ({ page }) => {
    await page.goto('/admin/users')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10_000 })
  })

  test('role list page loads', async ({ page }) => {
    await page.goto('/admin/roles')
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10_000 })
  })

  test('department page loads', async ({ page }) => {
    await page.goto('/admin/departments')
    await expect(page.locator('body')).toContainText(/部门/, { timeout: 10_000 })
  })

  test('settings page loads with tabs', async ({ page }) => {
    await page.goto('/admin/settings')
    await expect(page.locator('body')).toContainText(/系统设置|设置/, { timeout: 10_000 })
  })

  test('audit log page loads', async ({ page }) => {
    await page.goto('/admin/audit')
    await expect(page.locator('body')).toContainText(/审计|操作日志/, { timeout: 10_000 })
  })
})
