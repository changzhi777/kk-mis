/**
 * Playwright E2E global setup（2026-07-13）
 *
 * 单 export 函数：启动 admin + oa-agent 子进程；
 * 返回 teardown 函数（Playwright 1.50+ 支持）。
 */
import { spawn, type ChildProcess, type SpawnOptions } from 'node:child_process'
import { existsSync, promises as fs } from 'node:fs'
import path from 'node:path'
import http from 'node:http'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const ADMIN_PORT = 8300
const OA_AGENT_PORT = 9001

let adminProc: ChildProcess | null = null
let oaAgentProc: ChildProcess | null = null

function waitPort(port: number, timeoutMs = 30000): Promise<void> {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get({ host: '127.0.0.1', port, path: '/' }, (res) => {
        res.resume()
        if (res.statusCode && res.statusCode < 600) resolve()
        else retry()
      })
      req.on('error', retry)
      req.setTimeout(1000, () => {
        req.destroy()
        retry()
      })
    }
    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        reject(new Error(`port ${port} not ready after ${timeoutMs}ms`))
        return
      }
      setTimeout(tick, 500)
    }
    tick()
  })
}

function spawnService(
  name: string,
  cwd: string,
  args: string[],
  env: Record<string, string>,
): ChildProcess {
  const opts: SpawnOptions = {
    cwd,
    env: { ...process.env, ...env },
    stdio: 'pipe',
    detached: true,
  }
  const proc = spawn('python3', args, opts)
  proc.stdout?.on('data', (d) => {
    if (process.env.E2E_DEBUG) console.log(`[${name}]`, d.toString().trim())
  })
  proc.stderr?.on('data', (d) => {
    if (process.env.E2E_DEBUG) console.error(`[${name}]`, d.toString().trim())
  })
  return proc
}

export default async function globalSetup() {
  // apps/web/tests/e2e/global-setup.ts → ../../../services/admin (apps/web 在 mis-system 内)
  const adminDir = path.resolve(
    __dirname,
    '..',  // tests/e2e -> tests
    '..',  // tests -> web
    '..',  // web -> apps
    '..',  // apps -> mis-system (apps/web 直接在 mis-system 下)
    'services',
    'admin',
  )
  if (existsSync(adminDir)) {
    adminProc = spawnService(
      'admin',
      adminDir,
      [
        '-m', 'uvicorn', 'app.main:app',
        '--host', '127.0.0.1', '--port', String(ADMIN_PORT), '--log-level', 'warning',
      ],
      {
        DB_DRIVER: 'sqlite',
        SQLITE_PATH: './test_e2e_playwright.db',
        JWT_SECRET: 'e2e-playwright-test-secret-key-1234567890',
        INIT_ADMIN_PASSWORD: 'admin1234',
        OA_AGENT_URL: `http://127.0.0.1:${OA_AGENT_PORT}`,
        LOG_LEVEL: 'WARNING',
      },
    )
    try {
      await waitPort(ADMIN_PORT, 30000)
      console.log(`[e2e] admin :${ADMIN_PORT} ready`)
    } catch (e) {
      console.error(`[e2e] admin 启动失败: ${e}`)
    }
  } else {
    console.error(`[e2e] admin dir not found: ${adminDir}`)
  }

  // apps/web/tests/e2e → ../../../../oa-agent (从 mis-system 上溯到仓库根)
  const oaDir = path.resolve(
    __dirname,
    '..',  // tests/e2e -> tests
    '..',  // tests -> web
    '..',  // web -> apps
    '..',  // apps -> mis-system
    '..',  // mis-system -> szdhts-a (仓库根)
    'oa-agent',
  )
  if (existsSync(oaDir)) {
    oaAgentProc = spawnService(
      'oa-agent',
      oaDir,
      [
        '-m', 'uvicorn', 'oa_agent.api:create_app', '--factory',
        '--host', '127.0.0.1', '--port', String(OA_AGENT_PORT), '--log-level', 'warning',
      ],
      {
        PYTHONPATH: path.join(oaDir, 'src'),
      },
    )
    try {
      await waitPort(OA_AGENT_PORT, 30000)
      console.log(`[e2e] oa-agent :${OA_AGENT_PORT} ready`)
    } catch {
      console.warn(`[e2e] oa-agent 未就绪，继续`)
    }
  }

  return async function teardown() {
    for (const [name, proc] of [
      ['admin', adminProc],
      ['oa-agent', oaAgentProc],
    ] as const) {
      if (proc && !proc.killed) {
        try {
          process.kill(-proc.pid!, 'SIGTERM')
        } catch {
          try {
            proc.kill('SIGTERM')
          } catch {
            /* ignore */
          }
        }
        console.log(`[e2e] ${name} stopped`)
      }
    }
    const dbPath = path.resolve(adminDir, 'test_e2e_playwright.db')
    if (existsSync(dbPath)) {
      try {
        await fs.unlink(dbPath)
      } catch {
        /* ignore */
      }
    }
  }
}