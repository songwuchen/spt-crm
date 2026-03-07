import { Page, expect } from '@playwright/test'

/** Login as admin and store token in localStorage */
export async function login(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill('admin')
  await page.getByPlaceholder('密码').fill('admin123')
  await page.getByRole('button', { name: /登录/ }).click()
  // Wait for redirect to dashboard
  await expect(page).toHaveURL('/', { timeout: 10_000 })
}

/** Login via API and inject token into localStorage (faster) */
export async function loginViaApi(page: Page) {
  const res = await page.request.post('/api/v1/auth/login', {
    data: { username: 'admin', password: 'admin123' },
  })
  const json = await res.json()
  const token = json.data?.access_token
  if (!token) throw new Error('Login failed: no token')
  await page.goto('/')
  await page.evaluate((t) => localStorage.setItem('access_token', t), token)
  await page.goto('/')
  await expect(page).toHaveURL('/', { timeout: 10_000 })
}

/** Generate a unique name for test data */
export function uniqueName(prefix: string) {
  return `${prefix}_E2E_${Date.now()}`
}
