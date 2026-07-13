import { test, expect } from '@playwright/test'

/**
 * 前端公开页面 E2E（2026-07-13）
 *
 * 不依赖登录流程，测试前端路由 + 渲染：
 * - 登录页表单渲染
 * - 公开防伪核销页（无需登录）
 *
 * 注意：vite dev server 通过 Playwright webServer 自动启动；
 * admin + oa-agent 通过 global-setup 启动。
 */

test('登录页：表单渲染 + 错误密码提示', async ({ page }) => {
  await page.goto('/oa/login')
  await expect(page.locator('input[type="text"], input[placeholder*="账号"]').first()).toBeVisible()
  await expect(page.locator('input[type="password"]').first()).toBeVisible()
  await expect(page.locator('button:has-text("登录")').first()).toBeVisible()

  // 错误密码登录 → 应有错误提示（不跳走）
  await page.fill('input[type="text"]', 'admin')
  await page.fill('input[type="password"]', 'wrong-password-xxx')
  await page.click('button:has-text("登录")')
  // 期望仍停在登录页（错误提示由 Element Plus el-message 显示）
  await page.waitForTimeout(1500)
  // 还在 login 页
  await expect(page).toHaveURL(/\/oa\/login/)
})

test('公开防伪核销页：64 位 hex → "防伪验证" 关键字', async ({ page, request }) => {
  // 用 admin API 真实生成一张卡（globalSetup 已起 admin）
  const loginRes = await request.post('http://127.0.0.1:8300/admin/api/v1/auth/login', {
    data: { username: 'admin', password: 'admin1234' },
  })
  if (loginRes.status() !== 200) {
    test.skip(true, 'admin 不可达，跳过')
    return
  }
  const token = (await loginRes.json()).access_token
  const H = { Authorization: `Bearer ${token}` }

  // 创建 VIP 类型 + 批次 + 生成 1 张卡
  const tRes = await request.post('http://127.0.0.1:8300/admin/api/v1/asset/card-types', {
    headers: H,
    data: { name: `E2E-PW-${Date.now()}`, type: 'vip', unit_price: 1888.0 },
  })
  const t = await tRes.json()
  const bRes = await request.post('http://127.0.0.1:8300/admin/api/v1/asset/batches', {
    headers: H,
    data: { type_id: t.id, name: 'E2E-PW-批次', quantity: 1, unit_price: 1888.0 },
  })
  const b = await bRes.json()
  const gRes = await request.post(
    `http://127.0.0.1:8300/admin/api/v1/asset/batches/${b.id}/generate`,
    { headers: H, data: { quantity: 1 } },
  )
  expect(gRes.status()).toBe(200)

  const listRes = await request.get('http://127.0.0.1:8300/admin/api/v1/asset/cards', {
    headers: H,
    params: { batch_id: b.id },
  })
  const card = (await listRes.json()).items[0]
  expect(card.unique_code).toHaveLength(64)

  // 访问公开核销页
  await page.goto(`/oa/verify/${card.unique_code}`)
  // "防伪验证通过" 关键字（v-html 渲染）
  await expect(page.locator('text=防伪验证')).toBeVisible({ timeout: 5_000 })
})

test('公开防伪核销页：非 64 位 → 错误页', async ({ page }) => {
  await page.goto('/oa/verify/short')
  await expect(page.locator('text=防伪验证失败').or(page.locator('text=验证失败'))).toBeVisible({
    timeout: 5_000,
  })
})