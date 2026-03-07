import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('shows login page', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByText('SPT-CRM')).toBeVisible()
    await expect(page.getByPlaceholder('用户名')).toBeVisible()
    await expect(page.getByPlaceholder('密码')).toBeVisible()
  })

  test('login with valid credentials redirects to dashboard', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('用户名').fill('admin')
    await page.getByPlaceholder('密码').fill('admin123')
    await page.getByRole('button', { name: /登录/ }).click()
    await expect(page).toHaveURL('/', { timeout: 10_000 })
    // Dashboard should show content
    await expect(page.locator('body')).toContainText(/仪表盘|Dashboard|商机|客户/)
  })

  test('login with wrong password shows error', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('用户名').fill('admin')
    await page.getByPlaceholder('密码').fill('wrongpass')
    await page.getByRole('button', { name: /登录/ }).click()
    // Should stay on login page
    await page.waitForTimeout(2000)
    await expect(page).toHaveURL(/login/)
  })

  test('unauthenticated user is redirected to login', async ({ page }) => {
    await page.goto('/customers')
    await expect(page).toHaveURL(/login/, { timeout: 10_000 })
  })
})
