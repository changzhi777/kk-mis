import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import adminApi from '@/api/admin'
import type { LoginResult, UserInfo } from '@/api/admin'
import type { MenuItem } from '@/types'

const TOKEN_KEY = 'kk-mis-admin-token'
const REFRESH_KEY = 'kk-mis-admin-refresh'
const USER_KEY = 'kk-mis-admin-user'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const userInfo = ref<UserInfo | null>(
    (() => {
      const raw = localStorage.getItem(USER_KEY)
      return raw ? (JSON.parse(raw) as UserInfo) : null
    })()
  )
  const menus = ref<MenuItem[]>([])

  const isLogin = computed(() => !!token.value)
  const roles = computed(() => userInfo.value?.roles || [])
  const permissions = computed(() => userInfo.value?.permissions || [])
  const isSuperAdmin = computed(
    () => roles.value.includes('super_admin') || permissions.value.includes('*')
  )

  function hasPermission(code: string): boolean {
    if (isSuperAdmin.value) return true
    return permissions.value.includes(code)
  }

  /** 写入登录态并拉取菜单（login/register 复用，DRY） */
  async function applyLogin(data: LoginResult) {
    token.value = data.access_token
    userInfo.value = data.user
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(REFRESH_KEY, data.refresh_token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    await fetchMenus()
  }

  async function login(username: string, password: string) {
    await applyLogin(await adminApi.login(username, password))
  }

  async function register(payload: {
    username: string; password: string; name: string; phone?: string; email?: string
  }) {
    await applyLogin(await adminApi.register(payload))
  }

  /** OAuth 回调用：只有 token，需 fetchMe 拉 user */
  async function applyOAuthLogin(accessToken: string, refreshToken: string) {
    token.value = accessToken
    userInfo.value = null
    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(REFRESH_KEY, refreshToken)
    await fetchMe()
    await fetchMenus()
  }

  async function fetchMenus() {
    if (!token.value) {
      menus.value = []
      return
    }
    try {
      menus.value = await adminApi.fetchMenus()
    } catch {
      menus.value = []
    }
  }

  async function fetchMe() {
    userInfo.value = await adminApi.me()
    localStorage.setItem(USER_KEY, JSON.stringify(userInfo.value))
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    menus.value = []
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return {
    token,
    userInfo,
    menus,
    isLogin,
    roles,
    permissions,
    isSuperAdmin,
    hasPermission,
    login,
    register,
    applyOAuthLogin,
    fetchMe,
    fetchMenus,
    logout,
  }
})
