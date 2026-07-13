import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

/**
 * Playwright E2E 配置（VIP 卡代理销售模式重构，2026-07-13）
 *
 * 启动要求：
 * 1. globalSetup 启动 admin :8300 + oa-agent :9001
 * 2. webServer 启动 vite dev server :5173
 * 3. spec 假设上述服务都在跑
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'pnpm dev',
    port: 5173,
    timeout: 60_000,
    reuseExistingServer: true,
  },
  globalSetup: resolve(__dirname, 'tests/e2e/global-setup.ts'),
})
