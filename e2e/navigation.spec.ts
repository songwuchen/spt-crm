import { test, expect } from '@playwright/test'
import { loginViaApi } from './helpers'

test.describe('Page Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  const pages = [
    { path: '/', text: /仪表盘|Dashboard|商机|客户/ },
    { path: '/customers', text: /客户管理/ },
    { path: '/leads', text: /线索/ },
    { path: '/opportunities', text: /商机管理/ },
    { path: '/follow-ups', text: /跟进/ },
    { path: '/payments', text: /回款|付款/ },
    { path: '/products', text: /产品/ },
    { path: '/tasks', text: /任务/ },
    { path: '/service-tickets', text: /工单|服务/ },
    { path: '/approvals', text: /审批/ },
    { path: '/analytics', text: /分析|报表/ },
    { path: '/notifications', text: /通知/ },
    { path: '/profile', text: /个人|资料/ },
  ]

  for (const { path, text } of pages) {
    test(`${path} loads without error`, async ({ page }) => {
      await page.goto(path)
      await expect(page.locator('body')).toContainText(text, { timeout: 10_000 })
      // No crash - page rendered
    })
  }
})
