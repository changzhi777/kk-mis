/**
 * C 端终端用户登录态（独立于 admin stores/user）
 * token 存 localStorage，与 admin token 分离（公开页 admin 未登录，C 端独立）
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { EndUser } from '@/api/cms'

const TOKEN_KEY = 'kk-cms-end-user-token'
const USER_KEY = 'kk-cms-end-user'

export const useEndUserStore = defineStore('endUser', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref<EndUser | null>(
    (() => {
      const raw = localStorage.getItem(USER_KEY)
      return raw ? (JSON.parse(raw) as EndUser) : null
    })()
  )

  const isLogin = computed(() => !!token.value)
  /** 显示名：昵称优先，否则手机号脱敏 */
  const displayName = computed(() => {
    if (!user.value) return ''
    return user.value.nickname || user.value.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
  })

  function setAuth(t: string, u: EndUser) {
    token.value = t
    user.value = u
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, JSON.stringify(u))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return { token, user, isLogin, displayName, setAuth, logout }
})
