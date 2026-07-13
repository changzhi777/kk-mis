/**
 * stores/user RBAC 核心逻辑测试。
 *
 * 覆盖：
 * - isLogin / isSuperAdmin computed
 * - hasPermission 行为（super_admin 通配 / 普通用户精确匹配 / 未登录拒绝）
 * - applyLogin 写入 token + userInfo + localStorage
 * - logout 清空所有状态
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// mock adminApi 避免调真实接口
vi.mock('@/api/admin', () => ({
  default: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    fetchMenus: vi.fn().mockResolvedValue([]),
  },
}))

import { useUserStore } from '@/stores/user'

describe('stores/user — RBAC 核心', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  describe('isLogin / isSuperAdmin', () => {
    it('初始无 token 时 isLogin=false', () => {
      const store = useUserStore()
      expect(store.isLogin).toBe(false)
      expect(store.isSuperAdmin).toBe(false)
    })

    it('有 token 但无 userInfo 时 isLogin=true', () => {
      const store = useUserStore()
      store.token = 'abc123'
      expect(store.isLogin).toBe(true)
    })

    it('roles 含 super_admin → isSuperAdmin=true', () => {
      const store = useUserStore()
      store.userInfo = {
        id: 1,
        username: 'admin',
        name: '管理员',
        roles: ['super_admin'],
        permissions: [],
      }
      expect(store.isSuperAdmin).toBe(true)
    })

    it('permissions 含 * 通配 → isSuperAdmin=true', () => {
      const store = useUserStore()
      store.userInfo = {
        id: 2,
        username: 'wildcard',
        name: '通配',
        roles: [],
        permissions: ['*'],
      }
      expect(store.isSuperAdmin).toBe(true)
    })
  })

  describe('hasPermission', () => {
    it('super_admin 对任意 code 返回 true（即使权限列表里没有）', () => {
      const store = useUserStore()
      store.userInfo = {
        id: 1,
        username: 'admin',
        name: '管理员',
        roles: ['super_admin'],
        permissions: [],
      }
      expect(store.hasPermission('system:user:list')).toBe(true)
      expect(store.hasPermission('finance:report:view')).toBe(true)
    })

    it('普通用户：权限码匹配 → true', () => {
      const store = useUserStore()
      store.userInfo = {
        id: 2,
        username: 'staff',
        name: '员工',
        roles: ['staff'],
        permissions: ['oa:announcement:save', 'finance:transaction:save'],
      }
      expect(store.hasPermission('oa:announcement:save')).toBe(true)
      expect(store.hasPermission('finance:transaction:save')).toBe(true)
    })

    it('普通用户：权限码不匹配 → false', () => {
      const store = useUserStore()
      store.userInfo = {
        id: 2,
        username: 'staff',
        name: '员工',
        roles: ['staff'],
        permissions: ['oa:announcement:save'],
      }
      expect(store.hasPermission('system:user:list')).toBe(false)
    })

    it('未登录（无 userInfo）→ 任何权限码返回 false', () => {
      const store = useUserStore()
      expect(store.userInfo).toBeNull()
      expect(store.hasPermission('oa:announcement:save')).toBe(false)
    })
  })

  describe('login + logout', () => {
    it('login() 写入 token + userInfo + 3 个 localStorage 键', async () => {
      const adminApi = (await import('@/api/admin')).default
      vi.mocked(adminApi.login).mockResolvedValueOnce({
        access_token: 'tok-123',
        refresh_token: 'ref-456',
        user: {
          id: 3,
          username: 'alice',
          name: 'Alice',
          roles: ['staff'],
          permissions: ['oa:announcement:save'],
        },
      } as any)

      const store = useUserStore()
      await store.login('alice', 'pass')

      expect(store.token).toBe('tok-123')
      expect(store.userInfo?.username).toBe('alice')
      expect(localStorage.getItem('kk-mis-admin-token')).toBe('tok-123')
      expect(localStorage.getItem('kk-mis-admin-refresh')).toBe('ref-456')
      expect(JSON.parse(localStorage.getItem('kk-mis-admin-user') || '{}').username).toBe(
        'alice'
      )
    })

    it('logout 清空 token + userInfo + 3 个 localStorage 键', async () => {
      const adminApi = (await import('@/api/admin')).default
      vi.mocked(adminApi.login).mockResolvedValueOnce({
        access_token: 'tok-123',
        refresh_token: 'ref-456',
        user: { id: 1, username: 'x', name: 'X', roles: [], permissions: [] },
      } as any)

      const store = useUserStore()
      await store.login('x', 'p')

      store.logout()

      expect(store.token).toBe('')
      expect(store.userInfo).toBeNull()
      expect(localStorage.getItem('kk-mis-admin-token')).toBeNull()
      expect(localStorage.getItem('kk-mis-admin-refresh')).toBeNull()
      expect(localStorage.getItem('kk-mis-admin-user')).toBeNull()
    })
  })
})