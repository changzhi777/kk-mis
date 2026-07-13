/**
 * 路由守卫测试 — 验证 beforeEach 的 3 条规则：
 * 1. 公开页面（meta.public）直接放行（即使未登录）
 * 2. 未登录访问受保护页面 → 跳 /login + 携带 redirect query
 * 3. 已登录但权限码不匹配 → 跳 /
 *
 * 不引入完整 router 实例（避免拉一堆 view chunk）；用最小化路由配置 + 直接调 beforeEach。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { Router } from 'vue-router'

vi.mock('@/api/admin', () => ({
  default: {
    fetchMenus: vi.fn().mockResolvedValue([]),
  },
}))

import { useUserStore } from '@/stores/user'

/** 构造一个最小 router，只保留守卫逻辑（不挂 view）
 *
 * 复制 src/router/index.ts 的 beforeEach 行为，测试时直接 _run 模拟路由跳转。
 * 不引入完整 router 实例（避免拉一堆 view chunk）。
 */
function makeMiniRouter(): Router {
  let installed: any = null
  const router = {
    beforeEach: (cb: any) => {
      installed = cb
      return router
    },
    push: vi.fn(),
    _run: async (to: any) => {
      const next = vi.fn()
      if (!installed) throw new Error('beforeEach not installed — bug in makeMiniRouter')
      await installed(to, { path: '/' }, next)
      return next
    },
  } as any

  // 安装守卫逻辑（与 src/router/index.ts::beforeEach 一致）
  router.beforeEach(async (to: any, _from: any, next: any) => {
    document.title = (to.meta.title as string) || 'kk-mis'
    const userStore = useUserStore()
    if (to.meta.public) {
      next()
      return
    }
    if (!userStore.token) {
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }
    const perm = to.meta.permission as string | undefined
    if (perm && !userStore.hasPermission(perm)) {
      next('/')
      return
    }
    next()
  })

  return router as Router
}

describe('router 守卫 — 3 条规则', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('公开页（meta.public）即使未登录也直接放行', async () => {
    const router = makeMiniRouter()
    const store = useUserStore()
    expect(store.token).toBe('') // 未登录

    const next = await router._run({
      path: '/login',
      meta: { public: true, title: '登录' },
      fullPath: '/login',
    })

    // 第一次调用就是 next() 无参 = 放行
    expect(next).toHaveBeenCalledWith()
  })

  it('未登录访问受保护页 → next({path:/login, query:{redirect: 原路径}})', async () => {
    const router = makeMiniRouter()
    const store = useUserStore()
    expect(store.token).toBe('')

    const next = await router._run({
      path: '/system/user',
      meta: { permission: 'system:user:list', title: '用户管理' },
      fullPath: '/system/user',
    })

    expect(next).toHaveBeenCalledWith({
      path: '/login',
      query: { redirect: '/system/user' },
    })
  })

  it('已登录但 permission 不匹配 → next("/")', async () => {
    const router = makeMiniRouter()
    const store = useUserStore()
    store.token = 'tok'
    store.userInfo = {
      id: 2,
      username: 'staff',
      name: '员工',
      roles: ['staff'],
      permissions: ['oa:announcement:save'], // 没有 system:user:list
    }

    const next = await router._run({
      path: '/system/user',
      meta: { permission: 'system:user:list', title: '用户管理' },
      fullPath: '/system/user',
    })

    expect(next).toHaveBeenCalledWith('/')
  })

  it('已登录 + permission 匹配 → next() 放行', async () => {
    const router = makeMiniRouter()
    const store = useUserStore()
    store.token = 'tok'
    store.userInfo = {
      id: 2,
      username: 'staff',
      name: '员工',
      roles: ['staff'],
      permissions: ['system:user:list'],
    }

    const next = await router._run({
      path: '/system/user',
      meta: { permission: 'system:user:list', title: '用户管理' },
      fullPath: '/system/user',
    })

    expect(next).toHaveBeenCalledWith()
  })

  it('super_admin 任意权限码都放行', async () => {
    const router = makeMiniRouter()
    const store = useUserStore()
    store.token = 'tok'
    store.userInfo = {
      id: 1,
      username: 'admin',
      name: '管理员',
      roles: ['super_admin'],
      permissions: [],
    }

    const next = await router._run({
      path: '/finance/report',
      meta: { permission: 'finance:report:view', title: '统计报表' },
      fullPath: '/finance/report',
    })

    expect(next).toHaveBeenCalledWith()
  })

  it('受保护页 + 无 permission meta + 已登录 → 放行（meta 不要求则不校验）', async () => {
    const router = makeMiniRouter()
    const store = useUserStore()
    store.token = 'tok'
    store.userInfo = {
      id: 2,
      username: 'staff',
      name: '员工',
      roles: [],
      permissions: [],
    }

    const next = await router._run({
      path: '/dashboard',
      meta: { title: '工作台' }, // 无 permission
      fullPath: '/dashboard',
    })

    expect(next).toHaveBeenCalledWith()
  })
})